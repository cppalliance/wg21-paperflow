# Red-team: whisker guard/calibrate vs pdf-to-markdown

**Target repo:** `packages/whisker/research/repos/pdf-to-markdown` (v0.1.3, 12-stage JS pipeline, 4 mocha spec files, no CI config, no committed goldens).

## Summary

- pdf-to-markdown has **no automated regression gate at all** (no goldens, no baseline JSON, no GitHub Actions; `package.json:11-12` is lint+mocha only) — whisker guard/calibrate are already ahead on CI plumbing; this repo's lesson is **what manual-only QA looks like** and which signals it uses that guard ignores.
- The repo's real QA asset is a **12-transform replay debugger** (`AppState.jsx:53-67`, `DebugView.jsx:83-89`) with **per-stage count messages** and **annotation-filtered diffs** (`PageView.jsx:20-22`, `DetectHeaders.jsx:118-120`) — guard diffs only four terminal floats and cannot localize which pipeline stage broke.
- Hardcoded fuzzy thresholds exist but are **never corpus-calibrated**: TOC headline link `wordMatch >= 0.5` (`DetectTOC.jsx:276-277`), repetitive header/footer quorum `Math.max(3, pages.length * 2 / 3)` (`RemoveRepetitiveElements.jsx:77-78`), list/headline heuristics — parallel to whisker's provisional `constants.py` edges, not to `calibrate.py`'s ROC fit.
- **[CRITICAL][ACTIONABLE-NOW]** `baseline_from_rows` writes `axis_slack` and `floors` into the baseline JSON (`guard.py:141-142`) but `diff_rows`/`_evaluate_paper` always read live `constants.py` and CLI `--slack` (`guard.py:62,205,161-162`) — committed baseline metadata is decorative; threshold drift in `constants.py` silently invalidates old baselines.
- **Top portable detail:** `wordMatch` set-overlap formula `intersection.size / Math.max(words1.size, words2.size)` with uppercase tokenization (`stringFunctions.jsx:112-118`) plus the **`>= 0.5` operating point** for TOC headline recovery (`DetectTOC.jsx:276-277`), unit-tested at `stringFunctions.spec.js:182-193`.

---

## 1. REGRESSION-GATE GAPS

### [CRITICAL] No committed output or metric snapshot (repo baseline is manual-only)

**pdf-to-markdown:** Zero end-to-end PDF fixtures, zero expected markdown, zero metric baselines. `npm run test` (`package.json:11`) runs only helper unit specs (`test/stringFunctions.spec.js`, `test/HeadlineFinder.spec.js`, `test/models/StashingStream.spec.js`). Final markdown is rendered once in `ResultView.jsx:23-40` with no assertion.

**guard.py:** Per-paper, per-axis metric baseline with `--update` refresh (`guard.py:136-147`, `__main__.py:361-367`).

**Adopt?** **No** (whisker already has what this repo lacks). Use pdf-to-markdown as a **negative control**: shipping a converter with only unit tests and a debug UI is exactly the blind spot guard was built to close.

---

### [HIGH] Per-stage intermediate regression (12 transforms, not one terminal score)

**pdf-to-markdown:** Pipeline is explicit and stepped (`AppState.jsx:53-67`): CalculateGlobalStats → CompactLines → RemoveRepetitiveElements → VerticalToHorizontal → DetectTOC → DetectHeaders → DetectListItems → GatherBlocks → DetectCodeQuoteBlocks → DetectListLevels → ToTextBlocks → ToMarkdown. `DebugView.jsx:83-89` replays transforms `0..N`, and each stage emits **`ParseResult.messages` count strings** (e.g. `'Detected ' + detectedHeaders + ' headlines.'` at `DetectHeaders.jsx:118-120`; list counts at `DetectListItems.jsx:55-58`; header/footer removal at `RemoveRepetitiveElements.jsx:93-96`).

**guard.py:** Scores terminal `BenchRow` only (`bench.py:149-166`); no stage index, no stage counters in baseline.

**Adopt?** **Yes, partially (tomd-side).** Snapshot per-stage counters (headlines detected, list items, headers removed) alongside metric rows. A TEDS drop with unchanged `DetectHeaders` message implicates table extraction, not heading heuristics. Out of scope for guard.py alone but guard's baseline schema should reserve a `stages` dict when tomd exposes hooks.

---

### [HIGH] Modification-only / annotation-level diff (not full-text rescore)

**pdf-to-markdown:** Transformations annotate items (`Annotation.jsx:11-34`: Added/Removed/Detected/Modified). `PageView.jsx:20-22` filters to `block.annotation` when `modificationsOnly` is set; `LineItemTable.jsx:38-40` colors annotated rows. `ToLineItemTransformation.jsx:31-38` commits removals via `REMOVED_ANNOTATION` cleanup between stages.

