# whisker Professional-Grade Audit - Stage 0 Evidence Frame

**Stage:** 0 (evidence framing only). **Author role:** Stage 0 evidence-framing lead.
**Date:** 2026-07-18. **Scope of THIS document:** design the audit; do not run it.

This file plus `00-ROSTER.md` are the complete Stage 0 output. Downstream stages
(the 30 Composer-2.5 internet-research personas, then an Opus synthesis) consume
these two files. Nothing here scores whisker.

---

## 1. Objective

Design a rigorous, repeatable audit that later answers ONE decision question:

> Is `packages/whisker` a **professional, hybrid (deterministic core + advisory
> LLM overlay), well-documented, defensibly-best-quality** WG21 extraction-QA
> package, and where must it improve to be so?

The audit must be able to assess whether whisker:

1. is **professional** and **release-ready** as a Python package (packaging,
   API contract, tests, CI, deps, docs), judged against external standards and
   serious exemplars (Google LangExtract, IBM Docling, and others chosen on
   evidence);
2. is a coherent **hybrid** design: a strict deterministic, LLM-free gate plus
   an opt-in advisory LLM layer that never gates, cleanly separated;
3. **combines the user's and Sean's determinism approaches** into one defensible
   determinism doctrine (a strict-reproducible core reconciled with a
   nondeterminism-tolerant advisory layer);
4. is **well-documented**, specifically that `src/whisker/CLAUDE.md` and the
   operator surface meet a defensible documentation/operator-UX bar;
5. reaches the **best defensible LLM extraction / conversion-QA quality** that
   the evidence supports, with metrics whose construct validity and calibration
   hold up.

Stage 0 produces the **frame**: the objective, the non-goals, an overlap map
against prior research, a source hierarchy, an audit-method taxonomy, the
downstream scoring-design requirements, and an exact 30-persona roster.

---

## 2. Non-goals (hard boundaries for THIS stage and its personas)

- **No whisker production-code inspection or scoring.** Stage 0 read only
  `packages/whisker/research/**` (for overlap) and `src/whisker/CLAUDE.md`
  (only to enumerate already-documented categories, never to judge quality).
  The 30 personas are **internet-research** personas: they research HOW to audit
  and WHAT "good" looks like externally. They do not open whisker source, cite no
  whisker `file:line`, and reach no whisker verdict. Producing the verdict is a
  later stage, not this one.
- **No cloning, forking, or code copying.** Case-study personas read public
  docs, papers, release notes, and (read-only, in-browser) public source; they
  extract *practices and criteria*, never vendored code.
- **No edits outside `packages/whisker/research/Audit/**`.** The parent
  `research/` dir already exists; `Audit/` is created here at explicit user
  request. Package-boundary rule stands: whisker research artifacts only.
- **No re-litigation of settled prior research.** Where a prior swarm already
  reached a code-level verdict (see the overlap map), personas must not repeat
  it; they operate one level up, on *method and external benchmark*, and hand the
  synthesis a rubric, not a re-derived finding.
- **This is a frame, not a plan of record.** It imposes no architecture decision
  on whisker and does not touch the protected `projects/.../PROJECT-PLAN*` set.

---

## 3. Existing-research overlap map (what is already covered, and the boundary)

Prior work under `packages/whisker/research/` is substantial. The audit must not
duplicate it. Two prior swarms already performed **code-level audits**; several
folders already cover **narrow build/consume decisions**. The 30 new personas are
deliberately pitched at the **methodology / external-standard** layer that these
did not cover.

