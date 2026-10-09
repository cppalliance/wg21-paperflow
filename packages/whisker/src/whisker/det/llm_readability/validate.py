#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Per-rule evaluation and aggregation for the table-readability contract.

This module owns three things and deliberately not a fourth.

1. The closed set of applicability predicates the contract declares. A rule can
   only be gated on a condition that exists in both ``rules.toml`` and this
   registry; a mismatch raises, because an inapplicable rule cannot fail and
   that is the most dangerous direction for a certification contract.
2. A check registry keyed by the ``check_id`` each rule declares. The
   deterministic candidate-side checks that need nothing but the supplied table
   units ship here; the source-compare, LLM and certification lanes register
   their own checks under the ids their rules already name. A rule whose method
   did not run, or whose check nobody registered, is ``not_evaluated`` and never
   ``pass``.
3. Aggregation into a report that keeps three verdicts apart:
   ``document_deterministic_ok`` (what candidate markdown alone establishes),
   ``model_certified`` (profile resolved, every method the profile demands
   executed, no applicable HARD rule failing or unevaluated), and ``vacuous``
   (no tables, so nothing was certified).

What it does not own is a table parser. Lanes hand in :class:`TableUnit` values
and leave every field they could not determine at ``None``, which makes the
depending check ``not_evaluated`` rather than passing it by omission.

R2 defect flags in this file are punch-list calibrated. Add a new helper for a
new defect class. Do not loosen, merge, or rename an existing heuristic when a
control or paper fixture goes red. See
``llm/calibration/tables/TABLE-CALIBRATION.md``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace

from whisker.det.llm_readability.contract import ContractSchemaError
from whisker.det.llm_readability.models import (
    FORMAT_HTML,
    FORMAT_PIPE,
    METHOD_DETERMINISTIC,
    METHODS,
    STATUS_FAIL,
    STATUS_NOT_APPLICABLE,
    STATUS_NOT_EVALUATED,
    STATUS_PASS,
    STATUS_REVIEW,
    STRENGTH_HARD,
    THRESHOLD_KIND_NUMERIC,
    THRESHOLD_KIND_TOKEN_SET,
    VERDICT_FAIL,
    VERDICT_INCOMPLETE,
    VERDICT_NOT_APPLICABLE,
    VERDICT_PASS,
    VERDICT_REVIEW,
    CheckOutcome,
    DocumentFacts as _ModelDocumentFacts,
    Finding,
    ResolvedContract,
    Rule,
    RuleResult,
    TableReadabilityReport,
    TableUnit,
    Threshold,
)
from whisker.tables import (  # noqa: PLC2701
    _html_tables_with_spans,
    _scan_pipe_blocks,
    parse_code_table_groups,
)

__all__ = [
    "APPLICABILITY_PREDICATES",
    "Check",
    "CheckContext",
    "DETERMINISTIC_CHECKS",
    "FINDINGS_PER_RULE_CAP",
    "REASON_CHECK_NOT_REGISTERED",
    "REASON_METHOD_NOT_EXECUTED",
    "count_unescaped_pipes",
    "default_registry",
    "document_facts",
    "evaluate",
    "table_units_from_markdown",
]

# Findings are evidence, not a log. One blank-cell rule on a 500-row table would
# otherwise bury the report; the cap keeps a report readable while the per-rule
# status still reflects every table.
FINDINGS_PER_RULE_CAP = 20

REASON_METHOD_NOT_EXECUTED = "method_not_executed"
REASON_CHECK_NOT_REGISTERED = "check_not_registered"
REASON_NO_UNITS = "no_table_units"
REASON_RAW_ROWS_UNAVAILABLE = "raw_rows_unavailable"
REASON_SEPARATOR_UNKNOWN = "header_or_separator_unknown"

# Fence-group tables are neither pipe nor html. TABLE_FORMATS stays the
# pipe|html pair (models.py is frozen); this string is only a unit tag.
FORMAT_CODE_GROUP = "code_group"

