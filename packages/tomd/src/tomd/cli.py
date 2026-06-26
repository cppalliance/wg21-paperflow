#
# Copyright (c) 2026 Sean Parsons (sean.parsons@muckrack.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""tomd developer CLI: the golden QA workflow.

The package's sanctioned CLI boundary: the one tomd module that prints and
persists. All scoring, blessing, rendering, and gap logic lives in
`tomd.lib.golden_qa` / `tomd.lib.golden_gaps` (data-returning); this module only
parses arguments, calls those functions, and reports. Verbs operate on the
golden fixtures directory, never the paperstore workspace:

    tomd add <paper_id> [source]   download (or copy) a source; render pages if PDF
    tomd generate <paper_id>       seed a candidate ideal from tomd's own conversion (no LLM)
    tomd review <paper_id>         LLM punch-list of structural divergences vs source (optional)
    tomd render <paper_id>         render a PDF source to page images
    tomd score <paper_id> | --all  per-axis score vs committed baseline
    tomd bless <paper_id>          validate a candidate ideal, record baseline
    tomd issue <paper_id>          draft ready-to-file issues from the gaps
                                    --create  file them via gh CLI
    tomd rebless <paper_id> | --all ratchet baselines up after a tomd improvement

Every verb takes the same first argument, a `paper_id` (the WG21 id including
revision, `P4228R0`), normalized to the lowercase fixture stem at parse time.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from tomd.lib.golden_qa import (
    bless_stem,
    download_source,
    fidelity_verdict,
    find_source,
    generate_ideal,
    ideal_path,
    issue_for_stem,
    rebless_stems,
    render_pdf_pages,
    review_ideal,
    score_report,
    stage_source,
)

# The golden fixtures live beside the package: packages/tomd/tests/fixtures/golden.
_DEFAULT_GOLDEN = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "golden"
_RENDER_DPI = 150
# Page images are transient build artifacts; keep them out of the tracked fixtures.
_RENDER_SUBDIR = ".render"


def _manifest(args: argparse.Namespace) -> Path:
    return args.golden_dir / "baselines.json"


def _select_stems(args: argparse.Namespace) -> list[str] | None:
    """Stems to act on: every blessed paper (--all) or the one given paper_id."""
    if getattr(args, "all", False):
        manifest = _manifest(args)
        if manifest.exists():
            return sorted(json.loads(manifest.read_text(encoding="utf-8")).keys())
        return []
    if args.paper_id:
        return [args.paper_id]
    return None


def _format_rows(stem: str, rows: list) -> str:
    lines = [stem, f"  {'axis':<12}{'current':>9}{'baseline':>10}{'delta':>9}"]
    for r in rows:
        base = f"{r.baseline:.3f}" if r.baseline is not None else "-"
        delta = f"{r.delta:+.3f}" if r.delta is not None else ""
        detail = f"  ({r.detail})" if r.detail else ""
        lines.append(f"  {r.axis:<12}{r.current:>9.3f}{base:>10}{delta:>9}{detail}")
    return "\n".join(lines)


def _cmd_add(args: argparse.Namespace) -> int:
    golden, pid = args.golden_dir, args.paper_id
    if args.source_path is not None:
        try:
            dest = stage_source(pid, args.source_path, golden)
        except (ValueError, OSError) as exc:
            print(f"add: {exc}", file=sys.stderr)
            return 1
        print(f"staged {dest}")
    elif (dest := find_source(pid, golden)) is not None:
        print(f"add: {pid} already staged at {dest}")
    else:
        try:
            dest = download_source(pid, golden)
        except OSError as exc:
            print(f"add: could not download {pid} from wg21.link: {exc}", file=sys.stderr)
            return 1
        print(f"downloaded {dest}")
    if dest.suffix == ".pdf":
        out_dir = golden / _RENDER_SUBDIR / pid
        pages = render_pdf_pages(dest, out_dir, dpi=args.dpi)
        print(f"rendered {len(pages)} page(s) to {out_dir}")
    print(f"Next: `tomd generate {pid}` to seed the ideal, then `tomd bless {pid}`.")
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    pid = args.paper_id
    try:
        dest = generate_ideal(pid, args.golden_dir)
    except OSError as exc:
        print(f"generate: could not stage source for {pid}: {exc}", file=sys.stderr)
        return 1
    print(f"seeded {dest} from tomd's own conversion")
    print(f"Correct its structure against the source (optionally `tomd review {pid}`), "
          f"then `tomd bless {pid}`.")
    return 0


