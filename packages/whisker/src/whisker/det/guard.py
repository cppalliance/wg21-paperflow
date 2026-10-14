#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Per-paper, per-axis regression guard against a committed baseline.

``whisker bench`` reports corpus MEANS and only compares the mean ``overall``
to a baseline, so one paper can collapse while the mean holds: that is the exact
"no collateral damage" blind spot this guard closes. It diffs EACH paper's EACH
axis (``nid``/``teds``/``mhs``/``content_recall``/``overall``) against a committed
baseline and fails on any per-paper regression.

The design fuses the highest-value practices found across 28 document-conversion
projects (see ``notes/cross-repo-qa-research.md``) and was hardened against a
second adversarial pass (see ``notes/redteam-synthesis.md``):

- metrics-as-snapshots committed per item (unstructured),
- per-axis absolute floors as a backstop when no baseline entry exists (marker,
  opendataloader-pdf ``thresholds.json``),
- monotonic known-bad baselines: a paper already weak in the baseline is not
  re-flagged unless it gets WORSE or crosses a floor downward (tabula-java
  ``expectedFailure``),
- an explicit refresh ritual (the CLI ``--update`` flag; pandoc ``--accept``,
  go-html-to-markdown ``-update``, html-to-markdown ``--bless``),
- the contract travels WITH the data: the slack and floors used to judge a run
  are read from the committed baseline, not from live constants, so a baseline
  remains reproducible even if ``constants.py`` later moves (pandoc/grobid),
- the producer toolchain travels too: ``tool_versions`` (tomd/whisker) is
  stamped at ``--update`` time and a mismatch hard-fails before any per-paper
  diff, so a dependency bump cannot silently pass against wrong-era metrics
  (PyMuPDF version-keyed goldens).

An ineligible axis (``teds``/``mhs`` stored as ``null`` because the reference has
no tables/headings) is SKIPPED for both the floor and the regression check, never
treated as a corrupt value (the opendataloader-pdf null-eligibility rule). Only a
real NaN/inf is ``STATUS_INVALID``.

Reading order is carried for reporting but never gates (advisory axis, the same
separation every benchmark repo keeps; see ``bench`` module docstring).

This module returns data only; the CLI persists the baseline and owns exit codes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version

from whisker import constants as C
from whisker.det.bench import BenchRow

__all__ = [
    "GUARD_BASELINE_KIND",
    "GuardFinding",
    "GuardReport",
    "baseline_from_rows",
    "collect_tool_versions",
    "diff_rows",
]

GUARD_BASELINE_KIND = "whisker-guard-baseline"

# Producer packages whose version is stamped into every baseline. Kept small and
# named (minimalism): tomd produces the candidate markdown, whisker produces the
# scores. A bump in either invalidates the stored rows, so a mismatch hard-fails
# the gate (PyMuPDF's "never diff against a wrong-era golden" lesson). Transitive
# deps (numpy/scipy/lxml) rarely change markdown output and are deliberately not
# snapshotted; extend this tuple with evidence, not speculatively.
_TOOL_VERSION_PACKAGES = ("tomd", "whisker")


def collect_tool_versions() -> dict[str, str]:
    """Return ``{package: installed version}`` for the producer toolchain.

    Uses stdlib ``importlib.metadata`` (no new dependency, no PEP 440 range
    logic: exact string match is the gate). A package absent from the
    environment is recorded as ``"unknown"`` rather than raising, so a baseline
    can still be written; the mismatch check then flags the discrepancy.
    """
    out: dict[str, str] = {}
    for name in sorted(_TOOL_VERSION_PACKAGES):
        try:
            out[name] = version(name)
        except PackageNotFoundError:
            out[name] = "unknown"
    return out

# Per-paper status values. REGRESSED/CROSSED_FLOOR/NEW_BELOW_FLOOR/INVALID fail
# unconditionally; NEW fails only under fail_on_new; OK passes.
STATUS_OK = "ok"
STATUS_NEW = "new"
STATUS_REGRESSED = "regressed"
STATUS_CROSSED_FLOOR = "crossed_floor"
STATUS_NEW_BELOW_FLOOR = "new_below_floor"
STATUS_INVALID = "invalid"

_FAILING_STATUSES = frozenset(
    {STATUS_REGRESSED, STATUS_CROSSED_FLOOR, STATUS_NEW_BELOW_FLOOR, STATUS_INVALID}
)

