"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from tomd.domain.elements import (
    Blockquote,
    CodeBlock,
    Heading,
    ImageElement,
    ListBlock,
    ListItem,
    Paragraph,
    ThematicBreak,
    UncertainElement,
    WordingBlock,
)
from tomd.domain.span import CodeSpan, TextSpan
from tomd.writers.markdown.blocks import write_element


def test_write_heading():
    h1 = Heading.from_text(1, "Introduction")
    assert write_element(h1) == "# Introduction"

    h2 = Heading.from_text(2, "Scope and Design", id="scope.design")
    assert write_element(h2) == "## Scope and Design {#scope.design}"

    h_deep = Heading.from_text(10, "Deep Subheading")
    assert write_element(h_deep) == "###### Deep Subheading"

    h_zero = Heading.from_text(0, "Zero Level")
    assert write_element(h_zero) == "# Zero Level"


def test_write_paragraph():
    p1 = Paragraph.from_text("This is simple prose.")
    assert write_element(p1) == "This is simple prose."

    p2 = Paragraph(spans=[TextSpan("See "), CodeSpan("std::format"), TextSpan(".")])
    assert write_element(p2) == "See `std::format`."


def test_write_code_block():
    cb1 = CodeBlock(code="int main() {\n    return 0;\n}", language="cpp")
    expected1 = "```cpp\nint main() {\n    return 0;\n}\n```"
    assert write_element(cb1) == expected1

    cb2 = CodeBlock(code="x = 1", language="python", title="example.py")
    expected2 = '```python title="example.py"\nx = 1\n```'
    assert write_element(cb2) == expected2

    cb_fenced = CodeBlock(code="```\nembedded fence\n```", language="markdown")
    assert write_element(cb_fenced).startswith("````markdown")
    assert write_element(cb_fenced).endswith("````")


def test_write_list_block_unordered_and_ordered():
    ul = ListBlock(
        items=[ListItem.from_text("item 1"), ListItem.from_text("item 2")],
        ordered=False,
    )
    assert write_element(ul) == "- item 1\n- item 2"

    ol = ListBlock(
        items=[ListItem.from_text("first"), ListItem.from_text("second")],
        ordered=True,
    )
    assert write_element(ol) == "1. first\n2. second"


def test_write_blockquote():
    bq1 = Blockquote.from_text("Single line note.")
    assert write_element(bq1) == "> Single line note."

    bq2 = Blockquote.from_text("Line 1\nLine 2")
    assert write_element(bq2) == "> Line 1\n> Line 2"


def test_write_thematic_break():
    assert write_element(ThematicBreak()) == "---"


def test_write_wording_block():
    wb = WordingBlock(role="wording", text="Modify [format.string] as follows:")
    assert write_element(wb) == "Modify [format.string] as follows:"


def test_write_image_element():
    img1 = ImageElement(
        caption="Architecture Diagram",
        alt="System Diagram",
        stored_filename="images/fig1.png",
    )
    assert write_element(img1) == "![System Diagram](images/fig1.png)\n\n*Architecture Diagram*"

    img2 = ImageElement(
        caption="Same",
        alt="Same",
        stored_filename="images/fig2.png",
    )
    assert write_element(img2) == "![Same](images/fig2.png)"


def test_write_uncertain_element():
    unc = UncertainElement(prompt="Verify math formula", raw_content="$$E=mc^2$$")
    assert write_element(unc) == '<!-- tomd:uncertain prompt="Verify math formula" -->\n$$E=mc^2$$'
