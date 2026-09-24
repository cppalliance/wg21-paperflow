#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Source-aware unit-based fidelity checks (v6).

Orchestrates: risk routing -> unit LLM checks -> defect aggregation.
Runs AFTER the monolith PDF judge, only when risk signals warrant it.
Library-pure: returns data, never persists.

Contract: the caller provides:
- ``risk_signals``: a list of ``RiskSignal`` dataclass instances from the router
- ``unit_text_map``: a dict mapping ``unit_id`` -> source text for that unit
  (e.g. page text or section text). The caller builds this from PageUnit/SectionUnit.
- ``candidate_md``: the full unfiltered candidate markdown
- ``agent``: the LLM backend for scoped calls
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import secrets
import tomllib
from dataclasses import replace
from pathlib import Path

from pipeline import AgentBackend, PipelinePrompt
from pipeline.tools import guard_instruction, inject_untrusted

from whisker.det.llm_readability.code_validate import (
    code_units_from_markdown,
    evaluate_code,
)
from whisker.det.llm_readability.contract import CONSTRUCT_CODEBLOCKS, render_llm_rubric
from whisker.det.llm_readability.models import (
    METHOD_DETERMINISTIC,
    METHOD_SOURCE_COMPARE,
    ResolvedContract,
)
from whisker.det.llm_readability.profile import (
    ProfileError,
    resolve_contract,
    resolved_core_only,
    service_model_identity,
)
from whisker.det.llm_readability.report import report_to_dict
from whisker.det.llm_readability.validate import (
    default_registry,
    evaluate,
    table_units_from_markdown,
)
from whisker.llm.chunking import chunk_markdown, make_table_atomic_check
from whisker.llm.code_probes import (
    code_probes_to_dict,
    run_code_probes,
)
from whisker.llm.constants import (
    FLEET_UNIT_CHECK_BASE,
    FLEET_UNIT_CHECK_CEILING,
    FLEET_UNIT_CHECK_SIGNAL_COUNT_THRESHOLD,
    MAX_PAPER_MD_CHARS,
    MAX_UNIT_CHECKS,
    SIGNAL_CLASS_QUOTA,
    UNIT_CHECK_TIMEOUT_SECONDS,
)
from whisker.llm.grounding import (
    CANDIDATE_AMBIGUOUS,
    CANDIDATE_NOT_FOUND,
    CANDIDATE_PRESENT,
    GROUND_EXACT,
    GROUND_FUZZY,
    GroundedSpan,
    classify_candidate_evidence,
    ground_spans,
    semantic_parity_holds,
)
from whisker.llm.judge_task import run_judge_task
from whisker.llm.models import (
    UNIT_CLEAR_CONFIDENCE_FLOOR,
    UNIT_CLEAR_MAX_TOKENS,
    UNIT_DEFECTS_MAX_TOKENS,
    EvidenceSpan,
    MetadataOutlineCheck,
    UnitCheck,
    UnitCheckClear,
    UnitCheckDefects,
    to_unit_check,
)
from whisker.llm.source_router import RiskSignal
from whisker.llm.table_probes import run_unit_dumps, unit_dumps_to_dict

logger = logging.getLogger(__name__)

__all__ = [
    "CODE_CONTRACT_SENTINEL",
    "CONVERSION_CONTRACT",
    "FULL_AUDIT_NO_SIGNAL_CONTEXT",
    "METADATA_CHECK_SYSTEM_PROMPT",
    "TABLE_CONTRACT_SENTINEL",
    "UNIT_CHECK_SYSTEM_PROMPT",
    "UnitJudgeResult",
    "build_llm_readability_block",
    "fleet_max_unit_checks",
    "hydrate_pipeline_prompt",
    "inject_code_rubric",
    "inject_table_rubric",
    "resolve_runtime_code_contract",
    "resolve_runtime_table_contract",
    "run_metadata_outline_check",
    "run_unit_checks",
]

# Environment variable that toggles the dynamic per-paper unit-check quota
# (fleet_max_unit_checks) on fleet runs. "1" (default) enables it; any other
# value falls back to the static MAX_UNIT_CHECKS cap. Audit modes (exhaustive,
# required units) always bypass this switch entirely.
DYNAMIC_QUOTA_ENV_VAR = "TAPETUM_DYNAMIC_QUOTA"

# Full conversion contract shared with pdf_judge prompts. Lives here so
# pdf_judge can import it without a cycle (pdf_judge already imports
# unit_judge; the reverse would create one).
CONVERSION_CONTRACT = (
    "The converter operates under a fixed contract. The following are "
    "CORRECT conversion behavior, never defects and never missing content:\n"
    "- The PDF's title block (document number, date, intent, audience, "
    "reply-to lines) is converted into the YAML front-matter block at the "
    "top of the markdown (keys: title, document, date, intent, audience, "
    "reply-to). If those values appear in the YAML block, they are NOT "
    "missing.\n"
    "- The table of contents is DELIBERATELY REMOVED by the converter; the "
    "body headings replace it. A missing TOC is sanctioned, never a "
    "defect. The INVERSE is a defect: TOC content that REMAINS in the "
    "markdown body is leaked TOC. Signatures: a standalone 'Contents' / "
    "'Table of Contents' label or heading in the body, a heading "
    "duplicated with a trailing page number (e.g. '## 1. Introduction 3' "
    "alongside '## 1. Introduction'), or an unpaired heading that carries "
    "a section number, title, bracketed stable name, and trailing page "
    "number (e.g. '## 5 Lexical conventions [lex] 10' with no matching "
    "'## 5 Lexical conventions [lex]' in the body). Report leaked TOC in "
    "your reasoning and cap the verdict at review (or fail if the leak is "
    "extensive). Severity is at least major.\n"
    "- Page numbers, running headers, and running footers are page "
    "furniture and are deliberately dropped.\n"
    "- Text rendered INSIDE a figure or image (a diagram, chart, or "
    "scanned block) is legitimately imaged; the converter is not expected "
    "to transcribe it. Do not flag it as missing.\n"
    "- HTML comments of the form <!-- tomd:... --> or <!-- tapetum:... --> "
    "are sanctioned converter disclosures, not corruption. This includes "
    "<!-- tomd:lossy-table -->. <!-- tomd:mixed-table --> stays sanctioned "
    "only when the source is HTML, not when the source is a PDF. A PDF "
    "source whose markdown contains a raw HTML table is a table defect "
    "(raw_html_table), severity at least minor, verdict at least review. "
    "The source format is given with the paper.\n"
    "- Wording markup is the DELIVERABLE of wording papers: inline "
    "<ins>/<del> tags mark proposed standard-text edits that were colored "
    "green/red (or struck through) in the PDF. Text inside these tags "
    "IS present content; never count it as deleted, hidden, or corrupted. "
    "Inside fenced code blocks, `<ins>` and `<del>` stay literal and "
    "unescaped on the tokens they mark. "
    "The raw text layer does not carry color, so you CANNOT verify whether "
    "the markup matches the PDF's colors. If the markup placement looks "
    "suspicious (e.g. ordinary prose wrapped in `<del>`), say so "
    "and cap your verdict at review, never fail on markup placement "
    "alone.\n"
    "- Prose paragraphs are unwrapped to one line and words are "
    "dehyphenated across line breaks; differing line breaks are not "
    "defects.\n\n"
)


