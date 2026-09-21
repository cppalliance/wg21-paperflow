#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Per-unit count-dump probes: live LLM probes for conversion-defect detection.

**Per-unit count-dump probes** (``run_unit_dumps``): iterate every pipe unit,
classify each as label_shift, data_as_header, wrap_bleed, continuation,
wording_clause, header_is_data, flattened, truncated_leak, row_merge, or
aligned, send
the isolated table fragment with an R1-aware system prompt, and score the
response deterministically. Priority:
label_shift > wrap_bleed > data_as_header > continuation > wording_clause >
header_is_data > flattened > truncated_leak > row_merge > aligned.
Label-shift units use count-then-dump (the model's strength is counting,
~84% row/col count in CoTabBench). data_as_header units (all-numeric header,
blank body) and wrap_bleed units (sentence fragment header bleeding into body)
use count-dump with specialised scorers. Continuation and header_is_data
units use a closed question ("data values?"). truncated_leak units receive
the table plus trailing prose and are asked "leaked rows or prose?".
row_merge units are asked how many distinct row-records a cell contains.
Aligned units are scored by comparing the dump against actual cells.
``header_is_data`` / ``truncated_leak`` / ``wording_clause`` never let a
typed ``column headers`` or ``prose`` answer clear a det class
(reject-and-keep); a source-grid row-0 or row-count mismatch confirms the
defect without a typed clear.
``wrap_orphan`` still allows a typed veto (T0). Results are evidence, not
certification.

Architecture: this module lives in ``tapetum_llm`` (LLM-touching). The
``llm_readability`` core package stays LLM-free (CLAUDE.md invariant).

D1 exemption (inherited from readback): calls the pod via raw ``httpx``,
not ``pipeline.run_agent``, because probes are zero-shot Q&A tasks with no
pipeline steps, no structured output, and no retry cascade.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from whisker.det.llm_readability.models import TableUnit
from whisker.llm.table_compare import (
    GRID_EXTRA_OR_MISSING_ROWS,
    GRID_ROW0_MISMATCH,
    GRID_UNRELIABLE,
    TableCompareResult,
    compare_pdf_tables,
    grid_match_for_unit,
    grid_pairing_note,
    grid_signal_for_unit,
)
from whisker.tables import split_pipe_cells

logger = logging.getLogger(__name__)

__all__ = [
    "AllUnitDumpsResult",
    "ProbeResult",
    "UNIT_DUMPS_KIND",
    "UnitDumpResult",
    "run_unit_dumps",
    "pair_unit_to_page",
    "score_header_is_data_answer",
    "score_numeric_header_dump",
    "score_wording_clause_answer",
    "score_row_merge_answer",
    "score_source_mismatch_answer",
    "score_truncated_leak_answer",
    "score_wrap_bleed_dump",
    "score_flattened_answer",
    "resolve_source_typed_probe",
    "unit_dumps_to_dict",
]

_NO_CLEAR_CLASSES = frozenset({
    "header_is_data",
    "truncated_leak",
    "wording_clause",
    "flattened",
})
_GRID_KEEP = frozenset({GRID_ROW0_MISMATCH, GRID_EXTRA_OR_MISSING_ROWS})

UNIT_DUMPS_KIND = "whisker-table-unit-dumps"

_REQUEST_TIMEOUT = 120.0
_MAX_ANSWER_TOKENS = 512
# Pod default flipped thinking-on; pin off for raw httpx probe calls.
_NON_THINK_CHAT_TEMPLATE_KWARGS: dict[str, object] = {"enable_thinking": False}
_TEXTLAYER_EXCERPT_CHARS = 1800
_SOURCE_VERDICTS = (
    "match",
    "split",
    "data-header",
    "leaked-rows",
    "merged-rows",
    "wrap",
    "glue",
    "flattened",
)

@dataclass
class ProbeResult:
    """Result of one probe question."""

    probe_id: str
    question: str
    expected: str
    answer: str
    passed: bool
    latency_ms: int = 0
    error: bool = False
    skipped: bool = False
    skip_reason: str = ""
    defect_confirmed: bool = False


@dataclass
class UnitDumpResult:
    """Count-dump probe result for a single table unit."""

    unit_index: int
    classification: str  # "label_shift" | "continuation" | "aligned"
    probe: ProbeResult
    dump: dict[str, dict[int, str]] | None = None


@dataclass
class AllUnitDumpsResult:
    """Results of count-dump probes over every pipe unit in a paper."""

    pid: str
    model: str
    units: list[UnitDumpResult] = field(default_factory=list)

    @property
    def pass_count(self) -> int:
        return sum(1 for u in self.units if u.probe.passed and not u.probe.error and not u.probe.skipped)

    @property
    def fail_count(self) -> int:
        return sum(1 for u in self.units if not u.probe.passed and not u.probe.error and not u.probe.skipped)

    @property
    def skip_count(self) -> int:
        return sum(1 for u in self.units if u.probe.skipped)


def unit_dumps_to_dict(result: AllUnitDumpsResult) -> dict:
    """Serialize dumps as evidence. Never a certification envelope."""
    return {
        "kind": UNIT_DUMPS_KIND,
        "pid": result.pid,
        "model": result.model,
        "units": [
            {
                "unit_index": unit.unit_index,
                "classification": unit.classification,
                "dump": unit.dump,
                "probe": {
                    "probe_id": unit.probe.probe_id,
                    "question": unit.probe.question,
                    "expected": unit.probe.expected,
                    "answer": unit.probe.answer,
                    "passed": unit.probe.passed,
                    "latency_ms": unit.probe.latency_ms,
                    "error": unit.probe.error,
                    "skipped": unit.probe.skipped,
                    "skip_reason": unit.probe.skip_reason,
                    "defect_confirmed": unit.probe.defect_confirmed,
                },
            }
            for unit in result.units
        ],
        "pass_count": result.pass_count,
        "fail_count": result.fail_count,
        "skip_count": result.skip_count,
    }


