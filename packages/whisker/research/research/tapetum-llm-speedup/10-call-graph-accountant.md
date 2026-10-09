# 10 - Call-Graph-Accountant

**Verdict:** usable-with-conditions (+ per-paper call graph is exact and reconciles to the 2284-call census; unit checks alone cannot reach 5–10 min without combining levers, but they are the single class with the largest wall-clock budget)
**Confidence:** high

## Findings

- [CRITICAL] **Fleet call census decomposes exactly:** 2284 LLM calls = **381 first-pass** (180 PDF monolith + 201 HTML tier-1) + **377 metadata/outline** (4 error tombstones skipped) + **~1510 unit checks** (median 5 = `MAX_UNIT_CHECKS`) + **~16 page escalations** + **~23 HTML tier-2** adjudications (tier-2 omitted from the rounded 2284 headline but present in the 2308 sidecar aggregate). Evidence: `00-baseline.md:22-23`, `research/tapetum-llm-throughput/01-call-count-accountant.md:8-15`. Impact: **66.1% of all calls are unit checks**; at ~20 s/call and 16 server slots (`00-baseline.md:24-25`), unit checks imply **~1888 s (~63%) of the 3003 s wall** under the linear slot model (2284×20/16≈2855 s closes to measured 3003 s).

- [CRITICAL] **PDF lane per-paper call graph (fleet default, serial within paper):**  
  `monolith` → `metadata_outline` → `page_escalation×0–5` → `unit_check×0–5` → optional `ideal_verify`.  
  Triggers: monolith always (`pdf_judge.py:646-657`); metadata always mandatory (`pdf_judge.py:675-684`, comment at `437-438`); page escalation when `screen_pages` flags a page and count ≤ `MAX_PAGE_ESCALATIONS=5` (`pdf_judge.py:733-763`, `constants.py:191`); unit checks when `risk_signals` non-empty or `--all-pages` (`pdf_judge.py:858-890`, `unit_judge.py:340-341` returns None if no signals and no required units); ideal when tomd ideal exists (`cli.py:1151-1158`, `ideal_verify.py:151`). All steps serial: page loop `pdf_judge.py:753`, unit loop `unit_judge.py:389`. Cross-paper: up to `_DEFAULT_CONCURRENCY=32` (`cli.py:127`, semaphore `cli.py:1112`, `asyncio.gather` `cli.py:1397`); dispatch bypasses global `run_task` Semaphore(1) via `run_judge_task` (`judge_task.py:52-74`). Measured PDF lane (n=180): median **7 calls** = 1+1+0+5 (`01-call-count-accountant.md:11,36`). Impact: each PDF paper pays **~140 s minimum serial chain** (7×20 s) regardless of fleet concurrency (`00-baseline.md:38-39`).

- [CRITICAL] **Text lane per-paper call graph (HTML / `--text-only`, serial within paper):**  
  `tier1_triage` → `tier2_adjudicate?` → `metadata_outline` → `unit_check×0–5` → optional `ideal_verify`.  
  Triggers: tier-1 always (`adjudicate.py:232-253`, chunked papers triage serially `248-252`); tier-2 only when `_escalation_signals` non-empty — axis conflict, ungrounded evidence, or ambiguous confidence band (`adjudicate.py:256-299`, `constants.py:16-31`); metadata always in `_run_html_unit_checks` (`adjudicate.py:501-508`); units when router emits `risk_signals` (`adjudicate.py:516-523`, cap `unit_judge.py:365`); chunked papers skip tier-2 (`adjudicate.py:290-291`). Measured HTML lane (n=201): median **6 calls** = 1+0+1+4; **23 papers escalated** to tier-2 (`01-call-count-accountant.md:13-15,37`). Impact: text lane adds **mandatory metadata + up to 5 units** on top of the 07-09 single-call cascade; tier-2 is **~1% of fleet calls**, not the regression driver.

- [HIGH] **Unit checks are the only call class large enough to matter for wall-clock, and 70% are zero-yield.** 1510 unit calls; **1057/1510 (70%) returned zero defect groups** (`00-baseline.md:29-30`); only **16/381 papers** had merged verdict changed by LLM findings (~143 calls per flip). Each unit call sends the **full candidate markdown** plus one page/section source (`unit_judge.py:769-776`); monolith and page escalation also embed full markdown (`pdf_judge.py:640-643`, `215-222`). Impact: **eliminating the 1057 zero-defect unit calls** would cut **~46% of fleet calls (~1380 s on the 3003 s run)** if routing were perfect — but imperfect filtering risks missing the 16 verdict-changing papers. **Quality risk: HIGH** for blind elimination, **MEDIUM** for metadata-fail short-circuit (below).

- [HIGH] **Metadata-fail short-circuit is the highest-yield elimination within the unit-check class.** PDF lane runs metadata then still runs up to 5 unit checks with no early exit (`pdf_judge.py:677-890` — no branch between metadata fail and unit loop). Fusion already caps merged verdict when metadata ≠ pass (`fusion.py:187-189`, `12-false-economy-hunter.md:14`). **244 papers** had metadata ≠ pass yet still ran **1043 unit checks** (~45% of fleet calls, est. **~1320 s**). Impact: skipping units after metadata fail saves **~1043 calls (~45% wall, ~1350 s on 3003 s)** with **no merged-verdict change** on those papers. **Quality risk: MEDIUM** — 3 papers lose unit-level sidecar defect detail that fusion already caps at review (`12-false-economy-hunter.md:28-29`); mitigated by keeping units when `table_compare` emits cell diffs (`adjudicate.py:580-597`).

