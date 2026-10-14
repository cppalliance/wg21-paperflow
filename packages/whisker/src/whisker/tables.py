#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Shared table-parsing utilities for whisker facts and bench.

Pipe-table scanning (header + separator + body rows) is used by both
``facts.py`` (cell-neighbor comprehension checks) and ``bench.py`` (TEDS
scoring). HTML-table parsing handles tomd-emitted ``<table>`` blocks that
the pipe-only parser cannot see (Tony Tables, SPEC_TABLE, NB_BALLOT, any
cell with newlines). Both return the same grid shape: a list of rows, each
row a list of cell strings.

Pipe splitting is escape-aware (R6): unescaped ``|`` is the delimiter,
``\\|`` is a literal bar. HTML rowspan/colspan is denormalized by repeating
the spanned value into every covered slot; ``spans_declared`` on the
detailed HTML path records that a span was present so callers do not treat
a flattened grid as span-free.

golden-hook: the ``list[list[str]]`` grid remains the public adapter for
existing callers. Span occupancy is expanded into that grid rather than
dropped. A future golden-grid model can hang richer cell coordinates off
the detailed helpers below without a second parser.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import NamedTuple

__all__ = [
    "parse_code_table_groups",
    "parse_html_tables",
    "parse_pipe_tables",
    "split_pipe_cells",
]

_WS_RE = re.compile(r"\s+")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _is_escaped_at(text: str, index: int) -> bool:
    """True when ``text[index]`` is preceded by an odd number of backslashes."""
    count = 0
    pos = index - 1
    while pos >= 0 and text[pos] == "\\":
        count += 1
        pos -= 1
    return count % 2 == 1


def _unescape_cell(cell: str) -> str:
    """Decode GFM table escapes in a pipe-table cell.

    Only ``\\|`` becomes a literal bar and ``\\\\`` a literal backslash.
    A backslash before any other character is kept, so C/C++ sequences
    such as ``\\n`` and path fragments stay intact. A trailing unpaired
    backslash is kept, so round-trip of broken source stays honest.
    """
    out: list[str] = []
    escaped = False
    for char in cell:
        if escaped:
            if char in ("|", "\\"):
                out.append(char)
            else:
                out.append("\\")
                out.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        out.append(char)
    if escaped:
        out.append("\\")
    return "".join(out)


def split_pipe_cells(line: str) -> list[str]:
    """Split a pipe-table row into raw cell strings (whitespace-trimmed).

    Splits on unescaped ``|``, then unescapes ``\\|`` in each cell. Optional
    outer pipes are stripped only when they are themselves unescaped.
    """
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not _is_escaped_at(body, len(body) - 1):
        body = body[:-1]
    parts: list[str] = []
    start = 0
    for index, char in enumerate(body):
        if char == "|" and not _is_escaped_at(body, index):
            parts.append(_unescape_cell(body[start:index].strip()))
            start = index + 1
    parts.append(_unescape_cell(body[start:].strip()))
    return parts


class _PipeScan(NamedTuple):
    """One fence-aware pipe-table scan result, valid or malformed.

    ``raw_rows`` never includes the separator line. Valid tables set
    ``has_header`` and ``has_separator``. A table-shaped outer-pipe block
    with no separator is still a scan, so the contract adapter can fail
    R2 instead of dropping the block.

    ``start_line`` is the 0-based index of the header row in the source
    markdown. ``line_after`` is the first line index past the table body
    (exclusive upper bound), so the gap between consecutive scans is
    ``lines[scan_a.line_after : scan_b.start_line]``.
    """

    grid: list[list[str]]
    raw_rows: tuple[str, ...]
    has_header: bool
    has_separator: bool
    start_line: int
    line_after: int


def _has_outer_pipes(line: str) -> bool:
    """True when ``line`` is wrapped in unescaped opening and closing pipes."""
    body = line.strip()
    if len(body) < 2 or not body.startswith("|"):
        return False
    return body.endswith("|") and not _is_escaped_at(body, len(body) - 1)


def _is_valid_pipe_start(lines: list[str], index: int) -> bool:
    """True when ``lines[index]`` is a header immediately followed by a separator."""
    if index + 1 >= len(lines):
        return False
    if "|" not in lines[index] or "|" not in lines[index + 1]:
        return False
    return bool(_TABLE_SEP_RE.match(lines[index + 1]))


