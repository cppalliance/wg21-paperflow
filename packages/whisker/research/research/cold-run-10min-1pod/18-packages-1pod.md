# 18 - CONSERVATIVE / MODERATE / AGGRESSIVE packages (1 pod only, S=16)

**Date:** 2026-07-24  
**Corpus:** `research/cold-run-10min-1pod/` (twin pod **forbidden**)  
**Sources:** `research/cold-run-10min/SYNTHESIS.md` §3, `11-wall-arithmetic.md`, `22-path-a-b-10min.md`, `48-combined-lever-modeler.md` (tapetum-llm-speedup), `21-prior-synthesis-gaps.md`, `16-dense-judge-candidates.md`  
**Constraint:** **S_eff = 16 fixed** on `alliance-pod` only. No `h200x8-deepseek-v4-pro`, no `--max-num-seqs 32`, no client c>32.

---

## Wall model

```
wall = (N_rem × L_eff) / 16 + T + C − L_abs
```

| Symbol | Baseline | Notes |
|--------|----------|-------|
| N | 2284 | ~6 calls/paper, 381 papers |
| L | 20 s/call | Closes measured **3003 s** cold wall |
| S | **16** | Server slots; **never 32** on one pod (+57% regression) |
| T+C | 148 s → **28 s** (opt) / **68 s** (pess) | After LJF + `to_thread` |
| L_abs | prefix + verdict-first | Absolute seconds; **not** scaled by S |

**Stacking:** N cuts first → rescale L_abs to surviving mix → divide by S=16. Same-factor levers do not add linearly (`48` overlap ledger).

---

## Package definitions (adapted from SYNTHESIS §3)

Dual-pod shard is **removed** from CONSERVATIVE. Dense-judge offload uses **existing** dense Alliance endpoints (`h200-qwen3-32b`, etc.), not a second V4-Pro replica.

### CONSERVATIVE (no verdict-semantics change)

| Lever | Est. saving @ S=16 | Quality gate |
|-------|---------------------:|--------------|
| Error tombstone fingerprints + `--retry-errors` | 0 s cold; ~50 s warm | None |
| HMAC per-paper guard tag + unit user-block reorder | **−550 to −600 s** (full fleet prefix low bound) | Lane bump + holdout A/B |
| Server APC retention env + MBT 16384 | (included in prefix envelope) | Ops confirm flags |
| LJF paper ordering | **−60 to −90 s** on T | None |
| `asyncio.to_thread` (screen_pages / grounding) | **−30 to −60 s** on C | None |
| Monolith `asyncio.wait_for` | 0 s mean cold; tail guard | None |
| ~~Dual-pod shard~~ | **EXCLUDED** (1-pod corpus) | — |

**Does NOT include:** metadata short-circuit, verdict-first schema, router tightening, dense offload, deterministic metadata diff.

### MODERATE (CONSERVATIVE + call elimination + decode shrink)

| Added lever | Calls / latency | Est. saving @ S=16 |
|-------------|-----------------|-------------------:|
| Metadata Tier A+B short-circuit | **−847 calls**; N: 2284→1419 | **−1059 s** compute |
| Escalation skip-and-synthesize | **−18 calls** | **−23 s** |
| Verdict-first / pass-path reasoning shrink | ~55→~10 tok on pass units | **−155 s** (scaled to N_rem=1419) |
| Prefix on **remaining** mix only | Rescaled unit reorder | **−281 s** (not full −600) |
| MTP speculative decode k=1 (optional, A/B-gated) | Decode 1.49× on MoE | **+220 to +470 s** upside; **not in central** |

**Does NOT include:** router combo_safe, deterministic metadata diff, dense-judge offload.

### AGGRESSIVE (MODERATE + router + dense offload + optional metadata diff)

| Added lever | Calls / latency | Est. saving @ S=16 |
|-------------|-----------------|-------------------:|
| Router combo_safe tightening | **−190 calls** (scaled **~63** post-short-circuit) | **−238 s** full fleet; **~79 s** post-v11 |
| Dense-judge offload (`h200-qwen3-32b` primary) | 82.6% of calls @ L≈10 s; 17.4% MoE fallback @ L=20 s | **L_eff ≈ 11.74 s** on N_rem |
| Deterministic metadata/outline diff (P131, optional) | **−377 calls** | **−471 s** compute; separate A/B |
| Prefix + verdict on AGGRESSIVE survivor mix | Rescaled | **−211 to −345 s** (48 vs 148) |

**Quality gates (all mandatory before ship):** 381/381 fused verdict parity (dense), router FN holdout (6 PIDs), metadata diff A/B (LLM adds nothing).