- [HIGH] **In-paper parallelization of unit checks buys less than elimination at fleet scale.** Unit loop is explicitly serial (`unit_judge.py:389`); advisory lane is exempt from D11 serial rule (`judge_task.py:17-18`, `00-baseline.md:39-42`). Parallelizing 5 unit checks would shrink one paper's unit phase from ~100 s to ~20 s, but **does not reduce total call count**; with 32 papers overfilling 16 server slots (`cli.py:123-125`), fleet wall is **`total_calls × latency / slots`** (`00-baseline.md:24-25`), so parallel unit checks mostly **reshuffle queue depth**, not aggregate wall. MoE batch-composition variance is the quality-stability risk (`00-baseline.md:96`, `05-web.md:31-33`). Impact: parallelization saves **≤0 s fleet wall** when slot-saturated; **~80 s per paper** only in interactive `--all-pages` / single-paper runs. **Quality risk: MEDIUM** (verdict drift from concurrent MoE batches).

- [MED] **Page escalation and tier-2 are negligible call classes.** Page escalations: **16 calls (0.7%)**, 11/16 refuted with zero quotes (`12-false-economy-hunter.md:18`). Tier-2: **~23 calls (~1%)**. Monolith/first-pass: **381 calls (16.7%)**, ~476 s wall — cannot cut without losing whole-document coverage (`pdf_judge.py:575-577`). Ideal verification: **1 call** in fleet (`01-call-count-accountant.md:22`), uses `run_task` global Semaphore(1) (`ideal_verify.py:151`) — irrelevant at fleet scale. Impact: eliminating page escalation entirely saves **~20 s**; eliminating tier-2 saves **~29 s**.

- [MED] **No-source-packet units waste quota without LLM spend.** Router selects units before checking empty `unit_text_map` (`unit_judge.py:366-385`); **111 warnings / 102 papers** (`12-false-economy-hunter.md:8`, `00-baseline.md:30-31`). Skipped units force `coverage_complete=false` → fusion review cap. Impact: pre-filter fix costs **zero LLM calls** but recovers **MAX_UNIT_CHECKS slots** for real pages on affected papers; est. **~50–100 s** fleet wall from fewer spurious serial chains. **Quality risk: LOW**.

## False-pass hypothesis

Metadata-fail short-circuit on paper **P0533R9-class qualifier-omission** (231-vs-80 `constexpr` delta established by unit mechanical count, `unit_judge.py:604-648`): if metadata passes (`review` on heading drift only) but unit checks are skipped because a deterministic pre-gate misclassifies the paper as "metadata-failed," the fleet would merge `pass` while the only signal that catches mass keyword loss never runs. The safe cut requires short-circuit **only when metadata verdict is `fail`**, not `review`.

## False-fail hypothesis

Pre-filtering empty-packet units before quota selection (`unit_judge.py:366` before `379-385`) could leave a paper with `coverage_complete=true` while a **critical table_corruption signal** on an unroutable page never gets an LLM look, letting a localized table swap survive as `pass` on the LLM lane if monolith and metadata both pass. Mitigation: treat unroutable critical signals like cap overflow — force `review` without spending a slot (`unit_judge.py:460-464`).

## What would change my mind

Sidecar replay showing **>16 papers** where a unit check (not monolith/metadata) supplied the sole evidence for `llm_rescue_heading` or `llm_clear_soft_review` on a metadata-pass paper would mean metadata-fail short-circuit is unsafe at the measured 45% savings estimate and the waste figure in `12-false-economy-hunter.md` is too aggressive.

## Call-class ledger (3003 s cold fleet, 381 papers)

| Call class | Calls | Share of 2284 | Est. wall (s) | Share of 3003 s | Serial / parallelizable | Primary trigger |
|------------|------:|--------------:|--------------:|----------------:|:------------------------|:----------------|
| First pass (monolith / tier-1) | 381 | 16.7% | ~476 | 15.9% | Serial per paper; parallel across papers (c=32) | Always |
| Metadata / outline | 377 | 16.5% | ~471 | 15.7% | Serial | Always mandatory (`pdf_judge.py:677`, `adjudicate.py:501`) |
| **Unit check** | **1510** | **66.1%** | **~1888** | **~62.9%** | **Serial loop** (`unit_judge.py:389`); **could** parallelize per paper (D11 exempt) | `risk_signals` or `--all-pages` (`pdf_judge.py:880`, `unit_judge.py:340`) |
| Page escalation | 16 | 0.7% | ~20 | 0.7% | Serial loop (`pdf_judge.py:753`) | Per-page recall screen flag (`pdf_judge.py:636`, `733`) |
| Tier-2 adjudicate | ~23 | ~1.0% | ~29 | ~1.0% | Serial after tier-1 | `_escalation_signals` (`adjudicate.py:293-299`) |
| Ideal verification | ~1 | ~0% | ~1 | ~0% | Serial; global Semaphore(1) via `run_task` | Ideal file exists (`cli.py:1124-1158`) |

**Single class with largest wall-clock lever:** **unit checks** — metadata-fail **elimination** (~1350 s, 45%) beats **parallelization** (~0 s fleet when slot-saturated). Reaching 5–10 min still requires stacking dual-pod sharding, prefix caching (`05-web.md:6-12`, `69-73`), and/or warm incremental skip (`00-baseline.md:19-20`).