def _cmd_review(args: argparse.Namespace) -> int:
    pid = args.paper_id
    try:
        punch = review_ideal(pid, args.golden_dir)
    except FileNotFoundError as exc:
        print(f"review: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"review: claude exited {exc.returncode}: "
              f"{(exc.stderr or exc.stdout or '').strip()[:500]}", file=sys.stderr)
        return 1
    except (subprocess.SubprocessError, OSError) as exc:
        print(f"review: failed (needs the `claude` CLI installed and "
              f"authenticated): {exc}", file=sys.stderr)
        return 1
    print(punch)
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    golden, pid = args.golden_dir, args.paper_id
    src = find_source(pid, golden)
    if src is None:
        print(f"render: no staged source for {pid}", file=sys.stderr)
        return 1
    if src.suffix != ".pdf":
        print(f"render: {pid} is HTML; feed the HTML directly, no page render needed.")
        return 0
    out_dir = golden / _RENDER_SUBDIR / pid
    pages = render_pdf_pages(src, out_dir, dpi=args.dpi)
    print(f"rendered {len(pages)} page(s) to {out_dir}")
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    golden, manifest = args.golden_dir, _manifest(args)
    stems = _select_stems(args)
    if stems is None:
        print("score: give a paper_id or --all", file=sys.stderr)
        return 2
    payload: dict[str, dict] = {}
    chunks: list[str] = []
    missing: list[str] = []
    for stem in stems:
        try:
            rows = score_report(stem, golden, manifest)
        except FileNotFoundError:
            missing.append(stem)
            continue
        payload[stem] = {
            r.axis: {"current": r.current, "baseline": r.baseline,
                     "delta": r.delta, "detail": r.detail, "sub": r.sub}
            for r in rows
        }
        chunks.append(_format_rows(stem, rows))
    for stem in missing:
        print(f"score: no staged source for {stem}", file=sys.stderr)
    if args.as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif chunks:
        print("\n\n".join(chunks))
    return 1 if (missing and not args.all) else 0


def _cmd_bless(args: argparse.Namespace) -> int:
    golden, pid = args.golden_dir, args.paper_id
    src = find_source(pid, golden)
    if src is None:
        print(f"bless: no staged source for {pid}", file=sys.stderr)
        return 1
    ideal = ideal_path(golden, pid)
    if not ideal.is_file():
        print(f"bless: no candidate ideal at {ideal}", file=sys.stderr)
        return 1
    verdict = fidelity_verdict(src, ideal.read_text(encoding="utf-8"))
    print(f"fidelity: coverage={verdict.coverage:.3f} drift={verdict.drift:.3f} "
          "(coarse 'not gutted' guard; it does not detect paraphrase)")
    try:
        row = bless_stem(pid, golden, _manifest(args))
    except ValueError as exc:
        print(f"bless: {exc}", file=sys.stderr)
        return 1
    print(f"blessed {pid}: {json.dumps(row, sort_keys=True)}")
    print("Confirm the ideal is verbatim against the source before committing.")
    return 0


def _split_draft(draft: str) -> tuple[str, str]:
    """Split a draft into (title, body). First line is '## <title>'."""
    lines = draft.split("\n", 2)
    title = lines[0].lstrip("#").strip()
    body = lines[2] if len(lines) > 2 else ""
    return title, body


def _cmd_issue(args: argparse.Namespace) -> int:
    pid = args.paper_id
    try:
        drafts = issue_for_stem(pid, args.golden_dir)
    except FileNotFoundError:
        print(f"issue: no staged source for {pid}", file=sys.stderr)
        return 1
    if not drafts:
        print(f"issue: no gaps for {pid}; tomd matches the ideal.")
        return 0
    if not args.create:
        print(("\n\n" + "-" * 72 + "\n\n").join(drafts))
        return 0
    failed = 0
    for draft in drafts:
        title, body = _split_draft(draft)
        try:
            result = subprocess.run(
                ["gh", "issue", "create", "--title", title, "--body", body, "--label", "bug"],
                capture_output=True, text=True,
            )
        except FileNotFoundError:
            print("issue: gh not found; install from https://cli.github.com/", file=sys.stderr)
            return 1
        if result.returncode == 0:
            print(result.stdout.strip())
        else:
            print(f"issue: gh failed: {result.stderr.strip()}", file=sys.stderr)
            failed += 1
    return 1 if failed else 0


