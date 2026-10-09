# 143 - litellm-Concurrency-Limits

**Verdict:** usable-with-conditions — LiteLLM's per-deployment `asyncio.Semaphore` (not its proxy TPM/RPM 429 stack or usage-based routing) is the portable primitive for dual-pod tapetum-llm; enforce one semaphore per pod capped at `--max-num-seqs` (16) plus deterministic paper→pod pinning in `cli.py`, skip token-budget dispatch entirely on uptime-billed MoE pods.
**Confidence:** high

## Findings

- [CRITICAL] **LiteLLM bounds concurrency with one `asyncio.Semaphore` per deployment, acquired for the whole outbound call.** `InitalizeCachedClient.set_max_parallel_requests_client` reads `litellm_params.max_parallel_requests` / `rpm` / `tpm`, calls `calculate_max_parallel_requests`, and stores `asyncio.Semaphore(calculated_max_parallel_requests)` in the router cache keyed by deployment id (`litellm/router_utils/client_initalization_utils.py:16-35`). Every async completion path wraps the in-flight HTTP task in `async with rpm_semaphore` before awaiting the response (`litellm/router.py:2823-2839`, same pattern at `:3749-3758`, `:3855-3858`, etc.). **Queueing behavior:** semaphore saturation blocks the caller (FIFO wait), it does not return 429. Impact: port as `pod_sems[pod_name] = asyncio.Semaphore(16)` in `cli.py`, acquired inside `_adjudicate_one` after paper→pod assignment; **~100-300 s** saved vs a lone global `asyncio.Semaphore(32)` under completion-order skew (`22-multi-pod-fleet-designer.md:14`, `00-baseline.md:24-25`); **quality risk: LOW** (same model, fixed pod per paper).

- [CRITICAL] **Dual-pod semaphore topology: split 16/16 per pod, not c=32 per pod and not one undifferentiated global pool.** LiteLLM treats each backend endpoint as a deployment with its own semaphore budget; `calculate_max_parallel_requests` resolves the cap per deployment independently (`litellm/utils.py:4441-4481`, priority `max_parallel_requests > rpm > int(tpm/1000*6) > default_max_parallel_requests`). Our pods run `--max-num-seqs 16` (`00-baseline.md:66`); client default `_DEFAULT_CONCURRENCY = 32` already targets ~2× server slots fleet-wide (`cli.py:127`, `cli.py:1112-1120`). Concrete whisker topology (no router import):

  ```
  live_pods = sorted(probed_healthy_shard_pods)          # e.g. alliance-pod, h200x8-...
  pod_cap = 16                                           # match vLLM --max-num-seqs
  pod_sems = {p: asyncio.Semaphore(pod_cap) for p in live_pods}
  fleet_cap = pod_cap * len(live_pods)                   # 32 when both live

  async def _adjudicate_one(index, pid):
      pod = live_pods[index % len(live_pods)]            # persona-21 pin
      async with pod_sems[pod]:                          # LiteLLM deployment semaphore
          ... adjudicate_paper(..., service_overrides={**overrides, "fast": pod, ...})
  ```

  Replace the current single `sem = asyncio.Semaphore(concurrency)` (`cli.py:1112`) with per-pod semaphores; keep `--concurrency` as `min(args.concurrency, fleet_cap)` guard only. Impact: **~3003 s → ~1600 s** when both pods fill evenly (`21-dual-pod-sharder.md:8`); **quality risk: LOW-MED** (MoE batch-neighbor variance, same as single-pod reruns).

- [HIGH] **`max_parallel_requests` is the knob that maps to vLLM scheduler slots; rpm/tpm are fallbacks for cloud quotas.** Resolution order and Azure TPM→parallel heuristic: `litellm/utils.py:4461-4477` (`tpm/1000*6` RPM equivalent). Tests confirm semaphore `_value` equals explicit `max_parallel_requests` when set (`tests/local_testing/test_router_max_parallel_requests.py:99-106`, `:45-67`). For self-hosted DeepSeek pods with no API quota, set explicit `max_parallel_requests=16` equivalent in whisker (the semaphore init value), not derived TPM. Impact: prevents over-admitting >16 concurrent requests per pod (measured +60% wall at server 32 slots, `00-baseline.md:82`); **quality risk: none**.

- [HIGH] **LiteLLM has two limit semantics: router semaphore = queue; proxy/router TPM-RPM enforcement = reject (429).** Router: blocking wait on `asyncio.Semaphore` (`litellm/router.py:2828-2839`). Proxy `parallel_request_limiter_v3`: `should_rate_limit` returns `OVER_LIMIT` → `_handle_rate_limit_error` raises `ProxyRateLimitError` (429), no client-side queue (`litellm/proxy/hooks/parallel_request_limiter_v3.py:2422-2434`, `:2284-2320`). Router `ModelRateLimitingCheck` likewise raises `RateLimitError` on exceeded TPM/RPM minute counters (`litellm/router_utils/pre_call_checks/model_rate_limit_check.py:169-187`, `:250-269`). Whisker should copy the **semaphore queue** pattern only; 429-and-retry would add tail latency and cross-pod retry risk (`litellm/router.py:6486-6502`). Impact: **0 s** if wrongly copied; **quality risk: MED-HIGH** if 429 triggers mid-chain pod switch.

