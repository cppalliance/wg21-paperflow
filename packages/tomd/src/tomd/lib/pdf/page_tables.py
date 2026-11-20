"""Tables read from the page image by an outside model (opt-in).

tomd makes no model calls. :func:`page_table_requests` lists one request per
page; a resolver outside tomd shows each page image to a vision model, which
writes out the tables on it as rows of cells (:data:`INSTRUCTIONS`,
:data:`SCHEMA`). Given those answers, :func:`model_tables` turns them into
table sections:

- Words stay verbatim. A cell keeps a token only where the page has it, as a
  word (each page word used once) or inside the page's text; any other token
  the model wrote is dropped. The model proposes the structure, never the words.
- Pieces the model marks as continuing are joined across consecutive pages
  when their column counts agree. A header repeated at the top of the next
  piece is dropped.
- A model table no table tomd selected overlaps is added. Where they overlap,
  the tomd and model tables form groups (:func:`combine`); each group whose
  readings differ becomes a reading-judge request, and only a confident answer
  for the model's reading swaps the group's tables. Replacing without the judge
  lost as often as it won (docs/plans/tomd-tables-port/page-tables.md).

Request: ``{"id", "page"}``. The id hashes the prompt version and the rendered
page PNG, so an answer applies only to the page image it was given for.
Answer: ``{"tables": [{"rows": [[str]], "continues_from_previous_page": bool,
"continues_on_next_page": bool}]}``. A missing or malformed answer adds nothing.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Mapping

import fitz

from tomd.domain.elements import Confidence

from .judge import ID_ROUND, SEP, _digest, answer_pick
from .select import _to_section
from .types import Line, Section, Span, TableCandidate

PROMPT_VERSION = "page-tables-1"
RENDER_DPI = 150
MAX_EDGE = 1568          # pixels: larger pages are scaled down
SOURCE = "page-model"
MAX_GROUP_PAGES = 8      # a group of overlapping tables over more pages keeps tomd's tables
GROUP_VERSION = "group-2"  # group requests: judge prompt with the table definition (2026-11-21)

INSTRUCTIONS = """This is one page of a C++ standards committee paper. Transcribe every table on this page.

A table is content laid out in rows and columns that a reader would put into a Markdown table. This includes:
poll result tables; before/after or side-by-side code comparison tables; status, attendance and logistics
tables; feature-test macro tables; unruled 2-column metadata blocks at the top of a paper
(e.g. "Document number: | P1234", 2+ rows of label/value pairs); tables on presentation slides.
Not a table: code listings; wording insert/delete boxes; a single boxed code sample; tables of contents;
bullet lists; figures and diagrams.

For each table, in reading order:
- rows: a list of rows, each a list of cell strings. Row 0 is the header row when there is one.
- Write cell text exactly as printed, whitespace collapsed to single spaces; join a cell's lines with single
  spaces. Keep punctuation, underscores and symbols. Empty cells are "". All rows have the same number of cells.
