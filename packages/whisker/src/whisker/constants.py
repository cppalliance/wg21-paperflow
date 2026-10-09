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

# -- Content coverage band edges ----------------------------------------------
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
#
# The two edges promote INDEPENDENTLY of each other (see
# corpus/calibration/PROTOCOL.md section 13): across the full 376-paper
# non-golden corpus, only 4 papers fall below the fail edge, far short of
# MIN_SAMPLES_PER_CLASS_PER_SPLIT's 10-positive-total floor, so the fail edge
# cannot be empirically fitted on this corpus while the review edge's 49-paper
# mid band can. Each constant below therefore carries its OWN
# "FAIL_EDGE:"/"REVIEW_EDGE:" marker line stating its own PROVISIONAL/
# CALIBRATED status, checked independently by
# tests/test_calibration_consistency.py's `_coverage_edge_comment_block`
# (do not remove or merge these marker lines back into one shared comment).

# FAIL_EDGE: PROVISIONAL, pre-calibration. Hand-set from the clean-paper
# expectation (tomd's check_content: clean papers land 0.90-0.97), not yet a
# value fitted on a labeled corpus. See PROTOCOL.md section 13: this edge is
# structurally unfittable on the current corpus (4/376 papers qualify as
# positive examples, below the 10 needed for a calibration/holdout split).
UNIGRAM_COVERAGE_FAIL_EDGE = 0.85

# REVIEW_EDGE: PROVISIONAL, pre-calibration. Mirrors DP-Bench/Docling
# clean-conversion recall norms and the simulation operating point, not yet a
# value fitted on a labeled corpus. Unlike the fail edge, this one has a
# workable 49-paper mid-band population (PROTOCOL.md section 13) and remains a
# realistic calibration target.
UNIGRAM_COVERAGE_REVIEW_EDGE = 0.95

# Drift above this is a soft flag (markdown carries tokens absent from source).
DRIFT_SOFT_EDGE = 0.10

# Misaligned regions are a localization signal, not a verdict on their own:
# tomd deliberately strips furniture, so some regions are expected on clean
# papers. This many or more raises a soft (review) flag; regions never hard-fail
# (unigram_coverage below the floor is the hard signal for missing content).
REGION_SOFT_COUNT = 1

# Benign-region fold: a paper whose ONLY soft flags are misaligned region(s) AND
# whose unigram coverage is at or above this floor is deemed benign and passes.
# tomd deliberately strips page furniture (headers, footers, page numbers), which
# causes region mismatches on clean papers. At unigram >= 0.95 the content is
# demonstrably complete; the regions are furniture, not missing content.
REGION_BENIGN_UNIGRAM_FLOOR = 0.95

# tomd structural QA score (0-100). Below this is a soft flag. Mirrors tomd's
# own _NEEDS_REVIEW_THRESHOLD so the two tools agree on the review line.
QA_SCORE_SOFT_EDGE = 70

# -- Benchmark metric floors (PROVISIONAL) -----------------------------------
# Used by `whisker bench` against labeled ground truth, and reused as per-axis
# soft-flag floors for the reference-oracle agreement check below.
TEDS_FLOOR = 0.80
MHS_FLOOR = 0.80
NID_FLOOR = 0.90

# Content-recall floor (multiset bag-of-words recall of GT content present in the
# candidate; see metrics.content_recall). PROVISIONAL, pre-calibration: a clean
# conversion should preserve almost all reference word occurrences, so a recall
# this far below 1.0 means a paragraph/section was dropped. Independent of
# NID_FLOOR: recall catches missing CONTENT, NID catches sequence edits, and the
# two are regressed separately (never averaged into overall), the Nougat/
# Unstructured lesson that strata must not be merged into one gate.
CONTENT_RECALL_FLOOR = 0.90

# -- Structural parity (categorical structure detection) ----------------------
# A converter that emits 0 of a marker class the reference has at least this
# many of is a categorical failure, not a degree issue. Used by
# ``structural_parity`` in bench/guard as a hard gate on labeled GT.
STRUCTURAL_PARITY_MIN_REFERENCE_COUNT = 1

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

