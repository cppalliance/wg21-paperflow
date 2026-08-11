#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

"""Tests for agora pipeline guards, subreddit routing, Step 0 fail-fast,
blueprint validation, the-mod.md prompt injection, and the research toggle."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from paperstore import SqliteBackend

from agora import agora_paper
from agora.errors import (
    PaperNotConvertedError,
    PaperNotFoundError,
)
from pipeline import PipelinePrompt, StepContext, build_pipeline
from pipeline.errors import ValidationStepError
from agora.models import (
    EncounterPlan,
    PipelineState,
    Reply,
    ResearchAgentReport,
    SkeletonOutput,
    SkeletonReply,
    TechnicalAnchor,
)
from agora.pipeline import (
    _STEP_2_RESEARCH,
    _build_hooks,
    _extract_skeleton,
    _guard_encounter_count_positive,
    _prepare_calibrate,
    _prepare_encounters,
    _prepare_skeleton,
    _prepare_smell_test,
    _prepare_submission,
    _pure_research,
    _pure_research_disabled,
    _route_committee,
    _split_paper_id,
    _validate_blueprint,
)


@pytest.fixture(autouse=True)
def _placeholder_api_keys(monkeypatch):
    # Tests in this module invoke ``agora_paper`` to exercise error
    # paths unrelated to authentication. ``pipeline.resolve_pipeline_models``
    # now validates env vars at slot-binding; placeholder values let
    # the validation pass so the test reaches the path it actually
    # cares about. The fail-fast contract itself is covered in
    # ``packages/pipeline/tests/test_services.py``.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "placeholder-for-tests")
    monkeypatch.setenv("RUNPOD_API_KEY", "placeholder-for-tests")
    monkeypatch.setenv("VLLM_DEEPSEEK_API_KEY", "placeholder-for-tests")


def test_guard_encounter_count_skips_when_zero():
    s = PipelineState(encounter_count=0)
    assert _guard_encounter_count_positive(s) is False


def test_guard_encounter_count_skips_when_none():
    s = PipelineState()
    assert _guard_encounter_count_positive(s) is False


def test_guard_encounter_count_runs_when_positive():
    s = PipelineState(encounter_count=2)
    assert _guard_encounter_count_positive(s) is True


@pytest.mark.parametrize(
    "audience,expected",
    [
        ("EWG", "ewg"),
        ("EWGI", "ewg"),
        ("LEWG", "lewg"),
        ("LEWGI", "lewg"),
        ("CWG", "cwg"),
        ("LWG", "lwg"),
        ("SG21", "ewg"),
        ("Plenary", "ewg"),
        ("EWG, LEWG", "ewg"),  # first wins
        ("LEWG/LEWGI", "lewg"),
        ("", "ewg"),  # default
        ("unknown", "ewg"),
    ],
)
def test_route_committee(audience: str, expected: str):
    assert _route_committee(audience) == expected


@pytest.mark.parametrize(
    "pid,expected",
    [
        ("P4003R2", ("P4003", 2)),
        ("p4003r0", ("P4003", 0)),
        ("P12345R14", ("P12345", 14)),
        ("D1234R0", ("D1234R0", 0)),  # D-prefix: not a P-paper, no split
    ],
)
def test_split_paper_id(pid: str, expected: tuple[str, int]):
    assert _split_paper_id(pid) == expected


def test_agora_paper_unknown_pid_raises(tmp_path: Path):
    backend = SqliteBackend(tmp_path)
    with pytest.raises(PaperNotFoundError):
        asyncio.run(agora_paper("PXXXXR0", backend))


def test_agora_paper_not_converted_raises(tmp_path: Path):
    backend = SqliteBackend(tmp_path)
    backend.upsert_year("2026", [{"paper_id": "P1234R0"}])
    with pytest.raises(PaperNotConvertedError):
        asyncio.run(agora_paper("P1234R0", backend))


# -- Blueprint validation ------------------------------------------------


def _anchor(anchor_id: str) -> TechnicalAnchor:
    return TechnicalAnchor(
        id=anchor_id,
        kind="load_bearing",
        summary="The benchmark claim the argument stands on.",
        claim_text="We measured a 2x speedup.",
        claim_uid=1,
    )


def _reply(slot_id: str, **overrides) -> Reply:
    fields = {
        "slot_id": slot_id,
        "parent_slot_id": None,
        "depth": 0,
        "role": "signal",
        "brief": "Address the anchor from a domain lens.",
    }
    fields.update(overrides)
    return Reply(**fields)


def _encounter_plan(slot_ids: list[str]) -> EncounterPlan:
    return EncounterPlan(
        encounter_id="e01",
        design_tension_id="t01",
        design_tension="Ergonomics versus compile-time cost.",
        position_a="The API is worth the instantiation cost.",
        position_b="The cost lands on every user of the header.",
        resolution="narrowing",
        slot_ids=slot_ids,
    )


def test_validate_blueprint_unaddressed_anchor_raises():
    state = PipelineState(
        technical_anchors=[_anchor("a01"), _anchor("a02")],
        interest="niche",
    )
    replies = [_reply("s01", anchor_id="a01", domain_lens=1)]
    with pytest.raises(ValidationStepError, match="a02"):
        _validate_blueprint(state, replies, [])


def test_validate_blueprint_orphan_encounter_slot_raises():
    state = PipelineState(interest="niche")
    replies = [_reply("s01", role="encounter", depth=3)]
    with pytest.raises(ValidationStepError, match="s01"):
        _validate_blueprint(state, replies, [])


def test_validate_blueprint_orphan_raises_even_with_plans_present():
    state = PipelineState(interest="niche")
    replies = [
        _reply("s01", role="encounter", depth=3),
        _reply("s02", role="encounter", depth=4),
    ]
    plans = [_encounter_plan(["s01"])]
    with pytest.raises(ValidationStepError, match="s02"):
        _validate_blueprint(state, replies, plans)


def test_validate_blueprint_lens_floor_shortfall_raises():
    state = PipelineState(
        technical_anchors=[_anchor("a01")],
        interest="magnetic",
    )
    replies = [
        _reply("s01", anchor_id="a01", domain_lens=1),
        _reply("s02", domain_lens=2),
    ]
    with pytest.raises(ValidationStepError, match="magnetic"):
        _validate_blueprint(state, replies, [])


def test_validate_blueprint_case_c_without_prior_raises():
    state = PipelineState(interest="niche", revision_case="C")
    with pytest.raises(ValidationStepError, match="prior_revision"):
        _validate_blueprint(state, [], [])


def test_validate_blueprint_composition_drift_raises():
    # The 2026-07-17 drift shape: plan said 6 signal / 24 noise, the
    # skeleton delivered 16 / 12.
    state = PipelineState(interest="niche", signal_count=6, noise_count=24)
    replies = [_reply(f"s{n:02d}") for n in range(1, 17)] + [
        _reply(f"s{n:02d}", role="noise") for n in range(17, 29)
    ]
    with pytest.raises(ValidationStepError, match="signal-class"):
        _validate_blueprint(state, replies, [])


def test_validate_blueprint_composition_within_tolerance_ok():
    # Teasers count as signal-class, tangents as noise-class; drift of
    # +2 signal / -5 noise sits inside the +/-25%-or-2 band.
    state = PipelineState(interest="niche", signal_count=10, noise_count=20)
    replies = (
        [_reply(f"s{n:02d}") for n in range(1, 12)]
        + [_reply("s12", role="teaser")]
        + [_reply(f"s{n:02d}", role="noise") for n in range(13, 26)]
        + [_reply(f"s{n:02d}", role="tangent") for n in range(26, 28)]
    )
    _validate_blueprint(state, replies, [])


def test_validate_blueprint_composition_skipped_without_plan():
    state = PipelineState(interest="niche")
    replies = [_reply(f"s{n:02d}") for n in range(1, 17)]
    _validate_blueprint(state, replies, [])


def test_validate_blueprint_valid_thread_passes():
    state = PipelineState(
        technical_anchors=[_anchor("a01")],
        interest="magnetic",
    )
    replies = [
        _reply("s01", anchor_id="a01", domain_lens=1),
        _reply("s02", role="teaser", domain_lens=8, depth=0),
        _reply("s03", domain_lens=11, depth=1),
        _reply("s04", role="encounter", depth=3, encounter_id="e01"),
        _reply("s05", role="encounter", depth=4, encounter_id="e01"),
        _reply("s06", role="noise", noise_tone="sarcastic",
               noise_stance="didn't-read", depth=0),
    ]
    plans = [_encounter_plan(["s04", "s05"])]
    _validate_blueprint(state, replies, plans)


def test_validate_blueprint_no_anchors_passes_vacuously():
    """Process documents legitimately plan zero anchors."""
    state = PipelineState(interest="niche")
    _validate_blueprint(state, [_reply("s01", role="noise")], [])


def test_validate_blueprint_cyclic_parent_chain_raises():
    state = PipelineState(interest="niche")
    replies = [
        _reply("s01", role="noise", parent_slot_id="s02", depth=1),
        _reply("s02", role="noise", parent_slot_id="s01", depth=2),
    ]
    with pytest.raises(ValidationStepError, match="cyclic"):
        _validate_blueprint(state, replies, [])


def test_validate_blueprint_self_parent_raises():
    state = PipelineState(interest="niche")
    replies = [_reply("s01", role="noise", parent_slot_id="s01", depth=1)]
    with pytest.raises(ValidationStepError, match="cyclic"):
        _validate_blueprint(state, replies, [])


def test_validate_blueprint_trap_without_correction_child_raises():
    state = PipelineState(interest="niche")
    replies = [
        _reply("s01", role="noise", noise_stance="misconception"),
        _reply("s02", role="noise", parent_slot_id="s01", depth=1),
    ]
    with pytest.raises(ValidationStepError, match="misconception-trap"):
        _validate_blueprint(state, replies, [])


def test_validate_blueprint_trap_with_signal_child_passes():
    state = PipelineState(interest="niche")
    replies = [
        _reply("s01", role="noise", noise_stance="misconception"),
        _reply("s02", role="signal", parent_slot_id="s01", depth=1),
    ]
    _validate_blueprint(state, replies, [])


def test_validate_blueprint_misconception_on_non_noise_role_raises():
    state = PipelineState(interest="niche")
    replies = [_reply("s01", role="signal", noise_stance="misconception")]
    with pytest.raises(ValidationStepError, match="role 'noise'"):
        _validate_blueprint(state, replies, [])


# -- the-mod.md prompt injection -------------------------------------------


@pytest.fixture(scope="module")
def agora_prompt() -> PipelinePrompt:
    return PipelinePrompt.load("agora", "agora.md")


@pytest.fixture()
def prepare_ctx(agora_prompt: PipelinePrompt) -> StepContext:
    return StepContext(prompt=agora_prompt)


def test_smell_test_prompt_carries_mod_reference(prepare_ctx: StepContext):
    message = _prepare_smell_test(PipelineState(), prepare_ctx)
    assert "## The Mod Reference (the-mod.md)" in message
    assert "1.4c Falsification requirement" in message
    assert "2.1d Process document classification" in message


def test_calibrate_prompt_carries_mod_reference(prepare_ctx: StepContext):
    message = _prepare_calibrate(PipelineState(), prepare_ctx)
    assert "2.3 Heat tier" in message
    assert "2.4 Interest tier" in message
    assert "### 4. Thread Architecture" in message


def test_submission_prompt_carries_mod_reference(prepare_ctx: StepContext):
    message = _prepare_submission(PipelineState(), prepare_ctx)
    assert "### 3. The Submission Post" in message
    assert "Update-thread rules" in message


def test_skeleton_prompt_carries_mod_reference(prepare_ctx: StepContext):
    message = _prepare_skeleton(PipelineState(), prepare_ctx)
    assert "Table C: Domain" in message
    assert "Stock phrases" in message
    assert "5b. Mod Presence" in message
    assert "1.4d Anchor priority routing" in message


def test_encounters_prompt_carries_mod_reference(prepare_ctx: StepContext):
    message = _prepare_encounters(PipelineState(), prepare_ctx)
    assert "### 11. The Encounter" in message
    assert "Never more than 5 exchanges" in message


def test_extract_skeleton_widens_slots_to_replies():
    state = PipelineState()
    output = SkeletonOutput(
        replies=[
            SkeletonReply(slot_id="s01", depth=0, role="teaser", brief="hook"),
            SkeletonReply(
                slot_id="s02", parent_slot_id="s01", depth=1, role="noise",
                brief="react", noise_tone="snark", noise_stance="process-cynic",
            ),
        ],
        encounter_slot_groups=[["s03", "s04"]],
    )
    _extract_skeleton(state, output)
    assert state.replies is not None
    assert all(isinstance(r, Reply) for r in state.replies)
    assert state.replies[1].noise_tone == "snark"
    assert state.replies[1].content is None
    assert state.replies[1].votes == []
    assert state.encounter_slot_groups == [["s03", "s04"]]


def test_prepare_is_deterministic(prepare_ctx: StepContext):
    state = PipelineState(
        technical_anchors=[_anchor("a01")],
        interest="magnetic",
        heat="hot",
    )
    first = _prepare_skeleton(state, prepare_ctx)
    second = _prepare_skeleton(state, prepare_ctx)
    assert first == second


# -- Research toggle ---------------------------------------------------------


def test_build_hooks_default_keeps_research():
    hooks = _build_hooks()
    assert hooks[_STEP_2_RESEARCH].custom is _pure_research


def test_build_hooks_research_off_swaps_stub():
    hooks = _build_hooks(research=False)
    assert hooks[_STEP_2_RESEARCH].custom is _pure_research_disabled


def test_research_disabled_records_empty_summary(prepare_ctx: StepContext):
    state = PipelineState()
    asyncio.run(_pure_research_disabled(state, prepare_ctx, None))
    summary = state.research_summary
    assert summary is not None
    assert "research disabled" in summary.public_reception.findings
    assert summary.committee_history.agent == "committee_history"


def test_research_without_web_tools_degrades(prepare_ctx: StepContext):
    """Research on, but no web tools registered: empty summary, no raise."""
    hooks = _build_hooks()
    specs = build_pipeline(prepare_ctx.prompt, hooks)
    spec = next(s for s in specs if s.step.name == _STEP_2_RESEARCH)
    state = PipelineState()
    asyncio.run(_pure_research(state, prepare_ctx, spec))
    summary = state.research_summary
    assert summary is not None
    assert "no findings" in summary.public_reception.findings


def test_research_enabled_dispatches_all_three_agents(
    agora_prompt: PipelinePrompt, monkeypatch,
):
    calls: list[str] = []

    async def fake_run_task(agent, system_prompt, user_message, output_type,
                            **kwargs):
        calls.append(kwargs.get("label", ""))
        return ResearchAgentReport(
            agent="public_reception",
            findings="stub findings",
            sources=[],
            heat_signal="warm",
            interest_signal="relevant",
        )

    monkeypatch.setattr("agora.pipeline.run_task", fake_run_task)
    hooks = _build_hooks()
    specs = build_pipeline(agora_prompt, hooks)
    spec = next(s for s in specs if s.step.name == _STEP_2_RESEARCH)
    ctx = StepContext(
        prompt=agora_prompt,
        agents={spec.step.model: object()},
        tool_registry={
            "deep_search": lambda *a, **k: None,
            "web_fetch": lambda *a, **k: None,
        },
    )
    state = PipelineState()
    asyncio.run(_pure_research(state, ctx, spec))
    assert len(calls) == 3
    summary = state.research_summary
    assert summary is not None
    # Slot names are forced even if the model echoed something else.
    assert summary.committee_history.agent == "committee_history"
    assert summary.author_ecosystem.agent == "author_ecosystem"


def test_paperstore_agora_round_trip(tmp_path: Path):
    """write_agora_json/read_agora_json/get_agora_path/clear_agora behave."""
    backend = SqliteBackend(tmp_path)
    backend.upsert_year("2026", [{"paper_id": "P1234R0"}])
    payload = {"document": "P1234R0", "replies": []}
    out_path = backend.write_agora_json("P1234R0", payload)
    assert out_path.exists()
    assert out_path.name == "p1234r0.agora.json"

    got = backend.read_agora_json("P1234R0")
    assert got == payload

    p = backend.get_agora_path("P1234R0")
    assert p == out_path

    backend.clear_agora("P1234R0")
    assert not p.exists()
