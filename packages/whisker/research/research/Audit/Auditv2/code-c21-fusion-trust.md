# C21 Fusion and Operator Trust

**Role**: Audit fusion rules, promotion/demotion behavior, and operator trust.
**Audited state**: whisker 0.5.0, HEAD 51cb704 + local mods.
**Gates**: D1 (All LLM calls via pipeline), D3 (Batch isolation).

## 1. Scope

Verify the complete fusion rule matrix: promotion rules, rescue behavior,
clear behavior, ideal demotion, source-aware caps, and stale/error sidecar
handling.

## 2. Commands and Exits

```
uv run --package whisker pytest packages/whisker/tests/test_fusion.py -v
```

Exit: Offline suite passes (E1). Fusion is pure Python (no LLM required),
so the test matrix is fully exercisable.

## 3. Current Evidence

### 3.1 Fusion architecture

`fusion.py` is a pure function module: two sidecar dicts in, one
`FusionResult` out. No I/O, no LLM calls. The merged verdict is advisory
and never replaces the deterministic whisker verdict.

`FusionResult` (line 67) is a frozen dataclass with `advisory: bool = True`
(immutable, always True).

### 3.2 Sidecar validation

Before fusion, both sidecars are validated:

- **Whisker sidecar** (`_validate_whisker_sidecar`, line 116): Rejects
  non-dict, missing/empty pid, missing/unrecognized verdict.
- **Tapetum sidecar** (`_validate_tapetum_sidecar`, line 129): Rejects
  non-dict, missing/empty pid. Sanitizes fingerprint (removes non-dict).
  For error status, returns early. For non-error, requires
  `suggested_verdict` in recognized set and valid finite confidence.
- **`_finite_float`** (line 105): Rejects bool, non-numeric, Inf, NaN.

Invalid sidecars result in `whisker_only` fusion (deterministic verdict
preserved).

### 3.3 Tapetum usability check

`_tapetum_is_usable()` (line 155) returns False when:
- tapetum is None
- `status == "error"`
- `confidence == 0.0` AND no `axis_findings` (partial/incomplete stub)

Exception: source-aware data (schema v6+) always passes usability check
even at low confidence, because source-aware checks have their own
fail-closed logic.

### 3.4 Complete fusion rule matrix

`fuse_verdicts()` (line 329+) applies rules in priority order:

| Rule | Condition | Result | Direction |
|------|-----------|--------|-----------|
| **whisker_only** | tapetum unusable | det verdict | neutral |
| **agree** | det == llm | det verdict | neutral |
| **whisker_fail_locked** | det=fail, NOT heading-only | fail | locked |
| **llm_rescue_heading** | det=fail, heading-only, llm=pass/review | review | rescue (never pass) |
| **source_aware_review_cap** | source-aware data requires review | review | demotion cap |
| **ideal_review_cap** | ideal verifier says review | review | demotion cap |
| **clear_blocked_missing_region** | det=review, missing_region_count > 0 | review | block clear |
| **clear_blocked_ideal_flag** | det=review, ideal soft flags present | review | block clear |
| **llm_clear_soft_review** | det=review, soft-only, llm=pass, conf >= 0.50, ref_nid >= 0.10 | pass | promotion (review->pass) |
| **llm_escalate_major** | det=pass, llm=fail with major axis | review | escalation |
| **fallback** | none of the above | det verdict | neutral |

### 3.5 Asymmetric transitions (the critical property)

The fusion matrix is asymmetric by design:

- **fail -> pass**: IMPOSSIBLE. No rule produces this transition.
  `whisker_fail_locked` holds for non-heading fails. `llm_rescue_heading`
  only produces review, never pass.

- **fail -> review**: Only via `llm_rescue_heading` for heading-only fails.

- **review -> pass**: Only via `llm_clear_soft_review`, requiring ALL of:
  soft-only flags, LLM pass, confidence >= 0.50, ref_nid >= 0.10 (or None),
  no missing regions, no ideal flags. Five guardrails.

- **pass -> fail**: IMPOSSIBLE. `llm_escalate_major` only produces review.

- **pass -> review**: Via `llm_escalate_major` (LLM fail with major axis),
  `source_aware_review_cap`, or `ideal_review_cap`.

### 3.6 Guardrails on clear (review -> pass)

