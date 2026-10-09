# Base64 / data-URI / garbage-text handling in converters and misc extractors

Research across six local clones: `pandoc`, `grobid`, `camelot`, `img2table`, `surya`, `PDF-Extract-Kit`.

**Scope note:** These repos are upstream of our `tomd` → `whisker tapetum_llm` lane. None implement a chunk-level markdown filter for megabyte `data:image/png;base64,...` lines like P2728R11/R12. Their relevant patterns are: (a) whether converters pass through or externalize data URIs, (b) domain-specific noise filters on extracted text, (c) length/repetition guards on model output.

---

## 1. pandoc (Haskell)

### 1.1 Data-URI parsing and fetch path

Pandoc recognizes `data:...;base64,...` URIs with a dedicated parser and lenient decode:

```125:141:src/Text/Pandoc/URI.hs
pBase64DataURI :: A.Parser (B.ByteString, MimeType)
pBase64DataURI = base64uri
 where
  base64uri = do
    A.string "data:"
    ...
    A.string ";base64,"
    b64 <- mconcat <$> many
              (A.takeWhile1 (A.inClass "A-Za-z0-9/+ \t\r\n") <|> percentOctet)
    ...
    pure (decodeLenient (encodeUtf8 b64), mime)
```

When fetching resources, `downloadOrRead` short-circuits on base64 data URIs:

```374:377:src/Text/Pandoc/Class/PandocMonad.hs
downloadOrRead s
 | "data:" `T.isPrefixOf` s,
   Right (bs, mt) <- A.parseOnly (pBase64DataURI <* A.endOfInput) s
   = pure (bs, Just mt)
```

### 1.2 HTML reader: data URIs pass through unchanged

The HTML reader does not decode or strip `data:` image sources. `canonicalizeUrl` explicitly returns them as-is:

```1230:1237:src/Text/Pandoc/Readers/HTML.hs
canonicalizeUrl :: PandocMonad m => Text -> TagParser m Text
canonicalizeUrl url
  | "data:" `T.isPrefixOf` url = return url
  | otherwise = do
     mbBaseHref <- baseHref <$> getState
     return $ case (parseURIReference (T.unpack url), mbBaseHref) of
```

`pImage` then writes that URL into the AST image node:

```816:823:src/Text/Pandoc/Readers/HTML.hs
pImage = do
  ...
  url <- canonicalizeUrl $ fromAttrib "src" tag
  ...
  return $ B.imageWith attr (escapeURI url) title (B.text alt)
```

For inline SVG, the reader can *create* a base64 data URI (SVG → image):

```833:839:src/Text/Pandoc/Readers/HTML.hs
  let rawText = T.strip $ renderTags' (opent : contents ++ [closet])
  let svgData = "data:image/svg+xml;base64," <>
                   UTF8.toText (encode $ UTF8.fromText rawText)
  ...
  return $ B.imageWith (ident,cls,kvs) svgData mempty mempty
```

### 1.3 Markdown writer: emits raw data URIs into markdown

The markdown writer does not externalize or truncate image `src`. It renders `![...](source)` with the source literal:

```705:727:src/Text/Pandoc/Writers/Markdown/Inline.hs
inlineToMarkdown opts img@(Image attr alternate (source, tit))
  ...
  | otherwise = do
  ...
  linkPart <- inlineToMarkdown opts (Link attr txt (source, tit))
  ...
  return $ case variant of
                ...
                _ -> "!" <> linkPart
```

The markdown *reader* also accepts inline base64 data URIs in link targets:

```1864:1878:src/Text/Pandoc/Readers/Markdown.hs
  src <- try (litBetween '<' '>') <|> try base64DataURI <|> sourceURL
  ...
base64DataURI = do
  ...
  case r of
    A.Done remaining consumed -> do
      ...
      return consumed
```

**Round-trip evidence:** test input preserves a full `data:image/png;base64,...` in markdown:

```1:3:test/command/typst-images.md
% pandoc -t typst
![dot](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAACXBIWXMAAC4jAAAuIwF4pT92AAAASUlEQVQYGa3OWwoAIAgEQNf739k0EjVCfxKCHtMqiEh0jcWjOKBAkQjPe7MFdun/IbRdDNb05nvolzWzEx0DdozK96W1PzjNHxcgphkBs9CoHwAAAABJRU5ErkJggg==){width=1in}
```

