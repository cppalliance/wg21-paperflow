"""Tests for .agora.json serialization and producer validation."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agora.artifact import (
    SCHEMA_VERSION,
    ArtifactError,
    thread_to_artifact,
    validate_artifact,
)
from agora.models import (
    Reply,
    ResearchAgentReport,
    ResearchSummary,
    TechnicalAnchor,
    Thread,
    Vote,
)

_FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    with open(_FIXTURES / name, encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture()
def rich_artifact() -> dict:
    """The hand-authored rich Case-A fixture (hot, 15 comments)."""
    return _load_fixture("P2987R0.agora.json")


@pytest.fixture()
def revision_artifact() -> dict:
    """The hand-authored compact Case-C revision fixture."""
    return _load_fixture("P2611R3.agora.json")


def _fixture_personas(artifact: dict) -> set[str]:
    personas = {artifact["submission_poster_id"]}
    for vote in artifact["submission_votes"]:
        personas.add(vote["persona"])
    for comment in artifact["comments"]:
        personas.add(comment["persona"])
        for vote in comment["votes"]:
            personas.add(vote["persona"])
    return personas


# -- Fixture validation ------------------------------------------------------


def test_rich_fixture_passes_validation(rich_artifact: dict):
    validate_artifact(rich_artifact)


def test_revision_fixture_passes_validation(revision_artifact: dict):
    validate_artifact(revision_artifact)


def test_fixture_passes_with_matching_roster(rich_artifact: dict):
    validate_artifact(rich_artifact, roster=_fixture_personas(rich_artifact))


def test_unknown_username_rejected_with_roster(rich_artifact: dict):
    roster = _fixture_personas(rich_artifact)
    roster.discard(rich_artifact["comments"][0]["persona"])
    with pytest.raises(ArtifactError, match="not.*in the roster"):
        validate_artifact(rich_artifact, roster=roster)


# -- Invariant violations ----------------------------------------------------


def test_missing_top_level_key_rejected(rich_artifact: dict):
    del rich_artifact["committee"]
    with pytest.raises(ArtifactError, match="missing top-level keys"):
        validate_artifact(rich_artifact)


def test_wrong_schema_version_rejected(rich_artifact: dict):
    rich_artifact["schema_version"] = 2
    with pytest.raises(ArtifactError, match="schema_version"):
        validate_artifact(rich_artifact)


def test_wrong_subreddit_rejected(rich_artifact: dict):
    rich_artifact["subreddit"] = "r/ewg"
    with pytest.raises(ArtifactError, match="r/wg21"):
        validate_artifact(rich_artifact)


def test_unknown_committee_rejected(rich_artifact: dict):
    rich_artifact["committee"] = "sg21"
    with pytest.raises(ArtifactError, match="committee"):
        validate_artifact(rich_artifact)


def test_case_c_without_prior_revision_rejected(revision_artifact: dict):
    revision_artifact["prior_revision"] = None
    with pytest.raises(ArtifactError, match="prior_revision"):
        validate_artifact(revision_artifact)


def test_dangling_parent_rejected(rich_artifact: dict):
    rich_artifact["comments"][3]["parent_slot_id"] = "r999"
    with pytest.raises(ArtifactError, match="dangling parent"):
        validate_artifact(rich_artifact)


def test_depth_inconsistent_with_parent_rejected(rich_artifact: dict):
    child = next(
        c for c in rich_artifact["comments"]
        if c["parent_slot_id"] is not None
    )
    child["depth"] = child["depth"] + 1
    with pytest.raises(ArtifactError, match="depth"):
        validate_artifact(rich_artifact)


def test_top_level_comment_with_nonzero_depth_rejected(rich_artifact: dict):
    top = next(
        c for c in rich_artifact["comments"] if c["parent_slot_id"] is None
    )
    top["depth"] = 1
    with pytest.raises(ArtifactError, match="top-level"):
        validate_artifact(rich_artifact)


def test_duplicate_slot_id_rejected(rich_artifact: dict):
    duplicate = copy.deepcopy(rich_artifact["comments"][0])
    rich_artifact["comments"].append(duplicate)
    with pytest.raises(ArtifactError, match="Duplicate"):
        validate_artifact(rich_artifact)


def test_duplicate_vote_rejected(rich_artifact: dict):
    votes = rich_artifact["comments"][0]["votes"]
    votes.append(dict(votes[0]))
    with pytest.raises(ArtifactError, match="more than once"):
        validate_artifact(rich_artifact)


def test_zero_direction_rejected(rich_artifact: dict):
    rich_artifact["comments"][0]["votes"][0]["direction"] = 0
    with pytest.raises(ArtifactError, match="direction"):
        validate_artifact(rich_artifact)


def test_empty_body_rejected(rich_artifact: dict):
    rich_artifact["comments"][0]["body"] = ""
    with pytest.raises(ArtifactError, match="no body"):
        validate_artifact(rich_artifact)


def test_unknown_anchor_reference_rejected(rich_artifact: dict):
    anchored = next(
        c for c in rich_artifact["comments"] if c["anchor_id"] is not None
    )
    anchored["anchor_id"] = "a999"
    with pytest.raises(ArtifactError, match="unknown anchor"):
        validate_artifact(rich_artifact)


def test_unaddressed_anchor_rejected(rich_artifact: dict):
    for comment in rich_artifact["comments"]:
        comment["anchor_id"] = None
    with pytest.raises(ArtifactError, match="no addressing comment"):
        validate_artifact(rich_artifact)


def test_is_op_by_non_poster_rejected(rich_artifact: dict):
    op_comment = next(
        c for c in rich_artifact["comments"] if c["is_op"]
    )
    op_comment["persona"] = "lifetimes_lucy"
    with pytest.raises(ArtifactError, match="is_op"):
        validate_artifact(rich_artifact)


def test_unknown_role_rejected(rich_artifact: dict):
    rich_artifact["comments"][0]["role"] = "lurker"
    with pytest.raises(ArtifactError, match="unknown role"):
        validate_artifact(rich_artifact)


# -- Serialization from a Thread ---------------------------------------------


def _anchor(anchor_id: str) -> TechnicalAnchor:
    return TechnicalAnchor(
        id=anchor_id,
        kind="load_bearing",
        summary="The core claim.",
        claim_text="We measured a 2x speedup.",
        claim_uid=1,
    )


def _research() -> ResearchSummary:
    report = ResearchAgentReport(
        agent="public_reception",
        findings="No prior mentions.",
        sources=[],
        heat_signal="warm",
        interest_signal="relevant",
    )
    return ResearchSummary(
        public_reception=report,
        committee_history=report.model_copy(
            update={"agent": "committee_history"},
        ),
        author_ecosystem=report.model_copy(
            update={"agent": "author_ecosystem"},
        ),
    )


def _generated_thread() -> Thread:
    """A small but complete thread with generation fields filled in."""
    replies = [
        Reply(
            slot_id="s01", parent_slot_id=None, depth=0, role="signal",
            brief="Quote the speedup claim and challenge the benchmark.",
            anchor_id="a01", domain_lens=4,
            content="The 2x claim only holds on their microbenchmark.",
            character_username="hft_latency_larry",
            votes=[Vote(persona="ranges_andy", direction=1)],
        ),
        Reply(
            slot_id="s02", parent_slot_id="s01", depth=1, role="noise",
            brief="React with a low-stakes complaint about churn.",
            noise_tone="performatively-tired", noise_stance="process-cynic",
            content="great, another paper that will take 10 years",
            character_username="build_system_victim",
            edited=True,
            votes=[
                Vote(persona="ranges_andy", direction=-1),
                Vote(persona="lifetimes_lucy", direction=1),
            ],
        ),
    ]
    return Thread(
        document="P4003R2", paper="P4003", revision=2,
        mailing_id="2026-05",
        title="Faster widgets", authors=["A. Author"], audience="LEWG",
        date="2026-05-15", subreddit="r/wg21", committee="lewg",
        paper_type="proposal",
        technical_anchors=[_anchor("a01")],
        research_summary=_research(),
        heat="warm", interest="relevant",
        target_comment_count=2, encounter_count=0,
        signal_count=1, noise_count=1,
        submission_title="[P4003R2] Faster widgets",
        submission_body="The paper proposes faster widgets.",
        submission_link="https://wg21.link/p4003r2",
        submission_flair="Proposal",
        replies=replies,
        submission_poster_id="abi_archivist",
        submission_votes=[Vote(persona="lifetimes_lucy", direction=1)],
        generated_at=datetime(2026, 7, 9, 12, 0, 0, tzinfo=UTC),
    )


def test_generated_thread_serializes_and_validates():
    artifact = thread_to_artifact(_generated_thread())
    validate_artifact(artifact)


def test_artifact_top_level_keys_match_contract(rich_artifact: dict):
    artifact = thread_to_artifact(_generated_thread())
    fixture_keys = {k for k in rich_artifact if not k.startswith("_")}
    assert set(artifact.keys()) == fixture_keys


def test_artifact_comment_keys_match_contract(rich_artifact: dict):
    artifact = thread_to_artifact(_generated_thread())
    assert set(artifact["comments"][0].keys()) == set(
        rich_artifact["comments"][0].keys()
    )


def test_artifact_vocabulary_translation():
    artifact = thread_to_artifact(_generated_thread())
    assert artifact["schema_version"] == SCHEMA_VERSION
    assert artifact["subreddit"] == "r/wg21"
    assert artifact["committee"] == "lewg"
    assert artifact["submission_tag"] == "Proposal"
    first, second = artifact["comments"]
    assert first["persona"] == "hft_latency_larry"
    assert first["body"].startswith("The 2x claim")
    assert second["edited"] is True
    assert second["votes"] == [
        {"persona": "ranges_andy", "direction": -1},
        {"persona": "lifetimes_lucy", "direction": 1},
    ]


def test_blueprint_carries_plan_but_no_generation_fields():
    artifact = thread_to_artifact(_generated_thread())
    blueprint = artifact["blueprint"]
    assert blueprint["document"] == "P4003R2"
    assert blueprint["heat"] == "warm"
    assert "submission_poster_id" not in blueprint
    assert "generated_at" not in blueprint
    for slot in blueprint["replies"]:
        assert slot["brief"]
        assert "content" not in slot
        assert "character_username" not in slot
        assert "votes" not in slot


def test_generated_at_serialized_as_iso(rich_artifact: dict):
    artifact = thread_to_artifact(_generated_thread())
    assert artifact["generated_at"].startswith("2026-07-09T12:00:00")
