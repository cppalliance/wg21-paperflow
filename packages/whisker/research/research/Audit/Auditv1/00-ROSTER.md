# whisker Professional-Grade Audit - Stage 0 Persona Roster (dispatch-ready)

30 mutually distinct Composer-2.5 **internet-research** personas. Each is a
separate task, run in parallel, fan-in to an Opus synthesis.

**Global rules for every persona (do not repeat per entry):**
- You are an internet-research persona. **Do NOT open, inspect, or score whisker
  production code.** Cite no whisker `file:line`. Reach no whisker verdict. Your
  job is to research external method, standards, and exemplars, and to hand back
  *audit criteria + an external bar*, not a whisker judgment.
- Obey the source hierarchy in `00-FRAME.md` section 4: >= 3 distinct Tier 1-2
  primary sources, stable URLs + dates/versions, contradictions surfaced.
- Write exactly ONE file to `packages/whisker/research/Audit/<your filename>`.
  Write nowhere else.
- Follow the fixed report skeleton in `00-FRAME.md` section 9 (Question ->
  Criteria -> External bar -> Weight/gate recommendation -> Sources -> Overlap
  statement). Tag each criterion with its audit-method (section 5) and its
  scoring-design hook (section 6), and state its gaming vector + anti-gaming
  guard.
- Do not clone, fork, or copy code. Read public docs/papers/source in-browser.
- End with an explicit **overlap boundary** confirmation naming the prior folder
  you avoided duplicating.

---

## Cluster A - Professional Python package & release readiness

### 1. Python Packaging & Release-Readiness Auditor
- **File:** `p01-python-release-readiness.md`
- **Mandate (unique):** Define the external bar for a *professional, releasable*
  Python package and turn it into audit criteria: `pyproject.toml` conformance,
  build backend, wheel/sdist correctness, semantic versioning + release cadence,
  changelog discipline, entry-point/console-script hygiene, Python-version
  support policy, packaging metadata completeness.
- **Web questions / search leads:** "PyPA packaging user guide pyproject 2026";
  "PEP 621 / PEP 517 build metadata"; "semantic versioning + keepachangelog for
  libraries"; "Python packaging release-readiness checklist"; "console_scripts
  entry points best practice".
- **Required primary-source types:** PyPA official guides, relevant PEPs,
  semver.org/keepachangelog specs, official setuptools/hatch/uv docs.
- **Overlap boundary:** Not a whisker-code audit; not the `buildvsbuy/`
  library-choice decision. Packaging-standard criteria only.

### 2. Public API & Contract-Design Researcher
- **File:** `p02-api-contract-design.md`
- **Mandate (unique):** External standards for public-API stability of a library:
  what belongs in the public surface, `__all__` / re-export discipline, typing
  (`py.typed`, PEP 561), deprecation policy, backward-compat guarantees, "library
  returns data, caller persists" separation-of-concerns as an API contract.
- **Web questions:** "PEP 561 typed package distribution"; "library public API
  deprecation policy best practice"; "hyrum's law API stability"; "designing
  Python library APIs guidance"; "SemVer public API definition".
- **Required sources:** PEP 561/387, PyPA typing docs, authoritative API-design
  writing (e.g. maintainer guides, published talks).
- **Overlap boundary:** Distinct from the `persona/` / `llm-stack/` code-level
  "api-contract-design" personas (those scored whisker code); this researches the
  external contract standard only.

### 3. Dependency & Supply-Chain Hygiene Researcher
- **File:** `p03-dependency-supply-chain.md`
- **Mandate (unique):** Bar for dependency and supply-chain hygiene: pinning vs
  ranges, lockfiles, SBOM (CycloneDX/SPDX), SLSA build provenance, dependency
  license compatibility, minimizing transitive/optional-extra risk, vuln scanning.
- **Web questions:** "SLSA supply chain levels 2026"; "CycloneDX SBOM Python";
  "NIST SSDF dependency management"; "pip-audit / OSV dependency scanning";
  "optional extras vs core deps best practice".
- **Required sources:** SLSA spec, NIST SSDF (SP 800-218), CycloneDX/SPDX specs,
  PyPA + OSV docs.
