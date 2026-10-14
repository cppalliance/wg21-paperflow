# 13b - marker LLM-processor gating and reject-and-keep semantics

**Claims tested:** C4(a) block-selective `--use_llm`; C4 reject-and-keep gates  
**Exhaustive:** yes  
**Corpus SHA:** marker `ef16c2c` (matches `00-baseline.md`)

## Method

Search commands run:

```
rg -i "llm|use_llm" packages/whisker/research/repos/marker --glob "*.py" -l
rg -n "length|ratio|balanced|llm_error|reject|retry|score|schema|skip|use_llm|extract_images|row_count|block_size|floor|cap" packages/whisker/research/repos/marker-v1.10.2/marker/processors/llm -i
rg -n "llm_error_count|no corrections|balanced|score <|min_equation|max_table|inference_blocks|rewrite_blocks|use_llm" packages/whisker/research/repos/marker-v1.10.2/marker/processors/llm
rg -n "use_llm|LLMSimpleBlockMetaProcessor|initialize_processors" packages/whisker/research/repos/marker-v1.10.2/marker/converters
git -C packages/whisker/research/repos/marker rev-parse HEAD
```

Files read in full (production LLM processor scope):

- `marker/processors/llm/__init__.py`
- `marker/processors/llm/llm_meta.py`
- `marker/processors/llm/llm_table.py`
- `marker/processors/llm/llm_table_merge.py`
- `marker/processors/llm/llm_form.py`
- `marker/processors/llm/llm_complex.py`
- `marker/processors/llm/llm_equation.py`
- `marker/processors/llm/llm_image_description.py`
- `marker/processors/llm/llm_handwriting.py`
- `marker/processors/llm/llm_mathblock.py`
- `marker/processors/llm/llm_sectionheader.py`
- `marker/processors/llm/llm_page_correction.py`
- `marker/converters/__init__.py` (`initialize_processors`, meta-processor bundling)
- `marker/converters/pdf.py` (default processor list, `use_llm` wiring)
- `marker/services/gemini.py` (schema/JSON failure path returning `{}`)
- `marker/config/parser.py` (`--use_llm`, `--disable_image_extraction` → `extract_images`)

## Inventory

### A. Pipeline wiring (when `--use_llm` is set)

| file:line | role |
|---|---|
| `pdf.py:74-103` | Default processor list includes all 10 LLM processor classes plus non-LLM processors. |
| `pdf.py:138-139` | Instantiates `default_llm_service` only when `config.get("use_llm", False)`. |
| `converters/__init__.py:43-63` | Bundles all `BaseLLMSimpleBlockProcessor` instances into one `LLMSimpleBlockMetaProcessor`; complex processors stay standalone. |
| `__init__.py:64-67` | `BaseLLMProcessor.__init__`: if `not self.use_llm`, `llm_service = None` (no calls). |
| `llm_meta.py:29-30` | Meta wrapper: if `not self.use_llm or self.llm_service is None`, return (zero prompts). |
| `__init__.py:138-139` | Complex wrapper: same global guard before `rewrite_blocks`. |

Simple-block processors bundled by meta (in pdf default order): `LLMFormProcessor`, `LLMComplexRegionProcessor`, `LLMImageDescriptionProcessor`, `LLMEquationProcessor`, `LLMHandwritingProcessor` (`pdf.py:91-96`).

### B. Global skip gates (no LLM call)

| file:line | processor | condition | on skip |
|---|---|---|---|
| `__init__.py:64-67` | all `BaseLLMProcessor` | `use_llm == False` | service never injected |
| `__init__.py:138-139` | all complex | `use_llm == False` or `llm_service is None` | return immediately |
| `llm_meta.py:29-30` | meta simple bundle | same | return, zero futures submitted |
| `__init__.py:155-156` | complex (default `rewrite_blocks`) | `total_blocks == 0` for `block_types` | return |
| `llm_mathblock.py:77-78` | `LLMMathBlockProcessor` | `redo_inline_math == False` (default) | return, no LLM |
| `llm_mathblock.py:141-142` | `LLMMathBlockProcessor` | `len(inference_blocks) == 0` | return |
| `llm_page_correction.py:269-270` | `LLMPageCorrectionProcessor` | `block_correction_prompt is None` (default) | return, no per-page LLM |
| `llm_page_correction.py:274-275` | `LLMPageCorrectionProcessor` | `len(document.pages) == 0` | return |
| `llm_sectionheader.py:153-154` | `LLMSectionHeaderProcessor` | `len(section_headers) == 0` | return |
| `llm_table_merge.py:158-160` | `LLMTableMergeProcessor` | `no_merge_tables_across_pages == True` | log info, return |
| `llm_table_merge.py:225-226` | `LLMTableMergeProcessor` | `len(table_runs) == 0` | return |

