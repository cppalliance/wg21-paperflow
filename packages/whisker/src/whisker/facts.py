#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Lane 3 comprehension: deterministic, source-verified fact assertions.

The fuzzy axes (Lane 2: nid/teds/mhs) measure FIDELITY (is the output close to a
reference) and the golden lane (Lane 1) measures STABILITY (did the output
change). Neither proves COMPREHENSION: that an LLM consuming the markdown can
still recover the paper's facts. A faithful-looking reflow can still scramble a
table so "row 3, column 2" no longer reads correctly, or drop a formula's
exponent, and every fidelity metric can stay green.

Across the 28 surveyed converter repos, only ``olmocr`` tests this, via
deterministic, machine-checkable fact assertions: authored statements
(``present``/``absent``/``order``/``table``/``math``) verified against the source
PDF/HTML, with NO LLM in the scoring loop. whisker adopts that model
verbatim. This also sidesteps the ground-truth-provenance problem (no repo has an
automatic "this file is 100% correct" oracle): a handful of source-verified facts
per paper are cheap to author and independent of any single ``tomd`` output.

Provenance gate: a fact is enforced ONLY when ``checked == "verified"`` (its
needle was confirmed against the source). Unverified (draft) facts are loaded and
reported but never gate, so authoring a fact and blessing it are separate, auditable
steps. Honest status: the current corpus was verified by the agent against the
staged sources; independent human blessing is pending (CLAUDE.md, Known gaps).

Facts are CONJUNCTIVE with the metric guard: a failed verified fact is a hard
fail even when the numeric slack holds. This module is pure (returns data); the
CLI reads ``<pid>.facts.jsonl`` and owns exit codes.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein as _Lev

from whisker.constants import (
    BASELINE_MAX_REPEATED_NGRAM_RATIO,
    BASELINE_MIN_ALNUM_CHARS,
)
from whisker.metrics import normalized_text, textblock2unicode
from whisker.tables import (
    parse_code_table_groups,
    parse_html_tables,
    parse_pipe_tables,
)

__all__ = [
    "FACTS_KIND",
    "FACT_TYPES",
    "Fact",
    "FactCheck",
    "FactReport",
    "auto_baseline_checks",
    "check_facts",
    "facts_from_records",
    "parse_facts_jsonl",
]

FACTS_KIND = "whisker-facts"

FACT_PRESENT = "present"
FACT_ABSENT = "absent"
FACT_ORDER = "order"
FACT_TABLE = "table"
FACT_MATH = "math"
FACT_CODE = "code"
FACT_XREF = "xref"
FACT_IMAGE_REF = "image_ref"
FACT_TYPES = (
    FACT_PRESENT, FACT_ABSENT, FACT_ORDER, FACT_TABLE, FACT_MATH,
    FACT_CODE, FACT_XREF, FACT_IMAGE_REF,
)

SURFACE_NORMALIZED = ""
SURFACE_RAW = "raw"
_VALID_SURFACES = (SURFACE_NORMALIZED, SURFACE_RAW)

# Only this value of the ``checked`` field promotes a draft fact to an enforced
# one. Any other value (absent, "draft", "unverified") leaves it advisory.
CHECKED_VERIFIED = "verified"

_TABLE_DIRECTIONS = ("up", "down", "left", "right", "heading")

_WS_RE = re.compile(r"\s+")
_IMAGE_REF_RE = re.compile(r"!\[.*?\]\(.*?\)")


# -- Data model --------------------------------------------------------------


@dataclass(frozen=True)
class Fact:
    """One human-authored assertion about the converted markdown.

    ``checked`` is True only when the source record had ``checked == "verified"``.
    Type-specific fields: ``text``/``max_diffs`` (present/absent/math),
    ``sequence`` (order), ``cell``/``neighbors`` (table, where neighbors is a
    tuple of ``(direction, expected_text)`` with direction in
    up/down/left/right/heading). ``question`` is the optional authored
    blind readback prompt; Lane 3 ``check_facts`` ignores it.
    """

    id: str
    type: str
    checked: bool
    text: str = ""
    max_diffs: int = 0
    sequence: tuple[str, ...] = ()
    cell: str = ""
    neighbors: tuple[tuple[str, str], ...] = ()
    surface: str = ""
    table_heading: str = ""
    question: str = ""


