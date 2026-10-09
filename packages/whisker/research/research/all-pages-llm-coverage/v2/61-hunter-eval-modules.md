# 61 - Adversarial counterexample hunter (eval/bench/qa/metrics modules)
**Claims tested:** C1
**Exhaustive:** no (245 pattern-matched source files across 31 repos; all conversion-output scoring modules read in full; CI/url/pydantic “validation” hits and vendored `.venv` excluded from scoring inventory; benchmark data artifacts excluded)

## Method
PowerShell directory/file enumeration under `packages/whisker/research/repos/` (31 clones) with path/name filters: `eval|bench|metric|score|judge|valid|qa` on `*.py,*.rs,*.java,*.go,*.ts,*.js,*.sh,*.hs,*.yml,*.yaml`, excluding `.git`, `node_modules`, `.venv`, `history/`, `prediction/`, `__pycache__`, `docs/benchmark/` data trees.

Supplemental ripgrep (case-insensitive) for LLM call sites in scoring modules:
`openai`, `anthropic`, `claude`, `gemini`, `google.genai`, `genai`, `litellm`, `vllm`, `chat.completions`, `messages.create`, `generate_content`, `GenerativeModel`, `generateText`, `gpt-`.

Required minimums read in full: `olmocr/olmocr/bench/*`, `marker/benchmarks/**`, `unstructured/unstructured/metrics/**`, `opendataloader-bench-tmp/src/evaluator*.py`, `nougat/nougat/metrics.py`, `docling/**/docling-evaluate.py`, MinerU (no dedicated eval package found), surya (no benchmark eval package found).

## Inventory
Verdict key: **LLM-scored** = scores already-produced conversion/extraction output quality using an LLM/VLM; **deterministic** = scores output without LLM; **not-output-scoring** = eval/bench/metrics code that does not score conversion output quality.

### marker (PDF→MD benchmarks) — **C1 REFUTATION**
| Module | Role | Output scoring? | LLM calls | Verdict |
|--------|------|---------------|-----------|---------|
| `marker/benchmarks/overall/scorers/llm.py:94-154` | `LLMScorer.__call__` takes pre-built `markdown` + renders PDF page image; Gemini rates fidelity | yes (per benchmark sample/page) | `client.models.generate_content(model="gemini-2.0-flash-001", ...)` at `llm.py:144-152` | **LLM-scored** |
| `marker/benchmarks/overall/overall.py:56-59` | Invokes registered scorers on `method_md` after method produces markdown | orchestrates scoring | none in scorer dispatch | **LLM-scored** (when `--scores llm`) |
| `marker/benchmarks/overall/scorers/heuristic.py:10-47` | Rapidfuzz alignment vs GT blocks | yes | none | deterministic |
| `marker/benchmarks/overall/scorers/clean.py` | Markdown normalization helper | helper | none | deterministic |
| `marker/benchmarks/table/scoring.py:1-110` | TEDS tree edit on HTML tables | yes (table HTML) | none | deterministic |
| `marker/benchmarks/table/table.py:19-76` | Runs inference then TEDS scoring | yes | none in scoring path | deterministic |
| `marker/benchmarks/table/gemini.py:28-47` | Gemini **extracts** table HTML from image (competitor method, not scoring) | no (extraction) | `generate_content` at `gemini.py:37-45` | not-output-scoring |
| `marker/benchmarks/verify_scores.py:5-23` | Threshold check on saved JSON scores | reads scores | none | deterministic |