def source_format_from_path(path: object | None) -> str:
    """pdf, html, or unknown from a sibling source file.

    A missing path, a path that is not a file, or any other suffix is
    unknown. The suffix is taken from the path the caller already has.
    """
    if path is None:
        return "unknown"
    is_file = getattr(path, "is_file", None)
    if not callable(is_file):
        return "unknown"
    try:
        exists = bool(is_file())
    except OSError:
        return "unknown"
    if not exists:
        return "unknown"
    suffix = str(getattr(path, "suffix", "")).lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in (".html", ".htm"):
        return "html"
    return "unknown"


def source_format_line(source_format: str) -> str:
    """One user-message line. Only pdf, html, or unknown are emitted."""
    if source_format not in ("pdf", "html", "unknown"):
        source_format = "unknown"
    return f"source format: {source_format}\n"


FULL_AUDIT_NO_SIGNAL_CONTEXT = (
    "full audit: no specific risk signal; this unit is checked as part of "
    "an exhaustive all-pages review"
)
"""Risk-context line for a required unit that has no router signal."""

METADATA_CHECK_SYSTEM_PROMPT = (
    "You are a metadata and outline validator. Compare the source metadata "
    "and source heading outline with the candidate Markdown front matter and "
    "heading outline. Judge field values, missing sections, and heading-level "
    "drift. Cosmetic source formatting is not a defect. Ignore source "
    "table-of-contents entries, page numbers, running headers, and running "
    "footers as sanctioned source chrome; the candidate is expected to omit "
    "that chrome while preserving the corresponding body headings.\n\n"
    "date_matches: set to true when either side has no date (a missing date is "
    "not a mismatch). Only set to false when both source and candidate contain "
    "a date and the dates differ.\n\n"
    "Verdict:\n"
    "- pass: metadata and outline faithfully match.\n"
    "- review: a metadata field or heading level needs human review.\n"
    "- fail: title/document identity is wrong or major sections are missing.\n\n"
    "reasoning at most 40 words. Report only concrete mismatches.\n"
)

UNIT_CHECK_SYSTEM_PROMPT = (
    "You are a conversion-fidelity unit checker. You receive:\n"
    "1. SOURCE TEXT: one bounded region (a page or section) from the "
    "source document.\n"
    "2. CANDIDATE MARKDOWN: the full converted document.\n"
    "3. RISK SIGNAL: why this unit was flagged for checking.\n\n"
    "Your task: determine whether the candidate faithfully preserves the "
    "source content for THIS UNIT ONLY. Report specific defects.\n\n"
    "Content from this unit counts as present if it appears ANYWHERE in "
    "the candidate markdown, in any order; document-wide reordering is a "
    "separate check you are not performing here.\n\n"
    + CONVERSION_CONTRACT +
    "Defect types: qualifier_omission (missing keywords like constexpr), "
    "heading_drift (wrong heading level), content_omission (text/figures "
    "missing), table_corruption (table structure broken, cells shifted or "
    "content changed), table_flattened (source contains a tabular structure "
    "but candidate renders it as an ATX heading followed by prose lines "
    "instead of a pipe table; the table is lost), "
    "cell_content_wrong (specific table cell has different "
    "text than source), label_not_stripped (structural label like section "
    "number retained in heading), punctuation_loss "
    "(periods/operators dropped), entity_artifact (HTML entities in output), "
    "toc_leak (TOC content in body), code_loss (code block missing/broken).\n\n"
    "For each defect group, provide an `affected_count`: the total number "
    "of instances of that specific defect in the unit, not just the quoted "
    "example. This count must be verifiable against the source text.\n\n"
    "Verdict:\n"
    "- pass: unit content faithfully preserved.\n"
    "- review: minor defects a human should check.\n"
    "- fail: substantial content missing or corrupted in this unit.\n\n"
    "### Output discipline (binding)\n"
    "reasoning at most 40 words. source_quote must be verbatim from the "
    "SOURCE TEXT. affected_count must be exact.\n"
)

TABLE_CONTRACT_SENTINEL = "<!-- whisker:table-readability-contract -->"
CODE_CONTRACT_SENTINEL = "<!-- whisker:codeblock-readability-contract -->"

_C10_PROBE_SYSTEM = (
    "You are a document comprehension assistant. "
    "Treat each fenced block as one listing. "
    "Line numbers are 1-based inside the fence body and do not count "
    "the opening or closing fence markers. "
    "Answer with the identifier quoted exactly, or NOT FOUND. "
    "Be precise and concise."
)


def resolve_runtime_table_contract(
    *,
    service: str | None = None,
    model: str | None = None,
) -> ResolvedContract:
    """Resolve the table contract by MODEL identity, never by slot name.

    An unknown model or missing SERVICES.toml entry returns the universal
    core alone so certification stays fail-closed (``profile_missing``).
    """
    try:
        if model:
            return resolve_contract(model=model)
        if service:
            identity = service_model_identity(service)
            return resolve_contract(model=identity)
    except ProfileError:
        return resolved_core_only()
    return resolved_core_only()


def resolve_runtime_code_contract(
    *,
    service: str | None = None,
    model: str | None = None,
) -> ResolvedContract:
    """Resolve the codeblock contract by MODEL identity, never by slot name."""
    try:
        if model:
            return resolve_contract(model=model, construct=CONSTRUCT_CODEBLOCKS)
        if service:
            identity = service_model_identity(service)
            return resolve_contract(model=identity, construct=CONSTRUCT_CODEBLOCKS)
    except ProfileError:
        return resolved_core_only(construct=CONSTRUCT_CODEBLOCKS)
    return resolved_core_only(construct=CONSTRUCT_CODEBLOCKS)


