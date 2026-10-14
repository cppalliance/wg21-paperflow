# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# One-shot calibration draw: stratify by unigram_coverage band, not whisker
# verdict. Overwrites sample_manifest.json. Safe to delete after use.

from __future__ import annotations

import json
import re
import sys
import traceback
from pathlib import Path

from paperstore import SqliteBackend
from whisker.constants import UNIGRAM_COVERAGE_FAIL_EDGE, UNIGRAM_COVERAGE_REVIEW_EDGE
from whisker.det.score import score_paper

# Sibling standalone modules live in this directory, not in the installed
# whisker package. No __init__.py on purpose: these are scripts, not a package.
_CALIBRATION_DIR = Path(__file__).resolve().parent
if str(_CALIBRATION_DIR) not in sys.path:
    sys.path.insert(0, str(_CALIBRATION_DIR))

from calibration_sampler import ScoredPaper, sample_calibration_candidates  # noqa: E402

WORKSPACE = Path(r"C:\Users\sabo2\Desktop\cppalliance\data")
MANIFEST_PATH = Path(__file__).with_name("sample_manifest.json")
SEED = 42
N_PER_BAND = 15

EXCLUDED_GOLDEN_PIDS = [
    "cwg1",
    "p0533r9",
    "p0957r8",
    "p1068r11",
    "p1122r3",
    "p2040r0",
    "p3411r5",
    "p3556r0",
    "p3953r0",
    "p4020r0",
    "p4182r0",
    "p4228r0",
]

EXCLUDED_UPPER = {pid.upper() for pid in EXCLUDED_GOLDEN_PIDS}
_PAPER_MD_RE = re.compile(r"^[a-z0-9]+\.md$")

VERDICT_TO_BAND = {"fail": "low", "review": "mid", "pass": "high"}
BAND_ORDER = ("low", "mid", "high")
BAND_TO_VERDICT = {"low": "fail", "mid": "review", "high": "pass"}


def coverage_band(unigram_coverage: float) -> str:
    if unigram_coverage < UNIGRAM_COVERAGE_FAIL_EDGE:
        return "low"
    if unigram_coverage < UNIGRAM_COVERAGE_REVIEW_EDGE:
        return "mid"
    return "high"


def discover_pids(backend: SqliteBackend) -> list[str]:
    papers_dir = backend.workspace_dir / "paperstore"
    pids: list[str] = []
    for path in sorted(papers_dir.glob("*.md")):
        if not _PAPER_MD_RE.match(path.name):
            continue
        pid = path.stem.upper()
        if pid in EXCLUDED_UPPER:
            continue
        pids.append(pid)
    return pids


def main() -> int:
    backend = SqliteBackend(WORKSPACE)
    pids = discover_pids(backend)

    scored_papers: list[ScoredPaper] = []
    scoring_failures: list[dict[str, str]] = []
    band_counts = {"low": 0, "mid": 0, "high": 0}

    for pid in pids:
        try:
            result = score_paper(pid, backend, reference_engine=None)
            band = coverage_band(result.unigram_coverage)
            band_counts[band] += 1
            scored_papers.append(
                ScoredPaper(
                    pid=pid,
                    verdict=BAND_TO_VERDICT[band],  # type: ignore[arg-type]
                    unigram_coverage=result.unigram_coverage,
                )
            )
        except Exception as exc:  # noqa: BLE001 — per-paper catch, do not abort batch
            scoring_failures.append({"pid": pid, "reason": f"{type(exc).__name__}: {exc}"})

    population_size = len(scored_papers)
    sample = sample_calibration_candidates(scored_papers, n_per_band=N_PER_BAND, seed=SEED)

    # Map sampler verdict bands back to coverage bands for manifest accounting.
    verdict_to_coverage = {"pass": "high", "review": "mid", "fail": "low"}
    draw_by_coverage: dict[str, dict[str, int]] = {}
    for band_draw in sample.bands:
        cov = verdict_to_coverage[band_draw.verdict]
        draw_by_coverage[cov] = {
            "available": band_draw.available,
            "requested": band_draw.requested,
            "drawn": band_draw.drawn,
        }

    candidates = [
        {
            "pid": paper.pid,
            "coverage_band": VERDICT_TO_BAND[paper.verdict],
            "unigram_coverage": round(paper.unigram_coverage, 4),
        }
        for paper in sample.candidates
    ]

    drawn_pids = {c["pid"] for c in candidates}
    overlap = drawn_pids & EXCLUDED_UPPER
    assert not overlap, f"golden pids leaked into candidates: {sorted(overlap)}"

    manifest = {
        "$schema": "whisker-calibration-sample-manifest-v1",
        "stratification": "unigram_coverage_band",
        "stratification_note": (
            "The 'verdict' tag on each candidate below is a coverage-band label "
            "(low->'fail' tag, mid->'review' tag, high->'pass' tag) chosen ONLY to "
            "reuse sample_calibration_candidates' three-way partition. It is NOT "
            "whisker's own computed verdict, which mixes structural gates with content "
            "coverage and was shown (see PROTOCOL.md) to over-represent structural-only "
            "failures in a verdict-stratified draw."
        ),
        "band_edges": {
            "low": f"< {UNIGRAM_COVERAGE_FAIL_EDGE} (UNIGRAM_COVERAGE_FAIL_EDGE)",
            "mid": f"{UNIGRAM_COVERAGE_FAIL_EDGE} <= x < {UNIGRAM_COVERAGE_REVIEW_EDGE}",
            "high": f">= {UNIGRAM_COVERAGE_REVIEW_EDGE} (UNIGRAM_COVERAGE_REVIEW_EDGE)",
        },
        "seed": SEED,
        "n_per_band": N_PER_BAND,
        "excluded_golden_pids": EXCLUDED_GOLDEN_PIDS,
        "population_size": population_size,
        "bands": [
            {
                "coverage_band": band,
                "available": band_counts[band],
                "requested": N_PER_BAND,
                "drawn": draw_by_coverage.get(band, {}).get("drawn", 0),
            }
            for band in BAND_ORDER
        ],
        "candidates": candidates,
        "scoring_failures": scoring_failures,
    }

    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"population_size={population_size}", file=sys.stderr)
    print(f"band_counts={band_counts}", file=sys.stderr)
    print(f"candidates={len(candidates)}", file=sys.stderr)
    print(f"scoring_failures={len(scoring_failures)}", file=sys.stderr)
    for band in BAND_ORDER:
        d = draw_by_coverage.get(band, {})
        print(
            f"band {band}: available={band_counts[band]} "
            f"requested={N_PER_BAND} drawn={d.get('drawn', 0)}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