_TABLE_BLOCK_RE = re.compile(
    r"<table\b[^>]*>.*?</table>",
    re.IGNORECASE | re.DOTALL,
)
_INS_DEL_BLOCK_RE = re.compile(
    r"<(ins|del)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
_HTML_ENTITY_RE = re.compile(r"&(?:lt|gt|amp|quot);", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class DocumentFacts(_ModelDocumentFacts):
    """Applicability facts, plus the PDF-source inputs R14 reads.

    ``source_format`` and ``html_entity_count`` default at the end. The base
    dataclass in ``models.py`` is unchanged.
    """

    source_format: str = "unknown"
    html_entity_count: int = 0


def _count_table_html_entities(markdown: str) -> int:
    """Count ``&lt;`` ``&gt;`` ``&amp;`` ``&quot;`` inside ``table`` regions.

    Entities outside a table do not count. ``ins`` and ``del`` elements,
    tags and text, are removed before the count.
    """
    total = 0
    for match in _TABLE_BLOCK_RE.finditer(markdown):
        region = match.group(0)
        previous = None
        while previous != region:
            previous = region
            region = _INS_DEL_BLOCK_RE.sub("", region)
        total += len(_HTML_ENTITY_RE.findall(region))
    return total


# -- document facts ------------------------------------------------------------


def document_facts(
    units: Sequence[TableUnit],
    *,
    source_available: bool = False,
    chunking_evaluated: bool = False,
    source_format: str = "unknown",
    markdown: str | None = None,
) -> DocumentFacts:
    """Derive the applicability facts from the supplied table units.

    ``markdown`` is read only to count HTML entities inside tables.
    """
    return DocumentFacts(
        table_count=len(units),
        pipe_table_count=sum(1 for unit in units if unit.fmt == FORMAT_PIPE),
        html_table_count=sum(1 for unit in units if unit.fmt == FORMAT_HTML),
        max_columns=max((unit.column_count for unit in units), default=0),
        max_rows=max((unit.row_count for unit in units), default=0),
        max_cells=max((unit.cell_count for unit in units), default=0),
        tables_with_empty_cells=sum(1 for unit in units if _has_blank_cell(unit)),
        source_available=source_available,
        chunking_evaluated=chunking_evaluated,
        source_format=source_format,
        html_entity_count=_count_table_html_entities(markdown or ""),
    )


def _is_code_group_corner(unit: TableUnit, row_index: int, col_index: int) -> bool:
    """The fence-group corner is an empty label-column header, not a lost cell."""
    return unit.fmt == FORMAT_CODE_GROUP and row_index == 0 and col_index == 0


def _has_blank_cell(unit: TableUnit) -> bool:
    for row_index, row in enumerate(unit.cells):
        for col_index, cell in enumerate(row):
            if _is_code_group_corner(unit, row_index, col_index):
                continue
            if not cell.strip():
                return True
    return False


# -- applicability -------------------------------------------------------------

ApplicabilityPredicate = Callable[[DocumentFacts, Mapping[str, Threshold]], bool]


def _any_table(facts: DocumentFacts, _: Mapping[str, Threshold]) -> bool:
    return facts.table_count > 0


def _any_pipe_table(facts: DocumentFacts, _: Mapping[str, Threshold]) -> bool:
    return facts.pipe_table_count > 0


def _wide_table(facts: DocumentFacts, thresholds: Mapping[str, Threshold]) -> bool:
    return facts.max_columns > _numeric(thresholds, "wide_table_column_threshold")


def _long_table(facts: DocumentFacts, thresholds: Mapping[str, Threshold]) -> bool:
    return facts.max_rows >= _numeric(thresholds, "long_table_row_threshold")


def _table_with_empty_cell(facts: DocumentFacts, _: Mapping[str, Threshold]) -> bool:
    return facts.tables_with_empty_cells > 0


def _chunking_in_scope(facts: DocumentFacts, _: Mapping[str, Threshold]) -> bool:
    return facts.chunking_evaluated


def _pdf_source(facts: DocumentFacts, _: Mapping[str, Threshold]) -> bool:
    return facts.source_format == "pdf"


APPLICABILITY_PREDICATES: Mapping[str, ApplicabilityPredicate] = {
    "any_table": _any_table,
    "any_pipe_table": _any_pipe_table,
    "wide_table": _wide_table,
    "long_table": _long_table,
    "table_with_empty_cell": _table_with_empty_cell,
    "chunking_in_scope": _chunking_in_scope,
    "pdf_source": _pdf_source,
}


def _numeric(thresholds: Mapping[str, Threshold], name: str) -> float:
    threshold = thresholds.get(name)
    if threshold is None or threshold.kind != THRESHOLD_KIND_NUMERIC:
        raise ContractSchemaError(f"missing numeric threshold {name!r}")
    value = threshold.value
    if value is None:
        raise ContractSchemaError(f"numeric threshold {name!r} carries no value")
    return value


def _token_set(thresholds: Mapping[str, Threshold], name: str) -> tuple[str, ...]:
    threshold = thresholds.get(name)
    if threshold is None or threshold.kind != THRESHOLD_KIND_TOKEN_SET:
        raise ContractSchemaError(f"missing token_set threshold {name!r}")
    return tuple(threshold.values or ())


# -- check protocol ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CheckContext:
    """Everything a check may read. Checks are pure functions of this."""

    rule: Rule
    units: tuple[TableUnit, ...]
    facts: DocumentFacts
    thresholds: Mapping[str, Threshold]

    def numeric(self, name: str) -> float:
        return _numeric(self.thresholds, name)

    def token_set(self, name: str) -> tuple[str, ...]:
        return _token_set(self.thresholds, name)

    def pipe_units(self) -> tuple[TableUnit, ...]:
        return tuple(unit for unit in self.units if unit.fmt == FORMAT_PIPE)

    def html_units(self) -> tuple[TableUnit, ...]:
        return tuple(unit for unit in self.units if unit.fmt == FORMAT_HTML)


Check = Callable[[CheckContext], CheckOutcome]


def _aggregate(
    rule: Rule,
    *,
    findings: Sequence[Finding],
    unevaluated: Sequence[str],
    evaluated_any: bool,
) -> CheckOutcome:
    """Fold per-table outcomes into one rule outcome.

    A proven violation dominates: it is a fact about the document and no amount
    of unevaluable siblings makes it go away. Otherwise an unevaluable table
    dominates a clean one, because a clean subset is not a clean document.
    """
    if findings:
        return CheckOutcome(
            status=rule.failure_status,
            findings=tuple(findings[:FINDINGS_PER_RULE_CAP]),
        )
    if unevaluated:
        return CheckOutcome(status=STATUS_NOT_EVALUATED, reason=unevaluated[0])
    if not evaluated_any:
        return CheckOutcome(status=STATUS_NOT_EVALUATED, reason=REASON_NO_UNITS)
    return CheckOutcome(status=STATUS_PASS)


# -- deterministic candidate-side checks ---------------------------------------


def count_unescaped_pipes(line: str) -> int:
    """Count vertical bars in ``line`` that are not backslash-escaped."""
    count = 0
    escaped = False
    for char in line:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "|":
            count += 1
    return count


_LABEL_SHIFT_MAJORITY = 0.5

_NUMERIC_HEADER_RE = re.compile(r"^\d+$")
_SMALL_INT_RE = re.compile(r"^\*?\d{1,2}\*?$")
_DATE_HEADER_RE = re.compile(r"^\d{4}-\d{2}$")
_PAPER_CITE_RE = re.compile(r"\b(?:P\d{3,5}R\d+|N\d{4})\b", re.IGNORECASE)
_PAPER_CITE_STRIP_RE = re.compile(
    r"\[[PN]\d{3,5}R?\d*\]\([^)]+\)"
    r"|\[?\b(?:P\d{3,5}R\d+|N\d{4})\b\]?"
    r"|\[\d+\]"
    r"|\(\d{4}\)",
    re.IGNORECASE,
)


def _paper_cite_leftover_words(h: str) -> list[str] | None:
    """Words left in ``h`` after stripping paper cites, bracket refs and years.

    ``None`` when ``h`` carries no paper cite at all. URL scheme tokens are
    not words. Shared by the two cite predicates so they cannot drift.
    """
    if not _PAPER_CITE_RE.search(h):
        return None
    rest = _PAPER_CITE_STRIP_RE.sub(" ", h)
    return [w for w in re.findall(r"[A-Za-z0-9]+", rest) if w.lower() not in {"http", "https"}]


def _paper_cite_is_data_cell(h: str) -> bool:
    """True when a header cell is a leftover paper-cite row, not a column title.

    A cell that is only cites (plus years) is data (P4094R0 T1 ``P0285R0 (2016)``).
    A cite plus three or more leftover words is a smashed header (P4096R0 §5.1
    ``P2464R0 Predicted claim outcome``). A cite plus a short gloss
    (``P2300R10 for networking``) is a real column label.
    """
    words = _paper_cite_leftover_words(h)
    if words is None:
        return False
    return len(words) == 0 or len(words) >= 3


def _paper_cite_only_cell(h: str) -> bool:
    """True when a cell is cite(s) plus optional year and nothing else.

    The cite-only subset of ``_paper_cite_is_data_cell`` (P4094R0 T1
    ``P0285R0 (2016)``). The cite-plus-leftover-words smash is not included.
    """
    words = _paper_cite_leftover_words(h)
    return words is not None and len(words) == 0


# -- #411: label-like cells --------------------------------------------------
# A column label is short (<= 3 words), starts Title-case, carries no code
# span mixed into prose and no trailing sentence punctuation; or it is exactly
# one whitespace-free code span (``execution::task``; a code LINE with spaces
# such as ``submdspan(md, range_slice{0, 10})`` is a value, P3982R0 /
# P3400R3). Paper cites, bracket refs and years are
# stripped first. Used only to NARROW two R2 branches (back-to-back tables
# with distinct label headers, comparison-matrix headers whose column labels
# are cite+year). Never used to fire a flag.
_LABEL_LIKE_MAX_WORDS = 3
_CODE_SPAN_LABEL_RE = re.compile(r"^`[^`\s]+`$")
_EMPTY_PARENS_RE = re.compile(r"\(\s*\)")
_LABEL_TRAILING_PUNCT = (".", ",", ":", ";")


def _is_label_like_cell(cell: str) -> bool:
    """True when ``cell`` reads as a column label, not a data value.

    Quiet on P4096R0 HEAD 5.2 (``Property | Coroutine executor |
    execution::task ([P3552R3][14])``). Not label-like: ``de Wever, Mark``,
    ``NEN`` (N5040 attendance), ``Returns `p_->continuation()``` (P2583R0
    Boost.Capy), ``Property What throws Trigger condition`` (P4096R0 BASE).
    """
    text = _EMPTY_PARENS_RE.sub(" ", _PAPER_CITE_STRIP_RE.sub(" ", cell)).strip()
    if not text:
        return False
    if _CODE_SPAN_LABEL_RE.match(text):
        return True
    if "`" in text:
        return False
    words = text.split()
    if len(words) > _LABEL_LIKE_MAX_WORDS:
        return False
    if text.endswith(_LABEL_TRAILING_PUNCT):
        return False
    return bool(_TITLE_CASE_WORD_RE.match(words[0]))


def _is_label_header(cells: tuple[str, ...]) -> bool:
    """True when a header row reads as column labels, not a promoted data row.

    Every non-empty cell is label-like and at least one of them is Title-case
    prose (not a code span): a row made only of code spans
    (``| `cobalt` | `coroutine_handle<>` |``) is a data row of a library
    table. An all-empty header is never a label header.
    """
    non_empty = [c.strip() for c in cells if c.strip()]
    if not non_empty or not all(_is_label_like_cell(c) for c in non_empty):
        return False
    return any("`" not in c for c in non_empty)


def _is_comparison_matrix_header(unit: TableUnit) -> bool:
    """True when column 0 is a label column: header cell and every non-empty
    body cell in column 0 are label-like (P4096R0 5.4 ``Criterion`` /
    ``Error channel`` / ``Lifecycle``). Requires at least one body row.
    A cite in header column 0 (P4094R0 T1) is not a matrix.
    """
    if len(unit.cells) < 2 or not unit.cells[0]:
        return False
    if not _is_label_like_cell(unit.cells[0][0]):
        return False
    body_col0 = [row[0].strip() for row in unit.cells[1:] if row and row[0].strip()]
    if not body_col0:
        return False
    return all(_is_label_like_cell(c) for c in body_col0)


_ROW_ID_RE = re.compile(r"^[A-Z]\d{1,2}$")
_ROW_ID_IN_CELL_RE = re.compile(r"\b[A-Z]\d{1,2}\b")
_WRAP_BLEED_MIN_WORDS = 4
_WRAP_BLEED_SENTENCE_END_RE = re.compile(r"[.!?;]\s*$")

_ALLCAPS_IDENTIFIER_RE = re.compile(r"^[A-Z][A-Z0-9_]+$")
_TITLE_CASE_WORD_RE = re.compile(r"^[A-Z][a-z]")
_HEADER_DATA_MIN_PHRASE_WORDS = 4
_LABEL_PREFIXES = frozenset({"a", "an", "the", "this", "that", "in"})
_TRUNCATED_LEAK_LOOKAHEAD = 6
_ROW_MERGE_MIN_WORDS = 4
_WRAP_ORPHAN_RE = re.compile(
    r"(?:Appendix\s+[A-Z],\s*[A-Z]\b|,\s+[A-Z]\s*$)",
)
_HYPHEN_GLUE_RE = re.compile(
    r"[a-z](?:independent|friendly|threaded)\b",
)
_WORDING_PARA_NUM_RE = re.compile(r"^\d{1,2}$")
_WORDING_CLAUSE_MIN_ROWS = 2
_WORDING_CLAUSE_MIN_COLUMNS = 2
_WORDING_CLAUSE_MIN_NUMBERED_FRACTION = 1.0
_WORDING_CLAUSE_MIN_PROSE_WORDS = 8
_WORDING_CLAUSE_MIN_PROSE_ROWS = 2
_WORDING_CLAUSE_STABLE_NAME_RE = re.compile(r"\(\[[a-z][a-z0-9.]*\]\)")
_WORDING_CLAUSE_SENTENCE_RE = re.compile(r"[.!?]")

# -- C1: trailing-row leak (multi-column) --------------------------------------
# A pipe table whose last N data rows leaked into prose: the line
# immediately after the table has the same column count when split on
# whitespace runs that match tab-stops or bare separators. Extends
# ``_is_truncated_leak`` to >2-col tables beyond 2 body rows (N.6 in
# P4016R0: 4-col, 3 body rows, 4th row became "3 6-7 [768, 1000) ...").
_TRAILING_ROW_LEAK_MIN_COLS = 3
_TRAILING_ROW_LEAK_LOOKAHEAD = 4

# -- C2: heading-shattered table -----------------------------------------------
# Column headers rendered as consecutive empty-body ATX headings followed by
# a partial pipe table or prose data rows (N.14 in P4016R0:
# ``##### Property Guarantee / ##### Determinism / | Correctness | ... |``).
_HEADING_SHATTER_MIN_HEADINGS = 2
_HEADING_SHATTER_MAX_HEADING_TOKENS = 3

# -- C5: absorbed-prose / mega-row collapse ------------------------------------
# One row's total token count is an extreme outlier vs sibling rows: the
# converter collapsed multiple source rows into one (p4094r0 Assertion table;
# K.1 in P4016R0 where 4 demonstrators merged into one cell).
_ABSORBED_PROSE_TOKEN_RATIO = 3.0
_ABSORBED_PROSE_MIN_TOKENS = 40

_WORDING_CLAUSE_MARKERS = (
    "[*note",
    "[note:",
    "*— end*",
    "— end note",
    "models `",
    "a type `",
    "a type is",
    "types satisfying",
)
_SENTENCE_STARTERS = frozenset({
    "a", "an", "the", "this", "that", "these", "those", "we", "it",
    "in", "on", "for", "and", "but", "motion", "following",
})

_TRIVIAL_WORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "can",
    "do", "for", "from", "had", "has", "have", "he", "her", "his",
    "if", "in", "is", "it", "its", "may", "my", "no", "not", "of",
    "on", "or", "our", "out", "per", "she", "so", "than", "that",
    "the", "then", "they", "this", "to", "too", "up", "us", "was",
    "we", "were", "what", "when", "who", "will", "with", "yet", "you",
})


