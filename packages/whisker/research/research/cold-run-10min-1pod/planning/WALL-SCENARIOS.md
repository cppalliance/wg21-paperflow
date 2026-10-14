# Wall scenarios (1 MoE pod, S=16)

**Date:** 2026-07-24  
**Sources:** `SYNTHESIS.md`, reports `11`, `12`, `17`, `18`, `20`  
**Model (single queue):** `wall = (N × L) / S + T + C − L_abs`  
**Model (hetero):** `wall = max(T_moe, T_dense) + T_client`

| Name | N | L | S | Wall | Assumptions | Status |
|------|--:|--:|--:|-----:|-------------|--------|
| Baseline v10 cold | 2284 | 20 s | 16 MoE | **3003 s** (~50 min) | All calls on `alliance-pod` | measured |
| v11 short-circuit only | ~1219–1419 | 20 s | 16 | **~1260–1493 s** (~21–25 min) | Metadata Tier A+B / full skip; partial prefix + LJF | modeled |
| CONSERVATIVE package | 2284 | 20 s | 16 | **~2163 s** (~36 min) | Prefix/HMAC/LJF/server APC; no short-circuit | modeled |
| MODERATE package | 1419 | 20 s | 16 | **~1366 s** (148 pess. ~1493) | Short-circuit + verdict-first + residual prefix | modeled |
| MODERATE + max server ops | 1419 | L cut only | 16 | **~1499–1735 s** (~25–29 min) | Post-SC + Tier-1/2 ops (~186–422 s) | modeled |
| Front-end physics floor | 758 | 20 s | 16 | **948 s** (~16 min) | Monolith+metadata only; no units | modeled |
| Loaded-decode floor | 1419 | decode@19 tok/s | 16 | **672 s** decode-only | Prefill/queue excluded | modeled |
| AGGRESSIVE bare optimistic | 1229 | L_eff 11.74 s | 16 | **~585 s** | Router + 2× dense; zero friction; unvalidated | modeled |
| AGGRESSIVE realistic | 1229 | L_eff 11.74 s | 16 | **~715–910 s** (~12–15 min) | +130–230 s friction | modeled |
| AGGRESSIVE planning central | 1229 | L_eff 11.74 s | 16 | **~680 s** | 148 pessimistic path (`11`) | modeled |
| Hetero A: units+meta dense @2× | Dense 1879 / MoE ~428 | Dense 10/5 s; MoE 19–20 s | Dense 48 / MoE 16 | **~511 s** (MoE-bound) | Scoping landed; dense live | modeled / **blocked** |
| Hetero B: units dense, meta on MoE | Dense 1502 / MoE ~758 | Dense 10 s; MoE 20 s | 48 / 16 | **~620–710 s** | Scoping landed | modeled / **blocked** |
| Hetero + MODERATE short-circuit | Dense ~1040 / MoE ~428 | Dense 10/5; MoE 19–20 | 48 / 16 | **~511 s** (still MoE-bound) | Short-circuit shrinks dense, not monolith | modeled / **blocked** |
| Hetero 70% @2× (no short-circuit) | Dense 1599 / MoE 685 | Dense 10; MoE 20 | 48 / 16 | **~856 s** (~14 min) | MoE-bound at all S_dense 32–48 | modeled / **blocked** |
| Hetero 70% after MODERATE | Dense 993 / MoE 426 | Dense 10; MoE 20 | 48 / 16 | **~533 s** | Recompute legs; do not double-count −1059 s | modeled / **blocked** |
| Dense unscoped (negative EV) | Dense 1879 | ~20 s | Dense ≤16 | T_dense **~2349 s** | Full `candidate_md`; no scoping | modeled / **blocked** |
| Dense pods all 404 | MoE-only | — | 16 | Honest SLA **~15–20 min** | After MoE package; no hetero | **blocked** |
| Dual-pod / S=32 | — | — | 32 | ~~−887 s~~ | Twin forbidden; seq-32 +57% wall | **rejected** |

## How to read status

| Status | Meaning |
|--------|---------|
| **measured** | Live cold fleet number in corpus |
| **modeled** | Arithmetic from census + L assumptions; no stacked AGGRESSIVE/hetero cold run |
| **blocked** | Requires live dense (`h200-qwen3-32b` etc.) and/or payload scoping; dense **HTTP 404** as of 2026-07-24 probe |
| **rejected** | Hard constraint / measured regression |

## Takeaway

- **Measured today:** only the v10 baseline (3003 s). Remeasure v11 (P0) before treating 21–25 min as fact.
- **Shippable without infra:** MODERATE / MoE AGGRESSIVE software → **~12–25 min**, never bank ≤600 s (`17`, `18`).
- **Only ≤600 s design:** hetero MoE+dense at ~511 s central, currently **infra-blocked** (`12`, `20`, `SYNTHESIS`).
