#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Deterministic command implementations for the whisker CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from paperstore.errors import MissingPaperMdError, MissingSourceError
from tomd.lib.check_content import compute_content_coverage

from whisker import constants as C
from whisker.cli_common import open_backend, render_progress, verdict_exit_code
from whisker.det.anchors import anchor_spec_from_dict, check_anchors
from whisker.det.bench import aggregate, run_bench, table_score
from whisker.det.calibrate import (
    CALIBRATION_ARTIFACT_SCHEMA_VERSION,
    DEFAULT_TARGET_FPR_FAIL_EDGE,
    DEFAULT_TARGET_FPR_REVIEW_EDGE,
    HoldoutCalibrationResult,
    InsufficientCalibrationDataError,
    calibrate_threshold_with_holdout,
)
from whisker.det.code_fence_align import (
    CodeFenceAlignment,
    compare_code_fence_boundaries,
)
from whisker.det.corpus_tools import (
    draft_facts_scaffold,
    stratify_candidates,
    write_draft_facts,
)
from whisker.det.delta import DeltaFinding, DeltaResult, compute_delta
from whisker.det.golden import (
    GOLDEN_EXPECTED_SUFFIX,
    GOLDEN_MANIFEST_KIND,
    GOLDEN_MANIFEST_NAME,
    GoldenItem,
    diff_goldens,
    normalize_for_exact_lane,
)
from whisker.det.guard import baseline_from_rows, diff_rows
from whisker.det.paragraph_align import ParagraphAlignment, compare_paragraph_boundaries
from whisker.det.reference import REFERENCE_ENGINES
from whisker.det.report import build_report, render_report_md, render_summary
from whisker.det.score import (
    VERDICT_FAIL,
    VERDICT_PASS,
    VERDICT_REVIEW,
    WhiskerResult,
    score_paper,
    sidecar_path,
    whisker_output_dir,
)
from whisker.facts import FACTS_KIND, check_facts, parse_facts_jsonl
from whisker.gates import run_gates
from whisker.metrics import content_recall, mhs, normalized_text, text_nid

logger = logging.getLogger("whisker")

# The ten verb bodies are this module's public dispatch API: __main__.py
# routes to them and menu.py imports them.
__all__ = [
    "bench_main",
    "calibrate_main",
    "check_facts_main",
    "corpus_main",
    "delta_main",
    "facts_main",
    "golden_main",
    "guard_main",
    "score_file_main",
    "score_main",
]

def _snapshot_prev_report(out_dir: Path) -> None:
    """Copy an existing ``report.json`` to ``report.prev.json`` before overwrite.

    Gives ``whisker delta`` a stable prior snapshot to diff the next run
    against. A no-op on the first run in ``out_dir`` (no ``report.json`` yet).
    """
    report_json_path = out_dir / "report.json"
    if report_json_path.exists():
        shutil.copy2(report_json_path, out_dir / "report.prev.json")



