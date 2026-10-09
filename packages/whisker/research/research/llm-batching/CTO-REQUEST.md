# Pod requests: batch throughput for the whisker advisory lane

> **ANSWERED by CTO, 2026-07-07.** There is only ONE pod
> (`https://sgjy18glyi4blu-8000.proxy.runpod.net`); the
> `h200x8-deepseek-v4-pro` entry in SERVICES.toml is stale and its 404 is
> expected. Launch parameters are published at
> https://github.com/cppalliance/runpod/blob/master/templates/deepseek/H200SXM.txt
> Key facts: vLLM image `cppalliance/vllm-openai:v0.24.0`,
> `--max-num-seqs 16`, `--max-model-len 393216`, `--kv-cache-dtype fp8`,
> `--gpu-memory-utilization 0.95`, `--reasoning-parser deepseek_v4`,
> tool-call parser `deepseek_v4`, expert parallelism on. Prefix caching is
> not explicitly disabled, so vLLM V1's default-on applies.
> Consequences applied: client `_DEFAULT_CONCURRENCY` raised to 16 (matches
> the scheduler cap); dual-pod sharding cancelled (no second pod);
> structured output remains possible (reasoning parser is configured).
> The original request text below is kept for the record.

We parallelized our advisory LLM batch runs (200 papers: 36 min -> minutes).
Three server-side items would help us further; all are your call, we only
consume the API.

1. **Twin pod is down.** `h200x8-deepseek-v4-pro`
   (`https://w80putgan2qou8-8000.proxy.runpod.net`) returns HTTP 404 on all
   paths (including `/v1/models`) while `alliance-pod` is healthy. If it is
   meant to be retired, tell us and we drop it from SERVICES.toml; if not, a
   restart gives us a free 2x by sharding papers across both pods.

2. **What is `--max-num-seqs` on alliance-pod?** Our sweep shows the pod
   absorbs at least 20 concurrent requests with stable ~30 s per-request
   latency (zero errors at 32 in flight). Knowing the configured value lets
   us pin the client concurrency ceiling instead of guessing.
   Reference: https://docs.vllm.ai/en/stable/configuration/optimization/

3. **Prefix caching + reasoning parser status.** Is
   `enable_prefix_caching` active (default-on in vLLM V1), and which
   `--reasoning-parser` is set? All our requests share an identical ~8 KB
   system prompt (prefix-cache friendly), and we may adopt structured
   output (`response_format: json_schema`, xgrammar), which needs the
   reasoning parser configured for DeepSeek-V4-Pro.
   References:
   - https://docs.vllm.ai/en/stable/features/structured_outputs/
   - https://docs.vllm.ai/en/v0.24.0/features/reasoning_outputs/

Optional, only if we ever need bit-stable regression baselines: a
batch-invariant mode costs ~50% throughput and is not needed for normal
advisory runs.
