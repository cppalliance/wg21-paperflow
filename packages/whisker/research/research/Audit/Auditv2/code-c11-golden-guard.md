# C11 Golden and Guard

**Role:** Audit Lane 1 stability and Lane 2 guard mechanisms.
**Audited state:** whisker 0.5.0, HEAD 51cb704, Python 3.12.10, pytest 8.4.2.
**Date:** 2026-07-20

## 1. Scope

Audit the golden comparison system (Lane 1) and the per-paper regression guard
(Lane 2). Check: membership rules, missing candidate handling, update safety
(symlink rejection), regression detection, expected failures, tool-version
pinning, and floor enforcement.

## 2. Commands and Exits

| Evidence | Command / source | Exit |
|----------|-----------------|------|
| E1 | Full test suite 1406p/8s/3x | 0 |
| E3 | Golden/guard/fusion/incremental/gates 284p | 0 |

## 3. Current Evidence

### 3.1 Golden (Lane 1) - `golden.py`

**Normalizer** (`normalize_for_exact_lane`, line 79-90):
- Collapses `\r\n` and `\r` to `\n`
- Strips trailing whitespace per line
- Enforces single trailing newline at EOF
- Empty/whitespace-only input returns `""`

**Evaluation** (`_evaluate`, lines 155-179):
- Missing candidate -> `STATUS_MISSING` (hard fail)
- Missing expected -> `STATUS_NEW` (passes by default; `fail_on_new` overrides)
- Normalized match -> `STATUS_OK` or `STATUS_XFAIL_OK` (for expected failures)
- Normalized mismatch -> `STATUS_CHANGED` with unified diff

**Report** (`diff_goldens`, lines 182-192):
- Items sorted by pid before evaluation (deterministic order)
- `GoldenReport.failed` checks both `_FAILING_STATUSES` and `fail_on_new`
- Findings sorted by pid in `to_dict()`

**Membership rules** (from test_golden.py and __main__.py):
- Union of existing `<pid>.expected.md` snapshots and optional `<pid>.gt.md`
  markers
- Case-insensitive pid matching
- Expected-only members compare normally; GT-only members remain `new`

### 3.2 Golden test coverage (27 tests in test_golden.py)

| Test | What it verifies |
|------|-----------------|
| `test_normalize_collapses_crlf_and_trailing_ws` | Platform line-ending normalization |
| `test_normalize_single_trailing_newline` | EOF handling |
| `test_normalize_empty_is_empty` | Empty input edge case |
| `test_identical_after_normalization_is_ok` | CRLF/LF + trailing space -> ok |
| `test_text_change_is_changed` | Content change detected with unified diff |
| `test_missing_candidate_is_missing` | Vanished paper -> hard fail |
| `test_new_paper_is_new` | No snapshot -> new (not fail by default) |
| `test_fail_on_new_makes_new_fail` | --fail-on-new flag |
| `test_expected_failure_unchanged_is_xfail_ok` | Known-imperfect golden, unchanged |
| `test_expected_failure_changed_is_changed` | Known-imperfect golden, changed -> fail |
| `test_report_to_dict_sorted_by_pid` | Deterministic output order |
| `test_load_rejects_symlinks` | Symlink safety |
| `test_golden_member_union_expected_and_gt` | Membership union rule |
| `test_golden_case_insensitive_dedup` | Case-insensitive pid matching |
| `test_golden_main_*` (multiple) | CLI integration |

### 3.3 Guard (Lane 2) - `guard.py`

**Baseline construction** (`baseline_from_rows`, lines 227-248):
- Embeds `schema_version`, `kind`, `tool_versions`, `axis_slack`, `floors`
- Contract travels with the data (self-describing baseline)
- Rows indexed by pid, axes rounded to `_NDIGITS = 4`
- Rejects duplicate pids

**Baseline validation** (`_validate_baseline`, lines 251-304):
- Checks `kind == GUARD_BASELINE_KIND`
- Checks `schema_version == WHISKER_SCHEMA_VERSION`
- Checks `tool_versions` match current installed versions
- Rejects non-finite values (NaN/inf)

**Paper evaluation** (`_evaluate_paper`, lines 330-393):
- Non-finite metric detection: NaN/inf -> `STATUS_INVALID` (hard fail)
- Symmetric rounding to `_NDIGITS` before comparison
- Floor breach detection (below published floor)
- Regression detection: `drop > slack` -> `STATUS_REGRESSED`
- Floor crossing: sub-slack drop across a floor -> `STATUS_CROSSED_FLOOR`
- New paper: below floor -> `STATUS_NEW_BELOW_FLOOR`; above -> `STATUS_NEW`
- Ineligible axes (None) skipped for all checks

**Missing paper detection** (`diff_rows`, lines 432-433):
- Papers in baseline but absent from current run -> `missing` list
- Any missing paper causes `GuardReport.failed = True`

**Tool-version pinning** (lines 69-90):
- `_TOOL_VERSION_PACKAGES = ("tomd", "whisker")`
- Current versions collected via `importlib.metadata.version`
- Mismatch hard-fails before any per-paper diff