def _norm_cell(text: str) -> str:
    """Normalize cell text for comparison: lowercase, collapse whitespace."""
    return re.sub(r"\s+", " ", text.lower()).strip()


# -- Defect probe helpers (label shift + continuation header) ------------------

_LABEL_SHIFT_MAJORITY = 0.5

_R1_SYSTEM_PROMPT = (
    "You are a pipe-table structure analyst. A pipe table is a 1D token "
    "stream whose delimiters carry the coordinates. A cell is located by "
    "counting pipe delimiters left to right. Follow the output format "
    "exactly. Use EMPTY for empty cells."
)

_DATA_KEYWORDS = frozenset({
    "data value", "data", "person", "name", "continuation",
    "not a header", "not header", "not column header",
})
_WORDING_CLAUSE_ANSWER_KEYWORDS = frozenset({
    "numbered",
    "paragraph",
    "spec paragraph",
    "wording",
})

_CELL_DUMP_RE = re.compile(
    r"\[(\d+)\]\s*=\s*(.+?)(?=\s*\[\d+\]\s*=|\s*$)"
)


def _label_shift_on_unit(
    unit: TableUnit,
) -> tuple[int, int] | None:
    """Return ``(stub_col, starved_col)`` if *this specific unit* has a label shift.

    Returns ``None`` when the unit is clean.
    """
    if unit.fmt != "pipe" or len(unit.cells) < 2:
        return None
    header = unit.cells[0]
    body = unit.cells[1:]
    width = len(header)
    n_body = len(body)
    if n_body == 0:
        return None
    col_fill = [
        sum(1 for row in body if col < len(row) and row[col].strip())
        for col in range(width)
    ]
    for stub_col in range(width):
        if header[stub_col].strip():
            continue
        if col_fill[stub_col] <= n_body * _LABEL_SHIFT_MAJORITY:
            continue
        for neighbour in (stub_col + 1, stub_col - 1):
            if neighbour < 0 or neighbour >= width:
                continue
            if not header[neighbour].strip():
                continue
            if col_fill[neighbour] > n_body * _LABEL_SHIFT_MAJORITY:
                continue
            return (stub_col, neighbour)
    return None


def score_numeric_header_dump(
    dump: dict[str, dict[int, str]],
    unit: TableUnit,
) -> tuple[bool, str]:
    """Score a count-dump for a data_as_header unit (poll-split pattern).

    Passes (defect confirmed) when the model echoes the numeric header cells
    back, proving they are data masquerading as column labels.
    """
    header_dump = dump.get("HEADER", {})
    if not header_dump:
        return False, "dump missing HEADER"

    actual_header = unit.cells[0] if unit.cells else ()
    numeric_matches = 0
    total_checked = 0
    for col_1based, dumped_val in header_dump.items():
        col_0based = col_1based - 1
        if col_0based < 0 or col_0based >= len(actual_header):
            continue
        expected = actual_header[col_0based].strip()
        if not expected:
            continue
        total_checked += 1
        if expected.isdigit() and _norm_cell(dumped_val) == _norm_cell(expected):
            numeric_matches += 1

    if total_checked == 0:
        return False, "no non-empty header cells to check"
    if numeric_matches == total_checked:
        return True, f"all {numeric_matches} header cells are numeric data"
    return False, f"only {numeric_matches}/{total_checked} header cells matched as numeric"


def score_wrap_bleed_dump(
    dump: dict[str, dict[int, str]],
    unit: TableUnit,
) -> tuple[bool, str]:
    """Score a count-dump for a wrap_bleed unit (sentence fragment in header).

    Passes (defect confirmed) when the model echoes the sentence-fragment
    header faithfully, confirming the header contains prose, not field labels.
    """
    header_dump = dump.get("HEADER", {})
    if not header_dump:
        return False, "dump missing HEADER"

    actual_header = unit.cells[0] if unit.cells else ()
    fragment_matches = 0
    fragment_total = 0
    for col_1based, dumped_val in header_dump.items():
        col_0based = col_1based - 1
        if col_0based < 0 or col_0based >= len(actual_header):
            continue
        expected = actual_header[col_0based].strip()
        if not expected or len(expected.split()) < 3:
            continue
        fragment_total += 1
        if _norm_cell(dumped_val).startswith(_norm_cell(expected)[:20]):
            fragment_matches += 1

    if fragment_total == 0:
        return False, "no sentence-length header cells to check"
    if fragment_matches > 0:
        return True, f"header contains sentence fragments ({fragment_matches} confirmed)"
    return False, f"model did not echo sentence fragments (0/{fragment_total})"


def pair_unit_to_page(
    unit: TableUnit,
    pages: list[str],
) -> tuple[int, str] | None:
    """Return ``(page_index, excerpt)`` for the textlayer page matching *unit*.

    Scores pages by how many non-trivial tokens from the table header and
    first body row appear in the page text. Requires at least two hits.
    Missing or empty *pages* returns ``None`` (caller must not fake a pass).
    """
    if not pages:
        return None
    tokens: list[str] = []
    for row in unit.cells[:3]:
        for cell in row:
            for word in cell.replace("`", " ").split():
                clean = word.strip("[]()*.,;:\"'").lower()
                if len(clean) > 3 and clean not in {
                    "this", "that", "with", "from", "have", "been",
                }:
                    tokens.append(clean)
    if not tokens:
        return None
    unique = list(dict.fromkeys(tokens))
    best_i = -1
    best_score = 0
    for i, page in enumerate(pages):
        plow = page.lower()
        score = sum(1 for t in unique if t in plow)
        if score > best_score:
            best_i = i
            best_score = score
    if best_i < 0 or best_score < 2:
        return None
    page = pages[best_i]
    hay = page.lower()
    pos = -1
    for t in unique:
        pos = hay.find(t)
        if pos >= 0:
            break
    if pos < 0:
        excerpt = page[:_TEXTLAYER_EXCERPT_CHARS]
    else:
        start = max(0, pos - 200)
        excerpt = page[start:start + _TEXTLAYER_EXCERPT_CHARS]
    return best_i, excerpt


