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

TEDS/MHS require a labeled reference and normally live in ``whisker bench``;
the one exception is a paper with a golden ideal (human-blessed ground truth
from the tomd golden-QA fixtures, auto-discovered per pid), which gets the
full Lane-2 ideal panel as an additional advisory signal. This module returns
data only; the CLI persists.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

import fitz
from bs4 import BeautifulSoup
from paperstore.backend import StorageBackend
from tomd.lib.check_content import check_paper_content
from tomd.lib.pdf.qa import compute_metrics

from whisker import constants as C
from whisker.det.bench import table_score
from whisker.det.code_fence_align import (
    CodeFenceAlignment,
    compare_code_fence_boundaries,
)
from whisker.det.golden_compare import StructuralScore
from whisker.det.golden_compare import compare as golden_compare
from whisker.det.llm_readability.validate import table_units_from_markdown
from whisker.det.match import block_metrics
from whisker.det.paragraph_align import ParagraphAlignment, compare_paragraph_boundaries
from whisker.det.reference import reference_markdown
from whisker.gates import GateResult, run_gates
from whisker.golden_ideals import (
    IDEAL_STATUS_PRESENT,
    IDEAL_STATUS_UNAVAILABLE,
    IdealPanel,
    find_ideals_dir,
    resolve_ideal,
    score_against_ideal,
)
from whisker.metrics import mhs, normalized_text, punct_content_recall, text_nid

