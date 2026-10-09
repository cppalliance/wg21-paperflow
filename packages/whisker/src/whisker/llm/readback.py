#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""whisker-readback: blind LLM read-back validation of comprehension facts.

Opt-in CLI in the tapetum-llm extra. For each paper with a ``.facts.jsonl``,
generates a comprehension question per fact, sends it blind to the
alliance-pod (DeepSeek-V4-Pro), compares the answer to the expected value,
and renders PASS/FAIL per fact in the terminal. Persists a markdown report
per paper for human blessing.

Blind protocol v2: ``present``/``absent``/``math``/``code``/``xref``/order
facts require an authored ``Fact.question`` that does not embed answer
lexemes. ``table``/``image_ref`` keep generated locus questions. An
adversarial ``--corrupt`` mode demonstrates the pod fails on corrupted
markdown. Generated present/absent questions that quoted ``fact.text``
were protocol v1 and are not a 100% claim.

D1 exemption: this module calls the LLM via raw httpx (not pipeline's
``run_agent``), because the read-back is a zero-shot Q&A task with no
pipeline prompt, no steps, no structured output. Documented exemption.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

import httpx

from whisker.facts import (
    _IMAGE_REF_RE,
    FACT_ABSENT,
    FACT_CODE,
    FACT_IMAGE_REF,
    FACT_MATH,
    FACT_ORDER,
    FACT_PRESENT,
    FACT_TABLE,
    FACT_XREF,
    SURFACE_RAW,
    Fact,
    _math_surface,
    _norm_cell,
    _present_within,
    _raw_surface,
)
from whisker.llm.unit_judge import (
    inject_code_rubric,
    inject_table_rubric,
    resolve_runtime_code_contract,
    resolve_runtime_table_contract,
)
from whisker.metrics import normalized_text
from whisker.tables import split_pipe_cells

logger = logging.getLogger(__name__)

__all__ = [
    "ReadbackResult",
    "question_leaks_answer",
    "readback_paper",
    "render_terminal",
    "render_markdown",
]

_AUTHORED_QUESTION_TYPES = frozenset({
    FACT_PRESENT, FACT_ABSENT, FACT_MATH, FACT_CODE, FACT_XREF, FACT_ORDER,
})
_LEAK_MIN_LEN = 4
_ABSENT_OK_RE = re.compile(
    r"\b(not found|does not appear|not present|absent|no longer appears)\b",
    re.IGNORECASE,
)

_DEFAULT_MODEL = "deepseek-v4-pro"
_REQUEST_TIMEOUT = 120.0
_MAX_ANSWER_TOKENS = 512
# Pod default flipped thinking-on; pin off for raw httpx probe calls.
_NON_THINK_CHAT_TEMPLATE_KWARGS: dict[str, object] = {"enable_thinking": False}
PROTOCOL_VERSION = "de-needle-v2"

# Corruption sentinel available for --corrupt-banner. NOT part of the
# measured control path by default (H2 audit finding): telling the model to
# distrust the document inflates corrupt-mode detection independently of
# whether the corruption itself is legible, which confounds the clean-vs-
# corrupt comparison (the banner gets measured, not the corruption). Off by
# default; explicit opt-in only, and every rendered report states whether it
# was applied so a banner-assisted run can never be mistaken for the
# unconfounded control.
_CORRUPT_PREFIX = (
    "--- CORRUPTION BLOCK: all tables, formulas, and references below have "
    "been scrambled for adversarial testing. Do not trust any data. ---\n\n"
)


@dataclass
class ReadbackCheck:
    """One fact's readback result.

    ``error`` marks transport/HTTP failures (timeouts, connection resets):
    the pod never answered, so the check is neither a pass nor a
    comprehension failure. ``weak`` marks passes whose evidence cannot be
    grounded in a quote (``absent`` facts: a NO answer has nothing to cite).
    """
    fact_id: str
    fact_type: str
    question: str
    expected: str
    pod_answer: str
    passed: bool
    latency_ms: int = 0
    error: bool = False
    weak: bool = False


