#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Shared PDF geometry extraction for source-aware structural checks.

Both ``paragraph_align`` and ``code_fence_align`` compare the candidate
markdown against the source PDF's typographic layout. They share the same
per-line geometry (position, baseline, fonts, sizes) extracted by PyMuPDF and
the same monospace classification (via tomd's triple-signal detector). This
module owns that shared layer so neither duplicates it.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from pathlib import Path

import fitz
from tomd.lib.pdf.mono import classify_monospace

_log = logging.getLogger(__name__)

__all__ = [
    "PdfLine",
    "body_font_size",
    "is_monospace_line",
    "load_pdf_lines",
]


@dataclass
class PdfLine:
    """One text line with the geometry structural checks need."""

    page: int
    x0: float
    baseline: float
    text: str
    fonts: frozenset[str] = field(default_factory=frozenset)
    sizes: frozenset[float] = field(default_factory=frozenset)
    page_first: bool = False


def load_pdf_lines(pdf_path: Path) -> list[PdfLine]:
    """Read every text line with position, baseline, fonts and sizes.

    ``baseline`` is the text origin of the line's dominant span, not the bbox
    top: superscripts raise the bbox and fake paragraph gaps (see
    paragraph_align module doc).
    """
    lines: list[PdfLine] = []
    doc = fitz.open(str(pdf_path))
    try:
        for page_index in range(doc.page_count):
            page_lines: list[PdfLine] = []
            for block in doc[page_index].get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                for raw in block.get("lines", []):
                    spans = raw.get("spans", [])
                    text = "".join(s.get("text", "") for s in spans)
                    if not spans or not text.strip():
                        continue
                    dominant = max(spans, key=lambda s: s.get("size", 0.0))
                    page_lines.append(PdfLine(
                        page=page_index + 1,
                        x0=raw["bbox"][0],
                        baseline=dominant["origin"][1],
                        text=text,
                        fonts=frozenset(s.get("font", "") for s in spans),
                        sizes=frozenset(
                            round(s.get("size", 0.0), 1) for s in spans
                        ),
                    ))
            page_lines.sort(key=lambda ln: (round(ln.baseline, 1), ln.x0))
            if page_lines:
                page_lines[0].page_first = True
            lines.extend(page_lines)
    finally:
        doc.close()
    return lines


def body_font_size(lines: list[PdfLine]) -> float:
    """The most common font size across all lines (the body size)."""
    sizes = [size for line in lines for size in line.sizes]
    return statistics.mode(sizes) if sizes else 0.0


def is_monospace_line(line: PdfLine) -> bool:
    """True when every font on the line is classified monospace by tomd."""
    if not line.fonts:
        return False
    return all(classify_monospace(font) for font in line.fonts)