- **Overlap boundary:** Distinct from `p22` (that is licensing/provenance/fork
  hygiene of ported code); this is dependency/supply-chain integrity. Not a
  whisker dep-tree audit.

### 4. CI/CD & Test-Suite Maturity Researcher
- **File:** `p04-cicd-test-maturity.md`
- **Mandate (unique):** External bar for test-suite and CI maturity of a QA tool:
  coverage expectations and their limits, hermetic/deterministic CI tests,
  canary/mutation tests ("gate with teeth"), test matrix (OS/Python), property
  vs example tests, what a QA tool must itself test to be trusted.
- **Web questions:** "mutation testing value evidence"; "hermetic tests CI best
  practice"; "test coverage as a target Goodhart"; "property-based testing
  hypothesis when to use"; "GitHub Actions test matrix Python packages".
- **Required sources:** peer-reviewed mutation/coverage-efficacy studies,
  pytest/hypothesis official docs, CI provider docs.
- **Overlap boundary:** Not the `persona/` "test-suite-auditor" code scoring;
  external test-maturity standard only.

---

## Cluster B - Architecture & hybrid deterministic+LLM design

### 5. Hybrid Deterministic-Core + Advisory-LLM Architecture Researcher
- **File:** `p05-hybrid-architecture.md`
- **Mandate (unique):** Research the architectural pattern of a strict
  deterministic core with an opt-in, never-gating advisory LLM overlay: how
  serious systems separate a trusted decision path from an assistive
  nondeterministic one, one-way "demote-only" ratchets, lane isolation to prevent
  confirmation bias, and how to audit that the separation actually holds.
- **Web questions:** "human-in-the-loop advisory vs authoritative ML decision
  systems"; "LLM as advisory not gating design pattern"; "guardrail vs judge
  architecture"; "confirmation bias LLM-as-judge isolation"; "fail-safe vs
  fail-secure control architecture".
- **Required sources:** peer-reviewed HITL / decision-support literature, OWASP/
  NIST guidance on ML decision authority, reputable systems-architecture writing.
- **Overlap boundary:** Not the `llm-stack/` audit of whisker's tapetum isolation;
  researches the general pattern + audit method. Excludes batch/throughput
  (`llm-batching/`).

### 6. Determinism & Reproducibility Standards Researcher
- **File:** `p06-determinism-reproducibility.md`
- **Mandate (unique):** External standards for reproducibility and determinism in
  computational pipelines: pure-function determinism, ordering/seed control,
  sources of run-to-run variance (concurrency, unordered iteration, floating
  point, hosted-LLM nondeterminism), the difference between bit-exact and
  quality-stable reproducibility, and how to *test/verify* a determinism claim.
- **Web questions:** "reproducibility computational research standards ACM";
  "deterministic pipeline testing rerun-and-diff"; "batch-invariant LLM inference
  nondeterminism"; "quality-stable vs bit-exact reproducibility"; "seed and
  ordering control determinism".
- **Required sources:** ACM reproducibility badging / reproducibility papers,
  vendor/research writing on LLM inference nondeterminism, testing-methodology
  literature.
- **Overlap boundary:** Not the `persona/`/`llm-stack/` "determinism-auditor"
  code findings; external standard + verification method only.

### 7. Dual-Determinism Reconciliation Researcher (user's + Sean's approaches)
- **File:** `p07-dual-determinism-reconciliation.md`
- **Mandate (unique):** Research external precedents for **reconciling two
  distinct determinism doctrines into one coherent contract**: a strict
  reproducible core plus a deliberately tolerated nondeterministic advisory layer
  (the "combine the user's and Sean's determinism approaches" requirement). How do
  mature systems document a layered determinism boundary, decide which guarantees
  apply where, and prevent the weaker layer's nondeterminism from leaking into the
  strong one? Produce the *criteria* for judging whether two such approaches are
  cleanly combined. **Note:** the concrete "user vs Sean" definitions are an open
  question (see `00-FRAME.md` section 10); research the reconciliation method so
  it holds regardless, and flag that the synthesis must obtain the two definitions
  from the user.
