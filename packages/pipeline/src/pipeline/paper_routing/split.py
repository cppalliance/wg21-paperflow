#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Stage 1: sentence splitting for paper routing."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pipeline.markdown import front_matter_end_index
from pipeline.markdown_patterns import HEADING_RE

_FENCE_OPEN_RE = re.compile(r"^(`{3,}|~{3,})(\w*)")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")
_GRAMMAR_PRODUCTION_RE = re.compile(
    r"^[a-z][a-z0-9_-]*\s*:\s*.+",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RawSentence:
    """A split sentence with its starting line index (0-based)."""

    text: str
    start_line: int


def split_sentences(paper_md: str) -> list[RawSentence]:
    """Split paper markdown into routable sentence units.

    Fenced code blocks and grammar-production lines are each kept as a
    single unit. Inline code stays attached to prose sentences.
    """
    lines = paper_md.splitlines()
    units: list[RawSentence] = []
    i = front_matter_end_index(lines)

    while i < len(lines):
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        if HEADING_RE.match(line):
            units.append(RawSentence(text=line.strip(), start_line=i))
            i += 1
            continue

        fence = _FENCE_OPEN_RE.match(line.strip())
        if fence:
            fence_char = fence.group(1)[0]
            fence_len = len(fence.group(1))
            block_lines = [line]
            start = i
            i += 1
            while i < len(lines):
                block_lines.append(lines[i])
                stripped = lines[i].strip()
                if stripped.startswith(fence_char * fence_len) and len(stripped) >= fence_len:
                    tail = stripped[fence_len:].strip()
                    if not tail or not tail[0].isalnum():
                        break
                i += 1
            units.append(RawSentence(text="\n".join(block_lines), start_line=start))
            i += 1
            continue

        if _GRAMMAR_PRODUCTION_RE.match(line.strip()):
            units.append(RawSentence(text=line.strip(), start_line=i))
            i += 1
            continue

        prose_start = i
        prose_buf: list[str] = []
        while i < len(lines):
            cur = lines[i]
            if not cur.strip():
                i += 1
                break
            if HEADING_RE.match(cur):
                break
            if _FENCE_OPEN_RE.match(cur.strip()):
                break
            if _GRAMMAR_PRODUCTION_RE.match(cur.strip()):
                break
            prose_buf.append(cur)
            i += 1
        if prose_buf:
            for part in _split_prose("\n".join(prose_buf)):
                units.append(RawSentence(text=part, start_line=prose_start))

    return [u for u in units if u.text.strip()]


def _split_prose(text: str) -> list[str]:
    """Split prose on sentence boundaries."""
    parts = _SENTENCE_END_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]