- [HIGH] **Per-request TPM routing (`usage-based-routing-v2`) is for quota-spread across deployments, not MoE slot fairness on pinned papers.** `LowestTPMLoggingHandler_v2._return_potential_deployments` picks the deployment with lowest current-minute TPM among those where `current_tpm + input_tokens <= tpm_limit` and RPM headroom remains (`litellm/router_strategy/lowest_tpm_rpm_v2.py:322-367`, `:396-398`). Post-call, TPM counters increment by `total_tokens` (`:297-301`). ITPM/OTPM adds pre-call reservation of estimated input + max output tokens with post-call reconcile (`litellm/router_utils/pre_call_checks/io_token_rate_limit_check.py:391-449`, `:522-558`). **Not worth porting for tapetum-llm:** pods are uptime-billed, not token-metered (`00-baseline.md:65-66`); within one paper all calls are serial (`00-baseline.md:36-38`), so monolith cannot starve unit checks on the same paper; paper→pod pin removes per-call deployment pick. Cross-paper "big monolith vs small unit" imbalance is a **server slot / prefill batch-composition** problem, not an API TPM budget problem. Impact: **~0-120 s** best case vs parity shard (`22-multi-pod-fleet-designer.md:8`); **quality risk: MED** (runtime-dependent routing). Skip.

- [MED] **`least-busy` in-flight counter routing is redundant once paper index pins pod.** Increments per deployment id on pre-call, decrements on success/failure (`litellm/router_strategy/least_busy.py:41-46`, `:63-70`, `:160-188`). Useful only for dynamic per-call load spread; conflicts with quality-stability when combined with `simple-shuffle`'s `random.choice` (`litellm/router_strategy/simple_shuffle.py:59-68`, `22-multi-pod-fleet-designer.md:18`). Impact: **≤120 s** marginal vs deterministic shard; **quality risk: MED** for determinism.

- [MED] **LiteLLM pre-call RPM check inside the semaphore still increments RPM atomically before the HTTP call completes** (`litellm/router_strategy/lowest_tpm_rpm_v2.py:60-117`; router wraps semaphore + `async_routing_strategy_pre_call_checks` at `litellm/router.py:2834-2837`). Whisker has no RPM quota; the analog is "one in-flight LLM chain slot per paper per pod," already enforced by serial within-paper calls plus per-pod semaphore. Impact: **N/A**; **quality risk: none**.

- [LOW] **Proxy TPM reservation (`parallel_request_limiter_v3` `reserve_tpm_tokens`, `tpm_reservation_enabled`) prevents concurrent under-count bursts on shared Redis counters** (`litellm/proxy/hooks/parallel_request_limiter_v3.py:2456-2473`, `:2405-2414`). Relevant only for multi-tenant proxy with `tokens_per_unit` descriptors. Whisker CLI has no shared counter layer. Impact: **0 s**; **quality risk: none** if omitted.

## False-pass hypothesis

**Global `Semaphore(32)` without per-pod caps during dual-pod rollout:** ~190 long-chain papers pile onto `alliance-pod` while `h200x8` idles. Wall drops modestly (~2200 s, not ~1600 s), operator reads success, but one pod runs at persistent queue depth >16, inflating per-call latency via MoE batch contention and raising zero-defect pass rates on that pod (`00-baseline.md:29-30`) while the underloaded pod would have flagged defects — advisory recall drops without deterministic lane noticing.

## False-fail hypothesis

**Porting LiteLLM TPM pre-call rejection for "fairness":** monolith call estimates ~80k input tokens, passes ITPM reservation (`io_token_rate_limit_check.py:414-422`); subsequent unit checks on the same paper hit 429 when minute counter is hot, `_write_error_tombstone` fires (`cli.py:1382-1387`), paper marked `error` despite healthy conversion — false operational failure, ~120 s × N warm retries.

## What would change my mind

A 381-paper cold A/B where (A) per-pod `Semaphore(16)` + index parity shard and (B) a whisker-local token-weighted scheduler (monolith weighted 4× unit check at dispatch time, still paper-pinned, no cross-pod mid-chain retry) shows wall **≥5% below** (A) **and** borderline verdict-flip rate **≤1.1×** single-pod baseline would upgrade token-budget dispatch to **usable-with-conditions**. Without that, ship semaphores only.
