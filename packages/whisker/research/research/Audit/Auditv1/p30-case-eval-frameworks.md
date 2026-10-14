# P30 — Eval-Framework Family Case Study (Ragas / DeepEval / TruLens / Giskard / promptfoo / Great Expectations)

**Persona:** 30 of 30 (Cluster H: Repository & framework case studies)  
**Date:** 2026-07-18  
**Scope:** External scoring-system design from mature eval/data-quality frameworks only. No whisker production-code inspection, no code cloning.

---

## 1. Question restated

How do mature **evaluation and data-quality frameworks** structure **scoring, gating, regression detection, uncertainty reporting, and CI integration**? This grouped case study extracts transferable **scoring-system patterns** from Ragas, DeepEval, TruLens, Giskard, promptfoo, and Great Expectations, tagged to `00-FRAME.md` scoring-design hooks §6.1–§6.6, to inform the whisker audit rubric synthesis. The question is not "which framework to adopt" but "what external bar must the audit's own scoring system meet."

---

## 2. Proposed audit criteria

Each criterion uses a **0–4 maturity ladder** unless marked **hard gate**. Evidence grades: **A** = multiple Tier-1 corroborating; **B** = single Tier-1 or converging Tier-2; **C** = Tier-3/contested; **D** = Tier-4/speculative.

### Framework scoring-pattern inventory (feeds all criteria)

| Framework | Primary scoring unit | Per-axis reporting | Threshold / gate | Regression / baseline | CI pattern | §6 hook |
|---|---|---|---|---|---|---|
| **Ragas** | `MetricResult` (0–1 + reason) per metric | Faithfulness, answer relevancy, context precision/recall/utilization as separate columns | No first-class pass gate in core; experiment analytics | Timestamped CSV experiment runs; git metadata optional | Integrates via experiment runner, not pytest-native | §6.1, §6.6 |
| **DeepEval** | Metric score 0–1 + `reason`; `threshold` per metric | RAG triad split (retriever vs generator metrics) | `metric.is_successful()` iff score ≥ threshold; `strict_mode` → binary | Confident AI `--official` baseline run | `assert_test()` + `deepeval test run` → pytest fail | §6.1, §6.2, §6.4 |
| **TruLens** | Feedback function score 0–1 + optional CoT reason | RAG triad: Groundedness, ContextRelevance, AnswerRelevance | Scorer `threshold` param (default 0.5); pass if score ≥ threshold | Dashboard aggregate trends + per-record drill-down | MLflow batch evaluate; not pytest-native by default | §6.1, §6.3 |
| **Giskard** | Probe severity + ordinal **grade A–D** | Category-tagged probes (OWASP LLM Top 10 + extensions) | `ACCEPTABLE_GRADES = ["A","B"]` CI gate | Promote successful attacks → permanent regression dataset | Hub SDK scan → `sys.exit(1)` on grade fail | §6.2, §6.4, §6.5 |
| **promptfoo** | Per-assertion score; weighted composite | `metric` field → named metrics aggregated separately | Test-case `threshold`; `assert-set` partial pass; `PROMPTFOO_PASS_RATE_THRESHOLD` | JSON output diff; suite pass-rate vs prior runs | Exit code 100 when pass rate below threshold | §6.1, §6.2, §6.4, §6.6 |
| **Great Expectations** | Per-expectation pass/fail (+ optional numeric) | Expectation Suite lists every check; Validation Result per expectation | `CheckpointResult.success` conjunctive; `severity` critical/warning/info | Versioned suites in store; Data Docs history | Checkpoint in pipeline; halt on `success == false` | §6.1, §6.2, §6.3 |

**Contradiction surfaced:** Ragas and TruLens default to **analytics dashboards** (no built-in fail-closed CI gate), while DeepEval, Giskard, promptfoo, and Great Expectations default to **pass/fail pipeline gates**. The synthesis must not treat "has a score" as "has a gate"; gate semantics are a separate design choice (§6.2).

---

### Criterion E1 — Per-axis metric decomposition (never single-number collapse)

