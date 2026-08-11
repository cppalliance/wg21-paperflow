#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Frozen HistGradientBoosting paper-level routing head (single-classifier path)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path

import joblib  # type: ignore[import-untyped]

from pipeline.classifier_backends import (
    ClassifierBackend,
    MultiLabelClassifierBackend,
    NliCrossEncoderBackend,
)

from assay.paper_routing.features import (
    default_catalog_ids,
    extract_paper_features,
    vectorize_features,
)
from assay.paper_routing.types import RoutingGroup, Sentence

_ROUTING_DATA_DIR = Path("data") / "routing"
_MODEL_FILE = "aggregator_hgb.joblib"
_FEATURE_NAMES_FILE = "feature_names.json"
_GROUP_THRESHOLDS_FILE = "group_thresholds.json"
_GROUP_ORDER: tuple[RoutingGroup, ...] = tuple(RoutingGroup)
_LEARNED_GROUP_THRESHOLD_FALLBACK: float = 0.5


def _assay_package_root() -> Path:
    return Path(__file__).resolve().parents[3]


def routing_data_dir() -> Path:
    return _assay_package_root() / _ROUTING_DATA_DIR


def learned_model_available() -> bool:
    root = routing_data_dir()
    return (
        (root / _MODEL_FILE).is_file()
        and (root / _FEATURE_NAMES_FILE).is_file()
        and (root / _GROUP_THRESHOLDS_FILE).is_file()
    )


@lru_cache(maxsize=1)
def _load_feature_names() -> tuple[str, ...]:
    path = routing_data_dir() / _FEATURE_NAMES_FILE
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        raise ValueError(f"{path}: expected JSON array of strings")
    return tuple(raw)


@lru_cache(maxsize=1)
def _load_group_thresholds() -> dict[RoutingGroup, float]:
    path = routing_data_dir() / _GROUP_THRESHOLDS_FILE
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected JSON object")
    out: dict[RoutingGroup, float] = {}
    for key, value in raw.items():
        out[RoutingGroup(key)] = float(value)
    return out


@lru_cache(maxsize=1)
def _load_model() -> object:
    path = routing_data_dir() / _MODEL_FILE
    return joblib.load(path)


def predict_learned_groups(
    sentences: list[Sentence],
    *,
    audience: list[str] | None = None,
) -> tuple[dict[RoutingGroup, float], dict[RoutingGroup, float]]:
    """Return emitted groups and per-group probabilities."""
    if not learned_model_available():
        raise FileNotFoundError(
            f"learned routing aggregator artifacts missing under {routing_data_dir()}",
        )

    feature_names = _load_feature_names()
    catalog_ids = default_catalog_ids()
    features = extract_paper_features(
        sentences,
        audience=audience,
        catalog_ids=catalog_ids,
    )
    vector = vectorize_features(features, feature_names)
    model = _load_model()
    prob_row = model.predict_proba([vector])[0]  # type: ignore[union-attr]
    thresholds = _load_group_thresholds()

    probs: dict[RoutingGroup, float] = {}
    for idx, group in enumerate(_GROUP_ORDER):
        probs[group] = float(prob_row[idx])

    groups: dict[RoutingGroup, float] = {
        group: score
        for group, score in probs.items()
        if score >= thresholds.get(group, _LEARNED_GROUP_THRESHOLD_FALLBACK)
    }
    return groups, probs


def _classifier_backends(classifiers: object) -> list[object]:
    if isinstance(classifiers, ClassifierBackend):
        return [classifiers]
    if isinstance(classifiers, Mapping):
        return list(dict.fromkeys(classifiers.values()))
    if isinstance(classifiers, Sequence) and not isinstance(classifiers, (str, bytes)):
        return list(classifiers)
    return []


def is_learned_aggregator_path(
    classifiers: object,
    *,
    use_regex: bool,
) -> bool:
    """True when routing should use the learned aggregator instead of hand rules.

    Eligible: regex off, homogeneous single-family backends (NLI-only or seqcls-only).
    Mixed NLI+seqcls ensembles and regex paths keep the hand aggregate.
    """
    if use_regex or classifiers is None:
        return False

    backends = _classifier_backends(classifiers)
    if not backends:
        return False
    has_nli = any(isinstance(b, NliCrossEncoderBackend) for b in backends)
    has_seqcls = any(isinstance(b, MultiLabelClassifierBackend) for b in backends)
    if has_nli and has_seqcls:
        return False
    if has_nli:
        return all(isinstance(b, NliCrossEncoderBackend) for b in backends)
    if has_seqcls:
        return all(isinstance(b, MultiLabelClassifierBackend) for b in backends)
    return False


def is_seqcls_only_path(
    classifiers: object,
    *,
    use_regex: bool,
) -> bool:
    """True when classifiers are seqcls-only (no regex, no NLI)."""
    if use_regex or classifiers is None:
        return False

    backends = _classifier_backends(classifiers)
    if not backends:
        return False
    if any(not isinstance(b, MultiLabelClassifierBackend) for b in backends):
        return False
    return True
