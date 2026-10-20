"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

import pytest

from tomd.domain.elements import (
    Blockquote,
    CodeBlock,
    Heading,
    ListBlock,
    ListItem,
    Paragraph,
    WordingBlock,
    WordingRole,
)
from tomd.domain.span import (
    CodeSpan,
    Span as DomainSpan,
    StrikethroughSpan,
    StrongSpan,
    TextSpan,
    UnderlineSpan,
)
from tomd.domain.table import Table, TableRow, TextCell
from tomd.lib.html.extract import parse_html
from tomd.lib.html.render import _render_blockquote, _render_div, _render_element, _render_wording_div
from tomd.lib.pdf.types import Line, Section, SectionKind, Span as PdfSpan
from tomd.lib.pdf.wording_emit import _render_wording_section
from tomd.lib.wording_cleanup import strip_redundant_tags
from tomd.writers.markdown.blocks import strip_redundant_roles, write_element


def _pdf_span(text: str, role: str | None = None, *, monospace: bool = False) -> PdfSpan:
    span = PdfSpan(text=text, monospace=monospace)
    span.wording_role = role
    return span


def _make_wording_section(kind: SectionKind, lines: list[Line]) -> Section:
    text = "\n".join("".join(s.text for s in ln.spans) for ln in lines)
    return Section(kind=kind, text=text, lines=lines)


def test_wording_prose_uniform_add_and_remove():
    add_sec = _make_wording_section(
        SectionKind.WORDING_ADD,
        [Line(spans=[_pdf_span("• added bullet", "ins")])],
    )
    add_ast = WordingBlock(
        role="wording-add",
        children=[Paragraph(spans=[UnderlineSpan.from_text("• added bullet")])],
    )
    assert write_element(strip_redundant_roles(add_ast)) == _render_wording_section(add_sec) == "• added bullet"

    rem_sec = _make_wording_section(
        SectionKind.WORDING_REMOVE,
        [Line(spans=[_pdf_span("doomed paragraph", "del")])],
    )
    rem_ast = WordingBlock(
        role="wording-remove",
        children=[Paragraph(spans=[StrikethroughSpan.from_text("doomed paragraph")])],
    )
    assert write_element(strip_redundant_roles(rem_ast)) == _render_wording_section(rem_sec) == "doomed paragraph"


def test_wording_prose_mixed_and_neutral():
    mixed_sec = _make_wording_section(
        SectionKind.WORDING_ADD,
        [Line(spans=[_pdf_span("context "), _pdf_span("inserted", "ins"), _pdf_span(" tail")])],
    )
    mixed_ast = WordingBlock(
        role="wording-add",
        children=[
            Paragraph(
                spans=[
                    TextSpan("context "),
                    UnderlineSpan.from_text("inserted"),
                    TextSpan(" tail"),
                ]
            )
        ],
    )
    assert (
        write_element(strip_redundant_roles(mixed_ast))
        == _render_wording_section(mixed_sec)
        == "context <ins>inserted</ins> tail"
    )

    neutral_sec = _make_wording_section(
        SectionKind.WORDING,
        [Line(spans=[_pdf_span("new", "ins"), _pdf_span(" / "), _pdf_span("old", "del")])],
    )
    neutral_ast = WordingBlock(
        role="wording",
        children=[
            Paragraph(
                spans=[
                    UnderlineSpan.from_text("new"),
                    TextSpan(" / "),
                    StrikethroughSpan.from_text("old"),
                ]
            )
        ],
    )
    assert (
        write_element(strip_redundant_roles(neutral_ast))
        == _render_wording_section(neutral_sec)
        == "<ins>new</ins> / <del>old</del>"
    )


