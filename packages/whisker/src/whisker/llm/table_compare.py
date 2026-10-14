#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Deterministic table-cell comparison between PDF source and candidate markdown.

Uses PyMuPDF find_tables() as the cell-grid oracle (already a whisker dependency).
Compares cell text content between source PDF tables and candidate markdown tables.
Library-pure: returns data, never persists.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from whisker.det.llm_readability.models import TableUnit
from whisker.tables import parse_html_tables, parse_pipe_tables

__all__ = [
    "GRID_EQUAL",
    "GRID_EXTRA_OR_MISSING_ROWS",
    "GRID_ROW0_MISMATCH",
    "GRID_UNRELIABLE",
    "SourceGrid",
    "TableCellDiff",
    "TableCompareResult",
    "TableGridMatch",
    "classify_grid_pair",
    "compare_pdf_tables",
    "extract_pdf_table_grids",
    "grid_match_for_unit",
    "grid_pairing_note",
    "grid_signal_for_unit",
    "parse_markdown_tables",
]

GRID_ROW0_MISMATCH = "row0_mismatch"
GRID_EXTRA_OR_MISSING_ROWS = "extra_or_missing_rows"
GRID_EQUAL = "equal"
GRID_UNRELIABLE = "unreliable"

# Constants
_NEWLINE_RE = re.compile(r"\s*\n\s*")
_WS_RE = re.compile(r"\s+")

# Pseudo-grid header rules (issue #425). On WG21 PDFs
# ``find_tables(strategy="text")`` returns one whole-page grid per page, so
# row 0 is whatever text sits at the top of the page: a prose line, a title
# block, a running header or a code line, chopped at column gaps. A real
# table header has at least two word-bearing cells, no word cut by a column
# boundary and no code punctuation. These rules only decide whether a grid
# may pair with a markdown unit (``grid_match_for_unit``); the grid stays in
# ``TableCompareResult.matches`` for the risk-signal consumers.
_MIN_ALPHABETIC_HEADER_CELLS = 2  # "} | |", "// For free functions | | | |", "21 | PROPOSAL | |"
_STRADDLE_MIN_OVERLAP_PT = 0.5  # a word must reach this far into two cells to count as cut
# "nothrow = see below;", "std::coroutine handle | <> h;", "const auto | a = ["
# (P3373R2 G6, the same-width code line the poll units fall back to once
# the title line is excluded). Asymmetric on purpose: "]" closes stable
# names at the end of real table rows (N5040 "54 | US 75-138 20.3.2.2
# [util.smartptr.shared] | Accepted"), and ")" ends "Time (ms)".
_CODE_TAIL_CHARS = frozenset("{};=[")
_CODE_COMMENT_PREFIX = "//"
# Title-block label on the joined row text: "Document | Number: | P4007R0".
# Word-bounded so "Document | Notes" does not match. Fleet 2026-09-18: no
# markdown table row in paperstore contains the label.
_TITLE_BLOCK_RE = re.compile(r"\bdocument (?:number|no\.?)(?![a-z])")

logger = logging.getLogger(__name__)
_INVISIBLE_CHARS = "\u200b\u200c\u200d\ufeff"  # zero-width marks PyMuPDF keeps at cell ends
_ALPHA_RE = re.compile(r"[^\W\d_]")


@dataclass
class TableCellDiff:
    """One cell-content mismatch between source and candidate."""
    page: int
    table_index: int
    row: int
    col: int
    source_text: str
    candidate_text: str
    diff_type: str  # "content_mismatch", "missing_cell", "extra_cell"


@dataclass
class SourceGrid:
    """One PyMuPDF grid: page (1-based), normalized cell rows, and whether
    row 0 looks like page layout rather than a table header (#425)."""
    page: int
    rows: list[list[str]]
    pseudo_header: bool = False


@dataclass
class TableGridMatch:
    """One source table paired to a candidate grid (or to nothing)."""
    table_index: int
    page: int
    source_header: tuple[str, ...]
    candidate_header: tuple[str, ...] | None
    source_row_count: int
    candidate_row_count: int
    row0_mismatch: bool
    extra_or_missing_rows: bool
    # Row 0 of the source grid failed the pseudo-header rules; such a match
    # never pairs with a markdown unit (``grid_match_for_unit``).
    source_pseudo: bool = False


