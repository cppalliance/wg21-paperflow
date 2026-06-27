#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Lane 3 comprehension: deterministic, human-verified fact assertions.

The fuzzy axes (Lane 2: nid/teds/mhs) measure FIDELITY (is the output close to a
reference) and the golden lane (Lane 1) measures STABILITY (did the output
change). Neither proves COMPREHENSION: that an LLM consuming the markdown can
still recover the paper's facts. A faithful-looking reflow can still scramble a
table so "row 3, column 2" no longer reads correctly, or drop a formula's
exponent, and every fidelity metric can stay green.

Across the 28 surveyed converter repos, only ``olmocr`` tests this, via
deterministic, machine-checkable fact assertions: human-authored statements
(``present``/``absent``/``order``/``table``/``math``) verified against the source
PDF/HTML by a person, with NO LLM in the scoring loop. whisker adopts that model
verbatim. This also sidesteps the ground-truth-provenance problem (no repo has an
automatic "this file is 100% correct" oracle): a handful of human-verified facts
per paper are cheap to author and independent of any single ``tomd`` output.

Provenance gate: a fact is enforced ONLY when ``checked == "verified"`` (a human
confirmed it against the source). Unverified (draft) facts are loaded and
reported but never gate, so authoring a fact and blessing it are separate, auditable
steps.

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

from whisker.metrics import normalized_text, textblock2unicode

__all__ = [
    "FACTS_KIND",
    "FACT_TYPES",
    "Fact",
    "FactCheck",
    "FactReport",
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
FACT_TYPES = (FACT_PRESENT, FACT_ABSENT, FACT_ORDER, FACT_TABLE, FACT_MATH)

# Only this value of the ``checked`` field promotes a draft fact to an enforced
# one. Any other value (absent, "draft", "unverified") leaves it advisory.
CHECKED_VERIFIED = "verified"

_TABLE_DIRECTIONS = ("up", "down", "left", "right", "heading")

_WS_RE = re.compile(r"\s+")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


# -- Data model --------------------------------------------------------------


@dataclass(frozen=True)
class Fact:
    """One human-authored assertion about the converted markdown.

    ``checked`` is True only when the source record had ``checked == "verified"``.
    Type-specific fields: ``text``/``max_diffs`` (present/absent/math),
    ``sequence`` (order), ``cell``/``neighbors`` (table, where neighbors is a
    tuple of ``(direction, expected_text)`` with direction in
    up/down/left/right/heading).
    """

    id: str
    type: str
    checked: bool
    text: str = ""
    max_diffs: int = 0
    sequence: tuple[str, ...] = ()
    cell: str = ""
    neighbors: tuple[tuple[str, str], ...] = ()


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


def _math_surface(text: str) -> str:
    """Fold inline LaTeX to unicode and collapse whitespace, KEEPING symbols.

    Unlike ``normalized_text`` (which strips to alnum+CJK and would erase ``^``,
    ``_``, ``=``), this preserves math structure for a structural compare. No
    KaTeX/Node dependency: ``pylatexenc`` (already a dep) does the folding, so
    ``$x^2$`` and ``x^2`` compare equal. Deterministic.
    """
    return _WS_RE.sub(" ", textblock2unicode(text)).strip().lower()


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


def _split_cells(line: str) -> list[str]:
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    return [_norm_cell(c) for c in body.split("|")]


def _parse_pipe_tables(md: str) -> list[list[list[str]]]:
    """Return each markdown pipe table as a grid of normalized cell text.

    Header row + separator + body rows; fenced code is skipped so pipes inside
    code do not masquerade as tables. Mirrors the bench table detector but emits
    cell grids (not HTML) for neighbor-graph checks. Deterministic.
    """
    lines = md.splitlines()
    in_fence = False
    tables: list[list[list[str]]] = []
    i = 0
    while i < len(lines):
        if _FENCE_RE.match(lines[i]):
            in_fence = not in_fence
            i += 1
            continue
        if in_fence:
            i += 1
            continue
        is_sep = (
            i + 1 < len(lines)
            and "|" in lines[i + 1]
            and _TABLE_SEP_RE.match(lines[i + 1])
        )
        if "|" in lines[i] and is_sep:
            rows = [_split_cells(lines[i])]
            j = i + 2
            while j < len(lines) and "|" in lines[j] and lines[j].strip():
                rows.append(_split_cells(lines[j]))
                j += 1
            tables.append(rows)
            i = j
            continue
        i += 1
    return tables


def _neighbor_value(grid: list[list[str]], r: int, c: int, direction: str) -> str | None:
    """Return the normalized neighbor cell text, or None if out of bounds."""
    if direction == "heading":
        return grid[0][c] if grid and c < len(grid[0]) else None
    dr, dc = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}[direction]
    nr, nc = r + dr, c + dc
    if 0 <= nr < len(grid) and 0 <= nc < len(grid[nr]):
        return grid[nr][nc]
    return None


