# PDF extraction libraries: binary/garbage/blob handling research

Research date: 2026-07-07. Local clones under `packages/whisker/research/repos/`.

**Context:** WG21 papers converted to markdown sometimes contain giant base64-like garbage blobs (undecodable embedded data streams). We are evaluating chunk-level filters before LLM QA (`tapetum_llm/chunking.py`). This report surveys five PDF-to-text/markdown libraries for prior art.

---

## PyMuPDF

### 1. Binary / undecodable content streams

**Default unknown-unicode policy: emit CID/GID, not filter.** Text extraction flags include `TEXT_USE_CID_FOR_UNKNOWN_UNICODE` by default in word/block/dict modes:

```17633:17638:PyMuPDF/src/__init__.py
TEXTFLAGS_WORDS = (0
        | TEXT_PRESERVE_LIGATURES
        | TEXT_PRESERVE_WHITESPACE
        | TEXT_MEDIABOX_CLIP
        | TEXT_USE_CID_FOR_UNKNOWN_UNICODE
        )
```

**U+FFFD as replacement character for unmappable glyphs.** Partial OCR detects spans containing `chr(0xFFFD)`, redacts them, and re-extracts legible text; illegible spans are sent to OCR:

```337:342:PyMuPDF/src/utils.py
    # Ensure 0xFFFD is not suppressed
    flags = (
        flags
        & ~pymupdf.TEXT_USE_CID_FOR_UNKNOWN_UNICODE
        & ~pymupdf.TEXT_USE_GID_FOR_UNKNOWN_UNICODE
    )
```

```386:393:PyMuPDF/src/utils.py
        fffd_spans = [
            s["bbox"]
            for b in blocks
            if b["type"] == 0
            for l in b["lines"]
            for s in l["spans"]
            if chr(0xFFFD) in s["text"]
        ]
```

**Orphaned UTF-16 surrogates escaped as `\ufffd` in text output:**

```18755:18761:PyMuPDF/src/__init__.py
def make_escape(ch):
    if ch == 92:
        return "\\u005c"
    elif 32 <= ch <= 127 or ch == 10:
        return chr(ch)
    elif 0xd800 <= ch <= 0xdfff:  # orphaned surrogate
        return "\\ufffd"
```

**`clean_contents(sanitize=1)` applies to annotation appearance streams, not extracted markdown text:**

```875:881:PyMuPDF/src/__init__.py
    def clean_contents(self, sanitize=1):
        """Clean appearance contents stream."""
        CheckParent(self)
        annot = self.this
        pdf = mupdf.pdf_get_bound_document(mupdf.pdf_annot_obj(annot))
        filter_ = _make_PdfFilterOptions(recurse=1, instance_forms=0, ascii=0, sanitize=sanitize)
        mupdf.pdf_filter_annot_contents(pdf, annot, filter_)
```

**Finding:** No pass that detects or strips high-entropy / base64-like text blobs in extracted output. Unknown-font text may surface as PUA/CID characters or U+FFFD; OCR path handles FFFD spans only when OCR is invoked.

### 2. Text-quality heuristics

Partial OCR uses FFFD-in-span as a legibility signal (see above). Font subsetting checks `0xFFFD in unc_set` to switch glyph-vs-unicode strategy:

```7617:7619:PyMuPDF/src/__init__.py
                with io.open(f"{tmp_dir}/uncfile.txt", "w", encoding='utf8') as unc_file:
                    if 0xFFFD in unc_set:  # error unicode exists -> use glyphs
                        args.append(f"--gids-file={uncfile_path}")
```

No printable-char ratio, entropy, or mojibake heuristics on extracted text.

### 3. LLM-oriented filtering

Not applicable; PyMuPDF is a low-level PDF engine, not an LLM markdown pipeline.

### 4. Base64 / data URI mentions

`base64.b64encode` appears in Python bindings for pixmap/stream serialization (`src/__init__.py:16576`), not for filtering extracted text.

---

## pymupdf4llm

### 1. Binary / undecodable content

**Null bytes replaced with U+FFFD in final markdown string:**

```1221:1223:pymupdf4llm/src/helpers/pymupdf_rag.py
        while parms.md_string.startswith("\n"):
            parms.md_string = parms.md_string[1:]
        parms.md_string = parms.md_string.replace(chr(0), REPLACEMENT_CHARACTER)
```

