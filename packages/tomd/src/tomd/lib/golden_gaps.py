#
# Copyright (c) 2026 Sean Parsons (sean.parsons@muckrack.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Deterministic gap locator and issue drafter for golden QA.

A reporting layer on top of the comparator (`golden_compare`): it locates the
per-axis divergences between tomd's output and the blessed ideal, then drafts
ready-to-file GitHub issues carrying the objectivity triple (axis score, located
divergence, violated contract rule). Pure: no LLM, no network, no `gh` calls.
The maintainer reviews a draft and files it by hand.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass

from tomd.lib.golden_compare import NormalizedDoc, compare, normalize


@dataclass(frozen=True)
class Gap:
    axis: str    # "frontmatter" | "heading" | "list" | "code" | "table" | "text"
    kind: str    # "wrong-level" | "missing" | "extra" | "wrong" | "drift"
    tomd: str    # what tomd produced
    ideal: str   # what the ideal has
    rule: str    # the cited contract rule the divergence violates


# Contract rules (the third leg of the objectivity triple): the tomd CLAUDE.md
# line each divergence kind violates.
_HEADING_LEVEL_RULE = ("Body headings start at H2 (H1 is the front-matter title); "
                       "the level is the section-numbering depth plus one.")
_HEADING_PRESENCE_RULE = ("Every source heading must appear in the output, and only "
                          "real headings (no promoted prose, no dropped sections).")
_LIST_RULE = ("Nested list items must be detected and nested, not flattened to prose "
              "(the nested-bullet bug).")
_CODE_RULE = ("Code goes in fenced blocks with a language label: one fence per source "
              "listing, never split at a page break, never merged.")
_TABLE_RULE = ("Tables are reconstructed with the source's row and column counts; do "
               "not mis-split a table.")
_FRONTMATTER_RULE = ("WG21 metadata becomes YAML front matter in the fixed key order: "
                     "title, document, date, intent, audience, reply-to.")
_TEXT_RULE = "Content is verbatim: the converter fixes structure, never content."

# Best-effort symptom-to-module pointer, mirroring the tomd-surgical-edits map.
_ORIGIN = {
    "heading": "lib/pdf/structure.py heading intelligence (PDF) or lib/html/render.py (HTML)",
    "list": "lib/pdf/structure.py list detection (PDF) or lib/html/render.py (HTML)",
    "code": "lib/pdf/structure.py + lib/pdf/emit.py code blocks (PDF) or lib/html/render.py (HTML)",
    "table": "lib/pdf/table.py (PDF) or lib/html/render.py table handling (HTML)",
    "frontmatter": "api.py _canonicalize_front_matter and the per-format metadata extractors",
    "text": "lib/pdf/extract.py / lib/pdf/cleanup.py (PDF) or lib/html/render.py (HTML)",
}

# tomd's text axis is 1.0 on identical prose; anything below means real drift.
_TEXT_DRIFT_THRESHOLD = 0.999


def _headings(doc: NormalizedDoc) -> list[tuple[int, str]]:
    return [(blk.level, blk.text) for blk in doc.blocks if blk.kind == "heading"]


def _heading_gaps(tomd: NormalizedDoc, ideal: NormalizedDoc) -> list[Gap]:
    aa = _headings(tomd)
    bb = _headings(ideal)
    opcodes = difflib.SequenceMatcher(None, [t for _, t in aa], [t for _, t in bb])
    gaps: list[Gap] = []
    for tag, i1, i2, j1, j2 in opcodes.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                al, atext = aa[i1 + k]
                bl, btext = bb[j1 + k]
                if al != bl:
                    gaps.append(Gap("heading", "wrong-level",
                                    f"H{al} '{atext}'", f"H{bl} '{btext}'",
                                    _HEADING_LEVEL_RULE))
        elif tag in ("replace", "insert"):
            for bl, btext in bb[j1:j2]:
                gaps.append(Gap("heading", "missing", "(absent)",
                                f"H{bl} '{btext}'", _HEADING_PRESENCE_RULE))
            if tag == "replace":
                for al, atext in aa[i1:i2]:
                    gaps.append(Gap("heading", "extra", f"H{al} '{atext}'",
                                    "(absent)", _HEADING_PRESENCE_RULE))
        elif tag == "delete":
            for al, atext in aa[i1:i2]:
                gaps.append(Gap("heading", "extra", f"H{al} '{atext}'",
                                "(absent)", _HEADING_PRESENCE_RULE))
    return gaps


