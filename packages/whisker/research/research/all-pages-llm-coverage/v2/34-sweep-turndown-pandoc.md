# 34 - turndown, pandoc
**Claims tested:** C1
**Exhaustive:** yes (turndown: entire repo tree; pandoc: `src/` only per scope; pandoc non-`src/` trees not scanned)

Pinned SHAs verified: turndown `fb7a865`, pandoc `76bd78f`.

## Method

Search-floor combined regex (case-insensitive), run with `rg -i -n --no-heading`:

```
openai|anthropic|claude|gemini|google\.genai|genai|litellm|vllm|ollama|chat\.completions|completions\.create|messages\.create|generate_content|GenerativeModel|transformers|AutoModel|\.generate\(|pipeline\(|predict|invoke|prompt|system_prompt|LLM|VLM|gpt-|llama|qwen
```

- **turndown:** regex over entire repo root.
- **pandoc:** regex over `src/` only (production Haskell sources).

Haskell HTTP / AI-API supplemental scan on pandoc `src/` (case-insensitive):

```
openai|anthropic|claude|gemini|generativeai|api\.openai\.com|generativelanguage|cohere|mistral|huggingface|http-client|HTTP\.Client|Network\.HTTP|openai\.com|anthropic\.com
```

Production code read in full for C1 adjudication: `pandoc/src/Text/Pandoc/Class/IO/HTTP.hs` (116 lines). Turndown production tree is 8 files under `src/` (29 files repo-wide); all listed; zero non-lockfile search-floor hits.

## Inventory

### turndown (SHA fb7a865) — 4 hits (all false positives)

**0 LLM invocation sites.** Patterns run (combined regex above).

| file:line | classification |
|---|---|
| `package-lock.json:2203` | lockfile; substring `Vlm` inside sha512 integrity hash |
| `package-lock.json:2889` | lockfile; substring `VLM` inside sha512 integrity hash |
| `package-lock.json:3276` | lockfile; substring `llm` inside sha512 integrity hash (`TumMl6`) |
| `package-lock.json:4465` | lockfile; substring `Vlm` inside sha512 integrity hash |

No matches in `src/`, `test/`, config, or docs for any search-floor or targeted API pattern.

---

### pandoc (SHA 76bd78f) — 74 search-floor hits in `src/` (all false positives)

**0 LLM invocation sites** from search-floor regex in `src/`.

