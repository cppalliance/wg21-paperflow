# 62 - Adversarial doc-claim hunter (C1 refutation attempt)
**Claims tested:** C1
**Exhaustive:** yes (all 31 clones under `packages/whisker/research/repos/`; pattern hits enumerated; implementing code read for every on-topic claim)

## Method

Repos searched (31): camelot, docling, Dolphin, firecrawl, grobid, html-to-markdown-go, html-to-markdown-py, html2text, img2table, langextract, markdownify, marker, markitdown, mdream, MinerU, node-html-markdown, nougat, olmocr, opendataloader-bench-tmp, opendataloader-pdf, pandoc, PDF-Extract-Kit, pdf-to-markdown, pdfplumber, PyMuPDF, pymupdf4llm, surya, tabula-java, tabula-java-tmp, turndown, unstructured.

Exact commands (from repo root `packages/whisker/research/repos/`):

```text
rg -i -n --glob 'README*' --glob '*.md' --glob 'docs/**' \
  "LLM.{0,40}(verif|valid|check|judge|QA|quality)" .

rg -i -n --glob 'README*' --glob '*.md' --glob 'docs/**' \
  "AI.{0,40}(verif|valid|review)" .

rg -i -n --glob 'README*' --glob '*.md' --glob 'docs/**' \
  "self.?(check|correct|verif)" .

rg -i -n --glob 'README*' --glob '*.md' --glob 'docs/**' \
  "hallucination" .

rg -i -n --glob 'README*' --glob '*.md' --glob 'docs/**' \
  "confidence" .

rg -i -n "(llm.*judge|judge.*llm|as an? llm judge|LLMScorer|llm_rater)" marker/
```

Follow-up reads (implementing code for on-topic claims): `marker/benchmarks/overall/scorers/llm.py`, `marker/benchmarks/overall/overall.py`, `marker/benchmarks/overall/elo.py`, `marker/marker/processors/llm/llm_page_correction.py`, `langextract/langextract/prompt_validation.py`, `langextract/langextract/extraction.py`, `docling/docling/datamodel/base_models.py`, `docling/docling/models/stages/layout/layout_model.py`, `olmocr/olmocr/bench/` (README only; no LLM scorer found).

