# 12b - langextract chunk coverage and failure semantics
**Claims tested:** C4(b)
**Exhaustive:** yes (annotation.py, chunking.py, resolver.py, extraction.py read in full line-by-line; AnnotatedDocument fields verified in core/data.py:206-215 for result-model question only)

## Method
Files read in full (no rg truncation):
- `packages/whisker/research/repos/langextract/langextract/annotation.py` (626 lines)
- `packages/whisker/research/repos/langextract/langextract/chunking.py` (507 lines)
- `packages/whisker/research/repos/langextract/langextract/resolver.py` (1405 lines)
- `packages/whisker/research/repos/langextract/langextract/extraction.py` (428 lines)

Supplementary (result model fields only): `langextract/core/data.py:206-215` (`AnnotatedDocument`).

No experiments run.

## Inventory

### Public entry points: `suppress_parse_errors` default

| Entry point | Signature line | Default | Citation |
|---|---|---|---|
| `extract()` | `extraction.py:45` | **True** (via `alignment_kwargs.setdefault("suppress_parse_errors", True)` at `extraction.py:365`; docstring `extraction.py:136-138`) | `extraction.py:45,136-138,365` |
| `lx.extract` wrapper | `__init__.py:53` | **True** (delegates to `extract_func`) | `__init__.py:53-55` → `extraction.py:365` |
| `Annotator.annotate_documents()` | `annotation.py:209` | **False** (no param; `**kwargs` → `_annotate_documents_single_pass(..., suppress_parse_errors: bool = False, ...)` at `annotation.py:295`) | `annotation.py:209-220,295` |
| `Annotator.annotate_text()` | `annotation.py:532` | **False** (same `**kwargs` chain through `annotate_documents`) | `annotation.py:532-544,586-597` |
| `Annotator._annotate_documents_single_pass()` | `annotation.py:285` | **False** (`suppress_parse_errors: bool = False` at `annotation.py:295`) | `annotation.py:295` |
| `Resolver.resolve()` | `resolver.py:276` | **False** (`suppress_parse_errors: bool = False` at `resolver.py:279`) | `resolver.py:279` |

Routing: `extract()` passes `suppress_parse_errors` in `**alignment_kwargs` to `annotate_text` / `annotate_documents` (`extraction.py:401,425`), which forwards `**kwargs` to `_annotate_documents_single_pass` (`annotation.py:269,282,491`), which passes it only to `resolver.resolve(..., suppress_parse_errors=suppress_parse_errors, ...)` (`annotation.py:407`). It is **not** consumed by `resolver.align` (listed in `ALIGNMENT_PARAM_KEYS` at `resolver.py:84` but unused in `align` body).

### Retry logic (scoped files only)

| Location | Finding |
|---|---|
| `extraction.py:147-148` | Docstring only: `language_model_params` may carry Gemini `max_retries`, `retry_delay`, `max_retry_delay`. No retry loop in scoped files. |
| `annotation.py:392` | Single `language_model.infer(...)` call per batch; no retry wrapper in this file. |
| `resolver.py:304-306` | Delegates parse to `format_handler.parse_output(...)`; any parse retry lives in `format_handler` (out of scope). No retry loop in `resolver.py`. |
| `chunking.py` | No retry logic. |

### Multi-pass merge rules (`extraction_passes > 1`)

| Rule | Citation |
|---|---|
| `annotate_documents` routes to `_annotate_documents_sequential_passes` when `extraction_passes != 1` | `annotation.py:259-283` |
| Documents materialized with `list(documents)` | `annotation.py:468` |
| Each pass calls `_annotate_documents_single_pass` with same `**kwargs` (including `suppress_parse_errors`) | `annotation.py:482-491` |
| Per-pass extractions stored as `list[list[Extraction]]` keyed by `document_id` | `annotation.py:470-501` |
| Merge via `_merge_non_overlapping_extractions`: **first pass wins** on overlapping `char_interval`; later-pass extraction dropped if overlap detected | `annotation.py:46-84,507-508` |
| Overlap check skipped when either extraction lacks `char_interval` (`return False` at `_extractions_overlap`) → later-pass extraction **always appended** if either side has `char_interval is None` | `annotation.py:99-100,74-82` |
| Emission order follows original `document_list` | `annotation.py:503-528` |
| `debug` logging of merge counts only when `debug=True` on outer call; inner passes use `debug=(debug and pass_num == 0)` | `annotation.py:487,511-522` |

