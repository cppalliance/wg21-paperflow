#
# Copyright (c) 2026 Glenn Siegman (glenn@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the generation phase: Step 8 (Cast) and Step 9 (Voice).

The LLM is mocked: a fake ``run_task`` returns canned structured
output per call and records what it was asked, so the tests pin the
casting rules, the-mod.md generation order, prompt assembly, agent
routing, determinism, and error behavior without any model traffic.
"""

from __future__ import annotations

import asyncio

import pytest

from pipeline import PipelinePrompt, StepContext, build_pipeline
from pipeline.errors import ValidationStepError

from agora.casting import MISCONCEPTION_STANCE, _stable_key
from agora.generate import (
    DELETED_BODY,
    _flag_controversial,
    _flag_edited,
    _pure_cast,
    _pure_voice,
    generation_order,
)
from agora.models import (
    CommentOutput,
    EncounterPlan,
    PipelineState,
    Reply,
    ResearchAgentReport,
    ResearchSummary,
    TechnicalAnchor,
    Thread,
)
from agora.pipeline import _STEP_8_CAST, _STEP_9_VOICE, _build_hooks
from agora.roster import MODS, PERSONA_BY_USERNAME

_DOCUMENT = "P4003R2"


# -- Fixture thread ------------------------------------------------------------


def _reply(slot_id: str, **overrides) -> Reply:
    defaults = dict(
        slot_id=slot_id, parent_slot_id=None, depth=0,
        role="signal", brief="Do the thing.",
    )
    defaults.update(overrides)
    return Reply(**defaults)


def _research() -> ResearchSummary:
    report = ResearchAgentReport(
        agent="public_reception", findings="None.", sources=[],
        heat_signal="warm", interest_signal="relevant",
    )
    return ResearchSummary(
        public_reception=report,
        committee_history=report.model_copy(
            update={"agent": "committee_history"}),
        author_ecosystem=report.model_copy(
            update={"agent": "author_ecosystem"}),
    )


def _anchor(anchor_id: str) -> TechnicalAnchor:
    return TechnicalAnchor(
        id=anchor_id,
        kind="load_bearing",
        summary="The benchmark claim the argument stands on.",
        claim_text="We measured a 2x speedup on all workloads.",
        claim_uid=1,
    )


def _thread(
    replies: list[Reply],
    encounters: list[EncounterPlan] = (),
    document: str = _DOCUMENT,
) -> Thread:
    return Thread(
        document=document, paper="P4003", revision=2,
        title="Foo", authors=["A. Author"], audience="EWG",
        date="2026-01-15", paper_type="proposal",
        technical_anchors=[_anchor("a01")],
        research_summary=_research(),
        heat="warm", interest="relevant",
        target_comment_count=len(replies), encounter_count=len(encounters),
        signal_count=sum(1 for r in replies if r.role == "signal"),
        noise_count=sum(1 for r in replies if r.role == "noise"),
        submission_title="[P4003R2] Foo",
        submission_body="The paper claims a 2x speedup on all workloads.",
        submission_link="https://wg21.link/p4003r2",
        replies=list(replies),
        encounters=list(encounters),
    )


def _encounter_plan(slot_ids: list[str]) -> EncounterPlan:
    return EncounterPlan(
        encounter_id="e01", design_tension_id="t01",
        design_tension="Ergonomics versus compile-time cost.",
        position_a="The API is worth the instantiation cost.",
        position_b="The cost lands on every user of the header.",
        resolution="narrowing",
        slot_ids=list(slot_ids),
    )


def _full_thread(document: str = _DOCUMENT) -> Thread:
    """One of everything: teaser, encounter chain, signal, trap pair,
    noise, tangent, mod, deleted."""
    replies = [
        _reply("s01", role="teaser", domain_lens=11,
               anchor_id="a01", carries_quote=True),
        _reply("s02", role="signal", domain_lens=9, carries_code=True),
        _reply("s03", role="encounter", domain_lens=9, depth=3,
               encounter_id="e01"),
        _reply("s04", role="encounter", domain_lens=9, depth=4,
               parent_slot_id="s03", encounter_id="e01"),
        _reply("s05", role="encounter", domain_lens=9, depth=5,
               parent_slot_id="s04", encounter_id="e01"),
        _reply("s06", role="noise", noise_stance=MISCONCEPTION_STANCE,
               brief="Ask the confused question voicing the misreading."),
        _reply("s07", parent_slot_id="s06", depth=1, role="signal",
               domain_lens=12, brief="Gently correct the misreading."),
        _reply("s08", role="noise", noise_stance="process-cynic"),
        _reply("s09", role="tangent"),
        _reply("s10", role="mod"),
        _reply("s11", role="deleted"),
    ]
    return _thread(replies, [_encounter_plan(["s03", "s04", "s05"])],
                   document=document)


# -- Harness -------------------------------------------------------------------


@pytest.fixture(scope="module")
def agora_prompt() -> PipelinePrompt:
    return PipelinePrompt.load("agora", "agora.md")


@pytest.fixture(scope="module")
def specs_by_name(agora_prompt):
    specs = build_pipeline(agora_prompt, _build_hooks())
    return {s.step.name: s for s in specs}


class _FakeAgent:
    def __init__(self, name: str) -> None:
        self.name = name


class _VoiceRecorder:
    """Stands in for ``run_task``: canned output, full call capture."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.fail_on_call: int | None = None

    async def __call__(self, agent, system_prompt, user_message, output_type,
                       *, tools=None, label="", debug_log=None):
        if self.fail_on_call is not None and len(self.calls) + 1 == self.fail_on_call:
            raise RuntimeError("model exploded mid-thread")
        self.calls.append({
            "agent": agent,
            "system": system_prompt,
            "user": user_message,
            "label": label,
        })
        assert output_type is CommentOutput
        slot_id = label.split("(")[-1].rstrip(")")
        return CommentOutput(content=f"generated body for {slot_id}")

    def slot_order(self) -> list[str]:
        return [c["label"].split("(")[-1].rstrip(")") for c in self.calls]


