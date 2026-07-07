#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.classifier_backends import NliCrossEncoderBackend

from assay.paper_routing import RoutingGroup, route_paper
from assay.paper_routing.hypotheses import (
    CATALOG,
    Hypothesis,
    _ROUTING_NLI_THRESHOLD,
    get_hits_from_text,
    score_hypotheses,
)
from assay.paper_routing.split import split_sentences
from assay.paper_routing.headings import classify_routing_section
from assay.paper_routing.types import SectionType
from assay.paper_routing.aggregate import (
    _apply_metadata_bonus,
    aggregate_quadrant_scores,
)
from assay.paper_routing.sustain import min_sustained_threshold
from assay.paper_routing.threshold import apply_thresholds, THRESHOLD_LEWG

_FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "routing"


def _read(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def test_n3854_routes_lewg_and_lwg():
    result = route_paper(_read("n3854.md"), audience=["LEWG", "LWG"])
    assert "LEWG" in result.groups
    assert "LWG" in result.groups
    assert "EWG" not in result.groups
    assert "CWG" not in result.groups
    assert not result.is_administrative


def test_n5044_administrative():
    result = route_paper(_read("n5044_excerpt.md"), audience=["WG21"])
    assert result.groups == {}
    assert result.is_administrative


def test_stray_language_no_ewg():
    result = route_paper(_read("stray_language.md"), audience=["LEWG"])
    assert "EWG" not in result.groups
    assert "CWG" not in result.groups


def test_performance_focused_flag():
    result = route_paper(_read("performance_focused.md"), classifier=None)
    assert result.is_performance_focused is True


def test_route_without_classifier():
    result = route_paper(_read("n3854.md"), classifier=None)
    assert result.sentence_count > 0
    assert "LEWG" in result.groups


def test_determinism():
    md = _read("n3854.md")
    a = route_paper(md, audience=["LEWG", "LWG"])
    b = route_paper(md, audience=["LEWG", "LWG"])
    assert a == b


def test_code_block_is_single_sentence():
    md = "Prose before.\n\n```cpp\nint x = 1;\nint y = 2;\n```\n\nProse after."
    units = split_sentences(md)
    assert len(units) == 3
    assert "```" in units[1].text


def test_heading_section_mapping():
    assert classify_routing_section("Motivation and Scope") == SectionType.MOTIVATION
    assert classify_routing_section("Proposed Wording") == SectionType.WORDING
    assert classify_routing_section("References") == SectionType.APPENDIX


@pytest.mark.parametrize("hyp", CATALOG)
def test_hypothesis_catalog_ids_unique(hyp: Hypothesis):
    ids = [h.id for h in CATALOG]
    assert ids.count(hyp.id) == 1


def test_d1_matches_library_header():
    hyp = next(h for h in CATALOG if h.id == "D1")
    assert hyp.matches_regex("Use <type_traits> for trait queries.")
    assert not hyp.matches_regex("No headers here.")


def test_sustained_min_floor():
    assert min_sustained_threshold(10) == 3
    assert min_sustained_threshold(500) == 10


def _zeroed_scores() -> dict[RoutingGroup, float]:
    return {g: 0.0 for g in RoutingGroup}


@pytest.mark.parametrize(
    ("audience", "expected"),
    [
        (
            ["LEWG"],
            {
                RoutingGroup.LEWG: 0.20,
                RoutingGroup.LWG: 0.10,
                RoutingGroup.EWG: 0.0,
                RoutingGroup.CWG: 0.0,
            },
        ),
        (
            ["LWG"],
            {
                RoutingGroup.LEWG: 0.15,
                RoutingGroup.LWG: 0.10,
                RoutingGroup.EWG: 0.0,
                RoutingGroup.CWG: 0.0,
            },
        ),
        (
            ["Library Evolution"],
            {
                RoutingGroup.LEWG: 0.20,
                RoutingGroup.LWG: 0.10,
                RoutingGroup.EWG: 0.0,
                RoutingGroup.CWG: 0.0,
            },
        ),
        (
            ["LEWG", "LWG"],
            {
                RoutingGroup.LEWG: 0.20,
                RoutingGroup.LWG: 0.10,
                RoutingGroup.EWG: 0.0,
                RoutingGroup.CWG: 0.0,
            },
        ),
        (
            ["EWG"],
            {
                RoutingGroup.LEWG: 0.0,
                RoutingGroup.LWG: 0.0,
                RoutingGroup.EWG: 0.20,
                RoutingGroup.CWG: 0.0,
            },
        ),
    ],
)
def test_metadata_bonus_audience_tokens(
    audience: list[str], expected: dict[RoutingGroup, float]
):
    scores = _zeroed_scores()
    _apply_metadata_bonus(scores, [], audience)
    assert scores == expected


_M4_NLI_TEXT = "The sentence explains why a design choice was made."
_NLI_ONLY_SENTENCE = "We chose this approach because it minimizes template bloat."


class _StubNliClassifier(NliCrossEncoderBackend):
    def __init__(self, entailment: float, *, match_hypothesis: str | None = None) -> None:
        self._entailment = entailment
        self._match_hypothesis = match_hypothesis
        self.calls: list[list[tuple[str, str]]] = []

    def nli_entailment_pairs(
        self, pairs: list[tuple[str, str]]
    ) -> list[dict[str, float]]:
        self.calls.append(list(pairs))
        scores: list[dict[str, float]] = []
        for _premise, hypothesis in pairs:
            if self._match_hypothesis is None or hypothesis == self._match_hypothesis:
                e = self._entailment
            else:
                e = 0.0
            scores.append({"entailment": e, "neutral": 0.0, "contradiction": 0.0})
        return scores


def test_routing_nli_threshold_constant():
    assert _ROUTING_NLI_THRESHOLD == 0.3


def test_score_hypotheses_nli_path_fires_on_high_entailment():
    sentence = _NLI_ONLY_SENTENCE
    assert get_hits_from_text(sentence) == set()

    classifier = _StubNliClassifier(0.9, match_hypothesis=_M4_NLI_TEXT)
    scored = score_hypotheses([sentence], classifier=classifier)

    assert len(scored) == 1
    assert "M4" in scored[0].hypothesis_hits
    assert classifier.calls
    assert classifier.calls[0][0][0] == sentence


def test_score_hypotheses_nli_path_skips_low_entailment():
    sentence = _NLI_ONLY_SENTENCE
    classifier = _StubNliClassifier(0.1, match_hypothesis=_M4_NLI_TEXT)
    scored = score_hypotheses([sentence], classifier=classifier)

    assert len(scored) == 1
    assert "M4" not in scored[0].hypothesis_hits


def test_score_hypotheses_from_sentence_list_matches_regex_hits():
    sentences = [
        "We propose to add std::widget.",
        "Effects: returns a value.",
    ]
    scored = score_hypotheses(sentences)
    assert len(scored) == 2
    assert scored[0].text == sentences[0]
    assert scored[1].text == sentences[1]
    assert scored[0].section == SectionType.PREAMBLE
    assert scored[1].section == SectionType.PREAMBLE
    assert set(scored[0].hypothesis_hits) == get_hits_from_text(sentences[0])
    assert set(scored[1].hypothesis_hits) == get_hits_from_text(sentences[1])


def test_score_hypotheses_markdown_assigns_section_from_headings():
    md = "## Motivation\n\nWe propose to add <vector> support."
    scored = score_hypotheses(md)
    assert len(scored) == 2
    assert scored[1].section == SectionType.MOTIVATION


def test_score_hypotheses_rejects_invalid_input_type():
    with pytest.raises(TypeError, match="expects str"):
        score_hypotheses(123)  # type: ignore[arg-type]


def test_score_hypotheses_rejects_non_string_list_items():
    with pytest.raises(TypeError, match="sentence list items must be str"):
        score_hypotheses(["ok", 1])  # type: ignore[list-item]


def test_threshold_requires_sustained_signal():
    from assay.paper_routing.types import Sentence

    sentences = [
        Sentence(
            "std::vector in <vector>",
            SectionType.MOTIVATION,
            0,
            frozenset({"D1", "M1"}),
        ),
        Sentence(
            "proposal to add more", SectionType.MOTIVATION, 1, frozenset({"M1", "D3"})
        ),
        Sentence(
            "library design rationale",
            SectionType.MOTIVATION,
            2,
            frozenset({"D3", "M6"}),
        ),
    ]
    scores = aggregate_quadrant_scores(sentences)
    groups, _ = apply_thresholds(scores, sentences)
    if scores[RoutingGroup.LEWG] > THRESHOLD_LEWG:
        assert RoutingGroup.LEWG in groups