### Code paths: chunk extractions lost or document/run aborted

#### A. Silent or partial chunk-level extraction loss (run completes)

| # | Path | Effect | Citation |
|---|---|---|---|
| 1 | `Resolver.resolve`: `FormatError` caught, `suppress_parse_errors=True` | Returns `[]` for that chunk; no extractions appended for chunk | `resolver.py:309-312` |
| 2 | `Resolver.resolve`: `ValueError` from `extract_ordered_extractions`, `suppress_parse_errors=True` | Returns `[]` for that chunk | `resolver.py:317-320` |
| 3 | `_annotate_documents_single_pass`: empty `scored_outputs` | **Not silent** — raises `InferenceOutputError` (see B) | `annotation.py:399-402` |
| 4 | `_merge_non_overlapping_extractions`: later-pass extraction overlaps earlier-pass `char_interval` | Later extraction dropped from merged result | `annotation.py:71-82` |
| 5 | `extract_ordered_extractions`: `index_suffix` set and no index key for extraction class | That extraction skipped (`continue`); other extractions from same chunk kept | `resolver.py:508-515` |
| 6 | `extract_ordered_extractions`: `extraction_data` empty | Returns `[]` for that chunk (valid empty parse) | `resolver.py:466-468,469` |
| 7 | `WordAligner.align_extractions`: fuzzy alignment fails | Extraction still appended to output groups but may remain unaligned (`alignment_status=None`, intervals unset) | `resolver.py:1021-1068,1067-1068` |
| 8 | `accept_match_lesser=False`: partial exact match | Intervals and `alignment_status` cleared; extraction object still yielded | `resolver.py:1015-1019,1067-1068` |
| 9 | `_annotate_documents_single_pass`: `if not batch: continue` | Empty batch skipped (not a chunk loss) | `annotation.py:367-368` |
| 10 | `Resolver.align`: empty `extractions` | Early return; nothing yielded (chunk contributed zero extractions upstream) | `resolver.py:368-373` |

#### B. Document/run aborted (exception propagates; no `AnnotatedDocument` returned)

