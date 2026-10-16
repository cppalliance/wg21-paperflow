"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from dataclasses import dataclass, field
from enum import StrEnum

from tomd.domain.elements import BlockElement
from tomd.domain.span import Span, TextSpan


class CellAlign(StrEnum):
    """Cell text alignment."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    DEFAULT = "default"


class TableStrategy(StrEnum):
    """Output rendering strategy for tables."""

    PIPE = "pipe"


@dataclass
class Cell:
    """Base table cell container."""

    align: CellAlign = CellAlign.DEFAULT
    width: str | None = None

    @property
    def text(self) -> str:
        """Return plain unformatted text of this cell."""
        return ""


@dataclass
class TextCell(Cell):
    """Table cell containing inline formatted text spans."""

    spans: list[Span] = field(default_factory=list)

    @classmethod
    def from_text(
        cls,
        text: str,
        align: CellAlign = CellAlign.DEFAULT,
        width: str | None = None,
    ) -> "TextCell":
        return cls(
            spans=[TextSpan(text)],
            align=align,
            width=width,
        )

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans)


@dataclass
class CodeCell(Cell):
    """Table cell containing a code block (e.g. Tony Tables)."""

    code: str = ""
    language: str = "cpp"

    @property
    def text(self) -> str:
        return self.code


TableCell = Cell  # Compatibility alias


@dataclass
class TableRow:
    """A row of cells in a table body."""

    cells: list[Cell] = field(default_factory=list)


@dataclass
class Table(BlockElement):
    """Table structure with explicit headers, rows, and rendering strategy."""

    headers: list[Cell] = field(default_factory=list)
    rows: list[TableRow] = field(default_factory=list)
    strategy: TableStrategy = TableStrategy.PIPE
    caption: str | None = None

    @property
    def text(self) -> str:
        parts: list[str] = []
        if self.headers:
            parts.append("\t".join(c.text for c in self.headers))
        for row in self.rows:
            parts.append("\t".join(c.text for c in row.cells))
        return "\n".join(parts)
