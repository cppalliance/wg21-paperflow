# Garbage-text and base64 handling in ML PDF-to-Markdown pipelines

Research across five local clones: `marker`, `MinerU`, `nougat`, `olmocr`, `Dolphin`.

**Scope note:** These are image/VLM pipelines. None implement a dedicated "strip embedded PDF data-stream blobs from markdown" filter. Their defenses target (a) bad native PDF text before OCR/VLM, (b) model repetition/hallucination in generated output, or (c) document-level quality gates. Deliberate base64 encoding of page images for model prompts is universal and is **not** garbage filtering.

---

## 1. nougat

### 1.1 During-generation repetition detection (pre-output, tied to decode)

`StoppingCriteriaScores` monitors variance of per-step max logit scores; low variance triggers early stop, a classic repetition/hallucination signal:

```442:474:nougat/nougat/model.py
class StoppingCriteriaScores(StoppingCriteria):
    def __init__(self, threshold: float = 0.015, window_size: int = 200):
        ...
    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor):
        ...
        if varvar[b] < self.threshold:
            ...
        return all(self.stopped.values()) and len(self.stopped) > 0
```

Post-decode, token-level variance subdivisions mark repetition indices; generation is padded/truncated and pages can be flagged:

```618:647:nougat/nougat/model.py
            varvar = np.array([np.var(v) for v in subdiv(var[::-1])][::-1])
            ...
            small_var = np.where(varvar < 0.045)[0]
            if early_stopping and len(small_var) > 1:
                ...
                    logging.warn("Found repetitions in sample %i" % b)
                    output["repeats"].append(idx)
```

### 1.2 Page-level failure placeholders (post-model, CLI)

When repetition is detected at inference time, the page is replaced with a sentinel instead of emitting garbage:

```181:185:nougat/predict.py
            elif args.skipping and model_output["repeats"][j] is not None:
                if model_output["repeats"][j] > 0:
                    logging.warning(f"Skipping page {page_num} due to repetitions.")
                    predictions.append(f"\n\n[MISSING_PAGE_FAIL:{page_num}]\n\n")
```

### 1.3 Post-generation cleanup (post-model)

**Tail repetition truncation** (suffix loop detection, min length 30):

```102:115:nougat/nougat/postprocessing.py
def truncate_repetitions(s: str, min_len=30):
    """
    Attempt to truncate repeating segments in the input string.
    ...
    """
```

**Hallucinated reference block removal** via fuzzy duplicate-line clustering (`rapidfuzz`, line-length caps):

```301:323:nougat/nougat/postprocessing.py
def remove_hallucinated_references(text: str) -> str:
    ...
    for to_delete in reversed(to_delete):
        text = text.replace(to_delete, "\n\n[MISSING_PAGE_POST]\n\n")
```

**Absurd table line removal** (per-line structural counts):

```451:457:nougat/nougat/postprocessing.py
    for l in generation.split("\n"):
        if (
            l.count("\\begin{tabular}") > 15
            or l.count("\\multicolumn") > 60
            or l.count("&") > 400
        ):
            generation = generation.replace(l, "")
```

### 1.4 No input garbage / base64 blob handling

Nougat consumes page **images**, not extracted PDF text streams. No entropy, printable-ratio, or base64-garbage filters on text input. Postprocessing runs on model output only (`postprocess_single` at `nougat/nougat/postprocessing.py:332`).

---

## 2. marker

### 2.1 Heuristic bad-OCR detection on native PDF text (pre-model)

Ratio thresholds on spaces, newlines, alphanumerics, and replacement characters; comment explicitly names garbled text:

```379:399:marker/marker/providers/pdf.py
    def detect_bad_ocr(self, text):
        ...
        if alphanum_ratio(text) < self.ocr_alphanum_threshold:  # Garbled text
            return True
        invalid_chars = len([c for c in text if c in self.ocr_invalid_chars])
        if invalid_chars > max(6.0, len(text) * 0.03):
            return True
```

Supporting ratio helper (stdlib only):

