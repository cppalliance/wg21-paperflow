"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from dataclasses import dataclass, field
from enum import StrEnum

from tomd.domain.elements import BlockElement
from tomd.domain.image import ExtractedImage
from tomd.domain.metadata import PaperMetadata


class SkipReason(StrEnum):
    """Reason a paper was skipped during conversion."""

    EMPTY_CONTENT = "empty_content"
    SLIDE_DECK = "slide_deck"
    STANDARDS_DRAFT = "standards_draft"
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


@dataclass
class ConvertedPaper:
    """Final result container of paper conversion."""

    paper_id: str
    markdown: str
    metadata: PaperMetadata = field(default_factory=PaperMetadata)
    images: list[ExtractedImage] = field(default_factory=list)
    is_skipped: bool = False
    skip_reason: SkipReason | None = None

    @classmethod
    def from_document(cls, doc: PaperDocument, markdown: str) -> "ConvertedPaper":
        """Construct a ConvertedPaper from a PaperDocument and generated Markdown."""
        return cls(
            paper_id=doc.paper_id,
            markdown=markdown,
            metadata=doc.metadata,
            images=list(doc.images),
            is_skipped=doc.is_skipped,
            skip_reason=doc.skip_reason,
        )
