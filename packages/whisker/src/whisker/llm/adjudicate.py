#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Advisory LLM adjudication pipeline for conversion fidelity.

Two public entry points:

- :func:`select_candidates` — pure Python candidate selector (no LLM).
- :func:`adjudicate_paper` — async pipeline entry that runs the cascade.

Library returns data; the CLI persists.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline import (
    AgentBackend,
    PipelinePrompt,
    StepContext,
    StepHooks,
    build_pipeline,
    dispatch,
    resolve_pipeline_models,
    run_agent,
)
from pipeline.services import load_services

from whisker.det.score import VERDICT_FAIL, VERDICT_PASS, VERDICT_REVIEW, sidecar_path
from whisker.llm.chunking import (
    aggregate_adjudications,
    chunk_markdown,
    strip_binary_payloads,
    worst_axis_verdict,
)
from whisker.llm.constants import (
    CONFIDENCE_AMBIGUOUS_HI,
    CONFIDENCE_AMBIGUOUS_LO,
    COV_UNIGRAM_GAP_TRIGGER,
    GUARD_TAG,
    MAX_PAPER_MD_CHARS,
    MONOLITH_TIMEOUT_SECONDS,
    REGION_BENIGN_UNIGRAM_FLOOR,
    SHORT_CIRCUIT_CONFIDENCE,
    SIGNAL_AXIS_CONFLICT,
    SIGNAL_CONFIDENCE_AMBIGUOUS,
    SIGNAL_UNGROUNDED_EVIDENCE,
)
from whisker.llm.grounding import GROUND_FUZZY, ground_spans
from whisker.llm.html_outline import (
    SectionUnit,
    extract_heading_outline,
    extract_heading_outline_normalized,
    extract_section_units,
    format_outline,
)
from whisker.llm.metadata_compare import compare_metadata_outline
from whisker.llm.models import (
    Adjudication,
    AxisFinding,
    MetadataOutlineCheck,
    TapetumResult,
)
from whisker.llm.source_router import RiskSignal, route_html_units, route_pdf_units
from whisker.llm.table_compare import compare_pdf_tables
from whisker.llm.textlayer import (
    PageUnit,
    TextLayerError,
    extract_page_units,
    extract_textlayer,
)
from whisker.llm.toc_leak import clamp_toc_leak, detect_unpaired_toc_leak, toc_leak_tag
from whisker.llm.trace_render import render_text_trace
from whisker.llm.unit_judge import (
    UnitJudgeResult,
    build_llm_readability_block,
    hydrate_pipeline_prompt,
    resolve_runtime_code_contract,
    resolve_runtime_table_contract,
    run_metadata_outline_check,
    run_unit_checks,
)

logger = logging.getLogger(__name__)

__all__ = [
    "adjudicate_paper",
    "select_candidates",
]

# Per-slot output-token ceilings, mirroring the ``max-output`` step meta in
# ``llm.md``. Schema-level Field caps (models.py, 2026-07-08)
# enforce 60-word reasoning, 12-word axis notes, 20-word evidence quotes,
# so observed outputs are now well under 1k tokens. The backend grows on a
# ``finish_reason=length`` retry, so these ceilings are safe.
_SLOT_MAX_TOKENS = {
    "fast": 1024,
    "deep": 2048,
}
_DEFAULT_MAX_TOKENS = 2048
_SOURCE_METADATA_CHARS = 4000


def _textlayer_pages_or_none(ctx: StepContext) -> list[str] | None:
    """Extract PDF text-layer pages for table probes; None if not a PDF."""
    source_path = ctx.backend.get_source_path(ctx.pid)
    if not str(source_path).lower().endswith(".pdf"):
        return None
    try:
        return extract_textlayer(source_path)
    except TextLayerError:
        logger.info("%s: textlayer unavailable for table dumps", ctx.pid)
        return None


# -- Candidate selection (pure Python, no LLM) --------------------------------


def select_candidates(results: list[dict]) -> list[str]:
    """Select advisory candidates from whisker sidecar dicts.

    Three populations (synthesis 2a):
    - PRIMARY: pass-tier papers carrying gate-ignored risk signals.
    - SECONDARY: non-benign review papers (exclude region-only).
    - RESCUE: heading_monotone-only fails (advisory "likely shippable").

    Returns a sorted list of PIDs.
    """
    candidates: set[str] = set()

    for r in results:
        pid = r.get("pid", "")
        verdict = r.get("verdict", "")

        if verdict == VERDICT_PASS:
            if _has_pass_risk_signals(r):
                candidates.add(pid)

        elif verdict == VERDICT_REVIEW:
            if not _is_benign_region_only(r):
                candidates.add(pid)

        elif verdict == VERDICT_FAIL:
            if _is_heading_only_fail(r):
                candidates.add(pid)

    return sorted(candidates)