def _is_data_as_header(unit: TableUnit) -> bool:
    """True when every non-empty header cell is a bare integer and the body is blank.

    This catches the poll-split pattern where vote counts become the GFM
    header row and the actual body row is empty (``| | | | | |``).
    """
    if unit.fmt != FORMAT_PIPE or len(unit.cells) < 2:
        return False
    header = unit.cells[0]
    non_empty = [c.strip() for c in header if c.strip()]
    if not non_empty:
        return False
    if not all(_NUMERIC_HEADER_RE.match(c) for c in non_empty):
        return False
    for row in unit.cells[1:]:
        if any(c.strip() for c in row):
            return False
    return True


def _is_wrap_bleed(unit: TableUnit) -> bool:
    """True when a header cell is a sentence fragment continued by the first body cell.

    Detects the wording-table collapse where a sentence in the header
    spills into the body: the header cell ends mid-sentence (no terminal
    punctuation, enough words) and the first body cell starts lowercase,
    continuing the thought.
    """
    if unit.fmt != FORMAT_PIPE or len(unit.cells) < 2:
        return False
    header = unit.cells[0]
    body_row = unit.cells[1]
    for col_idx, hcell in enumerate(header):
        h = hcell.strip()
        if not h:
            continue
        if len(h.split()) < _WRAP_BLEED_MIN_WORDS:
            continue
        if _WRAP_BLEED_SENTENCE_END_RE.search(h):
            continue
        if col_idx >= len(body_row):
            continue
        b = body_row[col_idx].strip()
        if not b:
            continue
        if b[0].islower():
            return True
    return False


def _header_cell_is_data(h: str) -> bool:
    """True when a single header cell looks like a matrix value, not a label."""
    if h.endswith(",") or (h.count("(") > h.count(")")):
        return True
    if h.count('"') % 2 == 1:
        return True
    if _DATE_HEADER_RE.match(h):
        return True
    if _paper_cite_is_data_cell(h):
        return True
    if _ROW_ID_IN_CELL_RE.search(h) and len(h.split()) >= 2:
        return True
    if h[:1].islower() and len(h.split()) >= 2:
        return True
    if ":" in h and not h.endswith(":"):
        return True
    if _ALLCAPS_IDENTIFIER_RE.match(h):
        return True
    if h.startswith("`") and h.endswith("`"):
        return True
    if "::" in h and " " not in h:
        return True
    words = h.split()
    first = words[0].lower().rstrip(".,;:!?") if words else ""
    if first in _LABEL_PREFIXES:
        return False
    if len(words) >= _HEADER_DATA_MIN_PHRASE_WORDS:
        return True
    if len(words) >= 3 and "(" in h:
        return True
    return False


def _is_count_row_as_header(unit: TableUnit) -> bool:
    """True when a count-matrix data row was promoted to the GFM header.

    Fingerprint: first cell is a category label, at least three other header
    cells are small integers, and at least one body row has the same numeric
    shape. Catches ``Timeline | 5 | 4 | 1 | 0 | 0`` (P4047R0 §4).
    """
    if unit.fmt != FORMAT_PIPE or len(unit.cells) < 2 or unit.column_count < 4:
        return False
    header = [c.strip() for c in unit.cells[0]]
    if not header[0] or header[0][0].isdigit():
        return False
    if sum(1 for c in header[1:] if _SMALL_INT_RE.match(c)) < 3:
        return False
    for row in unit.cells[1:]:
        cells = [c.strip() for c in row]
        if sum(1 for c in cells[1:] if _SMALL_INT_RE.match(c)) >= 3:
            return True
    return False


def _is_header_is_data(unit: TableUnit) -> bool:
    """True when header cells look like data values, not column labels.

    Catches tables where non-label content (code, ALLCAPS identifiers, long
    phrases, truncated cells, colon-values) sits in the header. Truncated
    headers (trailing comma or unmatched paren) fire without a label-like
    body, because the body is often the rest of the smashed row.
    """
    if unit.fmt not in (FORMAT_PIPE, FORMAT_HTML) or len(unit.cells) < 2:
        return False
    header = unit.cells[0]
    body_row = unit.cells[1]
    non_empty = [(i, c.strip()) for i, c in enumerate(header) if c.strip()]
    if not non_empty:
        return False
    if all(_NUMERIC_HEADER_RE.match(c) for _, c in non_empty):
        return False
    if _is_count_row_as_header(unit):
        return True

    # #411: in a comparison matrix (label column 0) a cite-only header cell
    # such as ``[P2464R0][1] (2021)`` is the column label, not a leftover
    # data row, provided the body cells under it are not cite-only too (a
    # ``Topic | Paper`` table whose first row got promoted keeps cites in
    # the body column and still fires). The cite-plus-words smash (P4096R0
    # BASE 5.1) is unaffected, and a cite in column 0 (P4094R0 T1) never
    # forms a matrix.
    matrix = _is_comparison_matrix_header(unit)

    def _cite_label(col_idx: int, h: str) -> bool:
        if not (matrix and _paper_cite_only_cell(h)):
            return False
        return not any(
            col_idx < len(row) and _paper_cite_only_cell(row[col_idx].strip())
            for row in unit.cells[1:]
        )

    data_like = sum(
        1 for i, h in non_empty if not _cite_label(i, h) and _header_cell_is_data(h)
    )
    truncated = any(
        h.endswith(",")
        or h.count("(") > h.count(")")
        or h.count('"') % 2 == 1
        or _DATE_HEADER_RE.match(h)
        or (_paper_cite_is_data_cell(h) and not _cite_label(i, h))
        or (h[:1].islower() and len(h.split()) >= 2)
        for i, h in non_empty
    )
    if truncated:
        return True
    if data_like <= len(non_empty) / 2:
        return False

    label_like = 0
    for col_idx, _ in non_empty:
        if col_idx >= len(body_row):
            continue
        b = body_row[col_idx].strip()
        if not b or "`" in b:
            continue
        words = b.split()
        if len(words) <= 3 and _TITLE_CASE_WORD_RE.match(b):
            label_like += 1

    return label_like >= 1


def _wording_clause_row_is_prose(row: tuple[str, ...]) -> bool:
    """True when cells after the paragraph number carry wording prose."""
    rest = " ".join(cell.strip() for cell in row[1:] if cell.strip())
    if not rest:
        return False
    if len(rest.split()) < _WORDING_CLAUSE_MIN_PROSE_WORDS:
        return False
    lowered = rest.lower()
    if any(marker in lowered for marker in _WORDING_CLAUSE_MARKERS):
        return True
    if _WORDING_CLAUSE_STABLE_NAME_RE.search(rest):
        return True
    return bool(_WORDING_CLAUSE_SENTENCE_RE.search(rest))


def _is_wording_clause_table(unit: TableUnit) -> bool:
    """True when numbered WG21 wording paragraphs were rendered as a pipe table.

    Signature: first cell of every row is a bare 1-2 digit paragraph number
    and the remaining cells carry wording prose (sentences, Note markers,
    stable-name references). The GFM header is paragraph 1 promoted to a
    header row. Straw-poll and key-value tables do not match.
    """
    if unit.fmt != FORMAT_PIPE:
        return False
    if unit.row_count < _WORDING_CLAUSE_MIN_ROWS:
        return False
    if unit.column_count < _WORDING_CLAUSE_MIN_COLUMNS:
        return False
    numbered = 0
    prose_rows = 0
    for row in unit.cells:
        if not row:
            continue
        first = row[0].strip()
        if not _WORDING_PARA_NUM_RE.match(first):
            continue
        numbered += 1
        if _wording_clause_row_is_prose(row):
            prose_rows += 1
    if numbered / unit.row_count < _WORDING_CLAUSE_MIN_NUMBERED_FRACTION:
        return False
    return prose_rows >= _WORDING_CLAUSE_MIN_PROSE_ROWS


def _looks_like_row_stub(line: str) -> bool:
    """True when a prose line has the shape of a leaked table row, not a sentence."""
    if re.search(r"[.!?:]\s*$", line):
        return False
    words = line.split()
    if not (2 <= len(words) <= 8):
        return False
    first = words[0].rstrip(".,;:!?")
    if not first or first.lower() in _SENTENCE_STARTERS:
        return False
    if not first[0].isupper():
        return False
    return True


def _is_truncated_leak(
    unit: TableUnit,
    md_lines: list[str],
    line_after: int,
) -> bool:
    """True when a table leaks a leftover row into subsequent prose.

    The original path is a one-body-row pipe table whose next line is a
    Title-Case stub. A second path covers two-column tables with several
    body rows whose last row still leaked (P4047R0 §5): the following
    line has the same short-phrase shape as the first column.
    """
    if unit.fmt != FORMAT_PIPE:
        return False
    one_body = unit.row_count == 2
    two_col_list = unit.column_count == 2 and unit.row_count >= 3
    if not one_body and not two_col_list:
        return False

    header_tokens: set[str] = set()
    for cell in unit.cells[0]:
        for word in cell.strip().lower().split():
            if len(word) > 2 and word not in _TRIVIAL_WORDS:
                header_tokens.add(word)

    for i in range(line_after, min(line_after + _TRUNCATED_LEAK_LOOKAHEAD, len(md_lines))):
        line = md_lines[i].strip()
        if not line:
            continue
        if _HEADING_RE.match(line):
            return False
        if "|" in line:
            return False
        words = line.split()
        if not words:
            return False
        first = words[0].rstrip(".,;:!?")
        if first.lower() in _SENTENCE_STARTERS:
            return False
        if two_col_list:
            stubs = sum(
                1
                for row in unit.cells[1:]
                if row and _looks_like_row_stub(row[0].strip())
            )
            if stubs >= 2 and _looks_like_row_stub(line):
                return True
            return False
        stub_words = 0
        for w in words[:3]:
            clean = w.rstrip(".,;:!?")
            if _TITLE_CASE_WORD_RE.match(clean) and clean.lower() not in _TRIVIAL_WORDS:
                stub_words += 1
            else:
                break
        if stub_words >= 1 and (
            len(words) == 1 or not words[1].rstrip(".,;:!?").islower()
        ):
            return True
        if header_tokens:
            line_tokens = {w.lower().rstrip(".,;:!?") for w in words}
            if len(line_tokens & header_tokens) >= 2:
                return True
        return False

    return False


