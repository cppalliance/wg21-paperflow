# P09 — Document-Extraction Quality-Metrics Researcher

**Persona:** 9 (Cluster C — Extraction quality & eval science)  
**Date:** 2026-07-18  
**Scope:** External construct-validity criteria for document→Markdown extraction metrics. No whisker code inspection.

---

## 1. Question restated

What quality metrics are accepted for document→Markdown (and structured intermediate) extraction, what does each metric **actually** measure, where are the known blind spots, and when must a metric be **null-eligible** because the modality or annotation unit is absent? The downstream audit must be able to reject gates built on metrics whose construct validity does not match the failure mode under test.

---

## 2. Proposed audit criteria

Each criterion includes: how to measure compliance, audit-method (from `00-FRAME.md` §5), scoring-design hook (§6), gaming vector + anti-gaming guard, evidence grade, and Tier 1–2 citations.

### Criterion 2.1 — Per-modality null-eligibility and explicit absence reporting

**Statement:** Every scored axis declares (a) which document modalities it applies to, (b) what happens when that modality is absent in ground truth or prediction, and (c) that absence is reported as `null`/`N/A`, not imputed as perfect or zero.

**How to measure:** Inspect the metric spec and benchmark harness. For each axis (text serialization, table structure, formula, reading order, layout detection), verify:
- Tables absent → table metrics (TEDS, TEDS-S, GriTS) are skipped, not averaged as 100%.
- Tables/figures/charts absent from NID/NED serialization scope where the benchmark excludes them (DP-Bench excludes tables, figures, charts from NID).
- Reading order absent or not annotated → reading-order metric skipped; OmniDocBench excludes tables, images, and ignored components from reading-order Edit Distance.
- Layout-detection P/R/F1 or mAP runs only when bbox ground truth exists for that page subset.

