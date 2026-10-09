# 27 - Dual-Pod Dependency Rewrite (1-pod substitutes)

**Date:** 2026-07-24  
**Sources:** `research/cold-run-10min/SYNTHESIS.md`, `11-wall-arithmetic.md`, `22-path-a-b-10min.md`, `15-dual-pod-liveness.md`, `67-dual-endpoint-shard-patterns.md`, `45-litellm-vs-custom-shard.md`, `53-multi-gpu-ep.md`, `16-dense-judge-candidates.md`, `research/cold-run-10min-1pod/{00-baseline,12-dense-offload-architecture,18-packages-1pod,17-physics-floor-skeptic,SYNTHESIS-DRAFT}.md`  
**Constraint:** No second DeepSeek-V4-Pro replica. `S_eff = 16` on `alliance-pod` fixed.

---

## Executive summary

`cold-run-10min/SYNTHESIS.md` reached **~596 s (~10 min)** only on **Path A**: MODERATE software levers plus **dual-pod sharding** (S: 16→32). Every other ranked lever (metadata short-circuit, prefix/APC, verdict-first, escalation dedupe, client stalls) works on one pod.

On one MoE pod, MODERATE lands **~1366–1493 s (~23–25 min)**. The missing **~887 s** is almost entirely **parallel MoE slot capacity**, not fixable by raising `--max-num-seqs` to 32 (+57% wall) or widening EP on the existing 8×H200 node.

**1-pod substitute for the dual-pod multiplier:** heterogeneous **dense-judge offload** to already-running Alliance dense endpoints (`h200-qwen3-32b` primary), with **`wall = max(T_dense, T_moe)`**, plus payload scoping and full AGGRESSIVE quality gates. Central estimate **~511–715 s** depending on metadata placement and friction. MoE-only software without dense offload **cannot** hit ≤600 s at quality floor.

---

## Levers that REQUIRED dual-pod (from SYNTHESIS)

These are items where dual-pod was a **hard dependency** for the ≤600 s cold target or for the lever itself to exist. Software levers that merely stacked *with* dual-pod but work alone are listed in §Excluded.

