# Base64 / garbage-blob handling in doc-AI pipelines

Research date: 2026-07-07. Local clones under `packages/whisker/research/repos/`.

**Scope:** How docling, unstructured, and markitdown handle embedded binary (base64 / data URIs), noise/garbage text, and chunk-level filtering before LLM consumption.

**Whisker context:** P2728R11/R12 markdown contains a giant undecodable base64-like blob that survives `tomd` conversion and chokes `tapetum_llm` chunking. This report informs a possible chunk-layer filter.

---

## Executive summary

| Repo | Binary in markdown output | Garbage-text detection | Chunk-level blob filter |
|------|----------------------------|------------------------|-------------------------|
| **docling** | Configurable: placeholder by default at ingest; CLI markdown export defaults to embedded base64 | No entropy/gibberish filter; Unicode cleanup + VLM JSON salvage only | Token caps only; optional `![IMAGE]` placeholder, no blob strip |
| **markitdown** | **Default strips data-URI payload** to `data:image/png;base64...` | No gibberish/entropy filter | No chunking stage |
| **unstructured** | Base64 in **metadata** (`image_base64`), not inline text by default | Partition heuristics (alpha ratio, English words); **no** base64-blob detector | Token/char caps with whitespace split; **no** content filtering |

None of the three projects implements a general “long high-entropy alphanumeric run” filter on markdown body text. Closest portable patterns: markitdown’s data-URI truncation, docling’s byte cap + reject-on-load, unstructured’s opt-in metadata stripping at chunk consolidation.

---

## 1. Docling

### 1.1 Embedded binary / base64 policy

**Ingest: images not fetched by default (placeholder, no bytes).**

When `fetch_images` is false (the default for HTML and Markdown backends), HTML images become structure-only placeholders with no decoded payload:

```4430:4438:docling/docling/backend/html_backend.py
        if not cast(HTMLBackendOptions, self.options).fetch_images or not src_loc:
            # Do not fetch the image, just add a placeholder
            placeholder: PictureItem = doc.add_picture(
                caption=caption_item,
                parent=parent,
                content_layer=self.content_layer,
                prov=pic_prov,
            )
            return placeholder.get_ref()
```

Defaults are explicit:

```73:78:docling/docling/datamodel/backend_options.py
    fetch_images: bool = Field(
        False,
        description=(
            "Whether the backend should access remote or local resources to parse "
            "images in an HTML document."
        ),
```

```105:108:docling/docling/datamodel/backend_options.py
    max_image_data_base64_bytes: PositiveInt = Field(
        20 * 1024 * 1024,  # 20 MB
        description="The maximum number of base64 data bytes that the backend will accept.",
    )
```

**When fetch is enabled: decode data URIs with a 20 MB cap; oversize raises `ValueError`.**

Shared loader used by HTML and Markdown backends:

```248:255:docling/docling/backend/utils/image_resource_loader.py
        elif src_loc.startswith("data:"):
            encoded_data = re.sub(r"^data:image/.+;base64,", "", src_loc)
            decoded_data = base64.b64decode(encoded_data)

            if len(decoded_data) > self.max_image_data_base64_bytes:
                raise ValueError(
                    f"Decoded image exceeds size limit of {self.max_image_data_base64_bytes} bytes."
                )
```

Markdown backend delegates to the same loader and returns `None` when fetch is off:

```661:667:docling/docling/backend/md_backend.py
        md_options = cast(MarkdownBackendOptions, self.options)
        if not md_options.fetch_images or not dest:
            return None
        base_path = (
            str(md_options.source_uri) if md_options.source_uri is not None else None
        )
        return self._get_image_loader().load_image_ref(dest, base_path)
```

Tests lock in: default skips decode; cap rejects oversize with warning and `image is None`:

```220:222:docling/tests/test_backend_markdown.py
def test_convert_embedded_base64_image_disabled_by_default():
    """Without fetch_images the picture stays a placeholder (default behavior)."""
    markdown = f"# Title\n\n![alt]({_png_data_uri(7, 5)})\n"
```

```234:248:docling/tests/test_backend_markdown.py
def test_convert_embedded_base64_image_enforces_size_limit():
    """Decoded base64 images larger than the configured cap are rejected."""
    ...
    with pytest.warns(UserWarning, match="exceeds size limit"):
        doc = _convert_markdown(
            markdown,
            MarkdownBackendOptions(fetch_images=True, max_image_data_base64_bytes=8),
        )
    ...
    assert pictures[0].image is None
```