- **Web questions:** "tiered determinism guarantees system design"; "mixing
  deterministic and probabilistic components contract"; "eventual vs strict
  consistency analogy determinism layers"; "reconciling conflicting design
  doctrines architecture decision record"; "boundary between reproducible core
  and nondeterministic subsystem".
- **Required sources:** systems/architecture literature on layered guarantees,
  ADR practice, consistency-model writing used analogically (cited as analogy).
- **Overlap boundary:** No prior folder addresses reconciling two determinism
  doctrines; unique. Not a whisker-code audit.

### 8. Modularity, Coupling & Package-Boundary Researcher
- **File:** `p08-modularity-boundaries.md`
- **Mandate (unique):** External bar for module design and package boundaries in a
  standalone package: coupling/cohesion metrics, import-layering contracts
  (import-linter), "consume other packages via public API only", one-way
  dependency direction, and how to *measure* boundary integrity.
- **Web questions:** "import-linter layered architecture Python"; "coupling
  cohesion metrics software quality"; "package boundary enforcement monorepo";
  "acyclic dependencies principle"; "public API vs private symbol discipline".
- **Required sources:** import-linter docs, software-architecture-metrics
  literature, monorepo package-boundary practice.
- **Overlap boundary:** Not the `persona/` "maintainability-complexity" code
  score; external boundary-integrity method only.

---

## Cluster C - Extraction quality & eval science

### 9. Document-Extraction Quality-Metrics Researcher
- **File:** `p09-extraction-quality-metrics.md`
- **Mandate (unique):** Catalog the accepted quality metrics for document->markdown
  extraction and their **construct validity**: TEDS / S-TEDS, GriTS, NID /
  normalized edit distance, set precision/recall/F1, content recall, reading-order
  metrics. What each truly measures, its known blind spots, and when it must be
  null-eligible (modality absent). Produce metric-validity criteria.
- **Web questions:** "TEDS tree edit distance table structure PubTabNet";
  "GriTS grid table similarity paper"; "normalized edit distance document
  conversion metric"; "OmniDocBench metrics definitions"; "reading order metric
  document parsing".
- **Required sources:** TEDS/PubTabNet, GriTS, OmniDocBench, DP-Bench papers +
  official metric docs.
- **Overlap boundary:** Not `buildvsbuy/` (which package to import) nor the
  `persona/` metric code scores; researches construct validity of the metrics.

### 10. LLM-as-Judge Eval-Science Researcher
- **File:** `p10-llm-as-judge-eval.md`
- **Mandate (unique):** The science of using an LLM to judge extraction quality:
  known biases (position, verbosity, self-preference, sycophancy), agreement with
  humans, confidence (mis)calibration, verdict instability across reruns, and the
  methodology to *validate* a judge before trusting it. Produce criteria for
  auditing an advisory LLM judge's trustworthiness.
- **Web questions:** "LLM-as-a-judge bias evaluation survey 2026"; "LLM judge
  agreement with human annotators"; "self-reported confidence calibration LLM";
  "verdict flip rate LLM evaluation stability"; "position/verbosity bias LLM
  judge".
- **Required sources:** peer-reviewed LLM-as-judge papers (e.g. MT-Bench line),
  calibration literature, bias studies.
- **Overlap boundary:** Not the `llm-stack/` audit of tapetum's cascade; external
  judge-eval science. Not model selection (`deepseek-v4-pro/`).

### 11. Ground-Truth & Corpus-Construction Methodologist
- **File:** `p11-ground-truth-corpus.md`
- **Mandate (unique):** Methodology for building trustworthy ground truth without
  a perfect oracle: annotation protocols, inter-annotator agreement (kappa/alpha),
  provenance of labels (draft vs verified vs human-blessed), stratified sampling
  for corpus representativeness, and the independence problem (author != verifier
  != answerer). Produce corpus-quality and label-provenance criteria.
- **Web questions:** "inter-annotator agreement Cohen kappa Krippendorff";
  "annotation guidelines gold standard construction"; "stratified sampling corpus
  representativeness"; "label provenance verification data quality"; "annotator
  independence bias".
