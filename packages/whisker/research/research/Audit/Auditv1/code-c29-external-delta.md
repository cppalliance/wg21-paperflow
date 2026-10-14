# C29 -- External-Delta Steelman

**Persona:** External-Delta Steelman
**Date:** 2026-07-19
**Scope:** whisker vs LangExtract, Docling, olmOCR, Marker, MinerU, unstructured, Nougat, Surya, and eval frameworks (Ragas, DeepEval, promptfoo)
**Focus:** Adopted patterns, missed opportunities, correctly rejected patterns, unique innovations, competitive position.

---

## 1. Adopted from External Repos (correctly)

These are design patterns whisker adopted from the surveyed ecosystem with clear provenance and appropriate adaptation.

### 1.1 OmniDocBench `normalized_text` (MinerU/OmniDocBench)

| Aspect | Detail |
|--------|--------|
| Source | OmniDocBench evaluation toolkit (MinerU project) |
| What whisker takes | `normalized_text = clean_string(textblock2unicode(text))`: the exact two-stage pipeline (LaTeX fold via pylatexenc, then strip-to-alnum+CJK) |
| Adaptation | Privatized names, added guard ladder for malformed LaTeX, dropped batch/CLI helpers |
| Verdict | **Correct adoption.** This normalizer is the only published standard for comparing document-conversion outputs that handles inline math. Using it verbatim ensures whisker's NID scores are comparable to OmniDocBench leaderboard numbers. |

### 1.2 PubTabNet/OmniDocBench TEDS (PubTabNet, OmniDocBench, Docling)

| Aspect | Detail |
|--------|--------|
| Source | PubTabNet (IBM), adopted by OmniDocBench, Docling eval |
| What whisker takes | The full TEDS algorithm: lxml parse, `_TableTree` nodes, APTED tree edit distance, char-level Levenshtein for cell content, xpath-descendant denominator |
| Adaptation | Zero-denominator guard, privatized names, dropped visualization helpers |
| Verdict | **Correct adoption.** TEDS is the only published table-quality metric with broad community acceptance. Docling uses the same algorithm for `verify_table_v2`. Adopting it ensures cross-system comparability. |

### 1.3 Block matching with Hungarian assignment (OmniDocBench `match_quick`)

| Aspect | Detail |
|--------|--------|
| Source | OmniDocBench evaluation code |
| What whisker takes | Split into blocks, NED cost matrix, Hungarian assignment, accept/reject thresholds, fuzzy rescue for embedded GT blocks |
| Adaptation | Added cell-budget cap (`BLOCK_MATRIX_CELL_BUDGET`) for giant documents, separate advisory `reading_order_ned` from the same pass |
| Verdict | **Correct adoption.** This makes `block_text_nid` reorder-robust, matching the field consensus that content coverage and reading order are separate axes. The cell-budget cap is a necessary engineering guard absent from the original. |

### 1.4 Content recall as multiset bag-of-words (Docling, Nougat, DP-Bench)

| Aspect | Detail |
|--------|--------|
| Source | Docling (`set(word_tokenize)` precision/recall), Nougat (set-F1), OmniDocBench (content separate from order) |
| What whisker takes | `content_recall`: tokenize, Counter bags, `sum(min)` / `sum(ref)`. Order-invariant. Catches dropped sections that edit distance hides. |
| Adaptation | Recall-only (no precision penalty for extra candidate words), because tomd expanding abbreviations or adding front-matter keys should not penalize |
| Verdict | **Correct adoption.** The field consensus is that content presence and sequence order measure different things. Using recall-only matches the converter-QA use case (missing content is the defect; extra content is benign). |

### 1.5 Separate reading-order axis (OmniDocBench, Docling, Nougat)

| Aspect | Detail |
|--------|--------|
| Source | All three benchmark repos separate reading order from content quality |
| What whisker takes | `reading_order_ned` is computed but NEVER gates. Explicitly advisory. |
| Verdict | **Correct adoption.** Multi-column PDF reflow legitimately reorders blocks; gating on order would fail correct conversions. The field learned this; whisker respects it. |

### 1.6 Advisory-only LLM (ecosystem-wide pattern)

