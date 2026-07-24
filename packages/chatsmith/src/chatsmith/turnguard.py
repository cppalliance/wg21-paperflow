#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Per-session turn guard for cancel-during-thinking.

A monotonic generation per session lets a newer turn, or an explicit cancel when
the user resumes talking, invalidate the reply currently in flight. The in-flight
turn checks ``is_current`` before it persists, so a superseded turn never saves. A
per-session lock serializes one session's turns so the cancelled turn releases
before the replacement runs.

In-memory and process-local: fine for the single-process local server. A
multi-worker deployment (the Django site) needs a shared generation store (e.g.
Redis) plus a cross-process lock; the generation model is reusable, but this
concrete implementation does not port unchanged (see the integration plan).
"""

from __future__ import annotations

import threading
from collections.abc import Callable


class TurnCancelled(Exception):
    """Raised inside a turn when a newer turn or an explicit cancel supersedes it."""


class TurnGuard:
    """Tracks the latest turn generation per session and hands out per-session locks."""

    def __init__(self) -> None:
        # _registry guards only the maps below (state-lock lookup/creation and
        # cleanup). It is a leaf lock, never held across save() or a state lock, so
        # it never blocks an unrelated session.
        self._registry = threading.Lock()
        self._gen: dict[str, int] = {}
        self._session_locks: dict[str, threading.Lock] = {}
        # One re-entrant lock per session serializes that session's generation
        # changes (begin/cancel/forget) with its own commit's check+save. A commit
        # holds it across save(), so no invalidation can land between the check and
        # the write. It is distinct from session_lock (a caller may hold that across
        # a whole turn, including the slow LLM call, which must not block cancel()).
        self._state_locks: dict[str, threading.RLock] = {}

    def _state_lock(self, session_id: str) -> threading.RLock:
        """The session's state lock, created on first use (i.e. when a turn begins)."""
        with self._registry:
            lock = self._state_locks.get(session_id)
            if lock is None:
                lock = threading.RLock()
                self._state_locks[session_id] = lock
            return lock

    def _existing_state_lock(self, session_id: str) -> threading.RLock | None:
        """The session's state lock, or None if it never began.

        Returns None (allocating nothing) for an unknown or attacker-supplied id, so
        read-only and no-op paths cannot grow the maps for sessions that never ran.
        """
        with self._registry:
            return self._state_locks.get(session_id)

    def begin(self, session_id: str) -> int:
        """Start a turn: bump the session's generation and return this turn's id."""
        with self._state_lock(session_id):
            gen = self._gen.get(session_id, 0) + 1
            self._gen[session_id] = gen
            return gen

    def cancel(self, session_id: str) -> None:
        """Invalidate the in-flight turn for a session that has one.

        A no-op for a session with no recorded turn, so an unknown or
        attacker-supplied id can never allocate guard state. Serialized against a
        concurrent ``commit`` for the same session by the state lock, so it either
        supersedes the turn before its write or waits until that write completes.
        """
        lock = self._existing_state_lock(session_id)
        if lock is None:
            return
        with lock:
            if session_id in self._gen:
                self._gen[session_id] += 1

    def is_current(self, session_id: str, my_gen: int) -> bool:
        """True while ``my_gen`` is still the latest generation for the session."""
        lock = self._existing_state_lock(session_id)
        if lock is None:
            return self._gen.get(session_id, 0) == my_gen
        with lock:
            return self._gen.get(session_id, 0) == my_gen

    def commit(self, session_id: str, my_gen: int, save: Callable[[], None]) -> bool:
        """Persist iff this turn is still the session's current, started generation.

        The generation check and ``save()`` both run under the session's state lock,
        so a concurrent ``begin``, ``cancel``, or ``forget`` for this session cannot
        slip between the check and the write and leave an orphaned, superseded turn:
        persistence is conditional on the generation still being current at write
        time. Other sessions take their own lock and are never blocked. The lock is
        re-entrant, so ``save()`` may read this guard without deadlocking, but it
        must not mutate this session's turn state. A session with no started
        generation (never began, or already forgotten) is rejected without saving.
        """
        lock = self._existing_state_lock(session_id)
        if lock is None:
            return False
        with lock:
            current = self._gen.get(session_id)
            if current is None or current != my_gen:
                return False
            save()
            return True

    def session_lock(self, session_id: str) -> threading.Lock:
        """A stable per-session lock, so one session's turns run one at a time."""
        with self._registry:
            lock = self._session_locks.get(session_id)
            if lock is None:
                lock = threading.Lock()
                self._session_locks[session_id] = lock
            return lock

    def forget(self, session_id: str) -> None:
        """Drop a finished session's guard state so session churn stays bounded.

        The engine calls this once a session is closed and no turn can still
        ``commit`` or ``cancel`` it. The generation is dropped under the state lock
        so it never races a same-session commit; a later turn for the same id simply
        starts a fresh generation. A no-op (allocating nothing) for an unknown id.
        """
        lock = self._existing_state_lock(session_id)
        if lock is None:
            return
        with lock:
            self._gen.pop(session_id, None)
        with self._registry:
            self._session_locks.pop(session_id, None)
            self._state_locks.pop(session_id, None)
