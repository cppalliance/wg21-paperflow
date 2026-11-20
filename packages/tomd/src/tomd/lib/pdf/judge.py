"""Outside reading judge for tables the readers disagree on (opt-in).

tomd makes no model calls. Where two or more readings of a table region pass
the rule checks and differ, selection lists a *judge request*: the region's
page pieces and its distinct readings, in an order that does not depend on
which reader made them. A resolver outside tomd shows the page crop and the
readings to a model, which picks the reading a person would understand as the
table. Given those answers on a later run, selection emits the picked reading
instead of the one source priority chose. With no answers, nothing changes.

Answers only choose among readings tomd already made. They never write cell
text, so the output keeps the source's words verbatim.

Request: ``{"id", "pieces": [[page, [x0, y0, x1, y1]], ...], "readings":
[rows, ...], "sources": [...], "today": index}``. ``today`` is the reading
source priority chose; ``sources`` is diagnosis only and is not shown to the
judge. Answers: ``{id: {"pick": index, "confidence": "high"|"medium"|"low"}}``.
A low-confidence answer, a missing id or a malformed answer keeps today's
choice.

The id hashes the prompt version, the pieces and the readings, so an answer
applies only to the region and readings it was given for. Measured on dev-side
regions (2026-11-18): the judge kept a right reading in 59 of 62 regions that
were right before, and fixed 23 of 25 that were wrong while a right reading existed
(docs/plans/tomd-tables-port/reading-judge.md).
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping

from .types import TableCandidate

PROMPT_VERSION = "reading-judge-1"
LETTERS = "ABCDEFGH"
MAX_PAGES = 4            # a region spread over more pages keeps today's choice
PAD = 12.0               # points around the readings' union on each page
CROP_DPI = 150
MAX_EDGE = 1568          # pixels: larger crops are scaled down
CONFIDENT = ("high", "medium")
ID_ROUND = 1.0           # points: ids survive sub-point jitter in the boxes
SEP = ("=== next table ===",)   # a row between tables in a reading that holds several (page_tables groups)
_GROUP_NOTE = ("A reading may hold several tables, separated by a row \"=== next table ===\"; prefer the reading "
               "that splits and joins tables as a person reading the page would. Count as a table: content laid "
               "out in rows and columns, including poll results, before/after code comparisons, status and "
               "feature-macro tables, and an unruled block of 2+ label/value rows at the top of a paper "
               "(\"Document number: | P1234\"). Not a table: code listings, wording insert/delete boxes, a single "
               "boxed code sample, tables of contents, bullet lists, figures.")

INSTRUCTIONS = """You are judging table extraction from a PDF page.

The image(s) show one region of a page: one image per page the region covers, in page order. \
Below are candidate readings of the table in that region. A reading lists its rows, one per line, \
with cells separated by " | " and "·" marking an empty cell.

Pick the reading that best reproduces the table as a person reading the page would understand it. \
Get the row and column structure right: one row per logical record, header cells as the first row, \
multi-line cells kept as one cell (not split into several rows), code blocks side by side kept as \
one cell per column, and no text from outside the table. Word-level noise matters less than \
structure. If no reading is good, still pick the closest one.

Answer with the reading's letter, your confidence (high, medium or low), and one short sentence why."""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s)).strip()


def norm_rows(c: TableCandidate) -> list[list[str]]:
    return [[_norm(t) for t in row] for row in c.text_rows()]


def _digest(obj) -> str:
    return hashlib.sha1(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def region_readings(primary: TableCandidate, others: list[TableCandidate]) -> list[TableCandidate]:
    """The primary first, then each other reading whose rows differ from every earlier one."""
    out, seen = [], set()
    for c in [primary] + [o for o in others if o is not primary]:
        key = json.dumps(norm_rows(c), ensure_ascii=False)
        if key not in seen and c.rows:
            seen.add(key)
            out.append(c)
    return out


def _pieces(readings: list[TableCandidate]) -> list[list]:
    boxes: dict[int, list[float]] = {}
    for c in readings:
        for pg, bb in c.bboxes.items():
            b = boxes.get(pg)
            boxes[pg] = list(bb) if b is None else [min(b[0], bb[0]), min(b[1], bb[1]),
                                                     max(b[2], bb[2]), max(b[3], bb[3])]
    return [[pg, [b[0] - PAD, b[1] - PAD, b[2] + PAD, b[3] + PAD]] for pg, b in sorted(boxes.items())]


def judge_request(readings: list[TableCandidate]) -> tuple[dict, list[TableCandidate]] | None:
    """The request for a region's distinct readings (primary first), and the readings in request order.

    None when there is nothing to judge: fewer than two distinct readings, more
    than the letters allow, or a region spread over more than MAX_PAGES pages.
    """
    if not 2 <= len(readings) <= len(LETTERS):
        return None
    pieces = _pieces(readings)
    if len(pieces) > MAX_PAGES:
        return None
    rows = [norm_rows(c) for c in readings]
    # order by content, not by reader: the judge never learns which reading is today's
    order = sorted(range(len(readings)), key=lambda i: _digest(rows[i]))
    ordered_rows = [rows[i] for i in order]
    rid = _digest([PROMPT_VERSION, [[pg, [round(v / ID_ROUND) for v in bb]] for pg, bb in pieces],
                   ordered_rows])[:16]
    req = {"id": rid, "pieces": pieces, "readings": ordered_rows,
           "sources": [readings[i].source for i in order], "today": order.index(0)}
    return req, [readings[i] for i in order]


def answer_pick(req: dict, answers: Mapping[str, Mapping] | None) -> tuple[int, str] | None:
    """(index, confidence) of the answer to adopt, or None to keep today's choice."""
    if not answers:
        return None
    a = answers.get(req["id"])
    if not isinstance(a, Mapping):
        return None
    pick, conf = a.get("pick"), a.get("confidence")
    if not isinstance(pick, int) or isinstance(pick, bool) or not 0 <= pick < len(req["readings"]):
        return None
    if conf not in CONFIDENT or pick == req["today"]:
        return None
    return pick, conf


def prompt_text(req: dict) -> str:
    """The text half of the judge prompt: instructions and the lettered readings."""
    parts = [INSTRUCTIONS, ""]
    if any(list(row) == list(SEP) for rows in req["readings"] for row in rows):
        parts[0] = INSTRUCTIONS.replace("Below are candidate readings of the table in that region.",
                                        "Below are candidate readings of the table(s) in that region. " + _GROUP_NOTE)
    for letter, rows in zip(LETTERS, req["readings"]):
        parts.append(f"### Reading {letter} ({len(rows)} rows)")
        parts += [" | ".join(c if c else "·" for c in row) for row in rows]
        parts.append("")
    return "\n".join(parts)


def render_crops(doc, req: dict) -> list[bytes]:
    """PNG bytes of each page piece of ``req``, in page order. ``doc`` is an open fitz document."""
    import fitz
    out = []
    for pg, bb in req["pieces"]:
        page = doc[int(pg)]
        rect = fitz.Rect(*bb) & page.rect
        if rect.is_empty:
            continue
        zoom = CROP_DPI / 72
        longest = max(rect.width, rect.height) * zoom
        if longest > MAX_EDGE:
            zoom *= MAX_EDGE / longest
        out.append(page.get_pixmap(clip=rect, matrix=fitz.Matrix(zoom, zoom)).tobytes("png"))
    return out
