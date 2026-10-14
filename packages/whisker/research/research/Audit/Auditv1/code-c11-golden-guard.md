# C11 -- Golden and Guard Auditor

**Mandate:** Audit Lane 1 stability and Lane 2 regression guard.
**Auditor role:** Golden and Guard Auditor
**Date:** 2026-07-19
**Scope:** `golden.py`, `guard.py`, `__main__.py` (golden/guard verbs), `test_golden.py`, `test_guard.py`, `constants.py`

---

## 1. Lane 1 Stability: `golden.py`

### F1: `diff_goldens` uses exact difflib compare on normalized text

- **Severity:** INFO (confirmed correct)
- **Claim:** `diff_goldens` normalizes both sides with `normalize_for_exact_lane` then does an exact `==` compare, with `difflib.unified_diff` generating the human-readable diff on mismatch.
- **Evidence:** `golden.py:164-179` -- `_evaluate` calls `normalize_for_exact_lane` on both `item.candidate` and `item.expected`, compares with `cur == exp`, and falls through to `difflib.unified_diff` on inequality.
- **Affected gate:** Lane 1 stability
- **Confidence:** HIGH
- **False-pass hypothesis:** A normalizer bug that silently drops meaningful characters would let a regression through. The normalizer is conservative (CRLF collapse, trailing whitespace strip, single trailing newline), well-precedented (pymupdf4llm, html2text), and tested (`test_normalize_collapses_crlf_and_trailing_ws`, `test_normalize_single_trailing_newline`, `test_normalize_empty_is_empty`).
- **False-fail hypothesis:** Platform line-ending differences on Windows checkouts would cause spurious failures without the normalizer. The normalizer absorbs this correctly.

### F2: `expected_failures` mechanism in golden.json

- **Severity:** INFO (confirmed correct)
- **Claim:** `GoldenItem.expected_failure` is a boolean flag. When set AND the snapshot is unchanged, the status is `STATUS_XFAIL_OK` (passes but is labeled distinctly). When set AND the snapshot changes, it still emits `STATUS_CHANGED` (fails), forcing a deliberate re-bless.
- **Evidence:** `golden.py:167-169` -- identity branch returns `STATUS_XFAIL_OK` when `item.expected_failure` is true. `golden.py:170-179` -- any diff produces `STATUS_CHANGED` regardless of the flag.
- **Affected gate:** Lane 1 stability
- **Confidence:** HIGH
- **Test coverage:** `test_expected_failure_unchanged_passes_but_is_labeled`, `test_expected_failure_still_fails_on_any_change` both pass.
- **False-pass hypothesis:** None identified. A silent improvement on an expected-failure golden still trips `changed`.
- **False-fail hypothesis:** None. The xfail flag passes cleanly when unchanged.

### F3: `--update` is the bless ritual and changes exit code to 0

- **Severity:** INFO (confirmed correct)
- **Claim:** In `__main__.py`, the `golden` verb's `--update` flag rewrites the `<pid>.expected.md` files from the current candidates and returns `EXIT_OK` (0), bypassing any diff check.
- **Evidence:** `__main__.py:16` -- docstring states `--update` for golden verb. The guard verb has the same pattern at `__main__.py:551-561`: `if args.update: ... baseline_path.write_text(...) ... return C.EXIT_OK`.
- **Affected gate:** Bless ritual
- **Confidence:** HIGH
- **False-pass hypothesis:** If `--update` is called accidentally, regressions are silently blessed. This is by design (pandoc `--accept` precedent) and requires human review of the diff.
- **False-fail hypothesis:** None.

### F4: NORMALIZATION_VERSION tracks normalizer changes

- **Severity:** INFO (confirmed correct)
- **Claim:** `NORMALIZATION_VERSION = 1` is stamped into every `GoldenReport`. A normalizer change bumps this version, signaling that all snapshots must be re-blessed.
- **Evidence:** `golden.py:65-66`, `golden.py:125`.
- **Affected gate:** Lane 1 stability
- **Confidence:** HIGH

