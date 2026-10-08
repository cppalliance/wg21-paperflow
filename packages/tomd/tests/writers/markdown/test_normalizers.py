"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from tomd.writers.markdown.normalizers import (
    normalize_front_matter,
    strip_body_metadata_text,
    strip_toc,
)


def test_strip_toc_removes_contents_block():
    text = (
        "## Contents\n"
        "1. Scope\n"
        "2. Terms\n\n"
        "## 1 Scope\n"
        "Body paragraph.\n"
    )
    stripped = strip_toc(text)
    assert "## Contents" not in stripped
    assert "1. Scope" not in stripped
    assert "## 1 Scope\nBody paragraph.\n" in stripped


def test_strip_body_metadata_text():
    md = (
        "---\n"
        "title: Sample\n"
        "document: P1000R0\n"
        "---\n\n"
        "| Doc No. | P1000R0 |\n"
        "| --- | --- |\n"
        "| Date | 2026-01-01 |\n"
        "| Reply-to | author@example.com |\n\n"
        "## Introduction\n"
        "Real content here.\n"
    )
    cleaned = strip_body_metadata_text(md)
    assert "Real content here." in cleaned
    assert "| Doc No. | P1000R0 |" not in cleaned


def test_normalize_front_matter_function():
    md = "---\ntitle: Raw Title\n---\n\nBody content"
    meta = {"document": "P7777R0", "date": "2026-05-01"}
    normalized = normalize_front_matter(md, meta)
    assert 'title: "Raw Title"' in normalized
    assert "document: P7777R0" in normalized
    assert "date: 2026-05-01" in normalized
    assert "Body content" in normalized
