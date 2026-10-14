#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for HTML heading outline extraction."""

from whisker.llm.html_outline import (
    extract_heading_outline,
    extract_section_units,
    format_outline,
)


class TestExtractHeadingOutline:
    def test_basic_headings(self):
        html = "<h1>Title</h1><h2>Abstract</h2><h2>Motivation</h2><h3>Background</h3>"
        result = extract_heading_outline(html)
        assert result == [("h1", "Title"), ("h2", "Abstract"), ("h2", "Motivation"), ("h3", "Background")]

    def test_empty_html(self):
        assert extract_heading_outline("") == []

    def test_no_headings(self):
        assert extract_heading_outline("<p>Just a paragraph</p>") == []

    def test_nested_tags_in_heading(self):
        html = '<h2><a href="#ref">References</a></h2>'
        result = extract_heading_outline(html)
        assert result == [("h2", "References")]

    def test_heading_with_whitespace(self):
        html = "<h2>  Some   Heading  </h2>"
        result = extract_heading_outline(html)
        assert result == [("h2", "Some Heading")]

    def test_empty_heading_skipped(self):
        html = "<h2></h2><h3>Real Heading</h3>"
        result = extract_heading_outline(html)
        assert result == [("h3", "Real Heading")]

    def test_all_heading_levels(self):
        html = "".join(f"<h{i}>H{i}</h{i}>" for i in range(1, 7))
        result = extract_heading_outline(html)
        assert len(result) == 6
        assert result[0] == ("h1", "H1")
        assert result[5] == ("h6", "H6")


class TestFormatOutline:
    def test_basic_format(self):
        headings = [("h1", "Title"), ("h2", "Abstract")]
        result = format_outline(headings)
        assert "Source HTML heading outline:" in result
        assert "- h1: Title" in result
        assert "- h2: Abstract" in result

    def test_empty_returns_empty(self):
        assert format_outline([]) == ""

    def test_long_text_truncated(self):
        headings = [("h2", "A" * 200)]
        result = format_outline(headings)
        assert "..." in result
        assert len(result.split("\n")[1]) < 150


class TestExtractSectionUnits:
    def test_inline_code_is_not_counted_as_block_code(self):
        inline_code = " ".join(f"<code>name{index}</code>" for index in range(20))
        units = extract_section_units(f"<h2>Wording</h2><p>{inline_code}</p>")

        assert units[0].code_blocks == 0

    def test_nested_pre_code_is_counted_once(self):
        units = extract_section_units(
            "<h2>Example</h2><pre><code>constexpr int value = 1;</code></pre>"
        )

        assert units[0].code_blocks == 1