```1:10:marker/marker/providers/utils.py
def alphanum_ratio(text):
    ...
    ratio = alphanumeric_count / len(text)
    return ratio
```

Bad text causes `check_line_spans` to reject provider lines, forcing layout/OCR path:

```317:318:marker/marker/providers/pdf.py
        if self.detect_bad_ocr(text):
            return False
```

### 2.2 ML OCR-error page classifier (pre-model)

Surya `OCRErrorPredictor` labels each page's extracted text good/bad; bad pages trigger detection+OCR:

```234:249:marker/marker/builders/line.py
    def ocr_error_detection(
        self, pages: List[PageGroup], provider_page_lines: ProviderPageLines
    ):
        ...
        ocr_error_detection_results = self.ocr_error_model(
            page_texts, batch_size=int(self.get_ocr_error_batch_size())
        )
```

```152:152:marker/marker/builders/line.py
            document_page.ocr_errors_detected = ocr_error_detection_label == "bad"
```

### 2.3 Page skip heuristics for untrusted embedded text (pre-model)

Invisible OCR layers, glyphless fonts, and full-page images trigger page rejection:

```338:375:marker/marker/providers/pdf.py
        if self.strip_existing_ocr:
            ...
                if pdfium_c.FPDFTextObj_GetTextRenderMode(text_obj) in [
                    pdfium_c.FPDF_TEXTRENDERMODE_INVISIBLE,
                    ...
                ]:
                    return False
            ...
            if page_bbox.intersection_pct(img_bbox) >= self.image_threshold:
                return False
```

### 2.4 Blank-line and blank-page filters (pre-model)

```329:342:marker/marker/builders/line.py
    def filter_blank_lines(self, page: PageGroup, lines: List[ProviderOutput]):
        ...
            if not is_blank_image(page_image.crop(line_bbox)):
                good_lines.append(line)
```

```17:20:marker/marker/processors/blank_page.py
class BlankPageProcessor(BaseProcessor):
    """
    A processor to filter out blank pages detected as a single layout block
```

### 2.5 Repetitive header/footer suppression (pre-model, structural)

Fuzzy cross-page common-element detection; not entropy-based:

```14:18:marker/marker/processors/ignoretext.py
class IgnoreTextProcessor(BaseProcessor):
    """
    A processor for identifying and ignoring common text blocks in a document. 
    These blocks often represent repetitive or non-essential elements, such as headers, footers, or page numbers.
```

### 2.6 Deliberate base64 (not garbage filtering)

Images encoded for JSON/API output:

```55:62:marker/marker/renderers/__init__.py
        if to_base64:
            ...
            cropped = base64.b64encode(image_buffer.getvalue()).decode(
```

HTML data-URI preprocessing decodes and re-encodes images for PDF rendering:

```86:98:marker/marker/providers/document.py
    def _preprocess_base64_images(html_content):
        pattern = r'data:([^;]+);base64,([^"\'>\s]+)'
        ...
                img_data = base64.b64decode(match.group(2))
```

### 2.7 No post-markdown garbage-blob strip

No regex/entropy filter on final markdown for embedded data streams. Quality improvement is optional LLM correction (`marker/marker/converters/pdf.py:72`).

---

## 3. MinerU

### 3.1 Absurd native char-count cap (pre-model)

Pages with >65535 native chars fall back to post-OCR instead of trusting embedded text:

```17:17:MinerU/mineru/utils/span_pre_proc.py
MAX_NATIVE_TEXT_CHARS_PER_PAGE = 65535
```

```54:62:MinerU/mineru/utils/span_pre_proc.py
        if page_char_count is not None and page_char_count > MAX_NATIVE_TEXT_CHARS_PER_PAGE:
            logger.info(
                "Fallback to post-OCR in txt_spans_extract due to high char count: "
                f"count_chars={page_char_count}"
            )
```

### 3.2 Unicode Private Use Area (PUA) garbage detection (pre-model)

Font-mapping garbage (common in broken PDFs) triggers per-span OCR fallback:

```312:317:MinerU/mineru/utils/span_pre_proc.py
def _is_private_use_char(char: str) -> bool:
    """判断单个字符是否落在 Unicode 私用区，用于识别字体映射异常。"""
    return (
        len(char) == 1
        and PRIVATE_USE_AREA_START <= ord(char) <= PRIVATE_USE_AREA_END
```

```353:362:MinerU/mineru/utils/span_pre_proc.py
def _should_fallback_to_post_ocr_for_private_use_text(signal) -> bool:
    ...
    return (
        signal['max_pua_run'] >= PRIVATE_USE_TEXT_RUN_THRESHOLD
        or signal['pua_ratio'] >= PRIVATE_USE_TEXT_RATIO_THRESHOLD
    )
```

### 3.3 Sparse/empty span heuristic (pre-model)

```291:294:MinerU/mineru/utils/span_pre_proc.py
        elif len(span['content']) * span['height'] < span['width'] * 0.5:
            need_ocr_spans.append(span)
```

### 3.4 Deliberate base64 handling (extraction, not garbage filter)

Inline data-URIs in HTML are decoded to files; unrecognized formats are skipped:

```78:80:MinerU/mineru/backend/utils/html_image_utils.py
    match = INLINE_IMAGE_DATA_URI_RE.match(b64_data_uri)
    if not match:
        logger.warning(f"Unrecognized image_base64 format in page {page_index}, skipping.")
```

VLM pipeline encodes crops for prompts:

```241:242:MinerU/mineru/backend/pipeline/batch_analyze.py
        b64_str = base64.b64encode(encoded.tobytes()).decode("ascii")
        return f"data:image/jpg;base64,{b64_str}"
```

### 3.5 Broken-page skip (pre-model, PDF repair)

```204:221:MinerU/mineru/cli/common.py
            "PDFium rewrite returned empty bytes, trying to skip broken pages."
            ...
            skipped_pages = [page_index + 1 for page_index in broken_page_indices]
            ...
                f"Skipped broken PDF pages during PDFium rewrite: {skipped_pages}"
```

### 3.6 No post-markdown garbage-blob filter

No repetition, entropy, or base64-garbage strip on assembled markdown. "Hallucination-free" claims refer to pipeline-vs-VLM mode choice (`MinerU/mineru/cli/api_request.py:112`), not a text-span filter.

---

## 4. olmocr

### 4.1 Document-level pre-filter (pre-model, optional `--apply_filter`)

`PdfFilter` drops whole PDFs: forms, non-English, SEO/download spam, unreadable PDFs:

```35:62:olmocr/olmocr/filter/filter.py
    def _is_download_spam(self, base_text: str) -> bool:
        seo_words = {
            "download", "pdf", "epub", ...
        }
        ...
        return (seo_score / total_words) > self.download_spam_threshold
```

```97:110:olmocr/olmocr/filter/filter.py
        if alpha_count / len(base_text) < 0.50:
            logger.info(f"Keeping {local_pdf_path} on the safe side because it's text does not contain many letters ...")
            return False  # keep the pdf
        ...
        if self.apply_download_spam_check and self._is_download_spam(base_text):
            logger.info(f"Filtering out {local_pdf_path} because of SEO/download spam")
            return True  # Filter out
```

Applied at document ingress:

```540:542:olmocr/olmocr/pipeline.py
        if args.apply_filter and get_pdf_filter().filter_out_pdf(local_pdf_path):
            logger.info(f"Filtering out pdf {pdf_orig_path}")
            return None
```

**Important:** Low alpha ratio does **not** filter; it keeps the PDF (lines 97-99). This is a corpus-curation gate, not a per-chunk markdown filter.

### 4.2 Deliberate base64 for VLM prompts (not garbage filtering)

```112:140:olmocr/olmocr/pipeline.py
        image_base64 = await asyncio.to_thread(render_pdf_to_base64png, local_pdf_path, page, ...)
        ...
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
```

### 4.3 Post-generation validity and truncation checks (post-model)

Invalid if context exceeded or generation did not finish cleanly:

