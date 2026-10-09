# 20 - olmocr-VLM-pipeline-analyst

**Verdict:** usable-with-conditions — olmOCR is the strongest open-source reference for per-page PDF rasterization + OpenAI-style VLM requests + YAML-validated structured page metadata, but its production path is **conversion** (emit markdown), not **QA-of-conversion**; port the image/request/validation skeleton and invert the prompt/output to judge whisker markdown against the page image, while dropping temperature escalation, parallel in-flight pages, and pdftotext fallback.
**Confidence:** high

## Findings

- [CRITICAL] **Production inference does NOT use document anchoring.** `build_page_query` sends only `build_no_anchoring_v4_yaml_prompt()` plus the PNG; `--target_anchor_text_len` is documented as unused for new models (`olmocr/pipeline.py:139-141,1230`). v1 anchoring lives in training/bench: `get_anchor_text(..., pdf_engine="pdfreport")` linearizes position-tagged text (`[x y]content`, `[Image x0 y0 to x1 y1]`) capped at `target_length`, wrapped in `RAW_TEXT_START`/`RAW_TEXT_END` via `build_finetuning_prompt` or `NewYamlFinetuningPromptWithAnchoring` (`olmocr/prompts/anchor.py:17-49,256-360`, `olmocr/prompts/prompts.py:147-154`, `olmocr/train/dataloader.py:206-236`). Fallback after VLM failure uses plain `pdftotext` only, not full anchor report (`olmocr/pipeline.py:233-249`). Impact: for whisker QA, **do not** copy conversion prompts; optionally port **pdfreport-style anchor** as supplementary *untrusted* text alongside page image + converted markdown (DOCR-Inspector / coarse pattern from `05-web.md:76-83`), not as the model's output target.

- [HIGH] **Page rendering: poppler subprocess, longest-side pixel budget.** `get_pdf_media_box_width_height` shells `pdfinfo -f N -l N -box` for MediaBox width/height in points (`olmocr/data/renderpdf.py:8-35`). `render_pdf_to_base64png` sets `-r` to `target_longest_image_dim * 72 / longest_dim` so the longest page side renders to exactly `target_longest_image_dim` pixels (72 px/point conversion at `renderpdf.py:39-59`); CLI default **1288** (`olmocr/pipeline.py:1229`). PNG bytes are base64-encoded for `data:image/png;base64,...` (`renderpdf.py:59`, `pipeline.py:141`). Rotation retries PIL-transpose the decoded PNG before re-encode (`pipeline.py:114-131`). Render concurrency capped by `pdf_render_max_workers_limit` semaphore tied to CPU count (`pipeline.py:87-88,111-112`). Impact: **port the math** (`longest_side_px = target_dim`) via PyMuPDF `fitz.Matrix(scale, scale)` where `scale = target_dim / max(page.rect)` (`00-baseline.md:83-84`); drop poppler/pdfinfo deps.

- [HIGH] **Request shape: text-first multimodal user message, fixed generation budget.** `build_page_query` returns OpenAI chat JSON: single `user` message, `content` order **(1) text prompt, (2) image_url** (`olmocr/pipeline.py:133-146`; tests assert `content[1]["image_url"]` at `tests/test_pipeline.py`). `max_tokens=8000`; base `temperature=0.0` overridden per attempt (`pipeline.py:107,144-145,164-177`). POST to `{server}/chat/completions`, default model `allenai/olmOCR-2-7B-1025-FP8` (`pipeline.py:161,1212-1215`). Optional `guided_regex` when `--guided_decoding` (`pipeline.py:179-182`). Impact: vLLM `image_url` data-URI packaging is directly portable (`05-web.md:40-43`); whisker must add multimodal `content` parts end-to-end (`00-baseline.md:73`); pre-resize client-side because vLLM ignores per-request pixel limits (`05-web.md:51-55`).

- [HIGH] **Retry ladder: 8 attempts, temperature escalation, rotation-aware branch.** `MAX_RETRIES = args.max_page_retries` default **8** (`pipeline.py:1221,289-290`). `TEMPERATURE_BY_ATTEMPT = [0.1, 0.1, 0.2, 0.3, 0.5, 0.8, 0.9, 1.0]` indexed by attempt (`pipeline.py:84-85,164-165`). Attempt 0 first; if `is_rotation_valid` is false, sequential retries with cumulative `rotation_correction` from model YAML (`pipeline.py:296-331,307-318`). Non-rotation failures retry sequentially, then fire **parallel** remaining attempts when vLLM queue depth is 0 (`pipeline.py:334-361,345`). Connection errors: up to 10 exponential backoff sleeps inside `try_single_page_with_backoff` (`pipeline.py:265-279`). Impact: **not portable** to whisker determinism (D5 pins temperature/seed; D11 serial in-flight); keep **rotation retry idea** only if QA model emits orientation metadata; use fixed `temperature=0` and serial page loop.

