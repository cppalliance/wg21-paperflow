#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for ``pipeline.classifier_backends``.

Uses a fake backend implementing the ``ClassifierBackend`` ABC plus
monkey-patched ``transformers`` / ``sentence_transformers`` stubs to
exercise ``ZeroShotV2Backend`` and ``NliCrossEncoderBackend`` without
touching the network or HF cache.
"""

from __future__ import annotations

import sys
import types

import pytest

from conftest import SeqClsStubModel, install_seqcls_transformers_stub
from pipeline.classifier_backends import (
    CLASSIFIER_BACKEND_REGISTRY,
    ClassifierBackend,
    MultiLabelClassifierBackend,
    NliCrossEncoderBackend,
    ZeroShotV2Backend,
)


# ---------------------------------------------------------------------------
# ABC contract
# ---------------------------------------------------------------------------


def test_abc_cannot_instantiate():
    with pytest.raises(TypeError):
        ClassifierBackend()  # type: ignore[abstract]


class _FakeBackend(ClassifierBackend):
    def __init__(self, scores: dict[str, float]) -> None:
        self.model_id = "fake"
        self.device = "cpu"
        self._scores = scores
        self.last_call: dict | None = None

    def classify(self, texts, candidate_labels, *, multi_label=True):
        self.last_call = {
            "texts": list(texts),
            "labels": list(candidate_labels),
            "multi_label": multi_label,
        }
        return [
            {label: float(self._scores.get(label, 0.0)) for label in candidate_labels}
            for _ in texts
        ]


def test_fake_backend_implements_contract():
    fb = _FakeBackend({"a": 0.7, "b": 0.2})
    result = fb.classify(["x", "y"], ["a", "b"])
    assert result == [{"a": 0.7, "b": 0.2}, {"a": 0.7, "b": 0.2}]
    assert fb.last_call == {
        "texts": ["x", "y"],
        "labels": ["a", "b"],
        "multi_label": True,
    }


def test_fake_backend_records_multi_label_flag():
    fb = _FakeBackend({"a": 1.0, "b": 0.0})
    fb.classify(["x"], ["a", "b"], multi_label=False)
    assert fb.last_call is not None and fb.last_call["multi_label"] is False


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_contains_known_backends():
    assert "zeroshot_v2" in CLASSIFIER_BACKEND_REGISTRY
    assert "nli_cross_encoder" in CLASSIFIER_BACKEND_REGISTRY
    assert "multilabel_seqcls" in CLASSIFIER_BACKEND_REGISTRY
    assert CLASSIFIER_BACKEND_REGISTRY["zeroshot_v2"] is ZeroShotV2Backend
    assert CLASSIFIER_BACKEND_REGISTRY["nli_cross_encoder"] is NliCrossEncoderBackend
    assert (
        CLASSIFIER_BACKEND_REGISTRY["multilabel_seqcls"] is MultiLabelClassifierBackend
    )


# ---------------------------------------------------------------------------
# ZeroShotV2Backend
# ---------------------------------------------------------------------------


class _StubHFPipeline:
    """Mimics the callable returned by ``transformers.pipeline``.

    Accepts ``batch_size`` for parity with the real HF pipeline call
    site introduced by :mod:`pipeline.transformer_backend`. Materializes
    ``texts`` once so generator inputs (used to defeat the HF
    is_last-flush batching trap) are handled correctly.
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, texts, *, candidate_labels, multi_label, batch_size=None):
        materialized = list(texts)
        self.calls.append(
            {
                "texts": materialized,
                "labels": list(candidate_labels),
                "multi_label": multi_label,
                "batch_size": batch_size,
            }
        )
        out = []
        for _ in materialized:
            # Return labels in reversed order to verify reconstruction.
            sorted_labels = list(reversed(candidate_labels))
            scores = [0.9 - 0.3 * i for i in range(len(sorted_labels))]
            out.append(
                {
                    "sequence": "...",
                    "labels": sorted_labels,
                    "scores": scores,
                }
            )
        return out if len(materialized) > 1 else out[0]


def _install_stub_transformers(monkeypatch, stub: _StubHFPipeline) -> None:
    fake_mod = types.ModuleType("transformers")

    def fake_pipeline(task, *, model, device, **_kw):
        assert task == "zero-shot-classification"
        return stub

    fake_mod.pipeline = fake_pipeline
    monkeypatch.setitem(sys.modules, "transformers", fake_mod)


