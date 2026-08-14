#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Stage 1: sentence splitting for paper routing."""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass
from typing import cast

from pysbd import Segmenter
from pysbd.utils import TextSpan

from assay.paper_routing.standardese import (
    STANDARDESE_LABEL_RE,
    is_standardese_line,
)
from pipeline.markdown import HEADING_RE, front_matter_end_index

_FENCE_OPEN_RE = re.compile(r"^(`{3,}|~{3,})(\w*)")
_BNF_PRODUCTION_RE = re.compile(r"^[a-z][a-z0-9_-]*\s*:\s*.+")
# Lowercase lhs tokens that look like BNF but are wording directives or prose.
_BNF_FALSE_POSITIVE_LHS = frozenset({"add", "modify", "insert", "strike", "delete"})
# A genuine BNF right-hand side is made of grammar tokens (nonterminal names,
# terminals, meta-symbols): no sentence-terminal punctuation and no
# capitalized prose words. Lines that fail this look like informal lowercase
# labels ("note:", "caveat:", "aside:") rather than grammar productions, and
# would otherwise be swallowed whole instead of sentence-split.
_BNF_RHS_PROSE_RE = re.compile(r"[.!?](?:\s|$)|[A-Z]")
_SEGMENTER = Segmenter(language="en", clean=False, char_span=True)


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
                if stripped.startswith(fence_char * fence_len):
                    tail = stripped[fence_len:].strip()
                    if not tail or not tail[0].isalnum():
                        break
                i += 1
            units.append(RawSentence(text="\n".join(block_lines), start_line=start))
            i += 1
            continue

        if _is_bnf_production_line(line):
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
            if _is_bnf_production_line(cur):
                break
            prose_buf.append(cur)
            i += 1
        if prose_buf:
            units.extend(_split_prose_units(prose_buf, prose_start))

    return [u for u in units if u.text.strip()]


def _is_bnf_production_line(line: str) -> bool:
    """Return True for lowercase BNF grammar productions, not Standardese labels."""
    stripped = line.strip()
    if is_standardese_line(stripped):
        return False
    match = _BNF_PRODUCTION_RE.match(stripped)
    if match is None:
        return False
    lhs, _, rhs = stripped.partition(":")
    if lhs.strip() in _BNF_FALSE_POSITIVE_LHS:
        return False
    if _BNF_RHS_PROSE_RE.search(rhs.strip()):
        return False
    return True


def _prose_line_offsets(prose_lines: list[str]) -> list[int]:
    """Character offset of each prose line within a newline-joined paragraph."""
    if not prose_lines:
        return [0]
    offsets = [0]
    for line in prose_lines[:-1]:
        offsets.append(offsets[-1] + len(line) + 1)
    return offsets


def _offset_to_prose_line(line_offsets: list[int], char_offset: int) -> int:
    """Map a paragraph character offset to a 0-based index within *prose_lines*."""
    idx = bisect.bisect_right(line_offsets, char_offset) - 1
    return max(0, idx)


_NORMATIVE_SPLIT_SUFFIX_RE = re.compile(
    r"(?:add:\s*$|modify:\s*$)",
    re.IGNORECASE,
)
_ATTACHED_LABEL_PREFIX_RE = re.compile(
    r"(?:"
    r"[-*]\s*$"  # markdown list marker
    r"|\(\w+\)\s*$"  # lettered (a), (b)
    r"|\d+(?:\.\d+)+\s*$"  # clause ref 1.2.3
    r"|\d+\.\s*$"  # numbered normative 1.
    r"|\b[A-Za-z]+\s*$"  # prose word before label (Release, with)
    r")",
    re.IGNORECASE,
)


def _should_split_at_standardese(prefix: str) -> bool:
    """Return True when an internal Standardese label should start a new unit."""
    if _ATTACHED_LABEL_PREFIX_RE.search(prefix):
        return False
    return _NORMATIVE_SPLIT_SUFFIX_RE.search(prefix) is not None


def _standardese_split_points(text: str) -> list[int]:
    """Local offsets where *text* should split before an internal Standardese label."""
    points: list[int] = []
    for match in STANDARDESE_LABEL_RE.finditer(text):
        if match.start() == 0:
            continue
        prefix = text[: match.start()]
        if not _should_split_at_standardese(prefix):
            continue
        points.append(match.start())
    return points


def _post_split_standardese(span: TextSpan) -> list[tuple[str, int]]:
    """Split a pySBD TextSpan on internal Standardese label boundaries."""
    text = span.sent
    base = span.start
    points = _standardese_split_points(text)
    if not points:
        return [(text, base)]

    parts: list[tuple[str, int]] = []
    prev = 0
    for point in points:
        chunk = text[prev:point]
        if chunk.strip():
            parts.append((chunk, base + prev))
        prev = point
    tail = text[prev:]
    if tail.strip():
        parts.append((tail, base + prev))
    return parts


def _split_prose_units(prose_lines: list[str], prose_start: int) -> list[RawSentence]:
    """Split prose lines into sentences with per-sentence source line attribution."""
    paragraph = "\n".join(prose_lines)
    line_offsets = _prose_line_offsets(prose_lines)
    units: list[RawSentence] = []

    for raw_span in _SEGMENTER.segment(paragraph):
        span = cast(TextSpan, raw_span)
        for part_text, abs_offset in _post_split_standardese(span):
            text = part_text.strip()
            if not text:
                continue
            local_line = _offset_to_prose_line(line_offsets, abs_offset)
            units.append(RawSentence(text=text, start_line=prose_start + local_line))

    return units
