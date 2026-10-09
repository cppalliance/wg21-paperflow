# 13 - TOC and Page-Furniture Specialist

**Verdict:** usable-with-conditions — whisker already encodes the tomd conversion contract (TOC
removal, furniture drop, front-matter migration) in gates, prompts, and `clean_pages`, but
furniture/TOC quotes are not classified before evidence promotion, so sanctioned source-only text
still masquerades as "missing content."
**Confidence:** high

## Executive summary

Page furniture and TOC are the highest-volume **sanctioned-absence** class in WG21 PDF conversion.
tomd strips them by design; whisker must treat their absence from Markdown as correct, not as a
conversion defect. The failure mode in the nine-PR replay is the inverse: the PDF judge proves
source presence only (`pdf_judge.py:513-520`, `grounding.py:171-241`) while the sidecar hard-codes
`"present in PDF text layer, absent from markdown"` (`pdf_judge.py:401-404`) without a candidate
locate pass (`00-baseline.md` §2). Furniture makes that one-sided proof worse because the **source
lane strips some furniture** (`textlayer.py:132-187`) but the **judge can still quote unstripped
raw lines** from pages the LLM saw before cleaning, and because **TOC page-number suffixes in the
source text layer** (`test_pdf_judge.py:200-212`) survive into recall screens while the Markdown
never carried them.

External repos separate these concerns structurally. **Docling** labels `PAGE_HEADER` /
`PAGE_FOOTER` / `DOCUMENT_INDEX`, assigns `ContentLayer.FURNITURE`
(`readingorder_model.py:402-403`), and treats PDF bookmarks as a separate outline channel
(`pdf_outline.py:1-137`, `heading_hierarchy_model.py:10`). **PyMuPDF** raw `get_text("text",
sort=True)` returns furniture inline (`textlayer.py:113`); **pymupdf4llm** uses layout
`page-header` / `page-footer` classes and can omit them at export (`document_layout.py:934-939`,
`utils.py:674-723`; tests default `header=False, footer=False` at
`pymupdf4llm/tests/test_general.py:29-30`). **olmOCR-Bench** runs symmetric `PRESENT` / `ABSENT`
`TextPresenceTest` with optional `first_n` / `last_n` zone windows for header/footer strata
(`olmocr/bench/tests.py:129-182`; `05-web.md` Q1). Whisker should adopt the olmOCR pattern
(classify → source locate → candidate locate → disposition) with furniture-specific reason codes,
not a new dependency.

## Sanctioned vs genuine: decision table

| Source text class | Expected in Markdown? | Whisker today | Correct disposition |
|---|---|---|---|
| Running header/footer (repeated line) | No | Stripped in `clean_pages` for judge input; may still be quoted from raw layer | `sanctioned_omit` / never promote to missing quote |
| Isolated page number line (`^\d{1,5}$`) | No | Stripped per page (`textlayer.py:183-184`) | `sanctioned_omit` |
| TOC block / outline entries | No (body headings replace) | Prompt + `no_toc_leak` ban **leaked** TOC in MD (`pdf_judge.py:137-144`, `gates.py:143-185`) | Source TOC quote → `sanctioned_omit`; MD TOC residue → `leak_defect` |
| Title block (document, date, reply-to) | Yes, as YAML front matter | Prompt sanctions migration (`pdf_judge.py:132-136`) | `front_matter_migrated` if values in YAML |
| TOC entry with trailing page number in **source** | No in MD; number suffix not body content | Not stripped from source text; can inflate false "missing" quotes | `sanctioned_omit` after stem match |
| Body prose, tables, code, math | Yes | Candidate-absence unverified | `genuine_miss` only after bidirectional check |
| Text inside figures/images | No (imaged) | Prompt sanctions (`pdf_judge.py:147-149`) | `figure_imaged` |

**Genuine omission** requires: class = body content (or migrated front-matter value missing from
YAML), source locate passes, candidate locate fails at threshold, and quote is not a TOC-leak
artifact in the Markdown.

## Findings

- [CRITICAL] PDF-judge evidence is one-sided: `ground_spans(spans, pdf_text)` proves source
  presence only (`pdf_judge.py:513-520`; `00-baseline.md` §2). Sidecar reason
  `"present in PDF text layer, absent from markdown"` (`pdf_judge.py:401-404`) is asserted, not
  verified. Impact: furniture and TOC lines that are **correctly absent** from Markdown still
  enter `grounded_evidence` as missing-content, inflating the 40% false-absence rate in the
  replay (`00-baseline.md` §1).

