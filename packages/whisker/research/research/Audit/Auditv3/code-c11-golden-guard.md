# C11 Golden and Guard

**Role**: Audit Lane 1 stability (`golden.py`) and the per-paper regression guard (`guard.py`), and determine whether this run's RED suite implicates either.
**Audited state**: whisker 0.5.0, working tree, manifest b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771
**Gates**: D2 (Reproducible scoring pipeline), D4 (Scoring accuracy)

## 1. Scope

Confirm `golden.py`'s exact-diff mechanism and `guard.py`'s per-paper,
per-axis regression detection are unchanged in the working tree, and
directly answer the planner's question: do the three RED failures in ledger
E1 touch Lane 1 or Lane 2's guard mechanism.

## 2. Commands and Exits

`uv run --package whisker pytest packages/whisker/tests -q --tb=line` (E1):
`3 failed, 1784 passed, 8 skipped, 3 xfailed`. The three named failures are
`test_dev_replay_schema.py::TestHoldoutAnchors::test_locked_candidate_dispositions`,
`test_score_pinning.py::test_score_pinned[p3556r0]`, and
`test_score_pinning.py::test_score_pinned[p2040r0]` (ledger E1 table).

## 3. Current Evidence

### 3.1 `golden.py` mechanism, reconfirmed unchanged

`normalize_for_exact_lane` (`golden.py:79-90`): collapses `\r\n`/`\r` to
`\n`, strips trailing whitespace per line, enforces one trailing newline.
`_evaluate` (`golden.py:155-179`): missing candidate is always
`STATUS_MISSING` (hard fail); missing expected snapshot is `STATUS_NEW`
(passes unless `--fail-on-new`); a normalized match is `STATUS_OK` or
`STATUS_XFAIL_OK`; any other difference is `STATUS_CHANGED` with a unified
diff. `GoldenReport.failed` (`golden.py:133-134`) checks
`_FAILING_STATUSES = {STATUS_CHANGED, STATUS_MISSING}` plus `fail_on_new`.
This is a direct re-read of the current working-tree file and matches
Auditv2's description exactly; no drift found in this module.

### 3.2 `guard.py` mechanism, reconfirmed unchanged

`baseline_from_rows` (`guard.py:227-248`) embeds `schema_version`,
`tool_versions`, `axis_slack`, and `floors` into the committed baseline so
the contract travels with the data. `_validate_baseline`
(`guard.py:251-304`) hard-rejects a wrong `kind`, a mismatched
`schema_version`, a mismatched `tool_versions` entry, or a non-finite stored
axis. `_evaluate_paper` (`guard.py:330-393`) catches non-finite current
values first (`STATUS_INVALID`), then floor breaches, then, for an existing
paper, regression (`drop > slack`) or sub-slack floor crossing. A missing
paper is a hard fail in `GuardReport.failed` (`guard.py:187-191`) regardless
of per-axis status. All of this matches the current source file; no drift
found.

### 3.3 Direct determination: neither RED failure is in Lane 1 or the guard mechanism

This is the specific question the planner posed. Answered plainly by
reading each failing test file directly, not inferring from its name:

- **`test_score_pinning.py::test_score_pinned[p3556r0]` and
  `[p2040r0]`**: this file imports only `whisker.gates.run_gates` and
  tomd's `compute_metrics` (`test_score_pinning.py:32,34,90-91`). It never
  imports or calls anything from `whisker.golden` or `whisker.guard`. It is
  a regression pin on structural gates and tomd QA metrics, the inputs to
  `score.py::_decide` (see C10). It is **not** a Lane 1 (golden) or Lane 2
  guard test.
- **`test_dev_replay_schema.py::TestHoldoutAnchors::test_locked_candidate_dispositions`**:
  this file imports `whisker.tapetum_llm.grounding.classify_candidate_evidence`
  and `whisker.tapetum_llm.models.EvidenceSpan`
  (`test_dev_replay_schema.py:20-27`). The failing test loads locked
  candidate/source fixtures from `packages/whisker/corpus/holdout/` (three
  papers: `p1112r4`, `p3714r0`, `p4182r0`, per `holdout/manifest.json`),
  reconstructs `GroundedSpan` objects from committed anchor JSONL, and
  asserts `classify_candidate_evidence` still returns the expected
  disposition (`present_in_candidate`/`candidate_not_found`/`ambiguous`) for
  every anchor. This is the advisory LLM lane's own evidence-classification
  regression harness, not `golden.py`'s exact-diff lane and not
  `guard.py`'s per-axis regression guard. Ledger E1 names the failing
  assertion target as `p4182r0`, whose locked candidate is
  `packages/tomd/tests/fixtures/golden/ideals/p4182r0.md`, a human-blessed
  ideal used by the LLM lane's grounding module, not a whisker golden
  snapshot or guard baseline entry.

**Plain statement: no RED failure this run touches `golden.py`, `guard.py`,
`test_golden.py`, or `test_guard.py`.** All three failures are in adjacent
machinery: two in the score-path's trusted inputs (C10), one in the
advisory LLM lane's evidence-classification holdout harness (out of this
claim's scope, more properly a C09/C13-family concern). `test_golden.py`
and `test_guard.py` are part of the 1784 tests that passed.

### 3.4 What this means for Lane 1/Lane 2 stability itself