def inject_table_rubric(text: str, resolved: ResolvedContract) -> str:
    """Insert the rendered table TOML rubric as trusted system material.

    Replaces ``TABLE_CONTRACT_SENTINEL`` when present. Otherwise appends.
    Already-hydrated text (core id plus hash) is left unchanged so a second
    inject cannot duplicate the contract.
    """
    if not text:
        return render_llm_rubric(resolved)
    core_id = resolved.core.id
    core_hash = resolved.core.hash
    if core_id in text and core_hash in text:
        return text
    rubric = render_llm_rubric(resolved)
    if TABLE_CONTRACT_SENTINEL in text:
        return text.replace(TABLE_CONTRACT_SENTINEL, rubric)
    return text.rstrip() + "\n\n" + rubric


def inject_code_rubric(text: str, resolved: ResolvedContract) -> str:
    """Insert the rendered codeblock TOML rubric as trusted system material.

    Replaces ``CODE_CONTRACT_SENTINEL`` when present. Otherwise appends.
    Already-hydrated text (core id plus hash) is left unchanged so a second
    inject cannot duplicate the contract.
    """
    if not text:
        return render_llm_rubric(resolved)
    core_id = resolved.core.id
    core_hash = resolved.core.hash
    if core_id in text and core_hash in text:
        return text
    rubric = render_llm_rubric(resolved)
    if CODE_CONTRACT_SENTINEL in text:
        return text.replace(CODE_CONTRACT_SENTINEL, rubric)
    return text.rstrip() + "\n\n" + rubric


def hydrate_pipeline_prompt(
    prompt: PipelinePrompt,
    resolved: ResolvedContract,
    *,
    code_resolved: ResolvedContract | None = None,
) -> PipelinePrompt:
    """Materialize a frozen PipelinePrompt with rendered rubrics.

    When ``code_resolved`` is given, the codeblock rubric is injected
    alongside the table rubric.
    """
    def _inject(text: str) -> str:
        result = inject_table_rubric(text, resolved)
        if code_resolved is not None:
            result = inject_code_rubric(result, code_resolved)
        return result

    new_sections = {
        key: _inject(value)
        for key, value in prompt.sections.items()
    }
    new_steps = tuple(
        replace(step, system_prompt=_inject(step.system_prompt))
        if step.system_prompt
        else step
        for step in prompt.steps
    )
    return replace(
        prompt,
        system_prompt=_inject(prompt.system_prompt),
        sections=new_sections,
        steps=new_steps,
    )


def _find_services_toml() -> Path | None:
    """Walk up from cwd to find SERVICES.toml (same source as the judge)."""
    here = Path.cwd()
    for parent in [here, *here.parents]:
        candidate = parent / "SERVICES.toml"
        if candidate.is_file():
            return candidate
    return None


def _pod_credentials(service: str | None) -> tuple[str, str, str] | None:
    """Return (base_url, api_key, model) for a SERVICES.toml entry, or None."""
    if not service:
        return None
    path = _find_services_toml()
    if path is None:
        return None
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    svc = data.get("services", {}).get(service)
    if not isinstance(svc, dict):
        return None
    base_url = str(svc.get("base_url", "") or "")
    api_key_raw = str(svc.get("api_key", "") or "")
    if api_key_raw.startswith("$"):
        api_key = os.environ.get(api_key_raw[1:], "")
    else:
        api_key = api_key_raw
    model_name = str(svc.get("model", "") or "")
    if not base_url or not api_key:
        return None
    return base_url, api_key, model_name


def build_llm_readability_block(
    md: str,
    *,
    pid: str = "",
    service: str | None = None,
    model: str | None = None,
    table_compare: dict | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    textlayer_pages: list[str] | None = None,
    source_path: Path | None = None,
) -> dict:
    """Evaluate candidate tables and codeblocks plus available evidence.

    The advisory judge still scores every conversion axis. This block is
    the instrumented sidecar: tables and codeblocks get contract reports
    and live probes. Certification stays separate from ``run_gates`` /
    ``WhiskerResult``. Probes are sibling evidence, never a ``METHOD_LLM``
    stamp.
    """
    resolved = resolve_runtime_table_contract(service=service, model=model)
    code_resolved = resolve_runtime_code_contract(service=service, model=model)
    chunks, partial = chunk_markdown(md, MAX_PAPER_MD_CHARS)
    registry = default_registry()
    registry["table_atomic_chunk"] = make_table_atomic_check(
        chunks, max_chars=MAX_PAPER_MD_CHARS
    )
    methods = [METHOD_DETERMINISTIC]
    compare = table_compare or {}
    if compare:
        methods.append(METHOD_SOURCE_COMPARE)
    units = table_units_from_markdown(md)
    report = evaluate(
        resolved,
        units,
        methods_executed=methods,
        source_available=bool(compare),
        chunking_evaluated=True,
        registry=registry,
    )
    payload = report_to_dict(report)
    payload["chunking"] = {
        "chunk_count": len(chunks),
        "partial": partial,
    }
    if compare:
        payload["source_compare"] = {
            "grid_unreliable": compare.get("grid_unreliable"),
            "matched_tables": compare.get("matched_tables"),
            "cell_diff_count": compare.get("cell_diff_count"),
            "total_source_tables": compare.get("total_source_tables"),
            "total_candidate_tables": compare.get("total_candidate_tables"),
        }
    code_units = code_units_from_markdown(md)
    code_report = evaluate_code(
        code_resolved,
        code_units,
        methods_executed=(METHOD_DETERMINISTIC,),
        source_available=bool(compare),
        markdown_text=md,
    )
    payload["code_readability"] = report_to_dict(code_report)
    dump_url = base_url
    dump_key = api_key
    dump_model = model or ""
    if not dump_url or not dump_key:
        resolved_creds = _pod_credentials(service)
        if resolved_creds is not None:
            dump_url, dump_key, toml_model = resolved_creds
            if not dump_model:
                dump_model = toml_model
    if dump_url and dump_key:
        try:
            dumps = run_unit_dumps(
                pid,
                units,
                base_url=dump_url,
                api_key=dump_key,
                model=dump_model or "deepseek-v4-pro",
                md_lines=md.splitlines(),
                textlayer_pages=textlayer_pages,
                source_path=source_path,
            )
            payload["unit_dumps"] = unit_dumps_to_dict(dumps)
        except Exception:
            # Evidence lane: a dump failure must not fail the advisory judge.
            logger.exception("unit dumps failed; leaving readability block without dumps")
        try:
            probes = run_code_probes(
                pid,
                code_units,
                base_url=dump_url,
                api_key=dump_key,
                model=dump_model or "deepseek-v4-pro",
                system_prompt=inject_code_rubric(_C10_PROBE_SYSTEM, code_resolved),
            )
            payload["code_probes"] = code_probes_to_dict(probes)
        except Exception:
            logger.exception("code probes failed; leaving readability block without probes")
    return payload


