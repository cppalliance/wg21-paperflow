#
# Copyright (c) 2026 Glenn Siegman (glenn@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the persona roster data module and its export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agora.artifact import validate_artifact
from agora.roster import (
    ALL_PERSONAS,
    MODS,
    PERSONA_BY_USERNAME,
    ROSTER,
    ROSTER_VERSION,
    Persona,
    dump_roster,
    dump_roster_json,
    roster_usernames,
)

_FIXTURES = Path(__file__).parent / "fixtures"

_EXPECTED_ROSTER = {
    "monomorphic_dan", "abi_archivist", "embedded_for_20_years",
    "lifetimes_lucy", "the_constexpr_oracle",
    "async_skeptic", "ranges_andy", "nanosecond_nancy", "compiles_first_try",
    "not_a_real_cpp_dev", "bootcamp_grad_2025",
    "just_use_rust_lol", "committee_gonna_committee",
    "segfault_enjoyer_69", "template_error_survivor",
}
_EXPECTED_MODS = {
    "standards_shepherd", "paper_trail_2019", "not_on_the_committee",
    "cwg_watcher", "template_janitor", "AutoModerator",
}


# -- Roster shape --------------------------------------------------------------


def test_roster_is_the_documented_fifteen():
    assert {p.username for p in ROSTER} == _EXPECTED_ROSTER
    assert len(ROSTER) == 15


def test_mod_set_matches_the_mod_md_roster():
    assert {p.username for p in MODS} == _EXPECTED_MODS
    assert all(p.archetype == "mod" for p in MODS)


def test_archetype_distribution():
    counts: dict[str, int] = {}
    for persona in ROSTER:
        counts[persona.archetype] = counts.get(persona.archetype, 0) + 1
    assert counts == {"academic": 5, "middle": 4, "novice": 2, "jokester": 4}


def test_tier_follows_archetype():
    expected = {
        "academic": "signal", "middle": "signal",
        "novice": "learner", "jokester": "noise", "mod": "mod",
    }
    for persona in ALL_PERSONAS:
        assert persona.tier == expected[persona.archetype], persona.username


def test_signal_personas_carry_all_four_traits():
    for persona in ROSTER:
        if persona.tier != "signal":
            continue
        assert persona.voice is not None, persona.username
        assert persona.argumentation is not None, persona.username
        assert persona.domain_lens is not None, persona.username
        assert persona.behavior is not None, persona.username


def test_novice_argumentation_is_null():
    novices = [p for p in ROSTER if p.archetype == "novice"]
    assert len(novices) == 2
    for persona in novices:
        assert persona.argumentation is None
        assert persona.voice is not None
        assert persona.domain_lens is not None
        assert persona.behavior is not None


def test_jokesters_and_mods_carry_no_table_traits():
    for persona in ALL_PERSONAS:
        if persona.archetype not in ("jokester", "mod"):
            continue
        assert persona.voice is None, persona.username
        assert persona.argumentation is None, persona.username
        assert persona.domain_lens is None, persona.username
        assert persona.behavior is None, persona.username


def test_documented_trait_numbers():
    """Spot-check the trait table against the master plan §5 roster."""
    dan = PERSONA_BY_USERNAME["monomorphic_dan"]
    assert (dan.voice, dan.argumentation, dan.domain_lens, dan.behavior) == \
        (2, 1, 8, 8)
    nancy = PERSONA_BY_USERNAME["nanosecond_nancy"]
    assert (nancy.voice, nancy.argumentation, nancy.domain_lens,
            nancy.behavior) == (8, 7, 4, 5)
    novice = PERSONA_BY_USERNAME["not_a_real_cpp_dev"]
    assert (novice.voice, novice.domain_lens, novice.behavior) == (1, 6, 7)


def test_every_persona_has_prompt_bio_and_floats_in_range():
    for persona in ALL_PERSONAS:
        assert persona.system_prompt.strip(), persona.username
        assert persona.bio.strip(), persona.username
        for value in (persona.upvote_bias, persona.contrarianism,
                      persona.snark_affinity):
            assert 0.0 <= value <= 1.0, persona.username


def test_usernames_are_unique():
    usernames = [p.username for p in ALL_PERSONAS]
    assert len(usernames) == len(set(usernames))


# -- Model invariants ----------------------------------------------------------


def test_tier_archetype_mismatch_rejected():
    with pytest.raises(ValidationError):
        Persona(
            username="x", archetype="jokester", tier="signal",
            system_prompt="p", bio="b",
            upvote_bias=0.5, contrarianism=0.5, snark_affinity=0.5,
        )


def test_novice_with_argumentation_rejected():
    with pytest.raises(ValidationError):
        Persona(
            username="x", archetype="novice", tier="learner",
            voice=1, argumentation=3, domain_lens=6, behavior=7,
            system_prompt="p", bio="b",
            upvote_bias=0.5, contrarianism=0.5, snark_affinity=0.5,
        )


def test_signal_with_missing_trait_rejected():
    with pytest.raises(ValidationError):
        Persona(
            username="x", archetype="middle", tier="signal",
            voice=1, argumentation=3, domain_lens=None, behavior=7,
            system_prompt="p", bio="b",
            upvote_bias=0.5, contrarianism=0.5, snark_affinity=0.5,
        )


def test_out_of_range_float_rejected():
    with pytest.raises(ValidationError):
        Persona(
            username="x", archetype="jokester", tier="noise",
            system_prompt="p", bio="b",
            upvote_bias=1.5, contrarianism=0.5, snark_affinity=0.5,
        )


# -- Ready consumer: artifact validation ---------------------------------------


def test_frozen_fixtures_validate_against_the_real_roster():
    """Every persona in the frozen v1 samples is a roster member."""
    for name in ("P2987R0.agora.json", "P2611R3.agora.json"):
        artifact = json.loads((_FIXTURES / name).read_text())
        validate_artifact(artifact, roster=set(roster_usernames()))


def test_roster_usernames_covers_mods():
    names = roster_usernames()
    assert _EXPECTED_ROSTER <= names
    assert _EXPECTED_MODS <= names
    assert len(names) == 21


# -- Export --------------------------------------------------------------------


def test_dump_roster_shape():
    dump = dump_roster()
    assert dump["roster_version"] == ROSTER_VERSION
    assert set(dump["personas"]) == _EXPECTED_ROSTER | _EXPECTED_MODS
    entry = dump["personas"]["lifetimes_lucy"]
    assert entry == {
        "archetype": "academic",
        "tier": "signal",
        "voice": 5,
        "argumentation": 4,
        "domain_lens": 11,
        "behavior": 3,
        "bio": PERSONA_BY_USERNAME["lifetimes_lucy"].bio,
        "avatar_seed": "lifetimes_lucy",
    }


def test_dump_excludes_generation_internals():
    for entry in dump_roster()["personas"].values():
        assert "system_prompt" not in entry
        assert "upvote_bias" not in entry


def test_dump_json_is_stable_and_round_trips():
    first = dump_roster_json()
    second = dump_roster_json()
    assert first == second
    assert first.endswith("\n")
    assert json.loads(first) == dump_roster()
