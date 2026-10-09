#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Benchmark a candidate conversion against labeled ground-truth Markdown.

Unlike the per-paper verdict (no ground truth), the benchmark requires a
reference Markdown per paper and reports the structural-fidelity axes plus an
unweighted Overall:

- ``nid``  : block-matched text similarity (whisker.det.match.block_text_nid),
- ``teds`` : mean table similarity over order-matched Markdown tables, or
  ``None`` when the reference has no tables (ineligible, not a synthetic 1.0),
- ``mhs``  : heading-hierarchy similarity, or ``None`` when the reference has no
  headings (ineligible),
- ``overall`` : mean of the ELIGIBLE structural axes only (nid plus whichever of
  teds/mhs the reference exercises), so a table-less / heading-less paper is not
  inflated toward 1.0 (opendataloader-pdf null-eligibility rule),
- ``content_recall`` : multiset bag-of-words recall of GT content present in the
  candidate (whisker.metrics.content_recall). A first-class gate but deliberately
  NOT folded into Overall: it catches dropped sections that edit distance hides,
  and (per Nougat/Unstructured) missing-content strata must not be averaged into
  one number.
- ``reading_order`` : block reading-order disagreement, reported as a SEPARATE
  advisory axis and never folded into Overall (reading order does not gate
  content quality, the same separation every benchmark repo keeps). ``None``
  when the matrix-budget fallback skipped block matching entirely (not
  measured, null-eligible like ``teds``/``mhs``), never a synthetic 0.0
  ("perfect order").
- ``grits_con`` : GriTS-Con cell-content F1 (grits-metric), a complementary
  table signal to ``teds`` that catches localized cell / merge-split errors a
  tree-edit distance smooths over. ADVISORY only (stored and reported, never
  gated) until it has its own calibration; ``None`` when the reference has no
  tables.

