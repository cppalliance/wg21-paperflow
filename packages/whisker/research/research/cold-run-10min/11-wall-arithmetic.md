# 11 - Wall-Arithmetic Rebuilder

**Verdict:** usable-with-conditions — MODERATE (CONSERVATIVE + call elimination + verdict-first) reaches **~596 s central (530–670 s)** on the measured **3003 s** baseline, but **only with dual-pod sharding**; without `h200x8-deepseek-v4-pro`, the same lever set stays **~1490–1570 s** and cannot hit ≤600 s.
**Confidence:** medium-high (reconciled from `148-verifier-stacking-arithmetic.md` + `48-combined-lever-modeler.md`; no live stacked cold run yet)

## Baseline anchor

| Source | Wall (s) | Notes |
|--------|----------|-------|
| **Measured v10 cold fleet** | **3003.4** | `tapetum-llm-speedup/00-baseline.md:17-18` — **use this for arithmetic** |
| SYNTHESIS package table | 2903 | Rounded header in `SYNTHESIS.md` §3; **does not close** `2284×20/16 + 148` |
| Throughput footer | 2883–2886 | Alternate accounting path (`cold-run-10min/00-baseline.md:19`) |

**Chosen baseline: 3003 s** (measured). Closure check: `N=2284`, `L=20 s`, `S=16`, `T+C≈148 s` → `2284×20/16 + 148 = 3003 s` ✓ (`48-combined-lever-modeler.md:31`).

SYNTHESIS **2903 s** is cited in the package table for historical continuity; all lever seconds below are rescaled against **3003 s**.

## Stacking method (non-negotiable)

```
wall = (N_rem × L) / S_eff + T + C − L_abs
```

1. Apply **N cuts first** (metadata short-circuit, escalation dedupe).
2. Apply **L_abs** (prefix cache, verdict-first) on the **surviving call mix only** — do not sum full-fleet prefix/verdict estimates on calls metadata already removed.
3. Apply **S multiplier** (dual-pod) to the compute term only; **L_abs does not halve** when S doubles.
4. Apply **T/C trims** (LJF, `to_thread`) additively on the remainder.

**Critical overlap:** metadata Tier A+B removes **847 unit checks** (~100% of eliminated calls are units, `17-metadata-short-circuit.md`). Short-circuit therefore removes calls that verdict-first and unit-block prefix reorder would also have shrunk. Naive sum of metadata (−1059 s) + full-fleet prefix (−600 s) double-counts **~319 s** of phantom prefix on dead calls (`48-combined-lever-modeler.md:89`).

## Lever table (CONSERVATIVE + MODERATE only)

All savings measured against **3003 s baseline @ S=16** unless noted. **AGGRESSIVE levers excluded** (deterministic metadata diff, router tightening, dense-judge offload).

| Lever | Package | Calls removed / latency reduced | Est. wall saving (s) | Overlap note |
|-------|---------|--------------------------------|---------------------|--------------|
| **Metadata Tier A+B short-circuit** | MODERATE | **−847 calls** (141 fail-only + 706 review→1 unit); N: 2284→1437 | **−1059** compute @ S=16 (`847×20/16`) | **Removes 663/1510 surviving unit checks' worth of prefix + ~66% zero-defect decode** that verdict-first would have targeted. Tier C full skip (−1047 / −1331 s) excluded — inspect regression. |
| **Escalation skip-and-synthesize** | MODERATE | **−18 calls** (PDF page-esc dedupe) | **−23** @ S=16 | Low overlap; PDF-only; independent of metadata fail/review set. |
| **Verdict-first / pass-path reasoning shrink** | MODERATE | ~55 tok → ~10 tok on pass-path unit checks; decode −2–4 s/call on survivors | **−155** scaled (`250×1419/2284`); range **−124 to −155** | **HIGH overlap with short-circuit:** full-fleet −250 s is wrong; 847 eliminated unit checks included ~692 zero-defect calls (`17`: 66.1%) that verdict-first would shrink. Apply only to **N_rem=1419**. |
| **Prefix cache envelope** (per-paper HMAC guard tag + unit user-block reorder + server APC + MBT 16384 + retention env) | CONSERVATIVE | Prefill reuse on calls 2–6 per paper; static system suffix shared | **−550 to −600** full fleet @ S=16 (`15-prefix-cache-enabler.md` low bound); **−225 to −281** after metadata rescale (`500×663/1510` unit reorder + static APC × `1419/2284`) | **HIGH overlap with short-circuit:** unit-block reorder base ~500 s → **219 s** on 663 remaining unit checks, not 500 s. Monolith/metadata/page calls unchanged (663+756 non-unit ≈ 1419). |
| **Dual-pod shard** (`alliance-pod` + `h200x8-deepseek-v4-pro`, per-pod Semaphore(16)) | CONSERVATIVE | S: 16→32 effective; halves compute term | **−887** on MODERATE remainder (`1419×20/32` vs `/16`); **−1428** on CONSERVATIVE full N | **Independent of N/L_abs accounting** but **required for ≤600 s**. Prefix/verdict absolute seconds unchanged by S. Skew friction **+75–125 s** if per-pod caps missing (`148`); sem guard **−50 s** in optimistic stack (`48`). |
| **LJF paper scheduling** | CONSERVATIVE | Tail scheduling; heavy papers start earlier | **−60 to −90** on T | None with call-count levers. |
| **`asyncio.to_thread` (screen_pages / grounding)** | CONSERVATIVE | Event-loop unblocking | **−30 to −60** on C | None with call-count levers. |
| **Monolith `wait_for` timeout** | CONSERVATIVE | Tail-risk removal (hang → fail fast) | Not in cold arithmetic (0 s on tonight's fleet; `26-timeout-budget-auditor`) | Prevents **+1200 s** tail outliers; mean wall unchanged. |
| **Tombstone fingerprints + `--retry-errors`** | CONSERVATIVE | Warm skip for error papers | **0 s cold**; **~50 s warm** (`46-warm-run-auditor`) | Out of scope for cold-wall target. |
| **MTP speculative decode** | MODERATE (A/B-gated) | Decode 1.49× on MoE | **+220 to +470** optional upside (`38-speculative-decoding-scout`) | **Not in central 596 s** (`148` / `48` stacks omit MTP). Could tighten low band if A/B passes. |

### Overlap worked example (short-circuit vs verdict-first vs prefix)

| Naive (wrong) | Correct (MODERATE) |
|---------------|-------------------|
| Metadata −1059 + prefix −600 + verdict −250 = **−1909 s** | Metadata −1059 + prefix **−281** + verdict **−155** = **−1495 s** on compute+latency terms before dual-pod |
| Phantom **~414 s** from counting prefix/verdict on 847 dead unit calls | Rescale ratios: prefix `663/1510`, verdict `1419/2284` |

## Package rollups

### CONSERVATIVE (no verdict-semantics change)

**Levers:** dual-pod + prefix/APC + LJF + `to_thread` + monolith timeout + server flags. **Excludes:** metadata short-circuit, verdict-first, MTP, AGGRESSIVE.

| Configuration | N | S | Central wall (s) | Range (s) | ≤600 s? |
|---------------|--:|--:|-----------------:|----------:|:-------:|
| Single-pod | 2284 | 16 | **~2370** | 2280–2450 | ❌ |
| Dual-pod | 2284 | 32 | **~945** | 860–1020 | ❌ |

Arithmetic (dual-pod, planning / `148` pessimistic): `2284×20/32 + 68 − 550 + 100 friction ≈ 945 s`.

Optimistic (`48`): **685–856 s** (11–14 min) with sem guard as saving — still **above 600 s** at central estimate.

### MODERATE (CONSERVATIVE + metadata + escalation + verdict-first)

**Adds:** metadata Tier A+B, escalation dedupe, pass-path verdict-first. **Excludes:** AGGRESSIVE (metadata diff, router, dense offload). MTP optional, not in central.

| Configuration | N | S | Central wall (s) | Range (s) | ≤600 s? |
|---------------|--:|--:|-----------------:|----------:|:-------:|
| Single-pod | 1419 | 16 | **~1493** | 1420–1570 | ❌ |
| Dual-pod | 1419 | 32 | **~596** | 530–670 | ✅ (planning band) |
| Dual-pod optimistic (`48`) | 1419 | 32 | **~529** | 480–530 | ✅ (margin) |

Step rebuild (dual-pod, `48` method, optimistic central):

```
N: 2284 − 847 − 18 = 1419
Call elimination:  −1059 − 23 = −1082 s  → 1921 s
Verdict-first:     −155 s (scaled)         → 1766 s
Prefix remaining:  −281 s                  → 1485 s  (compute@16 = 1774 s)
Dual-pod:          compute@32 = 887 s      → 887 + 28 − 281 − 155 ≈ 479 s
Sem/friction:      +50 s                   → ~529 s
```

Planning central (`148` pessimistic): **~596 s** (+12% vs optimistic; lower prefix/verdict savings, higher T+C retention, +75 s skew friction).

## Target gate: ≤600 s cold wall

| Question | Answer |
|----------|--------|
| **≤600 s without dual-pod?** | **No.** Single-pod MODERATE ≈ **1493 s (~25 min)** even after −1082 s of call cuts and −436 s of latency levers. Compute term `@ S=16` on 1419 calls alone is **1774 s**. |
| **≤600 s with dual-pod?** | **Yes (planning).** MODERATE central **596 s**, range **530–670 s** (~9–11 min). Low band touches 600 s; MTP A/B (+220–470 s) improves margin but is not counted in central. |
| **CONSERVATIVE alone ≤600 s?** | **No.** Best case ~685 s optimistic; planning ~945 s. Needs MODERATE call elimination. |

## Dual-pod dependency and twin-pod-dead failure mode

**Dependency: YES** for the ≤600 s cold-wall target under CONSERVATIVE+MODERATE levers.

`21-dual-pod-sharder.md`: pre-gather health probe on `alliance-pod` and `h200x8-deepseek-v4-pro`. If **≥1 pod live**, run on `live_pods` (single pod gets all papers, warning logged). If **0 live**, exit 1.

**When twin pod (`h200x8-deepseek-v4-pro`) is dead:**

| What breaks | Effect |
|-------------|--------|
| Effective **S drops 32→16** | Compute term **doubles**; MODERATE wall **~596 s → ~1493 s** |
| **≤600 s target** | **Misses by ~2.5×** — looks like "speed program failed" if operators do not check pod health |
| Sharding assignment | All 381 papers on `alliance-pod`; no connection errors if fallback works (`21`: avoids 404 half-dead round-robin) |
| Fingerprint / warm skip | Shard **set** in fingerprint; toggling dual↔single forces one cold pass (expected) |
| Prefix cache | Per-pod APC state; no cross-pod KV sharing — perf only, not correctness |
| Quality | Same model weights; second variance axis removed — within existing advisory drift budget |

**What still works on one pod:** metadata short-circuit, prefix reorder, verdict-first, LJF, `to_thread` — all client-side or single-pod server config. **What is lost:** the **~887 s** compute-term halving on the MODERATE remainder. No software fallback replaces a second H200.

Historical note: `h200x8-deepseek-v4-pro` returned **404** in one probe (`21-dual-pod-sharder.md:12`, `llm-batching/18-load-splitter.md:8`) while `alliance-pod` was healthy — dual-pod is **infra-conditional**, not guaranteed.

## Findings

- [CRITICAL] **3003 s is the closure baseline; 2903 s is a SYNTHESIS rounding artifact.** Evidence: `tapetum-llm-speedup/00-baseline.md:17`, `48-combined-lever-modeler.md:31`. Impact: rescaling `%` savings from sidecar denominator 2362 (`17`) to wall-closed N=2284 shifts metadata cut **~1059 s**, not 1076 s.

- [CRITICAL] **MODERATE reaches ≤600 s only with dual-pod.** Evidence: `148-verifier-stacking-arithmetic.md:34,51`; single-pod rebuild `1419×20/16 + 68 − 349 ≈ 1493 s`. Impact: **~887 s** of the MODERATE stack is slot doubling, not call elimination.

- [CRITICAL] **Short-circuit must precede prefix/verdict rescaling.** Evidence: `48-combined-lever-modeler.md:58-89`; 847/847 eliminated calls are unit checks. Impact: naive stacking overstates savings by **~300–420 s** and predicts false **~339 s** walls.

- [HIGH] **CONSERVATIVE alone cannot reach 10 min.** Evidence: `148` central **945 s** (860–1020); `48` optimistic **685–856 s**. Impact: metadata Tier A+B (−1059 s @ S=16) is mandatory for sub-600 s even with dual-pod.

- [HIGH] **Twin-pod-dead fallback is safe but slow.** Evidence: `21-dual-pod-sharder.md:12-13`. Impact: 0× sharding savings; MODERATE degrades to **~25 min**, not error-storm if health gate works.

- [MED] **MTP in SYNTHESIS MODERATE list is not in central 596 s.** Evidence: `SYNTHESIS.md:51` vs `148`/`48` stacks. Impact: optional **220–470 s** upside if A/B-gated; not required for planning gate.

- [MED] **Tier C metadata full skip (−1047 calls / −1331 s) stays out of MODERATE.** Evidence: `17-metadata-short-circuit.md:16`; inspect regression on 19 review papers. Impact: extra **~200 calls / ~250 s** left on table vs full skip.

## False-pass hypothesis

Ship MODERATE using optimistic **529 s** central without dual-pod health monitoring: live run on dead twin pod lands **~1400–1600 s**; operators disable metadata short-circuit as "broken" and revert to CONSERVATIVE **~945 s**, losing real **~350 s** from verified call cuts (`148-verifier-stacking-arithmetic.md:76-77`).

## False-fail hypothesis

Reject metadata short-circuit because single-pod wall is **~1493 s**: conclude call elimination "does not work" when the missing lever is **S=32**, not N — dual-pod restores **~596 s** (`148-verifier-stacking-arithmetic.md:80-81`).

## What would change my mind

Instrumented MODERATE cold run with `{call_type, N_rem, pod_id, cached_tokens, wall_s}` logging: measured wall **450–620 s** upgrades central to `48` optimistic band; measured **>700 s** on both live pods forces AGGRESSIVE tier or MTP for reliable ≤600 s.

---

## Executive summary (for parent agent)

| Field | Value |
|-------|-------|
| **Baseline used** | **3003 s** measured (2903 s = SYNTHESIS round; do not use for closure) |
| **Central estimate (MODERATE + dual-pod)** | **596 s** |
| **Range** | **530–670 s** (optimistic low **~480–530 s** if friction matches `48`) |
| **Dual-pod dependency** | **YES** — without twin pod, central **~1493 s**; ≤600 s not achievable on CONSERVATIVE+MODERATE alone |
| **≤600 s achievable?** | **With dual-pod: yes** (planning). **Without: no.** |
