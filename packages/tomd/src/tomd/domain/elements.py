"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""
from dataclasses import dataclass, field
from enum import StrEnum

from tomd.domain.span import Span, TextSpan


class ElementKind(StrEnum):
    """Enumeration of block element kinds."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    CODE_BLOCK = "code_block"
    TABLE = "table"
    LIST = "list"
    BLOCKQUOTE = "blockquote"
    WORDING = "wording"
    THEMATIC_BREAK = "thematic_break"
    IMAGE = "image"
    UNCERTAIN = "uncertain"


@dataclass
class BlockElement:
    """Base class for all document-level block AST nodes."""

    @property
    def text(self) -> str:
        """Return recursive unformatted plain text of this block."""
        return ""


@dataclass
class Heading(BlockElement):
    """Section heading with depth level and optional anchor ID."""

    level: int
    spans: list[Span] = field(default_factory=list)
    id: str | None = None

    @classmethod
    def from_text(cls, level: int, text: str, id: str | None = None) -> "Heading":
        return cls(level=level, spans=[TextSpan(text)], id=id)

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans)


@dataclass
class Paragraph(BlockElement):
    """Prose paragraph containing inline text spans."""

    spans: list[Span] = field(default_factory=list)

    @classmethod
    def from_text(cls, text: str) -> "Paragraph":
        return cls(spans=[TextSpan(text)])

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans)


@dataclass
class CodeBlock(BlockElement):
    """Fenced multi-line code block."""

    code: str
    language: str = "cpp"
    title: str | None = None

    @property
    def text(self) -> str:
        return self.code


@dataclass
class ListItem:
    """Individual item in a list containing inline spans."""

    spans: list[Span] = field(default_factory=list)

    @classmethod
    def from_text(cls, text: str) -> "ListItem":
        return cls(spans=[TextSpan(text)])

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans)


@dataclass
class ListBlock(BlockElement):
    """Ordered or unordered list containing list items."""

    items: list[ListItem] = field(default_factory=list)
    ordered: bool = False

    @property
    def text(self) -> str:
        return "\n".join(item.text for item in self.items)


@dataclass
class Blockquote(BlockElement):
    """Indented quotation or note block."""

    content: str
    role: str | None = None

    @classmethod
    def from_text(cls, content: str, role: str | None = None) -> "Blockquote":
        return cls(content=content, role=role)

    @property
    def text(self) -> str:
        return self.content


@dataclass
class WordingBlock(BlockElement):
    """Proposed standard wording modification block."""

    role: str
    content: str = ""

    def __init__(self, role: str, text: str = "", content: str = "") -> None:
        self.role = role
        self.content = text if text else content

    @property
    def text(self) -> str:
        return self.content

    @classmethod
    def from_text(cls, text: str, role: str = "wording") -> "WordingBlock":
        return cls(role=role, text=text)


@dataclass
class ThematicBreak(BlockElement):
    """Horizontal divider / thematic break (---)."""

    pass


@dataclass
class ImageElement(BlockElement):
    """Block image reference with caption and alt text."""

    caption: str
    alt: str = ""
    stored_filename: str = ""

    @property
    def text(self) -> str:
        return self.caption or self.alt


@dataclass
class UncertainElement(BlockElement):
    """Flagged block with conversion uncertainty or reviewer prompt."""

    prompt: str
    raw_content: str = ""

    @property
    def text(self) -> str:
        return self.raw_content
