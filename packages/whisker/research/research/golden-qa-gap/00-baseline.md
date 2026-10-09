# 00 - Evidence Baseline: Golden-QA Gap Analysis

**Target:** Self-target `packages/whisker` (deterministic gates, bench, LLM lane)
**Comparison codebase:** 31 cloned repos at `packages/whisker/research/repos/`
**Date:** 2026-07-15
**Goal:** Identify the simplest adoptable solutions from surveyed repos for the 5 verified miss-classes our Det+LLM pipeline failed on during PRs #282-295.

## What the target is

Whisker is a deterministic + advisory-LLM QA system for WG21 paper conversions. It has two lanes:
1. **Deterministic lane** (`score.py`, `gates.py`, `bench.py`, `constants.py`): 5 structural gates + coverage/drift/region signals + golden-ideal panel
2. **Advisory LLM lane** (`tapetum_llm/`): text-judge (HTML), PDF-text-layer-judge (PDF), per-page recall screen, fusion with deterministic verdict

Entry points: `whisker <PID>` (det), `whisker-tapetum-llm <PID>` (LLM), fused via `tapetum_llm/fusion.py`.

## Size

- `packages/whisker/src/whisker/`: ~4200 LOC across 30 .py files
- `packages/whisker/src/whisker/tapetum_llm/`: ~2400 LOC across 17 .py files
- Tests: ~45 test files under `packages/whisker/tests/`
- Cloned repos: 31 in `packages/whisker/research/repos/`

## The 5 verified miss-classes (runtime evidence from PRs #282-295)

### MC1: Front-Matter Truth (gates.py:60-75)

**What happened:** PR #290 (p1122r3) — title is `"1. Introduction"` (the first body heading, not the paper's title), `date` key entirely absent, `reply-to` has 18 entries instead of 1. Deterministic verdict: **pass**. LLM verdict: **pass conf 0.98** (claimed "Front-matter correctly captures the title block").

**Root cause:** `_gate_front_matter()` at `gates.py:60-75` only checks parseability and presence of `title`/`document` keys. It never validates:
- Whether the title VALUE is plausible (vs being the first body heading)
- Whether `date` is present when the source has a `Date:` label
- Whether `reply-to` entries are well-formed `"Name <email>"` pairs

**Whisker anchor:** `gates.py:64-70` — the key-presence loop. `_REQUIRED_FRONT_MATTER_KEYS = ("title", "document")` at line 34.

### MC2: TOC Leak Detection (no check exists)

**What happened:** PR #290 (p1122r3) — entire Table of Contents (source pp. 0-1) leaked into the body as duplicate headings with page numbers (`## 1. Introduction 3`). PR #293 (p0533r9) — CONTENTS/TOC table kept in body. Both passed all 5 gates and scored green.

**Root cause:** No gate or signal checks for TOC-shaped content in the body. tomd has a documented TOC-stripping step (`lib/toc.py`), but whisker has no check verifying it fired. The `heading_monotone` gate cannot see duplicate headings (it checks level progression, not uniqueness).

**Whisker anchor:** `gates.py:96-112` (`_gate_heading_monotone`) — only checks `level > prev + 1`, blind to duplicates. No TOC-detection gate exists.

### MC3: Photocopy-Golden Blindness (bench.py:170-211)

**What happened:** PR #290 — bench NID 0.9975, MHS 1.0, content_recall 1.0, overall 0.9992. Scores are misleadingly perfect because the golden ideal is a near-verbatim copy of tomd's own buggy output. The wrong title, missing date, TOC leak, and heading-level miss are all byte-identical between our tomd output and the "ideal", so they cancel out in every comparison metric.

**Root cause:** `run_bench()` at `bench.py:170-211` compares candidate vs reference text, but when both sides share the same bug, the metric is blind. No signal measures how much the golden diverges from the SOURCE (the original HTML/PDF), only from our own output.

**Whisker anchor:** `bench.py:170-211` — the comparison is always candidate-md vs reference-md, never candidate vs source. `score.py:241-328` (`score_markdown`) similarly — `ideal_md` is scored against `md_text` (our output), not against the source.

### MC4: Sub-Resolution Defects (metrics resolution limits)

**What happened:** PR #294 (p3411r5) — one dropped period in a 3878-line document. Every metric rounded to 1.0, all gates passed, LLM said pass at conf 1.00. Only the byte-level diff against an independent second conversion caught it.

**Root cause:** Structural: a single character change in a document of this size is below the numerical resolution of NID, TEDS, MHS, content_recall, and coverage. No amount of threshold tuning can detect a 1-char defect in 100k+ chars via aggregate metrics.

**Whisker anchor:** All metric computations in `bench.py` and `metrics.py`. This is a fundamental resolution limit, not a tunable bug.

### MC5: LLM Calibration (False-Clear + False-Positive)

