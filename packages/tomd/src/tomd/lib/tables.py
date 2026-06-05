#
# Copyright (c) 2026 Dmitriy Chukhin (dmitriy@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow

"""Format-neutral table rendering shared by the PDF and HTML converters.

This module owns the *markup* for code-comparison tables ("Tony Tables":
side-by-side before/after code, where each cell is multi-line code that a
CommonMark pipe table would flatten). The renderer takes plain row/cell
strings so it has no dependency on either converter's internal types
(PDF `Span`/`Section` or HTML `bs4.Tag`).

The output is intentionally byte-identical to the PDF emitter's
`_render_html_table` on the ``sg/tomd-table-figures-abstract-metadata``
branch (the `CODE_COMPARISON` -> `HTML_TABLE` strategy). The HTML converter
calls this helper today so HTML papers and PDF papers render the same
comparison markup.

DRY-UP AFTER REBASE: this branch (the HTML labeled-grid work) is built on
`main` and the `sg` table-pipeline overhaul lands first. Once this work is
rebased onto `sg`, the PDF path should stop carrying its own copy of this
markup: reduce `lib/pdf/emit.py::_render_html_table` to a thin adapter that
flattens each `Section.columns` cell (its spans, splitting on the ``"\\n"``
sentinel span) into a cell string and delegates here. At that point both
converters share one renderer and the format can only ever change in one
place. Keep this helper's output stable until that swap is done, since the
PDF emitter's current output is the compatibility target.
"""

import html

# Inline-styled HTML table. WG21 markdown is consumed by renderers with no
# shared stylesheet, so the presentation travels with the element. These
# literals mirror the PDF emitter's `_render_html_table` exactly; see the
# DRY-UP note above before changing either copy.
_TABLE_OPEN = (
    '<table border="1" rules="all" cellpadding="6" cellspacing="0"'
    ' style="border-collapse: collapse; width: 100%;">'
)


def _cell_style(num_cols: int) -> str:
    col_w = f"{100 // num_cols}%" if num_cols else "50%"
    return (f"border: 1px solid #999; padding: 6px 10px; "
            f"vertical-align: top; width: {col_w};")


def render_code_comparison_table(
    rows: list[list[str]],
    *,
    has_header: bool = True,
) -> str:
    """Render a code-comparison grid as an HTML table with ``<pre>`` cells.

    ``rows`` is row-major: each inner list holds one row's cell strings, in
    column order, with multi-line cell text carrying embedded newlines.
    Ragged rows are padded with empty cells to the widest row.

    When ``has_header`` is true the first row is emitted as ``<th>`` header
    cells (plain text, no ``<pre>``); every other row is data. A header cell,
    or any empty cell, is emitted without a ``<pre>`` wrapper. Cell text is
    HTML-escaped, so code containing ``<``/``&``/quotes is preserved literally
    inside the ``<pre>``.

    Returns the empty string for an empty grid.
    """
    if not rows:
        return ""

    num_cols = max(len(row) for row in rows)
    style = _cell_style(num_cols)
    parts: list[str] = [_TABLE_OPEN]

    for row_index, row in enumerate(rows):
        parts.append("<tr>")
        is_header = has_header and row_index == 0
        tag = "th" if is_header else "td"
        for col_index in range(num_cols):
            text = row[col_index].strip() if col_index < len(row) else ""
            escaped = html.escape(text)
            if is_header or not text:
                parts.append(f'<{tag} style="{style}">{escaped}</{tag}>')
            else:
                parts.append(
                    f'<{tag} style="{style}">'
                    f'<pre style="margin: 0;">{escaped}</pre></{tag}>')
        parts.append("</tr>")

    parts.append("</table>")
    return "\n".join(parts)
