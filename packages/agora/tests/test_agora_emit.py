#
# Copyright (c) 2026 Glenn Siegman (glenn@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for Step 11 (Emit): the full-artifact write.

The emit step is pure Python, so everything runs on real code paths:
a thread is generated end-to-end through the real Cast and Reactor
passes (Voice is replaced by directly filling bodies — the LLM is the
only mocked piece), then emitted against a real ``SqliteBackend``.
The tests pin that the persisted artifact is the full contract shape,
that validation failures persist nothing, that the write is
deterministic up to ``generated_at``, and that QA findings are
advisory.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from paperstore import SqliteBackend
from pipeline import StepContext
from pipeline.errors import ValidationStepError

from agora.artifact import validate_artifact
from agora.generate import DELETED_BODY, _pure_cast
from agora.models import (
    PipelineState,
    Reply,
    ResearchAgentReport,
    ResearchSummary,
    TechnicalAnchor,
    Thread,
)
from agora.pipeline import _pure_emit
from agora.reactor import _pure_react
from agora.render import render_trace
from agora.roster import roster_usernames

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


def _thread() -> Thread:
    replies = [
        _reply("s01", role="teaser", anchor_id="a01", domain_lens=11),
        _reply("s02", role="signal", domain_lens=9),
        _reply("s03", role="noise", noise_tone="snark",
               noise_stance="process-cynic"),
        _reply("s04", role="mod", depth=1, parent_slot_id="s03"),
        _reply("s05", role="deleted", depth=1, parent_slot_id="s02"),
    ]
    return Thread(
        document=_DOCUMENT, paper="P4003", revision=2,
        title="Foo", authors=["A. Author"], audience="EWG",
        date="2026-01-15", paper_type="proposal",
        technical_anchors=[
            TechnicalAnchor(
                id="a01", kind="load_bearing",
                summary="The benchmark claim the argument stands on.",
                claim_text="We measured a 2x speedup on all workloads.",
                claim_uid=1,
            ),
        ],
        research_summary=_research(),
        heat="warm", interest="relevant",
        target_comment_count=len(replies), encounter_count=0,
        signal_count=2, noise_count=1,
        submission_title="[P4003R2] Foo",
        submission_body="The paper claims a 2x speedup on all workloads.",
        submission_link="https://wg21.link/p4003r2",
        replies=replies,
    )


def _generated_state() -> PipelineState:
    """Run the real Cast and Reactor passes; fill bodies in between."""
    state = PipelineState(thread=_thread(), paper_id=_DOCUMENT,
                          paper_title="Foo")
    asyncio.run(_pure_cast(state, None, None))
    for reply in state.thread.replies:
        if reply.role == "deleted":
            reply.content = DELETED_BODY
            reply.deleted = True
        else:
            reply.content = f"Generated body for {reply.slot_id}."
    asyncio.run(_pure_react(state, None, None))
    return state


def _backend(tmp_path: Path) -> SqliteBackend:
    backend = SqliteBackend(tmp_path)
    backend.upsert_year("2026", [{"paper_id": _DOCUMENT}])
    return backend


def _emit(state: PipelineState, backend: SqliteBackend) -> None:
    ctx = StepContext(backend=backend, pid=_DOCUMENT)
    asyncio.run(_pure_emit(state, ctx, None))


# -- The write -----------------------------------------------------------------


def test_emit_writes_a_validated_full_artifact(tmp_path: Path):
    state = _generated_state()
    backend = _backend(tmp_path)
    _emit(state, backend)

    out_path = backend.get_agora_path(_DOCUMENT)
    assert out_path.exists()
    assert state.artifact_path == str(out_path)

    artifact = backend.read_agora_json(_DOCUMENT)
    validate_artifact(artifact, roster=roster_usernames())
    assert artifact["document"] == _DOCUMENT
    assert artifact["generated_at"]
    assert len(artifact["comments"]) == len(state.thread.replies)


def test_emit_artifact_is_full_not_blueprint(tmp_path: Path):
    """Every comment carries a body, persona, and votes; the blueprint
    embedded for audit carries none of them."""
    state = _generated_state()
    backend = _backend(tmp_path)
    _emit(state, backend)

    artifact = backend.read_agora_json(_DOCUMENT)
    for comment in artifact["comments"]:
        assert comment["body"]
        assert comment["persona"]
        assert isinstance(comment["votes"], list)
    assert artifact["submission_poster_id"]
    assert isinstance(artifact["submission_votes"], list)
    for slot in artifact["blueprint"]["replies"]:
        assert "body" not in slot
        assert "content" not in slot
        assert "votes" not in slot


