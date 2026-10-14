# 48 - Combined-Lever-Modeler

**Verdict:** usable-with-conditions (+ MODERATE and AGGRESSIVE packages can reach ≤600 s on the wall model, but only with holdout validation on metadata short-circuit and small-judge offload; CONSERVATIVE alone stays ~14 min)
**Confidence:** medium (persona estimates reconcile to baseline census; no live stacked A/B yet)

## Persona inventory (10–47)

Read **26** reports present; **11** slots empty (no file):

| Present | Missing |
|---------|---------|
| 10-call-graph-accountant, 11-router-precision-auditor, 12-unit-batching-architect, 13-payload-scoper, 14-output-token-surgeon, 15-prefix-cache-enabler, 16-monolith-redundancy-skeptic, 17-metadata-short-circuit, 18-escalation-overlap-auditor, 19-incremental-granularity, 20-in-paper-parallelist, 21-dual-pod-sharder, 22-multi-pod-fleet-designer, 23-small-judge-evaluator, 24-cascade-designer, 25-retry-economist, 26-timeout-budget-auditor, 27-http-client-tuner, 28-semaphore-topologist, 29-tail-latency-scheduler, 30-chunking-auditor, 31-thinking-token-auditor, 32-structured-output-mechanic, 33-prompt-compressor, 37-ideal-verifier-accountant, 39-kv-quant-scout | 34–36, 38, 40–47 |

Rejected or negligible for stacking (same factor or garbage): unit batching (12, quality), in-paper parallel (20, 0 s fleet), HTTP client (27), prompt compression (33), chunking (30, 0 s today), timeouts (26, 0 s tonight), retries (25, ≤100 s), structured output (32, ≤100 s), thinking tokens (31, 0 s), FP8 KV (39, already on), ideal reorder (37, ≤14 s), cascade pre-gate (24, n=1), monolith cut (16, semantics change).

## Wall model

```
wall = (N × L) / S + T + C
```

| Symbol | Baseline (v10 cold) | Source |
|--------|---------------------|--------|
| N | 2284 calls | `00-baseline.md:22-23` |
| L | ~20 s/call (effective) | `00-baseline.md:24-25` |
| S | 16 server slots | `00-baseline.md:66`, `SERVICES.toml` |
| T | ~90 s (retries + tail scheduling) | 55 retries ~100 s (`25`), LJF trim separate |
| C | ~58 s (client CPU on event loop) | `28-semaphore-topologist` |
| **wall** | **3003 s** | measured |

Check: 2284 × 20 / 16 + 148 = **2855 + 148 = 3003 s** ✓

**Stacking rule:** factors multiply only across **N** (call count), **L** (per-call latency), **S** (parallel slots), **T** (tail), **C** (client CPU). Same-factor levers do not add linearly.

**Recomputation method:** apply call-count deltas first (remove eliminated calls from N), then compute absolute wall savings for L/T/C levers on the **remaining** call set only, then apply S multiplier to the compute term `(N_rem × L) / S`.

---

## Lever ledger (by factor)

| Lever | Factor | Persona | Δ on 3003 s baseline | Quality gate |
|-------|--------|---------|----------------------|--------------|
| Prefix cache + server flags + per-paper tag + unit user reorder | L | 15 | **600–1100 s** @ S=16 on N=2284 | Holdout A/B on reorder |
| Dual-pod shard (`alliance-pod` + `h200x8-deepseek-v4-pro`) | S | 21, 22 | **S: 16→32** (~halves compute term) | Health probe both pods |
| Per-pod semaphores (16 cap each) | S | 22 | **+100–300 s** vs naive skew | Low |
| Metadata fail short-circuit | N | 17 | **−141 calls**, ~179 s | Verdict-safe (32/32 fail) |
| Metadata fail + review→1 unit (Tier A+B) | N | 17 | **−847 calls**, ~1076 s | Inspect completeness MED |
| Metadata full skip (fail+review) | N | 17 | **−1047 calls**, ~1331 s | Inspect MED; verdict-safe |
| Router combo_safe tightening | N | 11 | **−190 calls**, ~238 s | 6/47 FN papers |
| Escalation skip-and-synthesize | N | 18 | **−18 calls**, ~23 s | Dev-replay 9 PRs |
| Verdict-first / pass-path output shrink | L | 14 | **−200–340 s** @ S=16 on N=2284 | 48-paper holdout |
| Small-judge offload (unit+metadata→dense 32B) | L | 23 | **~2× on 82.6%** of calls (~850–1200 s alone) | 381/381 verdict parity A/B |
| LJF paper scheduling | T | 29 | **−60–180 s** | None |
| `asyncio.to_thread` for screen/ground | C | 28 | **−30–60 s** | None |

