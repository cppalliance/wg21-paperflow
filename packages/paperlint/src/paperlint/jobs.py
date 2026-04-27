#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Batch job library for the paperflow pipeline.

Each ``run_*`` function is ``async def`` and returns a result dict with
``succeeded``, ``failed``, and ``skipped`` lists. Workers are coroutines
(or ``asyncio.to_thread`` wrappers for CPU-bound work) that return plain
result dicts - they never touch the storage backend. The main coroutine
receives each result via ``asyncio.as_completed`` and writes to the
backend serially, avoiding any SQLite concurrency issues.

Command modules call ``asyncio.run(jobs.run_*(...))``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from paperstore.backend import StorageBackend
from paperstore.errors import MissingMailingIndexError, MissingSourceError

logger = logging.getLogger(__name__)

MAILING_EARLIEST_YEAR = 2011


# ---------------------------------------------------------------------------
# Target resolution helpers
# ---------------------------------------------------------------------------

def _validate_targets(targets: list[str]) -> str:
    """Return the target type: 'all', 'years', or 'papers'.

    Raises ValueError if targets are empty, mix years and paper IDs, or
    contain an unrecognized format.
    """
    if not targets:
        raise ValueError("At least one target is required.")
    if targets == ["all"]:
        return "all"
    # Check all are years (4 digits) or all are paper IDs.
    are_years = [t.isdigit() and len(t) == 4 for t in targets]
    if all(are_years):
        return "years"
    if not any(are_years):
        return "papers"
    raise ValueError(
        "Cannot mix years and paper IDs in one command. "
        f"Got: {targets!r}"
    )


def _papers_from_scope(
    targets: list[str], target_type: str, backend: StorageBackend
) -> list[dict]:
    """Return paper rows matching the scope, without idempotency filtering."""
    if target_type == "all":
        ids = backend.list_all_paper_ids()
        rows = []
        for pid in ids:
            result = backend.resolve_year_for_paper(pid)
            if result:
                _, row = result
                rows.append(row)
        return rows
    if target_type == "years":
        rows = []
        for year in targets:
            try:
                rows.extend(backend.list_papers_for_year(year))
            except MissingMailingIndexError:
                logger.warning("No papers found for year %s; run 'paperflow mailing %s' first.", year, year)
        return rows
    # paper IDs
    rows = []
    for pid in targets:
        result = backend.resolve_year_for_paper(pid.upper())
        if result is None:
            logger.warning("Paper %s not found in database.", pid)
        else:
            _, row = result
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# run_mailing
# ---------------------------------------------------------------------------

async def run_mailing(
    targets: list[str],
    backend: StorageBackend,
    *,
    current_year: str | None = None,
) -> dict:
    """Scrape mailing indexes from open-std.org and store in the backend.

    ``targets`` is a list of year strings, or ``["all"]``. Past years
    where ``backend.has_year(year)`` is True are skipped; the current year
    is always re-fetched.
    """
    from mailing.scrape import discover_years, fetch_all_mailings_for_year

    if current_year is None:
        current_year = str(datetime.now(timezone.utc).year)

    target_type = _validate_targets(targets)

    if target_type == "all":
        all_years = discover_years()
        years = [y for y in all_years if int(y) >= MAILING_EARLIEST_YEAR]
    else:
        years = targets

    succeeded = []
    skipped = []
    failed = []

    for year in years:
        # Skip past years already in DB; always refresh current year.
        if year < current_year and backend.has_year(year):
            skipped.append(year)
            continue
        try:
            all_mailings = fetch_all_mailings_for_year(year)
            for mailing_id, papers in sorted(all_mailings.items()):
                backend.upsert_year(year, papers)
            total = len(backend.list_papers_for_year(year))
            succeeded.append({"year": year, "papers": total})
        except Exception as exc:
            logger.exception("Failed to fetch year %s", year)
            failed.append({"year": year, "error": str(exc)})

    return {"succeeded": succeeded, "skipped": skipped, "failed": failed}


# ---------------------------------------------------------------------------
# run_download
# ---------------------------------------------------------------------------

