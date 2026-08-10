#
# Copyright (c) 2026 Glenn Siegman (glenn@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Generation phase: cast the personas, then write the comments.

Two steps appended after the planner's Serialize step:

- **Step 8 - Cast** is pure Python. It copies the deterministic
  :func:`agora.casting.cast_thread` assignments onto the planned
  :class:`~agora.models.Thread`, marks the identity booleans
  (``is_mod``, ``is_op``), and decides the deterministic dressing
  flags (``edited``, ``controversial``) — those must exist *before*
  text is written because they change what the text says (an edited
  comment carries an EDIT line; a controversial encounter turn reads
  sharper).

- **Step 9 - Voice** walks the cast slots in the-mod.md generation
  order (teaser first, then encounter chains in turn order, then
  signal, then the noise fill) and asks the LLM to write each comment
  body. Every call runs through :func:`pipeline.tasks.run_task` with
  the pipeline guard floor prepended to the assigned persona's
  ``system_prompt``, and every paper-derived or previously generated
  block in the user message rides inside ``ctx.inject_untrusted``
  markers — the same prompt-injection boundary the dispatch path
  enforces. Each written body is then checked (required verbatim
  blockquote present; every URL drawn from the verified link
  inventory) and rejected bodies are rewritten with the violations
  appended, twice, before the step fails. ``deleted``-role slots
  never reach the LLM: their body is the literal ``[deleted]`` and
  the flag is set here.

Votes, scores, orderings, and time labels stay ``None``/empty: the
reactor pass owns votes and everything display-side derives from
them.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable

from pipeline import StepContext, StepSpec, run_task
from pipeline.agents import AgentBackend
from pipeline.errors import ValidationStepError

from agora import mod_reference
from agora.casting import MISCONCEPTION_STANCE, _stable_key, cast_thread
from agora.models import CommentOutput, PipelineState, Reply, Thread
from agora.roster import MODS, PERSONA_BY_USERNAME

logger = logging.getLogger(__name__)

_STEP_8_NUMBER = 8
_STEP_9_NUMBER = 9

DELETED_BODY = "[deleted]"
"""Literal body for ``deleted``-role slots. The artifact requires a
non-empty body on every comment; a deleted comment's body is the
placeholder Reddit shows, not generated text."""

_SIGNAL_AGENT_ROLES = frozenset({"signal", "teaser", "encounter", "mod"})
"""Roles routed through the ``signal`` logical model. Everything else
(noise, tangent) goes through ``noise``. Mod actions ride the signal
slot: they are short but must be procedurally accurate."""

_EDITED_PARITY_MOD = 2
"""An edited comment appears in roughly half of all threads: the
document hash's parity decides, so the same paper always gets the
same answer."""

_VOICE_MAX_ATTEMPTS = 3
"""Tries per slot: the write plus up to two corrective rewrites
before Step 9 fails the run (no partial artifact is ever persisted)."""

_URL_RE = re.compile(r"https?://[^\s<>()\[\]{}\"'`]+", re.IGNORECASE)

_PAPER_REF_RE = re.compile(r"\b([PN]\d{4})(R\d+)?\b")
"""WG21 paper ids as they appear in paper text (``P2900``,
``P2900R14``, ``N4950``). Feeds the wg21.link allowance: a paper the
source document cites certainly exists, so linking it is safe."""


# -- Step 8 - Cast -------------------------------------------------------------


async def _pure_cast(state: PipelineState, ctx: StepContext, spec: StepSpec) -> None:
    """Assign a persona to every slot and set the pre-text flags."""
    thread = state.thread
    assert thread is not None, "Step 8 requires the Thread from Step 7."

    casting = cast_thread(thread)
    thread.submission_poster_id = casting.submission_poster

    mod_usernames = {mod.username for mod in MODS}
    for reply in thread.replies:
        username = casting.assignments[reply.slot_id]
        reply.character_username = username
        reply.is_mod = username in mod_usernames
        reply.is_op = username == casting.submission_poster

    _flag_edited(thread)
    _flag_controversial(thread)

    logger.info(
        "Step 8: cast %d slots; poster=%s; regulars=%s",
        len(casting.assignments),
        casting.submission_poster,
        ", ".join(casting.regulars),
    )


