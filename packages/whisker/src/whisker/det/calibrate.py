#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Fit whisker's content-coverage threshold edges from labeled data.

whisker's coverage band edges (``UNIGRAM_COVERAGE_FAIL_EDGE`` /
``UNIGRAM_COVERAGE_REVIEW_EDGE``) ship PROVISIONAL: hand-set from the
clean-paper expectation, never fitted on labeled outcomes. Almost none of the 28
surveyed converter projects calibrate at all (floors are engineering judgment),
so a real fit makes whisker measurably more principled than the field.

The gate is a "lower is worse" rule: a paper is FLAGGED when its
``unigram_coverage`` is BELOW the edge. Given samples labeled good/bad, this
module sweeps every reachable threshold, computes the full ROC confusion at
each, and selects the operating point that MAXIMIZES recall (true-positive rate,
bad papers caught) subject to a false-positive-rate ceiling, falling back to the
Youden-J maximizer when no threshold meets the ceiling. It reports the chosen
edge alongside its measured TPR/FPR/precision.

Fit/holdout separation (P16 criterion 2.2,
``packages/whisker/research/research/Audit/Auditv1/p16-threshold-calibration.md``):
fitting tau and reporting its TPR/FPR on the SAME labeled set is an
anti-gaming leak the audit calls out by name. ``calibrate_threshold`` (single
labeled set, no split) remains as an internal building block; the public path
is ``calibrate_threshold_with_holdout``, which partitions samples by a frozen
``split`` tag, selects tau on ``"calibration"``-split samples only, and reports
TPR/FPR/precision on ``"holdout"``-split samples that never influenced
selection.

This module returns data only. The CLI writes a ``thresholds.json`` artifact; a
human promotes the values into ``constants.py`` (thresholds are deliberate, see
the architecture-protection rule), exactly the audit the constants docstring
promises.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

__all__ = [
    "BootstrapBand",
    "CALIBRATION_ARTIFACT_SCHEMA_VERSION",
    "CalibrationResult",
    "DEFAULT_TARGET_FPR_FAIL_EDGE",
    "DEFAULT_TARGET_FPR_REVIEW_EDGE",
    "HoldoutCalibrationResult",
    "HoldoutEvaluation",
    "InsufficientCalibrationDataError",
    "MIN_SAMPLES_PER_CLASS_PER_SPLIT",
    "OperatingPoint",
    "Split",
    "bootstrap_holdout_band",
    "calibrate_threshold",
    "calibrate_threshold_with_holdout",
]

Split = Literal["calibration", "holdout"]

# Selection defaults: the largest false-positive rate tolerated while
# maximizing recall of bad conversions. The fail and review edges get
# DISTINCT ceilings because the two edges have asymmetric cost (reconciling
# the old single DEFAULT_TARGET_FPR=0.05 against CLAUDE.md's "FPR <= 10%"
# aspiration, which described the review edge, not the fail edge).
DEFAULT_TARGET_FPR_FAIL_EDGE = 0.05
"""Fail-edge target FPR ceiling: at most 1 in 20 good papers wrongly hard-failed.
A false positive here blocks a genuinely good paper — the more severe, less
recoverable error, so it gets the stricter ceiling."""

DEFAULT_TARGET_FPR_REVIEW_EDGE = 0.10
"""Review-edge target FPR ceiling: a false positive here only flags a good
paper for human review, a recoverable, cheaper error, so it can tolerate a
looser ceiling (matches the CLAUDE.md aspiration this constant reconciles)."""

# Conservative placeholder pending real P16 sample-size guidance (see
# p16-threshold-calibration.md criterion 2.3: "declared minimum N... class
# balance", isotonic-style guidance scaled down for a screening threshold
# sweep rather than a full isotonic regression). Five per class per split is
# enough to make every operating point non-degenerate (no 0/1 or 1/1 rates)
# without pretending to statistical power; raise this once real P16 sample-
# size guidance lands.
MIN_SAMPLES_PER_CLASS_PER_SPLIT = 5

