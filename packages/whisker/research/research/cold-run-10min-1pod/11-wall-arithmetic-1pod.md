# 11 - Wall-Arithmetic Rebuilder (single pod, twin forbidden)

**Date:** 2026-07-24  
**Hard constraint:** `S_eff = 16` forever. No `h200x8-deepseek-v4-pro`. No second DeepSeek-V4-Pro replica.  
**Goal:** Cold `whisker-tapetum-llm` fleet 381 papers → **≤600 s (~10 min)** on `alliance-pod` only.  
**Baseline:** **3003 s** measured v10 cold run (`research/tapetum-llm-speedup/00-baseline.md`, `research/cold-run-10min/11-wall-arithmetic.md`).

**Verdict:** **≤600 s is NOT reachable on one pod at planning-grade confidence.**  
**Central estimate (full single-pod stack):** **~680 s** (148 pessimistic AGGRESSIVE path).  
**Honest floor:** **~680–715 s** with friction; bare optimistic **~585 s** requires unvalidated AGGRESSIVE quality gates and zero friction — not shippable as a target.

**Confidence:** medium-high (reconciled from `cold-run-10min/11-wall-arithmetic.md`, `22-path-a-b-10min.md`, `48-combined-lever-modeler.md`; no live stacked cold run on v11 + AGGRESSIVE).

---

## Wall model (non-negotiable)

```
wall = (N_rem × L_eff) / S_eff + T + C − L_abs
```

| Symbol | Value | Source |
|--------|------:|--------|
| N₀ | 2284 | ~6 calls/paper, 381 papers |
| L (MoE baseline) | ~20 s/call | Closes 3003 s @ S=16 |
| **S_eff** | **16** | `--max-num-seqs 16`; **32 forbidden** (+57% wall) |
| T + C | 148 s → **28 s** after LJF + `to_thread` | `48-combined-lever-modeler.md` |
| L_abs | prefix + verdict-first (absolute; **not** halved by S) | Rescaled to survivor mix |

**Stacking rules** (from `48-combined-lever-modeler.md:58-89`):

1. Apply **N cuts first** (metadata short-circuit, deterministic metadata, router, cap).
2. Apply **L_abs** only on **survivors** — do not sum full-fleet prefix/verdict on calls metadata already removed.
3. Apply **L_eff** (dense offload, MTP) on remaining call mix.
4. **S_eff fixed at 16** — no silent S=32, no twin shard.

---

## Lever inventory (single-pod only)

| Lever | Status @ HEAD | Calls / latency | Est. Δwall @ S=16 | Overlap |
|-------|---------------|-----------------|------------------:|---------|
| **v11 metadata short-circuit** | Working tree (uncommitted) | −847 to −1047 calls | **−1059 to −1331 s** | Base N cut; 847–1047 are ~100% unit checks |
| **Escalation dedupe (P18)** | Not implemented | −3 to −18 calls | **−4 to −23 s** | ~15 esc already skipped by #1 |
| **Deterministic metadata diff** | Not implemented | −377 LLM calls | **−471 s** | Independent; replaces metadata LLM, not units |
| **Router combo_safe trim** | Not implemented | −63 to −190 calls (scaled) | **−79 to −238 s** | Mostly pass-tier units; LOW overlap with metadata fail set |
| **MAX_UNIT_CHECKS 5→3** | Not implemented | −154 to −502 calls (scaled) | **−193 to −628 s** | HIGH with metadata cut; A/B gated |
| **Dynamic quota (hypothesis)** | Not implemented | ~−160 to −320 calls | **−200 to −400 s** | Preferred over blind cap 3 (`58-max-unit-checks-knob.md`) |
| **Prefix/HMAC + unit reorder** | **Partial** (PDF lane) | Prefill reuse calls 2–6 | **−225 to −281 s** scaled | HIGH with metadata cut; HTML lane gap |
| **Verdict-first + pass max_tokens** | Not implemented | ~55→~10 tok pass path | **−124 to −155 s** scaled | HIGH with metadata cut |
| **Dense unit-check offload (`h200-qwen3-32b`)** | Not implemented | L=20→~10 on ~82.6% calls | **L_eff 11.74 s** on offload mix | HIGH with cap/router; quality unproven |
| **Server MBT 16384 + APC retention** | Ops (partial) | Scheduling / KV | **−60 to −180 s** | Overlaps prefix envelope |
| **Server MTP k=1 + DeepEP/DBO** | Ops A/B | Decode ~1.15–1.5× | **−120 to −470 s** | Overlaps prefix/decode; not in central stack |
| **Fail-fast retries** | Not implemented | ~55→~30 retries | **−45 to −80 s** | Independent (~3% baseline) |
| **LJF + `to_thread`** | Implemented | T + C trim | **−120 s** | Already in T+C baseline adjustment |
| ~~Dual-pod shard~~ | **FORBIDDEN** | S: 16→32 | ~~−887 s on MODERATE remainder~~ | Out of scope |

