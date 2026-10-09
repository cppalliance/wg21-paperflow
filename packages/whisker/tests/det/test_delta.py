#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

import json
import os

import pytest
from whisker import constants as C
from whisker.det.cli import _llm_report_is_stale, _snapshot_prev_report, delta_main
from whisker.det.delta import (
    STATUS_GONE,
    STATUS_IMPROVED,
    STATUS_NEW,
    STATUS_REGRESSED,
    STATUS_UNCHANGED,
    compute_delta,
)
from whisker.llm.cli import _snapshot_prev_merged_report


def _result(pid, verdict="pass", **metrics):
    base = {"unigram_coverage": 0.98, "coverage": 0.95, "qa_score": 90, "ref_nid": 0.95}
    base.update(metrics)
    return {"pid": pid, "verdict": verdict, **base}


def _report(*results):
    return {"schema_version": C.WHISKER_SCHEMA_VERSION, "count": len(results),
            "results": list(results)}


# -- verdict transitions ------------------------------------------------------


def test_verdict_worsening_is_regressed():
    prev = _report(_result("P1", verdict="pass"))
    curr = _report(_result("P1", verdict="not-llm-readable"))
    result = compute_delta(prev, curr)
    assert result.any_regressed
    f = result.regressed()[0]
    assert f.status == STATUS_REGRESSED
    assert f.prev_verdict == "pass" and f.curr_verdict == "not-llm-readable"


def test_verdict_improving_is_improved():
    prev = _report(_result("P1", verdict="not-llm-readable"))
    curr = _report(_result("P1", verdict="pass"))
    result = compute_delta(prev, curr)
    assert not result.any_regressed
    f = result.improved()[0]
    assert f.status == STATUS_IMPROVED


def test_review_to_pass_is_improved_pass_to_review_is_regressed():
    prev = _report(_result("P1", verdict="review"))
    curr = _report(_result("P1", verdict="pass"))
    assert compute_delta(prev, curr).improved()[0].pid == "P1"

    prev2 = _report(_result("P1", verdict="pass"))
    curr2 = _report(_result("P1", verdict="review"))
    assert compute_delta(prev2, curr2).regressed()[0].pid == "P1"


def test_verdict_change_dominates_ordering_over_metric_only_change():
    # A verdict regression on P1 must outrank a metric-only regression on P2
    # in worst-first severity (verdict transitions always sort first).
    prev = _report(
        _result("P1", verdict="pass"),
        _result("P2", verdict="pass", unigram_coverage=0.98),
    )
    curr = _report(
        _result("P1", verdict="not-llm-readable"),
        _result("P2", verdict="pass", unigram_coverage=0.90),
    )
    result = compute_delta(prev, curr)
    regressed = sorted(result.regressed(), key=lambda f: -f.severity)
    assert [f.pid for f in regressed] == ["P1", "P2"]


# -- metric epsilon behavior ---------------------------------------------------


def test_metric_drop_beyond_epsilon_is_regressed():
    prev = _report(_result("P1", unigram_coverage=0.98))
    curr = _report(_result("P1", unigram_coverage=0.98 - C.DELTA_METRIC_EPSILON - 0.001))
    result = compute_delta(prev, curr)
    assert result.regressed()[0].pid == "P1"


def test_metric_drop_within_epsilon_is_unchanged():
    prev = _report(_result("P1", unigram_coverage=0.98))
    curr = _report(_result("P1", unigram_coverage=0.98 - C.DELTA_METRIC_EPSILON / 2))
    result = compute_delta(prev, curr)
    assert result.unchanged()[0].status == STATUS_UNCHANGED
    assert not result.any_regressed


def test_metric_drop_exactly_at_epsilon_is_not_a_regression():
    # strictly-greater-than semantics: a drop == epsilon does not trip.
    prev = _report(_result("P1", unigram_coverage=0.90))
    curr = _report(_result("P1", unigram_coverage=round(0.90 - C.DELTA_METRIC_EPSILON, 4)))
    result = compute_delta(prev, curr)
    assert not result.any_regressed


