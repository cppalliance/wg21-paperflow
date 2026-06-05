#
# Copyright (c) 2026 Dmitriy Chukhin (dmitriy@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow

"""Tests for lib.tables (shared code-comparison table renderer).

These pin the exact markup, which is the compatibility target for the PDF
emitter's CODE_COMPARISON output on the sg branch. If this format changes,
the DRY-up after rebase (one shared renderer for both converters) must change
both copies together, so an exact-string assertion here is intentional.
"""

from tomd.lib.tables import render_code_comparison_table


class TestRenderCodeComparisonTable:
    def test_empty_grid_returns_empty(self):
        assert render_code_comparison_table([]) == ""

    def test_header_and_one_data_row_exact_markup(self):
        out = render_code_comparison_table(
            [["Before", "After"], ["int a;", "int b;"]]
        )
        expected = (
            '<table border="1" rules="all" cellpadding="6" cellspacing="0"'
            ' style="border-collapse: collapse; width: 100%;">\n'
            "<tr>\n"
            '<th style="border: 1px solid #999; padding: 6px 10px;'
            ' vertical-align: top; width: 50%;">Before</th>\n'
            '<th style="border: 1px solid #999; padding: 6px 10px;'
            ' vertical-align: top; width: 50%;">After</th>\n'
            "</tr>\n"
            "<tr>\n"
            '<td style="border: 1px solid #999; padding: 6px 10px;'
            ' vertical-align: top; width: 50%;">'
            '<pre style="margin: 0;">int a;</pre></td>\n'
            '<td style="border: 1px solid #999; padding: 6px 10px;'
            ' vertical-align: top; width: 50%;">'
            '<pre style="margin: 0;">int b;</pre></td>\n'
            "</tr>\n"
            "</table>"
        )
        assert out == expected

    def test_code_is_html_escaped(self):
        out = render_code_comparison_table(
            [["A", "B"], ["vector<int> v;", "x && y;"]]
        )
        assert "vector&lt;int&gt; v;" in out
        assert "x &amp;&amp; y;" in out

    def test_header_cell_has_no_pre_wrapper(self):
        out = render_code_comparison_table([["Before", "After"], ["c;", "d;"]])
        assert ">Before</th>" in out
        assert "<pre" not in out.split("</tr>", 1)[0]  # header row has no <pre>

    def test_empty_cell_emitted_without_pre(self):
        out = render_code_comparison_table([["A", "B"], ["code;", ""]])
        # the empty data cell is a bare <td>, not a <pre>
        assert '<td style="border: 1px solid #999; padding: 6px 10px;' \
               ' vertical-align: top; width: 50%;"></td>' in out

    def test_three_columns_width(self):
        out = render_code_comparison_table([["A", "B", "C"], ["x;", "y;", "z;"]])
        assert "width: 33%;" in out

    def test_has_header_false_emits_all_td(self):
        out = render_code_comparison_table(
            [["x;", "y;"]], has_header=False
        )
        assert "<th" not in out
        assert "<pre style=\"margin: 0;\">x;</pre>" in out

    def test_ragged_rows_padded(self):
        out = render_code_comparison_table([["A", "B"], ["only;"]])
        # second column of the short data row is an empty <td>
        assert out.count("<td") == 2
