#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

import hashlib
import json
from datetime import datetime, timezone

import pytest
from whisker import constants as C
from whisker.det.calibrate import (
    CALIBRATION_ARTIFACT_SCHEMA_VERSION,
    DEFAULT_TARGET_FPR_FAIL_EDGE,
    DEFAULT_TARGET_FPR_REVIEW_EDGE,
    MIN_SAMPLES_PER_CLASS_PER_SPLIT,
    InsufficientCalibrationDataError,
    bootstrap_holdout_band,
    calibrate_threshold,
    calibrate_threshold_with_holdout,
)
from whisker.det.cli import calibrate_main

# -- calibrate_threshold (single-set fit, internal building block) -----------


def test_separable_data_recovers_a_perfect_edge():
    # bad (positive) papers cluster low, good cluster high, clean gap at 0.8.
    bad = [(0.50, True), (0.60, True), (0.70, True)]
    good = [(0.90, False), (0.95, False), (0.99, False)]
    fit = calibrate_threshold(bad + good, name="edge", target_fpr=0.05)
    c = fit.chosen
    # A threshold in (0.70, 0.90] flags all bad, no good: perfect separation.
    assert c.tpr == 1.0
    assert c.fpr == 0.0
    assert c.precision == 1.0
    assert 0.70 < c.threshold <= 0.90
    assert fit.method == "max_tpr_at_fpr"


def test_fpr_ceiling_is_respected():
    # Overlapping classes: a good paper sits at 0.72 among the bad ones.
    bad = [(0.50, True), (0.60, True), (0.70, True)]
    good = [(0.72, False), (0.95, False), (0.99, False), (0.98, False)]
    fit = calibrate_threshold(bad + good, name="edge", target_fpr=0.0)
    # With FPR ceiling 0.0, the chosen edge must flag zero good papers.
    assert fit.chosen.fpr == 0.0
    assert fit.chosen.fp == 0


def test_youden_fallback_when_no_threshold_meets_ceiling():
    # Force infeasibility: every flag of a bad paper also flags a good one.
    bad = [(0.50, True)]
    good = [(0.50, False)]  # identical value -> any flagging is symmetric
    fit = calibrate_threshold(
        [(0.50, True), (0.50, False), (0.40, True), (0.90, False)],
        name="edge", target_fpr=0.0,
    )
    # target 0.0 may be infeasible if catching the 0.50 bad also catches 0.50 good
    assert fit.method in ("max_tpr_at_fpr", "youden_j")
    # Youden's J of the chosen point is the max over the curve when fallback hits.
    if fit.method == "youden_j":
        assert fit.chosen.youden_j == max(op.youden_j for op in fit.curve)


def test_requires_both_classes():
    with pytest.raises(ValueError):
        calibrate_threshold([(0.5, True), (0.6, True)], name="edge")
    with pytest.raises(ValueError):
        calibrate_threshold([(0.5, False), (0.6, False)], name="edge")


def test_confusion_counts_are_consistent():
    bad = [(0.50, True), (0.60, True)]
    good = [(0.90, False), (0.95, False)]
    fit = calibrate_threshold(bad + good, name="edge")
    for op in fit.curve:
        assert op.tp + op.fn == fit.n_pos
        assert op.fp + op.tn == fit.n_neg
        # rates in [0, 1]
        assert 0.0 <= op.tpr <= 1.0
        assert 0.0 <= op.fpr <= 1.0
        assert 0.0 <= op.precision <= 1.0


def test_monotonic_tpr_along_increasing_threshold():
    # As the edge rises (flag more), TPR is non-decreasing (a "< t" gate only
    # adds flagged items as t grows).
    bad = [(0.50, True), (0.65, True), (0.75, True)]
    good = [(0.85, False), (0.92, False)]
    fit = calibrate_threshold(bad + good, name="edge")
    ordered = sorted(fit.curve, key=lambda op: op.threshold)
    tprs = [op.tpr for op in ordered]
    assert tprs == sorted(tprs)


def test_result_is_json_serializable():
    bad = [(0.50, True), (0.60, True)]
    good = [(0.90, False), (0.95, False)]
    fit = calibrate_threshold(bad + good, name="unigram_coverage_fail_edge")
    d = fit.to_dict()
    assert d["name"] == "unigram_coverage_fail_edge"
    assert "chosen" in d and "curve" in d
    assert d["n"] == 4


