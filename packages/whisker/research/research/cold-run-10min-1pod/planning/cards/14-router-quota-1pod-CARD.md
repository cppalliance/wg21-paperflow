# CARD: Router + dynamic MAX_UNIT_CHECKS (single pod)

## Bottom line (3 sentences max)
Paired dynamic cap + router tightening can safely reclaim **~150–220 calls (~190–310 s @ S=16)** on post-v11 survivors. The full **~289-call (~12%)** fusion-dead band is **not** fully harvestable without risking the **3/381** unit-cap-driver papers. Third-tier N cut — cannot erase the ~800–900 s MODERATE gap alone.

## Numbers that matter
- Post-v11 survivors ~**1298** LLM calls; residual fusion-dead units ~**289** (~**361 s** upper bound @ S=16)
- Router combo_safe only: ~**63** calls / ~**79 s**; **6/47** defect-group FN; merged verdict unchanged on replay
- Dynamic quota (base 3, ceiling 7): ~**132–220** calls / ~**165–275 s**; preferred over static cap 3
- Combined (non-additive): ~**150–250** calls / ~**190–310 s**
- Gate sets: **16/381** merged LLM flips; **3/381** unit-cap defect-group drivers (primary recall gate)

## Architecture implication
Implement `fleet_max_unit_checks` (severity/table/routable bumps); ship Tier-1 router hygiene (no `heading_drift` on empty packets) immediately. A/B combo_safe + dynamic as one bundle; optional static cap-3 experiment only. Preserve `--inspect` / exhaustive / all-pages bypass and fail-closed coverage. `_LANE_VERSION` bump mandatory; do not sum with metadata short-circuit naively.

## Cite / do not re-open
- Blind harvest of all 289 fusion-dead calls
- Permanent static cap 3 as fleet default without holdout
- Treating router/quota as a substitute for dense offload / decode shrink
- Equating 16/381 with unit-only influence (only 3/381 are unit-cap drivers)

## Links to related reports
- `research/cold-run-10min-1pod/14-router-quota-1pod.md` (this source)
- `00-baseline.md`, `10-impl-status-1pod.md`, `19-quality-gate-1pod.md`
- Prior: `cold-run-10min/{50-router-false-economy,58-max-unit-checks-knob,70-fusion-verdict-influence}.md`
