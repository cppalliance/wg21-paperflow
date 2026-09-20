#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Lane-local source-unit risk routing for advisory LLM review.

The router compares source packets directly with candidate Markdown. It never
reads deterministic whisker artifacts and never emits a conversion verdict.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from whisker.llm import constants
from whisker.llm.html_outline import SectionUnit, normalize_heading_text
from whisker.llm.textlayer import _CPP_KEYWORDS, PageUnit
from whisker.metrics import content_recall, content_tokens, normalized_text

__all__ = [
    "RiskSignal",
    "normalize_heading_text",
    "route_html_units",
    "route_pdf_units",
]

_WORD_RE = re.compile(r"\b\w+\b", re.UNICODE)
_ATX_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
_SETEXT_RE = re.compile(r"^[ \t]*(=+|-+)[ \t]*$")
_FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
_HTML_PRE_BLOCK_RE = re.compile(r"<pre\b", re.IGNORECASE)
_SANCTIONED_TOC_TITLE_KEYS = frozenset({"contents", "tableofcontents"})


@dataclass
class RiskSignal:
    """A lane-local source-vs-candidate discrepancy for one unit."""

    unit_id: str
    signal_type: str
    severity: str
    detail: str


@dataclass
class _MarkdownSection:
    level: int
    title: str
    text: str
    code_blocks: int


def _text_key(text: str) -> str:
    return normalized_text(text).casefold()


def _strip_front_matter(lines: list[str]) -> list[str]:
    if not lines or lines[0].strip() != "---":
        return lines
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return lines[index + 1:]
    return lines


def _parse_markdown_sections(markdown: str) -> list[_MarkdownSection]:
    """Parse top-level ATX/setext sections and fenced code-block counts."""
    lines = _strip_front_matter(markdown.splitlines())
    sections: list[_MarkdownSection] = []
    current_level: int | None = None
    current_title = ""
    current_body: list[str] = []
    current_code_blocks = 0
    current_html_code_blocks = 0
    fence_marker: str | None = None

    def finish() -> None:
        nonlocal current_level, current_title, current_body
        nonlocal current_code_blocks, current_html_code_blocks
        if current_level is None:
            return
        body = "\n".join(current_body).strip()
        sections.append(_MarkdownSection(
            level=current_level,
            title=current_title,
            text=body,
            code_blocks=current_code_blocks + current_html_code_blocks,
        ))
        current_level = None
        current_title = ""
        current_body = []
        current_code_blocks = 0
        current_html_code_blocks = 0

    index = 0
    while index < len(lines):
        line = lines[index]
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if fence_marker is None:
                fence_marker = marker
                if current_level is not None:
                    current_code_blocks += 1
            elif marker[0] == fence_marker[0] and len(marker) >= len(fence_marker):
                fence_marker = None
            if current_level is not None:
                current_body.append(line)
            index += 1
            continue

        if fence_marker is None:
            atx_match = _ATX_HEADING_RE.match(line)
            if atx_match:
                finish()
                current_level = len(atx_match.group(1))
                current_title = atx_match.group(2).strip()
                index += 1
                continue
            if (
                line.strip()
                and index + 1 < len(lines)
                and (setext_match := _SETEXT_RE.match(lines[index + 1]))
            ):
                finish()
                current_level = 1 if setext_match.group(1).startswith("=") else 2
                current_title = line.strip()
                index += 2
                continue
            if current_level is not None:
                current_html_code_blocks += len(_HTML_PRE_BLOCK_RE.findall(line))

        if current_level is not None:
            current_body.append(line)
        index += 1

    finish()
    return sections


def _is_sanctioned_toc_title(title: str) -> bool:
    return _text_key(title) in _SANCTIONED_TOC_TITLE_KEYS


def _fenced_code_text(markdown: str) -> str:
    """Concatenate fenced code-block bodies from candidate markdown.

    Reuses this module's ``_FENCE_RE`` (same fence grammar as section
    parsing). ``unit_judge._FENCE_RE`` is a sibling regex; importing it
    here would cycle because ``unit_judge`` imports ``source_router``.
    """
    bodies: list[str] = []
    current: list[str] = []
    fence_marker: str | None = None
    for line in markdown.splitlines():
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if fence_marker is None:
                fence_marker = marker
                current = []
                continue
            if (
                marker[0] == fence_marker[0]
                and len(marker) >= len(fence_marker)
            ):
                bodies.append("\n".join(current))
                fence_marker = None
                current = []
                continue
        if fence_marker is not None:
            current.append(line)
    if fence_marker is not None:
        bodies.append("\n".join(current))
    return "\n".join(bodies)


