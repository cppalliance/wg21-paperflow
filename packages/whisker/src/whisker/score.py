#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Per-paper QA verdict.

``score_paper`` fuses the reference-free signals available without ground
truth into a three-way verdict:

- structural gates (whisker.gates), every failure is hard,
- content coverage (unigram/token-set recall) / unigram drift / misaligned
  regions (tomd check_content; the order-sensitive shingle coverage and shingle
  drift are reported but do not gate), and
- the tomd structural QA score (tomd qa.compute_metrics).

TEDS/MHS are deliberately absent here: they require a labeled reference and
live in ``whisker bench``. This module returns data only; the CLI persists.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from paperstore.backend import StorageBackend
from tomd.lib.check_content import check_paper_content
from tomd.lib.pdf.qa import compute_metrics

from whisker import constants as C
from whisker.bench import table_score
from whisker.gates import GateResult, run_gates
from whisker.metrics import mhs, normalized_text, text_nid
from whisker.reference import reference_markdown

__all__ = [
    "VERDICT_FAIL",
    "VERDICT_PASS",
    "VERDICT_REVIEW",
    "WhiskerResult",
    "score_markdown",
    "score_paper",
    "sidecar_path",
    "whisker_output_dir",
]

VERDICT_PASS = "pass"
VERDICT_REVIEW = "review"
VERDICT_FAIL = "fail"


@dataclass
class WhiskerResult:
    pid: str
    source_format: str
    verdict: str
    coverage: float
    drift: float
    unigram_coverage: float
    unigram_drift: float
    missing_region_count: int
    extra_region_count: int
    qa_score: int
    uncertain_count: int
    mojibake_count: int
    table_parse_errors: int
    lossy_table_count: int
    gates: list[GateResult]
    hard_flags: list[str] = field(default_factory=list)
    soft_flags: list[str] = field(default_factory=list)
    # Reference-oracle agreement (tomd vs an independent converter), or None
    # when reference scoring is disabled (--no-reference). When present these
    # are the primary verdict signal; see _decide.
    ref_engine: str | None = None
    ref_nid: float | None = None
    ref_teds: float | None = None
    ref_mhs: float | None = None
    ref_overall: float | None = None
    schema_version: int = C.WHISKER_SCHEMA_VERSION

    def to_dict(self) -> dict:
        """Deterministic, JSON-serializable view (sorted unordered fields)."""
        def _r(v: float | None) -> float | None:
            return round(v, 4) if v is not None else None

        return {
            "schema_version": self.schema_version,
            "pid": self.pid,
            "source_format": self.source_format,
            "verdict": self.verdict,
            "coverage": round(self.coverage, 4),
            "drift": round(self.drift, 4),
            "unigram_coverage": round(self.unigram_coverage, 4),
            "unigram_drift": round(self.unigram_drift, 4),
            "missing_region_count": self.missing_region_count,
            "extra_region_count": self.extra_region_count,
            "qa_score": self.qa_score,
            "uncertain_count": self.uncertain_count,
            "mojibake_count": self.mojibake_count,
            "table_parse_errors": self.table_parse_errors,
            "lossy_table_count": self.lossy_table_count,
            "ref_engine": self.ref_engine,
            "ref_nid": _r(self.ref_nid),
            "ref_teds": _r(self.ref_teds),
            "ref_mhs": _r(self.ref_mhs),
            "ref_overall": _r(self.ref_overall),
            "gates": [asdict(g) for g in self.gates],
            "hard_flags": sorted(self.hard_flags),
            "soft_flags": sorted(self.soft_flags),
        }


def _decide(
    unigram_coverage: float,
    unigram_drift: float,
    missing_count: int,
    extra_count: int,
    qa_score: int,
    uncertain_count: int,
    gates: list[GateResult],
    ref: tuple[float, float, float, float] | None = None,
) -> tuple[str, list[str], list[str]]:
    """Return (verdict, hard_flags, soft_flags) from fused signals.

    The content hard-gate runs on ``unigram_coverage`` (order-invariant token-set
    recall), not on the order-sensitive shingle coverage. Structural gates and
    ``unigram_coverage < UNIGRAM_COVERAGE_FAIL_EDGE`` are the only HARD fails
    (broken artifact or genuinely missing words). A unigram coverage in the
    review band, ``unigram_drift`` (order-invariant precision complement),
    misaligned regions, qa and uncertain markers are soft (review). Both the
    shingle ``coverage`` and the order-sensitive shingle ``drift`` are
    reading-order proxies: reported elsewhere, never a verdict flag, because
    every benchmark repo keeps reading order off the content gate (see
    constants). The soft drift signal therefore tracks ``unigram_drift`` so a
    faithful reflow does not look like injected content.

    When ``ref`` (nid, teds, mhs, overall) is present, cross-converter TEXT
    agreement is layered on as an ADVISORY soft signal only: low ``ref_nid``
    adds a review flag but NEVER hard-fails (cross-converter agreement is a
    confidence signal, not ground truth: "agreement != correctness"). teds/mhs
    are reported per-axis but never flag, since against a weak oracle they carry
    no reliable signal.
    """
    hard: list[str] = []
    soft: list[str] = []

    for gate in gates:
        if not gate.passed:
            hard.append(f"gate:{gate.name}:{gate.detail or 'failed'}")

    if unigram_coverage < C.UNIGRAM_COVERAGE_FAIL_EDGE:
        hard.append(
            f"unigram coverage {unigram_coverage:.3f} < "
            f"{C.UNIGRAM_COVERAGE_FAIL_EDGE} (content missing)"
        )
    elif unigram_coverage < C.UNIGRAM_COVERAGE_REVIEW_EDGE:
        soft.append(f"unigram coverage {unigram_coverage:.3f} in review band")

    region_total = missing_count + extra_count
    if region_total >= C.REGION_SOFT_COUNT:
        soft.append(f"{region_total} misaligned region(s)")

    if unigram_drift > C.DRIFT_SOFT_EDGE:
        soft.append(f"unigram drift {unigram_drift:.3f} > {C.DRIFT_SOFT_EDGE}")
    if qa_score < C.QA_SCORE_SOFT_EDGE:
        soft.append(f"qa_score {qa_score} < {C.QA_SCORE_SOFT_EDGE}")
    if uncertain_count:
        soft.append(f"{uncertain_count} uncertain marker(s)")

    if ref is not None:
        ref_nid = ref[0]
        if ref_nid < C.REF_NID_ADVISORY_EDGE:
            soft.append(f"reference text agreement {ref_nid:.3f} low (advisory)")

    if hard:
        return VERDICT_FAIL, hard, soft
    if soft:
        return VERDICT_REVIEW, hard, soft
    return VERDICT_PASS, hard, soft


