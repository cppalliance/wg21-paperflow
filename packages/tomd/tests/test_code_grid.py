#
# Copyright (c) 2026 Luan Fonseca (luan@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for lib.pdf.code_grid."""

from tomd.lib.pdf.types import Line, Section, SectionKind
from tomd.lib.pdf.code_grid import (
    CodeGrid,
    _estimate_char_width,
    _DEFAULT_CHAR_WIDTH,
)

from conftest import make_span


def _line(text, x0, *, monospace=True, char_w=6.0):
    """One-span line whose bbox encodes the glyph run width.

    ``x0`` is the left edge; the right edge is sized so a multi-glyph
    span measures to ``char_w`` per non-space character.
    """
    n = max(len(text.replace(" ", "")), 1)
    span = make_span(text, monospace=monospace,
                     bbox=(x0, 0.0, x0 + char_w * n, 10.0))
    return Line(spans=[span])


def _multi_span_line(spans):
    return Line(spans=spans)


class TestColumn:
    def test_origin_maps_to_zero(self):
        grid = CodeGrid(origin_x=100.0, char_w=6.0)
        assert grid.column(100.0) == 0

    def test_rounds_to_nearest_column(self):
        grid = CodeGrid(origin_x=100.0, char_w=6.0)
        assert grid.column(118.0) == 3
        assert grid.column(117.0) == 3
        assert grid.column(120.0) == 3

    def test_negative_offset_clamped_to_zero(self):
        grid = CodeGrid(origin_x=100.0, char_w=6.0)
        assert grid.column(80.0) == 0

    def test_zero_char_width_yields_zero(self):
        grid = CodeGrid(origin_x=100.0, char_w=0.0)
        assert grid.column(200.0) == 0


class TestIndent:
    def test_empty_line_has_no_indent(self):
        grid = CodeGrid(origin_x=0.0, char_w=6.0)
        assert grid.indent(Line(spans=[])) == 0

    def test_x_position_drives_indent(self):
        # First glyph 4 columns right of origin, no literal leading space.
        grid = CodeGrid(origin_x=100.0, char_w=6.0)
        line = _line("code", x0=124.0)
        assert grid.indent(line) == 4

    def test_literal_indent_used_when_it_agrees(self):
        # Literal two-space indent and x-derived column both equal 2.
        grid = CodeGrid(origin_x=100.0, char_w=6.0)
        span = make_span("  code", monospace=True,
                         bbox=(112.0, 0.0, 148.0, 10.0))
        line = _multi_span_line([span])
        assert grid.indent(line) == 2

    def test_x_position_wins_when_literal_disagrees(self):
        # Literal says 2, geometry says 5: geometry is the source of truth.
        grid = CodeGrid(origin_x=100.0, char_w=6.0)
        span = make_span("  code", monospace=True,
                         bbox=(130.0, 0.0, 166.0, 10.0))
        line = _multi_span_line([span])
        assert grid.indent(line) == 5

    def test_first_nonspace_span_selected(self):
        # Leading whitespace-only span is skipped; indent comes from the
        # first span with visible text.
        grid = CodeGrid(origin_x=100.0, char_w=6.0)
        ws = make_span("   ", monospace=True, bbox=(100.0, 0.0, 118.0, 10.0))
        code = make_span("x", monospace=True, bbox=(118.0, 0.0, 124.0, 10.0))
        line = _multi_span_line([ws, code])
        assert grid.indent(line) == 3

    def test_max_indent_pins_overflow_to_zero(self):
        # An implausibly deep indent (right-margin element split onto its
        # own line) collapses to column zero.
        grid = CodeGrid(origin_x=100.0, char_w=6.0)
        line = _line("note", x0=400.0)  # 50 columns
        assert grid.indent(line, max_indent=10) == 0

    def test_max_indent_allows_within_budget(self):
        grid = CodeGrid(origin_x=100.0, char_w=6.0)
        line = _line("code", x0=124.0)  # 4 columns
        assert grid.indent(line, max_indent=10) == 4


