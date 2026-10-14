# 05b - Web: LLM-as-judge / eval harness wall-time patterns

**Forage date:** 2026-07-24  
**Scope:** DeepEval, Ragas, promptfoo, LangSmith evals, SLMJury, Arena-Hard-Auto, Cascaded Selective Evaluation (Jung et al.), LLMTrace judge cascade.  
**Out of scope:** document extraction stacks (docling/marker/etc.).  
**Fleet context:** 381 docs × ~6 serial LLM calls/doc on a MoE pod (`alliance-pod`); decode-bound (~5.9 s decode vs ~0.5 s prefill); server slots=16 / client c≤32 hard caps.

---

## Finding cards

### Short-circuit / DAG gates

- **[HIGH] DeepEval `DAGMetric` — fail-fast binary gates before subjective scoring**  
  https://deepeval.com/docs/metrics-dag  
  Rubric as a decision graph: `BinaryJudgementNode` can terminate with a fixed `score` on the fail branch (`add_verdict(verdict=False, score=0)`) and only `then=` into `GEval` / further nodes on pass. Docs explicitly recommend DAG when rubric is “fail immediately if a requirement is missing; otherwise continue.” Independent branches can run concurrently under `async_mode=True`; the active path still short-circuits unused nodes.  
  **Portable:** encode metadata / hard unit gates as early terminal nodes so the remaining ~5 serial MoE calls never fire.

- **[HIGH] Cascaded Selective Evaluation (Jung et al., ICLR 2025 Oral)**  
  https://arxiv.org/abs/2407.18370  
  Cheap judge first; escalate only when confidence is insufficient for a target human-agreement level. Reported cost savings vs GPT-4 alone: up to **78.5%** (stronger cascades) and **87.4%** (weaker cascades), with coverage ~79% at ≥80% human agreement on ChatArena subsets. Abstention tracks subjectivity, not shallow length/overlap features.  
  **Portable:** treat “confident pass/fail” as short-circuit; only ambiguous cases consume MoE budget.

- **[MED] Pollack CascadedJury / TierPolicy framing**  
  https://blog.pollack.ai/here-comes-the-judge/  
  Production framing of Jung-style cascades: deterministic / cheap checks → expensive LLM tier only when basics pass or confidence is low. Cites 78–87% cost save from cascaded evaluation.  
  **Portable:** same shape as metadata-fail short-circuit already ranked #1 in `00-baseline.md`.

### Cascade judges / small-model first

- **[HIGH] SLMJury — quick 10-token verdicts on SLMs (0.6B–14B)**  
  https://arxiv.org/abs/2606.07810 · https://github.com/anishh15/SLMJury  
  Closed-ended judging: Phi-4 14B at **B=10** output tokens hits **89.55%** oracle accuracy / ~100% instruction-following; Qwen3-14B similar. Quick verdicts match or beat 8k-token reasoned judging on math; reasoning wins by up to **23%** on general/open tasks. Multi-agent debate (RCR) **degrades** accuracy vs majority vote — do not buy latency for debate.  
  **Portable:** closed-ended unit checks → tiny max_tokens + optional dense/SLM offload; keep MoE + long reason only for open/ambiguous paths.

- **[HIGH] PoLL — panel of smaller models vs one large judge**  
  https://arxiv.org/abs/2404.18796  
  Diverse small-model panel correlates better with humans than single GPT-4 judge in studied settings, at **>7× lower cost**; panels can run in parallel. Caveat: studied tasks are relatively simple; complex nuance may still prefer a strong single judge.  
  **Portable to fleet:** only if a second dense pod is live; do not multiply serial MoE calls on one pod (would worsen wall under slot cap).

- **[MED] LLMTrace judge cascade ADR**  
  https://docs.llmtrace.io/architecture/JUDGE_CASCADE/ · https://docs.llmtrace.io/guides/llm-judge/  
  Tiered: fast local classifier (~50 ms GPU) → escalate to slow LLM only when confidence ∈ ambiguous band. Structured 6-field verdict; production default async.  
  **Portable:** confidence-band escalate, not “always escalate on fail.”

### Caching