- **Required sources:** annotation-methodology papers, IAA statistics references,
  data-quality standards.
- **Overlap boundary:** Not the `persona/` "ground-truth-provenance" code finding;
  external methodology only.

### 12. Benchmarking & Leaderboard-Methodology Researcher
- **File:** `p12-benchmarking-methodology.md`
- **Mandate (unique):** How serious document-parsing benchmarks are built and
  reported: per-axis (never single-number) scoring, separating content coverage
  from reading order, null-eligibility of absent modalities, held-out vs
  dev/replay splits, avoiding tuning on the holdout, and honest cross-tool
  comparison. Produce benchmarking-integrity criteria.
- **Web questions:** "OmniDocBench methodology per-axis scoring"; "DP-Bench
  document parsing benchmark"; "held-out test set contamination avoidance";
  "benchmark reporting standards ML"; "separating content coverage reading order
  evaluation".
- **Required sources:** OmniDocBench, DP-Bench, Docling eval, benchmark-integrity
  literature.
- **Overlap boundary:** Not the `redteam/` per-converter reports; external
  benchmarking method. Distinct from P16 (calibration) and P09 (metric validity).

### 13. Comprehension-vs-Fidelity Evaluation Researcher
- **File:** `p13-comprehension-vs-fidelity.md`
- **Mandate (unique):** The distinction between *fidelity* (resemblance to a
  reference) and *comprehension* (a downstream reader can recover the facts), and
  how to evaluate comprehension: question-answering / fact-recovery eval, blind
  read-back methodology, why "regenerate similar text" round-trips are the wrong
  test, and adversarial controls (corrupt-and-recheck). Produce comprehension-eval
  criteria.
- **Web questions:** "downstream task evaluation vs surface similarity";
  "question answering evaluation document extraction"; "faithfulness vs fluency
  evaluation"; "adversarial control corrupted input evaluation"; "blind reading
  comprehension test methodology".
- **Required sources:** QA-eval papers, faithfulness-evaluation literature,
  downstream-task-eval writing.
- **Overlap boundary:** Not the internal `comprehension-poc-report.md` results;
  external comprehension-eval science + method.

---

## Cluster D - Audit frameworks, scoring & calibration

### 14. Audit-Framework & Maturity-Model Researcher
- **File:** `p14-audit-frameworks-maturity.md`
- **Mandate (unique):** How rigorous technical audits and maturity models are
  structured: capability/maturity ladders (CMMI-style, OpenSSF Scorecard, SAMM),
  dimension decomposition, level descriptors, and evidence requirements per level.
  Produce the *skeleton* of the whisker audit's maturity model.
- **Web questions:** "OpenSSF Scorecard checks methodology"; "OWASP SAMM maturity
  levels"; "CMMI capability levels software"; "software maturity model rubric
  design"; "audit evidence requirements standard".
- **Required sources:** OpenSSF Scorecard docs, OWASP SAMM, CMMI/ISO references.
- **Overlap boundary:** Unique; no prior folder builds the audit's own maturity
  model. Feeds section 6.1.

### 15. Weighted-Scoring & Rubric-Design Researcher
- **File:** `p15-weighted-scoring-rubric.md`
- **Mandate (unique):** How to design a defensible weighted composite: MCDA / AHP
  weighting, pitfalls of composite indices (compensatory masking), when to use
  hard gates (non-compensatory criteria) vs weights, and how to justify each
  weight. Produce the weighting + hard-gate design rules.
- **Web questions:** "multi-criteria decision analysis weighting methods";
  "composite indicator methodology OECD pitfalls"; "non-compensatory vs
  compensatory scoring"; "analytic hierarchy process weighting"; "rubric design
  reliability".
- **Required sources:** OECD composite-indicator handbook, MCDA/AHP literature,
  rubric-reliability research.
- **Overlap boundary:** Unique; feeds section 6.1-6.2. Not a whisker score.