def _has_pass_risk_signals(r: dict) -> bool:
    """Check if a pass-tier paper carries false-pass risk signals."""
    if r.get("lossy_table_count", 0) > 0:
        return True
    if r.get("table_parse_errors", 0) > 0:
        return True
    if r.get("mojibake_count", 0) > 0:
        return True
    uni = r.get("unigram_coverage", 0.0)
    cov = r.get("coverage", 0.0)
    if (uni - cov) > COV_UNIGRAM_GAP_TRIGGER:
        return True
    return False


_REGION_FLAG_SUFFIX = "misaligned region(s)"


def _is_benign_region_only(r: dict) -> bool:
    """True if the paper's sole soft flag is misaligned region(s) with high uni."""
    soft_flags = r.get("soft_flags", [])
    if not soft_flags:
        return False
    if not all(f.endswith(_REGION_FLAG_SUFFIX) for f in soft_flags):
        return False
    uni = r.get("unigram_coverage", 0.0)
    return uni >= REGION_BENIGN_UNIGRAM_FLOOR


def _is_heading_only_fail(r: dict) -> bool:
    """True if the paper's sole hard flag is heading_monotone.

    Prefix-match the gate name; gate details quote document text (a
    no_toc_leak detail contains the word "heading"), so a substring match
    would wrongly route TOC-leak fails into the RESCUE population.
    """
    hard_flags = r.get("hard_flags", [])
    if not hard_flags:
        return False
    heading_flags = [f for f in hard_flags if f.startswith("gate:heading_monotone")]
    return len(heading_flags) == len(hard_flags)


# -- Pipeline state ------------------------------------------------------------


@dataclass
class _PipelineState:
    """Mutable state flowing through the tapetum_llm cascade."""

    paper_md: str = ""
    whisker_signals: dict = field(default_factory=dict)
    tier1: Adjudication | None = None
    tier2: Adjudication | None = None
    # True when the paper exceeded MAX_PAPER_MD_CHARS and was triaged in chunks.
    chunked: bool = False
    # True when a chunk could not be read in full (a single H2 section larger
    # than the budget was hard-split, or a chunk call failed). A partial read
    # must never become a clean pass: decide forces "review" and discloses it.
    partial: bool = False
    # Derived uncertainty signals that fired the tier-2 escalation (see the
    # SIGNAL_* constants). Empty when the tier-1 verdict stood.
    escalation_signals: list[str] = field(default_factory=list)
    # Source-aware unit check results (HTML and PDF paths, v6+)
    unit_result: UnitJudgeResult | None = None
    risk_signals: list[RiskSignal] = field(default_factory=list)
    metadata_outline_check: MetadataOutlineCheck | None = None
    table_compare_result: dict = field(default_factory=dict)
    unit_selection: list[dict] = field(default_factory=list)
    exhaustive: bool = False
    phase_durations: dict[str, float] = field(default_factory=dict)


@contextmanager
def _phase_timer(state: _PipelineState, name: str):
    """Accumulate ``time.monotonic()`` deltas into ``state.phase_durations``."""
    started = time.monotonic()
    try:
        yield
    finally:
        state.phase_durations[name] = (
            state.phase_durations.get(name, 0.0) + (time.monotonic() - started)
        )


# -- Step hooks ----------------------------------------------------------------


async def _custom_select(state: _PipelineState, ctx: StepContext, spec) -> None:
    """Step 0: load paper markdown and whisker signals.

    Inline binary payloads (data-URI images, bare base64 debris) are replaced
    by sanctioned markers before the markdown enters state: everything
    downstream (chunking, triage prompts, grounding) sees the same filtered
    text, so evidence char intervals stay consistent with what the LLM read.
    The on-disk paper.md is untouched.
    """
    backend = ctx.backend
    pid = ctx.pid

    paper_md, stripped = strip_binary_payloads(backend.get_paper_md(pid))
    if stripped:
        logger.info(
            "%s: stripped %d inline binary payload(s) before triage", pid, stripped
        )

    sc_path = sidecar_path(pid, backend)
    signals: dict = {}
    if sc_path.exists():
        signals = json.loads(sc_path.read_text(encoding="utf-8"))

    state.paper_md = paper_md
    state.whisker_signals = signals


async def _custom_triage(state: _PipelineState, ctx: StepContext, spec) -> None:
    """Step 1: fast-model triage.

    Papers within MAX_PAPER_MD_CHARS are a single LLM call. Oversized papers are
    split on H2 boundaries and triaged serially (D11: one in-flight request at a
    time, no parallelism), then folded into one Adjudication.

    HTML metadata-first: when the outline check already caps the paper and
    this is not an audit run, skip the monolith and persist the metadata
    verdict. Breaks the LJF HTML-giant convoy (metadata is a small prompt).
    """
    if await _html_metadata_first_skip_triage(state, ctx):
        return
    chunks, partial = chunk_markdown(state.paper_md, MAX_PAPER_MD_CHARS)
    if len(chunks) == 1:
        user_msg = _build_triage_message(state, ctx, state.paper_md)
        with _phase_timer(state, "triage"):
            state.tier1 = await asyncio.wait_for(
                run_agent(ctx, spec, user_msg),
                timeout=MONOLITH_TIMEOUT_SECONDS,
            )
        return

    state.chunked = True
    state.partial = partial
    parts: list[Adjudication] = []
    for index, chunk in enumerate(chunks):
        user_msg = _build_triage_message(
            state, ctx, chunk, chunk_index=index, chunk_count=len(chunks)
        )
        with _phase_timer(state, "triage"):
            parts.append(await asyncio.wait_for(
                run_agent(ctx, spec, user_msg),
                timeout=MONOLITH_TIMEOUT_SECONDS,
            ))
    state.tier1 = aggregate_adjudications(parts, len(chunks))


