#
# Copyright (c) 2026 Sean Parsons (sean.parsons@muckrack.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Golden QA orchestration helpers: locate a paper's source, convert it with
tomd, and score it against its blessed ideal. Library functions return data;
the bless and regen scripts own persistence.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from tomd.lib.check_content import compute_content_coverage
from tomd.lib.golden_compare import compare
from tomd.lib.golden_gaps import draft_issues, locate_gaps
from tomd.lib.html import convert_html
from tomd.lib.pdf import run_pipeline


# The golden fixtures are organized by role under the golden root.
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


# Default page-render resolution for the generator skill's vision input. 150 dpi
# is plenty to read layout (columns, font sizes, indentation).
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


# wg21.link resolves a paper id to its canonical document; the UA matches the
# project default (mailing.DEFAULT_USER_AGENT) without taking a mailing dep.
_WG21_LINK = "https://wg21.link/"
_USER_AGENT = "paperflow/0.1 (+https://github.com/cppalliance/wg21-paperflow)"


def _fetch(url: str) -> tuple[str, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req) as resp:
        return resp.geturl(), resp.read()


def _source_ext(final_url: str, data: bytes) -> str:
    if final_url.lower().endswith(".pdf") or data[:5] == b"%PDF-":
        return ".pdf"
    return ".html"


def download_source(stem: str, golden_dir: Path, *, opener=_fetch) -> Path:
    """Download the WG21 source for `stem` from wg21.link into the golden dir.

    Follows the wg21.link redirect to the canonical PDF or HTML and saves it as
    `<stem>.<ext>`. Network is used only here; the rest of the QA flow is offline.
    `opener(url) -> (final_url, bytes)` is injectable for testing.
    """
    final_url, data = opener(_WG21_LINK + stem)
    dest = source_dir(golden_dir) / f"{stem}{_source_ext(final_url, data)}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest


def render_pdf_pages(pdf_path: Path, out_dir: Path, dpi: int = _RENDER_DPI) -> list[Path]:
    """Render each page of `pdf_path` to a PNG in `out_dir`; return written paths.

    Page images are the vision input for the tomd-review step (PDF sources):
    transient build artifacts, not committed fixtures.
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


# Page renders (the LLM review's vision input for PDFs) are transient build
# artifacts under this subdir, not committed fixtures.
_RENDER_SUBDIR = ".render"


def generate_ideal(stem: str, golden_dir: Path) -> Path:
    """Seed a candidate ideal for `stem` from tomd's OWN conversion (no LLM).

    The starting draft for the human to correct. It runs the same conversion
    `score_stem` compares against, so a freshly seeded ideal is byte-identical to
    tomd's output and scores 1.0 on every axis. tomd already gets the content
    right; the human edits the draft's STRUCTURE toward what the source shows
    (heading levels, list nesting, fences, tables), and that correction is what
    opens the gap the gate then tracks. Cheap and instant: no model, no tokens.
    Optionally run `review_ideal` for an LLM punch-list of suspected divergences,
    then `bless_stem` (with human review) is the gate.
    """
    src = find_source(stem, golden_dir)
    if src is None:
        src = download_source(stem, golden_dir)
    markdown = run_pipeline(src).md if src.suffix == ".pdf" else convert_html(src)[0]
    dest = ideal_path(golden_dir, stem)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(markdown, encoding="utf-8", newline="\n")
    return dest


# Structural review (the optional LLM step) uses the best available model via the
# Claude CLI. It compares the source to a candidate ideal and emits a punch-list
# of STRUCTURAL divergences, which plays to the LLM's strength: judgment over a
# short defect list, not transcription of a whole document. The
# model-sovereignty/determinism doctrine that governs dissect/agora does not apply
# (a human reads the punch-list and edits by hand); and the pipeline framework has
# no vision support for the PDF page-image path, so the Claude CLI is the engine.
_REVIEW_MODEL = "opus"
_REVIEW_TIMEOUT_S = 600
# The tomd-review skill is the single source of truth for the review contract,
# shared by interactive use and this command. The command reads it and embeds it
# deterministically (rather than relying on model-driven skill auto-invocation).
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


# Fallback contract when the skill file is absent (e.g. a partial clone): a stub
# so the command still works, degraded. The skill is the authoritative version.
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

    `skill_text` is the canonical contract (the tomd-review SKILL.md), embedded so
    the command and interactive use share one source of truth; when empty a stub
    fallback is used. PDF source points at the pre-rendered page images; HTML is
    embedded inline.
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


def _claude_runner(prompt: str, golden_dir: Path) -> str:
    # Prompt goes on stdin, not argv: it embeds the full source and can exceed the
    # OS argument-length limit. Read-only tools: review never writes.
    result = subprocess.run(
        ["claude", "-p", "--model", _REVIEW_MODEL, "--allowedTools", "Read",
         "--add-dir", str(golden_dir), "--output-format", "text"],
        cwd=str(golden_dir), input=prompt, text=True,
        capture_output=True, timeout=_REVIEW_TIMEOUT_S, check=True)
    return result.stdout


def review_ideal(stem: str, golden_dir: Path, *, runner=_claude_runner) -> str:
    """LLM structural review of `stem`'s candidate ideal against its source.

    The optional de-anchoring step: because the seed comes from tomd, a human can
    rubber-stamp tomd's own structural mistakes. This asks an LLM to compare the
    source to the candidate ideal and return a punch-list of suspected STRUCTURAL
    divergences (never verbatim content). Returns the punch-list text; the caller
    prints it. For PDFs it renders the page images if they are not already staged.
    `runner(prompt, golden_dir) -> text` is injectable for testing.
    """
    src = find_source(stem, golden_dir)
    if src is None:
        raise FileNotFoundError(f"no staged source for {stem}")
    ideal = ideal_path(golden_dir, stem)
    if not ideal.is_file():
        raise FileNotFoundError(
            f"no candidate ideal at {ideal}; run `generate` first")
    if src.suffix == ".pdf":
        pages_dir = golden_dir / _RENDER_SUBDIR / stem
        if not (pages_dir.is_dir() and any(pages_dir.glob("page-*.png"))):
            render_pdf_pages(src, pages_dir)
    prompt = build_review_prompt(
        stem, src, golden_dir, ideal.read_text(encoding="utf-8"),
        review_skill_text(golden_dir))
    return runner(prompt, golden_dir)


def tomd_markdown(stem: str, golden_dir: Path) -> str | None:
    """Convert the staged source for `stem`, dispatching by source type."""
    src = find_source(stem, golden_dir)
    if src is None:
        return None
    if src.suffix == ".pdf":
        return run_pipeline(src).md
    return convert_html(src)[0]


def is_unedited_seed(stem: str, golden_dir: Path) -> bool:
    """True if `stem`'s ideal is byte-identical to tomd's current conversion.

    The signature of a raw `generate` seed that was never hand-corrected: a
    genuine structural correction makes the ideal differ from tomd's output (and
    the comparator scores semantically, so even a structurally-perfect corrected
    ideal differs byte-wise from tomd's emit). Identity therefore means the
    correction step was skipped, so the ideal tests nothing the byte-exact
    snapshot net does not already cover. Returns False if either side is missing.
    """
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


def score_report(stem: str, golden_dir: Path, manifest: Path) -> list[AxisReport]:
    """Per-axis current score vs committed baseline, with deltas and sub-signals.

    The human-facing superset of :func:`score_stem`: each row carries the
    committed baseline, the delta, the axis detail string, and (for heading)
    the sub-signals, so the CLI can print a self-explaining table.
    """
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


def issue_for_stem(stem: str, golden_dir: Path) -> list[str]:
    """Locate gaps for `stem` and draft one ready-to-file issue per defect axis."""
    md = tomd_markdown(stem, golden_dir)
    if md is None:
        raise FileNotFoundError(f"no staged source for {stem}")
    ideal = ideal_path(golden_dir, stem).read_text(encoding="utf-8")
    gaps = locate_gaps(md, ideal)
    scores = {name: ax.score for name, ax in compare(md, ideal).axes.items()}
    return draft_issues(stem, gaps, scores)


# Coverage-vs-source is a coarse "not gutted" guard, not a paraphrase detector
# (see fidelity_verdict): a faithful ideal and tomd's own output score nearly the
# same (~0.84 / ~0.11 on P4228R0). These floors catch an LLM that drops or guts a
# large fraction of the paper while clearing faithful ideals with margin.
# Recalibrate as the blessed set grows.
_MIN_IDEAL_COVERAGE = 0.75
_MAX_IDEAL_DRIFT = 0.20


@dataclass(frozen=True)
class FidelityVerdict:
    ok: bool
    coverage: float
    drift: float
    reason: str = ""


def fidelity_verdict(source_path: Path, candidate_md: str) -> FidelityVerdict:
    """Coarse "not gutted" guard: does the candidate ideal still contain the
    source's content?

    Catches an ideal that DROPPED or gutted a large fraction of the paper. It
    does NOT detect paraphrase: shingled coverage is blind to rewording that
    keeps the vocabulary, and a faithful ideal scores about the same as tomd's
    own output (~0.84 coverage / ~0.11 drift on P4228R0). The human review at
    bless time is the authority on verbatim content; do not lean on this gate
    for that.
    """
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
    row = score_stem(stem, golden_dir)
    data = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    data[stem] = row
    manifest.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return row


# Float slack for baseline comparison: deterministic comparator and pipeline,
# so this only absorbs last-ULP cross-machine noise.
_SCORE_EPSILON = 1e-9


@dataclass(frozen=True)
class ReblessOutcome:
    stem: str
    old: dict[str, float]
    new: dict[str, float]
    lowered: dict[str, tuple[float, float]]  # axis -> (old, new) where new < old


def rebless_stems(
    stems: list[str], golden_dir: Path, manifest: Path, *, force: bool = False,
) -> list[ReblessOutcome]:
    """Recompute baselines for `stems` and write them, ratcheting UP only.

    The routine ratchet after a verified tomd improvement: it raises each
    paper's baseline to the current score. It refuses (raises ValueError,
    leaving the manifest untouched) if any axis would drop below its committed
    baseline, unless `force` is set, so a careless rebless cannot enshrine the
    regression the gate exists to catch.
    """
    data = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    updated = dict(data)
    outcomes: list[ReblessOutcome] = []
    for stem in stems:
        old = data.get(stem, {})
        new = score_stem(stem, golden_dir)
        lowered = {ax: (old[ax], new[ax]) for ax in new
                   if ax in old and new[ax] < old[ax] - _SCORE_EPSILON}
        outcomes.append(ReblessOutcome(stem, old, new, lowered))
        updated[stem] = new
    if not force:
        offenders = {o.stem: o.lowered for o in outcomes if o.lowered}
        if offenders:
            raise ValueError(
                f"rebless would lower baselines (use --force to override): {offenders}")
    manifest.write_text(
        json.dumps(updated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return outcomes
