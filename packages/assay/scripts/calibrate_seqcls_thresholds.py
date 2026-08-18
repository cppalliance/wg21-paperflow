# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
"""Per-label threshold calibration from out-of-fold seqcls probabilities."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from eval_common import assay_package_root, repo_root

MIN_SUPPORT_FOR_CALIBRATION = 30
DEFAULT_THRESHOLD = 0.5


@dataclass
class SweepResult:
    threshold: float
    f1: float
    precision: float
    recall: float
    support: int
    calibrated: bool


def _load_oof(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def best_threshold_for_label(
    probs: list[float],
    golds: list[bool],
    *,
    min_support: int = MIN_SUPPORT_FOR_CALIBRATION,
    default_threshold: float = DEFAULT_THRESHOLD,
) -> SweepResult:
    support = sum(golds)
    if support < min_support:
        tp = sum(1 for p, g in zip(probs, golds, strict=True) if g and p >= default_threshold)
        fp = sum(1 for p, g in zip(probs, golds, strict=True) if not g and p >= default_threshold)
        fn = sum(1 for p, g in zip(probs, golds, strict=True) if g and p < default_threshold)
        precision, recall, f1 = _prf(tp, fp, fn)
        return SweepResult(default_threshold, f1, precision, recall, support, calibrated=False)

    candidates = sorted(set(probs) | {default_threshold})
    best = SweepResult(default_threshold, -1.0, 0.0, 0.0, support, calibrated=True)
    default_result: SweepResult | None = None
    for threshold in candidates:
        tp = sum(1 for p, g in zip(probs, golds, strict=True) if g and p >= threshold)
        fp = sum(1 for p, g in zip(probs, golds, strict=True) if not g and p >= threshold)
        fn = sum(1 for p, g in zip(probs, golds, strict=True) if g and p < threshold)
        precision, recall, f1 = _prf(tp, fp, fn)
        candidate = SweepResult(threshold, f1, precision, recall, support, calibrated=True)
        if threshold == default_threshold:
            default_result = candidate
        if f1 > best.f1:
            best = candidate

    assert default_result is not None
    if best.f1 <= default_result.f1:
        return SweepResult(
            default_threshold,
            default_result.f1,
            default_result.precision,
            default_result.recall,
            support,
            calibrated=False,
        )
    return best


def calibrate(oof_rows: list[dict[str, object]]) -> dict[str, SweepResult]:
    all_labels: set[str] = set()
    for row in oof_rows:
        all_labels.update(row["probs"].keys())  # type: ignore[union-attr]

    results: dict[str, SweepResult] = {}
    for label in sorted(all_labels):
        probs = [float(row["probs"][label]) for row in oof_rows]  # type: ignore[index]
        golds = [label in (row.get("labels") or []) for row in oof_rows]
        results[label] = best_threshold_for_label(probs, golds)
    return results


def main() -> int:
    default_oof = repo_root() / "data" / "routing_tagger" / "kfold" / "oof_probs.jsonl"
    default_out = assay_package_root() / "data" / "seqcls" / "per_label_thresholds.json"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oof", type=Path, default=default_oof)
    parser.add_argument("--out", type=Path, default=default_out)
    parser.add_argument("--min-support", type=int, default=MIN_SUPPORT_FOR_CALIBRATION)
    args = parser.parse_args()

    oof_rows = _load_oof(args.oof)
    results = calibrate(oof_rows)

    print(f"{'label':6s} {'support':>7s} {'thresh':>7s} {'f1':>6s} {'prec':>6s} {'rec':>6s}  calibrated")
    for label, row in sorted(results.items()):
        print(
            f"{label:6s} {row.support:7d} {row.threshold:7.3f} {row.f1:6.3f} "
            f"{row.precision:6.3f} {row.recall:6.3f}  {row.calibrated}",
        )

    thresholds = {label: row.threshold for label, row in results.items()}
    args.out.write_text(
        json.dumps(thresholds, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
