#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for tapetum_llm --trace rendering and phase accounting."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from pipeline.runner import StepMetrics
from whisker.llm.adjudicate import _PipelineState, adjudicate_paper
from whisker.llm.constants import GUARD_TAG
from whisker.llm.models import (
    Adjudication,
    AxisFinding,
    EvidenceSpan,
    MetadataOutlineCheck,
    TapetumResult,
)
from whisker.llm.pdf_judge import (
    PageScreenEntry,
    PdfJudgeResult,
    PdfLaneError,
    _set_progress,
)
from whisker.llm.source_router import RiskSignal
from whisker.llm.trace_render import (
    _QUOTE_LEN,
    render_pdf_trace,
    render_text_trace,
)
from whisker.llm.unit_judge import UnitJudgeResult

_PAPER_SENTINEL = "UNIQUE_PAPER_MD_SENTINEL_xyz_do_not_leak"


def _adjudication(verdict: str = "review") -> Adjudication:
    return Adjudication(
        reasoning="checked wording and structure",
        axis_findings=[
            AxisFinding(
                axis="wording",
                verdict=verdict,
                severity="minor",
                note="wording drift in abstract",
            ),
        ],
        worst_axis="wording",
        verdict=verdict,
        confidence=0.42,
        evidence_spans=[
            EvidenceSpan(
                axis="wording",
                quote="A" * (_QUOTE_LEN + 20),
                reason="present",
            ),
        ],
        primary_concern="wording drift",
    )


def _populated_state() -> _PipelineState:
    state = _PipelineState(
        paper_md=_PAPER_SENTINEL + " more markdown text",
        whisker_signals={"verdict": "pass", "soft_flags": ["coverage"]},
        tier1=_adjudication("review"),
        tier2=_adjudication("not-llm-readable"),
        chunked=True,
        partial=False,
        escalation_signals=["axis_conflict", "ungrounded_evidence"],
        unit_result=UnitJudgeResult(
            risk_signals=[],
            unit_results=[
                {
                    "unit_id": "page:1",
                    "verdict": "pass",
                    "evidence_dispositions": [
                        {"quote": "cell value", "candidate_status": "present_in_candidate"},
                    ],
                },
                {"unit_id": "page:2", "verdict": "review", "evidence_dispositions": []},
            ],
            defect_groups=[],
            verdict="review",
            checked_unit_ids=["page:1"],
            failed_unit_ids=["page:2"],
            unchecked_unit_ids=["page:3"],
        ),
        risk_signals=[
            RiskSignal("page:2", "table_corruption", "critical", "cell swapped"),
        ],
        metadata_outline_check=MetadataOutlineCheck(
            reasoning="title mismatch",
            title_matches=False,
            document_number_matches=True,
            date_matches=True,
            heading_drift=["h2:Abstract -> ###:Abstract"],
            missing_sections=["Introduction"],
            verdict="review",
        ),
        table_compare_result={
            "total_source_tables": 2,
            "total_candidate_tables": 1,
            "matched_tables": 1,
            "cell_diff_count": 1,
            "grid_unreliable": False,
            "cell_diffs": [
                {
                    "page": 2,
                    "table_index": 0,
                    "row": 1,
                    "col": 0,
                    "source_text": "src",
                    "candidate_text": "dst",
                    "diff_type": "mismatch",
                },
            ],
        },
        unit_selection=[{"unit_id": "page:1", "status": "checked"}],
        phase_durations={
            "metadata": 4.2,
            "triage": 12.0,
            "adjudicate": 8.0,
            "unit_checks": 3.1,
            "table_compare": 0.4,
        },
    )
    state._result = TapetumResult(
        pid="P1R0",
        whisker_verdict="pass",
        suggested_verdict="review",
        confidence=0.42,
        escalated=True,
        tier1_model="fast",
        tier2_model="deep",
        grounded_evidence=[
            {"quote": "cell value", "status": "exact", "start": 0, "end": 10},
        ],
        ungrounded_dropped=1,
        status="ok",
    )
    return state


def _metrics() -> list[StepMetrics]:
    return [
        StepMetrics(name="0. Select", duration_s=12.3),
        StepMetrics(name="1. Triage", duration_s=90.0),
        StepMetrics(name="2. Adjudicate", duration_s=8.0),
        StepMetrics(name="3. Decide", duration_s=3.5),
    ]