def test_metric_gain_beyond_epsilon_is_improved():
    prev = _report(_result("P1", unigram_coverage=0.90))
    curr = _report(_result("P1", unigram_coverage=0.90 + C.DELTA_METRIC_EPSILON + 0.001))
    result = compute_delta(prev, curr)
    assert result.improved()[0].pid == "P1"


def test_null_metric_on_either_side_is_never_a_regression():
    # ref_nid absent (e.g. --no-reference): must not be treated as a drop to
    # zero/None, and must not gate the verdict.
    prev = _report(_result("P1", ref_nid=0.95))
    curr = _report(_result("P1", ref_nid=None))
    result = compute_delta(prev, curr)
    assert not result.any_regressed
    f = result.unchanged()[0]
    assert f.metrics["ref_nid"].delta is None


def test_null_metric_both_sides_stays_not_comparable():
    prev = _report(_result("P1", ref_nid=None))
    curr = _report(_result("P1", ref_nid=None))
    result = compute_delta(prev, curr)
    assert result.unchanged()[0].metrics["ref_nid"].delta is None


def test_qa_score_integer_drop_registers_as_regression():
    prev = _report(_result("P1", qa_score=90))
    curr = _report(_result("P1", qa_score=85))
    result = compute_delta(prev, curr)
    assert result.regressed()[0].pid == "P1"


# -- new / gone -----------------------------------------------------------------


def test_new_paper_classified_new():
    prev = _report(_result("P1"))
    curr = _report(_result("P1"), _result("P2", verdict="review"))
    result = compute_delta(prev, curr)
    assert not result.any_regressed  # a new paper never counts as a regression
    f = result.new_papers()[0]
    assert f.pid == "P2" and f.status == STATUS_NEW and f.curr_verdict == "review"


def test_gone_paper_classified_gone():
    prev = _report(_result("P1"), _result("P2", verdict="not-llm-readable"))
    curr = _report(_result("P1"))
    result = compute_delta(prev, curr)
    f = result.gone_papers()[0]
    assert f.pid == "P2" and f.status == STATUS_GONE and f.prev_verdict == "not-llm-readable"


def test_gone_paper_alone_does_not_trip_any_regressed():
    prev = _report(_result("P1", verdict="not-llm-readable"))
    curr = _report()
    result = compute_delta(prev, curr)
    assert not result.any_regressed


# -- deterministic ordering ------------------------------------------------------


def test_findings_are_pid_sorted_regardless_of_input_order():
    prev = _report(_result("P3"), _result("P1"), _result("P2"))
    curr = _report(_result("P2"), _result("P3"), _result("P1"))
    result = compute_delta(prev, curr)
    assert [f.pid for f in result.findings] == ["P1", "P2", "P3"]


def test_filtered_views_stay_pid_sorted():
    prev = _report(
        _result("PZ", verdict="pass"), _result("PA", verdict="pass"),
    )
    curr = _report(
        _result("PZ", verdict="not-llm-readable"), _result("PA", verdict="not-llm-readable"),
    )
    result = compute_delta(prev, curr)
    assert [f.pid for f in result.regressed()] == ["PA", "PZ"]


def test_to_dict_is_deterministic_and_json_serializable():
    prev = _report(_result("P1", verdict="pass"))
    curr = _report(_result("P1", verdict="not-llm-readable"))
    result = compute_delta(prev, curr)
    d1 = json.dumps(result.to_dict())
    d2 = json.dumps(compute_delta(prev, curr).to_dict())
    assert d1 == d2


# -- malformed input ------------------------------------------------------------


def test_missing_results_key_raises():
    with pytest.raises(ValueError):
        compute_delta({"count": 0}, _report(_result("P1")))


def test_non_dict_report_raises():
    with pytest.raises(ValueError):
        compute_delta([], _report(_result("P1")))


def test_duplicate_pid_in_report_raises():
    curr = {"results": [_result("P1"), _result("P1")]}
    with pytest.raises(ValueError):
        compute_delta(_report(_result("P1")), curr)


def test_result_missing_pid_raises():
    curr = {"results": [{"verdict": "pass"}]}
    with pytest.raises(ValueError):
        compute_delta(_report(_result("P1")), curr)


