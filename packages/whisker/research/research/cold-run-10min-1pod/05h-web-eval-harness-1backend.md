# 05h - Web/GitHub: DeepEval, Ragas, promptfoo, LangSmith (1 backend)

**Verdict:** usable-with-conditions — these harnesses optimize **call count and recompute**, not single-endpoint throughput. Concurrency knobs (`num_workers`, `maxConcurrency`, `max_concurrency`) are the wrong lever under the 1-pod cap (S_eff=16). Steal the **N-cutting** patterns below.
**Confidence:** high (docs + source; cold-fleet transfer is medium)

Scope: how each stack behaves when **only one LLM backend** is available (no load split across twin pods / multi-provider fanout). Focus: short-circuit, metric DAGs / multi-step pipelines, caching. Dual-pod / raise-concurrency advice is out of scope.

## Findings

- [CRITICAL] **Exact-match LLM/embedding caches are the shared primitive.** All four store prior judge I/O and skip the network/GPU on hit. DeepEval caches **per (test case × metric config)** scores; Ragas/promptfoo/LangSmith cache **at the HTTP/LLM-call layer**. Evidence: DeepEval `test_run/cache.py` + `evaluate/execute.py` metric loop; Ragas `DiskCacheBackend` + `cacher()` on `generate`/`agenerate` ([docs](https://docs.ragas.io/en/stable/howtos/customizations/_caching/)); promptfoo provider+digest keys ([docs](https://www.promptfoo.dev/docs/configuration/caching/)); LangSmith `LANGSMITH_TEST_CACHE` VCR disk cache ([docs](https://docs.langchain.com/langsmith/experiment-configuration)). Impact: **warm / CI / metric-tweak reruns → N≈0**; cold unique papers → mostly miss unless **intra-run** or **shared subprompt** hits.

- [HIGH] **Metric-level cache (DeepEval) beats call-level cache when the metric is a black box.** DeepEval looks up `CachedMetricData` before `_execute_metric`; hit skips the entire `measure()` (often multi-call). Cache key includes case fields + hyperparameters + `MetricConfiguration` (`threshold`, `evaluation_model`, `strict_mode`, `criteria`, `evaluation_steps`, …). Changing threshold alone invalidates. Evidence: `execute.py` metric loop; `MetricConfiguration` in `cache.py`. Impact: rerunning the same fleet with the same judge config → full metric skip; **threshold/model churn burns the cache**.

- [HIGH] **Call-level cache enables cross-metric DAG reuse (Ragas).** Faithfulness is a fixed 2-LLM-step DAG: (1) statement decomposition → (2) batched NLI over all statements in one prompt, then local ratio. AnswerCorrectness is a 3-step DAG: statements(response) + statements(reference) → TP/FP/FN classify → optional embedding similarity. Exact-match caching on the shared LLM means **identical decomposition prompts across metrics/samples hit without a framework DAG scheduler**. Evidence: `metrics/collections/faithfulness/metric.py`, `answer_correctness/metric.py`; Ragas claims ~50–60% cost save / 60× on cached re-eval. Impact for 1-pod: design **shared intermediate prompts** (one claim extract reused by faithfulness + correctness) and cache them; do not re-extract per metric.

- [HIGH] **Short-circuit / skip is first-class for call elimination.** DeepEval `skip_on_missing_params` / CLI `-s`: missing `retrieval_context` etc. → `continue` without LLM (`MissingTestCaseParamsError`). Promptfoo `PROMPTFOO_SHORT_CIRCUIT_TEST_FAILURES`: throw on first failed assertion (stops remaining graded work). Promptfoo docs also push **deterministic preflight** (`is-json`, `contains`, `regex`, `javascript`) and, if needed, a **separate cheap eval** before `llm-rubric` so invalid outputs never pay for a judge. Evidence: deepeval ErrorConfig docs; `assertionsResult.ts`; [llm-as-a-judge guide](https://www.promptfoo.dev/docs/guides/llm-as-a-judge/). Impact: maps cleanly to tapetum **metadata / fusion-dead short-circuit** and to **cheap gate → expensive unit check**.

- [MED] **In-flight coalescing (promptfoo) cuts duplicate concurrent identical calls without raising concurrency.** `inflightFetchResponses` Map: same cache key shares one Promise; losers await the winner. Evidence: `promptfoo/src/cache.ts`. Impact: when two metrics/steps would fire the same prompt at once on one pod, you pay **1** call, not 2. Useful if a DAG fanout is accidental.

- [MED] **Self-consistency and repetitions are N-multipliers; turn them down on one backend.** Ragas `AspectCritic.strictness` runs majority vote over `strictness` LLM calls (docs show 3 for harmfulness). LangSmith `num_repetitions` re-runs target **and** all evaluators. Impact: set `strictness=1`, `num_repetitions=1` for cold wall; reserve multi-sample for offline quality studies.

- [MED] **Replace LLM DAG nodes with local / non-LLM scorers.** Ragas `FaithfulnesswithHHEM`: keep LLM statement extract, swap NLI for Vectara HHEM local classifier (batched). Promptfoo: prefer deterministic + embedding `similar` / classifier over `llm-rubric` / `g-eval` / multi-judge. AnswerCorrectness `weights[1]=0` skips the embedding arm. Impact: cuts judge calls per paper without needing a second V4-Pro.

- [LOW] **Concurrency is the trap.** DeepEval `num_workers` / async `max_concurrent`; promptfoo AIMD `maxConcurrency`; LangSmith `max_concurrency` / `aevaluate` semaphore. Under one pod these only increase queueing / 429 / TTFT pressure (promptfoo then **cuts** concurrency via AIMD). Evidence: rate-limit docs. Impact: for this corpus, treat concurrency as **already capped**; harvest only N-cuts.

## Per-harness cheat sheet (1 backend)

| Harness | Cache grain | Short-circuit / skip | Metric DAG / multi-step | Call-cut knobs |
|---------|-------------|----------------------|-------------------------|----------------|
| **DeepEval** | Metric score + config hash; disk/Redis | `skip_on_missing_params`; cache hit skips `measure` | GEval/ArenaGEval: steps then score/compare (multi-call per metric) | Stable thresholds/models; write_cache; skip missing params; fewer metrics |
| **Ragas** | Exact prompt+params on LLM/embed | Empty statements → NaN (skips NLI) | Faithfulness 2-step; AnswerCorrectness 3-step; batched NLI | `DiskCacheBackend`; `strictness=1`; HHEM; drop unused metrics; weight=0 similarity |
| **promptfoo** | Provider+request digest; TTL 14d; inflight coalesce | `PROMPTFOO_SHORT_CIRCUIT_TEST_FAILURES`; deterministic-first / preflight eval | Assertions often parallel (full visibility) unless short-circuit env | Cache on; fewer `llm-rubric`; no multi-judge; namespace cache; `--no-cache` only when needed |
| **LangSmith** | VCR disk via `LANGSMITH_TEST_CACHE` (Python/`langsmith[vcr]`) | None built-in for evaluator DAG | Target once, then N evaluators per example | `num_repetitions=1`; `max_concurrency=0` if serial; commit cache for CI warm only |

## False-pass hypothesis

Caching or short-circuit could hide quality regressions: DeepEval threshold-only key mismatches (third-party writeups warn model swap without cache versioning); LangSmith/promptfoo CI caches serving stale judge answers after prompt/model change; skip-on-missing silently drops metrics that should have failed closed.

## False-fail hypothesis

Treating harness "optimize throughput" docs as gospel → crank workers on one pod → 429/TTFT → retries inflate **effective N** and wall; short-circuit on first assertion fail hides remaining defects and looks like "faster green" in CI while under-measuring.

## What would change my mind

- Evidence that DeepEval (or Ragas) has a **cross-metric intermediate store** (shared claim list) beyond accidental exact-match cache hits.
- Measured cold-fleet hit rates for call-level cache on **unique** paper markdown (expect near-zero cross-paper; non-zero within-paper shared substeps).
- A LangSmith evaluator cascade API that skips remaining evaluators on hard fail (not found in current experiment-configuration docs).

## Top ideas that cut **calls**, not concurrency

Ranked for single-pod cold `whisker-tapetum-llm` transfer (S_eff fixed at 16):

1. **Cheap gate → expensive judge (promptfoo / DeepEval skip).** Deterministic or metadata preflight; never spend a fusion/unit LLM call when inputs or structure already fail. (Aligns with existing v11 short-circuit.)
2. **Shared intermediate DAG + call-level cache (Ragas pattern).** One claim/statement extraction reused by multiple checks; exact-match cache so identical prompts never re-hit the pod.
3. **Metric-result cache with frozen config (DeepEval).** Persist per-(case, metric, model, criteria) scores across reruns; version cache when judge/prompt changes.
4. **Collapse multi-call judge nodes.** Batched NLI (all statements in one prompt); `strictness=1`; no `num_repetitions`; avoid multi-judge / Arena step generation when a single rubric call suffices.
5. **Swap LLM nodes for local scorers.** HHEM-style NLI, embeddings/`similar`, regex/JSON gates; drop optional similarity arms (`weights`).
6. **In-flight request coalescing (promptfoo).** Dedup identical in-flight prompts so accidental fanout costs 1 call.
7. **Fewer LLM metrics per case.** Evaluate only metrics that can fail the paper; escalate secondary rubrics only on borderline primary scores (harness-agnostic; promptfoo asserts this culturally via "model-graded sparingly").

## Arithmetic note (corpus obligation)

These patterns reduce **N_rem** (and sometimes **L_eff** via shorter schemas), not **S_eff**:

`wall ≈ (N_rem × L_eff) / 16 + T + C − L_abs`

Caching that only hits on **warm** re-eval does not move cold wall unless intermediate reuse or short-circuit fires **inside** the cold pass.

## Sources (2026-07-24)

- DeepEval: https://github.com/confident-ai/deepeval (`evaluate/execute.py`, `test_run/cache.py`); https://deepeval.com/docs/evaluation-flags-and-configs
- Ragas: https://docs.ragas.io/en/stable/howtos/customizations/_caching/; faithfulness / answer_correctness metric sources on `explodinggradients/ragas`
- promptfoo: https://www.promptfoo.dev/docs/configuration/caching/; https://www.promptfoo.dev/docs/guides/llm-as-a-judge/; `src/cache.ts`, `src/assertions/assertionsResult.ts`
- LangSmith: https://docs.langchain.com/langsmith/experiment-configuration; `aevaluate` / `LANGSMITH_TEST_CACHE` reference docs
