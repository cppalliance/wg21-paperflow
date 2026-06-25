#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""whisker command-line entry point.

Commands:

    whisker [PID ...] [--all] [--json] [--no-write] [--gate {pass,review,fail}]
            [--reference ENGINE | --no-reference]
    whisker bench     --corpus DIR [--baseline FILE] [--out FILE]
    whisker guard     --corpus DIR --baseline FILE [--update] [--slack F]
                      [--fail-on-new] [--out FILE]
    whisker golden    --corpus DIR [--update] [--fail-on-new] [--out FILE]
    whisker facts     --corpus DIR [--strict] [--out FILE]
    whisker calibrate --labels FILE [--target-fpr F] [--out FILE]

The three lanes: ``golden`` is Lane 1 STABILITY (did the normalized markdown
change vs a committed ``<pid>.expected.md`` snapshot); ``bench``/``guard`` are
Lane 2 FIDELITY (how close is the output to a ``<pid>.gt.md`` reference, via
nid/teds/mhs); ``facts`` is Lane 3 COMPREHENSION (can an LLM still read it, via
deterministic human-verified ``<pid>.facts.jsonl`` assertions, no LLM in the
loop). ``guard`` additionally folds in anchors and facts conjunctively.

``bench`` reports corpus means; ``guard`` is the per-paper regression gate that
diffs each paper's each axis against a committed baseline (slack/floors read from
the baseline itself; refresh with ``--update``; ``--fail-on-new`` blocks papers
not yet in the baseline); ``golden`` is the Lane 1 stability gate that compares
each paper's normalized markdown against a committed ``<pid>.expected.md``
snapshot (refresh with ``--update``); ``facts`` is the Lane 3 comprehension gate
(only ``checked: verified`` facts gate; ``--strict`` also gates drafts);
``calibrate`` fits the coverage edges from labeled data and reports
TPR/FPR/precision. Typed exit codes (CI contract): 0 ok, 1 error, 3 review,
5 fail.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from paperstore.errors import MissingPaperMdError, MissingSourceError
from paperstore.sqlite_backend import SqliteBackend

from whisker import constants as C
from whisker.anchors import anchor_spec_from_dict, check_anchors
from whisker.bench import aggregate, run_bench
from whisker.calibrate import DEFAULT_TARGET_FPR as C_DEFAULT_TARGET_FPR
from whisker.calibrate import calibrate_threshold
from whisker.facts import FACTS_KIND, check_facts, parse_facts_jsonl
from whisker.golden import (
    GOLDEN_EXPECTED_SUFFIX,
    GOLDEN_MANIFEST_KIND,
    GOLDEN_MANIFEST_NAME,
    GoldenItem,
    diff_goldens,
    normalize_for_exact_lane,
)
from whisker.guard import baseline_from_rows, diff_rows
from whisker.reference import REFERENCE_ENGINES
from whisker.report import build_report, render_report_md, render_summary
from whisker.score import (
    VERDICT_FAIL,
    VERDICT_REVIEW,
    WhiskerResult,
    score_paper,
    sidecar_path,
    whisker_output_dir,
)

logger = logging.getLogger("whisker")

_GATE_ACCEPTS = {
    "pass": {"pass"},
    "review": {"pass", "review"},
    "fail": {"pass", "review", "fail"},
}


_PROGRESS_WIDTH = 28


def _render_progress(done: int, total: int) -> None:
    """Draw an in-place progress bar on stderr (only on a real terminal).

    stderr keeps stdout clean for JSON. When output is redirected/piped
    (not a tty) this is a no-op, so no carriage-return noise leaks into files.
    """
    if not sys.stderr.isatty() or total <= 0:
        return
    filled = int(_PROGRESS_WIDTH * done / total)
    bar = "#" * filled + "-" * (_PROGRESS_WIDTH - filled)
    pct = 100 * done // total
    sys.stderr.write(f"\r  whisker [{bar}] {done}/{total} ({pct}%)")
    sys.stderr.flush()
    if done >= total:
        sys.stderr.write("\n")
        sys.stderr.flush()


def _open_backend(workspace: str | None) -> SqliteBackend:
    if workspace:
        return SqliteBackend(Path(workspace))
    return SqliteBackend.from_env()


def _verdict_exit_code(verdicts: list[str], gate: str) -> int:
    accepted = _GATE_ACCEPTS[gate]
    if VERDICT_FAIL in verdicts and VERDICT_FAIL not in accepted:
        return C.EXIT_FAIL
    if VERDICT_REVIEW in verdicts and VERDICT_REVIEW not in accepted:
        return C.EXIT_REVIEW
    return C.EXIT_OK


