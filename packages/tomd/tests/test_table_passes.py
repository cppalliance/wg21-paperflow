# Copyright (c) 2026 C++ Alliance, Inc. (https://cppalliance.org)
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""Unit tests for new table detection passes added in PR #109."""

from types import SimpleNamespace

from tomd.lib.pdf.types import Span, Line, Block, Section, SectionKind
from tomd.lib.pdf.table import (
    _gap_asymmetry_reject,
    _block_horizontal_row_relaxed,
    _try_wrapped_partial_row,
    _try_cross_page_continuation,
    _filter_overlapping_mupdf_tables,
    _rot_midpoint,
    _detect_mupdf_native_tables,
    _detect_banded_rotated_tables,
)
from tomd.lib.pdf.pipeline import _column_aware_sort, _detect_drawing_grids

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


# 90-degree rotation matrix of a 595x842 portrait page (P3100R6 appendix
# geometry): maps unrotated page space into reading space via
# (x, y) -> (842 - y, x).
_ROT90 = (0.0, 1.0, -1.0, 0.0, _PAGE_H, 0.0)


def _rotated_line(text: str, rx: float, ry: float) -> Line:
    """Line whose page-space bbox maps to reading-space center (rx, ry)."""
    x, y = ry, _PAGE_H - rx
    return Line(spans=[Span(text=text, font_size=10.0)],
                bbox=(x - 5, y - 5, x + 5, y + 5))


class TestRotMidpoint:
    def test_no_rotation_returns_plain_midpoint(self):
        assert _rot_midpoint((10.0, 20.0, 30.0, 40.0), None) == (20.0, 30.0)

    def test_rot90_maps_into_reading_space(self):
        # Page-space midpoint (100, 742) -> reading space (842-742, 100).
        assert _rot_midpoint((90.0, 732.0, 110.0, 752.0), _ROT90) == (
            100.0, 100.0)


class TestMupdfNativeRotatedPage:
    """Pass 5 on rotated pages: cell assignment uses reading space.

    Models the P3100R6 appendix (pages rotated 90 degrees): find_tables()
    reports table/cell bboxes in reading space while extract_mupdf block
    bboxes stay in unrotated page space.  Without the rot matrix every
    line lands in the wrong cell (or none).
    """

    # 3 columns: keeps the 2-column label-transpose heuristic out of play.
    EXPECTED = [
        ["Name", "Meaning", "Notes"],
        ["pre", "a precondition check", "evaluated on entry"],
        ["post", "a postcondition check", "evaluated on exit"],
    ]

    def _tbl_info(self, rot):
        # 3x3 grid in reading space: rows at y 50/120/190,
        # cols at x 50/200/400.
        cells = [
            (50.0, 50.0, 200.0, 120.0), (200.0, 50.0, 400.0, 120.0),
            (400.0, 50.0, 560.0, 120.0),
            (50.0, 120.0, 200.0, 190.0), (200.0, 120.0, 400.0, 190.0),
            (400.0, 120.0, 560.0, 190.0),
            (50.0, 190.0, 200.0, 260.0), (200.0, 190.0, 400.0, 260.0),
            (400.0, 190.0, 560.0, 260.0),
        ]
        return {
            "bbox": (50.0, 50.0, 560.0, 260.0),
            "row_count": 3, "col_count": 3,
            "cells": cells,
            "header_names": None,
            "extract": [list(r) for r in self.EXPECTED],
            "rot": rot,
        }

    def _blocks(self):
        # One block per cell, placed at reading-space cell centers but
        # carrying page-space bboxes (as extract_mupdf delivers them).
        col_x = (125.0, 300.0, 480.0)
        row_y = (85.0, 155.0, 225.0)
        blocks = []
        for ri, row in enumerate(self.EXPECTED):
            for ci, txt in enumerate(row):
                ln = _rotated_line(txt, col_x[ci], row_y[ri])
                blocks.append(Block(lines=[ln], bbox=ln.bbox, page_num=0))
        return blocks

    def test_rotated_cells_assigned_correctly(self):
        sections, used = _detect_mupdf_native_tables(
            self._blocks(), {0: [self._tbl_info(_ROT90)]})
        assert len(sections) == 1
        rows = [
            ["".join(s.text for s in cell) for cell in row]
            for row in sections[0].columns
        ]
        assert rows == self.EXPECTED

    def test_without_rot_matrix_assembly_degrades(self):
        """Control: same geometry minus the matrix must not pair correctly."""
        sections, used = _detect_mupdf_native_tables(
            self._blocks(), {0: [self._tbl_info(None)]})
        for sec in sections:
            rows = [
                ["".join(s.text for s in cell) for cell in row]
                for row in sec.columns
            ]
            assert rows != self.EXPECTED


