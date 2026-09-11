"""HTML to Markdown converter for WG21 papers."""

import logging
import os
import re
from pathlib import Path

from .. import (
    DOC_NUM_RE,
    apply_strip_leading_h1,
    dedup_paragraphs,
    format_front_matter,
    override_revision_from_filename,
    strip_orphan_toc_list,
    strip_redundant_body_meta,
)
from . import extract as _extract
from . import render as _render
from .images import HtmlImagesResult
from ..pdf.images import TRUNCATION_MARKER_TEMPLATE

_log = logging.getLogger(__name__)


def convert_html(
    path: Path | os.PathLike[str],
    *,
    html_images_result: HtmlImagesResult | None = None,
) -> tuple[str, list[str] | None]:
    """Convert an HTML file to Markdown.

    Reads the file as UTF-8 (with replacement for decode errors). Returns
    ``(markdown_text, prompts_or_none)`` where ``prompts_or_none`` is a
    list of self-contained LLM reconcile prompts (one per flagged HTML
    conversion issue) or ``None`` when conversion was fully clean.

    ``<img>`` tags never reach the markdown (#408): the LLM consumer
    cannot use pixels, so no image syntax, raw ``data:`` URI, or
    unresolvable remote URL is emitted, with or without a manifest.
    ``html_images_result`` is still accepted so the caller can persist
    the sidecar files and so the truncation marker can disclose on-disk
    image counts.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")

    soup = _extract.parse_html(text)
    generator = _extract.detect_generator(soup)
    _log.debug("Generator: %s", generator)

    metadata = _extract.extract_metadata(soup, generator)
    if metadata and "document" not in metadata:
        stem_match = DOC_NUM_RE.search(path.stem)
        if stem_match:
            metadata["document"] = stem_match.group(1).upper()
    if metadata and "document" in metadata:
        override_revision_from_filename(metadata, path)

    problems = _extract.strip_boilerplate(soup, generator)
    # Suppress the "unknown generator" warning when extraction produced usable
    # metadata - the generic extractor handled it well enough.
    if generator == "unknown" and metadata:
        problems = [p for p in problems if "Unrecognized" not in p]

    body_md = _render.render_body(soup, generator)

    if html_images_result is not None and html_images_result.images_truncated:
        kept = len(html_images_result.images)
        total = html_images_result.source_image_count
        body_md = (
            body_md.rstrip()
            + "\n\n"
            + TRUNCATION_MARKER_TEMPLATE.format(
                kept=kept,
                total=total,
                dropped=total - kept,
            )
        )

    if metadata and "title" not in metadata:
        h_match = re.search(r"^##\s+(.+)$", body_md, re.MULTILINE)
        if h_match:
            metadata["title"] = h_match.group(1).strip()

    parts = []
    if metadata:
        parts.append(format_front_matter(metadata))

    body_stripped = body_md.strip()
    while body_stripped.startswith("---") and (
        len(body_stripped) == 3 or body_stripped[3] in ("\n", "\r")
    ):
        body_stripped = body_stripped[3:].lstrip("\n\r")
    if body_stripped:
        parts.append(body_stripped)

    md = "\n\n".join(parts)
    md = dedup_paragraphs(md)
    md = strip_redundant_body_meta(md)
    md = strip_orphan_toc_list(md)
    if metadata:
        md = apply_strip_leading_h1(md, metadata.get("title", ""), 2)

    md = md.rstrip() + "\n"

    prompts: list[str] | None = None
    if problems:
        prompts = [
            (
                "The HTML-to-Markdown conversion encountered the following issue. "
                "Review and correct the affected region in the converted "
                "Markdown.\n\n"
                f"{problem}"
            )
            for problem in problems
        ]

    return md, prompts