@pytest.mark.parametrize("bad_fpr", [-0.1, 1.5, float("nan")])
def test_target_fpr_out_of_range_raises(bad_fpr):
    samples = [(0.5, True), (0.9, False)]
    with pytest.raises(ValueError):
        calibrate_threshold(samples, name="edge", target_fpr=bad_fpr)


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_sample_value_raises(bad_value):
    # A NaN/inf coverage makes every `value < threshold` silently False and would
    # corrupt the ROC: reject rather than drop the labeled data silently.
    samples = [(bad_value, True), (0.9, False), (0.5, True)]
    with pytest.raises(ValueError):
        calibrate_threshold(samples, name="edge")


def test_default_target_fpr_is_the_fail_edge_default():
    # calibrate_threshold is kept as an internal building block; its default
    # matches the STRICTER of the two named ceilings (fail edge), preserving
    # the old DEFAULT_TARGET_FPR=0.05 numeric behavior for un-migrated callers.
    bad = [(0.50, True), (0.60, True)]
    good = [(0.90, False), (0.95, False)]
    explicit = calibrate_threshold(
        bad + good, name="edge", target_fpr=DEFAULT_TARGET_FPR_FAIL_EDGE
    )
    implicit = calibrate_threshold(bad + good, name="edge")
    assert explicit.chosen.threshold == implicit.chosen.threshold
    assert explicit.target_fpr == implicit.target_fpr


# -- Two distinct FPR ceilings ------------------------------------------------


def test_fail_and_review_ceilings_are_distinct_and_ordered():
    # Fail edge (more severe error: blocks a good paper) gets the STRICTER
    # (lower) ceiling; review edge (cheaper, recoverable error) gets the
    # looser one. Also pins the exact reconciliation values from CLAUDE.md.
    assert DEFAULT_TARGET_FPR_FAIL_EDGE == 0.05
    assert DEFAULT_TARGET_FPR_REVIEW_EDGE == 0.10
    assert DEFAULT_TARGET_FPR_FAIL_EDGE < DEFAULT_TARGET_FPR_REVIEW_EDGE


# -- calibrate_threshold_with_holdout (fit/holdout split, P16 2.2) -----------


def _tagged(pairs, split):
    return [(v, is_bad, split) for v, is_bad in pairs]


def test_holdout_fit_reports_calibration_and_holdout_separately():
    calibration = _tagged(
        [(0.50, True)] * 5 + [(0.90, False)] * 5, "calibration"
    )
    holdout = _tagged(
        [(0.55, True)] * 5 + [(0.92, False)] * 5, "holdout"
    )
    result = calibrate_threshold_with_holdout(
        calibration + holdout, name="edge", target_fpr=0.05
    )
    assert result.name == "edge"
    assert result.calibration.n_pos == 5 and result.calibration.n_neg == 5
    assert result.holdout.n_pos == 5 and result.holdout.n_neg == 5
    # Perfectly separable data on both splits at this threshold.
    assert result.holdout.tpr == 1.0
    assert result.holdout.fpr == 0.0
    assert result.holdout.precision == 1.0


def test_holdout_point_never_influences_selected_threshold():
    """The adversarial holdout point: proves holdout cannot move tau.

    Calibration-only data (5 bad @ 0.50, 5 good @ 0.90) at target_fpr=0.0
    selects tau=0.90 (the only feasible, fully-separating threshold). A good
    example at 0.60 would, if it leaked into the CALIBRATION split, collapse
    that feasibility (0.90 now flags the 0.60 point too) and shift tau down
    to 0.60 for a still-fully-separating fit. Tagging it "holdout" instead
    must leave tau at 0.90, unaffected by its presence.
    """
    calibration_core = _tagged([(0.50, True)] * 5 + [(0.90, False)] * 5, "calibration")
    holdout_core = _tagged([(0.50, True)] * 5 + [(0.90, False)] * 5, "holdout")
    adversarial = (0.60, False)

    # Adversarial point tagged holdout: must NOT move tau.
    with_holdout_tag = (
        calibration_core + holdout_core + [(*adversarial, "holdout")]
    )
    result = calibrate_threshold_with_holdout(with_holdout_tag, name="edge", target_fpr=0.0)
    assert result.calibration.chosen.threshold == pytest.approx(0.90)

    # Same point tagged calibration: proves it WOULD have moved tau had it
    # leaked in, so the first assertion is actually exercising the guard.
    with_calibration_tag = (
        calibration_core + [(*adversarial, "calibration")] + holdout_core
    )
    leaked = calibrate_threshold_with_holdout(with_calibration_tag, name="edge", target_fpr=0.0)
    assert leaked.calibration.chosen.threshold == pytest.approx(0.60)
    assert leaked.calibration.chosen.threshold != result.calibration.chosen.threshold


