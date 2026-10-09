# 17 - Physics Floor Skeptic (one pod, S=16)

**Verdict:** usable — **≤600 s (~10 min) cold on one `alliance-pod` is below the quality-preserving physics floor**; even aggressive call cuts leave **~23 min** at measured latency, and loaded decode alone exceeds 10 min before prefill and queue.
**Confidence:** high (call census + sidecar token P50s + measured slot/decode rates; no live stacked run)

## Executive answer

| Floor type | N (calls) | Wall @ S=16 | Minutes | vs 600 s target |
|------------|----------:|------------:|--------:|:---------------:|
| **Front-end only** (381 monolith + 377 metadata) | 758 | **948 s** | **15.8** | ❌ +348 s |
| **Loaded decode physics** (output ÷ 19 tok/s/user) | 1,419 | **672 s** | **11.2** | ❌ +72 s (decode only) |
| **Quality-preserving minimum** (MODERATE Tier A+B survivors) | 1,419 | **1,366–1,493 s** | **22.8–24.9** | ❌ +766–893 s |
| **Solo-decode fantasy** (output ÷ 70 tok/s, no prefill/queue) | 1,419 | **183 s** | **3.1** | Misleading |

**Return line:** **Irreducible floor ≈ 16 min** (monolith+metadata only, no units) to **≈ 23 min** (quality-preserving MODERATE minimum on one pod). **10 min is impossible** on one pod without violating S=16, pretending solo 70 tok/s holds under load, or dropping verification depth.

---

## Irreducible call census

Minimum calls that survive every quality-bounded lever in the one-pod corpus (metadata Tier A+B, escalation dedupe; **no** twin pod, **no** S→32):

| Class | Calls | Notes |
|-------|------:|-------|
| First-pass (PDF monolith + HTML tier-1) | **381** | One per paper; non-optional (`49-monolith-keep.md`) |
| Metadata / outline | **377** | 381 − 4 error tombstones; always runs before units |
| Unit checks (metadata-pass survivors + review→1) | **663** | 1,510 − 847 eliminated (`17-metadata-shortcircuit-design.md`, `11-wall-arithmetic.md`) |
| Page escalations (deduped) | **~16** | Overlap with units trimmed (`18-escalation-overlap-auditor.md`) |
| **N_irreducible** | **~1,419** | Canonical MODERATE remainder |

**381 monolith + metadata + pass-papers' units** decomposes as:

- **758** calls are **unconditional** (every adjudicated paper pays monolith/tier-1 + metadata).
- **663** unit calls remain on metadata-pass / single-check review survivors; zero-yield units on failed metadata are already cut.
- You **cannot** reach ≤600 s by trimming units alone: front-end **758 × 20 / 16 = 948 s** exceeds the target **before any unit check executes** (`58-max-unit-checks-knob.md:73`, `49-monolith-keep.md:24`).

---

## Wall model (fixed S=16)

```
wall = (N_rem × L_eff) / S + T + C − L_abs
```

| Symbol | One-pod value | Constraint |
|--------|---------------|------------|
| S | **16** | `--max-num-seqs 32` measured **+57%** wall (`00-baseline.md:32-33`) |
| L (fleet mean) | **20 s/call** | Closes 3,003 s measured wall (`2284×20/16 + 148`) |
| L_abs (best software) | **~436 s** | Prefix + verdict-first on survivor mix (`22-path-a-b-10min.md:51-54`) |
| T + C | **28–68 s** | LJF + `to_thread` after wins |

Path B rebuild (twin forbidden, MODERATE levers only):

```
N_rem = 1,419
compute@16 = 1,419 × 20 / 16 = 1,773.8 s
wall_optimistic = 1,773.8 + 28 − 436 = 1,366 s  (~22.8 min)
wall_pessimistic = 1,773.8 + 68 − 349 = 1,493 s (~24.9 min)
```

Gap to 600 s: **766–893 s** — almost exactly the **887 s** dual-pod would have halved from the compute term (`22-path-a-b-10min.md:96`, `138`).

---

## Decode @ ~70 tok/s: what it actually buys

**70 tok/s is solo inter-token latency (ITL)** on an unloaded request (`52-h200-capacity-math.md:83`, `pdf_judge.py:28`). It is **healthy** for DeepSeek-V4-Pro on 8×H200 (HBM ceiling ~45–70 tok/s realized for 49B active MoE). It is **not** the per-user rate under 16-slot continuous batching.

