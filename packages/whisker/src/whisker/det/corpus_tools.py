#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Corpus authoring tools for whisker comprehension facts.

Two helpers for building the source-verified comprehension corpus:

1. ``stratify_candidates`` — classify papers by structural strata (tables,
   math, code, footnotes, multi-column) and return stratified candidates
   that currently have zero fact coverage.
2. ``draft_facts_scaffold`` — generate a ``<pid>.facts.jsonl`` skeleton
   with ``checked: draft`` entries that a human can review and promote
   to ``checked: verified``.

All functions are whisker-local; they read via the paperstore public API
and do not touch other packages.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from whisker.tables import parse_html_tables, parse_pipe_tables

__all__ = [
    "StratumInfo",
    "draft_facts_scaffold",
    "stratify_candidates",
]

# -- Stratum detection heuristics -------------------------------------------

_DISPLAY_MATH_RE = re.compile(r"\$\$.*?\$\$", re.DOTALL)
_INLINE_MATH_RE = re.compile(r"(?<!\$)\$(?!\$).*?(?<!\$)\$(?!\$)")
_CODE_FENCE_RE = re.compile(r"^\s*(```|~~~)", re.MULTILINE)
_FENCED_BLOCK_RE = re.compile(r"^\s*(```|~~~).*?^\s*\1\s*$", re.DOTALL | re.MULTILINE)
_FOOTNOTE_REF_RE = re.compile(r"\[\^([^\]\r\n]+)\](?!:)")
_FOOTNOTE_DEF_RE = re.compile(r"^\[\^([^\]\r\n]+)\]:", re.MULTILINE)
_HTML_FOOTNOTE_REF_RE = re.compile(r"<sup>(\d+)</sup>", re.IGNORECASE)
_HTML_FOOTNOTE_DEF_RE = re.compile(r"^(\d+)\.\s+.*↩︎\s*$", re.MULTILINE)
_IMAGE_REF_RE = re.compile(r"!\[.*?\]\(.*?\)")


def _strip_fenced_blocks(md: str) -> str:
    """Remove fenced code block contents before prose-level regex counting.

    ``$`` is a legal character in code identifiers (P4234R0 uses ``$``-prefixed
    names throughout), so counting ``$$...$$`` on raw markdown misclassified
    code-heavy papers as display-math papers (red-team finding Jul 2026).
    """
    return _FENCED_BLOCK_RE.sub("", md)

STRATUM_TABLE = "table"
STRATUM_HTML_TABLE = "html_table"
STRATUM_DISPLAY_MATH = "display_math"
STRATUM_CODE_HEAVY = "code_heavy"
STRATUM_FOOTNOTES = "footnotes"
STRATUM_IMAGES = "images"

CODE_HEAVY_FENCE_THRESHOLD = 3


@dataclass
class StratumInfo:
    """Structural classification of a paper."""
    pid: str
    strata: list[str] = field(default_factory=list)
    pipe_table_count: int = 0
    html_table_count: int = 0
    display_math_count: int = 0
    code_fence_count: int = 0
    footnote_count: int = 0
    image_count: int = 0
    has_facts: bool = False


def classify_paper(pid: str, md: str) -> StratumInfo:
    """Classify a paper's structural features."""
    info = StratumInfo(pid=pid)

    prose = _strip_fenced_blocks(md)
    info.pipe_table_count = len(parse_pipe_tables(md))
    info.html_table_count = len(parse_html_tables(md))
    info.display_math_count = len(_DISPLAY_MATH_RE.findall(prose))
    info.code_fence_count = len(_CODE_FENCE_RE.findall(md)) // 2
    canonical_footnotes = set(_FOOTNOTE_REF_RE.findall(md)) & set(_FOOTNOTE_DEF_RE.findall(md))
    html_footnotes = set(_HTML_FOOTNOTE_REF_RE.findall(md)) & set(_HTML_FOOTNOTE_DEF_RE.findall(md))
    info.footnote_count = len(canonical_footnotes) + len(html_footnotes)
    info.image_count = len(_IMAGE_REF_RE.findall(md))

    if info.pipe_table_count > 0:
        info.strata.append(STRATUM_TABLE)
    if info.html_table_count > 0:
        info.strata.append(STRATUM_HTML_TABLE)
    if info.display_math_count > 0:
        info.strata.append(STRATUM_DISPLAY_MATH)
    if info.code_fence_count >= CODE_HEAVY_FENCE_THRESHOLD:
        info.strata.append(STRATUM_CODE_HEAVY)
    if info.footnote_count > 0:
        info.strata.append(STRATUM_FOOTNOTES)
    if info.image_count > 0:
        info.strata.append(STRATUM_IMAGES)

    return info


