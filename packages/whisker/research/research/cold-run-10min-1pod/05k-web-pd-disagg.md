# 05k — Web: Prefill/decode disaggregation for DeepSeek on one 8xH200

**Query:** Is P/D (prefill–decode) disaggregation useful for a decode-bound,
short-output DeepSeek judge fleet on a **single** 8×H200 node, or waste?

**Corpus constraint:** Only `alliance-pod` (no twin DeepSeek). Target: cut
per-call `L` or call count `N` toward cold wall ≤600 s. See `00-baseline.md`.

**Verdict for us: no**

---

## Our workload (settled, not rediscovered)

From `research/tapetum-llm-speedup/SYNTHESIS.md` + this corpus baseline:

| Fact | Value |
|------|------:|
| Pod | DeepSeek-V4-Pro, 8×H200, S_eff=16, client c=32 |
| Per-call wall | ~20 s |
| Phase split (mean) | **5.91 s decode vs 0.46 s prefill** (decode-bound) |
| Pass-path output | ~55 tokens of unused `reasoning` (short OSL; shrinking further) |
| Prompt shape | Long candidate (10–40k tokens), structured short JSON |

PD must beat **aggregated TP8+EP on the same 8 GPUs** under that shape, or it
is out of scope.

---

## Finding cards

### 1. Anyscale: PD loses on short-output workloads (explicit)

- **Title:** Achieving Up to 67% Cost Savings with Prefill-Decode Disaggregation Using Ray + vLLM on AMD MI325X
- **URL:** https://www.anyscale.com/blog/ray-vllm-prefill-decode-disaggregation-amd-mi325x-67-percent-savings
- **Date:** 2026-06-12
- **Summary:** PD’s win is flat TPOT under load; savings compound as
  `TPOT_delta × OSL`. Quote: *“When PD loses: short output. For short-output
  workloads (classification, extraction, short QA), the savings don't
  accumulate enough to justify the complexity. In these cases you should use
  aggregated.”* Also: PD can **hurt TTFT** (KV transfer); aggregated wins when
  TTFT-bound, short OSL, or high cache hit rate.
- **Relevance:** CRITICAL — our judges are classification/extraction-class
  short JSON, not long chat decode.

### 2. Single-node PD demos use models that fit on a GPU subset — not DeepSeek FP8

- **Title:** Next-Level Inference: Why Your Single-Node vLLM Setup Needs Prefill-Decode Disaggregation
- **URL:** https://vllm.ai/blog/2026-04-07-moriio-kv-connector
- **Summary:** 2.5× goodput on **one** 8-GPU MI300X by splitting 4P+4D with
  MORI-IO KV transfer. Benchmark: **Qwen3-235B-A22B-FP8**, ISL=2000 / **OSL=1000**,
  8 req/s. Architecture assumes two instances each on a subset of GPUs.
- **Relevance:** HIGH as mechanism proof; **LOW as portable recipe for us** —
  OSL=1000 is ~20× our pass-path tokens, and Qwen-235B-A22B fits a 4-GPU shard.

### 3. DeepSeek FP8 needs the whole 8×H200 for one replica — no 4P+4D room