def test_wording_prose_grouping_and_angle_bracket_escaping():
    cases: list[tuple[SectionKind, WordingRole, list[Line], list[DomainSpan]]] = [
        (
            SectionKind.WORDING,
            "wording",
            [Line(spans=[_pdf_span("A", "ins"), _pdf_span(" "), _pdf_span("B", "ins")])],
            [UnderlineSpan.from_text("A"), TextSpan(" "), UnderlineSpan.from_text("B")],
        ),
        (
            SectionKind.WORDING,
            "wording",
            [Line(spans=[_pdf_span("A", "ins"), _pdf_span(" "), _pdf_span("B", "del")])],
            [UnderlineSpan.from_text("A"), TextSpan(" "), StrikethroughSpan.from_text("B")],
        ),
        (
            SectionKind.WORDING,
            "wording",
            [Line(spans=[_pdf_span("native_simd", "del"), _pdf_span("<float>", monospace=True)])],
            [StrikethroughSpan.from_text("native_simd"), TextSpan("<float>")],
        ),
        (
            SectionKind.WORDING,
            "wording",
            [Line(spans=[_pdf_span("template<class U>", "ins")])],
            [UnderlineSpan.from_text("template<class U>")],
        ),
        (
            SectionKind.WORDING,
            "wording",
            [Line(spans=[_pdf_span("x", "del"), _pdf_span("U&& value", monospace=True)])],
            [StrikethroughSpan.from_text("x"), TextSpan("U&& value")],
        ),
        (
            SectionKind.WORDING,
            "wording",
            [Line(spans=[_pdf_span("use ", "ins"), _pdf_span("vec<float>", "context", monospace=True)])],
            [UnderlineSpan.from_text("use "), CodeSpan("vec<float>")],
        ),
        (
            SectionKind.WORDING_ADD,
            "wording-add",
            [
                Line(
                    spans=[
                        _pdf_span("• ", "ins"),
                        _pdf_span("common_type_t<From, To>", "ins", monospace=True),
                        _pdf_span(" is To,", "ins"),
                    ]
                )
            ],
            [
                UnderlineSpan.from_text("• "),
                UnderlineSpan.from_text("common_type_t<From, To>"),
                UnderlineSpan.from_text(" is To,"),
            ],
        ),
        (
            SectionKind.WORDING_ADD,
            "wording-add",
            [
                Line(spans=[_pdf_span("First inserted sentence.", "ins")]),
                Line(spans=[_pdf_span("Second inserted sentence.", "ins")]),
            ],
            [
                UnderlineSpan.from_text("First inserted sentence."),
                TextSpan("\n"),
                UnderlineSpan.from_text("Second inserted sentence."),
            ],
        ),
        (
            SectionKind.WORDING,
            "wording",
            [Line(spans=[_pdf_span('# include "header" ', None), _pdf_span("added", "ins")])],
            [TextSpan('# include "header" '), UnderlineSpan.from_text("added")],
        ),
    ]

    for sec_kind, role, lines, spans in cases:
        sec = _make_wording_section(sec_kind, lines)
        block = WordingBlock(role=role, children=[Paragraph(spans=spans)])
        assert write_element(strip_redundant_roles(block)) == _render_wording_section(sec)


def test_wording_wholesale_code_shapes():
    l1 = Line(spans=[_pdf_span("template<class From, class To>", "ins", monospace=True)])
    l2 = Line(
        spans=[_pdf_span("concept simd-consteval-broadcast-arg = see below;", "ins", monospace=True)]
    )
    sec = _make_wording_section(SectionKind.WORDING_ADD, [l1, l2])
    block = WordingBlock(
        role="wording-add",
        children=[
            CodeBlock(
                code=(
                    "template<class From, class To>\n"
                    "concept simd-consteval-broadcast-arg = see below;"
                ),
                language="cpp",
            )
        ],
    )
    assert write_element(strip_redundant_roles(block)) == _render_wording_section(sec)

    s1 = PdfSpan(text="ab", monospace=True, bbox=(100.0, 0.0, 112.0, 10.0))
    s1.wording_role = "ins"
    s2 = PdfSpan(text="cd", monospace=True, bbox=(118.0, 12.0, 130.0, 22.0))
    s2.wording_role = "ins"
    indented_sec = _make_wording_section(SectionKind.WORDING_ADD, [Line(spans=[s1]), Line(spans=[s2])])
    indented_block = WordingBlock(
        role="wording-add",
        children=[CodeBlock(code="ab\n   cd", language="cpp")],
    )
    assert write_element(strip_redundant_roles(indented_block)) == _render_wording_section(indented_sec)

    b1 = PdfSpan(text="int a;", monospace=True, bbox=(0.0, 0.0, 12.0, 10.0))
    b1.wording_role = "ins"
    b3 = PdfSpan(text="int b;", monospace=True, bbox=(0.0, 24.0, 12.0, 34.0))
    b3.wording_role = "ins"
    blank_sec = _make_wording_section(
        SectionKind.WORDING_ADD,
        [Line(spans=[b1]), Line(spans=[]), Line(spans=[b3])],
    )
    blank_block = WordingBlock(
        role="wording-add",
        children=[CodeBlock(code="int a;\n\nint b;", language="cpp")],
    )
    assert write_element(strip_redundant_roles(blank_block)) == _render_wording_section(blank_sec)


