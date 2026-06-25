#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Herald command-line entry point.

The parser surface is stable (`herald source add/ls/rm/enable/disable`, `herald sweep`,
`herald run`), but the handlers depend on the concrete storage backend and adapters that
land in later milestones, so they are scaffolded skeletons here. The seams the import
smoke test drives - no subcommand prints help and returns 0; `--version` exits 0 - work
without any backend or network. A raised :class:`HeraldError` is mapped to
``error: ...`` on stderr with exit code 1.
"""

from __future__ import annotations

import argparse
import sys

from herald import __version__


def _not_yet(name: str):
    def _handler(args: argparse.Namespace) -> int:  # pragma: no cover - needs later milestones
        from herald.collection.errors import HeraldError

        raise HeraldError(
            f"{name}: not available in this build (storage backend / adapters land in a later milestone)"
        )

    return _handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="herald", description="Herald collection layer")

    def _help_handler(p: argparse.ArgumentParser):
        def _handler(_args: argparse.Namespace) -> int:
            p.print_help()
            return 0

        return _handler

    parser.add_argument("--version", action="version", version=f"herald {__version__}")
    parser.add_argument(
        "--workspace", default=None, help="workspace dir (default $HERALD_WORKSPACE or ./herald-data)"
    )
    parser.set_defaults(_handler=None)
    sub = parser.add_subparsers(dest="command")

    p_source = sub.add_parser("source", help="manage sources")
    p_source.set_defaults(_handler=_help_handler(p_source))
    source = p_source.add_subparsers(dest="source_cmd")
    p_add = source.add_parser("add", help="add a source")
    p_add.add_argument("--kind", required=True)
    p_add.add_argument("--name", required=True)
    p_add.add_argument("--config", required=True, help="per-kind config as JSON")
    p_add.set_defaults(_handler=_not_yet("source add"))
    source.add_parser("ls", help="list sources").set_defaults(_handler=_not_yet("source ls"))
    p_rm = source.add_parser("rm", help="remove a source")
    p_rm.add_argument("--id", type=int, required=True)
    p_rm.set_defaults(_handler=_not_yet("source rm"))
    p_en = source.add_parser("enable", help="enable a source")
    p_en.add_argument("--id", type=int, required=True)
    p_en.set_defaults(_handler=_not_yet("source enable"))
    p_dis = source.add_parser("disable", help="disable a source")
    p_dis.add_argument("--id", type=int, required=True)
    p_dis.set_defaults(_handler=_not_yet("source disable"))

    p_sweep = sub.add_parser("sweep", help="run one sweep of a source")
    p_sweep.add_argument("--id", type=int, required=True)
    p_sweep.set_defaults(_handler=_not_yet("sweep"))

    p_run = sub.add_parser("run", help="run the scheduler + sweeps")
    p_run.add_argument("--dev", action="store_true")
    p_run.set_defaults(_handler=_not_yet("run"))

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "_handler", None)
    if handler is None:
        parser.print_help()
        return 0
    from herald.collection.errors import HeraldError

    try:
        return int(handler(args) or 0)
    except HeraldError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
