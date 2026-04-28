#
# Copyright (c) 2026 Greg Kaleka (greg@gregkaleka.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""tomd CLI: convert paperstore-staged WG21 papers to markdown.

Workspace dir defaults to ``$PAPERFLOW_WORKSPACE`` or ``./data``; pass
``--workspace-dir`` to override per command.

Usage::

    tomd P3642R4
    tomd 2026                     # all papers for year 2026
    tomd P3642R4 P3700R0          # multiple paper ids
    tomd 2026 --qa                # batch QA scoring

Year positionals (4-digit) expand to every paper id for that year in the
local index. Run ``paperflow mailing <year>`` first to populate the index.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

from paperstore import WORKSPACE_ENV_VAR, SqliteBackend, default_workspace_dir
from paperstore.errors import (
    MissingMailingIndexError,
    MissingMetaError,
    MissingPaperMdError,
    MissingSourceError,
)

from tomd.api import convert_paper

_YEAR_RE = re.compile(r"^\d{4}$")


def expand_references(
    references: list[str], backend: SqliteBackend
) -> list[str]:
    """Expand year references to their paper-id lists.

    Each positional is either a year (``YYYY``, expanded via
    ``backend.list_papers_for_year``) or a paper id (passed through, uppercased).

    Raises ``MissingMailingIndexError`` if a year positional has no persisted index.
    """
    out: list[str] = []
    for ref in references:
        if _YEAR_RE.match(ref):
            rows = backend.list_papers_for_year(ref)
            out.extend(row["paper_id"].upper() for row in rows)
        else:
            out.append(ref.upper())
    return out


def _cmd_convert(
    paper_ids: list[str], backend: SqliteBackend, *, write_prompts: bool
) -> int:
    rc = 0
    for pid in paper_ids:
        try:
            source_path = backend.get_source_path(pid)
            meta = backend.get_meta(pid)
            markdown, prompts, intent = convert_paper(pid, source_path, meta)
            md_path = backend.write_paper_md(pid, markdown)
            if write_prompts and prompts:
                backend.write_intermediate(pid, "prompts", prompts)
            if intent:
                backend.record_markdown(pid, md_path, intent=intent)
            print(f"Converted {pid} -> {md_path}")
        except (MissingSourceError, MissingMetaError) as e:
            print(f"Skipping {pid}: {e}", file=sys.stderr)
            rc = max(rc, 2)
        except Exception as e:
            print(f"FAIL: {pid} -- {e}", file=sys.stderr)
            rc = max(rc, 1)
    return rc


def _cmd_qa(
    paper_ids: list[str],
    backend: SqliteBackend,
    *,
    json_path: Path | None,
    workers: int,
    timeout: int,
) -> int:
    from tomd.lib.pdf.qa import run_qa_report

    items: list[tuple[str, str]] = []
    for pid in paper_ids:
        try:
            md = backend.get_paper_md(pid)
        except MissingPaperMdError:
            print(
                f"Skipping {pid}: no paper markdown. Run convert first.",
                file=sys.stderr,
            )
            continue
        items.append((pid.upper(), md))

    if not items:
        print("No markdown available for QA.", file=sys.stderr)
        return 1

    run_qa_report(items, json_path=json_path, workers=workers, timeout=timeout)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="tomd",
        description="Convert paperstore-staged WG21 papers to markdown.",
    )
    parser.add_argument(
        "references",
        nargs="+",
        metavar="REF",
        help="Paper ids (e.g. P3642R4) or year (e.g. 2026, expands to all papers).",
    )
    parser.add_argument(
        "--workspace-dir",
        default=default_workspace_dir(),
        metavar="DIR",
        type=Path,
        help=f"Paperstore backend root (default: ${WORKSPACE_ENV_VAR} or ./data).",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "--no-prompts",
        action="store_true",
        help="Skip writing the .prompts intermediate.",
    )
    parser.add_argument(
        "--qa",
        action="store_true",
        help="Run QA scoring against paper.md instead of converting.",
    )
    parser.add_argument(
        "--qa-json",
        type=Path,
        metavar="PATH",
        help="Write per-paper QA metrics as JSON to PATH (implies --qa).",
    )
    parser.add_argument("--workers", type=int, default=1, help="QA parallelism.")
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="QA straggler timeout in seconds.",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s: %(message)s")

    backend = SqliteBackend(args.workspace_dir)

    try:
        paper_ids = expand_references(args.references, backend)
    except MissingMailingIndexError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    if not paper_ids:
        print("No papers to process.", file=sys.stderr)
        return 1

    if args.qa or args.qa_json:
        return _cmd_qa(
            paper_ids,
            backend,
            json_path=args.qa_json,
            workers=args.workers,
            timeout=args.timeout,
        )

    return _cmd_convert(paper_ids, backend, write_prompts=not args.no_prompts)


if __name__ == "__main__":
    sys.exit(main())
