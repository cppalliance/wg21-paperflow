# Copyright (c) 2026 C++ Alliance, Inc. (https://cppalliance.org)
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""Unit tests for new table detection passes added in PR #109."""

from tomd.lib.pdf.types import Span, Line, Block
from tomd.lib.pdf.table import (
    _gap_asymmetry_reject,
    _block_horizontal_row_relaxed,
    _try_wrapped_partial_row,
)


def _line(text: str, x0: float, y0: float, x1: float, y1: float) -> Line:
    """Create a Line with explicit bbox."""
    return Line(
        spans=[Span(text=text, font_size=10.0)],
        bbox=(x0, y0, x1, y1),
    )


def _block_from_lines(lines: list[Line]) -> Block:
    """Create a Block from pre-built lines."""
    return Block(lines=lines, page_num=0)


class TestGapAsymmetryReject:
    """Tests for _gap_asymmetry_reject: filters false-positive table rows."""

    def test_fewer_than_3_lines_accepted(self):
        lines = [
            _line("A", 10, 100, 50, 110),
            _line("B", 100, 100, 150, 110),
        ]
        assert not _gap_asymmetry_reject(lines)

    def test_uniform_gaps_accepted(self):
        """Three cells with roughly equal spacing should pass."""
        lines = [
            _line("Col1", 10, 100, 60, 110),
            _line("Col2", 80, 100, 130, 110),
            _line("Col3", 150, 100, 200, 110),
        ]
        assert not _gap_asymmetry_reject(lines)

    def test_extreme_gap_asymmetry_rejected(self):
        """WG21 heading pattern: '4  General  [general]' with wildly uneven gaps."""
        lines = [
            _line("4", 72, 100, 82, 110),
            _line("General", 120, 100, 180, 110),
            _line("[general]", 400, 100, 470, 110),
        ]
        assert _gap_asymmetry_reject(lines)

    def test_moderate_gap_extreme_width_3cells_rejected(self):
        """Reference list pattern: tiny marker + long description.

        Gap between cell 1-2 = 5, gap between cell 2-3 = 20, ratio = 4.0 (> 3).
        Width of cell 1 = 23, cell 2 = 10, cell 3 = 380, ratio = 38 (> 10).
        """
        lines = [
            _line("(1.1)", 72, 100, 95, 110),
            _line("—", 100, 100, 110, 110),
            _line("IEC Electropedia: Very long description text", 130, 100, 510, 110),
        ]
        assert _gap_asymmetry_reject(lines)

    def test_4plus_cells_uniform_gaps_accepted(self):
        """4 cells with roughly uniform gaps should pass (real table)."""
        lines = [
            _line("A", 10, 100, 50, 110),
            _line("B", 70, 100, 110, 110),
            _line("C", 130, 100, 170, 110),
            _line("D", 190, 100, 230, 110),
        ]
        assert not _gap_asymmetry_reject(lines)

    def test_overlapping_gaps_not_counted(self):
        """When gaps are negative (overlapping), fewer than 2 positive gaps -> accept."""
        lines = [
            _line("A", 10, 100, 60, 110),
            _line("B", 50, 100, 110, 110),
            _line("C", 120, 100, 170, 110),
        ]
        assert not _gap_asymmetry_reject(lines)


class TestBlockHorizontalRowRelaxed:
    """Tests for _block_horizontal_row_relaxed: relaxed row detection."""

    def test_returns_none_below_min_cells(self):
        block = _block_from_lines([
            _line("Only one", 10, 100, 100, 110),
        ])
        assert _block_horizontal_row_relaxed(block, min_cells=2) is None

    def test_horizontal_row_detected(self):
        """Two cells on the same y-band should be detected."""
        block = _block_from_lines([
            _line("Col1", 10, 100, 60, 110),
            _line("Col2", 100, 100, 160, 110),
        ])
        result = _block_horizontal_row_relaxed(block, min_cells=2)
        assert result is not None
        assert len(result) == 2

    def test_vertical_stack_rejected(self):
        """Lines stacked vertically (different y) should be rejected."""
        block = _block_from_lines([
            _line("Line1", 10, 100, 100, 110),
            _line("Line2", 10, 150, 100, 160),
        ])
        assert _block_horizontal_row_relaxed(block, min_cells=2) is None

    def test_gap_asymmetry_rejects_heading_pattern(self):
        """Section heading pattern should be rejected by gap asymmetry guard."""
        block = _block_from_lines([
            _line("4", 72, 100, 82, 110),
            _line("General", 120, 100, 180, 110),
            _line("[general]", 400, 100, 470, 110),
        ])
        assert _block_horizontal_row_relaxed(block, min_cells=2) is None

    def test_wide_tolerance_non_overlapping(self):
        """Lines within wide Y tolerance, non-overlapping in x."""
        block = _block_from_lines([
            _line("Col1", 10, 100, 60, 110),
            _line("Col2", 100, 105, 160, 115),
        ])
        result = _block_horizontal_row_relaxed(block, min_cells=2)
        assert result is not None

    def test_overlapping_x_rejected(self):
        """Lines within wide Y tolerance but overlapping in x should be rejected."""
        block = _block_from_lines([
            _line("Overlap1", 10, 100, 120, 110),
            _line("Overlap2", 100, 105, 200, 115),
        ])
        assert _block_horizontal_row_relaxed(block, min_cells=2) is None


