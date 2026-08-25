"""Tests for lib.pdf.cleanup."""

from conftest import make_span, make_line, make_block
from tomd.lib.pdf.cleanup import (escape_leading_atx, normalize_whitespace,
                                  cleanup_text, _join_cross_page)
from tomd.lib import strip_format_chars
from tomd.lib.pdf.types import is_readable, Line, Block, Span


def test_strip_format_chars_zwsp():
    assert strip_format_chars("hello\u200bworld") == "helloworld"


def test_strip_format_chars_zwj():
    assert strip_format_chars("a\u200db") == "ab"


def test_strip_format_chars_lrm():
    assert strip_format_chars("text\u200e") == "text"


def test_strip_format_chars_soft_hyphen():
    assert strip_format_chars("imple\u00admentation") == "implementation"


def test_strip_format_chars_preserves_normal():
    assert strip_format_chars("Hello, World! 123") == "Hello, World! 123"


def test_strip_format_chars_empty():
    assert strip_format_chars("") == ""


def test_normalize_whitespace_nbsp():
    assert "\u00a0" not in normalize_whitespace("hello\u00a0world")


def test_normalize_whitespace_multi_space():
    assert "  " not in normalize_whitespace("hello   world")


def test_normalize_whitespace_trailing():
    result = normalize_whitespace("hello   \n  world  ")
    for line in result.split("\n"):
        assert line == line.rstrip()


def test_is_readable_normal():
    text = "This is a normal paragraph with enough text to pass the check."
    assert is_readable(text * 3)


def test_is_readable_too_short():
    assert not is_readable("short")


def test_is_readable_garbage():
    assert not is_readable("/" * 500)


def test_is_readable_empty():
    assert not is_readable("")


def test_cleanup_dehyphenates_joins():
    span1 = make_span("imple-")
    span2 = make_span("mentation of things")
    block = Block(lines=[Line(spans=[span1]), Line(spans=[span2])])
    result = cleanup_text([block])
    assert "implementation" in result[0].text


def test_cleanup_dehyphenates_single_span_continuation():
    span1 = make_span("imple-")
    span2 = make_span("mentation")
    block = Block(lines=[Line(spans=[span1]), Line(spans=[span2])])
    result = cleanup_text([block])
    full_text = result[0].text
    assert "implementation" in full_text
    assert "mentation" not in full_text.split("implementation")[-1]


def test_cleanup_dehyphenates_skips_compound():
    span1 = make_span("self-")
    span2 = make_span("contained")
    block = Block(lines=[Line(spans=[span1]), Line(spans=[span2])])
    result = cleanup_text([block])
    assert "self-" in result[0].text


def test_cleanup_dehyphenates_no_hyphen():
    span1 = make_span("hello")
    span2 = make_span("world")
    block = Block(lines=[Line(spans=[span1]), Line(spans=[span2])])
    result = cleanup_text([block])
    assert "hello" in result[0].text
    assert "world" in result[0].text


def test_cleanup_dehyphenates_single_span_next_line():
    """Regression: when the next line has one span entirely consumed by
    dehyphenation, the consumed word must not remain as a duplicate."""
    span1 = make_span("imple-")
    span2 = make_span("mentation")
    block = Block(lines=[Line(spans=[span1]), Line(spans=[span2])])
    result = cleanup_text([block])
    full_text = result[0].text
    assert "implementation" in full_text
    assert full_text.count("mentation") == 1, (
        f"'mentation' appears {full_text.count('mentation')} times in {full_text!r}"
    )


def test_cleanup_dehyphenates_next_line_multi_span_consumed():
    """When the next line has multiple spans and the first is fully consumed,
    remaining spans must survive."""
    span1 = make_span("imple-")
    first_consumed = make_span("mentation")
    remaining = make_span(" of things")
    block = Block(lines=[
        Line(spans=[span1]),
        Line(spans=[first_consumed, remaining]),
    ])
    result = cleanup_text([block])
    full_text = result[0].text
    assert "implementation" in full_text
    assert " of things" in full_text
    assert full_text.count("mentation") == 1


def test_cleanup_merges_cross_page():
    b1 = make_block(["Some text without terminal"], page_num=0)
    b2 = make_block(["continuation here"], page_num=1)
    result = cleanup_text([b1, b2])
    assert len(result) == 1
    assert "continuation" in result[0].text


def test_cleanup_no_merge_cross_page_with_terminal():
    b1 = make_block(["Some text with terminal."], page_num=0)
    b2 = make_block(["Next paragraph."], page_num=1)
    result = cleanup_text([b1, b2])
    assert len(result) == 2