def stratify_candidates(
    backend,
    corpus_dir: Path,
    *,
    max_per_stratum: int = 5,
) -> dict[str, list[StratumInfo]]:
    """Return stratified candidates with zero fact coverage.

    Papers that already have a ``.facts.jsonl`` in ``corpus_dir`` are
    excluded (they already have coverage). Results are grouped by stratum.
    """
    facts_suffix = ".facts.jsonl"
    existing_pids = {
        f.name[: -len(facts_suffix)].upper()
        for f in corpus_dir.glob(f"*{facts_suffix}")
    }

    all_pids = backend.list_all_paper_ids()
    by_stratum: dict[str, list[StratumInfo]] = {
        STRATUM_TABLE: [],
        STRATUM_HTML_TABLE: [],
        STRATUM_DISPLAY_MATH: [],
        STRATUM_CODE_HEAVY: [],
        STRATUM_FOOTNOTES: [],
        STRATUM_IMAGES: [],
    }

    for pid in sorted(all_pids):
        if pid in existing_pids:
            continue
        try:
            md = backend.get_paper_md(pid)
        except Exception:
            continue

        info = classify_paper(pid, md)
        for stratum in info.strata:
            bucket = by_stratum.get(stratum, [])
            if len(bucket) < max_per_stratum:
                bucket.append(info)
                by_stratum[stratum] = bucket

    return by_stratum


# -- Draft facts scaffold ---------------------------------------------------


def draft_facts_scaffold(pid: str, md: str) -> list[dict]:
    """Generate draft fact records for a paper.

    The output is a list of JSON-serializable dicts, each with
    ``checked: "draft"`` (never ``"verified"``). A human reviews, adjusts
    values, and promotes to ``verified`` to complete the blessing.
    """
    info = classify_paper(pid, md)
    records: list[dict] = []
    idx = 0

    lines = md.split("\n")
    headings = [ln.lstrip("#").strip() for ln in lines if ln.startswith("#")]
    if len(headings) >= 2:
        records.append({
            "id": f"order-headings-{idx}",
            "type": "order",
            "sequence": headings[:3],
            "checked": "draft",
        })
        idx += 1

    if headings:
        records.append({
            "id": f"present-title-{idx}",
            "type": "present",
            "text": headings[0][:80],
            "checked": "draft",
        })
        idx += 1

    pipe_tables = parse_pipe_tables(md)
    for ti, grid in enumerate(pipe_tables[:2]):
        if len(grid) >= 2 and len(grid[0]) >= 2:
            cell = grid[1][0]
            right = grid[1][1] if len(grid[1]) > 1 else ""
            heading = grid[0][0]
            records.append({
                "id": f"table-pipe-{ti}-{idx}",
                "type": "table",
                "cell": cell,
                "neighbors": {"right": right, "heading": heading},
                "table_heading": heading,
                "checked": "draft",
            })
            idx += 1

    html_tables = parse_html_tables(md)
    for ti, grid in enumerate(html_tables[:2]):
        if len(grid) >= 2 and len(grid[0]) >= 2:
            cell = grid[1][0]
            right = grid[1][1] if len(grid[1]) > 1 else ""
            heading = grid[0][0]
            records.append({
                "id": f"table-html-{ti}-{idx}",
                "type": "table",
                "cell": cell,
                "neighbors": {"right": right, "heading": heading},
                "table_heading": heading,
                "checked": "draft",
            })
            idx += 1

    display_math = _DISPLAY_MATH_RE.findall(_strip_fenced_blocks(md))
    for mi, formula in enumerate(display_math[:2]):
        clean = formula.strip("$").strip()[:120]
        records.append({
            "id": f"math-{mi}-{idx}",
            "type": "math",
            "text": clean,
            "checked": "draft",
        })
        idx += 1

    if info.code_fence_count > 0:
        in_fence = False
        code_lines: list[str] = []
        for line in lines:
            if re.match(r"^\s*(```|~~~)", line):
                if in_fence and code_lines:
                    snippet = " ".join(code_lines[:3]).strip()[:100]
                    if snippet:
                        records.append({
                            "id": f"code-{idx}",
                            "type": "code",
                            "text": snippet,
                            "checked": "draft",
                        })
                        idx += 1
                        break
                    code_lines = []
                in_fence = not in_fence
            elif in_fence:
                code_lines.append(line.strip())

    if info.image_count > 0:
        records.append({
            "id": f"image-ref-{idx}",
            "type": "image_ref",
            "text": "",
            "checked": "draft",
        })
        idx += 1

    xrefs = re.findall(r"\[([PpNn]\d{4}[Rr]\d+)\]", md)
    if xrefs:
        records.append({
            "id": f"xref-{idx}",
            "type": "xref",
            "text": f"[{xrefs[0]}]",
            "checked": "draft",
        })
        idx += 1

    return records


def write_draft_facts(pid: str, records: list[dict], out_dir: Path) -> Path:
    """Write draft facts to a .facts.jsonl file."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{pid.lower()}.facts.jsonl"
    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