# Prompts ask for one exact closed answer. Score the complete normalized
# string only; prose, negation, punctuation, embedded forms, and multiple
# verdicts are non-confirming.
_FLATTEN_DEFECT_ANSWERS = frozenset({"flattened", "flatten"})
_WRAP_DEFECT_ANSWERS = frozenset({"wrap"})
_GLUE_DEFECT_ANSWERS = frozenset({"glue", "glued"})
_SOURCE_AMBIGUOUS_PREFIX = "ambiguous source verdict:"
_SOURCE_EXACT_ANSWERS: dict[str, str] = {
    "match": "match",
    "split": "split",
    "data-header": "data-header",
    "data header": "data-header",
    "leaked-rows": "leaked-rows",
    "leaked rows": "leaked-rows",
    "merged-rows": "merged-rows",
    "merged rows": "merged-rows",
    "wrap": "wrap",
    "glue": "glue",
    "glued": "glue",
    "flattened": "flattened",
    "flatten": "flattened",
}


def score_source_mismatch_answer(
    answer: str,
    *,
    expect_defect: bool,
) -> tuple[bool, str]:
    """Score the source-vs-markdown closed question.

    Parses the complete normalized answer as exactly one closed-set
    verdict (``match``, ``split``, ``data-header`` / ``data header``,
    ``leaked-rows`` / ``leaked rows``, ``merged-rows`` / ``merged rows``,
    ``wrap``, ``glue`` / ``glued``, ``flatten`` / ``flattened``).
    Anything else is ambiguous.
    ``expect_defect=True``: any verdict except ``match`` confirms the defect.
    ``expect_defect=False``: only ``match`` passes (clean control).
    """
    verdict = _SOURCE_EXACT_ANSWERS.get(_norm_cell(answer))
    if verdict is None:
        return False, f"{_SOURCE_AMBIGUOUS_PREFIX} {answer[:80]!r}"
    if expect_defect:
        return verdict != "match", f"source verdict={verdict}"
    return verdict == "match", f"source verdict={verdict}"


def resolve_source_typed_probe(
    cls: str,
    *,
    source_ok: bool,
    typed_ok: bool | None,
    grid_signal: str,
    grid_note: str = "",
) -> tuple[bool, str]:
    """Decide whether a defect-class probe is confirmed.

    ``source_ok`` is True when source-first confirmed the defect.
    ``typed_ok`` is True when typed fallback confirmed it, False when
    it refused, None when typed was not run.

    For ``header_is_data`` / ``truncated_leak`` / ``wording_clause`` a
    grid mismatch keeps the det class (reject-and-keep). Typed
    ``column headers`` / ``prose`` never clears those classes.
    ``wrap_orphan`` / ``hyphen_glue`` still allow a typed veto (T0).

    ``grid_note`` (``table_compare.grid_pairing_note``) is appended to the
    abstain reason so the report tells "no grid" from "pairing rejected".
    """
    if source_ok:
        return True, "source confirmed defect"
    if cls in _NO_CLEAR_CLASSES:
        if grid_signal in _GRID_KEEP:
            return True, f"grid {grid_signal}; det kept"
        if typed_ok:
            return True, "typed confirmed defect"
        reason = f"abstain: typed did not confirm, grid={grid_signal}"
        if grid_note:
            reason = f"{reason} ({grid_note})"
        return False, reason
    if typed_ok:
        return True, "typed confirmed defect"
    return False, "typed did not confirm"


def score_header_is_data_answer(answer: str) -> tuple[bool, str]:
    """Score the closed question for a header_is_data unit.

    Same question as continuation: "column headers or data values?"
    Passes (defect confirmed) when the model says "data values".
    """
    norm = _norm_cell(answer)
    if any(kw in norm for kw in _DATA_KEYWORDS):
        return True, "model says header cells are data values"
    return False, f"model did not confirm data values: {answer[:80]!r}"


def score_wording_clause_answer(answer: str) -> tuple[bool, str]:
    """Score the closed question for a wording_clause unit.

    Reuses the header_is_data data-value keywords, then accepts
    numbered-paragraph phrasing. A typed "column headers" answer does
    not confirm (and cannot clear the det flag; see ``_NO_CLEAR_CLASSES``).
    """
    ok, reason = score_header_is_data_answer(answer)
    if ok:
        return ok, reason
    norm = _norm_cell(answer)
    if any(kw in norm for kw in sorted(_WORDING_CLAUSE_ANSWER_KEYWORDS)):
        return True, "model says rows are numbered spec paragraphs"
    return False, f"model did not confirm wording paragraphs: {answer[:80]!r}"


def score_truncated_leak_answer(answer: str) -> tuple[bool, str]:
    """Score the closed question for a truncated_leak unit.

    Question: "leaked rows or prose?" Passes when the model says
    "leaked rows".
    """
    norm = _norm_cell(answer)
    if "leaked" in norm or "leak" in norm:
        return True, "model says text is leaked rows"
    if "prose" in norm:
        return False, "model says text is prose"
    return False, f"model gave ambiguous answer: {answer[:80]!r}"


def score_row_merge_answer(answer: str) -> tuple[bool, str]:
    """Score the closed question for a row_merge unit.

    Question: "How many distinct row-records?" Passes when the answer
    is an integer >= 2.
    """
    for token in answer.split():
        clean = token.strip(".,;:!?()\"'")
        if clean.isdigit():
            count = int(clean)
            if count >= 2:
                return True, f"model says {count} row-records in cell"
            return False, f"model says {count} row-record(s), expected >= 2"
    return False, f"model did not return an integer: {answer[:80]!r}"


