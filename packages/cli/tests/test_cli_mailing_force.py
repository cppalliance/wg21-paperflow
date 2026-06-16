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

from cli import mailing
from paperstore import SqliteBackend


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "cli", *args],
        capture_output=True,
        text=True,
    )


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
    store = SqliteBackend(tmp_path)
    _seed_year(store, "2024")
    args = argparse.Namespace(targets=["2024"], force=True)

    with patch(
        "mailing.scrape.fetch_all_mailings_for_year", side_effect=_fake_fetch
    ) as fetch:
        rc = mailing.command(args, store)

    fetch.assert_called_once_with("2024")
    assert rc == 0
    assert store.list_papers_for_year("2024")[0].title == "Refreshed Title"


def test_mailing_force_not_rejected_by_cli(tmp_path: Path):
    store = SqliteBackend(tmp_path)
    _seed_year(store, "2024")

    with patch(
        "mailing.scrape.fetch_all_mailings_for_year", side_effect=_fake_fetch
    ):
        result = subprocess.run(
            [
                sys.executable, "-m", "cli",
                "--workspace-dir", str(tmp_path),
                "mailing", "--force", "2024",
            ],
            capture_output=True,
            text=True,
        )

    assert "not valid for 'mailing'" not in result.stderr
    assert result.returncode == 0