| Field | Value |
|---|---|
| **Criterion** | Scoring system reports **each quality axis separately** with named identifiers; composite (if any) is derived and always shown alongside axis scores. |
| **How to measure** | Inspect rubric output schema: verify ≥3 independent axes (e.g. fidelity, structure, comprehension) each with own score/reason; confirm no consumer-facing report hides axes behind one headline number. |
| **Audit method** | Metric construct-validity audit (§5.4) + comparative benchmarking (§5.3) |
| **Scoring hook** | **§6.1** weighted composite must show per-dimension scores; **§6.6** band drivers named per axis |
| **Gaming vector** | Optimizing one high-weight axis while ignoring others (e.g. high NID, broken tables). |
| **Anti-gaming guard** | Require minimum thresholds on **each** load-bearing axis before composite computed (promptfoo `named metrics`; Ragas separate columns; GE separate expectations). |
| **Evidence grade** | **A** |
| **Sources** | Ragas faithfulness/context-precision docs (S1–S3); Ragas paper multi-dimension design (S4); promptfoo named-metrics docs (S11); GE Expectation Suite model (S14) |

**Exemplar practices:**
- **Ragas:** Faithfulness = supported-claims / total-claims; Context Precision = mean precision@k with rank sensitivity (irrelevant chunk at rank 1 halves score). Each metric documented with formula and blind spots (S1–S3, S4).
- **promptfoo:** Assertions sharing a `metric` name aggregate together; `derivedMetrics` compose named scores but keep constituents visible (S11).
- **Wrong for whisker:** Cargo-culting Ragas RAG axes (retrieval/generation) onto document-extraction QA; transfer the **decomposition pattern**, not the axis names.

---

### Criterion E2 — Score + reason (auditability of every number)

| Field | Value |
|---|---|
| **Criterion** | Every non-trivial score carries **human-readable justification** (reason, CoT, or expectation failure message), not a bare float. |
| **How to measure** | Sample N scored items; verify ≥90% have attached reason text traceable to input evidence; LLM-judge reasons flagged as advisory-only per whisker doctrine. |
| **Audit method** | Observability audit (§5.11) + confidence grading (§5.12) |
| **Scoring hook** | **§6.3** evidence grade B minimum for LLM-generated reasons; **§6.4** reasons required to detect cosmetic pass |
| **Gaming vector** | Template/generic reasons that do not cite failing evidence. |
| **Anti-gaming guard** | Spot-check reasons against source spans; fail rubric if reason contradicts score direction. |
| **Evidence grade** | **A** |
| **Sources** | Ragas v0.4 `MetricResult.value` + `.reason` (S5); DeepEval `metric.reason` (S7); TruLens `_with_cot_reasons` implementations (S8) |

**Exemplar practices:**
- **Ragas v0.4:** Metrics return `MetricResult` objects, not raw floats; experiments store `factual_reason` columns alongside scores (S5, S6).
- **DeepEval:** All predefined metrics output score **and** reasoning; `verbose_mode` logs per execution (S7).
- **TruLens:** Generation-based feedback uses rubric + parsing; CoT variants expose justification (S8).

---

### Criterion E3 — Explicit, calibrated thresholds (no implicit 0.5 defaults)

| Field | Value |
|---|---|
| **Criterion** | Every pass/fail boundary is **declared**, **documented**, and tied to labeled calibration data or a cited operating-point protocol; implicit library defaults treated as uncalibrated. |
| **How to measure** | Enumerate all gates/thresholds in rubric config; for each: (a) numeric value recorded, (b) calibration provenance (date, corpus, TPR/FPR) or explicit "borrowed—uncalibrated" flag per P16. |
| **Audit method** | Calibration / operating-point audit (§5.5) |
| **Scoring hook** | **§6.2** hard gates; **§6.6** flip conditions when threshold ±ε changes verdict |
| **Gaming vector** | Leaving DeepEval/TruLens default threshold at 0.5 so everything passes (documented footgun in DeepEval CI docs). |
| **Anti-gaming guard** | CI config review rejects unset thresholds; calibration ledger required before production gate promotion. |
| **Evidence grade** | **A** |
| **Sources** | DeepEval metrics default threshold 0.5 + explicit override requirement (S7, S9); TruLens scorer `threshold=0.7` example (S10); promptfoo threshold semantics for llm-rubric (S12) |

