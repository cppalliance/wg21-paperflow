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
- ``teds`` : mean table similarity over order-matched Markdown tables,
- ``mhs``  : heading-hierarchy similarity,
- ``overall`` : mean(nid, teds, mhs),
- ``reading_order`` : block reading-order disagreement, reported as a SEPARATE
  advisory axis and never folded into Overall (reading order does not gate
  content quality, the same separation every benchmark repo keeps).

Text agreement is measured with block matching (OmniDocBench match_quick) rather
than a whole-document edit distance, so a faithful reflow is not penalized. All
metrics are deterministic. This module returns data; the CLI persists the
leaderboard and compares it against a committed baseline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from whisker import constants as C
from whisker.match import block_metrics
from whisker.metrics import mhs, teds

__all__ = ["BenchRow", "aggregate", "run_bench", "table_score"]

_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


@dataclass(frozen=True)
class BenchRow:
    pid: str
    nid: float
    teds: float
    mhs: float
    overall: float
    reading_order: float = 0.0

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "nid": round(self.nid, 4),
            "teds": round(self.teds, 4),
            "mhs": round(self.mhs, 4),
            "overall": round(self.overall, 4),
            "reading_order": round(self.reading_order, 4),
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
        teds_v = _table_score(candidate_md, reference_md)
        mhs_v = mhs(candidate_md, reference_md)
        overall = (nid_v + teds_v + mhs_v) / 3.0
        rows.append(BenchRow(
            pid=pid, nid=nid_v, teds=teds_v, mhs=mhs_v,
            overall=overall, reading_order=bm.reading_order,
        ))
    return sorted(rows, key=lambda r: r.pid)


def aggregate(rows: list[BenchRow]) -> dict:
    """Corpus-level means + a regression check against floors.

    ``reading_order`` is reported as a mean but is never part of ``below_floor``:
    it is an advisory axis, not a quality gate (reading order never gates
    content, see bench module docstring).
    """
    if not rows:
        return {
            "count": 0, "nid": 0.0, "teds": 0.0, "mhs": 0.0, "overall": 0.0,
            "reading_order": 0.0, "below_floor": [],
        }
    n = len(rows)
    mean_nid = sum(r.nid for r in rows) / n
    mean_teds = sum(r.teds for r in rows) / n
    mean_mhs = sum(r.mhs for r in rows) / n
    mean_overall = sum(r.overall for r in rows) / n
    mean_reading_order = sum(r.reading_order for r in rows) / n
    below = sorted(
        r.pid
        for r in rows
        if r.nid < C.NID_FLOOR or r.teds < C.TEDS_FLOOR or r.mhs < C.MHS_FLOOR
    )
    return {
        "count": n,
        "nid": round(mean_nid, 4),
        "teds": round(mean_teds, 4),
        "mhs": round(mean_mhs, 4),
        "overall": round(mean_overall, 4),
        "reading_order": round(mean_reading_order, 4),
        "below_floor": below,
    }