def _is_wrap_orphan(unit: TableUnit) -> bool:
    """True when a body cell holds a line-wrap leftover (``Appendix B, N``)."""
    if unit.fmt != FORMAT_PIPE or len(unit.cells) < 2:
        return False
    for row in unit.cells[1:]:
        for cell in row:
            if _WRAP_ORPHAN_RE.search(cell.strip()):
                return True
    return False


def _is_hyphen_glue(unit: TableUnit) -> bool:
    """True when a cell glues words that should be hyphenated."""
    if unit.fmt != FORMAT_PIPE:
        return False
    for row in unit.cells:
        for cell in row:
            if _HYPHEN_GLUE_RE.search(cell):
                return True
    return False


def _is_row_merge(unit: TableUnit) -> bool:
    """True when a body cell contains multiple entity names without row separator.

    Detects the pattern where two or more product names or vendor entries are
    concatenated in a single cell without commas, semicolons, or conjunctions
    to separate them (e.g. ``Intel oneMKL NVIDIA CUB``). This suggests the
    converter merged what should be distinct table rows.

    Uses ALLCAPS words (3+ alpha chars, all uppercase) as reliable anchor
    signals for brand/product names. Title-Case words alone are too common in
    natural language titles and descriptions to use as anchors.
    """
    if unit.fmt != FORMAT_PIPE or len(unit.cells) < 2:
        return False
    for row in unit.cells[1:]:
        for cell in row:
            text = cell.strip()
            if not text or len(text.split()) < _ROW_MERGE_MIN_WORDS:
                continue
            if "," in text or ";" in text or "/" in text:
                continue
            words = text.split()
            allcaps_pos: list[int] = []
            for i, w in enumerate(words):
                clean = w.rstrip(".,;:!?()")
                if len(clean) >= 3 and clean.isalpha() and clean.isupper():
                    allcaps_pos.append(i)
            if len(allcaps_pos) < 2:
                continue
            for j in range(1, len(allcaps_pos)):
                if allcaps_pos[j] - allcaps_pos[j - 1] <= 3:
                    return True
    return False


def _detect_label_shift(
    unit: TableUnit,
    rule_id: str,
) -> list[Finding]:
    """Detect a phantom-column label shift inside *unit*.

    A label shift is the signature left when a PDF-to-markdown converter
    inserts a spurious empty column: the header has an empty cell at some
    index *s*, yet body rows carry data there. Meanwhile an adjacent header
    cell names a real column whose body values are mostly empty because the
    data landed one position to the left.

    Returns one finding per detected shift pair (stub column, starved
    neighbour).
    """
    header = unit.cells[0]
    body = unit.cells[1:]
    if not body:
        return []
    width = len(header)
    n_body = len(body)

    col_fill: list[int] = []
    for col in range(width):
        col_fill.append(
            sum(
                1
                for row in body
                if col < len(row) and row[col].strip()
            )
        )

    findings: list[Finding] = []
    for stub_col in range(width):
        if header[stub_col].strip():
            continue
        if col_fill[stub_col] <= n_body * _LABEL_SHIFT_MAJORITY:
            continue
        for neighbour in (stub_col - 1, stub_col + 1):
            if neighbour < 0 or neighbour >= width:
                continue
            if not header[neighbour].strip():
                continue
            if col_fill[neighbour] > n_body * _LABEL_SHIFT_MAJORITY:
                continue
            findings.append(
                Finding(
                    rule_id=rule_id,
                    locus=unit.locus,
                    message=(
                        f"label shift: header column {stub_col + 1} is "
                        f"empty but body is {col_fill[stub_col]}/{n_body} "
                        f"filled, while adjacent header "
                        f"'{header[neighbour].strip()}' (column "
                        f"{neighbour + 1}) is {col_fill[neighbour]}/"
                        f"{n_body} filled"
                    ),
                    evidence=" | ".join(
                        c.strip() for c in header
                    ),
                )
            )
    return findings


def check_pipe_row_cell_deficit(ctx: CheckContext) -> CheckOutcome:
    """R1: no body row may carry fewer cells than the header row.

    Two signals are checked:

    1. **Cell-count deficit**: a body row with fewer cells than the header.
       A surplus belongs to R6 (unescaped delimiter), so the two rules never
       both fire on one cause.
    2. **Label shift**: an empty header cell whose body column is majority
       filled while an adjacent named header column is majority empty. This
       is the phantom-column signature left by a converter that inserts a
       spurious column, shifting values away from their header labels.
    """
    findings: list[Finding] = []
    unevaluated: list[str] = []
    evaluated_any = False
    for unit in ctx.pipe_units():
        if not unit.cells:
            unevaluated.append(REASON_NO_UNITS)
            continue
        evaluated_any = True
        width = len(unit.cells[0])
        for index, row in enumerate(unit.cells[1:], start=1):
            if len(row) < width:
                findings.append(
                    Finding(
                        rule_id=ctx.rule.id,
                        locus=f"{unit.locus} row {index + 1}",
                        message=(
                            f"row carries {len(row)} cells against a "
                            f"{width}-cell header, so its values are shifted"
                        ),
                        evidence=" | ".join(row),
                    )
                )
        findings.extend(_detect_label_shift(unit, ctx.rule.id))
    return _aggregate(
        ctx.rule,
        findings=findings,
        unevaluated=unevaluated,
        evaluated_any=evaluated_any,
    )


def check_pipe_header_separator(ctx: CheckContext) -> CheckOutcome:
    """R2: a pipe table needs a header row and an alignment separator row.

    Also flags continuation headers: when a pipe table immediately follows
    another (no heading in between) and its header row contains values that
    appear as body data in the preceding table, the header is actually a
    data row promoted by a page-break split. This is an R2 violation because
    the first row is data, not a header.
    """
    findings: list[Finding] = []
    unevaluated: list[str] = []
    evaluated_any = False
    for unit in ctx.pipe_units():
        if unit.has_header is None or unit.has_separator is None:
            unevaluated.append(REASON_SEPARATOR_UNKNOWN)
            continue
        evaluated_any = True
        missing = [
            name
            for name, present in (
                ("header row", unit.has_header),
                ("separator row", unit.has_separator),
            )
            if not present
        ]
        if missing:
            findings.append(
                Finding(
                    rule_id=ctx.rule.id,
                    locus=unit.locus,
                    message=f"missing {' and '.join(missing)}",
                )
            )
        if unit.continuation_of is not None:
            header_cells = " | ".join(
                c.strip() for c in unit.cells[0] if c.strip()
            )
            findings.append(
                Finding(
                    rule_id=ctx.rule.id,
                    locus=unit.locus,
                    message=(
                        f"continuation row used as header "
                        f"(follows pipe table {unit.continuation_of + 1})"
                    ),
                    evidence=header_cells,
                )
            )
        if unit.data_as_header:
            header_cells = " | ".join(
                c.strip() for c in unit.cells[0] if c.strip()
            )
            findings.append(
                Finding(
                    rule_id=ctx.rule.id,
                    locus=unit.locus,
                    message="data row used as header (all-numeric header, blank body)",
                    evidence=header_cells,
                )
            )
        if unit.wrap_bleed:
            header_cells = " | ".join(
                c.strip() for c in unit.cells[0] if c.strip()
            )
            findings.append(
                Finding(
                    rule_id=ctx.rule.id,
                    locus=unit.locus,
                    message="sentence fragment bleeds from header into body row",
                    evidence=header_cells,
                )
            )
        if unit.header_is_data:
            header_cells = " | ".join(
                c.strip() for c in unit.cells[0] if c.strip()
            )
            findings.append(
                Finding(
                    rule_id=ctx.rule.id,
                    locus=unit.locus,
                    message="header contains data values, not column labels",
                    evidence=header_cells,
                )
            )
        if unit.truncated_leak:
            header_cells = " | ".join(
                c.strip() for c in unit.cells[0] if c.strip()
            )
            findings.append(
                Finding(
                    rule_id=ctx.rule.id,
                    locus=unit.locus,
                    message=(
                        "table body appears truncated with rows "
                        "leaked into prose"
                    ),
                    evidence=header_cells,
                )
            )
        if unit.row_merge:
            merge_cell = ""
            for row in unit.cells[1:]:
                for cell in row:
                    if len(cell.strip().split()) >= _ROW_MERGE_MIN_WORDS:
                        merge_cell = cell.strip()[:80]
                        break
                if merge_cell:
                    break
            findings.append(
                Finding(
                    rule_id=ctx.rule.id,
                    locus=unit.locus,
                    message=(
                        "cell contains multiple row records "
                        "merged without separator"
                    ),
                    evidence=merge_cell,
                )
            )
        if unit.wrap_orphan:
            findings.append(
                Finding(
                    rule_id=ctx.rule.id,
                    locus=unit.locus,
                    message="cell contains a line-wrap orphan token",
                    evidence=" | ".join(
                        c.strip() for c in unit.cells[0] if c.strip()
                    ),
                )
            )
        if unit.hyphen_glue:
            glue_cell = ""
            for row in unit.cells:
                for cell in row:
                    if _HYPHEN_GLUE_RE.search(cell):
                        glue_cell = cell.strip()[:80]
                        break
                if glue_cell:
                    break
            findings.append(
                Finding(
                    rule_id=ctx.rule.id,
                    locus=unit.locus,
                    message="cell glues words that should be hyphenated",
                    evidence=glue_cell,
                )
            )
        if unit.flattened_prose:
            findings.append(
                Finding(
                    rule_id=ctx.rule.id,
                    locus=unit.locus,
                    message="table flattened to heading + prose rows",
                    evidence=" | ".join(
                        c.strip() for c in unit.cells[0] if c.strip()
                    ),
                )
            )
        if unit.wording_clause:
            findings.append(
                Finding(
                    rule_id=ctx.rule.id,
                    locus=unit.locus,
                    message="numbered wording paragraphs rendered as pipe table",
                    evidence=" | ".join(
                        c.strip() for c in unit.cells[0] if c.strip()
                    ),
                )
            )
        if unit.trailing_row_leak:
            findings.append(
                Finding(
                    rule_id=ctx.rule.id,
                    locus=unit.locus,
                    message=(
                        "table body row leaked into prose "
                        "after pipe block"
                    ),
                    evidence=" | ".join(
                        c.strip() for c in unit.cells[0] if c.strip()
                    ),
                )
            )
        if unit.absorbed_prose_row:
            merged_row = ""
            for row in unit.cells:
                total = sum(len(cell.split()) for cell in row)
                if total >= _ABSORBED_PROSE_MIN_TOKENS:
                    merged_row = " | ".join(
                        c.strip()[:40] for c in row if c.strip()
                    )[:120]
                    break
            findings.append(
                Finding(
                    rule_id=ctx.rule.id,
                    locus=unit.locus,
                    message=(
                        "body row has extreme token count "
                        "vs siblings (absorbed prose / mega-row)"
                    ),
                    evidence=merged_row,
                )
            )
    for unit in ctx.html_units():
        if unit.header_is_data:
            evaluated_any = True
            header_cells = " | ".join(
                c.strip() for c in unit.cells[0] if c.strip()
            )
            findings.append(
                Finding(
                    rule_id=ctx.rule.id,
                    locus=unit.locus,
                    message="header contains data values, not column labels",
                    evidence=header_cells,
                )
            )
    return _aggregate(
        ctx.rule,
        findings=findings,
        unevaluated=unevaluated,
        evaluated_any=evaluated_any,
    )


