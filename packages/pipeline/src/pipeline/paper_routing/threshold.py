#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Stage 6: multi-label thresholding."""

from __future__ import annotations

from pipeline.paper_routing.aggregate import LABEL_CWG, LABEL_EWG, LABEL_LEWG, LABEL_LWG
from pipeline.paper_routing.sustained import (
    min_sustained_threshold,
    performance_sustained_count,
    sustained_counts,
)
from pipeline.paper_routing.types import Sentence

THRESHOLD_LEWG = 0.08
THRESHOLD_LWG = 0.10
THRESHOLD_EWG = 0.08
THRESHOLD_CWG = 0.12

_LABEL_THRESHOLDS: dict[str, float] = {
    LABEL_LEWG: THRESHOLD_LEWG,
    LABEL_LWG: THRESHOLD_LWG,
    LABEL_EWG: THRESHOLD_EWG,
    LABEL_CWG: THRESHOLD_CWG,
}


def apply_thresholds(
    quadrant_scores: dict[str, float],
    sentences: list[Sentence],
) -> tuple[dict[str, float], bool]:
    """Return emitted groups and performance-focused flag."""
    counts = sustained_counts(sentences)
    min_sustained = min_sustained_threshold(len(sentences))
    groups: dict[str, float] = {}

    for label, score in quadrant_scores.items():
        threshold = _LABEL_THRESHOLDS[label]
        if score > threshold and counts.get(label, 0) >= min_sustained:
            groups[label] = score

    perf_count = performance_sustained_count(sentences)
    is_performance_focused = perf_count >= min_sustained

    return groups, is_performance_focused
