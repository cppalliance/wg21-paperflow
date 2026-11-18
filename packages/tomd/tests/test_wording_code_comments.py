# Copyright (c) 2026 Rob Beeston (rob@cppalliance.org)
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""A wording section of code whose comments are set in a text font is code (wording_emit)."""
from tomd.lib.pdf.types import Line, Section, SectionKind, Span
from tomd.lib.pdf.wording_emit import _is_code_line, _render_wording_section


def _sp(text, mono=True):
    return Span(text=text, monospace=mono, wording_role="ins", bbox=(10.0, 0, 10.0 + 5 * len(text), 9))


def _sec(*lines):
    ls = [Line(spans=list(l)) for l in lines]
    return Section(kind=SectionKind.WORDING_ADD, text="\n".join(l.text for l in ls), lines=ls)


def test_code_example_with_text_font_comments_is_fenced():
    sec = _sec([_sp("struct X {")], [_sp("int a, b;")], [_sp("~X() = delete;")],
               [_sp("// deleted destructor makes X a non-implicit-lifetime class", mono=False)],
               [_sp("};")])
    out = _render_wording_section(sec)
    assert out.startswith("```") and "int a, b;" in out.split("\n")[2]
    assert "// deleted destructor" in out


def test_code_with_trailing_text_font_comment_is_a_code_line():
    assert _is_code_line(Line(spans=[_sp("pre(( s.g++, false )); "), _sp("// #1", mono=False)]))


def test_prose_starting_with_an_identifier_is_not_a_code_line():
    assert not _is_code_line(Line(spans=[_sp("std::foo"), _sp(" returns the value.", mono=False)]))


def test_prose_wording_with_inline_code_stays_prose():
    sec = _sec([_sp("Effects: Equivalent to ", mono=False), _sp("return x;")],
               [_sp("Remarks: this function is constexpr if ", mono=False), _sp("T"), _sp(" is.", mono=False)])
    assert not _render_wording_section(sec).startswith("```")
