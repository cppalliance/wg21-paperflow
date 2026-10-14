# Opus Meta-Review C - Engineering Quality / Portability

Re-verification of the concrete port targets for the whisker LLM QA VLM lane against
the actual repo code (2026-07-07). Every anchor below was opened and confirmed; the
five mandate items were re-checked line-by-line, plus the supporting call sites the
port map depends on. Corrections to persona claims are called out inline and collected
in section 3.

Verification method: read the cited files directly; ran `uv run --package pipeline
python` twice to confirm the installed pydantic-ai surface (not a lockfile-only claim).

---

## 1. Mandate re-verification (5 items)

### (1) docling `api_image_request.py` - minimal request builder + content-part order

- **Path CONFIRMED:** `packages/whisker/research/repos/docling/docling/utils/api_image_request.py` (389 LOC, not 328 as baseline `00:44` states - baseline undercounts; the file has two builders).
- **Two builders, not one.** Non-streaming `api_image_request(image, prompt, url, timeout=20, headers=None, *, usage_response_key="usage", token_extract_key=None, **params)` at lines **165-260**; streaming `api_image_request_streaming(...)` at **263-389**.
- **Content-part order CONFIRMED = IMAGE FIRST, then TEXT.** Non-streaming builder, `messages[0]["content"]` at **192-208**: `{"type":"image_url","image_url":{"url":"data:image/png;base64,..."}}` (196-201) precedes `{"type":"text","text": prompt}` (202-205). Streaming builder mirrors it at **285-296**. This matches persona 25 (`25:8`) and contradicts olmocr's text-first order (see item 4). For our path the order is immaterial: we route through pydantic-ai, which composes parts from the `Sequence[UserContent]` we hand it.
- **Encode path CONFIRMED:** `image.copy()` -> `.convert("RGBA")` -> `image.save(img_io,"PNG")` -> `base64.b64encode(...).decode("utf-8")` at **176-190**. The `copy()`/RGBA dance is a PIL-input robustness fix; irrelevant when we feed PyMuPDF `pix.tobytes("png")` bytes directly.
- **Stop-reason taxonomy CONFIRMED:** `_map_stop_reason` at **91-98** maps `"content_filter" -> CONTENT_FILTERED`, `"length" -> LENGTH`, else `END_OF_SEQUENCE`. Baseline `00:45` cited 92-94; accurate.
- **Retry session CONFIRMED:** total=5, backoff=0.1, forcelist `(429,500,502,503,504)`, `allowed_methods={"POST"}`, `raise_on_status=False` at **24-46**.
- **Fail-silent CONFIRMED (the anti-pattern to invert):** every error path returns `ApiImageRequestResult("", 0, VlmStopReason.UNSPECIFIED)` at **231, 235, 258, 260**. Whisker must raise instead (fidelity: fail not partial).

**Verdict on item 1:** the "minimal request builder" claim HOLDS for the non-streaming `api_image_request` core (~176-255). See CORRECTION 1 and CORRECTION 2 for two evidence errors in the persona reports.

### (2) pydantic-ai multimodal (`BinaryContent` in the pinned version)

- **Pin CONFIRMED:** `pydantic-ai == 1.89.1` at `uv.lock:2882-2883`; `packages/pipeline/pyproject.toml:11` declares `pydantic-ai-slim` (resolved with the `openai`/`anthropic`/... extras, `uv.lock:2886`).
- **Runtime CONFIRMED (not just lockfile):** `uv run --package pipeline python` reports `version 1.89.1`; `from pydantic_ai.messages import BinaryContent, ImageUrl` succeeds; `inspect.signature(Agent.run)` shows `user_prompt: 'str | Sequence[UserContent] | None' = None`.
- **`UserContent` membership CONFIRMED:** `typing.get_args(UserContent)` = `(str, TextContent, Annotated[ImageUrl | AudioUrl | DocumentUrl | VideoUrl | BinaryContent | UploadedFile, Discriminator('kind')], CachePoint)`. `BinaryContent` and `ImageUrl` are valid members (nested inside the discriminated-union `Annotated` member). See CORRECTION 4.

**Verdict on item 2:** multimodal support is real in the pinned version. `agent.run([wrapped_text, BinaryContent(data=png, media_type="image/png")], output_type=...)` is a supported call shape. No new message type needs inventing inside `pipeline`.

### (3) Proposed `user_media` kwarg change points

