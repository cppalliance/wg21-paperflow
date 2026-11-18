# Copyright (c) 2026 Rob Beeston (rob@cppalliance.org)
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""A run of monospace spans is one inline code span (emit._render_line_spans,
wording_emit._render_wording_line), and the fonts that set code are seen as monospace."""
from conftest import make_span
from tomd.lib.pdf.emit import _render_line_spans
from tomd.lib.pdf.mono import classify_monospace
from tomd.lib.pdf.types import Line
from tomd.lib.pdf.wording_emit import _render_wording_line


def _line(*parts, role=None):
    spans = [make_span(t, monospace=m) for t, m in parts]
    for s in spans:
        s.wording_role = role
    return Line(spans=spans, page_num=1)


def test_adjacent_monospace_spans_with_different_text_are_one_code_span():
    line = _line(("Values (e.g. ", False), ("compute_value", True), ("()", True), (")", False))
    assert _render_line_spans(line) == "Values (e.g. `compute_value()`)"


def test_whitespace_between_monospace_spans_stays_inside_the_code_span():
    line = _line(("use ", False), ("std::vector", True), (" ", False), ("<int>", True), (" here", False))
    assert _render_line_spans(line) == "use `std::vector <int>` here"


def test_monospace_runs_separated_by_prose_stay_apart():
    line = _line(("(", False), ("42", True), (", ", False), ("x", True), (")", False))
    assert _render_line_spans(line) == "(`42`, `x`)"


def test_wording_line_merges_a_monospace_run():
    line = _line(("calls ", False), ("f", True), ("(x)", True), (" first", False), role="context")
    assert _render_wording_line(line) == "calls `f(x)` first"


def test_code_fonts_are_monospace():
    for name in ("NimbusMonL-Regu", "NimbusMonL-ReguObli", "NimbusMonL-Bold", "CMITT10", "Aptos Mono,Bold"):
        assert classify_monospace(name), name


def test_text_fonts_are_not_monospace():
    for name in ("NimbusRomNo9L-Regu", "NimbusSanL-Regu", "Montserrat-Bold", "EB Garamond,Bold"):
        assert not classify_monospace(name), name