Raw pattern hit counts (README*, docs/**, *.md; excluding tests/data/prediction/ground-truth snapshots): LLM-QA 6, AI-QA 37, self-check 1, hallucination 7, confidence 39. Most AI-QA and confidence hits are regex false positives (HTML “valid”, PR “review”, OCR confidence, statistical RME, etc.).

## Inventory

### On-topic documented claims (LLM/VLM QA, validation, or verification of conversion output)

| # | Doc location | Documented claim (summary) | Code location | Verdict |
|---|--------------|----------------------------|---------------|---------|
| 1 | `marker/README.md:470` | Benchmark set scored with “an LLM as a judge scoring method”; compares conversion methods on single-page PDFs | `marker/benchmarks/overall/scorers/llm.py:94-134` (`LLMScorer.__call__` renders page image from `sample["pdf"]`, sends image + **already-produced** `method_md` to Gemini; prompt lines 15-34: “comparing markdown to an image… rate how effectively markdown represents the text in the image”); invoked per sample at `marker/benchmarks/overall/overall.py:56-59` | **REFUTES C1** — eval harness; VLM judges existing conversion output against source page image, one page per benchmark row |
| 2 | `marker/README.md:470` (same section) | ELO-style pairwise markdown comparison (undocumented in README text but sibling benchmark path) | `marker/benchmarks/overall/elo.py:20-131` (`Comparer.__call__` sends page image + two markdown versions to Gemini, picks winner) | **REFUTES C1** — eval harness; VLM compares two **already-produced** markdown outputs against source page image |
| 3 | `marker/README.md:457`, `564` | `--use_llm` uses an LLM “to improve quality” during conversion | `marker/marker/processors/llm/llm_page_correction.py:32-71` (and sibling processors under `marker/processors/llm/`); production pipeline refinement, not post-hoc verification | **Not C1** — refinement during conversion; model fixes its own pipeline blocks, does not judge finalized output vs source as a QA gate |
| 4 | `markitdown/packages/markitdown-ocr/README.md:143` | Troubleshooting: “Verify” `llm_client` / `llm_model` present | No QA loop; plugin wiring only (`markitdown` OCR path) | **Not C1** — operator checklist, not output verification |
| 5 | `markitdown/README.md:164` | Azure Content Understanding offers “higher-quality document extraction” | Cloud extraction API integration | **Not C1** — extraction quality marketing, not judging existing output |
| 6 | `langextract/skills/langextract-usage/SKILL.md:86-103`, `references/prompt-validation.md:1-45` | “Prompt validation” catches misaligned few-shot examples before extraction | `langextract/langextract/prompt_validation.py:48-252`, called from `langextract/extraction.py:215-231` | **Not C1** — validates prompt **examples** align to example text; no comparison of conversion output to source document |
| 7 | `docling/docs/concepts/confidence_scores.md:1-56` | Per-page and document-level “confidence grades” for conversion quality; “identify documents requiring manual review” | `docling/docling/datamodel/base_models.py:539-609`; scores computed in layout/OCR stages e.g. `docling/models/stages/layout/layout_model.py:233-234` (model confidences, not LLM) | **Near-miss** — per-page deterministic self-metrics during conversion; **no LLM/VLM**, no comparison of finalized markdown to source |
| 8 | `docling/docs/examples/agent_skill/docling-document-intelligence/SKILL.md:192`, `pipelines.md:156` | Hybrid pipeline routes text natively, images/tables through VLM; “reduces hallucination” | Pipeline routing docs only; VLM used for extraction | **Not C1** — extraction-path design claim |
| 9 | `MinerU/README.md:74,76,139`; `docs/en/reference/changelog.md:34` | Engines claim “no/low hallucination” | Extraction engines | **Not C1** — extraction fidelity marketing, not post-hoc LLM verification |
| 10 | `olmocr/README.md:41` | Model release fixes “hallucinations on blank documents” | Model weights / inference | **Not C1** — extraction model improvement |
| 11 | `firecrawl/apps/test-site/.../open-researcher-interleaved-thinking.md:48` | Research agent “self-correcting” search strategy | Firecrawl research demo, unrelated to PDF→MD conversion | **Not C1** — different product surface |

### Pattern hits classified as false positives (not LLM conversion QA claims)

| Pattern | Count | Examples |
|---------|-------|----------|
| LLM-QA | 2 of 6 | `pymupdf4llm/README.md:171` (“checks image quality heuristics”, no LLM); `firecrawl/.../introducing-search-endpoint.md:62` (endpoint deprecation notice) |
| AI-QA | ~35 of 37 | `html2text/docs/how_it_works.md:110` (“create valid” HTML); `langextract/COMMUNITY_PROVIDERS.md:7` (“Please review” packages); duplicate API “invalid UTF-8” errors across html-to-markdown-py reference docs |
| self-check | 0 of 1 on-topic | `unstructured/test_unstructured_ingest/...` table cell text “self check” in fixture markdown |
| confidence | ~35 of 39 | `camelot/README.md:21`, `img2table/README.md:344+`, `surya/README.md:164+` (OCR/layout confidence); `mdream/bench/README.md:89` (statistical RME); `opendataloader-pdf/docs/hybrid/...` (routing triage confidence) |

### Undocumented but related (no matching doc claim in search scope)

| Code location | Role |
|---------------|------|
| `olmocr/olmocr/bench/` (see `olmocr/olmocr/bench/README.md:7-8`) | Per-page PDF deterministic fact-presence tests; **no LLM in eval loop** (consistent with `00-baseline.md:31`) |
| `marker/benchmarks/overall/scorers/heuristic.py:10-40` | Deterministic fuzzy alignment scorer for same benchmark; not LLM |

## Verdict on the claim(s)

**REFUTED** — `marker/benchmarks/overall/scorers/llm.py:94-105` implements `LLMScorer`, which takes an already-produced `method_md`, renders the source PDF page to an image, and calls Gemini to score fidelity of markdown to the page. Documented at `marker/README.md:470`. Benchmark dataset rows are single-page PDFs (`marker/README.md:470`; `LLMScorer` uses `doc[0]` at `llm.py:101-102`), so scoring is per page/unit. This is an eval harness, not the production conversion CLI, but the v2 charter explicitly states benchmark/eval harnesses count toward C1.

No other clone documents and implements LLM/VLM verification of **existing** conversion output against source at page/chunk granularity in a production path. Production `--use_llm` paths (marker, table benchmark inference) are refinement/extraction.

## Coverage gaps

None for the mandated search scope (README*, docs/, *.md across all 31 clones). Non-markdown docs (`.rst`, `.txt` outside README) and non-doc source files were not regex-scanned; a C1 counterexample hiding only in undocmented code would not appear here (this agent’s scope is documented claims only).

## What could still hide a counterexample

- Undocumented LLM judge code in Python/JS sources without a matching README/docs claim (out of scope for this hunter).
- LLM verification behind a cloud API with no local doc mention (e.g. commercial “quality” APIs referenced only on websites).
- Per-chunk verification in repos whose docs use non-English or non-matching vocabulary (e.g. “evaluate”, “audit”, “grounding”) not covered by the five regex patterns.
