# LLM Evidence Reliability - Evidence Baseline

**Date:** 2026-07-16  
**Target:** `packages/whisker/src/whisker/tapetum_llm/`  
**Question:** How should whisker verify an LLM claim that source text is
missing from converted Markdown, while preserving legitimate formatting,
reordering, dehyphenation, front-matter, TOC-removal, and image exceptions?

## 1. Reproduced failure

The forced nine-PR replay (`#282, #283, #284, #285, #286, #290, #293,
#294, #295`) completed 9/9 evaluations, 0 errors, 0 model retries. The PDF
judge emitted 20 source-grounded "missing-content" quotes across four papers.
Direct candidate-side verification found:

- PR #284: 3/5 genuinely absent; 2/5 already present in Markdown.
- PR #285: 0/5 absent; all quoted prose already present.
- PR #290: 0/5 absent; all quoted date lines already present, some twice.
- PR #293: 5/5 genuinely absent (`constexpr` declarations).

Observed candidate-absence precision: **8/20 = 40%**. The verdict-level replay
still improved human agreement from 4/9 to 7/9 because the deterministic
`no_toc_leak` gate caught four defects and the LLM correctly recognized several
high-level problems. Evidence precision, not verdict recall, is the target.

## 2. Root cause in current code

`pdf_judge.py:513-520` turns model quotes into `EvidenceSpan`s and calls
`ground_spans(spans, pdf_text)`. This proves only:

> the quote (or a fuzzy approximation) exists in the source PDF text layer.

It never proves the inverse:

> the quoted content is absent from the candidate Markdown.

`PdfJudgeResult.to_sidecar_dict()` nevertheless labels every retained quote
`"present in PDF text layer, absent from markdown"` (`pdf_judge.py:401-404`).
That label overstates the verified fact.

The page escalation repeats the same one-sided proof:
`ground_page_quotes(..., page_text)` checks source-page presence only
(`pdf_judge.py:572-580`; `grounding.py:244-278`). The LLM prompt asks it to
compare both texts, but post-hoc verification trusts the model's absence claim.

## 3. Existing reusable machinery

- `ground_spans()` already implements exact monotonic token alignment, normalized
  substring matching, and a constrained fuzzy tier (`grounding.py:171-241`).
- `ground_page_quotes()` uses a length-relative edit budget for page quotes
  (`grounding.py:244-278`).
- `normalized_text()` is punctuation-insensitive and therefore unsuitable as
  the only absence oracle for sub-resolution defects.
- `content_recall()` and the per-page screen locate low-recall pages but cannot
  decide whether a specific quote is absent after legitimate reformats.
- Current policy is fail-closed for lane failure and advisory-only for LLM output.
  Any solution must preserve both.

## 4. Model boundary

The likely minimal architecture is a **two-sided deterministic verifier**:

1. source-presence check (existing),
2. candidate-presence check using exact/normalized/token-window matching,
3. retain as "missing" only when source presence succeeds and candidate presence
   fails at a deliberately chosen threshold,
4. distinguish `absent`, `present`, and `ambiguous` rather than forcing binary,
5. demote or annotate LLM verdicts when all deciding quotes are present/ambiguous.

This approach would be revised if research shows that mature open-source PDF/LLM
systems achieve materially better precision with a simpler method, or if a
labeled replay demonstrates candidate fuzzy matching suppresses genuine misses.

## 5. Local comparison corpus

Thirty-one existing local clones are available under
`packages/whisker/research/repos/`: camelot, docling, Dolphin, firecrawl,
grobid, html-to-markdown-go, html-to-markdown-py, html2text, img2table,
langextract, markdownify, marker, markitdown, mdream, MinerU,
node-html-markdown, nougat, olmocr, opendataloader-bench-tmp,
opendataloader-pdf, pandoc, PDF-Extract-Kit, pdf-to-markdown, pdfplumber,
PyMuPDF, pymupdf4llm, surya, tabula-java, tabula-java-tmp, turndown,
unstructured.

The directory is gitignored. Agents must use explicit paths, direct reads, or
`rg --no-ignore --no-ignore-vcs`; ignore-respecting search may report it empty.

## 6. Research constraints

- Research only. No production code changes in this run.
- Any later code change stays inside `packages/whisker/`.
- Prefer existing code and stdlib; no new dependency without demonstrated need.
- LLM remains advisory and never changes `whisker --gate`.
- Claims require `file:line`, reproduced runtime evidence, or a URL.
- Separate source-grounding, candidate-absence, semantic equivalence, and
  verdict policy. Do not blur them into one "grounded" boolean.

## 7. Thirty-persona roster

1. Source-Presence Auditor
2. Candidate-Absence Auditor
3. Bidirectional Entailment Designer
4. Exact-Span Alignment Specialist
5. Fuzzy-Matching Threshold Auditor
6. Token-Window Retrieval Designer
7. Normalization Loss Auditor
8. Dehyphenation and Line-Wrap Specialist
9. Markdown-Markup Equivalence Specialist
10. Table-Semantics Specialist
11. Code-Block Fidelity Specialist
12. Math and Unicode Specialist
13. TOC and Page-Furniture Specialist
14. Front-Matter Migration Specialist
15. Figure and Caption Specialist
16. Reading-Order and Duplication Specialist
17. Claim-Schema Designer
18. Evidence-Provenance Designer
19. LLM-Judge Calibration Skeptic
20. Retrieval-Augmented Verification Analyst
21. NLI and Entailment Analyst
22. Information-Retrieval Metrics Analyst
23. Benchmark and Holdout Designer
24. False-Positive Hunter
25. False-Negative Hunter
26. Adversary-Evasion Analyst
27. Determinism Auditor
28. Performance and Complexity Auditor
29. Simplicity and Maintainability Skeptic
30. Steelman of the Current Design

## 8. Web questions

1. Which open-source PDF-to-Markdown or OCR systems use LLMs to verify missing
   content, and how do they validate evidence against both source and output?
2. Which open-source RAG/citation systems verify that a generated quote is
   supported by source and absent/contradicted in a target document?
3. Which text-diff, semantic-diff, or NLI methods robustly distinguish absence
   from reformatting, reordering, dehyphenation, and Markdown markup changes?
4. Which benchmarks measure evidence precision/recall for document conversion
   QA rather than only document-level quality?
5. Which mature systems use deterministic candidate generation followed by
   LLM adjudication, and what fail-closed policy do they apply?

## Required persona report template

```text
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