def _escalation_signals(tier1: Adjudication, paper_md: str) -> list[str]:
    """Derived uncertainty signals that justify a tier-2 re-read.

    Self-reported confidence is anti-calibrated (production: 18/18 fails at
    >= 0.95, band never hit in 198 runs), so the gate fires on observable
    contradictions instead: conflicting per-axis verdicts, evidence quotes
    that fail grounding, and (retained) the legacy scalar band. Sorted for
    a deterministic sidecar.
    """
    signals: set[str] = set()

    verdicts = {af.verdict for af in tier1.axis_findings}
    if VERDICT_PASS in verdicts and VERDICT_FAIL in verdicts:
        signals.add(SIGNAL_AXIS_CONFLICT)

    if tier1.evidence_spans:
        _, dropped = ground_spans(tier1.evidence_spans, paper_md)
        if dropped > 0:
            signals.add(SIGNAL_UNGROUNDED_EVIDENCE)

    if CONFIDENCE_AMBIGUOUS_LO <= tier1.confidence <= CONFIDENCE_AMBIGUOUS_HI:
        signals.add(SIGNAL_CONFIDENCE_AMBIGUOUS)

    return sorted(signals)


async def _custom_adjudicate(state: _PipelineState, ctx: StepContext, spec) -> None:
    """Step 2: deep-model adjudication (only when uncertainty signals fire)."""
    if state.tier1 is None:
        return

    # Oversized papers were triaged in chunks; re-injecting the full markdown for
    # tier2 would 413 again. Tier2 escalation for chunked papers is a later
    # upgrade. The aggregated tier1 stands.
    if state.chunked:
        return

    signals = _escalation_signals(state.tier1, state.paper_md)
    if not signals:
        return

    state.escalation_signals = signals
    user_msg = _build_adjudicate_message(state, ctx)
    with _phase_timer(state, "adjudicate"):
        result = await asyncio.wait_for(
            run_agent(ctx, spec, user_msg),
            timeout=MONOLITH_TIMEOUT_SECONDS,
        )
    state.tier2 = result


