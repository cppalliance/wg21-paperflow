# C03 Advisory Non-Leakage Audit

**Auditor:** C03 (Advisory Non-Leakage Auditor)
**Date:** 2026-07-19
**Scope:** Prove that LLM/advisory signals cannot change `whisker --gate` verdicts.
**Package:** `packages/whisker/`

---

## Executive Summary

The isolation between the deterministic gate and the LLM advisory lane is
**structurally sound**. No code path exists by which an LLM output, adversarial
or otherwise, can alter the exit code of `whisker --gate`. The separation is
enforced at four levels: import boundary, verdict computation, fusion semantics,
and exit-code derivation. CI tests cover the critical invariants.

**Overall verdict: PASS (no leakage found).**

---

## Finding 1: Import Isolation of Core Scoring Path

| Field | Value |
|---|---|
| **Severity** | Info (structural proof) |
| **Claim** | The scoring path (`score.py`, `gates.py`, `constants.py`, `metrics.py`, `match.py`, `bench.py`, `guard.py`, `golden.py`, `golden_ideals.py`, `facts.py`, `tables.py`, `anchors.py`, `reference.py`, `report.py`, `corpus_tools.py`, `calibrate.py`) contains zero imports from `whisker.tapetum_llm`. |
| **Evidence** | `rg "from whisker\.tapetum_llm\|import whisker\.tapetum_llm"` across `packages/whisker/src/whisker/*.py` (excluding `tapetum_llm/` subdirectory) returns hits ONLY in `menu.py` (lines 182, 195), which are lazy imports inside interactive TTY dispatch functions (`_run_score_plus_llm`, `_run_llm_only`), guarded by `_has_tapetum_llm()` (line 35-41). `menu.py` is a CLI module, not on the scoring path. The core modules `score.py`, `gates.py`, `constants.py`, `metrics.py`, `match.py`, `bench.py`, `guard.py`, `golden.py`, `golden_ideals.py`, `facts.py`, `tables.py`, `anchors.py`, `reference.py`, `report.py`, `corpus_tools.py`, `calibrate.py` have ZERO tapetum_llm imports. |
| **Affected gate/dimension** | G1 (verdict integrity), D1 (determinism) |
| **Confidence** | 1.0 (exhaustive grep, zero hits in scoring modules) |
| **False-pass hypothesis** | None. The absence is structural: no import means no call path. |
| **False-fail hypothesis** | N/A |

---

## Finding 2: Verdict Computation Is LLM-Free

| Field | Value |
|---|---|
| **Severity** | Info (structural proof) |
| **Claim** | `_decide()` in `score.py` computes the verdict from exactly: `unigram_coverage`, `unigram_drift`, `missing_count`, `extra_count`, `qa_score`, `uncertain_count`, `gates` (structural), `ref` (cross-converter NID, advisory), and `ideal` (golden-ideal panel, advisory). None of these inputs originate from an LLM. |
| **Evidence** | `score.py:136-231`: `_decide()` signature accepts only deterministic signals. Hard fails come from two sources only: (a) `gates` list (structural, from `gates.py:run_gates`, pure regex/AST on markdown), (b) `unigram_coverage < UNIGRAM_COVERAGE_FAIL_EDGE` (0.85). Soft flags come from coverage bands, drift, regions, qa, uncertain markers, `ref_nid` (cross-converter text NID, computed by `markitdown` oracle, no LLM), and `ideal` panel (golden-ideal NID/TEDS/MHS, computed by deterministic metrics). The `ref` and `ideal` signals are explicitly advisory: they only ever append to the `soft` list, never to `hard`. Lines 200-215 confirm: `ref_nid < REF_NID_ADVISORY_EDGE` appends to `soft`; ideal axes below floor append to `soft` with "(advisory)" suffix. The verdict at line 217-231: `hard` -> FAIL, benign-region fold -> PASS, `soft` -> REVIEW, else PASS. No LLM signal touches `hard`. |
| **Affected gate/dimension** | G1, D1 |
| **Confidence** | 1.0 (complete function trace) |
| **False-pass hypothesis** | None. `hard` list is populated only by gate failures and coverage floor. |
| **False-fail hypothesis** | None. Advisory signals add to `soft` only. |

---

## Finding 3: Fusion Is Demote-Only (No fail->pass, No review->pass Without Guardrails)

