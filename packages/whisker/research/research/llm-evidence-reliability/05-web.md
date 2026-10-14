# LLM Evidence Reliability - Web Finding Cards

**Date:** 2026-07-16  
**Foragers:** 5 Composer 2.5 agents  
**Question:** How do open-source systems prove source support and target absence
for document-conversion evidence?

## Q1. PDF/OCR and Markdown verification

### olmOCR-Bench - bidirectional deterministic text tests

- URL: https://github.com/allenai/olmocr/blob/main/olmocr/bench/tests.py
- Relevance: HIGH
- `TextPresenceTest` uses the same normalized/fuzzy machinery for `PRESENT` and
  `ABSENT`, with a length-relative edit threshold and optional first/last
  positional windows.
- Portable detail: run a second, candidate-side check and expose
  `present | absent | ambiguous`; add the length guard from olmOCR PR #462.

### Marker - deterministic GT block alignment

- URL: https://github.com/datalab-to/marker
- Relevance: HIGH
- `HeuristicScorer` fuzzy-aligns ground-truth blocks into candidate Markdown and
  combines block scores with reading order. The LLM scorer compares page image
  and Markdown but does not post-verify evidence.
- Portable detail: deterministic pairing first, LLM only after unresolved pairs.

### pdf-parse-bench - aligned pair then structured LLM rubric

- URL: https://github.com/phorn1/pdf-parse-bench
- Relevance: HIGH
- Formula/table pairs are identified before the LLM scores correctness,
  completeness, and semantic equivalence.
- Portable detail: never ask an LLM to discover and prove absence in one step.

### AbsenceBench - models are weak at absence

- URL: https://arxiv.org/abs/2506.11440
- Relevance: HIGH
- Even when original and edited documents are both in context, strong models
  systematically fail surface-form absence detection.
- Portable detail: absence claims require deterministic candidate verification.

## Q2. Quote and citation verification

### Google LangExtract - exact/fuzzy source span alignment

- URL: https://github.com/google/langextract
- Relevance: HIGH
- `WordAligner` maps model output back to source intervals; unlocatable
  extractions remain ungrounded. Whisker already ports its exact monotonic DP.
- Portable detail: record source-side and candidate-side alignment independently.

### LitRAG - locate before judge

- URL: https://github.com/nickjlamb/litrag/blob/main/faithfulness.py
- Relevance: HIGH
- Exact/normalized/fuzzy quote location runs before an LLM support judgment.
  Unlocatable quotes short-circuit as hallucinated.
- Portable detail: a candidate locate hit must override an LLM "missing" claim.

### Ragas quoted-span alignment

- URL: https://github.com/explodinggradients/ragas
- Relevance: MED
- Deterministic normalized substring alignment measures matched quotes / total.
- Portable detail: report evidence precision separately from verdict agreement.

### ALCE

- URL: https://github.com/princeton-nlp/ALCE
- Relevance: HIGH
- Separates citation recall (claims supported) from citation precision (citations
  necessary), evaluated per statement.
- Portable detail: score source support and candidate absence as separate axes.

### AttributionBench

- URL: https://github.com/OSU-NLP-Group/AttributionBench
- Relevance: MED
- Balanced claim/passage labels with explicit false-attributable and
  false-not-attributable rates.
- Portable detail: use FP/FN framing for quote evidence, not only paper verdict.

## Q3. Semantic diff and alignment

### OmniDocBench block matching

- URL: https://github.com/opendatalab/OmniDocBench
- Relevance: HIGH
- Hungarian block alignment plus fuzzy rescue tolerates reorder and block
  split/merge. Whisker already contains a partial port in `match.py`.
- Portable detail: use block-window rescue only for `ambiguous` quote matches.

### chopdiff cosmetic token filtering

- URL: https://github.com/jlevy/chopdiff
- Relevance: MED
- LCS token diffs classify whitespace/punctuation/HTML-only operations as
  cosmetic.
- Portable detail: the pattern is portable with stdlib `difflib`; the dependency
  itself is unnecessary.

### semdiff

- URL: https://github.com/brian-benzinger/semdiff
- Relevance: MED
- Segment, align deterministically, then ask an LLM only about changed units.
- Portable detail: `ambiguous` is a routing state, not a forced verdict.

### RefChecker / verifiable-rag

- URLs:
  - https://github.com/amazon-science/RefChecker
  - https://github.com/firish/rag-rack
- Relevance: MED
- NLI produces entailment/neutral/contradiction or calibrated sentence support.
- Portable detail: potential later resolver for ambiguous semantic equivalence;
  not justified for the first fix because it adds model dependencies.

## Q4. Evidence benchmarks

### olmOCR-Bench dataset

- URL: https://huggingface.co/datasets/allenai/olmOCR-bench
- 1,403 pages, 7,010 deterministic tests, including presence, absence, reading
  order, table cells, and math symbols.
- Best schema for a WG21 quote-level holdout.

### QASPER

- URL: https://huggingface.co/datasets/allenai/qasper
- 5,049 questions over 1,585 scientific papers with paragraph/sentence evidence.
- Best academic-paper domain proxy for WG21.

### FEVER / SciFact

- URLs:
  - https://github.com/awslabs/fever
  - https://github.com/allenai/scifact
- Mature evidence-sentence precision/recall and rationale selection metrics.
- Portable detail: use evidence F1 over quote/source-page labels.

### opendataloader-bench

- URL: https://github.com/opendataloader-project/opendataloader-bench
- Document-level NID/TEDS/MHS ground truth.
- Useful complement, but not sufficient for quote-level absence.

## Q5. Deterministic then LLM patterns

### CRAG - explicit ambiguous band

- URL: https://github.com/nimone/crag
- Relevance: MED
- Correct / Incorrect / Ambiguous routing avoids binary trust at uncertain scores.
- Portable detail: ambiguous quote matches should abstain and demote, not count
  as absent.

### FActScore - dual signal

- URL: https://github.com/shmsw25/FActScore
- Relevance: MED
- Retrieve passages, judge atomic facts, optionally require an independent
  nonparametric signal.
- Portable detail: retain a missing quote only when source presence and candidate
  absence independently pass.

### AuditRAG / sourcecheck - provenance and abstention

- URLs:
  - https://github.com/aryanSharmaGithub/auditRag
  - https://github.com/aberaio/sourcecheck
- Relevance: MED
- Evidence is loaded from deterministic stores; unverifiable claims abstain
  instead of being promoted to unsupported/absent.
- Portable detail: sidecars need explicit reason codes and provenance.

## Deduplicated web conclusion

No surveyed system solves PDF-to-Markdown equivalence with one model judgment.
The recurring production pattern is:

1. deterministic source locate,
2. deterministic candidate locate,
3. explicit `present | absent | ambiguous`,
4. optional LLM/NLI only for ambiguous semantics,
5. per-quote provenance and abstention,
6. separate evidence precision/recall from document verdict.

The lowest-risk candidate for whisker is an olmOCR-style candidate-side check
built from existing `ground_spans`, `ground_page_quotes`, `rapidfuzz`, and
Markdown-aware normalization. No new dependency is justified by the web evidence.
