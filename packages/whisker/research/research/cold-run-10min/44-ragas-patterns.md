# 44 - Ragas evaluation executor parallelism and metric short-circuit

**Verdict:** usable-with-conditions — Ragas shows how to fan out independent metric jobs under a semaphore and how to fail-soft vs fail-fast, but it has **no per-row / gate-metric short-circuit**; its only early-exit is cooperative global cancel or exception propagation after jobs are already submitted. Portable lesson for metadata-fail short-circuit: **gate before submit**, never cancel after.
**Confidence:** high

**Sources (2026-07-24):**
- [vibrantlabsai/ragas `src/ragas/executor.py`](https://github.com/vibrantlabsai/ragas/blob/main/src/ragas/executor.py) (main)
- [vibrantlabsai/ragas `src/ragas/async_utils.py`](https://github.com/vibrantlabsai/ragas/blob/main/src/ragas/async_utils.py)
- [vibrantlabsai/ragas `src/ragas/evaluation.py`](https://github.com/vibrantlabsai/ragas/blob/main/src/ragas/evaluation.py)
- [vibrantlabsai/ragas `src/ragas/run_config.py`](https://github.com/vibrantlabsai/ragas/blob/main/src/ragas/run_config.py)
- [Ragas Executor reference](https://docs.ragas.io/en/stable/references/executor/)
- [Ragas RunConfig howto](https://docs.ragas.io/en/v0.2.15/howtos/customizations/_run_config/)
- [Ragas cancellation howto](https://docs.ragas.io/en/latest/howtos/customizations/cancellation/)
- Local anchors: `cold-run-10min/00-baseline.md`, `10-impl-status-auditor.md`, `tapetum-llm-speedup/145-verifier-metadata-short-circuit.md`, `pdf_judge.py` metadata short-circuit block

## Findings

- [CRITICAL] **Ragas submits a flat Cartesian product of rows × metrics with no dependency graph.** Evidence: `evaluation.py` loops samples, then `executor.submit(metric.single_turn_ascore, ...)` for every metric before any result is read; scores reassemble via `results[len(metrics) * i + j]`. Impact: every metric always burns LLM budget even when an earlier metric already caps the row. Portable anti-pattern for tapetum: do **not** submit unit/page jobs until the metadata gate returns.
  Impact: confirms why metadata short-circuit must be a **scheduler stage**, not an after-the-fact cancel.

- [CRITICAL] **Ragas has no metric short-circuit / cascade.** Evidence: web + source search; only early-stop knobs are (1) `raise_exceptions=True` (propagate exception from a completed job) and (2) `executor.cancel()` (global cooperative cancel). Neither skips "remaining metrics for this sample while continuing other samples." Impact: metadata-fail short-circuit is a design we must own; Ragas is not a template for gate→skip.

- [HIGH] **Parallelism = asyncio tasks + `Semaphore(max_workers)`, default 16.** Evidence: `RunConfig.max_workers: int = 16`; `async_utils.as_completed` wraps each coro in `async with semaphore` when `max_workers != -1`; `-1` means unlimited `create_task`. Impact: same shape as our fleet slot budget (server 16 / client c=32). Short-circuit savings scale as eliminated jobs × latency / effective concurrency — matching the 1047×20/16 wall model in baseline.

- [HIGH] **Default error mode is fail-soft (`np.nan`), not short-circuit.** Evidence: `Executor.wrap_callable_with_index` catches `Exception`, logs, returns `(counter, np.nan)` when `raise_exceptions=False` (evaluate default). Sibling jobs keep running. Impact: soft-fail ≠ skip-dependents. For metadata-fail we need an explicit **skip dependents** path, not "record nan and continue siblings."

- [HIGH] **`raise_exceptions=True` is fail-fast on completed futures, not preemptive skip.** Evidence: `_process_coroutines` / `_process_batched_jobs` raise when `isinstance(result, Exception) and self.raise_exceptions`. Already-running siblings still finish unless cancel is also set. Impact: useless for metadata short-circuit (metadata `fail` is a successful structured verdict, not an exception).

- [HIGH] **Cancellation is cooperative, task-level, and wasteful after submit.** Evidence: `_cancel_event: threading.Event`; batch loop breaks on `is_cancelled()`; `as_completed(..., cancel_check=self.is_cancelled)` cancels **pending** tasks (`cancel_pending=True`) but docs state cancellation does not stop mid-LLM-call. Impact: if we ever parallelize units and then decide to skip, in-flight calls still pay full decode. Gate-before-submit avoids that tax entirely (current v11 PDF/HTML paths).

- [MED] **`batch_size` creates cancel/checkpoint granularity.** Evidence: with `batch_size` set, jobs process in `batched(...)` waves; cancel checked **before each batch**, not between jobs inside a batch. Impact: if we staged "metadata wave → unit wave," wave boundaries are the only safe abort points under a Ragas-like executor.

- [MED] **`run_async_tasks` defers fail-fast until all tasks complete.** Evidence: collects `first_exception`, drains the rest, then raises — opposite of Executor mid-stream raise. Impact: do not copy this for short-circuit; it maximizes wasted work after a gate failure.

- [MED] **Indexed wrap preserves submission order under `as_completed`.** Evidence: `wrap_callable_with_index` returns `(counter, result)`; `aresults` sorts by index. Impact: portable if we fan out independent units after a pass-gate: reassemble by unit_id/index, never by completion order.

- [LOW] **Production cancel patterns (timeout thread, Ctrl+C, web abort) are fleet-wide UX, not quality gates.** Evidence: cancellation howto. Impact: keep for operator timeouts; do not overload as the metadata short-circuit mechanism.

## Portable ideas for metadata-fail short-circuit

Mapped to our lever (~1341 s / 44.6% fusion-dead unit calls; v11 already in `pdf_judge.py` / `adjudicate.py`).

| # | Ragas pattern | Portable design for tapetum |
|---|---------------|-----------------------------|
| 1 | Flat submit-all (anti-pattern here) | **Two-phase schedule:** Phase A = monolith + metadata (+ deterministic screen). Phase B = page escalations + unit checks **only if** `metadata_check.verdict == "pass"` (or audit exempt). Never enqueue B jobs when A caps. |
| 2 | Global `cancel()` after submit | Prefer **do not submit**. Cancel is a backstop for operator timeout only. Per-paper short-circuit must not call fleet cancel. |
| 3 | `raise_exceptions` / `np.nan` | Treat metadata `fail`/`review` as **successful gate outputs**, not exceptions. Soft-fail (nan) does not skip dependents; we need an explicit `metadata_short_circuited` flag + empty unit lists (already logged at `pdf_judge.py:747-758`). |
| 4 | `max_workers` semaphore | Keep fleet concurrency at slot-safe width; short-circuit reduces **N** (calls), not **S** (slots). Do not "compensate" by raising slots to 32 (forbidden). |
| 5 | Cooperative cancel mid-wave | If in-paper unit parallelization ships later: short-circuit decision must complete **before** launching the unit wave; never cancel mid-wave expecting wall savings. |
| 6 | `batch_size` wave boundaries | Model papers as waves: gate wave → dependent wave. Optional: submit only pass-gate papers' unit jobs into the shared fleet semaphore (frees slots for other papers sooner). |
| 7 | Indexed reassembly | If Phase B fans out, tag results with `(pid, unit_id)` / index; fold after gather. Matches Ragas counter-sort. |
| 8 | Partial-results honesty | Ragas admits cancelled runs leave partial state. Our fidelity rule: short-circuit must be a **complete** advisory result with explicit `metadata_short_circuited=True`, not a truncated run mistaken for full coverage. Sidecar / inspect must show the skip. |
| 9 | No audit modes in Ragas | Keep exemptions: `--all-pages`, `--exhaustive-units`, `--inspect` / golden-PR must bypass short-circuit (already coded). Ragas has no analogue. |
| 10 | Fail-soft siblings continue | Cross-paper: one paper's metadata fail must not cancel other papers' in-flight work (Ragas cancel is all-or-nothing; our gather-per-paper already isolates). |

### Design sketch (Ragas-shaped, short-circuit-correct)

```
for each paper (fleet semaphore):
  submit/await Phase A: monolith, metadata [, page screen CPU]
  if metadata.verdict != pass and not audit_exempt:
      mark metadata_short_circuited
      skip Phase B entirely          # Ragas never does this
      fold verdict + persist complete sidecar
  else:
      submit Phase B jobs under same semaphore
      fold + persist
```

Ragas today is only the "else" branch with Phase A metrics mixed into the same flat job list.

### What not to copy

- Submitting all metrics/units up front then hoping cancel saves money.
- Mapping gate failure onto exceptions (`raise_exceptions`) — wrong type, races siblings.
- Deferred `first_exception` drain (`run_async_tasks`) after a known dead gate.
- Treating soft `nan` cells as "skipped dependents."

## False-pass hypothesis

Porting Ragas-style soft-fail only: metadata `fail` recorded, units still run (or units "nan" while inspect omits defect_groups without a `metadata_short_circuited` marker). Operator reads a full-looking sidecar and assumes units corroborated the fail; inspect channel silently thinner. Verdict may still be correct; **completeness** falsely looks complete.

## False-fail hypothesis

Using Ragas `raise_exceptions=True` (or fleet `cancel()`) when one paper's metadata call throws transport error: aborts or starves unrelated papers mid-batch, producing operational fail / partial fleet where our current per-paper error tombstone would isolate the fault. Not a content false-fail; an availability false-fail.

## What would change my mind

Evidence that current Ragas `@experiment` / a non-deprecated evaluator implements a documented per-row metric dependency DAG or "stop remaining metrics when metric X fails" — would upgrade Ragas from anti-pattern contrast to a direct template. As of main `evaluation.py` + docs (2026-07-24), that mechanism is absent.
