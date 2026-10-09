# 52 - marker block-selectivity + reject-and-keep (C4c)
**Claims tested:** C4c
**Exhaustive:** yes (all 11 files under `marker/processors/llm/`, plus `marker/converters/pdf.py`, `marker/converters/__init__.py`, `marker/config/parser.py`, `marker/processors/line_merge.py`; SHA `ef16c2c` matches baseline)

## Method
Search commands run:
```text
rg -l "LLMSectionHeaderProcessor|LLMTableProcessor|use_llm" packages/whisker/research/repos/marker
rg -n "use_llm|block_correction_prompt|redo_inline_math|extract_images|block_types|structure_blocks" packages/whisker/research/repos/marker-v1.10.2/marker --glob "*.py"
Get-ChildItem -Recurse packages/whisker/research/repos/marker-v1.10.2/marker/processors -Filter "*.py"
git -C packages/whisker/research/repos/marker rev-parse HEAD
```

Files read in full:
- `marker/processors/llm/__init__.py`
- `marker/processors/llm/llm_meta.py`
- `marker/processors/llm/llm_complex.py`
- `marker/processors/llm/llm_equation.py`
- `marker/processors/llm/llm_form.py`
- `marker/processors/llm/llm_handwriting.py`
- `marker/processors/llm/llm_image_description.py`
- `marker/processors/llm/llm_mathblock.py`
- `marker/processors/llm/llm_page_correction.py`
- `marker/processors/llm/llm_sectionheader.py`
- `marker/processors/llm/llm_table.py`
- `marker/processors/llm/llm_table_merge.py`
- `marker/converters/pdf.py`
- `marker/converters/__init__.py`
- `marker/config/parser.py`
- `marker/processors/line_merge.py`
- `tests/processors/test_llm_processors.py` (image-description default gate test)

## Inventory

### Global `--use_llm` gate (all LLM processors)

| file:line | role |
|---|---|
| `pdf.py:70-73` | `PdfConverter.use_llm = False` default |
| `pdf.py:138-139` | LLM service instantiated only when `config.get("use_llm", False)` |
| `config/parser.py:117-120` | CLI path: `get_llm_service()` returns `None` unless `--use_llm` |
| `llm/__init__.py:50-53` | `BaseLLMProcessor.use_llm = False` |
| `llm/__init__.py:64-65` | `BaseLLMProcessor.__init__`: `if not self.use_llm: return` (no service) |
| `llm/__init__.py:137-139` | `BaseLLMComplexBlockProcessor.__call__`: `if not self.use_llm or self.llm_service is None: return` |
| `llm_meta.py:29-30` | `LLMSimpleBlockMetaProcessor.__call__`: same early return |
| `util.py:58-79` | `assign_config`: shared keys like `use_llm` propagate to every processor instance |

### (a) Block-type gating — every LLM processor

| Processor | block_types (or equivalent) | file:line | Additional skip gates |
|---|---|---|---|
| `LLMTableProcessor` | `(BlockTypes.Table, BlockTypes.TableOfContents)` | `llm_table.py:19-22` | no TableCell children `125-127`; `row_count > max_table_rows` (175) `134-135` |
| `LLMTableMergeProcessor` | `(BlockTypes.Table, BlockTypes.TableOfContents)` | `llm_table_merge.py:18-21` | `no_merge_tables_across_pages` `158-160`; heuristic pair detection `176-207`; `len(blocks) < 2` `245-247` |
| `LLMFormProcessor` | `(BlockTypes.Form,)` | `llm_form.py:13` | requires TableCell children `70-72` |
| `LLMComplexRegionProcessor` | `(BlockTypes.ComplexRegion,)` | `llm_complex.py:13` | none beyond block type |
| `LLMImageDescriptionProcessor` | `(BlockTypes.Picture, BlockTypes.Figure,)` | `llm_image_description.py:12-15` | `extract_images=True` (default) → `inference_blocks` returns `[]` `44-45` |
| `LLMEquationProcessor` | `(BlockTypes.Equation,)` | `llm_equation.py:11` | height `< min_equation_height` unless `redo_inline_math=True` `79-83` |
| `LLMHandwritingProcessor` | `(BlockTypes.Handwriting, BlockTypes.Text,)` | `llm_handwriting.py:12` | Text blocks with lines or non-empty raw_text skipped `44-47` |
| `LLMMathBlockProcessor` | `(BlockTypes.TextInlineMath,)` primary; secondary `(Text, Caption, SectionHeader, Footnote)` when density threshold met | `llm_mathblock.py:26-32`, `94-99` | `redo_inline_math=False` (default) → immediate return `77-78`; page math-density `< inlinemath_min_ratio` (0.4) skips expansion `127-131` |
| `LLMSectionHeaderProcessor` | **no `block_types` attr**; equivalent filter `block.block_type == BlockTypes.SectionHeader` over `page.structure_blocks(document)` | `llm_sectionheader.py:147-151` | `len(section_headers) == 0` → return `153-154`; **document-level single call** (not per-page) `156-162` |
| `LLMPageCorrectionProcessor` | **no `block_types` attr**; equivalent: one pass per `document.pages` entry when prompt set | `llm_page_correction.py:286-288`, `143` | `block_correction_prompt is None` (default) → return `269-270` |
| `LLMSimpleBlockMetaProcessor` | wrapper only; delegates to simple processors' `block_types` via `inference_blocks` | `llm_meta.py:32-41`, `converters/__init__.py:48-62` | created at init; batches `LLMFormProcessor`, `LLMComplexRegionProcessor`, `LLMImageDescriptionProcessor`, `LLMEquationProcessor`, `LLMHandwritingProcessor` |
| `BaseLLMProcessor` | `block_types = None` (base default, not in pipeline directly) | `llm/__init__.py:58` | — |