**guard.py:** Reports axis deltas as strings (`guard.py:182-184`) but no item-level change set; cannot answer "which lines changed."

**Adopt?** **Yes as follow-on.** Store optional `{annotations_added, annotations_removed}` counts per paper in baseline, or wire whisker's existing `missing_regions`/`extra_regions` from the per-paper score path into guard findings.

---

### [HIGH] Per-page granularity within a document

**pdf-to-markdown:** `DebugView.jsx:125-140` paginates per page; regressions in multi-page PDFs are inspected page-by-page. `RemoveRepetitiveElements.jsx:39-71` computes header/footer hashes **per page** before corpus-wide quorum.

**guard.py:** One `GuardFinding` per `pid` (`guard.py:76-88`); no page index axis.

**Adopt?** **Partially.** WG21 papers are often single-flow markdown; per-page guard matters when tomd emits page breaks. Low priority unless bench gains page-stratified metrics.

---

### [HIGH] Normalization-before-compare at match site (not just inside metric)

**pdf-to-markdown:** `HeadlineFinder.jsx:6,13` normalizes via `normalizedCharCodeArray` (uppercase, strip whitespace/tab/dot — `stringFunctions.jsx:48-52`) **before** char-by-char match. `RemoveRepetitiveElements.jsx:61-62` hashes `toUpperCase()` text ignoring digits/spaces. `wordMatch` uppercases and tokenizes on spaces (`stringFunctions.jsx:113-114`).

**guard.py:** Rounds the **drop** to 4 decimals (`guard.py:177-180`) but compares raw float `cur` vs stored `prior`; does not round both operands symmetrically before subtraction.

**Adopt?** **Yes [ACTIONABLE-NOW].** Round `prior` and `cur` each to 4 decimals before computing `drop`, matching the storage granularity in `baseline_from_rows` (`guard.py:144`). Prevents `0.9900` stored vs `0.989999999` live from spurious regressions.

---

### [MEDIUM] Exact helper-level regression tests (statistical vs exact)

**pdf-to-markdown:** `stringFunctions.spec.js:182-193` locks exact `wordMatch` floats (`1.0`, `0.5`, `0.6666666666666666`, `0.25`, `0.0`) — exact equality on deterministic helpers, not slack bands.

**guard.py:** Meta-tests use slack bands (`test_guard.py:46-60`); no tests for duplicate pids, NaN axes, or baseline-metadata drift.

**Adopt?** **Yes [ACTIONABLE-NOW].** Add guard meta-tests mirroring pdf-to-markdown's exact helper style: duplicate pid rows, baseline `floors` override, symmetric rounding edge.

---

### [MEDIUM] New corpus items pass without baseline entry

**pdf-to-markdown:** Adding a transform or PDF has **zero CI consequence** (no fixtures to fail).

**guard.py:** New paper → `STATUS_NEW` passes if floors met (`guard.py:165-169`); no forced baseline update.

**Adopt?** **Yes.** Optional `--strict-new` (fail on any pid absent from baseline) mirrors what a golden-fixture repo enforces implicitly. pdf-to-markdown's total absence of e2e tests is the extreme case of guard's permissive `new` status.

---

### [MEDIUM] Refresh ritual exists only on whisker side

**pdf-to-markdown:** No `--update`/`--bless`/`--accept`; debug UI is the refresh path (`DebugView.jsx:157-161` manual "Next →" through stages).

**guard.py:** `--update` writes baseline (`__main__.py:361-367`).

**Adopt?** **Already present.** pdf-to-markdown confirms why the ritual matters: without it, QA stays manual forever.

---

### [LOW] Known-bad / expectedFailure monotonic model

**pdf-to-markdown:** No expectedFailure; known weaknesses are invisible to CI.

**guard.py:** Implements tabula-style monotonic baselines (`guard.py:22-24`, `test_guard.py:84-99`): weak baseline papers pass while stable, fail only when worse.

**Adopt?** **Already present.** pdf-to-markdown does not improve on this.

---

### [LOW] Missing-item detection

**pdf-to-markdown:** N/A (no item inventory gate).

**guard.py:** `missing` list hard-fails when baseline pid vanishes (`guard.py:221`, `109-115`).

**Adopt?** **Already present.**

---

### [CRITICAL][ACTIONABLE-NOW] Baseline-stored `axis_slack` / `floors` ignored at diff time

**pdf-to-markdown:** N/A.

**guard.py:** `baseline_from_rows` persists `"axis_slack"` and `"floors"` (`guard.py:141-142`); `diff_rows` reads only `baseline["rows"]` (`guard.py:213-214`) and uses module `_FLOORS` / default slack (`guard.py:62,205`). Changing `constants.py` after baseline commit desynchronizes the contract.