def _unit_id_sort_key(unit_id: str) -> tuple[int, str]:
    """Extract numeric page/section number for natural sort order.

    'page:13' -> (13, 'page:13'), 'section:0' -> (0, 'section:0')
    """
    parts = unit_id.split(":", 1)
    if len(parts) == 2:
        try:
            return (int(parts[1]), unit_id)
        except ValueError:
            pass
    return (999999, unit_id)


def fleet_max_unit_checks(
    routable_risky_ids: list[str],
    signals_by_unit: dict[str, list[RiskSignal]],
    *,
    base: int = FLEET_UNIT_CHECK_BASE,
    ceiling: int = FLEET_UNIT_CHECK_CEILING,
) -> int:
    """Compute per-paper unit-check cap based on signal profile.

    Bumps above base for table presence, missing code, high-severity
    signals, and high signal count. Capped at ceiling. Used in fleet
    mode only; audit modes (--inspect, --exhaustive-units, --all-pages)
    bypass.
    """
    all_signals = [s for ss in signals_by_unit.values() for s in ss]
    bump = 0
    if any(s.severity in {"critical", "high"} for s in all_signals):
        bump += 1
    if any(s.signal_type == "table_presence" for s in all_signals):
        bump += 1
    if any(s.signal_type == "missing_code" for s in all_signals):
        bump += 1
    if len(routable_risky_ids) > FLEET_UNIT_CHECK_SIGNAL_COUNT_THRESHOLD:
        bump += 1
    return min(ceiling, base + bump)


def _select_units_with_quotas(
    signals_by_unit: dict[str, list[RiskSignal]],
    risky_unit_ids: list[str],
    max_checks: int,
) -> list[str]:
    """Select units ensuring each signal_type gets at least one slot.

    1. Collect one representative unit per signal_type (first in sort order).
    2. Fill remaining slots from the sorted list, skipping already-selected.
    3. Cap at max_checks.
    """
    # Phase 1: guarantee SIGNAL_CLASS_QUOTA slots per signal class
    selected: list[str] = []
    selected_set: set[str] = set()
    class_counts: dict[str, int] = {}

    for unit_id in risky_unit_ids:
        if len(selected) >= max_checks:
            break
        unit_signals = signals_by_unit.get(unit_id, [])
        under_quota = [
            s.signal_type for s in unit_signals
            if class_counts.get(s.signal_type, 0) < SIGNAL_CLASS_QUOTA
        ]
        if under_quota and unit_id not in selected_set:
            selected.append(unit_id)
            selected_set.add(unit_id)
            for signal_type in {s.signal_type for s in unit_signals}:
                class_counts[signal_type] = class_counts.get(signal_type, 0) + 1

    # Phase 2: fill remaining slots in sort order
    for unit_id in risky_unit_ids:
        if len(selected) >= max_checks:
            break
        if unit_id not in selected_set:
            selected.append(unit_id)
            selected_set.add(unit_id)

    return selected


_FRONT_MATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*(?:\n|\Z)", re.DOTALL)
_MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$", re.MULTILINE)


def _candidate_structure_packet(candidate_md: str) -> tuple[str, list[str]]:
    """Extract bounded candidate front matter and ATX heading outline."""
    front_match = _FRONT_MATTER_RE.match(candidate_md)
    front_matter = front_match.group(0).strip() if front_match else "(missing)"
    headings = [
        f"h{len(match.group(1))}: {match.group(2).strip()}"
        for match in _MARKDOWN_HEADING_RE.finditer(candidate_md)
    ]
    return front_matter, headings


# Date-like patterns: YYYY-MM-DD or loose month/day/year combos.
_DATE_RE = re.compile(
    r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b"       # 2026-01-15, 2026/1/15
    r"|\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b"       # 01-15-2026
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b"        # January 15, 2026
    r"|\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"[a-z]*\.?\s+\d{4}\b",                   # 15 January 2026
    re.IGNORECASE,
)


def _stabilise_date_matches(
    result: MetadataOutlineCheck,
    source_metadata: str,
    candidate_front_matter: str,
) -> MetadataOutlineCheck:
    """Correct ``date_matches=False`` when either side lacks a date.

    Matches the deterministic rule in ``metadata_compare._date_matches``:
    a missing date on either side cannot be a mismatch signal. When the
    correction makes ``date_matches`` the only false field, the verdict
    is re-evaluated through the existing ``pass_requires_no_mismatch``
    validator (which rejects pass with a mismatch, but does not prevent
    promoting a review whose only mismatch was removed).
    """
    source_has_date = bool(_DATE_RE.search(source_metadata))
    candidate_has_date = bool(_DATE_RE.search(candidate_front_matter))
    if source_has_date and candidate_has_date:
        return result
    # One or both sides have no date: correct to True.
    corrected = result.model_copy(update={"date_matches": True})
    # If that was the only mismatch, the verdict may lift to pass.
    has_other_mismatch = (
        not corrected.title_matches
        or not corrected.document_number_matches
        or bool(corrected.heading_drift)
        or bool(corrected.missing_sections)
    )
    if not has_other_mismatch and corrected.verdict != "pass":
        corrected = corrected.model_copy(update={"verdict": "pass"})
    return corrected


async def run_metadata_outline_check(
    pid: str,
    source_metadata: str,
    source_outline: list[str],
    candidate_md: str,
    agent: AgentBackend,
    *,
    debug_log: list[str] | None = None,
    guard_tag: str | None = None,
) -> MetadataOutlineCheck:
    """Run the mandatory source metadata/outline comparison.

    This is a one-off call per paper (not repeated), so its user-message
    layout is not prefix-cache sensitive; ``guard_tag`` still lets it share
    the paper-level tag for the system-prompt prefix.
    """
    candidate_front_matter, candidate_headings = _candidate_structure_packet(
        candidate_md
    )
    tag = guard_tag or f"SRC{secrets.token_hex(4)}"
    system = METADATA_CHECK_SYSTEM_PROMPT + "\n" + guard_instruction(tag)
    user_msg = (
        f"Paper: {pid}\n\n"
        "SOURCE METADATA:\n"
        f"{inject_untrusted(source_metadata, tag)}\n\n"
        "SOURCE OUTLINE:\n"
        f"{inject_untrusted(chr(10).join(source_outline) or '(none)', tag)}\n\n"
        "CANDIDATE FRONT MATTER:\n"
        f"{inject_untrusted(candidate_front_matter, tag)}\n\n"
        "CANDIDATE HEADINGS:\n"
        f"{inject_untrusted(chr(10).join(candidate_headings) or '(none)', tag)}\n"
    )
    result = await asyncio.wait_for(
        run_judge_task(
            agent,
            system,
            user_msg,
            MetadataOutlineCheck,
            label=f"metadata-outline-{pid}",
            debug_log=debug_log,
        ),
        timeout=UNIT_CHECK_TIMEOUT_SECONDS,
    )
    # Deterministic post-check: date_matches follows the same rule as
    # metadata_compare._date_matches: a missing date on either side is
    # not a mismatch. The LLM sometimes flags date_matches=False when
    # one side has no date. Correct it here so the field is stable.
    if hasattr(result, "date_matches") and not result.date_matches:
        result = _stabilise_date_matches(
            result, source_metadata, candidate_front_matter,
        )
    return result