def test_wording_code_diff_shapes():
    l1 = Line(spans=[_pdf_span("template<class U>", monospace=True)])
    l2 = Line(
        spans=[
            _pdf_span("  constexpr ", monospace=True),
            _pdf_span("explicit(see below)", "del", monospace=True),
            _pdf_span(" basic_vec(U&& value) noexcept;", monospace=True),
        ]
    )
    sec = _make_wording_section(SectionKind.WORDING_REMOVE, [l1, l2])
    block = WordingBlock(
        role="wording-remove",
        children=[
            CodeBlock(
                language="cpp",
                lines=[
                    [TextSpan("template<class U>")],
                    [
                        TextSpan("  constexpr "),
                        StrikethroughSpan.from_text("explicit(see below)"),
                        TextSpan(" basic_vec(U&& value) noexcept;"),
                    ],
                ],
            )
        ],
    )
    assert write_element(strip_redundant_roles(block)) == _render_wording_section(sec)

    inline_edit_l1 = Line(
        spans=[
            _pdf_span("template<", monospace=True),
            _pdf_span("class", "del", monospace=True),
            _pdf_span("explicitly-convertible-to<value_type>", "ins", monospace=True),
            _pdf_span(" U>", monospace=True),
        ]
    )
    inline_edit_l2 = Line(
        spans=[_pdf_span("  consteval basic_vec(U&& x);", "ins", monospace=True)]
    )
    inline_sec = _make_wording_section(SectionKind.WORDING, [inline_edit_l1, inline_edit_l2])
    inline_block = WordingBlock(
        role="wording",
        children=[
            CodeBlock(
                language="cpp",
                lines=[
                    [
                        TextSpan("template<"),
                        StrikethroughSpan.from_text("class"),
                        UnderlineSpan.from_text("explicitly-convertible-to<value_type>"),
                        TextSpan(" U>"),
                    ],
                    [
                        TextSpan("  "),
                        UnderlineSpan.from_text("consteval basic_vec(U&& x);"),
                    ],
                ],
            )
        ],
    )
    assert write_element(strip_redundant_roles(inline_block)) == _render_wording_section(inline_sec)

    near_uniform_sec = _make_wording_section(
        SectionKind.WORDING_ADD,
        [
            Line(spans=[_pdf_span("x" * 200, "ins", monospace=True)]),
            Line(spans=[_pdf_span("noexcept", "del", monospace=True)]),
        ],
    )
    near_uniform_block = WordingBlock(
        role="wording-add",
        children=[
            CodeBlock(
                language="cpp",
                lines=[
                    [UnderlineSpan.from_text("x" * 200)],
                    [StrikethroughSpan.from_text("noexcept")],
                ],
            )
        ],
    )
    assert (
        write_element(strip_redundant_roles(near_uniform_block))
        == _render_wording_section(near_uniform_sec)
    )


