# 11 - Throughput-Auditor

**Verdict:** usable-with-conditions — the 36-min wall time is almost entirely LLM/pod decode time behind a client semaphore set to 3; raising whisker-side concurrency and cutting per-tier output budgets are the only in-package levers with multi-minute upside, but pod `max-num-seqs` (unknown, likely ~8) caps linear speedup.
**Confidence:** high

## Findings

- [CRITICAL] **Primary throttle is `cli.py` paper-level semaphore at N=3, not pipeline global locks.** Evidence: `cli.py:409-416` (`asyncio.Semaphore(concurrency)` wraps each `adjudicate_paper`); `runner.py:266-272` (`run_agent` calls `agent.run` directly, no semaphore); `tasks.py:38,57` (`_task_semaphore` only gates `run_task`, unused by tapetum). Impact: at c=3 only three papers' LLM calls reach the pod simultaneously; community H200×8 DeepSeek-V4 configs cite `max-num-seqs 8` (`00-baseline.md:36`, `05a-web-concurrency-knee.md:31`), so ~5 GPU sequence slots likely sit idle every wave. Raising `--concurrency` toward 8 is the largest whisker-only win; raising beyond the pod knee only deepens queue depth.

- [CRITICAL] **Measured wall time implies ~30 s mean per LLM call, not ~10 s; the baseline amortized metric mixes layers.** Evidence: `00-baseline.md:12-14` (2159.8 s / 200 papers = 10.8 s/paper effective; 13/197 tier-2 escalations); call inventory below (213 calls). Back-solve: `T_call ≈ 2159.8 × 3 / 213 ≈ 30.4 s`. The baseline formula `ceil(200/3) × ~30 s` (`00-baseline.md:84`) is directionally right on call latency but **wrong on call count** (uses 200 papers, ignores 13 extra tier-2 calls) and **wrong on interpreting 10.8 s/paper as per-call latency** (it is wall-time amortized over papers, already divided by parallelism). Impact: planning around "10 s calls" underestimates decode budget; concurrency math must use `(tier1 + tier2_calls) / N`.

- [HIGH] **Within-paper tier1→tier2 escalation is a hidden serial chain inside one semaphore slot.** Evidence: `adjudicate.py:239-257` (`_custom_adjudicate` awaits `run_agent` only after `_custom_triage` completes); `tapetum_llm.md:17-19` (fast and deep both `alliance-pod`). Impact: 13 escalated papers (~6.6% of 197) hold their concurrency slot for two sequential ~30 s calls (~60 s) instead of one, adding ~6–7% wall time versus a flat tier1-only model and preventing tier2 from overlapping with other papers' tier1. Not fixable without pipeline async redesign; whisker can only reduce escalation rate (out of scope) or raise N so other papers fill idle slots during tier2.

- [HIGH] **`load_services()` reparses `SERVICES.toml` and reconstructs every `ModelBackend` on every paper; `PipelinePrompt.load` does not.** Evidence: `adjudicate.py:440-458` (`load_services()` + `resolve_pipeline_models` + `AgentBackend` construction per `adjudicate_paper` call); `prompt.py:248-249` (`@functools.cache` on `_load_cached`). Impact: 200 redundant TOML parses + backend inits per batch. CPU cost is small (~1–4 s total at ~5–20 ms each, <0.2% of 36 min) but is pure waste and scales linearly with corpus size; hoisting to batch scope in `cli._run` is zero-risk.

- [HIGH] **Every LLM call constructs a fresh `AsyncOpenAI` client; no connection reuse.** Evidence: `model_backends.py:283` (`client = AsyncOpenAI(...)` inside `VllmThinkingBackend.run`, once per call); 213 calls on the 200-paper run. Impact: repeated TLS/TCP setup on each of ~213 requests (~50–200 ms each → ~10–40 s cumulative, ~0.5–2% of wall time). **PARKED:** fix belongs in `packages/pipeline`, not whisker.

- [MED] **Tier1 runs with `max_tokens=4096` and no `thinking_budget` despite authority doc specifying 2048/1024.** Evidence: `adjudicate.py:450-456` (single `max_tokens=4096`, no `thinking_budget` on either slot); `tapetum_llm.md:118-120` (`max-output: 2048`, `thinking-budget: 1024`); `runner.py:266-272` (`run_agent` does not forward `spec.step.max_output_tokens` or `thinking_budget` to `agent.run`). Impact: tier1 decode likely emits more tokens than necessary on 200/213 calls; shaving decode is second only to raising N. Whisker can bind tier-specific `AgentBackend` kwargs without pipeline changes; forwarding step meta is **PARKED** in pipeline.