**What happened:**
- PR #282: LLM confidently claimed "Section order and nesting match the source HTML outline exactly" when the ideal had `### References` vs source `h2: References` — **despite** having the explicit HTML heading outline injected into the prompt (`html_outline.py`).
- PR #290: LLM said "pass 0.98" and claimed front-matter was correct when the title was objectively wrong.
- PR #295: LLM said "review 0.95" flagging H2→H3 heading jump under References — **but the source HTML genuinely has** `h2: References → h3: Informative References`, so this was a False Positive.
- PR #293: LLM correctly caught 31 dropped `constexpr` (review 0.95) — a genuine hit.

**Root cause:** The LLM's self-reported confidence is anti-calibrated (research/hybrid-llm-scoring/SYNTHESIS.md: "min 0.90, median 0.95, 196/204 >= 0.95; fails carry same confidence as passes"). It cannot reliably detect heading-level mismatches even with injected outlines, and cannot validate front-matter truth against the source (it only sees the markdown).

**Whisker anchor:** `tapetum_llm/adjudicate.py` (text lane), `tapetum_llm/pdf_judge.py` (PDF lane), `tapetum_llm/html_outline.py` (outline injection).

## Comparison anchors in the repos

| Repo | Location | Relevance |
|---|---|---|
| olmocr | `packages/whisker/research/repos/olmocr/` | `tests.py` per-page deterministic fact checking, `partial_ratio` fuzzy presence, length-relative tolerance. NO LLM in eval loop. |
| docling | `packages/whisker/research/repos/docling/` | `verify_table_v2` span-aware grid, `eval_doc_vlm` per-page numeric scores, 10th-percentile-tail aggregation |
| marker | `packages/whisker/research/repos/marker-v1.10.2/` | `--use_llm` selective LLM with deterministic fallback, block-scoped reject-and-keep sanity gates |
| opendataloader-pdf | `packages/whisker/research/repos/opendataloader-pdf/` | Per-axis null-eligibility (already adopted in bench.py), `check_regression` per-axis guard |
| MinerU | `packages/whisker/research/repos/MinerU/` | Content-type-aware extraction routing, figure/table vs text separation |
| pdfplumber | `packages/whisker/research/repos/pdfplumber/` | Font-metadata extraction (size, bold, italic flags per character) |
| PyMuPDF/pymupdf4llm | `packages/whisker/research/repos/PyMuPDF/` + `pymupdf4llm/` | `page.get_text("dict")` span-level font/size/flags, heading detection by font metadata |
| grobid | `packages/whisker/research/repos/grobid/` | Consolidation provenance (`status`/`source`), metadata extraction from scholarly headers |
| langextract | `packages/whisker/research/repos/langextract/` | `char_interval is None` reject signal, grounding pattern (already adopted) |
| surya | `packages/whisker/research/repos/surya/` | OCR confidence per line, layout detection with heading/paragraph/table classification |
| pandoc | `packages/whisker/research/repos/pandoc/` | AST-level structure validation, metadata block parsing |
| nougat | `packages/whisker/research/repos/nougat/` | `[MISSING_PAGE_FAIL:n]` in-band markers, per-page degeneration guards |
| markitdown | `packages/whisker/research/repos/markitdown/` | Already used as reference oracle in whisker |
| html2text | `packages/whisker/research/repos/html2text/` | HTML heading level preservation logic |
| markdownify | `packages/whisker/research/repos/markdownify/` | HTML→MD heading mapping rules |
| camelot | `packages/whisker/research/repos/camelot/` | Table extraction confidence scores, lattice vs stream table detection |
| img2table | `packages/whisker/research/repos/img2table/` | Table border detection, cell extraction from images |
| tabula-java | `packages/whisker/research/repos/tabula-java/` | PDF table structure extraction |
| PDF-Extract-Kit | `packages/whisker/research/repos/PDF-Extract-Kit/` | Layout analysis + table recognition pipeline |
| firecrawl | `packages/whisker/research/repos/firecrawl/` | HTML-to-MD conversion quality checks |

## Prior research syntheses (do not re-file)

1. `research/hybrid-llm-scoring/SYNTHESIS.md` (2026-07-07): Asymmetric fusion matrix adopted. Fusion is live in `tapetum_llm/fusion.py`. Key finding: "Nobody averages. Confidence is anti-calibrated."
2. `research/per-page-judging/SYNTHESIS.md` (2026-07-09): Hybrid per-page recall screen adopted. Live in `pdf_judge.py:screen_pages`. Key finding: "Worst-page-wins noise math refutes per-page LLM judge. Deterministic screen + scoped escalation."
3. `packages/whisker/research/persona/` (original whisker research): 30 personas + 5 Opus meta-reviews. Full self-assessment of whisker's scoring system.

## Persona roster (25 total)

### Repo analysts (12) — "how does this repo validate/detect what we miss?"

