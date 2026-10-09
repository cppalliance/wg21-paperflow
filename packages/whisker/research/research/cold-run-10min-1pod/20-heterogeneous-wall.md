# 20 - Heterogeneous Wall Model (MoE S=16 + dense S=32–48)

**Verdict:** usable — parallel pods with **`wall = max(T_moe, T_dense)`** (not sum) are the correct single-MoE-pod layout; at **70% fleet calls offloaded @ 2× decode**, central wall is **~856 s (~14 min)**, **MoE-bound**, and **misses ≤600 s** unless paired with MODERATE call cuts or full unit+metadata offload (~82.6%).

**Confidence:** medium-high (slot formula closed against `00-baseline`; dense L=10 s is persona 23/105 hypothesis until bench)

**Date:** 2026-07-24. Sources: `research/cold-run-10min-1pod/{00-baseline,12-dense-offload-architecture}.md`, `research/cold-run-10min/{11-wall-arithmetic,16-dense-judge-candidates}.md`, `research/tapetum-llm-speedup/105-vllm-dense-judge-throughput.md`.

---

## Model

Two independent server queues run in parallel. Client `c=32` feeds both; each pod has its own slot semaphore.

```
T_pod = Σ(N_i × L_i) / S_pod          per pod
wall  = max(T_moe, T_dense) + T_client
```

| Symbol | Meaning | Fixed value (this corpus) |
|--------|---------|---------------------------|
| `S_moe` | `alliance-pod` `--max-num-seqs` | **16** (forbidden to raise; +57% wall) |
| `S_dense` | `h200-qwen3-32b` (or reserve) | **32–48** (KV-feasible with FP8 + scoped payload) |
| `L_moe` | MoE fleet mean per call | **20 s** baseline; **18–22 s** monolith band |
| `L_dense` | Dense offloaded call latency | **10 s** at **2×** vs MoE (`L_moe/2`); **5 s** for tiny metadata @ 2× |
| `N` | Fleet LLM calls | **2284** v10; **1419** after MODERATE Tier A+B |

**Not sum:** offloading 70% of calls does **not** subtract 70% of baseline wall. The slow leg sets fleet time.

**Prerequisites for 2× on dense:** payload scoping to ~10–15k tokens + FP8 KV (`12-dense-offload-architecture.md`, `105`). Without scoping, dense reverts to `L≈20 s`, `S≤16` → offload is negative EV.

---

## Call inventory (v10, 2284 calls)

| Class | Count | Default pod @ full offload | Share |
|-------|------:|----------------------------|------:|
| Unit check | 1510 | Dense | 66.1% |
| Metadata / outline | 377 | Dense | 16.5% |
| Monolith + HTML tier-1 | 381 | MoE | 16.7% |
| Page escalation | ~16 | MoE | 0.7% |
| HTML tier-2 | ~23 | MoE | 1.0% |
| Ideal verify | ~1 | MoE | ~0% |
| **Total** | **2284** | | **100%** |

Full heterogeneous offload (persona 16/12): **1879 dense (82.3%)**, **~428 MoE (18.8%)**.

**70% offload split:** `0.70 × 2284 = **1599**` dense, **`685`** MoE. Natural composition: **all 1510 unit checks** + **89 metadata** → dense; remainder (**288 metadata + 381 first-pass + ~16 esc**) → MoE.

---

## Scenario A — 70% calls offloaded @ 2× (requested)

**Assumptions:** scoped payload landed; `L_dense = 10 s` (2× vs `L_moe = 20 s`); metadata on dense uses same 2× where moved.

| Leg | N | L | S | T (s) |
|-----|--:|--:|--:|------:|
| Dense | 1599 | 10 s | 48 | **333** |
| Dense | 1599 | 10 s | 40 | **400** |
| Dense | 1599 | 10 s | 32 | **500** |
| MoE | 685 | 20 s | 16 | **856** |

### Answer (70% @ 2×)

| S_dense | T_dense | T_moe | **wall = max(...)** |
|--------:|--------:|------:|--------------------:|
| **48** | 333 | 856 | **856 s (~14.3 min)** |
| **40** | 400 | 856 | **856 s** |
| **32** | 500 | 856 | **856 s** |