All four cited surfaces exist as claimed (personas 12, 31, 16):

| Surface | Signature today | Anchor |
| --- | --- | --- |
| `run_agent` | `(ctx, spec, user_msg: str, *, request_limit=...)` | `packages/pipeline/src/pipeline/runner.py:219-225` |
| `run_task` | `(agent, system_prompt, user_message: str, output_type, *, tools, label, debug_log)` | `packages/pipeline/src/pipeline/tasks.py:41-50` |
| `AgentBackend.run` | `(self, system_prompt, user_message: str, output_type, *, tools, max_tokens, thinking_budget, label, debug_log, request_limit)` | `packages/pipeline/src/pipeline/agents.py:110-121` |
| `ModelBackend.run` (ABC) | `(self, system_prompt, user_message: str, output_type, *, max_tokens, tools, thinking_budget, label, debug_log, request_limit)` | `packages/pipeline/src/pipeline/model_backends.py:190-203` |

Supporting anchors also CONFIRMED:
- Text-only user message is materialized in `VllmThinkingBackend.run` at `model_backends.py:288-291` (`{"role":"user","content": user_message}` - a plain string, the exact spot that becomes a lie under multimodal).
- pydantic-ai backends already call `agent.run(user_message, ...)`: `_run_with_tools` at `model_backends.py:467`, `Llama3Backend` at `560`, `Qwen3Backend` at `655`, `AnthropicBackend` at `733`. These take a composed `[user_message, *user_media]` sequence with zero signature churn.
- `BACKEND_REGISTRY` at `model_backends.py:752` (register a new `vllm_vision` key here).
- `StepContext.inject_untrusted(content: str)` text-only at `runner.py:119-121`; debug appenders at `agents.py:151-160` and `tasks.py:72-80` are text-only (must log image placeholders, not base64).
- `validate_capabilities` at `validate.py:58`; gates `tools_capable` at `113`, `thinking_capable` at `121`; **no** `vision_capable` exists (must be added).

**Verdict on item 3:** the narrowest change (keyword-only `user_media: Sequence[UserContent] | None = None`, `None` == bit-identical to today) is sound and every insertion point is real.

### (4) olmocr retry-temperature-ladder + parallelism = DO-NOT-PORT

- **Temperature ladder CONFIRMED:** `TEMPERATURE_BY_ATTEMPT = [0.1, 0.1, 0.2, 0.3, 0.5, 0.8, 0.9, 1.0]` at `packages/whisker/research/repos/olmocr/olmocr/pipeline.py:85`; indexed by attempt at **164-165** (`temp_idx = min(attempt, len-1)`; `query["temperature"] = temperature` overrides the `0.0` set in `build_page_query`).
- **build_page_query CONFIRMED:** text-first content parts at **138-141** (text 139, image_url 140), `max_tokens=8000` at 107/144, `temperature: 0.0` "will get overridden later" at 145.
- **Parallel retry race CONFIRMED:** `asyncio.create_task(...)` fan-out + `asyncio.as_completed(tasks)` returning first winner at **343-360** (fired when `vllm_queued_requests == 0`).
- **Global concurrency CONFIRMED:** `max_concurrent_requests_limit = asyncio.BoundedSemaphore(1)` at **88** with comment "Actual value set by args in main()" (CLI default 1600 per baseline `00:18`).

**Verdict on item 4:** correctly flagged DO-NOT-PORT. The ladder violates D5 (never override temperature/seed per call); the `as_completed` race and 1600-wide semaphore violate D11 (one in-flight request). Our path uses fixed `temperature=0, seed=0` (already pinned in `VllmThinkingBackend` at `model_backends.py:310-312,333-335`) + `output_retries`, serial.

### (5) tomd rasterization + PyMuPDF pin

- **PyMuPDF pin CONFIRMED:** `pymupdf~=1.27.0` at `packages/tomd/pyproject.toml:10`. tomd CLAUDE.md restates the workspace-single-version invariant; whisker inherits fitz transitively through `tomd`.
- **`_RASTERISE_DPI = 150` CONFIRMED** at `packages/tomd/src/tomd/lib/pdf/vector_images.py:281`.
- **Render call CONFIRMED but it is NOT a reusable helper.** The `page.get_pixmap(clip=clip, dpi=_RASTERISE_DPI, colorspace=pymupdf.csRGB, alpha=False)` call is **inline** inside the per-cluster loop of `_extract_vector_images` at **1521-1527** (followed by optional `_whiteout_text_in_pixmap` at 1533 and `pix.tobytes("png")` at 1535). It is **clip-scoped to a cluster bbox**, not a full-page renderer, and there is no importable `def rasterize(...)`. See CORRECTION 3.

