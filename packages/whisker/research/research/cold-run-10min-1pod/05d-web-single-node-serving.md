# 05d — Web + vLLM recipes: single-node 8×H200, max-num-seqs=16, short JSON

**Query:** Maximize **output tok/s** for DeepSeek-V4-Pro on **ONE** 8×H200
node with **`--max-num-seqs 16` pinned**, workload ≈ short structured JSON
(~50–300 output tokens). Sources: vLLM recipes YAML, blogs, docs, GitHub
issues/forums. Evidence cards only; ranking is ops-flag priority for this
shape (not dual-pod, not raising slots).

**Hard pins (do not contradict without new evidence):**
- `--max-num-seqs 16` (recipe hopper override + measured 16→32 wall +57%).
- Single node only (`alliance-pod`). No twin V4-Pro.
- Short OSL (~50–300 tok JSON). Prefer decode/ITL levers; MTP k must be
  validated against short-OSL regressions.

**Prior corpus (cite, do not rediscover):**
`research/cold-run-10min/05a-web-deepseek-vllm.md`,
`research/cold-run-10min/26-server-ops-checklist.md`,
`research/tapetum-llm-speedup/40-server-flag-auditor.md`.

---

## Official hopper pin (source of truth)

From `vllm-project/recipes` `models/deepseek-ai/DeepSeek-V4-Pro.yaml`
(fetched 2026-07-24, `date_updated: 2026-07-10`):

**Base (all hardware):**
- `--trust-remote-code`
- `--kv-cache-dtype fp8`
- `--block-size 256`
- min vLLM `0.20.0`; DeepGEMM install for FP8 MoE kernels

**Hopper / H200 `hardware_overrides`:**
```
--max-model-len 200000
--gpu-memory-utilization 0.95
--max-num-seqs 16
--max-num-batched-tokens 16384
--no-enable-flashinfer-autotune
--compilation-config '{"mode": 0, "cudagraph_mode": "FULL_DECODE_ONLY"}'
```

**Strategy note:** YAML `default_strategy: single_node_tep` (TP+EP) with
strategy override
`compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE","custom_ops":["all"]}'`.
Guide text still recommends H200 **DP+EP** (`--data-parallel-size 8` +
`--enable-expert-parallel`). Both are single-node 8-GPU; TEP is the recipe
default, DEP is the prose recommendation and matches several H200 issue
repros.

**Spec decoding (opt-in feature, default mode MTP):**
```
--speculative-config '{"method":"mtp","num_speculative_tokens":2}'
```

**Parsers (correctness / retry avoidance, not primary tok/s):**
`--tokenizer-mode deepseek_v4`, `--reasoning-parser deepseek_v4`,
`--tool-call-parser deepseek_v4`, `--enable-auto-tool-choice`.

---

## Finding cards

### 1. Hopper recipe is already a max-num-seqs=16 short-batch profile

- **Title:** DeepSeek-V4-Pro.yaml (hopper override)
- **URL:** https://github.com/vllm-project/recipes/blob/main/models/deepseek-ai/DeepSeek-V4-Pro.yaml
- **Summary:** H200 override explicitly pins `max-num-seqs=16`,
  `max-num-batched-tokens=16384`, `gpu-memory-utilization=0.95`,
  `max-model-len=200000` (KV headroom with ~960 GB mixed weights),
  `FULL_DECODE_ONLY` cudagraphs, flashinfer autotune off. This is the
  closest first-party recipe to our constraint. Guide prose still mentions
  `--max-model-len 800000`; YAML hopper value is **200000**.
- **Relevance:** CRITICAL
- **Tok/s angle:** At fixed S=16, MBT 16384 + decode CUDA graphs are the
  recipe's throughput knobs; concurrency is intentionally not the knob.

### 2. H200 / H20 field configs converge on DP8+EP + FP8 KV + graphs

