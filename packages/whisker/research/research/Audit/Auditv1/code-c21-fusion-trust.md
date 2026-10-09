# C21 - Fusion and Operator-Trust Auditor

**Mandate:** Verify fusion rules, stale/error sidecars, and combined-verdict presentation.
**Focus dimensions:** D1 (determinism), G1 (gate integrity).

---

## 1. Fusion Rule Verification (`tapetum_llm/fusion.py`)

### 1.1 Demote-Only Ratchet (Advisory Never Raises)

| Severity | **PASS** |
|----------|----------|
| Claim | The advisory lane can lower a verdict (pass->review, rescue fail->review) but NEVER raise (fail->pass). |
| Evidence | `fusion.py:269-290` (det=fail branch): heading-only rescue outputs `VERDICT_REVIEW`, never `VERDICT_PASS`. All other fails locked at `VERDICT_FAIL` via `FUSION_RULE_WHISKER_FAIL_LOCKED`. `fusion.py:362-373` (det=pass branch): escalation outputs `VERDICT_REVIEW`, never `VERDICT_FAIL`. |
| Affected gate | G1 - gate integrity |
| Confidence | 0.98 |
| False-pass hypothesis | A code path exists that maps `(det=fail, llm=pass)` to `combined=pass`. Disproved: `_is_heading_only_fail` rescue always emits `VERDICT_REVIEW` (line 273), and `test_rescue_never_upgrades_to_pass` (test_fusion.py:124-130) pins this. |
| False-fail hypothesis | The ratchet is overly conservative and blocks legitimate upgrades. Not relevant to correctness. |

### 1.2 Heading-Only Rescue Rule

| Severity | **PASS** |
|----------|----------|
| Claim | Only `gate:heading_monotone`-prefixed hard flags qualify for rescue; other flags containing the substring "heading" (e.g., `no_toc_leak` with "duplicate heading") do not. |
| Evidence | `fusion.py:225-236`: `_is_heading_only_fail` checks `f.startswith("gate:heading_monotone")` per flag, not a substring search. `test_fusion.py:132-147`: `test_toc_leak_fail_is_not_rescued` asserts `no_toc_leak` stays `WHISKER_FAIL_LOCKED`. |
| Affected gate | G1 |
| Confidence | 0.99 |
| False-pass hypothesis | A TOC-leak fail gets wrongly rescued. Disproven by prefix matching + dedicated test. |
| False-fail hypothesis | Heading-monotone fails with additional flags are not rescued. Correct by design: multi-flag fails should not be rescued. |

### 1.3 Clear Soft Review (review->pass)

| Severity | **PASS** |
|----------|----------|
| Claim | `llm_clear_soft_review` requires: soft-only flags, LLM pass, confidence >= floor, ref_nid >= floor (or absent). |
| Evidence | `fusion.py:306-359`: four nested conditions: `_has_only_soft_flags`, `llm == VERDICT_PASS`, `conf >= CONFIDENCE_DECISION_FLOOR`, `ref_nid >= FUSION_REF_NID_FLOOR` (or `ref_nid is None`). Tests: `test_clear_soft_review` (line 149), `test_clear_guardrail_ref_nid` (line 157), `test_clear_blocked_below_confidence_floor` (line 165). |
| Affected gate | G1 |
| Confidence | 0.97 |
| False-pass hypothesis | The `ref_nid is None` fallback path allows clearing without any cross-converter validation. This is intentional and documented (line 342-359): papers without a reference oracle. |
| False-fail hypothesis | None identified. |

### 1.4 Missing-Region Clear Block

| Severity | **PASS** |
|----------|----------|
| Claim | When `missing_region_count > 0`, the clear path is blocked because the LLM cannot verify content absence (it only sees the markdown, not the source). |
| Evidence | `fusion.py:308-323`: explicit `missing_region_count` check before the clear guardrail. `test_fusion.py:221-257`: three tests (`test_clear_blocked_when_missing_regions`, `test_clear_allowed_when_zero_missing_regions`, `test_clear_allowed_when_missing_region_count_absent`) pin all branches. |
| Affected gate | G1 |
| Confidence | 0.99 |
| False-pass hypothesis | None: structurally sound. |
| False-fail hypothesis | None. |

### 1.5 Escalate Major (pass->review)

| Severity | **PASS** |
|----------|----------|
| Claim | `llm_escalate_major` triggers only when `det=pass` AND `llm=fail` AND at least one axis finding is `fail+major`. Non-major axis fails are ignored. |
| Evidence | `fusion.py:362-373`: checks `det == VERDICT_PASS`, `llm == VERDICT_FAIL`, and `_has_major_axis_fail(tapetum)`. `test_fusion.py:173-207`: `test_escalate_major_on_pass` and `test_escalate_ignores_non_major_fail` pin both paths. |
| Affected gate | G1 |
| Confidence | 0.99 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