# Calibration-artifact schema version. DISTINCT from
# whisker.constants.WHISKER_SCHEMA_VERSION (the per-paper scoring/sidecar
# schema): the calibration artifact versions independently from per-paper
# scoring, so a scoring-schema bump never forces a spurious calibration
# artifact bump and vice versa.
#
# Bumped 1 -> 2: the artifact semantics changed. ``fitted.<edge>`` may now be
# ``None`` when that edge is structurally unfittable (too few positive
# examples in the labeled pool, see PROTOCOL.md section 13's FAIL-edge
# finding), paired with a new ``not_fit_reason.<edge>`` field carrying the
# exact ``InsufficientCalibrationDataError`` text. A schema-1 consumer that
# assumed both edges are always present (e.g. blind dict access into
# ``fitted[key]["calibration"]``) would crash or silently mis-promote a
# ``None`` fit, so this is a genuine breaking change, not an additive one.
CALIBRATION_ARTIFACT_SCHEMA_VERSION = 2

_METHOD_AT_FPR = "max_tpr_at_fpr"
_METHOD_YOUDEN = "youden_j"

# Percentile bounds for the bootstrap band (95% central interval).
_BOOTSTRAP_LOWER_PERCENTILE = 2.5
_BOOTSTRAP_UPPER_PERCENTILE = 97.5


class InsufficientCalibrationDataError(ValueError):
    """Labeled samples cannot support a defensible fit/holdout calibration.

    Raised when: a split is missing one of the two classes (a discriminative
    threshold, or a defined TPR/FPR, does not exist without both), or a split
    has fewer than ``MIN_SAMPLES_PER_CLASS_PER_SPLIT`` examples of some class.
    A subclass of ``ValueError`` so existing ``except ValueError`` call sites
    keep working, but callers can catch this specific condition by name.
    """


@dataclass(frozen=True)
class OperatingPoint:
    """ROC confusion at one candidate threshold (flag iff value < threshold)."""

    threshold: float
    tpr: float
    fpr: float
    precision: float
    tp: int
    fp: int
    tn: int
    fn: int

    @property
    def youden_j(self) -> float:
        return self.tpr - self.fpr

    def to_dict(self) -> dict:
        return {
            "threshold": round(self.threshold, 4),
            "tpr": round(self.tpr, 4),
            "fpr": round(self.fpr, 4),
            "precision": round(self.precision, 4),
            "tp": self.tp,
            "fp": self.fp,
            "tn": self.tn,
            "fn": self.fn,
        }


@dataclass(frozen=True)
class CalibrationResult:
    name: str
    chosen: OperatingPoint
    target_fpr: float
    method: str
    n_pos: int
    n_neg: int
    curve: list[OperatingPoint]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "chosen": self.chosen.to_dict(),
            "target_fpr": self.target_fpr,
            "method": self.method,
            "n_pos": self.n_pos,
            "n_neg": self.n_neg,
            "n": self.n_pos + self.n_neg,
            "curve": [op.to_dict() for op in self.curve],
        }


@dataclass(frozen=True)
class HoldoutEvaluation:
    """Confusion/rates at an already-frozen threshold, holdout samples only.

    ``recall`` is included alongside ``tpr`` only because P16 criterion 2.7
    names both; for a binary screening gate they are the same quantity
    (recall of the positive/"bad" class), never computed independently.
    """

    tpr: float
    fpr: float
    precision: float
    tp: int
    fp: int
    tn: int
    fn: int
    n_pos: int
    n_neg: int

    def to_dict(self) -> dict:
        return {
            "tpr": round(self.tpr, 4),
            "fpr": round(self.fpr, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.tpr, 4),
            "tp": self.tp,
            "fp": self.fp,
            "tn": self.tn,
            "fn": self.fn,
            "n_pos": self.n_pos,
            "n_neg": self.n_neg,
            "n": self.n_pos + self.n_neg,
        }


@dataclass(frozen=True)
class HoldoutCalibrationResult:
    """Fit/holdout calibration outcome: frozen-tau selection plus one report.

    ``calibration`` is the full curve/selection on the ``"calibration"``-split
    samples (the existing ``CalibrationResult`` shape, unchanged). ``holdout``
    is the SEPARATE, single-shot evaluation of that frozen tau against
    ``"holdout"``-split samples only (P16 2.2: holdout never influences tau).
    """

    name: str
    calibration: CalibrationResult
    holdout: HoldoutEvaluation

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "calibration": self.calibration.to_dict(),
            "holdout": self.holdout.to_dict(),
        }