- **[HIGH] Arena-Hard-Auto — answer + judgment skip-if-present**  
  https://github.com/lmarena/arena-hard-auto  
  Generation cache skips regenerating answers for existing model–prompt pairs; judgment cache skips re-judging when both sides already judged (or skips if a side is missing). Style-control is post-hoc (Bradley-Terry regression), not extra LLM calls.  
  **Portable:** fingerprint (prompt + model + schema + payload hash) → skip or tombstone; warm path already ~65 s when most docs skip.

- **[HIGH] Ragas exact-match disk cache**  
  https://docs.ragas.io/en/stable/howtos/customizations/_caching/  
  `DiskCacheBackend` on LLM/embedding factories; cache key = exact prompt + params + response schema. Docs claim ~**60×** wall and ~100% cost save on full cache hits (100-sample toy: ~2 min → ~2 s). Anti-patterns: timestamps in prompts, high temperature, streaming.  
  **Portable:** content-addressed skip for identical unit-check payloads across retries / re-runs; invalidate on prompt or model change.

- **[HIGH] promptfoo disk cache (on by default)**  
  https://www.promptfoo.dev/docs/configuration/caching/  
  Composite keys (provider + prompt digest + config + vars); errors/429 not cached; TTL default 14 days; `--no-cache` for fresh CI.  
  **Portable:** same exact-match discipline; never cache rate-limit / 5xx.

- **[MED] LangSmith `LANGSMITH_TEST_CACHE`**  
  https://docs.langchain.com/langsmith/experiment-configuration  
  Disk folder of identical API call results for experiment re-runs. Complements `max_concurrency` / `aevaluate`.  
  **Portable:** experiment/dev loop only; cold fleet still needs path short-circuit, not just cache.

### Concurrency patterns

- **[HIGH] Ragas `Executor` + `RunConfig.max_workers` semaphore**  
  https://deepwiki.com/vibrantlabsai/ragas/2.2-executor-and-parallelization · https://docs.ragas.io/en/v0.3.7/howtos/customizations/_run_config/  
  One async job per `(sample, metric)`; `asyncio.Semaphore(max_workers)` caps in-flight LLM calls (`-1` = unlimited). Tune to provider/slot budget, not “as high as possible.”  
  **Portable:** fleet-level semaphore already exists (c≤32 / slots=16). Do **not** raise server slots to 32 (known +57% wall regression). Prefer across-doc fan-out at current c, not within-doc parallel MoE calls that fight APC/prefix reuse.

- **[HIGH] promptfoo AIMD adaptive concurrency**  
  https://www.promptfoo.dev/docs/configuration/rate-limits/  
  Set `maxConcurrency` high; on 429 cut concurrency **50%**; on sustained success +1; proactively cut when remaining quota <10%. Per-provider isolation; retries with `retry-after`. Generation + `llm-rubric` share the pool. Separate `PROMPTFOO_ASSERTIONS_MAX_CONCURRENCY` (default 3) for assertions.  
  **Portable:** AIMD under the **existing** c=32 ceiling when MoE returns 429/524; do not treat AIMD as license to exceed slot budget.

- **[MED] LangSmith `aevaluate` + `max_concurrency`**  
  https://docs.langchain.com/langsmith/evaluate-llm-application · https://docs.langchain.com/langsmith/experiment-configuration  
  Prefer async runner for large jobs; semaphore = concurrent **examples** (each example runs target + all evaluators). Pair with client-side rate limiters / retries.  
  **Portable:** example-level concurrency = paper-level concurrency in the fleet; keep per-paper call graph serial/gated.

- **[MED] DeepEval async metrics + `max_workers`**  
  https://deepeval.com/docs/metrics-dag (async_mode) · third-party scale notes on concurrent test runs  
  Metrics are I/O-bound; gather concurrent metric calls; cache_enabled skips identical `(query, expected, actual)` tuples. Caveat from scale writeups: cache is exact-match and can go stale across prompt/model changes; worker count must stay under provider quota.  
  **Portable:** async **across** independent papers/metrics; DAG still short-circuits **within** a paper.

### Structured output size reduction

