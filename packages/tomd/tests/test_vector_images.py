#
# Copyright (c) 2026 Dmitriy Chukhin (dmitriy@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Unit tests for _merge_row_clusters and _merge_sub_figure_clusters.

Constructs synthetic Block/Line inputs in-memory; no PDF fixture needed.
"""

from __future__ import annotations

from tomd.lib.pdf.types import Block, Line, Span
from tomd.lib.pdf.vector_images import (
    _SUB_FIGURE_MAX_GAP_PT,
    _SUB_FIGURE_MAX_X_GAP_PT,
    _merge_row_clusters,
    _merge_sub_figure_clusters,
)

_BIG_AREA = 10_000_000.0


def _block(bbox: tuple[float, float, float, float], *line_texts: str) -> Block:
    """Build a Block whose lines each carry a single span of text.

    Each line_text gets its own Line; the line bbox equals the block bbox
    (good enough for gap-membership tests which only inspect y-coordinates).
    """
    lines = [
        Line(spans=[Span(text=t)], bbox=bbox)
        for t in line_texts
    ]
    return Block(lines=lines, bbox=bbox)


# ---------------------------------------------------------------------------
# _merge_row_clusters: happy-path merges
# ---------------------------------------------------------------------------

def test_row_merge_two_panels_same_row_with_sub_caption_below():
    """Two same-height clusters with a sub-caption line below merge into one."""
    A = ((0.0, 0.0, 80.0, 60.0), 10)
    B = ((130.0, 0.0, 210.0, 60.0), 10)   # x-gap = 50pt
    caption = _block((0.0, 65.0, 210.0, 75.0), "(a) Panel label")

    result = _merge_row_clusters([A, B], [caption], max_merged_area=_BIG_AREA)

    assert len(result) == 1
    bb, _ = result[0]
    assert bb == (0.0, 0.0, 210.0, 60.0)


# ---------------------------------------------------------------------------
# _merge_row_clusters: non-merge conditions
# ---------------------------------------------------------------------------

def test_row_merge_no_sub_caption_below_no_merge():
    """Without a confirming sub-caption line below, no merge occurs."""
    A = ((0.0, 0.0, 80.0, 60.0), 10)
    B = ((130.0, 0.0, 210.0, 60.0), 10)

    result = _merge_row_clusters([A, B], [], max_merged_area=_BIG_AREA)

    assert len(result) == 2


def test_row_merge_x_gap_too_large_no_merge():
    """An x-gap exceeding _SUB_FIGURE_MAX_X_GAP_PT prevents a merge."""
    x_start_b = 80.0 + _SUB_FIGURE_MAX_X_GAP_PT + 10.0
    A = ((0.0, 0.0, 80.0, 60.0), 10)
    B = ((x_start_b, 0.0, x_start_b + 100.0, 60.0), 10)
    caption = _block((0.0, 65.0, x_start_b + 100.0, 75.0), "(a) label")

    result = _merge_row_clusters([A, B], [caption], max_merged_area=_BIG_AREA)

    assert len(result) == 2


def test_row_merge_no_y_overlap_no_merge():
    """Clusters with non-overlapping y-ranges are not merged."""
    A = ((0.0, 0.0, 100.0, 60.0), 10)
    B = ((110.0, 70.0, 200.0, 130.0), 10)   # y starts at 70 > 60 = A's bottom
    caption = _block((0.0, 135.0, 200.0, 145.0), "(a) label")

    result = _merge_row_clusters([A, B], [caption], max_merged_area=_BIG_AREA)

    assert len(result) == 2


def test_row_merge_area_cap_no_merge():
    """Merged bbox exceeding max_merged_area is not merged."""
    A = ((0.0, 0.0, 400.0, 50.0), 10)
    B = ((450.0, 0.0, 800.0, 50.0), 10)   # merged would be 800×50 = 40 000 pt²
    caption = _block((0.0, 55.0, 800.0, 65.0), "(a) label")

    result = _merge_row_clusters([A, B], [caption], max_merged_area=35_000.0)

    assert len(result) == 2


# ---------------------------------------------------------------------------
# _merge_row_clusters: transitive accumulation
# ---------------------------------------------------------------------------

def test_row_merge_four_panels_transitive():
    """Four clusters in left-to-right order merge in a single inner-loop pass.

    A (index 0), B (index 1), C (index 2), D (index 3) each have a 50pt x-gap
    to the next.  The A-D gap (310pt) exceeds _SUB_FIGURE_MAX_X_GAP_PT so no
    non-adjacent pair qualifies directly.  The inner loop for i=0 accumulates
    A+B, then A+B+C, then A+B+C+D in one pass.  The second while-loop
    iteration is a stability no-op.
    """
    A = ((0.0,   0.0, 80.0,  60.0), 5)
    B = ((130.0, 0.0, 210.0, 60.0), 5)   # gap A-B = 50pt
    C = ((260.0, 0.0, 340.0, 60.0), 5)   # gap B-C = 50pt
    D = ((390.0, 0.0, 480.0, 60.0), 5)   # gap C-D = 50pt; gap A-D = 310pt

    caption = _block((0.0, 65.0, 480.0, 75.0), "(a) All panels")

    result = _merge_row_clusters([A, B, C, D], [caption], max_merged_area=_BIG_AREA)

    assert len(result) == 1
    bb, _ = result[0]
    assert bb == (0.0, 0.0, 480.0, 60.0)


# ---------------------------------------------------------------------------
# _merge_sub_figure_clusters: happy-path merges
# ---------------------------------------------------------------------------

def test_sub_figure_merge_two_panels_with_sub_caption():
    """Two clusters with a single sub-caption line in the gap merge into one."""
    top = ((0.0, 0.0, 100.0, 100.0), 10)
    bot = ((0.0, 150.0, 100.0, 250.0), 10)
    gap_block = _block((0.0, 100.0, 100.0, 150.0), "(a) Top panel")

    result = _merge_sub_figure_clusters([top, bot], [gap_block], max_merged_area=_BIG_AREA)

    assert len(result) == 1
    bb, _ = result[0]
    assert bb == (0.0, 0.0, 100.0, 250.0)


def test_sub_figure_merge_reverse_order():
    """Lower-first input exercises the top_bb/bot_bb else-branch."""
    bot = ((0.0, 150.0, 100.0, 250.0), 10)   # index 0
    top = ((0.0, 0.0, 100.0, 100.0), 10)      # index 1
    gap_block = _block((0.0, 100.0, 100.0, 150.0), "(a) label")

    result = _merge_sub_figure_clusters([bot, top], [gap_block], max_merged_area=_BIG_AREA)

    assert len(result) == 1
    bb, _ = result[0]
    assert bb == (0.0, 0.0, 100.0, 250.0)


def test_sub_figure_merge_mixed_gap_text_merges():
    """A gap with one sub-caption line and other non-caption text merges.

    Under the any() rule: "(a) label" fires the positive check; "See also
    Figure 3." does not match _FIGURE_CAPTION_RE (it starts with "See ", not
    "Figure "), so the negative guard does not fire.  Result: merge.
    """
    top = ((0.0, 0.0, 100.0, 100.0), 10)
    bot = ((0.0, 150.0, 100.0, 250.0), 10)
    gap_block = _block(
        (0.0, 100.0, 100.0, 150.0),
        "(a) label",
        "See also Figure 3.",
    )

    result = _merge_sub_figure_clusters([top, bot], [gap_block], max_merged_area=_BIG_AREA)

    assert len(result) == 1


def test_sub_figure_merge_wrapped_sub_caption_no_longer_blocks():
    """Wrapped continuation text alongside a valid sub-caption does not block.

    "(a) Top panel" satisfies any(); the continuation "of the graph given in
    1a." does not match _FIGURE_CAPTION_RE.  Merge proceeds.
    """
    top = ((0.0, 0.0, 100.0, 100.0), 10)
    bot = ((0.0, 150.0, 100.0, 250.0), 10)
    gap_block = _block(
        (0.0, 100.0, 100.0, 150.0),
        "(a) Top panel",
        "of the graph given in 1a.",
    )

    result = _merge_sub_figure_clusters([top, bot], [gap_block], max_merged_area=_BIG_AREA)

    assert len(result) == 1


# ---------------------------------------------------------------------------
# _merge_sub_figure_clusters: non-merge conditions
# ---------------------------------------------------------------------------

def test_sub_figure_merge_no_text_in_gap_no_merge():
    """Empty gap (no text blocks) does not merge."""
    top = ((0.0, 0.0, 100.0, 100.0), 10)
    bot = ((0.0, 150.0, 100.0, 250.0), 10)

    result = _merge_sub_figure_clusters([top, bot], [], max_merged_area=_BIG_AREA)

    assert len(result) == 2


def test_sub_figure_merge_continuation_text_only_no_merge():
    """A gap with no sub-caption label (any() returns False) does not merge."""
    top = ((0.0, 0.0, 100.0, 100.0), 10)
    bot = ((0.0, 150.0, 100.0, 250.0), 10)
    gap_block = _block((0.0, 100.0, 100.0, 150.0), "of the airport graph")

    result = _merge_sub_figure_clusters([top, bot], [gap_block], max_merged_area=_BIG_AREA)

    assert len(result) == 2


def test_sub_figure_merge_figure_caption_in_gap_no_merge():
    """A figure caption line in the gap blocks the merge."""
    top = ((0.0, 0.0, 100.0, 100.0), 10)
    bot = ((0.0, 150.0, 100.0, 250.0), 10)
    gap_block = _block(
        (0.0, 100.0, 100.0, 150.0),
        "(a) Panel one",
        "Figure 2: Some figure description.",
    )

    result = _merge_sub_figure_clusters([top, bot], [gap_block], max_merged_area=_BIG_AREA)

    assert len(result) == 2


def test_sub_figure_merge_gap_too_large_no_merge():
    """A gap exceeding _SUB_FIGURE_MAX_GAP_PT is not merged."""
    gap = _SUB_FIGURE_MAX_GAP_PT + 10.0
    top = ((0.0, 0.0, 100.0, 100.0), 10)
    bot = ((0.0, 100.0 + gap, 100.0, 200.0 + gap), 10)
    gap_block = _block(
        (0.0, 100.0, 100.0, 100.0 + gap),
        "(a) label",
    )

    result = _merge_sub_figure_clusters([top, bot], [gap_block], max_merged_area=_BIG_AREA)

    assert len(result) == 2


def test_sub_figure_merge_no_x_overlap_no_merge():
    """Side-by-side clusters (no x-overlap) are not merged."""
    left  = ((0.0,   0.0, 100.0, 100.0), 10)
    right = ((200.0, 150.0, 300.0, 250.0), 10)
    gap_block = _block((0.0, 100.0, 300.0, 150.0), "(a) label")

    result = _merge_sub_figure_clusters([left, right], [gap_block], max_merged_area=_BIG_AREA)

    assert len(result) == 2


def test_sub_figure_merge_area_cap_no_merge():
    """Merged bbox exceeding max_merged_area is skipped."""
    top = ((0.0, 0.0, 500.0, 100.0), 10)
    bot = ((0.0, 150.0, 500.0, 250.0), 10)
    gap_block = _block((0.0, 100.0, 500.0, 150.0), "(a) label")
    # merged would be 500 × 250 = 125 000 pt²; cap at 100 000.
    result = _merge_sub_figure_clusters(
        [top, bot], [gap_block], max_merged_area=100_000.0,
    )

    assert len(result) == 2


def test_sub_figure_merge_overlapping_clusters_no_merge():
    """Vertically overlapping clusters are rejected by the overlap guard."""
    a = ((0.0, 100.0, 100.0, 200.0), 10)
    b = ((0.0, 150.0, 100.0, 250.0), 10)

    result = _merge_sub_figure_clusters([a, b], [], max_merged_area=_BIG_AREA)

    assert len(result) == 2


# ---------------------------------------------------------------------------
# _merge_sub_figure_clusters: multi-cluster and iterative passes
# ---------------------------------------------------------------------------

def test_sub_figure_merge_iterative_three_panels():
    """Two productive while-loop passes are needed when input order prevents
    a single-pass resolution.

    Setup: [B (top), A (bottom), C (mid)] — B at index 0, A at index 1,
    C at index 2. B-to-A gap (200pt) exceeds the max; B-to-C gap (40pt)
    and C-to-A gap (60pt) are both valid.

    Pass 1: i=0 (B) skips j=1 (A, gap too large) then merges j=2 (C) →
    [B+C, A].
    Pass 2: i=0 (B+C) merges j=1 (A) → [B+C+A].
    """
    B = ((0.0, 0.0, 100.0, 100.0), 5)    # top,    index 0
    A = ((0.0, 300.0, 100.0, 400.0), 5)  # bottom, index 1
    C = ((0.0, 140.0, 100.0, 240.0), 5)  # mid,    index 2

    # "(b) ..." text in the B-to-C gap (y 100–140).
    bc_gap = _block((0.0, 100.0, 100.0, 140.0), "(b) panel b")
    # "(a) ..." text in the C-to-A gap (y 240–300).
    ca_gap = _block((0.0, 240.0, 100.0, 300.0), "(a) panel a")

    result = _merge_sub_figure_clusters(
        [B, A, C], [bc_gap, ca_gap], max_merged_area=_BIG_AREA,
    )

    assert len(result) == 1
    bb, _ = result[0]
    assert bb == (0.0, 0.0, 100.0, 400.0)


def test_sub_figure_merge_far_cluster_not_lost():
    """A cluster too far to merge is preserved exactly once in the output.

    Catches the original accumulator-corruption bug: with the old
    swap-then-continue design, cluster A would disappear and B would
    appear twice when A-to-B gap > max but B-to-C gap is valid.
    """
    A = ((0.0, 450.0, 100.0, 550.0), 5)  # low,  index 0
    B = ((0.0, 200.0, 100.0, 300.0), 5)  # mid,  index 1
    C = ((0.0, 0.0, 100.0, 100.0), 5)    # high, index 2

    # A-to-B gap = 150pt > 120pt (no merge for A-B pair).
    # B-to-C gap = 100pt ≤ 120pt with sub-caption text.
    bc_gap = _block((0.0, 100.0, 100.0, 200.0), "(a) label")

    result = _merge_sub_figure_clusters(
        [A, B, C], [bc_gap], max_merged_area=_BIG_AREA,
    )

    assert len(result) == 2
    bboxes = [bb for bb, _ in result]
    # A is present exactly once and unchanged.
    assert bboxes.count((0.0, 450.0, 100.0, 550.0)) == 1
    # B and C merged into one cluster spanning both.
    assert (0.0, 0.0, 100.0, 300.0) in bboxes
