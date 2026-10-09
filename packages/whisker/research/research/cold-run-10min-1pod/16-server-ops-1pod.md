# 16 - Server Ops Checklist (alliance-pod ONLY, no seq raise)

**Audience:** Sam / RunPod operator  
**Goal:** Cut per-call latency **L** on the single live DeepSeek pod without raising `--max-num-seqs`  
**Constraint:** `--max-num-seqs 16` is settled; 16→32 was **+57% wall** (forbidden). No twin pod.  
**Sources:** `research/cold-run-10min/26-server-ops-checklist.md`, `64-flashinfer-moe-kernels.md`, `05c-web-moe-batching.md`, `05d-web-mtp-specdecode.md`, `research/cold-run-10min-1pod/00-baseline.md`, `research/cold-run-10min/11-wall-arithmetic.md`

**Verdict:** Server-only ops on `alliance-pod` save **~5–9 min** on the raw 3003 s cold baseline and **~3–7 min** on the post-short-circuit wall. They do **not** reach ≤10 min alone; client v11 call cuts and other levers remain mandatory.

---

## Two baselines (do not mix)

| Baseline | Wall (s) | Calls (N) | Use when |
|----------|----------:|----------:|----------|
| **Raw v10 cold fleet** | **3003** | 2284 | Comparing against historical 48 min runs |
| **Post-short-circuit (v11 Tier A+B)** | **~1921** | 1419 | Planning after metadata short-circuit ships (−847 units, −18 escalation) |

Post-short-circuit rebuild (`11-wall-arithmetic.md`): `3003 − 1059 − 23 = 1921 s` before any server **L** cuts or prefix/verdict client levers.

Server ops change **L**, not **N**. Savings scale roughly with surviving call count:

```
savings_post_SC ≈ savings_3003 × (1419 / 2284) ≈ savings_3003 × 0.621
```

---

## Combined server-only ceiling (minutes saved)

All figures are **ops-only** (pod restart / image bump). No whisker deploy. Overlap between decode levers (MTP, CUDA graphs, DeepEP+DBO) is discounted on the additive rows.

### On 3003 s raw baseline

| Envelope | Seconds saved | Minutes saved | Projected wall (s) |
|----------|--------------:|--------------:|-------------------:|
| **Conservative** (recipe bundle, `26`) | **300** | **5.0** | ~2703 |
| **Planning optimistic** (recipe bundle upper, `26`) | **550** | **9.2** | ~2453 |
| **Max optimistic** (recipe + DeepEP/DBO + EPLB, this card) | **~680** | **~11.3** | ~2323 |

**Max optimistic decomposition (3003 s):**

| Bucket | Source | Optimistic (s) | Notes |
|--------|--------|---------------:|-------|
| Recipe bundle (MBT, APC, MTP k=1, CUDA graphs, long-prefill) | `26`, `40` | **550** | Upper bound after ~25% intra-bundle overlap |
| DeepEP low-latency + DBO | `64`, `05c` | **+80** | Incremental after MTP/CUDA overlap; only if startup log shows default all2all |
| Async EPLB | `05c`, `98` | **+50** | Upper end of 5–10% wall if routing skewed; requires KV headroom |
| **Total max optimistic** | | **~680** | Further overlap discount on MoE rows |