@dataclass
class ReadbackResult:
    """All readback results for one paper.

    ``banner_applied`` records whether the priming ``_CORRUPT_PREFIX`` was
    added to the markdown sent to the pod (H2 audit finding): rendered in
    every report so a banner-assisted run is never mistaken for the
    unconfounded control.
    """
    pid: str
    checks: list[ReadbackCheck] = field(default_factory=list)
    model: str = ""
    corrupted: bool = False
    banner_applied: bool = False

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.passed and not c.error)

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed and not c.error)

    @property
    def error_count(self) -> int:
        return sum(1 for c in self.checks if c.error)


def _leak_needles(fact: Fact) -> tuple[str, ...]:
    """Strings that must not appear in a blind question."""
    if fact.type == FACT_ORDER:
        return fact.sequence
    if fact.type == FACT_TABLE:
        return tuple(value for _, value in fact.neighbors)
    if fact.type == FACT_IMAGE_REF:
        return ()
    if fact.text:
        return (fact.text,)
    return ()


def question_leaks_answer(fact: Fact, question: str) -> list[str]:
    """Return answer lexemes that appear as substrings in ``question``."""
    haystack = " ".join(question.lower().split())
    leaked: list[str] = []
    for needle in _leak_needles(fact):
        folded = " ".join(needle.lower().split())
        if len(folded) >= _LEAK_MIN_LEN and folded in haystack:
            leaked.append(needle)
    return leaked


def _expected_for(fact: Fact) -> str:
    if fact.type == FACT_ABSENT:
        return "NOT FOUND"
    if fact.type == FACT_ORDER:
        return " -> ".join(fact.sequence)
    if fact.type == FACT_TABLE:
        directions = ", ".join(f"{d}: {v}" for d, v in fact.neighbors)
        return f"cell={fact.cell}, {directions}"
    if fact.type == FACT_IMAGE_REF:
        return "IMAGE_REF"
    return fact.text


def _generate_locus_question(fact: Fact) -> str:
    """Generated questions for table/image_ref. Does not embed expected values."""
    if fact.type == FACT_TABLE:
        asks = []
        for d, _v in fact.neighbors:
            if d == "heading":
                asks.append(
                    f"the column heading of the column containing {fact.cell!r}"
                )
            else:
                asks.append(f"the cell immediately {d} of {fact.cell!r}")
        return (
            f"In the table containing cell {fact.cell!r}, identify: "
            f"{'; '.join(asks)}. Answer with the exact cell values."
        )
    if fact.type == FACT_IMAGE_REF:
        return (
            "Does the document contain any image references "
            "(markdown ![...](...) syntax)? Answer YES or NO, then quote "
            "one image reference exactly as it appears."
        )
    return ""


def _question_for(fact: Fact) -> str | None:
    """Return the question to send, or None if the fact is not runnable."""
    authored = fact.question.strip()
    if fact.type in _AUTHORED_QUESTION_TYPES:
        return authored or None
    if authored:
        return authored
    generated = _generate_locus_question(fact)
    return generated or None


def _grounded_quote(fact: Fact, answer: str) -> bool:
    """Check the answer quotes the fact's evidence (anti-sycophancy gate).

    A bare "YES" from an agreeable model must not count as comprehension:
    the pod is asked to quote the passage, so the fact text (fuzzy, within
    the fact's own ``max_diffs`` budget) must appear in the answer. For
    ``image_ref`` facts the quote is the ``![...](...)`` reference itself.
    """
    if fact.type == FACT_IMAGE_REF:
        if _IMAGE_REF_RE.search(answer):
            return True
        if fact.text:
            return _present_within(
                _raw_surface(fact.text), _raw_surface(answer), fact.max_diffs
            )
        return False
    if fact.type in (FACT_CODE, FACT_XREF) or fact.surface == SURFACE_RAW:
        return _present_within(
            _raw_surface(fact.text), _raw_surface(answer), fact.max_diffs
        )
    return _present_within(
        normalized_text(fact.text), normalized_text(answer), fact.max_diffs
    )


_WORD_BOUNDARY_TMPL = r"(?<![0-9a-z]){}(?![0-9a-z])"