| Field | Value |
|---|---|
| **Severity** | Info (structural proof) |
| **Claim** | `fuse_verdicts()` in `fusion.py` implements an asymmetric matrix where the combined verdict can never be strictly better than the deterministic verdict except under narrow, guarded conditions that still cannot produce a `pass` from a `fail`. |
| **Evidence** | `fusion.py:244-385`, complete trace of all branches: |
|  | **tapetum absent/error/stub** (line 253-260): combined = det. No change. |
|  | **det=fail** (line 269-290): `_is_heading_only_fail` + LLM pass/review -> combined = REVIEW (rescue, never pass, line 273). All other fails: combined = FAIL (locked, line 283). **fail->pass is impossible.** |
|  | **source-aware review cap** (line 292-303): det=pass or review with verified source-aware evidence -> combined = REVIEW. **Demote only.** |
|  | **det=review, missing regions** (line 310-323): LLM pass blocked -> combined = REVIEW. **No upgrade when content absence detected.** |
|  | **det=review, soft-only, LLM pass** (line 326-359): combined = PASS only if: (a) only soft flags, (b) LLM says pass, (c) confidence >= floor, (d) ref_nid >= floor OR ref_nid is None. This is the ONE upgrade path: review->pass. |
|  | **det=pass, LLM fail+major** (line 362-373): combined = REVIEW. **Demote only.** |
|  | **Default** (line 376-385): combined = det. |
|  | The review->pass path (FUSION_RULE_LLM_CLEAR_SOFT_REVIEW) is the sole upgrade and requires multiple guardrails. **No path exists from fail->pass.** |
| **Affected gate/dimension** | G1, D1 |
| **Confidence** | 1.0 (exhaustive branch analysis) |
| **False-pass hypothesis** | The review->pass clear path exists but is guarded by confidence floor + ref_nid floor + soft-flags-only + no missing regions. This is by design: the fusion is advisory and its `combined_verdict` is never read by `whisker --gate` (see Finding 5). |
| **False-fail hypothesis** | The pass->review escalate path exists (LLM major fail). Also advisory-only. |

---

## Finding 4: CI Tests Enforce Verdict Invariance and Demote-Only Ratchet

| Field | Value |
|---|---|
| **Severity** | Info (test coverage proof) |
| **Claim** | Test suites enforce: (a) the scoring path produces correct verdicts without LLM, (b) fusion is demote-only with explicit ratchet tests, (c) structural invariants hold. |
| **Evidence** | |
|  | **`test_score.py`**: 25 tests covering the full verdict trichotomy. Key invariance tests: `test_reference_low_text_agreement_is_advisory_review_never_fail` (line 213-224, advisory signal NEVER hard-fails), `test_coverage_still_hard_fails_with_reference_on` (line 241-251, coverage gate overrides agreeing reference), `test_reference_does_not_mask_structural_gate` (line 253-262), `test_reflow_high_unigram_low_shingle_not_fail` (line 89-96, reading order does not gate). |
|  | **`test_fusion.py`**: 30+ tests covering the full 3x3 fusion matrix. Key ratchet tests: `test_fail_locked_non_heading` (line 103-109, det=fail + LLM pass -> still FAIL), `test_rescue_never_upgrades_to_pass` (line 124-130, heading rescue caps at REVIEW), `test_toc_leak_fail_is_not_rescued` (line 132-147, TOC-leak fail stays locked despite LLM review), `test_clear_guardrail_ref_nid` (line 157-163, low ref_nid blocks clear), `test_clear_blocked_below_confidence_floor` (line 165-171), `test_escalate_ignores_non_major_fail` (line 191-207, non-major LLM fail does not demote pass), `test_clear_blocked_when_missing_regions` (line 221-232, missing regions block upgrade). `TestFusionDeterminism` class (line 513-587) proves same input produces same output and that det/LLM/merged are three distinct outputs. |
|  | **`test_invariants.py`**: Metric identity, symmetry, and bounds tests for `text_nid`, `teds`, `mhs`, `normalized_edit_distance`. These prove the deterministic metrics are pure functions. |
|  | **`test_claude_invariants.py`**: AST-level enforcement of no-print in library modules, no lazy imports, `__init__.py` purity. Scans all whisker source files. |
| **Affected gate/dimension** | G1, D1 |
| **Confidence** | 1.0 (tests read in full) |
| **False-pass hypothesis** | None. Tests assert both positive (correct verdict) and negative (advisory cannot flip) invariants. |
| **False-fail hypothesis** | None. |

---

## Finding 5: Adversarial All-Clear LLM Output Cannot Flip a Deterministic Gate

