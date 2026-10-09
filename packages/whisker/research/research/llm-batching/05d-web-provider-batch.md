# 05d - Web Forager: Provider Batch APIs vs Client-Side Parallel Processors

**Scope:** How OpenAI/Anthropic provider batch APIs work semantically, why they
mismatch a latency-focused self-hosted vLLM run (~200 papers, 36 min today),
and which maintained open-source client patterns are worth porting into whisker.

**Search seeds:** `openai cookbook api_request_parallel_processor.py parallel
requests pattern`, `anthropic message batches api vs realtime concurrency
self-hosted`, refined with OpenAI Batch API docs, LiteLLM batching, aiolimiter,
tenacity, vLLM online batch endpoint.

---

## Executive synthesis

| Model | Latency | Cost lever | Right for tapetum? |
| --- | --- | --- | --- |
| OpenAI `/v1/batches` | Up to 24 h SLA (often faster) | 50% token discount | **No** — wall-time goal is minutes |
| Anthropic Message Batches | Up to 24 h SLA (often <1 h) | 50% token discount | **No** — same reason |
| Client async concurrency (cookbook, aiolimiter, semaphore) | Seconds per request | None (pod is hourly) | **Yes** — extends existing `--concurrency` |
| vLLM continuous batching (server-side) | Real-time | Throughput via GPU saturation | **Yes** — already happens when we raise N |

Provider batch APIs optimize **cost and provider capacity scheduling**, not
interactive throughput. Our pod is billed per uptime hour (`00-baseline`), so
the 50% discount is irrelevant. The portable win is **client-side parallel
dispatch with dual request/token budgeting, retry queue, and backpressure** —
the OpenAI Cookbook processor is the canonical reference; `aiolimiter` +
`tenacity` are composable building blocks; LiteLLM's `batch_completion` is
heavier and sync-thread-based.

---

## Finding cards

### 1. OpenAI Batch API — async JSONL job, 24 h window, separate rate pool

**URL:** https://developers.openai.com/api/docs/guides/batch

**Summary:** OpenAI Batch is a **managed async job**, not a faster synchronous
path. You upload a JSONL file (up to 50,000 lines / 200 MB), call
`batches.create(input_file_id=..., endpoint="/v1/chat/completions",
completion_window="24h")`, then **poll until `status=completed`** and download
an output JSONL matched by `custom_id` (order not guaranteed). Processing is
guaranteed within **24 hours** (often much sooner for small jobs); pricing is
**50% off** standard rates. Batch rate limits are a **separate pool** from
real-time API limits (enqueued prompt tokens per model, 2,000 batches/hour).

**Relevance:** **HIGH** — defines the provider "batch" semantics we must not
confuse with client concurrency. Wrong model for tapetum because: (a) 24 h SLA
vs ~36 min wall-time target, (b) submit/poll/download orchestration replaces
streaming results, (c) cost discount is meaningless on hourly RunPod billing,
(d) no vLLM equivalent to OpenAI's offline queue-with-SLA exists on our pod.

---

### 2. Anthropic Message Batches — same async job pattern, poll-based results

**URL:** https://platform.claude.com/docs/en/build-with-claude/batch-processing

**Summary:** Anthropic's Message Batches API creates a batch from up to
**10,000 independent Messages requests**, processes them **asynchronously**
(each request handled independently), and exposes results when all complete or
after **24 hours** (whichever first). Typical completion is **<1 hour** but SLA
is 24 h; **50% cost reduction** vs synchronous Messages. Results are retrieved
by polling batch status then iterating `client.messages.batches.results()`;
streaming is **not supported**. Batches are immutable after submission; errors
surface per-request in the results file, not as submission-time exceptions.

**Relevance:** **HIGH** — confirms both major providers converge on the same
pattern: **deferral for cost/capacity**, not latency. Explicitly unsuitable for
interactive or latency-bound workloads (docs and community guides agree: use
synchronous parallel calls for background jobs needing minutes, not hours).
Self-hosted vLLM wins on real-time throughput via continuous batching on
concurrent HTTP requests, not via provider-style overnight jobs.

---

### 3. OpenAI Cookbook `api_request_parallel_processor.py` — dual-budget async worker

**URL:** https://github.com/openai/openai-cookbook/blob/main/examples/api_request_parallel_processor.py

**Summary:** Reference client for **high-throughput synchronous API calls**
under provider rate limits. Core loop: stream JSONL requests from disk; maintain
**two refilling budgets** (`available_request_capacity`,
`available_token_capacity`) that replenish proportional to elapsed time against
`max_requests_per_minute` / `max_tokens_per_minute`; when both budgets cover
the next request, fire `asyncio.create_task(APIRequest.call_api(...))` via a
shared `aiohttp.ClientSession`. Failed requests (including rate-limit 429s) go
to an **`asyncio.Queue` retry queue** (retried before new file reads); after any
429 the loop pauses **15 seconds** global cooldown. Token estimates use tiktoken
(prompt + `n * max_tokens`). Still referenced from OpenAI's current
`How_to_handle_rate_limits.ipynb` cookbook.

**Relevance:** **HIGH** — most directly portable pattern for whisker. Maps to
our problem: 200 independent requests, need higher N without 429 storms. We
already have `Semaphore + gather`; this adds **token-aware budgeting**, **retry
queue priority**, and **429 backpressure** we lack. Maintenance: living in
actively updated `openai-cookbook` repo (single ~500-line script, no package
dep beyond aiohttp/tiktoken). Adaptation: replace file streaming with in-memory
paper list; swap aiohttp for shared `AsyncOpenAI`; on self-hosted pod set RPM/TPM
to empirical knee, not provider tiers.

---

### 4. `aiolimiter` — maintained leaky-bucket backpressure primitive