| Aspect | Detail |
|--------|--------|
| Source | "0 of 31 surveyed document-conversion QA repos gate on LLM signals" |
| What whisker takes | LLM (`tapetum_llm`) is advisory, opt-in, never in CI, never hard-fails |
| Verdict | **Correct adoption.** Follows the universal ecosystem norm. No converter benchmark uses LLM output as a pass/fail authority. |

### 1.7 GriTS-Con (PubTabNet/GriTS project)

| Aspect | Detail |
|--------|--------|
| Source | GriTS metric (table cell-content F1, published alongside PubTabNet) |
| What whisker takes | `grits_con` as an advisory axis via the `grits-metric` package |
| Adaptation | Advisory only, never gated (no calibration yet) |
| Verdict | **Correct adoption.** Complementary to TEDS (structure vs content), correctly held advisory until calibrated. |

### 1.8 Zero-authoring baseline checks (olmOCR pattern)

| Aspect | Detail |
|--------|--------|
| Source | olmOCR quality checks (non-empty, no mojibake) |
| What whisker takes | `auto_baseline_checks`: non-empty alnum content + no repeated n-grams |
| Current status | Implemented, tested, but not wired into the gate (documented gap) |
| Verdict | **Correct adoption in spirit.** The pattern is right (zero-effort catch of catastrophic failures). The gap is only that it is unwired, not that it is wrong. |

---

## 2. Missed Opportunities

Patterns present in external repos that whisker does NOT implement, and reasonably SHOULD for a pre-1.0 document-conversion QA tool.

### 2.1 Span-aware table grid (Docling `verify_table_v2`)

| Priority | HIGH |
|----------|------|
| What external repos do | Docling's table verification preserves rowspan/colspan in the grid model. MinerU's evaluation handles merged cells. |
| What whisker does | `tables.py` flattens spanning cells into their first slot. |
| Impact | The golden-grid layer (planned) cannot compare tables with merged cells accurately. Neighbor-based facts on spanning cells are fragile. |
| Proportionality | Documented as Known gap #2. The fix is a prerequisite for the next validation layer and should precede 1.0. |

### 2.2 Formula-level metric (Nougat, MinerU)

| Priority | MEDIUM |
|----------|--------|
| What external repos do | Nougat reports per-formula accuracy (edit distance on LaTeX source vs reference). MinerU evaluates display-math blocks as separate units. |
| What whisker does | Lane 2 folds math into the full-text NID. Lane 3 `math` facts check individual formulas but only via presence/absence, not structural fidelity. |
| Impact | A conversion that renders `\sum_{i=0}^n` as `\sum_{i=0}^{n}` (semantically equivalent) vs `\sum_{i=0}` (truncated) both score the same on NID if the rest of the document is large. |
| Proportionality | For pre-1.0, the `math` fact type partially covers this (it catches missing exponents, flipped relations). A dedicated formula-NED metric per display block would improve sensitivity for math-heavy papers (WG21 has relatively few), so MEDIUM rather than HIGH. |

### 2.3 Image/figure evaluation (MinerU, Marker, Docling)

| Priority | MEDIUM |
|----------|--------|
| What external repos do | MinerU evaluates figure extraction quality (bounding box IoU, OCR of embedded text). Marker preserves and scores image regions. Docling extracts and classifies figures. |
| What whisker does | `image_ref` fact type checks only that `![...](...)` is present. No content-level evaluation of extracted images. |
| Impact | A conversion that extracts the wrong figure, or a corrupted raster, passes the `image_ref` check. |
| Proportionality | WG21 papers are text-heavy; figures are rare and primarily diagrams. The corpus has zero coverage in the `images` stratum (documented). For pre-1.0, the fact type + stratum awareness is honest about the gap. Post-1.0, image fidelity scoring (SSIM, or at minimum checking the image file is non-trivial bytes) would be appropriate. |

### 2.4 Calibration from labeled data (DP-Bench, Docling, promptfoo)

