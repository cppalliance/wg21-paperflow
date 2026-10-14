"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

import inspect

from tomd.writers import DocumentWriter, MarkdownWriter


def test_document_writer_protocol_and_markdown_writer_instance():
    writer = MarkdownWriter()
    assert isinstance(writer, DocumentWriter)
    assert hasattr(writer, "write")
    assert callable(writer.write)


def test_writers_take_only_the_document():
    for write in (DocumentWriter.write, MarkdownWriter.write):
        assert list(inspect.signature(write).parameters) == ["self", "document"]
