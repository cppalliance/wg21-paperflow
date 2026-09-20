#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""PDF text-layer extraction for the PDF-Text-Lane.

Text-only alternative to the VLM lane (vision.py + transcribe.py):
instead of a vision model reading pixels, PyMuPDF extracts the PDF's
embedded text layer per page. This is an independent extraction path
from tomd (different library traversal, block-sorted reading order),
usable as LLM judge input on a text-only model (DeepSeek-V4).

Known blind spot (documented, accepted): where the text layer itself
is broken (scanned pages, math rendered as glyph soup), this lane
cannot see the problem. A paper with an empty text layer fails loudly
rather than producing an empty comparison (fidelity rule).

Library-pure: returns data, never persists.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import median

import pymupdf

logger = logging.getLogger(__name__)

__all__ = [
    "MAX_TEXTLAYER_PAGES",
    "MIN_TEXTLAYER_CHARS",
    "HEADER_FOOTER_FREQ_THRESHOLD",
    "PageUnit",
    "TextLayerError",
    "clean_pages",
    "extract_page_units",
    "extract_textlayer",
    "normalize_textlayer",
]

MAX_TEXTLAYER_PAGES = 150
"""Page cap for text-layer extraction. Independent of the VLM lane's
``vision.MAX_PAGES`` (50) which reflects per-page raster cost.
Here the real protection is the context-budget check in ``pdf_judge.py``
(80 % of the model's context window); this cap is a safety net against
pathological documents. Largest paper in the current corpus: 101 pages."""

MIN_TEXTLAYER_CHARS = 200
"""A whole paper whose text layer totals fewer characters than this is
treated as effectively image-only (scanned / vector-text). The lane
fails loudly instead of judging against near-empty source text."""

HEADER_FOOTER_FREQ_THRESHOLD = 0.30
"""A line appearing on at least this fraction of pages is classified as
a running header or footer and stripped during normalization."""

_MIN_PAGES_FOR_HEADER_DETECTION = 3
"""Header/footer detection is only applied when the document has at
least this many pages; on shorter documents every line might repeat."""

_ISOLATED_PAGE_NUMBER_RE = re.compile(r"^\s*\d{1,5}\s*$")
"""Matches lines that contain only a page number (up to 5 digits)."""

_CONSECUTIVE_BLANK_RE = re.compile(r"\n{3,}")
"""Three or more consecutive newlines (collapsed to two)."""

_CAPTION_RE = re.compile(r"^\s*(?:Figure|Table)\s+\d+\b", re.IGNORECASE)
_HEADING_FONT_MULTIPLIER = 1.2
_TABLE_MIN_COLUMNS = 2
_TABLE_MIN_ROWS = 2
_CPP_KEYWORDS = frozenset({
    "constexpr", "template", "struct", "class", "enum", "auto", "concept",
    "requires", "noexcept", "void", "int", "float", "double", "char",
})
_WORD_RE = re.compile(r"\b\w+\b", re.UNICODE)


@dataclass
class PageUnit:
    """One page's structured source signals for the risk router."""

    page: int
    text: str
    heading_candidates: list[tuple[str, float]]
    has_images: bool
    has_tables: bool
    caption_lines: list[str]
    code_token_count: int
    content_tokens: int


class TextLayerError(Exception):
    """Raised when text-layer extraction fails for a document."""


