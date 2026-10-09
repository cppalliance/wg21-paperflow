# D08 — Measurement protocol for cold A/B

**Date:** 2026-07-24  
**Status:** Open (engineering)

---

## Decision needed

Require off-hours cold fleets with matched `/metrics` occupancy, and never treat a single A/B as ground truth under shared-pod noise?

## Recommendation from research

**Yes.** `alliance-pod` is Alliance multi-tenant: HIGH wall and verdict variance. Protocol: off-hours windows, log `/metrics` (running/waiting/util) for A and B, double-A or weekly-refreshed A2 at same `_LANE_VERSION`, `--force` cold (no warm fingerprint skip for equivalence). Half slots stolen ≈ ~2× wall; ≥25% flip confound on borderline sets.

## If yes (strict measurement)

- Honest deltas for v11 remeasure, det-metadata, dense B, and D05 gates.
- Slower calendar (wait for quiet windows; sometimes two A runs).
- Rejects false “wins” from empty-pod A vs crowded B.

## If no (ad-hoc single runs)

- Confound every lever claim; ship on noise.
- May quote 3003 s or one lucky 500 s as truth.
- Quality gate flip_AA becomes meaningless under unmatched occupancy.

## Evidence

| Claim | Source |
|-------|--------|
| Shared-pod HIGH variance; ~2× if half slots stolen | `28-shared-pod-noise.md` |
| Off-hours + `/metrics`; never single A/B as GT | `SYNTHESIS.md`, handoff §5 item 10 |
| A/A then bundled B; no warm skip for equivalence | `19-quality-gate-1pod.md` |
| Remeasure v11 before further claims | `ADR-017`, `10` |