With `--embed-resources`, pandoc *creates* data URIs in HTML output (opposite direction from our problem):

```24:28:test/command/8948.md
% pandoc --embed-resources
![minimal](command/minimal.svg)
^D
<figure>
<img role="img" aria-label="minimal" src="data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBzdGFuZGFsb25lPSJubyI/PgoKPHN2ZyB2aWV3Qm94PSItLjMzMyAtLjMzMyA0ODAgMTUwIiBzdHlsZT0iYmFja2dyb3VuZC1jb2xvcjojZmZmZmZmMDAiIHZlcnNpb249IjEuMSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB4bWxuczp4bGluaz0iaHR0cDovL3d3dy53My5vcmcvMTk5OS94bGluayIgeG1sOnNwYWNlPSJwcmVzZXJ2ZSI+CiAgICA8cGF0aCBkPSJNIDAgMzUuNSBMIDYuNSAyMi41IEwgMTYgMzcgTCAyMyAyNCBMIDM0LjggNDMuNyBMIDQyLjUgMzAgTCA1MC4zIDQ3IEwgNTkuNyAyNy43IEwgNjkgNDcgTCA4NSAxNy43IEwgOTguMyAzOSBMIDExMyA5LjcgTCAxMjcuNyA0Mi4zIEwgMTM2LjMgMjMuNyBMIDE0NyA0NC4zIEwgMTU4LjMgMjAuMyBMIDE3MC4zIDQwLjMgTCAxNzcuNyAyNS43IEwgMTg5LjcgNDMgTCAxOTkuNyAyMSBMIDIwNy43IDM1IEwgMjE5IDExIEwgMjMzIDM3IEwgMjQwLjMgMjMuNyBMIDI1MSA0MyBMIDI2MyAxOC4zIEwgMjcyLjcgMzMuMyBMIDI4MyAxMCBMIDI5NSAzMi4zIEwgMzAxLjMgMjMgTCAzMTEuNyAzNyBMIDMyMy43IDcuNyBMIDMzOS4zIDM5IEwgMzQ2LjMgMjUuNyBMIDM1Ni4zIDQyLjMgTCAzNjkuNyAxNSBMIDM3Ni4zIDI1LjcgTCAzODQgOSBMIDM5MyAyOC4zIEwgNDAwLjMgMTkgTCA0MTEuNyAzOC4zIEwgNDIxIDIxIEwgNDM0LjMgNDMgTCA0NDUgMjUgTCA0NTMgMzYuMyBMIDQ2NC4zIDE4LjMgTCA0NzYuMiA0MC4zIEwgNDgwIDMzLjUgTCA0ODAgMjE1IEwgMCAyMTUgTCAwIDM1LjUgWiIgZmlsbD0iIzE3NTcyMCIvPgo8L3N2Zz4K" alt="minimal" />
```

Manual documents the embed-resources policy:

```1098:1103:MANUAL.txt
`--embed-resources[=true|false]`

:   Produce a standalone HTML file with no external dependencies, using
    `data:` URIs to incorporate the contents of linked scripts, stylesheets,
    images, and videos. The resulting file should be "self-contained," in the
    sense that it needs no external files and no net access to be displayed
```

### 1.4 `--extract-media`: externalizes embedded bytes (opt-in)

Default is no extraction (`optExtractMedia = Nothing`):

```835:835:src/Text/Pandoc/App/Opt.hs
    , optExtractMedia          = Nothing
```

When enabled, `extractMedia` writes mediabag items to disk and rewrites image paths:

```249:266:src/Text/Pandoc/Class/IO.hs
-- | Extract media from the mediabag into a directory (or a zip archive if the
-- path supplied ends in @.zip@.
extractMedia :: (PandocMonad m, MonadIO m) => FilePath -> Pandoc -> m Pandoc
extractMedia path d = do
  media <- getMediaBag
  ...
      return $ walk (adjustImagePath dir media) d
```

`fillMediaBag` fetches data URIs into the mediabag (decode via `fetchItem`), enabling later externalization:

```509:521:src/Text/Pandoc/Class/PandocMonad.hs
fillMediaBag :: PandocMonad m => Pandoc -> m Pandoc
fillMediaBag d = walkM handleImage d
  where handleImage ...
                Nothing -> do
                  (bs, mt) <- fetchItem src
                  insertMedia fp mt (BL.fromStrict bs)
```

