# Delta from dual-pod Path A — twin ban, numbers

**Date:** 2026-07-24  
**Constraint:** No second DeepSeek-V4-Pro (`ADR-001`). `S_eff` stays **16**.  
**Baseline:** measured v10 cold **3003 s** (N=2284, L≈20 s, S=16, T+C≈148). Alternate footers 2883–2903 s are the same fleet class.

Sources: `research/cold-run-10min/{SYNTHESIS,11-wall-arithmetic,22-path-a-b-10min}.md`, `research/tapetum-llm-speedup/SYNTHESIS.md`, `../11-wall-arithmetic-1pod.md`.

---

## 1. What the twin ban removes

Dual-pod Path A treated two identical MoE replicas as one lever:

| Parameter | Dual-pod (Path A) | Twin banned (this program) |
|-----------|-------------------|----------------------------|
| Pods | `alliance-pod` + `h200x8-deepseek-v4-pro` | `alliance-pod` only |
| Effective slots `S_eff` | **32** (Semaphore(16) × 2) | **16** |
| Twin status (Jul-24) | Planned revive (HTTP **404** today) | **Forbidden** even if revived |

Everything else in MODERATE (metadata short-circuit, escalation dedupe, verdict-first, prefix/HMAC, LJF, `to_thread`) still applies on one pod. Only the **S multiplier** is gone.

---

## 2. The ~887 s figure (explicit)

On the MODERATE survivor mix after N cuts:

```
N_rem = 2284 − 847 − 18 = 1419   # metadata Tier A+B + escalation dedupe
L     ≈ 20 s/call
```

| Term | Formula | Seconds |
|------|---------|--------:|
| Compute @ S=16 | `1419 × 20 / 16` | **1774** |
| Compute @ S=32 | `1419 × 20 / 32` | **887** |
| **Delta (twin removes this saving)** | `1774 − 887` | **~887** |

So: dual-pod does **not** "save 887 s from the 3003 s baseline" by itself. It **halves the post-MODERATE compute term**. Losing the twin puts that **~887 s** back on the wall.

CONSERVATIVE (no metadata cut, full N=2284) would lose more on a dual→single flip (`2284×20/16 − 2284×20/32` ≈ **1428 s** compute-term delta). Planning uses the MODERATE remainder figure because Path A always stacked dual-pod **after** call elimination.

---

## 3. Package walls: dual-pod vs 1-pod

Overlap-adjusted stacks from `cold-run-10min/11-wall-arithmetic.md` (planning / 148-pessimistic central).

### MODERATE (short-circuit + escalation + verdict-first + prefix rescale + T/C trim)

| Config | `S_eff` | Central wall | Range | ≤600 s? |
|--------|--------:|-------------:|------:|:-------:|
| **Path A (dual-pod)** | 32 | **~596 s** (~9–11 min) | 530–670 | ✅ planning |
| **Twin banned** | 16 | **~1493 s** (~25 min) | 1420–1570 | ❌ |

| Comparison | Value |
|------------|------:|
| Absolute gap (central) | **1493 − 596 ≈ 897 s** (~**887 s** compute term; rest is T/C / friction bookkeeping) |
| Relative | Single-pod MODERATE is **~2.5×** dual-pod MODERATE |
| Dual-pod optimistic central (`48` stack) | ~529 s → single-pod analogue stays **~1.4–1.5 ks** class |

Rough rebuild (dual-pod optimistic, for intuition):

```
After N cuts + verdict + prefix @ S=16:  ~1485 s class (compute@16 = 1774, minus L_abs)
Dual-pod: compute@32 = 887  →  ~479–596 s after T/C / friction
Without twin: stay on ~1490 s path
```

### CONSERVATIVE (prefix/APC + dual-pod + stalls; no short-circuit)

| Config | Central (planning) | Optimistic band | ≤600 s? |
|--------|-------------------:|----------------:|:-------:|
| Dual-pod | ~945 s | 685–856 s | ❌ |
| Single-pod | ~2370 s | — | ❌ |

Twin ban does not turn CONSERVATIVE into a 10 min plan; call elimination was already required even with S=32.

### Headline supersessions from `cold-run-10min/SYNTHESIS.md`

| Prior claim | After twin ban |
|-------------|----------------|
| "10 min reachable with MODERATE + dual-pod (~596 s)" | **Superseded** as ship path |
| "Revive twin or accept ~20–25 min single-pod floor" | Twin option **closed** → accept **~23–25 min** MoE-only MODERATE, or change architecture |
| Day 3: bring twin + `--shard-pods` | **Out of scope** |

---

## 4. What still lands without the twin

Approximate single-pod savings vs 3003 s (same N/L levers; no S boost):

| Lever class | Est. Δwall @ S=16 | Notes |
|-------------|------------------:|-------|
| Metadata Tier A+B short-circuit | **−1059 s** | −847 calls; v11 working tree |
| Escalation dedupe | **−23 s** (or ~−4 s if short-circuit already ate most) | Small |
| Verdict-first (survivor-scaled) | **−124 to −155 s** | Overlaps short-circuit if naively summed |
| Prefix/HMAC (survivor-scaled) | **−225 to −281 s** | HTML lane still partial |
| LJF + `to_thread` | **−90 to −150 s** on T+C | Mostly landed |
| **Dual-pod** | ~~**−887 s**~~ | **Removed** |

Expected after shipping/running v11 alone (single pod): **~21–25 min**, not 48 and not 10. Full MODERATE software without twin: **~1490 s** central.

---

## 5. How to recover ~887 s without a twin

S=32 on one MoE pod is **forbidden** (measured **+57%** wall). Wider EP on the existing 8×H200 node does **not** double `S_eff`; even a generous 1.2–1.5× decode cut leaves MODERATE remainder **~1000–1250 s**.

Substitutes that attack **L** and **N**, not MoE S:

| Substitute | Role vs −887 s | Planning note |
|------------|----------------|---------------|
| Dense unit/metadata offload (`h200-qwen3-32b` etc.) | Parallel queue: `wall = max(T_moe, T_dense)` | Primary ≤10 min candidate; quality A/B required |
| Deterministic metadata (drop 377 LLM calls) | **−471 s** @ S=16 | AGGRESSIVE |
| Router / dynamic unit quota / cap 3 | Further N cuts | A/B gated; high overlap with short-circuit |
| MTP / DeepEP / DBO | Modest decode | Ops A/B; not a solo closer |

None of these restore "two identical V4-Pro schedulers." They buy a **different** path. See `../27-dualpod-dependency-rewrite.md`, `../12-dense-offload-architecture.md`, `../18-packages-1pod.md`.

---

## 6. One-line planner takeaway

**Twin ban = lose the S:16→32 compute halving (~887 s on N_rem=1419).**  
Path A central **~596 s** becomes single-pod MODERATE **~1493 s**. Reclaim the gap with dense hetero offload + AGGRESSIVE call cuts, or publish a ~20–25 min MoE-only cold SLA.
