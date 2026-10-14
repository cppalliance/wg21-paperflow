#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Deterministic content-loss label derived from a golden ``IdealPanel``.

A pure function, no LLM, no I/O: ``label_from_ideal_panel`` takes the
``IdealPanel`` already computed by ``whisker.golden_ideals.score_against_ideal``
and buckets it into one of three fixed labels ("good" / "review" / "bad") by
thresholding a single axis.

Construct validity is the whole point of this module. ONLY ``recall``
(multiset content recall of the ideal in the candidate) decides the label.
Every structural axis on the panel -- ``teds``, ``mhs``, ``block_agreement``,
``structural_parity``, ``heading_level_parity`` -- measures agreement on
DOCUMENT STRUCTURE (tables, heading hierarchy, block layout), not content
loss, and is deliberately ignored here. Real measurements confirm this split
matters: on the same heavy-content-loss papers (e.g. markitdown on P1068R11,
recall 0.261; P2040R0, recall 0.390), the whole-document ``nid`` axis stays
misleadingly HIGH (0.955 and 0.989 respectively) because edit-distance
similarity does not see whole sections quietly dropped from the tail of a
document. ``nid`` is carried on ``GoldenLabel`` as companion evidence only;
it never enters the labeling decision.

Usage: this label exists to serve as an INDEPENDENT check on a
``unigram_coverage`` threshold fitted elsewhere (calibration validation, out
of scope here). It must never itself become a fit source for that or any
other threshold; that would collapse the independence the check exists to
provide.
"""

from __future__ import annotations

from dataclasses import dataclass

from whisker.golden_ideals import IdealPanel

__all__ = [
    "GOLDEN_LABEL_BAD",
    "GOLDEN_LABEL_GOOD",
    "GOLDEN_LABEL_REVIEW",
    "GOLDEN_RECALL_BAD_EDGE",
    "GOLDEN_RECALL_GOOD_EDGE",
    "GoldenLabel",
    "label_from_ideal_panel",
]

GOLDEN_LABEL_GOOD = "good"
GOLDEN_LABEL_REVIEW = "review"
GOLDEN_LABEL_BAD = "bad"

# Fitted against real recall values across all 12 golden papers (tomd and
# markitdown conversions). Natural gaps in that data land at 0.39 -> 0.82 and
# 0.86 -> 0.92, not at a round number: 0.90 sits inside the upper gap (clean
# papers start at 0.923; the highest review-band case measured is 0.861), and
# 0.70 sits inside the lower gap (review-band floor measured at 0.823; clear
# heavy-loss cases top out at 0.390).
GOLDEN_RECALL_GOOD_EDGE = 0.90
GOLDEN_RECALL_BAD_EDGE = 0.70


@dataclass(frozen=True)
class GoldenLabel:
    """A deterministic content-loss verdict for one golden-scored paper.

    ``label`` is one of ``GOLDEN_LABEL_GOOD`` / ``GOLDEN_LABEL_REVIEW`` /
    ``GOLDEN_LABEL_BAD``, decided from ``recall`` alone.
    """

    label: str
    recall: float
    # Companion evidence only (see module docstring): reported for a human or
    # a downstream report to read alongside the label, but never consulted by
    # label_from_ideal_panel to make the decision. nid can be high even when
    # recall is low (whole sections dropped, edit distance blind to it).
    nid: float


def label_from_ideal_panel(panel: IdealPanel) -> GoldenLabel:
    """Bucket a golden ``IdealPanel`` into a content-loss label by ``recall``.

    Boundary convention (edges are inclusive on the side written below):

    - ``recall >= GOLDEN_RECALL_GOOD_EDGE`` -> ``GOLDEN_LABEL_GOOD``.
    - ``recall < GOLDEN_RECALL_BAD_EDGE`` -> ``GOLDEN_LABEL_BAD``.
    - otherwise -> ``GOLDEN_LABEL_REVIEW``.

    So ``recall == GOLDEN_RECALL_GOOD_EDGE`` (0.90) is "good", and
    ``recall == GOLDEN_RECALL_BAD_EDGE`` (0.70) is "review", not "bad".
    """
    if panel.recall >= GOLDEN_RECALL_GOOD_EDGE:
        label = GOLDEN_LABEL_GOOD
    elif panel.recall < GOLDEN_RECALL_BAD_EDGE:
        label = GOLDEN_LABEL_BAD
    else:
        label = GOLDEN_LABEL_REVIEW
    return GoldenLabel(label=label, recall=panel.recall, nid=panel.nid)
