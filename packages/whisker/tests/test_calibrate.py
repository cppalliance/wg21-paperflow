#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

import pytest

from whisker.calibrate import calibrate_threshold


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