**Export: CLI defaults to embedding base64 in Markdown output.**

`ImageRefMode.EMBEDDED` is the CLI default for image-capable formats (including Markdown):

```676:682:docling/docling/cli/main.py
    image_export_mode: Annotated[
        ImageRefMode,
        typer.Option(
            ...,
            help="Image export mode for image-capable document outputs (JSON, YAML, HTML, HTML split-page, and Markdown). Text, DocTags, and WebVTT outputs do not export images. With `placeholder`, only the position of the image is marked in the output. In `embedded` mode, the image is embedded as base64 encoded string. In `referenced` mode, the image is exported in PNG format and referenced from the main exported document.",
        ),
    ] = ImageRefMode.EMBEDDED,
```

Placeholder mode suppresses image generation for formats that do not support embedding:

```20:26:docling/docling/cli/export_utils.py
def _should_generate_export_images(
    image_export_mode: ImageRefMode,
    to_formats: list[OutputFormat],
) -> bool:
    return image_export_mode != ImageRefMode.PLACEHOLDER and any(
        to_format not in _OUTPUT_FORMATS_NOT_SUPPORTING_IMAGE_EMBEDDING
        for to_format in to_formats
    )
```

**Email attachments: binary payload never emitted** (only headers/body text extracted; test proves pass-through exclusion):

```59:60:docling/tests/test_backend_email.py
def test_email_with_attachment_excludes_encoded_content():
    """Test that base64-encoded attachment content is not included in the converted document."""
```

```80:84:docling/tests/test_backend_email.py
    # Verify base64-encoded attachment content is NOT in the document
    assert (
        "VGhpcyBpcyBhIHRlc3QgYXR0YWNobWVudCBmaWxlLgpJdCBjb250YWlucyBzb21lIGR1bW15IGNv"
        not in markdown
    )
```

The email backend itself only adds subject/from/to/date/body paragraphs (`docling/docling/backend/email_backend.py:144-176`); attachments are never iterated.

### 1.2 Garbage / noise text detection

**No entropy, gibberish, or dictionary-ratio filter on document text.**

Closest behaviors:

- **Unicode sanitization** in HTML text extraction (formatting chars, not binary blobs):

```4535:4540:docling/docling/backend/html_backend.py
    def _clean_unicode(text: str) -> str:
        """Replace typical Unicode characters in HTML for text processing.

        Several Unicode characters (e.g., non-printable or formatting) are typically
        found in HTML but are worth replacing to sanitize text and ensure consistency
        in text processing tasks.
```

- **VLM JSON salvage** (`_clean_json`): strips leading garbage before `[`, closes truncated arrays; unrelated to base64 body text:

```58:64:docling/docling/utils/dots_utils.py
def _clean_json(raw: str) -> str:
    """Best-effort cleanup of potentially truncated JSON arrays.

    1. Strip leading text before the first ``[``.
    2. If the array does not end with ``]``, find the last ``}`` and append ``]``.
    3. Return ``"[]"`` if no valid JSON structure found.
```

### 1.3 Chunking for LLM consumption

Chunking lives in `docling_core` (imported, not vendored here). Docling exposes **HybridChunker** / **HierarchicalChunker** via CLI and service API with **token limits**, not content filters:

```72:77:docling/docling/datamodel/service/chunking.py
    max_tokens: Annotated[
        Optional[int],
        Field(
            description="Maximum number of tokens per chunk. When left to none, the value is automatically extracted from the tokenizer.",
        ),
    ] = None
```

Image serialization in chunks is **off by default**; placeholder string is configurable:

```32:51:docling/docling/datamodel/service/chunking.py
    use_markdown_images: Annotated[
        bool,
        Field(
            description=(
                "Enable image serialization and image references inside chunks. "
                "Also adds a `has_image` field to chunk metadata to make image-containing "
                "chunks easier to identify."
            ),
        ),
    ] = False
    ...
    ] = "![IMAGE]"
```

CLI export writes contextualized chunk text with optional `num_tokens`; no pre-LLM blob stripping:

```538:548:docling/docling/cli/main.py
                        contextualized = chunker_obj.contextualize(doc_chunk)
                        num_tokens: int | None = None
                        if isinstance(chunker_obj, HybridChunker):
                            num_tokens = chunker_obj.tokenizer.count_tokens(
                                contextualized
                            )
                        chunk_record = ChunkedDocumentResultItem(
                            filename=doc_filename,
                            chunk_index=i,
                            text=contextualized,
```

