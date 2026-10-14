# 21 - Skip Monolith Revisit (1-pod, ≤10 min pressure)

**Verdict:** usable-with-conditions — **do not skip monolith** (conditional or fleet-wide) when metadata+units suffice; savings are **real but subordinate** to other 1-pod levers and **quality cost is not bounded** by the "metadata+units suffice" gate.
**Confidence:** high (sidecar replay + wall arithmetic from `49-monolith-keep.md`, `12-dense-offload-architecture.md`, `147-verifier-monolith-textlane.md`)
**Date:** 2026-07-24
**Prior:** `research/cold-run-10min/49-monolith-keep.md` → **keep monolith**. This note re-evaluates under **single `alliance-pod`**, no twin, ≤600 s target.

---

## Executive answer

| Question | Answer |
|----------|--------|
| **Skip monolith when metadata+units suffice?** | **No.** |
| **Why re-evaluate at all?** | Under heterogeneous dense offload, MoE queue is **monolith-bound (~511 s)**; monolith is no longer "cheap noise" on the critical path. |
| **Does skip close 10 min without other levers?** | **No.** Full skip saves **~476 s** on a single MoE queue but v11 MODERATE alone stays **~1366 s**; skip alone leaves **~890 s**. |
| **Does skip add margin once dense offload lands?** | **Yes (~159 s)** — fleet **511 → ~352 s** — but **6 fusion papers** lose `llm_clear_soft_review` and **16 PDF papers** lose mono-only cnf units miss. |
| **Better MoE cut without monolith?** | **Yes:** deterministic metadata diff (**−377 calls, ~471 s class**) preserves monolith as the sole document-wide lens. |

---

## What "metadata+units suffice" means

Proposed gate (not implemented): **skip call [1] monolith** when:

1. `metadata_outline_check.verdict == "pass"`, and
2. Downstream unit coverage is scheduled or complete (`risk_signals` non-empty, or `run_unit_checks` will run / did run with routed units).

This mirrors the inverse of **E-PDF-1** (metadata short-circuit skips units) and assumes metadata+units subsume monolith's detection surface.

**Code reality today:** monolith always runs first (`pdf_judge.py:668-684`); metadata is mandatory second (`701-714`); units are conditional (`934-945`). Monolith output is **not** an input to metadata or routing — the chain is parallel scopes, not redundant stages (`68-cascade-early-exit-map.md`).

---

## Savings (1-pod arithmetic, S=16)

### Full fleet monolith skip (381 first-pass calls)

| Layout | Baseline wall | After skip | Δ wall | Hits ≤600 s? |
|--------|-------------:|-----------:|-------:|:------------:|
| Single MoE queue (v11 MODERATE, no dense) | ~1366 s | ~890 s | **−476 s** | ❌ |
| Single MoE queue (v10) | 3003 s | ~2527 s | **−476 s** | ❌ |
| Heterogeneous dense offload (Scenario A, `12-dense-offload`) | ~511 s (MoE-bound) | ~352 s (dense-bound) | **−159 s** | ✅ both |

Formula: **381 × 20 / 16 ≈ 476 s** removed from MoE leg; under **`max(T_dense, T_moe)`** only the MoE-bound excess counts (**511 − 352 ≈ 159 s**).

PDF-only skip (181 calls): **226 s (~7.5%)** on single queue — confirms `49-monolith-keep.md`.

### Conditional skip when metadata pass + units scheduled

| Gate | Papers skipping monolith | Est. wall saved | Notes |
|------|-------------------------:|----------------:|-------|
| Naive: `metadata==pass` AND `risk_signals` non-empty | **~180/181 PDF** | **~21 s** | Router fires on almost every paper (`16-monolith-redundancy-skeptic.md:14`) — no-op for speed |
| Aggressive: `metadata==pass` AND zero screen flags AND doc recall ≥ 0.85 | **~165/181 PDF** | **~206 s** | **34 papers** retain monolith cnf the screen missed; **16** have mono-only cnf, zero unit cnf |
| Safe subset: metadata pass + units found ≥1 defect | **~subset of ~120** | **~150 s** (est.) | Monolith often inspect-only on those papers; fusion already capped by defects |

**Conclusion:** the conditional gate either saves **negligible wall** (safe/narrow) or **reopens false-pass history** (aggressive). There is no gate that saves **≥159 s** (heterogeneous margin) at **≤1 fusion-verdict delta**.

---

## Quality hit

### Measured on v10 sidecars (381 papers, 2026-07-23)

| Scenario | PDF `suggested_verdict` delta | Fleet fusion delta | Inspect / advisory loss |
|----------|------------------------------:|-------------------:|-------------------------|
| Strip monolith cnf only; keep metadata+units | **1/181** (`P4048R0` fail→review) | **0** material on cnf-only sim | Mono quotes on 39 papers |
| Full monolith skip | **8/181** (5 review→pass, 3 fail→review) | **6/378** material via `llm_clear_soft_review` | **74/378** zero-value monolith calls removed; **392** inspect quotes gone |
| Conditional (165 clean-screen skip) | **≤34** at risk (mono cnf screen missed) | Unmeasured; includes mono-only-cn cohort | Localized loss hidden in doc-average recall |

### What metadata+units do **not** cover (monolith-unique)

