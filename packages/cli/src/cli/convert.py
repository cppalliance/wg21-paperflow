#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""CLI command module for 'paperflow convert'."""

from __future__ import annotations

import argparse
import asyncio
import sys

from paperstore.backend import StorageBackend


_DEFAULT_CONVERT_CONCURRENCY = 4
_DEFAULT_QA_WORKERS = 1
_DEFAULT_QA_TIMEOUT = 120


def command(args: argparse.Namespace, backend: StorageBackend) -> int:
    if args.qa or args.qa_json or args.check_content or args.check_content_json:
        return _report_command(args, backend)
    return _convert_command(args, backend)


def _convert_command(args: argparse.Namespace, backend: StorageBackend) -> int:
    from cli.jobs import run_convert
    from cli.progress import make_progress_handler

    progress_ctx, on_progress = make_progress_handler("Converting")

    with progress_ctx:
        result = asyncio.run(run_convert(
            args.targets,
            backend,
            force=args.force,
            concurrency=args.concurrency or _DEFAULT_CONVERT_CONCURRENCY,
            write_prompts=not args.no_prompts,
            on_progress=on_progress,
        ))

    succeeded = result.get("succeeded", [])
    skipped = result.get("skipped", [])
    failed = result.get("failed", [])

    print(f"Convert: {len(succeeded)} converted, {len(skipped)} skipped, {len(failed)} failed.")
    if failed:
        for item in failed:
            print(f"  ERROR {item['paper_id']}: {item['error']}", file=sys.stderr)
        return 1
    return 0


def _report_command(args: argparse.Namespace, backend: StorageBackend) -> int:
    """Dispatch report-only modes (--qa and / or --check-content).

    Both flags may be set in one invocation; the report sections print
    back-to-back. Returns non-zero only if no work could be performed at
    all (no markdown to score on either side).
    """
    from cli.jobs import run_content_check, run_qa

    workers = args.workers or _DEFAULT_QA_WORKERS
    timeout = args.timeout or _DEFAULT_QA_TIMEOUT
    qa_requested = args.qa or args.qa_json
    cc_requested = args.check_content or args.check_content_json

    succeeded_anything = False

    if qa_requested:
        qa_result = run_qa(
            args.targets,
            backend,
            json_path=args.qa_json,
            workers=workers,
            timeout=timeout,
        )
        for entry in qa_result["skipped"]:
            print(
                f"Skipping {entry['paper_id']}: no paper markdown. "
                f"Run 'paperflow convert' first.",
                file=sys.stderr,
            )
        if qa_result["succeeded"]:
            succeeded_anything = True
        elif not cc_requested:
            print("No markdown available for QA.", file=sys.stderr)

    if cc_requested:
        cc_result = run_content_check(
            args.targets,
            backend,
            json_path=args.check_content_json,
            workers=workers,
            timeout=timeout,
        )
        for entry in cc_result["skipped"]:
            print(
                f"Skipping {entry['paper_id']}: {entry['reason']}.",
                file=sys.stderr,
            )
        if cc_result["succeeded"]:
            succeeded_anything = True
        elif not qa_requested:
            print(
                "No papers available for content check. Run "
                "'paperflow convert' to produce markdown first.",
                file=sys.stderr,
            )

    if not succeeded_anything:
        return 1
    return 0
