# 42 - DeepEval LLM-Judge Batching & Fail Short-Circuit (portable patterns)

**Verdict:** usable — DeepEval batches judge work as **asyncio concurrency of cases + metrics**, not provider token-batch APIs; **threshold fail does not short-circuit sibling metrics**. True call savings require **explicit gates** (DAG/verdict leaves, empty-intermediate exit, cache hit, timeout cascade, or sequential cheap→expensive order).

**Confidence:** high for orchestration shape (source-read); medium for DAG branch concurrency details (docs + graph API, not every node executor line audited).

**Date:** 2026-07-24. Sources: confident-ai/deepeval `@f030ca14` (`evaluate/execute.py`, `evaluate/configs.py`, `metrics/indicator.py`, `metrics/faithfulness/faithfulness.py`, `metrics/answer_relevancy/answer_relevancy.py`, `metrics/g_eval/g_eval.py`); docs `evaluation-flags-and-configs`, `metrics-dag`, `evaluation-end-to-end-single-turn`; issue `#2128` (gather timeouts).

---

## Scope

Portable patterns only: what a judge fleet can copy. No DeepEval adoption advice, no package-specific API recipes beyond evidence anchors.

---

## How DeepEval “batches” LLM judge calls

DeepEval does **not** coalesce many cases into one provider batch request. “Batch” means **overlapping in-flight judge calls** under a concurrency cap.

| Layer | Mechanism | Default / knob | Evidence |
|-------|-----------|----------------|----------|
| **Cases** | One task per test case; `asyncio.Semaphore(max_concurrent)`; optional stagger `sleep(throttle_value)` before next dispatch; outer `asyncio.wait_for(gather(...), gather_timeout)` | `max_concurrent=20`, `throttle_value=0`, `run_async=True` | `AsyncConfig` in `evaluate/configs.py`; `a_execute_test_cases` in `execute.py` |
| **Metrics per case** | Async path: **all metrics** on a case launched via `asyncio.gather` (parallel). Sync path: **for metric in metrics** sequential `_execute_metric` | Parallel when async | `measure_metrics_with_indicator` in `metrics/indicator.py`; sync loop in `execute.py` |
| **Metric instances** | `copy_metrics(...)` per case before dispatch | Required for safe parallel mutation | `a_execute_test_cases` |
| **Inside multi-step metrics** | Pipeline stages are serial (extract → verdict → reason); **independent extracts** may `gather` (e.g. Faithfulness truths∥claims); claim/statement **verdicts packed into one structured JSON call**, not N per-claim fanouts | Metric-local | `faithfulness.py`, `answer_relevancy.py` |
| **G-Eval-style** | Optional steps generation, then one score+reason judge call (logprobs path when supported) | 1–2 LLM calls | `g_eval/g_eval.py` |
| **Cache** | Per-(case, metric) cache hit skips the LLM measure | `CacheConfig.use_cache` | `indicator.py` / execute cache path |

**Implication:** wall time ≈ `(N_cases × M_metrics × calls_per_metric × L) / effective_concurrency`, with effective concurrency capped by `max_concurrent` (cases) and by how many metrics fire together inside a case. Provider continuous-batching is outside DeepEval; the client just keeps the slot queue full.

---

## Short-circuit: what exists vs what does not

### Does **not** short-circuit on failed metrics (threshold / `success=False`)

- Completing a metric with `score < threshold` sets `success=False` and **still runs every other metric** on that case.
- On the async path, siblings are already in-flight via `gather`, so a fail cannot cancel them cheaply even if you wanted to.
- `ErrorConfig` only covers **exceptions / missing params**, not “metric failed the bar.”

Portable lesson: **parallel-all-metrics forbids fail-fast savings**. If cheap gate → expensive judge is the goal, metrics must be **ordered and sequential**, or encoded as an explicit branch graph (below).

### Short-circuits / skips that **do** exist

| Trigger | Behavior | Portable pattern |
|---------|----------|------------------|
| **Missing params** (`skip_on_missing_params`) | That metric skipped; others continue | Skip inapplicable judges early; do not error the fleet |
| **Exception** (`ignore_errors=True`) | Mark metric errored/`success=False`, continue | Soft-fail individual judges; do not halt sibling work |
| **Exception** (default `ignore_errors=False`) | Raise; can abort the run | Fail-closed orchestration |
| **Case / gather timeout** | Current metric timed out; **later indices** marked `"Skipped due to case timeout."` without running | Deadline cascade: cancel pending, synthesize failure for not-yet-started siblings |
| **Upstream span/trace ERRORED** (agentic) | `_skip_metrics_for_error` → **do not run** metrics on that span/trace | If the unit under test already failed hard, skip all judges for that unit |
| **Cache hit** | Restore score/success/reason; no LLM call | Fingerprint identical (input, output, metric config) |
| **Empty intermediate** | e.g. 0 claims → empty verdicts, score defaults high, **no verdict LLM call** | If extractor yields nothing actionable, skip the expensive judge stage |
| **DAG / verdict leaves** | Judgement node with `score=` terminal; other branch’s `then=` continues. Only the chosen path runs. Docs: “fail immediately if requirement missing; otherwise continue.” Independent root branches may run concurrently when `async_mode=True` | **Cheap gate node → expensive node** is the real fail-fast pattern |

