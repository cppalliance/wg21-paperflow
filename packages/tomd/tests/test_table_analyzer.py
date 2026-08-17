# Copyright (c) 2026 C++ Alliance, Inc. (https://cppalliance.org)
# SPDX-License-Identifier: BSL-1.0

"""Tests for table classification (integrated in lib.pdf.table)."""

from conftest import make_span
from tomd.lib.pdf.table import (
    TableKind, _compute_table_signals, _classify_table,
    _classify_and_annotate,
)


def _cell(*texts, monospace=False):
    """Build a cell (list of Spans) from text strings."""
    return [make_span(t, monospace=monospace) for t in texts]


class TestComputeTableSignals:
    def test_empty_rows(self):
        signals = _compute_table_signals([])
        assert signals["empty"] is True

    def test_clean_matrix(self):
        rows = [
            [_cell("Header A"), _cell("Header B"), _cell("Header C")],
            [_cell("val1"), _cell("val2"), _cell("val3")],
            [_cell("val4"), _cell("val5"), _cell("val6")],
        ]
        signals = _compute_table_signals(rows)
        assert signals["empty"] is False
        assert signals["num_rows"] == 3
        assert signals["num_cols"] == 3
        assert signals["empty_ratio"] == 0.0
        assert signals["mono_ratio"] == 0.0
        assert signals["avg_spans_per_cell"] == 1.0

    def test_high_monospace_low_spans(self):
        """Code-declaration table: mono but few spans per cell."""
        rows = [
            [_cell("constexpr", monospace=True), _cell("foo()", monospace=True)],
            [_cell("constexpr", monospace=True), _cell("bar()", monospace=True)],
        ] * 6  # 12 rows
        signals = _compute_table_signals(rows)
        assert signals["mono_ratio"] == 1.0
        assert signals["num_rows"] == 12
        assert signals["avg_spans_per_cell"] == 1.0

    def test_tony_table_high_spans(self):
        """Tony Table: mono, few rows, many spans per cell."""
        long_cell = [make_span(f"line{i} ", monospace=True) for i in range(15)]
        rows = [
            [long_cell[:], long_cell[:]],
            [long_cell[:], long_cell[:]],
        ]
        signals = _compute_table_signals(rows)
        assert signals["mono_ratio"] == 1.0
        assert signals["num_rows"] == 2
        assert signals["num_cols"] == 2
        assert signals["avg_spans_per_cell"] == 15.0


class TestClassifyTable:
    def test_empty_is_false_positive(self):
        assert _classify_table({"empty": True}) == TableKind.FALSE_POSITIVE

    def test_high_empty_ratio_is_false_positive(self):
        signals = {
            "empty": False,
            "empty_ratio": 0.6,
            "mono_ratio": 0.0,
            "max_word_count": 3,
            "col_count_consistent": True,
            "num_cols": 3,
            "num_rows": 5,
            "avg_cell_length": 10,
            "avg_spans_per_cell": 1.0,
        }
        assert _classify_table(signals) == TableKind.FALSE_POSITIVE

    def test_inconsistent_cols_is_false_positive(self):
        signals = {
            "empty": False,
            "empty_ratio": 0.1,
            "mono_ratio": 0.0,
            "max_word_count": 3,
            "col_count_consistent": False,
            "num_cols": 3,
            "num_rows": 5,
            "avg_cell_length": 10,
            "avg_spans_per_cell": 1.0,
        }
        assert _classify_table(signals) == TableKind.FALSE_POSITIVE

    def test_code_comparison_tony_table(self):
        signals = {
            "empty": False,
            "empty_ratio": 0.0,
            "mono_ratio": 0.95,
            "max_word_count": 5,
            "col_count_consistent": True,
            "num_cols": 2,
            "num_rows": 3,
            "avg_cell_length": 120,
            "avg_spans_per_cell": 15.0,
        }
        assert _classify_table(signals) == TableKind.CODE_COMPARISON

    def test_per_line_code_table_is_code_comparison(self):
        """High mono + many rows + low spans = CODE_COMPARISON (per-line code table)."""
        signals = {
            "empty": False,
            "empty_ratio": 0.0,
            "mono_ratio": 0.95,
            "max_word_count": 3,
            "col_count_consistent": True,
            "num_cols": 2,
            "num_rows": 12,
            "avg_cell_length": 20,
            "avg_spans_per_cell": 2.0,
        }
        assert _classify_table(signals) == TableKind.CODE_COMPARISON

    def test_prose_table(self):
        signals = {
            "empty": False,
            "empty_ratio": 0.1,
            "mono_ratio": 0.0,
            "max_word_count": 25,
            "col_count_consistent": True,
            "num_cols": 2,
            "num_rows": 5,
            "avg_cell_length": 80,
            "avg_spans_per_cell": 3.0,
        }
        assert _classify_table(signals) == TableKind.PROSE_TABLE

    def test_clean_matrix(self):
        signals = {
            "empty": False,
            "empty_ratio": 0.05,
            "mono_ratio": 0.3,
            "max_word_count": 4,
            "col_count_consistent": True,
            "num_cols": 4,
            "num_rows": 8,
            "avg_cell_length": 15,
            "avg_spans_per_cell": 1.5,
        }
        assert _classify_table(signals) == TableKind.CLEAN_MATRIX