### 16. Threshold-Calibration & Operating-Point Researcher
- **File:** `p16-threshold-calibration.md`
- **Mandate (unique):** How to set gate thresholds from labeled data: ROC/PR
  analysis, choosing an operating point at a constrained FPR/TPR, reporting
  precision/recall at the chosen point, the risk of borrowed/uncalibrated
  thresholds, and a concrete calibration protocol (label N, fit, commit with
  recorded TPR/FPR). Produce the calibration method (to run later on real labels).
- **Web questions:** "ROC curve operating point selection FPR constraint";
  "threshold calibration classification best practice"; "precision recall
  tradeoff gate threshold"; "Youden index / cost-based threshold"; "calibration
  reliability diagram".
- **Required sources:** ROC/PR methodology, calibration literature, applied
  operating-point selection.
- **Overlap boundary:** Not the `buildvsbuy/calibration-roc.md` library choice nor
  a whisker threshold audit; the calibration *method*. Distinct from P12/P17.

### 17. Score-Uncertainty & Evidence-Grading Researcher
- **File:** `p17-score-uncertainty-grading.md`
- **Mandate (unique):** How to express uncertainty in an audit score and grade the
  evidence behind findings: evidence-grading systems (GRADE-style), confidence
  levels, propagating the weakest evidence grade, reporting a score band vs a
  point, and sensitivity/"flip condition" analysis. Produce sections 6.3 + 6.6.
- **Web questions:** "GRADE evidence quality grading system"; "confidence levels
  in assessment reporting"; "uncertainty quantification scoring band"; "sensitivity
  analysis decision threshold"; "evidence hierarchy grading".
- **Required sources:** GRADE handbook, evidence-hierarchy literature,
  uncertainty/sensitivity-analysis references.
- **Overlap boundary:** Unique; feeds sections 6.3 and 6.6. Not a whisker score.

---

## Cluster E - Adversarial / anti-gaming

### 18. Adversarial / Red-Team Methodology Researcher
- **File:** `p18-adversarial-methodology.md`
- **Mandate (unique):** How to red-team an extraction-QA system: attack taxonomies
  for content that passes gates while corrupting meaning (token-preserving
  reorderings, table row/cell swaps, math relation flips, decoy tables, code
  garbling), structured red-team process, and coverage measurement of the attack
  space. Produce adversarial-robustness criteria + a probe catalog design.
- **Web questions:** "red teaming ML systems methodology"; "adversarial evaluation
  document AI"; "metamorphic testing corruption invariance"; "OCR/parse robustness
  attack taxonomy"; "test oracle adversarial examples".
- **Required sources:** red-team methodology papers, metamorphic-testing
  literature, adversarial-eval writing.
- **Overlap boundary:** Not the `redteam/` per-converter reports (those red-team
  external converters); this researches red-team *method* for QA gates. Distinct
  from the `persona/` "adversary-gate-evasion" code finding.

### 19. Anti-Gaming & Goodhart-Robustness Researcher
- **File:** `p19-anti-gaming-goodhart.md`
- **Mandate (unique):** Goodhart's-law defenses for metrics used as gates: how a
  score gets gamed by cosmetic compliance, multi-metric triangulation, canaries
  that must fail, holdout secrecy, and writing criteria that resist optimization
  pressure. Produce the anti-gaming rules for section 6.4 and a gaming-vector
  checklist every criterion must pass.
- **Web questions:** "Goodhart's law metrics gaming"; "specification gaming ML";
  "metric overfitting benchmark contamination"; "canary test gate teeth";
  "reward hacking evaluation robustness".
- **Required sources:** Goodhart/specification-gaming literature, benchmark-
  contamination studies, measurement-validity writing.
- **Overlap boundary:** Unique; feeds section 6.4. Not a whisker audit.

---

## Cluster F - Documentation & operator UX

### 20. Documentation & Agent-Guidance (CLAUDE.md) Researcher
- **File:** `p20-documentation-agent-guidance.md`
- **Mandate (unique):** External bar for technical documentation AND for
  agent-guidance files (`CLAUDE.md` / `AGENTS.md`): what a complete doc set covers
  (contract, usage, invariants, failure modes, calibration status, known gaps,
  architecture map, greppable conventions), documentation-quality rubrics
  (e.g. Diataxis), and how agent-rule files are structured in serious repos.
  Produce a doc-completeness matrix as audit criteria.
