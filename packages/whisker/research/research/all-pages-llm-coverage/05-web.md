# 05 - Web finding cards (all-pages-llm-coverage)

Date: 2026-07-22. 5 Composer foragers, 25 cards, deduplicated.

## Q1: Does docling use an LLM/VLM per page, and how is full coverage guaranteed?

- **Docling Pipelines Reference** - https://docling-project.github.io/docling/examples/agent_skill/docling-document-intelligence/pipelines/ - Two PDF families: default standard pipeline (deterministic parse + OCR + neural layout, NO generative LLM per page) and VLM pipeline (page image -> one VLM call per page, Granite Docling default, prompt "Convert this page to docling."). [HIGH]
- **VlmPipeline API docs** - https://docling-project-docling.mintlify.app/api/pipelines/vlm - VLM path runs inference on every page; full-page coverage is architectural (paginated pipeline over all pages), not probabilistic. `force_backend_text=True` hybrid: VLM predicts structure, backend supplies literal text. [HIGH]
- **Confidence scores** - https://docling-project.github.io/docling/concepts/confidence_scores/ - Page-level and doc-level scores/grades (`layout_score`, `ocr_score`, `parse_score`, `table_score`) are a POST-conversion heuristic QA layer for routing low-quality outputs to manual review; distinct from extraction. [HIGH]
- **GPU support (VLM batching)** - https://docling-project.github.io/docling/usage/gpu/ - `vlm_options.concurrency` (default 1) and `page_batch_size` (default 4) tune throughput only; batching never skips pages. [MED]
- **granite-docling-258M model card** - https://huggingface.co/docling-project/granite-docling-2stage-258m - ~0.35 s/page on A100 via vLLM; "Document Element QA" prompts are optional structural Q&A, not the conversion default. [HIGH]

## Q2: How does langextract guarantee full-document coverage?

- **Chunking Strategy** - https://google-langextract-27.mintlify.app/concepts/chunking-strategy - Sentence-aware chunking via `max_char_buffer`; `extraction_passes` re-runs ALL chunks sequentially, merges first-pass-wins on overlapping `char_interval`s. Recall improvement, not a coverage guarantee. [HIGH]
- **Source Grounding** - https://google-langextract-27.mintlify.app/concepts/source-grounding - Every extraction aligned to absolute `char_interval`; unalignable extractions get `char_interval=None` (per-extraction verification filter, NOT a chunk-coverage check). [HIGH]
- **Long-document example** - https://github.com/google/langextract/blob/main/docs/examples/longer_text_example.md - Multi-pass = independent full re-processings merged for recall; docs frame it as sensitivity, not a formal guarantee every region was captured. [HIGH]
- **annotation.py** - https://github.com/google/langextract/blob/main/langextract/annotation.py - Progress tracks characters processed, no post-run audit that all chunks succeeded; empty model output raises `InferenceOutputError` and aborts the document. [HIGH]
- **Releases / retry PR** - https://github.com/google/langextract/releases - `suppress_parse_errors=True` (default in `extract()`) silently drops a failed chunk's extractions and continues; per-chunk retry only for transient API errors. No completion certificate. [HIGH]

## Q3: olmOCR-Bench methodology

- **olmOCR-Bench README** - https://github.com/allenai/olmocr/tree/main/olmocr/bench - 1,403 single-page PDFs, 7,010 machine-checkable unit tests in five classes. LLMs used to MINE tests (with human review), never to score. [HIGH]
- **olmOCR paper** - https://olmocr.allenai.org/papers/olmocr.pdf - Explicitly avoids LLM-as-judge; every page gets a mandatory baseline test (non-empty output, no runaway repetition) so each page is covered by at least one deterministic test. [HIGH]
- **bench/tests.py** - https://github.com/allenai/olmocr/blob/main/olmocr/bench/tests.py - Evaluation loop fully programmatic: rapidfuzz/fuzzysearch, table parsers, KaTeX rendering, per-page `BaselineTest`. No LLM in execution. [HIGH]
- **Issue #307** - https://github.com/allenai/olmocr/issues/307 - Maintainers confirm miner scripts + Flask review app; LLMs in creation pipeline only. [MED]
- **olmOCR 2 blog** - https://allenai.org/blog/olmocr-2 - Same deterministic unit-test framework powers RLVR training rewards; synthetic tests derived from Claude-rendered ground-truth HTML. [MED]

## Q4: LLM-as-judge exhaustive vs sampling in document-conversion eval

- **ParseBench (run-llama)** - https://github.com/run-llama/ParseBench - ~2,000 human-verified pages, 169K+ rule-based tests, every page scored exhaustively; authors explicitly reject LLM-as-judge in favor of deterministic pass/fail. [HIGH]
- **pdf-parse-bench (arXiv 2603.18652)** - https://arxiv.org/abs/2603.18652 - LLM judge applied exhaustively to every matched TABLE pair (451 tables, 100 PDFs) because rule metrics correlate poorly with humans (TEDS r=0.68 vs judge r=0.93 after 1,500+ human ratings). Full element coverage, scoped to hard semantic units, not whole-document QA. [HIGH]
- **Agreeableness bias (arXiv 2510.11822)** - https://arxiv.org/html/2510.11822v2 - 14 LLM validators: TPR >96% but TNR typically <25%; judges pass incorrect outputs and inflate quality. Mitigation: minority-veto ensembles + calibration on human-labeled sets. [HIGH]
- **Reporting LLM-judge evals (arXiv 2511.21140)** - https://arxiv.org/abs/2511.21140 - Raw judge pass rates are biased when true error prevalence is low (exactly the many-mostly-fine-pages setting); Rogan-Gladen correction with calibration set. [HIGH]
- **Clinical multi-stage validation (arXiv 2604.06028)** - https://arxiv.org/pdf/2604.06028 - At 76K-note scale: cheap rules + grounding first, judge LLM only on high-uncertainty subset. Routed deep-validation as the practical alternative to exhaustive judging. [MED]

## Q5: marker --use_llm coverage and cost

- **DeepWiki LLM Processors** - https://deepwiki.com/datalab-to/marker/6.2-llm-processors - `--use_llm` = block-selective processors (Table, Form, Equation, ComplexRegion, Handwriting, Picture, SectionHeader...), each with skip thresholds; reject-and-keep validation preserves originals on bad LLM output (length-ratio 33-50%, balanced tags, table self-score retry <4/5). [HIGH]
- **marker README** - https://github.com/datalab-to/marker - Hybrid accuracy boost on top of layout/OCR pipeline, not a replacement; `--processors` narrows scope; `--block_correction_prompt` for custom page-level correction. [HIGH]
- **converters/pdf.py** - https://github.com/datalab-to/marker/blob/master/marker/converters/pdf.py - LLM processors gated by `use_llm` + block-type matching; a text-only page may incur ZERO LLM calls. Cost proportional to qualifying blocks, not page count. [HIGH]
- **Issue #804** - https://github.com/datalab-to/marker/issues/804 - Maintainer: use_llm does not offload conversion to LLMs; token totals written to `*_meta.json` per run. [HIGH]
- **Issue #871** - https://github.com/datalab-to/marker/issues/871 - LLM usage restrictable to a single processor; one shared LLM service per run. [MED]
