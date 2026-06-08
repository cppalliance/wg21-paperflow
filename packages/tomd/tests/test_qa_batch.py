"""Tests for QA batch runner and report formatting."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tomd.lib.pdf.qa import (
    QAMetrics,
    format_qa_report,
    run_qa_batch,
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
    assert batch.metrics[0].score <= batch.metrics[1].score
    assert batch.metrics[0].score == 0
    assert batch.metrics[1].score == 100


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
