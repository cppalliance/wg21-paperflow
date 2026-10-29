"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from collections.abc import Callable
import re

from tomd.domain.document import PaperDocument
from tomd.lib import (
    dedup_paragraphs,
    format_front_matter,
    strip_orphan_toc_list,
    strip_redundant_body_meta,
)
from tomd.lib.metadata_yaml.format import parse_front_matter
from tomd.lib.shared import _find_front_matter_end, apply_strip_leading_h1
from tomd.writers.markdown import MarkdownWriter, append_trailer_markers
from tomd.writers.markdown.front_matter import write_front_matter

_TABLE_CSS = (
    "<style>\n"
    "table, th, td { border: 1px solid #999; "
    "border-collapse: collapse; padding: 6px 10px; }\n"
    "th { background: #f5f5f5; }\n"
    "</style>"
)

_UNCERTAIN_MARKER_RE = re.compile(r"<!-- tomd:uncertain:L(\d+)-L(\d+) -->")


def _inject_table_css(md: str) -> str:
    """Inject a <style> block for table borders when HTML tables are present."""
    if "<table " not in md:
        return md
    insert_after = None
    fm_end = _find_front_matter_end(md)
    if fm_end is not None:
        line_end = md.find("\n", fm_end)
        if line_end >= 0:
            insert_after = line_end + 1
    if insert_after is not None:
        return md[:insert_after] + "\n" + _TABLE_CSS + "\n" + md[insert_after:]
    return _TABLE_CSS + "\n\n" + md


def _strip_leading_h1(md: str, title: str | None = None) -> str:
    """Strip a leading H1 that duplicates the front-matter title."""
    if title is None:
        parsed_title = parse_front_matter(md).get("title", "")
        title = parsed_title if isinstance(parsed_title, str) else ""
    return apply_strip_leading_h1(md, title)


PDF_STRING_PASSES: tuple[Callable[[str], str], ...] = (
    dedup_paragraphs,
    strip_redundant_body_meta,
    strip_orphan_toc_list,
    _inject_table_css,
    _strip_leading_h1,
)


def _apply_legacy_empty_reply_to(md: str, document: PaperDocument) -> str:
    """Preserve legacy empty ``reply-to:`` front-matter emission until P02a merges."""
    meta_dict = document.metadata.to_dict()
    if document.metadata.reply_to or not meta_dict:
        return md
    front = write_front_matter(meta_dict)
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
        if step is _strip_leading_h1:
            md = _strip_leading_h1(md, document.metadata.title)
        else:
            md = step(md)

    md = append_trailer_markers(
        md,
        document.diagnostics,
        kept_image_count=len(document.images),
    )
    return md.rstrip() + "\n"
