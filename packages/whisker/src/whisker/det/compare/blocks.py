#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Parse Markdown into typed blocks for structural alignment.

Uses mistune's AST mode to tokenize the document, then maps each top-level
AST node to a typed Block with its raw source lines. This provides the
structural anchoring that makes side-by-side alignment meaningful: headings
lock to headings, code to code, tables to tables.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass

__all__ = [
    "Block",
    "BlockType",
    "parse_blocks",
]


class BlockType(enum.Enum):
    """Structural type of a Markdown block."""
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    CODE = "code"
    TABLE = "table"
    LIST = "list"
    QUOTE = "quote"
    THEMATIC_BREAK = "thematic_break"
    RAW = "raw"


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")
_TABLE_LINE_RE = re.compile(r"^\|.+\|")
_LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)]) ")
_QUOTE_RE = re.compile(r"^>\s?")
_HR_RE = re.compile(r"^(---|\*\*\*|___)\s*$")


@dataclass(frozen=True)
class Block:
    """A typed Markdown block with its raw source text and line span."""

    block_type: BlockType
    text: str
    start_line: int
    end_line: int
    level: int = 0  # heading level (1-6) or list indent depth

    @property
    def normalized(self) -> str:
        """Whitespace-collapsed text for alignment hashing."""
        return " ".join(self.text.split()).lower()


def parse_blocks(markdown: str) -> list[Block]:
    """Parse a Markdown string into a flat list of typed blocks.

    Uses a line-scanner approach for robustness: mistune's AST does not
    preserve exact line boundaries well enough for our source-faithful
    alignment, so we do a regex-based block segmentation that handles
    headings, fenced code, pipe tables, lists, blockquotes, and thematic
    breaks. Remaining contiguous non-blank lines become paragraphs.
    """
    lines = markdown.split("\n")
    blocks: list[Block] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        # Skip blank lines
        if not line.strip():
            i += 1
            continue

        # Thematic break
        if _HR_RE.match(line):
            blocks.append(Block(BlockType.THEMATIC_BREAK, line, i, i))
            i += 1
            continue

        # Heading
        m = _HEADING_RE.match(line)
        if m:
            blocks.append(Block(BlockType.HEADING, line, i, i, level=len(m.group(1))))
            i += 1
            continue

        # Fenced code block
        fm = _FENCE_RE.match(line)
        if fm:
            fence_marker = fm.group(1)[0]
            fence_len = len(fm.group(1))
            start = i
            i += 1
            while i < n:
                close = _FENCE_RE.match(lines[i])
                if close and close.group(1)[0] == fence_marker and len(close.group(1)) >= fence_len:
                    i += 1
                    break
                i += 1
            blocks.append(Block(BlockType.CODE, "\n".join(lines[start:i]), start, i - 1))
            continue

        # Table (pipe-delimited)
        if _TABLE_LINE_RE.match(line):
            start = i
            while i < n and _TABLE_LINE_RE.match(lines[i]):
                i += 1
            blocks.append(Block(BlockType.TABLE, "\n".join(lines[start:i]), start, i - 1))
            continue

        # Blockquote
        if _QUOTE_RE.match(line):
            start = i
            while i < n and (lines[i].strip() == "" or _QUOTE_RE.match(lines[i])):
                if lines[i].strip() == "":
                    if i + 1 < n and _QUOTE_RE.match(lines[i + 1]):
                        i += 1
                        continue
                    break
                i += 1
            blocks.append(Block(BlockType.QUOTE, "\n".join(lines[start:i]), start, i - 1))
            continue

        # List item
        lm = _LIST_RE.match(line)
        if lm:
            indent = len(lm.group(1))
            start = i
            i += 1
            while i < n:
                cl = lines[i]
                if not cl.strip():
                    if i + 1 < n and (lines[i + 1].startswith(" ") or _LIST_RE.match(lines[i + 1])):
                        i += 1
                        continue
                    break
                if _HEADING_RE.match(cl) or _FENCE_RE.match(cl) or _HR_RE.match(cl):
                    break
                if _LIST_RE.match(cl):
                    i += 1
                    continue
                if cl.startswith(" ") or cl.startswith("\t"):
                    i += 1
                    continue
                break
            blocks.append(Block(BlockType.LIST, "\n".join(lines[start:i]), start, i - 1, level=indent))
            continue

        # Default: paragraph (contiguous non-blank non-structural lines)
        start = i
        i += 1
        while i < n:
            cl = lines[i]
            if not cl.strip():
                break
            if _HEADING_RE.match(cl) or _FENCE_RE.match(cl) or _TABLE_LINE_RE.match(cl):
                break
            if _HR_RE.match(cl) or _QUOTE_RE.match(cl) or _LIST_RE.match(cl):
                break
            i += 1
        blocks.append(Block(BlockType.PARAGRAPH, "\n".join(lines[start:i]), start, i - 1))

    return blocks
