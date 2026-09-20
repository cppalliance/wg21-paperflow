#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Render an AlignedDocument as a block-locked two-pane HTML comparison.

Each aligned pair becomes one table row: left pane and right pane are
structurally locked (heading vs heading, code vs code) so that the
comparison never drifts. No JavaScript scroll-sync needed.
"""

from __future__ import annotations

import html

from whisker.det.compare.align import AlignedDocument, AlignedPair, PairStatus, WordSpan

__all__ = ["render_html"]

_CSS = """\
:root {
  --bg: #fff; --fg: #1a1a2e; --border: #ddd;
  --equal-bg: #f8f9fa; --changed-bg: #fff3cd;
  --left-only-bg: #f8d7da; --right-only-bg: #d1ecf1;
  --del-bg: #fecaca; --ins-bg: #bbf7d0;
  --mono: 'JetBrains Mono', 'Fira Code', monospace;
  --sans: 'Inter', -apple-system, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #1a1a2e; --fg: #e0e0e0; --border: #333;
    --equal-bg: #1e1e2e; --changed-bg: #3d3200;
    --left-only-bg: #3d0000; --right-only-bg: #002b36;
    --del-bg: #5c0000; --ins-bg: #003d00;
  }
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: var(--sans); background: var(--bg); color: var(--fg); padding: 1rem; }
h1 { font-size: 1.4rem; margin-bottom: 1rem; }
.stats { margin-bottom: 1rem; font-size: 0.85rem; color: #666; }
.controls { margin-bottom: 1rem; }
.controls label { margin-right: 1rem; cursor: pointer; }
table { width: 100%; border-collapse: collapse; table-layout: fixed; }
th { background: var(--border); padding: 0.5rem; text-align: left; font-size: 0.8rem; }
td { vertical-align: top; padding: 0.4rem 0.6rem; border: 1px solid var(--border);
     font-family: var(--mono); font-size: 0.75rem; white-space: pre-wrap;
     word-break: break-word; width: 50%; }
tr.equal td { background: var(--equal-bg); }
tr.changed td { background: var(--changed-bg); }
tr.left_only td { background: var(--left-only-bg); }
tr.right_only td { background: var(--right-only-bg); }
.del { background: var(--del-bg); text-decoration: line-through; }
.ins { background: var(--ins-bg); font-weight: 600; }
.block-type { font-size: 0.6rem; color: #888; text-transform: uppercase; display: block; margin-bottom: 2px; }
tr.hidden { display: none; }
kbd { font-size: 0.7rem; background: var(--border); padding: 2px 4px; border-radius: 3px; }
"""

_JS = """\
document.addEventListener('DOMContentLoaded', () => {
  const showAll = document.getElementById('show-all');
  const showDiff = document.getElementById('show-diff');
  const rows = document.querySelectorAll('tbody tr');
  function filter(mode) {
    rows.forEach(r => {
      if (mode === 'diff') r.classList.toggle('hidden', r.classList.contains('equal'));
      else r.classList.remove('hidden');
    });
  }
  showAll.addEventListener('change', () => filter('all'));
  showDiff.addEventListener('change', () => filter('diff'));
  document.addEventListener('keydown', e => {
    if (e.key === 'd') { showDiff.checked = true; filter('diff'); }
    if (e.key === 'a') { showAll.checked = true; filter('all'); }
  });
});
"""


def _escape(text: str) -> str:
    return html.escape(text, quote=False)


def _render_word_spans(spans: list[WordSpan]) -> str:
    if not spans:
        return ""
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


def _render_pair_row(pair: AlignedPair, idx: int) -> str:
    status_cls = pair.status.value
    left_html = ""
    right_html = ""

    if pair.left:
        btype = f'<span class="block-type">{pair.left.block_type.value}</span>'
        if pair.word_diff_left:
            left_html = btype + _render_word_spans(pair.word_diff_left)
        else:
            left_html = btype + _escape(pair.left.text)

    if pair.right:
        btype = f'<span class="block-type">{pair.right.block_type.value}</span>'
        if pair.word_diff_right:
            right_html = btype + _render_word_spans(pair.word_diff_right)
        else:
            right_html = btype + _escape(pair.right.text)

    return f'<tr class="{status_cls}" data-idx="{idx}"><td>{left_html}</td><td>{right_html}</td></tr>'


def render_html(doc: AlignedDocument) -> str:
    """Render an AlignedDocument as a self-contained HTML string."""
    rows = "\n".join(_render_pair_row(p, i) for i, p in enumerate(doc.pairs))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Compare: {_escape(doc.left_label)} vs {_escape(doc.right_label)}</title>
<style>{_CSS}</style>
</head>
<body>
<h1>Side-by-side: {_escape(doc.left_label)} vs {_escape(doc.right_label)}</h1>
<div class="stats">
  {doc.total_pairs} blocks | {doc.equal_pairs} equal | {doc.changed_pairs} changed |
  {sum(1 for p in doc.pairs if p.status == PairStatus.LEFT_ONLY)} left-only |
  {sum(1 for p in doc.pairs if p.status == PairStatus.RIGHT_ONLY)} right-only
</div>
<div class="controls">
  <label><input type="radio" name="filter" id="show-all" checked> All blocks (<kbd>a</kbd>)</label>
  <label><input type="radio" name="filter" id="show-diff"> Differences only (<kbd>d</kbd>)</label>
</div>
<table>
<thead><tr><th>{_escape(doc.left_label)}</th><th>{_escape(doc.right_label)}</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
<script>{_JS}</script>
</body>
</html>"""
