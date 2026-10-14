#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Stratified sampling + blind worksheet generation for calibration labeling.

whisker's coverage band edges (``UNIGRAM_COVERAGE_FAIL_EDGE`` /
``UNIGRAM_COVERAGE_REVIEW_EDGE``, see ``constants.py``) are fitted from human
labels by ``calibrate.py``. Today only 9 labels exist
(``corpus/dev-replay/labels.json``), overwhelmingly one class. This module
gives a future labeling effort two pure, I/O-free building blocks:

1. ``sample_calibration_candidates`` — pick a deterministic, stratified
   sample of papers to hand-label, instead of a human manually browsing
   hundreds of scored papers.
2. ``build_blind_worksheet`` — render that sample as a worksheet a human can
   judge WITHOUT seeing whisker's own computed verdict or
   ``unigram_coverage`` score. Showing either would make the eventual
   calibration circular: fitting a threshold to reproduce the very score
   that threshold is supposed to independently validate.

Neither function does I/O; both take already-loaded data and return plain
data (dataclasses / dicts), matching the "library returns data" convention
used across whisker. This module is intentionally standalone: it is not
wired into the ``whisker`` CLI or ``calibrate.py`` in this pass, and imports
nothing from either.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

__all__ = [
    "BandDraw",
    "SamplingResult",
    "ScoredPaper",
    "build_blind_worksheet",
    "sample_calibration_candidates",
]

Verdict = Literal["pass", "review", "fail"]

# Fixed processing order for the three verdict bands. One `random.Random`
# instance is walked across the bands in this order, so the result depends
# only on `seed` and the input list, never on incidental call order.
_BAND_ORDER: tuple[Verdict, ...] = ("pass", "review", "fail")

# Fields from ScoredPaper that must NEVER appear in a blind worksheet entry.
# Enforced by assertion in build_blind_worksheet, not just by field
# selection, so a future edit that copies fields wholesale cannot silently
# reintroduce the leak.
_LEAKED_FIELDS = ("verdict", "unigram_coverage")


@dataclass(frozen=True)
class ScoredPaper:
    """One paper's whisker verdict + score, as fed into the sampler.

    ``verdict`` mirrors whisker's own trichotomy (``whisker.det.score``
    ``VERDICT_PASS``/``VERDICT_REVIEW``/``VERDICT_FAIL``); this module does
    not import ``whisker.det.score`` to stay standalone, so callers translate
    their own ``WhiskerResult.verdict`` into this shape.
    """

    pid: str
    verdict: Verdict
    unigram_coverage: float


@dataclass(frozen=True)
class BandDraw:
    """Requested vs. actually-drawn accounting for one verdict band."""

    verdict: Verdict
    available: int
    requested: int
    drawn: int

    @property
    def shortfall(self) -> int:
        """How many fewer candidates were drawn than requested (>= 0)."""
        return self.requested - self.drawn


@dataclass(frozen=True)
class SamplingResult:
    """Output of ``sample_calibration_candidates``.

    ``candidates`` is band-ordered (pass, then review, then fail) and
    shuffle-ordered within each band; it is not interleaved across bands.
    ``bands`` reports the per-band requested/available/drawn counts so a
    shortfall is visible without recomputing it from ``candidates``.
    """

    candidates: list[ScoredPaper]
    bands: list[BandDraw]


def sample_calibration_candidates(
    scored_papers: Sequence[ScoredPaper],
    *,
    n_per_band: int,
    seed: int,
) -> SamplingResult:
    """Stratified, deterministic sample of papers to hand-label for calibration.

    Splits ``scored_papers`` into three disjoint bands by ``verdict``
    (pass/review/fail; disjoint because a paper has exactly one verdict),
    deterministically shuffles each band with a locally seeded
    ``random.Random(seed)`` instance (never the global ``random`` module, so
    the result cannot be perturbed by unrelated code elsewhere in the
    process calling ``random.seed``/``random.shuffle``), and takes up to
    ``n_per_band`` from each band. A band with fewer than ``n_per_band``
    candidates yields all of it; this is reported via ``SamplingResult.bands``,
    never an error.

    Determinism contract: for a fixed ``seed`` and a fixed input list (any
    order, since shuffling starts from a stable per-band partition of the
    input), the returned ``candidates`` list — including exact order — is
    identical on every call, regardless of process state or call order.

    Raises ``ValueError`` if ``n_per_band`` is negative or if any paper's
    ``verdict`` is outside ``{"pass", "review", "fail"}``.
    """
    if n_per_band < 0:
        raise ValueError(f"n_per_band must be >= 0, got {n_per_band}")

    by_band: dict[Verdict, list[ScoredPaper]] = {verdict: [] for verdict in _BAND_ORDER}
    for paper in scored_papers:
        if paper.verdict not in by_band:
            raise ValueError(
                f"unknown verdict {paper.verdict!r} for pid {paper.pid!r}; "
                f"expected one of {_BAND_ORDER}"
            )
        by_band[paper.verdict].append(paper)

    rng = random.Random(seed)
    candidates: list[ScoredPaper] = []
    bands: list[BandDraw] = []
    seen_pids: set[str] = set()

    for verdict in _BAND_ORDER:
        band = list(by_band[verdict])
        rng.shuffle(band)
        drawn = band[:n_per_band]

        for paper in drawn:
            assert paper.pid not in seen_pids, (
                f"pid {paper.pid!r} sampled twice across bands; verdict "
                "bands must be disjoint by construction"
            )
            seen_pids.add(paper.pid)

        candidates.extend(drawn)
        bands.append(
            BandDraw(
                verdict=verdict,
                available=len(band),
                requested=n_per_band,
                drawn=len(drawn),
            )
        )

    return SamplingResult(candidates=candidates, bands=bands)


def build_blind_worksheet(
    candidates: Sequence[ScoredPaper],
    markdown_lookup: Mapping[str, str],
) -> list[dict]:
    """One blind labeling entry per candidate, judgment fields blank.

    The entry shape mirrors the dev-replay label schema's input side
    (``pid``, ``pr``, ``source_type``, ``markdown``) plus the judgment
    fields a human fills in (``human_verdict``, ``label``,
    ``defect_groups``, ``split``), all blank/empty so labeling starts from a
    clean slate.

    Hard invariant: the returned dicts NEVER carry ``verdict`` or
    ``unigram_coverage`` from the input ``ScoredPaper``. Leaking either would
    let a labeler see whisker's own computed signal before judging, which
    makes any threshold later fitted on these labels circular (fitting a
    threshold to reproduce the score it is supposed to independently
    validate). This is asserted per entry, not just implied by writing an
    explicit field list, so a future edit that copies fields wholesale
    (e.g. ``{**vars(paper), ...}``) cannot silently reintroduce the leak.

    Raises ``KeyError`` if a candidate's ``pid`` is missing from
    ``markdown_lookup``.
    """
    worksheet: list[dict] = []
    for paper in candidates:
        entry = {
            "pid": paper.pid,
            "pr": None,
            "source_type": None,
            "markdown": markdown_lookup[paper.pid],
            "human_verdict": None,
            "label": None,
            "defect_groups": [],
            "split": None,
        }
        for leaked_field in _LEAKED_FIELDS:
            assert leaked_field not in entry, (
                f"blind worksheet entry for {paper.pid!r} leaked {leaked_field!r}"
            )
        worksheet.append(entry)
    return worksheet