def _build_header_is_data_question(
    unit: TableUnit,
    source_header: tuple[str, ...] | None = None,
) -> tuple[str, str, str] | None:
    """Build ``(probe_id, question, table_md)`` for a header_is_data unit.

    Same closed question as continuation: asks whether header cells are
    column headers or data values. When the PDF header row is known it
    is quoted so the model is not asked to judge the already-broken GFM
    header in isolation.
    """
    header_names = [h.strip() for h in unit.cells[0] if h.strip()]
    if not header_names:
        return None
    data_like = [
        h for h in header_names
        if (
            h.endswith(",")
            or h.count("(") > h.count(")")
            or ":" in h
            or h.startswith("`")
            or "::" in h
            or h.isupper()
            or len(h.split()) >= 3
        )
    ]
    quoted_cells = data_like or header_names
    table_md = _raw_rows_to_md(unit)
    quoted = " and ".join(repr(h) for h in quoted_cells)
    question = (
        f"Are the values {quoted} actual column header names (like "
        f"field labels), or are they data values (like a person's "
        f"name or a code identifier)? "
        f"Answer 'column headers' or 'data values'."
    )
    if source_header:
        src = " | ".join(cell for cell in source_header if cell)
        if src:
            question = (
                f"The PDF source header row is: {src}. "
                + question
            )
    return ("diag-header-is-data", question, table_md)


def _build_wording_clause_question(
    unit: TableUnit,
    source_header: tuple[str, ...] | None = None,
) -> tuple[str, str, str] | None:
    """Build ``(probe_id, question, table_md)`` for a wording_clause unit.

    Closed question: are these rows numbered spec paragraphs / data
    values rather than column headers?
    """
    header_names = [h.strip() for h in unit.cells[0] if h.strip()]
    if not header_names:
        return None
    table_md = _raw_rows_to_md(unit)
    quoted = " and ".join(repr(h) for h in header_names)
    question = (
        f"Are the values {quoted} column headers (field labels), or are "
        f"they numbered specification paragraphs / data values? "
        f"Answer 'column headers' or 'data values'."
    )
    if source_header:
        src = " | ".join(cell for cell in source_header if cell)
        if src:
            question = (
                f"The PDF source header row is: {src}. "
                + question
            )
    return ("diag-wording-clause", question, table_md)


def _build_truncated_leak_question(
    unit: TableUnit,
    md_lines: list[str],
    line_after: int,
) -> tuple[str, str, str] | None:
    """Build ``(probe_id, question, table_md_plus_context)`` for a truncated_leak unit.

    The model receives the table plus 4-6 lines of prose following it and
    is asked whether the text below is leaked table rows or normal prose.
    The question names a ``Label: value`` caption (``Result: Consensus``)
    as prose: det's ``_is_truncated_leak`` flags a filled poll grid followed
    by such a caption (P3290R4 T1-T5, #426), and the typed answer is what
    decides once no grid pairs (see ``resolve_source_typed_probe``). The
    exemption is the caption shape only; a trailing line that carries
    column values (a meeting, a date, a poll count) stays ``leaked rows``.
    """
    table_md = _raw_rows_to_md(unit)
    context_lines: list[str] = []
    for i in range(line_after, min(line_after + 6, len(md_lines))):
        context_lines.append(md_lines[i])
    if not context_lines:
        return None
    combined = table_md + "\n\n" + "\n".join(context_lines)
    question = (
        "Look at the table above and the text that follows it. "
        "Is the text below the table additional table rows that fell "
        "out of the pipe structure, or is it normal flowing prose? "
        "A short 'Label: value' caption directly under the table, such as "
        "'Result: Consensus' or 'Outcome: No consensus', is prose. "
        "Answer 'leaked rows' only when the text carries cell values that "
        "belong in the table's columns, even if it names a meeting, a date "
        "or a poll. Answer 'leaked rows' or 'prose'."
    )
    return ("diag-truncated-leak", question, combined)


def _build_row_merge_question(
    unit: TableUnit,
) -> tuple[str, str, str] | None:
    """Build ``(probe_id, question, table_md)`` for a row_merge unit.

    Asks how many distinct row-records are in a specific cell.
    """
    target_cell = ""
    for row in unit.cells[1:]:
        for cell in row:
            text = cell.strip()
            if len(text.split()) >= 4 and "," not in text and ";" not in text:
                target_cell = text
                break
        if target_cell:
            break
    if not target_cell:
        return None
    table_md = _raw_rows_to_md(unit)
    question = (
        f"Look at the cell containing: {target_cell!r}\n"
        f"How many distinct row-records (separate entries that should "
        f"each be their own table row) are in this cell? "
        f"Answer an integer."
    )
    return ("diag-row-merge", question, table_md)


def _build_source_mismatch_question(unit: TableUnit) -> str:
    """Closed question used when the unit is paired with a PDF text layer."""
    return (
        "Does the markdown table match the source table on this page, "
        "or is it broken? Answer exactly one of: "
        + ", ".join(_SOURCE_VERDICTS)
        + "."
    )


def _build_wrap_orphan_question(unit: TableUnit) -> tuple[str, str, str]:
    table_md = _raw_rows_to_md(unit)
    question = (
        "Does any cell contain a line-wrap leftover token "
        "(a lone N or K after an Appendix reference) that is not "
        "part of the cell meaning? Answer 'wrap' or 'clean'."
    )
    return ("diag-wrap-orphan", question, table_md)


def _build_hyphen_glue_question(unit: TableUnit) -> tuple[str, str, str]:
    table_md = _raw_rows_to_md(unit)
    question = (
        "Are words such as Debuggerfriendly, singlethreaded, or "
        "scheduleindependent missing hyphens? Answer 'glued' or 'normal'."
    )
    return ("diag-hyphen-glue", question, table_md)


def _build_flattened_question(unit: TableUnit) -> tuple[str, str, str] | None:
    """Build ``(probe_id, question, table_md)`` for a flattened unit.

    A flattened unit is a table that the converter rendered as an ATX
    heading followed by prose rows instead of a pipe table.
    """
    header_names = [h.strip() for h in unit.cells[0] if h.strip()]
    if not header_names:
        return None
    table_md = _raw_rows_to_md(unit)
    quoted = " and ".join(repr(h) for h in header_names)
    question = (
        f"The values {quoted} appear as a heading followed by prose "
        f"rows in the markdown, not as a pipe table. "
        f"Is this content that should be a proper table? "
        f"Answer 'flattened' if a table was incorrectly rendered as "
        f"heading + prose, or 'match' if this is correct prose."
    )
    return ("diag-flattened", question, table_md)


