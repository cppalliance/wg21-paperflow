#
# Copyright (c) 2026 Greg Kaleka (greg@gregkaleka.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""CLI tests for ``paperflow mailing --force``."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from cli.__main__ import _validate_flags
from paperstore import SqliteBackend


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "cli", *args],
        capture_output=True,
        text=True,
    )


def main_with_argv(argv: list[str]) -> int:
    from cli.__main__ import main

    with patch.object(sys, "argv", ["cli", *argv]):
        return main()


def test_mailing_help_lists_force():
    result = _run("mailing", "--help")
    assert result.returncode == 0
    assert "--force" in result.stdout


def _fake_fetch(year: str) -> dict:
    return {
        f"{year}-01": [
            {"paper_id": "P1000R0", "title": "Refreshed Title", "url": "x"}
        ]
    }


def _seed_year(store: SqliteBackend, year: str) -> None:
    store.upsert_year(year, [{"paper_id": "P1000R0", "title": "Original Title"}])


@pytest.mark.parametrize("force_flag", ["--force", "-f"])
def test_mailing_force_flag_accepted(tmp_path: Path, force_flag: str):
    _seed_year(SqliteBackend(tmp_path), "2024")

    with patch(
        "mailing.scrape.fetch_all_mailings_for_year", side_effect=_fake_fetch
    ) as fetch:
        rc = main_with_argv([
            "--workspace-dir", str(tmp_path),
            "mailing", force_flag, "2024",
        ])

    fetch.assert_called_once_with("2024")
    assert rc == 0
    store = SqliteBackend(tmp_path)
    assert store.list_papers_for_year("2024")[0].title == "Refreshed Title"


def test_mailing_force_not_rejected_by_cli():
    """``--force`` is in the mailing flag allowlist."""
    args = argparse.Namespace(force=True)
    _validate_flags("mailing", args)


def test_mailing_force_reaches_command(tmp_path: Path):
    with patch("cli.mailing.command", return_value=0) as cmd:
        rc = main_with_argv([
            "--workspace-dir", str(tmp_path),
            "mailing", "--force", "2024",
        ])

    assert rc == 0
    assert cmd.call_args[0][0].force is True
