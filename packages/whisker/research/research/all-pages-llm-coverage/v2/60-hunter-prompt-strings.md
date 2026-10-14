# 60 - Hunter: verification-style prompt strings
**Claims tested:** C1
**Exhaustive:** yes (all 31 clones under `packages/whisker/research/repos/` searched; every pattern hit near an LLM call site or in a prompt string constant read and classified)

## Method
Exact search commands run:
```text
rg -i -n "is missing|faithfully|compare the|original document|source document|check whether|correctly convert|correct convert|evaluate the" packages/whisker/research/repos/
rg -i -n "compare the|faithfully|verify if|evaluate the markdown|Compare the extracted|Compare the html|Compare the image|quality of the markdown|faithful to the original|Please verify|correctly convert|check whether.*convert" packages/whisker/research/repos/ --glob "*.py"
rg -i -n "prompt|system|instructions|compare|judge|verify|faithful|evaluate|quality|missing" packages/whisker/research/repos/marker-v1.10.2/marker --glob "*.py"
rg -i -n "prompt|system|instructions|compare|judge|verify|faithful|evaluate|quality|missing" packages/whisker/research/repos/MinerU/mineru --glob "*.py"
rg -i -n "prompt|system|instructions|compare|judge|verify|faithful|evaluate|quality|missing" packages/whisker/research/repos/olmocr/olmocr --glob "*.py"
rg -i -n "prompt|system|instructions|compare|judge|verify|faithful|evaluate|quality|missing" packages/whisker/research/repos/docling/docling --glob "*.py"
rg -i -l "openai|chat\.completions|generate_content|litellm" packages/whisker/research/repos/ --glob "*.py"
```

Files read in full (surrounding function or whole module where hit occurred):
- `marker/benchmarks/overall/scorers/llm.py`
- `marker/benchmarks/overall/elo.py`
- `marker/marker/processors/llm/llm_form.py`
- `marker/marker/processors/llm/llm_mathblock.py`
- `marker/marker/processors/llm/llm_table.py`
- `marker/marker/processors/llm/llm_page_correction.py`
- `marker/marker/processors/llm/llm_complex.py`
- `marker/marker/processors/llm/llm_handwriting.py`
- `marker/marker/processors/llm/llm_sectionheader.py`
- `olmocr/olmocr/bench/miners/check_headers_footers.py`
- `olmocr/olmocr/bench/miners/check_old_scans_math.py`
- `olmocr/olmocr/synth/mine_html_templates.py` (refinement step ~560-599)
- `MinerU/mineru/utils/llm_aided.py`
- `unstructured/unstructured/metrics/table/table_eval.py`
- `unstructured/unstructured/metrics/text_extraction.py` (line 200 context)
- `docling/tests/verify_utils.py` (sampled; no LLM calls)

## Inventory

