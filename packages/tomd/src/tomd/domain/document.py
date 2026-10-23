"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from dataclasses import dataclass, field
from enum import StrEnum

from tomd.domain.diagnostics import Diagnostics
from tomd.domain.elements import BlockElement
from tomd.domain.image import ExtractedImage
from tomd.domain.metadata import PaperMetadata


class SkipReason(StrEnum):
    """Closed set of early-exit reasons for paper conversion."""

    EMPTY_PDF = "empty pdf"
    SLIDE_DECK = "slide deck"
    STANDARDS_DRAFT = "standards draft"
    UNREADABLE = "unreadable"


@dataclass
class PaperDocument:
    """Intermediate Representation (IR) AST container for a WG21 paper."""

    paper_id: str
    metadata: PaperMetadata = field(default_factory=PaperMetadata)
    elements: list[BlockElement] = field(default_factory=list)
    body: str = ""
    images: list[ExtractedImage] = field(default_factory=list)
    is_skipped: bool = False
    skip_reason: SkipReason | None = None
    diagnostics: Diagnostics = field(default_factory=Diagnostics)