def _cmd_rebless(args: argparse.Namespace) -> int:
    golden, manifest = args.golden_dir, _manifest(args)
    stems = _select_stems(args)
    if stems is None:
        print("rebless: give a paper_id or --all", file=sys.stderr)
        return 2
    if not stems:
        print("rebless: no blessed papers to rebless", file=sys.stderr)
        return 1
    try:
        outcomes = rebless_stems(stems, golden, manifest, force=args.force)
    except ValueError as exc:
        print(f"rebless: {exc}", file=sys.stderr)
        print("Re-run with --force only if the lower scores are intentional.",
              file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"rebless: {exc}", file=sys.stderr)
        return 1
    for outcome in outcomes:
        changed = {ax: outcome.new[ax] for ax in outcome.new
                   if outcome.old.get(ax) != outcome.new[ax]}
        print(f"reblessed {outcome.stem}: {len(changed)} axis change(s) "
              f"{json.dumps(changed, sort_keys=True)}")
    return 0


def _paper_id(parser: argparse.ArgumentParser, *, optional: bool = False) -> None:
    # type=str.lower normalizes the WG21 id to the lowercase fixture stem.
    parser.add_argument("paper_id", nargs="?" if optional else None, type=str.lower)


def _all_flag(parser: argparse.ArgumentParser, verb: str) -> None:
    parser.add_argument("--all", action="store_true", help=f"{verb} every blessed paper.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tomd", description="tomd developer CLI: the golden QA workflow.")
    parser.add_argument(
        "--golden-dir", type=Path, default=_DEFAULT_GOLDEN,
        help="Fixtures dir (sources, snapshots, ideals, baselines.json).")
    sub = parser.add_subparsers(dest="action", required=True)

    p = sub.add_parser(
        "add", help="Stage a source (download from wg21.link if no path given and not "
                    "staged, or copy a local file); render PDF pages.")
    _paper_id(p)
    p.add_argument("source_path", type=Path, nargs="?",
                   help="Local source file; omit to download by paper id.")
    p.add_argument("--dpi", type=int, default=_RENDER_DPI)
    p.set_defaults(func=_cmd_add)

    p = sub.add_parser("generate", help="Seed a candidate ideal from tomd's own conversion (no LLM).")
    _paper_id(p)
    p.set_defaults(func=_cmd_generate)

    p = sub.add_parser("review", help="LLM punch-list of structural divergences vs the source (optional).")
    _paper_id(p)
    p.set_defaults(func=_cmd_review)

    p = sub.add_parser("render", help="Render a PDF source to page images for review.")
    _paper_id(p)
    p.add_argument("--dpi", type=int, default=_RENDER_DPI)
    p.set_defaults(func=_cmd_render)

    p = sub.add_parser("score", help="Per-axis score vs committed baseline, with deltas.")
    _paper_id(p, optional=True)
    _all_flag(p, "Score")
    p.add_argument("--json", dest="as_json", action="store_true", help="Emit JSON.")
    p.set_defaults(func=_cmd_score)

    p = sub.add_parser("bless", help="Validate a candidate ideal and record its baseline.")
    _paper_id(p)
    p.set_defaults(func=_cmd_bless)

    p = sub.add_parser("issue", help="Draft ready-to-file GitHub issues from the gaps.")
    _paper_id(p)
    p.add_argument("--create", action="store_true",
                   help="Create the issues in GitHub via the gh CLI.")
    p.set_defaults(func=_cmd_issue)

    p = sub.add_parser("rebless", help="Ratchet baselines up after a verified improvement.")
    _paper_id(p, optional=True)
    _all_flag(p, "Rebless")
    p.add_argument("--force", action="store_true",
                   help="Allow lowering a baseline (records a regression; off by default).")
    p.set_defaults(func=_cmd_rebless)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