def _scan_pipe_blocks(md: str) -> list[_PipeScan]:
    """Fence-aware scan of valid pipe tables and malformed outer-pipe blocks.

    Public ``parse_pipe_tables`` keeps only scans with a separator. The
    contract adapter consumes every scan, including a contiguous outer-pipe
    run of at least two rows with no separator. Prose that merely contains
    ``|`` is not table-shaped and is ignored.
    """
    lines = md.splitlines()
    in_fence = False
    scans: list[_PipeScan] = []
    i = 0
    while i < len(lines):
        if _FENCE_RE.match(lines[i]):
            in_fence = not in_fence
            i += 1
            continue
        if in_fence:
            i += 1
            continue
        if _is_valid_pipe_start(lines, i):
            raw_rows = [lines[i]]
            rows = [split_pipe_cells(lines[i])]
            j = i + 2
            while j < len(lines) and "|" in lines[j] and lines[j].strip():
                raw_rows.append(lines[j])
                rows.append(split_pipe_cells(lines[j]))
                j += 1
            scans.append(_PipeScan(rows, tuple(raw_rows), True, True, i, j))
            i = j
            continue
        if _has_outer_pipes(lines[i]):
            run: list[str] = []
            j = i
            while (
                j < len(lines)
                and not _FENCE_RE.match(lines[j])
                and _has_outer_pipes(lines[j])
                and not _is_valid_pipe_start(lines, j)
                and not _TABLE_SEP_RE.match(lines[j])
                and lines[j].strip()
            ):
                run.append(lines[j])
                j += 1
            if len(run) >= 2:
                scans.append(
                    _PipeScan(
                        [split_pipe_cells(row) for row in run],
                        tuple(run),
                        True,
                        False,
                        i,
                        j,
                    )
                )
            i = j if j > i else i + 1
            continue
        i += 1
    return scans


def _pipe_tables_with_raw(md: str) -> list[tuple[list[list[str]], tuple[str, ...]]]:
    """Valid header+separator tables as grids plus raw header/body lines.

    The separator row is omitted from ``raw_rows`` so escape checks compare
    header width to body width. Public ``parse_pipe_tables`` is the grid adapter.
    """
    return [
        (scan.grid, scan.raw_rows)
        for scan in _scan_pipe_blocks(md)
        if scan.has_separator
    ]


def parse_pipe_tables(md: str) -> list[list[list[str]]]:
    """Return each markdown pipe table as a grid of raw cell strings.

    Header row + separator + body rows; fenced code is skipped so pipes
    inside code do not masquerade as tables. Deterministic.
    """
    return [grid for grid, _raw in _pipe_tables_with_raw(md)]


def _attr_span(attrs: list[tuple[str, str | None]], name: str) -> int:
    raw = dict(attrs).get(name)
    if raw is None:
        return 1
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 1
    return value if value >= 1 else 1


