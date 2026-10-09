# 06 - Performance-Scalability

**Verdict:** usable-with-conditions — wall clock is dominated by serial LLM round-trips (one triage call per paper, often doubled by JSON retry), not Python overhead; batch throughput scales O(N) with paper count because the CLI never fans out independent papers.
**Confidence:** high

## Findings

- [CRITICAL] Batch loop is strictly serial: one `await adjudicate_paper(...)` per PID with no concurrency knob. Evidence: `cli.py:277-288` (`for i, pid in enumerate(pids)` then single await); baseline runtime 200 papers in ~1.5–2 h → **27–36 s/paper** (`00-baseline.md:49`). Impact: throughput cannot exceed single-paper latency × N; this is the primary reason a 200-paper run costs 1.5–2 h.
  Determinism risk if fixed: shared-pod vLLM continuous batching can perturb MoE routing and token choices under concurrent load (`MODELS.md:69`; vLLM batch invariance docs in `05-web.md` Q4). Mitigation: bound client concurrency to pod `--max-num-seqs` and use index-ordered `gather_concurrent` (`runner.py:133-162`; vLLM #10269 in `05-web.md` Q3).

- [HIGH] Per-paper wall time is ~95%+ LLM latency, not framework setup. Evidence: reproduced benchmark on HEAD — full per-paper setup (`PipelinePrompt.load` + `load_services` + `resolve_pipeline_models` + `build_pipeline` + `AgentBackend` construction) averages **2.5 ms/paper** over 200 iterations; grounding on an 80k-char doc with 3 spans averages **37 ms/paper**. Against baseline **25–40 s/paper**, Python overhead is **<0.2%**. Impact: optimize inference path and concurrency, not prompt parsing.

- [HIGH] JSON retry loop often doubles LLM cost on the same paper. Evidence: batch mode explicitly notes retry warnings fire on "most papers" because deepseek-v4-pro token corruption self-corrects on attempt 2 (`cli.py:51-52`); `_RAW_JSON_MAX_ATTEMPTS = 3` with full re-issue per failure (`model_backends.py:76-85`, `:382-421`); vLLM Issue #41985 reports CJK injection in **~50–75%** of outputs at temperature=1.0 (`05-web.md` Q2). Static decomposition: one successful triage call ≈ **15–25 s**; one retry adds another full round-trip → observed **25–40 s/paper** band. Impact: guided decoding / structured outputs (`05-web.md` Q4) is a latency win comparable to adding concurrency for retry-heavy papers.

- [HIGH] Oversized papers multiply LLM calls via a serial chunk loop (D11). Evidence: papers above `MAX_PAPER_MD_CHARS = 500_000` split on H2 and triage **serially** (`constants.py:44`, `adjudicate.py:174-191`: `for index, chunk in enumerate(chunks): ... await run_agent`); baseline notes **~6 corpus papers** exceed the budget and a 2.5 MB paper yields **~5–6 serial chunks** (`constants.py:42-43`). Impact: outlier papers cost **5–6×** single-paper latency (~125–240 s at 25–40 s/call) and dominate batch tail; chunk parallelization via `ctx.gather_concurrent` would cut that factor by concurrency (with same determinism caveats as paper-level fan-out).

- [MED] `load_services()` is re-parsed and re-instantiates every backend on every paper while `PipelinePrompt.load` is cached. Evidence: `adjudicate.py:378-379` calls both each invocation; `PipelinePrompt.load` hits `@functools.cache` on `_load_cached` (`prompt.py:248-245`); `load_services` has no cache and rebuilds all `[services.*]` backends (`services.py:97-215`). Reproduced: **2.05 ms/call × 200 = 409 ms** total batch waste. Impact: low absolute cost today, but scales with service count and hides a footgun if backends grow heavyweight (HTTP pools, tokenizer init).

- [MED] Evidence grounding uses `rapidfuzz.partial_ratio` against the **whole normalized document** per span. Evidence: `grounding.py:39-51` (`norm_md = normalized_text(markdown)` once, then `partial_ratio(norm_quote, norm_md)` per span); whisker documents full-document rapidfuzz as milliseconds (`whisker/CLAUDE.md` metrics section). Reproduced: **37 ms** at 80k chars / 3 spans; **269 ms** at 500k chars / 3 spans. Impact: negligible vs LLM for typical papers; becomes visible only on max-budget papers with many evidence spans, and is still **<1%** of 25–40 s/paper.

- [LOW] Cascade tier-2 is dead weight in production (0 escalations), so throughput is already single-call — no deep-tier savings left on the table. Evidence: baseline **0 / 197** sidecars with `escalated=true` (`00-baseline.md:46`); gate at `adjudicate.py:206-208`; `fast` and `deep` both map to `alliance-pod` (`tapetum_llm.md:17-19`). Impact: performance work should not target cascade gating; the triage step is the sole LLM hot path for 197/197 successful papers.

## False-pass hypothesis

A 200-paper batch run with `--concurrency 8` completes in ~20 min with all sidecars written, but three papers flip from `review` to `pass` because concurrent vLLM batching changed deepseek confidence across the ambiguous band — ordering invariants hold, verdict distribution shifts.

## False-fail hypothesis

An operator rejects paper-level concurrency because D11 mentions global semaphores, missing that the sanctioned hook is CLI paper fan-out (`00-baseline.md:71`) not `_parallel_semaphore`; serial 200-paper runs continue at 1.5–2 h while the stack is labeled "too slow to adopt."

## What would change my mind

A profiled 200-paper rerun with per-phase timestamps (setup vs LLM vs grounding vs persist) showing Python/I/O ≥ 10% of wall clock, or a pod trace proving JSON retries occur on < 5% of papers (making guided decoding a minor win).

## Top 3 throughput wins (ranked)

| Rank | Win | Expected gain | Determinism risk |
|------|-----|---------------|------------------|
| 1 | Paper-level `--concurrency N` on `cli.py` batch loop via `gather_concurrent` (`runner.py:133-162`), N ≤ pod `--max-num-seqs` (vLLM #10269, `05-web.md` Q3) | ~N× batch wall clock up to server capacity (200 papers: **1.5–2 h → ~12–30 min** at N=4–8) | **HIGH** — MoE routing + continuous-batching token flips (`MODELS.md:69`; `05-web.md` Batch Invariance) |
| 2 | Adopt vLLM structured outputs / guided JSON to eliminate CJK retry round-trips (`model_backends.py:76-85`; vLLM #41985, `05-web.md` Q2/Q4) | ~**30–50%** latency reduction on retry-heavy papers (most of batch per `cli.py:51-52`) | **MED** — thinking+JSON interaction on DeepSeek-V4 (Issue #41132, `05-web.md` Q1); mitigated in v0.9+ with `--reasoning-parser` |
| 3 | Bounded chunk fan-out for oversized papers (`adjudicate.py:187-191`) instead of strictly serial chunk triage | ~**5–6×** speedup on ~6 outlier papers (tail latency) | **MED** — same shared-pod batch interference as rank 1, confined to multi-chunk papers |
