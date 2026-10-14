# W5 — OCR / Scanned-PDF Boundary (Block F raw evidence)

Auditv3 raw evidence. No verdicts assigned.

---

## 1. OCR presence in OUR code

Search command (2026-08-03):

```text
rg -ni "\bocr\b|tesseract|surya|paddleocr|easyocr|rapidocr|nougat|olmocr" packages/ --glob "!**/research/repos/**"
```

### 1a. Production conversion path (`packages/tomd/src`, `packages/cli/src`)

**Zero hits** in `packages/tomd/src` and `packages/cli/src` (verified with scoped `rg` on 2026-08-03).

### 1b. Whisker production src (`packages/whisker/src`) — classified hits

| path:line | classification | note |
|---|---|---|
| `packages/whisker/src/whisker/tapetum_llm/transcribe.py:10` | (d) documentation/comment only | `"Sends rasterized page images to an olmOCR-class VLM"`; module docstring states dormant |
| `packages/whisker/src/whisker/tapetum_llm/transcribe.py:14` | (d) | `"Prompt adapted from olmOCR's no-anchor path"` |
| `packages/whisker/src/whisker/tapetum_llm/transcribe.py:19` | (d) | `"NOT ported from olmOCR"` |
| `packages/whisker/src/whisker/tapetum_llm/transcribe.py:53` | (d) | `TRANSCRIPTION_SYSTEM_PROMPT` opens with `"You are a document OCR system..."` — dormant VLM lane only |
| `packages/whisker/src/whisker/tapetum_llm/transcribe.py:25` | (d) | `"Dormant status: this transcriber is used only by the unwired VLM prototype."` |
| `packages/whisker/src/whisker/survey/adapters/marker.py:13` | (b) survey/benchmark adapter | `"Applying required surya patches programmatically"` |
| `packages/whisker/src/whisker/survey/adapters/marker.py:47-49` | (b) | Comment: WG21 papers text-native; OCR sensitivity kept as measurement |
| `packages/whisker/src/whisker/survey/adapters/marker.py:52-54` | (b) | `MODES` includes `"fast-disable-ocr": {"mode": "fast", "disable_ocr": True}` |
| `packages/whisker/src/whisker/survey/adapters/marker.py:96,117,250,331,341,343,368,475,478` | (b) | Surya patch application for Marker competitor install |
| `packages/whisker/src/whisker/survey/runner.py:11` | (b) | `"fast and fast-disable-ocr sensitivity"` |
| `packages/whisker/src/whisker/survey/runtime.py:144-175` | (b) | `SURYA_GGUF_LOCAL_*` env for Marker/Surya GGUF |
| `packages/whisker/src/whisker/survey/locks/marker.lock.json:13-41` | (b) | Pinned `datalab-to/surya-ocr-2-gguf` artifacts and surya patches |
| `packages/whisker/src/whisker/anchors.py:18-19` | (d) | Comment: fuzzy hit-rate for `"OCR/VLM noise"`; `"tomd's deterministic path does not need it"` |
| `packages/whisker/src/whisker/bench.py:25,192` | (d) | Comment references Nougat/Unstructured strata |
| `packages/whisker/src/whisker/constants.py:25,72,82,190-191` | (d) | Comment references Nougat, CE-OCR, olmOCR baseline pattern |
| `packages/whisker/src/whisker/facts.py:17,642,651` | (d) | Comment references olmOCR comprehension/baseline patterns |
| `packages/whisker/src/whisker/tapetum_llm/constants.py:204` | (d) | Comment: olmocr-bench length-relative fuzzy grounding |
| `packages/whisker/src/whisker/tapetum_llm/cli.py:973` | (d) | Comment: pre-flight gate mirrors olmocr/docling |
| `packages/whisker/src/whisker/tapetum_llm/grounding.py:625` | (d) | Comment: olmocr-bench fuzzy |
| `packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md:128` | (d) | Prior-art reference to olmocr-bench coverage gate |
| `packages/whisker/src/whisker/CLAUDE.md:135,338,381,409` | (d) | Documentation references olmOCR, Nougat, CE-OCR |

**No hit in whisker production src implements OCR in the tomd convert path or the deterministic whisker gate.**

### 1c. Benchmark / test hits (representative; not production)

