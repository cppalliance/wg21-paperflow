#
# Copyright (c) 2026 Greg Kaleka (greg@gregkaleka.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

"""Tests for SqliteBackend."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from paperstore import SqliteBackend
from paperstore.errors import (
    MissingEvaluationError,
    MissingMailingIndexError,
    MissingMetaError,
    MissingPaperMdError,
    MissingSourceError,
)


@pytest.fixture
def store(tmp_path: Path) -> SqliteBackend:
    return SqliteBackend(tmp_path)


def test_put_source_and_get_source_path(store: SqliteBackend, tmp_path: Path):
    path = store.put_source("P1234R0", b"%PDF-1.7\n", suffix=".pdf")
    assert path == tmp_path / "p1234r0.pdf"
    assert path.read_bytes() == b"%PDF-1.7\n"
    assert store.get_source_path("p1234r0") == path


def test_put_source_updates_source_file_in_db(store: SqliteBackend):
    path = store.put_source("P1", b"x", suffix=".pdf")
    meta = store.get_meta("P1")
    assert meta["source_file"] == str(path)


def test_put_source_overwrites_existing(store: SqliteBackend):
    store.put_source("P1", b"v1", suffix=".pdf")
    store.put_source("P1", b"v2", suffix=".pdf")
    assert store.get_source_path("P1").read_bytes() == b"v2"


def test_get_source_path_missing_raises(store: SqliteBackend):
    with pytest.raises(MissingSourceError):
        store.get_source_path("NOPE")


def test_write_and_get_paper_md(store: SqliteBackend, tmp_path: Path):
    path = store.write_paper_md("P1", "# Hi\n")
    assert path == tmp_path / "p1.md"
    assert store.get_paper_md("P1") == "# Hi\n"


def test_get_paper_md_missing_raises(store: SqliteBackend):
    with pytest.raises(MissingPaperMdError):
        store.get_paper_md("NOPE")


def test_write_paper_md_updates_markdown_path(store: SqliteBackend):
    path = store.write_paper_md("P1", "content")
    meta = store.get_meta("P1")
    assert meta["markdown_path"] == str(path)


def test_write_and_get_evaluation(store: SqliteBackend, tmp_path: Path):
    store.upsert_year("2026", [{"paper_id": "P1"}])
    path = store.write_evaluation_json("P1", {"summary": "ok", "pipeline_status": "complete"})
    assert path == tmp_path / "p1.eval.json"
    result = store.get_evaluation("P1")
    assert result["summary"] == "ok"


def test_get_evaluation_missing_raises(store: SqliteBackend):
    with pytest.raises(MissingEvaluationError):
        store.get_evaluation("NOPE")


def test_write_intermediate(store: SqliteBackend, tmp_path: Path):
    store.write_intermediate("P1", "1-findings", [{"n": 1}])
    path = tmp_path / "p1.1-findings.json"
    assert path.exists()
    assert json.loads(path.read_text())  == [{"n": 1}]


def test_upsert_year_and_list_papers(store: SqliteBackend):
    papers = [
        {"paper_id": "P1", "title": "One"},
        {"paper_id": "P2", "title": "Two"},
    ]
    store.upsert_year("2026", papers)
    rows = store.list_papers_for_year("2026")
    ids = {r["paper_id"] for r in rows}
    assert ids == {"P1", "P2"}


def test_upsert_year_preserves_source_file(store: SqliteBackend):
    """Re-upsert must not clobber source_file set by download."""
    store.upsert_year("2026", [{"paper_id": "P1", "title": "T"}])
    source_path = store.put_source("P1", b"bytes", suffix=".pdf")
    store.upsert_year("2026", [{"paper_id": "P1", "title": "Updated"}])
    meta = store.get_meta("P1")
    assert meta["source_file"] == str(source_path)


def test_write_meta_json_preserves_source_and_markdown(store: SqliteBackend):
    """write_meta_json must not clobber source_file/markdown_path on omission."""
    source_path = store.put_source("P1", b"bytes", suffix=".pdf")
    md_path = store.write_paper_md("P1", "# body\n")
    store.write_meta_json("P1", {"title": "T", "year": "2026"})
    meta = store.get_meta("P1")
    assert meta["title"] == "T"
    assert meta["source_file"] == str(source_path)
    assert meta["markdown_path"] == str(md_path)


def test_write_meta_json_can_set_source_file_when_provided(store: SqliteBackend):
    """write_meta_json still writes columns the caller explicitly supplies."""
    store.write_meta_json("P1", {"title": "T", "source_file": "/tmp/explicit.pdf"})
    meta = store.get_meta("P1")
    assert meta["source_file"] == "/tmp/explicit.pdf"


def test_close_is_idempotent(tmp_path: Path):
    backend = SqliteBackend(tmp_path)
    backend.close()
    backend.close()


def test_context_manager_closes_connection(tmp_path: Path):
    with SqliteBackend(tmp_path) as backend:
        backend.upsert_year("2026", [{"paper_id": "P1"}])
    # Subsequent queries should fail because the connection is closed.
    with pytest.raises(Exception):
        backend.list_all_paper_ids()


def test_put_source_rejects_suffix_without_dot(store: SqliteBackend):
    with pytest.raises(ValueError, match="must start with '.'"):
        store.put_source("P1", b"x", suffix="pdf")


def test_list_papers_for_year_missing_raises(store: SqliteBackend):
    with pytest.raises(MissingMailingIndexError):
        store.list_papers_for_year("9999")


def test_has_year(store: SqliteBackend):
    assert not store.has_year("2026")
    store.upsert_year("2026", [{"paper_id": "P1"}])
    assert store.has_year("2026")


def test_list_all_paper_ids(store: SqliteBackend):
    store.upsert_year("2026", [{"paper_id": "P1"}, {"paper_id": "P2"}])
    ids = store.list_all_paper_ids()
    assert set(ids) == {"P1", "P2"}


def test_resolve_year_for_paper_hit(store: SqliteBackend):
    store.upsert_year("2026", [{"paper_id": "P1", "url": "https://example.com/p1.pdf"}])
    result = store.resolve_year_for_paper("P1")
    assert result is not None
    year, row = result
    assert year == "2026"
    assert row["url"] == "https://example.com/p1.pdf"


def test_resolve_year_for_paper_miss(store: SqliteBackend):
    assert store.resolve_year_for_paper("NOPE") is None


def test_resolve_year_for_paper_case_insensitive(store: SqliteBackend):
    store.upsert_year("2026", [{"paper_id": "P3000R5"}])
    assert store.resolve_year_for_paper("p3000r5") is not None
    assert store.resolve_year_for_paper("P3000R5") is not None


def test_get_meta_missing_raises(store: SqliteBackend):
    with pytest.raises(MissingMetaError):
        store.get_meta("NOPE")


def test_write_meta_json_upserts(store: SqliteBackend):
    store.write_meta_json("P1", {"title": "Hello", "year": "2026"})
    meta = store.get_meta("P1")
    assert meta["title"] == "Hello"
    assert meta["year"] == "2026"


def test_authors_roundtrip_as_list(store: SqliteBackend):
    store.upsert_year("2026", [{"paper_id": "P1", "authors": ["Alice", "Bob"]}])
    meta = store.get_meta("P1")
    assert meta["authors"] == ["Alice", "Bob"]


def test_list_years(store: SqliteBackend):
    store.upsert_year("2025", [{"paper_id": "P1"}])
    store.upsert_year("2026", [{"paper_id": "P2"}, {"paper_id": "P3"}])
    years = store.list_years()
    assert ("2025", 1) in years
    assert ("2026", 2) in years
