# 112 - sglang-Benchmark-Evidence

**Verdict:** usable-with-conditions — the clone ships purpose-built prefix-heavy benchmarks (`generated-shared-prefix`, `--enable-shared-prefix`) that structurally match post–persona-15 unit checks, but in-repo sglang-vs-vLLM tables are ShareGPT with RadixAttention disabled (~3% offline gap); the 6.4× prefix-heavy delta is external, and fixing vLLM APC + prompt reorder is the higher-ROI path than engine migration.
**Confidence:** medium

## Findings

- [CRITICAL] **`generated-shared-prefix` is the canonical "N questions over one document" bench in `bench_serving`.** Dataset registered at `python/sglang/benchmark/datasets/__init__.py:27`; prompt shape is `{system_prompt}\n\n{question}` with many questions sharing one system group (`generated_shared_prefix.py:284`). CLI defaults: 64 groups × 16 prompts/group = 1024 requests; system 2048 tok, question 128 tok, output 256 tok (`serving.py:2560-2590`). Impact: this is the right harness to replay our workload (long shared body + short unique tail), but the clone publishes **no checked-in sglang-vs-vLLM result table** on this dataset; quality risk: none for benchmarking; fleet impact unknown until run on DeepSeek-V4-Pro @ concurrency 16.

- [HIGH] **`hicache --enable-shared-prefix` explicitly models grouped questions over one prefix.** README documents request order `[A+Q1, A+Q2, B+Q1, B+Q2, …]` (`benchmark/hicache/README.md:66-69`); `bench_serving.py` flattens prefix groups when `enable_shared_prefix=True` (`benchmark/hicache/bench_serving.py:418-420`). This matches persona-15 unit-check reorder (shared `candidate_md` before unique unit/source tail). Impact: serial within-paper unit checks naturally emit this order; fleet-level 32-paper interleaving dilutes locality vs the bench's `--disable-shuffle` ideal. Expected incremental win over broken vLLM APC: **600–1100 s** on 3003 s cold run (`15-prefix-cache-enabler.md:22`); SGLang radix may add margin only if vLLM block-APC hit rate stalls below ~75%.

- [HIGH] **In-repo sglang-vs-vLLM head-to-head numbers are NOT prefix-heavy; radix cache is explicitly disabled.** `benchmark_vllm_060/README.md:61-62` launches both engines with `--disable-radix-cache`. Measured on Llama-3.1-8B ShareGPT @ RPS 4: median TTFT **31.98 ms (SGLang) vs 100.48 ms (vLLM)** (~3.1×), median ITL **11.93 vs 129.32 ms** (~10.8×) (`benchmark_vllm_060/README.md:11-14`); offline output throughput **4281.51 vs 4132.37 tok/s** (~**3.6%** margin, `benchmark_vllm_060/README.md:31-32`). Impact: these numbers **understate** prefix-cache value and **overstate** the case for migration when the gap collapses without shared prefixes (05-web Q4). Our post-reorder workload is prefix-heavy; this table is the wrong regime.

- [HIGH] **RadixAttention "up to 5×" claim in README is blog-linked, not clone-local measured.** `README.md:56` cites LMSYS blog; no JSON/MD artifact in `research/repos/sglang` with 5× on GSP. Closest in-repo radix measurement: HiCache GSP microbench asserts hierarchical cache cuts mean TTFT to **≤60%** of no-cache baseline on 128 prompts sharing one 1792-tok group (`test_npu_hierarchical_cache_ttft_mha.py:68-84`). Impact: supports radix helps TTFT on shared-prefix loads, but on **Ascend NPU / Qwen3-32B**, not our **H200 / DeepSeek-V4-Pro / vLLM APC** stack; cannot translate to fleet seconds without a live A/B.

- [HIGH] **GSP "prefix90" perf tests encode ~90% shared-prefix ratio — closest CI knob to our unit-check cascade — but are NPU baselines, not migration proof.** Example: `repeat_rate=0.9`, `input_len=65536`, `output_len=1024`, `max_concurrency=40`, `dataset_name="generated-shared-prefix"`, CI floor `output_token_throughput=660` tok/s (`test_npu_qwen3_6_35b_a3b_1p_in64k_out1k_prefix90_50ms_aime26.py:123-133`). Analogous MoE test: `output_token_throughput=390.5859` @ prefix90 (`test_npu_minimax_m2_5_w8a8_4p_in64k_out1k_prefix90_50ms_gpqa.py:104-113`). Impact: confirms SGLang invests in high-share-prefix regression, but **hardware/model mismatch** with `alliance-pod`; vLLM PR #43447 already shows **44→196 tok/s (~4.5×)** at **74.3%** hit rate on **our** DeepSeek-V4-Pro @ `--max-num-seqs 16` (05-web Q1, `00-baseline.md:65-66`).

- [MED] **`llm_judge` benchmark is judge-shaped but not serving-comparable.** Shared article in system context + 6 short dimension verdicts (`benchmark/llm_judge/bench_sglang.py:24-50`); uses SGLang `fork()` batching, not HTTP `bench_serving`. README gives run recipes only, **no sglang-vs-vLLM latency table** (`benchmark/llm_judge/README.md:1-27`). Impact: architectural analog (one long doc, many short structured outputs) but no hard throughput numbers; fleet lever remains prefix-cache + call-count, not frontend fork API.

