#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Monthly survey run: corpus load, conversion, and scoring.

Orchestrates: load corpus.json, convert all corpus PDFs with tomd and the
competitor (balanced primary, fast and fast-disable-ocr sensitivity, each
twice for Lane 1), then score Lane 1/2/3 exactly per runbook. Library
functions return data; the CLI persists.
"""

from __future__ import annotations

import difflib
import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tomd.lib.pdf import run_pipeline

from whisker.det.bench import BenchRow, aggregate, run_bench
from whisker.det.golden import normalize_for_exact_lane
from whisker.facts import check_facts, parse_facts_jsonl

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

# Competitor configurations now live on the adapter as MODES, because they are
# that project's vocabulary: Marker's `disable_ocr` means nothing to the next
# converter. The runner only needs to know how many times to repeat each one.
REPEATS = ("a", "b")

# E3 canonicalization: strip leading YAML front-matter and leading H1
_FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_LEADING_H1_RE = re.compile(r"\A#\s+[^\n]+\n+")


def canonicalize_for_lane2(md: str) -> str:
    """Apply E3 canonicalization: strip front-matter then leading H1.

    Per runbook decision E3, applied symmetrically to ideal AND candidate
    before run_bench, so title representation differences do not bias mhs.
    """
    text = _FRONT_MATTER_RE.sub("", md)
    text = _LEADING_H1_RE.sub("", text)
    return text


# ---------------------------------------------------------------------------
# Corpus contract
# ---------------------------------------------------------------------------


@dataclass
class CorpusPaper:
    """A paper entry from corpus.json, with every input path already resolved.

    ``ideal_path`` and ``facts_path`` are carried here rather than left for the
    caller to reconstruct. ``load_corpus`` resolves and validates both, so a
    caller deriving them a second time can only get them wrong: that is exactly
    what happened when the corpus moved into ``corpus/`` and the survey CLI kept
    building v1-era ``<bench>/golden/<pid>.ideal.md`` paths, silently scoring
    Lanes 2 and 3 against files that did not exist.
    """

    pid: str
    pdf_path: Path
    ideal_path: Path
    facts_path: Path
    page_count: int
    structure_class: str


@dataclass
class CorpusContract:
    """Loaded and validated corpus contract."""

    corpus_version: int
    papers: list[CorpusPaper]
    frozen: str


def _find_repo_root(start: Path) -> Path | None:
    """Walk up from *start* looking for the workspace pyproject.toml."""
    for parent in (start, *start.parents):
        if (parent / "pyproject.toml").is_file() and (parent / "packages").is_dir():
            return parent
    return None


def load_corpus(corpus_root: Path) -> CorpusContract:
    """Load corpus.json and validate all required files exist.

    Corpus v2 resolves PDFs and ideals from the canonical tomd fixture tree
    (``packages/tomd/tests/fixtures/golden/``) rather than local copies.
    Facts are expected under ``corpus_root/facts/<pid>.facts.jsonl``.

    Raises RuntimeError if validation fails (missing ideal, facts, etc.).
    """
    corpus_path = corpus_root / "corpus.json"
    if not corpus_path.is_file():
        raise RuntimeError(f"corpus.json not found at {corpus_path}")

    data = json.loads(corpus_path.read_text(encoding="utf-8"))
    corpus_version = data.get("corpus_version")
    if corpus_version is None:
        raise RuntimeError("corpus.json missing corpus_version")

    frozen = data.get("frozen", "")
    papers: list[CorpusPaper] = []

    repo_root = _find_repo_root(corpus_root)

    for entry in data.get("papers", []):
        pid = entry["pid"]

        # Resolve PDF: v2 uses canonical fixture path via repo root
        pdf_rel = entry.get("pdf")
        if pdf_rel and not Path(pdf_rel).is_absolute():
            pdf_path = corpus_root / pdf_rel
        else:
            pdf_path = (
                repo_root / "packages" / "tomd" / "tests" / "fixtures"
                / "golden" / "sources" / f"{pid}.pdf"
            ) if repo_root else corpus_root / "pdfs" / f"{pid}.pdf"

        if not pdf_path.is_file():
            raise RuntimeError(f"PDF not found for {pid}: {pdf_path}")

        # Resolve ideal: canonical tomd golden ideals directory
        if repo_root:
            ideal_path = (
                repo_root / "packages" / "tomd" / "tests" / "fixtures"
                / "golden" / "ideals" / f"{pid}.md"
            )
        else:
            ideal_path = corpus_root / "golden" / f"{pid}.ideal.md"

        if not ideal_path.is_file():
            raise RuntimeError(
                f"Ideal not found for {pid} (corpus_version={corpus_version}): "
                f"{ideal_path}"
            )

        # Facts: look in corpus_root/facts/ first, then legacy golden/
        facts_path = corpus_root / "facts" / f"{pid}.facts.jsonl"
        if not facts_path.is_file():
            facts_path = corpus_root / "golden" / f"{pid}.facts.jsonl"
        if not facts_path.is_file():
            raise RuntimeError(
                f"Facts not found for {pid} (corpus_version={corpus_version}): "
                f"{facts_path}"
            )

        papers.append(CorpusPaper(
            pid=pid,
            pdf_path=pdf_path,
            ideal_path=ideal_path,
            facts_path=facts_path,
            page_count=entry.get("page_count", 0),
            structure_class=entry.get("structure_class", ""),
        ))

    if not papers:
        raise RuntimeError("corpus.json has no papers")

    return CorpusContract(
        corpus_version=corpus_version,
        papers=papers,
        frozen=frozen,
    )


# ---------------------------------------------------------------------------
# Conversion orchestration
# ---------------------------------------------------------------------------


@dataclass
class ConversionResult:
    """Result of converting one paper with one config and one repeat."""

    pid: str
    config: str
    repeat: str
    md_path: Path
    exit_code: int
    duration_seconds: float = 0.0



def convert_with_tomd(
    pdf_path: Path,
    out_dir: Path,
    pid: str,
) -> ConversionResult:
    """Convert a PDF using tomd (workspace dependency, direct import)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{pid}.md"

    start = time.monotonic()
    try:
        result = run_pipeline(pdf_path)
        md_path.write_text(result.md, encoding="utf-8")
        exit_code = 0
    except Exception as exc:
        log.error("tomd conversion failed for %s: %s", pid, exc)
        exit_code = 1

    duration = time.monotonic() - start
    return ConversionResult(
        pid=pid, config="default", repeat="a",
        md_path=md_path, exit_code=exit_code,
        duration_seconds=duration,
    )


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_lane1(
    run_a_path: Path,
    run_b_path: Path,
    pid: str,
) -> dict[str, Any]:
    """Lane 1 Stability: compare run-a vs run-b using Whisker normalization."""
    if not run_a_path.is_file() or not run_b_path.is_file():
        return {"pid": pid, "stable": None, "error": "missing file"}

    a_text = normalize_for_exact_lane(run_a_path.read_text(encoding="utf-8"))
    b_text = normalize_for_exact_lane(run_b_path.read_text(encoding="utf-8"))

    stable = a_text == b_text
    result: dict[str, Any] = {"pid": pid, "stable": stable}
    if not stable:
        diff = list(difflib.unified_diff(
            a_text.splitlines(keepends=True),
            b_text.splitlines(keepends=True),
            fromfile="run-a", tofile="run-b", n=2,
        ))
        result["diff_lines"] = len(diff)
    return result