def test_split_partition_is_total_and_disjoint():
    """Every input sample lands in exactly one bucket; no double-counting."""
    calibration = _tagged([(0.50, True)] * 5 + [(0.90, False)] * 5, "calibration")
    holdout = _tagged([(0.55, True)] * 6 + [(0.92, False)] * 7, "holdout")
    samples = calibration + holdout
    result = calibrate_threshold_with_holdout(samples, name="edge", target_fpr=0.05)

    total_calibration = result.calibration.n_pos + result.calibration.n_neg
    total_holdout = result.holdout.n_pos + result.holdout.n_neg
    assert total_calibration == len(calibration)
    assert total_holdout == len(holdout)
    assert total_calibration + total_holdout == len(samples)


def test_unknown_split_value_raises():
    samples = (
        _tagged([(0.50, True)] * 5, "training")
        + _tagged([(0.90, False)] * 5, "calibration")
        + _tagged([(0.50, True)] * 5 + [(0.90, False)] * 5, "holdout")
    )
    with pytest.raises(InsufficientCalibrationDataError, match="unknown split"):
        calibrate_threshold_with_holdout(samples, name="edge", target_fpr=0.05)


def test_calibration_split_missing_class_raises():
    samples = (
        _tagged([(0.50, True)] * 5, "calibration")  # no negatives
        + _tagged([(0.50, True)] * 5 + [(0.90, False)] * 5, "holdout")
    )
    with pytest.raises(InsufficientCalibrationDataError, match="calibration split has 0 negative"):
        calibrate_threshold_with_holdout(samples, name="edge", target_fpr=0.05)


def test_holdout_split_missing_class_raises():
    samples = (
        _tagged([(0.50, True)] * 5 + [(0.90, False)] * 5, "calibration")
        + _tagged([(0.50, True)] * 5, "holdout")  # no negatives -> undefined FPR
    )
    with pytest.raises(InsufficientCalibrationDataError, match="holdout split has 0 negative"):
        calibrate_threshold_with_holdout(samples, name="edge", target_fpr=0.05)
    # Message must name what's missing and never silently report 0/0 as 0.0.
    with pytest.raises(InsufficientCalibrationDataError, match="cannot compute a defined FPR"):
        calibrate_threshold_with_holdout(samples, name="edge", target_fpr=0.05)


def test_total_n_below_floor_raises():
    # Both classes present in both splits, but under MIN_SAMPLES_PER_CLASS_PER_SPLIT.
    assert MIN_SAMPLES_PER_CLASS_PER_SPLIT > 2  # otherwise this fixture proves nothing
    samples = (
        _tagged([(0.50, True)] * 2 + [(0.90, False)] * 2, "calibration")
        + _tagged([(0.50, True)] * 5 + [(0.90, False)] * 5, "holdout")
    )
    with pytest.raises(InsufficientCalibrationDataError, match="need at least"):
        calibrate_threshold_with_holdout(samples, name="edge", target_fpr=0.05)


# -- bootstrap_holdout_band ---------------------------------------------------


def _holdout_pairs():
    return [(0.50, True)] * 8 + [(0.90, False)] * 8 + [(0.70, False)] * 2


def test_bootstrap_band_is_deterministic_for_the_same_seed():
    band1 = bootstrap_holdout_band(_holdout_pairs(), threshold=0.80, n_resamples=200, seed=42)
    band2 = bootstrap_holdout_band(_holdout_pairs(), threshold=0.80, n_resamples=200, seed=42)
    assert band1 == band2


