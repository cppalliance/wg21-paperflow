#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""PDF-Text-Lane: DeepSeek judges PDF text layer vs tomd-Markdown.

The text-only replacement for the dormant VLM lane. PyMuPDF extracts
the PDF's embedded text layer (an extraction path independent of tomd),
and a text LLM receives BOTH the raw text layer and the converted
markdown, judging conversion fidelity against the prompt rules.

Unlike the VLM lane (pixels only, deterministic diff afterwards), the
judge here sees both sides at once. That is a deliberate, user-approved
trade: no vision endpoint exists, and the runtime simulation showed
DeepSeek-V4 discriminates cleanly (clean pair -> pass 0.98, half the
markdown removed -> fail 1.00 with precise missing-content quotes).

Deterministic metrics (text_nid, content_recall) are computed alongside
and recorded in the sidecar as supplementary signals, NOT as the
verdict: the raw text layer's line breaks and missing heading markup
make the VLM-lane thresholds systematically too strict here.

The system prompt carries a binding output-discipline section (mirroring
the text lane in llm.md): shorter answers are the latency lever
because per-call time is decode-bound (~70 tok/s on alliance-pod).

Library-pure: returns data, never persists.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import secrets
import time
from collections import Counter
from dataclasses import dataclass, field

from pipeline import AgentBackend
from pipeline.tools import guard_instruction, inject_untrusted
from pydantic import BaseModel, Field

from whisker.det.llm_readability.code_validate import code_units_with_spans
from whisker.llm.chunking import strip_binary_payloads
from whisker.llm.constants import (
    MAX_MISSING_QUOTES,
    MAX_PAGE_ESCALATIONS,
    MONOLITH_TIMEOUT_SECONDS,
    PAGE_ESCALATION_TIMEOUT_SECONDS,
    PAGE_MIN_TOKENS,
    PAGE_RECALL_FLOOR,
    PDF_JUDGE_NID_FLOOR,
    PDF_JUDGE_RECALL_FLOOR,
)
from whisker.llm.fence_fonts import (
    FenceFontEvidence,
    clamp_source_monospace,
    fence_font_evidence,
)
from whisker.llm.grounding import (
    CANDIDATE_AMBIGUOUS,
    CANDIDATE_NOT_FOUND,
    CANDIDATE_PRESENT,
    CandidateEvidence,
    classify_candidate_evidence,
    ground_page_spans,
    ground_spans,
)
from whisker.llm.judge_task import run_judge_task
from whisker.llm.metadata_compare import compare_metadata_outline
from whisker.llm.models import (
    CODE_BOUNDARY_MAX_TOKENS,
    CodeBoundaryJudgment,
    EvidenceSpan,
    IdealVerification,
    MetadataOutlineCheck,
    PageJudgment,
    Verdict,
)
from whisker.llm.source_router import RiskSignal, route_pdf_units
from whisker.llm.table_compare import TableCompareResult, compare_pdf_tables
from whisker.llm.textlayer import (
    PageUnit,
    TextLayerError,
    clean_pages,
    extract_page_units,
    extract_textlayer,
    normalize_textlayer,
)
from whisker.llm.toc_leak import clamp_toc_leak, detect_unpaired_toc_leak, toc_leak_tag
from whisker.llm.trace_render import DONE_PHASE, PHASE_STARTED_KEY
from whisker.llm.unit_judge import (
    CONVERSION_CONTRACT,
    METADATA_CHECK_SYSTEM_PROMPT,
    UNIT_CHECK_SYSTEM_PROMPT,
    UnitJudgeResult,
    build_llm_readability_block,
    inject_code_rubric,
    inject_table_rubric,
    resolve_runtime_code_contract,
    resolve_runtime_table_contract,
    run_metadata_outline_check,
    run_unit_checks,
)
from whisker.metrics import content_recall, content_tokens, normalized_text, text_nid

logger = logging.getLogger(__name__)

__all__ = [
    "CODE_BOUNDARY_SYSTEM_PROMPT",
    "PdfJudgment",
    "PdfJudgeResult",
    "PdfLaneError",
    "JUDGE_SYSTEM_PROMPT",
    "METADATA_CHECK_SYSTEM_PROMPT",
    "PAGE_JUDGE_SYSTEM_PROMPT",
    "PageScreenEntry",
    "UNIT_CHECK_SYSTEM_PROMPT",
    "screen_pages",
    "judge_pdf_extraction",
]

CONTEXT_SAFETY_MARGIN = 0.80
"""Both texts plus prompt overhead must fit within this fraction of the
service's context window, otherwise the paper fails loudly (fidelity:
no silent truncation)."""

_MARKUP_CLAIM_TOKENS = (
    "<ins>", "<del>", "</ins>", "</del>",
    ":::wording", ":::wording-add", ":::wording-remove",
)
"""Wording-markup tokens the system prompt describes as sanctioned. They can
bleed into the judge's ``reasoning`` (rubric bleed) even when absent from the
markdown; ``_annotate_reasoning`` flags that specific hallucination pattern."""

_DEHYPHENATE_RE = re.compile(r"(\w)-\n(\w)")
"""A word split across a line break by a trailing hyphen."""

PDF_SIDECAR_SCHEMA_VERSION = 9
"""Bump when PDF sidecar fields change; fusion tolerates unknown keys.

v9: adds ``evaluated_at`` (B2 warm marker, cli.py._persist_lane_result), set
only on an actual evaluation, never on a fingerprint skip.
"""


def _set_progress(progress: dict | None, **fields) -> None:
    """Cheap in-place progress writes for CLI partial-audit persistence.

    When ``phase`` is passed, close out the previous phase into
    ``phase_durations`` (accumulate) and start the new one.
    """
    if progress is None:
        return
    phase = fields.get("phase")
    if phase is not None:
        now = time.monotonic()
        durations = progress.setdefault("phase_durations", {})
        previous = progress.get("phase")
        started = progress.get(PHASE_STARTED_KEY)
        if (
            previous
            and previous != DONE_PHASE
            and started is not None
        ):
            durations[previous] = durations.get(previous, 0.0) + (now - started)
        progress[PHASE_STARTED_KEY] = now
    progress.update(fields)


def _empty_unit_selection() -> dict[str, list[str]]:
    """Sidecar unit_selection shape when all-pages mode is off."""
    return {
        "required": [],
        "checked": [],
        "unchecked": [],
        "failed": [],
    }


def _dehyphenate(text: str) -> str:
    """Rejoin a word split across a page-internal line break by a hyphen.

    Without this, a cross-page-style hyphen split ("implementa-" / "tion")
    tokenizes as two tokens that match neither the source word nor its
    correctly-joined form in the markdown, undercounting a healthy page's
    recall (research/research/per-page-judging/SYNTHESIS.md edge-case 4).
    """
    return _DEHYPHENATE_RE.sub(r"\1\2", text)


def _annotate_reasoning(reasoning: str, paper_md: str) -> str:
    """Flag markup-token claims in reasoning that contradict the markdown.

    The system prompt describes sanctioned wording-markup forms (e.g.
    <ins>/<del>), which can bleed into the model's reasoning even when absent
    from the actual file. This check catches the most common rubric-bleed
    pattern.
    """
    annotations: list[str] = []
    reasoning_lower = reasoning.lower()
    for token in _MARKUP_CLAIM_TOKENS:
        if token.lower() in reasoning_lower and token not in paper_md:
            annotations.append(f"'{token}' not present in markdown")
    if annotations:
        return reasoning + f" [unverified: {'; '.join(annotations)}]"
    return reasoning


# CONVERSION_CONTRACT lives in unit_judge (public) so the unit lane and
# this lane share one text without an import cycle. Sanctioned conversion
# behavior for every judge prompt here (monolith and page-scoped
# escalation): the page-1/TOC/figure traps that make naive presence
# checks structurally false-fail-prone unless the full contract is
# inherited (research/research/per-page-judging/SYNTHESIS.md).

