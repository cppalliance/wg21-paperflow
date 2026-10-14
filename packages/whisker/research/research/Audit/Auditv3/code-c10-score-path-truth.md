# C10 Score-Path Truth

**Role**: Trace what actually influences verdicts and exit codes, and check it against live runtime behavior, not just static code reading.
**Audited state**: whisker 0.5.0, working tree, manifest b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771
**Gates**: D1 (Determinism), D3 (Advisory non-leakage)

## 1. Scope

Confirm the documented hard-fail/soft-flag split in `score.py::_decide` is
both statically true and behaves identically under live, separate-process
execution. Confirm the exit-code contract holds under fault injection.
Confront the RED test suite (ledger E1) and determine whether its two
`test_score_pinning.py` failures implicate this path.

## 2. Commands and Exits

Deterministic runtime driver `rt1_deterministic.py`, real workspace, every
writing run redirected or `--no-write` (ledger section B). Fleet run
`whisker --all --json --no-write`, exit 5, 381 papers, 524.1s (E8). Fault
injection (E11): five deliberate faults, every one produced exit 1 or 5,
never 0. Determinism replay (E10): 3 papers scored twice in separate OS
processes, byte-identical stdout JSON in all 3.

## 3. Current Evidence

### 3.1 `_decide` is unchanged and still exactly two hard-fail paths

`score.py:174-231` (`_decide`) still has exactly two conditions that append
to `hard`: a failed structural gate (`score.py:177-179`) and
`unigram_coverage < C.UNIGRAM_COVERAGE_FAIL_EDGE` (`score.py:181-185`). Every
other signal, including the reference-oracle `ref_nid`
(`score.py:200-203`) and the golden-ideal panel axes (`score.py:205-215`),
only appends to `soft`. The docstring at `score.py:147-173` states this
explicitly and matches the code. This part of Auditv2's finding is
reconfirmed by direct re-reading of the current working-tree file, not
carried forward on trust.

### 3.2 Live confirmation of the exit-code contract (E9)

Against real papers (not synthetic fixtures): `N5036` (pass) exits 0 at
every gate level; `N5034` (review) exits 3 under `--gate pass`, 0 under
`--gate review`/`--gate fail`; `P3039R1` (fail) exits 5 under
`--gate pass`/`--gate review`, 0 under `--gate fail`. This is exactly the
documented 0/1/3/5 contract with zero deviation, now confirmed against real
paperstore data end to end rather than by code inspection alone.

### 3.3 Fault injection never produces a false pass (E11)

Five deliberate faults against the live deterministic path: unknown pid
(exit 1), empty markdown via `score-file` (exit 5, correctly scored as a
fidelity fail, not silently skipped), binary bytes as markdown (exit 1),
corrupt PDF as `--source` (exit 1), missing markdown file (exit 1). No fault
produced exit 0. This directly tests the "fail-closed" claim the score path
makes, live, rather than by tracing code paths for a hypothetical bad input.

### 3.4 Determinism replay confirms `_decide` is pure in practice, not just in theory

E10: N5034, N5036, and P3039R1 each scored twice in two separate OS
processes; all three produced byte-identical stdout JSON hashes. Combined
with `--no-write` leaving zero files changed on a real paper (E12), this is
live confirmation that the score path has no hidden state, hidden write, or
timing dependency that could make two runs on the same input diverge, a
claim Auditv2 could only make from reading `_decide`'s signature (a pure
function of 9 parameters) since it had no live workspace to replay against.

### 3.5 The RED suite's score-pinning failures: what they actually touch

Ledger E1 lists two `test_score_pinning.py` failures
(`p3556r0`: gate mismatch; `p2040r0`: `max_heading_level` mismatch,
actual=3, expected=4). Reading `tests/test_score_pinning.py` directly: this
test calls only `whisker.gates.run_gates(md_text)` and tomd's
`compute_metrics(md_text, file=stem)` (`test_score_pinning.py:90-91`)
against committed tomd golden markdown files, and diffs the result against a
committed JSON baseline (`test_score_pinning.py:161-183`). It does not call
`score.py::_decide` or `score_markdown` directly. It DOES exercise exactly
the two inputs `_decide` consumes for its hard-fail path: structural gates
(via `run_gates`) and the QA score/heading metrics (via `compute_metrics`,
which feeds `qa_score`, `uncertain_count`, etc. into `score_markdown`,
`score.py:262-263`).

This means the two failures are upstream of `_decide`'s own logic (which is
unchanged, 3.1) but squarely inside the two inputs that logic trusts blindly.
A `gate mismatch` on `p3556r0` means the structural-gate output for a
committed golden changed without an acknowledged baseline update: either the
golden markdown changed, or `gates.py`'s behavior changed, and the pinning
test is the only thing currently catching it (see `_EXPECTED_GATE_FAILURES`,
`test_score_pinning.py:153-158`, the explicit-acknowledgment allowlist
Auditv2 F9 already documented as a control). Likewise `p2040r0`'s
`max_heading_level` mismatch (actual 3, expected 4) is a tomd QA-metric
drift on a paper already listed in `_EXPECTED_GATE_FAILURES` for a DIFFERENT
gate (`heading_monotone`), meaning a second, unacknowledged property of the
same golden has drifted.

