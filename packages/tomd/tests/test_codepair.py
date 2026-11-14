"""Tests for lib.pdf.codepair block bridging."""

from tomd.lib.pdf.codepair import _bridged
from tomd.lib.pdf.types import Line, Span

_H = 9.0


def _line(x0, y0, text="f(x);", mono=True, width=150.0):
    bbox = (x0, y0, x0 + width, y0 + _H)
    return Line(spans=[Span(text=text, monospace=mono, bbox=bbox)], bbox=bbox, page_num=0)


def _boxes(blocks):
    return sorted((round(min(ln.bbox[1] for ln in b)), round(max(ln.bbox[3] for ln in b)), len(b))
                  for b in blocks)


def test_a_gap_in_one_column_is_bridged_by_the_column_beside_it():
    left_top = [_line(60, 100), _line(60, 111)]
    left_bottom = [_line(60, 160), _line(60, 171)]
    right = [_line(300, y) for y in range(100, 182, 11)]
    out = _bridged([left_top, left_bottom, right], rest=[])
    assert _boxes(out) == [(100, 180, 4), (100, 186, 8)]


def test_staggered_gaps_in_both_columns_are_bridged():
    # the right column ends a line before the left one resumes, and the reverse
    left = [[_line(60, 100), _line(60, 111)], [_line(60, 170), _line(60, 181), _line(60, 192)]]
    right = [[_line(300, 100), _line(300, 111), _line(300, 122), _line(300, 133), _line(300, 144), _line(300, 155)],
             [_line(300, 200), _line(300, 211)]]
    out = _bridged(left + right, rest=[])
    assert len(out) == 2


def test_text_in_the_gap_keeps_the_blocks_apart():
    left_top = [_line(60, 100), _line(60, 111)]
    left_bottom = [_line(60, 160), _line(60, 171)]
    right = [_line(300, y) for y in range(100, 182, 11)]
    caption = _line(60, 140, text="Figure 1: before", mono=False, width=100)
    out = _bridged([left_top, left_bottom, right], rest=[caption])
    assert len(out) == 3


def test_a_drawn_rule_in_the_gap_keeps_the_blocks_apart():
    left_top = [_line(60, 100), _line(60, 111)]
    left_bottom = [_line(60, 160), _line(60, 171)]
    right = [_line(300, y) for y in range(100, 182, 11)]
    out = _bridged([left_top, left_bottom, right], rest=[], rules=[(140.0, 50.0, 520.0)])
    assert len(out) == 3


def test_a_lone_column_is_not_bridged():
    out = _bridged([[_line(60, 100), _line(60, 111)], [_line(60, 160), _line(60, 171)]], rest=[])
    assert len(out) == 2


def test_a_block_beside_that_starts_at_the_gap_does_not_bridge_it():
    # two snippets on the left, one on the right set between them: rows, not one cell
    left = [[_line(60, 100), _line(60, 111), _line(60, 122)], [_line(60, 168), _line(60, 179)]]
    right = [[_line(300, 134), _line(300, 145), _line(300, 156)]]
    out = _bridged(left + right, rest=[])
    assert len(out) == 3


def test_blocks_split_without_a_gap_are_not_bridged():
    # a dedented closing line right under its block is not this rule's business
    left = [[_line(80, 100), _line(80, 111)], [_line(60, 122, text="}", width=5)]]
    right = [[_line(300, y) for y in range(90, 140, 11)]]
    out = _bridged(left + right, rest=[])
    assert len(out) == 3


def test_a_dedented_closing_line_joins_the_block_above_it():
    from tomd.lib.pdf.codepair import _blocks
    lines = [_line(60, 100, "int main() {"), _line(80, 111, "f(x);", width=60), _line(60, 122, "}", width=5)]
    assert [len(b) for b in _blocks(lines)] == [3]
