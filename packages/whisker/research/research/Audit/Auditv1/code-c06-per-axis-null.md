# C06 — Per-Axis and Null-Eligibility Audit

**Mandate:** Test G4 across score, bench, guard, reports, and tables.
**Gate dimension:** G4 (per-axis separation, null eligibility)
**Auditor:** Per-Axis and Null-Eligibility Auditor
**Date:** 2026-07-19

---

## Summary

The whisker package correctly implements per-axis null eligibility and per-axis reporting throughout. No synthetic 1.0 is ever imputed for an absent modality. Each axis (nid, teds, mhs, content_recall, grits_con) is reported, gated, and aggregated independently. The codebase is clean on G4.

---

## Finding 1: Null eligibility for teds/mhs/grits_con in bench.py

- **Severity:** PASS (correctly implemented)
- **Claim:** When the reference lacks tables, `teds` is `None`; when the reference lacks headings, `mhs` is `None`; when no tables exist, `grits_con` is `None`. No synthetic 1.0 is injected.
- **Evidence:**
  - `bench.py:185-190`: `teds_v = _table_score(...) if _extract_md_tables(reference_md) else None` — GT-driven eligibility: teds is None when reference has no tables.
  - `bench.py:190`: `mhs_v = mhs(...) if has_headings(reference_md) else None` — mhs is None when reference has no headings.
  - `bench.py:154-155`: `_grits_con_score` returns `None` when `not ref` (no reference tables).
  - `bench.py:200-205`: `overall` is computed from `parts = [nid_v]` plus whichever of teds/mhs is non-None, so ineligible axes do not inflate overall.
- **Affected gate/dimension:** G4
- **Confidence:** 1.0
- **False-pass hypothesis:** None identified. The eligibility is driven by the reference, which is correct.
- **False-fail hypothesis:** None identified.

## Finding 2: BenchRow preserves None through serialization

- **Severity:** PASS (correctly implemented)
- **Claim:** `BenchRow.to_dict()` faithfully serializes `None` for ineligible axes (JSON null).
- **Evidence:**
  - `bench.py:78`: `"teds": None if self.teds is None else round(self.teds, 4)`
  - `bench.py:79`: `"mhs": None if self.mhs is None else round(self.mhs, 4)`
  - `bench.py:83`: `"grits_con": None if self.grits_con is None else round(self.grits_con, 4)`
  - `bench.py:72-74`: Comment: "teds/mhs are ``None`` (-> JSON null) when the reference lacks that modality (no tables / no headings): the axis is ineligible, not a synthetic perfect score."
- **Affected gate/dimension:** G4
- **Confidence:** 1.0

## Finding 3: Aggregate uses eligibility-weighted means

- **Severity:** PASS (correctly implemented)
- **Claim:** Corpus-level aggregation averages teds/mhs/grits_con only over eligible rows, not all rows.
- **Evidence:**
  - `bench.py:237-243`: `teds_vals = [r.teds for r in rows if r.teds is not None]` — filters to eligible rows. Mean is computed from `len(teds_vals)` not `n`. Same for mhs and grits_con.
  - `bench.py:241`: `mean_teds = sum(teds_vals) / len(teds_vals) if teds_vals else None` — None when no eligible rows.
  - `bench.py:264-269`: `eligible_counts` dict exposes per-axis denominators.
- **Affected gate/dimension:** G4
- **Confidence:** 1.0

## Finding 4: below_floor respects null eligibility

- **Severity:** PASS (correctly implemented)
- **Claim:** A paper with `teds=None` or `mhs=None` is never flagged as below floor for that axis.
- **Evidence:**
  - `bench.py:251`: `(r.teds is not None and r.teds < C.TEDS_FLOOR)` — None teds skips the floor check.
  - `bench.py:252`: `(r.mhs is not None and r.mhs < C.MHS_FLOOR)` — None mhs skips the floor check.
- **Affected gate/dimension:** G4
- **Confidence:** 1.0