def _banded_frag(row_ys, col_xs=(50.0, 200.0, 400.0, 560.0)):
    """A find_tables fragment dict in reading space.

    row_ys: list of (y_top, y_bot) per row; col_xs: column boundaries.
    """
    cells = []
    for (yt, yb) in row_ys:
        for k in range(len(col_xs) - 1):
            cells.append((col_xs[k], yt, col_xs[k + 1], yb))
    bbox = (col_xs[0], row_ys[0][0], col_xs[-1], row_ys[-1][1])
    return {
        "bbox": bbox,
        "row_count": len(row_ys), "col_count": len(col_xs) - 1,
        "cells": cells,
        "header_names": None,
        "extract": [],
        "rot": _ROT90,
    }


class TestBandedRotatedAssembly:
    """Banded assembly path: fragment stitching with band barriers.

    Models the P3100R6 appendix: a rotated page where find_tables()
    splits one logical table into fragments separated by category-band
    blocks.  1-row fragments are continuation rows; bands start a new
    section and stay unclaimed (rendered as prose headings).
    """

    HEADER = ["Name", "Meaning", "Notes"]
    ROW_PRE = ["pre", "a precondition", "on entry"]
    ROW_POST = ["post", "a postcondition", "on exit"]
    ROW_ASSERT = ["assert", "an assertion", "mid-body"]

    COL_CENTERS = (125.0, 300.0, 480.0)

    def _row_blocks(self, texts, ry):
        blocks = []
        for ci, txt in enumerate(texts):
            ln = _rotated_line(txt, self.COL_CENTERS[ci], ry)
            blocks.append(Block(lines=[ln], bbox=ln.bbox, page_num=0))
        return blocks

    def _band_block(self, text, ry):
        ln = _rotated_line(text, 100.0, ry)
        return Block(lines=[ln], bbox=ln.bbox, page_num=0)

    def _setup(self, frag2_rows):
        """Header frag / band / 1-row frag / band / 2-row frag."""
        frags = [
            _banded_frag([(50.0, 80.0)]),
            _banded_frag([(100.0, 160.0)]),
            _banded_frag([(180.0, 240.0), (240.0, 300.0)]),
        ]
        blocks = []
        blocks += self._row_blocks(self.HEADER, 65.0)
        band1 = self._band_block("I. Contracts", 90.0)
        blocks.append(band1)
        blocks += self._row_blocks(self.ROW_PRE, 130.0)
        band2 = self._band_block("II. Checks", 170.0)
        blocks.append(band2)
        row_ys = (210.0, 270.0)
        for texts, ry in zip(frag2_rows, row_ys):
            blocks += self._row_blocks(texts, ry)
        band_indices = {blocks.index(band1), blocks.index(band2)}
        return blocks, frags, band_indices

    @staticmethod
    def _texts(section):
        return [
            ["".join(s.text for s in cell) for cell in row]
            for row in section.columns
        ]

    def test_band_barriers_split_into_categories(self):
        blocks, frags, band_idx = self._setup(
            [self.ROW_POST, self.ROW_ASSERT])
        sections, used = _detect_mupdf_native_tables(blocks, {0: frags})
        assert len(sections) == 2
        assert all(s.table_source == "banded_grid" for s in sections)
        # Category I: canonical header + the 1-row fragment.
        assert self._texts(sections[0]) == [self.HEADER, self.ROW_PRE]
        # Category II: canonical header + both rows of fragment 2.
        assert self._texts(sections[1]) == [
            self.HEADER, self.ROW_POST, self.ROW_ASSERT]

    def test_band_blocks_stay_unclaimed(self):
        blocks, frags, band_idx = self._setup(
            [self.ROW_POST, self.ROW_ASSERT])
        sections, used = _detect_mupdf_native_tables(blocks, {0: frags})
        assert not (used & band_idx)

    def test_repeated_header_dropped(self):
        # Fragment 2 starts with a per-page header repeat that differs
        # from the canonical header in one cell (the P3100R6 typo case).
        blocks, frags, band_idx = self._setup(
            [["Nam", "Meaning", "Notes"], self.ROW_POST])
        sections, used = _detect_mupdf_native_tables(blocks, {0: frags})
        assert len(sections) == 2
        assert self._texts(sections[1]) == [self.HEADER, self.ROW_POST]

    def test_without_bands_does_not_fire(self):
        blocks, frags, band_idx = self._setup(
            [self.ROW_POST, self.ROW_ASSERT])
        blocks = [b for i, b in enumerate(blocks) if i not in band_idx]
        sections, used, consumed = _detect_banded_rotated_tables(
            blocks, {0: frags})
        assert consumed == set()
        assert sections == []

    def test_without_rot_does_not_fire(self):
        blocks, frags, band_idx = self._setup(
            [self.ROW_POST, self.ROW_ASSERT])
        frags = [{**f, "rot": None} for f in frags]
        sections, used, consumed = _detect_banded_rotated_tables(
            blocks, {0: frags})
        assert consumed == set()

    def test_band_hugging_fragment_edge_still_splits(self):
        """A band heading inside the claim margin of the next fragment
        must stay a band (review fix: band detection runs before block
        claiming, otherwise the heading is swallowed into a cell)."""
        blocks, frags, band_idx = self._setup(
            [self.ROW_POST, self.ROW_ASSERT])
        # Move band 2 from ry 170 to ry 179: 1pt above fragment 3's top
        # edge (180), well inside its 5pt claim margin.
        for i in band_idx:
            if blocks[i].text == "II. Checks":
                ln = _rotated_line("II. Checks", 100.0, 179.0)
                blocks[i] = Block(lines=[ln], bbox=ln.bbox, page_num=0)
        sections, used = _detect_mupdf_native_tables(blocks, {0: frags})
        assert len(sections) == 2
        assert self._texts(sections[1]) == [
            self.HEADER, self.ROW_POST, self.ROW_ASSERT]
        # The heading itself must not appear in any cell.
        all_cells = [c for s in sections for row in self._texts(s)
                     for c in row]
        assert "II. Checks" not in all_cells

    def test_two_column_header_repeat_requires_exact_match(self):
        """In a 2-column table a data row sharing one cell with the
        header is real data, not a header repeat (review fix: the
        1-mismatch tolerance applies only to 3+ column tables)."""
        two_cols = (50.0, 200.0, 400.0)
        frags = [
            _banded_frag([(50.0, 80.0)], col_xs=two_cols),
            _banded_frag([(100.0, 160.0)], col_xs=two_cols),
        ]
        header = ["Default", "Meaning"]
        data_row = ["Default", "checks enabled"]
        blocks = []
        for ci, txt in enumerate(header):
            ln = _rotated_line(txt, (125.0, 300.0)[ci], 65.0)
            blocks.append(Block(lines=[ln], bbox=ln.bbox, page_num=0))
        blocks.append(self._band_block("I. Modes", 90.0))
        for ci, txt in enumerate(data_row):
            ln = _rotated_line(txt, (125.0, 300.0)[ci], 130.0)
            blocks.append(Block(lines=[ln], bbox=ln.bbox, page_num=0))
        sections, used = _detect_mupdf_native_tables(blocks, {0: frags})
        assert len(sections) == 1
        assert self._texts(sections[0]) == [header, data_row]

    def test_distant_rotated_table_not_absorbed(self):
        """An independent rotated table on a far page is its own run and
        must not be stitched into the banded table (review fix)."""
        blocks, frags, band_idx = self._setup(
            [self.ROW_POST, self.ROW_ASSERT])

        # Independent 3x3 rotated table on page 20, different column
        # count irrelevant: distance alone must isolate it.
        other_rows = [
            ["Opt", "Type", "Doc"],
            ["-O2", "level", "speed"],
            ["-Og", "level", "debug"],
        ]
        cells = []
        row_ys = [(50.0, 120.0), (120.0, 190.0), (190.0, 260.0)]
        col_xs = (50.0, 200.0, 400.0, 560.0)
        for yt, yb in row_ys:
            for k in range(len(col_xs) - 1):
                cells.append((col_xs[k], yt, col_xs[k + 1], yb))
        tbl20 = {
            "bbox": (50.0, 50.0, 560.0, 260.0),
            "row_count": 3, "col_count": 3,
            "cells": cells,
            "header_names": None,
            "extract": [list(r) for r in other_rows],
            "rot": _ROT90,
        }
        for ri, row in enumerate(other_rows):
            for ci, txt in enumerate(row):
                ln = _rotated_line(txt, self.COL_CENTERS[ci],
                                   (85.0, 155.0, 225.0)[ri])
                blocks.append(Block(lines=[ln], bbox=ln.bbox, page_num=20))

        sections, used = _detect_mupdf_native_tables(
            blocks, {0: frags, 20: [tbl20]})
        banded = [s for s in sections if s.table_source == "banded_grid"]
        assert len(banded) == 2
        assert self._texts(banded[0]) == [self.HEADER, self.ROW_PRE]
        assert self._texts(banded[1]) == [
            self.HEADER, self.ROW_POST, self.ROW_ASSERT]
        # Page 20 keeps its own table, assembled by the main loop.
        others = [s for s in sections if s.page_num == 20]
        assert len(others) == 1
        assert self._texts(others[0]) == other_rows