Pipeline only runs `fillMediaBag` when `optExtractMedia` is set or output is docx:

```310:315:src/Text/Pandoc/App.hs
            >=> (if not (optSandbox opts) &&
                    (isJust (optExtractMedia opts)
                     || format == "docx")
                 then fillMediaBag
                 else return)
            >=> maybe return extractMedia (optExtractMedia opts)
```

Manual:

```758:768:MANUAL.txt
`--extract-media=`*DIR*|*FILE*`.zip`

:   Extract images and other media contained in or linked from
    the source document to the path *DIR*, creating it if
    necessary, and adjust the images references in the document
    so they point to the extracted files.
    ...
    Otherwise filenames are constructed from the SHA1 hash of
    the contents.
```

### 1.5 Failure fallback: replace unfetchable image with alt text

On fetch failure, pandoc substitutes a span with alt text instead of emitting the broken URL:

```524:534:src/Text/Pandoc/Class/PandocMonad.hs
                PandocResourceNotFound _ -> do
                  report $ CouldNotFetchResource src
                            "replacing image with description"
                  -- emit alt text
                  return $ replacementSpan attr src tit lab
```

### 1.6 No length cap on emitted text nodes

No grep hits for max-length truncation of inline text or image URLs in the markdown writer. Image `source` is emitted verbatim via `literal source` in `Inline.hs:725-726`.

**Pandoc verdict:** First-class data-URI support; default HTML→markdown path **passes through** full base64 payloads. Externalization requires explicit `--extract-media`. This is the closest upstream analogue to "strip or externalize before downstream consumption," but it is opt-in and not applied by default.

---

## 2. grobid (Java, scientific PDF)

### 2.1 No base64 / data-URI handling

`findstr /s /i base64 grobid-core/src/main/java/org/grobid/core/*.java` returns no matches. Grobid does not parse, emit, or filter base64 blobs.

### 2.2 PDF noise awareness (not blob filtering)

Document ingestion acknowledges invalid UTF from PDF garbage-in, with a comment about pre-cleaning XML:

```320:322:grobid-core/src/main/java/org/grobid/core/document/Document.java
        // The XML generated by pdfalto might contains invalid UTF characters due to the "garbage-in" of the PDF,
        // which will result in a "fatal" parsing failure (the joy of XML!). The solution could be to prevent
        // having those characters in the input XML by cleaning it first
```

Regex authors warn about catastrophic backtracking from PDF noise:

```50:50:grobid-core/src/main/java/org/grobid/core/utilities/TextUtilities.java
    // note: be careful of catastrophic backtracking here as a consequence of PDF noise!
```

### 2.3 TextUtilities cleaners (metadata / line level)

`cleanField` trims leading/trailing punctuation and optional stopwords on bibliographic fields:

```455:460:grobid-core/src/main/java/org/grobid/core/utilities/TextUtilities.java
    /**
     * Remove useless punctuation at the end and beginning of a metadata field.
     * <p/>
     * Still experimental ! Use with care !
     */
    public final static String cleanField(String input0, boolean applyStopwordsFilter) {
```

`filterLine` drops empty lines and pdfalto layout markers, not high-entropy text:

```1203:1210:grobid-core/src/main/java/org/grobid/core/utilities/TextUtilities.java
    public static boolean filterLine(String line) {
        boolean filter = false;
        if (StringUtils.isEmpty(line)) {
            filter = true;
        } else if (line.contains("@IMAGE") || line.contains("@PAGE")) {
            filter = true;
        }
        return filter;
```

Used during segmentation feature extraction:

```489:498:grobid-core/src/main/java/org/grobid/core/engines/Segmentation.java
                    // final sanitization and filtering
                    text = text.replaceAll("[ \n\r]", "");
                    text = text.trim();

                    if ((text.length() == 0) ||
                            (TextUtilities.filterLine(line))) {
                        continue;
                    }
```

### 2.4 Domain "garbage" / noise rejection (structured output, not raw text)

Bibliographic references without minimal metadata are rejected as garbage:

```4510:4527:grobid-core/src/main/java/org/grobid/core/data/BiblioItem.java
    /**
     *  Check is the biblio item can be considered as a minimally valid bibliographical reference.
     *  A certain minimal number of core metadata have to be instantiated. Otherwise, the biblio
     *  item can be considered as "garbage" extracted incorrectly.
     */
    public boolean rejectAsReference() {
        ...
        if (!titleSet && !authorSet && url == null && doi == null && halId == null)
            return true;
        else
            return false;
```

