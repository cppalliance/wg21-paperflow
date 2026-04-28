#
# Copyright (c) 2026 Greg Kaleka (greg@gregkaleka.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Download staged paper sources into a paperstore-backed workspace."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT_SEC = 120
_USER_AGENT = "paperflow/0.1 (+https://github.com/cppalliance/paperlint)"
_ALLOWED_SUFFIXES = (".pdf", ".html", ".htm")


def _suffix_from_url(source_url: str) -> str:
    name = Path(urlparse(source_url).path).name.lower()
    suffix = Path(name).suffix
    if suffix not in _ALLOWED_SUFFIXES:
        raise ValueError(
            f"source_url must end with one of {_ALLOWED_SUFFIXES}: {source_url!r}"
        )
    # Normalize .htm to .html so get_source_path finds exactly one entry.
    return ".html" if suffix == ".htm" else suffix


def content_length(url: str, *, timeout: float = 30.0) -> int | None:
    """Send a HEAD request and return Content-Length as int, or None if absent.

    Uses ``Accept-Encoding: identity`` to get the uncompressed size.
    Returns ``None`` if the header is missing or the request fails.
    """
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.head(
                url,
                headers={
                    "User-Agent": _USER_AGENT,
                    "Accept-Encoding": "identity",
                },
            )
            resp.raise_for_status()
        cl = resp.headers.get("content-length")
        return int(cl) if cl is not None else None
    except Exception:
        logger.debug("HEAD request failed for %s", url, exc_info=True)
        return None


def download_paper(
    paper_id: str,
    workspace_dir: Path,
    *,
    source_url: str,
    timeout: float = _FETCH_TIMEOUT_SEC,
    refetch: bool = False,
) -> Path | None:
    """Download a paper's source file to ``workspace_dir``.

    Writes via a ``<pid>.tmp.<suffix>`` temp file then ``os.replace`` to the
    final path. ``os.replace`` is atomic on POSIX; on Windows the rename can
    transiently raise ``PermissionError`` if the destination is held open by
    another process, so we retry up to ten times at 100 ms intervals before
    re-raising. Does NOT touch the database - the caller is responsible for
    persisting the returned path to storage.

    Returns the local path on success, or ``None`` if ``source_url`` is empty.
    """
    if not source_url:
        logger.warning("No source URL for %s - skipping download", paper_id)
        return None

    suffix = _suffix_from_url(source_url)
    pid_lower = paper_id.strip().upper().lower()
    final_path = Path(workspace_dir) / f"{pid_lower}{suffix}"
    temp_path = final_path.with_stem(final_path.stem + ".tmp")

    logger.info("Downloading %s from %s", paper_id, source_url)

    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        resp = client.get(source_url)
        resp.raise_for_status()

    if temp_path.exists():
        temp_path.unlink()

    try:
        temp_path.write_bytes(resp.content)
        for attempt in range(10):
            try:
                os.replace(temp_path, final_path)
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.1)
    except BaseException:
        if temp_path.exists():
            temp_path.unlink()
        raise

    logger.info("Staged %s at %s", paper_id, final_path)
    return final_path
