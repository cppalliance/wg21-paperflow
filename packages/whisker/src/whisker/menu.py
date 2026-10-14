#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Interactive TTY menu for whisker.

Launched when ``whisker`` is invoked with no arguments in a TTY. Renders a
numbered action list via rich and dispatches to the existing subcommand
functions with synthesised argv.
"""

from __future__ import annotations

import importlib
import logging
import os
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from whisker import __version__
from whisker import constants as C
from whisker.det.cli import (
    bench_main,
    delta_main,
    facts_main,
    golden_main,
    guard_main,
    score_main,
)
from whisker.det.golden import GOLDEN_EXPECTED_SUFFIX
from whisker.golden_ideals import find_ideals_dir, list_ideal_stems

logger = logging.getLogger(__name__)

_TAPETUM_LLM_PKG = "whisker.llm.cli"
_FACTS_SUFFIX = ".facts.jsonl"
_GT_SUFFIX = ".gt.md"

_CORPUS_RELPATH = Path("packages") / "whisker" / "corpus"


def _find_default_corpus(start: Path | None = None) -> Path | None:
    """Locate the committed whisker corpus by walking up to the repo root.

    Mirrors ``golden_ideals.find_ideals_dir``: checks parents of this source
    file first (whisker always lives inside the workspace checkout), then
    parents of *start* (default: cwd) for editable installs running elsewhere.
    """
    roots: list[Path] = []
    here = Path(__file__).resolve()
    roots.extend(here.parents)
    origin = (start or Path.cwd()).resolve()
    roots.append(origin)
    roots.extend(origin.parents)
    for root in roots:
        candidate = root / _CORPUS_RELPATH
        if candidate.is_dir():
            return candidate
    return None


def _count_corpus_files(corpus: Path) -> dict[str, int]:
    """Count reference files in *corpus* by type."""
    return {
        "expected": len(list(corpus.glob(f"*{GOLDEN_EXPECTED_SUFFIX}"))),
        "facts": len(list(corpus.glob(f"*{_FACTS_SUFFIX}"))),
        "gt": len(list(corpus.glob(f"*{_GT_SUFFIX}"))),
    }


def _has_tapetum_llm() -> bool:
    """Return True if the tapetum-llm extra is installed."""
    try:
        importlib.import_module(_TAPETUM_LLM_PKG)
        return True
    except ImportError:
        return False


# shortcut: llm.cli is the optional tapetum extra; import at call time so
# the TTY menu still loads when the extra is missing. Lift to file top
# when tapetum is a required dependency.
def _tapetum_main():
    from whisker.llm.cli import main as tapetum_main
    return tapetum_main


def _workspace_label() -> str:
    return os.environ.get("WG21_DATA_DIR", "(not set)")


# ── Menu actions ────────────────────────────────────────────────────────────

MENU_ITEMS: list[tuple[int, str, str]] = [
    (1, "Deterministic", "Score papers (Gates + Coverage + QA), always from scratch"),
    (2, "Deterministic + AI", "Run (1), then the tapetum-LLM advisory lane"),
    (3, "LLM only", "Advisory LLM lane: pick warm, cold, or preview"),
    (4, "Corpus Lanes", "golden | facts | bench/guard sub-menu"),
    (5, "Last Report", "Render whisker/det/report.md"),
    (6, "Delta", "What changed vs the previous run (det, llm, or both)"),
]


def _render_menu(console: Console) -> None:
    """Draw the header panel and the options table."""
    header = f"[bold]whisker[/bold] v{__version__}  |  workspace: {_workspace_label()}"
    console.print(Panel(header, expand=False, border_style="cyan"))

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan", width=5)
    table.add_column(style="bold")
    table.add_column(style="dim")

    for num, label, desc in MENU_ITEMS:
        table.add_row(f"({num})", label, desc)
    table.add_row("(q)", "Quit", "")
    console.print(table)


def _prompt_choice(console: Console) -> int | None:
    """Prompt for a menu choice. Returns None for quit."""
    raw = Prompt.ask("\n[cyan]Select[/cyan]", console=console, default="q")
    if raw.strip().lower() == "q":
        return None
    try:
        return int(raw)
    except ValueError:
        console.print(f"[red]Invalid choice:[/red] {raw!r}")
        return -1


# ── Dispatch helpers ────────────────────────────────────────────────────────

def _prompt_pids(console: Console) -> list[str]:
    """Ask whether to run all papers or specific PIDs."""
    mode = Prompt.ask(
        "[cyan]All papers or specific PIDs?[/cyan]",
        choices=["all", "pids"],
        default="all",
        console=console,
    )
    if mode == "all":
        return ["--all"]
    raw = Prompt.ask("[cyan]Enter PIDs (space-separated)[/cyan]", console=console)
    return raw.split()


def _prompt_reference(console: Console) -> list[str]:
    """Ask whether to use the reference oracle."""
    use_ref = Prompt.ask(
        "[cyan]Reference oracle?[/cyan]",
        choices=["y", "n"],
        default="y",
        console=console,
    )
    return ["--no-reference"] if use_ref == "n" else []


# The one decision an LLM run actually turns on, named the way the docs and
# the operator talk about it. Previously this was a "Force re-evaluation of
# unchanged papers?" y/n buried among six other y/n prompts, so the warm/cold
# switch was findable only if you already knew it was a --force flag.
_TAPETUM_MODES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("warm", "re-evaluate only papers whose content changed (cheap)", ()),
    ("cold", "re-evaluate every paper, ignore the fingerprint cache", ("--force",)),
    ("preview", "show what warm would skip, no LLM calls at all", ("--would-skip",)),
)


def _prompt_tapetum_mode(console: Console) -> list[str]:
    """Ask warm/cold/preview and return the matching flags.

    ``--inspect`` rides along on a real run (warm or cold) rather than being
    its own prompt: it only writes ``tapetum-inspect.md`` and was already
    defaulted to yes. Preview does not get it because it returns before any
    adjudication happens.
    """
    console.print()
    width = max(len(name) for name, _, _ in _TAPETUM_MODES)
    for name, blurb, _ in _TAPETUM_MODES:
        console.print(f"  [bold]{name:<{width}}[/bold]  [dim]{blurb}[/dim]")
    mode = Prompt.ask(
        "[cyan]Run mode?[/cyan]",
        choices=[name for name, _, _ in _TAPETUM_MODES],
        default="warm",
        console=console,
    )
    flags = [
        flag for name, _, mode_flags in _TAPETUM_MODES if name == mode
        for flag in mode_flags
    ]
    if mode != "preview":
        flags.append("--inspect")
    return flags


def _prompt_tapetum_advanced(console: Console) -> list[str]:
    """Diagnostics, behind one gate so the common path is a single Enter."""
    if Prompt.ask(
        "[cyan]Advanced options?[/cyan] [dim](retry failed papers, debug or "
        "trace transcript)[/dim]",
        choices=["y", "n"],
        default="n",
        console=console,
    ) == "n":
        return []
    flags: list[str] = []
    if Prompt.ask(
        "[cyan]Retry papers that errored last run?[/cyan]",
        choices=["y", "n"], default="n", console=console,
    ) == "y":
        flags.append("--retry-errors")
    if Prompt.ask(
        "[cyan]Debug transcript?[/cyan]",
        choices=["y", "n"], default="n", console=console,
    ) == "y":
        flags.append("--debug")
    if Prompt.ask(
        "[cyan]Trace transcript?[/cyan]",
        choices=["y", "n"], default="n", console=console,
    ) == "y":
        flags.append("--trace")
    return flags


def _prompt_tapetum_scope(console: Console) -> list[str]:
    """Ask which papers the LLM lane should adjudicate, then how.

    "all" = bare full run over every converted paper, where the warm/cold
    mode decides whether the fingerprint skip applies.
    "candidates" = risk-candidate filter (--review-all). No mode prompt: the
    fingerprint skip is off for that path by default and --force is ignored
    there, so there is no warm/cold choice to make.
    """
    scope = Prompt.ask(
        "[cyan]Scope?[/cyan] [dim](all = full corpus, candidates = whisker "
        "risk candidates)[/dim]",
        choices=["all", "candidates"],
        default="all",
        console=console,
    )
    if scope == "candidates":
        return ["--review-all", "--inspect"]
    return _prompt_tapetum_mode(console)


def _tapetum_unavailable(console: Console) -> None:
    console.print(
        "\n[yellow]tapetum-llm extra not installed.[/yellow]\n"
        "Install with: [bold]uv sync --extra tapetum-llm[/bold]\n"
    )


def _run_score(console: Console) -> int:
    """Option 1: deterministic scoring."""
    # No warm/cold prompt here on purpose: the deterministic lane has no cache
    # to reuse. Saying so is cheaper than letting the operator hunt for a
    # switch that only the LLM lane (options 2 and 3) has.
    console.print(
        "\n[dim]Rescores every requested paper from scratch. No warm/cold "
        "choice here: only the LLM lane caches.[/dim]"
    )
    argv = _prompt_pids(console) + _prompt_reference(console)
    console.print(f"\n[dim]whisker {' '.join(argv)}[/dim]\n")
    return score_main(argv)


def _run_score_plus_llm(console: Console) -> int:
    """Option 2: deterministic + LLM advisory."""
    if not _has_tapetum_llm():
        _tapetum_unavailable(console)
        return 1

    rc = _run_score(console)
    # EXIT_REVIEW / EXIT_FAIL are verdict codes, not errors: they mean advisory
    # candidates exist, which is exactly when the LLM lane should run.
    if rc not in (C.EXIT_OK, C.EXIT_REVIEW, C.EXIT_FAIL):
        console.print(f"[red]Deterministic scoring exited with {rc}, skipping LLM.[/red]")
        return rc

    console.print("\n[bold]Running tapetum-LLM advisory...[/bold]\n")
    argv = _prompt_tapetum_scope(console) + _prompt_tapetum_advanced(console)
    console.print(f"\n[dim]whisker-tapetum-llm {' '.join(argv)}[/dim]\n")
    _tapetum_main()(argv)
    return 0


def _run_llm_only(console: Console) -> int:
    """Option 3: LLM advisory (full corpus or candidates)."""
    if not _has_tapetum_llm():
        _tapetum_unavailable(console)
        return 1

    argv = _prompt_tapetum_scope(console) + _prompt_tapetum_advanced(console)
    console.print(f"\n[dim]whisker-tapetum-llm {' '.join(argv)}[/dim]\n")
    _tapetum_main()(argv)
    return 0


_LANE_SPEC: dict[int, tuple[str, tuple[str, ...], bool]] = {
    1: ("golden", (GOLDEN_EXPECTED_SUFFIX, _GT_SUFFIX), False),
    2: ("facts", (_FACTS_SUFFIX,), False),
    3: ("bench", (_GT_SUFFIX,), False),
    4: ("guard", (_GT_SUFFIX,), True),
}


def _corpus_submenu(console: Console) -> int:
    """Option 4: corpus lane sub-menu."""
    sub = Table(show_header=False, box=None, padding=(0, 2))
    sub.add_column(style="bold cyan", width=5)
    sub.add_column(style="bold")
    sub.add_row("(1)", "golden  (Lane 1: stability)")
    sub.add_row("(2)", "facts   (Lane 3: comprehension)")
    sub.add_row("(3)", "bench   (Lane 2: fidelity benchmark)")
    sub.add_row("(4)", "guard   (Lane 2: regression gate)")
    sub.add_row("(5)", "ideals  (Lane 2: score papers with a golden ideal)")
    sub.add_row("(b)", "Back")
    console.print(sub)

    raw = Prompt.ask("[cyan]Select lane[/cyan]", console=console, default="b")
    if raw.strip().lower() == "b":
        return 0

    try:
        choice = int(raw)
    except ValueError:
        console.print(f"[red]Invalid choice:[/red] {raw!r}")
        return 1

    if choice == 5:
        return _run_ideals_lane(console)

    spec = _LANE_SPEC.get(choice)
    if spec is None:
        console.print(f"[red]Unknown lane:[/red] {choice}")
        return 1

    lane_name, required_suffixes, needs_baseline = spec

    default_corpus = _find_default_corpus()
    if default_corpus is not None:
        counts = _count_corpus_files(default_corpus)
        console.print(
            f"\n[dim]{default_corpus}:\n"
            f"  {counts['expected']} {GOLDEN_EXPECTED_SUFFIX} (golden), "
            f"{counts['facts']} {_FACTS_SUFFIX} (facts), "
            f"{counts['gt']} {_GT_SUFFIX} (bench/guard)[/dim]"
        )

    prompt_kwargs: dict = {"console": console}
    if default_corpus is not None:
        prompt_kwargs["default"] = str(default_corpus)
    corpus = Prompt.ask("[cyan]Corpus directory[/cyan]", **prompt_kwargs)
    if not corpus:
        console.print("[red]Corpus path required.[/red]")
        return 1

    corpus_path = Path(corpus)
    if not corpus_path.is_dir():
        console.print(f"[red]Not a directory:[/red] {corpus}")
        return 1

    if not any(list(corpus_path.glob(f"*{suf}")) for suf in required_suffixes):
        need = " or ".join(required_suffixes)
        console.print(
            f"[yellow]{lane_name} needs {need} files, "
            f"but none were found in {corpus}.[/yellow]"
        )
        return 1

    if choice == 1:
        return golden_main(["--corpus", corpus])
    if choice == 2:
        return facts_main(["--corpus", corpus])
    if choice == 3:
        return bench_main(["--corpus", corpus])

    baseline = Prompt.ask("[cyan]Baseline JSON path[/cyan]", console=console)
    if not baseline:
        console.print("[red]Baseline path required for guard.[/red]")
        return 1
    return guard_main(["--corpus", corpus, "--baseline", baseline])


def _run_ideals_lane(console: Console) -> int:
    """Corpus lane (5): deterministic scoring restricted to ideal-backed papers.

    Auto-discovers the tomd golden ideals directory and runs the normal
    deterministic score path (option 1 semantics: sidecars, det/report.md, the
    ideal panel) over exactly the papers that have a human-blessed ideal.
    """
    ideals_dir = find_ideals_dir()
    if ideals_dir is None:
        console.print(
            "[yellow]No golden ideals directory found "
            "(packages/tomd/tests/fixtures/golden/ideals).[/yellow]"
        )
        return 1
    stems = list_ideal_stems(ideals_dir)
    if not stems:
        console.print(f"[yellow]No ideals in {ideals_dir} yet.[/yellow]")
        return 1

    console.print(f"[dim]{len(stems)} ideal(s): {', '.join(stems)}[/dim]")
    argv = [s.upper() for s in stems] + _prompt_reference(console)
    console.print(f"\n[dim]whisker {' '.join(argv)}[/dim]\n")
    return score_main(argv)


def _show_last_report(console: Console) -> int:
    """Option 5: render the last report.md via rich."""
    data_dir = os.environ.get("WG21_DATA_DIR", "")
    if not data_dir:
        console.print("[red]WG21_DATA_DIR not set.[/red]")
        return 1

    report_path = Path(data_dir) / "whisker" / "det" / "report.md"
    if not report_path.exists():
        console.print(f"[yellow]No report found at {report_path}[/yellow]")
        return 1

    md_text = report_path.read_text(encoding="utf-8")
    console.print(Markdown(md_text))
    return 0


def _show_delta(console: Console) -> int:
    """Option 6: run-to-run delta (det, llm, or both)."""
    scope = Prompt.ask(
        "[cyan]Scope?[/cyan] [dim](det = deterministic and gating, "
        "llm = advisory LLM lane, never gates, both = det then llm)[/dim]",
        choices=["det", "llm", "both"],
        default="det",
        console=console,
    )
    if scope == "det":
        console.print("\n[dim]whisker delta[/dim]\n")
        return delta_main([])
    if scope == "llm":
        console.print("\n[dim]whisker delta --llm[/dim]\n")
        return delta_main(["--llm"])
    console.print("\n[dim]whisker delta[/dim]\n")
    rc_det = delta_main([])
    console.print("\n[dim]whisker delta --llm[/dim]\n")
    rc_llm = delta_main(["--llm"])
    # An operational failure outranks a verdict code: it means one lane never
    # produced a comparison at all, which a regression code would mask.
    if C.EXIT_ERROR in (rc_det, rc_llm):
        return C.EXIT_ERROR
    # Only the det lane can return a regression code; the llm view is 0/1 by
    # contract. max() keeps that honest without asserting which lane it came
    # from, and stays correct if the det lane gains further verdict codes.
    return max(rc_det, rc_llm)


_DISPATCH: dict[int, callable] = {
    1: _run_score,
    2: _run_score_plus_llm,
    3: _run_llm_only,
    4: _corpus_submenu,
    5: _show_last_report,
    6: _show_delta,
}


# ── Entry point ─────────────────────────────────────────────────────────────

def _pause(console: Console) -> None:
    """Hold a finished result on screen until the operator is ready.

    Without this the loop redraws the menu immediately and scrolls the result
    out of reach: a delta or a fleet report is hundreds of lines. Swallows
    EOF/interrupt so a menu driven from a closed or piped stdin still falls
    through to the next iteration instead of raising.
    """
    try:
        Prompt.ask(
            "\n[dim]Enter to return to the menu[/dim]",
            default="",
            show_default=False,
            console=console,
        )
    except (EOFError, KeyboardInterrupt):
        console.print()


def run_menu() -> int:
    """Main menu loop. Returns an exit code."""
    console = Console()

    while True:
        console.print()
        _render_menu(console)
        choice = _prompt_choice(console)

        if choice is None:
            return 0
        if choice == -1:
            continue

        handler = _DISPATCH.get(choice)
        if handler is None:
            console.print(f"[red]Unknown option:[/red] {choice}")
            continue

        try:
            rc = handler(console)
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted.[/yellow]")
            rc = 130

        if rc:
            console.print(f"\n[yellow]Exited with code {rc}[/yellow]")
        else:
            console.print("\n[green]Done.[/green]")

        _pause(console)