**Exemplar practices:**
- **DeepEval:** Success iff `score >= threshold`; default 0.5 for all metrics—docs warn explicit setting for CI (S7, S9).
- **TruLens / MLflow:** `Groundedness(..., threshold=0.7)`; default 0.5 if omitted (S10).
- **promptfoo:** Without `threshold`, llm-rubric passes on LLM `pass: true` even when `score: 0`—docs call this a common misconfiguration (S12).
- **Wrong for whisker:** Using cloud-judge thresholds from vendor demos without WG21 golden calibration (model-sovereignty + P16 method).

---

### Criterion E4 — Conjunctive hard gates independent of composite score

| Field | Value |
|---|---|
| **Criterion** | Non-negotiable checks **fail the verdict regardless of weighted score**; gates are logically AND-ed, not averaged away. |
| **How to measure** | Construct scenario where composite ≥ pass band but one hard gate fails; verify overall verdict = fail. Count gates; require ≤7 with written rationale each. |
| **Audit method** | Anti-gaming / Goodhart stress (§5.7) + maturity model (§5.2) |
| **Scoring hook** | **§6.2** hard gates conjunctive with weighted score |
| **Gaming vector** | High documentation/process score compensating for failed security or licensing gate. |
| **Anti-gaming guard** | Gate list includes at least one **canary that must fail** when inverted (P19); GE `severity: critical` pattern. |
| **Evidence grade** | **A** |
| **Sources** | GE Checkpoint `success` conjunctive (S14, S15); Giskard grade gate `ACCEPTABLE_GRADES` (S13); promptfoo pass-rate gate (S11); `00-FRAME.md` §6.2 |

**Exemplar practices:**
- **Great Expectations:** Checkpoint runs Validation Definitions; `CheckpointResult` success fails pipeline; expectations carry `severity: critical|warning|info` (S14, S15, S16).
- **Giskard Hub:** Scan grade A–D; CI exits non-zero if grade ∉ acceptable set (S13).
- **promptfoo:** `PROMPTFOO_PASS_RATE_THRESHOLD` (default 100%) triggers exit code 100 independent of individual assertion weights (S11).

---

### Criterion E5 — Suite-of-checks pattern (versioned expectation battery)

| Field | Value |
|---|---|
| **Criterion** | Quality rules live in a **named, versioned suite** of atomic checks; suites are reusable across batches/runs and diffable over time. |
| **How to measure** | Verify suite artifact exists (YAML/code) with stable name + version; each check maps to one measurable assertion; suite applied identically in CI and local runs. |
| **Audit method** | Conformance checklist (§5.1) + reproducibility replay (§5.8) |
| **Scoring hook** | **§6.1** sub-criteria map 1:1 to suite members; **§6.4** prevents "has eval code somewhere" gaming |
| **Gaming vector** | Ad-hoc checks in scripts that never run in CI; suite edited during eval to pass. |
| **Anti-gaming guard** | Suite hash pinned in CI; changes require review + changelog entry (GE store freshness checks). |
| **Evidence grade** | **A** |
| **Sources** | GE Expectation Suite + Validation Definition + Checkpoint (S14, S15); Giskard `generate_test_suite()` from scan (S17); promptfoo YAML test cases (S11) |

**Exemplar practices:**
- **Great Expectations:** Workflow = Connect → Define Expectations → Run Validations; suite is collection of expectations applied to batches (S14).
- **Giskard (legacy OSS):** `scan_results.generate_test_suite("My first test suite")` then `test_suite.run()` for regression (S17).
- **Giskard Hub:** Successful probe attempts promoted to dataset test cases with `checks` identifiers (S13).
- **promptfoo:** Declarative `tests` + `assert` blocks; assert-sets group related checks (S11).

---

### Criterion E6 — Weighted composition with declared weights (compensatory layer only)