@dataclass
class TableCompareResult:
    """Result of comparing all tables in a document."""
    total_source_tables: int
    total_candidate_tables: int
    matched_tables: int
    cell_diffs: list[TableCellDiff] = field(default_factory=list)
    grid_unreliable: bool = False  # True when source grid extraction failed/uncertain
    matches: list[TableGridMatch] = field(default_factory=list)

    @property
    def has_diffs(self) -> bool:
        return bool(self.cell_diffs)


def _normalize_cell_text(text: str) -> str:
    """Normalize cell text for comparison.

    Handles vertically wrapped text by joining newline-separated fragments:
    'S\\nF' -> 'SF' (the specific PR #286 case).
    Then collapses whitespace and strips.
    """
    # Join newline-wrapped text (critical for wrapped cells like S\nF -> SF)
    joined = _NEWLINE_RE.sub("", text)
    # Collapse remaining whitespace
    return _WS_RE.sub(" ", joined).strip()


def _is_pseudo_header(cells: list[str]) -> bool:
    """Lexical pseudo-header rules on normalized row-0 cells.

    Pseudo when fewer than ``_MIN_ALPHABETIC_HEADER_CELLS`` cells carry a
    letter (a lone ``}``, a code comment, a page number plus one word),
    when a cell ends in code punctuation / starts a ``//`` comment, or when
    the row reads as a title block (``Document Number:``).
    """
    alphabetic = sum(1 for cell in cells if _ALPHA_RE.search(cell))
    if alphabetic < _MIN_ALPHABETIC_HEADER_CELLS:
        return True
    row_text = _WS_RE.sub(" ", " ".join(cells)).lower()
    if _TITLE_BLOCK_RE.search(row_text):
        return True
    for cell in cells:
        text = cell.strip().strip(_INVISIBLE_CHARS).strip()
        if not text:
            continue
        if text.startswith(_CODE_COMMENT_PREFIX) or text[-1] in _CODE_TAIL_CHARS:
            return True
    return False


def _header_words_straddle(
    word_spans: list[tuple[float, float]],
    cell_spans: list[tuple[float, float] | None],
) -> bool:
    """True when any row-0 word reaches into two cells.

    ``strategy="text"`` derives column gaps from the whole page, so on a
    prose line the gaps fall inside words and the cell text is clipped
    (``Of Operati | on Stat``). A real header never has a word on a column
    boundary. Spans are ``(x0, x1)`` in PDF points; ``None`` is a missing
    cell.
    """
    for wx0, wx1 in word_spans:
        hits = 0
        for span in cell_spans:
            if span is None:
                continue
            if min(wx1, span[1]) - max(wx0, span[0]) > _STRADDLE_MIN_OVERLAP_PT:
                hits += 1
        if hits > 1:
            return True
    return False


def _row0_straddles(page: pymupdf.Page, table: object) -> bool:
    """Geometry check for ``_header_words_straddle`` on a PyMuPDF table."""
    try:
        row0 = table.rows[0]
        cell_spans = [
            (cell[0], cell[2]) if cell is not None else None for cell in row0.cells
        ]
        words = page.get_text("words", clip=pymupdf.Rect(row0.bbox))
    except Exception as exc:
        # PyMuPDF table objects vary by version; without geometry the
        # lexical rules alone decide and the grid is not called pseudo.
        logger.debug("row-0 straddle geometry unavailable: %s: %s", type(exc).__name__, exc)
        return False
    return _header_words_straddle([(w[0], w[2]) for w in words], cell_spans)


def extract_pdf_table_grids(
    source_path: Path,
) -> list[SourceGrid]:
    """Extract cell grids from PDF tables using PyMuPDF find_tables().

    Returns one ``SourceGrid`` per table (page number 1-based, rows of
    normalized cell strings, ``pseudo_header`` from ``_is_pseudo_header``
    plus the row-0 word-straddle geometry). Uses strategy="text" for
    borderless table support.

    The cell text has newlines from wrapped content joined (S\\nF -> SF).
    """
    try:
        doc = pymupdf.open(str(source_path))
    except Exception:
        return []

    grids: list[SourceGrid] = []
    try:
        for page_idx in range(doc.page_count):
            page = doc.load_page(page_idx)
            try:
                tables = page.find_tables(strategy="text")
            except Exception:
                continue
            for table in tables:
                try:
                    extracted = table.extract()
                except Exception:
                    continue
                if not extracted:
                    continue
                grid: list[list[str]] = []
                for row in extracted:
                    grid.append([
                        _normalize_cell_text(cell if cell is not None else "")
                        for cell in row
                    ])
                if grid:
                    pseudo = _is_pseudo_header(grid[0]) or _row0_straddles(page, table)
                    grids.append(SourceGrid(page_idx + 1, grid, pseudo))
    finally:
        doc.close()

    return grids


