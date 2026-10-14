# Red-team: whisker guard/calibrate vs PyMuPDF QA

- PyMuPDF gates on **committed output artifacts** (text files, PDFs, PNG pixmaps, pickle structs) with **version-keyed parallel goldens** selected by `mupdf_version_tuple`; guard stores four floats per paper and cannot catch output churn that preserves NID/TEDS/MHS.
- PyMuPDF uses **heterogeneous tolerance semantics** (exact strings, pixmap RMS `< 0.1`, rect norm `1e-3`, cell-geometry `< 0.2`); guard applies one scalar `GUARD_AXIS_SLACK` to every axis.
- PyMuPDF **never compares against stale embedded thresholds**: tests read the golden matching the runtime dependency version; guard writes `floors`/`axis_slack` into the baseline JSON but **`diff_rows` ignores them** and always uses live `constants.py`.
- PyMuPDF wraps **every test** in global-state hygiene (`mupdf_warnings` empty, `_globals` unchanged, fd leak detection); guard has no post-score contamination check and **`below_floor` on existing papers is advisory-only** (status stays `ok`).
- `calibrate.py` is ahead of PyMuPDF (no ROC code in-repo), but PyMuPDF's multi-threshold, version-branching, and platform-conditional expectations expose missing **NaN handling**, **fail/review edge ordering**, and **no per-axis/toolchain calibration**.

---

## 1. REGRESSION-GATE GAPS

### 1.1 Version-keyed parallel goldens (dependency bump safety)

**PyMuPDF:** Committed expected outputs are keyed to the MuPDF runtime version. `test_2608` selects among three text goldens (`test_2608_expected`, `_1.26`, `_1.28`) via `mupdf_version_tuple` branches (`tests/test_font.py:69-77`). `test_1645` swaps PDF pixmaps at `(1, 27)` (`tests/test_annots.py:241-244`). `test_3842` swaps OCR text at `(1, 28)` (`tests/test_tesseract.py:82-85`). `test_markdown` inlines version-specific expected markdown strings (`tests/test_tables.py:308-326`). `test_2548` asserts **different warning text** per version band (`tests/test_2548.py:29-36`).

**guard.py:** Single unversioned baseline per paper (`guard.py:136-147`). A tomd/pymupdf/whisker metric-definition bump can pass guard while comparing against the wrong-era baseline, or fail spuriously with no selector.

**Adopt?** **Yes [ACTIONABLE-NOW].** Add `toolchain`/`schema_version`/`tomd_version` to baseline metadata; support version-keyed row maps (or explicit baseline file paths per toolchain). Without this, dependency upgrades silently invalidate the contract PyMuPDF explicitly prevents.

**Severity:** [CRITICAL]

---

### 1.2 Output goldens vs metric snapshots

**PyMuPDF:** Regression is on **actual outputs**: exact UTF-8 text (`tests/test_font.py:85`), exact OCR text (`tests/test_tesseract.py:107`), exact committed `symbols.txt` (`tests/test_drawings.py:18-24`), pickle-serialized table extracts with geometry checks (`tests/test_tables.py:15-37`), pixmap byte RMS (`tests/test_annots.py:263-268`, `gentle_compare.py:45-65`).

**guard.py:** Only diffs `nid/teds/mhs/overall` floats (`guard.py:172-184`). Metric-preserving output corruption (wrong heading level markup, table pipe layout, front-matter drift) can pass.

**Adopt?** **Partially.** Keep metrics gate; add optional per-pid output fingerprints (line count, hash of normalized markdown, or committed `.md` golden with refresh ritual). Full byte goldens are overkill for WG21 corpus size; structural counts are PyMuPDF's `test_drawings1` pattern at lower cost.

**Severity:** [CRITICAL]

---

### 1.3 Per-field tolerance semantics (not one slack for all)

