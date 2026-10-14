# 10 - KV-Cache-Preemption-Auditor

**Verdict:** ruled-out — V4-Pro's hybrid CSA/HCA + fp8 KV leaves ~100+ GiB headroom on 8×H200 at 0.95 util; 32 concurrent 3k–100k-token prompts need ~15 GiB peak, far below pool capacity, so preemption/recompute thrashing cannot explain the +57% wall-time regression.
**Confidence:** high

## The math (HBM budget, KV bytes/token, capacity at 16 vs 32 seqs)

### HBM budget (8× H200 SXM, `--gpu-memory-utilization 0.95`)

| Item | Calculation | Result |
|------|-------------|--------|
| Raw HBM | 8 × 141 GiB | **1,128 GiB** |
| Usable budget | 1,128 × 0.95 | **1,071 GiB** |
| V4-Pro weights (FP4 MoE + FP8 dense) | Published deploy guides: ~862 GiB (Lushbinary) to ~960 GiB (vLLM GB200 recipe) | **862–960 GiB** |
| Remaining for activations + KV | 1,071 − 862 … 1,071 − 960 | **111–209 GiB** |

Per-GPU equal split (TP8+EP, 8 ranks): ~108–120 GiB weights/GPU on 133.95 GiB budget (141 × 0.95). After `profile_run` activation peak at `--max-model-len 393216`, expect **~15–25 GiB KV pool per GPU → ~120–200 GiB cluster KV pool**. Sources: [Lushbinary self-hosting guide](https://lushbinary.com/blog/deepseek-v4-self-hosting-guide-vllm-hardware-deployment/), [vLLM DeepSeek-V4-Pro recipe](https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro), [vLLM memory profiling discussion](https://discuss.vllm.ai/t/max-model-len-vs-gpu-memory-usage/2724/2).

### KV bytes per token (V4-Pro, `--kv-cache-dtype fp8`, MLA lineage)

DeepSeek-V4 is **not** classic per-layer MHA KV. It uses shared-KV with CSA (4× seq compression + sparse indexer) and HCA (128× seq compression), plus 128-token SWA and fp4 indexer cache. vLLM appendix arithmetic at **1M tokens, bf16**:

- V3.2 MLA stack: **83.9 GiB** / sequence ([vLLM V4 blog appendix](https://github.com/vllm-project/vllm-project.github.io/blob/main/_posts/2026-04-24-deepseek-v4.md))
- V4-Pro hybrid (30× CSA + 31× HCA): **9.62 GiB** / sequence bf16 — **8.7× smaller**
- With `--kv-cache-dtype fp8` + fp4 indexer cache: **~2× further reduction → ~4.8 GiB / sequence at 1M tokens** (same blog, §"Running DeepSeek V4")

**At workload-relevant 100k tokens** (user prompt ceiling), scaling vLLM's layer formulas (n = 100,000):

```
c4a layer (×30):  (128 + n/4)×1024 + (n/4)×256  ≈ 30.7 MiB/layer  → 919 MiB
c128a layer (×31): (128 + n/128)×1024            ≈ 0.89 MiB/layer  →  28 MiB
bf16 total ≈ 0.93 GiB/seq  →  fp8/fp4 ≈ 0.47 GiB/seq
```

Effective **~4.9 KiB/token** at 100k (sublinear vs raw MLA's 656 B/token/layer × 61 ≈ 40 KiB/token for V3.2 fp8). V4's sequence-dimension compression dominates; the "KV pressure" hypothesis is structurally weak for this model class ([arXiv:2606.19348](https://arxiv.org/html/2606.19348): 10% of V3.2 KV at 1M; [HuggingFace V4 blog](https://huggingface.co/blog/deepseekv4): ~2% of bf16 GQA).

Five cache kinds (c4a main, c128a main, SWA, CSA indexer, compressor state) share three page-size buckets (1,728 / 8,640 / 37,440 B per 256-token logical block); block accounting at 100k native tokens ≈ **0.54 GiB/seq** — consistent with the analytic estimate above.

### Peak KV demand: 16 vs 32 slots (identical client c=32)

| Scenario | Per-seq KV (fp8, 100k prompt + 2k decode) | Concurrent in vLLM | Peak KV |
|----------|-------------------------------------------|--------------------|---------|
| `--max-num-seqs 16` | ~0.47 GiB | 16 running, 16 queued | **~7.5 GiB** |
| `--max-num-seqs 32` | ~0.47 GiB | 32 running | **~15 GiB** |
| Stress (all 32 at 100k + 4k out) | ~0.50 GiB | 32 | **~16 GiB** |
| Theoretical max (32 × 393216 tokens) | ~1.85 GiB | 32 | **~59 GiB** |

Even the theoretical max uses **~30–55%** of a pessimistic 111 GiB KV pool. User prompts cap at **100k**, not 393216. **Headroom ratio at 32 slots: ~7–13×** above measured peak.

### Does `--max-num-seqs 32` with `--max-model-len 393216` shrink startup per-seq budget?

**No — not via KV preallocation.** vLLM startup flow ([GitHub #10110](https://github.com/vllm-project/vllm/discussions/10110)):

1. `profile_run` at `max_model_len` measures **activation peak** (no permanent KV).
2. KV pool = `(total × gpu_memory_utilization) − weights − activation_peak`.
3. Logs `Maximum concurrency for {max_model_len} tokens per request: X` = pool ÷ memory-for-one-max-length sequence.

`max_num_seqs` is a **scheduler batch cap**, not a KV reservation multiplier ([vLLM Discuss #2609](https://discuss.vllm.ai/t/to-understand-max-num-seqs-better/2609); [issue #6641](https://github.com/vllm-project/vllm/issues/6641)). Raising 16→32 does **not** re-profile a smaller KV pool at startup. It may widen CUDA-graph capture sizes ([conserving memory docs](https://docs.vllm.ai/en/latest/configuration/conserving_memory/)), slightly reducing KV pool — secondary, not the 57% regression driver.

The 393216 cap **does** inflate activation profiling vs an 800k native window (vLLM H200 recipe caps at 800k for KV headroom; user runs 393216 for Think Max — [recipes.vllm.ai](https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro)). That is shared by **both** 16- and 32-slot configs; it does not explain the A/B delta.

## Findings

- [HIGH] **KV pool >> peak demand at 32 concurrent long prompts.** Evidence: computed 15 GiB peak (32 × 100k fp8) vs 111–209 GiB pool (table above); vLLM V4 blog: 4.8 GiB/seq at 1M fp8. Impact: KV exhaustion is mathematically implausible as primary cause; no throughput cliff from block exhaustion expected.

- [HIGH] **MLA lineage + V4 compression makes KV a weak hypothesis for this regression.** Evidence: V4 at 1M = 9.62 GiB bf16 vs V3.2 83.9 GiB ([vLLM blog appendix](https://github.com/vllm-project/vllm-project.github.io/blob/main/_posts/2026-04-24-deepseek-v4.md)); FlashMLA 656 B/token applies to V3.x dense MLA decode, not V4's CSA/HCA compressed entries. Impact: reasoning from V3 "656 B/token × 61 layers" overstates V4 pressure by ~8×.

- [HIGH] **vLLM V1 preemption is RECOMPUTE, not SWAP; would log explicitly if firing.** Evidence: [optimization docs](https://docs.vllm.ai/en/stable/configuration/optimization/): `WARNING … Sequence group N is preempted by PreemptionMode.RECOMPUTE mode because there is not enough KV cache space … total_cumulative_preemption_cnt=…`. Impact: if preemption were thrashing, logs/metrics would show rising `total_cumulative_preemption_cnt` and full prompt recomputes on 3k–100k inputs — expensive, but only possible if pool is exhausted (math says it is not).

- [MED] **`max-num-seqs 32` doubles in-flight KV vs 16 but remains in safe zone.** Evidence: 7.5 → 15 GiB peak (computed); MoE weight dominance leaves 111+ GiB KV ([Paralleliq MoE guide](https://www.paralleliq.ai/blog/why-moe-models-break-your-vllm-configuration): tight for V3 671B on 8×H100, but V4 fp4 experts shrink weight footprint ~28% vs pure fp8). Impact: contributing memory-bandwidth contention at most; sibling report `11-moe-batch-scaling.md` identifies expert-union decode cost as primary (+57% matches ~1.6× MoE latency, not 2×+ preemption tax).

- [MED] **Measured regression pattern (692.3 s → 1090.2 s, +57%) fits compute/MoE saturation, not KV cliff.** Evidence: `11-moe-batch-scaling.md` — ELDR paper: active-expert count 16→128 → 4.7× MoE latency at fixed batch; dense-model analogue vLLM #17598: max-num-seqs 16→32 → +14% TPOT only. Impact: MoE EP8 on single node amplifies batch-size sensitivity; wall time grew because decode steps slowed, not because prompts were recomputed from scratch.

- [LOW] **Community H200×8 V4 configs cap `max-num-seqs` at 8, not for KV but for MoE/scheduler stability.** Evidence: [GitHub #42265](https://github.com/vllm-project/vllm/issues/42265) (`--max-num-seqs 8`, `--max-model-len 393216`, `--kv-cache-dtype fp8`); `05a-web-concurrency-knee.md`. Impact: operator's 16 was already aggressive; 32 worsens batch dynamics without hitting KV OOM.

## What would confirm/refute this (specific log line or test)

**Refute (confirm KV preemption as cause):** Pod startup or runtime logs show any of:

```
WARNING … preempted by PreemptionMode.RECOMPUTE mode because there is not enough KV cache space … total_cumulative_preemption_cnt=<monotonically rising, >>0>
```

or Prometheus `vllm:num_preemptions_total` climbing during the 381-paper run at `--max-num-seqs 32`. Re-run one paper with 100k prompt; if wall time includes a full second prefill pass, preemption fired.

**Confirm (rule out KV):** Capture startup line:

```
Maximum concurrency for 393216 tokens per request: X
```

If **X ≥ 32** (expect ~40–80× given math), startup budget allows 32 full-length sequences — preemption at 100k prompts should be zero. A/B the 381-paper batch at `--max-num-seqs 32` with `nvidia-smi`/`vllm` KV block utilization staying **<40%** peak while wall time still ~1090 s → regression is compute/scheduling, not cache.

**Decisive experiment:** Same corpus, client c=32, server `--max-num-seqs 32`, but cap client `max_tokens` prompts to ≤32k (well inside KV comfort). If wall time stays ~1090 s (not ~692 s), KV/preemption is ruled out; MoE batch scaling stands.
