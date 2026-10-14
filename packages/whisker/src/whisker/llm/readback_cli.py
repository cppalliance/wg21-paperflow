#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""whisker-readback CLI entry point.

Console script registered as ``whisker-readback`` under the tapetum-llm
extra. Never runs in CI (LLM-touching). Reads facts from a corpus directory,
runs blind readback against the alliance-pod, and writes terminal output +
a markdown artifact per paper.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tomllib
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from paperstore.sqlite_backend import SqliteBackend

from whisker import constants as C
from whisker.facts import parse_facts_jsonl
from whisker.llm.readback import (
    readback_paper,
    render_markdown,
    render_terminal,
)

logger = logging.getLogger(__name__)

_FACTS_SUFFIX = ".facts.jsonl"
_DEFAULT_SERVICE = "alliance-pod"
_SERVICES_FILENAME = "SERVICES.toml"


def _find_services_toml() -> Path | None:
    """Walk up from cwd to find SERVICES.toml.

    whisker-local, standalone re-implementation (not imported from
    ``pipeline.services``): ``pipeline.services.load_services`` returns
    ``ModelBackend`` instances whose ``base_url``/``api_key``/``model`` are
    private by design (not meant for raw extraction outside the pipeline's own
    call paths). Reading SERVICES.toml directly here keeps whisker standalone
    (CLAUDE.md invariant) and avoids reaching into another package's private
    attributes.
    """
    here = Path.cwd()
    for parent in [here, *here.parents]:
        candidate = parent / _SERVICES_FILENAME
        if candidate.is_file():
            return candidate
    return None


def _resolve_service(service_name: str) -> tuple[str, str, str]:
    """Return (base_url, api_key, model) by parsing SERVICES.toml directly."""
    path = _find_services_toml()
    if path is None:
        raise ValueError(f"{_SERVICES_FILENAME} not found (walked up from cwd)")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    services = data.get("services", {})
    svc = services.get(service_name)
    if svc is None:
        raise ValueError(
            f"service {service_name!r} not found in {_SERVICES_FILENAME}; "
            f"available: {sorted(services)}"
        )
    base_url = svc.get("base_url", "")
    api_key_raw = svc.get("api_key", "")
    if api_key_raw.startswith("$"):
        api_key = os.environ.get(api_key_raw[1:], "")
    else:
        api_key = api_key_raw
    model = svc.get("model", "")
    return base_url, api_key, model


def _readback_exit_code(*, total_fail: int, corrupt: bool) -> int:
    """Typed exit code for a completed readback run (H2 audit finding).

    Operational errors (no corpus/workspace/key/papers) are decided earlier
    in ``main`` and always return ``C.EXIT_ERROR``; this helper only covers
    a run that actually executed checks.

    Clean mode measures comprehension directly: any comprehension failure
    is a definite defect, not an ambiguous "needs review" state, so it maps
    to ``C.EXIT_FAIL`` rather than ``C.EXIT_REVIEW``.

    Corrupt mode is the adversarial control and its expectation is
    INVERTED: the corruption is supposed to be caught. A corrupt run where
    every check still passes is an inverted canary (G6 failure mode, the
    control has no teeth) and must exit non-zero exactly like a clean-mode
    failure. A corrupt run where the pod's comprehension actually degraded
    (at least one failure) is the control working as designed and exits 0.
    """
    if corrupt:
        return C.EXIT_OK if total_fail > 0 else C.EXIT_FAIL
    return C.EXIT_FAIL if total_fail > 0 else C.EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    load_dotenv(find_dotenv())

    parser = argparse.ArgumentParser(
        prog="whisker-readback",
        description=(
            "Blind LLM readback validation: send fact-derived questions to "
            "the alliance-pod and verify comprehension."
        ),
    )
    parser.add_argument(
        "--corpus", required=True,
        help="directory of <pid>.facts.jsonl files",
    )
    parser.add_argument(
        "--workspace", help="override $WG21_DATA_DIR",
    )
    parser.add_argument(
        "--service", default=_DEFAULT_SERVICE,
        help=f"SERVICES.toml service name (default: {_DEFAULT_SERVICE})",
    )
    parser.add_argument(
        "--out", help="directory for <pid>.readback.md artifacts",
    )
    parser.add_argument(
        "--corrupt", action="store_true",
        help="run in adversarial mode (corrupt markdown, expect failures)",
    )
    parser.add_argument(
        "--corrupt-banner", action="store_true",
        help=(
            "opt-in only, requires --corrupt: prepend a priming banner "
            "telling the model to distrust the document. OFF by default "
            "because the banner confounds the measured comprehension "
            "control (H2); every report states whether it was applied"
        ),
    )
    parser.add_argument(
        "--pid", action="append",
        help="only run this PID (repeatable; default: all in corpus)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="show full pod answers in terminal output",
    )
    args = parser.parse_args(argv)

    if args.corrupt_banner and not args.corrupt:
        logger.warning("--corrupt-banner has no effect without --corrupt")

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    # Pod answers may contain unicode math/prose (Windows console defaults to
    # cp1252, which raises UnicodeEncodeError on e.g. non-ASCII operators).
    # errors="replace" degrades gracefully instead of crashing mid-report; the
    # persisted .readback.md (opened as UTF-8) always carries the exact text.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    corpus = Path(args.corpus)
    if not corpus.is_dir():
        logger.error("corpus dir not found: %s", corpus)
        return C.EXIT_ERROR

    workspace = args.workspace or os.environ.get("WG21_DATA_DIR", "")
    if not workspace:
        logger.error("set --workspace or $WG21_DATA_DIR")
        return C.EXIT_ERROR
    backend = SqliteBackend(Path(workspace))

    try:
        base_url, api_key, model = _resolve_service(args.service)
    except ValueError as exc:
        logger.error("%s", exc)
        return C.EXIT_ERROR
    if not api_key:
        logger.error("API key for service %r is empty", args.service)
        return C.EXIT_ERROR

    out_dir = Path(args.out) if args.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    pid_filter = {p.upper() for p in args.pid} if args.pid else None

    total_pass = 0
    total_fail = 0
    total_error = 0
    total_papers = 0

    for facts_file in sorted(corpus.glob(f"*{_FACTS_SUFFIX}")):
        pid = facts_file.name[: -len(_FACTS_SUFFIX)].upper()
        if pid_filter and pid not in pid_filter:
            continue

        try:
            paper_md = backend.get_paper_md(pid)
        except Exception as exc:
            logger.warning("skipping %s: %s", pid, exc)
            continue

        facts = parse_facts_jsonl(
            facts_file.read_text(encoding="utf-8-sig"), pid,
        )
        verified_facts = [f for f in facts if f.checked]
        if not verified_facts:
            logger.info("%s: no verified facts, skipping", pid)
            continue

        logger.info("readback %s: %d verified facts", pid, len(verified_facts))
        result = readback_paper(
            pid, paper_md, verified_facts,
            base_url=base_url, api_key=api_key, model=model,
            corrupt=args.corrupt, inject_banner=args.corrupt_banner,
        )

        print(render_terminal(result))
        total_pass += result.pass_count
        total_fail += result.fail_count
        total_error += result.error_count
        total_papers += 1

        if out_dir:
            md_report = render_markdown(result)
            suffix = ".readback-corrupt.md" if args.corrupt else ".readback.md"
            report_path = out_dir / f"{pid.lower()}{suffix}"
            report_path.write_text(md_report + "\n", encoding="utf-8")
            logger.info("wrote %s", report_path)

    if total_papers == 0:
        logger.error("no papers with verified facts found")
        return C.EXIT_ERROR

    exit_code = _readback_exit_code(total_fail=total_fail, corrupt=args.corrupt)

    print(f"\n{'=' * 60}")
    print(
        f"READBACK SUMMARY: {total_papers} paper(s), "
        f"{total_pass} pass, {total_fail} fail, {total_error} error"
    )
    if total_error:
        print("  (ERROR = transport failure, not comprehension: rerun those)")
    if args.corrupt:
        banner_note = "applied" if args.corrupt_banner else "not applied (default)"
        print(f"  (CORRUPT mode: failures expected; priming banner {banner_note})")
        if exit_code != C.EXIT_OK:
            print("  (INVERTED CANARY: every check passed under corruption)")
    print(f"{'=' * 60}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
