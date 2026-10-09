# W5 — Eval/QA frameworks combining deterministic checks with LLM judging (2026 landscape)

Research date: 2026-07-22. Sources: official docs, arXiv, GitHub, vendor blogs (8 web searches).

---

- DeepEval metrics use a `threshold` (default 0.5); `metric.is_successful()` is true only when score meets threshold, so LLM-judge scores can gate Pytest/CI pass-fail. — https://deepeval.com/docs/metrics-introduction — 2026 (docs current) — **Relevance:** mainstream pattern treats LLM verdict as gating when wired into test assertions; matches our baseline finding that 0/31 conversion-QA repos gate mechanically on LLM, but DeepEval enables it if teams choose.

- DeepEval `DAGMetric` builds decision-tree evals where terminal outcomes map to controlled scores; docs position it for "hard gates" (e.g., invalid JSON fails before tone scoring) while branch decisions remain LLM-based. — https://deepeval.com/docs/metrics-dag — 2026 — **Relevance:** hybrid deterministic+LLM composition closest to a layered gate inside one metric; still no separate claim-generation/recall stage.

- DeepEval blog (2026) recommends G-Eval for subjective criteria and DAG for objective/mixed criteria with explicit scoring branches; advises `strict_mode` (binary 0/1) when flakiness is unacceptable. — https://deepeval.com/blog/llm-as-a-judge — 2026 — **Relevance:** ecosystem treats LLM judges as primary scorers with optional deterministic pre-gates, not advisory-only by default.

- Ragas `Faithfulness` decomposes a response into atomic claims (LLM step), then checks each claim against retrieved context (LLM step); score = supported claims / total claims. — https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/ — 2025-12-09 — **Relevance:** clearest mainstream "claim generation + evidence verification" two-stage pattern; verification is precision-only (cannot surface defects the decomposer never emits), analogous to our `grounding.py` asymmetry.

- Ragas also ships `FaithfulnesswithHHEM`, replacing the per-claim LLM verifier with Vectara's HHEM-2.1-Open classifier for hallucination detection on claim–context pairs. — https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/ — 2025-12-09 — **Relevance:** hybrid LLM claim extraction + deterministic/neural verifier second stage; closer to our two-lane fusion idea than pure LLM-as-judge.

- Ragas docs note non-LLM context-precision variants using string similarity for cheap deterministic checks alongside LLM-judged metrics. — https://qaskills.sh/blog/ragas-faithfulness-answer-relevancy-context-precision-recall-reference-2026 — 2026 — **Relevance:** explicit deterministic+LLM metric layering in RAG eval stacks; no built-in routing budget for which samples get expensive faithfulness.

- Promptfoo docs recommend stacking deterministic assertions (`is-json`, `javascript`, `regex`) before model-graded rubrics, and a separate preflight eval to skip judge calls on structurally invalid outputs. — https://www.promptfoo.dev/docs/guides/llm-as-a-judge/ — 2026 — **Relevance:** documented fail-fast deterministic gate before LLM judge; maps to "deterministic tripwires first" answer-class 5 in baseline.

- Promptfoo "Tiered evaluation" guidance: Tier 1 deterministic always-on, Tier 2 cheap judge always-on, Tier 3 expensive judge conditional on failures, borderline cases, or high-risk routes. — https://www.promptfoo.dev/docs/guides/llm-as-a-judge/ — 2026 — **Relevance:** only surveyed framework with explicit budget-aware scheduling of which items get expensive LLM inspection; parallels our `MAX_UNIT_CHECKS` starvation problem but user-configured not severity-sorted.

- Promptfoo supports CI gating via pass-rate thresholds or `--fail-on-error`; model-graded assertions are paid/non-deterministic while deterministic checks are free/stable. — https://qaskills.sh/blog/promptfoo-llm-testing-guide — 2026 — **Relevance:** LLM verdicts gate merges when teams set thresholds; default posture is engineering gate not advisory triage.

- LangSmith supports offline/online evals and LLM-as-a-judge evaluators with human annotation queues; "Align Evals" calibrates judge scores using human corrections as few-shot examples. — https://www.langchain.com/resources/langsmith-vs-braintrust — 2026 — **Relevance:** judge treated as production scorer with human calibration loop; no native claim-then-verify architecture for document fidelity.

- LangSmith vs Braintrust comparison: LangSmith CI/CD quality gates require custom GitHub Actions scripting; Braintrust ships native `braintrustdata/eval-action` posting PR score summaries. — https://www.braintrust.dev/articles/langsmith-vs-braintrust — 2026 — **Relevance:** gating is opt-in engineering discipline everywhere; Braintrust optimizes for release-control workflows.

- Braintrust docs show `braintrustdata/eval-action@v2` on pull requests and `bt eval --first N` for PR smoke runs vs full merge runs. — https://www.braintrust.dev/docs/evaluate/run-evaluations — 2026 — **Relevance:** budget sampling at dataset level (first N cases), not per-unit severity routing within a document.

- Braintrust eval-action posts experiment score tables to PR comments; merge blocking depends on eval code throwing when scores regress (standard CI exit codes). — https://github.com/braintrustdata/eval-action — 2026 — **Relevance:** LLM scorers can gate merges but threshold logic lives in user eval code, not framework policy.

- Inspect AI (UK AISI) Task = dataset + solver + scorer; built-in scorers include deterministic `match`/`includes`/`pattern`/`choice`/`math` and model-graded `model_graded_qa`/`model_graded_fact`. — https://inspect.aisi.org.uk/scorers.html — 2026 — **Relevance:** composable deterministic+LLM scorers for safety/benchmark evals; oriented to model capability not document conversion QA.

