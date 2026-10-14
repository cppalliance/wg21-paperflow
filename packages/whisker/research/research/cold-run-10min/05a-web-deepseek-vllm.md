# 05a — Web forage: DeepSeek-V4-Pro / V4 MoE on vLLM (decode / TTFT)

**Query:** Serving-side optimizations for DeepSeek-V4-Pro (or DeepSeek V4 MoE) on
vLLM that improve decode throughput / TTFT for long-context structured-output
judging workloads.

**Scope:** 2025–2026 web sources (vLLM blog, recipes, docs, guided-decoding
benchmarks). Evidence cards only; no implementation recommendations beyond what
sources state.

**Known negative (do not contradict without evidence):** Raising
`max-num-seqs` 16→32 on their MoE pod slowed cold wall **+57%**
(`slots-32-regression`). Official V4-Pro H200 recipe also pins
`--max-num-seqs 16`.

---

## Finding cards

### 1. Official DeepSeek-V4-Pro recipe pins parsers + max-num-seqs 16

- **Title:** deepseek-ai/DeepSeek-V4-Pro | vLLM Recipes
- **URL:** https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro
- **Summary:** Verified H200 single-node recipe serves V4-Pro with
  `--tokenizer-mode deepseek_v4`, `--reasoning-parser deepseek_v4`,
  `--tool-call-parser deepseek_v4`, `--enable-auto-tool-choice`,
  `--kv-cache-dtype fp8`, `--block-size 256`, `--enable-expert-parallel`,
  `--max-num-seqs 16`, `--max-num-batched-tokens 16384`, and
  `cudagraph_mode: FULL_DECODE_ONLY`. Spec Decoding feature is labeled
  “for low latency & small batch size”; MTP default in recipe YAML is
  `num_speculative_tokens: 2`. Advanced UI also offers much higher
  `max-num-seqs` (e.g. 256) as a throughput knob — that conflicts with the
  verified 16 default and with the known +57% regression at 32.
- **Relevance:** HIGH
- **Conflict note:** Recipe’s verified path keeps `max-num-seqs=16`. Raising
  concurrency for “throughput” is not free on MoE; their measured 16→32
  slowdown is consistent with keeping the recipe pin.

### 2. V4 long-context attention + FP4 indexer / hybrid KV packing

- **Title:** DeepSeek V4 in vLLM: Efficient Long-context Attention
- **URL:** https://vllm.ai/blog/2026-04-24-deepseek-v4
- **Summary:** vLLM’s V4 support targets 1M-token CSA+HCA hybrid attention with
  logical block size 256 so prefix-hit detection and scheduling stay uniform
  across compression ratios. Blog quickstarts use
  `--attention_config.use_fp4_indexer_cache=True`, `--kv-cache-dtype fp8`,
  expert parallel + data parallel, and the same `deepseek_v4` tokenizer /
  tool / reasoning parsers. KV footprint is called out as ~8.7× smaller than
  a V3.2-style stack at 1M (bf16 estimate), further cut by fp4 indexer + fp8
  attention cache — directly relevant to long-context judging TTFT/prefill
  capacity.
- **Relevance:** HIGH

### 3. MTP speculative decoding: decode win at low concurrency, regression risk otherwise

- **Title:** DeepSeek-V3.2 on GB300: Performance Breakthrough (MTP section)
- **URL:** https://vllm.ai/blog/2026-02-13-gb300-deepseek
- **Summary:** For DeepSeek MTP on vLLM
  (`--speculative-config.method mtp`, `num_speculative_tokens: 1` in this
  blog), decode throughput improves when context is not long and concurrency
  stays moderate (acceptance >80% cited; gains out to concurrency ≤256 on
  R1-0528/GB300). Throughput collapses under high concurrency. In short-output
  mixed workloads (ISL=2k, OSL=64), MTP overhead is not amortized and
  **overall throughput is worse than MTP-off** at both low and high
  concurrency. Recipe pages still advertise MTP for “low latency & small
  batch.” Long-context structured judging with short JSON answers is closer
  to the losing regime than chat decode-heavy.
- **Relevance:** HIGH
- **Conflict note:** Do not expect MTP to rescue a MoE pod already hurt by
  higher `max-num-seqs`; MTP itself can worsen short-decode / high-batch
  mixes.

### 4. Static MTP depth can slow MoE; adaptive K proposed

- **Title:** [RFC] Adaptive Speculation Depth for MoE Models via Per-Iteration Utility Budgeting
- **URL:** https://github.com/vllm-project/vllm/issues/46295
- **Summary:** Upstream RFC argues static `num_speculative_tokens` causes
  measurable throughput regressions on MoE (DeepSeek-V3 family cited). Cascade
  (arXiv:2506.20675) is referenced: static K=4 up to **1.5× slowdown** on
  code/math with DeepSeek-V3; adaptive K limits slowdown to ~5% and yields
  7–14% over best static K. Proposed flag shape:
  `moe_adaptive_spec: true` with an upper-bound K. Not shipped as a settled
  default; treat as evidence that “turn on MTP with K=2–4” is unsafe without
  measuring their judging mix.
