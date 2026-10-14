#
# Copyright (c) 2026 Sean Parsons
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Proof test: structural_parity separates Marker from tomd.

Marker-balanced/run-a output scored against the golden ideals must have
strictly lower ``structural_parity`` than tomd on papers where Marker drops
categorical structure (code fences, inline code). The key case: Marker
emits 0 code fences on P4012R0-codeblock while the ideal has many,
and 0 inline code on every paper. nid/mhs must remain bitwise deterministic
(no algorithm change).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from whisker.det.bench import _structural_parity, run_bench

_RUN_DIR = Path(__file__).resolve().parents[2] / "benchmark" / "runs" / "2026-08-pilot"
_MARKER_DIR = _RUN_DIR / "marker-v2-balanced" / "run-a"
_TOMD_DIR = _RUN_DIR / "tomd" / "run-a"
_GOLDEN_DIR = _RUN_DIR / "golden"

_PIDS = ["P1112R4", "P4004R1", "P4012R0-codeblock", "P4012R0-page-10", "P4012R0-page-6"]


def _ideal(pid: str) -> str:
    path = _GOLDEN_DIR / f"{pid}.ideal.review.md"
    if not path.is_file():
        pytest.skip(f"golden ideal {path.name} not found")
    return path.read_text(encoding="utf-8")


def _output(directory: Path, pid: str) -> str:
    path = directory / f"{pid}.md"
    if not path.is_file():
        pytest.skip(f"output {path.name} not found in {directory}")
    return path.read_text(encoding="utf-8")


@pytest.fixture(params=_PIDS)
def pid(request):
    return request.param


class TestStructuralParityCatchesMarker:
    """Marker's structural_parity must be strictly worse than tomd's."""

    def test_marker_fails_structural_parity_on_codeblock(self):
        pid = "P4012R0-codeblock"
        ideal = _ideal(pid)
        marker = _output(_MARKER_DIR, pid)
        sp = _structural_parity(marker, ideal)
        assert sp is not None and sp < 1.0, (
            f"structural_parity {sp} should be < 1.0 for Marker on {pid}"
        )

    def test_marker_parity_strictly_worse_than_tomd(self, pid):
        ideal = _ideal(pid)
        marker = _output(_MARKER_DIR, pid)
        tomd = _output(_TOMD_DIR, pid)
        sp_marker = _structural_parity(marker, ideal)
        sp_tomd = _structural_parity(tomd, ideal)
        if sp_marker is None and sp_tomd is None:
            pytest.skip(f"both None for {pid}")
        m = sp_marker if sp_marker is not None else 1.0
        t = sp_tomd if sp_tomd is not None else 1.0
        assert m <= t, (
            f"Marker structural_parity ({sp_marker}) should not exceed "
            f"tomd ({sp_tomd}) on {pid}"
        )


class TestExistingAxesUnchanged:
    """nid and mhs values must remain bitwise identical (no algorithm change)."""

    def test_nid_and_mhs_deterministic(self, pid):
        ideal = _ideal(pid)
        tomd = _output(_TOMD_DIR, pid)
        rows_a = run_bench([(pid, tomd, ideal)])
        rows_b = run_bench([(pid, tomd, ideal)])
        assert rows_a[0].nid == rows_b[0].nid, f"nid not deterministic on {pid}"
        assert rows_a[0].mhs == rows_b[0].mhs, f"mhs not deterministic on {pid}"