| Prior folder | What it already did | Level | Overlap risk | Boundary the new personas must hold |
|---|---|---|---|---|
| `persona/` (30 personas + 5 opus) | Code-level audit of whisker's **deterministic core** vs an evidence baseline (metrics, calibration, gates, TEDS/NID/MHS, ground truth, WG21 domain, FP/FN, maintainability, corpus, schema, regression). | whisker code verdict | HIGH | New personas research *external method/standard* for the same topics; they never re-audit whisker code or cite the evidence baseline. |
| `llm-stack/` (22 personas + 5 opus) | Code-level audit of whisker's **advisory LLM lane** (`tapetum_llm`): isolation, fail-not-partial, injection defense, cascade, calibration, schema compliance, grounding. Verdict: harden. | whisker code verdict | HIGH | New personas research *how to audit* hybrid LLM lanes and *what best practice is*, not whether tapetum is hardened. |
| `langextract/` (22 personas + 5 opus) | Deep audit of Google **LangExtract** as an adoption candidate; verdict adopt-partially (port the aligner DP, reject the library). | external repo adoption verdict | MED | The LangExtract case-study persona treats it as a **release/eval/provenance EXEMPLAR** (packaging, eval harness, grounding provenance, docs), NOT to re-decide algorithm adoption. |
| `redteam/` (28 converter reports) | Per-repo red-team of external converters (docling, marker, MinerU, nougat, olmocr, surya, unstructured, camelot, grobid, firecrawl, ...). | external converter red-team | MED | Case-study personas view these repos as **engineering/eval maturity exemplars** (release, typed API, benchmarking, governance, comprehension eval), not as converters to red-team again. |
| `buildvsbuy/` | Build-vs-buy per whisker metric mechanism (calibration ROC, exact lane, TEDS, edit distance, MHS, anchors, versioned baselines). | library-choice decision | MED | New personas do not re-pick metric libraries; the metrics personas research **construct validity and calibration method**, not which package to import. |
| `base64-blob-filter/` | Blob/base64 filtering + converter survey. | narrow feature | LOW | Avoid; no persona targets blob filtering. |
| `llm-batching/` | Concurrency/throughput/batch-endpoint research for the LLM lane. | infra/throughput | LOW-MED | The observability/failure persona excludes throughput tuning; the hybrid-architecture persona excludes batch-endpoint selection. |
| `deepseek-v4-pro/` | Model-specific eval of one candidate model for the judge/extraction task. | model selection | LOW-MED | The LLM-as-judge persona researches **judge-eval science generally**, not one model's benchmark scores. |
| `repos/` | Cloned repo trees / READMEs (git metadata). | raw material | LOW | Case studies read public docs live; no persona depends on the local clones. |
| Root syntheses (`tapetum-llm-decision-synthesis.md`, `whisker-llm-lane4-plan.md`, `comprehension-poc-report.md`, `models-vram-deployment-survey.md`, `toc-ab-experiment.md`, golden-review findings) | Prior decisions + POC evidence for the LLM lane, comprehension POC, model deployment. | decisions/POC | MED | Personas must not restate these decisions as findings; they may be cited by the synthesis as internal context but are out of scope for internet-research personas. |