| Field | Value |
|---|---|
| **Severity** | Info (structural proof) |
| **Claim** | An adversarial LLM producing `{"suggested_verdict": "pass", "confidence": 1.0}` for every paper cannot change ANY `whisker --gate` exit code. |
| **Evidence** | The `whisker --gate` exit code is computed at `__main__.py:283`: `return _verdict_exit_code([r.verdict for r in results], args.gate)`. The `results` list contains `WhiskerResult` objects produced by `score_paper()` (line 220). `score_paper` calls `score_markdown` which calls `_decide`, which is the LLM-free function analyzed in Finding 2. The `WhiskerResult.verdict` field is set at line 290-300 from `_decide`'s return. `_verdict_exit_code` (line 130-136) reads ONLY `r.verdict` from these results. The `tapetum_llm` lane runs in a SEPARATE CLI (`whisker-tapetum-llm`, entry point in `tapetum_llm/cli.py`), NOT in the `whisker` CLI's `_score_main`. The fusion (`fuse_verdicts`) is called only from `tapetum_llm/cli.py`, never from `__main__.py._score_main`. The `FusionResult.advisory` field is hardcoded `True` (line 70). Even `menu.py`'s option 2 (deterministic + LLM) runs `_score_main` first and returns its exit code; the tapetum lane runs afterward and its result is discarded from the exit code path (line 174-186). |
|  | **Attack surface**: Even if an adversary controls the full tapetum sidecar JSON, the `whisker` CLI never reads it. The tapetum CLI writes to `whisker/llm/` (a separate directory). The deterministic CLI reads and writes `whisker/det/`. No code path in `_score_main` touches `whisker/llm/`. |
| **Affected gate/dimension** | G1 |
| **Confidence** | 1.0 (full call-chain trace from CLI entry to exit code) |
| **False-pass hypothesis** | None. The two CLIs are separate executables with separate exit codes. |
| **False-fail hypothesis** | None. |

---

## Finding 6: Exit Codes Depend Only on Deterministic Verdict

| Field | Value |
|---|---|
| **Severity** | Info (structural proof) |
| **Claim** | `whisker --gate` exit codes are `0` (ok), `1` (error), `3` (review), `5` (fail), derived solely from deterministic `WhiskerResult.verdict` values. |
| **Evidence** | `constants.py:154-157`: `EXIT_OK=0`, `EXIT_ERROR=1`, `EXIT_REVIEW=3`, `EXIT_FAIL=5`. `__main__.py:88-91`: `_GATE_ACCEPTS = {"pass": {"pass"}, "review": {"pass", "review"}, "fail": {"pass", "review", "fail"}}`. `__main__.py:130-136`: `_verdict_exit_code` checks whether any verdict in the list is outside the accepted set. The list is `[r.verdict for r in results]` (line 283), where each `r` is a `WhiskerResult` from `score_paper`. No tapetum/fusion/LLM verdict is ever in this list. |
| **Affected gate/dimension** | G1, D1 |
| **Confidence** | 1.0 |
| **False-pass hypothesis** | None. |
| **False-fail hypothesis** | None. |

---

## Finding 7: menu.py tapetum_llm References Are CLI-Only, Not Scoring-Path

| Field | Value |
|---|---|
| **Severity** | Info (clarification) |
| **Claim** | `menu.py` is the only core-level module referencing `tapetum_llm`, but its imports are lazy (inside function bodies), guarded by `_has_tapetum_llm()`, and used only for interactive menu dispatch (options 2 and 3). They are unreachable from the scoring path. |
| **Evidence** | `menu.py:182`: `from whisker.tapetum_llm.cli import main as tapetum_main` inside `_run_score_plus_llm()`. `menu.py:195`: same inside `_run_llm_only()`. Both functions check `_has_tapetum_llm()` first (lines 170, 191) and bail if the extra is not installed. `menu.py` is classified as a CLI module (`_CLI_MODULES` in `test_claude_invariants.py:40`) and is excluded from the library purity checks. The menu is only launched when `whisker` is invoked with no arguments on a TTY; `whisker --gate` always goes through `_score_main` which never touches `menu.py`. |
| **Affected gate/dimension** | G1 |
| **Confidence** | 1.0 |
| **False-pass hypothesis** | None. |
| **False-fail hypothesis** | None. |

---

## Summary Table

| # | Claim | Verdict | Confidence |
|---|---|---|---|
| F1 | Zero tapetum_llm imports in scoring modules | VERIFIED | 1.0 |
| F2 | `_decide()` uses only deterministic signals | VERIFIED | 1.0 |
| F3 | Fusion is demote-only (never fail->pass) | VERIFIED | 1.0 |
| F4 | CI tests enforce invariance + ratchet | VERIFIED | 1.0 |
| F5 | Adversarial LLM all-clear cannot flip gate | VERIFIED | 1.0 |
| F6 | Exit codes depend only on deterministic verdict | VERIFIED | 1.0 |
| F7 | menu.py references are CLI-only, not scoring | VERIFIED | 1.0 |

**No leakage path found. The advisory lane is structurally isolated from the
deterministic gate.**