`llm_clear_soft_review` is blocked when any of:
1. Hard flags present (`_has_only_soft_flags()` returns False)
2. `missing_region_count > 0` (FUSION_RULE_CLEAR_BLOCKED_MISSING_REGION)
3. Ideal soft flags present (FUSION_RULE_CLEAR_BLOCKED_IDEAL_FLAG)
4. LLM confidence < CONFIDENCE_DECISION_FLOOR (0.50)
5. ref_nid < FUSION_REF_NID_FLOOR (0.10) and ref_nid is not None

### 3.7 Source-aware review cap

`_source_aware_requires_review()` (line 183) implements fail-closed logic:
- Non-pass metadata check -> review
- Incomplete unit coverage -> review
- Unchecked or failed unit IDs -> review
- High/critical severity defect groups with verified count > 0 -> review
- Accepted unit-check claims with exact source + candidate_not_found -> review

This runs BEFORE the clear check, so source-aware evidence trumps LLM clear.

### 3.8 Stale sidecar detection

`_whisker_fingerprint()` (line 99) computes a SHA-256 hash (truncated to
16 hex chars) of the canonical JSON-serialized whisker sidecar. This
fingerprint is stored in the `FusionResult` for downstream staleness
detection. If the deterministic sidecar changes, the fingerprint changes,
and the fusion result is stale.

### 3.9 Test coverage (test_fusion.py)

The test suite covers:
- `test_fail_locked`: det=fail stays fail when LLM says pass
- `test_rescue_never_upgrades_to_pass`: heading rescue produces review
- `test_clear_soft_review`: review with soft-only flags cleared by LLM pass
- `test_clear_blocked_missing_region`: clear blocked by missing regions
- `test_clear_blocked_ideal_flag`: clear blocked by ideal soft flags
- `test_escalate_major`: pass escalated to review by LLM fail+major
- `test_malformed_payloads`: invalid sidecars fall back to whisker_only
- `test_source_aware_review_cap`: source-aware caps non-fail at review
- `test_ideal_review_cap`: ideal verifier caps non-fail at review

Complete parametric matrix covering all rule combinations. All pass (E1).

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | fail-to-pass transition is structurally impossible in the fusion matrix | Informational | HIGH |
| F2 | pass-to-fail transition is structurally impossible | Informational | HIGH |
| F3 | review-to-pass requires five simultaneous guardrail conditions | Informational | HIGH |
| F4 | Source-aware review cap runs before clear check (trumps LLM opinion) | Informational | HIGH |
| F5 | Stale/error/stub sidecars fall back to whisker_only (safe default) | Informational | HIGH |
| F6 | FusionResult.advisory = True is frozen (immutable) | Informational | HIGH |

No violations found.

## 5. False-Pass Hypothesis

**Could operator manipulation of sidecar files change fusion behavior?**

An operator with disk access could modify the tapetum sidecar to change
the `suggested_verdict` or `confidence`. However: (1) fusion is advisory
and never affects `whisker --gate` exit codes, (2) the whisker fingerprint
detects staleness of the deterministic sidecar, and (3) the `advisory=True`
field is frozen on `FusionResult`. The impact of sidecar manipulation is
limited to changing the advisory merged report, not the CI gate.

## 6. Gate/Dimension Mapping

- **D1 (All LLM via pipeline)**: PASS. Fusion is pure Python. No LLM calls.
- **D3 (Batch isolation)**: PASS. Fusion operates per-paper: each
  `fuse_verdicts()` call is independent, no shared state between papers.

## 7. Limitations

- Fusion is pure Python and fully testable offline. No runtime limitation
  for this role's core checks.
- The interaction between live LLM sidecars and fusion behavior in practice
  requires runtime testing (BLOCKED).
- Sidecar integrity on disk is not cryptographically verified (SHA-256
  fingerprint covers the whisker sidecar, not the tapetum sidecar).

## 8. Conclusion

The fusion rule matrix is well-designed and asymmetric by construction.
The critical properties hold: fail-to-pass and pass-to-fail transitions
are structurally impossible. Review-to-pass (clear) requires five
simultaneous guardrail conditions. Source-aware and ideal review caps run
before clear checks. Stale, errored, and stub sidecars fall back to the
deterministic verdict. The fusion is advisory, never affecting CI exit
codes, and the complete test matrix covers all rule combinations.
