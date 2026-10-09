# 05 - Web finding cards (5 foragers, 2026-07-16)

Grouped by originating question. Cite as `05-web.md / <question> / <title>`.

## Q1: LLM-as-judge as a mechanical CI/accept gate in production doc-AI (2025-2026)?

- **olmOCR-Bench: Deterministic Unit Tests Instead of LLM-as-Judge** (HIGH)
  https://github.com/allenai/olmocr/tree/main/olmocr/bench
  7,000+ binary pass/fail unit tests across 1,400 pages, explicitly designed to avoid
  LLM-as-judge and fuzzy gold-text matching because model judges are biased and
  unreliable. Eval uses simple machine-checkable facts (text presence, table cell
  relationships, reading order, math symbols). CI via pytest.

- **ParseBench: Rule-Based Document Parsing Eval (No LLM Judge)** (HIGH)
  https://github.com/run-llama/parsebench
  LlamaIndex, ~2,000 enterprise PDF pages, 167K+ rules. Explicit: "ParseBench does not
  use LLM-as-judge - all evaluation is deterministic and rule-based." Cites olmOCR.

- **Unstructured SCORE: Production Doc-Parsing Metrics Without LLM Judge** (HIGH)
  https://github.com/Unstructured-IO/unstructured-eval-metrics
  Interpretation-agnostic deterministic metrics (adjusted edit distance, omission/
  hallucination diagnostics, table cell accuracy). Traditional metrics reversed
  rankings on 2-5% of pages; answer was better deterministic metrics, not judges.

- **Marker: LLM-as-Judge for Benchmarks, Not Production CI Gate** (MED)
  https://github.com/datalab-to/marker
  LLM judge only in the public benchmark suite; CI/quality control is structural and
  heuristic.

- **What Happens When LLM-Judge CI Gates Are Treated as Hard Blockers** (HIGH)
  https://www.theorydelta.com/findings/agent-testing-non-deterministic-ci/
  Feb 2026 analysis (deepeval, promptfoo, AWS agent-evaluation): judge gates are
  probabilistic; same code passes then fails. Mitigations reduce but never eliminate
  variance. Teams got flaky CI, spurious blocks, plus a false-pass bug in the eval
  framework itself (deepeval `is_successful`). Recommended: deterministic assertions
  first, judge only for free-text quality.

## Q2: LLM-as-judge reliability: bias, calibration, variance (2024-2026)

- **Judging the Judges: Position Bias in LLM-as-a-Judge** (HIGH)
  https://aclanthology.org/2025.ijcnlp-long.18/
  150,000+ judgments, 15 judges: position bias is systematic, judge- and task-specific.
  Load-bearing mitigation is position swapping; most debiasing methods leave residual
  bias.

- **Beyond the Surface: Measuring Self-Preference in LLM Judgments** (HIGH)
  https://aclanthology.org/2025.emnlp-main.86/
  DBG score isolates true self-bias via gold-judge anchoring; naive metrics conflate
  favoritism with genuine quality differences.

- **An Empirical Study of LLM-as-a-Judge: Design Choices and Reliability** (HIGH)
  https://arxiv.org/html/2506.13639v1
  Explicit rubrics + reference answers drive human alignment; greedy decoding gives
  zero variance but LOWER human correlation than multi-sample averaging. CoT adds
  little over detailed rubrics.

- **Necessary but Not Sufficient: Temperature Control and Reproducibility** (HIGH)
  https://arxiv.org/html/2606.26185
  Production safety graders at default temp 1.0: up to ~50% per-item pass/fail
  disagreement across 20 identical runs. temp=0 reduces but does not eliminate flips.
  Recommendation: pin temp/seed, multi-epoch, report grader-disagreement rate.

- **Overconfidence in LLM-as-a-Judge: Diagnosis and Confidence-Driven Solution** (HIGH)
  https://arxiv.org/html/2508.06225v3
  Judges systematically express higher confidence than correctness warrants; dangerous
  for gating pipelines. TH-Score + LLM-as-a-Fuser ensemble for calibration.

## Q3: Ground-truth creation/validation in the major doc benchmarks

- **OmniDocBench (CVPR 2025)** (HIGH)
  https://arxiv.org/html/2412.07626v2
  3 stages: model pre-annotation (LayoutLMv3, PaddleOCR, UniMERNet, GPT-4o), human
  correction (char-level verification), expert inspection (CDM render checks, 3
  researchers). Procedural validation; NO inter-annotator agreement reported.

- **olmOCR-Bench GT methodology (arXiv:2502.18443)** (HIGH)
  https://arxiv.org/abs/2502.18443
  No full-page references; 7,010 deterministic tests. LLM-mined (Gemini/Claude
  drafts), then AT LEAST one manual review round per category; per-test `verified`
  flag in the dataset. No IAA metrics.

- **Marker benchmark dataset** (MED)
  https://github.com/datalab-to/marker#benchmarks
  ~2,138 Common Crawl pages, `gt_blocks` HTML. No documented human review protocol or
  IAA; validation is downstream via heuristic + LLM scorers.

- **docling-eval** (MED)
  https://github.com/docling-project/docling-eval
  Ingests third-party GT (OmniDocBench, DP-Bench, FinTabNet, ...); adds metric
  orchestration, not independent annotation.

- **DP-Bench (upstage)** (MED)
  https://huggingface.co/datasets/upstage/dp-bench
  Human-intended layout annotations; annotation workflow undocumented; QA is
  maintainer post-release fixes.

## Q4: Industry pattern: deterministic checks vs model-based evaluation

- **Deterministic vs LLM-Judge Evals: 2026 Guide** (HIGH)
  https://futureagi.com/blog/deterministic-vs-llm-judge-evals-2026/
  Cascade layering: deterministic gates catch 30-60% of failures at sub-ms cost and
  block immediately; LLM judges reserved for the semantic remainder. Anti-pattern:
  either layer in isolation.

- **Deterministic Guardrails (DistilledPatterns)** (HIGH)
  https://distilledpatterns.org/patterns/deterministic-guardrails/
  Named architectural pattern: "the model proposes, deterministic checks decide."
  Guardrail logic versioned, tested, stable across model/prompt changes.

- **Deterministic Safety Checks in MLflow with Guardrails AI** (HIGH)
  https://mlflow.org/blog/mlflow-guardrails-scorers/
  MLflow 3.10+: deterministic validators as repeatable regression gates; LLM judges
  for subjective quality. Rule-based better when speed, consistency, auditability
  matter.

- **AI Guardrails And Output Validation 2026: Production Patterns** (HIGH)
  https://www.alexcloudstar.com/blog/ai-guardrails-output-validation-2026/
  Cheap deterministic first, expensive probabilistic last; guardrails (blocking)
  vs evaluators (post-hoc). LLM judge on every response is a flagged v1 anti-pattern.

- **Why LLM judges fail in production (FlowVerify)** (HIGH)
  https://www.flowverify.co/blog/llm-judge-production-failures
  Verifier hierarchies: deterministic first pass, escalate to judges only for the
  remainder; human review as final calibration authority.

## Q5: Maintainer rationale for advisory LLM scores

- **olmOCR-Bench README - Benchmark Principles (AllenAI)** (HIGH)
  https://github.com/allenai/olmocr/blob/main/olmocr/bench/README.md
  Explicit rationale: soft metrics penalize correct parses and miss semantically
  critical one-char errors; machine-checkable pass/fail tests are clear and
  reproducible.

- **olmOCR 2: Unit test rewards for document OCR (Ai2 blog)** (HIGH)
  https://allenai.org/blog/olmocr-2
  If correctness is programmatically checkable, the same checks supervise training
  (GRPO rewards) AND score evaluation. Objective/metric alignment as the path to
  reproducible OCR.

- **Marker CI gates heuristic only (verify_scores.py)** (HIGH)
  https://github.com/datalab-to/marker/blob/master/benchmarks/verify_scores.py
  CI gates on heuristic >= 90 only; harness catches LLM scorer exceptions ("Some
  scorers can fail, like the LLM one"). Architecture encodes the rationale.

- **Docling confidence scores - grades decide, numerics advisory (IBM)** (MED)
  https://github.com/docling-project/docling/blob/main/docs/concepts/confidence_scores.md
  Numeric scores are informational and unstable across releases; categorical grades
  drive workflow decisions.

- **docling #1102 - confidence from deterministic pipeline signals** (MED)
  https://github.com/docling-project/docling/issues/1102
  Maintainer design: aggregate confidence from deterministic signals (OCR cell
  confidences, layout scores), explicitly not from an external LLM judge.

---
5 foragers, 25 finding cards, 25 unique URLs. Collected 2026-07-16.
