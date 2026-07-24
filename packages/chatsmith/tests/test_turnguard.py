#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

from __future__ import annotations

import threading

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


def test_commit_rejects_session_that_never_began() -> None:
    # An unknown session has no started generation; the default sentinel 0 must not
    # be treated as valid, so a crafted commit can never persist for it.
    guard = TurnGuard()
    saved: list[str] = []
    assert guard.commit("never-began", 0, lambda: saved.append("x")) is False
    assert saved == []


def test_forget_drops_session_state() -> None:
    # After a session is forgotten, a stale commit for it is rejected, and a fresh
    # turn for the same id starts a new (non-recycled) generation that still works.
    guard = TurnGuard()
    gen = guard.begin("s")
    guard.forget("s")
    saved: list[str] = []
    assert guard.commit("s", gen, lambda: saved.append("stale")) is False
    assert saved == []

    new_gen = guard.begin("s")
    assert guard.commit("s", new_gen, lambda: saved.append("fresh")) is True
    assert saved == ["fresh"]

    # forget() is a no-op for an unknown id (never allocates guard state).
    guard.forget("attacker-supplied")


def test_commit_save_is_atomic_against_a_concurrent_cancel() -> None:
    # The core guarantee: while commit() runs save(), a concurrent cancel() for the
    # same session is blocked on the per-session state lock, so it cannot invalidate
    # the turn between the generation check and the write. The cancel only lands
    # after the save completes, so an orphaned, superseded save is impossible.
    guard = TurnGuard()
    gen = guard.begin("s")
    order: list[str] = []
    in_save = threading.Event()
    cancel_done = threading.Event()

    def canceller() -> None:
        in_save.wait(1.0)
        guard.cancel("s")  # blocks until commit's save() releases the state lock
        order.append("cancel")
        cancel_done.set()

    worker = threading.Thread(target=canceller)
    worker.start()

    def save() -> None:
        in_save.set()
        # cancel() is now runnable but must be unable to finish while commit holds
        # the session's state lock, regardless of thread scheduling.
        assert not cancel_done.is_set()
        order.append("save")

    assert guard.commit("s", gen, save) is True
    worker.join(1.0)
    assert order == ["save", "cancel"]


def test_session_lock_is_stable_per_session() -> None:
    # Turn serialization depends on a stable per-session lock identity: the same id
    # must always return the same lock object, and different ids distinct locks.
    guard = TurnGuard()
    lock_a = guard.session_lock("s")
    assert guard.session_lock("s") is lock_a
    assert guard.session_lock("other") is not lock_a
