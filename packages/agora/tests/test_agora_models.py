#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

"""Tests for agora domain models and the analysis/generation field split."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from agora.models import (
    ENCOUNTER_TURNS,
    MOD_ACTION_RESERVE,
    SIGNAL_RATIO_FLOOR,
    CalibrationOutput,
    DesignTension,
    EncounterPlan,
    EncountersOutput,
    PipelineState,
    Reply,
    ResearchAgentReport,
    ResearchSummary,
    SkeletonOutput,
    SkeletonReply,
    SmellTestOutput,
    SubmissionOutput,
    TechnicalAnchor,
    Thread,
    Vote,
)


def _anchor(id_="a01"):
    return TechnicalAnchor(
        id=id_,
        kind="load_bearing",
        summary="X is the central claim.",
        claim_text="X is the central claim.",
        claim_uid=1,
    )


def _research():
    rep = ResearchAgentReport(
        agent="public_reception",
        findings="No prior mentions.",
        sources=[],
        heat_signal="warm",
        interest_signal="relevant",
    )
    return ResearchSummary(
        public_reception=rep,
        committee_history=rep.model_copy(update={"agent": "committee_history"}),
        author_ecosystem=rep.model_copy(update={"agent": "author_ecosystem"}),
    )


def test_technical_anchor_round_trip():
    a = _anchor()
    assert TechnicalAnchor.model_validate(a.model_dump()) == a
    assert a.claim_uid == 1


def test_design_tension_optional_anchor():
    t = DesignTension(id="t01", description="A vs B")
    assert t.anchor_id is None
    t2 = DesignTension(id="t02", description="C vs D", anchor_id="a01")
    assert t2.anchor_id == "a01"


def test_reply_required_fields_only_analysis():
    r = Reply(slot_id="s01", parent_slot_id=None, depth=0,
              role="signal", brief="Address anchor a01.")
    assert r.content is None
    assert r.character_username is None
    assert r.score is None
    assert r.votes == []
    assert r.edited is False
    assert r.is_op is False


def test_vote_direction_literal():
    Vote(persona="ranges_andy", direction=1)
    Vote(persona="ranges_andy", direction=-1)
    with pytest.raises(ValidationError):
        Vote(persona="ranges_andy", direction=0)
    with pytest.raises(ValidationError):
        Vote(persona="ranges_andy", direction=2)


def test_reply_depth_bounds():
    Reply(slot_id="s01", depth=6, role="signal", brief="b")
    with pytest.raises(ValidationError):
        Reply(slot_id="s01", depth=7, role="signal", brief="b")
    with pytest.raises(ValidationError):
        Reply(slot_id="s01", depth=-1, role="signal", brief="b")


def test_reply_noise_stance_vocabulary_is_closed():
    """A stance typo must fail loudly, not demote a trap to noise."""
    Reply(slot_id="s01", depth=0, role="noise", brief="b",
          noise_stance="misconception")
    Reply(slot_id="s01", depth=0, role="noise", brief="b",
          noise_stance="process-cynic")
    with pytest.raises(ValidationError):
        Reply(slot_id="s01", depth=0, role="noise", brief="b",
              noise_stance="misconceptions")


def test_reply_lens_bounds():
    Reply(slot_id="s01", depth=0, role="signal", brief="b", domain_lens=13)
    with pytest.raises(ValidationError):
        Reply(slot_id="s01", depth=0, role="signal", brief="b", domain_lens=14)
    with pytest.raises(ValidationError):
        Reply(slot_id="s01", depth=0, role="signal", brief="b", domain_lens=0)


def test_encounter_plan_round_trip():
    e = EncounterPlan(
        encounter_id="e01",
        design_tension_id="t01",
        design_tension="A vs B",
        position_a="A",
        position_b="B",
        resolution="narrowing",
        slot_ids=["s05", "s06", "s07"],
    )
    assert EncounterPlan.model_validate(e.model_dump()) == e


def test_thread_construct_with_analysis_only_fields():
    t = Thread(
        document="P4003R2", paper="P4003", revision=2,
        title="Foo", authors=["A. Author", "B. Author"], audience="EWG",
        date="2026-01-15", subreddit="r/wg21", committee="ewg",
        paper_type="proposal",
        technical_anchors=[_anchor()],
        research_summary=_research(),
        heat="warm", interest="relevant",
        target_comment_count=25, encounter_count=0,
        signal_count=10, noise_count=15,
        submission_title="[P4003R2] foo",
        submission_body="body",
        submission_link="https://wg21.link/p4003r2",
    )
    # Generation-phase fields all None / default.
    assert t.submission_poster_id is None
    assert t.submission_votes is None
    assert t.generated_at is None
    # Defaults for collections.
    assert t.replies == []
    assert t.encounters == []
    assert t.tangent_magnets == []


def test_smell_test_output_defaults():
    o = SmellTestOutput(paper_type="wording")
    assert o.technical_anchors == []
    assert o.hot_takes == []
    assert o.design_tensions == []


def test_calibration_output_negative_count_rejected():
    with pytest.raises(ValidationError):
        CalibrationOutput(
            heat="warm", interest="relevant",
            target_comment_count=-1,
            encounter_count=0, signal_count=0, noise_count=0,
            rationale="r",
        )


def test_calibration_output_consistent_plan_accepted():
    o = CalibrationOutput(
        heat="warm", interest="relevant",
        target_comment_count=30,
        encounter_count=0, signal_count=12, noise_count=18,
        rationale="r",
    )
    assert o.target_comment_count == 30


def test_calibration_output_multiplied_target_capped_at_90():
    # thermonuclear x gravitational would be 180-450 uncapped; the only
    # admissible target is the 90-comment ceiling.
    with pytest.raises(ValidationError, match="capped at 90"):
        CalibrationOutput(
            heat="thermonuclear", interest="gravitational",
            target_comment_count=180,
            encounter_count=2, signal_count=60, noise_count=100,
            rationale="r",
        )
    o = CalibrationOutput(
        heat="thermonuclear", interest="gravitational",
        target_comment_count=90,
        encounter_count=2, signal_count=45, noise_count=35,
        rationale="r",
    )
    assert o.target_comment_count == 90


def test_calibration_output_target_below_tier_range_rejected():
    # hot x relevant scales the 30-60 baseline to 45-90.
    with pytest.raises(ValidationError, match="outside"):
        CalibrationOutput(
            heat="hot", interest="relevant",
            target_comment_count=30,
            encounter_count=1, signal_count=10, noise_count=16,
            rationale="r",
        )


def test_calibration_output_signal_share_floor_rejected():
    # The 2026-07-15 failure shape: a noise-swamped pool at an interest
    # tier whose minimum signal share is 35%.
    with pytest.raises(ValidationError, match="signal share"):
        CalibrationOutput(
            heat="warm", interest="relevant",
            target_comment_count=30,
            encounter_count=0, signal_count=6, noise_count=24,
            rationale="r",
        )


def test_calibration_output_unexplained_reserve_rejected():
    # 8 slots of the target are unaccounted for: no encounters, and
    # warm reserves at most 1 mod action.
    with pytest.raises(ValidationError, match="encounters and mod actions"):
        CalibrationOutput(
            heat="warm", interest="relevant",
            target_comment_count=30,
            encounter_count=0, signal_count=12, noise_count=10,
            rationale="r",
        )


def test_calibration_output_cold_encounter_rejected():
    with pytest.raises(ValidationError, match="no encounters"):
        CalibrationOutput(
            heat="cold", interest="niche",
            target_comment_count=8,
            encounter_count=1, signal_count=2, noise_count=3,
            rationale="r",
        )


def test_calibration_output_hot_without_encounter_rejected():
    with pytest.raises(ValidationError, match="at least 1 encounter"):
        CalibrationOutput(
            heat="hot", interest="relevant",
            target_comment_count=45,
            encounter_count=0, signal_count=16, noise_count=28,
            rationale="r",
        )


def _calibration_plan(heat, interest, target, encounter_count):
    """Plan kwargs with the reserve at its lower bound and the signal
    share at the interest floor - valid except where a test perturbs
    the target or encounter count."""
    mods_low, _ = MOD_ACTION_RESERVE[heat]
    pool = target - encounter_count * ENCOUNTER_TURNS[0] - mods_low
    signal = math.ceil(SIGNAL_RATIO_FLOOR[interest] * pool)
    return {
        "heat": heat,
        "interest": interest,
        "target_comment_count": target,
        "encounter_count": encounter_count,
        "signal_count": signal,
        "noise_count": pool - signal,
        "rationale": "r",
    }


@pytest.mark.parametrize(
    ("heat", "interest", "encounter_count", "target", "ok"),
    [
        # cold x niche: baseline 5-10 x 1.0.
        ("cold", "niche", 0, 4, False),
        ("cold", "niche", 0, 5, True),
        ("cold", "niche", 0, 10, True),
        ("cold", "niche", 0, 11, False),
        # warm x relevant: 15-30 x 1.5 -> 22-45.
        ("warm", "relevant", 0, 21, False),
        ("warm", "relevant", 0, 22, True),
        ("warm", "relevant", 0, 45, True),
        ("warm", "relevant", 0, 46, False),
        # hot x relevant: 30-60 x 1.5 -> 45-90.
        ("hot", "relevant", 1, 44, False),
        ("hot", "relevant", 1, 45, True),
        ("hot", "relevant", 1, 90, True),
        ("hot", "relevant", 1, 91, False),
        # thermonuclear x gravitational: 180-450 uncapped, so the
        # 90-comment ceiling is the only admissible target.
        ("thermonuclear", "gravitational", 1, 89, False),
        ("thermonuclear", "gravitational", 1, 90, True),
        ("thermonuclear", "gravitational", 1, 91, False),
    ],
)
def test_calibration_output_target_boundaries(
    heat, interest, encounter_count, target, ok
):
    kwargs = _calibration_plan(heat, interest, target, encounter_count)
    if ok:
        assert CalibrationOutput(**kwargs).target_comment_count == target
    else:
        with pytest.raises(ValidationError, match="outside"):
            CalibrationOutput(**kwargs)


def test_calibration_output_encounter_count_over_max_rejected():
    with pytest.raises(ValidationError, match="exceeds the maximum"):
        CalibrationOutput(
            **_calibration_plan("thermonuclear", "gravitational", 90, 4)
        )


def test_calibration_output_warm_second_encounter_rejected():
    with pytest.raises(ValidationError, match="at most 1 encounter"):
        CalibrationOutput(**_calibration_plan("warm", "relevant", 30, 2))


def test_calibration_output_warm_single_encounter_accepted():
    o = CalibrationOutput(**_calibration_plan("warm", "relevant", 30, 1))
    assert o.encounter_count == 1


def test_calibration_output_reports_every_violation_at_once():
    # The retry budget is 3: a draft that breaks four rules must not
    # spend one retry per rule discovering them.
    with pytest.raises(ValidationError) as excinfo:
        CalibrationOutput(
            heat="cold", interest="niche",
            target_comment_count=50,
            encounter_count=5, signal_count=1, noise_count=1,
            rationale="r",
        )
    message = str(excinfo.value)
    assert "outside" in message
    assert "exceeds the maximum" in message
    assert "no encounters" in message
    assert "encounters and mod actions" in message


def test_submission_output_default_case_A():
    o = SubmissionOutput(
        submission_title="t", submission_body="b",
        submission_link="https://wg21.link/p1r0",
    )
    assert o.revision_case == "A"


def test_skeleton_output_carries_groups():
    o = SkeletonOutput(
        replies=[SkeletonReply(slot_id="s01", depth=0, role="signal", brief="b")],
        encounter_slot_groups=[["s05", "s06", "s07"]],
    )
    assert len(o.encounter_slot_groups) == 1
    assert o.encounter_slot_groups[0] == ["s05", "s06", "s07"]


def test_skeleton_reply_has_no_generation_fields():
    fields = set(SkeletonReply.model_fields)
    assert fields <= set(Reply.model_fields)
    assert not fields & {
        "content", "character_username", "score", "ordering",
        "time_label", "controversial", "edited", "collapsed",
        "deleted", "removed", "is_mod", "is_op", "flair", "votes",
    }


def test_skeleton_reply_widens_to_reply():
    slot = SkeletonReply(
        slot_id="s01", parent_slot_id=None, depth=0, role="signal",
        brief="b", anchor_id="a01", domain_lens=3, carries_code=True,
    )
    reply = Reply(**slot.model_dump())
    assert reply.slot_id == "s01"
    assert reply.anchor_id == "a01"
    assert reply.carries_code is True
    assert reply.content is None
    assert reply.character_username is None
    assert reply.votes == []


def test_encounters_output_default():
    o = EncountersOutput()
    assert o.encounters == []


def test_pipeline_state_defaults_none():
    s = PipelineState()
    assert s.paper_id == ""
    assert s.paper_source is None
    assert s.subreddit is None
    assert s.revision_case == "A"
    assert s.heat is None
    assert s.thread is None
    assert s.paper_authors == []


def test_pipeline_state_assignable():
    s = PipelineState()
    s.paper_id = "P4003R2"
    s.subreddit = "r/wg21"
    s.committee = "lewg"
    s.heat = "thermonuclear"
    s.encounter_count = 3
    assert s.paper_id == "P4003R2"
    assert s.subreddit == "r/wg21"
    assert s.committee == "lewg"
    assert s.heat == "thermonuclear"
    assert s.encounter_count == 3