def _generate(thread: Thread, agora_prompt, specs_by_name, monkeypatch,
              recorder: _VoiceRecorder | None = None) -> _VoiceRecorder:
    """Run Cast then Voice over ``thread`` with the mocked model."""
    recorder = recorder or _VoiceRecorder()
    monkeypatch.setattr("agora.generate.run_task", recorder)
    ctx = StepContext(
        prompt=agora_prompt,
        agents={"signal": _FakeAgent("signal"), "noise": _FakeAgent("noise")},
    )
    state = PipelineState(thread=thread)
    asyncio.run(_pure_cast(state, ctx, specs_by_name[_STEP_8_CAST]))
    asyncio.run(_pure_voice(state, ctx, specs_by_name[_STEP_9_VOICE]))
    return recorder


# -- Step 8 - Cast --------------------------------------------------------------


def test_cast_fills_identity_on_every_slot(specs_by_name):
    thread = _full_thread()
    state = PipelineState(thread=thread)
    asyncio.run(_pure_cast(state, StepContext(), specs_by_name[_STEP_8_CAST]))

    assert thread.submission_poster_id
    mod_usernames = {m.username for m in MODS}
    for reply in thread.replies:
        assert reply.character_username in PERSONA_BY_USERNAME, reply.slot_id
        assert reply.is_mod == (reply.character_username in mod_usernames)
        assert reply.is_op == (
            reply.character_username == thread.submission_poster_id
        )