class UnitJudgeResult:
    """Aggregated result from source-aware unit checks."""

    def __init__(
        self,
        risk_signals: list[dict],
        unit_results: list[dict],
        defect_groups: list[dict],
        verdict: str,
        *,
        coverage_complete: bool = True,
        checked_unit_ids: list[str] | None = None,
        unchecked_unit_ids: list[str] | None = None,
        failed_unit_ids: list[str] | None = None,
        evidence_summary: dict[str, int] | None = None,
        unit_selection: list[dict] | None = None,
        required_unit_ids: list[str] | None = None,
        unroutable_unit_ids: list[str] | None = None,
    ) -> None:
        self.risk_signals = risk_signals
        self.unit_results = unit_results
        self.defect_groups = defect_groups
        self.verdict = verdict
        self.coverage_complete = coverage_complete
        self.checked_unit_ids = checked_unit_ids or []
        self.unchecked_unit_ids = unchecked_unit_ids or []
        self.failed_unit_ids = failed_unit_ids or []
        self.evidence_summary = evidence_summary or {
            CANDIDATE_PRESENT: 0,
            CANDIDATE_NOT_FOUND: 0,
            CANDIDATE_AMBIGUOUS: 0,
            "source_ungrounded": 0,
        }
        self.unit_selection = unit_selection or []
        self.required_unit_ids = list(required_unit_ids or [])
        self.unroutable_unit_ids = list(unroutable_unit_ids or [])

    def has_verified_defects(self) -> bool:
        return bool(self.defect_groups)


