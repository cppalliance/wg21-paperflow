# 05 - Web finding cards (5 foragers, 2026-07-23)

## Q1: vLLM MoE serving tuning for DeepSeek-class judge workloads

- **[HIGH] DeepSeek V4 selective prefix-cache retention (vLLM PR #43447)**
  https://github.com/vllm-project/vllm/pull/43447
  DeepSeek V4's sliding-window KV cache evicted APC blocks under concurrency ->
  0% prefix hits. After the fix + `VLLM_PREFIX_CACHE_RETENTION_INTERVAL=32768`:
  trace replay at concurrency 16 on DeepSeek-V4-Pro went 0% -> 74.3% prefix
  hits, server output throughput 44 -> 196 tok/s (~4.5x), per-user decode
  6 -> 19 tok/s, ITL p50 155 -> 54 ms; GSM8K stayed ~95.6%. OUR MODEL, OUR
  CONCURRENCY.
- **[HIGH] DeepSeek-V4-Pro official vLLM recipe (H200)**
  https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro
  Defaults: TP+EP, `--max-num-seqs 16`, `--max-num-batched-tokens 16384`,
  `--kv-cache-dtype fp8`, MTP speculative decoding via
  `--speculative-config '{"method":"mtp","num_speculative_tokens":2}'`.
- **[HIGH] DeepSeek serving guide (vLLM blog GB300)**
  https://blog.vllm.ai/2026/02/13/gb300-deepseek.html
  MTP num_speculative_tokens=1: >80% acceptance, higher decode throughput at
  concurrency <=256; drops when OSL very short (64) because overhead is not
  amortized.
- **[HIGH] FP8 KV cache state (vLLM blog)**
  https://vllm.ai/blog/2026-04-22-fp8-kvcache
  `--kv-cache-dtype fp8`: halves KV memory, decode ITL slope ~54% of BF16,
  +14.9% output throughput under load, <=1-2 pt accuracy loss. DeepSeek caveat:
  sliding-window layers may need skip flag.
- **[HIGH] DeepSeek-V4-Flash MTP benchmark (HF canada-quant)**
  https://huggingface.co/canada-quant/DeepSeek-V4-Flash-W4A16-FP8-MTP
  MTP k=1: 1.49x decode speedup bs=1, acceptance 89% calibrated / 70% random.
- **[MED] vLLM expert parallel deployment docs**; **[MED] AMD MoE playbook**
  (TP+EP vs DP+EP by concurrency regime); **[MED] chunked prefill + APC
  compose (PR #7753)**: both on ~ +8% over APC alone.

## Q2: olmOCR throughput design

- **[HIGH] olmOCR technical report** https://olmocr.allenai.org/papers/olmocr.pdf
  ~500-page work items; within an item ALL pages submitted concurrently; worker
  waits for zero pending, then next item. H100: 3050 output tok/s (1288 pages
  in 5m07s). $176-178/M pages. 12% retry rate measured.
- **[HIGH] olmocr/pipeline.py defaults**
  https://github.com/allenai/olmocr/blob/main/olmocr/pipeline.py
  `--workers 20`, `--max_concurrent_requests 1600`, `--pages_per_group 500`,
  `--max_page_retries 8`, `--max_page_error_rate 0.004`; global semaphore;
  pages via asyncio.TaskGroup; temperature ramp on retries; pdftotext fallback.
- **[HIGH] README migration SGLang -> vLLM (v0.1.75)**; model FP8 dense 7B.
- **[HIGH] Robustness tradeoffs (report App. D.2)**: NO guided JSON at
  inference (avoids repetition collapse; parse failures just retry).
- **[HIGH] olmOCR-Bench**: 82.4 overall vs marker 76.1; quality NOT traded.

## Q3: batch inference patterns

- **[HIGH] Batch inference 2026 (swfte)**: vLLM offline engine / Ray Data ~2x
  vs HTTP-mediated batches on same hardware; sustained batch utilization ~90%
  vs ~35% online.
- **[HIGH] vLLM auto_tune README**: sweep max-num-seqs/max-num-batched-tokens
  against p99 budget; short-context workloads need larger max-num-seqs.
- **[HIGH] Ray Data LLM batch pattern**: batch_size aligned with max_num_seqs.
- **[HIGH] Multi-objective judge prompt packing (arXiv 2605.26046)**: packing
  per-criterion judge instructions into one prompt drops Spearman rho ~5.3%;
  multi-task configs often never beat single-task.
- **[MED] Batch Prompting (arXiv 2301.08721)**: N-questions-per-call saves ~5x
  tokens but accuracy drops as per-item context grows. Caution for multi-unit
  packing with long pages.
- **[MED] Red Hat vLLM triage**: watch `vllm:num_requests_running` /
  `num_requests_waiting`; persistent waiting>0 inflates TTFT.

## Q4: prefix caching / RadixAttention measurements

- **[HIGH] KV cache reuse (gingerlabs)**: Qwen3-32B, 20 questions over ONE
  shared document: TTFT 4343 -> 970 ms (-78%), output throughput +254% with
  APC. Correct pattern: [static system] + [shared document] + [unique query
  LAST].
- **[HIGH] vLLM APC design doc**: block-granular (16 tokens), only identical
  LEADING token sequences match; LRU eviction.
- **[HIGH] Optimal prompt structure (theneuralbase)**: dynamic/random tokens
  early in the prompt = zero sharing; even whitespace differences break it.
- **[HIGH] SGLang RadixAttention (lmsys)**: up to 5x on prefix-heavy loads.
- **[HIGH] SGLang vs vLLM 2026 (particula)**: +29% baseline, up to 6.4x on
  prefix-heavy; gap collapses with unique prompts.
- **[MED] squeezebits APC benchmark**: APC with NO shared prefixes adds ~36.7%
  throughput OVERHEAD (hash management); payoff scales with share ratio.
- **[MED] UniCache (SIGMETRICS26)**: LRU vs LFU eviction under mixed loads;
  scan pollution can evict hot shared-document prefixes.

## Q5: LLM-judge latency practices

- **[HIGH] SLMJury (arXiv 2606.07810)**: Phi-4 14B judge = 89.55% oracle
  agreement at 10 output tokens; Qwen3-4B only 1.74% behind; quick verdicts
  beat 8k-token reasoning on math, lose up to 23% on general tasks.
- **[HIGH] LLMTrace judge cascade ADR**: fast classifier handles confident
  cases, only ambiguous band (0.3-0.7) escalates to slow LLM judge.
- **[HIGH] Deterministic vs LLM-judge evals 2026 (futureagi)**: deterministic
  floor catches 30-60% of failures; cascades cut cost 80-90% with no measured
  detection-rate drop on most rubrics.
- **[HIGH] RuVerBench (arXiv 2606.29920)**: batching 4-5 rubrics per call
  drops EVERY tested model by double digits on long-context agentic tasks.
  Strong caution against multi-unit packing for our page checks.
- **[HIGH] SAJA (ACL industry 2026)**: one structured extraction call + cheap
  calibration head = 5-10x fewer calls; confidence triage automates 44% of
  judgments at 99.6% accuracy.
- **[HIGH] Deterministic pre-gate (spinov)**: only UNCERTAIN spans reach the
  expensive judge.
- **[MED] INSPECTOR (arXiv 2601.22588)**: linear probes on hidden states as
  decoding-free judges. **[MED] LLMTrace judge setup**: 60-token outputs,
  strict JSON, prompt caching on hardened system prompt.

---
20+ unique URLs, 5 foragers. Cards feed personas and synthesis.
