#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Stage 5: sustained signal co-firing test."""

from __future__ import annotations

import math

from pipeline.paper_routing.aggregate import LABEL_CWG, LABEL_EWG, LABEL_LEWG, LABEL_LWG
from pipeline.paper_routing.axis_hits import (
    design_hits,
    language_hits,
    library_hits,
    wording_hits,
)
from pipeline.paper_routing.hypotheses import PERFORMANCE_HYPOTHESIS
from pipeline.paper_routing.types import Sentence

MIN_SUSTAINED_FLOOR = 3
SUSTAINED_FRACTION = 0.02

_LABEL_DOMAIN_MODE: dict[str, tuple] = {
    LABEL_LEWG: (library_hits, design_hits),
    LABEL_LWG: (library_hits, wording_hits),
    LABEL_EWG: (language_hits, design_hits),
    LABEL_CWG: (language_hits, wording_hits),
}


def min_sustained_threshold(sentence_count: int) -> int:
    """Minimum co-firing sentences required for a label to emit."""
    return max(MIN_SUSTAINED_FLOOR, math.floor(sentence_count * SUSTAINED_FRACTION))


def sustained_counts(sentences: list[Sentence]) -> dict[str, int]:
    """Count sentences participating in domain+mode co-firing per label."""
    if not sentences:
        return {LABEL_LEWG: 0, LABEL_LWG: 0, LABEL_EWG: 0, LABEL_CWG: 0}

    by_index = {s.index: s for s in sentences}
    ordered = sorted(sentences, key=lambda s: s.index)
    counts = {LABEL_LEWG: 0, LABEL_LWG: 0, LABEL_EWG: 0, LABEL_CWG: 0}

    for label, (domain_fn, mode_fn) in _LABEL_DOMAIN_MODE.items():
        relevant: set[int] = set()
        for sent in ordered:
            has_domain = bool(domain_fn(sent.hypothesis_hits))
            has_mode = bool(mode_fn(sent.hypothesis_hits))
            if has_domain and has_mode:
                relevant.add(sent.index)
                continue
            for neighbor in (sent.index - 1, sent.index + 1):
                other = by_index.get(neighbor)
                if other is None or other.section != sent.section:
                    continue
                other_domain = bool(domain_fn(other.hypothesis_hits))
                other_mode = bool(mode_fn(other.hypothesis_hits))
                if (has_domain and other_mode) or (has_mode and other_domain):
                    relevant.add(sent.index)
        counts[label] = len(relevant)

    return counts


def performance_sustained_count(sentences: list[Sentence]) -> int:
    """Sentences where M13 (performance argument) fires."""
    return sum(
        1 for s in sentences if PERFORMANCE_HYPOTHESIS in s.hypothesis_hits
    )
