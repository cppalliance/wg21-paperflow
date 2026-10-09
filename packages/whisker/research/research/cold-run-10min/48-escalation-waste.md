# 48 - Escalation Waste (page screen → scoped LLM)

**Verdict:** usable-with-conditions — page escalations are real but tiny (~16–18 LLM calls / 381 papers, ~0.8% of fleet calls); **100% duplicate unit checks** on overlapping pages (speedup P18); **~23 s fleet wall** was eliminable pre-v11, of which **~19 s is already captured** by metadata short-circuit at HEAD and **~4 s** remains for skip-and-synthesize dedupe.
**Confidence:** high (sidecar census + log lines reconciled; overlap replayed on workspace sidecars 2026-07-24)

**Date:** 2026-07-24. Sources: `research/tapetum-llm-throughput/{00-baseline,09-escalation-cost-auditor}.md`, `research/tapetum-llm-speedup/{00-baseline,17-metadata-short-circuit,18-escalation-overlap-auditor,48-combined-lever-modeler}.md`, `research/cold-run-10min/{10-impl-status-auditor,11-wall-arithmetic,20-payload-scoping-auditor}.md`, `packages/whisker/src/whisker/tapetum_llm/pdf_judge.py`, workspace sidecar replay (`data/whisker/llm/*.whisker.tapetum.json`, n=381).

---

## Executive answer (seconds on table)

| Lever | Status @ HEAD | Calls removed | Fleet wall @ S=16, L=20 s |
|-------|---------------|---------------|---------------------------|
| **Metadata short-circuit skips escalations** when `metadata_outline_check.verdict != pass` | **Implemented** (`pdf_judge.py:742-759`) | **15 / 18** (v10 census) | **~19 s** |
| **P18 skip-and-synthesize dedupe** (defer `_escalate_page` when `page:{N}` already in unit router selection) | **Not implemented** (`10-impl-status-auditor.md:20`) | **3 / 18** remaining on meta-pass papers (100% still overlap unit checks) | **~4 s** |
| **Combined (pre-v11 baseline)** | — | **16–18** | **~20–23 s** |

**Bottom line:** Escalation fixes are **hygiene, not a 10 min lever**. Against the **3003 s** cold wall they move **≤0.8%**. After v11, **~4 s** is still on the table from P18 dedupe; the larger **~19 s** escalation waste is already gone unless operators run `--all-pages` / `--exhaustive-units` (audit modes bypass short-circuit).

---

## How many page escalations fire?

Page escalation = deterministic `screen_pages()` flags a PDF page (`content_recall < PAGE_RECALL_FLOOR`, `tokens >= PAGE_MIN_TOKENS`), then one scoped `PageJudgment` LLM call per flagged page (cap `MAX_PAGE_ESCALATIONS=5`, serial loop `pdf_judge.py:818-825`).

| Run / source | Fleet papers | Page-esc LLM calls | PDF papers touched | Notes |
|--------------|-------------:|-------------------:|-------------------:|-------|
| Throughput cold run (2026-07-23) | 381 | **16** | **13** | stderr log + sidecars (`tapetum-llm-throughput/00-baseline.md:32`, `09-escalation-cost-auditor.md:8`) |
| Speedup v10 census (2026-07-23) | 381 | **18** | — | sidecar call graph (`tapetum-llm-speedup/18-escalation-overlap-auditor.md:8`, `147-verifier-monolith-textlane.md:8`) |
| Workspace sidecar replay (2026-07-24) | 381 | **14** | **11** | script over `data/whisker/llm/*.whisker.tapetum.json` |

Use **~16–18 calls / 381 papers (~0.04–0.05 per paper, ~7–10% of ~181 PDF papers)** for planning. The "~16 of 381" phrasing is **call count**, not paper count.

**Not tier-2 text adjudication:** HTML cascade tier-2 fired **23 / 201** papers (`09-escalation-cost-auditor.md:18`) — a separate path. This report is **PDF page escalations only**.

---

## Cost

### Fleet wall (what matters for 10 min target)

Standard closure model (`11-wall-arithmetic.md:20-24`):

```
Δwall ≈ N_esc × L / S
```

With **S=16** server slots, **L≈20 s** implied per-call latency (`tapetum-llm-speedup/00-baseline.md:24-25`):