**Optional `use_glyphs=True` swaps FFFD for GID numbers** via `FZ_STEXT_USE_GID_FOR_UNKNOWN_UNICODE`:

```1278:1280:pymupdf4llm/src/helpers/pymupdf_rag.py
    # optionally replace REPLACEMENT_CHARACTER by glyph number
    if use_glyphs:
        textflags |= mupdf.FZ_STEXT_USE_GID_FOR_UNKNOWN_UNICODE
```

**PUA characters dropped from list-item bullet detection** (not global text filter):

```155:166:pymupdf4llm/src/helpers/document_layout.py
def omit_if_pua_char(text):
    """Check if character is in the Private Use Area (PUA) of Unicode."""
    if len(text) != 1:  # only single characters are checked
        return text
    o = ord(text)
    if (
        (0xE000 <= o <= 0xF8FF)
        or (0xF0000 <= o <= 0xFFFFD)
        or (0x100000 <= o <= 0x10FFFD)
    ):
        return ""
    return text
```

Used at list-item parsing sites, e.g.:

```301:302:pymupdf4llm/src/helpers/document_layout.py
    if not omit_if_pua_char(span0_text):
        spans.pop(0)
```

**Finding:** No detection or removal of long base64-like runs in body text. PUA stripping is scoped to bullet-character classification.

### 2. Text-quality heuristics

- **`sanitize_spans`** merges adjacent spans on a line (layout repair, not content safety):

```70:81:pymupdf4llm/src/helpers/get_text_lines.py
    def sanitize_spans(line):
        """Sort and join the spans in a re-synthesized line.
        ...
        Returns:
            A list of sorted, and potentially cleaned-up spans
        """
```

- **`image_size_limit=0.05`** skips images smaller than 5% of page width/height (reduces noise graphics, not text blobs):

```489:494:pymupdf4llm/src/helpers/pymupdf_rag.py
        if (
            rect.width < page.rect.width * image_size_limit
            or rect.height < page.rect.height * image_size_limit
        ):
            return ""
```

- **`graphics_limit`** (optional) ignores pages with excessive vector graphics count (`pymupdf_rag.py:373`).
- **`fontsize_limit=3`** drops tiny text (`pymupdf_rag.py:347`).
- OCR tests assert FFFD absent when OCR backends available (`tests/test_ocr.py:36`).

No entropy or printable-ratio checks on text.

### 3. LLM-oriented filtering (markdown output)

**Images embedded as base64 data URIs when `embed_images=True`, with no byte-size cap** (contrast opendataloader-pdf):

```509:513:pymupdf4llm/src/helpers/pymupdf_rag.py
        elif embed_images is True:
            # make a base64 encoded string of the image
            data = b2a_base64(pix.tobytes(IMG_EXTENSION)).decode()
            data = f"data:image/{IMG_EXTENSION};base64," + data
            return data
```

Same pattern in layout mode:

```818:821:pymupdf4llm/src/helpers/document_layout.py
                        # make a base64 encoded string of the image
                        data = base64.b64encode(box.image).decode()
                        data = f"data:image/{self.image_format};base64," + data
                        md_string += GRAPHICS_TEXT % data + "\n\n"
```

Default is `embed_images=False` (`src/__init__.py:63`). **`table_max_width=100`** caps table column width in chars only.

**Finding:** pymupdf4llm intentionally produces base64 data URIs for images but does not cap payload size or filter accidental base64 text in body content.

### 4. Base64 / data URI mentions

Explicit and tested (`tests/test_137.py:21` uses `embed_images=True`). No tests or code targeting garbage base64 *text* blobs.

---

## pdfplumber

### 1. Binary / undecodable content

**PDF name/string decoding:** `decode_text` maps PDFDocEncoding; on unknown code points falls back to `str(s)` (pass-through):

```10:21:pdfplumber/pdfplumber/utils/pdfinternals.py
def decode_text(s: Union[bytes, str]) -> str:
    """
    Decodes a PDFDocEncoding string to Unicode.
    ...
    """
    try:
        ords = (ord(c) if isinstance(c, str) else c for c in s)
        return "".join(PDFDocEncoding[o] for o in ords)
    except IndexError:
        return str(s)
```

**Page char text comes straight from pdfminer** with optional Unicode normalization only:

```378:384:pdfplumber/pdfplumber/page.py
        if isinstance(obj, (LTChar, LTTextContainer)):
            text = obj.get_text()
            attr["text"] = (
                normalize_unicode(self.pdf.unicode_norm, text)
                if self.pdf.unicode_norm is not None
                else text
            )
```

