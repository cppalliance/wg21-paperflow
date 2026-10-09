#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Run-to-run delta between two det-lane ``report.json`` payloads.

The det lane (``whisker [PID...]`` / ``whisker --all``) overwrites its sidecars
and ``report.json`` every run, so an operator editing the tomd converter has no
way to answer "did my change make papers better or worse, and which other
papers regressed collaterally". ``compute_delta`` closes that gap by comparing
a prior ``report.json`` (the baseline) against the current one, per paper.

Classification per pid, verdict ordering (``pass`` < ``review`` < ``fail``) is
primary:

- a worse verdict is a regression, a better verdict is an improvement;
- an unchanged verdict falls back to the watched metrics
  (``unigram_coverage``, ``coverage``, ``qa_score``, ``ref_nid``): a drop
  greater than ``DELTA_METRIC_EPSILON`` is a regression, a gain greater than
  it is an improvement, otherwise the paper is unchanged;
- a metric that is ``None`` on either side (e.g. ``ref_*`` under
  ``--no-reference``) is not comparable and is never treated as a regression;
- a verdict listed in ``verdict_sentinels`` on either side means the row
  carries no verdict at all rather than a real tier, so the whole row is not
  comparable and is never treated as a regression;
- a pid present only in the current report is ``new``; only in the prior
  report is ``gone``.

Pure library: this module returns data (``DeltaResult``/``DeltaFinding``). The
CLI (``whisker delta`` in ``__main__.py``) reads the two report.json files,
calls ``compute_delta``, and owns all persistence, rendering, and exit codes.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from whisker import constants as C
from whisker.det.score import VERDICT_FAIL, VERDICT_PASS, VERDICT_REVIEW

__all__ = [
    "DELTA_REPORT_KIND",
    "STATUS_GONE",
    "STATUS_IMPROVED",
    "STATUS_NEW",
    "STATUS_REGRESSED",
    "STATUS_UNCHANGED",
    "DeltaFinding",
    "DeltaResult",
    "MetricDelta",
    "compute_delta",
]

DELTA_REPORT_KIND = "whisker-delta-report"

STATUS_REGRESSED = "regressed"
STATUS_IMPROVED = "improved"
STATUS_UNCHANGED = "unchanged"
STATUS_NEW = "new"
STATUS_GONE = "gone"

_FAILING_STATUSES = frozenset({STATUS_REGRESSED})

# The metrics watched for a same-verdict comparison. Names match the exact
# WhiskerResult.to_dict() / report.json fields (see score.py, report.py):
# note the sidecar field is `qa_score`, not `qa`.
_WATCHED_METRICS = ("unigram_coverage", "coverage", "qa_score", "ref_nid")

# Unknown verdicts (should not occur; defensive only) rank as REVIEW so a
# corrupt/foreign report entry cannot silently sort as the best or worst case.
_VERDICT_RANK = {VERDICT_PASS: 0, VERDICT_REVIEW: 1, VERDICT_FAIL: 2}
_UNKNOWN_VERDICT_RANK = _VERDICT_RANK[VERDICT_REVIEW]


def _rank(verdict: str) -> int:
    return _VERDICT_RANK.get(verdict, _UNKNOWN_VERDICT_RANK)


@dataclass(frozen=True)
class MetricDelta:
    """One watched metric's value on both sides of the comparison.

    ``delta`` is ``curr - prev`` and is ``None`` whenever either side is
    missing/null, so an ineligible metric (e.g. ``ref_nid`` under
    ``--no-reference``) is never mistaken for a regression.
    """

    prev: float | None
    curr: float | None
    delta: float | None

    def to_dict(self) -> dict:
        return {
            "prev": self.prev,
            "curr": self.curr,
            "delta": round(self.delta, 4) if self.delta is not None else None,
        }


@dataclass(frozen=True)
class DeltaFinding:
    """One pid's verdict across the two reports.

    ``severity`` is a non-negative display-ordering weight (verdict
    transitions always outrank a same-verdict metric wobble); it is not a
    scoring value and carries no meaning beyond sorting worst-first.
    """

    pid: str
    status: str
    prev_verdict: str | None
    curr_verdict: str | None
    metrics: dict[str, MetricDelta] = field(default_factory=dict)
    reason: str = ""
    severity: float = 0.0

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "status": self.status,
            "prev_verdict": self.prev_verdict,
            "curr_verdict": self.curr_verdict,
            "metrics": {
                name: d.to_dict() for name, d in sorted(self.metrics.items())
            },
            "reason": self.reason,
            "severity": round(self.severity, 4),
        }


