# 05 - Web Finding Cards: llm-stack (self-target)

Collected 2026-07-03 by 3 Composer foragers (5 questions from `00-baseline.md`).
Cards are grouped under their originating question. Deduplicated by URL.

## Q1: vLLM guided decoding vs thinking/reasoning models (`<think>` blocks)

**OpenAI Chat Completion Structured Outputs With Reasoning (vLLM example)** [HIGH]
https://docs.vllm.ai/en/v0.8.5/getting_started/examples/openai_chat_completion_structured_outputs_with_reasoning.html
Official vLLM example for DeepSeek-R1-style reasoning models: "The thinking process will not be guided by the JSON schema provided by the user. Only the final output will be structured." Requires `--reasoning-parser deepseek_r1` (or equivalent). Structured JSON lands in `content`, free-form reasoning in `reasoning_content`.

**Reasoning Outputs - vLLM docs** [HIGH]
https://docs.vllm.ai/en/stable/features/reasoning_outputs/
Documents `--reasoning-parser` and a model compatibility table (`json, regex` structured output for DeepSeek R1, Qwen3, ...). Mechanism: the structured-output engine (xgrammar) uses the Reasoner's `end_token_id` to detect active reasoning and SKIP grammar masking until reasoning ends. DeepSeek-V4-Pro requires `enable_thinking: true` in `chat_template_kwargs` to emit thinking tokens at all.

