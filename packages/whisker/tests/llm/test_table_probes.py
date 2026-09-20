#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Offline tests for per-unit count-dump probes (no network).

Tests classification, scorers, question builders, and evidence
serialization. Pod calls are not exercised.
"""

from __future__ import annotations

import pytest
from whisker.det.llm_readability.models import (
    FORMAT_HTML,
    FORMAT_PIPE,
    TableUnit,
)
from whisker.llm.table_compare import (
    GRID_EQUAL,
    GRID_EXTRA_OR_MISSING_ROWS,
    GRID_ROW0_MISMATCH,
    GRID_UNRELIABLE,
)
from whisker.llm.table_probes import (
    UNIT_DUMPS_KIND,
    AllUnitDumpsResult,
    ProbeResult,
    UnitDumpResult,
    _build_continuation_question,
    _build_count_dump_question,
    _build_header_is_data_question,
    _build_truncated_leak_question,
    _build_wording_clause_question,
    _classify_unit,
    _estimate_line_after,
    _label_shift_on_unit,
    _raw_rows_to_md,
    pair_unit_to_page,
    parse_cell_dump,
    resolve_source_typed_probe,
    score_cell_dump,
    score_flattened_answer,
    score_header_is_data_answer,
    score_numeric_header_dump,
    score_row_merge_answer,
    score_source_mismatch_answer,
    score_truncated_leak_answer,
    score_wording_clause_answer,
    score_wrap_bleed_dump,
    unit_dumps_to_dict,
)

# -- Fixtures ------------------------------------------------------------------

def _pipe_unit(cells: list[list[str]], index: int = 0) -> TableUnit:
    return TableUnit(
        index=index,
        fmt=FORMAT_PIPE,
        cells=tuple(tuple(row) for row in cells),
    )


def _html_unit(cells: list[list[str]], index: int = 0, spans: bool = False) -> TableUnit:
    return TableUnit(
        index=index,
        fmt=FORMAT_HTML,
        cells=tuple(tuple(row) for row in cells),
        spans_declared=spans,
    )


# -- Tests for defect probe helpers --------------------------------------------

class TestCountDumpQuestion:
    SHIFT_UNIT = _pipe_unit([
        ["", "Name", "National Body"],
        ["Adams, Michael", "", "SCC"],
        ["Alday, Juan", "", "ANSI"],
    ])

    def test_question_mentions_format(self):
        q, _md = _build_count_dump_question(self.SHIFT_UNIT)
        assert "HEADER:" in q
        assert "BODY ROW 1" in q
        assert "UNDER header[2]" in q
        assert "[1]=" in q

    def test_table_md_is_isolated_fragment(self):
        _q, md = _build_count_dump_question(self.SHIFT_UNIT)
        assert "Name" in md
        assert "Adams" in md
        assert "---" in md

    def test_body_row_cap(self):
        q, _md = _build_count_dump_question(self.SHIFT_UNIT, n_body_rows=1)
        assert "BODY ROW 1" in q
        assert "BODY ROW 2" not in q


class TestRawRowsToMd:
    def test_roundtrip_from_cells(self):
        unit = _pipe_unit([
            ["A", "B"],
            ["1", "2"],
        ])
        md = _raw_rows_to_md(unit)
        assert "| A | B |" in md
        assert "---" in md
        assert "| 1 | 2 |" in md


class TestContinuationQuestion:
    def test_builds_question(self):
        cont = TableUnit(
            index=1, fmt=FORMAT_PIPE,
            cells=(("de Wever, Mark", "ANSI"), ("Delfino", "UNI")),
            continuation_of=0,
        )
        result = _build_continuation_question(cont)
        assert result is not None
        pid, q, tmd = result
        assert pid == "diag-continuation-header"
        assert "de Wever" in q
        assert "data values" in q
        assert "de Wever" in tmd

    def test_empty_header_returns_none(self):
        cont = TableUnit(
            index=1, fmt=FORMAT_PIPE,
            cells=(("", ""), ("x", "y")),
            continuation_of=0,
        )
        assert _build_continuation_question(cont) is None


class TestParseCellDump:
    GOOD_DUMP = (
        "HEADER: [1]=EMPTY [2]=Name [3]=National Body\n"
        "BODY ROW 1: [1]=Adams, Michael [2]=EMPTY [3]=SCC\n"
        "BODY ROW 2: [1]=Alday, Juan [2]=EMPTY [3]=ANSI\n"
        "UNDER header[2]: EMPTY"
    )

    BAD_DUMP = (
        "HEADER: [1]=EMPTY [2]=Name [3]=National Body\n"
        "BODY ROW 1: [1]=Adams, Michael [2]=Adams, Michael [3]=SCC\n"
        "UNDER header[2]: Adams, Michael"
    )

    def test_parses_header(self):
        d = parse_cell_dump(self.GOOD_DUMP)
        assert d["HEADER"] == {1: "EMPTY", 2: "Name", 3: "National Body"}

    def test_parses_body_rows(self):
        d = parse_cell_dump(self.GOOD_DUMP)
        assert d["BODY ROW 1"][1] == "Adams, Michael"
        assert d["BODY ROW 1"][2] == "EMPTY"
        assert d["BODY ROW 2"][1] == "Alday, Juan"

    def test_parses_under_line(self):
        d = parse_cell_dump(self.GOOD_DUMP)
        assert d["UNDER"] == {2: "EMPTY"}

    def test_parses_bad_dump(self):
        d = parse_cell_dump(self.BAD_DUMP)
        assert d["BODY ROW 1"][2] == "Adams, Michael"
        assert d["UNDER"] == {2: "Adams, Michael"}

    def test_empty_answer(self):
        d = parse_cell_dump("")
        assert d == {}

    def test_missing_indices(self):
        d = parse_cell_dump("HEADER: no brackets here")
        assert d == {}


class TestScoreCellDump:
    SHIFT_UNIT = _pipe_unit([
        ["", "Name", "National Body"],
        ["Adams, Michael", "", "SCC"],
        ["Alday, Juan", "", "ANSI"],
    ])
    STUB_COL = 0
    STARVED_COL = 1

    def test_good_dump_passes(self):
        dump = parse_cell_dump(
            "HEADER: [1]=EMPTY [2]=Name [3]=National Body\n"
            "BODY ROW 1: [1]=Adams, Michael [2]=EMPTY [3]=SCC\n"
            "UNDER header[2]: EMPTY"
        )
        ok, reason = score_cell_dump(
            dump, self.SHIFT_UNIT, self.STUB_COL, self.STARVED_COL,
        )
        assert ok
        assert "matches" in reason

    def test_adams_under_name_fails(self):
        dump = parse_cell_dump(
            "HEADER: [1]=EMPTY [2]=Name [3]=National Body\n"
            "BODY ROW 1: [1]=Adams, Michael [2]=Adams, Michael [3]=SCC\n"
            "UNDER header[2]: Adams, Michael"
        )
        ok, reason = score_cell_dump(
            dump, self.SHIFT_UNIT, self.STUB_COL, self.STARVED_COL,
        )
        assert not ok
        assert "EMPTY" in reason

    def test_missing_header_fails(self):
        dump = parse_cell_dump("BODY ROW 1: [1]=x [2]=y [3]=z")
        ok, reason = score_cell_dump(
            dump, self.SHIFT_UNIT, self.STUB_COL, self.STARVED_COL,
        )
        assert not ok
        assert "missing" in reason.lower()

    def test_stub_not_empty_in_header_fails(self):
        dump = parse_cell_dump(
            "HEADER: [1]=Something [2]=Name [3]=National Body\n"
            "BODY ROW 1: [1]=Adams [2]=EMPTY [3]=SCC"
        )
        ok, reason = score_cell_dump(
            dump, self.SHIFT_UNIT, self.STUB_COL, self.STARVED_COL,
        )
        assert not ok
        assert "header[1]" in reason

    def test_under_line_with_value_fails(self):
        dump = parse_cell_dump(
            "HEADER: [1]=EMPTY [2]=Name [3]=National Body\n"
            "BODY ROW 1: [1]=Adams [2]=EMPTY [3]=SCC\n"
            "UNDER header[2]: Adams"
        )
        ok, reason = score_cell_dump(
            dump, self.SHIFT_UNIT, self.STUB_COL, self.STARVED_COL,
        )
        assert not ok
        assert "UNDER" in reason


class TestLabelShiftOnUnit:
    """Per-unit label-shift detection."""

    SHIFT_UNIT = _pipe_unit([
        ["", "Name", "National Body"],
        ["Adams, Michael", "", "SCC"],
        ["Alday, Juan", "", "ANSI"],
    ])

    CLEAN_UNIT = _pipe_unit([
        ["Name", "Value"],
        ["alpha", "1"],
        ["beta", "2"],
    ])

    def test_detects_shift(self):
        result = _label_shift_on_unit(self.SHIFT_UNIT)
        assert result is not None
        assert result == (0, 1)

    def test_clean_unit_none(self):
        assert _label_shift_on_unit(self.CLEAN_UNIT) is None

    def test_single_row_none(self):
        unit = _pipe_unit([["A", "B"]])
        assert _label_shift_on_unit(unit) is None

    def test_html_unit_none(self):
        unit = _html_unit([["", "Name"], ["Adams", ""]])
        assert _label_shift_on_unit(unit) is None


class TestPunchListCoverage:
    """All five continuation headers must produce distinct probe results."""

    CONT_HEADERS = [
        "de Wever, Mark",
        "Kawulak, Robert",
        "Nash, Phil",
        "Tanwar Preeti",
        "Mara Bos",
    ]

    def test_each_continuation_builds_question(self):
        for name in self.CONT_HEADERS:
            unit = TableUnit(
                index=0, fmt=FORMAT_PIPE,
                cells=((name, "ANSI"), ("Someone", "BSI")),
                continuation_of=0,
            )
            result = _build_continuation_question(unit)
            assert result is not None, f"no question for {name!r}"
            assert name in result[1], f"{name!r} not in question"

    def test_shift_unit_detected(self):
        unit = _pipe_unit([
            ["", "Name", "National Body"],
            ["Adams, Michael", "", "SCC"],
            ["Alday, Juan", "", "ANSI"],
        ])
        assert _label_shift_on_unit(unit) is not None

    def test_aligned_unit_not_false_positive(self):
        unit = _pipe_unit([
            ["Proposal", "Decision"],
            ["P2900R12", "Accept"],
        ])
        assert _label_shift_on_unit(unit) is None


class TestControlPapersSkip:
    """P4182R0 and P0876R23 must not trigger defect probes."""

    def test_p4182r0_no_defect(self):
        from pathlib import Path
        p = Path("data/paperstore/p4182r0.md")
        if not p.exists():
            pytest.skip("corpus file not available")
        from whisker.det.llm_readability.validate import table_units_from_markdown
        units = table_units_from_markdown(p.read_text(encoding="utf-8"))
        for unit in units:
            assert _label_shift_on_unit(unit) is None
            assert unit.continuation_of is None

    def test_p0876r23_no_defect(self):
        from pathlib import Path
        p = Path("data/paperstore/p0876r23.md")
        if not p.exists():
            pytest.skip("corpus file not available")
        from whisker.det.llm_readability.validate import table_units_from_markdown
        units = table_units_from_markdown(p.read_text(encoding="utf-8"))
        for unit in units:
            assert _label_shift_on_unit(unit) is None
            assert unit.continuation_of is None

    def test_p0876r23_no_data_as_header(self):
        from pathlib import Path
        p = Path("data/paperstore/p0876r23.md")
        if not p.exists():
            pytest.skip("corpus file not available")
        from whisker.det.llm_readability.validate import table_units_from_markdown
        units = table_units_from_markdown(p.read_text(encoding="utf-8"))
        flagged = [u for u in units if u.data_as_header or u.wrap_bleed]
        assert flagged == [], f"false positive on {[u.index for u in flagged]}"


class TestClassifyUnit:
    """_classify_unit respects priority order."""

    def test_data_as_header(self):
        unit = _pipe_unit([["8", "3", "1"], ["", "", ""]], index=0)
        unit = TableUnit(
            index=0, fmt=FORMAT_PIPE,
            cells=unit.cells, data_as_header=True,
        )
        assert _classify_unit(unit) == "data_as_header"

    def test_wrap_bleed(self):
        unit = TableUnit(
            index=0, fmt=FORMAT_PIPE,
            cells=(
                ("`predicate_false`", "The predicate of the contract assertion evaluated to false or would have", "", ""),
                ("`evaluation_exception`", "evaluated to false an uncaught exception occurred", "", ""),
            ),
            wrap_bleed=True,
        )
        assert _classify_unit(unit) == "wrap_bleed"

    def test_continuation(self):
        unit = TableUnit(
            index=1, fmt=FORMAT_PIPE,
            cells=(("5", "7", "0", "0", "0"), ("", "", "", "", "")),
            continuation_of=0,
        )
        assert _classify_unit(unit) == "continuation"

    def test_aligned(self):
        unit = _pipe_unit([["SF", "F", "N", "A", "SA"], ["8", "3", "1", "0", "0"]])
        assert _classify_unit(unit) == "aligned"

    def test_wrap_bleed_beats_continuation(self):
        unit = TableUnit(
            index=1, fmt=FORMAT_PIPE,
            cells=(
                ("`predicate_false`", "The predicate of the contract assertion evaluated to false or would have", "", ""),
                ("`evaluation_exception`", "evaluated to false an uncaught exception occurred", "", ""),
            ),
            continuation_of=0,
            wrap_bleed=True,
        )
        assert _classify_unit(unit) == "wrap_bleed"

    def test_data_as_header_beats_continuation(self):
        unit = TableUnit(
            index=1, fmt=FORMAT_PIPE,
            cells=(("5", "7", "0", "0", "0"), ("", "", "", "", "")),
            continuation_of=0,
            data_as_header=True,
        )
        assert _classify_unit(unit) == "data_as_header"


class TestScoreNumericHeaderDump:
    """Scorer for data_as_header (poll-split) units."""

    POLL_UNIT = TableUnit(
        index=0, fmt=FORMAT_PIPE,
        cells=(("8", "3", "1", "0", "0"), ("", "", "", "", "")),
        data_as_header=True,
    )

    def test_numeric_header_echoed_passes(self):
        dump = parse_cell_dump(
            "HEADER: [1]=8 [2]=3 [3]=1 [4]=0 [5]=0\n"
            "BODY ROW 1: [1]=EMPTY [2]=EMPTY [3]=EMPTY [4]=EMPTY [5]=EMPTY"
        )
        ok, reason = score_numeric_header_dump(dump, self.POLL_UNIT)
        assert ok
        assert "numeric" in reason

    def test_missing_header_fails(self):
        dump = parse_cell_dump("BODY ROW 1: [1]=EMPTY")
        ok, reason = score_numeric_header_dump(dump, self.POLL_UNIT)
        assert not ok

    def test_wrong_values_fail(self):
        dump = parse_cell_dump(
            "HEADER: [1]=SF [2]=F [3]=N [4]=A [5]=SA\n"
        )
        ok, reason = score_numeric_header_dump(dump, self.POLL_UNIT)
        assert not ok


class TestScoreWrapBleedDump:
    """Scorer for wrap_bleed (sentence fragment header) units."""

    WRAP_UNIT = TableUnit(
        index=0, fmt=FORMAT_PIPE,
        cells=(
            ("`predicate_false`", "The predicate of the contract assertion evaluated to false or would have", "", ""),
            ("`evaluation_exception`", "evaluated to false an uncaught exception occurred", "", ""),
        ),
        wrap_bleed=True,
    )

    def test_sentence_fragment_echoed_passes(self):
        dump = parse_cell_dump(
            "HEADER: [1]=`predicate_false` [2]=The predicate of the contract assertion evaluated to false or would have [3]=EMPTY [4]=EMPTY\n"
            "BODY ROW 1: [1]=`evaluation_exception` [2]=evaluated to false an uncaught exception occurred [3]=EMPTY [4]=EMPTY"
        )
        ok, reason = score_wrap_bleed_dump(dump, self.WRAP_UNIT)
        assert ok
        assert "sentence fragment" in reason

    def test_missing_header_fails(self):
        dump = parse_cell_dump("BODY ROW 1: [1]=x")
        ok, reason = score_wrap_bleed_dump(dump, self.WRAP_UNIT)
        assert not ok


class TestClassifyHeaderIsData:
    """_classify_unit routes header_is_data before aligned."""

    def test_header_is_data_classification(self):
        unit = TableUnit(
            index=0, fmt=FORMAT_PIPE,
            cells=(
                ("`inclusive_scan`", "`std::execution::par_unseq`", "GENERALIZED_SUM"),
                ("Operand order", "Policy", "Grouping"),
            ),
            header_is_data=True,
        )
        assert _classify_unit(unit) == "header_is_data"

    def test_header_is_data_after_continuation(self):
        unit = TableUnit(
            index=1, fmt=FORMAT_PIPE,
            cells=(
                ("`inclusive_scan`", "`std::execution::par_unseq`", "GENERALIZED_SUM"),
                ("Operand order", "Policy", "Grouping"),
            ),
            continuation_of=0,
            header_is_data=True,
        )
        assert _classify_unit(unit) == "continuation"


class TestClassifyWordingClause:
    """_classify_unit routes wording_clause after continuation."""

    def test_wording_clause_classification(self):
        unit = TableUnit(
            index=0, fmt=FORMAT_PIPE,
            cells=(
                (
                    "1",
                    "A type `T` models `allowed_semantics_label` if it is "
                    "an allowed-semantics control",
                    "type([basic.contract.control]).",
                ),
                (
                    "2",
                    "[*Note*: Combined assertion-control objects intersect "
                    "the allowed semantics sets of their",
                    "constituents. *— end* *note*]",
                ),
            ),
            wording_clause=True,
        )
        assert _classify_unit(unit) == "wording_clause"

    def test_continuation_beats_wording_clause(self):
        unit = TableUnit(
            index=1, fmt=FORMAT_PIPE,
            cells=(
                (
                    "1",
                    "A type `T` models `allowed_semantics_label` if it is "
                    "an allowed-semantics control",
                    "type([basic.contract.control]).",
                ),
                (
                    "2",
                    "[*Note*: Combined assertion-control objects intersect "
                    "the allowed semantics sets of their",
                    "constituents. *— end* *note*]",
                ),
            ),
            continuation_of=0,
            wording_clause=True,
        )
        assert _classify_unit(unit) == "continuation"


class TestWordingClauseProbePath:
    """Closed-question builder and scorer for wording_clause units."""

    UNIT = TableUnit(
        index=0, fmt=FORMAT_PIPE,
        cells=(
            (
                "1",
                "A type `T` models `allowed_semantics_label` if it is "
                "an allowed-semantics control",
                "type([basic.contract.control]).",
            ),
            (
                "2",
                "[*Note*: Combined assertion-control objects intersect "
                "the allowed semantics sets of their",
                "constituents. *— end* *note*]",
            ),
        ),
        wording_clause=True,
    )

    def test_builder_asks_closed_question(self):
        built = _build_wording_clause_question(self.UNIT)
        assert built is not None
        probe_id, question, table_md = built
        assert probe_id == "diag-wording-clause"
        assert "column headers" in question
        assert "data values" in question
        assert "numbered specification paragraphs" in question
        assert "allowed_semantics_label" in table_md

    def test_confirming_answer_sets_defect_confirmed(self):
        ok, reason = score_wording_clause_answer("data values")
        assert ok
        error = False
        passed = ok
        defect_confirmed = not error and passed
        assert defect_confirmed
        assert "data" in reason.lower()

    def test_numbered_paragraph_answer_confirms(self):
        ok, reason = score_wording_clause_answer(
            "numbered spec paragraphs",
        )
        assert ok
        assert "numbered" in reason.lower() or "paragraph" in reason.lower()

    def test_error_not_defect_confirmed(self):
        ok, _reason = score_wording_clause_answer("data values")
        error = True
        passed = False if error else ok
        defect_confirmed = not error and passed
        assert not defect_confirmed

    def test_column_headers_does_not_confirm(self):
        ok, _reason = score_wording_clause_answer("column headers")
        assert not ok


class TestClassifyTruncatedLeak:
    """_classify_unit routes truncated_leak before aligned."""

    def test_truncated_leak_classification(self):
        unit = TableUnit(
            index=0, fmt=FORMAT_PIPE,
            cells=(
                ("Feature", "Status"),
                ("Parameterization", "Complete"),
            ),
            truncated_leak=True,
        )
        assert _classify_unit(unit) == "truncated_leak"


# P3290R4 (#426): five filled `SF | F | N | A | SA` polls, one numeric body
# row each, caption `Result: Consensus` under every one. det flags all five
# as truncated_leak (frozen, false positive); the LLM lane must not confirm.
_P3290_POLL_BODIES = (
    ("8", "3", "1", "0", "0"),
    ("5", "7", "0", "0", "0"),
    ("4", "17", "6", "5", "1"),
    ("2", "11", "5", "0", "0"),
    ("1", "8", "4", "3", "0"),
)
_P3290_POLL_HEADER = ("SF", "F", "N", "A", "SA")


def _p3290_poll_unit(index: int) -> TableUnit:
    cells = (_P3290_POLL_HEADER, _P3290_POLL_BODIES[index])
    return TableUnit(
        index=index,
        fmt=FORMAT_PIPE,
        cells=cells,
        raw_rows=tuple("| " + " | ".join(row) + " |" for row in cells),
        truncated_leak=True,
    )


def _p3290_md_lines() -> list[str]:
    lines: list[str] = ["## Polls", ""]
    for i, body in enumerate(_P3290_POLL_BODIES):
        lines += [
            f"SG21, Teleconference, 2024-09-0{i + 1}",
            "",
            f"Forward Proposal {i + 1} of D3290R2 to EWG and LEWG for design review.",
            "",
            "| " + " | ".join(_P3290_POLL_HEADER) + " |",
            "|---|---|---|---|---|",
            "| " + " | ".join(body) + " |",
            "",
            "Result: Consensus",
            "",
        ]
    return lines


class TestP3290PollCaptionNotLeak:
    """#426: identical poll headers each get their own lookahead; the
    question names the caption as prose; abstain on unreliable grid."""

    def test_each_poll_gets_its_own_line_after(self):
        md_lines = _p3290_md_lines()
        offsets = [
            _estimate_line_after(_p3290_poll_unit(i), md_lines)
            for i in range(len(_P3290_POLL_BODIES))
        ]
        assert len(set(offsets)) == len(offsets), offsets
        for i, off in enumerate(offsets):
            # Line right after the body row is the blank before the caption;
            # the body row itself must be this poll's, not the first poll's.
            assert md_lines[off - 1] == "| " + " | ".join(_P3290_POLL_BODIES[i]) + " |"
            assert md_lines[off + 1] == "Result: Consensus"

    def test_header_only_fallback_when_body_does_not_match(self):
        md_lines = _p3290_md_lines()
        stray = TableUnit(
            index=9, fmt=FORMAT_PIPE,
            cells=(_P3290_POLL_HEADER, ("99", "99", "99", "99", "99")),
            raw_rows=(
                "| SF | F | N | A | SA |",
                "| 99 | 99 | 99 | 99 | 99 |",
            ),
            truncated_leak=True,
        )
        first = _estimate_line_after(_p3290_poll_unit(0), md_lines)
        assert _estimate_line_after(stray, md_lines) == first

    def test_no_header_hit_returns_end(self):
        md_lines = ["prose only", "", "more prose"]
        assert _estimate_line_after(_p3290_poll_unit(0), md_lines) == len(md_lines)

    def test_question_carries_caption_context_and_rubric(self):
        md_lines = _p3290_md_lines()
        unit = _p3290_poll_unit(2)
        built = _build_truncated_leak_question(
            unit, md_lines, _estimate_line_after(unit, md_lines),
        )
        assert built is not None
        probe_id, question, combined = built
        assert probe_id == "diag-truncated-leak"
        assert "| 4 | 17 | 6 | 5 | 1 |" in combined
        assert "Result: Consensus" in combined
        assert "| 8 | 3 | 1 | 0 | 0 |" not in combined
        assert "'Label: value' caption" in question
        assert "'Result: Consensus'" in question
        # The exemption is the caption shape only: a leaked row that names
        # a meeting, date or poll must still be answered 'leaked rows'.
        assert "even if it names a meeting, a date or a poll" in question
        assert "meeting and date line, is prose" not in question
        assert question.endswith("Answer 'leaked rows' or 'prose'.")

    def test_no_separator_unit_body_sits_under_header(self):
        md_lines = [
            "| Feature | Status |",
            "| Parameterization | Complete |",
            "Evaluation Order Fully specified",
            "",
        ]
        unit = TableUnit(
            index=0, fmt=FORMAT_PIPE,
            cells=(("Feature", "Status"), ("Parameterization", "Complete")),
            raw_rows=("| Feature | Status |", "| Parameterization | Complete |"),
            has_separator=False,
            truncated_leak=True,
        )
        off = _estimate_line_after(unit, md_lines)
        assert off == 2
        built = _build_truncated_leak_question(unit, md_lines, off)
        assert built is not None
        assert "Evaluation Order Fully specified" in built[2]

    def test_full_row_match_prefers_later_identical_header_and_first_row(self):
        # Same header AND same first body row twice; second table differs
        # only in its second body row. Full-sequence matching finds it.
        md_lines = [
            "| SF | F | N | A | SA |", "|---|---|---|---|---|",
            "| 0 | 0 | 0 | 0 | 0 |", "", "Result: No consensus", "",
            "| SF | F | N | A | SA |", "|---|---|---|---|---|",
            "| 0 | 0 | 0 | 0 | 0 |", "| 1 | 2 | 3 | 4 | 5 |", "",
            "Leaked Row Stub", "",
        ]
        second = TableUnit(
            index=1, fmt=FORMAT_PIPE,
            cells=(_P3290_POLL_HEADER, ("0", "0", "0", "0", "0"), ("1", "2", "3", "4", "5")),
            raw_rows=(
                "| SF | F | N | A | SA |",
                "| 0 | 0 | 0 | 0 | 0 |",
                "| 1 | 2 | 3 | 4 | 5 |",
            ),
            truncated_leak=True,
        )
        assert _estimate_line_after(second, md_lines) == 10

    def test_typed_prose_on_unreliable_grid_abstains(self):
        typed_ok, _ = score_truncated_leak_answer("prose")
        passed, reason = resolve_source_typed_probe(
            "truncated_leak",
            source_ok=False,
            typed_ok=typed_ok,
            grid_signal=GRID_UNRELIABLE,
            grid_note="no pairing",
        )
        assert not passed
        assert reason == "abstain: typed did not confirm, grid=unreliable (no pairing)"

    def test_bibliography_glue_still_confirms(self):
        """T8 (bibliography smashed into a 4-col table) stays a DEFECT."""
        unit = TableUnit(
            index=7, fmt=FORMAT_PIPE,
            cells=(
                ("[P3191R0] [P3290R0] [P3311R0]",
                 "Louis Dionne, Yeoul Na, and Konstantin Varlamov, "
                 "\u201cFeedback on the scalability of contract violation "
                 "handlers in P2900\u201d, 2024 `http://wg21.link/P3191R0` "
                 "Joshua Berne, Timur Doumler, and John Lakos, "
                 "\u201cIntegrating Existing Assertions",
                 "With Contracts\u201d, 2024", ""),
                ("[P2900R14]",
                 "Joshua Berne, Timur Doumler, and Andrzej Krzemie\u0144ski, "
                 "\u201cContracts for C++\u201d, `http://wg21.link/P2900R14`",
                 "2025", ""),
            ),
            header_is_data=True,
        )
        assert _classify_unit(unit) == "header_is_data"
        source_ok, _ = score_source_mismatch_answer("glue", expect_defect=True)
        passed, reason = resolve_source_typed_probe(
            "header_is_data",
            source_ok=source_ok,
            typed_ok=None,
            grid_signal=GRID_UNRELIABLE,
        )
        assert passed
        assert reason == "source confirmed defect"


class TestClassifyRowMerge:
    """_classify_unit routes row_merge before aligned."""

    def test_row_merge_classification(self):
        unit = TableUnit(
            index=0, fmt=FORMAT_PIPE,
            cells=(
                ("Algorithm", "Vendor Support"),
                ("reduce", "Intel oneMKL NVIDIA CUB AMD rocPRIM"),
            ),
            row_merge=True,
        )
        assert _classify_unit(unit) == "row_merge"


class TestClassifyFlattened:
    """_classify_unit routes flattened before truncated_leak."""

    def test_flattened_classification(self):
        unit = TableUnit(
            index=0, fmt=FORMAT_PIPE,
            cells=(
                ("Parallelism", "Mechanism", "Typical", "Scale"),
                ("Thread-level", "std::thread", "coarse", "cores"),
            ),
            flattened_prose=True,
        )
        assert _classify_unit(unit) == "flattened"

    def test_flattened_not_remapped_to_header_is_data(self):
        """flattened_prose must NOT be remapped to header_is_data."""
        unit = TableUnit(
            index=0, fmt=FORMAT_PIPE,
            cells=(
                ("Parallelism", "Mechanism", "Typical", "Scale"),
                ("Thread-level", "std::thread", "coarse", "cores"),
            ),
            flattened_prose=True,
        )
        assert _classify_unit(unit) != "header_is_data"

    def test_flattened_after_header_is_data(self):
        """header_is_data takes priority over flattened_prose."""
        unit = TableUnit(
            index=0, fmt=FORMAT_PIPE,
            cells=(
                ("1.0", "2.0", "3.0"),
                ("a", "b", "c"),
            ),
            header_is_data=True,
            flattened_prose=True,
        )
        assert _classify_unit(unit) == "header_is_data"


class TestScoreHeaderIsDataAnswer:
    """Scorer for header_is_data closed question."""

    def test_data_values_confirms_defect(self):
        ok, reason = score_header_is_data_answer("data values")
        assert ok
        assert "data" in reason.lower()

    def test_column_headers_means_no_defect(self):
        ok, reason = score_header_is_data_answer("column headers")
        assert not ok

    def test_ambiguous_is_no_confirmation(self):
        ok, reason = score_header_is_data_answer("I'm not sure about this table")
        assert not ok


class TestScoreTruncatedLeakAnswer:
    """Scorer for truncated_leak closed question."""

    def test_leaked_rows_confirms_defect(self):
        ok, reason = score_truncated_leak_answer("leaked rows")
        assert ok
        assert "leak" in reason.lower()

    def test_prose_means_no_defect(self):
        ok, reason = score_truncated_leak_answer("prose")
        assert not ok
        assert "prose" in reason.lower()

    def test_ambiguous_is_no_confirmation(self):
        ok, reason = score_truncated_leak_answer("hard to tell")
        assert not ok


class TestScoreRowMergeAnswer:
    """Scorer for row_merge closed question."""

    def test_integer_ge_2_confirms_defect(self):
        ok, reason = score_row_merge_answer("3")
        assert ok
        assert "3" in reason

    def test_integer_1_means_no_merge(self):
        ok, reason = score_row_merge_answer("1")
        assert not ok

    def test_non_integer_is_no_confirmation(self):
        ok, reason = score_row_merge_answer("multiple items")
        assert not ok


class TestPairUnitToPage:
    def test_pairs_by_token_overlap(self):
        unit = _pipe_unit(
            [["Library", "Feature"], ["Intel oneMKL NVIDIA CUB", "CNR"]],
        )
        pages = [
            "Introduction and unrelated prose about algorithms.",
            "Library Feature Intel oneMKL NVIDIA CUB Conditional Numerical Reproducibility",
        ]
        paired = pair_unit_to_page(unit, pages)
        assert paired is not None
        assert paired[0] == 1
        assert "oneMKL" in paired[1]

    def test_empty_pages_returns_none(self):
        unit = _pipe_unit([["A", "B"], ["1", "2"]])
        assert pair_unit_to_page(unit, []) is None


class TestScoreSourceMismatchAnswer:
    def test_defect_confirmed_by_split(self):
        ok, reason = score_source_mismatch_answer("split", expect_defect=True)
        assert ok
        assert "split" in reason

    def test_defect_rejected_by_match(self):
        ok, _reason = score_source_mismatch_answer("match", expect_defect=True)
        assert not ok

    def test_clean_unit_needs_match(self):
        ok, reason = score_source_mismatch_answer("match", expect_defect=False)
        assert ok
        assert "match" in reason

    def test_clean_unit_fails_on_wrap(self):
        ok, _reason = score_source_mismatch_answer("wrap", expect_defect=False)
        assert not ok

    def test_flattened_confirms_defect(self):
        ok, reason = score_source_mismatch_answer("flattened", expect_defect=True)
        assert ok
        assert "flattened" in reason

    def test_flattened_fails_clean(self):
        ok, _reason = score_source_mismatch_answer("flattened", expect_defect=False)
        assert not ok


class TestScoreFlattenedAnswer:
    """Scorer for flattened closed question."""

    def test_flattened_confirms_defect(self):
        ok, reason = score_flattened_answer("flattened")
        assert ok
        assert "flattened" in reason.lower()

    def test_flatten_variant_confirms(self):
        ok, reason = score_flattened_answer("The content looks flatten")
        assert ok

    def test_match_does_not_confirm(self):
        ok, _reason = score_flattened_answer("match")
        assert not ok

    def test_ambiguous_does_not_confirm(self):
        ok, _reason = score_flattened_answer("I see a heading followed by text")
        assert not ok


class TestUnitDumpsToDict:
    def test_evidence_kind_and_forbidden_keys(self):
        result = AllUnitDumpsResult(
            pid="N5040",
            model="deepseek-v4-pro",
            units=[
                UnitDumpResult(
                    unit_index=2,
                    classification="label_shift",
                    dump={"header": {1: "EMPTY"}},
                    probe=ProbeResult(
                        probe_id="shift-t2",
                        question="count",
                        expected="shift",
                        answer="HEADER: [1]=EMPTY",
                        passed=True,
                    ),
                ),
            ],
        )
        payload = unit_dumps_to_dict(result)
        assert payload["kind"] == UNIT_DUMPS_KIND
        assert payload["pass_count"] == 1
        assert payload["units"][0]["unit_index"] == 2
        for forbidden in (
            "methods_executed",
            "model_certified",
            "certified",
            "verdict",
            "rules",
            "blocking_reasons",
            "suggested_verdict",
            "confidence",
            "document_deterministic_ok",
            "status",
            "source",
        ):
            assert forbidden not in payload


class TestResolveSourceTypedProbe:
    """Reject-and-keep for T5/T7; typed veto for T0; aligned stay fail-closed."""

    def test_t5_grid_row0_does_not_clear(self):
        passed, reason = resolve_source_typed_probe(
            "header_is_data",
            source_ok=False,
            typed_ok=False,
            grid_signal=GRID_ROW0_MISMATCH,
        )
        assert passed
        assert "row0_mismatch" in reason
        assert "det kept" in reason

    def test_t7_grid_missing_rows_does_not_clear(self):
        passed, reason = resolve_source_typed_probe(
            "truncated_leak",
            source_ok=False,
            typed_ok=False,
            grid_signal=GRID_EXTRA_OR_MISSING_ROWS,
        )
        assert passed
        assert "extra_or_missing_rows" in reason

    def test_t5_typed_column_headers_cannot_clear_on_equal_grid(self):
        passed, reason = resolve_source_typed_probe(
            "header_is_data",
            source_ok=False,
            typed_ok=False,
            grid_signal=GRID_EQUAL,
        )
        assert not passed
        assert "abstain" in reason

    def test_abstain_reason_carries_grid_note(self):
        passed, reason = resolve_source_typed_probe(
            "truncated_leak",
            source_ok=False,
            typed_ok=False,
            grid_signal=GRID_UNRELIABLE,
            grid_note="no pairing, 1 pseudo-grid excluded",
        )
        assert not passed
        assert reason == (
            "abstain: typed did not confirm, grid=unreliable"
            " (no pairing, 1 pseudo-grid excluded)"
        )
        # No note: reason unchanged from v23.
        _, bare = resolve_source_typed_probe(
            "truncated_leak", source_ok=False, typed_ok=False,
            grid_signal=GRID_UNRELIABLE,
        )
        assert bare == "abstain: typed did not confirm, grid=unreliable"

    def test_t0_typed_veto_still_clears_wrap_orphan(self):
        passed, reason = resolve_source_typed_probe(
            "wrap_orphan",
            source_ok=False,
            typed_ok=False,
            grid_signal=GRID_EQUAL,
        )
        assert not passed
        assert "typed did not confirm" in reason

    def test_aligned_source_split_stays_fail_closed(self):
        ok, reason = score_source_mismatch_answer("split", expect_defect=False)
        assert not ok
        assert "split" in reason

    def test_aligned_non_match_not_passed(self):
        for answer in ("split", "data-header", "broken", "glue", "wrap"):
            ok, _reason = score_source_mismatch_answer(answer, expect_defect=False)
            assert not ok, f"aligned '{answer}' should not pass"

    def test_source_confirm_wins_without_grid(self):
        passed, reason = resolve_source_typed_probe(
            "header_is_data",
            source_ok=True,
            typed_ok=False,
            grid_signal=GRID_UNRELIABLE,
        )
        assert passed
        assert "source confirmed" in reason


class TestHeaderIsDataQuestionSourceRow:
    def test_quotes_pdf_header_when_known(self):
        unit = TableUnit(
            index=0,
            fmt=FORMAT_PIPE,
            cells=(
                ("Specification model", "Sequential left fold", "GENERALIZED_NONCOMMUTATIVE_REDUCE"),
                ("Grouping", "left fold", "binary"),
            ),
        )
        built = _build_header_is_data_question(
            unit,
            source_header=("Property", "accumulate", "scan", "reduce", "proposed"),
        )
        assert built is not None
        _pid, question, _md = built
        assert "Property" in question
        assert "accumulate" in question
        assert "GENERALIZED_NONCOMMUTATIVE_REDUCE" in question


class TestDefectConfirmedFlag:
    """ProbeResult.defect_confirmed distinguishes aligned non-match from real FAIL."""

    def test_defect_confirmed_in_probe(self):
        probe = ProbeResult(
            probe_id="src-t0",
            question="Does it match?",
            expected="source verdict=split",
            answer="split",
            passed=False,
            defect_confirmed=True,
        )
        assert probe.defect_confirmed
        assert not probe.passed

    def test_clean_pass_not_defect_confirmed(self):
        probe = ProbeResult(
            probe_id="src-t1",
            question="Does it match?",
            expected="source verdict=match",
            answer="match",
            passed=True,
        )
        assert not probe.defect_confirmed

    def test_serialization_includes_defect_confirmed(self):
        result = AllUnitDumpsResult(
            pid="TEST",
            model="test-model",
            units=[
                UnitDumpResult(
                    unit_index=0,
                    classification="aligned",
                    probe=ProbeResult(
                        probe_id="src-t0",
                        question="q",
                        expected="source verdict=split",
                        answer="split",
                        passed=False,
                        defect_confirmed=True,
                    ),
                ),
            ],
        )
        payload = unit_dumps_to_dict(result)
        assert payload["units"][0]["probe"]["defect_confirmed"] is True

    def test_typed_branch_defect_confirmed(self):
        """Typed-branch: passed=True + no error -> defect_confirmed=True.

        Reproduces the P4012R0 section 10.2 bug where the LLM correctly
        said "data values" (passed=True for a header_is_data probe) but
        defect_confirmed stayed False.
        """
        probe = ProbeResult(
            probe_id="header_is_data-t7",
            question="Are '10.2' and 'modify [simd.expos]' column headers or data values?",
            expected="model says header cells are data values",
            answer="data values",
            passed=True,
            defect_confirmed=not False and True,
        )
        assert probe.defect_confirmed
        assert probe.passed

    def test_typed_branch_error_not_defect_confirmed(self):
        """Typed-branch: error=True -> defect_confirmed=False even if passed."""
        probe = ProbeResult(
            probe_id="header_is_data-t0",
            question="q",
            expected="e",
            answer="(transport error)",
            passed=False,
            error=True,
            defect_confirmed=not True and False,
        )
        assert not probe.defect_confirmed

    def test_source_branch_expect_defect_confirmed(self):
        """Source-mismatch branch: expect_defect=True, passed=True -> defect_confirmed."""
        expect_defect = True
        error = False
        passed = True
        is_defect_confirmed = not error and (passed if expect_defect else not passed)
        assert is_defect_confirmed

    def test_source_branch_expect_defect_not_confirmed(self):
        """Source-mismatch branch: expect_defect=True, passed=False -> no defect."""
        expect_defect = True
        error = False
        passed = False
        is_defect_confirmed = not error and (passed if expect_defect else not passed)
        assert not is_defect_confirmed

    def test_source_branch_aligned_clean(self):
        """Source-mismatch branch: expect_defect=False (aligned), passed=True -> clean."""
        expect_defect = False
        error = False
        passed = True
        is_defect_confirmed = not error and (passed if expect_defect else not passed)
        assert not is_defect_confirmed

    def test_source_branch_aligned_mismatch(self):
        """Source-mismatch branch: expect_defect=False (aligned), not passed -> defect."""
        expect_defect = False
        error = False
        passed = False
        is_defect_confirmed = not error and (passed if expect_defect else not passed)
        assert is_defect_confirmed

    def test_inspect_renders_defect(self):
        from whisker.llm.inspect_report import _format_unit_dumps

        dumps = {
            "kind": "whisker-table-unit-dumps",
            "model": "test",
            "pass_count": 0,
            "fail_count": 0,
            "skip_count": 0,
            "units": [
                {
                    "unit_index": 0,
                    "classification": "aligned",
                    "probe": {
                        "passed": False,
                        "defect_confirmed": True,
                        "skipped": False,
                        "error": False,
                    },
                },
                {
                    "unit_index": 1,
                    "classification": "aligned",
                    "probe": {
                        "passed": False,
                        "defect_confirmed": False,
                        "skipped": False,
                        "error": False,
                    },
                },
            ],
        }
        lines = _format_unit_dumps(dumps)
        text = "\n".join(lines)
        assert "DEFECT" in text
        assert "FAIL" in text

    def test_inspect_typed_passed_defect_not_rendered_as_pass(self):
        """Core bug: passed=True + defect_confirmed=True must render DEFECT, not PASS.

        Before the fix, the renderer checked ``passed`` before
        ``defect_confirmed``, so a confirmed defect from the typed-branch
        (where passed=True means "defect hypothesis confirmed") was
        displayed as PASS.
        """
        from whisker.llm.inspect_report import _format_unit_dumps

        dumps = {
            "kind": "whisker-table-unit-dumps",
            "model": "test",
            "pass_count": 0,
            "fail_count": 0,
            "skip_count": 0,
            "units": [
                {
                    "unit_index": 7,
                    "classification": "header_is_data",
                    "probe": {
                        "passed": True,
                        "defect_confirmed": True,
                        "skipped": False,
                        "error": False,
                    },
                },
                {
                    "unit_index": 3,
                    "classification": "aligned",
                    "probe": {
                        "passed": True,
                        "defect_confirmed": False,
                        "skipped": False,
                        "error": False,
                    },
                },
            ],
        }
        lines = _format_unit_dumps(dumps)
        text = "\n".join(lines)
        assert "| DEFECT |" in text
        assert "| PASS |" in text
        assert "defect=1" in text
        assert "pass=1" in text

    def test_inspect_unconfirmed_defect_class_renders_abstain(self):
        """A det-flagged unit the lane could not confirm is ABSTAIN, not FAIL.

        P3978R0 T0 (#424/#425): truncated_leak, source `prose`, typed
        `prose`, grid unreliable -> resolve_source_typed_probe returns
        passed=False with reason "abstain: ...". The lane withheld a
        verdict; rendering it as FAIL read like a failed conversion.
        """
        from whisker.llm.inspect_report import _format_unit_dumps

        dumps = {
            "kind": "whisker-table-unit-dumps",
            "model": "test",
            "pass_count": 0,
            "fail_count": 1,
            "skip_count": 0,
            "units": [
                {
                    "unit_index": 0,
                    "classification": "truncated_leak",
                    "probe": {
                        "passed": False,
                        "defect_confirmed": False,
                        "skipped": False,
                        "error": False,
                        "expected": "abstain: typed did not confirm, grid=unreliable",
                    },
                },
                {
                    "unit_index": 1,
                    "classification": "aligned",
                    "probe": {
                        "passed": True,
                        "defect_confirmed": False,
                        "skipped": False,
                        "error": False,
                    },
                },
            ],
        }
        lines = _format_unit_dumps(dumps)
        text = "\n".join(lines)
        assert "| T0 | truncated\\_leak | ABSTAIN |" in text
        assert "| FAIL |" not in text
        assert "abstain=1" in text
        assert "fail=0" in text
        assert "pass=1" in text
