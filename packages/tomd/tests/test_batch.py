"""Tests for tomd.lib.batch."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from paperstore.progress import ProgressEvent

from tomd.lib.batch import (
    format_batch_finished,
    format_batch_progress_line,
    format_batch_timeout,
    run_parallel_batch,
)


def test_sequential_batch_returns_all_outcomes():
    items = [("a", 1), ("b", 2), ("c", 3)]
    run = run_parallel_batch(items, lambda x: x * 2, workers=1)
    assert run.timed_out == []
    assert run.outcomes == [("a", 2), ("b", 4), ("c", 6)]
    assert run.elapsed_sec >= 0.0


def test_on_progress_fires_per_completion():
    events: list[ProgressEvent] = []

    def on_progress(ev: ProgressEvent) -> None:
        events.append(ev)

    items = [("p1", 1), ("p2", 2)]
    run_parallel_batch(items, lambda x: x, workers=1, on_progress=on_progress)

    assert len(events) == 2
    assert events[0].step == 1
    assert events[0].total == 2
    assert events[0].name == "p1"
    assert events[0].pct == 0.5
    assert events[1].step == 2
    assert events[1].name == "p2"
    assert events[1].pct == 1.0


def test_format_batch_progress_line_shape():
    with patch("tomd.lib.batch.time.monotonic", return_value=10.0):
        line = format_batch_progress_line(2, 5, "P1234R0", t0=8.0)
    assert line.startswith("\r  [2/5]")
    assert "P1234R0" in line
    assert "files/s" in line
    assert "ETA" in line


def test_format_batch_finished():
    text = format_batch_finished(120.0, 4)
    assert "Finished in" in text
    assert "30.0s/file avg" in text


def test_format_batch_timeout():
    text = format_batch_timeout(["P1", "P2"], 120)
    assert "TIMEOUT: 2 files aborted" in text
    assert "P1" in text
    assert "P2" in text


def test_worker_exception_stored_as_outcome():
    def boom(_x: int) -> int:
        raise RuntimeError("worker failed")

    run = run_parallel_batch([("x", 1)], boom, workers=1)
    assert len(run.outcomes) == 1
    item_id, outcome = run.outcomes[0]
    assert item_id == "x"
    assert isinstance(outcome, RuntimeError)
    assert str(outcome) == "worker failed"


def test_empty_items():
    run = run_parallel_batch([], lambda x: x, workers=1)
    assert run.outcomes == []
    assert run.timed_out == []
    assert run.elapsed_sec == 0.0