def test_zeroshot_v2_passes_labels_through_and_dicts_results(monkeypatch):
    stub = _StubHFPipeline()
    _install_stub_transformers(monkeypatch, stub)

    backend = ZeroShotV2Backend(model="fake/model", device="cpu")
    result = backend.classify(["a", "b"], ["target", "skip"])

    assert len(stub.calls) == 1
    call = stub.calls[0]
    assert call["texts"] == ["a", "b"]
    assert call["labels"] == ["target", "skip"]
    assert call["multi_label"] is True
    # TransformerBackend always forwards a batch_size from the active
    # provider so the HF pipeline batches across sequence boundaries
    # (huggingface/transformers#24005).
    assert call["batch_size"] is not None and call["batch_size"] > 0
    assert len(result) == 2
    for r in result:
        assert set(r.keys()) == {"target", "skip"}
        assert all(isinstance(v, float) for v in r.values())


def test_zeroshot_v2_empty_input_short_circuits(monkeypatch):
    stub = _StubHFPipeline()
    _install_stub_transformers(monkeypatch, stub)
    backend = ZeroShotV2Backend(model="fake/model")
    assert backend.classify([], ["target", "skip"]) == []
    assert stub.calls == []


def test_zeroshot_v2_single_input_handled(monkeypatch):
    stub = _StubHFPipeline()
    _install_stub_transformers(monkeypatch, stub)
    backend = ZeroShotV2Backend(model="fake/model")
    result = backend.classify(["only one"], ["target", "skip"])
    assert len(result) == 1
    assert set(result[0].keys()) == {"target", "skip"}


def test_zeroshot_v2_caches_pipeline(monkeypatch):
    """Verify the pipeline is loaded once per instance, not per call."""
    load_count = {"n": 0}
    stub = _StubHFPipeline()

    fake_mod = types.ModuleType("transformers")

    def fake_pipeline(task, *, model, device, **_kw):
        load_count["n"] += 1
        return stub

    fake_mod.pipeline = fake_pipeline
    monkeypatch.setitem(sys.modules, "transformers", fake_mod)

    backend = ZeroShotV2Backend(model="fake/model")
    backend.classify(["a"], ["target", "skip"])
    backend.classify(["b"], ["target", "skip"])
    backend.classify(["c"], ["target", "skip"])
    assert load_count["n"] == 1


def test_zeroshot_v2_propagates_multi_label_flag(monkeypatch):
    stub = _StubHFPipeline()
    _install_stub_transformers(monkeypatch, stub)
    backend = ZeroShotV2Backend(model="fake/model")
    backend.classify(["x"], ["target", "skip"], multi_label=False)
    assert stub.calls[-1]["multi_label"] is False


# ---------------------------------------------------------------------------
# NliCrossEncoderBackend
# ---------------------------------------------------------------------------


class _StubCrossEncoder:
    def __init__(self, model_id, device=None, local_files_only=False, **_kw):
        self.model_id = model_id
        self.device = device
        self.calls: list[list[tuple[str, str]]] = []
        # Map hypothesis suffix -> (entail_logit, contra_logit) so tests
        # can construct deterministic per-label outcomes.
        self.scores_by_hypothesis: dict[str, tuple[float, float]] = {}

    def predict(
        self,
        pairs,
        *,
        apply_softmax=False,
        show_progress_bar=False,
        batch_size=None,
        **_kw,
    ):
        self.calls.append(list(pairs))
        out = []
        for _premise, hypothesis in pairs:
            entail, contra = self.scores_by_hypothesis.get(hypothesis, (0.0, 0.0))
            # Index 0 = contradiction, 1 = entailment, 2 = neutral.
            row = [contra, entail, 0.0]
            if apply_softmax:
                import math

                m = max(row)
                exps = [math.exp(v - m) for v in row]
                z = sum(exps)
                row = [v / z for v in exps]
            out.append(row)
        return out


def _install_stub_st(monkeypatch, stub: _StubCrossEncoder) -> None:
    fake_mod = types.ModuleType("sentence_transformers")

    def factory(model, device=None, local_files_only=False, model_kwargs=None, **_kw):
        # The backend's _load tries local_files_only=True first; in our
        # stub that succeeds, so the fallback branch never runs.
        stub.model_id = model
        stub.device = device
        return stub

    fake_mod.CrossEncoder = factory
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_mod)


def test_nli_cross_encoder_multi_label(monkeypatch):
    stub = _StubCrossEncoder("fake")
    stub.scores_by_hypothesis = {
        # Hypothesis 'This text is target' strongly entailed for both texts.
        "This text is target": (3.0, -1.0),
        # Hypothesis 'This text is skip' strongly contradicted.
        "This text is skip": (-2.0, 2.0),
    }
    _install_stub_st(monkeypatch, stub)
    backend = NliCrossEncoderBackend(model="fake/nli")
    result = backend.classify(["foo", "bar"], ["target", "skip"], multi_label=True)

    assert len(result) == 2
    for r in result:
        assert r["target"] > 0.9  # entailed
        assert r["skip"] < 0.1  # contradicted


