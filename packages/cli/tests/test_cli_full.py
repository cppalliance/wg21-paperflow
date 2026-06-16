"""CLI tests for ``paperflow full``."""

from __future__ import annotations

import argparse
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

from cli import full as full_mod
from paperstore import SqliteBackend


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "cli", *args],
        capture_output=True,
        text=True,
    )


def test_full_help_lists_expected_flags():
    result = _run("full", "--help")
    assert result.returncode == 0
    for flag in ("--force", "--verify", "--concurrency", "--extract-vector-images"):
        assert flag in result.stdout, f"missing {flag} in help"


def test_full_help_differs_from_agora():
    full_help = _run("full", "--help").stdout
    agora_help = _run("agora", "--help").stdout
    assert full_help != agora_help


def test_full_all_target_accepted():
    result = _run("full", "all", "--help")
    assert result.returncode == 0


def test_full_forwards_extract_vector_images(tmp_path: Path):
    store = SqliteBackend(tmp_path)
    args = argparse.Namespace(
        targets=["2026"],
        force=False,
        verify=False,
        concurrency=None,
        extract_vector_images=True,
        vector_whiteout_text=True,
    )
    captured: dict = {}

    async def _fake_run_full(*a, **kw):
        captured.update(kw)
        results = {
            "mailing": {"succeeded": [], "skipped": ["2026"], "failed": []},
            "download": {"succeeded": [], "skipped": [], "failed": []},
            "convert": {"succeeded": [], "skipped": [], "failed": []},
        }
        on_stage = kw.get("on_stage_complete")
        if on_stage:
            on_stage("mailing", results["mailing"])
            on_stage("download", results["download"])
            on_stage("convert", results["convert"])
        return results

    with (
        patch("cli.progress.make_progress_handler", return_value=(nullcontext(), None)),
        patch("cli.full.run_full", new=_fake_run_full),
    ):
        rc = full_mod.command(args, store)

    assert rc == 0
    assert captured.get("extract_vector") is True
    assert captured.get("whiteout_text") is True


def test_full_prints_stage_summaries_and_final_complete(tmp_path: Path, capsys):
    store = SqliteBackend(tmp_path)
    args = argparse.Namespace(
        targets=["2026"],
        force=False,
        verify=False,
        concurrency=None,
        extract_vector_images=False,
        vector_whiteout_text=False,
    )

    async def _fake_run_full(*a, **kw):
        results = {
            "mailing": {"succeeded": [{"year": "2026", "papers": 1}], "skipped": [], "failed": []},
            "download": {"succeeded": ["P1000R0"], "skipped": [], "failed": []},
            "convert": {"succeeded": ["P1000R0"], "skipped": [], "failed": []},
        }
        on_stage = kw.get("on_stage_complete")
        if on_stage:
            on_stage("mailing", results["mailing"])
            on_stage("download", results["download"])
            on_stage("convert", results["convert"])
        return results

    with (
        patch("cli.progress.make_progress_handler", return_value=(nullcontext(), None)),
        patch("cli.full.run_full", new=_fake_run_full),
    ):
        rc = full_mod.command(args, store)

    assert rc == 0
    out = capsys.readouterr().out
    assert "Mailing: 1 scraped, 0 skipped, 0 failed" in out
    assert "Download: 1 succeeded, 0 skipped, 0 failed" in out
    assert "Convert: 1 succeeded, 0 skipped, 0 failed" in out
    assert out.strip().endswith("Full: complete")
