#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Render an AlignedDocument as a print-ready landscape side-by-side PDF.

The interactive HTML view is for reviewing at a desk; this is for the version
that gets attached to a report or handed to someone in a meeting. Two differences
follow from that.

Runs of consecutive identical blocks are collapsed to a single marker line. A
300-block paper that agrees on 200 blocks would otherwise produce forty pages of
matching text with the interesting parts scattered through it.

Colour is print-safe and on-brand: no dark mode, no saturated fills, and diff
tints light enough that black text stays legible if the page is printed in
greyscale.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

from whisker.branding.theme import ReportMeta, wrap_document
from whisker.det.compare.align import AlignedDocument, AlignedPair, PairStatus, WordSpan

__all__ = ["render_pdf_html", "COLLAPSE_THRESHOLD"]

# Below this many consecutive equal blocks it is clearer to just show them.
COLLAPSE_THRESHOLD = 3

_EXTRA_CSS = """\
.cmp-summary {
  display: flex;
  gap: 16pt;
  flex-wrap: wrap;
  margin: 0 0 12pt 0;
  font-size: 8.5pt;
  color: var(--ink-muted);
}
.cmp-summary b { color: var(--ink); font-weight: 600; }

.cmp-legend {
  display: flex;
  gap: 14pt;
  flex-wrap: wrap;
  align-items: center;
  margin: 0 0 14pt 0;
  font-size: 7.5pt;
  color: var(--ink-muted);
}
.cmp-chip {
  display: inline-block;
  padding: 1pt 5pt;
  border-radius: 2pt;
  border: 0.5pt solid var(--panel-edge);
  margin-right: 4pt;
}
.chip-equal { background: #ffffff; }
.chip-changed { background: #fdf3d7; }
.chip-left { background: #fbe4e4; }
.chip-right { background: #e2eef4; }

table.cmp {
  table-layout: fixed;
  font-size: 7.6pt;
  margin-top: 0;
  /* The base theme keeps tables whole; a 250-row comparison must be allowed to
     flow across pages or it is pushed off the document entirely. */
  page-break-inside: auto;
  break-inside: auto;
}
/* Repeat the pane headers on every page so a mid-document page still says
   which column is which. */
table.cmp thead { display: table-header-group; }
table.cmp tbody tr { page-break-inside: avoid; break-inside: avoid; }
table.cmp thead th {
  font-size: 8pt;
  padding: 5pt 7pt;
  border-bottom: 1pt solid var(--rule);
}
table.cmp thead th:first-child { width: 50%; }
table.cmp col.gutter { width: 22pt; }

table.cmp td {
  vertical-align: top;
  padding: 3.5pt 6pt;
  border-bottom: 0.5pt solid var(--rule);
  font-family: var(--font-code);
  white-space: pre-wrap;
  overflow-wrap: break-word;
  page-break-inside: avoid;
  break-inside: avoid;
}
table.cmp td.idx {
  font-family: var(--font-body);
  font-size: 6.5pt;
  color: var(--ink-faint);
  text-align: right;
  white-space: nowrap;
  padding: 3.5pt 3pt;
}

tr.changed td { background: #fdf3d7; }
tr.left_only td { background: #fbe4e4; }
tr.right_only td { background: #e2eef4; }

tr.collapsed td {
  background: var(--panel);
  font-family: var(--font-body);
  font-size: 7.5pt;
  color: var(--ink-faint);
  text-align: center;
  font-style: italic;
  padding: 3pt 6pt;
}

.btype {
  display: block;
  font-family: var(--font-body);
  font-size: 5.8pt;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--ink-faint);
  margin-bottom: 1.5pt;
}

.del {
  background: #f6cfcf;
  text-decoration: line-through;
  text-decoration-thickness: 0.4pt;
}
.ins {
  background: #cfe6d0;
  font-weight: 600;
}
"""


@dataclass(frozen=True)
class _CollapsedRun:
    """A stretch of consecutive identical blocks, shown as one line."""

    start: int
    count: int


def _escape(text: str) -> str:
    return html.escape(text, quote=False)


def _render_spans(spans: list[WordSpan]) -> str:
    parts: list[str] = []
    for span in spans:
        escaped = _escape(span.text)
        if span.tag == "equal":
            parts.append(escaped)
        elif span.tag == "delete":
            parts.append(f'<span class="del">{escaped}</span>')
        elif span.tag == "insert":
            parts.append(f'<span class="ins">{escaped}</span>')
    return " ".join(parts)


