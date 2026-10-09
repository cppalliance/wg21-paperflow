# 40 - Server-Flag-Auditor

**Verdict:** usable-with-conditions — the official DeepSeek-V4-Pro recipe closes a real MBT/MTP/CUDA-graph gap vs today's H200SXM launch, but server flags alone conservatively save ~300–550 s on the 3003 s cold run; reaching 5–10 min still requires client-side prefix alignment and call-count levers.
**Confidence:** high

## Operator verification checklist (introspect running `alliance-pod`)

| Flag / knob | How to verify live | Pass criterion |
|---|---|---|
| vLLM version (PR #43447 retention merge) | `GET /version` → semver; startup log `vLLM API server version`; or `GET /server_info?config_format=json` if `VLLM_SERVER_DEV_MODE=1` ([PR #16572](https://github.com/vllm-project/vllm/pull/16572)) | Build ≥ merge of [PR #43447](https://github.com/vllm-project/vllm/pull/43447) (2026-06-04); container `cppalliance/vllm-openai:v0.24.0` may predate it — confirm before enabling APC |
| `--max-num-seqs` | `/metrics` → `vllm:num_requests_running` peaks ≤16 under fleet load; startup log `max_num_seqs`; `/server_info` `max_num_seqs=16` | **16** (matches [recipe](https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro), `00-baseline.md:66`) |
| `--max-num-batched-tokens` | Startup log line `max_num_batched_tokens=`; `/server_info` scheduler block; absence in [H200SXM.txt](https://raw.githubusercontent.com/cppalliance/runpod/master/templates/deepseek/H200SXM.txt) ⇒ v0.24 H200 OPENAI default **8192** ([arg_utils.py:2387-2391](https://github.com/vllm-project/vllm/blob/v0.24.0/vllm/engine/arg_utils.py#L2387-L2391)) | Target **16384** per recipe (`05-web.md:15-16`) |
| `--kv-cache-dtype` | `/server_info` or startup `kv_cache_dtype=fp8`; `/metrics` `vllm:kv_cache_usage_perc` (lower vs bf16 at same concurrency) | **fp8** — already in H200SXM.txt |
| `--enable-prefix-caching` | Startup `Enabling prefix caching`; `/server_info` `enable_prefix_caching=True`; `/metrics` counters `vllm:prefix_cache_queries_total` / `vllm:prefix_cache_hits_total` non-zero under load ([metrics.md](https://github.com/vllm-project/vllm/blob/main/docs/design/metrics.md)) | Explicit **on** + retention env below; hit rate `rate(hits[5m])/rate(queries[5m])` should rise above 0% once prompts share prefixes |
| `VLLM_PREFIX_CACHE_RETENTION_INTERVAL` | `/server_info` `vllm_env` block; pod env in RunPod template | **32768** ([PR #43447](https://github.com/vllm-project/vllm/pull/43447), `05-web.md:8-9`) |
| MTP / `--speculative-config` | Startup `SpeculativeConfig(method='mtp'...)`; `/server_info` `speculative_config=...`; optional acceptance metrics if exposed | `{"method":"mtp","num_speculative_tokens":1}` (recipe uses 2; judge OSL is short — see target set) |
| CUDA graph mode | Startup `compilation_config` / `cudagraph_mode`; `/metrics` `vllm:cudagraph_*` if `--cudagraph-metrics` | `FULL_DECODE_ONLY` via `--compilation-config` ([recipe MI355X example](https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro)) |
| Chunked prefill | `/server_info` `chunked_prefill_enabled=True`; docs default-on V1 ([optimization](https://docs.vllm.ai/en/stable/configuration/optimization/#chunked-prefill)) | **Leave on** (default when model supports); do not disable |
| Scheduler health | `/metrics`: `vllm:num_requests_waiting`, `vllm:kv_cache_usage_perc`, `histogram_quantile(0.95, vllm:time_per_output_token_seconds)` | Waiting ≈0 sustained at c=16; no preemption storm in logs |

**Log grep one-liner (pod stdout):** `max_num_batched_tokens|max_num_seqs|prefix caching|SpeculativeConfig|compilation_config|cudagraph|kv_cache_dtype|chunked_prefill`

**Metrics one-liner:** `curl -s $POD/metrics | rg 'prefix_cache|num_requests_(running|waiting)|kv_cache_usage'`

## Target flag set (delta from current H200SXM launch)

**Baseline (confirmed today):** [H200SXM.txt](https://raw.githubusercontent.com/cppalliance/runpod/master/templates/deepseek/H200SXM.txt) — TP8+EP, `--max-num-seqs 16`, `--max-model-len 393216`, `--kv-cache-dtype fp8`, `--gpu-memory-utilization 0.95`. Missing vs recipe: explicit MBT, prefix caching + retention env, MTP, CUDA graphs.

**Recommended launch delta (add/replace only):**

```bash
# Environment (RunPod template)
VLLM_PREFIX_CACHE_RETENTION_INTERVAL=32768

# Container start command additions (keep all existing H200SXM flags)
--max-num-batched-tokens 16384 \
--enable-prefix-caching \
--speculative-config '{"method":"mtp","num_speculative_tokens":1}' \
--compilation-config '{"mode": 3, "cudagraph_mode": "FULL_DECODE_ONLY"}' \
--long-prefill-token-threshold 8192
```

| Flag | Justification |
|---|---|
| `--max-num-batched-tokens 16384` | Official [DeepSeek-V4-Pro recipe](https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro) default; v0.24 OPENAI server on H200 silently defaults **8192** ([arg_utils.py:2387-2391](https://github.com/vllm-project/vllm/blob/v0.24.0/vllm/engine/arg_utils.py#L2387-L2391)). Doubling co-tuned with `--max-num-seqs 16` avoids prefill-chunk budget starvation documented in [optimization](https://docs.vllm.ai/en/stable/configuration/optimization/#performance-tuning-with-chunked-prefill) and internal [13-prefill-interference.md](../slots-32-regression/13-prefill-interference.md). |
| `--enable-prefix-caching` + `VLLM_PREFIX_CACHE_RETENTION_INTERVAL=32768` | DeepSeek V4 sliding-window KV evicts APC blocks at c=16 without retention → **0% hits**; fix + env yields **74.3% hits**, server output **44→196 tok/s** at same concurrency ([PR #43447](https://github.com/vllm-project/vllm/pull/43447)). APC is opt-in via flag ([APC docs](https://docs.vllm.ai/en/stable/features/automatic_prefix_caching/)); prior swarm research confirms not effectively enabled on alliance-pod. |
| `--speculative-config '{"method":"mtp","num_speculative_tokens":1}'` | Recipe specifies MTP k=2 (`05-web.md:16-17`); [GB300 DeepSeek blog](https://blog.vllm.ai/2026/02/13/gb300-deepseek.html) shows k=1 >80% acceptance and higher decode throughput at concurrency ≤256, but k=1 hurts when OSL is very short (64). Tapetum judge outputs are structured JSON with reasoning capped 40–60 words (`00-baseline.md:28-29`) — use **k=1** first; A/B k=2 if acceptance metrics justify. |
| `--compilation-config '{"mode": 3, "cudagraph_mode": "FULL_DECODE_ONLY"}'` | Recipe CUDA-graph mode ([recipes.vllm.ai](https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro)); captures decode-step graphs without full prefill capture, reducing launch overhead on decode-heavy batches. |
| `--long-prefill-token-threshold 8192` | Co-tune with MBT for 3k–100k judge prefills; caps single-step prefill monopoly ([PR #31330](https://github.com/vllm-project/vllm/pull/31330), [15-deployment-tuning.md](../slots-32-regression/15-deployment-tuning.md)). |
| **Keep** `--max-num-seqs 16` | Measured sweet spot; 16→32 without co-tune regressed wall +57% ([00-baseline.md:82-83](../tapetum-llm-speedup/00-baseline.md)). |
| **Keep** `--kv-cache-dtype fp8` | Already set; halves KV traffic, ~54% decode ITL slope vs BF16, ≤1–2 pt eval loss ([FP8 KV blog](https://vllm.ai/blog/2026-04-22-fp8-kvcache)). |
| **Keep** chunked prefill (default on) | V1 enables when model supports ([arg_utils.py:2444-2448](https://github.com/vllm-project/vllm/blob/v0.24.0/vllm/engine/arg_utils.py#L2444-L2448)); disabling risks startup failure at 393k context. |

**Do not change:** `--max-num-seqs` above 16 without proportional MBT co-scale; `--enable-ep-weight-filter` (load-time only, [PR #37351](https://github.com/vllm-project/vllm/pull/37351)).

## Quality / determinism vs throughput-only classification

| Lever | Changes model outputs? | Notes |
|---|---|---|
| `--max-num-batched-tokens` | **No** (scheduling only) | Alters batch composition timing; MoE routing variance already documented (`MODELS.md:69-70`) — same class as concurrency tuning, not new semantic risk |
| `--enable-prefix-caching` + retention env | **No** | Replays identical KV for identical leading tokens ([APC docs](https://docs.vllm.ai/en/stable/features/automatic_prefix_caching/)); bitwise prefix replay |
| `--kv-cache-dtype fp8` | **Slight** (already live) | ≤1–2 pt benchmark loss typical; DeepSeek hybrid layers may need `--kv-cache-dtype-skip-layers sliding_window` if regressions seen ([FP8 KV blog](https://vllm.ai/blog/2026-04-22-fp8-kvcache)) |
| MTP speculative decoding | **No** (algorithmically) | vLLM documents lossless rejection sampling ([spec decode docs](https://docs.vllm.ai/en/stable/features/speculative_decoding/#lossless-guarantees-of-speculative-decoding)); logprob/run variance still possible under continuous batching |
| `FULL_DECODE_ONLY` CUDA graphs | **No** | Kernel launch path only |
| Chunked prefill (on/off) | **No** | Scheduler policy; default-on recommended |

## Findings

- [CRITICAL] **`alliance-pod` runs recipe-aligned seq cap and FP8 KV but omits the rest of the official H200 tuning triangle.** Evidence: [H200SXM.txt](https://raw.githubusercontent.com/cppalliance/runpod/master/templates/deepseek/H200SXM.txt) has `--max-num-seqs 16` and `--kv-cache-dtype fp8`; no `--max-num-batched-tokens` ⇒ **8192** implicit on v0.24 H200 OPENAI path ([arg_utils.py:2387-2391](https://github.com/vllm-project/vllm/blob/v0.24.0/vllm/engine/arg_utils.py#L2387-L2391)); recipe expects **16384** ([recipes.vllm.ai](https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro), `05-web.md:15-16`). Impact: **+100–250 s** conservative on 3003 s from reduced prefill/decode scheduler contention; quality risk **none**.

- [CRITICAL] **Prefix caching is the largest server-side lever but requires PR #43447 build + retention env; without both, APC can stay at 0% hits on DeepSeek V4.** Evidence: trace replay at c=16: **0%→74.3%** prefix hits, output throughput **44→196 tok/s** ([PR #43447](https://github.com/vllm-project/vllm/pull/43447)); prior research: not effectively enabled (`05-web.md:5-12`, `15-prefix-cache-enabler.md:6-8`). Server-only (static ~820 tok system prefix across ~2284 calls): **60–180 s** (`15-prefix-cache-enabler.md:20`). Full hit rate needs client per-paper tag + user reorder (out of scope here). Impact: **60–180 s** server-only; **600–1100 s** with client alignment. Quality risk: **none** for server config.

- [HIGH] **MTP is absent today; recipe-native decode acceleration for short structured judge outputs.** Evidence: recipe MTP k=2 (`05-web.md:16-17`); [GB300 blog](https://blog.vllm.ai/2026/02/13/gb300-deepseek.html) k=1 >80% acceptance at c≤256; Flash benchmark **1.49×** decode at bs=1 ([HF canada-quant](https://huggingface.co/canada-quant/DeepSeek-V4-Flash-W4A16-FP8-MTP)). Tapetum is decode-tagged (`pdf_judge.py:27`, `00-baseline.md:26-28`) but prefill-heavy per call (~17 s of ~20 s on large docs). Impact: **100–200 s** conservative (decode fraction × 1.3–1.5× speedup × 2284 calls / 16 slots). Quality risk: **none** algorithmically; monitor for JSON schema retries.

- [HIGH] **CUDA graphs `FULL_DECODE_ONLY` missing; recipe ships `mode:3` compilation config.** Evidence: [recipes.vllm.ai](https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro) MI355X/H200-class example; not present in H200SXM.txt. Impact: **50–120 s** on decode overhead at 16 slots. Quality risk: **none**.

- [HIGH] **Chunked prefill is already on by default — verify, do not disable.** Evidence: v0.24 sets `enable_chunked_prefill` from model support when unset ([arg_utils.py:2444-2448](https://github.com/vllm-project/vllm/blob/v0.24.0/vllm/engine/arg_utils.py#L2444-L2448)); V1 optimization docs ([chunked prefill](https://docs.vllm.ai/en/stable/configuration/optimization/#chunked-prefill)). Impact: **0 s delta** if left default; disabling risks correctness/startup at 393k. Quality risk: **none** if unchanged.

- [MED] **`--kv-cache-dtype fp8` is already deployed — confirm, not a delta.** Evidence: H200SXM.txt; blog: +14.9% output throughput under load, median ITL −14.8% ([FP8 KV blog](https://vllm.ai/blog/2026-04-22-fp8-kvcache)). Impact: **0 s** incremental; already baked into 3003 s baseline. Quality risk: **slight** (≤1–2 pt), already accepted.

- [MED] **Conservative combined server-flag envelope on the 3003 s cold run (no client prompt reorder): ~300–550 s (10–18%), wall ~2450–2700 s.** Decomposition: MBT 16384 **100–250 s** + APC server-only **60–180 s** + MTP k=1 **100–200 s** + CUDA graphs **50–120 s**, with overlap/discount ~25%. Does **not** reach 5–10 min alone (`00-baseline.md:3-4`). If vLLM lacks PR #43447, APC line drops to **0 s** and may add hash overhead ([05-web.md Q4 squeezebits](research/tapetum-llm-speedup/05-web.md)). Quality risk: aggregate **low** (FP8 already live; MTP lossless-by-design).

- [LOW] **Optional co-tune `--long-prefill-token-threshold 8192` pairs with MBT 16384 for mixed 3k–100k prompts.** Evidence: [PR #31330](https://github.com/vllm-project/vllm/pull/31330); [15-deployment-tuning.md](../slots-32-regression/15-deployment-tuning.md). Impact: **30–80 s** incremental vs MBT alone under heavy prefill bursts. Quality risk: **none**.

## False-pass hypothesis

Enable APC + retention on v0.24 without PR #43447: `/metrics` prefix hit rate stays ~0%, operators treat the fleet as "optimized," and wall time unchanged or slightly worse from APC hash overhead ([05-web.md Q4](05-web.md)) while believing server tuning is complete — masking that client guard-tag placement still blocks the 74% hit regime.

## False-fail hypothesis

Deploy MTP k=2 (recipe default) on unit checks with very short JSON outputs (<64 tokens effective OSL): MTP draft overhead dominates acceptance gain ([GB300 blog](https://blog.vllm.ai/2026/02/13/gb300-deepseek.html)), decode TPOT rises, and operators revert all recipe flags including beneficial MBT 16384 and retention env — falsely attributing regression to prefix caching or FP8.

## What would change my mind

A/B on the 381-paper cold fleet: control = current H200SXM launch; variant = full target flag set above (with vLLM build confirmed post-#43447), same client code, reporting wall time and sidecar verdict diff rate. If wall savings <200 s or verdict diffs exceed the advisory ~25% flip budget, downgrade to **garbage** for the combined recipe bundle and keep only MBT + CUDA graphs.
