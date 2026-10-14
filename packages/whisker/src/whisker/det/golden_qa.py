#
# Copyright (c) 2026 Sean Parsons (seanpatrick2013@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Golden QA orchestration helpers: locate a paper's source, convert it with
tomd, and score it against its blessed ideal.

Scoring and gap helpers are pure (return data). The three orchestrator
functions that drive the dev workflow -- `generate_ideal`, `bless_stem`, and
`rebless_stems` -- own their own persistence: they write the ideal file and
the baselines manifest as part of their contract. The CLI calls them and
reports results; it does not re-persist what they have already written.

Migrated from tomd.lib.golden_qa to whisker (golden-QA ownership
consolidation). Subprocess bridges (_call_whisker_score_file/check_facts)
converted to in-process calls since this module now lives inside whisker.

``generate_ideal`` and ``render_pdf_pages`` are local (tomd conversion and
PyMuPDF). They support the on-demand QA verbs only; they are not wired
into the deterministic (1) lane. Network download and LLM review helpers
have been removed: callers must stage a local source first.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from tomd.lib.check_content import compute_content_coverage
from tomd.lib.html import convert_html
from tomd.lib.pdf import run_pipeline

from whisker import constants as C
from whisker.det.anchors import anchor_spec_from_dict, check_anchors
from whisker.det.bench import table_score
from whisker.det.code_fence_align import compare_code_fence_boundaries
from whisker.det.golden_compare import compare
from whisker.det.golden_gaps import draft_issues, locate_gaps
from whisker.det.paragraph_align import compare_paragraph_boundaries
from whisker.facts import check_facts, parse_facts_jsonl
from whisker.gates import run_gates
from whisker.metrics import content_recall, mhs, normalized_text, text_nid

_log = logging.getLogger(__name__)

_SOURCES_SUBDIR = "sources"
_IDEALS_SUBDIR = "ideals"


def source_dir(golden_dir: Path) -> Path:
    return golden_dir / _SOURCES_SUBDIR


def ideal_path(golden_dir: Path, stem: str) -> Path:
    """Path to the blessed ideal for `stem` (ideals/<stem>.md)."""
    return golden_dir / _IDEALS_SUBDIR / f"{stem}.md"


def find_source(stem: str, golden_dir: Path) -> Path | None:
    """The staged source for `stem`: a PDF or HTML file under sources/."""
    for ext in (".pdf", ".html"):
        candidate = source_dir(golden_dir) / f"{stem}{ext}"
        if candidate.is_file():
            return candidate
    return None


_RENDER_DPI = 150


def stage_source(stem: str, source_path: Path, golden_dir: Path) -> Path:
    """Copy a source file into the golden dir as `<stem>.<ext>`; return the dest."""
    ext = source_path.suffix.lower()
    if ext not in (".pdf", ".html"):
        raise ValueError(f"unsupported source type {ext!r}; expected .pdf or .html")
    dest = source_dir(golden_dir) / f"{stem}{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, dest)
    return dest