@dataclass(frozen=True)
class DeltaResult:
    """Delta over the full pid union of two reports, pid-sorted throughout."""

    findings: list[DeltaFinding]
    prev_count: int
    curr_count: int

    @property
    def any_regressed(self) -> bool:
        return any(f.status in _FAILING_STATUSES for f in self.findings)

    def _by_status(self, status: str) -> list[DeltaFinding]:
        # `findings` is built pid-sorted in compute_delta, so every filtered
        # view below stays pid-sorted for free (deterministic output).
        return [f for f in self.findings if f.status == status]

    def regressed(self) -> list[DeltaFinding]:
        return self._by_status(STATUS_REGRESSED)

    def improved(self) -> list[DeltaFinding]:
        return self._by_status(STATUS_IMPROVED)

    def unchanged(self) -> list[DeltaFinding]:
        return self._by_status(STATUS_UNCHANGED)

    def new_papers(self) -> list[DeltaFinding]:
        return self._by_status(STATUS_NEW)

    def gone_papers(self) -> list[DeltaFinding]:
        return self._by_status(STATUS_GONE)

    def to_dict(self) -> dict:
        counts: dict[str, int] = {}
        for f in self.findings:
            counts[f.status] = counts.get(f.status, 0) + 1
        return {
            "schema_version": C.WHISKER_SCHEMA_VERSION,
            "kind": DELTA_REPORT_KIND,
            "prev_count": self.prev_count,
            "curr_count": self.curr_count,
            "any_regressed": self.any_regressed,
            "status_counts": dict(sorted(counts.items())),
            "findings": [f.to_dict() for f in self.findings],
        }


def _require_results(
    report: dict | list, label: str, results_key: str | None,
) -> dict[str, dict]:
    """Validate a report payload and return its results, keyed by pid.

    ``results_key`` names the key wrapping the list inside ``report`` (the
    det-lane ``report.json`` shape); when ``None``, ``report`` IS the results
    list directly (the LLM lane's bare-list ``report-merged.json`` shape).
    Raises ``ValueError`` on anything malformed so the CLI can turn it into a
    clean operational-error exit rather than an unhandled traceback.
    """
    if results_key is None:
        if not isinstance(report, list):
            raise ValueError(f"{label} must be a JSON list (results_key=None)")
        results = report
    else:
        if not isinstance(report, dict):
            raise ValueError(f"{label} must be a JSON object")
        results = report.get(results_key)
        if not isinstance(results, list):
            raise ValueError(f"{label} is missing a {results_key!r} list")
    by_pid: dict[str, dict] = {}
    for entry in results:
        if not isinstance(entry, dict) or "pid" not in entry:
            raise ValueError(f"{label} contains a result with no 'pid'")
        pid = entry["pid"]
        if pid in by_pid:
            raise ValueError(f"{label} contains duplicate pid {pid!r}")
        by_pid[pid] = entry
    return by_pid


# Metric deltas are rounded to this precision before any epsilon comparison,
# the same fixed-precision discipline whisker.det.guard uses (_NDIGITS): it makes
# the epsilon boundary deterministic instead of at the mercy of binary float
# representation (0.90 - 0.89 != 0.01 exactly in IEEE-754).
_DELTA_NDIGITS = 4


def _metric_deltas(
    prev: dict, curr: dict, watched_metrics: Sequence[str],
) -> dict[str, MetricDelta]:
    deltas: dict[str, MetricDelta] = {}
    for name in watched_metrics:
        prev_val = prev.get(name)
        curr_val = curr.get(name)
        delta = (
            round(curr_val - prev_val, _DELTA_NDIGITS)
            if prev_val is not None and curr_val is not None
            else None
        )
        deltas[name] = MetricDelta(prev=prev_val, curr=curr_val, delta=delta)
    return deltas


def _metric_reason(deltas: dict[str, MetricDelta], *, worse: bool) -> str:
    """One clause per metric that crossed the epsilon in the given direction."""
    parts = []
    for name in sorted(deltas):
        d = deltas[name]
        if d.delta is None:
            continue
        crossed = d.delta < -C.DELTA_METRIC_EPSILON if worse else d.delta > C.DELTA_METRIC_EPSILON
        if crossed:
            parts.append(f"{name} {d.prev:.4f} -> {d.curr:.4f}")
    return "; ".join(parts)


