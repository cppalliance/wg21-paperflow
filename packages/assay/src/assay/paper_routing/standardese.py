#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""WG21 normative element (Standardese) label detection for sentence splitting."""

from __future__ import annotations

import re

# Labels aligned with W1 hypothesis regex in hypotheses.py plus common wording
# elements from tomd golden fixtures.
STANDARDESE_LABELS: tuple[str, ...] = (
    "Effects",
    "Returns",
    "Requires",
    "Remarks",
    "Throws",
    "Complexity",
    "Mandates",
    "Preconditions",
    "Synchronization",
    "Expects",
    "Notes",
)

_LABEL_ALT = "|".join(re.escape(label) for label in STANDARDESE_LABELS)

# Line-start matcher: optional markdown emphasis (*Effects:*), case-insensitive.
STANDARDESE_LINE_RE = re.compile(
    rf"^\s*(?:\*)?({_LABEL_ALT})(?:\*)?\s*:",
    re.IGNORECASE,
)

# Unanchored matcher for label boundaries inside a sentence (post-split pass).
STANDARDESE_LABEL_RE = re.compile(
    rf"(?:\*)?({_LABEL_ALT})(?:\*)?\s*:",
    re.IGNORECASE,
)


def is_standardese_line(line: str) -> bool:
    """Return True when *line* begins with a normative element label."""
    return STANDARDESE_LINE_RE.match(line.strip()) is not None
