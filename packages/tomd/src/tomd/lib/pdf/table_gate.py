"""Outside table/not-table answers for emitted tables (prototype, opt-in).

tomd makes no model calls. For every emitted table it returns a *gate
request* (the table's page pieces and a stable id). A resolver outside tomd
looks at each piece (for example with a vision model) and answers whether it
holds a table. Given those answers on a later run, tomd *vetoes* tables the
answers say are not tables: their text stays in the prose, exactly as if no
reader had proposed them. With no answers, nothing changes.

Answers only remove tables (phase 1). They never add one or change a table's
rows or columns.

Request: ``{"id", "pieces": [[page, [x0, y0, x1, y1]], ...], "source"}``.
Answers: ``{id: bool}``, True = a table, False = not a table. A table is vetoed
only when its answer is False; a missing id keeps it.
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping

from .types import Section

ID_ROUND = 1.0      # points: ids survive sub-point jitter in the boxes


def _pieces(t: Section) -> list[tuple[int, tuple[float, float, float, float]]]:
    boxes = dict((t.metadata.get("page_bboxes") or {}).items())
    if t.metadata.get("region_bbox"):
        pg, bb = t.metadata["region_bbox"]
        boxes.setdefault(pg, bb)
    if not boxes:   # a table without recorded boxes: the union of its lines per page
        for ln in t.lines or []:
            b = boxes.get(ln.page_num)
            boxes[ln.page_num] = ln.bbox if b is None else (
                min(b[0], ln.bbox[0]), min(b[1], ln.bbox[1]), max(b[2], ln.bbox[2]), max(b[3], ln.bbox[3]))
    return sorted((int(pg), tuple(float(v) for v in bb)) for pg, bb in boxes.items())


def gate_id(t: Section) -> str:
    key = ";".join(f"{pg}:" + ",".join(str(round(v / ID_ROUND)) for v in bb) for pg, bb in _pieces(t))
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def gate_requests(tables: list[Section]) -> list[dict]:
    """One request per table that has page pieces."""
    out = []
    for t in tables:
        pieces = _pieces(t)
        if pieces:
            out.append({"id": gate_id(t), "pieces": [[pg, list(bb)] for pg, bb in pieces],
                        "source": t.table_source})
    return out


def veto_tables(tables: list[Section], answers: Mapping[str, bool] | None
                ) -> tuple[list[Section], list[Section]]:
    """Split ``tables`` into (kept, vetoed) by the answers."""
    if not answers:
        return list(tables), []
    kept, vetoed = [], []
    for t in tables:
        (vetoed if answers.get(gate_id(t)) is False else kept).append(t)
    return kept, vetoed


def vetoed_boxes(vetoed: list[Section]) -> list[tuple[int, tuple[float, float, float, float]]]:
    return [p for t in vetoed for p in _pieces(t)]


def inside_vetoed(page: int, bbox, boxes) -> bool:
    """The centre of ``bbox`` lies in a vetoed piece on the same page."""
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    return any(pg == page and b[0] <= cx <= b[2] and b[1] <= cy <= b[3] for pg, b in boxes)
