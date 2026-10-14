# 15 - Concurrency-Safety-Skeptic

**Verdict:** usable-with-conditions — paper-level fan-out is structurally sound (per-paper state, gather-ordered persistence, exception firewall), but raising N to 8/16/32 shifts failure from "slow" to "queued-timeout errors" and "verdict-distribution drift" before anything in whisker corrupts on-disk artifacts.
**Confidence:** high (client code paths verified line-by-line); medium on exact RunPod proxy knees (server flags and proxy idle caps are UNKNOWN per `00-baseline.md:34-35`).

## Findings

- [CRITICAL] **600 s read timeout fires on requests that sit in the pod queue before streaming starts.** Evidence: `AsyncOpenAI` default `Timeout(read=600)` (runtime probe, matches `model_backends.py:283` fresh-client-per-call); transient retry catches only `APITimeoutError` with 2 s / 4 s backoff and `max_attempts = min(2, request_limit)` (`model_backends.py:300-351`); baseline community V4 deploy uses `--max-num-seqs 8` while client allows `--concurrency 32` (`00-baseline.md:36`, `cli.py:409-416`). Impact: at N=16/32, tail papers can exceed 600 s wall time waiting for a slot plus decode; worker raises, exception firewall logs one ERROR, **no sidecar written** (`cli.py:451-462`), footer `error` count rises — wall time may not improve and the corpus becomes incomplete.

- [HIGH] **Sync blocking I/O in the hot path undermines real parallelism and stresses the shared `SqliteBackend`.** Evidence: `_custom_select` calls `backend.get_paper_md(pid)` and `sc_path.read_text()` without `await` or `to_thread` (`adjudicate.py:174-183`); `get_paper_md` does sync sqlite query + full-file read (`sqlite_backend.py:1137-1153`); class docstring: "not thread-safe; call only from the main event-loop coroutine" (`sqlite_backend.py:558-559`). Impact: while one in-flight paper loads markdown, the event loop cannot advance other sem-held workers through their select step; at N=32, effective overlap concentrates on HTTP wait, not load/persist; sqlite `busy_timeout = 5000` (`sqlite_backend.py:581`) can surface as sporadic `OperationalError` if another tool writes concurrently.

- [HIGH] **Concurrent in-flight streams to one vLLM pod silently shift verdict distributions (semantic degradation, not sidecar corruption).** Evidence: `run_agent` has no global semaphore (`00-baseline.md:47-50`); escalation gate is observable contradictions + ambiguous confidence band (`adjudicate.py:213-236`, `250-257`); vLLM batch invariance docs: `temperature=0` / `seed=0` do not guarantee identical tokens under continuous batching without `VLLM_BATCH_INVARIANT=1` (`05-web.md` Q4, `00-baseline.md:77-78`). Impact: raising N from 3 to 8/16/32 can flip papers across `CONFIDENCE_AMBIGUOUS_LO/HI` and change tier-2 escalation rate (baseline 13/197) without any whisker bug; sidecars remain well-formed but **advisory meaning drifts**.

- [HIGH] **Shared batch logging handler is process-global and contended under concurrent completions.** Evidence: batch mode replaces `root.handlers = [bar_handler]` (`cli.py:387-393`); one `_RetryCountFilter` attached to that handler (`cli.py:391-392`, `76-88`); `_BarAwareHandler.emit` mutates `bar_len` / calls `redraw` without a lock (`cli.py:103-109`); `_draw` closure captures mutable `done` and `current` label (`cli.py:395-403`, `463-465`). Impact: interleaved ERROR lines and progress-bar redraws at N≥8; retry footer count remains approximately correct (asyncio single-threaded `+=`) but **terminal UX degrades**; mitigated for tallies: `counts` and `inspect_pairs` merge post-`gather` in input order (`cli.py:474-483`).

- [MED] **Peak memory scales with N, not 200 — but N=32 with large papers and `--debug` is unbounded per worker.** Evidence: `asyncio.gather` schedules all coroutines but `async with sem` bounds in-flight adjudication (`cli.py:416-472`); each `_PipelineState` holds full `paper_md` up to `MAX_PAPER_MD_CHARS = 500_000` after strip (`adjudicate.py:144`, `constants.py:61`); pre-filter 2.5 MB papers shrink to single-chunk via `strip_binary_payloads` (baseline `00-baseline.md:21-22`, `adjudicate.py:174-178`); `--debug` allocates per-paper `ctx.debug_log` lists appending full raw JSON (`runner.py:130-131`, `model_backends.py:354-359`). Impact: rough peak markdown RAM ≈ N × 0.5 MB (post-filter) → ~16 MB at N=32; with `--debug`, add N × (thinking + JSON) streams; **not all 200 markdowns loaded at once**.