def _list_gaps(tomd: NormalizedDoc, ideal: NormalizedDoc) -> list[Gap]:
    a = [(e.depth, e.marker, e.ordered) for blk in tomd.blocks
         if blk.kind == "list" for e in blk.items]
    b = [(e.depth, e.marker, e.ordered) for blk in ideal.blocks
         if blk.kind == "list" for e in blk.items]
    if a == b:
        return []
    return [Gap("list", "wrong", f"{len(a)} list item(s)",
                f"{len(b)} list item(s)", _LIST_RULE)]


def _code_gaps(tomd: NormalizedDoc, ideal: NormalizedDoc) -> list[Gap]:
    a = [(blk.code_lang, blk.code_lines) for blk in tomd.blocks if blk.kind == "code"]
    b = [(blk.code_lang, blk.code_lines) for blk in ideal.blocks if blk.kind == "code"]
    if a == b:
        return []
    return [Gap("code", "wrong", f"{len(a)} fence(s)", f"{len(b)} fence(s)", _CODE_RULE)]


def _table_gaps(tomd: NormalizedDoc, ideal: NormalizedDoc) -> list[Gap]:
    a = [(blk.table_rows, blk.table_cols) for blk in tomd.blocks if blk.kind == "table"]
    b = [(blk.table_rows, blk.table_cols) for blk in ideal.blocks if blk.kind == "table"]
    if a == b:
        return []
    return [Gap("table", "wrong", f"{a} (rows,cols)", f"{b} (rows,cols)", _TABLE_RULE)]


def _frontmatter_gaps(tomd: NormalizedDoc, ideal: NormalizedDoc) -> list[Gap]:
    if tomd.front_matter_keys == ideal.front_matter_keys:
        return []
    return [Gap("frontmatter", "wrong", str(tomd.front_matter_keys),
                str(ideal.front_matter_keys), _FRONTMATTER_RULE)]


def locate_gaps(tomd_md: str, ideal_md: str) -> list[Gap]:
    """Locate the per-axis divergences between tomd output and the ideal.

    Heading gaps are granular (which heading, what level); list/code/table/
    front-matter gaps are coarse (count or dimension mismatch); the text gap is
    a single drift flag when the verbatim-text axis falls below 1.0.
    """
    tomd = normalize(tomd_md)
    ideal = normalize(ideal_md)
    gaps: list[Gap] = []
    gaps += _frontmatter_gaps(tomd, ideal)
    gaps += _heading_gaps(tomd, ideal)
    gaps += _list_gaps(tomd, ideal)
    gaps += _code_gaps(tomd, ideal)
    gaps += _table_gaps(tomd, ideal)
    if compare(tomd_md, ideal_md).axes["text"].score < _TEXT_DRIFT_THRESHOLD:
        gaps.append(Gap("text", "drift", "(prose diverges from source)",
                        "(verbatim source text)", _TEXT_RULE))
    return gaps


def draft_issues(stem: str, gaps: list[Gap], scores: dict[str, float]) -> list[str]:
    """One ready-to-file issue draft per axis that has gaps.

    Each draft carries the objectivity triple: the axis score, the located
    divergences, and the cited contract rule, plus a repro command and a
    suggested origin module.
    """
    pid = stem.upper()
    by_axis: dict[str, list[Gap]] = {}
    for gap in gaps:
        by_axis.setdefault(gap.axis, []).append(gap)
    drafts: list[str] = []
    for axis in sorted(by_axis):
        axis_gaps = by_axis[axis]
        score = scores.get(axis)
        score_str = f"{score:.3f}" if score is not None else "n/a"
        lines = [
            f"## tomd: {axis} divergence on {pid}",
            "",
            "**Label:** Bug",
            f"**Paper:** {pid}",
            f"**Axis:** {axis} (score {score_str})",
            "",
            "### Located divergences",
        ]
        lines += [f"- {g.kind}: tomd `{g.tomd}` vs ideal `{g.ideal}`" for g in axis_gaps]
        lines += [
            "",
            "### Contract rule",
            f"> {axis_gaps[0].rule}",
            "",
            "### Reproduce",
            "",
            "```",
            f"tomd score {stem}",
            "```",
            "",
            "### Suggested origin",
            _ORIGIN.get(axis, "see the tomd-surgical-edits symptom map"),
        ]
        drafts.append("\n".join(lines))
    return drafts