def score_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="whisker", description="QA verdict for tomd conversions")
    parser.add_argument("pids", nargs="*", help="paper ids to score")
    parser.add_argument("--all", action="store_true", help="score every paper in the store")
    parser.add_argument("--json", action="store_true", help="emit JSON to stdout")
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="show every paper (incl. pass) and lift the per-section cap",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="print only the one-line summary footer",
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="append a flag rollup (counts per hard/soft flag)",
    )
    parser.add_argument(
        "--reference",
        choices=REFERENCE_ENGINES,
        default=REFERENCE_ENGINES[0],
        help="reference oracle: score tomd vs an independent converter (default: %(default)s)",
    )
    parser.add_argument(
        "--no-reference", action="store_true",
        help="skip the reference oracle; use structural/coverage signals only",
    )
    parser.add_argument(
        "--no-write", action="store_true",
        help="do not write sidecars or the run report (stdout only)",
    )
    parser.add_argument(
        "--report-dir",
        help="directory for sidecars + report.md/report.json (default: <data>/whisker/det)",
    )
    parser.add_argument(
        "--gate",
        choices=("pass", "review", "not-llm-readable"),
        default="review",
        help="lowest verdict considered acceptable for exit 0 (default: review)",
    )
    parser.add_argument("--workspace", help="override $WG21_DATA_DIR")
    args = parser.parse_args(argv)

    if args.all and args.pids:
        parser.error("pass either PID arguments or --all, not both")
    if not args.all and not args.pids:
        parser.error("provide at least one PID or --all")
    if args.verbose and args.quiet:
        parser.error("pass either --verbose or --quiet, not both")

    try:
        backend = open_backend(args.workspace)
    except EnvironmentError as exc:
        logger.error("%s", exc)
        return C.EXIT_ERROR

    if args.all:
        # Only papers that have been converted are scorable. Filtering here
        # avoids a MissingPaperMdError warning for every un-converted id in the
        # store (the vast majority on a fresh workspace).
        pids = [
            pid for pid in backend.list_all_paper_ids()
            if backend.get_paper_md_path(pid).exists()
        ]
        if not pids:
            logger.error("no converted papers found; run 'paperflow convert' first")
            return C.EXIT_ERROR
    else:
        pids = [p.upper() for p in args.pids]

    reference_engine = None if args.no_reference else args.reference

    results: list[WhiskerResult] = []
    scored_pids: list[str] = []
    errored = 0
    skipped = 0
    total = len(pids)
    started = time.monotonic()
    for idx, pid in enumerate(pids, start=1):
        try:
            result = score_paper(pid, backend, reference_engine=reference_engine)
            results.append(result)
            scored_pids.append(pid)
        except (MissingPaperMdError, MissingSourceError) as exc:
            skipped += 1
            logger.warning("skipping %s: %s", pid, exc)
        except Exception:
            # Batch worker firewall: one paper that trips an upstream
            # extraction/normalization bug must not abort the whole run or
            # discard the results already gathered.
            errored += 1
            logger.exception("error scoring %s (skipped)", pid)
        finally:
            render_progress(idx, total)
    elapsed = time.monotonic() - started

    if not results:
        logger.error("no papers scored (%d errored)", errored)
        return C.EXIT_ERROR
    if errored:
        logger.warning("%d paper(s) errored and were skipped", errored)

    report_md_path: str | None = None
    if not args.no_write:
        out_dir = Path(args.report_dir) if args.report_dir else whisker_output_dir(
            scored_pids[0], backend
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        for pid, result in zip(scored_pids, results):
            sidecar = (
                Path(args.report_dir) / f"{pid.lower()}.whisker.json"
                if args.report_dir
                else sidecar_path(pid, backend)
            )
            sidecar.write_text(
                json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        _snapshot_prev_report(out_dir)
        (out_dir / "report.json").write_text(
            json.dumps(build_report(results), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        report_md = out_dir / "report.md"
        report_md.write_text(render_report_md(results), encoding="utf-8")
        report_md_path = str(report_md)
        logger.info("wrote report + %d sidecar(s) to %s", len(results), out_dir)

    if args.json:
        # stdout stays pure JSON for machines; the human summary would corrupt it.
        print(json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False))
    else:
        print(render_summary(
            results,
            elapsed=elapsed,
            errored=errored,
            skipped=skipped,
            report_path=report_md_path,
            color=sys.stdout.isatty(),
            verbose=args.verbose,
            quiet=args.quiet,
            stats=args.stats,
        ))

    return verdict_exit_code([r.verdict for r in results], args.gate)


def _print_score_file_result(payload: dict) -> None:
    """Human-readable summary of a score-file result."""
    verdict = payload["verdict"]
    mark = {"pass": "PASS", "review": "REVIEW", "not-llm-readable": "FAIL"}.get(verdict, verdict.upper())
    print(f"{payload['pid']}: {mark}")
    for flag in payload.get("hard_flags", []):
        print(f"  FAIL  {flag}")
    for flag in payload.get("soft_flags", []):
        print(f"  soft  {flag}")
    for g in payload.get("gates", []):
        status = "ok  " if g["passed"] else "FAIL"
        detail = f": {g['detail']}" if g.get("detail") else ""
        print(f"  gate {status}  {g['name']}{detail}")
    ref_nid = payload.get("ref_nid")
    if ref_nid is not None:
        print(f"  ref_nid={ref_nid:.4f}  "
              f"ref_teds={payload.get('ref_teds', 0):.4f}  "
              f"ref_mhs={payload.get('ref_mhs', 0):.4f}  "
              f"ref_overall={payload.get('ref_overall', 0):.4f}")
    if payload.get("content_recall") is not None:
        print(f"  content_recall={payload['content_recall']:.4f}")
    if payload.get("unigram_coverage") is not None:
        print(f"  unigram_coverage={payload['unigram_coverage']:.4f}  "
              f"unigram_drift={payload.get('unigram_drift', 0):.4f}")


def score_file_main(argv: list[str]) -> int:
    """whisker score-file: score a markdown file against an optional reference.

    whisker score-file --md FILE [--ref FILE] [--source FILE] [--json]

    Gates always run on --md. Reference NID/TEDS/MHS require --ref.
    Source coverage and region detail require --source.
    Exit codes: 0 pass, 1 error, 3 review, 5 fail.
    """
    parser = argparse.ArgumentParser(prog="whisker score-file")
    parser.add_argument("--md", required=True, type=Path, metavar="FILE",
                        help="Candidate markdown file to score")
    parser.add_argument("--ref", type=Path, metavar="FILE",
                        help="Reference/ideal markdown for NID/TEDS/MHS/content_recall")
    parser.add_argument("--source", type=Path, metavar="FILE",
                        help="Source PDF or HTML for content-coverage and region detail")
    parser.add_argument("--json", action="store_true", dest="json_out",
                        help="Emit JSON to stdout")
    args = parser.parse_args(argv)

    if not args.md.is_file():
        print(f"score-file: {args.md} not found", file=sys.stderr)
        return C.EXIT_ERROR

    md_text = args.md.read_text(encoding="utf-8")
    pid = args.md.stem

    gates = run_gates(md_text)

    ref_nid = ref_teds = ref_mhs = ref_overall = ref_content_recall = None
    if args.ref is not None:
        if not args.ref.is_file():
            print(f"score-file: --ref {args.ref} not found", file=sys.stderr)
            return C.EXIT_ERROR
        ref_md = args.ref.read_text(encoding="utf-8")
        ref_nid = text_nid(normalized_text(md_text), normalized_text(ref_md))
        ref_teds = table_score(md_text, ref_md)
        ref_mhs = mhs(md_text, ref_md)
        ref_overall = (ref_nid + ref_teds + ref_mhs) / 3.0
        ref_content_recall = content_recall(md_text, ref_md)

    cov = drift = u_cov = u_drift = None
    missing_regions: list[dict] = []
    extra_regions: list[dict] = []
    source_format: str | None = None
    paragraph: ParagraphAlignment | None = None
    fence: CodeFenceAlignment | None = None
    if args.source is not None:
        if not args.source.is_file():
            print(f"score-file: --source {args.source} not found", file=sys.stderr)
            return C.EXIT_ERROR
        try:
            r = compute_content_coverage(args.source, md_text, paper_id=pid)
        except Exception as exc:
            print(f"score-file: content coverage failed: {exc}", file=sys.stderr)
            return C.EXIT_ERROR
        cov, drift = r.coverage, r.drift
        u_cov, u_drift = r.unigram_coverage, r.unigram_drift
        source_format = r.source_format

        def _reg(reg) -> dict:
            return {"page": reg.page, "token_start": reg.token_start,
                    "token_end": reg.token_end, "sample": reg.sample}

        missing_regions = [_reg(reg) for reg in r.missing_regions[:C.REGION_DETAIL_CAP]]
        extra_regions = [_reg(reg) for reg in r.extra_regions[:C.REGION_DETAIL_CAP]]
        paragraph = compare_paragraph_boundaries(args.source, md_text)
        fence = compare_code_fence_boundaries(args.source, md_text)

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

    verdict = VERDICT_FAIL if hard else VERDICT_REVIEW if soft else VERDICT_PASS
    exit_code = C.EXIT_FAIL if hard else C.EXIT_REVIEW if soft else C.EXIT_OK

    def _r(v: float | None) -> float | None:
        return round(v, 4) if v is not None else None

    payload = {
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

    if args.json_out:
        print(json.dumps(payload))
        return exit_code

    _print_score_file_result(payload)
    return exit_code


def _load_corpus_pairs(corpus: Path, backend) -> list[tuple[str, str, str]]:
    """Pair every ``<pid>.gt.md`` reference with the staged candidate markdown.

    Shared by ``bench`` and ``guard``: both score the same (pid, candidate,
    reference) triples over a ground-truth corpus directory.
    """
    pairs: list[tuple[str, str, str]] = []
    for ref_file in sorted(corpus.glob("*.gt.md")):
        pid = ref_file.name[: -len(".gt.md")].upper()
        try:
            candidate = backend.get_paper_md(pid)
        except MissingPaperMdError as exc:
            logger.warning("skipping %s: %s", pid, exc)
            continue
        pairs.append((pid, candidate, ref_file.read_text(encoding="utf-8")))
    return pairs


def bench_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="whisker bench", description="Benchmark vs ground truth")
    parser.add_argument("--corpus", required=True, help="dir of <pid>.gt.md reference files")
    parser.add_argument("--baseline", help="prior leaderboard JSON to check regressions against")
    parser.add_argument("--out", help="write leaderboard JSON to this path")
    parser.add_argument("--workspace", help="override $WG21_DATA_DIR")
    args = parser.parse_args(argv)

    corpus = Path(args.corpus)
    if not corpus.is_dir():
        logger.error("corpus dir not found: %s", corpus)
        return C.EXIT_ERROR

    try:
        backend = open_backend(args.workspace)
    except EnvironmentError as exc:
        logger.error("%s", exc)
        return C.EXIT_ERROR

    pairs = _load_corpus_pairs(corpus, backend)
    if not pairs:
        logger.error("no (candidate, reference) pairs found in %s", corpus)
        return C.EXIT_ERROR

    rows = run_bench(pairs)
    agg = aggregate(rows)
    leaderboard = {
        "schema_version": C.WHISKER_SCHEMA_VERSION,
        "aggregate": agg,
        "rows": [r.to_dict() for r in rows],
    }
    payload = json.dumps(leaderboard, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    print(payload)

    exit_code = C.EXIT_OK
    if agg["below_floor"]:
        logger.warning("below floor: %s", ", ".join(agg["below_floor"]))
        exit_code = C.EXIT_FAIL
    if args.baseline:
        try:
            base = json.loads(Path(args.baseline).read_text(encoding="utf-8-sig"))
            base_overall = base["aggregate"]["overall"]
        except (OSError, KeyError, ValueError) as exc:
            logger.error("cannot read baseline: %s", exc)
            return C.EXIT_ERROR
        if agg["overall"] < base_overall - C.BENCH_REGRESSION_SLACK:
            logger.error(
                "overall regressed %.4f -> %.4f (slack %.4f)",
                base_overall, agg["overall"], C.BENCH_REGRESSION_SLACK,
            )
            exit_code = C.EXIT_FAIL
    return exit_code


def guard_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="whisker guard",
        description="Per-paper regression gate over a ground-truth corpus",
    )
    parser.add_argument("--corpus", required=True, help="dir of <pid>.gt.md reference files")
    parser.add_argument(
        "--baseline", required=True,
        help="committed per-paper baseline JSON (read to diff, or written with --update)",
    )
    parser.add_argument(
        "--update", action="store_true",
        help="rewrite the baseline from the current run and exit 0 (the refresh ritual)",
    )
    parser.add_argument(
        "--slack", type=float, default=None,
        help=(
            "max per-axis drop tolerated before a paper counts as regressed; "
            "overrides the slack stored in the baseline (default: from baseline, "
            f"else {C.GUARD_AXIS_SLACK})"
        ),
    )
    parser.add_argument(
        "--fail-on-new", action="store_true",
        help="fail papers absent from the baseline (force an explicit --update to admit them)",
    )
    parser.add_argument("--out", help="write the guard report JSON to this path")
    parser.add_argument("--json", action="store_true", help="emit the guard report JSON to stdout")
    parser.add_argument("--workspace", help="override $WG21_DATA_DIR")
    args = parser.parse_args(argv)

    corpus = Path(args.corpus)
    if not corpus.is_dir():
        logger.error("corpus dir not found: %s", corpus)
        return C.EXIT_ERROR

    try:
        backend = open_backend(args.workspace)
    except EnvironmentError as exc:
        logger.error("%s", exc)
        return C.EXIT_ERROR

    pairs = _load_corpus_pairs(corpus, backend)
    if not pairs:
        logger.error("no (candidate, reference) pairs found in %s", corpus)
        return C.EXIT_ERROR

    rows = run_bench(pairs)

    baseline_path = Path(args.baseline)
    if args.update:
        try:
            payload = baseline_from_rows(rows)
        except ValueError as exc:
            logger.error("cannot build baseline: %s", exc)
            return C.EXIT_ERROR
        baseline_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        logger.info("wrote guard baseline (%d paper(s)) to %s", len(rows), baseline_path)
        return C.EXIT_OK

    baseline = None
    if baseline_path.exists():
        try:
            # utf-8-sig: the baseline is committed and may be hand-edited.
            baseline = json.loads(baseline_path.read_text(encoding="utf-8-sig"))
        except ValueError as exc:
            logger.error("cannot read baseline %s: %s", baseline_path, exc)
            return C.EXIT_ERROR
    else:
        logger.warning(
            "baseline %s not found; judging every paper against absolute floors "
            "(run with --update to commit one)", baseline_path,
        )

    try:
        report = diff_rows(rows, baseline, slack=args.slack, fail_on_new=args.fail_on_new)
    except ValueError as exc:
        logger.error("invalid baseline %s: %s", baseline_path, exc)
        return C.EXIT_ERROR

    # Substring anchors are conjunctive with the metric guard: an anchor miss is
    # a hard fail even when the numeric slack holds (a phrase can vanish while
    # nid/teds/mhs stay in tolerance).
    try:
        anchor_reports = _run_anchor_checks(corpus, pairs)
    except ValueError as exc:
        logger.error("invalid anchors file: %s", exc)
        return C.EXIT_ERROR
    anchors_failed = any(r.failed for r in anchor_reports)

    # Lane 3 comprehension facts are also conjunctive: a failed VERIFIED fact is
    # a hard fail even when fidelity (nid/teds/mhs) stays green, because a
    # faithful-looking reflow can still scramble a table or drop an exponent.
    try:
        fact_reports = _run_fact_checks(corpus, pairs)
    except ValueError as exc:
        logger.error("invalid facts file: %s", exc)
        return C.EXIT_ERROR
    facts_vacuous = _warn_vacuous_reports(fact_reports)
    facts_failed = any(r.failed for r in fact_reports) or bool(facts_vacuous)

    report_dict = report.to_dict()
    report_dict["anchors"] = [r.to_dict() for r in anchor_reports]
    report_dict["facts"] = [r.to_dict() for r in fact_reports]
    payload = json.dumps(report_dict, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    if args.json:
        print(payload)
    else:
        print(_render_guard_summary(report, anchor_reports, fact_reports))

    if report.failed or anchors_failed or facts_failed:
        return C.EXIT_FAIL
    return C.EXIT_OK


def _run_anchor_checks(corpus: Path, pairs: list[tuple[str, str, str]]) -> list:
    """Run ``<pid>.anchors.json`` tripwires over the corpus candidates.

    Only papers with a committed anchors file are checked; the rest are silent.
    Returns one ``AnchorReport`` per anchored paper (sorted by pid).
    """
    candidates = {pid: candidate for pid, candidate, _ in pairs}
    reports = []
    for anchors_file in sorted(corpus.glob("*.anchors.json")):
        pid = anchors_file.name[: -len(".anchors.json")].upper()
        if pid not in candidates:
            logger.warning("anchors for %s but no staged candidate; skipping", pid)
            continue
        data = json.loads(anchors_file.read_text(encoding="utf-8-sig"))
        spec = anchor_spec_from_dict(data, pid)
        reports.append(check_anchors(candidates[pid], spec))
    return reports


FACTS_SUFFIX = ".facts.jsonl"


def _warn_vacuous_reports(reports: list) -> set[str]:
    """Return PIDs whose facts file has zero verified facts (vacuous green).

    Mirrors the CI guard in test_comprehension_corpus.py: a facts file that
    never gates anything proves nothing about comprehension.
    """
    vacuous: set[str] = set()
    for r in reports:
        verified_count = r.to_dict()["verified_count"]
        if verified_count == 0:
            vacuous.add(r.pid)
            logger.warning(
                "%s: facts file has 0 verified facts (%d draft); vacuous green",
                r.pid, len(r.checks),
            )
    return vacuous


def _run_fact_checks(corpus: Path, pairs: list[tuple[str, str, str]]) -> list:
    """Run ``<pid>.facts.jsonl`` comprehension assertions over the candidates.

    Only papers with a committed facts file are checked; the rest are silent.
    Returns one ``FactReport`` per paper that has a facts file (sorted by pid).
    Lane 3: deterministic, source-verified facts, no LLM in the loop.
    """
    candidates = {pid: candidate for pid, candidate, _ in pairs}
    reports = []
    for facts_file in sorted(corpus.glob(f"*{FACTS_SUFFIX}")):
        pid = facts_file.name[: -len(FACTS_SUFFIX)].upper()
        if pid not in candidates:
            logger.warning("facts for %s but no staged candidate; skipping", pid)
            continue
        facts = parse_facts_jsonl(facts_file.read_text(encoding="utf-8-sig"), pid)
        reports.append(check_facts(candidates[pid], facts, pid))
    return reports


def _render_guard_summary(report, anchor_reports=None, fact_reports=None) -> str:
    """Compact human summary: one line per failing paper + a footer."""
    anchor_reports = anchor_reports or []
    fact_reports = fact_reports or []
    lines: list[str] = []
    for f in sorted(report.regressed(), key=lambda x: x.pid):
        detail = "; ".join(f.regressions + f.crossed_floor + f.below_floor)
        lines.append(f"  FAIL {f.pid} [{f.status}] {detail}")
    for pid in report.missing:
        lines.append(f"  FAIL {pid} [missing] in baseline but absent from corpus")
    for r in sorted(anchor_reports, key=lambda x: x.pid):
        if r.failed:
            detail = "; ".join(c.detail for c in r.failures())
            lines.append(f"  FAIL {r.pid} [anchor] {detail}")
    for r in sorted(fact_reports, key=lambda x: x.pid):
        if r.failed:
            detail = "; ".join(f"{c.type}:{c.detail or c.id}" for c in r.failures())
            lines.append(f"  FAIL {r.pid} [fact] {detail}")
    counts = report.to_dict()["status_counts"]
    rollup = ", ".join(f"{k}={v}" for k, v in counts.items()) or "none"
    anchors_failed = any(r.failed for r in anchor_reports)
    facts_failed = any(r.failed for r in fact_reports)
    verdict = "REGRESSION" if (report.failed or anchors_failed or facts_failed) else "clean"
    n = len(report.findings)
    anchored = len(anchor_reports)
    facted = len(fact_reports)
    lines.append(
        f"whisker guard: {verdict} over {n} paper(s) ({rollup}); "
        f"anchors checked on {anchored} paper(s); facts checked on {facted} paper(s)"
    )
    return "\n".join(lines)


def _load_golden_manifest(corpus: Path) -> set[str]:
    """Return the set of expected-failure pids from an optional golden.json.

    The manifest is an optional, hand-authored, trusted config; absence means no
    expected-failure markers. Returns upper-cased pids.
    """
    manifest_path = corpus / GOLDEN_MANIFEST_NAME
    if not manifest_path.exists():
        return set()
    raw = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError(f"{GOLDEN_MANIFEST_NAME} must be a JSON object")
    kind = raw.get("kind")
    if kind is not None and kind != GOLDEN_MANIFEST_KIND:
        raise ValueError(
            f"{GOLDEN_MANIFEST_NAME} kind {kind!r} != {GOLDEN_MANIFEST_KIND!r}"
        )
    xfails = raw.get("expected_failures", [])
    if not isinstance(xfails, list):
        raise ValueError("golden.json 'expected_failures' must be a list")
    return {str(p).upper() for p in xfails}


def _load_golden_items(corpus: Path, backend, xfails: set[str]) -> list[GoldenItem]:
    """Build (pid, candidate, expected) items over the blessed micro-corpus.

    Membership is the deterministic union of committed ``<pid>.expected.md``
    snapshots and optional ``<pid>.gt.md`` bootstrap markers. The candidate is
    the staged markdown; expected-only members remain visible when it is absent.
    """
    items: list[GoldenItem] = []
    for pid, expected_path in _golden_member_paths(corpus):
        try:
            candidate = backend.get_paper_md(pid)
        except MissingPaperMdError as exc:
            logger.warning("missing %s: %s", pid, exc)
            candidate = None
        expected = (
            expected_path.read_text(encoding="utf-8-sig")
            if expected_path is not None
            else None
        )
        items.append(GoldenItem(
            pid=pid, candidate=candidate, expected=expected,
            expected_failure=pid in xfails,
        ))
    return items


def _golden_member_paths(corpus: Path) -> list[tuple[str, Path | None]]:
    """Return normalized PID members with their actual expected-file paths."""
    expected_members: dict[str, tuple[str, Path]] = {}
    gt_members: dict[str, tuple[str, Path]] = {}
    expected_suffix = GOLDEN_EXPECTED_SUFFIX.casefold()
    gt_suffix = ".gt.md"
    for path in sorted(corpus.iterdir(), key=lambda p: (p.name.casefold(), p.name)):
        name = path.name.casefold()
        if name.endswith(expected_suffix):
            pid = path.name[: -len(GOLDEN_EXPECTED_SUFFIX)].upper()
            members = expected_members
            kind = "expected snapshots"
        elif name.endswith(gt_suffix):
            pid = path.name[: -len(gt_suffix)].upper()
            members = gt_members
            kind = "GT markers"
        else:
            continue
        if path.is_symlink():
            raise ValueError(f"symlinked corpus member not allowed: {path.name}")
        if not path.is_file():
            continue
        key = pid.casefold()
        previous = members.get(key)
        if previous is not None:
            raise ValueError(
                f"ambiguous duplicate {kind}: {previous[1].name}, {path.name}"
            )
        members[key] = (pid, path)

    result: list[tuple[str, Path | None]] = []
    for key in sorted(expected_members.keys() | gt_members.keys()):
        if key in expected_members:
            pid, expected_path = expected_members[key]
        else:
            pid, _ = gt_members[key]
            expected_path = None
        result.append((pid, expected_path))
    return result


def golden_main(argv: list[str]) -> int:
    # golden-hook: the coming golden-file layer (construct-isolated pairs,
    # span-aware golden grids) extends THIS verb rather than adding a new
    # one. Once golden grids gate tables, the table facts in Lane 3 become
    # redundant for papers that ship a grid and can be partially retired.
    parser = argparse.ArgumentParser(
        prog="whisker golden",
        description="Lane 1 stability gate: exact compare vs committed snapshots",
    )
    parser.add_argument(
        "--corpus", required=True,
        help="dir of <pid>.expected.md snapshots and optional <pid>.gt.md markers",
    )
    parser.add_argument(
        "--update", action="store_true",
        help="rewrite <pid>.expected.md from the current run and exit 0 (the bless ritual)",
    )
    parser.add_argument(
        "--fail-on-new", action="store_true",
        help="fail papers with no committed snapshot (force an explicit --update)",
    )
    parser.add_argument("--out", help="write the golden report JSON to this path")
    parser.add_argument("--json", action="store_true", help="emit the golden report JSON to stdout")
    parser.add_argument("--workspace", help="override $WG21_DATA_DIR")
    args = parser.parse_args(argv)

    corpus = Path(args.corpus)
    if not corpus.is_dir():
        logger.error("corpus dir not found: %s", corpus)
        return C.EXIT_ERROR

    try:
        backend = open_backend(args.workspace)
    except EnvironmentError as exc:
        logger.error("%s", exc)
        return C.EXIT_ERROR

    try:
        xfails = _load_golden_manifest(corpus)
    except ValueError as exc:
        logger.error("cannot read %s: %s", GOLDEN_MANIFEST_NAME, exc)
        return C.EXIT_ERROR

    try:
        items = _load_golden_items(corpus, backend, xfails)
    except ValueError as exc:
        logger.error("invalid golden corpus: %s", exc)
        return C.EXIT_ERROR
    if not items:
        logger.error("no <pid>.expected.md or <pid>.gt.md papers found in %s", corpus)
        return C.EXIT_ERROR

    if args.update:
        try:
            expected_paths = {
                pid.casefold(): path
                for pid, path in _golden_member_paths(corpus)
                if path is not None
            }
        except ValueError as exc:
            logger.error("invalid golden corpus: %s", exc)
            return C.EXIT_ERROR
        written = 0
        for item in items:
            if item.candidate is None:
                logger.warning("skipping %s: not staged, no snapshot written", item.pid)
                continue
            expected_path = expected_paths.get(
                item.pid.casefold(), corpus / f"{item.pid}{GOLDEN_EXPECTED_SUFFIX}",
            )
            if expected_path.is_symlink():
                logger.error(
                    "symlinked corpus member not allowed: %s", expected_path.name
                )
                return C.EXIT_ERROR
            expected_path.write_text(
                normalize_for_exact_lane(item.candidate), encoding="utf-8"
            )
            written += 1
        logger.info("blessed %d golden snapshot(s) in %s", written, corpus)
        return C.EXIT_OK

    report = diff_goldens(items, fail_on_new=args.fail_on_new)
    payload = json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    if args.json:
        print(payload)
    else:
        print(_render_golden_summary(report))

    if report.failed:
        return C.EXIT_FAIL
    return C.EXIT_OK


def _render_golden_summary(report) -> str:
    """Compact human summary: one line per failing paper + a footer."""
    lines: list[str] = []
    for f in sorted(report.regressed(), key=lambda x: x.pid):
        if f.status == "changed":
            lines.append(f"  FAIL {f.pid} [changed] {len(f.diff)} diff line(s)")
        else:
            lines.append(f"  FAIL {f.pid} [{f.status}]")
    counts = report.to_dict()["status_counts"]
    rollup = ", ".join(f"{k}={v}" for k, v in counts.items()) or "none"
    verdict = "CHANGED" if report.failed else "stable"
    n = len(report.findings)
    lines.append(f"whisker golden: {verdict} over {n} paper(s) ({rollup})")
    return "\n".join(lines)


def facts_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="whisker facts",
        description="Lane 3 comprehension gate: deterministic source-verified fact assertions",
    )
    parser.add_argument("--corpus", required=True, help="dir of <pid>.facts.jsonl files")
    parser.add_argument("--out", help="write the facts report JSON to this path")
    parser.add_argument("--json", action="store_true", help="emit the facts report JSON to stdout")
    parser.add_argument(
        "--strict", action="store_true",
        help="also fail when an UNVERIFIED (draft) fact fails (default: only verified facts gate)",
    )
    parser.add_argument("--workspace", help="override $WG21_DATA_DIR")
    args = parser.parse_args(argv)

    corpus = Path(args.corpus)
    if not corpus.is_dir():
        logger.error("corpus dir not found: %s", corpus)
        return C.EXIT_ERROR

    try:
        backend = open_backend(args.workspace)
    except EnvironmentError as exc:
        logger.error("%s", exc)
        return C.EXIT_ERROR

    reports = []
    for facts_file in sorted(corpus.glob(f"*{FACTS_SUFFIX}")):
        pid = facts_file.name[: -len(FACTS_SUFFIX)].upper()
        try:
            candidate = backend.get_paper_md(pid)
        except MissingPaperMdError as exc:
            logger.warning("skipping %s: %s", pid, exc)
            continue
        try:
            facts = parse_facts_jsonl(facts_file.read_text(encoding="utf-8-sig"), pid)
        except ValueError as exc:
            logger.error("invalid facts file %s: %s", facts_file, exc)
            return C.EXIT_ERROR
        reports.append(check_facts(candidate, facts, pid))

    if not reports:
        logger.error("no <pid>%s files with a staged candidate found in %s", FACTS_SUFFIX, corpus)
        return C.EXIT_ERROR

    # Mirror the CI guard (test_comprehension_corpus.py:67-70): a facts file
    # with zero verified facts is vacuous green, not a valid pass.
    vacuous_pids = _warn_vacuous_reports(reports)

    payload = json.dumps(
        {"kind": FACTS_KIND, "papers": [r.to_dict() for r in reports]},
        indent=2, ensure_ascii=False,
    )
    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    if args.json:
        print(payload)
    else:
        print(_render_facts_summary(reports))

    # --strict also gates draft facts: any check (verified or not) that fails.
    if args.strict:
        failed = any(not c.passed for r in reports for c in r.checks)
    else:
        failed = any(r.failed for r in reports)
    return C.EXIT_FAIL if (failed or vacuous_pids) else C.EXIT_OK


def _render_facts_summary(reports) -> str:
    """Compact human summary: one line per failing paper + a footer."""
    lines: list[str] = []
    verified = 0
    vacuous_count = 0
    for r in sorted(reports, key=lambda x: x.pid):
        rd = r.to_dict()
        verified += rd["verified_count"]
        if rd["verified_count"] == 0:
            vacuous_count += 1
            lines.append(f"  VACUOUS {r.pid} 0 verified facts ({len(r.checks)} draft)")
        elif r.failed:
            detail = "; ".join(f"{c.type}:{c.detail or c.id}" for c in r.failures())
            lines.append(f"  FAIL {r.pid} {detail}")
    failed = any(r.failed for r in reports)
    verdict = "COMPREHENSION FAIL" if (failed or vacuous_count) else "clean"
    lines.append(
        f"whisker facts: {verdict} over {len(reports)} paper(s) "
        f"({verified} verified fact(s) gated, {vacuous_count} vacuous)"
    )
    return "\n".join(lines)


def _resolve_det_report_dir(
    report_dir: str | None, workspace: str | None, lane: str = "det",
) -> Path | None:
    """Resolve the directory holding a lane's report artifacts.

    ``lane`` is ``"det"`` (default; ``report.json``, honoring ``--report-dir``
    exactly as before) or ``"llm"`` (``report-merged.json``). With no
    override, the det directory is derived from any converted paper via
    ``whisker_output_dir``, and the llm directory is its sibling
    ``whisker/llm`` (mirrors ``_llm_output_dir`` in ``llm/cli.py``,
    reimplemented here so the core ``whisker`` command does not pull in the
    optional ``tapetum-llm`` extra's dependencies).
    Returns ``None`` (after logging the cause) when neither an override nor a
    usable backend/paper is available.
    """
    if report_dir:
        return Path(report_dir)
    try:
        backend = open_backend(workspace)
    except EnvironmentError as exc:
        logger.error("%s", exc)
        return None
    pids = [
        pid for pid in backend.list_all_paper_ids()
        if backend.get_paper_md_path(pid).exists()
    ]
    if not pids:
        logger.error(
            "no converted papers found; cannot resolve the report directory "
            "(pass --report-dir)"
        )
        return None
    det_dir = whisker_output_dir(pids[0], backend)
    return det_dir if lane == "det" else det_dir.parent / lane


def _delta_severity_key(f: DeltaFinding) -> tuple:
    """Sort key for worst-first ordering: highest severity first, pid as tiebreak."""
    return (-f.severity, f.pid)


def _log_missing_current(path: Path, rerun_hint: str) -> None:
    """Explain an absent current report rather than surfacing a bare errno."""
    logger.error("no report to compare at %s. Run `%s` first.", path, rerun_hint)


def _log_missing_baseline(path: Path, rerun_hint: str) -> None:
    """Explain an absent baseline: a first run cannot have one.

    The snapshot is written when a run overwrites an *existing* report, so it
    appears on the second run, never the first. A bare "No such file or
    directory" reads like a defect to an operator who ran the lane once and
    did everything right.
    """
    logger.error(
        "no baseline to compare against yet (%s). This is expected after a "
        "first run: the snapshot is written when the NEXT run overwrites the "
        "current report. Run `%s` a second time, then retry.",
        path.name, rerun_hint,
    )


def _render_delta_summary(result: DeltaResult) -> str:
    """Compact human summary: regressed (worst first), improved, new/gone, footer."""
    lines: list[str] = []

    regressed = sorted(result.regressed(), key=_delta_severity_key)
    if regressed:
        lines.append(f"regressed ({len(regressed)})")
        for f in regressed:
            lines.append(f"  REGRESSED {f.pid} [{f.prev_verdict} -> {f.curr_verdict}] {f.reason}")
        lines.append("")

    improved = sorted(result.improved(), key=_delta_severity_key)
    if improved:
        lines.append(f"improved ({len(improved)})")
        for f in improved:
            lines.append(f"  improved  {f.pid} [{f.prev_verdict} -> {f.curr_verdict}] {f.reason}")
        lines.append("")

    new_papers = result.new_papers()
    if new_papers:
        lines.append(f"new ({len(new_papers)})")
        for f in new_papers:
            lines.append(f"  new       {f.pid} [{f.curr_verdict}]")
        lines.append("")

    gone_papers = result.gone_papers()
    if gone_papers:
        lines.append(f"gone ({len(gone_papers)})")
        for f in gone_papers:
            lines.append(f"  gone      {f.pid} [was {f.prev_verdict}]")
        lines.append("")

    lines.append(f"unchanged: {len(result.unchanged())}")
    verdict = "REGRESSION" if result.any_regressed else "clean"
    lines.append(
        f"whisker delta: {verdict} ({result.prev_count} prior, "
        f"{result.curr_count} current paper(s))"
    )
    return "\n".join(lines)


# -- whisker delta --llm: advisory delta over the LLM lane's merged report --

_LLM_MERGED_FILENAME = "report-merged.json"
_LLM_MERGED_PREV_FILENAME = "report-merged.prev.json"
_LLM_WATCHED_METRICS = ("unigram",)

# report-merged.json carries two "no verdict here" markers, both produced by
# fusion_report._verdict's defaults: "-" on the llm field when a paper has no
# tapetum data, and "?" on the det field when its whisker sidecar is missing
# or malformed. Neither is a tier, so neither may be ranked: a paper whose
# det sidecar vanished between runs would otherwise read as pass -> "?" (a
# regression that did not happen) or fail -> "?" (an improvement that hides a
# real failure), and its unigram would read 0.0 because
# build_merged_json defaults the missing coverage to zero.
# ``None`` joins them for a row that omits the field outright (hand-edited or
# foreign JSON): absent is absent however it is spelled.
_LLM_VERDICT_ABSENT = "-"
_LLM_VERDICT_UNKNOWN = "?"
_LLM_VERDICT_SENTINELS = (_LLM_VERDICT_ABSENT, _LLM_VERDICT_UNKNOWN, None)


def _llm_advisory_movers(result: DeltaResult) -> list[DeltaFinding]:
    """Verdict-tier movers from the llm-field-only pass, worst-first.

    Rows that gained or lost LLM coverage are already excluded upstream:
    ``compute_delta`` classifies a ``_LLM_VERDICT_SENTINELS`` row as
    unchanged, so it can reach neither ``regressed()`` nor ``improved()``.
    """
    return sorted(result.regressed() + result.improved(), key=_delta_severity_key)


def _render_llm_advisory_lines(movers: list[DeltaFinding]) -> list[str]:
    lines = ["--- LLM advisory verdict changes (single-run, may be judge noise) ---"]
    if not movers:
        lines.append("  none")
        return lines
    for f in movers:
        lines.append(f"  {f.pid} [{f.prev_verdict} -> {f.curr_verdict}]")
    return lines


def _count_replayed(rows: object) -> int:
    """Count rows whose ``replayed`` field is truthy (warm-skip carryover)."""
    if not isinstance(rows, list):
        return 0
    return sum(1 for row in rows if isinstance(row, dict) and row.get("replayed"))


def _llm_report_is_stale(llm_dir: Path, det_dir: Path | None = None) -> bool:
    """True (and logs a WARNING) if any input sidecar postdates the aggregate.

    ``report-merged.json`` is only refreshed on a full LLM-lane run or
    ``--fuse-only`` (see the tapetum_llm freshness contract in CLAUDE.md); a
    partial run (explicit PIDs, ``--review-all``) updates per-paper sidecars
    without rebuilding it, so it can silently fall behind.

    BOTH of its inputs count. ``build_merged_json`` reads the tapetum sidecars
    *and* the live det sidecars (``tapetum_llm.cli._read_whisker_sidecar``), so
    a bare ``whisker --all`` with no tapetum run afterwards leaves the
    aggregate's ``det`` column frozen exactly as surely as a partial LLM run
    leaves its ``llm`` column frozen. Watching only the tapetum sidecars would
    call that case fresh, which is the more misleading of the two: the det
    column is the one a reader is most likely to mistake for authoritative.

    No aggregate or no sidecars is not staleness (nothing to be behind).
    """
    merged_path = llm_dir / _LLM_MERGED_FILENAME
    if not merged_path.exists():
        return False
    # The two patterns cannot collide: "<pid>.whisker.tapetum.json" does not
    # match "*.whisker.json", so passing det_dir == llm_dir is harmless.
    sidecar_paths = list(llm_dir.glob("*.whisker.tapetum.json"))
    if det_dir is not None:
        sidecar_paths += det_dir.glob("*.whisker.json")
    if not sidecar_paths:
        return False
    merged_mtime = merged_path.stat().st_mtime
    newest_sidecar_mtime = max(p.stat().st_mtime for p in sidecar_paths)
    stale = newest_sidecar_mtime > merged_mtime
    if stale:
        logger.warning(
            "report-merged.json may be stale (a sidecar moved since the last "
            "aggregate rebuild); consider running whisker-tapetum-llm "
            "--fuse-only first"
        )
    return stale


def _delta_llm_main(args: argparse.Namespace) -> int:
    """whisker delta --llm: advisory delta over the LLM lane's merged report.

    Reads ``whisker/llm/report-merged.json`` (current) and
    ``report-merged.prev.json`` (baseline, or ``--baseline`` override), both
    bare lists (``fusion_report.build_merged_json`` does not wrap in
    ``{"results": [...]}``).

    The PRIMARY section is the det-tier verdict (row field ``"det"``) plus the
    ``unigram`` metric, rendered exactly like the det-lane delta
    (``compute_delta`` with defaults would read a different shape and field,
    hence the explicit keyword overrides). A SECOND, independent pass over the
    ``"llm"`` field (verdict-only, no metric fallback) surfaces judge-tier
    movers in an advisory-only section.

    Exit codes are 0 or 1 only: this whole view renders, it never gates. See
    the note above ``return C.EXIT_OK`` for why the det section is informative
    here but not authoritative.
    """
    llm_dir = _resolve_det_report_dir(args.report_dir, args.workspace, lane="llm")
    if llm_dir is None:
        return C.EXIT_ERROR

    curr_path = llm_dir / _LLM_MERGED_FILENAME
    baseline_path = (
        Path(args.baseline) if args.baseline else llm_dir / _LLM_MERGED_PREV_FILENAME
    )

    try:
        curr_rows = json.loads(curr_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        _log_missing_current(curr_path, "whisker-tapetum-llm")
        return C.EXIT_ERROR
    except OSError as exc:
        logger.error("cannot read current merged report %s: %s", curr_path, exc)
        return C.EXIT_ERROR
    except ValueError as exc:
        logger.error("invalid JSON in %s: %s", curr_path, exc)
        return C.EXIT_ERROR

    try:
        prev_rows = json.loads(baseline_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        _log_missing_baseline(baseline_path, "whisker-tapetum-llm")
        return C.EXIT_ERROR
    except OSError as exc:
        logger.error("cannot read baseline merged report %s: %s", baseline_path, exc)
        return C.EXIT_ERROR
    except ValueError as exc:
        logger.error("invalid JSON in %s: %s", baseline_path, exc)
        return C.EXIT_ERROR

    try:
        det_result = compute_delta(
            prev_rows, curr_rows,
            verdict_field="det", watched_metrics=_LLM_WATCHED_METRICS, results_key=None,
            verdict_sentinels=_LLM_VERDICT_SENTINELS,
        )
        llm_result = compute_delta(
            prev_rows, curr_rows,
            verdict_field="llm", watched_metrics=(), results_key=None,
            verdict_sentinels=_LLM_VERDICT_SENTINELS,
        )
    except ValueError as exc:
        logger.error("cannot compute LLM-lane delta: %s", exc)
        return C.EXIT_ERROR

    movers = _llm_advisory_movers(llm_result)
    replayed_count = _count_replayed(curr_rows)
    # Mirrors the llm-from-det derivation in _resolve_det_report_dir. An
    # explicit --report-dir is a single flat directory holding both lanes'
    # artifacts (that is what the flag means for the det lane too), so the det
    # sidecars sit right next to the aggregate.
    det_dir = llm_dir if args.report_dir else llm_dir.parent / "det"
    stale = _llm_report_is_stale(llm_dir, det_dir)

    if args.json:
        payload = {
            "det_delta": det_result.to_dict(),
            "llm_advisory_movers": [
                {"pid": f.pid, "prev_llm": f.prev_verdict, "curr_llm": f.curr_verdict}
                for f in movers
            ],
            "replayed_count": replayed_count,
            "stale": stale,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(_render_delta_summary(det_result))
        print()
        for line in _render_llm_advisory_lines(movers):
            print(line)
        print(f"replayed (warm-skipped, unchanged): {replayed_count}")
        if det_result.any_regressed:
            print(
                "note: this view does not gate. Run `whisker delta` for the "
                "authoritative deterministic regression check."
            )

    # Always 0: this view renders, it never gates.
    #
    # The det column here is honest (build_merged_json reads the live det
    # sidecars) but it is sampled on a DIFFERENT TIME AXIS than the det lane's
    # own delta. `whisker delta` compares consecutive `whisker --all` runs;
    # this compares consecutive tapetum aggregate rebuilds. The aggregate is
    # rebuilt only by a full LLM run or --fuse-only, so the two axes drift
    # apart in both directions:
    #
    #   `whisker --all` then no tapetum run: report.json moved, the aggregate
    #   did not. Gating here would report clean while a real regression exists.
    #
    #   `whisker --all` twice, then a late --fuse-only: the det lane already
    #   absorbed the change into its own baseline, so `whisker delta` is clean
    #   while the aggregate only now picks the move up. Gating here would fail
    #   a build for a regression the authoritative gate no longer reports.
    #
    # One authoritative emitter per signal: `whisker delta` owns deterministic
    # regression gating because it reads report.json, the artifact whose
    # baseline moves in lockstep with it. Machine consumers that want the
    # movement without the gate read `det_delta.any_regressed` from --json.
    return C.EXIT_OK


def delta_main(argv: list[str]) -> int:
    """whisker delta: run-to-run comparison of two det-lane report.json payloads.

    whisker delta [--baseline PATH] [--report-dir DIR] [--workspace DIR] [--json]
                  [--llm]

    Compares the current ``report.json`` against a prior snapshot (by default
    ``report.prev.json`` next to it, written automatically by the det-lane
    write path on every run after the first). Exit codes: 0 clean, 1 error
    (missing/unreadable reports), 3 if any paper regressed.

    ``--llm`` switches to the advisory LLM lane instead: it diffs
    ``whisker/llm/report-merged.json`` against ``report-merged.prev.json``
    (also snapshotted automatically), rendering a det-tier section and an
    LLM-tier-movers section for visibility. Exit codes are 0 or 1 only: the
    whole ``--llm`` view renders, it never gates. Regression gating stays
    with plain ``whisker delta``. See ``_delta_llm_main``.
    """
    parser = argparse.ArgumentParser(
        prog="whisker delta",
        description=(
            "Run-to-run delta (det lane: report.json, exits 0/3/1; "
            "--llm: report-merged.json, renders only, exits 0/1)"
        ),
    )
    parser.add_argument(
        "--baseline",
        help=(
            "prior report.json (default: report.prev.json next to the current "
            "report.json); with --llm, the prior report-merged.json "
            "(default: report-merged.prev.json)"
        ),
    )
    parser.add_argument(
        "--report-dir",
        help=(
            "directory holding report.json (default: <data>/whisker/det); "
            "with --llm, the directory holding report-merged.json "
            "(default: <data>/whisker/llm)"
        ),
    )
    parser.add_argument("--workspace", help="override $WG21_DATA_DIR")
    parser.add_argument("--json", action="store_true", help="emit the delta report JSON to stdout")
    parser.add_argument(
        "--llm", action="store_true",
        help=(
            "compare the LLM lane's report-merged.json instead of the det "
            "lane's report.json (renders both det-tier and LLM-tier sections "
            "for visibility; exits 0 or 1 only, never gates; use plain "
            "`whisker delta` for the authoritative regression check)"
        ),
    )
    args = parser.parse_args(argv)

    if args.llm:
        return _delta_llm_main(args)

    report_dir = _resolve_det_report_dir(args.report_dir, args.workspace)
    if report_dir is None:
        return C.EXIT_ERROR

    curr_path = report_dir / "report.json"
    baseline_path = Path(args.baseline) if args.baseline else report_dir / "report.prev.json"

    try:
        curr_report = json.loads(curr_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        _log_missing_current(curr_path, "whisker --all")
        return C.EXIT_ERROR
    except OSError as exc:
        logger.error("cannot read current report %s: %s", curr_path, exc)
        return C.EXIT_ERROR
    except ValueError as exc:
        logger.error("invalid JSON in %s: %s", curr_path, exc)
        return C.EXIT_ERROR

    try:
        prev_report = json.loads(baseline_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        _log_missing_baseline(baseline_path, "whisker --all")
        return C.EXIT_ERROR
    except OSError as exc:
        logger.error("cannot read baseline report %s: %s", baseline_path, exc)
        return C.EXIT_ERROR
    except ValueError as exc:
        logger.error("invalid JSON in %s: %s", baseline_path, exc)
        return C.EXIT_ERROR

    try:
        result = compute_delta(prev_report, curr_report)
    except ValueError as exc:
        logger.error("cannot compute delta: %s", exc)
        return C.EXIT_ERROR

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(_render_delta_summary(result))

    return C.EXIT_REVIEW if result.any_regressed else C.EXIT_OK


def check_facts_main(argv: list[str]) -> int:
    """whisker check-facts: validate fact and anchor assertions on a markdown file.

    whisker check-facts --md FILE [--facts FILE] [--anchors FILE] [--json]

    Exit codes: 0 all assertions pass, 1 error, 5 one or more failures.
    """
    parser = argparse.ArgumentParser(prog="whisker check-facts")
    parser.add_argument("--md", required=True, type=Path, metavar="FILE",
                        help="Markdown file to validate assertions against")
    parser.add_argument("--facts", type=Path, metavar="FILE",
                        help="JSONL facts file (whisker-facts format)")
    parser.add_argument("--anchors", type=Path, metavar="FILE",
                        help="JSON anchors file (whisker-anchors format)")
    parser.add_argument("--strict", action="store_true",
                        help="Also gate on draft facts (default: verified only)")
    parser.add_argument("--json", action="store_true", dest="json_out")
    args = parser.parse_args(argv)

    if not args.md.is_file():
        print(f"check-facts: {args.md} not found", file=sys.stderr)
        return C.EXIT_ERROR

    md_text = args.md.read_text(encoding="utf-8")
    pid = args.md.stem

    fact_report = None
    if args.facts is not None:
        if not args.facts.is_file():
            print(f"check-facts: --facts {args.facts} not found", file=sys.stderr)
            return C.EXIT_ERROR
        facts = parse_facts_jsonl(args.facts.read_text(encoding="utf-8"), pid=pid)
        fact_report = check_facts(md_text, facts, pid=pid)

    anchor_report = None
    if args.anchors is not None:
        if not args.anchors.is_file():
            print(f"check-facts: --anchors {args.anchors} not found", file=sys.stderr)
            return C.EXIT_ERROR
        spec = anchor_spec_from_dict(
            json.loads(args.anchors.read_text(encoding="utf-8")), pid=pid
        )
        anchor_report = check_anchors(md_text, spec)

    failed = False
    if fact_report is not None:
        for c in fact_report.failures():
            if args.strict or c.verified:
                failed = True
                break
    if anchor_report is not None and not anchor_report.passed:
        failed = True

    payload = {
        "pid": pid,
        "verdict": "not-llm-readable" if failed else "pass",
        "facts": fact_report.to_dict() if fact_report is not None else None,
        "anchors": anchor_report.to_dict() if anchor_report is not None else None,
    }

    if args.json_out:
        print(json.dumps(payload))
        return C.EXIT_FAIL if failed else C.EXIT_OK

    if fact_report is not None:
        print(f"facts: {len(fact_report.checks)} checked")
        for c in fact_report.checks:
            mark = "ok  " if c.passed else "FAIL"
            print(f"  {mark}  [{c.type}] {c.detail or ''}")
    if anchor_report is not None:
        status = "pass" if anchor_report.passed else "FAIL"
        print(f"anchors: {status}")
        for c in anchor_report.failures():
            print(f"  FAIL  {c.detail or ''}")
    return C.EXIT_FAIL if failed else C.EXIT_OK


_LABEL_FAIL = "not-llm-readable"
_LABEL_REVIEW = "review"
_VALID_LABELS = {"pass", _LABEL_REVIEW, _LABEL_FAIL}


_VALID_SPLITS = {"calibration", "holdout"}


def _load_labeled_samples(path: Path, backend_factory) -> list[tuple[str, str, float, str]]:
    """Return (pid, label, unigram_coverage, split) tuples from a labels file.

    Accepts a list of records
    ``[{"pid","label","split","unigram_coverage"?}]``. ``split`` is REQUIRED on
    every record and must be ``"calibration"`` or ``"holdout"`` (P16 2.2: the
    split assignment is frozen in the input file, never guessed by this
    loader). When ``unigram_coverage`` is absent for any record the store is
    opened and the paper is scored (reference oracle off, so calibration is
    deterministic and fast).
    """
    # utf-8-sig tolerates a UTF-8 BOM (common on Windows-edited JSON) and reads
    # plain utf-8 otherwise; a hand-authored labels file is an untrusted input.
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, list):
        raise ValueError(
            "labels file must be a JSON list of {pid,label,split[,unigram_coverage]} "
            "records (a bare {pid: label} mapping cannot carry a split field)"
        )
    records: list[dict] = list(raw)

    need_backend = any("unigram_coverage" not in r for r in records)
    backend = backend_factory() if need_backend else None

    out: list[tuple[str, str, float, str]] = []
    for r in records:
        pid = str(r["pid"]).upper()
        label = str(r["label"]).lower()
        if label not in _VALID_LABELS:
            raise ValueError(f"{pid}: invalid label {label!r} (expected {sorted(_VALID_LABELS)})")
        if "split" not in r:
            raise ValueError(
                f"{pid}: missing required 'split' field (expected {sorted(_VALID_SPLITS)})"
            )
        split = str(r["split"]).lower()
        if split not in _VALID_SPLITS:
            raise ValueError(f"{pid}: invalid split {split!r} (expected {sorted(_VALID_SPLITS)})")
        if "unigram_coverage" in r:
            cov = float(r["unigram_coverage"])
        else:
            result = score_paper(pid, backend, reference_engine=None)
            cov = result.unigram_coverage
        out.append((pid, label, cov, split))
    return out


def calibrate_main(argv: list[str], *, now: datetime | None = None) -> int:
    """CLI entry for ``whisker calibrate``.

    ``now`` is injectable (defaults to the real current time) so tests can
    assert an exact ``calibration_timestamp`` without a real-clock race.
    """
    parser = argparse.ArgumentParser(
        prog="whisker calibrate",
        description=(
            "Fit content-coverage edges from labeled data with a fit/holdout "
            "split (P16 2.2): tau is selected on 'calibration'-split samples "
            "only, and TPR/FPR/precision are reported once on 'holdout'-split "
            "samples that never influenced selection. The fail and review "
            "edges are two independently-defaulted fits, each against its own "
            "FPR ceiling."
        ),
    )
    parser.add_argument(
        "--labels", required=True,
        help=(
            "JSON labels file: a list of {pid,label,split[,unigram_coverage]} "
            "records. label is one of pass/review/fail. split is REQUIRED on "
            "every record and is one of 'calibration'/'holdout' (frozen by "
            "the file's author, never guessed)."
        ),
    )
    parser.add_argument(
        "--fail-target-fpr", type=float, default=DEFAULT_TARGET_FPR_FAIL_EDGE,
        help="max FPR for the fail-edge fit, on the calibration split (default: %(default)s)",
    )
    parser.add_argument(
        "--review-target-fpr", type=float, default=DEFAULT_TARGET_FPR_REVIEW_EDGE,
        help="max FPR for the review-edge fit, on the calibration split (default: %(default)s)",
    )
    parser.add_argument("--out", help="write the fitted thresholds JSON to this path")
    parser.add_argument("--workspace", help="override $WG21_DATA_DIR")
    args = parser.parse_args(argv)

    labels_path = Path(args.labels)
    try:
        labels_bytes = labels_path.read_bytes()
    except OSError as exc:
        logger.error("cannot read labels file: %s", exc)
        return C.EXIT_ERROR
    # Hash of the raw bytes as loaded, not a re-serialization of the parsed
    # JSON, so the provenance record is byte-faithful to what was actually
    # read (P16 2.7: "calibration dataset reference" with a hash).
    labels_file_sha256 = hashlib.sha256(labels_bytes).hexdigest()

    try:
        samples = _load_labeled_samples(labels_path, lambda: open_backend(args.workspace))
    except (OSError, ValueError, KeyError) as exc:
        logger.error("cannot load labels: %s", exc)
        return C.EXIT_ERROR
    except EnvironmentError as exc:
        logger.error("%s", exc)
        return C.EXIT_ERROR

    if not samples:
        logger.error("no labeled samples found in %s", args.labels)
        return C.EXIT_ERROR

    # FAIL edge: positive = genuinely bad (label fail). REVIEW edge: positive =
    # anything that needs human eyes (fail OR review). Both gate on coverage.
    # split is carried through unchanged from the labels file.
    fail_samples = [(cov, label == _LABEL_FAIL, split) for _, label, cov, split in samples]
    review_samples = [
        (cov, label in (_LABEL_FAIL, _LABEL_REVIEW), split) for _, label, cov, split in samples
    ]

    # Each edge is fit INDEPENDENTLY (no shared try/except): a corpus can be
    # structurally too thin for one edge (PROTOCOL.md section 13: the fail
    # edge has only 4/376 papers below it, far short of the 10-positive-total
    # floor `MIN_SAMPLES_PER_CLASS_PER_SPLIT` needs) while still supporting a
    # real fit for the other (the review edge's 49-paper mid band). A single
    # combined try/except would let the unfittable edge silently swallow a
    # perfectly good fit on the other edge and abort the whole run.
    _EDGE_SPECS = (
        ("not-llm-readable", "unigram_coverage_fail_edge", fail_samples, args.fail_target_fpr),
        ("review", "unigram_coverage_review_edge", review_samples, args.review_target_fpr),
    )
    fitted: dict[str, HoldoutCalibrationResult | None] = {}
    not_fit_reason: dict[str, str] = {}
    for edge_label, edge_name, edge_samples, target_fpr in _EDGE_SPECS:
        try:
            fitted[edge_name] = calibrate_threshold_with_holdout(
                edge_samples, name=edge_name, target_fpr=target_fpr,
            )
        except InsufficientCalibrationDataError as exc:
            fitted[edge_name] = None
            not_fit_reason[edge_name] = str(exc)
            logger.warning(
                "%s-Kante nicht gefittet: %s, bleibt PROVISIONAL", edge_label, exc,
            )

    fail_fit = fitted["unigram_coverage_fail_edge"]
    review_fit = fitted["unigram_coverage_review_edge"]

    # A complete failure (neither edge fittable) is still a hard failure: there
    # is nothing to write. One or both edges fitting is a partial-or-full
    # success and the run proceeds.
    if fail_fit is None and review_fit is None:
        logger.error(
            "calibration failed for both edges: fail=%s, review=%s",
            not_fit_reason.get("unigram_coverage_fail_edge"),
            not_fit_reason.get("unigram_coverage_review_edge"),
        )
        return C.EXIT_ERROR

    # The two edges are fit independently, so nothing structurally forbids a
    # fitted fail edge ABOVE the review edge (an inverted, meaningless band:
    # "fail" stricter than "review"). Surface it loudly instead of shipping a
    # silently broken band; the human reviewing the fit must reconcile it.
    # Ordering is only DEFINED when both edges actually fitted; with one edge
    # missing there is nothing to compare, so `edge_ordering_ok` is `None`
    # ("not applicable"), never a fabricated `True`/`False`.
    if fail_fit is not None and review_fit is not None:
        fail_edge = fail_fit.calibration.chosen.threshold
        review_edge = review_fit.calibration.chosen.threshold
        edge_ordering_ok = fail_edge <= review_edge
        if not edge_ordering_ok:
            logger.warning(
                "fitted fail edge %.3f > review edge %.3f: inverted band, do NOT promote "
                "as-is (more labeled data or different --fail-target-fpr/--review-target-fpr "
                "likely needed)",
                fail_edge, review_edge,
            )
    else:
        edge_ordering_ok = None

    calibration_timestamp = (now if now is not None else datetime.now(timezone.utc)).isoformat()

    payload = {
        # The calibration artifact versions independently from the per-paper
        # scoring/sidecar schema (whisker.constants.WHISKER_SCHEMA_VERSION);
        # do not conflate the two.
        "schema_version": CALIBRATION_ARTIFACT_SCHEMA_VERSION,
        "kind": "whisker-calibration",
        "n": len(samples),
        "edge_ordering_ok": edge_ordering_ok,
        # -- P16 2.7 provenance fields --------------------------------------
        "calibrator_version": CALIBRATION_ARTIFACT_SCHEMA_VERSION,
        "calibration_timestamp": calibration_timestamp,
        "labels_file_sha256": labels_file_sha256,
        "split_assignment_source": "frozen 'split' field in the labels input file",
        "current": {
            "unigram_coverage_fail_edge": C.UNIGRAM_COVERAGE_FAIL_EDGE,
            "unigram_coverage_review_edge": C.UNIGRAM_COVERAGE_REVIEW_EDGE,
        },
        # A `None` here means that edge could not be fitted (see
        # `not_fit_reason` below for the exact reason); it is not "not yet
        # computed" or an error in this payload's own construction.
        "fitted": {
            "unigram_coverage_fail_edge": fail_fit.to_dict() if fail_fit is not None else None,
            "unigram_coverage_review_edge": (
                review_fit.to_dict() if review_fit is not None else None
            ),
        },
        # Only the edges that failed to fit appear here; {} when both fitted.
        "not_fit_reason": not_fit_reason,
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        logger.info("wrote fitted thresholds to %s", args.out)
    print(text)

    for fit in (fail_fit, review_fit):
        if fit is None:
            continue
        h = fit.holdout
        logger.info(
            "%s: edge=%.3f holdout_tpr=%.3f holdout_fpr=%.3f holdout_precision=%.3f "
            "(%s, calibration n=%d, holdout n=%d)",
            fit.name, fit.calibration.chosen.threshold, h.tpr, h.fpr, h.precision,
            fit.calibration.method, fit.calibration.n_pos + fit.calibration.n_neg,
            h.n_pos + h.n_neg,
        )
    # Calibration is informational: it never gates. The human promotes the fitted
    # edges into constants.py after reviewing the operating points.
    return C.EXIT_OK


def corpus_main(argv: list[str]) -> int:
    """Corpus authoring tools: stratify candidates and generate draft facts."""
    parser = argparse.ArgumentParser(
        prog="whisker corpus",
        description="Comprehension corpus authoring tools",
    )
    sub = parser.add_subparsers(dest="subcmd")

    strat_p = sub.add_parser(
        "stratify",
        help="list zero-coverage papers by structural stratum",
    )
    strat_p.add_argument("--corpus", required=True, help="dir of <pid>.facts.jsonl")
    strat_p.add_argument("--workspace", help="override $WG21_DATA_DIR")
    strat_p.add_argument("--max", type=int, default=5, help="max per stratum")

    draft_p = sub.add_parser(
        "draft",
        help="generate draft .facts.jsonl for a paper",
    )
    draft_p.add_argument("pid", nargs="+", help="paper ID(s)")
    draft_p.add_argument("--out", required=True, help="output dir for .facts.jsonl")
    draft_p.add_argument("--workspace", help="override $WG21_DATA_DIR")

    args = parser.parse_args(argv)
    if args.subcmd is None:
        parser.print_help()
        return C.EXIT_ERROR

    if args.subcmd == "stratify":
        try:
            backend = open_backend(args.workspace)
        except EnvironmentError as exc:
            logger.error("%s", exc)
            return C.EXIT_ERROR
        corpus = Path(args.corpus)
        if not corpus.is_dir():
            logger.error("corpus dir not found: %s", corpus)
            return C.EXIT_ERROR
        by_stratum = stratify_candidates(backend, corpus, max_per_stratum=args.max)
        for stratum, infos in sorted(by_stratum.items()):
            if not infos:
                continue
            logger.info("--- %s (%d) ---", stratum, len(infos))
            for info in infos:
                detail = ", ".join(
                    f"{k}={v}" for k, v in [
                        ("pipe_tables", info.pipe_table_count),
                        ("html_tables", info.html_table_count),
                        ("math", info.display_math_count),
                        ("code_fences", info.code_fence_count),
                        ("footnotes", info.footnote_count),
                        ("images", info.image_count),
                    ] if v > 0
                )
                logger.info("  %s  [%s]", info.pid, detail)
        return C.EXIT_OK

    if args.subcmd == "draft":
        try:
            backend = open_backend(args.workspace)
        except EnvironmentError as exc:
            logger.error("%s", exc)
            return C.EXIT_ERROR
        out_dir = Path(args.out)
        for pid in args.pid:
            pid_upper = pid.strip().upper()
            try:
                md = backend.get_paper_md(pid_upper)
            except Exception as exc:
                logger.warning("skipping %s: %s", pid_upper, exc)
                continue
            records = draft_facts_scaffold(pid_upper, md)
            path = write_draft_facts(pid_upper, records, out_dir)
            logger.info("%s: wrote %d draft facts -> %s", pid_upper, len(records), path)
        return C.EXIT_OK

    return C.EXIT_ERROR