- [MED] **Per-paper `load_services()` + fresh `AsyncOpenAI` per LLM call multiply connection and parse overhead under load.** Evidence: every `adjudicate_paper` calls `load_services()` and builds new `AgentBackend` dict (`adjudicate.py:441-458`); each `VllmThinkingBackend.run` constructs `AsyncOpenAI(...)` (`model_backends.py:283`); httpx pool allows `max_connections=1000` per client (runtime probe) but **no reuse across calls** (`00-baseline.md:52-56`). Impact: at N=32 with ~13% tier-2 escalation, up to 32 concurrent TLS handshakes through RunPod proxy per wave; CPU + FD churn, not incorrect results; amplifies proxy connection-cap risk (below).

- [MED] **RunPod HTTPS proxy is an external queue in front of vLLM; limits are not instrumented in whisker.** Evidence: `base_url = https://sgjy18glyi4blu-8000.proxy.runpod.net/v1` (`00-baseline.md:29-30`); request body cap drove `MAX_PAPER_MD_CHARS` (`constants.py:55-61`); vLLM maintainers warn client flooding causes timeouts (`05-web.md` Q3 / issue #10269). Impact: idle-timeout on long streams, per-IP connection caps, and TLS proxy buffering are UNKNOWN; symptoms match finding 1 (`APITimeoutError`, `APIConnectionError` retried then raised at `model_backends.py:341-351`). Whisker cannot fix proxy; can only cap N and add per-paper wall-clock guards.

- [LOW] **`TestCliConcurrency` does not exercise production N or load-shaped failures.** Evidence: tests cap at 6 papers and `--concurrency 3` (`test_tapetum_llm.py:1329-1336`); cover serial default, sem bound, firewall, clamp (`test_tapetum_llm.py:1322-1349`); no tests for 8/16/32, timeout behavior, debug memory, logging interleave, or post-gather ordering with mixed tier-2. Impact: regressions in timeout/error rates at high N would ship unnoticed.

## False-pass hypothesis

Operator raises `--concurrency` to 16 on `alliance-pod`; all 200 sidecars persist, footer sums look healthy, but concurrent vLLM continuous batching (no `VLLM_BATCH_INVARIANT`) changes token choices on ~5–10 borderline papers: tier-1 confidence exits the ambiguous band, tier-2 never fires (`adjudicate.py:250-252`), and `suggested_verdict` shifts from `review` to `pass` on papers whisker already flagged — **silent advisory false-pass**, no file corruption.

## False-fail hypothesis

Operator runs `--concurrency 32`; pod `max-num-seqs` ≈ 8 queues 24 streams; several papers hit `APITimeoutError` after 600 s pre-stream (`model_backends.py:341-351`), exception firewall catches them (`cli.py:451-458`), **no `.tapetum.json` written**, footer shows elevated `error` count — good papers are not marked `fail`, but the corpus is **spuriously unadjudicated** (false-fail at coverage level, not verdict level).

## What would change my mind

A 200-paper paired run on the same pid list at `--concurrency 3` vs `--concurrency 8` vs `--concurrency 16` with: (1) `error` count = 0 at all N, (2) ≥99% identical `suggested_verdict` per pid, (3) pod-side confirmation of `max-num-seqs` and whether `VLLM_BATCH_INVARIANT=1` is enabled — would flip verdict to **usable** at the tested N ceiling.

## Whisker-local mitigations (ranked)

| Risk | Mitigation (packages/whisker only) |
|------|-------------------------------------|
| Timeout / proxy queue | Cap or warn when `--concurrency > 8`; wrap `adjudicate_paper` in `asyncio.wait_for` with explicit per-paper budget in `cli.py:_adjudicate_one` |
| Sync I/O blocking | Offload `get_paper_md` / sidecar read in `_custom_select` via `asyncio.to_thread` (`adjudicate.py`) |
| Verdict drift | Document that N>1 is throughput-only; recommend A/B before trusting distributions; optional `--concurrency` default 3 until pod invariance proven |
| Logging contention | Per-worker `_RetryCountFilter` merged post-gather; `asyncio.Lock` around `_BarAwareHandler.emit` (`cli.py`) |
| Connection churn | Load `ServiceRegistry` once per batch in `cli._run`, pass into `adjudicate_paper` (extend `service_overrides` path) to skip per-paper `load_services()` |
| Test gap | Extend `TestCliConcurrency` with parametrized N=8 mock-latency test asserting `max_inflight` and post-gather count order |