---

## Portable patterns (ranked for a cold judge fleet)

### P1 — Semaphore-capped case concurrency + dispatch throttle

- Cap in-flight **cases** (not unbounded gather).
- Optional stagger between task create to absorb 429s without shrinking the cap to 1.
- Outer gather timeout + cancel/drain pending tasks (`return_exceptions=True` on cleanup).

**When it helps:** many independent papers/cases, I/O-bound judge latency.  
**When it hurts:** cap ≫ server slots → queue thrash / timeout storms (same class as raising client `c` past slot budget).

### P2 — Parallelize only **independent** judge work; serialize **dependent** stages

- Case-level: many cases in flight under a semaphore.
- Metric-internal: `gather` independent extracts; await verdict only after extracts; reason after score.
- Do **not** fan out one LLM call per claim if a single structured “verdicts[]” JSON call suffices.

**When it helps:** Faithfulness-like multi-call metrics; multi-metric suites with no data dependence.  
**Tradeoff:** parallel metrics burn more concurrent slots per case (case_cap × metrics_per_case).

### P3 — No implicit short-circuit on threshold fail; add an explicit gate if you need call cuts

DeepEval’s default multi-metric evaluate **will not** save the expensive judge after a cheap one fails.

Portable designs that actually cut calls:

1. **Sequential cheap→expensive** with an early `return` / skip after gate fail.
2. **Branch graph** (DAG-style): fail leaf assigns score and stops; pass leaf points to next judge.
3. **Preflight deterministic filters** before any LLM (schema/presence checks) — analogous to DeepEval’s missing-params skip, but for your domain.

**False-pass risk:** gate too aggressive → skip quality judges that would have caught defects. Gate must be sound for “failure is final.”

### P4 — Timeout cascade marks remaining work skipped, not hanging

On case deadline: finished metrics keep results; in-flight gets timeout error; **not-yet-started** siblings get synthetic skip/fail without launching LLM calls.

Portable: pair `wait_for` / task cancel with explicit “remaining = skipped due to deadline” bookkeeping so partial cases never look complete.

### P5 — Isolate mutable metric/judge state per concurrent unit

DeepEval copies metric objects per case before parallel dispatch. Portable: never share mutable scorer state across in-flight cases (scores, prompts buffers, cost counters).

### P6 — Cache / fingerprint short-circuit before the judge

Identical (payload, metric config) → reuse score. Portable warm-path tombstones / result cache sit at the same layer as DeepEval’s per-metric cache hit.

### P7 — Empty-intermediate early exit

If the decomposition step produces zero atoms, skip the verdict LLM and define a deterministic score. Portable for claim/statement/unit-check extractors that would otherwise call a judge on an empty list.

---

## Mapping to cold-run-10min levers (evidence only, no new arithmetic)

| DeepEval pattern | Related cold-run idea | Fit |
|------------------|----------------------|-----|
| No threshold short-circuit across parallel metrics | Metadata-fail short-circuit (sequential gate before unit fanout) | DeepEval default **does not** give you this; you must encode the gate |
| DAG fail leaf | Cheap metadata/format fail → skip expensive unit judges | Closest built-in analogue to call-cutting short-circuit |
| Semaphore + throttle | Client `c` vs server slots | Same control surface; defaults (20) are not sacred |
| Packed verdicts JSON | Dense unit-check batching into fewer judge calls | Prefer one structured multi-item judge over N micro-calls |
| Timeout cascade skip | Per-task deadlines without silent hangs | Aligns with gather-timeout hygiene (`#2128`) |
| Cache hit | Error tombstones / warm fingerprint skip | Same shape |

---

## False-pass hypothesis

Treating DeepEval’s parallel multi-metric evaluate as “fail-fast” would **overstate** available call cuts: a failed AnswerRelevancy still pays for Faithfulness/GEval on the same case. Conversely, over-eager DAG fail leaves or empty-claim score=1 can **false-pass** if “no claims extracted” is treated as perfect faithfulness.

---

## Citations (primary)

- `https://github.com/confident-ai/deepeval/blob/f030ca14/deepeval/evaluate/configs.py` — `AsyncConfig`, `ErrorConfig`
- `https://github.com/confident-ai/deepeval/blob/f030ca14/deepeval/evaluate/execute.py` — semaphore dispatch, sync sequential metrics, timeout skip of later metrics, `_skip_metrics_for_error`
- `https://github.com/confident-ai/deepeval/blob/f030ca14/deepeval/metrics/indicator.py` — `asyncio.gather` across metrics; cache hit path
- `https://github.com/confident-ai/deepeval/blob/f030ca14/deepeval/metrics/faithfulness/faithfulness.py` — gather truths∥claims; packed verdicts; empty-claims early return
- `https://deepeval.com/docs/evaluation-flags-and-configs` — async/error config semantics
- `https://deepeval.com/docs/metrics-dag` — verdict `score` vs `then` termination (true short-circuit)
- `https://github.com/confident-ai/deepeval/issues/2128` — gather timeout / cancel / drain pattern
