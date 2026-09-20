#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for `whisker survey reports`, the report locator.

The ordering test is the point of this file. Run bundles are named by date, and
sorting those names in reverse puts ``2026-08-pilot`` ahead of ``2026-08``, so a
name-sorted implementation reports a superseded pilot as the newest report. That
is a wrong answer that looks right, which is worse than an error.
"""

from __future__ import annotations

import os
import time

from whisker.survey.cli import _find_reports


def _write(path, text: str, age_seconds: float = 0.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if age_seconds:
        stamp = time.time() - age_seconds
        os.utime(path, (stamp, stamp))
    return path


class TestFindReports:
    def test_empty_when_no_report_roots(self, tmp_path):
        assert _find_reports(tmp_path) == []

    def test_finds_published_reports(self, tmp_path):
        _write(tmp_path / "reports" / "2026-08" / "report.pdf", "a")

        assert [p.name for p in _find_reports(tmp_path)] == ["report.pdf"]

    def test_finds_reports_at_differing_depths(self, tmp_path):
        runs = tmp_path / "runs"
        _write(runs / "2026-08" / "report.pdf", "a")
        _write(runs / "2026-07-pilot" / "report" / "report.pdf", "b")

        names = {p.name for p in _find_reports(tmp_path)}
        assert names == {"report.pdf"}
        assert len(_find_reports(tmp_path)) == 2

    def test_legacy_inline_reports_still_found_alongside_published(self, tmp_path):
        """Older bundles kept their report inline; moving to reports/ must not
        make those invisible, or history disappears from the listing."""
        published = _write(tmp_path / "reports" / "2026-09" / "report.pdf", "new")
        _write(tmp_path / "runs" / "2026-08" / "report.pdf", "old",
               age_seconds=86_400)

        found = _find_reports(tmp_path)
        assert len(found) == 2
        assert found[0] == published

    def test_newest_by_mtime_not_by_directory_name(self, tmp_path):
        """A pilot bundle sorts after its successor by name but must not win."""
        runs = tmp_path / "runs"
        current = _write(runs / "2026-08" / "report.pdf", "current")
        _write(runs / "2026-08-pilot" / "report" / "report.pdf", "old",
               age_seconds=86_400)

        assert _find_reports(tmp_path)[0] == current

    def test_comparison_appendices_are_excluded(self, tmp_path):
        runs = tmp_path / "runs"
        _write(runs / "2026-08" / "report.pdf", "main")
        _write(runs / "2026-08" / "compare" / "pdf" / "report.pdf", "appendix")

        found = _find_reports(tmp_path)
        assert len(found) == 1
        assert "compare" not in found[0].parts

    def test_findings_documents_are_included(self, tmp_path):
        runs = tmp_path / "runs"
        _write(runs / "2026-08" / "report.md", "r")
        _write(runs / "2026-08" / "findings-marker.md", "m")
        _write(runs / "2026-08" / "findings-whisker.md", "w")

        stems = {p.stem for p in _find_reports(tmp_path)}
        assert stems == {"report", "findings-marker", "findings-whisker"}

    def test_unrelated_files_are_ignored(self, tmp_path):
        runs = tmp_path / "runs"
        _write(runs / "2026-08" / "report.pdf", "r")
        _write(runs / "2026-08" / "manifest.json", "{}")
        _write(runs / "2026-08" / "scores.json", "{}")

        assert [p.name for p in _find_reports(tmp_path)] == ["report.pdf"]
