#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.paper_routing import route_paper
from pipeline.paper_routing.hypotheses import CATALOG, Hypothesis
from pipeline.paper_routing.split import split_sentences
from pipeline.heading_classifiers import classify_routing_section
from pipeline.paper_routing.types import SectionType
from pipeline.paper_routing.aggregate import (
    LABEL_CWG,
    LABEL_EWG,
    LABEL_LEWG,
    LABEL_LWG,
    _apply_metadata_bonus,
    aggregate_quadrant_scores,
)
from pipeline.paper_routing.sustained import min_sustained_threshold
from pipeline.paper_routing.threshold import apply_thresholds, THRESHOLD_LEWG

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


def _zeroed_scores() -> dict[str, float]:
    return {LABEL_LEWG: 0.0, LABEL_LWG: 0.0, LABEL_EWG: 0.0, LABEL_CWG: 0.0}


@pytest.mark.parametrize(
    ("audience", "expected"),
    [
        (["LEWG"], {LABEL_LEWG: 0.20, LABEL_LWG: 0.0, LABEL_EWG: 0.0, LABEL_CWG: 0.0}),
        (["LWG"], {LABEL_LEWG: 0.15, LABEL_LWG: 0.10, LABEL_EWG: 0.0, LABEL_CWG: 0.0}),
        (
            ["Library Evolution"],
            {LABEL_LEWG: 0.20, LABEL_LWG: 0.0, LABEL_EWG: 0.0, LABEL_CWG: 0.0},
        ),
        (["EWG"], {LABEL_LEWG: 0.0, LABEL_LWG: 0.0, LABEL_EWG: 0.20, LABEL_CWG: 0.0}),
    ],
)
def test_metadata_bonus_audience_tokens(audience: list[str], expected: dict[str, float]):
    scores = _zeroed_scores()
    _apply_metadata_bonus(scores, [], audience)
    assert scores == expected


def test_threshold_requires_sustained_signal():
    from pipeline.paper_routing.types import Sentence

    sentences = [
        Sentence("std::vector in <vector>", SectionType.MOTIVATION, 0, frozenset({"D1", "M1"})),
        Sentence("proposal to add more", SectionType.MOTIVATION, 1, frozenset({"M1", "D3"})),
        Sentence("library design rationale", SectionType.MOTIVATION, 2, frozenset({"D3", "M6"})),
    ]
    scores = aggregate_quadrant_scores(sentences)
    groups, _ = apply_thresholds(scores, sentences)
    if scores["LEWG"] > THRESHOLD_LEWG:
        assert "LEWG" in groups
