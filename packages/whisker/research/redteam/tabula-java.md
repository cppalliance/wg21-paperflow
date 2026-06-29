# Red-team: whisker guard/calibrate vs tabula-java QA

**Source repo:** `packages/whisker/research/repos/tabula-java` (tabulapdf/tabula-java, shallow read 2026-06-25)

## Summary

- tabula-java gates a **67-PDF ICDAR corpus** with **per-PDF committed JSON baselines** and **16 `expectedFailure:true` monotonic cases**; whisker `guard` matches per-item/per-axis intent but lacks tabula's **explicit expectedFailure bit**, **improvement-must-refresh rule**, and **dual-counter monotonic guard** (recall + false-positive count).
- tabula runs **exact output goldens** (byte-exact CSV/JSON via `assertEquals`) alongside metric baselines; guard diffs only rolled-up `nid/teds/mhs/overall` scalars, so formatting-only regressions and extraction drift invisible to tabula's writer tests still pass guard if metrics hold.
- tabula has **no ROC calibration**; thresholds are fixed ICDAR geometry (`contains` + no intersect). `calibrate.py` is ahead on operating-point fit, but tabula exposes **multi-threshold directional constraints** (correct ≥ baseline AND erroneous ≤ baseline) that guard's single slack drop does not replicate.
- **Concrete whisker bugs:** baseline `axis_slack`/`floors`/`kind` written but not read on diff; duplicate PIDs duplicate findings; known-bad papers that **improve** pass silently (tabula **fails** until JSON refresh); `calibrate_threshold` can emit `fail_edge > review_edge`; NaN/inf samples silently skew ROC.
- **Top portable detail:** adopt tabula's **expectedFailure monotonic triple** (`numCorrectlyDetectedTables >= baseline`, `numErroneouslyDetectedTables <= baseline`, fail if `failed` became false) as an explicit baseline flag + `status_improved_requires_update` in guard.

---

## 1. REGRESSION-GATE GAPS

### 1.1 Per-item committed JSON baselines (metrics-as-snapshots)

tabula stores one baseline JSON per PDF (`us-001.json` beside `us-001.pdf`), loaded at test start (`TestTableDetection.java:58-70`, `:87-89`). Each file records `numExpectedTables`, `numCorrectlyDetectedTables`, `numErroneouslyDetectedTables`, `expectedFailure` (e.g. `us-001.json:1`).

guard writes one committable JSON with all PIDs (`guard.py:136-147`, `__main__.py:361-366`).

**Adopt?** **Already present [PRESENT].** Same per-item snapshot contract; whisker's single-file baseline is easier to diff in PRs.

### 1.2 Per-axis / multi-metric (not corpus mean)

tabula never averages the 67 cases for CI pass/fail; each parameterized PDF is an independent gate (`TestTableDetection.java:104-122`, `:152-283`). Cumulative stats are logged only (`:260-264`).

guard diffs **each paper's each axis** (`guard.py:172-184`, `constants.py:99`).

**Adopt?** **Already present [PRESENT].** Exceeds tabula (guard also tracks `overall` as a fourth regression axis).

### 1.3 Explicit `expectedFailure` monotonic baselines

tabula's core pattern for known-bad cases (`expectedFailure:true`, 16/67 JSON files):

```275:279:packages/whisker/research/repos/tabula-java/src/test/java/technology/tabula/TestTableDetection.java
            if (this.status.expectedFailure) {
                // make sure the failure didn't get worse
                assertTrue("...", this.numCorrectlyDetectedTables >= this.status.numCorrectlyDetectedTables);
                assertTrue("...", this.numErroneouslyDetectedTables <= this.status.numErroneouslyDetectedTables);
                assertTrue("This test used to fail but now it passes! ... Please update the test's JSON file accordingly.", failed);
```

Known-bad stays in corpus; **worsening** fails; **improving to pass** also fails until a human rewrites the JSON (refresh ritual).

guard approximates this implicitly: papers below floor in baseline are not re-flagged if stable (`guard.py:192-197`, `tests/test_guard.py:84-92`). No `expected_failure` field in baseline JSON; a paper at nid=0.91 (above `NID_FLOOR=0.90`) but weak vs baseline cannot be marked known-bad without encoding a low baseline value.

