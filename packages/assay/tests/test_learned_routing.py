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
    aggregator_model_dir,
    is_learned_aggregator_path,
    learned_model_available,
    predict_learned_groups,
    routing_metadata_dir,
    _load_feature_names,
    _load_group_order,
    _load_group_thresholds,
    _load_model,
)
from assay.paper_routing.routing import route_paper
from assay.paper_routing.types import (
    ROUTING_GROUP_ORDER,
    RoutingGroup,
    SectionType,
    Sentence,
)
from pipeline.classifier_backends import (
    MultiLabelClassifierBackend,
    NliCrossEncoderBackend,
)


class _StubSeqcls(MultiLabelClassifierBackend):
    labels = ("D1",)

    def classify(self, texts, candidate_labels, *, multi_label=True):
        return []


class _StubNli(NliCrossEncoderBackend):
    def classify(self, texts, candidate_labels, *, multi_label=True):
        return []


@pytest.fixture(autouse=True)
def _clear_learned_aggregate_caches():
    """Prevent one test's monkeypatched dirs from leaking into another."""
    yield
    _load_feature_names.cache_clear()
    _load_group_order.cache_clear()
    _load_group_thresholds.cache_clear()
    _load_model.cache_clear()


def _sentence(text: str, hits: frozenset[str]) -> Sentence:
    return Sentence(
        text=text, section=SectionType.DESIGN, index=0, hypothesis_hits=hits
    )


def _write_metadata(data_dir: Path) -> None:
    (data_dir / "feature_names.json").write_text("[]\n", encoding="utf-8")
    (data_dir / "group_thresholds.json").write_text("{}\n", encoding="utf-8")
    (data_dir / "group_order.json").write_text(
        json.dumps([g.value for g in ROUTING_GROUP_ORDER], indent=2) + "\n",
        encoding="utf-8",
    )


def test_routing_group_order_matches_enum() -> None:
    assert ROUTING_GROUP_ORDER == tuple(RoutingGroup)


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


def test_is_learned_aggregator_path() -> None:
    assert is_learned_aggregator_path(_StubSeqcls(model="m"))
    assert is_learned_aggregator_path(_StubNli(model="m"))
    assert not is_learned_aggregator_path(
        [_StubSeqcls(model="m"), _StubNli(model="m")],
    )
    assert not is_learned_aggregator_path(None)


def test_route_paper_hgb_requires_regex(monkeypatch: pytest.MonkeyPatch) -> None:
    """HGB was trained on regex+classifier hits; skip it when regex is off."""
    sentences = [
        _sentence("We propose to add std::widget to the library.", frozenset({"D3"})),
    ]
    monkeypatch.setattr(
        "assay.paper_routing.routing.score_hypotheses",
        lambda *args, **kwargs: sentences,
    )
    monkeypatch.setattr(
        "assay.paper_routing.routing.learned_model_available",
        lambda classifiers: True,
    )
    called: list[bool] = []

    def _fake_predict(scored, *, audience=None, classifiers=None):
        del scored, audience, classifiers
        called.append(True)
        empty = {group: 0.0 for group in RoutingGroup}
        return {RoutingGroup.LEWG: 0.9}, {**empty, RoutingGroup.LEWG: 0.9}

    monkeypatch.setattr(
        "assay.paper_routing.routing.predict_learned_groups",
        _fake_predict,
    )
    classifier = _StubNli(model="m")
    md = "We propose to add std::widget to the library."

    route_paper(
        md,
        classifiers=classifier,
        use_regex=False,
        use_learned_aggregator=True,
    )
    assert called == []

    route_paper(
        md,
        classifiers=classifier,
        use_regex=True,
        use_learned_aggregator=True,
    )
    assert called == [True]


def test_bundled_learned_artifacts_available() -> None:
    assert learned_model_available(_StubSeqcls(model="m"))
    assert learned_model_available(_StubNli(model="m"))


def test_predict_learned_groups_raises_when_artifacts_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    meta_dir = tmp_path / "data" / "routing"
    meta_dir.mkdir(parents=True)
    _write_metadata(meta_dir)
    monkeypatch.setattr(
        "assay.paper_routing.learned_aggregate._assay_package_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "assay.paper_routing.learned_aggregate.routing_metadata_dir",
        lambda: meta_dir,
    )

    with pytest.raises(
        FileNotFoundError, match="learned routing aggregator artifacts missing"
    ):
        predict_learned_groups(
            [_sentence("proposal", frozenset({"D1"}))],
            classifiers=_StubSeqcls(model="m"),
        )