### 1.4 Explicit base64 mentions

- Loader + tests: `docling/docling/backend/utils/image_resource_loader.py:248-255`, `docling/tests/test_backend_html.py:1045-1065`
- Service datamodel: `docling/tests/test_service_datamodels.py:70` (`"base64_string": "ZmFrZQ=="`)
- KServe binary tensors (inference transport, not document text): `docling/tests/test_kserve_v2_binary.py`

### 1.5 Failure / fallback on unparseable binary

- Oversize or invalid image: warn and `return None` from `create_image_ref` (`image_resource_loader.py:169-179`)
- Oversize data URI: `ValueError` (`image_resource_loader.py:252-255`)
- fetch disabled: placeholder picture, no bytes (`html_backend.py:4430-4438`)

**Pass-through gap:** Raw base64-like text that is already plain markdown (not `data:` URIs, not `PictureItem`) is not filtered anywhere in docling.

---

## 2. Markitdown

### 2.1 Embedded binary / data-URI policy

**Default: truncate data-URI payloads in HTML→Markdown** (keep MIME prefix + `...`).

Documented in converter class:

```8:16:markitdown/packages/markitdown/src/markitdown/converters/_markdownify.py
class _CustomMarkdownify(markdownify.MarkdownConverter):
    """
    A custom version of markdownify's MarkdownConverter. Changes include:

    - Altering the default heading style to use '#', '##', etc.
    - Removing javascript hyperlinks.
    - Truncating images with large data:uri sources.
    - Ensuring URIs are properly escaped, and do not conflict with Markdown syntax
    """
```

Implementation:

```106:108:markitdown/packages/markitdown/src/markitdown/converters/_markdownify.py
        # Remove dataURIs
        if src.startswith("data:") and not self.options["keep_data_uris"]:
            src = src.split(",")[0] + "..."
```

Default `keep_data_uris=False`:

```18:21:markitdown/packages/markitdown/src/markitdown/converters/_markdownify.py
    def __init__(self, **options: Any):
        options["heading_style"] = options.get("heading_style", markdownify.ATX)
        options["keep_data_uris"] = options.get("keep_data_uris", False)
```

CLI/docstring:

```135:138:markitdown/packages/markitdown/src/markitdown/__main__.py
    parser.add_argument(
        "--keep-data-uris",
        action="store_true",
        help="Keep data URIs (like base64-encoded images) in the output. By default, data URIs are truncated.",
```

**Regression vectors:** default output must include truncated form and must **not** include full payload prefix:

```28:32:markitdown/packages/markitdown/tests/_test_vectors.py
            "data:image/png;base64...",
        ],
        must_not_include=[
            "data:image/png;base64,iVBORw0KGgoAAAANSU",
        ],
```

**PPTX:** without `keep_data_uris`, emit filename placeholder instead of inline base64:

```143:152:markitdown/packages/markitdown/src/markitdown/converters/_pptx_converter.py
                    # If keep_data_uris is True, use base64 encoding for images
                    if kwargs.get("keep_data_uris", False):
                        blob = shape.image.blob
                        content_type = shape.image.content_type or "image/png"
                        b64_string = base64.b64encode(blob).decode("utf-8")
                        md_content += f"\n![{alt_text}](data:{content_type};base64,{b64_string})\n"
                    else:
                        # A placeholder name
                        filename = re.sub(r"\W", "", shape.name) + ".jpg"
                        md_content += "\n![" + alt_text + "](" + filename + ")\n"
```

**Input path:** `data:` URIs are decoded for conversion (not truncated at parse):

```19:50:markitdown/packages/markitdown/src/markitdown/_uri_utils.py
def parse_data_uri(uri: str) -> Tuple[str | None, Dict[str, str], bytes]:
    if not uri.startswith("data:"):
        raise ValueError("Not a data URI")
    ...
    content = base64.b64decode(data) if is_base64 else unquote_to_bytes(data)
```

**Image→LLM caption path** intentionally embeds full base64 in API payload (not markdown output):

```117:129:markitdown/packages/markitdown/src/markitdown/converters/_image_converter.py
        data_uri = f"data:{content_type};base64,{base64_image}"
        ...
                        "image_url": {
                            "url": data_uri,
                        },
```

### 2.2 Garbage / noise text detection

