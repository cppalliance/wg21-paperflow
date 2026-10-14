# 13a - marker (ef16c2c)
**Claims tested:** C1, C2
**Exhaustive:** yes

## Method
Repo: `packages/whisker/research/repos/marker` @ `ef16c2c`. SHA verified via `git rev-parse HEAD`.

Search commands (run from repo root):
```
rg -i -n "openai|anthropic|claude|gemini|litellm|vllm|ollama|chat\.completions|completions\.create|messages\.create|generate_content|GenerativeModel|system_prompt|LLM|VLM|gpt-" --glob "*.py"
rg -n "llm_service\(|\.generate_content\(|chat\.completions|messages\.create|/api/generate|\.generate\(" --glob "*.py"
rg -i -n "vllm|transformers|AutoModel|litellm|pipeline\(" --glob "*.py"
```

Files read in full: all `marker/processors/llm/*.py`, all `marker/services/*.py`, `marker/extractors/page.py`, `marker/extractors/document.py`, `marker/extractors/__init__.py`, `marker/converters/__init__.py`, `marker/converters/pdf.py`, `marker/converters/table.py`, `marker/converters/extraction.py`, `marker/config/parser.py`, `benchmarks/overall/scorers/llm.py`, `benchmarks/overall/elo.py`, `benchmarks/table/gemini.py`, `benchmarks/table/inference.py`, `benchmarks/overall/methods/olmocr.py`, `benchmarks/overall/overall.py`.

## Inventory

### Production processors (`marker/processors/llm/`)

| # | file:line | processor / function | trigger | input | output | role |
|---|-----------|---------------------|---------|-------|--------|------|
| 1 | `llm_meta.py:68` | `LLMSimpleBlockMetaProcessor.get_response` | `use_llm=True` and `llm_service` set (`__init__.py:64-65`, `pdf.py:138-142`); dispatches one call per prompt from nested simple processors | prompt, block crop image, block, pydantic schema from child processor | parsed JSON dict per child schema | other (shared dispatcher for rows 2–6) |
| 2 | `llm_complex.py:54-67` → via `llm_meta.py:68` | `LLMComplexRegionProcessor.block_prompts` | `BlockTypes.ComplexRegion` blocks on any page when `use_llm=True` | block image + `block.raw_text(document)` in prompt | `corrected_markdown` → HTML on block if passes length / "no corrections" gates (`llm_complex.py:69-90`) | refinement |
| 3 | `llm_equation.py:71-103` → via `llm_meta.py:68` | `LLMEquationProcessor.block_prompts` | `BlockTypes.Equation` where `block.polygon.height / page.polygon.height >= min_equation_height` (default 0.06) OR `redo_inline_math=True` (`llm_equation.py:78-84`) | block image + existing block html/raw text | `corrected_equation` HTML with `<math>` tags (`llm_equation.py:106-128`) | refinement |
| 4 | `llm_form.py:65-91` → via `llm_meta.py:68` | `LLMFormProcessor.block_prompts` | `BlockTypes.Form` with at least one `TableCell` child (`llm_form.py:70-73`) | form block image + rendered block HTML | `corrected_html` on block if length gate passes (`llm_form.py:94-114`) | refinement |
| 5 | `llm_handwriting.py:36-66` → via `llm_meta.py:68` | `LLMHandwritingProcessor.block_prompts` | `BlockTypes.Handwriting`; OR `BlockTypes.Text` with zero `Line` children and empty `raw_text` (`llm_handwriting.py:43-47`) | block image only (generation prompt) | `markdown` → HTML on block (`llm_handwriting.py:68-82`) | extraction |
| 6 | `llm_image_description.py:42-67` → via `llm_meta.py:68` | `LLMImageDescriptionProcessor.block_prompts` | `BlockTypes.Picture` or `Figure` when `extract_images=False` (default True skips all blocks, `llm_image_description.py:44-46`) | block image + `raw_text` | `image_description` on `block.description` (`llm_image_description.py:69-83`) | refinement |
| 7 | `llm_mathblock.py:176` | `LLMMathBlockProcessor.process_rewriting` | only when `redo_inline_math=True` (`llm_mathblock.py:77-78`); blocks: all `TextInlineMath`; Text/Caption/SectionHeader/Footnote/ListItem lines with `"math"` format; plus page-wide expansion when math-block ratio ≥ `inlinemath_min_ratio` (0.4, `llm_mathblock.py:127-135`) | block image + extracted block HTML | `corrected_html` on block (`llm_mathblock.py:178-195`) | refinement |
| 8 | `llm_sectionheader.py:125` | `LLMSectionHeaderProcessor.process_rewriting` | at least one `SectionHeader` in document (`llm_sectionheader.py:147-154`); single document-wide call | JSON of all section headers (bbox, id, html); **no image** (`llm_sectionheader.py:125-127`) | corrected header html levels on matching blocks (`llm_sectionheader.py:134-139`) | refinement |
| 9 | `llm_page_correction.py:159` | `LLMPageCorrectionProcessor.process_rewriting` | **only if** `block_correction_prompt` is non-null (`llm_page_correction.py:269-270`); one call per page when enabled | full-page lowres image + JSON of all `page.structure_blocks` (id, block_type, bbox, html) + user prompt (`llm_page_correction.py:150-159`) | `correction_type` + block reorder and/or html rewrites applied in-place (`llm_page_correction.py:166-178`) | refinement |
| 10 | `llm_table.py:199` | `LLMTableProcessor.rewrite_single_chunk` | `BlockTypes.Table` or `TableOfContents` with `TableCell` children; row_count ≤ `max_table_rows` (175); chunked by `max_rows_per_batch` (60); may recurse up to `max_table_iterations` (2) if score < 4 (`llm_table.py:129-225`) | table crop image + batch HTML | `corrected_html` → reparsed `TableCell` structures (`llm_table.py:207-240`) | refinement |
| 11 | `llm_table_merge.py:265` | `LLMTableMergeProcessor.process_rewriting` | adjacent table pairs passing geometric heuristics (subsequent-page, same-page vertical/horizontal, new-column; `llm_table_merge.py:169-207`); skipped if `no_merge_tables_across_pages=True` (`llm_table_merge.py:158-160`) | two table images + both tables' HTML | merge bool + direction → joined cells/images (`llm_table_merge.py:272-293`) | refinement |

**LLMPageCorrectionProcessor detail:** Receives marker's **already-built** per-page block list (normalized JSON with rendered `html` from `json_to_html(block.render(document))`, `llm_page_correction.py:143-147`, `__init__.py:98-103`) plus the **source page image**. Prompt instructs: "analyze the blocks and the image" and correct reorder/type/html (`llm_page_correction.py:37-70`). It is **correction of marker's own pipeline output** guided by the source image, not a separate post-render markdown QA pass. Default `block_correction_prompt=None` makes the processor a no-op unless CLI `--block_correction_prompt` is set (`llm_page_correction.py:33-36`, `269-270`, README.md:128).

**Block-selective coverage (`--use_llm`):** PdfConverter registers processors above but each fires only on matching block types/thresholds (`pdf.py:89-99`). A text-only page with no ComplexRegion, Equation, Form, Handwriting, Table, etc. receives **zero** LLM calls unless `block_correction_prompt` enables page correction or `redo_inline_math` expands math processing.

### Extractors (production, structured extraction path)

| # | file:line | function | trigger | input | output | role |
|---|-----------|----------|---------|-------|--------|------|
| 12 | `extractors/page.py:119` | `PageExtractor.inference_single_chunk` | `ExtractionConverter` with `page_schema` set; chunks of `extraction_page_chunk_size` (3) pages of markdown (`extraction.py:71`, `page.py:148-160`) | page-markdown text + JSON schema (no image) | `PageExtractionSchema` notes per chunk | extraction |
| 13 | `extractors/document.py:127` | `DocumentExtractor.__call__` | after page extraction completes | aggregated page notes + schema | `DocumentExtractionSchema` with final JSON string | extraction |

### Service backends (production transport; all implement `BaseService.__call__`)