def render_pdf_pages(pdf_path: Path, out_dir: Path, dpi: int = _RENDER_DPI) -> list[Path]:
    """Render each page of `pdf_path` to a PNG in `out_dir`; return written paths.

    [DEFERRED] Page images are the vision input for the tomd-review step.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    doc = pymupdf.open(str(pdf_path))
    try:
        for i, page in enumerate(doc):
            dest = out_dir / f"page-{i + 1:03d}.png"
            page.get_pixmap(dpi=dpi).save(str(dest))
            written.append(dest)
    finally:
        doc.close()
    return written


_RENDER_SUBDIR = ".render"


def generate_ideal(stem: str, golden_dir: Path) -> Path:
    """Seed a candidate ideal for `stem` from tomd's OWN conversion (no LLM).

    [DEFERRED] The starting draft for the human to correct.
    """
    src = find_source(stem, golden_dir)
    if src is None:
        raise FileNotFoundError(
            f"No staged source for {stem}; run 'whisker qa add {stem} <path>' first")
    markdown = run_pipeline(src).md if src.suffix == ".pdf" else convert_html(src)[0]
    dest = ideal_path(golden_dir, stem)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(markdown, encoding="utf-8", newline="\n")
    return dest


_REVIEW_SKILL_REL = ".claude/skills/tomd-review/SKILL.md"


def _repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / ".claude").is_dir():
            return candidate
    return start


def review_skill_text(golden_dir: Path) -> str:
    """The committed tomd-review skill contract, or '' if not present."""
    skill = _repo_root(golden_dir) / _REVIEW_SKILL_REL
    return skill.read_text(encoding="utf-8") if skill.is_file() else ""


_REVIEW_FALLBACK_CONTRACT = (
    "You are a structural reviewer. Treat the source as the ground truth for "
    "STRUCTURE. Compare the candidate markdown to it and emit a punch-list of "
    "STRUCTURAL divergences only (heading levels, list nesting, code fencing, "
    "tables, front-matter key order, chrome/TOC leakage). Do NOT flag wording, "
    "paraphrase, or verbatim content: a human owns content fidelity. If there "
    "are none, say exactly 'No structural divergences found.'")


def build_review_prompt(
    stem: str, src: Path, golden_dir: Path, candidate_md: str, skill_text: str = "",
) -> str:
    """The structural-review prompt: the tomd-review contract plus concrete inputs.

    [DEFERRED] LLM-driven review.
    """
    contract = skill_text.strip() or _REVIEW_FALLBACK_CONTRACT
    if src.suffix == ".pdf":
        pages = golden_dir / _RENDER_SUBDIR / stem
        source_block = (
            f"The source is a PDF; read its page images in {pages} "
            "(page-001.png, page-002.png, ...) with the Read tool. They are the "
            "ground truth for structure. Do not read plain extracted PDF text.")
    else:
        html = src.read_text(encoding="utf-8", errors="replace")
        source_block = ("The source HTML (ground truth for structure) follows "
                        f"between the markers:\n<<<SOURCE\n{html}\nSOURCE>>>")
    return (
        f"{contract}\n\n---\n\nReview the WG21 paper {stem.upper()} candidate ideal "
        f"below against its source.\n\n{source_block}\n\nCANDIDATE markdown under "
        f"review:\n<<<CANDIDATE\n{candidate_md}\nCANDIDATE>>>\n\nOutput ONLY the "
        "punch-list.")


def tomd_markdown(stem: str, golden_dir: Path) -> str | None:
    """Convert the staged source for `stem`, dispatching by source type."""
    src = find_source(stem, golden_dir)
    if src is None:
        return None
    if src.suffix == ".pdf":
        return run_pipeline(src).md
    return convert_html(src)[0]


def is_unedited_seed(stem: str, golden_dir: Path) -> bool:
    """True if `stem`'s ideal is byte-identical to tomd's current conversion."""
    md = tomd_markdown(stem, golden_dir)
    ideal = ideal_path(golden_dir, stem)
    if md is None or not ideal.is_file():
        return False
    return ideal.read_text(encoding="utf-8") == md


def score_stem(stem: str, golden_dir: Path) -> dict[str, float]:
    """Per-axis structural score of tomd's output vs the blessed `<stem>.ideal.md`."""
    md = tomd_markdown(stem, golden_dir)
    if md is None:
        raise FileNotFoundError(f"no staged source for {stem}")
    ideal = ideal_path(golden_dir, stem).read_text(encoding="utf-8")
    score = compare(md, ideal)
    return {name: round(ax.score, 2) for name, ax in score.axes.items()}


@dataclass(frozen=True)
class AxisReport:
    axis: str
    current: float
    baseline: float | None
    delta: float | None
    detail: str
    sub: dict[str, float]


@dataclass(frozen=True)
class ScoreResult:
    """Full score output: structural axes plus optional whisker and comprehension panels."""
    axes: list[AxisReport]
    whisker: dict | None
    comprehension: dict | None


_FACTS_SUBDIR = "facts"
_ANCHORS_SUBDIR = "anchors"


def facts_path(golden_dir: Path, stem: str) -> Path:
    """Path to the facts JSONL for `stem` (facts/<stem>.facts.jsonl)."""
    return golden_dir / _FACTS_SUBDIR / f"{stem}.facts.jsonl"


def anchors_path(golden_dir: Path, stem: str) -> Path:
    """Path to the anchors JSON for `stem` (anchors/<stem>.anchors.json)."""
    return golden_dir / _ANCHORS_SUBDIR / f"{stem}.anchors.json"


