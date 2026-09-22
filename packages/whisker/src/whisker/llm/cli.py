#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""whisker-tapetum-llm: advisory LLM fidelity adjudication CLI.

Console-script entry point (``whisker-tapetum-llm``). Runs the multi-axis
conversion-fidelity cascade on one or more candidate papers. Advisory ONLY:
never touches ``whisker --gate``, never changes whisker verdict.

Exit contract: advisory verdicts (pass/review/fail) yield exit 0. Operational
errors (exception, timeout, ``status="error"``) yield exit 1 after remaining
papers complete and after in-run retry waves on this-run errors.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import shutil
import sys
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx
import pymupdf
from dotenv import find_dotenv, load_dotenv
from paperstore.sqlite_backend import SqliteBackend
from pipeline import AgentBackend, PipelinePrompt, write_debug_file
from pipeline.services import load_services

from whisker.cli_common import open_backend, render_progress
from whisker.det.score import sidecar_path, whisker_output_dir
from whisker.golden_ideals import find_ideals_dir, ideal_path
from whisker.llm.adjudicate import adjudicate_paper, select_candidates
from whisker.llm.constants import (
    GUARD_TAG,
    MAX_PAGE_ESCALATIONS,
    MAX_UNIT_CHECKS,
    PAGE_ESCALATION_TIMEOUT_SECONDS,
    UNIT_CHECK_TIMEOUT_SECONDS,
)
from whisker.llm.fusion import (
    _validate_tapetum_sidecar,
    _validate_whisker_sidecar,
    fuse_verdicts,
)
from whisker.llm.fusion_report import (
    build_merged_json,
    persist_merged_report,
    render_terminal_fusion_footer,
)
from whisker.llm.ideal_verify import (
    IDEAL_VERIFY_PROMPT_CONTRACT,
    verify_against_ideal,
)
from whisker.llm.inspect_report import format_report
from whisker.llm.models import (
    Adjudication,
    CodeBoundaryJudgment,
    IdealVerification,
    MetadataOutlineCheck,
    PageJudgment,
    UnitCheck,
    UnitCheckClear,
    UnitCheckDefects,
)
from whisker.llm.pdf_judge import (
    CODE_BOUNDARY_FENCE_CAP,
    CODE_BOUNDARY_SYSTEM_PROMPT,
    JUDGE_SYSTEM_PROMPT,
    PAGE_JUDGE_SYSTEM_PROMPT,
    PdfJudgment,
    judge_pdf_extraction,
)
from whisker.llm.trace_render import render_pdf_trace
from whisker.llm.unit_judge import (
    METADATA_CHECK_SYSTEM_PROMPT,
    UNIT_CHECK_SYSTEM_PROMPT,
    hydrate_pipeline_prompt,
    inject_code_rubric,
    inject_table_rubric,
    resolve_runtime_code_contract,
    resolve_runtime_table_contract,
)

logger = logging.getLogger(__name__)

_EXIT_OK = 0
_SERVICES_FILENAME = "SERVICES.toml"
_SAFE_SERVICE_FIELDS = (
    "backend",
    "model",
    "base_url",
    "max_context_window",
    "chars_per_token",
    "token_multiplier",
    "thinking_capable",
    "tools_capable",
    "stream",
)

# Bump when lane logic changes without a prompt change. The fingerprint
# includes this, so an incremental run re-evaluates all papers after a bump.
# v2: models.py Field-Description caps + _SLOT_MAX_TOKENS 1024/2048 (2026-07-08).
# v3: per-page recall screen + scoped page-escalation calls, PdfJudgeResult
# gains page_screen/page_escalations (2026-07-15).
# v4: source-grounded missing-content claims are checked against candidate
# Markdown and persisted with explicit present/not-found/ambiguous provenance.
# v6: metadata/outline is mandatory, unit coverage is fail-closed, and
# fingerprints include every source-aware prompt/schema/service.
# v7: optional ideal-aware verification is attached after the source-aware
# judge; fingerprints include ideal content and verifier identity.
# v8: fusion validates ideal sidecar data against the shared schema; reports
# treat malformed ideal data as neutral and bound/escape rendered details.
# v9: fingerprint gains coverage_mode (default/exhaustive/all_pages) so
# --exhaustive-units / --all-pages cannot poison the incremental cache.
# v10: routed units without source packets are pre-filtered before
# MAX_UNIT_CHECKS quota selection; they no longer burn cap slots or
# force coverage_complete=false on the routed path.
# v11: metadata-fail short-circuit skips unit checks and page escalations
# when the metadata/outline verdict already caps the paper; per-paper HMAC
# guard tag replaces random per-call tags for prefix-cache reuse; user
# message reorder puts shared candidate markdown first.
# v12: schema contracts gain UnitCheckClear/UnitCheckDefects (the
# verdict-first bifurcation output schemas in unit_judge.py were dispatched
# to the LLM but never hashed); fingerprint gains unit_check_mode
# (TAPETUM_VERDICT_FIRST) so flipping that dispatch toggle invalidates the
# cache even when neither schema's own JSON changed (09-determinism.md F3).
# v15: code-boundary checks run even under the metadata short-circuit;
# CODE_BOUNDARY_SYSTEM_PROMPT gains heading_in_fence negative rules and
# quote-discipline cap to reduce false positives and JSON retries.
# v16: per-fence scoping (one LLM call per fence slice with context lines)
# replaces per-page scoping, eliminating duplicate and misattributed findings.
# v17: fence cap 6->25 (per-fence calls are cheap; covers all calibration papers).
# v18: CB gated behind metadata short-circuit on default fleet; cap back to
# 6 (v17 calibration overfit, 0 CB demotions on 09-01 fleet). Audit modes
# exempt. PDF-timeout envelope gains CB term. CB errors fail-closed.
# v19: string-aware JSON extract (pipeline); CB timeout still fail-closed,
# JSON/validation persist cb_error and continue; retry wave at c=16; LJF
# by predicted work; HTML metadata-first; default fleet skips CB/page-LLM
# (audit/inspect only); unit-quota overflow is a zero-LLM coverage cap;
# ideal_pending fusion-cap + no fingerprint skip after a failed attach.
# v20: non-think pin at all call sites after pod default flipped;
# sidecars from the thinking-on window must be re-evaluated.
# v22: code-boundary source font evidence (fence_fonts): per-fence font
# layer appended to the CB user message, prose_in_fence on monospace-set
# source lines clamped to clean. Prompt changed too; the bump covers the
# clamp and the message change.
# v23: unit-dump grid pairing skips candidate-less source grids
# (table_compare.grid_match_for_unit): no synthetic row0_mismatch, no
# pseudo-header quoted into typed questions. 37 fleet units confirmed by
# page-layout pseudo-grids lose the DEFECT stamp (#424).
# v24: unit-dump grid pairing also skips pseudo-header source grids
# (table_compare.SourceGrid.pseudo_header: row-0 word cut by a column
# boundary, <2 alphabetic cells, code tail, title block). A same-width
# pseudo-grid paired at header score 0 carried a measured row0_mismatch
# and confirmed truncated_leak / header_is_data over the model's answer
# (P3373R2 T0-T2, P4003R0 T1/T3/T5-T7). Those units abstain now (#425).
# v25: truncated_leak typed question names a "Label: value" caption
# (Result: Consensus) as prose and keeps "leaked rows" for any line carrying
# column values, meeting/date/poll words included; _estimate_line_after
# matches header plus body rows so repeated poll headers get their own
# lookahead (P3290R4 T1-T5, #426). The unit-probe question is not in
# prompt_sha256, so the bump re-evaluates.
# v26: a unit without a textlayer pairing takes the same typed question as
# the source-first fallback (_typed_question_for), so flattened /
# wrap_orphan / hyphen_glue units are judged instead of skipped with
# "no typed question" (P4178R0 T6, #427). Fleet blast radius at v25: that
# one unit; every other skip in the protected fleet is an aligned unit.
# v27: header_is_data asks whether the markdown header is the PDF's top
# row or a body row that moved up, and only the exact answer "body row"
# confirms. "data values" no longer confirms: a section reference is a
# data value and still the real header (P4178R0 HEAD, #427). The typed
# fallback sends the text-layer page along when one was paired.
_LANE_VERSION = 28

# Fleet LJF: papers are sorted by descending predicted work before dispatch
# (_predicted_work_seconds: sidecar duration, else PDF page count, else
# source KiB). Tie-break is ascending PID.
#
# Papers adjudicated concurrently by default. The advisory lane may run
# N > 1 because papers are independent (own state, own sidecar file) and the
# lane never gates; this is the per-package mechanism allowed by CLAUDE.md
# D11 and does not touch the pipeline package or dissect. Default 16 matches
# the pod's --max-num-seqs 16 so the waitlist lives in this semaphore, not
# in the vLLM queue: queued HTTP connections charge wait time against
# wait_for budgets and the RunPod proxy kills idle ones (~100s). Historical
# overfill (c=32, 692.3s vs 722.4s at c=16 on the 1-call lane, 2026-07-08)
# is parked; lane v17 is multi-call and the 2026-08-27 fleet at c=32 left
# 62 timeout/proxy tombstones (issue 401). Pass ``--concurrency 1`` for a
# serial run.
_DEFAULT_CONCURRENCY = 16

