#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""whisker: deterministic QA verdict + benchmark for tomd conversions."""

from whisker.bench import BenchRow, aggregate, run_bench
from whisker.gates import GateResult, run_gates
from whisker.match import block_text_nid, reading_order_ned
from whisker.metrics import mhs, normalized_edit_distance, teds, text_nid
from whisker.reference import REFERENCE_ENGINES, reference_markdown
from whisker.report import build_report, render_report_md, render_summary
from whisker.score import (
    VERDICT_FAIL,
    VERDICT_PASS,
    VERDICT_REVIEW,
    WhiskerResult,
    score_markdown,
    score_paper,
    sidecar_path,
    whisker_output_dir,
)

__all__ = [
    "BenchRow",
    "GateResult",
    "REFERENCE_ENGINES",
    "VERDICT_FAIL",
    "VERDICT_PASS",
    "VERDICT_REVIEW",
    "WhiskerResult",
    "aggregate",
    "block_text_nid",
    "build_report",
    "mhs",
    "normalized_edit_distance",
    "reading_order_ned",
    "reference_markdown",
    "render_report_md",
    "render_summary",
    "run_bench",
    "run_gates",
    "score_markdown",
    "score_paper",
    "sidecar_path",
    "teds",
    "text_nid",
    "whisker_output_dir",
]

__version__ = "0.4.1"
