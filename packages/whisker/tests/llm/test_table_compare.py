#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Hermetic grid-signal tests for table_compare (no PDF, no pod)."""

from __future__ import annotations

from whisker.det.llm_readability.models import FORMAT_PIPE, TableUnit
from whisker.llm.table_compare import (
    GRID_EQUAL,
    GRID_EXTRA_OR_MISSING_ROWS,
    GRID_ROW0_MISMATCH,
    GRID_UNRELIABLE,
    TableCompareResult,
    TableGridMatch,
    _header_words_straddle,
    _is_pseudo_header,
    _row0_straddles,
    classify_grid_pair,
    grid_match_for_unit,
    grid_pairing_note,
    grid_signal_for_unit,
)


def _unit(cells: list[list[str]]) -> TableUnit:
    return TableUnit(
        index=0,
        fmt=FORMAT_PIPE,
        cells=tuple(tuple(row) for row in cells),
    )


def _result(*matches: TableGridMatch, unreliable: bool = False) -> TableCompareResult:
    return TableCompareResult(
        total_source_tables=len(matches),
        total_candidate_tables=sum(1 for m in matches if m.candidate_header is not None),
        matched_tables=sum(1 for m in matches if m.candidate_header is not None),
        grid_unreliable=unreliable,
        matches=list(matches),
    )


class TestClassifyGridPair:
    def test_t5_row0_mismatch(self):
        source = [
            ["Property", "accumulate", "scan", "reduce", "proposed"],
            ["Specification model", "Sequential left fold", "GENERALIZED_NONCOMMUTATIVE_REDUCE", "", ""],
        ]
        candidate = [
            ["Specification model", "Sequential left fold", "GENERALIZED_NONCOMMUTATIVE_REDUCE", "", ""],
            ["Grouping", "left fold", "binary", "", ""],
        ]
        assert classify_grid_pair(source, candidate) == GRID_ROW0_MISMATCH

    def test_t7_extra_source_rows(self):
        source = [
            ["Property", "Sequential", "Parallel"],
            ["Standard Section", "21.2", "21.3"],
            ["Evaluation Order", "left", "unspecified"],
            ["Grouping", "fold", "reduce"],
            ["Complexity", "linear", "log"],
        ]
        candidate = [
            ["Property", "Sequential", "Parallel"],
            ["Grouping", "fold", "reduce"],
            ["Complexity", "linear", "log"],
        ]
        assert classify_grid_pair(source, candidate) == GRID_EXTRA_OR_MISSING_ROWS

    def test_t0_identical_cells_are_equal(self):
        grid = [
            ["Topic", "Refs"],
            ["Polls, §4, §5, Appendix B, N", "yes"],
        ]
        assert classify_grid_pair(grid, grid) == GRID_EQUAL

    def test_missing_source_is_unreliable(self):
        assert classify_grid_pair(None, [["A", "B"]]) == GRID_UNRELIABLE
        assert classify_grid_pair([["A"]], [["A"]], unreliable=True) == GRID_UNRELIABLE