def test_bootstrap_band_can_differ_for_a_different_seed():
    # Intent: a different seed CAN change the resampled band (never asserted
    # as a hard guarantee across all inputs, since a theoretical seed
    # collision cannot be ruled out in general -- this fixture demonstrates
    # the intended sensitivity to `seed`, it does not prove a property).
    band_a = bootstrap_holdout_band(_holdout_pairs(), threshold=0.80, n_resamples=200, seed=1)
    band_b = bootstrap_holdout_band(_holdout_pairs(), threshold=0.80, n_resamples=200, seed=2)
    assert band_a != band_b


def test_bootstrap_band_bounds_are_sane():
    band = bootstrap_holdout_band(_holdout_pairs(), threshold=0.80, n_resamples=500, seed=7)
    assert 0.0 <= band.tpr_lo <= band.tpr_hi <= 1.0
    assert 0.0 <= band.fpr_lo <= band.fpr_hi <= 1.0
    assert band.n_resamples == 500
    assert band.seed == 7


def test_bootstrap_band_requires_both_classes_in_holdout():
    with pytest.raises(InsufficientCalibrationDataError):
        bootstrap_holdout_band([(0.5, True)] * 5, threshold=0.6, seed=1)
    with pytest.raises(InsufficientCalibrationDataError):
        bootstrap_holdout_band([(0.9, False)] * 5, threshold=0.6, seed=1)


def test_bootstrap_band_uses_local_random_never_global_state():
    """A prior call (or any other code) touching the global `random` module
    must not perturb the result: the function seeds its OWN generator."""
    import random as random_module

    random_module.seed(12345)
    random_module.random()
    random_module.random()
    band_after_global_use = bootstrap_holdout_band(
        _holdout_pairs(), threshold=0.80, n_resamples=200, seed=99
    )
    random_module.seed(999999)
    for _ in range(17):
        random_module.random()
    band_after_different_global_state = bootstrap_holdout_band(
        _holdout_pairs(), threshold=0.80, n_resamples=200, seed=99
    )
    assert band_after_global_use == band_after_different_global_state


# -- CLI: `whisker calibrate` (provenance, split loading, two ceilings) ------


def _write_labels(tmp_path, n_per_class_per_split=5):
    """A synthetic labels file with fail/pass papers split calibration/holdout.

    unigram_coverage is supplied directly so the CLI never needs a backend.
    """
    records = []
    for split, base in (("calibration", 0), ("holdout", 100)):
        for i in range(n_per_class_per_split):
            records.append({
                "pid": f"F{base + i}",
                "label": "not-llm-readable",
                "split": split,
                "unigram_coverage": 0.50 + i * 0.01,
            })
        for i in range(n_per_class_per_split):
            records.append({
                "pid": f"P{base + i}",
                "label": "pass",
                "split": split,
                "unigram_coverage": 0.90 + i * 0.01,
            })
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return path


def test_cli_provenance_fields_are_complete_and_plausible(tmp_path):
    labels_path = _write_labels(tmp_path)
    out_path = tmp_path / "thresholds.json"
    fixed_now = datetime(2026, 1, 15, 12, 30, 0, tzinfo=timezone.utc)

    rc = calibrate_main(["--labels", str(labels_path), "--out", str(out_path)], now=fixed_now)
    assert rc == C.EXIT_OK

    payload = json.loads(out_path.read_text(encoding="utf-8"))

    # calibrator/schema version: the calibration artifact's OWN version, not
    # whisker.constants.WHISKER_SCHEMA_VERSION (the per-paper scoring schema).
    assert payload["schema_version"] == CALIBRATION_ARTIFACT_SCHEMA_VERSION
    assert payload["calibrator_version"] == CALIBRATION_ARTIFACT_SCHEMA_VERSION
    assert payload["schema_version"] != C.WHISKER_SCHEMA_VERSION

    # timestamp: ISO-8601, matches the injected clock exactly.
    assert payload["calibration_timestamp"] == fixed_now.isoformat()
    assert datetime.fromisoformat(payload["calibration_timestamp"]) == fixed_now

    # calibration dataset reference: SHA-256 of the raw bytes on disk.
    sha = payload["labels_file_sha256"]
    assert len(sha) == 64
    assert all(c in "0123456789abcdef" for c in sha)
    assert sha == hashlib.sha256(labels_path.read_bytes()).hexdigest()

    assert isinstance(payload["split_assignment_source"], str) and payload[
        "split_assignment_source"
    ]

    for edge_name in ("unigram_coverage_fail_edge", "unigram_coverage_review_edge"):
        fitted = payload["fitted"][edge_name]
        # Selection rule (method) and tau are surfaced on the calibration side.
        assert fitted["calibration"]["method"] in ("max_tpr_at_fpr", "youden_j")
        assert isinstance(fitted["calibration"]["chosen"]["threshold"], float)
        # Per-split class counts, reported SEPARATELY (not one combined n).
        assert fitted["calibration"]["n_pos"] == 5
        assert fitted["calibration"]["n_neg"] == 5
        assert fitted["holdout"]["n_pos"] == 5
        assert fitted["holdout"]["n_neg"] == 5
        # TPR/FPR/precision/recall on holdout only.
        for key in ("tpr", "fpr", "precision", "recall", "tp", "fp", "tn", "fn"):
            assert key in fitted["holdout"]