def test_emit_stamps_generated_at(tmp_path: Path):
    state = _generated_state()
    assert state.thread.generated_at is None
    _emit(state, _backend(tmp_path))
    assert state.thread.generated_at is not None
    assert state.thread.generated_at.tzinfo is not None


# -- Failure persists nothing ----------------------------------------------------


def test_emit_validation_failure_persists_nothing(tmp_path: Path):
    state = _generated_state()
    state.thread.replies[1].content = ""  # violates non-empty body

    backend = _backend(tmp_path)
    with pytest.raises(ValidationStepError):
        _emit(state, backend)

    assert list(tmp_path.rglob("*.agora.json")) == []
    assert state.artifact_path is None


def test_emit_requires_thread(tmp_path: Path):
    state = PipelineState()
    with pytest.raises(AssertionError):
        _emit(state, _backend(tmp_path))


# -- Determinism -----------------------------------------------------------------


def test_emit_is_deterministic_up_to_generated_at(tmp_path: Path):
    """The whole Cast -> fill -> Reactor -> Emit chain re-run from the
    same blueprint produces the identical artifact; ``generated_at``
    (provenance, stamped at write time) is the only exception."""
    first_state = _generated_state()
    second_state = _generated_state()
    _emit(first_state, _backend(tmp_path / "one"))
    _emit(second_state, _backend(tmp_path / "two"))

    first = SqliteBackend(tmp_path / "one").read_agora_json(_DOCUMENT)
    second = SqliteBackend(tmp_path / "two").read_agora_json(_DOCUMENT)
    first.pop("generated_at")
    second.pop("generated_at")
    first["blueprint"].pop("generated_at", None)
    second["blueprint"].pop("generated_at", None)
    assert first == second


# -- QA findings are advisory ----------------------------------------------------


def test_emit_qa_findings_do_not_fail_the_run(tmp_path: Path):
    state = _generated_state()
    state.thread.replies[1].content = (
        "As u/some_invented_redditor said, this is fine."
    )
    backend = _backend(tmp_path)
    _emit(state, backend)

    assert backend.get_agora_path(_DOCUMENT).exists()
    assert state.qa_findings
    assert any("unknown-handle" in f for f in state.qa_findings)


def test_emit_records_empty_qa_findings_when_clean(tmp_path: Path):
    state = _generated_state()
    _emit(state, _backend(tmp_path))
    assert state.qa_findings == []


# -- Trace -----------------------------------------------------------------------


def test_trace_renders_emit_section(tmp_path: Path):
    state = _generated_state()
    _emit(state, _backend(tmp_path))

    out = render_trace(state, stop_step=11)
    assert "## 11. Emit" in out
    assert state.artifact_path in out
    assert "QA findings: none" in out

    assert "## 11. Emit" not in render_trace(state, stop_step=10)


def test_trace_lists_qa_findings(tmp_path: Path):
    state = _generated_state()
    state.thread.replies[1].content = "Only an idiot would ship this."
    _emit(state, _backend(tmp_path))

    out = render_trace(state, stop_step=11)
    assert "QA findings: 1" in out
    assert "personal-attack" in out


# -- End to end ------------------------------------------------------------------
#
# The whole 12-step pipeline through the real ``dispatch``, with the
# LLM mocked at the single seam every call funnels through
# (``AgentBackend.run``). ``research=False`` keeps Step 2 offline, so
# the run is: plan (canned structured outputs) -> cast/voice/react ->
# emit, against a real SqliteBackend.


@pytest.fixture
def _placeholder_api_keys(monkeypatch):
    # ``agora_paper`` resolves SERVICES.toml slots and constructs a
    # WebResearcher even when research is off; placeholder values let
    # slot-binding validation pass without any real credentials.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "placeholder-for-tests")
    monkeypatch.setenv("RUNPOD_API_KEY", "placeholder-for-tests")
    monkeypatch.setenv("VLLM_DEEPSEEK_API_KEY", "placeholder-for-tests")
    monkeypatch.setenv("BRAVE_API_KEY", "placeholder-for-tests")
    # A developer with BRAVE_API_BASE exported would otherwise point the
    # backend at their proxy during tests.
    monkeypatch.delenv("BRAVE_API_BASE", raising=False)