async def _custom_decide(state: _PipelineState, ctx: StepContext, spec) -> None:
    """Step 3: ground evidence, run unit checks, apply decision floor, build TapetumResult."""
    working = state.tier2 if state.tier2 is not None else state.tier1
    if working is None:
        return

    grounded, dropped = ground_spans(working.evidence_spans, state.paper_md)

    confidence = working.confidence

    # Overall == severity-aware worst axis (see _worst_axis_verdict). This
    # overrides the model's self-reported overall verdict so a fail/minor axis
    # cannot become a hard overall fail. Fall back to the reported verdict only
    # when there are no axis findings to fold.
    if working.axis_findings:
        suggested_verdict = worst_axis_verdict(working.axis_findings)
    else:
        suggested_verdict = working.verdict

    # Safety demotions (never upgrade): an ungrounded fail/review keeps the human,
    # and sub-floor confidence keeps the human. The lane never turns uncertainty
    # into a pass/fail.
    if suggested_verdict != VERDICT_PASS and not grounded:
        suggested_verdict = VERDICT_REVIEW
    # #277 condition 1: a pass whose evidence was emitted but entirely dropped
    # by grounding is untrustworthy (the model claimed evidence, none survived).
    # Demote to review. Do NOT demote passes with no evidence at all (sanctioned
    # empty-evidence passes where working.evidence_spans is empty/falsy).
    if (
        suggested_verdict == VERDICT_PASS
        and working.evidence_spans
        and not grounded
    ):
        suggested_verdict = VERDICT_REVIEW
    # Fuzzy-only demotion: evidence survived grounding but only at fuzzy
    # resolution (no exact char-interval). The model's claim is plausible
    # but not verifiably anchored, so the pass is untrustworthy.
    if (
        suggested_verdict == VERDICT_PASS
        and grounded
        and all(g.status == GROUND_FUZZY for g in grounded)
    ):
        suggested_verdict = VERDICT_REVIEW
    # Self-reported confidence is anti-calibrated (production: 18/18 fails at
    # >= 0.95, band never hit in 198 runs). Replace the scalar confidence floor
    # with a derived-signal demotion: if escalation signals fired (axis conflict,
    # ungrounded evidence) AND the model still claims pass, demote to review.
    # Zero confidence is a mechanical anomaly (model bug), not a calibration
    # signal: demote pass to review.
    if confidence == 0.0 and suggested_verdict == VERDICT_PASS:
        suggested_verdict = VERDICT_REVIEW
    if state.escalation_signals and suggested_verdict == VERDICT_PASS:
        suggested_verdict = VERDICT_REVIEW

    # A partial read (oversized section hard-split, or a failed chunk) must never
    # masquerade as a clean pass: force review and disclose it (docling's
    # PARTIAL_SUCCESS analog).
    if state.partial and suggested_verdict == VERDICT_PASS:
        suggested_verdict = VERDICT_REVIEW

    toc_hits = detect_unpaired_toc_leak(state.paper_md)
    suggested_verdict, _ = clamp_toc_leak(suggested_verdict, toc_hits)
    if toc_hits:
        patched = False
        for af in working.axis_findings:
            if af.axis == "structure":
                af.verdict, af.severity = clamp_toc_leak(
                    af.verdict, toc_hits, af.severity,
                )
                patched = True
        if not patched:
            working.axis_findings.append(
                AxisFinding(
                    axis="structure",
                    verdict="review",
                    severity="major",
                    note=f"toc_leak_unpaired: {toc_hits[0].heading!r}",
                )
            )
        working.reasoning = (
            (working.reasoning or "") + toc_leak_tag(toc_hits[0].heading)
        )
        logger.info(
            "%s: text-lane toc-leak clamp fired (%d hit(s)), verdict=%s",
            ctx.pid, len(toc_hits), suggested_verdict,
        )

    # -- Source-aware unit checks (v6+, HTML and PDF) --
    # Runs after the monolith triage/adjudicate.
    source_path = ctx.backend.get_source_path(ctx.pid)
    if str(source_path).lower().endswith((".html", ".htm")):
        await _run_html_unit_checks(state, ctx)
    elif str(source_path).lower().endswith(".pdf"):
        await _run_pdf_unit_checks(state, ctx)
    if state.metadata_outline_check is not None:
        if state.metadata_outline_check.verdict == VERDICT_FAIL:
            suggested_verdict = VERDICT_FAIL
        elif (
            state.metadata_outline_check.verdict == VERDICT_REVIEW
            and suggested_verdict == VERDICT_PASS
        ):
            suggested_verdict = VERDICT_REVIEW
    if state.unit_result is not None and state.unit_result.verdict == "review":
        if suggested_verdict == VERDICT_PASS:
            suggested_verdict = VERDICT_REVIEW

    # Corroboration rule (v21): a monolith fail stays only when a second
    # independent signal supports it. Without corroboration the claim is a
    # single-model utterance and folds to review. Corroborators:
    #   - verified unit defect (unit checks found a concrete bug)
    #   - metadata verdict fail (title/doc identity is wrong)
    #   - TOC leak clamp (structural artefact detected deterministically)
    if suggested_verdict == VERDICT_FAIL:
        has_unit_defect = (
            state.unit_result is not None
            and state.unit_result.has_verified_defects()
        )
        has_metadata_fail = (
            state.metadata_outline_check is not None
            and state.metadata_outline_check.verdict == VERDICT_FAIL
        )
        has_toc_clamp = bool(toc_hits)
        if not (has_unit_defect or has_metadata_fail or has_toc_clamp):
            suggested_verdict = VERDICT_REVIEW
            logger.info(
                "%s: fail demoted to review (no corroboration: "
                "unit_defect=%s, metadata_fail=%s, toc_clamp=%s)",
                ctx.pid, has_unit_defect, has_metadata_fail, has_toc_clamp,
            )

    escalated = state.tier2 is not None
    tier1_model = _resolve_model_name(ctx, "fast")
    tier2_model = _resolve_model_name(ctx, "deep") if escalated else None

    axis_dicts = [
        {"axis": af.axis, "verdict": af.verdict, "severity": af.severity, "note": af.note}
        for af in working.axis_findings
    ]

    evidence_dicts = [
        {"quote": g.span.quote, "status": g.status, "start": g.start, "end": g.end}
        for g in grounded
    ]

    # Collect source-aware unit check data for the sidecar
    risk_signal_dicts: list[dict] = [
        {"unit_id": s.unit_id, "signal_type": s.signal_type,
         "severity": s.severity, "detail": s.detail}
        for s in state.risk_signals
    ]
    defect_group_dicts: list[dict] = []
    unit_check_dicts: list[dict] = []
    if state.unit_result is not None:
        defect_group_dicts = state.unit_result.defect_groups
        unit_check_dicts = state.unit_result.unit_results
    unit_evidence_dispositions = [
        {
            **disposition,
            "unit_id": unit_result.get("unit_id", ""),
        }
        for unit_result in unit_check_dicts
        for disposition in unit_result.get("evidence_dispositions", [])
    ]
    unit_evidence_summary = (
        state.unit_result.evidence_summary
        if state.unit_result is not None
        else {
            "present_in_candidate": 0,
            "candidate_not_found": 0,
            "ambiguous": 0,
            "source_ungrounded": 0,
        }
    )
    unit_coverage = (
        {
            "coverage_complete": state.unit_result.coverage_complete,
            "checked_unit_ids": state.unit_result.checked_unit_ids,
            "unchecked_unit_ids": state.unit_result.unchecked_unit_ids,
            "failed_unit_ids": state.unit_result.failed_unit_ids,
            "evidence_summary": state.unit_result.evidence_summary,
        }
        if state.unit_result is not None
        else {
            "coverage_complete": True,
            "checked_unit_ids": [],
            "unchecked_unit_ids": [],
            "failed_unit_ids": [],
        }
    )

    # Readability probes (table dumps, code probes) are synchronous httpx
    # calls. They run in a worker thread so they cannot block the event loop
    # that serves the other in-flight papers; timed as their own phase so
    # the trace shows their share.
    with _phase_timer(state, "readability"):
        llm_readability = await asyncio.to_thread(
            build_llm_readability_block,
            state.paper_md,
            pid=ctx.pid,
            service=tier1_model or None,
            table_compare=state.table_compare_result or None,
            textlayer_pages=_textlayer_pages_or_none(ctx),
            source_path=ctx.backend.get_source_path(ctx.pid),
        )

    result = TapetumResult(
        pid=ctx.pid,
        whisker_verdict=state.whisker_signals.get("verdict", ""),
        suggested_verdict=suggested_verdict,
        confidence=confidence,
        escalated=escalated,
        tier1_model=tier1_model,
        tier2_model=tier2_model,
        axis_findings=axis_dicts,
        grounded_evidence=evidence_dicts,
        evidence_dispositions=unit_evidence_dispositions,
        evidence_summary=unit_evidence_summary,
        ungrounded_dropped=dropped,
        escalation_signals=state.escalation_signals,
        primary_concern=working.primary_concern,
        reasoning=working.reasoning,
        risk_signals=risk_signal_dicts,
        defect_groups=defect_group_dicts,
        unit_checks=unit_check_dicts,
        metadata_outline_check=(
            state.metadata_outline_check.model_dump()
            if state.metadata_outline_check is not None
            else {}
        ),
        unit_coverage=unit_coverage,
        unit_selection=state.unit_selection,
        table_compare=state.table_compare_result,
        llm_readability=llm_readability,
    )

    state._result = result  # type: ignore[attr-defined]


