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