**Annotation metadata decode failures:** warn or raise per `raise_unicode_errors` (default `True`):

```297:308:pdfplumber/pdfplumber/page.py
                    try:
                        extras[k] = v.decode("utf-8")
                    except UnicodeDecodeError:
                        try:
                            extras[k] = v.decode("utf-16")
                        except UnicodeDecodeError:
                            if self.pdf.raise_unicode_errors:
                                raise
                            warn(
                                f"Could not decode {k} of annotation."
                                f" {k} will be missing."
                            )
```

**Finding:** No junk/garbage detection on page text. Extracted char strings pass through unchanged.

### 2. Text-quality heuristics

Structural/tolerance heuristics only (table clustering, dedupe_chars, etc.). No FFFD ratio, printable ratio, or entropy checks in core extraction.

### 3. LLM-oriented filtering

None. pdfplumber targets programmatic PDF inspection, not LLM markdown.

### 4. Base64 / data URI mentions

**Base64 used only to serialize binary PDF stream objects in JSON/CSV export**, not in text extraction:

```58:59:pdfplumber/pdfplumber/convert.py
def to_b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")
```

```112:113:pdfplumber/pdfplumber/convert.py
    def do_PDFStream(self, obj: Any) -> Dict[str, Optional[str]]:
        return {"rawdata": to_b64(obj.rawdata) if obj.rawdata else None}
```

---

## pdf-to-markdown

Browser-side tool (pdf.js). Parses PDF in `LoadingView.jsx`, transforms to markdown via layout heuristics.

### 1. Binary / undecodable content

**Text pass-through from pdf.js `getTextContent()`:** `item.str` copied directly into `TextItem` with no sanitization:

```123:150:pdf-to-markdown/src/javascript/components/LoadingView.jsx
                    page.getTextContent().then(function(textContent) {
                        const textItems = textContent.items.map(function(item) {
                            ...
                            return new TextItem({
                                x: Math.round(item.transform[4]),
                                y: Math.round(item.transform[5]),
                                width: Math.round(item.width),
                                height: Math.round(dividedHeight <= 1 ? item.height : dividedHeight),
                                text: item.str,
                                font: item.fontName
                            });
                        });
```

**Finding:** No binary/junk/corrupt-content handling at extraction layer. Whatever pdf.js emits is preserved.

### 2. Text-quality heuristics

Layout-only: font-height stats (`CalculateGlobalStats.jsx`), header/list/TOC detection, repetitive element removal, code-block detection. **`stringFunctions.jsx`** provides digit/whitespace/list helpers and `hasUpperCaseCharacterInMiddleOfWord` (TOC/header heuristic), not garbage detection.

No FFFD, printable ratio, or entropy checks.

### 3. LLM-oriented filtering

None. README explicitly warns manual cleanup is required (`README.md:44`).

### 4. Base64 / data URI mentions

No matches in `src/javascript/` extraction path. Bundled pdf.js worker contains minified base64 routines for internal PDF parsing, not for output filtering.

---

## opendataloader-pdf

Java core + Python/Node wrappers. Explicitly targets safe LLM data loading.

### 1. Binary / undecodable content

**Invalid PDF at preprocessing:** throws `InvalidPdfFileException` for wrong magic bytes or truncated bodies (`DocumentProcessorMagicNumberTest.java:100` — `"corrupted or truncated"`).

**U+FFFD replacement:** veraPDF inserts `\uFFFD` for unmappable chars; `TextProcessor.replaceUndefinedCharacters` replaces with configurable char (default space):

```41:52:opendataloader-pdf/java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/processors/TextProcessor.java
    public static void replaceUndefinedCharacters(List<IObject> contents, String replacementCharacterString) {
        if (ChunkParser.REPLACEMENT_CHARACTER_STRING.equals(replacementCharacterString)) {
            return;
        }
        for (IObject object : contents) {
            if (object instanceof TextChunk) {
                TextChunk textChunk = ((TextChunk) object);
                if (textChunk.getValue().contains(ChunkParser.REPLACEMENT_CHARACTER_STRING)) {
                    textChunk.setValue(textChunk.getValue().replace(ChunkParser.REPLACEMENT_CHARACTER_STRING, replacementCharacterString));
```

Default config:

```76:76:opendataloader-pdf/java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/api/Config.java
    private String replaceInvalidChars = " ";
```

