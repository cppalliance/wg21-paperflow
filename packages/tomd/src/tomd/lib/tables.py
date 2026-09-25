#
# Copyright (c) 2026 Dmitriy Chukhin (dmitriy@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow

"""Shared HTML-table markup for code-comparison tables ("Tony Tables").

The HTML renderer (``lib/html/render.py::_render_mixed_code_table``) emits
side-by-side comparison tables as HTML. A PDF table is a pipe table or a
labeled fence group, never this markup. This module owns the table tag, cell
style, and code-cell wrapping for the HTML path.

It deliberately owns only the markup, not the iteration: the HTML converter
walks its own DOM. Non-code cells pass sanitized inline HTML.
"""

import html

# Marker flagging a structure-preserving HTML table (vs a lossy flattened one).
# Emitted by the HTML renderer for every mixed table. A PDF code table uses
# the same marker in front of a labeled fence group, not an HTML table.
MIXED_TABLE_MARKER = "<!-- tomd:mixed-table -->"

# Inline-styled table open tag. WG21 markdown is consumed by renderers with no
# shared stylesheet, so the presentation travels with the element.
TABLE_OPEN = (
    '<table border="1" rules="all" cellpadding="6" cellspacing="0"'
    ' style="border-collapse: collapse; width: 100%;">'
)
TABLE_CLOSE = "</table>"


def cell_style(num_cols: int) -> str:
    """Per-cell inline style with equal column widths for ``num_cols`` columns."""
    col_w = f"{100 // num_cols}%" if num_cols else "50%"
    return (f"border: 1px solid #999; padding: 6px 10px; "
            f"vertical-align: top; width: {col_w};")


def _rowspan_attr(rowspan: int) -> str:
    return f' rowspan="{rowspan}"' if rowspan and rowspan > 1 else ""


def code_cell(tag: str, code_text: str, style: str, *, rowspan: int = 1) -> str:
    """Render a code cell: ``<pre><code>`` wrapping HTML-escaped ``code_text``.

    ``tag`` is ``"th"`` or ``"td"``. ``code_text`` is raw code; this function
    escapes it, so ``<``/``&``/quotes survive inside the ``<pre>``.
    Blank lines are preserved as ``&#10;`` so they survive HTML rendering.
    """
    escaped = html.escape(code_text)
    escaped = "\n".join(line or "&#10;" for line in escaped.split("\n"))
    return (f'<{tag} style="{style}"{_rowspan_attr(rowspan)}>'
            f'<pre style="margin: 0;"><code>{escaped}</code></pre></{tag}>')


def text_cell(tag: str, inner_html: str, style: str, *, rowspan: int = 1) -> str:
    """Render a non-code cell. ``inner_html`` is emitted verbatim.

    The caller is responsible for preparing ``inner_html``: the PDF side passes
    HTML-escaped plain text, the HTML side passes sanitized inline HTML. This
    function never escapes, so it does not double-escape pre-escaped text nor
    mangle the kept inline tags.
    """
    return f'<{tag} style="{style}"{_rowspan_attr(rowspan)}>{inner_html}</{tag}>'
