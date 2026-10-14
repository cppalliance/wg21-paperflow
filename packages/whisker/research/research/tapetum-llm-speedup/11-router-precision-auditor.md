# 11 - Router-Precision-Auditor

**Verdict:** usable-with-conditions (+ sidecar replay proves 68.6% zero-defect unit checks and a safe ~12% call cut via combined soft filters, but router-only tightening cannot reach the 5–10 min target without missing 6/47 defect-group papers)
**Confidence:** high

## Findings

- [CRITICAL] **`heading_drift` dominates routed volume and zero-defect checks.** Sidecar aggregate (`data/whisker/llm/*.whisker.tapetum.json`, 381 papers): **5237/7997 (65%)** risk-signal firings; on checked units **903/1284 (70.3%)** returned zero defects. HTML lane accounts for **3876** outline-level mismatches (`source_router.py:285-312`); PDF large-font prose adds **1361** (`source_router.py:236-255`). Impact: caps `MAX_UNIT_CHECKS=5` (`constants.py:223`) with medium-severity noise; estimated **~0 s** recoverable without a filter because quota already saturates only 256/376 checked papers at 5 calls. Quality risk: displaces higher-value units (PR286 P1068R11: nine `heading_drift` signals consumed five slots, pages 5–9 unchecked).

- [CRITICAL] **`table_presence` is unconditional on any PDF table page and precision-poor.** Evidence: `source_router.py:257-263` emits high-severity signal whenever `unit.has_tables`; fleet **1478** firings (PDF-only), **313/511 (61.3%)** zero-defect on checked units. **1465/1478** table pages have no co-occurring `low_recall` on the same unit. Dropping all `table_presence` (simulated quota replay) saves **149 calls (9.1%) ≈ 186 s wall** (@ 20 s/call, 16 slots, `00-baseline.md:24-25`) but **misses 11/47 defect-group papers** (e.g. P3181R1, P4003R0, P4123R0). Impact: blunt removal is unsafe; see soft cap below.

- [HIGH] **`low_recall` is the lowest-yield checked signal but mostly non-tunable.** Checked units: **241/279 (86.4%)** zero-defect. Recall distribution on 914 signals: **894 <0.80**, **16 in [0.85,0.90)**, **4 in [0.80,0.85)** (all flagged because recall `< PAGE_RECALL_FLOOR/SECTION_RECALL_FLOOR = 0.90`, `constants.py:177,211`). Lowering floor **0.90→0.85** drops only **16 signals**; **5/16** checked units in that band had defects. Impact: **~1 call saved (~1 s wall)**; false-negative risk on marginal HTML section loss. Raising floor would add calls, not cut them.

- [HIGH] **`token_delta` and `missing_captions` never fire on this fleet.** Runtime: **0** sidecar signals vs implemented paths `source_router.py:184-207,224-234`. PDF keyword delta needs `TOKEN_DELTA_THRESHOLD=5` (`constants.py:219-221`); captions require `_CAPTION_RE` matches in `textlayer.py:241-244`. Impact: no cut available here without new corpus coverage; do not spend tuning budget on thresholds that did not activate across 381 papers.

- [HIGH] **Combined safe router tightening saves ~12% unit calls with bounded FN.** Simulated quota replay (381 sidecars, `MAX_UNIT_CHECKS=5`, `SIGNAL_CLASS_QUOTA=1`): (a) **one `table_presence` per paper** (first table page only), (b) drop PDF `heading_drift` with `detail` >120 chars containing `large-font` (prose mis-extraction per PR286), (c) `SECTION_RECALL_FLOOR` **0.90→0.85**. Saves **190 calls (11.6% of ~1634 routed selections) ≈ 238 s wall**; **6/47 defect-group papers** lost (vs 3 baseline simulation gap). Impact: **~8% of 3003 s cold run**, not sufficient alone for 5–10 min target; acceptable only with holdout replay on missed PIDs.

- [MED] **`missing_code` (HTML) is small but relatively productive.** **369** firings, **147** checked units, **66.0%** zero-defect, **50/147 (34.0%)** unit-level defects; only **1** defect-group paper relied exclusively on this signal. Tightening `source_router.py:344-353` is low ROI. Impact: defer.

- [MED] **Pre-filter empty source packets before quota, not after selection.** `run_unit_checks` selects units then skips empty `unit_text_map` entries (`unit_judge.py:366-368` then `389-398`), causing **111** no-packet warnings across **102** papers (`12-false-economy-hunter.md`). HTML `heading_drift` on empty outline sections (`source_router.py:285-312` vs `adjudicate.py:519-520` ID mismatch) poisons `coverage_complete`. Impact: **0 LLM tokens today** but fewer spurious review caps; move filter before `_select_units_with_quotas` (`unit_judge.py:175-213`). Quality risk: **none** (calls were already skipped).

- [LOW] **`SIGNAL_CLASS_QUOTA=1` guarantees one slot per signal class even when 70% of checks are empty.** Evidence: `constants.py:229-233`, `_select_units_with_quotas` phase 1 (`unit_judge.py:186-203`). With **4+ signal types** on many PDFs, quota burns slots on `table_presence` before `low_recall`. Impact: lowering quota to 0 for `table_presence` when `table_corruption` from `table_compare` exists (`adjudicate.py:580-597`) could reclaim slots; not measured separately in replay.

## False-pass hypothesis

**One `table_presence` per paper** (`combo_safe` simulation): P4025R1/P4025R2 had defects on multiple table pages (sidecar replay); keeping only the first table page would skip later corrupted tables that `table_compare` did not cell-diff, yielding `pass` unit checks and empty `defect_groups` on those pages while the monolith still says `review`. Measured FN: **6/47** defect-group papers under the combined safe bundle.

## False-fail hypothesis

Unconditional **`table_presence` on all 1478 PDF table pages** saturates `MAX_UNIT_CHECKS=5` on **256/376** checked papers (sidecar `checks_per_paper[5]=256`), leaving **uncheckable high-severity units** in `unchecked_unit_ids` (`unit_judge.py:370-372`). Fusion then caps at `review` via incomplete coverage (`fusion.py:192-195`) even when the conversion is clean, i.e. router over-fire causes false-fail at the advisory layer without finding defects.

## What would change my mind

Holdout replay on the **6 missed PIDs** from `combo_safe` (P3181R1, P3725R2, P3865R2, P3865R3, P3891R1, P3938R1, P4003R0, P4025R1, P4025R2, P4090R0, P4123R0 subset) showing monolith or deterministic `table_compare` already surfaces the same defect groups would downgrade FN risk to LOW and justify shipping the combined filter.
