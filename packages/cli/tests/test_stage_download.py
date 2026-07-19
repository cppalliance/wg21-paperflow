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
from cli.process import _stage_download, ensure_paper_md


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

    monkeypatch.setattr("cli.process.download_paper", boom)

    with pytest.raises(RuntimeError, match="404"):
        asyncio.run(_stage_download(staged_paper, backend))

    # The stage must not have advanced or persisted anything on failure.
    assert backend.get_meta(staged_paper).source_file in (None, "")


def test_stage_download_raises_on_request_error(
    backend: SqliteBackend, staged_paper: str, monkeypatch
):
    async def boom(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("cli.process.download_paper", boom)

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

    monkeypatch.setattr("cli.process.download_paper", ok)

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

    monkeypatch.setattr("cli.process.download_paper", ok)
    monkeypatch.setattr("cli.process.fetch_html_images", images)

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

    monkeypatch.setattr("cli.process.download_paper", ok)
    monkeypatch.setattr("cli.process.fetch_html_images", no_images)

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

    monkeypatch.setattr("cli.process.download_paper", ok)
    monkeypatch.setattr("cli.process.fetch_html_images", boom)

    # Firewall: the walk failure is swallowed, download stage still succeeds.
    asyncio.run(_stage_download(staged_paper, backend))

    assert manifest_path.exists()


def test_stage_download_keeps_stale_manifest_when_all_image_fetches_fail(
    backend: SqliteBackend, staged_paper: str, monkeypatch
):
    """Source still references images but every fetch failed.

    ``fetch_html_images`` swallows per-image errors and returns ``[]``
    without raising, so ``walk_ok`` stays True. The stage must NOT read
    that empty list as "the source has no images" and wipe previously
    good artifacts - only a source that genuinely references zero
    ``<img>`` tags should clear them.
    """
    backend.write_paper_image(
        staged_paper, page=0, index=1, ext="png", data=b"old",
    )
    manifest_path = backend.get_html_images_manifest_path(staged_paper)
    manifest_path.write_text('{"pid": "P1234R0", "entries": []}', encoding="utf-8")
    stale_image = backend.get_paper_image_path(
        staged_paper, page=0, index=1, ext="png",
    )
    assert stale_image.exists()

    # Re-downloaded HTML still references an image (<img src>), but the
    # walk recovers nothing because every per-image fetch failed.
    async def ok(*args, **kwargs):
        return (b"<html><img src='x.png'></html>", ".html")

    async def no_images(*args, **kwargs):
        return []

    monkeypatch.setattr("cli.process.download_paper", ok)
    monkeypatch.setattr("cli.process.fetch_html_images", no_images)

    asyncio.run(_stage_download(staged_paper, backend))

    assert manifest_path.exists()
    assert stale_image.exists()


def test_process_paper_marks_failed_when_download_raises(
    backend: SqliteBackend, staged_paper: str, monkeypatch
):
    """The reworked error path relies on ``process_paper``'s outer handler.

    ``_stage_download`` raises on transport failure; ``process_paper``
    must catch it, call ``fail_paper`` (negative status + stored error),
    and re-raise. This guards the wiring that the isolated stage tests
    cannot: they would stay green even if the outer handler were removed.
    """
    from paperstore.stages import STAGES

    from cli.process import process_paper

    async def boom(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("cli.process.download_paper", boom)

    with pytest.raises(RuntimeError, match="ConnectError"):
        asyncio.run(
            process_paper(
                staged_paper, backend, through=STAGES["download"] + 1,
            )
        )

    meta = backend.get_meta(staged_paper)
    assert meta.status == -(STAGES["download"] + 1)
    assert "ConnectError" in (meta.error or "")


def test_ensure_paper_md_persists_failure_on_download_error(
    backend: SqliteBackend, staged_paper: str, monkeypatch
):
    """The citation shortcut must record a download failure on the paper row.

    ``_stage_download`` now raises instead of calling ``fail_paper`` itself.
    ``ensure_paper_md`` has no outer ``process_paper`` handler, so it must
    persist the failure on the way out rather than swallowing it silently.
    """
    from paperstore.stages import STAGES

    async def boom(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("cli.process.download_paper", boom)

    result = asyncio.run(ensure_paper_md(staged_paper, backend))

    assert result is None
    meta = backend.get_meta(staged_paper)
    assert meta.status == -(STAGES["download"] + 1)
    assert "ConnectError" in (meta.error or "")


def test_ensure_paper_md_persists_failure_at_convert_stage(
    backend: SqliteBackend, staged_paper: str, monkeypatch
):
    """A convert-stage failure after a successful download must be recorded
    at the convert stage (status -2), not the download stage.

    Guards ``ensure_paper_md``'s stage tracking: the failure is attributed
    to whichever stage actually raised.
    """
    from paperstore.stages import STAGES

    async def ok(*args, **kwargs):
        return (b"%PDF-1.7 fake", ".pdf")

    async def boom_convert(*args, **kwargs):
        raise RuntimeError("convert exploded")

    monkeypatch.setattr("cli.process.download_paper", ok)
    monkeypatch.setattr("cli.process._stage_convert", boom_convert)

    result = asyncio.run(ensure_paper_md(staged_paper, backend))

    assert result is None
    meta = backend.get_meta(staged_paper)
    assert meta.status == -(STAGES["convert"] + 1)
    assert "convert exploded" in (meta.error or "")
