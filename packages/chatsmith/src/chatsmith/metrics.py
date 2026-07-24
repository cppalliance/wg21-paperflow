#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Latency instrumentation for the turn pipeline (STT -> normalize -> LLM -> TTS).

One machine-readable JSON record per turn is emitted to the ``chatsmith.metrics``
logger. The glue layer attaches a file handler so records land in a per-session
sink for later analysis; the per-phase durations are also available to the API.

Timing is captured for maintenance/improvement and is exportable with the chat
(``chatsmith export --with-timings``); it is deliberately NOT shown to end users.
A developer overlay in the local GUI is gated behind ``CHATSMITH_DEV_METRICS``.

Record shape (one JSON object per line)::

    {"ts": 1721201234.56, "source": "server", "event": "turn",
     "session_id": "…", "turn": 6, "path": "text",
     "timings_ms": {"normalize": 182.4, "llm": 2103.7, "tts": 648.2,
                    "server_total": 2951.1}}
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

LOGGER_NAME = "chatsmith.metrics"
metrics_log = logging.getLogger(LOGGER_NAME)


def now_ms() -> float:
    """Monotonic clock in milliseconds, for measuring durations (not wall-clock)."""
    return time.perf_counter() * 1000.0


@dataclass
class Stopwatch:
    """Accumulate named phase durations (ms) over one turn.

    ``measure`` times a block; a re-entered phase accumulates (a retried call sums
    rather than overwrites), which keeps totals honest without extra bookkeeping.
    """

    spans: dict[str, float] = field(default_factory=dict)

    @contextmanager
    def measure(self, phase: str) -> Iterator[None]:
        start = now_ms()
        try:
            yield
        finally:
            self.record(phase, now_ms() - start)

    def record(self, phase: str, ms: float) -> None:
        self.spans[phase] = round(self.spans.get(phase, 0.0) + ms, 1)

    def as_dict(self) -> dict[str, float]:
        return dict(self.spans)


def turn_record(
    *,
    source: str,
    session_id: str,
    turn: Any,
    path: str,
    timings_ms: dict[str, float],
    **extra: Any,
) -> dict[str, Any]:
    """Build a normalized per-turn record (adds wall-clock ``ts`` and ``event``)."""
    return {
        "ts": round(time.time(), 3),
        "source": source,
        "event": "turn",
        "session_id": session_id,
        "turn": turn,
        "path": path,
        "timings_ms": timings_ms,
        **extra,
    }


def emit(record: dict[str, Any]) -> dict[str, Any]:
    """Write one metrics record as a compact JSON line; never raises."""
    try:
        metrics_log.info(json.dumps(record, separators=(",", ":"), ensure_ascii=False))
    except Exception:  # metrics must never break a turn
        logging.getLogger(__name__).debug("metrics emit failed", exc_info=True)
    return record
