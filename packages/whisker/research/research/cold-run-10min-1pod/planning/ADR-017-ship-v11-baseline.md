# ADR-017: Ship v11 as the measured baseline

## Status

Proposed

## Date

2026-07-24

## Context

Working-tree `_LANE_VERSION = 11` already lands the largest single-pod call cut: metadata-fail short-circuit (−1059 to −1341 s of fusion-dead unit/page work), plus LJF ordering, `asyncio.to_thread(screen_pages)`, monolith/tier timeouts, empty-packet pre-filter, and partial PDF HMAC / md-first prefix reuse. Arithmetic after those levers is **~1260–1493 s (~21–25 min)** cold wall at S=16, not the measured v10 **3003 s**.

No fresh cold fleet run exists on post-v11 HEAD. Continuing to quote 3003 s as the baseline confounds every later A/B (det-metadata, verdict-first, router, dense cascade) and makes quality-gate Config A dishonest (`19`: Config A must be MODERATE single-pod, not v10). Shipping further levers without a committed, remeasured v11 baseline also leaves partial v11 work (text-lane HMAC, monolith/metadata reorder) unanchored.

## Decision

1. **Remeasure first.** Run one bare full-fleet cold on local working-tree v11 under the measurement protocol (off-hours, matched `/metrics` occupancy). Expect ~21–25 min; record wall, call census, and sidecar fingerprints.
2. **Treat that run as Config A / truth baseline** for all subsequent packages. Stop using 3003 s as the denominator for “wins after v11.”
3. **Ship / commit the landed v11 levers** (short-circuit + already-done scheduling/cache hygiene) as the stable lane baseline once the remeasure confirms the arithmetic order of magnitude.
4. Finish remaining partial v11 items (text-lane `guard_tag`, md-first on HTML unit/metadata, monolith/metadata prompt reorder) as low-risk follow-ons; do not bump lane solely for prompt geometry if fused verdicts are unchanged.
5. Do **not** claim further wall cuts, or start dense-offload quality gates, until step 1 lands a number.

## Consequences

**Positive**

- Honest baseline for Option A MoE package and for Option B Config A (~23–25 min).
- Largest lever already coded is locked as the comparison point; later tickets measure deltas against ~21–25 min, not 50 min.
- Unblocks P1 in the handoff phase table without inventing dual-pod capacity.

**Negative / cost**

- Remeasure costs one full cold fleet (~0.5 h wall, longer under shared-pod noise).
- If remeasure comes in ≫25 min, short-circuit accounting or shared-tenant occupancy must be revisited before shipping the “v11 baseline” label.
- Partial prefix / text-lane HMAC savings stay estimated until finished and remeasured.

**Falsifiers**

- Post-v11 cold ≤700 s without dense offload → revisit L_abs / short-circuit accounting before treating ~21–25 min as the floor.
- Remeasure still ~48–50 min → do not ship “v11 baseline”; debug short-circuit path before any further package.

## Evidence

| Claim | Source |
|-------|--------|
| Metadata short-circuit −1059 to −1341 s; `_LANE_VERSION = 11` | `10-impl-status-1pod.md` |
| Expected cold after v11 ~1260–1493 s (~21–25 min) | `10-impl-status-1pod.md`, `SYNTHESIS.md` |
| No fresh cold run post-v11; remeasure before treating arithmetic as fact | `10-impl-status-1pod.md`, `SYNTHESIS.md` |
| Config A = MODERATE single-pod on working-tree v11, not v10 3003 s | `19-quality-gate-1pod.md`, `PLANNING-HANDOFF.md` §10 |
| P0 remeasure → P1 ship v11 | `PLANNING-HANDOFF.md` §6 |
| Decision checklist item 3: ship v11 as committed baseline | `PLANNING-HANDOFF.md` §5 |
