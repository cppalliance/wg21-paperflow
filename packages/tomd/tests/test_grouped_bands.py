# Copyright (c) 2026 Rob Beeston (rob@cppalliance.org)
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""Rule bands that hold several records (ruled._split_grouped_bands)."""
from tomd.lib.pdf.ruled import _split_grouped_bands
from tomd.lib.pdf.select import table_flags
from tomd.lib.pdf.types import Line, Span, TableCandidate

H = 9.0                     # line height
X = (10.0, 120.0, 230.0)    # column starts


def _ln(text, col, y, width=None):
    x = X[col]
    w = width if width is not None else 5.0 * len(text)
    return Line(spans=[Span(text=text, bbox=(x, y, x + w, y + H))], bbox=(x, y, x + w, y + H), page_num=1)


def _band(*lines):
    """lines: (col, text, y[, width]); a row of cells, each a list of Lines."""
    cells = [[] for _ in X]
    for col, text, y, *w in lines:
        cells[col].append(_ln(text, col, y, *w))
    return cells


def _texts(rows):
    return [[" ".join(ln.text for ln in c) for c in r] for r in rows]


HEADER = _band((0, "Param", 0), (1, "Alias", 0), (2, "Description of each name", 0))


def test_records_on_shared_baselines_split_into_rows():
    body = _band((0, "G", 20), (2, "Graph", 20),
                 (1, "graph_ref_t", 32), (2, "Graph reference", 32),
                 (0, "GV", 44), (2, "Graph value", 44))
    out = _split_grouped_bands([HEADER, body])
    assert _texts(out) == [["Param", "Alias", "Description of each name"], ["G", "", "Graph"],
                           ["", "graph_ref_t", "Graph reference"], ["GV", "", "Graph value"]]


def test_wrapped_description_joins_its_record():
    body = _band((0, "V", 20), (1, "vertex_t", 20), (2, "Vertex descriptor and more words here", 20, 100.0),
                 (2, "continued", 32),
                 (0, "E", 44), (1, "edge_t", 44), (2, "Edge descriptor", 44))
    out = _split_grouped_bands([HEADER, body])
    assert _texts(out)[1:] == [["V", "vertex_t", "Vertex descriptor and more words here continued"],
                               ["E", "edge_t", "Edge descriptor"]]


def test_one_record_per_band_with_every_cell_wrapping_stays_whole():
    # both quotes wrap on every line: one record per band
    body = _band((0, "we consider coroutines a", 20, 100.0), (1, "coroutines are easier to", 20, 100.0),
                 (0, "poor choice for a basis", 32, 100.0), (1, "understand and maintain", 32, 100.0))
    assert _texts(_split_grouped_bands([HEADER, body])) == _texts([HEADER, body])


def test_cells_off_shared_baselines_stay_whole():
    # code in one column, a paragraph beside it at its own line pitch
    body = _band((0, "template<class Fn,", 20), (0, "class Tuple>", 31),
                 (1, "If the expression", 25), (1, "is well formed", 36))
    assert _texts(_split_grouped_bands([HEADER, body])) == _texts([HEADER, body])


def test_code_listing_band_stays_whole():
    body = _band((0, "int f() {", 20), (1, "auto f() {", 20),
                 (0, "  return 1;", 32), (1, "  return 1;", 32),
                 (0, "}", 44), (1, "}", 44))
    for c in body:
        for ln in c:
            for s in ln.spans:
                s.monospace = True
    assert _texts(_split_grouped_bands([HEADER, body])) == _texts([HEADER, body])


def test_grouped_rows_with_blank_keys_are_not_ragged():
    rows = [HEADER, _band((0, "G", 20), (2, "Graph", 20)), _band((1, "graph_ref_t", 32), (2, "Graph ref", 32)),
            _band((0, "GV", 44), (2, "Graph value", 44)), _band((0, "V", 56), (1, "vertex_t", 56), (2, "Vertex", 56)),
            _band((1, "vertex_ref_t", 68), (2, "Vertex ref", 68))]
    plain = TableCandidate("rules", rows, {1: (0, 0, 300, 80)})
    grouped = TableCandidate("rules", rows, {1: (0, 0, 300, 80)}, flags=["grouped-bands"])
    assert "ragged-columns" in table_flags(plain)
    assert "ragged-columns" not in table_flags(grouped)


def test_line_opening_with_closing_punctuation_continues():
    body = _band((0, "class bar : public base", 20), (1, "class bar : base,", 20),
                 (0, "{};", 32), (1, "{};", 32),
                 (0, "struct x", 44), (1, "struct y", 44),
                 (0, "union u", 56), (1, "union v", 56),
                 (0, "enum e", 68), (1, "enum f", 68))
    out = _split_grouped_bands([HEADER, body])
    assert _texts(out)[1:] == [["class bar : public base {};", "class bar : base, {};", ""],
                               ["struct x", "struct y", ""], ["union u", "union v", ""], ["enum e", "enum f", ""]]


def test_declaration_broken_over_lines_stays_one_record():
    # code in a proportional font: lines ending in "," or ":" are unfinished
    first = _band((0, "foo::foo(int x) :", 20), (1, "foo::foo(int x) :", 20),
                  (0, "a(x)", 32), (1, "a(x),", 32), (0, "{...}", 44), (1, "{...}", 44))
    body = _band((0, "class bar :", 70), (1, "class bar :", 70),
                 (0, "public base,", 82), (1, "public base,", 82),
                 (0, "public mixin", 94), (1, "public mixin,", 94),
                 (0, "{};", 106), (1, "{};", 106))
    out = _split_grouped_bands([HEADER, first, body])
    assert len(out) == 3


def test_identifier_broken_at_the_column_edge_continues():
    body = _band((0, "Go", 20), (1, "io.Reader", 20), (2, "ok", 20),
                 (0, "Rust", 32), (1, "AsyncRead", 32), (2, "ok", 32),
                 (0, "Ours", 44), (1, "ReadStream::read_som", 44), (2, "ok", 44),
                 (1, "e()", 56))
    out = _split_grouped_bands([HEADER, body])
    assert _texts(out)[-1] == ["Ours", "ReadStream::read_som e()", "ok"]