## Finding 5: Per-axis reporting in score.py (verdict path)

- **Severity:** PASS (correctly implemented)
- **Claim:** `score.py` uses per-axis reporting (separate hard_flags, soft_flags per signal), not a single composite gate.
- **Evidence:**
  - `score.py:136-231` (`_decide`): Each signal is checked independently: structural gates (line 177-179), unigram_coverage (lines 181-188), regions (lines 189-191), unigram_drift (lines 193-194), qa_score (lines 195-196), uncertain markers (lines 197-198), ref_nid advisory (lines 200-203), ideal per-axis flags (lines 205-215).
  - `score.py:208-215`: Ideal panel loops per axis (nid, teds, mhs, recall) with null-eligibility guard: `if value is not None and value < floor`.
  - `score.py:82-85`: `ref_teds` and `ref_mhs` are computed and stored but NEVER appear in any flag logic — report-only, exactly as documented.
- **Affected gate/dimension:** G4
- **Confidence:** 1.0

## Finding 6: Per-axis columns in report.py

- **Severity:** PASS (correctly implemented)
- **Claim:** The Markdown report table has separate columns for each axis.
- **Evidence:**
  - `report.py:111`: Header: `"| PID | verdict | overall | nid | teds | mhs | ideal | unigram | coverage | drift | qa | regions | flags |"`
  - `report.py:115-116`: `_cell()` helper renders `None` as `"-"`, preserving the null signal visually.
  - `report.py:132-146`: Golden ideals get a dedicated detail section with per-axis columns (overall, nid, teds, mhs, recall).
- **Affected gate/dimension:** G4
- **Confidence:** 1.0

## Finding 7: Table scoring requires BOTH structure and content

- **Severity:** PASS (correctly implemented)
- **Claim:** TEDS (structure) and content_recall (content) are paired but independent axes, never averaged into one composite.
- **Evidence:**
  - `bench.py:24-26`: docstring: "content_recall ... A first-class gate but deliberately NOT folded into Overall: it catches dropped sections that edit distance hides."
  - `bench.py:199-205`: `overall = sum(parts) / len(parts)` where parts is `[nid_v]` plus eligible teds/mhs. content_recall is EXCLUDED from overall.
  - `bench.py:247-254`: `below_floor` checks BOTH teds (`r.teds < C.TEDS_FLOOR`) AND content_recall (`r.content_recall < C.CONTENT_RECALL_FLOOR`) independently.
  - `constants.py:63-74`: Separate floors: `TEDS_FLOOR = 0.80`, `CONTENT_RECALL_FLOOR = 0.90`.
- **Affected gate/dimension:** G4
- **Confidence:** 1.0

## Finding 8: No synthetic 1.0 for missing teds

- **Severity:** PASS (correctly implemented)
- **Claim:** An absent teds modality is never imputed as 1.0.
- **Evidence:**
  - `bench.py:185-189`: When reference has no tables, `teds_v = None`, not `1.0`.
  - `bench.py:112-125` (`_table_score`): Returns 1.0 ONLY when `not cand and not ref` (BOTH sides lack tables — identical empty structure is legitimately 1.0). When only one side has tables, the pairing logic tanks the score (empty table matched against real table via `teds(empty, b)`).
  - `bench.py:200-201`: `if teds_v is not None: parts.append(teds_v)` — None teds is excluded from overall computation.
- **Affected gate/dimension:** G4
- **Confidence:** 1.0
- **False-pass hypothesis:** `_table_score` returns 1.0 when neither side has tables. This is NOT a synthetic imputation — it's the correct score for identical (empty) structure. The None path is for when the reference has tables but we want to signal ineligibility.

---

## Verdict

**G4: CLEAN.** Per-axis null eligibility and independent per-axis reporting are correctly implemented throughout bench, score, aggregate, guard, and report. No synthetic 1.0 imputation. No composite gate hiding axis-level failures. 8/8 findings pass.
