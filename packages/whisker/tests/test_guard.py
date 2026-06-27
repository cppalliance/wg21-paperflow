#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

import math

import pytest

from whisker import constants as C
from whisker.bench import BenchRow
from whisker.guard import (
    GUARD_BASELINE_KIND,
    baseline_from_rows,
    collect_tool_versions,
    diff_rows,
)


def _row(pid, nid=0.99, teds=0.99, mhs=0.99, reading_order=0.0):
    overall = (nid + teds + mhs) / 3.0
    return BenchRow(pid=pid, nid=nid, teds=teds, mhs=mhs, overall=overall,
                    reading_order=reading_order)


def _baseline(rows):
    return baseline_from_rows(rows)


def test_baseline_roundtrip_is_clean():
    rows = [_row("P1"), _row("P2")]
    base = _baseline(rows)
    assert base["kind"] == GUARD_BASELINE_KIND
    assert set(base["rows"]) == {"P1", "P2"}
    report = diff_rows(rows, base)
    assert not report.failed
    assert all(f.status == "ok" for f in report.findings)


def test_axis_regression_beyond_slack_fails():
    base = _baseline([_row("P1", teds=0.99)])
    # teds drops 0.99 -> 0.90 = 0.09 > slack
    report = diff_rows([_row("P1", teds=0.90)], base)
    assert report.failed
    f = report.findings[0]
    assert f.status == "regressed"
    assert any("teds" in r for r in f.regressions)


def test_drop_within_slack_passes():
    base = _baseline([_row("P1", teds=0.99)])
    # 0.99 -> 0.98 = 0.01 <= slack (0.02)
    report = diff_rows([_row("P1", teds=0.98)], base)
    assert not report.failed
    assert report.findings[0].status == "ok"


def test_slack_boundary_exact_is_not_a_regression():
    base = _baseline([_row("P1", teds=0.99)])
    # exactly slack: drop == slack is NOT > slack, so it passes
    cur = round(0.99 - C.GUARD_AXIS_SLACK, 4)
    report = diff_rows([_row("P1", teds=cur)], base)
    assert not report.failed


def test_crossed_floor_sub_slack_still_fails():
    # nid floor is 0.90. 0.905 -> 0.895 is only -0.010 (< slack 0.02) but it
    # crosses the published floor downward, which must still fail.
    base = _baseline([_row("P1", nid=0.905)])
    report = diff_rows([_row("P1", nid=0.895)], base)
    assert report.failed
    assert report.findings[0].status == "crossed_floor"


def test_new_paper_below_floor_fails():
    report = diff_rows([_row("P1", teds=0.50)], baseline=None)
    assert report.failed
    assert report.findings[0].status == "new_below_floor"


def test_new_paper_above_floor_passes_as_new():
    report = diff_rows([_row("P1")], baseline=None)
    assert not report.failed
    assert report.findings[0].status == "new"


def test_known_weak_paper_not_reflagged_when_stable():
    # A paper already below floor in the baseline (tabula monotonic model):
    # it is NOT re-flagged as long as it does not get worse.
    base = _baseline([_row("P1", teds=0.50)])
    report = diff_rows([_row("P1", teds=0.50)], base)
    assert not report.failed
    f = report.findings[0]
    assert f.status == "ok"
    assert any("teds" in b for b in f.below_floor)  # still reported as info


def test_known_weak_paper_getting_worse_fails():
    base = _baseline([_row("P1", teds=0.50)])
    report = diff_rows([_row("P1", teds=0.40)], base)
    assert report.failed
    assert report.findings[0].status == "regressed"


def test_missing_paper_is_hard_fail():
    base = _baseline([_row("P1"), _row("P2")])
    report = diff_rows([_row("P1")], base)  # P2 vanished
    assert report.failed
    assert report.missing == ["P2"]


def test_overall_erosion_trips_even_when_no_single_axis_does():
    # Each axis drops 0.015 (< slack 0.02), but overall also drops 0.015, which
    # is < slack too -> should NOT trip. Confirms overall uses the same slack.
    base = _baseline([_row("P1", nid=0.99, teds=0.99, mhs=0.99)])
    report = diff_rows([_row("P1", nid=0.975, teds=0.975, mhs=0.975)], base)
    assert not report.failed
    # But a 0.03 uniform drop (> slack) trips on every axis incl. overall.
    report2 = diff_rows([_row("P1", nid=0.96, teds=0.96, mhs=0.96)], base)
    assert report2.failed
    assert "overall" in " ".join(report2.findings[0].regressions)


def test_report_dict_is_serializable_and_sorted():
    base = _baseline([_row("P2"), _row("P1")])
    report = diff_rows([_row("P2"), _row("P1")], base)
    d = report.to_dict()
    assert [f["pid"] for f in d["findings"]] == ["P1", "P2"]
    assert d["failed"] is False
    assert "status_counts" in d


# --- second-pass red-team hardening -----------------------------------------


def test_baseline_embedded_slack_drives_the_gate():
    # A baseline that committed a looser slack must be honored (the contract
    # travels with the data), not the live constant.
    base = _baseline([_row("P1", teds=0.99)])
    base["axis_slack"] = 0.05
    # 0.99 -> 0.95 = 0.04 drop: regresses under default 0.02, passes under 0.05.
    report = diff_rows([_row("P1", teds=0.95)], base)
    assert not report.failed
    assert report.slack == 0.05


def test_cli_slack_argument_overrides_baseline():
    base = _baseline([_row("P1", teds=0.99)])
    base["axis_slack"] = 0.05
    # Explicit slack=0.0 tolerates nothing: a 0.01 drop now regresses.
    report = diff_rows([_row("P1", teds=0.98)], base, slack=0.0)
    assert report.failed
    assert report.slack == 0.0