`PdfConverter.default_processors` registers the 10 concrete LLM classes at `pdf.py:89-99`.

### (b) Concrete negative: page with only Text / SectionHeader blocks

**Scenario:** one page whose structure blocks are only `BlockTypes.Text` and/or `BlockTypes.SectionHeader` (no Table, Form, Equation, Picture, Figure, ComplexRegion, Handwriting). `--use_llm` enabled with default flags (`block_correction_prompt=None`, `redo_inline_math=False`, `extract_images=True`).

| Processor | Could fire on this page under defaults? | Evidence |
|---|---|---|
| `LLMTableProcessor` | No | `block_types` Table/TOC only `llm_table.py:19-22` |
| `LLMTableMergeProcessor` | No | same `llm_table_merge.py:18-21` |
| `LLMFormProcessor` | No | Form only `llm_form.py:13` |
| `LLMComplexRegionProcessor` | No | ComplexRegion only `llm_complex.py:13` |
| `LLMImageDescriptionProcessor` | No | Picture/Figure only; default `extract_images=True` disables all prompts `llm_image_description.py:44-45` (test: `test_llm_caption_processor_disabled`) |
| `LLMEquationProcessor` | No | Equation only `llm_equation.py:11` |
| `LLMHandwritingProcessor` | No for normal Text (lines/raw_text present); Yes only for **empty** Text (no Line children, empty raw_text) | `llm_handwriting.py:44-47` |
| `LLMMathBlockProcessor` | No | `redo_inline_math=False` → `return` `llm_mathblock.py:77-78` |
| `LLMSectionHeaderProcessor` | **Yes if any SectionHeader exists anywhere in the document** (one doc-level LLM call, not isolated to this page) | `llm_sectionheader.py:147-154`, `125-127` |
| `LLMPageCorrectionProcessor` | No under defaults | `block_correction_prompt=None` → `return` `llm_page_correction.py:269-270` |
| `LineMergeProcessor` | Runs deterministic merge only when `use_llm=True`; **no LLM API call** | `line_merge.py:36-39`, `118-119` |

**Non-default flags that would add LLM calls on Text/SectionHeader pages:**

| Flag | Processor affected | file:line |
|---|---|---|
| `block_correction_prompt="<text>"` | `LLMPageCorrectionProcessor` → **one LLM call per page** (including plain-text pages) | `llm_page_correction.py:269-270`, `286-288` |
| `redo_inline_math=True` | `LLMMathBlockProcessor`, `LLMEquationProcessor` → Text/Caption/SectionHeader/Footnote blocks on math-dense pages | `llm_mathblock.py:77-78`, `127-131`; `llm_equation.py:79-83` |
| `extract_images=False` | `LLMImageDescriptionProcessor` → would run on Picture/Figure (still none on Text-only page) | `llm_image_description.py:44-45` |
| (empty Text blocks) | `LLMHandwritingProcessor` | `llm_handwriting.py:44-47` |