### C. Per-processor skip gates (block never sent to LLM)

| file:line | processor | condition | on skip |
|---|---|---|---|
| `llm_table.py:125-127` | `LLMTableProcessor` | table has zero `TableCell` children | return (keep deterministic table) |
| `llm_table.py:134-135` | `LLMTableProcessor` | `row_count > max_table_rows` (default 175) | return (keep original) |
| `llm_equation.py:79-83` | `LLMEquationProcessor` | `block.height/page.height < min_equation_height` (0.06) and `redo_inline_math == False` | block omitted from prompts |
| `llm_form.py:71-72` | `LLMFormProcessor` | form has no `TableCell` children | block omitted |
| `llm_handwriting.py:44-47` | `LLMHandwritingProcessor` | `BlockTypes.Text` with `len(lines) > 0` OR `len(raw_text.strip()) > 0` | block omitted |
| `llm_image_description.py:44-45` | `LLMImageDescriptionProcessor` | `extract_images == True` (default) | returns `[]` for all Picture/Figure blocks |
| `llm_table_merge.py:245-247` | `LLMTableMergeProcessor` | `len(blocks) < 2` in run | return |
| `llm_table_merge.py:254-256` | `LLMTableMergeProcessor` | either table lacks cells | `break` merge loop |
| `llm_table_merge.py:169-207` | `LLMTableMergeProcessor` | geometric/heuristic merge prefilter fails | pair not added to `table_runs` (no LLM for that pair) |
| `llm_mathblock.py:127-131` | `LLMMathBlockProcessor` | page math-block ratio `< inlinemath_min_ratio` (0.4) | page's extra text blocks omitted |
| `llm_meta.py:32-34` | meta | sum of `inference_blocks` across simple processors is 0 | tqdm total 0, no `llm_service` calls |

`extract_images` interplay:

- Default `True` on `LLMImageDescriptionProcessor` (`llm_image_description.py:16`) skips all image-description LLM work (`llm_image_description.py:44-45`).
- CLI `--disable_image_extraction` sets `extract_images=False` (`config/parser.py:106-107`), which enables Picture/Figure LLM description prompts.
- Tests confirm: with `extract_images=False`, descriptions run (`tests/processors/test_llm_processors.py:124-130`); with default, descriptions stay `None` (`tests/processors/test_llm_processors.py:107-115`).

### D. Validation / rejection gates (post-LLM or post-service)

Reject-and-keep pattern: on rejection, processors either `return` without mutating `block.html` / `block.description` / table structure, or increment `llm_error_count` metadata and return. Original deterministic output is preserved.

#### D1. Service-layer schema / JSON failures (feeds all processors)

| file:line | condition | on failure |
|---|---|---|
| `services/gemini.py:94-111` | `APIError` (non-retryable or max retries) | log error, fall through |
| `services/gemini.py:112-125` | `JSONDecodeError` (max retries) | log error, fall through |
| `services/gemini.py:126-129` | other `Exception` | log error, break |
| `services/gemini.py:131` | all failure paths | **`return {}`** |

Empty `{}` is caught downstream as falsy `response`, triggering processor gates below. No `llm_error_count` at service layer; processors own that.

#### D2. Meta-processor finalize gate

| file:line | condition | on reject |
|---|---|---|
| `llm_meta.py:60-61` | any exception in `processor(result, prompt_data, document)` | `logger.warning(...)` only; original block unchanged |

#### D3. `LLMTableProcessor` gates

