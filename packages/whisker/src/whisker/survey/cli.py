#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""CLI for the whisker survey: the repeatable competitor monitor.

Subcommands:
    whisker survey list
        Show registered competitor projects with installed/upstream versions.

    whisker survey status [NAME]
        Show last run, due status, runtime cache state.
        Exit codes: 0 = not due, 2 = due (run needed).

    whisker survey install NAME [--force]
        Build the competitor runtime and verify it, then stop. Separate from
        `run` because `run` continues into hours of inference, which is the
        wrong price for confirming a machine can build the toolchain or that
        `purge` was reversible.

    whisker survey run NAME [--refresh-runtime] [--out DIR]
        Execute a complete survey run for the named competitor: install if
        needed, convert the corpus with tomd and the competitor, score all
        three lanes, write the report.

    whisker survey purge [--dry-run] [--yes]
        Remove runtime caches and legacy install directories. Rebuild with
        `install`.

    whisker survey clean [--dry-run]
        Remove run bundles, keeping the corpus contract and protocol.

    whisker survey reports [--open]
        List every generated report with its path, newest run first. Run
        bundles are nested by date, so this is the answer to "where is the
        report" without having to know the run ID.

Competitors are resolved through the registry, and each one's adapter module is
loaded by the path its spec names. Nothing here is Marker-specific; see
``benchmark/protocol/ADDING-A-COMPETITOR.md``.

