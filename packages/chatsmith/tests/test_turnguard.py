#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

from __future__ import annotations

from chatsmith.turnguard import TurnGuard


def test_newer_turn_supersedes_older() -> None:
    guard = TurnGuard()
    gen1 = guard.begin("s")
    assert guard.is_current("s", gen1)
    gen2 = guard.begin("s")  # a newer turn
    assert not guard.is_current("s", gen1)
    assert guard.is_current("s", gen2)


def test_cancel_is_noop_for_unknown_session() -> None:
    guard = TurnGuard()
    # No turn has begun, so cancel must not allocate state for a crafted id.
    guard.cancel("attacker-supplied")
    assert guard.is_current("attacker-supplied", 0)


def test_commit_only_when_current() -> None:
    guard = TurnGuard()
    gen = guard.begin("s")
    saved: list[str] = []
    assert guard.commit("s", gen, lambda: saved.append("first")) is True
    assert saved == ["first"]

    stale = gen
    guard.begin("s")  # supersede
    assert guard.commit("s", stale, lambda: saved.append("second")) is False
    assert saved == ["first"]  # superseded commit did not save


def test_cancel_invalidates_in_flight_turn() -> None:
    # The barge-in path the guard exists for: a turn is in flight, the subject
    # resumes talking, cancel() fires, and the in-flight commit must be dropped.
    guard = TurnGuard()
    gen = guard.begin("s")
    assert guard.is_current("s", gen)
    guard.cancel("s")
    assert not guard.is_current("s", gen)
    saved: list[str] = []
    assert guard.commit("s", gen, lambda: saved.append("late")) is False
    assert saved == []


def test_session_lock_is_stable_per_session() -> None:
    # Turn serialization depends on a stable per-session lock identity: the same id
    # must always return the same lock object, and different ids distinct locks.
    guard = TurnGuard()
    lock_a = guard.session_lock("s")
    assert guard.session_lock("s") is lock_a
    assert guard.session_lock("other") is not lock_a
