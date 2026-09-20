#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Lane 1 (Stability): byte-/near-exact golden compare of tomd output.

The fuzzy metrics (Lane 2: nid/teds/mhs) measure how CLOSE the candidate is to a
reference; they smooth over small formatting regressions. This lane catches the
opposite: did the EXACT output text change at all? It compares the normalized
candidate markdown against a committed ``<pid>.expected.md`` snapshot and fails
on any difference.

Provenance discipline (the June 2026 golden-provenance audit, 28 repos): no repo
has an automatic "this file is 100% correct" oracle. The committed expected file
is a self-blessed snapshot of tomd output, frozen by a HUMAN reviewing the diff,
NOT a correctness oracle. So this lane proves STABILITY (no silent change), never
correctness. Correctness is the job of Lane 2 (fidelity vs ``gt.md``) and Lane 3
(comprehension via fact assertions). Run it on a small blessed
micro-corpus, not the full corpus, to keep the bless cheap and the diffs small.

Field consensus the lane mirrors (~17/28 repos: pandoc ``--accept``, html2text
``rstrip`` compare, html-to-markdown-go ``-update``, pymupdf4llm ``.expected.md``
with ``\\r`` strip): committed output files + explicit non-CI refresh flag +
deterministic normalize before diff. The refresh ritual here is the CLI
``--update`` flag, structurally parallel to ``whisker guard --update``.

An optional ``golden.json`` manifest may list ``expected_failures``: pids whose
committed snapshot is KNOWN imperfect (tabula-java ``expectedFailure``). Such a
golden still fails on ANY change (a silent regression OR the silent improvement
you were waiting for), forcing a deliberate human re-bless either way.

This module returns data only; the CLI reads the corpus, writes snapshots, and
owns exit codes.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field

from whisker import constants as C

__all__ = [
    "GOLDEN_EXPECTED_SUFFIX",
    "GOLDEN_MANIFEST_KIND",
    "GOLDEN_MANIFEST_NAME",
    "NORMALIZATION_VERSION",
    "GoldenFinding",
    "GoldenItem",
    "GoldenReport",
    "diff_goldens",
    "normalize_for_exact_lane",
]

GOLDEN_EXPECTED_SUFFIX = ".expected.md"
GOLDEN_MANIFEST_NAME = "golden.json"
GOLDEN_MANIFEST_KIND = "whisker-golden-manifest"

# Bump when the normalize function changes; a changed normalizer shifts every
# comparison and requires a deliberate --update + review, so the version travels
# with the snapshot semantics (golden-exact-lane audit, PyMuPDF lesson).
NORMALIZATION_VERSION = 1

# A snapshot present and identical -> ok. CHANGED/MISSING fail unconditionally;
# NEW fails only under fail_on_new; XFAIL_OK is a known-imperfect golden that is
# still unchanged (passes, reported distinctly).
STATUS_OK = "ok"
STATUS_CHANGED = "changed"
STATUS_NEW = "new"
STATUS_MISSING = "missing"
STATUS_XFAIL_OK = "expected_failure"

_FAILING_STATUSES = frozenset({STATUS_CHANGED, STATUS_MISSING})


def normalize_for_exact_lane(text: str) -> str:
    """Deterministic near-exact normalizer applied to BOTH sides before diff.

    Policy (html2text / pymupdf4llm precedent): collapse ``\\r\\n`` and ``\\r``
    to ``\\n``, strip trailing whitespace per line, and enforce a single
    trailing newline at EOF. This absorbs platform line-ending and
    trailing-space noise (the brittle part of byte-exact goldens on Windows
    checkouts) while keeping every meaningful character change visible.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    body = "\n".join(line.rstrip() for line in text.split("\n")).rstrip("\n")
    return body + "\n" if body else ""


@dataclass(frozen=True)
class GoldenItem:
    """One corpus entry: the staged candidate and its committed snapshot.

    ``candidate`` is ``None`` when the paper is not staged (vanished from the
    store); ``expected`` is ``None`` when no ``<pid>.expected.md`` is committed.
    """

    pid: str
    candidate: str | None
    expected: str | None
    expected_failure: bool = False


@dataclass(frozen=True)
class GoldenFinding:
    pid: str
    status: str
    diff: list[str] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return self.status in _FAILING_STATUSES

    def to_dict(self) -> dict:
        return {"pid": self.pid, "status": self.status, "diff": list(self.diff)}


@dataclass(frozen=True)
class GoldenReport:
    findings: list[GoldenFinding]
    fail_on_new: bool = False
    normalization_version: int = NORMALIZATION_VERSION

    def _is_failing(self, f: GoldenFinding) -> bool:
        if f.status in _FAILING_STATUSES:
            return True
        return self.fail_on_new and f.status == STATUS_NEW

    @property
    def failed(self) -> bool:
        return any(self._is_failing(f) for f in self.findings)

    def regressed(self) -> list[GoldenFinding]:
        return [f for f in self.findings if self._is_failing(f)]

    def to_dict(self) -> dict:
        counts: dict[str, int] = {}
        for f in self.findings:
            counts[f.status] = counts.get(f.status, 0) + 1
        return {
            "schema_version": C.WHISKER_SCHEMA_VERSION,
            "kind": "whisker-golden-report",
            "normalization_version": self.normalization_version,
            "fail_on_new": self.fail_on_new,
            "failed": self.failed,
            "count": len(self.findings),
            "status_counts": dict(sorted(counts.items())),
            "findings": [f.to_dict() for f in sorted(self.findings, key=lambda x: x.pid)],
        }


def _evaluate(item: GoldenItem) -> GoldenFinding:
    if item.candidate is None:
        # A corpus member without a staged candidate is always missing, even
        # when it entered through a GT marker and has no snapshot yet.
        return GoldenFinding(item.pid, STATUS_MISSING)
    if item.expected is None:
        # No committed snapshot: a new paper. Passes by default; --fail-on-new
        # forces an explicit --update to admit it (guard parity).
        return GoldenFinding(item.pid, STATUS_NEW)
    cur = normalize_for_exact_lane(item.candidate)
    exp = normalize_for_exact_lane(item.expected)
    if cur == exp:
        return GoldenFinding(
            item.pid, STATUS_XFAIL_OK if item.expected_failure else STATUS_OK
        )
    diff = list(
        difflib.unified_diff(
            exp.splitlines(),
            cur.splitlines(),
            fromfile=f"{item.pid}{GOLDEN_EXPECTED_SUFFIX}",
            tofile=f"{item.pid} (candidate)",
            lineterm="",
        )
    )
    return GoldenFinding(item.pid, STATUS_CHANGED, diff)


def diff_goldens(items: list[GoldenItem], *, fail_on_new: bool = False) -> GoldenReport:
    """Compare normalized candidates against committed snapshots.

    Each item is judged independently: an exact (normalized) match is ``ok``
    (or ``expected_failure`` for a flagged known-imperfect golden), any
    difference is ``changed`` (with a unified diff), a missing snapshot is
    ``new`` only when the candidate exists, and a missing candidate is always
    ``missing``. Deterministic.
    """
    findings = [_evaluate(item) for item in sorted(items, key=lambda x: x.pid)]
    return GoldenReport(findings=findings, fail_on_new=fail_on_new)
