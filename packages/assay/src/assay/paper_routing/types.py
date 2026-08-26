#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Domain types for the paper routing classifier."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class HypothesisAxis(StrEnum):
    """Hypothesis axis categories from the classifier spec (Section 3).

    Two independent axes (Domain and Mode) plus structural/meta signals.
    """

    LIBRARY_DOMAIN = "library_domain"
    LANGUAGE_DOMAIN = "language_domain"
    DESIGN_MODE = "design_mode"
    WORDING_MODE = "wording_mode"
    STRUCTURAL = "structural"


class RoutingGroup(StrEnum):
    """WG21 review-group labels: the 2x2 grid of Domain x Mode.

    Each member sits at the intersection of one domain axis and one mode
    axis, mirroring the spec grid (paper-routing-classifier.md lines 29-38).
    """

    LEWG = "LEWG"
    LWG = "LWG"
    EWG = "EWG"
    CWG = "CWG"

    @property
    def domain(self) -> HypothesisAxis:
        if self in (RoutingGroup.LEWG, RoutingGroup.LWG):
            return HypothesisAxis.LIBRARY_DOMAIN
        return HypothesisAxis.LANGUAGE_DOMAIN

    @property
    def mode(self) -> HypothesisAxis:
        if self in (RoutingGroup.LEWG, RoutingGroup.EWG):
            return HypothesisAxis.DESIGN_MODE
        return HypothesisAxis.WORDING_MODE


# OneVsRest predict_proba column order for the learned aggregator. Training and
# inference must use this tuple; do not reorder without retraining aggregator_hgb.
# Persisted as artifact_names.GROUP_ORDER_FILE under ROUTING_METADATA_DIR and validated at load.
ROUTING_GROUP_ORDER: tuple[RoutingGroup, ...] = (
    RoutingGroup.LEWG,
    RoutingGroup.LWG,
    RoutingGroup.EWG,
    RoutingGroup.CWG,
)


class SectionType(StrEnum):
    """WG21 paper section categories for section-aware aggregation."""

    PREAMBLE = "PREAMBLE"
    MOTIVATION = "MOTIVATION"
    DESIGN = "DESIGN"
    WORDING = "WORDING"
    IMPACT = "IMPACT"
    IMPLEMENTATION = "IMPLEMENTATION"
    APPENDIX = "APPENDIX"


@dataclass(frozen=True)
class Sentence:
    """One routable unit from Stage 1 with section context and hypothesis hits."""

    text: str
    section: SectionType
    index: int
    hypothesis_hits: frozenset[str]
