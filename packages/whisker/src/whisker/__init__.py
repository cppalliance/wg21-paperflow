#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""whisker: deterministic QA verdict + benchmark for tomd conversions."""

# The table-readability contract is re-exported as a namespace rather than
# flattened into this one. Its vocabulary (Rule, Finding, evaluate, STATUS_*)
# would collide with the names already here, and a table-readability status is
# not a whisker verdict: certification is deliberately a separate axis from
# run_gates and WhiskerResult.
from whisker.det import llm_readability
from whisker.det.anchors import (
    AnchorCheck,
    AnchorReport,
    AnchorSpec,
    anchor_spec_from_dict,
    check_anchors,
)
from whisker.det.bench import BenchRow, aggregate, run_bench
from whisker.det.calibrate import (
    CALIBRATION_ARTIFACT_SCHEMA_VERSION,
    DEFAULT_TARGET_FPR_FAIL_EDGE,
    DEFAULT_TARGET_FPR_REVIEW_EDGE,
    MIN_SAMPLES_PER_CLASS_PER_SPLIT,
    BootstrapBand,
    CalibrationResult,
    HoldoutCalibrationResult,
    HoldoutEvaluation,
    InsufficientCalibrationDataError,
    OperatingPoint,
    Split,
    bootstrap_holdout_band,
    calibrate_threshold,
    calibrate_threshold_with_holdout,
)
from whisker.det.canonical import canonicalize_conventions
from whisker.det.delta import (
    DELTA_REPORT_KIND,
    STATUS_GONE,
    STATUS_IMPROVED,
    STATUS_NEW,
    STATUS_REGRESSED,
    STATUS_UNCHANGED,
    DeltaFinding,
    DeltaResult,
    MetricDelta,
    compute_delta,
)
from whisker.det.golden import (
    GoldenFinding,
    GoldenItem,
    GoldenReport,
    diff_goldens,
    normalize_for_exact_lane,
)
from whisker.det.guard import (
    GuardFinding,
    GuardReport,
    baseline_from_rows,
    collect_tool_versions,
    diff_rows,
)
from whisker.det.match import block_text_nid, reading_order_ned
from whisker.det.probe_strength import (
    TRUNCATION_LEVELS,
    keep_fraction,
    shuffle_sections,
    strip_all_structure,
)
from whisker.det.reference import REFERENCE_ENGINES, reference_markdown
from whisker.det.report import build_report, render_report_md, render_summary
from whisker.det.score import (
    VERDICT_FAIL,
    VERDICT_PASS,
    VERDICT_REVIEW,
    WhiskerResult,
    score_markdown,
    score_paper,
    sidecar_path,
    whisker_output_dir,
)
from whisker.det.structural import MARKER_PATTERNS, count_markers
from whisker.facts import (
    Fact,
    FactCheck,
    FactReport,
    check_facts,
    facts_from_records,
    parse_facts_jsonl,
)
from whisker.gates import GateResult, run_gates
from whisker.golden_ideals import (
    IDEAL_STATUS_ABSENT,
    IDEAL_STATUS_PRESENT,
    IDEAL_STATUS_UNAVAILABLE,
    IdealPanel,
    find_ideals_dir,
    ideal_path,
    list_ideal_stems,
    resolve_ideal,
    score_against_ideal,
)
from whisker.metrics import (
    heading_level_parity,
    mhs,
    normalized_edit_distance,
    parse_headings,
    teds,
    text_nid,
)

__all__ = [
    "AnchorCheck",
    "AnchorReport",
    "AnchorSpec",
    "BenchRow",
    "BootstrapBand",
    "CALIBRATION_ARTIFACT_SCHEMA_VERSION",
    "CalibrationResult",
    "compute_delta",
    "DELTA_REPORT_KIND",
    "DEFAULT_TARGET_FPR_FAIL_EDGE",
    "DEFAULT_TARGET_FPR_REVIEW_EDGE",
    "DeltaFinding",
    "DeltaResult",
    "Fact",
    "FactCheck",
    "FactReport",
    "GateResult",
    "GoldenFinding",
    "GoldenItem",
    "GoldenReport",
    "GuardFinding",
    "GuardReport",
    "HoldoutCalibrationResult",
    "HoldoutEvaluation",
    "IDEAL_STATUS_ABSENT",
    "IDEAL_STATUS_PRESENT",
    "IDEAL_STATUS_UNAVAILABLE",
    "IdealPanel",
    "InsufficientCalibrationDataError",
    "MIN_SAMPLES_PER_CLASS_PER_SPLIT",
    "OperatingPoint",
    "REFERENCE_ENGINES",
    "Split",
    "VERDICT_FAIL",
    "VERDICT_PASS",
    "VERDICT_REVIEW",
    "WhiskerResult",
    "aggregate",
    "anchor_spec_from_dict",
    "baseline_from_rows",
    "block_text_nid",
    "canonicalize_conventions",
    "check_anchors",
    "count_markers",
    "bootstrap_holdout_band",
    "build_report",
    "calibrate_threshold",
    "calibrate_threshold_with_holdout",
    "check_facts",
    "collect_tool_versions",
    "diff_goldens",
    "diff_rows",
    "facts_from_records",
    "find_ideals_dir",
    "heading_level_parity",
    "ideal_path",
    "keep_fraction",
    "MARKER_PATTERNS",
    "list_ideal_stems",
    "MetricDelta",
    "normalize_for_exact_lane",
    "mhs",
    "parse_headings",
    "score_against_ideal",
    "parse_facts_jsonl",
    "normalized_edit_distance",
    "reading_order_ned",
    "resolve_ideal",
    "reference_markdown",
    "render_report_md",
    "render_summary",
    "run_bench",
    "run_gates",
    "score_markdown",
    "score_paper",
    "shuffle_sections",
    "sidecar_path",
    "STATUS_GONE",
    "STATUS_IMPROVED",
    "STATUS_NEW",
    "STATUS_REGRESSED",
    "STATUS_UNCHANGED",
    "strip_all_structure",
    "llm_readability",
    "teds",
    "text_nid",
    "TRUNCATION_LEVELS",
    "whisker_output_dir",
]

__version__ = "0.5.0"
