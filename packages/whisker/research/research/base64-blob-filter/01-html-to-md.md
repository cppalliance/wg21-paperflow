# HTML-to-Markdown repos: base64 / data-URI / garbage-blob handling

Research date: 2026-07-07. Scope: six local clones under `packages/whisker/research/repos/`. Goal: learn how peer converters treat `data:` URIs, base64 payloads, and oversized attribute/text emission before adding a chunk-level filter in `tapetum_llm`.

---

## turndown

### data-URI policy
**Absent.** `<img src>` and `<a href>` values are copied into markdown with only markdown escaping (parentheses/brackets in destinations, quotes in titles). No `data:` prefix check.

- Image emission: `turndown/src/commonmark-rules.js:249-254` — `const src = escapeLinkDestination(node.getAttribute('src') || '')` then `'![' + alt + ']' + '(' + src + titlePart + ')'`.
- Link emission: `turndown/src/commonmark-rules.js:152-156` — `const href = escapeLinkDestination(node.getAttribute('href'))` then `'[' + content + '](' + href + titlePart + ')'`.
- `escapeLinkDestination` only escapes `<>` and wraps space-containing URLs in angle brackets: `turndown/src/commonmark-rules.js:262-264` — `destination.replace(/([<>()])/g, '\\$1')`.

### base64 detection
**None** in source or tests. Repo-wide search finds no `base64`, `data:`, or `data-uri` in `src/` or `test/`.

### Size caps
**None** on attribute values or emitted markdown. Unknown elements fall through to `defaultReplacement`, which concatenates child text with no length limit: `turndown/src/turndown.js:30-31` — `return node.isBlock ? '\n\n' + content + '\n\n' : content`.

### Entropy / garbage detection
**None.**

### Tests / docs
No fixtures mention base64 or data URIs. Closest related test is `keepReplacement` preserving raw HTML: `turndown/test/turndown-test.js:135-141`.

**Pass-through proof:** any `data:image/png;base64,...` in `src` becomes `![](data:image/png;base64,...)` via the image rule above.

---

## markdownify (python-markdownify)

### data-URI policy
**Absent.** `convert_img` emits `src` verbatim inside markdown image syntax.

- `markdownify/markdownify/__init__.py:582-591` — `src = el.attrs.get('src', None) or ''` then `return '![%s](%s%s)' % (alt, src, title_part)`.
- `convert_a` passes `href` unchanged: `markdownify/markdownify/__init__.py:444-456` — `return '%s[%s](%s%s)%s' % (prefix, text, href, title_part, suffix) if href else text`.

### base64 detection
**None.**

### Size caps
**None** on URLs or text nodes. Table colspan is clamped (`max(1, min(1000, int(el['colspan'])))` at `markdownify/markdownify/__init__.py:738`) but that is unrelated to blobs.

### Entropy / garbage detection
**None.**

### Tests / docs
No tests reference `data:` or base64. README discusses shields.io badge URLs only: `markdownify/README.rst:3-4`.

**Pass-through proof:** image rule at `markdownify/markdownify/__init__.py:591`.

---

## html2text

### data-URI policy
**Absent.** Image `src` (including `data:`) is written into markdown or raw HTML unchanged.

- Default markdown path: `html2text/html2text/__init__.py:548-594` — `attrs["href"] = attrs["src"]` then `'![' + escape_md(alt) + '](' + escape_md(urlparse.urljoin(self.baseurl, href)) + ')'`.
- Raw HTML path (`images_as_html`): `html2text/html2text/__init__.py:559` — `self.o("<img src='" + attrs["src"] + "' ")`.
- Opt-out flags (not data-URI-specific): `ignore_images` drops all images (`html2text/html2text/config.py:45`); `images_to_alt` keeps alt text only (`html2text/html2text/config.py:47`, `html2text/html2text/__init__.py:587-588`).

Links: `href` emitted via `link_url` with no `data:` filter (`html2text/html2text/__init__.py:508-537`).

### base64 detection
**None.**

### Size caps
- **Line wrap:** default `BODY_WIDTH = 78` (`html2text/html2text/config.py:15-16`).
- Paragraphs containing markdown links are **not wrapped** when `wrap_links` is true (default): `html2text/html2text/utils.py:197-198` — `if not wrap_links and config.RE_LINK.search(para): return True` (skip wrap).
- `optwrap` applies `textwrap.wrap` only when `body_width` is non-zero: `html2text/html2text/__init__.py:961-962`, `992-994`.
- No cap on individual attribute or text-node length.

### Entropy / garbage detection
**None.** `handle_data` passes text through (with whitespace/stress tweaks only): `html2text/html2text/__init__.py:872-876` — `if not data: return`.

### Tests / docs
CLI documents `--ignore-images`, `--images-to-alt`, `--body-width` (`html2text/html2text/cli.py:92-96`, `151-155`). No base64/data-URI fixtures found.

