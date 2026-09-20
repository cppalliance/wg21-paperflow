#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Oversize-paper handling for the tapetum_llm advisory lane.

The whole ``paper.md`` is normally injected into one LLM request. Papers above
the per-request budget (see ``MAX_PAPER_MD_CHARS``) 413 at the pod's nginx body
cap. Following the convergent pattern from the research repos (marker section
chunking, docling's heading-aware HybridChunker, MinerU page windows): split on
the natural boundary, process each unit, then aggregate. We split WG21 bodies on
H2 headings (the tomd body contract) and fold the per-chunk adjudications with
the same severity-aware worst-axis rule the decide step uses.

Pure functions, no LLM and no I/O: unit-testable at zero cost.
"""

from __future__ import annotations

import re

from whisker.det.llm_readability.models import (
    STATUS_FAIL,
    STATUS_NOT_EVALUATED,
    STATUS_PASS,
    CheckOutcome,
    Finding,
)
from whisker.det.score import VERDICT_FAIL, VERDICT_PASS, VERDICT_REVIEW
from whisker.llm.constants import (
    BASE64_LINE_ALPHABET_FLOOR,
    BASE64_LINE_MIN_CHARS,
    SEVERITY_MAJOR,
)
from whisker.llm.models import Adjudication, AxisFinding

__all__ = [
    "aggregate_adjudications",
    "chunk_markdown",
    "make_table_atomic_check",
    "strip_binary_payloads",
    "worst_axis_verdict",
]


# -- Binary-payload stripping (pre-LLM) -----------------------------------------

# `![alt](data:mime;base64,payload)`. The payload alphabet contains no `)`, so
# `[^)]` is safe and linear even on megabyte payloads.
_DATA_URI_IMAGE_RE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\(\s*data:(?P<mime>[^;,)]*)(?P<rest>[^)]*)\)"
)

_BASE64_ALPHABET = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
)


def strip_binary_payloads(md: str) -> tuple[str, int]:
    """Replace inline binary payloads with sanctioned markers, pre-LLM.

    Two deterministic filters (the ecosystem-consensus pattern, see
    research/research/base64-blob-filter/SYNTHESIS.md; firecrawl strips data-URI images
    by default, markitdown truncates every data URI):

    1. ``![alt](data:...)`` image references: the payload is replaced by
       ``<!-- tapetum:data-uri-stripped MIME ~SIZE -->``; the alt text (prose,
       judgeable) is kept.
    2. Bare lines of at least ``BASE64_LINE_MIN_CHARS`` whose chars are
       >= ``BASE64_LINE_ALPHABET_FLOOR`` base64-alphabet (whitespace counts
       against the ratio): wrapper-less binary debris no library handles;
       replaced whole.

    Returns ``(filtered_md, stripped_count)``. Pure; the caller decides what to
    do with the count. The on-disk paper.md is never touched.
    """
    count = 0

    def _replace_image(m: re.Match) -> str:
        nonlocal count
        count += 1
        mime = m.group("mime") or "unknown"
        size_kb = (len(m.group("rest")) + 1023) // 1024
        return (
            f"![{m.group('alt')}]"
            f"(<!-- tapetum:data-uri-stripped {mime} ~{size_kb}kB -->)"
        )

    md = _DATA_URI_IMAGE_RE.sub(_replace_image, md)

    lines = md.splitlines(keepends=True)
    for i, line in enumerate(lines):
        body = line.rstrip("\r\n")
        if len(body) < BASE64_LINE_MIN_CHARS:
            continue
        # Whitespace counts AGAINST the ratio: tomd emits whole paragraphs as
        # single unwrapped lines, and their ~15-20% spaces are what separates
        # prose from a base64 run (which contains none).
        hits = sum(1 for c in body if c in _BASE64_ALPHABET)
        if hits / len(body) >= BASE64_LINE_ALPHABET_FLOOR:
            count += 1
            size_kb = (len(body) + 1023) // 1024
            eol = line[len(body):]
            lines[i] = f"<!-- tapetum:base64-line-stripped ~{size_kb}kB -->{eol}"
    if count:
        md = "".join(lines)

    return md, count


def worst_axis_verdict(findings: list[AxisFinding]) -> str:
    """Severity-aware worst-axis fold.

    The overall verdict tracks the worst axis, but a ``fail`` label only becomes
    a hard overall fail when its severity is ``major`` (unrecoverable). A
    non-major fail is the model's recoverable/cosmetic call (e.g. a heading-level
    jump) and folds to ``review``. This is what rescues the false-fail RESCUE
    population instead of escalating a cosmetic defect to ``fail``.
    """
    worst = VERDICT_PASS
    for af in findings:
        if af.verdict == VERDICT_FAIL:
            if af.severity == SEVERITY_MAJOR:
                return VERDICT_FAIL
            worst = VERDICT_REVIEW
        elif af.verdict == VERDICT_REVIEW:
            worst = VERDICT_REVIEW
    return worst


# -- Chunking ------------------------------------------------------------------


def chunk_markdown(md: str, max_chars: int) -> tuple[list[str], bool]:
    """Split markdown into ``<= max_chars`` chunks on H2 boundaries.

    WG21 paper bodies start at H2 (``## ``) per the tomd contract, so H2 headings
    are the natural section boundary. Sections are packed greedily into chunks
    that stay under ``max_chars`` (marker's section packing). A single section
    larger than ``max_chars`` is hard-split on line boundaries as a last resort;
    that section was broken mid-content, so the read is partial.

    Returns ``(chunks, partial)``. The concatenation of ``chunks`` reproduces
    ``md`` exactly (lossless). For ``md`` that already fits, returns
    ``([md], False)`` so the common path is unchanged.
    """
    if len(md) <= max_chars:
        return [md], False

    partial = False
    pieces: list[str] = []
    for section in _split_sections(md):
        if len(section) > max_chars:
            split_pieces, _oversized_atomic = _hard_split(section, max_chars)
            pieces.extend(split_pieces)
            partial = True
        else:
            pieces.append(section)

    chunks: list[str] = []
    buf = ""
    for piece in pieces:
        if buf and len(buf) + len(piece) > max_chars:
            chunks.append(buf)
            buf = piece
        else:
            buf += piece
    if buf:
        chunks.append(buf)
    return chunks, partial


def _split_sections(md: str) -> list[str]:
    """Split into contiguous sections at H2 headings, fence-aware.

    A ``## `` line inside a fenced code block is not a heading. The preamble
    (front matter, H1 title, anything before the first H2) is the first section.
    """
    sections: list[str] = []
    current: list[str] = []
    in_fence = False
    fence_marker = ""
    in_html_table = False
    for line in md.splitlines(keepends=True):
        stripped = line.lstrip()
        lower = stripped.lower()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            marker = stripped[:3]
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif stripped.startswith(fence_marker):
                in_fence = False
                fence_marker = ""
        if "<table" in lower:
            in_html_table = True
        closed_html = in_html_table and _HTML_TABLE_CLOSE_RE.search(line)
        if (not in_fence) and (not in_html_table) and line.startswith("## ") and current:
            sections.append("".join(current))
            current = [line]
        else:
            current.append(line)
        if closed_html:
            in_html_table = False
    if current:
        sections.append("".join(current))
    return sections


_PIPE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_HTML_TABLE_CLOSE_RE = re.compile(r"</table\s*>", re.IGNORECASE)


def _atomic_segments(text: str) -> list[str]:
    """Split ``text`` into fenced blocks, tables, and other line runs.

    Concatenating the result reproduces ``text``. Fence, pipe-table, and HTML
    table segments are each a single item.
    """
    lines = text.splitlines(keepends=True)
    segments: list[str] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            marker = stripped[:3]
            block = [lines[i]]
            i += 1
            while i < len(lines):
                block.append(lines[i])
                if lines[i].lstrip().startswith(marker):
                    i += 1
                    break
                i += 1
            segments.append("".join(block))
            continue
        lower = lines[i].lower()
        table_at = lower.find("<table")
        if table_at != -1:
            buf = [lines[i]]
            if _HTML_TABLE_CLOSE_RE.search(lines[i][table_at:]):
                i += 1
                segments.append("".join(buf))
                continue
            i += 1
            while i < len(lines):
                buf.append(lines[i])
                if _HTML_TABLE_CLOSE_RE.search(lines[i]):
                    i += 1
                    break
                i += 1
            segments.append("".join(buf))
            continue
        body = lines[i].rstrip("\r\n")
        nxt = lines[i + 1].rstrip("\r\n") if i + 1 < len(lines) else ""
        if "|" in body and "|" in nxt and _PIPE_SEP_RE.match(nxt):
            block = [lines[i], lines[i + 1]]
            i += 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                block.append(lines[i])
                i += 1
            segments.append("".join(block))
            continue
        segments.append(lines[i])
        i += 1
    return segments


def _is_atomic_block(segment: str) -> bool:
    stripped = segment.lstrip()
    if stripped.startswith("```") or stripped.startswith("~~~"):
        return True
    lower = stripped.lower()
    if "<table" in lower:
        return True
    lines = segment.splitlines()
    if (
        len(lines) >= 2
        and "|" in lines[0]
        and "|" in lines[1]
        and _PIPE_SEP_RE.match(lines[1])
    ):
        return True
    return False


def _hard_split(text: str, max_chars: int) -> tuple[list[str], bool]:
    """Split one oversized section without cutting atomic units.

    Fenced code, pipe tables, and HTML ``<table>...</table>`` blocks are
    atomic: they are never bisected. An atomic unit larger than ``max_chars``
    is emitted whole and the read is marked partial. Ordinary prose still
    splits on line bounds; a single oversize prose line is char-sliced so
    non-table overflow stays bounded.
    """
    pieces: list[str] = []
    buf = ""
    oversized_atomic = False
    for segment in _atomic_segments(text):
        if len(segment) > max_chars and _is_atomic_block(segment):
            if buf:
                pieces.append(buf)
                buf = ""
            pieces.append(segment)
            oversized_atomic = True
            continue
        if len(segment) > max_chars:
            if buf:
                pieces.append(buf)
                buf = ""
            for i in range(0, len(segment), max_chars):
                pieces.append(segment[i : i + max_chars])
            continue
        if buf and len(buf) + len(segment) > max_chars:
            pieces.append(buf)
            buf = segment
        else:
            buf += segment
    if buf:
        pieces.append(buf)
    return pieces, oversized_atomic


def make_table_atomic_check(chunks: list[str], *, max_chars: int):
    """Return the R12 check closed over a completed chunking run."""

    def check(ctx) -> CheckOutcome:
        original = "".join(chunks)
        table_segments = [
            segment
            for segment in _atomic_segments(original)
            if _is_table_segment(segment)
        ]
        findings: list[Finding] = []
        unevaluated: list[str] = []
        evaluated_any = False
        for index, segment in enumerate(table_segments):
            evaluated_any = True
            holders = [chunk for chunk in chunks if segment in chunk]
            if not holders:
                findings.append(
                    Finding(
                        rule_id=ctx.rule.id,
                        locus=f"table block {index + 1}",
                        message="chunk boundary fell inside a table",
                        evidence=segment.splitlines()[0][:80] if segment else "",
                    )
                )
                continue
            if len(segment) > max_chars:
                unevaluated.append("oversized_atomic_table")
        if findings:
            return CheckOutcome(
                status=STATUS_FAIL,
                findings=tuple(findings),
            )
        if unevaluated:
            return CheckOutcome(
                status=STATUS_NOT_EVALUATED,
                reason=unevaluated[0],
            )
        if not evaluated_any:
            return CheckOutcome(status=STATUS_PASS)
        return CheckOutcome(status=STATUS_PASS)

    return check


def _is_table_segment(segment: str) -> bool:
    lower = segment.lstrip().lower()
    if "<table" in lower:
        return True
    lines = segment.splitlines()
    return (
        len(lines) >= 2
        and "|" in lines[0]
        and "|" in lines[1]
        and _PIPE_SEP_RE.match(lines[1]) is not None
    )


# -- Aggregation ---------------------------------------------------------------


def aggregate_adjudications(parts: list[Adjudication], chunk_count: int) -> Adjudication:
    """Fold per-chunk adjudications into one (worst-axis, min confidence, union).

    - ``axis_findings``: the most severe finding per axis across chunks, sorted
      by axis name (deterministic).
    - ``verdict``: severity-aware worst over the folded findings (advisory; the
      decide step re-derives it the same way).
    - ``confidence``: the minimum across chunks (most conservative).
    - ``evidence_spans``: the union (dedup on axis/quote/reason, order-preserving);
      decide grounds them against the full paper markdown.
    - ``reasoning``/``primary_concern``/``worst_axis``: taken from the worst
      chunk, with a note that the paper was chunked.
    """
    if not parts:
        return Adjudication(
            reasoning="no chunks produced",
            axis_findings=[],
            worst_axis="structure",
            verdict=VERDICT_REVIEW,
            confidence=0.0,
            evidence_spans=[],
            primary_concern="paper produced no readable chunks",
        )

    best: dict[str, AxisFinding] = {}
    for adj in parts:
        for af in adj.axis_findings:
            current = best.get(af.axis)
            if current is None or _finding_rank(af) > _finding_rank(current):
                best[af.axis] = af
    axis_findings = [best[axis] for axis in sorted(best)]

    verdict = worst_axis_verdict(axis_findings) if axis_findings else _worst_part_verdict(parts)
    confidence = min(a.confidence for a in parts)
    worst_part = max(parts, key=_part_rank)

    if axis_findings:
        top_rank = max(_finding_rank(af) for af in axis_findings)
        worst_axis = sorted(af.axis for af in axis_findings if _finding_rank(af) == top_rank)[0]
    else:
        worst_axis = worst_part.worst_axis

    seen: set[tuple[str, str, str]] = set()
    spans = []
    for adj in parts:
        for sp in adj.evidence_spans:
            key = (sp.axis, sp.quote, sp.reason)
            if key not in seen:
                seen.add(key)
                spans.append(sp)

    note = f"(paper chunked into {chunk_count} parts for size)"
    primary_concern = (
        f"{worst_part.primary_concern} {note}".strip()
        if worst_part.primary_concern
        else note
    )

    return Adjudication(
        reasoning=f"[aggregated over {chunk_count} chunks] {worst_part.reasoning}".strip(),
        axis_findings=axis_findings,
        worst_axis=worst_axis,
        verdict=verdict,
        confidence=confidence,
        evidence_spans=spans,
        primary_concern=primary_concern,
    )


def _finding_rank(af: AxisFinding) -> int:
    if af.verdict == VERDICT_FAIL and af.severity == SEVERITY_MAJOR:
        return 3
    if af.verdict == VERDICT_FAIL:
        return 2
    if af.verdict == VERDICT_REVIEW:
        return 1
    return 0


def _part_rank(a: Adjudication) -> int:
    if a.axis_findings:
        return max(_finding_rank(af) for af in a.axis_findings)
    return {VERDICT_FAIL: 2, VERDICT_REVIEW: 1, VERDICT_PASS: 0}.get(a.verdict, 0)


def _part_effective_verdict(a: Adjudication) -> str:
    """Per-part verdict with severity fold when axis findings are present."""
    if a.axis_findings:
        return worst_axis_verdict(a.axis_findings)
    return a.verdict


def _worst_part_verdict(parts: list[Adjudication]) -> str:
    """Worst part verdict when aggregated axis_findings is empty.

    Applies the same major-severity fold as ``worst_axis_verdict`` on each
    part's own findings so a cosmetic structure fail in one chunk cannot
    bypass the fold via the empty-findings aggregation path.
    """
    worst = VERDICT_PASS
    for a in parts:
        v = _part_effective_verdict(a)
        if v == VERDICT_FAIL:
            return VERDICT_FAIL
        if v == VERDICT_REVIEW:
            worst = VERDICT_REVIEW
    return worst
