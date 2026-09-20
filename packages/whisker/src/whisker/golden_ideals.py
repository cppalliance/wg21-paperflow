#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Golden ideals as ground truth for the deterministic lane.

The tomd golden-QA workflow (upstream PR #257) maintains hand-corrected
"ideal" markdown files under ``packages/tomd/tests/fixtures/golden/ideals/``:
one ``<pid>.md`` per blessed paper, human-verified against the source. Unlike
the markitdown oracle (an independent but WEAK converter, advisory only) an
ideal IS ground truth, so scoring tomd's live conversion against it gives the
deterministic lane a Lane-2-quality fidelity signal per paper, with zero
configuration: any new ideal that lands in the directory is picked up on the
next run.

Boundary note: whisker only READS the ideal files from tomd's fixture tree
(read-only file access, no tomd-private imports), which keeps the
package-boundary rule intact. The metrics are the existing whisker Lane-2
axes; nothing new is computed here.

Verdict policy: ideal agreement stays ADVISORY (a review flag at most, never a
hard fail). The calibrated hard gate (structural gates + unigram coverage) is
untouched; wiring ideals into the hard gate would change the verdict model and
needs its own calibration and sign-off.

Availability audit (M1): a paper's ``ideal_*`` fields all read ``None`` for two
structurally different reasons that an installed sidecar cannot otherwise tell
apart: the ideals checkout is not reachable at all (an installed wheel with no
workspace checkout on disk), or the checkout IS reachable but this particular
paper simply has no ideal yet. ``IDEAL_STATUS_UNAVAILABLE`` /
``IDEAL_STATUS_ABSENT`` / ``IDEAL_STATUS_PRESENT`` (``resolve_ideal``) make that
distinction explicit instead of collapsing both into an indistinguishable null.

Pure functions; the module never writes. Callers persist.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from whisker.det.bench import _block_agreement, _structural_parity, table_score
from whisker.metrics import (
    content_recall,
    has_headings,
    heading_level_parity,
    mhs,
    normalized_text,
    text_nid,
)
from whisker.tables import parse_html_tables, parse_pipe_tables

__all__ = [
    "IDEAL_STATUS_ABSENT",
    "IDEAL_STATUS_PRESENT",
    "IDEAL_STATUS_UNAVAILABLE",
    "IdealPanel",
    "find_ideals_dir",
    "ideal_path",
    "list_ideal_stems",
    "resolve_ideal",
    "score_against_ideal",
]

# Repo-relative location of the tomd golden ideals, discovered by walking up
# from this file (and, as a fallback, from the cwd) to the workspace root.
_IDEALS_RELPATH = Path("packages") / "tomd" / "tests" / "fixtures" / "golden" / "ideals"

# -- Ideal-lane availability status (M1 audit) --------------------------------
# All three collapse to ideal_*: None on WhiskerResult, but they mean different
# things to a human or CI job reading the sidecar: UNAVAILABLE says "look
# elsewhere for this signal, this environment cannot see any ideals";
# IDEAL_STATUS_ABSENT says "the signal exists here, this paper just has none
# yet"; IDEAL_STATUS_PRESENT says the panel below is populated ground truth.
IDEAL_STATUS_UNAVAILABLE = "unavailable"
IDEAL_STATUS_ABSENT = "absent"
IDEAL_STATUS_PRESENT = "present"


@dataclass(frozen=True)
class IdealPanel:
    """Fidelity of a candidate markdown against a human-blessed ideal.

    All axes are the existing Lane-2 metrics. ``teds``/``mhs`` are ``None``
    when the ideal lacks that modality (no tables / no headings): the axis is
    ineligible, not a synthetic perfect score (bench null-eligibility rule,
    schema v3 lesson). ``overall`` is the mean of the ELIGIBLE structural axes
    only. ``recall`` is reported separately (strata stay separate, never
    folded into overall).
    """

    nid: float
    teds: float | None
    mhs: float | None
    recall: float
    overall: float
    block_agreement: float | None = None
    structural_parity: float | None = None
    heading_level_parity: float | None = None


def find_ideals_dir(start: Path | None = None) -> Path | None:
    """Locate the golden ideals directory by walking up to the repo root.

    Checks the parents of this source file first (whisker always lives inside
    the workspace checkout), then the parents of ``start`` (default: cwd) for
    editable installs running elsewhere. Returns None when the directory does
    not exist, which callers treat as "no ideals available" and skip silently.
    """
    roots: list[Path] = []
    here = Path(__file__).resolve()
    roots.extend(here.parents)
    origin = (start or Path.cwd()).resolve()
    roots.append(origin)
    roots.extend(origin.parents)
    for root in roots:
        candidate = root / _IDEALS_RELPATH
        if candidate.is_dir():
            return candidate
    return None


def ideal_path(pid: str, ideals_dir: Path) -> Path | None:
    """Resolve the ideal file for a pid, matching the stem case-insensitively.

    The workflow names ideals lowercase (``p4182r0.md``) while whisker pids
    are uppercase; a literal lowercase lookup would silently skip an ideal
    whose file happens to carry different casing on a case-sensitive
    filesystem. Scanning the directory keeps the lookup exact on every OS.
    """
    wanted = pid.strip().lower()
    for candidate in ideals_dir.glob("*.md"):
        if candidate.stem.lower() == wanted and candidate.is_file():
            return candidate
    return None


def list_ideal_stems(ideals_dir: Path) -> list[str]:
    """Sorted lowercase stems of every ideal in the directory."""
    return sorted(p.stem.lower() for p in ideals_dir.glob("*.md"))


def resolve_ideal(pid: str, ideals_dir: Path | None) -> tuple[str | None, str]:
    """Resolve the ideal markdown (if any) for a pid, with an explicit status.

    ``ideals_dir`` is the directory already resolved by the caller (``None``
    when discovery found nothing, e.g. an installed wheel with no workspace
    checkout on disk). Returns ``(ideal_md, status)``:

    - ``ideals_dir`` is ``None`` -> ``(None, IDEAL_STATUS_UNAVAILABLE)``: the
      ideals lane cannot be evaluated at all in this environment.
    - ``ideals_dir`` exists but has no file for ``pid`` ->
      ``(None, IDEAL_STATUS_ABSENT)``: the lane works here, this paper has no
      ideal yet.
    - a matching file exists -> ``(file text, IDEAL_STATUS_PRESENT)``.
    """
    if ideals_dir is None:
        return None, IDEAL_STATUS_UNAVAILABLE
    found = ideal_path(pid, ideals_dir)
    if found is None:
        return None, IDEAL_STATUS_ABSENT
    return found.read_text(encoding="utf-8"), IDEAL_STATUS_PRESENT


def score_against_ideal(md_text: str, ideal_md: str) -> IdealPanel:
    """Score a candidate markdown against its ideal on the Lane-2 axes.

    Same metric surfaces as the oracle path in ``score.score_markdown``: nid
    on content-normalized text, teds/mhs on raw markdown (they need table and
    heading structure intact), plus multiset content recall of the ideal in
    the candidate (catches dropped sections that edit distance hides).

    Null-eligibility follows bench, not the oracle path: an ideal is
    well-formed labeled ground truth, so a modality it lacks yields ``None``
    (excluded from ``overall``) instead of a synthetic 1.0 that would inflate
    the composite of table-less / heading-less papers.

    nid is the WHOLE-DOCUMENT ``text_nid``, not bench's block-matched variant:
    an ideal is a hand-corrected version of the same conversion, so reading
    order matches by construction and the reorder-robustness of block matching
    buys nothing here (while its adjacency-merge pitfalls against odd blocking
    cost real under-scoring, see score.py's oracle rationale). Against the
    NID_FLOOR this is the conservative choice: whole-document nid can only be
    <= the block-matched score.
    """
    nid = text_nid(normalized_text(md_text), normalized_text(ideal_md))
    has_tables = bool(parse_pipe_tables(ideal_md) or parse_html_tables(ideal_md))
    teds = table_score(md_text, ideal_md) if has_tables else None
    heading_sim = mhs(md_text, ideal_md) if has_headings(ideal_md) else None
    recall = content_recall(md_text, ideal_md)
    ba = _block_agreement(md_text, ideal_md)
    sp = _structural_parity(md_text, ideal_md)
    hlp = heading_level_parity(md_text, ideal_md)
    parts = [nid]
    if teds is not None:
        parts.append(teds)
    if heading_sim is not None:
        parts.append(heading_sim)
    overall = sum(parts) / len(parts)
    return IdealPanel(
        nid=nid, teds=teds, mhs=heading_sim, recall=recall, overall=overall,
        block_agreement=ba, structural_parity=sp, heading_level_parity=hlp,
    )