**PyMuPDF:** Tolerance is **assertion-specific**: word strings exact, rects `delta > 1e-3` fails (`gentle_compare.py:13-27`), pixmap RMS `< 0.05` (`tests/test_mupdf_regressions.py:54`) or `< 0.1` (`tests/test_annots.py:268`), table cells `abs(c1-c0) < 0.2` plus containment (`tests/test_tables.py:36-37`), width `abs(d['width'] - 2.449) < 0.01` (`tests/test_drawings.py:266`).

**guard.py:** One `slack` for all regression axes (`constants.py:94`, `guard.py:180-184`).

**Adopt?** **Yes [ACTIONABLE-NOW].** Per-axis slack in baseline JSON (already written at `guard.py:141` but unused at compare time). TEDS/table axis likely needs looser slack than NID; mirror PyMuPDF's pattern of different thresholds per property type.

**Severity:** [HIGH]

---

### 1.4 Baseline-embedded floors/slack ignored at diff time

**PyMuPDF:** Tests always load the golden matching **current** runtime; no drift between committed threshold file and live code.

**guard.py:** `baseline_from_rows` writes `floors` and `axis_slack` (`guard.py:141-142`), but `_evaluate_paper` reads `_FLOORS` from live `constants.py` (`guard.py:62`, `161-163`) and `diff_rows` never reads `baseline["axis_slack"]` (`guard.py:201-206`, `__main__.py:334-335` CLI default only).

**Adopt?** **Yes [ACTIONABLE-NOW].** Diff must use baseline-stored `floors`/`axis_slack` when present; fail if `schema_version` mismatch. Otherwise a constants.py floor edit retroactively rewrites history without a baseline refresh.

**Severity:** [HIGH]

---

### 1.5 Normalization before compare

**PyMuPDF:** Strips platform `\r` before exact text compare (`tests/test_font.py:80-82`). Version-specific markdown expected strings differ in strikethrough rendering (`tests/test_tables.py:308-326`). Pickle compare separates **exact cell text** from **approximate geometry** (`tests/test_tables.py:25-37`).

**guard.py:** Rounds only the **drop** to 4 decimals (`guard.py:177-180`), not both operands symmetrically. No normalization of inputs before bench scoring in guard path.

**Adopt?** **Yes [ACTIONABLE-NOW].** Round `prior` and `cur` to baseline storage precision before subtraction. Optionally normalize markdown before bench when refreshing baselines (whisker already has `normalized_text`; guard does not use it).

**Severity:** [HIGH]

---

### 1.6 Global state / side-effect hygiene (meta-gate)

**PyMuPDF:** `conftest.py:wrap` asserts empty `mupdf_warnings()` pre/post (`conftest.py:74-75`, `142-146`), unchanged `pymupdf._globals` (`conftest.py:119-153`), stable `JM_annot_id_stem` (`conftest.py:109`, `158-159`), optional fd-leak dumps (`conftest.py:161-172`).

**guard.py:** No check that scoring mutated shared state or emitted warnings. Batch scoring in `__main__.py` swallows per-paper exceptions and continues (`__main__.py:185-190`).

**Adopt?** **Partially.** Add optional determinism replay (score same pid twice, assert identical metrics). Full global-state wrapping belongs in whisker test harness, not guard diff logic.

**Severity:** [MEDIUM]

---

### 1.7 Known-bad / version-conditional expectedFailure

**PyMuPDF:** Does not use pytest `xfail`; instead **version/platform branches** skip or alternate expectations: `test_2907` returns early on classic (`tests/test_2907.py:9-11`), `test_4435` skips when `PYMUPDF_TEST_QUICK=1` (`tests/util.py:30-34`, `tests/test_pixmap.py:516-517`), Windows/Pyodide alloc-failure path (`tests/test_pixmap.py:523-541`), GraalVM skips (`tests/test_tables.py:200-202`).

**guard.py:** Monotonic known-weak baseline (paper below floor in baseline not re-flagged unless worse) (`guard.py:171-198`, `test_guard.py:84-92`). No version/platform dimension; no explicit `expectedFailure` bit per pid.

