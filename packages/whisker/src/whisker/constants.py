#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tunable thresholds for the whisker QA verdict and benchmark.

Every value here is a named module-level constant (no bare literals in the
scoring path). The coverage band edges are PROVISIONAL: they encode the
clean-paper expectation documented in tomd's check_content (clean papers land
0.90-0.97) and the simulation operating point, not yet a value fitted on a
labeled corpus. The `calibrate` workflow replaces them from real data and
records the measured TPR/FPR/precision next to the chosen edges.
"""

from __future__ import annotations

# -- Content coverage band edges (PROVISIONAL, pre-calibration) --------------
# The content hard-gate runs on unigram_coverage (token-set recall), NOT on the
# shingle coverage. Every document-parsing benchmark splits two axes: content
# coverage (order-invariant: is the text present?) and reading order (is it in
# the right sequence?), and reading order NEVER gates content quality. Docling
# scores set(word_tokenize) precision/recall; Nougat reports set-F1; OmniDocBench
# Hungarian-matches blocks before NED and keeps reading-order out of the overall
# score (DP-Bench/READoc likewise). tomd's own ContentCheckResult docstring says
# it plainly: a large unigram_coverage - coverage gap means the text is present
# but reformatted (faithful, e.g. multi-column reflow), whereas a low
# unigram_coverage means content is genuinely missing.
#
# So the shingle `coverage` (5-gram, order-sensitive) is a reading-order proxy:
# reported as a metric, never a verdict flag. unigram_coverage is the gate:
#   >= REVIEW_EDGE (0.95) : content OK (DP-Bench/Docling clean-conversion recall)
#   FAIL..REVIEW          : some words missing -> soft review
#   <  FAIL_EDGE  (0.85)  : content genuinely missing -> hard fail
UNIGRAM_COVERAGE_FAIL_EDGE = 0.85
UNIGRAM_COVERAGE_REVIEW_EDGE = 0.95

# Drift above this is a soft flag (markdown carries tokens absent from source).
DRIFT_SOFT_EDGE = 0.10

# Misaligned regions are a localization signal, not a verdict on their own:
# tomd deliberately strips furniture, so some regions are expected on clean
# papers. This many or more raises a soft (review) flag; regions never hard-fail
# (unigram_coverage below the floor is the hard signal for missing content).
REGION_SOFT_COUNT = 1

# tomd structural QA score (0-100). Below this is a soft flag. Mirrors tomd's
# own _NEEDS_REVIEW_THRESHOLD so the two tools agree on the review line.
QA_SCORE_SOFT_EDGE = 70

# -- Benchmark metric floors (PROVISIONAL) -----------------------------------
# Used by `whisker bench` against labeled ground truth, and reused as per-axis
# soft-flag floors for the reference-oracle agreement check below.
TEDS_FLOOR = 0.80
MHS_FLOOR = 0.80
NID_FLOOR = 0.90

# -- Reference-oracle agreement (ADVISORY) -----------------------------------
# Cross-converter text agreement: tomd's markdown vs an independent converter's
# markdown (the oracle, e.g. markitdown), both normalized with OmniDocBench's
# clean_string so the comparison is content vs content, not formatting style.
#
# This is ADVISORY, not a gate. The literature is explicit that cross-converter
# agreement is a confidence signal, not ground truth (CE-OCR, Infinity-Parser:
# "agreement != correctness"), and no major benchmark uses a second automated
# converter as a pass/fail reference (all use human gold). So low text agreement
# raises a review flag for a human to LOOK; it NEVER hard-fails. The hard gate is
# the trustworthy reference-free path (structural gates + coverage floor).
# teds/mhs are reported per-axis but never flag: against a weak oracle (pdfminer
# emits no heading hierarchy, structures tables differently) they carry no
# reliable signal (OpenDataloader nulls such axes; OmniDocBench/kapa.ai never
# collapse per-axis scores into one number).
#
# Edge adopted from a literal repo constant: 0.85 = edgeparse's NID CI floor
# (benchmark/thresholds.json), here used to raise the advisory flag.
REF_NID_ADVISORY_EDGE = 0.85

# Allowed regression slack before `bench` fails against a committed baseline.
BENCH_REGRESSION_SLACK = 0.03

# -- Block-matching thresholds (NID, adopted VERBATIM from OmniDocBench) ------
# match_quick.py: a < 0.25 NED pre-locks a near-exact block pair, adjacent pred
# blocks are merged while they improve the match, the Hungarian assignment keeps
# pairs at <= 0.70 NED, and an unmatched GT block is rescued if some pred
# substring is within < 0.40 NED. These define the block-matched text edit that
# replaces the order-sensitive full-document NID (see metrics.block_text_nid).
BLOCK_LOCK_NED = 0.25
BLOCK_ACCEPT_NED = 0.70
BLOCK_FUZZY_RESCUE_NED = 0.40

# OmniDocBench matches blocks PER PAGE (tens of blocks), so its NED cost matrix
# is always small. whisker has no page structure in markdown and matches whole
# documents, so the matrix is O(gt_blocks * pred_blocks): a 1700-block paper
# costs ~25s. Cap it. Above this many cells, block_text_nid falls back to the
# whole-document text_nid (advisory signal either way).
# shortcut: a faithful fix is to bucket blocks into pseudo-pages (e.g. by H2
# section) and match within each; do that if large papers need block fidelity.
BLOCK_MATRIX_CELL_BUDGET = 400_000

# The < 0.40 fuzzy rescue scans every length-len(gt) window of a pred block; on a
# very long pred block that is O(pred_len * gt_len) per pair. Skip the scan for
# pred blocks longer than this (the rescue targets short embedded blocks).
BLOCK_FUZZY_MAX_PRED_LEN = 2000

# -- Exit codes (CI contract) ------------------------------------------------
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_REVIEW = 3
EXIT_FAIL = 5

# -- Terminal summary display (human output only, never touches scoring) -----
# Per-section line cap in the default terminal summary. Overflow collapses to a
# "... and N more" pointer to report.md, the way ruff/eslint/mineru cap long
# lists. -v lifts the cap and shows every paper.
SUMMARY_SECTION_CAP = 15

# -- Sidecar / report schema -------------------------------------------------
WHISKER_SCHEMA_VERSION = 1