# -- Reading-order disagreement (ADVISORY, soft only) -------------------------
# Block-matched reading-order NED between the candidate and the reference.
# OmniDocBench keeps reading order off the content gate and reports it as a
# separate axis; whisker likewise never hard-fails on reading order. A value
# above this edge raises an advisory soft flag, so a section permutation
# reaches review instead of silently passing. The edge is calibrated against
# synthetic permutation canaries: two swapped sections in a ~15-block paper
# yield reading-order NED ~0.25-0.40. A threshold of 0.10 catches any
# permutation involving more than one block pair.
READING_ORDER_SOFT_EDGE = 0.10

# -- Punctuation-sensitive text disagreement (ADVISORY, soft only) -------------
# The OmniDocBench normalizer (`clean_string`) strips all non-alphanumeric
# characters, making the text-NID axis blind to operator corruption (E28: `<=`
# vs `>=`, `T&&` vs `T&`). This soft flag compares punctuation-preserving
# token recall between the candidate markdown and the source text. When the
# content-token recall (alphanumeric) is high but the punctuation-token recall
# is lower by more than this margin, it means punctuation-carrying tokens were
# corrupted. Advisory only: never gates content.
PUNCT_RECALL_DIVERGENCE_SOFT_EDGE = 0.02

# -- Paragraph-boundary alignment (ADVISORY, soft only) -----------------------
# Every other source-aware signal is token-based, so a dropped paragraph break
# moves no token and stays invisible (see paragraph_align.py). These tunables
# govern the two typographic conventions that mark a paragraph start in a WG21
# PDF, and were fitted on the five PDF goldens plus the P0957R8 review pair.

# A first-line indent sits this many points right of the body margin. The
# window spans the observed range (P0957R8 +8.5pt to P2040R0 +19.9pt) with
# headroom; beyond it lies block quoting, not paragraph indentation.
PARA_INDENT_MIN_PT = 4.0
PARA_INDENT_MAX_PT = 40.0
# Ignore x0 clusters too small to be a document-wide convention.
PARA_INDENT_MIN_LINES = 10
# The discriminator that frequency alone gets wrong: the fraction of lines at
# a candidate x0 whose next line returns to the body margin. A first-line
# indent is isolated, a block indent sustains. Measured on P0957R8: 0.67 for
# the real indent at x0=62.5 against 0.00 for the wording block at x0=75.0,
# which has MORE lines and would win on frequency. The edge sits below the
# true value with margin and far above every decoy.
PARA_INDENT_MIN_ISOLATION = 0.45
# Slack when matching a line's left edge against margin or indent.
PARA_ALIGN_X_TOLERANCE_PT = 2.0

# Fallback convention: paragraphs flush left, separated by extra leading. A
# baseline gap above `leading * PARA_SKIP_RATIO` opens a paragraph. Gaps are
# measured baseline to baseline; bbox tops are corrupted by footnote
# superscripts (P3556R0: 15.57 against a 11.96 leading, two false breaks).
PARA_SKIP_RATIO = 1.25
# Gaps larger than this are page furniture or column breaks, not leading.
PARA_SKIP_MAX_GAP_PT = 60.0
# Below these counts the gap histogram cannot establish a convention.
PARA_SKIP_MIN_GAPS = 40
PARA_SKIP_MIN_WIDE = 10

# Short paragraphs (captions, one-line notes) align too loosely to judge.
PARA_ALIGN_MIN_WORDS = 8
# Leading words that must match verbatim to anchor a paragraph in the stream.
PARA_ALIGN_PROBE_WORDS = 6
# Resynchronisation window for small insertions/deletions during the walk.
PARA_ALIGN_MAX_SKEW = 5
# Words quoted either side of a swallowed boundary, and the evidence cap.
PARA_ALIGN_EVIDENCE_WORDS = 9
PARA_ALIGN_EVIDENCE_CAP = 10
# One swallowed source paragraph is already a structural defect worth a look.
# Soft only: tomd flattens structure by design today, so hard-gating this would
# fail the fleet the way hard-gating ref_nid and shingle coverage did before
# (see "Calibration status"). The golden-QA bless path is where it can bite.
PARAGRAPH_MERGE_SOFT_COUNT = 1

