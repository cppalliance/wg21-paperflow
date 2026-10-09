# 28 - The Regression-Guard Reviewer

**Verdict:** usable-with-conditions — all seven Tier-1 redteam fixes are present in the current code and unit-tested; the per-paper gate is trustworthy on a frozen GT corpus with explicit `--update`/`--fail-on-new` CI wiring, but default-off new-paper admission and newly-eligible axes below floor still slip through on existing baseline rows.
**Confidence:** high

## Findings

- [HIGH] **Tier-1 fix #1 VERIFIED: baseline `axis_slack` and `floors` are authoritative; CLI override only when explicit.** Evidence: embedded at write time (`guard.py:239-240`); read via `_resolve_slack` (`guard.py:320-327`) and `_resolve_floors` (`guard.py:307-317`); applied in `diff_rows` (`guard.py:425-426`); CLI passes `slack=args.slack` only when `--slack` set (`__main__.py:358-364`, `421`); `test_guard.py:138-167` proves embedded slack/floors beat live constants. Impact: committed baselines remain reproducible if `constants.py` moves later.

- [HIGH] **Tier-1 fix #2 VERIFIED: non-finite axis values hard-fail `STATUS_INVALID`.** Evidence: `_evaluate_paper` rejects any non-`None` non-finite axis before comparisons (`guard.py:346-349`); `_finite` helper (`guard.py:135-136`); baseline load rejects non-finite stored metrics (`guard.py:301-304`); mirror in `calibrate_threshold` (`calibrate.py:170-172`); tests `test_guard.py:191-205`, `test_calibrate.py:100-106`. Impact: NaN/inf can no longer silently pass via `x < floor` being False.

- [HIGH] **Tier-1 fix #3 VERIFIED: inverted fail/review band is surfaced, not silently shipped.** Evidence: independent fits in `_calibrate_main` (`__main__.py:833-838`); ordering check + warning (`__main__.py:849-855`); `edge_ordering_ok` recorded in payload (`__main__.py:861`). Impact: overlapping label JSON cannot produce a promoted band with fail stricter than review without a human seeing the warning. Gap: CLI still exits 0 (`__main__.py:883-885`) even when `edge_ordering_ok` is false — informational only, matching "never silently ships" but not fail-closed.

- [MED] **Tier-1 fix #4 VERIFIED: baseline `kind` and `schema_version` validated before diff.** Evidence: `_validate_baseline` (`guard.py:258-271`); invoked from `diff_rows` (`guard.py:418-419`); tests `test_guard.py:170-181`. Impact: bench leaderboards and stale schema-1 artifacts cannot be mistaken for guard baselines (`00` §3b stale schema-1 report).

- [MED] **Tier-1 fix #5 VERIFIED: duplicate PIDs raise `ValueError`, no last-win.** Evidence: `_require_unique_pids` (`guard.py:214-224`); called from `baseline_from_rows` (`guard.py:234`) and `diff_rows` (`guard.py:417`); test `test_guard.py:208-213`. Impact: conflicting scores for one paper cannot hide behind dict comprehension last-win.

- [MED] **Tier-1 fix #6 VERIFIED: `target_fpr` range-checked in [0, 1].** Evidence: `calibrate_threshold` (`calibrate.py:167-168`); parametrized tests `test_calibrate.py:93-97`. Impact: nonsense FPR ceilings cannot corrupt ROC selection.

- [MED] **Tier-1 fix #7 VERIFIED: symmetric 4dp rounding before all guard comparisons.** Evidence: `_NDIGITS = 4` (`guard.py:117`); baseline write rounds (`guard.py:243`); current axes rounded in `cur_axes` before floor/regression (`guard.py:351-354`); drop also rounded (`guard.py:375`); slack-boundary test `test_guard.py:60-65`. Impact: IEEE boundary flicker between stored baseline and live `BenchRow` is bounded. Residual: no meta-test for `prior=0.9700` stored vs `cur=0.96995` adversarial pair; `prior` is not re-rounded at read time if a baseline is hand-edited off-grid (`guard.py:372` uses raw stored `prior`).

- [MED] **`STATUS_NEW` passes by default; `--fail-on-new` is opt-in (Tier-2, implemented).** Evidence: new paper above floors returns `STATUS_NEW` (`guard.py:363-367`); only fails when `fail_on_new` (`guard.py:182-185`, `396-402`); CLI flag (`__main__.py:367-368`, wired `421`); test `test_guard.py:216-222`. Impact: CI that runs `whisker guard` without `--fail-on-new` admits any new corpus member above floors without an explicit `--update` acknowledgement — pandoc-style fail-closed on corpus growth requires deliberate wiring.

- [MED] **Null-axis skipping works for symmetric ineligibility; newly-eligible axis below floor on an existing row can false-pass.** Evidence: regression loop skips when `prior is None or cur is None` (`guard.py:370-374`); floor breach is recorded in `below_floor` (`guard.py:358-361`) but status for existing papers is driven only by `regressions`/`crossed` (`guard.py:387-392`), not `below_floor`; tests cover symmetric null skip (`test_guard.py:275-294`) but not `prior=None, cur=0.55`. Impact: if GT gains tables/headings and baseline is not `--update`d, a baselined paper can score `teds=0.55` (below `TEDS_FLOOR=0.80`, `constants.py:56`) and still roll up `status=ok` — real table quality loss masked until baseline refresh.

- [LOW] **`--fail-on-new` and symmetric rounding lack CLI/integration regression nets.** Evidence: guard logic unit-tested (`test_guard.py:216-222`); no test imports `whisker.__main__` or subprocesses `whisker guard --fail-on-new` (`16-test-suite-auditor.md` HIGH on CLI); calibrate `edge_ordering_ok` path untested (`test_calibrate.py` stops at library). Impact: Tier-1 library fixes hold today; the shipped command surface could regress without CI catching it.

- [LOW] **`content_recall` is a first-class guard axis but has no dedicated regression test.** Evidence: in `_FLOORS` and `C.GUARD_REGRESSION_AXES` (`guard.py:105-110`, `constants.py:67`, `109`); `_row` test helper omits it (`test_guard.py:22-25`); no test asserts `content_recall` floor cross or slack regression. Impact: once Lane 2 corpus exists (`00` §4), a dropped-section regression on recall could slip until someone adds a test — nid/teds/mhs paths are covered.

## False-pass hypothesis

Baselined paper **P1** with committed `teds: null` (GT had no tables at last `--update`). GT is amended to include tables; re-run scores `teds=0.55`. Guard: regression skipped (`guard.py:373-374`), `below_floor` lists `teds 0.550 < floor 0.8` (`guard.py:358-361`), status stays **`ok`** (`guard.py:387-392`). Whisker guard passes while table fidelity is materially below the published floor.

## False-fail hypothesis

CI enables `--fail-on-new` on a growing corpus: a legitimately new paper with all axes above floors receives **`STATUS_NEW`** and fails (`guard.py:363-367`, `182-185`) until someone runs `--update`. That is intentional fail-closed semantics, not a metric false fail. Separately, a known-weak baselined paper stable below floor passes by design (`test_guard.py:89-97`, tabula monotonic model) — informational `below_floor` only.

## What would change my mind

A guard integration test (or one `_evaluate_paper` unit test) proving **`prior=None`, `cur` below floor on an existing pid → hard fail** (or documenting that GT corpus edits always require `--update` and enforcing it in CI with `--fail-on-new`), plus a CI recipe that runs `whisker guard --fail-on-new` on the committed baseline, would flip this to **usable** unconditionally.
