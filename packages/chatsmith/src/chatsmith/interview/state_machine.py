#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""A light, advisory phase model for the interview.

v1 is tool-free: the persona drives the conversation from context. These helpers
only track a coarse phase for display and resume, and detect an explicit close.
Deterministic termination (coverage/assertion gates) is deferred.
"""

from __future__ import annotations

GREETING = "greeting"
ELICIT = "elicit"
WALK = "walk"
CLOSE = "close"

# Subject-turn counts that advance the coarse phase (advisory only).
_MIN_TURNS_TO_ELICIT = 1
_MIN_TURNS_TO_WALK = 3

# Phrases from the subject or operator that end the interview.
_CLOSE_PHRASES = (
    "done for the day",
    "i'm done",
    "im done",
    "that's all",
    "that is all",
    "let's stop",
    "lets stop",
    "we're done",
    "quit the interview",
    "end the interview",
)


def is_close_intent(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in _CLOSE_PHRASES)


def next_phase(current: str, subject_turns: int, close_intent: bool) -> str:
    """Advance the coarse phase. Advisory only."""
    if close_intent:
        return CLOSE
    if current in (GREETING, "") and subject_turns >= _MIN_TURNS_TO_ELICIT:
        return ELICIT
    if current == ELICIT and subject_turns >= _MIN_TURNS_TO_WALK:
        return WALK
    return current or GREETING