def test_render_text_trace_step_headings_and_durations():
    state = _populated_state()
    metrics = _metrics()
    for step in range(4):
        text = render_text_trace(state, step, step_metrics=metrics)
        for index in range(step + 1):
            name = ("Select", "Triage", "Adjudicate", "Decide")[index]
            assert f"## Step {index} ({name})" in text
        assert f"## Step {step + 1} " not in text
        assert _PAPER_SENTINEL not in text

    full = render_text_trace(state, 3, step_metrics=metrics)
    assert "## Step 0 (Select) (12.3s)" in full
    assert "## Step 1 (Triage) (1.5m)" in full
    assert "paper_md: " in full
    assert "chars" in full
    assert '"' + ("A" * _QUOTE_LEN) + '..."' in full
    assert "### Phases" in full
    assert "- metadata: 4.2s" in full
    assert "- triage: 12.0s" in full
    assert "- adjudicate: 8.0s" in full
    assert "- unit_checks: 3.1s" in full
    assert "### Escalation signals (2)" in full
    assert "### Risk signals (1)" in full
    assert "### Unit results checked (1)" in full
    assert "### Unit results failed (1)" in full
    assert "### Evidence (" in full


def test_render_text_trace_empty_step_still_has_heading():
    text = render_text_trace(_PipelineState(), 2, step_metrics=[])
    assert "## Step 0 (Select)" in text
    assert "## Step 1 (Triage)" in text
    assert "## Step 2 (Adjudicate)" in text
    assert "- tier1: none" in text
    assert "### Escalation signals (0)" in text


def _pdf_result(**overrides) -> PdfJudgeResult:
    result = PdfJudgeResult(
        pid="P1R0",
        verdict="review",
        confidence=0.81,
        reasoning="should not appear in the trace body as dumped prose",
        missing_content=["secret missing quote"],
        ungrounded_dropped=2,
        text_nid=0.91,
        content_recall=0.88,
        page_count=4,
        page_screen=[
            PageScreenEntry(page=1, recall=0.99, tokens=80, flagged=False, skipped=False),
            PageScreenEntry(page=2, recall=0.40, tokens=90, flagged=True, skipped=False),
        ],
        page_escalations=[{"page": 2, "content_missing": True}],
        risk_signals=[{"unit_id": "page:2", "signal_type": "low_recall"}],
        defect_groups=[{"type": "omission", "count": 1}],
        unit_checks=[{"unit_id": "page:2", "verdict": "review"}],
        metadata_outline_check={"verdict": "pass"},
        unit_coverage={
            "coverage_complete": False,
            "checked_unit_ids": ["page:1", "page:2"],
            "unchecked_unit_ids": ["page:3"],
            "failed_unit_ids": ["page:4"],
        },
        all_pages_requested=True,
        unit_selection={
            "required": ["page:1", "page:2", "page:3", "page:4"],
            "checked": ["page:1", "page:2"],
            "unchecked": ["page:3"],
            "failed": ["page:4"],
        },
        toc_leak_hits=["## Contents 3"],
        code_boundary=[{"locus": "fence-1", "verdict": "pass"}],
        ideal_pending=False,
    )
    for key, value in overrides.items():
        setattr(result, key, value)
    return result


def test_render_pdf_trace_full_success():
    progress = {
        "phase": "done",
        "_phase_started": 99.0,
        "page_count": 4,
        "checked_unit_ids": ["page:1", "page:2"],
        "required_unit_ids": ["page:1", "page:2", "page:3", "page:4"],
        "phase_durations": {
            "extract": 1.2,
            "page_screen": 0.4,
            "monolith": 10.0,
            "metadata": 2.0,
            "escalations": 3.0,
            "unit_checks": 5.0,
            "code_boundary": 1.1,
        },
    }
    text = render_pdf_trace("P1R0", progress, _pdf_result(), None)
    assert "## Step 1 (Extract)" in text
    assert "## Step 2 (Screen)" in text
    assert "## Step 3 (Monolith)" in text
    assert "## Step 4 (Metadata)" in text
    assert "## Step 5 (Escalations)" in text
    assert "## Step 6 (Unit checks)" in text
    assert "## Step 7 (Code boundary)" in text
    assert "## Result" in text
    assert "- verdict: review" in text
    assert "- status: ok" in text
    assert "_phase_started" not in text
    assert "secret missing quote" not in text
    assert "should not appear in the trace body" not in text