### 3.4 Guard test coverage (31 tests in test_guard.py)

| Test | What it verifies |
|------|-----------------|
| `test_baseline_roundtrip_is_clean` | Build + diff -> all ok |
| `test_axis_regression_beyond_slack_fails` | Regression detection |
| `test_drop_within_slack_passes` | Slack tolerance |
| `test_slack_boundary_exact_is_not_a_regression` | Exact boundary |
| `test_crossed_floor_sub_slack_still_fails` | Floor crossing |
| `test_new_paper_below_floor_fails` | New paper entry bar |
| `test_new_paper_above_floor_passes` | New paper accepted |
| `test_fail_on_new_flag` | Explicit acknowledgment |
| `test_missing_paper_fails` | Vanished paper |
| `test_nan_metric_is_invalid` | NaN detection |
| `test_inf_metric_is_invalid` | Inf detection |
| `test_non_finite_stored_metric_fails_validation` | Corrupt baseline |
| `test_baseline_schema_version_mismatch_fails` | Schema evolution |
| `test_baseline_kind_mismatch_fails` | Wrong file detection |
| `test_tool_version_mismatch_fails` | Dependency bump |
| `test_ineligible_axes_are_not_invalid` | None != NaN |
| `test_ineligible_axis_skips_floor` | None skips floor |
| `test_ineligible_axis_skips_regression` | None skips regression |
| `test_duplicate_pid_rejected` | Data integrity |
| `test_reading_order_not_gated` | Advisory axis |
| `test_grits_con_not_gated` | Advisory axis |

### 3.5 Score pinning meta-test

`test_score_pinning.py::test_no_unannotated_false_gates` (lines 153-200):
papers with false gates must appear in `_EXPECTED_GATE_FAILURES`. An
unannotated false gate in the baseline fails, forcing explicit acknowledgment.
Currently annotated: `p0533r9` (no_toc_leak), `p1122r3` (no_toc_leak),
`p3968r0` (no_toc_leak).

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | Golden normalizer handles CRLF, trailing whitespace, and EOF correctly | PASS | HIGH |
| F2 | Missing candidate, changed content, and expected failures all produce correct statuses | PASS | HIGH |
| F3 | Symlink rejection prevents malicious corpus entries | PASS | HIGH |
| F4 | Guard regression detection is correct across slack, floor-crossing, and boundary cases | PASS | HIGH |
| F5 | Tool-version pinning prevents stale-baseline comparisons | PASS | HIGH |
| F6 | NaN/inf detection hard-fails before any comparison | PASS | HIGH |
| F7 | Null-eligibility (None axes) correctly skipped for floor and regression | PASS | HIGH |
| F8 | Missing paper from baseline is a hard fail | PASS | HIGH |
| F9 | Score pinning meta-test blocks unannotated false gates | PASS | HIGH |
| F10 | Advisory axes (reading_order, grits_con) are never gated in the guard | PASS | HIGH |
| F11 | `_NDIGITS = 4` symmetric rounding prevents IEEE-754 boundary artifacts | PASS | MEDIUM |

## 5. False-Pass Hypothesis and Falsification

**Hypothesis:** The guard could pass a regression if the baseline's
`axis_slack` is so large that no real regression exceeds it.

**Falsification:** The slack is embedded in the baseline and validated:
`_validate_baseline` (line 290) checks `slack >= 0` and `_finite(slack)`.
The default slack `GUARD_AXIS_SLACK = 0.02` matches OpenDataloader-pdf's
per-axis tolerance. The test `test_axis_regression_beyond_slack_fails` uses
a 0.09 drop against 0.02 slack, confirming the gate trips. The
`test_crossed_floor_sub_slack_still_fails` test proves that even within-slack
drops that cross a floor are caught.

## 6. Gate/Dimension Mapping

| Gate | Dimension | Status |
|------|-----------|--------|
| D2: Reproducible scoring pipeline | Lane 1 stability | PASS |
| D4: Scoring accuracy | Lane 2 regression guard | PASS |

## 7. Limitations

- The golden lane requires a committed snapshot per paper. Papers without
  snapshots are `new` and only fail under `--fail-on-new`. There is no
  automatic snapshot creation.
- The guard baseline must be manually regenerated (`--update`) after a
  tomd/whisker version bump. This is by design (explicit acknowledgment) but
  means a forgotten update blocks the guard entirely (hard fail on version
  mismatch).
- The `NORMALIZATION_VERSION = 1` in golden.py is not automatically checked
  against the baseline; a normalizer change requires a manual re-bless.

## 8. Conclusion

Lane 1 (golden) and Lane 2 (guard) are well-constructed and thoroughly tested.
The golden lane handles platform differences, expected failures, and membership
union correctly. The guard catches regressions, floor crossings, stale
baselines, corrupt values, missing papers, and tool-version mismatches. Both
systems enforce explicit human acknowledgment for changes, matching the
field consensus from 17/28 surveyed repos.