def check_pipe_escape_roundtrip(ctx: CheckContext) -> CheckOutcome:
    """R6: a literal bar inside a cell must be escaped.

    Checked on the raw row text. A cell splitter that ignores escapes would
    reproduce the phantom column this rule exists to forbid, so a unit that
    carries no raw rows is unevaluated rather than assumed clean.
    """
    findings: list[Finding] = []
    unevaluated: list[str] = []
    evaluated_any = False
    for unit in ctx.pipe_units():
        rows = unit.raw_rows
        if not rows:
            unevaluated.append(REASON_RAW_ROWS_UNAVAILABLE)
            continue
        evaluated_any = True
        width = count_unescaped_pipes(rows[0])
        for index, row in enumerate(rows[1:], start=1):
            found = count_unescaped_pipes(row)
            if found > width:
                findings.append(
                    Finding(
                        rule_id=ctx.rule.id,
                        locus=f"{unit.locus} row {index + 1}",
                        message=(
                            f"row carries {found} unescaped delimiters against "
                            f"{width} in the header, so a literal bar was left "
                            f"unescaped and invented a column"
                        ),
                        evidence=row.strip(),
                    )
                )
    return _aggregate(
        ctx.rule,
        findings=findings,
        unevaluated=unevaluated,
        evaluated_any=evaluated_any,
    )


def check_wide_table_column_budget(ctx: CheckContext) -> CheckOutcome:
    """R7: a table wider than the column budget must be split or restated."""
    budget = ctx.numeric("wide_table_column_threshold")
    findings: list[Finding] = []
    for unit in ctx.units:
        if unit.column_count > budget:
            findings.append(
                Finding(
                    rule_id=ctx.rule.id,
                    locus=unit.locus,
                    message=(
                        f"{unit.column_count} columns exceed the "
                        f"{budget:g}-column budget; split the columns or "
                        f"restate the rows as key/value pairs"
                    ),
                )
            )
    return _aggregate(
        ctx.rule,
        findings=findings,
        unevaluated=(),
        evaluated_any=bool(ctx.units),
    )


def check_long_table_header_repeat(ctx: CheckContext) -> CheckOutcome:
    """R8: a long table must repeat its header at the declared interval."""
    row_threshold = ctx.numeric("long_table_row_threshold")
    interval = ctx.numeric("header_repeat_row_interval")
    findings: list[Finding] = []
    evaluated_any = False
    for unit in ctx.units:
        if unit.row_count < row_threshold or not unit.cells:
            continue
        evaluated_any = True
        header = unit.cells[0]
        anchors = [0]
        anchors.extend(
            index for index, row in enumerate(unit.cells) if index > 0 and row == header
        )
        for position, anchor in enumerate(anchors):
            end = (
                anchors[position + 1] if position + 1 < len(anchors) else unit.row_count
            )
            body_rows = end - anchor - 1
            if body_rows > interval:
                findings.append(
                    Finding(
                        rule_id=ctx.rule.id,
                        locus=f"{unit.locus} rows {anchor + 2}-{end}",
                        message=(
                            f"{body_rows} body rows run without a repeated "
                            f"header, past the {interval:g}-row interval"
                        ),
                    )
                )
                break
    return _aggregate(
        ctx.rule,
        findings=findings,
        unevaluated=(),
        evaluated_any=evaluated_any,
    )


def check_empty_cell_sentinel(ctx: CheckContext) -> CheckOutcome:
    """R9: an intentionally empty cell must carry an explicit sentinel."""
    sentinels = ctx.token_set("empty_cell_sentinels")
    expected = ", ".join(sorted(sentinels))
    findings: list[Finding] = []
    for unit in ctx.units:
        for row_index, row in enumerate(unit.cells):
            for column_index, cell in enumerate(row):
                if cell.strip():
                    continue
                if _is_code_group_corner(unit, row_index, column_index):
                    continue
                findings.append(
                    Finding(
                        rule_id=ctx.rule.id,
                        locus=(
                            f"{unit.locus} row {row_index + 1} "
                            f"column {column_index + 1}"
                        ),
                        message=(
                            f"blank cell cannot be told apart from lost "
                            f"content; expected one of {expected}"
                        ),
                    )
                )
    return _aggregate(
        ctx.rule,
        findings=findings,
        unevaluated=(),
        evaluated_any=bool(ctx.units),
    )


def check_html_table_in_markdown(ctx: CheckContext) -> CheckOutcome:
    """R14: a PDF source must not arrive as a raw HTML table.

    Fires only when applicability is ``pdf_source``. An HTML unit, or HTML
    entities standing in for code inside a table, fails the rule. Findings
    name the table index.
    """
    findings: list[Finding] = []
    for unit in ctx.units:
        if unit.fmt != FORMAT_HTML:
            continue
        findings.append(
            Finding(
                rule_id=ctx.rule.id,
                locus=unit.locus,
                message=f"raw HTML table index {unit.index}",
            )
        )
    if ctx.facts.html_entity_count > 0:
        indexes = [unit.index for unit in ctx.units if unit.fmt == FORMAT_HTML]
        if not indexes:
            indexes = [0]
        for index in indexes:
            findings.append(
                Finding(
                    rule_id=ctx.rule.id,
                    locus=f"table index {index}",
                    message=(
                        f"HTML entities standing in for code in table index {index}"
                    ),
                )
            )
    return _aggregate(
        ctx.rule,
        findings=findings,
        unevaluated=(),
        evaluated_any=True,
    )


# The candidate-side checks that need nothing but the supplied units. Keys are
# the `check_id` values declared in rules.toml. The remaining rules name check
# ids that the source-compare (R3, R4, R5, R10, R11), chunking (R12) and
# certification (R13) lanes register; until they do, those rules evaluate to
# `not_evaluated`, which is the honest answer and blocks certification.
DETERMINISTIC_CHECKS: Mapping[str, Check] = {
    "pipe_row_cell_deficit": check_pipe_row_cell_deficit,
    "pipe_header_separator": check_pipe_header_separator,
    "pipe_escape_roundtrip": check_pipe_escape_roundtrip,
    "wide_table_column_budget": check_wide_table_column_budget,
    "long_table_header_repeat": check_long_table_header_repeat,
    "empty_cell_sentinel": check_empty_cell_sentinel,
    "html_table_in_markdown": check_html_table_in_markdown,
}


def default_registry() -> dict[str, Check]:
    """Return a mutable copy of the deterministic check registry."""
    return dict(DETERMINISTIC_CHECKS)


# -- flattened-prose detection --------------------------------------------------

_FLAT_HEADING_RE = re.compile(r"^#{3,6}\s+(.+)$")
_FLAT_CHAPTER_PREFIX_RE = re.compile(r"^\d+(\.\d+)*\s")
_FLAT_SENTENCE_END_RE = re.compile(r"[.!?:]\s*$")
_FLAT_MIN_HEADER_TOKENS = 3
_FLAT_MIN_DATA_ROWS = 2
_FLAT_COLUMN_LABELS = frozenset({
    "assertion", "source", "evidence", "question", "outcome",
    "prediction", "date", "category", "confirmed", "unconfirmed",
    "pending", "partial", "criterion",
})
_TRAIL_ROW_LABELS = frozenset({
    "error channel", "lifecycle", "generic composition", "deployed networking",
})
_YEAR_LABEL_HEADING_RE = re.compile(r"^#{2,6}\s+(\d{4})\s+(.+)$")