def _classify_present(
    pid: str, prev: dict, curr: dict, verdict_field: str,
    watched_metrics: Sequence[str], verdict_sentinels: frozenset[str | None],
) -> DeltaFinding:
    prev_verdict = prev.get(verdict_field)
    curr_verdict = curr.get(verdict_field)
    deltas = _metric_deltas(prev, curr, watched_metrics)

    # A sentinel means "this row has no verdict", not "this row is at the
    # review tier". Ranking it would manufacture a regression (or, worse, an
    # improvement that hides a real fail) out of a missing sidecar, and the
    # metrics that travel with it are equally synthetic, so the entire row is
    # withheld from classification rather than only its verdict.
    if prev_verdict in verdict_sentinels or curr_verdict in verdict_sentinels:
        return DeltaFinding(
            pid=pid, status=STATUS_UNCHANGED, prev_verdict=prev_verdict,
            curr_verdict=curr_verdict, metrics=deltas,
            reason=f"not comparable ({prev_verdict} -> {curr_verdict})",
        )

    rank_diff = _rank(curr_verdict) - _rank(prev_verdict)
    if rank_diff != 0:
        status = STATUS_REGRESSED if rank_diff > 0 else STATUS_IMPROVED
        severity = abs(rank_diff) * C.DELTA_VERDICT_SEVERITY_WEIGHT
        reason = f"verdict {prev_verdict} -> {curr_verdict}"
        return DeltaFinding(
            pid=pid, status=status, prev_verdict=prev_verdict,
            curr_verdict=curr_verdict, metrics=deltas, reason=reason,
            severity=severity,
        )

    worst_drop = max(
        (-d.delta for d in deltas.values() if d.delta is not None and d.delta < 0),
        default=0.0,
    )
    best_gain = max(
        (d.delta for d in deltas.values() if d.delta is not None and d.delta > 0),
        default=0.0,
    )
    if worst_drop > C.DELTA_METRIC_EPSILON:
        return DeltaFinding(
            pid=pid, status=STATUS_REGRESSED, prev_verdict=prev_verdict,
            curr_verdict=curr_verdict, metrics=deltas,
            reason=_metric_reason(deltas, worse=True), severity=worst_drop,
        )
    if best_gain > C.DELTA_METRIC_EPSILON:
        return DeltaFinding(
            pid=pid, status=STATUS_IMPROVED, prev_verdict=prev_verdict,
            curr_verdict=curr_verdict, metrics=deltas,
            reason=_metric_reason(deltas, worse=False), severity=best_gain,
        )
    return DeltaFinding(
        pid=pid, status=STATUS_UNCHANGED, prev_verdict=prev_verdict,
        curr_verdict=curr_verdict, metrics=deltas, reason="no change",
    )


def compute_delta(
    prev_report: dict | list,
    curr_report: dict | list,
    *,
    verdict_field: str = "verdict",
    watched_metrics: Sequence[str] | None = None,
    results_key: str | None = "results",
    verdict_sentinels: Sequence[str | None] = (),
) -> DeltaResult:
    """Compare two report payloads, per paper.

    ``prev_report`` is the prior snapshot, ``curr_report`` is the current one.
    With no keyword arguments this is the original det-lane contract:
    ``report.json``-shaped payloads (a ``{"results": [...]}`` object),
    verdicts read from each row's ``"verdict"`` field, and the metrics in
    ``_WATCHED_METRICS``.

    Keyword arguments generalize the comparison to other report shapes (e.g.
    the LLM lane's bare-list ``report-merged.json``):

    - ``verdict_field``: the key to read each row's verdict from.
    - ``watched_metrics``: metric names diffed on a same-verdict row; ``None``
      (the default) uses ``_WATCHED_METRICS``. Pass ``()`` for a verdict-only
      comparison (no metric fallback).
    - ``results_key``: the key wrapping the row list inside the report dict;
      ``None`` means the report argument IS the row list directly.
    - ``verdict_sentinels``: verdict values that mean "no verdict available"
      rather than a real tier. A row carrying one on either side classifies
      as ``unchanged`` (never a regression or improvement). ``None`` is a
      legal member and covers a row missing the verdict field entirely. The
      det lane needs none, because ``score.py`` only ever emits
      pass/review/fail; the LLM lane's merged report needs ``"?"``
      (missing/malformed det sidecar) and ``"-"`` (paper with no LLM data),
      both produced by ``fusion_report._verdict``'s defaults.

    Raises ``ValueError`` if either payload is malformed for the requested
    shape (missing results list/key, a row missing 'pid', or a duplicate
    pid); the caller (the CLI) turns that into an operational-error exit.
    """
    metrics = tuple(watched_metrics) if watched_metrics is not None else _WATCHED_METRICS
    sentinels = frozenset(verdict_sentinels)
    prev_results = _require_results(prev_report, "prev_report", results_key)
    curr_results = _require_results(curr_report, "curr_report", results_key)

    findings: list[DeltaFinding] = []
    for pid in sorted(set(prev_results) | set(curr_results)):
        prev = prev_results.get(pid)
        curr = curr_results.get(pid)
        if prev is None:
            findings.append(DeltaFinding(
                pid=pid, status=STATUS_NEW, prev_verdict=None,
                curr_verdict=curr.get(verdict_field),
                reason=f"new paper (verdict {curr.get(verdict_field)})",
            ))
        elif curr is None:
            findings.append(DeltaFinding(
                pid=pid, status=STATUS_GONE, prev_verdict=prev.get(verdict_field),
                curr_verdict=None,
                reason=f"removed (was {prev.get(verdict_field)})",
            ))
        else:
            findings.append(_classify_present(
                pid, prev, curr, verdict_field, metrics, sentinels,
            ))

    return DeltaResult(
        findings=findings, prev_count=len(prev_results), curr_count=len(curr_results),
    )
