#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Direct coverage for ``extract_paper_features``: empty, audience, and sustained paths."""

from __future__ import annotations

from assay.paper_routing.features import extract_paper_features
from assay.paper_routing.sustain import MIN_SUSTAINED_FLOOR
from assay.paper_routing.types import RoutingGroup, SectionType, Sentence


def test_extract_paper_features_empty_sentences_are_all_zero() -> None:
    features = extract_paper_features([])

    for section in SectionType:
        assert features[f"section_mass_{section.value}"] == 0.0
    for group in RoutingGroup:
        assert features[f"sustained_{group.value}"] == 0.0
    assert features["min_sustained"] == float(MIN_SUSTAINED_FLOOR)
    assert features["sentence_count_log1p"] == 0.0
    assert features["s1_fired"] == 0.0
    assert features["axis_any_library_domain"] == 0.0
    assert features["axis_any_language_domain"] == 0.0
    assert features["axis_any_design_mode"] == 0.0
    assert features["axis_any_wording_mode"] == 0.0


def test_extract_paper_features_audience_flags_are_independent() -> None:
    sentence = Sentence(
        text="proposal text",
        section=SectionType.PREAMBLE,
        index=0,
        hypothesis_hits=frozenset(),
    )

    lewg = extract_paper_features([sentence], audience=["LEWG"])
    assert lewg["audience_lewg"] == 1.0
    assert lewg["audience_library"] == 0.0
    assert lewg["audience_library_evolution"] == 0.0
    assert lewg["audience_ewg"] == 0.0

    library_evolution = extract_paper_features(
        [sentence], audience=["Library Evolution"]
    )
    assert library_evolution["audience_library_evolution"] == 1.0
    assert library_evolution["audience_lewg"] == 0.0

    core = extract_paper_features([sentence], audience=["Core"])
    assert core["audience_core"] == 1.0
    assert core["audience_cwg"] == 0.0

    no_audience = extract_paper_features([sentence], audience=None)
    for flag in (
        "audience_library_evolution",
        "audience_lewg",
        "audience_library",
        "audience_lwg",
        "audience_core",
        "audience_cwg",
        "audience_evolution",
        "audience_ewg",
    ):
        assert no_audience[flag] == 0.0


def test_extract_paper_features_s1_fired_flag() -> None:
    fired = Sentence(
        text="audience: LEWG, LWG",
        section=SectionType.PREAMBLE,
        index=0,
        hypothesis_hits=frozenset({"S1"}),
    )
    not_fired = Sentence(
        text="no metadata here",
        section=SectionType.PREAMBLE,
        index=0,
        hypothesis_hits=frozenset(),
    )

    assert extract_paper_features([fired])["s1_fired"] == 1.0
    assert extract_paper_features([not_fired])["s1_fired"] == 0.0


def test_extract_paper_features_sustained_counts_reflect_cofiring() -> None:
    """Sentences co-firing LIBRARY_DOMAIN + DESIGN_MODE across a section
    should raise sustained_LEWG above zero, while a domain with no co-firing
    stays at zero."""
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

    features = extract_paper_features(sentences)

    assert features["sustained_LEWG"] > 0.0
    assert features["sustained_CWG"] == 0.0
    assert features["axis_any_library_domain"] == 1.0
    assert features["axis_any_language_domain"] == 0.0
