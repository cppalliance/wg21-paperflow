# ADR-008: Router hygiene + dynamic MAX_UNIT_CHECKS

## Title

Replace fixed fleet `MAX_UNIT_CHECKS = 5` with a per-paper dynamic quota (base 3, ceiling 7), ship Tier-1 router hygiene immediately, and A/B-gate combo_safe router tightening as one bundle with the dynamic cap.

## Status

**Proposed** — usable-with-conditions. Third-tier N cut on the single-pod path. Tier-1 hygiene may ship without holdout; dynamic quota + combo_safe require stratified A/B.

## Context

Single `alliance-pod`, `S_eff = 16`. Dual-pod out of scope.

After v11 metadata short-circuit, residual unit waste is not a second metadata class. Sidecar analysis puts ~**289** fusion-dead survivor calls (cap-locked pass-tier units + refuted escalations) as the upper band (~**361 s** @ S=16). That band is **not** fully harvestable without quality risk.

Quality exposure is stratified:

- **16/381** — any LLM-driven merged verdict change (mostly monolith rescue/clear, not unit-sourced).
- **3/381** — unit accepted `defect_groups` drove `source_aware_review_cap` (primary recall gate for unit cuts).
- **6/47** defect-group papers lose unit evidence under combo_safe in replay (merged unchanged).

Static cap **5→3** treats every paper alike; **179/180 PDFs** already saturate cap 5. The failure mode at low caps is **SIGNAL_CLASS_QUOTA** burning all slots on diversity (heading_drift) before `table_presence` (PR #286-class). Dynamic bumps recover table/severity floors while dropping zero-yield slots 4–5 on clean saturated PDFs.

Router waste beyond metadata is selection quality: `_select_units_with_quotas` has no fusion awareness. combo_safe trims ~**63** post-v11-scaled calls (~**79 s**) with bounded FN.

Safe combined harvest: **~150–220 calls (~190–310 s @ S=16)**, not the full 289. Still insufficient alone for ≤600 s.

Package boundary: `packages/whisker/` only.

## Decision

1. **Dynamic quota (fleet mode only)** — before `_select_units_with_quotas`:

```python
def fleet_max_unit_checks(
    routable_risky_ids: list[str],
    signals_by_unit: dict[str, list[RiskSignal]],
    *,
    base: int = 3,
    ceiling: int = 7,
) -> int:
    signals = [s for ss in signals_by_unit.values() for s in ss]
    bump = 0
    if any(s.severity in {"critical", "high"} for s in signals):
        bump += 1
    if any(s.signal_type == "table_presence" for s in signals):
        bump += 1
    if len(routable_risky_ids) > 8:
        bump += 1
    return min(ceiling, base + bump)
```

   - Constants: `FLEET_UNIT_CHECK_BASE = 3`, `FLEET_UNIT_CHECK_CEILING = 7`; keep `MAX_UNIT_CHECKS = 5` as test/ceiling alias until migration complete.
   - Invariants: `--inspect` / `--exhaustive-units` / `--all-pages` bypass cap; unroutable pre-filter unchanged; overflow → `unchecked_unit_ids` → `coverage_complete=false` → fusion review cap (fail-closed, not silent pass).

2. **Do not** permanently ship static cap 3 as fleet default. Cap-3-only remains an optional A/B experiment for bump tuning.

3. **Router Tier 1 (ship first, zero LLM risk):** do not emit `heading_drift` when `unit_text_map[unit_id]` is empty.

4. **Router Tier 2 combo_safe (holdout-gated, bundled with dynamic quota):**
   - One `table_presence` per paper (first table page).
   - Drop PDF `heading_drift` with `detail` >120 chars containing `large-font`.
   - `SECTION_RECALL_FLOOR` 0.90→0.85 (measured ~16 signals; 5/16 checked units had defects).

5. **Tier 3 quota walk (pairs with dynamic cap):** reserve `table_presence` and `low_recall` before `heading_drift` when `max_checks ≤ 4`; optional `SIGNAL_CLASS_QUOTA = 0` for `heading_drift` when `table_presence` exists on the same paper.

6. Persist `unit_selection.max_checks_dynamic` in sidecars; bump `_LANE_VERSION`. No ship on wall alone.

## Consequences

**Positive**

- Reclaims **~132–220** unit calls via dynamic quota (~165–275 s); combo_safe adds ~63 (~79 s); combined central **~150–250** calls / **~190–310 s** after overlap.
- Preserves table/severity floors that static cap 3 can starve.
- Tier-1 empty-packet hygiene stops signal noise with no recall trade.

**Negative / risks**

- Blind cut of all 289 fusion-dead calls risks the **3/381** cap-drivers and inspect detail on the **16/381** flip set.
- combo_safe: **6/47** defect-group papers lose unit-level evidence (inspect false-clear appearance; multi-table FN on P4025R1/R2).
- Uniform low cap on clean long PDFs → more advisory `review` noise (operators treating review as shippable ≈ effective false-fail).
- Overlap with metadata short-circuit and other N cuts: do not sum naively.

**Neutral**

- Fail-closed coverage cap still yields `review`, not silent `pass`, when table pages are missed.
- Timeout formula `(1+MAX_UNIT_CHECKS)×120` shrinks with lower caps; irrelevant to mean cold wall.

## Evidence

| Claim | Source |
|-------|--------|
| ~289 fusion-dead survivors; safe ~150–220 calls | `14-router-quota-1pod.md`; `50-router-false-economy.md` |
| 16/381 vs 3/381 influence | `70-fusion-verdict-influence.md`; `14` risk matrix |
| Dynamic policy + SIGNAL_CLASS_QUOTA H3 | `58-max-unit-checks-knob.md`; `14` Design A |
| combo_safe ~63 calls / ~79 s; 6/47 FN | `11-router-precision-auditor.md`; scaled in `14` / `50` |
| 179/180 PDFs saturate cap 5 | `58`; `14` |
| Status: router not started; MAX_UNIT_CHECKS constant only | `10-impl-status-1pod.md` |
| HTML median 4 vs PDF median 5 units | `22-html-vs-pdf-mix.md`; `58` |

## Quality gate

Required before shipping dynamic quota + combo_safe:

1. **Fleet A/A** on 381 → establish `flip_AA` noise floor.
2. **Candidate B** = dynamic quota + combo_safe (or cap-3 alone for sensitivity).
3. **Pass iff** four-component equivalence vector is discordant with **both** A runs; `flip_AB ≤ flip_AA + margin`.
4. **Stratified must-not-regress:**
   - All **16/381** discordant PIDs reviewed (not pass-rate only).
   - **3/381** cap-driver papers: defect-group multiset unchanged.
   - **48 holdout anchors:** non-regressing recall.
   - **9 dev-replay PRs:** `recall_B ≥ recall_A − 0.05`.
5. **Acceptable trade:** higher `review` from coverage cap if **zero new `pass`** on anchor blockers.

**Tier-1** empty-packet `heading_drift` skip: may ship without the full vector (zero LLM risk).

**Mind-changers:** slots 4–5 on all 16 merged-flip papers tagged zero-defect on fresh v11 replay → upgrade safe cut toward ~250 calls; combo_safe **0/47** FN → upgrade router trim; dynamic A/B with 381/381 equivalence and unchanged 3/381 defect groups → ship as MODERATE single-pod lever.