---

## Package rollups @ S=16

### CONSERVATIVE

```
N = 2284,  L = 20 s,  S = 16
wall = 2284×20/16 + 28 − 600 − 90 − 30
     = 2855 + 28 − 720
     = 2163 s
```

| Estimate | Central (s) | Range (s) | Minutes | ≤600 s? |
|----------|------------:|----------:|--------:|:-------:|
| 48 optimistic (`22` Path B formula) | **2163** | 2100–2200 | **36.0–36.7** | ❌ |
| 11 planning (prefix low bound variance) | **~2370** | 2280–2450 | **38–41** | ❌ |

**Verdict:** Saves **~840–1140 s** vs baseline but **cannot reach 10 min**. Missing dual-pod was **~887–1428 s** of compute halving on this package class.

---

### MODERATE

```
N_rem = 2284 − 847 − 18 = 1419
compute@16 = 1419 × 20 / 16 = 1773.8 s
L_abs = 281 + 155 = 436 s  (48)  |  225 + 124 = 349 s  (148 pess.)
T+C = 28 s (48)  |  68 s (148)

wall (48)  = 1773.8 + 28 − 436  = 1365.8 ≈ 1366 s
wall (148) = 1773.8 + 68 − 349  = 1492.8 ≈ 1493 s
```

| Estimate | Central (s) | Range (s) | Minutes | ≤600 s? |
|----------|------------:|----------:|--------:|:-------:|
| 48 optimistic | **1366** | 1330–1400 | **22.2–23.3** | ❌ |
| 148 pessimistic | **1493** | 1420–1550 | **23.7–25.8** | ❌ |
| + MTP A/B (optional, best case) | **~896–1146** | — | **15–19** | ❌ |

**Step rebuild (48):**

| Step | Δ wall (s) | Cumulative (s) |
|------|----------:|-----------------:|
| Baseline | — | 3003 |
| Metadata Tier A+B | −1059 | 1944 |
| Escalation dedupe | −23 | 1921 |
| Verdict-first (scaled) | −155 | 1766 |
| Prefix (remaining only) | −281 | **1485** |
| Compute term check | 1419×20/16 = 1774 | 1774 + 28 − 436 = **1366** ✓ |

**Verdict:** Best quality-bounded software stack on one pod. **~54% wall reduction** vs baseline. Still **~766–893 s above** the 600 s gate. Compute term alone on 1419 calls is **1774 s**.

---

### AGGRESSIVE

```
N_rem = 1419 − 190 = 1229   (router; 48 full-fleet scale)
L_eff = 0.826×10 + 0.174×20 = 11.74 s
compute@16 = 1229 × 11.74 / 16 = 902.2 s
L_abs = 211 + 134 = 345 s  (48)  |  ~290 s  (148 pess.)
T+C = 28  |  68
heterogeneous friction = +130 s  (48)  |  +230 s  (148)
```

| Estimate | Central (s) | Range (s) | Minutes | ≤600 s? |
|----------|------------:|----------:|--------:|:-------:|
| 48 bare (no friction) | **585** | 560–610 | **9.8–10.2** | ⚠️ hairline |
| 48 + friction | **715** | 680–780 | **11.3–13.0** | ❌ |
| 148 pessimistic + friction | **910** | 850–970 | **14–16** | ❌ |
| + deterministic metadata diff (−377 calls) | **~520 bare** / **~650 friction** | planning only | — | ⚠️ / ❌ |
| + MTP A/B (optional) | **−220 to −470 s** on MoE leg | — | — | could flip bare ✅ |

**Step rebuild (48 bare):**

| Step | Δ wall (s) | Cumulative (s) |
|------|----------:|-----------------:|
| From MODERATE remainder | 1366 | 1366 |
| Router −190 calls | −238 | — |
| N→1229, L_eff 11.74 | compute 902 vs 1536 | — |
| Prefix + verdict rescale | net −91 vs MODERATE L_abs | — |
| **Bare wall** | — | **585** |
| + heterogeneous routing friction | +130 | **715** |

**Verdict:** Only package that **touches** the 600 s gate. **585 s bare** is planning-grade **optimistic** (assumes 2× dense decode, zero parity drift, no router FN). With measured friction, plan **715–910 s**. Not a reliable ≤600 s path without instrumented cold run.

---

## Summary table (1 pod, S=16)

