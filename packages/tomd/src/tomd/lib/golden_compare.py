#
# Copyright (c) 2026 Sean Parsons (seanpatrick2013@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Deterministic structural comparator for golden QA.

Parses two Markdown strings into a normalized block tree and scores how
well they match across six independent axes (front-matter, heading, list,
code, table, per-block text). Pure: no I/O, no LLM, no pipeline state.
Same inputs always give the same score.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

import mistune

from tomd.lib.metadata_yaml.format import FRONT_MATTER_ORDER
from tomd.lib.similarity import word_jaccard

_AST = mistune.create_markdown(renderer="ast", plugins=["table"])

# Same delimiter shape as lib.pdf.qa: a leading "---" block. We only need
# the top-level keys, so indented list items (e.g. under reply-to) are skipped.
_FRONT_MATTER_RE = re.compile(r"^---\n(.+?\n)---", re.DOTALL)

# Block-alignment key length for the text axis: blocks are aligned on this
# many leading characters so a paraphrase still aligns to its counterpart
# rather than registering as an insert/delete.
_TEXT_ALIGN_PREFIX_CHARS = 60

# Heading axis sub-signals, equal-weighted. text: are the right headings
# present in the right order. level: is each at the right absolute depth.
# nesting: is the relative shape (deltas between consecutive headings) right.
# A uniform level shift scores text=1, nesting=1, level=0 -> 0.667, which is
# the #155 signature stated precisely, instead of a featureless 0.0.
_HEADING_SUBSIGNALS = ("text", "level", "nesting")


@dataclass(frozen=True)
class ListEntry:
    depth: int
    ordered: bool
    marker: str
    text: str


@dataclass
class Block:
    kind: str  # "heading" | "paragraph" | "list" | "code" | "table"
    text: str = ""
    level: int = 0
    items: tuple[ListEntry, ...] = ()
    code_lang: str = ""
    code_lines: int = 0
    table_rows: int = 0
    table_cols: int = 0


@dataclass
class NormalizedDoc:
    front_matter_keys: tuple[str, ...]
    blocks: list[Block] = field(default_factory=list)


def _collect_text(node: dict, out: list[str]) -> None:
    raw = node.get("raw")
    if isinstance(raw, str) and node.get("type") in {"text", "codespan"}:
        out.append(raw)
    for child in node.get("children", []) or []:
        _collect_text(child, out)


def _inline_text(node: dict) -> str:
    parts: list[str] = []
    _collect_text(node, parts)
    return " ".join(p for p in parts if p).strip()


def _code_line_count(raw: str) -> int:
    if not raw.strip():
        return 0
    return raw.rstrip("\n").count("\n") + 1


def _table_dims(tok: dict) -> tuple[int, int]:
    rows = 0
    cols = 0
    for child in tok.get("children", []):
        ctype = child.get("type", "")
        if ctype == "table_head":
            rows += 1
            cols = max(cols, len(child.get("children", [])))
        elif ctype == "table_body":
            for row in child.get("children", []):
                rows += 1
                cols = max(cols, len(row.get("children", [])))
    return rows, cols


def _walk_list(list_tok: dict):
    ordered = list_tok.get("attrs", {}).get("ordered", False)
    depth = list_tok.get("attrs", {}).get("depth", 0)
    marker = list_tok.get("bullet") or ("1." if ordered else "-")
    for item in list_tok.get("children", []):
        if item.get("type") != "list_item":
            continue
        text_parts: list[str] = []
        nested: list[dict] = []
        for child in item.get("children", []):
            if child.get("type") == "list":
                nested.append(child)
            else:
                _collect_text(child, text_parts)
        yield ListEntry(depth=depth, ordered=ordered, marker=marker,
                        text=" ".join(text_parts).strip())
        for nested_list in nested:
            yield from _walk_list(nested_list)