| # | Dual-pod lever (SYNTHESIS) | Wall role | 1-pod substitute | Substitute wall / outcome |
|---|---------------------------|-----------|------------------|---------------------------|
| 1 | **Dual-pod shard** (lever #4, `00-baseline.md:35`) | S: 16→32; halves compute term | **Dense hetero offload** (`12-dense-offload-architecture.md`): route ~1879 calls to `h200-qwen3-32b`, keep ~428 on MoE; per-pod semaphores; `max(T_dense, T_moe)` | **~511 s** central (MoE-bound) if scoping + 2× dense decode; **~620–715 s** if metadata stays on MoE at L=20 |
| 2 | **Twin pod `h200x8-deepseek-v4-pro` liveness** (`SYNTHESIS.md:20`, Day 3) | Second identical V4-Pro replica | **IMPOSSIBLE** under operator ban. Functional equivalent = row 1 (different model, not replica) | N/A |
| 3 | **`--shard-pods alliance-pod,h200x8-deepseek-v4-pro`** (`SYNTHESIS.md:40,129`; missing at HEAD) | Paper-pinned split across two MoE schedulers | **Call-class service router** in tapetum: monolith/page/oversize → MoE; units+metadata → dense (`12` §Recommended routing) | Same as row 1; not paper-hash shard |
| 4 | **Per-pod `Semaphore(16)` × 2 → S_eff=32** (`22-path-a-b-10min.md:42`, `67:47`) | 32 in-flight MoE decodes fleet-wide | **MoE `Semaphore(16)` + dense `Semaphore(32–48)`** on separate endpoints (`12` §Scheduling rule) | Parallel capacity via **heterogeneous queues**, not doubled MoE slots |
| 5 | **Pre-gather dual health probe** (`15-dual-pod-liveness.md`, Day 3) | Filter dead twin before shard | **Per-endpoint liveness** for MoE + chosen dense pod before fleet; shrink routing set on failure | Dense-only fallback degrades to MoE-only (**~1366 s** class), not 404 storm |
| 6 | **`blake2b(pid) % N` paper sticky routing** (`67-dual-endpoint-shard-patterns.md`) | Prefix-cache locality per paper on one MoE instance | **Sticky by call class**, not PID hash: all unit calls for a paper go to dense; monolith chain stays on MoE. Prefix locality on dense for unit user-block reorder | Different affinity unit; same intent (reuse KV within call class) |
| 7 | **Custom cli.py shard (~20 LOC, not LiteLLM)** (`45-litellm-vs-custom-shard.md`) | MoE fan-out without mid-chain failover | **Same LOC budget, different map:** `_adjudicate_one` selects service by `call_type` + token preflight, not `shard_pod(pid, live_pods)` | Reuse semaphore/health patterns; change assignment function |
| 8 | **Manual two-process PID split** (`15-dual-pod-liveness.md:12`, `18-load-splitter.md`) | Zero-code dual-pod when twin alive | **IMPOSSIBLE** while twin 404. With dense: single process, two service endpoints | N/A without live second MoE URL |
| 9 | **Fingerprint encodes shard SET** (`67:49`, `21-dual-pod-sharder`) | Warm skip invalidates on dual↔single toggle | **Fingerprint encodes routing profile:** `{moe: alliance-pod, dense: h200-qwen3-32b, lane_version}` | Required on any default service change |
| 10 | **MODERATE package ≤600 s** (`SYNTHESIS.md:19,33`, `11-wall-arithmetic.md:97-98`) | Planning central **596 s** only at S=32 | **IMPOSSIBLE** at MODERATE on one MoE pod (**~1366 s**). Substitute = row 1 + MODERATE N/L levers (Package C in `SYNTHESIS-DRAFT.md`) | **~476–550 s** sketch with det-metadata + offload; needs validation |
| 11 | **CONSERVATIVE package ≤600 s** (`11-wall-arithmetic.md:99`) | Even with dual-pod, **~945 s** central | **IMPOSSIBLE** for 10 min at any pod count without call elimination | Single-pod CONSERVATIVE **~2163 s** |
| 12 | **Path A execution plan** (`SYNTHESIS.md:52-60`, `22:144-152`) | Ordered path to 9–11 min | **Package C heterogeneous** (`SYNTHESIS-DRAFT.md` §Packages): v11 + det-metadata + verdict-first + dense offload + gates | **Maybe** ≤600 s; not Path A arithmetic |
| 13 | **Compute-term halving (~887 s on N_rem=1419)** (`22:138`, `18-packages-1pod.md:176`) | `1419×20/32` vs `/16` | **Attack L and queue split, not S:** dense 2× decode on 82.6% of calls + eliminate 377 metadata LLM calls (det diff **−471 s**) + keep monolith on MoE (**~476 s** floor) | MoE monolith queue often **binds** wall |
| 14 | **Second live DeepSeek endpoint** (`SYNTHESIS.md:70-72`, Path B option 1) | Same as twin shard | **IMPOSSIBLE** (operator: no budget/authority for second V4-Pro) | N/A |
| 15 | **Hardware uplift 8×H200 DP+EP on one node** (`SYNTHESIS.md:72`, `53-multi-gpu-ep.md`) | Misread as "add GPUs to one pod" | **IMPOSSIBLE as S substitute:** `alliance-pod` already **8×H200 TP8+EP**. Wider EP does not double `S_eff`; at best modest L cut, still **~1000 s+** after MODERATE | N/A |
| 16 | **`--max-num-seqs 32` on one MoE pod** (forbidden twin substitute) | Would raise S on one scheduler | **IMPOSSIBLE** — measured **+57% wall** (`00-baseline.md:27`, `slots-32-regression`) | Forbidden |
| 17 | **LiteLLM Router dual deployment** (`45-litellm-vs-custom-shard.md`) | Per-request load balance across pods | **IMPOSSIBLE for 10 min** — no paper affinity; D1 clash. **Not a substitute** for custom shard or dense router | Use call-class router in whisker |
| 18 | **Verdict-identity check across pods** (`SYNTHESIS.md:144`) | Quality gate when two MoE replicas | **381/381 fused parity** dense vs MoE teacher (`12` §Quality gate) | Different test; same fail-closed bar |

---

## Substitute stack (recommended 1-pod rewrite of Path A)

Replace Day 3 (twin + shard) with:

| Step | Dual-pod SYNTHESIS | 1-pod rewrite |
|------|-------------------|---------------|
| Infra | Revive twin + `--shard-pods` | Confirm `h200-qwen3-32b` (or pilot `b300-qwen36-27b`) live; **no** second V4-Pro |
| Parallelism | S_eff=32 MoE | `max(T_moe, T_dense)` with MoE S=16, dense S=32–48 |
| Code | `shard_pod(pid, live_pods)` | Payload scoping → service router by call class |
| Quality | Cross-pod verdict drift check | 381/381 parity + equivalence vector (`25-quality-gate-protocol.md`) |
| Expected wall | **~596 s** central (MODERATE + dual) | **~511 s** central optimistic (`12` Scenario C); **~715 s** with friction (`18-packages-1pod` AGGRESSIVE realistic) |

**Still ship on one pod (unchanged from SYNTHESIS):** metadata Tier A+B, HMAC/prefix, escalation dedupe, verdict-first, LJF, `to_thread`, tombstones, server ops flags.

---

## IMPOSSIBLE substitutes (do not pursue for 10 min)

| Attempted substitute | Why IMPOSSIBLE |
|---------------------|----------------|
| Revive `h200x8-deepseek-v4-pro` | Operator forbidden |
| Second identical V4-Pro replica (any name) | Same as twin ban |
| `--max-num-seqs 32` on one MoE pod | +57% wall regression |
| Client `c>32` | Proxy 524 / TTFT risk |
| Wider EP / multi-node single replica | Does not double S; alliance already EP8; **~1000 s+** after MODERATE (`53`) |
| MODERATE software only on one MoE pod | **~1366 s** floor (`17-physics-floor-skeptic.md`) |
| MoE-only AGGRESSIVE without dense | **~715–910 s** realistic (`18-packages-1pod`) |
| LiteLLM as shard vehicle | Per-request routing; no paper pin; wrong layer (`45`) |
| Manual two-process MoE split | Blocked while twin 404 |

---

## Excluded (did NOT require dual-pod)

These appear in SYNTHESIS Path A but **work on one pod**; they are not dual-pod dependencies:

- Metadata Tier A+B short-circuit (−847 calls)
- HMAC guard tag + unit user-block reorder / APC
- Escalation dedupe (−18 calls)
- Verdict-first / terse pass schema
- Error tombstone fingerprints
- LJF, `asyncio.to_thread`, monolith `wait_for`
- Per-call sidecar timings (instrumentation)
- Server ops flags (MBT 16384, tokenizer/reasoning parsers, DeepEP/DBO A/B)
- MTP k=1 (optional upside, not dual-dependent)
- Deterministic metadata diff (AGGRESSIVE; orthogonal)
- Router combo_safe (AGGRESSIVE; orthogonal)

---

## Return: list of substitutes

| Dual-pod requirement | 1-pod substitute |
|---------------------|------------------|
| Dual-pod shard / S=32 | **Dense hetero offload** to `h200-qwen3-32b` + call-class router + `max(T_dense,T_moe)` |
| `--shard-pods` CLI | **Service router by call type** (~same LOC site in `cli.py`) |
| Per-pod Semaphore(16)×2 | **MoE Semaphore(16) + dense Semaphore(32–48)** |
| Twin health probe | **MoE + dense endpoint probes**; route to survivors |
| PID hash sharding | **Call-class routing** (units/metadata→dense, monolith→MoE) |
| MODERATE ≤600 s | **Package C:** MODERATE + dense offload + det-metadata + quality gates |
| ~887 s compute halving | **Dense 2× decode on 82.6% calls** + **−471 s** det-metadata + MoE monolith binding |
| Path A ≤10 min plan | **SYNTHESIS-DRAFT Package C** heterogeneous |
| Cross-pod verdict check | **381/381 dense vs MoE parity** |
| Second V4-Pro endpoint | **IMPOSSIBLE** |
| Twin revival | **IMPOSSIBLE** |
| max-num-seqs 32 / c>32 | **IMPOSSIBLE** |
| Wider EP on one node | **IMPOSSIBLE** (already 8×H200; no S gain) |
| MODERATE alone ≤600 s | **IMPOSSIBLE** |
| LiteLLM router | **IMPOSSIBLE** (use custom call-class router) |
| Manual two-process MoE split | **IMPOSSIBLE** (twin dead) |

---

## False-pass / false-fail

**False-pass:** Implement `--shard-pods` against a dead twin; half the fleet 404s or all traffic falls back to one pod → **~1366 s** while blaming MODERATE levers.

**False-fail:** Conclude "10 min impossible" without dense offload → miss **~511 s** class arithmetic when dense pods are already in `SERVICES.toml` and paid for.

---

## What would change this

1. Operator restores twin → revert to `cold-run-10min/SYNTHESIS.md` Path A; MODERATE **~596 s** without dense validation burden.
2. Instrumented Package C cold run **≤620 s** with 381/381 parity → upgrade heterogeneous path to ✅.
3. Measured MODERATE **≤650 s** on one MoE pod → model error; revisit (unlikely per `17-physics-floor-skeptic`).
