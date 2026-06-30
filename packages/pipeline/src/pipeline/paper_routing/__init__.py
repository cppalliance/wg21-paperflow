#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Paper routing classifier: multi-hypothesis WG21 review-group routing."""

from __future__ import annotations

from dataclasses import dataclass

from pipeline.classifier_backends import ClassifierBackend
from pipeline.paper_routing.aggregate import aggregate_quadrant_scores
from pipeline.paper_routing.hypotheses import score_hypotheses
from pipeline.paper_routing.sustain import sustained_counts
from pipeline.paper_routing.threshold import apply_thresholds
from pipeline.paper_routing.types import HypothesisAxis, RoutingGroup  # noqa: F401


@dataclass(frozen=True)
class RoutingResult:
    """Multi-label routing output from Stages 1-6."""

    groups: dict[RoutingGroup, float]
    quadrant_scores: dict[RoutingGroup, float]
    sustained_counts: dict[RoutingGroup, int]
    is_performance_focused: bool
    sentence_count: int

    @property
    def is_administrative(self) -> bool:
        """Zero labels above threshold means non-proposal document."""
        return len(self.groups) == 0


def route_paper(
    paper_md: str,
    *,
    audience: list[str] | None = None,
    classifier: ClassifierBackend | None = None,
    debug_log: list[str] | None = None,
) -> RoutingResult:
    """Run the 6-stage paper routing classifier on full paper markdown.

    Assay calls this on blanked paper (Step 0 ``blank_paper``), so
    references, acknowledgments, and revision-history headings are
    already empty lines and do not contribute hypothesis hits. Standalone
    callers passing raw markdown may see appendix-style signals from
    those sections; see ``heading_classifiers.is_appendix_heading_line``.
    """
    sentences = score_hypotheses(
        paper_md,
        audience=audience,
        classifier=classifier,
        debug_log=debug_log,
    )
    quadrant_scores = aggregate_quadrant_scores(sentences, audience=audience)
    sustained = sustained_counts(sentences)
    groups, is_performance_focused = apply_thresholds(quadrant_scores, sentences)

    return RoutingResult(
        groups=groups,
        quadrant_scores=quadrant_scores,
        sustained_counts=sustained,
        is_performance_focused=is_performance_focused,
        sentence_count=len(sentences),
    )