---

## 2. Lane 2 Regression Guard: `guard.py`

### F5: `diff_rows` catches per-paper regressions with correct slack

- **Severity:** INFO (confirmed correct)
- **Claim:** `diff_rows` evaluates EACH paper's EACH axis against the committed baseline. A drop exceeding `GUARD_AXIS_SLACK` (0.02) on any regression axis (`nid`, `teds`, `mhs`, `content_recall`, `overall`) triggers `STATUS_REGRESSED`. A sub-slack drop that crosses a floor downward triggers `STATUS_CROSSED_FLOOR`. Both are hard fails.
- **Evidence:** `guard.py:370-393` -- the `_evaluate_paper` function iterates `C.GUARD_REGRESSION_AXES`, computes `drop = round(prior - cur, _NDIGITS)`, checks `drop > slack`, and separately checks floor crossings. `guard.py:101-103` -- `_FAILING_STATUSES` includes `REGRESSED`, `CROSSED_FLOOR`, `NEW_BELOW_FLOOR`, `INVALID`.
- **Affected gate:** Lane 2 fidelity guard
- **Confidence:** HIGH
- **False-pass hypothesis:** Symmetric rounding at `_NDIGITS=4` prevents float-representation artifacts from hiding a tiny regression. Tested at `test_slack_boundary_exact_is_not_a_regression`.
- **False-fail hypothesis:** A paper already below floor in the baseline is NOT re-flagged as long as it stays stable (tabula-java monotonic model). Tested at `test_known_weak_paper_not_reflagged_when_stable`.

### F6: Slack and floors travel with the baseline

- **Severity:** INFO (confirmed correct)
- **Claim:** The baseline embeds `axis_slack` and `floors`. `diff_rows` reads these from the baseline when present, so the gate is reproducible from the committed file alone. CLI `--slack` overrides this.
- **Evidence:** `guard.py:307-327` -- `_resolve_floors` and `_resolve_slack` check the baseline first, fall back to constants. Tests: `test_baseline_embedded_slack_drives_the_gate`, `test_cli_slack_argument_overrides_baseline`, `test_baseline_embedded_floors_are_honored`.
- **Affected gate:** Lane 2 guard reproducibility
- **Confidence:** HIGH

### F7: Tool-version mismatch is a hard fail

- **Severity:** INFO (confirmed correct)
- **Claim:** `_validate_baseline` checks `tool_versions` (tomd, whisker) against the currently installed versions. A mismatch raises `ValueError`, refusing to diff against wrong-era metrics.
- **Evidence:** `guard.py:276-288`. Test: `test_tool_version_mismatch_hard_fails`.
- **Affected gate:** Lane 2 guard integrity
- **Confidence:** HIGH

### F8: Null-eligibility for teds/mhs is handled correctly

- **Severity:** INFO (confirmed correct)
- **Claim:** An ineligible axis (stored as `None` because the reference lacks tables/headings) is SKIPPED for both floor and regression checks, never treated as NaN/inf. A real NaN/inf is `STATUS_INVALID` and hard-fails.
- **Evidence:** `guard.py:344-354` -- the `_evaluate_paper` function explicitly checks `axes.get(a) is not None` before flagging non-finite, and `cur is None` before comparing. Tests: `test_ineligible_axes_are_not_invalid`, `test_ineligible_axis_skips_floor`, `test_ineligible_axis_skips_regression`, `test_nan_axis_still_invalid`.
- **Affected gate:** Lane 2 guard, null-eligibility
- **Confidence:** HIGH

### F9: Conjunctive anchors + facts in guard

