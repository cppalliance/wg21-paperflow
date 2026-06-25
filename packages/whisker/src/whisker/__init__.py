#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""whisker: deterministic QA verdict + benchmark for tomd conversions."""

from whisker.anchors import (
    AnchorCheck,
    AnchorReport,
    AnchorSpec,
    anchor_spec_from_dict,
    check_anchors,
)
from whisker.bench import BenchRow, aggregate, run_bench
from whisker.calibrate import CalibrationResult, OperatingPoint, calibrate_threshold
from whisker.facts import (
    Fact,
    FactCheck,
    FactReport,
    check_facts,
    facts_from_records,
    parse_facts_jsonl,
)
from whisker.gates import GateResult, run_gates
from whisker.golden import (
    GoldenFinding,
    GoldenItem,
    GoldenReport,
    diff_goldens,
    normalize_for_exact_lane,
)
from whisker.guard import (
    GuardFinding,
    GuardReport,
    baseline_from_rows,
    collect_tool_versions,
    diff_rows,
)
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
    "AnchorCheck",
    "AnchorReport",
    "AnchorSpec",
    "BenchRow",
    "CalibrationResult",
    "Fact",
    "FactCheck",
    "FactReport",
    "GateResult",
    "GoldenFinding",
    "GoldenItem",
    "GoldenReport",
    "GuardFinding",
    "GuardReport",
    "OperatingPoint",
    "REFERENCE_ENGINES",
    "VERDICT_FAIL",
    "VERDICT_PASS",
    "VERDICT_REVIEW",
    "WhiskerResult",
    "aggregate",
    "anchor_spec_from_dict",
    "baseline_from_rows",
    "block_text_nid",
    "check_anchors",
    "build_report",
    "calibrate_threshold",
    "check_facts",
    "collect_tool_versions",
    "diff_goldens",
    "diff_rows",
    "facts_from_records",
    "normalize_for_exact_lane",
    "mhs",
    "parse_facts_jsonl",
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

__version__ = "0.5.0"