# Highest concurrency exercised against the pod in a full-corpus run.
# Values above it are permitted but warn: c=381 broke catastrophically
# (257/381 proxy-killed connections, 2026-07-08), so the ceiling is real.
_MAX_TESTED_CONCURRENCY = 32

# After the main gather, this-run error papers (verdict_str is None) are
# re-adjudicated at the same width as the main gather. Phase-1 shrinks
# the error set (JSON flakes no longer abort the paper); remaining
# timeouts recover at full concurrency. Prior-run tombstones stay
# skipped unless the operator passes --retry-errors.
_ERROR_RETRY_CONCURRENCY = 16
_ERROR_RETRY_ROUNDS = 2

# Cold-run LJF fallback when no sidecar duration exists: seconds per PDF
# page. Metadata-pass chains dominate wall time, not raw source bytes.
_LJF_SECONDS_PER_PDF_PAGE = 8.0

# Wall-clock budget per paper. Generous: worst observed chain is a chunked
# paper (7 chunks x ~30 s) plus a tier-2 escalation. Prevents one hung
# request from holding a concurrency slot for the AsyncOpenAI default
# 600 s read timeout per call across retries.
_PAPER_TIMEOUT_SECONDS = 900.0

# Standalone ideal-verifier structured output is a verdict plus a bounded
# discrepancy list; match the established deep text-lane ceiling.
_IDEAL_MAX_TOKENS = 2048

# Wall-clock budget for the PDF-judge path specifically: the monolith call
# (bounded by _PAPER_TIMEOUT_SECONDS above) plus a moderate per-call
# allowance for up to MAX_PAGE_ESCALATIONS serial page-escalation calls
# (each individually bounded by PAGE_ESCALATION_TIMEOUT_SECONDS, D11:
# escalations run one at a time, never concurrently). Deliberately additive,
# not a 33x scale-up: escalation only fires on pages the deterministic
# screen flagged (typically 0-2, SYNTHESIS.md), so this is a ceiling for the
# worst case, not the expected cost. When *unit_count* is set (all-pages
# review mode), the unit-check term scales to the real page count instead of
# the fleet MAX_UNIT_CHECKS cap.
def _pdf_judge_timeout_seconds(
    unit_count: int | None = None,
    *,
    code_boundary: bool = True,
) -> float:
    unit_slots = (
        (1 + unit_count) if unit_count is not None else (1 + MAX_UNIT_CHECKS)
    )
    cb_term = (
        CODE_BOUNDARY_FENCE_CAP * PAGE_ESCALATION_TIMEOUT_SECONDS
        if code_boundary else 0.0
    )
    return (
        _PAPER_TIMEOUT_SECONDS
        + MAX_PAGE_ESCALATIONS * PAGE_ESCALATION_TIMEOUT_SECONDS
        + unit_slots * UNIT_CHECK_TIMEOUT_SECONDS
        + cb_term
    )


def _pdf_page_count(pid: str, backend: SqliteBackend) -> int | None:
    """Cheap physical page count for all-pages timeout sizing.

    Opens the staged source PDF via pymupdf, reads ``page_count``, and closes.
    Returns None on any error so the caller falls back to the default budget.
    """
    try:
        source_path = backend.get_source_path(pid)
        doc = pymupdf.open(source_path)
        try:
            return int(doc.page_count)
        finally:
            doc.close()
    except Exception as exc:
        logger.warning(
            "Could not read page count for %s; using default PDF timeout: %s",
            pid,
            exc,
        )
        return None


def _coverage_mode_for_paper(
    args: argparse.Namespace, *, is_pdf_lane: bool
) -> str:
    """Fingerprint coverage key for incremental skip separation."""
    if getattr(args, "all_pages", False) and is_pdf_lane:
        return "all_pages"
    if getattr(args, "exhaustive_units", False) or getattr(args, "inspect", False):
        return "exhaustive"
    return "default"


def _text_lane_timeout_seconds() -> float:
    return (
        _PAPER_TIMEOUT_SECONDS
        + (1 + MAX_UNIT_CHECKS) * UNIT_CHECK_TIMEOUT_SECONDS
    )

# Pre-batch endpoint probe budget (GET {server_root}/health).
_HEALTH_PROBE_TIMEOUT_SECONDS = 30.0

# Loggers whose per-call INFO lines (HTTP requests, step dispatch, slot
# resolution) would repeat for every paper in a batch run and drown the
# progress bar. Quieted to WARNING in batch mode only; single-paper runs
# keep them for debugging.
_BATCH_QUIET_LOGGERS = (
    "httpx",
    "openai",
    "pipeline.runner",
    "pipeline.services",
)

# Known self-correcting retry warnings from the model backend. In batch mode
# they fire on most papers (model token-corruption artifact, attempt 2
# succeeds), so they are counted and rolled into the footer instead of
# printing one line per paper. A paper whose retries are exhausted still
# surfaces as an ERROR line.
_RETRY_WARNING_MARKERS: dict[str, str] = {
    "Raw JSON parse failed": "parse",
    "Raw JSON output truncated": "truncated",
    "Transient API error": "transient",
}


class _RetryCountFilter(logging.Filter):
    """Swallow known transient-retry warnings, counting them for the footer.

    Keeps a per-marker counter and logs each swallowed line at DEBUG so the
    full fleet log still contains the pid and error when needed.
    """

    def __init__(self) -> None:
        super().__init__()
        self.count = 0
        self.by_kind: dict[str, int] = {}

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for marker, kind in _RETRY_WARNING_MARKERS.items():
            if marker in msg:
                self.count += 1
                self.by_kind[kind] = self.by_kind.get(kind, 0) + 1
                logger.debug("model-retry [%s]: %s", kind, msg)
                return False
        return True

    def summary(self) -> str:
        """Human-readable breakdown for the footer line."""
        if not self.by_kind:
            return str(self.count)
        parts = ", ".join(
            f"{kind} {n}" for kind, n in sorted(self.by_kind.items())
        )
        return f"{self.count} model retries: {parts}"


class _BarAwareHandler(logging.StreamHandler):
    """Stream handler that keeps the progress bar as the bottom line.

    Before emitting a record it blanks the in-place bar, after emitting it
    redraws the bar, so log lines and the bar never share a line.
    """

    def __init__(self) -> None:
        super().__init__(sys.stderr)
        self.bar_len = 0
        self.redraw: object = None

    def emit(self, record: logging.LogRecord) -> None:
        if self.bar_len and sys.stderr.isatty():
            sys.stderr.write("\r" + " " * self.bar_len + "\r")
            self.bar_len = 0
        super().emit(record)
        if callable(self.redraw):
            self.bar_len = self.redraw()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="whisker-tapetum-llm",
        description="Advisory LLM conversion-fidelity adjudication.",
    )
    parser.add_argument(
        "pids",
        nargs="*",
        help="Paper IDs to adjudicate (case-insensitive). If omitted "
        "(and --review-all is not set), all converted papers are "
        "adjudicated with automatic fingerprint-based skip.",
    )
    parser.add_argument(
        "--review-all",
        action="store_true",
        help="Auto-select risk candidates from existing whisker "
        "sidecars instead of running all converted papers.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Write debug transcript.",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Write trace transcript.",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Also write a readable side-by-side report (whisker vs advisory) "
        "to whisker/llm/tapetum-inspect.md.",
    )
    parser.add_argument(
        "--exhaustive-units",
        action="store_true",
        help="Check ALL routed units instead of capping at MAX_UNIT_CHECKS. "
        "Use for golden-PR review where wall-clock cost is acceptable. "
        "Implied by --inspect.",
    )
    parser.add_argument(
        "--all-pages",
        action="store_true",
        help="Forces a scoped LLM unit check for EVERY physical PDF page; "
        "PDF papers only; review-mode tool, not for fleet runs. "
        "It implies exhaustive unit semantics.",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        default=None,
        help="Override WG21_DATA_DIR.",
    )
    parser.add_argument(
        "--service",
        action="append",
        default=[],
        metavar="SLOT=NAME",
        help="Override a service slot, e.g. --service deep=alliance-pod. "
        "Repeatable.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=_DEFAULT_CONCURRENCY,
        metavar="N",
        help="Adjudicate up to N papers concurrently (default %(default)s). "
        "Advisory lane only; results are persisted in input order. "
        "Use 1 for a strictly serial run.",
    )
    parser.add_argument(
        "--fuse-only",
        action="store_true",
        help="Recompute fusion blocks from existing sidecar pairs on disk. "
        "No LLM calls. Useful after a whisker --all re-run.",
    )
    parser.add_argument(
        "--text-only",
        action="store_true",
        help="Force all papers through the markdown text lane, skipping "
        "the PDF-text-layer judge lane for PDF papers.",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Skip papers whose existing sidecar fingerprint matches "
        "(same source, same markdown, same prompt, same lane version). "
        "For explicit PIDs and --review-all this is opt-in (off by "
        "default). The bare full-run (no PIDs, no --review-all) enables "
        "incremental automatically; use --force to override.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-evaluate every paper even when a fingerprint match "
        "exists. Only meaningful in the default full-run mode where "
        "incremental is on by default; ignored when explicit PIDs or "
        "--review-all are given.",
    )
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Re-evaluate papers whose previous run ended in an error "
        "tombstone, even when the fingerprint matches. Without this "
        "flag, prior-run error tombstones with valid fingerprints are "
        "skipped like successful runs. This-run errors are retried "
        "automatically before the batch footer.",
    )
    parser.add_argument(
        "--would-skip",
        action="store_true",
        help="Dry run: resolve the paper set and print the fingerprint "
        "skip decision each paper WOULD get ('run', 'skip (fingerprint "
        "match)', 'skip (superset: MODE)', or 'skip (tombstone)'), then "
        "exit. No LLM calls, no health probe, no sidecar or report writes.",
    )
    return parser.parse_args(argv)


