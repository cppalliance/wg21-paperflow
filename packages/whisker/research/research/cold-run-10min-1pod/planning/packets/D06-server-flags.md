# D06 — Server flags on alliance-pod

**Date:** 2026-07-24  
**Status:** Open (ops)

---

## Decision needed

Apply Tier-1 vLLM/ops flags on `alliance-pod` (MBT 16384, decode CUDA graphs, EP / `deepep_low_latency`, APC retention) while **never** raising `--max-num-seqs` above 16? Treat MTP k=1 and DBO as A/B-only, not banked?

## Recommendation from research

**Yes on Tier-1; no bank MTP/DBO.** Plan ~10–15% tok/s from DeepEP low-latency at S=16. MTP k=1 / ngram behind acceptance gate (short JSON @ c≈16 is lose/flat). DBO usually flat at seqs=16. Confirm async-scheduling: if `running≈16` + elevated waiting under c=32, try `--no-async-scheduling`. Never enable `VLLM_BATCH_INVARIANT` on the speed path.

## If yes (Tier-1 + gated experiments)

- Server-only ceiling post-SC: **~3–7 min** saved; still ~25 min without client cuts.
- Ops restarts required; measure with `/metrics` before/after.
- MTP may need disable under load if acceptance collapses.

## If no (leave server defaults)

- Leave ~5–15% decode on the table; client N-cuts remain the only path.
- Avoid restart risk on shared Alliance traffic.
- Still cannot hit 10 min either way from server alone.

## Evidence

| Claim | Source |
|-------|--------|
| Server checklist; never S>16 (+57% wall) | `16-server-ops-1pod.md`, `ADR-002` |
| DeepEP ~10–15%; DBO flat at 16 | `05t`, `SYNTHESIS.md` |
| MTP short JSON lose/flat @ c≈16 | `05j` |
| BI mode ~50% throughput hit | `05v`, `NON-GOALS.md` |
| Async-scheduling underfill heuristic | `05s` |