**URL:** https://aiolimiter.readthedocs.io/en/stable/

**Summary:** Small MIT library (v1.2.1, ~16M PyPI downloads/month, actively
maintained) implementing **`AsyncLimiter(max_rate, time_period=60)`** with the
**leaky bucket** algorithm. Used as `async with limiter:` or `await
limiter.acquire(amount=1)`; provides `has_capacity()` for non-blocking checks.
Burst up to `max_rate` then blocks until capacity refills. Docs warn: **one
limiter per asyncio loop**, not shared across loops.

**Relevance:** **MED** — not a full processor; composable **backpressure**
layer. Could wrap each `run_agent` call instead of bare `Semaphore(N)` to
enforce requests/minute without hard concurrency cap, or implement dual limiters
(request count + estimated tokens). Lighter than porting the full cookbook loop;
does not provide retry queue or 429 cooldown by itself — pair with tenacity.

---

### 5. Tenacity — maintained retry/backoff decorator (pair with header-aware waits)

**URL:** https://tenacity.readthedocs.io/en/stable/

**Summary:** General-purpose retry library (actively maintained; fork of
unmaintained `retrying`). Provides `@retry(stop=..., wait=..., retry=...)` for
sync and **`AsyncRetrying`** for async. Standard LLM pattern:
`retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError))`
+ `wait_exponential_jitter(initial=1, max=30)` + `stop_after_attempt(4)`.
Production guides stress tenacity **does not read `Retry-After` headers
automatically** — custom wait class should parse `exc.response.headers` on 429
or risk thundering herd / wasted attempts.

**Relevance:** **MED** — solves the **retry/backoff** slice of the cookbook
processor without porting its main loop. We already have per-paper firewall and
1 model retry in baseline; tenacity would standardize transient-error handling
at HTTP layer. Not a parallelism solution on its own. Maintenance: stable, wide
adoption; no LLM-specific logic built in.

---

### 6. LiteLLM `batch_completion` + Router — ThreadPoolExecutor wrapper, separate from provider Batch API

**URL:** https://docs.litellm.ai/docs/completion/batching

**Summary:** LiteLLM's **`batch_completion(model, messages=[...])`** sends a
list of message-lists via **`ThreadPoolExecutor(max_workers=100)`**, chunking
into sub-batches of 100; exceptions captured per slot, not raised globally.
**`batch_completion_models`** races multiple models, returns first response
(cancels others). **`Router.abatch_completion`** adds deployment routing. This
is **not** OpenAI/Anthropic async Batch API — it is **client-side parallel
sync/async HTTP**. Router adds **`max_parallel_requests` per deployment**
(semaphore for async). Known bug (issue #20704, 2025): `batch_completion_models_all_responses` historically executed sequentially due to `future.result()` inside submit loop — verify version if using.

**Relevance:** **MED** — maintained (BerriAI/litellm, active releases) but
**heavy dependency** for whisker constraints (pipeline read-only; we'd wrap at
whisker CLI). ThreadPool model differs from our asyncio path; vLLM-specific
branch delegates to `vllm_handler.batch_completions`. Useful as reference for
**max_workers + exception-per-item** pattern, not as drop-in. Router's
`max_parallel_requests` mirrors our Semaphore but adds RPM/TPM-aware routing we
don't need on a single pod.

---

### 7. vLLM `/v1/chat/completions/batch` — online multi-conversation POST (not provider async batch)

**URL:** https://docs.vllm.ai/en/latest/examples/generate/batched_chat_completions_online/

**Summary:** vLLM 0.24+ exposes **`POST /v1/chat/completions/batch`**: send
`messages` as a **list of conversations** in one HTTP request; server processes
them concurrently and returns one choice per conversation (indexed 0..N-1).
Limitations vs standard endpoint: **no streaming, no tool use, no beam search**.
Separate from `vllm run-batch` CLI (offline JSONL file processing). Under the
hood, vLLM's **continuous batching** (iteration-level scheduling) already
merges concurrent individual `/v1/chat/completions` requests at the engine —
raising client concurrency exploits this without a special batch endpoint.

**Relevance:** **HIGH** — clarifies self-hosted "batching" is **real-time
server-side scheduling**, not OpenAI's 24 h job queue. For tapetum: (a)
provider Batch APIs are the wrong abstraction; (b) optional HTTP micro-batching
(N papers per POST) could cut connection overhead but conflicts with our
per-paper streaming + structured-output path unless we validate endpoint support
on the pod; (c) simplest lever remains raising `--concurrency` on individual
streaming calls and letting continuous batching absorb load.

---

## Why provider Batch APIs fail the tapetum use case (checklist)

1. **Latency contract:** 24 h SLA vs target of single-digit minutes (`00-baseline`).
2. **Cost model:** 50% token discount irrelevant; pod is hourly, not per-token.
3. **Result delivery:** Poll + JSONL download vs in-process verdict persistence.
4. **Streaming:** Provider batches return complete messages; we stream + assemble.
5. **Infrastructure:** No shell on pod for `vllm run-batch`; API is online-only.
6. **Determinism:** Async job scheduling adds run-to-run variance in completion order timing (verdict order already handled by input-order persistence).

---

## Port recommendation (ranked)

| Rank | Pattern | Port cost | Fits whisker |
| --- | --- | --- | --- |
| 1 | Cookbook dual-budget loop + retry queue | Medium (~100 LOC in cli) | Best match |
| 2 | Semaphore(N) + aiolimiter RPM cap | Low | Incremental on today |
| 3 | tenacity on HTTP transient errors | Low | Complements 1 or 2 |
| 4 | LiteLLM batch_completion | High (new dep, threads) | Poor fit |
| 5 | Provider Batch API client | N/A | Wrong semantics |