JUDGE_SYSTEM_PROMPT = (
    "You are a conversion-fidelity judge. You receive two versions of the "
    "same WG21 C++ committee paper:\n"
    "1. RAW PDF TEXT: the text layer extracted directly from the PDF "
    "(includes page headers/footers and raw line breaks; that is expected "
    "noise, not an error).\n"
    "2. CONVERTED MARKDOWN: the output of our PDF-to-Markdown converter.\n\n"
    "Judge whether the markdown faithfully preserves the paper's content: "
    "sections, prose, tables, code blocks, math, references. Ignore "
    "formatting differences, page furniture (running titles, page numbers), "
    "and line-wrap artifacts in the raw text. Flag only real content loss, "
    "corruption, or reordering.\n\n"
    + CONVERSION_CONTRACT +
    "Verdict semantics:\n"
    "- pass: the markdown faithfully represents the PDF text.\n"
    "- review: minor omissions or structural drift a human should check.\n"
    "- fail: substantial content missing, corrupted, or reordered.\n\n"
    f"Report at most {MAX_MISSING_QUOTES} missing-content quotes, most "
    "important first. Each quote must be copied verbatim from the RAW PDF "
    "TEXT so it can be verified mechanically. Never quote page furniture, "
    "the TOC, or title-block lines that map to the YAML front matter as "
    "missing content. Leaked TOC found in the markdown is reported in "
    "`reasoning`, not as a missing-content quote.\n\n"
    "### Output discipline (binding)\n\n"
    "Inspect thoroughly, report tersely. Length limits cap prose, never "
    "judgment:\n"
    "- `reasoning`: at most 60 words. State what you checked and the "
    "deciding finding, nothing else.\n"
    "- `missing_content`: each quote at most 20 words, still verbatim. "
    "Pick the single most damning excerpt per gap; do not stack "
    "cumulative evidence for the same defect.\n"
    "- Do not restate the rubric, conversion contract, or sanctioned "
    "behavior in your output.\n"
)

PAGE_JUDGE_SYSTEM_PROMPT = (
    "You are a conversion-fidelity judge performing a SCOPED re-check of "
    "ONE page that a deterministic recall screen flagged as possibly "
    "missing from the markdown. You receive:\n"
    "1. RAW PDF TEXT: the text layer of THIS ONE PAGE ONLY (includes "
    "page headers/footers and raw line breaks; that is expected noise, "
    "not an error).\n"
    "2. CONVERTED MARKDOWN: the full converted document (all pages).\n\n"
    "Question: which content-bearing text of THIS PAGE is missing from "
    "the markdown? Content from this page counts as present if it "
    "appears ANYWHERE in the markdown, in any order; document-wide "
    "reordering is a separate check you are not performing here.\n\n"
    + CONVERSION_CONTRACT +
    "Answer semantics:\n"
    "- content_missing=false: nothing content-bearing from this page is "
    "missing, OR everything that looks missing is sanctioned conversion "
    "behavior described above.\n"
    "- content_missing=true: content-bearing text from this page is "
    "genuinely absent from the markdown.\n\n"
    f"Report at most {MAX_MISSING_QUOTES} missing-content quotes, most "
    "important first. Each quote must be copied verbatim from THIS "
    "PAGE'S raw text so it can be verified mechanically. Never quote "
    "page furniture, the TOC, or title-block lines that map to the YAML "
    "front matter as missing content. Leaked TOC found in the markdown "
    "is reported in `reasoning`, not as a missing-content quote.\n\n"
    "### Output discipline (binding)\n\n"
    "Inspect thoroughly, report tersely. Length limits cap prose, never "
    "judgment:\n"
    "- `reasoning`: at most 60 words. State what you checked and the "
    "deciding finding, nothing else.\n"
    "- `missing_content`: each quote at most 20 words, still verbatim. "
    "Pick the single most damning excerpt per gap; do not stack "
    "cumulative evidence for the same defect.\n"
    "- Do not restate the rubric, conversion contract, or sanctioned "
    "behavior in your output.\n"
)

class PdfJudgment(BaseModel):
    """Structured judge output (D6)."""

    verdict: Verdict = Field(
        description="pass = faithful, review = minor issues, not-llm-readable = "
        "substantial content loss or corruption."
    )
    missing_content: list[str] = Field(
        default_factory=list,
        max_length=MAX_MISSING_QUOTES,
        description="Verbatim quotes from the RAW PDF TEXT that are absent "
        f"from the markdown (max {MAX_MISSING_QUOTES}, most important "
        "first). Empty if nothing is missing.",
    )
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(
        description="At most 60 words: what was checked, deciding finding."
    )


CODE_BOUNDARY_SYSTEM_PROMPT = (
    "You are a code-boundary fidelity judge for a WG21 C++ committee paper. "
    "You receive ONE fenced code block together with a few lines of "
    "surrounding context (before and after the fence). Your task: decide "
    "whether the fence boundaries of THIS SINGLE FENCE are correct.\n\n"
    "Specifically check for:\n"
    "- heading_in_fence: a SECTION HEADING or TITLE line sits INSIDE the "
    "fenced code block where it does not belong. A heading is a numbered "
    "or lettered section label like 'F. Modifications to ...' or "
    "'4.2 Function synopsis'. NEVER flag: C++ keywords (if, for, while, "
    "fwd, auto), identifiers (make_array, fwd, span), or comment lines "
    "(// ..., including // [stable.name]). A line starting with // inside "
    "a fence is ALWAYS a C++ comment, never a heading.\n"
    "- listing_split: this fence is a micro-fragment (1-2 body lines, a "
    "lone keyword, an ellipsis-only fence) that was clearly part of a "
    "larger listing now split across multiple fences. Look at the context "
    "lines for adjacent micro-fences as evidence.\n"
    "- prose_in_fence: ordinary prose text or non-code labels have been "
    "swallowed into the code fence. Examples: bare identifiers on their "
    "own line before a function definition, plain-English sentences. "
    "When a SOURCE FONT EVIDENCE block is given, use it for this kind: "
    "lines it lists as proportional-font are the prime prose_in_fence "
    "candidates; when it says every line of the fence is monospace in the "
    "source, the fence has NO prose_in_fence (data literals, diagram "
    "captions and column headers of an ASCII figure set in monospace are "
    "code or figure content by the author's choice, whatever they read "
    "like); lines without a confident match are judged as before.\n"
    "- code_as_prose: program text visible in the context lines that "
    "should be inside a code fence is left as unformatted prose.\n"
    "- false_wording_on_comment: wording markup (<ins>, <del>) is applied "
    "to comment markers (// or /*) that are not wording changes.\n"
    "- clean: no boundary defect found for this fence.\n\n"
    "For each finding, provide:\n"
    "- A candidate_quote: a VERBATIM substring from the provided text "
    "(grounding requirement). Keep it SHORT: one line or a small fragment, "
    "at most 200 characters. Avoid embedded double-quotes or backslashes.\n"
    "- The rule_id of the codeblock readability rule violated (C1, C2, C4, "
    "C5, C6, C7, C9) or 'none' for clean.\n\n"
    "You MUST report EXACTLY ONE finding per call. If no boundary defect "
    "exists, report kind='clean'.\n\n"
    "### Output discipline (binding)\n"
    "reasoning at most 40 words. candidate_quote must be verbatim from "
    "the provided text, at most 200 characters. Report only boundary "
    "issues for THIS fence, not content completeness.\n"
)

CODE_BOUNDARY_FENCE_CAP = 6
"""Max fences checked per paper for code boundary. Canonical constant."""

CODE_BOUNDARY_CONTEXT_LINES = 8
"""Lines of surrounding context included before/after each fence slice."""


@dataclass
class _FenceSlice:
    """One fence plus its surrounding context, ready for a single LLM call."""

    index: int
    total: int
    fence_md: str
    locus: str


