# Opus C - Engineering Quality Meta-Review

**Domain:** Determinism, CI, security, license, performance, error-handling, tests, regression guard.
**Method:** Independent code inspection + grep + test run (353 passed, 1.67s) against live repo on 2026-06-25.

## Claim verification

| # | Claim (source persona) | Verdict | Evidence |
|---|---|---|---|
| 1 | GPL `levenshtein` fully removed from production code (P12) | **CONFIRMED** | `grep '^import Levenshtein\|^from Levenshtein' packages/whisker/src/whisker/` = zero hits. All three usages (`metrics.py:41`, `match.py:37`, `facts.py:42`) import `from rapidfuzz.distance import Levenshtein as _Lev`. `pyproject.toml` has no `levenshtein` entry. `test_edit_distance_parity.py:56-70` lint-bans the GPL import in `src/whisker/*.py`. |
| 2 | Tier-1 fix #1: baseline slack/floors read from baseline (P28) | **CONFIRMED** | `_resolve_slack` (`guard.py:320-327`) and `_resolve_floors` (`guard.py:307-317`) read from baseline dict, fallback to constants. `test_guard.py:138-167` proves embedded slack/floors override live constants. |
| 3 | Tier-1 fix #2: NaN/inf hard-fail STATUS_INVALID (P28) | **CONFIRMED** | `guard.py:346-349` checks `_finite()` on all axes. `calibrate.py:170-172` rejects non-finite samples. Tests: `test_guard.py:191-205`, `test_calibrate.py:100-106`. |
| 4 | Tier-1 fix #3: inverted band surfaced in calibrate (P28) | **CONFIRMED** | `__main__.py:849-855` checks `fail_edge <= review_edge`, logs warning, records `edge_ordering_ok` in payload. Gap: still exits 0. |
| 5 | Tier-1 fix #4: baseline kind/schema validated (P28) | **CONFIRMED** | `_validate_baseline` (`guard.py:258-271`) checks `kind == GUARD_BASELINE_KIND` and `schema_version == WHISKER_SCHEMA_VERSION`. `test_guard.py:170-181`. |
| 6 | Tier-1 fix #5: duplicate PIDs raise ValueError (P28) | **CONFIRMED** | `_require_unique_pids` (`guard.py:214-224`), called from both `baseline_from_rows` and `diff_rows`. `test_guard.py:208-213`. |
| 7 | Tier-1 fix #6: target_fpr range-checked (P28) | **CONFIRMED** | `calibrate.py:167-168` validates `0.0 <= target_fpr <= 1.0`. `test_calibrate.py:93-97`. |
| 8 | Tier-1 fix #7: symmetric 4dp rounding (P28) | **CONFIRMED** | `_NDIGITS = 4` at `guard.py:117`. Baseline write rounds (`guard.py:243`), current axes rounded (`guard.py:351-354`), drop rounded (`guard.py:375`). `test_guard.py:60-65` boundary test. |
| 9 | Per-paper scoring is deterministic (P04) | **CONFIRMED** | Pure function chain: `score_paper` -> `check_paper_content` -> `run_gates` -> `_decide`. No RNG, no set iteration into output, no network. Flags sorted (`score.py:111-112`). Report sorted by pid (`report.py:89`). |
| 10 | `--json` stdout array not pid-sorted (P04) | **CONFIRMED** | `__main__.py:253`: `[r.to_dict() for r in results]` uses `results` in scoring order. `build_report` sorts by pid (`report.py:89`) but `--json` path does not. |
| 11 | `list_all_paper_ids()` has no ORDER BY (P04) | **CONFIRMED** | `sqlite_backend.py:763`: `SELECT paper_id FROM papers` bare, no `ORDER BY`. |
| 12 | CLI surface (~794 LOC) entirely untested (P16) | **CONFIRMED** | `grep '__main__' packages/whisker/tests/` = zero hits. No test imports `whisker.__main__` or asserts subprocess exit codes. |
| 13 | Errored papers do not affect exit code (P15, P09) | **CONFIRMED** | `__main__.py:210-215` catches `Exception`, increments `errored`, continues. `_verdict_exit_code` at line 267 only inspects `[r.verdict for r in results]`. No check on `errored > 0`. |
| 14 | `_decide` has no NaN guard on unigram_coverage (P15) | **CONFIRMED** | `score.py:156` uses `unigram_coverage < C.UNIGRAM_COVERAGE_FAIL_EDGE` with no `math.isfinite` check. In Python, `NaN < 0.85` is `False`, so NaN coverage would skip both hard and soft flags and could PASS. Guard lane (`guard.py:346-349`) is hardened; score lane is not. |
| 15 | `content_recall` guard axis has no dedicated regression test (P28, P16) | **CONFIRMED** | `test_guard.py:261-266` `_ineligible_row` has `content_recall` param but no test asserts a `content_recall` floor crossing or slack regression. All floor/regression tests use `nid`/`teds`/`mhs` only. |
| 16 | Block-matrix budget fallback untested (P14, P16) | **CONFIRMED** | `grep 'BLOCK_MATRIX_CELL_BUDGET' packages/whisker/tests/` = zero hits. `match.py:253-255` fallback path has no test coverage. |
| 17 | `qa_score` / `uncertain_count` soft-flag branches untested (P16) | **CONFIRMED** | `grep 'qa_score\|uncertain_count\|mojibake\|table_parse\|lossy_table' packages/whisker/tests/` = zero hits. Two CLAUDE.md-listed soft signals are dead code from a test perspective. |
| 18 | Apache-2.0 verbatim ports lack NOTICE file (P12) | **CONFIRMED** | No `NOTICE`, `THIRD_PARTY_NOTICES`, or `LICENSE` file under `packages/whisker/`. `metrics.py:394-399` documents TEDS as a verbatim port of OmniDocBench (Apache-2.0) with only a source-comment citation, no redistributed license text. |
| 19 | GPL lint only scans import lines, not pyproject.toml (P12) | **CONFIRMED** | `test_edit_distance_parity.py:58-66` scans `src/whisker/*.py` for import lines only. Does not inspect `pyproject.toml` or `uv.lock`. |
| 20 | Default oracle ~5-12x slower than `--no-reference` (P14) | **PARTIALLY** (accepted claim, not independently timed) | Architecture confirms: `reference.py:64` runs markitdown per paper; `score.py:212-214` adds full-doc `text_nid` + `table_score` + `mhs` on oracle output. Baseline §3a reports 86.1s ref-free for 382 papers. Cannot independently time without running `--all`. |
| 21 | Null-axis newly-eligible below floor can false-pass on existing row (P28) | **CONFIRMED** | `guard.py:370-374`: regression loop skips when `prior is None or cur is None`. Floor breach goes to `below_floor` list (`guard.py:358-361`) but status for existing papers is driven only by `regressions`/`crossed` (`guard.py:387-392`), not `below_floor`. |

## Real bugs vs nits

### Real bugs (affect correctness, CI safety, or compliance)

1. **[HIGH] NaN unigram_coverage can false-pass in score path.** `score.py:156` has no `math.isfinite` guard. A corrupt `check_paper_content` returning NaN coverage would produce a PASS verdict (NaN < 0.85 is False, NaN < 0.95 is False, so no flag fires). Guard lane has the fix (`guard.py:346-349`); score lane does not. This is a real gap between the two paths.

2. **[HIGH] Errored papers invisible to CI exit code and JSON output.** `__main__.py:210-215,267`: a paper that throws during `score_paper` is skipped, but `_verdict_exit_code` only inspects scored verdicts. CI checking exit code alone can pass while papers failed to score. `--json` omits errored papers entirely (`__main__.py:253`). Stale sidecars from a previous PASS run persist on disk.

3. **[HIGH] CLI surface entirely untested.** 794 LOC including exit-code contract, gate wiring, batch `--all`, `--no-write`, anchor/fact conjunctive checks. Zero test imports or subprocess assertions. All 7 Tier-1 fixes are unit-tested in library modules but not through the command users actually run.

4. **[MED] GPL lint gap: pyproject.toml not checked.** `test_edit_distance_parity.py:56-70` only scans Python import lines. Re-adding `levenshtein` to `pyproject.toml` would pass all 353 tests while reintroducing GPL at install time.