FlashInfer fused MoE (`64` Tier B) is **excluded** from max optimistic: not V4-Pro H200 recipe default; can regress TTOT at c=16 (#28882).

### On ~1921 s post-short-circuit wall

| Envelope | Seconds saved | Minutes saved | Projected wall (s) |
|----------|--------------:|--------------:|-------------------:|
| **Conservative** | **~186** | **~3.1** | ~1735 |
| **Planning optimistic** (recipe) | **~342** | **~5.7** | ~1579 |
| **Max optimistic** (recipe + DeepEP/DBO + EPLB) | **~422** | **~7.0** | ~1499 |

Scaling check: `680 × 0.621 ≈ 422 s`; `550 × 0.621 ≈ 342 s`.

Post-short-circuit + max server ops still lands **~25 min**, not 10 min. Compute term alone on 1419 calls @ 16 slots is **1774 s** before **L** cuts (`11-wall-arithmetic.md`).

---

## What ops can change (no code deploy)

| Change class | Examples | Requires |
|---|---|---|
| RunPod template env | `VLLM_PREFIX_CACHE_RETENTION_INTERVAL=32768` | Pod restart |
| vLLM launch flags | MBT, APC, MTP, CUDA graphs, DeepEP, DBO, EPLB, parsers | Pod restart |
| Container image bump | `cppalliance/vllm-openai:v0.24.0+` with **PR #43447** (APC retention) | Pod restart + pull |
| Verification only | `GET /version`, `GET /metrics`, startup log grep | Nothing |

**Not ops-only:** metadata short-circuit, HMAC guard tag, prompt reorder, client concurrency, dual-pod sharding, verdict-first schema.

**Hard anti-knobs (`05c`, `64`, `00-baseline`):**

- Raise `--max-num-seqs` above **16**
- Raise client **c > 32**
- `deepep_high_throughput` on decode-heavy mixed judge node
- MTP **k ≥ 2** on short JSON judge tails (GB300 OSL≈64 cliff, `05d`)
- FlashInfer MoE without fixed-seqs A/B
- APC on pre-#43447 build (0% hits, possible hash overhead)

---

## Pre-flight: confirm build before APC

APC on DeepSeek V4 without retention fix can stay at **0% hits**.

| Check | Pass |
|---|---|
| vLLM build ≥ PR #43447 merge (2026-06-04) | Startup log / `GET /version` |
| `VLLM_PREFIX_CACHE_RETENTION_INTERVAL=32768` | RunPod env or `/server_info` |
| Container includes #43447 | Image tag verified, not assumed |

---

## Operator checklist (ranked by expected cold-run impact)

Run after restart; scrape `/metrics` every 10 s during a fleet load test.

### Tier 1 — Recipe bundle (`26`, highest confidence)

| Rank | Flag / knob | Verify | Pass | Impact on 3003 s (s) |
|------|-------------|--------|------|---------------------:|
| 1 | `--max-num-batched-tokens 16384` | Startup `max_num_batched_tokens=`; `/server_info` | **16384** (implicit default on H200 OPENAI is **8192**) | **100–250** |
| 2 | `--speculative-config '{"method":"mtp","num_speculative_tokens":1}'` | Startup `SpeculativeConfig(method='mtp'...)`; `spec_decode_draft_acceptance_rate` ≥ **70%** | k=**1** only; CUDA-graph decode path on | **100–200** (`05d`: 7–16% fleet if healthy) |
| 3 | `--enable-prefix-caching` + retention env | `/metrics` `prefix_cache_hits/queries` > 0% under load | On + interval **32768** + #43447 | **60–180** server-only static prefix |
| 4 | `--compilation-config '{"mode": 3, "cudagraph_mode": "FULL_DECODE_ONLY"}'` | Startup `compilation_config` / cudagraph metrics | `FULL_DECODE_ONLY` | **50–120** |
| 5 | `--long-prefill-token-threshold 8192` | Startup log | **8192**, co-tuned with MBT 16384 | **30–80** incremental |

**Combined Tier 1 envelope:** **300–550 s** on 3003 s (`26`, overlap-discounted).

### Tier 2 — MoE comm overlap at fixed seqs=16 (`64`, `05c`)

Apply **after** Tier 1 smoke pass. One restart cycle per A/B.

| Rank | Flag / knob | Verify | Pass | Impact on 3003 s (s) |
|------|-------------|--------|------|---------------------:|
| 6 | `--all2all-backend deepep_low_latency` | Startup `all2all_backend=` | Not default `allgather_reducescatter` on decode-heavy node | **30–80** if EP-bound |
| 7 | `--enable-dbo` (+ decode token threshold) | Startup `enable_dbo=True` | Overlap dispatch/combine with compute | **20–60** incremental |
| 8 | `--enable-eplb --eplb-config '{"use_async":true,...}'` | Startup EPLB block | Async only; watch KV at 0.95 util | **20–150** (5–10% wall if skewed, `98`) |

**Do not enable:** `deepep_high_throughput` on this mixed judge workload (`05c` anti-knob).

**Tier 2 incremental (optimistic, after Tier 1 overlap):** **~50–130 s** on 3003 s → **~680 s** ceiling with Tier 1 upper bound.

### Tier 3 — Correctness gates (not throughput; prevent false-fail)

| Flag | Verify | Why |
|------|--------|-----|
| `--tokenizer-mode deepseek_v4` | Startup log | Wrong tokenizer → silent token errors |
| `--reasoning-parser deepseek_v4` | JSON in `content` after thinking | Missing parser → retries / empty JSON masquerading as slowness |
| `--tool-call-parser deepseek_v4` | Startup log | If auto tool choice enabled |

Structured JSON + reasoning + MTP requires vLLM build with reasoning-boundary fixes (`05d`: #44927, #44993 class). Smoke one paper with `--trace` before fleet.

### Keep unchanged (already correct or harmful to touch)

| Knob | Value | Reason |
|------|-------|--------|
| `--max-num-seqs` | **16** | Measured sweet spot; do not raise |
| `--kv-cache-dtype fp8` | fp8 | Already live; **0 s incremental** |
| Chunked prefill | **on** (default) | Do not disable |
| `--enable-ep-weight-filter` | on | Load-time only |
| TP8 + EP topology | as H200SXM | Confirmed 8×H200 (`57-alliance-inventory`) |

---

## Target launch delta (add to H200SXM baseline)

**Keep:** TP8+EP, `--max-num-seqs 16`, `--max-model-len 393216`, `--kv-cache-dtype fp8`, `--gpu-memory-utilization 0.95`, `--enable-ep-weight-filter`.

```bash
# RunPod environment
VLLM_PREFIX_CACHE_RETENTION_INTERVAL=32768

# Container start — Tier 1 (apply together)
--max-num-batched-tokens 16384 \
--enable-prefix-caching \
--tokenizer-mode deepseek_v4 \
--reasoning-parser deepseek_v4 \
--tool-call-parser deepseek_v4 \
--speculative-config '{"method":"mtp","num_speculative_tokens":1}' \
--compilation-config '{"mode": 3, "cudagraph_mode": "FULL_DECODE_ONLY"}' \
--long-prefill-token-threshold 8192

# Tier 2 — A/B after Tier 1 smoke (if startup shows default all2all)
--all2all-backend deepep_low_latency \
--enable-dbo \
--enable-eplb \
--eplb-config '{"window_size":100,"step_interval":1000,"num_redundant_experts":32,"use_async":true}'
```

---

## MTP acceptance gate (`05d`)

| Metric | Pass | Fail action |
|--------|------|-------------|
| `spec_decode_draft_acceptance_rate` | ≥ **70%** | Disable MTP; keep MBT + retention + CUDA graphs |
| Structured JSON validity | ≥ baseline | Revert MTP first; check reasoning-parser + image version |
| k | **1** only on first deploy | k=2 hurts short OSL; recipe k=2 is anti-pattern here |

Greedy/temp=0: healthy k=1 acceptance clusters **80–90%** (PR #12755, GB300 blog). Collapsed **<60%** is a bug/regression class (#33497), not "MTP useless."

---

## Quality / determinism (server flags)

| Lever | Changes outputs? | Ops action |
|---|---|---|
| MBT, APC, CUDA graphs, long-prefill | No (scheduling / KV replay) | Safe |
| MTP k=1 | No (lossless rejection); graph path required | A/B verdict counts |
| DeepEP / DBO / EPLB | Marginal numeric / routing | A/B; async EPLB only |
| FP8 KV | Slight (already live) | Confirm only |

Scheduling-only levers: sidecar byte-diff A/B suffices. Do not raise seqs to "speed up."

---

## Rollout procedure

1. Snapshot current flags (startup log + `/metrics` baseline).
2. Confirm vLLM ≥ PR #43447; bump image if needed.
3. Apply **Tier 1**; restart `alliance-pod` only.
4. Smoke: one paper `whisker-tapetum-llm --trace`; confirm JSON parse, MTP acceptance, prefix hit rate > 0%.
5. Cold fleet 381 papers with metrics scrape; compare wall + sidecar verdict diff.
6. If wall gain ≥ **200 s** and flip budget OK: **Tier 2** A/B on same pod.
7. Revert order on regression: MTP first → CUDA graphs → DeepEP/DBO; keep MBT + retention.

**Log grep:**

```text
max_num_batched_tokens|max_num_seqs|prefix caching|SpeculativeConfig|compilation_config|cudagraph|all2all|enable_dbo|eplb|kv_cache_dtype|tokenizer-mode|reasoning-parser
```

**Metrics:**

```bash
curl -s "$POD/metrics" | rg 'prefix_cache|spec_decode|num_requests_(running|waiting)|kv_cache_usage'
```

---

## False-pass / false-fail traps

**False-pass:** APC enabled on pre-#43447 build → 0% hits → team marks server tuning done while wall unchanged.

**False-fail:** Deploy MTP k=2 on ~55 tok pass-path JSON → overhead dominates → revert entire recipe bundle including beneficial MBT 16384.

**False-fail:** Enable `deepep_high_throughput` on mixed decode/prefill judge node → ITL regression → blame "MoE tuning" and revert DeepEP low-latency that would have helped.

**False-pass:** FlashInfer MoE forced on because blog says so → TTFT regression at c=16 (#28882) while high-concurrency bench looked fine.

---

## Executive summary

| Field | Value |
|-------|-------|
| **Max optimistic server-only minutes saved (3003 s baseline)** | **~11.3 min** (~680 s) |
| **Planning optimistic (recipe bundle only)** | **~9.2 min** (~550 s) |
| **Conservative (recipe bundle)** | **~5.0 min** (~300 s) |
| **Max optimistic on post-short-circuit (~1921 s)** | **~7.0 min** (~422 s) |
| **≤10 min reachable server-only?** | **No** — post-SC + max ops ≈ **~25 min** still |
| **Seq raise required?** | **No** — all levers at `--max-num-seqs 16` |

---

## References

- Recipe checklist: `research/cold-run-10min/26-server-ops-checklist.md`
- DeepEP / FlashInfer: `research/cold-run-10min/64-flashinfer-moe-kernels.md`
- MoE batching mechanisms: `research/cold-run-10min/05c-web-moe-batching.md`
- MTP acceptance / JSON: `research/cold-run-10min/05d-web-mtp-specdecode.md`
- Wall arithmetic: `research/cold-run-10min/11-wall-arithmetic.md`
- 1pod constraint: `research/cold-run-10min-1pod/00-baseline.md`
- Flag audit: `research/tapetum-llm-speedup/40-server-flag-auditor.md`
- MoE serving physics: `research/tapetum-llm-speedup/98-vllm-moe-serving.md`
- H200 template: https://raw.githubusercontent.com/cppalliance/runpod/master/templates/deepseek/H200SXM.txt
- V4-Pro recipe: https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro
