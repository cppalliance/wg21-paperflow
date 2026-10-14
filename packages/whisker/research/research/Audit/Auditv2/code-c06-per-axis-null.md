# C06 Per-Axis and Null Eligibility

**Role:** Verify axis separation and null handling in bench/guard scoring.
**Audited state:** whisker 0.5.0, HEAD 51cb704, Python 3.12.10, pytest 8.4.2.
**Date:** 2026-07-20

## 1. Scope

Verify that TEDS/MHS/grits_con are `None` (not zero) when the reference lacks
the modality. Verify that the overall composite excludes ineligible axes.
Verify that `bench.py::aggregate` computes correctly with mixed eligibility.
Verify that `guard.py` skips ineligible axes for floor and regression checks.

## 2. Commands and Exits

| Evidence | Command / source | Exit |
|----------|-----------------|------|
| E1 | Full test suite 1406p/8s/3x | 0 |
| E3 | Golden/guard/fusion/incremental/gates 284p | 0 |
| E4 | Core metric/scoring 218p | 0 |

## 3. Current Evidence

### 3.1 GT-driven eligibility in `bench.py`

`run_bench` (bench.py lines 170-211) implements GT-driven eligibility:

```python
teds_v = (
    _table_score(candidate_md, reference_md)
    if _extract_md_tables(reference_md)
    else None
)
mhs_v = mhs(candidate_md, reference_md) if has_headings(reference_md) else None
```

When the reference has no tables, `teds_v` is `None` (not 0.0, not 1.0).
When the reference has no headings, `mhs_v` is `None`. The `has_headings`
function (metrics.py:671-679) checks via `_parse_headings` on the reference.

GriTS-Con eligibility follows the same rule (bench.py lines 153-155):
```python
ref = _extract_md_tables(reference_md)
if not ref:
    return None
```

### 3.2 Overall excludes ineligible axes

`run_bench` (bench.py lines 199-205) computes overall from only eligible parts:
```python
parts = [nid_v]
if teds_v is not None:
    parts.append(teds_v)
if mhs_v is not None:
    parts.append(mhs_v)
overall = sum(parts) / len(parts)
```

So a table-less, heading-less paper's overall equals its `nid` alone, not
`(nid + 1.0 + 1.0) / 3`.

### 3.3 Aggregate eligibility-weighted means

`aggregate` (bench.py lines 214-272) filters by eligibility before averaging:
```python
teds_vals = [r.teds for r in rows if r.teds is not None]
mhs_vals = [r.mhs for r in rows if r.mhs is not None]
mean_teds = sum(teds_vals) / len(teds_vals) if teds_vals else None
```

When no rows are eligible for an axis, the mean is `None`. Eligible counts
are exposed in the output dict under `eligible_counts`.

### 3.4 Guard skips ineligible axes

`guard.py::_evaluate_paper` (lines 330-393):
- Floor check (line 359): `if cur is not None and cur < floor` skips None axes.
- Regression check (line 373): `if prior is None or cur is None: continue`
  skips ineligible axes.
- Invalid check (line 346): `axes.get(a) is not None and not _finite(...)` only
  flags non-None non-finite values, never None.

### 3.5 Test evidence

**test_bench.py:**

- `test_no_table_no_heading_axes_are_none` (line 68): With a plain-prose
  reference (no tables, no headings), asserts `row.teds is None`,
  `row.mhs is None`, and the same in `to_dict()`.

- `test_overall_not_inflated_by_ineligible_axes` (line 77): With teds/mhs
  ineligible, asserts `row.overall == row.nid` (not pulled toward 1.0).

- `test_aggregate_eligible_counts_and_excluded_means` (line 87): With a mix
  of PLAIN (no tables/headings) and RICH (tables+headings) papers, asserts
  `eligible_counts["nid"] == 2`, `eligible_counts["teds"] == 1`,
  `eligible_counts["mhs"] == 1`, and that teds/mhs means average only the
  eligible paper (both 1.0 since RICH is self-identical).

- `test_aggregate_all_ineligible_axis_mean_is_none` (line 98): With only
  PLAIN papers, asserts `agg["teds"] is None` and `eligible_counts["teds"] == 0`.

- `test_grits_con_none_when_no_reference_table` (line 113): Asserts
  `grits_con is None` for a tableless reference.

- `test_grits_con_is_not_gated` (line 118): A grits_con difference must
  never appear in `below_floor`.

**test_guard.py:**

- `test_ineligible_axes_are_not_invalid` (line 275): A row with `teds=None`,
  `mhs=None` passes as `ok` against its own baseline (not treated as corrupt).

- `test_ineligible_axis_skips_floor` (line 283): An ineligible row with
  `nid=0.99` passes as `new` with no below_floor entries.

- `test_ineligible_axis_skips_regression` (line 290+): An ineligible axis
  changing eligibility across baseline/current does not trigger regression.

### 3.6 Score.py ideal panel null-eligibility

`score.py::_decide` (lines 206-215) respects null-eligibility for ideals:
```python
for value, floor, axis in (
    (ideal.nid, C.NID_FLOOR, "nid"),
    (ideal.teds, C.TEDS_FLOOR, "teds"),
    ...
):
    if value is not None and value < floor:
        soft.append(...)
```

An ideal panel with `teds=None` (no tables in the ideal) does not flag.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | TEDS/MHS/grits_con are None (not zero) when the reference lacks modality | PASS | HIGH |
| F2 | Overall composite includes only eligible axes | PASS | HIGH |
| F3 | Aggregate means are eligibility-weighted with exposed counts | PASS | HIGH |
| F4 | Guard skips None axes for both floor and regression checks | PASS | HIGH |
| F5 | Ideal panel respects null-eligibility (None axes do not flag) | PASS | HIGH |
| F6 | Advisory-only axes (reading_order, grits_con) are never gated | PASS | HIGH |

## 5. False-Pass Hypothesis and Falsification

**Hypothesis:** The tests could pass because they all use self-identical
inputs (candidate == reference), which always produces `None` for ineligible
axes, but a non-identical candidate might trigger a code path that synthesizes
a 0.0 instead of None.

**Falsification:** `test_overall_not_inflated_by_ineligible_axes` uses a
candidate with "Totally different words" against a plain-prose reference. The
candidate and reference are NOT identical, yet `teds is None` and `mhs is None`
still hold, and `overall == nid` (not zero). The eligibility check runs on the
REFERENCE (does it have tables/headings?), not on the comparison result, so it
is structurally impossible for a non-identical candidate to change eligibility.

## 6. Gate/Dimension Mapping

| Gate | Dimension | Status |
|------|-----------|--------|
| G4: Metric correctness | D4: Scoring accuracy | PASS |

## 7. Limitations

- Null-eligibility is tested at the unit level (per-row and per-aggregate).
  End-to-end testing with real papers that lack tables/headings requires
  `WG21_DATA_DIR` and is not exercised in CI.
- The `content_recall` axis is always eligible (text is always present). There
  is no null-eligibility path for it, which is correct (an empty reference
  yields 1.0 per `metrics.content_recall` line 389-390).

## 8. Conclusion

The null-eligibility model is correctly implemented and thoroughly tested.
Ineligible axes are `None` (not synthetic 1.0 or 0.0), overall excludes them,
aggregate averages are weighted by eligible counts, the guard skips them, and
advisory axes never gate. The opendataloader-pdf null-eligibility rule is
faithfully adopted.