def _fence_slices(candidate_md: str) -> list[_FenceSlice]:
    """Build per-fence slices with surrounding context lines.

    Each slice contains the fence itself plus ``CODE_BOUNDARY_CONTEXT_LINES``
    lines of context before and after. The number of slices is capped at
    ``CODE_BOUNDARY_FENCE_CAP``.
    """
    spans = code_units_with_spans(candidate_md)
    if not spans:
        return []
    lines = candidate_md.split("\n")
    total = len(spans)
    slices: list[_FenceSlice] = []
    for unit, start, end in spans[:CODE_BOUNDARY_FENCE_CAP]:
        ctx_start = max(0, start - CODE_BOUNDARY_CONTEXT_LINES)
        ctx_end = min(len(lines), end + 1 + CODE_BOUNDARY_CONTEXT_LINES)
        fence_md = "\n".join(lines[ctx_start:ctx_end])
        slices.append(_FenceSlice(
            index=unit.index + 1,
            total=total,
            fence_md=fence_md,
            locus=f"fence:{unit.index + 1}",
        ))
    return slices


async def _run_code_boundary_check(
    agent: AgentBackend,
    pid: str,
    fence_locus: str,
    candidate_md: str,
    risk_context: str,
    *,
    debug_log: list[str] | None = None,
    guard_tag: str | None = None,
    font_evidence: FenceFontEvidence | None = None,
) -> CodeBoundaryJudgment:
    """One scoped code-boundary check on a single fence slice.

    ``font_evidence`` (source font layer per fence line) is appended to the
    user message when available; the prompt declares it authoritative for
    ``prose_in_fence``.
    """
    tag = guard_tag or f"SRC{secrets.token_hex(4)}"
    resolved = resolve_runtime_table_contract(
        service=getattr(agent, "service_name", "") or None
    )
    code_resolved = resolve_runtime_code_contract(
        service=getattr(agent, "service_name", "") or None
    )
    system = (
        inject_code_rubric(
            inject_table_rubric(CODE_BOUNDARY_SYSTEM_PROMPT, resolved),
            code_resolved,
        )
        + "\n"
        + guard_instruction(tag)
    )
    user_msg = (
        f"CANDIDATE MARKDOWN:\n"
        f"{inject_untrusted(candidate_md, tag)}\n\n"
        f"Paper: {pid}\n"
        f"Fence: {fence_locus}\n"
        f"Risk context: {risk_context}\n"
    )
    if font_evidence is not None:
        user_msg += f"{font_evidence.line()}\n"
    return await asyncio.wait_for(
        run_judge_task(
            agent,
            system,
            user_msg,
            CodeBoundaryJudgment,
            label=f"code-boundary-{pid}-{fence_locus}",
            debug_log=debug_log,
            max_tokens=CODE_BOUNDARY_MAX_TOKENS,
        ),
        timeout=PAGE_ESCALATION_TIMEOUT_SECONDS,
    )


@dataclass
class PageScreenEntry:
    """One page's deterministic recall-screen result (no LLM, lane-local)."""

    page: int
    """1-indexed page number, matching the ``[pN]`` quote attribution used
    downstream in escalation results."""
    recall: float | None
    """``content_recall(tomd_md, page_text)``, or ``None`` when skipped."""
    tokens: int
    """``content_tokens`` count of the (dehyphenated) page text."""
    flagged: bool
    skipped: bool

    def to_dict(self) -> dict:
        return {
            "page": self.page,
            "recall": round(self.recall, 4) if self.recall is not None else None,
            "tokens": self.tokens,
            "flagged": self.flagged,
            "skipped": self.skipped,
        }


def screen_pages(cleaned_pages: list[str], tomd_md: str) -> list[PageScreenEntry]:
    """Deterministic per-page recall screen (no LLM, lane-local).

    For each cleaned page: dehyphenate, count content tokens, skip trivial
    pages (< ``PAGE_MIN_TOKENS``), else compute
    ``content_recall(tomd_md, page)`` and flag pages below
    ``PAGE_RECALL_FLOOR``. Computed purely from the source page text and the
    converted markdown; never reads the deterministic whisker sidecar (lane
    independence, ``whisker/CLAUDE.md`` "Two lanes by source kind").
    """
    md_counts = Counter(content_tokens(tomd_md))
    entries: list[PageScreenEntry] = []
    for index, page_text in enumerate(cleaned_pages):
        dehyphenated = _dehyphenate(page_text)
        tokens = len(content_tokens(dehyphenated))
        if tokens < PAGE_MIN_TOKENS:
            entries.append(PageScreenEntry(
                page=index + 1, recall=None, tokens=tokens,
                flagged=False, skipped=True,
            ))
            continue
        recall = content_recall(
            tomd_md, dehyphenated, candidate_counts=md_counts,
        )
        entries.append(PageScreenEntry(
            page=index + 1, recall=recall, tokens=tokens,
            flagged=recall < PAGE_RECALL_FLOOR, skipped=False,
        ))
    return entries


def _candidate_evidence_to_dict(
    evidence: CandidateEvidence,
    *,
    page: int | None = None,
) -> dict:
    result = {
        "axis": evidence.span.axis,
        "quote": evidence.span.quote,
        "source_status": evidence.source_status,
        "candidate_status": evidence.candidate_status,
        "candidate_grounding": evidence.candidate_grounding,
        "candidate_start": evidence.candidate_start,
        "candidate_end": evidence.candidate_end,
    }
    if page is not None:
        result["page"] = page
    return result


def _fold_monolith_verdict(
    judgment: PdfJudgment,
    evidence: list[CandidateEvidence],
    source_ungrounded: int,
) -> str:
    """Recompute a missing-content verdict from two-sided evidence.

    Dropped or ambiguous claims fold to ``review``. A non-pass clears only
    when every asserted missing quote is refuted in the candidate.

    Hardened fail rule (v21): a ``fail`` requires at least one grounded
    ``candidate_not_found`` quote. Without that evidence, the claim is
    unsubstantiated and folds to ``review``. An empty ``missing_content``
    list (independent structure concern) likewise caps at ``review``.
    """
    if not judgment.missing_content:
        # No missing-content claims: independent structure concern.
        # Cap at review; fail requires substantiated missing content.
        if judgment.verdict == "not-llm-readable":
            return "review"
        return judgment.verdict

    statuses = {item.candidate_status for item in evidence}
    if CANDIDATE_NOT_FOUND in statuses:
        # At least one substantiated missing quote. A fail stays, a pass
        # is demoted (model claimed pass despite missing content).
        return "review" if judgment.verdict == "pass" else judgment.verdict
    if source_ungrounded or CANDIDATE_AMBIGUOUS in statuses:
        return "review"
    if (
        len(evidence) == len(judgment.missing_content)
        and statuses == {CANDIDATE_PRESENT}
    ):
        return "pass"
    return "review"


async def _escalate_page(
    agent: AgentBackend,
    pid: str,
    page_num: int,
    page_text: str,
    tomd_md: str,
    *,
    debug_log: list[str] | None = None,
    guard_tag: str | None = None,
) -> PageJudgment:
    """One scoped LLM call re-checking a single flagged page.

    Inherits the full monolith conversion contract (``CONVERSION_CONTRACT``
    in ``unit_judge``) so page-1/TOC/figure traps are cleared by the model
    as sanctioned instead of raising false-flag noise. Bounded by
    ``PAGE_ESCALATION_TIMEOUT_SECONDS`` (a single small call, not the
    whole-paper budget in cli.py).

    ``guard_tag``, when provided, is the paper-level stable tag (prefix-cache
    reuse across this paper's calls); falls back to a fresh random tag.
    The user message leads with the large shared CONVERTED MARKDOWN so the
    ``[system_prompt + guard_instruction][CONVERTED MARKDOWN:...]`` prefix
    is identical across every escalation call for this paper.
    """
    tag = guard_tag or f"SRC{secrets.token_hex(4)}"
    resolved = resolve_runtime_table_contract(
        service=getattr(agent, "service_name", "") or None
    )
    code_resolved = resolve_runtime_code_contract(
        service=getattr(agent, "service_name", "") or None
    )
    system = (
        inject_code_rubric(
            inject_table_rubric(PAGE_JUDGE_SYSTEM_PROMPT, resolved),
            code_resolved,
        )
        + "\n"
        + guard_instruction(tag)
    )
    user_msg = (
        f"CONVERTED MARKDOWN (full document):\n"
        f"{inject_untrusted(tomd_md, tag)}\n\n"
        f"Paper: {pid}\n"
        f"Page: {page_num}\n\n"
        f"RAW PDF TEXT (page {page_num} only):\n"
        f"{inject_untrusted(page_text, tag)}\n"
    )
    return await asyncio.wait_for(
        run_judge_task(
            agent, system, user_msg, PageJudgment,
            label=f"pdf-judge-page-{page_num}",
            debug_log=debug_log,
        ),
        timeout=PAGE_ESCALATION_TIMEOUT_SECONDS,
    )