def parse_markdown_tables(markdown: str) -> list[list[list[str]]]:
    """Extract tables from markdown as cell grids.

    Delegates to the shared pipe and HTML parsers so source-compare, facts,
    and bench see the same cells, including escaped bars and denormalized
    HTML spans. Each cell is whitespace-normalized for PDF grid matching.
    """
    tables: list[list[list[str]]] = []
    for grid in parse_pipe_tables(markdown):
        tables.append([[_normalize_cell_text(cell) for cell in row] for row in grid])
    for grid in parse_html_tables(markdown):
        tables.append([[_normalize_cell_text(cell) for cell in row] for row in grid])
    return tables


def _match_tables(
    source_grids: list[SourceGrid],
    candidate_grids: list[list[list[str]]]
) -> list[tuple[SourceGrid, list[list[str]] | None]]:
    """Match source tables to candidate tables by column count and header similarity.

    Returns (source, candidate_grid_or_None) tuples.
    Simple sequential matching with column-count tiebreaking. Pseudo-header
    grids take part like any other grid: the risk-signal consumers of
    ``compare_pdf_tables`` see an unchanged pairing, and only the unit
    pairing (``grid_match_for_unit``) skips them.
    """
    matched: list[tuple[SourceGrid, list[list[str]] | None]] = []
    used_candidates: set[int] = set()

    for source in source_grids:
        source_grid = source.rows
        if not source_grid:
            continue
        source_cols = len(source_grid[0]) if source_grid else 0
        source_header = [_normalize_cell_text(c) for c in source_grid[0]] if source_grid else []

        best_idx: int | None = None
        best_score = -1

        for ci, cand_grid in enumerate(candidate_grids):
            if ci in used_candidates or not cand_grid:
                continue
            cand_cols = len(cand_grid[0])
            if cand_cols != source_cols:
                continue
            # Score by header cell overlap
            cand_header = [_normalize_cell_text(c) for c in cand_grid[0]]
            score = sum(
                1 for s, c in zip(source_header, cand_header)
                if s and c and (s.lower() == c.lower() or s.lower() in c.lower() or c.lower() in s.lower())
            )
            if score > best_score:
                best_score = score
                best_idx = ci

        if best_idx is not None:
            used_candidates.add(best_idx)
            matched.append((source, candidate_grids[best_idx]))
        else:
            matched.append((source, None))

    return matched


def _header_overlap(left: list[str], right: list[str]) -> int:
    return sum(
        1
        for src, cand in zip(left, right)
        if src
        and cand
        and (
            src.lower() == cand.lower()
            or src.lower() in cand.lower()
            or cand.lower() in src.lower()
        )
    )


def classify_grid_pair(
    source_grid: list[list[str]] | None,
    candidate_grid: list[list[str]] | None,
    *,
    unreliable: bool = False,
) -> str:
    """Classify one source/candidate grid pair without a PDF.

    T5 (wrong GFM header) is ``row0_mismatch``. T7 (leaked rows) is
    ``extra_or_missing_rows`` when row 0 still matches. T0 identical
    strings are ``equal``.
    """
    if unreliable or not source_grid or not candidate_grid:
        return GRID_UNRELIABLE
    src0 = [_normalize_cell_text(cell) for cell in source_grid[0]]
    cand0 = [_normalize_cell_text(cell) for cell in candidate_grid[0]]
    width = max(len(src0), len(cand0))
    row0_mismatch = any(
        (src0[i] if i < len(src0) else "").lower()
        != (cand0[i] if i < len(cand0) else "").lower()
        for i in range(width)
    )
    extra_or_missing = len(source_grid) != len(candidate_grid)
    if row0_mismatch:
        return GRID_ROW0_MISMATCH
    if extra_or_missing:
        return GRID_EXTRA_OR_MISSING_ROWS
    return GRID_EQUAL