- **Relevance:** MED

### 5. Automatic prefix caching cuts TTFT when judge prompts share prefixes

- **Title:** Automatic Prefix Caching — vLLM docs
- **URL:** https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/
- **Summary:** APC (`enable_prefix_caching=True` / `--enable-prefix-caching`)
  reuses KV for shared prompt prefixes; canonical win is long-document query
  (same document, different questions) and multi-turn history. Docs stress APC
  helps **prefill/TTFT**, not decode generation time; no gain if answers are
  long relative to shared prefix or if prefixes do not match. For structured
  judging with a stable system/schema prefix + paper body reuse (HMAC/prompt
  reorder territory), APC is the first-party TTFT lever. V4 blog notes
  allocator was designed to keep prefix-hit detection working with hybrid
  compressed KV blocks.
- **Relevance:** HIGH

### 6. Chunked prefill + max-num-batched-tokens trade TTFT vs ITL

- **Title:** Optimization and Tuning — Chunked Prefill (vLLM)
- **URL:** https://docs.vllm.ai/en/v0.22.0/configuration/optimization/
- **Summary:** In V1, chunked prefill is on by default and **prioritizes
  decode** before scheduling prefills into the remaining
  `max_num_batched_tokens` budget. Smaller budgets (e.g. 2048) improve
  inter-token latency; larger budgets improve TTFT by packing more prefill
  tokens per step; docs recommend `>8192` for throughput on smaller models /
  large GPUs. V4-Pro recipe uses **16384** on H200 with `max-num-seqs 16`.
  Related: inter-prefill-budget (PR #33743) can cut median TTFT ~37% by
  avoiding packing multiple saturated prefills into one batch — relevant if
  many long papers queue together.
- **Relevance:** HIGH

### 7. Guided decoding / structured-output cost on vLLM is real at batch ≥8

- **Title:** Guided Decoding Performance on vLLM and SGLang
- **URL:** https://blog.squeezebits.com/guided-decoding-performance-vllm-sglang
- **Summary:** Sep 2025 SqueezeBits benchmark (vLLM 0.10.0, XGrammar vs
  LLGuidance): guided decoding is required for schema correctness, but vLLM
  shows a **significant throughput drop vs unconstrained**, especially at
  batch size ≥8, because per-step mask generation is not fully overlapped with
  GPU work (SGLang hides more of that cost). For repetitive schemas, XGrammar
  + caching wins; for per-request unique/complex schemas, LLGuidance is more
  stable and XGrammar can stall the engine on CPU mask build. Older vLLM blog
  (2025-01-14) likewise flags FSM compile as a TTFT contributor and points at
  scheduler-level / off-critical-path masks in V1. Structured judging should
  assume guided decoding is a decode-path tax unless schema is fixed and
  cached.
- **Relevance:** HIGH

### 8. Speculative decoding / APC composition guidance (general serving)

- **Title:** vLLM Advanced: Building Custom Inference Pipelines at Scale (2026)
- **URL:** https://inference.net/content/vllm-advanced-custom-inference-pipelines/
- **Summary:** Secondary 2026 guide: APC + chunked prefill called out as
  near-zero-config 40–70% throughput wins when prefixes repeat; speculative
  decoding framed as 2–3× latency help for latency-sensitive traffic at
  **low-to-medium concurrency**, collapsing when the GPU is already saturated
  (rough threshold: below ~4 concurrent requests per GPU). Guided decoding
  overhead cited ~5–15% vs free-form; prefer `xgrammar` when schema compile
  cost shows up. Aligns with MTP blog and with keeping `max-num-seqs` low on
  MoE rather than chasing batch size.
- **Relevance:** MED

---

## Cross-cutting conflict: max-num-seqs

| Source | Signal |
|--------|--------|
| Internal `slots-32-regression` | 16→32 server slots: **+57%** cold wall on MoE pod |
| V4-Pro verified recipe (H200) | `--max-num-seqs 16` |
| V4-Pro recipe “Advanced” UI | Suggests `max-num-seqs=256` for throughput |
| MI355X ROCm example in same recipe page | `--max-num-seqs 512` (different hardware / backend) |
| MTP GB300 blog | High concurrency + MTP hurts; short OSL hurts MTP |
| SqueezeBits guided decoding | vLLM structured-output tax grows with batch ≥8 |

**Takeaway for cold-run research:** Prefer recipe-aligned low `max-num-seqs`,
APC / shared prefixes for TTFT, and treat MTP + higher seq concurrency +
guided decoding as interacting costs — not independent “turn all on” knobs.
