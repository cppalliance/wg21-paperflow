# 51 - docling-Batching-Architect

**Verdict:** usable-with-conditions (docling's remote "batching" is concurrent separate HTTP requests, not one multi-unit POST; the portable lever for tapetum is in-paper parallel unit checks, not prompt packing)
**Confidence:** high

## Findings

- [CRITICAL] Docling splits work at three batch tiers with explicit constants: `page_batch_size=4` (pages per pipeline chunk), `elements_batch_size=16` (enrichment), `doc_batch_size=1` / `doc_batch_concurrency=1` (cross-document; experimental). Evidence: `docling/datamodel/settings.py:30-36`. Impact: Tapetum analog is grouping up to `MAX_UNIT_CHECKS=5` units per paper before dispatch; no cross-paper batching in docling's VLM path. Quality risk: none from grouping alone if each unit still gets its own request.

- [CRITICAL] Pages are filled into batches via `chunkify(conv_res.pages, settings.perf.page_batch_size)` in `PaginatedPipeline._build_document`, then each chunk is initialized and passed through `build_pipe` models in order. Evidence: `docling/pipeline/base_pipeline.py:270-282`, `docling/utils/utils.py:11-15`. Impact: For a 20-page doc, VLM sees 5 sequential page-batches of 4, not 20 serial singletons. Our unit checks have no within-paper batching gate (`unit_judge.py:389-408` serial `for unit_id`). Wall saving if we parallelize 5 checks: up to ~4× on the unit phase per paper (~80 s → ~20 s for a 5-check paper), fleet-level ~15-25% on the 3003 s run if unit checks stay decode-bound. Quality risk: MoE batch-composition variance (00-baseline open lever #3).

- [HIGH] **Local vLLM = true client-side batching:** legacy `VllmVlmModel.process_images` and new `VllmEngine.predict_batch` build `llm_inputs = [{"prompt": p, "multi_modal_data": {"image": im}}, ...]` and call **one** `llm.generate(llm_inputs, sampling_params=...)`; outputs are reassembled by enumerate index. Evidence: `docling/models/vlm_pipeline_models/vllm_model.py:312-319,334-352`, `docling/models/inference_engines/vlm/vllm_engine.py:254-322,331-352`. Impact: This eliminates HTTP overhead and maximizes GPU batch fill. We call a remote vLLM pod over HTTP (1 completion = 1 POST), so this pattern does not apply unless we colocate an in-process engine or switch to offline batch mode (05-web ~2× vs HTTP). Server-side continuous batching is a partial substitute, not equivalent.

- [HIGH] **Remote API (`api_vlm` / `ApiVlmEngine`) = N separate HTTP POSTs, not one batched POST:** `predict_batch` submits each `VlmEngineInput` to `_process_single_input`, which calls `api_image_request` → `session.post` (one image + one prompt per request). Concurrency is a `ThreadPoolExecutor(max_workers=min(options.concurrency, len(input_batch)))`; results collected as `[future.result() for future in futures]` preserving submission order. Legacy `ApiVlmModel.process_images` is identical pattern (`ThreadPoolExecutor(max_workers=self.concurrency)` + `executor.map`). Evidence: `docling/models/inference_engines/vlm/api_openai_compatible_engine.py:100-218`, `docling/models/vlm_pipeline_models/api_vlm_model.py:97-186`, `docling/utils/api_image_request.py:165-218`. Impact: Docling's remote path is **client-side concurrent requests**, which vLLM's scheduler already continuous-batches across independent POSTs (`--max-num-seqs 16`, 00-baseline). We already exploit this at **fleet** level (`cli.py:127`, `asyncio.gather` ~32 papers) but **not within-paper** (serial unit loop). Adding in-paper concurrency (≤5) is the direct port; expected saving similar to raising effective in-flight from ~32 to ~32 (unchanged peak) but reducing per-paper serial depth so more papers finish unit phase per wall-clock slice. Quality risk: low if prompts stay isolated per request.

- [HIGH] Remote services require explicit opt-in: `enable_remote_services=True` on pipeline options or `--enable-remote-services` CLI; otherwise `OperationNotAllowed`. Evidence: `docling/models/vlm_pipeline_models/api_vlm_model.py:34-38`, `docling/models/inference_engines/vlm/api_openai_compatible_engine.py:62-66`, `docling/pipeline/vlm_pipeline.py:163-169`. Impact: No speed/security trade hidden in defaults. Our pod is already remote/self-hosted; no gating issue.

- [MED] Default remote concurrency is **1** (`ApiVlmOptions.concurrency=1`, `ApiVlmEngineOptions.concurrency=1`); shipped presets override to **4** (e.g. `GRANITEDOCLING_VLLM_API.concurrency=4`). Evidence: `docling/datamodel/pipeline_options_vlm_model.py:401-410`, `docling/datamodel/vlm_engine_options.py:228`, `docling/datamodel/vlm_model_specs.py:56-68`. Impact: Out-of-box remote docling is serial within a page batch unless tuned. Matches our within-paper serial default; tuning docling to 4 is analogous to `asyncio.gather` on ≤4 unit checks per paper.

- [MED] Result reassembly is **positional, not keyed:** pages collected in iteration order, `zip(pages_with_images, predictions)` or index-aligned `outputs[i]`; invalid/skipped pages omitted from zip but original page list yield order preserved in legacy models. Evidence: `docling/models/stages/vlm_convert/vlm_convert_model.py:205-208`, `docling/models/vlm_pipeline_models/api_vlm_model.py:51-95`, `docling/models/vlm_pipeline_models/vllm_model.py:219-266`. Impact: Parallel unit dispatch must preserve `unit_id → result` mapping (sorted gather by input order, same as `cli.py:1401`). Quality risk: none if mapping is deterministic.

- [MED] Docling does **not** pack multiple distinct page questions into one prompt; `VlmConvertModel` uses the same `model_spec.prompt` for every page in a batch (per-page prompts only in legacy `_build_prompt_safe`). Evidence: `docling/models/stages/vlm_convert/vlm_convert_model.py:177-178`. Impact: Multi-unit tapetum packing (N page rubrics in one call) is **not** docling's VLM pattern and conflicts with RuVerBench-style quality loss (05-web Q5). Do not conflate docling batching with multi-criterion prompt packing.

- [LOW] `page_batch_concurrency` is documented "Currently unused" (`settings.py:33`); threaded `StandardPdfPipeline` uses separate stage `batch_size` defaults (`ocr/layout/table_batch_size=4`) with timeout-based queue drain, not page-level async. Evidence: `docling/datamodel/settings.py:33`, `docling/datamodel/pipeline_options.py:1908-1928`, `docling/pipeline/standard_pdf_pipeline.py:276`. Impact: Docling's LLM/VLM speed comes from page grouping + (remote) thread pool or (local) single generate(), not from parallel page-batch pipelines.

## Client-side batch vs server continuous batch (tapetum mapping)

| Mechanism | Docling | Tapetum today | Portable? |
|---|---|---|---|
| **Client batch, one engine/HTTP call, N sequences** | Local `vllm.generate(llm_inputs)` | Not used (remote OpenAI API = 1 seq/POST) | Only if in-process vLLM or offline engine |
| **Client concurrent N HTTP requests** | `ApiVlmEngine` ThreadPool, default concurrency 1, presets 4 | Fleet `gather` ×32; **within-paper serial** unit checks | **Yes:** `gather` ≤5 unit checks per paper |
| **Server continuous batching** | Benefits remote concurrent path automatically | Already active at 16 seq slots | **Already have**; does not fix in-paper serial chain |
| **Multi-question single prompt** | Not used for VLM | Not used | **No** (quality evidence against) |

Docling-style batched submission for our unit checks = **fire up to 5 independent judge POSTs concurrently per paper** (scoped payloads unchanged), then reassemble by `unit_id` in submission order. That differs from vLLM continuous batching, which merges already-in-flight independent requests at the scheduler: we get continuous batching "for free" only when requests overlap in time. Serial unit checks per paper mean each paper contributes at most **one** unit-check request to the server at a time, underfilling slots during the ~1510-call unit phase despite 32-paper fleet concurrency.

## False-pass hypothesis

In-paper parallel unit checks (docling-remote pattern, concurrency=5) on DeepSeek MoE at `--max-num-seqs 16` change expert routing/noise versus serial execution; a borderline defect on one page is dropped in one ordering and caught in another, violating quality-stability (00-baseline constraint).

## False-fail hypothesis

Keeping unit checks strictly serial while fleet concurrency is 32 leaves server slots idle whenever the active paper cohort is in monolith/metadata (long prefill, short parallel unit phase), inflating queue latency and pushing marginal papers into `UNIT_CHECK_TIMEOUT_SECONDS=120` false failures (00-baseline: ~20 s/call implied, 120 s cap).

## What would change my mind

A 381-paper cold replay with in-paper `asyncio.gather` on unit checks (concurrency=5, payloads unchanged) showing **zero** merged-verdict drift vs v10 serial baseline and ≥30% wall reduction on the unit-check slice would flip verdict to fully **usable** for that lever.