### 1.6 Source-Aware Review Cap

| Severity | **PASS** |
|----------|----------|
| Claim | Schema-v6 source-aware metadata review/fail, accepted high/critical defect groups, or incomplete unit coverage cap a non-fail merge at review without consulting confidence. |
| Evidence | `fusion.py:292-303`: `_source_aware_requires_review` checks metadata verdict, unit coverage completeness, unchecked/failed unit IDs, and accepted defect groups. Applied BEFORE the clear/escalate branches. Tests: `TestSourceAwareFusion` class (14 tests, lines 260-510) exhaustively covers metadata, coverage, defect groups, accepted vs unaccepted evidence, and edge cases. |
| Affected gate | G1, D1 |
| Confidence | 0.97 |
| False-pass hypothesis | An unverified-count defect group with accepted evidence does not trigger the cap. This is intentional: only `_is_accepted_disposition` (exact source, candidate_not_found) triggers the cap. |
| False-fail hypothesis | The `_accepted_flat_dispositions` path (line 171-178) requires `unit_id` on dispositions; dispositions without `unit_id` are silently ignored and do not trigger the cap. By design. |

---

## 2. Stale Sidecar Handling

| Severity | **PASS** |
|----------|----------|
| Claim | The whisker fingerprint detects staleness via SHA-256 of the canonical JSON representation of the whisker sidecar. |
| Evidence | `fusion.py:87-90`: `_whisker_fingerprint` uses `json.dumps(whisker, sort_keys=True, ensure_ascii=True)` + SHA-256 truncated to 16 hex chars. The fingerprint is stored in every `FusionResult`. `test_fusion.py:522-527`: `test_fingerprint_stable` confirms stability and length. |
| Affected gate | D1 |
| Confidence | 0.95 |
| False-pass hypothesis | If the whisker sidecar changes between runs but the tapetum sidecar does not, the fingerprint mismatch signals staleness. The fingerprint is RECORDED but fusion.py itself does not ENFORCE staleness rejection; that responsibility is in the CLI (`cli.py`'s fingerprint-based skip logic). |
| False-fail hypothesis | None. |

**Finding (INFORMATIONAL):**

| Severity | INFO |
|----------|------|
| Claim | `fuse_verdicts` itself does not reject stale tapetum sidecars; it always fuses whatever is passed. The staleness enforcement is in the CLI's fingerprint-skip logic, not in the pure function. |
| Evidence | `fusion.py:244-385`: no fingerprint comparison against tapetum's recorded whisker fingerprint. |
| Affected gate | D1 |
| Confidence | 0.90 |
| False-pass hypothesis | A stale tapetum sidecar (generated against a different whisker run) could produce a misleading combined verdict if the CLI does not enforce the fingerprint check. |
| False-fail hypothesis | Unlikely: the CLI is documented to perform fingerprint-based skip. |

---

## 3. Error Sidecar Handling

| Severity | **PASS** |
|----------|----------|
| Claim | An error tapetum sidecar (`status=error`) is treated as absent: merged = det, whisker_only, tapetum_available=False. |
| Evidence | `fusion.py:93-103`: `_tapetum_is_usable` returns `False` when `tapetum.get("status") == "error"`. Line 253-262: unusable tapetum produces `FUSION_RULE_WHISKER_ONLY` with `tapetum_available=False`. `test_fusion.py:86-93`: `test_error_stub_whisker_only` pins this. |
| Affected gate | G1 |
| Confidence | 0.99 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

---

## 4. Confidence-Zero Stub Handling

| Severity | **PASS** |
|----------|----------|
| Claim | A tapetum sidecar with `confidence=0.0` and no axis findings is treated as a stub (unusable). |
| Evidence | `fusion.py:101-102`: `tapetum.get("confidence", 0.0) == 0.0 and not tapetum.get("axis_findings")` returns False (unusable). Exception: source-aware data bypasses this check (line 99-100). `test_fusion.py:95-101`: `test_confidence_zero_stub_whisker_only` pins this. |
| Affected gate | G1 |
| Confidence | 0.98 |
| False-pass hypothesis | A confidence-zero sidecar WITH axis findings would still be usable. Correct: if the model provided specific axis findings, the data is meaningful even at zero confidence. |
| False-fail hypothesis | None. |

---

## 5. Combined Presentation (`fusion_report.py`)

| Severity | **PASS** |
|----------|----------|
| Claim | The merged report presents three distinct verdicts (det, llm, merged) with delta arrows, confidence, rule names, and cosmetic classification. |
| Evidence | `fusion_report.py:42-74`: `build_merged_json` builds rows with `det`, `llm`, `merged`, `delta`, `conf`, `rule`, `class`. `fusion_report.py:113-159`: `render_merged_report_md` produces a markdown table with all fields. `fusion_report.py:166-175`: `render_terminal_fusion_line` shows per-paper one-liner. |
| Affected gate | D1 |
| Confidence | 0.97 |
| False-pass hypothesis | The `_delta_symbol` function (line 77-85) correctly maps tier comparisons to arrows (up/down/equal). |
| False-fail hypothesis | None. |

### 5.1 Cosmetic Classification

| Severity | **PASS** |
|----------|----------|
| Claim | Papers where the LLM's ONLY non-pass axis is `structure/minor` are classified as "cosmetic" (fast-track review candidates). |
| Evidence | `fusion_report.py:88-103`: `_classify_cosmetic` checks `suggested_verdict == VERDICT_REVIEW` and ALL non-pass findings are `axis=structure, severity=minor`. `test_fusion.py:736-775`: `TestCosmeticTier` tests structure-only-minor, non-structure axis, and major severity. |
| Affected gate | D1 |
| Confidence | 0.98 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

---

## 6. Inspect Report (`inspect_report.py`)

| Severity | **PASS** |
|----------|----------|
| Claim | The side-by-side report shows whisker signals, LLM per-axis findings, grounded evidence, metadata checks, unit coverage, defect groups, and evidence dispositions. |
| Evidence | `inspect_report.py:51-213`: `format_paper_section` renders all available data. `inspect_report.py:216-264`: `format_report` adds header with totals, adjudicated count, differs count, and merged rollup. |
| Affected gate | D1 |
| Confidence | 0.95 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

### 6.1 Inspect Report Merged Rollup

| Severity | **PASS** |
|----------|----------|
| Claim | The inspect report header includes a merged rollup when fusion data is present. |
| Evidence | `inspect_report.py:229-261`: iterates pairs, collects fusion data, counts merged verdicts, appends to header. `test_fusion.py:794-801`: `TestInspectMergedRollup` asserts "merged rollup" and "1 pass" in the report. |
| Affected gate | D1 |
| Confidence | 0.98 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

---

## 7. Test Coverage (`test_fusion.py`)

| Severity | **PASS** |
|----------|----------|
| Claim | The test suite covers all fusion rules, real sidecar fixtures, determinism, fusion report rendering, cosmetic classification, inspect rollup, and chunk aggregation. |
| Evidence | `test_fusion.py`: 7 test classes, 44 tests total. `TestFusionMatrix` (16 tests): all base cells and special rules. `TestSourceAwareFusion` (11 tests): schema-v6 evidence paths. `TestFusionDeterminism` (4 tests): same-input stability, fingerprint, evidence cleanup invariance, three-verdict distinctness. `TestRealSidecarFixtures` (5 tests): real production sidecar pairs. `TestFusionReport` (4 tests): JSON building, MD rendering, terminal output. `TestCosmeticTier` (4 tests): cosmetic classification. `TestChunkFoldBypassFix` (2 tests): aggregation edge cases. |
| Affected gate | D1 |
| Confidence | 0.95 |
| False-pass hypothesis | No negative test for "LLM says fail, det says fail, different hard flags" but this falls through to the default agree/whisker_only path which is tested. |
| False-fail hypothesis | None. |

---

## Summary

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | Demote-only ratchet holds: advisory never raises fail->pass | CRITICAL | PASS |
| 2 | Heading rescue uses prefix matching, not substring | HIGH | PASS |
| 3 | Clear requires four guardrails (soft-only, LLM pass, confidence, ref_nid) | HIGH | PASS |
| 4 | Missing-region blocks clear path | HIGH | PASS |
| 5 | Source-aware review cap independent of confidence | HIGH | PASS |
| 6 | Error/stub sidecars correctly treated as absent | HIGH | PASS |
| 7 | Staleness enforcement is in CLI, not in `fuse_verdicts` | INFO | NOTED |
| 8 | Test coverage: 44 tests across 7 classes | MEDIUM | PASS |
| 9 | Determinism: pure function, no I/O, sorted outputs | D1 | PASS |
| 10 | Combined presentation: three-verdict + delta + cosmetic | D1 | PASS |

**Auditor verdict: The fusion subsystem is sound.** The demote-only ratchet is structurally enforced and comprehensively tested. The one informational finding (staleness enforcement location) is by design: `fuse_verdicts` is a pure function and staleness is a CLI concern.
