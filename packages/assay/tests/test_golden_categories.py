#
# Copyright (c) 2026 Leo Chen (leo.chen0412@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ASSAY_ROOT = Path(__file__).resolve().parents[1]
_JSONL = _ASSAY_ROOT / "data" / "golden" / "paper_categories.jsonl"
_VALIDATE = _ASSAY_ROOT / "study" / "golden" / "validate_categories.py"


def test_validate_schema_rejects_invalid_target_group(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(
        '{"paper_id": "P0000R0", "title": "t", "target_group": "LWEG", '
        '"categories": ["library-design"], "confidence": "high", "notes": ""}\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(_VALIDATE), str(bad)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "invalid target_group 'LWEG'" in result.stderr


def test_validate_schema_rejects_first_category_target_group_mismatch(
    tmp_path,
):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(
        '{"paper_id": "P0000R0", "title": "t", "target_group": "LEWG", '
        '"categories": ["library-wording"], "confidence": "high", "notes": ""}\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(_VALIDATE), str(bad)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert (
        "first category 'library-wording' does not match target_group 'LEWG'"
        in result.stderr
    )


def test_validate_schema_rejects_duplicate_categories(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(
        '{"paper_id": "P0000R0", "title": "t", "target_group": "LEWG", '
        '"categories": ["library-design", "library-design"], "confidence": "high", '
        '"notes": ""}\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(_VALIDATE), str(bad)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "duplicate categories" in result.stderr


def test_validate_schema_rejects_unsorted_category_tail(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(
        '{"paper_id": "P0000R0", "title": "t", "target_group": "LEWG", '
        '"categories": ["library-design", "library-wording", "language-evolution"], '
        '"confidence": "high", "notes": ""}\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(_VALIDATE), str(bad)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "categories after the first must be sorted" in result.stderr


def test_validate_schema_rejects_informational_with_primary(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(
        '{"paper_id": "P0000R0", "title": "t", "target_group": "NONE", '
        '"categories": ["informational", "library-design"], "confidence": "high", '
        '"notes": ""}\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(_VALIDATE), str(bad)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert (
        "informational cannot co-occur with primary categories"
        in result.stderr
    )


def test_golden_categories_validate_exits_zero():
    result = subprocess.run(
        [sys.executable, str(_VALIDATE), str(_JSONL)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"validate_categories failed:\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