- **Web questions:** "Diataxis documentation framework"; "AGENTS.md standard
  convention"; "CLAUDE.md best practices repository"; "good README / docs rubric
  open source"; "documentation completeness checklist library".
- **Required sources:** Diataxis, AGENTS.md/agent-file conventions, exemplar repo
  docs (Docling/firecrawl AGENTS.md/CLAUDE.md observed in `repos/`), doc-quality
  writing.
- **Overlap boundary:** Uses `CLAUDE.md` only for the *category list* (already
  captured in `00-FRAME.md` section 3); does not judge whisker's doc quality here.
  Not the `persona/` "documentation-claims" code finding.

### 21. Operator & CLI-UX Researcher
- **File:** `p21-operator-cli-ux.md`
- **Mandate (unique):** The bar for developer-tool CLI UX: exit-code contracts,
  stdout-is-result / stderr-is-progress separation, machine-readable output
  (`--json`) hygiene, triaged summaries (pytest/ruff/eslint patterns), actionable
  error messages, and progress-bar-safe piping. Produce operator-UX criteria.
- **Web questions:** "command line interface guidelines clig.dev"; "exit code
  conventions POSIX tools"; "machine readable CLI output json best practice";
  "ruff / eslint output format design"; "actionable error message guidelines".
- **Required sources:** clig.dev / CLI-guidelines, POSIX exit-code conventions,
  exemplar tool docs (ruff, pytest, eslint).
- **Overlap boundary:** Unique; external CLI-UX standard, not a whisker CLI audit.

---

## Cluster G - Provenance, licensing, security, privacy, observability

### 22. Provenance, Licensing & Fork-Hygiene Researcher
- **File:** `p22-provenance-licensing.md`
- **Mandate (unique):** The bar for using others' code correctly: license
  compatibility matrices (MIT/Apache-2.0/BSD/BSL/GPL), port-vs-vendor discipline,
  attribution and `THIRD_PARTY_NOTICES`, copyright-header hygiene, and honest
  provenance when an algorithm is re-implemented from an external repo. Produce
  provenance/licensing criteria and candidate hard gates.
- **Web questions:** "Apache-2.0 attribution requirements port"; "license
  compatibility matrix GPL MIT BSD"; "SPDX license identifiers"; "third party
  notices best practice"; "clean-room reimplementation provenance".
- **Required sources:** SPDX, OSI/Apache/BSL license texts, license-compatibility
  references.
- **Overlap boundary:** Distinct from `p03` (dependency/supply-chain integrity);
  this is license/attribution/fork hygiene. Not the `langextract/` adoption
  verdict (which already covered the Apache-2.0 attribution for the DP port).

### 23. Security & Prompt-Injection Defense Researcher
- **File:** `p23-security-prompt-injection.md`
- **Mandate (unique):** Security bar for a pipeline that feeds untrusted document
  and web text to LLMs: prompt-injection defense (delimiter escaping, treat
  content as data, structured output), OWASP LLM Top 10, input validation at trust
  boundaries, tool/scope minimization, and how to *test* injection defenses.
  Produce security criteria and candidate hard gates.
- **Web questions:** "OWASP Top 10 for LLM applications 2026"; "prompt injection
  defense delimiter data not instruction"; "indirect prompt injection document";
  "structured output injection mitigation"; "LLM tool scope least privilege".
- **Required sources:** OWASP LLM Top 10, NIST AI RMF, prompt-injection research.
- **Overlap boundary:** Distinct from `p24` (privacy). Not the `llm-stack/`
  tapetum injection-defense code audit; external standard + test method.

### 24. Privacy & Data-Governance Researcher
- **File:** `p24-privacy-data-governance.md`
- **Mandate (unique):** Data-governance bar for a document pipeline: handling of
  potentially sensitive source content, data minimization, retention of debug/
  trace artifacts, sending content to (self-hosted vs cloud) models, and
  reproducibility-vs-privacy tension. Produce privacy/governance criteria.
  (Scoped to what applies to a public WG21-paper QA tool; flag where WG21 papers
  are public and thus lower-risk, so criteria are proportionate.)
