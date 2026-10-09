# 10b - olmocr page-coverage and failure semantics

**Claims tested:** C4(b) adjacent (olmocr extraction coverage vs verification); page-level audit facts for foreign-repo comparison. C1/C2/C3 not primary scope.

**Exhaustive:** yes

**Repo SHA:** f7cfe4c (matches baseline pin)

## Method

Search commands:

```text
rg -n "process_page|make_fallback|filter_out|is_fallback|try_single_page|build_dolma|return None" olmocr/olmocr --glob "*.py"
git rev-parse HEAD  # in packages/whisker/research/repos/olmocr
```

Files read in full (page-routing callees of `pipeline.py`):

- `olmocr/pipeline.py`
- `olmocr/filter/filter.py`
- `olmocr/prompts/prompts.py`
- `olmocr/prompts/anchor.py`
- `olmocr/prompts/__init__.py`
- `olmocr/train/front_matter.py`
- `olmocr/data/renderpdf.py`
- `olmocr/work_queue.py`
- `olmocr/metrics.py`
- `olmocr/image_utils.py`
- `olmocr/check.py`

Not read in full (imported by pipeline but no page-routing logic beyond I/O): `olmocr/s3_utils.py` (partial: `process_pdf` only catches `NoSuchKey` at `pipeline.py:582-587`; other download errors propagate to `worker`).

## Architecture (page loop)

Every PDF that reaches `process_single_pdf` schedules one `process_page` task per physical page (`pipeline.py:548-551`, pages 1..`num_pages`). There is no per-page router that skips the VLM before the first `try_single_page` call. The only per-page non-VLM output path is `make_fallback_result` after retry exhaustion (`pipeline.py:233-250`, called at `332` and `375`).

VLM call chain: `process_page` → `try_single_page_with_backoff` → `try_single_page` → `build_page_query` → `render_pdf_to_base64png` (`renderpdf.py:39-60`) → HTTP POST to `/chat/completions` (`pipeline.py:184-185`).

## Inventory

Category key: **(a)** skip VLM, **(b)** fail then retry, **(c)** fail permanently (output produced), **(d)** dropped from output.