async def run_unit_checks(
    pid: str,
    candidate_md: str,
    agent: AgentBackend,
    *,
    risk_signals: list[RiskSignal],
    unit_text_map: dict[str, str],
    debug_log: list[str] | None = None,
    exhaustive: bool = False,
    required_unit_ids: list[str] | None = None,
    guard_tag: str | None = None,
    source_format: str = "unknown",
) -> UnitJudgeResult | None:
    """Run source-aware unit checks if risk signals warrant it.

    Returns None if no risk signals were provided and no required units
    were requested (the monolith result stands alone). Returns a
    UnitJudgeResult with defect groups otherwise.

    When *exhaustive* is True (e.g. golden-PR review via --inspect), ALL
    routed units are checked instead of capping at the quota. The pod
    is billed hourly, not per token, so the marginal cost is wall-clock only.

    Outside exhaustive mode, the cap is ``fleet_max_unit_checks`` (a dynamic
    per-paper quota derived from the routed signal profile) unless the
    ``TAPETUM_DYNAMIC_QUOTA`` environment variable is set to anything other
    than ``"1"``, in which case the static ``MAX_UNIT_CHECKS`` is used
    instead.

    When *required_unit_ids* is non-empty (all-pages review), every listed
    unit is checked exactly once even with an empty risk list. Neither cap
    ever applies to required units; routed-only units still respect the
    existing cap/exhaustive logic. Iteration order is numeric page order via
    ``_unit_id_sort_key``.

    ``guard_tag``, when provided, is the fleet-wide constant tag (see
    ``constants.GUARD_TAG``) passed through to every ``_check_one_unit``
    call so the shared system-prompt prefix (and the CANDIDATE MARKDOWN
    lead-in) is byte-identical across all unit checks for this paper,
    enabling vLLM automatic-prefix-cache reuse.
    """
    required_list = list(required_unit_ids or [])
    has_required = bool(required_list)
    if not risk_signals and not has_required:
        return None

    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sorted_signals = sorted(
        risk_signals,
        key=lambda s: (
            severity_rank.get(s.severity, 3),
            _unit_id_sort_key(s.unit_id),
            s.signal_type,
            s.detail,
        ),
    )
    signals_by_unit: dict[str, list[RiskSignal]] = {}
    for signal in sorted_signals:
        signals_by_unit.setdefault(signal.unit_id, []).append(signal)
    risky_unit_ids = list(signals_by_unit)
    routable_risky_ids = [
        uid for uid in risky_unit_ids if unit_text_map.get(uid, "")
    ]
    unroutable_unit_ids = [
        uid for uid in risky_unit_ids if not unit_text_map.get(uid, "")
    ]
    for unit_id in unroutable_unit_ids:
        logger.warning("%s: unit %s has no source packet", pid, unit_id)
    if exhaustive:
        max_checks = len(routable_risky_ids)
    elif os.environ.get(DYNAMIC_QUOTA_ENV_VAR, "1") == "1":
        max_checks = fleet_max_unit_checks(routable_risky_ids, signals_by_unit)
    else:
        max_checks = MAX_UNIT_CHECKS
    selected_unit_ids = _select_units_with_quotas(
        signals_by_unit, routable_risky_ids, max_checks,
    )
    quota_selected = set(selected_unit_ids)
    unchecked_unit_ids = [
        uid for uid in routable_risky_ids if uid not in quota_selected
    ]

    required_set = set(required_list)
    if has_required:
        # Cap never applies to required units; promote quota-skipped required
        # units back into the selected set and drop them from unchecked.
        selected_set = set(selected_unit_ids) | required_set
        unchecked_unit_ids = [
            uid for uid in unchecked_unit_ids if uid not in required_set
        ]
        selected_unit_ids = sorted(selected_set, key=_unit_id_sort_key)

    if unchecked_unit_ids and not exhaustive and not has_required:
        logger.info(
            "%s: unit-quota overflow (%d unchecked); skipping unit LLM, "
            "coverage_complete=false",
            pid, len(unchecked_unit_ids),
        )
        overflow_unchecked = sorted(
            set(unchecked_unit_ids) | set(selected_unit_ids)
        )
        overflow_selected = set(selected_unit_ids)
        unit_selection = []
        for uid in risky_unit_ids:
            unit_selection.append({
                "unit_id": uid,
                "status": "unchecked",
                "signals": [
                    _signal_to_dict(s) for s in signals_by_unit.get(uid, [])
                ],
                "reason": (
                    "quota_overflow"
                    if uid in overflow_selected or uid in unchecked_unit_ids
                    else "priority"
                ),
            })
        return UnitJudgeResult(
            risk_signals=[_signal_to_dict(s) for s in sorted_signals],
            unit_results=[],
            defect_groups=[],
            verdict="review",
            coverage_complete=False,
            checked_unit_ids=[],
            unchecked_unit_ids=overflow_unchecked,
            failed_unit_ids=[],
            unit_selection=unit_selection,
            required_unit_ids=required_list,
            unroutable_unit_ids=unroutable_unit_ids,
        )

    failed_unit_ids: list[str] = []
    checked_unit_ids: list[str] = []

    unit_results: list[dict] = []

    for unit_id in selected_unit_ids:
        unit_signals = signals_by_unit.get(unit_id, [])
        source_text = unit_text_map.get(unit_id, "")
        if not source_text:
            if unit_id in required_set:
                logger.warning(
                    "%s: unit %s has no source packet", pid, unit_id,
                )
                unchecked_unit_ids.append(unit_id)
            continue

        if unit_signals:
            signal_detail = "; ".join(
                signal.detail for signal in unit_signals
            )
        else:
            signal_detail = FULL_AUDIT_NO_SIGNAL_CONTEXT

        signal_types = {s.signal_type for s in unit_signals}

        try:
            result = await _check_one_unit(
                pid,
                unit_id,
                source_text,
                candidate_md,
                signal_detail,
                agent,
                debug_log=debug_log,
                guard_tag=guard_tag,
                signal_types=signal_types,
                source_format=source_format,
            )
            unit_results.append(result)
            checked_unit_ids.append(unit_id)
        except Exception as exc:
            logger.warning(
                "%s: unit check %s failed: %s", pid, unit_id, exc,
            )
            failed_unit_ids.append(unit_id)

    unit_results = verify_unit_evidence(unit_results, unit_text_map, candidate_md)

    # -- Table page veto: cap pass → review when table signals contradict.
    _table_veto_units = {
        s.unit_id
        for s in risk_signals
        if s.signal_type in ("table_corruption", "table_orphan")
    }
    for result in unit_results:
        if (
            result.get("verdict") == "pass"
            and result.get("unit_id") in _table_veto_units
        ):
            result["verdict"] = "review"
            reason = result.get("reasoning", "")
            result["reasoning"] = (
                reason + " [table-veto: grid mismatch or orphan source table]"
            )
            logger.info(
                "%s: table-veto capped %s pass → review",
                pid, result.get("unit_id"),
            )

    evidence_summary = {
        CANDIDATE_PRESENT: 0,
        CANDIDATE_NOT_FOUND: 0,
        CANDIDATE_AMBIGUOUS: 0,
        "source_ungrounded": 0,
    }
    verified_defects: list[dict] = []
    for result in unit_results:
        for defect in result.get("defects", []):
            disposition = defect.get("evidence_disposition", {})
            status = disposition.get("candidate_status", "source_ungrounded")
            evidence_summary[status] = evidence_summary.get(status, 0) + 1
            if (
                status == CANDIDATE_NOT_FOUND
                and disposition.get("source_status") == GROUND_EXACT
            ):
                verified_defects.append(defect)

    defect_groups = _aggregate_defects(verified_defects)

    # Mechanical count verification: enriches each defect group with
    # source/candidate counts for countable keywords
    defect_groups = verify_defect_counts(defect_groups, unit_text_map, candidate_md)

    defect_groups = [
        group
        for group in defect_groups
        if not (
            group.get("count_verification", {}).get("count_status") == "verified"
            and group["count_verification"].get("verified_delta") == 0
        )
    ]
    routable_coverage = set(routable_risky_ids)
    coverage_units = routable_coverage | required_set
    coverage_complete = (
        set(checked_unit_ids) == coverage_units
        and not unchecked_unit_ids
        and not failed_unit_ids
    )
    evidence_uncertain = (
        evidence_summary[CANDIDATE_AMBIGUOUS] > 0
        or evidence_summary["source_ungrounded"] > 0
        or any(
            disposition.get("source_status") not in (None, GROUND_EXACT)
            for result in unit_results
            for disposition in result.get("evidence_dispositions", [])
        )
    )
    verdict = (
        "review"
        if defect_groups or not coverage_complete or evidence_uncertain
        else "pass"
    )

    checked_set = set(checked_unit_ids)
    failed_set = set(failed_unit_ids)
    unroutable_set = set(unroutable_unit_ids)
    unit_selection = []
    for uid in risky_unit_ids:
        if uid in unroutable_set:
            unit_selection.append({
                "unit_id": uid,
                "status": "unroutable",
                "signals": [
                    _signal_to_dict(s) for s in signals_by_unit.get(uid, [])
                ],
                "reason": "no_source_packet",
            })
            continue
        unit_selection.append({
            "unit_id": uid,
            "status": (
                "checked" if uid in checked_set
                else ("failed" if uid in failed_set else "unchecked")
            ),
            "signals": [
                _signal_to_dict(s) for s in signals_by_unit.get(uid, [])
            ],
            "reason": (
                "exhaustive" if exhaustive
                else ("quota" if uid in quota_selected else "priority")
            ),
        })

    return UnitJudgeResult(
        risk_signals=[_signal_to_dict(s) for s in sorted_signals],
        unit_results=unit_results,
        defect_groups=defect_groups,
        verdict=verdict,
        coverage_complete=coverage_complete,
        checked_unit_ids=checked_unit_ids,
        unchecked_unit_ids=sorted(set(unchecked_unit_ids)),
        failed_unit_ids=failed_unit_ids,
        evidence_summary=evidence_summary,
        unit_selection=unit_selection,
        required_unit_ids=required_list,
        unroutable_unit_ids=unroutable_unit_ids,
    )


def _signal_to_dict(signal: RiskSignal | dict) -> dict:
    """Convert a RiskSignal to a serializable dict."""
    if isinstance(signal, RiskSignal):
        return {
            "unit_id": signal.unit_id,
            "signal_type": signal.signal_type,
            "severity": signal.severity,
            "detail": signal.detail,
        }
    return dict(signal)


_COUNTABLE_KEYWORDS = frozenset({
    "constexpr", "template", "noexcept", "concept", "requires",
    "override", "virtual", "explicit", "inline", "static",
    "volatile", "mutable", "extern", "register",
})
"""Keywords where the LLM affected_count can be mechanically verified."""

_WORD_RE_UNIT = re.compile(r"\b\w+\b", re.UNICODE)


def _mechanical_count(keyword: str, text: str) -> int:
    """Count keyword occurrences in text (case-sensitive word boundary)."""
    return sum(1 for m in _WORD_RE_UNIT.finditer(text) if m.group() == keyword)


