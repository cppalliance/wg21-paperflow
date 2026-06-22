#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

from types import SimpleNamespace

from whisker.report import build_report, render_report_md, render_summary
from whisker.score import score_markdown

_CLEAN_MD = """---
title: "A Paper"
document: P1234R0
---

## Introduction

Faithful prose that the source also contains.
"""


def _content(coverage, *, drift=0.0):
    return SimpleNamespace(
        source_format="pdf",
        coverage=coverage,
        drift=drift,
        unigram_coverage=coverage,
        unigram_drift=drift,
        missing_regions=(),
        extra_regions=(),
    )


def _results():
    return [
        score_markdown("P0002", _CLEAN_MD, content=_content(0.98)),
        score_markdown("P0001", _CLEAN_MD, content=_content(0.90)),
    ]


def test_build_report_sorts_and_counts():
    report = build_report(_results())
    assert report["count"] == 2
    assert [r["pid"] for r in report["results"]] == ["P0001", "P0002"]
    assert report["counts"]["pass"] == 1
    assert report["counts"]["review"] == 1
    assert report["schema_version"] == 1


def test_render_report_md_is_table_sorted_by_pid():
    md = render_report_md(_results())
    assert md.startswith("# whisker report")
    assert "| PID |" in md
    p1 = md.index("P0001")
    p2 = md.index("P0002")
    assert p1 < p2


def test_render_report_md_is_deterministic():
    results = _results()
    assert render_report_md(results) == render_report_md(results)


def _mixed():
    # 0.98 -> pass, 0.90 -> review (in band), 0.50 -> fail (below floor).
    return [
        score_markdown("P0003", _CLEAN_MD, content=_content(0.98)),
        score_markdown("P0002", _CLEAN_MD, content=_content(0.90)),
        score_markdown("P0001", _CLEAN_MD, content=_content(0.50)),
    ]


def test_summary_hides_passes_groups_nonpass_and_has_footer():
    out = render_summary(_mixed(), elapsed=12.5)
    assert "fail (1)" in out
    assert "review (1)" in out
    assert "P0001" in out  # the fail is listed
    assert "P0002" in out  # the review is listed
    assert "P0003" not in out  # the pass is hidden by default
    assert out.strip().endswith("===")
    assert "1 failed, 1 review, 1 passed (3 scored) in 12.5s ===" in out


def test_summary_quiet_is_footer_only():
    out = render_summary(_mixed(), quiet=True)
    assert "\n" not in out
    assert out.startswith("=== ") and out.endswith(" ===")
    assert "fail (" not in out


def test_summary_verbose_shows_pass_section():
    out = render_summary(_mixed(), verbose=True)
    assert "pass (1)" in out
    assert "P0003" in out


def test_summary_caps_long_section_with_pointer():
    results = [
        score_markdown(f"P{i:04d}", _CLEAN_MD, content=_content(0.90))
        for i in range(40)
    ]
    out = render_summary(results, cap=15, report_path="whisker/report.md")
    assert "review (40)" in out
    assert "... and 25 more (see whisker/report.md)" in out


def test_summary_stats_rollup_counts_flags():
    out = render_summary(_mixed(), stats=True)
    assert "flag rollup" in out
    # the fail carries a hard coverage flag; the review carries a soft band flag
    assert "hard" in out and "soft" in out


def test_summary_stats_aggregates_by_category_not_value():
    # Two fails at different unigram coverages must roll up into ONE category row
    # of 2, not two rows of 1 (the value 0.50 vs 0.60 is noise for a rollup).
    results = [
        score_markdown("P0001", _CLEAN_MD, content=_content(0.50)),
        score_markdown("P0002", _CLEAN_MD, content=_content(0.60)),
    ]
    out = render_summary(results, stats=True)
    assert "2  hard  unigram coverage <" in out
    assert "0.50" not in out.split("flag rollup")[1]


def test_summary_color_only_when_requested():
    plain = render_summary(_mixed(), elapsed=1.0, color=False)
    painted = render_summary(_mixed(), elapsed=1.0, color=True)
    assert "\033[" not in plain
    assert "\033[" in painted


def test_summary_is_deterministic():
    results = _mixed()
    assert render_summary(results, elapsed=1.0) == render_summary(results, elapsed=1.0)


def _ref_results():
    # reference present: identical text -> pass; divergent text -> fail (nid).
    divergent = "## Other\n\nCompletely different words sharing nothing here zzz.\n" * 3
    return [
        score_markdown("P0001", _CLEAN_MD, content=_content(0.98),
                       reference_md=_CLEAN_MD, ref_engine="markitdown"),
        score_markdown("P0002", _CLEAN_MD, content=_content(0.98),
                       reference_md=divergent, ref_engine="markitdown"),
    ]


def test_report_md_surfaces_reference_columns():
    md = render_report_md(_ref_results())
    assert "| overall | nid | teds | mhs |" in md


def test_summary_item_line_leads_with_reference_metrics():
    out = render_summary(_ref_results())
    # the review (P0002) line leads with the oracle agreement, not coverage.
    assert "ovr=" in out and "teds=" in out
    assert "cov=" not in out