```200:206:olmocr/olmocr/pipeline.py
        is_valid = True
        if base_response_data["usage"]["total_tokens"] > MODEL_MAX_CONTEXT:
            is_valid = False
        if base_response_data["choices"][0]["finish_reason"] != "stop":
            is_valid = False
```

`max_tokens` cap on page query:

```107:144:olmocr/olmocr/pipeline.py
    MAX_TOKENS = 8000
    ...
        "max_tokens": MAX_TOKENS,
```

### 4.4 Fallback and document discard (post-model)

Failed pages fall back to `pdftotext`; too many fallbacks discard the document:

```233:249:olmocr/olmocr/pipeline.py
def make_fallback_result(pdf_orig_path: str, pdf_local_path: str, page_num: int) -> PageResult:
    """Create a fallback PageResult using pdftotext."""
```

```559:562:olmocr/olmocr/pipeline.py
        if num_fallback_pages / num_pages > args.max_page_error_rate:
            logger.error(
                f"Document {pdf_orig_path} has {num_fallback_pages} fallback pages out of {num_pages} exceeding max_page_error_rate ..."
```

### 4.5 Repetition mitigation at retry (pre-model, sampling)

Higher temperature on later attempts to break decode loops:

```84:85:olmocr/olmocr/pipeline.py
# Temperature values for retry attempts - higher temperature helps overcome repetition issues
TEMPERATURE_BY_ATTEMPT = [0.1, 0.1, 0.2, 0.3, 0.5, 0.8, 0.9, 1.0]
```

### 4.6 No markdown-span garbage/base64 filter

No code strips long base64-like runs from model-produced markdown. Training-only cutoff detection (`olmocr/tests/test_cutoff_detection.py`) is for synthetic HTML mining, not production output.

---

## 5. Dolphin

### 5.1 Optional tail-repetition truncation (post-model, `post_process=True`)

```52:77:Dolphin/utils/markdown_utils.py
def truncate_repeated_tail(s, threshold=20, keep=1):
    ...
        if count > threshold:
            non_repeat_part = s[:pos]
            kept_repeats = pattern * keep
            return non_repeat_part + kept_repeats
```

Applied per recognition block only when post-processing enabled:

```320:321:Dolphin/utils/markdown_utils.py
                    if self.post_process:
                        text = truncate_repeated_tail(text, threshold=20, keep=1)
```

### 5.2 Formula dot repetition cleanup (post-model, optional)

```47:49:Dolphin/utils/markdown_utils.py
def replace_repeated_cdots(latex):
    latex = re.sub(r"(\\cdots\s*){3,}", r"\\cdots$$", latex)
```

### 5.3 Deliberate base64 for figures (not garbage filtering)

Raw base64 figure text is wrapped as a data URI:

```256:264:Dolphin/utils/markdown_utils.py
            if text.startswith("data:image/"):
                return f"![Figure {section_count}]({text})\n\n"
            ...
                data_uri = f"data:image/{img_format};base64,{text}"
```

### 5.4 Pass-through when post_process disabled (proving no default filter)

Regular paragraph text is emitted unchanged through `_handle_text`:

```342:345:Dolphin/utils/markdown_utils.py
                    else:
                        processed_text = self._handle_text(text)
                        markdown_content.append(f"{processed_text}\n\n")
```

`repetition_penalty` in generation is commented out (no decode-time guard):

```103:108:Dolphin/demo_page.py
        generated_ids = self.model.generate(
            **inputs,
            max_new_tokens=4096,
            do_sample=False,
            temperature=None,
            # repetition_penalty=1.05
```

### 5.5 No pre-model garbage detection

No entropy, printable ratio, language, or base64-garbage filters on input. Dolphin is image-in, text-out with optional light post-cleaning.

---

## Comparative table

