"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from __future__ import annotations

import re

from tomd.domain.elements import (
    BlockElement,
    Blockquote,
    CodeBlock,
    Heading,
    ImageElement,
    ListBlock,
    Paragraph,
    ThematicBreak,
    UncertainElement,
    WordingBlock,
)
from tomd.domain.table import Table
from tomd.writers.markdown.spans import write_spans
from tomd.writers.markdown.tables import write_table


def _format_code_block(element: CodeBlock) -> str:
    """Format a fenced code block choosing appropriate fence length and info string."""
    backtick_runs = re.findall(r"`+", element.code)
    max_run = max((len(r) for r in backtick_runs), default=2)
    fence = "`" * max(3, max_run + 1)

    lang = element.language or ""
    if element.title:
        info = f'{lang} title="{element.title}"' if lang else f'title="{element.title}"'
    else:
        info = lang

    return f"{fence}{info}\n{element.code}\n{fence}"


def _format_list_block(element: ListBlock) -> str:
    """Format an ordered or unordered list with aligned multiline continuations."""
    formatted_items: list[str] = []
    for i, item in enumerate(element.items, 1):
        item_text = write_spans(item.spans)
        prefix = f"{i}. " if element.ordered else "- "
        lines = item_text.split("\n")
        first = f"{prefix}{lines[0]}"
        indent = " " * len(prefix)
        rest = [f"{indent}{line}" if line else "" for line in lines[1:]]
        formatted_items.append("\n".join([first] + rest))
    return "\n".join(formatted_items)


def write_element(element: BlockElement) -> str:
    """Format a single BlockElement into Markdown text."""
    if isinstance(element, Heading):
        level = max(1, min(6, element.level))
        prefix = "#" * level
        return f"{prefix} {write_spans(element.spans)}"

    if isinstance(element, Paragraph):
        return write_spans(element.spans)

    if isinstance(element, CodeBlock):
        return _format_code_block(element)

    if isinstance(element, ListBlock):
        return _format_list_block(element)

    if isinstance(element, Table):
        return write_table(element)

    if isinstance(element, Blockquote):
        lines = element.content.split("\n")
        return "\n".join(f"> {line}" if line else ">" for line in lines)

    if isinstance(element, ThematicBreak):
        return "---"

    if isinstance(element, WordingBlock):
        return element.content

    # Markdown never carries image syntax (#408); the node stays in the AST for other writers.
    if isinstance(element, ImageElement):
        return ""

    if isinstance(element, UncertainElement):
        prompt_str = element.prompt.replace('"', '\\"')
        return f'<!-- tomd:uncertain prompt="{prompt_str}" -->\n{element.raw_content}'

    return getattr(element, "text", "")


__all__ = ["write_element"]
