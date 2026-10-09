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
    whisker bench       --corpus DIR [--baseline FILE] [--out FILE]
    whisker guard       --corpus DIR --baseline FILE [--update] [--slack F]
                        [--fail-on-new] [--out FILE]
    whisker golden      --corpus DIR [--update] [--fail-on-new] [--out FILE]
    whisker facts       --corpus DIR [--strict] [--out FILE]
    whisker delta       [--baseline FILE] [--report-dir DIR] [--json] [--llm]
    whisker calibrate   --labels FILE [--fail-target-fpr F] [--review-target-fpr F]
                        [--out FILE]
    whisker score-file  --md FILE [--ref FILE] [--source FILE] [--json]
    whisker check-facts --md FILE [--facts FILE] [--anchors FILE] [--json]
    whisker corpus      {stratify --corpus DIR | draft PID... --out DIR}
    whisker survey      {list | status [NAME] | run NAME [--refresh-runtime] [--out DIR]}
    whisker llm-readability {rules | profiles | check FILE} [--profile ID]
                        [--model NAME] [--service SLOT] [--json] [--rubric]
    whisker qa <verb>   golden QA workflow (migrated from tomd):
                        add, generate, render, score, bless, issue,
                        rebless, fact, anchor (also: whisker qa-<verb>)

The three lanes: ``golden`` is Lane 1 STABILITY (did the normalized markdown
change vs a committed ``<pid>.expected.md`` snapshot); ``bench``/``guard`` are
Lane 2 FIDELITY (how close is the output to a ``<pid>.gt.md`` reference, via
nid/teds/mhs); ``facts`` is Lane 3 COMPREHENSION (can an LLM still read it, via
deterministic source-verified ``<pid>.facts.jsonl`` assertions, no LLM in the
loop). ``guard`` additionally folds in anchors and facts conjunctively.

``bench`` reports corpus means; ``guard`` is the per-paper regression gate that
diffs each paper's each axis against a committed baseline (slack/floors read from
the baseline itself; refresh with ``--update``; ``--fail-on-new`` blocks papers
not yet in the baseline); ``golden`` is the Lane 1 stability gate that compares
each paper's normalized markdown against a committed ``<pid>.expected.md``
snapshot (refresh with ``--update``); ``facts`` is the Lane 3 comprehension gate
(only ``checked: verified`` facts gate; ``--strict`` also gates drafts);
``calibrate`` fits the coverage edges from a labeled, fit/holdout-split labels
file (P16 2.2): tau is selected on ``"calibration"``-split samples only and
TPR/FPR/precision are reported once on ``"holdout"``-split samples. The fail
and review edges fit independently, each against its own default FPR ceiling
(``--fail-target-fpr``/``--review-target-fpr``). ``delta`` is the run-to-run
regression view for the det lane: it diffs the current ``report.json`` against
the prior run's snapshot (``report.prev.json``, written automatically before
each overwrite) so an operator can see which papers got worse/better across a
tomd change, not just the current pass/review/fail snapshot. ``--llm`` switches the same verb to the advisory LLM lane's
``report-merged.json`` (renders both a det-tier and an LLM-tier section for
visibility, but exits 0 or 1 only; regression gating stays with plain
``whisker delta``). ``score-file`` and
``check-facts`` are file-based entry points
(no paperstore backend required) used by ``whisker qa-score`` / ``whisker qa-bless``
in-process. Typed exit codes (CI contract): 0 ok, 1 error, 3 review, 5 fail.
"""

from __future__ import annotations

import logging
import sys

from whisker import constants as C
from whisker.det import cli as det_cli
from whisker.det.llm_readability.cli import main as llm_readability_main
from whisker.det.qa_cli import qa_main
from whisker.menu import run_menu
from whisker.survey.cli import survey_main


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # Paper titles may contain unicode math/prose (Windows console defaults to
    # cp1252, which raises UnicodeEncodeError on unsupported characters).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv in (["-h"], ["--help"]):
        print(__doc__.strip())
        return C.EXIT_OK
    if not argv and sys.stdin.isatty() and sys.stdout.isatty():
        return run_menu()
    if argv and argv[0] == "bench":
        return det_cli.bench_main(argv[1:])
    if argv and argv[0] == "guard":
        return det_cli.guard_main(argv[1:])
    if argv and argv[0] == "golden":
        return det_cli.golden_main(argv[1:])
    if argv and argv[0] == "facts":
        return det_cli.facts_main(argv[1:])
    if argv and argv[0] == "delta":
        return det_cli.delta_main(argv[1:])
    if argv and argv[0] == "calibrate":
        return det_cli.calibrate_main(argv[1:])
    if argv and argv[0] == "corpus":
        return det_cli.corpus_main(argv[1:])
    if argv and argv[0] == "survey":
        return survey_main(argv[1:])
    if argv and argv[0] == "llm-readability":
        return llm_readability_main(argv[1:])
    if argv and argv[0] == "score-file":
        return det_cli.score_file_main(argv[1:])
    if argv and argv[0] == "check-facts":
        return det_cli.check_facts_main(argv[1:])
    if argv and argv[0].startswith("qa-"):
        verb = argv[0][3:]
        return qa_main([verb] + argv[1:])
    if argv and argv[0] == "qa":
        return qa_main(argv[1:])
    return det_cli.score_main(argv)


if __name__ == "__main__":
    sys.exit(main())