def _cell_value_in_answer(expected_val: str, answer: str) -> bool:
    """Word-boundary match of a normalized cell value inside the answer.

    Plain substring matching let expected "8" pass on an answer containing
    "18" (red-team finding Jul 2026). Alphanumeric boundaries reject that
    while still matching values embedded in punctuation ("(8)", "8,").
    """
    want = _norm_cell(expected_val)
    haystack = _norm_cell(answer)
    return bool(re.search(_WORD_BOUNDARY_TMPL.format(re.escape(want)), haystack))


def _evaluate_answer(fact: Fact, expected: str, answer: str) -> tuple[bool, bool]:
    """Check the pod's answer against the expected value.

    Returns ``(passed, weak)``. ``weak`` is True for passes that cannot be
    grounded in a quote (``absent``: a correct NO cites nothing).
    """
    answer_lower = answer.lower().strip()
    if fact.type in (FACT_PRESENT, FACT_CODE, FACT_XREF, FACT_IMAGE_REF):
        return _grounded_quote(fact, answer), False
    if fact.type == FACT_ABSENT:
        ok = bool(_ABSENT_OK_RE.search(answer)) or answer_lower.startswith("no")
        return ok, ok
    if fact.type == FACT_MATH:
        ok = _present_within(
            _math_surface(fact.text), _math_surface(answer), fact.max_diffs
        )
        return ok, False
    if fact.type == FACT_ORDER:
        norm_answer = normalized_text(answer)
        positions = []
        for item in fact.sequence:
            pos = norm_answer.find(normalized_text(item))
            if pos == -1:
                return False, False
            positions.append(pos)
        return positions == sorted(positions), False
    if fact.type == FACT_TABLE:
        for _, expected_val in fact.neighbors:
            if not _cell_value_in_answer(expected_val, answer):
                return False, False
        return True, False
    return expected.lower() in answer_lower, False


def _ask_pod(
    client: httpx.Client,
    base_url: str,
    api_key: str,
    model: str,
    paper_md: str,
    question: str,
    *,
    table_fact: bool = False,
    code_fact: bool = False,
) -> tuple[str, int]:
    """Send a question to the pod and return (answer, latency_ms)."""
    system = (
        "You are a document comprehension assistant. "
        "Answer questions about the document below. "
        "Be precise and concise."
    )
    if table_fact:
        system = inject_table_rubric(
            system, resolve_runtime_table_contract(model=model)
        )
    if code_fact:
        system = inject_code_rubric(
            system, resolve_runtime_code_contract(model=model)
        )
    t0 = time.monotonic()
    resp = client.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": system,
                },
                {
                    "role": "user",
                    "content": (
                        f"DOCUMENT:\n{paper_md}\n\n"
                        f"QUESTION:\n{question}"
                    ),
                },
            ],
            "max_tokens": _MAX_ANSWER_TOKENS,
            "temperature": 0.0,
            "chat_template_kwargs": _NON_THINK_CHAT_TEMPLATE_KWARGS,
        },
        timeout=_REQUEST_TIMEOUT,
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    resp.raise_for_status()
    data = resp.json()
    choices = data.get("choices", [])
    if not choices:
        return "(no response)", latency_ms
    answer = choices[0].get("message", {}).get("content", "")
    return answer.strip(), latency_ms