Because the RED failures are not in `golden.py` or `guard.py`'s own test
files, this run has no direct evidence of a regression in either
mechanism's own logic. Auditv2's structural findings (F1-F11 in that
report: normalizer correctness, symlink rejection, regression/floor-crossing
detection, tool-version pinning, NaN/inf hard-fail, null-eligibility
skipping) are reconfirmed by the unchanged source (3.1, 3.2) but were not
independently re-run against live fleet data this pass; this audit's live
evidence effort (sections B and C of the shared ledger) was directed at the
deterministic score path and the LLM lane, not at a fresh `whisker guard
--update`/diff cycle. That is a genuine coverage gap for this specific
claim, recorded honestly rather than papered over with the unchanged-source
finding.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | `golden.py`'s normalize/evaluate/report logic is unchanged from Auditv2's description, confirmed by direct re-read of the current working-tree file | Informational | HIGH |
| F2 | `guard.py`'s baseline validation, regression, floor-crossing, and missing-paper logic is unchanged, confirmed by direct re-read | Informational | HIGH |
| F3 | Neither of the two `test_score_pinning.py` RED failures touches Lane 1 (`golden.py`) or the guard mechanism (`guard.py`); both are in the score-path's structural-gate/QA-metric inputs (see C10) | Informational (clarifies scope, does not implicate this claim) | HIGH |
| F4 | The `test_dev_replay_schema.py` RED failure is in the advisory LLM lane's evidence-classification holdout harness (`grounding.py::classify_candidate_evidence`), not Lane 1 or Lane 2's guard | Informational (clarifies scope) | HIGH |
| F5 | This audit did not independently re-execute a live `whisker guard`/`whisker golden --update` cycle against fleet data; the mechanism's correctness this run rests on unchanged-source inspection, not fresh live evidence | LOW | HIGH |

## 5. False-Pass Hypothesis

**Could the RED suite be hiding a real Lane 1/Lane 2 regression by
coincidence, i.e. is it possible `golden.py`/`guard.py` broke but no test
happens to catch it?** Not ruled out by this report. The evidence available
(unchanged source, 1784 of 1787 non-excluded tests passing, and specifically
`test_golden.py`/`test_guard.py` among the passing set per ledger E1's
arithmetic) is consistent with the mechanism being sound, but this claim did
not independently generate a live guard baseline diff against the current
381-paper fleet (E8) to positively confirm zero silent regressions there.
The distinction matters: "the tests that exist still pass" is weaker than
"we ran the guard against real data and it agreed with the tests."

**Could the planner's question itself reveal a scope confusion in how the
audit organizes claims?** Worth flagging plainly: `test_score_pinning.py`
sits at the seam between C10 (score path) and C11 (this claim) precisely
because `gates.py` output feeds both `score.py::_decide`'s hard-fail path
AND indirectly informs what a human would expect a golden snapshot's gate
column to say. This report resolves the ambiguity by scoping strictly to
what the failing test imports and calls (3.3), not by which lane feels
closest by name.

## 6. Gate/Dimension Mapping (PROPOSED)

| Gate | Dimension | Proposed status |
|------|-----------|------------------|
| D2 Reproducible scoring pipeline | `golden.py` exact-diff mechanism | PROPOSED PASS (unchanged, source-confirmed) |
| D4 Scoring accuracy | `guard.py` regression/floor-crossing mechanism | PROPOSED PASS (unchanged, source-confirmed) |
| D2/D4 | Live fleet-scale re-verification of golden/guard this run | PROPOSED gap: not attempted; recommend a live `whisker guard`/`whisker golden` pass in the next audit cycle |
| N/A | RED-suite attribution to Lane 1/Lane 2 | PROPOSED: correctly attributed elsewhere; not a Lane 1/Lane 2 finding |

## 7. Limitations

- No fresh live `whisker golden` or `whisker guard` invocation was run
  against the 381-paper fleet this audit pass; the mechanism's soundness
  rests on source-code reconfirmation plus the passing offline test suite,
  not new runtime evidence at fleet scale.
- This report does not re-verify Auditv2's individual test-by-test
  breakdown (27 golden tests, 31 guard tests); it confirms the modules they
  test are unchanged and infers those tests still exercise the same logic.
- The advisory LLM lane's holdout regression (`test_dev_replay_schema.py`)
  is out of scope for this claim beyond the scoping determination in 3.3;
  its root cause is not diagnosed here.

## 8. Conclusion

`golden.py` and `guard.py` are unchanged from Auditv2's audited state, and
this run answers the planner's direct question unambiguously: none of the
three RED test failures in ledger E1 touch Lane 1 stability or the Lane 2
guard mechanism. Two are in the score path's structural-gate/QA-metric
inputs (C10's territory) and one is in the advisory LLM lane's evidence-
classification holdout harness (neither Lane 1 nor Lane 2). This is good
news narrowly construed, but it is paired with an honest gap: this claim's
own evidence is source-reconfirmation plus a passing offline suite, not a
fresh live guard/golden run against the current fleet, which Auditv2 also
could not do and this audit did not prioritize either.

## 9. Delta vs Auditv2

Auditv2's C11 was entirely static (HEAD 51cb704, offline test counts) and
concluded an unqualified summary of both lanes as "well-constructed and
thoroughly tested," citing 1406 passed/8 skipped/3 xfailed with zero
failures. This run's baseline is RED (1784 passed/3 failed), a fact Auditv2
never had to reckon with. The principal addition this report makes over
Auditv2 is not new mechanism evidence (the modules are unchanged, 3.1-3.2)
but the explicit, source-verified triage of the RED suite against this
claim's scope (3.3), which Auditv2's clean suite made unnecessary. Auditv2's
per-test tables (27 golden tests, 31 guard tests) are not re-verified
line-by-line here; they are assumed current given the unchanged source, a
weaker standard of evidence than Auditv2's own clean-run confirmation.