class TestClassifyAndAnnotate:
    def test_clean_matrix(self):
        rows = [
            [_cell("A"), _cell("B")],
            [_cell("C"), _cell("D")],
        ]
        kind, strategy, _ = _classify_and_annotate(rows)
        assert kind == "clean_matrix"
        assert strategy == "pipe_table"

    def test_empty_is_false_positive(self):
        kind, strategy, _ = _classify_and_annotate([])
        assert kind == "false_positive"
        assert strategy == "skip"

    def test_tony_table_gets_html_table(self):
        long_cell = [make_span(f"line{i} ", monospace=True) for i in range(15)]
        rows = [
            [long_cell[:], long_cell[:]],
            [long_cell[:], long_cell[:]],
        ]
        kind, strategy, _ = _classify_and_annotate(rows)
        assert kind == "code_comparison"
        assert strategy == "html_table"

    def test_soft_wrapped_prose_stays_a_pipe_table(self):
        """N5040: a wrapped prose cell is not multi-line content."""
        wrapped = [
            make_span("US 70-126 [compare.type] Allow "),
            make_span("\n"),
            make_span("incomplete types in type_order"),
        ]
        rows = [
            [_cell("#"), _cell("Title"), _cell("Status")],
            [_cell("1"), wrapped, _cell("Accepted (C++26)")],
        ]
        _, strategy, _ = _classify_and_annotate(rows)
        assert strategy == "pipe_table"

    def test_multiline_code_cell_still_escapes_to_html(self):
        """A break inside monospace is semantic and must survive."""
        code = [
            make_span("struct Draw {", monospace=True),
            make_span("\n", monospace=True),
            make_span("  void f();", monospace=True),
        ]
        rows = [
            [_cell("Before"), _cell("After")],
            [code, _cell("some prose describing the change")],
        ]
        _, strategy, _ = _classify_and_annotate(rows)
        assert strategy == "html_table"

    def test_mixed_table_escapes_when_any_cell_is_code(self):
        """p0957r8: prose and assembly in one table; the assembly wins."""
        prose = [
            make_span("To evaluate code generation we "),
            make_span("\n"),
            make_span("compiled the example."),
        ]
        asm = [
            make_span("mov rax, qword ptr [rdi]", monospace=True),
            make_span("\n", monospace=True),
            make_span("jmp qword ptr [rax + 24]", monospace=True),
        ]
        rows = [
            [_cell("Notes"), _cell("Output")],
            [prose, asm],
        ]
        _, strategy, _ = _classify_and_annotate(rows)
        assert strategy == "html_table"