_log = logging.getLogger(__name__)

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
VERDICT_FAIL = "not-llm-readable"


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
    # Report-only R2 defect flags surfaced from the table-readability punch-list
    # (validate.py helpers). These do NOT gate the verdict; they inform the
    # reviewer and the LLM lane. Empty when no table flags fire.
    table_readability_flags: list[str] = field(default_factory=list)
    hard_flags: list[str] = field(default_factory=list)
    soft_flags: list[str] = field(default_factory=list)
    missing_regions: list[dict] = field(default_factory=list)
    extra_regions: list[dict] = field(default_factory=list)
    # Reference-oracle agreement (tomd vs an independent converter), or None
    # when reference scoring is disabled (--no-reference). When present these
    # are the primary verdict signal; see _decide.
    ref_engine: str | None = None
    ref_nid: float | None = None
    ref_teds: float | None = None
    ref_mhs: float | None = None
    ref_overall: float | None = None
    # Block-matched reading-order disagreement vs the reference (0 = same
    # order, 1 = fully reordered). None when reference scoring is disabled.
    ref_reading_order: float | None = None
    # Punctuation-preserving token recall of source content in candidate.
    # Divergence from unigram_coverage (alphanumeric) isolates operator
    # corruption invisible to the clean_string normalizer. None when no
    # source text was provided.
    punct_recall: float | None = None
    # Source-vs-candidate paragraph-boundary agreement (PDF geometry). None
    # when no source was provided; status "abstained"/"unsupported" when the
    # source carries no detectable paragraph convention. Advisory.
    paragraph_status: str | None = None
    paragraph_convention: str | None = None
    paragraph_merged_count: int | None = None
    # Source-vs-candidate code-fence boundary agreement (PDF font geometry).
    # None when no source was provided; status "abstained"/"unsupported" when
    # the source has no monospaced fonts or is not a PDF. Advisory.
    fence_status: str | None = None
    fence_prose_in_fence_count: int | None = None
    fence_code_outside_fence_count: int | None = None
    # Golden-ideal agreement (tomd vs a human-blessed ideal from the tomd
    # golden-QA fixtures), or None when the paper has no ideal. Ground truth,
    # but still advisory in the verdict (see constants).
    # ``ideal_status`` disambiguates WHY the ideal_* axes below are None: an
    # unreachable ideals checkout (IDEAL_STATUS_UNAVAILABLE) vs a reachable
    # checkout with no ideal for this pid (IDEAL_STATUS_ABSENT) vs a scored
    # ideal (IDEAL_STATUS_PRESENT). See golden_ideals.resolve_ideal.
    ideal_status: str | None = None
    ideal_nid: float | None = None
    ideal_teds: float | None = None
    ideal_mhs: float | None = None
    ideal_recall: float | None = None
    ideal_overall: float | None = None
    ideal_block_agreement: float | None = None
    ideal_structural_parity: float | None = None
    ideal_heading_level_parity: float | None = None
    # Per-axis structural breakdown from golden_compare (Sean's deterministic
    # comparator). Present only when the paper has a golden ideal. Each axis
    # is a 0-1 score; gc_composite is the weighted average over present axes.
    gc_composite: float | None = None
    gc_frontmatter: float | None = None
    gc_heading: float | None = None
    gc_heading_text: float | None = None
    gc_heading_level: float | None = None
    gc_heading_nesting: float | None = None
    gc_list: float | None = None
    gc_code: float | None = None
    gc_table: float | None = None
    gc_text: float | None = None
    gc_worst_axis: str | None = None
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
            "ref_reading_order": _r(self.ref_reading_order),
            "punct_recall": _r(self.punct_recall),
            "paragraph_status": self.paragraph_status,
            "paragraph_convention": self.paragraph_convention,
            "paragraph_merged_count": self.paragraph_merged_count,
            "fence_status": self.fence_status,
            "fence_prose_in_fence_count": self.fence_prose_in_fence_count,
            "fence_code_outside_fence_count": self.fence_code_outside_fence_count,
            "ideal_status": self.ideal_status,
            "ideal_nid": _r(self.ideal_nid),
            "ideal_teds": _r(self.ideal_teds),
            "ideal_mhs": _r(self.ideal_mhs),
            "ideal_recall": _r(self.ideal_recall),
            "ideal_overall": _r(self.ideal_overall),
            "ideal_block_agreement": _r(self.ideal_block_agreement),
            "ideal_structural_parity": _r(self.ideal_structural_parity),
            "ideal_heading_level_parity": _r(self.ideal_heading_level_parity),
            "gc_composite": _r(self.gc_composite),
            "gc_frontmatter": _r(self.gc_frontmatter),
            "gc_heading": _r(self.gc_heading),
            "gc_heading_text": _r(self.gc_heading_text),
            "gc_heading_level": _r(self.gc_heading_level),
            "gc_heading_nesting": _r(self.gc_heading_nesting),
            "gc_list": _r(self.gc_list),
            "gc_code": _r(self.gc_code),
            "gc_table": _r(self.gc_table),
            "gc_text": _r(self.gc_text),
            "gc_worst_axis": self.gc_worst_axis,
            "gates": [asdict(g) for g in self.gates],
            "table_readability_flags": sorted(self.table_readability_flags),
            "hard_flags": sorted(self.hard_flags),
            "soft_flags": sorted(self.soft_flags),
            "missing_regions": self.missing_regions,
            "extra_regions": self.extra_regions,
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
    ideal: IdealPanel | None = None,
    reading_order: float | None = None,
    punct_recall: float | None = None,
    paragraph: ParagraphAlignment | None = None,
    fence: CodeFenceAlignment | None = None,
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

    When ``reading_order`` (block-matched reading-order NED vs the reference) is
    present and exceeds ``READING_ORDER_SOFT_EDGE``, an advisory soft flag is
    raised. Reading order never gates content (OmniDocBench, Docling, DP-Bench
    precedent).

    When ``punct_recall`` (punctuation-preserving token recall against the
    source) is present and diverges from ``unigram_coverage`` by more than
    ``PUNCT_RECALL_DIVERGENCE_SOFT_EDGE``, an advisory soft flag is raised.
    The divergence isolates operator corruption that the alphanumeric tokenizer
    is blind to (E28).

    When ``paragraph`` reports swallowed source paragraph breaks, an advisory
    soft flag is raised. The defect is token-preserving, so no other signal in
    this function can see it. It stays soft: tomd flattens paragraph structure
    by design today, and hard-gating a structural axis over-failed twice before
    (``ref_nid``, shingle ``coverage``; see constants).

    When ``fence`` reports code-fence boundary mismatches (prose swallowed into
    a fence, or code left outside a fence), an advisory soft flag is raised.
    Like paragraph boundaries, fence boundaries are token-preserving, so no
    other signal in this function can see them. Soft only for the same reason.

    When ``ideal`` is present the paper has a human-blessed golden ideal, which
    IS ground truth, so every Lane-2 axis flags against its bench floor. The
    flags are still ADVISORY (review, never hard fail): the calibrated hard
    gate stays untouched until the ideal corpus is large enough to calibrate
    its own operating point (see constants).
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

    if reading_order is not None and reading_order > C.READING_ORDER_SOFT_EDGE:
        soft.append(
            f"reading order disagreement {reading_order:.3f} > "
            f"{C.READING_ORDER_SOFT_EDGE} (advisory)"
        )

    if punct_recall is not None:
        divergence = unigram_coverage - punct_recall
        if divergence > C.PUNCT_RECALL_DIVERGENCE_SOFT_EDGE:
            soft.append(
                f"punctuation recall {punct_recall:.3f} diverges from "
                f"unigram {unigram_coverage:.3f} by {divergence:.3f} (advisory)"
            )

    if (paragraph is not None
            and paragraph.merged_count >= C.PARAGRAPH_MERGE_SOFT_COUNT):
        soft.append(
            f"{paragraph.merged_count} source paragraph break(s) missing from "
            f"the candidate (advisory)"
        )

    if (fence is not None
            and fence.total_findings >= C.CODE_FENCE_SOFT_COUNT):
        parts: list[str] = []
        if fence.prose_in_fence_count:
            parts.append(f"{fence.prose_in_fence_count} prose line(s) inside fence")
        if fence.code_outside_fence_count:
            parts.append(
                f"{fence.code_outside_fence_count} code line(s) outside fence"
            )
        soft.append(f"code fence boundary mismatch: {', '.join(parts)} (advisory)")

    if ideal is not None:
        # teds/mhs are None when the ideal lacks the modality (null-eligibility):
        # an ineligible axis cannot flag.
        for value, floor, axis in (
            (ideal.nid, C.NID_FLOOR, "nid"),
            (ideal.teds, C.TEDS_FLOOR, "teds"),
            (ideal.mhs, C.MHS_FLOOR, "mhs"),
            (ideal.recall, C.CONTENT_RECALL_FLOOR, "recall"),
        ):
            if value is not None and value < floor:
                soft.append(f"ideal {axis} {value:.3f} < {floor} (advisory)")
        if (ideal.structural_parity is not None
                and ideal.structural_parity < 1.0):
            soft.append(
                f"ideal structural_parity {ideal.structural_parity:.3f} "
                f"< 1.0 (advisory)"
            )
        if (ideal.heading_level_parity is not None
                and ideal.heading_level_parity < 1.0):
            soft.append(
                f"ideal heading_level_parity "
                f"{ideal.heading_level_parity:.3f} < 1.0 (advisory)"
            )

    if hard:
        return VERDICT_FAIL, hard, soft

    # Benign-region fold: when the ONLY soft flags are misaligned region(s) and
    # unigram coverage confirms the content is complete (>= 0.95), the paper
    # passes. tomd deliberately strips page furniture, so region mismatches on
    # high-coverage papers are expected, not defects. The region flag stays
    # visible (annotated "(benign)") for auditability.
    if soft and _is_benign_region_only(soft, unigram_coverage):
        benign_soft = [f"{f} (benign)" for f in soft]
        return VERDICT_PASS, hard, benign_soft

    if soft:
        return VERDICT_REVIEW, hard, soft
    return VERDICT_PASS, hard, soft


