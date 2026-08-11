#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

from __future__ import annotations

import json
from pathlib import Path

import pytest

from assay.paper_routing.features import (
    build_feature_names,
    default_catalog_ids,
    extract_paper_features,
    vectorize_features,
)
from assay.paper_routing.learned_aggregate import (
    is_learned_aggregator_path,
    is_seqcls_only_path,
    learned_model_available,
    predict_learned_groups,
    _load_feature_names,
    _load_group_thresholds,
    _load_model,
)
from assay.paper_routing.types import SectionType, Sentence
from pipeline.classifier_backends import MultiLabelClassifierBackend, NliCrossEncoderBackend


def _sentence(text: str, hits: frozenset[str]) -> Sentence:
    return Sentence(text=text, section=SectionType.DESIGN, index=0, hypothesis_hits=hits)


def test_feature_vector_length_stable() -> None:
    catalog = default_catalog_ids()
    names = build_feature_names(catalog)
    features = extract_paper_features(
        [_sentence("library design proposal", frozenset({"D1", "M1"}))],
        audience=["LEWG"],
        catalog_ids=catalog,
    )
    vector = vectorize_features(features, names)
    assert len(vector) == len(names)


def test_is_seqcls_only_path() -> None:
    class _Seqcls(MultiLabelClassifierBackend):
        labels = ("D1",)

        def classify(self, texts, candidate_labels, *, multi_label=True):
            return []

    class _Nli(NliCrossEncoderBackend):
        def classify(self, texts, candidate_labels, *, multi_label=True):
            return []

    assert is_seqcls_only_path(_Seqcls(model="m"), use_regex=False)
    assert not is_seqcls_only_path(_Seqcls(model="m"), use_regex=True)
    assert not is_seqcls_only_path([_Nli(model="m")], use_regex=False)
    assert not is_seqcls_only_path([_Seqcls(model="m"), _Nli(model="m")], use_regex=False)


def test_is_learned_aggregator_path() -> None:
    class _Seqcls(MultiLabelClassifierBackend):
        labels = ("D1",)

        def classify(self, texts, candidate_labels, *, multi_label=True):
            return []

    class _Nli(NliCrossEncoderBackend):
        def classify(self, texts, candidate_labels, *, multi_label=True):
            return []

    assert is_learned_aggregator_path(_Seqcls(model="m"), use_regex=False)
    assert is_learned_aggregator_path(_Nli(model="m"), use_regex=False)
    assert not is_learned_aggregator_path(_Seqcls(model="m"), use_regex=True)
    assert not is_learned_aggregator_path(
        [_Seqcls(model="m"), _Nli(model="m")],
        use_regex=False,
    )


def test_learned_aggregate_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("sklearn")
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.multiclass import OneVsRestClassifier
    import joblib

    from assay.paper_routing.types import RoutingGroup

    catalog = default_catalog_ids()
    feature_names = build_feature_names(catalog)
    sentences = [_sentence("proposal", frozenset({"D1"}))]
    features = extract_paper_features(sentences, audience=["LEWG"], catalog_ids=catalog)
    vector = vectorize_features(features, feature_names)

    model = OneVsRestClassifier(
        HistGradientBoostingClassifier(random_state=0, max_depth=3, max_iter=50),
    )
    y = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    x = [vector, vector, vector, vector]
    model.fit(x, y)

    data_dir = tmp_path / "routing"
    data_dir.mkdir()
    joblib.dump(model, data_dir / "aggregator_hgb.joblib")
    (data_dir / "feature_names.json").write_text(
        json.dumps(list(feature_names)) + "\n",
        encoding="utf-8",
    )
    thresholds = {g.value: 0.1 for g in RoutingGroup}
    (data_dir / "group_thresholds.json").write_text(
        json.dumps(thresholds, indent=2) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "assay.paper_routing.learned_aggregate.routing_data_dir",
        lambda: data_dir,
    )
    _load_feature_names.cache_clear()
    _load_group_thresholds.cache_clear()
    _load_model.cache_clear()

    assert learned_model_available()
    groups, probs = predict_learned_groups(sentences, audience=["LEWG"])
    assert RoutingGroup.LEWG in groups
    assert probs[RoutingGroup.LEWG] >= 0.1
