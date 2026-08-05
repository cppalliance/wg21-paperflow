#
# Copyright (c) 2026 Greg Kaleka (greg@gregkaleka.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Smoke tests for the ``paperflow`` CLI entry point.

These run the package as a script (``python -m cli``) so they
exercise the same code path users hit. The goal is to catch import
errors, broken subcommand registration, or argparse setup regressions
before they reach a release.
"""

from __future__ import annotations

import subprocess
import sys

import pytest


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "cli", *args],
        capture_output=True,
        text=True,
    )


def test_no_args_prints_help_and_exits_zero():
    result = _run()
    assert result.returncode == 0
    assert "paperflow" in result.stdout.lower()


def test_top_level_help_exits_zero():
    result = _run("--help")
    assert result.returncode == 0
    assert "paperflow" in result.stdout.lower()


@pytest.mark.parametrize("subcommand", ["mailing", "download", "convert", "full"])
def test_each_subcommand_help_exits_zero(subcommand: str):
    result = _run(subcommand, "--help")
    assert result.returncode == 0, (
        f"`paperflow {subcommand} --help` exited {result.returncode}\n"
        f"stderr: {result.stderr}"
    )


def test_no_verb_fallback_routes_to_full():
    # `paperflow 2026 --help` should be rewritten to `paperflow full 2026 --help`
    # by the no-verb fallback. The full subcommand's help text differs from the
    # top-level help, so we assert on a flag that only `full` registers.
    full_help = _run("full", "--help").stdout
    fallback_help = _run("2026", "--help").stdout
    assert fallback_help == full_help, (
        "no-verb fallback should produce the same help as `full --help`"
    )


@pytest.mark.parametrize(
    ("argv", "msg"),
    [
        (["mailing", "P1234R5"], "not paper IDs"),
        (["mailing", "2026-01"], "not paper IDs"),
        (["full", "2026-01"], "not year-month"),
        (["agora", "P0000R0", "P0001R0"], "accepts exactly one target"),
        (["assay", "P0000R0", "P0001R0"], "accepts exactly one target"),
        (["agora", "2026"], "not bare years"),
    ],
)
def test_invalid_targets_rejected(argv: list[str], msg: str):
    result = _run(*argv)
    assert result.returncode != 0
    assert msg in result.stderr


def test_assay_accepts_bare_year():
    from cli.__main__ import _validate_targets

    _validate_targets("assay", ["2026"])


@pytest.mark.parametrize(
    ("argv", "msg"),
    [
        (["full", "all", "2026"], "`all` must be the only target"),
        (["full", "2026", "all"], "`all` must be the only target"),
        (["mailing", "all", "2026"], "`all` must be the only target"),
    ],
)
def test_all_target_mixing_rejected(argv: list[str], msg: str):
    result = _run(*argv)
    assert result.returncode != 0
    assert msg in result.stderr
