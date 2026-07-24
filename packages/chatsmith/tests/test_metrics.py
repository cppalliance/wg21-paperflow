#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

from __future__ import annotations

import json
import logging

from chatsmith.metrics import LOGGER_NAME, Stopwatch, emit, turn_record


def test_stopwatch_accumulates_a_re_entered_phase() -> None:
    # A retried phase sums rather than overwrites, so totals stay honest; spans are
    # rounded to a tenth of a millisecond.
    sw = Stopwatch()
    sw.record("llm", 100.0)
    sw.record("llm", 50.04)
    assert sw.as_dict() == {"llm": 150.0}


def test_stopwatch_measure_times_a_block() -> None:
    sw = Stopwatch()
    with sw.measure("normalize"):
        pass
    spans = sw.as_dict()
    assert "normalize" in spans
    assert spans["normalize"] >= 0.0


def test_stopwatch_as_dict_is_a_snapshot_copy() -> None:
    # Mutating the returned dict must not leak back into the stopwatch.
    sw = Stopwatch()
    sw.record("a", 1.0)
    snapshot = sw.as_dict()
    snapshot["a"] = 999.0
    assert sw.as_dict() == {"a": 1.0}


def test_turn_record_has_canonical_shape() -> None:
    rec = turn_record(
        source="server",
        session_id="s1",
        turn=6,
        path="text",
        timings_ms={"llm": 10.0},
    )
    assert rec["event"] == "turn"
    assert rec["source"] == "server"
    assert rec["session_id"] == "s1"
    assert rec["turn"] == 6
    assert rec["path"] == "text"
    assert rec["timings_ms"] == {"llm": 10.0}
    assert isinstance(rec["ts"], float)


def test_turn_record_extra_cannot_clobber_canonical_keys() -> None:
    # extra is merged first, so a colliding caller field can never overwrite a
    # canonical key (which would corrupt downstream JSON-line parsing).
    rec = turn_record(
        source="server",
        session_id="s1",
        turn=1,
        path="text",
        timings_ms={},
        event="malicious",
        note="kept",
    )
    assert rec["event"] == "turn"
    assert rec["note"] == "kept"


def test_emit_writes_one_json_line(caplog) -> None:
    record = {"event": "turn", "session_id": "s1", "turn": 2}
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        returned = emit(record)
    assert returned is record
    assert len(caplog.records) == 1
    assert json.loads(caplog.records[0].getMessage()) == record


def test_emit_never_raises_on_unserializable_record() -> None:
    # Metrics must never break a turn: a non-JSON-serializable payload is swallowed
    # and the record is still returned unchanged.
    record = {"bad": object()}
    returned = emit(record)
    assert returned is record
