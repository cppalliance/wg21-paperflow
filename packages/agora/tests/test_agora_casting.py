"""Tests for deterministic persona casting over blueprint slots."""

from __future__ import annotations

from agora.casting import (
    MISCONCEPTION_STANCE,
    NEAREST_DOMAIN,
    cast_thread,
    select_persona_for_slot,
    select_regulars,
    select_submission_poster,
)
from agora.models import (
    EncounterPlan,
    Reply,
    ResearchAgentReport,
    ResearchSummary,
    Thread,
)
from agora.roster import PERSONA_BY_USERNAME

_DOCUMENT = "P4003R2"


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


def _thread(replies: list[Reply], encounters: list[EncounterPlan] = ()) -> Thread:
    return Thread(
        document=_DOCUMENT, paper="P4003", revision=2,
        title="Foo", authors=["A. Author"], audience="EWG",
        date="2026-01-15", paper_type="proposal",
        research_summary=_research(),
        heat="warm", interest="relevant",
        target_comment_count=len(replies), encounter_count=len(encounters),
        signal_count=sum(1 for r in replies if r.role == "signal"),
        noise_count=sum(1 for r in replies if r.role == "noise"),
        submission_title="[P4003R2] Foo",
        submission_body="body",
        submission_link="https://wg21.link/p4003r2",
        replies=list(replies),
        encounters=list(encounters),
    )


def _select(slot: Reply, **kwargs):
    return select_persona_for_slot(slot, document=_DOCUMENT, **kwargs)


# -- Per-slot rules ------------------------------------------------------------


def test_signal_slot_gets_matching_domain_signal_persona():
    persona = _select(_reply("s01", role="signal", domain_lens=9))
    assert persona.tier == "signal"
    assert persona.domain_lens == 9  # async_skeptic is the only 9
    assert persona.username == "async_skeptic"


def test_signal_slot_without_lens_gets_some_signal_persona():
    persona = _select(_reply("s01", role="signal", domain_lens=None))
    assert persona.tier == "signal"


def test_uncovered_domain_falls_back_to_nearest():
    persona = _select(_reply("s01", role="signal", domain_lens=6))
    assert persona.tier == "signal"
    assert persona.domain_lens == NEAREST_DOMAIN[6]


def test_every_table_c_domain_resolves_to_a_signal_persona():
    for lens in range(1, 14):
        persona = _select(_reply("s01", role="signal", domain_lens=lens))
        assert persona.tier == "signal", lens


def test_noise_slot_gets_jokester():
    persona = _select(_reply("s01", role="noise", noise_stance="didnt-read"))
    assert persona.tier == "noise"
    assert persona.archetype == "jokester"


def test_misconception_trap_gets_novice():
    persona = _select(
        _reply("s01", role="noise", noise_stance=MISCONCEPTION_STANCE))
    assert persona.tier == "learner"
    assert persona.archetype == "novice"


def test_teaser_slot_gets_signal_persona():
    persona = _select(_reply("s01", role="teaser", domain_lens=11))
    assert persona.username == "lifetimes_lucy"


def test_mod_slot_gets_human_mod():
    persona = _select(_reply("s01", role="mod"))
    assert persona.archetype == "mod"
    assert persona.username != "AutoModerator"


def test_deleted_slot_gets_jokester():
    persona = _select(_reply("s01", role="deleted"))
    assert persona.archetype == "jokester"


def test_tangent_slot_gets_jokester_or_novice():
    persona = _select(_reply("s01", role="tangent"))
    assert persona.archetype in ("jokester", "novice")


def test_selection_never_returns_an_unseeded_username():
    for role, extra in (
        ("signal", {"domain_lens": 5}), ("noise", {}), ("teaser", {}),
        ("tangent", {}), ("mod", {}), ("deleted", {}),
    ):
        persona = _select(_reply("s01", role=role, **extra))
        assert persona.username in PERSONA_BY_USERNAME


# -- Thread casting ------------------------------------------------------------


