#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for removed ``--service`` / ``--classifier`` / ``--provider`` CLI flags."""

from __future__ import annotations

import subprocess
import sys

import pytest

_SUBPROCESS_KW = {
    "capture_output": True,
    "text": True,
    "timeout": 60,
    "stdin": subprocess.DEVNULL,
}


def test_service_overrides_function_removed():
    """The CLI no longer parses ``--service``; the helper is gone."""
    import cli._process as proc

    assert not hasattr(proc, "_parse_service_overrides")


@pytest.mark.parametrize(
    ("flag", "value"),
    [
        ("--service", "x"),
        ("--classifier", "nli-small"),
        ("--provider", "cpu-fp32"),
    ],
)
def test_removed_flag_rejected_by_cli(flag, value):
    """Removed override flags are rejected at argparse with exit code 2."""
    result = subprocess.run(
        [sys.executable, "-m", "cli", "assay", "P0000R0", flag, value],
        **_SUBPROCESS_KW,
    )
    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr
