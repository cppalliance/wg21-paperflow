#
# Copyright (c) 2026 Sean Parsons (seanpatrick2013@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""On-demand golden QA CLI verbs for whisker.

Migrated from tomd.cli. These verbs operate on the golden fixtures directory
(packages/tomd/tests/fixtures/golden/) and are invoked as ``whisker qa-<verb>``:

    whisker qa-add <paper_id> [source]
    whisker qa-generate <paper_id>
    whisker qa-render <paper_id>
    whisker qa-score <paper_id> | --all
    whisker qa-bless <paper_id>
    whisker qa-issue <paper_id> [--create]
    whisker qa-rebless <paper_id> | --all [--force]
    whisker qa-fact <paper_id>
    whisker qa-anchor <paper_id>

qa-review (LLM punch-list via the claude CLI) has been removed.

Deterministic verbs (qa-score, qa-bless, qa-rebless) are fully functional.
qa-generate is local tomd conversion. qa-render is local PyMuPDF (no
network). No deferred LLM/network verbs remain on this surface.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from whisker.det.golden_qa import (
    _ANCHORS_TEMPLATE,
    _FACTS_TEMPLATE,
    anchors_path,
    bless_stem,
    facts_path,
    fidelity_verdict,
    find_source,
    generate_ideal,
    ideal_path,
    issue_for_stem,
    rebless_stems,
    render_pdf_pages,
    score_result,
    stage_source,
    validate_anchors_json,
    validate_facts_jsonl,
)
from whisker.golden_ideals import find_ideals_dir


def _default_golden_dir() -> Path:
    """Locate tomd's golden fixture root (ideals + sources + baselines.json).

    Reuses the ideals discovery in ``golden_ideals`` so the on-demand QA verbs
    and the deterministic lane always resolve the same checkout; the golden
    root is the ideals directory's parent. The literal fallback keeps a
    meaningful path in the ``--help`` output when no checkout is reachable.
    """
    found = find_ideals_dir()
    if found is not None:
        return found.parent
    return (
        Path(__file__).resolve().parents[3]
        / "tomd" / "tests" / "fixtures" / "golden"
    )


_DEFAULT_GOLDEN = _default_golden_dir()
_RENDER_DPI = 150
_RENDER_SUBDIR = ".render"


def _manifest(args: argparse.Namespace) -> Path:
    return args.golden_dir / "baselines.json"


def _select_stems(args: argparse.Namespace) -> list[str] | None:
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


def _format_whisker_panel(w: dict) -> str:
    lines = ["  --- whisker metrics (ideal as ground truth) ---",
             f"  {'metric':<16}{'value':>8}"]
    for key, label in [("ref_nid", "NID"), ("ref_teds", "TEDS"),
                        ("ref_mhs", "MHS"), ("content_recall", "content_recall")]:
        val = w.get(key)
        if val is not None:
            lines.append(f"  {label:<16}{val:>8.4f}")
    lines.append(f"  {'verdict':<16}{'':>3}{w.get('verdict', '?')}")
    for flag in w.get("hard_flags", []):
        lines.append(f"  FAIL  {flag}")
    for flag in w.get("soft_flags", []):
        lines.append(f"  soft  {flag}")
    return "\n".join(lines)


def _format_comprehension_panel(c: dict) -> str:
    lines = ["  --- comprehension assertions ---"]
    facts = c.get("facts")
    anchors = c.get("anchors")
    if facts:
        checks = facts.get("checks", [])
        passed = sum(1 for ch in checks if ch["passed"])
        lines.append(f"  facts    {passed}/{len(checks)} pass")
        for ch in checks:
            if not ch["passed"]:
                lines.append(f"  FAIL  [{ch['type']}] {ch.get('detail') or ''}")
    if anchors:
        checks = anchors.get("checks", [])
        passed = sum(1 for ch in checks if ch["passed"])
        lines.append(f"  anchors  {passed}/{len(checks)} pass")
        for ch in checks:
            if not ch["passed"]:
                lines.append(f"  FAIL  {ch.get('detail') or ''}")
    return "\n".join(lines) if len(lines) > 1 else ""