def _trap_thread() -> Thread:
    replies = [
        _reply("s01", role="teaser", domain_lens=11),
        _reply("s02", role="noise", noise_stance=MISCONCEPTION_STANCE,
               brief="Confused question voicing the misreading."),
        _reply("s03", parent_slot_id="s02", depth=1, role="signal",
               domain_lens=12, brief="Gently correct the misreading."),
        _reply("s04", role="noise", noise_stance="process-cynic"),
    ]
    return _thread(replies)


def test_cast_thread_pairs_trap_question_with_teaching_reply():
    casting = cast_thread(_trap_thread())
    assert casting.trap_pairs == (("s02", "s03"),)
    question = PERSONA_BY_USERNAME[casting.assignments["s02"]]
    teaching = PERSONA_BY_USERNAME[casting.assignments["s03"]]
    assert question.tier == "learner"
    assert teaching.tier == "signal"


def test_cast_thread_covers_every_slot():
    casting = cast_thread(_trap_thread())
    assert set(casting.assignments) == {"s01", "s02", "s03", "s04"}


def test_encounter_alternates_two_distinct_signal_personas():
    replies = [
        _reply("s01", role="encounter", domain_lens=9),
        _reply("s02", role="encounter", domain_lens=9, depth=1,
               parent_slot_id="s01"),
        _reply("s03", role="encounter", domain_lens=9, depth=2,
               parent_slot_id="s02"),
    ]
    plan = EncounterPlan(
        encounter_id="e01", design_tension_id="t01", design_tension="A vs B",
        position_a="A", position_b="B", resolution="narrowing",
        slot_ids=["s01", "s02", "s03"],
    )
    casting = cast_thread(_thread(replies, [plan]))
    side_a = casting.assignments["s01"]
    side_b = casting.assignments["s02"]
    assert side_a != side_b
    assert casting.assignments["s03"] == side_a
    assert PERSONA_BY_USERNAME[side_a].tier == "signal"
    assert PERSONA_BY_USERNAME[side_b].tier == "signal"


def _big_thread() -> Thread:
    replies = [
        _reply("s01", role="teaser", domain_lens=11),
        _reply("s02", role="signal", domain_lens=9),
        _reply("s03", role="signal", domain_lens=10),
        _reply("s04", role="signal", domain_lens=13),
        _reply("s05", role="signal", domain_lens=10,
               parent_slot_id="s03", depth=1),
        _reply("s06", role="noise", noise_stance="rust"),
        _reply("s07", role="noise", noise_stance="doomsayer"),
        _reply("s08", role="noise", noise_stance="process-cynic"),
        _reply("s09", role="noise", noise_stance="didnt-read"),
        _reply("s10", role="tangent"),
        _reply("s11", role="tangent", parent_slot_id="s10", depth=1),
        _reply("s12", role="mod"),
    ]
    return _thread(replies)


def test_cast_thread_is_deterministic():
    first = cast_thread(_big_thread())
    second = cast_thread(_big_thread())
    assert first == second


def test_regulars_recur_within_a_thread():
    casting = cast_thread(_big_thread())
    assert 2 <= len(casting.regulars) <= 3
    counts: dict[str, int] = {}
    for username in casting.assignments.values():
        counts[username] = counts.get(username, 0) + 1
    recurring = {name for name, count in counts.items() if count >= 2}
    assert len(recurring) >= 2


def test_regulars_are_seeded_by_document_alone():
    assert select_regulars(_DOCUMENT) == select_regulars(_DOCUMENT)
    regulars = select_regulars(_DOCUMENT)
    tiers = [PERSONA_BY_USERNAME[name].tier for name in regulars]
    assert tiers.count("signal") == 2
    assert tiers.count("noise") == 1


def test_submission_poster_is_a_signal_regular():
    poster = select_submission_poster(_DOCUMENT)
    assert poster in select_regulars(_DOCUMENT)
    assert PERSONA_BY_USERNAME[poster].tier == "signal"


def test_nearest_domain_map_targets_covered_lenses():
    covered = {
        p.domain_lens for p in PERSONA_BY_USERNAME.values()
        if p.tier == "signal"
    }
    for source, target in NEAREST_DOMAIN.items():
        assert source not in covered
        assert target in covered