| Operating point | tok/s | Source |
|-----------------|------:|--------|
| Solo ITL (batch=1) | **~70** | Baseline docstring + capacity math |
| Loaded per-user @ S=16 | **~19** (TPOT scrapes 36–40) | `52-h200-capacity-math.md:84`, persona 146 |
| Fleet mean decode slice | **5.91 s** vs **0.46 s** prefill (pod-wide) | `21-prior-synthesis-gaps.md`, `47-max-tokens-shrink.md` |

Per-call **output** P50 (sidecar reconstruction, `11-output-token-decode-auditor.md`):

| Call type | P50 output (tok) | Solo decode @ 70 tok/s | Loaded decode @ 19 tok/s |
|-----------|-----------------:|-----------------------:|-------------------------:|
| Monolith / tier-1 | 283 | 4.0 s | 14.9 s |
| Metadata | 112 | 1.6 s | 5.9 s |
| Unit check | 77 | 1.1 s | 4.1 s |
| Page escalation | ~200 (est.) | 2.9 s | 10.5 s |

**Fleet output tokens (N_irreducible = 1,419):**

```
381×283 + 377×112 + 663×77 + 16×200 ≈ 204,300 tok
```

| Decode assumption | Serial decode | ÷ S=16 | Minutes |
|-------------------|--------------:|-------:|--------:|
| Solo 70 tok/s (optimistic) | 2,919 s | **183 s** | 3.1 |
| Loaded 19 tok/s (MoE batch physics) | 10,753 s | **672 s** | **11.2** |

**Loaded decode alone exceeds 600 s** before:

- Prefill (~14k tok monolith, ~7k tok per unit with full `candidate_md`; repeated ~6× per paper),
- Scheduler queue (~2.4 s mean wait component in 9.0 s E2E decomposition),
- T + C overhead,
- Any L_abs savings from APC (prefix helps prefill, **not decode**; `102-vllm-anti-steelman.md:22`).

Measured closure: **150–300 out tok ÷ 70 ≈ 2–4 s decode** per call; **residual ~16 s** is queue + prefill (`52-h200-capacity-math.md:102`). Shrinking output (verdict-first) saves **seconds per call**, not **minutes per fleet**, when N remains ~1,419.

---

## Why ≤10 min is impossible on one pod

### 1. Front-end floor already busts the budget

**758 monolith + metadata calls × 20 s / 16 slots = 948 s (~15.8 min).**

No amount of decode tuning at 70 tok/s removes these calls without losing the document-wide lens, metadata gate, or 31 PDF fails driven by metadata (`49-monolith-keep.md:24`). Nightly monolith+metadata-only **still misses unit-check-only defects** (P1000R8 table corruption class).

### 2. S=16 is the ceiling, not the dial

MoE expert-union grows with batch width; measured **16→32 server slots = +57% wall** (`00-baseline.md:32-33`). Community DeepSeek recipes cap **4–8** seqs; the fleet already runs **16** (`49-steelman-defender.md:10`). There is **no S=32 substitute** on one pod without regression.

The **887 s** gap to 10 min on MODERATE is **structurally** the second pod's compute halving (`11-wall-arithmetic.md:97`, `22-path-a-b-10min.md:166`).

### 3. 70 tok/s does not apply under fleet load

At **19 tok/s/user**, decode on 204k output tokens needs **672 s of slot time** — **already >600 s** with zero prefill, zero queue, zero CPU post-processing. Solo 70 tok/s **understates** loaded ITL by **~3.7×** (`70/19`).

You cannot "fix" this without:

- A different model class (dense 32B on another endpoint = dense offload, not one V4 pod),
- Lower N (forbidden without quality proof),
- Or pretending batch=1 while running 381 papers × c=32 client overfill.

### 4. Call elimination has a quality floor above 758

MODERATE Tier A+B already removes **847 unit calls (44.6% of fleet)** with **0 merged-verdict drift** on metadata-non-pass papers (`17-metadata-shortcircuit-design.md:11-12`). Tier C full skip (−1,047 calls) is excluded for **inspect regression** on 19 review papers.

Remaining **663 units** sit on papers where metadata passed or review still warrants one localized check. **16/381 papers** had LLM findings change merged verdict; blind unit cuts hit that tail (`10-call-graph-accountant.md:18`).

### 5. Latency levers cannot close a 766 s gap

Best-case **L_abs ≈ 436 s** (prefix reorder on survivors + verdict-first) on Path B still yields **~1,366 s**. Even **AGGRESSIVE** dense offload on one MoE pod plans **715–910 s realistic** with friction (`22-path-a-b-10min.md:119-124`) — still missing 10 min under pessimistic accounting.

