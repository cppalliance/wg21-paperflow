# 22 - HTML vs PDF mix (381-paper fleet, 1 pod)

**Verdict:** usable-with-conditions — HTML is **52.8% of papers** and already **~11% cheaper per paper** via cascade + routing; it is **not** a separate path to ≤600 s. The leverage is **port HTML deterministic patterns to PDF** (metadata diff), not “optimize HTML harder.”
**Confidence:** high (lane counts from sidecar census); medium (HTML-only savings if metadata diff ships HTML-first)

**Date:** 2026-07-24. Sources: `research/tapetum-llm-throughput/01-call-count-accountant.md`, `research/tapetum-llm-speedup/10-call-graph-accountant.md`, `research/cold-run-10min/{49-monolith-keep,68-cascade-early-exit-map,58-max-unit-checks-knob}.md`, `research/cold-run-10min-1pod/{00-baseline,13-deterministic-metadata,18-packages-1pod}.md`, `research/tapetum-llm-speedup/131-surya-model-sizing.md`.

**Constraint:** single `alliance-pod`, S_eff = **16** (`00-baseline.md`).

---

## Executive answer

| Question | Answer |
|----------|--------|
| **How many HTML vs PDF of 381?** | **201 HTML (52.8%)**, **180 PDF (47.2%)**. Mutually exclusive by staged source suffix (`cli._source_kind`: `.html`/`.htm` vs `.pdf`). |
| **Is HTML already cheaper?** | **Yes, modestly.** Median **6** calls/paper vs PDF **7**; mean **5.73** vs **6.43**. No PDF-only page escalation; tier-2 fires on **23/201** (11%) only. |
| **Because HTML “already has cascade”?** | **Partially.** Tier-1 → optional tier-2 → metadata → units is wired (`68-cascade-early-exit-map.md`). v11 metadata short-circuit applies to **both** lanes. HTML does **not** skip tier-1 or metadata LLM today. |
| **Incremental 1-pod savings from HTML lane?** | **Narrow:** HTML-first deterministic metadata ≈ **251 s** (201 calls); fleet-wide same lever ≈ **471 s**. No large HTML-only lever beyond mix accounting. |
| **Does mix get us to ≤600 s?** | **No.** HTML share (~**48%** of LLM calls) is already reflected in the **3003 s** baseline. Closing the **~800–900 s** 1-pod gap still needs MODERATE+ (short-circuit, prefix, verdict-first) and/or AGGRESSIVE (deterministic metadata, dense offload). |

---

## Fleet mix table

| Lane | Papers | Share | Calls/paper (median) | Calls/paper (mean) | Est. lane calls |
|------|-------:|------:|---------------------:|-------------------:|----------------:|
| **HTML** | **201** | **52.8%** | **6** | **5.73** | **~1152** |
| **PDF** | **180** | **47.2%** | **7** | **6.43** | **~1157** |
| **Fleet** | **381** | 100% | **7** | **6.11** | **~2308** |

Evidence: `01-call-count-accountant.md:8-15,34-38` (2308 sidecar aggregate; 2284 rounded census + tier-2/page-esc in `10-call-graph-accountant.md:8`).

---

## Call-class split by lane (3003 s baseline)

| Call class | Fleet total | HTML (est.) | PDF (est.) | Notes |
|------------|------------:|------------:|-----------:|-------|
| First pass | 381 | **201** tier-1 | **180** monolith | HTML tier-1 ≈ PDF monolith role (~251 s wall each) |
| Metadata / outline | 377 | **~198** | **~179** | 4 error tombstones skipped metadata |
| Unit checks | ~1510 | **~614** (median **4**/paper) | **~896** (median **5**/paper) | `58-max-unit-checks-knob.md:51` |
| Page escalation | ~16 | **0** | **~16** | PDF-only (`09-escalation-cost-auditor.md:8`) |
| Tier-2 adjudicate | ~23 | **~23** | **0** | HTML-only; 11.4% of HTML papers |
| **Lane subtotal** | **~2308** | **~1036 (45%)** | **~1271 (55%)** | Wall ≈ calls × 20 / 16 |

