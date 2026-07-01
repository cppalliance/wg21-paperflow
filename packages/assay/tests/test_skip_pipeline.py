#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

from __future__ import annotations

import asyncio

from assay.models import PipelineState, SynthesisOutput
from assay.pipeline import _custom_synthesize, _run_unless_skipped
from assay.render import render_report


def test_run_unless_skipped_guard():
    assert _run_unless_skipped(PipelineState(skipped=False)) is True
    assert _run_unless_skipped(PipelineState(skipped=True)) is False


def test_custom_synthesize_preserves_survey_synthesis_when_skipped():
    original = SynthesisOutput(
        verdict_label="Skipped",
        verdict_statement="Wording Dominant: not analyzed.",
        skip_reason="Wording-dominant paper (>80% clause headings).",
        paper_stats={"total_chars": 50000, "chunk_count": 10},
    )
    state = PipelineState(skipped=True, synthesis=original)

    asyncio.run(_custom_synthesize(state, None, None))

    assert state.synthesis is original
    assert state.synthesis.verdict_label == "Skipped"
    assert (
        state.synthesis.skip_reason == "Wording-dominant paper (>80% clause headings)."
    )


def test_render_skipped_report_shows_stats_and_reason():
    state = PipelineState(
        paper_id="P1000R0",
        paper_title="Big Wording Paper",
        skipped=True,
        synthesis=SynthesisOutput(
            verdict_label="Skipped",
            verdict_statement="Wording Dominant: not analyzed.",
            skip_reason="Wording-dominant paper (>80% clause headings).",
            paper_stats={
                "total_chars": 250000,
                "chunk_count": 42,
                "wording_ratio": 0.85,
                "audience": "CWG, LWG",
            },
        ),
    )
    report = render_report(state, "")
    assert "Wording-dominant paper" in report
    assert "250,000" in report
    assert "Sections: 42" in report
    assert "85%" in report
    assert "CWG, LWG" in report
    assert "Step 3 (Survey)" in report
    assert "Model: n/a" not in report
    assert "Service: n/a" not in report
