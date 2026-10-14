# Research: base64 / garbage-blob handling in LLM-ready markdown pipelines

**Scope:** Local clones of [firecrawl](https://github.com/mendableai/firecrawl), [mdream](https://github.com/harlan-zw/mdream), and [langextract](https://github.com/google/langextract).  
**Question:** How do these projects detect, strip, cap, or skip base64 blobs, data URIs, and high-entropy garbage before or during chunking for LLM consumption?

---

## 1. Firecrawl

Firecrawl is a web-scrape-to-markdown API. Garbage handling is split across **HTML pre-processing**, **markdown conversion**, and a **late markdown post-pass**. There is no entropy detector.

### 1.1 `removeBase64Images` (markdown post-pass, default ON)

API default and documented intent:

```521:521:apps/api/src/controllers/v1/types.ts
  removeBase64Images: z.boolean().prefault(true),
```

```2538:2541:apps/api/openapi.json
          "removeBase64Images": {
            "type": "boolean",
            "description": "Removes all base 64 images from the output, which may be overwhelmingly long. The image's alt text remains in the output, but the URL is replaced with a placeholder."
          },
```

Implementation is a **single regex** on finished markdown, run late in the transformer stack (after LLM extract/summary steps):

```4:13:apps/api/src/scraper/scrapeURL/transformers/removeBase64Images.ts
const regex = /(!\[.*?\])\(data:image\/.*?;base64,.*?\)/g;

export function removeBase64Images(meta: Meta, document: Document): Document {
  if (meta.options.removeBase64Images && document.markdown !== undefined) {
    document.markdown = document.markdown.replace(
      regex,
      "$1(<Base64-Image-Removed>)",
    );
  }
  return document;
}
```

```632:632:apps/api/src/scraper/scrapeURL/transformers/index.ts
  removeBase64Images,
```

**Limits:** Only matches markdown image syntax `![alt](data:image/...;base64,...)`. Raw base64 text blocks, non-image `data:` schemes, or bare garbage strings are untouched.

E2E test exists but the assertion is commented out with a TODO:

```431:450:apps/api/src/__tests__/e2e_v1_withAuth_all_params/index.test.ts
    "should handle 'removeBase64Images' parameter correctly",
    async () => {
      const scrapeRequest = {
        url: E2E_TEST_SERVER_URL,
        removeBase64Images: true,
      } as ScrapeRequest;
      // ...
      // - TODO: not working for every image
      // expect(response.body.data.markdown).toContain("Image-Removed");
```

### 1.2 HTML stripping before markdown (script / style / noscript)

Before `html-to-markdown`, Rust `transform_html` detaches entire subtrees:

```442:456:apps/api/native/src/html.rs
  while let Ok(x) = document.select_first("head") {
    x.as_node().detach();
  }
  while let Ok(x) = document.select_first("meta") {
    x.as_node().detach();
  }
  while let Ok(x) = document.select_first("noscript") {
    x.as_node().detach();
  }
  while let Ok(x) = document.select_first("style") {
    x.as_node().detach();
  }
  while let Ok(x) = document.select_first("script") {
    x.as_node().detach();
  }
```

This prevents giant inline JS/CSS from entering markdown, but **does not** remove inline `data:` attributes on surviving elements (e.g. `<img src="data:image/...">`).

### 1.3 Markdown conversion and `postProcessMarkdown`

Conversion path: Go `html-to-markdown` (or Turndown fallback) then Rust `post_process_markdown`:

```78:78:apps/api/src/lib/html-to-markdown.ts
      markdownContent = await postProcessMarkdown(markdownContent);
```

`post_process_markdown` only fixes multi-line link syntax and removes "Skip to Content" links. No blob filtering:

```959:961:apps/api/native/src/html.rs
/// Process multi-line links in markdown.
#[napi]
pub async fn post_process_markdown(markdown: String) -> napi::Result<String> {
```

### 1.4 Image extraction keeps `data:` and `blob:` URLs

Separate from markdown emission; image list API **passes through** data URIs:

```789:792:apps/api/native/src/html.rs
    if src.starts_with("data:") || src.starts_with("blob:") {
      return Ok(src.to_string());
    }
```

```938:938:apps/api/native/src/html.rs
    .filter(|url| url.starts_with("data:") || url.starts_with("blob:") || Url::parse(url).is_ok())
```

### 1.5 LLM content-size caps (`trimToTokenLimit`)

Optional `onlyCleanContent` LLM pass pre-trims markdown before tiktoken encode. Rationale: avoid event-loop freeze on huge strings:

```162:177:apps/api/src/scraper/scrapeURL/transformers/llmExtract.ts
// Generous upper bound on the number of characters a single token can represent.
// ...
// Without this cap, encoding an unbounded multi-megabyte string
// can block the event loop for tens of seconds.
const MAX_CHARS_PER_TOKEN = 5;

export function trimToTokenLimit(
  text: string,
  maxTokens: number,
```

Used at 120000-token budget for clean-content; skips cleaning entirely if still over model output limit:

```1152:1163:apps/api/src/scraper/scrapeURL/transformers/llmExtract.ts
  const trimOutput = trimToTokenLimit(
    document.markdown,
    120000,
    "gpt-4o-mini",
    document.warning,
  );
  // ...
  if (trimOutput.numTokens > modelLimits.maxOutputTokens) {
    const skipWarning = `Content cleaning was skipped because the content is too long (${trimOutput.numTokens} tokens) for the model to return in full (max output: ${modelLimits.maxOutputTokens} tokens). The original markdown has been preserved.`;
```

This is a **head truncate for LLM cleaning**, not a semantic blob filter.

### 1.6 PDF base64 (orthogonal path)

When `parsePDF: false`, PDF bytes stay base64 in output (documented in OpenAPI). Not markdown garbage, but shows base64 is sometimes intentional:

```2341:2341:apps/api/openapi.json
            "description": "Controls how PDF files are processed during scraping. When true, the PDF content is extracted and converted to markdown format, with billing based on the number of pages (1 credit per page). When false, the PDF file is returned in base64 encoding with a flat rate of 1 credit total.",
```

---

## 2. Mdream

Mdream optimizes HTML→markdown for **token cost**. It drops non-visible HTML at parse time and cleans markdown links post-conversion. **No base64-specific or entropy-based filter** exists.

### 2.1 Parse-time exclusion: script, style, template (pass-through proof for rawtext)

`<script>` and `<style>` set `excludes_text_nodes: true`; their body never reaches markdown:

```54:55:crates/core/src/tags.rs
    t[TAG_SCRIPT as usize] = Some(TagHandler { excludes_text_nodes: true, is_non_nesting: true, ..NONE });
    t[TAG_STYLE as usize] = Some(TagHandler { is_non_nesting: true, excludes_text_nodes: true, ..NONE });
```

```354:359:crates/core/src/convert/mod.rs
                // Rawtext (<script>/<style>) content. Its text is excluded
                // from output, so bulk-scan it here instead of routing every
                // byte through the general path, while tracking JS/CSS string
                // literals so a `</script>` inside a string stays literal text
                // (issue #93). The fast path above never fires in non-nesting
                // mode, so all script/style bytes reach this branch.
```

`<svg>` is a block element **without** `excludes_text_nodes`; inline SVG path data can still appear in markdown output:

```164:164:crates/core/src/tags.rs
    t[TAG_SVG as usize] = Some(BLOCK_NO_SPACING);
```

**No `base64`, `data:`, or `blob:` string appears anywhere in `crates/core/`** (repo search). Data-URI handling is only in post-conversion clean helpers.

### 2.2 Post-markdown `cleanEmptyLinks`: strip `data:` link targets, keep text

```210:214:packages/js/src/clean.ts
        if (url === '#' || url.startsWith('javascript:') || url.startsWith('data:') || url.startsWith('vbscript:')) {
          result += link.text
          i = link.end
          continue
        }
```

Enabled by default when `minimal: true` or `clean: true`:

```27:27:packages/js/src/clean.ts
    return { urls: true, fragments: true, emptyLinks: true, redundantLinks: true, selfLinkHeadings: true, emptyImages: true, emptyLinkText: true }
```

**Effect:** `[caption](data:image/png;base64,AAAA...)` becomes plain `caption`. Does not handle bare blob paragraphs or fenced code full of base64.

### 2.3 Post-markdown `cleanEmptyImages`: drop `![]()` entirely

```343:357:packages/js/src/clean.ts
        if (alt.length === 0) {
          // Empty alt — find the (url) part and skip the whole thing
          j++ // skip ]
          if (j < len && md.charCodeAt(j) === 40 /* ( */) {
            // ... skip to closing paren ...
            i = j
            continue
          }
        }
```

Decorative/tracking pixels with empty alt are removed wholesale. A data-URI image **with** alt text is kept (URL intact unless `emptyLinks` also runs on links, not images).

### 2.4 Minimal preset: structural filter, not blob filter

Default exclude list removes chrome elements, not binary payloads:

```83:84:packages/mdream/src/index.ts
const MINIMAL_FILTER_EXCLUDE = ['form', 'fieldset', 'object', 'embed', 'footer', 'aside', 'iframe', 'input', 'textarea', 'select', 'button', 'nav'] as const
const MINIMAL_FILTER_DEFAULT = { exclude: MINIMAL_FILTER_EXCLUDE as unknown as string[] }
```

### 2.5 Markdown splitter size caps (structural, not sanity)

LangChain-compatible splitter defaults; splits on headers, not content quality:

```13:16:crates/core/src/splitter.rs
    /// Maximum chunk size in characters.
    pub chunk_size: usize,
    /// Overlap between chunks for context preservation.
    pub chunk_overlap: usize,
```

```25:26:crates/core/src/splitter.rs
            chunk_size: 1000,
            chunk_overlap: 200,
```

### 2.6 Build-time base64 only (not content policy)

WASM inlining for distribution; unrelated to document blobs:

```54:56:packages/mdream/build.config.ts
// Inline WASM binary (base64)
var _wasmBase64="${wasmBase64}";
function _decodeBase64(s){var e=atob(s),n=e.length,a=new Uint8Array(n);for(var i=0;i<n;i++)a[i]=e.charCodeAt(i);return a.buffer}
```

---

## 3. Langextract

Langextract chunks text for LLM extraction using **sentence boundaries and a character buffer**. It assumes input is natural language. **No base64, data-URI, entropy, or garbage detection.**

### 3.1 `max_char_buffer` chunking (default 200 chars)

```213:234:langextract/annotation.py
      max_char_buffer: int = 200,
      batch_length: int = 1,
      # ...
      max_char_buffer: Max number of characters that we can run inference on.
        The text will be broken into chunks up to this length.
```

`ChunkIterator` docstring: oversized single token becomes an entire chunk (antidisestablishmentarianism case). A megabyte base64 line would land in one chunk:

```366:373:langextract/chunking.py
  B)
  If a single token exceeds the max char buffer, it comprises the whole chunk.
  Consider the sentence:
  "This is antidisestablishmentarianism."
  With max_char_buffer=20, the chunks are:
  * "This is" len=7
  * "antidisestablishmentarianism" len=28
```

### 3.2 `_sanitize`: whitespace only

```246:262:langextract/chunking.py
def _sanitize(text: str) -> str:
  """Converts all whitespace characters in input text to a single space.
  # ...
  sanitized_text = re.sub(r"\s+", " ", text.strip())
  if not sanitized_text:
    raise ValueError("Sanitized text is empty.")
  return sanitized_text
```

No tests reference `sanitized_chunk_text`, base64, or garbage (`tests/chunking_test.py`, `tests/annotation_test.py` cover sentence splits and buffer sizes only).

### 3.3 Explicit pass-through finding

Repo search in `langextract/` (excluding `.venv`) finds **zero** mentions of `base64`, `data:image`, `entropy`, or `garbage` in chunking or annotation code. Input text flows unchanged into `ChunkIterator` except whitespace normalization on the `sanitized_chunk_text` property.

---

## 4. Comparative table

| Repo | data-URI / base64 policy | Size caps | Rationale documented | Portable idea for whisker chunk filter |
|------|--------------------------|-----------|----------------------|----------------------------------------|
| **firecrawl** | Default-on regex replaces `![...](data:image/...;base64,...)` → `![...](<Base64-Image-Removed>)`; HTML strips script/style/noscript; `data:`/`blob:` kept in image-extraction API | `trimToTokenLimit` pre-trims to `maxTokens * 5` chars before tiktoken; 120k token cap for LLM clean | OpenAPI: base64 images "may be overwhelmingly long"; tiktoken comment: huge strings freeze event loop | Late markdown regex on `data:image/...;base64` image syntax; placeholder preserves alt text |
| **mdream** | Parse-time drop script/style/template; post-md `cleanEmptyLinks` unwraps `data:`/`javascript:` links to text; `cleanEmptyImages` drops `![]()` | Splitter `chunk_size=1000`, `chunk_overlap=200` (header-based) | README: "token optimizer"; clean.ts: "meaningless hrefs" | Unwrap or drop markdown links/images with `data:`/`blob:` targets; drop empty-alt images |
| **langextract** | **None** (pass-through) | `max_char_buffer` (default 200); single huge token = one chunk | Docstring explains buffer for inference limits, not content quality | Hard per-chunk char ceiling; split oversized tokens at newlines if possible |

---

## 5. Portable ideas (ranked for whisker `tapetum_llm` chunk-level filter)

1. **Firecrawl-style markdown image placeholder (highest fit)**  
   After H2 chunk assembly, run a deterministic regex (or line scanner) on `![...](data:...;base64,...)` and replace the URL with a short placeholder like `<base64-image-removed>`, keeping alt text. Matches P2728 failure mode (LLM describing garbage in image markdown). Pure Python `re`, no deps.

2. **Mdream `cleanEmptyLinks` / `cleanEmptyImages` port (high fit)**  
   Character-scan markdown (no regex on full doc): unwrap `[text](data:...)` → `text`; drop `![](data:...)` when alt empty. Handles links; combine with (1) for images with alt.

3. **Per-chunk character budget with blob-aware split (high fit)**  
   Langextract's `max_char_buffer` plus firecrawl's pre-trim: if a chunk (or paragraph within chunk) exceeds N chars and matches base64 alphabet density or `data:` prefix, replace the span with a one-line placeholder before LLM call. Deterministic, fits existing H2 chunking in `chunking.py`.

4. **Long-line / high-alphabet run detector (medium fit)**  
   None of the three repos do entropy checks. For WG21 PDF debris (bare base64 paragraphs), detect lines > L chars where >90% of chars match `[A-Za-z0-9+/=]{min_len,}` and substitute `[embedded binary data removed, N chars]`. Simple counting, no scipy.

5. **Upstream HTML/script exclusion (lower fit at chunk layer)**  
   Firecrawl and mdream already drop script/style at conversion. Whisker problem is **post-tomd markdown**; fixing at chunk layer is still needed for PDF-embedded streams. Prefer chunk filter over re-parsing HTML.

---

## 6. Gaps relevant to P2728R11/R12

- **Firecrawl regex does not match bare base64 paragraphs** (only markdown image syntax).
- **Mdream `data:` handling requires markdown link/image structure**; bare blobs pass through.
- **Langextract will pack an entire garbage paragraph into one chunk** if it is one "sentence" or one regex token.
- **No surveyed repo uses entropy or base64 decode validation**; all policies are syntactic (URL scheme, HTML tag, markdown shape).

A whisker chunk-level filter should treat **both** markdown-wrapped data URIs and **raw high-length alphanumeric runs** as first-class cases.
