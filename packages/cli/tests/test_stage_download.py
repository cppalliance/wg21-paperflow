#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for ``cli.process._stage_download`` failure propagation.

Lives in its own module (not ``test_process.py``) on purpose: that
module's autouse ``_patch_stage_bodies`` fixture replaces
``_stage_download`` for every test, so the real body can only be
exercised from a module without that stub. These tests assert the
download stage RAISES on HTTP/transport failure (so ``process_paper``'s
outer handler marks the paper failed and stops) rather than swallowing
the error with ``fail_paper`` + return.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from paperstore import SqliteBackend
from cli.process import _stage_download


@pytest.fixture
def backend(tmp_path: Path) -> SqliteBackend:
    return SqliteBackend(tmp_path)


@pytest.fixture
def staged_paper(backend: SqliteBackend) -> str:
    pid = "P1234R0"
    backend.upsert_year("2026", [
        {"paper_id": pid, "url": "https://example.com/p1234r0.pdf"},
    ])
    return pid


def test_stage_download_raises_on_http_status_error(
    backend: SqliteBackend, staged_paper: str, monkeypatch
):
    request = httpx.Request("GET", "https://example.com/p1234r0.pdf")
    response = httpx.Response(404, request=request)

    async def boom(*args, **kwargs):
        raise httpx.HTTPStatusError("404", request=request, response=response)

    monkeypatch.setattr("mailing.download.download_paper", boom)

    with pytest.raises(RuntimeError, match="404"):
        asyncio.run(_stage_download(staged_paper, backend))

    # The stage must not have advanced or persisted anything on failure.
    assert backend.get_meta(staged_paper).source_file in (None, "")


def test_stage_download_raises_on_request_error(
    backend: SqliteBackend, staged_paper: str, monkeypatch
):
    async def boom(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("mailing.download.download_paper", boom)

    with pytest.raises(RuntimeError, match="ConnectError"):
        asyncio.run(_stage_download(staged_paper, backend))

    # The stage must not have advanced or persisted anything on failure.
    assert backend.get_meta(staged_paper).source_file in (None, "")
