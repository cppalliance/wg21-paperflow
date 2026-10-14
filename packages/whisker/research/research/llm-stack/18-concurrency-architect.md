# 18 - Concurrency-Architect

**Verdict:** usable-with-conditions (+ paper-level `--concurrency N` in `cli.py` is the sanctioned D11 hook and preserves per-paper internal seriality, but N>1 on the shared `alliance-pod` vLLM pod trades wall-clock for cross-request batch variance unless the pod runs batch-invariant kernels)
**Confidence:** high

## Findings

- [CRITICAL] Concurrent in-flight HTTP requests to one vLLM pod perturb token choices even at `temperature=0` / `seed=0` because continuous batching changes reduction order; `VLLM_BATCH_INVARIANT=1` restores invariance at ~50% throughput cost. Evidence: `05-web.md` Q4 Batch Invariance card, https://docs.vllm.ai/en/stable/features/batch_invariance/; `MODELS.md:77` (hosted inference flips tokens without server-side batch-invariant kernels). Impact: `--concurrency N>1` can flip confidence across the ambiguous band (`adjudicate.py:206-208`) and shift suggested-verdict distribution while sidecar field order stays stable; this is a **semantic-stability** regression, not a framework bug.

- [HIGH] D11 forbids flipping global framework semaphores; the sanctioned hook is **CLI paper-level fan-out**, not `_task_semaphore` / `_PARALLEL_CONCURRENCY`. Evidence: `CLAUDE.md:88` (per-package mechanism, dissect stays serial); `tasks.py:30-38` (`_TASK_CONCURRENCY = 1`, module-level `_task_semaphore`); `00-baseline.md:70-71` (hook = `cli.py` batch loop, not `run_agent`). Impact: raising `_task_semaphore` or a nonexistent `_parallel_semaphore` would let dissect/agora paths inherit concurrent LLM calls (`dispatch()` parallel branch is already a serial `for msg in user_msgs` at `runner.py:369-373`); a CLI-local `asyncio.Semaphore(N)` satisfies D11.

- [HIGH] The serial batch loop owns shared mutable state that becomes a race under fan-out: `counts` dict (`cli.py:273`), `_RetryCountFilter.count` (`cli.py:258-259`, `:66`), `_BarAwareHandler` redraw closure (`cli.py:262-270`, `:76-94`), and `inspect_pairs` append (`cli.py:276`, `:300-302`). Evidence: `cli.py:277-317`. Impact: naïve `asyncio.gather` without per-worker isolation corrupts footer tallies, retry counts, progress-bar position, and inspect ordering; counts and inspect data must be merged **after** gather in input-index order, with an `asyncio.Lock` only for progress-bar redraw and retry-filter increments.

- [HIGH] `adjudicate_paper` is re-entrant at the asyncio level but wasteful and internally serial. Evidence: each call loads `PipelinePrompt.load` + `load_services()` + fresh `StepContext(default_concurrency=1)` (`adjudicate.py:378-410`); oversized-paper chunk triage is an explicit serial `for` loop (`adjudicate.py:187-191`, comment at `:175-176`). Impact: concurrent papers do not share `StepContext` or `debug_log`; per-pid debug/trace paths are disjoint (`adjudicate.py:414-416`, `runner.py:320-324`); internal chunk loops must **not** be parallelized in v1 without a separate variance budget.

- [MED] Sidecar persistence is order-independent and safe under concurrent completion. Evidence: `_persist_result` writes `{pid}.tapetum.json` under pid-scoped paths (`cli.py:191-201`); inspect report re-sorts by pid before write (`cli.py:221`). Impact: gather completion order does not affect on-disk artifacts; only aggregate footer stats and terminal log interleaving need explicit ordering discipline.

- [MED] Client concurrency should cap at the pod's `--max-num-seqs`, not unbounded gather. Evidence: vLLM maintainers in Issue #10269 (`05-web.md` Q3): client `Semaphore(N)` limits in-flight HTTP connections; flooding causes timeouts. Impact: default `N=1`, document `N ≤ pod max-num-seqs`; expect diminishing returns once the server scheduler is saturated.

- [LOW] Authority doc declares `concurrency: 1` but CLI has no flag yet. Evidence: `tapetum_llm.md:23`; `_parse_args` ends at `--service` with no concurrency knob (`cli.py:97-142`). Impact: wiring `--concurrency` defaulting to `1` preserves today's behavior and matches the authority doc without touching framework globals.

## False-pass hypothesis

Operator runs `--concurrency 8` on 200 papers; all sidecars write, footer counts sum correctly, but three papers flip from `review` to `pass` because concurrent vLLM batching changed deepseek confidence outside the ambiguous band — ordering invariants hold, verdict distribution shifts (`00-baseline.md:46`, 106/197 review rate).

## False-fail hypothesis

Operator rejects paper-level concurrency because D11 mentions `_parallel_semaphore` / `_task_semaphore` (`CLAUDE.md:88`, `MODELS.md:59-60`), missing that the sanctioned hook is CLI paper fan-out (`00-baseline.md:71`); serial 200-paper runs continue at 1.5–2 h (`00-baseline.md:49`) while the stack is labeled "too slow to adopt."

## What would change my mind

A 200-paper A/B on `alliance-pod` with `--concurrency 1` vs `--concurrency 4`, same pid list, showing ≥99% identical `suggested_verdict` and confidence within ±0.01 on every sidecar — or pod logs proving `VLLM_BATCH_INVARIANT=1` is enabled on the deployment.