---

## Stacked table (3003 s → single pod)

Cumulative wall applying levers in dependency order. Savings are **overlap-adjusted** where noted.

| Step | Lever | ΔN | Δwall (s) | Cumulative wall (s) | Notes |
|-----:|-------|-----:|----------:|----------------------:|-------|
| 0 | **Baseline v10** | 2284 | — | **3003** | Measured |
| 1 | v11 metadata short-circuit (full fail+review skip) | −1047 | **−1331** | **1672** | Working tree; Tier A+B (−847/−1059) is conservative bound |
| 2 | Escalation dedupe (P18) | −3 | **−4** | **1668** | ~15 esc already in #1 (`48-escalation-waste.md`) |
| 3 | Deterministic metadata diff | −377 | **−471** | **1197** | 377 calls × 20/16; AGGRESSIVE (`131-surya-model-sizing.md`) |
| 4 | Router combo_safe (post-cut scale) | −63 | **−79** | **1118** | 190 × (523/1570) scaled (`50-router-false-economy.md`) |
| 5 | MAX_UNIT_CHECKS 5→3 (post-cut scale) | −154 | **−193** | **925** | 502 × (463/1510); **MEDIUM–HIGH quality risk** |
| 6 | Prefix/HMAC + APC/MBT (survivors) | — | **−281** | **644** | Rescaled from 600 s full-fleet (`11-wall-arithmetic.md:40-41`); partial HTML gap |
| 7 | Verdict-first + pass max_tokens | — | **−155** | **489** | Scaled 250 × (1419/2284); schema not at HEAD |
| 8 | Dense unit offload (`h200-qwen3-32b`) | — | **−150** | **339** | Net compute after L_eff; replaces naive #7+#5 unit L overlap |
| 9 | Server MTP k=1 + DeepEP/DBO (net) | — | **−120** | **219** | Net after overlap with #6; not full 300–550 s ops envelope |
| 10 | Fail-fast retries | — | **−55** | **164** | v11 projected ~30 retries (`28-retry-failfast.md`) |
| — | **+ Realistic friction** | — | **+130 to +230** | **294–394** | MoE variance, dense A/B skew, router FN buffer (`22-path-a-b-10min.md:115-116`) |

**Naive cumulative (steps 0–10, no friction): ~164 s** — below physical floor; friction row restores honesty.

---

## Package rollups @ S_eff = 16 (twin forbidden)

### MODERATE (software, no AGGRESSIVE)

**Levers:** v11 short-circuit + escalation dedupe + verdict-first + prefix (partial) + LJF/`to_thread`.

| Estimate | N_rem | Central wall (s) | Range (s) | ≤600 s? |
|----------|------:|-----------------:|----------:|:-------:|
| Tier A+B short-circuit (148 pess.) | 1419 | **1493** | 1420–1550 | ❌ |
| Full skip v11 (working tree) | 1219 | **~1243** | 1115–1270 | ❌ |
| Full skip + verdict-first + prefix | 1219 | **~906** | 850–980 | ❌ |

Compute term alone on 1419 calls: `1419 × 20 / 16 = **1774 s**` — exceeds 600 s before any latency lever.

### AGGRESSIVE (+ deterministic metadata, router, cap/dynamic, dense offload)

**Levers:** MODERATE N/L cuts + deterministic metadata + router + dense offload on unit+metadata survivors.

Recomputation from `48-combined-lever-modeler.md:197-234` and `22-path-a-b-10min.md:106-124` @ **S=16**:

```
N_rem = 1229  (after metadata −847, esc −18, router −190)
         −377 deterministic metadata → 852 calls (if stacked additively)

L_eff = 0.826×10 + 0.174×20 = 11.74 s  (dense hypothesis on offloadable mix)

compute@16 = 1229 × 11.74 / 16 = 902 s
L_abs (prefix + verdict, scaled) = 345 s (48) | 290 s (148 pess.)
T + C = 28 s (48) | 68 s (148)

wall (48 optimistic) = 902 + 28 − 345 = 585 s  (bare)
wall + friction (+130) = 715 s

wall (148 pessimistic) = 902 + 68 − 290 = 680 s  (central)
wall + friction (+230) = 910 s
```

| Configuration | Central (s) | Range (s) | ≤600 s? |
|---------------|------------:|----------:|:-------:|
| AGGRESSIVE bare (48) | **585** | 550–620 | ⚠️ hairline |
| AGGRESSIVE + friction (48) | **715** | 650–780 | ❌ |
| AGGRESSIVE planning (148) | **680** | 620–760 | ❌ |
| AGGRESSIVE + friction (148) | **910** | 780–950 | ❌ |

### MAX_UNIT_CHECKS sensitivity (single pod, post-v11)

| Cap | ΔN (fleet central) | Δwall @ S=16 | Post-short-circuit Δwall |
|-----|-------------------:|-------------:|-------------------------:|
| Keep 5 | 0 | 0 | 0 |
| Cap 3 | −502 | **−628** | **−193** (scaled) |
| Dynamic quota | ~−250 | **−313** | **−200 to −400** (hypothesis) |

Cap 3 alone on raw baseline leaves **~2375 s** — insufficient for 10 min (`58-max-unit-checks-knob.md:75`).

---

## Server-only delta (ops, no whisker deploy)

