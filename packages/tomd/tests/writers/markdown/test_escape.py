"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

import pytest

from tomd.domain.elements import Heading, Paragraph, RawBlock
from tomd.domain.span import EmphasisSpan, StrongSpan, TextSpan
from tomd.domain.table import Table, TableRow, TextCell
from tomd.writers.markdown.blocks import write_element
from tomd.writers.markdown.escape import (
    escape_italic_wrapper,
    escape_leading_atx,
    escape_pipe_in_cell,
    escape_wording_angle_brackets,
)
from tomd.writers.markdown.tables import write_table


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("# heading", r"\# heading"),
        ("## h2", r"\## h2"),
        ("### h3", r"\### h3"),
        ("#### h4", r"\#### h4"),
        ("##### h5", r"\##### h5"),
        ("###### h6", r"\###### h6"),
        ("####### seven hashes", "####### seven hashes"),
        ("#", r"\#"),
        ("###", r"\###"),
        ("#\twith tab", "\\#\twith tab"),
        ("#define FOO 1", "#define FOO 1"),
        ("#include <vector>", "#include <vector>"),
        ('# include "q-char-sequence"', r'\# include "q-char-sequence"'),
        ("see # include below", "see # include below"),
        (r"\# include", r"\# include"),
        ("ordinary prose", "ordinary prose"),
        ("", ""),
    ],
)
def test_escape_leading_atx_table(raw: str, expected: str):
    assert escape_leading_atx(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", ""),
        ("plain caption text", "plain caption text"),
        ("a * b", r"a \* b"),
        ("foo_bar", r"foo\_bar"),
        ("code `x` here", r"code \`x\` here"),
        ("path\\to\\file", r"path\\to\\file"),
        ("- a list looking line", r"\- a list looking line"),
        ("* asterisk first", r"\* asterisk first"),
        ("+ plus first", r"\+ plus first"),
        ("> quoted thing", r"\> quoted thing"),
        ("# heading-shaped", r"\# heading-shaped"),
        ("1. first item", r"1\. first item"),
        ("42. answer", r"42\. answer"),
        ("v1. not ordered list", "v1. not ordered list"),
        ("*_\\`", r"\*\_\\\`"),
    ],
)
def test_escape_italic_wrapper_table(raw: str, expected: str):
    assert escape_italic_wrapper(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", ""),
        ("plain cell", "plain cell"),
        ("a | b", r"a \| b"),
        ("a || b", r"a \|\| b"),
        ("|leading and trailing|", r"\|leading and trailing\|"),
        (r"already \| escaped", r"already \\| escaped"),
    ],
)
def test_escape_pipe_in_cell_table(raw: str, expected: str):
    assert escape_pipe_in_cell(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", ""),
        ("plain text", "plain text"),
        ("vec<float>", "vec&lt;float&gt;"),
        ("a & b < c > d", "a &amp; b &lt; c &gt; d"),
        ("&already;", "&amp;already;"),
        ("template<class T, class U = std::less<T>>", "template&lt;class T, class U = std::less&lt;T&gt;&gt;"),
    ],
)
def test_escape_wording_angle_brackets_table(raw: str, expected: str):
    assert escape_wording_angle_brackets(raw) == expected


def test_writer_plain_prose_leaves_markdown_chars_untouched():
    p = Paragraph(
        spans=[
            TextSpan("Prose with * and _ and <T> and "),
            EmphasisSpan(children=(TextSpan("em_text <U>"),)),
            TextSpan(" and "),
            StrongSpan(children=(TextSpan("bold*text"),)),
        ]
    )
    assert write_element(p) == "Prose with * and _ and <T> and *em_text <U>* and **bold*text**"

    h = Heading(
        level=2,
        spans=[
            TextSpan("Section with foo_bar, a * b, and std::vector<int> "),
            EmphasisSpan(children=(TextSpan("italic_part"),)),
        ],
    )
    assert write_element(h) == "## Section with foo_bar, a * b, and std::vector<int> *italic_part*"


def test_writer_paragraph_escapes_leading_atx():
    p = Paragraph.from_text("# heading-like paragraph")
    assert write_element(p) == r"\# heading-like paragraph"


def test_writer_heading_starting_with_hash_not_double_escaped():
    h = Heading.from_text(2, "# already hashed title")
    assert write_element(h) == "## # already hashed title"


def test_writer_table_caption_is_escaped():
    table = Table(
        headers=[TextCell.from_text("Col")],
        rows=[TableRow(cells=[TextCell.from_text("Val")])],
        caption="Figure 1: foo_bar * `code`",
    )
    rendered = write_table(table)
    assert rendered.endswith("\n\n*Figure 1: foo\\_bar \\* \\`code\\`*")


def test_writer_raw_block_round_trips_bytes():
    raw_md = "Line 1 with trailing spaces   \n\nLine 3 with *raw* `markdown` | pipes\n\n\nLine 6  "
    block = RawBlock(markdown=raw_md, origin="pdf")
    assert block.text == raw_md
    assert write_element(block) == raw_md