**Verdict on item 5:** PyMuPDF is pinned and present; tomd is a *pattern reference* for the `get_pixmap` + dpi call, **not** a code-reuse target. Whisker writes its own full-page rasterizer.

---

## 2. Authoritative port map

Per mechanism: **adopt-from-repo** (copy/translate specific code), **write-fresh** (no
adequate prior art), or **extend-ours** (modify an existing in-repo surface). Anchors are
`file:line`. Repo paths are under `packages/whisker/research/repos/`.

### rasterize -> WRITE FRESH (new `packages/whisker/src/whisker/tapetum_llm/vision.py`)

- No importable helper exists to reuse (CORRECTION 3). Write `rasterize_pages(pdf_path, *, longest_dim) -> list[PageRaster]`, library-pure (returns bytes+WxH+page index, no writes).
- **Pattern reference:** tomd inline call `lib/pdf/vector_images.py:1521-1527` (`get_pixmap(dpi=..., colorspace=csRGB, alpha=False)`); use **full-page** `page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)` with `scale = LONGEST_DIM / max(page.rect.width, page.rect.height)` (olmocr longest-side math, `olmocr/pipeline.py:112` via `renderpdf.render_pdf_to_base64png`).
- Pin `LONGEST_DIM` / DPI as a named module constant (candidates: olmocr 1288 px `00:15`; docling scale=2.0 ~144 DPI `25:12`; marker highres 192 DPI `21:16`). Pre-resize client-side is mandatory - vLLM ignores per-request `max_pixels` (`05-web` Q3).
- Acquire `_FITZ_LOCK` (`packages/tomd/src/tomd/lib/pdf/_fitz_lock.py:13-16`) if the process also runs tomd conversion (MuPDF font store is process-global, persona 16).
- PDF source via existing `backend.get_source_path(pid)` (`packages/paperstore/src/paperstore/sqlite_backend.py:1119-1135`).
- **DO NOT PORT:** olmocr poppler subprocess `olmocr/data/renderpdf.py:18-60` (poppler absent on the Windows dev box, persona 16 CRITICAL); pypdfium2 (marker/nougat/docling) - PyMuPDF is already the workspace engine and matches tomd's own extraction raster, minimizing cross-renderer diffs.

### encode -> WRITE FRESH (trivial, in `vision.py`)

- `png = pix.tobytes("png")` (tomd pattern, `vector_images.py:1535`) then wrap as `BinaryContent(data=png, media_type="image/png", identifier=f"page{n}")`.
- **Do not** build a `data:image/png;base64,...` URI ourselves; pydantic-ai emits the OpenAI `image_url` part from `BinaryContent`. The docling encode block (`api_image_request.py:176-190`) is the *reference* for what the wire ends up looking like, not code to copy.

### request-build -> EXTEND OURS + WRITE FRESH backend

