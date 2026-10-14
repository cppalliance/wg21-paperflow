"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from tomd.domain.document import PaperDocument
from tomd.domain.elements import UncertainElement
from tomd.lib.metadata_yaml.format import format_front_matter
from tomd.writers.markdown.blocks import format_uncertain_element, write_element
from tomd.writers.markdown.markers import append_trailer_markers


class MarkdownWriter:
    """Canonical Markdown writer for PaperDocument ASTs."""

    def write_body(self, document: PaperDocument) -> str:
        """Format a PaperDocument into canonical Markdown text without trailer markers."""
        if document.is_skipped:
            return ""

        blocks: list[str] = []
        line_num = 1

        front = format_front_matter(document.metadata.to_dict())
        if front:
            blocks.append(front)
            line_num += front.count("\n") + 2

        for elem in document.elements:
            if isinstance(elem, UncertainElement):
                rendered = format_uncertain_element(elem, line_num)
            else:
                rendered = write_element(elem)
                if not rendered.strip():
                    continue
            blocks.append(rendered)
            line_num += rendered.count("\n") + 2

        if not blocks:
            return ""
        return "\n\n".join(blocks).rstrip() + "\n"

    def write(self, document: PaperDocument) -> str:
        """Render ``document.metadata`` as front matter followed by the document elements.

        A skipped document renders as the empty string, as does one with neither
        metadata nor visible elements.
        """
        if document.is_skipped:
            return ""

        return append_trailer_markers(
            self.write_body(document),
            document.diagnostics,
            kept_image_count=len(document.images),
        )
