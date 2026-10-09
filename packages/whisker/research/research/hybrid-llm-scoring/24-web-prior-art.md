# 24 - Web Prior Art (Hybrid Deterministic + LLM Scoring)

**Verdict:** usable — published benchmarks and production QA patterns consistently separate deterministic and model lanes, then fuse only at the reporting layer via escalation matrices, arbitration, or side-by-side scores; no mainstream benchmark collapses them into one gate score.
**Confidence:** high

Date: 2026-07-07. Persona: 24-web-prior-art. Mandate: web research on hybrid scoring fusion, calibration, persistence, and disagreement reporting for whisker/tapetum design.

---

## Question 1: How do document-parsing benchmarks combine deterministic checks with LLM judgment in one score?

### Finding cards

#### olmOCR-Bench: deterministic public score, LLM judge as post-hoc semantic layer
**URL:** https://github.com/allenai/olmocr/tree/main/olmocr/bench  
**Relevance:** HIGH

olmOCR-Bench scores every unit as a binary pass/fail fact check (string presence, table neighbor relations, math symbol layout) and reports Overall as the macro-average of per-category pass rates with bootstrap confidence intervals. The official harness deliberately avoids edit distance and LLM-as-judge for the public leaderboard because soft metrics reward structurally wrong parses. The benchmark does not fuse deterministic and LLM verdicts at scoring time; it is deterministic-only on record.

#### Unsiloed olmOCR re-evaluation: strict pass-rate + separate semantic rescue score
**URL:** https://www.unsiloed.ai/blog/unsiloed-ai-achieves-1-rank-on-olmocr-bench-2  
**Relevance:** HIGH

Unsiloed publishes two scores on the same harness: 88.0% strict deterministic pass-rate (leaderboard metric) and 94.8% after re-running every strict failure through GPT-5.5 LLM-as-judge (`minor` = semantic rescue, `real` = genuine miss). The judge is explicitly a diagnostic on top of strict rules, not a replacement; both numbers are reported separately. This is the clearest 2026 prior art for a dual-lane merged *report* without changing the authoritative deterministic score.

#### OmniDocBench v1.5: deterministic composite, no LLM judge in Overall
**URL:** https://github.com/opendatalab/OmniDocBench/blob/v1_5/README.md  
**Relevance:** HIGH

OmniDocBench v1.5 Overall is a pure deterministic composite: `((1 - Text Edit Distance) × 100 + Table TEDS + Formula CDM) / 3`, averaged across all pages. Sub-scores (text, table, formula, read-order edit) are reported individually on the leaderboard. v1.6 adds Multi-Granularity Adaptive Matching and a three-tier protocol (Full/Base/Hard subsets) but remains edit-distance and structure-metric based, not LLM-judged. Fusion here is numeric averaging of deterministic axes, analogous to whisker `ref_overall`.

#### Marker benchmark: heuristic and LLM rubric scores reported side by side
**URL:** https://pypi.org/project/marker-pdf/1.7.4/  
**Relevance:** HIGH

Marker's `benchmarks/overall.py` supports `--scores heuristic,llm` as comma-separated independent scorers on the same corpus. Heuristic score is block-level edit distance with reading-order weighting; LLM score is rubric grading (1–5 scale) that the authors report correlates best with human visual inspection. Hybrid `--use_llm` mode improves extraction accuracy but the benchmark still emits separate columns (`Heuristic Score`, `LLM Score`), not a single fused metric. Production hybrid mode applies LLM only to problematic regions after the CV pipeline.

#### DP-Bench: axis-specific deterministic metrics, no model lane
**URL:** https://huggingface.co/datasets/upstage/dp-bench  
**Relevance:** MED

DP-Bench evaluates parsers with three deterministic metrics: NID (layout/reading-order serialization, tables excluded), TEDS (table structure + content), and TEDS-S (structure only). Each metric is reported separately; there is no LLM judge or combined Overall formula in the benchmark README. Whisker already uses NID/TEDS/MHS-family signals (`ref_nid`, `ref_teds`, `ref_mhs`, `ref_overall`), making DP-Bench a deterministic-lane anchor rather than a fusion reference.