**LLMSectionHeaderProcessor own gating flags:** inherits only `use_llm` from `BaseLLMProcessor` (`llm/__init__.py:50-53`, `64-65`, `137-139`). No per-block "llm flag" field exists on SectionHeader blocks in `marker/schema/blocks/` (metadata tracks `llm_request_count` etc. post-call, not pre-gating). When SectionHeaders exist, processor always submits one prompt for the full header list.

### (c) Reject-and-keep gates (verbatim condition + keep-original branch)

**Gate 1 — table rewrite (`llm_table.py:207-209`):**
```python
        # The original table is okay
        if "no corrections needed" in corrected_html.lower():
            return
```
Keep-original: `return` without assigning `block.structure` / cells (prior HTML/cells unchanged).

**Gate 2 — equation rewrite (`llm_equation.py:116-117`):**
```python
        if "no corrections needed" in html_equation.lower():
            return
```
Keep-original: `return` without `block.html = html_equation` (line 128 never reached).

**Gate 3 — form rewrite (`llm_form.py:105-106`):**
```python
        if "no corrections needed" in corrected_html.lower():
            return
```

**Gate 4 — complex region (`llm_complex.py:80-81`):**
```python
        if "no corrections" in corrected_markdown.lower():
            return
```

**Gate 5 — inline math block (`llm_mathblock.py:188-189`):**
```python
        if "no corrections needed" in corrected_html.lower():
            return
```

**Gate 6 — section header batch (`llm_sectionheader.py:135-136`):**
```python
        if correction_type == "no_corrections":
            return
```

**Gate 7 — page correction (`llm_page_correction.py:167-168`):**
```python
        if correction_type == "no_corrections":
            return
```

**Gate 8 — table merge reject (`llm_table_merge.py:279-281`):**
```python
            if "true" not in merge:
                start_block = curr_block
                continue
```
Keep-original: does not merge cells/images; advances to next table candidate.

**Gate 9 — length-ratio reject, form (`llm_form.py:109-111`):**
```python
        if len(corrected_html) < len(block_html) * .33:
            block.update_metadata(llm_error_count=1)
            return
```
Keep-original: no `block.html = corrected_html` (assignment at 114 skipped).

**Gate 10 — length-ratio reject, complex region (`llm_complex.py:84-86`):**
```python
        if len(corrected_markdown) < len(text) * .5:
            block.update_metadata(llm_error_count=1)
            return
```

## Verdict on the claim(s)

**CONFIRMED with nuance**

- **CONFIRMED:** Under `--use_llm` with default flags, a page containing **only `BlockTypes.Text` blocks** (no SectionHeader, Table, Form, Equation, Picture, Figure, ComplexRegion, Handwriting) incurs **zero LLM API calls**. Every default LLM processor either lacks matching blocks or is disabled by default secondary gates (`redo_inline_math=False`, `block_correction_prompt=None`, `extract_images=True`).
- **NUANCE:** A page with **SectionHeader** blocks is **not** LLM-free under defaults: `LLMSectionHeaderProcessor` submits **one document-level** call when any SectionHeader exists (`llm_sectionheader.py:147-162`), even if this particular page is otherwise plain text.
- **NUANCE:** `LLMPageCorrectionProcessor` is the processor that **would touch every page** (one call per page), but only when `block_correction_prompt` is set; default is `None` and `rewrite_blocks` returns immediately (`llm_page_correction.py:33-35`, `269-270`). No default processor unconditionally iterates all pages for LLM.
- **CONFIRMED:** Reject-and-keep gates preserve deterministic block HTML on LLM "no corrections" responses and on failed validation (length ratio, merge=false, etc.).

## Coverage gaps

None for C4c scope. Benchmark lane (`benchmarks/overall/scorers/llm.py`) and extraction converter (`converters/extraction.py`) not read; out of scope for `--use_llm` PDF pipeline block-selectivity claim.

## What could still hide a counterexample

- Custom `--processors` list omitting or adding LLM processors (`config/parser.py:141-152`).
- Non-default class-prefixed config keys (e.g. `LLMPageCorrectionProcessor_block_correction_prompt`) via `util.py:72-79`.
- LLM calls inside builders/OCR (`builders/ocr.py` references `structure_blocks`) not classified as `--use_llm` processors.
- `TableConverter` subset (`converters/table.py:18-24`) still block-type gated to Table/Form/TOC only.