MTP, chunked prefill, engine swap: decode-bound fleet means prefill levers are **second-order**; MTP hurts short OSL (~55 tok pass-path JSON) (`05d-web-mtp-specdecode.md`).

### 6. In-paper parallelism does not reduce slot-seconds

Total slot-seconds = **N × L** regardless of serial vs parallel within a paper (`20-in-paper-parallelist.md:12-14`). Fleet already saturates 16 slots with c=32 cross-paper concurrency.

---

## Findings

- [CRITICAL] **Front-end irreducible floor = 948 s (~15.8 min) > 600 s target.** Evidence: 758 calls × 20 s / 16 (`49-monolith-keep.md:24`, `66-marker-quality-speed-flags.md:22`). Impact: **10 min unreachable** even if every unit check vanishes.

- [CRITICAL] **Quality-preserving N_irreducible = 1,419 → 1,366–1,493 s (~23–25 min) on one pod.** Evidence: Path B MODERATE (`22-path-a-b-10min.md:82-94`); no twin pod. Impact: **766–893 s gap** to target; matches forbidden dual-pod savings.

- [CRITICAL] **Loaded decode physics floor ≈ 672 s (~11.2 min) on output tokens alone.** Evidence: 204k tok ÷ 19 tok/s ÷ 16 slots; P50 sidecar outputs (`11-output-token-decode-auditor.md:10-14`). Impact: **decode @ fleet load exceeds 10 min before prefill**; solo 70 tok/s is not operative.

- [HIGH] **70 tok/s is in-band for V4-Pro H200, not a tuning bug.** Evidence: `52-h200-capacity-math.md:75-102`. Impact: chasing faster decode on this pod is **the wrong lever**; call count and S topology dominate.

- [HIGH] **S=16→32 on one pod forbidden (+57% wall).** Evidence: `00-baseline.md:32-33`, `102-vllm-anti-steelman.md:14`. Impact: no software trick replaces **second identical replica**.

- [MED] **Verdict-first / schema shrink saves ~155 s scaled, not ~900 s.** Evidence: `11-wall-arithmetic.md:39`; overlap with eliminated zero-defect units. Impact: decode discipline helps margin, not feasibility.

- [MED] **Deterministic metadata replacement (~377 calls) is AGGRESSIVE tier, weeks of validation.** Evidence: `49-monolith-keep.md:26`. Impact: even full metadata demotion to CPU diff leaves **381 + 663 + esc ≈ 1,060+ calls** on MoE — still **~1,325 s @ 20 s/call / 16** before L_abs.

---

## False-pass hypothesis

Operator sees **~183 s** solo-decode arithmetic, ships "physics proves 10 min fits," disables metadata short-circuit as unnecessary, and runs full **2,284-call** cold at **~50 min** while claiming the model was wrong — when the error was using **70 tok/s under S=16 MoE load** instead of **19 tok/s/user**.

## False-fail hypothesis

Operator abandons MODERATE (**~23 min** achievable) because 10 min is impossible, never ships **−847 call** short-circuit, and stays at **~50 min** baseline — leaving **~1,637 s** of verified waste on the table (`22-path-a-b-10min.md:186-187`).

## What would change my mind

1. **Instrumented one-pod MODERATE cold ≤650 s** with `{call_type, wall_s, output_tok, cached_tok}` logging → model error; revisit L or N cuts.
2. **Proof that metadata-pass unit floor ≤200 calls** with 381/381 verdict parity → lowers N below 1,000 and reopens arithmetic.
3. **S=16 sustained >40 tok/s/user ITL** under production judge payloads (not bench) → loaded decode floor drops toward ~400 s; still need front-end 758-call accounting.

---

## Summary table (one pod, S=16, decode reference rates)

| Scenario | Minutes | Achievable? |
|----------|--------:|:-----------:|
| Target | **10.0** | Goal |
| Front-end only (758 calls, L=20) | **15.8** | Quality-safe minimum without units |
| Loaded decode only (1,419 calls, 19 tok/s) | **11.2** | Theoretical decode slice; no prefill |
| MODERATE + best L_abs (measured L=20) | **22.8–24.9** | **Best realistic one-pod floor** |
| Solo decode fantasy (70 tok/s, no prefill) | **3.1** | **Not physically reachable under load** |

**Bottom line:** Treat **~23 min** as the one-pod physics floor after quality-bounded call cuts. Treat **~16 min** as the absolute call-graph floor (monolith + metadata, zero units). **10 min requires a second S=16 replica or a forbidden concurrency regression**, not decode tuning on the existing pod.
