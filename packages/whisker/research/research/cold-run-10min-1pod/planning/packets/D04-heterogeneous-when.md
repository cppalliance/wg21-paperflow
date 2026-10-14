# D04 — When to enable heterogeneous cascade

**Date:** 2026-07-24  
**Status:** Blocked until D02

---

## Decision needed

When (and under what gates) enable Option B: units (+ optional metadata) on dense, monolith/HTML/escalations on MoE?

## Recommendation from research

**Enable only after all four prereqs:** (1) `h200-qwen3-32b` live, (2) payload scoping ~10–15k/unit so dense S=32–48 is viable, (3) escalate ≤15% calibrated, (4) 381/381 fused-verdict parity + holdouts (`19`). Do not pilot on Gemma-4. Schedule after MoE package P2–P4 so Config A is clean.

## If yes (enable when prereqs met)

- Only arithmetic path under twin ban to ≤600 s: wall ≈ **max(~476 s MoE, ~207–511 s dense) → ~511 s** if 2× scoped dense holds.
- Semantic lane change: `_LANE_VERSION` bump; ~0.8–1.2 h validation wall.
- Risk: 70% offload alone (~856 s) still misses; need ~82.6% (units+metadata) and/or MODERATE cuts.

## If no (never / defer indefinitely)

- Cap at MoE-only ~12–23 min; ≤10 min program ends or waits on twin (forbidden).
- Avoid dense false-clear/fail and scoping recall loss.
- Still ship Option A quality improvements without model-family swap.

## Evidence

| Claim | Source |
|-------|--------|
| Architecture + ~511 s Scenario A | `12-dense-offload-architecture.md`, `ADR-003` |
| `wall = max(T_moe, T_dense)` | `20-heterogeneous-wall.md` |
| Without scoping dense collapses → negative EV | `23-payload-scope-dense.md`, `ADR-004` |
| Cascade lit: escalate ≤15% | `05l`, `05e`, `05p` |
| Dense 404 today | `26` |