def _parse_service_overrides(items: list[str]) -> dict[str, str]:
    """Parse ``SLOT=NAME`` override strings into a slot -> service map."""
    overrides: dict[str, str] = {}
    for item in items:
        slot, sep, name = item.partition("=")
        if not sep or not slot.strip() or not name.strip():
            logger.error("Ignoring malformed --service '%s' (want SLOT=NAME)", item)
            continue
        overrides[slot.strip()] = name.strip()
    return overrides


def _read_sidecar_dict(path: Path) -> dict | None:
    """Read an untrusted JSON sidecar only when its root is an object."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _collect_sidecar_dicts(backend: SqliteBackend) -> list[dict]:
    """Read all whisker sidecars from the whisker output directory."""
    # Discover by scanning the whisker dir for *.whisker.json files
    # We use a known PID to get the whisker dir path (any PID works for the dir)
    papers = backend.list_all_paper_ids()
    results: list[dict] = []
    seen_dirs: set[Path] = set()

    for paper in papers:
        pid = paper if isinstance(paper, str) else getattr(paper, "paper_id", str(paper))
        w_dir = whisker_output_dir(pid, backend)
        if w_dir in seen_dirs:
            continue
        seen_dirs.add(w_dir)
        if not w_dir.exists():
            continue
        for sc_file in w_dir.glob("*.whisker.json"):
            data = _read_sidecar_dict(sc_file)
            validated = _validate_whisker_sidecar(data)
            expected_pid = sc_file.name.removesuffix(".whisker.json").upper()
            if (
                validated is not None
                and validated["pid"].upper() == expected_pid
            ):
                results.append(validated)
            else:
                results.append({"pid": expected_pid, "verdict": "?"})

    return results


def _llm_output_dir(pid: str, backend: SqliteBackend) -> Path:
    """Return ``whisker/llm/``, the advisory lane's artifact directory.

    Sibling of the deterministic ``whisker/det/`` (see
    ``whisker.det.score.whisker_output_dir``): the two lanes are separated on disk,
    each with its own sidecars and reports.
    """
    return whisker_output_dir(pid, backend).parent / "llm"


def _sha256_file(path: Path) -> str:
    """Return hex SHA-256 of a file's contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_str(text: str) -> str:
    """Return hex SHA-256 of a UTF-8 string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_services_config(path: Path | None = None) -> dict:
    """Parse repo-level SERVICES.toml without importing pipeline internals."""
    if path is None:
        for parent in (Path.cwd(), *Path.cwd().parents):
            candidate = parent / _SERVICES_FILENAME
            if candidate.is_file():
                path = candidate
                break
    if path is None or not path.is_file():
        raise FileNotFoundError(f"{_SERVICES_FILENAME} not found")
    with open(path, "rb") as config_file:
        return tomllib.load(config_file)


def _sanitize_base_url(value: object) -> str:
    """Remove credentials and query data while preserving endpoint identity."""
    if not isinstance(value, str) or not value:
        return ""
    parsed = urlsplit(value)
    safe_netloc = parsed.netloc.rsplit("@", 1)[-1]
    return urlunsplit((parsed.scheme, safe_netloc, parsed.path, "", ""))


def _pdf_prompt_contract(*, service: str | None = None) -> str:
    """All system prompts that can affect a PDF-lane result."""
    resolved = resolve_runtime_table_contract(service=service)
    code_resolved = resolve_runtime_code_contract(service=service)
    def _inject(text: str) -> str:
        return inject_code_rubric(inject_table_rubric(text, resolved), code_resolved)
    return "\n".join((
        _inject(JUDGE_SYSTEM_PROMPT),
        _inject(PAGE_JUDGE_SYSTEM_PROMPT),
        _inject(CODE_BOUNDARY_SYSTEM_PROMPT),
        METADATA_CHECK_SYSTEM_PROMPT,
        _inject(UNIT_CHECK_SYSTEM_PROMPT),
    ))


def _pdf_schema_contract() -> str:
    """All structured output schemas used by the PDF lane.

    Includes both arms of the verdict-first unit-check bifurcation
    (``UnitCheckClear``/``UnitCheckDefects``, unit_judge.py): unit checks are
    shared between the PDF and text lanes, and either schema's shape can
    change the model's actual output independent of the legacy ``UnitCheck``
    schema.
    """
    return json.dumps(
        {
            "PdfJudgment": PdfJudgment.model_json_schema(),
            "PageJudgment": PageJudgment.model_json_schema(),
            "CodeBoundaryJudgment": CodeBoundaryJudgment.model_json_schema(),
            "MetadataOutlineCheck": MetadataOutlineCheck.model_json_schema(),
            "UnitCheck": UnitCheck.model_json_schema(),
            "UnitCheckClear": UnitCheckClear.model_json_schema(),
            "UnitCheckDefects": UnitCheckDefects.model_json_schema(),
        },
        sort_keys=True,
    )


def _text_prompt_contract(
    prompt: PipelinePrompt, *, service: str | None = None
) -> str:
    """All system prompts that can affect an HTML/text-lane result."""
    if service is None:
        services = getattr(prompt, "services", None) or {}
        try:
            mapping = dict(services)
        except (TypeError, ValueError):
            mapping = {}
        service = mapping.get("fast") or mapping.get("default")
    resolved = resolve_runtime_table_contract(service=service)
    code_resolved = resolve_runtime_code_contract(service=service)
    if isinstance(prompt, PipelinePrompt):
        prompt = hydrate_pipeline_prompt(
            prompt, resolved, code_resolved=code_resolved
        )
    def _inject(text: str) -> str:
        return inject_code_rubric(inject_table_rubric(text, resolved), code_resolved)
    step_prompts = [
        _inject(step.system_prompt)
        for step in getattr(prompt, "steps", ())
        if step.system_prompt
    ]
    return "\n".join((
        _inject(prompt.system_prompt),
        *step_prompts,
        METADATA_CHECK_SYSTEM_PROMPT,
        _inject(UNIT_CHECK_SYSTEM_PROMPT),
    ))


def _text_schema_contract() -> str:
    """All structured output schemas used by the HTML/text lane.

    See ``_pdf_schema_contract`` for why the verdict-first unit-check arms
    are included: unit_judge.py is shared by both lanes.
    """
    return json.dumps(
        {
            "Adjudication": Adjudication.model_json_schema(),
            "MetadataOutlineCheck": MetadataOutlineCheck.model_json_schema(),
            "UnitCheck": UnitCheck.model_json_schema(),
            "UnitCheckClear": UnitCheckClear.model_json_schema(),
            "UnitCheckDefects": UnitCheckDefects.model_json_schema(),
        },
        sort_keys=True,
    )


def _effective_model_contract(
    services: dict[str, str],
    services_config: dict,
) -> str:
    """Return canonical, secret-free config for the effective LLM services.

    Only aliases selected by fast/deep/default and allowlisted effective fields
    participate. Credentials, unrelated services, comments, and formatting do
    not affect the contract or enter a sidecar.
    """
    default_service = services.get("default", "")
    slots: dict[str, str] = {}
    for slot in ("fast", "deep", "default"):
        slots[slot] = services.get(slot) or default_service

    configured = services_config.get("services", {})
    selected: dict[str, dict[str, object]] = {}
    for service in sorted(set(slots.values())):
        raw = configured.get(service, {})
        selected[service] = {
            field: (
                _sanitize_base_url(raw[field])
                if field == "base_url"
                else raw[field]
            )
            for field in _SAFE_SERVICE_FIELDS
            if field in raw
            and isinstance(raw[field], (bool, int, float, str))
        }

    return json.dumps(
        {
            "services": selected,
            "slots": slots,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _compute_fingerprint(
    pid: str,
    backend: SqliteBackend,
    lane: str,
    prompt_text: str,
    model_name: str,
    schema_json: str,
    *,
    ideal_text: str | None = None,
    coverage_mode: str = "default",
) -> dict:
    """Build a content fingerprint for incremental skip detection.

    Keys:
        md_sha256: hash of the converted paper markdown.
        source_sha256: hash of the PDF/HTML source file.
        prompt_sha256: hash of the LLM system prompt text.
        model: effective model/service name.
        lane_version: ``_LANE_VERSION`` constant (bumped on logic changes).
        lane: lane label ("pdf_textlayer_judge" or "text").
        schema_sha256: hash of the Pydantic output schema (auto-invalidates
            on Field-description or structure changes in models.py / pdf_judge.py).
        unit_check_mode: current value of the ``TAPETUM_VERDICT_FIRST`` env
            toggle (unit_judge.py). Both arms of the verdict-first
            bifurcation are always hashed into ``schema_sha256``, but the
            toggle itself changes which schema a given unit check actually
            dispatches to without changing either schema's own JSON, so it
            needs its own key to invalidate the cache on a flip.
        ideal_sha256: hash of the discovered ideal, or null when absent.
        ideal_prompt_sha256, ideal_schema_sha256, ideal_model: verifier
            identities when an ideal is present, otherwise null.
        coverage_mode: ``default``, ``exhaustive``, or ``all_pages``.
    """
    md_path = backend.get_paper_md_path(pid)
    source_path = backend.get_source_path(pid)
    has_ideal = ideal_text is not None
    return {
        "md_sha256": _sha256_file(md_path),
        "source_sha256": _sha256_file(source_path),
        "prompt_sha256": _sha256_str(prompt_text),
        "model": model_name,
        "lane_version": _LANE_VERSION,
        "lane": lane,
        "schema_sha256": _sha256_str(schema_json),
        "unit_check_mode": os.environ.get("TAPETUM_VERDICT_FIRST", "1"),
        "ideal_sha256": _sha256_str(ideal_text) if has_ideal else None,
        "ideal_prompt_sha256": (
            _sha256_str(IDEAL_VERIFY_PROMPT_CONTRACT)
            if has_ideal
            else None
        ),
        "ideal_schema_sha256": (
            _sha256_str(
                json.dumps(IdealVerification.model_json_schema(), sort_keys=True)
            )
            if has_ideal
            else None
        ),
        "ideal_model": model_name if has_ideal else None,
        "coverage_mode": coverage_mode,
    }


def _read_existing_fingerprint(
    pid: str, backend: SqliteBackend
) -> dict | None:
    """Read the fingerprint block from an existing tapetum sidecar, if any."""
    out_dir = _llm_output_dir(pid, backend)
    sc_path = out_dir / f"{sidecar_path(pid, backend).stem}.tapetum.json"
    if not sc_path.exists():
        return None
    data = _read_sidecar_dict(sc_path)
    fingerprint = data.get("fingerprint") if data is not None else None
    return fingerprint if isinstance(fingerprint, dict) else None


def _read_existing_sidecar_status(
    pid: str, backend: SqliteBackend
) -> str | None:
    """Read the ``status`` field from an existing tapetum sidecar, if any."""
    out_dir = _llm_output_dir(pid, backend)
    sc_path = out_dir / f"{sidecar_path(pid, backend).stem}.tapetum.json"
    if not sc_path.exists():
        return None
    data = _read_sidecar_dict(sc_path)
    return data.get("status") if data is not None else None


def _read_existing_ideal_pending(pid: str, backend: SqliteBackend) -> bool:
    """True when a sidecar recorded a failed/missing ideal attach."""
    out_dir = _llm_output_dir(pid, backend)
    sc_path = out_dir / f"{sidecar_path(pid, backend).stem}.tapetum.json"
    if not sc_path.exists():
        return False
    data = _read_sidecar_dict(sc_path)
    return bool(data.get("ideal_pending")) if data is not None else False


_COVERAGE_MODE_RANK = {"default": 0, "exhaustive": 1, "all_pages": 2}


def _fingerprint_matches(
    pid: str, backend: SqliteBackend, new_fp: dict
) -> bool:
    """True if the existing sidecar's fingerprint matches *new_fp*.

    Coverage-mode superset skip: an existing ``all_pages`` sidecar satisfies
    a ``default`` or ``exhaustive`` request (it is strictly more thorough);
    ``exhaustive`` satisfies ``default``. The reverse never skips.
    ``--force`` bypasses this function entirely (caller responsibility).
    """
    old = _read_existing_fingerprint(pid, backend)
    if old is None:
        return False
    for key, new_val in new_fp.items():
        old_val = old.get(key)
        if key == "coverage_mode":
            old_rank = _COVERAGE_MODE_RANK.get(old_val, -1)
            new_rank = _COVERAGE_MODE_RANK.get(new_val, -1)
            if old_rank < new_rank:
                return False
            # old_rank >= new_rank: existing is at least as thorough, skip
        elif old_val != new_val:
            return False
    return True


def _fingerprint_skip_decision(
    pid: str,
    backend: SqliteBackend,
    fp: dict,
    *,
    retry_errors: bool,
) -> tuple[bool, str, str]:
    """Return ``(would_skip, kind, detail)`` for a computed fingerprint.

    ``kind`` is one of:
        ``none``: the fingerprint does not match; re-evaluate.
        ``retry``: a matching error tombstone, but ``--retry-errors`` forces
            re-evaluation anyway.
        ``tombstone``: a matching error tombstone; skip.
        ``match``: a matching successful sidecar; skip.
        ``superset``: a matching sidecar at a higher coverage_mode rank;
            skip. ``detail`` carries the old (higher-rank) mode.

    Shared by the live skip branch in ``_adjudicate_one`` and the
    ``--would-skip`` dry-run reporter, so their skip semantics cannot drift
    apart from each other.
    """
    if not _fingerprint_matches(pid, backend, fp):
        return False, "none", ""
    existing_status = _read_existing_sidecar_status(pid, backend)
    if existing_status == "error":
        if retry_errors:
            return False, "retry", ""
        return True, "tombstone", ""
    if _read_existing_ideal_pending(pid, backend):
        return False, "none", "ideal_pending"
    old_fp = _read_existing_fingerprint(pid, backend)
    old_mode = old_fp.get("coverage_mode", "default") if old_fp else "default"
    new_mode = fp.get("coverage_mode", "default")
    if old_mode != new_mode:
        return True, "superset", old_mode
    return True, "match", ""


def _skip_reason_label(kind: str, detail: str) -> str:
    """Human-readable skip reason for log lines and ``--would-skip`` output."""
    return {
        "tombstone": "previous error; use --retry-errors",
        "match": "fingerprint match",
        "superset": f"fingerprint superset: {detail}",
    }[kind]


def _source_kind(pid: str, backend: SqliteBackend) -> str:
    """Determine if a paper's source is PDF or HTML."""
    try:
        source = backend.get_source_path(pid)
        suffix = source.suffix.lower()
        if suffix == ".pdf":
            return "pdf"
        if suffix in (".html", ".htm"):
            return "html"
        return "unknown"
    except Exception:
        return "unknown"