**Adopt?** **Yes [ACTIONABLE-NOW].** `diff_rows` should prefer `baseline.get("axis_slack", slack)` and `baseline.get("floors", _FLOORS)` with CLI override documented as intentional drift.

---

## 2. CALIBRATION GAPS

### [HIGH] Hardcoded `wordMatch >= 0.5` with no ROC / corpus fit

**pdf-to-markdown:** TOC headline recovery flags a line when `wordMatch(linkText, line.text()) >= 0.5` (`DetectTOC.jsx:276-277`). The underlying metric is tested for exact outputs (`stringFunctions.spec.js:182-193`) but the **0.5 cutoff is never validated** against a labeled corpus.

**calibrate.py:** Fits `unigram_coverage` edges via ROC with FPR ceiling (`calibrate.py:149-180`); does not emit thresholds for auxiliary fuzzy matchers.

**Adopt?** **Yes.** Extend calibrate (or a sibling) to fit `wordMatch`-style scores if whisker adds TOC/headline-link checks. pdf-to-markdown proves the field pattern: invent metric in code, pick cutoff by hand, never measure TPR/FPR.

---

### [HIGH] Quorum threshold `max(3, pages * 2/3)` is engineering judgment, not calibrated

**pdf-to-markdown:** Header/footer removal fires when line hash repeats on `>= Math.max(3, parseResult.pages.length * 2 / 3)` pages (`RemoveRepetitiveElements.jsx:77-78`).

**calibrate.py:** No path to fit discrete count/quorum rules; only continuous `< threshold` gates on coverage.

**Adopt?** **Partially.** Document that furniture-stripping quorums need a separate calibration story (grid search on labeled header false-positive rate). calibrate.py's ROC sweep does not cover integer quorum parameters.

---

### [MEDIUM] Multi-threshold ladder (list vs numbered vs headline)

**pdf-to-markdown:** Separate detectors with distinct rules: `isListItem` regex (`stringFunctions.jsx:104-106`), `isNumberedListItem` (`stringFunctions.jsx:108-110`), font-height headline bands (`DetectHeaders.jsx:55-84`), TOC digit-line heuristic (`DetectTOC.jsx:28-40`). Each is an implicit threshold surface.

**calibrate.py:** Two edges only (`__main__.py:490-498`: fail + review on same `unigram_coverage` axis).

**Adopt?** **Yes for future axes.** pdf-to-markdown shows structural QA needs **per-axis calibration** (lists, headings, TOC), not one coverage edge.

---

### [MEDIUM] No cross-validation / holdout

**pdf-to-markdown:** N/A.

**calibrate.py:** Single-sample ROC on all labels (`calibrate.py:171-172`); no k-fold.

**Adopt?** **Yes when n ≥ 30.** pdf-to-markdown's sparse tests (dozens of assertions, not documents) warn that small-n threshold picks overfit; calibrate should report bootstrap CIs or holdout FPR before promoting edges to `constants.py`.

---

### [LOW] Class imbalance handling

**pdf-to-markdown:** N/A.

**calibrate.py:** Maximizes TPR at FPR ceiling (`calibrate.py:174-177`); no explicit prevalence weighting.

**Adopt?** **Optional.** If fail labels are rare, report balanced accuracy alongside TPR/FPR in calibration output.

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Severity | Function | Scenario | Expected failure mode |
|----------|----------|----------|------------------------|
| [CRITICAL][ACTIONABLE-NOW] | `diff_rows` / `_evaluate_paper` | Baseline committed with `floors: {nid: 0.88}` but `constants.py` later sets `NID_FLOOR=0.90` | Gate uses live 0.90 (`guard.py:62,161-162`), not baseline 0.88; false pass/fail vs reviewer intent |
| [CRITICAL][ACTIONABLE-NOW] | `diff_rows` | Baseline stores `axis_slack: 0.02`, operator runs without `--slack`, code changes default to 0.03 | Slack read from constants (`guard.py:205`), not baseline (`guard.py:141`) |
| [HIGH][ACTIONABLE-NOW] | `_evaluate_paper` | `prior=0.97` (stored rounded), live `cur=0.949999999` (binary float) | `drop = round(0.02, 4)` may flip across slack boundary depending on pre-round float |
| [HIGH] | `baseline_from_rows` | Duplicate `pid` in `rows` list | Dict comprehension last-wins silently (`guard.py:143-146`); no error |
| [HIGH] | `diff_rows` | Duplicate `pid` in current rows | Duplicate `GuardFinding` entries; `report.failed` may double-count same paper |
| [HIGH] | `_evaluate_paper` | `cur` or `prior` is NaN | `drop > slack` is False; `cur < floor` is False; paper reports `ok` while metrics are invalid |
| [MEDIUM] | `diff_rows` | Empty `rows`, non-empty baseline | All baseline pids in `missing` (`guard.py:221`); correct hard fail, but no dedicated test (pdf-to-markdown never defines empty-corpus behavior) |
| [MEDIUM] | `_load_labeled_samples` / `calibrate_threshold` | Duplicate `pid` in labels file | Same paper double-counted in ROC (`__main__.py:441-452`) |
| [MEDIUM] | `calibrate_threshold` | All bad papers share one coverage value, all good share another, one good at bad value | Tie-break picks higher threshold (`calibrate.py:177`); sensible, but identical-value ties at same threshold need explicit test (pdf-to-markdown tests exact `wordMatch` ties at `stringFunctions.spec.js:190-191`) |
| [MEDIUM] | `_guard_main` | Corpus load skips missing candidates (`__main__.py:256-258`) | Partial corpus diffs against full baseline → `missing` fails; correct but easy to misread as regression |
| [LOW] | `_evaluate_paper` | `below_floor` populated but status `ok` for stable weak paper | Informational only (`test_guard.py:84-92`); operators may think `below_floor` implies fail (pdf-to-markdown colors Removed red but does not fail CI) |
| [LOW] | `calibrate_threshold` | `target_fpr=1.0` | Feasible set is entire curve; chooses max TPR — OK, but undocumented |