- **Title:** deepseek-ai/DeepSeek-V3 \| vLLM Recipes
- **URL:** https://recipes.vllm.ai/deepseek-ai/DeepSeek-V3
- **Summary:** Verified FP8 hardware is **8×H200** with TP8+EP (or DP8+EP).
  Recipe UI lists “Prefill/Decode Disaggregation” as a strategy, but the
  documented disagg path points at **experimental multi-node / GB200 Wide-EP**
  (issue #33583, GB200 blog), not a split of one 8×H200 into P and D replicas.
  Weight footprint ~805 GB FP8; 4×H200 ≈ 564 GB cannot hold a second full FP8
  replica for the other phase.
- **Relevance:** CRITICAL — classic single-node “half the GPUs for decode”
  topology is **not available** for DeepSeek-class FP8 on one node without a
  second node or a quality-changing FP4/INT4 shrink.

### 4. Multi-node DeepSeek PD: latency, not per-GPU throughput; needs ≥2 nodes

- **Title:** awslongs/awsome-distributed-ai — dsv3-uccl-nixl README
- **URL:** https://github.com/awslabs/awsome-distributed-ai/blob/main/3.test_cases/pytorch/vllm/dsv3-uccl-nixl/README.md
- **Summary:** DeepSeek-V3-0324 P/D across **multiple** `p5en.48xlarge`
  (8×H200) nodes; NIXL KV over EFA; DeepEP high-throughput on prefill /
  low-latency on decode. Measured lesson: *“Disaggregation pays off mostly in
  latency, not throughput. Unified has the best tok/s/GPU.”* Knee around
  1P:4D — explicitly multi-node ratios.
- **Relevance:** HIGH — confirms DeepSeek PD is a **cluster** pattern; also
  that unified often wins raw GPU efficiency. Twin-pod / multi-node is
  **forbidden** in this corpus (`00-baseline.md`).

### 5. vLLM Wide-EP blog: PD helps MoE when prefill stalls the EP group

- **Title:** vLLM Large Scale Serving: DeepSeek @ 2.2k tok/s/H200 with Wide-EP
- **URL:** https://vllm.ai/blog/2025-12-17-large-scale-serving
- **Summary:** Prefill can delay an entire expert-parallel group (all ranks
  sync on MoE combine). Disagg lets prefill and decode use different DeepEP
  kernels and removes that stall. Gains shown in **multi-node** Wide-EP /
  llm-d / Dynamo / Ray Serve LLM settings.
- **Relevance:** MED — mechanism is real for **long-prefill + concurrent decode
  under EP**, but our measured prefill is already ~0.46 s vs ~5.91 s decode;
  interference headroom is small relative to decode shrink / call elimination.

---

## Mapping to alliance-pod

| PD claim | Applies here? |
|----------|---------------|
| Isolate decode from prefill interference | Weak: prefill already ~8% of phase time |
| TPOT savings compound over long OSL | No: ~55-token (shrinking) structured outs |
| Split 4P+4D on one 8-GPU node | No: DeepSeek FP8 needs full 8×H200 per replica |
| Multi-node 1P:N D | Forbidden (no twin / no second V4-Pro) |
| Better tok/s/GPU than unified | AWS: unified often **better** on that metric |
| Ops cost (proxy, NIXL/MORI, P:D tune) | High; no payoff path on one pod |

Arithmetic intuition (not a substitute for a bench): even a generous 10 ms/token
TPOT win × 55 tokens ≈ **0.55 s/call**. Against ~20 s/call that is ~3%, and
it assumes a topology we cannot deploy on one FP8 8×H200 without starving
decode GPUs or adding a second node. KV transfer + TTFT tax can erase that.

---

## False-pass hypothesis (why we might wrongly say yes)

Reading the single-node MORI-IO 2.5× headline and assuming it ports to
DeepSeek-V4-Pro judges. That bench is Qwen-235B, OSL=1000, and a 4+4 GPU
split — none of which match alliance-pod.

## False-fail hypothesis (why we might wrongly say no)

If V4-Pro FP8 somehow supports **intra-engine** phase specialization (same
TP8 ranks, no second replica, negligible KV hop) that still cuts decode
stalls under c=32 long-prompt bursts, a narrow flag experiment could show a
few percent. No public DeepSeek-on-one-8×H200 recipe demonstrates that as of
these sources; treat as unproven, not as current plan.

## What would change my mind

1. A measured A/B on **alliance-pod** (or identical V4-Pro 8×H200) showing
   ≥15% drop in per-call wall for tapetum unit-check shapes (long ISL, OSL≤128)
   under S=16 / c=32 with PD vs current aggregated recipe, **without** a second
   node; or
2. Official DeepSeek/vLLM recipe for **single-node** PD that keeps all 8 GPUs
   as one weight replica (not 4+4) with documented short-OSL wins.

Until then: **waste for this fleet.** Prefer decode shrink (verdict-first /
max_tokens / Non-think), call elimination, APC/prefix layout, MTP A/B, dense
offload — levers already in `00-baseline.md` scope.

---

## Bottom line

**Worth for us? no**

P/D disagg is a real multi-node / long-OSL goodput tool. On one DeepSeek FP8
8×H200 running short-output decode-bound judges, it is the wrong topology and
the wrong workload class.
