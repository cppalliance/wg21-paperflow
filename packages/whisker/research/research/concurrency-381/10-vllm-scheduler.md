# 10 - vLLM-Scheduler-Auditor

**Verdict:** risky — vLLM 0.24 accepts all 381 into an unbounded FCFS waiting queue and still schedules only 16 sequences per iteration; wall time does not improve vs c=16, but tail TTFT grows to many minutes and intersects default client read timeouts.
**Confidence:** high (scheduler semantics + confirmed pod flags); medium on exact tail error count without a live c=381 run

## Findings

- [CRITICAL] **`--max-num-seqs 16` caps GPU parallelism, not queue depth.** Evidence: `cppalliance/runpod` `templates/deepseek/H200SXM.txt` (`--max-num-seqs 16`); vLLM Discuss maintainer clarification (`05a-web-concurrency-knee.md:37-41`); measured 381 papers at c=16 in 722.4 s with 0 errors (user baseline). Impact: firing 381 requests at once does not raise throughput above 16 concurrent sequences; it only grows the server waiting queue from ~0–16 (client-throttled) to ~365.

- [CRITICAL] **Waiting queue is unbounded by default; no 429/503 rejection on this pod.** Evidence: vLLM RFC #18826 and PR #27064 (`--max-waiting-queue-length` rejects with HTTP 503 when enabled); `H200SXM.txt` launch flags omit that parameter; PR #27064 notes pre-0.24 behavior is "all incoming requests are added to the queue" as an unbounded CPU deque. Impact: all 381 POSTs are admitted; rejection is not the failure mode — queue latency and resource pressure are.

- [CRITICAL] **Continuous batching admission is per scheduler step: decode-first, then chunked prefill under token budget.** Evidence: vLLM optimization docs (`https://docs.vllm.ai/en/stable/configuration/optimization/`, Chunked Prefill + Preemption sections); internal `05a-web-concurrency-knee.md:9-11`. Impact: with V1 defaults (chunked prefill on, not disabled in template), long 5k–300k-token prompts are chunked across iterations rather than monopolizing one step, but a burst of 381 still serializes through 16 slots FCFS — tail requests wait for hundreds of prior service intervals before first prefill chunk.

- [HIGH] **Tail TTFT at c=381 is order-of-queue-position × mean service time / 16.** Evidence: FCFS waiting queue (PR #6867, issue #6077); baseline ~30 s mean per call (`17-latency-decomposer.md:10`, 722.4 s / 381 ≈ 1.9 s/paper effective at c=16 implies saturated 16-wide service); back-of-queue estimate: position 381 waits ~(380/16)×30 s ≈ **712 s** before scheduling plus ~2 s prefill. Impact: exceeds default `AsyncOpenAI` httpx **600 s read** timeout (`15-concurrency-safety.md:8`, `model_backends.py:283` no custom timeout) even though whisker wraps papers in 900 s (`cli.py:76`); tail papers likely `APITimeoutError` before first stream chunk — the c=16 baseline stayed clean because client semaphore kept server queue shallow.

- [HIGH] **KV-cache pressure triggers V1 `RECOMPUTE` preemption, not swap.** Evidence: vLLM optimization docs Preemption section (default `PreemptionMode.RECOMPUTE` in V1); MoE H200 guidance (`05a-web-concurrency-knee.md:17-21`, Paralleliq + issue #42265). Impact: 16 concurrent decode-heavy tapetum calls with 5k–8.5k-token typical prompts are what the pod already saturates at c=16; adding 365 queued long-context requests increases preemption/recompute churn when a 300k-token paper reaches the head, widening ITL/TTFT variance for everyone — preemption count is the early warning metric (`disable_log_stats=False`).

- [MED] **No server-side per-request execution timeout on alliance-pod.** Evidence: `H200SXM.txt` lacks `--enable-request-timeout` / `--api-request-timeout`; third-party vLLM timeout docs state both flags are required together for enforcement. Impact: vLLM will not kill long-queued or long-generating requests server-side; failures surface only when the client/proxy closes the connection (600 s httpx default, RunPod proxy limits unknown per `00-baseline.md:33-35`, `15-concurrency-safety.md:20`).

- [MED] **Measured c=32 (20 papers) showed zero errors; c=381 is unmeasured queue depth.** Evidence: `20-sweep-results.md:9-14,29-30` (c=8/16/32 on 20 PIDs, 0 errors); `cli.py:66-69` warns behavior past `_MAX_TESTED_CONCURRENCY = 32` is unmeasured. Impact: scheduler tolerates brief over-subscription (20 > 16 queued 4 briefly); 381 simultaneous connections is 19× deeper than the tested worst case — proxy connection caps and CPU memory for 381 pending request objects are unknown.

- [LOW] **Prefix caching is on by default and benefits shared ~2.9k-token system/schema prefix.** Evidence: `20-sweep-results.md:91-92`; `05c-web-prefix-guided.md:19-23`. Impact: saves <1 s/call on typical papers when warm (`17-latency-decomposer.md:20`); irrelevant to queue-wait dominance at c=381.

## Expected wall-time at c=381 vs c=16

| Metric | c=16 (measured) | c=381 (projected) |
|--------|-----------------|-------------------|
| Server active sequences | ≤16 | ≤16 (unchanged) |
| Server waiting queue depth | ~0–16 (client-throttled) | ~365 steady-state |
| Total LLM calls | ~381 tier-1 + ~6% tier-2 ≈ **406** | same |
| Wall time (if no timeouts) | **722.4 s** | **~730–800 s** (406×30/16 ≈ 761 s; ±preemption/KV noise) |
| Tail request TTFT | bounded by client wave (~≤60 s queue) | **~700+ s** for last FCFS entries |
| Error expectation | 0 (measured) | **non-zero** on tail fraction from 600 s httpx read timeout before first token; retries add wall time |

**Bottom line:** c=381 does not beat c=16 on wall time (same 16-wide bottleneck). It trades a shallow queue for a deep one, converting scheduler patience into client-side timeouts and spurious incomplete corpus coverage.

## What would change my mind

A live `whisker-tapetum-llm --review-all --concurrency 381` on the same 381-PID list with: (1) `error` count = 0, (2) wall within 5% of 722.4 s, (3) pod metrics showing `total_cumulative_preemption_cnt` stable — would flip to **safe**. Conversely, `--max-waiting-queue-length` enabled on the pod returning 503 once the queue exceeds N would make c=381 **breaks** immediately (mass rejection) rather than risky (slow success).