# -- CLI: report.prev.json snapshot behavior ------------------------------------


def test_snapshot_prev_report_is_noop_on_first_run(tmp_path):
    _snapshot_prev_report(tmp_path)
    assert not (tmp_path / "report.prev.json").exists()


def test_snapshot_prev_report_copies_existing_report(tmp_path):
    report_path = tmp_path / "report.json"
    report_path.write_text('{"count": 1}', encoding="utf-8")

    _snapshot_prev_report(tmp_path)

    prev_path = tmp_path / "report.prev.json"
    assert prev_path.exists()
    assert prev_path.read_text(encoding="utf-8") == '{"count": 1}'
    # the live report is untouched by the snapshot step itself
    assert report_path.read_text(encoding="utf-8") == '{"count": 1}'


def test_snapshot_prev_report_overwrites_prior_snapshot(tmp_path):
    (tmp_path / "report.json").write_text('{"count": 1}', encoding="utf-8")
    _snapshot_prev_report(tmp_path)
    (tmp_path / "report.json").write_text('{"count": 2}', encoding="utf-8")
    _snapshot_prev_report(tmp_path)

    assert (tmp_path / "report.prev.json").read_text(encoding="utf-8") == '{"count": 2}'


# -- CLI: whisker delta verb -----------------------------------------------------


def test_delta_main_exits_review_on_regression(tmp_path, capsys):
    (tmp_path / "report.prev.json").write_text(
        json.dumps(_report(_result("P1", verdict="pass"))), encoding="utf-8",
    )
    (tmp_path / "report.json").write_text(
        json.dumps(_report(_result("P1", verdict="not-llm-readable"))), encoding="utf-8",
    )

    rc = delta_main(["--report-dir", str(tmp_path)])

    assert rc == C.EXIT_REVIEW
    out = capsys.readouterr().out
    assert "P1" in out
    assert "regressed (1)" in out


def test_delta_main_exits_ok_when_clean(tmp_path, capsys):
    (tmp_path / "report.prev.json").write_text(
        json.dumps(_report(_result("P1", verdict="pass"))), encoding="utf-8",
    )
    (tmp_path / "report.json").write_text(
        json.dumps(_report(_result("P1", verdict="pass"))), encoding="utf-8",
    )

    rc = delta_main(["--report-dir", str(tmp_path)])

    assert rc == C.EXIT_OK
    assert "unchanged: 1" in capsys.readouterr().out


def test_delta_main_json_output_is_clean_object_on_stdout(tmp_path, capsys):
    (tmp_path / "report.prev.json").write_text(
        json.dumps(_report(_result("P1", verdict="pass"))), encoding="utf-8",
    )
    (tmp_path / "report.json").write_text(
        json.dumps(_report(_result("P1", verdict="not-llm-readable"))), encoding="utf-8",
    )

    rc = delta_main(["--report-dir", str(tmp_path), "--json"])

    assert rc == C.EXIT_REVIEW
    payload = json.loads(capsys.readouterr().out)
    assert payload["any_regressed"] is True
    assert payload["findings"][0]["pid"] == "P1"


def test_delta_main_missing_current_report_is_operational_error(tmp_path):
    (tmp_path / "report.prev.json").write_text(
        json.dumps(_report(_result("P1"))), encoding="utf-8",
    )
    rc = delta_main(["--report-dir", str(tmp_path)])
    assert rc == C.EXIT_ERROR


def test_delta_main_missing_baseline_is_operational_error(tmp_path):
    (tmp_path / "report.json").write_text(
        json.dumps(_report(_result("P1"))), encoding="utf-8",
    )
    rc = delta_main(["--report-dir", str(tmp_path)])
    assert rc == C.EXIT_ERROR


def test_delta_main_explicit_baseline_override(tmp_path, capsys):
    baseline = tmp_path / "custom-baseline.json"
    baseline.write_text(
        json.dumps(_report(_result("P1", verdict="pass"))), encoding="utf-8",
    )
    (tmp_path / "report.json").write_text(
        json.dumps(_report(_result("P1", verdict="not-llm-readable"))), encoding="utf-8",
    )

    rc = delta_main(["--report-dir", str(tmp_path), "--baseline", str(baseline)])

    assert rc == C.EXIT_REVIEW