def test_baseline_embedded_floors_are_honored():
    # A baseline committed a stricter teds floor (0.88) than the constant default.
    # prior 0.89 is above it, current 0.875 dips below it by only 0.015 (< slack
    # 0.02): a sub-slack crossing of the BASELINE's floor, which must still fail.
    base = _baseline([_row("P1", teds=0.89)])
    base["floors"]["teds"] = 0.88
    report = diff_rows([_row("P1", teds=0.875)], base)
    assert report.failed
    assert report.findings[0].status == "crossed_floor"
    assert report.floors["teds"] == 0.88


def test_wrong_kind_baseline_raises():
    base = _baseline([_row("P1")])
    base["kind"] = "whisker-bench-leaderboard"
    with pytest.raises(ValueError):
        diff_rows([_row("P1")], base)


def test_schema_mismatch_baseline_raises():
    base = _baseline([_row("P1")])
    base["schema_version"] = "0.0.0-ancient"
    with pytest.raises(ValueError):
        diff_rows([_row("P1")], base)


def test_nonfinite_baseline_value_raises():
    base = _baseline([_row("P1")])
    base["rows"]["P1"]["teds"] = float("nan")
    with pytest.raises(ValueError):
        diff_rows([_row("P1")], base)


def test_nonfinite_current_axis_is_invalid_and_fails():
    base = _baseline([_row("P1")])
    report = diff_rows([_row("P1", teds=float("nan"))], base)
    assert report.failed
    f = report.findings[0]
    assert f.status == "invalid"
    # report stays JSON-clean: a NaN axis serializes to null, not a bare NaN token.
    d = f.to_dict()
    assert d["axes"]["teds"] is None


def test_inf_current_axis_is_invalid_even_without_baseline():
    report = diff_rows([_row("P1", nid=math.inf)], baseline=None)
    assert report.failed
    assert report.findings[0].status == "invalid"


def test_duplicate_pids_raise_in_diff_and_baseline():
    with pytest.raises(ValueError):
        baseline_from_rows([_row("P1"), _row("P1")])
    base = _baseline([_row("P1")])
    with pytest.raises(ValueError):
        diff_rows([_row("P1"), _row("P1")], base)


def test_fail_on_new_blocks_unbaselined_paper():
    base = _baseline([_row("P1")])
    # P2 is brand new and above floors: passes by default, fails under fail_on_new.
    assert not diff_rows([_row("P1"), _row("P2")], base).failed
    strict = diff_rows([_row("P1"), _row("P2")], base, fail_on_new=True)
    assert strict.failed
    assert any(f.pid == "P2" and f.status == "new" for f in strict.regressed())


# --- A2: versioned baselines (tool_versions) --------------------------------


def test_baseline_embeds_tool_versions():
    base = _baseline([_row("P1")])
    assert base["tool_versions"] == collect_tool_versions()
    # tomd and whisker are installed in the workspace; both must be recorded.
    assert set(base["tool_versions"]) == {"tomd", "whisker"}


def test_collect_tool_versions_is_sorted_and_stringy():
    tv = collect_tool_versions()
    assert list(tv) == sorted(tv)
    assert all(isinstance(v, str) and v for v in tv.values())


def test_matching_tool_versions_pass():
    rows = [_row("P1")]
    base = _baseline(rows)
    assert not diff_rows(rows, base).failed


def test_tool_version_mismatch_hard_fails():
    base = _baseline([_row("P1")])
    base["tool_versions"]["tomd"] = "0.0.0-stale"
    with pytest.raises(ValueError):
        diff_rows([_row("P1")], base)


def test_non_object_tool_versions_raises():
    base = _baseline([_row("P1")])
    base["tool_versions"] = "0.4.1"
    with pytest.raises(ValueError):
        diff_rows([_row("P1")], base)


def _ineligible_row(pid, nid=0.99, content_recall=0.99):
    # teds/mhs ineligible (reference had no tables/headings): overall = nid.
    return BenchRow(
        pid=pid, nid=nid, teds=None, mhs=None, overall=nid,
        content_recall=content_recall,
    )


def test_baseline_stores_null_for_ineligible_axes():
    base = _baseline([_ineligible_row("P1")])
    assert base["rows"]["P1"]["teds"] is None
    assert base["rows"]["P1"]["mhs"] is None


def test_ineligible_axes_are_not_invalid():
    # A None axis must NOT be treated as a corrupt (NaN/inf) value.
    rows = [_ineligible_row("P1")]
    report = diff_rows(rows, _baseline(rows))
    assert not report.failed
    assert report.findings[0].status == "ok"


def test_ineligible_axis_skips_floor():
    # nid above floor, teds/mhs ineligible -> no below_floor, passes as NEW.
    report = diff_rows([_ineligible_row("P1", nid=0.99)], None)
    assert not report.failed
    assert report.findings[0].status == "new"


def test_ineligible_axis_skips_regression():
    base = _baseline([_ineligible_row("P1", nid=0.99)])
    # nid holds; teds/mhs stay None on both sides -> no regression.
    report = diff_rows([_ineligible_row("P1", nid=0.99)], base)
    assert not report.failed


def test_nan_axis_still_invalid():
    # Eligibility null is fine, but a real NaN is still STATUS_INVALID.
    bad = BenchRow(pid="P1", nid=math.nan, teds=None, mhs=None, overall=0.99)
    report = diff_rows([bad], None)
    assert report.findings[0].status == "invalid"
    assert report.failed
