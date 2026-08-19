# Copyright (c) 2026 C++ Alliance, Inc. (https://cppalliance.org)
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""Tables MuPDF merged into neighbouring blocks (issue #368).

P3290R4's poll boxes are atomized one-cell-per-line and, on two pages, fused
into the preceding prose block. Both bands (the SF/F/N/A/SA header and the vote
counts) land inside one block, so a splitter that peels only the last band takes
the votes and calls them the header.
"""

from tomd.lib.pdf.types import Span, Line, Block
from tomd.lib.pdf.table import (
    _split_trailing_horizontal_rows,
    _pass1_region_incomplete,
    detect_tables,
)


def _line(text: str, x0: float, y0: float, width: float = 12.0,
          height: float = 10.0) -> Line:
    return Line(spans=[Span(text=text, font_size=10.0)],
                bbox=(x0, y0, x0 + width, y0 + height))


def _prose(text: str, y0: float) -> Line:
    return _line(text, 87.6, y0, width=430.0)


# Real P3290R4 page-3 geometry: header band at y=450.2, votes at y=464.2.
_HEADER_XS = [(93.6, "SF"), (119.1, "F"), (138.6, "N"),
              (159.1, "A"), (179.6, "SA")]
_VOTE_XS = [(97.4, "8"), (119.9, "3"), (139.9, "1"),
            (160.5, "0"), (184.0, "0")]


def _band(cells, y0):
    return [_line(text, x, y0) for x, text in cells]


def _rows_text(section):
    return [["".join(s.text for s in cell) for cell in row]
            for row in section.columns]


def _poll_block(with_prose: bool) -> Block:
    lines = []
    if with_prose:
        lines += [_prose("Forward Proposals 1.1-1.3 of D3290R2", 424.1),
                  _prose("to EWG and LEWG for design review.", 437.6)]
    lines += _band(_HEADER_XS, 450.2) + _band(_VOTE_XS, 464.2)
    return _block(lines, page_num=2)


class TestTwoBandPoll:
    """Both header and data bands merged into one block."""

    def test_fused_with_prose_yields_header_and_votes(self):
        sections, remaining = _split_trailing_horizontal_rows(
            [_poll_block(with_prose=True)])
        assert len(sections) == 1
        assert _rows_text(sections[0]) == [
            ["SF", "F", "N", "A", "SA"],
            ["8", "3", "1", "0", "0"],
        ]

    def test_fused_with_prose_leaves_only_prose_behind(self):
        _, remaining = _split_trailing_horizontal_rows(
            [_poll_block(with_prose=True)])
        assert len(remaining) == 1
        assert len(remaining[0].lines) == 2
        assert "SF" not in "".join(
            s.text for ln in remaining[0].lines for s in ln.spans)

    def test_standalone_block_yields_the_whole_table(self):
        """No prose fused in: the block is entirely table (start == 0)."""
        sections, remaining = _split_trailing_horizontal_rows(
            [_poll_block(with_prose=False)])
        assert len(sections) == 1
        assert _rows_text(sections[0]) == [
            ["SF", "F", "N", "A", "SA"],
            ["8", "3", "1", "0", "0"],
        ]

    def test_standalone_block_leaves_no_empty_paragraph(self):
        _, remaining = _split_trailing_horizontal_rows(
            [_poll_block(with_prose=False)])
        assert remaining == []

    def test_no_synthetic_empty_row(self):
        """The invented empty row is what trips whisker's no_empty_table gate."""
        sections, _ = _split_trailing_horizontal_rows(
            [_poll_block(with_prose=True)])
        for row in sections[0].columns:
            assert any("".join(s.text for s in cell).strip() for cell in row)


class TestSingleBandUnchanged:
    """The P4012R0 case this splitter was written for must not regress."""

    def test_lone_header_band_still_gets_an_empty_row(self):
        lines = [_prose("Suggested poll wording follows.", 424.1)]
        lines += _band(_HEADER_XS, 450.2)
        sections, remaining = _split_trailing_horizontal_rows(
            [_block(lines, page_num=2)])
        assert len(sections) == 1
        rows = _rows_text(sections[0])
        assert rows[0] == ["SF", "F", "N", "A", "SA"]
        assert len(rows) == 2
        assert not any(c.strip() for c in rows[1])


class TestBandsMustAgree:
    """Two bands only merge when they describe the same columns."""

    def test_unequal_cell_counts_do_not_merge(self):
        lines = [_prose("Some paragraph text here.", 424.1)]
        lines += _band(_HEADER_XS[:4], 450.2)
        lines += _band(_VOTE_XS, 464.2)
        sections, _ = _split_trailing_horizontal_rows(
            [_block(lines, page_num=2)])
        assert len(sections) == 1
        rows = _rows_text(sections[0])
        assert rows[0] == ["8", "3", "1", "0", "0"]
        assert len(rows[0]) == 5


# --- Pass 1 deferral: MuPDF sees the whole table, Pass 1 sees part of it ---

# Real P3290R4 page-16 geometry for [tab:support.contract.enum.detection].
_DETECTION_REGION = (151.9, 518.3, 460.1, 657.8)


def _cell(text: str, x0: float, y0: float, width: float) -> Line:
    return Line(spans=[Span(text=text, font_size=10.0)],
                bbox=(x0, y0, x0 + width, y0 + 11.0))


def _block(lines: list[Line], page_num: int = 0) -> Block:
    """A Block with the bbox extraction would have given it."""
    return Block(
        lines=lines,
        bbox=(min(ln.bbox[0] for ln in lines),
              min(ln.bbox[1] for ln in lines),
              max(ln.bbox[2] for ln in lines),
              max(ln.bbox[3] for ln in lines)),
        page_num=page_num,
    )


def _header_and_first_row() -> Block:
    """Block 14: the Name|Meaning header fused with the `unspecified` row."""
    return _block([
        _cell("Name", 158.1, 519.3, 30.0),
        _cell("Meaning", 283.8, 519.3, 45.0),
        _cell("unspecified", 158.1, 536.4, 60.0),
        _cell("The mode of detection was not", 283.8, 535.6, 160.0),
    ])


def _predicate_row() -> Block:
    return _block([
        _cell("predicate_false", 158.1, 579.6, 75.0),
        _cell("The predicate of the contract", 283.8, 576.7, 160.0),
    ])


def _exception_row() -> Block:
    return _block([
        _cell("evaluation_exception", 158.1, 620.6, 100.0),
        _cell("An uncaught exception occurred", 283.8, 617.7, 160.0),
    ])


class TestPass1RegionIncomplete:
    """The predicate behind deferring a low-row-count MuPDF table."""

    def test_unclaimed_block_inside_region_is_incomplete(self):
        header, pred, exc = (_header_and_first_row(), _predicate_row(),
                             _exception_row())
        assert _pass1_region_incomplete(
            _DETECTION_REGION, 0, [pred, exc], [header, pred, exc])

    def test_all_blocks_claimed_is_complete(self):
        header, pred, exc = (_header_and_first_row(), _predicate_row(),
                             _exception_row())
        assert not _pass1_region_incomplete(
            _DETECTION_REGION, 0, [header, pred, exc], [header, pred, exc])

    def test_blocks_on_other_pages_are_ignored(self):
        pred, exc = _predicate_row(), _exception_row()
        elsewhere = _block(list(_header_and_first_row().lines), page_num=7)
        assert not _pass1_region_incomplete(
            _DETECTION_REGION, 0, [pred, exc], [pred, exc, elsewhere])

    def test_blocks_outside_the_region_are_ignored(self):
        pred, exc = _predicate_row(), _exception_row()
        below = _block([_cell("Add a new section", 71.6, 665.2, 200.0)])
        assert not _pass1_region_incomplete(
            _DETECTION_REGION, 0, [pred, exc], [pred, exc, below])


class TestDetectionTableNotSplit:
    """End-to-end: a 4-row MuPDF table must not become a headerless 2-row one."""

    def _mupdf_tables(self):
        return {0: [{
            "bbox": _DETECTION_REGION,
            "row_count": 4,
            "col_count": 2,
            "cells": [],
            "header_names": None,
            "extract": [],
            "rot": None,
        }]}

    def test_data_rows_never_form_a_table_without_their_header(self):
        blocks = [_header_and_first_row(), _predicate_row(), _exception_row()]
        sections, _ = detect_tables(
            blocks, page_mupdf_tables=self._mupdf_tables())
        for sec in sections:
            text = " ".join(
                "".join(s.text for s in cell)
                for row in (sec.columns or []) for cell in row)
            if "predicate_false" in text:
                assert "Name" in text, (
                    "data rows were tabled without the header block")