**Pass-through proof:** img handler at `html2text/html2text/__init__.py:549-594`.

---

## node-html-markdown

### data-URI policy
**Explicit opt-in for images; default is strip.**

- Image translator: `node-html-markdown/src/config.ts:290-292` — `if (!src || (!options.keepDataImages && /^data:/i.test(src))) return { ignore: true };`
- When kept: `node-html-markdown/src/config.ts:297-298` — ``content: `![${alt}](${src}${title && ` "${title}"`})```
- Option docs: `node-html-markdown/src/options.ts:88-93` — `@default false`, note "These can be up to 1MB each" (documentation only; **no size check in code**).
- `keepDataImages` is **not** set in `defaultOptions` (`node-html-markdown/src/config.ts:32-73`), so it defaults to falsy/undefined → data images dropped.

**Links:** `<a href="data:...">` is **not** filtered; href is percent-encoded for markdown safety only: `node-html-markdown/src/config.ts:248-285`.

### base64 detection
Regex prefix only: `/^data:/i.test(src)` on `<img src>` (`node-html-markdown/src/config.ts:292`). No base64 alphabet or decode validation.

### Size caps
- `maxConsecutiveNewlines: 3` in defaults (`node-html-markdown/src/config.ts:41`); post-process collapses excess blank lines: `node-html-markdown/src/visitor.ts:313-316`.
- No max length on `src`, `href`, or text nodes.

### Entropy / garbage detection
**None.**

### Tests / docs
- Default drops data URI: `node-html-markdown/test/default-tags.test.ts:67-69` — comment "elided due to default option keepDataImages = false".
- Opt-in keeps URI verbatim: `node-html-markdown/test/options.test.ts:274-285` — `keepDataImages = true` expects `![](data:image/gif;base64,R0lGODlhEA)`.
- README mirrors option text: `node-html-markdown/README.md:197-202`.

---

## html-to-markdown-go (JohannesKaufmann/html-to-markdown v2)

### data-URI policy
**Absent; pass-through.**

- Images: `html-to-markdown-go/plugin/commonmark/render_image.go:31-54` — `src := dom.GetAttributeOr(n, "src", "")`, `src = ctx.AssembleAbsoluteURL(...)`, then `w.WriteString(src)` inside `![](...)`.
- Links: `html-to-markdown-go/plugin/commonmark/render_link.go:50-53`, `35` — `href` trimmed, absolutized, written unchanged into `(...)`.

### base64 detection
**None** in Go source (repo-wide search: zero matches for `base64`, `data:` in `*.go`).

### Size caps
**None** on attributes or output strings. File-output `O_TRUNC` is unrelated (`html-to-markdown-go/cli/html2markdown/cmd/io_output.go:182-191`).

### Entropy / garbage detection
**None.**

### Tests / docs
Image tests use normal paths only, e.g. `![](/image.png)` (`html-to-markdown-go/cli/html2markdown/cmd/exec_test.go:583-586`). No data-URI cases.

**Pass-through proof:** `html-to-markdown-go/plugin/commonmark/render_image.go:54`.

---

## html-to-markdown-py (html-to-markdown-rs)

### data-URI policy
**Dual path: default markdown pass-through; optional extraction with validation.**

1. **Default markdown output (most common):** `src` sanitized but not stripped; emitted in `![alt](src)` including full data URIs.
   - Handler: `html-to-markdown-py/crates/html-to-markdown/src/converter/handlers/image.rs:48-51`, `256-279` — `format_image_markdown` pushes `src` into output.
   - `skip_images: false` by default: `html-to-markdown-py/crates/html-to-markdown/src/options/conversion.rs:239`.

2. **Skip all images (including data URIs):** `skip_images: true` omits image markdown entirely.
   - Gate: `html-to-markdown-py/crates/html-to-markdown/src/converter/handlers/image.rs:188-192` — `if !options.skip_images { ... output.push_str(&img_text) }`.
   - Test: `html-to-markdown-py/crates/html-to-markdown/tests/skip_images_test.rs:143-163` — asserts no `data:image`, no `iVBORw0KGgo` when skipping.

3. **Optional inline extraction (`extract_images` + `inline-images` feature):** parallel collector validates/decodes data URIs; invalid/oversized payloads are **skipped with warnings**, not inlined into a side channel.
   - Entry: `html-to-markdown-py/crates/html-to-markdown/src/converter/handlers/image.rs:90-114` — `if src.trim_start().starts_with("data:") { handle_inline_data_image(...) }`.
   - Validation: `html-to-markdown-py/crates/html-to-markdown/src/converter/media/image.rs:31-91` — requires `data:` + `;base64,` marker.
   - Size cap (encoded then decoded): `image.rs:97-108`, `123-131` — compares against `collector.max_decoded_size()`.
   - Default limit constant: `html-to-markdown-py/crates/html-to-markdown/src/inline_images.rs:19-20` — `DEFAULT_INLINE_IMAGE_LIMIT: u64 = 5 * 1024 * 1024`.
   - Default option: `conversion.rs:244-245` — `extract_images: false`, `max_image_size: 5_242_880`.