| Repo | Garbage-text detection | Mechanism | Applied where | Portable idea for whisker chunk filter |
|------|------------------------|-----------|---------------|----------------------------------------|
| **nougat** | Yes (repetition, hallucinated refs, absurd tables) | Logit-variance early stop; suffix repetition; fuzzy duplicate lines; per-line LaTeX counts | During decode + post-model on generated markdown | Replace bad spans with `[MISSING_PAGE_*]` placeholders; tail-repetition truncation |
| **marker** | Yes (garbled native PDF text) | Space/newline/alphanum ratios; invalid-char count; ML OCR-error classifier; blank-line image crop | Pre-model on PDF provider text (before layout/OCR) | **`alphanum_ratio` threshold** on chunk spans; invalid-char density |
| **MinerU** | Yes (PUA chars, extreme char count, sparse spans) | Unicode PUA run/ratio; 65535 char page cap; width×height content heuristic | Pre-model on PDF span extraction | PUA-ratio gate; **max span length** with OCR/skip fallback |
| **olmocr** | Partial (corpus-level only) | Language detect; SEO word-frequency; alpha sanity (keep-not-drop); finish_reason/context checks | Pre-model whole-PDF filter + post-model page validity | Document-level spam word ratio less useful at chunk level; **finish_reason / length cap** pattern for LLM chunks |
| **Dolphin** | Minimal (optional tail repetition) | Suffix pattern repeat count; `\\cdots` regex | Post-model only if `post_process=True` | `truncate_repeated_tail` for model loop artifacts; default pass-through otherwise |

---

## Portable ideas (ranked for chunk-level markdown filter)

Pure Python, deterministic, no new dependencies.

1. **Alphanumeric ratio + invalid-char density (from marker)**  
   For any chunk span over N chars, compute `alphanum_ratio` and count U+FFFD/replacement chars. Spans below ~0.3 alphanum or above ~3% invalid chars become `[EMBEDDED_DATA_STRIPPED]` (marker uses this pre-OCR at `marker/marker/providers/pdf.py:379-399`). Directly targets base64-like blobs that are mostly `A-Za-z0-9+/=`.

2. **Maximum run-length on base64 alphabet (regex, no decode)**  
   Flag spans where a single line (or paragraph) has a run of `[A-Za-z0-9+/=]{500,}` or total base64-alphabet fraction >90% over >2 KB. None of the five repos do this explicitly, but it is the closest fit to P2728-style garbage surviving `tomd`. Deterministic, cheap.

3. **Tail repetition truncation (nougat + Dolphin)**  
   Before sending a chunk to the LLM, run suffix-pattern repetition collapse (`truncate_repetitions` / `truncate_repeated_tail`). Stops the model from burning `max_tokens` narrating loops. Already proven in two pipelines (`nougat/nougat/postprocessing.py:102`, `Dolphin/utils/markdown_utils.py:52`).

4. **Hard per-paragraph byte cap with placeholder (MinerU char-count spirit)**  
   MinerU's 65535 native-char fallback (`MinerU/mineru/utils/span_pre_proc.py:54-62`) suggests a chunking-layer cap: any single H2-section paragraph over e.g. 32 KB of mostly non-whitespace text gets replaced with a one-line placeholder citing byte length, not sent to the LLM.

5. **PUA / non-printable ratio (MinerU)**  
   Count chars in Unicode PUA range U+E000–U+F8FF and other `unicodedata.category` `C*` classes. High ratio triggers strip/skip (`MinerU/mineru/utils/span_pre_proc.py:312-362`). Useful for font-mapped garbage distinct from base64.

---

## Summary judgment

| Question | Answer |
|----------|--------|
| Do any repos filter base64 garbage blobs in markdown? | **No.** Base64 appears only for intentional image/prompt encoding. |
| Closest pre-existing patterns? | marker `alphanum_ratio`, MinerU PUA + char-count caps, nougat/Dolphin repetition truncation. |
| Post-LLM truncation guards? | olmocr `finish_reason` + context check; nougat page placeholders. |
| Entropy-based detection? | **None** in these five repos. |
| Best starting point for whisker `tapetum_llm` chunking? | Combine marker-style **alphanum ratio** with a **long base64-alphabet run regex** and **placeholder replacement** (nougat-style), applied pre-LLM per chunk.