### olmocr (olmOCR-bench)
| Module | Role | Output scoring? | LLM calls | Verdict |
|--------|------|---------------|-----------|---------|
| `olmocr/olmocr/bench/benchmark.py:33-137` | Per-page MD vs JSONL rules via `test.run(md_content)` | yes (per pdf/page) | none | deterministic |
| `olmocr/olmocr/bench/tests.py:114-881` | Rule tests: fuzzy text, tables, math (KaTeX render), order | yes | none | deterministic |
| `olmocr/olmocr/bench/table_parsing.py` | Table parse helpers for tests | helper | none | deterministic |
| `olmocr/olmocr/bench/katex/render.py` | Equation render/compare | yes (math tests) | none | deterministic |
| `olmocr/olmocr/bench/utils.py` | Bootstrap CI / stats | aggregate | none | deterministic |
| `olmocr/olmocr/bench/report.py` | HTML report generation | reporting | none | not-output-scoring |
| `olmocr/scripts/eval/runeval.py:19-80` | DocumentEditSimilarity vs gold (per page key) | yes | none | deterministic |
| `olmocr/scripts/eval/dolma_refine/metrics.py` | Edit-distance metrics | yes | none | deterministic |
| `olmocr/scripts/eval/scoreelo.py` | Elo from human review HTML | indirect | none | not-output-scoring |
| `olmocr/olmocr/bench/scripts/run_difference.py:26-64` | LLM compares page image to ChatGPT+Gemini outputs | partial (inline regen via `run_chatgpt`/`run_gemini` at `:21-23`) | `client.chat.completions.create` at `:47-60` | not-output-scoring (generates outputs first) |
| `olmocr/olmocr/bench/scripts/screen_pdfs.py:48-70` | PII/resume screening of benchmark PDFs | no | `chat.completions.create` at `:54-70` | not-output-scoring |
| `olmocr/olmocr/bench/miners/*_gpt*.py`, `mine_tables_gemini.py` | Mine benchmark **test cases** | no | various GPT/Gemini miners | not-output-scoring |
| `olmocr/olmocr/bench/runners/run_*.py` | Produce candidate MD for bench | extraction runners | LLM in some runners (extraction, not scoring) | not-output-scoring |

### opendataloader-bench-tmp
| Module | Role | Output scoring? | LLM calls | Verdict |
|--------|------|---------------|-----------|---------|
| `src/evaluator.py:94-125` | Orchestrates GT vs pred markdown metrics | yes (per document) | none | deterministic |
| `src/evaluator_reading_order.py:22-40` | Rapidfuzz NID | yes | none | deterministic |
| `src/evaluator_table.py` | TEDS-style table similarity | yes | none | deterministic |
| `src/evaluator_heading_level.py` | Markdown heading-level match | yes | none | deterministic |
| `src/evaluator_table_detection.py` | Table detection overlap | yes | none | deterministic |
| `src/evaluator_triage.py` | Triage helper | utility | none | not-output-scoring |

### unstructured
| Module | Role | Output scoring? | LLM calls | Verdict |
|--------|------|---------------|-----------|---------|
| `unstructured/metrics/evaluate.py:125-898` | CCT accuracy, table structure, element type, object detection calculators | yes | none | deterministic |
| `unstructured/metrics/text_extraction.py` | Weighted edit distance | yes | none | deterministic |
| `unstructured/metrics/table/table_eval.py` | Table structure/content accuracy | yes | none | deterministic |
| `unstructured/metrics/object_detection.py` | Layout F1/mAP | yes (layout) | none | deterministic |
| `unstructured/metrics/element_type.py` | Element-type frequency match | yes | none | deterministic |
| `unstructured/scripts/performance/benchmark_partition.py` | Throughput bench | no | none | not-output-scoring |

### nougat
| Module | Role | Output scoring? | LLM calls | Verdict |
|--------|------|---------------|-----------|---------|
| `nougat/nougat/metrics.py:27-44` | BLEU/METeor/edit distance vs GT markdown | yes | none (NLTK) | deterministic |

### docling
| Module | Role | Output scoring? | LLM calls | Verdict |
|--------|------|---------------|-----------|---------|
| `docs/examples/agent_skill/.../docling-evaluate.py:133-177` | Heuristic thresholds on exported JSON/MD (density, duplicates, replacement chars) | yes (quality heuristics) | none | deterministic |
| No vendored `docling-eval` package at pinned SHA | — | — | — | NOT VERIFIED (external package) |

### langextract
| Module | Role | Output scoring? | LLM calls | Verdict |
|--------|------|---------------|-----------|---------|
| `benchmarks/benchmark.py` | Runs `langextract.extract()` (LLM extraction) and counts entities | measures extraction, not post-hoc output QA | via `extract()` | not-output-scoring |
| `benchmarks/fuzzy_benchmark.py` | Resolver alignment micro-bench | no | none | not-output-scoring |