From `26-server-ops-checklist.md`: MBT 16384, APC + retention (#43447), MTP k=1, DeepEP/DBO, CUDA graphs.

| Server bundle | Est. Δwall @ S=16 | Overlap |
|---------------|------------------:|---------|
| MBT + APC + retention | **−60 to −180 s** | Overlaps client prefix (#6) |
| MTP k=1 (acceptance ≥70%) | **−120 to −470 s** | Decode-only; JSON+reasoning version-sensitive |
| DeepEP low-latency + DBO | **−50 to −150 s** | Independent of seq slots (`64-flashinfer-moe-kernels.md`) |
| **Combined ops (net unique)** | **−120 to −200 s** | Do not sum full 550 s on top of prefix stack |

Server flags **do not** close the ~800–900 s gap MODERATE leaves vs 600 s (`26-server-ops-checklist.md:8`).

---

## Gap analysis: why 600 s needs ~887 s we cannot have

| Missing multiplier | Effect @ MODERATE remainder | Seconds lost |
|--------------------|----------------------------|-------------:|
| Twin pod S: 16→32 | Halves compute on 1419 calls | **~887 s** |
| Forbidden `--max-num-seqs 32` | +57% wall measured | **+1700 s** (wrong direction) |

Single-pod MODERATE after all honest N+L cuts: **~906–1243 s** depending on short-circuit tier.  
Gap to 600 s: **~306–643 s** — exactly the class dense offload + AGGRESSIVE N cuts address, but **148 pessimistic AGGRESSIVE still lands ~680 s**.

---

## Findings

- [CRITICAL] **Compute floor @ S=16 blocks ≤600 s for MODERATE.** `1419 × 20 / 16 = 1774 s` compute alone (`22-path-a-b-10min.md:66-67`). No N/L lever stack on MODERATE closes ~1174 s gap to 600 s.

- [CRITICAL] **Twin removal costs ~887 s** — the largest single term in the dual-pod MODERATE stack (`11-wall-arithmetic.md:126-127`). All single-pod plans must recover this via call elimination + L_eff, not S.

- [CRITICAL] **AGGRESSIVE single-pod central ~680 s (148)** — misses 600 s by **~80 s** at planning grade; with friction **~715–910 s** (`22-path-a-b-10min.md:119-124`). Bare 585 s is not planning-grade.

- [HIGH] **v11 metadata short-circuit (working tree) is the largest landed N cut: −1059 to −1331 s.** Expected single-pod wall after v11 alone: **~21–25 min** (`cold-run-10min/SYNTHESIS.md:46`, `10-impl-status-auditor.md:59`).

- [HIGH] **Deterministic metadata (−471 s) is the cheapest AGGRESSIVE N cut** but requires A/B that LLM adds no findings (`131-surya-model-sizing.md`).

- [HIGH] **Dense offload L cut is necessary but not sufficient.** `h200-qwen3-32b` at 2× on 82.6% of calls; MoE leg still ~620–710 s without dual-pod (`16-dense-judge-candidates.md:68-69`). Quality: **381/381 parity gate unrun**.

- [MED] **MAX_UNIT_CHECKS 5→3 saves ~−628 s raw / ~−193 s post-short-circuit** — meaningful but **MEDIUM–HIGH recall risk**; dynamic quota preferred (`58-max-unit-checks-knob.md`).

- [MED] **Prefix/HMAC partial on PDF lane; HTML/text lane still gaps** (`12-prefix-cache-code-auditor.md:20-21`). Full envelope unmeasured post-v11.

- [LOW] **Escalation dedupe + fail-fast are hygiene (~4 + ~55 s)** — not 10 min levers (`48-escalation-waste.md`, `28-retry-failfast.md`).

---

## False-pass hypothesis

Ship naive stacked table (steps 0–10, no friction, no overlap rescale): model predicts **~164–339 s**. Live run lands **~700–900 s** because (1) AGGRESSIVE quality gates fail and dense offload reverts to MoE L=20, (2) friction +130–230 s omitted, (3) prefix/verdict double-counted on eliminated unit calls. Operators conclude single-pod optimization "failed" when honest floor was never ≤600 s.

## False-fail hypothesis

Reject all call elimination because twin is dead: stay at **~3003 s** when v11 short-circuit alone delivers **~1672 s (~28 min)** and full MODERATE software **~906–1243 s (~15–21 min)** without any infra spend.

## What would change my mind

Instrumented single-pod cold run @ S=16 with `{call_type, N_rem, L_eff, cached_tokens, wall_s}` logging, executing full AGGRESSIVE stack with deterministic metadata + dense offload + all ops flags. Measured wall **≤620 s** upgrades verdict to **reachable-with-conditions**. Measured **>750 s** confirms **~680 s floor**.

---

## Executive answer (for parent agent)

| Field | Value |
|-------|-------|
| **Baseline** | **3003 s** measured v10 |
| **S_eff** | **16** (fixed; twin forbidden) |
| **≤600 s reachable?** | **No** (planning-grade) |
| **Central seconds (full single-pod stack)** | **~680 s** (148 AGGRESSIVE @ S=16) |
| **Honest floor (if no)** | **~680–715 s** central band; range **585–910 s** (bare optimistic → pessimistic+friction) |
| **Best realistic single-pod target** | **~23 min** (MODERATE software) to **~11–12 min** (AGGRESSIVE validated) |
| **What would flip to yes** | Measured instrumented AGGRESSIVE cold run **≤620 s**, or new S multiplier (forbidden twin or seq-32) |

---

Sources: `research/cold-run-10min-1pod/00-baseline.md`, `research/cold-run-10min/{11-wall-arithmetic,22-path-a-b-10min,10-impl-status-auditor,12-prefix-cache-code-auditor,17-metadata-shortcircuit-design,48-escalation-waste,47-max-tokens-shrink,50-router-false-economy,58-max-unit-checks-knob,16-dense-judge-candidates,26-server-ops-checklist,28-retry-failfast,05d-web-mtp-specdecode,64-flashinfer-moe-kernels}.md`, `research/tapetum-llm-speedup/48-combined-lever-modeler.md`.
