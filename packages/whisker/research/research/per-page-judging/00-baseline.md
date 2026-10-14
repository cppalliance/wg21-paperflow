# Per-Page LLM Judging - Evidence Baseline

**Research question:** How do document-conversion and conversion-QA repos scope
their LLM (or quality) verification to small units (page, block, element,
chunk) instead of one monolithic whole-document call, and how do they aggregate
per-unit results into a document-level verdict?

**Why we ask:** Verified failure (2026-07-14, p0957r8): our PDF-text-layer
judge received the FULL 33-page text layer + FULL converted markdown in one
~40k-token call. Page-13 content (Figure 1/2 captions, Table 2 comparison
table) was present in the RAW block (debug transcript lines 523-550) and
absent from the markdown block (zero matches), yet the model said
`pass, confidence 0.98, missing_content: []`. Root cause: absence detection
over two 20k-token documents requires exhaustive enumeration, which attention
does not perform; presence-checking at small scale is reliable. We are about
to rebuild the judge per-page and want the strongest prior art first.

## Our code anchors (comparison substrate)

- `packages/whisker/src/whisker/tapetum_llm/pdf_judge.py`
  - `JUDGE_SYSTEM_PROMPT` (L75-132): monolithic "judge whether the markdown
    faithfully preserves the paper's content", max 5 missing-content quotes,
    60-word reasoning cap.
  - `judge_pdf_extraction()` (L222-327): one LLM call for the whole paper;
    deterministic `text_nid`/`content_recall` computed alongside; grounding of
    quotes via `ground_spans` against the WHOLE text layer; demotions:
    confidence floor 0.50, recall floor 0.85, nid floor 0.80 (pass->review).
- `packages/whisker/src/whisker/tapetum_llm/textlayer.py`
  - `extract_textlayer()` (L75-128): PyMuPDF per-page extraction, returns
    `list[str]` (one string per page) - per-page data ALREADY exists.
  - `normalize_textlayer()` (L131-187): header/footer strip + join; the paged
    judge needs the cleaned pages as a list (planned `clean_pages()` split).
- `packages/whisker/src/whisker/tapetum_llm/chunking.py`
  - `aggregate_adjudications()`: existing precedent for folding chunk verdicts
    (worst axis, min confidence, union of evidence) - the text lane already
    chunk-splits oversized papers on H2 boundaries and triages serially.
- `packages/whisker/src/whisker/tapetum_llm/constants.py`: named-constant
  discipline; `CONFIDENCE_DECISION_FLOOR=0.50`, `PDF_JUDGE_RECALL_FLOOR=0.85`,
  `PDF_JUDGE_NID_FLOOR=0.80`, `MAX_PAPER_MD_CHARS=500_000`.
- Determinism rules (root CLAUDE.md): D5 no per-call temperature/seed
  overrides, D6 structured output_type, D10 finite retry budget, D11 at most
  one in-flight request (serial); fidelity: fail the paper, never partial.

## Prior research (do not re-file, cite and extend)

- `research/vlm-pdf-qa/SYNTHESIS.md`: decided v1 = olmOCR VLM per-page
  transcription + deterministic diff (needs a vision pod that does not exist
  yet). Our current fix is the TEXT-lane adaptation of the per-page idea.
- `research/vlm-pdf-qa/20-olmocr-pipeline-analyst.md`: olmocr per-page
  mechanics already partially mined (retry ladder, TaskGroup dispatch,
  fallback policy 0.004 error rate, front-matter validation). EXTEND with the
  bench side (olmocr/bench, BasePDFTest presence/absence/order tests) which is
  NOT yet covered.
- `research/hybrid-llm-scoring/SYNTHESIS.md`: fusion rules, confidence
  anti-calibration (18/18 fails at >=0.95).
- `packages/whisker/research/tapetum-golden-review-findings-2026-07-14.md`:
  the F1/F2/F3 failure modes and the fix batch this research feeds.

## Targets (cloned, analyze in place, read-only)

All under `packages/whisker/research/repos/`: olmocr, marker, docling, MinerU,
nougat, langextract, surya, PDF-Extract-Kit, grobid, unstructured, firecrawl,
opendataloader-pdf, Dolphin, pdfplumber, pymupdf4llm, camelot, img2table,
markitdown, pandoc, and others. Not every repo is relevant; each persona gets
an assigned subset.

## What each persona must answer (its angle of these five)

1. **Unit of scoping**: page / block / element / chunk / region - what is the
   LLM- or QA-call unit, and where in the code is the unit boundary drawn?
2. **Prompt or check shape**: extraction ("transcribe this page") vs
   verification ("does X match Y") vs presence-testing ("is this content
   present"). Exact prompt/code anchors.
3. **Aggregation policy**: how do unit results become a document verdict?
   Worst-unit, error-rate threshold, weighted score, majority? Constants.
4. **Per-unit failure handling**: retry ladders, validation gates, fallback,
   trivial/empty-unit skip logic.
5. **Anti-hallucination per unit**: grounding, schema validation, sanity
   checks that reject an LLM answer for a single unit.

## Required report template (verbatim)

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
