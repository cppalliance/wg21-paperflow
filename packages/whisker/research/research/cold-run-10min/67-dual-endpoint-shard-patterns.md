# 67 - Dual-Endpoint Shard Patterns

**Verdict:** usable — for **381 papers / 2 identical pods**, prefer **PID-keyed hash modulo** (`blake2b(pid) % len(live_pods)` over lexicographically sorted healthy names); rings/vnodes are overkill at N=2; enumerate-index round-robin is acceptable only for full sorted fleet runs.
**Confidence:** high

## Research question

What do web/GitHub LLM routers use for **deterministic sticky routing** across identical OpenAI-compatible endpoints (session / document affinity), and what is the simplest **asyncio client-side** design for whisker fleet dual-pod (`alliance-pod` + `h200x8-deepseek-v4-pro`)?

## Recommended algorithm (381 × 2)

**Use: document-id sticky hash modulo.**

```python
import hashlib

def shard_pod(pid: str, live_pods: list[str]) -> str:
    """Deterministic paper → pod. live_pods already health-filtered."""
    pods = sorted(live_pods)  # membership order must not depend on CLI arg order
    digest = hashlib.blake2b(pid.encode("utf-8"), digest_size=8).digest()
    return pods[int.from_bytes(digest, "big") % len(pods)]
```

| Property | Value for 381 / 2 |
|----------|-------------------|
| Balance (synthetic P0001R0… style IDs) | blake2b % 2 → ~187/194 (skew ≤7); md5 % 2 → 192/189 |
| Stickiness key | **paper id** (not request index, not HTTP body hash) |
| Membership change | if one pod dies → `live_pods=[survivor]` → all papers remapped (correct) |
| Asyncio fit | pure function inside `_adjudicate_one`; no ring state, no sticky map |
| Prefix-cache locality | all calls for one paper (fast+deep+default) share one pod |
| Warm / subset runs | same PID → same pod even if CLI PID list is reordered or partial |

**Do not use for this fleet:** vnode consistent-hash rings, cache-aware / LMCache routers, power-of-two load pickers, or random per request.

**Acceptable alternative (full fleet only):** `sorted(pids)` then `live_pods[i % N]` (prior `21-dual-pod-sharder.md`). Reject for explicit-PID / subset reruns: list order changes ownership.

---

## Findings