def _utc_now_iso() -> str:
    """Current UTC time as an ISO 8601 string (warm marker timestamp)."""
    return datetime.now(timezone.utc).isoformat()


def _persist_lane_result(
    result,
    backend: SqliteBackend,
    fingerprint: dict | None = None,
    duration_seconds: float | None = None,
) -> Path:
    """Write a lane result sidecar (with fusion block) to the LLM lane dir.

    Works for any result object exposing ``.pid`` and
    ``.to_sidecar_dict()`` (PdfJudgeResult, VlmDiffResult)."""
    pid = result.pid
    out_dir = _llm_output_dir(pid, backend)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{sidecar_path(pid, backend).stem}.tapetum.json"

    payload = result.to_sidecar_dict()
    whisker_sc = _read_whisker_sidecar(pid, backend)
    fusion = fuse_verdicts(whisker_sc, payload)
    payload["fusion"] = fusion.to_dict()
    if fingerprint is not None:
        payload["fingerprint"] = fingerprint
    if duration_seconds is not None:
        payload["duration_seconds"] = round(duration_seconds, 2)
    # Warm marker (B2): set only on an actual evaluation, never on a
    # fingerprint skip, so the merged report can tell a fresh result from a
    # replayed one (see build_merged_json / _refresh_fusion_on_skip).
    payload["evaluated_at"] = _utc_now_iso()

    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return out_path


def _persist_result(
    result,
    backend: SqliteBackend,
    fingerprint: dict | None = None,
    duration_seconds: float | None = None,
) -> Path:
    """Write tapetum result sidecar (with fusion block) to the LLM lane dir."""
    pid = result.pid
    out_dir = _llm_output_dir(pid, backend)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{sidecar_path(pid, backend).stem}.tapetum.json"

    payload = result.to_dict()
    whisker_sc = _read_whisker_sidecar(pid, backend)
    fusion = fuse_verdicts(whisker_sc, payload)
    payload["fusion"] = fusion.to_dict()
    if fingerprint is not None:
        payload["fingerprint"] = fingerprint
    if duration_seconds is not None:
        payload["duration_seconds"] = round(duration_seconds, 2)
    payload["evaluated_at"] = _utc_now_iso()

    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return out_path


def _read_whisker_sidecar(pid: str, backend: SqliteBackend) -> dict:
    """Read a paper's whisker sidecar dict, or a stub if it is missing."""
    sc = sidecar_path(pid, backend)
    if sc.exists():
        payload = _read_sidecar_dict(sc)
        validated = _validate_whisker_sidecar(payload)
        if validated is not None and validated["pid"].upper() == pid.upper():
            return validated
    return {"pid": pid, "verdict": "?"}


