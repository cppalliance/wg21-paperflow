# 15b - Dolphin page/element coverage and failure semantics

**Claims tested:** C4 (foreign facts: Dolphin extraction coverage and silent-gap behavior)
**Exhaustive:** yes

## Method

Search commands run:

```
rg -n "try:|except|continue|raise |return \[\]|Error|Warning|distorted_page" packages/whisker/research/repos/Dolphin --glob "*.py"
rg -n "if not |if len|size\[0\]|assert |return |continue" packages/whisker/research/repos/Dolphin --glob "*.py" | rg -i "page|element|layout|bbox|crop|batch|pdf|image"
git -C packages/whisker/research/repos/Dolphin rev-parse HEAD
```

Files read in full (all Python in clone at SHA `befa5da`):

- `demo_page.py` (396 lines) — production document path: `process_document`, `process_single_image`, `process_elements`, `process_element_batch`
- `demo_layout.py` (275 lines) — layout-only page path
- `demo_element.py` (234 lines) — standalone single-element demo
- `utils/utils.py` (538 lines) — PDF conversion, output save, layout helpers
- `utils/markdown_utils.py` (359 lines) — JSON→markdown conversion

Note: there is no `demo_document.py`; the document orchestrator is `process_document` in `demo_page.py:127-168`.

## Output structure (baseline for detectability)

Multi-page PDF combined JSON (`utils/utils.py:110-118`):

```json
{"source_file": "...", "total_pages": N, "pages": [{"page_number": k, "elements": [...]}, ...]}
```

Per-element dict fields emitted by the page pipeline (`demo_page.py:233-240`, `demo_page.py:312-318`): `label`, `text`, `bbox`, `reading_order`, `tags`; figures also `figure_path`. No `status`, `error`, `failed`, or `partial` keys anywhere in the clone.

Single-image JSON (`utils/utils.py:238-240`): flat list of element dicts (same fields).

## Inventory

Every error-handling, fallback, or silent-loss path on the page/element pipeline. Columns: path id, location, trigger, stdout/stderr, what lands in structured output, caller-detectable from output alone?

