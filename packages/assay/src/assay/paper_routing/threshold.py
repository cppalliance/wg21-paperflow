#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Stage 6: multi-label thresholding with admin gate and argmax+margin emission."""

from __future__ import annotations

from assay.paper_routing.sustain import (
    min_sustained_threshold,
    performance_sustained_count,
    sustained_counts,
)
from assay.paper_routing.types import RoutingGroup, Sentence

# Per-group score thresholds (fitted via offline sweep on golden labels).
THRESHOLD_LEWG = 0.30
THRESHOLD_LWG = 0.12
THRESHOLD_EWG = 0.35
THRESHOLD_CWG = 0.18

_GROUP_THRESHOLDS: dict[RoutingGroup, float] = {
    RoutingGroup.LEWG: THRESHOLD_LEWG,
    RoutingGroup.LWG: THRESHOLD_LWG,
    RoutingGroup.EWG: THRESHOLD_EWG,
    RoutingGroup.CWG: THRESHOLD_CWG,
}

# Argmax+margin: secondary groups must be within this margin of the primary.
SECONDARY_MARGIN = 0.08

# Admin gate: if the maximum quadrant score is at or below this, emit nothing.
ADMIN_MAX_SCORE_GATE = 0.05


def apply_thresholds(
    quadrant_scores: dict[RoutingGroup, float],
    sentences: list[Sentence],
) -> tuple[dict[RoutingGroup, float], bool]:
    """Emit groups using admin gate + argmax + margin policy.

    Policy:
    1. If max(quadrant_scores) <= ADMIN_MAX_SCORE_GATE -> emit {} (administrative).
    2. Find candidates passing both sustained floor AND group threshold.
    3. Primary = argmax among candidates (or global argmax as fallback).
    4. Emit primary; emit secondary only within SECONDARY_MARGIN of primary.
    """
    counts = sustained_counts(sentences)
    min_sustained = min_sustained_threshold(len(sentences))

    perf_count = performance_sustained_count(sentences)
    is_performance_focused = perf_count >= min_sustained

    if not quadrant_scores:
        return {}, is_performance_focused

    max_score = max(quadrant_scores.values())

    # Admin gate
    if max_score <= ADMIN_MAX_SCORE_GATE:
        return {}, is_performance_focused

    # Collect candidates that pass both sustained and threshold
    candidates: dict[RoutingGroup, float] = {}
    for group, score in quadrant_scores.items():
        threshold = _GROUP_THRESHOLDS[group]
        if score > threshold and counts.get(group, 0) >= min_sustained:
            candidates[group] = score

    if not candidates:
        # Fallback: emit global argmax if it passes its threshold
        best_group = max(quadrant_scores, key=lambda g: quadrant_scores[g])
        best_score = quadrant_scores[best_group]
        if best_score > _GROUP_THRESHOLDS[best_group]:
            return {best_group: best_score}, is_performance_focused
        return {}, is_performance_focused

    # Primary = highest-scoring candidate
    primary = max(candidates, key=lambda g: candidates[g])
    primary_score = candidates[primary]

    # Emit primary; add secondaries only within margin
    groups: dict[RoutingGroup, float] = {primary: primary_score}
    for group, score in candidates.items():
        if group == primary:
            continue
        if score >= primary_score - SECONDARY_MARGIN:
            groups[group] = score

    return groups, is_performance_focused