class TestColumnAwareSortRotated:
    """_column_aware_sort uses reading-space y on rotated pages."""

    def test_rotated_page_sorts_by_reading_order(self):
        # Reading order: heading (ry 30), table row (ry 100), footer
        # (ry 200).  In page space their y-order is inverted (the 90
        # degree rotation maps reading-y onto page-x).
        ln_heading = _rotated_line("Appendix", 100.0, 30.0)
        heading = Block(lines=[ln_heading], bbox=ln_heading.bbox, page_num=0)
        ln_row = _rotated_line("data", 100.0, 100.0)
        row = Block(lines=[ln_row], bbox=ln_row.bbox, page_num=0)
        ln_footer = _rotated_line("73", 100.0, 200.0)
        footer = Block(lines=[ln_footer], bbox=ln_footer.bbox, page_num=0)
        blocks = [footer, row, heading]
        _column_aware_sort(blocks, {0: 595.0}, {0: _ROT90})
        assert [b.text for b in blocks] == ["Appendix", "data", "73"]

    def test_without_rotation_map_behavior_unchanged(self):
        a = Block(lines=[_line("top", 10, 50, 100, 60)],
                  bbox=(10, 50, 100, 60), page_num=0)
        b = Block(lines=[_line("bottom", 10, 500, 100, 510)],
                  bbox=(10, 500, 100, 510), page_num=0)
        blocks = [b, a]
        _column_aware_sort(blocks, {0: 595.0})
        assert [blk.text for blk in blocks] == ["top", "bottom"]


