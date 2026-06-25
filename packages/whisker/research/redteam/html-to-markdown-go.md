# Red-team: whisker guard/calibrate vs html-to-markdown-go

**Target repo:** `packages/whisker/research/repos/html-to-markdown-go` (14 `.in.html`/`.out.md` goldie pairs, 43 `*_test.go` files, CI matrix Go 1.25–1.26 × ubuntu/macos/windows).

## Summary

- html-to-markdown-go gates on **byte-exact committed markdown** per fixture (`goldie.Assert`, zero tolerance); whisker guard gates on **rounded float metrics** with 0.02 slack — formatting-only regressions that preserve NID/TEDS/MHS pass guard but fail go.
- go **fails every new/changed fixture until `go test -update`**; guard marks new papers `STATUS_NEW` and passes if above floors — no committed output contract for additions.
- go has **no ROC/threshold calibration** (implicit FPR=0 via exact match); calibrate is whisker's advantage, but it cannot substitute for fixture-level exactness on known HTML snippets.
- **[CRITICAL][ACTIONABLE-NOW]** `baseline_from_rows` writes `axis_slack`/`floors` into the baseline JSON but `diff_rows` always reads live `constants.py` and CLI `--slack`, never the committed payload — baseline metadata is decorative.
- **Top portable detail:** goldie `-update` refresh ritual + CI that never runs `-update` (`README.md:387–393`, `.github/workflows/go.yml:31`) plus `.gitattributes * -text` (`plugin/commonmark/testdata/.gitattributes:4`) for cross-platform golden stability.

---

## 1. REGRESSION-GATE GAPS

### [CRITICAL] Byte-exact output snapshot vs fuzzy metric snapshot

**go:** `internal/tester/goldenfiles.go:63–78` converts each `.in.html`, then `goldie.Assert(t, run, []byte(output))` — full markdown compared byte-for-byte; any character change fails.

**guard:** `guard.py:172–184` diffs only `nid`/`teds`/`mhs`/`overall` with slack; output text never enters the gate.

