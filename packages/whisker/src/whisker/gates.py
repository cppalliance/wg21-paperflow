#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Reference-free structural gates.

These need no ground truth and no source document: they assert that the
Markdown is structurally well-formed on its own terms. A failing hard gate
forces a FAIL verdict regardless of coverage, because the artifact is broken
in a way no amount of content fidelity can excuse (truncated file, malformed
front matter, empty code fence, headless table).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from whisker.tables import split_pipe_cells

__all__ = ["GateResult", "iter_body_lines", "run_gates", "split_front_matter"]

# WG21 straw-poll ballot. A header-only / blank-body grid with these cells
# in this order is a filled-in form, not a missing table (#424, P3978R0).
_POLL_HEADER_CELLS = ("SF", "F", "N", "A", "SA")


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    detail: str = ""


_FENCE_RE = re.compile(r"^(\s*)(```|~~~)(.*)$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+\S")
_REQUIRED_FRONT_MATTER_KEYS = ("title", "document")


def split_front_matter(md_text: str) -> tuple[list[str] | None, str]:
    """Return (front-matter lines, body). Front matter is None if absent.

    A valid block is a leading ``---`` line and the next ``---`` terminator.
    """
    lines = md_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, md_text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], "\n".join(lines[i + 1 :])
    return None, md_text


def _gate_non_empty(body: str) -> GateResult:
    stripped = body.strip()
    return GateResult(
        "non_empty",
        bool(stripped),
        "" if stripped else "body has no non-whitespace content",
    )


def _gate_front_matter(fm_lines: list[str] | None) -> GateResult:
    if fm_lines is None:
        return GateResult("front_matter_valid", False, "missing or unterminated front matter")
    keys = set()
    for line in fm_lines:
        if not line.strip() or line.startswith((" ", "\t", "-")):
            continue
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:", line)
        if m:
            keys.add(m.group(1).lower())
    missing = [k for k in _REQUIRED_FRONT_MATTER_KEYS if k not in keys]
    return GateResult(
        "front_matter_valid",
        not missing,
        "" if not missing else f"missing keys: {', '.join(missing)}",
    )


def iter_body_lines(body: str):
    """Yield (line, in_fence) skipping nothing; tracks fenced-code state."""
    in_fence = False
    fence_marker = ""
    for line in body.splitlines():
        m = _FENCE_RE.match(line)
        if m and (not in_fence or m.group(2) == fence_marker):
            if in_fence:
                in_fence = False
                fence_marker = ""
            else:
                in_fence = True
                fence_marker = m.group(2)
            yield line, "fence_toggle"
            continue
        yield line, "fence_body" if in_fence else "text"


def _gate_heading_monotone(body: str) -> GateResult:
    prev = 0
    for line, kind in iter_body_lines(body):
        if kind != "text":
            continue
        m = _HEADING_RE.match(line)
        if not m:
            continue
        level = len(m.group(1))
        if prev and level > prev + 1:
            return GateResult(
                "heading_monotone",
                False,
                f"heading level jumps H{prev} -> H{level}",
            )
        prev = level
    return GateResult("heading_monotone", True)


def _gate_no_empty_code(body: str) -> GateResult:
    pending_open = False
    saw_content = False
    for line, kind in iter_body_lines(body):
        if kind == "fence_toggle":
            if not pending_open:
                pending_open = True
                saw_content = False
            else:
                if not saw_content:
                    return GateResult("no_empty_code", False, "empty fenced code block")
                pending_open = False
        elif pending_open and line.strip():
            saw_content = True
    return GateResult("no_empty_code", True)


_TOC_LABEL_RE = re.compile(
    r"^(?:#{1,6}\s+)?(?:table\s+of\s+contents|contents)\s*:?\s*$", re.IGNORECASE
)
_HEADING_TEXT_RE = re.compile(r"^#{1,6}\s+(\S.*)$")
_PAGE_SUFFIX_RE = re.compile(r"^(?P<stem>.*\S)\s+(?P<page>\d{1,4})$")


def _normalize_heading_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _gate_no_toc_leak(body: str) -> GateResult:
    """Detect table-of-contents content that leaked into the body.

    tomd's contract strips the TOC; body headings replace it. Two leak
    signatures survive that strip failing (PRs #290/#293, golden-qa-gap):

    a) A standalone "Contents" / "Table of Contents" line (plain or heading).
    b) A page-numbered duplicate: one heading is another heading's text plus
       a trailing bare number (the TOC page number), e.g. "## 1. Introduction 3"
       alongside "## 1. Introduction". Matching is pairwise so unrelated
       numbered headings ("## Step 1" / "## Step 2") never collide.
    """
    suffixed_stems: dict[str, str] = {}
    seen_plain: set[str] = set()
    for line, kind in iter_body_lines(body):
        if kind != "text":
            continue
        stripped = line.strip()
        if _TOC_LABEL_RE.match(stripped):
            return GateResult("no_toc_leak", False, f"TOC label in body: {stripped!r}")
        m = _HEADING_TEXT_RE.match(stripped)
        if not m:
            continue
        text = _normalize_heading_text(m.group(1))
        pm = _PAGE_SUFFIX_RE.match(text)
        if pm:
            stem = pm.group("stem")
            suffixed_stems.setdefault(stem, text)
            if stem in seen_plain:
                return GateResult(
                    "no_toc_leak",
                    False,
                    f"page-numbered duplicate heading {text!r} after {stem!r} (TOC leak)",
                )
        if text in suffixed_stems and suffixed_stems[text] != text:
            return GateResult(
                "no_toc_leak",
                False,
                f"duplicate heading {text!r} previously seen as "
                f"{suffixed_stems[text]!r} (TOC leak)",
            )
        seen_plain.add(text)
    return GateResult("no_toc_leak", True)


_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def _gate_no_empty_table(body: str) -> GateResult:
    lines = [ln for ln, kind in iter_body_lines(body) if kind == "text"]
    for i, line in enumerate(lines):
        # A GFM table separator must contain a pipe and sit directly under a
        # header row that also has a pipe. Without the pipe checks a bare "---"
        # (thematic break / horizontal rule) or a setext underline matches and
        # produces a false empty-table failure.
        if "|" not in line or not _TABLE_SEP_RE.match(line):
            continue
        header = lines[i - 1] if i > 0 else ""
        if "|" not in header:
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if "|" not in nxt:
            return GateResult("no_empty_table", False, "table separator with no data row")
        if not nxt.replace("|", "").strip():
            if tuple(split_pipe_cells(header)) == _POLL_HEADER_CELLS:
                continue
            return GateResult("no_empty_table", False, "table separator with no data row")
    return GateResult("no_empty_table", True)


def run_gates(md_text: str) -> list[GateResult]:
    """Run every tier-0 structural gate. All gates are hard (FAIL on failure)."""
    fm_lines, body = split_front_matter(md_text)
    return [
        _gate_non_empty(body),
        _gate_front_matter(fm_lines),
        _gate_heading_monotone(body),
        _gate_no_empty_code(body),
        _gate_no_empty_table(body),
        _gate_no_toc_leak(body),
    ]
