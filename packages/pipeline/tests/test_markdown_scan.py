#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

from __future__ import annotations

from pipeline.markdown import front_matter_end_index

_WG21_FM = """\
---
title: "Example"
document: P1234R0
---

## Motivation

Body.
"""


def test_front_matter_end_index_empty():
    assert front_matter_end_index([]) == 0


def test_front_matter_end_index_no_fence():
    lines = ["## Title", "", "Body."]
    assert front_matter_end_index(lines) == 0


def test_front_matter_end_index_leading_blank_then_fence():
    lines = ["", "  ---", "title: x", "---", "## Motivation"]
    assert front_matter_end_index(lines) == 4


def test_front_matter_end_index_standard_wg21_block():
    lines = _WG21_FM.splitlines()
    assert front_matter_end_index(lines) == 4


def test_front_matter_end_index_unterminated_fence():
    lines = ["---", "title: x", "## Never closes"]
    assert front_matter_end_index(lines) == 3


def test_front_matter_end_index_first_non_blank_not_fence():
    lines = ["# Title", "---", "ignored"]
    assert front_matter_end_index(lines) == 0