---

## 4. MISSING AXIS / CHECK

| Severity | pdf-to-markdown axis | Evidence | whisker equivalent |
|----------|---------------------|----------|-------------------|
| [CRITICAL] | **End-to-end markdown output gate** | No test asserts converted markdown (`ResultView.jsx:35-40`) | `guard` metrics only; no byte/line snapshot |
| [HIGH] | **TOC detection + headline link recovery** | `DetectTOC.jsx:18-204`, `wordMatch >= 0.5` at `276-277` | No TOC axis; MHS partial |
| [HIGH] | **List item detection** (bullet + numbered) | `DetectListItems.jsx:16-59`, regex gates `stringFunctions.jsx:104-110` | No list-structure axis |
| [HIGH] | **Repetitive header/footer stripping** | `RemoveRepetitiveElements.jsx:29-98`, `2/3` quorum | `unigram_coverage` indirect; no furniture-specific gate |
| [HIGH] | **Code/quote block detection** | `DetectCodeQuoteBlocks.jsx` (stage 9 in pipeline) | No code-block axis |
| [MEDIUM] | **Font-height / global stats headline inference** | `CalculateGlobalStats.jsx:12-105`, `DetectHeaders.jsx:16-36` | MHS on output hierarchy, not PDF font stats |
| [MEDIUM] | **Multi-line headline assembly** | `HeadlineFinder.jsx:11-28` + tests `HeadlineFinder.spec.js:31-131` | Block NID partial; no cross-line headline finder |
| [MEDIUM] | **Stage message counters** | e.g. `'Removed Header: N'` (`RemoveRepetitiveElements.jsx:93-96`) | Not in guard baseline |
| [LOW] | **Preview round-trip** (markdown render) | `ResultView.jsx:66-75` Remarkable HTML preview | Out of scope for whisker |

---

## 5. TOP PORTABLE DETAIL

**Adopt:** Order-invariant word overlap with explicit operating point — from `stringFunctions.jsx:112-118`:

```javascript
const words1 = new Set(string1.toUpperCase().split(' '));
const words2 = new Set(string2.toUpperCase().split(' '));
const intersection = new Set([...words1].filter(x => words2.has(x)));
return intersection.size / Math.max(words1.size, words2.size);
```

Used as a **hard gate** at **`>= 0.5`** for TOC headline linking (`DetectTOC.jsx:276-277`), with exact unit-test fixtures at `stringFunctions.spec.js:182-193` (including the `0.6666666666666666` boundary case for `'text 1 2 3'` vs `'text 1 4 5'`).

**Why this one:** pdf-to-markdown has no corpus metrics, no CI, and no calibration — but this pair (formula + cutoff + unit tests) is the clearest template for adding a **calibrated, order-invariant structural axis** to whisker (TOC/section recovery) beneath guard's terminal NID/TEDS/MHS. Run `calibrate.py` on labeled `(wordMatch_score, headline_found_bool)` samples to replace the hand-set `0.5`, then optionally gate in guard as a fifth axis with slack.

**Secondary portable constant:** repetitive furniture quorum **`Math.max(3, pages.length * 2 / 3)`** at `RemoveRepetitiveElements.jsx:77-78` — useful if whisker adds reference-free header/footer confidence alongside `unigram_coverage`.
