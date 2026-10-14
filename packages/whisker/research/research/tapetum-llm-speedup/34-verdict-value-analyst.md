# 34 - Verdict-Value-Analyst

**Verdict:** usable-with-conditions (+ the master table reconciles fleet cost to verdict/fusion value; 548/2345 calls are zero-yield at measured granularity and ~692 unit checks on metadata-non-pass are fusion-dead, but reaching 5–10 min still requires stacking non-call-cut levers because high-value calls remain serial-heavy)
**Confidence:** high

## Findings

- [CRITICAL] **Master value-per-call table (381 sidecars, 378 ok / 3 error, counterfactual replay with `suggested_verdict` recomputed before `fuse_verdicts`, fusion logic `fusion.py:348-549`).** Linear wall model: 3003.4 s × calls/2345.

| Call class | Calls | Est. wall (s) | Moved `suggested_verdict` (papers) | Moved fusion combined (papers) | Inspect findings (papers) | Zero-value calls |
|------------|------:|--------------:|-----------------------------------:|-------------------------------:|--------------------------:|-----------------:|
| Monolith (PDF monolith + HTML tier-1) | 378 | 484 | 75 / 378 (19.8%) | 20 / 378 (5.3%); **6 material** (`review→pass` via `llm_clear_soft_review`) | 299 / 378 (79.1%) | 74 (19.6%) |
| Metadata / outline | 378 | 484 | 108 / 378 (28.6%) | 62 / 378 (16.4%); **56** reverse `source_aware_review_cap` (`fusion.py:410-423`) | 232 / 378 (61.4%) | 112 (29.6%) |
| Page escalation | 18 | 23 | 0 / 378 | 0 / 378 | 2 / 378 (0.5%) | 15 (83.3%) |
| Unit check | 1570 | 2012 | 43 / 378 (11.4%) | 79 / 378 (20.9%); **71** reverse `source_aware_review_cap` via accepted defects/coverage (`fusion.py:209-227`) | 240 / 378 (63.5%) | 347 (22.1%) |
| Ideal verification | 1 | 1 | 0 / 378 | 0 / 378 | 1 / 378 | 0 |

  Impact: **unit checks = 67.0% of calls / ~67% of wall** but only **43 papers** lose a different `suggested_verdict` if the entire class vanishes; **79 papers** lose a different merged verdict. Quality risk: **HIGH** for blind unit elimination; **LOW–MEDIUM** for metadata-`fail` short-circuit (below).

- [CRITICAL] **Cheapest 50% of calls by per-call value score (1172/2345 calls): mostly zero-yield unit + monolith prefill.** Bottom half: **548 zero-value calls (23.4% of fleet, ~702 s)** composed of **347 unit + 112 metadata-context unit + 74 monolith + 15 page escalation** (ranked list from sidecar replay 2026-07-23). Dropping only those 548 calls breaks **nothing measured** on `suggested_verdict` or fusion for those call instances. Dropping the full cheap half (includes finding-only inspect rows) strips **~392 unit-check inspect quotes** on papers already capped at `review` by metadata. Impact: **~702 s** from zero-value cull alone; still **~2300 s** short of 300–600 s target (`00-baseline.md:17-18`).

- [HIGH] **Metadata-non-pass unit checks are fusion-dead: 1047 calls, 692 zero-defect (66.1%), ~1344 s.** Measured: **232/378** papers with `metadata_outline_check.verdict ∈ {fail, review}`; **1047** unit checks; **692/1047 (66.1%)** returned no defects (matches `00-baseline.md:29-30` fleet-wide 70%). Fusion cap fires before clear/rescue when metadata ≠ pass (`fusion.py:187-189`, applied at `fusion.py:410-423`). **32/32** metadata-`fail` papers end `suggested_verdict=fail`; **0** flip if units removed (confirms persona **17**). Cross-check persona **17**: counts **232 / 1047 / 692** align; their **~1331 s** upper bound maps to **3003.4×1047/2345 ≈ 1341 s** on v10 sidecars. Impact: Tier-A fail short-circuit saves **141 calls (~181 s)** verdict-identical; full skip on metadata non-pass saves **1047 calls (~1341 s)** on merged verdict with **MEDIUM** inspect loss. Quality risk: **LOW** on merged verdict; **MEDIUM** on human `--inspect` completeness (`CLAUDE.md` inspect contract).

