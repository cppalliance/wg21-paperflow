#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Offline tests for whisker survey purge and clean commands."""

import argparse
from unittest.mock import patch

from whisker.survey.cli import _clean_cmd, _purge_cmd


class TestPurgeDryRun:
    def test_purge_dryrun_no_dirs(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
        with patch("whisker.survey.cli._LEGACY_DIRS", [tmp_path / "nonexist"]):
            args = argparse.Namespace(dry_run=True, yes=False)
            result = _purge_cmd(args)
            assert result == 0

    def test_purge_dryrun_with_cache(self, tmp_path, monkeypatch):
        survey_dir = tmp_path / "appdata" / "whisker" / "survey"
        survey_dir.mkdir(parents=True)
        (survey_dir / "test.bin").write_bytes(b"x" * 1000)
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
        with patch("whisker.survey.cli._LEGACY_DIRS", []):
            args = argparse.Namespace(dry_run=True, yes=False)
            result = _purge_cmd(args)
            assert result == 0
            assert survey_dir.exists()

    def test_purge_yes_removes(self, tmp_path, monkeypatch):
        survey_dir = tmp_path / "appdata" / "whisker" / "survey"
        survey_dir.mkdir(parents=True)
        (survey_dir / "test.bin").write_bytes(b"x" * 1000)
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
        with patch("whisker.survey.cli._LEGACY_DIRS", []):
            args = argparse.Namespace(dry_run=False, yes=True)
            result = _purge_cmd(args)
            assert result == 0
            assert not survey_dir.exists()


class TestCleanDryRun:
    def test_clean_dryrun_shows_runs(self, tmp_path, monkeypatch):
        bench = tmp_path / "benchmark"
        runs = bench / "runs" / "2026-08"
        runs.mkdir(parents=True)
        (runs / "data.json").write_text("{}")
        with patch("whisker.survey.cli._default_bench_root", return_value=bench):
            args = argparse.Namespace(dry_run=True)
            result = _clean_cmd(args)
            assert result == 0
            assert runs.exists()

    def test_clean_removes_runs(self, tmp_path, monkeypatch):
        bench = tmp_path / "benchmark"
        runs = bench / "runs" / "2026-08"
        runs.mkdir(parents=True)
        (runs / "data.json").write_text("{}")
        corpus = bench / "corpus"
        corpus.mkdir(parents=True)
        (corpus / "corpus.json").write_text("{}")
        with patch("whisker.survey.cli._default_bench_root", return_value=bench):
            args = argparse.Namespace(dry_run=False)
            result = _clean_cmd(args)
            assert result == 0
            assert not runs.exists()
            assert corpus.exists()
