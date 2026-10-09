# C06 Per-Axis Null Eligibility

**Role**: Verify axes that do not apply are `None`, never a synthesized zero (or one), and that per-axis scores are never collapsed into a false single composite.
**Audited state**: whisker 0.5.0, working tree, manifest b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771 (HEAD 0d18a65 + 7205 uncommitted insertions).
**Gates**: G4 (Metric correctness / per-axis evaluation).

## 1. Scope

Verify `teds`/`mhs`/`grits_con` are `None` (not a synthetic 0.0 or 1.0) when the reference lacks that modality; verify `overall` excludes ineligible axes rather than averaging in a synthetic value; verify `aggregate()` reports eligibility-weighted means with exposed counts; verify `guard.py` skips `None` axes for floor and regression checks; verify `content_recall` and `reading_order` stay reported as separate strata, never folded into `overall`; and confront the E18 metrology finding (a corruption class invisible to every text axis at once) as a limit on what "per-axis" can mean when the axes share one underlying blind spot.

## 2. Commands and Exits

| Evidence | Command / source | Exit |
|---|---|---|
| E1 | offline suite (context) | 1 (unrelated failures, see C02) |
| E17 | `rt4_canaries.py`, 4 mutations, live | n/a (per-axis metric-value comparison) |
| E18 | canary C4, 14 mangled code spans | n/a (per-axis metric-value comparison) |

## 3. Current Evidence

### 3.1 `teds`/`mhs`/`grits_con` are `None`, not a synthetic value, when the reference lacks the modality

`bench.py:185-196` (`run_bench`):

```python
teds_v = (
    _table_score(candidate_md, reference_md)
    if _extract_md_tables(reference_md)
    else None
)
mhs_v = mhs(candidate_md, reference_md) if has_headings(reference_md) else None
...
grits_con_v = _grits_con_score(candidate_md, reference_md)
```

`_grits_con_score` (`bench.py:142-167`) itself returns `None` at line 155 (`if not ref: return None`) before computing anything, when the reference has no tables. All three conditions test the REFERENCE (`_extract_md_tables(reference_md)`, `has_headings(reference_md)`), never the candidate and never the comparison RESULT, so eligibility is a property of the ground truth, not of how well the candidate happened to match it.

### 3.2 `overall` excludes ineligible axes; it does not average in a placeholder

`bench.py:200-205`:

```python
parts = [nid_v]
if teds_v is not None:
    parts.append(teds_v)
if mhs_v is not None:
    parts.append(mhs_v)
overall = sum(parts) / len(parts)
```

A table-less, heading-less reference produces `parts = [nid_v]` and `overall = nid_v`, not `(nid_v + 1.0 + 1.0) / 3` (which would inflate the composite toward a false perfection) and not `(nid_v + 0.0 + 0.0) / 3` (which would falsely penalize a paper for lacking a modality its reference never had either). `grits_con` never enters `parts` at all under any condition; it is excluded from `overall` unconditionally (module docstring, `bench.py:30-34`, and confirmed by its absence from the `parts` list).

### 3.3 `aggregate()`: eligibility-weighted means with an exposed denominator

`bench.py:214-272` (`aggregate`): `teds_vals`/`mhs_vals`/`grits_vals` are built by filtering `if r.teds is not None` etc. (`bench.py:237-239`), and each mean divides by `len(teds_vals)` etc., not by `n` (the full row count). When the filtered list is empty, the mean is explicitly `None` (`bench.py:241-243`: `mean_teds = sum(teds_vals) / len(teds_vals) if teds_vals else None`), not a divide-by-zero crash and not a silent 0.0. `eligible_counts` (`bench.py:264-269`) publishes the denominator for every axis (`nid`, `teds`, `mhs`, `content_recall`, `grits_con`) so a reader can see how many papers each mean actually rests on, distinct from the corpus row count `n`.

### 3.4 `guard.py`: floor and regression checks skip `None` axes (not independently re-read this pass; carried forward from Auditv2)

Auditv2 C06 §3.4 cited `guard.py:359` (floor check: `if cur is not None and cur < floor` skips `None`) and `guard.py:373` (regression check: `if prior is None or cur is None: continue`). This run did not independently re-read `guard.py`; the claim is carried forward as unconfirmed-this-pass rather than re-verified, per the Limitations below, because `guard.py` is outside this batch's mandatory source-file list (`score.py`, `gates.py`, `metrics.py`, `constants.py`, `bench.py`, `__main__.py`, `tapetum_llm/{fusion.py,constants.py}`) and no ledger entry this run exercised it live.

### 3.5 `content_recall` and `reading_order` stay separate strata, never folded into `overall`