**[V1] Structured Outputs + Thinking compatibility (PR #16577)** [HIGH]
https://github.com/vllm-project/vllm/pull/16577
Merged PR bringing thinking+structured-output coexistence to the V1 engine: grammar applies only after the reasoning segment. Landed in v0.9.0+. Test command: `vllm serve ... --guided-decoding-backend xgrammar --reasoning-parser deepseek_r1`.

**[Feature]: Guided decoding after thinking is done (Issue #18255)** [HIGH]
https://github.com/vllm-project/vllm/issues/18255
Original failure mode: with guided decoding on DeepSeek-R1, JSON-invalid tokens were masked DURING the thinking phase, degrading CoT and answer quality; JSON sometimes routed to `reasoning_content` instead of `content`. Closed after V1 support shipped in PR #16577.

**[Bug]: DeepSeek V3.2 & V4 incorrect structured output when thinking enabled (Issue #41132)** [HIGH]
https://github.com/vllm-project/vllm/issues/41132
Reproduces on DeepSeek-V4-Pro with `--reasoning-parser deepseek_v4` and `enable_thinking: True`: `response_format: json_object` produces valid JSON inside `reasoning` while `content` is None. Fixed by PR #41199 ("Pass reasoning parser kwargs to structured output"). Directly relevant to RunPod DeepSeek v4 Pro deployments.

## Q2: DeepSeek stray-CJK-token JSON injection: reports and mitigations

**DeepSeek-V4-Pro CJK bad tokens on vLLM, SGLang unaffected (vLLM Issue #41985)** [HIGH]
https://github.com/vllm-project/vllm/issues/41985
Reproducible vLLM bug: DeepSeek-V4-Pro at temperature=1.0 injects stray CJK tokens in ~50-75% of English/code outputs, breaking JSON; official inference shows ~20% baseline because ~86% of CJK/ASCII boundaries have <1.0 logit margin. Root cause: MLA attention FP8 precision in vLLM's custom decode path. SGLang shows zero bad tokens. Merged PR #42287 reported to fix it.

**Runtime token block for adjacent tokens 2576/2577 (DeepSeek-V3 Issue #1241)** [HIGH]
https://github.com/deepseek-ai/DeepSeek-V3/issues/1241
Tokenizer IDs 2576 ("...") and 2577 (CJK) are adjacent, so sampling occasionally picks the wrong token mid-English/JSON. Proposed mitigations: `bad_words`/logit block, adaptive regeneration, fallback string replace. Explicitly notes JSON/code breakage.

**Intermittent isolated Chinese characters in English-only sessions (DeepSeek-V3 Issue #1045)** [HIGH]
https://github.com/deepseek-ai/DeepSeek-V3/issues/1045
Long-running report across V3/R1-class models: sporadic isolated CJK characters in otherwise correct English text. Attributed to multilingual tokenizer proximity and low-probability sampling errors. Reproducible across unrelated sessions.

**The CJK token bug: vocabulary adjacency and JSON breakage (pixelstech)** [MED]
https://www.pixelstech.net/article/1756263566-the-curious-case-of-the-%E2%80%9C%E6%9E%81%E2%80%9D-token-bug-in-deepseek-v3-1
Community synthesis with concrete invalid-JSON examples. Ranks mitigations: structured-output APIs first, post-parse retry second, character sanitization last resort.

**Structured outputs / guided decoding in vLLM (Red Hat)** [MED]
https://developers.redhat.com/articles/2025/06/03/structured-outputs-vllm-guiding-ai-responses
Server-side mitigation: per-token masking via guided JSON/regex/grammar backends (XGrammar, llguidance) prunes invalid continuations (including stray CJK inside numeric/string JSON slots) before sampling. Complementary controls: `logit_bias`, `bad_words`, `allowed_token_ids`.

## Q3: Ordered bounded-concurrency asyncio pattern for deterministic batch LLM calls

**Coroutines and tasks - Python 3 docs (asyncio.gather, TaskGroup)** [HIGH]
https://docs.python.org/3/library/asyncio-task.html
`asyncio.gather(*tasks)` returns results in input order regardless of completion order. `return_exceptions=True` turns exceptions into positional results for deterministic partial batches. `TaskGroup` cancels all siblings on first failure (wrong fit when all N items should be attempted).

**Waiting in asyncio (hynek.me)** [HIGH]
https://hynek.me/articles/waiting-in-asyncio/
Canonical bounded+ordered recipe: create all tasks upfront, wrap each worker in `async with semaphore`, then `await asyncio.gather(...)`. Avoid `as_completed` when order matters. Per-item timeouts belong inside each worker. gather + return_exceptions=True is the fit when all N items must be attempted without sibling cancellation.

**OpenAI Cookbook - api_request_parallel_processor.py** [HIGH]
https://github.com/openai/openai-cookbook/blob/main/examples/api_request_parallel_processor.py
Reference production pattern: concurrent tasks with capacity throttling (RPM/TPM), retry with backoff, results keyed by request metadata so output order is recoverable. Warns that unfettered parallelism causes 429s and wasted retries.

**Mastering asyncio.gather and as_completed for LLM processing (Instructor blog)** [HIGH]
https://python.useinstructor.com/blog/2023/11/13/learn-async/
Standard LLM batch recipe: `Semaphore(N)` + per-input coroutine + `asyncio.gather` for input-order output. Labels semaphore-limited gather as the rate-limited ordered path for structured extraction workloads.

**[Usage]: Adaptive batching and concurrent requests (vLLM Issue #10269)** [HIGH]
https://github.com/vllm-project/vllm/issues/10269
vLLM maintainers: submit all requests and let the server scheduler batch internally by KV-cache capacity; client-side `Semaphore(N)` caps in-flight HTTP connections, not server batch size. Bound client concurrency to the pod's `--max-num-seqs`; flooding causes timeouts (related #14365).

## Q4: vLLM OpenAI-compatible `response_format=json_schema` + determinism

**Structured Outputs - vLLM docs** [HIGH]
https://docs.vllm.ai/en/stable/features/structured_outputs/
OpenAI-compatible server supports `response_format={"type": "json_schema", "json_schema": {...}}`. Reasoning+structured-output combo works with `--reasoning-parser`. `guided_json` is deprecated since v0.12.0 in favor of `structured_outputs` / `response_format`. Backend selectable via `--structured-outputs-config.backend`.

**Batch Invariance - vLLM docs** [HIGH]
https://docs.vllm.ai/en/stable/features/batch_invariance/
`temperature=0` and `seed` alone do NOT guarantee deterministic output under continuous batching (batch size and request order change reduction order and can flip token choices). `VLLM_BATCH_INVARIANT=1` gives outputs invariant to batch size/order; ~50% throughput penalty, incompatible with CUDA graphs / torch.compile.

**vllm/entrypoints/openai/completion/protocol.py - ResponseFormat handling** [MED]
https://github.com/vllm-project/vllm/blob/469f3dcf/vllm/entrypoints/openai/completion/protocol.py
Source: the server parses `response_format.type` of text/json_object/json_schema; json_schema maps into `structured_outputs_kwargs` for the constrained-decoding path. Defines the wire contract for OpenAI SDK clients.

**vllm/sampling_params.py - temperature and seed** [MED]
https://github.com/vllm-project/vllm/blob/469f3dcf/vllm/sampling_params.py
`temperature=0` means greedy; `seed` first-class. Structured outputs are orthogonal to sampling: grammar masking constrains logits independently; temperature still picks among legal tokens when >0.

**Structured Output Reliability (The Neural Base vLLM course)** [MED]
https://theneuralbase.com/vllm/learn/intermediate/structured-output-reliability/
Operational guidance: temperature=0 with guided decoding in production. Warns invalid/incomplete JSON schema causes vLLM to SILENTLY fall back to unconstrained generation. Grammar enforcement does not itself guarantee cross-run determinism.

## Q5: Failure modes of retry-with-error-feedback loops

**Why Retrying Fails: Context Contamination in LLM Agent Pipelines (arXiv)** [HIGH]
https://arxiv.org/html/2605.08563v1
Formal model: failed attempts remaining in context raise per-step error rate, causing super-linear reliability decay with pipeline depth. Recommends clean-restart or budget-aware retry depth rather than naive history accumulation.

**pydantic-ai: full history sent on ModelRetry bloats repair context (Issue #4908)** [HIGH]
https://github.com/pydantic/pydantic-ai/issues/4908
After validation failure/ModelRetry the next request includes full accumulated history (invalid outputs + prior turns). Workaround: trim to system prompt + original task + last assistant response + retry feedback.

**Schema validation retry with cross-step learning (awesome-agentic-patterns)** [MED]
https://github.com/nibzard/awesome-agentic-patterns/blob/main/patterns/schema-validation-retry-cross-step-learning.md
Tradeoffs: context bloat, cost/latency, non-guaranteed convergence. Prescribes rolling window of last errors, per-step retry caps, retry-worthy vs escalate-worthy distinction.

**Instructor retry mechanisms and persistent-error limits** [MED]
https://github.com/567-labs/instructor/blob/main/docs/learning/validation/retry_mechanisms.md
Standard error-feedback loop and its ceilings: retry budget burns tokens; some errors are not LLM-fixable. On exhaustion raises with full attempt history for debugging misattribution (model "fixes" the wrong field).

**LLM structured outputs in production (towardsai)** [MED]
https://pub.towardsai.net/llm-structured-outputs-in-production-how-to-stop-json-from-breaking-your-ai-workflow-66703754d341
Failure catalog: blind retries repeating the same broken output, mutation of already-correct fields, schema drift. Recommends targeted repair prompts with exact validation paths, hard retry limits, "same field fails twice -> escalate".