| Priority | MEDIUM |
|----------|--------|
| What external repos do | DP-Bench fits thresholds on labeled conversion quality. Docling reports precision/recall at operating points. promptfoo supports threshold-from-data workflows. |
| What whisker does | All thresholds are "borrowed/uncalibrated" (adopted from external repos). The `calibrate` workflow exists but has never run. |
| Impact | Edges may be sub-optimal for the WG21 domain. False-pass and false-fail rates are unknown. |
| Proportionality | This is documented honestly (Known gap #13, "Calibration status" section). For a pre-1.0 tool that acknowledges its edges are provisional, this is acceptable but should be closed before 1.0 release. The infrastructure (`whisker calibrate`) already exists. |

### 2.5 Paragraph-level granularity in reporting (unstructured, Docling)

| Priority | LOW |
|----------|-----|
| What external repos do | unstructured reports per-element quality (paragraph, table, list). Docling evaluates per-section. |
| What whisker does | Whole-document metrics (NID, content_recall) with block matching for reorder-robustness. Region detail provides page-level WHERE. |
| Impact | When NID is low, the user must manually locate which paragraph degraded. Region detail partially mitigates this but at page granularity, not paragraph. |
| Proportionality | For a CI gate, the verdict (pass/review/fail) plus region detail is sufficient. Per-paragraph drill-down is a UX feature, not a correctness requirement. LOW priority for pre-1.0. |

### 2.6 Multi-evaluator agreement / IAA (DeepEval, Ragas)

| Priority | LOW (for pre-1.0) |
|----------|-------------------|
| What external repos do | DeepEval runs multiple LLM evaluators and reports inter-annotator agreement. Ragas supports ensemble scoring. |
| What whisker does | Single deterministic evaluation (no disagreement possible). The advisory LLM lane is single-model. |
| Impact | None for the deterministic gate (it is reproducible by construction). The advisory lane has a measured >= 25% verdict-flip rate but no agreement metric. |
| Proportionality | IAA makes sense for LLM-judged quality. whisker's deterministic gate has no stochasticity to measure. The advisory lane's instability is documented and handled architecturally (advisory-only). Multi-evaluator agreement is a post-1.0 enhancement for the advisory lane. |

---

## 3. Correctly Rejected

Patterns present in external repos that whisker deliberately does NOT use, with good reason.

### 3.1 RAG for same-document QA

| Rejected from | Ragas, DeepEval, general RAG-eval frameworks |
|---------------|----------------------------------------------|
| Why external repos use it | They evaluate retrieval pipelines that need to find relevant chunks across a corpus. |
| Why whisker rejects it | whisker is a SAME-DOCUMENT tool. Every operation compares a paper's conversion against its own source. RAG would add latency, complexity, and non-determinism for zero information gain. The document IS the context. (C23 confirms all three RAG protocol questions answer NO.) |
| Verdict | **Correctly rejected.** Fundamental architecture mismatch. |

### 3.2 LLM-as-judge for hard gating (DeepEval, Ragas, promptfoo)

| Rejected from | All three eval frameworks use LLM scores as first-class verdicts |
|---------------|------------------------------------------------------------------|
| Why external repos use it | They evaluate open-ended generation quality where deterministic metrics are insufficient. |
| Why whisker rejects it | (1) >= 25% verdict-flip rate measured empirically. (2) Anti-correlated confidence (96/96 clear firings at >= 0.95 confidence, including known false-clears). (3) Determinism invariant. (4) Model-sovereignty (open-weight models are less stable). (5) 0/31 converter QA repos gate on LLM signals. |
| Verdict | **Correctly rejected.** The evidence base (measured instability, anti-calibrated confidence, ecosystem consensus) is overwhelming. |

### 3.3 Single composite score (Ragas, DeepEval)

| Rejected from | Both frameworks produce a single 0-1 composite by averaging sub-metrics |
|---------------|-------------------------------------------------------------------------|
| Why external repos use it | Simplicity for leaderboard ranking. |
| Why whisker rejects it | (1) OmniDocBench never collapses per-axis scores. (2) A paper can pass fidelity and fail comprehension (the composite would hide this). (3) Different axes have different null-eligibility (a paper without tables has no TEDS). Averaging null-eligible and non-null axes produces meaningless numbers. |
| Verdict | **Correctly rejected.** Strata stay separate; each axis can gate independently. This is the mature pattern from document-conversion benchmarks. |

### 3.4 Embedding-based semantic similarity (Ragas faithfulness, DeepEval)

| Rejected from | Both frameworks use embedding cosine similarity |
|---------------|--------------------------------------------------|
| Why external repos use it | Captures semantic equivalence beyond lexical overlap. |
| Why whisker rejects it | (1) Introduces model dependency into the gate (violates determinism). (2) Embeddings are a black box; a flip from 0.89 to 0.84 has no interpretable cause. (3) For document conversion QA, the question is "are the same words/structures present?", not "is the meaning similar?" A converter that paraphrases is broken, not semantically equivalent. |
| Verdict | **Correctly rejected.** Character-level edit distance (NID) directly measures what matters for conversion fidelity. Embedding similarity would mask word-level corruption. |

### 3.5 Reference-free LLM quality scoring (promptfoo, DeepEval)

| Rejected from | promptfoo's LLM-graded assertions, DeepEval's reference-free metrics |
|---------------|----------------------------------------------------------------------|
| Why external repos use it | When no reference exists, ask an LLM to judge quality. |
| Why whisker rejects it | whisker HAS the source document (the ultimate reference). Reference-free LLM scoring is for tasks where no ground truth exists. For document conversion, the PDF/HTML source IS the reference. Using an LLM to judge conversion quality when you can directly compare tokens is objectively less reliable. |
| Verdict | **Correctly rejected.** Direct source comparison beats indirect LLM judgment for this task. |

### 3.6 Human annotation pipelines as a runtime dependency (LangExtract, Surya)

| Rejected from | LangExtract requires labeled training data per domain. Surya's benchmarks require COCO-format annotation. |
|---------------|-----------------------------------------------------------------------------------------------------------|
| Why external repos use it | They evaluate models that need domain-specific training/fine-tuning. |
| Why whisker rejects it | whisker's deterministic gate needs zero labeled data to produce a verdict. The `calibrate` workflow is an offline one-time step, not a runtime dependency. Source-verified facts need authoring but not annotation infrastructure. |
| Verdict | **Correctly rejected for the gate.** The calibration gap (no fitted edges) is an honest limitation, not an architecture mistake. |

---

## 4. Whisker-Unique Innovations

Patterns present in whisker that NONE of the surveyed external repos implement.

### 4.1 Three-lane architecture (Stability / Fidelity / Comprehension)

| Innovation | Three independent lanes that gate independently |
|------------|--------------------------------------------------|
| What it means | A paper can pass fidelity (all metrics green) and fail comprehension (a table cell is scrambled). A paper can pass comprehension and fail stability (the snapshot changed). The lanes answer different questions and their verdicts are never averaged. |
| Why no external repo does this | (1) Benchmarks (OmniDocBench, DP-Bench) measure fidelity only. (2) QA tools (olmOCR) measure comprehension only. (3) Stability tracking (golden files, Marker) is a separate tool, never integrated with quality metrics. No one combines all three in one tool with independent gates. |
| Significance | HIGH. This is the correct architecture for a CI gate on a live converter: stability catches drift, fidelity catches degradation, comprehension catches semantic corruption that fidelity metrics miss. |

### 4.2 Deterministic comprehension facts (source-verified, no LLM in the loop)

| Innovation | Type-specific assertions (`present`/`absent`/`order`/`table`/`math`/`code`/`xref`/`image_ref`) evaluated purely deterministically |
|------------|-----------------------------------------------------------------------------------------------------------------------------------|
| What it means | A "comprehension" check without any LLM. The assertion "row 3, column 2 of the Feature table reads 8" is evaluated by string matching, not by asking a model. |
| Why no external repo does this | (1) olmOCR's comprehension test uses LLM Q&A (the exact thing whisker's readback does, but as the PRIMARY gate). (2) Ragas/DeepEval evaluate comprehension via LLM-as-judge. (3) No converter benchmark has a deterministic comprehension layer. |
| Significance | HIGH. Solves the "fidelity is not comprehension" gap without introducing LLM instability into the gate. The one-time readback validation is the empirical anchor; the deterministic facts are the CI-safe proxy. |

