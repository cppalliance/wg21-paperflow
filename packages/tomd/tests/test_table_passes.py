# Copyright (c) 2026 C++ Alliance, Inc. (https://cppalliance.org)
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""Unit tests for new table detection passes added in PR #109."""

from types import SimpleNamespace

from tomd.lib.pdf.types import Span, Line, Block
from tomd.lib.pdf.table import (
    _gap_asymmetry_reject,
    _block_horizontal_row_relaxed,
    _try_wrapped_partial_row,
)
from tomd.lib.pdf.pipeline import _detect_drawing_grids

# Page height of a 595x842 portrait page (P3100R6 geometry), shared by
# the drawing-grid tests and the rotation fixtures below.
_PAGE_H = 842.0


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


class _FakePage:
    """Stub page exposing get_drawings()/get_text() with synthetic items."""

    def __init__(self, lines, text_lines=None):
        self._lines = lines
        self._text_lines = text_lines or []

    def get_drawings(self):
        return [
            {"items": [("l", SimpleNamespace(x=x0, y=y0),
                        SimpleNamespace(x=x1, y=y1))]}
            for x0, y0, x1, y1 in self._lines
        ]

    def get_text(self, kind, flags=0):
        return {
            "blocks": [{
                "type": 0,
                "lines": [{"bbox": bbox} for bbox in self._text_lines],
            }]
        }


def _grid_lines(x0, x1, ys):
    """Horizontal rules at each y plus full-height verticals at x0/x1."""
    lines = [(x0, y, x1, y) for y in ys]
    lines.append((x0, ys[0], x0, ys[-1]))
    lines.append((x1, ys[0], x1, ys[-1]))
    return lines


def _two_col_text(ys, left_x=200.0, right_x=300.0):
    """Two side-by-side text cells per row band (a real table)."""
    cells = []
    for y in ys:
        cells.append((left_x, y, left_x + 40, y + 11))
        cells.append((right_x, y, right_x + 90, y + 11))
    return cells


class TestDetectDrawingGrids:
    """Tests for _detect_drawing_grids: bordered grids find_tables missed."""

    PAGE_H = _PAGE_H

    def test_p3100r6_geometry_detected(self):
        """The real P3100R6 page-66 grid (8 h-rules, verticals) is found."""
        ys = [565.0, 578.9, 581.3, 595.2, 609.2, 623.1, 637.1, 637.5]
        text = _two_col_text([566.1, 583.0, 597.0, 610.9, 624.9])
        page = _FakePage(_grid_lines(190.0, 405.0, ys), text)
        grids = _detect_drawing_grids(page, self.PAGE_H, [])
        assert len(grids) == 1
        bbox = grids[0]["bbox"]
        assert bbox[0] == 190.0 and bbox[2] == 405.0
        # Synthetic entry must carry the full find_tables shape with
        # row_count=0 so Pass 5 skips it.
        assert grids[0]["row_count"] == 0
        assert grids[0]["cells"] == []

    def test_full_page_margin_rules_rejected(self):
        """Full-page-height rules (wording margins) must not become grids."""
        ys = [74.0, 190.0, 306.0, 422.0, 538.0, 654.0, 769.0]
        text = _two_col_text([100.0, 220.0, 340.0, 460.0, 580.0],
                             left_x=210.0, right_x=270.0)
        page = _FakePage(_grid_lines(205.0, 320.0, ys), text)
        grids = _detect_drawing_grids(page, self.PAGE_H, [])
        assert grids == []

    def test_too_few_horizontals_rejected(self):
        ys = [565.0, 595.0, 637.0]
        text = _two_col_text([570.0, 600.0])
        page = _FakePage(_grid_lines(190.0, 405.0, ys), text)
        assert _detect_drawing_grids(page, self.PAGE_H, []) == []

    def test_missing_vertical_borders_rejected(self):
        """Horizontal rules without side borders (e.g. hr separators)."""
        ys = [565.0, 580.0, 595.0, 610.0, 625.0]
        text = _two_col_text([567.0, 582.0, 597.0, 612.0])
        page = _FakePage([(190.0, y, 405.0, y) for y in ys], text)
        assert _detect_drawing_grids(page, self.PAGE_H, []) == []

    def test_already_covered_by_find_tables_skipped(self):
        ys = [565.0, 580.0, 595.0, 610.0, 625.0]
        text = _two_col_text([567.0, 582.0, 597.0, 612.0])
        page = _FakePage(_grid_lines(190.0, 405.0, ys), text)
        existing = [{"bbox": (185.0, 560.0, 410.0, 630.0)}]
        assert _detect_drawing_grids(page, self.PAGE_H, existing) == []

    def test_boxed_code_single_column_rejected(self):
        """Bordered wording/code boxes (one line per y-band) are not tables."""
        ys = [565.0, 580.0, 595.0, 610.0, 625.0]
        # One text line per band, varying indentation (code box pattern).
        text = [
            (200.0, 567.0, 380.0, 578.0),
            (215.0, 582.0, 390.0, 593.0),
            (215.0, 597.0, 350.0, 608.0),
            (200.0, 612.0, 360.0, 623.0),
        ]
        page = _FakePage(_grid_lines(190.0, 405.0, ys), text)
        assert _detect_drawing_grids(page, self.PAGE_H, []) == []

    def test_mostly_single_cell_bands_rejected(self):
        """A grid where most rows hold one cell is a box stack, not a table."""
        ys = [565.0, 580.0, 595.0, 610.0, 625.0, 640.0]
        text = [
            # 2 multi-cell bands...
            (200.0, 567.0, 240.0, 578.0), (300.0, 567.0, 390.0, 578.0),
            (200.0, 582.0, 240.0, 593.0), (300.0, 582.0, 390.0, 593.0),
            # ...but 3 single-cell bands dominate
            (200.0, 597.0, 390.0, 608.0),
            (200.0, 612.0, 390.0, 623.0),
            (200.0, 627.0, 390.0, 638.0),
        ]
        page = _FakePage(_grid_lines(190.0, 405.0, ys), text)
        assert _detect_drawing_grids(page, self.PAGE_H, []) == []
