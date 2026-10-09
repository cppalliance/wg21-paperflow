# 22 - Path A / Path B: 10 min with twin pod alive vs dead

**Date:** 2026-07-24  
**Sources:** `research/tapetum-llm-speedup/48-combined-lever-modeler.md`, `SYNTHESIS.md`, `148-verifier-stacking-arithmetic.md`, `cold-run-10min/00-baseline.md`  
**Assumption:** `h200x8-deepseek-v4-pro` (twin) **may be dead**; `alliance-pod` is the reliable DeepSeek-V4-Pro endpoint.

## Wall model (unchanged)

```
wall = (N_rem × L_eff) / S_eff + T + C − L_abs
```

| Symbol | Baseline | Notes |
|--------|----------|-------|
| N | 2284 | 381 papers, ~6 calls/paper |
| L | 20 s/call | Fleet mean; closes 3003 s measured wall |
| S | 16 (single) / 32 (dual) | **32 server slots on one pod forbidden** (+57% regression) |
| T+C | 148 s → 28 s (opt) / 68 s (pess) | After LJF + `to_thread` |
| L_abs | prefix + verdict-first | Absolute seconds; **not** halved when S doubles |

Stacking rule: apply **N cuts first**, rescale **L_abs** to surviving mix, then divide by **S**. Same-factor levers do not add linearly (`48` overlap ledger).

---

## SYNTHESIS packages table (2026-07-23, dual-pod assumed)

From `SYNTHESIS.md` §3, reconciled by `48` and audited by `148`:

| Package | Levers (deduped) | S_eff | Expected cold wall | ≤600 s? |
|---------|------------------|------:|-------------------:|:-------:|
| **BASELINE** | — | 16 | 2903–3003 s (~48–50 min) | ❌ |
| **CONSERVATIVE** | tombstone FP, HMAC guard + prompt reorder, APC retention env, LJF, `to_thread`, monolith timeout, **dual-pod shard** | 32 | **685–856 s** (48) / **860–1020 s** (148 pess.) | ❌ |
| **MODERATE** | CONSERVATIVE + metadata Tier A+B (−847), escalation dedupe (−18), verdict-first pass schema | 32 | **480–530 s** (48) / **530–670 s** (148); **~596 s central** | ✅ |
| **AGGRESSIVE** | MODERATE + router combo_safe (−190), dense-judge offload (`h200-qwen3-32b`) | 32 | **260–350 s** (48) / **420–580 s** (148) | ✅ |

**Prior verdict:** MODERATE on dual-pod is the quality-bounded path to ~10 min. AGGRESSIVE is optional for ≤5 min or margin.

---

## Path A: twin alive (`alliance-pod` + `h200x8-deepseek-v4-pro`)

**Infra:** Both pods probe 200 at pre-gather; `--shard-pods` with per-pod `Semaphore(16)`; deterministic `index % 2` on sorted PIDs (`21-dual-pod-sharder`).

**Effective slots:** S_eff = 32 (plan S=28–30 until live proof; skew friction +75–125 s if semaphores missing, `148`).

### MODERATE stack (recommended)

```
N_rem = 2284 − 847 − 18 = 1419
compute@32 = 1419 × 20 / 32 = 886.9 s
L_abs = prefix 281 + verdict 155 = 436 s  (48 rescale)
T+C = 28 s

wall = 886.9 + 28 − 436 = 478.9 s
+ per-pod skew friction: +50 to +125 s
```

| Estimate | Central (s) | Range (s) | Minutes |
|----------|------------:|----------:|--------:|
| Persona 48 (optimistic friction) | **529** | 480–530 | 8.0–8.8 |
| SYNTHESIS / 148 planning | **596** | 530–670 | 9–11 |
| Upper guard (148 false-pass band) | — | ≤670 | ≤11.2 |

**Path A verdict:** ✅ **≤600 s at planning central (~596 s)**. Ship MODERATE; instrument before claiming ≤530 s.

### CONSERVATIVE only (no semantics change)

Central **~770–945 s** (11–16 min). Dual-pod alone is insufficient without call elimination.

### AGGRESSIVE (if ≤5 min or tight 10 min margin)

Central **~295–495 s** (5–8 min). Requires dense pod + router A/B (`23`, `11`).

---

## Path B: twin dead (single `alliance-pod`, S_eff = 16)

**Infra:** Pre-gather health probe finds twin 404 (historical: `18-load-splitter.md:8`, `21:12`); fallback assigns **all 381 papers to `alliance-pod`**. No second DeepSeek replica. Client c=32 unchanged (still overfills 16 server slots on one pod).

**Forbidden substitute:** `--max-num-seqs 32` on one pod (+57% wall, `00-baseline`).

### MODERATE stack (same levers, no dual-pod)

```
N_rem = 1419
compute@16 = 1419 × 20 / 16 = 1773.8 s
L_abs = 436 s (48)  |  349 s (148 pess.: prefix 225 + verdict 124)
T+C = 28 s (48)     |  68 s (148)
```

| Estimate | Formula | Central (s) | Range (s) | Minutes |
|----------|---------|------------:|----------:|--------:|
| 48 optimistic | 1773.8 + 28 − 436 | **1366** | 1330–1400 | **22.2–23.3** |
| 148 pessimistic | 1773.8 + 68 − 349 | **1493** | 1420–1550 | **23.7–25.8** |

**Path B + MODERATE verdict:** ❌ **Does not hit 10 min.** Missing ~766–893 s vs target; dual-pod was ~887 s of the MODERATE savings (halving compute on 1419 calls).

