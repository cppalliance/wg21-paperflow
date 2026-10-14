# Web Forager: Client Concurrency Knee for vLLM + DeepSeek-Class MoE

Research date: 2026-07-07. Target stack: vLLM 0.24.0, DeepSeek-V4-Pro, 8×H200, OpenAI-compatible API. Client today: asyncio concurrency=3, ~10.8 s/paper effective.

---

## Finding: vLLM Optimization and Tuning (official docs)

**URL:** https://docs.vllm.ai/en/stable/configuration/optimization/

**Summary:** vLLM V1 uses continuous batching with chunked prefill enabled by default: the scheduler prioritizes all pending **decode** steps before admitting **prefill**, and splits oversized prefills into chunks bounded by `max_num_batched_tokens`. Each scheduler iteration admits at most `max_num_seqs` sequences and `max_num_batched_tokens` total tokens; exceeding KV budget triggers **preemption** (recompute in V1), which the docs warn "can adversely affect end-to-end latency." Tuning guidance: smaller `max_num_batched_tokens` (e.g. 2048) improves inter-token latency; values >8192 favor throughput on large GPUs; decreasing `max_num_seqs` reduces concurrent batch pressure when preemptions appear.

**Relevance:** HIGH

---

## Finding: Why MoE Models Break Your vLLM Configuration Rules (Paralleliq)

**URL:** https://www.paralleliq.ai/blog/why-moe-models-break-your-vllm-configuration

**Summary:** Dense-model concurrency rules do not transfer to DeepSeek-class MoE: all 671B parameters must reside in VRAM even though only ~37B activate per token, leaving almost no KV-cache headroom after weights load. For DeepSeek V3 on **8× H100**, the author recommends `max_num_seqs` of **4–8**, explicitly *not* the 32–64 you'd use for a dense 7B model; setting it higher "will immediately OOM." At long context (1M tokens), a single sequence can consume the entire remaining KV budget. Recommended starting config: `--gpu-memory-utilization 0.80 --max-num-seqs 8 --max-model-len 32768` with expert parallelism.

**Relevance:** HIGH

---

## Finding: DeepSeek-V4-Pro on H200×8 — production config dump (GitHub #42265)

**URL:** https://github.com/vllm-project/vllm/issues/42265

**Summary:** A reported production deployment of **DeepSeek-V4-Pro (fp4+fp8 mixed) on NVIDIA H200×8** runs vLLM 0.20.2 with `--tensor-parallel-size 8 --max-num-seqs 8 --max-num-batched-tokens 8196 --max-model-len 393216 --kv-cache-dtype fp8 --gpu-memory-utilization 0.98 --enable-chunked-prefill`. This is the closest public H200×8 + DeepSeek-V4 config with explicit concurrency caps; it independently corroborates the MoE guidance of capping at **8 concurrent sequences**, not 32–64.

**Relevance:** HIGH

---

## Finding: max-num-seqs queue behavior (vLLM Discuss)

**URL:** https://discuss.vllm.ai/t/to-understand-max-num-seqs-better/2609

**Summary:** Community maintainer clarification: `max-num-seqs` is the maximum number of **sequences (requests)** processed in a single scheduler iteration, independent of which client sent them. If 6 users each send 1 request and `max-num-seqs=6`, all 6 run concurrently; a 7th waits in the **waiting queue** until a running slot frees. This limit operates alongside `max-num-batched-tokens`: if token budget is exhausted first, requests are chunked (with chunked prefill) or deferred even when sequence slots remain. Client-side concurrency above `max-num-seqs` therefore adds queue depth, not GPU parallelism.

**Relevance:** HIGH

---

## Finding: Continuous batching p99 latency trace (Llama 70B, 4×H100)

**URL:** https://dev.to/marcuswwchen/continuous-batching-wrecked-our-p99-latency-heres-the-trace-42d1

**Summary:** Production case study on vLLM 0.7 with Llama 3.3 70B on 4×H100: enabling continuous batching cut p50 (340→190 ms) but **p99 spiked 1.2→9.8 s** because long prefills blocked decodes in the same forward pass; `time_per_output_token` widened from 32→380 ms. Fix: chunked prefill + `max_num_batched_tokens=4096`, `max_num_seqs=96`; attempting to raise `max_num_seqs` to **256 made things worse** (KV pressure, eviction churn). Final config recovered p99 to 1.4 s at ~4,310 tok/s (vs 4,820 naive CB). Illustrates the latency-collapse mechanism when concurrency/KV pressure exceeds what the scheduler can absorb.

**Relevance:** MED

---

## Finding: DeepSeek V3.2 concurrency sweep (8× MI325X, vLLM 0.14.1)

**URL:** https://docs.vultr.com/inference-cookbook/rocm/benchmarks/stress-testing/deepseek-v3-2

**Summary:** Vultr stress-tested DeepSeek-V3.2 (685B MoE, FP8, TP=8) on **8× MI325X (256 GB each, 2 TB total)** with `vllm bench serve`. Throughput scaled from 461 tok/s at c=5 to 7,266 tok/s at c=200; p99 latency rose modestly (8→14 s). Saturation testing peaked at **500 concurrent** (15,343 tok/s) before plateau at 750. Recommended tiers: low-latency c=5–10, balanced c=25–50, high-throughput c=100–200. **Caveat:** AMD ROCm hardware with 2 TB aggregate VRAM — not directly comparable to H200×8 (~1.1 TB) with tighter MoE weight footprint; shows MoE can scale far beyond 8–64 *when* VRAM headroom is large, but does not contradict the 4–8 `max-num-seqs` cap on memory-constrained H200 deployments.

**Relevance:** MED