def score_lane2(
    candidate_path: Path,
    ideal_path: Path,
    pid: str,
) -> dict[str, Any] | None:
    """Lane 2 Fidelity: run_bench with E3 canonicalization."""
    if not candidate_path.is_file() or not ideal_path.is_file():
        return None

    candidate = candidate_path.read_text(encoding="utf-8")
    ideal = ideal_path.read_text(encoding="utf-8")

    # E3 canonicalization
    candidate_canon = canonicalize_for_lane2(candidate)
    ideal_canon = canonicalize_for_lane2(ideal)

    rows = run_bench([(pid, candidate_canon, ideal_canon)])
    if not rows:
        return None
    return rows[0].to_dict()


def score_lane3(
    candidate_path: Path,
    facts_path: Path,
    pid: str,
) -> dict[str, Any] | None:
    """Lane 3 Comprehension: check-facts on the uncanonized candidate."""
    if not candidate_path.is_file() or not facts_path.is_file():
        return None

    candidate = candidate_path.read_text(encoding="utf-8")
    facts_text = facts_path.read_text(encoding="utf-8")
    facts = parse_facts_jsonl(facts_text, pid)

    report = check_facts(candidate, facts, pid)
    return report.to_dict()


def aggregate_lane2(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate Lane 2 results using whisker.det.bench.aggregate."""
    bench_rows: list[BenchRow] = []
    for r in rows:
        if r is not None:
            bench_rows.append(BenchRow(
                pid=r["pid"],
                nid=r.get("nid"),
                teds=r.get("teds"),
                mhs=r.get("mhs"),
                overall=r.get("overall"),
                content_recall=r.get("content_recall"),
                reading_order=r.get("reading_order"),
                grits_con=r.get("grits_con"),
            ))
    if not bench_rows:
        return {}
    return aggregate(bench_rows)