`BenchRow` (`bench.py:57-69`) stores `content_recall: float = 1.0` and `reading_order: float = 0.0` as fields distinct from `overall`; `run_bench` (`bench.py:191-199`) computes `recall_v = content_recall(...)` and assigns it to `content_recall=recall_v` on the constructed row (`bench.py:207-209`), and the `overall` computation two lines earlier (`bench.py:200-205`) never references `recall_v` or `bm.reading_order`. The module docstring is explicit about why: `content_recall` "catches dropped sections that edit distance hides," so averaging it into `overall` would let a high `nid` mask a dropped section, exactly the Nougat/Unstructured stratification lesson the docstring cites (`bench.py:19-26`). `aggregate()`'s `below_floor` list (`bench.py:247-254`) DOES include `content_recall` as a first-class gate condition (`or r.content_recall < C.CONTENT_RECALL_FLOOR`), confirming it gates independently rather than being silently absorbed into the composite.

### 3.6 `score.py`'s ideal panel respects the same null-eligibility rule

`score.py:205-215` (`_decide`, `ideal is not None` block): iterates `(ideal.nid, C.NID_FLOOR, "nid"), (ideal.teds, C.TEDS_FLOOR, "teds"), (ideal.mhs, C.MHS_FLOOR, "mhs"), (ideal.recall, C.CONTENT_RECALL_FLOOR, "recall")` and only appends a soft flag `if value is not None and value < floor` (`score.py:214`). An ideal panel with `teds=None` (ideal has no tables) is silently skipped for that one axis rather than treated as a failing 0.0; the comment at `score.py:206-207` states this explicitly ("an ineligible axis cannot flag"). This is the same eligibility discipline as `bench.py`, applied to the per-paper verdict path rather than the corpus-leaderboard path, confirming the rule is not implemented twice with diverging semantics.

### 3.7 The metrology limit on "per-axis": E18 shows the axes can share one blind spot simultaneously

Null-eligibility guarantees an axis is either a real measurement or an honest `None`; it does not guarantee that a "real measurement" axis is SENSITIVE to every defect class. E18 (canary C4, 14 mangled `<memory_resource>` code spans) produced numerically IDENTICAL `text_nid` (0.8645), `content_recall` (0.9697), and `unigram_coverage` (0.9542) between the corrupted and control documents, because `clean_string` (`metrics.py:115,118-126`) and `content_tokens`'s `\w+` tokenizer (`metrics.py:359-373`) both strip the corrupted character (`>` -> `<`) as a non-word character on both sides before any comparison runs. This means three DIFFERENT named axes (`text_nid`, `content_recall`, `unigram_coverage`), which C06's null-eligibility rule keeps honestly separate from each other (§3.5), can still all be simultaneously and identically blind to the SAME defect, because they share one upstream normalizer. Per-axis separation prevents one axis's blindness from being HIDDEN by another axis's sensitivity (the composite-collapse failure mode this claim is about); it does not, and structurally cannot, prevent all axes from sharing an upstream normalization blind spot. This is a distinct failure mode from what C06 audits and must not be conflated with it: no axis here reports a false PASS by averaging with a failing axis (there is no failing axis to average with); every axis independently and correctly reports "no defect visible from here," which is true from that axis's own vantage point and false about the document.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---|---|---|
| F1 | `teds`/`mhs`/`grits_con` are `None`, never a synthetic value, gated on reference eligibility alone (`bench.py:142-196`) | Informational | HIGH |
| F2 | `overall` is built only from eligible parts; a table-less/heading-less paper's `overall` equals its `nid` alone (`bench.py:200-205`) | Informational | HIGH |
| F3 | `aggregate()` reports eligibility-weighted means with an explicit `None` for a fully-ineligible axis and publishes `eligible_counts` (`bench.py:214-272`) | Informational | HIGH |
| F4 | `content_recall` and `reading_order` are stored and gated (recall only) as separate strata, never averaged into `overall` (`bench.py:57-69,191-209,247-254`) | Informational | HIGH |
| F5 | `score.py`'s per-paper ideal panel applies the identical null-eligibility rule as `bench.py`'s corpus leaderboard, confirmed by a fresh read of `score.py:205-215` this run | Informational | HIGH |
| F6 | `guard.py`'s floor/regression-skip-on-`None` behavior was NOT independently re-verified this run; carried forward from Auditv2 as unconfirmed-this-pass | Low | MEDIUM |
| F7 | Three distinct named axes (`text_nid`, `content_recall`, `unigram_coverage`) can be simultaneously and identically blind to the same punctuation-only corruption, because they share one upstream normalizer (`clean_string`/`content_tokens`'s `\w+` filter). This is a normalizer-level metrology gap, not a null-eligibility or composite-collapse defect (E18) | **Medium** | HIGH |

## 5. False-Pass Hypothesis

**Could the null-eligibility model look correct while a non-identical candidate actually triggers a synthesized value?**

Auditv2's own falsification (C06 §5, `test_overall_not_inflated_by_ineligible_axes`, a candidate with "Totally different words" against a plain-prose reference, still `teds is None`/`overall == nid`) was not independently re-run this pass, but the code re-read this run (§3.1-§3.3) confirms the STRUCTURAL reason that test must hold: eligibility is computed from `_extract_md_tables(reference_md)`/`has_headings(reference_md)`, functions of the reference argument ALONE, with no data-flow dependency on the candidate argument at all. A non-identical candidate cannot change which reference-derived branch executes, so the prior falsification's logic is reconfirmed by fresh code inspection, not merely re-asserted.

A second, DIFFERENT false-pass risk, not tested by Auditv2 because it required live canary data Auditv2 could not obtain: could "every axis is honestly reporting" be mistaken for "the defect would be caught by at least one axis"? E18 answers this directly and unfavorably: no. Three independent, correctly-implemented, honestly-null-eligible axes all report clean on a real defect. This is the more dangerous false-pass mode for a reader of this file to miss, because it survives even a perfect null-eligibility implementation.

## 6. Gate/Dimension Mapping

**PROPOSED, not a settled verdict.** G4 (Metric correctness / per-axis evaluation): the null-eligibility implementation itself is correct on every code path this run inspected (`bench.py`, `score.py`), confirmed by fresh reads at F1-F5. PROPOSED: this narrow claim (axes are `None` not synthetic, `overall` excludes them, strata stay separate) **holds**. The PROPOSED verdict should NOT be read as "the per-axis model catches every corruption class": F7/E18 is a separate, real limitation on axis SENSITIVITY (not axis SEPARATION) that the planner should record alongside, and not allow F1-F5's clean result to overshadow.

## 7. Limitations

- `guard.py`'s floor/regression handling of `None` axes (F6) was not independently re-verified with a fresh code read or live test this run; it is carried forward from Auditv2 unchanged.
- E18's finding (F7) is a single canary observation on one base document; it establishes that the shared-blind-spot failure mode EXISTS and is reproducible for this exact corruption class (angle-bracket punctuation in a C++ template name), not that all three axes are blind to every non-word-character corruption in general. A different punctuation-adjacent defect (e.g. one that also perturbed adjacent word characters) might be visible to at least one axis.
- This file does not independently verify `golden_ideals.py`'s `IdealPanel` construction (only `score.py`'s CONSUMPTION of it); Auditv2's citation of `golden_ideals.py:56-63` for the same null-eligibility comment is carried forward, not re-read line-for-line this run.