class TestGridSignalForUnit:
    def test_pairs_t5_by_candidate_header(self):
        unit = _unit([
            ["Specification model", "Sequential left fold", "GENERALIZED_NONCOMMUTATIVE_REDUCE"],
            ["Grouping", "left fold", "binary"],
        ])
        match = TableGridMatch(
            table_index=0,
            page=1,
            source_header=("Property", "accumulate", "scan"),
            candidate_header=("Specification model", "Sequential left fold", "GENERALIZED_NONCOMMUTATIVE_REDUCE"),
            source_row_count=3,
            candidate_row_count=2,
            row0_mismatch=True,
            extra_or_missing_rows=True,
        )
        assert grid_signal_for_unit(unit, _result(match)) == GRID_ROW0_MISMATCH

    def test_t0_equal_match(self):
        unit = _unit([
            ["Topic", "Refs"],
            ["Polls, §4, §5, Appendix B, N", "yes"],
        ])
        match = TableGridMatch(
            table_index=0,
            page=1,
            source_header=("Topic", "Refs"),
            candidate_header=("Topic", "Refs"),
            source_row_count=2,
            candidate_row_count=2,
            row0_mismatch=False,
            extra_or_missing_rows=False,
        )
        assert grid_signal_for_unit(unit, _result(match)) == GRID_EQUAL

    def test_unreliable_extract(self):
        unit = _unit([["A", "B"], ["1", "2"]])
        assert grid_signal_for_unit(unit, _result(unreliable=True)) == GRID_UNRELIABLE

    def test_candidate_less_pseudo_grid_is_not_paired(self):
        # P3978R0 (#424): an empty poll form used to pair with a 24-column
        # page-layout pseudo-grid via a one-letter substring hit
        # ("N" in "ocument Number:"). The source grid never found a
        # candidate, so its row0_mismatch is synthetic and must neither
        # confirm the det class nor supply the "PDF source header" quoted
        # into the typed question.
        unit = _unit([
            ["SF", "F", "N", "A", "SA"],
            ["", "", "", "", ""],
        ])
        match = TableGridMatch(
            table_index=0,
            page=1,
            source_header=("", "D", "ocument Number:", "P3978R", "0") + ("",) * 19,
            candidate_header=None,
            source_row_count=46,
            candidate_row_count=0,
            row0_mismatch=True,
            extra_or_missing_rows=True,
        )
        assert grid_match_for_unit(unit, _result(match)) is None
        assert grid_signal_for_unit(unit, _result(match)) == GRID_UNRELIABLE

    def _poll_unit(self) -> TableUnit:
        return _unit([
            ["SF", "F", "N", "A", "SA"],
            ["", "", "", "", ""],
        ])

    def _p3373r2_match(self, *, pseudo: bool) -> TableGridMatch:
        # P3373R2 (#425): _match_tables paired the page-1 pseudo-grid
        # ``Of Operati | on Stat | es and | Their Life | tim`` with the
        # same-width poll table at header score 0, so the match carries a
        # measured row0_mismatch and confirmed truncated_leak on T0-T2.
        return TableGridMatch(
            table_index=0,
            page=1,
            source_header=("Of Operati", "on Stat", "es and", "Their Life", "tim"),
            candidate_header=("SF", "F", "N", "A", "SA"),
            source_row_count=57,
            candidate_row_count=2,
            row0_mismatch=True,
            extra_or_missing_rows=False,
            source_pseudo=pseudo,
        )

    def test_pseudo_same_width_grid_is_not_paired(self):
        unit = self._poll_unit()
        result = _result(self._p3373r2_match(pseudo=True))
        assert grid_match_for_unit(unit, result) is None
        assert grid_signal_for_unit(unit, result) == GRID_UNRELIABLE

    def test_non_pseudo_same_width_grid_still_pairs(self):
        # The score-0 pairing itself is untouched: a T5 wrong header has
        # zero overlap with the source header by definition.
        unit = self._poll_unit()
        result = _result(self._p3373r2_match(pseudo=False))
        assert grid_signal_for_unit(unit, result) == GRID_ROW0_MISMATCH

    def test_pseudo_grid_excluded_from_column_fallback(self):
        unit = _unit([
            ["Property", "Path A", "Path B"],
            ["Type erasure", "yes", "no"],
        ])
        pseudo = TableGridMatch(
            table_index=0,
            page=1,
            source_header=("Docume", "nt Number:", "P4127R0"),
            candidate_header=("Mechanism", "Delivers to operator new?", "Reduces to"),
            source_row_count=73,
            candidate_row_count=5,
            row0_mismatch=True,
            extra_or_missing_rows=False,
            source_pseudo=True,
        )
        real = TableGridMatch(
            table_index=8,
            page=9,
            source_header=("Mechanism", "Delivers to operator new?", "Reduces"),
            candidate_header=("Context", "Wrong value", "Consequence"),
            source_row_count=29,
            candidate_row_count=4,
            row0_mismatch=True,
            extra_or_missing_rows=False,
        )
        # Two 3-column matches would make the column fallback ambiguous;
        # the pseudo one does not count, so the real grid is the unique hit.
        assert grid_match_for_unit(unit, _result(pseudo, real)) is real

    def test_pairing_note_distinguishes_no_grid_from_rejected(self):
        unit = self._poll_unit()
        assert grid_pairing_note(unit, None) == "no source compare"
        assert grid_pairing_note(unit, _result()) == "no source grids"
        assert grid_pairing_note(
            unit, _result(self._p3373r2_match(pseudo=True)),
        ) == "no pairing, 1 pseudo-grid excluded"
        assert grid_pairing_note(unit, _result(self._p3373r2_match(pseudo=False))) == ""
        other = TableGridMatch(
            table_index=0, page=1,
            source_header=("Field", "Value"), candidate_header=("Field", "Value"),
            source_row_count=3, candidate_row_count=3,
            row0_mismatch=False, extra_or_missing_rows=False,
        )
        assert grid_pairing_note(unit, _result(other)) == "no pairing"