def _normalized_word_stream(text: str) -> str:
    return " ".join(word.lower() for word in _WORD_RE.findall(text))


def _page_keyword_line_coverage(
    page_text: str, fenced_text: str,
) -> tuple[int, int]:
    """Return ``(covered_hits, countable_hits)`` using page-local line snippets.

    A keyword hit counts only when its source line has enough tokens to be
    distinctive. Coverage requires that same token sequence inside a fence,
    not merely that the keyword type appears somewhere in the document.
    """
    fenced_norm = _normalized_word_stream(fenced_text)
    min_tokens = constants.PDF_MISSING_CODE_SNIPPET_MIN_TOKENS
    covered = 0
    countable = 0
    for raw_line in page_text.splitlines() or [page_text]:
        words = [word.lower() for word in _WORD_RE.findall(raw_line)]
        hits = sum(1 for word in words if word in _CPP_KEYWORDS)
        if hits == 0 or len(words) < min_tokens:
            continue
        countable += hits
        snippet = " ".join(words)
        if snippet and snippet in fenced_norm:
            covered += hits
    return covered, countable


def _missing_code_signal(
    unit: PageUnit, fenced_text: str,
) -> RiskSignal | None:
    """Return a PDF ``missing_code`` signal when fences under-cover the page."""
    if unit.code_token_count < constants.PDF_MISSING_CODE_TOKEN_THRESHOLD:
        return None
    covered, countable = _page_keyword_line_coverage(unit.text, fenced_text)
    if countable < constants.PDF_MISSING_CODE_TOKEN_THRESHOLD:
        return None
    required = (
        constants.PDF_MISSING_CODE_FENCE_COVER_RATIO * countable
    )
    if covered >= required:
        return None
    return RiskSignal(
        unit_id=f"page:{unit.page}",
        signal_type="missing_code",
        severity="high",
        detail=(
            f"page has {unit.code_token_count} code-token hits, "
            f"candidate fences cover {covered}"
        ),
    )


def route_pdf_units(
    page_units: list[PageUnit],
    candidate_md: str,
) -> list[RiskSignal]:
    """Identify PDF pages with source-vs-candidate discrepancies."""
    signals: list[RiskSignal] = []
    candidate_words = Counter(_WORD_RE.findall(candidate_md))
    candidate_surface = _text_key(candidate_md)
    # Secno stripping must happen BEFORE _text_key on both sides. _text_key
    # removes whitespace, so normalizing an already-keyed title is a no-op:
    # "1 History" keys to "1history", which _SECNO_RE (it needs the space)
    # can no longer match, while the source side keys to "history".
    candidate_heading_keys = {
        _text_key(normalize_heading_text(section.title))
        for section in _parse_markdown_sections(candidate_md)
    }
    source_document_words = Counter(
        word
        for unit in page_units
        for word in _WORD_RE.findall(unit.text)
    )
    for token in sorted(_CPP_KEYWORDS):
        deficit = source_document_words[token] - candidate_words[token]
        if deficit < constants.TOKEN_DELTA_THRESHOLD:
            continue
        representative = next(
            (
                unit
                for unit in page_units
                if token in {
                    word for word in _WORD_RE.findall(unit.text)
                }
            ),
            None,
        )
        if representative is not None:
            signals.append(RiskSignal(
                unit_id=f"page:{representative.page}",
                signal_type="token_delta",
                severity="medium",
                detail=(
                    f"{token}: source document has {source_document_words[token]}, "
                    f"candidate has {candidate_words[token]}, delta {deficit}"
                ),
            ))

    md_counts = Counter(content_tokens(candidate_md))
    fenced_text = _fenced_code_text(candidate_md)
    for unit in page_units:
        unit_id = f"page:{unit.page}"
        if unit.content_tokens >= constants.PAGE_MIN_TOKENS:
            recall = content_recall(
                candidate_md, unit.text, candidate_counts=md_counts,
            )
            if recall < constants.PAGE_RECALL_FLOOR:
                signals.append(RiskSignal(
                    unit_id=unit_id,
                    signal_type="low_recall",
                    severity="high",
                    detail=(
                        f"page recall {recall:.4f} below "
                        f"{constants.PAGE_RECALL_FLOOR:.2f}"
                    ),
                ))

        missing_code = _missing_code_signal(unit, fenced_text)
        if missing_code is not None:
            signals.append(missing_code)

        missing_captions = [
            caption for caption in unit.caption_lines
            if _text_key(caption) not in candidate_surface
        ]
        if missing_captions:
            signals.append(RiskSignal(
                unit_id=unit_id,
                signal_type="missing_captions",
                severity="medium",
                detail="candidate lacks: " + "; ".join(missing_captions),
            ))

        missing_headings = [
            title for title, _font_size in unit.heading_candidates
            if _text_key(normalize_heading_text(title)) not in candidate_heading_keys
        ]
        # combo_safe: an empty source packet carries no content to compare
        # headings against; flagging heading_drift here would be noise, not
        # a real discrepancy.
        if missing_headings and unit.text.strip():
            signals.append(RiskSignal(
                unit_id=unit_id,
                signal_type="heading_drift",
                severity="medium",
                detail=(
                    "large-font source lines are not Markdown headings: "
                    + "; ".join(missing_headings)
                ),
            ))

        if unit.has_tables:
            signals.append(RiskSignal(
                unit_id=unit_id,
                signal_type="table_presence",
                severity="high",
                detail="source page contains table structure",
            ))

    return signals