def _bbox_block(lines: list[Line], monospace: bool = False) -> Block:
    """Build a Block whose bbox encloses its lines (optionally monospace)."""
    if monospace:
        for ln in lines:
            for sp in ln.spans:
                sp.monospace = True
    x0 = min(ln.bbox[0] for ln in lines)
    y0 = min(ln.bbox[1] for ln in lines)
    x1 = max(ln.bbox[2] for ln in lines)
    y1 = max(ln.bbox[3] for ln in lines)
    return Block(lines=lines, bbox=(x0, y0, x1, y1), page_num=0)


class TestWrappedPartialRow:
    """Tests for _try_wrapped_partial_row (Pass 1 Branch 3b).

    Models the P4182R1 Table A defect: a data row whose Heap and Hosted
    cells sit 41pt apart (below _COLUMN_GAP_THRESHOLD), so MuPDF groups
    them into one non-columnar block that splits the table without this
    branch.
    """

    # Table A header columns: Category, Coro, TLS, PMR, Heap, Hosted.
    REF_COLS = [66.7, 294.2, 339.1, 373.4, 438.8, 480.0]
    COLUMN_XS = frozenset(REF_COLS)

    def _established_table(self) -> list[Block]:
        """Header + one data row, ending at y1=472.2 (the Full RTOS anchor)."""
        header = _bbox_block([_line(t, x, 344.6, x + 20, 358.2)
                              for t, x in zip("ABCDEF", self.REF_COLS)])
        anchor = _bbox_block([
            _line("Full RTOS", 66.7, 458.6, 196.4, 472.2),
            _line("Yes", 294.2, 458.6, 307.1, 472.2),
            _line("Yes", 339.1, 458.6, 352.0, 472.2),
            _line("Hosted", 373.4, 458.6, 400.7, 472.2),
        ])
        return [header, anchor]

    def _right_fragment(self) -> Block:
        """Heap + Hosted cells, same y-band as the anchor, 41pt gap."""
        return _bbox_block([
            _line("Yes", 438.8, 458.6, 451.6, 472.2),
            _line("Partial to", 480.0, 458.6, 514.8, 472.2),
        ])

    def test_narrow_gap_right_fragment_absorbed(self):
        blocks = self._established_table() + [self._right_fragment()]
        result = _try_wrapped_partial_row(
            blocks, 2, self.REF_COLS, self.COLUMN_XS, blocks[:2])
        assert result is not None
        assert result.advance_to == 3
        assert result.multi_orphan is True
        assert id(blocks[2]) in result.absorbed_ids

    def test_left_margin_prose_rejected(self):
        """A wrapped paragraph at the label column (index 0) is not a row."""
        prose = _bbox_block([
            _line("Some prose that wraps onto", 66.7, 500.0, 300.0, 512.0),
            _line("a second physical line here", 66.7, 514.0, 300.0, 526.0),
        ])
        blocks = self._established_table() + [prose]
        assert _try_wrapped_partial_row(
            blocks, 2, self.REF_COLS, self.COLUMN_XS, blocks[:2]) is None

    def test_columnar_block_rejected(self):
        """A block whose gap exceeds the threshold is handled by Branches 1-3."""
        columnar = _bbox_block([
            _line("Yes", 294.2, 458.6, 307.1, 472.2),
            _line("Hosted", 373.4, 458.6, 400.7, 472.2),
        ])
        blocks = self._established_table() + [columnar]
        assert _try_wrapped_partial_row(
            blocks, 2, self.REF_COLS, self.COLUMN_XS, blocks[:2]) is None

    def test_monospace_fragment_rejected(self):
        frag = _bbox_block([
            _line("Yes", 438.8, 458.6, 451.6, 472.2),
            _line("code", 480.0, 458.6, 514.8, 472.2),
        ], monospace=True)
        blocks = self._established_table() + [frag]
        assert _try_wrapped_partial_row(
            blocks, 2, self.REF_COLS, self.COLUMN_XS, blocks[:2]) is None

    def test_unestablished_table_rejected(self):
        """Need header + a data row before absorbing a fragment."""
        blocks = self._established_table()[:1] + [self._right_fragment()]
        assert _try_wrapped_partial_row(
            blocks, 1, self.REF_COLS, self.COLUMN_XS, blocks[:1]) is None

    def test_far_y_gap_rejected(self):
        frag = _bbox_block([
            _line("Yes", 438.8, 600.0, 451.6, 612.0),
            _line("Partial to", 480.0, 600.0, 514.8, 612.0),
        ])
        blocks = self._established_table() + [frag]
        assert _try_wrapped_partial_row(
            blocks, 2, self.REF_COLS, self.COLUMN_XS, blocks[:2]) is None
