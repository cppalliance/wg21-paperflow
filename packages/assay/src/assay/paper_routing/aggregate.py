#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Stage 4: section-aware aggregation into quadrant scores."""

from __future__ import annotations

from assay.paper_routing.audience import audience_blob, audience_has_phrase
from assay.paper_routing.axis_hist import (
    axis_density,
    design_hits,
    language_hits,
    library_hits,
    wording_hits,
)
from assay.paper_routing.types import RoutingGroup, SectionType, Sentence

_DESIGN_SECTION_WEIGHTS: dict[SectionType, float] = {
    SectionType.PREAMBLE: 0.3,
    SectionType.MOTIVATION: 1.0,
    SectionType.DESIGN: 1.0,
    SectionType.WORDING: 0.1,
    SectionType.IMPACT: 0.5,
    SectionType.IMPLEMENTATION: 0.3,
    SectionType.APPENDIX: 0.0,
}

_WORDING_SECTION_WEIGHTS: dict[SectionType, float] = {
    SectionType.PREAMBLE: 0.1,
    SectionType.MOTIVATION: 0.1,
    SectionType.DESIGN: 0.1,
    SectionType.WORDING: 1.0,
    SectionType.IMPACT: 0.2,
    SectionType.IMPLEMENTATION: 0.0,
    SectionType.APPENDIX: 0.0,
}

_METADATA_BONUS_LIBRARY_LEWG = 0.15
_METADATA_BONUS_LIBRARY_LWG = 0.10
_METADATA_BONUS_LIBRARY_EVOLUTION_LEWG = 0.20
_METADATA_BONUS_CORE_CWG = 0.15
_METADATA_BONUS_CORE_EWG = 0.10
_METADATA_BONUS_EVOLUTION_EWG = 0.20

# Domain arbitration: suppress the weaker domain unless it clears this margin
# of the stronger domain's best score. Prevents double-domain firing.
DOMAIN_ARBITRATION_MARGIN = 0.10


def aggregate_quadrant_scores(
    sentences: list[Sentence],
    *,
    audience: list[str] | None = None,
) -> dict[RoutingGroup, float]:
    """Compute pre-threshold LEWG/LWG/EWG/CWG scores with domain arbitration."""
    if not sentences:
        return {g: 0.0 for g in RoutingGroup}

    total = len(sentences)
    by_section: dict[SectionType, list[Sentence]] = {}
    for sent in sentences:
        by_section.setdefault(sent.section, []).append(sent)

    scores: dict[RoutingGroup, float] = {g: 0.0 for g in RoutingGroup}

    for section_type, section_sents in by_section.items():
        section_count = len(section_sents)
        mass_factor = section_count / total
        lib_density = axis_density(section_sents, library_hits)
        lang_density = axis_density(section_sents, language_hits)
        design_density = axis_density(section_sents, design_hits)
        wording_density = axis_density(section_sents, wording_hits)

        design_weight = _DESIGN_SECTION_WEIGHTS[section_type]
        wording_weight = _WORDING_SECTION_WEIGHTS[section_type]

        scores[RoutingGroup.LEWG] += (
            design_weight * min(lib_density, design_density) * mass_factor
        )
        scores[RoutingGroup.LWG] += (
            wording_weight * min(lib_density, wording_density) * mass_factor
        )
        scores[RoutingGroup.EWG] += (
            design_weight * min(lang_density, design_density) * mass_factor
        )
        scores[RoutingGroup.CWG] += (
            wording_weight * min(lang_density, wording_density) * mass_factor
        )

    _apply_metadata_bonus(scores, sentences, audience)
    _apply_domain_arbitration(scores)
    return scores


def _apply_domain_arbitration(scores: dict[RoutingGroup, float]) -> None:
    """Suppress the weaker domain unless it is within margin of the stronger."""
    library_best = max(scores[RoutingGroup.LEWG], scores[RoutingGroup.LWG])
    language_best = max(scores[RoutingGroup.EWG], scores[RoutingGroup.CWG])

    if library_best == 0.0 and language_best == 0.0:
        return

    if library_best >= language_best:
        if language_best < library_best - DOMAIN_ARBITRATION_MARGIN:
            scores[RoutingGroup.EWG] *= 0.0
            scores[RoutingGroup.CWG] *= 0.0
    else:
        if library_best < language_best - DOMAIN_ARBITRATION_MARGIN:
            scores[RoutingGroup.LEWG] *= 0.0
            scores[RoutingGroup.LWG] *= 0.0


def _apply_metadata_bonus(
    scores: dict[RoutingGroup, float],
    _sentences: list[Sentence],
    audience: list[str] | None,
) -> None:
    blob = audience_blob(audience)
    if not blob:
        return

    if audience_has_phrase(blob, "LIBRARY EVOLUTION") or audience_has_phrase(
        blob, "LEWG"
    ):
        scores[RoutingGroup.LEWG] += _METADATA_BONUS_LIBRARY_EVOLUTION_LEWG
        scores[RoutingGroup.LWG] += _METADATA_BONUS_LIBRARY_LWG
    elif audience_has_phrase(blob, "LIBRARY") or audience_has_phrase(blob, "LWG"):
        scores[RoutingGroup.LEWG] += _METADATA_BONUS_LIBRARY_LEWG
        scores[RoutingGroup.LWG] += _METADATA_BONUS_LIBRARY_LWG

    if audience_has_phrase(blob, "CORE") or audience_has_phrase(blob, "CWG"):
        scores[RoutingGroup.CWG] += _METADATA_BONUS_CORE_CWG
        scores[RoutingGroup.EWG] += _METADATA_BONUS_CORE_EWG
    elif (
        audience_has_phrase(blob, "EVOLUTION") or audience_has_phrase(blob, "EWG")
    ) and not audience_has_phrase(blob, "LIBRARY EVOLUTION"):
        scores[RoutingGroup.EWG] += _METADATA_BONUS_EVOLUTION_EWG
