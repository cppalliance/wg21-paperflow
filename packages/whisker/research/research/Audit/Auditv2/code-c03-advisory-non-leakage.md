# C03 Advisory Non-Leakage

**Role**: Prove advisory LLM output cannot authorize a deterministic gate.
**Audited state**: whisker 0.5.0, HEAD 51cb704 + local mods.
**Gates**: G1 (Deterministic Gate Integrity), D1 (All LLM calls via pipeline).

## 1. Scope

Verify the architectural claim that tapetum_llm advisory verdicts never change
whisker exit codes, fusion cannot promote fail to pass, and the two lanes use
separate report paths (whisker/det/ vs whisker/llm/).

## 2. Commands and Exits

```
uv run --package whisker pytest packages/whisker/tests/test_fusion.py -v
```

Exit: BLOCKED (real-LLM tests require ALLIANCE_POD_KEY). Offline test suite
passes (E1 from shared ledger: 1406 passed, 8 skipped, 3 xfailed).

## 3. Current Evidence

### 3.1 score.py: No LLM import, no advisory input

`score.py` imports only deterministic modules: `whisker.constants`,
`whisker.gates`, `whisker.golden_ideals`, `whisker.metrics`,
`whisker.reference`, `whisker.bench`. No import from `tapetum_llm` exists.
`_decide()` (line 136) accepts only numeric thresholds and `GateResult` objects.
The `ideal` parameter triggers only soft (review) flags, never hard fails
(lines 206-215: `soft.append(...)`, never `hard.append(...)`).

The `WhiskerResult.advisory` field does not exist on this dataclass. No advisory
LLM verdict is accepted as input anywhere in `score.py`.

### 3.2 __main__.py: Exit codes from deterministic verdicts only

`_verdict_exit_code()` (line 130) reads from `[r.verdict for r in results]`
where each `r` is a `WhiskerResult` from `score_paper()`. The exit code map
is `{0: ok, 1: error, 3: review, 5: fail}` per `constants.py` lines 154-157.
No tapetum verdict is consulted.

The `_GATE_ACCEPTS` dict (line 88) maps `--gate` choices to accepted verdicts.
These are compared only to `WhiskerResult.verdict`, which is set exclusively by
`_decide()` in `score.py`.

### 3.3 fusion.py: Asymmetric rules prevent fail-to-pass promotion

`fuse_verdicts()` (line 329) is the only merge function. Code evidence for
each rule:

- **whisker_fail_locked** (line 379): When `det == VERDICT_FAIL` and the fail is
  NOT heading-only, the combined verdict is `VERDICT_FAIL` regardless of LLM
  opinion. This is unconditional.

- **llm_rescue_heading** (line 367): The ONLY rescue path. Requires ALL of:
  `det == VERDICT_FAIL`, `_is_heading_only_fail(whisker)` (line 292, checks
  every hard flag starts with `"gate:heading_monotone"`), and LLM says pass or
  review. Result: `VERDICT_REVIEW`, never `VERDICT_PASS`.

- **llm_clear_soft_review** (lines 459-496): Requires `det == VERDICT_REVIEW`,
  `_has_only_soft_flags(whisker)` (no hard flags), `llm == VERDICT_PASS`,
  `conf >= CONFIDENCE_DECISION_FLOOR` (0.50), and either `ref_nid >= 0.10` or
  `ref_nid is None`. This is review-to-pass, never fail-to-pass.

- **llm_escalate_major** (line 501): `det == VERDICT_PASS` and LLM says fail
  with a major axis finding. Result: `VERDICT_REVIEW`, never `VERDICT_FAIL`.

- Additional guardrails: `FUSION_RULE_CLEAR_BLOCKED_MISSING_REGION` (line 424)
  blocks clear when `missing_region_count > 0`. `FUSION_RULE_CLEAR_BLOCKED_IDEAL_FLAG`
  (line 441) blocks clear when deterministic ideal flags are present.

**Summary of all possible transitions**:
- fail -> fail (locked, non-heading)
- fail -> review (rescue, heading-only)
- review -> pass (clear, soft-only + guardrails)
- review -> review (blocked clear, or no applicable rule)
- pass -> review (escalate major)
- pass -> pass (agree)

**NEVER**: fail -> pass. The code path does not exist.

### 3.4 FusionResult.advisory field

`FusionResult` (line 66) has `advisory: bool = True` as a frozen dataclass
field. It is always True with no setter or override path.

### 3.5 Separate report paths

`score.py` line 388: `whisker_output_dir()` returns `<root>/whisker/det`.
`cli.py` (tapetum) line 371: `_llm_output_dir()` returns `<root>/whisker/llm`.
Sidecars: `<pid>.whisker.json` (det) vs `<pid>.whisker.tapetum.json` (llm).
Reports: `report.md/json` (det) vs `report-merged.md/json` (llm).

### 3.6 Test evidence (offline)

`test_fusion.py` contains:
- `test_fail_locked`: asserts `det=fail` stays fail when LLM says pass.
- `test_rescue_never_upgrades_to_pass`: asserts heading rescue produces review,
  not pass.
- Parametric matrix covering all rule combinations.

All tests pass in the offline suite (E1).

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | No code path exists for fail-to-pass promotion | Informational (confirms claim) | HIGH |
| F2 | Rescue is constrained to heading-monotone-only fails and caps at review | Informational | HIGH |
| F3 | `FusionResult.advisory = True` is immutable (frozen dataclass) | Informational | HIGH |
| F4 | Clear-blocked guardrails add two extra barriers to review-to-pass | Informational | HIGH |

No violations found.

## 5. False-Pass Hypothesis

**Could an advisory verdict leak into a deterministic gate?**

The only hypothetical vector is if `__main__.py` ever read `fusion.combined_verdict`
instead of `WhiskerResult.verdict` for exit-code computation. Code inspection
shows `_verdict_exit_code()` receives `[r.verdict for r in results]` where `r`
is `WhiskerResult` (from `score_paper()`), not `FusionResult`. There is no
import of `fusion` or `FusionResult` in `__main__.py`. The vector does not exist.

## 6. Gate/Dimension Mapping

- **G1 (Deterministic Gate Integrity)**: PASS. Advisory output is structurally
  excluded from deterministic exit codes and verdicts.
- **D1 (All LLM via pipeline)**: PASS for tapetum_llm (uses `run_agent`/
  `run_task`). Readback has a documented D1 exemption (raw httpx, no pipeline
  steps). Neither touches the deterministic gate.

## 7. Limitations

- Runtime proof BLOCKED: cannot confirm live LLM verdicts are actually advisory
  in a running system with real model output. All evidence is from code/test
  inspection.
- Fusion matrix tested only with synthetic sidecar dicts, not real-world
  sidecar files from a live run.

## 8. Conclusion

The advisory non-leakage claim holds. The architecture enforces a strict
one-way boundary: `score.py` does not import `tapetum_llm`, `__main__.py`
computes exit codes exclusively from `WhiskerResult.verdict`, and `fusion.py`'s
asymmetric rules make fail-to-pass structurally impossible. The `advisory=True`
field on `FusionResult` is frozen. Separate disk paths (`whisker/det/` vs
`whisker/llm/`) prevent accidental overwrite.