Exit codes:
    0  success / not due
    1  error
    2  due (status only: last run > 30 days or newer upstream version)
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from whisker.survey import history, registry, runtime
from whisker.survey.adapters import load_adapter
from whisker.survey.history import DUE_INTERVAL_DAYS
from whisker.survey.registry import CompetitorSpec, load_lockfile
from whisker.survey.report import build_report_json, default_report_dir, write_report
from whisker.survey.runner import (
    REPEATS,
    aggregate_lane2,
    convert_with_tomd,
    load_corpus,
    score_lane1,
    score_lane2,
    score_lane3,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_DUE = 2

_MAX_SELF_REPAIR_ATTEMPTS = 1


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def _list_cmd(args: argparse.Namespace) -> int:
    """List registered competitors."""
    competitors = registry.list_competitors()
    if not competitors:
        log.info("No competitors registered.")
        return EXIT_OK

    for spec in competitors:
        root = runtime.cache_root(spec.name, spec.pinned_version)
        status = "installed" if runtime.is_installed(root) else "not installed"
        modes = ", ".join(load_adapter(spec.adapter).MODES)
        print(f"{spec.name:12s}  {spec.display_name}")
        print(f"  {'version:':<12s} {spec.pinned_version}")
        print(f"  {'runtime:':<12s} {status}")
        print(f"  {'patches:':<12s} {len(spec.patches)}")
        print(f"  {'modes:':<12s} {modes}")
    return EXIT_OK


def _install_cmd(args: argparse.Namespace) -> int:
    """Build a competitor runtime and verify it, without running a survey.

    Installation is a side effect of ``run``, which then spends hours on
    inference. That is the wrong granularity for the two cases that matter most:
    a teammate confirming their machine can build the toolchain at all, and
    anyone checking that ``purge`` is actually reversible. Both want the install
    and nothing else.
    """
    spec = registry.get_competitor(args.name)
    if spec is None:
        log.error("Unknown competitor: %s", args.name)
        return EXIT_ERROR

    lock = load_lockfile(spec)
    adapter = load_adapter(spec.adapter)
    root = runtime.cache_root(spec.name, spec.pinned_version)

    if args.force:
        log.info("Tearing down existing runtime at %s", root)
        runtime.teardown(root)

    if runtime.is_installed(root) and not args.force:
        log.info("Runtime already installed; verifying. Use --force to rebuild.")
    else:
        log.info("Installing %s %s into %s", spec.name, spec.pinned_version, root)
        log.info("First install downloads models and a native binary; expect GBs.")
        adapter.install(root, lock)

    errors = runtime.verify_integrity(root, lock)
    venv_dir = runtime.venv_dir(root)
    installed = adapter.installed_version(venv_dir)

    print(f"Competitor:       {spec.display_name} ({spec.name})")
    print(f"Runtime root:     {root}")
    print(f"Pinned version:   {spec.pinned_version}")
    print(f"Installed:        {installed or '(absent)'}")
    print(f"Patches locked:   {len(spec.patches)}")

    if errors:
        print(f"Integrity:        FAILED ({len(errors)})")
        for err in errors:
            print(f"  {err}")
        log.error("Runtime is not usable. Re-run with --force to rebuild.")
        return EXIT_ERROR

    print("Integrity:        OK")

    # A matching version is the point of pinning; report a drift rather than
    # letting a survey run produce numbers attributed to the wrong version.
    if installed != spec.pinned_version:
        log.error(
            "Installed version %s does not match the pin %s.",
            installed, spec.pinned_version,
        )
        return EXIT_ERROR

    print("\nReady. Run the survey with:")
    print(f"  whisker survey run {spec.name}")
    return EXIT_OK


def _status_cmd(args: argparse.Namespace) -> int:
    """Show status for one or all competitors."""
    if args.name:
        spec = registry.get_competitor(args.name)
        if spec is None:
            log.error("Unknown competitor: %s", args.name)
            return EXIT_ERROR
        return _show_status(spec)

    # Show all
    any_due = False
    for spec in registry.list_competitors():
        code = _show_status(spec)
        if code == EXIT_DUE:
            any_due = True
    return EXIT_DUE if any_due else EXIT_OK


def _show_status(spec: CompetitorSpec) -> int:
    """Print status for one competitor and return exit code."""
    root = runtime.cache_root(spec.name, spec.pinned_version)

    # Non-fatal if the network is unavailable: status must work offline.
    upstream = load_adapter(spec.adapter).latest_upstream_version()

    due, reason = history.is_due(
        root,
        upstream_version=upstream,
        pinned_version=spec.pinned_version,
    )

    last = history.last_successful_run(root)
    installed = runtime.is_installed(root)

    print(f"Competitor:       {spec.display_name} ({spec.name})")
    print(f"Pinned version:   {spec.pinned_version}")
    print(f"Upstream latest:  {upstream or '(unknown)'}")
    print(f"Runtime cache:    {'OK' if installed else 'not installed'}")
    print(f"Last success:     {last['timestamp'] if last else 'never'}")
    print(f"Due:              {'YES' if due else 'no'} ({reason})")
    print(f"Due interval:     {DUE_INTERVAL_DAYS} days")
    print()

    return EXIT_DUE if due else EXIT_OK


def _run_cmd(args: argparse.Namespace) -> int:
    """Execute a complete survey run for the named competitor."""
    spec = registry.get_competitor(args.name)
    if spec is None:
        log.error("Unknown competitor: %s", args.name)
        return EXIT_ERROR

    lock = load_lockfile(spec)
    adapter = load_adapter(spec.adapter)
    root = runtime.cache_root(spec.name, spec.pinned_version)

    # Handle --refresh-runtime
    if args.refresh_runtime:
        runtime.teardown(root)

    # Ensure runtime is installed
    if not runtime.is_installed(root):
        log.info("Runtime not installed; running first-time install...")
        adapter.install(root, lock)

    # Verify integrity (with self-repair on first failure)
    errors = runtime.verify_integrity(root, lock)
    if errors:
        log.warning("Integrity check failed; attempting self-repair (1/%d):",
                    _MAX_SELF_REPAIR_ATTEMPTS)
        for err in errors:
            log.warning("  %s", err)

        # Self-repair: remove sentinel, re-run install (resumable), re-verify
        runtime.remove_sentinel(root)
        try:
            adapter.install(root, lock)
        except Exception as exc:
            log.error("Self-repair install failed: %s", exc)
            log.error(
                "Runtime is corrupt. Run with --refresh-runtime to rebuild "
                "from scratch."
            )
            return EXIT_ERROR

        errors = runtime.verify_integrity(root, lock)
        if errors:
            log.error(
                "Runtime integrity still broken after self-repair. Failures:"
            )
            for err in errors:
                log.error("  %s", err)
            log.error(
                "Run with --refresh-runtime to tear down and rebuild the "
                "runtime cache from scratch."
            )
            return EXIT_ERROR
        log.info("Self-repair succeeded; runtime integrity verified.")

    # Determine corpus root (default: the BENCH folder)
    bench_root = _default_bench_root()

    # load_corpus takes the directory holding corpus.json, which is bench/corpus,
    # not bench itself.
    try:
        corpus = load_corpus(bench_root / "corpus")
    except RuntimeError as exc:
        log.error("Corpus validation failed: %s", exc)
        return EXIT_ERROR

    log.info(
        "Corpus loaded: version=%d, %d papers",
        corpus.corpus_version,
        len(corpus.papers),
    )

    # Restrictions exist so this command can be smoke-tested. A full matrix is
    # hours of inference, which is far too expensive as a way of finding out
    # that a path is wrong. A restricted run is not a survey: its report covers
    # only what it converted, so it is written wherever --out points.
    papers = corpus.papers
    if args.pid:
        wanted = {p.lower() for p in args.pid}
        papers = [p for p in papers if p.pid.lower() in wanted]
        if not papers:
            log.error("No corpus paper matches: %s", ", ".join(args.pid))
            return EXIT_ERROR

    modes = dict(adapter.MODES)
    if args.mode:
        unknown = [m for m in args.mode if m not in modes]
        if unknown:
            log.error(
                "Unknown mode(s) for %s: %s. Available: %s",
                spec.name, ", ".join(unknown), ", ".join(adapter.MODES),
            )
            return EXIT_ERROR
        modes = {m: modes[m] for m in args.mode}

    restricted = len(papers) != len(corpus.papers) or len(modes) != len(adapter.MODES)
    if restricted:
        log.warning(
            "Restricted run: %d/%d papers, %d/%d modes. Not a full survey; "
            "this result must not be published as one.",
            len(papers), len(corpus.papers), len(modes), len(adapter.MODES),
        )

    # Determine output directory
    if args.out:
        out_dir = Path(args.out)
    else:
        out_dir = default_report_dir(bench_root)

    env_dict = runtime.build_env_dict(root, lock)
    venv_dir = runtime.venv_dir(root)
    timestamp = datetime.now(timezone.utc).isoformat()

    lane1_results: dict[str, list[dict[str, Any]]] = {}
    lane2_results: dict[str, list[dict[str, Any] | None]] = {}
    lane3_results: dict[str, list[dict[str, Any] | None]] = {}

    # Convert with tomd (twice for Lane 1)
    log.info("Converting with tomd...")
    tomd_dir = out_dir / "tomd"
    for paper in papers:
        for repeat in REPEATS:
            repeat_dir = tomd_dir / f"run-{repeat}"
            convert_with_tomd(paper.pdf_path, repeat_dir, paper.pid)

    # Output labels carry the competitor's major version, derived from the pin
    # rather than hardcoded, so a project at v1 is not filed under "v2". Built
    # once and reused, because the conversion loop and all three scoring loops
    # must agree on the directory name or the scores read empty directories.
    major = spec.pinned_version.split(".")[0]
    labels = {mode: f"{spec.name}-v{major}-{mode}" for mode in modes}
    config_labels = list(labels.values())

    # Convert with competitor
    for mode_name, mode_cfg in modes.items():
        log.info("Converting with %s mode=%s...", spec.name, mode_name)
        comp_dir = out_dir / labels[mode_name]
        for paper in papers:
            for repeat in REPEATS:
                repeat_dir = comp_dir / f"run-{repeat}"
                # Mode keys are the adapter's own vocabulary, so they are passed
                # through rather than named here.
                adapter.convert(
                    paper.pdf_path,
                    repeat_dir,
                    paper.pid,
                    env_overrides=env_dict,
                    venv_dir=venv_dir,
                    **mode_cfg,
                )

    # Score Lane 1 (stability)
    log.info("Scoring Lane 1 (stability)...")
    for config_label in ["tomd", *config_labels]:
        config_dir = out_dir / config_label
        lane1_config: list[dict[str, Any]] = []
        for paper in papers:
            run_a = config_dir / "run-a" / f"{paper.pid}.md"
            run_b = config_dir / "run-b" / f"{paper.pid}.md"
            lane1_config.append(score_lane1(run_a, run_b, paper.pid))
        lane1_results[config_label] = lane1_config

    # Score Lane 2 (fidelity) on run-a (E1)
    log.info("Scoring Lane 2 (fidelity)...")
    for config_label in ["tomd", *config_labels]:
        config_dir = out_dir / config_label
        lane2_config: list[dict[str, Any] | None] = []
        for paper in papers:
            candidate = config_dir / "run-a" / f"{paper.pid}.md"
            lane2_config.append(
                score_lane2(candidate, paper.ideal_path, paper.pid)
            )
        lane2_results[config_label] = lane2_config

    # Score Lane 3 (comprehension) on run-a
    log.info("Scoring Lane 3 (comprehension)...")
    for config_label in ["tomd", *config_labels]:
        config_dir = out_dir / config_label
        lane3_config: list[dict[str, Any] | None] = []
        for paper in papers:
            candidate = config_dir / "run-a" / f"{paper.pid}.md"
            lane3_config.append(
                score_lane3(candidate, paper.facts_path, paper.pid)
            )
        lane3_results[config_label] = lane3_config

    # Aggregate Lane 2
    lane2_agg: dict[str, Any] = {}
    for config_label, rows in lane2_results.items():
        valid = [r for r in rows if r is not None]
        if valid:
            lane2_agg[config_label] = aggregate_lane2(valid)

    # Build and write report
    report = build_report_json(
        competitor_name=spec.name,
        competitor_version=spec.pinned_version,
        corpus_version=corpus.corpus_version,
        timestamp=timestamp,
        lane1=lane1_results,
        lane2=lane2_results,
        lane3=lane3_results,
        lane2_aggregate=lane2_agg,
    )
    write_report(report, out_dir, spec.name)

    # Record in history
    history.append_run(
        root,
        timestamp=timestamp,
        version=spec.pinned_version,
        corpus_version=corpus.corpus_version,
        report_dir=str(out_dir),
        success=True,
    )

    log.info("Survey run complete. Report written to %s", out_dir)
    return EXIT_OK


# ---------------------------------------------------------------------------
# Purge and clean commands
# ---------------------------------------------------------------------------

_LEGACY_DIRS = [
    Path("C:/mkr2venv"),
    Path("C:/mkr2tools"),
]


def _dir_size(path: Path) -> int:
    """Total size of all files under path, in bytes."""
    if not path.is_dir():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _format_size(nbytes: int) -> str:
    if nbytes < 1024:
        return f"{nbytes} B"
    if nbytes < 1024 * 1024:
        return f"{nbytes / 1024:.1f} KB"
    if nbytes < 1024 * 1024 * 1024:
        return f"{nbytes / 1024 / 1024:.1f} MB"
    return f"{nbytes / 1024 / 1024 / 1024:.2f} GB"


def _purge_cmd(args: argparse.Namespace) -> int:
    """Remove runtime caches and legacy install directories."""
    targets: list[tuple[Path, str]] = []

    # Survey runtime cache (%LOCALAPPDATA%/whisker/survey/)
    local_app = Path(os.environ.get("LOCALAPPDATA", ""))
    if local_app.name:
        survey_cache = local_app / "whisker" / "survey"
        if survey_cache.is_dir():
            targets.append((survey_cache, "survey runtime cache"))

    # Legacy dirs
    for legacy in _LEGACY_DIRS:
        if legacy.is_dir():
            targets.append((legacy, f"legacy install ({legacy})"))

    if not targets:
        print("Nothing to purge. All caches are clean.")
        return EXIT_OK

    total = 0
    print("Purge inventory:")
    for path, desc in targets:
        size = _dir_size(path)
        total += size
        print(f"  {_format_size(size):>10}  {desc}: {path}")
    print(f"  {'─' * 10}")
    print(f"  {_format_size(total):>10}  TOTAL")

    if args.dry_run:
        print("\n(dry-run: no files removed)")
        return EXIT_OK

    if not args.yes:
        print("\nThis will permanently delete the above directories.")
        answer = input("Continue? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted.")
            return EXIT_OK

    for path, desc in targets:
        print(f"  Removing {path}...")
        shutil.rmtree(path, ignore_errors=True)
    print("Purge complete.")
    return EXIT_OK


def _clean_cmd(args: argparse.Namespace) -> int:
    """Remove benchmark run bundles (keeps corpus, protocol, archive)."""
    bench = _default_bench_root()
    runs_dir = bench / "runs"

    if not runs_dir.is_dir():
        print("No runs directory found. Nothing to clean.")
        return EXIT_OK

    run_dirs = [d for d in sorted(runs_dir.iterdir()) if d.is_dir()]
    if not run_dirs:
        print("No run bundles found.")
        return EXIT_OK

    total = 0
    print("Run bundles:")
    for d in run_dirs:
        size = _dir_size(d)
        total += size
        print(f"  {_format_size(size):>10}  {d.name}")
    print(f"  {'─' * 10}")
    print(f"  {_format_size(total):>10}  TOTAL")

    if args.dry_run:
        print("\n(dry-run: no files removed)")
        return EXIT_OK

    for d in run_dirs:
        print(f"  Removing {d.name}...")
        shutil.rmtree(d)
    print("Clean complete. Corpus and protocol remain intact.")
    return EXIT_OK


# Report file stems worth surfacing.
_REPORT_STEMS = (
    "report",
    "findings-marker",
    "findings-whisker",
    "defect-inventory",
    "final-audit",
)
_REPORT_SUFFIXES = (".pdf", ".html", ".md")

# Published deliverables live under reports/; runs/ is searched too because
# older bundles kept their report inline and the locator must still find them.
_REPORT_ROOTS = ("reports", "runs")


def _find_reports(bench: Path) -> list[Path]:
    """Locate report artifacts, most recent first.

    Searches both roots and tolerates varying nesting depth, because run bundles
    from different generations placed their reports differently.

    Ordering is by modification time, not by directory name. Sorting names in
    reverse puts ``2026-08-pilot`` ahead of ``2026-08`` and would report a
    superseded pilot as the newest report.
    """
    found: set[Path] = set()

    for root_name in _REPORT_ROOTS:
        root = bench / root_name
        if not root.is_dir():
            continue
        for stem in _REPORT_STEMS:
            for suffix in _REPORT_SUFFIXES:
                for path in root.rglob(f"{stem}{suffix}"):
                    # Exclude the per-comparison PDF bundle: those are appendices,
                    # not reports, and there are twelve of them.
                    if "compare" in path.relative_to(root).parts:
                        continue
                    found.add(path)

    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def _reports_cmd(args: argparse.Namespace) -> int:
    """List report artifacts, and optionally open the newest one."""
    bench = _default_bench_root()
    reports = _find_reports(bench)

    if not reports:
        print(f"No reports found under {bench / 'reports'}")
        return EXIT_ERROR

    print(f"Reports under {bench}\n")
    for path in reports:
        size = path.stat().st_size
        stamp = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"  {path.relative_to(bench).as_posix():<52} {size:>9,}  {stamp}")

    newest = next(
        (p for p in reports if p.suffix == ".pdf"),
        reports[0],
    )
    print(f"\nNewest: {newest}")

    if args.open:
        # webbrowser handles the platform's default application for the type.
        webbrowser.open(newest.resolve().as_uri())
        print("Opened in the default viewer.")

    return EXIT_OK