| Field | Value |
|---|---|
| **Criterion** | If a composite exists, each input axis has a **declared weight with written rationale**; weights sum to fixed total; compensatory composite never replaces axis reporting. |
| **How to measure** | Weight table present; sensitivity analysis shows which axis swing moves composite across band (§6.6 flip condition). |
| **Audit method** | Weighted-scoring / rubric design (§5.3 analog via P15) + score uncertainty (§5.12) |
| **Scoring hook** | **§6.1** weights; **§6.6** sensitivity note mandatory |
| **Gaming vector** | Low-weight on hard-to-fix axes; weight tuning on holdout. |
| **Anti-gaming guard** | Holdout secrecy (P12/P19); steelman before down-weighting contested axis (§6.5). |
| **Evidence grade** | **B** |
| **Sources** | promptfoo assertion `weight` + weighted average (S11); promptfoo `derivedMetrics` (S11); DeepEval multi-metric `assert_test` lists (S9) |

**Exemplar practices:**
- **promptfoo:** Final test-case score = weighted average of assertion scores; optional custom scoring function over **named** metrics (S11).
- **DeepEval:** `assert_test(test_case, [metric1, metric2, ...])`—all must pass (conjunctive at test level), distinct from weighted average (S9).

**Contradiction:** promptfoo allows compensatory weighting; DeepEval `assert_test` is conjunctive-all-metrics. Synthesis should use **weights for maturity composite** and **conjunctive gates for non-negotiables** (§6.1 + §6.2 split).

---

### Criterion E7 — Regression detection with stored baseline

| Field | Value |
|---|---|
| **Criterion** | Eval system compares current run to a **marked baseline** (official run, prior checkpoint, or pinned suite version) and flags regressions per axis. |
| **How to measure** | Demonstrate baseline artifact + diff output; regression on one axis surfaces even if composite unchanged. |
| **Audit method** | Reproducibility replay (§5.8) + benchmarking methodology (§5.3 via P12) |
| **Scoring hook** | **§6.5** record both positions when baseline disputed; **§6.6** band shift from regression |
| **Gaming vector** | Re-baseline after every failure; comparing against stale unrelated run. |
| **Anti-gaming guard** | Baseline promotion requires explicit `--official` or tagged release; auto-rebaseline forbidden in CI. |
| **Evidence grade** | **B** |
| **Sources** | DeepEval `--official` flag for Confident AI baseline (S9); Ragas timestamped experiment CSVs (S6); Giskard attack→regression promotion (S13, S17) |

**Exemplar practices:**
- **DeepEval:** Designate official test run on Confident AI for future comparison (S9).
- **Ragas:** Experiments auto-save to `experiments/YYYYMMDD-HHMMSS-name.csv` with metadata (git commit, model version) (S6).
- **Giskard:** Scan findings → permanent test cases; re-run suite without regenerating scenarios in CI (S13).

---

### Criterion E8 — CI integration with fail-closed exit semantics

| Field | Value |
|---|---|
| **Criterion** | CI runs the same eval suite as local; failure produces **non-zero exit** and blocks merge; stderr/artifacts identify failing axis + reason. |
| **How to measure** | Run eval in CI on known-failing fixture; verify exit code contract and artifact retention. |
| **Audit method** | Conformance checklist (§5.1) + observability audit (§5.11) |
| **Scoring hook** | **§6.2** gates enforced in CI; **§6.4** same suite local/CI |
| **Gaming vector** | CI runs subset; `threshold: 0` or score-only mode to never fail (promptfoo documented pattern). |
| **Anti-gaming guard** | Ban score-collection mode in merge gates; require full suite hash match. |
| **Evidence grade** | **A** |
| **Sources** | DeepEval `deepeval test run` + pytest (S9); promptfoo exit codes 100/1 (S11); Giskard CI grade gate (S13) |

---

### Criterion E9 — Severity tiers and partial-pass semantics (fuzzy boundaries)

