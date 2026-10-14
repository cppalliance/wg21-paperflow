#
# Copyright (c) 2026 Sean Parsons
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for deterministic metadata/outline comparison."""

from __future__ import annotations

from whisker.llm.metadata_compare import compare_metadata_outline

_SOURCE_METADATA = (
    "P2583R3\n"
    "Date: 2024-01-15\n"
    "A Proposal for a Utility Class to Represent Expected\n"
)

_CANDIDATE_MD_CLEAN = """---
title: "A Proposal for a Utility Class to Represent Expected"
document: P2583R3
date: 2024-01-15
---

## Abstract

Some abstract text.

## Introduction

Some introduction text.
"""


def test_clean_html_match():
    result = compare_metadata_outline(
        "P2583R3",
        _SOURCE_METADATA,
        [],
        _CANDIDATE_MD_CLEAN,
        source_kind="html",
        html_outline=[("h2", "Abstract"), ("h2", "Introduction")],
    )
    assert result.verdict == "pass"
    assert result.document_number_matches is True
    assert result.title_matches is True
    assert result.date_matches is True
    assert result.heading_drift == []
    assert result.missing_sections == []


_CANDIDATE_MD_REFERENCES = """---
title: "A Proposal for a Utility Class to Represent Expected"
document: P2583R3
date: 2024-01-15
---

## Abstract

Some abstract text.

### References

[1] Some reference.
"""


def test_html_heading_drift():
    result = compare_metadata_outline(
        "P2583R3",
        _SOURCE_METADATA,
        [],
        _CANDIDATE_MD_REFERENCES,
        source_kind="html",
        html_outline=[("h2", "Abstract"), ("h2", "References")],
    )
    assert result.verdict == "review"
    assert result.heading_drift
    assert "h2:References" in result.heading_drift[0]
    assert "h3:References" in result.heading_drift[0]


def test_wrong_document_pid_fails():
    candidate_md = _CANDIDATE_MD_CLEAN.replace("document: P2583R3", "document: P2583R2")
    result = compare_metadata_outline(
        "P2583R3",
        _SOURCE_METADATA,
        [],
        candidate_md,
        source_kind="html",
        html_outline=[("h2", "Abstract"), ("h2", "Introduction")],
    )
    assert result.verdict == "not-llm-readable"
    assert result.document_number_matches is False


def test_missing_sections():
    result = compare_metadata_outline(
        "P2583R3",
        _SOURCE_METADATA,
        [],
        _CANDIDATE_MD_CLEAN,
        source_kind="html",
        html_outline=[
            ("h2", "Abstract"),
            ("h2", "Introduction"),
            ("h2", "Acknowledgements"),
        ],
    )
    assert result.verdict == "review"
    assert result.missing_sections
    assert any("Acknowledgements" in entry for entry in result.missing_sections)


def test_toc_entries_ignored():
    result = compare_metadata_outline(
        "P2583R3",
        _SOURCE_METADATA,
        [],
        _CANDIDATE_MD_CLEAN,
        source_kind="html",
        html_outline=[
            ("h2", "Table of Contents"),
            ("h2", "Abstract"),
            ("h2", "Introduction"),
        ],
    )
    assert result.verdict == "pass"
    assert result.heading_drift == []
    assert result.missing_sections == []


def test_secno_normalized_matches():
    result = compare_metadata_outline(
        "P2583R3",
        _SOURCE_METADATA,
        [],
        _CANDIDATE_MD_CLEAN,
        source_kind="html",
        html_outline=[("h2", "1. Abstract"), ("h2", "2. Introduction")],
    )
    assert result.verdict == "pass"
    assert result.heading_drift == []
    assert result.missing_sections == []


def test_pdf_noisy_page_one_extracts_pid():
    noisy_metadata = (
        "Programming Language C++\n"
        "Some Author, some.author@example.com\n"
        "P2583R3\n"
        "2024-01-15\n"
        "A Proposal for a Utility Class to Represent Expected\n"
        "Abstract\n"
        "This paper proposes a utility class expected<T, E> that represents "
        "either an expected value or an error value...\n"
    )
    result = compare_metadata_outline(
        "P2583R3",
        noisy_metadata,
        [],
        _CANDIDATE_MD_CLEAN,
        source_kind="pdf",
    )
    assert result.document_number_matches is True


def test_pdf_missing_section_caps_at_review():
    source_outline = [
        "page 1, font 18.00: Abstract",
        "page 2, font 18.00: Motivation and Scope",
    ]
    result = compare_metadata_outline(
        "P2583R3",
        _SOURCE_METADATA,
        source_outline,
        _CANDIDATE_MD_CLEAN,
        source_kind="pdf",
    )
    assert result.verdict == "review"
    assert result.missing_sections
    assert any("Motivation" in entry for entry in result.missing_sections)


def test_empty_source_outline_no_error():
    result = compare_metadata_outline(
        "P2583R3",
        _SOURCE_METADATA,
        [],
        _CANDIDATE_MD_CLEAN,
        source_kind="pdf",
    )
    assert result.heading_drift == []
    assert result.missing_sections == []
    assert result.verdict == "pass"


def test_date_mismatch_is_review_not_fail():
    candidate_md = _CANDIDATE_MD_CLEAN.replace("date: 2024-01-15", "date: 2024-02-20")
    result = compare_metadata_outline(
        "P2583R3",
        _SOURCE_METADATA,
        [],
        candidate_md,
        source_kind="html",
        html_outline=[("h2", "Abstract"), ("h2", "Introduction")],
    )
    assert result.date_matches is False
    assert result.verdict == "review"


def test_missing_candidate_title_is_review_not_fail():
    candidate_md = _CANDIDATE_MD_CLEAN.replace(
        'title: "A Proposal for a Utility Class to Represent Expected"\n', ""
    )
    result = compare_metadata_outline(
        "P2583R3",
        _SOURCE_METADATA,
        [],
        candidate_md,
        source_kind="html",
        html_outline=[("h2", "Abstract"), ("h2", "Introduction")],
    )
    assert result.title_matches is False
    assert result.document_number_matches is True
    assert result.verdict == "review"


def test_reasoning_is_compact():
    result = compare_metadata_outline(
        "P2583R3",
        _SOURCE_METADATA,
        [],
        _CANDIDATE_MD_CLEAN,
        source_kind="html",
        html_outline=[("h2", "Abstract"), ("h2", "Introduction")],
    )
    assert len(result.reasoning.split()) < 40


def test_heading_drift_and_missing_sections_capped_at_five():
    html_outline = [("h2", f"Section {i}") for i in range(10)]
    result = compare_metadata_outline(
        "P2583R3",
        _SOURCE_METADATA,
        [],
        _CANDIDATE_MD_CLEAN,
        source_kind="html",
        html_outline=html_outline,
    )
    assert len(result.missing_sections) <= 5
    assert len(result.heading_drift) <= 5
