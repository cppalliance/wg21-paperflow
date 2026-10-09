#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Block-level text matching (OmniDocBench match_quick port).

The full-document edit distance (``metrics.text_nid``) hides localized errors
and is order-sensitive: a faithful reflow of multi-column text scores low even
though every word is present. OmniDocBench instead matches blocks before
measuring text agreement: a normalized-edit-distance (NED) cost matrix, a
Hungarian assignment, an accept threshold, and a fuzzy substring rescue for
unmatched ground-truth blocks. Text agreement is then the page-weighted
``sum(Edit_num) / sum(upper_len)`` over matched blocks (OmniDocBench
``edit_whole``), which is robust to block reordering and to junk that only one
side emits (it simply does not match).

This module returns data only. ``block_text_nid`` is the public entry used by
the per-paper oracle (score.py) and the labeled benchmark (bench.py).

Faithful to ``_bench_src/OmniDocBench/src/core/matching/match_quick.py`` and
``src/metrics/cal_metric.py``. shortcut: the OmniDocBench ``deal_with_truncated``
adjacency-merge step (merging consecutive pred blocks when one side split a
paragraph) is not ported; the < 0.40 fuzzy rescue covers the common embedded /
clipped case. Port the merge if split-paragraph oracles measurably depress
block agreement on real papers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
from rapidfuzz.distance import Levenshtein as _Lev
from scipy.optimize import linear_sum_assignment

from whisker import constants as C
from whisker.metrics import normalized_text, text_nid

__all__ = [
    "BlockMatch",
    "BlockMetrics",
    "block_metrics",
    "block_text_nid",
    "match_blocks",
    "reading_order_ned",
    "split_paragraph_blocks",
]

_FENCE_RE = re.compile(r"^\s*(```|~~~)")


@dataclass(frozen=True)
class BlockMatch:
    """One matched (gt_block, pred_block(s)) pair with its edit cost.

    ``gt_index`` / ``pred_indices`` index into the original block lists (a single
    pred block per match in this port; a list keeps the OmniDocBench shape for
    reading order and a future adjacency-merge). ``edit`` is the NED in [0, 1];
    ``edit_num`` / ``upper_len`` are the raw Levenshtein distance and the longer
    length, summed by ``block_edit_whole``.
    """

    gt_index: int
    pred_indices: tuple[int, ...]
    edit: float
    edit_num: int
    upper_len: int


def split_paragraph_blocks(md: str) -> list[str]:
    """Split markdown into blank-line-separated blocks, skipping fenced code.

    Code fences are dropped wholesale: their content is not prose and would
    dominate the edit distance. Each returned block is stripped and non-empty.
    """
    blocks: list[str] = []
    cur: list[str] = []
    in_fence = False
    for line in md.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not line.strip():
            if cur:
                blocks.append("\n".join(cur).strip())
                cur = []
        else:
            cur.append(line)
    if cur:
        blocks.append("\n".join(cur).strip())
    return [b for b in blocks if b]


def _ned(a: str, b: str) -> float:
    """Normalized edit distance in [0, 1] (OmniDocBench convention)."""
    if not a and not b:
        return 0.0
    longest = max(len(a), len(b))
    if longest == 0:
        return 0.0
    return _Lev.distance(a, b) / longest


def _ned_matrix(gt_lines: list[str], pred_lines: list[str]) -> np.ndarray:
    """OmniDocBench compute_edit_distance_matrix_new: NED for every (gt, pred)."""
    m = np.zeros((len(gt_lines), len(pred_lines)))
    for i, g in enumerate(gt_lines):
        for j, p in enumerate(pred_lines):
            m[i, j] = _ned(g, p)
    return m


def _sub_gt_fuzzy_matching(pred: str, gt: str) -> float:
    """Best NED of any pred substring of len(gt) against gt (sub_gt_fuzzy_matching).

    Returns the minimum NED over the sliding window, or 1.0 when gt cannot be
    embedded in pred. Used to rescue an unmatched GT block whose text is present
    inside a longer pred block.
    """
    gt_len = len(gt)
    pred_len = len(pred)
    if gt_len == 0 or pred_len < gt_len:
        return 1.0
    best = 1.0
    for i in range(pred_len - gt_len + 1):
        d = _Lev.distance(pred[i:i + gt_len], gt) / gt_len
        if d < best:
            best = d
            if best == 0.0:
                break
    return best


