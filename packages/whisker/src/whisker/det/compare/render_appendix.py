#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Render selected exhibits as an evidence appendix for a report.

``render_pdf`` dumps a whole comparison, which for this corpus runs to three
hundred pages. That is a reference archive, not evidence: nobody checks a claim
by reading three hundred pages. This renders only the pairs behind named claims,
grouped by claim, so a skeptical reader can verify each assertion in place.

Long blocks are truncated, with the omitted length stated. Evidence that lies
about its own completeness is worse than no evidence, so the cap is declared on
the page and the untruncated comparisons stay available alongside the report.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field

from whisker.branding.theme import ReportMeta, wrap_document
from whisker.det.compare.align import AlignedPair, PairStatus
from whisker.det.compare.exhibits import Exhibit

__all__ = ["ClaimEvidence", "PaperEvidence", "TEXT_CAP_CHARS", "render_appendix_html"]

# Enough to show a code block's shape and its defect without spilling a page.
TEXT_CAP_CHARS = 1100

_EXTRA_CSS = """\
.appendix-intro {
  font-size: 8.6pt;
  color: var(--ink-muted);
  margin: 0 0 18pt 0;
  max-width: 46em;
}

.claim {
  margin: 0 0 22pt 0;
  page-break-inside: auto;
  break-inside: auto;
}
.claim > h2 {
  margin-top: 20pt;
  padding-bottom: 5pt;
  border-bottom: 1pt solid var(--rule);
}
.claim-assertion {
  font-size: 8.6pt;
  color: var(--ink-soft);
  background: var(--panel);
  border-left: 2.5pt solid var(--brand-red);
  padding: 7pt 10pt;
  margin: 0 0 12pt 0;
}
.claim-assertion .src {
  display: block;
  font-size: 7.4pt;
  color: var(--ink-faint);
  margin-top: 3pt;
}

.paper-band {
  font-family: var(--font-body);
  font-size: 8.2pt;
  font-weight: 600;
  color: var(--ink);
  margin: 12pt 0 4pt 0;
  page-break-after: avoid;
  break-after: avoid;
}
.paper-band .count {
  font-weight: 400;
  color: var(--ink-faint);
  margin-left: 6pt;
}

table.ex {
  table-layout: fixed;
  width: 100%;
  font-size: 7.4pt;
  margin: 0 0 10pt 0;
  page-break-inside: auto;
  break-inside: auto;
}
table.ex thead { display: table-header-group; }
table.ex thead th {
  font-size: 7.6pt;
  padding: 4pt 7pt;
  border-bottom: 1pt solid var(--rule);
}
table.ex col.gutter { width: 26pt; }
table.ex thead th:nth-child(2) { width: 50%; }

table.ex td {
  vertical-align: top;
  padding: 4pt 7pt;
  border-bottom: 0.5pt solid var(--rule);
  font-family: var(--font-code);
  white-space: pre-wrap;
  overflow-wrap: break-word;
  page-break-inside: avoid;
  break-inside: avoid;
}
table.ex td.idx {
  font-family: var(--font-body);
  font-size: 6.4pt;
  color: var(--ink-faint);
  text-align: right;
  white-space: nowrap;
  padding: 4pt 3pt;
}
table.ex td.absent {
  font-family: var(--font-body);
  font-style: italic;
  color: var(--ink-faint);
  background: #fbe4e4;
}

tr.ex-changed td { background: #fdf3d7; }
tr.ex-left_only td { background: #fbe4e4; }
tr.ex-right_only td { background: #e2eef4; }

.btype {
  display: block;
  font-family: var(--font-body);
  font-size: 5.8pt;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--ink-faint);
  margin-bottom: 1.5pt;
}
.trunc {
  display: block;
  font-family: var(--font-body);
  font-style: italic;
  font-size: 6.4pt;
  color: var(--ink-faint);
  margin-top: 2pt;
}
.none {
  font-size: 8.2pt;
  color: var(--ink-faint);
  font-style: italic;
  margin: 0 0 12pt 0;
}
"""


@dataclass(frozen=True)
class PaperEvidence:
    """Exhibits for one claim on one paper, plus the full match count."""

    pid: str
    exhibits: list[Exhibit]
    total: int