**Adopt?** **Partially [ACTIONABLE-NOW].** Extend baseline rows with optional `expect_below_floor: true` or `skip_axes: [...]` for papers known weak on a toolchain, analogous to PyMuPDF's version branch skipping wrong golden. Monotonic model alone cannot express "this pid is allowed to warn on mupdf 1.26 only."

**Severity:** [MEDIUM]

---

### 1.8 Missing / added item detection

**PyMuPDF:** `gentle_compare` fails on word-count mismatch (`gentle_compare.py:15-17`). Pickle table test asserts `len(cells) == len(old_cells)` (`tests/test_tables.py:32-33`). No corpus-level "paper vanished" gate.

**guard.py:** Hard-fails `missing` pids (`guard.py:113-115`, `221`). New pids get `new`/`new_below_floor` (`guard.py:165-169`). Does not flag **duplicate pids** in input rows or **added** pids as requiring baseline refresh audit.

**Adopt?** **Partially [ACTIONABLE-NOW].** Dedupe/validate unique pids in `diff_rows`; emit `added` list distinct from `new` when baseline exists. Missing detection already matches PyMuPDF's list-length checks in spirit.

**Severity:** [MEDIUM]

---

### 1.9 CI multi-version matrix

**PyMuPDF:** `test_quick.yml` runs tests against MuPDF **master** and **1.28.x** (`test_quick.yml:26-46`). `test_multiple.yml` matrixes OS × MuPDF branches (`test_multiple.yml:24-29`).

**guard.py / CLI:** Single run, single baseline file (`__main__.py:319-395`). No enforced matrix across tomd/whisker versions.

**Adopt?** **Yes.** CI should run `whisker guard` under pinned toolchain matrix; store version-keyed baselines per matrix cell. Guard code need not embed CI, but baseline schema must support it (see 1.1).

**Severity:** [MEDIUM]

---

### 1.10 Refresh ritual

**PyMuPDF:** No single `--accept` flag; goldens are **hand-updated files** committed beside tests (e.g. adding `test_2608_expected_1.28` when MuPDF 1.28 changes output). `test_4336` documents pickle refresh workflow behind `if 0:` (`tests/test_pixmap.py:468-499`).

**guard.py:** Explicit `--update` rewrite (`__main__.py:329-331`, `361-367`).

**Adopt?** **Already present.** PyMuPDF's lesson is refresh must be **version-aware** (add parallel golden, not overwrite old), which `--update` currently does not do.

**Severity:** [LOW] (ritual exists; version-awareness missing)

---

### 1.11 Statistical vs exact

**PyMuPDF:** **Both**, chosen per property: exact strings/dicts (`tests/test_general.py:698-699`), statistical pixmap RMS, approximate geometry.

**guard.py:** Deterministic float threshold only.

**Adopt?** **Yes** for optional secondary checks (RMS-like metric variance across re-runs). Not a replacement for per-paper axis diff.

**Severity:** [LOW]

---

## 2. CALIBRATION GAPS

PyMuPDF has **no ROC/threshold calibration module**; thresholds are literal asserts (`rms < 0.1`, `delta > 1e-3`, `abs(c1-c0) < 0.2`). Gaps below are places PyMuPDF's **implicit multi-threshold** practice is richer than `calibrate.py`.

### 2.1 Multi-threshold, per-assertion operating points

**PyMuPDF:** Each test carries its own threshold constant inline (`gentle_compare.py:13`, `test_annots.py:268`, `test_tables.py:37`).

**calibrate.py:** Fits one scalar edge per call (`calibrate.py:149-185`). CLI fits only `unigram_coverage` fail/review edges (`__main__.py:488-499`). No calibration path for NID/TEDS/MHS guard slack or floor values.

**Adopt?** **Yes.** Extend calibration to bench axes and per-axis FPR budgets; emit a `thresholds.json` resembling opendataloader's multi-key shape. PyMuPDF proves different properties need different tolerances.

**Severity:** [HIGH]

---

### 2.2 Version-conditional thresholds

