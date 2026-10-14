#
# Copyright (c) 2026 Sean Parsons
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Probe-strength gate: every corpus fact set must measurably degrade.

A fact set that still scores 1.0 under ``structure_stripped`` or
``keep_10pct`` is not testing conversion quality and is not admissible
for the benchmark.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from whisker.det.probe_strength import keep_fraction, strip_all_structure
from whisker.facts import check_facts, parse_facts_jsonl

_FACTS_DIR = Path(__file__).resolve().parents[2] / "benchmark" / "corpus" / "facts"
_IDEALS_DIR = (
    Path(__file__).resolve().parents[3]
    / "tomd" / "tests" / "fixtures" / "golden" / "ideals"
)

if not _FACTS_DIR.is_dir():
    pytest.skip(
        "retired competitor-campaign corpus is not in this checkout",
        allow_module_level=True,
    )


def _corpus_pairs() -> list[tuple[str, Path, Path]]:
    """Return (pid, facts_path, ideal_path) for every corpus paper."""
    pairs = []
    for fp in sorted(_FACTS_DIR.glob("*.facts.jsonl")):
        pid = fp.stem.replace(".facts", "")
        ideal = _IDEALS_DIR / f"{pid}.md"
        if ideal.is_file():
            pairs.append((pid, fp, ideal))
    return pairs


_PAIRS = _corpus_pairs()
_IDS = [p[0] for p in _PAIRS]


@pytest.fixture(params=_PAIRS, ids=_IDS)
def paper(request):
    return request.param


def _pass_rate(md: str, facts_path: Path, pid: str) -> float:
    facts = parse_facts_jsonl(facts_path.read_text(encoding="utf-8"), pid)
    checks = check_facts(md, facts, pid).checks
    if not checks:
        return 0.0
    return sum(1 for c in checks if c.passed) / len(checks)


class TestProbeStrengthGate:
    """Fact sets that survive severe mutilation are inadmissible."""

    def test_structure_stripped_below_one(self, paper):
        pid, facts_path, ideal_path = paper
        md = ideal_path.read_text(encoding="utf-8")
        rate = _pass_rate(strip_all_structure(md), facts_path, pid)
        assert rate < 1.0, (
            f"{pid}: fact set still passes at 1.0 under structure_stripped "
            f"(rate={rate}). Facts are too easy."
        )

    def test_keep_10pct_below_one(self, paper):
        pid, facts_path, ideal_path = paper
        md = ideal_path.read_text(encoding="utf-8")
        rate = _pass_rate(keep_fraction(md, 0.10), facts_path, pid)
        assert rate < 1.0, (
            f"{pid}: fact set still passes at 1.0 under keep_10pct "
            f"(rate={rate}). Facts are too easy."
        )
