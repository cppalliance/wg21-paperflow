# D14 — Enable DeepEP low-latency

**Date:** 2026-07-24  
**Status:** Open (ops Tier-2 after Tier-1 smoke)

---

## Decision needed

Enable `--all2all-backend deepep_low_latency` on `alliance-pod` after Tier-1 recipe flags (MBT / CUDA graphs / prefix)?

## Recommendation from research

**Yes, as measured Tier-2.** Plan ~**10–15%** output tok/s at seqs=16 (~12% planning pin). Most fixed-seqs EP win is DeepEP-LL, not DBO. Never `deepep_high_throughput` on this mixed judge node. Optional `--enable-dbo` only if DEP thresholds fire and A/B improves wall.

## If yes

- Honest L cut without forbidden S raise; stacks with client N cuts.
- Ops verifies via `/metrics` + startup greps; revert DeepEP before MBT if regress.
- Alone still leaves post-SC wall ~25 min class — do not claim 10 min from DeepEP.

## If no

- Leave default AGRS EP path; forgo the main fixed-S=16 server tok/s lever.
- Tier-1 (MBT/graphs/prefix) may still ship without DeepEP.

## Evidence

| Claim | Source |
|-------|--------|
| DeepEP-LL ~10–15% @ seqs=16; DBO often 0–5% alone | `05t-web-dbo-deepep.md`, ADR-011 |
| Server Tier-1 then DeepEP; never S>16 | `16-server-ops-1pod.md`, `SYNTHESIS.md` |
| CHECK pin ~12% | `planning/checks/CHECK-deepep-12pct.md` |