@dataclass(frozen=True)
class FactCheck:
    id: str
    type: str
    verified: bool
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "verified": self.verified,
            "passed": self.passed,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class FactReport:
    pid: str
    checks: tuple[FactCheck, ...] = field(default_factory=tuple)

    def _enforced(self) -> list[FactCheck]:
        return [c for c in self.checks if c.verified]

    @property
    def passed(self) -> bool:
        # Only verified facts gate; a paper with no verified facts passes.
        return all(c.passed for c in self._enforced())

    @property
    def failed(self) -> bool:
        return not self.passed

    def failures(self) -> list[FactCheck]:
        return [c for c in self._enforced() if not c.passed]

    def by_type(self) -> dict[str, dict[str, float]]:
        """Macro-average per assertion type over VERIFIED facts only.

        ``{type: {passed, total, pass_rate}}``. A type with no verified facts is
        omitted so a reviewer sees only the types actually exercised.
        """
        out: dict[str, dict[str, float]] = {}
        for ftype in FACT_TYPES:
            group = [c for c in self._enforced() if c.type == ftype]
            if not group:
                continue
            passed = sum(1 for c in group if c.passed)
            out[ftype] = {
                "passed": passed,
                "total": len(group),
                "pass_rate": round(passed / len(group), 4),
            }
        return out

    def to_dict(self) -> dict:
        enforced = self._enforced()
        return {
            "pid": self.pid,
            "passed": self.passed,
            "verified_count": len(enforced),
            "total_count": len(self.checks),
            "by_type": self.by_type(),
            "checks": [c.to_dict() for c in self.checks],
        }


# -- Surfaces ----------------------------------------------------------------


_DISPLAY_MATH_DELIM_RE = re.compile(r"\\\[(.*?)\\\]", re.DOTALL)
_DOUBLED_BACKSLASH_CMD_RE = re.compile(r"\\\\(?=[A-Za-z])")


def _undouble_latex_backslashes(text: str) -> str:
    """Collapse ``\\\\command`` to ``\\command`` (a JSON/LLM escaping artifact).

    Found live via ``whisker-readback`` against the alliance-pod
    (2026-07-08): some formulas came back with every LaTeX command backslash
    doubled (``\\\\text{rms}``, ``\\\\cdot``, ``\\\\sin``, ``\\\\varphi``)
    while others in the same response used single backslashes. pylatexenc
    parses ``\\\\`` as the LaTeX line-break command, leaving ``text{rms}`` as
    literal text instead of folding it, so the doubled form silently fails to
    fold at all.

    Scoped to ``\\\\`` immediately followed by a letter: a genuine LaTeX
    line-break command is followed by whitespace, an optional ``[...]``
    spacing argument, or end of string, never directly by a command name, so
    this cannot misfire on an intentional line break.
    """
    return _DOUBLED_BACKSLASH_CMD_RE.sub("\\\\", text)


def _fold_display_math_delims(text: str) -> str:
    """Rewrite ``\\[...\\]`` display-math delimiters to ``\\(...\\)`` inline form.

    ``metrics.textblock2unicode`` (the shared Lane 2 text normalizer) only
    recognizes ``$...$``/``\\(...\\)`` by design (OmniDocBench's inline-only
    scope); extending its regex would shift the whole-document ``nid`` axis.
    Math FACTS need to compare the SAME formula whether the source or an LLM
    paraphrase wrote it as inline or display math (verified empirically: the
    alliance-pod reproduces an inline formula on its own display-math block,
    e.g. ``\\[\\n x^{2k} \\geq 0 \\n\\]``), so this pre-fold is scoped to
    ``_math_surface`` only.

    The captured content is whitespace-collapsed before rewrapping: ``metrics.
    _INLINE_REG`` has no ``re.DOTALL``, so an inline match cannot span the
    newlines a display-math block commonly wraps its formula in.
    """

    def _rewrap(match: re.Match[str]) -> str:
        flat = _WS_RE.sub(" ", match.group(1)).strip()
        return f"\\({flat}\\)"

    return _DISPLAY_MATH_DELIM_RE.sub(_rewrap, text)