5. **[MED] Null-axis newly-eligible below floor false-pass.** A baselined paper with `prior=None` (no tables in GT) gaining `cur=0.55` (tables now present, badly scored) stays `status=ok` because floor breach is informational only for existing rows. The guard silently passes table quality below `TEDS_FLOOR=0.80`.

6. **[MED] Apache-2.0 attribution gap.** Verbatim ports from OmniDocBench/PubTabNet (TEDS, match_quick, text normalizers) have source-comment citations but no redistributed Apache-2.0 license text. Not a copyleft blocker, but a compliance gap for wheel/sdist distribution.

### Style nits (non-blocking, good-to-fix)

1. **[LOW] `--json` array order not pid-sorted.** `__main__.py:253` emits results in scoring order; `build_report` sorts. Machine consumers should key by pid, not array index. A one-line `sorted()` fix.

2. **[LOW] `list_all_paper_ids()` no ORDER BY.** Stable on current data but not guaranteed across VACUUM/rebuild. Affects `--all` iteration order only; sidecars and `report.json` are sorted independently.

3. **[LOW] `qa_score`/`uncertain_count` soft-flag branches untested.** These exist in `_decide` (`score.py:170-173`) and fire on real data (6 qa, 30 uncertain in baseline §3a), but have zero test coverage. Regressions would be silent.

4. **[LOW] Block-matrix budget fallback untested.** `match.py:253-255` fallback changes metric semantics (block NID -> whole-doc NID, `reading_order=0.0`) on 13+ real papers. No test pins this behavior.

5. **[LOW] Stale research docs still reference GPL `levenshtein`.** `research/buildvsbuy/text-edit-distance.md:25` prescribes the old dependency. Misleading but does not affect runtime.

## My independent verdict

**Verdict: usable-with-conditions**
**Confidence: high**

The engineering is significantly above average for a QA tool at this maturity level. The 7 Tier-1 redteam fixes all hold in both library code and tests. Determinism is genuine: pure functions, sorted outputs, no RNG/set-order leakage. The license swap from GPL `levenshtein` to MIT `rapidfuzz` is verified complete in production code (though the lint guard has a manifest-level gap). The test suite (353 tests, 1.67s) provides strong regression coverage of metric math, guard diff logic, and threshold wiring.

The conditions are:

1. **CI must check errored count, not just exit code.** The batch firewall (`__main__.py:210-215`) swallows scorer exceptions and exit code only reflects scored verdicts. A broken paper vanishes from the rollup.
2. **Score-path NaN guard is missing.** Unlike the guard lane (hardened at Tier-1 fix #2), the default `whisker --all` score path has no `math.isfinite` check on `unigram_coverage`, allowing a corrupt NaN to false-pass.
3. **CLI integration tests do not exist.** The entire command surface (exit codes, gate modes, `--no-write`, `--json`) has zero test coverage.

These are fixable in a few hours. The underlying metric math, guard logic, and calibration framework are sound.

## Top-3 issues

1. **Errored papers are CI-invisible.** A paper that throws during scoring is logged and skipped, but exit code stays driven by scored papers only. `--json` omits it. Stale sidecars persist. Fix: non-zero exit when `errored > 0` (or a separate exit code), and include `errored`/`skipped` pids in JSON output.

2. **Score-path NaN false-pass.** `score.py:156` compares `unigram_coverage < 0.85` without a `math.isfinite` guard. NaN comparisons are always False in Python, so NaN coverage silently passes. Fix: add `if not math.isfinite(unigram_coverage): hard.append(...)` before the threshold check, mirroring `guard.py:346-349`.

3. **No CLI integration tests.** 794 LOC of CLI logic (exit codes, gate wiring, batch iteration, anchor/fact conjunctive checks) is untested through the command surface. All Tier-1 fixes are tested at the library level but not through `__main__`. Fix: subprocess tests asserting exit 0/1/3/5 for pass/review/fail/missing-pid fixtures.
