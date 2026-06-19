#
# Copyright (c) 2026 Leo Chen (leo.chen0412@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Hermetic integration tests for ``cli.jobs.run_full``."""

from __future__ import annotations

import asyncio
from pathlib import Path

from cli import jobs
from cli.models import ConvertResult, Paper
from paperstore import SqliteBackend


def _fake_fetch(year: str) -> dict:
    return {
        f"{year}-01": [
            {
                "paper_id": "P1000R0",
                "title": "Sample",
                "url": "http://example.test/a.pdf",
            }
        ]
    }


def test_run_full_chains_stages_and_returns_citations(
    tmp_path: Path, monkeypatch,
):
    store = SqliteBackend(tmp_path)
    stages: list[str] = []

    def _on_stage_complete(stage: str, result: dict | None) -> None:
        stages.append(stage)
        assert result is not None

    monkeypatch.setattr(
        "mailing.scrape.fetch_all_mailings_for_year", _fake_fetch,
    )

    async def _download(paper_id: str, *, source_url: str, client=None, timeout: float = 30.0):
        return (b"%PDF-stub", ".pdf")

    monkeypatch.setattr("mailing.download.download_paper", _download)

    def _convert(paper: Paper, **_kwargs):
        return ConvertResult(
            paper_id=paper.document_id,
            markdown="See P2000R0 for context.\n",
            prompts=[],
            intent="",
            title=paper.title,
            images=[],
            status="ok",
        )

    monkeypatch.setattr("cli.orchestrator.convert_one_paper", _convert)

    results = asyncio.run(jobs.run_full(
        ["2026"],
        store,
        current_year="2026",
        concurrency=1,
        on_stage_complete=_on_stage_complete,
    ))

    assert stages == ["mailing", "download", "convert"]
    assert set(results) == {"mailing", "download", "convert", "citations"}
    assert results["mailing"]["succeeded"] == [{"year": "2026", "papers": 1}]
    assert results["download"]["succeeded"] == ["P1000R0"]
    assert results["convert"]["succeeded"] == ["P1000R0"]
    assert results["citations"]["succeeded"] == ["P1000R0"]

    assert store.get_source_path("P1000R0") is not None
    assert store.get_paper_md("P1000R0") == "See P2000R0 for context.\n"
    cited = {r.cited_paper_id for r in store.get_paper_citations("P1000R0")}
    assert cited == {"P2000R0"}