# -- compute_delta generalization (verdict_field / watched_metrics / results_key) --


def test_compute_delta_bare_list_with_custom_verdict_field_and_metrics():
    prev = [{"pid": "P1", "det": "pass", "unigram": 0.98}]
    curr = [{"pid": "P1", "det": "not-llm-readable", "unigram": 0.80}]
    result = compute_delta(
        prev, curr, verdict_field="det", watched_metrics=("unigram",), results_key=None,
    )
    assert result.any_regressed
    f = result.regressed()[0]
    assert f.prev_verdict == "pass" and f.curr_verdict == "not-llm-readable"
    assert set(f.metrics) == {"unigram"}


def test_compute_delta_verdict_only_pass_empty_watched_metrics():
    prev = [{"pid": "P1", "llm": "pass", "unigram": 0.98}]
    curr = [{"pid": "P1", "llm": "not-llm-readable", "unigram": 0.10}]
    result = compute_delta(prev, curr, verdict_field="llm", watched_metrics=(), results_key=None)
    f = result.regressed()[0]
    # unigram moved a lot but watched_metrics=() means only the verdict field
    # (llm) is compared; the metric is never consulted.
    assert f.metrics == {}


def test_compute_delta_bare_list_same_verdict_falls_back_to_no_metrics():
    prev = [{"pid": "P1", "llm": "pass"}]
    curr = [{"pid": "P1", "llm": "pass"}]
    result = compute_delta(prev, curr, verdict_field="llm", watched_metrics=(), results_key=None)
    assert result.unchanged()[0].pid == "P1"


def test_compute_delta_results_key_none_rejects_non_list():
    with pytest.raises(ValueError):
        compute_delta({"results": []}, [], results_key=None)


def test_compute_delta_default_call_unaffected_by_new_kwargs():
    # Backward compatibility: the det caller's exact original call shape
    # (positional args, no kwargs) must behave identically to before.
    prev = _report(_result("P1", verdict="pass"))
    curr = _report(_result("P1", verdict="not-llm-readable"))
    result = compute_delta(prev, curr)
    assert result.any_regressed
    assert result.regressed()[0].prev_verdict == "pass"


# -- whisker delta --llm: advisory LLM-lane merged-report delta -----------------


def _merged_row(pid, *, det="pass", llm="pass", unigram=0.98, replayed=None, **extra):
    """A fixture row matching fusion_report.build_merged_json's row shape."""
    row = {
        "pid": pid, "det": det, "llm": llm, "merged": det, "delta": "=",
        "conf": 0.9, "unigram": unigram, "overall": None, "ideal": None,
        "ideal_verdict": None, "ideal_discrepancy_count": 0, "flags": "",
        "rule": "", "class": "", "replayed": replayed,
    }
    row.update(extra)
    return row


def _write_llm_reports(llm_dir, prev_rows, curr_rows=None, baseline_path=None):
    if baseline_path is None:
        (llm_dir / "report-merged.prev.json").write_text(
            json.dumps(prev_rows), encoding="utf-8",
        )
    else:
        baseline_path.write_text(json.dumps(prev_rows), encoding="utf-8")
    if curr_rows is not None:
        (llm_dir / "report-merged.json").write_text(
            json.dumps(curr_rows), encoding="utf-8",
        )


def test_delta_llm_renders_det_regression_but_does_not_gate(tmp_path, capsys):
    # The det movement is real and worth showing, but this view is sampled on
    # a different time axis than `whisker delta` (aggregate rebuilds vs
    # `whisker --all` runs), so it must not own the gate.
    _write_llm_reports(
        tmp_path,
        [_merged_row("P1", det="pass", llm="pass", unigram=0.98)],
        [_merged_row("P1", det="not-llm-readable", llm="pass", unigram=0.80)],
    )

    rc = delta_main(["--llm", "--report-dir", str(tmp_path)])

    assert rc == C.EXIT_OK
    out = capsys.readouterr().out
    assert "regressed (1)" in out
    assert "P1" in out
    assert "--- LLM advisory verdict changes (single-run, may be judge noise) ---" in out
    assert "replayed (warm-skipped, unchanged): 0" in out
    # Exit 0 next to a rendered "regressed" section is confusing without this.
    assert "does not gate" in out
    assert "whisker delta" in out


