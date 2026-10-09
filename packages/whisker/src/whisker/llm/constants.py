#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tunable thresholds for the tapetum_llm advisory lane.

Every cutoff is a named constant (no bare literals in the cascade), mirroring
whisker core's constants discipline.
"""

from __future__ import annotations

# Guard tag used to delimit untrusted source text in every tapetum_llm prompt
# (both lanes, all call types). It is a constant, identical across papers and
# across runs, for two reasons: (1) the vLLM prefix cache can reuse the KV
# blocks of the 28-33k-char shared system prompt across all papers of a fleet
# run only if the first bytes are identical, and a per-paper tag at byte 0
# defeats it; (2) identical prompt bytes across runs are a precondition for
# measuring verdict stability at all. Tag secrecy is not the injection
# control: pipeline.tools.escape_guard_delimiters escapes forged delimiter
# text before wrapping, so a paper that knows the tag still cannot close it.
GUARD_TAG = "SRCA7E2C9D1"

# Sentinel confidence for the metadata-first short-circuit stub. When the
# HTML metadata check already caps the paper, triage is skipped and a
# synthetic Adjudication is created with this confidence. It is NOT 0.0
# (which the code interprets as a "mechanical anomaly" and demotes pass to
# review): the stub verdict is already review or fail from metadata, so the
# demotion is a no-op but the 0.0 value pollutes stability measurements.
# Named constant so audits do not mistake it for a model output.
SHORT_CIRCUIT_CONFIDENCE = 0.01

# Cascade escalation. Tier 1 (the fast slot) emits a confidence in [0, 1]. When
# that confidence falls inside the ambiguous band, the call escalates to Tier 2
# (the deep slot). Outside the band, the Tier 1 verdict stands. Adopted from the
# LLM-as-judge cascade literature (escalate on calibrated uncertainty, not raw
# confidence); these are provisional and must be refit on the labeled review set
# (see the mini-eval), exactly like whisker's UNIGRAM_COVERAGE edges.
#
# The band alone proved dead in production (0/198 escalations; DeepSeek's
# self-reported confidence never left [0.85, 1.00]), so escalation now also
# fires on DERIVED uncertainty signals (see the SIGNAL_* names below): the
# scalar band is kept as one trigger among three, not the sole gate.
CONFIDENCE_AMBIGUOUS_LO = 0.35
CONFIDENCE_AMBIGUOUS_HI = 0.65

# Derived escalation-signal names, recorded verbatim in the sidecar
# (TapetumResult.escalation_signals) so a reviewer can see WHY tier 2 fired.
# SIGNAL_AXIS_CONFLICT: tier-1 per-axis verdicts contain both a pass and a
#   fail (internal contradiction; self-reported confidence is anti-calibrated
#   and hides this, measured at 123/198 papers with axis disagreement).
# SIGNAL_UNGROUNDED_EVIDENCE: at least one tier-1 evidence quote failed
#   grounding against the markdown (the model cited text that is not there).
# SIGNAL_CONFIDENCE_AMBIGUOUS: the legacy scalar band trigger.
SIGNAL_AXIS_CONFLICT = "axis_conflict"
SIGNAL_UNGROUNDED_EVIDENCE = "ungrounded_evidence"
SIGNAL_CONFIDENCE_AMBIGUOUS = "confidence_ambiguous"

# Severity at which an axis "fail" becomes a hard overall fail. A fail-labeled
# axis below this severity (the model's recoverable/cosmetic call, e.g. a
# heading-level jump) folds to "review", which is what lets the false-fail
# RESCUE population (heading_monotone-only) actually be rescued. Mirrors the
# AxisFinding.severity Literal in models.py.
SEVERITY_MAJOR = "major"

# Per-request markdown budget. The whole paper.md is injected into one LLM
# request; oversized papers 413 at the pod's nginx body cap (~1 MB). Papers
# above this char budget are split on H2 boundaries into <= budget chunks,
# triaged serially, and aggregated (see chunking.py). Conservative: after
# JSON-escaping plus the system prompt the request body stays well under 1 MB.
# Tunable: if a single chunk still 413s, lower this. Only ~6 papers in the
# corpus exceed it; a 2.5 MB paper yields ~5-6 serial chunks.
MAX_PAPER_MD_CHARS = 500_000

# Evidence grounding: spans the model quotes are checked against the paper
# markdown (verbatim, normalized whitespace). A quote that cannot be located is
# dropped as ungrounded (the langextract `char_interval is None` reject signal).
# If no grounded evidence survives, the suggestion is demoted to "review".
EVIDENCE_FUZZY_FLOOR = 0.90

# Minimum normalized-quote length (chars) for the fuzzy partial_ratio tier.
# partial_ratio compares the quote against the WHOLE document, so a short
# generic phrase ("the committee", "this paper") clears 0.90 trivially.
# Quotes below this length must ground exactly or by normalized substring.
EVIDENCE_MIN_FUZZY_CHARS = 20

# Maximum evidence quotes accepted from either the monolith PDF judge or one
# page escalation. The prompt, output schema, and defensive consumers share it.
MAX_MISSING_QUOTES = 5

# -- Ideal-verification (candidate vs. blessed golden) -------------------------
# Schema bounds for the verifier's structured output. These are not
# display-time truncation: valid sidecars preserve complete grounded text
# while malformed or oversized untrusted sidecars are rejected as neutral.
MAX_IDEAL_DISCREPANCIES = 10
MAX_IDEAL_QUOTE_CHARS = 500
MAX_IDEAL_EXPLANATION_CHARS = 500

# -- Candidate-selection thresholds (PROVISIONAL, pending mini-eval) -----------
# These gate which papers are forwarded to the advisory LLM lane. All are
# PROVISIONAL; final values will be fitted on a labeled holdout.

# unigram_coverage - coverage gap above this triggers a false-pass candidate.
# A large gap means all words are present (high unigram) but reading order is
# scrambled (low shingle coverage). The 0.15 value flags papers with 15pp+ gap.
COV_UNIGRAM_GAP_TRIGGER = 0.15

# Papers in the pass tier carrying any of these risk signals are false-pass
# candidates: lossy_table_count > 0, table_parse_errors > 0, mojibake_count > 0,
# or a unigram-coverage - coverage gap > COV_UNIGRAM_GAP_TRIGGER. These signals
# are present on WhiskerResult but never consumed by score._decide or gates.

# Unigram coverage floor for skipping region-only review papers (the benign
# region filter from synthesis 2a SECONDARY). Papers whose sole soft flag is
# "misaligned region(s)" AND unigram_coverage >= this value are benign: tomd
# deliberately strips furniture, and the coverage is fine.
REGION_BENIGN_UNIGRAM_FLOOR = 0.95

# -- Binary-payload stripping (pre-LLM, research/research/base64-blob-filter) -----------
# Inline data-URI images (`![alt](data:...;base64,...)`) reached 1.1 MB per
# LINE in the corpus (P2728R11/12) and choke triage. Images are out of scope
# for the extraction mission (client decision, 2026-07-07), so the payload is
# replaced by a sanctioned marker before the LLM sees the markdown. The stored
# paper.md is never modified.

# A bare line (no image wrapper) at least this long whose chars are
# >= BASE64_LINE_ALPHABET_FLOOR base64-alphabet is treated as binary debris and
# stripped. Whitespace counts against the ratio: tomd emits whole paragraphs
# as single unwrapped lines, and their ~15-20% spaces (plus punctuation) are
# what keeps prose safely below the floor, while a base64 run contains neither.
BASE64_LINE_MIN_CHARS = 1024
BASE64_LINE_ALPHABET_FLOOR = 0.90

# -- Fusion constants (deterministic + LLM merge) -----------------------------
# The fusion lane joins the whisker sidecar verdict with the tapetum advisory
# verdict into a combined advisory verdict. All constants here govern that
# merge; none affect whisker core or the tapetum LLM cascade.

# Rule names persisted in `combined_rule` for traceability. Every merged
# verdict carries exactly one rule name explaining how it was derived.
FUSION_RULE_AGREE = "agree"
FUSION_RULE_WHISKER_ONLY = "whisker_only"
FUSION_RULE_WHISKER_FAIL_LOCKED = "whisker_fail_locked"
FUSION_RULE_LLM_RESCUE_HEADING = "llm_rescue_heading"
FUSION_RULE_LLM_CLEAR_SOFT_REVIEW = "llm_clear_soft_review"
FUSION_RULE_LLM_ESCALATE_MAJOR = "llm_escalate_major"
FUSION_RULE_SOURCE_AWARE_REVIEW_CAP = "source_aware_review_cap"
FUSION_RULE_IDEAL_REVIEW_CAP = "ideal_review_cap"

# Caps a deterministic pass at review whenever the primary tapetum verdict
# is anything other than pass and no more specific cap above already fired.
# Closes audit finding M2 (E19/E32): a det=pass could previously read
# combined_verdict=pass next to tapetum_verdict=review or tapetum_verdict=fail
# with no cap at all, because only the fail+major-axis case (llm_escalate_major)
# and the schema-v6/ideal caps had an upward channel to review.
FUSION_RULE_LLM_REVIEW_CAP = "llm_review_cap"

# Guardrail: llm_clear_soft_review is suppressed when the oracle text
# agreement (ref_nid) is pathologically low, indicating a near-empty or
# degenerate conversion that the LLM might incorrectly call "pass".
FUSION_REF_NID_FLOOR = 0.10

# Guardrail: llm_clear_soft_review is also blocked when the whisker sidecar
# recorded missing source regions. The LLM only sees the converted markdown,
# never the source, so it structurally cannot verify the absence of content
# whisker flagged as missing; upgrading review -> pass on its say-so is unsafe.
FUSION_RULE_CLEAR_BLOCKED_MISSING_REGION = "clear_blocked_missing_region"
FUSION_RULE_CLEAR_BLOCKED_IDEAL_FLAG = "clear_blocked_ideal_flag"

# Deterministic golden-ideal flags emitted by score.py share this prefix.
# Fusion treats them as ground-truth review signals that an ordinary LLM pass
# cannot clear.
IDEAL_SOFT_FLAG_PREFIX = "ideal "

# Bumped 3 -> 4 for compact ideal-verifier verdict/count fields.
FUSION_SCHEMA_VERSION = 4

# -- PDF-judge deterministic floors (pass -> review demotion) ------------------
# When the PDF-text-layer judge says "pass" but the deterministic metrics
# contradict, the verdict is demoted to "review". These are conservative
# floors: only blatant content loss triggers the demotion.
PDF_JUDGE_RECALL_FLOOR = 0.85
PDF_JUDGE_NID_FLOOR = 0.80

# -- Per-page recall screen (deterministic, lane-local, no LLM) ----------------
# Hybrid design (research/research/per-page-judging/SYNTHESIS.md, plan
# per-page_judge_hybrid_c06253b3): a per-page content_recall(tomd_md, page)
# screen isolates localized absence that PDF_JUDGE_RECALL_FLOOR (a
# whole-document average) mathematically cannot see. Calibrated via an
# offline flip-check: p0957r8's known defect (page 13, recall 0.8810) against
# a negative control of all 8 golden PDFs' non-trivial pages (107 pages,
# correct snapshots, worst healthy page 0.9129). The gap between 0.8810 and
# 0.9129 is wide enough for a floor at 0.90 to flag the defect and clear
# every one of the 107 control pages (0 false flags).
PAGE_RECALL_FLOOR = 0.90

# Pages whose content_tokens count falls below this are skipped by the
# screen: too little text for recall to be meaningful (a half-title or
# near-blank page would otherwise flag spuriously). Same calibration run as
# PAGE_RECALL_FLOOR above.
PAGE_MIN_TOKENS = 50

# Cap on scoped LLM escalation calls per paper. The screen typically flags
# 0-2 pages (SYNTHESIS.md); a flagged-page count above this is itself
# anomalous (a systemic extraction/conversion issue, not a handful of
# isolated gaps), so escalation is skipped entirely and the verdict is
# capped at review on screen evidence alone, rather than spending 1+N calls
# chasing what the screen already shows is broken document-wide.
MAX_PAGE_ESCALATIONS = 5

# Wall-clock timeout for one page-scoped escalation call. Sized for a single
# small call (one page's raw text + the full markdown, <=60-word reasoning
# output), independent of _PAPER_TIMEOUT_SECONDS in cli.py, which budgets
# the whole paper (monolith call plus up to MAX_PAGE_ESCALATIONS of these).
PAGE_ESCALATION_TIMEOUT_SECONDS = 120.0

# Length-relative fuzzy grounding for page-scoped escalation quotes (olmocr-
# bench pattern: threshold = 1.0 - max_diffs/len(quote), tests.py:168-173).
# A fixed character-diff budget divided by the quote's own length keeps short
# quotes strict and gives long quotes proportionally more slack, instead of
# EVIDENCE_FUZZY_FLOOR's one flat ratio over a whole document.
PAGE_QUOTE_MAX_DIFFS = 2

# -- Source-aware unit routing and structured checks (v6) --------------------
# These thresholds govern the risk router that identifies pages/sections for
# unit-based LLM checks. The router is lane-local: it reads only source units
# and candidate markdown, never the deterministic whisker sidecar.

SECTION_RECALL_FLOOR = 0.90
"""Recall floor for section-level content checks (HTML lane). Sections below
this are flagged for unit-based LLM re-check."""

SECTION_MIN_TOKENS = 50
"""Minimum content tokens for a section to be eligible for unit checks.
Trivial sections (title pages, near-blank) skip the router."""

TOKEN_DELTA_THRESHOLD = 5
"""Flag when a tracked token (e.g. constexpr, template) count in the source
differs from the candidate by at least this many occurrences."""

PDF_MISSING_CODE_TOKEN_THRESHOLD = 8
"""PDF pages with at least this many C++ keyword hits
(``PageUnit.code_token_count``) are checked for flattened listings. Below
this, prose that merely mentions a few keywords is not routed."""

PDF_MISSING_CODE_FENCE_COVER_RATIO = 0.5
"""Fraction of a page's distinctive keyword-line hits that must appear
inside candidate fenced bodies as the same page-local snippet. Global
keyword-type presence (``int`` in some other fence) does not count.
Coverage below this ratio means the listing was flattened into prose
(P3596R0 pages 66-72)."""

PDF_MISSING_CODE_SNIPPET_MIN_TOKENS = 3
"""Minimum word tokens on a source line before it can witness coverage.
A lone ``int`` / ``void`` label is too short to match against other
pages' fences."""