# ---------------------------------------------------------------------------
# Cross-page table continuation (issue #304)
# ---------------------------------------------------------------------------

# Real geometry from P0957R8 "Table 3 - Sample compiler configurations", which
# runs off the bottom of page 12 and resumes at the top of page 13.
_P12_HEADER_XS = [63.0, 200.3, 343.7, 453.0]
_P12_ROW1_XS = [75.4, 224.5, 347.4, 452.2]
_P12_ROW2_XS = [94.4, 228.4, 351.2, 452.2]
_P13_CONT_XS = [81.7, 224.5, 347.4, 452.2]


def _row(page: int, y0: float, y1: float, xs: list[float]) -> Block:
    """A columnar block: one line per cell, starting at each x in xs."""
    lines = [
        Line(spans=[Span(text=f"c{i}", font_size=10.0)],
             bbox=(x, y0, x + 40.0, y1), page_num=page)
        for i, x in enumerate(xs)
    ]
    return Block(lines=lines, bbox=(xs[0], y0, xs[-1] + 40.0, y1),
                 page_num=page)


def _spacer(page: int, y0: float, y1: float) -> Block:
    """A whitespace-only block, as left behind by header/footer stripping."""
    line = Line(spans=[Span(text=" ", font_size=10.0)],
                bbox=(62.5, y0, 64.8, y1), page_num=page)
    return Block(lines=[line], bbox=(62.5, y0, 64.8, y1), page_num=page)


