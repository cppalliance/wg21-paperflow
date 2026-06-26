#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

"""Tests for ``cli.jobs.run_citations``.

Covers the regex-driven extractor's interaction with the paperstore
backend: which papers get processed, what gets stored, and the
self-citation / idempotency rules.
"""

from __future__ import annotations

import asyncio

from cli import jobs
from paperstore.testing import store  # noqa: F401  (pytest fixture)


def _seed(store, paper_id: str, markdown: str) -> None:
    """Register the paper in the mailing index and write its markdown."""
    store.upsert_year("2026", [{"paper_id": paper_id, "title": ""}])
    store.write_paper_md(paper_id, markdown)


def test_extracts_p_n_and_d_citations(store):
    pid = "P5000R0"
    _seed(store, pid, "See P1234R0 and N4567 plus D9999R2 for context.\n")

    result = asyncio.run(jobs.run_citations([pid], store))

    assert result["succeeded"] == [pid]
    cited = {r.cited_paper_id for r in store.get_paper_citations(pid)}
    assert cited == {"P1234R0", "N4567", "D9999R2"}


def test_self_citation_is_dropped(store):
    pid = "P1234R0"
    # The paper mentions its own ID twice and one foreign citation.
    _seed(store, pid, "P1234R0 supersedes P1000R0. See P1234R0.\n")

    asyncio.run(jobs.run_citations([pid], store))

    cited = {r.cited_paper_id for r in store.get_paper_citations(pid)}
    assert cited == {"P1000R0"}


def test_revision_self_reference_is_kept(store):
    """P1234R3 referring to P1234R1 is a real edge, not a self-cite."""
    pid = "P1234R3"
    _seed(store, pid, "This revises P1234R1 substantially.\n")

    asyncio.run(jobs.run_citations([pid], store))

    cited = {r.cited_paper_id for r in store.get_paper_citations(pid)}
    assert cited == {"P1234R1"}


def test_link_url_is_not_double_counted(store):
    """A markdown link with the same ID in text and URL counts once, not twice."""
    pid = "P5000R0"
    _seed(store, pid, "See [P1234R0](https://wg21.link/P1234R0) for details.\n")

    asyncio.run(jobs.run_citations([pid], store))

    rows = store.get_paper_citations(pid)
    assert len(rows) == 1
    assert rows[0].cited_paper_id == "P1234R0"
    assert rows[0].count == 1


def test_paper_id_only_in_url_is_skipped(store):
    """Bare ``[text](URL)`` with the paper-id only in the URL is intentionally
    not counted -- dissect strips link URLs before regexing."""
    pid = "P5000R0"
    _seed(store, pid, "See [the proposal](https://wg21.link/P1234R0).\n")

    asyncio.run(jobs.run_citations([pid], store))

    assert store.get_paper_citations(pid) == []


def test_idempotent_skips_papers_with_existing_rows(store):
    pid = "P5000R0"
    _seed(store, pid, "Cites P1234R0.\n")

    first = asyncio.run(jobs.run_citations([pid], store))
    assert first["succeeded"] == [pid]

    second = asyncio.run(jobs.run_citations([pid], store))
    assert second["succeeded"] == []
    assert {s["paper_id"] for s in second["skipped"]} == {pid}
    assert second["skipped"][0]["reason"] == "already_extracted"


def test_force_reextracts_even_with_existing_rows(store):
    pid = "P5000R0"
    _seed(store, pid, "Cites P1234R0.\n")

    asyncio.run(jobs.run_citations([pid], store))
    # Rewrite markdown with a different citation; force=True should pick it up.
    store.write_paper_md(pid, "Cites P9999R0.\n")

    asyncio.run(jobs.run_citations([pid], store, force=True))

    cited = {r.cited_paper_id for r in store.get_paper_citations(pid)}
    assert cited == {"P9999R0"}


def test_skips_papers_without_markdown(store):
    pid = "P5000R0"
    store.upsert_year("2026", [{"paper_id": pid, "title": ""}])  # no write_paper_md

    result = asyncio.run(jobs.run_citations([pid], store))

    assert result["succeeded"] == []
    assert {s["paper_id"] for s in result["skipped"]} == {pid}
    assert result["skipped"][0]["reason"] == "no_markdown"


def test_zero_citation_paper_is_skipped_on_second_run(store):
    """A prose-only paper (no citations) sets ``citations_extracted_at`` even
    though it stores zero rows.  The next run must skip it rather than
    re-extracting forever."""
    pid = "P5000R0"
    _seed(store, pid, "This paper contains no citations at all.\n")

    first = asyncio.run(jobs.run_citations([pid], store))
    assert first["succeeded"] == [pid]
    assert store.get_paper_citations(pid) == []

    second = asyncio.run(jobs.run_citations([pid], store))
    assert second["succeeded"] == []
    reasons = {s["paper_id"]: s["reason"] for s in second["skipped"]}
    assert reasons.get(pid) == "already_extracted"


def test_citations_not_stale_after_clear_downstream_outputs(store):
    """After ``clear_downstream_outputs`` clears the citations stamp, the next
    ``run_citations`` call re-extracts rather than skipping."""
    pid = "P5000R0"
    _seed(store, pid, "Cites P1234R0.\n")
    asyncio.run(jobs.run_citations([pid], store))
    assert {r.cited_paper_id for r in store.get_paper_citations(pid)} == {"P1234R0"}

    # Simulate a forced re-convert: rewrite markdown, invalidate downstream.
    store.write_paper_md(pid, "Now only cites P9999R0.\n")
    store.clear_downstream_outputs(pid)

    assert store.get_paper_citations(pid) == []
    assert store.get_meta(pid).citations_extracted_at == ""

    asyncio.run(jobs.run_citations([pid], store))
    assert {r.cited_paper_id for r in store.get_paper_citations(pid)} == {"P9999R0"}


def test_count_is_preserved(store):
    pid = "P5000R0"
    _seed(store, pid, "P1234R0 ... P1234R0 ... P1234R0 ... P9999R0\n")

    asyncio.run(jobs.run_citations([pid], store))

    rows = {r.cited_paper_id: r.count for r in store.get_paper_citations(pid)}
    assert rows == {"P1234R0": 3, "P9999R0": 1}