class TestEstimateCharWidth:
    def test_measures_from_multi_glyph_span(self):
        # "ab" spanning 12pt -> 6pt per character.
        line = _line("ab", x0=0.0, char_w=6.0)
        assert _estimate_char_width([line]) == 6.0

    def test_single_glyph_spans_fall_back_to_default(self):
        line = _line("x", x0=0.0)
        assert _estimate_char_width([line]) == _DEFAULT_CHAR_WIDTH

    def test_mono_only_skips_non_monospace_spans(self):
        serif = make_span("10", monospace=False, bbox=(0.0, 0.0, 30.0, 10.0))
        mono = make_span("code", monospace=True, bbox=(0.0, 0.0, 24.0, 10.0))
        line = _multi_span_line([serif, mono])
        # Without mono_only, the serif "10" (15pt/char) is measured first.
        assert _estimate_char_width([line]) == 15.0
        # With mono_only, the serif number is skipped; "code" -> 6pt/char.
        assert _estimate_char_width([line], mono_only=True) == 6.0


def _code_section(lines):
    return Section(kind=SectionKind.CODE, text="", lines=lines)


class TestForCodeSection:
    def test_origin_is_leftmost_content_glyph(self):
        sec = _code_section([
            _line("ab", x0=120.0),
            _line("cd", x0=100.0),
            _line("ef", x0=140.0),
        ])
        grid = CodeGrid.for_code_section(sec)
        assert grid.origin_x == 100.0
        assert grid.char_w == 6.0

    def test_blank_first_span_ignored_for_origin(self):
        blank = Line(spans=[
            make_span("", monospace=True, bbox=(50.0, 0.0, 50.0, 10.0)),
        ])
        sec = _code_section([blank, _line("ab", x0=100.0)])
        grid = CodeGrid.for_code_section(sec)
        assert grid.origin_x == 100.0

    def test_whitespace_leading_span_does_not_drop_line_from_origin(self):
        # A line whose spans[0] is whitespace-only still contributes its
        # content glyph to the origin via first_content_span(); selecting
        # spans[0] instead would skip this line and lift the origin to the
        # other line's larger x, inflating every reconstructed indent.
        ws = make_span("  ", monospace=True, bbox=(80.0, 0.0, 92.0, 10.0))
        content = make_span("ab", monospace=True,
                            bbox=(92.0, 0.0, 104.0, 10.0))
        leading_ws_line = _multi_span_line([ws, content])
        sec = _code_section([leading_ws_line, _line("cd", x0=100.0)])
        grid = CodeGrid.for_code_section(sec)
        assert grid.origin_x == 92.0

    def test_empty_section_uses_zero_origin_and_default_width(self):
        sec = _code_section([])
        grid = CodeGrid.for_code_section(sec)
        assert grid.origin_x == 0.0
        assert grid.char_w == _DEFAULT_CHAR_WIDTH

    def test_width_sampled_from_monospace_only(self):
        # A proportional (serif) leading comment must not anchor the
        # per-character pitch for the monospace code that follows: the
        # serif "10" measures 15pt/char and would corrupt every indent
        # if it were the first qualifying span. ``for_code_section``
        # now passes ``mono_only=True``, matching ``for_gutter``.
        serif = make_span(
            "10", monospace=False, bbox=(0.0, 0.0, 30.0, 10.0),
        )
        mono = make_span(
            "code", monospace=True, bbox=(0.0, 0.0, 24.0, 10.0),
        )
        sec = _code_section([_multi_span_line([serif, mono])])
        grid = CodeGrid.for_code_section(sec)
        assert grid.char_w == 6.0


class TestForGutter:
    def test_origin_is_caller_supplied(self):
        sec = _code_section([_line("ab", x0=200.0)])
        grid = CodeGrid.for_gutter(sec, origin_x=42.0)
        assert grid.origin_x == 42.0

    def test_width_sampled_from_monospace_only(self):
        serif = make_span("10", monospace=False, bbox=(0.0, 0.0, 30.0, 10.0))
        mono = make_span("code", monospace=True, bbox=(0.0, 0.0, 24.0, 10.0))
        sec = _code_section([_multi_span_line([serif, mono])])
        grid = CodeGrid.for_gutter(sec, origin_x=0.0)
        assert grid.char_w == 6.0
