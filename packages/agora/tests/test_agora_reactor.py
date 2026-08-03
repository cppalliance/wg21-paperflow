"""Tests for Step 10 (Reactor): the deterministic per-persona vote pass.

The pass is a pure heuristic — no LLM — so everything here runs on
real code paths: the tests pin the artifact invariants (at most one
vote per persona per target, roster-only voters, no self-votes, no
AutoModerator), the float dynamics (each reactor float moves the
upvote probability the documented way), the the-mod.md vote texture
on a crafted thread, determinism, and the promise that scores and
timing stay untouched.
"""

from __future__ import annotations

import asyncio

import pytest

from agora.models import (
    PipelineState,
    Reply,
    ResearchAgentReport,
    ResearchSummary,
    TechnicalAnchor,
    Thread,
)
from agora.reactor import (
    SUBMISSION_TARGET,
    _pure_react,
    decide_vote,
    react_thread,
    upvote_probability,
)
from agora.roster import PERSONA_BY_USERNAME, Persona, roster_usernames

_DOCUMENT = "P4003R2"


# -- Fixture thread ------------------------------------------------------------


def _reply(slot_id: str, **overrides) -> Reply:
    defaults = dict(
        slot_id=slot_id, parent_slot_id=None, depth=0,
        role="signal", brief="Do the thing.",
        character_username="monomorphic_dan",
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


def _thread(
    replies: list[Reply],
    document: str = _DOCUMENT,
    heat: str = "warm",
) -> Thread:
    return Thread(
        document=document, paper="P4003", revision=2,
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
        heat=heat, interest="relevant",
        target_comment_count=len(replies), encounter_count=0,
        signal_count=sum(1 for r in replies if r.role == "signal"),
        noise_count=sum(1 for r in replies if r.role == "noise"),
        submission_title="[P4003R2] Foo",
        submission_body="The paper claims a 2x speedup on all workloads.",
        submission_link="https://wg21.link/p4003r2",
        submission_poster_id="monomorphic_dan",
        replies=list(replies),
    )


def _mixed_thread(document: str = _DOCUMENT, heat: str = "warm") -> Thread:
    replies = [
        _reply("s01", role="teaser", content="The claim is load-bearing."),
        _reply("s02", role="signal", character_username="async_skeptic",
               content="The benchmark section does not hold up."),
        _reply("s03", role="noise", noise_tone="snark",
               character_username="segfault_enjoyer_69",
               content="2x speedup and all I have to do is recompile the"
               " universe."),
        _reply("s04", role="noise", noise_tone="earnest",
               character_username="not_a_real_cpp_dev",
               content="Wait, does this apply to constexpr too?"),
        _reply("s05", role="mod", character_username="paper_trail_2019",
               is_mod=True, content="Rule 3. Take a breath."),
        _reply("s06", role="deleted", character_username="segfault_enjoyer_69",
               content="[deleted]", deleted=True),
    ]
    return _thread(replies, document=document, heat=heat)


def _persona(**floats) -> Persona:
    defaults = dict(
        upvote_bias=0.5, contrarianism=0.5, snark_affinity=0.5,
    )
    defaults.update(floats)
    return Persona(
        username="crafted_voter", archetype="jokester", tier="noise",
        system_prompt="A crafted test voter.", bio="Crafted.",
        **defaults,
    )


# -- Artifact invariants -------------------------------------------------------


def test_at_most_one_vote_per_persona_per_target():
    thread = _mixed_thread()
    react_thread(thread)

    assert thread.submission_votes is not None
    submission_voters = [v.persona for v in thread.submission_votes]
    assert len(submission_voters) == len(set(submission_voters))
    for reply in thread.replies:
        voters = [v.persona for v in reply.votes]
        assert len(voters) == len(set(voters)), reply.slot_id


def test_voters_are_roster_usernames_with_valid_directions():
    thread = _mixed_thread()
    react_thread(thread)

    roster = roster_usernames()
    all_votes = list(thread.submission_votes or [])
    for reply in thread.replies:
        all_votes.extend(reply.votes)
    assert all_votes
    for vote in all_votes:
        assert vote.persona in roster
        assert vote.direction in (1, -1)


def test_automoderator_never_votes():
    thread = _mixed_thread(heat="thermonuclear")
    react_thread(thread)

    voters = {v.persona for v in thread.submission_votes or []}
    for reply in thread.replies:
        voters |= {v.persona for v in reply.votes}
    assert "AutoModerator" not in voters


def test_no_self_votes():
    thread = _mixed_thread(heat="thermonuclear")
    react_thread(thread)

    assert all(
        v.persona != thread.submission_poster_id
        for v in thread.submission_votes or []
    )
    for reply in thread.replies:
        assert all(v.persona != reply.character_username for v in reply.votes)


def test_submission_votes_are_produced():
    thread = _mixed_thread()
    react_thread(thread)

    assert thread.submission_votes
    up = sum(1 for v in thread.submission_votes if v.direction == 1)
    assert up > len(thread.submission_votes) - up


# -- Float dynamics ------------------------------------------------------------


def test_upvote_bias_raises_probability_everywhere():
    generous = _persona(upvote_bias=0.9)
    stingy = _persona(upvote_bias=0.1)
    for snarky, consensus in ((False, False), (True, False), (False, True)):
        assert upvote_probability(
            generous, snarky=snarky, consensus=consensus,
        ) > upvote_probability(stingy, snarky=snarky, consensus=consensus)


def test_snark_affinity_swings_snarky_targets_only():
    lover = _persona(snark_affinity=0.95)
    hater = _persona(snark_affinity=0.05)
    assert upvote_probability(
        lover, snarky=True, consensus=False,
    ) > upvote_probability(hater, snarky=True, consensus=False)
    assert upvote_probability(
        lover, snarky=False, consensus=False,
    ) == upvote_probability(hater, snarky=False, consensus=False)


def test_contrarianism_penalizes_consensus_targets_only():
    contrarian = _persona(contrarianism=0.9)
    agreeable = _persona(contrarianism=0.1)
    assert upvote_probability(
        contrarian, snarky=False, consensus=True,
    ) < upvote_probability(agreeable, snarky=False, consensus=True)
    assert upvote_probability(
        contrarian, snarky=False, consensus=False,
    ) == upvote_probability(agreeable, snarky=False, consensus=False)


def test_deleted_penalty_and_clamping():
    voter = _persona(upvote_bias=0.5)
    assert upvote_probability(
        voter, snarky=False, consensus=False, deleted=True,
    ) < upvote_probability(voter, snarky=False, consensus=False)
    sunny = _persona(upvote_bias=1.0, snark_affinity=1.0)
    grim = _persona(upvote_bias=0.0, contrarianism=1.0, snark_affinity=0.0)
    assert upvote_probability(sunny, snarky=True, consensus=False) <= 0.95
    assert upvote_probability(
        grim, snarky=True, consensus=True, deleted=True,
    ) >= 0.05


def test_decide_vote_abstains_below_participation():
    voter = _persona()
    assert decide_vote(
        _DOCUMENT, voter, "s01",
        participation=0.0, snarky=False, consensus=False,
    ) is None
    vote = decide_vote(
        _DOCUMENT, voter, "s01",
        participation=1.0, snarky=False, consensus=False,
    )
    assert vote is not None and vote.persona == "crafted_voter"


# -- the-mod.md texture --------------------------------------------------------


def test_snark_outscores_the_technical_take():
    """the-mod.md section 4: the quip beats the best technical comment,
    which can sit buried below zero. The pass is deterministic, so one
    document exhibiting the dynamic exhibits it forever; this one puts
    the quip net-positive and the strong signal take net-negative."""
    thread = _mixed_thread(document="P3125R5", heat="thermonuclear")
    react_thread(thread)

    def net(slot_id: str) -> int:
        reply = next(r for r in thread.replies if r.slot_id == slot_id)
        return sum(v.direction for v in reply.votes)

    snark_net = net("s03")
    signal_net = net("s02")
    deleted_net = net("s06")
    assert snark_net > 0
    assert signal_net < 0
    assert snark_net > signal_net
    assert deleted_net < 0


def test_deeper_replies_draw_fewer_votes():
    """Participation decays with depth: a top-level comment is seen by
    everyone, a depth-5 turn only by whoever expanded the subthread."""
    shallow = [
        _reply(f"s{i:02d}", role="signal") for i in range(1, 9)
    ]
    parent = _reply("s99", role="signal")
    deep = [
        _reply(f"s{i:02d}", role="signal", depth=5, parent_slot_id="s99")
        for i in range(9, 17)
    ]
    thread = _thread(shallow + [parent] + deep, heat="thermonuclear")
    react_thread(thread)

    def total(slots: list[Reply]) -> int:
        return sum(len(r.votes) for r in slots)

    assert total(thread.replies[:8]) > total(thread.replies[-8:])


def test_hotter_threads_draw_more_votes():
    cold = _mixed_thread(heat="cold")
    thermo = _mixed_thread(heat="thermonuclear")
    react_thread(cold)
    react_thread(thermo)

    def total(thread: Thread) -> int:
        return len(thread.submission_votes or []) + sum(
            len(r.votes) for r in thread.replies
        )

    assert total(cold) < total(thermo)


# -- Determinism and untouched fields -------------------------------------------


def test_reactor_is_deterministic():
    first = _mixed_thread()
    second = _mixed_thread()
    react_thread(first)
    react_thread(second)

    assert first.submission_votes == second.submission_votes
    for a, b in zip(first.replies, second.replies):
        assert a.votes == b.votes


def test_no_score_ordering_or_timing_written():
    thread = _mixed_thread()
    react_thread(thread)

    assert thread.generated_at is None
    for reply in thread.replies:
        assert reply.score is None
        assert reply.ordering is None
        assert reply.time_label is None


def test_pure_react_requires_thread():
    state = PipelineState()
    with pytest.raises(AssertionError):
        asyncio.run(_pure_react(state, None, None))


def test_pure_react_fills_votes():
    state = PipelineState()
    state.thread = _mixed_thread()
    asyncio.run(_pure_react(state, None, None))
    assert state.thread.submission_votes
    assert any(reply.votes for reply in state.thread.replies)


def test_submission_target_cannot_collide_with_slot_ids():
    thread = _mixed_thread()
    assert all(r.slot_id != SUBMISSION_TARGET for r in thread.replies)


def test_fixture_usernames_are_real_roster_entries():
    thread = _mixed_thread()
    for reply in thread.replies:
        assert reply.character_username in PERSONA_BY_USERNAME