---

## Double-counting sanity check (CRITICAL)

**The 1331 s metadata-short-circuit saving overlaps per-call latency levers on the same calls.**

1047 eliminated calls are **~100% unit checks** (`17-metadata-short-circuit`). Those calls today contribute:

```
1047 × 20 s / 16 slots = 1309 s compute wall
```

Any **prefix-cache** or **verdict-first** estimate derived from the full 1510 unit-check population **must be scaled down**, not added on top of metadata elimination.

| Lever pair | Overlap | Correct treatment |
|------------|---------|-------------------|
| Metadata skip + prefix reorder | **HIGH** — 1047/1510 unit checks removed | Prefix unit-block saving: `500 s × (463/1510) = 153 s`, not 500 s |
| Metadata skip + verdict-first | **HIGH** — 692/1047 zero-defect units on non-pass metadata (`17`) | Verdict shrink: `250 s × (N_rem/2284)`, not full 250 s |
| Metadata skip + small-judge | **HIGH** — offloaded calls gone | Dense speedup applies to **remaining** 663 unit + 377 metadata − overlap |
| Prefix + payload scoping | **HIGH** — same prefill | Take max, not sum (`13` defers to `15`) |
| Dual-pod + in-paper parallel | **NONE** (S vs serial depth) | In-paper parallel ~0 s fleet (`20`) |
| Dual-pod + prefix | **LOW** — different factors | Prefix absolute seconds ~invariant to S; compute term halves |
| Router + metadata | **LOW** — router cuts pass-metadata units | Router −190 is mostly `table_presence` on pass papers; metadata skip targets fail/review papers; **~minimal overlap** |

**Explicit overlap arithmetic (metadata + prefix):**

- Full-fleet prefix upper bound: **600 s** (`15`, low end)
- Unit-check reorder portion: **~500 s** (5/6 of envelope)
- After Tier A+B metadata (−847 calls, **663 unit checks remain**):
  - Reorder saving: `500 × (663/1510) = **219 s**` (not 600 s)
  - Static-system APC: `100 × (1419/2284) = **62 s**`
  - **Total prefix on MODERATE stack: ~281 s** (deduplicated)

If we naively summed metadata (−1076 s) + prefix (−600 s) = **−1676 s**, we would **double-count ~319 s** of prefix that would have applied to eliminated unit checks.

---

## Package 1: CONSERVATIVE (no verdict-semantics change)

**Levers:** server APC + retention env + per-paper guard tag + unit user-block reorder; dual-pod sharding + per-pod semaphores; LJF scheduling; `asyncio.to_thread` for `screen_pages`/grounding.

**Does NOT include:** metadata short-circuit, router tightening, verdict-first schema, small-judge offload.

### Arithmetic

```
N = 2284          (unchanged)
L = 20 s          (unchanged mean; prefix applied as absolute saving)
S = 32            (dual-pod)
T = 90 − 90 = 0   (LJF)
C = 58 − 30 = 28  (to_thread)
```

| Step | Computation | Wall (s) |
|------|-------------|----------|
| Baseline compute | 2284 × 20 / 16 | 2855 |
| Prefix + reorder (full fleet, low) | −600 | 2255 |
| Dual-pod (halve compute term) | 2855 / 2 | 1427.5 |
| Prefix (absolute, not halved by S) | −600 | 827.5 |
| + T + C | + 0 + 28 | 855.5 |
| Per-pod sem skew guard | −50 (mid) | **~806 s** |

Alternative single-line form:

```
wall = 2284×20/32 + 28 − 600 − 90 − 30 − 50
     = 1427.5 + 28 − 770
     = 685.5 s   (without sem guard: 855 s)
```

**Expected wall: 685–856 s (11.4–14.3 min)**

**Target:** ❌ ≤600 s (10 min), ❌ ≤300 s (5 min)

**Validation effort: LOW–MEDIUM**
- Deploy vLLM PR #43447 + `VLLM_PREFIX_CACHE_RETENTION_INTERVAL=32768` on both pods (`15`, `39`)
- `--shard-pods` + health probe (`21`)
- 48-paper holdout A/B on user-block reorder only (`15`: verdict diff ≤25% band)
- `asyncio.to_thread` — no quality gate
- LJF — no quality gate

---

## Package 2: MODERATE (+ metadata short-circuit + escalation dedupe + verdict-first)

**Adds to CONSERVATIVE:**
- Metadata Tier A+B: skip units on `fail`; on `review` run **1** highest-severity unit (`17`)
- Escalation skip-and-synthesize when unit already scheduled (`18`)
- Pass-path verdict-first output / shrink empty `reasoning` (`14`)

### Arithmetic

```
N₀ = 2284
−847 (metadata Tier A+B) −18 (escalation dedupe) → N = 1419
Remaining unit checks ≈ 663 (1510 − 847)
S = 32
```

| Step | Computation | Cumulative wall (s) |
|------|-------------|---------------------|
| Start | measured | 3003 |
| Call elimination | −847×20/16 = **−1059** | 1944 |
| Escalation | −18×20/16 = **−23** | 1921 |
| Verdict-first (scaled) | −250×(1419/2284) = **−155** | 1766 |
| Prefix on **remaining** only | −[62+219] = **−281** | 1485 |
| Dual-pod on compute | −(1419×20/16)/2 = **−887** … see below | |

Clean recomputation from factors:

```
compute@16 = 1419 × 20 / 16 = 1773.8 s
compute@32 = 886.9 s
prefix_rem = 281 s
verdict_rem = 155 s
T+C after trims = 148 − 90 − 30 = 28 s

wall = 886.9 + 28 − 281 − 155 = 478.9 s
```

Add per-pod sem guard (+50 s conservative friction): **~529 s (8.8 min)**

Round to uncertainty band: **480–530 s (8.0–8.8 min)**

**Target:** ✅ ≤600 s (10 min) at mid estimate; ✅ with margin at low bound; ❌ ≤300 s (5 min)

**Validation effort: MEDIUM**
- All CONSERVATIVE gates
- Metadata Tier A+B: sidecar replay proving **0** papers where `metadata=fail` and units flip verdict (`17`: current count 0); `--inspect` diff review on 19 review papers losing extra quotes
- Escalation dedupe: 9-paper dev-replay (`18`)
- Verdict-first schemas: 48-paper holdout, ≥95% verdict stability, zero `source_ungrounded` increase (`14`)
- **Estimated engineering: ~2–3 weeks** (whisker-local + pod config; no model swap)

---

## Package 3: AGGRESSIVE (+ router tightening + small-judge offload)

**Adds to MODERATE:**
- Router combo_safe: one `table_presence`/paper, drop long `heading_drift`, recall floor 0.85 (`11`)
- Offload unit checks + metadata/outline to `h200-qwen3-32b` (MoE fallback for 8 oversize papers) (`23`)

### Arithmetic

```
N after MODERATE call cuts = 1419
−190 (router) → N = 1229
Remaining unit checks ≈ 473

L_eff on remaining calls:
  82.6% at L=10 s (dense 2× speedup)
  17.4% at L=20 s (monolith/page/tier-2/oversize fallback)
  L_eff = 0.826×10 + 0.174×20 = 11.74 s
```

| Step | Computation | Wall (s) |
|------|-------------|----------|
| Start from baseline | 3003 | 3003 |
| Call elimination total | −(2284−1229)×20/16 = **−1319** | 1684 |
| Router included above | (190 of 1319) | |
| Prefix on remaining | −[54+157] = **−211** | 1473 |
| Verdict-first scaled | −250×(1229/2284) = **−134** | 1339 |
| Compute @ S=32 with L_eff | 1229×11.74/32 = **451** | |
| + T+C | +28 | |
| Subtract L reductions already in L_eff? | No — prefix/verdict are separate from L_eff | |
| **wall** | 451 + 28 − 211 − 134 | **134 s** |