| file:line | gate type | condition | on reject |
|---|---|---|---|
| `llm_table.py:201-203` | schema field / empty service response | `not response or "corrected_html" not in response` | `llm_error_count=1`, return; **original kept** |
| `llm_table.py:208-209` | accept-without-change | `"no corrections needed" in corrected_html.lower()` | return; **original kept** |
| `llm_table.py:218-225` | **self-score retry** | `score = response.get("score", 5)`; if `total_iterations < max_table_iterations (2)` and `score < 4` | log info, recurse with corrected html as new input (not reject) |
| `llm_table.py:228-231` | parse sanity | `len(parsed_cells) <= 1` | `llm_error_count=1`, `logger.debug`; **original kept** |
| `llm_table.py:233-238` | structural tag check | `not corrected_html.endswith("</table>")` | `llm_error_count=1`, `logger.debug`; **original kept** |
| `llm_table.py:175-176` | batch abort | `batch_parsed_cells is None` from chunk | return from `process_rewriting`; **prior chunks may have applied; failed chunk keeps original structure** |

Row-count cap skip (not post-LLM): `llm_table.py:134-135` (`max_table_rows=175`). Batch size: `max_rows_per_batch=60` (`llm_table.py:144`).

#### D4. `LLMEquationProcessor` gates

| file:line | gate type | condition | on reject |
|---|---|---|---|
| `llm_equation.py:110-112` | schema field / empty response | `not response or "corrected_equation" not in response` | `llm_error_count=1`; **original kept** |
| `llm_equation.py:116-117` | accept-without-change | `"no corrections needed" in html_equation.lower()` | return; **original kept** |
| `llm_equation.py:119-126` | **balanced-tag + length-ratio** | reject unless ALL: non-empty html, `count("<math") == count("</math>")`, `len(html_equation) > len(text) * 0.3` | `llm_error_count=1`; **original kept** |

Block-size floor skip (pre-LLM): `llm_equation.py:79-83` (`min_equation_height=0.06`).

#### D5. `LLMComplexRegionProcessor` gates

| file:line | gate type | condition | on reject |
|---|---|---|---|
| `llm_complex.py:73-75` | schema field / empty response | `not response or "corrected_markdown" not in response` | `llm_error_count=1`; **original kept** |
| `llm_complex.py:80-81` | accept-without-change | `"no corrections" in corrected_markdown.lower()` | return; **original kept** |
| `llm_complex.py:84-86` | **length-ratio** | `len(corrected_markdown) < len(text) * 0.5` | `llm_error_count=1`; **original kept** |

#### D6. `LLMFormProcessor` gates

| file:line | gate type | condition | on reject |
|---|---|---|---|
| `llm_form.py:98-100` | schema field / empty response | `not response or "corrected_html" not in response` | `llm_error_count=1`; **original kept** |
| `llm_form.py:105-106` | accept-without-change | `"no corrections needed" in corrected_html.lower()` | return; **original kept** |
| `llm_form.py:109-111` | **length-ratio** | `len(corrected_html) < len(block_html) * 0.33` | `llm_error_count=1`; **original kept** |

#### D7. `LLMHandwritingProcessor` gates

| file:line | gate type | condition | on reject |
|---|---|---|---|
| `llm_handwriting.py:72-74` | schema field / empty response | `not response or "markdown" not in response` | `llm_error_count=1`; **original kept** |
| `llm_handwriting.py:77-79` | **length-ratio** | `len(markdown) < len(raw_text) * 0.5` | `llm_error_count=1`; **original kept** |

#### D8. `LLMImageDescriptionProcessor` gates

| file:line | gate type | condition | on reject |
|---|---|---|---|
| `llm_image_description.py:74-76` | schema field / empty response | `not response or "image_description" not in response` | `llm_error_count=1`; **original kept** (description stays None) |
| `llm_image_description.py:79-81` | absolute length floor | `len(image_description) < 10` | `llm_error_count=1`; **original kept** |

#### D9. `LLMMathBlockProcessor` gates

| file:line | gate type | condition | on reject |
|---|---|---|---|
| `llm_mathblock.py:178-180` | schema field / empty response | `not response or "corrected_html" not in response` | `llm_error_count=1`; **original kept** |
| `llm_mathblock.py:183-185` | empty string | `not corrected_html` | `llm_error_count=1`; **original kept** |
| `llm_mathblock.py:188-189` | accept-without-change | `"no corrections needed" in corrected_html.lower()` | return; **original kept** |
| `llm_mathblock.py:191-193` | **length-ratio** | `len(corrected_html) < len(block_text) * 0.6` | `llm_error_count=1`; **original kept** |