def _math_surface(text: str) -> str:
    """Fold inline LaTeX to unicode and collapse whitespace, KEEPING symbols.

    Unlike ``normalized_text`` (which strips to alnum+CJK and would erase ``^``,
    ``_``, ``=``), this preserves math structure for a structural compare. No
    KaTeX/Node dependency: ``pylatexenc`` (already a dep) does the folding, so
    ``$x^2$`` and ``x^2`` compare equal. ``\\[...\\]`` display math is folded
    to the same surface as ``\\(...\\)`` inline math before unicode-folding.

    Case and braces are preserved so ``x^{2k}`` and ``x^2k`` remain
    distinguishable and ``X`` vs ``x`` is assertable. Deterministic.

    Doubled LaTeX command backslashes (``\\\\text`` instead of ``\\text``,
    an observed LLM-paraphrase escaping artifact) are undoubled before
    folding; see ``_undouble_latex_backslashes``.
    """
    folded = _fold_display_math_delims(_undouble_latex_backslashes(text))
    return _WS_RE.sub(" ", textblock2unicode(folded)).strip()


def _raw_surface(text: str) -> str:
    """Whitespace-normalize only, preserving operators, case, and punctuation.

    Unlike ``normalized_text`` (which strips to alnum+CJK), this keeps ``!=``,
    ``C++``, ``>=``, brackets, and case intact so operator-sensitive and
    revision-sensitive assertions (``surface: raw``) can distinguish ``x != y``
    from ``x == y`` and ``P1234R5`` from ``P1234R4``.
    """
    return _WS_RE.sub(" ", text).strip()


def _norm_cell(text: str) -> str:
    return _WS_RE.sub(" ", text).strip().lower()


# -- Fuzzy presence ----------------------------------------------------------


def _substring_edit_distance(needle: str, region: str) -> int:
    """Minimum edits to match ``needle`` as a substring of ``region``.

    Free-start / free-end Levenshtein DP: the match may begin and end anywhere
    in ``region`` at no cost, so the result is the fewest substitutions /
    insertions / deletions to align ``needle`` against its best window. Run only
    on a small region (the alignment hit widened by ``max_diffs``), not the whole
    document. Deterministic.
    """
    n, m = len(needle), len(region)
    if n == 0:
        return 0
    prev = [0] * (m + 1)  # empty needle prefix matches anywhere for free
    for i in range(1, n + 1):
        cur = [i] + [0] * m
        ch = needle[i - 1]
        for j in range(1, m + 1):
            cost = 0 if ch == region[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return min(prev)  # match may end anywhere


def _best_match(needle: str, haystack: str, max_diffs: int) -> int:
    """Start index of a within-budget match of ``needle`` in ``haystack``, or -1.

    Exact substring first (the common case). For ``max_diffs > 0`` rapidfuzz
    locates the approximate region, which is then widened by ``max_diffs`` and
    measured with the exact substring DP, since rapidfuzz's Indel-based window can
    trim boundary characters a substitution-aware match would keep.
    """
    if not needle:
        return 0
    idx = haystack.find(needle)
    if idx != -1:
        return idx
    if max_diffs <= 0:
        return -1
    al = fuzz.partial_ratio_alignment(needle, haystack)
    if al is None:
        return -1
    start = max(0, al.dest_start - max_diffs)
    end = min(len(haystack), al.dest_end + max_diffs)
    if _substring_edit_distance(needle, haystack[start:end]) <= max_diffs:
        return start
    return -1


def _present_within(needle: str, haystack: str, max_diffs: int) -> bool:
    """True if ``needle`` occurs in ``haystack`` within ``max_diffs`` edits."""
    return _best_match(needle, haystack, max_diffs) != -1


def _position_within(needle: str, haystack: str, max_diffs: int) -> int:
    """First near-match position of ``needle`` (or -1). Used for order checks."""
    return _best_match(needle, haystack, max_diffs)


# -- Table grids -------------------------------------------------------------


def _normalize_grid(grid: list[list[str]]) -> list[list[str]]:
    """Normalize all cells in a grid to lowercase + whitespace-collapsed."""
    return [[_norm_cell(c) for c in row] for row in grid]


def _all_tables(md: str) -> list[list[list[str]]]:
    """Return normalized grids from pipe, HTML, and fence-group tables.

    A fence group is not also an HTML or pipe grid, so the three lists
    do not count one table twice.
    """
    pipe = [_normalize_grid(g) for g in parse_pipe_tables(md)]
    html = [_normalize_grid(g) for g in parse_html_tables(md)]
    code = [_normalize_grid(g) for g in parse_code_table_groups(md)]
    return pipe + html + code


def _neighbor_value(grid: list[list[str]], r: int, c: int, direction: str) -> str | None:
    """Return the normalized neighbor cell text, or None if out of bounds."""
    if direction == "heading":
        return grid[0][c] if grid and c < len(grid[0]) else None
    dr, dc = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}[direction]
    nr, nc = r + dr, c + dc
    if 0 <= nr < len(grid) and 0 <= nc < len(grid[nr]):
        return grid[nr][nc]
    return None


