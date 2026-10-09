# ADR-007: Verdict-first unit schema (UnitCheckClear bifurcation)

## Title

Bifurcate unit checks into a pass-path micro-schema (`UnitCheckClear`) and a fail/review schema (`UnitCheckDefects`), with verdict-first field order and paired `max_tokens`.

## Status

**Proposed** — usable-with-conditions. MODERATE decode lever #3 on the single-pod path. Holdout-gated before default.

## Context

Single `alliance-pod`, `S_eff = 16`. Dual-pod out of scope.

After v11 metadata Tier A+B short-circuit, survivors are still decode-bound on unit checks: **~663** unit calls remain (~463 / ~70% zero-defect). Those pass calls still emit full nested `UnitCheck` JSON (`reasoning` first ≤40 words, `defects[]` max 5 with 7-field `DefectFinding`, `verdict`, `confidence`) for no downstream value: fusion and grounding skip unit reasoning on pass.

Measured pass P50 ≈ **77 tok** (~55 tok in `reasoning`). Target clear JSON ≈ **15–25 tok**. Nested arrays, free `defect_type: str`, and `ge`/`le`/`maxItems` in served schema push vLLM XGrammar toward context-dependent masks or Outlines fallback; community guidance favors bifurcating pass vs findings schemas and dropping grammar bounds in favor of post-parse Pydantic validators (`05n-web-v4-structured.md`, tactics 1–4).

Savings must apply **L_abs on survivors only** (no phantom stack with short-circuited units). Central estimate: unit bifurcation **~92 s** (77–110 s) @ S=16; full MODERATE verdict-first stack (units + metadata/monolith reasoning caps) **~155 s** (124–155 s). Post short-circuit + verdict-first wall ≈ **~1338 s** — still short of ≤600 s.

Package boundary: `packages/whisker/` only.

## Decision

1. Add `UnitCheckClear` (pass-only micro-schema):
   - Field order: `unit_id` → `verdict: Literal["pass"]` → `confidence` → optional short `reasoning` (≤10 words; empty preferred).
   - No `defects[]`. Validator rejects non-pass.
   - Call with `max_tokens=128` (retry ceiling 192).
2. Add `UnitCheckDefects` (fail/review path): current `UnitCheck` shape, enum-hardened:
   - `defect_type` → closed `Literal` of the eight existing categories.
   - Drop `ge`/`le`/`maxItems` from **served** JSON schema; keep Pydantic validators + `ModelRetry`.
   - Cap quote length in prompt, not grammar `maxLength`.
   - Call with `max_tokens=768` (retry ceiling 1152). Do not lower global judge default below 768 until routing exists.
3. **Routing** in `unit_judge.py`:
   - Default: Stage 1 on metadata-pass units that are not high-risk; map clear → `UnitCheck` with `defects=[]`.
   - Escalate to Stage 2 when: `confidence < UNIT_CLEAR_CONFIDENCE_FLOOR` (e.g. 0.85); router high-risk (`table_presence`, keyword delta); deterministic pre-screen recall below floor; Stage 1 transport/parse failure.
   - High-risk / defect-prone units may skip Stage 1 (zero added calls on known-fail path).
   - Do not ship “always Stage 1 then Stage 2” without holdout proof Stage 1 miss ≤5% (worst case ~+250 s).
4. Persist via `to_unit_check()`; include `unit_schema_variant` in lane fingerprint when A/B-ing; bump `_LANE_VERSION`.
5. Keep `verify_unit_evidence`, keyword delta groups, and deterministic post-checks. Do not delete semantic axes beyond omitting empty `defects[]` on the clear path.

## Consequences

**Positive**

- ~52–62 tok saved per clear call; XGrammar stays on flat cached path for ~70% of unit calls.
- Central **~92 s** wall from unit bifurcation; **~155 s** for full verdict-first stack @ S=16.
- Aligns with V4/vLLM schema-slim guidance: bifurcate, flatten, enum-harden, post-validate bounds.

**Negative / risks**

- Empty/short reasoning removes auditable CoT on the pass path (selection-gap risk).
- Naive Stage 1→2 on every unit doubles calls on defect papers (~+250 s).
- Fewer free axes can raise MoE rerun variance if over-slimmed.
- Cap alone without schema change saves ~0 s (model still emits 77-tok JSON).

**Neutral**

- Sidecar/fusion continue to consume `UnitCheck`-shaped records.
- Does not close ≤600 s alone; stacks with deterministic metadata, router/quota, dense offload.

## Evidence

| Claim | Source |
|-------|--------|
| 663 survivors, ~463 pass-shaped, 77→~20 tok | `15-verdict-first-design.md`; `47-max-tokens-shrink.md` |
| Stacking on survivors only | `11-wall-arithmetic.md`; `15` stacking rule |
| UnitClear ~92 s; full stack ~155 s @ S=16 | `15` savings tables |
| Post levers ~1338 s, gap remains | `15`; `10-impl-status-1pod.md` |
| Bifurcate + drop grammar bounds | `05n-web-v4-structured.md` tactics 1, 4; `62-schema-slim-web.md` |
| Reasoning-first CoT floor today | `models.py` UnitCheck field order |
| Status not started | `10-impl-status-1pod.md` Tier 1 |

## Quality gate

Ship blockers (all required):

1. **48-paper holdout:** ≥**95%** verdict stability vs current schemas.
2. **9 golden PR replay:** zero silent demotions on table/cell defects.
3. **No vacuous pass widening:** retain evidence verify, keyword deltas, deterministic post-checks.
4. **Stage 1 false-clear:** if >**5%** on holdout, disable optimistic routing (always Stage 2 on high-risk signals).
5. **Determinism:** do not remove `verdict` / `confidence` / essential axes; measure rerun instability vs baseline.

**Mind-changers (post-land 20-paper `--debug`):** pass median completion_tokens **>30** → caps below 128 unsafe; median **≤20** and measured wall Δ ≥**90 s** → upgrade central estimate; verdict flips exceeding ≥25% rerun instability baseline → revert to single-schema `UnitCheck` with reasoning cap only.