**None.** HTML converter removes `<script>` / `<style>` only (`_html_converter.py:56-58`). No entropy or printable-ratio checks on body text.

### 2.3 Chunking

Markitdown is a **single-shot converter**; no chunking or pre-LLM filter stage.

### 2.4 Failure / fallback

Deeply nested HTML: RecursionError → warn and fall back to `get_text()` (`_html_converter.py:68-77`). No handling for undecodable binary in plain text.

**Pass-through gap:** Raw base64 runs in markdown/plain text (not in `![...](data:...)` ) pass through unchanged.

---

## 3. Unstructured

### 3.1 Embedded binary / base64 policy

**Partitioning:** images optionally stored as **metadata** `image_base64`, not inline narrative text, only when `extract_image_block_to_payload=True`:

```123:127:unstructured/unstructured/partition/auto.py
    extract_image_block_to_payload
        Only applicable if `strategy=hi_res`.
        If True, images of the element type(s) defined in 'extract_image_block_types' will be
        encoded as base64 data and stored in two metadata fields: 'image_base64' and
        'image_mime_type'.
```

**HTML re-export:** inline data URI only when metadata present and not excluded:

```94:100:unstructured/unstructured/partition/html/convert.py
    def _inject_html_element_content(self, element_html: Tag, **kwargs: Any) -> None:
        exclude_binary_image_data = kwargs.get("exclude_binary_image_data", False)
        if self.element.metadata.image_base64 and not exclude_binary_image_data:
            image_mime_type = self.element.metadata.image_mime_type or "image/png"
            element_html["src"] = (
                f"data:{image_mime_type};base64,{self.element.metadata.image_base64}"
            )
```

**Default strip on partition:** unless image extraction to payload is requested:

```239:242:unstructured/unstructured/partition/html/partition.py
            # -- remove <image_base64> if not requested --
            if not self._should_include_image_base64(e):
                e.metadata.image_base64 = None
                e.metadata.image_mime_type = None
```

**Chunk consolidation drops binary from chunk metadata:**

```543:544:unstructured/unstructured/documents/elements.py
            "image_base64": cls.DROP,
            "image_mime_type": cls.DROP,
```

**Pass-through:** Element `.text` from PDF/HTML extraction is not scanned for embedded base64 blobs. Test `fake-html-with-base64-image.html` validates **metadata extraction**, not inline blob removal (`test_unstructured/partition/test_auto.py:634-644`).

### 3.2 Garbage / noise text detection

**Cleaners** (`unstructured/cleaners/core.py`): whitespace, bullets, dashes, ligatures, `clean_non_ascii_chars` (ASCII transliteration). **No entropy or base64 detection.**

**Partition typing heuristics** (`partition/text_type.py`): reject narrative/title candidates via:

- `under_non_alpha_ratio` — low alphabetic character proportion:

```241:265:unstructured/unstructured/partition/text_type.py
def under_non_alpha_ratio(text: str, threshold: float = 0.5):
    """Checks if the proportion of non-alpha characters in the text snippet exceeds a given
    threshold. This helps prevent text like "-----------BREAK---------" from being tagged
    as a title or narrative text. The ratio does not count spaces.
    ...
    return ((alpha_count / total_count) < threshold) if total_count > 0 else False
```

- `exceeds_cap_ratio`, `contains_english_word`, verb checks for narrative classification (`text_type.py:27-88`).

These affect **element typing**, not removal. Base64-like strings (high alphabetic ratio) would **pass** `under_non_alpha_ratio`.

PDF path uses `clean_extra_whitespace_with_index_run` for layout coordinates (`partition/pdf.py:22-25`), not blob stripping.

### 3.3 Chunking for LLM consumption

**Hard caps:** default 500 chars if unset; optional `max_tokens` via tiktoken:

```33:39:unstructured/unstructured/chunking/base.py
CHUNK_MAX_CHARS_DEFAULT: int = 500
"""Hard-max chunk-length when no explicit value specified in `max_characters` argument.
...
Only `ChunkingOptions.max_characters` should apply a default value.
```

**Oversized element text:** split on separators, then binary-search whitespace boundary for token limits — **no content-type filter**:

```1496:1520:unstructured/unstructured/chunking/base.py
        # -- fallback: split on whitespace boundary using binary search to find token limit --
        ...
        while low <= high:
            mid = (low + high) // 2
            if measure(s[:mid]) <= maxlen:
                best_pos = mid
                low = mid + 1
```