@dataclass
class PdfJudgeResult:
    """PDF-Text-Lane outcome for one paper."""

    pid: str
    verdict: str
    confidence: float
    reasoning: str
    missing_content: list[str] = field(default_factory=list)
    evidence_verification: list[dict] = field(default_factory=list)
    """Per-claim two-sided provenance (schema v6), including refuted and
    ambiguous missing-content claims. Monolith missing-content verdicts are
    recomputed from these dispositions before other PDF judgments are folded."""
    ungrounded_dropped: int = 0
    text_nid: float = 0.0
    content_recall: float = 0.0
    page_count: int = 0
    judge_model: str = ""
    page_screen: list[PageScreenEntry] = field(default_factory=list)
    """Deterministic per-page recall screen, every page."""
    page_escalations: list[dict] = field(default_factory=list)
    """Scoped LLM escalation results for flagged pages. Empty when no page
    was flagged, or when the flagged-page count exceeded
    ``MAX_PAGE_ESCALATIONS`` (capped without any escalation call)."""
    risk_signals: list[dict] = field(default_factory=list)
    """Lane-local source-vs-candidate risk signals from the router."""
    defect_groups: list[dict] = field(default_factory=list)
    """Verified defect groups from unit-based checks (type, count, examples)."""
    unit_checks: list[dict] = field(default_factory=list)
    """Raw unit check results (unit_id, verdict, defects)."""
    metadata_outline_check: dict = field(default_factory=dict)
    """Mandatory source metadata/front-matter and outline comparison."""
    unit_coverage: dict = field(default_factory=dict)
    """Whether every routed risky unit completed its scoped check."""
    all_pages_requested: bool = False
    """True when the caller requested fail-closed every-page unit checks."""
    unit_selection: dict = field(default_factory=_empty_unit_selection)
    """Audit lists: required/checked/unchecked/failed unit ids (all-pages)."""
    ideal_verification: IdealVerification | None = None
    toc_leak_hits: list[str] = field(default_factory=list)
    """Unpaired TOC-leak headings detected by the mechanical clamp.
    Non-empty forces sidecar ``review`` + structure ``major``."""
    llm_readability: dict = field(default_factory=dict)
    code_boundary: list[dict] = field(default_factory=list)
    """Structured code-boundary judgments from the LLM (per fence)."""
    ideal_pending: bool = False
    """True when an ideal file exists but verification did not land."""

    def to_sidecar_dict(self) -> dict:
        """Tapetum-compatible sidecar dict (fusion reads verdict,
        axis_findings, confidence, status)."""
        mapped = {"pass": "none", "review": "minor", "not-llm-readable": "major"}[
            self.verdict
        ]
        verdict, severity = clamp_toc_leak(
            self.verdict, self.toc_leak_hits, mapped,
        )
        note = f"PDF-text-layer judge: {self.reasoning}"
        if self.missing_content:
            note += f" ({len(self.missing_content)} missing-content quotes)"
        if self.toc_leak_hits:
            tag = toc_leak_tag(self.toc_leak_hits[0])
            if tag not in note:
                note += tag
        findings = [{
            "axis": "structure",
            "verdict": verdict,
            "severity": severity,
            "note": note,
        }]
        dispositions = list(self.evidence_verification)
        if not dispositions and self.missing_content:
            dispositions = [
                {
                    "axis": "structure",
                    "quote": quote,
                    "source_status": "unknown",
                    "candidate_status": CANDIDATE_NOT_FOUND,
                    "candidate_grounding": None,
                    "candidate_start": None,
                    "candidate_end": None,
                }
                for quote in self.missing_content
            ]
        dispositions = sorted(
            dispositions,
            key=lambda item: (
                item.get("page") or 0,
                item.get("quote", ""),
                item.get("candidate_status", ""),
            ),
        )
        missing_evidence = [
            item for item in dispositions
            if item.get("candidate_status") == CANDIDATE_NOT_FOUND
        ]
        evidence_summary = {
            CANDIDATE_PRESENT: sum(
                item.get("candidate_status") == CANDIDATE_PRESENT
                for item in dispositions
            ),
            CANDIDATE_NOT_FOUND: len(missing_evidence),
            CANDIDATE_AMBIGUOUS: sum(
                item.get("candidate_status") == CANDIDATE_AMBIGUOUS
                for item in dispositions
            ),
            "source_ungrounded": self.ungrounded_dropped + sum(
                item.get("candidate_status") == "source_ungrounded"
                for item in dispositions
            ),
        }
        result = {
            "pid": self.pid,
            "status": "ok",
            "source_kind": "pdf",
            "lane": "pdf_textlayer_judge",
            "whisker_verdict": "",
            "suggested_verdict": verdict,
            "confidence": round(self.confidence, 4),
            "escalated": False,
            "escalation_signals": [],
            "tier1_model": self.judge_model,
            "tier2_model": None,
            "axis_findings": findings,
            "grounded_evidence": [
                {
                    **item,
                    "reason": (
                        "present in PDF text layer; candidate text not located"
                    ),
                }
                for item in missing_evidence
            ],
            "evidence_dispositions": dispositions,
            "evidence_summary": evidence_summary,
            "ungrounded_dropped": self.ungrounded_dropped,
            "primary_concern": (
                self.missing_content[0][:160]
                if self.missing_content else ""
            ),
            "reasoning": self.reasoning,
            "advisory": True,
            "textlayer_diff": {
                "text_nid": round(self.text_nid, 4),
                "content_recall": round(self.content_recall, 4),
                "page_count": self.page_count,
            },
            "page_count": self.page_count,
            "page_screen": [entry.to_dict() for entry in self.page_screen],
            "page_escalations": self.page_escalations,
            "risk_signals": self.risk_signals,
            "defect_groups": self.defect_groups,
            "unit_checks": self.unit_checks,
            "metadata_outline_check": self.metadata_outline_check,
            "unit_coverage": self.unit_coverage,
            "all_pages_requested": self.all_pages_requested,
            "unit_selection": self.unit_selection,
            "schema_version": PDF_SIDECAR_SCHEMA_VERSION,
        }
        if self.ideal_verification is not None:
            result["ideal_verification"] = self.ideal_verification.model_dump()
        if self.ideal_pending:
            result["ideal_pending"] = True
        if self.llm_readability:
            result["llm_readability"] = self.llm_readability
        if self.code_boundary:
            result["code_boundary"] = self.code_boundary
        return result


class PdfLaneError(Exception):
    """Raised when the PDF-Text-Lane cannot complete for a paper."""


_TAB_REF_RE = re.compile(r"\[tab:", re.IGNORECASE)
_TABLE_CAPTION_RE = re.compile(
    r"^\s*Table\s+\d+\b", re.IGNORECASE | re.MULTILINE,
)


def real_table_pages(page_units: list) -> set[int]:
    """Return page numbers that carry a genuine table marker.

    A page qualifies if any of:
    - A ``caption_lines`` entry starts with "Table" (from ``_CAPTION_RE``).
    - The page text contains a ``[tab:…]`` LaTeX cross-reference.
    - The page text contains a standalone ``Table N`` caption line.

    Pages without such markers are considered phantom-grid false positives
    from ``find_tables(strategy="text")`` and must not emit
    ``table_orphan`` / ``table_corruption`` signals.
    """
    result: set[int] = set()
    for unit in page_units:
        if any(
            line.lower().startswith("table")
            for line in unit.caption_lines
        ):
            result.add(unit.page)
        elif _TAB_REF_RE.search(unit.text):
            result.add(unit.page)
        elif _TABLE_CAPTION_RE.search(unit.text):
            result.add(unit.page)
    return result


