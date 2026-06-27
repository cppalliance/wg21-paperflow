#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

from whisker.gates import run_gates

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
