#
# Copyright (c) 2026 Sean Parsons
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Structural marker counts for cheap, deterministic conversion triage.

Similarity metrics compress a document to one number and can hide a categorical
failure: a converter that emits no code fences at all still scores respectably
on character-level recall, because the characters are present, just unmarked.
Counting markers per class exposes that directly.

Each pattern is a compiled regex matching one structural construct in Markdown.
``count_markers`` returns all counts in one pass.
"""

from __future__ import annotations

import re

__all__ = ["MARKER_PATTERNS", "count_markers"]

MARKER_PATTERNS: dict[str, re.Pattern[str]] = {
    "code_fence": re.compile(r"^```", re.MULTILINE),
    "inline_code": re.compile(r"`[^`\n]+`"),
    "indented_code": re.compile(r"^    \S", re.MULTILINE),
    "heading": re.compile(r"^#{1,6} ", re.MULTILINE),
    "table_row": re.compile(r"^\|", re.MULTILINE),
    "empty_table_row": re.compile(r"^\|(\s*\|)+\s*$", re.MULTILINE),
    "image": re.compile(r"^!\[", re.MULTILINE),
    "escaped_underscore": re.compile(r"\\_"),
    "list_item": re.compile(r"^\s*[-*+] ", re.MULTILINE),
}


def count_markers(text: str) -> dict[str, int]:
    """Count structural markers in a Markdown document.

    Returns a dict mapping each marker class name to its count. All nine
    standard classes are always present in the result (zero when absent).
    """
    return {name: len(pat.findall(text)) for name, pat in MARKER_PATTERNS.items()}