_FLOORS = {
    "nid": C.NID_FLOOR,
    "teds": C.TEDS_FLOOR,
    "mhs": C.MHS_FLOOR,
    "content_recall": C.CONTENT_RECALL_FLOOR,
}

# Decimal granularity at which every metric is reported (see BenchRow.to_dict and
# the baseline writer). All comparisons round to it so the slack boundary is
# deterministic and not at the mercy of binary float representation
# (0.99 - 0.97 != 0.02 in IEEE-754), and so current values are compared at the
# SAME precision as the already-rounded baseline (symmetric rounding).
_NDIGITS = 4


def _axes(row: BenchRow) -> dict[str, float | None]:
    # teds/mhs may be None (ineligible: reference lacks that modality). None is
    # carried through and means "skip this axis", distinct from a NaN/inf which
    # is STATUS_INVALID.
    return {
        "nid": row.nid,
        "teds": row.teds,
        "mhs": row.mhs,
        "overall": row.overall,
        "content_recall": row.content_recall,
        "reading_order": row.reading_order,
        "grits_con": row.grits_con,
        "block_agreement": row.block_agreement,
        "structural_parity": row.structural_parity,
        "heading_level_parity": row.heading_level_parity,
    }


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


@dataclass(frozen=True)
class GuardFinding:
    """One paper's verdict against the baseline.

    ``regressions`` / ``crossed_floor`` / ``below_floor`` hold human-readable
    per-axis strings; ``status`` is the rolled-up verdict (see STATUS_* above).
    """

    pid: str
    status: str
    axes: dict[str, float | None]
    regressions: list[str] = field(default_factory=list)
    crossed_floor: list[str] = field(default_factory=list)
    below_floor: list[str] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return self.status in _FAILING_STATUSES

    def to_dict(self) -> dict:
        # Non-finite axes are serialized as null: a NaN/inf would emit a bare
        # ``NaN`` token (invalid JSON, silently re-parsed) and corrupt the report.
        return {
            "pid": self.pid,
            "status": self.status,
            "axes": {
                k: (round(v, _NDIGITS) if _finite(v) else None)
                for k, v in sorted(self.axes.items())
            },
            "regressions": list(self.regressions),
            "crossed_floor": list(self.crossed_floor),
            "below_floor": list(self.below_floor),
        }


@dataclass(frozen=True)
class GuardReport:
    findings: list[GuardFinding]
    missing: list[str]  # in baseline, absent from the current corpus
    slack: float
    floors: dict[str, float] = field(default_factory=lambda: dict(_FLOORS))
    fail_on_new: bool = False

    def _is_failing(self, f: GuardFinding) -> bool:
        if f.status in _FAILING_STATUSES:
            return True
        return self.fail_on_new and f.status == STATUS_NEW

    @property
    def failed(self) -> bool:
        # A vanished paper is a hard fail: a dropped paper can silently hide a
        # regression, so the baseline must be updated explicitly to drop it.
        return bool(self.missing) or any(self._is_failing(f) for f in self.findings)

    def regressed(self) -> list[GuardFinding]:
        return [f for f in self.findings if self._is_failing(f)]

    def to_dict(self) -> dict:
        counts: dict[str, int] = {}
        for f in self.findings:
            counts[f.status] = counts.get(f.status, 0) + 1
        return {
            "schema_version": C.WHISKER_SCHEMA_VERSION,
            "kind": "whisker-guard-report",
            "slack": self.slack,
            "floors": dict(sorted(self.floors.items())),
            "fail_on_new": self.fail_on_new,
            "failed": self.failed,
            "count": len(self.findings),
            "status_counts": dict(sorted(counts.items())),
            "missing": sorted(self.missing),
            "findings": [f.to_dict() for f in sorted(self.findings, key=lambda x: x.pid)],
        }


def _require_unique_pids(rows: list[BenchRow]) -> None:
    seen: set[str] = set()
    dups: set[str] = set()
    for row in rows:
        if row.pid in seen:
            dups.add(row.pid)
        seen.add(row.pid)
    if dups:
        # last-wins in a dict comprehension would silently keep one of two
        # conflicting scores for the same paper: refuse rather than guess.
        raise ValueError(f"duplicate pid(s) in rows: {sorted(dups)}")


