"""Outside table/not-table answers: requests out, vetoes in (tomd.lib.pdf.table_gate)."""
from tomd.lib.pdf.table_gate import gate_id, gate_requests, inside_vetoed, veto_tables, vetoed_boxes
from tomd.lib.pdf.types import Section, SectionKind


def _table(page, bbox, source="grid"):
    return Section(kind=SectionKind.TABLE, text="", table_source=source,
                   metadata={"region_bbox": (page, bbox)})


def test_one_request_per_table_with_pieces():
    a, b = _table(0, (10, 20, 200, 80)), _table(3, (10, 100, 300, 400), "rules")
    reqs = gate_requests([a, b])
    assert [r["id"] for r in reqs] == [gate_id(a), gate_id(b)]
    assert reqs[1]["pieces"] == [[3, [10.0, 100.0, 300.0, 400.0]]] and reqs[1]["source"] == "rules"


def test_id_is_stable_under_subpoint_jitter_and_differs_by_place():
    assert gate_id(_table(0, (10, 20, 200, 80))) == gate_id(_table(0, (10.2, 19.9, 200.3, 80.1)))
    assert gate_id(_table(0, (10, 20, 200, 80))) != gate_id(_table(1, (10, 20, 200, 80)))


def test_stitched_table_has_every_page_piece():
    t = Section(kind=SectionKind.TABLE, text="",
                metadata={"page_bboxes": {4: (1, 2, 3, 4), 5: (5, 6, 7, 8)}, "region_bbox": (4, (1, 2, 3, 4))})
    assert [p[0] for p in gate_requests([t])[0]["pieces"]] == [4, 5]


def test_no_answers_keeps_everything():
    ts = [_table(0, (0, 0, 10, 10)), _table(1, (0, 0, 10, 10))]
    assert veto_tables(ts, None) == (ts, []) and veto_tables(ts, {}) == (ts, [])


def test_only_a_false_answer_vetoes():
    a, b, c = _table(0, (0, 0, 10, 10)), _table(1, (0, 0, 10, 10)), _table(2, (0, 0, 10, 10))
    kept, vetoed = veto_tables([a, b, c], {gate_id(a): False, gate_id(b): True})
    assert kept == [b, c] and vetoed == [a]


def test_inside_vetoed_uses_the_centre_on_the_same_page():
    boxes = vetoed_boxes([_table(2, (100, 100, 300, 300))])
    assert inside_vetoed(2, (150, 150, 250, 250), boxes)
    assert not inside_vetoed(1, (150, 150, 250, 250), boxes)
    assert not inside_vetoed(2, (0, 0, 120, 120), boxes)