def _is_trailing_row_leak(
    unit: TableUnit,
    md_lines: list[str],
    line_after: int,
) -> bool:
    """True when a multi-column pipe table leaks its last row(s) into prose.

    Extends ``_is_truncated_leak`` to tables with >= 3 columns and more than
    2 body rows (the existing helper covers 1-body-row and 2-col-list cases).
    The leaked line must start with a value that looks like a continuation of
    the first column (a bare number, a range, an ordinal) and have at least
    as many whitespace-separated segments as the table has columns.
    """
    if unit.fmt != FORMAT_PIPE:
        return False
    if unit.column_count < _TRAILING_ROW_LEAK_MIN_COLS:
        return False
    if unit.row_count < 3:
        return False
    num_cols = unit.column_count

    col0_values = [
        row[0].strip() for row in unit.cells[1:] if row and row[0].strip()
    ]
    if not col0_values:
        return False

    for i in range(line_after, min(line_after + _TRAILING_ROW_LEAK_LOOKAHEAD,
                                   len(md_lines))):
        line = md_lines[i].strip()
        if not line:
            continue
        if _HEADING_RE.match(md_lines[i]):
            return False
        if line.startswith("|"):
            return False

        segments = line.split()
        if len(segments) < num_cols:
            return False
        first = segments[0]
        last_col0 = col0_values[-1]
        try:
            last_num = int(last_col0)
            first_num = int(first)
            if first_num == last_num + 1:
                return True
        except ValueError:
            pass
        if first[0].isdigit() and last_col0[0].isdigit():
            return True
        return False
    return False


def _is_heading_shattered_table(
    md_lines: list[str],
) -> list[TableUnit]:
    """Find tables whose column headers became consecutive empty-body headings.

    Pattern (N.14 in P4016R0)::

        ##### Property Guarantee
        ##### Determinism
        Expression-identical ...
        | Correctness | ... |

    Two or more consecutive headings with <= 3 tokens each and no body text
    between them, followed within a few lines by either a pipe table or
    prose data rows, signals that the source table's header was exploded
    into one heading per column.
    """
    results: list[TableUnit] = []
    i = 0
    while i < len(md_lines):
        m = _FLAT_HEADING_RE.match(md_lines[i])
        if not m:
            i += 1
            continue
        heading_text = m.group(1).strip()
        tokens = heading_text.split()
        if len(tokens) > _HEADING_SHATTER_MAX_HEADING_TOKENS:
            i += 1
            continue
        if _FLAT_CHAPTER_PREFIX_RE.match(heading_text):
            i += 1
            continue

        headings: list[str] = [heading_text]
        j = i + 1
        while j < len(md_lines):
            raw = md_lines[j].strip()
            if not raw:
                j += 1
                continue
            hm = _FLAT_HEADING_RE.match(md_lines[j])
            if hm:
                ht = hm.group(1).strip()
                htoks = ht.split()
                if len(htoks) <= _HEADING_SHATTER_MAX_HEADING_TOKENS and not _FLAT_CHAPTER_PREFIX_RE.match(ht):
                    headings.append(ht)
                    j += 1
                    continue
            break

        if len(headings) < _HEADING_SHATTER_MIN_HEADINGS:
            i += 1
            continue

        has_following_data = False
        k = j
        scan_limit = min(k + 6, len(md_lines))
        while k < scan_limit:
            raw = md_lines[k].strip()
            if not raw:
                k += 1
                continue
            if raw.startswith("|"):
                has_following_data = True
                break
            if not raw.startswith("#") and len(raw.split()) >= 2:
                has_following_data = True
                break
            k += 1

        if has_following_data:
            header = tuple(headings)
            cells = (header,)
            results.append(
                TableUnit(
                    index=0,
                    fmt=FORMAT_PIPE,
                    cells=cells,
                    raw_rows=tuple(
                        "| " + " | ".join(row) + " |" for row in cells
                    ),
                    has_header=True,
                    has_separator=True,
                    flattened_prose=True,
                )
            )
        i = j if j > i + 1 else i + 1
    return results