def test_cleanup_cross_page_no_mutation():
    b1 = make_block(["Some text without terminal"], page_num=0)
    b2 = make_block(["continuation here"], page_num=1)
    original_text = b1.text
    cleanup_text([b1, b2])
    assert b1.text == original_text


def test_cleanup_text_strips_nbsp():
    block = make_block(["hello\u00a0world"])
    result = cleanup_text([block])
    assert "\u00a0" not in result[0].text


def test_cleanup_text_dehyphenates():
    span1 = make_span("imple-")
    span2 = make_span("mentation of things")
    line1 = make_line.__wrapped__ if hasattr(make_line, '__wrapped__') else None
    from tomd.lib.pdf.types import Line, Block
    l1 = Line(spans=[span1])
    l2 = Line(spans=[span2])
    block = Block(lines=[l1, l2])
    result = cleanup_text([block])
    full_text = result[0].text
    assert "implementation" in full_text


class TestEscapeLeadingAtx:
    """A body block opening on "#" must not be parsed as a heading (#302)."""

    def test_preprocessor_directive_is_escaped(self):
        text = "# include \" q-char-sequence \" new-line causes the replacement"
        assert escape_leading_atx(text) == "\\" + text

    def test_all_six_atx_levels_are_escaped(self):
        for n in range(1, 7):
            body = "#" * n + " text"
            assert escape_leading_atx(body) == "\\" + body

    def test_seven_hashes_is_not_atx(self):
        body = "####### text"
        assert escape_leading_atx(body) == body

    def test_hash_without_following_space_is_left_alone(self):
        assert escape_leading_atx("#define FOO 1") == "#define FOO 1"

    def test_bare_hash_is_escaped(self):
        assert escape_leading_atx("#") == "\\#"

    def test_interior_hash_is_left_alone(self):
        assert escape_leading_atx("see # include below") == "see # include below"

    def test_already_escaped_text_is_not_double_escaped(self):
        assert escape_leading_atx("\\# include") == "\\# include"

    def test_ordinary_prose_is_unchanged(self):
        assert escape_leading_atx("ordinary prose") == "ordinary prose"


class TestJoinCrossPage:
    def test_join_cross_page_merges_matching_paragraphs(self):
        """Unpunctuated prose ending on page 0 merges with lowercase start on page 1."""
        span1 = Span(text="This paragraph continues across", font_size=10.0, monospace=False)
        line1 = Line(spans=[span1], page_num=0)
        block1 = Block(lines=[line1], page_num=0)

        span2 = Span(text="page boundaries smoothly.", font_size=10.0, monospace=False)
        line2 = Line(spans=[span2], page_num=1)
        block2 = Block(lines=[line2], page_num=1)

        result = _join_cross_page([block1, block2])
        assert len(result) == 1
        assert len(result[0].lines) == 2
        assert result[0].text == "This paragraph continues across\npage boundaries smoothly."

    def test_join_cross_page_does_not_merge_prose_with_monospace_code(self):
        """Prose on page 0 does not merge with monospace code on page 1."""
        span1 = Span(text="Here is some code", font_size=10.0, monospace=False)
        line1 = Line(spans=[span1], page_num=0)
        block1 = Block(lines=[line1], page_num=0)

        span2 = Span(text="template <class T>", font_size=10.0, monospace=True)
        line2 = Line(spans=[span2], page_num=1)
        block2 = Block(lines=[line2], page_num=1)

        result = _join_cross_page([block1, block2])
        assert len(result) == 2
        assert result[0].text == "Here is some code"
        assert result[1].text == "template <class T>"

    def test_join_cross_page_does_not_merge_divergent_font_sizes(self):
        """Footnote (small font) on page 0 does not merge with body text on page 1."""
        span1 = Span(text="2 footnote text without punctuation", font_size=8.0, monospace=False)
        line1 = Line(spans=[span1], page_num=0)
        block1 = Block(lines=[line1], page_num=0)

        span2 = Span(text="and then the next page body continues.", font_size=11.0, monospace=False)
        line2 = Line(spans=[span2], page_num=1)
        block2 = Block(lines=[line2], page_num=1)

        result = _join_cross_page([block1, block2])
        assert len(result) == 2

    def test_join_cross_page_does_not_merge_monospace_code_blocks(self):
        """Code block on page 0 does not merge with code block on page 1."""
        span1 = Span(text="int x = 42;", font_size=10.0, monospace=True)
        line1 = Line(spans=[span1], page_num=0)
        block1 = Block(lines=[line1], page_num=0)

        span2 = Span(text="return x;", font_size=10.0, monospace=True)
        line2 = Line(spans=[span2], page_num=1)
        block2 = Block(lines=[line2], page_num=1)

        result = _join_cross_page([block1, block2])
        assert len(result) == 2
        assert result[0].text == "int x = 42;"
        assert result[1].text == "return x;"