| Defect class | Monolith prompt | Metadata | Units / screen |
|--------------|-----------------|----------|----------------|
| Document-wide section **reordering** | Yes (`pdf_judge.py:190-196`) | No (outline values, not order) | No (`pdf_judge.py:225-226`) |
| Cross-page structure / TOC leak reasoning | Yes | Partial (outline drift) | Per-page only |
| Mono-only `candidate_not_found` | Yes | No | **16/181 PDF** papers: mono cnf, zero unit cnf |
| Whisker soft-review clear path | Monolith axis fail absence required | No | Defect-driven only |

Fleet reorder hits today: **0** deciding defects (`16-monolith-redundancy-skeptic.md:18`). That is **not** a license to delete the only prompt that checks reordering — it is an unmeasured tail risk (PR #286-class architecture false-clear at advisory pass).

### "Suffice" is false for fusion, not just inspect

- **Metadata pass + zero-defect units** does **not** imply monolith added nothing: **6 whisker-`review` papers** clear via `llm_clear_soft_review` when monolith axes are clean (`34-verdict-value-analyst.md:24`).
- **Metadata pass + units running** still misses **mono-only cnf** on quiet pages where router did not flag the page and units returned empty (`147-verifier-monolith-textlane.md:14-16`).

Quality risk summary:

| Risk tier | Trigger |
|-----------|---------|
| **HIGH** | Fleet-wide or aggressive conditional skip |
| **MEDIUM** | Full skip under dense offload (6 fusion paths, 8 PDF verdict shifts) |
| **LOW** | cnf-only ablation (1 PDF fail→review) — still loses reorder lens |

---

## 1-pod pressure: does the math override keep?

| Lever (1-pod) | Est. savings | Quality gate | Supersedes monolith skip? |
|---------------|-------------:|--------------|---------------------------|
| v11 metadata short-circuit (landed) | −1059 to −1341 s | Verified zero fusion drift | ✅ Already shipped |
| Dense unit+metadata offload | −2300 s class vs baseline; **511 s** fleet central | 381/381 A/B required | ✅ Hits 10 min **without** monolith cut |
| Deterministic metadata diff | **−471 s** (377 calls) | A/B fold parity | ✅ Cuts MoE **more** than monolith skip on single queue |
| Verdict-first / prefix on survivors | −124 to −360 s | 48-anchor holdout | ✅ Incremental on MoE survivors |
| **Monolith skip (conditional)** | **~21–206 s** | 16–34 papers exposed | ❌ |
| **Monolith skip (full)** | **159–476 s** | 6 fusion + reorder tail | ❌ |

Under 1-pod constraint:

1. **Without dense offload:** monolith skip **does not reach 600 s** (~890 s best case post-skip on v11 MODERATE).
2. **With dense offload:** target is **already plausibly met (~511 s)**; monolith skip buys **~159 s margin**, not admission to 10 min.
3. **MoE-bound regime** makes monolith **visible** on the critical path, but the correct MoE cut is **deterministic metadata (−377 calls)**, not deleting the document-wide judge.

---

## Recommendation

| Action | Verdict |
|--------|---------|
| Skip monolith when metadata pass + units scheduled | **No** |
| Skip monolith fleet-wide for 1-pod speed | **No** |
| Keep monolith on `alliance-pod` | **Yes** |
| Replace **metadata LLM** with deterministic diff (keep monolith) | **Yes** (AGGRESSIVE, A/B-gated) |
| Future: cheap **outline-only reorder call** on ~20–30 borderline papers | **Defer** — replacement architecture, not skip (`16-monolith-redundancy-skeptic.md:20`) |

---

## False-pass hypothesis

Ship conditional skip on `metadata==pass && risk_signals`: **180/181** papers skip monolith; **P4048R0-class** mono-only cnf and future **section-order swaps** with clean per-page recall pass screen+metadata+units — advisory `pass` on LLM lane while deterministic whisker still `pass`.

## False-fail hypothesis

Reject any skip because "monolith is 7.5%": under dense offload, monolith is **100% of the MoE bottleneck** — but **deterministic metadata** and **prefix/APC** shrink that bottleneck without removing the reorder lens.

## What would change my mind

1. Holdout **≥30 labeled reorder/structure PDFs**: if **≥50%** caught **only** by monolith and not by metadata+units+outline-only substitute → monolith mandatory (same bar as `49-monolith-keep.md`).
2. Dense-offload A/B at **>650 s** MoE-bound after deterministic metadata → revisit **full** skip with bundled 381-paper parity gate (accept 6 fusion deltas explicitly).
3. Per-call attribution: **>43 papers** where a **single unit check** is sole cause of fusion flip on whisker-`pass` → would force units into protected set (falsifies "units suffice" column); not observed.

---

## Sources

- `research/cold-run-10min/49-monolith-keep.md` — prior keep decision
- `research/cold-run-10min-1pod/12-dense-offload-architecture.md` — MoE-bound ~511 s, monolith 381/428 MoE calls
- `research/cold-run-10min-1pod/10-impl-status-1pod.md` — v11 ~1366 s single-pod MODERATE
- `research/tapetum-llm-speedup/16-monolith-redundancy-skeptic.md` — conditional gates, replacement architecture
- `research/tapetum-llm-speedup/34-verdict-value-analyst.md` — fusion-light monolith, 6 material clears
- `research/tapetum-llm-speedup/147-verifier-monolith-textlane.md` — 1/181 cnf-only delta, 8/181 full removal
- `research/cold-run-10min/68-cascade-early-exit-map.md` — call order, E-PDF-1 short-circuit
