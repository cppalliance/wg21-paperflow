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

The success-path tests guard the restored persistence code (source +
HTML image/manifest writes) and the stale-artifact cleanup that runs
when a re-downloaded HTML source no longer has images.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from mailing.html_images import HtmlFetchedImage
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


def test_stage_download_persists_source_on_success(
    backend: SqliteBackend, staged_paper: str, monkeypatch
):
    """A successful non-HTML download writes the source file (the path
    that was dead code before the persistence fix)."""
    async def ok(*args, **kwargs):
        return (b"%PDF-1.7 fake", ".pdf")

    monkeypatch.setattr("mailing.download.download_paper", ok)

    asyncio.run(_stage_download(staged_paper, backend))

    source_file = backend.get_meta(staged_paper).source_file
    assert source_file
    assert Path(source_file).exists()


def test_stage_download_persists_html_images_and_manifest(
    backend: SqliteBackend, staged_paper: str, monkeypatch
):
    """A successful HTML download persists fetched images and writes the
    convert-time handoff manifest."""
    async def ok(*args, **kwargs):
        return (b"<html><img src='x.png'></html>", ".html")

    async def images(*args, **kwargs):
        return [
            HtmlFetchedImage(
                original_src="https://example.com/x.png",
                ext="png",
                bytes=b"\x89PNG fake",
                document_order=1,
                caption_text="",
                alt_attr="",
            )
        ]

    monkeypatch.setattr("mailing.download.download_paper", ok)
    monkeypatch.setattr("mailing.fetch_html_images", images)

    asyncio.run(_stage_download(staged_paper, backend))

    manifest_path = backend.get_html_images_manifest_path(staged_paper)
    assert manifest_path.exists()
    image_path = backend.get_paper_image_path(
        staged_paper, page=0, index=1, ext="png",
    )
    assert image_path.exists()


def test_stage_download_clears_stale_manifest_when_no_images(
    backend: SqliteBackend, staged_paper: str, monkeypatch
):
    """Re-downloading an HTML source that no longer has images drops the
    stale manifest + orphan image files so convert can't pair fresh
    source with old figures."""
    # Seed a prior image + manifest as if a previous run had figures.
    backend.write_paper_image(
        staged_paper, page=0, index=1, ext="png", data=b"old",
    )
    manifest_path = backend.get_html_images_manifest_path(staged_paper)
    manifest_path.write_text('{"pid": "P1234R0", "entries": []}', encoding="utf-8")
    stale_image = backend.get_paper_image_path(
        staged_paper, page=0, index=1, ext="png",
    )
    assert stale_image.exists()

    async def ok(*args, **kwargs):
        return (b"<html>no images here</html>", ".html")

    async def no_images(*args, **kwargs):
        return []

    monkeypatch.setattr("mailing.download.download_paper", ok)
    monkeypatch.setattr("mailing.fetch_html_images", no_images)

    asyncio.run(_stage_download(staged_paper, backend))

    assert not manifest_path.exists()
    assert not stale_image.exists()


def test_stage_download_keeps_stale_manifest_on_walk_failure(
    backend: SqliteBackend, staged_paper: str, monkeypatch
):
    """A transient image-walk failure must NOT destroy previously good
    artifacts; the per-paper firewall keeps them and lets convert warn."""
    manifest_path = backend.get_html_images_manifest_path(staged_paper)
    manifest_path.write_text('{"pid": "P1234R0", "entries": []}', encoding="utf-8")

    async def ok(*args, **kwargs):
        return (b"<html><img src='x.png'></html>", ".html")

    async def boom(*args, **kwargs):
        raise RuntimeError("transient network blip")

    monkeypatch.setattr("mailing.download.download_paper", ok)
    monkeypatch.setattr("mailing.fetch_html_images", boom)

    # Firewall: the walk failure is swallowed, download stage still succeeds.
    asyncio.run(_stage_download(staged_paper, backend))

    assert manifest_path.exists()