#### D10. `LLMTableMergeProcessor` gates

| file:line | gate type | condition | on reject |
|---|---|---|---|
| `llm_table_merge.py:272-274` | schema field / empty response | `not response or ("direction" not in response or "merge" not in response)` | `curr_block.update_metadata(llm_error_count=1)`, `break`; **tables stay separate** |
| `llm_table_merge.py:279-281` | merge decision | `"true" not in merge` | `start_block = curr_block; continue`; **no merge, originals kept** |
| `llm_table_merge.py:285-287` | post-LLM structural validate | `not validate_merge(...)` (row/col count tolerance) | `continue`; **no merge, originals kept** |
| `llm_table_merge.py:295-305` | `validate_merge` | bottom: `abs(row_counts) < 5`; right: `abs(col_counts) < 2` | returns False → reject merge |

Row-count prefilter (pre-LLM): `llm_table_merge.py:173`, `298-300` (`< 5` rows).

#### D11. `LLMSectionHeaderProcessor` gates

| file:line | gate type | condition | on reject |
|---|---|---|---|
| `llm_sectionheader.py:130-132` | schema field / empty response | `not response or "correction_type" not in response` | `logger.warning("LLM did not return a valid response")`; **all headers kept** |
| `llm_sectionheader.py:135-136` | accept-without-change | `correction_type == "no_corrections"` | return; **original kept** |
| `__init__.py:121-123` | rewrite apply | block id not found in document | `logger.debug`, `continue`; **that header kept** |
| `__init__.py:127-129` | rewrite apply | parse exception on block id | `logger.debug`, `continue`; **kept** |

No `llm_error_count` in section-header processor.

#### D12. `LLMPageCorrectionProcessor` gates

| file:line | gate type | condition | on reject |
|---|---|---|---|
| `llm_page_correction.py:162-164` | schema field / empty response | `not response or "correction_type" not in response` | `logger.warning(...)`; **page blocks kept** |
| `llm_page_correction.py:167-168` | accept-without-change | `correction_type == "no_corrections"` | return; **original kept** |
| `llm_page_correction.py:180-181` | unknown enum | correction type not in known set | `logger.warning(...)`; **original kept** |
| `llm_page_correction.py:200-204` | reorder validation | response page IDs ≠ document page IDs | `logger.debug`, return; **order kept** |
| `llm_page_correction.py:222-231` | reorder validation | response block ids ⊄ page structure | `logger.debug`, `continue`; **order kept** |
| `llm_page_correction.py:233-242` | reorder validation | page structure block ids ⊄ response | `logger.debug`, `continue`; **order kept** |
| `llm_page_correction.py:258-260` | rewrite apply | block not found | `logger.debug`, `continue`; **kept** |
| `llm_page_correction.py:264-266` | rewrite apply | parse exception | `logger.debug`, `continue`; **kept** |

No `llm_error_count` in page-correction processor.

### E. `llm_error_count` increment sites (complete list, n=17)

| file:line | processor |
|---|---|
| `llm_table.py:202` | table missing response field |
| `llm_table.py:229` | table parse ≤1 cell |
| `llm_table.py:237` | table missing `</table>` |
| `llm_equation.py:111` | equation missing response field |
| `llm_equation.py:125` | equation balanced-tag / length-ratio fail |
| `llm_complex.py:74` | complex missing response field |
| `llm_complex.py:85` | complex length-ratio fail |
| `llm_form.py:99` | form missing response field |
| `llm_form.py:110` | form length-ratio fail |
| `llm_handwriting.py:73` | handwriting missing response field |
| `llm_handwriting.py:78` | handwriting length-ratio fail |
| `llm_image_description.py:75` | image missing response field |
| `llm_image_description.py:80` | image description too short |
| `llm_mathblock.py:179` | mathblock missing response field |
| `llm_mathblock.py:184` | mathblock empty corrected_html |
| `llm_mathblock.py:192` | mathblock length-ratio fail |
| `llm_table_merge.py:273` | merge missing response fields |