| # | file:line | Trigger | Stdout/stderr | Structured output | Detectable? |
|---|-----------|---------|---------------|-------------------|-------------|
| 1 | `utils/utils.py:66-91` | PDF open/render throws | `Error converting PDF to images: …` | Returns `[]` | **No** (no file written yet) |
| 2 | `demo_page.py:134-135` | `convert_pdf_to_images` returned `[]` | Exception propagates (message only) | No output file; exception to caller | **Yes** (exception) |
| 3 | `demo_layout.py:141-142` | Same empty PDF conversion | Same | Same | **Yes** (exception) |
| 4 | `demo_page.py:140-157` | Per-page loop; no inner try/except | Page progress prints only | Each page always appended: `{page_number, elements}` even if `elements` empty/partial | **No** for partial/empty distinction |
| 5 | `demo_page.py:378-391` | Any exception in `process_document` for one input file | `Error processing {file_path}: …` | **No output** for that file; loop continues | **Yes** (missing output file) |
| 6 | `demo_layout.py:256-266` | Exception in `process_layout` for one file | `✗ Error processing {file_path}: …` | **No output** for that file | **Yes** (missing output) |
| 7 | `demo_element.py:215-229` | Exception in `process_element` for one image | `Error processing {image_path}: …` | **No output** for that image | **Yes** (missing output) |
| 8 | `demo_page.py:186` | Stage-1 layout VLM `model.chat` throws (OOM, CUDA, etc.) | Unhandled | Propagates → path #5; no partial PDF JSON | **Yes** (exception / no file) |
| 9 | `demo_page.py:204-205` | Layout string empty or missing `[`/`]` wrapper | None | Replaced with one synthetic `distorted_page` element covering full image; normal element dict | **No** (indistinguishable from intentional distorted_page) |
| 10 | `demo_page.py:207-209` | `check_bbox_overlap` returns True (`utils/utils.py:528-531`) | `Falling back to distorted_page mode…` / overlap ratio print | Same as #9: single `distorted_page` element | **No** |
| 11 | `demo_layout.py:177-178` | Layout parse fail (layout-only demo) | None | Single `distorted_page` bbox entry with `"text": ""` | **No** |
| 12 | `demo_page.py:220-264` | Exception during bbox crop/coordinate/figure prep for one layout element | `Error processing bbox with label {label}: …` | **Element omitted** from `recognition_results`; gap in `reading_order` sequence possible | **No** (no tombstone; missing element) |
| 13 | `demo_page.py:230-260` | Cropped region ≤3×3 px (`pil_crop.size[0] > 3 and … > 3` false) | None | Element **silently skipped**; `reading_order` still incremented (`demo_page.py:260`) | **No** |
| 14 | `utils/utils.py:34-52` | Figure PNG save throws | `Error saving figure: …` | Figure element still appended with `figure_path: figures/{name}_figure_{ord}_error.png` (`demo_page.py:233-237`); file may not exist | **No** (looks like normal figure ref) |
| 15 | `demo_page.py:268-282` / `289-320` | Stage-2 batch VLM `model.chat` throws | Unhandled | Propagates → #5 or #8; entire page/file aborts | **Yes** (exception) |
| 16 | `demo_page.py:307-318` | Batch VLM returns empty/garbage string | None | Element dict with `"text": ""` (after `.strip()`) | **No** (empty text indistinguishable from blank content) |
| 17 | `utils/utils.py:110-118` | Always (success path) | None | Combined JSON with `total_pages: len(all_page_results)`; no per-page status | **No** for page-level failure |
| 18 | `utils/utils.py:126-134` | Page has empty `elements` list | None | Page **omitted from combined markdown**; still present in JSON as `{page_number, elements: []}` | **Partially** (JSON shows empty array; markdown hides page) |
| 19 | `utils/utils.py:149-150` | `ImportError` during combined markdown | `MarkdownConverter not available…` | JSON saved; **no combined .md** | **Partially** (JSON exists, markdown absent) |
| 20 | `utils/utils.py:151-152` | Exception during combined markdown generation | `Error generating markdown: …` | JSON saved; markdown may be missing/partial | **Partially** |
| 21 | `utils/markdown_utils.py:324-325` | Element has empty `text` after strip | None | Element **skipped in markdown** only; still in JSON if present | **No** in markdown; **Yes** in JSON (empty/missing text field) |
| 22 | `utils/markdown_utils.py:347-350` | Exception converting one element to markdown | `Error processing item {n}: …` | Markdown gets `*[Error processing content]*`; **JSON unchanged** (no error field) | **No** in JSON; **Yes** in markdown placeholder |
| 23 | `utils/markdown_utils.py:18-20` | HTML table extract fails | `extract_table_from_html error: …` | Markdown embeds `<table>…Error extracting table…</table>` | **Yes** (error string in markdown) |
| 24 | `utils/markdown_utils.py:226-228` | Heading handler fails | `_handle_heading error: …` | Markdown `# Error processing heading: …` | **Yes** (markdown only) |
| 25 | `utils/markdown_utils.py:236-238` | List item handler fails | `_handle_list_item error: …` | Markdown `- Error processing list item: …` | **Yes** (markdown only) |
| 26 | `utils/markdown_utils.py:267-269` | Figure handler fails | `_handle_figure error: …` | Markdown `*[Error processing figure: …]*` | **Yes** (markdown only) |
| 27 | `utils/markdown_utils.py:282-284` | Table handler fails | `_handle_table error: …` | Markdown `*[Error processing table: …]*` | **Yes** (markdown only) |
| 28 | `utils/markdown_utils.py:304-306` | Formula handler fails | `_handle_formula error: …` | Markdown `*[Error processing formula: …]*` | **Yes** (markdown only) |
| 29 | `utils/markdown_utils.py:356-358` | Top-level `convert` fails | `convert error: …` | Returns string `Error generating markdown content: …` written to `.md` | **Yes** (markdown file content) |
| 30 | `utils/markdown_utils.py:158-160` | `try_remove_newline` fails | `try_remove_newline error: …` | Returns original text (degraded silently in JSON) | **No** |
| 31 | `utils/markdown_utils.py:176-178` | `_handle_text` fails | `_handle_text error: …` | Returns original text | **No** |
| 32 | `utils/markdown_utils.py:192-194` | `_process_formulas_in_text` fails | `_process_formulas_in_text error: …` | Returns original text | **No** |
| 33 | `utils/markdown_utils.py:211-213` | `_remove_newline_in_heading` fails | `_remove_newline_in_heading error: …` | Returns original text | **No** |
| 34 | `utils/utils.py:234-254` | `save_outputs` (single image): JSON write / markdown / `visualize_layout` | Unhandled exceptions propagate | No local catch | **Yes** (exception) |
| 35 | `utils/utils.py:309-310` | `visualize_layout` image load fails | Unhandled `ValueError` | Aborts `save_outputs` | **Yes** (exception) |
| 36 | `utils/utils.py:320-321` | Layout result dict missing `"bbox"` key | None (early `return`) | Visualization PNG incomplete; JSON/markdown already written | **No** |
| 37 | `demo_page.py:56` | Batch prompt/image count mismatch in `DOLPHIN.chat` | Unhandled `AssertionError` | Aborts current page/file | **Yes** (exception) |
| 38 | `demo_layout.py:183-192` | `process_coordinates` throws on bad bbox (layout demo) | Unhandled | Aborts file → #6 | **Yes** (exception) |
| 39 | `demo_page.py:355-363` | CLI: missing input / unsupported extension | `FileNotFoundError` / `ValueError` before processing | No output | **Yes** (exception) |