| file:line | classification |
|---|---|
| `src/Text/Pandoc/App.hs:313` | production; `fillMediaBag` call; substring `llm` in identifier |
| `src/Text/Pandoc/Class/PandocMonad.hs:57` | production; `fillMediaBag` export; substring `llm` |
| `src/Text/Pandoc/Class/PandocMonad.hs:511` | production; `fillMediaBag` type sig; substring `llm` |
| `src/Text/Pandoc/Class/PandocMonad.hs:512` | production; `fillMediaBag` impl; substring `llm` |
| `src/Text/Pandoc/Extensions.hs:496` | production; `allMarkdownExtensions` def; substring `llm` in `allM` |
| `src/Text/Pandoc/Extensions.hs:526` | production; `allMarkdownExtensions` ref; substring `llm` |
| `src/Text/Pandoc/Extensions.hs:527` | production; `allMarkdownExtensions` ref; substring `llm` |
| `src/Text/Pandoc/Extensions.hs:528` | production; `allMarkdownExtensions` ref; substring `llm` |
| `src/Text/Pandoc/Extensions.hs:529` | production; `allMarkdownExtensions` ref; substring `llm` |
| `src/Text/Pandoc/Extensions.hs:530` | production; `allMarkdownExtensions` ref; substring `llm` |
| `src/Text/Pandoc/Extensions.hs:531` | production; `allMarkdownExtensions` ref; substring `llm` |
| `src/Text/Pandoc/Extensions.hs:550` | production; `allMarkdownExtensions` ref; substring `llm` |
| `src/Text/Pandoc/Extensions.hs:646` | production; `allMarkdownExtensions` ref; substring `llm` |
| `src/Text/Pandoc/PDF.hs:62` | production; import `fillMediaBag`; substring `llm` |
| `src/Text/Pandoc/PDF.hs:107` | production; `fillMediaBag` call; substring `llm` |
| `src/Text/Pandoc/Readers/BibTeX.hs:78` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Parsing/State.hs:31` | production; import `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Parsing/State.hs:152` | production; `nullMeta` init; substring `llM` |
| `src/Text/Pandoc/Parsing/State.hs:153` | production; `nullMeta` init; substring `llM` |
| `src/Text/Pandoc/Readers/CslJson.hs:54` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/URI.hs:65` | production; URI scheme list; substring `llm` in `ms-enrollment` |
| `src/Text/Pandoc/URI.hs:95` | production; URI scheme `"gemini"` (link scheme, not Generative AI API) |
| `src/Text/Pandoc/XML.hs:491` | production; HTML element name `"prompt"` in allowlist |
| `src/Text/Pandoc/Readers/DocBook.hs:351` | production; DocBook `<prompt>` element comment |
| `src/Text/Pandoc/Readers/DocBook.hs:1311` | production; DocBook `"prompt"` tag handler |
| `src/Text/Pandoc/Readers/EPUB.hs:169` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Readers/Haddock.hs:169` | production; GHCi REPL `prompt` parameter name |
| `src/Text/Pandoc/Readers/Haddock.hs:170` | production; REPL prompt CSS class `"prompt"` |
| `src/Text/Pandoc/Readers/Haddock.hs:176` | production; comment about REPL prompt whitespace |
| `src/Text/Pandoc/Readers/Haddock.hs:177` | production; REPL `prompt` variable |
| `src/Text/Pandoc/Writers/ChunkedHTML.hs:90` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Writers/ChunkedHTML.hs:173` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Readers/Ipynb.hs:79` | production; `jsonMetaToPairs (cellMetadata c)`; substring `llm` in `Meta` |
| `src/Text/Pandoc/Writers/EPUB.hs:816` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Writers/EPUB.hs:935` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Writers/EPUB.hs:992` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Readers/Mdoc.hs:111` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Readers/Man.hs:49` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Readers/Markdown.hs:306` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Writers/Docx/Table.hs:201` | production; `OOXMLCellMerge`; substring `llm` in `CellMerge` |
| `src/Text/Pandoc/Writers/Docx/Table.hs:221` | production; `OOXMLCellMerge`; substring `llm` |
| `src/Text/Pandoc/Writers/Docx/Table.hs:253` | production; `OOXMLCellMerge`; substring `llm` |
| `src/Text/Pandoc/Writers/HTML.hs:1770` | production; LaTeX env `"smallmatrix"`; substring `llm` |
| `src/Text/Pandoc/Writers/Markdown.hs:270` | production; `isNullMeta`; substring `llM` |
| `src/Text/Pandoc/Writers/Markdown.hs:693` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Writers/Markdown.hs:800` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Readers/MediaWiki.hs:59` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Readers/Muse.hs:66` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Writers/Ms.hs:683` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Writers/Markdown/Inline.hs:701` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Writers/Markdown/Inline.hs:710` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Readers/Native.hs:34` | production; comment showing `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Readers/Native.hs:42` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Writers/Ipynb.hs:64` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Writers/Ipynb.hs:66` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Writers/Ipynb.hs:113` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Writers/Ipynb.hs:120` | production; `cellMetadata`; substring `llm` in `Metadata` |
| `src/Text/Pandoc/Writers/Ipynb.hs:142` | production; `cellMetadata`; substring `llm` |
| `src/Text/Pandoc/Writers/Ipynb.hs:168` | production; `cellMetadata`; substring `llm` |
| `src/Text/Pandoc/Writers/Ipynb.hs:186` | production; `cellMetadata`; substring `llm` |
| `src/Text/Pandoc/Writers/OPML.hs:38` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Writers/OPML.hs:40` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Writers/OPML.hs:60` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Writers/OPML.hs:79` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Readers/Vimwiki.hs:64` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Readers/Vimwiki.hs:432` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Readers/Roff.hs:415` | production; `fillMacroArg`; substring `llM` |
| `src/Text/Pandoc/Readers/Roff.hs:417` | production; `fillMacroArg`; substring `llM` |
| `src/Text/Pandoc/Readers/Roff.hs:418` | production; `fillMacroArg`; substring `llM` |
| `src/Text/Pandoc/Readers/Textile.hs:14` | production; URL `promptworks.com`; substring `prompt` |
| `src/Text/Pandoc/Readers/Textile.hs:93` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Readers/LaTeX/Parsing.hs:184` | production; `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Readers/Org/ParserState.hs:50` | production; import `nullMeta`; substring `llM` |
| `src/Text/Pandoc/Readers/Org/ParserState.hs:182` | production; `nullMeta`; substring `llM` |

#### pandoc Haskell HTTP supplemental — 10 hits (all generic fetch, not AI)

| file:line | classification |
|---|---|
| `src/Text/Pandoc/Class/CommonState.hs:28` | production; `Network.HTTP.Client` import for shared `Manager`; generic HTTP infra |
| `src/Text/Pandoc/Class/IO.hs:52` | production; `Network.HTTP.Client` import; generic HTTP infra |
| `src/Text/Pandoc/Class/IO.hs:55` | production; `Network.HTTP.Client.Internal` proxy helper |
| `src/Text/Pandoc/Class/IO.hs:56` | production; `Network.HTTP.Client.TLS` TLS manager settings |
| `src/Text/Pandoc/Class/IO.hs:57` | production; `Network.HTTP.Types.Header` content-type header |
| `src/Text/Pandoc/Class/IO/HTTP.hs:37` | production; `Network.HTTP.Client` import in `openURL` fetcher |
| `src/Text/Pandoc/Class/IO/HTTP.hs:40` | production; proxy helper import |
| `src/Text/Pandoc/Class/IO/HTTP.hs:41` | production; TLS manager import |
| `src/Text/Pandoc/Class/IO/HTTP.hs:42` | production; content-type header import |
| `src/Text/Pandoc/URI.hs:20` | production; `Network.HTTP.Types` import for URI parsing |

`HTTP.hs` implements `openURL` for fetching remote images/resources into the media bag. No AI endpoint URLs, no request bodies resembling chat/completions payloads, no model parameters.

Supplemental AI-API URL scan (`openai.com`, `anthropic.com`, `api.openai`, `generativelanguage`, `huggingface`, etc.): **0 hits** in `src/`.

**0 LLM invocation sites** in pandoc `src/`.

## Verdict on the claim(s)

**C1 CONFIRMED** for turndown and pandoc at pinned SHAs.

- **turndown:** Deterministic HTML-to-Markdown library (`src/turndown.js` plus rule modules). No LLM/VLM client imports, no HTTP AI calls, no eval harness scoring converted output against source pages.
- **pandoc:** Deterministic document converter. HTTP usage is limited to generic remote resource fetch (`openURL`). No OpenAI/Anthropic/Gemini/HuggingFace API usage in `src/`. No code path judges already-produced conversion output against source per page/chunk/unit.

## Coverage gaps

- **pandoc:** Only `src/` scanned (per task scope). Not scanned: `test/`, `doc/`, `data/`, `tools/`, cabal/stack files, CI YAML outside `src/`. Unlikely to hold production conversion verification LLM paths, but not exhaustively ruled out outside `src/`.
- **turndown:** None within assigned scope (entire repo tree searched).

## What could still hide a counterexample

- Pandoc code outside `src/` (Lua filters shipped separately, undocumented shell wrappers) invoking external LLM CLIs at runtime without in-repo string literals matching search floor.
- Dynamic string construction of AI endpoint URLs not matching literal scans.
- Runtime-loaded plugins/filters not present in the pinned checkout.
