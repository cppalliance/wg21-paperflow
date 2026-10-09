# C28 Engineering Meta-Review

**Role**: Assess engineering quality, dependency hygiene, packaging, test
discipline, and maintainability as a system, independent of whether any
individual gate or metric is correct.
**Audited state**: whisker 0.5.0, working tree, manifest
b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771
**Gates**: CLAUDE.md invariants (BSL-1.0 headers, named thresholds, no
`default=str`, standalone core/extra isolation), PROPOSED.

## 1. Scope

Test suite health (pass/fail state, coverage gaps, what a red test actually
means here), dependency and license hygiene, wheel/packaging correctness, and
the maintainability cost of the working tree's current shape (uncommitted
scope, dormant subtrees, documentation drift).

## 2. Commands and Exits

```
uv run --package whisker pytest packages/whisker/tests -q --tb=line   (E1, exit 1)
uv run --package whisker pytest packages/whisker/tests --collect-only -q  (exit 0, 1798 collected)
uv build --package whisker --wheel   (exit 0)
uv lock --check   (exit 0, "Resolved 249 packages in 7ms")
```

## 3. Current Evidence

### 3.1 The suite is red, and the failures are not interchangeable

E1: `3 failed, 1784 passed, 8 skipped, 3 xfailed` (1798 collected). This is a
regression against Auditv2's `1406 passed, 8 skipped, 3 xfailed`, zero
failures. The three failures are not equally significant:

| Test | Assertion | What it means |
|---|---|---|
| `test_score_pinning.py::test_score_pinned[p3556r0]` | gate mismatch | The pinning tripwire, whose sole job is catching unannounced gate/metric drift, has drifted |
| `test_score_pinning.py::test_score_pinned[p2040r0]` | `max_heading_level` actual=3, expected=4 | Same mechanism, second paper; the golden ideal's structure changed without a re-baseline |
| `test_dev_replay_schema.py::TestHoldoutAnchors::test_locked_candidate_dispositions` | `AssertionError: p4182r0`, at line 190 (candidate-hash check) | The locked candidate file for the project's canonical comprehension corpus paper no longer matches its recorded hash |

Two of three failures are inside `test_score_pinning.py`
(`packages/whisker/tests/test_score_pinning.py:170`, `:181`), the mechanism
`CLAUDE.md:879-881` names as the fix for "no CI guard against silent gate
additions." A red pinning test is not evidence of flakiness; it is the
mechanism doing its job and finding a real, uncommitted drift that has not
been reconciled. Treating these three as ordinary failures to be triaged
later would be a misreading of what they are.

### 3.2 Test coverage gaps, one persistent, several new