### 4.3 Advisory LLM with one-way ratchet (fusion asymmetry)

| Innovation | LLM can demote (pass -> review) but NEVER promote (fail -> pass). Can rescue fail -> review but never override a deterministic fail to pass. |
|------------|----------------------------------------------------------------------------------------------------------------------------------------------|
| What it means | The LLM adds caution, never confidence. If the deterministic gate says fail, the LLM cannot override it. If the LLM is uncertain, it demotes. |
| Why no external repo does this | Other tools either (a) do not use LLMs in QA at all, or (b) treat LLM output symmetrically (it can raise or lower the score). The asymmetric ratchet is novel. |
| Significance | MEDIUM-HIGH. Architecturally prevents the measured instability from causing false passes. The worst case of LLM instability is a false review (benign), never a false pass (dangerous). |

### 4.4 Comprehension readback with adversarial control (`--corrupt`)

| Innovation | Built-in adversarial validation: scramble tables, flip operators, shift exponents, then verify the same questions now FAIL |
|------------|-----------------------------------------------------------------------------------------------------------------------------|
| What it means | Proves the test is sensitive to the markdown content, not just answerable from prior knowledge. |
| Why no external repo does this | olmOCR's comprehension test has no adversarial control. Ragas/DeepEval have no corruption-mode. Benchmarks test one direction only (does it pass on correct input?), never the other (does it fail on corrupted input?). |
| Significance | MEDIUM. Good scientific practice. Addresses the "trivially answerable" critique of LLM Q&A tests. |