_UNGRIDDED_ORPHAN_MARKER_FALLBACK = "table marker"
"""Detail fallback when a real-table page has no recoverable caption or ``[tab:]`` token."""


def _table_evidence_marker(unit: PageUnit) -> str:
    """Return the caption line or ``[tab:…]`` token that marked this page real."""
    for line in unit.caption_lines:
        if line.lower().startswith("table"):
            return line.strip()
    tab_prefix = _TAB_REF_RE.search(unit.text)
    if tab_prefix is not None:
        close = unit.text.find("]", tab_prefix.start())
        if close != -1:
            return unit.text[tab_prefix.start() : close + 1]
    for line in unit.text.splitlines():
        if _TABLE_CAPTION_RE.search(line):
            return line.strip()
    return _UNGRIDDED_ORPHAN_MARKER_FALLBACK


def _orphan_signals_for_ungridded_pages(
    real_table_pages: set[int],
    page_units: list[PageUnit],
    table_compare_result: TableCompareResult,
    existing_signals: list[RiskSignal] | None = None,
) -> list[RiskSignal]:
    """Emit ``table_orphan`` for real-table pages with no PyMuPDF grid match.

    The existing grid-compare loop only orphans a page when a match exists
    and ``candidate_header`` is None. Borderless spec tables (P3400R3
    ``[tab:lex.key]``) produce no match at all; those pages must still
    hard-flag. When ``grid_unreliable`` is True, ``matches`` is empty and
    every real-table page is covered.
    """
    prior = existing_signals if existing_signals is not None else []
    already_flagged = {
        signal.unit_id
        for signal in prior
        if signal.signal_type in ("table_orphan", "table_corruption")
    }
    gridded_pages = {match.page for match in table_compare_result.matches}
    units_by_page = {unit.page: unit for unit in page_units}
    signals: list[RiskSignal] = []
    for page in sorted(real_table_pages):
        if page in gridded_pages:
            continue
        unit_id = f"page:{page}"
        if unit_id in already_flagged:
            continue
        unit = units_by_page.get(page)
        marker = (
            _table_evidence_marker(unit)
            if unit is not None
            else _UNGRIDDED_ORPHAN_MARKER_FALLBACK
        )
        signals.append(RiskSignal(
            unit_id=unit_id,
            signal_type="table_orphan",
            severity="critical",
            detail=(
                f"source table {marker} has no extracted grid "
                f"on this page"
            ),
        ))
    return signals