def test_cli_defaults_use_distinct_fpr_ceilings_per_edge(tmp_path):
    labels_path = _write_labels(tmp_path)
    out_path = tmp_path / "thresholds.json"
    rc = calibrate_main(["--labels", str(labels_path), "--out", str(out_path)])
    assert rc == C.EXIT_OK
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert (
        payload["fitted"]["unigram_coverage_fail_edge"]["calibration"]["target_fpr"]
        == DEFAULT_TARGET_FPR_FAIL_EDGE
    )
    assert (
        payload["fitted"]["unigram_coverage_review_edge"]["calibration"]["target_fpr"]
        == DEFAULT_TARGET_FPR_REVIEW_EDGE
    )


def test_cli_fail_and_review_target_fpr_flags_are_independently_overridable(tmp_path):
    labels_path = _write_labels(tmp_path)
    out_path = tmp_path / "thresholds.json"
    rc = calibrate_main([
        "--labels", str(labels_path), "--out", str(out_path),
        "--fail-target-fpr", "0.20", "--review-target-fpr", "0.30",
    ])
    assert rc == C.EXIT_OK
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["fitted"]["unigram_coverage_fail_edge"]["calibration"]["target_fpr"] == 0.20
    assert payload["fitted"]["unigram_coverage_review_edge"]["calibration"]["target_fpr"] == 0.30


def test_cli_labels_missing_split_field_names_the_pid(tmp_path, caplog):
    records = [{"pid": "P1", "label": "not-llm-readable", "unigram_coverage": 0.5}]
    labels_path = tmp_path / "labels.json"
    labels_path.write_text(json.dumps(records), encoding="utf-8")

    rc = calibrate_main(["--labels", str(labels_path)])
    assert rc == C.EXIT_ERROR
    assert "P1" in caplog.text
    assert "split" in caplog.text


def test_cli_labels_invalid_split_value_names_the_pid(tmp_path, caplog):
    records = [
        {"pid": "P1", "label": "not-llm-readable", "split": "training", "unigram_coverage": 0.5},
    ]
    labels_path = tmp_path / "labels.json"
    labels_path.write_text(json.dumps(records), encoding="utf-8")

    rc = calibrate_main(["--labels", str(labels_path)])
    assert rc == C.EXIT_ERROR
    assert "P1" in caplog.text
    assert "split" in caplog.text


def test_cli_mapping_form_labels_file_is_rejected(tmp_path, caplog):
    # The legacy {pid: label} mapping form cannot carry a per-entry split, so
    # it is no longer accepted (P16 2.2 requires a frozen split assignment).
    labels_path = tmp_path / "labels.json"
    labels_path.write_text(json.dumps({"P1": "not-llm-readable"}), encoding="utf-8")

    rc = calibrate_main(["--labels", str(labels_path)])
    assert rc == C.EXIT_ERROR
    assert "split" in caplog.text.lower()


def test_cli_insufficient_data_fails_loudly(tmp_path, caplog):
    records = [
        {"pid": "P1", "label": "not-llm-readable", "split": "calibration", "unigram_coverage": 0.5},
        {"pid": "P2", "label": "pass", "split": "holdout", "unigram_coverage": 0.9},
    ]
    labels_path = tmp_path / "labels.json"
    labels_path.write_text(json.dumps(records), encoding="utf-8")

    rc = calibrate_main(["--labels", str(labels_path)])
    assert rc == C.EXIT_ERROR
    assert "calibration failed" in caplog.text