**Path count: 39**

### Swallowed-exception summary (`demo_page.py` / `process_document` equivalents)

| Location | Behavior | Output effect |
|----------|----------|---------------|
| `demo_page.py:262-264` | `except Exception: continue` in element loop | Failed layout element absent from `elements` array |
| `demo_page.py:389-391` | `except Exception: continue` in file loop | Entire document produces no saved results |
| `utils/utils.py:89-91` | PDF conversion swallowed → `[]` | Raised at `demo_page.py:135` before any page output |
| `utils/utils.py:49-52` | Figure save swallowed | Figure entry with `_error.png` path |
| `demo_element.py:227-229` | Per-image swallowed | That image skipped |

`process_element_batch` (`demo_page.py:289-320`) and Stage-1/2 `model.chat` (`demo_page.py:186`, `307`) have **zero** try/except: failures abort the page or whole file rather than recording per-element failure in output.

## Verdict on the claim(s)

**CONFIRMED (C4-adjacent):** Dolphin walks every PDF page sequentially (`demo_page.py:140-157`) with one layout VLM call plus batched element VLM calls per page (`demo_page.py:186-190`, `268-282`). This is extraction coverage, not verification.

**CONFIRMED:** Per-element failures inside a page are swallowed at `demo_page.py:262-264` (`continue` after print). Layout parse/overlap failures silently downgrade to `distorted_page` (`demo_page.py:204-209`). File-level failures skip the file (`demo_page.py:389-391`). Empty pages appear in JSON with `elements: []` but are dropped from combined markdown (`utils/utils.py:128-129`). **No output field allows a caller to reliably detect a failed element or partially failed page from JSON alone.**

## Coverage gaps

None. All five Python source files in the Dolphin clone were read in full. No other production modules exist in the clone.

## What could still hide a counterexample

- Custom wrappers or fork code outside this clone (not in corpus).
- Runtime failures inside `transformers` / `model.generate` that return degenerate text instead of throwing (would appear as normal empty/garbage `text`, path #16).
- Operator ignores JSON and reads only combined markdown (paths #18, #21 hide empty/failed pages/elements).