- A cell spanning several columns or rows: its text in the first (top-left) position, "" in the others.
- continues_from_previous_page: true if this table is the continuation of a table from the previous page
  (e.g. it starts at the top of the page without its own caption, or the previous page's table ran off).
- continues_on_next_page: true if the table runs off the bottom of this page.
If the page has no table, return an empty list."""

SCHEMA = {
    "type": "object",
    "properties": {"tables": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
            "continues_from_previous_page": {"type": "boolean"},
            "continues_on_next_page": {"type": "boolean"},
        },
        "required": ["rows", "continues_from_previous_page", "continues_on_next_page"],
        "additionalProperties": False}}},
    "required": ["tables"],
    "additionalProperties": False,
}

Box = tuple[float, float, float, float]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s)).strip()


def render_page(page) -> bytes:
    """The page image the model is shown: RENDER_DPI, long edge at most MAX_EDGE pixels."""
    z = RENDER_DPI / 72
    w, h = page.rect.width * z, page.rect.height * z
    if max(w, h) > MAX_EDGE:
        z *= MAX_EDGE / max(w, h)
    return page.get_pixmap(matrix=fitz.Matrix(z, z)).tobytes("png")


def request_id(png: bytes) -> str:
    return hashlib.sha256(PROMPT_VERSION.encode() + b"\0" + png).hexdigest()[:24]


def page_table_requests(doc) -> list[dict]:
    """One request per page of an open document."""
    return [{"id": request_id(render_page(doc[pg])), "page": pg} for pg in range(doc.page_count)]


def _valid(ans) -> list[dict]:
    if not isinstance(ans, Mapping) or not isinstance(ans.get("tables"), list):
        return []
    out = []
    for t in ans["tables"]:
        rows = t.get("rows") if isinstance(t, Mapping) else None
        if (isinstance(rows, list) and rows and all(isinstance(r, list) and r for r in rows)
                and all(isinstance(c, str) for r in rows for c in r)):
            out.append(t)
    return out


def _piece(table: Mapping, words: list[tuple[str, str, Box]], pool: dict, page_text: str, pg: int):
    """A model table on page pg as cells of verbatim page words, or None when no word is the page's.

    Each token takes an unused page word with its text. A word that occurs once
    on the page anchors the table's area; every other token takes the occurrence
    nearest that area, so a common word ("the", a number) is not taken from the
    header or another table and the table's box stays its own."""
    toks = [[[t for t in _norm(c).split(" ") if t] for c in r] for r in table["rows"]]
    anchors = [words[pool[t][0]][2] for r in toks for c in r for t in c if len(pool.get(t, ())) == 1]
    seed = ((min(b[0] for b in anchors), min(b[1] for b in anchors), max(b[2] for b in anchors),
             max(b[3] for b in anchors)) if anchors else None)

    def dist(b: Box) -> float:
        if seed is None:
            return 0.0
        dx = max(seed[0] - b[2], b[0] - seed[2], 0.0)
        dy = max(seed[1] - b[3], b[1] - seed[3], 0.0)
        return dx + dy

    rows, boxes = [], []
    for r in toks:
        row = []
        for c in r:
            cell: list[tuple[str, Box | None]] = []
            for tok in c:
                if pool.get(tok):
                    k = min(range(len(pool[tok])), key=lambda k: (dist(words[pool[tok][k]][2]), k))
                    i = pool[tok].pop(k)
                    cell.append((words[i][1], words[i][2]))
                    boxes.append(words[i][2])
                elif tok in page_text:
                    cell.append((tok, None))       # part of a page word: kept, placed with the cell
            row.append(cell)
        rows.append(row)
    if not boxes:
        return None
    box = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    width = max(len(r) for r in rows)
    return [r + [[] for _ in range(width - len(r))] for r in rows], box


def _cells(rows, pg: int, box: Box) -> list[list[list[Line]]]:
    out = []
    for r in rows:
        line_row = []
        for cell in r:
            known = [b for _, b in cell if b is not None]
            cb = (min(b[0] for b in known), min(b[1] for b in known), max(b[2] for b in known),
                  max(b[3] for b in known)) if known else box
            # one line per cell, its words joined by spaces (as a reader transcribes a wrapped cell)
            spans = [Span(text=t + (" " if i < len(cell) - 1 else ""), bbox=b or cb) for i, (t, b) in enumerate(cell)]
            line_row.append([Line(spans=spans, bbox=cb, page_num=pg)] if cell else [])
        out.append(line_row)
    return out


def _overlaps(a: Box, b: Box) -> bool:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return False
    small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return w * h >= 0.1 * max(small, 1e-6)


def section_boxes(sec: Section) -> dict[int, Box]:
    """Page -> bounding box of a table section's lines (its region when it has no lines)."""
    out: dict[int, Box] = {}
    for ln in sec.lines or []:
        b, a = ln.bbox, out.get(ln.page_num)
        out[ln.page_num] = b if a is None else (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))
    if not out and sec.metadata.get("region_bbox"):
        pg, b = sec.metadata["region_bbox"]
        out[pg] = tuple(b)
    return out


def _section(c: dict) -> Section:
    cells = [r for pg, rows, box in c["parts"] for r in _cells(rows, pg, box)]
    cand = TableCandidate(source=SOURCE, rows=cells, bboxes=dict(c["boxes"]))
    sec = _to_section(cand, Confidence.UNCERTAIN, [])
    first = cand.pages[0]
    sec.metadata["region_bbox"] = (first, tuple(cand.bboxes[first]))
    if len(cand.pages) > 1:
        sec.metadata["page_bboxes"] = dict(cand.bboxes)
    sec.metadata["uncertain_reasons"] = ["single-source", "page-model"]
    sec.metadata["table_note"] = ("No reader kept a table here; a vision model read the page image and "
                                  "tomd kept only the page's own words.")
    return sec


