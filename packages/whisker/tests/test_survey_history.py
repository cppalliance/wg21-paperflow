#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for whisker.survey.history: due logic (fresh, stale, upstream-newer)."""

from datetime import datetime, timedelta, timezone

import pytest
from whisker.survey.history import (
    DUE_INTERVAL_DAYS,
    append_run,
    is_due,
    last_successful_run,
    load_history,
    save_history,
)


@pytest.fixture
def cache_dir(tmp_path):
    """A temp directory standing in for the runtime cache root."""
    return tmp_path


class TestHistoryIO:
    """Basic history read/write tests."""

    def test_load_empty(self, cache_dir):
        assert load_history(cache_dir) == []

    def test_save_and_load(self, cache_dir):
        entries = [{"timestamp": "2026-07-01T00:00:00+00:00", "success": True}]
        save_history(cache_dir, entries)
        loaded = load_history(cache_dir)
        assert loaded == entries

    def test_append_run(self, cache_dir):
        append_run(
            cache_dir,
            timestamp="2026-08-01T10:00:00+00:00",
            version="2.0.0",
            corpus_version=1,
            report_dir="/some/path",
            success=True,
        )
        entries = load_history(cache_dir)
        assert len(entries) == 1
        assert entries[0]["success"] is True
        assert entries[0]["version"] == "2.0.0"

    def test_last_successful_run_none(self, cache_dir):
        assert last_successful_run(cache_dir) is None

    def test_last_successful_run_skips_failures(self, cache_dir):
        entries = [
            {"timestamp": "2026-07-01T00:00:00+00:00", "success": True, "version": "1.0"},
            {"timestamp": "2026-08-01T00:00:00+00:00", "success": False, "version": "2.0"},
        ]
        save_history(cache_dir, entries)
        last = last_successful_run(cache_dir)
        assert last is not None
        assert last["version"] == "1.0"


class TestDueLogic:
    """Due computation tests."""

    def test_never_run_is_due(self, cache_dir):
        due, reason = is_due(cache_dir)
        assert due is True
        assert reason == "never_run"

    def test_fresh_run_not_due(self, cache_dir):
        now = datetime(2026, 8, 1, tzinfo=timezone.utc)
        recent = (now - timedelta(days=5)).isoformat()
        save_history(cache_dir, [
            {"timestamp": recent, "success": True, "version": "2.0.0"},
        ])
        due, reason = is_due(cache_dir, now=now)
        assert due is False
        assert reason == "not_due"

    def test_stale_run_is_due(self, cache_dir):
        now = datetime(2026, 8, 1, tzinfo=timezone.utc)
        old = (now - timedelta(days=DUE_INTERVAL_DAYS + 1)).isoformat()
        save_history(cache_dir, [
            {"timestamp": old, "success": True, "version": "2.0.0"},
        ])
        due, reason = is_due(cache_dir, now=now)
        assert due is True
        assert reason == "stale"

    def test_exactly_30_days_is_due(self, cache_dir):
        now = datetime(2026, 8, 1, tzinfo=timezone.utc)
        boundary = (now - timedelta(days=DUE_INTERVAL_DAYS)).isoformat()
        save_history(cache_dir, [
            {"timestamp": boundary, "success": True, "version": "2.0.0"},
        ])
        due, reason = is_due(cache_dir, now=now)
        assert due is True
        assert reason == "stale"

    def test_upstream_newer_is_due(self, cache_dir):
        now = datetime(2026, 8, 1, tzinfo=timezone.utc)
        recent = (now - timedelta(days=2)).isoformat()
        save_history(cache_dir, [
            {"timestamp": recent, "success": True, "version": "2.0.0"},
        ])
        due, reason = is_due(
            cache_dir,
            upstream_version="2.1.0",
            pinned_version="2.0.0",
            now=now,
        )
        assert due is True
        assert reason == "upstream_newer"

    def test_upstream_same_not_due(self, cache_dir):
        now = datetime(2026, 8, 1, tzinfo=timezone.utc)
        recent = (now - timedelta(days=2)).isoformat()
        save_history(cache_dir, [
            {"timestamp": recent, "success": True, "version": "2.0.0"},
        ])
        due, reason = is_due(
            cache_dir,
            upstream_version="2.0.0",
            pinned_version="2.0.0",
            now=now,
        )
        assert due is False
        assert reason == "not_due"

    def test_only_failed_runs_is_due(self, cache_dir):
        save_history(cache_dir, [
            {"timestamp": "2026-07-30T00:00:00+00:00", "success": False},
        ])
        due, reason = is_due(cache_dir)
        assert due is True
        assert reason == "never_run"