def baseline_from_rows(rows: list[BenchRow]) -> dict:
    """Build a committable per-paper baseline payload from bench rows.

    Embeds the slack and floors in force so the baseline is self-describing:
    re-diffing it reproduces the same verdicts regardless of later constant
    changes. Raises ``ValueError`` on duplicate pids.
    """
    _require_unique_pids(rows)
    return {
        "schema_version": C.WHISKER_SCHEMA_VERSION,
        "kind": GUARD_BASELINE_KIND,
        "tool_versions": collect_tool_versions(),
        "axis_slack": C.GUARD_AXIS_SLACK,
        "floors": dict(sorted(_FLOORS.items())),
        "rows": {
            row.pid: {
                k: (None if v is None else round(v, _NDIGITS))
                for k, v in sorted(_axes(row).items())
            }
            for row in sorted(rows, key=lambda r: r.pid)
        },
    }


def _validate_baseline(baseline: dict) -> None:
    """Reject a baseline that is the wrong kind, schema, or carries bad values.

    A stale or mismatched baseline trusted blindly would silently change the
    meaning of the gate. Schema/kind mismatches and non-finite stored metrics
    are hard errors.
    """
    if not isinstance(baseline, dict):
        raise ValueError("baseline must be a JSON object")
    kind = baseline.get("kind")
    if kind != GUARD_BASELINE_KIND:
        raise ValueError(
            f"baseline kind {kind!r} != {GUARD_BASELINE_KIND!r} "
            "(wrong file? bench leaderboards are not guard baselines)"
        )
    schema = baseline.get("schema_version")
    if schema != C.WHISKER_SCHEMA_VERSION:
        raise ValueError(
            f"baseline schema_version {schema!r} != {C.WHISKER_SCHEMA_VERSION!r} "
            "(regenerate with --update)"
        )
    # Toolchain mismatch is a hard fail (not a warning): scores produced by a
    # different tomd/whisker are not comparable to the stored rows. Warn-only
    # would recreate the silent stale-baseline bug. The fix is an explicit
    # --update, the same acknowledgement pandoc requires via --accept.
    base_versions = baseline.get("tool_versions")
    if base_versions is not None:
        if not isinstance(base_versions, dict):
            raise ValueError("baseline 'tool_versions' must be a JSON object")
        current = collect_tool_versions()
        for name in sorted(_TOOL_VERSION_PACKAGES):
            want = base_versions.get(name)
            have = current.get(name)
            if want is not None and want != have:
                raise ValueError(
                    f"baseline tool_versions.{name} {want!r} != current {have!r} "
                    "(regenerate with --update)"
                )
    slack = baseline.get("axis_slack")
    if slack is not None and not (_finite(slack) and slack >= 0):
        raise ValueError(f"baseline axis_slack must be a non-negative number, got {slack!r}")
    rows = baseline.get("rows")
    if rows is not None and not isinstance(rows, dict):
        raise ValueError("baseline 'rows' must be a JSON object")
    for pid, axes in (rows or {}).items():
        if not isinstance(axes, dict):
            raise ValueError(f"baseline row {pid!r} must be a JSON object")
        for axis, value in axes.items():
            # null is a legitimate ineligible axis (no tables / no headings in
            # the reference); only an actual NaN/inf/non-number is corrupt.
            if value is not None and not _finite(value):
                raise ValueError(
                    f"baseline row {pid!r} axis {axis!r} is non-finite ({value!r})"
                )


def _resolve_floors(baseline: dict | None, override: dict[str, float] | None) -> dict[str, float]:
    if override is not None:
        return dict(override)
    if baseline:
        base_floors = baseline.get("floors")
        if isinstance(base_floors, dict) and base_floors:
            # Keep only known axes; ignore unknown keys defensively.
            resolved = {k: float(base_floors[k]) for k in _FLOORS if k in base_floors}
            if resolved:
                return resolved
    return dict(_FLOORS)


def _resolve_slack(baseline: dict | None, override: float | None) -> float:
    if override is not None:
        return override
    if baseline:
        slack = baseline.get("axis_slack")
        if _finite(slack):
            return float(slack)
    return C.GUARD_AXIS_SLACK