| Field | Value |
|---|---|
| **Criterion** | Checks declare **severity** or partial-credit rules; critical failures fail regardless of warning-level noise; fuzzy rules documented (`mostly`, assert-set threshold). |
| **How to measure** | Inject critical vs warning failures; verify checkpoint/verdict behavior matches declared severity table. |
| **Audit method** | Threshold calibration (§5.5) + anti-gaming (§5.7) |
| **Scoring hook** | **§6.2** critical = hard gate; **§6.6** warnings widen uncertainty band |
| **Gaming vector** | Downgrade all checks to `info` to always pass. |
| **Anti-gaming guard** | Minimum count of `critical` checks; severity immutable without ADR. |
| **Evidence grade** | **A** |
| **Sources** | GE `severity` + `mostly` parameters (S16); promptfoo `assert-set` with `threshold: 0.5` (S11); Giskard severity > 0 on attempts (S13) |

**Exemplar practices:**
- **Great Expectations:** `mostly` allows fuzzy validation (% rows passing); execution failures always recorded as critical (S16).
- **promptfoo:** `assert-set` passes if fraction of inner assertions ≥ set threshold (S11).
- **Giskard:** `attempt.severity > 0` marks successful attack (S13).

---

### Criterion E10 — Adversarial / red-team scores orthogonal to quality composite

| Field | Value |
|---|---|
| **Criterion** | Security/adversarial evaluation produces a **separate score or grade** from quality/fidelity composite; neither substitutes for the other. |
| **How to measure** | Verify two report sections; high quality score cannot override failed security grade. |
| **Audit method** | Adversarial methodology (§5.6) + maturity model (§5.2) |
| **Scoring hook** | **§6.2** security gate independent; **§6.5** if frameworks disagree on severity |
| **Gaming vector** | Running only happy-path quality metrics while skipping injection probes. |
| **Anti-gaming guard** | Mandatory Giskard-style probe catalog or equivalent; OWASP LLM Top 10 coverage tag set (S13). |
| **Evidence grade** | **B** |
| **Sources** | Giskard scan categories + OWASP mapping (S13); DeepEval safety metrics + DeepTeam pointer (S7); Giskard heuristics + LLM-assisted detectors (S17) |

---

### Criterion E11 — LLM-judge scores marked advisory in rubric (self-consistency)

| Field | Value |
|---|---|
| **Criterion** | Any score produced primarily by an LLM judge is **non-gating** in the audit rubric itself unless independently validated (P10); deterministic checks gate. |
| **How to measure** | Classify each rubric criterion by scorer type; verify LLM-judge outputs feed §6.1 composite only as capped weight or human-review queue. |
| **Audit method** | Metric construct-validity (§5.4) + confidence grading (§5.12) |
| **Scoring hook** | **§6.4** aligns with whisker advisory-LLM doctrine |
| **Gaming vector** | LLM judge grading LLM-heavy system without human anchor. |
| **Anti-gaming guard** | Require inter-rater agreement stats before promoting judge to gate (P10, P11). |
| **Evidence grade** | **B** |
| **Sources** | Ragas LLM-assisted metrics (S1–S4); DeepEval LLM-as-judge default (S7); TruLens LLM evaluation tier (S8); `00-FRAME.md` §6.4 |

**Contradiction:** DeepEval and Ragas treat LLM-judge scores as CI gates by default; whisker audit rubric must **not** copy that for advisory lanes without P10 validation. Transfer **structure** (threshold + reason), not **authority level**.

---

### Criterion E12 — Experiment / run metadata for score uncertainty bands

| Field | Value |
|---|---|
| **Criterion** | Published audit scores include **band** (not point only), naming drivers: contested criteria, low evidence grade, uncalibrated thresholds, LLM-judge variance. |
| **How to measure** | Final synthesis output shows composite band + list of uncertainty drivers; sensitivity names single flip criterion. |
| **Audit method** | Score uncertainty grading (§5.12) |
| **Scoring hook** | **§6.3** weakest evidence propagates; **§6.6** band + flip conditions |
| **Gaming vector** | False precision (two decimal places on uncalibrated LLM scores). |
| **Anti-gaming guard** | Round scores to defensible precision; widen band when any load-bearing input is grade C or below. |
| **Evidence grade** | **B** |
| **Sources** | Ragas experiment metadata fields (S6); promptfoo JSON eval outputs + pass-rate (S11); `00-FRAME.md` §6.6 |

---

## 3. External benchmark / exemplar bar

