#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

from whisker.gates import iter_body_lines, run_gates, split_front_matter

_GOOD = """---
title: "A Paper"
document: P1234R0
---

## Introduction

Some prose here.

## Design

```cpp
int main() {}
```

| Col A | Col B |
|-------|-------|
| 1     | 2     |
"""


def _gate(results, name):
    return next(g for g in results if g.name == name)


def test_public_parsing_helpers_preserve_gate_surfaces():
    front_matter, body = split_front_matter(
        "---\ntitle: x\ndocument: P1\n---\n\n## A\n\n```\nbody\n```\n"
    )

    assert front_matter == ["title: x", "document: P1"]
    assert list(iter_body_lines(body)) == [
        ("", "text"),
        ("## A", "text"),
        ("", "text"),
        ("```", "fence_toggle"),
        ("body", "fence_body"),
        ("```", "fence_toggle"),
    ]


def test_clean_document_passes_all_gates():
    results = run_gates(_GOOD)
    assert all(g.passed for g in results), [g for g in results if not g.passed]


def test_missing_front_matter_fails():
    g = _gate(run_gates("## Heading\n\ntext\n"), "front_matter_valid")
    assert not g.passed


def test_unterminated_front_matter_fails():
    md = "---\ntitle: x\ndocument: P1\n\n## Body\n"
    g = _gate(run_gates(md), "front_matter_valid")
    assert not g.passed


def test_empty_body_fails():
    md = "---\ntitle: x\ndocument: P1\n---\n\n   \n"
    g = _gate(run_gates(md), "non_empty")
    assert not g.passed


def test_heading_skip_fails():
    md = "---\ntitle: x\ndocument: P1\n---\n\n## A\n\n#### Skipped\n"
    g = _gate(run_gates(md), "heading_monotone")
    assert not g.passed


def test_empty_code_block_fails():
    md = "---\ntitle: x\ndocument: P1\n---\n\n## A\n\n```\n```\n"
    g = _gate(run_gates(md), "no_empty_code")
    assert not g.passed


def test_pipes_inside_code_are_not_a_table():
    md = (
        "---\ntitle: x\ndocument: P1\n---\n\n## A\n\n"
        "```\n| not | a |\n|-----|---|\n```\n"
    )
    assert _gate(run_gates(md), "no_empty_table").passed


def test_headless_table_fails():
    md = "---\ntitle: x\ndocument: P1\n---\n\n## A\n\n| H |\n|---|\n"
    g = _gate(run_gates(md), "no_empty_table")
    assert not g.passed


def test_thematic_break_is_not_an_empty_table():
    # A bare "---" horizontal rule must not be mistaken for a table separator.
    md = "---\ntitle: x\ndocument: P1\n---\n\n## A\n\nSome prose.\n\n---\n\nMore prose.\n"
    g = _gate(run_gates(md), "no_empty_table")
    assert g.passed


def test_real_table_with_data_passes():
    md = (
        "---\ntitle: x\ndocument: P1\n---\n\n## A\n\n"
        "| Col A | Col B |\n|-------|-------|\n| 1 | 2 |\n"
    )
    g = _gate(run_gates(md), "no_empty_table")
    assert g.passed


# --- no_toc_leak (PR-replay regressions: #290 p1122r3, #293 p0533r9) ---


def test_toc_leak_page_numbered_duplicate_fails():
    # PR #290 shape: TOC entries leaked as headings with trailing page
    # numbers, followed by the real body headings.
    md = (
        "---\ntitle: x\ndocument: P1\n---\n\n"
        "## 1. Introduction 3\n\n## 2. Scope 5\n\n## 1. Introduction\n\ntext\n"
    )
    g = _gate(run_gates(md), "no_toc_leak")
    assert not g.passed
    assert "TOC leak" in g.detail


def test_toc_leak_reverse_order_duplicate_fails():
    md = (
        "---\ntitle: x\ndocument: P1\n---\n\n"
        "## 1. Introduction\n\ntext\n\n## 1. Introduction 3\n"
    )
    g = _gate(run_gates(md), "no_toc_leak")
    assert not g.passed


def test_toc_leak_contents_label_fails():
    # PR #293 shape: a CONTENTS block kept in the body.
    md = "---\ntitle: x\ndocument: P1\n---\n\n## Abstract\n\ntext\n\nCONTENTS\n\nI. History\n"
    g = _gate(run_gates(md), "no_toc_leak")
    assert not g.passed
    assert "TOC label" in g.detail


def test_toc_leak_contents_heading_fails():
    md = "---\ntitle: x\ndocument: P1\n---\n\nintro\n\n## Contents\n\n| a | 3 |\n"
    g = _gate(run_gates(md), "no_toc_leak")
    assert not g.passed


def test_legit_duplicate_heading_without_page_number_passes():
    md = "---\ntitle: x\ndocument: P1\n---\n\n## Example\n\na\n\n## Example\n\nb\n"
    g = _gate(run_gates(md), "no_toc_leak")
    assert g.passed


def test_numbered_step_headings_pass():
    md = "---\ntitle: x\ndocument: P1\n---\n\n## Step 1\n\na\n\n## Step 2\n\nb\n"
    g = _gate(run_gates(md), "no_toc_leak")
    assert g.passed


def test_toc_shape_inside_code_fence_passes():
    md = (
        "---\ntitle: x\ndocument: P1\n---\n\n## A\n\n"
        "```md\n## 1. Intro 3\n## 1. Intro\nContents\n```\n"
    )
    g = _gate(run_gates(md), "no_toc_leak")
    assert g.passed


def test_contents_as_prose_word_passes():
    md = "---\ntitle: x\ndocument: P1\n---\n\n## A\n\nThe contents of the file are shown.\n"
    g = _gate(run_gates(md), "no_toc_leak")
    assert g.passed
