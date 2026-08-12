#
# Copyright (c) 2026 Leo Chen (leo.chen0412@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_ASSAY_ROOT = Path(__file__).resolve().parents[1]
_VALIDATE = _ASSAY_ROOT / "study" / "golden" / "validate_categories.py"


def _load_validate_module():
    spec = importlib.util.spec_from_file_location(
        "validate_categories",
        _VALIDATE,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_validate = _load_validate_module()


def test_validate_schema_rejects_invalid_target_group(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(
        '{"paper_id": "P0000R0", "title": "t", "target_group": "LWEG", '
        '"categories": ["library-design"], "confidence": "high", "notes": ""}\n',
        encoding="utf-8",
    )
    entries = _validate.load_entries(bad)
    errors = _validate.validate_schema(entries)
    assert any("invalid target_group 'LWEG'" in err for err in errors)


def test_validate_schema_rejects_first_category_target_group_mismatch(
    tmp_path,
):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(
        '{"paper_id": "P0000R0", "title": "t", "target_group": "LEWG", '
        '"categories": ["library-wording"], "confidence": "high", "notes": ""}\n',
        encoding="utf-8",
    )
    entries = _validate.load_entries(bad)
    errors = _validate.validate_schema(entries)
    assert any(
        "first category 'library-wording' does not match target_group 'LEWG'"
        in err
        for err in errors
    )


def test_validate_schema_rejects_duplicate_categories(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(
        '{"paper_id": "P0000R0", "title": "t", "target_group": "LEWG", '
        '"categories": ["library-design", "library-design"], "confidence": "high", '
        '"notes": ""}\n',
        encoding="utf-8",
    )
    entries = _validate.load_entries(bad)
    errors = _validate.validate_schema(entries)
    assert any("duplicate categories" in err for err in errors)


def test_validate_schema_rejects_unsorted_category_tail(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(
        '{"paper_id": "P0000R0", "title": "t", "target_group": "LEWG", '
        '"categories": ["library-design", "library-wording", "language-evolution"], '
        '"confidence": "high", "notes": ""}\n',
        encoding="utf-8",
    )
    entries = _validate.load_entries(bad)
    errors = _validate.validate_schema(entries)
    assert any("categories after the first must be sorted" in err for err in errors)


def test_validate_schema_rejects_informational_with_primary(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(
        '{"paper_id": "P0000R0", "title": "t", "target_group": "NONE", '
        '"categories": ["informational", "library-design"], "confidence": "high", '
        '"notes": ""}\n',
        encoding="utf-8",
    )
    entries = _validate.load_entries(bad)
    errors = _validate.validate_schema(entries)
    assert any(
        "informational cannot co-occur with primary categories" in err
        for err in errors
    )


def test_golden_categories_default_validate_exits_zero():
    result = subprocess.run(
        [sys.executable, str(_VALIDATE)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"validate_categories failed:\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert "Train and test paper_id sets are disjoint." in result.stdout


def test_golden_categories_train_validate_exits_zero():
    result = subprocess.run(
        [sys.executable, str(_VALIDATE), "--train"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"validate_categories failed:\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def test_golden_categories_test_validate_exits_zero():
    result = subprocess.run(
        [sys.executable, str(_VALIDATE), "--test"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"validate_categories failed:\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def test_train_test_paper_ids_disjoint():
    train_entries = _validate.load_entries(_validate.train_path())
    test_entries = _validate.load_entries(_validate.test_path())
    errors = _validate.disjointness_errors(train_entries, test_entries)
    assert not errors
