"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from typing import Any

from tomd.domain.document import PaperDocument
from tomd.domain.elements import BlockElement
from tomd.domain.table import Table
from tomd.lib.metadata_yaml.format import parse_front_matter
from tomd.lib.shared import apply_strip_leading_h1, strip_freeform_metadata_lines
from tomd.writers.markdown.blocks import write_element
from tomd.writers.markdown.front_matter import write_front_matter
from tomd.writers.markdown.normalizers import (
    normalize_front_matter,
    strip_body_metadata_text,
    strip_toc,
)
from tomd.writers.markdown.tables import write_table


class MarkdownWriter:
    """Canonical Markdown backend writer and normalizer for PaperDocument ASTs."""

    def write(
        self,
        document: PaperDocument,
        meta: dict[str, Any] | None = None,
        *,
        wording_tags: bool = True,
    ) -> str:
        """Format a PaperDocument into canonical Markdown text."""
        if document.is_skipped:
            return ""

        mailing_meta = meta if meta is not None else document.metadata.to_dict()

        # Branch 1: Structured AST Elements
        if document.elements:
            blocks: list[str] = []
            front = write_front_matter(mailing_meta)
            if front:
                blocks.append(front)

            for elem in document.elements:
                if isinstance(elem, Table):
                    rendered = write_table(elem, wording_tags=wording_tags)
                elif isinstance(elem, BlockElement):
                    rendered = write_element(elem, wording_tags=wording_tags)
                else:
                    rendered = getattr(elem, "text", "")

                if rendered:
                    blocks.append(rendered)

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
