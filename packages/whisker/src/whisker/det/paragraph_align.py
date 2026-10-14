#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Source-vs-candidate paragraph-boundary comparison (deterministic, no LLM).

Every other source-aware signal in whisker is token-based: coverage, drift,
punct recall, content recall. A paragraph boundary that the candidate drops
moves no token, so all of them stay green while the document structure is
wrong. This module closes that blind spot by comparing where the SOURCE starts
paragraphs against where the CANDIDATE does.

Two conventions carry the signal in WG21 PDFs and a document uses one or the
other, never both:

- **first-line indent**: the opening line of each paragraph sits a few points
  right of the body margin (classic LaTeX ``\\parindent``).
- **paragraph skip**: paragraphs are flush left and separated by extra vertical
  leading (``parskip``, Bikeshed/Pandoc output).

Detecting which one applies is the hard part, and two naive detectors were
measured and rejected before the ones below:

1. *Most frequent secondary x0 cluster.* On P0957R8 that picks the wording-block
   indent at x0=75.0 (123 lines) over the real paragraph indent at x0=62.5
   (109 lines). Frequency is the wrong ranking. A first-line indent is
   ISOLATED: the indented line is followed by a line back at the margin, while
   a block indent sustains. Measured isolation on that paper: 0.67 for the real
   indent against 0.00 for every decoy.
2. *bbox top for vertical gaps.* A 7pt footnote superscript lifts the bbox of an
   otherwise ordinary line, inflating the gap to the NEXT line (measured on
   P3556R0: 15.57 against a 11.96 leading, over a 15.0 threshold) and inventing
   two paragraph breaks. Baselines are immune, so gaps are measured baseline to
   baseline.

Only the MERGED direction is reported: a source paragraph start that the
candidate swallowed mid-paragraph. The inverse (candidate splits where the
source continues) was measured at ~54% precision because figure captions,
note blocks and page-opening lines are legitimately indented or gapped, so it
is deliberately not emitted rather than shipped as noise.

When neither convention is detectable the result ABSTAINS. A check that cannot
tell must not guess: a wrong structural flag on a hand-built golden costs more
than a missed one.

