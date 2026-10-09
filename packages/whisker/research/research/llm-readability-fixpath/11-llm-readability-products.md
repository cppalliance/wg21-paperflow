# 11 - llm-readability-products

**Verdict:** usable-with-conditions — all four ship production PDF/HTML→markdown converters with scrape- or snapshot-level QA, but none verify LLM comprehension; whisker's Lane 3 facts corpus (5 papers, 37 verified facts), CI hermetic gate, and 37/37 blind readback strictly exceed their output QA.
**Confidence:** high

## Findings

- [CRITICAL] **Firecrawl has no LLM-readability comprehension gate.** Markdown QA is substring presence/absence on live test URLs (`scrapeURL.test.ts:55` `expect(out.document.markdown).toContain("Firecrawl Test Site")`), metadata contracts (`scrapeURL.test.ts:56-71`), and format wiring — not table-neighbor, math-surface, or blind fact recovery. Zero `toMatchSnapshot` / `matchSnapshot` under `apps/api/src` (runtime grep, 2026-07-09). Impact: Firecrawl's "LLM-ready" claim is marketing; whisker `facts.py:8-32` + `check_facts` is the only tested comprehension model in this quartet.

- [HIGH] **Firecrawl's closest LLM-facing eval is downstream extract, not markdown QA.** `llmExtract.ts:339-347` feeds `document.markdown` into an LLM prompt for schema-shaped JSON; `e2e_extract/index.test.ts:35-45` scores fuzzy `gotItRight > 1` on author names. That validates the extract product feature, not whether markdown preserves recoverable facts. Impact: mirrors whisker tapetum advisory (LLM reads output) but Firecrawl never gates CI on it; whisker separates deterministic gate (`facts.py`) from opt-in readback (`readback.py:8-24`).

- [HIGH] **Firecrawl PDF shadow comparison is telemetry-only in production.** `shadowComparison.ts:27-61` joint-tiers `lenRatio` + `numberPreservationRatio` + table count; unit-tested (`shadowComparison.test.ts:39-107`). Production path logs under `PDF_SHADOW_COMPARISON_ENABLE` and does not fail scrapes (`engines/pdf/index.ts:523-559`). Impact: portable auxiliary guard pattern for whisker PDF papers, but not a comprehension proof.

- [HIGH] **pymupdf4llm QA stops at byte-exact markdown goldens.** `tests/test_370.py:45` `assert actual == expected`; `tests/test_sce-150.py:21,40,59` same. No JSONL fact corpus, no present/absent/order/table/math assertions, no LLM readback in CI. Impact: structural snapshot fidelity (Lane 1 class), not comprehension; whisker Lane 3 (`facts.py:65-76` eight fact types) is strictly ahead.

- [MED] **pymupdf4llm `page_chunks` + `extract_words` offer RAG metadata whisker readback does not consume today.** `pymupdf_rag.py:339-375` documents `page_chunks`, `extract_words`; `extract_words=True` forces `page_chunks=True` (`pymupdf_rag.py:395-396`). Chunk dicts return `metadata`, `text`, `words`, `tables`, `images` (`pymupdf_rag.py:1301-1311`); README documents `page_boxes` per chunk (`README.md:233-239`). Impact: word-bbox sidecar could enrich tapetum grounding (`adjudicate.py:239-301` `ground_spans` on markdown char intervals) or `corpus_tools.py:176-190` table-fact drafting, but whisker gates markdown not PDF positions; no test scores chunk consumability.

- [MED] **pdf-to-markdown has rich human-in-the-loop debug UX, zero automated output QA.** `DebugView.jsx:83-89` replays transforms `0..N` for stage inspection; `PageView.jsx:20-22` filters to `block.annotation` for modification-only diffs; `ResultView.jsx:35-44` concatenates final markdown with no assertion. Tests are helper-only mocha (`package.json:11-12`), no PDF fixtures. Impact: negative control for comprehension; stage-replay + annotation-filter pattern is learnable for `corpus_tools.py` fact-authoring UX (localize which conversion stage broke a table cell), not for automated gates.

