"""Tests for tomd.lib.batch."""

from __future__ import annotations

from concurrent.futures import Future
from unittest.mock import patch

from paperstore.progress import ProgressEvent

from tomd.lib.batch import (
    format_batch_finished,
    format_batch_progress_line,
    format_batch_timeout,
    run_parallel_batch,
)


def _double(x: int) -> int:
    return x * 2


def test_sequential_batch_returns_all_outcomes():
    items = [("a", 1), ("b", 2), ("c", 3)]
    run = run_parallel_batch(items, lambda x: x * 2, workers=1)
    assert run.timed_out == ()
    assert run.outcomes == (("a", 2), ("b", 4), ("c", 6))
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
    assert "(no progress for 120s)" in text
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
    assert run.outcomes == ()
    assert run.timed_out == ()
    assert run.elapsed_sec == 0.0


def test_parallel_batch_collects_outcomes():
    future_a = Future()
    future_a.set_result(2)
    future_b = Future()
    future_b.set_result(4)

    class FakePool:
        def __init__(self, max_workers: int) -> None:
            pass

        def submit(self, worker, payload):  # noqa: ANN001
            if payload == 1:
                return future_a
            return future_b

        def __enter__(self) -> FakePool:
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def shutdown(self, *, wait: bool = False, cancel_futures: bool = False) -> None:
            pass

    with patch("tomd.lib.batch.ProcessPoolExecutor", FakePool):
        run = run_parallel_batch([("a", 1), ("b", 2)], _double, workers=2)

    assert run.timed_out == ()
    assert sorted(run.outcomes) == [("a", 2), ("b", 4)]


def test_parallel_batch_timeout_aborts_pending():
    done_future = Future()
    done_future.set_result(2)
    pending_future = Future()

    class FakePool:
        def __init__(self, max_workers: int) -> None:
            self._submit_count = 0

        def submit(self, worker, payload):  # noqa: ANN001
            self._submit_count += 1
            if payload == 1:
                return done_future
            return pending_future

        def __enter__(self) -> FakePool:
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def shutdown(self, *, wait: bool = False, cancel_futures: bool = False) -> None:
            pass

    monotonic_values = iter([0.0, 0.0, 0.0, 200.0, 200.0])

    with patch("tomd.lib.batch.ProcessPoolExecutor", FakePool):
        with patch(
            "tomd.lib.batch.time.monotonic",
            side_effect=lambda: next(monotonic_values),
        ):
            with patch("tomd.lib.batch.time.sleep"):
                run = run_parallel_batch(
                    [("a", 1), ("b", 2)],
                    _double,
                    workers=2,
                    timeout_sec=120,
                )

    assert run.timed_out == ("b",)
    assert run.outcomes == (("a", 2),)
