# 55 - docling-Cache-Strategy

**Verdict:** usable-with-conditions — docling caches pipeline objects and model weights aggressively, but has no library-level conversion-result skip or per-page/per-element fingerprint reuse; only user-script output-exists patterns and a perf-tool mtime cache exist outside the core path.
**Confidence:** high

## Findings

- [CRITICAL] **No content-hash conversion skip in core library.** `DocumentConverter.convert()` / `convert_all()` always execute `_process_document()` for every input; batching only chunks documents for threading (`document_converter.py:658-679`), never checks prior outputs. Evidence: `document_converter.py:725-732`, `document_converter.py:497-548`. Impact: **0 s** saved on the 3003 s cold fleet from docling-style conversion memoization (mechanism absent). Quality risk: none (nothing to mis-skip).

- [CRITICAL] **No finer-grained reuse than whole-document processing.** Commented-out `page_hash` on `Page` (`base_models.py:465`); `document_hash` is a SHA-256 of source bytes for identity/logging only (`utils.py:19-37`, `document.py:178-192`), not used to skip stages. `page_range` limits which pages run but still re-executes the full pipeline on selected pages (`document_converter.py:439-457`). Impact: **0 s** on cold run; docling offers **no pattern** for persona 19 per-unit fingerprints. Quality risk: none.

- [HIGH] **Pipeline instance cache keyed by `(pipeline_class, md5(options))`.** `DocumentConverter` and `DocumentExtractor` keep `initialized_pipelines` under a lock and reuse loaded models across documents with identical serialized options (`document_converter.py:404-409`, `document_converter.py:707-723`, `document_extractor.py:119-122`, `document_extractor.py:302-316`). Regression tests lock this (`test_options.py:516-541`, `test_options.py:555-593`); in-place option mutation broke caching (#3109, `standard_pdf_pipeline.py:622-623`). Impact: amortizes **one-time model init per options hash per process** across a batch (seconds, not minutes on 381 papers if process stays warm); **~0 s** on a cold one-shot CLI that exits per paper. Quality risk: low if fingerprint/options hashing stays stable; **high** if options are mutated in place after first init (historical #3109 bug).

- [HIGH] **Model weight / artifact disk cache only.** Default `~/.cache/docling` (`settings.py:67`), HuggingFace-style `repo_cache_folder` paths (`pipeline_options.py:844-845`, `model_downloader.py:75-116`), CLI `docling-tools models download` (`cli/models.py:88-113`). VLM engines resolve local dirs before download (`vlm/_utils.py:116-125`). Impact: eliminates re-download latency on repeat runs; **~0 s** on cold fleet where weights are already on pod. Quality risk: none.

- [MED] **Intra-conversion page image cache, explicitly cleared.** Per-page `_image_cache` avoids re-rasterizing the same scale during one conversion (`base_models.py:475-507`); cleared after each page batch unless `keep_images` (`base_pipeline.py:285-287`, `standard_pdf_pipeline.py:670-676`). Impact: shaves PDF raster work **within** a conversion, not across LLM judge calls; **negligible** on tapetum-llm (different workload). Quality risk: none.

- [MED] **docling-serve request path: converter-object pool, not result cache.** Separate repo (docs synced v1.21.0); `DOCLING_SERVE_OPTIONS_CACHE_SIZE` default 2 keeps `DocumentConverter` instances with loaded models (`docs/usage/api_server/deployment.md:58-59`, docling-serve `configuration.md` line 61 via web fetch). `DOCLING_SERVE_ENG_LOC_SHARE_MODELS` default false. REST API is submit → poll → fetch result with no documented content-addressed dedup (`rest_api.md:11-18`). Client `job.py:33` caches **task status**, not conversion output. Impact: warm-server latency reduction only; **0 s** on our self-hosted judge pod unless we mirror converter pooling. Quality risk: low.

- [LOW] **Batch "skip already converted" exists only in example scripts, not API.** `run_with_formats_html_rendered.py:35-46` filters inputs where output JSON already exists; `batch_convert.py` has no skip. `render_notebooks.py:14-15` uses mtime idempotency for docs builds. Impact: pattern is **user-owned output-exists**, coarser than our sidecar fingerprint and blind to prompt/schema changes. Quality risk: **high** if copied verbatim without hashing judge inputs.

- [LOW] **Perf-only mtime cache for PDF page counts.** `perfs/iterate_pdf_pages.py:573-624` JSON cache keyed by path + size + mtime_ns; not wired into conversion. Impact: **0 s** on tapetum-llm. Quality risk: none.

- [LOW] **@lru_cache on model factories** (`models/factories/__init__.py:14-40`) and **transformer `use_kv_cache` / vLLM `kv_cache_dtype`** (`pipeline_options_vlm_model.py:304-309`, `vlm/vllm_engine.py:79`) are inference-time KV reuse, not cross-document artifact reuse. Impact: per-call decode only (aligns with 05-web prefix/KV cards), not call-count reduction. Quality risk: none at default settings.

## False-pass hypothesis

Copying docling's example-script "output file exists → skip" into tapetum-llm without hashing prompts, schemas, `_LANE_VERSION`, and ideal verifier identity would silently skip re-judge after a logic or prompt fix while markdown unchanged (our fingerprint explicitly includes those keys at `cli.py:566-615`).

## False-fail hypothesis

None found for docling cache patterns themselves (docling does not skip conversions in-library). A mistaken port of pipeline options MD5 caching without deep-copy discipline could force stale pipeline behavior after option mutation (#3109), causing unnecessary re-conversion or wrong model config — false **quality** failure, not false reject.

## What would change my mind

A docling-serve v1.21+ source file showing content-addressed storage of conversion results (hash of source + options → skip recompute) or persisted per-page stage artifacts reused across runs — absent in the cloned docling repo and not described in synced serve docs.