| N_esc | Fleet wall |
|------:|-----------:|
| 16 | **20 s** |
| 18 | **22.5 s** |

Share of **3003 s** baseline: **0.7–0.75%**. Throughput persona priced page+tier-2 escalation at **~33 s / 2883 s (~1.1%)** combined (`09-escalation-cost-auditor.md:22`); page-only is the smaller slice.

### Call-volume share

| Denominator | Page escalations | Share |
|-------------|-----------------:|------:|
| ~2111 calls (throughput sidecar sum) | 16 | **0.76%** |
| 2284 calls (speedup v10 model) | 16–18 | **0.7–0.8%** |
| 2345 sidecar-counted calls (metadata verifier) | 18 | **0.77%** |

### Per-paper serial tax (does not scale fleet wall)

Escalations run **inside** the paper semaphore slot, **after** monolith + metadata, **before** unit checks (`pdf_judge.py:646-890`). Each call adds **~20–30 s** serial hold on that paper (`09-escalation-cost-auditor.md:14`). Up to **5 overlapping pages → ~100 s** on one paper (P18), but fleet wall still sums to **~23 s** because other papers fill slots.

### Payload / decode

Each escalation sends **one page source + full candidate markdown** (`pdf_judge.py:397-403`, `20-payload-scoping-auditor.md:15`). Prefill-heavy like unit checks; **~150 tok P50 output** (`47-max-tokens-shrink.md:17`). Not vision (`09-escalation-cost-auditor.md:12`).

### Yield (why the spend is low-value)

| Metric | Throughput run (16) | v10 overlap study (18) | Workspace replay (14) |
|--------|--------------------:|-----------------------:|----------------------:|
| `content_missing=true` (confirmed) | **5** (31%) | **2** | **3** (21%) |
| Refuted (`content_missing=false`) | **11** (69%) | **16** | **11** (79%) |
| Escalation pages also unit-checked | — | **18/18 (100%)** | **14/14 (100%)** |

The lane mostly **sanctions deterministic screen false flags**; unit checks on the same pages often find stricter defects anyway (P18: 6 pages escalation-sanctioned while unit returned review/fail).

---

## Dedupe opportunities (speedup P18)

**Persona:** `research/tapetum-llm-speedup/18-escalation-overlap-auditor.md` (not llm-qa-integration "P18 fuzzy demotion").

### Root cause

`judge_pdf_extraction` runs two serial loops with **no overlap guard**:

1. Page escalations — `for entry in flagged_entries: await _escalate_page(...)` (`pdf_judge.py:818-825`)
2. Unit checks — `await run_unit_checks(...)` (`pdf_judge.py:923-944`)

Both trigger on **`content_recall < PAGE_RECALL_FLOOR`**: screen per page (`pdf_judge.py:296-320`) vs router `low_recall` on `page:{N}` units (`source_router.py:209-222`). On v10 fleet, **every escalated page also had a unit check**; **764** unit-only pages had other router signals (`table_presence`, `heading_drift`, etc.) and are **not** dedupe candidates.

### Recommended fix (skip-and-synthesize, not prompt merge)

1. After `run_unit_checks` routing, **skip `_escalate_page`** when `page:{N}` ∈ `selected_unit_ids`.
2. **Synthesize** `page_escalations[]` from unit `content_omission` + `candidate_not_found` for sidecar/fusion consumers.
3. **Fallback:** keep `_escalate_page` when screen flags a page **quota skipped** (not observed in fleet: 0 screen-flagged-not-escalated papers).

**Quality:** LOW risk on measured overlap (0/2 confirmed escalation pages unit-passed; prompt fusion rejected — RuVerBench multi-rubric degradation, P18 false-fail hypothesis).

**Implementation:** **Not at HEAD** (`10-impl-status-auditor.md:20`).

### Interaction with metadata short-circuit (v11)

Pre-v11, escalations ran even when metadata already capped verdict (`17-metadata-short-circuit.md:18`): **15/18** escalation calls were on metadata **fail/review** papers — pure waste (~**19 s** fleet).

v11 short-circuit **skips the entire escalation loop** when `metadata_check.verdict != "pass"` (`pdf_judge.py:747-759`). Workspace replay: **13/14** stored escalations were on metadata non-pass (historical run artifacts); only **1** escalation on a meta-pass paper (**P4042R0**, page 1, refuted).