def test_delta_llm_omits_the_gate_note_when_nothing_regressed(tmp_path, capsys):
    _write_llm_reports(
        tmp_path,
        [_merged_row("P1", det="pass", unigram=0.98)],
        [_merged_row("P1", det="pass", unigram=0.98)],
    )

    rc = delta_main(["--llm", "--report-dir", str(tmp_path)])

    assert rc == C.EXIT_OK
    assert "does not gate" not in capsys.readouterr().out


def test_delta_llm_tier_only_change_never_gates(tmp_path, capsys):
    _write_llm_reports(
        tmp_path,
        [_merged_row("P1", det="pass", llm="pass", unigram=0.98)],
        [_merged_row("P1", det="pass", llm="not-llm-readable", unigram=0.98)],
    )

    rc = delta_main(["--llm", "--report-dir", str(tmp_path)])

    assert rc == C.EXIT_OK
    out = capsys.readouterr().out
    assert "P1 [pass -> not-llm-readable]" in out


def test_delta_llm_excludes_absent_marker_transitions_from_advisory_section(tmp_path, capsys):
    _write_llm_reports(
        tmp_path,
        [_merged_row("P1", det="pass", llm="-", unigram=0.98)],
        [_merged_row("P1", det="pass", llm="pass", unigram=0.98)],
    )

    rc = delta_main(["--llm", "--report-dir", str(tmp_path)])

    assert rc == C.EXIT_OK
    out = capsys.readouterr().out
    assert "  none" in out
    assert "P1 [- ->" not in out


# -- whisker delta --llm: the missing-det-sidecar false-regression class --------
#
# build_merged_json defaults a missing/malformed whisker sidecar to det "?"
# (fusion_report._verdict) and its coverage to unigram 0.0. Ranking "?" as a
# real tier would turn an infrastructure gap into an exit-3 regression, and
# the reverse transition into an "improvement" that hides a genuine fail.


def test_delta_llm_det_pass_to_unknown_is_not_a_regression(tmp_path, capsys):
    _write_llm_reports(
        tmp_path,
        [_merged_row("P1", det="pass", unigram=0.98)],
        [_merged_row("P1", det="?", unigram=0.0)],
    )

    rc = delta_main(["--llm", "--report-dir", str(tmp_path)])

    assert rc == C.EXIT_OK
    out = capsys.readouterr().out
    assert "regressed" not in out
    assert "unchanged: 1" in out


def test_delta_llm_det_fail_to_unknown_is_not_an_improvement(tmp_path, capsys):
    # The dangerous direction: a lost sidecar must never read as a paper
    # getting better, which would retire a real failure from the report.
    _write_llm_reports(
        tmp_path,
        [_merged_row("P1", det="not-llm-readable", unigram=0.50)],
        [_merged_row("P1", det="?", unigram=0.0)],
    )

    rc = delta_main(["--llm", "--report-dir", str(tmp_path)])

    assert rc == C.EXIT_OK
    assert "improved" not in capsys.readouterr().out


def test_delta_llm_det_unknown_to_pass_is_not_an_improvement(tmp_path, capsys):
    _write_llm_reports(
        tmp_path,
        [_merged_row("P1", det="?", unigram=0.0)],
        [_merged_row("P1", det="pass", unigram=0.98)],
    )

    rc = delta_main(["--llm", "--report-dir", str(tmp_path)])

    assert rc == C.EXIT_OK
    assert "improved" not in capsys.readouterr().out


