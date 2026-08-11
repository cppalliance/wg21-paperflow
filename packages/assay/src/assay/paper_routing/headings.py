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
# "Strong" patterns are specific multi-word phrases (or unambiguous terms of
# art) that only ever belong to one section type per the spec table. "Weak"
# patterns are generic single-word tokens (bare "design", "API", "wording",
# "implementation") that can co-occur with another category's strong
# vocabulary in the same heading (e.g. "API and ABI Considerations"). All
# strong patterns are checked, across every category, before any weak
# pattern, so a specific term never loses to a generic one just because its
# category happens to be checked later. See test_heading_cross_category_*.
_DESIGN_STRONG_RE = re.compile(
    r"(?i)\b(design\s+decisions?|proposed\s+design|interface|proposal)\b"
)
_DESIGN_WEAK_RE = re.compile(r"(?i)\bdesign\b(?!\s+of\s+this\s+document)|\bAPI\b")
_WORDING_STRONG_RE = re.compile(
    r"(?i)\b(proposed\s+wording|standardese"
    r"|proposed\s+changes|modifications?\s+to\s+the\s+standard)\b"
)
_WORDING_WEAK_RE = re.compile(r"(?i)\bwording\b")
_IMPACT_RE = re.compile(
    r"(?i)\b(impact\s+on\s+the\s+standard|compatibility"
    r"|ABI\s+considerations?|feature\s+test\s+macro)\b"
)
_IMPLEMENTATION_STRONG_RE = re.compile(
    r"(?i)\b(implementation\s+experience|reference\s+implementation)\b"
)
_IMPLEMENTATION_WEAK_RE = re.compile(r"(?i)\bimplementation\b")
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

    Evaluated in two passes so that check order never lets a generic
    single-word token (bare "design", "API", "wording", "implementation")
    pre-empt a more specific phrase from a different category that happens
    to be checked later, e.g. "API and ABI Considerations" resolves to
    IMPACT (matches the specific "ABI Considerations" phrase) rather than
    DESIGN (matches the generic bare "API" token).
    """
    text = heading_text.strip()
    if not text:
        return SectionType.PREAMBLE

    if _WORDING_STRONG_RE.search(text):
        return SectionType.WORDING
    if _DESIGN_STRONG_RE.search(text):
        return SectionType.DESIGN
    if _MOTIVATION_RE.search(text):
        return SectionType.MOTIVATION
    if _IMPACT_RE.search(text):
        return SectionType.IMPACT
    if _IMPLEMENTATION_STRONG_RE.search(text):
        return SectionType.IMPLEMENTATION
    if _APPENDIX_RE.search(text):
        return SectionType.APPENDIX
    if _PREAMBLE_RE.search(text):
        return SectionType.PREAMBLE

    if _WORDING_WEAK_RE.search(text):
        return SectionType.WORDING
    if _DESIGN_WEAK_RE.search(text):
        return SectionType.DESIGN
    if _IMPLEMENTATION_WEAK_RE.search(text):
        return SectionType.IMPLEMENTATION

    return SectionType.PREAMBLE
