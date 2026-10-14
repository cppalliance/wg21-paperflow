#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Shared command-line helpers for deterministic and advisory lanes."""

from __future__ import annotations

import sys
from pathlib import Path

from paperstore.sqlite_backend import SqliteBackend

from whisker import constants as C

__all__ = ["open_backend", "render_progress", "verdict_exit_code"]

_GATE_ACCEPTS = {
    "pass": {"pass"},
    "review": {"pass", "review"},
    "not-llm-readable": {"pass", "review", "not-llm-readable"},
}
_PROGRESS_WIDTH = 28


def render_progress(done: int, total: int, label: str = "") -> int:
    """Draw an in-place progress bar on terminal stderr and return its width."""
    if not sys.stderr.isatty() or total <= 0:
        return 0
    filled = int(_PROGRESS_WIDTH * done / total)
    bar = "#" * filled + "-" * (_PROGRESS_WIDTH - filled)
    pct = 100 * done // total
    suffix = f" {label:<12}" if label else ""
    line = f"  whisker [{bar}] {done}/{total} ({pct}%){suffix}"
    sys.stderr.write("\r" + line)
    sys.stderr.flush()
    if done >= total:
        sys.stderr.write("\n")
        sys.stderr.flush()
    return len(line)


def open_backend(workspace: str | None) -> SqliteBackend:
    """Open the configured paperstore workspace."""
    if workspace:
        return SqliteBackend(Path(workspace))
    return SqliteBackend.from_env()


def verdict_exit_code(verdicts: list[str], gate: str) -> int:
    """Return the typed CLI exit code for *verdicts* under *gate*."""
    accepted = _GATE_ACCEPTS[gate]
    if "not-llm-readable" in verdicts and "not-llm-readable" not in accepted:
        return C.EXIT_FAIL
    if "review" in verdicts and "review" not in accepted:
        return C.EXIT_REVIEW
    return C.EXIT_OK