A multi-megabyte base64 blob without whitespace would remain a **single chunk** until token split mid-string (still sending garbage to downstream).

### 3.4 Explicit base64 mentions

- Metadata: `elements.py:183`, staging gzip round-trip `elements.py:373-451`
- Tests: `test_unstructured/partition/test_api.py:195-197`, `partition/html/test_convert.py:275-281`

### 3.5 Failure / fallback

No dedicated “undecodable binary in text” path. Garbage PDF layout noted in comment only:

```627:627:unstructured/unstructured/partition/pdf.py
    that would be extremely slow or produce garbage results with PDFMiner text extraction.
```

---

## 4. Comparative table

| Repo | Embedded-binary policy | Garbage-text detection | Chunk-level filtering | Portable idea for whisker |
|------|------------------------|------------------------|----------------------|---------------------------|
| **docling** | Ingest: no fetch → placeholder; fetch → decode with 20 MB cap. Export CLI: default **embed** base64 in MD | Unicode cleanup; VLM JSON trim only | `max_tokens`; `use_markdown_images=False` → `![IMAGE]`; no blob strip | Cap + reject at load; placeholder export mode; chunk image placeholder string |
| **markitdown** | Default **truncate** `data:` URIs to `data:...;base64...`; opt-in `--keep-data-uris` | None (drop script/style) | N/A (no chunker) | **Truncate/replace** `data:` image URLs in markdown (proven test vectors) |
| **unstructured** | Base64 in **metadata** only when opted in; stripped from chunks (`DROP`) | Alpha ratio / English / caps for **classification** only | Char/token max + whitespace split; metadata binary dropped | Drop binary metadata before chunk text; optional alpha-ratio skip for narrative (weak for base64) |

---

## 5. Portable ideas for whisker `tapetum_llm` chunk filter

Ranked by fit (pure Python, deterministic, no new deps):

1. **Markitdown-style data-URI truncation on markdown chunks** — Regex/lines matching `![...](data:...;base64,...)` or bare `data:*;base64,` runs: replace payload with `[binary data omitted, N chars]`. Directly mirrors `_markdownify.py:107-108` and `_test_vectors.py:28-32`. Handles structured data URIs; **not** raw P2728 blobs unless they match URI shape.

2. **Docling-style byte/character cap with placeholder** — Before LLM: if a chunk (or line) exceeds `MAX_BLOB_CHARS` (e.g. 8–32 KiB) and matches `[A-Za-z0-9+/=\s]{MIN_LEN,}` with low whitespace ratio, replace entire run with `[omitted N-byte encoded blob]`. Mirrors `max_image_data_base64_bytes` + reject/placeholder pattern (`image_resource_loader.py:252-255`, `html_backend.py:4431-4432`).

3. **Line-level high-entropy gate (deterministic heuristic)** — For each line: if `len(line) > L` and `unique_chars/len < 0.15` and `sum(c.isalnum() for c in line)/len > 0.95`, treat as blob. No Shannon entropy needed; similar spirit to unstructured’s ratio checks but inverted for “too uniform.” Catches raw P2728-style garbage; tune thresholds on golden papers.

4. **Chunk token budget pre-check** — Like unstructured/docling chunkers: if chunk char count > threshold, scan for longest alnum run and replace before send. Prevents max_tokens burn even when H2 split lands inside a blob.

5. **Unstructured-style metadata separation (preventive)** — If `tomd` ever emits images as metadata side channels, keep binary out of `.text` and drop on consolidate (`elements.py:543-544`). Lower priority for current P2728 issue (blob is inline markdown text).

---

## 6. Gap analysis for P2728R11/R12

- **Problem shape:** Undecodable base64-**like** text inline in markdown body, not necessarily a well-formed `data:` image URL.
- **Best upstream fix:** Strip/cap in `tomd` conversion (markitdown/docling both act at conversion, not chunk QA).
- **Best chunk-layer fix:** Idea **#2 + #3** combined: detect long uniform alnum runs, replace with fixed placeholder, log original length for trace/debug.
- **None of the three repos** implements that exact filter; markitdown is the closest precedent for **deterministic truncation** with tested golden vectors.

---

## 7. Sources searched

Terms: `base64`, `data:`, `entropy`, `gibberish`, `garbage`, `printable`, `clean`, `noise`, `placeholder`, `binary`, `chunk`, `truncat` across `docling/`, `unstructured/unstructured/`, `markitdown/packages/`.
