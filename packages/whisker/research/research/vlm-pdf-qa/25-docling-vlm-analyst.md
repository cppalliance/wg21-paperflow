# 25 - docling-VLM-analyst

**Verdict:** usable-with-conditions — the baseline claim holds: `api_image_request.py` is the cleanest self-contained OpenAI-compatible page-image request builder in the survey, but docling's VLM path is **conversion** (DocTags/markdown per page), returns **empty text on HTTP/parse failure** (not fail-loud), and has **no JSON-schema / pydantic output_type** on vision calls; port the ~40-line request builder + `VlmStopReason` mapping only, not `VlmPipeline` assembly or DocTags parsing.
**Confidence:** high

## Findings

- [CRITICAL] **Minimal portable request builder confirmed: PIL → PNG → base64 data URI → OpenAI multipart user message.** `api_image_request(image, prompt, url, timeout=20, **params)` copies the PIL image, converts to RGBA, saves PNG to `BytesIO`, base64-encodes, and POSTs JSON with `messages[0].content = [{"type":"image_url","image_url":{"url":"data:image/png;base64,..."}}, {"type":"text","text": prompt}]` plus caller-supplied params (`model`, `max_tokens`, `temperature`, etc.) — `docling/docling/utils/api_image_request.py:165-213`. Response: validate with `OpenAiApiResponse.model_validate`, extract `choices[0].message.content` (or tool-call arguments fallback), map `finish_reason` to `VlmStopReason` incl. `CONTENT_FILTERED` on `"content_filter"` — `api_image_request.py:75-98,243-254`. Retry session: 5 retries, backoff 0.1, status list `(429,500,502,503,504)` — `api_image_request.py:24-46`. Impact: **this is the wire-format reference to port** into a new `VllmVisionBackend`; matches olmocr/marker/vLLM docs (`00-baseline.md:44`, `05-web.md:40-43`); image-first part order (docling) vs olmocr text-first is immaterial to vLLM.

- [HIGH] **ApiVlmModel orchestration: page image at `vlm_options.scale`, RGB normalize, concurrent POSTs.** Legacy API path: for each valid page, `hi_res_image = page.get_image(scale=self.vlm_options.scale, max_size=self.vlm_options.max_size)` — `docling/docling/models/vlm_pipeline_models/api_vlm_model.py:71-75`; converts non-RGB PIL to RGB — `api_vlm_model.py:131-133`; calls `api_image_request(..., url=self.vlm_options.url, timeout=self.timeout, headers=..., **self.params)` where `params = {**vlm_options.params, "temperature": vlm_options.temperature}` — `api_vlm_model.py:41-46,163-170`. Results batched via `ThreadPoolExecutor(max_workers=self.concurrency)` — `api_vlm_model.py:185-186`. Remote calls gated by `enable_remote_services=True` or `OperationNotAllowed` — `api_vlm_model.py:34-39`. Impact: scale/temperature/timeout are **options-layer** concerns; whisker should pass `temperature=0` via params and keep **concurrency=1** (D11); do not copy ThreadPool default `concurrency=4` from Granite API preset (`vlm_model_specs.py:67`).

- [HIGH] **VLM options: `scale=2.0` default (~144 DPI), prompt strings, API presets.** `BaseVlmOptions.scale` default **2.0**, range note 0.5–4.0 — `docling/docling/datamodel/pipeline_options_vlm_model.py:48-57`. SmolDocling/GraniteDocling prompt: `"Convert this page to docling."`, `response_format=DOCTAGS`, `temperature=0.0`, `scale=2.0` — `docling/docling/datamodel/vlm_model_specs.py:22-37,98-124`. Remote Granite preset: `ApiVlmOptions(url="http://localhost:8000/v1/chat/completions", timeout=90, scale=2.0, concurrency=4, params={model, max_tokens})` — `vlm_model_specs.py:56-70`. `ApiVlmOptions.timeout` default **60.0** — `pipeline_options_vlm_model.py:391-400`. New `VlmConvertOptions.scale` also defaults **2.0** — `docling/docling/datamodel/pipeline_options.py:950-952`. Impact: for whisker QA, reuse **scale=2.0 / ~144 DPI** as starting resolution; replace conversion prompt with page-scoped fidelity judge prompt; pre-resize client-side (vLLM ignores per-request pixel caps, `05-web.md:51-55`).

- [HIGH] **Page image provisioning: pypdfium2 PdfBackend, supersample-then-downscale.** `Page.get_image(scale)` caches by scale, optionally caps via `max_size`, delegates to `page._backend.get_page_image(scale=scale)` — `docling/docling/datamodel/base_models.py:459-474`. Both `PyPdfiumDocumentBackend` and `DoclingParseDocumentBackend` render with `pypdfium2`: `page.render(scale=scale * 1.5, ...)` then `PIL.resize` to `(cropbox.width * scale, cropbox.height * scale)` for sharpness — `docling/docling/backend/pypdfium2_backend.py:357-391`, `docling/docling/backend/docling_parse_backend.py:203-237`. Pipeline-level `images_scale` defaults **1.0** on `PaginatedPipelineOptions` — `pipeline_options.py:1311-1320`; VLM pipeline sets `page._default_image_scale` from `pipeline_options.images_scale` in `initialize_page` — `vlm_pipeline.py:209-211`. CLI forces `images_scale=2` for VLM mode — `cli/main.py:1091`. Impact: effective VLM input resolution is **`vlm_options.scale` (2.0)**, not pipeline `images_scale`; whisker should mirror **scale-as-DPI-factor** via PyMuPDF `Matrix(scale, scale)` (`00-baseline.md:83-84`) rather than adding pypdfium2; optional 1.5× supersample is a quality tweak, not required.

