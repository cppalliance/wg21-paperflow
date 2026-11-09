"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from collections.abc import Callable
import re
from typing import Any

from tomd.api import (
    _normalize_front_matter,
    _strip_body_metadata_text,
    _strip_toc,
)
from tomd.domain.document import PaperDocument
from tomd.lib import (
    dedup_paragraphs,
    format_front_matter,
    strip_orphan_toc_list,
    strip_redundant_body_meta,
)
from tomd.lib.metadata_yaml.format import parse_front_matter
from tomd.lib.pdf.emit import inject_table_css, renumber_uncertain_markers
from tomd.lib.pdf.pipeline import insert_after_front_matter
from tomd.lib.pdf.summary import header_comment
from tomd.lib.shared import apply_strip_leading_h1, strip_freeform_metadata_lines
from tomd.writers.markdown import MarkdownWriter, append_trailer_markers

_UNCERTAIN_MARKER_RE = re.compile(r"<!-- tomd:uncertain:L(\d+)-L(\d+) -->")


def _strip_leading_h1(md: str) -> str:
    """Strip a leading H1 that duplicates the front-matter title."""
    parsed_title = parse_front_matter(md).get("title", "")
    title = parsed_title if isinstance(parsed_title, str) else ""
    return apply_strip_leading_h1(md, title)


PDF_STRING_PASSES: tuple[Callable[[str], str], ...] = (
    dedup_paragraphs,
    strip_redundant_body_meta,
    strip_orphan_toc_list,
    inject_table_css,
    _strip_leading_h1,
)


def apply_api_normalizers(md: str, meta: dict[str, Any]) -> str:
    """Run the API-level legacy Markdown string normalizer chain."""
    md = _normalize_front_matter(md, meta)
    md = _strip_body_metadata_text(md)
    md = strip_freeform_metadata_lines(md, metadata=meta)
    title = parse_front_matter(md).get("title")
    if isinstance(title, str) and title:
        md = apply_strip_leading_h1(md, title)
    md = _strip_toc(md)
    return renumber_uncertain_markers(md)


def _apply_legacy_empty_reply_to(md: str, document: PaperDocument) -> str:
    """Preserve legacy empty ``reply-to:`` front-matter emission when ``format_front_matter`` retains empty lists."""
    meta_dict = document.metadata.to_dict()
    if document.metadata.reply_to or not meta_dict:
        return md
    front = format_front_matter(meta_dict)
    if not front or not md.startswith(front):
        return md
    legacy_fm = format_front_matter({**meta_dict, "reply-to": []})
    md = legacy_fm + md[len(front) :]
    line_delta = legacy_fm.count("\n") - front.count("\n")
    if line_delta != 0 and "<!-- tomd:uncertain:L" in md:
        md = _UNCERTAIN_MARKER_RE.sub(
            lambda m: (
                f"<!-- tomd:uncertain:L{int(m.group(1)) + line_delta}"
                f"-L{int(m.group(2)) + line_delta} -->"
            ),
            md,
        )
    return md


def render_pdf(document: PaperDocument) -> str:
    """Render a PDF PaperDocument to Markdown via MarkdownWriter and legacy string passes."""
    if document.is_skipped:
        return ""

    md = MarkdownWriter().write_body(document).removesuffix("\n")
    md = _apply_legacy_empty_reply_to(md, document)

    for step in PDF_STRING_PASSES:
        md = step(md)

    md = append_trailer_markers(
        md,
        document.diagnostics,
        kept_image_count=len(document.images),
    )
    md = renumber_uncertain_markers(md.rstrip() + "\n")
    if document.diagnostics.summary is not None and md.strip():
        md = insert_after_front_matter(md, header_comment(document.diagnostics.summary))
    return md
