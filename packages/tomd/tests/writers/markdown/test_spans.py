"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

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
from tomd.writers.markdown.spans import write_span, write_spans


def test_write_span_primitives():
    assert write_span(TextSpan("hello world")) == "hello world"
    assert write_span(CodeSpan("std::vector<int>")) == "`std::vector<int>`"
    assert write_span(CodeSpan("a ` b")) == "``a ` b``"
    assert write_span(LineBreakSpan()) == "<br>"


def test_write_span_formatting():
    assert write_span(StrongSpan.from_text("bold")) == "**bold**"
    assert write_span(EmphasisSpan.from_text("italic")) == "*italic*"
    assert write_span(StrikethroughSpan.from_text("deleted")) == "<del>deleted</del>"
    assert write_span(StrikethroughSpan.from_text("deleted"), wording_tags=False) == "~~deleted~~"
    assert write_span(UnderlineSpan.from_text("inserted")) == "<ins>inserted</ins>"
    assert write_span(UnderlineSpan.from_text("inserted"), wording_tags=False) == "<u>inserted</u>"
    assert write_span(SubscriptSpan.from_text("2")) == "<sub>2</sub>"
    assert write_span(SuperscriptSpan.from_text("3")) == "<sup>3</sup>"
    assert write_span(LinkSpan.from_text("link", "https://example.com")) == "[link](https://example.com)"
    assert (
        write_span(LinkSpan.from_text("link", "https://example.com", title="Title"))
        == '[link](https://example.com "Title")'
    )


def test_write_span_nesting_and_composition():
    nested = StrongSpan(
        children=(
            EmphasisSpan.from_text("nested"),
            TextSpan(" "),
            CodeSpan("code"),
        )
    )
    assert write_span(nested) == "***nested* `code`**"

    link = LinkSpan(children=(CodeSpan("std::span"),), url="https://isocpp.org")
    assert write_span(link) == "[`std::span`](https://isocpp.org)"


def test_write_span_whitespace_trimming_under_delimiters():
    assert write_span(StrongSpan.from_text("  trimmed  ")) == "  **trimmed**  "
    assert write_span(EmphasisSpan.from_text("  padded ")) == "  *padded* "


def test_write_spans_empty_and_fallback():
    assert write_spans([]) == ""
    assert write_spans([TextSpan("a"), TextSpan("b")]) == "ab"
    assert write_span(Span()) == ""
