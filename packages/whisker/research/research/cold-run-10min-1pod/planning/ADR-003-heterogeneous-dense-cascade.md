# ADR-003: Heterogeneous dense cascade (MoE monolith + dense units)

**Status:** Blocked — dense pod restart required (all four dense services return HTTP 404 on `/v1/models` as of 2026-07-24; see `26-dense-pod-liveness.md`).

**Date:** 2026-07-24

---

## Context

Cold fleet today is single-queue on `alliance-pod` (DeepSeek-V4-Pro, S_eff=16): ~2284 LLM calls, ~3003 s wall. A second V4-Pro replica is out of scope. Already-declared open-weight dense endpoints in `SERVICES.toml` are in scope for offload.

Unit checks (~1510) plus optional metadata (~377) are the high-volume, bounded-payload lane. Monolith / HTML tier-1 (~381) need full-document context (393k) and stay on MoE.

Judge literature supports cheap-first escalate (Jung Cascaded Selective Evaluation, FrugalGPT, AutoMix): dense first for units, Pro on abstain / invalid schema / low confidence / oversize. Fleet wall is not the sum of both pods:

```
T_pod = Σ(N_i × L_i) / S_pod
wall  = max(T_moe, T_dense) + T_client
```

At 70% fleet offload @ 2× decode, wall is MoE-bound ~856 s and misses ≤600 s. Full unit+metadata offload (~82.6%) with scoped 2× targets ~511 s (still MoE-bound, fragile).

---

## Decision

Adopt a **heterogeneous cascade**, not a second MoE pod:

| Tier | Service | Workload |
|------|---------|----------|
| T0 (future) | CPU | Deterministic metadata short-circuit when landed |
| T1 | Dense primary (`h200-qwen3-32b`) | Unit checks (scoped md); optionally metadata |
| T2 | `alliance-pod` | Monolith, HTML tier-1, page escalation, oversize units, unit escalate band |

Routing targets from architecture census:

- **MoE:** ~428 calls (381 first-pass + ~16 page esc + 8 oversize units + ~23 tier-2).
- **Dense:** ~1879 calls (~1502 in-budget units + 377 metadata) when full offload lands.

Scheduling: client per-pod semaphores — MoE `Semaphore(16)`, dense `Semaphore(32–48)` after payload scoping. Wall = `max(T_moe, T_dense)`.

Unit escalate → Pro if any of: invalid/missing schema fields; confidence &lt; λ (calibrate for escalate ≈10–20% of units); empty defect quote on non-pass; dense timeout/5xx after one dense retry; oversize for dense context (skip T1).

Do not use ABC multi-dense jury on every unit (latency). Do not raise MoE `--max-num-seqs` above 16.

---

## Consequences

**Positive**

- Removes ~82% of LLM calls from the MoE queue without a twin V4-Pro.
- At scoped 2× unit decode, central heterogeneous wall ~511 s (Scenario A); band ~510–710 s if metadata stays on MoE at L=20 s.
- Literature cascade shape (78–87% judge-cost cut class) maps to "most easy units never touch Pro," while monolith remains authoritative.

**Negative / constraints**

- 70% offload alone is insufficient (~856 s). Need ~82.6% (units+metadata) and/or MODERATE call cuts for ≤600 s margin.
- Escalate fraction must stay small; at ~30% unit escalate, Pro queue can push wall above 600 s.
- Semantic lane change: requires 381/381 fused-verdict A/B and `_LANE_VERSION` bump before ship.
- Today: **zero dense pods live** — decision cannot be piloted or benched until restart.

---

## Evidence

| Claim | Source |
|-------|--------|
| `wall = max(T_moe, T_dense)` | `20-heterogeneous-wall.md`, `105-vllm-dense-judge-throughput.md` |
| 70% @ 2× → ~856 s MoE-bound | `20-heterogeneous-wall.md` Scenario A |
| Full units+metadata @ 2× → ~511 s | `12-dense-offload-architecture.md` Scenario A; `20` Scenario B |
| Routing split ~428 MoE / ~1879 dense | `12-dense-offload-architecture.md` |
| Cascade: monolith=Pro, units=dense | `05l-web-cascade-papers.md` |
| Jung escalate-on-low-conf; target escalate ≤15% | arXiv:2407.18370 via `05l` |
| Dense pods 0/4 UP (404) | `26-dense-pod-liveness.md` (2026-07-24 probe) |
| `alliance-pod` control UP | `26-dense-pod-liveness.md` |

---

## Open blockers

1. **Dense pod restart (hard):** At least `h200-qwen3-32b` must return 200 on `/v1/models` and complete a unit-check smoke. Until then this ADR stays **Blocked**.
2. **Payload scoping** (ADR-004): without scoped ~10–15k unit payloads + FP8 KV, dense stays S≤16, L≈20 s → negative EV.
3. **381/381 A/B parity** vs all-Pro baseline (equivalence vector + zero-defect cohort + MoE fallback for 8 oversize papers).
4. **Escalate-rate calibration:** λ such that escalate ≤15–20% while holding fused-verdict parity.
5. **Service router** in tapetum: call class → `{alliance-pod, h200-qwen3-32b}` with oversize preflight.
