#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""CLI command module for 'paperflow full'."""

from __future__ import annotations

import asyncio
import sys

from cli.jobs import DEFAULT_DOWNLOAD_CONCURRENCY, run_full
from paperstore.stages import STAGES


def _stage_counts(result: dict) -> tuple[int, int, int]:
    return (
        len(result["succeeded"]),
        len(result["skipped"]),
        len(result["failed"]),
    )


def _print_stage_summaries(
    stage_results: dict[str, dict | None],
    backend,
) -> None:
    """Emit human-readable stage summaries after the progress bar closes."""
    mailing = stage_results.get("mailing")
    if mailing is None and "mailing" in stage_results:
        print("Mailing: skipped")
    elif mailing is not None:
        succeeded, skipped, failed = _stage_counts(mailing)
        print(
            f"Mailing: {succeeded} scraped, {skipped} skipped, {failed} failed"
        )
        for entry in mailing["failed"]:
            year = entry.get("year", "?")
            error = entry.get("error", "unknown error")
            print(f"  Failed {year}: {error}", file=sys.stderr)

    download = stage_results.get("download")
    if download is not None:
        succeeded, skipped, failed = _stage_counts(download)
        print(
            f"Download: {succeeded} succeeded, {skipped} skipped, "
            f"{failed} failed"
        )
        for entry in download["failed"]:
            pid = entry["paper_id"]
            error = entry.get("error", "unknown error")
            backend.fail_paper(pid, stage=STAGES["download"], error=error)
            print(f"{pid}: {error}", file=sys.stderr)

    convert = stage_results.get("convert")
    if convert is not None:
        succeeded, skipped, failed = _stage_counts(convert)
        print(
            f"Convert: {succeeded} succeeded, {skipped} skipped, "
            f"{failed} failed"
        )
        for entry in convert["failed"]:
            pid = entry["paper_id"]
            error = entry.get("error", "unknown error")
            backend.fail_paper(pid, stage=STAGES["convert"], error=error)
            print(f"{pid}: {error}", file=sys.stderr)


def _print_citations_summary(citations: dict | None) -> None:
    """Emit a one-line citations summary (informational; never affects exit code)."""
    if citations is None:
        return
    succeeded, skipped, failed = _stage_counts(citations)
    if failed and succeeded == 0 and skipped == 0:
        print("Citations: failed (see logs)")
        return
    print(
        f"Citations: {succeeded} extracted, {skipped} skipped, {failed} failed"
    )


def command(args, backend):
    from cli.progress import make_progress_handler

    targets = args.targets
    force = getattr(args, "force", False)
    verify = getattr(args, "verify", False)
    concurrency = getattr(args, "concurrency", None) or DEFAULT_DOWNLOAD_CONCURRENCY
    extract_vector = getattr(args, "extract_vector_images", False)
    whiteout_text = getattr(args, "vector_whiteout_text", False)

    exit_code = 0
    stage_failures: dict[str, int] = {}
    stage_results: dict[str, dict | None] = {}

    def on_stage_complete(stage: str, result: dict | None) -> None:
        nonlocal exit_code

        stage_results[stage] = result
        if result is None:
            return

        failed = len(result["failed"])
        if failed:
            stage_failures[stage] = failed
            exit_code = 1

    progress_ctx, on_progress = make_progress_handler("Full pipeline")

    with progress_ctx:
        results = asyncio.run(
            run_full(
                targets, backend,
                force=force,
                verify=verify,
                concurrency=concurrency,
                extract_vector=extract_vector,
                whiteout_text=whiteout_text,
                on_progress=on_progress,
                on_stage_complete=on_stage_complete,
            )
        )

    _print_stage_summaries(stage_results, backend)
    _print_citations_summary(results.get("citations"))

    total_failed = sum(stage_failures.values())
    if total_failed:
        parts = ", ".join(
            f"{name}: {count}" for name, count in sorted(stage_failures.items())
        )
        print(f"Full: {total_failed} failed ({parts})")
    else:
        print("Full: complete")

    return exit_code