| # | file:line | class | API | role |
|---|-----------|-------|-----|------|
| 14 | `services/gemini.py:79` | `BaseGeminiService` / `GoogleGeminiService` | `client.models.generate_content` | other (backend) |
| 15 | `services/vertex.py:7-28` | `GoogleVertexService` | inherits `gemini.py:79` | other (backend) |
| 16 | `services/openai.py:92` | `OpenAIService` | `client.beta.chat.completions.parse` | other (backend) |
| 17 | `services/azure_openai.py:74` | `AzureOpenAIService` | `client.beta.chat.completions.parse` | other (backend) |
| 18 | `services/claude.py:106` | `ClaudeService` | `client.messages.create` | other (backend) |
| 19 | `services/ollama.py:57` | `OllamaService` | `POST {base}/api/generate` | other (backend) |

### Eval / benchmark harness (offline)

| # | file:line | function | trigger | input | output | role |
|---|-----------|----------|---------|-------|--------|------|
| 20 | `benchmarks/overall/scorers/llm.py:105` → `144` | `LLMScorer.llm_rater` / `llm_response_wrapper` | `--scores` includes `llm` in overall benchmark (`registry.py:13`) | page-0 PDF render image + **already-extracted markdown** | component scores 0–5 (`llm.py:15-84`, `131-134`) | eval-harness |
| 21 | `benchmarks/overall/elo.py:125` → `145` | `EloScorer.llm_rater` / `llm_response_wrapper` | ELO comparison runs | page image + pairwise markdown comparison prompt | winner label | eval-harness |
| 22 | `benchmarks/table/gemini.py:37` | `gemini_table_rec` | `--use_gemini` in table benchmark (`inference.py:153-155`) | table crop image | HTML table JSON | eval-harness |
| 23 | `benchmarks/overall/methods/olmocr.py:48` | `convert_single_page` | `--methods` includes `olmocr` (`overall.py:151-157`) | PDF page image via olmOCR prompt | extracted text via `model.generate` | eval-harness (external method baseline, not marker pipeline) |

### Scripts / examples (wiring only; marked)

| file:line | note |
|-----------|------|
| `scripts/convert.py:85` | passes `config_parser.get_llm_service()` to converter |
| `scripts/convert_single.py:36` | same |
| `scripts/server.py:101` | same |
| `scripts/streamlit_app.py:38` | same |
| `scripts/extraction_app.py:44` | same |
| `examples/marker_modal_deployment.py:235` | `llm_service=... if use_llm else None` |
| `config/parser.py:117-125` | `get_llm_service()` factory; returns None unless `use_llm` |

No LLM invocation inside converters themselves beyond processor dispatch. `TableConverter` (`table.py:17-24`) subsets LLM processors to table/form/complex only.

## Verdict on the claim(s)

**C1: REFUTED** for marker @ ef16c2c.

Refuting production paths (judge already-produced conversion output against source, per block/page/chunk):
- Refinement processors (rows 2–4, 6–11) always present marker-generated HTML/text plus source image (or page image for page correction) and ask the model to compare and optionally rewrite (`llm_table.py:47-64`, `llm_form.py:14-23`, `llm_mathblock.py:34-43`, etc.).
- `LLMPageCorrectionProcessor` (`llm_page_correction.py:159`) is an explicit per-page pass over marker block JSON + page image when `block_correction_prompt` is set.

Refuting eval-harness path (counts per charter line 14):
- `benchmarks/overall/scorers/llm.py:15-30` defines an LLM rater that compares extracted markdown to the page image and scores fidelity; invocation at `llm.py:144`.

These are inline pipeline refinement or offline scoring, not a tapetum-style post-golden verification lane, but they match C1's operative definition: LLM/VLM judging already-produced conversion output against the source document at page/chunk/block granularity.

**C2:** All 23 inventory rows above carry file:line and role (extraction / refinement / eval-harness / other).

## Coverage gaps
None for production Python under `marker/` and `benchmarks/`. Test files (`tests/processors/test_llm_processors.py`, `tests/services/test_service_init.py`, etc.) contain mocks, not additional live call paths; not read line-by-line. No `.generate(` hits outside `olmocr.py:48`. No `litellm`, `vllm`, or direct `transformers` inference in production `marker/` code.

## What could still hide a counterexample
Runtime-only processor overrides via `--processors` CLI strings not statically enumerated here (would still use same `llm_service` backends). Jupyter/notebook paths: none found in repo. Dynamic `llm_service` class strings outside documented services: only classes under `marker/services/` implement `__call__`.