_REGION_FLAG_SUFFIX = "misaligned region(s)"


def _is_benign_region_only(soft: list[str], unigram_coverage: float) -> bool:
    """True when all soft flags are region flags and coverage is high enough."""
    if unigram_coverage < C.REGION_BENIGN_UNIGRAM_FLOOR:
        return False
    return all(f.endswith(_REGION_FLAG_SUFFIX) for f in soft)


def score_markdown(
    pid: str,
    md_text: str,
    *,
    content,
    reference_md: str | None = None,
    ref_engine: str | None = None,
    ideal_md: str | None = None,
    ideal_status: str | None = None,
    source_text: str | None = None,
    paragraph: ParagraphAlignment | None = None,
    fence: CodeFenceAlignment | None = None,
) -> WhiskerResult:
    """Build a verdict from already-loaded markdown and a content-check result.

    Split out from ``score_paper`` so tests can drive the verdict logic with a
    synthetic ``ContentCheckResult`` and no backend. When ``reference_md`` is
    given, tomd's markdown is scored against it (nid/teds/mhs via the bench
    metrics) and that agreement drives the verdict. When ``ideal_md`` is given
    (a human-blessed golden ideal), the ideal panel is computed and layered on
    as an additional advisory signal. ``ideal_status`` records WHY the ideal
    axes are populated or not (see golden_ideals.resolve_ideal); when omitted
    it defaults to IDEAL_STATUS_PRESENT if ``ideal_md`` was given, else
    IDEAL_STATUS_UNAVAILABLE (this backend-free core has no way to tell
    "unreachable" from "reachable but absent" on its own; score_paper passes
    the resolved status explicitly).

    When ``source_text`` is given, a punctuation-preserving token recall is
    computed between the candidate and the source (the only ground truth for
    operator-level fidelity). The divergence from the alphanumeric
    ``unigram_coverage`` isolates punctuation-only corruption.

    ``paragraph`` is a precomputed source-vs-candidate paragraph-boundary
    comparison (``whisker.det.paragraph_align``). Like ``content`` it is passed in
    rather than derived, so this core stays backend- and filesystem-free.

    ``fence`` is a precomputed source-vs-candidate code-fence boundary
    comparison (``whisker.det.code_fence_align``). Same pass-in pattern.
    """
    qa = compute_metrics(md_text, file=pid)
    gates = run_gates(md_text)

    ref: tuple[float, float, float, float] | None = None
    ref_nid = ref_teds = ref_mhs = ref_overall = None
    reading_order: float | None = None
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

        bm = block_metrics(md_text, reference_md)
        reading_order = bm.reading_order

    punct_recall_val: float | None = None
    if source_text is not None:
        punct_recall_val = punct_content_recall(md_text, source_text)

    ideal: IdealPanel | None = None
    gc: StructuralScore | None = None
    if ideal_md is not None:
        ideal = score_against_ideal(md_text, ideal_md)
        gc = golden_compare(md_text, ideal_md)
    if ideal_status is None:
        ideal_status = IDEAL_STATUS_PRESENT if ideal_md is not None else IDEAL_STATUS_UNAVAILABLE

    def _region_dicts(regions) -> list[dict]:
        ordered = sorted(regions, key=lambda r: r.token_start)
        return [
            {"page": r.page, "token_start": r.token_start,
             "token_end": r.token_end, "sample": r.sample}
            for r in ordered[:C.REGION_DETAIL_CAP]
        ]

    verdict, hard, soft = _decide(
        content.unigram_coverage,
        content.unigram_drift,
        len(content.missing_regions),
        len(content.extra_regions),
        qa.score,
        qa.uncertain_count,
        gates,
        ref=ref,
        ideal=ideal,
        reading_order=reading_order,
        punct_recall=punct_recall_val,
        paragraph=paragraph,
        fence=fence,
    )
    table_flags: list[str] = []
    _FLAG_ATTRS = (
        "truncated_leak", "trailing_row_leak", "row_merge",
        "absorbed_prose_row", "flattened_prose", "header_is_data",
        "wrap_bleed", "data_as_header", "wrap_orphan", "hyphen_glue",
        "wording_clause",
    )
    for unit in table_units_from_markdown(md_text):
        for attr in _FLAG_ATTRS:
            if getattr(unit, attr, False):
                label = f"{attr}@T{unit.index + 1}"
                if label not in table_flags:
                    table_flags.append(label)
    table_flags.sort()

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
        ref_reading_order=reading_order,
        punct_recall=punct_recall_val,
        paragraph_status=paragraph.status if paragraph else None,
        paragraph_convention=paragraph.convention if paragraph else None,
        paragraph_merged_count=paragraph.merged_count if paragraph else None,
        fence_status=fence.status if fence else None,
        fence_prose_in_fence_count=fence.prose_in_fence_count if fence else None,
        fence_code_outside_fence_count=fence.code_outside_fence_count if fence else None,
        ideal_status=ideal_status,
        ideal_nid=ideal.nid if ideal else None,
        ideal_teds=ideal.teds if ideal else None,
        ideal_mhs=ideal.mhs if ideal else None,
        ideal_recall=ideal.recall if ideal else None,
        ideal_overall=ideal.overall if ideal else None,
        ideal_block_agreement=ideal.block_agreement if ideal else None,
        ideal_structural_parity=ideal.structural_parity if ideal else None,
        ideal_heading_level_parity=ideal.heading_level_parity if ideal else None,
        gc_composite=gc.composite if gc else None,
        gc_frontmatter=gc.axes["frontmatter"].score if gc else None,
        gc_heading=gc.axes["heading"].score if gc else None,
        gc_heading_text=gc.axes["heading"].sub.get("text") if gc else None,
        gc_heading_level=gc.axes["heading"].sub.get("level") if gc else None,
        gc_heading_nesting=gc.axes["heading"].sub.get("nesting") if gc else None,
        gc_list=gc.axes["list"].score if gc else None,
        gc_code=gc.axes["code"].score if gc else None,
        gc_table=gc.axes["table"].score if gc else None,
        gc_text=gc.axes["text"].score if gc else None,
        gc_worst_axis=gc.worst_present_axis if gc else None,
        gates=gates,
        table_readability_flags=table_flags,
        hard_flags=hard,
        soft_flags=soft,
        missing_regions=_region_dicts(content.missing_regions),
        extra_regions=_region_dicts(content.extra_regions),
    )


