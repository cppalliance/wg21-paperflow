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

This module returns data only. The CLI writes a ``thresholds.json`` artifact; a
human promotes the values into ``constants.py`` (thresholds are deliberate, see
the architecture-protection rule), exactly the audit the constants docstring
promises.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = [
    "CalibrationResult",
    "OperatingPoint",
    "calibrate_threshold",
]

# Selection default: the largest false-positive rate tolerated while maximizing
# recall of bad conversions. 0.05 = at most 1 in 20 good papers wrongly flagged,
# the conventional screening-gate operating ceiling.
DEFAULT_TARGET_FPR = 0.05

_METHOD_AT_FPR = "max_tpr_at_fpr"
_METHOD_YOUDEN = "youden_j"


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


def calibrate_threshold(
    samples: list[tuple[float, bool]],
    *,
    name: str,
    target_fpr: float = DEFAULT_TARGET_FPR,
) -> CalibrationResult:
    """Fit a lower-is-worse threshold edge from labeled ``(value, is_bad)`` samples.

    Selection: maximize TPR among thresholds with ``fpr <= target_fpr``; tie-break
    by higher precision, then by the HIGHER threshold (catch more, the screening
    bias). If no threshold meets the FPR ceiling, maximize Youden's J instead.

    Raises ``ValueError`` if either class is empty (a discriminative threshold is
    undefined without both good and bad examples), if ``target_fpr`` is outside
    [0, 1], or if any sample value is non-finite (a NaN/inf coverage would make
    every ``value < threshold`` comparison silently False and corrupt the ROC).
    """
    if not (0.0 <= target_fpr <= 1.0):
        raise ValueError(f"target_fpr must be in [0, 1], got {target_fpr}")

    bad = [v for v, _ in samples if not (isinstance(v, (int, float)) and math.isfinite(v))]
    if bad:
        raise ValueError(f"calibration samples must be finite; got non-finite value(s): {bad}")

    n_pos = sum(1 for _, is_pos in samples if is_pos)
    n_neg = len(samples) - n_pos
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
