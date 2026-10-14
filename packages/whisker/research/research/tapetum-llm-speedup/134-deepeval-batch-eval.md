# 134 - deepeval-Batch-Eval

**Verdict:** usable-with-conditions — DeepEval's batch harness (N×M evaluate loop, disk cache resume, cost rollup, AsyncConfig concurrency) is production-grade for LLM-judge fleets, but its parallelism axis is cross-test-case not in-document, and structured per-call-class timing is UI-only not exported.
**Confidence:** high

## Findings

- [CRITICAL] **Evaluation loop is test_cases × metrics with two concurrency tiers.** `evaluate()` dispatches to `a_execute_test_cases()` (async default) or `execute_test_cases()` (sync); async path creates one semaphore-gated task per test case (`asyncio.Semaphore(async_config.max_concurrent)` at `deepeval/evaluate/execute/e2e.py:348-354`), and within each case all metrics run via `asyncio.gather` in `measure_metrics_with_indicator()` (`deepeval/metrics/indicator.py:157-195,226-238`). Evidence: `deepeval/evaluate/evaluate.py:158-224`, `deepeval/evaluate/configs.py:8-11` (defaults `max_concurrent=20`, `throttle_value=0`). Impact: adopting cross-case `max_concurrent` alone does not fix tapetum's in-paper serial chain (~120 s/paper at 6 calls, 00-baseline:36-38); in-paper parallel unit checks is the orthogonal lever, but DeepEval's within-case metric gather validates the pattern. Quality risk: parallel metrics on shared judge context can increase MoE batch variance (05-web RuVerBench caution).

- [CRITICAL] **Partial-run resume via per-(test_case, metric) disk cache, not whole-run tombstone.** `CacheConfig(use_cache=False, write_cache=True)` (`deepeval/evaluate/configs.py:38-41`); cache keyed by test-case fields + hyperparameters + metric config (`deepeval/test_run/cache.py:113-170`, `.deepeval-cache.json` at `cache.py:34-35`). Docs explicitly describe rerunning 1 of 1000 cases after failure 999 (`docs/content/docs/evaluation-flags-and-configs.mdx:161-162`); CLI `-c` flag (`evaluation-flags-and-configs.mdx:155-158`). In-run checkpoint: `TEMP_FILE_PATH` + `_skip_reset` accumulates duration (`deepeval/test_run/test_run.py:60`, `deepeval/evaluate/evaluate.py:263-265`). Impact: fleet's whole-paper fingerprint (00-baseline:57-59) wastes ~5 calls on unchanged pages; per-unit cache could cut cold reruns toward warm-like 64.8 s behavior. Quality risk: stale cache if prompt/schema changes without cache key bump.

- [HIGH] **Run-level cost and duration surfaced at wrap-up; per-metric cost accrued in structured JSON.** Each LLM call returns `(output, cost)`; `metric._accrue_cost()` rolls up (`deepeval/metrics/base_metric.py:90-95`); test-case API aggregates (`deepeval/test_run/api.py:69-76,112-113`); run total printed as `time taken: Xs | token cost: Y USD` (`deepeval/test_run/test_run.py:1118-1124`). `EvaluationCost` carries input/output token counts (`deepeval/models/utils.py:10-40`). Self-hosted judges return `0` cost (`deepeval/models/llms/ollama_model.py:95-101`; LocalModel same pattern). LiteLLM/vLLM path supports `cost_per_input_token` overrides (`deepeval/models/llms/litellm_model.py:46-47,111-112`; CLI `deepeval set-openai --cost-per-input-token`, `cli/main.py:635-651`). Impact: fleet lacks run footer cost/token rollup; even at $0 uptime billing, token counts diagnose decode-bound 20 s/call (00-baseline:24-25). Quality risk: none for display-only instrumentation.

- [HIGH] **Progress/timing instrumentation is Rich nested bars + per-case `run_duration`, not persisted per-call-class.** Three-level progress: run bar (`e2e.py:390-394`), per-case bar (`e2e.py:551-555`), per-metric spinner with elapsed suffix (`indicator.py:147-152`). Per-case wall stored via `api_test_case.update_run_duration()` (`e2e.py:635-640`, `api.py:78-79`). Overall run timed at `evaluate.py:191-227`. Metric timing is progress-UI only (`indicator.py:147-152`), not written to `MetricData` JSON. Impact: closes persona-79 gap only if fleet exports structured `{monolith, metadata, page_escalation, unit_check}` timings to sidecar JSON; UI bars alone insufficient for 3003 s optimization. Quality risk: none.