# -- Per-edge partial fit: only the review edge has enough data (PROTOCOL.md §13) --


def _write_review_only_labels(tmp_path, n_per_class_per_split=5):
    """A labels file with ZERO ``fail``-labeled papers, but enough ``pass`` and
    ``review`` labels for the review edge to fit cleanly.

    Mirrors PROTOCOL.md section 13's real-world finding: across the full
    376-paper corpus, only 4 papers fall below the fail edge, far short of
    ``MIN_SAMPLES_PER_CLASS_PER_SPLIT``'s 10-positive-total floor, so the fail
    edge cannot be fitted at all (0 positive examples), while the review
    edge's 49-paper mid band supports a real fit.
    """
    records = []
    for split, base in (("calibration", 0), ("holdout", 100)):
        for i in range(n_per_class_per_split):
            records.append({
                "pid": f"P{base + i}",
                "label": "pass",
                "split": split,
                "unigram_coverage": 0.97 + i * 0.001,
            })
        for i in range(n_per_class_per_split):
            records.append({
                "pid": f"R{base + i}",
                "label": "review",
                "split": split,
                "unigram_coverage": 0.87 + i * 0.001,
            })
        # Deliberately no "not-llm-readable"-labeled records at all.
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return path


def test_cli_review_only_partial_fit_succeeds_with_documented_fail_non_fit(tmp_path):
    """The exact scenario this task targets: the fail edge is structurally
    unfittable (0 positive examples), the review edge fits cleanly. The run
    must NOT abort: it exits OK, writes a real review fit, and documents the
    fail edge's non-fit rather than silently dropping it or crashing.
    """
    labels_path = _write_review_only_labels(tmp_path)
    out_path = tmp_path / "thresholds.json"

    rc = calibrate_main(["--labels", str(labels_path), "--out", str(out_path)])

    assert rc == C.EXIT_OK
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    # Review edge: a real, fully-shaped fit.
    review_fit = payload["fitted"]["unigram_coverage_review_edge"]
    assert review_fit is not None
    assert review_fit["calibration"]["method"] in ("max_tpr_at_fpr", "youden_j")
    assert isinstance(review_fit["calibration"]["chosen"]["threshold"], float)
    assert review_fit["holdout"]["n_pos"] == 5 and review_fit["holdout"]["n_neg"] == 5

    # Fail edge: documented non-fit, not a crash and not silently dropped.
    assert payload["fitted"]["unigram_coverage_fail_edge"] is None
    fail_reason = payload["not_fit_reason"]["unigram_coverage_fail_edge"]
    assert isinstance(fail_reason, str) and fail_reason.strip()
    assert "unigram_coverage_review_edge" not in payload["not_fit_reason"]

    # Nothing to compare when one edge is unfit: explicitly None, not True/False.
    assert payload["edge_ordering_ok"] is None

    # "current" always reflects the live constants regardless of fit outcome.
    assert payload["current"]["unigram_coverage_fail_edge"] == C.UNIGRAM_COVERAGE_FAIL_EDGE
    assert payload["current"]["unigram_coverage_review_edge"] == C.UNIGRAM_COVERAGE_REVIEW_EDGE


def test_cli_both_edges_unfittable_still_exits_error(tmp_path, caplog):
    """When NEITHER edge can be fitted (e.g. every label is "pass"), the run
    must still fail loudly, exactly as before this change: a complete failure
    stays a complete failure.
    """
    records = [
        {"pid": "P1", "label": "pass", "split": "calibration", "unigram_coverage": 0.97},
        {"pid": "P2", "label": "pass", "split": "holdout", "unigram_coverage": 0.98},
    ]
    labels_path = tmp_path / "labels.json"
    labels_path.write_text(json.dumps(records), encoding="utf-8")

    rc = calibrate_main(["--labels", str(labels_path)])

    assert rc == C.EXIT_ERROR
    assert "calibration failed" in caplog.text
    assert "fail" in caplog.text.lower()
    assert "review" in caplog.text.lower()