def _check_neighbors(
    grid: list[list[str]], r: int, c: int, fact: Fact,
) -> tuple[bool, str]:
    """Verify neighbor values at (r, c) in grid against the fact."""
    for direction, expected in fact.neighbors:
        actual = _neighbor_value(grid, r, c, direction)
        want = _norm_cell(expected)
        if actual is None:
            return False, f"{direction} of {fact.cell!r} is out of bounds (want {expected!r})"
        if actual != want and _Lev.distance(actual, want) > fact.max_diffs:
            return False, f"{direction} of {fact.cell!r} is {actual!r}, want {expected!r}"
    return True, ""


def _check_table(md: str, fact: Fact) -> tuple[bool, str]:
    """Verify a target cell exists and its neighbors match. Deterministic.

    When ``table_heading`` is set, only tables whose header row contains the
    heading text are searched, and EVERY occurrence of the cell in those
    tables must satisfy the neighbor checks (fail-closed: a decoy table with
    the same heading and a conflicting row fails the fact instead of being
    shadowed by the genuine one). When ``table_heading`` is absent, the fact
    passes if ANY occurrence satisfies the neighbor checks (fixes the
    first-match-wins decoy-table false-pass without breaking cells that
    legitimately repeat across unrelated tables).
    """
    # golden-hook: a golden-grid compare (whole table committed as snapshot,
    # compared grid-vs-grid) catches column swaps and row reordering that
    # point-wise neighbor facts structurally cannot see; the heading-scoped
    # ALL-semantics below narrows the decoy gap but does not close it for
    # anchorless facts. Hang the golden table layer here, replacing the
    # per-cell candidate scan for papers that ship a golden grid.
    target = _norm_cell(fact.cell)
    heading_filter = _norm_cell(fact.table_heading) if fact.table_heading else ""
    tables = _all_tables(md)

    candidates: list[tuple[int, int, list[list[str]]]] = []
    for grid in tables:
        if heading_filter:
            if not grid or not any(heading_filter in cell for cell in grid[0]):
                continue
        for r, row in enumerate(grid):
            for c, value in enumerate(row):
                if value == target:
                    candidates.append((r, c, grid))

    if not candidates:
        return False, f"cell {fact.cell!r} not found in any table"

    if heading_filter:
        for r, c, grid in candidates:
            ok, detail = _check_neighbors(grid, r, c, fact)
            if not ok:
                return False, f"occurrence at row {r}: {detail}"
        return True, ""

    last_detail = ""
    for r, c, grid in candidates:
        ok, detail = _check_neighbors(grid, r, c, fact)
        if ok:
            return True, ""
        last_detail = detail

    return False, last_detail


