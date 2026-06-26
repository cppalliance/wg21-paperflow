#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Domain types for the paper routing classifier."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SectionType(str, Enum):
    """WG21 paper section categories for section-aware aggregation."""

    PREAMBLE = "PREAMBLE"
    MOTIVATION = "MOTIVATION"
    DESIGN = "DESIGN"
    WORDING = "WORDING"
    IMPACT = "IMPACT"
    IMPLEMENTATION = "IMPLEMENTATION"
    APPENDIX = "APPENDIX"


@dataclass(frozen=True)
class Sentence:
    """One routable unit from Stage 1 with section context and hypothesis hits."""

    text: str
    section: SectionType
    index: int
    hypothesis_hits: frozenset[str]
