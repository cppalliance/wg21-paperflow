"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from markdown_it import MarkdownIt

from tomd.domain.elements import CodeBlock, ListBlock, ListItem, Paragraph
from tomd.domain.span import TextSpan
from tomd.lib.html.extract import parse_html
from tomd.lib.html.render import _render_list
from tomd.lib.pdf.emit import _render_list_spans
from tomd.lib.pdf.types import Line, Section, SectionKind, Span
from tomd.writers.markdown.blocks import write_element

_COMMONMARK = MarkdownIt("commonmark")


def test_flat_bullets():
    block = ListBlock(items=[ListItem.from_text("a"), ListItem.from_text("b")])
    legacy = _render_list(parse_html("<ul><li>a</li><li>b</li></ul>").find("ul"), "-", "mpark")

    assert write_element(block) == legacy == "- a\n- b"


def test_ordered_from_1():
    block = ListBlock(items=[ListItem.from_text("a"), ListItem.from_text("b")], ordered=True)
    legacy = _render_list(parse_html("<ol><li>a</li><li>b</li></ol>").find("ol"), "1.", "mpark")

    assert write_element(block) == legacy == "1. a\n2. b"


def test_nested_two_levels():
    block = ListBlock(
        items=[
            ListItem(spans=[TextSpan("a")], children=[ListBlock(items=[ListItem.from_text("b")])]),
        ],
    )
    legacy = _render_list(
        parse_html("<ul><li>a<ul><li>b</li></ul></li></ul>").find("ul"), "-", "mpark"
    )

    assert write_element(block) == legacy == "- a\n  - b"


def test_nested_three_levels_under_ordered():
    innermost = ListBlock(items=[ListItem.from_text("c")])
    middle = ListBlock(items=[ListItem(spans=[TextSpan("b")], children=[innermost])])
    block = ListBlock(items=[ListItem(spans=[TextSpan("a")], children=[middle])], ordered=True)
    legacy = _render_list(
        parse_html("<ol><li>a<ul><li>b<ul><li>c</li></ul></li></ul></li></ol>").find("ol"),
        "1.",
        "mpark",
    )

    markdown = write_element(block)

    assert markdown == legacy == "1. a\n   - b\n     - c"
    assert _COMMONMARK.render(markdown).replace("\n", "") == (
        "<ol><li>a<ul><li>b<ul><li>c</li></ul></li></ul></li></ol>"
    )


def test_continuation_paragraph():
    block = ListBlock(
        items=[
            ListItem(spans=[TextSpan("a")], children=[Paragraph.from_text("b")]),
            ListItem.from_text("c"),
        ],
    )
    legacy = _render_list(
        parse_html("<ul><li><p>a</p><p>b</p></li><li>c</li></ul>").find("ul"), "-", "mpark"
    )

    markdown = write_element(block)

    assert markdown == legacy == "- a\n\n  b\n- c"
    assert _COMMONMARK.render(markdown).replace("\n", "") == (
        "<ul><li><p>a</p><p>b</p></li><li><p>c</p></li></ul>"
    )


def test_fenced_code_child():
    block = ListBlock(items=[ListItem(spans=[TextSpan("a")], children=[CodeBlock(code="code")])])
    legacy = _render_list(parse_html("<ul><li>a<pre>code</pre></li></ul>").find("ul"), "-", "mpark")

    assert write_element(block) == legacy == "- a\n\n  ```cpp\n  code\n  ```"


def test_code_child_after_nested_list_gets_a_blank_line():
    block = ListBlock(
        items=[
            ListItem(
                spans=[TextSpan("a")],
                children=[ListBlock(items=[ListItem.from_text("b")]), CodeBlock(code="c")],
            ),
        ],
    )
    legacy = _render_list(
        parse_html("<ul><li>a<ul><li>b</li></ul><pre>c</pre></li></ul>").find("ul"), "-", "mpark"
    )

    markdown = write_element(block)

    assert markdown == legacy == "- a\n  - b\n\n  ```cpp\n  c\n  ```"
    assert _COMMONMARK.render(markdown).replace("\n", "") == (
        '<ul><li><p>a</p><ul><li>b</li></ul><pre><code class="language-cpp">c</code></pre></li></ul>'
    )