**Adopt?** Partially. Metric guard is correct for WG21 PDF corpus (GT markdown, not HTML fixtures). Add a **small golden-markdown corpus** (practice #2 from cross-repo notes) with exact or normalized-string diff beneath the metric gate for localized, format-sensitive regressions (escaping, table pipes, heading markers). Metric-only guard alone cannot catch regressions visible in go's model.

### [HIGH] Zero tolerance vs per-axis slack

**go:** exact equality; no numeric tolerance anywhere in `goldenfiles.go`.

**guard:** `constants.py:94` `GUARD_AXIS_SLACK = 0.02`; `guard.py:181` `drop > slack`.

**Adopt?** Keep slack for stochastic-free float metrics on large papers, but document that go's implicit tolerance is **0** and whisker's is **±0.02 per axis**. Consider a `--strict` mode (slack=0) for release branches mirroring go's semantics on the golden subset.

### [HIGH] New fixture must fail until blessed; guard passes new papers

**go:** new `.in.html` without matching `.out.md` fails `goldie.Assert` until `go test -update` (`README.md:389–393`).

**guard:** `guard.py:165–169` — no baseline entry → `STATUS_NEW` (passes if floors met).

**Adopt?** Yes. Treat **baseline absence as fail** (or require explicit `STATUS_NEW` allowlist in baseline). go's model prevents silent corpus growth without review; guard's `new` status is a hole for papers added without baseline update.

### [HIGH] Round-trip idempotence gate (HTML→MD→HTML→MD)

**go:** `internal/tester/round_trip.go:87–120` — `bytes.Equal(FirstMarkdown, SecondMarkdown)` after goldmark re-render; enabled via `-round` flag (`goldenfiles.go:14`, `goldenfiles.go:81–95`).

**guard:** no equivalent.

**Adopt?** Yes as optional bench/guard axis for HTML-sourced fixtures (tomd HTML path). Catches normalization drift that preserves GT similarity but breaks stable re-conversion — invisible to one-pass metrics.

### [MEDIUM] Normalization is in the converter, not a pre-diff hook

**go:** collapse/escape/textutils normalize **before** output is frozen as golden (`collapse/collapse_test.go`, `internal/escape/*_test.go`); diff is on canonical output.

**guard:** `bench.py` scores via `normalized_text` internally, but `diff_rows` compares raw float scores computed after normalization — no separate "normalize both sides identically then diff scores" audit trail.

**Adopt?** Partially. Log normalized score inputs in guard report for debugging; ensure any change to `metrics.normalized_text` triggers baseline refresh policy (go would force `-update` on every golden).

### [MEDIUM] Fixture-directory hygiene (orphan file detection)

**go:** `goldenfiles.go:33–34` errors on any file in `testdata/GoldenFiles/` that is not `.in.html` or `.out.md`; `goldenfiles.go:27–28` errors on subdirectories.

**guard:** `_load_corpus_pairs` (`__main__.py:252–260`) silently ignores non-`*.gt.md` files; no orphan/unpaired detection.

**Adopt?** Yes [ACTIONABLE-NOW]. Fail if corpus dir contains unexpected files or `*.gt.md` without scorable candidate (already warns-skip, but doesn't fail the run).

### [MEDIUM] Missing-item detection asymmetry

**go:** removing `.in.html` **silently drops** a test case (no explicit "missing fixture" fail); only `.out.md`-without-`.in.html` is skipped at listing (`goldenfiles.go:30–31`).

**guard:** `guard.py:221` hard-fails on baseline PIDs absent from current run — **stronger** than go.

**Adopt?** Keep guard behavior; optionally add go-style **added `.out.md` without `.in.html`** detection for corpus hygiene.

### [MEDIUM] Cross-platform golden stability (line endings)

**go:** `plugin/commonmark/testdata/.gitattributes:4` `* -text`; `convert_test.go:59–101` explicit `\r\n` collapse tests.

**guard:** no CRLF normalization on corpus paths or metric inputs; JSON baselines may differ if hand-edited on Windows (`__main__.py:372` utf-8-sig helps BOM only).

**Adopt?** Yes for committed baselines: document LF-only + gitattributes on `whisker-guard-baseline.json` and GT corpus.

### [LOW] CI never runs refresh; explicit human ritual

**go:** `.github/workflows/go.yml:31` `go test ./...` (no `-update`); refresh documented `README.md:389`.

**guard:** `__main__.py:361–367` `--update` exits 0, never run in CI by convention.

**Adopt?** Already aligned. Enforce in CI: fail if `--update` would change baseline (dry-run diff job).

### [LOW] Known-bad / expectedFailure monotonic baselines

**go:** none — every golden must pass exactly today.

**guard:** `guard.py:84–92`, `test_guard.py:84–92` — papers below floor in baseline are not re-flagged unless they worsen.

**Adopt?** Keep — whisker ahead of go here (tabula-java pattern). go would force `-update` on any known-weak output.

### [LOW] Statistical vs exact

**go:** exact only.

**guard:** deterministic floats + slack; no sampling.

**Adopt?** Keep determinism; do not add statistical tolerance without measured variance (whisker scores are deterministic per `CLAUDE.md`).

---

## 2. CALIBRATION GAPS

html-to-markdown-go has **no threshold calibration, ROC, or class labels** — quality is implicit: **100% precision, 0% tolerated deviation** on committed goldens.

### [HIGH] calibrate optimizes fuzzy coverage FPR; go enforces exact-output FPR=0 on fixtures

**go:** any output change fails (`goldenfiles.go:78`).

**calibrate:** `calibrate.py:149–180` sweeps `unigram_coverage` with `target_fpr=0.05` default.

**Gap:** calibrate cannot replicate fixture-level certainty. A fitted edge at 5% FPR accepts 1/20 good papers wrong — go accepts 0/N.

**Adopt?** Use calibrate for **unlabeled/scored corpus** edges only; keep exact golden subset outside ROC (complementary, not replacement). Consider `target_fpr=0.0` mode for golden-equivalent subsets.

### [MEDIUM] No multi-threshold / multi-config calibration

**go:** `commonmark_test.go:44–223` `TestOptionFunc` — separate expected output per option permutation (29+ inline cases); each is an independent exact threshold at equality.

**calibrate:** single scalar edge per `calibrate_threshold` call; no option dimension.

**Adopt?** If tomd gains scored option flags, calibrate per-flag or use stratified labels — go shows option matrix is first-class.

### [MEDIUM] No cross-validation / holdout

**go:** all 14 goldens always run in CI (`.github/workflows/go.yml:31`).

**calibrate:** fits in-sample on all labels; no k-fold.

**Adopt?** Add holdout reporting before promoting edges to `constants.py` (field blind spot, but go's full-corpus run is implicit "no holdout" too — still worth adding for whisker labels).

### [LOW] Class imbalance

**go:** N/A (no classes).

**calibrate:** `calibrate.py:164–168` rejects empty class; no weighting for imbalanced labels.

**Adopt?** Optional weighted TPR or minimum per-class counts when label set is skewed.

### [LOW] Per-axis calibration

**go:** each plugin (commonmark, table, strikethrough) has isolated golden sets — implicit per-axis gating.

**calibrate:** only `unigram_coverage` (`__main__.py:490–498`); no ROC for `nid`/`teds`/`mhs`.

**Adopt?** Later: per-axis ROC for bench metrics when labeled bad/good exists per axis.

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Severity | Function | Scenario | Expected fool/break behavior |
|----------|----------|----------|------------------------------|
| **[CRITICAL][ACTIONABLE-NOW]** | `diff_rows` | Baseline JSON has `"axis_slack": 0.05` or edited `"floors"` | Ignored — always uses CLI `--slack` default and `constants.py` `_FLOORS` (`guard.py:155`, `guard.py:214–217`; baseline writes at `guard.py:141–142`). Slack/floor edits in committed baseline have no effect. |
| **[CRITICAL][ACTIONABLE-NOW]** | `_evaluate_paper` | Baseline stores `round(v,4)` (`guard.py:144`); current `cur` is full-precision `BenchRow` float | Asymmetric compare: e.g. baseline `0.9700` from stored round, current `0.96995` — drop rounds to `0.0001` (pass) vs true drop `0.00005`. Boundary flips near slack. |
| **[HIGH][ACTIONABLE-NOW]** | `diff_rows` | `baseline` dict missing `"kind"`/`"schema_version"` or wrong shape | `baseline.get("rows", {}) or {}` (`guard.py:214`) → empty baseline → all papers judged as new/floors-only; silent weakening. go errors on missing goldens (`goldenfiles.go:50–52`). |
| **[HIGH]** | `_evaluate_paper` | `axes[axis]` is `NaN` (bench failure propagated) | `NaN < floor` → False; `round(prior - NaN, 4)` → NaN; `NaN > slack` → False → **status ok**, silent pass. |
| **[HIGH]** | `diff_rows` | Duplicate `pid` in `rows` | Two `GuardFinding` entries same pid; no dedup/ error (`guard.py:216–218`). go fixture names are unique by filesystem. |
| **[MEDIUM][ACTIONABLE-NOW]** | `_evaluate_paper` | Existing paper below floor but stable vs baseline | `below_floor` populated but `status == ok` (`guard.py:160–163`, `196–197`). go fails exact output regardless. Intentional monotonic model, but **current** below-floor on previously-above-floor paper only caught via `crossed_floor` path (`guard.py:185–190`), not `below_floor` alone. |
| **[MEDIUM]** | `calibrate_threshold` | All samples same value, mixed labels e.g. `(0.85, True), (0.85, False)` | At every threshold, TP and FP move together; Youden fallback (`calibrate.py:178–180`); arbitrary tie-break. go would fail both classes on identical output. |
| **[MEDIUM]** | `calibrate_threshold` | `NaN`/`inf` in sample values | `value < threshold` → False for NaN; inflates TN, depresses FPR — bogus operating point. |
| **[MEDIUM]** | `_load_labeled_samples` | Duplicate `pid` in labels JSON | Last record wins silently; no error (`__main__.py:442–452`). |
| **[LOW]** | `diff_rows` | Empty `rows`, empty baseline | `report.failed == False` (`guard.py:112–115`). CLI pre-checks pairs (`__main__.py:354–356`) but library API allows vacuous pass. |
| **[LOW]** | `calibrate_threshold` | Single sample per class (n=2) | Runs but TPR/FPR are 0 or 1 only; overfit edge. go avoids with 14+ fixtures minimum. |
| **[LOW]** | `_candidate_thresholds` | Empty `values` after filter | Returns `[]` (`calibrate.py:131–132`); would raise on empty curve if reachable past class check. |

---

## 4. MISSING AXIS / CHECK (go gates, whisker has no equivalent)

| Tag | go check | Evidence | whisker gap |
|-----|----------|----------|-------------|
| **[CRITICAL]** | Full markdown byte-exact output | `goldenfiles.go:78` | No output snapshot diff; only metric baselines |
| **[HIGH]** | Round-trip idempotence MD→HTML→MD | `round_trip.go:115–120`, flag `goldenfiles.go:14` | Not in guard/bench/calibrate |
| **[HIGH]** | Per-element escaping regression | 8 files under `internal/escape/*_test.go` | No per-construct escape anchors |
| **[HIGH]** | Option/config permutation matrix | `commonmark_test.go:44–223` | Single scoring config per run |
| **[MEDIUM]** | DOM/collapse intermediate representation | `collapse_test.go:22–27`, `dom_representation.go:11–18` | No per-stage intermediate goldens (tomd-side) |
| **[MEDIUM]** | Plugin-isolated golden suites | `plugin/table/table_test.go:14–27`, strikethrough, commonmark each own `testdata/GoldenFiles/` | Single aggregate bench row per paper |
| **[MEDIUM]** | Windows `\r\n` input normalization | `convert_test.go:59–101` | No explicit CRLF corpus case in guard fixtures |
| **[MEDIUM]** | Config validation error contract | `validation.go:41–100`, `validation_test.go:58–87` | guard doesn't validate baseline schema/kind |
| **[LOW]** | Concurrency/race safety | `convert_test.go:104–163` (500 goroutines) | N/A for deterministic whisker scoring |
| **[LOW]** | `-race` in CI | `.github/workflows/go.yml:31` | pytest guard tests only; no race scope |

---

## 5. TOP PORTABLE DETAIL

**Adopt:** **goldie refresh ritual + CI non-update + gitattributes line-ending lock**

```text
# Developer refresh (NEVER in CI):
go test -update          # goldenfiles.go via goldie; rewrites *.out.md

# CI gate (.github/workflows/go.yml:31):
go test ./... -v -race   # no -update → any golden drift fails build

# Cross-platform golden stability (plugin/commonmark/testdata/.gitattributes:4):
* -text                  # prevent CRLF mutation of committed goldens on Windows
```

**Whisker mapping [ACTIONABLE-NOW]:**

1. `whisker guard --update` already mirrors refresh (`__main__.py:361–367`) — add CI job: run guard **without** `--update`, fail on diff vs committed baseline (same contract as go).
2. Add `.gitattributes` `* -text` on committed `guard-baseline.json` and `*.gt.md` corpus.
3. Document in guard header: **CI must never pass `--update`** (parallel `README.md:393`).

Exact-match formula from go (for optional golden tier): `fail iff convert(input) != committed_bytes` — zero slack, zero FPR on that subset. This is the single practice that most directly closes the "collateral damage" blind spot go solves and metric-only guard cannot.