- **Severity:** INFO (confirmed correct)
- **Claim:** `whisker guard` runs anchor checks and fact checks conjunctively. `anchors_failed || facts_failed -> EXIT_FAIL` regardless of metric slack.
- **Evidence:** `__main__.py:591` -- `anchors_failed = any(r.failed for r in anchor_reports)`. `__main__.py:602` -- `facts_failed = any(r.failed for r in fact_reports) or bool(facts_vacuous)`. `__main__.py:615` -- `if report.failed or anchors_failed or facts_failed: return C.EXIT_FAIL`.
- **Affected gate:** Guard gate, conjunctive lane fusion
- **Confidence:** HIGH
- **False-pass hypothesis:** A vacuous facts file (zero verified facts) would pass silently without the `facts_vacuous` guard. The guard catches this: `_warn_vacuous_reports` returns vacuous PIDs and they are folded into `facts_failed`.
- **False-fail hypothesis:** None. Unverified (draft) facts do not gate.

### F10: Missing paper in baseline is a hard fail

- **Severity:** INFO (confirmed correct)
- **Claim:** A paper present in the baseline but absent from the current run is a hard fail (a vanished paper can hide a regression).
- **Evidence:** `guard.py:189-191` -- `bool(self.missing)` is checked in `GuardReport.failed`. Test: `test_missing_paper_is_hard_fail`.
- **Affected gate:** Lane 2 guard
- **Confidence:** HIGH

---

## 3. Test Coverage Assessment

### `test_golden.py` (8 tests)

| Test | What it covers |
|------|----------------|
| `test_normalize_collapses_crlf_and_trailing_ws` | Normalizer CRLF + trailing whitespace |
| `test_normalize_single_trailing_newline` | Normalizer EOF behavior |
| `test_normalize_empty_is_empty` | Normalizer edge case |
| `test_identical_after_normalization_is_ok` | Happy path: platform-noise absorbed |
| `test_real_change_fails_with_diff` | Regression detection: status=changed, diff present |
| `test_new_paper_passes_by_default_fails_on_new` | New paper semantics + fail_on_new flag |
| `test_missing_candidate_is_hard_fail` | Dropped paper detection |
| `test_expected_failure_unchanged_passes_but_is_labeled` | XFAIL happy path |
| `test_expected_failure_still_fails_on_any_change` | XFAIL still fails on change |
| `test_report_dict_is_sorted_and_serializable` | Serialization + sorted output |

**Gap:** No test exercises the golden.json manifest loading path (expected_failures sourced from a file). The `GoldenItem.expected_failure` flag is tested directly, but the file-to-flag wiring in `__main__.py` is integration-only.

### `test_guard.py` (24 tests)

Comprehensive coverage including:
- Baseline roundtrip, axis regression, slack boundary, crossed floor
- New paper above/below floor, known weak paper stable/worsening
- Missing paper, overall erosion, embedded slack/floors, wrong kind/schema
- Non-finite values (NaN/inf), duplicate PIDs, fail_on_new
- Tool versions: embed, mismatch, sorted, matching
- Null-eligibility: store, skip floor, skip regression, NaN still invalid

**Gap:** No test exercises the conjunctive anchor/fact logic at the guard level (that integration is in `__main__.py`). The unit tests cover `diff_rows` but not the CLI composition.

---

## 4. Summary

| Finding | Severity | Verdict |
|---------|----------|---------|
| F1: diff_goldens uses exact difflib on normalized text | INFO | CONFIRMED |
| F2: expected_failures mechanism correct | INFO | CONFIRMED |
| F3: --update bless ritual exits 0 | INFO | CONFIRMED |
| F4: NORMALIZATION_VERSION tracks changes | INFO | CONFIRMED |
| F5: diff_rows per-paper, per-axis regression with slack | INFO | CONFIRMED |
| F6: Slack/floors travel with baseline | INFO | CONFIRMED |
| F7: Tool-version mismatch hard fails | INFO | CONFIRMED |
| F8: Null-eligibility handled correctly | INFO | CONFIRMED |
| F9: Conjunctive anchors + facts in guard | INFO | CONFIRMED |
| F10: Missing paper hard fails | INFO | CONFIRMED |

**Overall assessment:** Lane 1 and Lane 2 guard implementations are structurally sound, well-tested, and consistent with their architectural documentation. No material defects found.