---

## Question 2: Best practices for fusing rule-based verdicts with LLM-as-judge verdicts

### Finding cards

#### Layered architecture: deterministic constraints first, LLM for semantic quality
**URL:** https://pub.towardsai.net/llm-as-a-judge-designing-reliable-ai-evaluators-for-modern-agentic-system-debf4419cebd  
**Relevance:** HIGH

2026 production guidance recommends a four-layer stack: deterministic validation for exact constraints (schema, PII, format), semantic LLM judgment for nuanced rubrics, calibration against human labels for decision thresholds, and escalation for ambiguity or high-stakes cases. The article argues the largest quality gain comes from measurement design (criteria, evidence access, judging regime) before model choice. For whisker, this maps directly to C1: rules gate, tapetum advises, fusion lives in a reporting layer.

#### Concord: agreement-aware triage and disagreement-flagged inspection lists
**URL:** https://aclanthology.org/2026.gem-main.46.pdf  
**Relevance:** HIGH

Concord runs multiple LLM judges, aggregates via majority vote or final adjudicator, and exports per-judge predictions plus a triage list of low-confidence examples. Agreement signals flag borderline cases (e.g., 2–1 judge splits); a complementary rule flags examples where ≥2 judges disagree with the final decision. The union forms a "disagreement" subset for human-in-the-loop review. This is a concrete agreement-matrix pattern for inspection reports when deterministic and LLM lanes diverge (cf. whisker 123/194 disagreements).

#### DAFE: dynamic arbitration — cheap judges agree, expensive judge breaks ties
**URL:** https://arxiv.org/html/2503.08542v1  
**Relevance:** HIGH

DAFE starts with two complementary open-source judges; when they agree, no further evaluation runs. On disagreement, a stronger LLM arbitrator provides a third vote and majority rule decides. On AmbigQA, arbitration raised Macro F1 from 72.9% to 86.6% and Cohen's κ from 0.467 to 0.773. The pattern mirrors tapetum's two-tier cascade (fast triage → deep escalate) but applied to judge disagreement rather than extraction.

#### LeMAJ: hybrid rule-based + majority voting with fail-priority heuristics
**URL:** https://aclanthology.org/2025.nllp-1.23.pdf  
**Relevance:** MED

LeMAJ tested four fusion flavors for legal QA: pure rule-based (prioritize red/incorrect labels), majority voting, hybrid (red if any judge says red, else majority), and chain-of-verification. The hybrid rule-based + majority approach achieved best overall accuracy (0.852) while a variant optimized for detecting incorrect cases. This supports asymmetric fusion where safety-critical deterministic fails take precedence over LLM leniency, aligning with whisker C1.

#### ChatBench hybrid recipe: tiered filters, LLM judge, human spot checks
**URL:** https://www.chatbench.org/llm-as-a-judge-evaluation-methodology/  
**Relevance:** MED

Production hybrid evaluation stacks three tiers: rule-based filters (safety, PII), LLM judge (helpfulness, tone), and weekly 5% human spot checks for calibration drift. Operational mitigations include temperature ≤ 0.3, chain-of-thought before scoring, answer-order scrambling for pairwise tests, and cross-family majority vote. Confidence thresholds trigger escalation rather than automatic pass/fail override.

---

## Question 3: Is LLM-judge self-reported confidence calibrated?

### Finding cards

#### Closing the Confidence-Faithfulness Gap: verbalized confidence is orthogonal to accuracy
**URL:** https://arxiv.org/pdf/2603.25052  
**Relevance:** HIGH