def _prose(page: int, y0: float, y1: float) -> Block:
    """A single-line block carrying real text."""
    line = Line(spans=[Span(text="Some prose.", font_size=10.0)],
                bbox=(62.5, y0, 400.0, y1), page_num=page)
    return Block(lines=[line], bbox=(62.5, y0, 400.0, y1), page_num=page)


class TestTryCrossPageContinuation:
    """Branch 6: a table runs off one page and resumes on the next."""

    def _table_blocks(self) -> list[Block]:
        return [
            _row(12, 714.0, 727.8, _P12_HEADER_XS),
            _row(12, 730.3, 743.7, _P12_ROW1_XS),
            _row(12, 745.9, 759.3, _P12_ROW2_XS),
        ]

    def test_continuation_row_across_blank_spacer(self):
        """The P0957R8 case: spacer on page 12, continuation on page 13."""
        table_blocks = self._table_blocks()
        blocks = [_spacer(12, 770.6, 793.1),
                  _row(13, 73.5, 86.9, _P13_CONT_XS)]
        result = _try_cross_page_continuation(
            blocks, 0, _P12_ROW2_XS, table_blocks)
        assert result is not None
        assert result.advance_to == 2
        assert result.new_ref_cols == _P13_CONT_XS

    def test_continuation_row_with_nothing_between(self):
        table_blocks = self._table_blocks()
        blocks = [_row(13, 73.5, 86.9, _P13_CONT_XS)]
        result = _try_cross_page_continuation(
            blocks, 0, _P12_ROW2_XS, table_blocks)
        assert result is not None
        assert result.advance_to == 1

    def test_real_block_between_ends_the_table(self):
        """Only whitespace may intervene; prose means the table stopped."""
        table_blocks = self._table_blocks()
        blocks = [_prose(12, 770.6, 785.0),
                  _row(13, 73.5, 86.9, _P13_CONT_XS)]
        assert _try_cross_page_continuation(
            blocks, 0, _P12_ROW2_XS, table_blocks) is None

    def test_page_gap_larger_than_one_rejected(self):
        table_blocks = self._table_blocks()
        blocks = [_row(14, 73.5, 86.9, _P13_CONT_XS)]
        assert _try_cross_page_continuation(
            blocks, 0, _P12_ROW2_XS, table_blocks) is None

    def test_candidate_below_top_band_rejected(self):
        """A table further down the next page is a different table."""
        table_blocks = self._table_blocks()
        blocks = [_row(13, 300.0, 313.4, _P13_CONT_XS)]
        assert _try_cross_page_continuation(
            blocks, 0, _P12_ROW2_XS, table_blocks) is None

    def test_table_not_at_page_bottom_rejected(self):
        """A table ending mid-page did not run out of room."""
        table_blocks = [
            _row(12, 300.0, 313.4, _P12_HEADER_XS),
            _row(12, 315.0, 328.4, _P12_ROW1_XS),
            _row(12, 330.0, 343.4, _P12_ROW2_XS),
        ]
        blocks = [_row(13, 73.5, 86.9, _P13_CONT_XS)]
        assert _try_cross_page_continuation(
            blocks, 0, _P12_ROW2_XS, table_blocks) is None

    def test_column_count_mismatch_rejected(self):
        table_blocks = self._table_blocks()
        blocks = [_row(13, 73.5, 86.9, [81.7, 224.5, 347.4])]
        assert _try_cross_page_continuation(
            blocks, 0, _P12_ROW2_XS, table_blocks) is None

    def test_column_drift_beyond_tolerance_rejected(self):
        """Same column count but a visibly different layout."""
        table_blocks = self._table_blocks()
        blocks = [_row(13, 73.5, 86.9, [200.0, 300.0, 400.0, 500.0])]
        assert _try_cross_page_continuation(
            blocks, 0, _P12_ROW2_XS, table_blocks) is None

    def test_unestablished_table_rejected(self):
        """A single row is not yet a table worth continuing."""
        table_blocks = [_row(12, 745.9, 759.3, _P12_ROW2_XS)]
        blocks = [_row(13, 73.5, 86.9, _P13_CONT_XS)]
        assert _try_cross_page_continuation(
            blocks, 0, _P12_ROW2_XS, table_blocks) is None

    def test_non_columnar_candidate_rejected(self):
        table_blocks = self._table_blocks()
        blocks = [_prose(13, 73.5, 86.9)]
        assert _try_cross_page_continuation(
            blocks, 0, _P12_ROW2_XS, table_blocks) is None

    def test_trailing_blanks_only_rejected(self):
        """Running off the end of the document is not a continuation."""
        table_blocks = self._table_blocks()
        blocks = [_spacer(12, 770.6, 793.1)]
        assert _try_cross_page_continuation(
            blocks, 0, _P12_ROW2_XS, table_blocks) is None


