"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from tomd.domain.document import PaperDocument
from tomd.domain.table import Table
from tomd.writers.markdown.blocks import write_element
from tomd.writers.markdown.front_matter import write_front_matter
from tomd.writers.markdown.tables import write_table


class MarkdownWriter:
    """Canonical Markdown writer for PaperDocument ASTs."""

    def write(self, document: PaperDocument) -> str:
        """Render ``document.metadata`` as front matter followed by the document elements.

        A skipped document renders as the empty string, as does one with neither
        metadata nor visible elements.
        """
        if document.is_skipped:
            return ""

        blocks = [write_front_matter(document.metadata)]
        for elem in document.elements:
            blocks.append(write_table(elem) if isinstance(elem, Table) else write_element(elem))

        rendered = [block for block in blocks if block]
        if not rendered:
            return ""
        return "\n\n".join(rendered).rstrip() + "\n"
