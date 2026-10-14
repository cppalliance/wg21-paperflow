#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Run history and due-computation for the whisker survey monitor.

Each competitor maintains a history JSON file in the runtime cache root
recording timestamps, versions, report paths, and success flags. The
due-computation determines whether a new run is needed (older than 30 days
or a newer upstream version was detected).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

DUE_INTERVAL_DAYS = 30
_HISTORY_FILENAME = "survey_history.json"


# ---------------------------------------------------------------------------
# History I/O
# ---------------------------------------------------------------------------


def history_path(cache_root: Path) -> Path:
    """Return the path to the history JSON for a competitor."""
    return cache_root / _HISTORY_FILENAME


def load_history(cache_root: Path) -> list[dict[str, Any]]:
    """Load the run history list. Returns empty list if no history."""
    path = history_path(cache_root)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Cannot read history at %s: %s", path, exc)
    return []


def save_history(cache_root: Path, entries: list[dict[str, Any]]) -> None:
    """Persist the run history list."""
    path = history_path(cache_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def append_run(
    cache_root: Path,
    *,
    timestamp: str,
    version: str,
    corpus_version: int,
    report_dir: str,
    success: bool,
) -> None:
    """Append a completed run record to history."""
    entries = load_history(cache_root)
    entries.append({
        "timestamp": timestamp,
        "version": version,
        "corpus_version": corpus_version,
        "report_dir": report_dir,
        "success": success,
    })
    save_history(cache_root, entries)


# ---------------------------------------------------------------------------
# Due computation
# ---------------------------------------------------------------------------


def last_successful_run(cache_root: Path) -> dict[str, Any] | None:
    """Return the most recent successful run entry, or None."""
    entries = load_history(cache_root)
    for entry in reversed(entries):
        if entry.get("success"):
            return entry
    return None


def is_due(
    cache_root: Path,
    *,
    upstream_version: str | None = None,
    pinned_version: str | None = None,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """Determine if a new run is due.

    Returns (is_due, reason). Reasons:
    - "never_run": no successful run recorded
    - "stale": last run older than DUE_INTERVAL_DAYS
    - "upstream_newer": upstream version differs from pinned
    - "not_due": fresh and no newer upstream
    """
    if now is None:
        now = datetime.now(timezone.utc)

    last = last_successful_run(cache_root)
    if last is None:
        return True, "never_run"

    # Check age
    try:
        last_time = datetime.fromisoformat(last["timestamp"])
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)
        age_days = (now - last_time).days
        if age_days >= DUE_INTERVAL_DAYS:
            return True, "stale"
    except (KeyError, ValueError):
        return True, "never_run"

    # Check upstream version
    if upstream_version and pinned_version:
        if upstream_version != pinned_version:
            return True, "upstream_newer"

    return False, "not_due"