class TestFilterOverlappingMupdfTablesCrossPage:
    """A cross-page section must claim a y-range per page, not one union."""

    def _cross_page_section(self) -> Section:
        """Section whose lines span the bottom of page 12 and top of page 13."""
        return Section(
            kind=SectionKind.TABLE,
            text="",
            lines=[
                Line(spans=[Span(text="a")], bbox=(63.0, 714.0, 500.0, 727.8),
                     page_num=12),
                Line(spans=[Span(text="b")], bbox=(81.7, 73.5, 500.0, 86.9),
                     page_num=13),
            ],
            page_num=12,
        )

    def test_unrelated_table_on_same_page_survives(self):
        """A find_tables entry mid-page-12 does not overlap the bottom band."""
        page_tables = {12: [{"bbox": (60.0, 448.0, 520.0, 560.0)}]}
        kept = _filter_overlapping_mupdf_tables(
            page_tables, [self._cross_page_section()])
        assert kept == page_tables

    def test_overlapping_entry_on_each_touched_page_dropped(self):
        """Both the page-12 and the page-13 fragment suppress their own page."""
        page_tables = {
            12: [{"bbox": (60.0, 710.0, 520.0, 760.0)}],
            13: [{"bbox": (60.0, 70.0, 520.0, 90.0)}],
        }
        kept = _filter_overlapping_mupdf_tables(
            page_tables, [self._cross_page_section()])
        assert kept == {}


# --- N5040 attendance table (issue #360) ------------------------------------
#
# A two-column bordered table whose header cells are CENTERED while every
# body cell is left-aligned, running past the bottom of one page and
# continuing at the top of the next. Geometry mirrors the real paper:
# body names at x0=74, national bodies at x0=367, and the centered header
# cells at x0=203 / x0=404.

_ATT_NAME_X = 74.0
_ATT_BODY_X = 367.0
_ATT_HDR_NAME_X = 203.0
_ATT_HDR_BODY_X = 404.0


def _attendance_page(names, page_num, y0, *, header=False, blank_tail=0):
    """Build one page's worth of the attendance table as a single Block."""
    lines, y = [], y0
    if header:
        lines.append(_line("Name", _ATT_HDR_NAME_X, y, _ATT_HDR_NAME_X + 36, y + 13))
        lines.append(_line("National Body", _ATT_HDR_BODY_X, y,
                           _ATT_HDR_BODY_X + 78, y + 13))
        y += 17
    for name, body in names:
        lines.append(_line(name, _ATT_NAME_X, y, _ATT_NAME_X + 90, y + 13))
        lines.append(_line(body, _ATT_BODY_X, y, _ATT_BODY_X + 31, y + 13))
        y += 17
    for _ in range(blank_tail):
        lines.append(_line(" ", _ATT_NAME_X, y, _ATT_NAME_X + 3, y + 13))
        y += 17
    for ln in lines:
        ln.page_num = page_num
    x1 = _ATT_HDR_BODY_X + 78
    blk = Block(lines=lines, bbox=(_ATT_NAME_X, y0, x1, y), page_num=page_num)
    return blk, (_ATT_NAME_X, y0, x1, y)


