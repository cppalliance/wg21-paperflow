# Copyright (c) 2026 Rob Beeston (rob@cppalliance.org)
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""Tables read from page images by an outside model: requests out, tables in (tomd.lib.pdf.page_tables)."""
import fitz

from tomd.lib.pdf.page_tables import (INSTRUCTIONS, SCHEMA, model_tables, page_table_requests, render_page,
                                      request_id)
from tomd.lib.pdf.pipeline import _deck_tables, run_pipeline
from tomd.lib.pdf.types import Line, Section, SectionKind, Span

_ROWS = [["Name", "Value"], ["alpha", "1"], ["beta", "2"]]


def _doc(pages):
    """pages: list of lists of (x, y, text)."""
    doc = fitz.open()
    for items in pages:
        page = doc.new_page(width=612, height=792)
        for x, y, t in items:
            page.insert_text((x, y), t, fontsize=10)
    return doc


def _grid(rows, y0=100):
    return [(72 + 150 * c, y0 + 20 * r, t) for r, row in enumerate(rows) for c, t in enumerate(row) if t]


def _answers(doc, per_page):
    return {request_id(render_page(doc[pg])): {"tables": t} for pg, t in per_page.items()}


def _table(rows, cont_prev=False, cont_next=False):
    return {"rows": rows, "continues_from_previous_page": cont_prev, "continues_on_next_page": cont_next}


def test_one_request_per_page_and_ids_follow_the_image():
    doc = _doc([_grid(_ROWS), _grid(_ROWS), [(72, 100, "other")]])
    reqs = page_table_requests(doc)
    assert [r["page"] for r in reqs] == [0, 1, 2]
    assert reqs[0]["id"] == reqs[1]["id"] != reqs[2]["id"]       # same image, same id
    assert reqs[0]["id"] == page_table_requests(doc)[0]["id"]    # stable
    assert "tables" in SCHEMA["properties"] and "table" in INSTRUCTIONS


def test_words_stay_the_pages_own():
    doc = _doc([_grid(_ROWS)])
    wrong = [["Name", "Value"], ["alpha", "1 invented"], ["beta", "2"]]
    secs = model_tables(doc, doc, _answers(doc, {0: [_table(wrong)]}), [])
    assert len(secs) == 1
    assert secs[0].text.splitlines() == ["Name | Value", "alpha | 1", "beta | 2"]
    assert secs[0].metadata["table_source"] == "page-model"
    assert secs[0].metadata["uncertain_reasons"] == ["single-source", "page-model"]
    # a table none of whose words are on the page adds nothing
    assert model_tables(doc, doc, _answers(doc, {0: [_table([["x", "y"]])]}), []) == []


def test_no_table_where_tomd_already_has_one():
    doc = _doc([_grid(_ROWS)])
    ln = Line(spans=[Span(text="alpha", bbox=(72, 110, 110, 125))], bbox=(72, 110, 110, 125), page_num=0)
    existing = Section(kind=SectionKind.TABLE, text="x", lines=[ln], page_num=0)
    assert model_tables(doc, doc, _answers(doc, {0: [_table(_ROWS)]}), [existing]) == []


def test_continued_pieces_join_and_a_repeated_header_is_dropped():
    more = [["Name", "Value"], ["gamma", "3"]]
    doc = _doc([_grid(_ROWS, y0=600), _grid(more)])
    ans = _answers(doc, {0: [_table(_ROWS, cont_next=True)], 1: [_table(more, cont_prev=True)]})
    secs = model_tables(doc, doc, ans, [])
    assert len(secs) == 1
    assert secs[0].text.splitlines() == ["Name | Value", "alpha | 1", "beta | 2", "gamma | 3"]
    assert sorted(secs[0].metadata["page_bboxes"]) == [0, 1]
    # a piece with another column count starts a new table
    three = [["Name", "Value", "gamma"]]
    doc2 = _doc([_grid(_ROWS, y0=600), _grid(three)])
    ans2 = _answers(doc2, {0: [_table(_ROWS, cont_next=True)], 1: [_table(three, cont_prev=True)]})
    assert len(model_tables(doc2, doc2, ans2, [])) == 2


def test_malformed_answers_add_nothing():
    doc = _doc([_grid(_ROWS)])
    rid = request_id(render_page(doc[0]))
    for bad in (None, {}, {"tables": "x"}, {"tables": [{"rows": []}]}, {"tables": [{"rows": [[1, 2]]}]}):
        assert model_tables(doc, doc, {rid: bad}, []) == []
    assert model_tables(doc, doc, None, []) == []


def test_skipped_paper_with_answers_emits_its_tables():
    doc = _doc([_grid(_ROWS)])
    assert _deck_tables(doc, None) is None
    assert _deck_tables(doc, _answers(doc, {0: []})) is None
    res = _deck_tables(doc, _answers(doc, {0: [_table(_ROWS)]}))
    assert not res.skipped and res.page_count == 1
    assert "| alpha | 1 |" in res.md and "only its tables are converted" in res.md


def test_pipeline_adds_a_model_table_only_with_answers(tmp_path):
    prose = ["This paper proposes a change to the standard library for range adaptors and views."] * 30
    lines = [(72, 100 + 14 * i, t) for i, t in enumerate(prose + ["Our vote: strongly for 5, against 2."])]
    doc = _doc([lines])
    path = tmp_path / "p.pdf"
    doc.save(str(path))
    base = run_pipeline(path).md
    assert run_pipeline(path, page_tables={}).md == base
    ans = _answers(doc, {0: [_table([["strongly for", "against"], ["5,", "2."]])]})
    md = run_pipeline(path, page_tables=ans).md
    assert md != base and "| strongly for | against |" in md
