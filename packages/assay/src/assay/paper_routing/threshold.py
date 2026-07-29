#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Stage 6: multi-label thresholding."""

from __future__ import annotations

from assay.paper_routing.sustain import (
    min_sustained_threshold,
    performance_sustained_count,
    sustained_counts,
)
from assay.paper_routing.types import RoutingGroup, Sentence

THRESHOLD_LEWG = 0.25
THRESHOLD_LWG = 0.10
THRESHOLD_EWG = 0.15
THRESHOLD_CWG = 0.08

_GROUP_THRESHOLDS: dict[RoutingGroup, float] = {
    RoutingGroup.LEWG: THRESHOLD_LEWG,
    RoutingGroup.LWG: THRESHOLD_LWG,
    RoutingGroup.EWG: THRESHOLD_EWG,
    RoutingGroup.CWG: THRESHOLD_CWG,
}


def apply_thresholds(
    quadrant_scores: dict[RoutingGroup, float],
    sentences: list[Sentence],
) -> tuple[dict[RoutingGroup, float], bool]:
    """Return emitted groups and performance-focused flag."""
    counts = sustained_counts(sentences)
    min_sustained = min_sustained_threshold(len(sentences))
    groups: dict[RoutingGroup, float] = {}

    for group, score in quadrant_scores.items():
        threshold = _GROUP_THRESHOLDS[group]
        if score > threshold and counts.get(group, 0) >= min_sustained:
            groups[group] = score

    perf_count = performance_sustained_count(sentences)
    is_performance_focused = perf_count >= min_sustained

    return groups, is_performance_focused
