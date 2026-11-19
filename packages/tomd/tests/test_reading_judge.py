# Copyright (c) 2026 Rob Beeston (rob@cppalliance.org)
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""Outside reading judge: requests out, picks in (tomd.lib.pdf.judge, select.select_tables)."""
import fitz

from conftest import make_span
from tomd.lib.pdf.judge import (LETTERS, MAX_PAGES, answer_pick, judge_request, prompt_text,
                                region_readings, render_crops)
from tomd.lib.pdf.select import select_tables
from tomd.lib.pdf.types import Line, TableCandidate


def _line(text, x, y, page=0):
    return Line(spans=[make_span(text, bbox=(x, y, x + 6 * len(text), y + 10))],
                bbox=(x, y, x + 6 * len(text), y + 10), page_num=page)


def _cand(source, rows, page=0, x0=50, y0=100, row_h=20, col_w=150):
    cells = [[[_line(t, x0 + c * col_w, y0 + r * row_h, page)] if t else []
              for c, t in enumerate(row)] for r, row in enumerate(rows)]
    bbox = (x0, y0, x0 + col_w * max(len(r) for r in rows), y0 + row_h * len(rows))
    return TableCandidate(source, cells, {page: bbox})


_A = [["Name", "Value"], ["alpha", "1"], ["beta", "2"], ["gamma", "3"]]
_B = [["Name", "Value"], ["alpha", "1"], ["beta 2", ""], ["gamma", "3"]]


def test_one_reading_or_identical_readings_need_no_judge():
    a = _cand("grid", _A)
    assert judge_request(region_readings(a, [])) is None
    assert judge_request(region_readings(a, [_cand("rules", _A)])) is None


def test_request_hides_which_reading_is_today_and_is_stable():
    a, b = _cand("grid", _A), _cand("rules", _B)
    req1, order1 = judge_request(region_readings(a, [b]))
    req2, order2 = judge_request(region_readings(b, [a]))
    # the same readings come in the same order whichever reader was primary
    assert req1["readings"] == req2["readings"]
    assert [c.source for c in order1] == [c.source for c in order2]
    assert order1[req1["today"]] is a and order2[req2["today"]] is b
    assert req1["id"] == req2["id"] and len(req1["id"]) == 16
    assert req1["pieces"] == [[0, [38.0, 88.0, 362.0, 192.0]]]


def test_regions_over_too_many_pages_keep_today():
    pages = [_cand("grid", _A, page=p) for p in range(MAX_PAGES + 1)]
    multi = TableCandidate("grid", pages[0].rows, {p: c.bboxes[p] for p, c in enumerate(pages)})
    assert judge_request(region_readings(multi, [_cand("rules", _B)])) is None


def test_only_a_confident_different_well_formed_answer_is_adopted():
    req, _ = judge_request(region_readings(_cand("grid", _A), [_cand("rules", _B)]))
    other = 1 - req["today"]
    rid = req["id"]
    assert answer_pick(req, None) is None
    assert answer_pick(req, {rid: {"pick": other, "confidence": "low"}}) is None
    assert answer_pick(req, {rid: {"pick": req["today"], "confidence": "high"}}) is None
    assert answer_pick(req, {rid: {"pick": 5, "confidence": "high"}}) is None
    assert answer_pick(req, {rid: {"pick": True, "confidence": "high"}}) is None
    assert answer_pick(req, {rid: "B"}) is None
    assert answer_pick(req, {"other-id": {"pick": other, "confidence": "high"}}) is None
    assert answer_pick(req, {rid: {"pick": other, "confidence": "medium"}}) == (other, "medium")


def test_prompt_letters_the_readings_and_marks_empty_cells():
    req, _ = judge_request(region_readings(_cand("grid", _A), [_cand("rules", _B)]))
    text = prompt_text(req)
    assert "### Reading A (4 rows)" in text and "### Reading B (4 rows)" in text
    assert "beta 2 | ·" in text
    assert "grid" not in text and "rules" not in text     # the judge never learns the reader
    assert len(LETTERS) >= 2


def test_crops_cover_every_page_piece():
    doc = fitz.open()
    for _ in range(2):
        doc.new_page(width=612, height=792)
    req = {"pieces": [[0, [38.0, 88.0, 362.0, 192.0]], [1, [0.0, 0.0, 612.0, 792.0]]]}
    crops = render_crops(doc, req)
    assert len(crops) == 2 and all(c.startswith(b"\x89PNG") for c in crops)
    big = fitz.Pixmap(crops[1])
    assert max(big.width, big.height) <= 1568


class TestSelection:
    # table_source is set later in the pipeline: the emitted rows tell which reading won
    def _run(self, answers=None, requests=None):
        return select_tables([], [_cand("rules", _B)], [_cand("grid", _A)], [],
                             judge_answers=answers, judge_requests=requests)

    def test_without_answers_source_priority_decides_and_the_region_is_listed(self):
        reqs = []
        out = self._run(requests=reqs)
        assert len(out) == 1 and "beta | 2" in out[0].text          # grid outranks rules
        assert out[0].text == self._run()[0].text
        assert len(reqs) == 1 and reqs[0]["sources"][reqs[0]["today"]] == "grid"
        assert "judged" not in out[0].metadata

    def test_a_confident_answer_picks_the_other_reading(self):
        reqs = []
        self._run(requests=reqs)
        req = reqs[0]
        other = 1 - req["today"]
        out = self._run({req["id"]: {"pick": other, "confidence": "high"}})
        assert len(out) == 1 and "beta 2 | " in out[0].text
        assert out[0].metadata["judged"] == "rules over grid (high)"

    def test_a_low_confidence_answer_keeps_today(self):
        reqs = []
        self._run(requests=reqs)
        req = reqs[0]
        out = self._run({req["id"]: {"pick": 1 - req["today"], "confidence": "low"}})
        assert "beta | 2" in out[0].text and "judged" not in out[0].metadata
