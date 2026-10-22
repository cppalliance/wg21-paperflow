"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from typing import Any

from tomd.domain.document import PaperDocument
from tomd.lib.metadata_yaml.format import parse_front_matter
from tomd.lib.shared import apply_strip_leading_h1, strip_freeform_metadata_lines
from tomd.writers.markdown.blocks import RenderContext
from tomd.writers.markdown.front_matter import write_front_matter
from tomd.writers.markdown.markers import append_trailer_markers
from tomd.writers.markdown.normalizers import (
    normalize_front_matter,
    strip_body_metadata_text,
    strip_toc,
)


class MarkdownWriter:
    """Canonical Markdown backend writer and normalizer for PaperDocument ASTs."""

    def write_body(
        self,
        document: PaperDocument,
        meta: dict[str, Any] | None = None,
    ) -> str:
        """Format a PaperDocument into canonical Markdown text without trailer markers."""
        if document.is_skipped:
            return ""

        mailing_meta = meta if meta is not None else document.metadata.to_dict()

        # Branch 1: Structured AST Elements
        if document.elements:
            front = write_front_matter(mailing_meta)
            ctx = RenderContext.from_front_matter(front)
            blocks = [front] if front else []
            blocks.extend(
                rendered
                for elem in document.elements
                if (rendered := ctx.render_block(elem))
            )
            return "\n\n".join(blocks).rstrip() + "\n"

        # Branch 2: Hybrid Body String (Adapter Fallback)
        if not document.body.strip():
            front = write_front_matter(mailing_meta)
            return (front + "\n") if front else ""

        md = document.body
        md = normalize_front_matter(md, mailing_meta)
        md = strip_body_metadata_text(md)
        md = strip_freeform_metadata_lines(md, metadata=mailing_meta)

        title = parse_front_matter(md).get("title")
        if isinstance(title, str) and title:
            md = apply_strip_leading_h1(md, title)

        md = strip_toc(md)
        return md

    def write(
        self,
        document: PaperDocument,
        meta: dict[str, Any] | None = None,
    ) -> str:
        """Format a PaperDocument into canonical Markdown text."""
        if document.is_skipped:
            return ""

        return append_trailer_markers(
            self.write_body(document, meta=meta),
            document.diagnostics,
            kept_image_count=len(document.images),
        )
