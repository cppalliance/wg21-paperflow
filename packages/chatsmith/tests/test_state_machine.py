#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

from __future__ import annotations

from chatsmith.interview.state_machine import (
    CLOSE,
    ELICIT,
    GREETING,
    WALK,
    is_close_intent,
    next_phase,
)


def test_close_intent_matches_known_phrases_case_insensitively() -> None:
    assert is_close_intent("I think we're DONE here") is True
    assert is_close_intent("ok, that's all for today") is True


def test_close_intent_false_for_ordinary_talk() -> None:
    assert is_close_intent("let's keep going, this is a great thread") is False


def test_close_intent_forces_close_from_any_phase() -> None:
    assert next_phase(ELICIT, subject_turns=1, close_intent=True) == CLOSE
    assert next_phase(GREETING, subject_turns=0, close_intent=True) == CLOSE
    assert next_phase(WALK, subject_turns=5, close_intent=True) == CLOSE


def test_greeting_advances_to_elicit_after_first_subject_turn() -> None:
    assert next_phase(GREETING, subject_turns=0, close_intent=False) == GREETING
    assert next_phase(GREETING, subject_turns=1, close_intent=False) == ELICIT


def test_empty_phase_is_treated_as_greeting() -> None:
    # A resumed session with no recorded phase behaves like greeting.
    assert next_phase("", subject_turns=0, close_intent=False) == GREETING
    assert next_phase("", subject_turns=1, close_intent=False) == ELICIT


def test_elicit_advances_to_walk_after_enough_turns() -> None:
    assert next_phase(ELICIT, subject_turns=2, close_intent=False) == ELICIT
    assert next_phase(ELICIT, subject_turns=3, close_intent=False) == WALK


def test_walk_is_terminal_without_an_explicit_close() -> None:
    # There is no advisory transition out of walk; only a close intent leaves it.
    assert next_phase(WALK, subject_turns=99, close_intent=False) == WALK
