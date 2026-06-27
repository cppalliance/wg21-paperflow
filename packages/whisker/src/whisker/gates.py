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

__all__ = ["GateResult", "run_gates"]


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    detail: str = ""


_FENCE_RE = re.compile(r"^(\s*)(```|~~~)(.*)$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+\S")
_REQUIRED_FRONT_MATTER_KEYS = ("title", "document")


def _split_front_matter(md_text: str) -> tuple[list[str] | None, str]:
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


def _iter_body_lines(body: str):
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
    for line, kind in _iter_body_lines(body):
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
    for line, kind in _iter_body_lines(body):
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


_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def _gate_no_empty_table(body: str) -> GateResult:
    lines = [ln for ln, kind in _iter_body_lines(body) if kind == "text"]
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
        if "|" not in nxt or not nxt.replace("|", "").strip():
            return GateResult("no_empty_table", False, "table separator with no data row")
    return GateResult("no_empty_table", True)


def run_gates(md_text: str) -> list[GateResult]:
    """Run every tier-0 structural gate. All gates are hard (FAIL on failure)."""
    fm_lines, body = _split_front_matter(md_text)
    return [
        _gate_non_empty(body),
        _gate_front_matter(fm_lines),
        _gate_heading_monotone(body),
        _gate_no_empty_code(body),
        _gate_no_empty_table(body),
    ]
