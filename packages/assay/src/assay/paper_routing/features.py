#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Deterministic paper-level feature extraction for the learned aggregator."""

from __future__ import annotations

import math
from collections.abc import Sequence

from assay.paper_routing.audience import audience_blob, audience_has_phrase
from assay.paper_routing.axis_hist import (
    AXIS_HIT_FN,
    axis_density,
    design_hits,
    language_hits,
    library_hits,
    wording_hits,
)
from assay.paper_routing.hypotheses import CATALOG
from assay.paper_routing.sustain import min_sustained_threshold, sustained_counts
from assay.paper_routing.types import HypothesisAxis, RoutingGroup, SectionType, Sentence

_SECTION_ORDER: tuple[SectionType, ...] = tuple(SectionType)
_GROUP_ORDER: tuple[RoutingGroup, ...] = tuple(RoutingGroup)
_AXIS_ORDER: tuple[HypothesisAxis, ...] = (
    HypothesisAxis.LIBRARY_DOMAIN,
    HypothesisAxis.LANGUAGE_DOMAIN,
    HypothesisAxis.DESIGN_MODE,
    HypothesisAxis.WORDING_MODE,
)

_AUDIENCE_FLAG_NAMES: tuple[str, ...] = (
    "audience_library_evolution",
    "audience_lewg",
    "audience_library",
    "audience_lwg",
    "audience_core",
    "audience_cwg",
    "audience_evolution",
    "audience_ewg",
    "s1_fired",
)


def default_catalog_ids() -> tuple[str, ...]:
    return tuple(sorted(h.id for h in CATALOG))


def build_feature_names(catalog_ids: Sequence[str]) -> tuple[str, ...]:
    names: list[str] = []
    for section in _SECTION_ORDER:
        names.append(f"section_mass_{section.value}")
    for section in _SECTION_ORDER:
        for axis in _AXIS_ORDER:
            names.append(f"axis_density_{section.value}_{axis.value}")
    for hyp_id in sorted(catalog_ids):
        names.append(f"hyp_density_{hyp_id}")
    for group in _GROUP_ORDER:
        names.append(f"sustained_{group.value}")
    names.append("min_sustained")
    names.append("sentence_count_log1p")
    names.extend(_AUDIENCE_FLAG_NAMES)
    for axis in _AXIS_ORDER:
        names.append(f"axis_any_{axis.value}")
    return tuple(names)


def extract_paper_features(
    sentences: list[Sentence],
    *,
    audience: list[str] | None = None,
    catalog_ids: Sequence[str] | None = None,
) -> dict[str, float]:
    """Build a named feature map for one paper's scored sentences."""
    ids = tuple(sorted(catalog_ids or default_catalog_ids()))
    total = len(sentences)
    by_section: dict[SectionType, list[Sentence]] = {}
    for sent in sentences:
        by_section.setdefault(sent.section, []).append(sent)

    features: dict[str, float] = {}
    for section in _SECTION_ORDER:
        section_sents = by_section.get(section, [])
        mass = len(section_sents) / total if total else 0.0
        features[f"section_mass_{section.value}"] = mass
        for axis in _AXIS_ORDER:
            axis_fn = AXIS_HIT_FN[axis]
            features[f"axis_density_{section.value}_{axis.value}"] = axis_density(
                section_sents,
                axis_fn,
            )

    for hyp_id in ids:
        if total:
            count = sum(1 for s in sentences if hyp_id in s.hypothesis_hits)
            features[f"hyp_density_{hyp_id}"] = count / total
        else:
            features[f"hyp_density_{hyp_id}"] = 0.0

    sustained = sustained_counts(sentences)
    for group in _GROUP_ORDER:
        features[f"sustained_{group.value}"] = float(sustained[group])
    features["min_sustained"] = float(min_sustained_threshold(total))
    features["sentence_count_log1p"] = math.log1p(total)

    blob = audience_blob(audience)
    s1_fired = any("S1" in s.hypothesis_hits for s in sentences)
    features["s1_fired"] = 1.0 if s1_fired else 0.0
    features["audience_library_evolution"] = (
        1.0 if audience_has_phrase(blob, "LIBRARY EVOLUTION") else 0.0
    )
    features["audience_lewg"] = 1.0 if audience_has_phrase(blob, "LEWG") else 0.0
    features["audience_library"] = 1.0 if audience_has_phrase(blob, "LIBRARY") else 0.0
    features["audience_lwg"] = 1.0 if audience_has_phrase(blob, "LWG") else 0.0
    features["audience_core"] = 1.0 if audience_has_phrase(blob, "CORE") else 0.0
    features["audience_cwg"] = 1.0 if audience_has_phrase(blob, "CWG") else 0.0
    features["audience_evolution"] = 1.0 if audience_has_phrase(blob, "EVOLUTION") else 0.0
    features["audience_ewg"] = 1.0 if audience_has_phrase(blob, "EWG") else 0.0

    if total:
        all_hits = set().union(*(s.hypothesis_hits for s in sentences))
        features["axis_any_library_domain"] = 1.0 if library_hits(frozenset(all_hits)) else 0.0
        features["axis_any_language_domain"] = 1.0 if language_hits(frozenset(all_hits)) else 0.0
        features["axis_any_design_mode"] = 1.0 if design_hits(frozenset(all_hits)) else 0.0
        features["axis_any_wording_mode"] = 1.0 if wording_hits(frozenset(all_hits)) else 0.0
    else:
        features["axis_any_library_domain"] = 0.0
        features["axis_any_language_domain"] = 0.0
        features["axis_any_design_mode"] = 0.0
        features["axis_any_wording_mode"] = 0.0

    return features


def vectorize_features(
    features: dict[str, float],
    feature_names: Sequence[str],
) -> list[float]:
    return [float(features[name]) for name in feature_names]
