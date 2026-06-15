#
# Copyright (c) 2026 Dmitriy Chukhin (dmitriy@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow

"""Tests for lib.tables (shared comparison-table markup primitives).

These pin the exact markup both the PDF emitter and the HTML renderer emit,
so the two converters render a comparison the same way. An exact-string
assertion here is intentional: a change to the format must be a deliberate
edit to this one module, visible to both callers.
"""

from tomd.lib.tables import (
    MIXED_TABLE_MARKER, TABLE_OPEN, TABLE_CLOSE, cell_style, code_cell, text_cell,
)


def test_markers_and_table_tag():
    assert MIXED_TABLE_MARKER == "<!-- tomd:mixed-table -->"
    assert TABLE_OPEN == (
        '<table border="1" rules="all" cellpadding="6" cellspacing="0"'
        ' style="border-collapse: collapse; width: 100%;">'
    )
    assert TABLE_CLOSE == "</table>"


def test_cell_style_width_by_column_count():
    assert "width: 50%;" in cell_style(2)
    assert "width: 33%;" in cell_style(3)
    assert "width: 100%;" in cell_style(1)
    # degenerate: no columns falls back to 50%
    assert "width: 50%;" in cell_style(0)


def test_code_cell_wraps_pre_code_and_escapes():
    style = cell_style(2)
    out = code_cell("td", "vector<int> v; a && b;", style)
    assert out == (
        f'<td style="{style}">'
        '<pre style="margin: 0;"><code>vector&lt;int&gt; v; a &amp;&amp; b;</code></pre>'
        "</td>"
    )


def test_code_cell_blank_lines_preserved():
    out = code_cell("td", "a;\n\nb;", cell_style(2))
    assert "<code>a;\n&#10;\nb;</code>" in out


def test_code_cell_header_tag():
    out = code_cell("th", "x;", cell_style(2))
    assert out.startswith("<th ")
    assert "<pre style=\"margin: 0;\"><code>x;</code></pre></th>" in out


def test_code_cell_rowspan():
    out = code_cell("td", "x;", cell_style(2), rowspan=3)
    assert ' rowspan="3"' in out
    # rowspan=1 (the default) emits no attribute
    assert " rowspan=" not in code_cell("td", "x;", cell_style(2))
    assert " rowspan=" not in code_cell("td", "x;", cell_style(2), rowspan=1)


def test_text_cell_emits_inner_verbatim():
    style = cell_style(2)
    # inner is already-prepared (escaped or sanitized) by the caller; the
    # primitive must not re-escape it
    out = text_cell("th", "Before", style)
    assert out == f'<th style="{style}">Before</th>'
    kept = text_cell("th", "<strong>Before</strong>", style)
    assert kept == f'<th style="{style}"><strong>Before</strong></th>'


def test_text_cell_rowspan():
    out = text_cell("td", "x", cell_style(2), rowspan=2)
    assert ' rowspan="2"' in out