### camelot (table extraction bench)
| Module | Role | Output scoring? | LLM calls | Verdict |
|--------|------|---------------|-----------|---------|
| `bench/_metrics.py:24-50` | TEDS proxy, detection F1 | yes (tables) | none | deterministic |
| `bench/benchmark_icdar.py`, `benchmark_fintabnet.py` | ICDAR/FinTabNet eval drivers | yes | none | deterministic |

### grobid
| Module | Role | Output scoring? | LLM calls | Verdict |
|--------|------|---------------|-----------|---------|
| `grobid-trainer/.../EndToEndEvaluation.java:52+` | TEI field F1 vs gold XML | yes (GROBID XML fields, not MD conversion) | none | deterministic (different output type) |
| `EvaluationUtilities.java`, `PatentEvaluation.java`, `EvaluationDOIMatching.java` | Trainer eval helpers | yes (NER/fields) | none | deterministic |

### firecrawl
| Module | Role | Output scoring? | LLM calls | Verdict |
|--------|------|---------------|-----------|---------|
| `apps/api/src/services/monitoring/judgeChange.ts:138-145` | LLM judges whether scrape **diff** matters for monitor goal | no (change detection, not conversion QA) | `generateText` + `gemini-3-flash-preview` | not-output-scoring |
| `apps/api/src/services/monitoring/search/judge.ts:20-48` | Prompt builder for search relevance | no | none in file | not-output-scoring |
| `.github/scripts/eval_run.py:16-26` | POST to external eval API | unknown | none locally | not-output-scoring |

### img2table
| Module | Role | Output scoring? | LLM calls | Verdict |
|--------|------|---------------|-----------|---------|
| `src/img2table/tables/metrics.py:16+` | CV character-length heuristics for table layout | no (internal CV tuning) | none | not-output-scoring |

### opendataloader-pdf / pandoc / mdream / html-to-markdown-py
| Module | Role | Verdict |
|--------|------|---------|
| `opendataloader-pdf/scripts/experiments/docling_*_bench.py` | Latency/throughput | not-output-scoring |
| `pandoc/benchmark/benchmark-pandoc.hs` | Conversion speed | not-output-scoring |
| `mdream/bench/*.ts`, `crates/core/benches/convert_bench.rs` | Perf | not-output-scoring |
| `html-to-markdown-py/tools/benchmark-harness/src/bench.rs` | Perf | not-output-scoring |

### MinerU, surya, Dolphin, html2text, markdownify, markitdown, node-html-markdown, pdf-to-markdown, pdfplumber, PyMuPDF, pymupdf4llm, tabula-java, tabula-java-tmp, turndown, html-to-markdown-go, PDF-Extract-Kit (docs only)
No executable eval/bench module scoring conversion/extraction **output quality** found at pinned SHAs (MinerU/surya hits are internal model `score` tensors or OCR postprocess, not QA harnesses).

## Verdict on the claim(s)
**REFUTED** — `marker/benchmarks/overall/scorers/llm.py:94-154` implements an eval-harness code path where an already-produced markdown conversion (`method_md` from `overall.py:48-59`) is judged against the source PDF page image by Gemini (`generate_content` at `llm.py:144-152`). This is per-sample/per-page output verification using an LLM/VLM, matching the tapetum_llm lane shape. Benchmark/eval harnesses count per charter.

## Coverage gaps
- 245 pattern-matched source files not all read line-by-line; excluded categories (CI validation, URL validation, lockfile validation, pydantic validators inside `langextract/.venv`) not individually listed.
- `firecrawl` remote eval service behind `eval_run.py` not inspected (no local scoring code).
- External `docling-eval` PyPI package not vendored in clone.
- `PDF-Extract-Kit/docs/**/evaluation.rst` documentation only, no scoring code in clone.

## What could still hide a counterexample
- LLM output-verification buried under non-matching path names (e.g. `quality`, `audit`, `review`, `verify`) in repos marked “none found”.
- Production (non-benchmark) verification paths in repos not covered by path filter; this hunt focused on eval/bench/qa/metrics/scoring surfaces per task brief.
- Remote-only eval APIs (firecrawl) whose server-side logic is not in corpus.