**MoE-bound at every S_dense in 32–48.** Raising dense slots does not move wall until `T_dense` exceeds `T_moe` (not reachable at 70% offload). vs baseline **3003 s**: saves **~2147 s (~71%)**. vs **≤600 s** target: **misses by ~256 s (~43%)**.

Sensitivity on MoE leg (685 calls, mixed mono/meta):

| L_moe mix | T_moe | wall @ S_dense=48 |
|-----------|------:|------------------:|
| 20 s flat | 856 | **856** |
| 19 s mono + 10 s meta (685-call blend) | **792** | **792** |
| 18–22 s range | 771–943 | **771–943** |

Central estimate: **~856 s**; planning band **~790–860 s**.

---

## Scenario B — full unit offload @ 2× (66.1%, recommended floor)

Move **all 1510 unit checks** to dense; keep monolith, metadata, esc on MoE.

| Leg | N | L | S | T (s) |
|-----|--:|--:|--:|------:|
| Dense (units only) | 1510 | 10 s | 48 | **315** |
| Dense (units only) | 1510 | 10 s | 32 | **472** |
| MoE (774 non-unit) | 774 | 20 s | 16 | **968** |

With persona-12 MoE call census (**~428** calls after HTML/tier dedupe, `L≈19 s`):

| Leg | T (s) |
|-----|------:|
| T_dense (1510×10/48) | 315 |
| T_moe (~428×19.5/16) | **~511** |
| **wall** | **~511 s (~8.5 min)** |

Full unit offload + scoped 2× is **MoE-bound ~511 s** (inside ≤600 s band, fragile). This is why doc 12 targets **82.6%** (units + metadata on dense), not 70%.

---

## Scenario C — 70% @ 2× **after** MODERATE short-circuit

`N_rem = 1419` (2284 − 847 metadata short-circuit − 18 escalation dedupe).  
70% dense: **993 calls**; MoE: **426 calls**.

| Leg | N | L | S | T (s) |
|-----|--:|--:|--:|------:|
| Dense | 993 | 10 s | 48 | **207** |
| MoE | 426 | 20 s | 16 | **533** |
| **wall** | | | | **~533 s (~8.9 min)** |

Short-circuit shrinks the MoE queue enough that **70% offload @ 2×** can approach ≤600 s when combined with Tier A+B. Still MoE-bound; dense S=32–48 irrelevant (207 ≪ 533).

Stacking note: this **double-counts** if you also apply full metadata short-circuit savings (−1059 s) additively. Correct method: recompute `N` on each leg, then `max()`.

---

## Scenario D — 70% of **unit checks only** @ 2× (zero-defect cohort)

**1057/1510 (70%)** unit checks offloaded — matches zero-defect share (`00-baseline.md`). Defect-path units stay on MoE.

| Leg | N | L | S | T (s) |
|-----|--:|--:|--:|------:|
| Dense | 1057 | 10 s | 48 | **220** |
| MoE | 1227 | 20 s | 16 | **1534** |
| **wall** | | | | **~1534 s (~25.6 min)** |

Selective unit offload without moving metadata/monolith **fails**: MoE queue grows. Do not confuse "70% zero-defect units" with "70% fleet offload."

---

## S_dense sensitivity (full 1510 units + 377 metadata @ 2×)

MoE fixed at persona-12 **~511 s** (`~428` calls). Dense term only:

| S_dense | L_unit | L_meta | T_dense | **wall** |
|--------:|-------:|-------:|--------:|---------:|
| 32 | 10 s | 5 s | 516 | **516** |
| 40 | 10 s | 5 s | 425 | **511** |
| 48 | 10 s | 5 s | 352 | **511** |

At full offload, **S_dense ≥ 40** stops mattering once `T_dense < T_moe`. At **70% offload**, MoE has **685** calls → **T_moe ≈ 856 s** dominates regardless of S_dense.

---

## Comparison table

| Layout | Dense share | S_dense | **wall (central)** | ≤600 s? |
|--------|------------|--------:|-------------------:|:-------:|
| Single-pod baseline | 0% | — | 3003 | ❌ |
| Single-pod MODERATE @ S=16 | 0% | — | ~1493 | ❌ |
| **70% @ 2× (this doc)** | **70%** | **32–48** | **~856** | ❌ |
| Full units @ 2× | 66% | 48 | ~511–968† | ⚠️ |
| Full units+metadata @ 2× | 82.6% | 48 | **~511** | ⚠️ |
| Full offload + MODERATE short-circuit | 82.6% | 48 | **~511** | ⚠️ |
| 70% @ 2× + MODERATE short-circuit | 70% of 1419 | 48 | **~533** | ⚠️ |
| Dual V4-Pro (blocked) | 0% split | 32 MoE eff. | ~596 | ✅ blocked |