def _cmd_add(args: argparse.Namespace) -> int:
    golden, pid = args.golden_dir, args.paper_id
    if args.source_path is not None:
        try:
            dest = stage_source(pid, args.source_path, golden)
        except (ValueError, OSError) as exc:
            print(f"qa-add: {exc}", file=sys.stderr)
            return 1
        print(f"staged {dest}")
    elif (dest := find_source(pid, golden)) is not None:
        print(f"qa-add: {pid} already staged at {dest}")
    else:
        print(f"qa-add: no local source and no staged source for {pid}. "
              f"Provide a local file: whisker qa add {pid} <path>", file=sys.stderr)
        return 1
    if dest.suffix == ".pdf":
        out_dir = golden / _RENDER_SUBDIR / pid
        pages = render_pdf_pages(dest, out_dir, dpi=args.dpi)
        print(f"rendered {len(pages)} page(s) to {out_dir}")
    print(f"Next: `whisker qa-generate {pid}` to seed the ideal, then `whisker qa-bless {pid}`.")
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    pid = args.paper_id
    try:
        dest = generate_ideal(pid, args.golden_dir)
    except OSError as exc:
        print(f"qa-generate: could not stage source for {pid}: {exc}", file=sys.stderr)
        return 1
    print(f"seeded {dest} from tomd's own conversion")
    print(f"Correct its structure against the source, then `whisker qa-bless {pid}`.")
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    golden, pid = args.golden_dir, args.paper_id
    src = find_source(pid, golden)
    if src is None:
        print(f"qa-render: no staged source for {pid}", file=sys.stderr)
        return 1
    if src.suffix != ".pdf":
        print(f"qa-render: {pid} is HTML; feed the HTML directly, no page render needed.")
        return 0
    out_dir = golden / _RENDER_SUBDIR / pid
    pages = render_pdf_pages(src, out_dir, dpi=args.dpi)
    print(f"rendered {len(pages)} page(s) to {out_dir}")
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    golden, manifest = args.golden_dir, _manifest(args)
    stems = _select_stems(args)
    if stems is None:
        print("qa-score: give a paper_id or --all", file=sys.stderr)
        return 2
    payload: dict[str, dict] = {}
    chunks: list[str] = []
    missing: list[str] = []
    for stem in stems:
        try:
            sr = score_result(stem, golden, manifest)
        except FileNotFoundError:
            missing.append(stem)
            continue
        payload[stem] = {
            "axes": {r.axis: {"current": r.current, "baseline": r.baseline,
                     "delta": r.delta, "detail": r.detail, "sub": r.sub}
                     for r in sr.axes},
            "whisker": sr.whisker,
            "comprehension": sr.comprehension,
        }
        text_parts = [_format_rows(stem, sr.axes)]
        if sr.whisker:
            text_parts.append(_format_whisker_panel(sr.whisker))
        if sr.comprehension:
            panel = _format_comprehension_panel(sr.comprehension)
            if panel:
                text_parts.append(panel)
        chunks.append("\n\n".join(text_parts))
    for stem in missing:
        print(f"qa-score: no staged source for {stem}", file=sys.stderr)
    if args.as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif chunks:
        print("\n\n".join(chunks))
    return 1 if (missing and not args.all) else 0


def _cmd_bless(args: argparse.Namespace) -> int:
    golden, pid = args.golden_dir, args.paper_id
    src = find_source(pid, golden)
    if src is None:
        print(f"qa-bless: no staged source for {pid}", file=sys.stderr)
        return 1
    ideal = ideal_path(golden, pid)
    if not ideal.is_file():
        print(f"qa-bless: no candidate ideal at {ideal}", file=sys.stderr)
        return 1
    verdict = fidelity_verdict(src, ideal.read_text(encoding="utf-8"))
    print(f"fidelity: coverage={verdict.coverage:.3f} drift={verdict.drift:.3f} "
          "(coarse 'not gutted' guard; it does not detect paraphrase)")
    try:
        row = bless_stem(pid, golden, _manifest(args))
    except ValueError as exc:
        print(f"qa-bless: {exc}", file=sys.stderr)
        return 1
    print(f"blessed {pid}: {json.dumps(row, sort_keys=True)}")
    print("Confirm the ideal is verbatim against the source before committing.")
    return 0


def _split_draft(draft: str) -> tuple[str, str]:
    lines = draft.split("\n", 2)
    title = lines[0].lstrip("#").strip()
    body = lines[2] if len(lines) > 2 else ""
    return title, body


def _cmd_issue(args: argparse.Namespace) -> int:
    pid = args.paper_id
    try:
        drafts = issue_for_stem(pid, args.golden_dir)
    except FileNotFoundError:
        print(f"qa-issue: no staged source for {pid}", file=sys.stderr)
        return 1
    if not drafts:
        print(f"qa-issue: no gaps for {pid}; tomd matches the ideal.")
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
            print("qa-issue: gh not found; install from https://cli.github.com/", file=sys.stderr)
            return 1
        if result.returncode == 0:
            print(result.stdout.strip())
        else:
            print(f"qa-issue: gh failed: {result.stderr.strip()}", file=sys.stderr)
            failed += 1
    return 1 if failed else 0


def _cmd_rebless(args: argparse.Namespace) -> int:
    golden, manifest = args.golden_dir, _manifest(args)
    stems = _select_stems(args)
    if stems is None:
        print("qa-rebless: give a paper_id or --all", file=sys.stderr)
        return 2
    if not stems:
        print("qa-rebless: no blessed papers to rebless", file=sys.stderr)
        return 1
    try:
        outcomes = rebless_stems(stems, golden, manifest, force=args.force)
    except ValueError as exc:
        print(f"qa-rebless: {exc}", file=sys.stderr)
        print("Re-run with --force only if the lower scores are intentional.",
              file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"qa-rebless: {exc}", file=sys.stderr)
        return 1
    for outcome in outcomes:
        changed = {ax: outcome.new[ax] for ax in outcome.new
                   if outcome.old.get(ax) != outcome.new[ax]}
        print(f"reblessed {outcome.stem}: {len(changed)} axis change(s) "
              f"{json.dumps(changed, sort_keys=True)}")
        if outcome.whisker_verdict and outcome.whisker_verdict != "pass":
            print(f"  whisker: {outcome.whisker_verdict}: review structural quality",
                  file=sys.stderr)
    return 0