**PyMuPDF:** Expected warnings and outputs change by `mupdf_version_tuple` (`tests/test_2548.py:29-36`, `tests/test_pixmap.py:545-549`). Threshold is not universal.

**calibrate.py:** Single edge per metric name with no toolchain dimension.

**Adopt?** **Yes** when whisker calibrates on labeled data collected under a specific tomd build; record `toolchain` in calibration artifact (`__main__.py:504-516`).

**Severity:** [MEDIUM]

---

### 2.3 Cross-validation / holdout

**PyMuPDF:** N/A (no fitter).

**calibrate.py:** Full-sample ROC sweep (`calibrate.py:171-172`); no k-fold or holdout. Small labeled sets (30-50 papers per CLAUDE.md) will overfit.

**Adopt?** **Yes** before promoting edges to `constants.py`.

**Severity:** [MEDIUM]

---

### 2.4 Class imbalance handling

**PyMuPDF:** N/A.

**calibrate.py:** `target_fpr` ceiling (`calibrate.py:43`, `174-177`) but no minimum TP count, no stratification, no cost weighting. One bad-class paper dominates TPR.

**Adopt?** **Partially [ACTIONABLE-NOW].** Report confidence bounds; require minimum `n_pos`/`n_neg` in artifact; optionally use balanced subsampling.

**Severity:** [MEDIUM]

---

### 2.5 Fail/review edge ordering invariant

**PyMuPDF:** N/A.

**calibrate.py:** Fits fail and review edges **independently** (`__main__.py:494-499`) with no constraint that `review_edge >= fail_edge`. Overlapping labels can yield inverted band.

**Adopt?** **Yes [ACTIONABLE-NOW].** After fit, assert `review_edge >= fail_edge` or fit review only on `pass`+`review` samples with fail fixed.

**Severity:** [HIGH]

---

### 2.6 Platform-conditional calibration

**PyMuPDF:** Tests branch on Windows/Pyodide/GraalVM (`tests/test_pixmap.py:523-541`, `tests/test_tables.py:200-202`).

**calibrate.py:** No platform tag on samples or edges.

**Adopt?** **Low priority** unless labeled data spans platforms.

**Severity:** [LOW]

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Function | Scenario | PyMuPDF lesson | Severity |
|----------|----------|----------------|----------|
| `_evaluate_paper` | Baseline paper has `teds=0.50` (known weak); current `teds=0.50`, still below `TEDS_FLOOR` | PyMuPDF re-asserts every run; guard returns `status=ok` with informational `below_floor` only (`guard.py:192-197`, `test_guard.py:84-92`) | [MEDIUM] |
| `_evaluate_paper` / `diff_rows` | `baseline["floors"]` differs from live `constants.py` after floor edit | Compare uses live `_FLOORS` (`guard.py:62`, `161`); stale committed floors are decorative | [HIGH] [ACTIONABLE-NOW] |
| `diff_rows` | `baseline["axis_slack"]=0.05` stored, CLI uses default `0.02` | Slack written (`guard.py:141`) never read back | [HIGH] [ACTIONABLE-NOW] |
| `diff_rows` | Duplicate `pid` in `rows` | Two findings, same pid; no error (PyMuPDF checks list lengths explicitly) | [MEDIUM] [ACTIONABLE-NOW] |
| `_evaluate_paper` | `prior=0.97`, `cur=0.9499999999999999` (IEEE noise) | Only drop rounded (`guard.py:180`); operands not rounded symmetrically (PyMuPDF normalizes `\r` before exact compare) | [MEDIUM] [ACTIONABLE-NOW] |
| `diff_rows` | `baseline` missing `kind` or wrong `schema_version` | Accepted silently (`guard.py:213-214`) | [MEDIUM] [ACTIONABLE-NOW] |
| `calibrate_threshold` | Sample value `NaN` or `inf` | `value < threshold` poisons ROC counts; no validation | [HIGH] [ACTIONABLE-NOW] |
| `calibrate_threshold` | All samples identical value, mixed labels | Tie-break `(tpr, precision, threshold)` (`calibrate.py:177`); arbitrary edge | [MEDIUM] |
| `calibrate_threshold` | `n_pos=1`, `target_fpr=0.05` | Single bad paper yields unstable TPR/FPR | [MEDIUM] |
| `_calibrate_main` | Independent fail/review fits | Can produce `review_edge < fail_edge` | [HIGH] [ACTIONABLE-NOW] |
| `_load_corpus_pairs` | Corpus pid skipped (missing candidate md) | Guard runs subset silently; missing-from-run ≠ missing-from-baseline (`__main__.py:256-258`) | [HIGH] |
| `baseline_from_rows` | Empty `rows` + `--update` | Writes empty baseline; next run passes with zero coverage | [MEDIUM] [ACTIONABLE-NOW] |
| `run_bench` → guard | Unicode-heavy WG21 paper | PyMuPDF normalizes `\r`, exact UTF-8 (`test_font.py:80-85`); guard inherits bench rounding only | [LOW] |
| `diff_rows` | Huge corpus | Linear in papers; no issue (PyMuPDF runs 171+ tests serially) | [LOW] |

