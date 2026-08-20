# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
"""Train and freeze the paper-level HistGradientBoosting aggregator.

Features come from regex catalog hits unioned with the chosen classifier
(nli-small by default). Inference must keep regex on; HGB was trained on
regex+classifier hypothesis densities.

Retraining writes ``provenance.json`` next to each family joblib so load
time can fail closed on sampling, threshold, or sklearn skew.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import TypedDict

import joblib  # type: ignore[import-untyped]
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import KFold
from sklearn.multiclass import OneVsRestClassifier

from assay.paper_routing.features import (
    build_feature_names,
    default_catalog_ids,
    extract_paper_features,
    vectorize_features,
)
from assay.paper_routing.hypotheses import score_hypotheses
from assay.paper_routing.provenance import build_provenance_record
from assay.paper_routing.types import ROUTING_GROUP_ORDER, RoutingGroup
from eval_common import (
    assay_package_root,
    default_paperstore_dir,
    expected_groups,
    parse_audience_from_md,
    paper_golden_train_path,
    resolve_classifier,
)

logger = logging.getLogger(__name__)

_TRAIN_SEED = 0
_CV_FOLDS = 5
_HGB_MAX_DEPTH = 4
_HGB_MAX_ITER = 200


def _make_aggregator() -> OneVsRestClassifier:
    """Unfitted OvR-HGB with the pinned training hyperparameters.

    CV folds and the final freeze each need a new instance; sklearn
    estimators are mutated by ``fit``.
    """
    return OneVsRestClassifier(
        HistGradientBoostingClassifier(
            random_state=_TRAIN_SEED,
            max_depth=_HGB_MAX_DEPTH,
            max_iter=_HGB_MAX_ITER,
        ),
    )


class TrainingRow(TypedDict):
    paper_id: str
    features: dict[str, float]
    labels: list[int]
    sentence_count: int


def _load_golden(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def _labels_vector(groups: set[RoutingGroup]) -> list[int]:
    return [1 if group in groups else 0 for group in ROUTING_GROUP_ORDER]


def _exact_match_rate(
    y_true: list[list[int]],
    y_pred: list[list[int]],
) -> float:
    if not y_true:
        return 0.0
    matches = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == p)
    return matches / len(y_true)


def _sweep_group_thresholds(
    y_true: list[list[int]],
    prob_rows: list[list[float]],
) -> dict[RoutingGroup, float]:
    thresholds: dict[RoutingGroup, float] = {}
    candidates = [i / 20 for i in range(1, 20)]
    for group_idx, group in enumerate(ROUTING_GROUP_ORDER):
        y_col = [row[group_idx] for row in y_true]
        probs = [row[group_idx] for row in prob_rows]
        best_t = 0.5
        best_f1 = -1.0
        for threshold in candidates:
            tp = sum(
                1 for p, y in zip(probs, y_col, strict=True) if y and p >= threshold
            )
            fp = sum(
                1 for p, y in zip(probs, y_col, strict=True) if not y and p >= threshold
            )
            fn = sum(
                1 for p, y in zip(probs, y_col, strict=True) if y and p < threshold
            )
            precision = tp / (tp + fp) if (tp + fp) else 0.0
            recall = tp / (tp + fn) if (tp + fn) else 0.0
            f1 = (
                2 * precision * recall / (precision + recall)
                if (precision + recall)
                else 0.0
            )
            if f1 > best_f1:
                best_f1 = f1
                best_t = threshold
        thresholds[group] = best_t
    return thresholds


def _apply_thresholds(
    prob_rows: list[list[float]],
    thresholds: dict[RoutingGroup, float],
) -> list[list[int]]:
    out: list[list[int]] = []
    for row in prob_rows:
        bits = [
            1 if row[idx] >= thresholds[group] else 0
            for idx, group in enumerate(ROUTING_GROUP_ORDER)
        ]
        out.append(bits)
    return out


def build_training_rows(
    *,
    paperstore_dir: Path,
    golden_path: Path,
    classifier_name: str,
    cache_path: Path | None,
) -> list[TrainingRow]:
    if cache_path is not None and cache_path.is_file():
        rows: list[TrainingRow] = []
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
        return rows

    classifier = resolve_classifier(classifier_name)
    golden_rows = _load_golden(golden_path)
    built: list[TrainingRow] = []
    for row in golden_rows:
        paper_id = str(row["paper_id"]).lower()
        md_path = paperstore_dir / f"{paper_id}.md"
        if not md_path.is_file():
            continue
        md = md_path.read_text(encoding="utf-8")
        audience = parse_audience_from_md(md)
        sentences = score_hypotheses(
            md,
            audience=audience,
            classifiers=classifier,
            use_regex=True,
        )
        categories = list(row.get("categories") or [])
        expected = expected_groups([str(c) for c in categories])
        features = extract_paper_features(sentences, audience=audience)
        built.append(
            {
                "paper_id": str(row["paper_id"]),
                "features": features,
                "labels": _labels_vector(expected),
                "sentence_count": len(sentences),
            },
        )
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("w", encoding="utf-8") as fh:
            for item in built:
                fh.write(json.dumps(item, sort_keys=True) + "\n")
    return built


def train_and_freeze(
    rows: list[TrainingRow],
    *,
    model_output_dir: Path,
    metadata_dir: Path,
) -> dict[str, object]:
    catalog_ids: tuple[str, ...] = default_catalog_ids()
    feature_names: tuple[str, ...] = build_feature_names(catalog_ids)
    x_rows = [vectorize_features(row["features"], feature_names) for row in rows]
    y_rows = [list(row["labels"]) for row in rows]

    kfold = KFold(n_splits=_CV_FOLDS, shuffle=True, random_state=_TRAIN_SEED)
    oof_probs: list[list[float]] = [[] for _ in range(len(x_rows))]
    for train_idx, test_idx in kfold.split(x_rows):
        x_train = [x_rows[i] for i in train_idx]
        y_train = [y_rows[i] for i in train_idx]
        fold_model = _make_aggregator()
        fold_model.fit(x_train, y_train)
        fold_probs = fold_model.predict_proba([x_rows[i] for i in test_idx])
        for local_idx, global_idx in enumerate(test_idx):
            oof_probs[global_idx] = [
                float(fold_probs[local_idx][j]) for j in range(len(ROUTING_GROUP_ORDER))
            ]

    thresholds = _sweep_group_thresholds(y_rows, oof_probs)
    oof_preds = _apply_thresholds(oof_probs, thresholds)
    oof_exact = _exact_match_rate(y_rows, oof_preds)

    final_model = _make_aggregator()
    final_model.fit(x_rows, y_rows)
    in_probs = final_model.predict_proba(x_rows)
    in_prob_rows = [
        [float(in_probs[row_idx][j]) for j in range(len(ROUTING_GROUP_ORDER))]
        for row_idx in range(len(x_rows))
    ]
    in_preds = _apply_thresholds(in_prob_rows, thresholds)
    in_exact = _exact_match_rate(y_rows, in_preds)

    model_output_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(final_model, model_output_dir / "aggregator_hgb.joblib")
    (metadata_dir / "feature_names.json").write_text(
        json.dumps(list(feature_names), indent=2) + "\n",
        encoding="utf-8",
    )
    (model_output_dir / "group_thresholds.json").write_text(
        json.dumps(
            {group.value: thresholds[group] for group in ROUTING_GROUP_ORDER},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (metadata_dir / "group_order.json").write_text(
        json.dumps([group.value for group in ROUTING_GROUP_ORDER], indent=2) + "\n",
        encoding="utf-8",
    )
    (metadata_dir / "train_report.json").write_text(
        json.dumps(
            {
                "n_papers": len(rows),
                "oof_exact_match": oof_exact,
                "in_sample_exact_match": in_exact,
                "group_thresholds": {
                    g.value: thresholds[g] for g in ROUTING_GROUP_ORDER
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    per_label_thresholds_path = model_output_dir / "per_label_thresholds.json"
    feature_names_path = metadata_dir / "feature_names.json"
    provenance = build_provenance_record(
        per_label_thresholds_path=per_label_thresholds_path,
        feature_names_path=feature_names_path,
    )
    (model_output_dir / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "oof_exact_match": oof_exact,
        "in_sample_exact_match": in_exact,
        "n_papers": len(rows),
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paperstore", type=Path, default=None)
    parser.add_argument("--golden", type=Path, default=paper_golden_train_path())
    parser.add_argument(
        "--model-output",
        type=Path,
        default=assay_package_root() / "data" / "nli",
        help="Directory for aggregator_hgb.joblib, group_thresholds.json, and provenance.json",
    )
    parser.add_argument(
        "--metadata-dir",
        type=Path,
        default=assay_package_root() / "data" / "routing",
        help="Directory for feature_names.json and group_order.json",
    )
    parser.add_argument("--classifier", default="nli-small")
    parser.add_argument(
        "--cache",
        type=Path,
        default=None,
        help="Optional JSONL cache of extracted features (read or write).",
    )
    args = parser.parse_args()
    paperstore = args.paperstore or default_paperstore_dir()
    rows = build_training_rows(
        paperstore_dir=paperstore,
        golden_path=args.golden,
        classifier_name=args.classifier,
        cache_path=args.cache,
    )
    if not rows:
        raise SystemExit("no training rows with markdown in paperstore")
    summary = train_and_freeze(
        rows,
        model_output_dir=args.model_output,
        metadata_dir=args.metadata_dir,
    )
    logger.info("trained aggregator: %s", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