- [HIGH] **Response validation: YAML front matter + PageResponse schema, soft validity flags.** Model must return markdown with `---` YAML block then body; `FrontMatterParser` extracts fields into `PageResponse` (`primary_language`, `is_rotation_valid`, `rotation_correction`, `is_table`, `is_diagram`; body → `natural_text`) (`olmocr/train/front_matter.py:37-99`, `olmocr/prompts/prompts.py:66-93,164-170`). `try_single_page` sets `is_valid=False` if `total_tokens > 16384` or `finish_reason != "stop"` but still parses YAML unless exception (`pipeline.py:162,200-217`). Parse exceptions → `None` (retry). Impact: whisker should use **Pydantic `output_type`** (D6/D10) for QA verdicts, not free YAML regex; olmOCR's front-matter pattern is a useful precedent for mixing metadata + prose in one completion.

- [HIGH] **Aggregation: per-page parallel TaskGroup, fallback-tolerant doc gate.** All pages `1..num_pages` dispatched concurrently via `asyncio.TaskGroup` (`pipeline.py:548-554`). Results ordered by task creation order (page 1..N). `build_dolma_document` concatenates `natural_text` with newlines, records char spans per page (`pipeline.py:602-651`). **One failed VLM page does NOT fail the doc:** exhausted retries → `make_fallback_result` (pdftotext) with `is_valid=True`, `is_fallback=True` (`pipeline.py:329-331,371-374,555-567`). Document **discarded** only if `num_fallback_pages / num_pages > max_page_error_rate` (default **0.004** = 1/250) (`pipeline.py:1222,559-563`); empty concatenated text → `None` (`pipeline.py:619-621`). `PdfFilter` (optional `--apply_filter`) drops whole PDFs pre-loop: non-English, forms, SEO spam (`olmocr/filter/filter.py:14-113`, `pipeline.py:540-542,91`). Impact: olmOCR's fallback policy optimizes **corpus yield**, opposite of whisker **fidelity** (fail not partial); QA lane must **fail the paper** on any unrasterizable page or VLM error, not silently substitute pdftotext.

- [MED] **Work queue, concurrency, resume.** `WorkQueue` stores SHA1-grouped PDF paths in zstd CSV index; `initialize_queue` skips `done_flags`, shuffles remainder (`olmocr/work_queue.py:127-171`). Worker locks (30 min stale) prevent duplicate work; `mark_done` writes `done_{hash}.flag` (`work_queue.py:173-229,338-354`). Pipeline runs `--workers` default 20 async workers, each processing one work item's PDFs in parallel (`pipeline.py:1223,698-802`). VLLM concurrency default **1600** via global `max_concurrent_requests_limit` (`pipeline.py:88,1224,1287-1289`). Impact: resume/locking pattern is overkill for single-paper whisker CLI; borrow **idempotent page artifact paths** if batching WG21 mailings later; keep **one in-flight VLM request** (D11).

- [MED] **Minimal port recipe (QA lane pseudocode).** Adapt olmOCR mechanics to serial PyMuPDF + judge prompt:

```python
TARGET_LONGEST = 1288  # match olmocr default (pipeline.py:1229)
for page_num in range(1, doc.page_count + 1):
    rect = doc[page_num - 1].rect
    scale = TARGET_LONGEST / max(rect.width, rect.height)
    pix = doc[page_num - 1].get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    b64 = base64.b64encode(pix.tobytes("png")).decode()
    md_chunk = page_markdown_slice(pid, page_num)  # from tomd/whisker, inject_untrusted
    msg = [{"type": "text", "text": QA_PROMPT + wrap_source(md_chunk)},
           {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]
    verdict = await run_agent(ctx, spec, user_msg=msg, output_type=PageQAVerdict)  # serial, temp=0
    if verdict.status == "error": raise FidelityError(f"page {page_num}")
aggregate(page_verdicts)  # ordered merge; any fail → fail paper
```

Evidence pattern: `renderpdf.py:39-59`, `pipeline.py:133-146`, `00-baseline.md:66-73`. Impact: ~25 lines maps olmOCR's hot path to whisker invariants without poppler, temperature ladder, or conversion fallback.

## False-pass hypothesis

After 8 VLM failures on a dense table page, `make_fallback_result` injects **pdftotext** as `natural_text` with `is_valid=True` (`pipeline.py:233-249,371-374`). If that page is 1 of 250, the document still ships (`max_page_error_rate=0.004`, `pipeline.py:559-567`). Mapped to whisker: copying fallback semantics would **false-pass** a corrupted markdown conversion whenever the VLM times out but poppler text happens to match token multiset, while the visual table structure is wrong (table QA EM 2–12% zero-shot, `05-web.md:62-63`).

## False-fail hypothesis

Rotation retry path returns a result with `is_rotation_valid=False` if `is_valid` but rotations never converge (`pipeline.py:322-326`). Mapped to whisker: if ported rotation metadata gates QA, correctly converted pages photographed skewed in scan could **false-fail** unless QA prompt ignores rotation flags and judges content only.

## What would change my mind

Finding an olmOCR production code path (not bench/train) that accepts **existing markdown plus page image** and emits a pass/fail fidelity verdict without rewriting the page. Current `pipeline.py` always targets `natural_text` extraction via `build_no_anchoring_v4_yaml_prompt()` (`pipeline.py:139,164-170`); the closest published analogue remains DOCR-Inspector / coarse `extraction_qa.py` (`05-web.md:76-83`), not olmOCR inference itself.