# -- Evaluation --------------------------------------------------------------


def _surface_for(fact: Fact, md: str) -> tuple[str, str]:
    """Return (needle, haystack) using the fact's surface mode."""
    if fact.surface == SURFACE_RAW:
        return _raw_surface(fact.text), _raw_surface(md)
    return normalized_text(fact.text), normalized_text(md)


def _evaluate(md: str, fact: Fact) -> tuple[bool, str]:
    if fact.type == FACT_PRESENT:
        needle, haystack = _surface_for(fact, md)
        ok = _present_within(needle, haystack, fact.max_diffs)
        return ok, "" if ok else f"required text {fact.text!r} absent"
    if fact.type == FACT_ABSENT:
        needle, haystack = _surface_for(fact, md)
        ok = not _present_within(needle, haystack, fact.max_diffs)
        return ok, "" if ok else f"forbidden text {fact.text!r} present"
    if fact.type == FACT_MATH:
        ok = _present_within(_math_surface(fact.text), _math_surface(md), fact.max_diffs)
        return ok, "" if ok else f"math {fact.text!r} absent (structural compare)"
    if fact.type == FACT_ORDER:
        if fact.surface == SURFACE_RAW:
            haystack = _raw_surface(md)
            items = [_raw_surface(item) for item in fact.sequence]
        else:
            haystack = normalized_text(md)
            items = [normalized_text(item) for item in fact.sequence]
        prev_pos = -1
        prev_item: str | None = None
        for item in items:
            pos = _position_within(item, haystack, fact.max_diffs)
            if pos == -1:
                return False, f"ordered item {item!r} absent"
            if pos <= prev_pos:
                return False, f"{item!r} not after {prev_item!r}"
            prev_pos = pos
            prev_item = item
        return True, ""
    if fact.type == FACT_TABLE:
        return _check_table(md, fact)
    if fact.type == FACT_CODE:
        needle = _raw_surface(fact.text)
        haystack = _raw_surface(md)
        ok = _present_within(needle, haystack, fact.max_diffs)
        return ok, "" if ok else f"code snippet {fact.text!r} absent"
    if fact.type == FACT_XREF:
        needle = _raw_surface(fact.text)
        haystack = _raw_surface(md)
        ok = _present_within(needle, haystack, fact.max_diffs)
        return ok, "" if ok else f"cross-reference {fact.text!r} absent"
    if fact.type == FACT_IMAGE_REF:
        ok = bool(_IMAGE_REF_RE.search(md))
        if not ok:
            return False, "no image reference ![...](...) found"
        if fact.text:
            needle = _raw_surface(fact.text)
            haystack = _raw_surface(md)
            ok = _present_within(needle, haystack, fact.max_diffs)
            return ok, "" if ok else f"image reference text {fact.text!r} absent"
        return True, ""
    raise ValueError(f"unknown fact type {fact.type!r}")


def check_facts(md: str, facts: list[Fact], pid: str = "") -> FactReport:
    """Evaluate every fact against the candidate markdown. Deterministic.

    Each fact is an independent pass/fail. Unverified facts are evaluated and
    reported but flagged ``verified=False``; only verified facts gate the report
    (see ``FactReport.passed``).
    """
    checks: list[FactCheck] = []
    for fact in facts:
        passed, detail = _evaluate(md, fact)
        note = detail
        if not fact.checked:
            # Carry the evaluation for visibility but make the non-gating status
            # explicit so an author knows a draft fact is not yet enforced.
            note = (detail + " " if detail else "") + "(unverified, not gated)"
        checks.append(FactCheck(fact.id, fact.type, fact.checked, passed, note.strip()))
    return FactReport(pid=pid, checks=tuple(checks))