Library returns data; the caller decides what to do with it. Advisory by
construction: this module has no notion of a verdict.
"""

from __future__ import annotations

import logging
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from whisker import constants as C
from whisker.det.pdf_geometry import (
    PdfLine,
    body_font_size,
    is_monospace_line,
    load_pdf_lines,
)

_log = logging.getLogger(__name__)

__all__ = [
    "ParagraphAlignment",
    "compare_paragraph_boundaries",
]

STATUS_CHECKED = "checked"
STATUS_ABSTAINED = "abstained"
STATUS_UNSUPPORTED = "unsupported"

CONVENTION_INDENT = "first-line-indent"
CONVENTION_SKIP = "paragraph-skip"

_WORD_RE = re.compile(r"[A-Za-z0-9_]+")
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_ORDERED_ITEM_RE = re.compile(r"^\s*\d+[.)]\s")
_FENCE_RE = re.compile(r"^\s*(?:`{3,}|~{3,})")
_NON_PROSE_PREFIXES = ("#", "|", ">", "-", "*", "+", "<", ":")


@dataclass(frozen=True)
class ParagraphAlignment:
    """Where the candidate's paragraph breaks disagree with the source's.

    ``merged`` holds one human-locatable quote per swallowed boundary, in
    document order: the words before the join, a pipe, the words after it.
    """

    status: str
    convention: str | None = None
    analysed: int = 0
    merged: tuple[str, ...] = ()
    detail: str = ""

    @property
    def merged_count(self) -> int:
        return len(self.merged)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "convention": self.convention,
            "analysed": self.analysed,
            "merged_count": self.merged_count,
            "merged": list(self.merged),
            "detail": self.detail,
        }


def _is_body(line: PdfLine, body_size: float) -> bool:
    """Prose at body size. Monospaced-only lines are code, not paragraphs."""
    if body_size not in line.sizes:
        return False
    return not is_monospace_line(line)


def _detect_indent(body: list[PdfLine]) -> tuple[float | None, float | None, str]:
    """Find the body margin and a first-line indent ranked by isolation."""
    if not body:
        return None, None, "no body lines"
    counts = Counter(round(line.x0, 1) for line in body)
    margin = counts.most_common(1)[0][0]

    followed_by_margin: Counter[float] = Counter()
    for current, following in zip(body, body[1:]):
        if current.page != following.page:
            continue
        if abs(round(following.x0, 1) - margin) <= C.PARA_ALIGN_X_TOLERANCE_PT:
            followed_by_margin[round(current.x0, 1)] += 1

    viable: list[tuple[float, int]] = []
    for x0, count in counts.items():
        offset = x0 - margin
        if not (C.PARA_INDENT_MIN_PT <= offset <= C.PARA_INDENT_MAX_PT):
            continue
        if count < C.PARA_INDENT_MIN_LINES:
            continue
        if followed_by_margin[x0] / count < C.PARA_INDENT_MIN_ISOLATION:
            continue
        viable.append((x0, count))
    if not viable:
        return margin, None, "no isolated indent cluster"
    # Sort before max so equal counts resolve identically on every run (D7).
    indent = max(sorted(viable), key=lambda pair: pair[1])[0]
    return margin, indent, ""


def _detect_skip(body: list[PdfLine]) -> tuple[float | None, str]:
    """Find the baseline gap above which a line opens a new paragraph."""
    gaps = [
        round(following.baseline - current.baseline, 1)
        for current, following in zip(body, body[1:])
        if current.page == following.page
        and 0 < following.baseline - current.baseline < C.PARA_SKIP_MAX_GAP_PT
    ]
    if len(gaps) < C.PARA_SKIP_MIN_GAPS:
        return None, f"only {len(gaps)} usable line gaps"
    leading = statistics.mode(gaps)
    threshold = leading * C.PARA_SKIP_RATIO
    wide = [gap for gap in gaps if gap > threshold]
    if len(wide) < C.PARA_SKIP_MIN_WIDE:
        return None, f"gap histogram not bimodal (leading {leading:.1f})"
    return threshold, ""


def _candidate_paragraphs(markdown: str) -> list[str]:
    """Prose paragraphs only: no front matter, headings, lists, tables, code."""
    lines = markdown.split("\n")
    if lines and lines[0].strip() == "---":
        try:
            lines = lines[lines.index("---", 1) + 1:]
        except ValueError:
            pass

    paragraphs: list[str] = []
    buffer: list[str] = []
    in_fence = False

    def flush() -> None:
        if buffer:
            paragraphs.append(" ".join(buffer))
            buffer.clear()

    for line in lines:
        if _FENCE_RE.match(line):
            flush()
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if stripped.startswith(_NON_PROSE_PREFIXES) or _ORDERED_ITEM_RE.match(line):
            flush()
            continue
        buffer.append(stripped)
    flush()
    return paragraphs


def _prose_words(text: str) -> list[str]:
    text = _IMAGE_RE.sub(" ", text)
    text = _LINK_RE.sub(r"\1", text)
    text = text.replace("`", " ").replace("*", " ").replace("_", " ")
    return [match.group(0).lower() for match in _WORD_RE.finditer(text)]


def _swallowed_boundaries(
    words: list[str],
    starts_paragraph: list[bool],
    paragraph: list[str],
    index: dict[str, list[int]],
    cursor: int,
) -> tuple[list[int], int]:
    """Walk one candidate paragraph through the source word stream.

    Returns the source positions where the SOURCE opens a paragraph while the
    candidate is still mid-paragraph, plus the new stream cursor. Small
    insertions and deletions are resynchronised within a bounded window; an
    unrecoverable divergence abandons the paragraph rather than guessing.
    """
    probe = min(len(paragraph), C.PARA_ALIGN_PROBE_WORDS)
    start: int | None = None
    for candidate in index.get(paragraph[0], ()):
        if candidate + probe > len(words):
            continue
        if words[candidate:candidate + probe] != paragraph[:probe]:
            continue
        if candidate >= cursor:
            start = candidate
            break
        if start is None:
            start = candidate
    if start is None:
        return [], cursor

    hits: list[int] = []
    position, word_index = start, 0
    while word_index < len(paragraph) and position < len(words):
        if words[position] == paragraph[word_index]:
            if word_index > 0 and starts_paragraph[position]:
                hits.append(position)
            position += 1
            word_index += 1
            continue
        for skew in range(1, C.PARA_ALIGN_MAX_SKEW + 1):
            if (position + skew < len(words)
                    and words[position + skew] == paragraph[word_index]):
                position += skew
                break
            if (word_index + skew < len(paragraph)
                    and words[position] == paragraph[word_index + skew]):
                word_index += skew
                break
        else:
            break
    return hits, max(cursor, position - C.PARA_ALIGN_MAX_SKEW)


def compare_paragraph_boundaries(
    source_path: Path,
    candidate_md: str,
) -> ParagraphAlignment:
    """Compare the candidate's paragraph breaks against the source PDF's.

    Never raises: an unreadable or unsupported source abstains, because this
    is an advisory signal and a crash here must not take a scoring run down.
    """
    if source_path.suffix.lower() != ".pdf":
        return ParagraphAlignment(
            status=STATUS_UNSUPPORTED,
            detail=f"{source_path.suffix or 'no'} source; PDF geometry only",
        )
    try:
        lines = load_pdf_lines(source_path)
    except Exception:
        _log.debug("paragraph alignment: cannot read %s", source_path, exc_info=True)
        return ParagraphAlignment(status=STATUS_ABSTAINED, detail="source unreadable")

    body_size = body_font_size(lines)
    body = [line for line in lines if _is_body(line, body_size)]

    margin, indent, indent_detail = _detect_indent(body)
    if indent is not None:
        convention = CONVENTION_INDENT
        starters = {
            id(line) for line in body
            if abs(line.x0 - indent) <= C.PARA_ALIGN_X_TOLERANCE_PT
            and not line.page_first
        }
    else:
        threshold, skip_detail = _detect_skip(body)
        if threshold is None:
            return ParagraphAlignment(
                status=STATUS_ABSTAINED,
                detail=f"no paragraph convention: {indent_detail}; {skip_detail}",
            )
        convention = CONVENTION_SKIP
        starters = {
            id(following) for current, following in zip(body, body[1:])
            if current.page == following.page
            and following.baseline - current.baseline > threshold
        }

    words: list[str] = []
    starts_paragraph: list[bool] = []
    for line in lines:
        opens = id(line) in starters
        for offset, match in enumerate(_WORD_RE.finditer(line.text)):
            words.append(match.group(0).lower())
            starts_paragraph.append(opens and offset == 0)

    index: dict[str, list[int]] = defaultdict(list)
    for position, word in enumerate(words):
        index[word].append(position)

    merged: list[str] = []
    analysed = 0
    cursor = 0
    for text in _candidate_paragraphs(candidate_md):
        paragraph = _prose_words(text)
        if len(paragraph) < C.PARA_ALIGN_MIN_WORDS:
            continue
        analysed += 1
        hits, cursor = _swallowed_boundaries(
            words, starts_paragraph, paragraph, index, cursor,
        )
        for hit in hits:
            before = words[max(0, hit - C.PARA_ALIGN_EVIDENCE_WORDS):hit]
            after = words[hit:hit + C.PARA_ALIGN_EVIDENCE_WORDS]
            merged.append(f"{' '.join(before)} | {' '.join(after)}")

    if margin is not None and indent is not None:
        detail = f"indent x0={indent:.1f} (margin {margin:.1f})"
    else:
        detail = "extra leading between paragraphs"
    return ParagraphAlignment(
        status=STATUS_CHECKED,
        convention=convention,
        analysed=analysed,
        merged=tuple(merged[:C.PARA_ALIGN_EVIDENCE_CAP]),
        detail=detail,
    )
