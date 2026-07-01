#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

from __future__ import annotations

from pipeline.classifier_backends import NliCrossEncoderBackend
from pipeline.nli_batch import NLI_ENTAILMENT_THRESHOLD, score_entailment_pairs


class _FakeNliBackend:
    def __init__(self, entailments: list[float]) -> None:
        self._entailments = entailments
        self.calls: list[list[tuple[str, str]]] = []

    def nli_pairs(self, pairs: list[tuple[str, str]]) -> list[dict[str, float]]:
        self.calls.append(list(pairs))
        return [
            {"entailment": e, "neutral": 0.0, "contradiction": 0.0}
            for e in self._entailments
        ]


class _FakeClassifier(NliCrossEncoderBackend):
    def __init__(self, entailments: list[float]) -> None:
        self._fake = _FakeNliBackend(entailments)

    def nli_entailment_pairs(
        self, pairs: list[tuple[str, str]]
    ) -> list[dict[str, float]]:
        return self._fake.nli_pairs(pairs)


def test_score_entailment_pairs_preserves_order():
    clf = _FakeClassifier([0.9, 0.1, 0.51])
    pairs = [("a", "h1"), ("b", "h2"), ("c", "h3")]
    fired, scores = score_entailment_pairs(clf, pairs, threshold=0.5)
    assert fired == [True, False, True]
    assert len(scores) == 3
    assert clf._fake.calls[0] == pairs


def test_score_entailment_pairs_empty():
    clf = _FakeClassifier([])
    fired, scores = score_entailment_pairs(clf, [])
    assert fired == []
    assert scores == []


def test_threshold_constant():
    assert NLI_ENTAILMENT_THRESHOLD == 0.5
