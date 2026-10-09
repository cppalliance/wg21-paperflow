# D01 — SLA target: ≤10 min vs ~15–20 min

**Date:** 2026-07-24  
**Status:** Open (human / product)

---

## Decision needed

Keep the cold-fleet goal as **≤600 s (~10 min)** on one MoE pod, or **reset the published SLA to ~15–20 min** until dense infra is live?

## Recommendation from research

**Conditional.** Keep ≤10 min only as a design target for Option B (heterogeneous cascade) after Alliance restarts dense. Until then, publish **~15–20 min** as the honest shippable SLA (Option A MoE package). Do not promise ≤10 min on MoE-only.

## If yes (keep ≤10 min)

- Program stays blocked on dense restart + payload scoping + 381 gate.
- Wall model is `max(T_moe, T_dense)` ≈ **~511 s** central if scoping + 2× dense decode + parity land.
- Failure mode: months of work still miss 10 min if dense stays 404; credibility hit if SLA is advertised as MoE-only.

## If no (reset to ~15–20 min)

- Ship Option A without waiting on ops: det-metadata → verdict-first → router → server Tier-1.
- Honest floor after MoE AGGRESSIVE realistic: **~12–15 min**; MODERATE ~23–25 min.
- ≤10 min becomes a later milestone when dense returns, not a current commitment.

## Evidence

| Claim | Source |
|-------|--------|
| MoE-only ≤600 s below quality floor; front-end alone 948 s | `17-physics-floor-skeptic.md` |
| Heterogeneous central ~511 s; only ≤10 min candidate | `12`, `20`, `SYNTHESIS.md` |
| Without dense: honest SLA ~15–20 min | `PLANNING-HANDOFF.md` §3–4, Option C |
| Dense pods 0/4 UP today | `26-dense-pod-liveness.md` |
