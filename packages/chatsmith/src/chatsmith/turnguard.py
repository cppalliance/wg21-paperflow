#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Per-session turn guard for cancel-during-thinking.

A monotonic generation per session lets a newer turn - or an explicit cancel when
the user resumes talking - invalidate the reply currently in flight. The in-flight
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
        self._lock = threading.Lock()  # guards the dicts below
        self._gen: dict[str, int] = {}
        self._session_locks: dict[str, threading.Lock] = {}

    def begin(self, session_id: str) -> int:
        """Start a turn: bump the session's generation and return this turn's id."""
        with self._lock:
            gen = self._gen.get(session_id, 0) + 1
            self._gen[session_id] = gen
            return gen

    def cancel(self, session_id: str) -> None:
        """Invalidate the in-flight turn for a session that has one.

        A no-op for a session with no recorded turn, so an unknown or
        attacker-supplied id can never allocate guard state.
        """
        with self._lock:
            if session_id in self._gen:
                self._gen[session_id] += 1

    def is_current(self, session_id: str, my_gen: int) -> bool:
        """True while ``my_gen`` is still the latest generation for the session."""
        with self._lock:
            return self._gen.get(session_id, 0) == my_gen

    def commit(self, session_id: str, my_gen: int, save: Callable[[], None]) -> bool:
        """Persist atomically iff this turn is still current.

        The generation check and ``save()`` run under one lock, so a concurrent
        ``cancel`` (or a newer ``begin``) cannot slip between them and leave an
        orphaned turn. Returns False without saving when the turn was superseded.
        """
        with self._lock:
            if self._gen.get(session_id, 0) != my_gen:
                return False
            save()
            return True

    def session_lock(self, session_id: str) -> threading.Lock:
        """A stable per-session lock, so one session's turns run one at a time."""
        with self._lock:
            lock = self._session_locks.get(session_id)
            if lock is None:
                lock = threading.Lock()
                self._session_locks[session_id] = lock
            return lock
