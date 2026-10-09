# P13 — Comprehension-vs-Fidelity Evaluation Researcher

**Persona:** 13 (Cluster C — Extraction quality & eval science)  
**Date:** 2026-07-18  
**Scope:** External comprehension-eval science and audit criteria only. No whisker code inspection, no whisker verdict.

---

## 1. Question restated

How should a professional-grade document-extraction QA audit **separate fidelity** (resemblance to a reference artifact: string overlap, edit distance, tree similarity to gold markdown) from **comprehension** (whether a downstream reader can recover the document's facts from the converted text alone), and what external methods exist to **evaluate comprehension** via fact-recovery QA, blind read-back, and adversarial corrupt-and-recheck controls—while rejecting round-trip / regenerate-similar-text tests as comprehension proxies?

---

## 2. Proposed audit criteria

### C1 — Explicit fidelity vs comprehension construct separation

**Criterion:** The eval harness MUST report fidelity metrics and comprehension metrics on **separate axes**, with written definitions that forbid treating one as a proxy for the other. Fidelity answers "does output resemble the reference representation?"; comprehension answers "can verified facts be recovered from output alone?"

**How to measure:** Review the eval spec and scorecard template. Pass if (a) at least one fidelity metric (e.g., normalized edit distance, TEDS/S-TEDS against gold markdown) and at least one comprehension metric (see C2–C4) are defined, scored, and reported independently; (b) no single composite collapses them without per-axis breakdown; (c) construct definitions cite the semantic-vs-surface distinction.

**Audit method:** Metric construct-validity audit (§5.4).

**Scoring-design hook:** Feeds §6.1 per-dimension composite (extraction-quality/eval cluster); supports §6.2 hard gate "disproven construct validity used as a gate."

**Gaming vector:** Rename a fidelity metric "comprehension" without changing the formula (e.g., high ROUGE reported as comprehension).

**Anti-gaming guard:** Require the rubric to name the **evidence source** each metric uses (reference text vs extracted text only vs downstream QA labels) and reject any metric whose inputs include both output and reference string alignment as a comprehension score.

**Evidence grade:** A (multiple Tier-1 converging sources).

**Sources:** Maynez et al. (ACL 2020); Fabbri et al. / SummEval (TACL 2021); Liu et al., FFCI (JAIR 2023); Poznanski et al., olmOCR (arXiv 2502.18443, 2025).

---

### C2 — Closed-book fact-recovery QA battery (primary comprehension metric)

**Criterion:** Comprehension MUST be measured by a **closed-book QA battery**: questions with verified gold answers, answered using **only** the extracted markdown (no PDF, no gold reference text, no source HTML). Score = fraction of questions where the recovered answer matches gold under a documented normalization policy.

**How to measure:** Corpus of N≥50 documents (stratified by modality: prose, tables, math, lists, headers) each with K≥5 fact-level questions authored from human-verified source reading (not from the converter output). Run a fixed QA procedure (human annotators and/or a pinned, disclosed QA model). Report per-question accuracy, per-document accuracy, and per-modality breakdown. Fail if QA inputs include any channel other than extracted text.

**Audit method:** Metric construct-validity audit (§5.4) + comparative benchmarking against exemplar protocols (§5.3).

**Scoring-design hook:** §6.1 weighted dimension; candidate §6.2 hard gate if comprehension QA falls below a calibrated operating point (paired with P16).

**Gaming vector:** Questions generated from the converter output (circularity) or copied from reference markdown (smuggles fidelity into comprehension).

**Anti-gaming guard:** Question provenance MUST be independent of the system under test (annotation protocol per P11); holdout question sets; spot-audit that questions are answerable from source PDF but not trivially from string overlap alone.

**Evidence grade:** A.

**Sources:** Durmus et al., FEQA (ACL 2020); Wang et al., QAGS (ACL 2020); RealDocBench (arXiv 2606.07401, 2026); Ragas Faithfulness metric docs (2025-12-11).

---

### C3 — Claim-decomposition faithfulness score (automated comprehension adjunct)

**Criterion:** An automated **claim-level faithfulness** score MUST decompose extracted text into atomic claims and verify each against a trusted context. For extraction QA, the trusted context is either (a) the source document at eval time, or (b) for blind read-back variants, pre-authored gold fact statements—not the reference markdown string.

**How to measure:** Implement the Ragas/FEQA pattern: (1) segment output into statements; (2) for each statement, NLI or QA verification against context; (3) score = supported claims / total claims. Report separately from edit-distance fidelity. Disclose verifier model/version. Require correlation spot-check with human factuality labels on a fixed slice (≥30 summaries/pages).

**Audit method:** Metric construct-validity audit (§5.4).

**Scoring-design hook:** §6.1 sub-criterion under comprehension; §6.4 anti-gaming (LLM verifier outputs are advisory, cannot sole-gate—consistent with frame §6.4).

**Gaming vector:** Verifier tuned on the same outputs; claim segmentation that merges errors into uncheckable blobs.

**Anti-gaming guard:** Pin verifier; publish segmentation prompt; require human-correlation floor on a frozen audit slice; never use the evaluated converter as verifier.

**Evidence grade:** A.

**Sources:** Durmus et al., FEQA (ACL 2020); Ragas Faithfulness (docs.ragas.io, 2025-12-11); Maynez et al. (ACL 2020) Table 9 (QA/entailment vs ROUGE correlation).

---

### C4 — Blind read-back protocol (human or hybrid)

**Criterion:** The audit MUST include a **blind read-back** arm: evaluators (human or structured QA) receive **only** the extracted markdown and a fact questionnaire; they do NOT receive the source PDF/HTML or reference markdown. Comprehension = successful fact recovery under blind conditions.

**How to measure:** Protocol document specifies: blinding procedure, question types (fact, relation, table cell, numeric, section scope), adjudication rules, and inter-annotator agreement reporting (kappa/alpha). Minimum one human-blind pass on a stratified subset OR a deterministic QA pipeline with human validation on ≥10% of items. Report blind accuracy separately from any open-book or reference-aligned score.

**Audit method:** Documentation-completeness audit (§5.9) of the protocol + metric construct-validity audit (§5.4) of blind vs open-book gap.

**Scoring-design hook:** §6.1 comprehension dimension; §6.3 evidence grade escalates when blind human pass exists.

**Gaming vector:** "Blind" evaluators given structural hints (section titles matching source layout) or questions so literal that token search passes.

**Anti-gaming guard:** Include **paraphrased** questions (different wording from source strings); require relation and multi-hop items; report blind-minus-open-book delta—large delta signals fidelity-without-comprehension.

**Evidence grade:** B (method synthesized from Tier-1 QA/factuality literature + Tier-1 field-QA benchmarks; blind read-back naming is operational, not a single canonical paper title).

**Sources:** RealDocBench QA track (arXiv 2606.07401, 2026); FEQA workflow (ACL 2020); Hermann et al., machine reading / CNN-DM (cited in SummEval, TACL 2021).

---

### C5 — Round-trip and surface-similarity tests excluded as comprehension gates

**Criterion:** **Regenerate-similar-text round-trips** (extract → regenerate → compare similarity) and **reference edit-distance / ROUGE-only** thresholds MUST NOT serve as comprehension gates or substitutes for fact-recovery QA.

**How to measure:** Inspect gate definitions and CI thresholds. Fail if any comprehension gate uses only: round-trip translation similarity, paraphrase BLEU/ROUGE, embedding cosine to reference, or "regenerate markdown from summary and diff" without fact verification.

**Audit method:** Anti-gaming / Goodhart stress (§5.7) + construct-validity audit (§5.4).

**Scoring-design hook:** §6.2 hard gate candidate—using round-trip similarity as comprehension is an automatic methodology fail.

**Gaming vector:** Optimize for lexical overlap with gold markdown while corrupting relations (swap table cells, flip inequality signs) that round-trip metrics miss.

**Anti-gaming guard:** Require documented **failure examples** where fidelity passes and comprehension fails (olmOCR-style math subscript/superscript swaps; RealDocBench field mismatch under high OCR similarity). Maintain a canary set.

**Evidence grade:** A.

**Sources:** Maynez et al. (ACL 2020) Table 9; Poznanski et al., olmOCR §3 (edit distance vs semantic math errors, 2025); Revisiting Round-Trip Translation (arXiv 2004.13937, 2020); ParseBench (arXiv 2604.08538, 2026) on text-similarity missing agent-critical failures.

---

### C6 — Binary semantic unit tests for high-stakes facts (comprehension primitives)

**Criterion:** Comprehension eval MUST include **deterministic pass/fail semantic predicates** on extracted output for facts that must not be soft-scored: presence/absence of critical strings, reading-order constraints, table cell neighborhood relations, math symbol orientation—analogous to software unit tests, not fuzzy gold diff.

**How to measure:** Catalog of predicate types (presence, absence, order, table-cell relation, formula structure). Report pass rate per category and overall; no LLM judge as sole oracle for these predicates. Extend catalog when new failure modes discovered (olmOCR-Bench pattern).

**Audit method:** Comparative benchmarking (§5.3) + adversarial probing (§5.6).

**Scoring-design hook:** §6.1 comprehension sub-axis; §6.2 candidate hard gate on safety-critical predicates (e.g., math, normative "shall/not" language in regulated docs).

**Gaming vector:** Overfit to a static predicate list; fuzzy matching so wide that wrong outputs pass.

**Anti-gaming guard:** Rotate held-out predicates; tighten fuzzy rules on canary corrupt cases; require predicate authorship independent of converter team.

**Evidence grade:** A.

**Sources:** Poznanski et al., olmOCR-Bench (arXiv 2502.18443, 2025); ACL Demo olmOCR (Anthology 2026.acl-demo.62, 2026); ParseBench rule-based dimensions (arXiv 2604.08538, 2026).

---

### C7 — Adversarial corrupt-and-recheck (metamorphic comprehension controls)

**Criterion:** Comprehension methodology MUST include **metamorphic / corrupt-and-recheck** tests: apply semantics-altering mutations to source or gold facts, re-run extraction (or inject corrupted markdown), and verify comprehension scores **drop** on affected questions while fidelity-to-original-reference may remain high.

**How to measure:** Defined mutation operators (table row swap, relation flip, token-preserving reorder, decoy paragraph, numeric off-by-one). For each operator: (1) mutate; (2) extract; (3) run comprehension battery; (4) expect ≥X% fail rate on targeted questions (calibrated on baseline). Report operator coverage matrix.

**Audit method:** Adversarial / red-team probing (§5.6).

**Scoring-design hook:** §6.1 adversarial-robustness crossover; §6.4 anti-gaming (proves comprehension metric has teeth).

**Gaming vector:** Mutations so extreme that fidelity also collapses—does not test comprehension independence.

**Anti-gaming guard:** Include **subtle** mutations (subscript/superscript, inequality direction, column swap) where edit distance to gold stays high but meaning changes; pair with C5 canaries.

**Evidence grade:** B (metamorphic testing Tier-1; document-parser adversarial Tier-1/2 mix).

**Sources:** Segura et al., metamorphic testing survey (IEEE/PMC 2016); ProSA structural vulnerability auditing (arXiv 2605.19309, 2026); olmOCR-Bench reading-order and formula predicates (2025).

---

### C8 — Per-modality comprehension reporting (no single comprehension number)

**Criterion:** Comprehension results MUST be reported **per modality axis** (minimum: body prose facts, table facts, math/logic, reading order / cross-reference)—never a single aggregate comprehension score without dimensional breakdown.

**How to measure:** Scorecard template mandates per-axis tables; synthesis may compute weighted composite only alongside visible per-axis scores (frame §6.1 exemplar: OmniDocBench / ParseBench pattern).

**Audit method:** Comparative benchmarking (§5.3) + maturity-model scoring (§5.2).

**Scoring-design hook:** §6.1 (no single composite alone); §6.6 uncertainty bands per axis.

**Gaming vector:** Strong prose QA hides table/math comprehension collapse.

**Anti-gaming guard:** Minimum sample counts per axis; flag axes with insufficient N as "not eligible" rather than imputing.

**Evidence grade:** A.

**Sources:** ParseBench five dimensions (arXiv 2604.08538, 2026); RealDocBench per-field/per-domain breakdown (arXiv 2606.07401, 2026); olmOCR-Bench category columns (2025).

---

## 3. External benchmark / exemplar bar

| Exemplar | What it demonstrates | Fidelity-like | Comprehension-like |
|---|---|---|---|
| **Maynez et al. 2020; SummEval (TACL 2021)** | ROUGE/BERTScore correlate weakly with faithfulness/factuality; QA and entailment correlate better | ROUGE, BERTScore | Human + QA factuality |
| **FEQA / QAGS (ACL 2020)** | QA answer-match between summary claims and source | — | QA-based faithfulness |
| **Ragas Faithfulness (2025 docs)** | Claim decomposition + support ratio vs context | — | Automated fact consistency |
| **olmOCR-Bench (2025; ACL Demo 2026)** | Rejects edit-distance gold diff and LLM-judge-only eval; 7,010 binary semantic unit tests | — (explicitly avoids soft reference match) | Pass/fail fact predicates on output |
| **RealDocBench (2026)** | Field-level QA over real regulated docs; markdown similarity ≠ agent-needed correctness | Layout track (IoU-style) | QA track: typed field recovery |
| **ParseBench (2026)** | Five semantic dimensions; rule-based binary tests over enterprise docs | — | Tables, charts, faithfulness, formatting, grounding |
| **Round-trip translation literature (2020)** | Surface similarity metrics fail semantic equivalence | RTT-BLEU | — (insufficient for meaning) |

**External bar (synthesis-ready):** A defensible comprehension eval stack combines (1) **closed-book QA** or blind read-back with independent question authorship, (2) **claim-level faithfulness** as an automated adjunct with pinned verifiers, (3) **binary semantic unit tests** for high-stakes structures, (4) **metamorphic corrupt-and-recheck** proving metrics detect meaning corruption fidelity misses, and (5) **per-modality reporting**—with fidelity metrics (edit distance, TEDS, etc.) explicitly quarantined to a separate axis (P09 territory).

**Contradiction surfaced:** Round-trip translation was deprecated for MT quality estimation (Somers 2005; Huang 1990; RTT-BLEU poor correlation) yet **Rethinking Round-Trip Translation (ACL Findings 2023)** shows modern NMT RTT can aid *monolingual* evaluation without references. **Resolution for this audit:** RTT may inform auxiliary quality estimation, but it MUST NOT gate comprehension for document extraction; extraction comprehension requires fact recovery from the artifact downstream systems actually consume (markdown), not similarity of regenerated text.

---

## 4. Recommended weight & hard-gate rationale

| Item | Recommendation | Rationale |
|---|---|---|
| **Weight in composite** | **Medium-high** within extraction-quality/eval cluster (~12–18% of total eval dimension weight; exact number deferred to P15) | RealDocBench and ParseBench show single surface scores hide large spreads; comprehension is the construct downstream WG21 QA consumers care about, but it is costlier to measure than fidelity. |
| **Hard gate?** | **Conditional hard gate:** No release/calibration sign-off if comprehension is **only** inferred from fidelity metrics (C5 fail), OR if closed-book QA (C2) is below a calibrated operating point once labels exist (P16). | Mirrors conjunctive guard design in frame §6.2: high fidelity with failed fact recovery is a known failure mode (olmOCR math example; ParseBench agent-critical errors under text overlap). |
| **Advisory-only LLM scores** | LLM-as-judge comprehension (Ragas LLM path) may inform but **must not sole-gate** | Frame §6.4 self-consistency; Panickssery et al. (2024) self-preference bias cited in olmOCR (2025). Prefer HHEM-style classifiers or human spot-checks for load-bearing gates. |

---

## 5. Sources (tiered)

### Tier 1 — Authoritative / primary

| ID | Source | URL | Version / date |
|---|---|---|---|
| S1 | Maynez, J. et al. "On Faithfulness and Factuality in Abstractive Summarization." ACL 2020 | https://aclanthology.org/2020.acl-main.173/ | DOI 10.18653/v1/2020.acl-main.173; July 2020 |
| S2 | Durmus, E. et al. "FEQA: A Question Answering Evaluation Framework for Faithfulness Assessment in Abstractive Summarization." ACL 2020 | https://aclanthology.org/2020.acl-main.454/ | DOI 10.18653/v1/2020.acl-main.454; July 2020 |
| S3 | Wang, A. et al. "Asking and Answering Questions to Evaluate the Factual Consistency of Summaries." ACL 2020 | https://aclanthology.org/2020.acl-main.248/ | ACL 2020 (QAGS) |
| S4 | Fabbri, A. R. et al. "SummEval: Re-evaluating Summarization Evaluation." TACL 2021 | https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00373/100686/ | DOI 10.1162/tacl_a_00373; 2021 |
| S5 | Liu, Y. et al. "FFCI: A Framework for Interpretable Automatic Evaluation of Summarization." JAIR 2023 | https://jair.org/index.php/jair/article/view/13167 | JAIR vol. 76, 2023 |
| S6 | Poznanski, J. et al. "olmOCR: Unlocking Trillions of Tokens in PDFs with Vision Language Models." arXiv 2025 | https://arxiv.org/abs/2502.18443 | v3, 2025 |
| S7 | Soldaini, L. et al. "The OLMOCR Project: Building Fully Open OCR using VLMs." ACL Demo 2026 | https://aclanthology.org/2026.acl-demo.62/ | 2026 |
| S8 | RealDocBench (field-level QA benchmark) | https://arxiv.org/html/2606.07401 | 2026 |
| S9 | ParseBench (semantic correctness benchmark) | https://arxiv.org/abs/2604.08538 | v2, 2026 |
| S10 | Segura, S. et al. "Metamorphic Testing for Cybersecurity." IEEE Trans. Software Engineering / PMC 2016 | https://pmc.ncbi.nlm.nih.gov/articles/PMC4993050/ | 2016 |
| S11 | Ragas — Faithfulness metric (official docs) | https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/faithfulness/ | Retrieved 2025-12-11 |

### Tier 2 — Strong secondary

| ID | Source | URL | Version / date |
|---|---|---|---|
| S12 | Revisiting Round-Trip Translation for Quality Estimation (arXiv) | https://arxiv.org/abs/2004.13937 | 2020 |
| S13 | ProSA: structural vulnerability auditing (arXiv preprint) | https://arxiv.org/html/2605.19309 | 2026 |

**Distinct Tier 1–2 count used for criteria:** 11 Tier-1 + 2 Tier-2 = **13 sources** (floor ≥3 satisfied).

---

## 6. Overlap statement

This persona researched **external** comprehension-vs-fidelity evaluation science only. It did **not**:

- Open or score whisker production code (no `file:line` citations).
- Restate or re-derive results from **`comprehension-poc-report.md`** or other internal POC syntheses (overlap map: frame §3, root syntheses row).
- Duplicate **P09** (metric construct validity for TEDS/NID/GriTS—surface metrics) beyond the separation boundary in C1.
- Duplicate **P10** (LLM-as-judge bias science) beyond the advisory-only gate note in §4.
- Duplicate **P12** (benchmark leaderboard methodology) beyond per-axis reporting alignment in C8.
- Duplicate **P28** (olmOCR/Marker/MinerU case study)—P28 mines repo practices; this file mines **evaluation theory and cross-domain criteria**.

**Overlap boundary confirmed:** avoided internal `comprehension-poc-report.md` results and prior code-level persona/`redteam/` converter findings; delivered external audit criteria and benchmark bar only.

---

## Strongest criterion (persona summary)

**C2 — Closed-book fact-recovery QA battery** is the strongest criterion: it most directly operationalizes comprehension (fact recovery from extracted text alone), aligns with the highest-evidence automatic methods (FEQA/QAGS, RealDocBench field QA), and exposes the fidelity–comprehension gap that surface metrics systematically miss (Maynez 2020; olmOCR 2025; RealDocBench 2026).

**Source count:** 13 (11 Tier-1, 2 Tier-2).