**Maturity ladder for scoring-system design (synthesis target):**

| Level | Bar (from framework exemplars) |
|---|---|
| **0** | Ad-hoc scripts; single number; no reasons; no CI. |
| **1** | Multiple metrics computed but collapsed in reporting; implicit thresholds. |
| **2** | Named per-axis scores + reasons; declarative tests; CI runs eval but gates weak (default 0.5). |
| **3** | Versioned suite/checkpoint; explicit calibrated thresholds; conjunctive hard gates; regression baseline; severity tiers. |
| **4** | Level 3 + adversarial suite orthogonal to quality; evidence grades on every criterion; composite band with flip analysis; LLM-judge quarantined to advisory unless P10-validated. |

**Professional bar:** Match **Great Expectations Checkpoint + Expectation Suite** rigor for deterministic checks, **promptfoo named-metric assertion composition** for multi-axis reporting, **DeepEval `assert_test` fail-closed CI** for regression enforcement, and **Giskard scan→regression promotion** for adversarial durability. **Ragas/TruLens** supply the **experiment trace + per-axis analytics** layer, not the gate authority.

**Strongest transferable scoring pattern (single recommendation):**

> **Suite-of-checks with named per-axis scores, severity-tiered expectations, explicit calibrated thresholds, conjunctive hard gates, and a pinned regression baseline—reported as axis table + banded composite, never a lone headline number.**

This fuses:
1. **Great Expectations:** versioned Expectation Suite → Validation Definition → Checkpoint with conjunctive `success` and `severity` (S14–S16).
2. **promptfoo:** named `metric` tags, weighted assertions, separate aggregation, CI pass-rate gate (S11–S12).
3. **DeepEval / Giskard:** pytest-grade fail-closed CI and scan→regression promotion (S9, S13, S17).

Ragas's **`MetricResult(score, reason)` + timestamped experiment CSVs** (S5–S6) are the strongest **reporting/trace** adjunct, not the gate core.

**Where exemplars are wrong for whisker:** Cloud-default judge models (Ragas, DeepEval, TruLens demos); Ragas reference-free RAG metrics as substitutes for WG21 golden fidelity; Giskard agent-security grades as document-QA quality; promptfoo pass-rate alone without per-axis floors.

---

## 4. Recommended weight & gate recommendation

| Recommendation | Rationale |
|---|---|
| **Dimension weight: 18%** of composite (scoring/calibration cluster shared with P14–P17) | Scoring-system shape is load-bearing for "defensibly-best-quality" verdict; frameworks consensus on decomposition + gates justifies high but not dominant weight. |
| **Hard gates (conjunctive): E4, E8** | Non-negotiable fail-closed CI and conjunctive gates mirror GE/Giskard/promptfoo; audit rubric cannot be softer than systems it judges. |
| **Hard gate candidate: E11** | LLM-judge gating without P10 validation fails whisker self-consistency (`00-FRAME.md` §6.4). |
| **Soft cap at level 2:** E3, E7 if uncalibrated / no baseline | Allows methodology design stage (Stage 0) but caps "professional-grade" claim until P16 executed on real labels. |
| **Evidence propagation** | Composite inherits weakest grade among E1, E4, E5, E8 (typically **A** when CI-enforced). |
| **Flip condition (§6.6)** | Re-classifying LLM-judge criterion from advisory to gating moves verdict across band without changing code scores. |

---

## 5. Sources

### Tier 1 — Authoritative / primary

| ID | Source | URL | Date/version |
|---|---|---|---|
| S4 | Es et al., *Ragas: Automated Evaluation of Retrieval Augmented Generation* (arXiv) | https://arxiv.org/abs/2309.15217 | v2, Sep 2023 |
| S16 | Great Expectations — Create an Expectation (severity, mostly) | https://docs.greatexpectations.io/docs/core/define_expectations/create_an_expectation/ | GX Core 1.19.0 |

### Tier 2 — Strong secondary (official project docs)