def test_render_pdf_trace_error_mid_monolith():
    progress = {
        "phase": "monolith",
        "_phase_started": 50.0,
        "page_count": 2,
        "phase_durations": {
            "extract": 1.0,
            "page_screen": 0.5,
        },
    }
    text = render_pdf_trace(
        "P1R0",
        progress,
        None,
        PdfLaneError("P1R0: judge call failed: boom"),
    )
    assert "## Step 1 (Extract)" in text
    assert "## Step 2 (Screen)" in text
    assert "## Step 3 (Monolith)" in text
    assert "## Step 4 (Metadata)" not in text
    assert "## Step 5 (Escalations)" not in text
    assert "## Step 6 (Unit checks)" not in text
    assert "## Step 7 (Code boundary)" not in text
    assert "## Result" not in text
    assert "## Error" in text
    assert "PdfLaneError" in text
    assert "judge call failed: boom" in text


def test_render_pdf_trace_metadata_short_circuit():
    progress = {
        "phase": "done",
        "phase_durations": {
            "extract": 1.0,
            "page_screen": 0.5,
            "monolith": 8.0,
            "metadata": 2.0,
            "metadata_short_circuit": 0.1,
        },
    }
    result = _pdf_result(
        metadata_outline_check={"verdict": "not-llm-readable"},
        unit_coverage={"mode": "metadata_short_circuit", "coverage_complete": True},
        page_escalations=[],
        unit_checks=[],
        all_pages_requested=False,
    )
    text = render_pdf_trace("P1R0", progress, result, None)
    assert "## Step 4 (Metadata)" in text
    assert "- short-circuit: yes" in text
    assert "## Step 5 (Escalations)" not in text
    assert "## Step 6 (Unit checks)" not in text
    assert "## Step 7 (Code boundary)" not in text
    assert "## Result" in text


def test_adjudicate_paper_passes_render_trace_fn(monkeypatch):
    captured: dict = {}

    async def fake_dispatch(pipeline, state, ctx, **kwargs):
        captured.update(kwargs)
        captured["ctx"] = ctx
        state._result = TapetumResult(
            pid="P1R0",
            whisker_verdict="pass",
            suggested_verdict="pass",
            confidence=0.9,
            escalated=False,
            tier1_model="fast",
            tier2_model=None,
        )

    monkeypatch.setattr("whisker.llm.adjudicate.dispatch", fake_dispatch)
    monkeypatch.setattr(
        "whisker.llm.adjudicate.PipelinePrompt.load",
        lambda *args, **kwargs: SimpleNamespace(
            services={"fast": "s", "deep": "s", "default": "s"},
        ),
    )
    monkeypatch.setattr(
        "whisker.llm.adjudicate.resolve_runtime_table_contract",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        "whisker.llm.adjudicate.resolve_runtime_code_contract",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        "whisker.llm.adjudicate.hydrate_pipeline_prompt",
        lambda prompt, *args, **kwargs: prompt,
    )
    monkeypatch.setattr(
        "whisker.llm.adjudicate.resolve_pipeline_models",
        lambda services, registry: {name: MagicMock() for name in services},
    )
    monkeypatch.setattr(
        "whisker.llm.adjudicate.AgentBackend",
        lambda *args, **kwargs: MagicMock(),
    )
    monkeypatch.setattr(
        "whisker.llm.adjudicate._build_hooks",
        lambda: {},
    )
    monkeypatch.setattr(
        "whisker.llm.adjudicate.build_pipeline",
        lambda prompt, hooks: [],
    )

    backend = MagicMock()
    asyncio.run(adjudicate_paper("P1R0", backend, trace=True, registry=MagicMock()))
    assert callable(captured.get("render_trace_fn"))
    # Constant guard tag at byte 0 of the system prompt: cross-paper prefix
    # cache and run-to-run identical prompt bytes both depend on it.
    assert captured["ctx"]._guard_tag == GUARD_TAG
    assert captured["ctx"].guard_instruction.startswith(
        f"- Content between <<<{GUARD_TAG}>>>"
    )


def test_set_progress_phase_accounting(monkeypatch):
    times = iter([100.0, 104.2, 110.0])
    monkeypatch.setattr(
        "whisker.llm.pdf_judge.time.monotonic",
        lambda: next(times),
    )
    progress: dict = {}
    _set_progress(progress, phase="page_screen")
    _set_progress(progress, phase="monolith")
    _set_progress(progress, phase="done")
    durations = progress["phase_durations"]
    assert durations["page_screen"] > 0
    assert durations["monolith"] > 0
    json.dumps(durations)
    json.dumps(progress)
