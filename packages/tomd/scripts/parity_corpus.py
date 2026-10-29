"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

import argparse
import difflib
import logging
import os
from pathlib import Path
import sys
from typing import Any
from unittest.mock import patch

import tomd.api as tomd_api
from tomd.api import convert_paper_full
from tomd.lib.shared import apply_strip_leading_h1, strip_freeform_metadata_lines
from tomd.lib.metadata_yaml.format import parse_front_matter
from tomd.lib.pdf.pipeline import run_pipeline
from tomd.parsers.legacy_bridge import render_pdf
from tomd.parsers.pdf import sections_to_document
from tomd.writers.markdown.normalizers import (
    normalize_front_matter,
    strip_body_metadata_text,
    strip_toc,
)

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


def _apply_api_normalizers(md: str, meta: dict[str, Any]) -> str:
    md = normalize_front_matter(md, meta)
    md = strip_body_metadata_text(md)
    md = strip_freeform_metadata_lines(md, metadata=meta)
    title = parse_front_matter(md).get("title")
    if isinstance(title, str) and title:
        md = apply_strip_leading_h1(md, title)
    return strip_toc(md)


def _discover_pdfs(data_dir: Path) -> list[Path]:
    paperstore_dir = data_dir / "paperstore"
    search_dir = paperstore_dir if paperstore_dir.is_dir() else data_dir
    return sorted(search_dir.glob("*.pdf"))


def run_corpus_parity(data_dir: Path) -> int:
    """Run converter-level and API-level parity across all PDFs in ``data_dir``."""
    pdfs = _discover_pdfs(data_dir)
    if not pdfs:
        _log.error("No .pdf files found under %s", data_dir)
        return 2

    converter_failures = 0
    api_failures = 0

    for pdf_path in pdfs:
        paper_id = pdf_path.stem.upper()
        legacy = run_pipeline(pdf_path)
        doc = sections_to_document(legacy, paper_id=paper_id)
        dark_md = render_pdf(doc)
        dark_prompts = doc.reconcile_prompts()

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
        with patch.object(tomd_api, "run_pipeline", return_value=legacy):
            legacy_api_md = convert_paper_full(paper_id, pdf_path, meta).markdown
        dark_api_md = _apply_api_normalizers(dark_md, meta)
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
        help="Path to WG21_DATA_DIR or directory of .pdf files (defaults to $WG21_DATA_DIR).",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    raw_dir = args.data_dir or (
        Path(os.environ["WG21_DATA_DIR"]) if os.environ.get("WG21_DATA_DIR") else None
    )
    if raw_dir is None or not raw_dir.is_dir():
        _log.error(
            "Valid --data-dir or $WG21_DATA_DIR directory is required (got %r)",
            str(raw_dir) if raw_dir is not None else None,
        )
        return 2

    return run_corpus_parity(raw_dir)


if __name__ == "__main__":
    sys.exit(main())
