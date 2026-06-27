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

- ``nid``  : block-matched text similarity (whisker.match.block_text_nid),
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
  content quality, the same separation every benchmark repo keeps).
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

import re
from dataclasses import dataclass

import grits

from whisker import constants as C
from whisker.match import block_metrics
from whisker.metrics import content_recall, has_headings, mhs, teds

__all__ = ["BenchRow", "aggregate", "run_bench", "table_score"]

_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


@dataclass(frozen=True)
class BenchRow:
    pid: str
    nid: float
    teds: float | None
    mhs: float | None
    overall: float
    content_recall: float = 1.0
    reading_order: float = 0.0
    # ADVISORY (like reading_order): GriTS-Con cell-content F1, a complementary
    # table signal to teds. Reported and stored but never gated until it has its
    # own calibration; None when the reference has no tables.
    grits_con: float | None = None

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
            "reading_order": round(self.reading_order, 4),
            "grits_con": None if self.grits_con is None else round(self.grits_con, 4),
        }


def _split_cells(line: str) -> list[str]:
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    return [c.strip() for c in body.split("|")]


def _extract_md_tables(md_text: str) -> list[str]:
    """Return each Markdown pipe table as a minimal HTML <table> string.

    A table is a header row, a separator row, then zero or more body rows.
    Fenced code is skipped so pipes inside code do not masquerade as tables.
    """
    lines = md_text.splitlines()
    in_fence = False
    tables: list[str] = []
    i = 0
    while i < len(lines):
        if _FENCE_RE.match(lines[i]):
            in_fence = not in_fence
            i += 1
            continue
        if in_fence:
            i += 1
            continue
        is_sep = (
            i + 1 < len(lines)
            and "|" in lines[i + 1]
            and _TABLE_SEP_RE.match(lines[i + 1])
        )
        if "|" in lines[i] and is_sep:
            header = _split_cells(lines[i])
            rows = [header]
            j = i + 2
            while j < len(lines) and "|" in lines[j] and lines[j].strip():
                rows.append(_split_cells(lines[j]))
                j += 1
            tables.append(_rows_to_html(rows))
            i = j
            continue
        i += 1
    return tables


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
        # overall is the mean of ELIGIBLE structural axes only (nid is always
        # eligible). An ineligible teds/mhs no longer inflates it toward 1.0.
        # grits_con is advisory and never folded into overall.
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
    content, see bench module docstring).
    """
    if not rows:
        return {
            "count": 0, "nid": 0.0, "teds": None, "mhs": None, "overall": 0.0,
            "content_recall": 0.0, "reading_order": 0.0, "grits_con": None,
            "eligible_counts": {
                "nid": 0, "teds": 0, "mhs": 0, "content_recall": 0, "grits_con": 0,
            },
            "below_floor": [],
        }
    n = len(rows)
    teds_vals = [r.teds for r in rows if r.teds is not None]
    mhs_vals = [r.mhs for r in rows if r.mhs is not None]
    grits_vals = [r.grits_con for r in rows if r.grits_con is not None]
    mean_nid = sum(r.nid for r in rows) / n
    mean_teds = sum(teds_vals) / len(teds_vals) if teds_vals else None
    mean_mhs = sum(mhs_vals) / len(mhs_vals) if mhs_vals else None
    mean_grits = sum(grits_vals) / len(grits_vals) if grits_vals else None
    mean_overall = sum(r.overall for r in rows) / n
    mean_content_recall = sum(r.content_recall for r in rows) / n
    mean_reading_order = sum(r.reading_order for r in rows) / n
    below = sorted(
        r.pid
        for r in rows
        if r.nid < C.NID_FLOOR
        or (r.teds is not None and r.teds < C.TEDS_FLOOR)
        or (r.mhs is not None and r.mhs < C.MHS_FLOOR)
        or r.content_recall < C.CONTENT_RECALL_FLOOR
    )
    return {
        "count": n,
        "nid": round(mean_nid, 4),
        "teds": None if mean_teds is None else round(mean_teds, 4),
        "mhs": None if mean_mhs is None else round(mean_mhs, 4),
        "overall": round(mean_overall, 4),
        "content_recall": round(mean_content_recall, 4),
        "reading_order": round(mean_reading_order, 4),
        "grits_con": None if mean_grits is None else round(mean_grits, 4),
        "eligible_counts": {
            "nid": n,
            "teds": len(teds_vals),
            "mhs": len(mhs_vals),
            "content_recall": n,
            "grits_con": len(grits_vals),
        },
        "below_floor": below,
    }
