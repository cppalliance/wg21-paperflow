# base64-blob-filter - Research Synthesis

**Question:** how do other converters/pipelines handle base64 blobs / data URIs /
garbage streams before emitting markdown or feeding an LLM, and what should our
chunk-level filter in `whisker tapetum_llm` look like?

**Corpus ground truth first** (00-corpus-evidence.md): our "garbage blob" is NOT
random corruption. It is well-formed `![alt](data:image/...;base64,...)` markdown
whose payload tomd passed through from the HTML source. p2728r11.md is 2.54 MB
with a single 1.14 MB line; 10 papers in the corpus carry the class; only the
P2728 pair exceeds the choke threshold. The client has confirmed images are
irrelevant to the extraction mission.

**Surveyed:** 28 repos across 6 domain groups (reports 01-06), composer-2.5 swarm,
2026-07-07.

## What the ecosystem does (consensus picture)

1. **Nobody filters generic high-entropy garbage in markdown body text.** All six
   reports independently confirm: no repo of 28 runs entropy/gibberish detection
   on emitted markdown. The tools that do quality-gate text (marker, MinerU,
   grobid, surya, nougat) do it at PDF-extraction or model-decode time with
   domain heuristics (alphanum ratio, PUA density, repetition loops), not on
   markdown.
2. **The projects that produce LLM-ready markdown strip data-URI images, and
   they strip them by default.** The three strongest precedents:
   - **firecrawl**: `removeBase64Images` default `true`; regex replaces
     `![alt](data:image/...;base64,...)` with `![alt](<Base64-Image-Removed>)`;
     rationale documented as avoiding "overwhelmingly long" output (05).
   - **markitdown**: truncates every `data:` URI to `data:image/png;base64...`
     (prefix only), regression-test-locked (02).
   - **node-html-markdown**: `keepDataImages: false` by default, drops
     `<img src="data:...">` entirely (01).
3. **Reference converters keep payloads by default and externalize on opt-in.**
   pandoc emits `data:` URIs verbatim unless `--extract-media` writes them to
   disk (06); pymupdf4llm will even CREATE uncapped base64 embeds (04); docling
   CLI defaults to full embedded base64 (02). Passing through is the
   conversion-layer default; filtering is the LLM-layer default. That maps
   exactly onto our split: tomd (conversion) may keep or externalize, tapetum
   (LLM lane) must strip.
4. **Where a size guard exists, it is a cap on the decoded payload, not a
   heuristic**: docling 20 MB decode cap, html-to-markdown-py 5 MiB extract cap,
   opendataloader-pdf 10 MB image cap (01/02/04).
5. **The bare-blob case (base64 run WITHOUT the image wrapper) is unhandled
   everywhere**; the closest tools are marker's alphanum-ratio gate and
   MinerU's 65535-char/page cap, both pre-model (03/04). Multiple reports
   converge on the same portable recipe for it: a long-run base64-alphabet
   line detector (e.g. >= 90% of non-whitespace chars in `[A-Za-z0-9+/=]` on a
   line longer than a named threshold).

## Decision for whisker (chunk-level, `tapetum_llm`)

Adopt the firecrawl pattern, extended with our sanctioned-marker convention:

1. **Primary filter (exact, closes the live failure):** before `chunk_markdown`,
   replace every `![alt](data:MIME;base64,PAYLOAD)` with
   `![alt](<!-- tapetum:data-uri-stripped MIME ~SIZE -->)`. Keep alt text (it is
   prose, judgeable). Deterministic regex, cannot false-positive on prose/code.
   Mirrors firecrawl (placeholder text) + markitdown (keep scheme prefix info).
2. **Secondary net (cheap, for wrapper-less debris):** drop/replace any single
   line whose length exceeds a named constant and whose non-whitespace chars are
   >= 90% base64-alphabet. This is the ecosystem-consensus recipe (03/04/05)
   for the case no library handles; it costs ~5 lines and protects against
   future PDF-side debris that lacks the `![](data:...)` wrapper.
3. **Prompt disclosure:** add the new marker to the "Sanctioned tomd markers"
   section of `tapetum_llm.md` so the LLM treats it as disclosure, not defect.
4. **Scope:** filter applies to what the LLM sees (adjudicate select/triage
   path). The stored `paper.md` is untouched. The tomd-side fix (externalize
   data URIs at conversion, pandoc `--extract-media` analog, matching the
   existing `<pid>-fig{page}-{n}.{ext}` layout) is the root-cause ticket for the
   tomd package, separate scope.

## Expected effect

- P2728R11/R12: 2.54 MB -> ~150 KB markdown; no chunking needed at all
  (below MAX_PAPER_MD_CHARS); the 2 standing batch errors disappear.
- 8 further papers stop paying silent token cost per adjudication.
- No fidelity loss: the client has declared images out of scope for the
  extraction mission, and the axis rubric never judged pixel content anyway.

---
Reports: 00 corpus evidence, 01 html-to-md (6 repos), 02 doc-ai (3), 03 pdf-ml
(5), 04 pdf-libs (5), 05 llm-ready-md (3), 06 converters-misc (6).