def _cmd_fact(args: argparse.Namespace) -> int:
    golden, pid = args.golden_dir, args.paper_id
    path = facts_path(golden, pid)
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    if is_new:
        path.write_text(_FACTS_TEMPLATE.format(pid=pid), encoding="utf-8")
        print(f"created {path}")
    else:
        count = sum(1 for line in path.read_text(encoding="utf-8").splitlines()
                    if line.strip() and not line.strip().startswith("#"))
        print(f"editing {path} ({count} existing fact(s))")
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
    try:
        subprocess.run([editor, str(path)], check=True)
    except subprocess.CalledProcessError as exc:
        print(f"qa-fact: editor exited {exc.returncode}", file=sys.stderr)
        return exc.returncode
    except FileNotFoundError:
        print(f"qa-fact: editor {editor!r} not found; edit {path} manually", file=sys.stderr)
        return 1
    errors = validate_facts_jsonl(path.read_text(encoding="utf-8"))
    if errors:
        for e in errors:
            print(f"qa-fact: {e}", file=sys.stderr)
        return 1
    count = sum(1 for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#"))
    print(f"validated {path} ({count} fact(s))")
    print(f"Next: `whisker qa-score {pid}` to see the comprehension panel.")
    return 0


def _cmd_anchor(args: argparse.Namespace) -> int:
    golden, pid = args.golden_dir, args.paper_id
    path = anchors_path(golden, pid)
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    if is_new:
        path.write_text(_ANCHORS_TEMPLATE.format(pid=pid), encoding="utf-8")
        print(f"created {path}")
    else:
        print(f"editing {path}")
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
    try:
        subprocess.run([editor, str(path)], check=True)
    except subprocess.CalledProcessError as exc:
        print(f"qa-anchor: editor exited {exc.returncode}", file=sys.stderr)
        return exc.returncode
    except FileNotFoundError:
        print(f"qa-anchor: editor {editor!r} not found; edit {path} manually", file=sys.stderr)
        return 1
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"qa-anchor: invalid JSON: {exc}", file=sys.stderr)
        return 1
    errors = validate_anchors_json(data)
    if errors:
        for e in errors:
            print(f"qa-anchor: {e}", file=sys.stderr)
        return 1
    print(f"validated {path}")
    print(f"Next: `whisker qa-score {pid}` to see the comprehension panel.")
    return 0


def _paper_id(parser: argparse.ArgumentParser, *, optional: bool = False) -> None:
    parser.add_argument("paper_id", nargs="?" if optional else None, type=str.lower)


def _all_flag(parser: argparse.ArgumentParser, verb: str) -> None:
    parser.add_argument("--all", action="store_true", help=f"{verb} every blessed paper.")


def qa_main(argv: list[str]) -> int:
    """Entry point for ``whisker qa-<verb>`` commands.

    Called from ``whisker.__main__.main()`` after stripping the ``qa-`` prefix
    and passing ``[verb, *rest]``.
    """
    parser = argparse.ArgumentParser(
        prog="whisker qa", description="Golden QA workflow (migrated from tomd).")
    parser.add_argument(
        "--golden-dir", type=Path, default=_DEFAULT_GOLDEN,
        help="Fixtures dir (sources, snapshots, ideals, baselines.json).")
    sub = parser.add_subparsers(dest="action", required=True)

    p = sub.add_parser(
        "add", help="Stage a local source file (required if not already staged); "
                    "render PDF pages.")
    _paper_id(p)
    p.add_argument("source_path", type=Path, nargs="?",
                   help="Local source file (.pdf or .html).")
    p.add_argument("--dpi", type=int, default=_RENDER_DPI)
    p.set_defaults(func=_cmd_add)

    p = sub.add_parser("generate", help="Seed a candidate ideal from tomd's own conversion (no LLM).")
    _paper_id(p)
    p.set_defaults(func=_cmd_generate)

    p = sub.add_parser("render", help="Render a PDF source to page images (local PyMuPDF).")
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

    p = sub.add_parser("fact", help="Create or edit comprehension fact assertions for a paper.")
    _paper_id(p)
    p.set_defaults(func=_cmd_fact)

    p = sub.add_parser("anchor", help="Create or edit structural anchor tripwires for a paper.")
    _paper_id(p)
    p.set_defaults(func=_cmd_anchor)

    args = parser.parse_args(argv)
    return args.func(args)
