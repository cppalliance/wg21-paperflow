"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from dataclasses import FrozenInstanceError
from pathlib import Path
import pytest

from tomd.domain.document import ConvertedPaper, PaperDocument, SkipReason
from tomd.domain.elements import (
    BlockElement,
    Blockquote,
    CodeBlock,
    ElementKind,
    Heading,
    ImageElement,
    ListBlock,
    ListItem,
    Paragraph,
    ThematicBreak,
    UncertainElement,
    WordingBlock,
)
from tomd.domain.image import ExtractedImage, ImageRef
from tomd.domain.metadata import FRONT_MATTER_ORDER, PaperMetadata
from tomd.domain.span import (
    CodeSpan,
    EmphasisSpan,
    LineBreakSpan,
    LinkSpan,
    Span,
    StrikethroughSpan,
    StrongSpan,
    SubscriptSpan,
    SuperscriptSpan,
    TextSpan,
    UnderlineSpan,
)
from tomd.domain.table import (
    Cell,
    CellAlign,
    CodeCell,
    Table,
    TableKind,
    TableRow,
    TableStrategy,
    TextCell,
)


def test_span_primitives_and_immutability():
    text = TextSpan(content="hello")
    assert text.content == "hello"
    assert text.text == "hello"

    code = CodeSpan(code="std::vector<int>")
    assert code.code == "std::vector<int>"
    assert code.text == "std::vector<int>"

    lb = LineBreakSpan()
    assert lb.text == "\n"

    # Spans are frozen dataclasses
    with pytest.raises(FrozenInstanceError):
        text.content = "modified"  # type: ignore[misc]


def test_enums_and_base_types():
    # Base Span
    base_span = Span()
    assert base_span.text == ""

    # Base Cell
    base_cell = Cell(rowspan=1, colspan=2, align=CellAlign.RIGHT, width="100px")
    assert base_cell.rowspan == 1
    assert base_cell.colspan == 2
    assert base_cell.align == CellAlign.RIGHT
    assert base_cell.width == "100px"
    assert base_cell.text == ""

    # ElementKind enumeration
    assert ElementKind.HEADING == "heading"
    assert ElementKind.PARAGRAPH == "paragraph"
    assert ElementKind.CODE_BLOCK == "code_block"
    assert ElementKind.TABLE == "table"
    assert ElementKind.LIST == "list"
    assert ElementKind.BLOCKQUOTE == "blockquote"
    assert ElementKind.WORDING == "wording"
    assert ElementKind.THEMATIC_BREAK == "thematic_break"
    assert ElementKind.IMAGE == "image"
    assert ElementKind.UNCERTAIN == "uncertain"

    # SkipReason enumeration
    assert SkipReason.EMPTY_CONTENT == "empty_content"
    assert SkipReason.SLIDE_DECK == "slide_deck"
    assert SkipReason.STANDARDS_DRAFT == "standards_draft"
    assert SkipReason.UNREADABLE == "unreadable"


def test_container_spans_and_nesting():
    strong = StrongSpan.from_text("bold")
    assert strong.text == "bold"
    assert len(strong.children) == 1
    assert isinstance(strong.children[0], TextSpan)

    emphasis = EmphasisSpan.from_text("italic")
    assert emphasis.text == "italic"

    strike = StrikethroughSpan.from_text("deleted")
    assert strike.text == "deleted"

    underline = UnderlineSpan.from_text("inserted")
    assert underline.text == "inserted"

    sub = SubscriptSpan.from_text("sub")
    assert sub.text == "sub"

    sup = SuperscriptSpan.from_text("sup")
    assert sup.text == "sup"

    link = LinkSpan.from_text("Link Text", "https://isocpp.org", title="ISO C++")
    assert link.text == "Link Text"
    assert link.url == "https://isocpp.org"
    assert link.title == "ISO C++"

    nested = StrongSpan(
        children=(
            EmphasisSpan(children=(TextSpan("nested "),)),
            CodeSpan("code"),
        )
    )
    assert nested.text == "nested code"


def test_paper_metadata_roundtrip_and_ordering():
    data = {
        "title": "A Title",
        "document": "P1234R0",
        "date": "2026-01-15",
        "intent": "change",
        "audience": ["EWG", "LEWG"],
        "reply-to": ["Author <author@example.com>"],
        "extra_field": "preserved",
    }
    meta = PaperMetadata.from_dict(data)
    assert meta.title == "A Title"
    assert meta.document == "P1234R0"
    assert meta.date == "2026-01-15"
    assert meta.intent == "change"
    assert meta.audience == ["EWG", "LEWG"]
    assert meta.reply_to == ["Author <author@example.com>"]
    assert meta.extra == {"extra_field": "preserved"}

    out = meta.to_dict()
    assert out["title"] == "A Title"
    assert out["document"] == "P1234R0"
    assert out["date"] == "2026-01-15"
    assert out["intent"] == "change"
    assert out["audience"] == ["EWG", "LEWG"]
    assert out["reply-to"] == ["Author <author@example.com>"]
    assert out["extra_field"] == "preserved"

    # Keys in FRONT_MATTER_ORDER appear in exact expected sequence
    out_keys = list(out.keys())
    for i, key in enumerate(FRONT_MATTER_ORDER):
        assert out_keys[i] == key

    empty_meta = PaperMetadata.from_dict(None)
    assert empty_meta.title == ""
    assert empty_meta.to_dict() == {}