def _aggregate_defects(defects: list[dict]) -> list[dict]:
    """Group defects by type and, when countable, by omitted keyword."""
    groups: dict[tuple[str, str | None], dict] = {}
    for defect in defects:
        dtype = defect.get("defect_type", "unknown")
        keywords = (
            _extract_keywords_from_examples([defect.get("source_quote", "")])
            if dtype == "qualifier_omission"
            else []
        )
        for keyword in keywords or [None]:
            group_key = (dtype, keyword)
            if group_key not in groups:
                groups[group_key] = {
                    "defect_type": dtype,
                    "affected_count": 0,
                    "severity": defect.get("severity", "medium"),
                    "source_unit": defect.get("source_unit", ""),
                    "source_quote": defect.get("source_quote", ""),
                    "examples": [],
                }
                if keyword is not None:
                    groups[group_key]["count_verification"] = {
                        "keyword": keyword
                    }
            disposition = defect.get("evidence_disposition", {})
            if (
                disposition.get("source_status") == GROUND_EXACT
                and disposition.get("candidate_status") == CANDIDATE_NOT_FOUND
            ):
                groups[group_key]["_exact_location_verified"] = True
            groups[group_key]["affected_count"] += defect.get("affected_count", 1)
            if len(groups[group_key]["examples"]) < 3:
                groups[group_key]["examples"].append(
                    defect.get("source_quote", "")[:100]
                )
            sev_rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
            if sev_rank.get(defect.get("severity", ""), 0) > sev_rank.get(
                groups[group_key]["severity"], 0
            ):
                groups[group_key]["severity"] = defect["severity"]

    return sorted(
        groups.values(),
        key=lambda g: (-{"critical": 3, "high": 2, "medium": 1, "low": 0}.get(
            g.get("severity", "low"), 0
        ), -g.get("affected_count", 0), g.get("defect_type", ""),
            tuple(g.get("examples", []))),
    )


def verify_defect_counts(
    defect_groups: list[dict],
    unit_text_map: dict[str, str],
    candidate_md: str,
) -> list[dict]:
    """Add mechanical count verification to defect groups.

    For countable defect types (qualifier_omission with known keywords),
    compute source_count, candidate_count, and verified_delta. For
    non-countable types, mark count_status as "unverified".
    """
    verified: list[dict] = []
    for group in defect_groups:
        enriched = dict(group)
        exact_location_verified = bool(
            enriched.pop("_exact_location_verified", False)
        )
        dtype = group.get("defect_type", "")
        examples = group.get("examples", [])

        if dtype == "qualifier_omission" and examples:
            keyword = (
                group.get("count_verification", {}).get("keyword")
                or _extract_keyword_from_examples(examples)
            )
            if keyword and keyword in _COUNTABLE_KEYWORDS:
                source_total = sum(
                    _mechanical_count(keyword, text)
                    for text in unit_text_map.values()
                )
                candidate_total = _mechanical_count(keyword, candidate_md)
                verified_delta = max(0, source_total - candidate_total)
                count_verification = {
                    "keyword": keyword,
                    "source_count": source_total,
                    "candidate_count": candidate_total,
                    "verified_delta": verified_delta,
                    "count_status": "verified",
                }
                if verified_delta == 0 and exact_location_verified:
                    count_verification.update({
                        "count_status": "unverified",
                        "location_conflict": True,
                    })
                    enriched["verified_count"] = None
                else:
                    enriched["verified_count"] = verified_delta
                enriched["count_verification"] = count_verification
            else:
                enriched["count_verification"] = {"count_status": "unverified"}
                enriched["verified_count"] = None
        else:
            enriched["count_verification"] = {"count_status": "unverified"}
            enriched["verified_count"] = None

        verified.append(enriched)
    return verified


def _extract_keyword_from_examples(examples: list[str]) -> str | None:
    """Return the first countable whole-word keyword in sorted order."""
    keywords = _extract_keywords_from_examples(examples)
    return keywords[0] if keywords else None


def _extract_keywords_from_examples(examples: list[str]) -> list[str]:
    """Extract every distinct countable whole-word keyword."""
    keywords: set[str] = set()
    for example in examples:
        keywords.update(
            match.group()
            for match in _WORD_RE_UNIT.finditer(example)
            if match.group() in _COUNTABLE_KEYWORDS
        )
    return sorted(keywords)


def verify_unit_evidence(
    unit_results: list[dict],
    unit_text_map: dict[str, str],
    candidate_md: str,
) -> list[dict]:
    """Two-sided verification of unit check claims.

    For each unit result with defects containing source_quotes, verify:
    1. The quote exists in the source unit (source provenance)
    2. Whether the quote is present in the candidate (refutation check)

    Returns enriched unit results with evidence dispositions.
    """
    enriched_results: list[dict] = []
    for unit_result in unit_results:
        enriched = dict(unit_result)
        unit_id = unit_result.get("unit_id", "")
        source_text = unit_text_map.get(unit_id, "")
        enriched_defects: list[dict] = []
        for defect in unit_result.get("defects", []):
            enriched_defect = dict(defect)
            quote = defect.get("source_quote", "")
            if not quote or len(quote) < 5:
                enriched_defect["evidence_disposition"] = {
                    "quote": quote[:80],
                    "source_grounded": False,
                    "candidate_status": "source_ungrounded",
                }
                enriched_defects.append(enriched_defect)
                continue

            span = EvidenceSpan(axis="structure", quote=quote, reason="unit-check")
            source_grounded, _ = ground_spans([span], source_text)
            if not source_grounded:
                enriched_defect["evidence_disposition"] = {
                    "quote": quote[:80],
                    "source_grounded": False,
                    "candidate_status": "source_ungrounded",
                }
                enriched_defects.append(enriched_defect)
                continue
            source_hit = source_grounded[0]
            if source_hit.status == GROUND_EXACT:
                assert source_hit.start is not None and source_hit.end is not None
                source_slice = source_text[source_hit.start:source_hit.end]
                if not semantic_parity_holds(span, source_slice):
                    source_grounded = [GroundedSpan(span, GROUND_FUZZY)]
            candidate_evidence = classify_candidate_evidence(
                source_grounded, candidate_md,
            )
            if candidate_evidence:
                ev = candidate_evidence[0]
                enriched_defect["evidence_disposition"] = {
                    "quote": quote[:80],
                    "source_grounded": True,
                    "source_status": ev.source_status,
                    "candidate_status": ev.candidate_status,
                }
            else:
                enriched_defect["evidence_disposition"] = {
                    "quote": quote[:80],
                    "source_grounded": True,
                    "candidate_status": CANDIDATE_NOT_FOUND,
                }
            enriched_defects.append(enriched_defect)

        enriched["defects"] = enriched_defects
        enriched["evidence_dispositions"] = [
            defect["evidence_disposition"] for defect in enriched_defects
        ]
        enriched_results.append(enriched)

    return enriched_results