Mechanistic analysis across three open-weight models shows calibration and verbalized confidence are encoded in orthogonal latent directions. When models reason and verbalize confidence simultaneously, a "Reasoning Contamination Effect" makes the signals anti-correlated and worsens miscalibration (ECE ≥ 35 unsteered). Adaptive steering from internal accuracy estimates reduces ECE 4–7×. Takeaway: tapetum `confidence [0..1]` should not be treated as a calibrated probability without external validation or decoupled estimation.

#### ADVICE: answer-independence drives overconfidence in verbalized scores
**URL:** https://aclanthology.org/2026.acl-long.1098.pdf  
**Relevance:** HIGH

ACL 2026 work identifies answer-independence (confidence not conditioned on the model's own answer) as the primary driver of systematic overconfidence in verbalized confidence. Fine-tuning for answer-dependent confidence (ADVICE) substantially improves calibration without degrading task performance and generalizes to unseen verbalization formats. Mitigation for tapetum: prompt or fine-tune so confidence is explicitly grounded in the axis findings and evidence spans already in the schema.

#### ConfTuner: tokenized Brier score as a proper scoring rule for verbalized confidence
**URL:** https://neurips.cc/virtual/2025/poster/117676  
**Relevance:** MED

NeurIPS 2025 ConfTuner fine-tunes LLMs to verbalize confidence using a tokenized Brier score loss, theoretically proven to be a proper scoring rule that incentivizes truthful probability reporting. It improves calibration across reasoning tasks without requiring ground-truth confidence labels. Relevant if tapetum confidence is ever used as a fusion weight (currently discouraged per `13-score-fusion-architect.md`).

#### Emergent Mind calibration survey: verbalized scores remain miscalibrated by default
**URL:** https://www.emergentmind.com/topics/confidence-calibration-in-llms  
**Relevance:** MED

January 2026 survey documents that verbalized scoring ("I am 80% confident…") and self-evaluation prompts are standard but poorly calibrated out of the box. Recommended mitigations include post-hoc scaling, reinforcement learning with proper scoring rules (log-scoring, tokenized Brier), self-correction loops, and abstention/cascade routing. ECE, Brier score, and MCE are the standard evaluation metrics.

---

## Question 4: Prior art for persisting dual-lane QA verdicts in per-document artifacts

### Finding cards

#### flydocs: single response artifact with extraction, geometric, and judge layers
**URL:** https://github.com/firefly-operationOS/flydocs  
**Relevance:** HIGH

flydocs returns one structured verdict per document: extracted fields with per-field confidence and `source` discriminator (`llm` / `pdf_text` / `ocr`), a geometric quality verdict on bounding boxes, and a Judge layer that re-checks each value (`pass` / `fail` / `uncertain` with `flag_for_review`). Optional escalation re-runs extract+judge with a stronger model and audits the trigger in `pipeline.escalation`. This is the closest production pattern to persisting deterministic + model lanes in one artifact while keeping layers addressable.

#### AWS Accelerated IDP: assessment appended to existing extraction sidecar
**URL:** https://github.com/aws-solutions-library-samples/accelerated-intelligent-document-processing-on-aws/blob/main/docs/assessment.md  
**Relevance:** HIGH

Post-extraction, an LLM assessment step appends per-attribute confidence scores (0.0–1.0) with explanatory reasoning into the existing `explainability_info` block of extraction results, not a separate database row. A post-LLM deterministic step can ground LLM-estimated bounding boxes in OCR geometry from `pageData.json` with zero prompt-token impact. Pattern: extend the per-document JSON sidecar with an `assessment` section rather than a second file.

#### pdf-ci-pipeline: `quality.json` machine-readable gate report per run
**URL:** https://github.com/infocusmodereal/pdf-ci-pipeline  
**Relevance:** MED

Deterministic ingest → parse/OCR → normalize → validate produces `artifacts/quality.json` with pass/fail gates, benchmark metrics (table precision/recall, drift), and versioned copies under `benchmarks/<run_id>/`. Per-document contracts and golden-file regression are separate from aggregate reports. Analogous to whisker `report.json` + per-paper sidecars, though this pipeline has no LLM lane.

#### pepsico-document-confidence: deterministic multi-metric scorer with routing recommendations
**URL:** https://pypi.org/project/pepsico-document-confidence/  
**Relevance:** MED

A sidecar-style `score()` call returns weighted metric aggregation (text coverage, table completeness, spatial density, crossref consistency) plus deficiency classification and accept/recover/human-review routing. Fully deterministic, no LLM calls, designed for high-throughput ETL. Useful as a schema reference for named metric lanes and threshold-based routing in a unified JSON artifact.

#### RaV-IDP: per-entity fidelity score triggers model fallback, anchored to source
**URL:** https://arxiv.org/pdf/2604.23644  
**Relevance:** MED

RaV-IDP computes a label-free fidelity score per extracted entity by reconstructing and comparing against the original document crop (Spearman ρ = 0.80–0.88 with ground truth). Below-threshold fidelity triggers a vision-LLM fallback; a bootstrap constraint ensures the comparator always anchors to the source region, never the extraction. Dual-lane pattern: deterministic fidelity gate + model fallback, with per-entity scores persisted in pipeline output.

---

## Question 5: Agreement/kappa methodology for reporting where evaluators disagree

### Finding cards

#### Reliability without Validity: universal kappa deflation vs raw agreement
**URL:** https://arxiv.org/html/2606.19544v1  
**Relevance:** HIGH

Largest systematic LLM-judge evaluation to date (21 judges, ~541K judgments, April 2026 frontier): raw exact-match agreement overstates performance by 33–41 percentage points versus Cohen's κ on MT-Bench. High test-retest reliability (>0.95) can coexist with severe position bias (>0.10). Authors distill a Minimum Viable Validation Protocol. For whisker inspect reports, report κ (or agreement with chance correction) alongside raw agree/DIFFERS counts, not exact-match alone.

#### Agreement Metrics for LLM-as-Judge: reporting checklist for binary rubrics
**URL:** https://arxiv.org/html/2606.00093  
**Relevance:** HIGH

Survey of 24 LLM-judge papers finds metric choice rarely stated for tie handling, abstention, and judgment scale. For binary MET/UNMET criteria, Pearson/Spearman/Kendall/φ/MCC collapse to one number on non-degenerate data; Cohen's κ is the coefficient that adds information beyond φ by normalizing for base-rate drift. Reporting checklist requires: judgment scale, abstention mode, coverage, confusion matrix, aggregation level, and one chance-corrected agreement coefficient.

#### FutureAGI 2026 calibration targets: κ > 0.6 production, > 0.8 strong
**URL:** https://futureagi.com/blog/llm-as-a-judge/  
**Relevance:** MED

Production LLM-judge calibration workflow: sample 100–300 traces, 2–3 human labelers, compute inter-annotator κ, then judge-to-human κ on the same rubric. Thresholds: IAA κ < 0.4 means rubric is ambiguous; 0.4–0.6 weak; > 0.6 acceptable; > 0.8 strong. Judge-to-human κ < 0.5 triggers rubric rework. Production pattern is sample-based live monitoring (1–10%) plus 100% in CI.

#### Concord disagreement subset: union of agreement-variance and panel-vs-final disagreement flags
**URL:** https://aclanthology.org/2026.gem-main.46.pdf  
**Relevance:** MED

Concord exports per-judge CSVs, combines into final verdict, and produces a triage list from two criteria: high score variance among judges (ordinal) or ≥2 judges disagreeing with the final adjudicator decision (binary). The disagreement subset concentrates human review on contentious cases. Direct template for `tapetum-inspect.md` enhancement: flag PIDs where whisker and tapetum disagree AND tapetum confidence is below floor or axis severity is major.

---

## Synthesis for our design

1. **No mainstream benchmark fuses deterministic + LLM into one authoritative gate score.** olmOCR (strict), Marker (heuristic + LLM columns), and OmniDocBench (deterministic composite) all keep lanes separable; Unsiloed's +6.8pp semantic lift is a second reported number, not a leaderboard overwrite. Whisker C1 is industry-norm, not conservative eccentricity.

2. **Merged score = reporting composite, not verdict override.** Best prior art (Unsiloed, flydocs, AWS assessment) appends or reports a combined view while the deterministic/pass-fail record stays immutable. Aligns with `13-score-fusion-architect.md` recommendation: `combined_verdict` in a fusion sidecar, never written back to `<pid>.whisker.json`.

3. **Asymmetric escalation beats democratic fusion.** LeMAJ fail-priority, DAFE arbitration-on-disagreement, and Concord disagreement triage all weight safety-critical or high-variance cases upward without letting the LLM lane alone demote or pass. Supports det-primary + at-most-one-step escalation to `review` when tapetum has major fail.

4. **Agreement matrices belong in inspect reports, not in the gate.** Export `(whisker_verdict, tapetum_verdict, combined_verdict, advisory_delta)` per PID plus aggregate agree/DIFFERS/κ. Raw 63% disagreement rate (123/194) is meaningful only alongside chance-corrected κ and per-axis confusion.

5. **tapetum `confidence` is advisory weight, not a fusion operand.** 2025–2026 calibration literature consistently finds verbalized confidence miscalibrated and answer-independent by default. Do not confidence-weight a numeric composite; use confidence only for inspect sort and escalation band (already in tapetum cascade).

6. **Persist both lanes in one file via namespaced blocks.** flydocs and AWS IDP append model assessment to the extraction artifact (`assessment`, `explainability_info`, `judge` blocks). Whisker goal 2 can add a `tapetum` block inside `<pid>.whisker.json` (schema bump) or a sibling `<pid>.fusion.json` without touching deterministic `verdict`.

7. **Handle absent/errored LLM lane explicitly.** olmOCR returns 0.0 for missing candidates; pdf-ci gates fail closed. Six tapetum errors in the 2026-07-06 run must produce `tapetum_available: false` and `combined_rule: whisker_only`, never imputed pass.

8. **Macro-average across strata, not micro-average across tests.** olmOCR Overall averages per-category pass rates to prevent one easy stratum from hiding table failures. If whisker reports a merged numeric display, macro-average per-axis lane bits rather than blending unrelated scalars (`ref_overall` vs `confidence`).

9. **Inspection reports should surface disagreement loci.** Concord and Agreement Metrics papers require confusion matrices and triage lists, not scalar agreement alone. Extend `tapetum-inspect.md` with per-axis `(whisker_flag, tapetum_axis_verdict, severity)` for DIFFERS rows.

10. **Calibration is a pre-production gate, not a runtime afterthought.** Before using merged scores in triage, run a 100–300 paper sample with human gold labels; target judge-to-human κ ≥ 0.6 (FutureAGI) and report κ not raw agreement (Reliability without Validity). This is the evidence that would unlock stronger fusion rules per `13-score-fusion-architect.md`.

## False-pass hypothesis

Macro-averaging olmOCR-style pass-bits across axes could mark a paper `combined_pass` when deterministic table gates fail but tapetum pass-bits are high on prose-heavy axes, the same anti-collapse risk olmOCR guards with per-stratum macro averages (Unsiloed: 91% of table strict failures are string-level, not semantic).

## False-fail hypothesis

Requiring both lanes to pass (AND fusion) would false-fail papers where Unsiloed-style LLM rescue would classify strict deterministic failures as `minor` (LaTeX-equivalent rewrites, whitespace), analogous to whisker `review` + tapetum `pass` on heading-monotone-only fails.

## What would change my mind

A published document-conversion benchmark that runs deterministic unit tests and LLM-as-judge in one harness, emits a single official leaderboard score computed as a documented fusion function (not side-by-side columns), and open-sources the fusion code. None found in 2026 prior art; all sources keep lanes separable.