| path:line | classification |
|---|---|
| `packages/whisker/benchmark/tools/marker_worker.py:12,22,95,98` | (b) Marker worker; `--disable-ocr` flag passed to Marker |
| `packages/whisker/benchmark/tools/convert_marker.py:65,132` | (b) `fast-disable-ocr` config |
| `packages/whisker/benchmark/tools/run_campaign_v2.py:53,61` | (b) campaign configs |
| `packages/whisker/tests/test_vlm_lane.py:110,230` | (c) test — asserts `"OCR" in TRANSCRIPTION_SYSTEM_PROMPT`; VisionAgent model `"olmocr"` |
| `packages/whisker/tests/test_survey_registry.py:76,90-91,116,123,125` | (c) test — surya patch registry |
| `packages/whisker/tests/test_survey_install.py:37-40,141-143` | (c) test — fake surya GGUF install |
| `packages/tomd/README.md:99` | (d) limitation statement |
| `packages/tomd/improvements.md:60-678` (multiple lines) | (d) competitor survey / future-work doc |

---

## 2. PDF text extraction path

### 2a. tomd — dual PyMuPDF text-layer extraction (no rasterize-and-recognize)

MuPDF dict path:

```23:29:packages/tomd/src/tomd/lib/pdf/extract.py
def extract_mupdf(page, page_num: int) -> list[Block]:
    """Extract text using MuPDF's built-in block/line/span hierarchy.

    Uses page.get_text("dict"). Returns MuPDF's interpretation of
    paragraphs, lines, and word groupings with font metadata preserved.
    """
    data = page.get_text("dict", flags=0)
```

Spatial rawdict path:

```69:81:packages/tomd/src/tomd/lib/pdf/extract.py
def extract_spatial(page, page_num: int) -> list[Block]:
    """Extract text using raw character coordinates and spatial rules.

    Uses page.get_text("rawdict") for per-character bounding boxes.
    ...
    """
    data = page.get_text("rawdict", flags=0)
```

Document open site:

```1405:1407:packages/tomd/src/tomd/lib/pdf/pipeline.py
    with _FITZ_LOCK:  # see _fitz_lock.py for why this lock is required
        try:
            doc = fitz.open(str(path))
```

**No OCR, tesseract, surya, paddleocr, or rasterize-and-recognize step appears in `packages/tomd/src/tomd/lib/pdf/`.** Rasterization in tomd is limited to figure extraction (`images.py`, opt-in `vector_images.py`) and is not fed to a text recognizer.

Architecture doc:

```55:56:packages/tomd/src/tomd/CLAUDE.md
1. **MuPDF path** - `page.get_text("dict")` for MuPDF's block/line/span grouping
2. **Spatial path** - `page.get_text("rawdict")` with four elif branches keyed on
```

Out-of-scope statement:

```104:105:packages/tomd/src/tomd/CLAUDE.md
- **Scanned-page PDFs** whose body is one image per page trip the 20-image cap and produce image-free markdown. See `improvements.md` §4.
- **No vision LLM.** Alt text comes from the caption-proximity regex only.
```

### 2b. Docling / TableFormer table path — OCR explicitly disabled

```168:171:packages/tomd/src/tomd/lib/pdf/docling_backend.py
        pipeline_opts = PdfPipelineOptions(
            do_table_structure=True,
            do_ocr=False,
        )
```

Docling is optional table-structure enrichment only (`docling_backend.py` module docstring: `"Provides table structure detection via Docling's TableFormer model"`). It does not perform OCR in our integration.

---

## 3. Text-layer guard

### 3a. Constant

```56:59:packages/whisker/src/whisker/tapetum_llm/textlayer.py
MIN_TEXTLAYER_CHARS = 200
"""A whole paper whose text layer totals fewer characters than this is
treated as effectively image-only (scanned / vector-text). The lane
fails loudly instead of judging against near-empty source text."""
```

Related cap (same file):

```49:49:packages/whisker/src/whisker/tapetum_llm/textlayer.py
MAX_TEXTLAYER_PAGES = 150
```

### 3b. Enforcement in `extract_textlayer`

Extraction call:

```141:141:packages/whisker/src/whisker/tapetum_llm/textlayer.py
                pages.append(page.get_text("text", sort=True).strip())
```