- **Web questions:** "data minimization principle privacy by design"; "LLM data
  handling governance self-hosted vs cloud"; "log/trace artifact retention
  sensitive data"; "NIST privacy framework"; "PII handling document pipelines".
- **Required sources:** NIST Privacy Framework, privacy-by-design references,
  data-governance guidance.
- **Overlap boundary:** Unique; distinct from `p23` (security) and `p25`
  (observability). Not a whisker audit.

### 25. Observability, Tracing & Failure-Handling Researcher
- **File:** `p25-observability-failure-handling.md`
- **Mandate (unique):** The bar for observability and failure handling in a QA
  pipeline: structured logging (not print), trace vs debug artifact separation
  (concise progress dump vs full-fidelity I/O), fail-closed / fail-not-partial
  behavior, error surfacing, and fault-injection testing. Produce observability +
  failure-handling criteria.
- **Web questions:** "structured logging best practice observability";
  "fail-closed vs fail-open design"; "fault injection testing chaos";
  "OpenTelemetry tracing conventions"; "graceful degradation batch pipeline error
  handling".
- **Required sources:** OpenTelemetry docs, SRE/observability literature,
  fault-injection/chaos-engineering references.
- **Overlap boundary:** Not the `persona/`/`llm-stack/` "error-handling" code
  scores; external observability standard + fault-injection method. Excludes
  throughput (`llm-batching/`).

---

## Cluster H - Repository & framework case studies

### 26. LangExtract Engineering & Eval Case Study
- **File:** `p26-case-langextract.md`
- **Mandate (unique):** Study Google **LangExtract** as an EXEMPLAR of extraction
  engineering: its release/packaging maturity, eval/test harness, grounding-
  provenance return shape (`char_interval` / alignment status), documentation, and
  provenance/licensing posture. Extract transferable practices; tag each to an
  audit dimension; note where its choices (cloud-first defaults, fail-soft) would
  be WRONG for whisker (model-sovereignty, fidelity).
- **Web questions:** "LangExtract GitHub release notes changelog"; "LangExtract
  grounding char interval alignment docs"; "LangExtract eval / examples"; "Google
  LangExtract packaging pyproject"; "LangExtract self-hosted model support issue".
- **Required sources:** official LangExtract repo docs/release notes, its README/
  API docs, its LICENSE.
- **Overlap boundary:** The `langextract/` swarm already decided *adopt the DP,
  reject the library*; this persona does NOT re-decide adoption - it mines
  engineering/eval/provenance *practices* as audit criteria.

### 27. Docling (IBM) Engineering & Governance Case Study
- **File:** `p27-case-docling.md`
- **Mandate (unique):** Study IBM **Docling** as an EXEMPLAR of enterprise release
  maturity: typed API design, benchmarking/eval transparency, table-structure
  verification (`verify_table_v2`, span-aware grids), governance
  (MAINTAINERS/CONTRIBUTING/code-of-conduct), release cadence, and docs. Extract
  transferable practices tagged to audit dimensions; note domain mismatches.
- **Web questions:** "Docling documentation API reference"; "Docling benchmarks
  DP-Bench"; "Docling table structure recognition TableFormer"; "Docling release
  notes governance MAINTAINERS"; "Docling typed models pydantic".
- **Required sources:** official Docling docs/repo, Docling technical report/paper,
  its governance files.
- **Overlap boundary:** `redteam/docling.md` red-teamed Docling as a converter;
  this mines maturity/governance/eval *practices*, not converter defects.

### 28. olmOCR / Marker / MinerU Comprehension-Eval Case Study
- **File:** `p28-case-olmocr-marker-mineru.md`
- **Mandate (unique):** Grouped study of **olmOCR, Marker, MinerU** for three
  lessons: (a) comprehension/QA-oriented evaluation (olmOCR is noted as the rare
  converter testing comprehension), (b) zero-authoring baseline sanity checks
  (non-empty content, no long repeated n-grams / mojibake), and (c) model-serving
  engineering maturity. Extract practices; keep the three repos' distinct lessons
  separate (no merged mush); tag to audit dimensions.
- **Web questions:** "olmOCR evaluation methodology comprehension"; "olmOCR
  quality checks repeated ngram mojibake"; "Marker pdf conversion benchmarks";
  "MinerU evaluation OmniDocBench"; "olmOCR / Marker release engineering".
- **Required sources:** official olmOCR/Marker/MinerU docs, olmOCR paper/eval,
  their READMEs/benchmarks.
- **Overlap boundary:** `redteam/` has single-repo reports for each; this groups
  them by *lesson* (comprehension eval, baseline checks, serving) to avoid
  redundant per-repo reports.

### 29. unstructured / Nougat / Surya API & Serving Case Study
- **File:** `p29-case-unstructured-nougat-surya.md`
- **Mandate (unique):** Grouped study of **unstructured, Nougat, Surya** for:
  (a) public API/library design and packaging, (b) license-model shifts and their
  lessons for OSS extraction tools, and (c) eval transparency / reported metrics
  (Nougat's edit-distance/F1 reporting). Extract practices; keep distinct lessons
  separate; tag to audit dimensions.
- **Web questions:** "unstructured.io library API partition license"; "Nougat
  paper metrics edit distance BLEU"; "Surya OCR benchmarks documentation";
  "unstructured license change open source"; "Nougat / Surya packaging release".
- **Required sources:** official unstructured/Nougat/Surya docs + Nougat paper,
  their LICENSE files/history.
- **Overlap boundary:** `redteam/` covered these as converters; this mines API/
  packaging/license/eval *practices* as audit criteria.

### 30. Eval-Framework Family Case Study (Ragas / DeepEval / TruLens / Giskard / promptfoo / Great Expectations)
- **File:** `p30-case-eval-frameworks.md`
- **Mandate (unique):** Grouped study of mature **evaluation and data-quality
  frameworks** for how they structure scoring and reporting: per-metric scores,
  gating/thresholds, regression detection, confidence/uncertainty reporting,
  test-suite-of-checks patterns (Great Expectations "expectations"), and CI
  integration. This directly feeds the scoring-design requirements (section 6);
  extract *scoring-system* patterns, tagged to sections 6.1-6.6.
- **Web questions:** "Ragas metrics scoring faithfulness answer relevancy";
  "DeepEval assertions pytest LLM"; "TruLens feedback functions"; "Giskard LLM
  scan test suite"; "promptfoo assertions grading"; "Great Expectations
  expectation suite data quality".
- **Required sources:** official docs of each framework, their scoring/threshold
  documentation.
- **Overlap boundary:** Unique; no prior folder studies eval-framework *scoring
  design*. Feeds section 6.

---

## Filename manifest (uniqueness check)

`p01-python-release-readiness.md`, `p02-api-contract-design.md`,
`p03-dependency-supply-chain.md`, `p04-cicd-test-maturity.md`,
`p05-hybrid-architecture.md`, `p06-determinism-reproducibility.md`,
`p07-dual-determinism-reconciliation.md`, `p08-modularity-boundaries.md`,
`p09-extraction-quality-metrics.md`, `p10-llm-as-judge-eval.md`,
`p11-ground-truth-corpus.md`, `p12-benchmarking-methodology.md`,
`p13-comprehension-vs-fidelity.md`, `p14-audit-frameworks-maturity.md`,
`p15-weighted-scoring-rubric.md`, `p16-threshold-calibration.md`,
`p17-score-uncertainty-grading.md`, `p18-adversarial-methodology.md`,
`p19-anti-gaming-goodhart.md`, `p20-documentation-agent-guidance.md`,
`p21-operator-cli-ux.md`, `p22-provenance-licensing.md`,
`p23-security-prompt-injection.md`, `p24-privacy-data-governance.md`,
`p25-observability-failure-handling.md`, `p26-case-langextract.md`,
`p27-case-docling.md`, `p28-case-olmocr-marker-mineru.md`,
`p29-case-unstructured-nougat-surya.md`, `p30-case-eval-frameworks.md`.

30 files, all distinct. None collide with existing `Audit/` files
(`00-FRAME.md`, `00-ROSTER.md`).
