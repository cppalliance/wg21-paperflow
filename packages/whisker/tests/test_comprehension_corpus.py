#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Lane 3 comprehension gate over the committed micro-corpus.

This is the CI-hermetic counterpart to the ``whisker facts`` CLI: the CLI reads
the candidate from the paperstore backend (``data/``, gitignored, absent in CI),
so it cannot gate in CI. Here the substrate is the committed
``corpus/<pid>.expected.md`` snapshot, so the comprehension assertions run with
no backend, no ``data/``, and no LLM.

For each paper that ships BOTH a ``<pid>.facts.jsonl`` and a
``<pid>.expected.md``, every ``checked: verified`` fact must hold against the
snapshot. A scrambled snapshot must fail (the canary), so a vacuous green is
ruled out from both sides.
"""

from pathlib import Path

import pytest

from whisker.facts import check_facts, parse_facts_jsonl

_CORPUS = Path(__file__).resolve().parent.parent / "corpus"
_FACTS_SUFFIX = ".facts.jsonl"
_EXPECTED_SUFFIX = ".expected.md"


def _corpus_pairs() -> list[tuple[str, Path, Path]]:
    """(pid, facts_path, expected_path) for papers with both artifacts.

    A facts file without a committed snapshot has no hermetic substrate, so it
    is skipped here (it is still exercised against ``data/`` by the CLI).
    """
    pairs: list[tuple[str, Path, Path]] = []
    for facts_path in sorted(_CORPUS.glob(f"*{_FACTS_SUFFIX}")):
        pid = facts_path.name[: -len(_FACTS_SUFFIX)].upper()
        expected_path = _CORPUS / f"{pid}{_EXPECTED_SUFFIX}"
        if expected_path.is_file():
            pairs.append((pid, facts_path, expected_path))
    return pairs


_PAIRS = _corpus_pairs()
_IDS = [pid for pid, _, _ in _PAIRS]


def test_corpus_has_at_least_one_comprehension_paper():
    # Guard against a vacuous suite: if every paper lost its snapshot the
    # parametrized test below would silently collect nothing and pass.
    assert _PAIRS, (
        f"no <pid>{_FACTS_SUFFIX} + <pid>{_EXPECTED_SUFFIX} pairs found in {_CORPUS}"
    )


@pytest.mark.parametrize(("pid", "facts_path", "expected_path"), _PAIRS, ids=_IDS)
def test_verified_facts_hold_against_snapshot(pid, facts_path, expected_path):
    md = expected_path.read_text(encoding="utf-8")
    facts = parse_facts_jsonl(facts_path.read_text(encoding="utf-8-sig"), pid)

    report = check_facts(md, facts, pid)

    # A paper with a committed facts file must enforce at least one fact, else
    # the snapshot proves nothing about comprehension.
    verified = [c for c in report.checks if c.verified]
    assert verified, f"{pid}: facts file has no checked:verified fact"

    if report.failed:
        lines = "\n".join(f"  {c.id} ({c.type}): {c.detail}" for c in report.failures())
        pytest.fail(f"{pid}: verified comprehension fact(s) failed:\n{lines}")


def test_canary_scrambled_table_cell_fails():
    # Proves the gate has teeth: corrupting one Table A cell of the P4182R0
    # snapshot must flip the corresponding verified table fact to a failure.
    pid = "P4182R0"
    expected_path = _CORPUS / f"{pid}{_EXPECTED_SUFFIX}"
    facts_path = _CORPUS / f"{pid}{_FACTS_SUFFIX}"
    if not (expected_path.is_file() and facts_path.is_file()):
        pytest.skip(f"{pid} corpus artifacts not present")

    md = expected_path.read_text(encoding="utf-8")
    needle = "(CUDA, SYCL) | No |"
    assert needle in md, "canary anchor drifted; update the scramble target"
    scrambled = md.replace(needle, "(CUDA, SYCL) | Yes |", 1)

    facts = parse_facts_jsonl(facts_path.read_text(encoding="utf-8-sig"), pid)
    report = check_facts(scrambled, facts, pid)

    assert report.failed, "scrambled snapshot must fail the comprehension gate"
    assert any(c.id == "tableA-gpu-coro-no" for c in report.failures())