def _match_from_grids(
    table_index: int,
    page: int,
    source_grid: list[list[str]],
    candidate_grid: list[list[str]] | None,
    *,
    pseudo: bool = False,
) -> TableGridMatch:
    source_header = tuple(
        _normalize_cell_text(cell) for cell in (source_grid[0] if source_grid else [])
    )
    if candidate_grid is None:
        return TableGridMatch(
            table_index=table_index,
            page=page,
            source_header=source_header,
            candidate_header=None,
            source_row_count=len(source_grid),
            candidate_row_count=0,
            row0_mismatch=True,
            extra_or_missing_rows=True,
            source_pseudo=pseudo,
        )
    candidate_header = tuple(
        _normalize_cell_text(cell) for cell in candidate_grid[0]
    )
    signal = classify_grid_pair(source_grid, candidate_grid)
    return TableGridMatch(
        table_index=table_index,
        page=page,
        source_header=source_header,
        candidate_header=candidate_header,
        source_row_count=len(source_grid),
        candidate_row_count=len(candidate_grid),
        row0_mismatch=signal == GRID_ROW0_MISMATCH,
        extra_or_missing_rows=signal == GRID_EXTRA_OR_MISSING_ROWS,
        source_pseudo=pseudo,
    )


def grid_match_for_unit(
    unit: TableUnit,
    result: TableCompareResult,
) -> TableGridMatch | None:
    """Pair a markdown unit to one ``TableGridMatch``, or None if unsure.

    Matches whose source grid found no candidate are never paired. Such a
    match carries no candidate information: ``_match_from_grids`` sets both
    mismatch flags on it to mean "no candidate", not a measured row-0
    difference, and its source header is whatever the extractor found. On
    WG21 PDFs ``find_tables(strategy="text")`` emits page-layout pseudo-grids
    (title block ``D | ocument Number:``, running header ``P3978R0 | 1
    Changelog``) that never pair with a markdown table; a one-letter
    substring hit on such a header was enough to stamp a det class as
    grid-confirmed and to quote the pseudo-header into the typed question.
    Fleet audit 2026-09-18: all 37 candidate-less pairings were pseudo-grids
    (#424).

    Matches whose source header failed the pseudo-header rules
    (``source_pseudo``) are never paired either. ``_match_tables`` pairs a
    pseudo-grid with a same-width markdown table at header score 0, and
    that match carries a measured ``row0_mismatch`` although the "source
    header" is a chopped prose line (P3373R2 ``Of Operati | on Stat``), a
    code line (P3373R2 ``const auto | a = [``) or a lone brace (P4003R0
    ``}``); it confirmed ``truncated_leak`` / ``header_is_data`` over the
    model's answer (#425). The score-0 pairing itself stays: a T5 wrong
    header has zero overlap with the source header by definition.
    """
    if result.grid_unreliable or not result.matches:
        return None
    unit_header = [
        _normalize_cell_text(cell) for cell in (unit.cells[0] if unit.cells else ())
    ]
    unit_cols = unit.column_count
    best: TableGridMatch | None = None
    best_score = -1
    for match in result.matches:
        if match.candidate_header is None or match.source_pseudo:
            continue
        cand = list(match.candidate_header)
        src = list(match.source_header)
        score = max(_header_overlap(unit_header, cand), _header_overlap(unit_header, src))
        if len(cand) == unit_cols:
            score += 1
        if score > best_score:
            best_score = score
            best = match
    if best is None or best_score <= 0:
        col_hits = [
            match
            for match in result.matches
            if match.candidate_header is not None
            and not match.source_pseudo
            and len(match.candidate_header) == unit_cols
        ]
        if len(col_hits) != 1:
            return None
        return col_hits[0]
    return best