def test_cast_obeys_persona_rules(specs_by_name):
    thread = _full_thread()
    state = PipelineState(thread=thread)
    asyncio.run(_pure_cast(state, StepContext(), specs_by_name[_STEP_8_CAST]))

    by_slot = {r.slot_id: r for r in thread.replies}

    def tier(sid: str) -> str:
        return PERSONA_BY_USERNAME[by_slot[sid].character_username].tier

    assert tier("s01") == "signal"           # teaser
    assert tier("s06") == "learner"          # trap question -> novice
    assert tier("s07") == "signal"           # teaching correction
    assert tier("s08") == "noise"            # noise -> jokester
    assert tier("s10") == "mod"              # mod slot -> human mod
    assert by_slot["s10"].character_username != "AutoModerator"
    # Encounter sides are distinct people alternating turns.
    assert (
        by_slot["s03"].character_username != by_slot["s04"].character_username
    )
    assert (
        by_slot["s03"].character_username == by_slot["s05"].character_username
    )


def test_cast_marks_sharpening_turn_controversial(specs_by_name):
    thread = _full_thread()
    state = PipelineState(thread=thread)
    asyncio.run(_pure_cast(state, StepContext(), specs_by_name[_STEP_8_CAST]))

    by_slot = {r.slot_id: r for r in thread.replies}
    assert by_slot["s04"].controversial is True
    assert by_slot["s03"].controversial is False
    assert by_slot["s05"].controversial is False


def test_flag_edited_is_deterministic_and_hash_gated():
    for document in ("P4003R2", "P1234R0", "P9999R9", "P2996R7"):
        first = _full_thread(document=document)
        second = _full_thread(document=document)
        _flag_edited(first)
        _flag_edited(second)
        flagged_first = [r.slot_id for r in first.replies if r.edited]
        flagged_second = [r.slot_id for r in second.replies if r.edited]
        assert flagged_first == flagged_second
        expect_edit = _stable_key(document, "edited") % 2 == 0
        assert len(flagged_first) == (1 if expect_edit else 0)
        if flagged_first:
            by_slot = {r.slot_id: r for r in first.replies}
            assert by_slot[flagged_first[0]].role == "signal"


def test_flag_edited_without_signal_slots_is_a_no_op():
    thread = _thread([_reply("s01", role="noise", noise_stance="student")])
    _flag_edited(thread)
    assert not any(r.edited for r in thread.replies)


def test_flag_controversial_skips_single_turn_chains():
    replies = [_reply("s01", role="encounter", depth=3, encounter_id="e01")]
    thread = _thread(replies, [_encounter_plan(["s01"])])
    _flag_controversial(thread)
    assert not any(r.controversial for r in thread.replies)


# -- Generation order -----------------------------------------------------------


def test_generation_order_is_teaser_encounters_signal_then_fill():
    order = [r.slot_id for r in generation_order(_full_thread())]
    assert order[0] == "s01"                       # teaser first
    assert order[1:4] == ["s03", "s04", "s05"]     # encounter chain, turn order
    assert order[4:6] == ["s02", "s07"]            # signal, blueprint order
    assert set(order[6:]) == {"s06", "s08", "s09", "s10", "s11"}
    # The trap question comes after its teaching child.
    assert order.index("s06") > order.index("s07")


def test_generation_order_covers_every_slot_once():
    thread = _full_thread()
    order = [r.slot_id for r in generation_order(thread)]
    assert sorted(order) == sorted(r.slot_id for r in thread.replies)


# -- Step 9 - Voice ---------------------------------------------------------------


def test_voice_fills_every_slot(agora_prompt, specs_by_name, monkeypatch):
    thread = _full_thread()
    _generate(thread, agora_prompt, specs_by_name, monkeypatch)
    for reply in thread.replies:
        assert reply.content, reply.slot_id
        assert reply.character_username, reply.slot_id


def test_voice_structure_survives_generation(agora_prompt, specs_by_name,
                                             monkeypatch):
    thread = _full_thread()
    blueprint = {
        r.slot_id: (r.parent_slot_id, r.depth, r.role, r.brief)
        for r in thread.replies
    }
    _generate(thread, agora_prompt, specs_by_name, monkeypatch)
    for reply in thread.replies:
        assert blueprint[reply.slot_id] == (
            reply.parent_slot_id, reply.depth, reply.role, reply.brief,
        )