**Adopt?** **Yes [HIGH] [ACTIONABLE-NOW].** Add `"expected_failure": true` per PID in baseline; for those rows: apply monotonic slack on each axis AND emit `status_improved_requires_update` when current metrics beat baseline (mirror `:279`).

### 1.4 Dual-direction monotonic guard (recall + false-positive count)

tabula tracks **two failure modes independently**: missed tables (`numCorrectlyDetectedTables` must not drop) and spurious detections (`numErroneouslyDetectedTables` must not rise) (`:277-278`).

guard only checks **score drops** on `nid/teds/mhs/overall` (`guard.py:172-184`). A regression that **adds hallucinated content** (higher drift, extra blocks) may leave nid unchanged or even improve while quality collapses.

**Adopt?** **Yes [HIGH].** Add at least one **upper-bound axis** in guard (e.g. `extra_regions` count or drift from `WhiskerResult`) with monotonic `<= baseline` for expectedFailure cases, matching tabula's erroneous-table counter.

### 1.5 Floors / absolute backstop

tabula has **no published numeric floor**; pass/fail is exact geometry + baseline comparison. whisker adds `NID_FLOOR`/`TEDS_FLOOR`/`MHS_FLOOR` (`constants.py:56-58`, `guard.py:160-163`, `:185-190`).

**Adopt?** **Keep whisker floors [PRESENT].** Strict improvement over tabula for catastrophic drops without a stale baseline.

### 1.6 Missing / added item detection

tabula discovers PDFs from directory listing (`TestTableDetection.java:110-118`). A PDF **without JSON** gets first-run baseline creation (`:267-272`), not a fail. A PDF **removed** from the directory simply disappears from the suite (no explicit missing-PID fail).

guard **hard-fails** baseline PIDs absent from current corpus (`guard.py:221`, `:113-115`) and passes **new** PIDs as `STATUS_NEW` if above floor (`:165-169`).

**Adopt?** **Partial [MEDIUM].** Missing detection is good (tabula lacks it). Consider **warn/fail on `STATUS_NEW`** until `--update` blesses newcomers (tabula always records first-run JSON; whisker allows silent pass).

### 1.7 Normalization-before-diff

tabula normalizes CSV line endings before golden compare (`UtilsForTesting.java:85`: `(?<!\r)\n` → `\r`). ICDAR detection compares **coordinate geometry** after y-flip (`TestTableDetection.java:190-200`, `:290-293`), citing ICDAR black-box rules (`:290-292`).

guard rounds metrics to 4 decimals at baseline write/compare (`guard.py:144`, `:180`); underlying bench path applies `normalized_text` before NID but guard does not snapshot normalization version.

**Adopt?** **Yes [MEDIUM] [ACTIONABLE-NOW].** Record `schema_version` + metric-normalization revision in baseline; reject diff when schema mismatch. Optional: CRLF/whitespace normalization layer before bench if markdown goldens added.

### 1.8 Tolerance semantics (exact vs slack)

tabula detection is **exact boolean** (errors list empty = pass, `:249`). Unit geometry tests use `1e-5` float tolerance (`TestProjectionProfile.java:81`). No regression slack.

guard uses **`drop > slack`** (strict inequality, `guard.py:181`) with `GUARD_AXIS_SLACK = 0.02` (`constants.py:94`).

**Adopt?** **Keep slack [PRESENT].** whisker metrics are continuous; tabula's exact pass/fail would false-alarm on benign float jitter. Document slack as whisker's equivalent of tabula's geometry rules.

### 1.9 Refresh ritual

tabula first-run **writes JSON inside the test** (`TestTableDetection.java:267-272`); improvement on expectedFailure requires hand-editing JSON (`:279`). No CLI flag; refresh = commit edited `.json`.

guard has explicit **`whisker guard --update`** (`__main__.py:329-331`, `:361-367`).

**Adopt?** **Already present [PRESENT].** Add tabula's **anti-silent-improvement** rule: improvement on expectedFailure must fail until `--update`.

### 1.10 Output golden regression (byte-exact)

tabula gates **extracted CSV/JSON output** against committed goldens (`TestWriters.java:39-46`, `:63-68`; `TestBasicExtractor.java:317-325`). Failures are `assertEquals` string equality.

guard never compares candidate markdown to `<pid>.gt.md`; only metric scalars from `run_bench`.