- [MED] **Chunked-paper serial triage is a dormant but catastrophic serialization point.** Evidence: `adjudicate.py:189-210` (chunk loop: `for index, chunk: await run_agent` serially); `00-baseline.md:20-22` (P2728R11/R12 were 755.8 s for 2 papers before data-URI strip; now 1-chunk). Impact: negligible on current 200-paper corpus post-filter; any future >500k-char paper (`MAX_PAPER_MD_CHARS = 500_000`) would monopolize one semaphore slot for N×30 s with no tier2 (`adjudicate.py:247-248`). Whisker-only mitigation: keep strip filter, monitor chunk count in batch footer.

- [LOW] **Sidecar path re-reads whisker sidecar after adjudicate already loaded it.** Evidence: `adjudicate.py:180-183` (read in `_custom_select`); `cli.py:436-438` (`_persist_result` → `fuse_verdicts` → `_read_whisker_sidecar` again). Impact: one extra disk read per paper (~200 reads); microseconds to low milliseconds each, <0.1% of 36 min. Whisker can pass whisker signals through or cache in result object.

## Call-path trace (batch start → sidecar written)

```
main() [cli.py:505-516]
  asyncio.run(_run)
    _load_backend, select_candidates / pids
    sem = Semaphore(concurrency)          ← GLOBAL BATCH THROTTLE
    asyncio.gather(_adjudicate_one × N)
      async with sem:                     ← slot acquired
        adjudicate_paper(pid)             [adjudicate.py:425-504]
          PipelinePrompt.load (cached)    [prompt.py:248]
          load_services()                 ← REDUNDANT PER PAPER
          resolve_pipeline_models + AgentBackend × slots
          build_pipeline + StepContext
          dispatch(steps 0→3 serial)      [runner.py:279-403]
            Step 0 _custom_select: disk I/O (paper.md, sidecar), strip_binary
            Step 1 _custom_triage:
              run_agent → AgentBackend.run → VllmThinkingBackend.run
                AsyncOpenAI() NEW         ← PER CALL
                stream chat.completions   ← NETWORK + DECODE (~30 s)
                retry loop (max 2)        [model_backends.py:300-406]
            Step 2 _custom_adjudicate (13/197 papers):
              run_agent (second serial call, same pod)
            Step 3 _custom_decide: ground_spans (CPU)
        _persist_result                   [cli.py:230-246]
          fuse_verdicts, json write sidecar
      sem released
```

**Serialization points ranked by wall-time impact:** (1) CLI semaphore N=3, (2) pod scheduler / `max-num-seqs` (external, unknown), (3) per-call LLM decode ~30 s, (4) within-paper tier1→tier2 serial on 6.6% of papers, (5) chunk serial loop (dormant), (6) fresh HTTP client per call (PARKED pipeline), (7) per-paper `load_services` (CPU noise).

## Quantification

| Metric | Value | Source |
|--------|-------|--------|
| Papers (2026-07-07 run) | 200 | `00-baseline.md:12` |
| Wall time | 2159.8 s (36.0 min) | `00-baseline.md:12` |
| Client concurrency | 3 | `00-baseline.md:12` |
| Amortized wall per paper | 10.8 s | `00-baseline.md:12` (derived) |
| Tier-1 LLM calls | 200 (1 per paper, post data-URI filter) | `adjudicate.py:197-200`, `00-baseline.md:22` |
| Tier-2 escalations | 13 / 197 ≈ 6.6% | `00-baseline.md:23` |
| Total LLM calls (200-paper run) | **213** (200 + 13) | derived |
| Mean LLM call duration (back-solved) | **~30.4 s** = `2159.8 × 3 / 213` | derived from measured wall + c=3 |
| Model retries (full run) | 1 | `00-baseline.md:14` |
| Default concurrency in code | **1** (run used 3 via flag) | `cli.py:52` |

**Fixed per-paper CPU/setup (re-done every paper):** `load_services()` + `resolve_pipeline_models` + `AgentBackend` construction + `build_pipeline` + `dispatch` step-0 disk reads + `ground_spans` in decide. `PipelinePrompt.load` is cached after first call. Estimated aggregate client CPU/IO overhead: **<3% of 36 min** (~97%+ is network + pod prefill/decode). Dominant term: ~30 s × 213 calls / 3 concurrent ≈ 2140 s ≈ measured wall.