def _default_bench_root() -> Path:
    """Return the default BENCH root (packages/whisker/benchmark/)."""
    here = Path(__file__).resolve()
    # packages/whisker/src/whisker/survey/cli.py -> parents[3] = packages/whisker
    return here.parents[3] / "benchmark"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for the survey subcommand."""
    parser = argparse.ArgumentParser(
        prog="whisker survey",
        description=(
            "Repeatable monthly competitor monitor. "
            "Converts corpus PDFs with tomd and a registered competitor, "
            "scores all Whisker lanes, and generates a report."
        ),
        epilog=(
            f"Exit codes: 0 = ok/not due, 1 = error, "
            f"2 = due (status: last run > {DUE_INTERVAL_DAYS} days "
            f"or newer upstream version detected)."
        ),
    )
    sub = parser.add_subparsers(dest="subcmd")

    sub.add_parser("list", help="List registered competitors")

    status_p = sub.add_parser(
        "status",
        help="Show last run, due status, and runtime state",
    )
    status_p.add_argument("name", nargs="?", help="Competitor name (default: all)")

    install_p = sub.add_parser(
        "install",
        help="Build and verify a competitor runtime without running a survey",
    )
    install_p.add_argument("name", help="Competitor name")
    install_p.add_argument(
        "--force", action="store_true",
        help="Tear down an existing runtime and rebuild it from scratch",
    )

    run_p = sub.add_parser(
        "run",
        help="Execute a complete monthly survey run",
    )
    run_p.add_argument("name", help="Competitor name")
    run_p.add_argument(
        "--refresh-runtime", action="store_true",
        help="Tear down and rebuild the runtime cache before running",
    )
    run_p.add_argument(
        "--out", metavar="DIR",
        help="Output directory for reports (default: BENCH/reports/YYYY-MM/)",
    )
    run_p.add_argument(
        "--pid", action="append", metavar="PID",
        help="Restrict to one corpus paper (repeatable). For smoke-testing "
             "only: the result is not a survey",
    )
    run_p.add_argument(
        "--mode", action="append", metavar="NAME",
        help="Restrict to one competitor mode (repeatable). See `survey list` "
             "for the modes a competitor declares",
    )

    purge_p = sub.add_parser(
        "purge",
        help="Remove runtime caches (venvs, models, legacy dirs)",
    )
    purge_p.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be removed with sizes, but do not delete",
    )
    purge_p.add_argument(
        "--yes", action="store_true",
        help="Skip confirmation prompt",
    )

    clean_p = sub.add_parser(
        "clean",
        help="Remove benchmark run bundles (keeps corpus and protocol)",
    )
    clean_p.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be removed with sizes, but do not delete",
    )

    reports_p = sub.add_parser(
        "reports",
        help="List generated reports and show where they are stored",
    )
    reports_p.add_argument(
        "--open", action="store_true",
        help="Open the newest report PDF in the default viewer",
    )

    return parser


def survey_main(argv: list[str]) -> int:
    """Entry point for the survey subcommand, called from whisker __main__."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.subcmd is None:
        parser.print_help()
        return EXIT_ERROR

    if args.subcmd == "list":
        return _list_cmd(args)
    if args.subcmd == "status":
        return _status_cmd(args)
    if args.subcmd == "install":
        return _install_cmd(args)
    if args.subcmd == "run":
        return _run_cmd(args)
    if args.subcmd == "purge":
        return _purge_cmd(args)
    if args.subcmd == "clean":
        return _clean_cmd(args)
    if args.subcmd == "reports":
        return _reports_cmd(args)

    parser.print_help()
    return EXIT_ERROR