- [HIGH] **Monolith marginal value is inspect-heavy, fusion-light; persona 16 overstates cnf-only verdict delta on v10 sidecars.** PDF monolith cnf quotes: **39/181** papers; removing **only** surviving cnf (keeping ambiguous/refuted mono dispositions) moves **`suggested_verdict` on 1/181** (`P4048R0`: `fail→review`). Persona **16** cited **4** papers (`N5036`, `P3828R1`, `P4124R0`, `P4048R0`); on v10 sidecars those three `review→pass` cases **do not fire** because ambiguous mono dispositions still fold to `review` (`pdf_judge.py:343-367`). Full monolith skip moves **11/181 PDF (93.9% stable)** and **6/378 fleet fusion papers** materially (`agree→llm_clear_soft_review`). **74/378** monolith calls are zero-value (refuted/empty mono dispositions). Impact: replace-not-delete monolith (~484 s) per persona 16 shape; naive delete risks **6** false-clear paths and **11** PDF suggested-verdict shifts. Quality risk: **MEDIUM** without reorder substitute (`pdf_judge.py:190-196` vs `pdf_judge.py:225-226`).

- [HIGH] **Page escalation is negligible cost and near-zero verdict value.** **18 calls / ~23 s**; **2 confirmed** `content_missing` (`page_escalations[].content_missing=true`, 2026-07-23 aggregate); **0** papers move `suggested_verdict` or fusion if class removed; **15/18** calls zero-value. Screen cap without LLM (`pdf_judge.py:738-746`) already demotes when >5 pages flagged. Impact: **≤23 s** at risk if eliminated; quality risk: **LOW** for fleet verdict, **MEDIUM** for rare localized loss (design intent in `pdf_judge.py:733-832`).

- [MED] **LLM-lane vs fusion-lane accounting: 163 papers where `combined_verdict ≠ whisker_verdict`, but only 26 are clear/rescue rules.** Measured fusion deltas: **`llm_clear_soft_review` 17** (`review→pass`, `fusion.py:477-519`), **`llm_rescue_heading` 9** (`fail→review`, `fusion.py:385-396`), **`source_aware_review_cap` 137** (`pass→review`, `fusion.py:410-423`). Baseline headline "16 papers merged verdict changed" (`00-baseline.md:29-30`) counts a narrower material set; this table uses full counterfactual replay (**79** papers where removing unit checks alone changes fusion rule/verdict). Impact: optimize for **cap drivers** (metadata + unit defects) before monolith/page spend. Quality risk: confusing cap with "no value" — cap **is** the fail-closed contract.

- [MED] **Ideal verification: 1 call, inspect-only value.** **1/378** papers ran ideal verifier; **0** fusion movement (`ideal_verdict=="review"` cap at `fusion.py:425-436` did not change combined outcome on this fleet); **1** inspect discrepancy block. Impact: **~1 s**; not a fleet lever.

- [LOW] **Call census vs baseline: 2345 sidecar-counted calls on 378 ok papers (not 2284)** because v10 sidecars include **1570** unit checks (+HTML tier-2 not in the five-class table). Tier-2 (~23 calls) rides inside HTML monolith cascade (`adjudicate.py:256-299`); not broken out here per mandate. Impact: percentages shift ~3% vs `10-call-graph-accountant.md`; direction unchanged.

## False-pass hypothesis

Skip **all 1047 unit checks** on metadata-`review` (not just `fail`) while keeping metadata cap: **`P1000R8`-class** papers retain merged `review` but lose the **only page-scoped unit quotes** in `--inspect`; a human clears on metadata summary alone and misses table-corruption evidence that never reached `defect_groups` severity. Persona **17** measured **19** such papers; merged verdict unchanged, inspect completeness degraded.

## False-fail hypothesis

Aggressively cull the **548 zero-value calls** plus **full monolith skip** on PDF: **`P4048R0`** drops `suggested_verdict` `fail→review` when mono cnf removed; combined with monolith skip, **6** whisker-soft-review papers lose the `llm_clear_soft_review` path (`fusion.py:477-519`) because monolith axis fails no longer absent — humans see extra review noise, not silent pass, but fleet triage workload rises.

## What would change my mind

Per-call attribution showing **>43 papers** where a **single** unit-check call (not metadata, not monolith) is the **sole** cause of a `suggested_verdict` tier change **and** that tier change flips `combined_verdict` on a whisker-`pass` paper — would falsify the "metadata-fail + zero-defect units are safe cuts" column and force unit checks back into the protected set.