---

## 4. MISSING AXIS / CHECK

| PyMuPDF gate | Whisker equivalent | Gap |
|--------------|-------------------|-----|
| **Exact text extraction** (`test_2608`, `test_3842`) | `nid` (block-matched, fuzzy) | No exact or normalized full-text golden | [CRITICAL] |
| **Pixmap visual RMS** (`test_1645`, `test_annots.py:435`) | none | Layout/rendering regressions invisible | [HIGH] |
| **Structured pickle snapshot** (table cells + extracts, `test_tables.py:15-37`) | `teds` (order-matched mean) | Cell-level geometry/content split not gated | [HIGH] |
| **Warning side-channel** (`conftest.py:142-146`, `test_2548.py:36`) | none | Silent MuPDF-style warnings in conversion pipeline | [MEDIUM] |
| **Global config invariants** (`conftest.py:148-153`) | none | Scoring mutating globals undetected | [MEDIUM] |
| **Version-specific expected side effects** (`test_2548`, `test_pixmap.py:545-549`) | none | Toolchain change alters behavior without baseline key | [CRITICAL] |
| **Drawing/vector structure exact** (`test_drawings.py:18-24`) | none | Vector/structure fidelity not in whisker axes | [MEDIUM] |
| **Markdown table rendering** (`test_tables.py:302-330`, `test_md_styles`) | `teds` | Strikethrough/MD dialect regressions can pass TEDS | [MEDIUM] |
| **Reading order / block order** (`gentle_compare` word order) | `reading_order` advisory only (`constants.py:97-99`) | Section swap under-reported vs PyMuPDF ordered checks | [HIGH] |

---

## 5. TOP PORTABLE DETAIL

**Adopt: version-keyed parallel goldens selected by runtime toolchain tuple.**

PyMuPDF pattern (minimal form):

```python
# tests/test_font.py:69-77
if pymupdf.mupdf_version_tuple >= (1, 28):
    path_expected2 = path_expected_1_28
elif pymupdf.mupdf_version_tuple >= (1, 27):
    path_expected2 = path_expected
else:
    path_expected2 = path_expected_1_26
```

For whisker guard: store `baseline["rows_by_toolchain"]["tomd-X.Y+whisker-Z"]` or sibling baseline files `guard-baseline-1.28.json`, and have `diff_rows` select on `import tomd; tomd.__version__` (and whisker schema). **Do not overwrite** the prior baseline on `--update`; add/update the entry for the current toolchain only.

Secondary portable constant if only one number: **pixmap RMS gate `rms < 0.1`** for visual regressions (`tests/test_annots.py:268`) as a template for optional render/hash checks; primary lesson is the **version branch**, not the RMS value alone.

**Severity if ignored:** [CRITICAL] — pymupdf/toml dependency bumps are exactly when PyMuPDF adds new golden files; whisker's single baseline will false-pass or false-fail.
