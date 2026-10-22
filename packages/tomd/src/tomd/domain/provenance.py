"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from dataclasses import dataclass
from enum import Enum


class Confidence(Enum):
    """Confidence level for structural classification decisions."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class Provenance:
    """Source page and confidence metadata for a block element."""

    page: int
    confidence: Confidence


__all__ = ["Confidence", "Provenance"]