@dataclass(frozen=True)
class ClaimEvidence:
    """One report claim and the exhibits that support or refute it."""

    claim_id: str
    title: str
    assertion: str
    source: str
    candidate_label: str
    reference_label: str
    papers: list[PaperEvidence] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(p.total for p in self.papers)

    @property
    def shown(self) -> int:
        return sum(len(p.exhibits) for p in self.papers)


def _escape(text: str) -> str:
    return html.escape(text, quote=False)


def _body(text: str) -> str:
    stripped = text.rstrip()
    if len(stripped) <= TEXT_CAP_CHARS:
        return _escape(stripped)
    omitted = len(stripped) - TEXT_CAP_CHARS
    return (
        _escape(stripped[:TEXT_CAP_CHARS])
        + f'<span class="trunc">[{omitted:,} further characters omitted]</span>'
    )


def _cell(pair: AlignedPair, side: str, other_label: str) -> str:
    block = pair.left if side == "left" else pair.right
    if block is None:
        return f'<td class="absent">absent &mdash; no counterpart to the {_escape(other_label)} block</td>'
    label = f'<span class="btype">{block.block_type.value}</span>'
    return f"<td>{label}{_body(block.text)}</td>"


def _row(exhibit: Exhibit, candidate_label: str, reference_label: str) -> str:
    pair = exhibit.pair
    status = pair.status.value if isinstance(pair.status, PairStatus) else str(pair.status)
    return (
        f'<tr class="ex-{status}">'
        f'<td class="idx">{exhibit.index + 1}</td>'
        + _cell(pair, "left", reference_label)
        + _cell(pair, "right", candidate_label)
        + "</tr>"
    )


def _claim_section(claim: ClaimEvidence) -> str:
    parts = [
        '<section class="claim">',
        f"<h2>{_escape(claim.claim_id)}. {_escape(claim.title)}</h2>",
        '<div class="claim-assertion">'
        f"{_escape(claim.assertion)}"
        f'<span class="src">{_escape(claim.source)}</span>'
        "</div>",
    ]

    if claim.total == 0:
        parts.append(
            '<p class="none">No occurrences detected across the corpus. '
            "The claim is not supported by this detector.</p></section>"
        )
        return "".join(parts)

    header = (
        '<table class="ex">'
        '<colgroup><col class="gutter"><col><col></colgroup>'
        "<thead><tr><th>Pair</th>"
        f"<th>{_escape(claim.candidate_label)}</th>"
        f"<th>{_escape(claim.reference_label)}</th>"
        "</tr></thead><tbody>"
    )

    for paper in claim.papers:
        if paper.total == 0:
            continue
        shown = len(paper.exhibits)
        suffix = (
            f"{paper.total} occurrence{'s' if paper.total != 1 else ''}"
            if shown == paper.total
            else f"{shown} of {paper.total} occurrences shown"
        )
        parts.append(
            f'<div class="paper-band">{_escape(paper.pid)}'
            f'<span class="count">{suffix}</span></div>'
        )
        rows = [
            _row(exhibit, claim.candidate_label, claim.reference_label)
            for exhibit in paper.exhibits
        ]
        parts.append(header + "\n".join(rows) + "</tbody></table>")

    parts.append("</section>")
    return "".join(parts)


def render_appendix_html(
    claims: list[ClaimEvidence],
    *,
    title: str,
    subtitle: str = "",
    intro: str = "",
    fields: tuple[tuple[str, str], ...] = (),
) -> str:
    """Render claim-grouped exhibits as branded landscape HTML."""
    body = [f'<p class="appendix-intro">{_escape(intro)}</p>'] if intro else []
    body.extend(_claim_section(claim) for claim in claims)

    meta = ReportMeta(
        title=title,
        subtitle=subtitle,
        fields=fields
        or (
            ("Claims", str(len(claims))),
            ("Exhibits shown", str(sum(c.shown for c in claims))),
            ("Occurrences detected", str(sum(c.total for c in claims))),
        ),
    )
    return wrap_document(
        "".join(body), meta, extra_css=_EXTRA_CSS, landscape=True
    )