Text agreement is measured with block matching (OmniDocBench match_quick) rather
than a whole-document edit distance, so a faithful reflow is not penalized. All
metrics are deterministic. This module returns data; the CLI persists the
leaderboard and compares it against a committed baseline.
"""

from __future__ import annotations

from dataclasses import dataclass

import grits

from whisker import constants as C
from whisker.det.canonical import canonicalize_conventions
from whisker.det.compare import align_documents
from whisker.det.match import block_metrics
from whisker.det.structural import count_markers
from whisker.metrics import (
    content_recall,
    has_headings,
    heading_level_parity,
    mhs,
    teds,
)
from whisker.tables import parse_html_tables, parse_pipe_tables

__all__ = ["BenchRow", "aggregate", "run_bench", "table_score"]



@dataclass(frozen=True)
class BenchRow:
    pid: str
    nid: float
    teds: float | None
    mhs: float | None
    overall: float
    content_recall: float = 1.0
    # ADVISORY: block reading-order disagreement. None when the matrix-budget
    # fallback skipped block matching (not measured, null-eligible like
    # teds/mhs), never a synthetic 0.0 ("perfect order").
    reading_order: float | None = 0.0
    # ADVISORY (like reading_order): GriTS-Con cell-content F1, a complementary
    # table signal to teds. Reported and stored but never gated until it has its
    # own calibration; None when the reference has no tables.
    grits_con: float | None = None
    # ADVISORY: exact block-pair match share computed on convention-canonicalized
    # text. Separates tomd/Marker much more sharply than NID.
    block_agreement: float | None = None
    # ADVISORY (promoted to hard gate on labeled GT): per marker-class
    # zero-vs-many parity. 1.0 = no categorical marker loss. None when
    # reference has no structural markers at all.
    structural_parity: float | None = None
    # ADVISORY: fraction of positionally aligned headings whose levels match.
    # None when the reference has no headings.
    heading_level_parity: float | None = None

    def to_dict(self) -> dict:
        # teds/mhs are ``None`` (-> JSON null) when the reference lacks that
        # modality (no tables / no headings): the axis is ineligible, not a
        # synthetic perfect score. nid and content_recall always apply (text).
        return {
            "pid": self.pid,
            "nid": round(self.nid, 4),
            "teds": None if self.teds is None else round(self.teds, 4),
            "mhs": None if self.mhs is None else round(self.mhs, 4),
            "overall": round(self.overall, 4),
            "content_recall": round(self.content_recall, 4),
            "reading_order": (
                None if self.reading_order is None else round(self.reading_order, 4)
            ),
            "grits_con": None if self.grits_con is None else round(self.grits_con, 4),
            "block_agreement": (
                None if self.block_agreement is None
                else round(self.block_agreement, 4)
            ),
            "structural_parity": (
                None if self.structural_parity is None
                else round(self.structural_parity, 4)
            ),
            "heading_level_parity": (
                None if self.heading_level_parity is None
                else round(self.heading_level_parity, 4)
            ),
        }


def _extract_md_tables(md_text: str) -> list[str]:
    """Return each Markdown table as a minimal HTML <table> string.

    Uses the shared pipe and HTML scanners so HTML-only references are not
    silently null-eligible for TEDS. Each grid is converted to the
    OmniDocBench-normalized HTML that TEDS expects.
    """
    grids = parse_pipe_tables(md_text) + parse_html_tables(md_text)
    return [_rows_to_html(rows) for rows in grids]


def _rows_to_html(rows: list[list[str]]) -> str:
    """Render extracted markdown rows as OmniDocBench-normalized table HTML.

    Every cell is a ``<td>`` (PubTabNet's TEDS drops ``<th>`` cell text, so a
    header row emitted as ``<th>`` would lose its content), wrapped in
    ``<html><body><table border="1">`` so ``TEDS.evaluate``'s ``body/table``
    xpath matches. Mirrors OmniDocBench ``table_structure_post_process``.
    """
    inner = []
    for row in rows:
        cells = "".join(f"<td>{c}</td>" for c in row)
        inner.append(f"<tr>{cells}</tr>")
    return f'<html><body><table border="1" >{"".join(inner)}</table></body></html>'


def _table_score(candidate_md: str, reference_md: str) -> float:
    """Mean TEDS over order-matched tables. 1.0 if neither side has tables."""
    cand = _extract_md_tables(candidate_md)
    ref = _extract_md_tables(reference_md)
    if not cand and not ref:
        return 1.0
    pairs = max(len(cand), len(ref))
    total = 0.0
    empty = "<table></table>"
    for k in range(pairs):
        a = cand[k] if k < len(cand) else empty
        b = ref[k] if k < len(ref) else empty
        total += teds(a, b)
    return total / pairs


def table_score(candidate_md: str, reference_md: str) -> float:
    """Mean TEDS over order-matched markdown tables; 1.0 if neither side has any.

    Public wrapper over the table-pairing logic so the per-paper reference path
    in score.py can score tables without re-running the full text benchmark.
    """
    return _table_score(candidate_md, reference_md)


# GriTS html_to_grids returns None on an unparseable fragment; an empty grid is
# the neutral stand-in (no cells matched) so a missing/garbled table scores 0.
_GRITS_EMPTY_GRID: list[list[str]] = [[]]


def _grits_con_score(candidate_md: str, reference_md: str) -> float | None:
    """Mean GriTS-Con (cell-content F1) over order-matched tables.

    Complementary to TEDS: GriTS scores a cell-grid F1 (precision/recall over
    matched cells), catching merge/split and localized cell errors a tree-edit
    distance can smooth over. ADVISORY only (never gates): returned for
    reporting alongside ``teds``. ``None`` when the reference has no tables
    (same GT-driven eligibility as ``teds``). Order-matched table pairing
    mirrors ``_table_score``; a dropped candidate table pairs against an empty
    grid and scores 0. Deterministic (grits uses numpy/scipy/pylcs, no RNG).
    """
    ref = _extract_md_tables(reference_md)
    if not ref:
        return None
    cand = _extract_md_tables(candidate_md)
    pairs = max(len(cand), len(ref))
    total = 0.0
    for k in range(pairs):
        true_grids = grits.html_to_grids(ref[k]) if k < len(ref) else None
        pred_grids = grits.html_to_grids(cand[k]) if k < len(cand) else None
        true_con = true_grids["con"] if true_grids else _GRITS_EMPTY_GRID
        pred_con = pred_grids["con"] if pred_grids else _GRITS_EMPTY_GRID
        # grits_con returns (precision, recall, f_score); the F1 is the axis.
        _, _, f_score = grits.grits_con(true_con, pred_con)
        total += f_score
    return total / pairs


def _block_agreement(candidate_md: str, reference_md: str) -> float:
    """Exact block-pair match share on convention-canonicalized text."""
    cand_canon = canonicalize_conventions(candidate_md)
    ref_canon = canonicalize_conventions(reference_md)
    aligned = align_documents(
        cand_canon, ref_canon, left_label="candidate", right_label="reference",
    )
    if not aligned.pairs:
        return 1.0
    equal = sum(
        1
        for pair in aligned.pairs
        if (pair.status.value if hasattr(pair.status, "value") else str(pair.status))
        == "equal"
    )
    return equal / len(aligned.pairs)


def _structural_parity(
    candidate_md: str, reference_md: str,
) -> float | None:
    """Per marker-class zero-vs-many parity between candidate and reference.

    Returns the fraction of reference-eligible marker classes (those with at
    least ``STRUCTURAL_PARITY_MIN_REFERENCE_COUNT`` in the reference) where the
    candidate also has a non-zero count. 1.0 means no categorical marker loss.
    ``None`` when the reference has no eligible marker classes.
    """
    cand_counts = count_markers(candidate_md)
    ref_counts = count_markers(reference_md)
    eligible_classes = [
        cls for cls, cnt in ref_counts.items()
        if cnt >= C.STRUCTURAL_PARITY_MIN_REFERENCE_COUNT
    ]
    if not eligible_classes:
        return None
    passed = sum(1 for cls in eligible_classes if cand_counts.get(cls, 0) > 0)
    return passed / len(eligible_classes)


def run_bench(pairs: list[tuple[str, str, str]]) -> list[BenchRow]:
    """Score (pid, candidate_md, reference_md) triples. Sorted by pid."""
    rows: list[BenchRow] = []
    for pid, candidate_md, reference_md in pairs:
        # Block-matched text agreement (OmniDocBench match_quick): blocks are
        # normalized and aligned before the edit distance, so a faithful reflow
        # is not penalized and reading order falls out as a separate axis. The
        # candidate is the prediction, the reference the ground truth.
        bm = block_metrics(candidate_md, reference_md)
        nid_v = bm.nid
        # GT-driven eligibility (opendataloader-pdf null rule): an axis the
        # reference cannot exercise (no tables / no headings) is None, not a
        # synthetic 1.0. Candidate-only modality LOSS is still caught: when the
        # reference HAS tables/headings the axis is eligible and the pairing
        # logic tanks the score for dropped tables / collapsed hierarchy.
        teds_v = (
            _table_score(candidate_md, reference_md)
            if _extract_md_tables(reference_md)
            else None
        )
        mhs_v = mhs(candidate_md, reference_md) if has_headings(reference_md) else None
        # content_recall is a SEPARATE missing-content axis, deliberately NOT
        # folded into overall (Nougat/Unstructured keep strata separate); a
        # converter can reflow faithfully (high nid) yet drop a section (low
        # recall), so the two gate independently.
        recall_v = content_recall(candidate_md, reference_md)
        grits_con_v = _grits_con_score(candidate_md, reference_md)
        block_agreement_v = _block_agreement(candidate_md, reference_md)
        structural_parity_v = _structural_parity(candidate_md, reference_md)
        hlp_v = heading_level_parity(candidate_md, reference_md)
        # overall is the mean of ELIGIBLE structural axes only (nid is always
        # eligible). An ineligible teds/mhs no longer inflates it toward 1.0.
        # grits_con, block_agreement, structural_parity, heading_level_parity
        # are advisory and never folded into overall.
        parts = [nid_v]
        if teds_v is not None:
            parts.append(teds_v)
        if mhs_v is not None:
            parts.append(mhs_v)
        overall = sum(parts) / len(parts)
        rows.append(BenchRow(
            pid=pid, nid=nid_v, teds=teds_v, mhs=mhs_v,
            overall=overall, content_recall=recall_v,
            reading_order=bm.reading_order, grits_con=grits_con_v,
            block_agreement=block_agreement_v,
            structural_parity=structural_parity_v,
            heading_level_parity=hlp_v,
        ))
    return sorted(rows, key=lambda r: r.pid)


def aggregate(rows: list[BenchRow]) -> dict:
    """Corpus-level means + a regression check against floors.

    Eligibility-weighted means (opendataloader-pdf): ``teds``/``mhs`` average
    ONLY over rows where the axis is eligible (not None), so table-less and
    heading-less papers do not inflate the corpus mean with synthetic 1.0s. The
    denominators are published in ``eligible_counts`` so a reviewer sees how many
    papers each axis was scored on. A mean with no eligible rows is ``None``.

    ``reading_order`` is reported as a mean but is never part of ``below_floor``:
    it is an advisory axis, not a quality gate (reading order never gates
    content, see bench module docstring). It now shares the eligibility-weighted
    treatment above: a row whose reading order was not measured (matrix-budget
    fallback) is excluded from the mean, not averaged in as a synthetic 0.0.
    """
    if not rows:
        return {
            "count": 0, "nid": 0.0, "teds": None, "mhs": None, "overall": 0.0,
            "content_recall": 0.0, "reading_order": None, "grits_con": None,
            "block_agreement": None, "structural_parity": None,
            "heading_level_parity": None,
            "eligible_counts": {
                "nid": 0, "teds": 0, "mhs": 0, "content_recall": 0,
                "reading_order": 0,
                "grits_con": 0, "block_agreement": 0,
                "structural_parity": 0, "heading_level_parity": 0,
            },
            "below_floor": [],
        }
    n = len(rows)
    teds_vals = [r.teds for r in rows if r.teds is not None]
    mhs_vals = [r.mhs for r in rows if r.mhs is not None]
    reading_order_vals = [r.reading_order for r in rows if r.reading_order is not None]
    grits_vals = [r.grits_con for r in rows if r.grits_con is not None]
    ba_vals = [r.block_agreement for r in rows if r.block_agreement is not None]
    sp_vals = [r.structural_parity for r in rows if r.structural_parity is not None]
    hlp_vals = [r.heading_level_parity for r in rows if r.heading_level_parity is not None]
    mean_nid = sum(r.nid for r in rows) / n
    mean_teds = sum(teds_vals) / len(teds_vals) if teds_vals else None
    mean_mhs = sum(mhs_vals) / len(mhs_vals) if mhs_vals else None
    mean_reading_order = (
        sum(reading_order_vals) / len(reading_order_vals) if reading_order_vals else None
    )
    mean_grits = sum(grits_vals) / len(grits_vals) if grits_vals else None
    mean_ba = sum(ba_vals) / len(ba_vals) if ba_vals else None
    mean_sp = sum(sp_vals) / len(sp_vals) if sp_vals else None
    mean_hlp = sum(hlp_vals) / len(hlp_vals) if hlp_vals else None
    mean_overall = sum(r.overall for r in rows) / n
    mean_content_recall = sum(r.content_recall for r in rows) / n
    below = sorted(
        r.pid
        for r in rows
        if r.nid < C.NID_FLOOR
        or (r.teds is not None and r.teds < C.TEDS_FLOOR)
        or (r.mhs is not None and r.mhs < C.MHS_FLOOR)
        or r.content_recall < C.CONTENT_RECALL_FLOOR
        or (r.structural_parity is not None and r.structural_parity < 1.0)
    )
    return {
        "count": n,
        "nid": round(mean_nid, 4),
        "teds": None if mean_teds is None else round(mean_teds, 4),
        "mhs": None if mean_mhs is None else round(mean_mhs, 4),
        "overall": round(mean_overall, 4),
        "content_recall": round(mean_content_recall, 4),
        "reading_order": (
            None if mean_reading_order is None else round(mean_reading_order, 4)
        ),
        "grits_con": None if mean_grits is None else round(mean_grits, 4),
        "block_agreement": None if mean_ba is None else round(mean_ba, 4),
        "structural_parity": None if mean_sp is None else round(mean_sp, 4),
        "heading_level_parity": None if mean_hlp is None else round(mean_hlp, 4),
        "eligible_counts": {
            "nid": n,
            "teds": len(teds_vals),
            "mhs": len(mhs_vals),
            "content_recall": n,
            "reading_order": len(reading_order_vals),
            "grits_con": len(grits_vals),
            "block_agreement": len(ba_vals),
            "structural_parity": len(sp_vals),
            "heading_level_parity": len(hlp_vals),
        },
        "below_floor": below,
    }