**Baseline numbers challenged (evidence, not guesses):**
1. `T = ceil(200/3) × ~30 s` ignores tier-2 calls; correct first-order model is `(200 + 13) × T_call / 3`, which at `T_call ≈ 30.4 s` reproduces 2159.8 s exactly.
2. "10.8 s/paper effective" is **not** per-call latency; dividing it into 30 s to claim "only 2–3× speedup" (`00-baseline.md:18-19`) compares incomparable quantities. c=3 achieves near-linear call throughput (213 calls in 2160 s vs ~6390 s serial at 30 s/call ≈ 3.0×).
3. "Single-paper latency 15–30 s" (`00-baseline.md:18`) comes from 3–9 paper micro-batches with variance (`00-baseline.md:16-17`), not an isolated c=1 corpus measurement; the 200-paper sustained average per call is ~30 s.
4. `PipelinePrompt.load` per call is **not** a cost center (`prompt.py:248` caches); `load_services()` per call **is** (`adjudicate.py:441`, uncached).

## Top 3 changes inside `packages/whisker` (ranked by expected wall-time impact)

1. **Raise default `--concurrency` from 1 to 8** (`cli.py:52`, `_DEFAULT_CONCURRENCY`). Rationale: only batch-level throttle; pod evidence suggests knee near 8 sequences. Expected: up to ~2.7× wall reduction if knee ≥ 8 (`2159.8 × 3/8 ≈ 810 s`); diminishing returns and latency collapse beyond pod knee (queue-only). Risk: tail latency spikes on long-prefill papers; monitor p99 before raising past 8.

2. **Tier-specific `AgentBackend` budgets in `adjudicate.py`** — fast slot `max_tokens=2048, thinking_budget=1024`; deep slot `max_tokens=4096, thinking_budget=4096` per `tapetum_llm.md:118-141`. Rationale: 200/213 calls are tier1; halving decode ceiling on the majority path directly cuts the ~30 s mean. Whisker-only because agents are constructed in `adjudicate_paper`, not by runner step-meta forwarding. Expected: 15–35% tier1 latency reduction if output tokens dominate (needs A/B on 9-paper batch).

3. **Hoist batch setup out of per-paper loop** — new `prepare_adjudication_batch()` (or inline in `cli._run`) calling `load_services`, `resolve_pipeline_models`, `build_pipeline`, `_build_hooks` once; pass shared `agents`/`pipeline`/`registry` into `adjudicate_paper`. Rationale: eliminates 200× `SERVICES.toml` parse. Expected wall-time savings small (<0.2%) but removes linear CPU tax and simplifies a future shared-client injection point.

**Honorable mention (whisker):** `asyncio.wait_for(adjudicate_paper(...), timeout=...)` per paper in `_adjudicate_one` — prevents one hung LLM call from holding a semaphore slot for the full httpx default timeout; improves effective throughput under tail failures, not mean case.

## PARKED (requires `packages/pipeline` or infra; not whisker)

- Reuse `AsyncOpenAI` / httpx connection pool across calls (`model_backends.py:283`).
- Forward `spec.step.max_output_tokens` and `thinking_budget` in `run_agent` (`runner.py:266-272`).
- Disable or make conditional `stream=true` for batch mode (service config in `SERVICES.toml`, read-only to whisker).
- Server-side: confirm `max-num-seqs`, prefix caching, dual-pod sharding via `--service deep=h200x8-deepseek-v4-pro` (operational, no code).

## False-pass hypothesis

Raising concurrency or shrinking tier1 `max_tokens` could cause truncated JSON on borderline papers; the backend retries once (`model_backends.py:300-406`) then fails loudly. Truncation that still parses as valid but incomplete `Adjudication` is the residual risk: a structurally valid JSON object with empty `axis_findings` could pass validation and yield a lenient tier1, skipping escalation. Mitigation: keep `output_retries` path hot, watch for escalations dropping when concurrency rises.

## False-fail hypothesis

Higher concurrency increases pod queue depth; under KV pressure, long-prefill WG21 papers may hit `APITimeoutError` and retry (`model_backends.py:341-350`), surfacing as `error` verdicts in batch footer (`cli.py:478-479`) without conversion defects. Per-paper timeout in whisker could also spuriously fail slow-but-valid papers if set too aggressively.

## What would change my mind

A concurrency sweep on the same 200-paper corpus: `--concurrency` ∈ {1, 3, 8, 16, 32} with per-run wall time, error count, and p95 single-call latency logged. If wall time stays flat above N=3, the bottleneck is pod-side (not client semaphore) and raising whisker defaults alone will not reach single-digit minutes.