def _is_absorbed_prose_row(unit: TableUnit) -> bool:
    """True when a row has extreme token count vs its siblings.

    Detects a converter collapsing multiple source rows into one pipe-table
    row, or absorbing prose into a table cell. The signature is one row whose
    total token count is >= ``_ABSORBED_PROSE_TOKEN_RATIO`` times the median
    of its *other* siblings, with at least ``_ABSORBED_PROSE_MIN_TOKENS``
    tokens. Using the median-excluding-self prevents a single mega-row from
    inflating its own baseline in two-body-row tables.

    The header row is included: on K.1 / p4094 the collapsed mega-row is
    often promoted to the GFM header (``header_is_data``), so a body-only
    scan would miss it.
    """
    if unit.fmt != FORMAT_PIPE or len(unit.cells) < 3:
        return False
    row_tokens: list[int] = []
    for row in unit.cells:
        count = sum(len(cell.split()) for cell in row)
        row_tokens.append(count)
    if len(row_tokens) < 2:
        return False
    for idx, count in enumerate(row_tokens):
        if count < _ABSORBED_PROSE_MIN_TOKENS:
            continue
        others = sorted(row_tokens[:idx] + row_tokens[idx + 1:])
        median_other = others[len(others) // 2]
        if median_other < 1:
            continue
        if count >= median_other * _ABSORBED_PROSE_TOKEN_RATIO:
            return True
    return False


def _detect_flattened_prose(md_lines: list[str]) -> list[TableUnit]:
    """Find ATX headings that are actually flattened table headers + data rows.

    Pattern: ``##### Label1 Label2 Label3`` followed by 2+ non-pipe, non-heading
    lines that start with a short capitalised label and have no sentence-ending
    punctuation. The heading itself must not have a chapter number prefix
    (``7.1 The Cost``), and needs at least 3 tokens that all look like column
    headers (Title-Case or ALLCAPS, no sentence punctuation).

    When every heading token is a known column label (P4094R0
    ``### Assertion Source Evidence``), sentence endings are allowed and one
    following line is enough. That branch is additive; the B.1 scanner stays
    strict for other headings.
    """
    results: list[TableUnit] = []
    i = 0
    while i < len(md_lines):
        m = _FLAT_HEADING_RE.match(md_lines[i])
        if not m:
            i += 1
            continue
        heading_text = m.group(1).strip()
        if _FLAT_CHAPTER_PREFIX_RE.match(heading_text):
            i += 1
            continue
        tokens = heading_text.split()
        if len(tokens) < _FLAT_MIN_HEADER_TOKENS:
            i += 1
            continue
        label_tokens = [t.rstrip("/,") for t in tokens if t.rstrip("/,")]
        all_labels = bool(label_tokens) and all(
            t.lower() in _FLAT_COLUMN_LABELS for t in label_tokens
        )
        if not all_labels and not all(
            t[0].isupper() and not _FLAT_SENTENCE_END_RE.search(t)
            for t in tokens
        ):
            i += 1
            continue

        data_rows: list[str] = []
        j = i + 1
        while j < len(md_lines):
            line = md_lines[j].strip()
            if not line:
                j += 1
                continue
            if _FLAT_HEADING_RE.match(line) or line.startswith("|"):
                break
            if all_labels:
                data_rows.append(line)
                j += 1
                continue
            if _FLAT_SENTENCE_END_RE.search(line):
                break
            words = line.split()
            if not words or not words[0][0].isupper():
                break
            if words[0].lower().rstrip(".,;:!?") in _SENTENCE_STARTERS:
                break
            data_rows.append(line)
            j += 1

        min_rows = 1 if all_labels else _FLAT_MIN_DATA_ROWS
        if len(data_rows) >= min_rows:
            header_cells = tuple(tokens)
            body_cells = []
            for row_text in data_rows:
                parts = row_text.split(None, len(tokens) - 1)
                while len(parts) < len(tokens):
                    parts.append("")
                body_cells.append(tuple(parts))
            cells = (header_cells,) + tuple(body_cells)
            unit = TableUnit(
                index=0,
                fmt=FORMAT_PIPE,
                cells=cells,
                raw_rows=tuple(
                    "| " + " | ".join(row) + " |" for row in cells
                ),
                has_header=True,
                has_separator=True,
                flattened_prose=True,
            )
            results.append(unit)
        i = j if j > i + 1 else i + 1
    return results


def _flat_unit(cells: tuple[tuple[str, ...], ...]) -> TableUnit:
    """Synthetic pipe unit for a flattened-prose table (R2 + dumps)."""
    return TableUnit(
        index=0,
        fmt=FORMAT_PIPE,
        cells=cells,
        raw_rows=tuple("| " + " | ".join(row) + " |" for row in cells),
        has_header=True,
        has_separator=True,
        flattened_prose=True,
    )


def _is_smashed_label_header(header_cells: tuple[str, ...]) -> bool:
    """True when a header-is-data cell starts with a column label plus extra text."""
    if not header_cells:
        return False
    tokens = header_cells[0].split()
    if len(tokens) < 2:
        return False
    return tokens[0].lower().rstrip("?:,") in _FLAT_COLUMN_LABELS


def _leading_flatten_before_pipe(
    md_lines: list[str],
    start_line: int,
    header_cells: tuple[str, ...],
) -> TableUnit | None:
    """Prose fragments immediately before a smashed-label pipe (P4094R0 §5.7)."""
    if start_line <= 0 or not _is_smashed_label_header(header_cells):
        return None
    collected: list[str] = []
    i = start_line - 1
    while i >= 0:
        raw = md_lines[i]
        line = raw.strip()
        if not line:
            i -= 1
            continue
        if raw.lstrip().startswith("#") or line.startswith("|") or line.startswith("<"):
            break
        collected.append(line)
        i -= 1
        if len(collected) >= 8:
            break
    collected.reverse()
    stubs = 0
    for line in collected:
        if _looks_like_row_stub(line) or re.match(r"^\d+(\.\d+)*\s+\S", line):
            stubs += 1
        elif line[:1].islower() or line[:1] in "\"'":
            stubs += 1
    if stubs < 2 or len(collected) < 2:
        return None
    first_tokens = header_cells[0].split()
    header = tuple(first_tokens[:3])
    while len(header) < 3:
        header = header + ("",)
    body = tuple((line,) + ("", "") for line in collected[:6])
    return _flat_unit((header,) + body)


def _is_trail_leak_line(line: str) -> bool:
    """True when a post-table prose line is a leaked cell, not a sentence."""
    s = line.strip()
    if not s:
        return False
    if s.startswith("]"):
        return True
    if re.search(r"P\d{3,5}R\d+\[\d+$", s, re.IGNORECASE):
        return True
    lowered = s.lower()
    if any(lowered.startswith(lab) for lab in _TRAIL_ROW_LABELS):
        return True
    return _looks_like_row_stub(s)


def _trailing_flatten_after_pipe(
    md_lines: list[str],
    line_after: int,
    header_cells: tuple[str, ...],
) -> TableUnit | None:
    """Prose leak immediately after a leftover smash pipe (P4096R0 §5.1 / §5.4)."""
    collected: list[str] = []
    leaks = 0
    j = line_after
    while j < len(md_lines) and len(collected) < 10:
        raw = md_lines[j]
        line = raw.strip()
        if not line:
            j += 1
            continue
        if raw.lstrip().startswith("#") or line.startswith("|") or line.startswith("<"):
            break
        collected.append(line)
        if _is_trail_leak_line(line):
            leaks += 1
        j += 1
    if leaks < 2 or len(collected) < 2:
        return None
    first = header_cells[0].split()[:3] if header_cells else ("(flattened)",)
    header = tuple(first)
    while len(header) < 2:
        header = header + ("",)
    body = tuple((line,) + ("",) * (len(header) - 1) for line in collected[:8])
    return _flat_unit((header,) + body)


def _detect_year_column_heading(md_lines: list[str]) -> list[TableUnit]:
    """``## 2026 evidence`` is a leaked column, not a section (P4096R0 §5.1)."""
    results: list[TableUnit] = []
    i = 0
    while i < len(md_lines):
        m = _YEAR_LABEL_HEADING_RE.match(md_lines[i])
        if not m:
            i += 1
            continue
        label = m.group(2).strip().lower()
        if label not in _FLAT_COLUMN_LABELS:
            i += 1
            continue
        data_rows: list[str] = []
        j = i + 1
        while j < len(md_lines):
            line = md_lines[j].strip()
            if not line:
                j += 1
                continue
            if line.startswith("#") or line.startswith("|") or line.startswith("<"):
                break
            data_rows.append(line)
            j += 1
        if data_rows:
            header = (m.group(1), m.group(2).strip())
            body = tuple((row, "") for row in data_rows[:6])
            results.append(_flat_unit((header,) + body))
        i = j if j > i + 1 else i + 1
    return results


_STACKED_TABLE_LABELS = frozenset({"#", "prediction", "source", "date", "outcome"})


def _detect_stacked_flattened(md_lines: list[str]) -> list[TableUnit]:
    """Find a table flattened to stacked header labels plus row-id lines.

    Pattern (P4047R0 Safety / Customization)::

        Safety and Correctness

        #
        Prediction
        Source
        Date
        Outcome

        S1
        ...
        C1
    """
    results: list[TableUnit] = []
    i = 0
    while i < len(md_lines):
        labels: list[str] = []
        j = i
        while j < len(md_lines):
            raw = md_lines[j]
            line = raw.strip()
            if not line:
                if labels:
                    j += 1
                    continue
                break
            if _HEADING_RE.match(raw) or line.startswith("|") or line.startswith("<"):
                break
            tokens = line.split()
            if len(tokens) != 1:
                break
            key = tokens[0].lower()
            if key in _STACKED_TABLE_LABELS or tokens[0] == "#":
                labels.append(tokens[0])
                j += 1
                continue
            break
        if len(labels) >= 3:
            k = j
            while k < len(md_lines) and not md_lines[k].strip():
                k += 1
            if k < len(md_lines) and _ROW_ID_RE.match(md_lines[k].strip()):
                row_ids: list[str] = []
                t = k
                while t < len(md_lines):
                    raw = md_lines[t]
                    s = raw.strip()
                    if s.startswith("|") or s.startswith("<table") or _HEADING_RE.match(raw):
                        break
                    if len(s.split()) == 1 and s.lower() in _STACKED_TABLE_LABELS:
                        break
                    if _ROW_ID_RE.match(s):
                        row_ids.append(s)
                    t += 1
                if len(row_ids) >= 2:
                    header = tuple(labels)
                    body = tuple((rid,) + ("",) * (len(labels) - 1) for rid in row_ids)
                    cells = (header,) + body
                    results.append(
                        TableUnit(
                            index=0,
                            fmt=FORMAT_PIPE,
                            cells=cells,
                            raw_rows=tuple(
                                "| " + " | ".join(row) + " |" for row in cells
                            ),
                            has_header=True,
                            has_separator=True,
                            flattened_prose=True,
                        )
                    )
                    i = t
                    continue
        i += 1
    return results


# -- continuation-header detection ---------------------------------------------

_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s")


def _gap_has_heading(lines: list[str], start: int, end: int) -> bool:
    """True when any line in ``lines[start:end]`` is a Markdown heading."""
    for i in range(start, min(end, len(lines))):
        if _HEADING_RE.match(lines[i]):
            return True
    return False


def _header_values_in_body(
    header_b: tuple[str, ...],
    body_a: tuple[tuple[str, ...], ...],
) -> bool:
    """True when B's header cells plausibly come from A's body.

    Matches when at least one non-empty header cell of B appears verbatim in
    any body row of A at the same column index. A completely empty header cell
    is not evidence.
    """
    for col_idx, cell in enumerate(header_b):
        if not cell.strip():
            continue
        for body_row in body_a:
            if col_idx < len(body_row) and body_row[col_idx].strip() == cell.strip():
                return True
    return False


def _effective_column_count(header: tuple[str, ...]) -> int:
    """Column count after dropping header columns whose header cell is empty."""
    return sum(1 for cell in header if cell.strip())


def _header_tokens_overlap_body(
    header_b: tuple[str, ...],
    body_a: tuple[tuple[str, ...], ...],
) -> bool:
    """True when any non-trivial word from B's header appears in A's body.

    Broader than ``_header_values_in_body`` which requires an exact cell
    match at the same column index. This catches cases where the same
    entity names appear in different columns or with slightly different
    formatting.
    """
    header_words: set[str] = set()
    for cell in header_b:
        for word in cell.strip().lower().split():
            if len(word) > 2 and word not in _TRIVIAL_WORDS:
                header_words.add(word)
    if not header_words:
        return False
    for row in body_a:
        for cell in row:
            for word in cell.strip().lower().split():
                if word in header_words:
                    return True
    return False


def _detect_continuations(
    scans: list,  # list[_PipeScan]
    md_lines: list[str],
) -> dict[int, int]:
    """Return ``{scan_index_b: scan_index_a}`` for detected continuations.

    Two consecutive pipe scans are flagged when:
    1. The gap between them contains only blank lines (no headings).
    2. B's header differs from A's header.
    3. B's header cells appear as body values in A at matching column
       positions, **or** the effective column count (non-empty header
       cells) is identical and B's header is not a label header
       (``_is_label_header``; #411: two back-to-back tables with distinct
       label headers are not a continuation, a header made only of code
       spans or left empty still is), **or** a non-trivial word from
       B's header appears in A's body.
    """
    result: dict[int, int] = {}
    for idx in range(1, len(scans)):
        prev = scans[idx - 1]
        curr = scans[idx]
        if not prev.has_separator or not curr.has_separator:
            continue
        if _gap_has_heading(md_lines, prev.line_after, curr.start_line):
            continue
        header_a = tuple(c.strip() for c in prev.grid[0])
        header_b = tuple(c.strip() for c in curr.grid[0])
        if header_a == header_b:
            continue
        body_a = tuple(
            tuple(c.strip() for c in row) for row in prev.grid[1:]
        )
        if _header_values_in_body(header_b, body_a):
            result[idx] = idx - 1
            continue
        eff_a = _effective_column_count(header_a)
        eff_b = _effective_column_count(header_b)
        if eff_a == eff_b and not _is_label_header(header_b):
            result[idx] = idx - 1
            continue
        if _header_tokens_overlap_body(header_b, body_a):
            result[idx] = idx - 1
    return result


# -- markdown adapter ----------------------------------------------------------


def table_units_from_markdown(md: str) -> tuple[TableUnit, ...]:
    """Build table units from candidate markdown using the shared grid parser.

    Pipe units carry escape-aware ``raw_rows`` (separator omitted) so R1/R6
    compare header width to body width. Valid tables set ``has_header`` and
    ``has_separator`` so R2 can pass. A table-shaped outer-pipe block with no
    separator is still a unit, with ``has_separator=False``, so R2 fails
    instead of vanishing. HTML units denormalize rowspan/colspan into the
    grid and set ``spans_declared`` when a span attribute was present.

    Adjacent pipe tables whose header row looks like a data continuation of
    the preceding table are annotated with ``continuation_of`` so R2 can
    report the defect.
    """
    scans = _scan_pipe_blocks(md)
    md_lines = md.splitlines()
    continuations = _detect_continuations(scans, md_lines)

    units: list[TableUnit] = []
    for scan_idx, scan in enumerate(scans):
        cont = continuations.get(scan_idx)
        provisional = TableUnit(
            index=len(units),
            fmt=FORMAT_PIPE,
            cells=tuple(tuple(row) for row in scan.grid),
            raw_rows=scan.raw_rows,
            has_header=scan.has_header,
            has_separator=scan.has_separator,
            continuation_of=cont,
        )
        dah = _is_data_as_header(provisional)
        hid = False if dah else _is_header_is_data(provisional)
        units.append(
            replace(
                provisional,
                data_as_header=dah,
                wrap_bleed=_is_wrap_bleed(provisional),
                header_is_data=hid,
                truncated_leak=_is_truncated_leak(
                    provisional, md_lines, scan.line_after,
                ),
                row_merge=_is_row_merge(provisional),
                wrap_orphan=_is_wrap_orphan(provisional),
                hyphen_glue=_is_hyphen_glue(provisional),
                wording_clause=_is_wording_clause_table(provisional),
                trailing_row_leak=_is_trailing_row_leak(
                    provisional, md_lines, scan.line_after,
                ),
                absorbed_prose_row=_is_absorbed_prose_row(provisional),
            )
        )
        if hid and provisional.cells:
            lead = _leading_flatten_before_pipe(
                md_lines, scan.start_line, provisional.cells[0],
            )
            if lead is not None:
                units.append(replace(lead, index=len(units)))
        if (hid or cont is not None) and provisional.cells:
            trail = _trailing_flatten_after_pipe(
                md_lines, scan.line_after, provisional.cells[0],
            )
            if trail is not None:
                units.append(replace(trail, index=len(units)))
    for grid, had_spans in _html_tables_with_spans(md):
        html_unit = TableUnit(
            index=len(units),
            fmt=FORMAT_HTML,
            cells=tuple(tuple(row) for row in grid),
            spans_declared=had_spans,
        )
        units.append(
            replace(
                html_unit,
                header_is_data=_is_header_is_data(html_unit),
            )
        )
    for flat_unit in _detect_flattened_prose(md_lines):
        units.append(replace(flat_unit, index=len(units)))
    for stacked in _detect_stacked_flattened(md_lines):
        units.append(replace(stacked, index=len(units)))
    for year_col in _detect_year_column_heading(md_lines):
        units.append(replace(year_col, index=len(units)))
    for shattered in _is_heading_shattered_table(md_lines):
        units.append(replace(shattered, index=len(units)))
    for grid in parse_code_table_groups(md):
        units.append(
            TableUnit(
                index=len(units),
                fmt=FORMAT_CODE_GROUP,
                cells=tuple(tuple(row) for row in grid),
            )
        )
    return tuple(units)


# -- evaluation ----------------------------------------------------------------


def _validate_applicability_coverage(resolved: ResolvedContract) -> None:
    declared = set(resolved.core.applicability)
    implemented = set(APPLICABILITY_PREDICATES)
    missing = sorted(declared - implemented)
    if missing:
        raise ContractSchemaError(
            f"applicability condition(s) {', '.join(missing)} are declared in the "
            f"contract but not implemented; a rule gated on an unimplemented "
            f"condition could never fail"
        )
    extra = sorted(implemented - declared)
    if extra:
        raise ContractSchemaError(
            f"applicability predicate(s) {', '.join(extra)} are implemented but "
            f"not declared in the contract"
        )


def _normalize_methods(methods_executed: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(sorted(set(methods_executed)))
    unknown = sorted(set(normalized) - set(METHODS))
    if unknown:
        raise ValueError(
            f"unknown evaluation method(s) {', '.join(unknown)} "
            f"(allowed: {', '.join(METHODS)})"
        )
    return normalized


def _evaluate_rule(
    rule: Rule,
    *,
    ctx_units: tuple[TableUnit, ...],
    facts: DocumentFacts,
    resolved: ResolvedContract,
    methods_executed: tuple[str, ...],
    registry: Mapping[str, Check],
) -> RuleResult:
    predicate = APPLICABILITY_PREDICATES[rule.applicability]
    if not predicate(facts, resolved.thresholds):
        return RuleResult(
            rule_id=rule.id,
            strength=rule.strength,
            scope=rule.scope,
            method=rule.method,
            check_id=rule.check_id,
            status=STATUS_NOT_APPLICABLE,
            reason=rule.applicability,
        )
    if rule.method not in methods_executed:
        return RuleResult(
            rule_id=rule.id,
            strength=rule.strength,
            scope=rule.scope,
            method=rule.method,
            check_id=rule.check_id,
            status=STATUS_NOT_EVALUATED,
            reason=f"{REASON_METHOD_NOT_EXECUTED}:{rule.method}",
        )
    check = registry.get(rule.check_id)
    if check is None:
        return RuleResult(
            rule_id=rule.id,
            strength=rule.strength,
            scope=rule.scope,
            method=rule.method,
            check_id=rule.check_id,
            status=STATUS_NOT_EVALUATED,
            reason=f"{REASON_CHECK_NOT_REGISTERED}:{rule.check_id}",
        )
    outcome = check(
        CheckContext(
            rule=rule,
            units=ctx_units,
            facts=facts,
            thresholds=resolved.thresholds,
        )
    )
    if outcome.status not in (
        STATUS_PASS,
        STATUS_NOT_EVALUATED,
        rule.failure_status,
    ):
        raise ContractSchemaError(
            f"check {rule.check_id!r} returned status {outcome.status!r}, which "
            f"rule {rule.id} does not allow (expected pass, not_evaluated or "
            f"{rule.failure_status})"
        )
    return RuleResult(
        rule_id=rule.id,
        strength=rule.strength,
        scope=rule.scope,
        method=rule.method,
        check_id=rule.check_id,
        status=outcome.status,
        reason=outcome.reason,
        findings=outcome.findings,
    )


def _verdict(results: Sequence[RuleResult], *, vacuous: bool) -> str:
    if vacuous:
        return VERDICT_NOT_APPLICABLE
    if any(item.status == STATUS_FAIL for item in results):
        return VERDICT_FAIL
    if any(
        item.status == STATUS_NOT_EVALUATED and item.strength == STRENGTH_HARD
        for item in results
    ):
        return VERDICT_INCOMPLETE
    if any(item.status == STATUS_REVIEW for item in results):
        return VERDICT_REVIEW
    if any(item.status == STATUS_NOT_EVALUATED for item in results):
        return VERDICT_REVIEW
    return VERDICT_PASS


def _deterministic_ok(results: Sequence[RuleResult], *, vacuous: bool) -> bool:
    """Whether candidate markdown alone cleared every HARD deterministic rule.

    Contextual deterministic findings raise the verdict to review but do not
    clear this flag: it answers exactly one question, whether the mechanically
    provable hard requirements hold.
    """
    if vacuous:
        return False
    for item in results:
        if item.strength != STRENGTH_HARD or item.method != METHOD_DETERMINISTIC:
            continue
        if item.status not in (STATUS_PASS, STATUS_NOT_APPLICABLE):
            return False
    return True


def _blocking_reasons(
    results: Sequence[RuleResult],
    *,
    resolved: ResolvedContract,
    methods_executed: tuple[str, ...],
    vacuous: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    profile = resolved.profile
    if profile is None:
        reasons.append("profile_missing")
    if vacuous:
        reasons.append("vacuous")
    if profile is not None:
        for method in profile.required_methods:
            if method not in methods_executed:
                reasons.append(f"required_method_not_executed:{method}")
        by_id = {item.rule_id: item for item in results}
        for rule_id in profile.required_rules:
            item = by_id.get(rule_id)
            if item is None or item.status in (
                STATUS_NOT_EVALUATED,
                STATUS_NOT_APPLICABLE,
            ):
                reasons.append(f"required_rule_not_evaluated:{rule_id}")
    for item in results:
        if item.status == STATUS_FAIL:
            reasons.append(f"rule_failed:{item.rule_id}")
        elif item.status == STATUS_REVIEW:
            reasons.append(f"rule_review:{item.rule_id}")
        elif item.status == STATUS_NOT_EVALUATED and item.strength == STRENGTH_HARD:
            reasons.append(f"hard_rule_not_evaluated:{item.rule_id}")
    return tuple(sorted(set(reasons)))


def evaluate(
    resolved: ResolvedContract,
    units: Sequence[TableUnit],
    *,
    methods_executed: Iterable[str] = (METHOD_DETERMINISTIC,),
    source_available: bool = False,
    chunking_evaluated: bool = False,
    registry: Mapping[str, Check] | None = None,
    source_format: str = "unknown",
    markdown: str | None = None,
) -> TableReadabilityReport:
    """Evaluate one document against the resolved contract.

    ``units`` are the tables a lane extracted. ``methods_executed`` declares
    which lanes actually ran: a rule owned by a lane that did not run is
    ``not_evaluated``, so a candidate-only run can never report a source-proven
    rule as passed.
    """
    _validate_applicability_coverage(resolved)
    methods = _normalize_methods(methods_executed)
    checks = registry if registry is not None else DETERMINISTIC_CHECKS
    ordered_units = tuple(units)
    facts = document_facts(
        ordered_units,
        source_available=source_available,
        chunking_evaluated=chunking_evaluated,
        source_format=source_format,
        markdown=markdown,
    )
    vacuous = facts.table_count == 0
    results = tuple(
        _evaluate_rule(
            rule,
            ctx_units=ordered_units,
            facts=facts,
            resolved=resolved,
            methods_executed=methods,
            registry=checks,
        )
        for rule in resolved.rules
    )
    verdict = _verdict(results, vacuous=vacuous)
    blocking = _blocking_reasons(
        results,
        resolved=resolved,
        methods_executed=methods,
        vacuous=vacuous,
    )
    return TableReadabilityReport(
        core_id=resolved.core.id,
        core_version=resolved.core_version,
        core_hash=resolved.core_hash,
        profile_id=resolved.profile_id,
        profile_version=resolved.profile_version,
        profile_hash=resolved.profile_hash,
        model_identity=resolved.model_identity,
        methods_executed=methods,
        table_count=facts.table_count,
        vacuous=vacuous,
        verdict=verdict,
        document_deterministic_ok=_deterministic_ok(results, vacuous=vacuous),
        model_certified=not blocking,
        blocking_reasons=blocking,
        results=results,
    )