`tables.py` (the shared grid parser `facts.py` and `bench.py` both depend
on) has zero test functions referencing it directly (E3, `raw/w1-test-suite.md`
section 5). This exact finding appears in Auditv2 as F01 ("Medium"); it is
unresolved across two audit cycles. New in this cycle: `vlm_pipeline.py` and
`judge_task.py` also have zero referencing test functions (E3), and
`readback_cli.py`, `vision.py`, `vision_task.py`, `vlm_diff.py`,
`table_compare.py`, and `survey/` (eight `test_survey_*.py` files but no
single entry-point test) have no dedicated `test_<name>.py` file at all.
`table_compare.py` specifically implements table-cell comparison logic
(`CLAUDE.md`'s a17 rule #23, "P0 fixes... now in `table_compare.py`"), a
mechanism the project itself calls a priority fix, tested only indirectly
through `test_mutation_corpus.py` and `test_defect_accountability.py`.

### 3.3 Packaging surface nearly doubled since Auditv2

Auditv2's wheel build (its C09/F06) reported 49 files. This audit's wheel
build (E6) reports **80 files**. The growth is not incidental: `survey/` (9
files incl. a `marker.py` adapter and a lockfile), `compare/` (6 files),
`branding/` (6 files incl. two binary assets), and new `tapetum_llm` modules
(`ideal_verify.py`, `metadata_compare.py`, `payload_scope.py`,
`table_compare.py`) all ship in the core wheel. Per C25 (E4), none of
`compare/`, `branding/`, or the VLM chain has any operator path, and per SS3.2
above, several of the newest modules have thin or no direct test coverage.
The wheel therefore ships substantially more code than an operator can reach
or a test file directly exercises, and this is new growth, not a
carried-forward Auditv2 finding.

### 3.4 License hygiene: sound, with one unresolved cross-audit contradiction

E7: no core dependency reports a GPL-family license. `rapidfuzz` (MIT)
remains the deliberate replacement for GPL `levenshtein`. But this run's
installed-metadata scan reports `pylatexenc` as **MIT**; Auditv2's ledger
(its E11, cited via C26 v2's G7 discussion of "LGPL-3.0+ (pylatexenc)")
recorded it as **LGPL-3.0+**. One of the two is wrong. This report does not
adjudicate which (that belongs to a license-specific claim), but flags it as
an engineering-process gap: two audits, ten days apart by the repository's
own dating, produced contradictory machine-read license metadata for the
same unchanged dependency declaration (`pylatexenc>=2.10` in both
`pyproject.toml` snapshots), which means at least one of the two scans was
run against a different resolved environment, a different pylatexenc
version, or was transcribed incorrectly. `THIRD_PARTY_NOTICES.md` continues
to name only `langextract`; TEDS, GriTS, APTED, OmniDocBench, and markitdown
remain undocumented as ported/adopted algorithms there (E7), unchanged from
Auditv2.

### 3.5 The audited tree is less reproducible than Auditv2's, not more

Auditv2 audited HEAD `51cb704` plus "18+ modified source files, 13+ modified
test files" and rated this a High-severity engineering risk (its F07). This
audit's target (00-PRECONDITIONS.md SS1) is HEAD `0d18a65` plus **7205
uncommitted insertions across 44 files**, plus whole untracked packages
(`survey/`, `compare/`, `branding/`) and 18 untracked test files. The
mitigation is a content-hash manifest (157 files,
`b9ad8ab0...8f771`), which lets a reader verify they hold the same bytes but
does not restore git-level reproducibility: "Reproducibility from a clean
clone remains impossible for this run" (00-PRECONDITIONS.md SS5). This is a
materially larger uncommitted surface than Auditv2 flagged, addressed by a
different, weaker mechanism (content hash vs. commit).

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---|---|---|
| F1 | Suite is red; 2 of 3 failures are inside the score-pinning tripwire itself | High | HIGH |
| F2 | Third failure is a broken provenance lock on the canonical comprehension corpus paper's candidate file | High | HIGH |
| F3 | `tables.py` remains untested directly across two audit cycles | Medium | HIGH |
| F4 | New, undertested surface: `vlm_pipeline.py`, `judge_task.py` (zero referencing tests), `table_compare.py` (indirect only) | Medium | HIGH |
| F5 | Wheel file count grew from 49 to 80 since Auditv2, driven by subtrees with weak test coverage and no operator path | Medium | HIGH |
| F6 | `pylatexenc` license metadata contradicts Auditv2's recorded value (MIT here vs LGPL-3.0+ there) for an unchanged dependency spec | Medium | MEDIUM |
| F7 | `THIRD_PARTY_NOTICES.md` still omits TEDS/GriTS/APTED/OmniDocBench/markitdown, unchanged from Auditv2 | Low | HIGH |
| F8 | Uncommitted surface grew from Auditv2's 18+ files to 7205 insertions across 44 files plus whole untracked packages | High | HIGH |

## 5. False-Pass Hypothesis

**Could the two pinning failures be dismissed as "expected" because
`p2040r0` already has a documented false-gate entry?**
`_EXPECTED_GATE_FAILURES` (`test_score_pinning.py:153-158`) lists `p2040r0`
as having a known `heading_monotone` false-gate, which is a different
assertion from `test_score_pinned`'s `max_heading_level` field check. The
`_EXPECTED_GATE_FAILURES` mechanism acknowledges a specific gate result as
known-bad; it does not exempt the paper's structural metrics from matching
the pinned baseline. A failing `max_heading_level` means the underlying
golden ideal content changed, a distinct fact from the pre-acknowledged gate
quirk, and the "expected failure" allowlist does not cover it.

**Could F6 (the license contradiction) be explained by Auditv2 having used a
different Python environment where pylatexenc actually was a different,
LGPL-licensed version?** Possible, and this report cannot rule it out without
independently re-running Auditv2's exact command against Auditv2's exact
lockfile state, which is out of scope here. What can be said: `uv.lock`
reports no drift in this run (`uv lock --check`, "Resolved 249 packages in
7ms", exit 0), so if the version differs, it differs against a
prior lockfile state, not within this one.

## 6. Gate/Dimension Mapping (PROPOSED)

- **Test discipline: PROPOSED FAIL-UNPROVEN for "no unannounced scoring
  changes."** The specific mechanism built to prove this is currently red.
- **Coverage completeness: PROPOSED PASS-PROVISIONAL.** The gaps are real,
  documented, and partly persistent (F3) or newly introduced (F4); none is
  catastrophic (indirect coverage exists for most), but the trend (growing
  undertested surface, F5) is negative.
- **Packaging correctness: PROPOSED PASS.** The build succeeds, ships no
  tests or research clones, and BSL headers are complete (69/69). Correctness
  of what ships is not in question; whether what ships should ship this large
  is a separate, PROPOSED PASS-PROVISIONAL judgment.
- **License hygiene: PROPOSED PASS-PROVISIONAL.** No GPL in core dependencies
  by either audit's reading; the pylatexenc contradiction (F6) is an
  unresolved data-integrity question that should be closed before either
  figure is cited with confidence.
- **Reproducibility: PROPOSED FAIL-UNPROVEN.** Larger uncommitted surface
  than Auditv2, mitigated by a manifest hash rather than resolved by a
  commit.

## 7. Limitations

- This report did not re-run Auditv2's license scan itself; the contradiction
  (F6) is reported as observed, not adjudicated.
- The specific gate diff behind `p3556r0`'s "gate mismatch" failure was not
  extracted (only the assertion message is cited); it is possible this
  failure has a narrower, more benign cause than `p2040r0`'s, which this
  report cannot distinguish from the traceback alone.
- No attempt was made to determine which of the 7205 uncommitted insertion
  lines caused the `p2040r0`/`p3556r0` drift specifically; the diff was not
  walked line-by-line.

## 8. Conclusion

The engineering quality remains, as Auditv2 found, above average for a
pre-1.0 tool on most static axes: packaging is clean, BSL headers are
complete, no core GPL dependency exists, and the deterministic core has
strong indirect and direct test coverage. But two things have moved in the
wrong direction since Auditv2, and both are structural rather than cosmetic.
First, the suite went from fully green to red, and the specific failures are
inside the tripwire mechanism built to catch silent scoring drift and inside
the provenance lock for the paper the project's comprehension-testing story
is built on, not in some unrelated corner. Second, the uncommitted surface
and the packaged-but-unreachable code both grew substantially, compounding
Auditv2's already-flagged reproducibility risk rather than resolving it. A
test suite report that only counted 1784 passes and moved on would miss both
of these; the failures are small in count and large in meaning.

## 9. Delta vs Auditv2

Auditv2's `code-c28-engineering-meta-review.md` audited a fully green suite
(1406 passed, 0 failed) with 18+ modified files, and its highest-severity
findings were process risks (F07 reproducibility, F12 PR-readiness), not test
failures. This audit inherits both those process risks in a worse state
(7205 insertions vs. 18+ files) and adds a category Auditv2 never had to
grapple with: actual, current, unreconciled test failures inside the exact
mechanisms meant to prevent them. Auditv2's F01 (`tables.py` untested) is
confirmed unchanged, a genuine two-cycle persistence rather than a fixed
issue re-appearing. Auditv2's wheel count (49 files, its F06/C09) is now 80,
entirely new growth this report is the first to measure. The pylatexenc
license contradiction (F6) is new specifically because it required both
audits' independently-run scans to exist and disagree; Auditv2 alone could
not have produced this finding.