def _flag_edited(thread: Thread) -> None:
    """Mark at most one signal comment as edited, deterministically.

    Roughly half of all threads carry an edit (document-hash parity);
    the flagged slot is the stable-hash minimum among signal slots, so
    re-running the same blueprint flags the same comment. The voice
    step reads the flag and appends the EDIT line.
    """
    if _stable_key(thread.document, "edited") % _EDITED_PARITY_MOD:
        return
    signal_slots = [r for r in thread.replies if r.role == "signal"]
    if not signal_slots:
        return
    chosen = min(
        signal_slots,
        key=lambda r: _stable_key(thread.document, "edited", r.slot_id),
    )
    chosen.edited = True


def _flag_controversial(thread: Thread) -> None:
    """Mark each encounter's sharpening turn (the second) controversial."""
    by_slot = {reply.slot_id: reply for reply in thread.replies}
    for plan in thread.encounters:
        if len(plan.slot_ids) < 2:
            continue
        sharpening = by_slot.get(plan.slot_ids[1])
        if sharpening is not None:
            sharpening.controversial = True


# -- Step 9 - Voice ------------------------------------------------------------


async def _pure_voice(state: PipelineState, ctx: StepContext, spec: StepSpec) -> None:
    """Write every comment body in the assigned persona's voice."""
    thread = state.thread
    assert thread is not None, "Step 9 requires the Thread from Step 7."

    instructions = ctx.prompt.step_section(spec.step.name)
    link_section, allowed_urls = _verified_links(state, thread)
    ordered = generation_order(thread)
    total = len(ordered)

    for index, reply in enumerate(ordered):
        if reply.role == "deleted":
            reply.content = DELETED_BODY
            reply.deleted = True
            continue

        username = reply.character_username or ""
        persona = PERSONA_BY_USERNAME.get(username)
        if persona is None:
            raise ValidationStepError(
                _STEP_9_NUMBER, spec.step.name,
                ValueError(
                    f"Slot {reply.slot_id!r} has no cast persona"
                    f" (character_username={username!r}); Step 8 must run first."
                ),
            )

        base_msg = _voice_message(
            thread, reply, instructions, ctx.inject_untrusted, link_section,
        )
        user_msg = base_msg
        for attempt in range(1, _VOICE_MAX_ATTEMPTS + 1):
            output = await run_task(
                _agent_for(reply, ctx, spec),
                f"{ctx.guard_instruction}\n\n{persona.system_prompt}",
                user_msg,
                CommentOutput,
                label=f"{spec.step.name} ({reply.slot_id})",
                debug_log=ctx.debug_log if ctx.debug else None,
            )
            content = output.content.strip()
            problems = _content_violations(reply, content, thread, allowed_urls)
            if not problems:
                break
            if attempt == _VOICE_MAX_ATTEMPTS:
                raise ValidationStepError(
                    _STEP_9_NUMBER, spec.step.name,
                    ValueError(
                        f"Slot {reply.slot_id!r} failed content validation"
                        f" after {_VOICE_MAX_ATTEMPTS} attempts:"
                        f" {'; '.join(problems)}"
                    ),
                )
            logger.info(
                "Step 9: rewriting %s (attempt %d rejected: %s)",
                reply.slot_id, attempt, "; ".join(problems),
            )
            user_msg = _corrected_message(base_msg, problems)
        reply.content = content
        ctx.sub_progress(index, total, f"{spec.step.name} {reply.slot_id}")

    missing = [r.slot_id for r in thread.replies if not r.content]
    if missing:
        raise ValidationStepError(
            _STEP_9_NUMBER, spec.step.name,
            ValueError(f"Slots left without content after voice pass: {missing}."),
        )


def _agent_for(reply: Reply, ctx: StepContext, spec: StepSpec) -> AgentBackend:
    """Route signal-tier writes through ``signal``, the rest through
    ``noise``; fall back to the step's own model when a logical name
    is not bound (unit tests bind only the step model)."""
    name = "signal" if reply.role in _SIGNAL_AGENT_ROLES else "noise"
    agent = ctx.agents.get(name)
    if agent is None:
        agent = ctx.agents[spec.step.model]
    return agent