def grid_pairing_note(unit: TableUnit, result: TableCompareResult | None) -> str:
    """Why ``grid_signal_for_unit`` is ``unreliable`` for this unit, or "".

    "no source compare" (no PDF compare ran), "no source grids"
    (``find_tables`` found nothing), "no pairing" with the count of
    candidate-bearing grids the pseudo-header rule kept out of the pairing
    (candidate-less grids are excluded by the #424 rule and not counted),
    or "" when a grid is paired.
    """
    if result is None:
        return "no source compare"
    if result.grid_unreliable or not result.matches:
        return "no source grids"
    if grid_match_for_unit(unit, result) is not None:
        return ""
    pseudo = sum(
        1 for m in result.matches
        if m.candidate_header is not None and m.source_pseudo
    )
    if pseudo:
        return f"no pairing, {pseudo} pseudo-grid{'s' if pseudo != 1 else ''} excluded"
    return "no pairing"


def grid_signal_for_unit(
    unit: TableUnit,
    result: TableCompareResult,
) -> str:
    """Map a markdown table unit onto a document-level grid compare.

    Pairing (``grid_match_for_unit``) uses header-token overlap against the
    candidate and source headers, then a unique column-count match, and
    skips candidate-less and pseudo-header source grids. No pair or an
    unreliable extract is ``unreliable``.
    """
    if result.grid_unreliable:
        return GRID_UNRELIABLE
    match = grid_match_for_unit(unit, result)
    if match is None:
        return GRID_UNRELIABLE
    if match.row0_mismatch:
        return GRID_ROW0_MISMATCH
    if match.extra_or_missing_rows:
        return GRID_EXTRA_OR_MISSING_ROWS
    return GRID_EQUAL


def compare_pdf_tables(
    source_path: Path,
    candidate_md: str,
) -> TableCompareResult:
    """Compare PDF source tables against candidate markdown tables.

    Uses PyMuPDF find_tables(strategy="text") for source cell grids and
    parses markdown pipe tables for candidate grids. Reports cell-level
    content mismatches.

    Returns a TableCompareResult. grid_unreliable is set when PyMuPDF
    could not extract tables (borderless/complex layout).
    """
    source_grids = extract_pdf_table_grids(source_path)
    candidate_grids = parse_markdown_tables(candidate_md)

    if not source_grids:
        return TableCompareResult(
            total_source_tables=0,
            total_candidate_tables=len(candidate_grids),
            matched_tables=0,
            grid_unreliable=True,
        )

    matches = _match_tables(source_grids, candidate_grids)
    cell_diffs: list[TableCellDiff] = []
    grid_matches: list[TableGridMatch] = []
    matched_count = 0

    for table_idx, (source, cand_grid) in enumerate(matches):
        page, source_grid = source.page, source.rows
        grid_matches.append(_match_from_grids(
            table_idx, page, source_grid, cand_grid, pseudo=source.pseudo_header,
        ))
        if cand_grid is None:
            # Entire table missing from candidate
            for ri, row in enumerate(source_grid):
                for ci, cell in enumerate(row):
                    if cell:
                        cell_diffs.append(TableCellDiff(
                            page=page,
                            table_index=table_idx,
                            row=ri,
                            col=ci,
                            source_text=cell,
                            candidate_text="",
                            diff_type="missing_cell",
                        ))
            continue

        matched_count += 1
        max_rows = max(len(source_grid), len(cand_grid))
        for ri in range(max_rows):
            source_row = source_grid[ri] if ri < len(source_grid) else []
            cand_row = cand_grid[ri] if ri < len(cand_grid) else []
            max_cols = max(len(source_row), len(cand_row))
            for ci in range(max_cols):
                source_cell = source_row[ci] if ci < len(source_row) else ""
                cand_cell = cand_row[ci] if ci < len(cand_row) else ""
                source_norm = _normalize_cell_text(source_cell)
                cand_norm = _normalize_cell_text(cand_cell)
                if source_norm.lower() != cand_norm.lower():
                    if not source_norm and cand_norm:
                        diff_type = "extra_cell"
                    elif source_norm and not cand_norm:
                        diff_type = "missing_cell"
                    else:
                        diff_type = "content_mismatch"
                    cell_diffs.append(TableCellDiff(
                        page=page,
                        table_index=table_idx,
                        row=ri,
                        col=ci,
                        source_text=source_norm,
                        candidate_text=cand_norm,
                        diff_type=diff_type,
                    ))

    return TableCompareResult(
        total_source_tables=len(source_grids),
        total_candidate_tables=len(candidate_grids),
        matched_tables=matched_count,
        cell_diffs=cell_diffs,
        matches=grid_matches,
    )