async def run_download(
    targets: list[str],
    backend: StorageBackend,
    *,
    refetch: bool = False,
    verify: bool = False,
    concurrency: int = 10,
    on_total: Callable[[int], None] | None = None,
    on_progress: Callable[[dict], None] | None = None,
) -> dict:
    """Download source files for papers. Workers are async httpx calls.

    ``on_total`` is invoked once with the count of papers that will be
    attempted (after idempotency filtering). ``on_progress`` is invoked
    once per task completion with the worker's result dict.
    """
    from mailing.download import content_length, download_paper

    target_type = _validate_targets(targets)
    all_papers = _papers_from_scope(targets, target_type, backend)

    # Apply idempotency filter via SQL-equivalent: exclude already-downloaded.
    if not refetch:
        to_process = [p for p in all_papers if not p.get("source_file")]
    else:
        to_process = [p for p in all_papers if p.get("url")]

    if on_total is not None:
        try:
            on_total(len(to_process))
        except Exception:
            logger.warning("on_total progress hook raised; continuing", exc_info=True)

    semaphore = asyncio.Semaphore(concurrency)

    workspace_dir = backend.workspace_dir

    async def _one(paper: dict) -> dict:
        pid = paper["paper_id"]
        url = paper.get("url", "")
        if not url:
            return {"paper_id": pid, "status": "skipped", "reason": "no_url"}
        async with semaphore:
            if verify and paper.get("source_file"):
                cl = content_length(url)
                if cl is not None:
                    existing = Path(paper["source_file"])
                    if existing.exists() and existing.stat().st_size == cl:
                        return {"paper_id": pid, "status": "skipped", "reason": "verified_match"}
            try:
                # Pass workspace_dir (not backend) - worker must not touch SQLite
                path = await asyncio.to_thread(
                    download_paper, pid, workspace_dir, source_url=url, refetch=refetch
                )
                if path is None:
                    return {"paper_id": pid, "status": "skipped", "reason": "no_url"}
                return {"paper_id": pid, "source_file": str(path), "status": "ok"}
            except Exception as exc:
                logger.exception("Download failed for %s", pid)
                return {"paper_id": pid, "status": "error", "error": str(exc)}

    tasks = [asyncio.create_task(_one(p)) for p in to_process]
    succeeded = []
    failed = []
    skipped_papers = [{"paper_id": p["paper_id"], "reason": "already_staged"}
                      for p in all_papers if p not in to_process]

    for coro in asyncio.as_completed(tasks):
        result = await coro
        if result["status"] == "ok":
            backend._patch_fields(result["paper_id"], {"source_file": result["source_file"]})
            succeeded.append(result["paper_id"])
        elif result["status"] == "skipped":
            skipped_papers.append(result)
        else:
            failed.append(result)
        if on_progress is not None:
            try:
                on_progress(result)
            except Exception:
                logger.warning("on_progress progress hook raised; disabling for remainder of run", exc_info=True)
                on_progress = None

    return {"succeeded": succeeded, "skipped": skipped_papers, "failed": failed}


# ---------------------------------------------------------------------------
# run_convert
# ---------------------------------------------------------------------------

async def run_convert(
    targets: list[str],
    backend: StorageBackend,
    *,
    refetch: bool = False,
    concurrency: int = 4,
) -> dict:
    """Convert staged source files to markdown. Workers run in threads."""
    from paperlint.orchestrator import convert_one_paper
    from paperlint.models import Paper

    target_type = _validate_targets(targets)
    all_papers = _papers_from_scope(targets, target_type, backend)

    if not refetch:
        to_process = [p for p in all_papers
                      if p.get("source_file") and not p.get("markdown_path")]
    else:
        to_process = [p for p in all_papers if p.get("source_file")]

    semaphore = asyncio.Semaphore(concurrency)

    def _make_paper(row: dict) -> Paper:
        authors = row.get("authors") or []
        if isinstance(authors, str):
            try:
                authors = json.loads(authors)
            except (json.JSONDecodeError, ValueError):
                authors = [a.strip() for a in authors.split(",") if a.strip()]
        return Paper(
            document_id=row["paper_id"],
            year=row.get("year", ""),
            title=row.get("title", ""),
            authors=authors,
            mailing_date=row.get("mailing_date", ""),
            document_date=row.get("document_date", ""),
            audience=row.get("target_group", ""),
            intent=row.get("intent", ""),
            url=row.get("url", ""),
            source_file=row.get("source_file", ""),
            markdown_path=row.get("markdown_path", ""),
        )

    async def _one(paper_row: dict) -> dict:
        pid = paper_row["paper_id"]
        async with semaphore:
            try:
                paper = _make_paper(paper_row)
                # No backend passed - convert_one_paper does no SQLite access
                result = await asyncio.to_thread(convert_one_paper, paper)
                return {
                    "paper_id": pid,
                    "markdown_path": result.markdown_path,
                    "intent": result.intent,
                    "title": result.title,
                    "status": "ok",
                }
            except RuntimeError as exc:
                msg = str(exc)
                if "empty markdown" in msg:
                    logger.warning("Skipping %s: %s", pid, msg)
                    return {"paper_id": pid, "status": "skipped", "reason": "unreadable_source"}
                logger.exception("Convert failed for %s", pid)
                return {"paper_id": pid, "status": "error", "error": msg}
            except Exception as exc:
                logger.exception("Convert failed for %s", pid)
                return {"paper_id": pid, "status": "error", "error": str(exc)}

    tasks = [asyncio.create_task(_one(p)) for p in to_process]
    succeeded = []
    failed = []
    skipped = [p["paper_id"] for p in all_papers if p not in to_process]

    for coro in asyncio.as_completed(tasks):
        result = await coro
        if result["status"] == "ok":
            backend._patch_fields(result["paper_id"], {
                "markdown_path": result["markdown_path"],
                "intent": result["intent"],
            })
            succeeded.append(result["paper_id"])
        elif result["status"] == "skipped":
            skipped.append(result)
        else:
            failed.append(result)

    return {"succeeded": succeeded, "skipped": skipped, "failed": failed}