_VALID_FACT_TYPES = frozenset({"present", "absent", "order", "table", "math"})
_VALID_CHECKED_VALUES = frozenset({"verified", "draft"})

_FACTS_TEMPLATE = """\
# Facts for {pid}
# One JSON object per line. type: present | absent | order | table | math
# checked: "verified" (gates in whisker qa-score) or "draft" (advisory only)
#
# Examples:
# {{"type": "present", "text": "the as-if rule", "checked": "draft"}}
# {{"type": "order", "sequence": ["Abstract", "Motivation"], "checked": "draft"}}
# {{"type": "table", "cell": "int", "right": "signed", "checked": "draft"}}
"""


def validate_facts_jsonl(text: str) -> list[str]:
    """Validate JSONL fact assertions. Returns list of error strings (empty = valid)."""
    errors = []
    for lineno, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {lineno}: invalid JSON: {exc}")
            continue
        if not isinstance(record, dict):
            errors.append(f"line {lineno}: expected JSON object")
            continue
        fact_type = record.get("type")
        if fact_type not in _VALID_FACT_TYPES:
            errors.append(
                f"line {lineno}: unknown type {fact_type!r}; "
                f"expected one of {sorted(_VALID_FACT_TYPES)}")
        checked = record.get("checked")
        if checked not in _VALID_CHECKED_VALUES:
            errors.append(
                f"line {lineno}: checked must be 'verified' or 'draft', got {checked!r}")
        if fact_type in {"present", "absent", "math"} and "text" not in record:
            errors.append(f"line {lineno}: type={fact_type!r} requires 'text' field")
        if fact_type == "order" and "sequence" not in record:
            errors.append(f"line {lineno}: type='order' requires 'sequence' list")
        if fact_type == "table" and "cell" not in record:
            errors.append(f"line {lineno}: type='table' requires 'cell' field")
    return errors


_VALID_ANCHOR_SURFACES = frozenset({"normalized", "raw"})

_ANCHORS_TEMPLATE = """\
{{
  "pid": "{pid}",
  "surface": "normalized",
  "must_contain": [],
  "must_not_contain": [],
  "ordered": [],
  "patterns": []
}}
"""


def validate_anchors_json(data: dict) -> list[str]:
    """Validate an anchor spec dict. Returns list of error strings (empty = valid)."""
    if not isinstance(data, dict):
        return ["root must be a JSON object"]
    errors = []
    surface = data.get("surface", "normalized")
    if surface not in _VALID_ANCHOR_SURFACES:
        errors.append(
            f"surface must be one of {sorted(_VALID_ANCHOR_SURFACES)}, got {surface!r}")
    for key in ("must_contain", "must_not_contain", "ordered"):
        val = data.get(key, [])
        if not isinstance(val, list):
            errors.append(f"{key!r} must be a list")
        elif not all(isinstance(s, str) for s in val):
            errors.append(f"{key!r} must be a list of strings")
    patterns = data.get("patterns", [])
    if not isinstance(patterns, list):
        errors.append("'patterns' must be a list of objects")
    else:
        for i, p in enumerate(patterns):
            if not isinstance(p, dict) or "regex" not in p:
                errors.append(f"patterns[{i}]: must have 'regex' key")
    return errors


def score_report(stem: str, golden_dir: Path, manifest: Path) -> list[AxisReport]:
    """Per-axis current score vs committed baseline, with deltas and sub-signals."""
    md = tomd_markdown(stem, golden_dir)
    if md is None:
        raise FileNotFoundError(f"no staged source for {stem}")
    ideal = ideal_path(golden_dir, stem).read_text(encoding="utf-8")
    score = compare(md, ideal)
    base = (json.loads(manifest.read_text(encoding="utf-8")).get(stem, {})
            if manifest.exists() else {})
    rows = []
    for name, ax in score.axes.items():
        b = base.get(name)
        delta = (ax.score - b) if b is not None else None
        rows.append(AxisReport(name, ax.score, b, delta, ax.detail, ax.sub))
    return rows


# ---------------------------------------------------------------------------
# In-process whisker scoring (replaces subprocess bridge)
# ---------------------------------------------------------------------------