def test_delta_llm_unknown_det_does_not_mask_a_real_regression_elsewhere(tmp_path, capsys):
    # The sentinel row is withheld; a genuine regression on another paper in
    # the same report must still be reported. Exit stays 0 (this view never
    # gates), so the rendered section is the whole signal and must be right.
    _write_llm_reports(
        tmp_path,
        [_merged_row("P1", det="pass"), _merged_row("P2", det="pass")],
        [_merged_row("P1", det="?", unigram=0.0), _merged_row("P2", det="not-llm-readable")],
    )

    rc = delta_main(["--llm", "--report-dir", str(tmp_path)])

    assert rc == C.EXIT_OK
    out = capsys.readouterr().out
    assert "regressed (1)" in out
    assert "P2" in out


def test_compute_delta_verdict_sentinels_withhold_the_whole_row():
    prev = [{"pid": "P1", "det": "pass", "unigram": 0.98}]
    curr = [{"pid": "P1", "det": "?", "unigram": 0.0}]

    result = compute_delta(
        prev, curr, verdict_field="det", watched_metrics=("unigram",),
        results_key=None, verdict_sentinels=("?", "-"),
    )

    assert not result.any_regressed
    f = result.unchanged()[0]
    assert f.status == STATUS_UNCHANGED
    assert "not comparable" in f.reason
    # the synthetic 0.0 coverage is still reported, just not acted on
    assert f.metrics["unigram"].curr == 0.0


def test_compute_delta_without_sentinels_still_ranks_unknown_verdicts():
    # Backward compat: the det lane passes no sentinels and keeps the old
    # defensive behavior (unknown ranks as review).
    prev = [{"pid": "P1", "det": "pass"}]
    curr = [{"pid": "P1", "det": "?"}]

    result = compute_delta(
        prev, curr, verdict_field="det", watched_metrics=(), results_key=None,
    )

    assert result.any_regressed


def test_delta_llm_replayed_count_counts_only_truthy(tmp_path, capsys):
    _write_llm_reports(
        tmp_path,
        [_merged_row("P1", det="pass", unigram=0.98)],
        [
            _merged_row("P1", det="pass", unigram=0.98, replayed=True),
            _merged_row("P2", det="pass", unigram=0.98, replayed=False),
        ],
    )

    rc = delta_main(["--llm", "--report-dir", str(tmp_path)])

    assert rc == C.EXIT_OK
    out = capsys.readouterr().out
    assert "replayed (warm-skipped, unchanged): 1" in out


def test_delta_llm_json_output_shape(tmp_path, capsys):
    _write_llm_reports(
        tmp_path,
        [_merged_row("P1", det="pass", llm="pass", unigram=0.98)],
        [_merged_row("P1", det="not-llm-readable", llm="review", unigram=0.80, replayed=True)],
    )

    rc = delta_main(["--llm", "--report-dir", str(tmp_path), "--json"])

    # Exit stays 0; a machine consumer that wants the det movement reads
    # det_delta.any_regressed instead of the exit code.
    assert rc == C.EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["det_delta"]["any_regressed"] is True
    assert payload["llm_advisory_movers"] == [
        {"pid": "P1", "prev_llm": "pass", "curr_llm": "review"}
    ]
    assert payload["replayed_count"] == 1
    assert payload["stale"] is False


def test_delta_llm_missing_current_report_is_operational_error(tmp_path):
    _write_llm_reports(tmp_path, [_merged_row("P1")])
    rc = delta_main(["--llm", "--report-dir", str(tmp_path)])
    assert rc == C.EXIT_ERROR


def test_delta_llm_missing_baseline_is_operational_error(tmp_path):
    (tmp_path / "report-merged.json").write_text(
        json.dumps([_merged_row("P1")]), encoding="utf-8",
    )
    rc = delta_main(["--llm", "--report-dir", str(tmp_path)])
    assert rc == C.EXIT_ERROR


def test_delta_llm_explicit_baseline_override(tmp_path):
    baseline = tmp_path / "custom-merged-baseline.json"
    _write_llm_reports(
        tmp_path,
        [_merged_row("P1", det="pass")],
        [_merged_row("P1", det="not-llm-readable")],
        baseline_path=baseline,
    )

    rc = delta_main(
        ["--llm", "--report-dir", str(tmp_path), "--baseline", str(baseline)]
    )

    assert rc == C.EXIT_OK


