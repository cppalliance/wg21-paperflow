#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Source font evidence for the code-boundary judge (C9 ``prose_in_fence``).

The judge sees only the candidate markdown of one fence. Data literals,
ASCII-diagram captions and column headers of a monospace figure read like
prose, so the model flags them as ``prose_in_fence`` although the author
set them in a monospace font. The deterministic aligner
(``det.code_fence_align``) already has the font layer of the PDF; this
module reuses that evidence per fence and offers it twice:

* :meth:`FenceFontEvidence.line` renders a short evidence block that is
  appended to the judge's user message (the prompt tells the model how
  to weigh it for C9);
* :func:`clamp_source_monospace` rewrites any surviving ``prose_in_fence``
  finding whose quote is (part of) a monospace-set source line to
  ``clean``.

Abstains (returns no evidence) when the source is not a PDF, cannot be
read, or has no monospace font at all: the judge then runs as before.
Library-pure: returns data, never persists.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from whisker.det.llm_readability.code_validate import code_units_with_spans
from whisker.det.pdf_geometry import PdfLine, is_monospace_line, load_pdf_lines
from whisker.llm.models import CodeBoundaryFinding, CodeBoundaryJudgment

logger = logging.getLogger(__name__)

__all__ = [
    "FenceFontEvidence",
    "SOURCE_MONOSPACE_NOTE",
    "clamp_source_monospace",
    "fence_font_evidence",
]

SOURCE_MONOSPACE_NOTE = "source-monospace clamp: monospace in PDF"
"""Reasoning text written into a clamped finding (greppable in sidecars)."""

_EVIDENCE_HEADER = "SOURCE FONT EVIDENCE"
_MAX_LISTED_PROPORTIONAL = 3
_LISTED_LINE_MAX_CHARS = 80
_MIN_MATCH_CHARS = 4
"""Shorter normalised lines (``}``, ``1``) match too many source lines to
count as evidence either way; they stay unmatched."""

_WORD_RE = re.compile(r"[A-Za-z0-9_]+")
_FENCE_OPENER_RE = re.compile(r"^\s*(?:`{3,}|~{3,})[^\n]*\n?")
"""The judge sometimes quotes the fence opener together with its first
body line ("```cpp\\n[1e16, ...]"); the opener carries no font evidence."""


def _normalise(text: str) -> str:
    """Word-token normalisation shared with the deterministic aligner.

    ASCII word tokens only: box-drawing and other symbol runs normalise to
    the empty string and stay unmatched, which is the conservative side.
    """
    return " ".join(_WORD_RE.findall(text)).lower()


@dataclass(frozen=True)
class FenceFontEvidence:
    """Font evidence for one fence.

    ``monospace`` / ``proportional`` hold the normalised body lines that
    matched a source line of that font (sets, deduplicated); the counts
    are per body line so they add up to ``total``. Blank body lines are
    not counted.
    """

    locus: str
    monospace: frozenset[str]
    proportional: frozenset[str]
    monospace_count: int
    proportional_count: int
    unmatched: int
    proportional_samples: tuple[str, ...] = ()

    @property
    def total(self) -> int:
        return self.monospace_count + self.proportional_count + self.unmatched

    @property
    def all_monospace(self) -> bool:
        return self.total > 0 and self.monospace_count == self.total

    def line(self) -> str:
        """Render the evidence block appended to the judge's user message."""
        parts = [
            f"{_EVIDENCE_HEADER} for {self.locus}: {self.monospace_count} of "
            f"{self.total} fence lines are set in a monospace font in the "
            f"source PDF, {self.proportional_count} match a proportional-font "
            f"line, {self.unmatched} have no confident match.",
        ]
        if self.all_monospace:
            parts.append("Every line of this fence is monospace in the source.")
        if self.proportional_samples:
            listed = "; ".join(
                repr(s[:_LISTED_LINE_MAX_CHARS]) for s in self.proportional_samples
            )
            parts.append(f"Proportional-font lines: {listed}.")
        return " ".join(parts)


def _font_index(pdf_lines: list[PdfLine]) -> tuple[set[str], set[str]]:
    """Document-wide normalised line sets by font. A text that occurs in
    both fonts (``int main`` in prose and in code) is ambiguous and
    dropped from both sets."""
    mono: set[str] = set()
    prop: set[str] = set()
    for pl in pdf_lines:
        norm = _normalise(pl.text)
        if len(norm) < _MIN_MATCH_CHARS:
            continue
        (mono if is_monospace_line(pl) else prop).add(norm)
    ambiguous = mono & prop
    return mono - ambiguous, prop - ambiguous


