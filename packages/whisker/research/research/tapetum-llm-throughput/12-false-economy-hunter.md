# 12 - False-Economy-Hunter

**Verdict:** usable-with-conditions (+ the regression price is real call volume, but ~47–58% of tonight's LLM wall bought no merged-verdict change and often no finding; fixes are routing/filter policy, not concurrency)
**Confidence:** high

## Findings

- [CRITICAL] **111 "no source packet" warnings spend zero LLM tokens but burn quota and force review caps.** Code selects units first (`unit_judge.py:356-358` `_select_units_with_quotas`), then skips the call when `unit_text_map` is empty (`unit_judge.py:381-385`: `if not source_text: ... continue`). Skipped units land in `unchecked_unit_ids` (`unit_judge.py:384`), making `coverage_complete=False` (`unit_judge.py:446-449`), which triggers `source_aware_review_cap` in fusion (`fusion.py:192-195`, `_source_aware_requires_review`). Runtime: 111 warnings across 102 papers in `_scratch/whisker-fullrun/llm-stderr.txt` (baseline `00-baseline.md:32-33`). Example: `P2929R2` logged `section:0 has no source packet`; sidecar shows `section:0` only in `heading_drift` risk with empty section body, while the 4 executed unit checks ran on other sections. Impact: false economy is not the LLM call (skipped) but the **slot + cap chain**; dropped units still count against the effective `MAX_UNIT_CHECKS=5` budget because selection happens before the guard.

- [CRITICAL] **321/381 merged papers are capped at review by `source_aware_review_cap` regardless of unit outcomes.** Fusion rule counts from `data/whisker/llm/report-merged.json`: 321 `source_aware_review_cap`, 9 `llm_rescue_heading`, 7 `llm_clear_soft_review`, 13 `agree`, 14 `whisker_fail_locked`. Only **16 papers** (9+7) had LLM-driven merged-verdict changes; `llm_escalate_major` fired 0 times. Fusion applies the source-aware cap **before** clear/rescue rules (`fusion.py:410-423` precedes `llm_clear_soft_review` at `fusion.py:477-519`). Sidecar cap drivers (replaying `_source_aware_requires_review`): 240 metadata-not-pass, 101 coverage-incomplete, 3 accepted defect groups. Impact: on 321 papers, **1321 unit LLM calls** (~86% of all unit calls) cannot change the merged verdict; **143 LLM calls per verdict actually changed** (2308 total calls / 16 flips, aligned with `01-call-count-accountant.md` aggregate).

- [CRITICAL] **70% of unit checks returned no defects (1057/1510).** Sidecar aggregate over `data/whisker/llm/*.whisker.tapetum.json`. These calls produced no sidecar finding and, for the 321 cap papers, no fusion movement. Combined with 11 refuted page escalations (`confirmed=False`, `quotes=0` in 11 of 16 escalation log lines in `llm-stderr.txt`; confirmation logic `pdf_judge.py:797-800`), **1068 calls (46.7%) changed no verdict and produced no finding** → **~1347 s of 2886 s** under a linear call-cost model. Broader "no verdict change" set (all unit calls on cap papers + refuted escalations): **1332 calls (58.2%) → ~1680 s**.

- [HIGH] **Metadata outline check already predetermines fusion for 244 papers, yet those papers still ran 1043 unit checks (avg 4.27/paper).** Sidecars: 244 with `metadata_outline_check.verdict != pass` (213 review, 27 fail). Fusion caps any non-fail merge when metadata ≠ pass (`fusion.py:187-189`) without reading unit results. PDF lane already folds metadata into `suggested_verdict` (`pdf_judge.py:711-714`). Impact: **~1043 unit calls (~45% of fleet LLM calls)** are fusion-dead on metadata-fail papers; they only re-confirm a cap already set by the mandatory metadata call (`pdf_judge.py:677`, `adjudicate.py:501`).

- [HIGH] **Risk routing fires on nearly the whole corpus while the page screen rarely fires.** Baseline: every logged paper `all_pages=False` (`00-baseline.md:35-36`). Sidecars: 376/381 papers have non-empty `risk_signals`; only 5 have zero. Log parse of 181 PDF `pdf-judge` lines: `screen_flagged=0` on **168/181** papers but `risk_signals` mean **15.2** (range 0–121). Router still selects up to `MAX_UNIT_CHECKS=5` (`unit_judge.py:355`, `constants.py:223`). Impact: unit checks run on pages the deterministic screen cleared; **179/180 PDFs saturated the 5-check cap** (`01-call-count-accountant.md:30`).

- [MED] **16 page escalations: 11 pure refutations, 5 confirmed misses.** Log: 16 `escalation` lines (`00-baseline.md:32`); 11 with `content_missing=False confirmed=False quotes=0`. Each refutation still paid a full scoped LLM call (`pdf_judge.py:756-759` `_escalate_page`). Impact: **~69% of escalation spend** bought nothing; small absolute cost (11 calls) but zero marginal signal.

- [LOW] **Empty-packet root cause is router/signal mismatch, not a missing LLM retry.** HTML `heading_drift` signals attach to `section:{outline_index}` (`source_router.py:286-287`) while packets come from `section:{unit.section_id}` (`adjudicate.py:519-520`). IDs usually align, but title-only / empty-body sections yield `source_text=""` and hit the skip guard. Impact: quota slots consumed by signals that can never produce a scoped call.

## False-pass hypothesis

A paper with metadata `review`, five empty unit checks, and `coverage_complete=False` still merges to `review` via `source_aware_review_cap` (`fusion.py:410-423`). A human reading only the merged report sees "LLM reviewed 5 units" when nothing was verified and the cap was already fixed by metadata; the extra calls did not increase safety, only latency.

## False-fail hypothesis

Skipping all unit checks when metadata fails would miss the **3 papers** whose only accepted high/critical defects came from unit checks (cap-reason `defect_groups` in sidecar replay). Those defects are real findings even though fusion stays `review`; a blanket skip would remove sidecar evidence, not merged verdict, but could hide actionable unit-level quotes in inspect output.

## What would change my mind

Debug transcripts showing unit checks on metadata-pass papers (`137` papers, `467` unit calls) that actually flipped merged verdicts beyond the 16 counted rules would mean unit spend is buying more than this analysis captured. A single counterexample PID with `combined_rule=llm_clear_soft_review` or `llm_rescue_heading` where a unit check (not metadata/monolith) supplied the decisive evidence would also shrink the waste estimate.

## Spend summary (2026-07-23 fleet, 2886 s wall)

| Waste class | Calls | Share of ~2308 | Est. seconds |
|-------------|------:|---------------:|-------------:|
| Empty unit checks + refuted escalations (no finding, no verdict change) | 1068 | 46.7% | ~1347 |
| All unit calls on `source_aware_review_cap` papers + refuted esc (no verdict change) | 1332 | 58.2% | ~1680 |
| Unit calls on metadata-already-failed papers (fusion-dead) | 1043 | 45.2% | ~1320 |

## Cheapest safe cut (ranked)

1. **Pre-filter before quota selection:** In `run_unit_checks`, drop `unit_id`s with empty `unit_text_map` entries *before* `_select_units_with_quotas` (`unit_judge.py:354-358`). Stops 111 no-packet warnings from consuming `MAX_UNIT_CHECKS` slots and from poisoning `coverage_complete`. Cost: zero LLM today; reduces spurious caps. Risk: low.

2. **Defer unit checks when metadata outline already failed (fleet routed mode):** After `run_metadata_outline_check`, if `verdict != pass`, skip `run_unit_checks` unless table-compare or deterministic signals require follow-up. Saves **~1043 calls (~45%)**, est. **~1200–1300 s**. Fusion-safe for merged verdict because `_source_aware_requires_review` already fires on metadata (`fusion.py:187-189`). Risk: medium (3 papers lose unit-level defect sidecar detail; mitigated by keeping checks when table_compare emits high-severity diffs).

3. **Tighten HTML `heading_drift` routing:** Do not emit `RiskSignal` for outline indices whose `unit_text_map` entry is empty (`source_router.py:285-312`). Stops selecting uncallable units. Complements (1).

Do **not** cut the mandatory metadata call or monolith/triage first pass: metadata failure is the primary cap signal for 240 papers; monolith remains the only whole-document pass on PDFs (`pdf_judge.py:649` comment, serial cascade).
