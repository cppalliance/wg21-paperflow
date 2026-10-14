# 40 — vLLM DeepSeek MoE serving recipe (single H200 node)

**Date:** 2026-07-24  
**Scope:** Exact recommended CLI flags from official vLLM docs/recipes for DeepSeek MoE on **one H200 node (8×141 GB)**. Not one GPU: full V3 / V4-Pro do not fit on a single H200 card.

**Repo clone:** skipped (`research/repos/` empty; docs/recipes pages sufficient).

---

## Hardware reading

vLLM’s “H200” DeepSeek recipes mean **8 GPUs on one node**, not TP=1 on one card.

| Model family | Official H200 target | Preferred parallel mode |
|---|---|---|
| DeepSeek-V3 / R1 | 8×H200 FP8 | DP8+EP (or TP8+EP) |
| DeepSeek-V3.2-Exp | 8×H200 | **DP8+EP** (TP=1); TP8 fallback |
| DeepSeek-V4-Pro | 8×H200 verified | **DP8+EP** recommended; verified UI also shows TP8+EP |
| DeepSeek-V4-Flash | H200 verified | **DP4+EP** (4 of 8 GPUs) for non-PD; TP8 optional |

---

## Flag lists (exact)

### A) DeepSeek-V3 single-node EP (docs; H200/H20 node)

Source: Expert Parallel Deployment.

```bash
vllm serve deepseek-ai/DeepSeek-V3-0324 \
  --tensor-parallel-size 1 \
  --data-parallel-size 8 \
  --enable-expert-parallel
```

**Flags:** `--tensor-parallel-size 1`, `--data-parallel-size 8`, `--enable-expert-parallel`

Optional EPLB on same shape:

```bash
vllm serve deepseek-ai/DeepSeek-V3-0324 \
  --tensor-parallel-size 1 \
  --data-parallel-size 8 \
  --enable-expert-parallel \
  --enable-eplb \
  --eplb-config '{"window_size":1000,"step_interval":3000,"num_redundant_experts":2,"log_balancedness":true}'
```

**Extra flags:** `--enable-eplb`, `--eplb-config …`  
**Optional advanced:** `--enable-dbo`, `--async-scheduling`, `--all2all-backend deepep_low_latency` / `deepep_high_throughput` (multi-node / PD)

### B) DeepSeek-V3 / R1 recipe — 8×H200 FP8

Source: DeepSeek-V3 (R1) Usage Guide.

**TP+EP (low latency / low load):**

```bash
vllm serve deepseek-ai/DeepSeek-R1-0528 \
  --trust-remote-code \
  --tensor-parallel-size 8 \
  --enable-expert-parallel
```

**Flags:** `--trust-remote-code`, `--tensor-parallel-size 8`, `--enable-expert-parallel`

**DP+EP (high load):**

```bash
vllm serve deepseek-ai/DeepSeek-R1-0528 \
  --trust-remote-code \
  --data-parallel-size 8 \
  --enable-expert-parallel
```

**Flags:** `--trust-remote-code`, `--data-parallel-size 8`, `--enable-expert-parallel`

### C) DeepSeek-V3.2-Exp — 8×H200 (recommended EP/DP)

Source: DeepSeek-V3.2-Exp Usage Guide. Kernels optimized for TP=1 → prefer DP=8, EP=8, TP=1.

```bash
vllm serve deepseek-ai/DeepSeek-V3.2-Exp -dp 8 --enable-expert-parallel
```

**Flags:** `-dp 8` (= `--data-parallel-size 8`), `--enable-expert-parallel`

Fallback:

```bash
vllm serve deepseek-ai/DeepSeek-V3.2-Exp -tp 8
```

**Flags:** `-tp 8` (= `--tensor-parallel-size 8`)

**Env (optional):** `VLLM_USE_DEEP_GEMM=0` (disable MoE DeepGEMM path / skip long warmup; some H20 reports better perf)

### D) DeepSeek-V4-Pro — H200 (primary for this corpus)

#### D1) Recommended deployment text (H200 8×): DP+EP

Source: recipes page “Recommended deployments”.

- `--data-parallel-size 8`
- `--enable-expert-parallel` (MoE EP strategy)
- `--max-model-len 800000` (800K cap for KV headroom when dense params are replicated across ranks)

Plus V4-required parsers from the same recipe family:

- `--trust-remote-code`
- `--kv-cache-dtype fp8`
- `--block-size 256`
- `--tokenizer-mode deepseek_v4`
- `--tool-call-parser deepseek_v4`
- `--enable-auto-tool-choice`
- `--reasoning-parser deepseek_v4`

**Constructed recommended H200 DP+EP line (docs text + V4 base args):**

```bash
vllm serve deepseek-ai/DeepSeek-V4-Pro \
  --trust-remote-code \
  --kv-cache-dtype fp8 \
  --block-size 256 \
  --enable-expert-parallel \
  --data-parallel-size 8 \
  --max-model-len 800000 \
  --tokenizer-mode deepseek_v4 \
  --tool-call-parser deepseek_v4 \
  --enable-auto-tool-choice \
  --reasoning-parser deepseek_v4
```

#### D2) Verified-on-H200 command block (recipes UI default; TP+EP)

Source: https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro (“Verified on NVIDIA H200”).