- Third-party `inspect-build-time-contract` lint warns when `@verifiable_task` uses model-graded scorers where deterministic alternatives exist; cites Inspect guidance "deterministic where possible, LLM where necessary." — https://pypi.org/project/inspect-build-time-contract/ — 2026 — **Relevance:** ecosystem norm explicitly prefers deterministic scorers; LLM grading is fallback not authority.

- Inspect AI supports `--no-score` deferral, cost/token limits per task/sample, and an early-stopping API based on previously scored samples. — https://inspect.aisi.org.uk/standard-scorers.html — 2026 — **Relevance:** budget controls exist at eval-run level, not selective per-defect-class routing within one artifact.

- OpenAI Evals platform is deprecating: read-only for existing users 2026-10-31, full shutdown 2026-11-30. — https://developers.openai.com/api/docs/guides/evals — 2026 — **Relevance:** hosted OpenAI eval gating is sunset; teams migrating to composed local graders.

- OpenAI evals best practices recommend composed graders: cheap deterministic `string_check`/Python first, model grader only when needed; all `testing_criteria` must pass for item success. — https://qaskills.sh/blog/openai-evals-graders-complete-reference-2026 — 2026 — **Relevance:** official layered pattern mirrors Promptfoo/DeepEval; LLM judge is conditional fallback after deterministic gate.

- Google LangExtract maps extractions to `char_interval` source offsets and flags ungrounded extractions (`char_interval = None`) for filtering. — https://github.com/google/langextract — 2026 — **Relevance:** extraction+grounding verification for IE, not defect detection; precision control after LLM generation, no recall for un-generated spans.

- Evidence Chain Evaluation (ECE, arXiv 2607.18240) is a tool-routed verification agent (web/scholarly/executable checks) returning structured verdicts with abstention on weak evidence; 97.8% selective accuracy on answered claims. — https://arxiv.org/html/2607.18240 — 2026-07 — **Relevance:** agentic claim verification with abstain, closer to advisory+fusion than hard gate; external evidence not same-document deterministic compare.

- SEVRA (arXiv 2606.19808) trains a recoverability gate to accept a base solver answer or invoke active verification under a token budget; selective policy verifies 3.0% of GSM8K examples vs always-on. — https://arxiv.org/html/2606.19808v1 — 2026-06 — **Relevance:** 2026 research on budget-aware selective verification routing; serving-layer gate not document QA, but directly addresses answer-class 2 (routing/budget starvation).

- Verifiable Process Rewards (VPR, arXiv 2605.10325) converts symbolic/algorithmic oracles into dense turn-level rewards, checking each intermediate action with verifiers (MCTS, constraints, posteriors). — https://arxiv.org/html/2605.10325v2 — 2026-05 — **Relevance:** PRM-style process verification for agentic reasoning; deterministic oracle per step, not claim-then-verify over document pairs.

- ACL 2026 Findings "Verifiable Process Reward Models" (VPRMs) apply rule-based deterministic verifiers to intermediate reasoning steps in medical risk-of-bias assessment; up to 20% F1 gain vs outcome-only verification. — https://aclanthology.org/2026.findings-acl.1611.pdf — 2026 — **Relevance:** structured-domain step verification with deterministic rules; evidence grounding emphasis but domain-specific rubrics not generic markdown fidelity.

- Knovo 2026 framework comparison: RAGAS strongest for retrieval metrics, DeepEval for CI-native Pytest gates, Promptfoo for prompt/model regression matrices; none positioned as document-conversion golden verification. — https://www.knovo.dev/guides/ai-evaluation-frameworks — 2026 — **Relevance:** confirms eval frameworks target RAG/prompt CI, not PDF/HTML→Markdown golden diff QA like whisker.

- Atlan 2026 comparison notes RAGAS/DeepEval/TruLens default to reference-free LLM-as-judge (faithfulness, relevancy) measuring internal consistency not external correctness against a human golden. — https://atlan.com/know/llm-evaluation-frameworks-compared/ — 2026 — **Relevance:** supports baseline answer-class 5: LLM judges score coherence with context, not contract-encoded golden rules (secno stripping, wrapped table cells).

- QASkills Ragas vs DeepEval 2026: both incur judge token cost and non-determinism; recommends DeepEval DAG or repeated runs for release gates needing reproducible numbers. — https://qaskills.sh/blog/ragas-vs-deepeval-2026 — 2026 — **Relevance:** industry treats LLM eval scores as noisy signals; deterministic structures preferred for gates, LLM for triage/monitoring.

- No surveyed framework (DeepEval, Ragas, Promptfoo, LangSmith, Braintrust, Inspect, OpenAI evals) documents source-aware unit routing with a hard cap displacing high-severity routed-but-unchecked units (our PR #286 `MAX_UNIT_CHECKS=5` failure mode). — synthesis of above sources — 2026-07-22 — **Relevance:** our routing/budget starvation gap appears internal; ecosystem budget controls are dataset-level or tier-conditional, not per-page severity queues.

- Closest architectural analog to whisker `tapetum_llm`: Ragas faithfulness (LLM claims + context verification) plus optional HHEM deterministic verifier; differs because verification cannot add recall and frameworks treat passing threshold as gate not advisory-only fusion cap. — synthesis — 2026-07-22 — **Relevance:** partial precedent for two-stage LLM+deterministic pipeline; none combine deterministic lane authority with advisory LLM lane and evidence subtraction-only semantics.