- [HIGH] `clean_pages` strips furniture for judge **input** but does not tag or block furniture
  quotes on the **evidence path**. Detection: lines on ≥30% of pages, `<120` chars
  (`textlayer.py:57-63,145-163`); isolated page numbers (`textlayer.py:65-66,183-184`). Tests
  confirm headers/page numbers removed from normalized layer (`test_pdf_judge.py:161-172,
  296-305`). Impact: LLM quotes taken from mental model of "RAW PDF TEXT" can cite furniture
  that cleaning already declared non-content; no reason code distinguishes stripped vs body.

- [HIGH] Short documents skip header/footer detection entirely (`textlayer.py:61-63,
  147`): below `_MIN_PAGES_FOR_HEADER_DETECTION=3`, repeated headers survive (`test_pdf_judge.py:174-181,261-265`). Impact: 1–2 page WG21 papers (common for R0 drafts) feed the judge
  and per-page recall screen furniture that long-paper cleaning would remove, increasing
  false low-recall flags (`pdf_judge.py:287-312`).

- [HIGH] `no_toc_leak` covers only two leak signatures: standalone Contents label and
  page-suffixed duplicate headings (`gates.py:132-185`; tests `test_gates.py:102-161`). Known
  gaps: dot-leader TOCs, roman numerals, non-English labels, table-formatted TOCs pass
  (`whisker/CLAUDE.md` Known gaps §683-688). Over-inclusive: legitimate `## C++ 26` beside
  `## C++` can hard-fail. Impact: leak defects slip through while benign versioned headings
  false-fail; LLM must catch leaks in `reasoning` with no structured reason code.

- [MED] Per-page recall screen runs on `clean_pages` output but compares against full Markdown
  (`pdf_judge.py:463-464,489`). Furniture stripping lowers recall denominators correctly, yet
  **TOC page-number stems** and section prefixes in source (e.g. `"43\nSection 1"` preserved in
  `test_pdf_judge.py:200-212`) still differ from Markdown headings, producing soft false flags on
  otherwise faithful pages. Impact: escalations fire on sanctioned formatting deltas, not body
  loss (`05-web.md`: ambiguous should demote, not count as absent).

- [MED] Docling and pymupdf4llm treat furniture as **typed, optional export**, not fuzzy
  deletion. Docling: `DocItemLabel.PAGE_HEADER` / `PAGE_FOOTER` → `ContentLayer.FURNITURE`
  (`readingorder_model.py:402-403`); `DOCUMENT_INDEX` for TOC tables (`layout_model.py:44`).
  pymupdf4llm: layout `page-header` / `page-footer` bboxes separated before reading order
  (`utils.py:674-723`), omitted when `header=False` / `footer=False` (`document_layout.py:934-939`).
  Whisker uses frequency heuristics only—no bbox class, no zone scoping. Impact: whisker cannot
  assert `ABSENT` on header/footer zones the way olmOCR `TextPresenceTest` does with `first_n` /
  `last_n` (`olmocr/bench/tests.py:160-165`).

- [LOW] TOC A/B readback shows injected TOC adds ~3.1k tokens with zero comprehension gain
  (`whisker/research/toc-ab-experiment.md` §90-118). Impact: any future "keep TOC for LLM
  navigation" policy is unsupported; sanctioned removal stays correct for downstream consumers.

## Provenance and reason-code design

Sidecar `grounded_evidence[]` should carry explicit provenance instead of a single hard-coded
reason string. Proposed fields (research-only schema; no code in this run):

```text
quote_class:   furniture | toc_source | toc_leak | front_matter | figure_text | body
source_locate: exact | fuzzy | not_found          # existing ground_spans tiers
candidate_locate: present_exact | present_fuzzy | absent | ambiguous | skipped
disposition:   genuine_miss | sanctioned_omit | leak_defect | unverified
reason_code:   machine enum (below)
provenance:    { lane, page?, matcher, threshold }
```

**Reason codes (ordered check pipeline):**