| Package | N_rem | L_eff | Central wall (s) | Range (s) | Minutes | ≤600 s? |
|---------|------:|------:|-----------------:|----------:|--------:|:-------:|
| **BASELINE** | 2284 | 20 s | **3003** | 2883–3003 | 48–50 | ❌ |
| **CONSERVATIVE** | 2284 | 20 s | **2163** | 2100–2450 | 35–41 | ❌ |
| **MODERATE** | 1419 | 20 s | **1366** | 1330–1550 | 22–26 | ❌ |
| **AGGRESSIVE** (bare) | 1229 | 11.74 s | **585** | 560–610 | ~10 | ⚠️ |
| **AGGRESSIVE** (realistic) | 1229 | 11.74 s | **715** | 680–910 | 11–15 | ❌ |

For comparison, dual-pod SYNTHESIS §3 @ S=32: MODERATE **~596 s central** (530–670 s), AGGRESSIVE **~260–350 s**.

---

## Gap analysis: why 600 s misses on 1 pod

| Missing lever vs dual-pod MODERATE | Wall impact (s) |
|-----------------------------------|----------------:|
| S: 32→16 (compute term doubles on N_rem=1419) | **+887** |
| MODERATE single-pod central | 1366 |
| MODERATE dual-pod central | 596 |
| **Gap** | **770** |

Software levers (metadata, prefix, verdict-first) save **~1637 s** combined on one pod but leave **~1366 s**. The remaining **~766 s** to 600 s is almost entirely **parallel MoE capacity** that only a second identical replica provides.

AGGRESSIVE dense offload attacks **L**, not **S**: heterogeneous `max(T_dense, T_moe)` still MoE-bound at **~620–710 s** without call elimination (`16-dense-judge-candidates.md`). Stacked with MODERATE N cuts, bare model reaches **585 s**; friction and validation risk push planning to **715+ s**.

---

## Optional stretch levers (not in central stacks)

| Lever | Est. @ S=16 | Package tier | ≤600 alone? |
|-------|------------:|--------------|:-----------:|
| Tier C metadata full skip (−1047 calls) | **−1331 s** | beyond MODERATE | ❌ (inspect regression) |
| MAX_UNIT_CHECKS cap 3 | **−628 s** full fleet / **~−138 s** post-metadata | AGGRESSIVE | ❌ |
| Payload scoping (~198 s) | overlaps prefix | — | ❌ |
| DeepEP low_latency + DBO ops kernels | **−10–30% L** hypothesis | CONSERVATIVE ops | ❌ (~1000 s+ after MODERATE) |
| NVFP4 / quant on H200 | N/A (unsupported) | — | — |
| Non-think / Flash V4 swap | quality tradeoff; unmeasured | AGGRESSIVE | unknown |

Even Tier C + MODERATE @ S=16: `(2284−1047−18)×20/16 + 28 − L_abs ≈ 1547 − 436 ≈ **1111 s**` — still **>600 s**.

---

## Answer: which package hits ≤600 s?

| Package | Hits ≤600 s? | Notes |
|---------|:------------:|-------|
| **CONSERVATIVE** | **No** | Central **~2163 s** (~36 min) |
| **MODERATE** | **No** | Central **~1366 s** (~23 min); best 1-pod quality path |
| **AGGRESSIVE** | **No (planning)** / **Maybe (bare model)** | Central **585 s bare** touches gate; **715 s realistic** with friction |

**Planning verdict:** **None of the three packages reliably hits ≤600 s on one pod @ S=16.** Only AGGRESSIVE bare optimistic arithmetic (**585 s**) crosses the line; that assumes unvalidated dense-judge parity, 2× decode speedup, and zero heterogeneous routing overhead. Treat **MODERATE ~1366 s (~23 min)** as the honest single-pod floor after v11 call elimination.

---

## False-pass / false-fail

**False-pass:** Ship AGGRESSIVE citing **585 s** without friction (+130 s), without 381/381 parity A/B, without MoE fallback for 8 oversize papers → live run **>900 s** or quality collapse; operators disable offload and revert to **~2900 s** baseline.

**False-fail:** Reject MODERATE because "10 min impossible on one pod," never ship metadata short-circuit (−847 calls) → stay at **~2900 s** when **~1366 s** was reachable without twin.

---

## What would change this

1. **Instrumented AGGRESSIVE cold run ≤620 s** with dense pod live, per-call `{pod_id, latency, cached_tokens}` → upgrade AGGRESSIVE to ✅.
2. **Measured MODERATE ≤650 s** on one pod → model error; revisit L_abs or N census.
3. **Restore twin pod** → revert to dual-pod SYNTHESIS §3; MODERATE **~596 s** central without AGGRESSIVE validation burden.
