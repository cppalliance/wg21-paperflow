# 24 - Fusion-Dead 44.6% Re-Verification (HEAD, `_LANE_VERSION=11`)

**Verdict:** usable-with-conditions — P145's fusion-dead algebra and **1047/2345 (44.6%)** unit-call fraction still hold at HEAD; v11 **implements** the skip on the default fleet path, so the lever is realized savings, not a hypothetical counterfactual.
**Confidence:** high

## Executive answer

| Question | Answer |
|----------|--------|
| **Claim still holds?** | **Yes** |
| **Caveat (one line)** | 44.6% is a **v10 sidecar replay** denominator; v11 default runs no longer emit those calls; **`--inspect` / `--exhaustive-units` / `--all-pages` bypass** the skip and still pay full unit cost; inspect detail (`defect_groups`, localized quotes) is still lost on short-circuited papers. |

---

## Findings

- [CRITICAL] **`_LANE_VERSION = 11` confirms metadata short-circuit shipped; fusion-dead logic unchanged.** Evidence: `cli.py:119-123` documents v11 as "metadata-fail short-circuit … verified zero verdict drift on 378-paper fleet, 44.6% call elimination"; `tapetum_llm.md:334` repeats the same contract. Impact: cold default fleet captures the P145 savings without operator flags; fusion algebra review is about correctness of that skip, not whether it is still paper-only.

- [CRITICAL] **Fusion still caps before unit evidence when metadata ≠ pass.** Evidence: `fusion.py:187-189` — `_source_aware_requires_review` returns `True` immediately when `metadata_outline_check.verdict != pass`, before `unit_coverage`, `defect_groups`, or accepted-disposition checks (`191-227`). Cap fires at `fuse_verdicts` **before** clear/rescue branches (`410-423` vs `477-519`). Tests: `test_fusion.py:462-473` (`test_html_metadata_fail_or_review_caps_pass_at_review`). Impact: unit findings cannot promote whisker `pass`/`review` to fused `pass` when metadata already non-pass; P145 "fusion-dead" definition still satisfied.

- [CRITICAL] **Lane verdict fold still one-way: metadata caps first; units only demote `pass → review`.** Evidence: PDF — metadata fold `pdf_judge.py:736-740` before short-circuit guard `742-759`; unit demotion only `982-983` (`unit_result.verdict == "review" and verdict == "pass"`). HTML — metadata short-circuit in `_run_html_unit_checks` `521-531`; fold in `_custom_decide` `382-392` (fail overwrites; review demotes pass; units demote pass only). `run_unit_checks` aggregate verdict is pass/review only (`unit_judge.py` doc + fold). Impact: units cannot lift metadata-capped LLM verdicts; cannot force `fail` from metadata-review base.

- [CRITICAL] **44.6% arithmetic unchanged as v10 fleet replay.** Evidence: P145 sidecar replay — **232** metadata-non-pass papers, **1047** unit LLM calls, fleet denominator **2345** LLM calls → **1047/2345 = 44.65% ≈ 44.6%**; wall model **3003.4 × 1047/2345 ≈ 1341 s** (`145-verifier-metadata-short-circuit.md:10-14`, `00-baseline.md:25`). No code change at v11 alters which papers are metadata-non-pass or how many unit checks they would have received under v10 routing. Impact: baseline table row in `cold-run-10min/00-baseline.md` remains valid for planning.

- [HIGH] **Short-circuit sidecar shape is fusion-safe.** Evidence: when skipped, `pdf_judge.py:1057-1066` sets `unit_coverage.mode = "metadata_short_circuit"`, empty unit lists, `coverage_complete=True`. Fusion metadata check runs **before** coverage completeness (`fusion.py:187-193`), so vacuous complete coverage does not bypass the metadata cap. Impact: v11 sidecars fuse identically to P145 counterfactual (strip units, force complete).

- [HIGH] **Default fleet path skips the 1047 calls; audit modes exempt.** Evidence: guard `pdf_judge.py:748-752` (`metadata != pass ∧ ¬all_pages ∧ ¬exhaustive_units`); skip body `798+`; HTML mirror `adjudicate.py:523-531`. CLI maps `--inspect` → `exhaustive` coverage mode `cli.py:199-200`, bypassing short-circuit via `exhaustive_units` at `cli.py:1326-1328`. Tests: `test_pdf_judge.py:2067-2137`, `test_source_aware_integration.py:627+`. Impact: 44.6% is **eliminated on default cold run**, not merely fusion-dead; inspect/golden-PR runs still pay full unit cost.

- [MED] **Inspect completeness cost unchanged from P145.** Evidence: short-circuit leaves `unit_checks=[]`, `defect_groups=[]`, `page_escalations=[]` on metadata-non-pass papers; P145 quantified **35 defect groups / 30 papers** lost to `--inspect` with zero verdict drift. Impact: speed lever is verdict-stable; human triage channel still degraded unless audit flags used.

- [LOW] **Text-only PDF adjudicate path has no metadata short-circuit.** Evidence: `_run_pdf_unit_checks` (`adjudicate.py:557-639`) runs units without metadata guard; only used when `use_pdf_judge` is false (`cli.py:1204-1205`, e.g. `--text-only`). Fleet PDFs (~184/381) use `judge_pdf_extraction`. Impact: edge-case path still wastes unit calls; does not invalidate fleet 44.6% claim.

---

## Code drift vs P145 citations

| P145 reference | HEAD (`_LANE_VERSION=11`) | Logic change? |
|----------------|---------------------------|---------------|
| `fusion.py:187-189` metadata early return | `fusion.py:187-189` | **No** |
| `fusion.py:410-423` cap before clear | `fusion.py:410-423` | **No** |
| `pdf_judge.py:711-714` metadata before units | Metadata `700-714`; fold `736-740`; **short-circuit `742-759`** | **Added skip** (v11) |
| `pdf_judge.py:927-928` unit demotion | `982-983` | **No** (line shift) |
| `adjudicate.py:371-381` metadata fold | `_custom_decide` `382-392` | **No** |
| (not in P145) HTML unit short-circuit | `adjudicate.py:521-531` | **Added** (v11) |

---

## False-pass hypothesis

Default metadata short-circuit on **review**-tier metadata skips all unit checks while fusion and `suggested_verdict` stay capped at `review`. A human running fleet output (not `--inspect`) clears on metadata heading drift without seeing accepted high/critical unit evidence (P145: 19 metadata-review papers with accepted exact+cnf findings). Verdict unchanged; inspect-channel false-clear risk remains.

## False-fail hypothesis

None on verdict path. Metadata-fail tier: stripping units cannot demote below `fail` (`pdf_judge.py:737-738`). Fusion cannot hard-fail whisker pass from metadata non-pass alone (caps at `review` via `FUSION_RULE_SOURCE_AWARE_REVIEW_CAP`).

## What would change my mind

Any HEAD default-fleet sidecar where `metadata_outline_check.verdict ∈ {fail, review}`, replaying `fuse_verdicts` with units/`defect_groups` stripped vs full sidecar, changes `combined_verdict` or `suggested_verdict` — or a fresh v11 fleet recount showing metadata-non-pass unit calls ≠ **1047** on the same 378-paper ok set.
