#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Stage 2 heading classifier: map heading text to SectionType.

Vocabulary from paper-routing-classifier.md Stage 2 table (lines 93-101).
"""

from __future__ import annotations

import re

from assay.paper_routing.types import SectionType

_MOTIVATION_RE = re.compile(
    r"(?i)\b(introduction|motivation|background|problem\s+statement)\b"
)
_DESIGN_RE = re.compile(
    r"(?i)\b(design\s+decisions?|proposed\s+design|interface|proposal)\b"
    r"|\bdesign\b(?!\s+of\s+this\s+document)"
    r"|\bAPI\b"
)
_WORDING_RE = re.compile(
    r"(?i)\b(proposed\s+wording|standardese"
    r"|proposed\s+changes|modifications?\s+to\s+the\s+standard)\b"
    r"|\bwording\b"
)
_IMPACT_RE = re.compile(
    r"(?i)\b(impact\s+on\s+the\s+standard|compatibility"
    r"|ABI\s+considerations?|feature\s+test\s+macro)\b"
)
_IMPLEMENTATION_RE = re.compile(
    r"(?i)\b(implementation\s+experience|reference\s+implementation)\b"
    r"|\bimplementation\b"
)
_APPENDIX_RE = re.compile(
    r"(?i)\b(acknowledg[e]?ments?|references|bibliography"
    r"|appendix|examples?|revision\s+history|change\s*log|document\s+history)\b"
)
_PREAMBLE_RE = re.compile(r"(?i)\babstract\b")


def classify_routing_section(heading_text: str) -> SectionType:
    """Classify stripped heading text into a paper section type.

    Receives the heading content without leading ``#`` markers (the
    caller in ``sections.py`` passes ``HEADING_RE.group(2).strip()``).
    Falls back to ``PREAMBLE`` when no pattern matches.
    """
    text = heading_text.strip()
    if not text:
        return SectionType.PREAMBLE

    if _WORDING_RE.search(text):
        return SectionType.WORDING
    if _DESIGN_RE.search(text):
        return SectionType.DESIGN
    if _MOTIVATION_RE.search(text):
        return SectionType.MOTIVATION
    if _IMPACT_RE.search(text):
        return SectionType.IMPACT
    if _IMPLEMENTATION_RE.search(text):
        return SectionType.IMPLEMENTATION
    if _APPENDIX_RE.search(text):
        return SectionType.APPENDIX
    if _PREAMBLE_RE.search(text):
        return SectionType.PREAMBLE

    return SectionType.PREAMBLE
