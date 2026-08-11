#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

"""Assay-level integration tests for paper routing in Step 3 (Survey)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from pipeline import StepContext

from assay.paper_routing import RoutingGroup

from assay.models import PipelineState
from assay.pipeline import _custom_survey
from assay.render import render_trace

_FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "routing"


def _read(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


class _Step:
    name = "3. Survey"
    model = "none"
    chunk_tokens = 1000


class _Spec:
    step = _Step()


def _ctx() -> StepContext:
    return StepContext(classifiers={}, default_concurrency=1)


def _state_from_fixture(
    name: str,
    *,
    paper_id: str,
    paper_title: str,
    audience: list[str],
) -> PipelineState:
    return PipelineState(
        paper_id=paper_id,
        paper_md=_read(name),
        paper_title=paper_title,
        audience=audience,
    )


def _run_survey(state: PipelineState) -> None:
    asyncio.run(_custom_survey(state, _ctx(), _Spec()))


def test_administrative_fixture_sets_skipped():
    state = _state_from_fixture(
        "n5044_excerpt.md",
        paper_id="N5044R0",
        paper_title="2024 Fall WG21 Meeting Venue",
        audience=["WG21"],
    )
    _run_survey(state)

    assert state.skipped is True
    assert state.routing is not None
    assert state.routing.is_administrative is True
    assert state.synthesis is not None
    assert state.synthesis.verdict_label == "Skipped"
    assert "Administrative" in (state.synthesis.skip_reason or "")
    assert "routing labels" in (state.synthesis.skip_reason or "").lower()


def test_trace_includes_routing_fields():
    state = _state_from_fixture(
        "n3854.md",
        paper_id="N3854R0",
        paper_title="Variable Templates For Type Traits",
        audience=["LEWG", "LWG"],
    )
    _run_survey(state)

    trace = render_trace(state, 3)
    assert "### Routing" in trace
    assert "LEWG: score=" in trace
    assert "LWG: score=" in trace
    assert "is_administrative:" in trace
    assert "is_performance_focused:" in trace


def test_non_administrative_does_not_skip():
    state = _state_from_fixture(
        "n3854.md",
        paper_id="N3854R0",
        paper_title="Variable Templates For Type Traits",
        audience=["LEWG", "LWG"],
    )
    _run_survey(state)

    assert state.skipped is False
    assert state.routing is not None
    assert not state.routing.is_administrative
    assert RoutingGroup.LEWG in state.routing.groups
    assert state.routing.quadrant_scores[RoutingGroup.LWG] > 0.0