def test_wording_html_div_equivalents():
    cases: list[tuple[str, WordingBlock]] = [
        (
            '<div class="wording-add"><p><ins>wholly added clause</ins></p></div>',
            WordingBlock(
                role="wording-add",
                children=[Paragraph(spans=[UnderlineSpan.from_text("wholly added clause")])],
            ),
        ),
        (
            '<div class="wording-add"><p>unchanged context here plus <ins>a bit</ins></p></div>',
            WordingBlock(
                role="wording-add",
                children=[
                    Paragraph(
                        spans=[
                            TextSpan("unchanged context here plus "),
                            UnderlineSpan.from_text("a bit"),
                        ]
                    )
                ],
            ),
        ),
        (
            '<div class="wording"><p><ins>everything inserted</ins></p></div>',
            WordingBlock(
                role="wording",
                children=[Paragraph(spans=[UnderlineSpan.from_text("everything inserted")])],
            ),
        ),
    ]

    for html, block in cases:
        div = parse_html(html).find("div")
        assert div is not None
        assert write_element(strip_redundant_roles(block)) == _render_wording_div(div, "mpark")


@pytest.mark.parametrize(
    ("role", "spans", "legacy_md"),
    [
        # Exactly at 0.95 threshold (95 role chars / 100 total chars)
        (
            "wording-add",
            [UnderlineSpan.from_text("a" * 95), TextSpan(" "), TextSpan("b" * 5)],
            f"<ins>{'a' * 95}</ins> {'b' * 5}",
        ),
        (
            "wording-remove",
            [StrikethroughSpan.from_text("a" * 95), TextSpan(" "), TextSpan("b" * 5)],
            f"<del>{'a' * 95}</del> {'b' * 5}",
        ),
        # Just below 0.95 threshold (94 role chars / 100 total chars)
        (
            "wording-add",
            [UnderlineSpan.from_text("a" * 94), TextSpan(" "), TextSpan("b" * 6)],
            f"<ins>{'a' * 94}</ins> {'b' * 6}",
        ),
        (
            "wording-remove",
            [StrikethroughSpan.from_text("a" * 94), TextSpan(" "), TextSpan("b" * 6)],
            f"<del>{'a' * 94}</del> {'b' * 6}",
        ),
        # Above 0.95 threshold (96 role chars / 100 total chars and 100%)
        (
            "wording-add",
            [UnderlineSpan.from_text("a" * 96), TextSpan(" "), TextSpan("b" * 4)],
            f"<ins>{'a' * 96}</ins> {'b' * 4}",
        ),
        (
            "wording-add",
            [UnderlineSpan.from_text("• added bullet")],
            "<ins>• added bullet</ins>",
        ),
        (
            "wording-remove",
            [StrikethroughSpan.from_text("obsolete clause")],
            "<del>obsolete clause</del>",
        ),
        # Contrarian tag survives uniform section
        (
            "wording-add",
            [UnderlineSpan.from_text("A" * 200), TextSpan(" "), StrikethroughSpan.from_text("x")],
            f"<ins>{'A' * 200}</ins> <del>x</del>",
        ),
        (
            "wording-remove",
            [StrikethroughSpan.from_text("B" * 200), TextSpan(" "), UnderlineSpan.from_text("y")],
            f"<del>{'B' * 200}</del> <ins>y</ins>",
        ),
        # Neutral role never strips even at 100%
        (
            "wording",
            [UnderlineSpan.from_text("a" * 100)],
            f"<ins>{'a' * 100}</ins>",
        ),
        # Multiline role spans
        (
            "wording-add",
            [UnderlineSpan.from_text("first line\nsecond line\nthird line")],
            "<ins>first line\nsecond line\nthird line</ins>",
        ),
        (
            "wording-remove",
            [StrikethroughSpan.from_text("first line\nsecond line\nthird line")],
            "<del>first line\nsecond line\nthird line</del>",
        ),
        # Untagged and empty
        (
            "wording-add",
            [TextSpan("Plain wording prose with no inline tags at all.")],
            "Plain wording prose with no inline tags at all.",
        ),
        (
            "wording-add",
            [],
            "",
        ),
    ],
)
def test_strip_redundant_roles_matches_strip_redundant_tags(
    role: WordingRole,
    spans: list[DomainSpan],
    legacy_md: str,
):
    block = WordingBlock(role=role, children=[Paragraph(spans=spans)] if spans else [])
    cleaned = strip_redundant_roles(block)

    assert write_element(block) == write_element(cleaned) == strip_redundant_tags(role, legacy_md)
    assert strip_redundant_roles(cleaned) == cleaned