MAX_UNIT_CHECKS = 5
"""Maximum scoped unit-check LLM calls per paper (fleet default). If more
units are risky, the paper verdict is capped at review without individual
calls (same pattern as MAX_PAGE_ESCALATIONS for the monolith page screen).
Golden-PR runs use exhaustive mode (all routed units checked)."""

# Dynamic unit-check quota: per-paper function replaces fixed MAX_UNIT_CHECKS
# for fleet mode. Base 3 with bumps for table presence, high severity, and
# high signal count; ceiling 7.
FLEET_UNIT_CHECK_BASE = 3
FLEET_UNIT_CHECK_CEILING = 7

# Signal count above which an extra slot is granted
FLEET_UNIT_CHECK_SIGNAL_COUNT_THRESHOLD = 8

SIGNAL_CLASS_QUOTA = 1
"""Minimum guaranteed unit-check slots per distinct signal_type. Ensures
every signal class (low_recall, heading_drift, token_delta, missing_code,
missing_captions, table_presence, table_corruption) gets at least one
check before noise from one class crowds others out."""

UNIT_CHECK_TIMEOUT_SECONDS = 120.0
"""Wall-clock timeout for one unit-scoped LLM check call."""

MONOLITH_TIMEOUT_SECONDS = 240.0
"""Wall-clock timeout for one monolith (full-document) LLM call.
Sized generously for the largest single-call payloads (~500k chars);
prevents a hung request from holding a fleet slot for the full
_PAPER_TIMEOUT_SECONDS (900s) budget."""