| NN | Persona | Assigned repos | Hunt target |
|---|---|---|---|
| 01 | olmocr-bench-analyst | olmocr | Per-rule deterministic fact checks, metadata validation patterns |
| 02 | marker-hybrid-analyst | marker | Selective LLM with deterministic fallback, block-level sanity gates |
| 03 | docling-eval-analyst | docling | Per-page scoring, span-aware table grids, metadata extraction |
| 04 | MinerU-Dolphin-analyst | MinerU, Dolphin | Content-type routing, layout-aware extraction |
| 05 | surya-nougat-analyst | surya, nougat | OCR confidence scoring, degeneration guards, page-level markers |
| 06 | grobid-unstructured-analyst | grobid, unstructured | Metadata extraction from headers, consolidation provenance |
| 07 | PyMuPDF-pdfplumber-analyst | PyMuPDF, pymupdf4llm, pdfplumber | Font-metadata heading detection, text span introspection |
| 08 | pandoc-html2text-analyst | pandoc, html2text, markdownify | AST structure validation, heading-level preservation |
| 09 | markitdown-firecrawl-analyst | markitdown, firecrawl | Reference oracle patterns, HTML→MD quality checks |
| 10 | table-tools-analyst | camelot, img2table, tabula-java | Table extraction confidence, separator detection patterns |
| 11 | opendataloader-PDFKit-analyst | opendataloader-pdf, PDF-Extract-Kit | Per-axis guards, null-eligibility, layout analysis |
| 12 | langextract-analyst | langextract | Char-interval grounding, reject signals |

### Miss-class hunters (8) — "what specific fix closes each gap?"

| NN | Persona | Failure class hunted |
|---|---|---|
| 13 | Front-Matter-Truth-Auditor | MC1: title plausibility, date presence, reply-to shape — what deterministic check can we add to `gates.py`? |
| 14 | TOC-Leak-Detective | MC2: duplicate-heading detection, page-number patterns in body text — what signal catches TOC leaks? |
| 15 | Photocopy-Golden-Detector | MC3: ideal-vs-source divergence metric, "how close is the ideal to raw tomd" as a WARNING signal |
| 16 | Sub-Resolution-Diff-Stratege | MC4: byte-level diff strategies that catch single-char defects, reference-based differencing |
| 17 | LLM-Calibration-Skeptic | MC5: LLM false-clear + false-positive patterns, confidence calibration, prompt engineering limits |
| 18 | Heading-Ground-Truth-Extractor | MC1/MC2 adjacent: PyMuPDF font-metadata as deterministic heading-level oracle for PDFs |
| 19 | Table-Separator-Robustness | MC-adjacent: `_TABLE_SEP_RE` at `tables.py:36` requires `-{2,}` — what about GFM-valid `|-|-|`? |
| 20 | Gate-Fold-Skeptic | MC-adjacent: advisory-ref-flag blocking pass-fold at `score.py:225-227` causing false `review` on clean papers |

### Process personas (5)

| NN | Persona | Mandate |
|---|---|---|
| 21 | Prior-Research-Archaeologist | Mine existing `research/**/*.md` and `packages/whisker/research/**/*.md` for findings already documented; prevent re-filing |
| 22 | Whisker-Boundary-Guardian | Every proposed adoption must land under `packages/whisker/src/whisker/`; flag any that would need pipeline/tomd changes |
| 23 | Simplicity-Skeptic | Minimalism Ladder: stdlib > existing dep > new dep > new code. Reject over-engineering |
| 24 | Test-Suite-Auditor | What guard tests does each proposed adoption need? Cite existing test patterns |
| 25 | Steelman | What our system already does RIGHT (PRs #286, #293 caught by LLM); keep the verdict fair |

## Web-forage questions (for Step 0.5)

1. **Golden-fixture validation in document-conversion QA:** `"golden test fixture validation document conversion QA 2025 2026"` — how do other projects validate their golden/blessed references against sources?
2. **Metamorphic testing for NLP/document scoring:** `"metamorphic testing document scoring NLP metrics sub-resolution 2025 2026"` — strategies for detecting defects below metric resolution.
3. **LLM-as-judge calibration techniques:** `"LLM judge calibration false positive false negative document fidelity 2025 2026"` — calibration approaches for LLM judges in document-quality contexts.

## Required persona report template

```
# NN - <Persona name>

**Verdict:** usable | usable-with-conditions | garbage   (+ 1 sentence why)
**Confidence:** high | medium | low

## Findings
- [CRITICAL|HIGH|MED|LOW] <claim>. Evidence: <file:line OR runtime number from 00>.
  Impact: <why it makes the target more/less trustworthy or adoptable>.
  (repeat; 3-8 findings, ranked)

## False-pass hypothesis
<one concrete case the target/our-equivalent would wrongly accept, or "none found">

## False-fail hypothesis
<one concrete case it would wrongly reject, or "none found">

## What would change my mind
<the single piece of evidence that would flip my verdict>
```