def _whisker_score_inline(
    md_text: str,
    *,
    ref_md: str | None = None,
    source_path: Path | None = None,
) -> dict | None:
    """In-process equivalent of the old ``whisker score-file --json`` subprocess.

    Returns the same payload dict that ``whisker score-file --json`` would
    print to stdout, or None on failure. Replaces the old subprocess bridge
    now that this module lives inside whisker.
    """
    try:
        pid = "inline"
        gates = run_gates(md_text)

        ref_nid = ref_teds = ref_mhs = ref_overall = ref_content_recall = None
        if ref_md is not None:
            ref_nid = text_nid(normalized_text(md_text), normalized_text(ref_md))
            ref_teds = table_score(md_text, ref_md)
            ref_mhs = mhs(md_text, ref_md)
            ref_overall = (ref_nid + ref_teds + ref_mhs) / 3.0
            ref_content_recall = content_recall(md_text, ref_md)

        cov = drift = u_cov = u_drift = None
        missing_regions: list[dict] = []
        extra_regions: list[dict] = []
        source_format: str | None = None
        paragraph = None
        fence = None
        if source_path is not None and source_path.is_file():
            try:
                r = compute_content_coverage(source_path, md_text, paper_id=pid)
                cov, drift = r.coverage, r.drift
                u_cov, u_drift = r.unigram_coverage, r.unigram_drift
                source_format = r.source_format
                missing_regions = [
                    {"page": reg.page, "token_start": reg.token_start,
                     "token_end": reg.token_end, "sample": reg.sample}
                    for reg in r.missing_regions[:C.REGION_DETAIL_CAP]
                ]
                extra_regions = [
                    {"page": reg.page, "token_start": reg.token_start,
                     "token_end": reg.token_end, "sample": reg.sample}
                    for reg in r.extra_regions[:C.REGION_DETAIL_CAP]
                ]
                paragraph = compare_paragraph_boundaries(source_path, md_text)
                fence = compare_code_fence_boundaries(source_path, md_text)
            except Exception:
                _log.debug("content coverage failed in golden_qa inline scoring",
                           exc_info=True)

        hard: list[str] = []
        soft: list[str] = []
        for g in gates:
            if not g.passed:
                hard.append(f"gate:{g.name}:{g.detail or 'failed'}")
        if u_cov is not None:
            if u_cov < C.UNIGRAM_COVERAGE_FAIL_EDGE:
                hard.append(f"unigram coverage {u_cov:.3f} < {C.UNIGRAM_COVERAGE_FAIL_EDGE}")
            elif u_cov < C.UNIGRAM_COVERAGE_REVIEW_EDGE:
                soft.append(f"unigram coverage {u_cov:.3f} in review band")
        if u_drift is not None and u_drift > C.DRIFT_SOFT_EDGE:
            soft.append(f"unigram drift {u_drift:.3f} > {C.DRIFT_SOFT_EDGE}")
        if ref_nid is not None and ref_nid < C.REF_NID_ADVISORY_EDGE:
            soft.append(f"ref nid {ref_nid:.3f} low (advisory)")
        if (paragraph is not None
                and paragraph.merged_count >= C.PARAGRAPH_MERGE_SOFT_COUNT):
            soft.append(
                f"{paragraph.merged_count} source paragraph break(s) missing from "
                f"the candidate (advisory)")
        if (fence is not None
                and fence.total_findings >= C.CODE_FENCE_SOFT_COUNT):
            parts: list[str] = []
            if fence.prose_in_fence_count:
                parts.append(f"{fence.prose_in_fence_count} prose line(s) inside fence")
            if fence.code_outside_fence_count:
                parts.append(
                    f"{fence.code_outside_fence_count} code line(s) outside fence")
            soft.append(f"code fence boundary mismatch: {', '.join(parts)} (advisory)")

        verdict = "not-llm-readable" if hard else "review" if soft else "pass"

        def _r(v: float | None) -> float | None:
            return round(v, 4) if v is not None else None

        return {
            "pid": pid,
            "verdict": verdict,
            "hard_flags": sorted(hard),
            "soft_flags": sorted(soft),
            "gates": [{"name": g.name, "passed": g.passed, "detail": g.detail}
                      for g in gates],
            "ref_nid": _r(ref_nid),
            "ref_teds": _r(ref_teds),
            "ref_mhs": _r(ref_mhs),
            "ref_overall": _r(ref_overall),
            "content_recall": _r(ref_content_recall),
            "coverage": _r(cov),
            "drift": _r(drift),
            "unigram_coverage": _r(u_cov),
            "unigram_drift": _r(u_drift),
            "source_format": source_format,
            "missing_regions": missing_regions,
            "extra_regions": extra_regions,
            "paragraph_alignment": paragraph.to_dict() if paragraph else None,
            "fence_alignment": fence.to_dict() if fence else None,
        }
    except Exception:
        _log.debug("whisker inline scoring failed", exc_info=True)
        return None