def _cell(pair: AlignedPair, side: str) -> str:
    block = pair.left if side == "left" else pair.right
    if block is None:
        return ""
    spans = pair.word_diff_left if side == "left" else pair.word_diff_right
    label = f'<span class="btype">{block.block_type.value}</span>'
    body = _render_spans(spans) if spans else _escape(block.text)
    return label + body


def _group(pairs: list[AlignedPair]) -> list[AlignedPair | _CollapsedRun]:
    """Collapse long runs of equal pairs, keeping everything else verbatim."""
    grouped: list[AlignedPair | _CollapsedRun] = []
    run_start = 0
    run: list[AlignedPair] = []

    def flush() -> None:
        if not run:
            return
        if len(run) >= COLLAPSE_THRESHOLD:
            grouped.append(_CollapsedRun(start=run_start, count=len(run)))
        else:
            grouped.extend(run)

    for index, pair in enumerate(pairs):
        if pair.status == PairStatus.EQUAL:
            if not run:
                run_start = index
            run.append(pair)
            continue
        flush()
        run = []
        grouped.append(pair)

    flush()
    return grouped


def _row(entry: AlignedPair | _CollapsedRun, index: int) -> str:
    if isinstance(entry, _CollapsedRun):
        last = entry.start + entry.count
        return (
            '<tr class="collapsed"><td class="idx"></td>'
            f'<td colspan="2">{entry.count} identical blocks '
            f"({entry.start + 1}&ndash;{last})</td></tr>"
        )
    return (
        f'<tr class="{entry.status.value}">'
        f'<td class="idx">{index + 1}</td>'
        f'<td>{_cell(entry, "left")}</td>'
        f'<td>{_cell(entry, "right")}</td>'
        "</tr>"
    )


def render_pdf_html(
    doc: AlignedDocument,
    title: str = "",
    subtitle: str = "",
) -> str:
    """Render an AlignedDocument as branded landscape HTML ready for printing."""
    left_only = sum(1 for p in doc.pairs if p.status == PairStatus.LEFT_ONLY)
    right_only = sum(1 for p in doc.pairs if p.status == PairStatus.RIGHT_ONLY)
    agreement = (doc.equal_pairs / doc.total_pairs * 100) if doc.total_pairs else 0.0

    rows: list[str] = []
    running = 0
    for entry in _group(list(doc.pairs)):
        if isinstance(entry, _CollapsedRun):
            rows.append(_row(entry, running))
            running += entry.count
        else:
            rows.append(_row(entry, running))
            running += 1

    summary = (
        '<div class="cmp-summary">'
        f"<span><b>{agreement:.1f}%</b> blocks identical</span>"
        f"<span><b>{doc.total_pairs}</b> block pairs</span>"
        f"<span><b>{doc.equal_pairs}</b> equal</span>"
        f"<span><b>{doc.changed_pairs}</b> changed</span>"
        f"<span><b>{left_only}</b> only in {_escape(doc.left_label)}</span>"
        f"<span><b>{right_only}</b> only in {_escape(doc.right_label)}</span>"
        "</div>"
    )

    legend = (
        '<div class="cmp-legend">'
        '<span><span class="cmp-chip chip-changed">&nbsp;&nbsp;</span>changed</span>'
        f'<span><span class="cmp-chip chip-left">&nbsp;&nbsp;</span>'
        f"only in {_escape(doc.left_label)}</span>"
        f'<span><span class="cmp-chip chip-right">&nbsp;&nbsp;</span>'
        f"only in {_escape(doc.right_label)}</span>"
        '<span><span class="del">struck</span> removed</span>'
        '<span><span class="ins">bold tint</span> added</span>'
        f"<span>runs of {COLLAPSE_THRESHOLD}+ identical blocks are collapsed</span>"
        "</div>"
    )

    table = (
        '<table class="cmp">'
        '<colgroup><col class="gutter"><col><col></colgroup>'
        "<thead><tr><th></th>"
        f"<th>{_escape(doc.left_label)}</th>"
        f"<th>{_escape(doc.right_label)}</th>"
        "</tr></thead><tbody>" + "\n".join(rows) + "</tbody></table>"
    )

    meta = ReportMeta(
        title=title or f"Side-by-side: {doc.left_label} vs {doc.right_label}",
        subtitle=subtitle,
        fields=(
            ("Left", doc.left_label),
            ("Right", doc.right_label),
            ("Block agreement", f"{agreement:.1f}% of {doc.total_pairs} pairs"),
        ),
    )

    return wrap_document(
        summary + legend + table, meta, extra_css=_EXTRA_CSS, landscape=True
    )
