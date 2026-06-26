#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Shared heading classifiers for blanking and survey signals."""

from __future__ import annotations

import re
from enum import Enum, auto

from pipeline.markdown_patterns import HEADING_RE

# ---------------------------------------------------------------------------
# Blanking tri-state
# ---------------------------------------------------------------------------


class HeadingKind(Enum):
    """Tri-state result for blanking heading classifiers."""

    YES = auto()
    NO = auto()
    UNKNOWN = auto()


# ---------------------------------------------------------------------------
# Revision history (blanking)
# ---------------------------------------------------------------------------

_REVISION_HEADING_RES: list[re.Pattern[str]] = [
    re.compile(r"^#{1,6}\s+.*revision\s+history", re.IGNORECASE),
    re.compile(r"^#{1,6}\s+.*change\s*log", re.IGNORECASE),
    re.compile(r"^#{1,6}\s+.*document\s+history", re.IGNORECASE),
    re.compile(
        r"^#{1,6}\s+(?:\d+[\.\d]*\s+)?changes\s+(?:since|from)\s+"
        r"(?:R\d|revision|the\s+previous|[PD]\d+R\d+|v\d)",
        re.IGNORECASE,
    ),
    re.compile(
        r"^#{1,6}\s+.*changes\s+in\s+this\s+(?:revision|paper)",
        re.IGNORECASE,
    ),
    re.compile(r"^#{1,6}\s+R\d+(?!\.\s*[A-Za-z])\b", re.IGNORECASE),
    re.compile(r"^#{1,6}\s+Revision\s+\d+", re.IGNORECASE),
    re.compile(
        r"^#{1,6}\s+(?:\d+[\.\d]*\s+)?changes\s+in\s+(?:R\d|revision\s+\d)",
        re.IGNORECASE,
    ),
]

_BOLD_REVISION_RES: list[re.Pattern[str]] = [
    re.compile(r"^\*\*\s*Revision\s+History\s*\*\*\s*$", re.IGNORECASE),
    re.compile(r"^\*\*\s*Changelog\s*\*\*\s*$", re.IGNORECASE),
    re.compile(r"^\*\*\s*Document\s+history\s*\*\*\s*$", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# References (blanking)
# ---------------------------------------------------------------------------

_REFERENCE_HEADING_RES: list[re.Pattern[str]] = [
    re.compile(
        r"^#{1,6}\s+(?:[\divxlcdm]+[\.\)]\s*)?\*?"
        r"(?:informative|normative)?\s*references\s*\*?"
        r"\s*[:{]?\s*(?:\{[^}]*\})?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^#{1,6}\s+(?:[\divxlcdm]+[\.\)]\s*)?\*?"
        r"bibliography\*?\s*(?:\{[^}]*\})?\s*$",
        re.IGNORECASE,
    ),
]

# ---------------------------------------------------------------------------
# Acknowledgments (blanking)
# ---------------------------------------------------------------------------

_ACKNOWLEDGMENT_HEADING_RE = re.compile(
    r"^#{1,6}\s+(?:[\divxlcdm]+[\.\)]\s*)?\*?"
    r"acknowledg[e]?ments?\s*\*?"
    r"\s*[:{]?\s*(?:\{[^}]*\})?\s*$",
    re.IGNORECASE,
)

# Survey wording signal (assay Step 3).
SURVEY_WORDING_HEADING_RE = re.compile(
    r"(?i)\bwording\b|\bproposed\s+changes\b|\bproposed\s+resolution\b",
)

_APPENDIX_KEYWORD_RE = re.compile(r"(?i)\b(appendix|examples?)\b")


def is_revision_heading(
    line: str,
    overrides: set[str] | frozenset[str] = frozenset(),
) -> HeadingKind:
    """YES: heading and revision history. NO: heading, not revision.

    UNKNOWN: not a heading. Bold standalone lines count as headings.
    """
    stripped = line.lstrip()

    if HEADING_RE.match(stripped):
        for rx in _REVISION_HEADING_RES:
            if rx.match(stripped):
                return HeadingKind.YES
        if overrides:
            low = stripped.lower()
            for token in overrides:
                if token in low:
                    return HeadingKind.YES
        return HeadingKind.NO

    for rx in _BOLD_REVISION_RES:
        if rx.match(stripped):
            return HeadingKind.YES

    return HeadingKind.UNKNOWN


def is_reference_heading(line: str) -> HeadingKind:
    """YES: heading that starts a references/bibliography section."""
    stripped = line.lstrip()
    if not HEADING_RE.match(stripped):
        return HeadingKind.UNKNOWN
    for rx in _REFERENCE_HEADING_RES:
        if rx.match(stripped):
            return HeadingKind.YES
    return HeadingKind.NO


def is_acknowledgment_heading(line: str) -> HeadingKind:
    """YES: heading that starts an acknowledgment section."""
    stripped = line.lstrip()
    if not HEADING_RE.match(stripped):
        return HeadingKind.UNKNOWN
    if _ACKNOWLEDGMENT_HEADING_RE.match(stripped):
        return HeadingKind.YES
    return HeadingKind.NO


def is_appendix_heading_line(
    line: str,
    *,
    overrides: set[str] | frozenset[str] = frozenset(),
) -> bool:
    """True when *line* opens a non-prose appendix block."""
    if is_revision_heading(line, overrides) is HeadingKind.YES:
        return True
    if is_reference_heading(line) is HeadingKind.YES:
        return True
    if is_acknowledgment_heading(line) is HeadingKind.YES:
        return True
    m = HEADING_RE.match(line.lstrip())
    if m and _APPENDIX_KEYWORD_RE.search(m.group(2)):
        return True
    return False