Person names without last names are dropped as noise:

```754:774:grobid-core/src/main/java/org/grobid/core/data/Person.java
    /**
     *  Remove invalid/impossible person names (no last names, noise, etc.)
     */
    public static List<Person> sanityCheck(List<Person> persons) {
        ...
        for (Person person : persons) {
            if (StringUtils.isNotBlank(person.getLastName())) {
                result.add(person);
            }
        }
```

Discarded noise tokens are tracked per bibliographic item:

```267:268:grobid-core/src/main/java/org/grobid/core/data/BiblioItem.java
    // All the tokens that are considered noise will be collected here
    private List<String> discardedPieces = new ArrayList<>();
```

### 2.5 Line length as ML feature, not output cap

Line length is scaled into a segmentation feature; it is not a hard truncation of emitted text:

```506:508:grobid-core/src/main/java/org/grobid/core/engines/Segmentation.java
                    //features.lineLength = line.length() / LINESCALE;
                    features.lineLength = featureFactory
                            .linearScaling(line.length(), maxLineLength, LINESCALE);
```

**Grobid verdict:** Rich PDF/OCR noise handling for *scientific structure extraction* (punctuation trim, layout markers, reference/person sanity). No base64, no data-URI, no high-entropy line filter, no markdown-length cap.

---

## 3. camelot (Python, table extraction)

### 3.1 No base64 / entropy / garbage-blob handling

No `base64`, `entropy`, `junk`, or `garbage` matches in `camelot/*.py`. Camelot reads PDF text via PDFMiner/Playa and assigns it to table cells.

### 3.2 Text pass-through with geometry dedup only

`text_in_bbox` keeps PDFMiner objects whose centre lies in a bbox; it deduplicates overlapping siblings by content equality, not by entropy:

```669:679:camelot/utils.py
def text_in_bbox(bbox, text):
    """Return all text objects in a bounding box.

    Keeps every text object whose centre lies inside the bbox (with a
    small pad), then discards each one whose bbox is >80% contained in a
    longer sibling *and* whose stripped text equals that sibling's
    stripped text.
```

Cell text is stripped of newlines only:

```1518:1518:camelot/utils.py
        text = t.get_text().strip("\n")
```

### 3.3 User-configurable strip/replace (not automatic junk detection)

`strip_text` removes caller-specified characters/substrings from cells:

```243:250:camelot/io.py
    strip_text : str or sequence of str, optional (default: '')
        Characters or substrings to strip from each cell before
        assignment. A ``str`` strips per-character — every character in
        the string is removed wherever it appears (e.g. ``" \n"`` drops
        all spaces and newlines). A list/tuple of ``str`` strips whole
        substrings (e.g. ``["[1]", "[2]"]`` removes those footnote
        markers but leaves bare ``[``/``]`` alone).
```

### 3.4 Minimum text length heuristic (table geometry, not content quality)

Text lines shorter than 2 chars are skipped when building alignment edges:

```235:237:camelot/core.py
        for tl in textlines:
            if len(tl.get_text().strip()) > 1:  # TODO: hacky
                self._register_textline(tl)
```

**Camelot verdict:** No blob/base64 policy. Text quality controls are optional `strip_text`/`replace_text` and geometric dedup. Absence of automatic garbage detection is proven by the pass-through `get_text().strip("\n")` path above.

---

## 4. img2table (Python, table extraction from images)

### 4.1 Base64 only for OCR API transport

Google Vision integration base64-encodes page images for the API, not for filtering extracted text:

```27:32:src/img2table/ocr/google_vision.py
        Convert image to base64 string
        ...
        return base64.b64encode(s=buffer).decode("utf-8")  # ty:ignore[invalid-argument-type]
```

### 4.2 `remove_noise` is pixel-level CV, not text-blob filtering

Borderless table layout uses connected-component geometry to drop speckle/dots/dashes from binarized images:

```80:92:src/img2table/tables/borderless/layout/_text_lines.pyx
def remove_noise(
    cnp.ndarray[cnp.int32_t, ndim=2] cc,
    ...
):
    """
    Remove noise from detected connected components
```

Removal criteria are size/density/elongation thresholds on image components:

