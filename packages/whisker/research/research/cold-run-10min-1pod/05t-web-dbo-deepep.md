# 05t - Web: `--enable-dbo` + `deepep_low_latency` decode gains (fixed seqs)

**Question:** What measured tok/s uplift do Dual Batch Overlap (`--enable-dbo`)
and `--all2all-backend deepep_low_latency` deliver for DeepSeek MoE **decode**
at **fixed** concurrency (no seq raise)?

**Constraint:** alliance-pod keeps `--max-num-seqs 16`. Numbers below are for
decode / TPOT / output tok/s at fixed slots, not for raising batch.

**Date:** 2026-07-24

---

## Expected % tok/s uplift (planning)

| Regime | Expected output tok/s uplift | Confidence |
|--------|-----------------------------:|:----------:|
| **Fixed seqs=16** (alliance-pod planning) vs default `allgather_reducescatter`, EP already on | **~10–15%** | medium |
| High concurrent decode tokens (**≥32** per GPU), EP-bound, AGRS → DeepEP-LL + DBO | **~20–35%** | medium-high |
| Fixed seqs=16, **already** on `deepep_low_latency` (DBO alone) | **~0–5%** (often 0 / slight loss) | high |

**Single planning number for this corpus (fixed seqs=16 A/B):** **~12% tok/s**.

Rationale: at 16 concurrent decode tokens, DBO is in the documented
"microbatch hurts or is flat" regime unless MTP / multi-token steps push
effective tokens ≥32. Most of the fixed-seqs win is therefore
`deepep_low_latency` (CUDA-graph decode all2all) vs AGRS, not DBO. High-batch
literature peaks (~25–30%) do **not** transfer 1:1 to seqs=16.

Aligns with sibling ops envelope: DeepEP+DBO as an **incremental** ~80 s on
the 3003 s raw cold wall after MTP/CUDA overlap (`16-server-ops-1pod.md`), not
a 30% fleet cut.

---

## Flag contract (vLLM)

- `--enable-dbo` requires `--data-parallel-size > 1`, `--enable-expert-parallel`,
  DeepEP installed, and `--all2all-backend` ∈
  `{deepep_low_latency, deepep_high_throughput}`.
- Decode-heavy / unified judge node: **`deepep_low_latency`** (CUDA-graph
  friendly, masked layout). Prefill-disagg nodes: `deepep_high_throughput`.
- Knobs: `--dbo-decode-token-threshold`, `--dbo-prefill-token-threshold`.
- Example: `vllm serve … --data-parallel-size 2 --enable-expert-parallel
  --enable-dbo --all2all-backend deepep_low_latency`

Sources:
https://docs.vllm.ai/en/latest/design/dbo/
https://docs.vllm.ai/en/stable/serving/expert_parallel_deployment/

---

## Measured cards

### 1. Microbatch / DBO-class overlap (fixed batch sweep)

- **Source:** Perplexity research, multi-node DeepSeek deployment (Apr 2025;
  page stamp Jul 2026)
  https://research.perplexity.ai/articles/lower-latency-and-higher-throughput-with-multi-node-deepseek-deployment
- **Setup:** EP128, TP1, H100, KV≈5k, query length 2; MoE layer latency.
- **Headline (bs=128):** NoOverlap 2667 µs → MicroBatch 1896 µs → **+29% layer
  speedup** (≈ **+41%** if that layer dominated tok/s 1:1; e2e less).
- **Fixed-batch curve (MicroBatch vs DispatchOverlap):**
  - **bs < 32:** **−5% to −40%** (microbatch **hurts**)
  - **bs ≥ 32:** **+10% to +35%**
- **Impact on seqs=16:** without MTP doubling tokens/step, DBO is in the
  hurt/flat band. Do not budget a large DBO-only uplift at fixed 16.

### 2. Two-microbatch tok/s (DeepSeek simulator, H800)

- **Source:** DeepSeek_Simulator H800 results
  https://deepwiki.com/shenh10/DeepSeek_Simulator/5.2-h800-performance-results
  (CSVs: `H800-two-microbatch-overlapping.csv` vs single-batch)