# -- whisker delta --llm: staleness detection ------------------------------------


def test_llm_report_is_stale_when_sidecar_postdates_aggregate(tmp_path):
    merged = tmp_path / "report-merged.json"
    merged.write_text("[]", encoding="utf-8")
    sidecar = tmp_path / "p1.whisker.tapetum.json"
    sidecar.write_text("{}", encoding="utf-8")
    os.utime(merged, (1_000_000, 1_000_000))
    os.utime(sidecar, (2_000_000, 2_000_000))

    assert _llm_report_is_stale(tmp_path) is True


def test_llm_report_is_stale_false_when_aggregate_postdates_sidecar(tmp_path):
    sidecar = tmp_path / "p1.whisker.tapetum.json"
    sidecar.write_text("{}", encoding="utf-8")
    merged = tmp_path / "report-merged.json"
    merged.write_text("[]", encoding="utf-8")
    os.utime(sidecar, (1_000_000, 1_000_000))
    os.utime(merged, (2_000_000, 2_000_000))

    assert _llm_report_is_stale(tmp_path) is False


def test_llm_report_is_stale_false_with_no_sidecars(tmp_path):
    (tmp_path / "report-merged.json").write_text("[]", encoding="utf-8")
    assert _llm_report_is_stale(tmp_path) is False


def test_llm_report_is_stale_false_with_no_aggregate(tmp_path):
    (tmp_path / "p1.whisker.tapetum.json").write_text("{}", encoding="utf-8")
    assert _llm_report_is_stale(tmp_path) is False


def test_llm_report_is_stale_when_a_det_sidecar_postdates_the_aggregate(tmp_path):
    # The blind spot: `whisker --all` moves det sidecars and nothing else. The
    # aggregate's det column is frozen, but no tapetum sidecar moved, so a
    # tapetum-only mtime check calls this fresh.
    det_dir = tmp_path / "det"
    llm_dir = tmp_path / "llm"
    det_dir.mkdir()
    llm_dir.mkdir()
    (llm_dir / "p1.whisker.tapetum.json").write_text("{}", encoding="utf-8")
    merged = llm_dir / "report-merged.json"
    merged.write_text("[]", encoding="utf-8")
    det_sidecar = det_dir / "p1.whisker.json"
    det_sidecar.write_text("{}", encoding="utf-8")
    os.utime(llm_dir / "p1.whisker.tapetum.json", (1_000_000, 1_000_000))
    os.utime(merged, (2_000_000, 2_000_000))
    os.utime(det_sidecar, (3_000_000, 3_000_000))

    assert _llm_report_is_stale(llm_dir) is False
    assert _llm_report_is_stale(llm_dir, det_dir) is True


def test_llm_report_is_stale_false_when_aggregate_postdates_det_sidecar(tmp_path):
    det_dir = tmp_path / "det"
    llm_dir = tmp_path / "llm"
    det_dir.mkdir()
    llm_dir.mkdir()
    det_sidecar = det_dir / "p1.whisker.json"
    det_sidecar.write_text("{}", encoding="utf-8")
    (llm_dir / "p1.whisker.tapetum.json").write_text("{}", encoding="utf-8")
    merged = llm_dir / "report-merged.json"
    merged.write_text("[]", encoding="utf-8")
    os.utime(det_sidecar, (1_000_000, 1_000_000))
    os.utime(llm_dir / "p1.whisker.tapetum.json", (1_000_000, 1_000_000))
    os.utime(merged, (2_000_000, 2_000_000))

    assert _llm_report_is_stale(llm_dir, det_dir) is False