- [MED] **PyMuPDF markdown/table QA is extraction-fidelity, not LLM comprehension.** `test_tables.py:302-319` exact `tab.to_markdown()` pipe golden; `gentle_compare.py:6-27` requires identical word strings in order with rect tolerance `1e-3`. No fact-assertion corpus, no blind LLM eval. Impact: upstream extraction layer validation; whisker `tables.py` neighbor checks operate on converted markdown, a downstream concern PyMuPDF tests never reach.

- [CRITICAL] **No product maintains a readability regression corpus comparable to whisker.** Firecrawl: curated live URLs + substring anchors, external `#scrape-quality-eval` dispatch (`scrape-evals.yml:9-69`) out of default CI. pymupdf4llm: handful of committed `*.expected.md` byte goldens. pdf-to-markdown: none. PyMuPDF: version-keyed text/pickle/pixmap goldens. Whisker's 5-paper corpus with 37 `checked: verified` facts (`00-baseline.md:48-51`), CI hermetic gate (`test_comprehension_corpus.py:60-74`), canary scrambles (`test_comprehension_corpus.py:77-116`), and live 37/37 blind readback (`readback.py:180-205` `_evaluate_answer`, `00-baseline.md:50-51`) exceeds all four — confirmed, not refuted.

## False-pass hypothesis

Firecrawl `scrapeURL.test.ts:55` `toContain("Firecrawl Test Site")` passes when title text survives but a table's row-3/col-2 neighbor is scrambled — the class of defect whisker `table` facts catch (`facts.py:112-114` cell + neighbors). pymupdf4llm `assert actual == expected` (`test_370.py:45`) passes when full-string goldens match but an LLM cannot answer "what is cell X's right neighbor?" from the same markdown.

## False-fail hypothesis

pymupdf4llm byte-exact goldens fail on intentional reflow improvements (whisker golden lane accepts human-blessed diffs via `golden.py`). Firecrawl substring `not.toContain` after `excludeTags` (`scrapeURL.test.ts:142-143` per prior scan) fails when excluded content is correctly removed but a synonym replacement breaks the exact anchor — whisker `present` facts with `max_diffs > 0` (`facts.py:110`) tolerate bounded edit distance.

## Adoption candidate

**Firecrawl `comparePdfOutputs` + helpers `extractNumbers` / `countTables`** — `shadowComparison.ts:16-61`. Clean-room reimplementation as an optional whisker guard sidecar for PDF-sourced papers (joint `lenRatio` + number-preservation + table-count tier). **License: AGPL-3.0** (Firecrawl `LICENSE`); cannot copy verbatim into BSL whisker. All four repos in this scan are AGPL (pymupdf4llm `LICENSE`, PyMuPDF `COPYING`, pdf-to-markdown `package.json:22`); no MIT-licensed adoptable module surfaced. pymupdf4llm `page_chunks` word metadata (`pymupdf_rag.py:1301-1311`) is second-ranked but AGPL-bound and PDF-position-centric, not directly usable by markdown-only `readback.py`.

## What would change my mind

A committed, human-verified fact-assertion corpus (present/absent/order/table/math) with CI gating and scored blind LLM readback in any of the four repos — equivalent to whisker `corpus/*.facts.jsonl` + `test_comprehension_corpus.py` + `readback.py` — would flip the verdict to "equal" on comprehension QA for that product.

---

## Five-question answers (extended from prior scans)

### Q1 — Firecrawl: how does it TEST LLM-readable markdown?

| Mechanism | Present? | Evidence |
|-----------|----------|----------|
| Jest snapshot tests | **No** | Zero `toMatchSnapshot` under `apps/api/src` |
| Substring anchors | **Yes (primary)** | `scrapeURL.test.ts:55` `markdown.toContain(...)`; engine matrix `scrapeURL.test.ts:24-37` |
| PDF shadow structural tiers | **Yes (unit only; log in prod)** | `shadowComparison.ts:54-61`; `index.ts:523-559` async log |
| LLM-based markdown eval | **No** | Extract reads markdown (`llmExtract.ts:346-347`) but tests score extract JSON (`e2e_extract/index.test.ts:45`), not markdown comprehension |
| External eval harness | **On-demand** | `scrape-evals.yml:9-69` dispatches to `firecrawl/scrape-evals`; not default PR CI |

