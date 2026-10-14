# 05c — Web Forager: Prefix Caching & Guided/Structured Output (vLLM 0.24)

Context: self-hosted vLLM **0.24.0**, `deepseek-v4-pro`, identical ~8 KB system prompt across all papers, unique 2–500 KB user markdown per request, raw JSON output path. Searches started from `vllm automatic prefix caching default enabled shared system prompt speedup 2026` and `vllm 0.24 structured output xgrammar performance deepseek reasoning`, then refined.

---

## Finding 1 — vLLM V1: Prefix Caching On by Default, Near-Zero Miss Penalty

**URL:** https://openlm.ai/vllm-v1/

**Summary:** In vLLM V1 (the default engine from ~v0.10 onward, including 0.24), prefix caching is **enabled by default** because V1 reworked hash-table eviction to constant time and cut Python object churn. V1 benchmarks report **<1% throughput loss at 0% cache hit rate** versus disabling APC, while high hit rates yield **several×** throughput gains. No client API change is required: the OpenAI-compatible server reuses KV blocks automatically when token prefixes match; clients only need a stable, byte-identical shared prefix (e.g., the same system message prepended to every request).

**Relevance:** **HIGH** — Direct answer on default-on behavior for 0.24 and that clients benefit passively if the pod runs V1 with APC (likely, but unverified on alliance-pod).

---

## Finding 2 — SqueezeBits: Shared System-Prompt Workload Benchmarks (vLLM 0.6.3)

**URL:** https://blog.squeezebits.com/vllm-vs-tensorrtllm-12-automatic-prefix-caching-38189

**Summary:** On Llama-3.1-8B with a dataset where **25% of input tokens are a shared prefix** (analogous to a fixed system prompt), vLLM APC raised throughput **~13.3%** and improved TPOT **~9.8%** at max concurrency 16; raising shared-prefix ratio from 0.1→0.9 lifted throughput **32%**. Without any shared prefix, legacy vLLM APC could **hurt** throughput (~36.7% drop on random data) due to hash overhead, though V1 claims to fix that miss-path penalty. APC only skips prefill for the cached portion, so TTFT gains scale with prefix length relative to total input.

**Relevance:** **HIGH** — Best published numbers for a system-prompt-like prefix; for tapetum's ~8 KB system prompt against 2–500 KB papers, expect **modest TTFT savings** (roughly the system-prompt fraction of prefill, not the 78% seen when most input is shared).

---

## Finding 3 — Jarvis Labs: Prefix Caching TTFT −78%, Throughput +254% (Heavy Shared-Prefix Dataset)

**URL:** https://jarvislabs.ai/blog/vllm-optimization-techniques

**Summary:** On Qwen3-32B with a custom 200-prompt benchmark designed for prefix reuse (`iris_prefix_cache_benchmark.jsonl`), enabling `--enable-prefix-caching` cut mean TTFT from **4343 ms → 970 ms (−78%)** and raised output-token throughput from **427 → 1513 tok/s (+254%)** at ~**50% cache hit rate**; TPOT rose ~10% (cache lookup overhead). This is an upper bound when a large fraction of input is shared; it overstates tapetum's case where only ~8 KB of a 50–500 KB prompt repeats.

**Relevance:** **MED** — Illustrates APC ceiling when prefix dominates input; useful as a sanity bound, not a direct projection for paper-heavy prompts.

---

## Finding 4 — vLLM Structured Decoding Blog: XGrammar Default, Up to 5× TPOT Under Load

**URL:** https://vllm.ai/blog/2025-01-14-struct-decode-intro

**Summary:** XGrammar became the **default** structured-decoding backend (replacing Outlines for supported schemas), moving grammar compilation to C with pthread and PDA-based batch masking. Under load, vLLM reports **up to 5× lower time-per-output-token (TPOT)** versus the old Outlines logit-processor path, which blocked entire batches during per-request FSM compile. Outlines-era guidance noted structured decoding could **increase TTFT** when FSM compilation sat on the sampling critical path; XGrammar targets that bottleneck. vLLM falls back to Outlines when XGrammar cannot represent the schema (regex ranges, some Literal edge cases).

**Relevance:** **HIGH** — Establishes that guided JSON is now a **throughput win under batching**, not purely overhead, once XGrammar is active (0.24 default).

---

## Finding 5 — vLLM Docs: Structured Outputs + Reasoning Models (DeepSeek)

**URL:** https://docs.vllm.ai/en/stable/features/structured_outputs/

**Summary:** vLLM 0.24 accepts `response_format: {type: "json_schema", ...}` and `extra_body.structured_outputs.json` (legacy `guided_json` removed in v0.12+). Structured outputs compose with reasoning models via `--reasoning-parser` (e.g., `deepseek_r1`): xgrammar uses the reasoner's **`end_token_id`** (e.g., ``) to detect when thinking ends and **only then** applies JSON constraints to the answer tokens. DeepSeek-V4-Pro requires `enable_thinking: true` in chat-template kwargs or reasoning never runs. Caveat from docs: on some models (Qwen3 Coder), structured output can disable unless `--structured-outputs-config.enable_in_reasoning=True`; DeepSeek R1/V3 list **json** support in the reasoning table.

**Relevance:** **HIGH** — Answers whether guided JSON fights thinking models: **designed to defer constraints until after reasoning**, not mask thinking tokens; server must run the correct `--reasoning-parser` for DeepSeek-V4-Pro (verify CTO pod flags).

---

## Finding 6 — vLLM PR #24300: XGrammar Bitmask Overlap (V1 Structured-Output Perf)

**URL:** https://github.com/vllm-project/vllm/pull/24300

**Summary:** Refactor moved grammar-bitmask work from the scheduler into the GPU runner so CPU bitmask calculation **overlaps** model forward passes; includes explicit handling for **"reason thinking"** structured-output requests. On Qwen3-8B, `benchmark_serving_structured_output.py` (100 prompts, xgrammar_bench) showed request throughput **18.47 → 24.29 req/s (+31.5%)**, output throughput **1132 → 1507 tok/s (+33.1%)**, mean TPOT **43.6 → 34.5 ms (−21%)**, mean TTFT **969 → 226 ms (−77%)** — though TTFT drop partly reflects moving work off the scheduler hot path. PR closed in favor of follow-on #26866, but numbers characterize the optimization direction in 0.24-era V1.

**Relevance:** **MED** — Concrete structured-output serving benchmarks; TTFT improvement is workload-specific, TPOT/throughput gains are the durable signal for batched JSON adjudication.

---

## Cross-cutting notes for tapetum (from cards above)

| Lever | Client change? | Expected effect on 36-min corpus |
|-------|----------------|-----------------------------------|
| APC (shared ~8 KB system prompt) | **No** — keep system message identical; optional `--no-enable-prefix-caching` only if CTO disables | Small per-request TTFT cut on large papers; larger win under concurrency when cache warm; verify pod has APC on |
| Guided JSON (`response_format` / `structured_outputs`) | **Yes** — add schema to API calls in whisker | Likely **lower retry rate** + faster decode vs free-form JSON parsing; xgrammar default in 0.24; needs `--reasoning-parser` aligned with DeepSeek-V4-Pro |

**Determinism flag:** GitHub issue #40896 documents non-deterministic outputs at `temperature=0` with prefix caching enabled on V1; disable APC or set `VLLM_BATCH_INVARIANT=1` if bit-identical reruns matter (baseline notes batch-invariant costs ~50% throughput).
