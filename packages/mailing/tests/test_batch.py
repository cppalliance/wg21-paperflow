#
# Copyright (c) 2026 Greg Kaleka (greg@gregkaleka.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Tests for ``mailing.batch.stage_mailing``: idempotent corpus staging."""

from __future__ import annotations

from mailing.batch import stage_mailing
from paperstore.testing import store  # noqa: F401  (pytest fixture)


def _rows(*paper_ids: str) -> list[dict]:
    return [
        {
            "paper_id": pid,
            "url": f"https://www.open-std.org/.../{pid.lower()}.pdf",
            "filename": f"{pid.lower()}.pdf",
            "title": f"Paper {pid}",
            "authors": [],
            "subgroup": "EWG",
        }
        for pid in paper_ids
    ]


def _fake_download(download_calls: list[str]):
    """Return a fake download function that records calls and yields stub bytes."""
    def _download(pid: str, *, source_url: str) -> tuple[bytes, str]:
        download_calls.append(pid)
        return b"%PDF-1.7\n", ".pdf"
    return _download


def test_stage_mailing_first_run_downloads_all(store):
    rows = _rows("P1000R0", "P1001R0")
    download_calls: list[str] = []

    counts = stage_mailing(
        "2026-01",
        store,
        fetch_papers=lambda mid: rows,
        download=_fake_download(download_calls),
    )

    assert counts == {
        "papers_in_index": 2,
        "downloaded": 2,
        "skipped": 0,
        "no_url": 0,
        "filtered_out": 0,
    }
    assert sorted(download_calls) == ["P1000R0", "P1001R0"]


def test_stage_mailing_second_run_is_a_noop(store):
    rows = _rows("P1000R0", "P1001R0")
    download_calls: list[str] = []
    fake = _fake_download(download_calls)

    stage_mailing("2026-01", store, fetch_papers=lambda mid: rows, download=fake)
    assert len(download_calls) == 2

    counts = stage_mailing("2026-01", store, fetch_papers=lambda mid: rows, download=fake)

    assert counts["downloaded"] == 0
    assert counts["skipped"] == 2
    assert len(download_calls) == 2  # no extra calls


def test_stage_mailing_picks_up_new_papers_only(store):
    download_calls: list[str] = []
    fake = _fake_download(download_calls)

    stage_mailing(
        "2026-01", store,
        fetch_papers=lambda mid: _rows("P1000R0"),
        download=fake,
    )
    assert download_calls == ["P1000R0"]

    counts = stage_mailing(
        "2026-01", store,
        fetch_papers=lambda mid: _rows("P1000R0", "P1001R0"),
        download=fake,
    )

    assert counts["downloaded"] == 1
    assert counts["skipped"] == 1
    assert download_calls == ["P1000R0", "P1001R0"]


def test_stage_mailing_refetch_redownloads_all(store):
    rows = _rows("P1000R0", "P1001R0")
    download_calls: list[str] = []
    fake = _fake_download(download_calls)

    stage_mailing("2026-01", store, fetch_papers=lambda mid: rows, download=fake)
    counts = stage_mailing("2026-01", store, refetch=True, fetch_papers=lambda mid: rows, download=fake)

    assert counts["downloaded"] == 2
    assert counts["skipped"] == 0
    assert len(download_calls) == 4  # two per run


def test_stage_mailing_filter_subset(store):
    rows = _rows("P1000R0", "P1001R0", "P1002R0")
    download_calls: list[str] = []

    counts = stage_mailing(
        "2026-01", store,
        papers={"P1001R0"},
        fetch_papers=lambda mid: rows,
        download=_fake_download(download_calls),
    )

    assert counts["downloaded"] == 1
    assert counts["filtered_out"] == 2
    assert download_calls == ["P1001R0"]


def test_stage_mailing_no_papers_in_mailing(store):
    counts = stage_mailing(
        "2026-01", store,
        fetch_papers=lambda mid: [],
        download=lambda pid, *, source_url: (b"", ".pdf"),
    )
    assert counts == {
        "papers_in_index": 0,
        "downloaded": 0,
        "skipped": 0,
        "no_url": 0,
        "filtered_out": 0,
    }


def test_stage_mailing_row_without_url(store):
    rows = [
        {
            "paper_id": "P1000R0",
            "url": "",
            "filename": "p1000r0.pdf",
            "title": "no url",
            "authors": [],
            "subgroup": "EWG",
        }
    ]
    download_calls: list[str] = []

    counts = stage_mailing(
        "2026-01", store,
        fetch_papers=lambda mid: rows,
        download=_fake_download(download_calls),
    )

    assert counts["no_url"] == 1
    assert counts["downloaded"] == 0
    assert download_calls == []