CLI: `--replace-invalid-chars` (`CLIOptions.java:104-105`).

**Replacement-char ratio warning (≥30%):** measured before replacement; suggests hybrid OCR fallback:

```75:82:opendataloader-pdf/java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/processors/ContentFilterProcessor.java
        double replacementCharRatio = TextProcessor.measureReplacementCharRatio(pageContents);
        StaticLayoutContainers.setReplacementCharRatio(pageNumber, replacementCharRatio);
        if (replacementCharRatio >= 0.3) {
            LOGGER.log(Level.WARNING,
                "Page {0}: {1,number,#.#%} of characters are replacement characters (U+FFFD). "
                + "This PDF likely contains CID-keyed fonts without ToUnicode mappings. "
                + "Text extraction may be incomplete. Consider enabling hybrid OCR fallback with --hybrid docling-fast.",
```

**Hybrid backend:** pages with invalid font-encoding code points may fail and fall back to Java path (`HybridClient.java:368-370` — `"invalid code points in PDF font encoding"`).

**Plain-text output sanitize:** strips null bytes only:

```250:251:opendataloader-pdf/java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/text/TextGenerator.java
    private String sanitize(String value) {
        return value == null ? "" : value.replace("\u0000", " ");
```

**Python hybrid server:** lone surrogates and nulls → U+FFFD before JSON response:

```113:114:opendataloader-pdf/python/opendataloader-pdf/src/opendataloader_pdf/hybrid_server.py
# Regex matching lone surrogates (U+D800..U+DFFF) and null characters
_INVALID_UNICODE_RE = re.compile(r"[\ud800-\udfff\x00]")
```

```264:265:opendataloader-pdf/python/opendataloader-pdf/src/opendataloader_pdf/hybrid_server.py
    if isinstance(data, str):
        return _INVALID_UNICODE_RE.sub("\ufffd", data)
```

**Finding:** Handles *character-level* invalid Unicode and warns on high FFFD ratios. Does **not** detect or strip long base64-alphabet garbage strings in extracted text.

### 2. Text-quality heuristics

| Heuristic | Location | Default |
|-----------|----------|---------|
| Tiny text filter (height ≤ 1pt) | `ContentFilterProcessor.java:60-62` | on |
| Out-of-page content removal | `ContentFilterProcessor.java:64-66` | on |
| Hidden text (contrast ratio) | `HiddenTextProcessor.java` | off |
| Duplicate text chunk removal | `ContentFilterProcessor.java:56` | on |
| Background line-art removal | `ContentFilterProcessor.java:95-111` | on |
| FFFD ratio ≥ 30% warning | `ContentFilterProcessor.java:77-82` | on |

No printable-ratio or Shannon-entropy checks on text content.

### 3. LLM-oriented filtering

**Content safety (opt-in PII masking):** `--sanitize` enables regex rules replacing emails, phones, IPs, credit cards, URLs (`FilterConfig.java:38-77`, `ContentSanitizer.java:253-261`). Disabled by default (`filterSensitiveData = false`).

**Content safety geometry filters** can be disabled via `--content-safety-off` (`CLIOptions.java:90-92`).

**Image output modes:** `off | embedded | external` (`CLIOptions.java:130-131`). Embedded mode uses base64 data URIs with **10 MB cap**:

```33:37:opendataloader-pdf/java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/utils/Base64ImageUtils.java
    /**
     * Maximum image file size for Base64 embedding (10MB).
     * Larger images will be skipped to prevent memory exhaustion.
     */
    public static final long MAX_EMBEDDED_IMAGE_SIZE = 10L * 1024 * 1024;
```

```61:64:opendataloader-pdf/java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/utils/Base64ImageUtils.java
                if (fileSize > MAX_EMBEDDED_IMAGE_SIZE) {
                    LOGGER.log(Level.WARNING, "Image too large to embed ({0} bytes, max {1} bytes): {2}",
                        new Object[]{fileSize, MAX_EMBEDDED_IMAGE_SIZE, imageFile.getName()});
                    return null;
```

**Alt-text / description sanitization** strips PUA, markup chars, nulls (`EnrichedImageChunk.java:86-104`).

**Pipeline hook:** `ContentSanitizer.sanitizeContents()` runs after extraction when `--sanitize` is set (`DocumentProcessor.java:188-190`).

### 4. Base64 / data URI mentions