- **Extend** the four surfaces (item 3) with keyword-only `user_media: Sequence[UserContent] | None = None`; when `None`, behavior is bit-identical. Backends compose `user_prompt = [user_message, *user_media]` for `agent.run`.
- **Write fresh** `VllmVisionBackend` in `model_backends.py`, registered at `BACKEND_REGISTRY:752` (key `vllm_vision`). Clone the raw-completions branch of `VllmThinkingBackend.run` (`model_backends.py:255-410`) but build OpenAI content-parts (`{"type":"text",...}` + `{"type":"image_url",...}`) at the spot that is text-only today (`288-291`). Text-first part order (matches olmocr `pipeline.py:138-141` and pydantic-ai natural list composition; docling's image-first is equivalent under vLLM).
- **Add** `vision_capable` ClassVar on the new backend + a gate in `validate.py:58` mirroring the `tools_capable` check at `validate.py:113`; add a `vision_capable = true` VLM entry to `SERVICES.toml` (none exists today, baseline `00:73`).
- **DO NOT PORT:** docling's raw `requests`-based HTTP builder (`api_image_request.py`) - it duplicates pydantic-ai + `OpenAIChatModel` and imports docling-core types (CORRECTION 1); its `X-Temperature` header hack (`api_image_request.py:311-313`); MinerU's httpx client; olmocr's direct POST to `{server}/chat/completions`.

### prompt -> WRITE FRESH

- **No surveyed repo has a QA-of-conversion judge prompt.** olmocr `build_no_anchoring_v4_yaml_prompt()` (`prompts/prompts.py:147`, used at `pipeline.py:139`), docling `"Convert this page to docling."` (`vlm_model_specs.py:24`), MinerU `"\nText Recognition:"` (`mineru_client.py`) are all **conversion** prompts. Confirmed across personas 20/21/22/25 (all four "what would change my mind" say no such path exists).
- Write fresh judge prompt: page image + `ctx.inject_untrusted(markdown_slice)` -> structured fidelity verdict. Follow the academic pattern DOCR-Inspector / coarse `extraction_qa.py` (`05-web` Q5). Conceptually mirror marker's "examine image -> analyze extraction -> verdict" step (`marker/processors/llm/llm_table.py:47-64`) but as **judge, not rewriter** (persona 21 CRITICAL).
- Markdown is untrusted; wrap via `ctx.inject_untrusted` (`runner.py:119-121`). Page image is also untrusted but not delimiter-injectable; it rides alongside the wrapped text.

### validate -> EXTEND OURS

- Keep pydantic `output_type` + `ModelRetry` (D6/D10). **Extend** the existing `Adjudication` model (`packages/whisker/src/whisker/tapetum_llm/models.py:72-86`) with page provenance: `page: int` on `AxisFinding`/`EvidenceSpan` and `source: Literal["markdown","page_image"]` on evidence (persona 12 HIGH). Image-only evidence that cannot ground in markdown must not be silently dropped by `ground_spans` (`grounding.py`) - carry a `page_image` source instead of forcing a markdown substring.
- **Adopt (taxonomy only):** docling `VlmStopReason` incl. `CONTENT_FILTERED` (`api_image_request.py:91-98`), but **invert** semantics - raise/fail the paper on `UNSPECIFIED`/`LENGTH`/`CONTENT_FILTERED`, never return empty (fidelity).
- Structured-output strategy: `VllmVisionBackend` starts on schema-in-prompt + `_extract_json` (clone `model_backends.py:285-410`), not pydantic-ai guided decoding, until a live Qwen2.5-VL/olmOCR endpoint proves guided-JSON+vision compose (persona 31 MED; D6 is preserved at the framework boundary because `output_type` still validates).
- **DO NOT PORT:** olmocr `FrontMatterParser` YAML free-text parse (`olmocr/train/front_matter.py`) or its soft `is_valid` flags; docling's free-text-then-string-parse (no `output_type`); marker's silent `{}` on exhaustion (`services/openai.py`) and self-score>=4 accept (`llm_table.py:213-225`).

### aggregate -> EXTEND OURS

- **Reuse** the existing per-chunk fold `aggregate_adjudications` (`packages/whisker/src/whisker/tapetum_llm/chunking.py:226-292`): sorted axis keys, severity-aware worst-axis, min confidence, deduped evidence union. Page order is naturally `0..page_count-1` from fitz.
- Keep the loop **serial** (D11). `StepContext.gather_concurrent` already sorts results by index (`runner.py:133-162`) but must be called with `concurrency=1`, or use a plain serial `for` loop like the existing chunk loop (`adjudicate.py:209-223`).
- **DO NOT PORT:** olmocr `asyncio.TaskGroup` concurrent page dispatch (`pipeline.py:548-554`); its fallback-tolerant doc gate `max_page_error_rate=0.004` + `make_fallback_result` pdftotext substitution (`pipeline.py:329-374,559-567`) - that optimizes corpus yield; whisker fails the paper on any unrasterizable page or VLM error. MinerU concurrent batching (`Semaphore(100)`) and docling `ThreadPoolExecutor(concurrency=4)` (`api_vlm_model.py:185-186`, preset `vlm_model_specs.py:67`) likewise excluded.

### persist -> EXTEND OURS

- Library returns data; **CLI owns persistence** (root CLAUDE.md invariant). Reuse `TapetumResult.to_dict()` (`models.py:118-141`) + existing sidecar writers (`tapetum_llm/cli.py:34-36`). **Add** an optional `page_verdicts: list[dict]` to `to_dict()` for inspect/fusion audit (persona 12), even though `fuse_verdicts` still consumes one folded verdict.
- Fusion layer stays unchanged: `fuse_verdicts` (`tapetum_llm/fusion.py`) is a pure, sorted-fingerprint function; VLM run-to-run variance is isolated to the tapetum sidecar (persona 11 MED).
- **Debug/trace:** extend `render_debug_prompt` (`tasks.py:72-80`) and the `AgentBackend.run` debug append (`agents.py:151-160`) to emit one HTML-comment placeholder per image (`page`, `sha256`, `WxH`, `bytes`, `media_type`), **never** raw base64 (personas 31 LOW, 12 MED).

### Cross-cutting DO-NOT-PORT ledger

olmocr: temperature ladder (`pipeline.py:85,164-165`), `as_completed` parallel retries (`343-360`), 1600 concurrency (`88`, CLI `1224`), poppler subprocess (`data/renderpdf.py`), pdftotext fallback (`233-249,371-374`). marker: `ThreadPoolExecutor`/`max_concurrency=3` (`processors/llm/__init__.py:42-45,163-172`), silent `{}` (`services/openai.py:124-127`), temp bump to 0.2 on retry (`services/gemini.py:62-65`), 96-DPI judge raster (`benchmarks/overall/scorers/llm.py:102`). MinerU: `Semaphore(100)` concurrent batch (`mineru_client.py:666-668`), token-markup parser, hybrid OCR sidecars. docling: raw `requests` builder + docling-core imports (`api_image_request.py:13-20`), fail-silent empty returns (`231,235,258,260`), `X-Temperature` header (`311-313`), `concurrency=4` (`api_vlm_model.py:185-186`).

---

## 3. Corrections to persona claims

**CORRECTION 1 (persona 25, docling-analyst, MED finding).** The claim "No docling-core
import in `api_image_request.py`" is **FALSE**. The file imports `ApiImageRequestResult,
ApiImageStreamingRequestResult, OpenAiApiResponse, OpenAiChatMessage, VlmStopReason` from
`docling.datamodel.base_models` (**lines 13-19**) and `GenerationStopper` from
`docling.models.utils.generation_utils` (**line 20**). Consequence: the file cannot be
copied verbatim into `pipeline`; port the ~40-line core logic and define our own
result/stop-reason types (or map straight onto pydantic-ai). Persona 25's headline
recommendation ("extract ~60 lines core") is still correct - only the "no docling-core
import" evidence sub-claim is wrong.

**CORRECTION 2 (baseline `00:44` and persona 25 line refs).** Baseline cites
"`api_image_request.py:190-199,283-290`" as one image-packaging block. In fact there are
**two builders**: non-streaming `api_image_request` (messages at **192-208**) and
streaming `api_image_request_streaming` (messages at **285-296**). The "283-290" range
lands in the *streaming* variant, not a continuation of the same function. Port target is
the non-streaming builder (165-260); the streaming path is unneeded (we do not stream QA
verdicts). File is **389 LOC**, not 328.

**CORRECTION 3 (persona 16, portability, MED finding).** Persona 16's phrasing "tomd
already rasterises via `page.get_pixmap(..., dpi=_RASTERISE_DPI)` - `vector_images.py:
1522-1535`" implies a reusable helper. Verified: that `get_pixmap` is an **inline,
clip-scoped** call inside the per-cluster loop of `_extract_vector_images` (1521-1527),
not an importable full-page rasterizer. Whisker must **write fresh** (persona 31 got this
right: new `tapetum_llm/vision.py`). tomd is a pattern reference only.

**CORRECTION 4 (persona 31, HIGH finding - minor/non-blocking).** Persona 31 states
`UserContent = str | TextContent | BinaryContent | ImageUrl | ...`. Precisely,
`typing.get_args(UserContent)` = `(str, TextContent, Annotated[ImageUrl | AudioUrl |
DocumentUrl | VideoUrl | BinaryContent | UploadedFile, Discriminator('kind')],
CachePoint)` - `BinaryContent`/`ImageUrl` sit inside a discriminated-union `Annotated`
member, so a naive `BinaryContent in typing.get_args(UserContent)` returns `False`. Usage
is unaffected: `agent.run([text, BinaryContent(...)])` type-checks and is the intended
API. The substantive claim holds.

**No correction** to items 1 (order), 2 (pin/BinaryContent), 3 (change points), 4
(olmocr anti-patterns), or 5 (DPI/pin) beyond the above; all other cited anchors matched.