- [HIGH] **Long documents: per-page VLM always; doc-level pass is assembly only.** `PaginatedPipeline._build_document` iterates all pages in batches of `settings.perf.page_batch_size` (default **4**) — `docling/docling/datamodel/settings.py:32`, `docling/docling/pipeline/base_pipeline.py:256-265`; each batch runs `initialize_page` → VLM model → yields pages. No second doc-wide VLM call. Document assembly concatenates per-page outputs: DocTags via `DocTagsDocument.from_doctags_and_image_pairs` — `vlm_pipeline.py:446-466`; markdown/HTML via per-page backend re-parse — `vlm_pipeline.py:676-718`. `document_timeout` can truncate with `PARTIAL_SUCCESS` — `base_pipeline.py:295-313`. Impact: whisker QA should follow same **serial/per-page loop + ordered aggregation** pattern as tapetum_llm chunk aggregation (`12-api-contract-analyst.md:16`); no docling-style doc-level VLM exists to port.

- [HIGH] **Response format / D6: free-text + post-hoc parse, not structured output on vision API.** `ResponseFormat` enum (DOCTAGS, MARKDOWN, DOCLANG, …) guides **downstream parsing**, not API `response_format` JSON schema — `pipeline_options_vlm_model.py:101-110`. API path returns raw `generated_text`; `decode_response` is identity unless overridden — `pipeline_options_vlm_model.py:97-98`. DocTags assembled by feeding VLM text strings into `DocTagsDocument.from_doctags_and_image_pairs` — `vlm_pipeline.py:446-466`. No `json_schema`, `guided_regex`, or OpenAI structured-output in `api_image_request` or `api_vlm_model`. Impact: docling's DocTags discipline is **prompt + string parsing**, irrelevant to whisker D6; we must keep **Pydantic `output_type` + ModelRetry** on QA verdicts (`CLAUDE.md` D6/D10); expect more retries than docling's empty-string fallback.

- [MED] **Failure handling conflicts with whisker fidelity.** HTTP non-OK, empty body, JSON decode error, or exception → `ApiImageRequestResult("", 0, VlmStopReason.UNSPECIFIED)` with error logged — `api_image_request.py:224-231,234-235,256-260`. `VlmPipeline._determine_status` promotes `LENGTH` and `CONTENT_FILTERED` stop reasons to `ConversionStatus.PARTIAL_SUCCESS` with per-page `ErrorItem` — `vlm_pipeline.py:245-272`; missing `vlm_response` also `PARTIAL_SUCCESS` — `vlm_pipeline.py:247-257`. Impact: docling optimizes **partial conversion yield**; whisker must **invert** this — raise/fail paper on `UNSPECIFIED`, `LENGTH`, or `CONTENT_FILTERED` for QA; only borrow the stop-reason taxonomy.

- [MED] **License and porting surface.** MIT License, IBM copyright 2024 — `docling/LICENSE:1-21`. Hot portable modules: `api_image_request.py` (328 LOC), `api_vlm_model.py` (187 LOC), option defaults in `pipeline_options_vlm_model.py` + `vlm_model_specs.py`. Dependencies for API path: `requests`, `PIL`, `pydantic` (response models in `base_models.py:497-520`). No docling-core import in `api_image_request.py`. Impact: **extract `api_image_request` logic** (~60 lines core) into `packages/pipeline` vision backend with BSL header; do not depend on docling package at runtime.

- [MED] **Distilled request-builder pseudocode (<20 lines).**

```python
def post_page_image_vlm(pil: Image, prompt: str, *, url, timeout=60, model, max_tokens, temperature=0.0, headers=None):
    buf = BytesIO()
    pil.copy().convert("RGBA").save(buf, "PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    payload = {"messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        {"type": "text", "text": prompt},
    ]}], "model": model, "max_tokens": max_tokens, "temperature": temperature}
    r = retry_session.post(url, json=payload, headers=headers or {}, timeout=timeout)
    if not r.ok: raise VlmRequestError(r.status_code, r.text)  # docling returns ""; we fail loud
    data = OpenAiApiResponse.model_validate(r.json())
    text = (data.choices[0].message.content or "").strip()
    stop = {"content_filter": CONTENT_FILTERED, "length": LENGTH}.get(data.choices[0].finish_reason, END_OF_SEQUENCE)
    return text, stop, data.usage
```

Evidence: `api_image_request.py:176-213,243-254`; whisker change: raise instead of `return ApiImageRequestResult("", ...)`.

## False-pass hypothesis

VLM API returns HTTP 502; `api_image_request` logs and returns `text=""` with `VlmStopReason.UNSPECIFIED` — `api_image_request.py:224-231`. `_turn_dt_into_doc` still builds a document from empty doctags strings — `vlm_pipeline.py:449-457`. Mapped to whisker: copying docling's silent-empty pattern would let a failed vision QA call produce **no axis findings**, and `_custom_decide` could inherit a passing tier1 verdict (`14-false-pass-hunter.md` hypothesis).

## False-fail hypothesis

`ApiVlmModel` converts every image to RGB before PNG encode — `api_vlm_model.py:131-133`; `api_image_request` then forces RGBA — `api_image_request.py:180-180`. Unusual PDF page color spaces (CMYK scan) could shift hues slightly vs PyMuPDF raster; a strict pixel-compare QA prompt could **false-fail** color-faithful conversions while text is correct. Mitigation: judge semantic/text/layout fidelity, not pixel identity.

## What would change my mind

A docling code path (not hypothetical) that sends **page image + existing markdown** to the API and returns a structured pass/fail QA verdict. Current `ApiVlmModel._build_prompt_safe` returns only the conversion prompt (`pipeline_options_vlm_model.py:79-95`); closest published match remains DOCR-Inspector / coarse `extraction_qa.py` (`05-web.md:76-83`), not docling VLM inference.