- **[HIGH] SLMJury budget split: B=10 vs B=8192**  
  https://arxiv.org/html/2606.07810  
  Decode budget is the quality/latency knob: closed-ended → single-word / boxed verdict under τ=0; open-ended / thinking models need large B and cannot usefully run at B=10.  
  **Portable:** for unit checks, pin tiny `max_tokens` and verdict-first JSON; only escalate to long-reason schema on ambiguous/fail paths. Aligns with decode-bound accounting (decode ≫ prefill).

- **[HIGH] DeepEval `include_reason=False` / binary judgement nodes**  
  https://deepeval.com/docs/metrics-dag · https://deepeval.com/blog/llm-as-a-judge  
  DAG binary nodes ask yes/no; terminal scores need no prose. `include_reason` defaults True on `DAGMetric` — turn off on pass-dominated paths. Built-in QAG-style metrics already decompose into closed-ended checks rather than one holistic essay.  
  **Portable:** schema = `{verdict, ...}` first; reasons optional or fail-only.

- **[MED] Binary-check decomposition (BinEval / practice writeups)**  
  https://arxiv.org/html/2606.27226v1 · https://dev.to/shimo4228/llm-as-judge-shouldnt-aggregate-scores-binary-checks-as-evidence-one-holistic-verdict-822  
  Atomic yes/no questions + one named holistic verdict; avoid long score essays and score averaging as the quality metric. Shorter, more parse-stable outputs.  
  **Portable:** unit checks as binary evidence; one fleet verdict enum — not multi-paragraph rubrics per call.

- **[LOW] LLMTrace 60-token structured JSON judge outputs** (cited in prior tapetum 05-web)  
  Caps reasoned fields; pairs with cascade so most traffic never hits the slow tier.

---

## Cross-harness pattern summary

| Lever | Who ships it | Wall-time mechanism | Quality guard |
|---|---|---|---|
| Path short-circuit | DeepEval DAG, CascadedJury | Skip remaining judge nodes/calls | Fail-closed terminal scores |
| Cascade / SLM-first | Jung 2024, SLMJury, LLMTrace, PoLL | Cheap/fast tier covers majority | Escalate on low confidence / open tasks |
| Exact-match cache | Ragas, promptfoo, LangSmith, Arena-Hard | 0 LLM tokens on hit | Invalidate on prompt/model/schema change |
| Bounded concurrency | Ragas semaphore, LangSmith aevaluate, promptfoo AIMD | Saturate slots without 429 storms | Cap to provider/slot budget |
| Tiny structured decode | SLMJury B=10, DeepEval binary + no reason | Cut decode tokens (dominant cost) | Long reason only when needed |

---

## Top 3 portable ideas (381 docs × ~6 serial calls, MoE pod)

1. **DAG / gate short-circuit inside the per-doc call chain**  
   Make early hard gates (metadata, deterministic unit fails) **terminal**: do not schedule the remaining serial MoE calls. Same shape as DeepEval `BinaryJudgementNode` fail→score and Jung “trust or escalate.” Baseline already prices metadata-fail short-circuit ~1341 s — this forage confirms it is industry-standard, not a one-off hack.

2. **Verdict-first, tiny decode on closed-ended checks**  
   SLMJury’s B=10 closed-ended regime + DeepEval binary/`include_reason=False`: pin short structured schemas and `max_tokens` for the ~70% zero-defect unit-check mass. Keep long reasoned output only for open/ambiguous/fail paths. Directly attacks decode-bound latency (~5.9 s mean decode).

3. **Confidence cascade off the MoE hot path (not more MoE concurrency)**  
   Jung/LLMTrace pattern: fast/deterministic or dense-SLM judge first; escalate to MoE only in the ambiguous band. Do **not** “speed up” by raising slots to 32 or blasting within-doc parallel MoE calls (forbidden / APC-hostile). Optional PoLL/dense offload only if a second pod is alive; on one MoE pod, cascade means **fewer** expensive calls, not more parallel ones.

**False-pass watch:** short-circuit or B=10 on open-ended / subjective criteria (SLMJury: reasoning wins by up to 23% there).  
**False-fail watch:** cascade that escalates only on “fail” instead of “low confidence” — confident fails should stay terminal; ambiguous passes need the strong judge.