def score_flattened_answer(answer: str) -> tuple[bool, str]:
    """Score the closed question for a flattened unit.

    Confirms only when the complete normalized answer is exactly
    ``flattened`` or ``flatten``. Exact ``match`` and every other string
    (prose, negation, punctuation, embedded forms) do not confirm.
    """
    if _norm_cell(answer) in _FLATTEN_DEFECT_ANSWERS:
        return True, "model says content is a flattened table"
    return False, f"model did not confirm flattened table: {answer[:80]!r}"


def _typed_question_for(
    cls: str,
    unit: TableUnit,
    md_lines: list[str] | None,
    source_header: tuple[str, ...] | None = None,
) -> tuple[str, str, str] | None:
    if cls == "header_is_data":
        return _build_header_is_data_question(unit, source_header=source_header)
    if cls == "wording_clause":
        return _build_wording_clause_question(unit, source_header=source_header)
    if cls == "truncated_leak":
        if md_lines is None:
            return None
        return _build_truncated_leak_question(
            unit, md_lines, _estimate_line_after(unit, md_lines),
        )
    if cls == "row_merge":
        return _build_row_merge_question(unit)
    if cls == "wrap_orphan":
        return _build_wrap_orphan_question(unit)
    if cls == "hyphen_glue":
        return _build_hyphen_glue_question(unit)
    if cls == "flattened":
        return _build_flattened_question(unit)
    return None


def _score_typed_answer(cls: str, answer: str) -> tuple[bool, str]:
    if cls == "header_is_data":
        return score_header_is_data_answer(answer)
    if cls == "wording_clause":
        return score_wording_clause_answer(answer)
    if cls == "truncated_leak":
        return score_truncated_leak_answer(answer)
    if cls == "row_merge":
        return score_row_merge_answer(answer)
    if cls == "wrap_orphan":
        if _norm_cell(answer) in _WRAP_DEFECT_ANSWERS:
            return True, "model says wrap orphan"
        return False, f"model did not confirm wrap: {answer[:80]!r}"
    if cls == "hyphen_glue":
        if _norm_cell(answer) in _GLUE_DEFECT_ANSWERS:
            return True, "model says hyphen glue"
        return False, f"model did not confirm glue: {answer[:80]!r}"
    if cls == "flattened":
        return score_flattened_answer(answer)
    return False, f"no typed scorer for {cls}"


def _estimate_line_after(unit: TableUnit, md_lines: list[str]) -> int:
    """Estimate the first line index after *unit* in *md_lines*.

    Finds the header row text and requires the unit's body rows to follow
    it (header, separator unless ``has_separator`` is False, body rows).
    Papers repeat one poll header verbatim (P3290R4: five
    ``SF | F | N | A | SA`` tables, #426); header-only matching sent every
    later poll's lookahead to the first poll's trailing prose. Falls back
    to the first header hit when no full-row match exists.

    # shortcut: re-derives what ``whisker.tables._PipeScan.line_after``
    # already knows; det drops it in ``table_units_from_markdown``
    # (frozen). Two byte-identical tables still both resolve to the first
    # one. Upgrade path: map ``scan.raw_rows -> scan.line_after`` from one
    # ``_scan_pipe_blocks`` pass when det exposes it.
    """
    if unit.raw_rows:
        rows = [r.strip() for r in unit.raw_rows]
    elif unit.cells:
        rows = [("| " + " | ".join(row) + " |").strip() for row in unit.cells]
    else:
        return len(md_lines)

    # Outer-pipe runs without a separator line are units too
    # (``has_separator=False``); their first body row sits right under the
    # header.
    sep = 0 if unit.has_separator is False else 1
    header_hits = [i for i, line in enumerate(md_lines) if line.strip() == rows[0]]
    for i in header_hits:
        body_start = i + 1 + sep
        if all(
            body_start + k < len(md_lines)
            and md_lines[body_start + k].strip() == row
            for k, row in enumerate(rows[1:])
        ):
            return body_start + len(rows) - 1
    if header_hits:
        return header_hits[0] + sep + len(rows)
    return len(md_lines)


def _raw_rows_to_md(unit: TableUnit) -> str:
    """Reconstruct a minimal pipe-table markdown fragment from a unit's raw_rows.

    The raw_rows tuple omits the separator line, so we synthesize one from
    the header width.
    """
    if unit.raw_rows:
        rows = list(unit.raw_rows)
        if len(rows) >= 1:
            n_cells = len(split_pipe_cells(rows[0]))
            sep = "| " + " | ".join("---" for _ in range(n_cells)) + " |"
            return rows[0] + "\n" + sep + "\n" + "\n".join(rows[1:])
    header = unit.cells[0] if unit.cells else ()
    sep = "| " + " | ".join("---" for _ in header) + " |"
    lines = [
        "| " + " | ".join(c for c in header) + " |",
        sep,
    ]
    for row in unit.cells[1:]:
        lines.append("| " + " | ".join(c for c in row) + " |")
    return "\n".join(lines)


def _build_count_dump_question(
    unit: TableUnit,
    n_body_rows: int = 3,
) -> tuple[str, str]:
    """Build the count-then-dump question and the table fragment to send.

    Returns ``(question_text, table_md_fragment)``.
    The question asks the model to list cells by 1-based index. The table
    fragment is only the target table, not the full paper.
    """
    table_md = _raw_rows_to_md(unit)
    cap = min(n_body_rows, max(0, unit.row_count - 1))
    body_rows_spec = ", ".join(f"BODY ROW {i}" for i in range(1, cap + 1))

    question = (
        "Count the pipe delimiters in each row of the table below. "
        "List every cell left-to-right using 1-based column indices.\n\n"
        "Use this exact format (one line per row, EMPTY for blank cells):\n"
        f"HEADER: [1]=... [2]=... [3]=...\n"
        f"{body_rows_spec}\n\n"
        "Then write one final line:\n"
        "UNDER header[2]: body[1][2]\n\n"
        "That line reports what body row 1's cell at position 2 contains, "
        "according to the header at position 2."
    )
    return question, table_md