def _block_from_token(tok: dict) -> Block | None:
    ttype = tok.get("type", "")
    if ttype == "heading":
        return Block(kind="heading",
                     level=tok.get("attrs", {}).get("level", 0),
                     text=_inline_text(tok))
    if ttype == "paragraph":
        return Block(kind="paragraph", text=_inline_text(tok))
    if ttype == "list":
        items = tuple(_walk_list(tok))
        return Block(kind="list", items=items,
                     text=" ".join(e.text for e in items))
    if ttype == "block_code":
        raw = tok.get("raw", "")
        return Block(kind="code",
                     code_lang=(tok.get("attrs", {}).get("info") or "").strip(),
                     code_lines=_code_line_count(raw),
                     text=raw)
    if ttype == "table":
        rows, cols = _table_dims(tok)
        return Block(kind="table", table_rows=rows, table_cols=cols,
                     text=_inline_text(tok))
    return None


def _front_matter_keys(md_text: str) -> tuple[str, ...]:
    """Top-level front-matter keys, ordered by the FRONT_MATTER_ORDER contract."""
    m = _FRONT_MATTER_RE.match(md_text)
    if not m:
        return ()
    present: set[str] = set()
    for line in m.group(1).split("\n"):
        if not line or line[0].isspace() or ":" not in line:
            continue
        present.add(line.split(":", 1)[0].strip().lower())
    return tuple(k for k in FRONT_MATTER_ORDER if k in present)


def normalize(md_text: str) -> NormalizedDoc:
    tokens = _AST(md_text)
    blocks: list[Block] = []
    for tok in tokens:
        block = _block_from_token(tok)
        if block is not None:
            blocks.append(block)
    return NormalizedDoc(front_matter_keys=_front_matter_keys(md_text), blocks=blocks)


@dataclass
class AxisScore:
    name: str
    score: float
    detail: str = ""
    sub: dict[str, float] = field(default_factory=dict)


@dataclass
class StructuralScore:
    axes: dict[str, AxisScore]
    composite: float
    worst_present_axis: str


# frontmatter/heading/text apply to every document; the structural axes only
# count toward the composite when the ideal actually exercises them, so a
# prose-only paper is not padded to a high composite by three vacuous 1.0s.
_ALWAYS_PRESENT = ("frontmatter", "heading", "text")
_STRUCT_KIND = {"list": "list", "code": "code", "table": "table"}


def _present_axes(expected: NormalizedDoc) -> set[str]:
    present = set(_ALWAYS_PRESENT)
    for axis, kind in _STRUCT_KIND.items():
        if any(blk.kind == kind for blk in expected.blocks):
            present.add(axis)
    return present


def _sequence_score(actual: list, expected: list) -> float:
    if not actual and not expected:
        return 1.0
    return difflib.SequenceMatcher(None, actual, expected).ratio()


def _frontmatter_axis(a: NormalizedDoc, b: NormalizedDoc) -> AxisScore:
    # normalize() always orders keys by FRONT_MATTER_ORDER, so equal key sets
    # yield equal tuples: the axis is set-membership Jaccard, never order.
    if a.front_matter_keys == b.front_matter_keys:
        return AxisScore("frontmatter", 1.0)
    sa, sb = set(a.front_matter_keys), set(b.front_matter_keys)
    union = sa | sb
    score = (len(sa & sb) / len(union)) if union else 1.0
    return AxisScore("frontmatter", score,
                     f"actual={a.front_matter_keys} expected={b.front_matter_keys}")


def _heading_signals(aa: list[tuple[int, str]],
                     bb: list[tuple[int, str]]) -> dict[str, float]:
    a_text = [t for _, t in aa]
    b_text = [t for _, t in bb]
    text = _sequence_score(a_text, b_text)
    sm = difflib.SequenceMatcher(None, a_text, b_text)
    aligned = [(i1 + k, j1 + k)
               for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag in ("equal", "replace")
               for k in range(min(i2 - i1, j2 - j1))]
    denom = max(len(aa), len(bb)) or 1
    level = sum(1 for ai, bi in aligned if aa[ai][0] == bb[bi][0]) / denom
    pairs = list(zip(aligned, aligned[1:]))
    if pairs:
        nest_hits = sum(
            1 for (ai, bi), (aj, bj) in pairs
            if (aa[aj][0] - aa[ai][0]) == (bb[bj][0] - bb[bi][0]))
        nesting = nest_hits / len(pairs)
    else:
        nesting = 1.0
    return {"text": text, "level": level, "nesting": nesting}