def test_strip_redundant_roles_unwraps_compound_child_blocks():
    block = WordingBlock(
        role="wording-add",
        children=[
            Heading(level=3, spans=[UnderlineSpan.from_text("20.1 General")]),
            ListBlock(
                items=[
                    ListItem(
                        spans=[StrongSpan(children=(UnderlineSpan.from_text("first item"),))],
                        children=[Paragraph(spans=[UnderlineSpan.from_text("continuation")])],
                    )
                ]
            ),
            Blockquote(children=[Paragraph(spans=[UnderlineSpan.from_text("quoted note")])]),
            Table(
                headers=[TextCell(spans=[UnderlineSpan.from_text("Header")])],
                rows=[TableRow(cells=[TextCell(spans=[UnderlineSpan.from_text("Value")])])],
            ),
        ],
    )
    cleaned = strip_redundant_roles(block)

    assert cleaned != block
    assert write_element(cleaned) == (
        "### 20.1 General\n\n"
        "- **first item**\n\n"
        "  continuation\n\n"
        "> quoted note\n\n"
        "| Header |\n"
        "| --- |\n"
        "| Value |"
    )


def test_blockquote_single_paragraph():
    block = Blockquote(children=[Paragraph.from_text("Quoted text")])
    el = parse_html("<blockquote><p>Quoted text</p></blockquote>").find("blockquote")
    assert el is not None

    assert write_element(block) == _render_blockquote(el, "mpark") == "> Quoted text"


def test_blockquote_multiple_paragraphs_quote_blank_lines_with_trailing_space():
    block = Blockquote(children=[Paragraph.from_text("First"), Paragraph.from_text("Second")])
    el = parse_html("<blockquote><p>First</p><p>Second</p></blockquote>").find("blockquote")
    assert el is not None

    assert write_element(block) == _render_blockquote(el, "mpark") == "> First\n> \n> Second"


def test_blockquote_multiple_blocks_with_code_and_internal_blank_lines():
    block = Blockquote(
        children=[
            Paragraph.from_text("Intro"),
            CodeBlock(code="int a;\n\nint b;", language="cpp"),
            Paragraph.from_text("Outro"),
        ]
    )
    html = "<blockquote><p>Intro</p><pre>int a;\n\nint b;</pre><p>Outro</p></blockquote>"
    el = parse_html(html).find("blockquote")
    assert el is not None

    assert (
        write_element(block)
        == _render_blockquote(el, "mpark")
        == "> Intro\n> \n> ```cpp\n> int a;\n> \n> int b;\n> ```\n> \n> Outro"
    )


def test_blockquote_with_nested_list():
    nested_list = ListBlock(
        items=[
            ListItem(
                spans=[TextSpan("one")],
                children=[ListBlock(items=[ListItem.from_text("sub")])],
            ),
            ListItem.from_text("two"),
        ]
    )
    block = Blockquote(children=[Paragraph.from_text("Items:"), nested_list])
    html = "<blockquote><p>Items:</p><ul><li>one<ul><li>sub</li></ul></li><li>two</li></ul></blockquote>"
    el = parse_html(html).find("blockquote")
    assert el is not None

    assert (
        write_element(block)
        == _render_blockquote(el, "mpark")
        == "> Items:\n> \n> - one\n>   - sub\n> - two"
    )


def test_blockquote_note_and_example_blocks():
    block = Blockquote(
        children=[Paragraph.from_text("Note 1"), Paragraph.from_text("Note 2")],
        role="note",
    )
    note_el = parse_html("<note-block><p>Note 1</p><p>Note 2</p></note-block>").find("note-block")
    div_el = parse_html('<div class="note"><p>Note 1</p><p>Note 2</p></div>').find("div")
    assert note_el is not None and div_el is not None

    assert (
        write_element(block)
        == _render_element(note_el, "schultke")
        == _render_div(div_el, "bikeshed")
        == "> Note 1\n> \n> Note 2"
    )


def test_empty_blockquote_renders_empty():
    el = parse_html("<blockquote></blockquote>").find("blockquote")
    assert el is not None
    assert _render_blockquote(el, "mpark") is None
    assert write_element(Blockquote()) == ""