def _build_continuation_question(
    cont_unit: TableUnit,
) -> tuple[str, str, str] | None:
    """Build ``(probe_id, question, table_md)`` for a continuation header."""
    header_names = [h.strip() for h in cont_unit.cells[0] if h.strip()]
    if not header_names:
        return None
    table_md = _raw_rows_to_md(cont_unit)
    quoted = " and ".join(repr(h) for h in header_names)
    question = (
        f"Are the values {quoted} actual column header names (like "
        f"field labels), or are they data values (like a person's "
        f"name and their organization)? "
        f"Answer 'column headers' or 'data values'."
    )
    return ("diag-continuation-header", question, table_md)


def parse_cell_dump(answer: str) -> dict[str, dict[int, str]]:
    """Parse a cell dump answer into ``{row_label: {col_index: value}}``.

    Handles lines like ``HEADER: [1]=EMPTY [2]=Name [3]=National Body``
    and ``BODY ROW 1: [1]=Adams, Michael [2]=EMPTY [3]=SCC``.
    Also captures ``UNDER header[N]: body[M][N]`` into key ``"UNDER"``.
    """
    result: dict[str, dict[int, str]] = {}
    under_re = re.compile(
        r"UNDER\s+header\[(\d+)\]\s*:\s*(.+)",
        re.IGNORECASE,
    )
    for line in answer.split("\n"):
        line = line.strip()
        if not line:
            continue
        m_under = under_re.match(line)
        if m_under:
            col = int(m_under.group(1))
            val = m_under.group(2).strip()
            result["UNDER"] = {col: val}
            continue
        colon = line.find(":")
        if colon < 0:
            continue
        label = line[:colon].strip().upper()
        payload = line[colon + 1:]
        cells: dict[int, str] = {}
        for m in _CELL_DUMP_RE.finditer(payload):
            idx = int(m.group(1))
            val = m.group(2).strip()
            cells[idx] = val
        if cells:
            result[label] = cells
    return result


def score_cell_dump(
    dump: dict[str, dict[int, str]],
    unit: TableUnit,
    stub_col: int,
    starved_col: int,
) -> tuple[bool, str]:
    """Score a parsed cell dump against the known label shift.

    Returns ``(passed, reason)`` where *passed* is True when the dump
    reflects the shift: the starved header column's body cell is EMPTY
    and the stub column's body cell is non-empty.
    """
    header = dump.get("HEADER", {})
    body1 = dump.get("BODY ROW 1", {})

    h_idx = stub_col + 1
    s_idx = starved_col + 1

    if not header or not body1:
        return False, "dump missing HEADER or BODY ROW 1"

    h_stub = _norm_cell(header.get(h_idx, ""))
    h_starved = _norm_cell(header.get(s_idx, ""))
    b_stub = _norm_cell(body1.get(h_idx, ""))
    b_starved = _norm_cell(body1.get(s_idx, ""))

    actual_header = unit.cells[0]
    expected_starved_name = _norm_cell(
        actual_header[starved_col] if starved_col < len(actual_header) else ""
    )

    checks: list[str] = []

    if h_stub != "empty":
        checks.append(
            f"header[{h_idx}] should be EMPTY, got {header.get(h_idx, '?')!r}"
        )
    if expected_starved_name and h_starved != expected_starved_name:
        checks.append(
            f"header[{s_idx}] should be {expected_starved_name!r}, "
            f"got {header.get(s_idx, '?')!r}"
        )
    if b_starved not in ("empty", ""):
        checks.append(
            f"body[1][{s_idx}] should be EMPTY, got {body1.get(s_idx, '?')!r}"
        )
    if b_stub in ("empty", ""):
        checks.append(
            f"body[1][{h_idx}] should be non-empty, got EMPTY"
        )

    if checks:
        return False, "; ".join(checks)

    under = dump.get("UNDER", {})
    if under:
        under_val = _norm_cell(next(iter(under.values()), ""))
        if under_val not in ("empty", ""):
            return False, (
                f"UNDER header[{s_idx}] should be EMPTY, "
                f"got {next(iter(under.values()), '?')!r}"
            )

    return True, "dump matches label-shift structure"


def _ask_pod_defect(
    client: httpx.Client,
    base_url: str,
    api_key: str,
    model_name: str,
    table_md: str,
    question: str,
    system_prompt: str = _R1_SYSTEM_PROMPT,
    source_text: str | None = None,
    source_page: int | None = None,
) -> tuple[str, int]:
    """Send a defect probe question with an isolated table fragment."""
    if source_text:
        page_label = (
            f"page {source_page + 1}" if source_page is not None else "page"
        )
        user_content = (
            f"SOURCE (PDF text layer, {page_label}):\n{source_text}\n\n"
            f"MARKDOWN TABLE:\n{table_md}\n\n"
            f"TASK:\n{question}"
        )
    else:
        user_content = f"TABLE:\n{table_md}\n\nTASK:\n{question}"
    t0 = time.monotonic()
    resp = client.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": _MAX_ANSWER_TOKENS,
            "temperature": 0.0,
            "chat_template_kwargs": _NON_THINK_CHAT_TEMPLATE_KWARGS,
        },
        timeout=_REQUEST_TIMEOUT,
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    resp.raise_for_status()
    data = resp.json()
    choices = data.get("choices", [])
    if not choices:
        return "(no response)", latency_ms
    answer = choices[0].get("message", {}).get("content", "")
    return answer.strip(), latency_ms


