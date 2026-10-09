#
# Copyright (c) 2026 Sean Parsons
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Probe-strength mutilators for Lane-3 fact-set quality assurance.

A fact set that still passes on a severely degraded document is not measuring
conversion quality.  These mutilators apply escalating damage so that a test
can reject fact sets whose facts are too easy to satisfy.
"""

from __future__ import annotations

import re

__all__ = [
    "TRUNCATION_LEVELS",
    "keep_fraction",
    "shuffle_sections",
    "strip_all_structure",
]

TRUNCATION_LEVELS = (1.0, 0.5, 0.25, 0.10, 0.05, 0.02)


def strip_all_structure(text: str) -> str:
    """Remove every block marker, keeping only the words."""
    text = re.sub(r"^```.*$", "", text, flags=re.M)
    text = re.sub(r"^#{1,6} ", "", text, flags=re.M)
    text = re.sub(r"^\|.*$", "", text, flags=re.M)
    text = re.sub(r"[`*_>]", "", text)
    return re.sub(r"\n{2,}", "\n", text)


def shuffle_sections(text: str) -> str:
    """Reverse block order, destroying document sequence but no words."""
    return "\n\n".join(reversed(text.split("\n\n")))


def keep_fraction(text: str, fraction: float) -> str:
    """Truncate *text* to the first *fraction* of its characters."""
    return text[: int(len(text) * fraction)]