| Code | When set | Action |
|---|---|---|
| `FURNITURE_STRIPPED` | Quote line ∈ `header_footer_lines` or matches `_ISOLATED_PAGE_NUMBER_RE` on source page | `sanctioned_omit`; drop from missing list |
| `TOC_SOURCE_SANCTIONED` | Quote stem matches PDF TOC/outline entry or `## N. Title P` source-only suffix | `sanctioned_omit` |
| `TOC_LEAK_MD` | `no_toc_leak` failed or LLM reasoning cites leak; quote is MD-side | `leak_defect`; structure axis, not missing quote |
| `FRONT_MATTER_MIGRATED` | Quote from title block; keys present in YAML | `sanctioned_omit` |
| `FIGURE_IMAGED` | Quote from figure bbox / prompt-classified image text | `sanctioned_omit` |
| `SRC_ONLY_VERIFIED` | Source locate pass, candidate check not run (today's default) | `unverified`; demote verdict |
| `CANDIDATE_PRESENT` | Source pass + candidate locate pass | drop quote (false absence) |
| `CANDIDATE_AMBIGUOUS` | Source pass + candidate fuzzy band | `unverified`; abstain (`05-web.md` CRAG pattern) |
| `Genuine_MISS` | Source pass + candidate absent at threshold | retain as evidence |

**Matcher provenance** (for audit): `matcher: freq_line | isolated_page_num | toc_stem | gate_no_toc_leak | ground_spans | ground_page_quotes`; `threshold: HEADER_FOOTER_FREQ_THRESHOLD`, `PAGE_RECALL_FLOOR`, `EVIDENCE_FUZZY_FLOOR`.

Policy: never promote `sanctioned_omit` quotes to `grounded_evidence`; count them in a separate
`suppressed_evidence[]` bucket for precision metrics (`05-web.md` §ALCE / evidence precision).

## Cleaning-risk verification (current code)

| Risk | Mechanism | Evidence | Severity |
|---|---|---|---|
| False missing quote (furniture) | Judge quotes header/footer; source locate passes on raw `pdf_text` | Prompt forbids (`pdf_judge.py:190-192`) but no post-filter; cleaning is pre-LLM only | HIGH |
| False missing quote (TOC stem) | `"## 1. Introduction 3"`-only-in-source | Not in `clean_pages`; sanctioned by contract | HIGH |
| False low-recall page | Short doc keeps repeated header | `textlayer.py:147` skip when `<3` pages | HIGH |
| False low-recall page | Section label + page index in source | `test_pdf_judge.py:200-212` | MED |
| Leak missed | Dot-leader / i18n / table TOC | `gates.py:143-185` gap per `CLAUDE.md:683-685` | MED |
| Hard fail benign | `## C++ 26` vs `## C++` | `CLAUDE.md:686-687` | MED |
| Boilerplate kept | Repeated line ≥120 chars not stripped | `textlayer.py:160-162` | LOW |
| Double strip inconsistency | `normalize_textlayer` cleans; `ground_spans` uses cleaned `pdf_text`; page escalation uses `cleaned_pages` | `pdf_judge.py:463-464,561` — consistent, good | — |

**Model boundary:** This classification layer would be revised if a labeled holdout shows
stem-based TOC matching suppresses >5% genuine misses on wording papers, or if bbox-class furniture
(from a layout backend) is added to the PDF lane.

## Portable patterns from local repos

1. **Docling content layers:** classify before compare; export pipelines can skip `FURNITURE`
   without touching body items (`readingorder_model.py:401-403`).
2. **pymupdf4llm optional omission:** `header=False, footer=False` at serialization
   (`document_layout.py:898-939`) — symmetric to tomd's drop, explicit at API boundary.
3. **olmOCR bidirectional text tests:** same fuzzy threshold for `PRESENT` and `ABSENT`
   (`tests.py:167-182`); zone windows for header/footer (`tests.py:160-165`). Direct template for
   whisker's candidate-side pass (`05-web.md` Q1).
4. **tomd TOC strip (upstream):** `drop_leaked_toc_entries` in `packages/tomd/tests/test_structure.py`
   — conversion removes TOC; whisker gates detect **leak back in**, not **sanctioned removal**.

## False-pass hypothesis

A paper leaks a dot-leader TOC (`"Introduction .......... 3"`) into the Markdown body. `no_toc_leak`
does not match (`gates.py:132-134` requires standalone Contents or suffixed duplicate **headings**).
PDF judge quotes a TOC line from source; one-sided grounding passes; disposition stays
`unverified` but verdict remains `pass` if the LLM ignores structure. Precision hole until
`TOC_LEAK_MD` is structured.

## False-fail hypothesis

A wording paper legitimately repeats a short boilerplate line (≤119 chars) on ≥30% of pages (e.g.
standard disclaimer). `clean_pages` strips it from source (`textlayer.py:157-163`); body prose
still in Markdown. Per-page `content_recall` drops (`pdf_judge.py:307-311`), triggering escalation
and missing-content quotes for lines that are **not** furniture but were classified as such.
Frequency heuristic confuses repeated body with running header.

## What would change my mind

A replay of the nine-PR furniture/TOC quote subset with bidirectional locate + the reason-code
pipeline above, reporting suppressed `sanctioned_omit` count and post-filter evidence precision
≥0.85 on missing-content quotes, would upgrade verdict to **usable** without conditions.
