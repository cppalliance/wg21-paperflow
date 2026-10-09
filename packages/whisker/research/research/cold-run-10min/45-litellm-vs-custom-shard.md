# 45 - LiteLLM vs Custom Dual-Pod Shard

**Verdict:** usable — for identical-model dual-pod (`alliance-pod` + `h200x8-deepseek-v4-pro`), a ~20-line whisker-local pin + per-pod semaphore beats importing LiteLLM; prior 140–144 still holds on a 2026-07-24 re-check.
**Confidence:** high
**Decision:** `custom shard`

## Scope

Fresh look at whether LiteLLM Router is now the right vehicle for dual-pod
sharding of the **same** DeepSeek-V4-Pro weights, or whether persona 21/143's
cli-local shard remains better. Not a re-audit of caching (142) or retry
blueprints (141); those stay "copy patterns, not the package."

## Prior work (re-verified, not rediscovered)

| Note | Load-bearing claim |
|------|--------------------|
| `tapetum-llm-speedup/140` | LiteLLM picks deployment **per request**; tapetum needs **paper-start pin** (all ~6 serial calls on one pod). |
| `tapetum-llm-speedup/143` | Portable primitive is `asyncio.Semaphore` per deployment capped at `--max-num-seqs` (16), not TPM/RPM 429 stacks. |
| `tapetum-llm-speedup/144` | Importing LiteLLM is **garbage** for this lane: dep mass, D1/D5/D6 clash, hidden retry/reroute, 0 s beyond what a local shim gets. |
| `tapetum-llm-speedup/21` | Spec: `--shard-pods`, `live_pods[index % N]`, dual health probe, fingerprint encodes shard **set**. |
| `cold-run-10min/10` | Dual-pod still **not implemented** at HEAD (`cli.py:1193` single `Semaphore(concurrency)`). |

## Findings

- [CRITICAL] **LiteLLM is still a per-request router; our bottleneck is paper-pinned fleet fan-out.** Current docs still list `simple-shuffle` (default, random/weighted), `least-busy`, latency/usage/cost strategies, and `max_parallel_requests` per deployment — all operate at **call** granularity ([LiteLLM routing docs](https://docs.litellm.ai/docs/routing), fetched 2026-07-24). No first-class paper/session affinity that would pin monolith → metadata → page → unit chain to one RunPod URL. Using Router as designed would mid-chain cross pods on retry/cooldown (140 false-fail), breaking prefix-cache locality and adding a second MoE batch axis. Impact: LiteLLM does not shrink the design to our constraint; it fights it. Wall: same dual-pod ceiling as persona 21 (~3003→~1600 s modeled) only if we **disable** its routing brain and pin externally anyway.

- [CRITICAL] **The winning topology is ~20 lines in `cli.py`, already fully specified.** Evidence: single global `sem = asyncio.Semaphore(concurrency)` today (`cli.py:1193`); `_adjudicate_one(index, pid)` already has a stable `index` (`cli.py:1196-1201`). Persona 21+143 recipe: probe both services in `SERVICES.toml:47-74`, build `pod_sems[name] = Semaphore(16)`, assign `pod = live_pods[index % len(live_pods)]`, `async with pod_sems[pod]`, pass `service_overrides` with all slots → that pod. No new dependency. Impact: dual-pod multiplier (~1.9× on post-cut wall) without supply-chain or D1 rewrite. Quality risk: LOW-MED (same weights, fixed pod per paper across reruns; within advisory variance budget, 21:16).

- [HIGH] **Fresh LiteLLM churn does not flip the adopt decision.** Upstream fixed semaphore TTL over-admission (PR #32764: move `max_parallel_requests` off expiring cache onto a plain dict / CapacityLimiter). That makes *their* concurrency limiter more correct for multi-tenant proxies. It does **not** add document affinity, remove default `simple-shuffle`, shrink the 2k-file / heavy lockfile surface (144), or integrate with `pipeline.run_agent` / `VllmThinkingBackend` BPE retries. Impact: **0 s** argument for adopting the package; reinforces "copy the semaphore idea."

- [HIGH] **Putting LiteLLM under `pipeline` or whisker still violates project invariants.** D1 requires `run_agent`/`run_task`; LiteLLM is a parallel `completion`/`Router.acompletion` stack (144). D5/D2 sampling pins and family workarounds live in `model_backends.py`, not in a generic translator. Whisker boundary rule: do not grow `pipeline` for a tapetum fleet scheduler. Impact: custom shard stays in `packages/whisker/.../cli.py` only; LiteLLM would be the wrong layer even if routing were perfect.

- [MED] **Optional least-busy at paper-start remains a whisker-local opt-in, not a reason to import Router.** 140 modeled ~952 s waste when deterministic 50/50 lands on a half-occupied `alliance-pod`. That is still true, and still solved by an in-process in-flight counter at **assignment time** (pin for the whole paper), not by per-call `least-busy`. Impact: if shared-pod contention shows up in A/B, extend the custom shard; do not pull LiteLLM for one counter.

- [LOW] **Neither package nor shim hits ≤10 min alone.** Dual-pod is lever #4 after metadata short-circuit (already live, `00-baseline.md` / `10-impl-status`). Custom shard unlocks the infra half; LiteLLM does not change the arithmetic.

## False-pass hypothesis

Ship LiteLLM Router with `least-busy` + `max_parallel_requests=16`, watch fleet wall drop, and attribute the win to "LiteLLM load balancing" while the real work was two healthy identical pods plus concurrency cap — masking that mid-chain failover and `simple-shuffle` defaults were left armed for the next MoE flip chase.

## False-fail hypothesis

Reject custom shard because "LiteLLM already does this," delay `--shard-pods` another sprint, and leave ~1.9× on the table while HEAD still runs one `Semaphore(concurrency)` against one pod (`10-impl-status.md:14-15`).

## What would change my mind

A thin integration where LiteLLM is used **only** as HTTP fan-out with (1) forced paper-sticky deployment id for the whole adjudicate chain, (2) no mid-chain failover, (3) no sampling/retry ownership, (4) **zero** new transitive deps beyond httpx/openai already in `pipeline`, and a 381-paper A/B beating the custom shard by **≥5% wall** at ≤1.1× single-pod flip rate. No such product exists today; "custom routing strategy" in LiteLLM still means writing the pin yourself inside their framework.

## Decision (return value)

```
custom shard
```

Ship persona 21 + 143 in `cli.py`. Do not add LiteLLM. Steal health-probe and semaphore patterns from 140/143; leave the package out.
