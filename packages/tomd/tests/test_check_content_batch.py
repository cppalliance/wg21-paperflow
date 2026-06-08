"""Tests for content-check batch runner and report formatting."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from paperstore import SqliteBackend

from tomd.lib.check_content import (
    ContentCheckResult,
    MisalignedRegion,
    format_content_check_report,
    run_content_check_batch,
)

_BODY = (
    "Section one introduces the proposal. "
    "The motivation explains why current C++ language facilities "
    "are insufficient for the use case under consideration. "
)


def _stage(store: SqliteBackend, pid: str, body: str, md: str) -> None:
    store.upsert_year("2026", [{"paper_id": pid, "title": "Sample"}])
    html = f"<html><body>{body}</body></html>"
    store.put_source(pid, html.encode("utf-8"), suffix=".html")
    store.write_paper_md(pid, md)


def test_run_content_check_batch_on_staged_fixture(tmp_path: Path):
    store = SqliteBackend(tmp_path)
    body = _BODY * 4
    _stage(store, "P1000R0", body, body)

    batch = run_content_check_batch(
        [("P1000R0", tmp_path)],
        workers=1,
    )
    assert len(batch.results) == 1
    assert batch.results[0].paper_id == "P1000R0"
    assert batch.results[0].coverage > 0.9
    assert batch.errors == []
    assert batch.skipped == []


def test_format_content_check_report_contains_expected_sections():
    results = [
        ContentCheckResult(
            paper_id="P1",
            source_format="html",
            coverage=0.92,
            drift=0.01,
            source_token_count=100,
            markdown_token_count=98,
            missing_regions=(
                MisalignedRegion(
                    side="source",
                    token_start=0,
                    token_end=10,
                    sample="dropped text fragment",
                    page=1,
                ),
            ),
        ),
    ]
    text = format_content_check_report(results, [], [])
    assert "tomd Content-Check Report: 1 files" in text
    assert "Coverage measures the share of source-text tokens" in text
    assert "Coverage Distribution:" in text
    assert "Worst 1 files (lowest coverage):" in text
    assert "P1" in text