def match_blocks(
    gt_blocks: list[str],
    pred_blocks: list[str],
    *,
    normalize=normalized_text,
) -> list[BlockMatch]:
    """Match GT blocks to pred blocks (OmniDocBench match_gt2pred_quick core).

    Pipeline: normalize both sides (empty-after-normalize blocks dropped), build
    the NED cost matrix, Hungarian-assign, keep pairs at <= BLOCK_ACCEPT_NED,
    then fuzzy-rescue unmatched GT blocks embedded in a pred block within
    < BLOCK_FUZZY_RESCUE_NED. Deterministic.
    """
    gt_n = [normalize(b) for b in gt_blocks]
    pr_n = [normalize(b) for b in pred_blocks]
    gt_keep = [(i, t) for i, t in enumerate(gt_n) if t]
    pr_keep = [(j, t) for j, t in enumerate(pr_n) if t]
    if not gt_keep or not pr_keep:
        return []

    gt_idx = [i for i, _ in gt_keep]
    pr_idx = [j for j, _ in pr_keep]
    gt_text = [t for _, t in gt_keep]
    pr_text = [t for _, t in pr_keep]

    cost = _ned_matrix(gt_text, pr_text)
    row_ind, col_ind = linear_sum_assignment(cost)

    matches: list[BlockMatch] = []
    matched_gt: set[int] = set()
    matched_pred: set[int] = set()
    for r, c in zip(row_ind, col_ind):
        edit = float(cost[r, c])
        if edit > C.BLOCK_ACCEPT_NED:
            continue
        g, p = gt_text[r], pr_text[c]
        matches.append(BlockMatch(
            gt_index=gt_idx[r],
            pred_indices=(pr_idx[c],),
            edit=edit,
            edit_num=_Lev.distance(g, p),
            upper_len=max(len(g), len(p)),
        ))
        matched_gt.add(r)
        matched_pred.add(c)

    # Fuzzy rescue: an unmatched GT block whose text is embedded in some (also
    # unmatched) pred block within < BLOCK_FUZZY_RESCUE_NED. Scan in index order
    # for determinism; first qualifying pred wins.
    for r in range(len(gt_text)):
        if r in matched_gt:
            continue
        for c in range(len(pr_text)):
            if c in matched_pred:
                continue
            if len(pr_text[c]) > C.BLOCK_FUZZY_MAX_PRED_LEN:
                continue
            d = _sub_gt_fuzzy_matching(pr_text[c], gt_text[r])
            if d < C.BLOCK_FUZZY_RESCUE_NED:
                g = gt_text[r]
                matches.append(BlockMatch(
                    gt_index=gt_idx[r],
                    pred_indices=(pr_idx[c],),
                    edit=d,
                    edit_num=round(d * len(g)),
                    upper_len=len(g),
                ))
                matched_gt.add(r)
                matched_pred.add(c)
                break

    return matches


def block_edit_whole(matches: list[BlockMatch]) -> float:
    """OmniDocBench edit_whole: sum(Edit_num) / sum(upper_len) over matches."""
    denom = sum(m.upper_len for m in matches)
    if denom == 0:
        return 0.0
    return sum(m.edit_num for m in matches) / denom


@dataclass(frozen=True)
class BlockMetrics:
    """Block-matched results for one (candidate, reference) pair.

    ``nid`` is the reorder-robust text similarity in [0, 1]; ``reading_order`` is
    the reading-order disagreement in [0, 1] (0 = same order), or ``None`` when
    it was not measured at all (the matrix-budget fallback below). ``matched`` /
    ``gt_blocks`` / ``pred_blocks`` expose alignment coverage. When the matrix
    budget forces the whole-document fallback, ``reading_order`` is ``None``
    (no per-block alignment was computed, so there is nothing to report: a
    stored ``0.0`` there would read as "perfect order", which is false) and the
    ``matched`` count is 0. Both-empty (``0.0``, no blocks on either side: a
    vacuous perfect agreement) and no-match (``0.0``, blocks exist but none
    aligned: measured disagreement) are genuine measurements and stay ``0.0``.
    """

    nid: float
    reading_order: float | None
    matched: int
    gt_blocks: int
    pred_blocks: int


def block_metrics(candidate: str, reference: str, *, normalize=normalized_text) -> BlockMetrics:
    """Block-match ``candidate`` (pred) against ``reference`` (gt), once.

    Splits both sides into prose blocks, matches them, and derives both the
    block-matched text nid and the reading-order disagreement from a single
    matching pass. Very large papers fall back to the whole-document text_nid
    (see BLOCK_MATRIX_CELL_BUDGET); reading order is not measured there and
    reported as ``None`` (not a synthetic "perfect order" 0.0).
    """
    gt_blocks = split_paragraph_blocks(reference)
    pred_blocks = split_paragraph_blocks(candidate)
    if not gt_blocks and not pred_blocks:
        return BlockMetrics(1.0, 0.0, 0, 0, 0)
    if len(gt_blocks) * len(pred_blocks) > C.BLOCK_MATRIX_CELL_BUDGET:
        nid = text_nid(normalize(candidate), normalize(reference))
        return BlockMetrics(nid, None, 0, len(gt_blocks), len(pred_blocks))
    matches = match_blocks(gt_blocks, pred_blocks, normalize=normalize)
    if not matches:
        return BlockMetrics(0.0, 0.0, 0, len(gt_blocks), len(pred_blocks))
    return BlockMetrics(
        nid=1.0 - block_edit_whole(matches),
        reading_order=reading_order_ned(matches),
        matched=len(matches),
        gt_blocks=len(gt_blocks),
        pred_blocks=len(pred_blocks),
    )


def block_text_nid(candidate: str, reference: str, *, normalize=normalized_text) -> float:
    """Block-matched text similarity in [0, 1] (1.0 = identical).

    ``reference`` is the ground truth, ``candidate`` the prediction. Returns
    1.0 when neither side has prose blocks (identical-empty), and 0.0 when blocks
    exist but none align (no agreement). Otherwise ``1 - block_edit_whole``: the
    reorder-robust replacement for the full-document ``text_nid``.
    """
    return block_metrics(candidate, reference, normalize=normalize).nid


def reading_order_ned(matches: list[BlockMatch]) -> float:
    """Reading-order disagreement in [0, 1] (OmniDocBench get_order_paired).

    0.0 = matched blocks appear in the same relative order in both documents;
    higher = more reordering. Uses block indices as order ids: the GT canonical
    sequence is the sorted gt indices, the pred sequence is those same gt indices
    ordered by their matched pred position. Advisory only: never gates content.
    """
    if not matches:
        return 0.0
    paired = [(m.gt_index, min(m.pred_indices)) for m in matches]
    gt_seq = sorted(g for g, _ in paired)
    pred_seq = [g for g, _ in sorted(paired, key=lambda x: x[1])]
    denom = max(len(gt_seq), len(pred_seq))
    if denom == 0:
        return 0.0
    return _Lev.distance(gt_seq, pred_seq) / denom