def test_nli_cross_encoder_pair_construction(monkeypatch):
    stub = _StubCrossEncoder("fake")
    _install_stub_st(monkeypatch, stub)
    backend = NliCrossEncoderBackend(model="fake/nli")
    backend.classify(["alpha", "beta"], ["target", "skip"])

    # One predict() call with N_texts * N_labels pairs.
    assert len(stub.calls) == 1
    pairs = stub.calls[0]
    assert pairs == [
        ("alpha", "This text is target"),
        ("alpha", "This text is skip"),
        ("beta", "This text is target"),
        ("beta", "This text is skip"),
    ]


def test_nli_cross_encoder_single_label_softmax(monkeypatch):
    stub = _StubCrossEncoder("fake")
    stub.scores_by_hypothesis = {
        "This text is target": (3.0, -1.0),
        "This text is skip": (1.0, 0.0),
    }
    _install_stub_st(monkeypatch, stub)
    backend = NliCrossEncoderBackend(model="fake/nli")
    result = backend.classify(["foo"], ["target", "skip"], multi_label=False)
    # Cross-label softmax, not independent per-label sigmoids.
    assert result[0]["target"] == pytest.approx(0.5624, abs=1e-3)
    assert result[0]["skip"] == pytest.approx(0.4376, abs=1e-3)
    total = sum(result[0].values())
    assert total == pytest.approx(1.0, abs=1e-6)
    assert result[0]["target"] > result[0]["skip"]


def test_nli_cross_encoder_empty_input(monkeypatch):
    stub = _StubCrossEncoder("fake")
    _install_stub_st(monkeypatch, stub)
    backend = NliCrossEncoderBackend(model="fake/nli")
    assert backend.classify([], ["target", "skip"]) == []
    assert stub.calls == []


def test_multilabel_seqcls_projects_scores(monkeypatch):
    stub_model = SeqClsStubModel(
        id2label={0: "alpha", 1: "beta"},
        logits=[0.0, 2.0],
    )
    install_seqcls_transformers_stub(monkeypatch, stub_model)
    backend = MultiLabelClassifierBackend(model="fake/seqcls")
    result = backend.classify(["one", "two"], ["alpha", "beta"])

    assert len(result) == 2
    for row in result:
        assert set(row.keys()) == {"alpha", "beta"}
        assert row["alpha"] == pytest.approx(0.5, abs=0.01)
        assert row["beta"] == pytest.approx(0.880797, abs=0.001)


def test_multilabel_seqcls_unknown_label_raises(monkeypatch):
    stub_model = SeqClsStubModel(
        id2label={0: "alpha", 1: "beta"},
        logits=[0.0, 2.0],
    )
    install_seqcls_transformers_stub(monkeypatch, stub_model)
    backend = MultiLabelClassifierBackend(model="fake/seqcls")
    with pytest.raises(ValueError, match="Unknown candidate_labels"):
        backend.classify(["x"], ["alpha", "missing"])


def test_multilabel_seqcls_empty_input_short_circuits(monkeypatch):
    stub_model = SeqClsStubModel(
        id2label={0: "alpha", 1: "beta"},
        logits=[0.0, 2.0],
    )
    install_seqcls_transformers_stub(monkeypatch, stub_model)
    backend = MultiLabelClassifierBackend(model="fake/seqcls")
    assert backend.classify([], ["alpha", "beta"]) == []
    assert stub_model.load_count == 0


def test_multilabel_seqcls_single_label_sum_normalized(monkeypatch):
    stub_model = SeqClsStubModel(
        id2label={0: "alpha", 1: "beta"},
        logits=[0.0, 2.0],
    )
    install_seqcls_transformers_stub(monkeypatch, stub_model)
    backend = MultiLabelClassifierBackend(model="fake/seqcls")
    result = backend.classify(["x"], ["alpha", "beta"], multi_label=False)
    total = sum(result[0].values())
    assert total == pytest.approx(1.0, abs=1e-6)
    assert result[0]["beta"] > result[0]["alpha"]
    # Sigmoid 0.5 / ~0.881 sum-normalized preserves ratios (~0.362 / ~0.638).
    assert result[0]["alpha"] == pytest.approx(0.5 / 1.38, abs=0.01)
    assert result[0]["beta"] == pytest.approx(0.88 / 1.38, abs=0.01)


def test_multilabel_seqcls_labels_property(monkeypatch):
    stub_model = SeqClsStubModel(
        id2label={0: "alpha", 1: "beta"},
        logits=[0.0, 2.0],
    )
    install_seqcls_transformers_stub(monkeypatch, stub_model)
    backend = MultiLabelClassifierBackend(model="fake/seqcls")
    assert backend.labels == ("alpha", "beta")