def test_table_and_cells():
    header_left = TextCell.from_text("Before", align=CellAlign.LEFT, width="50%")
    header_right = TextCell.from_text("After", align=CellAlign.LEFT, width="50%")
    assert header_left.text == "Before"
    assert header_left.align == CellAlign.LEFT
    assert header_left.width == "50%"

    code_cell = CodeCell(code="void f();", language="cpp", width="50%")
    assert code_cell.text == "void f();"
    assert code_cell.code == "void f();"
    assert code_cell.language == "cpp"

    text_cell = TextCell(
        spans=[TextSpan("Returns "), CodeSpan("nullopt")],
        rowspan=2,
        colspan=1,
        align=CellAlign.CENTER,
    )
    assert text_cell.text == "Returns nullopt"
    assert text_cell.rowspan == 2
    assert text_cell.colspan == 1
    assert text_cell.align == CellAlign.CENTER

    row = TableRow(cells=[code_cell, text_cell])
    assert len(row.cells) == 2

    table = Table(
        headers=[header_left, header_right],
        rows=[row],
        strategy=TableStrategy.MIXED_HTML,
        kind=TableKind.TONY_TABLE,
        caption="Comparison Table",
    )
    assert table.kind == TableKind.TONY_TABLE
    assert table.strategy == TableStrategy.MIXED_HTML
    assert table.caption == "Comparison Table"
    assert len(table.rows) == 1
    assert isinstance(table, BlockElement)


def test_image_models():
    extracted = ExtractedImage(
        stored_filename="figure1.png",
        bytes=b"\x89PNG\r\n\x1a\n",
        caption="Figure 1: State machine",
        alt="State machine diagram",
        source="raster",
    )
    assert extracted.stored_filename == "figure1.png"
    assert extracted.bytes == b"\x89PNG\r\n\x1a\n"
    assert extracted.caption == "Figure 1: State machine"
    assert extracted.source == "raster"

    ref = ImageRef(
        stored_filename="figure1.png",
        caption="Figure 1",
        alt="State machine",
        source_path=Path("/tmp/fig1.png"),
    )
    assert ref.stored_filename == "figure1.png"
    assert ref.source_path == Path("/tmp/fig1.png")


def test_block_elements_hierarchy():
    h = Heading.from_text(level=2, text="Introduction", id="intro")
    assert h.level == 2
    assert h.text == "Introduction"
    assert h.id == "intro"
    assert isinstance(h, BlockElement)

    p = Paragraph.from_text("A simple paragraph.")
    assert p.text == "A simple paragraph."
    assert isinstance(p, BlockElement)

    cb = CodeBlock(code='auto x = 42;\nstd::print("{}\\n", x);', language="cpp", title="sample.cpp")
    assert cb.code.startswith("auto x = 42;")
    assert cb.language == "cpp"
    assert cb.title == "sample.cpp"
    assert isinstance(cb, BlockElement)

    item1 = ListItem.from_text("First item")
    item2 = ListItem(spans=[StrongSpan.from_text("Second"), TextSpan(" item")])
    list_blk = ListBlock(items=[item1, item2], ordered=True)
    assert list_blk.ordered is True
    assert len(list_blk.items) == 2
    assert list_blk.items[1].text == "Second item"
    assert isinstance(list_blk, BlockElement)

    bq = Blockquote.from_text("This is quoted.", role="note")
    assert bq.role == "note"
    assert bq.text == "This is quoted."
    assert isinstance(bq, BlockElement)

    wb = WordingBlock(role="wording", text="Change [basic.def] as follows:")
    assert wb.role == "wording"
    assert wb.text == "Change [basic.def] as follows:"
    assert isinstance(wb, BlockElement)

    tb = ThematicBreak()
    assert isinstance(tb, BlockElement)

    img = ImageElement(caption="Figure 1", alt="Diagram", stored_filename="fig1.png")
    assert img.stored_filename == "fig1.png"
    assert isinstance(img, BlockElement)

    unc = UncertainElement(prompt="Check table layout", raw_content="<div>raw</div>")
    assert unc.prompt == "Check table layout"
    assert isinstance(unc, BlockElement)


def test_document_and_conversion_containers():
    meta = PaperMetadata(title="Sample Paper", document="P9999R0")
    h2 = Heading.from_text(2, "Proposed Wording")
    p = Paragraph.from_text("Text here.")

    doc = PaperDocument(
        paper_id="P9999R0",
        metadata=meta,
        elements=[h2, p],
        body="",
        is_skipped=False,
        skip_reason=None,
    )
    assert doc.paper_id == "P9999R0"
    assert len(doc.elements) == 2
    assert not doc.is_skipped
    assert doc.skip_reason is None

    skipped_doc = PaperDocument(
        paper_id="P0000R0",
        metadata=meta,
        is_skipped=True,
        skip_reason=SkipReason.EMPTY_CONTENT,
    )
    assert skipped_doc.is_skipped is True
    assert skipped_doc.skip_reason == SkipReason.EMPTY_CONTENT

    converted = ConvertedPaper.from_document(doc, markdown="---\ntitle: Sample Paper\n---\n\n## Proposed Wording\n\nText here.\n")
    assert converted.paper_id == "P9999R0"
    assert converted.metadata.title == "Sample Paper"
    assert "Proposed Wording" in converted.markdown