**Verdict:** scrape-fidelity + sparse downstream-extract proxy; no dedicated LLM-readability proof.

### Q2 — pymupdf4llm: output QA and API for readback/grounding?

**QA:** byte-exact committed `*.expected.md` (`test_370.py:45`, `test_sce-150.py:21`); OCR invariants (`test_ocr.py:35-38` U+FFFD); RAG demo scripts without assertions (`examples/country-capitals/` per prior scan). No comprehension corpus.

**API surface for whisker:**

| API | Grounding utility | Evidence |
|-----|-------------------|----------|
| `page_chunks=True` | Per-page markdown segments + metadata | `pymupdf_rag.py:366`, `1301-1311` |
| `extract_words=True` | Word list with bboxes in chunk dict `"words"` key | `pymupdf_rag.py:375,395-396,1310` |
| `page_boxes` | Layout boxes per page (README) | `README.md:239` |
| Plain `to_markdown()` | String only; no positions | `src/__init__.py:75` default `page_chunks=False` |

Whisker `readback.py` and `adjudicate.py:277` ground on markdown char spans, not PDF word bboxes — pymupdf4llm positions are upstream of whisker's markdown gate unless bridged in `corpus_tools.py` during fact authoring from source PDFs.

### Q3 — pdf-to-markdown: parsing-rule testing / HITL fact authoring UX?

**Parsing-rule testing:** four mocha spec files on string/headline helpers only (`package.json:11-12`); 12-stage pipeline (`AppState.jsx:53-67` per prior scan) with `DebugView.jsx:83-89` manual stage replay and per-stage count messages (`DetectHeaders.jsx:118-120` per prior scan). No automated parsing-rule regression.

**Learnable for `corpus_tools.py`:**

1. **Stage-scoped replay** (`DebugView.jsx:83-89`) — when a drafted table fact fails, replay tomd/whisker stages to the transform that broke the cell (whisker has no equivalent UI; CLI-only today).
2. **Annotation-filtered diff** (`PageView.jsx:20-22`) — show only changed blocks when reviewing draft facts (`corpus_tools.py:145-190` emits drafts but does not surface conversion deltas).
3. **`wordMatch` TOC linker** (`stringFunctions.jsx:112-118`, `DetectTOC.jsx:276`) — set-overlap heuristic for heading/TOC recovery; could seed `draft_facts_scaffold` order/present facts with calibratable threshold (whisker uses exact neighbor checks in `facts.py`, not fuzzy TOC linking).

### Q4 — Readability regression corpus across products?

| Product | Regression corpus type | Comprehension facts? |
|---------|------------------------|----------------------|
| Firecrawl | Live test URLs + substring expectations in test source | No |
| pymupdf4llm | ~handful PDF + `*.expected.md` byte goldens | No |
| pdf-to-markdown | None | No |
| PyMuPDF | Version-keyed text/pickle/markdown/pixmap goldens | No |
| **whisker** | **5 papers, 37 verified facts, CI gate, 37/37 readback** | **Yes** |

**Plain statement:** our 5-paper facts corpus + 37/37 readback already exceeds all four products' output QA. None maintain human-verified fact assertions with provenance gate (`facts.py:25-28` `checked == verified`) or blind readback with adversarial `--corrupt` control (`readback.py:67-74,297-313`).

### Q5 — Single highest-leverage adoptable module

**`comparePdfOutputs` / `extractNumbers` / `countTables`** (`firecrawl/.../shadowComparison.ts:16-61`). Highest signal-to-effort auxiliary guard for PDF-origin WG21 papers: catches gross number/table loss without byte goldens. **License: AGPL-3.0** — pattern-only, clean-room port required. Alternatives ruled out: pymupdf4llm byte goldens (wrong gate class), pdf-to-markdown DebugView (UX pattern only, AGPL), PyMuPDF `gentle_compare` (raw extraction, AGPL, no markdown comprehension).