def extract_textlayer(
    source_path: Path,
    *,
    max_pages: int = MAX_TEXTLAYER_PAGES,
) -> list[str]:
    """Extract the embedded text layer of each PDF page.

    Uses ``page.get_text("text", sort=True)``: blocks sorted by
    vertical then horizontal position, which approximates human reading
    order on multi-column layouts (deterministic, D7-adjacent).

    Returns a list of page text strings, one per page.

    Raises:
        TextLayerError: if the PDF cannot be opened, has zero pages,
            exceeds ``max_pages``, or its total text layer is below
            ``MIN_TEXTLAYER_CHARS`` (image-only PDF).
    """
    try:
        doc = pymupdf.open(str(source_path))
    except Exception as exc:
        raise TextLayerError(f"Cannot open PDF: {source_path}: {exc}") from exc

    try:
        page_count = doc.page_count
        if page_count == 0:
            raise TextLayerError(f"PDF has zero pages: {source_path}")
        if page_count > max_pages:
            raise TextLayerError(
                f"PDF has {page_count} pages, exceeds cap of {max_pages}: "
                f"{source_path}"
            )

        pages: list[str] = []
        for page_num in range(page_count):
            try:
                page = doc.load_page(page_num)
                pages.append(page.get_text("text", sort=True).strip())
            except Exception as exc:
                raise TextLayerError(
                    f"Page {page_num} text extraction failed: "
                    f"{source_path}: {exc}"
                ) from exc

        total_chars = sum(len(p) for p in pages)
        if total_chars < MIN_TEXTLAYER_CHARS:
            raise TextLayerError(
                f"Text layer is effectively empty ({total_chars} chars "
                f"across {page_count} pages); image-only PDF? "
                f"This lane requires an intact text layer: {source_path}"
            )
        return pages
    finally:
        doc.close()


def _block_looks_tabular(block: dict) -> bool:
    """Detect repeated multi-column text lines in one PyMuPDF text block."""
    multi_column_rows = 0
    for line in block.get("lines", []):
        nonempty_spans = [
            span for span in line.get("spans", [])
            if str(span.get("text", "")).strip()
        ]
        if len(nonempty_spans) >= _TABLE_MIN_COLUMNS:
            multi_column_rows += 1
    return multi_column_rows >= _TABLE_MIN_ROWS


def extract_page_units(source_path: Path) -> list[PageUnit]:
    """Extract per-page structured units from PDF using PyMuPDF's blocks API."""
    try:
        doc = pymupdf.open(str(source_path))
    except Exception as exc:
        raise TextLayerError(f"Cannot open PDF: {source_path}: {exc}") from exc

    try:
        if doc.page_count == 0:
            raise TextLayerError(f"PDF has zero pages: {source_path}")
        if doc.page_count > MAX_TEXTLAYER_PAGES:
            raise TextLayerError(
                f"PDF has {doc.page_count} pages, exceeds cap of "
                f"{MAX_TEXTLAYER_PAGES}: {source_path}"
            )

        raw_pages: list[str] = []
        page_metadata: list[
            tuple[list[tuple[str, float]], bool, bool, list[str], int]
        ] = []
        for page_index in range(doc.page_count):
            try:
                page = doc.load_page(page_index)
                page_dict = page.get_text("dict")
                raw_text = page.get_text("text", sort=True).strip()
            except Exception as exc:
                raise TextLayerError(
                    f"Page {page_index + 1} structured extraction failed: "
                    f"{source_path}: {exc}"
                ) from exc

            text_blocks = sorted(
                (
                    block for block in page_dict.get("blocks", [])
                    if block.get("type") == 0
                ),
                key=lambda block: (
                    block.get("bbox", (0.0, 0.0, 0.0, 0.0))[1],
                    block.get("bbox", (0.0, 0.0, 0.0, 0.0))[0],
                ),
            )
            has_images = any(
                block.get("type") == 1
                for block in page_dict.get("blocks", [])
            )
            lines_with_sizes: list[tuple[str, float]] = []
            font_sizes: list[float] = []
            has_table_structure = False
            for block in text_blocks:
                has_table_structure = (
                    has_table_structure or _block_looks_tabular(block)
                )
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    line_text = "".join(
                        str(span.get("text", "")) for span in spans
                    ).strip()
                    if not line_text:
                        continue
                    sizes = [
                        float(span.get("size", 0.0))
                        for span in spans
                        if str(span.get("text", "")).strip()
                    ]
                    line_size = max(sizes, default=0.0)
                    font_sizes.extend(size for size in sizes if size > 0.0)
                    lines_with_sizes.append((line_text, line_size))

            caption_lines = [
                text for text, _size in lines_with_sizes
                if _CAPTION_RE.match(text)
            ]
            median_size = median(font_sizes) if font_sizes else 0.0
            heading_candidates = [
                (text, size) for text, size in lines_with_sizes
                if median_size > 0.0
                and size > median_size * _HEADING_FONT_MULTIPLIER
            ]
            words = [word.lower() for word in _WORD_RE.findall(raw_text)]
            code_token_count = sum(word in _CPP_KEYWORDS for word in words)
            has_table_caption = any(
                line.lower().startswith("table") for line in caption_lines
            )
            raw_pages.append(raw_text)
            page_metadata.append((
                heading_candidates,
                has_images,
                has_table_structure or has_table_caption,
                caption_lines,
                code_token_count,
            ))

        cleaned_pages = clean_pages(raw_pages)
        return [
            PageUnit(
                page=index + 1,
                text=cleaned_pages[index],
                heading_candidates=metadata[0],
                has_images=metadata[1],
                has_tables=metadata[2],
                caption_lines=metadata[3],
                code_token_count=metadata[4],
                content_tokens=len(_WORD_RE.findall(cleaned_pages[index])),
            )
            for index, metadata in enumerate(page_metadata)
        ]
    finally:
        doc.close()