class TestPseudoHeader:
    """Row-0 rules that keep page-layout grids out of the unit pairing (#425)."""

    # Word and cell x-spans measured on the real PDFs (PyMuPDF points).
    P3373R2_P1_WORDS = [
        (72.0, 99.4), (106.7, 220.8), (228.0, 301.7),
        (308.9, 352.3), (359.5, 418.7), (426.0, 517.0),
    ]
    P3373R2_P1_CELLS = [
        (72.0, 192.4), (192.4, 271.6), (271.6, 359.1), (359.1, 464.6), (464.6, 507.0),
    ]
    P4127R0_P9_WORDS = [
        (66.7, 112.9), (260.3, 292.5), (294.5, 302.8),
        (304.8, 337.6), (341.7, 357.8), (448.2, 481.4),
    ]
    P4127R0_P9_CELLS = [(66.7, 259.8), (259.8, 448.2), (448.2, 481.4)]
    P4182R1_P8_WORDS = [(66.7, 85.9), (236.2, 258.5)]
    P4182R1_P8_CELLS = [
        (66.7, 236.2), (236.2, 310.6), (310.6, 364.8), (364.8, 418.1), (418.1, 461.7),
    ]

    def test_p3373r2_title_line_straddles(self):
        # "Operation", "States", "Lifetime" each span two cell boxes.
        assert _header_words_straddle(self.P3373R2_P1_WORDS, self.P3373R2_P1_CELLS)

    def test_p4127r0_mechanism_header_does_not_straddle(self):
        assert not _header_words_straddle(self.P4127R0_P9_WORDS, self.P4127R0_P9_CELLS)

    def test_p4182r1_field_value_does_not_straddle(self):
        assert not _header_words_straddle(self.P4182R1_P8_WORDS, self.P4182R1_P8_CELLS)

    def test_none_cell_is_skipped(self):
        assert not _header_words_straddle([(10.0, 20.0)], [None, (0.0, 30.0)])

    def test_overlap_within_tolerance_is_not_a_straddle(self):
        # A word starting 0.3pt before the column boundary is a kerning
        # artefact, not a cut word.
        assert not _header_words_straddle([(100.0, 150.0)], [(72.0, 100.3), (100.3, 200.0)])

    def test_fewer_than_two_alphabetic_cells_is_pseudo(self):
        for cells in (
            ["}", "", ""],                              # P4003R0 G34 (T3/T5-T7)
            ["", "}", ""],                              # P4003R0 G66
            ["// For free functions", "", "", "", ""],  # P4003R0 G22 (T1)
            ["References", "", ""],                     # P4127R0 G18
            ["21", "PROPOSAL", "", ""],                 # P4003R0 G0 title page
            [",", ", &", "", "", "", ""],               # P3373R2 G16
            ["", "", "", "", ""],                       # P4127R0 G7
        ):
            assert _is_pseudo_header(cells), cells

    def test_code_line_is_pseudo(self):
        for cells in (
            # P3373R2 G6: the 5-column code line T0-T2 re-pair to once G0 is
            # excluded; without this rule they keep row0_mismatch (#425).
            ["const auto", "a = [", "", "", ""],
            ["constexpr bool", "nothrow = see below;\u200b", ""],      # P3373R2 G19
            ["std::coroutine handle", "<> h;", ""],                    # P4003R2
            ["struct S", "{", ""],
        ):
            assert _is_pseudo_header(cells), cells

    def test_real_headers_are_not_pseudo(self):
        for cells in (
            ["Mechanism", "Delivers to operator new?", "Reduces"],      # P4127R0 G8
            ["Field", "Value", "", "", ""],                            # P4182R1 G7
            ["Platform", "Frame Allocator", "Time (ms)", "Speedup"],   # ")" is not code
            ["SF", "F", "N", "A", "SA"],
            ["expression", "return type", "assertion/note pre/post-conditions"],
            ["Property", "accumulate", "scan", "reduce", "proposed"],
        ):
            assert not _is_pseudo_header(cells), cells

    def test_title_block_is_pseudo(self):
        for cells in (
            ["Document", "Number:", "P4007R0"],        # P4007R0 G0, whole words
            ["Document Number:", "", "P4003R2"],
            ["document no.", "P1234R0"],
        ):
            assert _is_pseudo_header(cells), cells

    def test_title_block_label_is_word_bounded(self):
        for cells in (
            ["Document", "Notes"],           # "document no" as a prefix
            ["Document", "Normative?"],
            ["Documents", "Number of NB comments"],
        ):
            assert not _is_pseudo_header(cells), cells

    def test_row0_straddles_reads_pymupdf_geometry(self):
        # Duck-typed PyMuPDF objects: rows[0].cells are (x0, y0, x1, y1) or
        # None, rows[0].bbox is the row rectangle, page.get_text("words",
        # clip=) yields (x0, y0, x1, y1, text, ...).
        class Row:
            def __init__(self, cells, bbox):
                self.cells = cells
                self.bbox = bbox

        class Table:
            def __init__(self, row):
                self.rows = [row]

        class Page:
            def __init__(self, words):
                self._words = words

            def get_text(self, kind, clip=None):
                assert kind == "words"
                return self._words

        row = Row(
            cells=[(72.0, 56.0, 192.4, 68.0), None, (192.4, 56.0, 271.6, 68.0)],
            bbox=(72.0, 56.0, 271.6, 68.0),
        )
        cut = Page([(106.7, 56.0, 220.8, 68.0, "Operation", 0, 0, 0)])
        clean = Page([(72.0, 56.0, 99.4, 68.0, "Of", 0, 0, 0)])
        assert _row0_straddles(cut, Table(row))
        assert not _row0_straddles(clean, Table(row))

    def test_row0_straddles_without_geometry_is_not_pseudo(self):
        class NoRows:
            rows: list = []

        assert not _row0_straddles(object(), NoRows())

    def test_stable_name_row_is_not_pseudo(self):
        # N5040 G12: row 0 of a page grid is a data row of the NB-comment
        # table; "]" is a stable-name closer, not code. Fleet audit
        # 2026-09-18: with "]" in the tail set this real pairing was lost.
        assert not _is_pseudo_header(
            ["54", "US 75-138 20.3.2.2 [util.smartptr.shared]", "Accepted"]
        )