def score_markdown(
    pid: str,
    md_text: str,
    *,
    content,
    reference_md: str | None = None,
    ref_engine: str | None = None,
) -> WhiskerResult:
    """Build a verdict from already-loaded markdown and a content-check result.

    Split out from ``score_paper`` so tests can drive the verdict logic with a
    synthetic ``ContentCheckResult`` and no backend. When ``reference_md`` is
    given, tomd's markdown is scored against it (nid/teds/mhs via the bench
    metrics) and that agreement drives the verdict.
    """
    qa = compute_metrics(md_text, file=pid)
    gates = run_gates(md_text)

    ref: tuple[float, float, float, float] | None = None
    ref_nid = ref_teds = ref_mhs = ref_overall = None
    if reference_md is not None:
        # nid on content-normalized text (normalized_text folds inline LaTeX and
        # strips formatting so this measures content agreement, not tomd-style vs
        # oracle-style); teds/mhs on raw markdown, which need the table/heading
        # structure intact.
        ref_nid = text_nid(normalized_text(md_text), normalized_text(reference_md))
        ref_teds = table_score(md_text, reference_md)
        ref_mhs = mhs(md_text, reference_md)
        ref_overall = (ref_nid + ref_teds + ref_mhs) / 3.0
        ref = (ref_nid, ref_teds, ref_mhs, ref_overall)

    verdict, hard, soft = _decide(
        content.unigram_coverage,
        content.unigram_drift,
        len(content.missing_regions),
        len(content.extra_regions),
        qa.score,
        qa.uncertain_count,
        gates,
        ref=ref,
    )
    return WhiskerResult(
        pid=pid,
        source_format=content.source_format,
        verdict=verdict,
        coverage=content.coverage,
        drift=content.drift,
        unigram_coverage=content.unigram_coverage,
        unigram_drift=content.unigram_drift,
        missing_region_count=len(content.missing_regions),
        extra_region_count=len(content.extra_regions),
        qa_score=qa.score,
        uncertain_count=qa.uncertain_count,
        mojibake_count=qa.mojibake_count,
        table_parse_errors=qa.table_parse_errors,
        lossy_table_count=qa.lossy_table_count,
        ref_engine=ref_engine if reference_md is not None else None,
        ref_nid=ref_nid,
        ref_teds=ref_teds,
        ref_mhs=ref_mhs,
        ref_overall=ref_overall,
        gates=gates,
        hard_flags=hard,
        soft_flags=soft,
    )


def score_paper(
    pid: str,
    backend: StorageBackend,
    *,
    reference_engine: str | None = "markitdown",
) -> WhiskerResult:
    """Score one paper by id against its staged source and converted markdown.

    With ``reference_engine`` set (default ``markitdown``), an independent
    converter produces a reference markdown from the same source and tomd's
    output is scored against it. Pass ``reference_engine=None`` to skip the
    oracle and fall back to the structural/coverage signals only.

    Raises paperstore.MissingPaperMdError / MissingSourceError if the inputs
    are not present.
    """
    md_text = backend.get_paper_md(pid)
    content = check_paper_content(pid, backend)
    reference_md = None
    if reference_engine:
        reference_md = reference_markdown(pid, backend, engine=reference_engine)
    return score_markdown(
        pid, md_text, content=content,
        reference_md=reference_md, ref_engine=reference_engine,
    )


def whisker_output_dir(pid: str, backend: StorageBackend):
    """Return the directory where whisker artifacts for this store live.

    All whisker output (per-paper sidecars and the run report) is grouped under
    a single ``whisker/`` directory beside the markdown store, instead of
    scattering ``.whisker.json`` files among the converted papers.

    shortcut: this derives ``<root>/whisker`` from the canonical markdown path
    (``<root>/paperstore/<pid>.md``), since whisker is standalone and cannot add
    a path accessor to paperstore. Replace with a backend accessor if paperstore
    ever grows one. Local SqliteBackend layout only.
    """
    md_path = backend.get_paper_md_path(pid)
    return md_path.parent.parent / "whisker"


def sidecar_path(pid: str, backend: StorageBackend):
    """Derive the ``<pid>.whisker.json`` sidecar path in the whisker dir.

    Uses the canonical markdown path (no existence check) so the stem casing
    matches the store without touching paperstore internals.
    """
    md_path = backend.get_paper_md_path(pid)
    return whisker_output_dir(pid, backend) / (md_path.stem + ".whisker.json")