# -- Loading / validation ----------------------------------------------------


def _require_text(rec: dict, fid: str) -> str:
    text = rec.get("text")
    if not isinstance(text, str) or not text:
        raise ValueError(f"fact {fid!r}: 'text' must be a non-empty string")
    return text


def _max_diffs(rec: dict, fid: str) -> int:
    raw = rec.get("max_diffs", 0)
    if not isinstance(raw, int) or isinstance(raw, bool) or raw < 0:
        raise ValueError(f"fact {fid!r}: 'max_diffs' must be a non-negative integer")
    return raw


def _surface_mode(rec: dict, fid: str) -> str:
    raw = rec.get("surface", "")
    if raw not in _VALID_SURFACES:
        raise ValueError(
            f"fact {fid!r}: 'surface' {raw!r} not in {list(_VALID_SURFACES)}"
        )
    return raw


def _question_field(rec: dict, fid: str) -> str:
    raw = rec.get("question", "")
    if not isinstance(raw, str):
        raise ValueError(f"fact {fid!r}: 'question' must be a string")
    return raw


def _fact_from_record(rec: dict, index: int) -> Fact:
    if not isinstance(rec, dict):
        raise ValueError(f"fact #{index} must be a JSON object")
    ftype = rec.get("type")
    if ftype not in FACT_TYPES:
        raise ValueError(f"fact #{index}: 'type' {ftype!r} not in {list(FACT_TYPES)}")
    fid = str(rec.get("id", f"{ftype}[{index}]"))
    checked = rec.get("checked") == CHECKED_VERIFIED
    max_diffs = _max_diffs(rec, fid)
    surface = _surface_mode(rec, fid)
    question = _question_field(rec, fid)

    if ftype in (FACT_PRESENT, FACT_ABSENT, FACT_MATH):
        return Fact(id=fid, type=ftype, checked=checked,
                    text=_require_text(rec, fid), max_diffs=max_diffs,
                    surface=surface, question=question)

    if ftype in (FACT_CODE, FACT_XREF):
        return Fact(id=fid, type=ftype, checked=checked,
                    text=_require_text(rec, fid), max_diffs=max_diffs,
                    surface=SURFACE_RAW, question=question)

    if ftype == FACT_IMAGE_REF:
        text = rec.get("text", "")
        if not isinstance(text, str):
            raise ValueError(f"fact {fid!r}: 'text' must be a string")
        return Fact(id=fid, type=ftype, checked=checked,
                    text=text, max_diffs=max_diffs, surface=SURFACE_RAW,
                    question=question)

    if ftype == FACT_ORDER:
        seq = rec.get("sequence")
        if (
            not isinstance(seq, list)
            or len(seq) < 2
            or not all(isinstance(s, str) and s for s in seq)
        ):
            raise ValueError(
                f"fact {fid!r}: 'sequence' must be a list of >=2 non-empty strings"
            )
        return Fact(id=fid, type=ftype, checked=checked,
                    sequence=tuple(seq), max_diffs=max_diffs, surface=surface,
                    question=question)

    # FACT_TABLE
    cell = rec.get("cell")
    if not isinstance(cell, str) or not cell:
        raise ValueError(f"fact {fid!r}: 'cell' must be a non-empty string")
    raw_neighbors = rec.get("neighbors")
    if not isinstance(raw_neighbors, dict) or not raw_neighbors:
        raise ValueError(f"fact {fid!r}: 'neighbors' must be a non-empty JSON object")
    neighbors: list[tuple[str, str]] = []
    for direction, expected in raw_neighbors.items():
        if direction not in _TABLE_DIRECTIONS:
            raise ValueError(
                f"fact {fid!r}: neighbor direction {direction!r} not in "
                f"{list(_TABLE_DIRECTIONS)}"
            )
        if not isinstance(expected, str):
            raise ValueError(f"fact {fid!r}: neighbor {direction!r} must be a string")
        neighbors.append((direction, expected))
    # Sort by the fixed direction order so evaluation and reporting are stable.
    neighbors.sort(key=lambda dv: _TABLE_DIRECTIONS.index(dv[0]))
    table_heading = rec.get("table_heading", "")
    if not isinstance(table_heading, str):
        raise ValueError(f"fact {fid!r}: 'table_heading' must be a string")
    if checked and not table_heading.strip():
        raise ValueError(
            f"fact {fid!r}: verified table facts require table_heading"
        )
    return Fact(id=fid, type=ftype, checked=checked, cell=cell,
                neighbors=tuple(neighbors), max_diffs=max_diffs,
                table_heading=table_heading, question=question)