**HTML share of cold wall (call-linear model):** **~1295 s / 3003 s ≈ 43%**.  
**PDF share:** **~1589 s ≈ 53%** (remainder = T+C overhead in closure).

---

## Why HTML is already cheaper (cascade + routing)

### Wired today

| Mechanism | HTML | PDF | Savings vs counterfactual |
|-----------|------|-----|---------------------------|
| Two-tier triage | Tier-1 always; tier-2 **only if** axis conflict / ungrounded evidence (`adjudicate.py:256-299`) | Monolith always; no tier-2 | **~23 calls** fleet-wide (tier-2); early exit on **188/201** HTML papers |
| Page escalation | **None** | Up to 5 scoped calls after recall screen | **~16 calls**, PDF-only |
| Unit routing | `route_html_units`: deterministic outline level+title diff (`source_router.py:286-312`) | `route_pdf_units`: page/heuristic signals | Median **4** vs **5** unit checks → **~144–210** fewer HTML unit calls (`58-max-unit-checks-knob.md:51`) |
| Token ceiling | `fast` **1024** / `deep` **2048** (`adjudicate.py:90-93`) | Judge agent **1536** (`cli.py:1106-1112`) | ~**0.71×** effective per-call vs monolith class (`01-call-count-accountant.md:27`) |
| Metadata short-circuit (v11) | E-HTML-1: skip units when metadata ≠ pass (`adjudicate.py:521-531`) | E-PDF-1: same (`pdf_judge.py:742-759`) | **Shared** lever; not HTML-specific |

### Already realized “HTML discount”

If HTML papers paid PDF median (**7** calls): **201 × 1 ≈ 201 extra calls** → **~251 s** @ S=16.  
Fleet mix **already embeds** this; it is not an incremental lever on top of baseline arithmetic.

---

## Can HTML path get cheaper still?

### Yes, but small and mostly duplicates fleet levers

| Lever | HTML-only Δwall @ S=16 | Fleet-wide same idea | Quality gate |
|-------|------------------------:|----------------------|--------------|
| Deterministic metadata (drop LLM re-ask) | **~251 s** (201 calls) | **~471 s** (377 calls) | A/B: ≤5% metadata drift, zero fused verdict change (`13-deterministic-metadata.md`) |
| HTML-only metadata first | Same **251 s** as first tranche | PDF branch harder (page-1 noise) | HTML holdout catches PR #282-class level drift (`131-surya-model-sizing.md:10`) |
| Drop tier-1 on “clean” HTML | **~251 s** if all 201 skipped | N/A (loses whole-doc lens) | **Reject** — same class as dropping PDF monolith (~226 s, 1–8 verdict deltas, `49-monolith-keep.md`) |
| Tighter HTML unit cap | **~72–105 s** (144–210 calls at cap−1) | PDF saves more (896 unit calls) | Router FN holdout |
| `--review-all` skip clean HTML passes | **~250–350 s** modeled (`24-det-skip-llm.md:31`) | Applies to PDF pass cohort too | Selection-gap blind spot |

### No — cascade does not remove mandatory calls

HTML still pays:

1. **Tier-1 triage** on every paper (201 calls) — structural whole-doc compare, same budget class as PDF monolith (`12-dense-offload-architecture.md:28-29`).
2. **Metadata LLM** on every paper that reaches `_run_html_unit_checks` (~198 calls) — **duplicates** deterministic outline work already done in `route_html_units` (`131-surya-model-sizing.md:10`, `13-deterministic-metadata.md:74`).
3. **Up to 5 unit checks** when `risk_signals` non-empty — same cap as PDF (`unit_judge.py:355`).

The cascade **gates** tier-2 and units; it does **not** replace tier-1 or metadata with deterministic code **yet**.

---

## Leverage for the 1-pod plan

### What HTML mix implies

