#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

from whisker.bench import aggregate, run_bench

_REF = """---
title: "X"
document: P1
---

## Intro

Some prose.

| A | B |
|---|---|
| 1 | 2 |
"""


def test_identical_candidate_scores_perfect():
    rows = run_bench([("P1", _REF, _REF)])
    assert len(rows) == 1
    row = rows[0]
    assert row.nid == 1.0
    assert row.teds == 1.0
    assert row.mhs == 1.0
    assert row.overall == 1.0
    assert row.content_recall == 1.0


def test_dropped_section_lowers_content_recall_but_keeps_nid():
    # A candidate that drops a whole paragraph keeps high block-matched nid on
    # the surviving blocks, but content_recall falls because GT words are gone.
    ref = (
        "## H\n\nAlpha paragraph about allocators here.\n\n"
        "Beta paragraph about coroutines and executors.\n"
    )
    dropped = "## H\n\nAlpha paragraph about allocators here.\n"
    rows = run_bench([("P1", dropped, ref)])
    assert rows[0].nid == 1.0
    assert rows[0].content_recall < 1.0


def test_content_recall_in_row_dict():
    rows = run_bench([("P1", _REF, _REF)])
    assert rows[0].to_dict()["content_recall"] == 1.0


def test_aggregate_reports_content_recall_mean():
    rows = run_bench([("P1", _REF, _REF)])
    agg = aggregate(rows)
    assert agg["content_recall"] == 1.0


def test_aggregate_empty_has_content_recall():
    agg = aggregate([])
    assert agg["content_recall"] == 0.0


_PLAIN = "Just prose about allocators and coroutines, no tables and no headings.\n"


def test_no_table_no_heading_axes_are_none():
    rows = run_bench([("P1", _PLAIN, _PLAIN)])
    row = rows[0]
    assert row.teds is None
    assert row.mhs is None
    assert row.to_dict()["teds"] is None
    assert row.to_dict()["mhs"] is None


def test_overall_not_inflated_by_ineligible_axes():
    # With teds/mhs ineligible, overall is the text axis alone, not pulled toward
    # 1.0 by two synthetic perfect scores.
    cand = "Totally different words entirely unrelated to the reference content.\n"
    rows = run_bench([("P1", cand, _PLAIN)])
    row = rows[0]
    assert row.teds is None and row.mhs is None
    assert row.overall == row.nid


def test_aggregate_eligible_counts_and_excluded_means():
    rows = run_bench([("PLAIN", _PLAIN, _PLAIN), ("RICH", _REF, _REF)])
    agg = aggregate(rows)
    assert agg["eligible_counts"]["nid"] == 2
    assert agg["eligible_counts"]["teds"] == 1
    assert agg["eligible_counts"]["mhs"] == 1
    # teds mean averages only the one eligible (RICH) row.
    assert agg["teds"] == 1.0
    assert agg["mhs"] == 1.0


def test_aggregate_all_ineligible_axis_mean_is_none():
    rows = run_bench([("P1", _PLAIN, _PLAIN)])
    agg = aggregate(rows)
    assert agg["teds"] is None
    assert agg["mhs"] is None
    assert agg["eligible_counts"]["teds"] == 0


def test_grits_con_eligible_and_advisory():
    # Reference has a table -> grits_con is scored; identical -> 1.0.
    rows = run_bench([("P1", _REF, _REF)])
    assert rows[0].grits_con == 1.0
    assert rows[0].to_dict()["grits_con"] == 1.0


def test_grits_con_none_when_no_reference_table():
    rows = run_bench([("P1", _PLAIN, _PLAIN)])
    assert rows[0].grits_con is None


def test_grits_con_is_not_gated():
    # A cell difference drops grits_con but it must never appear in below_floor
    # (advisory axis, not a gate).
    cand = _REF.replace("| 1 | 2 |", "| 1 | 9 |")
    rows = run_bench([("P1", cand, _REF)])
    agg = aggregate(rows)
    assert rows[0].grits_con < 1.0
    assert agg["eligible_counts"]["grits_con"] == 1


def test_aggregate_empty_has_grits_con():
    agg = aggregate([])
    assert agg["grits_con"] is None
    assert agg["eligible_counts"]["grits_con"] == 0


def test_identical_candidate_has_zero_reading_order():
    rows = run_bench([("P1", _REF, _REF)])
    assert rows[0].reading_order == 0.0
    assert rows[0].to_dict()["reading_order"] == 0.0


def test_reordered_paragraphs_keep_high_nid():
    # Block matching aligns paragraphs regardless of position, so reordering the
    # body does not depress nid (it surfaces as reading_order instead).
    ref = "## H\n\nAlpha paragraph about allocators.\n\nBeta paragraph about coroutines.\n"
    reordered = "## H\n\nBeta paragraph about coroutines.\n\nAlpha paragraph about allocators.\n"
    rows = run_bench([("P1", reordered, ref)])
    assert rows[0].nid == 1.0


def test_aggregate_reports_reading_order_mean():
    rows = run_bench([("P1", _REF, _REF)])
    agg = aggregate(rows)
    assert "reading_order" in agg
    assert agg["reading_order"] == 0.0


def test_table_difference_lowers_teds():
    cand = _REF.replace("| 1 | 2 |", "| 1 | 9 |")
    rows = run_bench([("P1", cand, _REF)])
    assert rows[0].teds < 1.0


def test_rows_sorted_by_pid():
    rows = run_bench([("P2", _REF, _REF), ("P1", _REF, _REF)])
    assert [r.pid for r in rows] == ["P1", "P2"]


def test_aggregate_flags_below_floor():
    cand = "completely different text with no headings or tables"
    rows = run_bench([("P1", cand, _REF)])
    agg = aggregate(rows)
    assert agg["count"] == 1
    assert "P1" in agg["below_floor"]


def test_aggregate_empty():
    agg = aggregate([])
    assert agg["count"] == 0
    assert agg["below_floor"] == []