def model_sections(doc, render_doc, answers: Mapping[str, Mapping] | None, skip_pages=()) -> list[Section]:
    """Every table in the answers as a section, in page order.

    ``doc`` gives the words (hidden text already removed); ``render_doc`` is
    the unmodified document whose page images the ids were made from.
    """
    if not answers:
        return []
    cands: list[dict] = []
    for pg in range(doc.page_count):
        if pg in skip_pages:
            continue
        tables = _valid(answers.get(request_id(render_page(render_doc[pg]))))
        if not tables:
            continue
        words = [(_norm(w[4]), w[4], tuple(w[:4])) for w in doc[pg].get_text("words")]
        words = [w for w in words if w[0]]
        pool: dict[str, list[int]] = {}
        for i, (t, _, _) in enumerate(words):
            pool.setdefault(t, []).append(i)
        page_text = "".join(t for t, _, _ in words)
        for ti, t in enumerate(tables):
            got = _piece(t, words, pool, page_text, pg)
            if got is None:
                continue
            rows, box = got
            prev = cands[-1] if cands else None
            if (ti == 0 and t.get("continues_from_previous_page") and prev and prev["to_next"]
                    and max(prev["boxes"]) == pg - 1 and len(prev["rows"][0]) == len(rows[0])):
                head = [[w for w, _ in c] for c in rows[0]]
                if head == [[w for w, _ in c] for c in prev["rows"][0]]:
                    rows = rows[1:]                    # the header repeated on the new page
                prev["parts"].append((pg, rows, box))
                prev["rows"] += rows
                prev["boxes"][pg] = box
                prev["to_next"] = bool(t.get("continues_on_next_page")) and ti == len(tables) - 1
            else:
                cands.append({"rows": list(rows), "boxes": {pg: box}, "parts": [(pg, rows, box)],
                              "to_next": bool(t.get("continues_on_next_page")) and ti == len(tables) - 1})
    return [_section(c) for c in cands]


def _meets(a: Section, b: Section) -> bool:
    ba, bb = section_boxes(a), section_boxes(b)
    return any(_overlaps(box, bb[pg]) for pg, box in ba.items() if pg in bb)


def _rows(sec: Section) -> list[list[str]]:
    if sec.columns:
        return [[_norm("".join(sp.text for sp in cell).replace("\n", " ")) for cell in row] for row in sec.columns]
    return [[_norm(c) for c in line.split(" | ")] for line in (sec.text or "").splitlines()]


def _reading(secs: list[Section]) -> list[list[str]]:
    rows: list[list[str]] = []
    for k, sec in enumerate(secs):
        rows += ([list(SEP)] if k else []) + _rows(sec)
    return rows


def group_request(tomd: list[Section], model: list[Section]) -> dict | None:
    """The judge request for a group of overlapping tomd and model tables, or None when their
    readings agree or the group spreads over more than MAX_GROUP_PAGES pages."""
    readings = {"tomd": _reading(tomd), SOURCE: _reading(model)}
    if readings["tomd"] == readings[SOURCE]:
        return None
    boxes: dict[int, Box] = {}
    for sec in tomd + model:
        for pg, b in section_boxes(sec).items():
            a = boxes.get(pg)
            boxes[pg] = b if a is None else (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))
    if not boxes or len(boxes) > MAX_GROUP_PAGES:
        return None
    pieces = [[pg, [round(v, 1) for v in boxes[pg]]] for pg in sorted(boxes)]
    order = sorted(readings, key=lambda k: _digest(readings[k]))
    rid = "g" + _digest([GROUP_VERSION, PROMPT_VERSION, [[pg, [round(v / ID_ROUND) for v in bb]] for pg, bb in pieces],
                         [readings[k] for k in order]])[:15]
    return {"id": rid, "pieces": pieces, "readings": [readings[k] for k in order], "sources": order,
            "today": order.index("tomd")}


def combine(model: list[Section], existing: list[Section], judge_answers: Mapping[str, Mapping] | None = None,
            judge_requests: list[dict] | None = None) -> tuple[list[Section], list[Section]]:
    """(model tables to add, existing tables to drop).

    A model table no existing table overlaps is added. Overlapping tables form
    groups (connected through overlaps): each group whose readings differ is a
    judge request (appended to ``judge_requests``), and a confident answer for
    the model's reading swaps the group's tables for the model's.
    """
    add = [m for m in model if not any(_meets(m, e) for e in existing)]
    drop: list[Section] = []
    linked = [m for m in model if m not in add]
    seen: set[int] = set()
    for m0 in linked:
        if id(m0) in seen:
            continue
        ms, es, todo = [], [], [("m", m0)]
        while todo:
            kind, x = todo.pop()
            if id(x) in seen:
                continue
            seen.add(id(x))
            (ms if kind == "m" else es).append(x)
            others = existing if kind == "m" else linked
            todo += [("e" if kind == "m" else "m", y) for y in others if id(y) not in seen and _meets(x, y)]
        key = lambda s: (s.page_num, section_boxes(s).get(s.page_num, (0, 0))[1])  # noqa: E731
        ms.sort(key=key)
        es.sort(key=key)
        req = group_request(es, ms)
        if req is None:
            continue
        if judge_requests is not None:
            judge_requests.append(req)
        ans = answer_pick(req, judge_answers)
        if ans is not None and req["sources"][ans[0]] == SOURCE:
            for m in ms:
                m.metadata["judged"] = f"{SOURCE}/{ans[1]}"
            add += ms
            drop += es
    return add, drop


def model_tables(doc, render_doc, answers: Mapping[str, Mapping] | None, existing: list[Section],
                 skip_pages=()) -> list[Section]:
    """The model tables no existing table overlaps (no judging)."""
    return combine(model_sections(doc, render_doc, answers, skip_pages), existing)[0]
