#
# Copyright (c) 2026 Dmitriy Chukhin (dmitriy@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Unit tests for cli.jobs.run_content_check return contract."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from cli.jobs import run_content_check
from paperstore.testing import store  # noqa: F401  (pytest fixture)
from tomd.lib.check_content import ContentCheckBatchResult, ContentCheckResult


_BODY = (
    "Section one introduces the proposal. "
    "The motivation explains why current C++ language facilities "
    "are insufficient for the use case under consideration. "
)


def _stage(store, pid: str, body: str, md: str) -> None:
    store.upsert_year("2026", [{"paper_id": pid, "title": "Sample"}])
    html = f"<html><body>{body}</body></html>"
    store.put_source(pid, html.encode("utf-8"), suffix=".html")
    store.write_paper_md(pid, md)


def test_run_content_check_surfaces_batch_failures(store, tmp_path: Path):
    body = _BODY * 4
    _stage(store, "P1000R0", body, body)
    _stage(store, "P1001R0", body, body)

    ok_result = ContentCheckResult(
        paper_id="P1000R0",
        source_format="html",
        coverage=0.95,
        drift=0.01,
        source_token_count=100,
        markdown_token_count=98,
        missing_regions=(),
        extra_regions=(),
    )
    fake_batch = ContentCheckBatchResult(
        results=[ok_result],
        skipped=[],
        errors=[("P1001R0", "check failed")],
        timed_out=[],
        elapsed_sec=1.0,
    )

    with patch("cli.jobs.run_content_check_batch", return_value=fake_batch):
        result = run_content_check(["2026"], store)

    assert result["succeeded"] == ["P1000R0"]
    assert result["failed"] == [
        {"paper_id": "P1001R0", "reason": "check failed"},
    ]


def test_run_content_check_no_duplicate_timeout_failures(store, tmp_path: Path):
    body = _BODY * 4
    _stage(store, "P1000R0", body, body)
    _stage(store, "P1001R0", body, body)

    ok_result = ContentCheckResult(
        paper_id="P1000R0",
        source_format="html",
        coverage=0.95,
        drift=0.01,
        source_token_count=100,
        markdown_token_count=98,
        missing_regions=(),
        extra_regions=(),
    )
    timeout_msg = "timeout (no progress for 120s)"
    fake_batch = ContentCheckBatchResult(
        results=[ok_result],
        skipped=[],
        errors=[("P1001R0", timeout_msg)],
        timed_out=["P1001R0"],
        elapsed_sec=1.0,
    )

    with patch("cli.jobs.run_content_check_batch", return_value=fake_batch):
        result = run_content_check(["2026"], store)

    assert len(result["failed"]) == 1
    assert result["failed"] == [
        {"paper_id": "P1001R0", "reason": timeout_msg},
    ]
    assert result["succeeded"] == ["P1000R0"]