class TestInlineGridAttendanceTable:
    """Issue #360: phantom column, page-break splits, blank trailing rows."""

    @staticmethod
    def _run(blocks, bboxes):
        from tomd.lib.pdf.table import _detect_inline_grid_tables
        mupdf = {}
        for blk, bbox in zip(blocks, bboxes):
            mupdf.setdefault(blk.page_num, []).append({"bbox": bbox})
        return _detect_inline_grid_tables(blocks, mupdf)

    def _two_pages(self, blank_tail=0):
        page_a = [(f"Name A{i}", "ANSI") for i in range(38)]
        page_b = [(f"Name B{i}", "BSI") for i in range(20)]
        blk_a, bb_a = _attendance_page(page_a, 0, 120.0, header=True)
        blk_b, bb_b = _attendance_page(page_b, 1, 120.0, blank_tail=blank_tail)
        return self._run([blk_a, blk_b], [bb_a, bb_b])

    def test_centered_header_does_not_create_a_phantom_column(self):
        sections, _ = self._two_pages()
        assert len(sections) == 1
        assert len(sections[0].columns[0]) == 2

    def test_header_row_holds_the_column_labels(self):
        sections, _ = self._two_pages()
        header = ["".join(s.text for s in cell).strip()
                  for cell in sections[0].columns[0]]
        assert header == ["Name", "National Body"]

    def test_page_break_does_not_start_a_second_table(self):
        sections, _ = self._two_pages()
        assert len(sections) == 1
        # 1 header + 38 + 20 attendees, nothing dropped or duplicated.
        assert len(sections[0].columns) == 59

    def test_continuation_rows_are_body_rows_not_headers(self):
        sections, _ = self._two_pages()
        first_continuation = [
            "".join(s.text for s in cell).strip()
            for cell in sections[0].columns[39]
        ]
        assert first_continuation == ["Name B0", "BSI"]

    def test_blank_source_lines_do_not_become_empty_rows(self):
        sections, _ = self._two_pages(blank_tail=2)
        rows = sections[0].columns
        assert len(rows) == 59
        for row in rows:
            assert any("".join(s.text for s in cell).strip() for cell in row)


class TestMergeCrossPageFragments:
    """The merge helper is shared by the inline-grid and MuPDF-native passes."""

    @staticmethod
    def _fragment(rows, page_num, y0, y1):
        from tomd.lib.pdf.types import Confidence, Section, SectionKind
        lines = [_line(rows[0][0], 74.0, y0, 160.0, y0 + 13),
                 _line(rows[-1][0], 74.0, y1 - 13, 160.0, y1)]
        for ln in lines:
            ln.page_num = page_num
        columns = [[[Span(text=c)] for c in row] for row in rows]
        return Section(kind=SectionKind.TABLE, text="",
                       confidence=Confidence.HIGH, lines=lines,
                       page_num=page_num, columns=columns)

    def test_merges_fragments_across_a_page_break(self):
        from tomd.lib.pdf.table import _merge_cross_page_fragments
        a = self._fragment([["a1", "x"], ["a2", "y"]], 0, 120.0, 760.0)
        b = self._fragment([["b1", "z"], ["b2", "w"]], 1, 120.0, 300.0)
        merged = _merge_cross_page_fragments([a, b])
        assert len(merged) == 1
        assert len(merged[0].columns) == 4

    def test_leaves_fragments_with_different_column_counts_alone(self):
        from tomd.lib.pdf.table import _merge_cross_page_fragments
        a = self._fragment([["a1", "x"], ["a2", "y"]], 0, 120.0, 760.0)
        b = self._fragment([["b1", "z", "extra"]], 1, 120.0, 300.0)
        assert len(_merge_cross_page_fragments([a, b])) == 2

    def test_leaves_mid_page_neighbours_alone(self):
        from tomd.lib.pdf.table import _merge_cross_page_fragments
        a = self._fragment([["a1", "x"], ["a2", "y"]], 0, 120.0, 300.0)
        b = self._fragment([["b1", "z"]], 1, 400.0, 500.0)
        assert len(_merge_cross_page_fragments([a, b])) == 2
