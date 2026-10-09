# C05 Quality-Stability Replay

**Role:** Assess deterministic replay evidence for quality stability.
**Audited state:** whisker 0.5.0, HEAD 51cb704, Python 3.12.10, pytest 8.4.2.
**Date:** 2026-07-20

## 1. Scope

Evaluate the test suite's ability to detect score regressions through
deterministic replay: score pinning, deterministic metric assertions, and
fusion stability. Identify gaps where separate-process workspace replay is
not exercised due to missing `WG21_DATA_DIR`.

## 2. Commands and Exits

| Evidence | Command / source | Exit |
|----------|-----------------|------|
| E1 | Full test suite 1406p/8s/3x | 0 |
| E3 | Golden/guard/fusion/incremental/gates 284p | 0 |
| E4 | Core metric/scoring 218p | 0 |
| E10 | Deterministic replay via test assertions | 0 |

## 3. Current Evidence

### 3.1 Score pinning (19 papers)

`test_score_pinning.py` pins gate results and QA metrics for 19 tomd golden
fixture papers against a committed baseline (`fixtures/score-baseline.json`).
Pinned fields per paper: `gates` (each gate name + pass/fail + detail),
`qa_score`, `uncertain_count`, `mojibake_count`, `table_parse_errors`.

The baseline update mechanism has a CI safety guard (lines 133-138):
```python
if os.environ.get("WHISKER_PIN_UPDATE") == "1":
    if os.environ.get("CI"):
        pytest.fail("WHISKER_PIN_UPDATE=1 is forbidden in CI.")
```

A meta-test (`test_no_unannotated_false_gates`, line 187+) ensures that any
gate `passed: false` in the baseline must appear in the `_EXPECTED_GATE_FAILURES`
allowlist, preventing silent gate additions.

Paper stems covered: `p0533r9`, `p0957r8`, `p1068r11`, `p3556r0`, `p1122r3`,
`p2040r0`, `p3181r1-annex`, `p3100r6`, `p2845r8`, `p0447r28-annex-a`,
`p3412r0`, `p3554r0`, `p3968r0`, `p4012r0-codeblock`, `p4012r0-page-10`,
`p4016r0`, `p4020r0`, `p0447r28`, `p3181r1` (19 total).

### 3.2 Metric determinism assertions

- `test_metrics.py::test_metrics_are_deterministic`: repeated `teds` and `mhs`
  calls on identical inputs produce identical outputs.
- `test_match.py::test_match_blocks_is_deterministic`: repeated `match_blocks`
  calls produce identical `(gt_index, pred_indices)` tuples.
- `test_fusion.py::TestFusionDeterminism::test_same_input_same_dict`: repeated
  `fuse_verdicts` calls produce byte-identical JSON.
- `test_fusion.py::TestFusionDeterminism::test_fingerprint_stable`: whisker
  fingerprint is a stable 16-char hex string across calls.

### 3.3 Guard regression detection

`test_guard.py` (31 tests) exercises the per-paper, per-axis regression guard:
- `test_axis_regression_beyond_slack_fails`: a teds drop 0.99->0.90 trips the
  guard.
- `test_drop_within_slack_passes`: a 0.01 drop within 0.02 slack passes.
- `test_slack_boundary_exact_is_not_a_regression`: exact slack boundary passes.
- `test_crossed_floor_sub_slack_still_fails`: a sub-slack drop that crosses a
  published floor still fails.
- `test_tool_version_mismatch_fails`: mismatched tomd/whisker version in baseline
  hard-fails before any per-paper diff.
- `test_baseline_schema_version_mismatch_fails`: stale schema version hard-fails.

### 3.4 Golden stability (Lane 1)

`test_golden.py` (27 tests) exercises exact-lane golden comparison:
- Normalizer tests (CRLF collapse, trailing whitespace, single trailing newline).
- `diff_goldens` tests: identical-after-normalize is ok, text changes produce
  `changed` status with unified diff, missing candidate is `missing`, new paper
  is `new`, expected failures are tracked as `expected_failure`.
- Symlink rejection test: `test_load_rejects_symlinks`.

### 3.5 Comprehension corpus replay

`test_comprehension_corpus.py` replays all 5 corpus papers' verified facts
against committed `expected.md` snapshots with no backend. Three canary tests
prove gate sensitivity: scrambled table cell (P4182R0), mangled code (P4234R0),
flipped math relation (P4185R0).

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | Score pinning covers 19 papers with a CI-locked update mechanism | PASS | HIGH |
| F2 | Meta-test blocks unannotated false gates in the baseline | PASS | HIGH |
| F3 | Metric, match, and fusion determinism are explicitly tested | PASS | HIGH |
| F4 | Guard regression detection covers slack, floor-crossing, tool-version, and schema checks | PASS | HIGH |
| F5 | Golden stability and comprehension corpus replay are hermetic (no backend) | PASS | HIGH |
| F6 | **Gap: No separate-process workspace replay.** Without `WG21_DATA_DIR`, the full `whisker <pid>` pipeline (source extraction, content check, reference oracle) is not exercised in CI. Score pinning covers gates+QA on committed goldens; the content check and oracle paths are not replayed. | MEDIUM | HIGH |
| F7 | **Gap: Score pinning does not cover `ref_nid`, `ref_teds`, `ref_mhs`.** These require a reference oracle (markitdown) run, which needs a staged source file, not just a golden markdown. | MEDIUM | HIGH |
| F8 | The 19 pinned papers are tomd golden fixtures (dev set). The 5 corpus papers are separately tested for comprehension but not score-pinned for gates/QA. | INFO | HIGH |

## 5. False-Pass Hypothesis and Falsification

**Hypothesis:** Score pinning could pass despite a regression if the baseline
file drifts silently (e.g., a developer runs `WHISKER_PIN_UPDATE=1` without
reviewing the diff).

**Falsification:** The CI guard (`os.environ.get("CI")` check at line 134)
prevents baseline updates in CI. The meta-test
`test_no_unannotated_false_gates` catches undocumented gate failures. The
committed baseline is a JSON file tracked in git, so any change produces a
visible diff in pull requests.

## 6. Gate/Dimension Mapping

| Gate | Dimension | Status |
|------|-----------|--------|
| G3: Scoring determinism | D2: Reproducible scoring pipeline | PASS (within-process) |

## 7. Limitations

- Separate-process replay (running `whisker <pid>` in a fresh process on the
  workspace) is blocked by the absence of `WG21_DATA_DIR` in CI. This means the
  end-to-end pipeline including source extraction, content check, and reference
  oracle is not replayed. The gap is documented, not a defect: CI exercises the
  deterministic core through its test harness.
- The reference oracle (markitdown) path is tested in `test_golden_ideals.py`
  for ideal discovery but not for its effect on the final verdict.

## 8. Conclusion

The test suite provides strong quality-stability evidence through 19-paper
score pinning, explicit determinism tests, guard regression detection, golden
stability, and comprehension corpus replay. Two gaps exist: (1) no
separate-process workspace replay due to blocked `WG21_DATA_DIR`, and (2)
no score pinning of the reference oracle axes (ref_nid/teds/mhs). Both are
inherent to the CI-hermetic design (no staged source files) rather than
architectural oversights. The deterministic core is well-covered.