def generation_order(thread: Thread) -> list[Reply]:
    """the-mod.md section 9 order: teaser, encounters, signal, fill.

    Encounter chains run in plan order, each chain in turn order, so
    every turn can read the prior turns. Signal (including the
    misconception-trap corrections) precedes the noise fill, so a
    trap's confused question is written last and can be reverse-fit
    to the correction it provoked. Within each class, blueprint order
    is kept — the whole walk is deterministic.
    """
    by_slot = {reply.slot_id: reply for reply in thread.replies}
    encounter_slot_ids = {
        slot_id for plan in thread.encounters for slot_id in plan.slot_ids
    }
    ordered: list[Reply] = []
    seen: set[str] = set()

    def take(reply: Reply) -> None:
        if reply.slot_id not in seen:
            seen.add(reply.slot_id)
            ordered.append(reply)

    for reply in thread.replies:
        if reply.role == "teaser" and reply.slot_id not in encounter_slot_ids:
            take(reply)
    for plan in thread.encounters:
        for slot_id in plan.slot_ids:
            if slot_id in by_slot:
                take(by_slot[slot_id])
    for reply in thread.replies:
        if reply.role == "signal":
            take(reply)
    for reply in thread.replies:
        take(reply)
    return ordered


# -- Voice prompt assembly -----------------------------------------------------


def _voice_message(
    thread: Thread,
    reply: Reply,
    instructions: str,
    inject: Callable[[str], str],
    link_section: str,
) -> str:
    """Assemble the per-slot user message for the voice call.

    ``inject`` is ``ctx.inject_untrusted``: every paper-derived or
    previously generated block (submission body, anchor claim text,
    ancestor comments, the trap correction) crosses into the prompt
    inside guard markers, matching the dispatch-path boundary.
    """
    parts = [
        _thread_context(thread, inject),
        _assignment(thread, reply, inject),
    ]
    ancestry = _ancestry(thread, reply, inject)
    if ancestry:
        parts.append(ancestry)
    encounter = _encounter_context(thread, reply)
    if encounter:
        parts.append(encounter)
    trap = _trap_context(thread, reply, inject)
    if trap:
        parts.append(trap)
    constraints = _constraints(reply)
    if constraints:
        parts.append(constraints)
    parts.append(link_section)
    parts.append(
        f"## The Mod Reference (the-mod.md)\n\n{_mod_excerpts_for(reply)}"
    )
    parts.append(f"## Instructions\n\n{instructions}")
    return "\n\n".join(parts)


def _thread_context(thread: Thread, inject: Callable[[str], str]) -> str:
    return (
        f"## Thread\n\n"
        f"- paper: {thread.document} — {thread.title}\n"
        f"- authors: {', '.join(thread.authors)}\n"
        f"- committee: {thread.committee}; heat: {thread.heat};"
        f" interest: {thread.interest}\n"
        f"- submission by u/{thread.submission_poster_id}:"
        f" **{thread.submission_title}**\n"
        f"- link: {thread.submission_link}\n\n"
        f"### Submission body\n\n{inject(thread.submission_body)}"
    )


def _assignment(
    thread: Thread, reply: Reply, inject: Callable[[str], str],
) -> str:
    lines = [
        "## Your Comment",
        "",
        f"- you are u/{reply.character_username}"
        + (" (the OP)" if reply.is_op else "")
        + (" (moderator)" if reply.is_mod else ""),
        f"- slot: {reply.slot_id}; role: {reply.role}; depth: {reply.depth}",
        f"- brief: {reply.brief}",
    ]
    if reply.noise_tone or reply.noise_stance:
        lines.append(
            f"- noise palette: tone={reply.noise_tone or '-'},"
            f" stance={reply.noise_stance or '-'}"
        )
    anchor = next(
        (a for a in thread.technical_anchors if a.id == reply.anchor_id),
        None,
    )
    if anchor is not None:
        lines += [
            "",
            f"### Anchor {anchor.id} ({anchor.kind})",
            "",
            f"- summary: {anchor.summary}",
            "- the paper says (verbatim):",
            "",
            inject(anchor.claim_text),
        ]
    return "\n".join(lines)