### CONSERVATIVE only (Path B)

```
wall = 2284×20/16 + 28 − 600 − 90 − 30 = 2163 s (~36 min)
```

Still ❌; prefix without call cuts or second pod leaves ~22–36 min class.

### AGGRESSIVE stack (Path B: dense offload still available)

Dense judge runs on **`h200-qwen3-32b`** (separate service, not the dead twin). Only the **MoE compute term** loses dual-pod; offload levers unchanged.

```
N_rem = 1229
L_eff = 0.826×10 + 0.174×20 = 11.74 s  (MoE fallback 17.4%)
compute@16 = 1229 × 11.74 / 16 = 902.2 s
L_abs = 211 + 134 = 345 s (48)  |  290 s (148 pess.)
T+C = 28 | 68
friction = +130 (48) | +230 (148)
```

| Estimate | Central (s) | + friction | ≤600 s? |
|----------|------------:|-----------:|:-------:|
| 48 optimistic | **585** | **715** | ❌ (friction) / hairline (bare) |
| 148 pessimistic | **680** | **910** | ❌ |

**Path B + AGGRESSIVE verdict:** ❌ **Not a reliable ≤600 s path.** Optimistic bare model touches 585 s; with measured friction, plan **715–910 s** (12–15 min). Requires full AGGRESSIVE validation (`381/381` parity, router FN holdout) for a **maybe** that still misses under pessimistic accounting.

---

## Side-by-side summary (2026-07-24)

| Path | Infra | Package to ≤600 s | Central wall (s) | Range (s) | Hits 10 min? |
|------|-------|-------------------|-----------------:|----------:|:------------:|
| **A** | Twin alive, S=32 | **MODERATE** | **596** | 530–670 | ✅ |
| **A** | Twin alive, S=32 | AGGRESSIVE | 495 | 420–580 | ✅ (margin) |
| **B** | Twin dead, S=16 | MODERATE | **1366** | 1330–1550 | ❌ |
| **B** | Twin dead, S=16 | CONSERVATIVE | 2163 | 2100–2200 | ❌ |
| **B** | Twin dead, S=16 | AGGRESSIVE | **585** bare / **715** realistic | 585–910 | ❌ (realistic) |

**Gap opened by dead twin on MODERATE:** compute term doubles → **+887 s** on top of 529 s Path A optimistic (**1366 − 479 ≈ 887**).

---

## Updated path to 10 min (2026-07-24)

### Path A (twin alive) — unchanged from SYNTHESIS

1. Free wins (no lane bump): tombstone FP, LJF, `to_thread`, monolith timeout, per-call timing.
2. Lane bump: HMAC guard + user-block reorder + APC retention env on **both** pods.
3. Lane bump: metadata Tier A+B + escalation dedupe + verdict-first (MODERATE).
4. **Dual-pod shard** with dual health probe + per-pod semaphores.
5. Instrumented 381-paper cold run; accept **530–670 s** band before tuning AGGRESSIVE.

**Expected:** ~596 s central, 9–11 min.

### Path B (twin dead) — revised

**MODERATE alone cannot reach 10 min.** Operator choices:

| Option | Action | Expected wall | Quality cost |
|--------|--------|---------------:|:---------------|
| **B1 — Restore twin** | Fix `h200x8-deepseek-v4-pro` proxy/vLLM; run Path A | ~596 s | Same as MODERATE |
| **B2 — AGGRESSIVE on one MoE pod** | Add router + dense offload; accept HIGH validation | ~585–715 s | Router FN risk; 381-paper parity |
| **B3 — Accept slower cold** | Ship MODERATE without shard | ~1366 s (~23 min) | Verdict-safe; inspect delta only |
| **B4 — New S multiplier** | Second **identical** DeepSeek replica (not necessarily h200x8 name) | Path A arithmetic | Ops provisioning |

There is **no code-only** substitute for S=32 when one MoE pod holds 16 slots. Prefix cache and metadata cuts save ~1637 s combined on Path B but leave ~1366 s; the remaining ~766 s to 600 s is almost entirely **parallel MoE capacity**.

---

## Answer block

| Question | Answer |
|----------|--------|
| Path A (twin alive) hits 10 min with MODERATE? | **Yes** — central **~596 s** (range 530–670 s) |
| Path B (twin dead) hits 10 min with MODERATE? | **No** — central **~1366 s** (148 pess. **~1493 s**) |
| Path B hits 10 min with AGGRESSIVE? | **No** (realistic) — central **~715 s** with friction; bare optimistic **585 s** is not planning-grade |
| Single lever that flips Path B → Path A | Dual-pod shard (**~887 s** on MODERATE compute term) |

---

## False-pass hypothesis

Operator runs Path B MODERATE, sees **~1300–1400 s**, blames metadata short-circuit or prefix reorder (which did save ~1637 s vs baseline-on-one-pod) and reverts call elimination — fleet returns to **~2900 s** while twin stays unfixed.

## False-fail hypothesis

Operator skips MODERATE on Path B because "10 min impossible," never ships metadata cut (−847 calls) or prefix reorder (−281 s), and stays at **~2900 s** when **~1366 s** was reachable without twin.

## What would change my mind

1. **Twin restored + cold run ≤670 s** → Path A confirmed.  
2. **Path B AGGRESSIVE instrumented run ≤620 s** with dense pod live → upgrade Path B AGGRESSIVE to ✅.  
3. **New evidence that single-pod S=16 with MODERATE ≤650 s measured** → model error; revisit L_abs or N cuts.
