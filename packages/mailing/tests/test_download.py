#
# Copyright (c) 2026 Greg Kaleka (greg@gregkaleka.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Tests for ``mailing.download.download_paper``.

``httpx.Client`` is monkeypatched so tests run hermetically.
download_paper now takes workspace_dir (Path) instead of a StorageBackend.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mailing import download as md


class _FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def _make_mock_client(content: bytes) -> MagicMock:
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = _FakeResponse(content)
    return mock_client


def test_download_paper_writes_pdf_to_workspace(tmp_path: Path):
    pdf_bytes = b"%PDF-1.7\nhello"

    with patch("mailing.download.httpx.Client", return_value=_make_mock_client(pdf_bytes)):
        path = md.download_paper(
            "p1234r0",
            tmp_path,
            source_url="https://www.open-std.org/.../p1234r0.pdf",
        )
    assert path == tmp_path / "p1234r0.pdf"
    assert path.read_bytes() == pdf_bytes


def test_download_paper_normalizes_htm_to_html(tmp_path: Path):
    html_bytes = b"<html>ok</html>"

    with patch("mailing.download.httpx.Client", return_value=_make_mock_client(html_bytes)):
        path = md.download_paper(
            "n5000",
            tmp_path,
            source_url="https://www.open-std.org/.../n5000.htm",
        )
    assert path == tmp_path / "n5000.html"


def test_download_paper_returns_none_for_empty_url(tmp_path: Path):
    result = md.download_paper("p1", tmp_path, source_url="")
    assert result is None


def test_download_paper_rejects_unknown_suffix(tmp_path: Path):
    with pytest.raises(ValueError, match="must end with"):
        md.download_paper("p1", tmp_path, source_url="https://x/paper.docx")


def test_download_paper_retries_replace_on_permission_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    pdf_bytes = b"%PDF-1.7\nretry"
    real_replace = os.replace
    calls = {"n": 0}

    def flaky_replace(src, dst):
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError("Windows says no")
        real_replace(src, dst)

    monkeypatch.setattr(md.os, "replace", flaky_replace)
    monkeypatch.setattr(md.time, "sleep", lambda _s: None)

    with patch("mailing.download.httpx.Client", return_value=_make_mock_client(pdf_bytes)):
        path = md.download_paper(
            "p9999r0",
            tmp_path,
            source_url="https://www.open-std.org/.../p9999r0.pdf",
        )

    assert calls["n"] == 3
    assert path == tmp_path / "p9999r0.pdf"
    assert path.read_bytes() == pdf_bytes


def test_download_paper_raises_after_retries_exhausted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    pdf_bytes = b"%PDF-1.7\nblocked"
    calls = {"n": 0}

    def always_blocked(src, dst):
        calls["n"] += 1
        raise PermissionError("Windows says no")

    monkeypatch.setattr(md.os, "replace", always_blocked)
    monkeypatch.setattr(md.time, "sleep", lambda _s: None)

    with patch("mailing.download.httpx.Client", return_value=_make_mock_client(pdf_bytes)):
        with pytest.raises(PermissionError):
            md.download_paper(
                "p9998r0",
                tmp_path,
                source_url="https://www.open-std.org/.../p9998r0.pdf",
            )

    assert calls["n"] == 10
    assert not (tmp_path / "p9998r0.tmp.pdf").exists()
