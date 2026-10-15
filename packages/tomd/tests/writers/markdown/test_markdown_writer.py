"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

import pytest

from tomd.domain.document import PaperDocument
from tomd.domain.elements import Heading, ImageElement, Paragraph
from tomd.domain.metadata import PaperMetadata
from tomd.domain.span import CodeSpan, StrongSpan, TextSpan
from tomd.domain.table import CodeCell, Table, TableRow, TextCell
from tomd.lib.metadata_yaml.format import format_front_matter
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


def test_markdown_writer_skips_image_elements():
    doc = PaperDocument(
        paper_id="P9999R0",
        elements=[
            Paragraph.from_text("Before."),
            ImageElement(caption="Figure 1", alt="Diagram", stored_filename="fig1.png"),
            Paragraph.from_text("After."),
        ],
    )
    assert MarkdownWriter().write(doc) == "Before.\n\nAfter.\n"


def test_markdown_writer_skipped_document():
    doc = PaperDocument(paper_id="P0000R0", is_skipped=True)
    writer = MarkdownWriter()
    assert writer.write(doc) == ""


def test_markdown_writer_skipped_document_ignores_metadata_and_elements():
    doc = PaperDocument(
        paper_id="P0000R0",
        metadata=PaperMetadata(title="Slides", document="P0000R0"),
        elements=[Paragraph.from_text("Body.")],
        is_skipped=True,
    )
    assert MarkdownWriter().write(doc) == ""


def test_markdown_writer_renders_exactly_document_metadata():
    meta = PaperMetadata(title="Info: Status", document="D0123R0", reply_to=["Alice"])
    doc = PaperDocument(paper_id="P0123R0", metadata=meta)
    assert MarkdownWriter().write(doc) == format_front_matter(meta.to_dict()) + "\n"


def test_markdown_writer_empty_document_writes_empty_string():
    assert MarkdownWriter().write(PaperDocument(paper_id="P0000R0")) == ""


def test_markdown_writer_document_whose_elements_render_empty():
    image = ImageElement(caption="Figure 1", alt="Diagram", stored_filename="fig1.png")
    assert MarkdownWriter().write(PaperDocument(paper_id="P0000R0", elements=[image])) == ""

    meta = PaperMetadata(title="Figures", document="P0000R0")
    doc = PaperDocument(paper_id="P0000R0", metadata=meta, elements=[image])
    assert MarkdownWriter().write(doc) == format_front_matter(meta.to_dict()) + "\n"


def _write_metadata(meta: PaperMetadata) -> str:
    return MarkdownWriter().write(PaperDocument(paper_id="P0000R0", metadata=meta))


def test_markdown_writer_front_matter_canonical_order_and_quoting():
    meta = PaperMetadata(
        title="Sample Proposal",
        document="P1234R0",
        date="2026-03-01",
        intent="explore",
        audience=["LEWG", "SG1"],
        reply_to=["Author Name <author@example.com>"],
    )
    assert _write_metadata(meta) == (
        "---\n"
        'title: "Sample Proposal"\n'
        "document: P1234R0\n"
        "date: 2026-03-01\n"
        "intent: explore\n"
        "audience:\n"
        '  - "LEWG"\n'
        '  - "SG1"\n'
        "reply-to:\n"
        '  - "Author Name <author@example.com>"\n'
        "---\n"
    )


def test_markdown_writer_front_matter_extra_keys_precede_reply_to():
    meta = PaperMetadata(
        title="Extras",
        document="P9999R1",
        reply_to=["A <a@example.com>", "B <b@example.com>"],
        extra={"project": "ISO C++", "issue": "42"},
    )
    assert _write_metadata(meta) == (
        "---\n"
        'title: "Extras"\n'
        "document: P9999R1\n"
        "project: ISO C++\n"
        "issue: 42\n"
        "reply-to:\n"
        '  - "A <a@example.com>"\n'
        '  - "B <b@example.com>"\n'
        "---\n"
    )


def test_markdown_writer_front_matter_normalizes_title():
    meta = PaperMetadata(title="std :: execution  Senders", document="P2300R10")
    assert _write_metadata(meta) == '---\ntitle: "std::execution Senders"\ndocument: P2300R10\n---\n'


@pytest.mark.parametrize(
    "meta",
    [
        pytest.param(PaperMetadata(title="T", intent="  "), id="blank-scalar"),
        pytest.param(PaperMetadata(title="T", reply_to=["", " "]), id="blank-reply-to-items"),
        pytest.param(PaperMetadata(title="T", extra={"project": " "}), id="blank-extra"),
    ],
)
def test_markdown_writer_front_matter_skips_blank_fields(meta):
    assert _write_metadata(meta) == '---\ntitle: "T"\n---\n'