def _check_table(md: str, fact: Fact) -> tuple[bool, str]:
    """Verify a target cell exists and its neighbors match. Deterministic."""
    target = _norm_cell(fact.cell)
    tables = _parse_pipe_tables(md)
    located: tuple[int, int, list[list[str]]] | None = None
    for grid in tables:
        for r, row in enumerate(grid):
            for c, value in enumerate(row):
                if value == target:
                    located = (r, c, grid)
                    break
            if located:
                break
        if located:
            break
    if located is None:
        return False, f"cell {fact.cell!r} not found in any table"

    r, c, grid = located
    for direction, expected in fact.neighbors:
        actual = _neighbor_value(grid, r, c, direction)
        want = _norm_cell(expected)
        if actual is None:
            return False, f"{direction} of {fact.cell!r} is out of bounds (want {expected!r})"
        if actual != want and _Lev.distance(actual, want) > fact.max_diffs:
            return False, f"{direction} of {fact.cell!r} is {actual!r}, want {expected!r}"
    return True, ""


# -- Evaluation --------------------------------------------------------------


def _evaluate(md: str, fact: Fact) -> tuple[bool, str]:
    if fact.type == FACT_PRESENT:
        ok = _present_within(normalized_text(fact.text), normalized_text(md), fact.max_diffs)
        return ok, "" if ok else f"required text {fact.text!r} absent"
    if fact.type == FACT_ABSENT:
        ok = not _present_within(
            normalized_text(fact.text), normalized_text(md), fact.max_diffs
        )
        return ok, "" if ok else f"forbidden text {fact.text!r} present"
    if fact.type == FACT_MATH:
        ok = _present_within(_math_surface(fact.text), _math_surface(md), fact.max_diffs)
        return ok, "" if ok else f"math {fact.text!r} absent (structural compare)"
    if fact.type == FACT_ORDER:
        haystack = normalized_text(md)
        prev_pos = -1
        prev_item: str | None = None
        for item in fact.sequence:
            pos = _position_within(normalized_text(item), haystack, fact.max_diffs)
            if pos == -1:
                return False, f"ordered item {item!r} absent"
            if pos <= prev_pos:
                return False, f"{item!r} not after {prev_item!r}"
            prev_pos = pos
            prev_item = item
        return True, ""
    if fact.type == FACT_TABLE:
        return _check_table(md, fact)
    # Unreachable: type is validated at construction.
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


def _fact_from_record(rec: dict, index: int) -> Fact:
    if not isinstance(rec, dict):
        raise ValueError(f"fact #{index} must be a JSON object")
    ftype = rec.get("type")
    if ftype not in FACT_TYPES:
        raise ValueError(f"fact #{index}: 'type' {ftype!r} not in {list(FACT_TYPES)}")
    fid = str(rec.get("id", f"{ftype}[{index}]"))
    checked = rec.get("checked") == CHECKED_VERIFIED
    max_diffs = _max_diffs(rec, fid)

    if ftype in (FACT_PRESENT, FACT_ABSENT, FACT_MATH):
        return Fact(id=fid, type=ftype, checked=checked,
                    text=_require_text(rec, fid), max_diffs=max_diffs)

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
                    sequence=tuple(seq), max_diffs=max_diffs)

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
    return Fact(id=fid, type=ftype, checked=checked, cell=cell,
                neighbors=tuple(neighbors), max_diffs=max_diffs)


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
