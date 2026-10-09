# C28 Engineering and Release Meta-Review

**Role:** Adversarial meta-reviewer. Challenge C01-C25 from engineering quality,
test discipline, documentation accuracy, packaging, change risk, and merged
implementation interoperability perspectives.
**Date:** 2026-07-20
**Audited state:** whisker 0.5.0, HEAD 51cb704 + 18+ uncommitted source file
modifications, 13+ test file modifications, 2 untracked source/test files.

---

## 1. Test Discipline

### F01 (Medium): `tables.py` has no dedicated test file

**Finding:** `tables.py` (142 LOC, shared by `facts.py` and `bench.py`) has no
`test_tables.py`. Its coverage derives indirectly from `test_facts.py` (table
neighbor checks) and `test_metrics.py` (TEDS via HTML tables). No test directly
exercises `parse_pipe_tables` edge cases (escaped pipes, empty cells, ragged
rows) or `parse_html_tables` edge cases (malformed HTML, missing `<tr>`,
colspan/rowspan handling).

**Severity:** Medium
**Confidence:** HIGH
**Evidence:** `Glob("packages/whisker/tests/test_tables.py")` returns no match.
Grep for `from whisker.tables` in tests returns hits only in `test_facts.py`
(indirect, via `facts.check_facts`) and nowhere directly.

