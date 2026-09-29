"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from tomd.domain.document import PaperDocument
from tomd.domain.elements import Heading, Paragraph
from tomd.domain.metadata import PaperMetadata
from tomd.domain.span import CodeSpan, StrongSpan, TextSpan
from tomd.domain.table import CodeCell, Table, TableRow, TableStrategy, TextCell
from tomd.writers import MarkdownWriter


def test_markdown_writer_emits_structured_document():
    meta = PaperMetadata(title="Structured Proposal", document="P9999R0")
    doc = PaperDocument(
        paper_id="P9999R0",
        metadata=meta,
        elements=[
            Heading.from_text(2, "Proposed Changes"),
            Paragraph(
                spans=[
                    TextSpan("We propose adding "),
                    StrongSpan(children=(CodeSpan("std::print"),)),
                    TextSpan(" support."),
                ]
            ),
        ],
    )
    writer = MarkdownWriter()
    out = writer.write(doc)
    assert 'title: "Structured Proposal"' in out
    assert "document: P9999R0" in out
    assert "## Proposed Changes" in out
    assert "We propose adding **`std::print`** support." in out


def test_markdown_writer_emits_table_as_pure_markdown():
    meta = PaperMetadata(title="Table Paper", document="P1111R0")
    doc = PaperDocument(
        paper_id="P1111R0",
        metadata=meta,
        elements=[
            Heading.from_text(1, "Table Demo"),
            Table(
                headers=[TextCell.from_text("Before"), TextCell.from_text("After")],
                rows=[
                    TableRow(cells=[
                        CodeCell(code="int x = 1;"),
                        CodeCell(code="int x = 2;"),
                    ]),
                ],
                strategy=TableStrategy.MIXED_HTML,
            ),
        ],
    )
    writer = MarkdownWriter()
    out = writer.write(doc)
    assert "| Before | After |" in out
    assert "| `int x = 1;` | `int x = 2;` |" in out
    assert "<style" not in out
    assert "<table" not in out
    assert "<tr" not in out
    assert "<td" not in out
    assert "<th" not in out


def test_markdown_writer_skipped_document():
    doc = PaperDocument(paper_id="P0000R0", is_skipped=True)
    writer = MarkdownWriter()
    assert writer.write(doc) == ""


def test_markdown_writer_emits_hybrid_body_with_normalizers():
    meta = PaperMetadata(title="Sample Paper", document="P0123R0", date="2026-03-01")
    raw_body = (
        "---\n"
        "title: Sample Paper\n"
        "---\n\n"
        "# Sample Paper\n\n"
        "## Contents\n"
        "1. Introduction\n\n"
        "## Introduction\n\n"
        "Body content.\n"
    )
    doc = PaperDocument(
        paper_id="P0123R0",
        metadata=meta,
        body=raw_body,
    )
    writer = MarkdownWriter()
    out = writer.write(doc)
    assert "document: P0123R0" in out
    assert "date: 2026-03-01" in out
    assert "\n# Sample Paper\n" not in out
    assert "## Contents" not in out
    assert "## Introduction" in out