† ~968 if all 774 non-unit calls stay on MoE at L=20; ~511 with persona-12 MoE census.

---

## Findings

- [CRITICAL] **`wall = max(T_moe, T_dense)`, not sum.** Evidence: `105-vllm-dense-judge-throughput.md:16-24`, `12-dense-offload-architecture.md:81-148`. Impact: 70% offload saves dense-queue time but **does not reduce wall** until MoE leg drops below dense leg.

- [CRITICAL] **70% fleet offload @ 2× → ~856 s, MoE-bound.** Evidence: `1599×10/48 + 685×20/16` → max(333, 856). Impact: **misses ≤600 s by ~256 s** without further MoE-leg cuts (metadata diff, short-circuit, prefix on monolith).

- [HIGH] **S_dense 32–48 is irrelevant at 70% offload.** T_dense spans 333–500 s; T_moe ≈ 856 s. Impact: operator effort on dense slot tuning does not move wall until offload fraction exceeds ~82% or MoE N drops via call elimination.

- [HIGH] **Full unit+metadata offload (82.6%) @ 2× → ~511 s** with persona-12 MoE census. Evidence: `12-dense-offload-architecture.md:157-167`. Impact: touches ≤600 s band; quality-blocked until 381/381 A/B.

- [MED] **MODERATE short-circuit + 70% @ 2× on remainder → ~533 s.** Recomputed N on each leg, not additive −1059 s. Impact: plausible ≤600 s path without twin V4-Pro if short-circuit ships and dense 2× validates.

- [MED] **70% of unit checks only (zero-defect routing) → ~1534 s.** MoE absorbs defect-path units + all monolith/metadata. Impact: reject selective unit offload as a wall lever.

---

## False-pass hypothesis

Report "70% of calls offloaded at 2×" as **~42% wall reduction** (0.7/2 = 0.35 of compute): predicts **~1050 s** or better. Correct **`max()`** model gives **~856 s** — better than single queue but **not** 1050 s, and still **14 min**, not 10 min.

## False-fail hypothesis

Conclude dense offload "does not work" because 70% @ 2× misses 600 s: the failure mode is **insufficient offload fraction** (need ~83% + scoping), not heterogeneous scheduling. Full offload central **~511 s** vs **856 s** at 70%.

## What would change my mind

Measured cold run with `{pod, call_class, latency_s}` per call: if **685-call MoE leg** measures **≤550 s** (prefix/APC on monolith) while dense leg holds **≤333 s**, 70% @ 2× central drops to **~550 s** and enters ≤600 s band without full metadata move.

---

## Executive summary (for parent agent)

| Field | Value |
|-------|-------|
| **Model** | `wall = max(T_moe, T_dense) + T_client`; MoE **S=16**, dense **S=32–48** |
| **70% calls offloaded @ 2× decode** | **N_dense=1599, N_moe=685, L_dense=10 s, L_moe=20 s** |
| **T_dense @ S=48** | **~333 s** |
| **T_moe @ S=16** | **~856 s** |
| **wall (central)** | **~856 s (~14.3 min)** |
| **S_dense sensitivity (32–48)** | **No change** — MoE-bound |
| **≤600 s without twin V4-Pro?** | **No** at 70% offload alone; **plausible ~511–533 s** at **82.6%** offload or MODERATE + 70% on remainder |
| **Blockers** | Payload scoping; 381/381 dense-judge A/B (`12`, `16`) |

---

## References

- `research/cold-run-10min-1pod/00-baseline.md` — no twin V4-Pro, gap arithmetic
- `research/cold-run-10min-1pod/12-dense-offload-architecture.md` — routing split, Scenario A–D
- `research/cold-run-10min/11-wall-arithmetic.md` — slot formula, MODERATE N=1419
- `research/cold-run-10min/16-dense-judge-candidates.md` — 82.6% offload, 2× hypothesis
- `research/tapetum-llm-speedup/105-vllm-dense-judge-throughput.md` — KV math, `max()` model
