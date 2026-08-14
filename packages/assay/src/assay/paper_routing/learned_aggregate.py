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
from typing import Literal

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
from assay.paper_routing.types import ROUTING_GROUP_ORDER, RoutingGroup, Sentence

_ROUTING_METADATA_DIR = Path("data") / "routing"
_NLI_DATA_DIR = Path("data") / "nli"
_SEQCLS_DATA_DIR = Path("data") / "seqcls"
_MODEL_FILE = "aggregator_hgb.joblib"
_FEATURE_NAMES_FILE = "feature_names.json"
_GROUP_THRESHOLDS_FILE = "group_thresholds.json"
_GROUP_ORDER_FILE = "group_order.json"
_LEARNED_GROUP_THRESHOLD_FALLBACK: float = 0.5

AggregatorFamily = Literal["nli", "seqcls"]


def _assay_package_root() -> Path:
    here = Path(__file__).resolve()
    src_layout = here.parents[3]
    if (src_layout / "data").is_dir():
        return src_layout
    return here.parents[1]


def routing_metadata_dir() -> Path:
    """Shared routing metadata (feature names, group order)."""
    return _assay_package_root() / _ROUTING_METADATA_DIR


def routing_data_dir() -> Path:
    """Backward-compatible alias for :func:`routing_metadata_dir`."""
    return routing_metadata_dir()


def _family_data_dir(family: AggregatorFamily) -> Path:
    if family == "nli":
        return _assay_package_root() / _NLI_DATA_DIR
    return _assay_package_root() / _SEQCLS_DATA_DIR


def aggregator_model_dir(classifiers: object) -> Path:
    """Return ``data/nli`` or ``data/seqcls`` for the homogeneous classifier family."""
    return _family_data_dir(_aggregator_family(classifiers))


def _metadata_artifacts_present() -> bool:
    root = routing_metadata_dir()
    return (root / _FEATURE_NAMES_FILE).is_file() and (
        root / _GROUP_ORDER_FILE
    ).is_file()


def _family_artifacts_present(family: AggregatorFamily) -> bool:
    model_dir = _family_data_dir(family)
    return (model_dir / _MODEL_FILE).is_file() and (
        model_dir / _GROUP_THRESHOLDS_FILE
    ).is_file()


def learned_model_available(classifiers: object | None = None) -> bool:
    """True when shared metadata, family HGB model, and family thresholds are on disk."""
    if not _metadata_artifacts_present():
        return False
    if classifiers is None:
        return _family_artifacts_present("nli") or _family_artifacts_present("seqcls")
    if not is_learned_aggregator_path(classifiers):
        return False
    return _family_artifacts_present(_aggregator_family(classifiers))


@lru_cache(maxsize=1)
def _load_feature_names() -> tuple[str, ...]:
    path = routing_metadata_dir() / _FEATURE_NAMES_FILE
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        raise ValueError(f"{path}: expected JSON array of strings")
    return tuple(raw)


@lru_cache(maxsize=2)
def _load_group_thresholds(family: AggregatorFamily) -> dict[RoutingGroup, float]:
    path = _family_data_dir(family) / _GROUP_THRESHOLDS_FILE
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected JSON object")
    out: dict[RoutingGroup, float] = {}
    for key, value in raw.items():
        out[RoutingGroup(key)] = float(value)
    return out


@lru_cache(maxsize=1)
def _load_group_order() -> tuple[RoutingGroup, ...]:
    path = routing_metadata_dir() / _GROUP_ORDER_FILE
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        raise ValueError(f"{path}: expected JSON array of strings")
    order = tuple(RoutingGroup(x) for x in raw)
    if order != ROUTING_GROUP_ORDER:
        raise ValueError(
            f"{path}: group order {list(g.value for g in order)} does not match "
            f"ROUTING_GROUP_ORDER {list(g.value for g in ROUTING_GROUP_ORDER)}; "
            "retrain the aggregator or restore the matching group_order.json",
        )
    return order


@lru_cache(maxsize=2)
def _load_model(family: AggregatorFamily) -> object:
    path = _family_data_dir(family) / _MODEL_FILE
    return joblib.load(path)


def predict_learned_groups(
    sentences: list[Sentence],
    *,
    audience: list[str] | None = None,
    classifiers: object,
) -> tuple[dict[RoutingGroup, float], dict[RoutingGroup, float]]:
    """Return emitted groups and per-group probabilities."""
    if not learned_model_available(classifiers):
        raise FileNotFoundError(
            "learned routing aggregator artifacts missing: "
            f"metadata under {routing_metadata_dir()}, "
            f"model under {aggregator_model_dir(classifiers)}",
        )

    family = _aggregator_family(classifiers)
    feature_names = _load_feature_names()
    group_order = _load_group_order()
    catalog_ids = default_catalog_ids()
    features = extract_paper_features(
        sentences,
        audience=audience,
        catalog_ids=catalog_ids,
    )
    vector = vectorize_features(features, feature_names)
    model = _load_model(family)
    prob_row = model.predict_proba([vector])[0]  # type: ignore[union-attr]
    if len(prob_row) != len(group_order):
        raise ValueError(
            f"learned aggregator predict_proba length {len(prob_row)} "
            f"does not match group_order ({len(group_order)})",
        )
    thresholds = _load_group_thresholds(family)

    probs: dict[RoutingGroup, float] = {}
    for idx, group in enumerate(group_order):
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


def _aggregator_family(classifiers: object) -> AggregatorFamily:
    backends = _classifier_backends(classifiers)
    if not backends:
        raise ValueError("classifiers required for learned aggregation")
    if all(isinstance(b, NliCrossEncoderBackend) for b in backends):
        return "nli"
    if all(isinstance(b, MultiLabelClassifierBackend) for b in backends):
        return "seqcls"
    raise ValueError(
        "learned aggregation requires a homogeneous NLI-only or seqcls-only "
        f"classifier set, got {[type(b).__name__ for b in backends]}",
    )


def is_learned_aggregator_path(
    classifiers: object,
) -> bool:
    """True when routing should use the learned aggregator instead of hand rules.

    Eligible: homogeneous single-family backends (NLI-only or seqcls-only).
    Mixed NLI+seqcls ensembles keep the hand aggregate. Frozen HGB models
    were trained on regex+classifier hits; ``route_paper`` also requires
    ``use_regex=True`` before applying this path.
    """
    if classifiers is None:
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