def facts_from_records(records: list[dict], pid: str = "") -> list[Fact]:
    """Validate and build ``Fact`` objects from parsed JSONL records.

    Hand-authored config: a malformed record raises ``ValueError`` rather than
    silently disabling a comprehension check. ``pid`` is accepted for symmetry
    with the loader and is not otherwise used here.
    """
    if not isinstance(records, list):
        raise ValueError("facts records must be a list")
    seen: set[str] = set()
    facts: list[Fact] = []
    for i, rec in enumerate(records):
        fact = _fact_from_record(rec, i)
        if fact.id in seen:
            raise ValueError(f"duplicate fact id {fact.id!r}")
        seen.add(fact.id)
        facts.append(fact)
    return facts


def parse_facts_jsonl(text: str, pid: str = "") -> list[Fact]:
    """Parse ``<pid>.facts.jsonl`` content (one JSON fact per line).

    Blank lines are skipped. A malformed line raises ``ValueError`` (with the
    1-based line number) so a typo surfaces loudly. Pure: the CLI reads the file.
    """
    records: list[dict] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            records.append(json.loads(stripped))
        except json.JSONDecodeError as exc:
            raise ValueError(f"facts line {lineno}: invalid JSON: {exc}") from exc
    return facts_from_records(records, pid)


# -- Auto-baseline checks (olmOCR pattern) -----------------------------------

_ALNUM_RE = re.compile(r"[a-zA-Z0-9]")
_REPEATED_NGRAM_RE = re.compile(r"(.{3,})\1{4,}")


def auto_baseline_checks(md: str) -> list[FactCheck]:
    """Run zero-authoring baseline sanity checks on converted markdown.

    Inspired by olmOCR's per-page BasePDFTest/BaselineTest: non-empty
    alphanumeric content, no long repeating n-grams (mojibake/extraction
    debris). These require no human authoring and kill vacuous green for the
    entire fleet. All checks are always-verified (they are structural truths
    about any valid conversion, not paper-specific claims).

    Returns FactCheck objects that can be appended to an authored FactReport.
    """
    checks: list[FactCheck] = []

    alnum_count = len(_ALNUM_RE.findall(md))
    nonempty_ok = alnum_count >= BASELINE_MIN_ALNUM_CHARS
    checks.append(FactCheck(
        id="baseline-nonempty",
        type="baseline",
        verified=True,
        passed=nonempty_ok,
        detail="" if nonempty_ok else (
            f"only {alnum_count} alnum chars "
            f"(need >= {BASELINE_MIN_ALNUM_CHARS})"
        ),
    ))

    repeated_chars = sum(
        len(m.group(0)) for m in _REPEATED_NGRAM_RE.finditer(md)
    )
    total = max(len(md), 1)
    repeated_ratio = repeated_chars / total
    ngram_ok = repeated_ratio <= BASELINE_MAX_REPEATED_NGRAM_RATIO
    checks.append(FactCheck(
        id="baseline-no-repeated-ngrams",
        type="baseline",
        verified=True,
        passed=ngram_ok,
        detail="" if ngram_ok else (
            f"repeated n-gram ratio {repeated_ratio:.2f} "
            f"exceeds {BASELINE_MAX_REPEATED_NGRAM_RATIO}"
        ),
    ))

    return checks
