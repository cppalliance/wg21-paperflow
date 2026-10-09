# 05 - Web finding cards (5 foragers, 2026-07-23)

## Q1: How does marker parallelize/batch its LLM calls?

- **BaseLLMProcessor - per-document ThreadPoolExecutor, max_concurrency=3** (HIGH)
  https://github.com/datalab-to/marker/blob/master/marker/processors/llm/__init__.py
  All `--use_llm` processors inherit `BaseLLMProcessor`, default `max_concurrency=3`,
  fan-out via `ThreadPoolExecutor`. Synchronous per-call services, no batch API, no asyncio.
- **LLMSimpleBlockMetaProcessor - cross-processor prompt fan-out** (HIGH)
  https://github.com/datalab-to/marker/blob/master/marker/processors/llm/llm_meta.py
  All simple-processor prompts share one pool (default 3 workers), per PDF, not fleet-wide.
- **BaseService/LLMService - synchronous single-request calls, retry only** (HIGH)
  https://github.com/datalab-to/marker/blob/master/marker/services/__init__.py
  timeout=30, max_retries=2, linear backoff; parallelism lives only in the processor layer.
- **Batch CLI - mp.Pool PDF workers + VLM concurrency budget** (MED)
  https://github.com/datalab-to/marker/blob/master/marker/scripts/convert.py
  Whole-PDF process pool, `SURYA_INFERENCE_PARALLEL ~ 1.5x server capacity`; ~25 pg/s
  claim is VLM batch mode, not LLM-judge mode.
- **LLMScorer benchmark - fully serial** (HIGH)
  https://github.com/datalab-to/marker/blob/d63e3d94/benchmarks/overall/scorers/llm.py
  One synchronous Gemini call per sample in a serial loop, 120 s rate-limit backoff.

## Q2: docling VLM/LLM enrichment throughput at corpus scale

- **GPU support - Docling (VLM pipeline & benchmarks)** (HIGH)
  https://docling-project.github.io/docling/usage/gpu/
  Official guidance: decoupled `vllm serve` (granite-docling-258M) with
  `--max-num-seqs 512 --max-num-batched-tokens 8192 --enable-chunked-prefill`,
  client `vlm_options.concurrency=64`, `page_batch_size=64`. 2.0-4.5 pages/s end-to-end.
- **GPU Performance Optimization & Benchmark (Discussion #3442)** (HIGH)
  https://github.com/docling-project/docling/discussions/3442
  L4 corpus benchmark: raising batch size 4->256 and concurrency 1->4 had ZERO
  throughput effect (GIL/orchestration bound, GPU 24-29% util); maintainer recommends
  multi-process workers across documents.
- **Deployment - docling-serve** (HIGH)
  https://docling-project.github.io/docling/usage/api_server/deployment/
  Corpus scaling is architectural: Redis RQ workers, batch S3 endpoints, not
  in-process batching.
- **SmolDocling paper - vLLM model-only throughput** (MED)
  https://arxiv.org/html/2503.11576  0.35 s/page on A100, model-serving only.
- **RTX GPU Acceleration - Docling** (MED)
  https://docling-project.github.io/docling/getting_started/rtx/
  vLLM-served ~4x faster than inline llama.cpp; per-GPU batch guidance 16-128.

## Q3: olmOCR corpus-scale throughput

- **olmOCR technical report** (HIGH) https://arxiv.org/abs/2502.18443
  906 tok/s (L40S) / 3050 tok/s (H100) output throughput, ~$178/M pages, 12% retry
  rate; ~500-page work items, flood-then-drain per work item.
- **olmocr/pipeline.py** (HIGH) https://github.com/allenai/olmocr/blob/main/olmocr/pipeline.py
  Defaults `--workers 20`, `--max_concurrent_requests 1600`, all pages of a work
  item in flight behind one global BoundedSemaphore against vLLM/SGLang.
- **olmocr/work_queue.py** (HIGH) https://github.com/allenai/olmocr/blob/main/olmocr/work_queue.py
  S3-lock distributed queue, 200-300 nodes, ~500-page hashed work items.
- **Ai2 blog** (MED) https://allenai.org/blog/olmocr  ~$190/M pages, 1-to-hundreds of GPUs.
- **Tech report Appendix D.1** (HIGH) https://olmocr.allenai.org/papers/olmocr.pdf
  Explicit rule: flood the inference server with the whole work item, block until
  the queue drains, then next item. Latency traded for sustained GPU utilization.

## Q4: vLLM tuning for many concurrent structured-output requests

- **Optimization and Tuning - vLLM** (HIGH)
  https://docs.vllm.ai/en/latest/configuration/optimization.html
  V1 chunked prefill on by default, decode prioritized; on preemption warnings
  REDUCE max_num_seqs / max_num_batched_tokens, do not raise them. MoE: enable
  expert parallelism.
- **Why MoE models break your vLLM configuration rules - Paralleliq** (HIGH)
  https://www.paralleliq.ai/blog/why-moe-models-break-your-vllm-configuration
  MoE sizing by total params: DeepSeek-class models want `--max-num-seqs 4-8`,
  not dense-model 32-64; raising it causes preemption/recompute slowdowns.
  Directly matches our measured 16->32 regression (+60% wall).
- **Guided decoding performance on vLLM and SGLang - SqueezeBits** (HIGH)
  https://blog.squeezebits.com/guided-decoding-performance-vllm-sglang
  Repetitive identical JSON schemas: XGrammar mask caching wins at batch >= 8;
  vLLM pays a guided-decoding tax (sequential mask generation).
- **vLLM PR #24300 xgrammar bitmask overlap** (HIGH)
  https://github.com/vllm-project/vllm/pull/24300
  Overlapping mask generation with GPU work: +31.5% req throughput on structured
  output benches. Guided JSON overhead is CPU/scheduling-bound.
- **Automatic Prefix Caching - vLLM** (HIGH)
  https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/
  `--enable-prefix-caching` reuses KV for shared system prompts; prefill-only
  gains; client fan-out beyond max-num-seqs just queues server-side.

## Q5: LLM-as-judge harness parallelism defaults

- **Promptfoo rate limits & adaptive concurrency** (HIGH)
  https://www.promptfoo.dev/docs/configuration/rate-limits/
  Default maxConcurrency=4, AIMD adaptation, judge assertions capped at 3,
  disk cache 14-day TTL on by default.
- **DeepEval AsyncConfig** (HIGH) https://deepeval.com/docs/evaluation-flags-and-configs
  asyncio.Semaphore(20) default for judge calls; separate process-level `-n N`.
- **Ragas RunConfig** (HIGH) https://docs.ragas.io/en/stable/references/run_config/
  max_workers=16 default, tenacity retries (max 10), semaphore-bounded executor.
- **LangSmith experiment concurrency** (MED)
  https://docs.langchain.com/langsmith/experiment-configuration
  Default now sequential; positive max_concurrency opt-in; cache opt-in via env var.
- **OpenAI evals thread pool** (MED)
  https://github.com/openai/evals/blob/main/docs/run-evals.md
  10 threads default, 40 s thread timeout, progress checkpoint for resume.
