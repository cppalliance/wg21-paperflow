"""Tests for QA batch runner and report formatting."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from tomd.lib.batch import BatchRunResult
from tomd.lib.pdf.qa import (
    QAMetrics,
    format_qa_report,
    run_qa_batch,
    write_qa_json_atomic,
)


_GOOD_MD = """\
---
title: "Test Paper"
document: P1234R0
date: 2025-01-01
audience: LEWG
reply-to:
  - "Author Name <author@example.com>"
---

## 1 Introduction

Some introductory text about the paper.

## 2 Motivation

More text explaining motivation.
"""


def test_run_qa_batch_returns_sorted_metrics():
    items = [
        ("bad", ""),
        ("good", _GOOD_MD),
    ]
    batch = run_qa_batch(items, workers=1)
    assert len(batch.metrics) == 2
    assert batch.errors == ()
    assert batch.metrics[0].score <= batch.metrics[1].score
    assert batch.metrics[0].score == 0
    assert batch.metrics[1].score == 100


def test_run_qa_batch_collects_timeout_errors():
    fake_run = BatchRunResult(
        outcomes=(),
        timed_out=("bad",),
        elapsed_sec=1.0,
    )
    with patch("tomd.lib.pdf.qa.run_parallel_batch", return_value=fake_run):
        batch = run_qa_batch([("bad", "")], workers=1, timeout=120)

    assert batch.metrics == ()
    assert batch.errors == (
        ("bad", "timeout (no progress for 120s)"),
    )


def test_format_qa_report_contains_expected_sections():
    results = [
        QAMetrics(file="a.md", score=50, issues=["no headings"]),
        QAMetrics(file="b.md", score=100, issues=[]),
        QAMetrics(file="c.md", score=95, issues=[]),
    ]
    text = format_qa_report(results)
    assert "tomd QA Report: 3 files" in text
    assert "Score Distribution:" in text
    assert "Files needing review" in text
    assert "Worst" in text
    # Worst list is sorted by score ascending in metrics input; format uses
    # score < 100 filter preserving input order among non-perfect scores.
    assert "a.md" in text


def test_format_qa_report_renders_errors():
    text = format_qa_report(
        (),
        errors=(("P9999R0", "timeout (no progress for 120s)"),),
    )
    assert "Errors: 1" in text
    assert "P9999R0" in text
    assert "timeout (no progress for 120s)" in text
    assert "No papers were scored." in text
    assert "Score Distribution" not in text
    assert "Worst" not in text


def test_format_qa_report_empty_input_is_terse():
    text = format_qa_report(())
    assert "No papers were scored." in text
    assert "Score Distribution" not in text
    assert "Worst" not in text
    assert "Errors" not in text


def test_format_qa_report_renders_errors_alongside_metrics():
    results = [
        QAMetrics(file="good.md", score=100, issues=[]),
    ]
    text = format_qa_report(
        results,
        errors=(("bad.md", "worker failed"),),
    )
    assert "tomd QA Report: 1 files" in text
    assert "Score Distribution:" in text
    assert "Errors: 1" in text
    assert "bad.md" in text
    assert "worker failed" in text


def test_write_qa_json_atomic_round_trip(tmp_path: Path):
    metrics = [QAMetrics(file="a.md", score=90, issues=[])]
    path = tmp_path / "qa.json"
    write_qa_json_atomic(path, metrics)
    data = json.loads(path.read_text())
    assert data[0]["file"] == "a.md"
    assert data[0]["score"] == 90