Logged at `logger.debug` unless noted: table parse gates (`llm_table.py:230,234-235`), section-header / page-correction use `logger.warning` for invalid top-level response.

### F. Gate-type summary counts

| gate category | count (distinct file:line gates in `marker/processors/llm` + service feed) |
|---|---|
| Pre-LLM skip gates (Section B+C) | 21 |
| Post-LLM reject/accept gates (Section D2-D12) | 38 |
| **`llm_error_count` increments** | **17** |
| **Self-score retry loops** | **1** (`llm_table.py:218-225`, score `< 4`, max 2 iterations) |
| **Balanced-tag checks** | **1** (`llm_equation.py:119-122`, `<math>`/`</math>` parity) |
| **Length-ratio rejection checks** | **6** (equation 0.3, complex 0.5, form 0.33, handwriting 0.5, mathblock 0.6, image abs floor `<10` at `llm_image_description.py:79`) |
| Service schema/JSON failure → `{}` | 1 path (`services/gemini.py:131`; other service classes follow same pattern, not fully enumerated here) |

**Total enumerated post-service validation/rejection gate sites in processors/llm: 38.**  
**Total enumerated skip + validation gates (B+C+D): 59.**

## Verdict on the claim(s)

### C4(a): `--use_llm` is block-selective; plain page can get zero LLM calls

**PARTIALLY CONFIRMED / PARTIALLY REFUTED.**

- **CONFIRMED (narrow case):** A page containing only `Text` blocks that already have `Line` children, with no `SectionHeader`, `Table`, `Form`, `Equation`, `ComplexRegion`, or `Handwriting`, and with default `redo_inline_math=False` (`llm_mathblock.py:77-78`) and default `block_correction_prompt=None` (`llm_page_correction.py:269-270`), produces **zero** `llm_service(...)` calls. Evidence: each processor's skip gates above; meta-processor submits no futures when all `inference_blocks` lists are empty (`llm_meta.py:32-48`); complex processors exit on zero matching blocks or disabled flags.
- **REFUTED (typical text page):** Any document with **one or more `SectionHeader` blocks** triggers exactly **one** document-wide LLM call in `LLMSectionHeaderProcessor.process_rewriting` (`llm_sectionheader.py:145-162`, `125-127`), even when that page has no tables/forms/equations/complex regions. Section headers are not excluded by the claim's list but are normal on text-heavy PDF pages.
- **Additional refutations if config differs:** `--disable_image_extraction` (`extract_images=False`) enables Picture/Figure LLM calls (`llm_image_description.py:44-45`). Setting `redo_inline_math=True` (benchmark harness sets this when `use_llm` — `benchmarks/overall/methods/marker.py:19-20`) enables math-block LLM. Setting `block_correction_prompt` enables per-page LLM (`llm_page_correction.py:269-288`).

### C4 reject-and-keep gates

**CONFIRMED.** Every rejection path listed in Section D preserves the pre-LLM deterministic block/table output unless a gate explicitly applies a rewrite after passing validation. Failures increment `llm_error_count` on the block (17 sites) or log and return without mutation (section header, page correction, table merge decline).

## Coverage gaps

- Alternate LLM service implementations (`openai.py`, `claude.py`, `azure_openai.py`, `ollama.py`, `vertex.py`) not read line-by-line; schema-failure behavior assumed parallel to `gemini.py` returning `{}` after retries.
- `marker/extractors/*` and `benchmarks/*` LLM paths out of scope (not `marker/processors/llm`).
- `LineMergeProcessor` (`line_merge.py:118-119`) gates on `use_llm` but performs **no** `llm_service` calls (deterministic line merge only).

## What could still hide a counterexample

- A layout pass could label plain prose as `SectionHeader`, `Handwriting`, or `ComplexRegion`, creating LLM eligibility despite visual "text-only" appearance.
- Non-default config JSON (`config_json`) can set `block_correction_prompt`, `redo_inline_math`, or `extract_images=False` without CLI flags.
- Custom `--processors` list could insert additional LLM processors not in the default pdf list.
- Service implementations other than Gemini might surface pydantic validation errors differently before returning `{}`.