- [MED] **`bench_in_batch_prefix` is a micro synthetic prefix lab with runtime-only output.** 10 prefix groups × 32 samples, prefix **1024** tok, suffix **128** tok, gen **1** tok (`bench_in_batch_prefix.py:112-116`); compares batch-by-batch vs send-all strategies, prints latency to stdout (`bench_in_batch_prefix.py:123-130`), **no checked-in baseline ms or speedup ratio**. Impact: useful local repro, zero fleet projection; confirms SGLang tests prefix-cache batching semantics.

- [LOW] **Multi-turn benches cover shared system prompt but not "one doc, many judge calls".** `long_prompt_multi_turn.py` defaults: 128 conversations, 8 turns, system **2048** tok, Q **32** tok, A **128** tok (`long_prompt_multi_turn.py:117-121`); `bench_multiturn.py` defaults 256 clients × 5 rounds (`bench_multiturn.py:30-57`). Impact: secondary anchor; our unit checks are single-turn HTTP calls with shared middle block, not conversational KV extension.

## False-pass hypothesis

Migrate to SGLang for RadixAttention before deploying vLLM APC + PR #43447 retention + persona-15 reorder: operators burn a multi-week engine swap, MoE routing re-validates under different batch scheduler, and **prefix hit rate on unit checks stays near 0%** because guard-tag or user-block order was not fixed — fleet stays ~3003 s while attributing failure to "SGLang didn't help."

## False-fail hypothesis

Reject SGLang based solely on `benchmark_vllm_060` ShareGPT numbers (radix disabled, ~3.6% offline throughput gap): that table reflects **unique-prompt** regime where 05-web Q4 says gap collapses; a post-reorder prefix-heavy replay on `generated-shared-prefix` with `--gsp-ordered` could show large TTFT gains on **either** engine, falsely concluding vLLM APC is hopeless when `--enable-prefix-caching` + retention was never enabled on `alliance-pod`.

## What would change my mind

A single `bench_serving` A/B on **`alliance-pod` hardware**: DeepSeek-V4-Pro, `--max-num-seqs 16`, dataset `generated-shared-prefix` with `--gsp-ordered --gsp-num-groups 381 --gsp-prompts-per-group 4 --gsp-system-prompt-len 925 --gsp-question-len 2500 --gsp-output-len 400` (scaled to our unit-check token budget), comparing (A) vLLM APC+retention+reordered prompts vs (B) SGLang RadixAttention+same prompts, reporting median TTFT, output tok/s, and 48-paper holdout verdict diff. If SGLang wins **≥1.5× output tok/s** at ≥95% APC hit rate **and** holds verdict diff ≤25%, migration becomes worth piloting; otherwise stay on vLLM and spend the integration budget on call elimination + dual-pod sharding.

## Honest engine decision (post–persona-15 prompt structure)

**Actual prompt shape after persona-15 reorder** (`15-prefix-cache-enabler.md:10-12`): per-paper guard tag; unit user block `[system+tag] → Paper → candidate_md → Unit/Risk/SOURCE`. Cross-type calls (monolith / metadata / page / unit) still diverge at system-prompt token 0, so only **unit checks 2–5 within a paper** share the large `candidate_md` KV block (~75% of unit calls, ~1510 total).

| Regime | Who wins | By how much (evidence) | Worth migration? |
|--------|----------|------------------------|------------------|
| Prefix-heavy unit checks (post-reorder) | **Tie → slight SGLang** on paper | External: up to **6.4×** prefix-heavy (05-web Q4); in-clone radix TTFT **≤0.6×** on GSP (`test_npu_hierarchical_cache_ttft_mha.py:84`); vLLM APC fixed on **our** model: **~4.5×** tok/s @ 74.3% hits (05-web Q1) | **No** — vLLM fix is config + client reorder, not a new engine |
| Unique prompts / no shared prefix | **vLLM competitive or ahead** | ShareGPT w/ radix off: **3.6%** offline tok/s gap (`benchmark_vllm_060/README.md:31-32`); 05-web: gap collapses without shared prefixes | N/A |
| Extreme concurrency / MoE batch mixing | **Uncertain; vLLM won in one issue** | 05-web Q4 cites vLLM ahead at extreme concurrency; our `--max-num-seqs 16` is already high for MoE (`00-baseline.md:83`) | **No** — migration adds scheduler risk without call-count cuts |

**Fleet projection:** persona-15 prefix levers alone → **~1900–2400 s** wall (`15-prefix-cache-enabler.md:22`); still above 5–10 min target. Even a generous **1.3–1.5×** SGLang increment on top yields **~1300–1850 s**, not sub-600 s. **Engine migration delta (~300–500 s hypothetical) is smaller than metadata short-circuit + dual-pod + call elimination** already modeled in sibling personas (`48-combined-lever-modeler.md`).

**Recommendation:** Fix vLLM APC usage on `alliance-pod` (PR #43447 build, `--enable-prefix-caching`, `VLLM_PREFIX_CACHE_RETENTION_INTERVAL=32768`, per-paper guard tag, unit user reorder). Treat SGLang as **benchmark oracle and fallback**, not the primary fleet lever, until a DeepSeek-V4-Pro H200 GSP A/B proves ≥1.5× over a fully fixed vLLM baseline.