Threshold check and behavior (**raises `TextLayerError`**, not warning, not silent pass):

```148:154:packages/whisker/src/whisker/tapetum_llm/textlayer.py
        total_chars = sum(len(p) for p in pages)
        if total_chars < MIN_TEXTLAYER_CHARS:
            raise TextLayerError(
                f"Text layer is effectively empty ({total_chars} chars "
                f"across {page_count} pages); image-only PDF? "
                f"This lane requires an intact text layer: {source_path}"
            )
```

Docstring contract:

```117:120:packages/whisker/src/whisker/tapetum_llm/textlayer.py
        TextLayerError: if the PDF cannot be opened, has zero pages,
            exceeds ``max_pages``, or its total text layer is below
            ``MIN_TEXTLAYER_CHARS`` (image-only PDF).
```

Module-level blind-spot note:

```16:19:packages/whisker/src/whisker/tapetum_llm/textlayer.py
Known blind spot (documented, accepted): where the text layer itself
is broken (scanned pages, math rendered as glyph soup), this lane
cannot see the problem. A paper with an empty text layer fails loudly
rather than producing an empty comparison (fidelity rule).
```

### 3c. Consumers of `MIN_TEXTLAYER_CHARS` / `extract_textlayer`

| Consumer | path:line | behavior on sub-threshold PDF |
|---|---|---|
| `extract_textlayer` | `textlayer.py:149-154` | raises `TextLayerError` |
| `pdf_judge.judge_pdf_extraction` | `pdf_judge.py:620-622` | catches `TextLayerError` → raises `PdfLaneError` |
| Tests | `tests/test_pdf_judge.py:53-56,166-170,173` | import constant; `test_empty_textlayer_raises` |

`pdf_judge.py:620-622`:

```620:622:packages/whisker/src/whisker/tapetum_llm/pdf_judge.py
        pages = extract_textlayer(source_path)
    except TextLayerError as exc:
        raise PdfLaneError(f"{pid}: text-layer extraction failed: {exc}") from exc
```

`extract_page_units` (structured router input) does **not** re-check `MIN_TEXTLAYER_CHARS`; it only checks page count vs `MAX_TEXTLAYER_PAGES` (`textlayer.py:183-187`).

### 3d. tomd readability guard (separate from whisker `MIN_TEXTLAYER_CHARS`)

Constants:

```349:351:packages/tomd/src/tomd/lib/pdf/types.py
_READABLE_MIN_LENGTH = 100
_READABLE_MIN_RATIO = 0.3
_READABLE_MAX_SLASH_RATIO = 0.1
```

```355:371:packages/tomd/src/tomd/lib/pdf/types.py
def is_readable(text: str) -> bool:
    """Return True if text looks like real content rather than encoded garbage.

    Heuristic check that rejects PDFs with very low alphanumeric content,
    such as scanned-image-only PDFs or CID-encoded artifacts that produce
    mostly non-alphanumeric output.
    """
    if not text or len(text.strip()) < _READABLE_MIN_LENGTH:
        return False
    ...
    return (readable / len(non_space)) > _READABLE_MIN_RATIO
```

Pipeline gate:

```1605:1613:packages/tomd/src/tomd/lib/pdf/pipeline.py
    mupdf_text = "\n".join(b.text for b in all_mupdf_blocks)
    if not is_readable(mupdf_text):
        _log.warning("Extracted text is not readable (encrypted/scanned PDF?)")
        return _enforce_skip_contract(
            PipelineResult.for_skip(
                SkipReason.UNREADABLE,
                page_count=result.page_count,
                readable=False,
            )
        )
```

CLI surfacing (**fail loud**, not silent green):

```482:486:packages/tomd/src/tomd/api.py
    if r.skipped:
        raise RuntimeError(
            f"tomd produced empty markdown for {paper_id} "
            f"({r.skip_reason.value if r.skip_reason else 'slide deck, standards draft, or unreadable source'})."
        )
```

```456:461:packages/cli/src/cli/process.py
    if result.skipped:
        # The convert stage cannot make this paper into markdown.
        # Raise so process_paper records the failure and does not
        # advance status past download. ``skip_reason`` distinguishes
        # this from a genuine conversion error.
        raise RuntimeError(f"convert skipped ({result.skip_reason})")
```