def _heading_axis(a: NormalizedDoc, b: NormalizedDoc) -> AxisScore:
    aa = [(blk.level, blk.text) for blk in a.blocks if blk.kind == "heading"]
    bb = [(blk.level, blk.text) for blk in b.blocks if blk.kind == "heading"]
    sub = _heading_signals(aa, bb)
    score = sum(sub[k] for k in _HEADING_SUBSIGNALS) / len(_HEADING_SUBSIGNALS)
    detail = "" if score == 1.0 else (
        f"text={sub['text']:.2f} level={sub['level']:.2f} nesting={sub['nesting']:.2f}")
    return AxisScore("heading", score, detail, sub=sub)


def _list_axis(a: NormalizedDoc, b: NormalizedDoc) -> AxisScore:
    aa = [(e.depth, e.marker, e.ordered)
          for blk in a.blocks if blk.kind == "list" for e in blk.items]
    bb = [(e.depth, e.marker, e.ordered)
          for blk in b.blocks if blk.kind == "list" for e in blk.items]
    score = _sequence_score(aa, bb)
    detail = "" if score == 1.0 else f"actual {len(aa)} items expected {len(bb)}"
    return AxisScore("list", score, detail)


def _code_axis(a: NormalizedDoc, b: NormalizedDoc) -> AxisScore:
    aa = [(blk.code_lang, blk.code_lines) for blk in a.blocks if blk.kind == "code"]
    bb = [(blk.code_lang, blk.code_lines) for blk in b.blocks if blk.kind == "code"]
    score = _sequence_score(aa, bb)
    detail = "" if score == 1.0 else f"actual {len(aa)} fences expected {len(bb)}"
    return AxisScore("code", score, detail)


def _table_axis(a: NormalizedDoc, b: NormalizedDoc) -> AxisScore:
    aa = [(blk.table_rows, blk.table_cols) for blk in a.blocks if blk.kind == "table"]
    bb = [(blk.table_rows, blk.table_cols) for blk in b.blocks if blk.kind == "table"]
    score = _sequence_score(aa, bb)
    detail = "" if score == 1.0 else f"actual {aa} expected {bb}"
    return AxisScore("table", score, detail)


def _text_axis_score(actual: list[str], expected: list[str]) -> float:
    if not actual and not expected:
        return 1.0
    total = max(len(actual), len(expected))
    sm = difflib.SequenceMatcher(
        None,
        [t[:_TEXT_ALIGN_PREFIX_CHARS] for t in actual],
        [t[:_TEXT_ALIGN_PREFIX_CHARS] for t in expected])
    matched = 0.0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for off in range(i2 - i1):
                matched += word_jaccard(actual[i1 + off], expected[j1 + off])
        elif tag == "replace":
            for x, y in zip(actual[i1:i2], expected[j1:j2]):
                matched += word_jaccard(x, y)
    return matched / total if total else 1.0


def _text_axis(a: NormalizedDoc, b: NormalizedDoc) -> AxisScore:
    aa = [blk.text for blk in a.blocks if blk.kind != "code" and blk.text]
    bb = [blk.text for blk in b.blocks if blk.kind != "code" and blk.text]
    score = _text_axis_score(aa, bb)
    detail = "" if score == 1.0 else f"text axis {score:.3f}"
    return AxisScore("text", score, detail)


def compare(tomd_md: str, golden_md: str) -> StructuralScore:
    actual = normalize(tomd_md)
    expected = normalize(golden_md)
    axes = {
        "frontmatter": _frontmatter_axis(actual, expected),
        "heading": _heading_axis(actual, expected),
        "list": _list_axis(actual, expected),
        "code": _code_axis(actual, expected),
        "table": _table_axis(actual, expected),
        "text": _text_axis(actual, expected),
    }
    present = _present_axes(expected)
    scored = {name: ax for name, ax in axes.items() if name in present}
    composite = sum(ax.score for ax in scored.values()) / len(scored)
    worst = min(scored, key=lambda name: scored[name].score)
    return StructuralScore(axes=axes, composite=composite, worst_present_axis=worst)