**Stacking:** Metadata short-circuit and P18 dedupe **overlap** on non-pass papers. Correct accounting:

```
Pre-v11 escalation waste     ≈ 18 × 20/16 = 22.5 s
− v11 metadata skip (15 calls) ≈ 15 × 20/16 = 18.75 s  [IMPLEMENTED]
= Remaining P18 dedupe       ≈  3 × 20/16 =  3.75 s  [NOT IMPLEMENTED]
```

MODERATE stack in `48-combined-lever-modeler.md` / `11-wall-arithmetic.md` books **−18 calls / −23 s** against the **pre-short-circuit 3003 s** model; at HEAD, treat **~19 s as already realized** and **~4 s as remaining**.

---

## Findings

- [CRITICAL] **Page escalations are ~16–18 LLM calls on 381-paper fleet (~0.8% of calls), not a regression driver.** Evidence: throughput log 16 lines; v10 sidecar census 18; `09-escalation-cost-auditor.md:22` (unit checks ~72% of calls). Impact: fixing escalation cannot materially move the 48→10 min program; metadata short-circuit (−1059 s) and dual-pod (−887 s) dominate (`11-wall-arithmetic.md`).

- [CRITICAL] **P18 dedupe is 100% safe on measured overlap but saves only ~23 s pre-v11, ~4 s post-v11.** Evidence: `18-escalation-overlap-auditor.md:8-16`; workspace replay 14/14 overlap. Impact: ship for hygiene and serial slot relief on meta-pass PDFs, not for ≤600 s gate.

- [HIGH] **v11 metadata short-circuit already removes ~83% of escalation calls (~19 s fleet).** Evidence: `17-metadata-short-circuit.md:18` (15/18); `pdf_judge.py:742-759`. Impact: re-measuring escalation on HEAD cold run should show **≤3 calls**, not 16.

- [HIGH] **69–79% of escalation spend refutes the screen** (`content_missing=false`) while unit checks on the same pages often still fail/review. Impact: escalation is a low-yield confirmatory pass; unit-only on routed overlap pages does not regress the 2 confirmed misses (P18).

- [MED] **Escalation + tier-2 combined ≈39 calls (~1.9% volume, ~33 s fleet)** in throughput accounting (`09-escalation-cost-auditor.md:22`). Impact: do not conflate PDF page escalations with HTML tier-2 when prioritizing levers.

- [MED] **Screen CPU (`screen_pages`) is separate waste (~38 s PDF fleet, persona 43)** and can flag pages that escalation then refutes. Impact: tightening `PAGE_RECALL_FLOOR` or caching `content_tokens` saves CPU, not the same ~23 s LLM dedupe bucket.

- [LOW] **Sidecar count drift (14 vs 16 vs 18)** reflects different `_LANE_VERSION` runs, not analysis error. Impact: use ranges for planning; re-census after next HEAD cold run.

---

## False-pass hypothesis

Skip escalation on a meta-pass paper where unit **passes** but narrow `PAGE_JUDGE_SYSTEM_PROMPT` would have returned `content_missing=true` with grounded quotes. Measured: **0/2** confirmed escalation pages unit-passed (P18). Residual: synthesize `content_missing` only from grounded unit `content_omission`, not from unit pass alone.

---

## False-fail hypothesis

Prompt-merging page judge + unit check into one call causes multi-rubric degradation (RuVerBench; P18). Prefer skip-and-synthesize over prompt fusion.

---

## What would change my mind

HEAD cold run with logging `{call_class=page_escalation}` showing **>10** calls after metadata short-circuit (proving short-circuit bypass or new overlap class), or dev-replay skip-and-synthesize with **zero** verdict regressions on `corpus/dev-replay/labels.json` (P18 acceptance test).

---

## Implementation checklist (if shipping P18 dedupe)

1. Compute `selected_unit_ids` / flagged pages **before** escalation loop (router already runs later today — reorder or precompute page set from `route_pdf_units`).
2. Filter `flagged_entries` to pages **not** in unit selection.
3. After units, append synthesized `page_escalations` entries matching `pdf_judge.py:811-818` shape for fusion/inspect.
4. Bump `_LANE_VERSION`; holdout replay per `25-quality-gate-protocol.md`.
5. Re-run fleet census — expect **0–3** live escalation calls, **~4 s** wall delta.