| # | Path | Exception | Citation |
|---|---|---|---|
| 11 | Empty `scored_outputs` for a chunk | `InferenceOutputError` | `annotation.py:399-402`; defined `core/exceptions.py:125-130` |
| 12 | `Resolver.resolve`: `FormatError`, `suppress_parse_errors=False` | `ResolverParsingError` | `resolver.py:309-313` |
| 13 | `Resolver.resolve`: schema `ValueError`, `suppress_parse_errors=False` | `ResolverParsingError` | `resolver.py:317-321` |
| 14 | Duplicate `document_id` in `_document_chunk_iterator` (`restrict_repeats=True`) | `InvalidDocumentError` | `annotation.py:148-151` |
| 15 | Duplicate `document_id` in `_capture_docs` | `InvalidDocumentError` | `annotation.py:318-321` |
| 16 | `WordAligner`: invalid `exact_alignment_algorithm` | `ValueError` | `resolver.py:845-849` |
| 17 | `WordAligner`: invalid `fuzzy_alignment_algorithm` or threshold/density out of range | `ValueError` | `resolver.py:851-865` |
| 18 | `WordAligner`: delimiter not single token | `ValueError` | `resolver.py:889-890` |
| 19 | `WordAligner`: delimiter appears inside extraction text | `ValueError` | `resolver.py:916-921` |
| 20 | `WordAligner`: token interval IndexError during exact alignment | `IndexError` | `resolver.py:986-991` |
| 21 | `WordAligner`: block size > extraction length | `ValueError` | `resolver.py:1000-1004` |
| 22 | `WordAligner._set_seqs`: empty source or extraction tokens | `ValueError` | `resolver.py:567-568` |
| 23 | `get_token_interval_text`: empty string when `tokenized_text.text` non-empty | `TokenUtilError` | `chunking.py:206-212` |
| 24 | `_sanitize`: whitespace-only text | `ValueError` | `chunking.py:259-261` |
| 25 | `ChunkIterator.__init__`: neither `text` nor `document` | `ValueError` | `chunking.py:400-402` |
| 26 | `create_token_interval`: invalid indices | `ValueError` | `chunking.py:158-163` |
| 27 | `get_token_interval_text`: start >= end | `ValueError` | `chunking.py:193-197` |
| 28 | `get_char_interval`: start >= end | `ValueError` | `chunking.py:232-236` |
| 29 | `SentenceIterator.__init__`: token position out of range | `IndexError` | `chunking.py:301-308` |
| 30 | `TextChunk.chunk_text`: `document_text` unset | `ValueError` | `chunking.py:102-103` |
| 31 | `TextChunk.char_interval`: `document_text` unset | `ValueError` | `chunking.py:135-136` |
| 32 | `extract()`: no examples and no schema | `ValueError` | `extraction.py:203-208` |
| 33 | `extract()`: `output_schema` with `fence_output=True` | `output_schema_fence_error()` | `extraction.py:212-213` |
| 34 | `extract()`: unknown `resolver_params` key | `TypeError` | `extraction.py:377-379` |
| 35 | `extract()`: prompt validation ERROR mode failure | `PromptAlignmentError` (via `pv.handle_alignment_report`) | `extraction.py:228-232` |
| 36 | `extract_ordered_extractions`: index not int | `ValueError` (abort unless caught via suppress path 2) | `resolver.py:477-482` |
| 37 | `extract_ordered_extractions`: attributes not dict/None | `ValueError` | `resolver.py:485-494` |
| 38 | `extract_ordered_extractions`: extraction value wrong type | `ValueError` | `resolver.py:496-503` |
| 39 | `Resolver.string_to_extraction_data`: empty/non-str input | `ValueError` | `resolver.py:421-423` |
| 40 | `Resolver.string_to_extraction_data`: parse failure | `ResolverParsingError` | `resolver.py:430-431` |

**Path count:** 40 (10 silent/partial loss paths A1–A10; 30 abort paths B11–B40).

### Result object: can caller detect per-chunk parse success?

**No.**

After a successful run, the caller receives `data.AnnotatedDocument` (single string input) or `list[data.AnnotatedDocument]` (document iterable) from `extract()` (`extraction.py:75,188-190,403,427`).

`AnnotatedDocument` fields (`core/data.py:206-215`):
- `document_id` (property)
- `extractions: list[Extraction] | None`
- `text: str | None`
- `tokenized_text` (computed property)

There is **no** field for: chunk count, chunks processed, per-chunk parse status, failed-chunk list, or warnings surfaced on the result object. When `suppress_parse_errors=True`, a failed chunk contributes zero extractions indistinguishable from a successfully parsed chunk whose model returned no entities (`resolver.py:310-312,318-320`; merge at `annotation.py:431-432`).

Per-extraction `alignment_status` / `char_interval` on `Extraction` (`core/data.py:74-77,87-88`) reflect alignment, not chunk-level parse success.

## Verdict on the claim(s)
**CONFIRMED:** C4(b) — `extract()` defaults to `suppress_parse_errors=True` (`extraction.py:365`), silently dropping a failed chunk's extractions (`resolver.py:310-312,318-320`), and the returned `AnnotatedDocument` exposes no per-chunk coverage metadata (`core/data.py:206-215`).

## Coverage gaps
None for the four assigned modules. Result-model field enumeration required one out-of-scope read (`core/data.py:206-215`). Retry behavior inside `format_handler.parse_output` and provider `infer()` retry loops are not in the four scoped files (noted above).

## What could still hide a counterexample
- Chunk-level failures handled inside `language_model.infer()` (provider code) that return empty scored output vs raising.
- Parse-retry success/failure inside `format_handler.parse_output` after `FormatError`.
- Batch worker behavior when `max_workers>1` drops or swallows per-chunk errors outside the annotation loop.