- **Two-microbatch vs single-batch (tp=1), selected rows:**

  | DP | b_mla | Single tok/s | Two-µbatch tok/s | Δ |
  |---:|------:|-------------:|-----------------:|--:|
  | 32 | 64 | 1882 | 2327 | **+23.6%** |
  | 32 | 128 | 2782 | 3121 | **+12.2%** |
  | 48 | 64 | 2064 | 2560 | **+24.0%** |
  | 48 | 128 | 2415 | 3121 | **+29.2%** |
  | 72 | 64 | 1828 | 2560 | **+40.0%** |
  | 72 | 128 | 2064 | 3047 | **+47.6%** |

- **Range:** **+12–48% tok/s** at high DP / batch; sweet spot cited
  **b_mla 64–128**. Not a seqs=16 measurement.

### 3. `deepep_low_latency` vs AGRS (AWS / UCCL-EP, DeepSeek-V3)

- **Source:** awslabs `dsv3-uccl-nixl` README (vLLM 0.21, H200, single-seed
  smoke; authors warn to re-seed before citing externally)
  https://github.com/awslabs/awsome-distributed-ai/blob/main/3.test_cases/pytorch/vllm/dsv3-uccl-nixl/README.md
- **1P+3D DeepEP (HT prefill + LL decode) vs 1P+3D AGRS:**
  - Burst tok/s: 4408 vs 2721 → **+62%** (topology + backend; not pure kernel)
  - P50 TPOT @burst: 33.76 vs 48.20 ms → **≈ −30% TPOT**
- Authors summarize: UCCL-EP / DeepEP path **≈30% TPOT** vs AGRS on this MLA
  MoE. Inverse of 30% TPOT ≈ **~+43%** per-request decode rate if TPOT-bound.
- Backend note in same doc: AGRS called **60–90% slower on MLA** vs DeepEP
  decode path (stronger claim; treat as upper envelope, not alliance-pod pin).

### 4. vLLM wide-EP blog (aggregate, multi-factor)

- **Source:** https://blog.vllm.ai/2025/12/17/large-scale-serving.html
- **Result:** ~1.5k → **2.2k tok/s/H200** (**+~47%**). Authors attribute to
  kernel fusion **and** DBO for decode, plus Wide-EP / DeepEP / EPLB stack.
- **Not** an isolated `--enable-dbo` A/B. Use only as ceiling for a full
  recipe, not as DBO+DeepEP alone at fixed seqs=16.
- Qualitative: without DBO, MoE Dispatch/Combine dominates decode traces;
  with DBO, microbatch workers hide all2all behind compute.

### 5. Placement A/B on DeepEP-LL (not backend swap)

- **Source:** vLLM PR #28449 (DeepSeek-R1, H20×16, `deepep_low_latency`,
  max_concurrency=8)
  https://github.com/vllm-project/vllm/pull/28449
- Round-robin expert placement vs linear: **+14.57%** throughput,
  **−13.38%** TPOT. Orthogonal to enabling DeepEP; shows remaining headroom
  once LL backend is on.

---

## What applies to alliance-pod (fixed seqs=16)

1. **Prerequisite:** EP+DP must already be the serve shape. DBO without EP/DeepEP
   is unsupported.
2. **First A/B:** `--all2all-backend deepep_low_latency` alone at seqs=16.
   Budget **~10–15%** output tok/s if startup log still shows default AGRS.
3. **Second A/B:** add `--enable-dbo` + tune `--dbo-decode-token-threshold`
   (try ≤8 if MTP keeps effective tokens near 16). Expect **small additive**
   gain or flat/negative; keep only if tok/s or cold wall improves.
4. **Do not** use high-batch +29% / +47% figures as the fleet planning
   multiplier at seqs=16.
5. **Anti-knob:** `deepep_high_throughput` on a mixed prefill+decode judge
   node (docs: may regress mixed workloads).

Pass criterion (same as `64-flashinfer-moe-kernels.md`): higher effective
decode tok/s **or** lower cold fleet wall at c=32 with identical verdict
fingerprints.

---

## Verdict

**Usable-with-conditions.** Measured decode gains are real but
**batch-regime dependent**.

- Literature peak (bs≥32, EP-bound): **~20–35% tok/s** for DeepEP-LL + DBO
  vs weak all2all / no overlap.
- **This corpus (fixed seqs=16):** plan **~12% tok/s** (~10–15% band);
  attribute most of it to `deepep_low_latency`, treat `--enable-dbo` as a
  measured optional additive.
