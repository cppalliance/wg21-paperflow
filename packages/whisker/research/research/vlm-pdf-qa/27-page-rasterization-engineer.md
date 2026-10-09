# 27 - page-rasterization-engineer

**Verdict:** usable-with-conditions (+ PyMuPDF full-page rasterization is the correct reuse path, but default olmocr 1288px longest-side misses the 2px/stroke legibility floor for 9–10pt WG21 body/inline code; use 1684px longest-side / ~144 DPI unless token budget forces a downgrade)
**Confidence:** high

## Findings

- [CRITICAL] **Surveyed-repo rasterization parameters (library / effective DPI / size cap).**

  | Repo | Library | Effective DPI / scale | Size cap | Packaging | Evidence |
  |------|---------|----------------------|----------|-------------|----------|
  | **olmocr** | poppler `pdftoppm` subprocess | `dpi = target_longest_image_dim * 72 / longest_pt_side` (longest side → exactly `target_longest_image_dim` px); no post-resize | Default `target_longest_image_dim=1288` (`pipeline.py:1229`); function default `2048` (`renderpdf.py:39`); WEBP wrapper default `1024` (`renderpdf.py:62-63`) | base64 PNG (`renderpdf.py:60`) | `olmocr/olmocr/data/renderpdf.py:39-60`, `olmocr/olmocr/pipeline.py:1229` |
  | **marker** | pypdfium2 `page.render(scale=dpi/72)` | Layout `lowres_image_dpi=96`; OCR/LLM blocks `highres_image_dpi=192` (`document.py:18-25`) | None at page level; LLM crops use `image_expansion_ratio=0.01` (`processors/llm/__init__.py:46-48,69-78`) | WEBP base64 default (`services/__init__.py:22-25`) | `marker/marker/builders/document.py:18-25,41-42`, `marker/marker/providers/pdf.py:411-415`, `marker/marker/services/__init__.py:22` |
  | **docling** | pypdfium2 via `get_page_image` | VLM specs `scale=2.0` → ~144 DPI (`2.0 * 72`); backend renders at `scale*1.5` then resizes to `scale` for sharpness (`docling_parse_backend.py:225-234`) | `max_size` optional on `BaseVlmOptions`, default `None` (`pipeline_options_vlm_model.py:58-67`); page `get_image` clamps scale when `max_size` set (`base_models.py:468-470`) | base64 PNG in API path (`api_image_request.py:190-199`) | `docling/docling/datamodel/vlm_model_specs.py:34,50,65`, `docling/docling/backend/docling_parse_backend.py:225-234`, `docling/docling/datamodel/pipeline_options_vlm_model.py:48-67`, `docling/docling/utils/api_image_request.py:190-199` |
  | **nougat** | pypdfium2 `PdfBitmap.to_pil` | `scale=dpi/72`, default `dpi=96` (`rasterize.py:21,49`) | None | BMP in-memory / PNG on disk (`rasterize.py:54-57`) | `nougat/nougat/dataset/rasterize.py:18-49,69` |
  | **MinerU** | pypdfium2 `page.render(scale=scale)` | Default `dpi=200` → `scale=200/72` (`pdf_image_tools.py:35`; `pdf_reader.py:17`); if `long_side*scale > 3500` rescale to fit (`pdf_reader.py:14,20-21`) | `max_width_or_height=3500` px longest side (`pdf_reader.py:14`) | JPEG base64 default (`pdf_reader.py:39,49-52`) | `MinerU/mineru/utils/pdf_reader.py:11-33`, `MinerU/mineru/utils/pdf_image_tools.py:35,50-65,419-439` |

  Impact: Hot paths cluster around **longest-side pixel caps** (olmocr 1288) or **144–200 DPI** (docling 2.0×, MinerU 200). None use PyMuPDF; all are portable patterns we can mirror with `fitz`.