def route_html_units(
    section_units: list[SectionUnit],
    candidate_md: str,
    source_outline: list[tuple[str, str]],
) -> list[RiskSignal]:
    """Identify HTML sections with source-vs-candidate discrepancies."""
    signals: list[RiskSignal] = []
    candidate_sections = _parse_markdown_sections(candidate_md)
    candidate_by_title: dict[str, list[_MarkdownSection]] = defaultdict(list)
    for section in candidate_sections:
        candidate_by_title[_text_key(section.title)].append(section)

    candidate_by_normalized_title: dict[str, list[_MarkdownSection]] = defaultdict(list)
    for section in candidate_sections:
        norm_key = _text_key(normalize_heading_text(section.title))
        candidate_by_normalized_title[norm_key].append(section)

    # combo_safe: heading_drift is only meaningful when the outline entry's
    # corresponding section actually carries source content. extract_section_units
    # and extract_heading_outline walk the same heading-bounded document
    # traversal in order, so source_outline index N is section_units[N]'s
    # section_id (shared unit_id scheme, "section:N").
    section_text_by_id = {unit.section_id: unit.text for unit in section_units}

    source_occurrences: Counter[str] = Counter()
    for index, (source_tag, source_title) in enumerate(source_outline):
        unit_id = f"section:{index}"
        if _is_sanctioned_toc_title(source_title):
            continue
        normalized_title = normalize_heading_text(source_title)
        title_key = _text_key(normalized_title)
        # Occurrence tracking must count every outline entry (even ones whose
        # signal is later suppressed as combo_safe below), or a later
        # same-titled section would mismatch against the wrong candidate.
        occurrence = source_occurrences[title_key]
        source_occurrences[title_key] += 1
        if not section_text_by_id.get(index, "").strip():
            continue
        matches = candidate_by_normalized_title.get(title_key, [])
        candidate_section = (
            matches[occurrence] if occurrence < len(matches) else None
        )
        source_level = int(source_tag[1])
        if candidate_section is None or candidate_section.level != source_level:
            actual = (
                "missing"
                if candidate_section is None
                else f"h{candidate_section.level}"
            )
            signals.append(RiskSignal(
                unit_id=unit_id,
                signal_type="heading_drift",
                severity="medium",
                detail=(
                    f"{source_title!r}: source {source_tag}, candidate {actual}"
                ),
            ))

    unit_occurrences: Counter[str] = Counter()
    for unit in section_units:
        unit_id = f"section:{unit.section_id}"
        if _is_sanctioned_toc_title(unit.title):
            continue
        normalized_unit_title = normalize_heading_text(unit.title)
        title_key = _text_key(normalized_unit_title)
        occurrence = unit_occurrences[title_key]
        unit_occurrences[title_key] += 1
        matches = candidate_by_normalized_title.get(title_key, [])
        candidate_section = (
            matches[occurrence] if occurrence < len(matches) else None
        )
        if unit.content_tokens >= constants.SECTION_MIN_TOKENS:
            candidate_text = candidate_section.text if candidate_section else ""
            recall = content_recall(candidate_text, unit.text)
            if recall < constants.SECTION_RECALL_FLOOR:
                signals.append(RiskSignal(
                    unit_id=unit_id,
                    signal_type="low_recall",
                    severity="high",
                    detail=(
                        f"section recall {recall:.4f} below "
                        f"{constants.SECTION_RECALL_FLOOR:.2f}"
                    ),
                ))

        candidate_code_blocks = (
            candidate_section.code_blocks if candidate_section else 0
        )
        if unit.code_blocks > candidate_code_blocks:
            signals.append(RiskSignal(
                unit_id=unit_id,
                signal_type="missing_code",
                severity="medium",
                detail=(
                    f"source section has {unit.code_blocks} code blocks, "
                    f"candidate section has {candidate_code_blocks}"
                ),
            ))

    return signals