**Challenge to C15:** C15 mentions `tables.py: 142 lines` in scope but never
audits its parsing correctness independently. The grid model's known
rowspan/colspan limitation (CLAUDE.md gap #10) has no regression test preventing
silent breakage of the flatten-to-first-slot logic.

---

### F02 (Low): `corpus_tools.py` test coverage is minimal

**Finding:** `corpus_tools.py` (stratum classification, draft-facts scaffolding)
is tested only via two functions imported in `test_facts.py` (`classify_paper`,
`draft_facts_scaffold`). The `stratify_candidates` function (which integrates
with the paperstore backend) has no unit test. The fence-stripping logic
(`_strip_fenced_blocks`) used to avoid false-positive display-math detection in
code identifiers has no dedicated edge-case test.

**Severity:** Low
**Confidence:** HIGH
**Evidence:** Grep `from whisker.corpus_tools` in test files: only `test_facts.py`
line 10.

---

### F03 (Info): 1:1 source:test LOC ratio is healthy but asymmetric

**Finding:** The 15,589:14,436 ratio (1.08:1) is excellent for a QA tool. However
distribution is uneven: `tapetum_llm/` (24 files, ~6,000+ LOC) relies on 8 test
files where most tests are offline mocks (no real LLM). The deterministic core
(19 files) has 28 dedicated test files with concrete fixture data. The advisory
lane's real behavior is BLOCKED (E9) and untestable without credentials.

**Severity:** Info
**Confidence:** HIGH
**Evidence:** E5 (431 tests for tapetum_llm) vs E4+E6 (682 tests for core). The
tapetum tests are structurally sound offline but unverified at runtime.

---

## 2. Documentation (CLAUDE.md)

### F04 (Low): CLAUDE.md claims "879 lines" but its content is accurate

**Finding:** Compared the CLAUDE.md claims against code:
- "whisker core never imports tapetum_llm" -> verified, no reverse import exists.
- "Every metric is a pure function" -> verified by C02, frozen dataclasses.
- "Advisory lane instability >= 25% verdict-flip rate" -> documented, not
  re-measured post v0.5.0 changes (C17 notes this gap). The claim is historical.
- "5 corpus papers, 37 verified facts" -> consistent with C01 inventory.
- "Lane 2 edges are provisional, not fitted" -> honest, consistent with C10.

**Severity:** Low
**Confidence:** HIGH
**Evidence:** No material contradictions found between CLAUDE.md and code.

**Adversarial challenge:** The 879-line CLAUDE.md is itself a maintenance
liability. At this size it risks becoming stale documentation. A section-level
freshness check (last-modified date per section) would catch drift. Currently
nothing enforces its accuracy except `test_claude_invariants.py`, which tests
only a subset of claims.

---

### F05 (Medium): `test_claude_invariants.py` covers only structural invariants

**Finding:** The invariant test file checks import isolation, constants naming,
and `__init__.py` re-export rules. It does NOT verify behavioral claims like
"LLM never gates," "sorted outputs," or "no default=str." These are verified by
other test files (fusion, score, report) but there is no single regression test
that would break if advisory-to-deterministic leakage were introduced.

**Severity:** Medium
**Confidence:** HIGH
**Evidence:** `test_claude_invariants.py` exercises file-level structural
assertions. The absence of a dedicated "no advisory import in score.py" assertion
means a future developer could add `from whisker.tapetum_llm import ...` to
`score.py` without any test failing specifically because of that invariant.

**Counter-argument:** C03 audits this manually and fusion tests verify
asymmetric rules. The risk is future regression, not current violation.

---

## 3. Packaging

### F06 (Info): pyproject.toml is well-structured, no issues found

**Finding:** The `pyproject.toml` correctly:
- Separates core deps from optional `tapetum-llm` extra.
- Pins `rapidfuzz>=3.14.5,<4` (major-version upper bound).
- Uses `hatchling` with `packages = ["src/whisker"]` (no corpus/research leakage).
- Declares `requires-python = ">=3.12"` (reasonable for 2026).
- Three console scripts registered correctly.

**Severity:** Info
**Confidence:** HIGH
**Evidence:** C09 confirms wheel builds successfully with 49 files, all source
modules present, no stale artifacts.

**Minor note:** `paperstore` and `tomd` (workspace deps) have no version pins.
This is fine for monorepo development but means the wheel is not independently
installable from PyPI without those workspace packages.

---

## 4. Change Risk (Uncommitted Code)

### F07 (High): Auditing uncommitted code undermines reproducibility

**Finding:** C01 documents 18+ modified source files and 13+ modified test files
as the audited state. Key problems:

1. **Non-reproducible audit:** Another auditor at the same HEAD (51cb704) would
   see different code. The audit boundary is HEAD + working-tree state, which
   cannot be reconstructed from git alone.
2. **Scope uncertainty:** The modified files span both the deterministic core
   (`metrics.py`, `golden.py`, `corpus_tools.py`, `__main__.py`) and the
   advisory lane (7+ tapetum files). Changes may interact in ways the committed
   test suite cannot catch because the test modifications co-evolved with the
   source.
3. **Risk of regressed state:** If the uncommitted changes are abandoned or
   further modified before commit, findings from this audit become stale.

**Severity:** High
**Confidence:** HIGH
**Evidence:** C01 section "1. Worktree boundary" + git status showing extensive
local modifications.

**Mitigation observed:** All 1406 tests pass on the uncommitted state (E1). The
score-pinning baseline (`fixtures/score-baseline.json`) was presumably updated
to match the current working tree (it is listed as modified). This means the
tests validate internal consistency of the uncommitted state, but not that this
state is the INTENDED release state.

---

### F08 (Medium): `ideal_verify.py` is an untracked new file

**Finding:** `tapetum_llm/ideal_verify.py` and `tests/test_ideal_verify.py` are
both `??` (untracked). This module implements the conditional ideal verifier
(a new feature) that several reports (C20, C21) reference. If the audit
declares this feature "present and working" but the file is never committed,
the audit findings are void for that feature.

**Severity:** Medium
**Confidence:** HIGH
**Evidence:** Git status shows `?? packages/whisker/src/whisker/tapetum_llm/ideal_verify.py`.

---

## 5. Merged Implementation Interoperability

### F09 (Info): `score-file` and `check-facts` are correctly dispatchable

**Finding:** Both file-bridge commands are registered in `__main__.py` and
tested by `test_score_file.py` and `test_check_facts_main.py`. They operate
without a paperstore backend (file paths as arguments). They coexist with the
workspace-based commands. `whisker -h` lists both. No namespace collision.

**Severity:** Info
**Confidence:** HIGH
**Evidence:** C01 section 6 (CLI help surfaces), E6 (464 interop tests pass).

---

### F10 (Info): Deterministic and LLM reports are correctly separated

**Finding:** Output paths are split: `whisker/det/` for deterministic,
`whisker/llm/` for advisory. Three CLI entry points (`whisker`,
`whisker-tapetum-llm`, `whisker-readback`) own their respective artifact paths.
Fusion (`fuse_verdicts`) merges but never overwrites the deterministic sidecar.

**Severity:** Info
**Confidence:** HIGH
**Evidence:** C03 confirms non-leakage. C04 confirms error tombstones stay in
`whisker/llm/`. C25 confirms exit codes derive only from deterministic verdicts.

---

### F11 (Low): VLM lane (788 LOC, 5 files) is dead code in production

**Finding:** `vlm_diff.py`, `vlm_pipeline.py`, `vision.py`, `vision_task.py`,
plus partial `tapetum_llm/__init__.py` re-exports constitute 788 LOC that has
no production command, no CLI entry point, and no integration test exercising
real behavior. It is tested only via mock-based structural tests
(`test_vlm_lane.py`) that assert the boundary (text-only guard). This is a
maintenance burden: dead code that must be kept compilable across dependency
upgrades without delivering user value.

**Severity:** Low
**Confidence:** HIGH
**Evidence:** CLAUDE.md "Known gaps" #4: "VLM lane is unwired. Decision pending:
delete vs quarantine behind a feature flag."

---

## 6. PR Readiness

### F12 (High): The codebase is NOT ready for a clean PR as-is

**Finding:** Blockers for a clean PR:

1. **Uncommitted local modifications across 18+ files.** A PR must be a clean
   diff from a known base commit. The current state requires either committing
   all changes as one PR (too large for review) or splitting into logical units.
2. **Two untracked files** (`ideal_verify.py`, `test_ideal_verify.py`) are
   referenced by other reports but not in version control.
3. **Modified `score-baseline.json`** implies the baseline was updated locally
   but not committed. A reviewer cannot verify the old-vs-new baseline diff.
4. **Real-LLM runtime BLOCKED.** Any advisory-lane behavioral claims cannot be
   verified before merge.
5. **VLM dead code.** 788 LOC of unwired code would draw review attention and
   questions about intent.

**Severity:** High
**Confidence:** HIGH
**Evidence:** Composite of git status, C01 boundary analysis, and E9 runtime
block.

**What would unblock:**
- Commit or stash all changes into reviewed, logical commits.
- Resolve VLM fate (quarantine or delete).
- Document the runtime block as a known limitation in CHANGELOG or PR body.
- Split the diff: deterministic-core changes, advisory-lane changes, new ideal
  verifier, corpus additions.

---

## 7. Windows Behavior

### F13 (Low): Windows-specific issues are handled but not integration-tested

**Finding:** Code inspection shows:
- `readback_cli.py::main()` reconfigures stdout to UTF-8 with
  `errors="replace"` (CLAUDE.md documents the cp1252 fix).
- `report.py::_paint()` gates ANSI codes on `color=True` (set by tty detection).
- `__main__.py` uses `sys.stderr.isatty()` to suppress progress bars in pipes.
- File I/O uses `encoding="utf-8"` explicitly.
- Exit codes are numeric (platform-independent).

No Windows-specific integration test exists. The test suite runs on Windows
(documented: "OS: Windows NT 10.0.26200.0") and passes 1406/1406, which is
strong indirect evidence. But no test asserts behavior under cp1252 encoding,
no test verifies ANSI suppression in non-tty contexts, and no test exercises
path handling with Windows separators (backslash vs forward slash).

**Severity:** Low
**Confidence:** MEDIUM
**Evidence:** All tests pass on Windows (E1). Code inspection confirms encoding
guards. No dedicated Windows integration test module exists.

---

### F14 (Info): Path handling uses `pathlib.Path` throughout

**Finding:** The codebase uses `pathlib.Path` (not string concatenation) for
file operations, which handles Windows backslash paths correctly. The
`golden_ideals.py` discovery walk uses `Path.parents` and `/` operator
(platform-safe). No `os.path.join` with hardcoded `/` separators found in
the scoring path.

**Severity:** Info
**Confidence:** HIGH

---

## 8. Adversarial Challenges to Primary Reports

### Challenge to C02 (Deterministic Core): Cross-platform determinism untested

C02 correctly identifies within-process determinism but acknowledges
"Cross-platform determinism (different numpy/scipy builds) is not tested."
This is a real gap: if a CI runner uses a different numpy build (e.g., OpenBLAS
vs MKL), the Hungarian assignment for degenerate cost matrices could differ.
The `_NDIGITS = 4` rounding mitigates but does not eliminate this. No cross-OS
determinism test exists in CI.

### Challenge to C05 (Quality-Stability): Replay is intra-process only

C05 F6/F7 honestly document this. The score-pinning suite tests the scoring
engine on pre-computed golden fixtures, not the full pipeline (source
extraction -> conversion -> scoring). A regression in `markitdown` (the oracle)
would not be caught by score pinning. This is an architectural choice (hermetic
CI without staged sources) but weakens the "quality stability" claim.

### Challenge to C09 (License): No automated license scanning in CI

C09 relies on known-package reputation ("well-known packages with documented
permissive licenses"). A future dependency update that pulls in a GPL
transitive dependency (e.g., if `grits-metric` added a GPL dep) would not be
caught automatically. No `pip-licenses` or `liccheck` CI step exists.

### Challenge to C25 (Professional Surface): `rich` interaction unaudited

C25 acknowledges "The `rich` dependency may add its own ANSI formatting; its
interaction with the tty detection is not fully audited." Rich performs its own
terminal detection and may emit ANSI codes independently of `_paint()`. If
`report.py` or `__main__.py` uses Rich console objects (e.g., for the progress
bar), those may bypass the manual tty gating. This is a minor surface issue,
not a functional bug.

---

## 9. Summary Table

| # | Finding | Severity | Confidence | Affects Gate |
|---|---------|----------|------------|--------------|
| F01 | `tables.py` has no dedicated test file | Medium | HIGH | D4 (measurement) |
| F02 | `corpus_tools.py` minimal test coverage | Low | HIGH | None |
| F03 | Test LOC ratio asymmetric (tapetum undertested at runtime) | Info | HIGH | D1, D6 |
| F04 | CLAUDE.md is accurate but large (maintenance risk) | Low | HIGH | None |
| F05 | Invariant tests cover structure, not behavioral claims | Medium | HIGH | G1 |
| F06 | pyproject.toml is clean | Info | HIGH | G7 |
| F07 | **Uncommitted code undermines audit reproducibility** | **High** | HIGH | All |
| F08 | `ideal_verify.py` is untracked | Medium | HIGH | D5 |
| F09 | score-file/check-facts correctly dispatchable | Info | HIGH | None |
| F10 | Det/LLM reports correctly separated | Info | HIGH | G1 |
| F11 | VLM dead code (788 LOC) | Low | HIGH | None |
| F12 | **Not PR-ready without commit/split/cleanup** | **High** | HIGH | All |
| F13 | Windows handled but not integration-tested | Low | MEDIUM | D8 |
| F14 | Path handling is platform-safe | Info | HIGH | D8 |

---

## 10. Conclusion

The engineering quality is above average for a pre-1.0 tool: strong test
discipline (1406 tests, score pinning, canaries, determinism assertions),
clean packaging, honest documentation, and proper fault isolation. The two
HIGH-severity findings are both related to the audit CONTEXT rather than code
defects: (1) auditing uncommitted code makes findings non-reproducible, and
(2) the codebase needs commit/split work before PR review. The MEDIUM findings
(no `tables.py` test file, invariant tests lack behavioral assertions,
untracked `ideal_verify.py`) are legitimate engineering gaps that do not
invalidate the primary audit conclusions but represent pre-release hardening
work.

No finding in this meta-review contradicts any PASS verdict from C01-C25. The
challenges identify gaps in COVERAGE and PROCESS, not errors in the audited
code's logic or architecture.
