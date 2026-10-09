# 05 - Web Finding Cards

## Q1: Golden fixture validation in document-conversion QA

- **docx-parse-eval — differential .docx evaluation harness** (HIGH)
  URL: https://pypi.org/project/docx-parse-eval/
  Gold is built as an independent OOXML reading (python-docx reference adapter), not from the parser under test. `reconcile` does a field-level diff of blessed gold against a freshly re-bootstrapped draft to catch gold drift or inherited extractor bugs. `source_sha256` identity checks and conservation/TEDS flags make discrepancies bilateral defects.

- **olmOCR-Bench — source-anchored binary unit tests** (HIGH)
  URL: https://github.com/allenai/olmocr/tree/main/olmocr/bench
  Avoids fuzzy golden-reference matching; each of 7,010 tests is a deterministic pass/fail property checked on converter output against facts derived from the source PDF. Ground-truth anchors include TeX source for arXiv math, Library of Congress human transcriptions. Pattern: never bless converter output as gold; derive tests from independent source artifacts.

- **ParseBench — human-verified enterprise parsing benchmark** (HIGH)
  URL: https://arxiv.org/html/2604.08538v3
  Ground truth via two-pass pipeline: frontier VLMs draft, human annotators correct until convergence. Rules auto-generated from human-edited Markdown. Scalable pattern: machine draft, human arbitration against source, then rule-based checks independent of any frozen converter snapshot.

- **Docxodus — blessed WmlComparer + LibreOffice oracle** (MED)
  URL: https://github.com/JSv4/Docxodus/pull/238/files
  Uses a blessed WmlComparer oracle and headless LibreOffice as independent references on real source contracts. Inherited-bug detection: treat third-party implementations as oracles and fail when blessed output diverges.

- **stella — differential DOCX parser scaffold vs python-docx** (MED)
  URL: https://github.com/stella/stella/commit/da601b1f7809553cebaaf8cbee3dd1e913e78174
  Cross-checks parser output against python-docx by projecting both into normalized JSON and structurally diffing. Pattern: keep a second independent reader; treat any golden built without cross-check as suspect.

## Q2: Sub-resolution defect detection strategies

- **olmOCR-Bench: Pass/Fail Unit Tests Instead of Soft Metrics** (HIGH)
  URL: https://arxiv.org/abs/2502.18443v3
  Explicitly rejects aggregate soft metrics (edit distance, ROUGE, BLEU) because they fail to reveal fine-grained yet semantically critical errors (subscript vs superscript: $x_i$ vs $x^i$). Uses ~7,000 deterministic pass/fail unit tests. A single wrong character fails an entire test even when corpus-level scores look fine.

- **ParseBench: Rule-Based Verification at Word, Sentence, and Digit Granularity** (HIGH)
  URL: https://arxiv.org/html/2604.08538v1
  167K+ deterministic rules across tables, charts, formatting, content faithfulness. Content Faithfulness applies recall/precision at word, sentence, and digit frequency levels. Catches OCR digit swaps (6→8) that aggregate metrics dilute across a page. Single-token defects visible as localized failures.

- **docx-parse-eval: Differential Testing with Field-Level CI Gates** (HIGH)
  URL: https://pypi.org/project/docx-parse-eval/
  Projects reference and parser output into shared schema, diffs with conservation metrics and per-field flags. Any fired flag is a guaranteed discrepancy. bless/reconcile workflow separates real regressions from intentional fixture updates.

- **LLMORPH: Metamorphic Testing to Catch Bugs Aggregate Oracles Miss** (MED)
  URL: https://arxiv.org/abs/2603.23611
  Defines Metamorphic Relations: input transformations under which outputs should remain consistent. Across 561K test executions, MT found ~18% failure rate and detected bugs traditional testing missed. Probes invariant properties that can fail on a single token while headline metrics stay unchanged.

- **kapa.ai PDF Converter Benchmark: Element-Level Matched Diff Scoring** (MED)
  URL: https://docs.kapa.ai/research/pdf-converter-benchmark
  Hungarian assignment on normalized edit distance for headers/tables, then cell/header-level scoring. Unmatched elements affect precision/recall directly. Weighted group scores (headers at 1.5x) let teams prioritize structural defects aggregate metrics underweight.

## Q3: LLM-as-judge calibration techniques

- **VERDI: Single-Call Confidence via Decomposed Inference** (HIGH)
  URL: https://arxiv.org/html/2605.11334v1
  Targets structured document-comparison judges following evidence+claim→analysis→verdict. Extracts Step-Verdict Alignment, Claim-Level Margin, and Evidence Grounding Score from reasoning trace (not logprobs). Platt-scales into calibrated confidence. AUROC 0.73-0.88 on production factual rubrics.

- **Deep-Research Citation Benchmark: FP/FN Directional Bias** (HIGH)
  URL: https://arxiv.org/html/2607.08700
  Benchmarks 8 LLM judges on 1,248 human-reviewed rubric decisions. Shows judges with similar F1 differ sharply in pass-rate drift, FP rate, FN rate. Calibration: label a gold set, measure per-dimension sensitivity/specificity, pick judges by asymmetric FP/FN costs.

- **RULERS: Evidence-Grounded Text Evaluation** (HIGH)
  URL: https://arxiv.org/html/2601.08654
  Compiler-executor framework locking rubrics into versioned executable specs, schema-constrained decoding, verbatim evidence quotes required. Evidence gate caps scores when citation count below minimum, blocking high scores without grounding. Post-hoc Wasserstein-based calibration aligns to human ordinal scales.

- **Bias-Adjusted LLM-as-Judge Estimation** (HIGH)
  URL: https://arxiv.org/html/2511.21140v2
  Plug-in bias-adjusted estimator θ̂ = (p̂ + q̂₀ − 1) / (q̂₀ + q̂₁ − 1) and confidence intervals accounting for uncertainty in both test and calibration sets. Adaptive allocation of calibration samples between correct/incorrect classes.

- **Linear Probes for LLM Judge Uncertainty** (MED)
  URL: https://aclanthology.org/2026.acl-industry.14/
  Lightweight linear probes on reasoning judge's hidden states with Brier-score loss. Outperforms verbalized confidence. Requires model internals access. 10x lower compute than multi-generation methods.
