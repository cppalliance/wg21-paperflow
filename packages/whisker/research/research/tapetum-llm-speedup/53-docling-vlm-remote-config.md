# 53 - docling-VLM-Remote-Config

**Verdict:** usable-with-conditions — Docling's decoupled vLLM pattern (match client concurrency to server slots, batch pages before dispatch) is sound and partially matches our setup, but their main throughput lever is in-document page parallelism that our serial per-paper judge chain deliberately lacks.
**Confidence:** high

## Findings

- [CRITICAL] Docling's official GPU recipe pairs a vLLM server at `--max-num-seqs 512` with client `concurrency=64` and `settings.perf.page_batch_size=64`, with explicit rule `page_batch_size >= concurrency`. Evidence: `docs/usage/gpu.md:76-111`, `docs/examples/gpu_vlm_pipeline.py:60-77`. Impact: on our 16-slot MoE pod, docling would cap client concurrency at ~16 (not 32) and raise in-flight page/call batch to match; blindly copying their 64/512 ratio is wrong for our hardware but the **match-client-to-server-slots** rule is portable — potential ~0-15% wall saving if 32→16 reduces queue thrashing (quality risk: none if slots stay saturated), or wasted capacity if we were already slot-bound.

- [HIGH] Remote VLM concurrency is a manual knob, default **1**, not auto-discovered from the server. Legacy `ApiVlmOptions.concurrency` default 1, timeout 60s (`docling/datamodel/pipeline_options_vlm_model.py:391-410`); new-runtime `ApiVlmEngineOptions.concurrency` default 1, timeout 60s (`docling/datamodel/vlm_engine_options.py:226-228`); shipped API presets use concurrency **2–4**, timeout **90–120s** (`docling/datamodel/vlm_model_specs.py:56-69,336-350`). Impact: docling offers no magic auto-tuner we are missing; our c=32 must be justified against `--max-num-seqs 16` manually. Quality risk: none.

- [HIGH] Within each page batch, API requests run concurrently via `ThreadPoolExecutor(max_workers=min(concurrency, len(batch)))` — legacy path (`docling/models/vlm_pipeline_models/api_vlm_model.py:185`) and new runtime (`docling/models/inference_engines/vlm/api_openai_compatible_engine.py:202-212`). Pages arrive in batches of `settings.perf.page_batch_size` (default **4**, `docling/datamodel/settings.py:32`; fed by `docling/pipeline/base_pipeline.py:270-272`). Impact: docling parallelizes **within a document** up to batch size; our tapetum serializes 6 LLM calls per paper (`00-baseline.md:36-38`). Adopting in-paper parallel unit checks is the portable analogue — estimated 40-70% per-paper wall reduction on multi-call papers; quality risk: MoE batch-composition variance (noted in 00-baseline open levers).

- [HIGH] HTTP retry policy for remote VLM: `_RETRY_TOTAL=5`, `_RETRY_BACKOFF_FACTOR=0.1`, `_RETRY_STATUS_FORCELIST=(429,500,502,503,504)`, `respect_retry_after_header=True` on POST (`docling/utils/api_image_request.py:24-40`). Impact: our 55 retries (~100s, 00-baseline) may lack this layered transport retry; adding equivalent retry-on-429/5xx could shave transient failures without re-running full papers. Quality risk: low if capped and idempotent.

- [MED] Per-request timeout defaults **60s** (ApiVlmOptions/ApiVlmEngineOptions); docs/examples use **90–120s** (`docs/usage/gpu.md:99-101`, `docs/examples/agent_skill/docling-document-intelligence/pipelines.md:200`). Separate `document_timeout` recommended **90–120s** for production (`docling/datamodel/pipeline_options.py:1171-1179`). Our **120s** per-call timeouts align with docling's upper range; our **900s** paper budget is coarser than their per-document cap. Impact: timeout tuning alone unlikely to move the 3003s cold run materially. Quality risk: lowering below 120s risks false-fail on long prefill.

- [MED] Streaming SSE path with `GenerationStopper` early-abort closes the HTTP connection to stop server-side decode (`docling/utils/api_image_request.py:263-378`, triggered from `api_openai_compatible_engine.py:157-175`). Impact: cuts wasted decode on repetition/stop-string hits; we lack an equivalent streaming abort knob. Potential decode savings on runaway outputs; quality risk: premature abort if stop criteria too aggressive.

- [LOW] vLLM server flags in docling docs: `--max-num-batched-tokens 8192`, `--enable-chunked-prefill`, `--gpu-memory-utilization 0.9` alongside `--max-num-seqs 512` (`docs/usage/gpu.md:76-81`). Inline vLLM engine accepts `max_num_batched_tokens`, `tensor_parallel_size`, `gpu_memory_utilization` via `extra_generation_config` (`docling/models/vlm_pipeline_models/vllm_model.py:67-86,172-178`). Impact: server-side tuning already partially in our stack (16 slots vs their 512 for a 258M VLM); not directly comparable to MoE judge. Quality risk: n/a (infra).

- [LOW] Docling service client (separate from VLM pipeline) defaults `DEFAULT_MAX_CONCURRENCY=8`, cap **512**, job timeout **300s** (`docling/service_client/client.py:122-123`, `docling/cli/remote.py:266-278`). Picture-description API: concurrency default **1**, timeout **20s** (`docling/datamodel/pipeline_options.py:740-757`). Impact: confirms docling keeps document-level and stage-level concurrency separate; our single `_DEFAULT_CONCURRENCY=32` conflates paper-level fan-out with no per-stage batch coupling. Quality risk: none.

## False-pass hypothesis

Raising client concurrency toward docling's GPU example (64) without raising server `--max-num-seqs` beyond 16 would increase queue depth and MoE expert-switch variance, producing run-to-run verdict drift on borderline unit checks while still returning structured output (silent quality-stability regression, not obvious HTTP failures).

## False-fail hypothesis

Adding docling-style streaming early-abort (`GenerationStopper`) on unit-check responses could truncate valid defect lists when the model emits stop-like substrings in quoted source text before the schema completes, causing false FAIL/review on clean conversions.

## What would change my mind

A measured A/B on our pod: client concurrency 16 vs 32 vs 64 at fixed `--max-num-seqs 16`, reporting slot utilization (`num_requests_running/waiting`), per-call latency p50/p99, and verdict fingerprint drift across 381 papers — if 32 equals 16 on wall and stability, docling's match-slots rule does not apply to our serial-per-paper judge shape.