| Observation | Implication for ≤600 s on one pod |
|-------------|-----------------------------------|
| HTML = **52.8%** of papers, **~45%** of calls | Optimizing “HTML only” caps at **~half** the fleet; PDF unit load (**~896** calls, **59%** of units) dominates |
| HTML already uses cascade early-exit | **No hidden 500 s** sitting in HTML-only skips; v11 short-circuit is **lane-agnostic** |
| Biggest HTML-specific waste | **Metadata LLM re-asking outline diff** — port `compare_metadata_outline()` using existing `route_html_units` / `html_outline.py` |
| Dense offload | **201 tier-1 + ~23 tier-2 stay on MoE** (`12-dense-offload-architecture.md:29-30`); HTML mix **increases** MoE first-pass share vs PDF-only fleet |

### Stacked savings (S=16, from `18-packages-1pod.md`)

Baseline **3003 s**. HTML mix does **not** change these formulas; HTML-first metadata is a **deployment order**, not a different total.

| Package | Central wall (s) | HTML-relevant component |
|---------|-----------------:|-------------------------|
| MODERATE | **~1366** | Metadata short-circuit saves units on **both** lanes; ~**706** review-path HTML units included in −847 call model |
| MODERATE + deterministic metadata (AGGRESSIVE add-on) | **~1191** (−471 from MODERATE+short-circuit stack in `13-deterministic-metadata.md:38`) | **~53%** of −471 s benefits HTML papers (198/377 metadata calls) |
| AGGRESSIVE + dense offload | **~510–710** (`12-dense-offload-architecture.md:3`) | HTML tier-1/tier-2 remain MoE-bound |

**Bottom line:** HTML share explains **~43% of today’s wall** but offers **~251 s** of **incremental** HTML-prioritized metadata diff on top of already-realized cascade savings. The 1-pod gap (**~800–900 s** after MODERATE, `00-baseline.md:27-28`) requires **fleet-wide** N and L levers, not HTML-only tuning.

---

## False-pass hypothesis

Ship HTML-only deterministic metadata while PDF still uses LLM metadata: HTML papers lose LLM lenience on noisy edge cases; if PDF LLM passes a borderline PDF metadata case that HTML deterministic marks **review**, fleet reports inconsistent advisory posture by source kind. Mitigation: shadow both lanes, then flip **fleet-wide** (`13-deterministic-metadata.md:159-178`).

## False-fail hypothesis

Assume “HTML cascade = skip LLM on confident tier-1”: tier-1 **pass** with empty escalation signals still runs metadata + units when router fires (**376/381** papers have `risk_signals`, `01-call-count-accountant.md:30`). Treating HTML as “1-call papers” under-counts wall by **~5 calls × 201 papers**.

## What would change my mind

1. Sidecar replay showing **>30%** of HTML papers reach **≤2 LLM calls** on default cold (not error tombstones) would upgrade “HTML cascade already cheap” to a **primary** lever — tonight’s median **6** contradicts that.
2. HTML-only deterministic metadata shadow with **≥98%** verdict agreement and **zero** holdout fused drift would justify **HTML-first ship** for **~251 s** toward 1-pod target without waiting on PDF metadata parity.
3. A measured cold run ≤**600 s** at S=16 **without** fleet-wide metadata/unit levers would prove HTML mix alone sufficient — no persona in this corpus supports that.

---

## Return summary (operator)

| Metric | Value |
|--------|------:|
| **HTML share (papers)** | **201 / 381 = 52.8%** |
| **PDF share (papers)** | **180 / 381 = 47.2%** |
| **HTML share (LLM calls, est.)** | **~45%** (~1036 / 2308) |
| **HTML share (wall, est.)** | **~43%** (~1295 / 3003 s) |
| **Leverage** | HTML **already ~11% fewer calls/paper**; **incremental** HTML-prioritized metadata diff **~251 s**; **fleet-wide** deterministic metadata **~471 s**; **cannot** close 1-pod gap alone — borrow HTML **deterministic routing** to PDF, stack MODERATE + AGGRESSIVE levers |