**Audit-method:** Metric construct-validity audit (#4); Conformance checklist (#1).

**Scoring-design hook:** Hard-gate candidate (§6.2): using a modality-specific metric as a global gate when the modality is absent is a construct-validity failure. Feeds per-dimension reporting (§6.1).

**Gaming vector:** Score pages with no tables as "perfect table extraction" by averaging TEDS=1.0 on empty sets.

**Anti-gaming guard:** Require `eligible_count` and `null_count` per axis in every report; composite scores must be computed only over eligible pages/modalities, with the denominator documented.

**Evidence grade:** A (converging Tier-1 benchmark definitions).

**Sources:** DP-Bench README (NID excludes tables/figures/charts; table mode separate); OmniDocBench paper §4 (reading order excludes tables/images/ignored components); OmniDocBench repo `end2end.yaml` (separate metric blocks per modality).

---

### Criterion 2.2 — TEDS measures joint table tree structure + cell content, not layout detection

**Statement:** Tree-Edit-Distance-based Similarity (TEDS) evaluates HTML-tree similarity between predicted and reference tables, combining structural nodes (`colspan`, `rowspan`, row/cell topology) with normalized Levenshtein similarity on cell **content** at leaf `td` nodes. It is not a substitute for layout bounding-box detection or reading-order evaluation.

**How to measure:** Confirm the implementation models tables as trees (thead/tbody → tr → td with attributes) and uses tree edit distance normalized by max node count: `TEDS(Ta,Tb) = 1 − EditDist(Ta,Tb) / max(|Ta|,|Tb|)`. Verify cell substitution cost uses content similarity, not exact match only. Confirm table metrics are not used to score non-table pages.

**Audit-method:** Metric construct-validity audit (#4).

**Scoring-design hook:** Per-dimension sub-score for "table structure+content" (§6.1); do not fold into text-edit composite without weight disclosure.

**Gaming vector:** Inflate TEDS by emitting syntactically valid but semantically empty HTML shells; or match one predicted sub-table to ground truth while splitting/merging tables elsewhere (OmniDocBench/LlamaIndex documented false-flag case).

**Anti-gaming guard:** Pair full TEDS with TEDS-S (structure-only) and table count/recall checks; require Hungarian or explicit one-to-one table matching before averaging (READoc practice).

**Evidence grade:** A (foundational peer-reviewed definition + benchmark reuse).

**Sources:** Zhong et al., ECCV 2020 / PubTabNet (TEDS definition, superiority over adjacency-relation F1 on shift vs content perturbations); DP-Bench README; OmniDocBench evaluation §4.

---

### Criterion 2.3 — TEDS-S / S-TEDS (structure-only) must be reported separately from full TEDS

**Statement:** Structure-only table similarity (TEDS-S in DP-Bench; `TEDS_structure_only` / "Table TEDS-S" in OmniDocBench) uses the same tree-edit formulation but **strips cell content** from nodes. It measures rowspan/colspan/row-column alignment independent of OCR/text errors. Full TEDS and structure-only TEDS must never be conflated in gates or leaderboards.

**How to measure:** Verify two scores are computed from distinct tree representations. Check that regressions where TEDS-S stays high while full TEDS drops are flagged as content/OCR failures, not structure success.

**Audit-method:** Metric construct-validity audit (#4); Anti-gaming / Goodhart stress (#7).

**Scoring-design hook:** Mandatory paired reporting (§6.1 "no single composite alone"); contested criterion if only one is reported (§6.5).

**Gaming vector:** Optimize markdown/HTML table syntax cosmetically while cell text is wrong; structure-only score masks comprehension loss.

**Anti-gaming guard:** Hard rule: structure-only score cannot satisfy a "table fidelity" gate without full TEDS (or GriTS_Con) meeting the same threshold.

**Evidence grade:** A.

**Sources:** DP-Bench README (TEDS vs TEDS-S definitions); OmniDocBench README leaderboard columns (Table TEDS ↑ vs Table TEDS-S ↑); OmniDocBench `skills/SKILL.md` result parsing (`TEDS_structure_only`).

---

### Criterion 2.4 — GriTS provides matrix-native table evaluation with decomposed topology, content, and location

**Statement:** Grid Table Similarity (GriTS) evaluates predicted tables in native matrix form via 2D most-similar-substructure (2D-MSS), decomposed into GriTS_Top (cell topology), GriTS_Con (content), and GriTS_Loc (spatial/bbox alignment when available). Where TEDS is used, the audit should know GriTS exists as a cross-check when HTML-tree serialization choices (merged cells, thead/tbody conventions) distort TEDS.

**How to measure:** For table evaluation specs, check whether matrix-based similarity is available or acknowledged. If only TEDS is used, document known TEDS blind spots GriTS was designed to fix (adjacency/list metrics' under-reaction to multi-hop misalignment; tree/HTML representation sensitivity). When GriTS is used, report at least GriTS_Top and GriTS_Con separately.

**Audit-method:** Metric construct-validity audit (#4); Comparative benchmarking against exemplars (#3).

**Scoring-design hook:** Triangulation for anti-gaming (§6.4): table gate requires agreement between two construct-distinct metrics (e.g., TEDS + GriTS_Top) or explicit waiver with evidence.

**Gaming vector:** Pick HTML serialization that minimizes tree edits but wrong matrix topology; or ignore bbox localization errors when only HTML TEDS is computed.

**Anti-gaming guard:** On disputed table scores, rerun with alternate representation (HTML vs grid) and report sensitivity band (§6.6).

**Evidence grade:** A.

**Sources:** Smock, Pesala & Abraham, GriTS / ICDAR 2023 (arXiv:2203.12555); Microsoft Research publication page; GriTS paper §3.3 (GriTS_Top, GriTS_Con, GriTS_Loc); empirical comparison showing TEDSCon sensitivity differs from GriTS on row/column selection perturbations.

---

### Criterion 2.5 — NID / normalized edit distance (NED) measures text serialization and order, not table/formula fidelity

**Statement:** Normalized Indel Distance (NID, DP-Bench) and Normalized Edit Distance (NED / TextEdit, OmniDocBench) measure character-level alignment of **text layout elements** in reading order after matching. NID explicitly excludes substitutions (insert/delete only), penalizing length drift differently from standard Levenshtein NED. Neither measures table structure, formula semantics, or figure content when those modalities are excluded from the string.

**How to measure:** Verify metric formula and exclusion rules. DP-Bench: `NID = 1 − distance / (len(reference) + len(prediction))` with insert/delete-only distance. OmniDocBench: NED on matched text blocks after adjacency-search matching; headers/footers/page numbers may be ignored per benchmark ignore logic. Confirm tables/formulas are routed to separate metric channels.

**Audit-method:** Metric construct-validity audit (#4).

**Scoring-design hook:** Separate text-serialization dimension in composite (§6.1); cannot gate "table correctness" or "formula correctness."

**Gaming vector:** Perfect NID/NED via whitespace/punctuation normalization while losing semantic structure; or `no_split` matching that hides reading-order errors (OmniDocBench warns `no_split` skips reading-order output).

**Anti-gaming guard:** Require end-to-end matching mode (`quick_match` or equivalent) for any gate touching reading order; report match-method in results JSON.

**Evidence grade:** A.

**Sources:** DP-Bench README (NID formula, exclusions); OmniDocBench paper §4 (Pure Text NED, ignore handling, adjacency search match); OmniDocBench repo configs (`match_method`, separate `text_block` vs `table` vs `reading_order`).

---

### Criterion 2.6 — Reading-order metrics must use order-specific constructs, not proxy via plain-text edit distance alone

**Statement:** Reading order is a **sequence** over layout blocks (or tokens), not reducible to character edit distance on concatenated text without order annotation. Accepted constructs include: (a) NED/Edit Distance over matched block-index sequences (OmniDocBench: text components only, excluding tables/images/ignored); (b) Kendall's Tau Distance Similarity (KTDS) at block or token level (READoc); (c) NID over serialized element tokens in DP-Bench layout mode. A valid reading-order gate must specify which representation is ordered.

**How to measure:** Inspect whether reading-order score is computed on block order indices vs merged plaintext. Verify exclusions match benchmark (OmniDocBench excludes non-text blocks from order sequence). Check multi-column pages are reported separately (OmniDocBench Table 5: order edit by layout type).

**Audit-method:** Metric construct-validity audit (#4); Adversarial / red-team probing (#6) — token-preserving reorder attacks.

**Scoring-design hook:** Independent reading-order axis in composite (§6.1); sensitivity driver for layout-heavy documents (§6.6 flip conditions).

**Gaming vector:** Sort paragraphs alphabetically or by y-coordinate only; pass character NED while destroying cross-column order.

**Anti-gaming guard:** Canary pages with known multi-column ground-truth order; require order metric to fail on adjacent-block swap tests independent of character NED.

**Evidence grade:** A.

**Sources:** OmniDocBench paper §4 (Reading Order: NED on text components only); READoc ACL 2025 Findings (KTDS block-level and token-level); DP-Bench README (NID as element serialization in reading order).

---

### Criterion 2.7 — Set precision / recall / F1 (and mAP) apply to detection/localization, not transcription fidelity

**Statement:** Adjacency-relation F1 (legacy table metric), layout mAP (DocLayNet/COCO-style), and page-level P/R/F1 measure **whether regions or relations were detected**, not whether extracted text matches ground truth. PubTabNet/EDD showed adjacency F1 under-reacts to multi-hop cell misalignment and over-reacts to minor cell-content edits compared to TEDS. Layout mAP is appropriate for bbox layout detection (OmniDocBench layout subset) but must not stand in for end-to-end Markdown fidelity.

**How to measure:** Map each reported P/R/F1 or mAP to its object set (bbox classes, adjacency pairs, header/table counts). Verify it is not the sole gate for "extraction quality." If header/table **recall** metrics are used (kapa.ai-style decomposed eval), pair with precision to detect hallucinated structure.

**Audit-method:** Metric construct-validity audit (#4); Conformance checklist (#1).

**Scoring-design hook:** Layout detection as its own dimension, never compensating for text/table NED failures (§6.1 non-compensatory gates).

**Gaming vector:** High mAP by over-segmenting boxes; high table precision with empty cells; adjacency F1 gaming via local neighbor preservation while global structure collapses (Zhong et al. shift perturbation).

**Anti-gaming guard:** Require paired precision/recall; for tables, never gate on detection F1 without structure metric (TEDS-S or GriTS_Top).

**Evidence grade:** A.

**Sources:** Zhong et al. 2020 (adjacency F1 vs TEDS perturbation analysis); DocLayNet (IBM, mAP for layout); OmniDocBench repo layout_detection config (COCODet mAP); kapa.ai PDF converter benchmark (header/table recall vs precision decomposition — Tier 2 design doc).

---

### Criterion 2.8 — Content recall / vocabulary-F1 measures lexical coverage, not structure or comprehension

**Statement:** Content recall (e.g., fraction of ground-truth headers/tables found) and vocabulary-level F1 (READoc "Vocab F1" on plain-text token sets) measure **coverage of lexical units**, not structural fidelity or factual comprehension. READoc explicitly pairs Concat EDS with Vocab F1 for text extraction; kapa.ai separates header recall, table recall, and cell-text similarity. These metrics detect missing content but not swapped semantics, wrong heading hierarchy, or corrupted table relations.

**How to measure:** Verify content-recall metrics are defined against enumerated ground-truth sets (headers, tables, figures). Check they are not averaged into a single "quality" score without structure/order axes. Confirm recall is paired with precision where hallucination matters.

**Audit-method:** Metric construct-validity audit (#4); Anti-gaming / Goodhart stress (#7).

**Scoring-design hook:** Supplementary indicator only (§6.1); cannot be sole hard gate (§6.2) for WG21 QA where structure carries semantics.

**Gaming vector:** Dump all ground-truth tokens into a bag-of-words footer; inflate Vocab F1 while reading order and structure fail.

**Anti-gaming guard:** Gate on recall only together with order or structure metric on same corpus slice; cap contribution to composite weight.

**Evidence grade:** B+ (READoc Tier-1; kapa Tier-2 design doc converging).

**Sources:** READoc ACL 2025 (Semantic Unit Evaluation: Text Extraction — Concat EDS + Vocab F1); kapa.ai PDF converter benchmark metric definitions (header_recall, table_recall, cell_text_similarity).

---

### Criterion 2.9 — End-to-end matching algorithm is part of the metric contract

**Statement:** End-to-end extraction scores depend on **prediction–ground-truth alignment** (block matching, adjacency merge/split, table Hungarian matching, ignore rules). The matching policy is not neutral: OmniDocBench adjacency search merge changes NED; table one-to-one matching failures depress TEDS on semantically correct split tables; ignore rules for headers/footers differ by model convention.

**How to measure:** Document match_method (`quick_match`, `no_split`, etc.), ignore masks, timeout fallbacks, and table matching algorithm. Require version-pinned evaluator code (OmniDocBench tag/commit) alongside scores. Flag contradictions: e.g., claiming reading-order gate while using `no_split`.

**Audit-method:** Reproducibility replay (#8); Metric construct-validity audit (#4).

**Scoring-design hook:** Evidence grade on scores includes evaluator version (§6.3); contested if matching policy differs from benchmark default (§6.5).

**Gaming vector:** Tune merge thresholds on dev set; exploit ignore rules to drop hard regions from scoring.

**Anti-gaming guard:** Holdout evaluator config frozen; report scores under default and strict (no-ignore) sensitivity.

**Evidence grade:** A.

**Sources:** OmniDocBench paper §4 (Adjacency Search Match, Ignore Handling); OmniDocBench `end2end.yaml` (`match_method`, timeout fallbacks); LlamaIndex 2026 analysis of false-flag TEDS/NED from table matching (Tier 3 contextual — supports but does not sole-source).

---

### Criterion 2.10 — Composite scores must not collapse per-axis construct validity

**Statement:** Benchmarks that publish composites (OmniDocBench Overall = `((1−TextEdit)×100 + TableTEDS + FormulaCDM)/3`; DP-Bench leaderboard columns) explicitly combine **incommensurable constructs**. A professional audit treats composites as navigation only; gates and calibration attach to **per-axis** metrics with documented null-eligibility.

**How to measure:** Verify audit rubric lists TextEdit, Table TEDS, Table TEDS-S, Formula CDM, Reading Order Edit (and layout mAP if applicable) separately. Reject single-number "extraction quality" gates unless axis weights and null rules are published and justified.

**Audit-method:** Anti-gaming / Goodhart stress (#7); Weighted composite design rules (feeds §6.1 — persona P15 owns weights).

**Scoring-design hook:** §6.1 mandatory per-dimension display; §6.2 hard gate only on specific axis construct, not composite.

**Gaming vector:** Optimize composite by sacrificing reading order on table-heavy pages while table/formula axes dominate the average.

**Anti-gaming guard:** Minimum per-axis floor gates (e.g., reading-order edit below document-type-specific calibration) in addition to composite.

**Evidence grade:** A.

**Sources:** OmniDocBench README Overall formula; OmniDocBench paper Table 2 (separate TextEdit, TableTEDS, ReadOrderEdit columns); DP-Bench README (separate NID, TEDS, TEDS-S leaderboard columns); `00-FRAME.md` §6.1 (OmniDocBench precedent).

---

## 3. External benchmark / exemplar bar

Serious document-parsing evaluation (2024–2026) converges on **multi-axis, modality-aware** scoring:

| Exemplar | Text / serialization | Tables | Formulas | Reading order | Layout detection | Null / split behavior |
|---|---|---|---|---|---|---|
| **DP-Bench** (Upstage, 2024+) | NID (insert/delete, tables/figures excluded) | TEDS + TEDS-S | Not primary axis | Implicit in NID serialization | Element lists in JSON | `--mode layout` vs `table` vs `all` |
| **OmniDocBench** (CVPR 2025) | NED (TextEdit) | TEDS + TEDS-S | CDM + NED | Edit_dist on text block order | mAP (COCODet) on layout subset | Per-modality configs; ignore flags; `no_split` drops order |
| **PubTabNet / TEDS origin** | Cell content via tree leaves | TEDS vs adjacency F1 | N/A | N/A | N/A | Table-only task |
| **GriTS / PubTables** | GriTS_Con | GriTS_Top, GriTS_Loc | N/A | N/A | Loc when bboxes available | Table-only |
| **READoc** (ACL 2025) | Concat EDS + Vocab F1 | Tree TEDS after matching | Formula EDS | KTDS block + token | Implicit via segmentation | Segmented semantic units |
| **DocLayNet** | OCR text separate | Table regions only | N/A | N/A | mAP @ IoU | Detection-only |

**Professional bar:** An extraction-QA system claiming "best defensible quality" must (1) declare which exemplar metric family each gate uses, (2) report structure and content table metrics separately, (3) never impute absent modalities, (4) separate reading order from character edit distance, (5) treat detection P/R/F1 as orthogonal to transcription fidelity, and (6) pin evaluator matching code/version.

**Known cross-benchmark tensions (surfaced, not hidden):**
- NID (no substitutions) vs NED/Levenshtein (substitutions allowed) — scores are not directly comparable.
- TEDS-S naming: DP-Bench "TEDS-S" = OmniDocBench "TEDS_structure_only" / leaderboard "Table TEDS-S" — same construct, verify implementation parity before merging runs.
- OmniDocBench saturation critiques (2026): continuous edit metrics penalize harmless formatting divergence; single ground-truth markdown under-rewards semantically equivalent outputs — motivates comprehension/fidelity split (P13), not collapse of metric validity work.

---

## 4. Recommended weight & hard-gate rationale

| Criterion | Weight emphasis | Hard gate? | Rationale |
|---|---|---|---|
| 2.1 Null-eligibility | High in extraction-quality dimension | **Yes — candidate** | Using a metric outside its modality scope is a category error; DP-Bench and OmniDocBench both encode explicit exclusions. |
| 2.2 TEDS validity | High | No (calibrated threshold) | Core table fidelity metric, but requires paired structure-only score. |
| 2.3 TEDS-S separation | Medium-high | **Yes — paired gate** | Structure-only pass with full TEDS fail signals OCR/content corruption masked by HTML shape. |
| 2.4 GriTS cross-check | Medium | No | Triangulation when HTML serialization is unstable. |
| 2.5 NID/NED scope | High | No | Text gate only, with matching policy pinned. |
| 2.6 Reading order | High for layout-heavy corpora | Conditional gate | WG21 papers are multi-column; order errors break anchor/fact paths even when character NED is low. |
| 2.7 Set P/R/F1 | Medium | No | Layout module gate, not end-to-end extraction gate. |
| 2.8 Content recall / Vocab F1 | Low-medium | No | Supplementary missing-content detector. |
| 2.9 Matching contract | High (meta) | **Yes — process gate** | Scores without pinned matcher version are not reproducible evidence. |
| 2.10 No composite collapse | High (reporting) | **Yes — reporting gate** | Single-number claims violate OmniDocBench/FRAME precedent. |

**Suggested hard gates for synthesis (Tier-1 backed):**
1. **Null-eligibility violation** — any modality scored when absent → automatic fail of metric integrity.
2. **Table gate requires full TEDS (or GriTS_Con) AND structure metric (TEDS-S or GriTS_Top)** — blocks cosmetic HTML compliance.
3. **Reading-order gate cannot rely on `no_split` or plaintext-only proxy** — must use block-order construct.
4. **Evaluator version + match_method recorded** — otherwise evidence grade capped at C.

Weights within the extraction-quality dimension should defer to P15 (MCDA); this persona supplies construct-validity loadings, not numeric weights.

---

## 5. Sources

### Tier 1 — Authoritative / primary

| ID | Source | Version / date | URL | Used for |
|---|---|---|---|---|
| S1 | Zhong, ShafieiBavani & Yepes, "Image-based table recognition: data, model, and evaluation" (ECCV 2020 / PubTabNet) | arXiv v5, 2020 | https://arxiv.org/abs/1911.10683 | TEDS definition; adjacency F1 blind spots; tree HTML model |
| S2 | Smock, Pesala & Abraham, "GriTS: Grid table similarity metric for table structure recognition" (ICDAR 2023) | arXiv:2203.12555, 2022 | https://arxiv.org/abs/2203.12555 | GriTS_Top/Con/Loc; matrix vs tree metrics |
| S3 | Ouyang et al., "OmniDocBench: Benchmarking Diverse PDF Document Parsing with Comprehensive Annotations" (CVPR 2025) | arXiv:2412.07626, 2024–2025 | https://arxiv.org/html/2412.07626v2 | NED, TEDS, CDM, reading-order Edit; matching/ignore; per-axis tables |
| S4 | Wang et al., "READoc: A Unified Benchmark for Realistic Document Structured Extraction" (ACL 2025 Findings) | 2025 | https://arxiv.org/html/2409.05137 | EDS, TEDS, Vocab F1, KTDS reading order |
| S5 | Pfitzmann et al., "DocLayNet: A Large Human-Annotated Dataset for Document-Layout Analysis" | 2022 | https://arxiv.org/abs/2206.01062 | Layout mAP construct; detection vs parsing |

### Tier 2 — Strong secondary (official benchmark / maintainer docs)

| ID | Source | Version / date | URL | Used for |
|---|---|---|---|---|
| S6 | Upstage **DP-Bench** dataset README | 2024–2026 leaderboard | https://huggingface.co/datasets/upstage/dp-bench | NID formula; TEDS/TEDS-S; modality exclusions; `--mode` |
| S7 | OpenDataLab **OmniDocBench** repository (README, configs, skills) | v1.6_full, 2025–2026 | https://github.com/opendatalab/OmniDocBench | `end2end.yaml`; TEDS_structure_only; match_method; Overall formula |
| S8 | IBM **PubTabNet** repository | TEDS code release 2020-07-01 | https://github.com/ibm-aur-nlp/PubTabNet | Reference TEDS implementation lineage |
| S9 | kapa.ai, "Why We Built Our Own PDF Converter Benchmark" | design doc, 2025+ | https://docs.kapa.ai/research/pdf-converter-benchmark | Decomposed recall/precision (header, table, cell similarity) |

### Tier 3 — Contextual (cited for tension only, not sole criteria)

| ID | Source | Note |
|---|---|---|
| S10 | LlamaIndex, "OmniDocBench is Saturated, What's Next for OCR Benchmarks?" (2026) | False-flag TEDS/NED from matching; formatting penalty — supports 2.9/2.10 tension |

**Distinct Tier 1–2 count:** 9 (S1–S9). **Contradictions surfaced:** NID vs NED substitutability; composite Overall vs per-axis gates; semantic equivalence vs edit-distance fidelity (S10 vs S3).

---

## 6. Overlap statement

This persona researched **external construct validity of extraction-quality metrics only**. It did **not**:
- inspect or score whisker production code (boundary vs `persona/` code-level metric audits);
- re-litigate library import choices (boundary vs `buildvsbuy/`);
- red-team external converters (boundary vs `redteam/`);
- design benchmark holdout protocol (boundary vs P12) or LLM-judge trust (P10) or comprehension-vs-fidelity tests (P13).

**Overlap boundary confirmed:** avoided duplicating `buildvsbuy/` (which package to import) and `persona/` (whisker metric implementation scores). Output is audit **criteria + external bar** for metric validity, not a whisker verdict.

---

**Deliverable metadata:** 10 audit criteria | 9 Tier 1–2 sources | **Strongest criterion: 2.1 (per-modality null-eligibility and explicit absence reporting)** — without it, all other metrics can be gamed or applied out of scope, a failure mode explicitly encoded in DP-Bench and OmniDocBench but often omitted in single-number QA gates.