async def _ensure_html_metadata(
    state: _PipelineState, ctx: StepContext,
) -> None:
    """Run the HTML metadata/outline check once and store it on ``state``."""
    with _phase_timer(state, "metadata"):
        await _ensure_html_metadata_body(state, ctx)


async def _ensure_html_metadata_body(
    state: _PipelineState, ctx: StepContext,
) -> None:
    """Inner metadata work; the public wrapper times even a no-op second call."""
    if state.metadata_outline_check is not None:
        return
    source_path = ctx.backend.get_source_path(ctx.pid)
    if not str(source_path).lower().endswith((".html", ".htm")):
        return
    try:
        html_source = source_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    section_units: list[SectionUnit] = extract_section_units(html_source)
    source_outline = extract_heading_outline(html_source)
    agent = ctx.agents.get("fast")
    if agent is None:
        raise RuntimeError(f"{ctx.pid}: fast agent unavailable for source checks")
    metadata_parts = [
        f"{tag}: {text}" for tag, text in source_outline[:3]
    ]
    if section_units:
        metadata_parts.append(section_units[0].text[:_SOURCE_METADATA_CHARS])
    else:
        metadata_parts.append(html_source[:_SOURCE_METADATA_CHARS])
    _use_det_metadata = os.environ.get("TAPETUM_DET_METADATA") == "1"
    _shadow_metadata = os.environ.get("TAPETUM_METADATA_SHADOW") == "1"

    det_metadata_check: MetadataOutlineCheck | None = None
    if _use_det_metadata or _shadow_metadata:
        source_outline_pairs = extract_heading_outline_normalized(html_source)
        det_metadata_check = compare_metadata_outline(
            ctx.pid,
            "\n".join(metadata_parts),
            [f"{tag}: {text}" for tag, text in source_outline],
            state.paper_md,
            source_kind="html",
            html_outline=source_outline_pairs,
        )

    if _use_det_metadata:
        state.metadata_outline_check = det_metadata_check
    else:
        state.metadata_outline_check = await run_metadata_outline_check(
            ctx.pid,
            "\n".join(metadata_parts),
            [f"{tag}: {text}" for tag, text in source_outline],
            state.paper_md,
            agent,
            debug_log=ctx.debug_log,
            guard_tag=GUARD_TAG,
        )

    if _shadow_metadata and det_metadata_check is not None:
        logger.info(
            "%s: metadata shadow - det=%s llm=%s (match=%s)",
            ctx.pid, det_metadata_check.verdict,
            state.metadata_outline_check.verdict,
            det_metadata_check.verdict == state.metadata_outline_check.verdict,
        )


