#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

from __future__ import annotations

from pathlib import Path

import asyncio

from assay.models import PipelineState
from assay.pipeline import _apply_survey_skip, _custom_survey, _run_paper_routing
from assay.render import render_report, render_trace
from pipeline import StepContext, dispatch
from pipeline.prompt import StepHooks, StepPrompt, StepSpec

_FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "routing"


def _read(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def test_run_paper_routing_populates_state():
    state = PipelineState(
        paper_md=_read("n3854.md"),
        audience=["LEWG", "LWG"],
    )
    ctx = StepContext(classifiers={})
    result = _run_paper_routing(state, ctx)
    assert state.routing is result
    assert "LEWG" in result.groups


def test_administrative_fixture_sets_skipped():
    state = PipelineState(
        paper_md=_read("n5044_excerpt.md"),
        audience=["WG21"],
        chunk_map=[],
    )
    ctx = StepContext(classifiers={})
    spec = StepSpec(
        step=StepPrompt(name="3. Survey", number=3, model="none", execution="main"),
        hooks=StepHooks(),
    )
    asyncio.run(_custom_survey(state, ctx, spec))
    assert state.routing is not None
    assert state.routing.is_administrative
    assert state.skipped
    assert state.synthesis is not None
    assert state.synthesis.verdict_label == "Skipped"


def test_skipped_survey_produces_report():
    state = PipelineState(
        paper_md=_read("n5044_excerpt.md"),
        audience=["WG21"],
        chunk_map=[],
    )
    ctx = StepContext(classifiers={})
    spec = StepSpec(
        step=StepPrompt(name="3. Survey", number=3, model="none", execution="main"),
        hooks=StepHooks(),
    )
    asyncio.run(_custom_survey(state, ctx, spec))
    assert state.skipped
    state.report = render_report(state, "")
    assert state.report
    assert "## Classification" in state.report
    assert "Administrative" in state.report


def test_apply_survey_skip_sets_synthesis():
    state = PipelineState()
    asyncio.run(_apply_survey_skip(state, "test reason", "reference", {"lines": 1}))
    assert state.synthesis.verdict_label == "Skipped"
    assert state.skipped


def test_dispatch_skips_steps_when_state_skipped():
    calls: list[str] = []

    async def step0(state, ctx, spec):
        calls.append("0")

    async def step1(state, ctx, spec):
        calls.append("1")

    state = PipelineState(skipped=True)
    pipeline = [
        StepSpec(
            step=StepPrompt(name="0. A", number=0, model="none", execution="main"),
            hooks=StepHooks(custom=step0),
        ),
        StepSpec(
            step=StepPrompt(name="1. B", number=1, model="none", execution="main"),
            hooks=StepHooks(custom=step1),
        ),
    ]
    asyncio.run(dispatch(pipeline, state, StepContext()))
    assert calls == []


def test_trace_includes_routing_fields():
    from assay.pipeline import _run_paper_routing

    state = PipelineState(
        paper_md=_read("n3854.md"),
        audience=["LEWG", "LWG"],
    )
    _run_paper_routing(state, StepContext(classifiers={}))
    trace = render_trace(state, 3)
    assert "### Routing" in trace
    assert "LEWG" in trace
    assert "sentence_count:" in trace