# -- Code-fence boundary alignment (ADVISORY, soft only) ----------------------
# Every other source-aware signal is token-based, so a prose line swallowed
# into a fence (or a code listing left unfenced) moves no token and stays
# invisible (see code_fence_align.py). These tunables govern the font-based
# comparison between the source PDF's monospace classification (via tomd's
# triple-signal detector) and the candidate markdown's fence boundaries.

# Direction 2: a monospaced run in the PDF must be at least this many
# consecutive lines before we consider it a "code listing" whose absence from
# a fence is a finding. Shorter runs are legitimate inline code spans.
CODE_RUN_MIN_LINES = 3
# Maximum evidence items per direction (keeps the sidecar manageable).
CODE_FENCE_EVIDENCE_CAP = 15
# One finding in either direction is already worth a look.
CODE_FENCE_SOFT_COUNT = 1

# -- Golden-ideal agreement (ADVISORY) ----------------------------------------
# Unlike the markitdown oracle, a golden ideal (tomd golden-QA workflow,
# packages/tomd/tests/fixtures/golden/ideals/) IS human-blessed ground truth,
# so the ideal panel reuses the Lane-2 bench floors (NID_FLOOR, TEDS_FLOOR,
# MHS_FLOOR, CONTENT_RECALL_FLOOR) as its advisory edges rather than the
# weaker oracle edge. Still ADVISORY ONLY: a below-floor axis raises a review
# flag, never a hard fail. Folding ideals into the hard gate would change the
# calibrated verdict model and needs its own calibration and sign-off; until
# then the ideal panel steers a human to LOOK, exactly like the oracle
# overlay, but with trustworthy per-axis floors.

# Allowed regression slack before `bench` fails against a committed baseline.
BENCH_REGRESSION_SLACK = 0.03

# -- Per-paper regression guard ----------------------------------------------
# `whisker bench --baseline` only compares the corpus MEAN overall, so a single
# paper can collapse while the mean holds (the "kein Kollateralschaden" blind
# spot). The guard (whisker.det.guard) closes it by diffing EACH paper's EACH axis
# against a committed baseline. The per-axis slack is the largest drop tolerated
# before a paper is called a regression. It is tighter than BENCH_REGRESSION_SLACK
# (a single paper, not a mean) and matches OpenDataloader-pdf's per-axis
# check_regression tolerance (benchmark thresholds.json, 0.02). whisker's scoring
# is deterministic (no LLM), so re-running tomd on unchanged code reproduces the
# metrics exactly: the slack only absorbs intended, benign output changes, not
# statistical noise.
GUARD_AXIS_SLACK = 0.02

# Axes diffed for regression vs the baseline (overall included so a broad,
# sub-slack erosion across several axes still trips the gate). content_recall is
# a first-class gate (a dropped section regresses it). Reading order is excluded:
# advisory only, never gates content (see bench module docstring).
GUARD_REGRESSION_AXES = (
    "nid", "teds", "mhs", "content_recall", "overall", "structural_parity",
)

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

# -- Region detail (content-level WHERE) -------------------------------------
# Max regions per side (missing / extra) carried into WhiskerResult and shown
# in verbose output. Keeps the sidecar and terminal manageable.
REGION_DETAIL_CAP = 5
# Display cap for a region snippet. MisalignedRegion.sample is already truncated
# to ~60 chars by tomd (_REGION_SAMPLE_CHARS); this constant documents the cap
# and is used where a snippet length reference is needed in rendering.
REGION_SNIPPET_CHARS = 60