_TABLE_SIGNAL_TYPES = frozenset({
    "table_corruption", "table_orphan",
})
_CODE_SIGNAL_TYPES = frozenset({
    "missing_code",
})

_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})", re.MULTILINE)
"""Detect fenced code blocks in candidate markdown."""

_CODE_PAGE_INDICATORS = re.compile(
    r"(?:"
    r"constexpr\s|consteval\s|template\s*<|namespace\s+\w"
    r"|#include\s|#define\s|#if\b|#endif\b"
    r"|void\s+\w+\s*\(|int\s+\w+\s*\("
    r"|::\w+|->|std::"
    r")",
)
"""Heuristic code markers in PDF source text. When a page carries these,
Stage 1 Clear is skipped so fence-boundary defects are not rubber-stamped."""


async def _check_one_unit(
    pid: str,
    unit_id: str,
    source_text: str,
    candidate_md: str,
    signal_detail: str,
    agent: AgentBackend,
    *,
    debug_log: list[str] | None = None,
    guard_tag: str | None = None,
    signal_types: set[str] | None = None,
    source_format: str = "unknown",
) -> dict:
    """Run one scoped unit check via the LLM.

    ``guard_tag``, when provided, is the paper-level stable tag (prefix-cache
    reuse across this paper's calls); falls back to a fresh random tag. The
    user message leads with the large shared CANDIDATE MARKDOWN so the
    ``[system_prompt + guard_instruction][CANDIDATE MARKDOWN:...]`` prefix is
    identical across every unit check for this paper.

    When the unit has table-related or code-related risk signals
    (table_corruption, table_orphan, missing_code), Stage 1 Clear is
    skipped so the model must evaluate structure, not just keyword
    presence.
    """
    tag = guard_tag or f"SRC{secrets.token_hex(4)}"
    service = getattr(agent, "service_name", "") or None
    resolved = resolve_runtime_table_contract(service=service)
    code_resolved = resolve_runtime_code_contract(service=service)
    system = (
        inject_code_rubric(
            inject_table_rubric(UNIT_CHECK_SYSTEM_PROMPT, resolved),
            code_resolved,
        )
        + "\n"
        + guard_instruction(tag)
    )
    user_msg = (
        f"CANDIDATE MARKDOWN:\n"
        f"{inject_untrusted(candidate_md, tag)}\n\n"
        f"Paper: {pid}\n"
        f"{source_format_line(source_format)}"
        f"Unit: {unit_id}\n"
        f"Risk signal: {signal_detail}\n\n"
        f"SOURCE TEXT ({unit_id}):\n"
        f"{inject_untrusted(source_text, tag)}\n"
    )

    has_structure_signal = bool(
        signal_types
        and signal_types & (_TABLE_SIGNAL_TYPES | _CODE_SIGNAL_TYPES)
    )
    # Skip Stage 1 Clear when the source page has code content, not only
    # when a missing_code risk signal fires. Heading-in-fence, split
    # listings, and false wording tags are boundary defects that the fast
    # clear path cannot detect.
    has_code_on_page = bool(_CODE_PAGE_INDICATORS.search(source_text))
    unit_check = await _run_two_stage_unit_check(
        pid, unit_id, agent, system, user_msg,
        debug_log=debug_log,
        skip_clear=has_structure_signal or has_code_on_page,
    )

    return {
        "unit_id": unit_id,
        "verdict": unit_check.verdict,
        "confidence": unit_check.confidence,
        "reasoning": unit_check.reasoning,
        "defects": [d.model_dump() for d in unit_check.defects],
    }


async def _run_two_stage_unit_check(
    pid: str,
    unit_id: str,
    agent: AgentBackend,
    system: str,
    user_msg: str,
    *,
    debug_log: list[str] | None,
    skip_clear: bool = False,
) -> UnitCheck | UnitCheckDefects:
    """Dispatch the verdict-first bifurcation (Stage 1 Clear, Stage 2 Defects).

    Stage 1 tries the pass-only ``UnitCheckClear`` micro-schema
    (``UNIT_CLEAR_MAX_TOKENS``), the ~70% common case that lets the model
    stop decoding right after the verdict instead of always paying for the
    full defect schema. A confident pass short-circuits here. Anything else
    (non-pass verdict, low confidence, schema-validation failure, timeout)
    falls through to Stage 2, the full ``UnitCheckDefects`` schema
    (``UNIT_DEFECTS_MAX_TOKENS``). ``TAPETUM_VERDICT_FIRST=0`` disables the
    bifurcation and restores the legacy single-schema ``UnitCheck`` call.

    When ``skip_clear`` is True (table-related risk signals), Stage 1 is
    bypassed entirely so the model must evaluate structural defects, not
    just keyword presence.
    """
    use_verdict_first = os.environ.get("TAPETUM_VERDICT_FIRST", "1") == "1"

    if not use_verdict_first:
        return await asyncio.wait_for(
            run_judge_task(
                agent, system, user_msg, UnitCheck,
                label=f"unit-check-{pid}-{unit_id}",
                debug_log=debug_log,
            ),
            timeout=UNIT_CHECK_TIMEOUT_SECONDS,
        )

    if not skip_clear:
        try:
            clear_result: UnitCheckClear = await asyncio.wait_for(
                run_judge_task(
                    agent, system, user_msg, UnitCheckClear,
                    label=f"unit-clear-{pid}-{unit_id}",
                    debug_log=debug_log,
                    max_tokens=UNIT_CLEAR_MAX_TOKENS,
                ),
                timeout=UNIT_CHECK_TIMEOUT_SECONDS,
            )
            if (
                clear_result.verdict == "pass"
                and clear_result.confidence >= UNIT_CLEAR_CONFIDENCE_FLOOR
            ):
                return to_unit_check(clear_result)
        except Exception:
            logger.debug(
                "unit-clear stage failed for %s/%s, falling through to defects",
                pid, unit_id, exc_info=True,
            )
    else:
        logger.debug(
            "unit-clear skipped for %s/%s (structure/code signal)",
            pid, unit_id,
        )

    return await asyncio.wait_for(
        run_judge_task(
            agent, system, user_msg, UnitCheckDefects,
            label=f"unit-defects-{pid}-{unit_id}",
            debug_log=debug_log,
            max_tokens=UNIT_DEFECTS_MAX_TOKENS,
        ),
        timeout=UNIT_CHECK_TIMEOUT_SECONDS,
    )