# ---------------------------------------------------------------------------
# run_eval
# ---------------------------------------------------------------------------

async def run_eval(
    targets: list[str],
    backend: StorageBackend,
    *,
    refetch: bool = False,
    concurrency: int = 5,
    discovery_passes: int = 3,
) -> dict:
    """Run the LLM eval pipeline on converted papers."""
    from paperlint.orchestrator import run_paper_eval

    target_type = _validate_targets(targets)
    all_papers = _papers_from_scope(targets, target_type, backend)

    # Filter: only papers with markdown; skip already-complete unless refetch.
    if not refetch:
        to_process = []
        for p in all_papers:
            if not p.get("markdown_path"):
                continue
            try:
                ev = backend.get_evaluation(p["paper_id"])
                if ev.get("pipeline_status") == "complete":
                    continue
            except Exception:
                pass
            to_process.append(p)
    else:
        to_process = [p for p in all_papers if p.get("markdown_path")]

    semaphore = asyncio.Semaphore(concurrency)

    async def _one(paper_row: dict) -> dict:
        pid = paper_row["paper_id"]
        async with semaphore:
            try:
                result = await asyncio.to_thread(
                    run_paper_eval,
                    pid,
                    mailing_meta=paper_row,
                    storage=backend,
                    discovery_passes=discovery_passes,
                )
                return {"paper_id": pid, "status": "ok", "result": result}
            except Exception as exc:
                logger.exception("Eval failed for %s", pid)
                return {"paper_id": pid, "status": "error", "error": str(exc)}

    tasks = [asyncio.create_task(_one(p)) for p in to_process]
    succeeded = []
    failed = []
    skipped = [p["paper_id"] for p in all_papers if p not in to_process]

    for coro in asyncio.as_completed(tasks):
        result = await coro
        if result["status"] == "ok":
            succeeded.append(result["paper_id"])
        else:
            failed.append(result)

    return {"succeeded": succeeded, "skipped": skipped, "failed": failed}


# ---------------------------------------------------------------------------
# run_full
# ---------------------------------------------------------------------------

async def run_full(
    targets: list[str],
    backend: StorageBackend,
    *,
    refetch: bool = False,
    verify: bool = False,
    concurrency: int = 10,
    discovery_passes: int = 3,
    current_year: str | None = None,
) -> dict:
    """Chain mailing -> download -> convert -> eval for the given targets."""
    target_type = _validate_targets(targets)

    # Determine years for mailing stage.
    if target_type == "years":
        mailing_targets = targets
    elif target_type == "all":
        mailing_targets = ["all"]
    else:
        # Paper IDs: derive years from what's in the DB (or skip mailing stage).
        mailing_targets = None

    results = {}

    if mailing_targets is not None:
        results["mailing"] = await run_mailing(
            mailing_targets, backend, current_year=current_year
        )

    results["download"] = await run_download(
        targets, backend, refetch=refetch, verify=verify, concurrency=concurrency
    )
    results["convert"] = await run_convert(
        targets, backend, refetch=refetch, concurrency=(concurrency // 2) or 1
    )
    results["eval"] = await run_eval(
        targets, backend, refetch=refetch, concurrency=concurrency,
        discovery_passes=discovery_passes
    )

    return results
