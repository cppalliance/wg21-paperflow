#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""whisker command-line entry point.

Two commands:

    whisker [PID ...] [--all] [--json] [--no-write] [--gate {pass,review,fail}]
            [--reference ENGINE | --no-reference]
    whisker bench --corpus DIR [--baseline FILE] [--out FILE]

Typed exit codes (CI contract): 0 ok, 1 error, 3 review, 5 fail.
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
from whisker.bench import aggregate, run_bench
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

    pairs: list[tuple[str, str, str]] = []
    for ref_file in sorted(corpus.glob("*.gt.md")):
        pid = ref_file.name[: -len(".gt.md")].upper()
        try:
            candidate = backend.get_paper_md(pid)
        except MissingPaperMdError as exc:
            logger.warning("skipping %s: %s", pid, exc)
            continue
        pairs.append((pid, candidate, ref_file.read_text(encoding="utf-8")))

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
            base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
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


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "bench":
        return _bench_main(argv[1:])
    return _score_main(argv)


if __name__ == "__main__":
    sys.exit(main())