def _check_facts_inline(
    stem: str, golden_dir: Path, md_text: str,
) -> dict | None:
    """In-process equivalent of the old ``whisker check-facts --json`` subprocess.

    Returns parsed JSON payload or None. None means either no facts/anchors
    files exist (normal for new papers) or an internal error.
    """
    fp = facts_path(golden_dir, stem)
    ap = anchors_path(golden_dir, stem)
    if not fp.exists() and not ap.exists():
        return None
    try:
        pid = stem

        fact_report = None
        if fp.exists():
            facts = parse_facts_jsonl(fp.read_text(encoding="utf-8"), pid=pid)
            fact_report = check_facts(md_text, facts, pid=pid)

        anchor_report = None
        if ap.exists():
            spec = anchor_spec_from_dict(
                json.loads(ap.read_text(encoding="utf-8")), pid=pid)
            anchor_report = check_anchors(md_text, spec)

        failed = False
        if fact_report is not None:
            for c in fact_report.failures():
                if c.verified:
                    failed = True
                    break
        if anchor_report is not None and not anchor_report.passed:
            failed = True

        return {
            "pid": pid,
            "verdict": "not-llm-readable" if failed else "pass",
            "facts": fact_report.to_dict() if fact_report is not None else None,
            "anchors": anchor_report.to_dict() if anchor_report is not None else None,
        }
    except Exception:
        _log.debug("whisker inline check-facts failed", exc_info=True)
        return None


def _format_region_snippets(whisker_data: dict) -> list[str]:
    """Format whisker missing/extra region snippets as bullet lines."""
    lines = []
    for reg in whisker_data.get("missing_regions", []):
        page = f" (p.{reg['page']})" if reg.get("page") else ""
        lines.append(f"- Missing{page}: `{reg['sample']}`")
    for reg in whisker_data.get("extra_regions", []):
        lines.append(f"- Extra: `{reg['sample']}`")
    return lines


def issue_for_stem(stem: str, golden_dir: Path) -> list[str]:
    """Locate gaps for `stem` and draft one ready-to-file issue per defect axis."""
    md = tomd_markdown(stem, golden_dir)
    if md is None:
        raise FileNotFoundError(f"no staged source for {stem}")
    ideal = ideal_path(golden_dir, stem).read_text(encoding="utf-8")
    gaps = locate_gaps(md, ideal)
    scores = {name: ax.score for name, ax in compare(md, ideal).axes.items()}
    drafts = draft_issues(stem, gaps, scores)
    if not drafts:
        return drafts
    src = find_source(stem, golden_dir)
    whisker_data = _whisker_score_inline(md, ref_md=ideal, source_path=src)
    if whisker_data:
        snippets = _format_region_snippets(whisker_data)
        if snippets:
            drafts[0] = (drafts[0].rstrip() + "\n\n### Localized gaps\n\n"
                         + "\n".join(snippets))
    return drafts


_MIN_IDEAL_COVERAGE = 0.75
_MAX_IDEAL_DRIFT = 0.20


def score_result(stem: str, golden_dir: Path, manifest: Path) -> ScoreResult:
    """Full score: structural axes, whisker metrics panel, comprehension panel."""
    md = tomd_markdown(stem, golden_dir)
    if md is None:
        raise FileNotFoundError(f"no staged source for {stem}")
    ideal_text = ideal_path(golden_dir, stem).read_text(encoding="utf-8")
    score = compare(md, ideal_text)
    base = (json.loads(manifest.read_text(encoding="utf-8")).get(stem, {})
            if manifest.exists() else {})
    axes = []
    for name, ax in score.axes.items():
        b = base.get(name)
        delta = (ax.score - b) if b is not None else None
        axes.append(AxisReport(name, ax.score, b, delta, ax.detail, ax.sub))
    src = find_source(stem, golden_dir)
    whisker = _whisker_score_inline(md, ref_md=ideal_text, source_path=src)
    comprehension = _check_facts_inline(stem, golden_dir, md)
    return ScoreResult(axes=axes, whisker=whisker, comprehension=comprehension)


