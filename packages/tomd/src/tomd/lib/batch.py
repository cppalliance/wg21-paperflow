#
# Copyright (c) 2026 Dmitriy Chukhin (dmitriy@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Shared parallel batch runner for tomd QA and content-check batches."""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

from paperstore.progress import ProgressCallback, ProgressEvent

__all__ = [
    "BatchRunResult",
    "format_batch_finished",
    "format_batch_progress_line",
    "format_batch_timeout",
    "run_parallel_batch",
]

_DEFAULT_POLL_INTERVAL_SEC = 0.5


@dataclass(frozen=True)
class BatchRunResult[TResult]:
    """Outcome of a parallel or sequential batch run."""

    outcomes: tuple[tuple[str, TResult | Exception], ...]
    timed_out: tuple[str, ...]
    elapsed_sec: float


def format_batch_progress_line(
    done: int, total: int, item_id: str, t0: float,
) -> str:
    """Return the carriage-return progress line for stderr."""
    elapsed = time.monotonic() - t0
    rate = done / elapsed if elapsed > 0 else 0.0
    eta = (total - done) / rate if rate > 0 else 0.0
    return (
        f"\r  [{done}/{total}] {item_id:<40} "
        f"{rate:.1f} files/s  ETA {eta/60:.0f}m"
    )


def format_batch_finished(elapsed_sec: float, total: int) -> str:
    """Return the trailing batch-finished line for stderr."""
    avg = elapsed_sec / total if total else 0.0
    return f"\n  Finished in {elapsed_sec/60:.1f} minutes ({avg:.1f}s/file avg)"


def format_batch_timeout(timed_out: list[str], timeout_sec: int) -> str:
    """Return the timeout abort line for stderr."""
    return (
        f"\n  TIMEOUT: {len(timed_out)} files aborted "
        f"(no progress for {timeout_sec}s): "
        f"{', '.join(timed_out)}"
    )


def _fire_progress(
    on_progress: ProgressCallback | None,
    done: int,
    total: int,
    item_id: str,
) -> None:
    if on_progress is None:
        return
    on_progress(ProgressEvent(
        step=done,
        total=total,
        name=item_id,
        pct=done / total if total else 1.0,
    ))


def run_parallel_batch[TItem, TResult](
    items: list[tuple[str, TItem]],
    worker: Callable[[TItem], TResult],
    *,
    workers: int = 1,
    timeout_sec: int = 120,
    poll_interval_sec: float = _DEFAULT_POLL_INTERVAL_SEC,
    on_progress: ProgressCallback | None = None,
) -> BatchRunResult[TResult]:
    """Run *worker* over *items* with optional process parallelism.

    Each entry in *items* is ``(item_id, payload)``. Progress fires
    after each completion with ``ProgressEvent.step`` equal to the
    1-based completion count (matching existing QA/content-check output).
    """
    total = len(items)
    outcomes: list[tuple[str, TResult | Exception]] = []
    timed_out: list[str] = []
    t0 = time.monotonic()

    if total == 0:
        return BatchRunResult(
            outcomes=(),
            timed_out=(),
            elapsed_sec=0.0,
        )

    if workers > 1:
        done_count = 0
        with ProcessPoolExecutor(max_workers=workers) as pool:
            future_to_id = {
                pool.submit(worker, payload): item_id
                for item_id, payload in items
            }
            pending = set(future_to_id.keys())
            last_completion = time.monotonic()

            while pending:
                newly_done = {f for f in pending if f.done()}

                if newly_done:
                    last_completion = time.monotonic()
                    for f in newly_done:
                        pending.discard(f)
                        done_count += 1
                        item_id = future_to_id[f]
                        _fire_progress(on_progress, done_count, total, item_id)
                        try:
                            outcomes.append((item_id, f.result()))
                        except Exception as exc:
                            outcomes.append((item_id, exc))
                elif time.monotonic() - last_completion > timeout_sec:
                    for f in pending:
                        item_id = future_to_id[f]
                        timed_out.append(item_id)
                        f.cancel()
                    break
                else:
                    time.sleep(poll_interval_sec)

            pool.shutdown(wait=False, cancel_futures=True)
    else:
        for i, (item_id, payload) in enumerate(items, 1):
            try:
                outcomes.append((item_id, worker(payload)))
            except Exception as exc:
                outcomes.append((item_id, exc))
            _fire_progress(on_progress, i, total, item_id)

    return BatchRunResult(
        outcomes=tuple(outcomes),
        timed_out=tuple(timed_out),
        elapsed_sec=time.monotonic() - t0,
    )