def fence_font_evidence(
    source_path: Path, candidate_md: str,
) -> dict[str, FenceFontEvidence]:
    """Evidence keyed by fence locus (``fence:N``, 1-based like the judge).

    Returns ``{}`` (abstain) for non-PDF sources, unreadable PDFs and
    PDFs without any monospace line.
    """
    if source_path.suffix.lower() != ".pdf":
        return {}
    try:
        pdf_lines = load_pdf_lines(source_path)
    except Exception as exc:  # PyMuPDF raises a zoo of types; abstain on any
        logger.warning("fence font evidence: cannot read %s: %s", source_path, exc)
        return {}
    mono, prop = _font_index(pdf_lines)
    if not mono:
        return {}

    evidence: dict[str, FenceFontEvidence] = {}
    for unit, _start, _end in code_units_with_spans(candidate_md):
        locus = f"fence:{unit.index + 1}"
        mono_hits: set[str] = set()
        prop_hits: set[str] = set()
        samples: list[str] = []
        mono_count = prop_count = unmatched = 0
        for raw in unit.body_lines:
            if not raw.strip():
                continue
            norm = _normalise(raw)
            if len(norm) >= _MIN_MATCH_CHARS and norm in mono:
                mono_hits.add(norm)
                mono_count += 1
            elif len(norm) >= _MIN_MATCH_CHARS and norm in prop:
                prop_hits.add(norm)
                prop_count += 1
                if len(samples) < _MAX_LISTED_PROPORTIONAL:
                    samples.append(raw.strip())
            else:
                unmatched += 1
        evidence[locus] = FenceFontEvidence(
            locus=locus,
            monospace=frozenset(mono_hits),
            proportional=frozenset(prop_hits),
            monospace_count=mono_count,
            proportional_count=prop_count,
            unmatched=unmatched,
            proportional_samples=tuple(samples),
        )
    return evidence


def _quote_norms(quote: str) -> list[str]:
    """Normalised, non-trivial lines of a candidate quote (opener dropped)."""
    body = _FENCE_OPENER_RE.sub("", quote, count=1)
    norms = (_normalise(part) for part in body.split("\n"))
    return [n for n in norms if len(n) >= _MIN_MATCH_CHARS]


def _within(norm: str, lines: frozenset[str]) -> bool:
    """``norm`` is a monospace-set line or a fragment of one. Only this
    direction is safe: a short source line contained in a long prose
    quote proves nothing about the quote."""
    return any(norm == ln or norm in ln for ln in lines)


def clamp_source_monospace(
    judgment: CodeBoundaryJudgment, evidence: FenceFontEvidence | None,
) -> tuple[CodeBoundaryJudgment, int]:
    """Rewrite ``prose_in_fence`` findings on monospace-set lines to clean.

    A finding is clamped when every non-trivial line of its
    ``candidate_quote`` is (a fragment of) a monospace-set source line of
    this fence and none is (a fragment of) a proportional-font line.
    Returns the (possibly unchanged) judgment and the number of clamped
    findings. The judgment verdict becomes ``pass`` when no non-clean
    finding remains.
    """
    if evidence is None or not evidence.monospace:
        return judgment, 0
    clamped = 0
    findings = []
    for finding in judgment.findings:
        if finding.kind == "prose_in_fence":
            norms = _quote_norms(finding.candidate_quote)
            if (
                norms
                and all(_within(n, evidence.monospace) for n in norms)
                and not any(_within(n, evidence.proportional) for n in norms)
            ):
                finding = _clean_copy(finding)
                clamped += 1
        findings.append(finding)
    if not clamped:
        return judgment, 0
    verdict = judgment.verdict
    if all(f.kind == "clean" for f in findings):
        verdict = "pass"
    return (
        judgment.model_copy(update={"findings": findings, "verdict": verdict}),
        clamped,
    )


def _clean_copy(finding: CodeBoundaryFinding) -> CodeBoundaryFinding:
    """Clean copy of a clamped finding; the note keeps the clamp auditable."""
    return finding.model_copy(update={
        "kind": "clean",
        "verdict": "pass",
        "rule_id": "none",
        "reasoning": SOURCE_MONOSPACE_NOTE,
    })