def _read_tapetum_sidecar(path: Path) -> dict | None:
    """Read a tapetum sidecar dict, or mark malformed input unavailable."""
    return _validate_tapetum_sidecar(_read_sidecar_dict(path))


def _refresh_fusion_on_skip(pid: str, backend: SqliteBackend) -> None:
    """Recompute and persist the fusion block for a fingerprint-skipped paper.

    B3 fix: a fingerprint skip reuses the tapetum sidecar unchanged, but the
    deterministic whisker (det) sidecar may have been rescored since that
    sidecar was written, leaving a stale fusion paired with a fresh det
    verdict in the merged report. This recomputes ``fusion`` from the
    existing tapetum sidecar plus the CURRENT det sidecar, reusing the exact
    same ``fuse_verdicts`` call as ``--fuse-only`` (pure deterministic
    computation, zero LLM calls), and persists it back into the sidecar so
    the next merged-report rebuild picks up the current pairing.
    """
    out_dir = _llm_output_dir(pid, backend)
    sc_path = out_dir / f"{sidecar_path(pid, backend).stem}.tapetum.json"
    tap_data = _read_tapetum_sidecar(sc_path)
    if tap_data is None:
        return
    whisker_sc = _read_whisker_sidecar(pid, backend)
    fusion = fuse_verdicts(whisker_sc, tap_data)
    tap_data["fusion"] = fusion.to_dict()
    try:
        sc_path.write_text(
            json.dumps(tap_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        logger.debug("Could not refresh fusion for %s on skip", pid)


def _write_error_tombstone(
    pid: str,
    backend: SqliteBackend,
    exc: Exception,
    *,
    partial_progress: dict | None = None,
    fingerprint: dict | None = None,
    duration_seconds: float | None = None,
) -> None:
    """Write a minimal error sidecar so a stale pass from a previous run
    does not survive an adjudication failure.  ``fusion.py`` already handles
    ``status="error"`` sidecars on the read path (lines 86-94).

    When *partial_progress* is non-empty (PDF all-pages timeout mid-run),
    attach it under ``partial_progress`` so the tombstone keeps an honest
    audit trail. Verdict stays an error; never pass.

    When *fingerprint* is provided, it is attached under ``fingerprint`` so
    a subsequent warm run can recognize an unchanged error tombstone via
    ``_fingerprint_matches`` instead of unconditionally re-evaluating the
    paper. ``--retry-errors`` (see ``_adjudicate_one``) still lets a caller
    force re-evaluation of an error tombstone even when the fingerprint
    matches.
    """
    out_dir = _llm_output_dir(pid, backend)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{sidecar_path(pid, backend).stem}.tapetum.json"
    payload: dict = {
        "pid": pid,
        "status": "error",
        "error": type(exc).__name__,
    }
    if partial_progress:
        payload["partial_progress"] = partial_progress
    if fingerprint is not None:
        payload["fingerprint"] = fingerprint
    if duration_seconds is not None:
        payload["duration_seconds"] = round(duration_seconds, 2)
    payload["evaluated_at"] = _utc_now_iso()
    try:
        out_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.debug("Error tombstone written: %s", out_path)
    except OSError:
        logger.debug("Could not write error tombstone for %s", pid)


def _persist_inspect(
    pairs: list[tuple[dict, dict | None]],
    pids: list[str],
    backend: SqliteBackend,
) -> Path:
    """Write the combined whisker-vs-advisory inspection report."""
    pairs_sorted = sorted(pairs, key=lambda p: p[0].get("pid", ""))
    report = format_report(pairs_sorted)
    out_dir = _llm_output_dir(pids[0], backend)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "tapetum-inspect.md"
    out_path.write_text(report, encoding="utf-8")
    return out_path


def _snapshot_prev_merged_report(out_dir: Path) -> None:
    """Copy an existing ``report-merged.json`` to ``report-merged.prev.json``.

    Mirrors ``_snapshot_prev_report`` in ``whisker.det.cli`` (det lane): gives
    ``whisker delta --llm`` a stable prior snapshot to diff the next aggregate
    rebuild against. A no-op on the first aggregate build in ``out_dir`` (no
    ``report-merged.json`` yet).
    """
    merged_path = out_dir / "report-merged.json"
    if merged_path.exists():
        shutil.copy2(merged_path, out_dir / "report-merged.prev.json")
        logger.debug("Snapshotted %s -> report-merged.prev.json", merged_path)


def _build_merged_report(
    backend: SqliteBackend, *, run_started_at: str | None = None,
) -> None:
    """Build ``report-merged.md/json`` from existing sidecars on disk.

    Reads all whisker and tapetum sidecars, pairs them by PID, and writes the
    aggregate report.  Pure disk I/O, no LLM calls, no sidecar mutation.
    Called after full-corpus runs and by ``--fuse-only``.

    ``run_started_at`` (ISO 8601 UTC), when given, is the timestamp this
    adjudication run began: rows whose sidecar ``evaluated_at`` predates it
    (or is absent) are marked ``replayed`` in the merged report (B2). Left
    ``None`` for ``--fuse-only`` (no evaluation happened at all in that
    invocation, so every row with tapetum data is definitionally a replay).
    """
    out_dir = _find_llm_dir(backend)
    if out_dir is None:
        logger.info("No LLM lane directory (whisker/llm) found; skipping merged report.")
        return

    tapetum_files = sorted(out_dir.glob("*.whisker.tapetum.json"))
    if not tapetum_files:
        logger.info("No tapetum sidecars found in %s; skipping merged report.", out_dir)
        return

    whisker_sidecars: list[dict] = []
    tapetum_by_pid: dict[str, dict] = {}

    for tf in tapetum_files:
        tap_data = _read_tapetum_sidecar(tf)
        if tap_data is None:
            continue
        pid = tap_data.get("pid", "")
        if not pid:
            continue
        whisker_sidecars.append(_read_whisker_sidecar(pid, backend))
        tapetum_by_pid[pid.upper()] = tap_data

    all_whisker = _collect_sidecar_dicts(backend)
    covered_pids = {w.get("pid", "").upper() for w in whisker_sidecars}
    for wsc in all_whisker:
        if wsc.get("pid", "").upper() not in covered_pids:
            whisker_sidecars.append(wsc)

    rows = build_merged_json(
        whisker_sidecars, tapetum_by_pid, run_started_at=run_started_at,
    )
    _snapshot_prev_merged_report(out_dir)
    md_path, json_path = persist_merged_report(rows, out_dir)
    logger.info("Merged report -> %s, %s", md_path, json_path)

    footer = render_terminal_fusion_footer(rows)
    logger.info(footer)


def _fuse_only(backend: SqliteBackend, inspect: bool) -> None:
    """Recompute fusion blocks from existing sidecar pairs, no LLM calls."""
    out_dir = _find_llm_dir(backend)
    if out_dir is None:
        logger.info("No LLM lane directory (whisker/llm) found.")
        return

    tapetum_files = sorted(out_dir.glob("*.whisker.tapetum.json"))
    if not tapetum_files:
        logger.info("No tapetum sidecars found in %s", out_dir)
        return

    updated = 0
    counts: dict[str, int] = {}
    inspect_pairs: list[tuple[dict, dict | None]] = []

    for tf in tapetum_files:
        tap_data = _read_tapetum_sidecar(tf)
        if tap_data is None:
            continue

        pid = tap_data.get("pid", "")
        if not pid:
            continue

        whisker_sc = _read_whisker_sidecar(pid, backend)
        fusion = fuse_verdicts(whisker_sc, tap_data)
        tap_data["fusion"] = fusion.to_dict()

        tf.write_text(
            json.dumps(tap_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        updated += 1
        rule = fusion.combined_rule
        counts[rule] = counts.get(rule, 0) + 1

        if inspect:
            inspect_pairs.append((whisker_sc, tap_data))

    logger.info(
        "Fused %d sidecar pairs: %s",
        updated,
        ", ".join(f"{k}={v}" for k, v in sorted(counts.items())),
    )

    _build_merged_report(backend)

    if inspect and inspect_pairs:
        pids = [w.get("pid", "") for w, _ in inspect_pairs]
        report_path = _persist_inspect(inspect_pairs, pids, backend)
        logger.info("Inspection report -> %s", report_path)


def _service_api_key(service_config: dict) -> str:
    """Resolve one service credential in memory without logging or persisting it."""
    raw_key = service_config.get("api_key", "")
    if isinstance(raw_key, str) and raw_key.startswith("$"):
        return os.environ.get(raw_key[1:], "")
    if isinstance(raw_key, str) and raw_key:
        return raw_key
    env_name = service_config.get("api_key_env", "")
    return (
        os.environ.get(env_name, "")
        if isinstance(env_name, str) and env_name
        else ""
    )


async def _probe_llm_endpoint(
    overrides: dict[str, str],
    services_config: dict,
) -> None:
    """Fail loudly before fan-out if the LLM endpoint is unreachable.

    Mirrors the pre-flight server gate used by olmocr and docling: one
    ``GET {server_root}/health`` against the effective ``fast``-slot service.
    A cold or restarting pod otherwise burns the first N papers of a batch
    as connection errors. Exits the process on failure (CLI-level gate).
    """
    prompt = PipelinePrompt.load("whisker", "llm/llm.md")
    services = dict(prompt.services)
    services.update(overrides)
    name = services.get("fast") or next(iter(services.values()), "")
    service_config = services_config.get("services", {}).get(name, {})
    base_url = _sanitize_base_url(service_config.get("base_url", ""))
    if not base_url:
        logger.warning(
            "Health gate: no endpoint URL resolvable for service '%s'; "
            "skipping probe",
            name,
        )
        return
    url = base_url.rstrip("/").removesuffix("/v1") + "/health"
    api_key = _service_api_key(service_config)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        async with httpx.AsyncClient(
            timeout=_HEALTH_PROBE_TIMEOUT_SECONDS
        ) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error(
            "LLM endpoint '%s' failed health probe (%s): %s",
            name,
            url,
            exc,
        )
        sys.exit(1)
    logger.info("LLM endpoint '%s' healthy (%s)", name, url)


def _find_llm_dir(backend: SqliteBackend) -> Path | None:
    """Locate the LLM lane directory (``whisker/llm``) from any known paper."""
    papers = backend.list_all_paper_ids()
    for paper in papers:
        pid = paper if isinstance(paper, str) else getattr(paper, "paper_id", str(paper))
        d = _llm_output_dir(pid, backend)
        if d.exists():
            return d
    return None


def _source_file_size(pid: str, backend: SqliteBackend) -> int:
    """Source file size in bytes, 0 on error (sorts last in LJF)."""
    try:
        return backend.get_source_path(pid).stat().st_size
    except Exception:
        return 0


def _historical_duration_seconds(pid: str, backend: SqliteBackend) -> float | None:
    """Last successful sidecar duration, or None when absent."""
    try:
        out_dir = _llm_output_dir(pid, backend)
        sc_path = out_dir / f"{sidecar_path(pid, backend).stem}.tapetum.json"
        if not sc_path.exists():
            return None
        data = _read_sidecar_dict(sc_path)
        if data is None:
            return None
        duration = data.get("duration_seconds")
        if isinstance(duration, (int, float)) and duration > 0:
            return float(duration)
    except Exception:
        return None
    return None


def _predicted_work_seconds(pid: str, backend: SqliteBackend) -> float:
    """LJF key: historical duration, else PDF pages, else source KiB."""
    hist = _historical_duration_seconds(pid, backend)
    if hist is not None:
        return hist
    if _source_kind(pid, backend) == "pdf":
        pages = _pdf_page_count(pid, backend)
        if pages:
            return pages * _LJF_SECONDS_PER_PDF_PAGE
    return _source_file_size(pid, backend) / 1024.0


def _sort_pids_ljf(pids: list[str], backend: SqliteBackend) -> list[str]:
    """Sort PIDs by descending predicted work (longest job first).

    Prefer last-run ``duration_seconds``. Cold papers fall back to PDF
    page count, then source size. Tie-break is ascending PID.
    """
    return sorted(
        pids, key=lambda pid: (-_predicted_work_seconds(pid, backend), pid),
    )


async def _run(args: argparse.Namespace) -> int:
    try:
        backend = open_backend(args.workspace)
    except EnvironmentError:
        logger.error("WG21_DATA_DIR not set and --workspace not provided")
        return 1

    if args.fuse_only:
        _fuse_only(backend, inspect=args.inspect)
        return _EXIT_OK

    overrides = _parse_service_overrides(args.service)

    pids: list[str] = []
    full_run = False
    if args.review_all:
        sidecars = _collect_sidecar_dicts(backend)
        pids = select_candidates(sidecars)
        logger.info("Selected %d candidates for adjudication", len(pids))
    elif args.pids:
        pids = [p.upper() for p in args.pids]
    else:
        _all_converted = [
            pid for pid in backend.list_all_paper_ids()
            if backend.get_paper_md_path(pid).exists()
        ]
        pids = _sort_pids_ljf(_all_converted, backend)
        full_run = True
        logger.info("Full run: %d converted papers", len(pids))

    if not pids:
        logger.info("No papers to adjudicate.")
        return _EXIT_OK

    # Service registry is loaded once per batch (SERVICES.toml parse + backend
    # construction) and shared by every paper; adjudicate_paper falls back to
    # loading it per call only when a caller passes none (library contract).
    services_config = _load_services_config()
    registry = load_services()
    would_skip = getattr(args, "would_skip", False)
    if not would_skip:
        await _probe_llm_endpoint(overrides, services_config)

    # Resolve the approved ideal verifier from the established deep intent,
    # with the prompt's default service as fallback. The AgentBackend is
    # constructed once per batch and reused by both source-aware lanes.
    prompt = PipelinePrompt.load("whisker", "llm/llm.md")
    services = dict(prompt.services)
    services.update(overrides)
    ideal_service = services.get("deep") or services["default"]
    ideal_backend = registry.services.get(ideal_service)
    ideal_agent = (
        AgentBackend(
            ideal_backend,
            max_tokens=_IDEAL_MAX_TOKENS,
            thinking_budget=0,
            slot_name="ideal",
            service_name=ideal_service,
        )
        if ideal_backend is not None
        else None
    )
    ideals_dir = find_ideals_dir()

    # Judge agent for the PDF-text-layer lane. Resolved from the same
    # ## Services block (+ per-slot overrides) as the text lane, so
    # --service repoints both lanes consistently. None = --text-only.
    judge_agent = None
    if not args.text_only:
        judge_service = services.get("deep") or services["default"]
        judge_backend = registry.services.get(judge_service)
        if judge_backend is not None:
            # PdfJudgment is small (verdict + <=5 short quotes + 60-word
            # reasoning); 1536 covers worst-case output with margin.
            # Backend retry on finish_reason=length catches outliers.
            # Pod default flipped to thinking-on (live probe 2026-09-03);
            # thinking_budget=0 maps to chat_template_kwargs.enable_thinking=false
            # in pipeline.model_backends and pins the validated non-think request shape.
            judge_agent = AgentBackend(
                judge_backend, max_tokens=1536,
                thinking_budget=0,
                slot_name="judge", service_name=judge_service,
            )
            logger.info(
                "PDF-text-layer judge lane enabled: service=%s", judge_service,
            )
        else:
            logger.warning(
                "PDF judge lane disabled: service '%s' not found in "
                "SERVICES.toml. PDF papers will use the markdown text lane.",
                judge_service,
            )

    # Precompute prompt hashes and schema JSON for fingerprinting (cheap, once).
    # The pdf-judge lane makes two kinds of structured calls (the monolith
    # PdfJudgment call and scoped PageJudgment escalations), so both the
    # monolith and page-escalation prompts/schemas feed the fingerprint: a
    # change to either invalidates cached results.
    effective_services = dict(prompt.services)
    effective_services.update(overrides)
    _pdf_prompt_text = _pdf_prompt_contract(
        service=effective_services.get("fast") or effective_services.get("default")
    )
    _pdf_schema_json = _pdf_schema_contract()
    _text_prompt_text = _text_prompt_contract(
        prompt,
        service=effective_services.get("fast") or effective_services.get("default"),
    )
    _text_schema_json = _text_schema_contract()
    _effective_models = _effective_model_contract(
        effective_services,
        services_config,
    )

    if would_skip:
        # A2 dry run: resolve the same fingerprint each pid WOULD get on a
        # live run (identical lane/prompt/schema selection, no health probe,
        # no LLM call, no sidecar or report writes), then print and exit.
        for pid in pids:
            kind = _source_kind(pid, backend)
            use_pdf_judge = kind == "pdf" and judge_agent is not None
            if use_pdf_judge:
                fp_lane, fp_prompt, fp_schema = (
                    "pdf_textlayer_judge", _pdf_prompt_text, _pdf_schema_json,
                )
            else:
                fp_lane, fp_prompt, fp_schema = (
                    "text", _text_prompt_text, _text_schema_json,
                )
            coverage_mode = _coverage_mode_for_paper(
                args, is_pdf_lane=use_pdf_judge,
            )
            ideal_text: str | None = None
            if ideals_dir is not None:
                paper_ideal = ideal_path(pid, ideals_dir)
                if paper_ideal is not None:
                    try:
                        ideal_text = paper_ideal.read_bytes().decode("utf-8")
                    except (OSError, UnicodeDecodeError):
                        ideal_text = None
            incremental_dry = (
                not getattr(args, "force", False) if full_run
                else getattr(args, "incremental", False)
            )
            decision = "run"
            if incremental_dry:
                try:
                    fp = _compute_fingerprint(
                        pid, backend, fp_lane, fp_prompt, _effective_models,
                        fp_schema,
                        ideal_text=ideal_text,
                        coverage_mode=coverage_mode,
                    )
                    skip, skip_kind, skip_detail = _fingerprint_skip_decision(
                        pid, backend, fp,
                        retry_errors=getattr(args, "retry_errors", False),
                    )
                    if skip:
                        # Exact wording pinned by --would-skip's contract
                        # (differs from the friendlier live skip log line).
                        decision = {
                            "match": "skip (fingerprint match)",
                            "superset": f"skip (superset: {skip_detail})",
                            "tombstone": "skip (tombstone)",
                        }[skip_kind]
                except Exception:
                    decision = "run"
            print(f"{pid}: {decision}")
        return _EXIT_OK

    # Batch mode mirrors `whisker --all`: a progress bar plus a final footer,
    # with per-call log noise quieted. Single-paper runs keep the full logs.
    batch = len(pids) > 1
    retry_filter: _RetryCountFilter | None = None
    bar_handler: _BarAwareHandler | None = None
    if batch:
        for name in _BATCH_QUIET_LOGGERS:
            logging.getLogger(name).setLevel(logging.WARNING)
        root = logging.getLogger()
        bar_handler = _BarAwareHandler()
        if root.handlers:
            bar_handler.setFormatter(root.handlers[0].formatter)
        retry_filter = _RetryCountFilter()
        bar_handler.addFilter(retry_filter)
        root.handlers = [bar_handler]

    def _draw(done: int, current: str) -> None:
        length = render_progress(done, len(pids), label=current)
        if bar_handler is not None:
            bar_handler.bar_len = length if done < len(pids) else 0
            bar_handler.redraw = (
                (lambda: render_progress(done, len(pids), label=current))
                if done < len(pids)
                else None
            )

    per_paper_log = logger.debug if batch else logger.info
    counts = {
        "pass": 0, "review": 0, "not-llm-readable": 0, "error": 0, "skipped": 0,
        "skipped_fingerprint": 0, "skipped_superset": 0,
        "skipped_tombstone": 0,
    }
    started = time.monotonic()
    # B2/B3: this run's start time, threaded through to the merged report so
    # it can tell "evaluated this run" from "replayed from a prior run"
    # (fingerprint-skip papers keep their old evaluated_at).
    run_started_at = _utc_now_iso()
    if full_run:
        incremental = not getattr(args, "force", False)
    else:
        incremental = getattr(args, "incremental", False)

    concurrency = max(1, args.concurrency)
    if args.concurrency < 1:
        logger.warning("--concurrency %d clamped to 1", args.concurrency)
    if concurrency > _MAX_TESTED_CONCURRENCY:
        logger.warning(
            "--concurrency %d exceeds the tested ceiling of %d; queueing "
            "and per-request latency above that are unmeasured "
            "(research/research/llm-batching sweep)",
            concurrency,
            _MAX_TESTED_CONCURRENCY,
        )
    # asyncio.Semaphore wakes waiters FIFO, so with N=1 papers still run
    # strictly in input order (the serial default is behavior-identical to
    # the old sequential loop). With N>1, papers are independent: each has
    # its own state and writes its own sidecar file, no shared mutation.
    sem = asyncio.Semaphore(concurrency)
    done = 0
    retrying = False

    async def _adjudicate_one(
        index: int, pid: str
    ) -> tuple[
        int, str, str | None, tuple[dict, dict | None] | None, str | None,
    ]:
        """Firewalled per-paper worker: (index, pid, verdict|None,
        inspect_pair, skip_kind). ``skip_kind`` is one of ``match``,
        ``superset``, ``tombstone`` on a fingerprint skip, else ``None``."""
        nonlocal done
        async with sem:
            paper_started = time.monotonic()
            kind = _source_kind(pid, backend)
            use_pdf_judge = kind == "pdf" and judge_agent is not None
            lane_label = "pdf-judge" if use_pdf_judge else "text"
            paper_ideal = (
                ideal_path(pid, ideals_dir)
                if ideals_dir is not None
                else None
            )
            ideal_text: str | None = None
            ideal_read_error: Exception | None = None
            if paper_ideal is not None:
                try:
                    ideal_text = paper_ideal.read_bytes().decode("utf-8")
                except (OSError, UnicodeDecodeError) as exc:
                    ideal_read_error = exc

            async def _attach_ideal(
                result,
                debug_log: list[str] | None,
            ) -> None:
                if paper_ideal is None:
                    return
                if ideal_read_error is not None:
                    raise ideal_read_error
                if ideal_agent is None:
                    raise RuntimeError(
                        f"{pid}: ideal verifier service "
                        f"'{ideal_service}' is unavailable"
                    )
                candidate_md = backend.get_paper_md(pid)
                result.ideal_verification = await asyncio.wait_for(
                    verify_against_ideal(
                        ideal_agent,
                        candidate_md,
                        ideal_text,
                        debug_log=debug_log,
                    ),
                    timeout=_PAPER_TIMEOUT_SECONDS,
                )

            if use_pdf_judge:
                fp_lane = "pdf_textlayer_judge"
                fp_prompt = _pdf_prompt_text
                fp_model = _effective_models
                fp_schema = _pdf_schema_json
            else:
                fp_lane = "text"
                fp_prompt = _text_prompt_text
                fp_model = _effective_models
                fp_schema = _text_schema_json
            coverage_mode = _coverage_mode_for_paper(
                args, is_pdf_lane=use_pdf_judge,
            )

            if incremental and ideal_read_error is None:
                try:
                    fp = _compute_fingerprint(
                        pid, backend, fp_lane, fp_prompt, fp_model,
                        fp_schema,
                        ideal_text=ideal_text,
                        coverage_mode=coverage_mode,
                    )
                    skip, skip_kind, skip_detail = _fingerprint_skip_decision(
                        pid, backend, fp,
                        retry_errors=getattr(args, "retry_errors", False),
                    )
                    if skip_kind == "retry":
                        per_paper_log(
                            "%s [%s] retrying (previous error, "
                            "--retry-errors)",
                            pid, lane_label,
                        )
                        # Fall through: do not skip, re-adjudicate.
                    elif skip:
                        # A2: elevated to INFO (not per_paper_log) so a warm
                        # run shows what it skipped even in batch mode.
                        logger.info(
                            "%s [%s] skipped (%s)",
                            pid, lane_label,
                            _skip_reason_label(skip_kind, skip_detail),
                        )
                        # B3: keep this paper's fusion current against the
                        # CURRENT det sidecar even though the LLM result is
                        # reused unchanged (pure recompute, no LLM call).
                        _refresh_fusion_on_skip(pid, backend)
                        if not retrying:
                            done += 1
                            if batch:
                                _draw(done, pid)
                        return index, pid, "skipped", None, skip_kind
                except Exception:
                    fp = None
            else:
                fp = None

            per_paper_log(
                "Adjudicating %s [%s/%s] (%d/%d) ...",
                pid, kind, lane_label, index + 1, len(pids),
            )
            verdict_str: str | None = None
            inspect_pair: tuple[dict, dict | None] | None = None
            progress: dict = {}
            try:
                if use_pdf_judge:
                    judge_debug: list[str] | None = [] if args.debug else None
                    page_count_for_timeout: int | None = None
                    if getattr(args, "all_pages", False):
                        page_count_for_timeout = _pdf_page_count(pid, backend)
                    _is_audit = bool(
                        getattr(args, "all_pages", False)
                        or getattr(args, "exhaustive_units", False)
                        or getattr(args, "inspect", False)
                    )
                    judge_result = None
                    lane_exc = None
                    try:
                        judge_result = await asyncio.wait_for(
                            judge_pdf_extraction(
                                pid, backend, judge_agent,
                                debug_log=judge_debug,
                                all_pages=getattr(args, "all_pages", False),
                                exhaustive_units=(
                                    getattr(args, "exhaustive_units", False)
                                    or getattr(args, "inspect", False)
                                ),
                                code_boundary=_is_audit,
                                enable_page_escalations=_is_audit,
                                progress=progress,
                                guard_tag=GUARD_TAG,
                            ),
                            timeout=_pdf_judge_timeout_seconds(
                                page_count_for_timeout
                                if getattr(args, "all_pages", False)
                                else None,
                                code_boundary=_is_audit,
                            ),
                        )
                        try:
                            await _attach_ideal(judge_result, judge_debug)
                        except Exception as ideal_exc:
                            judge_result.ideal_pending = True
                            logger.warning(
                                "%s: ideal verification failed (%s: %s); "
                                "persisting judge result without ideal "
                                "(ideal_pending)",
                                pid,
                                type(ideal_exc).__name__,
                                ideal_exc,
                            )
                    except BaseException as exc:
                        lane_exc = exc
                        raise
                    finally:
                        # Flush the full accumulated list even when a later
                        # metadata/page/unit call fails. This runs before the
                        # outer firewall replaces a stale result with an error
                        # tombstone; write_debug_file preserves every call and
                        # output already appended by AgentBackend.
                        if (
                            judge_debug
                            and hasattr(backend, "get_debug_md_path")
                        ):
                            debug_path = backend.get_debug_md_path(
                                pid, tool="tapetum_llm"
                            )
                            try:
                                debug_path.parent.mkdir(
                                    parents=True, exist_ok=True
                                )
                                write_debug_file(debug_path, judge_debug)
                            except OSError:
                                logger.debug(
                                    "Could not write debug transcript for %s",
                                    pid,
                                )
                        if (
                            args.trace
                            and hasattr(backend, "get_trace_md_path")
                        ):
                            try:
                                trace_path = backend.get_trace_md_path(
                                    pid, tool="tapetum_llm"
                                )
                                ts = datetime.now(timezone.utc).strftime(
                                    "%Y-%m-%d %H:%M:%S UTC"
                                )
                                header = f"# Tapetum_Llm {pid} {ts}\n\n"
                                body = render_pdf_trace(
                                    pid, progress, judge_result, lane_exc,
                                )
                                trace_path.parent.mkdir(
                                    parents=True, exist_ok=True
                                )
                                trace_path.write_text(
                                    header + body,
                                    encoding="utf-8",
                                )
                            except Exception as trace_exc:
                                # Diagnostics firewall: this runs inside the
                                # lane's finally, so a render or write failure
                                # must never replace the paper's real outcome.
                                logger.warning(
                                    "%s: could not write trace transcript "
                                    "(%s: %s)",
                                    pid,
                                    type(trace_exc).__name__,
                                    trace_exc,
                                )
                    if fp is None:
                        try:
                            fp = _compute_fingerprint(
                                pid, backend, fp_lane, fp_prompt, fp_model,
                                fp_schema,
                                ideal_text=ideal_text,
                                coverage_mode=coverage_mode,
                            )
                        except Exception:
                            pass
                    paper_duration = time.monotonic() - paper_started
                    out_path = _persist_lane_result(
                        judge_result, backend, fingerprint=fp,
                        duration_seconds=paper_duration,
                    )
                    verdict_str = judge_result.verdict
                    per_paper_log(
                        "%s [pdf-judge] -> %s (conf=%.2f, missing=%d, "
                        "nid=%.4f, duration=%.1fs) -> %s",
                        pid, verdict_str,
                        judge_result.confidence,
                        len(judge_result.missing_content),
                        judge_result.text_nid,
                        paper_duration,
                        out_path,
                    )
                    if args.inspect:
                        wsc = _read_whisker_sidecar(pid, backend)
                        tap_dict = judge_result.to_sidecar_dict()
                        tap_dict["fusion"] = fuse_verdicts(wsc, tap_dict).to_dict()
                        inspect_pair = (wsc, tap_dict)
                else:
                    if getattr(args, "all_pages", False):
                        raise RuntimeError(
                            f"--all-pages is PDF-only; {pid} is an HTML paper "
                            f"(use --exhaustive-units for section-level coverage)"
                        )
                    result = await asyncio.wait_for(
                        adjudicate_paper(
                            pid,
                            backend,
                            debug=args.debug,
                            trace=args.trace,
                            exhaustive=getattr(args, "exhaustive_units", False)
                            or getattr(args, "inspect", False),
                            service_overrides=overrides,
                            registry=registry,
                        ),
                        timeout=_text_lane_timeout_seconds(),
                    )
                    if result.status == "error":
                        raise RuntimeError(
                            f"{pid}: pipeline returned status='error' "
                            f"({result.primary_concern})"
                        )
                    ideal_debug: list[str] | None = [] if args.debug else None
                    try:
                        try:
                            await _attach_ideal(result, ideal_debug)
                        except Exception as ideal_exc:
                            result.ideal_pending = True
                            logger.warning(
                                "%s: ideal verification failed (%s: %s); "
                                "persisting result without ideal "
                                "(ideal_pending)",
                                pid,
                                type(ideal_exc).__name__,
                                ideal_exc,
                            )
                    finally:
                        if (
                            ideal_debug
                            and hasattr(backend, "get_debug_md_path")
                        ):
                            debug_path = backend.get_debug_md_path(
                                pid, tool="tapetum_llm"
                            )
                            try:
                                existing = (
                                    debug_path.read_text(encoding="utf-8")
                                    if debug_path.exists()
                                    else ""
                                )
                                entries = (
                                    [existing, *ideal_debug]
                                    if existing
                                    else ideal_debug
                                )
                                debug_path.parent.mkdir(
                                    parents=True,
                                    exist_ok=True,
                                )
                                write_debug_file(debug_path, entries)
                            except OSError:
                                logger.debug(
                                    "Could not append ideal debug transcript "
                                    "for %s",
                                    pid,
                                )
                    if fp is None:
                        try:
                            fp = _compute_fingerprint(
                                pid, backend, fp_lane, fp_prompt, fp_model,
                                fp_schema,
                                ideal_text=ideal_text,
                                coverage_mode=coverage_mode,
                            )
                        except Exception:
                            pass
                    paper_duration = time.monotonic() - paper_started
                    out_path = _persist_result(
                        result, backend, fingerprint=fp,
                        duration_seconds=paper_duration,
                    )
                    verdict_str = result.suggested_verdict
                    per_paper_log(
                        "%s [text] -> %s (confidence=%.2f, escalated=%s, "
                        "duration=%.1fs) -> %s",
                        pid, verdict_str,
                        result.confidence, result.escalated,
                        paper_duration,
                        out_path,
                    )
                    if args.inspect:
                        wsc = _read_whisker_sidecar(pid, backend)
                        tap_dict = result.to_dict()
                        tap_dict["fusion"] = fuse_verdicts(wsc, tap_dict).to_dict()
                        inspect_pair = (wsc, tap_dict)
            except Exception as exc:
                if batch:
                    logger.error(
                        "Failed to adjudicate %s [%s]: %s: %s",
                        pid, lane_label,
                        type(exc).__name__, exc,
                    )
                else:
                    logger.exception("Failed to adjudicate %s [%s]", pid, lane_label)
                _write_error_tombstone(
                    pid,
                    backend,
                    exc,
                    partial_progress=progress if progress else None,
                    fingerprint=fp,
                    duration_seconds=time.monotonic() - paper_started,
                )
                if args.inspect:
                    inspect_pair = (_read_whisker_sidecar(pid, backend), None)
        if not retrying:
            done += 1
            if batch:
                _draw(done, pid)
        return index, pid, verdict_str, inspect_pair, None

    if batch:
        _draw(0, pids[0])
    records = list(await asyncio.gather(
        *(_adjudicate_one(i, pid) for i, pid in enumerate(pids))
    ))

    # This-run errors only (verdict_str is None). Fingerprint-skipped
    # papers return "skipped" and are never retried here. Prior-run
    # tombstones stay behind --retry-errors.
    if any(verdict_str is None for _i, _p, verdict_str, _ip, _sk in records):
        incremental = False
        retrying = True
        try:
            for wave in range(1, _ERROR_RETRY_ROUNDS + 1):
                errors = [
                    (index, pid)
                    for index, pid, verdict_str, _ip, _sk in records
                    if verdict_str is None
                ]
                if not errors:
                    break
                retry_c = min(_ERROR_RETRY_CONCURRENCY, concurrency)
                sem = asyncio.Semaphore(retry_c)
                logger.info(
                    "Retry wave %d: %d paper(s) at concurrency %d",
                    wave,
                    len(errors),
                    retry_c,
                )
                retry = await asyncio.gather(
                    *(_adjudicate_one(index, pid) for index, pid in errors)
                )
                by_index = {row[0]: row for row in retry}
                records = [by_index.get(row[0], row) for row in records]
        finally:
            retrying = False

    # gather() returns results in argument (= input) order regardless of
    # completion order, so counts and the inspect report are deterministic.
    inspect_pairs: list[tuple[dict, dict | None]] = []
    for _index, _pid, verdict_str, inspect_pair, skip_kind in records:
        if verdict_str is None:
            counts["error"] += 1
        else:
            counts[verdict_str] = counts.get(verdict_str, 0) + 1
        if skip_kind == "match":
            counts["skipped_fingerprint"] += 1
        elif skip_kind == "superset":
            counts["skipped_superset"] += 1
        elif skip_kind == "tombstone":
            counts["skipped_tombstone"] += 1
        if inspect_pair is not None:
            inspect_pairs.append(inspect_pair)

    if batch:
        elapsed = time.monotonic() - started
        retry_summary = retry_filter.summary() if retry_filter is not None else "0"
        skipped = counts["skipped"]
        evaluated = len(pids) - skipped
        parts = [
            f"=== {len(pids)} total: {evaluated} evaluated, "
            f"{counts['pass']} pass, {counts['review']} review, "
            f"{counts['not-llm-readable']} fail, {counts['error']} error",
        ]
        if skipped:
            # A2: breakdown by skip reason, not just a bare total, so a warm
            # run's footer tells you WHY papers were skipped.
            parts.append(
                f", {skipped} skipped (incremental: "
                f"{counts['skipped_fingerprint']} fingerprint, "
                f"{counts['skipped_superset']} superset, "
                f"{counts['skipped_tombstone']} tombstone)"
            )
        parts.append(f" ({retry_summary}) in {elapsed:.1f}s ===")
        logger.info("".join(parts))

    if args.inspect and inspect_pairs:
        report_path = _persist_inspect(inspect_pairs, pids, backend)
        logger.info("Inspection report -> %s", report_path)

    if full_run:
        _build_merged_report(backend, run_started_at=run_started_at)

    return 1 if counts["error"] > 0 else _EXIT_OK


def main(argv: list[str] | None = None) -> None:
    """Console-script entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stderr,
    )
    # Load the gitignored .env so services declaring api_key = "$VAR"
    # (e.g. alliance-pod -> ALLIANCE_POD_KEY) resolve their key.
    load_dotenv(find_dotenv(usecwd=True))
    args = _parse_args(argv)
    rc = asyncio.run(_run(args))
    sys.exit(rc)


if __name__ == "__main__":
    main()