| ID | Cat | File:line | Role / finding |
|----|-----|-----------|----------------|
| P01 | a | `pipeline.py:332` | Rotation-retry branch exhausted → `make_fallback_result` (pdftotext, no further VLM). |
| P02 | a | `pipeline.py:375` | Non-rotation retry branch exhausted → `make_fallback_result`. |
| P03 | a | `pipeline.py:233-250` | Fallback implementation: `get_anchor_text(..., pdf_engine="pdftotext")`, `is_fallback=True`, `input_tokens=0`, `output_tokens=0`. |
| P04 | a,d | `pipeline.py:540-542` | `--apply_filter` and `PdfFilter.filter_out_pdf` → return `None` before any page task (all pages skip VLM). |
| P05 | a,d | `filter.py:71-73` | Form PDF → `filter_out_pdf` returns True. |
| P06 | a,d | `filter.py:74-76` | PdfReader exception → filter out. |
| P07 | a,d | `filter.py:85-87` | pdftotext on pages 1-5 fails → filter out. |
| P08 | a,d | `filter.py:103-105` | Detected language not in `languages_to_keep` → filter out. |
| P09 | a,d | `filter.py:108-110` | Download/SEO spam threshold exceeded → filter out. |
| P10 | a,d | `pipeline.py:534-536` | `PdfReader.get_num_pages()` fails → abort document, no pages processed. |
| P11 | a,d | `pipeline.py:583-585` | S3 `NoSuchKey` → skip document entirely. |
| P12 | b | `pipeline.py:296` | First VLM attempt (`attempt=0`) for every page. |
| P13 | b | `pipeline.py:164-165,177` | Retry attempt selects higher `temperature` from `TEMPERATURE_BY_ATTEMPT`. |
| P14 | b | `pipeline.py:187-191` | HTTP status != 200 → `try_single_page` returns `None` → `process_page` retries. |
| P15 | b | `pipeline.py:202-203` | `usage.total_tokens > MODEL_MAX_CONTEXT` (16384) → `is_valid=False` → retry. |
| P16 | b | `pipeline.py:205-206` | `finish_reason != "stop"` → `is_valid=False` → retry. |
| P17 | b | `pipeline.py:228-230` | Parse/YAML/other exception in `try_single_page` → returns `None` → retry. |
| P18 | b | `pipeline.py:266-275` | `ConnectionError`/`OSError`/`asyncio.TimeoutError` → up to 10 exponential backoff replays inside `try_single_page_with_backoff` before returning to `process_page`. |
| P19 | b | `pipeline.py:308-317` | `result is not None and not result.response.is_rotation_valid` → sequential rotation retries with cumulative `rotation_correction`. |
| P20 | b | `pipeline.py:335-341` | Non-rotation failure path → sequential retries over `retry_attempts` (`range(1, max_page_retries)`). |
| P21 | b | `pipeline.py:345-363` | After a failed sequential retry, if `vllm_queued_requests == 0`, fire remaining attempts in parallel via `asyncio.as_completed`. |
| P22 | c | `pipeline.py:302-305` | First attempt success: `is_valid` and `is_rotation_valid` → return VLM `PageResult` (`is_fallback=False`). |
| P23 | c | `pipeline.py:314-317` | Rotation branch: valid + rotation_valid on retry → return VLM result. |
| P24 | c | `pipeline.py:322-326` | Rotation branch: retries exhausted but last `result.is_valid` → return VLM text even if rotation still invalid (not pdftotext fallback). |
| P25 | c | `pipeline.py:338-341` | Non-rotation branch: valid success on retry → return VLM result. |
| P26 | c | `pipeline.py:355-360` | Parallel retry success → return VLM result. |
| P27 | c | `pipeline.py:366-369` | Non-rotation branch: retries exhausted but last `result.is_valid` → return VLM text (may still have bad rotation). |
| P28 | c | `pipeline.py:328-332` | Rotation branch permanent fallback → pdftotext (`P01`). |
| P29 | c | `pipeline.py:371-375` | Non-rotation branch permanent fallback → pdftotext (`P02`). |
| P30 | c,d | `pipeline.py:559-563` | If `num_fallback_pages / num_pages > max_page_error_rate` (default 0.004) → discard entire Dolma document (`return None`). |
| P31 | c,d | `pipeline.py:619-621` | `build_dolma_document`: concatenated `document_text` empty → `return None`. |
| P32 | c,d | `pipeline.py:570-572` | Any exception in `process_single_pdf` outer `try` → `return None`. |
| P33 | d | `pipeline.py:548-553` | `asyncio.TaskGroup` for pages: uncaught exception in any `process_page` aborts whole PDF (no partial doc). Triggers include `renderpdf.py:59` assert on pdftoppm failure, `anchor.py:59` assert if pdftotext fails during fallback. |
| P34 | d | `pipeline.py:511` | `process_tarball`: `process_single_pdf` returning `None` omitted from tarball result list. |
| P35 | d | `pipeline.py:497-503` | Tarball members not ending in `.pdf` never extracted or processed. |
| P36 | d | `pipeline.py:727-732` | `worker`: failed `process_pdf`/`process_tarball` tasks → `result=None` → skipped when building JSONL. |
| P37 | d | `pipeline.py:803-804` | `worker` outer exception → work item not written to results (logged only). |
| P38 | d | `pipeline.py:277-278` | Max connection backoff in `try_single_page_with_backoff` → `sys.exit(1)` (job-level termination, in-flight docs lost). |
| P39 | — | `pipeline.py:609-612` | Page with `natural_text is None` → empty string in doc text; span still appended (page not dropped). |
| P40 | — | `pipeline.py:602-651` | Successful Dolma doc: per-page spans in `attributes.pdf_page_numbers`; doc-level `metadata.pdf-total-pages`, `metadata.total-fallback-pages`; per-page `primary_language`, `is_rotation_valid`, `rotation_correction`, `is_table`, `is_diagram` arrays. **No per-page `is_fallback` field in output.** |
| P41 | — | `pipeline.py:1222` | `--max_page_retries` default 8 (attempt 0 plus `range(1,8)` = 7 further attempts). |
| P42 | — | `pipeline.py:1222` | `--max_page_error_rate` default 0.004 (1/250 fallback pages discards whole doc). |