Skip reason enum:

```25:31:packages/tomd/src/tomd/lib/pdf/types.py
class SkipReason(StrEnum):
    ...
    UNREADABLE = "unreadable"
```

**No `textlayer.py` equivalent exists under `packages/tomd/src`.**

---

## 4. Dormant VLM lane

### 4a. Line counts (physical lines, 2026-08-03)

| File | Lines |
|---|---|
| `packages/whisker/src/whisker/tapetum_llm/vision.py` | 126 |
| `packages/whisker/src/whisker/tapetum_llm/vision_task.py` | 211 |
| `packages/whisker/src/whisker/tapetum_llm/vlm_diff.py` | 221 |
| `packages/whisker/src/whisker/tapetum_llm/vlm_pipeline.py` | 100 |
| **Total (four files)** | **658** |

Related dormant module (imported by `vlm_pipeline.py`, not in user's four-file list): `transcribe.py` — 154 physical lines.

### 4b. Dormancy declarations (verbatim)

`vision.py:15-16`:

```15:16:packages/whisker/src/whisker/tapetum_llm/vision.py
Dormant status: this rasterizer is used only by the unwired VLM prototype.
It is retained as tested prior art and is not production coverage.
```

`vision_task.py:23-26`:

```23:26:packages/whisker/src/whisker/tapetum_llm/vision_task.py
The VLM lane is dormant (no vision endpoint deployed). This module keeps
it functional for the day a vision pod exists, without any footprint in
the pipeline package. No production CLI or service configuration invokes
it, so it must not be reported as production coverage.
```

`vlm_diff.py:21-22`:

```21:22:packages/whisker/src/whisker/tapetum_llm/vlm_diff.py
Dormant status: this prototype is reachable only from the unwired VLM entry
point. It is retained as tested prior art and is not production coverage.
```

`vlm_pipeline.py:14-15`:

```14:15:packages/whisker/src/whisker/tapetum_llm/vlm_pipeline.py
Dormant status: no production CLI or service configuration invokes this
prototype. It is retained as tested prior art and is not production coverage.
```

`pdf_judge.py:10-18` (production PDF lane is text-only replacement):

```10:18:packages/whisker/src/whisker/tapetum_llm/pdf_judge.py
The text-only replacement for the dormant VLM lane. PyMuPDF extracts
the PDF's embedded text layer (an extraction path independent of tomd),
...
Unlike the VLM lane (pixels only, deterministic diff afterwards), the
judge here sees both sides at once. That is a deliberate, user-approved
trade: no vision endpoint exists, and the runtime simulation showed
```

Whisker CLAUDE.md:

```106:107:packages/whisker/src/whisker/CLAUDE.md
owns terminal readback output and explicit `<pid>.readback.md` files. The VLM
modules have no production command or report path and remain dormant.
```

### 4c. Import-chain reachability proof

**Repo-wide import of VLM modules** (2026-08-03 `rg`):

```
packages/whisker/src/whisker/tapetum_llm/vlm_pipeline.py  → vision, vision_task, transcribe, vlm_diff
packages/whisker/src/whisker/tapetum_llm/vlm_diff.py      → transcribe
packages/whisker/src/whisker/tapetum_llm/transcribe.py    → vision_task
packages/whisker/tests/test_vlm_lane.py                   → vision, transcribe, vlm_diff, vision_task
```

**No import of `vlm_pipeline`, `vlm_adjudicate_paper`, `vision`, `transcribe`, or `vlm_diff` from:**

- `packages/whisker/src/whisker/__main__.py` — **zero matches** for `vlm|vision|transcribe|rasterize`
- `packages/whisker/src/whisker/menu.py` — **zero matches**
- `packages/whisker/src/whisker/tapetum_llm/cli.py` — imports `pdf_judge`, `adjudicate_paper`; **no** `vlm_*` / `vision` / `transcribe` imports (grep of import block, lines 35-80)

`tapetum_llm/__init__.py:30-44` re-exports adjudication/models/table_compare only; **no** VLM symbols.

### 4d. Guards keeping pipeline text-only

`tests/test_vlm_lane.py:215-224`:

```215:224:packages/whisker/tests/test_vlm_lane.py
    def test_pipeline_stays_text_only(self):
        """Pipeline signatures carry no vision parameters."""
        import inspect
        from pipeline.agents import AgentBackend
        from pipeline.model_backends import BACKEND_REGISTRY, ModelBackend
        from pipeline.tasks import run_task
        assert "user_media" not in inspect.signature(ModelBackend.run).parameters
        assert "user_media" not in inspect.signature(AgentBackend.run).parameters
        assert "user_media" not in inspect.signature(run_task).parameters
        assert "vllm_vision" not in BACKEND_REGISTRY
```

VLM dispatch is whisker-local only (`vision_task.py:8-11`):

```8:11:packages/whisker/src/whisker/tapetum_llm/vision_task.py
"""Whisker-local multimodal LLM dispatch for the dormant VLM lane.

The pipeline framework is text-only by design and, per project decision,
stays unmodified by whisker: everything vision-specific lives HERE, inside
```

---

## 5. Documented reasoning for having no OCR

### 5a. `packages/whisker/research/Audit/Auditv1/p27-case-docling.md`

Docling studied as **release-engineering exemplar**, not OCR adoption. OCR mentioned only as evaluation modality context:

- `p27-case-docling.md:93`: `"separate strict/fuzzy tolerances for OCR vs programmatic PDF paths"`
- `p27-case-docling.md:292`: `"Docling's AI pipeline (layout, TableFormer, optional VLM) is inherently nondeterministic across hardware/backends"`

No Docling OCR-on vs OCR-off benchmark numbers in this file.

### 5b. `packages/whisker/research/Audit/Auditv1/p28-case-olmocr-marker-mineru.md`

**olmOCR**

- Uses OCR/VLM: `"olmOCR-Bench: 7,010 tests across 1,402 PDFs"` with categories including `"old scans"` and `"historical scans"` (`p28:54`).
- Downstream eval: `"+1.3 pp average"` on LM tasks (`p28:36`).
- Baseline checks: non-empty alphanumeric, repetition `"> 30 characters"`, charset rules (`p28:106`).
- **Benchmark numbers (Overall, from olmOCR paper Table 4, quoted in p28:185):** olmOCR v0.1.75 **75.5 ± 1.0** > Marker v1.7.5 **70.1 ± 1.1** > MinerU v1.3.10 **61.5 ± 1.1**.
- `"Neither Marker nor MinerU documents an equivalent zero-authoring universal baseline gate"` (`p28:115`).

**Marker**

- OCR via Surya in balanced/fast modes; `--disable-ocr` for text-layer-only (`p28:127-128` serving section references Marker README).
- Throughput: `"23.7 pg/s"` fast-no-OCR cited in steelman doc (see §5d), not in p28 body.
- LLM-as-judge advisory only per p28:235.

**MinerU**

- Reference-matching OmniDocBench eval; `"does not adopt olmOCR-style fact unit tests"` (`p28:63`).
- Headers/footers category: `"MinerU leads headers/footers exclusion at 96.6 vs Marker's 84.9"` (`p28:185`).

**Nougat** — not primary subject of p28 (see p29).

**Surya** — referenced only as Marker's OCR engine in p28 serving context (`p28:127`).

### 5c. `packages/whisker/research/Audit/Auditv1/p29-case-unstructured-nougat-surya.md`

**Nougat**

- `"Neural Optical Understanding for Academic Documents"` — OCR-by-design (`p29:109`).
- Per-modality metrics with limitation prose (`p29:93-127`).
- No OCR-on/off toggle documented; generative image-to-markdown model.

**Surya**

- OCR/layout predictors; dual license code Apache + OpenRAIL-M weights (`p29:181-197`).
- External benchmark on olmOCR-bench with reproducibility steps (`p29:201-217`).
- No explicit OCR-off mode in p29.

**Unstructured**

- Partition API; not an OCR engine (`p29:27-65`).
- `"core unstructured and unstructured-api repos remain Apache-2.0"` (`p29:87`).

### 5d. `packages/whisker/research/marker-v2/50-steelman-decision.md`

Scanned-PDF gap in tomd:

```27:27:packages/whisker/research/marker-v2/50-steelman-decision.md
7. **Scanned / image-heavy PDFs are an admitted tomd gap.** tomd CLAUDE.md: scanned-page PDFs trip the 20-image cap and produce image-free markdown (`improvements.md` §4 cited in CLAUDE). Marker balanced's job is exactly that gap (old scans categories on the bench).
```

Marker OCR modes and bench:

```17:17:packages/whisker/research/marker-v2/50-steelman-decision.md
2. **Throughput that matters at corpus scale.** On one B200, Marker balanced sustains **2.9 pg/s** vs MinerU pipeline **0.54 pg/s** (~**5×**), fast **7.4 pg/s**, fast-no-OCR **23.7 pg/s**. Evidence: `README.md` Benchmarks / Throughput (~450–517).
```

```41:41:packages/whisker/research/marker-v2/50-steelman-decision.md
3. **Determinism / Lane-1 golden contract.** ... Marker balanced/fast OCR routes through a Surya VLM server ... unless permanently pinned to `--disable_ocr` — which scores **43.6%** overall / **0.0** arXiv math (`README.md:462, 488–496`), i.e. you paid for Marker and threw away its quality.
```

```63:63:packages/whisker/research/marker-v2/50-steelman-decision.md
- [HIGH] **VLM path conflicts with convert determinism and Lane-1 goldens; disable_ocr path conflicts with quality claims.** Evidence: `models.py` SuryaInferenceManager; bench overall 76.0 vs 43.6 no-OCR; whisker `CLAUDE.md` Lane 1 + determinism. Impact: no Marker mode simultaneously satisfies (stable goldens) and (76% quality).
```

Verdict line:

```107:107:packages/whisker/research/marker-v2/50-steelman-decision.md
**adopt-component**
```

```113:114:packages/whisker/research/marker-v2/50-steelman-decision.md
1. **Study/port** Marker's deterministic `table_recon` ideas into tomd's table path (Apache-2.0 code, no weights).
2. **Optional research/oracle only:** wire Marker behind an explicit non-default whisker `REFERENCE_ENGINES` entry ... prefer `--disable_ocr` or document OpenRAIL acceptance for research weights.
```

Marker balanced bench (from steelman):

```15:15:packages/whisker/research/marker-v2/50-steelman-decision.md
1. **Measured quality on a third-party bench tomd does not claim.** Marker balanced scores **76.0%** overall / **83.5%** born-digital on olmOCR-bench (1,403 PDFs; math, tables, multi-column, scans).
```

### 5e. `packages/whisker/research/redteam/marker.md`

Single OCR-related row:

```244:244:packages/whisker/research/redteam/marker.md
| OCR-garble / unicode regression | `test_garbled_pdf.py:25`, `test_table_processor.py:29` | None at guard layer | [MEDIUM] — corpus fixtures |
```

### 5f. `packages/whisker/src/whisker/CLAUDE.md`

```633:634:packages/whisker/src/whisker/CLAUDE.md
- **Two lanes by source kind.** PDF papers go through the PDF-text-layer judge
  (`pdf_judge.py`): PyMuPDF extracts the raw text layer, the judge model
```

```885:886:packages/whisker/src/whisker/CLAUDE.md
4. **VLM lane is unwired.** 788 LOC across 5 files (`tapetum_llm/vlm_*.py`,
   `vision_task.py`) never reached integration. Decision pending: delete vs.
```

```944:944:packages/whisker/src/whisker/CLAUDE.md
    raster extraction, pixel inspection, VLM coverage, and image fidelity are
    outside the audit scope and are not missing scoring requirements.
```

### 5g. `packages/tomd/src/tomd/CLAUDE.md`

```104:105:packages/tomd/src/tomd/CLAUDE.md
- **Scanned-page PDFs** whose body is one image per page trip the 20-image cap and produce image-free markdown. See `improvements.md` §4.
- **No vision LLM.** Alt text comes from the caption-proximity regex only.
```

### 5h. Competitor OCR summary table (from cited research only)

| Competitor | Uses OCR? | Optional or default? | Benchmark OCR-on vs OCR-off (our research) |
|---|---|---|---|
| **Docling** | Capable; **our integration sets `do_ocr=False`** | Optional in Docling; **off in tomd** | Not recorded in p27 |
| **Marker** | Yes (Surya VLM OCR) | Default on balanced/fast; **`--disable-ocr` / `fast-disable-ocr`** | **76.0% overall (OCR on)** vs **43.6% overall (disable_ocr)** per steelman citing Marker README (`50-steelman-decision.md:41,63`) |
| **olmOCR** | Yes (VLM page transcription) | OCR is the product | olmOCR-Bench **75.5 ± 1.0** overall vs Marker **70.1 ± 1.1** vs MinerU **61.5 ± 1.1** (`p28:185`) |
| **MinerU** | VLM pipeline | Default VLM path | Category scores only in p28; no OCR-off row |
| **Nougat** | Yes (generative OCR) | Always image-to-MD | Per-modality edit distance/BLEU in p29; no on/off |
| **Surya** | Yes (OCR 2) | Used inside Marker; standalone predictors | External olmOCR-bench strata in p29; no on/off in our docs |
| **Unstructured** | Partition/OCR via optional deps | Format-dependent | Not OCR-focused in p29 |

---

## 6. Contract truthfulness (scan / raster claims in whisker + tomd `*.md` under `src/`)

Search: `rg -ni "scan|scanned|image-only|raster" packages/whisker packages/tomd --glob "*.md"` (scoped to `src/` for capability/limitation claims).

| path:line | quote (abbreviated) | classification |
|---|---|---|
| `packages/tomd/src/tomd/CLAUDE.md:104` | `"Scanned-page PDFs whose body is one image per page trip the 20-image cap and produce image-free markdown"` | **limitation statement** |
| `packages/tomd/src/tomd/CLAUDE.md:105` | `"No vision LLM."` | **limitation statement** |
| `packages/tomd/src/tomd/CLAUDE.md:18,69,81-87` | raster glyph / vector figure extraction mechanics | **unrelated** (embedded raster handling, not scan OCR) |
| `packages/tomd/src/tomd/lib/pdf/ARCHITECTURE.md:118,164` | scanned-page rasters; rejects encrypted/scanned via `is_readable` | **limitation statement** |
| `packages/tomd/src/tomd/PDF_ARCH.md:161` | `"Detect scanned or garbage extraction early"` | **limitation statement** |
| `packages/whisker/src/whisker/CLAUDE.md:944` | `"raster extraction, pixel inspection, VLM coverage, and image fidelity are outside the audit scope"` | **limitation statement** |
| `packages/whisker/src/whisker/CLAUDE.md:345` | `"pipe-table scanners"` | **unrelated** (string search, not document scanning) |
| `packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md:205` | sub-threshold raster glyph placeholder | **unrelated** |
| `packages/whisker/src/whisker/branding/assets/LAYOUT-PATTERN.md:83` | vector vs raster in CSS | **unrelated** |

Package-level limitation (not under `src/` but cited in task):

```99:99:packages/tomd/README.md
- **No OCR.** Scanned or image-only PDFs are not supported.
```

**No capability claim found in whisker/tomd src markdown stating that scanned or image-only PDFs are supported for conversion.**

---

## 7. Corpus reality

### 7a. `packages/whisker/corpus/`

Glob `packages/whisker/corpus/**/*.pdf` → **0 PDF files**.

Corpus holds markdown/facts artifacts only (e.g. `P4182R0.expected.md`, `*.facts.jsonl`, `holdout/*.anchors.jsonl`). **No scanned/image-only PDF present in-repo to classify.**

### 7b. `WG21_DATA_DIR` workspace

Environment (2026-08-03): `WG21_DATA_DIR=C:\Users\sabo2\Desktop\cppalliance\data`

PDF sources: `data/paperstore/*.pdf` → **189 files** (counted via `Get-ChildItem`).

### 7c. Text-layer character distribution (PyMuPDF)

Script: sum of `page.get_text("text", sort=True)` lengths per PDF across all 189 workspace PDFs. `$env:PYTHONIOENCODING="utf-8"`.

| Statistic | Value |
|---|---|
| Count | 189 |
| Min | 2,121 chars |
| Median | 21,478 chars |
| Max | 9,550,976 chars |
| Files under 1,000 chars | **0** |
| Files under `MIN_TEXTLAYER_CHARS` (200) | **0** |

**No in-workspace PDF qualifies as image-only by the whisker 200-char text-layer threshold.** This does not prove absence of scanned PDFs in the broader WG21 mailing; only that the staged 189-PDF workspace sample is text-layer-rich.
