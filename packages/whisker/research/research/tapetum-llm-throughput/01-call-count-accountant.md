# 01 - Call-Count-Accountant

**Verdict:** usable (+ exact per-paper call formula reconstructed from code; sidecar aggregate matches within 4 error tombstones)
**Confidence:** high

## Findings

- [CRITICAL] Tonight's 381-paper fleet run issued **2308 LLM calls** across 377 successful sidecars (mean **6.11 calls/paper**, median **7**, min **2**, max **10**). Evidence: sidecar aggregation over `data/whisker/llm/*.whisker.tapetum.json` (381 files); 4 error tombstones (`P3400R3`, `P3977R0`, `P4182R0`, `P4228R0`) contribute ~0 calls each (`status=error`, no `metadata_outline_check`). Impact: call volume is **~5.9×** the 07-09-era estimate (~389 calls for the same PDF/HTML mix), not a hidden multiplier.

- [CRITICAL] **PDF lane formula (fleet default, `all_pages=False`):**  
  `calls = 1 (monolith) + 1 (metadata/outline) + |page_escalations| + |checked_unit_ids|`  
  with `|page_escalations| ≤ MAX_PAGE_ESCALATIONS=5` (`constants.py:191`, `pdf_judge.py:738-763`) and `|checked_unit_ids| ≤ MAX_UNIT_CHECKS=5` when `risk_signals` non-empty (`unit_judge.py:355-358`, `pdf_judge.py:880-890`). Evidence: `run_judge_task` at `pdf_judge.py:650`, `run_metadata_outline_check` at `pdf_judge.py:677`, `_escalate_page` → `run_judge_task` at `pdf_judge.py:398`, `_check_one_unit` → `run_judge_task` at `unit_judge.py:755`. Measured PDF lane (n=180): median **7** = 2 + 0 page esc + 5 units; mean **6.43**; page escalations fired on **13** papers (max **3** calls). Impact: every PDF paper pays **+1 mandatory metadata** and **~5 unit checks** on top of the 07-09 monolith-only path.

- [CRITICAL] **HTML/text lane formula:**  
  `calls = 1 (tier-1 triage) + I(escalated) + 1 (metadata/outline) + |checked_unit_ids|`  
  with tier-2 only when `_escalation_signals` non-empty (`adjudicate.py:256-299`), metadata always in `_run_html_unit_checks` (`adjudicate.py:501`), units capped at 5 (`unit_judge.py:355`). Evidence: `run_agent` tier-1 at `adjudicate.py:242`, tier-2 at `adjudicate.py:299`, `run_metadata_outline_check` at `adjudicate.py:501`, unit checks at `adjudicate.py:523`. Measured HTML lane (n=201): median **6** = 1 + 0 tier-2 + 1 metadata + 4 units; **23** papers escalated to tier-2. Impact: HTML papers gained **+1 metadata + up to 5 units** since 07-17; tier-2 rate (~11%) is higher than the 07-09 benchmark (**13/200 ≈ 6.5%**, `00-baseline.md:61`) but is not the dominant multiplier.

- [HIGH] **Evidence verification is zero LLM calls.** Monolith missing-content quotes, page-escalation quotes, and unit-check defect quotes are grounded deterministically via `ground_spans` + `classify_candidate_evidence` (`pdf_judge.py:696-697`, `791-806`) and `verify_unit_evidence` (`unit_judge.py:656-728`). Impact: the suspected "per-finding LLM verification" multiplication does **not** exist; cost is in explicit judge/unit calls only.

- [HIGH] **07-09-era cascade was ~1 LLM call per paper.** At commit `58a978c`, `pdf_judge.py` had a single `run_judge_task` (monolith only; no `run_metadata_outline_check`, `run_unit_checks`, or `_escalate_page` in that revision). Text lane was tier-1 + occasional tier-2: **213 calls / 204 papers** (`00-baseline.md:61-62`). Reconstructed 07-09 total for tonight's mix (180 PDF × 1 + 201 HTML × 1.06): **~389 calls**. Impact: the throughput regression is **primarily call-multiplication**, not a concurrency/scheduling pathology (`00-baseline.md:38-39` steady ~8 papers/min rules out stall).

- [MED] **Optional paths did not multiply tonight's fleet.** Ideal verification: **1** paper (`ideal_verify.py:151` via `cli.py:1129`; 1 sidecar with `ideal_verification`). Vision/VLM: dormant (`vision_task.py:23-24`; fleet CLI routes PDFs through `judge_pdf_extraction`, not `vlm_pipeline.py`). Readback: separate CLI, not in bare fleet run. Impact: no hidden global serialization from `_VISION_TASK_CONCURRENCY=1` (`00-baseline.md:94-97`).

- [MED] **Arithmetic attribution of the 4.2× wall regression (692 s → 2883 s):**  
  - Call-volume ratio (successful papers): **2304 / 389 ≈ 5.9×**  
  - Observed wall ratio: **2883 / 692.3 ≈ 4.17×** (`00-baseline.md:10-14`, `27-28`)  
  - Implied per-call effective cost ratio: **4.17 / 5.9 ≈ 0.71×** (unit/metadata scoped calls appear ~30% cheaper per call than the old monolith/triage calls, consistent with shorter output discipline: metadata 40 words, unit 40 words vs monolith 60 words, `unit_judge.py:126-158`, `pdf_judge.py:203-212`).  
  - Bottom line: **~70–85% of the regression is explained by explicit 07-17 call multiplication**; the remainder is modest per-call latency/prompt growth (07-22 `CONVERSION_CONTRACT` inlined into every unit prompt, `00-baseline.md:74-77`), not a secret call site.

- [LOW] **Router fires on nearly the entire corpus:** **376/381** papers have `risk_signals`; **179/180** PDFs ran **5** unit checks (median). Only **5** papers had zero risk signals (4 errors + 1 clean skip path). Impact: `MAX_UNIT_CHECKS=5` cap is saturated on most papers; lowering wall requires routing precision or cap policy change, not finding a hidden batching bug.

## Calls-per-paper summary table

| Lane | Min | Median | Max | Mean | Formula |
|------|-----|--------|-----|------|---------|
| PDF (n=180) | 2 | 7 | 10 | 6.43 | 2 + page_esc + units |
| HTML (n=201) | 1* | 6 | 8 | 5.73 | 1 + tier2 + meta + units |
| **Fleet (n=381)** | **1*** | **7** | **10** | **6.11** | weighted mix |
| **07-09 estimate** | 1 | ~1 | 2 | ~1.02 | 1 (+ tier2 on HTML) |

\*Min 1 = error tombstones only; successful PDF minimum observed = **2** (monolith + metadata, zero risk units).

## False-pass hypothesis

A paper with saturated routing (5 unit checks all `pass`) plus monolith `pass` still receives **7 LLM calls**; if the router's `heading_drift` noise fires on clean papers (`00-baseline.md:104-108` back-of-envelope), the cascade spends full serial budget confirming absence of defects the deterministic lane already cleared. That is wasted cost, not a false pass, but it masks whether extra calls buy signal.

## False-fail hypothesis

none found (this persona counts calls, not verdict quality).

## What would change my mind

Debug transcripts for all 377 successful papers showing a `run_judge_task` / `run_agent` / `run_task` label count that diverges from sidecar-derived totals by more than retry duplicates (54 model retries, `00-baseline.md:28`) would indicate an unlogged call site.