def test_voice_skips_the_llm_for_deleted_slots(agora_prompt, specs_by_name,
                                               monkeypatch):
    thread = _full_thread()
    recorder = _generate(thread, agora_prompt, specs_by_name, monkeypatch)
    deleted = next(r for r in thread.replies if r.role == "deleted")
    assert deleted.content == DELETED_BODY
    assert deleted.deleted is True
    assert "s11" not in recorder.slot_order()
    assert len(recorder.calls) == len(thread.replies) - 1


def test_voice_writes_in_the_mod_md_order(agora_prompt, specs_by_name,
                                          monkeypatch):
    recorder = _generate(_full_thread(), agora_prompt, specs_by_name,
                         monkeypatch)
    order = recorder.slot_order()
    assert order[0] == "s01"
    assert order[1:4] == ["s03", "s04", "s05"]
    noise_positions = [order.index(s) for s in ("s06", "s08")]
    signal_positions = [order.index(s) for s in ("s02", "s07")]
    assert max(signal_positions) < min(noise_positions)


def test_voice_uses_persona_system_prompts(agora_prompt, specs_by_name,
                                           monkeypatch):
    thread = _full_thread()
    recorder = _generate(thread, agora_prompt, specs_by_name, monkeypatch)
    by_slot = {r.slot_id: r for r in thread.replies}
    for call in recorder.calls:
        slot_id = call["label"].split("(")[-1].rstrip(")")
        persona = PERSONA_BY_USERNAME[by_slot[slot_id].character_username]
        assert call["system"] == persona.system_prompt


def test_voice_routes_agents_by_role(agora_prompt, specs_by_name, monkeypatch):
    thread = _full_thread()
    recorder = _generate(thread, agora_prompt, specs_by_name, monkeypatch)
    by_slot = {r.slot_id: r for r in thread.replies}
    for call in recorder.calls:
        slot_id = call["label"].split("(")[-1].rstrip(")")
        role = by_slot[slot_id].role
        expected = (
            "signal" if role in ("signal", "teaser", "encounter", "mod")
            else "noise"
        )
        assert call["agent"].name == expected, slot_id


def test_voice_prompt_carries_anchor_and_constraints(agora_prompt,
                                                     specs_by_name,
                                                     monkeypatch):
    thread = _full_thread()
    recorder = _generate(thread, agora_prompt, specs_by_name, monkeypatch)
    prompts = {
        c["label"].split("(")[-1].rstrip(")"): c["user"]
        for c in recorder.calls
    }
    # Teaser addresses a01 with a verbatim quote required.
    assert "We measured a 2x speedup on all workloads." in prompts["s01"]
    assert "blockquote" in prompts["s01"]
    # s02 carries code.
    assert "code block" in prompts["s02"]
    # Encounter turns know their side, turn, and resolution.
    assert "position A" in prompts["s03"]
    assert "position B" in prompts["s04"]
    assert "narrowing" in prompts["s05"]
    # Every prompt carries the persona's brief and the step instructions.
    for slot_id, prompt_text in prompts.items():
        assert "## Instructions" in prompt_text, slot_id
        assert "The brief is the assignment." in prompt_text, slot_id


def test_voice_reverse_fits_the_trap_question(agora_prompt, specs_by_name,
                                              monkeypatch):
    thread = _full_thread()
    recorder = _generate(thread, agora_prompt, specs_by_name, monkeypatch)
    prompts = {
        c["label"].split("(")[-1].rstrip(")"): c["user"]
        for c in recorder.calls
    }
    # The confused question sees the correction it will receive.
    assert "generated body for s07" in prompts["s06"]
    assert "Write the confused or leading question" in prompts["s06"]