- Intentional: `Base64ImageUtils.toDataUri`, `MarkdownGenerator.java:209`, JSON `ImageSerializerTest.java:96`.
- Tests fixture: `samples/pdf/sanitization-targets.pdf` (PII masking, not base64 blobs).
- No code paths search for accidental base64 *text* in body content.

---

## Comparative table

| Repo | Binary / undecodable handling | Text-quality heuristics | LLM-oriented filtering | Portable idea for whisker chunk filter |
|------|------------------------------|-------------------------|------------------------|----------------------------------------|
| **PyMuPDF** | Default CID for unknown Unicode; U+FFFD for unmappable glyphs; partial OCR redacts FFFD spans | FFFD-span detection for OCR routing only | N/A (engine) | FFFD-span bbox redaction pattern → detect FFFD-heavy *lines* and skip/collapse |
| **pymupdf4llm** | Null→FFFD; optional GID mode; PUA dropped for bullet chars only | Image/graphics/fontsize size filters; span merging | Optional base64 image embed (**no size cap**); table width cap | Cap embedded payload size (borrow from opendataloader 10 MB pattern) |
| **pdfplumber** | Pass-through char text from pdfminer; metadata decode warn/raise | Structural tolerances only | None | Pass-through proof: chunk filter must live downstream of extraction |
| **pdf-to-markdown** | Pass-through `item.str` from pdf.js | Layout/header/list/code heuristics only | None | Pass-through proof: same as pdfplumber |
| **opendataloader-pdf** | U+FFFD→space (configurable); FFFD ratio warn ≥30%; corrupt PDF reject; surrogate/null sanitize | Tiny/out-of-page/hidden-text/background filters | Opt-in PII regex; base64 images capped at 10 MB; alt-text PUA strip | **Best prior art:** replacement-char ratio threshold; regex PII sanitizer architecture; max payload cap |

---

## Portable ideas (ranked for chunk-level markdown filter)

Pure Python, deterministic, no new dependencies.

1. **Long-run base64-alphabet line detector (highest fit).** None of the surveyed libraries filter accidental base64 *text* blobs. Invert opendataloader's intentional `data:...;base64,...` embedding: match lines/paragraphs where ≥N chars and ≥90% of non-whitespace chars match `[A-Za-z0-9+/=]`, optionally prefixed with `data:`. Replace with a fixed placeholder (`[embedded data omitted, N chars]`) or drop the chunk section. Directly addresses P2728R11/R12.

2. **Printable-word vs. symbol ratio on candidate lines.** Complement (1): require low whitespace *and* low ratio of `[a-zA-Z]{3,}` word tokens. Base64 garbage fails natural-language word tests even when alphabet-compliant. Deterministic, cheap.

3. **U+FFFD / PUA density threshold per chunk (from opendataloader + pymupdf4llm).** Port `measureReplacementCharRatio` logic: if `count(FFFD) / len(text) ≥ 0.3` or PUA code points exceed threshold, mark chunk as low-fidelity and replace body with a one-line warning rather than sending to LLM. Handles CID-font garbage distinct from base64 blobs.

4. **Max single-paragraph byte cap (from opendataloader image cap).** If any paragraph between H2 boundaries exceeds e.g. 64 KiB (configurable constant), truncate or omit with placeholder. Simpler than entropy; catches blobs even when not valid base64.

5. **Explicit `data:` URI strip pass.** Regex remove `data:[^;]+;base64,[A-Za-z0-9+/=]+` spans (with max match length guard). Handles intentional and accidental data URIs in markdown without affecting normal prose.

---

## Gap analysis for P2728 use case

| Symptom | Covered by any repo? |
|---------|---------------------|
| Giant base64-like text blob in markdown body | **No** — all repos pass through or only embed images intentionally |
| LLM max_tokens blow-up on garbage chunk | **No** — no chunk/paragraph size guard on text |
| Undecodable font → U+FFFD / PUA | Partial — PyMuPDF OCR path, opendataloader ratio warning + replace |
| Intentional base64 image in markdown | Yes — pymupdf4llm, opendataloader (with size cap in Java only) |

**Conclusion:** A chunk-level filter in `tapetum_llm` is justified; none of these extraction libraries solve the post-conversion garbage-blob problem. Closest patterns to port: opendataloader's ratio warning + payload cap + regex sanitizer pipeline architecture, plus a new base64-alphabet long-run detector (not present in any repo).