```111:123:src/img2table/tables/borderless/layout/_text_lines.pyx
        # Check dashes
        is_dash = (w_cc / <double> h_cc >= 2.0) and (0.5 * median_width <= w_cc <= 1.5 * median_width)
        is_dot = _is_dot_component(cc=cc, cc_stats=cc_stats, idx=idx)
        if is_dash or is_dot:
            continue
        ...
        if h_cc < (average_height / 3.0) or density < 0.08 or elongation < 0.08:
            keep_view[idx] = 0
```

Called from the text-line segmentation pipeline:

```128:131:src/img2table/tables/borderless/layout/text_lines.py
    cc_denoised = remove_noise(
        cc=cc.copy(), cc_stats=cc_stats, average_height=average_height, median_width=median_width
    )
```

**img2table verdict:** Image-segmentation noise removal only. No markdown/text blob handling, no data-URI awareness, no emitted-text length caps.

---

## 5. surya (Python, OCR / layout)

### 5.1 Base64 only for model prompt transport

OpenAI-compatible backend wraps crops as `data:image/png;base64,...`:

```44:44:surya/inference/backends/openai_client.py
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"},
```

This is intentional image encoding for inference, not output sanitization.

### 5.2 Skip OCR on figure/image blocks

Layout labels in `SKIP_OCR_LABELS` produce empty/skipped blocks:

```68:68:surya/inference/prompts.py
SKIP_OCR_LABELS = {"Figure", "Image", "Diagram", "Blank-Page"}
```

```8:14:surya/recognition/schema.py
class BlockOCRResult(PolygonBox):
    label: str  # canonicalized layout label (Picture, Text, ...)
    ...
    html: str = ""  # block HTML (BLOCK_PROMPT output, "" if skipped)
    skipped: bool = False  # True if label was in SKIP_OCR_LABELS
```

### 5.3 Blank-region and repeat-loop filters (model output quality)

Blank text regions are dropped after OCR:

```56:63:surya/recognition/__init__.py
    """Drop text-labeled blocks whose source page region is essentially blank.

    Full-page OCR can emit text divs for regions that are visually empty
    (margins, gutter space) — the model hallucinates a paragraph where there
    is none. We crop the region, count near-white pixels, and drop the block
    when the fraction exceeds ``blank_pixel_fraction``.
```

Repeat-loop detection catches stuck decoder output (analogous to our LLM narrating a blob):

```87:94:surya/recognition/__init__.py
    """True iff the tail of ``text`` ends in a repeating sequence.
    ...
    Catches the typical decoder failure mode
    where a page output gets stuck emitting the same div / phrase until it
    hits max_tokens.
```

### 5.4 `clean_block_html`: fence strip only

```113:121:surya/inference/parsers.py
def clean_block_html(html: str) -> str:
    """Light cleanup of model-emitted HTML for a single block.

    Strips code fences, leading/trailing whitespace. Does NOT validate against
    ALLOWED_TAGS — the model is expected to comply, and downstream consumers
    can sanitize further if needed.
    """
    cleaned = _strip_fences(html).strip()
    return cleaned
```

**Surya verdict:** Skips image blocks at OCR time; filters blank/hallucinated text and decoder repetition. No filter for embedded base64 *text* in output. Base64 appears only as input transport to vision models.

---

## 6. PDF-Extract-Kit (Python, multi-task PDF kit)

### 6.1 Base64 only in PaddleOCR image path

```40:42:pdf_extract_kit/tasks/ocr/models/paddle_ocr.py
                    data_base64 = str(base64.b64encode(image_bytes),
                    ...
                    image_decode = base64.b64decode(data_base64)
```

Encode/decode is for image bytes through the OCR pipeline, not for filtering extracted strings.

### 6.2 No garbage / junk / entropy text filters

`findstr /s /i garbage pdf_extract_kit/*.py` returns no matches.

### 6.3 `max_length` is model batch padding, not extraction output cap

LayoutLM collator `max_length` pads transformer inputs:

```40:41:pdf_extract_kit/tasks/layout_detection/models/layoutlmv3_util/layoutlmft/data/data_collator.py
        max_length (:obj:`int`, `optional`):
            Maximum length of the returned list and optionally padding length (see above).
```

**PDF-Extract-Kit verdict:** OCR/layout toolkit. Base64 is internal to image I/O. No post-extraction text blob sanitizer.