def _extract_source_text(source_path: Path) -> str | None:
    """Lightweight plain-text extraction from a PDF or HTML source.

    Used for the punctuation-preserving token recall. Simpler than
    ``check_content``'s extraction (no page-number stripping, no shingle
    tokenization); the token-level comparison is forgiving of repeating
    headers.
    """
    suffix = source_path.suffix.lower()
    try:
        if suffix == ".pdf":
            doc = fitz.open(str(source_path))
            try:
                return "\n".join(doc[i].get_text() for i in range(doc.page_count))
            finally:
                doc.close()
        if suffix in (".html", ".htm"):
            html = source_path.read_text(encoding="utf-8", errors="replace")
            return BeautifulSoup(html, "html.parser").get_text(separator=" ")
    except Exception:
        _log.debug("source text extraction failed for %s", source_path, exc_info=True)
    return None


def score_paper(
    pid: str,
    backend: StorageBackend,
    *,
    reference_engine: str | None = "markitdown",
    ideals_dir: Path | None = None,
) -> WhiskerResult:
    """Score one paper by id against its staged source and converted markdown.

    With ``reference_engine`` set (default ``markitdown``), an independent
    converter produces a reference markdown from the same source and tomd's
    output is scored against it. Pass ``reference_engine=None`` to skip the
    oracle and fall back to the structural/coverage signals only.

    Golden ideals are auto-discovered: when the tomd golden-QA fixtures carry
    an ideal for this pid, the ideal panel is computed and added as an
    advisory signal, with no configuration. Pass ``ideals_dir`` (a Path) to
    override the discovered directory, e.g. in tests.

    Raises paperstore.MissingPaperMdError / MissingSourceError if the inputs
    are not present.
    """
    md_text = backend.get_paper_md(pid)
    content = check_paper_content(pid, backend)
    reference_md = None
    if reference_engine:
        reference_md = reference_markdown(pid, backend, engine=reference_engine)
    resolved_ideals = ideals_dir if ideals_dir is not None else find_ideals_dir()
    ideal_md, ideal_status = resolve_ideal(pid, resolved_ideals)
    source_path = backend.get_source_path(pid)
    source_text = _extract_source_text(source_path)
    paragraph = compare_paragraph_boundaries(source_path, md_text)
    fence = compare_code_fence_boundaries(source_path, md_text)
    return score_markdown(
        pid, md_text, content=content,
        reference_md=reference_md, ref_engine=reference_engine,
        ideal_md=ideal_md, ideal_status=ideal_status,
        source_text=source_text,
        paragraph=paragraph,
        fence=fence,
    )


def whisker_output_dir(pid: str, backend: StorageBackend):
    """Return the directory where deterministic whisker artifacts live.

    All deterministic output (per-paper sidecars and the run report) is grouped
    under ``whisker/det/`` beside the markdown store. The advisory LLM lane
    keeps its artifacts in the sibling ``whisker/llm/`` (owned by tapetum_llm,
    never written by this module), so the two lanes are separated on disk.

    shortcut: this derives ``<root>/whisker/det`` from the canonical markdown
    path (``<root>/paperstore/<pid>.md``), since whisker is standalone and
    cannot add a path accessor to paperstore. Replace with a backend accessor
    if paperstore ever grows one. Local SqliteBackend layout only.
    """
    md_path = backend.get_paper_md_path(pid)
    return md_path.parent.parent / "whisker" / "det"


def sidecar_path(pid: str, backend: StorageBackend):
    """Derive the ``<pid>.whisker.json`` sidecar path in the whisker dir.

    Uses the canonical markdown path (no existence check) so the stem casing
    matches the store without touching paperstore internals.
    """
    md_path = backend.get_paper_md_path(pid)
    return whisker_output_dir(pid, backend) / (md_path.stem + ".whisker.json")