## Proposed design

### Hook and flag

| Item | Choice |
|---|---|
| Flag | `--concurrency N` on `whisker-tapetum-llm` (`cli.py` `_parse_args`) |
| Default | `N=1` (identical to today's serial loop) |
| Scope | Paper-level only; **never** touch `_task_semaphore` (`tasks.py:38`) or `_TASK_CONCURRENCY` (`tasks.py:30`) |
| Internal pipeline | Leave `adjudicate_paper` chunk triage serial (`adjudicate.py:187-191`); do not raise `StepContext.default_concurrency` above 1 in v1 |

### Control flow (replace `cli.py:277-317`)

```python
async def _adjudicate_one(
    index: int,
    pid: str,
    *,
    backend,
    args,
    overrides,
    sem: asyncio.Semaphore,
    progress_lock: asyncio.Lock,
    progress: dict,  # {"done": int, "current": str}
    retry_filter: _RetryCountFilter | None,
    batch: bool,
    draw_fn,
) -> tuple[int, str, TapetumResult | None, Exception | None]:
    async with sem:
        if batch:
            async with progress_lock:
                draw_fn(progress["done"], pid)
        try:
            result = await adjudicate_paper(
                pid, backend,
                debug=args.debug, trace=args.trace,
                service_overrides=overrides,
            )
            out_path = _persist_result(result, backend)
            return (index, pid, result, None)
        except Exception as exc:
            return (index, pid, None, exc)
        finally:
            if batch:
                async with progress_lock:
                    progress["done"] += 1
                    draw_fn(progress["done"], pid)


async def _run_batch(..., concurrency: int):
    sem = asyncio.Semaphore(concurrency)
    progress_lock = asyncio.Lock()
    progress = {"done": 0, "current": ""}
    coros = [
        _adjudicate_one(i, pid, ..., sem=sem, progress_lock=progress_lock, ...)
        for i, pid in enumerate(pids)
    ]
    raw = await asyncio.gather(*coros, return_exceptions=False)
    ordered = sorted(raw, key=lambda t: t[0])  # input-order merge
    # fold ordered into counts, inspect_pairs, per_paper_log
```

Pattern matches `StepContext.gather_concurrent` (`runner.py:133-162`) and canonical asyncio guidance (`05-web.md` Q3: semaphore + gather, input-order results).

### Progress and logging

- **Progress bar:** one `asyncio.Lock` around `_draw` / `_BarAwareHandler.redraw` (`cli.py:262-270`); `progress["done"]` incremented in worker `finally` so the bar never jumps backward.
- **Retry filter:** keep `_RetryCountFilter` on the shared handler; its `filter()` runs on the event loop thread — safe without a lock (logging is synchronous per record). Alternatively aggregate per-worker retry counts post-gather if contention appears.
- **Per-paper logs:** emit completion lines **after** gather in pid-list order (deterministic terminal transcript), not at completion time (avoids interleaved stderr under concurrency).
- **Batch firewall:** preserve `return_exceptions`-equivalent behavior by catching inside `_adjudicate_one` and returning `(index, pid, None, exc)`; one paper's failure must not cancel siblings (`cli.py:304-307`).

### Persistence and inspect

- **Sidecars:** write inside the worker immediately after `adjudicate_paper` succeeds (`cli.py:289-290` unchanged); paths are pid-scoped, no ordering requirement.
- **Inspect report:** collect `(whisker_dict, tapetum_dict|None)` tuples with index; after gather, build `inspect_pairs` in pid-list order (or sort by pid as today at `cli.py:221`).
- **Footer counts:** derive from ordered results, not shared `counts` mutation during flight.

### Determinism tradeoff statement

| Mode | Same-verdict-quality (semantic stability) | Bit-identical sidecars |
|---|---|---|
| `N=1`, serial | Baseline; only server load + corruption-luck variance remain (`03-determinism-auditor.md` finding 1–2) | No (guard tag, retry path, batch interference) |
| `N>1`, shared pod | **May degrade:** MoE routing + continuous batching can flip confidence/verdict (`MODELS.md:69`, `05-web.md` Batch Invariance) | No |
| `N>1`, pod with `VLLM_BATCH_INVARIANT=1` | Closer to serial; ~50% server throughput cost | Still no (guard tag, retry path) |

**Product stance:** tapetum is advisory (`cli.py:11-14`); document in `--help` and `tapetum_llm.md` that `N>1` optimizes wall-clock, not rerun identity. Require explicit `--concurrency` >1; never change the default from 1. Optional future: `--concurrency` cap auto-read from `SERVICES.toml` `max-num-seqs` if we add that field.

### D11 compliance checklist

1. Do not modify `_task_semaphore` or `_TASK_CONCURRENCY` (`tasks.py:30-38`).
2. Do not modify `dispatch()` parallel branch (`runner.py:358-375`).
3. Do not raise `StepContext.default_concurrent` inside `adjudicate_paper` (`adjudicate.py:409`).
4. Concurrency primitive is **CLI-local** `asyncio.Semaphore(N)` only.
5. Dissect/agora paths untouched; they continue one in-flight LLM request via existing framework serial defaults.

### v1 non-goals

- Chunk-level fan-out inside `_custom_triage` (would need per-chunk variance budget and interacts with partial-read fidelity at `chunking.py`).
- Caching `load_services()` across papers (safe optimization, separate PR; `adjudicate.py:379`).
- Auto-tuning N from server load.
