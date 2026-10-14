#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Source-vs-candidate code-fence boundary comparison (deterministic, no LLM).

Fence boundaries are token-preserving: swallowing a prose line into a fence or
leaving a code listing unfenced moves no token, so ``unigram_coverage``,
``content_recall`` and the LLM lane all stay green while the structure is wrong.

Two directions, both abstaining rather than accusing when unsure:

- **prose_in_fence** (Direction 1): a fenced body line whose normalised text
  matches a PDF line that is NOT monospaced. Catches prose swallowed into a
  fence.
- **code_outside_fence** (Direction 2): a run of >= ``CODE_RUN_MIN_LINES``
  consecutive monospaced PDF lines whose text appears in the candidate OUTSIDE
  any fence. The minimum-run constant keeps legitimate inline ``\\`foo\\``` spans
  from firing.

Abstains when:
- The source is not a PDF (HTML has no font geometry).
- The PDF contains no monospaced font at all (nothing to compare).
- A fence/prose line has no confident text match (tomd may join or reflow).

Library returns data; the caller decides what to do with it. Advisory by
construction: this module has no notion of a verdict.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from whisker import constants as C
from whisker.det.pdf_geometry import PdfLine, is_monospace_line, load_pdf_lines

_log = logging.getLogger(__name__)

__all__ = [
    "CodeFenceAlignment",
    "compare_code_fence_boundaries",
]

STATUS_CHECKED = "checked"
STATUS_ABSTAINED = "abstained"
STATUS_UNSUPPORTED = "unsupported"

_WORD_RE = re.compile(r"[A-Za-z0-9_]+")
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
_FRONT_MATTER_RE = re.compile(r"^---\s*$")


@dataclass(frozen=True)
class CodeFenceAlignment:
    """Where the candidate's fence boundaries disagree with the source's fonts.

    ``prose_in_fence`` holds normalised text of fenced lines that matched
    non-monospaced PDF lines (prose swallowed into a code block).

    ``code_outside_fence`` holds normalised text of unfenced lines that
    matched monospaced PDF runs (code left as prose).
    """

    status: str
    prose_in_fence: tuple[str, ...] = ()
    code_outside_fence: tuple[str, ...] = ()
    detail: str = ""

    @property
    def prose_in_fence_count(self) -> int:
        return len(self.prose_in_fence)

    @property
    def code_outside_fence_count(self) -> int:
        return len(self.code_outside_fence)

    @property
    def total_findings(self) -> int:
        return self.prose_in_fence_count + self.code_outside_fence_count

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "prose_in_fence_count": self.prose_in_fence_count,
            "code_outside_fence_count": self.code_outside_fence_count,
            "prose_in_fence": list(self.prose_in_fence),
            "code_outside_fence": list(self.code_outside_fence),
            "detail": self.detail,
        }


def _normalise(text: str) -> str:
    """Lower-cased alphanumeric words, space-joined. Ordering preserved."""
    return " ".join(w.lower() for w in _WORD_RE.findall(text))


def _parse_markdown_blocks(markdown: str) -> tuple[list[str], list[str]]:
    """Split candidate markdown into fenced-block lines and prose lines.

    Returns (fenced_lines, prose_lines) where each entry is the raw line text.
    Front matter, blank lines, and fence delimiters are excluded from both.
    """
    lines = markdown.split("\n")

    # Skip YAML front matter.
    if lines and _FRONT_MATTER_RE.match(lines[0]):
        try:
            end_idx = next(
                i for i in range(1, len(lines)) if _FRONT_MATTER_RE.match(lines[i])
            )
            lines = lines[end_idx + 1:]
        except StopIteration:
            pass

    fenced: list[str] = []
    prose: list[str] = []
    in_fence = False

    for line in lines:
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if in_fence:
            fenced.append(stripped)
        else:
            prose.append(stripped)

    return fenced, prose


def _build_mono_runs(lines: list[PdfLine]) -> list[list[PdfLine]]:
    """Group consecutive monospaced PDF lines into runs."""
    runs: list[list[PdfLine]] = []
    current: list[PdfLine] = []
    for ln in lines:
        if is_monospace_line(ln):
            current.append(ln)
        else:
            if current:
                runs.append(current)
                current = []
    if current:
        runs.append(current)
    return runs


def compare_code_fence_boundaries(
    source_path: Path,
    candidate_md: str,
) -> CodeFenceAlignment:
    """Compare the candidate's fence boundaries against the source PDF's fonts.

    Never raises: an unreadable or unsupported source abstains, because this
    is an advisory signal and a crash here must not take a scoring run down.
    """
    if source_path.suffix.lower() != ".pdf":
        return CodeFenceAlignment(
            status=STATUS_UNSUPPORTED,
            detail=f"{source_path.suffix or 'no'} source; PDF font geometry only",
        )
    try:
        lines = load_pdf_lines(source_path)
    except Exception:
        _log.debug(
            "code fence alignment: cannot read %s", source_path, exc_info=True
        )
        return CodeFenceAlignment(
            status=STATUS_ABSTAINED, detail="source unreadable"
        )

    if not any(is_monospace_line(ln) for ln in lines):
        return CodeFenceAlignment(
            status=STATUS_ABSTAINED,
            detail="no monospaced font detected in source",
        )

    # Build lookup sets from PDF lines.
    mono_norms: dict[str, PdfLine] = {}
    non_mono_norms: dict[str, PdfLine] = {}
    for ln in lines:
        norm = _normalise(ln.text)
        if not norm:
            continue
        if is_monospace_line(ln):
            mono_norms.setdefault(norm, ln)
        else:
            non_mono_norms.setdefault(norm, ln)

    fenced_lines, prose_lines = _parse_markdown_blocks(candidate_md)

    # Direction 1: fenced lines matching NON-mono PDF lines (prose in fence).
    # Only flag a line if it matches a non-mono line AND does NOT also match
    # a mono line (ambiguous lines are not findings).
    prose_in_fence: list[str] = []
    for fline in fenced_lines:
        fn = _normalise(fline)
        if not fn:
            continue
        if fn in non_mono_norms and fn not in mono_norms:
            prose_in_fence.append(fn)

    # Direction 2: monospaced runs of sufficient length whose text appears
    # outside any fence in the candidate.
    fenced_norms = {_normalise(fl) for fl in fenced_lines if _normalise(fl)}
    code_outside_fence: list[str] = []
    mono_runs = _build_mono_runs(lines)
    for run in mono_runs:
        if len(run) < C.CODE_RUN_MIN_LINES:
            continue
        unfenced = [
            _normalise(ln.text)
            for ln in run
            if _normalise(ln.text) and _normalise(ln.text) not in fenced_norms
        ]
        code_outside_fence.extend(unfenced)

    return CodeFenceAlignment(
        status=STATUS_CHECKED,
        prose_in_fence=tuple(prose_in_fence[:C.CODE_FENCE_EVIDENCE_CAP]),
        code_outside_fence=tuple(code_outside_fence[:C.CODE_FENCE_EVIDENCE_CAP]),
        detail=(
            f"checked {len(fenced_lines)} fenced, "
            f"{len(prose_lines)} prose lines against "
            f"{len(mono_norms)} mono, {len(non_mono_norms)} non-mono PDF lines"
        ),
    )