def readback_paper(
    pid: str,
    paper_md: str,
    facts: list[Fact],
    *,
    base_url: str,
    api_key: str,
    model: str = _DEFAULT_MODEL,
    corrupt: bool = False,
    inject_banner: bool = False,
) -> ReadbackResult:
    """Run blind readback for all facts of one paper. Synchronous.

    ``inject_banner`` adds the priming ``_CORRUPT_PREFIX`` ahead of the
    corrupted markdown. Off by default (H2 audit finding): the banner
    inflates corrupt-mode detection independently of the corruption itself,
    confounding the clean-vs-corrupt comparison. Only meaningful when
    ``corrupt`` is also True; ``result.banner_applied`` records the actual
    outcome so it can never be silently assumed from the flag alone.
    """
    md = paper_md
    banner_applied = False
    if corrupt:
        md = _corrupt_markdown(md)
        if inject_banner:
            md = _CORRUPT_PREFIX + md
            banner_applied = True

    result = ReadbackResult(
        pid=pid, model=model, corrupted=corrupt, banner_applied=banner_applied,
    )

    with httpx.Client() as client:
        for fact in facts:
            expected = _expected_for(fact)
            question = _question_for(fact)
            if question is None:
                result.checks.append(ReadbackCheck(
                    fact_id=fact.id,
                    fact_type=fact.type,
                    question="",
                    expected=expected,
                    pod_answer=(
                        "(schema error: authored question required for "
                        f"{fact.type})"
                    ),
                    passed=False,
                    error=True,
                ))
                continue
            leaked = question_leaks_answer(fact, question)
            if leaked:
                result.checks.append(ReadbackCheck(
                    fact_id=fact.id,
                    fact_type=fact.type,
                    question=question,
                    expected=expected,
                    pod_answer=f"(schema error: question leaks {leaked!r})",
                    passed=False,
                    error=True,
                ))
                continue

            error = False
            try:
                answer, latency = _ask_pod(
                    client, base_url, api_key, model, md, question,
                    table_fact=fact.type == FACT_TABLE,
                    code_fact=fact.type == FACT_CODE,
                )
            except (httpx.HTTPError, KeyError) as exc:
                # Transport failure: the pod never answered, so this is an
                # ERROR (rerun), not a comprehension FAIL (Fix 6).
                answer = f"(transport error: {type(exc).__name__}: {exc})"
                latency = 0
                error = True

            if error:
                passed, weak = False, False
            else:
                passed, weak = _evaluate_answer(fact, expected, answer)
            result.checks.append(ReadbackCheck(
                fact_id=fact.id,
                fact_type=fact.type,
                question=question,
                expected=expected,
                pod_answer=answer,
                passed=passed,
                latency_ms=latency,
                error=error,
                weak=weak,
            ))

    return result


_HEADING_RE = re.compile(r"^(#{2,6})\s")
_WORD_SWAP_RE = re.compile(r"\b(\w{4,})\b")
_CODE_IDENT_RE = re.compile(r"\b([a-z_]\w{3,})\b")

# Corruption cadence: every Nth qualifying line is corrupted. Low enough to
# produce measurable metric movement, high enough to leave the document
# recognizably the same (so the LLM should still partially comprehend it).
_CORRUPT_EVERY_NTH_LINE = 3


def _corrupt_markdown(md: str) -> str:
    """Deterministically corrupt markdown for adversarial testing.

    The previous implementation only reversed table cells, flipped ``>=`` to
    ``<=``, and bumped superscripts. The ``>=`` flip is invisible to the
    deterministic text axes (E28: ``clean_string`` strips both operators to
    the same alnum sequence), so the negative control had no teeth on the
    metric surface. This revision applies five corruption strategies that
    REGISTER on the deterministic AND punctuation-preserving axes:

    1. **Table cell reversal** (unchanged): swaps cell order within rows.
    2. **Operator flip** (unchanged): ``>=`` -> ``<=``. Now detectable via
       the punctuation-sensitive soft flag.
    3. **Superscript increment** (unchanged): ``^N`` -> ``^(N+1)``.
    4. **Heading level shift**: bumps ``##`` -> ``###`` etc. every Nth
       heading, measurable via MHS.
    5. **Prose word deletion**: drops one word per Nth prose line,
       measurable via unigram coverage/recall.
    6. **Code identifier mangling**: reverses identifiers in fenced code
       blocks every Nth line, measurable via code-span content checks.
    """
    lines = md.split("\n")
    result: list[str] = []
    in_code = False
    prose_idx = 0
    heading_idx = 0
    code_idx = 0

    in_html_table = False
    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()

        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code = not in_code
            result.append(line)
            continue

        if in_code:
            code_idx += 1
            if code_idx % _CORRUPT_EVERY_NTH_LINE == 0:
                line = _CODE_IDENT_RE.sub(
                    lambda m: m.group(1)[::-1], line, count=1
                )
            result.append(line)
            continue

        if "<table" in lower:
            in_html_table = True
        if in_html_table:
            result.append(line)
            if "</table" in lower:
                in_html_table = False
            continue

        if "|" in stripped:
            cells = split_pipe_cells(line)
            if len(cells) >= 2:
                line = "| " + " | ".join(reversed(cells)) + " |"

        line = re.sub(r">=", "<=", line)
        line = re.sub(r"\^(\d+)", lambda m: f"^{int(m.group(1)) + 1}", line)

        hm = _HEADING_RE.match(line)
        if hm:
            heading_idx += 1
            if heading_idx % _CORRUPT_EVERY_NTH_LINE == 0:
                hashes = hm.group(1)
                if len(hashes) < 6:
                    line = "#" + line
        elif len(stripped) > 20 and not stripped.startswith("---"):
            prose_idx += 1
            if prose_idx % _CORRUPT_EVERY_NTH_LINE == 0:
                words = line.split()
                if len(words) > 3:
                    mid = len(words) // 2
                    words.pop(mid)
                    line = " ".join(words)

        result.append(line)
    return "\n".join(result)


def render_terminal(result: ReadbackResult) -> str:
    """Render readback results for terminal display."""
    lines: list[str] = []
    mode = "CORRUPT" if result.corrupted else "NORMAL"
    lines.append(f"{'=' * 60}")
    lines.append(
        f"READBACK: {result.pid} ({mode}, model={result.model}, "
        f"protocol={PROTOCOL_VERSION})"
    )
    if result.corrupted:
        banner_note = "applied" if result.banner_applied else "not applied (default)"
        lines.append(f"Priming banner: {banner_note}")
    lines.append(f"{'=' * 60}")

    for c in result.checks:
        if c.error:
            status, marker = "ERROR", "!"
        elif c.passed:
            status, marker = "PASS", "+"
        else:
            status, marker = "FAIL", "X"
        weak_note = " (weak: no groundable quote)" if c.passed and c.weak else ""
        lines.append(f"  [{marker}] {status} {c.fact_id} ({c.fact_type}){weak_note}")
        lines.append(f"      Q: {c.question[:120]}")
        lines.append(f"      Expected: {c.expected[:80]}")
        answer_preview = c.pod_answer[:120].replace("\n", " ")
        lines.append(f"      Answer:   {answer_preview}")
        lines.append(f"      Latency:  {c.latency_ms}ms")
        lines.append("")

    lines.append(f"{'- ' * 30}")
    lines.append(
        f"  Total: {len(result.checks)} | "
        f"Pass: {result.pass_count} | "
        f"Fail: {result.fail_count} | "
        f"Error: {result.error_count}"
    )
    lines.append(f"{'=' * 60}")
    return "\n".join(lines)


def render_markdown(result: ReadbackResult) -> str:
    """Render readback results as a markdown report for blessing."""
    lines: list[str] = []
    mode = "CORRUPT" if result.corrupted else "NORMAL"
    lines.append(f"# Readback Report: {result.pid}")
    lines.append("")
    lines.append(f"- **Mode**: {mode}")
    lines.append(f"- **Protocol**: {PROTOCOL_VERSION}")
    lines.append(f"- **Model**: {result.model}")
    if result.corrupted:
        banner_note = "applied" if result.banner_applied else "not applied (default)"
        lines.append(f"- **Priming banner**: {banner_note}")
    lines.append(
        f"- **Result**: {result.pass_count}/{len(result.checks)} passed"
        + (f", {result.error_count} transport error(s)" if result.error_count else "")
    )
    lines.append("")

    for c in result.checks:
        if c.error:
            status = "**ERROR** (transport, rerun)"
        elif c.passed:
            status = "PASS (weak: no groundable quote)" if c.weak else "PASS"
        else:
            status = "**FAIL**"
        lines.append(f"## {c.fact_id} ({c.fact_type}) - {status}")
        lines.append("")
        lines.append(f"**Question**: {c.question}")
        lines.append("")
        lines.append(f"**Expected**: `{c.expected}`")
        lines.append("")
        lines.append("**Pod answer**:")
        lines.append(f"> {c.pod_answer}")
        lines.append("")
        lines.append(f"*Latency: {c.latency_ms}ms*")
        lines.append("")

    return "\n".join(lines)
