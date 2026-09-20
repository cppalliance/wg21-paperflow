#
# Copyright (c) 2026 Sean Parsons
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

from whisker.det.canonical import canonicalize_conventions


def test_idempotent():
    text = "## Introduction\n\nSome prose about allocators.\n"
    assert canonicalize_conventions(canonicalize_conventions(text)) == canonicalize_conventions(text)


def test_strips_div_fences():
    text = ":::wording\nSome text.\n:::\n"
    result = canonicalize_conventions(text)
    assert ":::" not in result
    assert "Some text." in result


def test_strips_edit_markup():
    text = "An <ins>inserted</ins> and <del>removed</del> word.\n"
    result = canonicalize_conventions(text)
    assert "<ins>" not in result
    assert "<del>" not in result
    assert "inserted" in result
    assert "removed" in result


def test_strips_arabic_heading_number():
    text = "## 2 Revision History\n\n### 4.1 What is a file?\n"
    result = canonicalize_conventions(text)
    assert result == "## Revision History\n\n### What is a file?\n"


def test_strips_roman_heading_number():
    text = "## II Revision history\n"
    result = canonicalize_conventions(text)
    assert result == "## Revision history\n"


def test_strips_roman_heading_number_with_dot():
    text = "## IV. Design\n"
    result = canonicalize_conventions(text)
    assert result == "## Design\n"


def test_preserves_prose():
    text = "This is paragraph 2 about 42 things and IV items.\n"
    result = canonicalize_conventions(text)
    assert result == text


def test_preserves_heading_without_number():
    text = "## Abstract\n\n### Motivation\n"
    assert canonicalize_conventions(text) == text


def test_collapses_triple_newlines():
    text = "## H\n\n\n\nParagraph.\n"
    result = canonicalize_conventions(text)
    assert "\n\n\n" not in result
    assert "## H\n\nParagraph.\n" == result


def test_symmetry_on_tomd_vs_ideal():
    tomd = ":::wording\n## 2 Revision History\n<ins>new</ins> text.\n:::\n"
    ideal = "## Revision History\nnew text.\n"
    assert canonicalize_conventions(tomd).strip() == canonicalize_conventions(ideal).strip()