async def _html_metadata_first_skip_triage(
    state: _PipelineState, ctx: StepContext,
) -> bool:
    """True when HTML metadata already caps the paper and triage should skip."""
    if state.exhaustive:
        return False
    source_path = ctx.backend.get_source_path(ctx.pid)
    if not str(source_path).lower().endswith((".html", ".htm")):
        return False
    await _ensure_html_metadata(state, ctx)
    check = state.metadata_outline_check
    if check is None or check.verdict == VERDICT_PASS:
        return False
    state.tier1 = Adjudication(
        reasoning=(
            "Metadata-first short-circuit: outline already caps the paper."
        ),
        axis_findings=[],
        worst_axis="structure",
        verdict=check.verdict,
        confidence=SHORT_CIRCUIT_CONFIDENCE,
        evidence_spans=[],
        primary_concern="metadata/outline mismatch",
    )
    logger.info(
        "%s: HTML metadata-first short-circuit (verdict=%s); skipping triage",
        ctx.pid, check.verdict,
    )
    return True


async def _run_html_unit_checks(state: _PipelineState, ctx: StepContext) -> None:
    """Source-aware unit checks for HTML papers (v6).

    Extracts section units from the HTML source, routes risk signals,
    and runs scoped LLM checks on flagged sections. Only runs when the
    source is HTML. Metadata may already have run (metadata-first triage).
    """
    source_path = ctx.backend.get_source_path(ctx.pid)

    if not str(source_path).lower().endswith((".html", ".htm")):
        return

    with _phase_timer(state, "unit_checks"):
        await _run_html_unit_checks_body(state, ctx, source_path)


async def _run_html_unit_checks_body(
    state: _PipelineState, ctx: StepContext, source_path: Path,
) -> None:
    """Inner unit-check work; the wrapper owns the source gate and the timer."""
    await _ensure_html_metadata(state, ctx)

    # Metadata short-circuit: skip unit checks when metadata already caps verdict.
    # Audit modes (exhaustive) are exempt.
    if (
        state.metadata_outline_check is not None
        and state.metadata_outline_check.verdict != "pass"
        and not state.exhaustive
    ):
        logger.info(
            "%s: HTML metadata short-circuit (verdict=%s); skipping unit checks",
            ctx.pid, state.metadata_outline_check.verdict,
        )
        return

    html_source = source_path.read_text(encoding="utf-8", errors="replace")
    section_units: list[SectionUnit] = extract_section_units(html_source)
    source_outline = extract_heading_outline(html_source)
    agent = ctx.agents.get("fast")
    if agent is None:
        raise RuntimeError(f"{ctx.pid}: fast agent unavailable for source checks")

    if not section_units:
        return

    risk_signals = route_html_units(section_units, state.paper_md, source_outline)
    state.risk_signals = risk_signals

    if not risk_signals:
        return

    unit_text_map: dict[str, str] = {
        f"section:{unit.section_id}": unit.text for unit in section_units
    }

    state.unit_result = await run_unit_checks(
        ctx.pid,
        state.paper_md,
        agent,
        risk_signals=risk_signals,
        unit_text_map=unit_text_map,
        debug_log=ctx.debug_log,
        exhaustive=state.exhaustive,
        guard_tag=GUARD_TAG,
    )