- **Title:** [Bug] h200 deepseekv4 pro mtp (#41483)
- **URL:** https://github.com/vllm-project/vllm/issues/41483
- **Summary:** Operator launch on H200 used
  `--enable-expert-parallel --data-parallel-size 8 --kv-cache-dtype fp8
  --block-size 256 --gpu-memory-utilization 0.95
  --compilation-config '{"mode":0,"cudagraph_mode":"FULL_DECODE_ONLY"}'
  --speculative-config '{"method":"mtp","num_speculative_tokens":1}'`
  plus `--no-enable-flashinfer-autotune`. MTP on early 0.20.0 was broken;
  v0.20.1 + patches restored MTP. Note their `max-num-seqs 512` is a
  **different** concurrency regime than our pin; keep their flag set for
  topology/kernels, not their seq count.
- **Relevance:** HIGH

### 3. Single-node H20 forum: MTP=1 ≈ +50–75% TPS

- **Title:** DEEPSEEK-V4-PRO ON H20-141G*8 SINGLE NODE (recipes#390)
- **URL:** https://github.com/vllm-project/recipes/issues/390
- **Summary:** On 8×H20-141G, operator report: **without MTP ≈40 TPS;
  MTP=1 ≈60–70 TPS**. MTP=2 hit DeepGEMM `next_n == 1 or next_n == 2`
  assert on some images until deep_gemm/vLLM updates. DEP=8 spawns multiple
  API servers (stats in `/metrics`, optional `--api-server-count=1`).
- **Relevance:** CRITICAL for short-decode tok/s
- **Conflict note:** Recipe default is MTP k=2. Short JSON (~50–300 tok)
  and prior GB300 short-OSL evidence favor **start at k=1**, A/B k=2 only
  if acceptance stays high and TPOT drops.

### 4. Short OSL can make MTP a net loss (do not blind-enable k=2)

- **Title:** DeepSeek-V3.2 on GB300 (MTP section) + prior 05a card
- **URL:** https://vllm.ai/blog/2026-02-13-gb300-deepseek
- **Summary:** MTP wins when decode is long enough to amortize draft/verify;
  mixed short-output (e.g. OSL≈64) can be **worse than MTP-off**. Our
  ~50–300 tok JSON sits near that edge. Recipe still advertises MTP for
  “low latency & small batch.”
- **Relevance:** HIGH
- **Ops implication:** Rank MTP high but with **k=1 first**; measure
  `spec_decode` accept rate under c=16.

### 5. Decode CUDA graphs are mandatory for production decode tok/s

- **Title:** Recipe strategy overrides + HF serving notes
- **URL:** https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro
- **Summary:** Hopper default uses `FULL_DECODE_ONLY`; TEP/DEP strategy
  overrides prefer `FULL_AND_PIECEWISE` + `custom_ops:["all"]`. Community
  NVFP4/MTP notes warn: **no `--enforce-eager`** if you want decode
  throughput; cold start 12–15 min for compile + cudagraph capture is
  expected. DBO (below) also requires full CUDA graphs.
- **Relevance:** HIGH

### 6. DeepEP low_latency + DBO for decode-dominated MoE

- **Title:** Dual Batch Overlap (vLLM docs) + Expert Parallel Deployment
- **URL:** https://docs.vllm.ai/en/latest/design/dbo/
- **URL:** https://docs.vllm.ai/en/latest/serving/expert_parallel_deployment/
- **Summary:** For DP+EP, `--enable-dbo` overlaps MoE all-to-all with
  compute. Requires DeepEP installed and
  `--all2all-backend deepep_low_latency` for **decode-primary** workloads
  (use `deepep_high_throughput` for prefill-primary). Thresholds:
  `--dbo-decode-token-threshold`, `--dbo-prefill-token-threshold`. Docs
  note DeepEP HT/LL kernels are tuned for disagg and can hurt mixed
  workloads. Forum thread reports single-node multi-GPU DBO attempts
  (DeepEP install + `deepep_low_latency`) with mixed success historically.
- **Relevance:** MED–HIGH for tok/s if already on DEP; lower priority if
  stuck on TEP without DeepEP.
- **Caveat at S=16:** DBO microbatching needs enough tokens in the
  decode-only batch and uniform DP-rank agreement; at 16 concurrent short
  gens it may often sit under threshold → measure before counting as a win.

### 7. Chunked prefill + MBT 16384 at S=16

- **Title:** Optimization and Tuning — Chunked Prefill
- **URL:** https://docs.vllm.ai/en/latest/configuration/optimization/
- **Summary:** V1 prioritizes decode, then fills remaining
  `max_num_batched_tokens` with prefill. Larger MBT → better TTFT /
  prefill packing; smaller → better ITL. Recipe hopper chooses **16384**
  with **seqs=16**. For short JSON decode, MBT is still the lever that
  keeps long judge prefills from starving the 16 decode slots when default
  is 8192.
- **Relevance:** HIGH (effective tok/s under load, not solo TPOT)

### 8. Wide-EP / EPLB are multi-node tok/s story, not our S=16 single node

- **Title:** vLLM Large Scale Serving: DeepSeek @ 2.2k tok/s/H200
- **URL:** https://vllm.ai/blog/2025-12-17-large-scale-serving
- **Summary:** 2.2k tok/s/H200 is a **wide-EP multi-node** result (DeepEP,
  DBO, EPLB). Useful as kernel/backend inventory (`--enable-dbo`,
  `--enable-eplb`, DeepEP backends), not as a claim that one 8×H200 at
  S=16 reaches that number.
- **Relevance:** MED (flag names); LOW (magnitude expectations)

### 9. Prefill planning / image maturity

- **Title:** [Perf] Optimize DSv4 prefill chunk planning (#45061)
- **URL:** https://github.com/vllm-project/vllm/pull/45061
- **Summary:** ~4% E2E throughput from better DSv4 prefill chunk packing;
  bench command shows DP8+EP, FP8 KV, block 256, MTP, and
  `FULL_AND_PIECEWISE` graphs. Reinforces staying on current vLLM/DeepSeek
  images rather than hunting exotic flags.
- **Relevance:** MED (image/version > exotic knobs)

---

## Composite single-node launch sketch (S=16, short JSON)

TEP-shaped (recipe default), tok/s-oriented deltas called out:

```bash
vllm serve deepseek-ai/DeepSeek-V4-Pro \
  --trust-remote-code \
  --kv-cache-dtype fp8 \
  --block-size 256 \
  --enable-expert-parallel \
  --tensor-parallel-size 8 \
  --max-num-seqs 16 \
  --max-num-batched-tokens 16384 \
  --max-model-len 200000 \
  --gpu-memory-utilization 0.95 \
  --no-enable-flashinfer-autotune \
  --compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE","custom_ops":["all"]}' \
  --speculative-config '{"method":"mtp","num_speculative_tokens":1}' \
  --tokenizer-mode deepseek_v4 \
  --reasoning-parser deepseek_v4 \
  --tool-call-parser deepseek_v4 \
  --enable-auto-tool-choice
```

DEP-shaped alternative (guide / many H200 issues): replace TP8 with
`--data-parallel-size 8`, add `--all2all-backend deepep_low_latency` and
optionally `--enable-dbo` if DeepEP is installed and decode batch size
clears DBO thresholds. Do **not** raise `--max-num-seqs`.

Client-side (not an ops flag, but dominates short JSON wall): Non-think /
disable thinking for unit-check JSON so OSL stays in the 50–300 band.

---

## Top 5 ops flags (ranked for output tok/s @ S=16, short JSON)

| Rank | Flag | Why it ranks here | Evidence | Caution |
|---:|---|---|---|---|
| **1** | `--speculative-config '{"method":"mtp","num_speculative_tokens":1}'` | Direct decode multiplier on 8×H20/H200-class nodes (~40→60–70 TPS reported) | recipes#390; recipe MTP feature; #41483 | Start **k=1**; k=2 is recipe default but short OSL can regress (GB300 short-OSL note). Need accept-rate A/B. |
| **2** | `--compilation-config` with decode CUDA graphs (`FULL_DECODE_ONLY` hopper, or `FULL_AND_PIECEWISE`+`custom_ops:["all"]` for TEP/DEP) | Removes decode launch overhead; required for DBO graphs; recipe + community “no enforce-eager” | Recipe YAML; DBO docs | Cold start 10–15 min; never pair with `--enforce-eager` for tok/s. |
| **3** | `--max-num-batched-tokens 16384` | Co-tuned with S=16 in hopper recipe; under load protects decode slots from default-8192 prefill starvation → higher effective tok/s | Recipe hopper; vLLM optimization docs | Pure solo TPOT may not move; fleet /metrics under c=16 is the test. |
| **4** | Topology: `--enable-expert-parallel` + (TEP `TP=8` **or** DEP `DP=8`) | Official single-node H200 path; EP shards MoE, keeps KV/attention efficient vs naive layouts | Recipe guide + YAML; #41483; V4 blog | Do not chase wide-EP/multi-node for S=16. DEP needs `/metrics` (multi API server). |
| **5** | `--all2all-backend deepep_low_latency` (+ `--enable-dbo` if DEP+DeepEP) | Decode-primary MoE all-to-all path; DBO overlaps comm/compute | EP deployment docs; DBO docs; 2.2k blog (flag inventory) | Needs DeepEP; DBO thresholds may not fire at S=16 short gens; mixed prefill+decode can prefer HT backend or DBO off. |

**Honorable (tok/s-adjacent, often already on or correctness):**
- `--kv-cache-dtype fp8` + `--block-size 256` + `--gpu-memory-utilization 0.95` + capped `--max-model-len` (200k hopper): KV headroom so 16 seqs stay resident.
- `--enable-prefix-caching` + retention env (when build has DSv4 APC fix): TTFT / effective throughput on shared judge prefixes, not raw decode tok/s.
- `--long-prefill-token-threshold 8192`: co-tune with MBT for long judge prefills.
- Parsers (`deepseek_v4`): prevent JSON/reasoning retries that destroy effective tok/s.

**Explicit anti-levers for this query:**
- Raising `--max-num-seqs` above 16.
- Blind MTP k=2 on short JSON without accept-rate proof.
- `--enforce-eager`.
- Expecting multi-node wide-EP 2.2k tok/s/H200 numbers on one pod.

---

## False-pass / false-fail

**False-pass:** Enable MTP k=2 because the recipe defaults to it; `/metrics`
shows speculative activity but short JSON TPOT rises and schema retries
increase → wall worse while “tok/s” looks busy.

**False-fail:** Enable DBO+DeepEP on TEP-only or under threshold decode
batches; no gain → conclude “all recipe flags useless” and skip MBT 16384
+ CUDA graphs, which are independent wins.

---

## References

- https://github.com/vllm-project/recipes/blob/main/models/deepseek-ai/DeepSeek-V4-Pro.yaml
- https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro
- https://vllm.ai/blog/2026-04-24-deepseek-v4
- https://vllm.ai/blog/2025-12-17-large-scale-serving
- https://docs.vllm.ai/en/latest/design/dbo/
- https://docs.vllm.ai/en/latest/serving/expert_parallel_deployment/
- https://github.com/vllm-project/vllm/issues/41483
- https://github.com/vllm-project/recipes/issues/390
- https://github.com/vllm-project/vllm/pull/45061
- https://discuss.vllm.ai/t/has-anyone-successfully-run-dbo-in-a-single-node-multi-card-environment/2054
