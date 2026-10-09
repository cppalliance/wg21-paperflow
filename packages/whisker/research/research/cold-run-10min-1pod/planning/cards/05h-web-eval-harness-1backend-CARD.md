# Card 05h — Eval harnesses on one backend (DeepEval / Ragas / promptfoo / LangSmith)

**Source report:** `05h-web-eval-harness-1backend.md`  
**Verdict in source:** usable-with-conditions

## Bottom line

These harnesses optimize **call count and recompute**, not single-endpoint throughput. Under S_eff=16, concurrency knobs (`num_workers`, `maxConcurrency`, …) are the wrong lever. Steal **N-cutting** patterns: cheap gate → expensive judge, shared intermediates + cache, metric-result cache, collapse multi-call nodes, local scorers, inflight coalesce.

## Numbers

- Ragas claims: ~50–60% cost save / **60×** on cached re-eval (warm).
- Faithfulness = 2-LLM-step DAG; AnswerCorrectness = 3-step; batched NLI in one prompt.
- Ragas `AspectCritic.strictness` / LangSmith `num_repetitions`: each >1 multiplies N — set to **1** for cold wall.
- promptfoo cache TTL 14d; inflight Map shares one Promise per identical key.
- Wall formula unchanged: cut N_rem / sometimes L_eff; caching that only hits warm re-eval does **not** move cold wall unless reuse/short-circuit fires inside the cold pass.

## Architecture implication

Map to tapetum: metadata/fusion-dead short-circuit; one claim extract reused by multiple checks; freeze judge config so metric caches survive; fewer LLM metrics per paper; escalate secondary rubrics only on borderline. Treat client concurrency as already capped.

## Reject-or-A-B

**Adopt N-cut patterns.** **Reject:** cranking workers on one pod as “throughput optimize”; banking warm CI cache for cold fleet wall. Watch false-pass: stale caches after prompt/model change; skip-on-missing dropping fail-closed metrics.

## Links

- https://github.com/confident-ai/deepeval
- https://docs.ragas.io/en/stable/howtos/customizations/_caching/
- https://www.promptfoo.dev/docs/configuration/caching/
- https://docs.langchain.com/langsmith/experiment-configuration
