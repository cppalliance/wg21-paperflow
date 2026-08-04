#
# Copyright (c) 2026 Dmitriy Chukhin (dmitriy@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Smoke tests for `paperflow convert --check-content`.

The flag short-circuits conversion (same as --qa); it must read the
staged source plus the converted markdown and emit a coverage report.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from paperstore.testing import store  # noqa: F401  (pytest fixture)
from tomd.lib.check_content import _JSON_SCHEMA_VERSION


_BODY = (
    "Section one introduces the proposal. "
    "The motivation explains why current C++ language facilities "
    "are insufficient for the use case under consideration. "
    "Implementation experience demonstrates feasibility "
    "on every major standard library implementation. "
)


def _stage(store, pid: str, body: str, md: str) -> None:
    store.upsert_year("2026", [{"paper_id": pid, "title": "Sample"}])
    html = f"<html><body>{body}</body></html>"
    store.put_source(pid, html.encode("utf-8"), suffix=".html")
    store.write_paper_md(pid, md)


def test_check_content_writes_json(store, tmp_path: Path):
    body = _BODY * 4
    _stage(store, "P1000R0", body, body)

    json_path = tmp_path / "check.json"
    result = subprocess.run(
        [
            sys.executable, "-m", "cli", "--workspace-dir", str(tmp_path),
            "convert", "2026", "--check-content",
            "--check-content-json", str(json_path),
        ],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert json_path.exists()
    payload = json.loads(json_path.read_text())
    # Track the library constant rather than a literal, so a schema bump
    # does not need an edit here to stay honest.
    assert payload["schema_version"] == _JSON_SCHEMA_VERSION
    assert "constants" in payload
    assert payload["constants"]["shingle_width"] == 5
    assert len(payload["papers"]) == 1
    paper = payload["papers"][0]
    assert paper["paper_id"] == "P1000R0"
    assert paper["coverage"] > 0.9
    # schema 2 adds the complementary word-level signal
    assert "unigram_coverage" in paper
    assert "unigram_drift" in paper


def test_check_content_report_structure(store, tmp_path: Path):
    body = _BODY * 4
    _stage(store, "P1000R0", body, body)

    result = subprocess.run(
        [
            sys.executable, "-m", "cli", "--workspace-dir", str(tmp_path),
            "convert", "2026", "--check-content",
        ],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "tomd Content-Check Report: 1 files" in result.stdout
    assert "Coverage Distribution:" in result.stdout
    assert "Worst 1 files (lowest coverage):" in result.stdout
    assert "P1000R0" in result.stdout
    assert re.search(
        r"\[\d+/1\].*P1000R0.*files/s.*ETA",
        result.stderr,
    )
    assert "Finished in" in result.stderr


def test_check_content_skips_papers_without_source(store, tmp_path: Path):
    store.upsert_year("2026", [{"paper_id": "P9998R0", "title": "no source"}])
    store.write_paper_md("P9998R0", "body\n")

    result = subprocess.run(
        [
            sys.executable, "-m", "cli", "--workspace-dir", str(tmp_path),
            "convert", "2026", "--check-content",
        ],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    assert "no_source" in result.stderr.lower() or "no source" in result.stderr.lower()
