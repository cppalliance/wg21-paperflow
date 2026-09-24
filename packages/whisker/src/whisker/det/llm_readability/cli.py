#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""The ``llm-readability`` CLI verb surface: show the contract, check a candidate.

This module owns formatting and stdout for the llm-readability lane; the
library functions it calls return data. Routed from ``whisker.__main__`` as
``whisker llm-readability``.

Verbs:

- ``rules`` prints the universal contract, or with ``--model`` / ``--profile``
  the effectively merged rules for that model.
- ``profiles`` lists the packaged model profiles.
- ``check FILE`` runs the candidate-side deterministic evaluation. It reports
  honestly and can never print a model certification, because a candidate file
  contains no source, no model and no probe results.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from whisker.det.llm_readability.code_validate import (
    code_units_from_markdown,
    evaluate_code,
)
from whisker.det.llm_readability.contract import (
    CONSTRUCT_CODEBLOCKS,
    CONSTRUCT_DIR,
    ContractError,
    contract_to_dict,
    load_core_contract,
    render_llm_rubric,
    render_rules_markdown,
)
from whisker.det.llm_readability.models import (
    METHOD_DETERMINISTIC,
    VERDICT_FAIL,
    VERDICT_INCOMPLETE,
    VERDICT_REVIEW,
)
from whisker.det.llm_readability.profile import available_profiles, resolve_contract
from whisker.det.llm_readability.report import render_markdown, report_to_dict
from whisker.det.llm_readability.validate import evaluate, table_units_from_markdown

__all__ = ["EXIT_ERROR", "EXIT_FAIL", "EXIT_OK", "EXIT_REVIEW", "build_parser", "main"]

# whisker's CI exit contract: 0 ok, 1 operational error, 3 review, 5 fail.
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_REVIEW = 3
EXIT_FAIL = 5

_VERDICT_EXIT = {
    VERDICT_FAIL: EXIT_FAIL,
    VERDICT_REVIEW: EXIT_REVIEW,
    VERDICT_INCOMPLETE: EXIT_REVIEW,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="whisker llm-readability",
        description="Whisker llm-readability contract: show it, check against it.",
    )
    sub = parser.add_subparsers(dest="verb")

    rules = sub.add_parser("rules", help="show the contract rules")
    rules.add_argument("--profile", help="model profile id")
    rules.add_argument("--model", help="model identity from SERVICES.toml")
    rules.add_argument("--service", help="service slot name from SERVICES.toml")
    rules.add_argument("--json", action="store_true", help="emit JSON")
    rules.add_argument(
        "--rubric",
        action="store_true",
        help="emit the LLM rubric exactly as a judge lane receives it",
    )
    rules.add_argument(
        "--construct",
        default=CONSTRUCT_DIR,
        help="construct to load (tables or codeblocks, default: tables)",
    )

    sub.add_parser("profiles", help="list packaged model profiles")

    check = sub.add_parser("check", help="check a candidate markdown file")
    check.add_argument("path", help="candidate markdown file")
    check.add_argument("--profile", help="model profile id")
    check.add_argument("--model", help="model identity from SERVICES.toml")
    check.add_argument("--service", help="service slot name from SERVICES.toml")
    check.add_argument("--json", action="store_true", help="emit JSON")
    check.add_argument(
        "--construct",
        default=CONSTRUCT_DIR,
        help="construct to load (tables or codeblocks, default: tables)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    verb = args.verb or "rules"
    try:
        if verb == "rules":
            return _run_rules(args)
        if verb == "profiles":
            return _run_profiles()
        if verb == "check":
            return _run_check(args)
    except ContractError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_ERROR
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_ERROR
    parser.error(f"unknown verb {verb!r}")
    return EXIT_ERROR


def _resolved(args: argparse.Namespace):
    return resolve_contract(
        profile_id=getattr(args, "profile", None),
        model=getattr(args, "model", None),
        service=getattr(args, "service", None),
        construct=getattr(args, "construct", CONSTRUCT_DIR),
    )


def _run_rules(args: argparse.Namespace) -> int:
    resolved = _resolved(args)
    if args.json:
        print(json.dumps(contract_to_dict(resolved), indent=2, sort_keys=False))
    elif args.rubric:
        print(render_llm_rubric(resolved), end="")
    else:
        print(render_rules_markdown(resolved), end="")
    return EXIT_OK


def _run_profiles() -> int:
    core = load_core_contract()
    print(f"contract {core.id} v{core.version} sha256:{core.hash}")
    profiles = available_profiles()
    if not profiles:
        print("no packaged model profiles")
        return EXIT_OK
    for profile_id in profiles:
        resolved = resolve_contract(profile_id=profile_id)
        profile = resolved.profile
        assert profile is not None
        print(
            f"{profile.id} v{profile.version} sha256:{profile.hash} "
            f"model={profile.model_identity} "
            f"status={profile.certification_status}"
        )
    return EXIT_OK


def _run_check(args: argparse.Namespace) -> int:
    resolved = _resolved(args)
    candidate = Path(args.path).read_text(encoding="utf-8")
    construct = getattr(args, "construct", CONSTRUCT_DIR)
    if construct == CONSTRUCT_CODEBLOCKS:
        report = evaluate_code(
            resolved,
            code_units_from_markdown(candidate),
            methods_executed=(METHOD_DETERMINISTIC,),
            markdown_text=candidate,
        )
    else:
        source = Path(args.path)
        if source.with_suffix(".pdf").is_file():
            source_format = "pdf"
        elif source.with_suffix(".html").is_file():
            source_format = "html"
        else:
            source_format = "unknown"
        report = evaluate(
            resolved,
            table_units_from_markdown(candidate),
            methods_executed=(METHOD_DETERMINISTIC,),
            source_format=source_format,
            markdown=candidate,
        )
    if args.json:
        print(json.dumps(report_to_dict(report), indent=2, sort_keys=False))
    else:
        print(render_markdown(report), end="")
    if report.vacuous:
        return EXIT_OK
    return _VERDICT_EXIT.get(report.verdict, EXIT_OK)


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(main())