**Adopt?** **Yes [MEDIUM].** Optional second gate tier: normalized markdown hash or anchor diff per paper (whisker notes practice #3). Out of scope for guard.py alone but tabula proves output goldens catch regressions metrics miss.

### 1.11 Baseline metadata ignored on read

`baseline_from_rows` writes `axis_slack`, `floors`, `kind` (`guard.py:140-142`); `diff_rows` always uses caller `slack` and module `_FLOORS` (`guard.py:62`, `:204-205`, `:161-163`), never `baseline["axis_slack"]` or `baseline["floors"]`. No validation of `kind == whisker-guard-baseline`.

**Adopt?** **Yes [HIGH] [ACTIONABLE-NOW].** Read slack/floors from baseline when present; reject unknown `kind`/`schema_version`.

### 1.12 Statistical vs exact aggregation

tabula prints running corpus counters during the suite (`TestTableDetection.java:260-264`) but **does not gate on them**. whisker `bench --baseline` still gates corpus-mean `overall` (`__main__.py:303-315`); `guard` does not.

**Adopt?** **guard already correct [PRESENT].** Deprecate or document mean-only `bench --baseline` as legacy; tabula never relied on means for CI.

---

## 2. CALIBRATION GAPS

tabula-java **does not calibrate**. Operating rules are fixed: ICDAR region `contains` ground-truth bbox without intersecting other GT regions (`TestTableDetection.java:290-318`); CSV goldens are exact. The "thresholds" are **directional monotonic constraints** on committed counters, not ROC fits.

| Gap | tabula-java evidence | calibrate.py gap | Adopt? |
|-----|---------------------|------------------|--------|
| **Operating-point selection** | N/A (fixed geometry) | max TPR @ FPR≤ceiling, Youden fallback (`calibrate.py:174-180`) | **Keep [PRESENT]** — whisker advantage |
| **Multi-threshold / tiered rules** | Three coupled rules on expectedFailure (`:277-279`) | Single threshold per `calibrate_threshold` call | **Yes [HIGH]:** model fail/review as **ordered band** with monotonic constraints, not independent ROC sweeps |
| **Per-axis calibration** | Separate counters: correct vs erroneous tables | Only `unigram_coverage` (`__main__.py:488-498`) | **Yes [MEDIUM]:** fit `nid/teds/mhs` bench axes from labeled corpus separately |
| **Cross-validation / holdout** | Fixed ICDAR holdout corpus (67 docs) | Single labels file, no split (`calibrate.py:149-185`) | **Yes [MEDIUM]:** hold out PID subset; tabula treats each PDF as permanent holdout item |
| **Class imbalance** | 16/67 expectedFailure (24%) explicitly tracked in JSON | Unweighted counts (`calibrate.py:164-165`) | **Yes [MEDIUM]:** report support; optionally weight by stratum |
| **Ordered band edges (fail ≤ review)** | N/A | fail and review fit independently (`__main__.py:494-498`) | **Yes [HIGH] [ACTIONABLE-NOW]:** enforce `fail_edge <= review_edge` post-fit |
| **False-positive axis calibration** | `numErroneouslyDetectedTables` capped upward (`:278`) | No upper-bound / drift metric in calibration | **Yes [HIGH]:** calibrate drift/extra-content edge separately from coverage |

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Severity | Function | Scenario | tabula lesson |
|----------|----------|----------|---------------|
| **[CRITICAL] [ACTIONABLE-NOW]** | `diff_rows` / `_evaluate_paper` | Known-bad paper **improves** above baseline (e.g. teds 0.50→0.95) | tabula **fails** until JSON updated (`TestTableDetection.java:279`); guard returns `STATUS_OK` (`test_guard.py:84-92`) — silent baseline staleness |
| **[HIGH] [ACTIONABLE-NOW]** | `diff_rows` | `baseline` contains `axis_slack`/`floors`/`kind` but diff uses CLI defaults | tabula always reads per-PDF JSON counters (`:62-63`); whisker metadata is write-only |
| **[HIGH] [ACTIONABLE-NOW]** | `_calibrate_main` | Small corpus: fail fit at 0.88, review fit at 0.92 → inverted band | tabula never inverts rules; independent ROC fits can contradict |
| **[HIGH]** | `diff_rows` | Duplicate `pid` in `rows` | Two `GuardFinding`s; `baseline["rows"]` dict last-wins — tabula is 1:1 PDF:JSON |
| **[HIGH]** | `calibrate_threshold` | Sample value `NaN` or `inf` | Skews sort/partition; tabula uses integer counts, no NaN path |
| **[MEDIUM] [ACTIONABLE-NOW]** | `_evaluate_paper` | Paper stable below floor: `status=ok` but `below_floor` populated (`test_guard.py:92-93`) | tabula separates expectedFailure (known fail) from pass; whisker conflates informational below_floor with ok status |
| **[MEDIUM]** | `diff_rows` | `baseline=None`, corpus run in CI | Every paper judged only against floors; no snapshot regression (tabula always has JSON after first run) |
| **[MEDIUM]** | `_load_corpus_pairs` + guard | New `<pid>.gt.md` added, scores 0.86 nid (above floor) | `STATUS_NEW` passes; tabula first-run would write JSON (`:267-272`) forcing explicit commit |
| **[MEDIUM]** | `calibrate_threshold` | `samples=[]` | Raises only on single-class, not empty list — empty input should fail loudly |
| **[MEDIUM]** | `calibrate_threshold` | All samples same value, mixed labels (tie) | Partition ambiguous; tabula integer counters avoid ties |
| **[LOW]** | `_evaluate_paper` | `prior=0.90`, `cur=0.89999`, slack=0.02 | `round(prior-cur,4)=0.0` passes; tabula exact geometry has no slack cliff |
| **[LOW]** | `_candidate_thresholds` | Single unique value | Returns `[v, v+1.0]` only — degenerate curve with one point |
| **[LOW]** | `run_bench` (guard input) | Paper with no GT tables: `teds=1.0` by convention (`bench.py:128-129`) | tabula still counts `numExpectedTables` from XML (`TestTableDetection.java:169-201`); whisker gives free pass on absent axis |

---

## 4. MISSING AXIS / CHECK

| tabula-java gate | Evidence | whisker equivalent |
|------------------|----------|-------------------|
| **Table detection recall** (`numCorrectlyDetectedTables`) | `TestTableDetection.java:313-314`, `:277` | Partial: `teds` on extracted MD tables, not layout detection |
| **False-positive table count** (`numErroneouslyDetectedTables`) | `:278`, `:328-331` | **Absent** — no guard axis for spurious tables/regions |
| **Exact extraction output** (CSV/JSON) | `TestWriters.java:45-46`, `TestBasicExtractor.java:325` | **Absent** — guard never diffs markdown bytes |
| **Geometric containment quality** | `:297-308` (contains + no intersect) | **Absent** — whisker has no bbox/layout stage |
| **expectedFailure registry** | 16 committed JSON flags | **Absent** — implicit via below-floor baseline only |
| **Improvement detection** | `:279` (must stay failed until refresh) | **Absent** |
| **Unicode / RTL extraction** | `TestSpreadsheetExtractor.java:458-463` (explicit Arabic asserts) | Partial: `normalized_text` CJK fold; no per-script golden gate |

---

## 5. TOP PORTABLE DETAIL

**Adopt tabula's `expectedFailure` monotonic triple** from `TestTableDetection.java:267-279`:

1. Persist per PID: `expected_failure: bool`, baseline axis values, and (for whisker) optional **upper-bound counters** (extra regions / drift).
2. On diff, if `expected_failure`:
   - fail if any gated axis **drops** more than slack (existing `drop > slack`, `guard.py:181`);
   - fail if any **upper-bound axis rises** (port of `numErroneouslyDetectedTables <= baseline`, `:278`);
   - fail if paper **no longer fails** the absolute floor/verdict bar (port of `assertTrue(..., failed)` on improvement, `:279`) until `whisker guard --update`.

This is the single highest-leverage pattern: it keeps 16/67-style weak papers in CI without noise, blocks collateral worsening, and **forces a deliberate baseline bump on fixes** — the one ritual tabula enforces that guard currently skips.

**Exact config to seed:** mirror tabula's counter semantics with whisker constants already in repo: slack `0.02` (`constants.py:94`), floors `nid≥0.90, teds≥0.80, mhs≥0.80` (`constants.py:56-58`), plus new `expected_failure: true` baseline field per known-weak PID.