134 s is below physical floor (overhead, variance). Apply friction terms:

- Per-pod sem: +50 s
- MoE variance buffer: +80 s
- Router FN recovery testing delay (not wall, but real): N/A

**Adjusted expected wall: 260–350 s (4.3–5.8 min)**

Conservative sub-estimate (L_eff=13 s, higher prefix overlap):

```
1229×13/32 + 28 − 211 − 134 = 499 − 317 = 182 + 100 friction = 282 s
```

**Target:** ✅ ≤600 s; ✅ ≤300 s at mid estimate (260–350 s band)

**Validation effort: HIGH**
- All MODERATE gates
- Router combo_safe: holdout replay on **6 missed PIDs** (`11`: P3181R1, P4003R0, P4123R0, etc.)
- Small-judge: **381/381 fused verdict parity** + defect_group match on 16 verdict-changing papers (`23`); 8-paper MoE fallback path; `_LANE_VERSION` bump + full cold rerun
- Dual-service fingerprint encodes shard set + offload service (`21`, `23`)
- **Estimated engineering: ~6–10 weeks** (A/B fleet + router tuning + dense pod provisioning)

---

## Summary table

| Package | N | S | Key L levers | Expected wall | ≤600 s? | ≤300 s? | Validation |
|---------|---:|---:|---|---:|---|---|---|
| Baseline | 2284 | 16 | — | 3003 s (50 min) | ❌ | ❌ | — |
| CONSERVATIVE | 2284 | 32 | prefix | **685–856 s** (11–14 min) | ❌ | ❌ | LOW–MED |
| MODERATE | 1419 | 32 | prefix + verdict-first | **480–530 s** (8–9 min) | ✅ | ❌ | MED |
| AGGRESSIVE | 1229 | 32 | prefix + verdict + dense offload | **260–350 s** (4–6 min) | ✅ | ✅ (mid) | HIGH |

---

## What does NOT reach target (explicit rejects)

| Lever | Modeled saving | Why excluded from packages |
|-------|-------------|---------------------------|
| In-paper parallel unit checks | ~0 s fleet | Same N, slot-saturated (`20`) |
| Unit batching | ~400–500 s theoretical | Double-digit detection loss (`12`) |
| Payload scoping alone | ~198 s | Overlaps prefix (`13`) |
| Monolith removal | ~200–400 s | Verdict-semantics / coverage change (`16`) |
| Full metadata skip (no review representative) | Saves +250 s vs Tier A+B | Inspect + human triage regression (`17`) |
| Client concurrency >32 | negative | Proxy 524s (`27`, `28`) |
| Server max-num-seqs 32 | +60% wall | Measured regression (`00-baseline.md:82`) |

---

## False-pass hypothesis

Stack MODERATE with naive prefix accounting: apply full **−600 s** prefix on top of **−1059 s** metadata elimination without rescaling unit-check reorder savings. Model predicts **~339 s** (false 5-min win). A live run lands **~530–650 s** because ~300 s of prefix savings were phantom on calls metadata already removed — operators conclude "speedup plan failed" when arithmetic was double-counted.

## False-fail hypothesis

AGGRESSIVE small-judge offload without MoE fallback for 8 oversize papers (`23`: >104k effective tokens): those papers hit `PdfLaneError` / truncation, tombstone to `error`, warm rerun re-executes full cascade — wall time **increases** vs MODERATE while verdict mix looks "stricter."

## What would change my mind

One instrumented cold run with per-call `{call_type, prompt_tokens, cached_tokens, wall_s, pod_id}` logging, executing MODERATE stack exactly, showing measured wall within **±15%** of the **529 s** model (i.e. 450–610 s). If measured wall **>650 s**, the prefix+metadata overlap is larger than modeled and AGGRESSIVE becomes mandatory for 10 min, not optional.