def test_learned_aggregate_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("sklearn")
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.multiclass import OneVsRestClassifier
    import joblib

    catalog = default_catalog_ids()
    feature_names = build_feature_names(catalog)
    sentences = [_sentence("proposal", frozenset({"D1"}))]
    classifier = _StubSeqcls(model="m")

    # One training row per group, distinguished by audience so the fitted
    # model actually associates a feature signal with each label instead of
    # mapping four identical inputs to four different outputs.
    group_audiences = {
        RoutingGroup.LEWG: ["LEWG"],
        RoutingGroup.LWG: ["LWG"],
        RoutingGroup.EWG: ["EWG"],
        RoutingGroup.CWG: ["CWG"],
    }
    x_rows = [
        vectorize_features(
            extract_paper_features(
                sentences, audience=group_audiences[group], catalog_ids=catalog
            ),
            feature_names,
        )
        for group in ROUTING_GROUP_ORDER
    ]
    y = [
        [1 if group is target else 0 for target in ROUTING_GROUP_ORDER]
        for group in ROUTING_GROUP_ORDER
    ]

    model = OneVsRestClassifier(
        HistGradientBoostingClassifier(random_state=0, max_depth=3, max_iter=50),
    )
    model.fit(x_rows, y)

    meta_dir = tmp_path / "data" / "routing"
    meta_dir.mkdir(parents=True)
    model_dir = tmp_path / "data" / "seqcls"
    model_dir.mkdir(parents=True)
    joblib.dump(model, model_dir / "aggregator_hgb.joblib")
    (meta_dir / "feature_names.json").write_text(
        json.dumps(list(feature_names)) + "\n",
        encoding="utf-8",
    )
    thresholds = {g.value: 0.1 for g in RoutingGroup}
    (meta_dir / "group_thresholds.json").write_text(
        json.dumps(thresholds, indent=2) + "\n",
        encoding="utf-8",
    )
    (meta_dir / "group_order.json").write_text(
        json.dumps([g.value for g in ROUTING_GROUP_ORDER], indent=2) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "assay.paper_routing.learned_aggregate.routing_metadata_dir",
        lambda: meta_dir,
    )
    monkeypatch.setattr(
        "assay.paper_routing.learned_aggregate._assay_package_root",
        lambda: tmp_path,
    )

    assert learned_model_available(classifier)
    assert routing_metadata_dir() == meta_dir
    assert aggregator_model_dir(classifier) == model_dir
    groups, probs = predict_learned_groups(
        sentences,
        audience=["LEWG"],
        classifiers=classifier,
    )
    assert RoutingGroup.LEWG in groups
    assert probs[RoutingGroup.LEWG] >= 0.1
    assert probs[RoutingGroup.LEWG] == max(probs.values())


def test_predict_learned_groups_raises_on_mismatched_group_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("sklearn")
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.multiclass import OneVsRestClassifier
    import joblib

    catalog = default_catalog_ids()
    feature_names = build_feature_names(catalog)
    sentences = [_sentence("proposal", frozenset({"D1"}))]
    classifier = _StubNli(model="m")
    x_rows = [
        vectorize_features(
            extract_paper_features(sentences, audience=["LEWG"], catalog_ids=catalog),
            feature_names,
        )
    ]
    y = [[1, 0, 0, 0]]
    model = OneVsRestClassifier(
        HistGradientBoostingClassifier(random_state=0, max_depth=3, max_iter=50),
    )
    model.fit(x_rows, y)

    meta_dir = tmp_path / "data" / "routing"
    meta_dir.mkdir(parents=True)
    model_dir = tmp_path / "data" / "nli"
    model_dir.mkdir(parents=True)
    joblib.dump(model, model_dir / "aggregator_hgb.joblib")
    (meta_dir / "feature_names.json").write_text(
        json.dumps(list(feature_names)) + "\n",
        encoding="utf-8",
    )
    (meta_dir / "group_thresholds.json").write_text(
        json.dumps({g.value: 0.1 for g in RoutingGroup}, indent=2) + "\n",
        encoding="utf-8",
    )
    (meta_dir / "group_order.json").write_text(
        json.dumps(["CWG", "LEWG", "LWG", "EWG"], indent=2) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "assay.paper_routing.learned_aggregate.routing_metadata_dir",
        lambda: meta_dir,
    )
    monkeypatch.setattr(
        "assay.paper_routing.learned_aggregate._assay_package_root",
        lambda: tmp_path,
    )

    with pytest.raises(ValueError, match="does not match ROUTING_GROUP_ORDER"):
        predict_learned_groups(
            sentences,
            audience=["LEWG"],
            classifiers=classifier,
        )
