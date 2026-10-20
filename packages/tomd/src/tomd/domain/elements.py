"""
Block-level AST nodes for WG21 paper documents.

Fenced code diffs are represented on ``CodeBlock`` via its optional ``lines``
field (per-line span sequences carrying ``UnderlineSpan`` / ``StrikethroughSpan``
role runs) rather than a separate element class, keeping one fenced-code block
type across the AST and writer.

Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from tomd.domain.span import Span, TextSpan

WordingRole = Literal["wording", "wording-add", "wording-remove"]


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
    """Section heading with depth level."""

    level: int
    spans: list[Span] = field(default_factory=list)

    @classmethod
    def from_text(cls, level: int, text: str) -> "Heading":
        return cls(level=level, spans=[TextSpan(text)])

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
    """Fenced multi-line code block; ``lines`` carries inline role spans for code diffs."""

    code: str = ""
    language: str = "cpp"
    title: str | None = None
    lines: list[list[Span]] | None = None

    @property
    def text(self) -> str:
        if self.lines is not None:
            return "\n".join("".join(s.text for s in line) for line in self.lines)
        return self.code


@dataclass
class ListItem:
    """Individual list item: an inline label plus optional continuation blocks."""

    spans: list[Span] = field(default_factory=list)
    children: list[BlockElement] = field(default_factory=list)
    marker: str | None = None

    @classmethod
    def from_text(cls, text: str) -> "ListItem":
        return cls(spans=[TextSpan(text)])

    @property
    def text(self) -> str:
        label = "".join(s.text for s in self.spans)
        parts = [label, *(child.text for child in self.children)]
        return "\n".join(part for part in parts if part)


@dataclass
class ListBlock(BlockElement):
    """Ordered or unordered list; ``start`` numbers the first ordered item."""

    items: list[ListItem] = field(default_factory=list)
    ordered: bool = False
    start: int = 1

    @property
    def text(self) -> str:
        return "\n".join(item.text for item in self.items)


@dataclass
class Blockquote(BlockElement):
    """Indented quotation or note block."""

    children: list[BlockElement] = field(default_factory=list)
    role: str | None = None

    @classmethod
    def from_text(cls, content: str, role: str | None = None) -> "Blockquote":
        return cls(children=[Paragraph.from_text(content)] if content else [], role=role)

    @property
    def text(self) -> str:
        return "\n".join(child.text for child in self.children if child.text)


@dataclass
class WordingBlock(BlockElement):
    """Proposed standard wording modification block."""

    role: WordingRole = "wording"
    children: list[BlockElement] = field(default_factory=list)

    @classmethod
    def from_text(cls, text: str, role: WordingRole = "wording") -> "WordingBlock":
        return cls(role=role, children=[Paragraph.from_text(text)] if text else [])

    @property
    def text(self) -> str:
        return "\n".join(child.text for child in self.children if child.text)


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