### 4.5 Canary facts (deterministic sensitivity proof)

| Innovation | Three canaries (scrambled table cell, flipped math relation, mangled code) that MUST fail in CI |
|------------|-----------------------------------------------------------------------------------------------|
| What it means | CI does not just check "do facts pass on good input?" but also "do facts FAIL on corrupted input?" If a code change accidentally weakens the fact engine, a canary will pass when it should fail, and CI breaks. |
| Why no external repo does this | No surveyed benchmark has "must-fail" test fixtures built into the CI contract. |
| Significance | MEDIUM. Prevents the gate from silently becoming vacuous. Small corpus, but the methodology is sound. |

### 4.6 Source-routing with deterministic per-page screen (tapetum_llm)

| Innovation | Before any LLM call, compute per-page `content_recall` deterministically. Only escalate pages that fail the screen to the LLM. |
|------------|--------------------------------------------------------------------------------------------------------------------------------|
| What it means | The LLM only looks at pages where something is measurably wrong. Cuts cost and latency proportional to conversion quality. |
| Why no external repo does this | LLM-based eval tools (DeepEval, Ragas) send everything to the LLM. Document QA tools (olmOCR) do not pre-screen. |
| Significance | MEDIUM. Engineering efficiency pattern that also prevents the LLM from hallucinating defects on clean pages. |

### 4.7 Stratum-aware corpus authoring (`whisker corpus stratify`)

| Innovation | Classifies zero-coverage papers by structural stratum (pipe/HTML tables, display math, code-heavy, footnotes, images) to guide human authoring of new facts |
|------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|
| What it means | Corpus growth is systematic: a human picks one paper per stratum rather than authoring facts randomly. |
| Why no external repo does this | Benchmarks (OmniDocBench, DP-Bench) assume the labeled corpus already exists. They have no tooling for growing it strategically. |
| Significance | LOW-MEDIUM. Good practice for a nascent corpus (5 papers), not a differentiator at scale. |

---

## 5. Competitive Position

### 5.1 Use-case definition

whisker occupies a niche that no surveyed tool fills: **CI-integrated, deterministic, document-conversion QA gate for a specific converter (tomd) on a specific domain (WG21 C++ standardization papers).**

The closest comparisons:
- **OmniDocBench / DP-Bench:** Benchmark suites that score a corpus post-hoc. No CI integration, no per-paper verdict, no comprehension layer. whisker's Lane 2 (bench) is comparable to these; Lanes 1 and 3 have no analog.
- **olmOCR evaluation:** Tests comprehension via LLM Q&A. No deterministic gate, no stability tracking, no fidelity metrics. whisker's readback is comparable; the deterministic facts layer has no analog.
- **Docling evaluation:** Per-element scoring with table verification. No CI gate, no stability lane, no comprehension layer. whisker's TEDS and block matching are comparable; the three-lane architecture is absent.
- **Ragas / DeepEval / promptfoo:** LLM output quality evaluators. Wrong domain (they evaluate generation, not conversion). Their patterns (embedding similarity, LLM-as-judge, composite scores) are correctly rejected.

