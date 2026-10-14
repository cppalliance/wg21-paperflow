#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""CLI for whisker compare: block-aligned Markdown comparison.

Usage (no console script; invoke as a module):
    python -m whisker.det.compare.cli run <left.md> <right.md> [--html out.html] [--left-label L] [--right-label R]
    python -m whisker.det.compare.cli clean <dir>

Not registered as a console script. Used by benchmark tools
(gen_compare_pdf.py, gen_appendix.py), not by operators.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import sys
from pathlib import Path

from whisker.det.compare.align import align_documents
from whisker.det.compare.render_html import render_html

log = logging.getLogger(__name__)

__all__ = ["main"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cmd_compare(args: argparse.Namespace) -> int:
    """Run a side-by-side comparison."""
    left_path = Path(args.left)
    right_path = Path(args.right)

    if not left_path.is_file():
        print(f"Error: left file not found: {left_path}", file=sys.stderr)
        return 1
    if not right_path.is_file():
        print(f"Error: right file not found: {right_path}", file=sys.stderr)
        return 1

    left_md = left_path.read_text(encoding="utf-8")
    right_md = right_path.read_text(encoding="utf-8")

    left_label = args.left_label or left_path.stem
    right_label = args.right_label or right_path.stem

    doc = align_documents(left_md, right_md, left_label=left_label, right_label=right_label)

    print(f"Aligned {doc.total_pairs} blocks: "
          f"{doc.equal_pairs} equal, {doc.changed_pairs} changed")

    if args.html:
        html_out = Path(args.html)
        html_out.parent.mkdir(parents=True, exist_ok=True)
        html_out.write_text(render_html(doc), encoding="utf-8")
        print(f"HTML written to: {html_out}")

    if args.json:
        json_out = Path(args.json)
        json_out.parent.mkdir(parents=True, exist_ok=True)
        provenance = {
            "left": {"path": str(left_path), "sha256": _sha256(left_path), "label": left_label},
            "right": {"path": str(right_path), "sha256": _sha256(right_path), "label": right_label},
            "total_pairs": doc.total_pairs,
            "equal_pairs": doc.equal_pairs,
            "changed_pairs": doc.changed_pairs,
        }
        json_out.write_text(json.dumps(provenance, indent=2), encoding="utf-8")
        print(f"Provenance written to: {json_out}")

    return 0


def _cmd_clean(args: argparse.Namespace) -> int:
    """Remove compare output directory."""
    target = Path(args.dir)
    if not target.is_dir():
        print(f"Nothing to clean: {target} does not exist")
        return 0
    size = sum(f.stat().st_size for f in target.rglob("*") if f.is_file())
    shutil.rmtree(target)
    print(f"Removed {target} ({size / 1024 / 1024:.1f} MB)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m whisker.det.compare.cli",
        description="Block-aligned Markdown side-by-side comparison",
    )
    sub = parser.add_subparsers(dest="command")

    # compare subcommand (also the default)
    run_p = sub.add_parser("run", help="Run a comparison")
    run_p.add_argument("left", help="Path to left Markdown file")
    run_p.add_argument("right", help="Path to right Markdown file")
    run_p.add_argument("--left-label", help="Label for left pane")
    run_p.add_argument("--right-label", help="Label for right pane")
    run_p.add_argument("--html", help="Output HTML file path")
    run_p.add_argument("--json", help="Output provenance JSON path")

    # clean subcommand
    clean_p = sub.add_parser("clean", help="Remove compare output directory")
    clean_p.add_argument("dir", help="Directory to remove")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        return _cmd_compare(args)
    elif args.command == "clean":
        return _cmd_clean(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