**Path count:** 42 inventory rows (P01–P42). Distinct routing outcomes: 29 for categories a–d (P01–P38 excluding audit-only P39–P42).

## (a) Skip VLM — summary

Per-page skip of VLM (output still produced for that page): **only** P01–P03 (`make_fallback_result` after retries).

Document-level skip of VLM (no page ever calls VLM): P04–P11 when filter/page-count/S3 miss applies.

There is **no** production path that emits page text without at least one VLM attempt first, except fallback after failure.

## (b) Fail and retry — summary

Failure signals that trigger retry (P14–P17) are evaluated inside `try_single_page`. Connection-layer retries (P18) wrap each attempt. `process_page` orchestrates up to `max_page_retries` attempts (P12, P19–P21) with rotation-aware branching at P19.

Success short-circuit (no further retries): P22–P27.

## (c) Fail permanently — summary

| Outcome | Marker in `PageResult` | In Dolma JSONL |
|---------|------------------------|----------------|
| pdftotext fallback | `is_fallback=True`, tokens 0 | Included if doc passes fallback-rate gate; only **aggregate** `metadata.total-fallback-pages` |
| Degraded VLM accept | `is_fallback=False`, may have invalid rotation | Included; no failure marker |
| Whole doc discarded | N/A | No record |

## (d) Dropped from output — summary

No path drops an individual page from an emitted document while siblings remain. Drop is always document-level (P30–P37) or job-level (P38). Empty `natural_text` pages remain as zero-width spans (P39).

## Per-page coverage audit from output

**Partially auditable.**

What the caller **can** verify from a emitted Dolma JSONL record:

- `metadata.pdf-total-pages` vs source PDF page count (if source known).
- `len(attributes.pdf_page_numbers)` equals `pdf-total-pages`; each span is `[start, end, page_num]` (`pipeline.py:617,643`).
- Aggregate fallback count: `metadata.total-fallback-pages` (`pipeline.py:630`).
- Per-page VLM metadata arrays: `primary_language`, `is_rotation_valid`, `rotation_correction`, `is_table`, `is_diagram` (`pipeline.py:644-648`).

What the caller **cannot** verify from output alone:

- **Which specific pages** used pdftotext fallback (`is_fallback` exists on `PageResult` but is **not serialized** per page in `build_dolma_document`).
- Whether a page ever received a VLM call vs only fallback (except heuristic: fallback pages have `input_tokens=0` at processing time but per-page token counts are not in attributes).
- Documents filtered or discarded (P04–P11, P30–P37): **no JSONL row**; only logs / missing `Source-File` in stats (`pipeline.py:1180` compares processed vs original paths).

Markdown output (`--markdown`, `pipeline.py:766-794`) mirrors `doc["text"]` only; no per-page markers.

Runtime metrics/logs: `metrics.add_metrics(failed_pages=1)` at `pipeline.py:330,373`; `WorkerTracker` states `started`/`finished`/`errored` (`pipeline.py:293-294,304,331,374`).

## Verdict on the claim(s)

**PARTIALLY** — olmocr extraction attempts VLM on every page of every non-filtered PDF; permanent page failure falls back to pdftotext; document-level gates can drop entire PDFs. Output supports page-count and aggregate-fallback audit but **not** per-page VLM-vs-fallback audit (C4-adjacent foreign fact for comparison with tapetum review mode).

## Coverage gaps

- `olmocr/s3_utils.py` not read in full; only `NoSuchKey` handling verified at call site.
- Bench runner `olmocr/bench/runners/run_olmocr_pipeline.py` imports `process_page` but is eval harness, out of production pipeline scope.
- No runtime execution; all findings from static read at SHA f7cfe4c.

## What could still hide a counterexample

- An unreviewed code path in `s3_utils` retry/backoff that swallows errors without logging.
- Future CLI wrappers not importing `pipeline.py` directly.
- Work-queue redelivery after P37/P38 leaving duplicate or missing JSONL without a manifest tying input PDF paths to outputs (done flags mark work **groups**, not individual PDFs).