def _confusion(
    samples: list[tuple[float, bool]], threshold: float
) -> tuple[int, int, int, int]:
    """Count (tp, fp, tn, fn) for the rule: predict positive iff value < threshold.

    Positive = the bad outcome we want to catch by flagging.
    """
    tp = fp = tn = fn = 0
    for value, is_pos in samples:
        flagged = value < threshold
        if is_pos and flagged:
            tp += 1
        elif is_pos and not flagged:
            fn += 1
        elif not is_pos and flagged:
            fp += 1
        else:
            tn += 1
    return tp, fp, tn, fn


def _candidate_thresholds(values: list[float]) -> list[float]:
    """Every threshold that yields a distinct ``value < t`` partition.

    The observed values give all downward partitions (``t = v`` flags everything
    strictly below ``v``); one point above the max lets the gate flag the whole
    set. Sorted and de-duplicated for determinism.
    """
    uniq = sorted(set(values))
    if not uniq:
        return []
    return uniq + [uniq[-1] + 1.0]


def _point(samples: list[tuple[float, bool]], threshold: float) -> OperatingPoint:
    tp, fp, tn, fn = _confusion(samples, threshold)
    n_pos = tp + fn
    n_neg = fp + tn
    tpr = tp / n_pos if n_pos else 0.0
    fpr = fp / n_neg if n_neg else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    return OperatingPoint(
        threshold=threshold, tpr=tpr, fpr=fpr, precision=precision,
        tp=tp, fp=fp, tn=tn, fn=fn,
    )


def _validate_finite(samples: list[tuple[float, bool]]) -> None:
    bad = [v for v, _ in samples if not (isinstance(v, (int, float)) and math.isfinite(v))]
    if bad:
        raise ValueError(f"calibration samples must be finite; got non-finite value(s): {bad}")


def _class_counts(samples: list[tuple[float, bool]]) -> tuple[int, int]:
    n_pos = sum(1 for _, is_pos in samples if is_pos)
    n_neg = len(samples) - n_pos
    return n_pos, n_neg


def _require_class_present(
    samples: list[tuple[float, bool]],
    *,
    split_name: str,
    missing_pos_msg: str,
    missing_neg_msg: str,
) -> None:
    n_pos, n_neg = _class_counts(samples)
    n = n_pos + n_neg
    if n_pos == 0:
        raise InsufficientCalibrationDataError(
            f"{split_name} split has 0 positive (bad) examples out of {n}; {missing_pos_msg}"
        )
    if n_neg == 0:
        raise InsufficientCalibrationDataError(
            f"{split_name} split has 0 negative (good) examples out of {n}; {missing_neg_msg}"
        )


def _require_min_samples(samples: list[tuple[float, bool]], *, split_name: str) -> None:
    n_pos, n_neg = _class_counts(samples)
    if n_pos < MIN_SAMPLES_PER_CLASS_PER_SPLIT:
        raise InsufficientCalibrationDataError(
            f"{split_name} split has only {n_pos} positive (bad) example(s); need at "
            f"least {MIN_SAMPLES_PER_CLASS_PER_SPLIT} per class per split"
        )
    if n_neg < MIN_SAMPLES_PER_CLASS_PER_SPLIT:
        raise InsufficientCalibrationDataError(
            f"{split_name} split has only {n_neg} negative (good) example(s); need at "
            f"least {MIN_SAMPLES_PER_CLASS_PER_SPLIT} per class per split"
        )