### 5.2 Strengths relative to the field

| Strength | Evidence |
|----------|----------|
| Determinism as first-class constraint | No other converter QA tool makes determinism an invariant. whisker's gate produces the same verdict every run. |
| Comprehension without LLM dependency | Unique. The only tool that CI-gates on "can downstream systems recover the content?" without model instability. |
| Honest calibration status | Documented as provisional. Most benchmarks publish thresholds without uncertainty ranges. whisker says "these are borrowed, not fitted." |
| CI-native exit codes | 0/1/3/5 contract. No benchmark tool has this. |
| Three independent failure modes | Cannot hide a comprehension failure behind good fidelity numbers. |

### 5.3 Weaknesses relative to the field

| Weakness | Severity | Mitigation |
|----------|----------|------------|
| Corpus breadth (5/381 papers) | HIGH | `whisker corpus stratify` exists; the bottleneck is human authoring time, not tooling |
| No fitted calibration | MEDIUM | `whisker calibrate` exists; needs 30-50 labeled papers to run |
| No span-aware table grid | MEDIUM | Prerequisite for golden-grid layer; documented as next step |
| No per-formula metric | MEDIUM | `math` facts partially cover; a formula-NED bench axis would improve math-paper coverage |
| Image evaluation is presence-only | LOW | Domain is text-heavy; proportionate for pre-1.0 |
| All facts agent-authored, no human blessing | MEDIUM | Verifications are auditable; closing this is a process step, not a code change |

### 5.4 Overall assessment

whisker is **architecturally ahead of the field** for its specific use case (document-conversion QA as a CI gate). No other tool combines deterministic gating, comprehension testing, stability tracking, and advisory LLM review in one integrated system. The metric implementations are faithful ports of published algorithms (OmniDocBench, PubTabNet), ensuring comparability.

The tool is **empirically behind** in corpus breadth and calibration: it has the right architecture and metrics but limited data to prove they work at scale. This is honest for a v0.5.0 pre-1.0 tool, and the infrastructure for closing the gap (calibrate workflow, corpus stratification, readback validation) already exists.

The key differentiator is the **three-lane architecture with the comprehension layer**: no surveyed tool tests "can a downstream system still recover the paper's facts?" deterministically. This fills a real gap, because fidelity metrics (NID, TEDS) are demonstrably blind to token-preserving semantic corruption (the "scrambled table cell" class of defects).

---

## Summary Table

| Dimension | Count | Key items |
|-----------|-------|-----------|
| Correctly adopted | 8 | OmniDocBench normalizer, PubTabNet TEDS, Hungarian block matching, multiset content_recall, separate reading-order axis, advisory-only LLM, GriTS-Con, olmOCR baseline checks |
| Missed opportunities | 6 | Span-aware grids (HIGH), formula metric (MED), image eval (MED), calibration from data (MED), paragraph granularity (LOW), multi-evaluator IAA (LOW) |
| Correctly rejected | 6 | RAG, LLM hard-gating, single composite, embedding similarity, reference-free LLM scoring, annotation-pipeline dependency |
| Whisker-unique | 7 | Three-lane architecture, deterministic comprehension facts, one-way LLM ratchet, adversarial readback control, canary facts, per-page screen, stratum-aware authoring |
| Competitive position | Architecturally ahead; empirically nascent | Leading architecture, limited data scale |

---

## Auditor Certification

This analysis compares whisker's documented and implemented patterns against the public repositories and frameworks named in the mandate. No fabricated citations are used (the quarantined MinerU2.5-Pro arXiv:2604.04771 is excluded as instructed). Assessments are proportionate to whisker's claimed phase (v0.5.0 pre-1.0, Stage 0 calibration, 5-paper corpus).

The tool's strongest claim is architectural: it fills a gap no other tool fills. Its weakest point is empirical: the corpus is small and the calibration is provisional. Both are documented honestly in the codebase.