- [HIGH] **Qwen-VL token math for A4 (8.27×11.69 in = 595.44×841.68 pt; longest pt side = 841.68).** Step-by-step (runtime `uv run --package tomd python`, 2026-07-07):

  1. **DPI from longest-side target:** `dpi = target_longest × 72 / 841.68`.
     - `target_longest=1288` → `dpi=110.18` → raw `911×1288` px (longest=1288).
     - `target_longest=1684` (144 DPI equivalent) → `dpi=144.00` → raw `1191×1683` px.
  2. **Qwen2.5-VL visual tokens** (28×28 patch grid per `05-web.md:54-55`; smart_resize replicated from `docling/utils/vlm_utils.py:26-75`):
     - `1288` longest → Qwen-sized `924×1288` → **1518 visual tokens** (`(1288/28)×(924/28)=46×33`).
     - `1684` longest → Qwen-sized (pre-cap) → **2580 visual tokens** (`(1683/28)×(1191/28)=60×42` before `max_pixels` clamp at higher DPI).
  3. **Qwen3-VL naive grid** (32×32 patches per `05-web.md:54-55`): `1288` longest → **1189 tokens** (`ceil(1288/32)×ceil(911/32)=41×29`); pixel count `1,173,368` sits inside recommended band `256×32²=262,144` … `1280×32²=1,310,720` (`05-web.md:55`).
  4. **olmocr default (1288)** lands near the **upper end** of the 256–1280 visual-token recommendation for Qwen3-VL, but **exceeds** it for Qwen2.5-VL (1518 tokens).

  Impact: Matching olmocr's 1288px cap is token-economical for Qwen3-VL but overshoots Qwen2.5-VL's recommended band; server `--mm-processor-kwargs` must be set accordingly (`05-web.md:46-49,52-55`).

- [HIGH] **9–10pt body text / inline code legibility (≥2 px per 1 pt stroke).** Rule: 1 pt PDF stroke → `stroke_px = dpi/72`; need `dpi ≥ 144`.
  - At olmocr default (`dpi=110.18`): `stroke_px=1.53`, `10pt` body height `=15.3 px` — **below** 2 px/stroke.
  - At docling `scale=2.0` (`dpi=144`): `stroke_px=2.00`, `10pt` height `=20.0 px` — **meets** threshold.
  - At marker highres (`dpi=192`): `stroke_px=2.67` — comfortable margin.

  Impact: For **conversion-fidelity QA** (spot missing inline code, thin rules, ins/del strokes), **1288px longest-side is insufficient**; **144 DPI / ~1684px longest on A4** is the minimum justified by the stroke rule.

- [HIGH] **PyMuPDF: `Matrix(z,z)` vs `dpi=` param.** Runtime on `data/paperstore/n5036.pdf` page 0 (`rect=595.3×841.9 pt`), `target_longest=1288`:
  - `z = 1288 / 841.9 = 1.5299`; `page.get_pixmap(matrix=fitz.Matrix(z,z), colorspace=fitz.csRGB, alpha=False)` → **911×1288**.
  - `page.get_pixmap(dpi=int(round(110.15)), ...)` → **910×1287** (1 px drift).
  - **Prefer float `Matrix(z,z)`** with `z = target_longest / max(page.rect.width, page.rect.height)` to mirror olmocr's longest-side invariant exactly (`renderpdf.py:40-52`).

  Impact: Integer `dpi=` rounding can desync client pre-resize from vLLM processor expectations (`05-web.md:52-53`: per-request pixel limits ineffective under vLLM).

- [MED] **Encoding tradeoffs for base64 payloads (n5036 page 0, 911×1288 RGB).** Runtime bytes:
  - PNG: **37,818** B → base64 **50,424** B.
  - JPEG q85: **39,462** B; q95: **49,990** B.
  - WEBP: **not supported** by PyMuPDF `Pixmap.tobytes` (error lists only png/jpeg/…).
  - WG21 text page: **PNG beats JPEG** on size (counter-intuitive but measured).

  Impact: Use **PNG** for OpenAI `data:image/png;base64` compatibility (`05-web.md:43-44`, `docling/utils/api_image_request.py:197-199`). WEBP (marker pattern) needs a Pillow post-step; skip unless bandwidth dominates.

- [MED] **Determinism and memory.**
  - Same-run: two `pix.tobytes('png')` calls → **identical SHA-256** (deterministic on Windows/PyMuPDF 1.27.2.3).
  - Cross-platform: PNG zlib/MuPDF build may differ — treat byte-identical output as **best-effort**, not guaranteed.
  - `n5036.pdf` (13 pages) at `target_longest=1288`: **45.8 MB** peak uncompressed RGB (`911×1288×3×13`); **0.92 MB** PNG total on disk. Per-page peak ~3.5 MB pixmap — safe for WG21 single-digit/low-teens page counts (`00-baseline.md:81`).

  Impact: Rasterize **one page at a time**, drop pixmap before next page; no need to hold 13 pixmaps concurrently.