| file:line | classification | one-line finding |
|---|---|---|
| `marker/benchmarks/overall/scorers/llm.py:15-52` | **eval-harness: true verification-of-existing-output** | `rating_prompt` asks Gemini to score already-produced markdown against a rendered PDF page image (`Compare the image to the markdown representation`; per-page via `doc[0]` in `__call__`). Offline benchmark only, not production convert path. |
| `marker/benchmarks/overall/scorers/llm.py:108-154` | eval-harness | `llm_rater` / `llm_response_wrapper` invoke `generate_content` with image + markdown prompt. |
| `marker/benchmarks/overall/elo.py:20-54` | **eval-harness: true verification-of-existing-output** | Pairwise markdown-vs-image judge for Elo benchmark (`evaluate the markdown based on the image`; `Decide which markdown representation is better`). Not production. |
| `marker/marker/processors/llm/llm_form.py:14-23` | **refinement (production)** | `--use_llm` block processor: passes existing block HTML + crop image; step 3 `Compare the html representation to the image`, then rewrite or `"No corrections needed"`. Inline pipeline fix, not post-hoc QA lane. |
| `marker/marker/processors/llm/llm_mathblock.py:34-44` | **refinement (production)** | Block-level: `Compare the extracted text to the corresponding text in the image` then emit corrected HTML or `"No corrections needed"`. |
| `marker/marker/processors/llm/llm_table.py:47-65` | **refinement (production)** | Table block: `faithful to the original table image`; writes comparison then corrected HTML or `"No corrections needed"` with self-score 1-5. |
| `marker/marker/processors/llm/llm_page_correction.py:37-65` | **refinement (production, per-page)** | Per-page JSON blocks + full page image; `Stay faithful to the original image` / analyze blocks vs image. Closest production per-page compare, but still conversion-time rewrite gate (`no_corrections` / reorder / rewrite), not tapetum-style judge-only verification. |
| `marker/marker/processors/llm/llm_page_correction.py:150-159` | refinement (production, per-page) | `process_rewriting` calls `llm_service(prompt, image, page1, PageSchema)` once per page when `--use_llm` enables this processor. |
| `marker/marker/processors/llm/llm_complex.py:14-33` | extraction/refinement (production) | Complex region: generate markdown from image + partial text; `faithful to the original image`. No compare-existing-output step; produces content. |
| `marker/marker/processors/llm/llm_handwriting.py:17-18` | extraction (production) | Handwriting OCR: generate markdown from image; `faithful to the original image`. No verification of prior output. |
| `marker/marker/processors/llm/llm_sectionheader.py:18-78` | refinement (production, document-level) | Fixes h1-h6 levels on header list; example text `missing the h1 tag` is few-shot only, not an LLM verification instruction. |
| `olmocr/olmocr/bench/miners/check_headers_footers.py:39-54` | **test-mining: true verification-of-existing-output (per-page)** | OpenAI vision: `Please verify if the headers or footers are exactly matches the below text` vs PDF page image. Bench test authoring tool, not olmocr convert pipeline. |
| `olmocr/olmocr/bench/miners/check_old_scans_math.py:40-57` | **test-mining: true verification-of-existing-output (per-page)** | `Please verify if the following LaTeX expression ... appears correctly in the document` vs page image. Bench miner only. |
| `olmocr/olmocr/synth/mine_html_templates.py:575-596` | test-mining / training synth | Claude compares original doc image vs rendered HTML image and revises HTML. Synthetic data pipeline, not production OCR verification. |
| `MinerU/mineru/utils/llm_aided.py:71-111` | refinement (production, optional) | Title-level assignment from title dict text; no comparison to source PDF/markdown output. Rejected as verification. |
| `MinerU/mineru/utils/llm_aided.py:178-180` | refinement (production) | `chat.completions.create` for title optimization prompt above. |
| `unstructured/unstructured/metrics/table/table_eval.py:1-16` | eval-harness (deterministic) | Docstring mentions `Verify table identification` and `Compare the token orders`; implementation uses difflib/alignment, **no LLM**. Rejected. |
| `unstructured/unstructured/metrics/text_extraction.py:200` | eval-harness (deterministic) | Comment `nothing missing because nothing in source document`; Levenshtein metrics, **no LLM**. Rejected. |
| `docling/tests/verify_utils.py:99-477` | test harness (deterministic) | `verify_text` / `verify_md` compare pred vs ground truth strings; **no LLM**. Rejected. |
| `olmocr/olmocr/bench/tests.py:131-518` | test harness (deterministic) | Page-scoped fuzzy fact-presence tests (`Test to verify the presence...`); **no LLM in eval loop**. Rejected (matches prior-art note in 00-baseline). |
| `markitdown/packages/markitdown-ocr/tests/test_pdf_converter.py:4` | test docstring | `compare the` in test module docstring; mock OCR, no verification LLM. Rejected. |
| `markitdown/packages/markitdown-ocr/tests/test_docx_converter.py:4` | test docstring | same | Rejected. |
| `markitdown/packages/markitdown-ocr/tests/test_pptx_converter.py:4` | test docstring | same | Rejected. |
| `markitdown/packages/markitdown-ocr/tests/test_xlsx_converter.py:4` | test docstring | same | Rejected. |
| `unstructured/unstructured/nlp/english-words.txt:127088` | dictionary | literal word `faithfully`. Rejected. |
| `marker/data/examples/markdown/thinkpython/thinkpython.md:4326` | example corpus content | converted book text mentioning "compare the speed". Rejected. |
| `marker/data/examples/markdown/switch_transformers/switch_trans.md:425` | example corpus content | paper text. Rejected. |

**Repos with zero verification-style prompt strings near any LLM call site (pattern floor applied, no qualifying hits):**
camelot, Dolphin, firecrawl, grobid, html-to-markdown-go, html-to-markdown-py, html2text, img2table, langextract, markdownify, mdream, node-html-markdown, nougat, opendataloader-bench-tmp, opendataloader-pdf, pandoc, PDF-Extract-Kit, pdf-to-markdown, pdfplumber, PyMuPDF, pymupdf4llm, surya, tabula-java, tabula-java-tmp, turndown.

(docling production `docling/` has VLM extraction prompts only; no compare-output-to-source verification strings found.)

## Verdict on the claim(s)
**C1 CONFIRMED.** No production code path in any of the 31 clones implements tapetum-style post-conversion LLM/VLM verification that judges already-produced conversion output against the source document per page/chunk/unit.

Closest counterexamples are **not production**:
- `marker/benchmarks/overall/scorers/llm.py:30` — true per-page markdown-vs-image verification, but eval harness only.
- `olmocr/olmocr/bench/miners/check_headers_footers.py:44` — true per-page verification prompt, but bench test-mining only.

Closest **production** near-misses are **refinement**, not verification lanes:
- `marker/marker/processors/llm/llm_page_correction.py:150-159` — per-page LLM compares pipeline blocks + page image and rewrites; gated by `--use_llm`, reject-and-keep semantics.
- `marker/marker/processors/llm/llm_form.py:21`, `llm_mathblock.py:42`, `llm_table.py:63` — block-level compare-then-rewrite inside conversion.

## Coverage gaps
None for the stated pattern floor across all 31 clone roots. Non-Python prompt carriers (`.jinja`, `.ts`, `.go`) were included in the broad first pass; no additional qualifying hits beyond those listed. Raw rg returned 135 Python line hits for the expanded pattern set; ~111 were test assertions (`Verify that...`), deterministic helpers, dependency messages, or document/example text and were triaged out in the inventory above.

## What could still hide a counterexample
- Prompt strings built by string concatenation without static keywords from the search floor.
- Verification logic in non-cloned dependencies or runtime-downloaded prompt templates not present at pinned SHAs.
- LLM calls in languages not searched (Rust/C++ native backends in grobid, tabula-java) — grep of those trees found no matching prompt literals.
