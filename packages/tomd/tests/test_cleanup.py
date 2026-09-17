"""Tests for lib.pdf.cleanup."""

import pytest

from conftest import make_span, make_line, make_block
from tomd.lib.pdf.cleanup import (escape_leading_atx, normalize_whitespace,
                                  cleanup_text, _join_cross_page,
                                  collect_hyphen_evidence, dehyphenate_pair)
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


# (wrapped lines of the block under test, evidence lines elsewhere in the
#  document, expected block lines after T9) - issue #413 compound-aware
#  dehyphenation. Evidence decides before form; form decides before the
#  default glue.
_DEHYPHENATION_CASES = [
    pytest.param(
        ["imple-", "mentation of things"], [],
        ["implementation", "of things"], id="syllable-default-glue"),
    pytest.param(
        ["a SIMD-", "friendly layout"], [],
        ["a SIMD-friendly", "layout"], id="acronym-prefix-keeps"),
    pytest.param(
        ["needs 64-", "bit lanes"], [],
        ["needs 64-bit", "lanes"], id="digit-prefix-keeps"),
    pytest.param(
        ["is non-", "associative here"], [],
        ["is non-associative", "here"], id="compound-prefix-keeps-and-pulls-up"),
    pytest.param(
        ["the re-", "sult is"], ["the result was clear"],
        ["the result", "is"], id="glued-seen-beats-prefix"),
    pytest.param(
        ["a floating-", "point value"], ["every floating-point type"],
        ["a floating-point", "value"], id="compound-seen-keeps"),
    pytest.param(
        ["a floating-", "point value"], ["floating values", "the point is"],
        ["a floating-point", "value"], id="both-standalone-keeps"),
    pytest.param(
        ["a cache-", "friendly walk"], ["a debugger-friendly comparator"],
        ["a cache-friendly", "walk"], id="tail-of-other-compound-keeps"),
    pytest.param(
        ["build-", "proof output"], [],
        ["buildproof", "output"], id="no-evidence-glues-known-residue"),
    pytest.param(
        ["a non-", "Associative op"], [],
        ["a non-", "Associative op"], id="uppercase-next-word-untouched"),
    pytest.param(
        ["see figure -", "and table"], [],
        ["see figure -", "and table"], id="bare-dash-untouched"),
    pytest.param(
        ["(non-", "associative)"], [],
        ["(non-associative)"], id="punctuation-around-keys-ignored"),
    pytest.param(
        ["imple-", "mentation"], [],
        ["implementation"], id="fully-consumed-next-line-dropped"),
    pytest.param(
        ["and how-", "ever it goes"], ["however, the rule"],
        ["and however", "it goes"], id="glued-seen-beats-both-standalone"),
    pytest.param(
        ["-?-", "simd-arg subsumes"], [],
        ["-?simd-arg", "subsumes"], id="no-alnum-prefix-glues-as-before"),
]


_MONO_CASES = [
    pytest.param(
        ["satisfies convertible_-", "to<value_type>"], [],
        ["satisfies convertible_to<value_type>"], id="identifier-break-glues"),
    pytest.param(
        ["concept simd-consteval-", "broadcast-arg = see below;"],
        ["simd-consteval-broadcast-arg subsumes"],
        ["concept simd-consteval-broadcast-arg", "= see below;"],
        id="attested-identifier-keeps"),
    pytest.param(
        ["a SIMD-", "friendly layout"], [],
        ["a SIMDfriendly", "layout"], id="form-rules-do-not-apply-in-code"),
]


@pytest.mark.parametrize(("wrapped", "evidence", "expected"), _MONO_CASES)
def test_cleanup_dehyphenation_monospace(wrapped, evidence, expected):
    block = make_block(wrapped, monospace=True)
    others = [make_block([ln], monospace=True) for ln in evidence]
    result = cleanup_text(others + [block])
    assert [ln.text for ln in result[-1].lines] == expected


def test_cleanup_dehyphenation_tolerates_span_edge_whitespace():
    """MuPDF leaves a trailing space on line-end spans; it is not content."""
    block = Block(lines=[
        Line(spans=[make_span("a floating- ")]),
        Line(spans=[make_span(" point value")]),
    ])
    result = cleanup_text([make_block(["floating-point math"]), block])
    assert [ln.text for ln in result[-1].lines] == ["a floating-point", "value"]