_CANNED_SKELETON_SLOTS = [
    dict(slot_id="s01", depth=0, role="teaser", anchor_id="a01",
         domain_lens=11, brief="Quote anchor a01 and open the thread."),
    dict(slot_id="s02", depth=0, role="signal", domain_lens=9,
         brief="Challenge the benchmark baseline."),
    dict(slot_id="s03", depth=1, parent_slot_id="s02", role="signal",
         domain_lens=12, brief="Back the challenge with a counter-example."),
    dict(slot_id="s04", depth=0, role="noise", noise_tone="snark",
         noise_stance="process-cynic", brief="Groan about committee pace."),
    dict(slot_id="s05", depth=1, parent_slot_id="s04", role="noise",
         noise_tone="earnest", noise_stance="student",
         brief="Ask what LEWG even does."),
    dict(slot_id="s06", depth=0, role="noise", noise_tone="drive-by",
         noise_stance="it's-fine-actually", brief="Shrug at the whole idea."),
]


def _canned_output(output_type):
    """One valid canned output per structured type the pipeline asks for."""
    from agora.models import (
        CalibrationOutput,
        CommentOutput,
        SkeletonOutput,
        SmellTestOutput,
        SubmissionOutput,
    )

    if output_type is SmellTestOutput:
        return SmellTestOutput(
            paper_type="proposal",
            technical_anchors=[
                TechnicalAnchor(
                    id="a01", kind="load_bearing",
                    summary="The benchmark claim the argument stands on.",
                    claim_text="We measured a 2x speedup on all workloads.",
                    claim_uid=1,
                ),
            ],
        )
    if output_type is CalibrationOutput:
        # cold x niche: target in [5, 10], no encounters, zero mod
        # reserve, so signal + noise must equal the target exactly.
        return CalibrationOutput(
            heat="cold", interest="niche",
            target_comment_count=6, encounter_count=0,
            signal_count=3, noise_count=3,
            rationale="A quiet wording paper for a niche audience.",
        )
    if output_type is SubmissionOutput:
        return SubmissionOutput(
            submission_title="[P4003R2] Foo",
            submission_body="The paper claims a 2x speedup on all workloads.",
            submission_link="https://wg21.link/p4003r2",
        )
    if output_type is SkeletonOutput:
        return SkeletonOutput(replies=_CANNED_SKELETON_SLOTS)
    if output_type is CommentOutput:
        return CommentOutput(content="A generated comment body.")
    raise AssertionError(f"Unexpected output type requested: {output_type}")


def test_agora_paper_end_to_end_writes_the_full_artifact(
    tmp_path: Path, monkeypatch, _placeholder_api_keys,
):
    from pipeline.agents import AgentBackend

    from agora import agora_paper

    async def fake_run(self, system_prompt, user_message, output_type,
                       **kwargs):
        return _canned_output(output_type)

    monkeypatch.setattr(AgentBackend, "run", fake_run)

    backend = SqliteBackend(tmp_path)
    backend.upsert_year("2026", [{
        "paper_id": _DOCUMENT, "title": "Foo",
        "authors": ["A. Author"], "target_group": "EWG",
        "document_date": "2026-01-15", "mailing_date": "2026-01",
        "url": "https://example.com/p4003r2.pdf",
    }])
    backend.write_paper_md(_DOCUMENT, "# P4003R2 Foo\n\nA 2x speedup.\n")

    thread = asyncio.run(agora_paper(_DOCUMENT, backend, research=False))

    assert isinstance(thread, Thread)
    artifact = backend.read_agora_json(_DOCUMENT)
    validate_artifact(artifact, roster=roster_usernames())
    assert artifact["document"] == _DOCUMENT
    assert artifact["heat"] == "cold"
    assert len(artifact["comments"]) == len(_CANNED_SKELETON_SLOTS)
    for comment in artifact["comments"]:
        assert comment["body"]
        assert comment["persona"]
    assert artifact["generated_at"]
    assert artifact["blueprint"]["replies"]