def test_llm_report_is_stale_tolerates_a_flat_report_dir(tmp_path):
    # --report-dir puts both lanes in one directory, so det_dir == llm_dir.
    # The two globs must not collide: a tapetum sidecar is not a det sidecar.
    merged = tmp_path / "report-merged.json"
    merged.write_text("[]", encoding="utf-8")
    tap = tmp_path / "p1.whisker.tapetum.json"
    tap.write_text("{}", encoding="utf-8")
    os.utime(tap, (1_000_000, 1_000_000))
    os.utime(merged, (2_000_000, 2_000_000))

    assert _llm_report_is_stale(tmp_path, tmp_path) is False

    det_sidecar = tmp_path / "p1.whisker.json"
    det_sidecar.write_text("{}", encoding="utf-8")
    os.utime(det_sidecar, (3_000_000, 3_000_000))

    assert _llm_report_is_stale(tmp_path, tmp_path) is True


def test_llm_report_is_stale_false_with_only_det_sidecars_and_no_aggregate(tmp_path):
    (tmp_path / "p1.whisker.json").write_text("{}", encoding="utf-8")
    assert _llm_report_is_stale(tmp_path, tmp_path) is False


# -- the merged-report snapshot seam that produces the --llm baseline ------------


def test_snapshot_prev_merged_report_is_noop_on_first_run(tmp_path):
    _snapshot_prev_merged_report(tmp_path)
    assert not (tmp_path / "report-merged.prev.json").exists()


def test_snapshot_prev_merged_report_copies_existing_report(tmp_path):
    merged = tmp_path / "report-merged.json"
    merged.write_text('[{"pid": "P1"}]', encoding="utf-8")

    _snapshot_prev_merged_report(tmp_path)

    prev = tmp_path / "report-merged.prev.json"
    assert prev.read_text(encoding="utf-8") == '[{"pid": "P1"}]'
    # the live aggregate is untouched by the snapshot step itself
    assert merged.read_text(encoding="utf-8") == '[{"pid": "P1"}]'


def test_snapshot_prev_merged_report_overwrites_prior_snapshot(tmp_path):
    merged = tmp_path / "report-merged.json"
    merged.write_text('[{"pid": "P1"}]', encoding="utf-8")
    _snapshot_prev_merged_report(tmp_path)
    merged.write_text('[{"pid": "P2"}]', encoding="utf-8")
    _snapshot_prev_merged_report(tmp_path)

    prev = tmp_path / "report-merged.prev.json"
    assert prev.read_text(encoding="utf-8") == '[{"pid": "P2"}]'


def test_snapshot_prev_merged_report_round_trips_into_a_clean_delta(tmp_path, capsys):
    # End-to-end on the real seam: what the snapshot writes must be exactly
    # what `whisker delta --llm` can read back as a baseline.
    rows = [_merged_row("P1", det="pass"), _merged_row("P2", det="review")]
    (tmp_path / "report-merged.json").write_text(json.dumps(rows), encoding="utf-8")

    _snapshot_prev_merged_report(tmp_path)
    rc = delta_main(["--llm", "--report-dir", str(tmp_path)])

    assert rc == C.EXIT_OK
    assert "unchanged: 2" in capsys.readouterr().out


# -- absent-marker symmetry: the curr side must be filtered too ------------------


def test_delta_llm_excludes_absent_marker_on_curr_side(tmp_path, capsys):
    # Mirror of the prev-side test above: losing LLM coverage is a coverage
    # change, not a judge-tier disagreement.
    _write_llm_reports(
        tmp_path,
        [_merged_row("P1", det="pass", llm="pass")],
        [_merged_row("P1", det="pass", llm="-")],
    )

    rc = delta_main(["--llm", "--report-dir", str(tmp_path)])

    assert rc == C.EXIT_OK
    out = capsys.readouterr().out
    assert "  none" in out
    assert "P1 [pass -> -]" not in out


def test_delta_llm_missing_det_key_entirely_is_not_a_regression(tmp_path, capsys):
    # A row that omits `det` outright (hand-edited or foreign JSON) reads as
    # None; absent is absent however it is spelled.
    prev = [_merged_row("P1", det="pass")]
    curr = [_merged_row("P1")]
    del curr[0]["det"]
    _write_llm_reports(tmp_path, prev, curr)

    rc = delta_main(["--llm", "--report-dir", str(tmp_path)])

    assert rc == C.EXIT_OK
    assert "regressed" not in capsys.readouterr().out
