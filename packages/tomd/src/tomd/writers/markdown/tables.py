"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from __future__ import annotations

import re

from tomd.domain.table import (
    Cell,
    CellAlign,
    CodeCell,
    Table,
    TextCell,
)
from tomd.writers.markdown.spans import write_spans


def _format_code_span(code: str) -> str:
    """Format an inline code snippet escaping backticks."""
    if "`" not in code:
        return f"`{code}`"

    backtick_runs = re.findall(r"`+", code)
    max_run = max(len(r) for r in backtick_runs) if backtick_runs else 1
    fence = "`" * (max_run + 1)
    if code.startswith("`") or code.endswith("`"):
        return f"{fence} {code} {fence}"
    return f"{fence}{code}{fence}"


def _format_pipe_cell(cell: Cell, wording_tags: bool) -> str:
    """Format and escape a table cell for GFM pipe table rendering."""
    if isinstance(cell, TextCell):
        raw = write_spans(cell.spans, wording_tags=wording_tags)
    elif isinstance(cell, CodeCell):
        code_lines = cell.code.splitlines()
        raw = "<br>".join(
            _format_code_span(ln) if ln.strip() else ""
            for ln in code_lines
        )
    else:
        raw = cell.text

    # Replace newlines with <br> for pipe tables
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    raw = re.sub(r"\n+", "<br>", raw)

    # Escape unescaped pipe characters
    escaped = re.sub(r"(?<!\\)\|", r"\|", raw)
    return escaped.strip()


def write_table(table: Table, *, wording_tags: bool = True) -> str:
    """Format a Table AST node as a pure Markdown GFM pipe table."""
    if not table.headers and not table.rows:
        return ""

    num_cols = max(
        [len(table.headers)] + [len(r.cells) for r in table.rows],
        default=1,
    ) or 1

    aligns: list[CellAlign] = []
    for ci in range(num_cols):
        align = CellAlign.DEFAULT
        if ci < len(table.headers):
            align = table.headers[ci].align
        if align == CellAlign.DEFAULT:
            for row in table.rows:
                if ci < len(row.cells) and row.cells[ci].align != CellAlign.DEFAULT:
                    align = row.cells[ci].align
                    break
        aligns.append(align)

    header_cells = [_format_pipe_cell(c, wording_tags) for c in table.headers]
    while len(header_cells) < num_cols:
        header_cells.append("")
    header_line = "| " + " | ".join(header_cells) + " |"

    delim_cells: list[str] = []
    for align in aligns:
        if align == CellAlign.LEFT:
            delim_cells.append(":---")
        elif align == CellAlign.CENTER:
            delim_cells.append(":---:")
        elif align == CellAlign.RIGHT:
            delim_cells.append("---:")
        else:
            delim_cells.append("---")
    delim_line = "| " + " | ".join(delim_cells) + " |"

    row_lines: list[str] = []
    for row in table.rows:
        row_cells = [_format_pipe_cell(c, wording_tags) for c in row.cells]
        while len(row_cells) < num_cols:
            row_cells.append("")
        row_lines.append("| " + " | ".join(row_cells) + " |")

    lines = [header_line, delim_line] + row_lines
    result = "\n".join(lines)

    if table.caption:
        result = f"{result}\n\n*{table.caption}*"

    return result


__all__ = ["write_table"]
