# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
"""Per-label NLI threshold calibration from out-of-fold entailment scores.

Reads JSONL rows ``{"probs": {hyp_id: float, ...}, "labels": [hyp_id, ...]}``.
Labels with fewer than ``--min-support`` gold positives keep 0.9, the routing
fallback. Writes ``packages/assay/{NLI_FAMILY_DIR / PER_LABEL_THRESHOLDS_FILE}``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from assay.paper_routing.artifact_names import NLI_FAMILY_DIR, PER_LABEL_THRESHOLDS_FILE
from calibrate_seqcls_thresholds import (
    MIN_SUPPORT_FOR_CALIBRATION,
    SweepResult,
    best_threshold_for_label,
)
from eval_common import assay_package_root, repo_root

DEFAULT_THRESHOLD = 0.9


def _load_oof(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def calibrate(
    oof_rows: list[dict[str, object]],
    *,
    min_support: int = MIN_SUPPORT_FOR_CALIBRATION,
    default_threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, SweepResult]:
    all_labels: set[str] = set()
    for row in oof_rows:
        all_labels.update(row["probs"].keys())  # type: ignore[union-attr]

    results: dict[str, SweepResult] = {}
    for label in sorted(all_labels):
        probs = [float(row["probs"][label]) for row in oof_rows]  # type: ignore[index]
        golds = [label in (row.get("labels") or []) for row in oof_rows]
        results[label] = best_threshold_for_label(
            probs,
            golds,
            min_support=min_support,
            default_threshold=default_threshold,
        )
    return results


def main() -> int:
    default_oof = repo_root() / "data" / "nli" / "kfold" / "oof_probs.jsonl"
    default_out = assay_package_root() / NLI_FAMILY_DIR / PER_LABEL_THRESHOLDS_FILE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oof", type=Path, default=default_oof)
    parser.add_argument("--out", type=Path, default=default_out)
    parser.add_argument("--min-support", type=int, default=MIN_SUPPORT_FOR_CALIBRATION)
    args = parser.parse_args()

    oof_rows = _load_oof(args.oof)
    results = calibrate(oof_rows, min_support=args.min_support)

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
