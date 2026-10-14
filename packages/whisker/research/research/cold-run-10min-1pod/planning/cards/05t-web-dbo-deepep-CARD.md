# CARD: 05t — `--enable-dbo` + `deepep_low_latency` (fixed seqs)

## Bottom line
At fixed seqs=16, plan ~12% output tok/s (~10–15% band), mostly from `deepep_low_latency` vs default AGRS, not from DBO. High-batch literature peaks (~20–35% / +47%) do not transfer 1:1 when concurrent decode tokens sit below the microbatch win threshold (≥32).

## Numbers
- Planning pin @ seqs=16: **~12%** tok/s (band **10–15%**).
- Already on DeepEP-LL, DBO alone: **~0–5%** (often 0 / slight loss).
- Microbatch curve: bs < 32 → **−5% to −40%**; bs ≥ 32 → **+10% to +35%**.
- AWS DeepEP-LL vs AGRS smoke: ~**−30% TPOT** / burst tok/s **+62%** (topology+backend; upper envelope).
- Sibling ops envelope: DeepEP+DBO incremental ~**80 s** on 3003 s raw wall after MTP/CUDA overlap — not a 30% fleet cut.
- Simulator two-µbatch: **+12–48%** at high DP/batch (not seqs=16).

## Architecture implication
Prerequisite: DP>1 + EP + DeepEP installed. First A/B: `deepep_low_latency` alone. Second: add `--enable-dbo` + tune `--dbo-decode-token-threshold` (try ≤8 if MTP keeps effective tokens near 16). Use `deepep_high_throughput` only on prefill-disagg nodes, not mixed judge.

## Reject-or-A-B
- **A/B Tier-2:** DeepEP-LL then DBO at fixed S=16; keep only if tok/s or cold wall improves with identical verdict fingerprints.
- **Reject as planning multiplier:** high-batch +29% / +47% / wide-EP blog +47% attributed to full stack.
- **Anti-knob:** `deepep_high_throughput` on unified prefill+decode judge node.

## Links
- Source: `05t-web-dbo-deepep.md`
- Related: `16-server-ops-1pod.md`, `64-flashinfer-moe-kernels.md`
- https://docs.vllm.ai/en/latest/design/dbo/
- https://docs.vllm.ai/en/stable/serving/expert_parallel_deployment/
- https://blog.vllm.ai/2025/12/17/large-scale-serving.html
