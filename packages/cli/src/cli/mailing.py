#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""CLI command module for 'paperflow mailing'."""

from __future__ import annotations

import asyncio
import sys


def command(args, backend):
    from cli.jobs import run_mailing
    from cli.progress import make_progress_handler

    targets = args.targets or ["all"]
    force = getattr(args, "force", False)

    progress_ctx, on_progress = make_progress_handler("Scraping mailings")

    with progress_ctx:
        result = asyncio.run(
            run_mailing(
                targets, backend,
                force=force,
                on_progress=on_progress,
            )
        )

    succeeded = len(result["succeeded"])
    skipped = len(result["skipped"])
    failed = len(result["failed"])

    for entry in result["failed"]:
        year = entry.get("year", "?")
        error = entry.get("error", "unknown error")
        print(f"  Failed {year}: {error}", file=sys.stderr)

    total_papers = len(backend.list_all_paper_ids())
    print(
        f"Mailing index: {succeeded} years scraped, {skipped} skipped, "
        f"{failed} failed. {total_papers} papers in store."
    )
    return 1 if failed else 0