def calibrate_threshold(
    samples: list[tuple[float, bool]],
    *,
    name: str,
    target_fpr: float = DEFAULT_TARGET_FPR_FAIL_EDGE,
) -> CalibrationResult:
    """Fit a lower-is-worse threshold edge from labeled ``(value, is_bad)`` samples.

    Selection: maximize TPR among thresholds with ``fpr <= target_fpr``; tie-break
    by higher precision, then by the HIGHER threshold (catch more, the screening
    bias). If no threshold meets the FPR ceiling, maximize Youden's J instead.

    No fit/holdout separation: this fits AND reports on the same ``samples``, so
    it is an internal building block only. ``calibrate_threshold_with_holdout``
    is the public, audit-compliant (P16 2.2) entry point.

    Raises ``ValueError`` if either class is empty (a discriminative threshold is
    undefined without both good and bad examples), if ``target_fpr`` is outside
    [0, 1], or if any sample value is non-finite (a NaN/inf coverage would make
    every ``value < threshold`` comparison silently False and corrupt the ROC).
    """
    if not (0.0 <= target_fpr <= 1.0):
        raise ValueError(f"target_fpr must be in [0, 1], got {target_fpr}")

    _validate_finite(samples)

    n_pos, n_neg = _class_counts(samples)
    if n_pos == 0 or n_neg == 0:
        raise ValueError(
            f"calibration needs both classes; got {n_pos} positive / {n_neg} negative"
        )

    values = [v for v, _ in samples]
    curve = [_point(samples, t) for t in _candidate_thresholds(values)]

    feasible = [op for op in curve if op.fpr <= target_fpr]
    if feasible:
        method = _METHOD_AT_FPR
        chosen = max(feasible, key=lambda op: (op.tpr, op.precision, op.threshold))
    else:
        method = _METHOD_YOUDEN
        chosen = max(curve, key=lambda op: (op.youden_j, op.precision, op.threshold))

    return CalibrationResult(
        name=name, chosen=chosen, target_fpr=target_fpr, method=method,
        n_pos=n_pos, n_neg=n_neg, curve=curve,
    )


def calibrate_threshold_with_holdout(
    samples: Sequence[tuple[float, bool, str]],
    *,
    name: str,
    target_fpr: float,
) -> HoldoutCalibrationResult:
    """Fit tau on ``"calibration"``-split samples; report once on ``"holdout"``.

    Each sample is ``(value, is_bad, split)`` with ``split`` a frozen
    ``"calibration"``/``"holdout"`` tag (typically the ``split`` field carried
    through from a labels file, see ``__main__._load_labeled_samples``).

    Implements P16 criterion 2.2 (fit/holdout separation): the threshold-
    selection sweep in ``calibrate_threshold`` runs ONLY on ``"calibration"``-
    split samples. The resulting tau is then FROZEN and used, unmodified, to
    compute TPR/FPR/precision on ``"holdout"``-split samples only. Holdout
    samples never enter the sweep, so they cannot move tau by construction
    (verified by ``test_calibrate.py``'s adversarial-holdout-point test).

    Raises ``InsufficientCalibrationDataError`` (a ``ValueError`` subclass) if:
      - any sample carries a ``split`` other than ``"calibration"``/``"holdout"``;
      - the calibration split is missing either class (can't fit a threshold);
      - the holdout split is missing either class (TPR or FPR undefined; never
        silently reported as 0.0 -- this must fail loudly);
      - either split has fewer than ``MIN_SAMPLES_PER_CLASS_PER_SPLIT`` examples
        of some class.
    """
    unknown = sorted({split for _, _, split in samples if split not in ("calibration", "holdout")})
    if unknown:
        raise InsufficientCalibrationDataError(
            f"samples carry unknown split value(s) {unknown}; expected "
            f"'calibration' or 'holdout'"
        )

    calibration_samples = [(v, is_bad) for v, is_bad, split in samples if split == "calibration"]
    holdout_samples = [(v, is_bad) for v, is_bad, split in samples if split == "holdout"]

    _require_class_present(
        calibration_samples, split_name="calibration",
        missing_pos_msg="cannot fit a threshold (no bad examples to catch)",
        missing_neg_msg="cannot fit a threshold (no good examples to avoid flagging)",
    )
    _require_class_present(
        holdout_samples, split_name="holdout",
        missing_pos_msg="cannot compute a defined TPR",
        missing_neg_msg="cannot compute a defined FPR",
    )
    _require_min_samples(calibration_samples, split_name="calibration")
    _require_min_samples(holdout_samples, split_name="holdout")

    _validate_finite(holdout_samples)

    calibration_result = calibrate_threshold(
        calibration_samples, name=name, target_fpr=target_fpr
    )
    threshold = calibration_result.chosen.threshold

    tp, fp, tn, fn = _confusion(holdout_samples, threshold)
    n_pos = tp + fn
    n_neg = fp + tn
    holdout = HoldoutEvaluation(
        tpr=tp / n_pos,
        fpr=fp / n_neg,
        precision=tp / (tp + fp) if (tp + fp) else 0.0,
        tp=tp, fp=fp, tn=tn, fn=fn, n_pos=n_pos, n_neg=n_neg,
    )
    return HoldoutCalibrationResult(name=name, calibration=calibration_result, holdout=holdout)