class _HTMLTableParser(HTMLParser):
    """HTML table parser that denormalizes rowspan/colspan into a grid."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[tuple[list[list[str]], bool]] = []
        self._in_table = False
        self._occupancy: dict[tuple[int, int], str] = {}
        self._row_index = -1
        self._col_index = 0
        self._current_cell: list[str] = []
        self._in_cell = False
        self._in_pre = 0
        self._preserve_ws = False
        self._pending_rowspan = 1
        self._pending_colspan = 1
        self._had_spans = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "table":
            if self._in_table:
                return
            self._in_table = True
            self._occupancy = {}
            self._row_index = -1
            self._had_spans = False
        elif tag == "tr" and self._in_table and not self._in_cell:
            self._row_index += 1
            self._col_index = 0
        elif tag in ("td", "th") and self._in_table:
            while (self._row_index, self._col_index) in self._occupancy:
                self._col_index += 1
            self._current_cell = []
            self._in_cell = True
            self._in_pre = 0
            self._preserve_ws = False
            self._pending_rowspan = _attr_span(attrs, "rowspan")
            self._pending_colspan = _attr_span(attrs, "colspan")
            if self._pending_rowspan > 1 or self._pending_colspan > 1:
                self._had_spans = True
        elif tag == "br" and self._in_cell:
            self._current_cell.append("\n" if (self._in_pre or self._preserve_ws) else " ")
        elif tag in ("pre", "code") and self._in_cell:
            self._in_pre += 1
            self._preserve_ws = True

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in ("pre", "code") and self._in_pre:
            self._in_pre -= 1
        elif tag in ("td", "th") and self._in_cell:
            if self._preserve_ws:
                text = "".join(self._current_cell).strip("\n")
            else:
                text = _WS_RE.sub(" ", "".join(self._current_cell)).strip()
            rowspan = self._pending_rowspan
            colspan = self._pending_colspan
            for delta_row in range(rowspan):
                for delta_col in range(colspan):
                    key = (self._row_index + delta_row, self._col_index + delta_col)
                    self._occupancy.setdefault(key, text)
            self._col_index += colspan
            self._in_cell = False
        elif tag == "table" and self._in_table:
            grid = self._occupancy_grid()
            if grid:
                self.tables.append((grid, self._had_spans))
            self._in_table = False
            self._occupancy = {}
            self._in_cell = False
            self._in_pre = 0

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._current_cell.append(data)

    def _occupancy_grid(self) -> list[list[str]]:
        if not self._occupancy:
            return []
        max_row = max(row for row, _col in self._occupancy)
        max_col = max(col for _row, col in self._occupancy)
        return [
            [self._occupancy.get((row, col), "") for col in range(max_col + 1)]
            for row in range(max_row + 1)
        ]


def _html_tables_with_spans(md: str) -> list[tuple[list[list[str]], bool]]:
    """Extract HTML tables as denormalized grids plus a had-spans flag."""
    if "<table" not in md.lower():
        return []
    parser = _HTMLTableParser()
    parser.feed(md)
    return parser.tables


def parse_html_tables(md: str) -> list[list[list[str]]]:
    """Extract grids from HTML ``<table>`` blocks embedded in markdown.

    tomd emits HTML tables for classes the pipe format cannot represent
    (CODE_COMPARISON, SPEC_TABLE, NB_BALLOT, cells with newlines). Rowspan
    and colspan are denormalized by repeating the cell value into every
    covered slot so neighbor facts see the spanned coordinates. Uses
    stdlib ``html.parser`` (no extra dependency). Deterministic.
    """
    return [grid for grid, _had_spans in _html_tables_with_spans(md)]


_MIXED_TABLE_MARKER = "<!-- tomd:mixed-table -->"
_ATX_HEADING_RE = re.compile(r"^#{1,6}(?:\s|$)")
_BOLD_ONLY_RE = re.compile(r"^\*\*(.+)\*\*$")
_ITALIC_ONLY_RE = re.compile(r"^\*([^*].*)\*$")
_FENCE_OPEN_RE = re.compile(r"^(`{3,}|~{3,})([^`~]*)$")


def _is_pipe_table_line(lines: list[str], index: int) -> bool:
    """True when ``lines[index]`` is a pipe-table row or its separator."""
    line = lines[index]
    if _TABLE_SEP_RE.match(line) or _has_outer_pipes(line):
        return True
    return _is_valid_pipe_start(lines, index)


def _fence_marker(line: str) -> str | None:
    match = _FENCE_OPEN_RE.match(line.strip())
    if match is None:
        return None
    return match.group(1)


def parse_code_table_groups(md: str) -> list[list[list[str]]]:
    """Parse labeled fence groups that start at ``<!-- tomd:mixed-table -->``.

    A group runs until the next marker, a pipe-table line, or an ATX heading.
    A line that is only ``**label**`` starts a body row. A line that is only
    ``*header*`` records the next column header. A fenced block fills the next
    cell of the current row, and a plain paragraph under that row is a text
    cell. The first grid row is ``""`` plus the column headers. Later rows are
    the label plus cells. An HTML table after the marker produces no grid, so
    it is not counted twice with ``parse_html_tables``.
    """
    lines = md.splitlines()
    groups: list[list[list[str]]] = []
    index = 0
    while index < len(lines):
        if lines[index].strip() != _MIXED_TABLE_MARKER:
            index += 1
            continue
        grid, index = _parse_one_code_group(lines, index + 1)
        if grid:
            groups.append(grid)
    return groups


def _group_ends(lines: list[str], index: int) -> bool:
    stripped = lines[index].strip()
    return (
        stripped == _MIXED_TABLE_MARKER
        or bool(_ATX_HEADING_RE.match(stripped))
        or _is_pipe_table_line(lines, index)
    )


def _parse_one_code_group(
    lines: list[str], start: int,
) -> tuple[list[list[str]], int]:
    headers: list[str] = []
    rows: list[list[str]] = []
    current: list[str] | None = None
    index = start
    while index < len(lines):
        if _group_ends(lines, index):
            break
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue
        bold = _BOLD_ONLY_RE.match(stripped)
        if bold:
            if current is not None:
                rows.append(current)
            current = [bold.group(1).strip()]
            index += 1
            continue
        italic = _ITALIC_ONLY_RE.match(stripped)
        if italic:
            headers.append(italic.group(1).strip())
            index += 1
            continue
        marker = _fence_marker(lines[index])
        if marker is not None:
            body: list[str] = []
            index += 1
            while index < len(lines) and lines[index].strip() != marker:
                body.append(lines[index])
                index += 1
            if index < len(lines) and lines[index].strip() == marker:
                index += 1
            if current is not None:
                current.append("\n".join(body))
            continue
        paragraph: list[str] = []
        while index < len(lines) and not _group_ends(lines, index):
            piece = lines[index].strip()
            if (
                not piece
                or _BOLD_ONLY_RE.match(piece)
                or _ITALIC_ONLY_RE.match(piece)
                or _fence_marker(lines[index]) is not None
            ):
                break
            paragraph.append(piece)
            index += 1
        if current is not None and paragraph:
            current.append("\n".join(paragraph))
    if current is not None:
        rows.append(current)
    if not headers and not rows:
        return [], index
    return [[""] + headers, *rows], index
