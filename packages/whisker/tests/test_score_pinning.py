#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Score-pinning regression: tomd goldens scored through whisker.

For every committed tomd golden (PDF + ``.golden.md``), this module runs
the whisker structural gates and tomd QA metrics on the golden markdown,
then compares the result against a committed baseline JSON.

The baseline captures the current scores so any change to tomd golden
output *or* whisker scoring logic shows up as a diff in one file.

Update the baseline with::

    WHISKER_PIN_UPDATE=1 uv run --package whisker pytest packages/whisker/tests/test_score_pinning.py -x

The test is hermetic: no backend, no source PDF extraction at runtime,
no network. Gates and QA metrics need only the markdown text.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from tomd.lib.pdf.qa import compute_metrics
from whisker.gates import run_gates

_GOLDEN_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "tomd" / "tests" / "fixtures" / "golden"
)

_BASELINE_PATH = Path(__file__).resolve().parent / "fixtures" / "score-baseline.json"

_GOLDEN_STEMS = (
    "p0533r9",
    "p0957r8",
    "p1068r11",
    "p3556r0",
    "p1122r3",
    "p2040r0",
    "p3714r0",
    "p1112r4",
    "p4174r0",
    "p4004r1",
    "p4100r1",
    "p3968r0",
    "p4094r0",
    "p4016r0",
    "p4024r0",
    "p4012r0-codeblock",
    "p4012r0-page-10",
    "p4012r0-page-6",
    "p0876r22-page-14",
)


def _golden_md_path(stem: str) -> Path | None:
    """Resolve a golden markdown across both fixture layouts.

    Upstream PR #257 moved most goldens from flat ``<stem>.golden.md`` into
    ``snapshots/<stem>.md``; papers added since then may exist in either
    place. Prefer the snapshot (the layout new goldens land in).
    """
    for candidate in (
        _GOLDEN_DIR / "snapshots" / f"{stem}.md",
        _GOLDEN_DIR / f"{stem}.golden.md",
    ):
        if candidate.exists():
            return candidate
    return None


def _score_one(stem: str) -> dict:
    """Score a single golden markdown and return a pinnable dict."""
    golden_md_path = _golden_md_path(stem)
    if golden_md_path is None:
        pytest.skip(f"golden md not found for stem: {stem}")

    md_text = golden_md_path.read_text(encoding="utf-8")

    gates = run_gates(md_text)
    qa = compute_metrics(md_text, file=stem)

    return {
        "gates": {g.name: g.passed for g in gates},
        "qa_score": qa.score,
        "heading_count": qa.heading_count,
        "max_heading_level": qa.max_heading_level,
        "code_block_count": qa.code_block_count,
        "table_count": qa.table_count,
        "front_matter_count": qa.front_matter_count,
        "uncertain_count": qa.uncertain_count,
        "mojibake_count": qa.mojibake_count,
        "table_parse_errors": qa.table_parse_errors,
        "lossy_table_count": qa.lossy_table_count,
        "paragraph_count": qa.paragraph_count,
        "heading_level_skips": qa.heading_level_skips,
        "wording_section_count": qa.wording_section_count,
    }


def _build_full_baseline() -> dict:
    """Generate the baseline dict for all goldens."""
    baseline: dict[str, dict] = {}
    for stem in _GOLDEN_STEMS:
        if _golden_md_path(stem) is None:
            continue
        baseline[stem] = _score_one(stem)
    return baseline


def _load_baseline() -> dict:
    if not _BASELINE_PATH.exists():
        pytest.fail(
            f"Baseline not found at {_BASELINE_PATH}. "
            "Generate it with: WHISKER_PIN_UPDATE=1 uv run --package whisker "
            "pytest packages/whisker/tests/test_score_pinning.py -x"
        )
    return json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def baseline():
    if os.environ.get("WHISKER_PIN_UPDATE") == "1":
        if os.environ.get("CI"):
            pytest.fail(
                "WHISKER_PIN_UPDATE=1 is forbidden in CI. "
                "Refresh the baseline locally, review the diff, then commit."
            )
        data = _build_full_baseline()
        _BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _BASELINE_PATH.write_text(
            json.dumps(data, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        pytest.skip("Baseline updated; re-run without WHISKER_PIN_UPDATE to test.")
    return _load_baseline()


# Papers whose baselines legitimately contain false gates. If a new golden
# shows up with a false gate and is NOT listed here, the meta-test below
# fails, forcing the author to either fix the golden or explicitly acknowledge
# the known failure (pandoc --accept discipline).
_EXPECTED_GATE_FAILURES: dict[str, set[str]] = {
    "p1122r3": {"no_toc_leak"},
    "p2040r0": {"heading_monotone"},
    "p3556r0": {"heading_monotone"},
}


@pytest.mark.parametrize("stem", _GOLDEN_STEMS)
def test_score_pinned(stem: str, baseline: dict):
    """Each golden's gate + QA snapshot must match the committed baseline."""
    if stem not in baseline:
        pytest.skip(f"{stem} not in baseline (golden md may be missing)")

    actual = _score_one(stem)
    expected = baseline[stem]

    assert actual["gates"] == expected["gates"], (
        f"{stem}: gate mismatch\n  actual:   {actual['gates']}\n  expected: {expected['gates']}"
    )

    for key in (
        "qa_score", "heading_count", "max_heading_level",
        "code_block_count", "table_count", "front_matter_count",
        "uncertain_count", "mojibake_count", "table_parse_errors",
        "lossy_table_count", "paragraph_count", "heading_level_skips",
        "wording_section_count",
    ):
        assert actual[key] == expected[key], (
            f"{stem}: {key} mismatch: actual={actual[key]}, expected={expected[key]}"
        )


@pytest.mark.parametrize("stem", _GOLDEN_STEMS)
def test_no_unacknowledged_gate_failures(stem: str, baseline: dict):
    """Fail-fast when a baseline contains a false gate not listed in
    _EXPECTED_GATE_FAILURES.  Forces the author to either fix the golden
    or explicitly acknowledge the known failure."""
    if stem not in baseline:
        pytest.skip(f"{stem} not in baseline")
    gates = baseline[stem].get("gates", {})
    failed = {name for name, passed in gates.items() if not passed}
    allowed = _EXPECTED_GATE_FAILURES.get(stem, set())
    unexpected = failed - allowed
    assert not unexpected, (
        f"{stem}: baseline has unacknowledged gate failure(s) {unexpected}. "
        "Either fix the golden or add the stem to _EXPECTED_GATE_FAILURES "
        "in test_score_pinning.py."
    )