@dataclass(frozen=True)
class BootstrapBand:
    """95% percentile bootstrap band for holdout TPR/FPR at a frozen threshold."""

    tpr_lo: float
    tpr_hi: float
    fpr_lo: float
    fpr_hi: float
    n_resamples: int
    seed: int

    def to_dict(self) -> dict:
        return {
            "tpr_lo": round(self.tpr_lo, 4),
            "tpr_hi": round(self.tpr_hi, 4),
            "fpr_lo": round(self.fpr_lo, 4),
            "fpr_hi": round(self.fpr_hi, 4),
            "n_resamples": self.n_resamples,
            "seed": self.seed,
        }


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Nearest-rank percentile of an already-sorted list. No numpy/scipy needed
    for a scalar percentile of a bootstrap distribution we already generated
    deterministically ourselves."""
    if not sorted_values:
        return 0.0
    idx = round((pct / 100.0) * (len(sorted_values) - 1))
    idx = max(0, min(len(sorted_values) - 1, idx))
    return sorted_values[idx]


def bootstrap_holdout_band(
    holdout_samples: Sequence[tuple[float, bool]],
    *,
    threshold: float,
    n_resamples: int = 1000,
    seed: int,
) -> BootstrapBand:
    """Bootstrap CI on holdout TPR/FPR at an already-frozen ``threshold``.

    Resamples ``holdout_samples`` WITH replacement ``n_resamples`` times using a
    LOCAL ``random.Random(seed)`` instance (never global ``random`` state, per
    CLAUDE.md's determinism invariant), so the exact same
    ``(holdout_samples, threshold, seed)`` always produces byte-identical
    output. Each resample recomputes TPR/FPR at the frozen ``threshold`` (this
    NEVER refits tau; that would re-leak calibration/holdout separation into
    the uncertainty band). The 2.5th/97.5th percentiles of the resampled TPR
    and FPR distributions form the band.

    A single bootstrap draw can land all-one-class by chance; such a draw
    contributes 0.0 for the undefined rate (standard bootstrap practice), same
    as ``_point``. This differs from ``calibrate_threshold_with_holdout``,
    which hard-fails on a missing class in the ORIGINAL (non-resampled)
    holdout set: a single degenerate resample is expected noise, but a
    degenerate original set is a data problem.

    Raises ``InsufficientCalibrationDataError`` if ``holdout_samples`` itself
    (before resampling) is missing either class: a bootstrap band on an
    undefined base rate is meaningless.
    """
    samples = list(holdout_samples)
    _require_class_present(
        samples, split_name="holdout",
        missing_pos_msg="cannot bootstrap a TPR band",
        missing_neg_msg="cannot bootstrap an FPR band",
    )

    rng = random.Random(seed)
    n = len(samples)
    tprs: list[float] = []
    fprs: list[float] = []
    for _ in range(n_resamples):
        resample = [samples[rng.randrange(n)] for _ in range(n)]
        tp, fp, tn, fn = _confusion(resample, threshold)
        n_pos = tp + fn
        n_neg = fp + tn
        tprs.append(tp / n_pos if n_pos else 0.0)
        fprs.append(fp / n_neg if n_neg else 0.0)
    tprs.sort()
    fprs.sort()

    return BootstrapBand(
        tpr_lo=_percentile(tprs, _BOOTSTRAP_LOWER_PERCENTILE),
        tpr_hi=_percentile(tprs, _BOOTSTRAP_UPPER_PERCENTILE),
        fpr_lo=_percentile(fprs, _BOOTSTRAP_LOWER_PERCENTILE),
        fpr_hi=_percentile(fprs, _BOOTSTRAP_UPPER_PERCENTILE),
        n_resamples=n_resamples,
        seed=seed,
    )