def test_collect_hyphen_evidence_code_lines_give_compounds_only():
    lines = [make_line(["x = some_time - n-1"], monospace=True),
             make_line(["concept simd-arg = true;"], monospace=True)]
    ev = collect_hyphen_evidence(lines)
    assert ev.words == frozenset()
    assert ev.tails == frozenset()
    assert "simd-arg" in ev.compounds


def test_cleanup_dehyphenation_font_change_is_not_a_wrap():
    """Prose ``over-`` running into a code line keeps both lines intact."""
    block = Block(lines=[
        Line(spans=[make_span("functions form an over-")]),
        Line(spans=[make_span("int ilogb(float arg)", monospace=True)]),
    ])
    result = cleanup_text([block])
    assert [ln.text for ln in result[0].lines] == [
        "functions form an over-", "int ilogb(float arg)"]


@pytest.mark.parametrize(("wrapped", "evidence", "expected"), _DEHYPHENATION_CASES)
def test_cleanup_dehyphenation_rules(wrapped, evidence, expected):
    block = make_block(wrapped)
    others = [make_block([ln]) for ln in evidence]
    result = cleanup_text(others + [block])
    assert [ln.text for ln in result[-1].lines] == expected


def test_collect_hyphen_evidence_excludes_wrap_fragments():
    lines = [make_line(["the imple-"]), make_line(["mentation is non-associative"])]
    ev = collect_hyphen_evidence(lines)
    assert "imple" not in ev.words
    assert "mentation" not in ev.words
    assert {"the", "is"} <= ev.words
    assert "non-associative" in ev.compounds
    assert "associative" in ev.tails


def test_dehyphenate_pair_reports_tokens_for_text_patching():
    ev = collect_hyphen_evidence([])
    pair = dehyphenate_pair(make_line(["is non-"]), make_line(["associative,", " said"]), ev)
    assert pair is not None
    assert (pair.prefix_token, pair.first_word, pair.joined) == (
        "non-", "associative,", "non-associative,")
    assert pair.last_line.text == "is non-associative,"
    assert pair.next_line is not None and pair.next_line.text == " said"


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

    def test_join_cross_page_does_not_merge_prev_monospace_cur_prose(self):
        """Monospace code block on page 0 does not merge with lowercase prose on page 1."""
        span1 = Span(text="int x = 42;", font_size=10.0, monospace=True)
        line1 = Line(spans=[span1], page_num=0)
        block1 = Block(lines=[line1], page_num=0)

        span2 = Span(text="and this is prose that starts lowercase.", font_size=10.0, monospace=False)
        line2 = Line(spans=[span2], page_num=1)
        block2 = Block(lines=[line2], page_num=1)

        result = _join_cross_page([block1, block2])
        assert len(result) == 2

    def test_join_cross_page_does_not_merge_prev_prose_cur_monospace(self):
        """Unclosed prose on page 0 does not merge with lowercase monospace code on page 1."""
        span1 = Span(text="This prose ends without punctuation", font_size=10.0, monospace=False)
        line1 = Line(spans=[span1], page_num=0)
        block1 = Block(lines=[line1], page_num=0)

        span2 = Span(text="return x;", font_size=10.0, monospace=True)
        line2 = Line(spans=[span2], page_num=1)
        block2 = Block(lines=[line2], page_num=1)

        result = _join_cross_page([block1, block2])
        assert len(result) == 2

    def test_join_cross_page_does_not_merge_monospace_blocks_with_blank_padding(self):
        """Monospace blocks padded with blank lines do not bypass the monospace gate."""
        span1 = Span(text="int x = 42;", font_size=10.0, monospace=True)
        line1 = Line(spans=[span1], page_num=0)
        pad1 = Line(spans=[Span(text="   ", font_size=10.0, monospace=False)], page_num=0)
        block1 = Block(lines=[line1, pad1], page_num=0)

        pad2 = Line(spans=[Span(text="", font_size=10.0, monospace=False)], page_num=1)
        span2 = Span(text="return x;", font_size=10.0, monospace=True)
        line2 = Line(spans=[span2], page_num=1)
        block2 = Block(lines=[pad2, line2], page_num=1)

        result = _join_cross_page([block1, block2])
        assert len(result) == 2