**Documented-category note (from `CLAUDE.md`, categories only, no quality judgment):**
CLAUDE.md already *documents* three lanes (stability/fidelity/comprehension), the
LLM-free hard gate, an advisory oracle overlay, an opt-in `tapetum_llm` lane, a
blind `whisker-readback` check, named-constant thresholds, exit-code CI contract,
trace/debug artifacts, calibration status, and a golden-file roadmap. The audit's
documentation persona (P20) assesses **whether that documentation meets an
external doc/operator-UX standard**, not whether the described design is good
(that is other personas' rubric territory, run later on code, not in Stage 0).

**Net Stage-0 conclusion:** the gap prior research leaves is exactly a
**methodology-and-standard frame**: nobody has assembled the external rubric that
a professional-grade / best-defensible-quality verdict should be measured
against. That gap is what the 30 personas fill.

---

## 4. Source hierarchy (evidence-quality contract for every persona)

Every persona ranks and cites sources by tier. Findings must rest on Tier 1-2;
Tier 3 contextualizes; Tier 4 may only *point to* a primary source and can never
be the sole basis for a criterion.

- **Tier 1 - Authoritative / primary.** Peer-reviewed papers; official standards
  and specs (PEPs, PyPA packaging guides, OWASP LLM Top 10, NIST SSDF / AI RMF,
  SLSA, ISO/IEC, SPDX); benchmark-defining papers (e.g. OmniDocBench, DP-Bench,
  PubTabNet/TEDS, GriTS); official metric/tool documentation.
- **Tier 2 - Strong secondary.** Official project source, release notes,
  CHANGELOGs, typed API references, and maintainer-authored design docs of the
  exemplar projects; reproducible leaderboards; conference/workshop proceedings.
- **Tier 3 - Contextual.** Reputable engineering blogs, well-cited conference
  talks, established practitioner handbooks, mature framework docs.
- **Tier 4 - Weak / corroborating only.** Forum threads, issue comments, vendor
  marketing, undated blogs. Allowed only to *locate* Tier 1-2 material.

**Per-persona floor:** at least **3 distinct Tier 1-2 primary sources**, each with
a stable URL and (where applicable) a date/version. Prefer sources dated within
~3 years unless citing a foundational standard. Contradicting sources must be
surfaced, not hidden. Every criterion a persona proposes for the rubric must trace
to at least one Tier 1-2 citation.

---

## 5. Audit-method taxonomy (the non-redundant method inventory)

The eventual audit is not one method; it is a portfolio. Each method answers a
distinct question and has a distinct failure mode, so they are not
interchangeable. Personas map their output to one or more of these methods so the
synthesis can assemble a coverage matrix with no duplicate lens.

1. **Conformance checklist** - measure against an external standard as a
   yes/no/partial checklist (PyPA packaging, OWASP LLM, SLSA, SPDX). Answers:
   "does it meet the published bar?" Fails at: things no standard covers.
2. **Maturity-model / capability-level scoring** - place each dimension on an
   ordinal ladder (e.g. level 0-4). Answers: "how far along?" Fails at:
   false precision if levels are ill-defined.
3. **Comparative benchmarking against exemplars** - contrast whisker's practice
   with LangExtract/Docling/olmOCR/etc. Answers: "is this normal / best-in-class?"
   Fails at: exemplars may themselves be wrong (must cite, not worship).
4. **Metric construct-validity audit** - does each quality metric measure what it
   claims (TEDS = table structure, NID = text similarity, comprehension = fact
   recovery)? Answers: "is the number meaningful?" Fails at: statistical rigor.
5. **Calibration / operating-point audit** - are thresholds fitted on labeled
   data at a stated FPR/TPR, or borrowed? Answers: "are the gates set right?"
   Fails at: needs a labeled corpus (method design only in Stage 0).
6. **Adversarial / red-team probing** - construct attacks that pass gates while
   corrupting content. Answers: "what slips through?" Fails at: coverage of the
   attack space.
7. **Anti-gaming / Goodhart stress** - can the score be inflated without real
   quality gain? Answers: "is the metric a target that stops being a measure?"
8. **Reproducibility replay** - rerun-and-diff; quantify run-to-run variance and
   its containment. Answers: "is it deterministic where it claims to be?"
9. **Documentation-completeness audit** - a doc coverage matrix (contract,
   usage, invariants, failure modes, calibration status, known gaps, agent
   guidance). Answers: "can a new operator/agent succeed from the docs alone?"
10. **Provenance / license conformance audit** - port-vs-vendor hygiene,
    attribution, license compatibility, third-party notices, fork discipline.
11. **Observability / fault-injection audit** - trace/debug completeness,
    fail-closed behavior, error surfacing under injected faults.
12. **Confidence / evidence grading of findings** - every finding carries an
    evidence grade and a confidence, so the synthesis can weight them.

---

## 6. Scoring-design requirements (what the downstream synthesis MUST build)

Stage 0 does not fix the weights (that needs the personas' external evidence). It
fixes the **shape** the scoring system must take. The synthesis stage is required
to deliver all of the following, each justified by persona-collected Tier 1-2
evidence:

### 6.1 Weighted composite with declared dimensions
- A fixed set of scored dimensions (candidate set mirrors the persona clusters:
  release-readiness, architecture/hybrid, determinism, extraction-quality/eval,
  scoring/calibration, adversarial-robustness, documentation/operator-UX,
  provenance/licensing, security/privacy/supply-chain, observability/failure).
- Explicit weights that sum to a fixed total, **with a written rationale per
  weight** citing evidence (a weight is a claim, not a vibe).
- Per-dimension sub-criteria scored on a bounded ordinal scale (e.g. 0-4 maturity
  levels) with concrete level descriptors, not adjectives.
- **No single composite number reported alone.** Per-dimension scores are always
  shown alongside the composite (exemplar precedent: OmniDocBench/kapa.ai never
  collapse per-axis scores into one figure; whisker's own docs state the same).

### 6.2 Hard gates (pass/fail independent of the weighted score)
- A short list of **non-negotiable gates** that cap or fail the overall verdict
  regardless of how high the weighted score is. Candidate gates (to be justified
  by personas): licensing/attribution violation; a security/prompt-injection hole
  at a trust boundary; an LLM signal that can hard-gate (violating the advisory
  contract); a determinism claim that replay refutes; a quality metric with a
  disproven construct validity used as a gate.
- Gates are **conjunctive with** the weighted score: a high weighted score with a
  failed gate is still a failing verdict (mirrors whisker's own conjunctive
  guard/anchor/facts design; the audit rubric should be no weaker than the thing
  it audits).

### 6.3 Confidence and evidence grades
- Every finding and every sub-criterion score carries: (a) an **evidence grade**
  (e.g. A = multiple Tier-1 corroborating; B = single Tier-1 or converging
  Tier-2; C = Tier-3 only / contested; D = Tier-4 / speculative), and (b) a
  **confidence** (high/medium/low) reflecting source agreement and directness.
- The composite propagates the *weakest* evidence grade among its load-bearing
  inputs (an audit is only as strong as its shakiest gate).

### 6.4 Anti-gaming rules
- Criteria must be written so they cannot be satisfied by cosmetic compliance
  (e.g. "has tests" -> "tests exercise the gate's teeth with a canary that must
  fail"; "documented" -> "an operator/agent can reproduce a run from docs
  alone"). Each persona proposing a criterion must state its **gaming vector** and
  the anti-gaming guard that closes it (Goodhart discipline).
- Scores derived from LLM output are advisory in the rubric too: the audit must
  not let an LLM-generated number gate the audit verdict (self-consistent with
  whisker's own advisory-only doctrine).

### 6.5 Disagreement handling
- When personas (or sources) disagree, the synthesis records **both positions**,
  the evidence tier of each, and a decision rule: prefer the higher Tier;
  on equal Tier, prefer the one reproducible against an exemplar; if still tied,
  mark the criterion **contested** and lower its weight/confidence rather than
  picking arbitrarily.
- A steelman is mandatory for any dimension scored below the pass line: the
  strongest case *for* whisker's current choice must be recorded before the
  low score stands (precedent: every prior swarm ran a steelman persona).

### 6.6 Score uncertainty
- The composite is reported as a **band, not a point** (e.g. score +/- derived
  from contested criteria and low-confidence inputs), with the specific criteria
  driving the uncertainty named.
- A sensitivity note: which single criterion, if re-graded, would move the
  verdict across a band boundary (the audit's own "flip conditions").

---

## 7. Case-study distribution (no redundant repo reports)

Mandatory: **Google LangExtract** and **IBM Docling** each get a dedicated
case-study persona. To avoid one-report-per-repo bloat (the `redteam/` folder
already has 28 single-repo reports), the remaining ecosystems are **grouped by
the lesson they teach**, not by repo:

- **P26 LangExtract** (solo) - release/eval/provenance exemplar; extraction +
  grounding provenance practice. Boundary vs `langextract/` swarm: engineering &
  eval maturity, not algorithm adoption.
- **P27 Docling** (solo) - enterprise release maturity, typed API, benchmarking,
  governance, docs. Boundary vs `redteam/docling.md`: exemplar practices, not
  converter red-team.
- **P28 olmOCR / Marker / MinerU** (grouped) - comprehension/QA-based eval,
  zero-authoring baseline checks, and model-serving engineering maturity.
- **P29 unstructured / Nougat / Surya** (grouped) - public API design, packaging,
  license-model shifts, and eval transparency.
- **P30 Eval-framework family** (grouped: Ragas, DeepEval, TruLens, Giskard,
  promptfoo, Great Expectations) - how mature *evaluation/data-quality*
  frameworks structure scoring, gating, reporting, and regression - directly
  feeding the scoring-design requirements in section 6.

Each case-study persona must isolate **transferable practices with citations**,
tag each practice with the audit dimension it informs, and explicitly note where
an exemplar's choice would be **wrong for whisker** (model-sovereignty,
determinism, WG21 domain), so the synthesis does not cargo-cult.

---

## 8. The exact 30-persona roster (summary; full mandates in `00-ROSTER.md`)

All 30 are Composer-2.5 internet-research personas. Each is mutually distinct,
has a narrow question, suggested queries, source-quality requirements, and a
unique output filename under `packages/whisker/research/Audit/`. Cluster grouping:

**A. Professional Python package & release readiness**
1. Python Packaging & Release-Readiness Auditor - `p01-python-release-readiness.md`
2. Public API & Contract-Design Researcher - `p02-api-contract-design.md`
3. Dependency & Supply-Chain Hygiene Researcher - `p03-dependency-supply-chain.md`
4. CI/CD & Test-Suite Maturity Researcher - `p04-cicd-test-maturity.md`

**B. Architecture & hybrid deterministic+LLM design**
5. Hybrid Deterministic-Core + Advisory-LLM Architecture Researcher - `p05-hybrid-architecture.md`
6. Determinism & Reproducibility Standards Researcher - `p06-determinism-reproducibility.md`
7. Dual-Determinism Reconciliation Researcher (user's + Sean's) - `p07-dual-determinism-reconciliation.md`
8. Modularity, Coupling & Package-Boundary Researcher - `p08-modularity-boundaries.md`

**C. Extraction quality & eval science**
9. Document-Extraction Quality-Metrics Researcher - `p09-extraction-quality-metrics.md`
10. LLM-as-Judge Eval-Science Researcher - `p10-llm-as-judge-eval.md`
11. Ground-Truth & Corpus-Construction Methodologist - `p11-ground-truth-corpus.md`
12. Benchmarking & Leaderboard-Methodology Researcher - `p12-benchmarking-methodology.md`
13. Comprehension-vs-Fidelity Evaluation Researcher - `p13-comprehension-vs-fidelity.md`

**D. Audit frameworks, scoring & calibration**
14. Audit-Framework & Maturity-Model Researcher - `p14-audit-frameworks-maturity.md`
15. Weighted-Scoring & Rubric-Design Researcher - `p15-weighted-scoring-rubric.md`
16. Threshold-Calibration & Operating-Point Researcher - `p16-threshold-calibration.md`
17. Score-Uncertainty & Evidence-Grading Researcher - `p17-score-uncertainty-grading.md`

**E. Adversarial / anti-gaming**
18. Adversarial / Red-Team Methodology Researcher - `p18-adversarial-methodology.md`
19. Anti-Gaming & Goodhart-Robustness Researcher - `p19-anti-gaming-goodhart.md`

**F. Documentation & operator UX**
20. Documentation & Agent-Guidance (CLAUDE.md) Researcher - `p20-documentation-agent-guidance.md`
21. Operator & CLI-UX Researcher - `p21-operator-cli-ux.md`

**G. Provenance, licensing, security, privacy, observability**
22. Provenance, Licensing & Fork-Hygiene Researcher - `p22-provenance-licensing.md`
23. Security & Prompt-Injection Defense Researcher - `p23-security-prompt-injection.md`
24. Privacy & Data-Governance Researcher - `p24-privacy-data-governance.md`
25. Observability, Tracing & Failure-Handling Researcher - `p25-observability-failure-handling.md`

**H. Repository & framework case studies**
26. LangExtract Engineering & Eval Case Study - `p26-case-langextract.md`
27. Docling (IBM) Engineering & Governance Case Study - `p27-case-docling.md`
28. olmOCR / Marker / MinerU Comprehension-Eval Case Study - `p28-case-olmocr-marker-mineru.md`
29. unstructured / Nougat / Surya API & Serving Case Study - `p29-case-unstructured-nougat-surya.md`
30. Eval-Framework Family Case Study (Ragas/DeepEval/TruLens/Giskard/promptfoo/Great Expectations) - `p30-case-eval-frameworks.md`

**Coverage check (13 required areas -> personas):** release-readiness P01/P02/P04;
architecture P05/P08; hybrid determinism+LLM P05/P07; determinism/reproducibility
P06/P07; extraction quality & eval science P09/P10/P11/P13; audit frameworks
P14/P15; adversarial/red-team P18/P19; documentation & operator UX P20/P21;
provenance/licensing/fork hygiene P22; security/privacy/supply chain
P03/P23/P24; observability/failure P25; benchmarking/scoring calibration
P12/P16/P17; repo lessons P26-P30. Every area is covered by at least two
non-redundant lenses except the single-owner niches (provenance P22,
observability P25), which are intentionally focused.

---

## 9. Dispatch contract (how the personas run downstream)

- Each persona is a **separate** Composer-2.5 internet-research task, run in
  parallel (fan-out), fan-in to an Opus synthesis.
- Each writes exactly one markdown file to `packages/whisker/research/Audit/`
  using its assigned filename. No persona writes outside `Audit/`.
- Each report follows a fixed skeleton so the synthesis can machine-fold them:
  **(1) Question restated; (2) Proposed audit criteria** (each = criterion,
  how-to-measure, the audit-method from section 5 it uses, the scoring-design
  hook from section 6 it feeds, its gaming vector + anti-gaming guard, evidence
  grade, source citations); **(3) External benchmark / exemplar bar**;
  **(4) Recommended weight & whether it should be a hard gate, with rationale**;
  **(5) Sources** (tiered, with URLs/dates); **(6) Overlap statement**
  confirming it did not re-audit whisker code or duplicate the named prior folder.
- No persona inspects whisker production code. The synthesis, in a later stage,
  applies the assembled rubric to the code.

---

## 10. Open questions recorded (anti-convergence self-check)

- **Who "Sean" is and the exact shape of his determinism approach** is not
  resolvable from `research/**` or `CLAUDE.md` alone. P07 is framed to research
  *external precedents for reconciling two determinism doctrines* (strict
  reproducible core + tolerated advisory nondeterminism) so the method holds
  regardless; the synthesis must obtain the concrete "user vs Sean" definitions
  from the user before scoring that dimension. Flagged, not assumed.
- **Weights are deferred to evidence.** Stage 0 fixes the scoring *shape*
  (section 6), not the numbers; assigning weights without the personas' Tier-1-2
  evidence would be exactly the unsupported assumption this frame forbids.
- **Calibration needs a labeled corpus** that Stage 0 does not build; P16
  designs the calibration *method* and operating-point protocol, to be executed
  later against real labels.