def test_labelless_item_first_child_follows_bare_marker():
    block = ListBlock(
        items=[ListItem(children=[CodeBlock(code="code"), Paragraph.from_text("after")])],
    )
    legacy = _render_list(
        parse_html("<ul><li><pre>code</pre><p>after</p></li></ul>").find("ul"), "-", "mpark"
    )

    markdown = write_element(block)

    assert markdown == legacy == "-\n  ```cpp\n  code\n  ```\n\n  after"
    assert _COMMONMARK.render(markdown).replace("\n", "") == (
        '<ul><li><pre><code class="language-cpp">code</code></pre><p>after</p></li></ul>'
    )


def test_continuation_indent_tracks_marker_width():
    block = ListBlock(
        items=[
            *[ListItem.from_text("x") for _ in range(9)],
            ListItem(spans=[TextSpan("t")], children=[Paragraph.from_text("more")]),
        ],
        ordered=True,
    )
    html = "<ol>" + "<li>x</li>" * 9 + "<li><p>t</p><p>more</p></li></ol>"
    legacy = _render_list(parse_html(html).find("ol"), "1.", "mpark")

    expected = "".join(f"{n}. x\n" for n in range(1, 10)) + "10. t\n\n    more"
    assert write_element(block) == legacy == expected


def test_empty_item_is_skipped_but_numbering_advances():
    block = ListBlock(items=[ListItem(), ListItem.from_text("b")], ordered=True)
    legacy = _render_list(parse_html("<ol><li></li><li>b</li></ol>").find("ol"), "1.", "mpark")

    assert write_element(block) == legacy == "2. b"


def test_blank_line_inside_child_is_padded_like_legacy():
    block = ListBlock(items=[ListItem(spans=[TextSpan("a")], children=[CodeBlock(code="x\n\ny")])])
    legacy = _render_list(
        parse_html("<ul><li>a<pre>x\n\ny</pre></li></ul>").find("ul"), "-", "mpark"
    )

    assert write_element(block) == legacy == "- a\n\n  ```cpp\n  x\n  \n  y\n  ```"


def test_pdf_bullet_glyphs():
    block = ListBlock(items=[ListItem.from_text("a"), ListItem.from_text("b")])
    section = Section(
        kind=SectionKind.LIST,
        text="● a\n○ b",
        lines=[Line(spans=[Span("● a")]), Line(spans=[Span("○ b")])],
    )

    assert write_element(block) == _render_list_spans(section) == "- a\n- b"


def test_pdf_ordinals_starting_at_5():
    block = ListBlock(items=[ListItem.from_text("a"), ListItem.from_text("b")], ordered=True, start=5)
    section = Section(
        kind=SectionKind.LIST,
        text="5. a\n6. b",
        lines=[Line(spans=[Span("5. a")]), Line(spans=[Span("6. b")])],
    )

    markdown = write_element(block)

    assert markdown == _render_list_spans(section) == "5. a\n6. b"
    assert _COMMONMARK.render(markdown).replace("\n", "") == '<ol start="5"><li>a</li><li>b</li></ol>'


def test_pdf_preserved_markers():
    block = ListBlock(
        items=[
            ListItem(spans=[TextSpan("x")], marker="b)"),
            ListItem(spans=[TextSpan("y")], marker="(c)"),
        ],
        ordered=True,
    )
    section = Section(
        kind=SectionKind.LIST,
        text="b) x\n(c) y",
        lines=[Line(spans=[Span("b) x")]), Line(spans=[Span("(c) y")])],
    )

    assert write_element(block) == _render_list_spans(section) == "b) x\n(c) y"


def test_pdf_bullet_then_ordinal_in_one_section():
    block = ListBlock(
        items=[ListItem.from_text("done."), ListItem(spans=[TextSpan("c")], marker="b)")],
    )
    section = Section(
        kind=SectionKind.LIST,
        text="● done.\nb) c",
        lines=[Line(spans=[Span("● done.")]), Line(spans=[Span("b) c")])],
    )

    assert write_element(block) == _render_list_spans(section) == "- done.\nb) c"


def test_preserved_marker_consumes_its_ordinal_slot():
    # No legacy equivalent: legacy never mixes preserved and generated ordinals.
    block = ListBlock(
        items=[
            ListItem.from_text("a"),
            ListItem(spans=[TextSpan("b")], marker="x)"),
            ListItem.from_text("c"),
        ],
        ordered=True,
        start=7,
    )

    assert write_element(block) == "7. a\nx) b\n9. c"


def test_multiline_label_aligns_continuation_to_marker_width():
    # No legacy equivalent: legacy flattens every label to one line.
    block = ListBlock(
        items=[ListItem.from_text("first\nsecond"), ListItem.from_text("third")],
        ordered=True,
    )

    assert write_element(block) == "1. first\n   second\n2. third"