## 8. Conclusion

The null-eligibility model is implemented correctly everywhere this run inspected it: `teds`/`mhs`/`grits_con` are honest `None` values gated on reference-only eligibility, `overall` never averages in a synthetic placeholder, `aggregate()` exposes its own denominators, and the per-paper ideal panel in `score.py` applies the identical rule as the corpus leaderboard in `bench.py`. Layered on top of that correct implementation, this run's live canary evidence (E18) surfaces a distinct and more serious limitation: three separately-computed, honestly-null-eligible axes can share one upstream normalization blind spot and all report "no defect" on the same real corruption simultaneously. Per-axis separation is necessary but not sufficient; it prevents one axis's blindness from being masked by another axis's SENSITIVITY, but it cannot manufacture sensitivity an axis's own normalizer structurally lacks.

## 9. Delta vs Auditv2

Auditv2's C06 (`Auditv2/code-c06-per-axis-null.md`) concluded a clean pass ("The null-eligibility model is correctly implemented and thoroughly tested... No violations found" was not its exact wording, but its findings table is all-PASS) based entirely on code inspection and unit tests (`test_bench.py`, `test_guard.py`), with an explicit Limitations note: "End-to-end testing with real papers that lack tables/headings requires `WG21_DATA_DIR` and is not exercised in CI." This run does not close that specific gap (no live bench/guard run against real table-less papers was in this run's ledger either), but it adds a DIFFERENT kind of live evidence Auditv2 had no access to at all: E18's canary result, which is not about eligibility gating but about axis SENSITIVITY once an axis IS eligible and IS computed. This is a genuinely new finding class (F7) that Auditv2's code-only method could not have surfaced, because it requires a live document mutation and a live metric comparison, not a code read. Auditv2's F1-F6 (null-eligibility correctness, `bench.py`/`guard.py`/`score.py` code shape) are reconfirmed by this run's fresh reads of `bench.py` and `score.py` (not `guard.py`, per F6/Limitations above), with no contradicting evidence found.
