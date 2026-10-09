#
# Copyright (c) 2026 Sean Parsons
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Convention-level canonicalization for fair block-agreement comparison.

Raw block agreement charges tomd for two things that are not conversion errors:
the deliberate ``:::wording`` fenced-div layer, which the ideals do not carry,
and heading section numbers, which the ideals themselves treat inconsistently
(p4182r0 keeps them, p1068r11 and p3556r0 strip them).

This module provides a pure canonicalization function that symmetrically removes
convention differences so that a block-agreement comparison measures conversion
quality, not markup dialect. Applied to BOTH candidate and reference.
"""

from __future__ import annotations

import re

__all__ = ["canonicalize_conventions"]

# Pandoc-style fenced divs (``:::wording``, ``:::`` close).
_DIV_FENCE_RE = re.compile(r"^:::.*$", re.MULTILINE)

# Leading heading section numbers: arabic dotted (``2.1.3``), roman
# (``IV``, ``XLII``), optionally followed by ``.`` or ``)``.
_HEADING_NUMBER_RE = re.compile(
    r"^(#{1,6})\s+(?:\d+(?:\.\d+)*|[IVXLC]+)[.)]?\s+(?=\S)",
    re.MULTILINE,
)

# Inline ``<ins>``/``<del>`` edit markup emitted by tomd for wording diffs.
_EDIT_MARKUP_RE = re.compile(r"</?(?:ins|del)>")

# Triple-or-more newlines collapsed to double (prevents blank-line inflation
# after stripping convention lines).
_EXCESS_NEWLINES_RE = re.compile(r"\n{3,}")


def canonicalize_conventions(text: str) -> str:
    """Remove convention-level markup that differs between tomd and the ideals.

    The same transformation is applied symmetrically to candidate and reference
    so the comparison measures conversion quality, not markup dialect.

    Removes:
    - Pandoc fenced-div lines (``:::wording``, ``:::`` close)
    - ``<ins>``/``<del>`` edit-markup tags
    - Leading heading section numbers (arabic and roman)
    - Excess blank lines introduced by the above
    """
    text = _DIV_FENCE_RE.sub("", text)
    text = _EDIT_MARKUP_RE.sub("", text)
    text = _HEADING_NUMBER_RE.sub(r"\1 ", text)
    return _EXCESS_NEWLINES_RE.sub("\n\n", text)