def _evaluate_paper(
    pid: str,
    axes: dict[str, float | None],
    base: dict[str, float | None] | None,
    slack: float,
    floors: dict[str, float],
) -> GuardFinding:
    regressions: list[str] = []
    crossed: list[str] = []
    below: list[str] = []

    # A non-finite metric (NaN/inf) makes every ``<`` comparison silently False,
    # which would let a corrupt score sail through. Catch it first and fail hard.
    # A None axis is NOT corrupt: it is an ineligible axis (reference lacks that
    # modality) and is skipped, not flagged.
    checked = sorted(set(C.GUARD_REGRESSION_AXES) | set(floors))
    bad = [a for a in checked if axes.get(a) is not None and not _finite(axes.get(a))]
    if bad:
        notes = [f"{a} non-finite ({axes.get(a)!r})" for a in bad]
        return GuardFinding(pid, STATUS_INVALID, axes, notes, [], [])

    # Compare current values at the baseline's reporting precision (symmetric).
    # Ineligible (None) axes stay None and are skipped by every check below.
    cur_axes = {
        a: (None if axes.get(a) is None else round(axes[a], _NDIGITS)) for a in checked
    }

    # Floor breaches (informational roll-up; a CURRENT value under its floor).
    for axis, floor in sorted(floors.items()):
        cur = cur_axes.get(axis)
        if cur is not None and cur < floor:
            below.append(f"{axis} {cur:.3f} < floor {floor}")

    if base is None:
        # New paper: the floor is its entry bar (no prior value to regress from).
        if below:
            return GuardFinding(pid, STATUS_NEW_BELOW_FLOOR, axes, [], [], below)
        return GuardFinding(pid, STATUS_NEW, axes, [], [], below)

    # Existing paper: regression vs its own baseline is the primary signal.
    for axis in C.GUARD_REGRESSION_AXES:
        cur = cur_axes.get(axis)
        prior = base.get(axis)
        if prior is None or cur is None:
            continue
        drop = round(prior - cur, _NDIGITS)
        if drop > slack:
            regressions.append(
                f"{axis} {prior:.3f} -> {cur:.3f} (-{drop:.3f} > slack {slack})"
            )
        elif axis in floors and prior >= floors[axis] > cur:
            # Crossed a floor downward by a sub-slack amount: still a regression
            # of quality across a published bar, just a small one.
            crossed.append(
                f"{axis} {prior:.3f} -> {cur:.3f} crossed floor {floors[axis]}"
            )

    if regressions:
        status = STATUS_REGRESSED
    elif crossed:
        status = STATUS_CROSSED_FLOOR
    else:
        status = STATUS_OK
    return GuardFinding(pid, status, axes, regressions, crossed, below)


def diff_rows(
    rows: list[BenchRow],
    baseline: dict | None,
    *,
    slack: float | None = None,
    floors: dict[str, float] | None = None,
    fail_on_new: bool = False,
) -> GuardReport:
    """Compare freshly scored rows against a committed baseline payload.

    ``baseline`` is the dict produced by ``baseline_from_rows`` (or ``None`` for
    a first run, where every paper is judged against the absolute floors only).

    Slack and floors are read FROM the baseline when present so the gate is
    reproducible from the committed file alone; ``slack``/``floors`` arguments
    override that only when explicitly passed (the CLI ``--slack`` flag). With
    ``fail_on_new`` a paper absent from the baseline fails even above floors,
    forcing an explicit ``--update`` acknowledgement before a new paper can pass.

    Raises ``ValueError`` on a malformed baseline or duplicate pids.
    """
    _require_unique_pids(rows)
    if baseline is not None:
        _validate_baseline(baseline)

    base_rows: dict[str, dict[str, float]] = {}
    if baseline:
        base_rows = baseline.get("rows", {}) or {}

    eff_slack = _resolve_slack(baseline, slack)
    eff_floors = _resolve_floors(baseline, floors)

    findings = [
        _evaluate_paper(row.pid, _axes(row), base_rows.get(row.pid), eff_slack, eff_floors)
        for row in sorted(rows, key=lambda r: r.pid)
    ]
    current_pids = {row.pid for row in rows}
    missing = sorted(pid for pid in base_rows if pid not in current_pids)
    return GuardReport(
        findings=findings,
        missing=missing,
        slack=eff_slack,
        floors=eff_floors,
        fail_on_new=fail_on_new,
    )