async def judge_pdf_extraction(
    pid: str,
    backend,
    agent: AgentBackend,
    *,
    debug_log: list[str] | None = None,
    all_pages: bool = False,
    exhaustive_units: bool = False,
    code_boundary: bool = True,
    enable_page_escalations: bool = True,
    progress: dict | None = None,
    guard_tag: str | None = None,
) -> PdfJudgeResult:
    """Run the PDF-Text-Lane for one paper.

    1. Extract the PDF text layer (PyMuPDF, independent of tomd)
    2. Compute deterministic metrics (supplementary, not the verdict) and
       the deterministic per-page recall screen (``screen_pages``)
    3. One LLM judge call: raw text layer + converted markdown, both
       guard-wrapped, structured output (D6/D10 via run_judge_task,
       whisker-local dispatch without the global run_task gate)
    4. Ground missing-content quotes against the text layer, then classify
       every source-grounded claim against the candidate Markdown
    5. Scoped LLM escalation on pages the screen flagged (0-``MAX_PAGE_
       ESCALATIONS``): confirmed misses cap the verdict at review with
       page-attributed quotes; sanctioned flags keep the monolith verdict.
    6. Source-aware unit checks: routed risky pages by default, or every
       physical page when ``all_pages=True`` (fail-closed coverage).

    Metadata short-circuit: when the mandatory metadata/outline check (step
    6's prerequisite) does not pass, the verdict is already capped at
    ``review``/``fail`` and steps 5-6 cannot change it further, so they are
    skipped (44.6% of LLM calls in the verified baseline). ``all_pages`` and
    ``exhaustive_units`` bypass the short-circuit for audit-mode fidelity.
    Code-boundary checks (step 7) run only when ``code_boundary`` is true
    and the metadata short-circuit did not fire. Page-escalation LLM calls
    run only when ``enable_page_escalations`` is true. The default fleet
    leaves both off; ``--inspect`` / ``--all-pages`` / ``--exhaustive-units``
    turn them on. Fusion never reads ``code_boundary``.

    ``guard_tag``, when provided, is the fleet-wide constant tag (see
    ``constants.GUARD_TAG``) reused across the monolith call, page
    escalations, and unit checks for this paper, so the shared system-prompt
    prefix stays byte-identical across a paper's ~6 serial calls and the
    vLLM pod's automatic prefix cache can reuse it. When absent, each call
    falls back to a fresh random tag (unchanged behavior).

    Fidelity policy: any failure -> PdfLaneError (no partial results).
    """
    source_path = backend.get_source_path(pid)
    if not str(source_path).lower().endswith(".pdf"):
        raise PdfLaneError(
            f"{pid}: PDF-Text-Lane requires a PDF source, got "
            f"{source_path.suffix}"
        )

    _set_progress(progress, phase="extract")
    try:
        pages = await asyncio.to_thread(extract_textlayer, source_path)
    except TextLayerError as exc:
        raise PdfLaneError(f"{pid}: text-layer extraction failed: {exc}") from exc

    page_count = len(pages)
    _set_progress(
        progress,
        page_count=page_count,
        checked_unit_ids=[],
        required_unit_ids=[],
    )

    cleaned_pages = clean_pages(pages)
    pdf_text = normalize_textlayer(pages)
    # Same pre-LLM filter as the text lane: inline binary payloads are
    # replaced with sanctioned markers (the on-disk paper.md is untouched).
    raw_tomd_md = backend.get_paper_md(pid)
    tomd_md, _ = strip_binary_payloads(raw_tomd_md)

    # Context guard: no silent truncation.
    total_chars = len(pdf_text) + len(tomd_md)
    est_tokens = (
        total_chars / agent.chars_per_token * agent.token_multiplier
        if agent.chars_per_token else 0
    )
    budget = agent.max_context_window * CONTEXT_SAFETY_MARGIN
    if est_tokens and est_tokens > budget:
        raise PdfLaneError(
            f"{pid}: estimated {est_tokens:.0f} tokens exceeds "
            f"{budget:.0f} context budget; refusing to truncate"
        )

    nid = text_nid(normalized_text(pdf_text), normalized_text(tomd_md))
    recall = content_recall(tomd_md, pdf_text)

    # Deterministic per-page recall screen: computed lane-locally from the
    # cleaned source pages + the converted markdown, independent of the
    # monolith call below and never reading the deterministic whisker
    # sidecar (research/research/per-page-judging/SYNTHESIS.md).
    _set_progress(progress, phase="page_screen")
    page_screen = await asyncio.to_thread(screen_pages, cleaned_pages, tomd_md)

    tag = guard_tag or f"SRC{secrets.token_hex(4)}"
    resolved = resolve_runtime_table_contract(
        service=getattr(agent, "service_name", "") or None
    )
    code_resolved = resolve_runtime_code_contract(
        service=getattr(agent, "service_name", "") or None
    )
    system = (
        inject_code_rubric(
            inject_table_rubric(JUDGE_SYSTEM_PROMPT, resolved),
            code_resolved,
        )
        + "\n"
        + guard_instruction(tag)
    )
    user_msg = (
        f"Paper: {pid}\n\n"
        f"RAW PDF TEXT:\n{inject_untrusted(pdf_text, tag)}\n\n"
        f"CONVERTED MARKDOWN:\n{inject_untrusted(tomd_md, tag)}\n"
    )

    _set_progress(progress, phase="monolith")
    try:
        # Whisker-local dispatch: no global run_task gate; the CLI's
        # paper-level --concurrency semaphore bounds in-flight requests.
        judgment: PdfJudgment = await asyncio.wait_for(
            run_judge_task(
                agent,
                system,
                user_msg,
                PdfJudgment,
                label=f"pdf-judge-{pid}",
                debug_log=debug_log,
            ),
            timeout=MONOLITH_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        raise PdfLaneError(f"{pid}: judge call failed: {exc}") from exc

    try:
        page_units: list[PageUnit] = await asyncio.to_thread(
            extract_page_units, source_path,
        )
    except TextLayerError as exc:
        raise PdfLaneError(
            f"{pid}: page-unit extraction failed: {exc}"
        ) from exc
    if not page_units:
        raise PdfLaneError(f"{pid}: page-unit extraction returned no units")
    source_outline = [
        f"page {unit.page}, font {size:.2f}: {text}"
        for unit in page_units
        for text, size in unit.heading_candidates
    ]
    source_metadata = page_units[0].text
    _set_progress(progress, phase="metadata")

    # Deterministic metadata comparison (shadow or replacement). Shadow mode
    # runs both and logs agreement; replacement mode is not yet the default
    # (see TAPETUM_DET_METADATA in metadata_compare.py's module docstring).
    _use_det_metadata = os.environ.get("TAPETUM_DET_METADATA") == "1"
    _shadow_metadata = os.environ.get("TAPETUM_METADATA_SHADOW") == "1"

    det_metadata_check: MetadataOutlineCheck | None = None
    if _use_det_metadata or _shadow_metadata:
        det_metadata_check = compare_metadata_outline(
            pid, source_metadata, source_outline, raw_tomd_md,
            source_kind="pdf",
        )

    if _use_det_metadata:
        metadata_check = det_metadata_check
    else:
        try:
            metadata_check: MetadataOutlineCheck = await run_metadata_outline_check(
                pid,
                source_metadata,
                source_outline,
                raw_tomd_md,
                agent,
                debug_log=debug_log,
                guard_tag=guard_tag,
            )
        except Exception as exc:
            raise PdfLaneError(
                f"{pid}: metadata/outline check failed: {exc}"
            ) from exc

    if _shadow_metadata and det_metadata_check is not None:
        logger.info(
            "%s: metadata shadow - det=%s llm=%s (match=%s)",
            pid, det_metadata_check.verdict, metadata_check.verdict,
            det_metadata_check.verdict == metadata_check.verdict,
        )

    # Ground missing-content quotes against the text layer. A quote the
    # judge cannot have read in the PDF text is dropped (anti-hallucination).
    spans = [
        EvidenceSpan(axis="structure", quote=q, reason="missing from markdown")
        for q in judgment.missing_content[:MAX_MISSING_QUOTES]
    ]
    grounded, dropped = ground_spans(spans, pdf_text)
    monolith_evidence = classify_candidate_evidence(grounded, raw_tomd_md)
    evidence_verification = [
        _candidate_evidence_to_dict(evidence)
        for evidence in monolith_evidence
    ]
    grounded_quotes = [
        evidence.span.quote
        for evidence in monolith_evidence
        if evidence.candidate_status == CANDIDATE_NOT_FOUND
    ]

    annotated_reasoning = _annotate_reasoning(judgment.reasoning, raw_tomd_md)

    verdict = _fold_monolith_verdict(judgment, monolith_evidence, dropped)
    # PDF outline guard: a metadata fail from an outline with at most one
    # entry cannot credibly claim "major sections are missing" because the
    # source outline itself is too sparse to support the claim. Demote to
    # review (never towards pass). Title/doc identity mismatches are kept.
    effective_metadata_verdict = metadata_check.verdict
    if (
        metadata_check.verdict == "not-llm-readable"
        and len(source_outline) <= 1
        and metadata_check.title_matches
        and metadata_check.document_number_matches
    ):
        effective_metadata_verdict = "review"
        logger.info(
            "%s: metadata fail demoted to review (source_outline=%d entries)",
            pid, len(source_outline),
        )
    if effective_metadata_verdict == "not-llm-readable":
        verdict = "not-llm-readable"
    elif effective_metadata_verdict == "review" and verdict == "pass":
        verdict = "review"

    # Metadata short-circuit: when the metadata/outline check already caps
    # the verdict, page escalations and unit checks cannot change it further.
    # Audit modes (--all-pages, --exhaustive-units, --inspect) are exempt.
    # Code-boundary checks also skip under the short-circuit; the default
    # fleet additionally leaves ``code_boundary`` off.
    metadata_short_circuited = False
    if (
        metadata_check.verdict != "pass"
        and not all_pages
        and not exhaustive_units
    ):
        metadata_short_circuited = True
        _set_progress(progress, phase="metadata_short_circuit")
        logger.info(
            "%s: metadata short-circuit (verdict=%s); skipping "
            "page escalations and unit checks",
            pid, metadata_check.verdict,
        )

    # Self-reported confidence is anti-calibrated; replace with derived signal.
    # Zero confidence is a mechanical anomaly (model bug), not a calibration
    # signal, so it still demotes.
    if verdict == "pass" and judgment.confidence == 0.0:
        verdict = "review"
    if verdict == "pass" and recall < PDF_JUDGE_RECALL_FLOOR:
        logger.info(
            "%s: pdf-judge pass demoted to review (content_recall=%.4f < %.2f)",
            pid, recall, PDF_JUDGE_RECALL_FLOOR,
        )
        verdict = "review"
    if verdict == "pass" and nid < PDF_JUDGE_NID_FLOOR:
        logger.info(
            "%s: pdf-judge pass demoted to review (text_nid=%.4f < %.2f)",
            pid, nid, PDF_JUDGE_NID_FLOOR,
        )
        verdict = "review"

    # Scoped LLM escalation on pages the deterministic screen flagged, and
    # source-aware unit checks below. Both are skipped entirely under the
    # metadata short-circuit (see above); these defaults hold for that path.
    flagged_entries: list[PageScreenEntry] = []
    page_escalations: list[dict] = []
    risk_signals: list[RiskSignal] = []
    defect_groups: list[dict] = []
    unit_checks_out: list[dict] = []
    unit_selection = _empty_unit_selection()
    # Vacuous complete default is for routed mode only (fleet unchanged).
    # All-pages always overwrites from the unit run below.
    unit_coverage: dict = {
        "coverage_complete": True,
        "checked_unit_ids": [],
        "unchecked_unit_ids": [],
        "failed_unit_ids": [],
        "mode": "all_pages" if all_pages else "routed",
    }

    table_compare_result = None

    if not metadata_short_circuited:
        # Scoped LLM escalation on pages the deterministic screen flagged.
        # The screen decides WHERE to look; the LLM only confirms/sanctions
        # that one page's specific gap, never re-judges the whole document.
        flagged_entries = [entry for entry in page_screen if entry.flagged]
        if len(flagged_entries) > MAX_PAGE_ESCALATIONS:
            _set_progress(progress, phase="escalations")
            logger.warning(
                "%s: %d pages flagged by the recall screen exceeds "
                "MAX_PAGE_ESCALATIONS=%d; capping verdict at review without "
                "escalation calls",
                pid, len(flagged_entries), MAX_PAGE_ESCALATIONS,
            )
            if verdict == "pass":
                verdict = "review"
            annotated_reasoning += (
                f" [page-screen: {len(flagged_entries)} pages flagged, "
                f"exceeds escalation cap of {MAX_PAGE_ESCALATIONS}, no "
                f"escalation calls made]"
            )
        elif enable_page_escalations:
            _set_progress(progress, phase="escalations")
            for entry in flagged_entries:
                page_text = _dehyphenate(cleaned_pages[entry.page - 1])
                try:
                    page_judgment = await _escalate_page(
                        agent, pid, entry.page, page_text, tomd_md,
                        debug_log=debug_log,
                        guard_tag=guard_tag,
                    )
                except Exception as exc:
                    raise PdfLaneError(
                        f"{pid}: page-{entry.page} escalation call failed: {exc}"
                    ) from exc

                page_spans = [
                    EvidenceSpan(
                        axis="structure",
                        quote=quote,
                        reason="missing from markdown",
                    )
                    for quote in (
                        page_judgment.missing_content[:MAX_MISSING_QUOTES]
                        if page_judgment.content_missing
                        else []
                    )
                ]
                page_source_grounded, page_dropped = ground_page_spans(
                    page_spans,
                    page_text,
                )
                dropped += page_dropped
                page_quotes = [item.span.quote for item in page_source_grounded]
                page_evidence = classify_candidate_evidence(
                    page_source_grounded,
                    raw_tomd_md,
                )
                page_dispositions = [
                    _candidate_evidence_to_dict(evidence, page=entry.page)
                    for evidence in page_evidence
                ]
                evidence_verification.extend(page_dispositions)
                candidate_not_found_quotes = [
                    evidence.span.quote
                    for evidence in page_evidence
                    if evidence.candidate_status == CANDIDATE_NOT_FOUND
                ]
                confirmed = (
                    page_judgment.content_missing
                    and bool(candidate_not_found_quotes)
                )
                uncertain = (
                    page_judgment.content_missing
                    and (
                        page_dropped > 0
                        or any(
                            evidence.candidate_status == CANDIDATE_AMBIGUOUS
                            for evidence in page_evidence
                        )
                    )
                )
                page_escalations.append({
                    "page": entry.page,
                    "content_missing": confirmed,
                    "grounded_quotes": page_quotes,
                    "confidence": round(page_judgment.confidence, 4),
                    "candidate_not_found_quotes": candidate_not_found_quotes,
                    "evidence_dispositions": page_dispositions,
                })
                logger.info(
                    "%s: page-%d escalation -> content_missing=%s confirmed=%s "
                    "quotes=%d conf=%.2f",
                    pid, entry.page, page_judgment.content_missing, confirmed,
                    len(candidate_not_found_quotes), page_judgment.confidence,
                )
                if confirmed or uncertain:
                    if verdict == "pass":
                        verdict = "review"
                if confirmed:
                    grounded_quotes.extend(
                        f"[p{entry.page}] {quote}"
                        for quote in candidate_not_found_quotes
                    )

        # -- Source-aware unit checks (v6): extract page units, route risk
        # signals, run scoped LLM checks on flagged units (or every page when
        # all_pages). The monolith call above remains the primary first pass;
        # unit checks refine it.
        risk_signals = await asyncio.to_thread(
            route_pdf_units, page_units, raw_tomd_md,
        )

        # -- Grid compare: detect orphan source tables and cell mismatches.
        # Gate: only pages with a real table marker (caption "Table N" or
        # "[tab:" reference) emit orphan/corruption signals.  PyMuPDF
        # find_tables(strategy="text") hallucinates grids on justified
        # prose; ungated signals would veto 75+ pages on spec papers.
        _real_table_pages = real_table_pages(page_units)

        try:
            if not _real_table_pages:
                table_compare_result = None
            else:
                table_compare_result = await asyncio.to_thread(
                    compare_pdf_tables, source_path, raw_tomd_md,
                )
            if table_compare_result is not None and table_compare_result.cell_diffs:
                for diff in table_compare_result.cell_diffs:
                    if diff.page not in _real_table_pages:
                        continue
                    unit_id = f"page:{diff.page}"
                    existing = any(
                        s.unit_id == unit_id
                        and s.signal_type == "table_corruption"
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
            if table_compare_result is not None and table_compare_result.matches:
                for match in table_compare_result.matches:
                    if match.candidate_header is None:
                        if match.page not in _real_table_pages:
                            continue
                        unit_id = f"page:{match.page}"
                        existing = any(
                            s.unit_id == unit_id
                            and s.signal_type == "table_orphan"
                            for s in risk_signals
                        )
                        if not existing:
                            src_cols = len(match.source_header)
                            risk_signals.append(RiskSignal(
                                unit_id=unit_id,
                                signal_type="table_orphan",
                                severity="critical",
                                detail=(
                                    f"{src_cols}-col source table "
                                    f"(header: {', '.join(match.source_header[:4])})"
                                    f" has no candidate table on this page"
                                ),
                            ))
            if table_compare_result is not None:
                risk_signals.extend(
                    _orphan_signals_for_ungridded_pages(
                        _real_table_pages,
                        page_units,
                        table_compare_result,
                        risk_signals,
                    )
                )
        except Exception as exc:
            logger.warning(
                "%s: table comparison failed: %s", pid, exc,
            )

        unit_text_map: dict[str, str] = {
            f"page:{unit.page}": unit.text for unit in page_units
        }
        required_unit_ids: list[str] = []
        unit_result: UnitJudgeResult | None = None

        if all_pages:
            required_unit_ids = [
                f"page:{unit.page}"
                for unit in sorted(page_units, key=lambda u: u.page)
            ]
            _set_progress(
                progress,
                phase="unit_checks",
                required_unit_ids=list(required_unit_ids),
                checked_unit_ids=[],
                page_count=page_count,
            )
            unit_result = await run_unit_checks(
                pid,
                raw_tomd_md,
                agent,
                risk_signals=risk_signals,
                unit_text_map=unit_text_map,
                debug_log=debug_log,
                exhaustive=True,
                required_unit_ids=required_unit_ids,
                guard_tag=guard_tag,
            )
        elif risk_signals:
            _set_progress(progress, phase="unit_checks", page_count=page_count)
            unit_result = await run_unit_checks(
                pid,
                raw_tomd_md,
                agent,
                risk_signals=risk_signals,
                unit_text_map=unit_text_map,
                debug_log=debug_log,
                exhaustive=exhaustive_units,
                guard_tag=guard_tag,
            )

        if unit_result is not None:
            defect_groups = unit_result.defect_groups
            unit_checks_out = unit_result.unit_results
            unit_coverage = {
                "coverage_complete": unit_result.coverage_complete,
                "checked_unit_ids": list(unit_result.checked_unit_ids),
                "unchecked_unit_ids": list(unit_result.unchecked_unit_ids),
                "failed_unit_ids": list(unit_result.failed_unit_ids),
                "unroutable_unit_ids": list(unit_result.unroutable_unit_ids),
                "evidence_summary": unit_result.evidence_summary,
                "mode": "all_pages" if all_pages else "routed",
            }
            evidence_verification.extend(
                {
                    "axis": "structure",
                    "unit_id": unit_check.get("unit_id", ""),
                    "quote": disposition.get("quote", ""),
                    "source_status": disposition.get(
                        "source_status",
                        (
                            "unknown"
                            if disposition.get("source_grounded")
                            else "source_ungrounded"
                        ),
                    ),
                    "candidate_status": disposition.get(
                        "candidate_status", "source_ungrounded"
                    ),
                    "candidate_grounding": None,
                    "candidate_start": None,
                    "candidate_end": None,
                }
                for unit_check in unit_result.unit_results
                for disposition in unit_check.get("evidence_dispositions", [])
            )
            if unit_result.verdict == "review" and verdict == "pass":
                verdict = "review"
                annotated_reasoning += (
                    f" [unit-checks: {len(defect_groups)} defect group(s) "
                    f"from {len(risk_signals)} risk signal(s)]"
                )

        if all_pages:
            # Fail-closed vs physical page_count: pages missing from page_units
            # (extractor drop) are coverage gaps even when required was built
            # only from the units that were present.
            present_pages = {unit.page for unit in page_units}
            missing_page_ids = [
                f"page:{page_num}"
                for page_num in range(1, page_count + 1)
                if page_num not in present_pages
            ]
            checked_ids = list(unit_coverage.get("checked_unit_ids", []))
            unchecked_ids = list(unit_coverage.get("unchecked_unit_ids", []))
            failed_ids = list(unit_coverage.get("failed_unit_ids", []))
            for missing_id in missing_page_ids:
                if missing_id not in unchecked_ids:
                    unchecked_ids.append(missing_id)
            unchecked_ids = sorted(
                set(unchecked_ids),
                key=lambda uid: (
                    int(uid.split(":", 1)[1])
                    if ":" in uid and uid.split(":", 1)[1].isdigit()
                    else 999999
                ),
            )
            required_set = set(required_unit_ids)
            page_units_set = {f"page:{unit.page}" for unit in page_units}
            coverage_complete = (
                set(checked_ids) == required_set
                and required_set == page_units_set
                and not unchecked_ids
                and not failed_ids
                and not missing_page_ids
            )
            unit_coverage["checked_unit_ids"] = checked_ids
            unit_coverage["unchecked_unit_ids"] = unchecked_ids
            unit_coverage["failed_unit_ids"] = failed_ids
            unit_coverage["coverage_complete"] = coverage_complete
            unit_coverage["mode"] = "all_pages"
            unit_selection = {
                "required": list(required_unit_ids),
                "checked": list(checked_ids),
                "unchecked": list(unchecked_ids),
                "failed": list(failed_ids),
            }
            _set_progress(
                progress,
                phase="unit_checks",
                required_unit_ids=list(required_unit_ids),
                checked_unit_ids=list(checked_ids),
                page_count=page_count,
            )
            if (
                not coverage_complete
                or unchecked_ids
                or failed_ids
            ) and verdict == "pass":
                verdict = "review"
                annotated_reasoning += (
                    " [all-pages: coverage incomplete]"
                )
        else:
            _set_progress(
                progress,
                checked_unit_ids=list(unit_coverage.get("checked_unit_ids", [])),
                required_unit_ids=[],
                page_count=page_count,
            )

    if metadata_short_circuited:
        unit_coverage = {
            "coverage_complete": True,
            "checked_unit_ids": [],
            "unchecked_unit_ids": [],
            "failed_unit_ids": [],
            "unroutable_unit_ids": [],
            "mode": "metadata_short_circuit",
        }
        unit_selection = _empty_unit_selection()

    # -- Code-boundary checks: one LLM call per fence slice (not per page).
    # On the default fleet, CB is gated behind the metadata short-circuit:
    # 0 [code-boundary:] demotions were observed on the 09-01 fleet (1593
    # calls, 900+ past fence 6), so the default fleet does not pay for them.
    # Audit modes (--all-pages, --exhaustive-units / --inspect) and explicit
    # code_boundary=True bypass the gate for full coverage.
    _run_cb = code_boundary and not metadata_short_circuited
    code_boundary_results: list[dict] = []
    cb_slices = _fence_slices(raw_tomd_md) if _run_cb else []
    # Source font layer per fence line: appended to the judge's message and
    # used to clamp prose_in_fence on monospace-set lines (data literals,
    # ASCII-diagram captions the model reads as prose). {} = abstain.
    cb_font_evidence: dict[str, FenceFontEvidence] = {}
    if _run_cb:
        _set_progress(progress, phase="code_boundary")
    if cb_slices:
        cb_font_evidence = await asyncio.to_thread(
            fence_font_evidence, source_path, raw_tomd_md,
        )
    for sl in cb_slices:
        cb_context = f"fence {sl.index} of {sl.total}"
        sl_evidence = cb_font_evidence.get(sl.locus)
        try:
            cb_result = await _run_code_boundary_check(
                agent, pid, sl.locus, sl.fence_md,
                cb_context,
                debug_log=debug_log,
                guard_tag=guard_tag,
                font_evidence=sl_evidence,
            )
            cb_result, cb_clamped = clamp_source_monospace(cb_result, sl_evidence)
            if cb_clamped:
                logger.info(
                    "%s: code-boundary %s: %d prose_in_fence finding(s) "
                    "clamped to clean (monospace in source)",
                    pid, sl.locus, cb_clamped,
                )
            cb_dict = cb_result.model_dump()
            if cb_clamped:
                cb_dict["source_monospace_clamped"] = cb_clamped
            code_boundary_results.append(cb_dict)
            non_clean = [
                f for f in cb_result.findings if f.kind != "clean"
            ]
            if non_clean and verdict == "pass":
                verdict = "review"
                annotated_reasoning += (
                    f" [code-boundary: {len(non_clean)} defect(s) on "
                    f"{sl.locus}]"
                )
            logger.info(
                "%s: code-boundary %s -> %s (%d findings, "
                "%d non-clean)",
                pid, sl.locus, cb_result.verdict,
                len(cb_result.findings), len(non_clean),
            )
        except TimeoutError as cb_exc:
            raise PdfLaneError(
                f"{pid}: code-boundary {sl.locus} failed: {cb_exc}"
            ) from cb_exc
        except Exception as cb_exc:
            logger.warning(
                "%s: code-boundary %s failed (%s: %s); marking cb_error "
                "and continuing remaining fences",
                pid, sl.locus, type(cb_exc).__name__, cb_exc,
            )
            code_boundary_results.append({
                "locus": sl.locus,
                "status": "cb_error",
                "error": type(cb_exc).__name__,
                "detail": str(cb_exc)[:200],
            })

    toc_hits = detect_unpaired_toc_leak(raw_tomd_md)
    toc_leak_hit_texts = [h.heading for h in toc_hits]
    verdict, _ = clamp_toc_leak(verdict, toc_hits)
    if toc_hits:
        annotated_reasoning += toc_leak_tag(toc_hits[0].heading)
        logger.info(
            "%s: toc-leak clamp fired (%d hit(s)), verdict=%s",
            pid, len(toc_leak_hit_texts), verdict,
        )

    logger.info(
        "%s: pdf-judge verdict=%s conf=%.2f missing=%d dropped=%d "
        "(nid=%.4f recall=%.4f) screen_flagged=%d risk_signals=%d "
        "all_pages=%s",
        pid, verdict, judgment.confidence,
        len(grounded_quotes), dropped, nid, recall,
        len(flagged_entries), len(risk_signals), all_pages,
    )

    # Readability probes (table dumps, code probes) are synchronous httpx
    # calls. They run in a worker thread so they cannot block the event loop
    # that serves the other in-flight papers; timed as their own phase so
    # the trace shows their share.
    _set_progress(progress, phase="readability")
    llm_readability = await asyncio.to_thread(
        build_llm_readability_block,
        tomd_md,
        pid=pid,
        service=getattr(agent, "service_name", "") or None,
        table_compare=(
            {
                "total_source_tables": table_compare_result.total_source_tables,
                "total_candidate_tables": table_compare_result.total_candidate_tables,
                "matched_tables": table_compare_result.matched_tables,
                "cell_diff_count": len(table_compare_result.cell_diffs),
                "grid_unreliable": table_compare_result.grid_unreliable,
            }
            if table_compare_result is not None
            else None
        ),
        textlayer_pages=pages,
        source_path=source_path,
    )

    _set_progress(progress, phase="done")
    return PdfJudgeResult(
        pid=pid,
        verdict=verdict,
        confidence=judgment.confidence,
        reasoning=annotated_reasoning,
        missing_content=grounded_quotes,
        evidence_verification=evidence_verification,
        ungrounded_dropped=dropped,
        text_nid=nid,
        content_recall=recall,
        page_count=page_count,
        judge_model=agent.service_name or "judge",
        page_screen=page_screen,
        page_escalations=page_escalations,
        risk_signals=[
            {"unit_id": s.unit_id, "signal_type": s.signal_type,
             "severity": s.severity, "detail": s.detail}
            for s in risk_signals
        ],
        defect_groups=defect_groups,
        unit_checks=unit_checks_out,
        metadata_outline_check=metadata_check.model_dump(),
        unit_coverage=unit_coverage,
        all_pages_requested=all_pages,
        unit_selection=unit_selection,
        toc_leak_hits=toc_leak_hit_texts,
        code_boundary=code_boundary_results,
        llm_readability=llm_readability,
    )
