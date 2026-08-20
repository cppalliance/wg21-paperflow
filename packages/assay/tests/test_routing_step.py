#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

"""Assay-level integration tests for paper routing in Step 3 (Survey)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from pipeline import StepContext
from pipeline.classifier_backends import NliCrossEncoderBackend

from assay.paper_routing import RoutingGroup
from assay.paper_routing.learned_aggregate import learned_model_available

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


class _StubNli(NliCrossEncoderBackend):
    """Canned NLI backend: does not load weights."""

    def __init__(self) -> None:
        self.model_id = "stub/nli"

    def nli_entailment_pairs(self, pairs):
        return [
            {"entailment": 0.9, "neutral": 0.0, "contradiction": 0.0} for _ in pairs
        ]


def _ctx_nli() -> StepContext:
    return StepContext(
        classifiers={"selector": _StubNli()},
        default_concurrency=1,
    )


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


def test_administrative_fixture_routes_but_does_not_skip():
    state = _state_from_fixture(
        "n5044_excerpt.md",
        paper_id="N5044R0",
        paper_title="2024 Fall WG21 Meeting Venue",
        audience=["WG21"],
    )
    _run_survey(state)

    assert state.skipped is False
    assert state.routing is not None
    assert state.routing.is_administrative is True
    assert state.synthesis is None


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
    assert "- LEWG: score=" in trace
    assert "- LWG: score=" in trace
    assert "RoutingGroup." not in trace
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


def test_survey_learned_path_runs_with_stub_nli(monkeypatch: pytest.MonkeyPatch):
    called: list[bool] = []

    def _fake_predict(sentences, *, audience=None, classifiers=None):
        del sentences, audience, classifiers
        called.append(True)
        empty = {group: 0.0 for group in RoutingGroup}
        return {RoutingGroup.LEWG: 0.9}, {**empty, RoutingGroup.LEWG: 0.9}

    monkeypatch.setattr(
        "assay.paper_routing.routing.predict_learned_groups",
        _fake_predict,
    )
    monkeypatch.setattr(
        "assay.paper_routing.routing.learned_model_available",
        lambda classifiers: True,
    )
    state = _state_from_fixture(
        "n3854.md",
        paper_id="N3854R0",
        paper_title="Variable Templates For Type Traits",
        audience=["LEWG", "LWG"],
    )
    asyncio.run(_custom_survey(state, _ctx_nli(), _Spec()))
    assert called == [True]
    assert state.routing is not None
    assert RoutingGroup.LEWG in state.routing.groups


def test_survey_learned_path_loads_committed_nli_joblib():
    nli_provenance = (
        Path(__file__).resolve().parents[1] / "data" / "nli" / "provenance.json"
    )
    if not nli_provenance.is_file():
        pytest.skip("committed nli provenance.json missing; retrain on other machine")
    assert learned_model_available(_StubNli())
    state = _state_from_fixture(
        "n3854.md",
        paper_id="N3854R0",
        paper_title="Variable Templates For Type Traits",
        audience=["LEWG", "LWG"],
    )
    asyncio.run(_custom_survey(state, _ctx_nli(), _Spec()))
    assert state.routing is not None
    assert not state.routing.is_administrative
    assert state.routing.groups
