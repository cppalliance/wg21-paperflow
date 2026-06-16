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

    def on_stage_complete(stage: str, result: dict | None) -> None:
        nonlocal exit_code

        if stage == "mailing":
            if result is None:
                print("Mailing: skipped")
                return
            succeeded, skipped, failed = _stage_counts(result)
            print(
                f"Mailing: {succeeded} scraped, {skipped} skipped, {failed} failed"
            )
            for entry in result["failed"]:
                year = entry.get("year", "?")
                error = entry.get("error", "unknown error")
                print(f"  Failed {year}: {error}", file=sys.stderr)
            if failed:
                stage_failures["mailing"] = failed
                exit_code = 1
            return

        if stage == "download":
            assert result is not None
            succeeded, skipped, failed = _stage_counts(result)
            print(
                f"Download: {succeeded} succeeded, {skipped} skipped, "
                f"{failed} failed"
            )
            for entry in result["failed"]:
                pid = entry["paper_id"]
                error = entry.get("error", "unknown error")
                backend.fail_paper(pid, stage=STAGES["download"], error=error)
                print(f"{pid}: {error}", file=sys.stderr)
            if failed:
                stage_failures["download"] = failed
                exit_code = 1
            return

        if stage == "convert":
            assert result is not None
            succeeded, skipped, failed = _stage_counts(result)
            print(
                f"Convert: {succeeded} succeeded, {skipped} skipped, "
                f"{failed} failed"
            )
            for entry in result["failed"]:
                pid = entry["paper_id"]
                error = entry.get("error", "unknown error")
                backend.fail_paper(pid, stage=STAGES["convert"], error=error)
                print(f"{pid}: {error}", file=sys.stderr)
            if failed:
                stage_failures["convert"] = failed
                exit_code = 1

    progress_ctx, on_progress = make_progress_handler("Full pipeline")

    with progress_ctx:
        asyncio.run(
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

    total_failed = sum(stage_failures.values())
    if total_failed:
        parts = ", ".join(
            f"{name}: {count}" for name, count in sorted(stage_failures.items())
        )
        print(f"Full: {total_failed} failed ({parts})")
    else:
        print("Full: complete")

    return exit_code
