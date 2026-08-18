#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Stage 5: sustained signal co-firing test."""

from __future__ import annotations

import math

from assay.paper_routing.axis_hist import AXIS_HIT_FN
from assay.paper_routing.hypotheses import PERFORMANCE_ARGUMENT_ID
from assay.paper_routing.types import RoutingGroup, Sentence

MIN_SUSTAINED_FLOOR = 3
SUSTAINED_FRACTION = 0.02


def min_sustained_threshold(sentence_count: int) -> int:
    """Minimum co-firing sentences required for a label to emit."""
    return max(MIN_SUSTAINED_FLOOR, math.floor(sentence_count * SUSTAINED_FRACTION))


def sustained_counts(sentences: list[Sentence]) -> dict[RoutingGroup, int]:
    """Count sentences participating in domain+mode co-firing per label.

    Neighbors are adjacent in the kept sentence list (sorted by ``index``),
    not raw ``index ± 1``, so sampling that drops sentences still allows
    cross-sentence co-fire when original indices are gapped.
    """
    if not sentences:
        return {g: 0 for g in RoutingGroup}

    ordered = sorted(sentences, key=lambda s: s.index)
    counts: dict[RoutingGroup, int] = {g: 0 for g in RoutingGroup}

    for group in RoutingGroup:
        domain_fn = AXIS_HIT_FN[group.domain]
        mode_fn = AXIS_HIT_FN[group.mode]
        relevant: set[int] = set()
        for i, sent in enumerate(ordered):
            has_domain = bool(domain_fn(sent.hypothesis_hits))
            has_mode = bool(mode_fn(sent.hypothesis_hits))
            if has_domain and has_mode:
                relevant.add(sent.index)
                continue
            neighbors: list[Sentence] = []
            if i > 0:
                neighbors.append(ordered[i - 1])
            if i < len(ordered) - 1:
                neighbors.append(ordered[i + 1])
            for other in neighbors:
                if other.section != sent.section:
                    continue
                other_domain = bool(domain_fn(other.hypothesis_hits))
                other_mode = bool(mode_fn(other.hypothesis_hits))
                if (has_domain and other_mode) or (has_mode and other_domain):
                    relevant.add(sent.index)
                    break
        counts[group] = len(relevant)

    return counts


def performance_sustained_count(sentences: list[Sentence]) -> int:
    """Sentences where M13 (performance argument) fires."""
    return sum(1 for s in sentences if PERFORMANCE_ARGUMENT_ID in s.hypothesis_hits)