| ID | Source | URL | Date/version |
|---|---|---|---|
| S1 | Ragas — Faithfulness metric | https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/ | stable, Dec 2025 |
| S2 | Ragas — Context Precision metric | https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/ | stable, Dec 2025 |
| S3 | Ragas — Introduction / experiments-first | https://docs.ragas.io/en/stable/ | stable, Dec 2025 |
| S5 | Ragas — v0.3→v0.4 migration (`MetricResult`) | https://docs.ragas.io/en/stable/howtos/migrations/migrate_from_v03_to_v04/ | stable, Dec 2025 |
| S6 | Ragas — Experimentation | https://docs.ragas.io/en/stable/concepts/experimentation/ | stable, Dec 2025 |
| S7 | DeepEval — Metrics introduction (threshold, strict_mode, reason) | https://deepeval.com/docs/metrics-introduction | DeepEval 4.x, 2026 |
| S8 | TruLens — Feedback implementations | https://trulens.org/component_guides/evaluation/feedback_implementations/ | 2026 |
| S9 | DeepEval — Unit testing in CI/CD (`assert_test`, `--official`) | https://deepeval.com/docs/evaluation-unit-testing-in-ci-cd | DeepEval 4.x, 2026 |
| S10 | TruLens scorers with MLflow (threshold config) | https://www.trulens.org/cookbook/frameworks/mlflow/mlflow_trulens_scorers/ | 2026 |
| S11 | promptfoo — Assertions and metrics (weights, assert-set, CI env) | https://www.promptfoo.dev/docs/configuration/expected-outputs/ | 2026 |
| S12 | promptfoo — LLM rubric threshold semantics | https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/llm-rubric/ | 2026 |
| S13 | Giskard Hub — Scans SDK (grades A–D, CI gate, regression promotion) | https://docs.giskard.ai/hub/sdk/guides/scans | 2026 |
| S14 | Great Expectations — GX Core overview (suites, checkpoints, actions) | https://docs.greatexpectations.io/docs/core/introduction/gx_overview/ | GX Core 1.19.0 |
| S15 | Great Expectations — Checkpoint API reference | https://docs.greatexpectations.io/docs/reference/api/checkpoint_class/ | GX Core 1.19.0 |
| S17 | Giskard — LLM scan (OSS) + test suite generation | https://docs.giskard.ai/en/stable/open_source/scan/index.html | stable |

### Tier 3 — Contextual (corroboration only)

| ID | Source | URL |
|---|---|---|
| S18 | MLflow — TruLens scorers integration | https://mlflow.org/docs/latest/genai/eval-monitor/scorers/third-party/trulens/ |
| S19 | promptfoo — CLI reference (exit codes) | https://www.promptfoo.dev/docs/usage/command-line/ |

**Source count:** 2 Tier-1 + 15 Tier-2 = **17 distinct Tier 1–2 sources** (floor ≥3 satisfied).

**Strongest transferable scoring pattern (restated):** Suite-of-checks + named per-axis scores + severity tiers + explicit thresholds + conjunctive gates + pinned regression baseline + banded composite reporting (GE + promptfoo + DeepEval/Giskard fusion).

---

## 6. Overlap statement

This persona researched **external eval-framework scoring design only**. It did **not** open whisker production code, cite whisker `file:line`, score whisker, clone/fork/copy code, or duplicate:

- **`persona/` / `llm-stack/`** — prior whisker code audits (deterministic core and tapetum lane).
- **`buildvsbuy/`** — library-choice decisions for metric implementations.
- **`deepseek-v4-pro/`** — single-model selection eval.
- **`p09`–`p13`, `p15`–`p17`** — those personas own construct validity, calibration method, weighting theory, and uncertainty grading; P30 supplies **framework exemplar patterns** that **feed §6.1–§6.6**, not duplicate their methods.
- **`p14`** — audit maturity model skeleton (OpenSSF/SAMM); P30 is case-study of eval tools, not maturity frameworks.
- **`p18`–`p19`** — red-team and Goodhart methodology; P30 cites Giskard only as scoring/gate exemplar, not attack taxonomy design.

Boundary held: **eval-framework scoring-system criteria and external bar**, unique in the roster (`00-ROSTER.md` P30 overlap boundary), handed to synthesis as inputs for the scoring-design requirements in `00-FRAME.md` section 6.