### base64 detection
Full parse path when `extract_images` enabled: MIME check, `;base64` segment, `STANDARD.decode`, empty/invalid rejection (`image.rs:89-115`). Not applied to default markdown emission.

### Size caps
- `max_image_size` / `DEFAULT_INLINE_IMAGE_LIMIT` = 5 MiB decoded (extraction path only).
- `wrap_width: 80` when `wrap: true`; default `wrap: false` (`conversion.rs:226-227`).
- `max_depth: Option<usize>` truncates DOM subtrees (`conversion.rs:171-173`), not string blobs.

### Entropy / garbage detection
**None** on free text. Preprocessing docs mention "tracking pixels" (`conversion.rs:131`) but no base64/entropy heuristic was found in preprocessing sources searched.

### Tests / docs
Extensive `skip_images` suite including base64 fixture (`skip_images_test.rs:143-164`). No default-path test asserting data URI **removal**; default behavior is emit-or-skip-via-flag.

---

## Comparative table

| Repo | data-URI policy | Size cap | Garbage / entropy detection | Portable idea for chunk-level filter |
|------|-----------------|----------|------------------------------|--------------------------------------|
| **turndown** | Pass-through verbatim in `src`/`href` | None | None | Minimal: not a model; shows baseline "emit whatever HTML had" |
| **markdownify** | Pass-through verbatim | None | None | Same as turndown |
| **html2text** | Pass-through; optional drop all images or alt-only | Line wrap 78 cols (skips link lines) | None | `ignore_images` / alt-only pattern for images; link lines exempt from wrap |
| **node-html-markdown** | **Drop** `img` with `^data:` unless `keepDataImages`; links pass through | Collapse >3 consecutive newlines only | None | **Best simple precedent:** prefix gate `^data:` + default-off keep flag |
| **html-to-markdown-go** | Pass-through verbatim | None | None | None beyond "don't assume conversion fixes it" |
| **html-to-markdown-py** | Default pass-through; `skip_images` drops; optional extract validates base64 + 5 MiB cap | 5 MiB (extract path); optional wrap 80 | None on text | **`skip_images` flag pattern**; validated decode + max bytes before accepting payload |

---

## Portable ideas (ranked for `tapetum_llm` chunk filter)

Pure Python, deterministic, no new dependencies.

1. **`^data:` prefix drop (node-html-markdown pattern).** If a line or markdown image/link destination starts with `data:` (case-insensitive), replace with a fixed placeholder such as `[embedded data removed]`. Matches the only converter that treats data URIs as special by default (`node-html-markdown/src/config.ts:292`). Cheap and targets the P2728 failure mode directly.

2. **Long-run base64 alphabet heuristic + length floor.** On lines > N chars (e.g. 500–2000), if ≥90% of non-whitespace chars match `[A-Za-z0-9+/=_-]` and length exceeds a chunk budget, replace the run with `[binary blob omitted, N chars]`. No decode required; catches undecodable garbage that is not prefixed with `data:`. Inspired by html-to-markdown-py's strict alphabet check on decode failure (`image.rs:114`) but applied to markdown text nodes.

3. **Markdown image/link destination cap.** When parsing `![...](DEST)` or `[...](DEST)`, if `len(DEST) > MAX_URL_LEN` (e.g. 512 or 2048), emit `![alt](<omitted>)` or drop the whole reference. html-to-markdown-py's encoded-size check before decode (`image.rs:97-108`) is the same idea applied earlier in the pipeline.

4. **Optional `skip_images`-style chunk mode.** html-to-markdown-py omits all `img` markdown when `skip_images: true` (`image.rs:188-192`; tests in `skip_images_test.rs:143-163`). For QA chunks, stripping `![](...)` lines entirely (keeping alt in a one-line note) avoids LLM attempts to "describe" image syntax.

5. **Do not rely on line wrapping.** html2text's `BODY_WIDTH`/`optwrap` does not split link-heavy lines (`utils.py:197-198`) and does not detect garbage. Wrapping alone will not prevent megabyte blobs from landing in a single chunk.

---

## Implication for whisker

All six converters assume HTML-stage handling or downstream filtering. **None** scan plain markdown text for high-entropy garbage. For P2728R11/R12 blobs already present in converted markdown, a **chunking-layer filter** (ideas 1–3) is consistent with industry practice: only node-html-markdown and html-to-markdown-py's optional paths attempt to keep base64 out of the readable stream, and both do it at **HTML attribute** time, not on arbitrary text runs.