def _classify_unit(unit: TableUnit) -> str:
    """Classify a pipe unit for the LLM probe lane.

    Priority:
    label_shift > wrap_bleed > data_as_header > continuation >
    wording_clause > header_is_data > truncated_leak > row_merge >
    aligned.

    The first four are the N5040/P3290 detectors. Later classes target
    P4016R0 table defects and sit after the existing classifications so
    the N5040 path is untouched.
    """
    if _label_shift_on_unit(unit) is not None:
        return "label_shift"
    if unit.wrap_bleed:
        return "wrap_bleed"
    if unit.data_as_header:
        return "data_as_header"
    if unit.continuation_of is not None:
        return "continuation"
    if getattr(unit, "wording_clause", False):
        return "wording_clause"
    if unit.header_is_data:
        return "header_is_data"
    if getattr(unit, "flattened_prose", False):
        return "flattened"
    if unit.truncated_leak:
        return "truncated_leak"
    if unit.row_merge:
        return "row_merge"
    if getattr(unit, "wrap_orphan", False):
        return "wrap_orphan"
    if getattr(unit, "hyphen_glue", False):
        return "hyphen_glue"
    return "aligned"


def run_unit_dumps(
    pid: str,
    units: tuple[TableUnit, ...],
    *,
    base_url: str,
    api_key: str,
    model: str = "deepseek-v4-pro",
    md_lines: list[str] | None = None,
    textlayer_pages: list[str] | None = None,
    source_path: Path | None = None,
    table_compare: TableCompareResult | None = None,
) -> AllUnitDumpsResult:
    """Probe every pipe unit. Typed defects keep their closed questions.

    Units without a typed flag are no longer scored by dumping against
    their own markdown. They receive the PDF text-layer page plus the
    markdown fragment and a closed match/broken question. Missing
    textlayer on an aligned unit is ``skipped``, not a fake pass.

    Results are evidence, not certification.
    """
    result = AllUnitDumpsResult(pid=pid, model=model)
    pipe_units = [u for u in units if u.fmt in ("pipe", "html")]
    if not pipe_units:
        return result

    compare = table_compare
    if compare is None and source_path is not None:
        candidate_md = "\n".join(md_lines) if md_lines is not None else ""
        if candidate_md:
            compare = compare_pdf_tables(source_path, candidate_md)

    _comprehension_prompt = (
        "You are a document comprehension assistant. "
        "Be precise and concise. When a SOURCE block is present, treat it "
        "as the ground-truth table from the PDF text layer."
    )

    with httpx.Client() as client:
        for unit in pipe_units:
            cls = _classify_unit(unit)
            paired = (
                pair_unit_to_page(unit, textlayer_pages)
                if textlayer_pages
                else None
            )
            source_page = paired[0] if paired else None
            source_text = paired[1] if paired else None

            if cls == "continuation":
                cont_q = _build_continuation_question(unit)
                if cont_q is None:
                    result.units.append(UnitDumpResult(
                        unit_index=unit.index,
                        classification="continuation",
                        probe=ProbeResult(
                            probe_id=f"cont-t{unit.index}",
                            question="", expected="", answer="",
                            passed=False, skipped=True,
                            skip_reason="empty header in continuation unit",
                        ),
                    ))
                    continue
                _probe_id, question, table_md = cont_q
                error = False
                try:
                    answer, latency = _ask_pod_defect(
                        client, base_url, api_key, model,
                        table_md, question,
                        system_prompt=_comprehension_prompt,
                        source_text=source_text,
                        source_page=source_page,
                    )
                except (httpx.HTTPError, KeyError) as exc:
                    answer = f"(transport error: {type(exc).__name__}: {exc})"
                    latency = 0
                    error = True

                passed = (
                    False if error
                    else any(kw in _norm_cell(answer) for kw in _DATA_KEYWORDS)
                )
                result.units.append(UnitDumpResult(
                    unit_index=unit.index,
                    classification="continuation",
                    probe=ProbeResult(
                        probe_id=f"cont-t{unit.index}",
                        question=question,
                        expected="data values",
                        answer=answer,
                        passed=passed,
                        latency_ms=latency,
                        error=error,
                    ),
                ))

            elif cls == "label_shift":
                shift = _label_shift_on_unit(unit)
                assert shift is not None
                stub_col, starved_col = shift
                question, table_md = _build_count_dump_question(unit)
                error = False
                try:
                    answer, latency = _ask_pod_defect(
                        client, base_url, api_key, model, table_md, question,
                    )
                except (httpx.HTTPError, KeyError) as exc:
                    answer = f"(transport error: {type(exc).__name__}: {exc})"
                    latency = 0
                    error = True

                if error:
                    passed = False
                    expected_str = "cell dump showing label shift"
                    dump = None
                else:
                    dump = parse_cell_dump(answer)
                    passed, reason = score_cell_dump(dump, unit, stub_col, starved_col)
                    expected_str = f"label-shift dump ({reason})"

                result.units.append(UnitDumpResult(
                    unit_index=unit.index,
                    classification="label_shift",
                    dump=dump,
                    probe=ProbeResult(
                        probe_id=f"shift-t{unit.index}",
                        question=question,
                        expected=expected_str,
                        answer=answer,
                        passed=passed,
                        latency_ms=latency,
                        error=error,
                    ),
                ))

            elif cls in ("data_as_header", "wrap_bleed"):
                question, table_md = _build_count_dump_question(unit)
                error = False
                try:
                    answer, latency = _ask_pod_defect(
                        client, base_url, api_key, model, table_md, question,
                    )
                except (httpx.HTTPError, KeyError) as exc:
                    answer = f"(transport error: {type(exc).__name__}: {exc})"
                    latency = 0
                    error = True

                if error:
                    passed = False
                    expected_str = f"{cls} cell dump"
                    dump = None
                else:
                    dump = parse_cell_dump(answer)
                    if cls == "data_as_header":
                        passed, reason = score_numeric_header_dump(dump, unit)
                    else:
                        passed, reason = score_wrap_bleed_dump(dump, unit)
                    expected_str = f"{cls} dump ({reason})"

                result.units.append(UnitDumpResult(
                    unit_index=unit.index,
                    classification=cls,
                    dump=dump,
                    probe=ProbeResult(
                        probe_id=f"{cls.replace('_', '-')}-t{unit.index}",
                        question=question,
                        expected=expected_str,
                        answer=answer,
                        passed=passed,
                        latency_ms=latency,
                        error=error,
                    ),
                ))

            elif cls in (
                "wording_clause",
                "header_is_data",
                "truncated_leak",
                "row_merge",
                "wrap_orphan",
                "hyphen_glue",
                "flattened",
                "aligned",
            ):
                expect_defect = cls != "aligned"
                table_md = _raw_rows_to_md(unit)
                if source_text:
                    question = _build_source_mismatch_question(unit)
                    error = False
                    try:
                        answer, latency = _ask_pod_defect(
                            client, base_url, api_key, model,
                            table_md, question,
                            system_prompt=_comprehension_prompt,
                            source_text=source_text,
                            source_page=source_page,
                        )
                    except (httpx.HTTPError, KeyError) as exc:
                        answer = f"(transport error: {type(exc).__name__}: {exc})"
                        latency = 0
                        error = True
                    source_ambiguous = False
                    if error:
                        passed = False
                        expected_str = "source mismatch closed question"
                    else:
                        passed, reason = score_source_mismatch_answer(
                            answer, expect_defect=expect_defect,
                        )
                        expected_str = reason
                        source_ambiguous = reason.startswith(
                            _SOURCE_AMBIGUOUS_PREFIX,
                        )
                    if (
                        expect_defect
                        and not error
                        and not passed
                    ):
                        grid_signal = (
                            grid_signal_for_unit(unit, compare)
                            if compare is not None
                            else GRID_UNRELIABLE
                        )
                        paired_match = (
                            grid_match_for_unit(unit, compare)
                            if compare is not None
                            else None
                        )
                        source_header = (
                            paired_match.source_header if paired_match else None
                        )
                        typed_q = _typed_question_for(
                            cls, unit, md_lines, source_header=source_header,
                        )
                        typed_ok: bool | None = None
                        if typed_q is not None:
                            _pid, typed_question, typed_md = typed_q
                            try:
                                typed_answer, typed_ms = _ask_pod_defect(
                                    client, base_url, api_key, model,
                                    typed_md, typed_question,
                                    system_prompt=_comprehension_prompt,
                                )
                                latency += typed_ms
                                typed_ok, typed_reason = _score_typed_answer(
                                    cls, typed_answer,
                                )
                                answer = f"{answer} | typed: {typed_answer}"
                                question = typed_question
                            except (httpx.HTTPError, KeyError):
                                typed_ok = None
                        passed, expected_str = resolve_source_typed_probe(
                            cls,
                            source_ok=False,
                            typed_ok=typed_ok,
                            grid_signal=grid_signal,
                            grid_note=grid_pairing_note(unit, compare),
                        )
                    is_defect_confirmed = (
                        not error
                        and (
                            passed if expect_defect
                            else (not passed and not source_ambiguous)
                        )
                    )
                    result.units.append(UnitDumpResult(
                        unit_index=unit.index,
                        classification=cls,
                        probe=ProbeResult(
                            probe_id=f"src-t{unit.index}",
                            question=question,
                            expected=expected_str,
                            answer=answer,
                            passed=passed,
                            latency_ms=latency,
                            error=error,
                            defect_confirmed=is_defect_confirmed,
                        ),
                    ))
                    continue

                if cls == "aligned":
                    result.units.append(UnitDumpResult(
                        unit_index=unit.index,
                        classification="aligned",
                        probe=ProbeResult(
                            probe_id=f"aligned-t{unit.index}",
                            question="", expected="", answer="",
                            passed=False, skipped=True,
                            skip_reason="no textlayer; refusing self-dump",
                        ),
                    ))
                    continue

                # No textlayer pairing: the typed question is the only
                # probe. Same builder as the source-first fallback, so a
                # class with a typed question there (flattened,
                # wrap_orphan, hyphen_glue) is judged here too instead of
                # skipped (P4178R0 T6, #427).
                if cls == "truncated_leak" and md_lines is None:
                    result.units.append(UnitDumpResult(
                        unit_index=unit.index,
                        classification=cls,
                        probe=ProbeResult(
                            probe_id=f"{cls}-t{unit.index}",
                            question="", expected="", answer="",
                            passed=False, skipped=True,
                            skip_reason="md_lines not provided",
                        ),
                    ))
                    continue
                typed_q = _typed_question_for(cls, unit, md_lines)
                if typed_q is None:
                    result.units.append(UnitDumpResult(
                        unit_index=unit.index,
                        classification=cls,
                        probe=ProbeResult(
                            probe_id=f"{cls}-t{unit.index}",
                            question="", expected="", answer="",
                            passed=False, skipped=True,
                            skip_reason=f"no typed question for {cls}",
                        ),
                    ))
                    continue
                _probe_id, question, typed_md = typed_q
                error = False
                try:
                    answer, latency = _ask_pod_defect(
                        client, base_url, api_key, model,
                        typed_md, question,
                        system_prompt=_comprehension_prompt,
                    )
                except (httpx.HTTPError, KeyError) as exc:
                    answer = f"(transport error: {type(exc).__name__}: {exc})"
                    latency = 0
                    error = True
                if error:
                    passed = False
                    expected_str = f"{cls} closed question"
                else:
                    typed_ok, reason = _score_typed_answer(cls, answer)
                    if cls in _NO_CLEAR_CLASSES:
                        grid_signal = (
                            grid_signal_for_unit(unit, compare)
                            if compare is not None
                            else GRID_UNRELIABLE
                        )
                        passed, expected_str = resolve_source_typed_probe(
                            cls,
                            source_ok=False,
                            typed_ok=typed_ok,
                            grid_signal=grid_signal,
                            grid_note=grid_pairing_note(unit, compare),
                        )
                    else:
                        passed, expected_str = typed_ok, reason
                result.units.append(UnitDumpResult(
                    unit_index=unit.index,
                    classification=cls,
                    probe=ProbeResult(
                        probe_id=f"{cls}-t{unit.index}",
                        question=question,
                        expected=expected_str,
                        answer=answer,
                        passed=passed,
                        latency_ms=latency,
                        error=error,
                        defect_confirmed=not error and passed,
                    ),
                ))

    return result

