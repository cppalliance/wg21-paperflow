# 147 - Verifier-C (Monolith + Text-Lane Re-verification)

**Verdict:** usable-with-conditions — load-bearing call-census and text-lane wall fractions reproduce independently; monolith quote grounding matches; monolith verdict-delta claim is materially overstated once downstream unit checks are included in the simulation.
**Confidence:** high

## Findings

- [CRITICAL] **Fleet lane split and call census (sidecar-derived, `data/whisker/llm/*.tapetum.json`, 381 files, 2026-07-23).** Papers: **197 text** + **181 PDF** + **3 error** tombstones (`status=error`, zero calls). Calls: **2363 total** = **378 first-pass** (181 monolith + 197 tier-1) + **18 tier-2** + **378 metadata** + **1570 unit checks** + **18 page escalations** + **1 ideal verify**. Text lane: **1201 calls (50.83%)**; PDF lane: **1162 calls**. Evidence: `_scratch/research-tapetum-llm-speedup/verifier_c.py`. Impact: confirms 42-text-lane call arithmetic; tier-2 **18/197 (9.1%)**, not 23.

- [CRITICAL] **Claim 2 text-lane wall share at equal 20 s/call reproduces.** Linear slot model (`00-baseline.md:24-25`): **1201 × 20 / 16 = 1501 s = 49.99%** of **3003 s** cold wall. Metadata-non-pass short-circuit eliminable units: **100/197** papers, **458 unit calls**, **458 × 20 / 16 = 572 s (19.06% fleet / 38.1% text-lane wall)**. Text metadata verdicts: **97 pass / 99 review / 1 fail**. Evidence: same script. Impact: 458-call / 572 s lever confirmed; fail-only skip is **5 calls (~6 s)**.

- [CRITICAL] **Claim 1 monolith quote grounding CONFIRMED on 181 PDF sidecars.** Monolith dispositions (no `page`, no `unit_id`): **392 quotes** = **228 `present_in_candidate` (58.2%)** + **87 `candidate_not_found` (22.2%)** + **77 `ambiguous`**. **39 papers** with ≥1 surviving monolith cnf. Matches `16-monolith-redundancy-skeptic.md` exactly. Evidence: independent aggregation in `verifier_c.py`.

- [HIGH] **Claim 1 “4/181 verdict changes if monolith cnf vanishes” → MODIFIED to 1/181 (fail→review only).** Simulation assumptions: re-apply `pdf_judge.py` downstream fold only (metadata `675-714`, page escalations `733-832`, units `927-932`, recall/NID demotions from sidecar `textlayer_diff` vs `PDF_JUDGE_RECALL_FLOOR=0.85`, `PDF_JUDGE_NID_FLOOR=0.80`); strip monolith `candidate_not_found` dispositions. **Only P4048R0** changes (**fail→review**); **N5036, P3828R1, P4124R0 stay review** because unit checks already emit `toc_leak` / `heading_drift` / `code_loss` defects (persona’s “zero defect groups” ignores `unit_checks[].defects`). Full monolith removal (not cnf-only): **8/181** papers differ (**5 review→pass**, **3 fail→review**: P3968R0, P4048R0, P4233R0). Logic owner: `pdf_judge.py:_fold_monolith_verdict` (`343-367`) + downstream caps; fusion (`fusion.py:187-189`) only caps merged output, not sidecar `suggested_verdict`.

- [HIGH] **Claim 1 “monolith ~17% of wall” → MODIFIED scope.** PDF monolith calls alone (**181**) → **226 s (7.5% of 3003 s)**. All first-pass calls (**378** monolith+tier-1) → **472 s (15.7%)**; persona’s **~17%** applies to **first-pass class fleet-wide**, not PDF monolith in isolation. Impact: dropping PDF monolith only saves **~226 s**, not **~476 s**.

- [HIGH] **Equal-latency-per-call is a rough but directionally fair fleet model; text lane is not uniformly cheaper.** No debug transcripts on disk; estimated user-msg bytes from `data/paperstore/<pid>.md`: median candidate **PDF 23732 B** vs **text 21661 B**; estimated monolith user payload **~51023 B** vs tier-1 **~23661 B** (monolith ≈ PDF text + full MD). Unit-check payloads: median **PDF ~26427 B** vs **text ~30103 B** (full MD + one page/section). Byte-weighted wall model → text lane **~1469 s (48.9%)** vs equal **1501 s (50.0%)**. Impact: 49.9% text share is **not materially biased** by equal latency; if anything unit-heavy text papers are **slightly slower per call** than the equal model assumes.

- [MED] **Persona 42 “1200 calls” vs measured 1201:** delta is **1 ideal-verify call** (`P4020R0`). Otherwise **197+18+197+788+1 = 1201** matches code formula `1 + I(escalated) + 1 + |unit_checks| + ideal?`.

## False-pass hypothesis

Accepting persona 16’s **3 review→pass** papers without re-running downstream unit fold would treat **N5036** (unit `toc_leak` on pages 2–3) as monolith-only review, silently clearing a localized TOC-leak signal that units already independently surface.

## False-fail hypothesis

Using **full monolith removal = 8 verdict deltas** overstates monolith marginal value: **5/8** are review→pass driven by monolith **structure reasoning** (e.g. `P2583R4` wording-markup review with **0 monolith cnf**), not missing-content cnf; conflating these inflates “safe to delete monolith” beyond measured cnf yield.

## What would change my mind

Debug transcripts (`--debug`) for the **8 full-removal delta papers** showing monolith raw `PdfJudgment.verdict` and `missing_content` lists, replayed through `_fold_monolith_verdict`, matching a cnf-only counter **≠ 1** would overturn the MODIFIED verdict-delta finding.

## Scripts

- `_scratch/research-tapetum-llm-speedup/verifier_c.py` — lane census, wall model, metadata elimination, prompt-size probe
- `_scratch/research-tapetum-llm-speedup/verifier_c_refined.py` — downstream + recall/NID verdict simulation
- `_scratch/research-tapetum-llm-speedup/verifier_c_results.json` — machine output

## Claim dispositions (Verifier-C)

| Claim | Verdict | Independent numbers |
|-------|---------|---------------------|
| **Claim 1** (16-monolith): 4/181 PDF verdict delta without monolith; ~17% wall; 228 refuted vs 87 grounded monolith quotes | **MODIFIED** | Quotes **CONFIRMED** (392/228/87/77). Wall **MODIFIED**: PDF monolith **226 s (7.5%)**; all first-pass **472 s (15.7%)**. Verdict delta **MODIFIED**: **1/181** cnf-only (**P4048R0 fail→review**); persona’s **3 review→pass refuted** (units keep review); full monolith removal **8/181**. |
| **Claim 2** (42-text-lane): 197 HTML, 1200 calls, ~1500 s (49.9%), 458 eliminable units (~572 s) | **CONFIRMED** (calls **1201** incl. 1 ideal) | **197** text OK papers, **1201 calls**, **1501 s (49.99%)**, **458** eliminable units, **572 s (19.06% fleet)**, tier-2 **18**. |