def _score_main(argv: list[str]) -> int:
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
        help="directory for sidecars + report.md/report.json (default: <data>/whisker)",
    )
    parser.add_argument(
        "--gate",
        choices=("pass", "review", "fail"),
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
        backend = _open_backend(args.workspace)
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
            _render_progress(idx, total)
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

    return _verdict_exit_code([r.verdict for r in results], args.gate)


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


def _bench_main(argv: list[str]) -> int:
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
        backend = _open_backend(args.workspace)
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


def _guard_main(argv: list[str]) -> int:
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
        backend = _open_backend(args.workspace)
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
    facts_failed = any(r.failed for r in fact_reports)

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


def _run_fact_checks(corpus: Path, pairs: list[tuple[str, str, str]]) -> list:
    """Run ``<pid>.facts.jsonl`` comprehension assertions over the candidates.

    Only papers with a committed facts file are checked; the rest are silent.
    Returns one ``FactReport`` per paper that has a facts file (sorted by pid).
    Lane 3: deterministic, human-verified facts, no LLM in the loop.
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
    """Build (pid, candidate, expected) items over the human-verified corpus.

    Membership is the micro-corpus marked by ``<pid>.gt.md`` (shared with guard
    and facts). The candidate is the staged markdown; the expected snapshot is
    the committed ``<pid>.expected.md`` when present.
    """
    items: list[GoldenItem] = []
    for ref_file in sorted(corpus.glob("*.gt.md")):
        pid = ref_file.name[: -len(".gt.md")].upper()
        try:
            candidate = backend.get_paper_md(pid)
        except MissingPaperMdError as exc:
            logger.warning("skipping %s: %s", pid, exc)
            candidate = None
        expected_path = corpus / f"{pid}{GOLDEN_EXPECTED_SUFFIX}"
        expected = (
            expected_path.read_text(encoding="utf-8-sig")
            if expected_path.exists()
            else None
        )
        items.append(GoldenItem(
            pid=pid, candidate=candidate, expected=expected,
            expected_failure=pid in xfails,
        ))
    return items


def _golden_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="whisker golden",
        description="Lane 1 stability gate: exact compare vs committed snapshots",
    )
    parser.add_argument("--corpus", required=True, help="dir of <pid>.gt.md + <pid>.expected.md")
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
        backend = _open_backend(args.workspace)
    except EnvironmentError as exc:
        logger.error("%s", exc)
        return C.EXIT_ERROR

    try:
        xfails = _load_golden_manifest(corpus)
    except ValueError as exc:
        logger.error("cannot read %s: %s", GOLDEN_MANIFEST_NAME, exc)
        return C.EXIT_ERROR

    items = _load_golden_items(corpus, backend, xfails)
    if not items:
        logger.error("no <pid>.gt.md papers found in %s", corpus)
        return C.EXIT_ERROR

    if args.update:
        written = 0
        for item in items:
            if item.candidate is None:
                logger.warning("skipping %s: not staged, no snapshot written", item.pid)
                continue
            (corpus / f"{item.pid}{GOLDEN_EXPECTED_SUFFIX}").write_text(
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


def _facts_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="whisker facts",
        description="Lane 3 comprehension gate: deterministic human-verified fact assertions",
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
        backend = _open_backend(args.workspace)
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
    return C.EXIT_FAIL if failed else C.EXIT_OK


def _render_facts_summary(reports) -> str:
    """Compact human summary: one line per failing paper + a footer."""
    lines: list[str] = []
    verified = 0
    for r in sorted(reports, key=lambda x: x.pid):
        verified += r.to_dict()["verified_count"]
        if r.failed:
            detail = "; ".join(f"{c.type}:{c.detail or c.id}" for c in r.failures())
            lines.append(f"  FAIL {r.pid} {detail}")
    failed = any(r.failed for r in reports)
    verdict = "COMPREHENSION FAIL" if failed else "clean"
    lines.append(
        f"whisker facts: {verdict} over {len(reports)} paper(s) "
        f"({verified} verified fact(s) gated)"
    )
    return "\n".join(lines)


_LABEL_FAIL = "fail"
_LABEL_REVIEW = "review"
_VALID_LABELS = {"pass", _LABEL_REVIEW, _LABEL_FAIL}


def _load_labeled_samples(path: Path, backend_factory) -> list[tuple[str, str, float]]:
    """Return (pid, label, unigram_coverage) triples from a labels file.

    Accepts either a list of records ``[{"pid","label","unigram_coverage"?}]`` or
    a mapping ``{"pid": "label"}``. When ``unigram_coverage`` is absent for any
    record the store is opened and the paper is scored (reference oracle off, so
    calibration is deterministic and fast).
    """
    # utf-8-sig tolerates a UTF-8 BOM (common on Windows-edited JSON) and reads
    # plain utf-8 otherwise; a hand-authored labels file is an untrusted input.
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    records: list[dict] = []
    if isinstance(raw, dict):
        records = [{"pid": k, "label": v} for k, v in raw.items()]
    elif isinstance(raw, list):
        records = list(raw)
    else:
        raise ValueError("labels file must be a JSON object or list")

    need_backend = any("unigram_coverage" not in r for r in records)
    backend = backend_factory() if need_backend else None

    out: list[tuple[str, str, float]] = []
    for r in records:
        pid = str(r["pid"]).upper()
        label = str(r["label"]).lower()
        if label not in _VALID_LABELS:
            raise ValueError(f"{pid}: invalid label {label!r} (expected {sorted(_VALID_LABELS)})")
        if "unigram_coverage" in r:
            cov = float(r["unigram_coverage"])
        else:
            result = score_paper(pid, backend, reference_engine=None)
            cov = result.unigram_coverage
        out.append((pid, label, cov))
    return out


def _calibrate_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="whisker calibrate",
        description="Fit content-coverage edges from labeled data (TPR/FPR/precision)",
    )
    parser.add_argument(
        "--labels", required=True,
        help="JSON labels file: list of {pid,label[,unigram_coverage]} or {pid: label}",
    )
    parser.add_argument(
        "--target-fpr", type=float, default=C_DEFAULT_TARGET_FPR,
        help="max false-positive rate while maximizing recall (default: %(default)s)",
    )
    parser.add_argument("--out", help="write the fitted thresholds JSON to this path")
    parser.add_argument("--workspace", help="override $WG21_DATA_DIR")
    args = parser.parse_args(argv)

    try:
        samples = _load_labeled_samples(
            Path(args.labels), lambda: _open_backend(args.workspace)
        )
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
    fail_samples = [(cov, label == _LABEL_FAIL) for _, label, cov in samples]
    review_samples = [(cov, label in (_LABEL_FAIL, _LABEL_REVIEW)) for _, label, cov in samples]

    try:
        fail_fit = calibrate_threshold(
            fail_samples, name="unigram_coverage_fail_edge", target_fpr=args.target_fpr
        )
        review_fit = calibrate_threshold(
            review_samples, name="unigram_coverage_review_edge", target_fpr=args.target_fpr
        )
    except ValueError as exc:
        logger.error("calibration failed: %s", exc)
        return C.EXIT_ERROR

    # The two edges are fit independently, so nothing structurally forbids a
    # fitted fail edge ABOVE the review edge (an inverted, meaningless band:
    # "fail" stricter than "review"). Surface it loudly instead of shipping a
    # silently broken band; the human reviewing the fit must reconcile it.
    fail_edge = fail_fit.chosen.threshold
    review_edge = review_fit.chosen.threshold
    edge_ordering_ok = fail_edge <= review_edge
    if not edge_ordering_ok:
        logger.warning(
            "fitted fail edge %.3f > review edge %.3f: inverted band, do NOT promote "
            "as-is (more labeled data or a different --target-fpr likely needed)",
            fail_edge, review_edge,
        )

    payload = {
        "schema_version": C.WHISKER_SCHEMA_VERSION,
        "kind": "whisker-calibration",
        "n": len(samples),
        "edge_ordering_ok": edge_ordering_ok,
        "current": {
            "unigram_coverage_fail_edge": C.UNIGRAM_COVERAGE_FAIL_EDGE,
            "unigram_coverage_review_edge": C.UNIGRAM_COVERAGE_REVIEW_EDGE,
        },
        "fitted": {
            "unigram_coverage_fail_edge": fail_fit.to_dict(),
            "unigram_coverage_review_edge": review_fit.to_dict(),
        },
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        logger.info("wrote fitted thresholds to %s", args.out)
    print(text)

    for fit in (fail_fit, review_fit):
        c = fit.chosen
        logger.info(
            "%s: edge=%.3f tpr=%.3f fpr=%.3f precision=%.3f (%s, n=%d)",
            fit.name, c.threshold, c.tpr, c.fpr, c.precision, fit.method, fit.n_pos + fit.n_neg,
        )
    # Calibration is informational: it never gates. The human promotes the fitted
    # edges into constants.py after reviewing the operating points.
    return C.EXIT_OK


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "bench":
        return _bench_main(argv[1:])
    if argv and argv[0] == "guard":
        return _guard_main(argv[1:])
    if argv and argv[0] == "golden":
        return _golden_main(argv[1:])
    if argv and argv[0] == "facts":
        return _facts_main(argv[1:])
    if argv and argv[0] == "calibrate":
        return _calibrate_main(argv[1:])
    return _score_main(argv)


if __name__ == "__main__":
    sys.exit(main())
