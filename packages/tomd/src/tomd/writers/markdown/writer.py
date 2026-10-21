"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from tomd.domain.document import PaperDocument
from tomd.lib.metadata_yaml.format import format_front_matter
from tomd.writers.markdown.blocks import write_element


class MarkdownWriter:
    """Canonical Markdown writer for PaperDocument ASTs."""

    def write(self, document: PaperDocument) -> str:
        """Render ``document.metadata`` as front matter followed by the document elements.

        A skipped document renders as the empty string, as does one with neither
        metadata nor visible elements.
        """
        if document.is_skipped:
            return ""

        blocks = [format_front_matter(document.metadata.to_dict())]
        blocks.extend(write_element(element) for element in document.elements)

        rendered = [block for block in blocks if block]
        if not rendered:
            return ""
        return "\n\n".join(rendered).rstrip() + "\n"