- [MED] **tomd existing pixmap usage — extend, don't replace.** Only production `get_pixmap` call site: `packages/tomd/src/tomd/lib/pdf/vector_images.py`:
  - `_RASTERISE_DPI = 150` with rationale at `:278-281` (~2× on-page density for figure preview).
  - Render: `page.get_pixmap(clip=clip, dpi=_RASTERISE_DPI, colorspace=pymupdf.csRGB, alpha=False)` at `:1522-1527`; encode `pix.tobytes("png")` at `:1535`.
  - Coordinate helper `_pdf_pt_to_pixel_irect(..., dpi)` at `:540-557` (`sx = dpi/72.0`).
  - **No full-page render helper exists.** `images.py:extract_page_images` pulls embedded xrefs, not page bitmaps.

  Impact: **Adapt > extend:** add a full-page helper beside `vector_images.py` (shared `csRGB`, `alpha=False`, PNG `tobytes`, float zoom math) rather than a parallel rasterizer or new dependency.

- [LOW] **Recommended parameters for whisker VLM QA lane (WG21 PDF fidelity judging).**

  | Parameter | Value | Justification |
  |-----------|-------|---------------|
  | Zoom | `z = 1684 / max(page.rect.width, page.rect.height)` | 144 DPI on A4 longest side (841.68 pt → 1683 px); meets ≥2 px/pt stroke for 9–10pt body/code |
  | Fallback (token-starved) | `z = 1288 / max(...)` | olmocr production default (`pipeline.py:1229`); ~1518 Qwen2.5-VL tokens; accept 1.53 px/stroke |
  | Hard cap | `target_longest ≤ 2048` | olmocr training/scripts ceiling (`renderpdf.py:39`, `scripts/pii/*:297`); no WG21 page hits it |
  | Colorspace | `fitz.csRGB`, `alpha=False` | Matches `vector_images.py:1525-1526`; ins/del color QA needs RGB |
  | Grayscale | **No** | WG21 wording uses green/red (`tomd/CLAUDE.md:83` region) |
  | Format | **PNG** → `data:image/png;base64,...` | vLLM/OpenAI compat (`05-web.md:43-44`); smaller than JPEG on text pages (runtime); deterministic |
  | Resize locus | **Client pre-resize** | vLLM ignores per-request `min_pixels`/`max_pixels` (`05-web.md:52-53`) |
  | Memory pattern | One page → pixmap → base64 → release | 13-page doc ≈ 0.9 MB PNG total, ~3.5 MB peak pixmap |

  Implementation sketch (extend `vector_images.py` constants module):
  ```python
  _VLM_PAGE_TARGET_LONGEST_PX = 1684  # 144 DPI on A4; stroke_px = dpi/72 >= 2
  z = _VLM_PAGE_TARGET_LONGEST_PX / max(page.rect.width, page.rect.height)
  pix = page.get_pixmap(matrix=fitz.Matrix(z, z), colorspace=fitz.csRGB, alpha=False)
  b64 = base64.b64encode(pix.tobytes("png")).decode("ascii")
  ```

  Impact: Balances **docling/MinerU DPI class (144–200)** with **olmocr longest-side cap pattern**, on already-shipped PyMuPDF (`00-baseline.md:75-76,84`).

## False-pass hypothesis

VLM QA at olmocr-default **1288px** (`dpi≈110`) on a WG21 page with dense **9pt monospace inline code** (`tomd` CODE sections): 1 pt strokes rasterize to **1.53 px**, the model reads smeared glyphs as matching the markdown, and fusion accepts a **false pass** on a dropped/backslash-wrong code token that 144 DPI would show clearly.

## False-fail hypothesis

At **1684px** longest-side on a 13-page paper, Qwen2.5-VL encodes **~2580 visual tokens/page**; with markdown text in the same context, total context blows past a conservatively configured vLLM `--max-model-len`, the server truncates or OOMs (`05-web.md:34-35`), the lane errors out, and fusion treats the LLM lane as failed → **false fail** (deterministic lane only) even though conversion is fine.

## What would change my mind

A/B raster study on 20+ WG21 papers showing **no measurable adjudication delta** between 1288px and 1684px longest-side (same VLM, same prompts) would justify collapsing to olmocr-default 1288 for token savings.