```bash
vllm serve deepseek-ai/DeepSeek-V4-Pro \
  --trust-remote-code \
  --kv-cache-dtype fp8 \
  --block-size 256 \
  --enable-expert-parallel \
  --tensor-parallel-size 8 \
  --max-model-len 200000 \
  --gpu-memory-utilization 0.95 \
  --max-num-seqs 16 \
  --max-num-batched-tokens 16384 \
  --no-enable-flashinfer-autotune \
  --compilation-config '{"mode": 0, "cudagraph_mode": "FULL_DECODE_ONLY"}' \
  --tokenizer-mode deepseek_v4 \
  --tool-call-parser deepseek_v4 \
  --enable-auto-tool-choice \
  --reasoning-parser deepseek_v4
```

**Exact flag list (D2):**

1. `--trust-remote-code`
2. `--kv-cache-dtype fp8`
3. `--block-size 256`
4. `--enable-expert-parallel`
5. `--tensor-parallel-size 8`
6. `--max-model-len 200000`
7. `--gpu-memory-utilization 0.95`
8. `--max-num-seqs 16`
9. `--max-num-batched-tokens 16384`
10. `--no-enable-flashinfer-autotune`
11. `--compilation-config '{"mode": 0, "cudagraph_mode": "FULL_DECODE_ONLY"}'`
12. `--tokenizer-mode deepseek_v4`
13. `--tool-call-parser deepseek_v4`
14. `--enable-auto-tool-choice`
15. `--reasoning-parser deepseek_v4`

**Extra install note (recipe):** DeepGEMM via `tools/install_deepgemm.sh`.

### E) DeepSeek-V4-Flash — H200-relevant

Recommended non-disaggregated: **DP+EP with `--data-parallel-size 4`** (4 of 8 H200 GPUs). Blog quickstart (4×B200/B300; same flag shape):

```bash
# docker image example from vLLM blog; flags are the recipe
vllm serve deepseek-ai/DeepSeek-V4-Flash \
  --trust-remote-code \
  --kv-cache-dtype fp8 \
  --block-size 256 \
  --enable-expert-parallel \
  --data-parallel-size 4 \
  --compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE", "custom_ops":["all"]}' \
  --attention_config.use_fp4_indexer_cache=True \
  --tokenizer-mode deepseek_v4 \
  --tool-call-parser deepseek_v4 \
  --enable-auto-tool-choice \
  --reasoning-parser deepseek_v4
```

**Flags:** `--trust-remote-code`, `--kv-cache-dtype fp8`, `--block-size 256`, `--enable-expert-parallel`, `--data-parallel-size 4`, `--compilation-config …`, `--attention_config.use_fp4_indexer_cache=True` (or `True`), `--tokenizer-mode deepseek_v4`, `--tool-call-parser deepseek_v4`, `--enable-auto-tool-choice`, `--reasoning-parser deepseek_v4`

---

## Compact “use this on 8×H200” cheat sheet

| Goal | Model | Core flags |
|---|---|---|
| Official EP example | V3-0324 | `--tensor-parallel-size 1 --data-parallel-size 8 --enable-expert-parallel` |
| V3/R1 high load | R1-0528 | `--trust-remote-code --data-parallel-size 8 --enable-expert-parallel` |
| V3/R1 low latency | R1-0528 | `--trust-remote-code --tensor-parallel-size 8 --enable-expert-parallel` |
| V3.2-Exp recommended | V3.2-Exp | `-dp 8 --enable-expert-parallel` |
| **V4-Pro H200 recommended** | V4-Pro | `--enable-expert-parallel --data-parallel-size 8 --max-model-len 800000` (+ V4 parsers / fp8 KV / block 256) |
| **V4-Pro H200 verified block** | V4-Pro | full D2 list above (TP8+EP, max-model-len 200000, …) |

---

## URLs

| Resource | URL |
|---|---|
| Expert Parallel Deployment (latest) | https://docs.vllm.ai/en/latest/serving/expert_parallel_deployment/ |
| Expert Parallel Deployment (stable) | https://docs.vllm.ai/en/stable/serving/expert_parallel_deployment/ |
| DeepSeek-V3 / R1 recipe | https://docs.vllm.ai/projects/recipes/en/latest/DeepSeek/DeepSeek-V3.html |
| DeepSeek-V3.1 recipe | https://docs.vllm.ai/projects/recipes/en/latest/DeepSeek/DeepSeek-V3_1.html |
| DeepSeek-V3.2-Exp recipe | https://docs.vllm.ai/projects/recipes/en/latest/DeepSeek/DeepSeek-V3_2-Exp.html |
| DeepSeek-V4-Pro recipe | https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro |
| DeepSeek-V4-Flash recipe | https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Flash |
| DeepSeek V4 blog quickstart | https://vllm.ai/blog/2026-04-24-deepseek-v4 |
| Wide-EP / H200 tok/s blog | https://vllm.ai/blog/2025-12-17-large-scale-serving |

---

## Note for cold-run-10min

This corpus targets **DeepSeek-V4-Pro on `h200x8`**. Prefer **D1 (DP8+EP, `--max-model-len 800000`)** as the recipe-stated H200 recommendation; keep **D2** as the verified-on-H200 CLI snapshot if matching the recipes UI block byte-for-byte.