async def _run_pdf_unit_checks(state: _PipelineState, ctx: StepContext) -> None:
    """Source-aware unit checks for PDF papers.

    Extracts page units from the PDF source, routes risk signals (including
    table presence), runs cell-grid comparison via PyMuPDF find_tables(),
    and runs scoped LLM checks on flagged pages.
    """
    source_path = ctx.backend.get_source_path(ctx.pid)

    if not str(source_path).lower().endswith(".pdf"):
        return

    with _phase_timer(state, "unit_checks"):
        try:
            page_units: list[PageUnit] = extract_page_units(source_path)
        except Exception as exc:
            logger.warning("%s: PDF page unit extraction failed: %s", ctx.pid, exc)
            return

        agent = ctx.agents.get("fast")
        if agent is None:
            raise RuntimeError(f"{ctx.pid}: fast agent unavailable for PDF source checks")

        risk_signals = route_pdf_units(page_units, state.paper_md)
        state.risk_signals = risk_signals

        try:
            with _phase_timer(state, "table_compare"):
                table_result = compare_pdf_tables(source_path, state.paper_md)
            state.table_compare_result = {
                "total_source_tables": table_result.total_source_tables,
                "total_candidate_tables": table_result.total_candidate_tables,
                "matched_tables": table_result.matched_tables,
                "cell_diff_count": len(table_result.cell_diffs),
                "grid_unreliable": table_result.grid_unreliable,
                "cell_diffs": [
                    {
                        "page": d.page,
                        "table_index": d.table_index,
                        "row": d.row,
                        "col": d.col,
                        "source_text": d.source_text,
                        "candidate_text": d.candidate_text,
                        "diff_type": d.diff_type,
                    }
                    for d in table_result.cell_diffs
                ],
            }
            if table_result.cell_diffs:
                for diff in table_result.cell_diffs:
                    unit_id = f"page:{diff.page}"
                    existing = any(
                        s.unit_id == unit_id and s.signal_type == "table_corruption"
                        for s in risk_signals
                    )
                    if not existing:
                        risk_signals.append(RiskSignal(
                            unit_id=unit_id,
                            signal_type="table_corruption",
                            severity="critical",
                            detail=(
                                f"cell ({diff.row},{diff.col}): source "
                                f"{diff.source_text!r} vs candidate "
                                f"{diff.candidate_text!r}"
                            ),
                        ))
        except Exception as exc:
            logger.warning("%s: table comparison failed: %s", ctx.pid, exc)

        if not risk_signals:
            return

        unit_text_map: dict[str, str] = {
            f"page:{unit.page}": unit.text for unit in page_units
        }

        state.unit_result = await run_unit_checks(
            ctx.pid,
            state.paper_md,
            agent,
            risk_signals=risk_signals,
            unit_text_map=unit_text_map,
            debug_log=ctx.debug_log,
            exhaustive=state.exhaustive,
            guard_tag=GUARD_TAG,
        )


def _build_hooks() -> dict[str, StepHooks]:
    """Build the step hook table for tapetum_llm.

    Keys are the full step header strings from llm.md, validated by
    test_hooks_match_tapetum_md.
    """
    return {
        "0. Select": StepHooks(custom=_custom_select),
        "1. Triage": StepHooks(custom=_custom_triage, output_type=Adjudication),
        "2. Adjudicate": StepHooks(custom=_custom_adjudicate, output_type=Adjudication),
        "3. Decide": StepHooks(custom=_custom_decide),
    }


# -- Message builders ----------------------------------------------------------

def _build_triage_message(
    state: _PipelineState,
    ctx: StepContext,
    md: str,
    *,
    chunk_index: int | None = None,
    chunk_count: int | None = None,
) -> str:
    """Build the user message for the Triage step.

    ``md`` is the markdown to inject (the full paper, or one chunk of an oversized
    paper). When ``chunk_count`` is set, a note tells the model this is a partial
    view so it does not flag chunk-boundary artifacts as conversion defects.

    Independence: no deterministic-lane signals (verdict, flags, metrics) are
    injected. The LLM judges the markdown on its own; fusion compares the two
    independent verdicts afterward.

    For HTML papers, a deterministic heading outline (h1-h6 tags from the source)
    is injected so the LLM can detect heading-level drift against the source.
    This is source metadata, not a whisker signal.
    """
    chunk_note = ""
    if chunk_count is not None:
        chunk_note = (
            f"NOTE: this is chunk {(chunk_index or 0) + 1} of {chunk_count} of a "
            f"large paper. Judge only the content shown. Do not flag missing front "
            f"matter, missing sections, or a body that stops mid-sentence at the "
            f"chunk boundary.\n"
        )

    outline_block = ""
    try:
        source_path = ctx.backend.get_source_path(ctx.pid)
        if str(source_path).lower().endswith((".html", ".htm")):
            html_source = source_path.read_text(encoding="utf-8", errors="replace")
            outline = format_outline(extract_heading_outline(html_source))
            if outline:
                outline_block = f"\n{outline}\n\n"
    except Exception:
        # Best-effort source metadata: a missing/unstaged source, unreadable
        # file, or test double must not break triage. Falls back to no outline.
        pass

    header = (
        f"Paper: {ctx.pid}\n"
        f"{chunk_note}{outline_block}\n"
        f"Converted Markdown:\n"
    )
    wrapped_md = ctx.inject_untrusted(md)
    return header + wrapped_md


def _build_adjudicate_message(state: _PipelineState, ctx: StepContext) -> str:
    """Build the user message for the Adjudicate step (includes tier1 reasoning).

    Tier-1 free-text fields (reasoning, concern) are model output derived from
    the untrusted paper text, so they are wrapped like the markdown itself: a
    paper that smuggled instructions into tier 1's reasoning must not have them
    replayed to tier 2 as trusted prose.

    Independence: no deterministic-lane signals (verdict, flags) are injected.
    Only the LLM's own tier-1 output is fed back for the deeper re-read.
    """
    tier1 = state.tier1
    assert tier1 is not None

    signals_str = ", ".join(state.escalation_signals) or "none"
    tier1_text = ctx.inject_untrusted(
        f"Tier 1 reasoning: {tier1.reasoning}\n"
        f"Tier 1 concern: {tier1.primary_concern}"
    )
    header = (
        f"Paper: {ctx.pid}\n"
        f"Escalation signals: {signals_str}\n\n"
        f"{tier1_text}\n"
        f"Tier 1 verdict: {tier1.verdict} (confidence {tier1.confidence:.2f})\n"
        f"Tier 1 worst axis: {tier1.worst_axis}\n\n"
        f"Converted Markdown:\n"
    )
    wrapped_md = ctx.inject_untrusted(state.paper_md)
    return header + wrapped_md


def _render_trace_firewalled(
    state: _PipelineState, step: int, ctx: StepContext,
) -> str:
    """Render the trace for ``dispatch``; a render bug must never fail the paper.

    ``dispatch`` calls the renderer inside its ``finally``, so an exception
    here would replace the paper's real outcome with a diagnostics error.
    """
    try:
        return render_text_trace(state, step, step_metrics=ctx.step_metrics)
    except Exception as exc:  # diagnostics firewall (see docstring)
        logger.warning("%s: trace render failed: %s", ctx.pid, exc)
        return f"trace render failed: {type(exc).__name__}: {exc}\n"


def _resolve_model_name(ctx: StepContext, slot: str) -> str:
    """Get the service name backing a slot (reflects any --service override)."""
    agent = ctx.agents.get(slot)
    if agent is not None and agent.service_name:
        return agent.service_name
    return slot


# -- Public entry point --------------------------------------------------------


async def adjudicate_paper(
    pid: str,
    backend: Any,
    *,
    debug: bool = False,
    trace: bool = False,
    exhaustive: bool = False,
    service_overrides: dict[str, str] | None = None,
    registry: Any | None = None,
) -> TapetumResult:
    """Run the tapetum_llm advisory cascade on a single paper.

    Model selection comes from ``llm.md``'s ``## Services`` block.
    ``service_overrides`` (slot -> service name) takes precedence per slot,
    so a caller can repoint ``fast``/``deep`` at a running pod without editing
    the authority doc. ``registry`` lets batch callers load SERVICES.toml
    once and share it across papers; when omitted, it is loaded per call.
    Library returns TapetumResult; does NOT write files.
    """
    prompt = PipelinePrompt.load("whisker", "llm/llm.md")
    if registry is None:
        registry = load_services()

    # Effective services: the frozen prompt map plus any per-slot override.
    services = dict(prompt.services)
    if service_overrides:
        services.update(service_overrides)

    table_contract = resolve_runtime_table_contract(
        service=services.get("fast") or services.get("default")
    )
    code_contract = resolve_runtime_code_contract(
        service=services.get("fast") or services.get("default")
    )
    prompt = hydrate_pipeline_prompt(
        prompt, table_contract, code_resolved=code_contract
    )

    models = resolve_pipeline_models(services, registry)

    agents: dict[str, AgentBackend] = {
        name: AgentBackend(
            model_backend,
            max_tokens=_SLOT_MAX_TOKENS.get(name, _DEFAULT_MAX_TOKENS),
            thinking_budget=0,  # pod default flipped thinking-on (probe 2026-09-03)
            slot_name=name,
            service_name=services[name],
        )
        for name, model_backend in models.items()
    }

    hooks = _build_hooks()
    pipeline = build_pipeline(prompt, hooks)

    state = _PipelineState()
    state.exhaustive = exhaustive

    ctx = StepContext(
        prompt=prompt,
        agents=agents,
        backend=backend,
        debug=debug,
        pid=pid,
        default_concurrency=1,
        # Constant tag (see constants.GUARD_TAG): the framework floor puts
        # the guard instruction at byte 0 of the system prompt, so the
        # default random-per-context tag would defeat cross-paper prefix
        # caching and vary the prompt bytes between runs.
        _guard_tag=GUARD_TAG,
    )

    debug_path: Path | None = None
    trace_path: Path | None = None
    if hasattr(backend, "get_debug_md_path"):
        debug_path = backend.get_debug_md_path(pid, tool="tapetum_llm") if debug else None
        trace_path = backend.get_trace_md_path(pid, tool="tapetum_llm") if trace else None

    await dispatch(
        pipeline,
        state,
        ctx,
        tool_name="tapetum_llm",
        trace_path=trace_path,
        debug_path=debug_path if debug else None,
        render_trace_fn=lambda st, step: _render_trace_firewalled(
            st, step, ctx
        ),
    )

    result: TapetumResult | None = getattr(state, "_result", None)
    if result is None:
        return TapetumResult(
            pid=pid,
            whisker_verdict=state.whisker_signals.get("verdict", ""),
            suggested_verdict=VERDICT_REVIEW,
            confidence=0.0,
            escalated=False,
            tier1_model=_resolve_model_name(ctx, "fast"),
            tier2_model=None,
            primary_concern="pipeline did not produce a result",
            reasoning="",
            status="error",
        )

    return result
