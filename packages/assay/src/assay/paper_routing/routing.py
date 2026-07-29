#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Paper routing orchestration: multi-hypothesis WG21 review-group classification."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from pipeline.classifier_backends import ClassifierBackend

from assay.paper_routing.aggregate import aggregate_quadrant_scores
from assay.paper_routing.hypotheses import score_hypotheses
from assay.paper_routing.sustain import sustained_counts
from assay.paper_routing.threshold import apply_thresholds
from assay.paper_routing.types import RoutingGroup


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
    classifiers: ClassifierBackend | Sequence[ClassifierBackend] | None = None,
    use_regex: bool = True,
    debug_log: list[str] | None = None,
) -> RoutingResult:
    """Run the 6-stage paper routing classifier on full paper markdown.

    Assay calls this on blanked paper (Step 0 ``blank_paper``), so
    references, acknowledgments, and revision-history headings are
    already empty lines and do not contribute hypothesis hits. Standalone
    callers passing raw markdown may see appendix-style signals from
    those sections; see ``assay.heading_classifiers.is_appendix_heading_line``.

    ``classifiers`` is an optional single backend or ordered sequence used
    for hypothesis scoring (NLI, fine-tuned seqcls). It is not the
    ``StepContext.classifiers`` slot dict from SERVICES.toml.
    """
    sentences = score_hypotheses(
        paper_md,
        audience=audience,
        classifiers=classifiers,
        use_regex=use_regex,
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