- [MED] **Large-run manageability: pytest-xdist + batched cloud upload + error isolation.** CLI `deepeval test run -n 4 -c -i` combines parallel workers, cache, ignore-errors (`evaluation-flags-and-configs.mdx:147-178`). Confident upload batches 40 LLM / 20 conversational cases per POST (`deepeval/test_run/test_run.py:880-884`, `CONFIDENT_TEST_CASE_BATCH_SIZE` env at `constants.py:23`). Dual timeout: per-task default 180 s outer budget (`settings.py:919-982`) + gather buffer 10-60 s (`settings.py:984-999`), enforced via `_await_with_outer_deadline` (`e2e.py:350-354`, `_common.py:227-238`). `ErrorConfig.ignore_errors` prevents one bad JSON from aborting 381-paper fleet. Impact: batched upload N/A locally; timeout/error isolation portable to tapetum paper budget (900 s, `cli.py:152`). Quality risk: `ignore_errors=True` can mask partial coverage (conflicts with fail-closed unless paired with explicit error counts).

- [MED] **Local/vLLM/Ollama judge config: OpenAI-compatible LocalModel + AsyncConfig, no vLLM-specific slot tuning.** vLLM: `deepeval set-local-model --model=X --base-url=http://localhost:8000/v1/` or `LocalModel(model=..., base_url=...)` (`docs/content/integrations/models/vllm.mdx:14-44`, `deepeval/models/llms/local_model.py:29-79`). Ollama: `OllamaModel` with `LOCAL_MODEL_BASE_URL` default `http://localhost:11434` (`ollama_model.py:36-41`). LiteLLM routes any provider including vLLM OpenAI shim (`litellm_model.py:27-35`). Concurrency guidance: reduce `max_concurrent` + raise `throttle_value` for rate limits (`evaluation-flags-and-configs.mdx:28-32`, FAQ `deepeval/evaluate(async_config=AsyncConfig(max_concurrent=5))`). No `--max-num-seqs` or server-side slot awareness. Impact: fleet already self-hosts vLLM; portable piece is client-side semaphore tuning (currently 32 papers, 00-baseline:34-35) decoupled from server `max-num-seqs 16`. Quality risk: raising client concurrency without server headroom repeats 381>32 regression (00-baseline:81).

- [LOW] **Dataset-scale entry points mirror `evaluate()` configs.** `EvaluationDataset.evals_iterator()` yields goldens then runs agentic loop with same `AsyncConfig`/`CacheConfig`/`DisplayConfig` (`deepeval/dataset/dataset.py:1513-1577`); saves `TEMP_FILE_PATH` then `wrap_up_test_run()` (`dataset.py:1646-1655`). CSV/JSON/JSONL bulk load (`dataset.py:487+`, `valid_file_types` at `dataset.py:76`). Impact: pattern for corpus ingest + iterator eval matches 381-paper fleet shape. Quality risk: none.

## Table-stakes vs tapetum fleet CLI (prioritized adoption)

| Priority | DeepEval table-stake | Fleet gap (00-baseline / code) | Portable action |
|----------|---------------------|-------------------------------|-----------------|
| P0 | Per-metric/per-phase timing in exportable JSON | Only paper-level progress + `partial_progress` dict; no `{monolith, unit_check}` wall breakdown | Add sidecar timing fields per call class on every `judge_task` completion |
| P0 | Run footer: wall + token cost (or token count at $0) | No cost/token display; uptime-billed pod hides spend | Sum `input_tokens`/`output_tokens` from judge responses; print at fleet end |
| P0 | Sub-granular cache (test_case × metric fingerprint) | Whole-paper fingerprint only (`cli.py:565+`) | Per-unit fingerprint on `(pid, page, check_type, content_hash)` |
| P1 | `max_concurrent` + `throttle_value` knobs | Fixed `_DEFAULT_CONCURRENCY=32`, no throttle | Expose `--max-concurrent` / `--throttle` aligned to server slots |
| P1 | Nested progress (run / case / metric) | Single paper counter (`cli.py:1080-1084`) | Rich or structured progress with phase labels |
| P2 | Dual timeout (per-task + gather) | Paper budget 900 s only | Per-call-class timeout + gather cancel for hung units |
| P2 | `ignore_errors` + error count in summary | Fail-closed (correct for production) | Keep fail-closed; add `--continue-on-error` debug mode only |

## False-pass hypothesis

Enabling DeepEval-style `CacheConfig(use_cache=True)` at whole-paper granularity without per-unit content hashes: a one-line markdown edit on page 3 would still serve cached monolith+unit results from the prior run, missing a new defect on the changed page.

## False-fail hypothesis

Copying DeepEval's within-case `asyncio.gather` for all 5 unit checks without MoE batch-composition controls: prefix-heavy shared `candidate_md` payloads (00-baseline:43-47) sent in parallel could increase judge variance and flip borderline papers to review/fail on rerun.

## What would change my mind

A tapetum fleet run with per-unit fingerprints + exported per-call-class timings that shows which call classes dominate the 3003 s wall and confirms in-paper parallel unit checks does not change merged verdicts on a 50-paper holdout.