# -- Sidecar / report schema -------------------------------------------------
# Bumped 1 -> 2 when the guard baseline gained embedded ``tool_versions`` (A2).
# Bumped 2 -> 3 for the scoring-v2 release (Phase B): a new ``content_recall``
# axis, null-eligibility for ``teds``/``mhs`` (stored as JSON null when the
# reference lacks the modality, so ``overall`` no longer averages synthetic
# 1.0s), and mistune-parsed headings (setext + inline-markup-flattened) which
# shift ``mhs`` on affected papers. A stale baseline at the old schema
# hard-fails and must be regenerated with ``whisker guard --update``. The same
# global version stamps every whisker artifact (sidecar, report, bench
# leaderboard, guard baseline, calibration).
# Bumped 3 -> 4 for the golden-ideal panel: sidecars gain five nullable
# ``ideal_*`` fields and papers with a human-blessed ideal can pick up new
# advisory ``ideal <axis> ... (advisory)`` soft flags, which may move a
# borderline pass to review. Purely additive for papers without an ideal.
# Bumped 4 -> 5 for the paragraph-boundary panel: sidecars gain three nullable
# ``paragraph_*`` fields and PDF papers whose source has a detectable paragraph
# convention can pick up a new advisory "source paragraph break(s) missing"
# soft flag, which may move a borderline pass to review. Papers that abstain
# (no convention detected) or are HTML are unaffected.
# Bumped 5 -> 6 for the code-fence boundary panel: sidecars gain three nullable
# ``fence_*`` fields and PDF papers whose source has monospaced fonts can pick
# up a new advisory "code fence boundary mismatch" soft flag. Papers without
# monospaced fonts or non-PDF sources are unaffected.
# Bumped 6 -> 7 for three new advisory benchmark axes: ``block_agreement``,
# ``structural_parity``, and ``heading_level_parity``. These are reported and
# stored but never folded into ``overall``. ``structural_parity`` becomes a
# hard gate in ``bench`` and ``guard`` (labeled GT only).
# Bumped 7 -> 8 (Phase 2a null-eligibility): ``reading_order`` (match.py's
# ``BlockMetrics`` and bench.py's ``BenchRow``) is now ``None`` on the
# matrix-budget fallback instead of a synthetic 0.0 ("perfect order"), the
# same null-eligibility rule already applied to ``teds``/``mhs`` at schema 3;
# aggregate/guard baselines carry the same value-shape change teds/mhs did.
# ``WhiskerResult`` also gains one new field, ``ideal_status``
# (``unavailable``/``absent``/``present``, see golden_ideals.py), so a
# sidecar can distinguish "no ideals checkout reachable" from "checkout
# reachable, this paper has none" instead of collapsing both into a null
# ``ideal_*`` panel. Purely additive for the ideal_status field; a stale
# baseline at schema 7 must be regenerated with ``whisker guard --update``.
# shortcut: bump from 9 to 10 for table_readability_flags field
WHISKER_SCHEMA_VERSION = 10

# -- Run-to-run delta detection (whisker delta, see delta.py) ----------------
# Minimum absolute change in a watched metric (unigram_coverage, coverage,
# ref_nid on their native 0-1 scale; qa_score on its 0-100 integer scale) to
# count as a real improvement or regression rather than rounding noise. Metric
# values in report.json are already rounded to 4 decimals
# (WhiskerResult.to_dict), so this margin sits well above that rounding floor
# while still catching a real single-percentage-point swing. On qa_score's
# integer scale this means any nonzero point drop registers, which is the
# desired behavior for a whole-number QA score.
DELTA_METRIC_EPSILON = 0.01

# Display-ordering weight only (not a scoring value): a verdict transition
# (pass/review/fail) always sorts ahead of a same-verdict metric wobble in the
# "regressed (worst first)" / "improved" sections, since crossing a verdict
# boundary is the signal an operator cares about first. Chosen well above any
# plausible metric delta (which is bounded near 1.0, or ~100 on qa_score's
# integer scale) so a single verdict-rank step always dominates.
DELTA_VERDICT_SEVERITY_WEIGHT = 1000.0

# -- Auto-baseline facts (olmOCR pattern, see facts.py) ----------------------
# Minimum alphanumeric characters for a non-empty conversion (olmOCR's
# BaselineTest checks "contains real alphanumeric output" per page; we apply
# it per document). Papers below this are extraction debris, not conversions.
BASELINE_MIN_ALNUM_CHARS = 50
# Maximum ratio of total characters that may be covered by repeated 3+char
# n-grams before the paper is flagged as mojibake/extraction debris.
BASELINE_MAX_REPEATED_NGRAM_RATIO = 0.30
