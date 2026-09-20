#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""PDF page rasterization for the VLM-PDF-Lane.

Library-pure: returns data, never persists. PDF source is obtained via
``backend.get_source_path(pid)`` (already exists in paperstore).

PyMuPDF is already a workspace dependency (tomd); no new dep needed.

Dormant status: this rasterizer is used only by the unwired VLM prototype.
It is retained as tested prior art and is not production coverage.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pymupdf

logger = logging.getLogger(__name__)

__all__ = [
    "MAX_PAGES",
    "TARGET_PIXELS",
    "RasterError",
    "rasterize_pdf",
]

MAX_PAGES = 50
"""Page cap. n5046 has 2679 pages (43% of all corpus pages); processing
every page at ~2000 visual tokens would blow context and wall-clock time.
Papers above this cap fail with a clear error (fidelity rule: no partial)."""

TARGET_PIXELS = 2_073_600
"""Client-side pixel budget per page image (~1440x1440 or 1920x1080).

The server's ``--mm-processor-kwargs max_pixels`` controls what the VLM
actually sees; client-side rasterization should match or slightly exceed
that to avoid double-downscale. 2.0M px at 72dpi letter = ~2.0x zoom."""

_BASE_DPI = 144
"""Starting render DPI. Adjusted per-page to hit TARGET_PIXELS."""


class RasterError(Exception):
    """Raised when PDF rasterization fails for a page or document."""


def rasterize_pdf(
    source_path: Path,
    *,
    max_pages: int = MAX_PAGES,
    target_pixels: int = TARGET_PIXELS,
) -> list[bytes]:
    """Rasterize each page of a PDF to PNG bytes.

    Returns a list of PNG byte strings, one per page. The list length
    equals the page count of the PDF.

    Raises:
        RasterError: if the PDF cannot be opened, has zero pages, or
            exceeds ``max_pages``.
        RasterError: if any individual page fails to rasterize (fidelity
            rule: no partial results).
    """
    try:
        doc = pymupdf.open(str(source_path))
    except Exception as exc:
        raise RasterError(f"Cannot open PDF: {source_path}: {exc}") from exc

    try:
        page_count = doc.page_count
        if page_count == 0:
            raise RasterError(f"PDF has zero pages: {source_path}")
        if page_count > max_pages:
            raise RasterError(
                f"PDF has {page_count} pages, exceeds cap of {max_pages}: "
                f"{source_path}"
            )

        pages: list[bytes] = []
        for page_num in range(page_count):
            try:
                page = doc.load_page(page_num)
                png_bytes = _rasterize_page(page, target_pixels)
                pages.append(png_bytes)
            except RasterError:
                raise
            except Exception as exc:
                raise RasterError(
                    f"Page {page_num} rasterization failed: {source_path}: {exc}"
                ) from exc
        return pages
    finally:
        doc.close()


def _rasterize_page(page: pymupdf.Page, target_pixels: int) -> bytes:
    """Render one page to PNG bytes, scaling to hit the pixel target."""
    rect = page.rect
    if rect.is_empty or rect.width <= 0 or rect.height <= 0:
        raise RasterError(f"Page has empty rect: {rect}")

    current_pixels = rect.width * rect.height
    if current_pixels <= 0:
        raise RasterError(f"Page has zero area: {rect}")

    scale = (target_pixels / current_pixels) ** 0.5
    zoom = max(scale, 1.0)

    mat = pymupdf.Matrix(zoom, zoom)
    pix = page.get_pixmap(
        matrix=mat,
        colorspace=pymupdf.csRGB,
        alpha=False,
    )
    try:
        return pix.tobytes("png")
    finally:
        pix = None