- [HIGH] **Industry pattern for sticky LLM backends is hash-by-session-id, not per-request RR.** [vllm-router load-balancing](https://github.com/bet0x/vllm-router/blob/main/docs/load-balancing.md) lists `consistent_hash` (ring + 160 vnodes) and `rendezvous_hash` (HRW) for session affinity / KV reuse; `round_robin` / `random` / `power_of_two` are for **stateless** batch with no affinity. Tapetum's affinity unit is the **paper** (multi-call monolith + units + optional deep), so map `pid` → worker the way routers map `x-session-id` → worker. Impact: stickiness preserves per-paper prefix-cache locality on one vLLM instance; RR-per-call would thrash both pods.

- [HIGH] **At N=2 fixed homogeneous pods, hash(key) % N equals the useful part of consistent hashing; rings add complexity without payoff.** Ring/vnode designs (e.g. [context-ring](https://github.com/david-spies/context-ring), vllm-router `consistent_hash`) minimize remapping when **membership grows**. Our membership is two named RunPod proxies that are either both up or filtered to one via health probe (`15-dual-pod-liveness.md`, `21-dual-pod-sharder.md`). Adding a third identical replica is rare; when it happens, remapping ~50% of keys once is fine for an advisory cold fleet. Impact: ~5-line modulo beats ~50-line ring for this ops shape.

- [HIGH] **Rendezvous / HRW is the right upgrade path if pod count grows, not the day-1 choice.** HRW scores `hash(f"{pid}|{pod}")` and picks max; O(N) per route, zero ring state ([vllm-router `rendezvous_hash`](https://github.com/bet0x/vllm-router/blob/main/docs/load-balancing.md), [proxenos](https://github.com/darvid/proxenos), turnstone design notes). For N=2 and 381 keys, HRW balance is fine but slightly worse skew in a quick synthetic check (197/184) and more code than `% 2`. Prefer HRW only if operators routinely toggle 2↔3+ identical replicas and want minimal key movement. Impact: keep modulo now; document HRW as N≥3 follow-on.

- [HIGH] **Simple asyncio design: one process, shared semaphore, per-paper service map — no proxy process.** Prior art already scoped this to `cli.py` only (`18-load-splitter.md`, `21-dual-pod-sharder.md`): health-filter → `live_pods`; in `_adjudicate_one` after `async with sem:` set `pod = shard_pod(pid, live_pods)` and `per_paper = {**overrides, "fast": pod, "deep": pod, "default": pod}`; keep `asyncio.gather` + existing concurrency (32 fills ~16 in-flight per pod when split). Zero-code fallback: two CLI processes with disjoint PID lists and `--service` overrides. Impact: ~15–25 LOC; no sidecar router (nexus-llm-router / context-ring) required for a batch client.

- [MED] **Index-parity RR is deterministic only under a stable sorted full list.** `live_pods[enumerate_index % N]` on `sorted(list_all_paper_ids())` is stable for cold full fleets (`21-dual-pod-sharder.md:10`) and balances 191/190. It **reshards** when operators pass an explicit subset or unsorted PID argv. Hash-by-pid does not. Impact: prefer hash-by-pid for fingerprint-stable ownership across warm/partial reruns; fingerprints should encode the **shard SET**, not the per-paper pod (`21-dual-pod-sharder.md:14`).

- [MED] **Dead-pod fallback must shrink membership before hashing, not walk a ring after assign.** vllm-router walks the ring on unhealthy sticky targets; our client should probe both pods pre-gather and hash only over `live_pods` (0 → exit, 1 → all traffic, 2 → split). Impact: avoids ~190 `error` tombstones from half-dead RR (`15-dual-pod-liveness.md`, `18-load-splitter.md`).

- [LOW] **Cache-aware / LMCache-aware routing is the wrong layer for fleet paper sharding.** Those policies optimize **request prefix** locality across many short chats ([vllm-router](https://github.com/bet0x/vllm-router/blob/main/docs/load-balancing.md)). Our locality is already enforced by binding an entire paper to one pod; APC reuse is intra-paper serial calls on that pod. Impact: do not pull cache_aware into `cli.py`.

## Pattern comparison (client-side, identical models)

| Algorithm | Sticky by doc? | Balance @ 381/2 | Code size | When membership drops 2→1 | Prefer? |
|-----------|----------------|-----------------|-----------|---------------------------|---------|
| **`blake2b(pid) % N`** | Yes | ~187–194 | ~5 LOC | All → survivor | **Yes (recommended)** |
| Sorted-index `i % N` | Yes iff full sorted list | 191/190 | ~3 LOC | All → survivor if rehash over live | Full fleet only |
| HRW / rendezvous | Yes | ~184–197 | ~15 LOC | Minimal remap if N>2 | N≥3 later |
| Ring + vnodes | Yes | Excellent at scale | ~50+ LOC | Walk / rebuild | Router proxy, not batch CLI |
| Per-request RR / random | No | Even requests, not docs | trivial | n/a | Forbidden (breaks paper affinity) |
| Power-of-two / least-load | No | Load-sensitive | needs metrics | n/a | Forbidden (non-deterministic) |

## Minimal asyncio sketch (whisker-shaped)

```python
# pre-gather (once)
live = [name for name in sorted(shard_pods) if await healthy(name)]
if not live:
    sys.exit(1)

async def _adjudicate_one(pid: str) -> ...:
    async with sem:
        pod = shard_pod(pid, live)
        per_paper = {**overrides, "fast": pod, "deep": pod, "default": pod}
        return await adjudicate_paper(pid, ..., service_overrides=per_paper)

await asyncio.gather(*(_adjudicate_one(pid) for pid in pids))
```

No shared mutable shard state beyond the immutable `live` tuple. No sticky session map. No bisect ring.

## False-pass hypothesis

Hash-by-pid looks "more production" than index RR, so operators skip the dual health probe; one pod 404 still maps half the PID space to a dead name if `live_pods` is not filtered → mass errors misread as conversion failures (same failure mode as unfiltered RR).

## False-fail hypothesis

Operator expects bit-identical advisory verdicts vs single-pod baseline; dual instances add a second MoE/batch variance axis (`18-load-splitter.md:24`). Assignment algorithm is innocent; the false "fail" is quality-stability expectations that the advisory lane already does not promise.

## What would change my mind

A third identical DeepSeek-V4-Pro replica joining the cold fleet regularly, or measured skew >20 papers (≈5%) under real PID strings with blake2b % 2. Then switch recommendation to HRW over sorted live names.

---

## Sources

- [bet0x/vllm-router load-balancing.md](https://github.com/bet0x/vllm-router/blob/main/docs/load-balancing.md) — policy matrix: consistent_hash, rendezvous_hash, RR, cache_aware
- [david-spies/context-ring](https://github.com/david-spies/context-ring) — asyncio + mmh3 + vnode ring for session sticky agents
- [Francis1998/nexus-llm-router](https://github.com/Francis1998/nexus-llm-router) — asyncio/httpx sticky-session = consistent-hash of session_id
- [darvid/proxenos](https://github.com/darvid/proxenos) — Python HRW toolkit
- Prior in-repo: `research/tapetum-llm-speedup/21-dual-pod-sharder.md`, `packages/whisker/research/llm-batching/18-load-splitter.md`, `research/cold-run-10min/15-dual-pod-liveness.md`
