"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

import argparse
import difflib
import logging
from pathlib import Path
import sys
from typing import Any
from unittest.mock import patch

from paperstore import MissingSourceError, StorageBackend, default_workspace_dir, from_uri
import tomd.api as tomd_api
from tomd.api import convert_paper_full
from tomd.lib.pdf.pipeline import run_pipeline
from tomd.parsers.legacy_bridge import apply_api_normalizers, render_pdf
from tomd.parsers.pdf import sections_to_document

_log = logging.getLogger(__name__)

_DIFF_CONTEXT_LINES = 3
_MAX_DIFF_LINES = 60


def _first_diff(expected: str, actual: str, label: str) -> str:
    diff = list(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile=f"{label}:legacy",
            tofile=f"{label}:dark",
            n=_DIFF_CONTEXT_LINES,
        )
    )
    return "".join(diff[:_MAX_DIFF_LINES])


def _staged_pdfs(backend: StorageBackend) -> list[tuple[str, Path]]:
    pdfs: list[tuple[str, Path]] = []
    for paper_id in sorted(backend.list_all_paper_ids()):
        try:
            path = backend.get_source_path(paper_id)
        except MissingSourceError:
            continue
        if path.suffix.lower() == ".pdf":
            pdfs.append((paper_id, path))
    return pdfs


def run_corpus_parity(backend: StorageBackend) -> int:
    """Run converter-level and API-level parity across every staged PDF in ``backend``."""
    pdfs = _staged_pdfs(backend)
    if not pdfs:
        _log.error("No staged PDF sources found")
        return 2

    converter_failures = 0
    api_failures = 0

    for paper_id, pdf_path in pdfs:
        legacy = run_pipeline(pdf_path)
        doc = sections_to_document(legacy, paper_id=paper_id)
        dark_md = render_pdf(doc)
        dark_prompts = doc.get_reconciliation_prompts()

        if dark_md != legacy.md or dark_prompts != legacy.prompts:
            converter_failures += 1
            if dark_md != legacy.md:
                _log.error(
                    "Converter MD mismatch for %s:\n%s",
                    pdf_path.name,
                    _first_diff(legacy.md, dark_md, f"{paper_id}:converter"),
                )
            else:
                _log.error("Converter prompts mismatch for %s", pdf_path.name)

        if legacy.skipped:
            if not doc.is_skipped or dark_md != "":
                api_failures += 1
                _log.error("API skip mismatch for %s", pdf_path.name)
            continue

        meta: dict[str, Any] = {"paper_id": paper_id}
        # Reuse this run so the API path does not convert the PDF a second time.
        with patch.object(tomd_api, "run_pipeline", return_value=legacy):
            legacy_api_md = convert_paper_full(paper_id, pdf_path, meta).markdown
        dark_api_md = apply_api_normalizers(dark_md, meta)
        if dark_api_md != legacy_api_md:
            api_failures += 1
            _log.error(
                "API MD mismatch for %s:\n%s",
                pdf_path.name,
                _first_diff(legacy_api_md, dark_api_md, f"{paper_id}:api"),
            )

    total = len(pdfs)
    _log.info(
        "Parity summary: %d PDFs checked | converter=%d/%d passed | api=%d/%d passed",
        total,
        total - converter_failures,
        total,
        total - api_failures,
        total,
    )
    return 1 if (converter_failures + api_failures) > 0 else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run converter-level and API-level parity over a PDF corpus.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Workspace directory (defaults to $WG21_DATA_DIR).",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        workspace_dir = args.data_dir or default_workspace_dir()
    except OSError as exc:
        _log.error("%s", exc)
        return 2
    if not workspace_dir.is_dir():
        _log.error("Workspace directory does not exist: %s", workspace_dir)
        return 2

    return run_corpus_parity(from_uri(workspace_dir=workspace_dir))


if __name__ == "__main__":
    sys.exit(main())