def clean_pages(pages: list[str]) -> list[str]:
    """Strip running headers/footers and isolated page numbers, per page.

    Header/footer lines are lines repeated on >= ``HEADER_FOOTER_FREQ_THRESHOLD``
    of pages (skipped below ``_MIN_PAGES_FOR_HEADER_DETECTION`` pages) and under
    120 chars. Blank lines within a page are preserved as ``""`` so page
    structure survives for callers that need it (the per-page recall screen in
    ``pdf_judge.py``); ``normalize_textlayer`` joins and collapses them the same
    way it always has. Returns one cleaned string per input page.
    """
    if not pages:
        return []

    # -- Identify repeated header/footer lines across pages ---------------
    header_footer_lines: set[str] = set()
    if len(pages) >= _MIN_PAGES_FOR_HEADER_DETECTION:
        line_counts: Counter[str] = Counter()
        for page_text in pages:
            seen_on_page: set[str] = set()
            for raw_line in page_text.splitlines():
                stripped = raw_line.strip()
                if stripped and stripped not in seen_on_page:
                    seen_on_page.add(stripped)
                    line_counts[stripped] += 1
        threshold = len(pages) * HEADER_FOOTER_FREQ_THRESHOLD
        header_footer_lines = {
            line for line, count in line_counts.items()
            if count >= threshold
            # shortcut: only strip short lines to avoid killing repeated
            # prose paragraphs (e.g. standard boilerplate in wording papers)
            and len(line) < 120
        }
        if header_footer_lines:
            logger.debug(
                "Stripping %d header/footer patterns (>= %.0f%% of %d pages)",
                len(header_footer_lines),
                HEADER_FOOTER_FREQ_THRESHOLD * 100,
                len(pages),
            )

    # -- Filter per page ----------------------------------------------------
    cleaned_pages: list[str] = []
    for page_text in pages:
        kept: list[str] = []
        for raw_line in page_text.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                kept.append("")
                continue
            if stripped in header_footer_lines:
                continue
            if _ISOLATED_PAGE_NUMBER_RE.match(stripped):
                continue
            kept.append(raw_line)
        cleaned_pages.append("\n".join(kept))
    return cleaned_pages


def normalize_textlayer(pages: list[str]) -> str:
    """Join extracted page texts and strip noise before LLM injection.

    Removes running headers/footers (lines repeated on >= 30 % of pages),
    isolated page-number lines, and collapses redundant whitespace.
    Real content is preserved; the output is the text the LLM and the
    grounding verifier both see (consistency requirement).
    """
    if not pages:
        return ""

    cleaned_parts = clean_pages(pages)
    joined = "\n\n".join(cleaned_parts)
    joined = _CONSECUTIVE_BLANK_RE.sub("\n\n", joined)
    return joined.strip()
