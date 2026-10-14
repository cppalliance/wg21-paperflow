# Lever scorecard (1 MoE pod, S=16)

**Date:** 2026-07-24  
**Sources:** `SYNTHESIS.md`, reports `10`–`20`  
**Constraint:** twin V4-Pro forbidden; `--max-num-seqs` stays 16.

Wall savings are overlap-aware estimates at **S=16** on `alliance-pod` unless noted.  
**Bankable for 10min?** = may this lever’s seconds be counted toward a ≤600 s commitment without inventing capacity.

| Lever | Est wall save @S=16 | Quality risk | Infra needed | Ship order | Bankable for 10min? |
|-------|--------------------:|--------------|--------------|------------|:-------------------:|
| Metadata-fail short-circuit (v11) | −1059 to −1341 s | Low (landed) | None | P1 (done in tree) | N |
| LJF + `to_thread` + timeouts | −60 to −120 s (T+C) | None | None | P1 (done) | N |
| HMAC / md-first prefix (PDF partial) | −100 to −281 s (survivors) | Low | None | P1 finish HTML/text | N |
| Error tombstones / `--retry-errors` | 0 s cold | None | None | P1 (done) | N |
| Escalation dedupe | −4 to −23 s | Low | None | P1–P2 hygiene | N |
| Per-call `call_timings[]` | 0 s (A/B enabler) | None | None | Before P2 A/B | N |
| Deterministic metadata / outline | −~471 s | High (A/B: ≤5% drift, 0 fused flips) | None (code) | P2 | N |
| Verdict-first / schema bifurcation | −124 to −155 s (survivors) | Medium (48-anchor holdout) | None | P3 | N |
| Router combo_safe | −79 to −238 s (−~63 calls post-v11) | Medium (6/47 FN) | None | P3 | N |
| Dynamic `MAX_UNIT_CHECKS` quota | −165 to −275 s (−132–220 calls) | Low–Medium (gate 3/381 + 16/381) | None | P3 | N |
| Static cap 3 (experiment only) | −193 to −628 s (scaled vs raw) | Medium–High | None | Optional A/B only | N |
| Router + dynamic combo (paired) | −190 to −310 s | Medium | None | P3 | N |
| Server Tier-1 (MBT 16384, APC, CUDA graphs) | −60 to −180 s (−~186 s post-SC conservative) | Low | Pod restart / image | P4 | N |
| DeepEP low-latency (± DBO if thresholds) | −50 to −150 s (~10–15% tok/s @ S=16) | Low | Ops flags | P4 after Tier-1 | N |
| MTP k=1 speculative decode | −120 to −470 s (ops envelope) | Medium (JSON short-OSL) | Ops A/B | P4 gated | N |
| Fail-fast retries | −45 to −80 s | Low | None | Hygiene anytime | N |
| Payload scoping (~10–15k/unit) | Enabler (prefill ~−198 s; unlocks dense S) | Medium (index miss → MoE fallback) | None (code); dense for EV | P6 | Maybe |
| Dense unit/metadata offload (`h200-qwen3-32b`) | −850 to −1200 s (single-queue); hetero wall → ~511 s | High (381/381 parity) | **Restart dense pod** (404 today) | P5→P7 | Maybe |
| Heterogeneous cascade (units dense, ≤15% escalate) | Fleet wall ~510–710 s if scoping+parity | High (same gate as dense) | Dense live + MoE | P7 | Maybe |
| Non-think kwargs on unit path | Unmeasured L cut | Medium (A/B) | Probe alliance-pod | Parallel probe | N |
| Call-class fingerprints | 0 s first cold | None | None | Out of cold path | N |
| Skip monolith | — | Critical (false-clears) | — | **Reject** | N |
| Twin / S=32 / c>32 | — | Forbidden / regresses | — | **Reject** | N |
| Flash V4 unit-judge | Theory ~1.7× decode if deployed | Medium | New endpoint/weights | Out of budget | N |
| `--det-skip` default | ~250–350 s (advisory) | High | — | Opt-in only | N |
| P/D disagg / `VLLM_BATCH_INVARIANT` / guided_grammar | Flat or regress | High / N/A | — | **Reject** | N |

## Notes

1. **MoE-only stack cannot bank a 10 min claim.** Physics floor: front-end alone 758×20/16 = 948 s (`17`); MODERATE central ~1366 s (`18`); AGGRESSIVE realistic ~715–910 s (`11`).
2. **Only Maybe path:** live dense + payload scoping + 381 parity → `wall = max(T_moe, T_dense) ≈ 511 s` (`12`, `20`). Infra-blocked while dense endpoints return HTTP 404 (`SYNTHESIS`, `26`).
3. **Do not bank** MTP, Flash, or dense seconds until A/B + infra land (`SYNTHESIS` reject ledger).
4. Ship order aligns with `PLANNING-HANDOFF.md` phases P0–P8; see `DEPENDENCY-GRAPH.md`.