def test_voice_ancestry_uses_content_when_written_else_brief(
        agora_prompt, specs_by_name, monkeypatch):
    thread = _full_thread()
    recorder = _generate(thread, agora_prompt, specs_by_name, monkeypatch)
    prompts = {
        c["label"].split("(")[-1].rstrip(")"): c["user"]
        for c in recorder.calls
    }
    # s07 (teaching child, written during the signal pass) replies to
    # s06 (the trap question, written later): the parent is unwritten
    # at that point, so its brief appears instead of content.
    assert "Ask the confused question voicing the misreading." in prompts["s07"]
    # s04 replies to s03, which was already written: content appears.
    assert "generated body for s03" in prompts["s04"]


def test_voice_carries_edit_instruction_for_edited_slots(
        agora_prompt, specs_by_name, monkeypatch):
    thread = _full_thread()
    edited_slot = next(r for r in thread.replies if r.role == "signal")
    recorder = _VoiceRecorder()
    monkeypatch.setattr("agora.generate.run_task", recorder)
    ctx = StepContext(
        prompt=agora_prompt,
        agents={"signal": _FakeAgent("signal"), "noise": _FakeAgent("noise")},
    )
    state = PipelineState(thread=thread)
    asyncio.run(_pure_cast(state, ctx, specs_by_name[_STEP_8_CAST]))
    edited_slot.edited = True
    asyncio.run(_pure_voice(state, ctx, specs_by_name[_STEP_9_VOICE]))
    prompt_text = next(
        c["user"] for c in recorder.calls
        if c["label"].endswith(f"({edited_slot.slot_id})")
    )
    assert "EDIT:" in prompt_text


def test_voice_is_deterministic(agora_prompt, specs_by_name, monkeypatch):
    first = _full_thread()
    second = _full_thread()
    _generate(first, agora_prompt, specs_by_name, monkeypatch)
    _generate(second, agora_prompt, specs_by_name, monkeypatch)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_voice_requires_cast_first(agora_prompt, specs_by_name, monkeypatch):
    thread = _full_thread()  # no usernames assigned
    recorder = _VoiceRecorder()
    monkeypatch.setattr("agora.generate.run_task", recorder)
    ctx = StepContext(prompt=agora_prompt, agents={"signal": _FakeAgent("s")})
    state = PipelineState(thread=thread)
    with pytest.raises(ValidationStepError, match="Step 8"):
        asyncio.run(_pure_voice(state, ctx, specs_by_name[_STEP_9_VOICE]))


def test_voice_mid_phase_error_propagates_without_persisting(
        agora_prompt, specs_by_name, monkeypatch):
    thread = _full_thread()
    recorder = _VoiceRecorder()
    recorder.fail_on_call = 3
    monkeypatch.setattr("agora.generate.run_task", recorder)

    class _ExplodingBackend:
        def __getattr__(self, name):  # any persistence attempt fails loudly
            raise AssertionError(
                f"generation steps must not touch the backend ({name})"
            )

    ctx = StepContext(
        prompt=agora_prompt,
        agents={"signal": _FakeAgent("signal"), "noise": _FakeAgent("noise")},
        backend=_ExplodingBackend(),
    )
    state = PipelineState(thread=thread)
    asyncio.run(_pure_cast(state, ctx, specs_by_name[_STEP_8_CAST]))
    with pytest.raises(RuntimeError, match="model exploded"):
        asyncio.run(_pure_voice(state, ctx, specs_by_name[_STEP_9_VOICE]))
    # The thread stays a consistent in-memory partial: the two slots
    # written before the failure have content, everything else is None.
    written = [r for r in thread.replies if r.content]
    assert len(written) == 2


def test_voice_never_sets_votes_scores_or_awards(agora_prompt, specs_by_name,
                                                 monkeypatch):
    thread = _full_thread()
    _generate(thread, agora_prompt, specs_by_name, monkeypatch)
    assert thread.submission_votes is None
    assert thread.generated_at is None
    for reply in thread.replies:
        assert reply.score is None
        assert reply.ordering is None
        assert reply.time_label is None
        assert reply.votes == []
        assert reply.collapsed is False
        assert reply.removed is False