**This is the score path's own trustworthy-input contract failing its own
regression control, live, in the current working tree.** It is not a Lane 1
(`golden.py`) or Lane 3 (`facts.py`) test; see C11 and C12 for that
determination in full. It is a direct, unacknowledged drift in the values
`_decide` treats as ground truth for the hard-fail path.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | `_decide`'s two-hard-fail-path structure is unchanged and reconfirmed against the current working tree | Informational | HIGH |
| F2 | The exit-code contract (0/1/3/5) is live-confirmed against real paperstore data across all three verdict tiers and all three gate levels, with zero deviation | Informational | HIGH |
| F3 | Fault injection across 5 distinct failure modes never produced a false exit 0 | Informational | HIGH |
| F4 | Determinism replay across separate OS processes is byte-identical, live-confirming the purity claim Auditv2 could only state from the function signature | Informational | HIGH |
| F5 | `test_score_pinning.py` has two unacknowledged failures (`p3556r0` gate mismatch, `p2040r0` heading-metric mismatch) in the CURRENT working tree; these are inputs to `_decide`'s hard-fail path (structural gates, QA metrics), not `_decide` itself, but a drift here silently changes what `score.py` decides is a hard fail without the explicit acknowledgment the pinning suite exists to force | HIGH | HIGH |

## 5. False-Pass Hypothesis

**Could the score path pass a paper it should fail, because of the pinning
drift in F5?** Possible in principle, not confirmed either way this run. The
pinning test's job (per its own docstring, `test_score_pinning.py:8-22`) is
exactly to surface "any change to tomd golden output or whisker scoring
logic" as a diff; it is functioning as designed by failing loudly rather than
silently absorbing the drift. The open question the pinning failure raises,
and this report does not resolve, is which side moved: the `p3556r0`/
`p2040r0` golden markdown files (a tomd-side change) or `gates.py`/tomd's
`compute_metrics` (a scoring-side change). Either way, until the baseline is
either updated (with review) or the regression is fixed, `_decide`'s hard-
fail path is operating on at least one unverified input for these two
papers specifically. This does not generalize to the other 379 fleet papers
(E8), which are not in the pinning suite.

**Could the live exit-code and fault-injection evidence (3.2-3.4) be masking
this?** No: the live matrix (E9, E11) used different representative papers
(N5036, N5034, P3039R1) than the two pinning failures (p3556r0, p2040r0), so
the live confirmation and the pinning regression are about different papers
and do not contradict each other. They are two separate, non-overlapping
pieces of evidence, correctly reported as such rather than netted into one
verdict.

## 6. Gate/Dimension Mapping (PROPOSED)

| Gate | Dimension | Proposed status |
|------|-----------|------------------|
| D1 Determinism | `_decide` purity, live replay | PROPOSED PASS (E10, byte-identical across processes) |
| D1 Determinism | Exit-code contract under live scoring | PROPOSED PASS (E9) |
| D3 Advisory non-leakage | `ref_nid`/ideal panel confined to soft flags | PROPOSED PASS (unchanged code, 3.1) |
| D1 Determinism | Input trustworthiness for the hard-fail path (gates.py output, tomd QA metrics) | PROPOSED FAIL for the two affected papers: unacknowledged drift in the pinning suite (F5) |

## 7. Limitations

- The pinning-drift root cause (tomd golden change vs. gates.py/QA-metric
  change) was not diagnosed in this report; it requires diffing the golden
  markdown files and `gates.py`/tomd QA history, which is outside this
  claim's evidence set.
- Live determinism replay (E10) covers 3 papers, not the full 381-paper
  fleet; it is a spot-check, not exhaustive replay.
- The `score-file` subcommand's parallel verdict implementation (noted by
  Auditv2 as a maintenance risk, not re-audited independently this run)
  was not separately live-tested against the pinning-affected papers.

## 8. Conclusion

The score path's own internal logic (`_decide`) is unchanged, reconfirmed
by direct reading, and now additionally live-confirmed under real workspace
execution, fault injection, and cross-process determinism replay, evidence
Auditv2 could not gather. Layered on top of that reconfirmation is a new,
concrete problem this run's RED suite surfaces: two of the score path's
trusted inputs (structural gate output and tomd QA metrics) have drifted,
unacknowledged, for two specific golden papers. The mechanism the codebase
built specifically to catch this kind of silent drift is the one currently
failing, which is the correct behavior of that control, not a new bug in
`_decide` itself.

## 9. Delta vs Auditv2

Auditv2's C10 was built entirely from static code tracing ("Runtime
verification with actual paper data requires `WG21_DATA_DIR` (not available
in this audit)") and concluded an unqualified "Gate verdict: PASS." This run
adds four live evidence streams Auditv2 explicitly could not obtain (E8-E12,
sections 3.2-3.4) that all reconfirm the static claims under real execution.
It also surfaces a finding Auditv2's all-passing test suite (1406 passed, 0
failed) could not have found: the current working tree's test suite is RED
specifically in the pinning mechanism that guards this exact code path
(F5), a regression against Auditv2's baseline that this report attributes
correctly to the path's inputs rather than to `_decide` itself.