---

## Comparative table

| Repo | base64 / data-URI policy | garbage / noise detection | notes | portable idea for whisker chunk filter |
|---|---|---|---|---|
| **pandoc** | Parse/decode on fetch; HTML reader and markdown writer **pass through** `data:` URIs by default; `--extract-media` externalizes to files; `--embed-resources` *creates* data URIs in HTML | None for high-entropy text; unfetchable images → alt-text span | Closest upstream to our blob source; default path emits megabyte `![](data:...)` lines | **Externalize-or-strip data-URI images** before chunking (pandoc `extract-media` / `fillMediaBag` pattern); **placeholder on failure** (`replacementSpan`) |
| **grobid** | No handling | `cleanField`, `filterLine` (@IMAGE/@PAGE), `rejectAsReference`, `Person.sanityCheck`; PDF noise breaks regex | Scientific metadata extraction, not markdown | **Line-level layout marker filter** (`@IMAGE` analogue: drop lines matching `data:image`); **structural sanity gate** before LLM (reject chunk if only blob) |
| **camelot** | No handling | Geometry dedup only; optional `strip_text` | Table cell text pass-through | Low fit; optional **per-line char strip** if user configures patterns |
| **img2table** | Base64 for Vision API input only | CV `remove_noise` on binarized pixels | Image segmentation, not string content | Low fit; **size/density thresholds** inspire pixel pre-filter upstream, not chunk filter |
| **surya** | Base64 for model image transport | Skip Figure/Image OCR; blank-region drop; repeat-loop detect; fence strip | Closest LLM-output hygiene analogue | **Skip OCR on image blocks** (upstream); **repeat-loop detect** on chunk text; **blank/near-empty chunk drop** |
| **PDF-Extract-Kit** | Base64 in PaddleOCR image codec | None in extraction output | ML task kit | No direct pattern; confirms base64 in PDF tools is almost always **image I/O**, not text cleanup |

---

## Portable ideas (ranked for chunk-level markdown filter)

1. **Data-URI line detector + placeholder replace (highest fit).** Match markdown image lines `!\[...\]\(data:[^)]+;base64,[A-Za-z0-9+/=]{N,}\)` (and raw `data:image` lines). Replace with `[embedded image removed: {mime}, {len} chars]` or split chunk boundary. Pandoc proves these are valid, intentional URIs passed through verbatim (`Readers/HTML.hs:1232`, `Writers/Markdown/Inline.hs:717`). Deterministic regex + length floor (e.g. N > 10_000).

2. **Single-line length cap (high fit).** If one markdown line exceeds K chars (P2728 largest line ≈ 1.1M), truncate or replace. None of these repos cap emitted text nodes; this is a gap we fill. Pair with data-URI rule since our blobs are single-line.

3. **Base64-alphabet ratio heuristic (medium fit).** For lines > L, if ≥95% of non-whitespace chars match `[A-Za-z0-9+/=]`, classify as blob. No repo uses entropy, but grobid's noise model is structural not statistical; a simple ratio is cheap and deterministic.

4. **Chunk skip with honest review flag (medium fit).** Surya skips `Figure`/`Image` blocks (`SKIP_OCR_LABELS`); pandoc substitutes alt text on fetch failure. If a chunk is >X% blob after stripping, emit sidecar `chunk_skipped: embedded_media` instead of sending to LLM.

5. **Repeat-loop tail detect on LLM-bound chunks (lower fit, post-strip).** Port surya `_detect_repeat_loop` (`recognition/__init__.py:81-108`) as a secondary guard if a partially-cleaned chunk still causes the model to narrate garbage until `max_tokens`.

---

## Cross-cutting conclusion

None of the six repos implement the specific filter we need: **deterministic removal or skipping of megabyte `data:image;base64` markdown lines before LLM chunking**. Pandoc is the reference for data-URI lifecycle (pass-through by default, externalize on `--extract-media`). Grobid and surya offer adjacent patterns (layout-marker line filter, block skip, repeat-loop detect). Table/OCR kits (camelot, img2table, PDF-Extract-Kit) treat text as pass-through or operate on pixels; their `base64` usage is image transport only.

For whisker `chunking.py`, the highest-value import is pandoc's **externalize-or-placeholder** split combined with a **hard per-line length ceiling**, applied before the tapetum LLM call.
