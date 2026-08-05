#
# Copyright (c) 2026 Glenn Siegman (glenn@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the agora verb's ``--no-research`` flag.

The flag rides the shared ``run_process_command`` driver: it must
reach ``process_paper`` as ``research=False``, default to ``True``
when absent, and stay agora-only in the verb flag allowlist.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from paperstore import SqliteBackend

from cli.postconditions import ProcessResult


@pytest.fixture
def backend(tmp_path: Path) -> SqliteBackend:
    backend = SqliteBackend(tmp_path)
    backend.upsert_year("2026", [{"paper_id": "P1234R0"}])
    return backend


def _stub_args(target: str, **extra) -> argparse.Namespace:
    return SimpleNamespace(
        targets=[target],
        debug=False,
        trace=None,
        force=True,
        **extra,
    )


def _run(args, backend) -> dict:
    """Drive run_process_command with a recording process_paper stub."""
    seen: dict = {}

    async def fake(pid, be, **kwargs):
        seen.update(kwargs)
        return ProcessResult(final_status=5, stages_run=[4])

    from cli._process import run_process_command
    with patch("cli._process.process_paper", new=fake):
        rc = run_process_command(args, backend, through=5)
    assert rc == 0
    return seen


def test_no_research_flag_reaches_process_paper(backend: SqliteBackend):
    seen = _run(_stub_args("P1234R0", no_research=True), backend)
    assert seen["research"] is False


def test_research_defaults_to_on(backend: SqliteBackend):
    seen = _run(_stub_args("P1234R0"), backend)
    assert seen["research"] is True


def test_no_research_is_agora_only():
    """The flag allowlist admits ``--no-research`` for agora and
    rejects it for the other process verbs."""
    from cli.__main__ import _validate_flags

    args = SimpleNamespace(no_research=True)
    _validate_flags("agora", args)
    with pytest.raises(SystemExit):
        _validate_flags("convert", args)