def _ancestry(
    thread: Thread, reply: Reply, inject: Callable[[str], str],
) -> str:
    """The chain above this comment, oldest first.

    Ancestors written earlier in the generation order contribute their
    text; ancestors not yet written contribute their brief, so every
    prompt stays deterministic within the fixed walk. The walk keeps a
    visited set: blueprint validation rejects cyclic parent graphs,
    but a cycle that slipped through must degrade to a truncated
    chain, not an infinite loop.
    """
    by_slot = {r.slot_id: r for r in thread.replies}
    chain: list[Reply] = []
    visited: set[str] = set()
    parent_id = reply.parent_slot_id
    while parent_id is not None and parent_id not in visited:
        visited.add(parent_id)
        parent = by_slot.get(parent_id)
        if parent is None:
            break
        chain.append(parent)
        parent_id = parent.parent_slot_id
    if not chain:
        return ""
    lines = ["## Comment Chain Above You (oldest first)", ""]
    for ancestor in reversed(chain):
        if ancestor.content:
            lines.append(
                f"- u/{ancestor.character_username} wrote:\n\n"
                f"{inject(ancestor.content)}"
            )
        else:
            lines.append(
                f"- u/{ancestor.character_username} will write a reply"
                f" whose brief is: {ancestor.brief}"
            )
    lines.append("")
    lines.append("You are replying to the last comment in this chain.")
    return "\n".join(lines)


def _encounter_context(thread: Thread, reply: Reply) -> str:
    plan = next(
        (p for p in thread.encounters if reply.slot_id in p.slot_ids),
        None,
    )
    if plan is None:
        return ""
    turn = plan.slot_ids.index(reply.slot_id)
    side = "A" if turn % 2 == 0 else "B"
    position = plan.position_a if side == "A" else plan.position_b
    return (
        f"## Encounter {plan.encounter_id}\n\n"
        f"- tension: {plan.design_tension}\n"
        f"- you argue position {side}: {position}\n"
        f"- this is turn {turn + 1} of {len(plan.slot_ids)};"
        f" the chain resolves by {plan.resolution}\n"
        f"- turn 1 is polite disagreement, turn 2 sharpens, the final"
        f" turn lands the {plan.resolution}"
    )


def _trap_context(
    thread: Thread, reply: Reply, inject: Callable[[str], str],
) -> str:
    """For a misconception-trap question: fit the question to its answer.

    The teaching correction (a signal child) is written before the
    noise fill, so by the time the confused question is generated its
    answer already exists. The question must be the one that answer
    actually addresses.
    """
    if reply.role != "noise" or reply.noise_stance != MISCONCEPTION_STANCE:
        return ""
    teaching = next(
        (
            child for child in thread.replies
            if child.parent_slot_id == reply.slot_id
            and child.role in ("signal", "teaser")
        ),
        None,
    )
    if teaching is None or not teaching.content:
        return ""
    return (
        f"## The Answer You Will Receive\n\n"
        f"u/{teaching.character_username} replies to your question with:\n\n"
        f"{inject(teaching.content)}\n\n"
        f"Write the confused or leading question that this reply"
        f" answers. Ask it in your own voice; do not know the answer."
    )


def _constraints(reply: Reply) -> str:
    items: list[str] = []
    if reply.carries_quote:
        items.append(
            "Quote the paper verbatim in a `>` blockquote (use the"
            " anchor's exact claim text or a fragment of the submission"
            " body — never paraphrase inside the blockquote)."
        )
    if reply.carries_code:
        items.append(
            "Include one 3-8 line C++ code block (syntactically"
            " plausible; a counter-example, breakage demo, or"
            " clarification)."
        )
    if reply.carries_link:
        items.append(
            "Include one URL copied verbatim from the Verified Links"
            " list in this message. Never invent or alter a URL."
        )
    if reply.edited:
        items.append(
            "This comment was edited after posting: append a final line"
            " starting with `EDIT:` that adds a small clarification or"
            " correction in the same voice."
        )
    if reply.controversial:
        items.append(
            "This is the exchange's sharpest turn: press the"
            " disagreement hard while staying technical."
        )
    if not items:
        return ""
    return "## Constraints\n\n" + "\n".join(f"- {item}" for item in items)


def _mod_excerpts_for(reply: Reply) -> str:
    if reply.encounter_id or reply.role == "encounter":
        return mod_reference.voice_encounter_excerpts()
    if reply.role == "mod":
        return mod_reference.voice_mod_excerpts()
    if reply.role in ("signal", "teaser"):
        return mod_reference.voice_signal_excerpts()
    return mod_reference.voice_noise_excerpts()


# -- Content validation ----------------------------------------------------------


def _verified_links(
    state: PipelineState, thread: Thread,
) -> tuple[str, frozenset[str]]:
    """The verified link inventory for this thread.

    Returns ``(prompt_section, allowed_urls)``: the ``## Verified
    Links`` section every voice prompt carries, and the normalized
    set the URL check accepts. Everything in it is verified by
    construction — the submission's resolved paper link, the
    paperstore url, URLs the Step 2 research agents actually visited,
    URLs from the paper's own external citations, and
    ``wg21.link/<id>`` for paper ids the paper's text cites (a paper
    the source document references certainly exists). Nothing else
    may appear in a comment.
    """
    urls: list[str] = []
    seen: set[str] = set()

    def _add(candidate: object) -> None:
        if not isinstance(candidate, str):
            return
        url = candidate.strip()
        if not url.lower().startswith(("http://", "https://")):
            return
        normalized = _normalize_url(url)
        if normalized not in seen:
            seen.add(normalized)
            urls.append(url)

    _add(thread.submission_link)
    _add(state.paper_url)
    _add(f"https://wg21.link/{thread.document.lower()}")
    rs = thread.research_summary
    for report in (rs.public_reception, rs.committee_history,
                   rs.author_ecosystem):
        for source in report.sources:
            _add(source)
    for row in state.dissect_external_citations or []:
        for value in row.values():
            _add(value)

    cited: set[str] = {thread.paper.upper()}
    for match in _PAPER_REF_RE.finditer(state.paper_source or ""):
        cited.add(match.group(1).upper())
        if match.group(2):
            cited.add((match.group(1) + match.group(2)).upper())

    allowed = set(seen)
    for pid in cited:
        allowed.add(_normalize_url(f"https://wg21.link/{pid.lower()}"))

    lines = [
        "## Verified Links",
        "",
        "If your comment includes any URL, copy it verbatim from this"
        " list. Never invent, guess, or alter a URL — prefer no link"
        " over a made-up one.",
        "",
    ]
    lines += [f"- {url}" for url in urls]
    lines.append(
        "- https://wg21.link/<paper-id> for a paper this paper cites: "
        + ", ".join(sorted(cited))
    )
    return "\n".join(lines), frozenset(allowed)


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/").lower()


def _extract_urls(content: str) -> list[str]:
    return [m.group(0).rstrip(".,;:!?*") for m in _URL_RE.finditer(content)]


def _content_violations(
    reply: Reply,
    content: str,
    thread: Thread,
    allowed_urls: frozenset[str],
) -> list[str]:
    """Check one written body against the enforceable slot constraints."""
    problems: list[str] = []
    if reply.carries_quote:
        quote_problem = _quote_violation(content, thread)
        if quote_problem:
            problems.append(quote_problem)
    for url in _extract_urls(content):
        if _normalize_url(url) not in allowed_urls:
            problems.append(
                f"The URL {url} is not in the Verified Links list;"
                f" use a listed URL verbatim or drop the link."
            )
    return problems


def _quote_violation(content: str, thread: Thread) -> str | None:
    """Require a ``>`` blockquote whose text is verbatim paper text.

    A blockquote satisfies the slot when its whitespace-squashed text
    is a contiguous fragment of an anchor's claim text or of the
    submission body — the two sources the constraint offers.
    """
    blocks = _blockquote_blocks(content)
    if not blocks:
        return (
            "The comment must quote the paper in a `>` blockquote"
            " and none was found."
        )
    sources = [_squash_ws(a.claim_text) for a in thread.technical_anchors]
    sources.append(_squash_ws(thread.submission_body))
    for block in blocks:
        text = _squash_ws(block)
        if text and any(text in source for source in sources):
            return None
    return (
        "No `>` blockquote matches the paper verbatim: quote the"
        " anchor's exact claim text (or an exact fragment of the"
        " submission body) without paraphrasing."
    )


def _blockquote_blocks(content: str) -> list[str]:
    """Contiguous ``>``-prefixed line runs, each squashed to one string."""
    blocks: list[str] = []
    current: list[str] = []
    for line in content.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(">"):
            current.append(stripped.lstrip("> ").strip())
        elif current:
            blocks.append(" ".join(current))
            current = []
    if current:
        blocks.append(" ".join(current))
    return blocks


def _squash_ws(text: str) -> str:
    return " ".join(text.split())


def _corrected_message(base_msg: str, problems: list[str]) -> str:
    bullets = "\n".join(f"- {p}" for p in problems)
    return (
        f"{base_msg}\n\n## Corrections\n\n"
        f"Your previous attempt was rejected for the reasons below."
        f" Rewrite the comment — same brief, same voice — fixing"
        f" every one:\n\n{bullets}"
    )