@dataclass(frozen=True)
class FidelityVerdict:
    ok: bool
    coverage: float
    drift: float
    reason: str = ""


def fidelity_verdict(source_path: Path, candidate_md: str) -> FidelityVerdict:
    """Coarse "not gutted" guard: does the candidate ideal still contain the
    source's content?"""
    r = compute_content_coverage(source_path, candidate_md)
    problems = []
    if r.coverage < _MIN_IDEAL_COVERAGE:
        problems.append(f"coverage {r.coverage:.3f} < {_MIN_IDEAL_COVERAGE}")
    if r.drift > _MAX_IDEAL_DRIFT:
        problems.append(f"drift {r.drift:.3f} > {_MAX_IDEAL_DRIFT}")
    return FidelityVerdict(
        ok=not problems, coverage=r.coverage, drift=r.drift,
        reason="; ".join(problems))


def bless_stem(
    stem: str, golden_dir: Path, manifest: Path,
) -> dict[str, float]:
    """Validate `<stem>.ideal.md` against its source, then merge its baseline
    row into `manifest`. Raises ValueError if the candidate fails the gate."""
    src = find_source(stem, golden_dir)
    if src is None:
        raise FileNotFoundError(f"no staged source for {stem}")
    ideal = ideal_path(golden_dir, stem).read_text(encoding="utf-8")
    verdict = fidelity_verdict(src, ideal)
    if not verdict.ok:
        raise ValueError(f"{stem} failed fidelity gate: {verdict.reason}")
    if is_unedited_seed(stem, golden_dir):
        raise ValueError(
            f"{stem}: ideal is byte-identical to tomd's output (an uncorrected "
            "`generate` seed). Correct its structure against the source before "
            "blessing.")
    whisker_data = _whisker_score_inline(ideal)
    if whisker_data is None:
        raise ValueError(
            f"{stem}: whisker gate unreachable (inline scoring failed). "
            "The structural gate cannot be verified, so the bless is refused.")
    failed_gates = [g for g in whisker_data.get("gates", []) if not g["passed"]]
    if failed_gates:
        details = ", ".join(
            f"{g['name']}: {g['detail'] or 'failed'}" for g in failed_gates
        )
        raise ValueError(f"{stem} failed structural gates: {details}")
    row = score_stem(stem, golden_dir)
    data = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    data[stem] = row
    manifest.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return row


_SCORE_EPSILON = 1e-9


@dataclass(frozen=True)
class ReblessOutcome:
    stem: str
    old: dict[str, float]
    new: dict[str, float]
    lowered: dict[str, tuple[float, float]]
    whisker_verdict: str | None = None


def rebless_stems(
    stems: list[str], golden_dir: Path, manifest: Path, *, force: bool = False,
) -> list[ReblessOutcome]:
    """Recompute baselines for `stems` and write them, ratcheting UP only."""
    data = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    missing = [s for s in stems if s not in data]
    if missing:
        raise ValueError(
            f"stems not in manifest (use `bless` first): {missing}")
    updated = dict(data)
    outcomes: list[ReblessOutcome] = []
    for stem in stems:
        old = data.get(stem, {})
        new = score_stem(stem, golden_dir)
        lowered = {ax: (old[ax], new[ax]) for ax in new
                   if ax in old and new[ax] < old[ax] - _SCORE_EPSILON}
        md = tomd_markdown(stem, golden_dir)
        whisker_verdict: str | None = None
        if md is not None:
            src = find_source(stem, golden_dir)
            ideal_text = ideal_path(golden_dir, stem).read_text(encoding="utf-8")
            w = _whisker_score_inline(md, ref_md=ideal_text, source_path=src)
            if w is not None:
                whisker_verdict = w.get("verdict")
        outcomes.append(ReblessOutcome(stem, old, new, lowered,
                                       whisker_verdict=whisker_verdict))
        updated[stem] = new
    if not force:
        offenders = {o.stem: o.lowered for o in outcomes if o.lowered}
        if offenders:
            raise ValueError(
                f"rebless would lower baselines (use --force to override): {offenders}")
    manifest.write_text(
        json.dumps(updated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return outcomes
