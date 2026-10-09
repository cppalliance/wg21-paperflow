# Executive Brief — Cold-Run ≤10 Min (1 MoE Pod)

**Date:** 2026-07-24 · **Audience:** Ops, Engineering, Decision-makers  
**Product:** Whisker `tapetum-llm`, bare full-fleet cold (381 papers, ~2284 LLM calls)

---

## Situation

Measured: **~48–50 min** cold run on `alliance-pod` (DeepSeek-V4-Pro, max 16 concurrent sequences). Goal: **≤10 min**, with quality-stability (same fused verdicts).

A second V4-Pro pod is **forbidden** (budget/authority). MoE concurrency stays at **16** (32 makes wall time worse).

With the v11 short-circuit already in the tree, expect **~21–25 min** — still far above 10 min. **MoE alone cannot hit 10 min at quality** (front-end alone is already ~948 s).

---

## Blocker (critical)

All dense Alliance endpoints in `SERVICES.toml` return **HTTP 404**:

| Endpoint | Status |
|----------|--------|
| `alliance-pod` (MoE) | **UP** |
| `h200-qwen3-32b` (primary needed) | **404** |
| `b300-qwen36-27b`, `b200x2-gemma4`, `b200-r1` | **404** |

Without a live dense pod, the only ≤10 min path is **infra-blocked**. Policy permission is not enough — the pod must answer.

---

## Options

| | **A — MoE-only** | **B — Heterogeneous (dense)** | **C — SLA reset** |
|---|---|---|---|
| **Promise** | Ship quality stack; **no** ≤10 min claim | ≤10 min via parallel MoE+dense | End the 10 min program |
| **Realistic wall** | ~15–20 min (honest); MODERATE ~23–25 min | ~511 s possible if dense + scoping + parity | ~15–20 min published |
| **Infra today** | `alliance-pod` UP — **shippable** | Dense all 404 — **blocked** | No dense dependency |
| **≤600 s?** | **No** | **Maybe** (design; dead today) | Goal moved |

**If dense restart is uncertain:** build A + use C language (honest SLA). Choose B only with a dated ops commitment.

---

## What Alliance ops must do

**Ask:** Restart endpoint **`h200-qwen3-32b`** until `GET /v1/models` → **HTTP 200**.

- **Why:** Offload ~1500–1800 unit/metadata calls from the shared MoE pod. Only arithmetic ≤10 min design under the twin ban.
- **Not asking for:** a second V4-Pro, raising MoE `max-num-seqs`, exclusive reservation of `alliance-pod`.
- **Do not prioritize as unit judge:** Gemma-4, R1.
- **If no restart:** stop the 10 min program; honest SLA **~15–20 min**.

---

## What the code team can do without infra

Immediate, on `alliance-pod` alone:

1. Remeasure cold on local v11 (truth baseline ~21–25 min).
2. Commit/ship v11 short-circuit.
3. Deterministic metadata (shadow A/B, HTML-first → fleet).
4. Verdict-first schema + router/quota (with holdout gates).
5. Server Tier-1 flags (MBT, CUDA graphs, DeepEP) — not enough alone for 10 min.

**Do not:** propose a twin, S=32, skip monolith, or ship a dense router against dead 404 proxies.

**After dense is UP (ops):** payload scoping → cascade → 381 quality gate (~0.8–1.2 h validation) → only then claim ≤10 min (instrumented ≤620 s + parity).
