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


def test_service_overrides_function_removed():
    """The CLI no longer parses ``--service``; the helper is gone."""
    import cli._process as proc

    assert not hasattr(proc, "_parse_service_overrides")


def test_service_flag_rejected_by_cli():
    """``paperflow assay --service ...`` is no longer a recognized flag."""
    result = subprocess.run(
        [sys.executable, "-m", "cli", "assay", "P0000R0", "--service", "x"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "--service" in combined or "unrecognized" in combined


def test_classifier_flag_rejected_by_cli():
    """``paperflow assay --classifier ...`` is no longer a recognized flag."""
    result = subprocess.run(
        [sys.executable, "-m", "cli", "assay", "P0000R0", "--classifier", "nli-small"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "--classifier" in combined or "unrecognized" in combined


def test_provider_flag_rejected_by_cli():
    """``paperflow assay --provider ...`` is no longer a recognized flag."""
    result = subprocess.run(
        [sys.executable, "-m", "cli", "assay", "P0000R0", "--provider", "cpu-fp32"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "--provider" in combined or "unrecognized" in combined
