"""Generation QA: a lightweight content report over a finished thread.

The emit step runs this after generation and before the artifact
write. Every check is a *report*, never a gate: findings are logged
and recorded in the trace so obvious content-rule violations surface
before the website's reveal-time moderation window, but a finding does
not fail the run — the hard invariants live in
:func:`agora.artifact.validate_artifact`.

The rules mirror the content boundaries the-mod.md draws:

- **unknown-handle** — a ``u/`` mention outside the roster. Selection
  guarantees every *author* is a roster persona; this catches bodies
  that *mention* invented or real Redditors (the "no real people"
  rule).
- **personal-attack** — ad-hominem vocabulary. Comments attack
  claims, never people.
- **typo-nitpick** — editorial nitpicks from the the-mod.md 1.3b
  exclusion list ("nobody says 'you misspelled ``noexcept``'").
  Comments containing a fenced code block are exempt: a small typo
  someone corrects in a code reply is sanctioned by section 10.
- **fourth-wall** — generation machinery leaking into a comment
  body (briefs, personas, slots, model self-reference).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from agora.models import Thread
from agora.roster import roster_usernames

SUBMISSION_TARGET = "submission"
"""Target label for findings against the submission body."""

_HANDLE_RE = re.compile(r"\bu/([A-Za-z0-9_-]{3,})")

_PERSONAL_ATTACK_RE = re.compile(
    r"\b(idiot(?:s|ic)?|moron(?:s|ic)?|imbecile(?:s)?|dumbass(?:es)?"
    r"|charlatan(?:s)?|clueless (?:author|committee|op))\b",
    re.IGNORECASE,
)

_TYPO_NITPICK_RE = re.compile(
    r"\b(typos?|misspell\w*|spelling (?:error|mistake)s?"
    r"|missing semicolons?)\b",
    re.IGNORECASE,
)

_FOURTH_WALL_RE = re.compile(
    r"\b(as an ai|as a language model|language model|system prompt"
    r"|my persona|my brief|the brief says|per the brief|my assigned"
    r"|slot s\d+|fourth wall)\b",
    re.IGNORECASE,
)

_CODE_FENCE = "```"


@dataclass(frozen=True)
class QaFinding:
    """One content-rule flag on one target."""

    target: str
    """``slot_id`` of the flagged comment, or ``"submission"``."""

    rule: str
    """Short rule key: ``unknown-handle``, ``personal-attack``,
    ``typo-nitpick``, or ``fourth-wall``."""

    detail: str
    """What matched, quoted for the human reading the report."""

    def __str__(self) -> str:
        return f"{self.target} [{self.rule}]: {self.detail}"


def qa_report(thread: Thread) -> list[QaFinding]:
    """Scan every written body for content-rule violations.

    Deterministic: findings come out in thread order (submission
    first, then replies in blueprint order), each body's rules in a
    fixed sequence. Deleted slots are skipped — ``[deleted]`` is a
    placeholder, not content.
    """
    findings: list[QaFinding] = []
    findings.extend(
        _scan_body(SUBMISSION_TARGET, thread.submission_body)
    )
    for reply in thread.replies:
        if reply.deleted or reply.role == "deleted":
            continue
        findings.extend(_scan_body(reply.slot_id, reply.content or ""))
    return findings


def _scan_body(target: str, body: str) -> list[QaFinding]:
    findings: list[QaFinding] = []
    known = roster_usernames()

    for match in _HANDLE_RE.finditer(body):
        handle = match.group(1)
        if handle not in known:
            findings.append(QaFinding(
                target, "unknown-handle",
                f"mentions u/{handle}, which is not a roster persona",
            ))

    attack = _PERSONAL_ATTACK_RE.search(body)
    if attack:
        findings.append(QaFinding(
            target, "personal-attack",
            f"ad-hominem phrasing: {attack.group(0)!r}",
        ))

    # Code replies may legitimately correct a typo in code (the-mod.md
    # section 10); prose-only editorial nitpicks are the 1.3b exclusion.
    if _CODE_FENCE not in body:
        nitpick = _TYPO_NITPICK_RE.search(body)
        if nitpick:
            findings.append(QaFinding(
                target, "typo-nitpick",
                f"editorial nitpick: {nitpick.group(0)!r}",
            ))

    wall = _FOURTH_WALL_RE.search(body)
    if wall:
        findings.append(QaFinding(
            target, "fourth-wall",
            f"generation machinery leaked: {wall.group(0)!r}",
        ))

    return findings
