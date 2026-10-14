# Red-team: whisker guard/calibrate vs PyMuPDF4LLM QA

- PyMuPDF4LLM gates on **byte-exact committed `.expected.md` goldens** (`assert md == expected`, zero slack) with **CRLF normalization** before compare; guard diffs four rounded floats with 0.02 slack and never snapshots output text.
- Every golden test **pins `to_markdown()` kwargs** (`write_images=False`, `header=False`, `footer=False`, …) and **version-skips** when `pymupdf.mupdf_version_tuple < (1, 28)`; guard baseline carries no scorer config, engine version, or skip matrix.
- PyMuPDF4LLM runs **environment-conditional assertions** (OCR engine present → `U+FFFD` must be absent) and **layout on/off dual paths**; guard has no env-keyed expectedFailure and excludes `reading_order` from regression axes.
- **Dependency-exact pins** (`pymupdf=={VERSION}` at import, `setup.py:12-28`) plus **multi-OS CI** (ubuntu/windows/macos, `.github/workflows/test_push.yml:20-24`) prevent silent baseline drift; guard ignores baseline `axis_slack` on read and treats new corpus PIDs as pass-without-refresh.
- `calibrate.py` is **ahead** of this repo (no ROC fitter), but PyMuPDF4LLM's **multi-threshold OCR cascade** (`BAD_CHAR_THRESHOLD=0.05`, `OCR_MODEL_THRESHOLD=0.93`, `analyze_page.py:25-29,318-344`) exposes gaps: no per-axis calibration, no env-conditional thresholds, no cross-validation.

---

## 1. REGRESSION-GATE GAPS

### 1.1 Exact full-output golden compare (zero tolerance)

**PyMuPDF4LLM:** Each fixture pairs PDF + committed markdown; tests assert full-string equality with no numeric slack (`tests/test_sce-150.py:21`, `tests/test_370.py:45`, `tests/test_137.py:58`). Failures print `difflib.unified_diff` line-by-line (`tests/test_370.py:35-42`).

**guard.py:** Compares only `nid/teds/mhs/overall` rounded to 4 decimals with `GUARD_AXIS_SLACK=0.02` (`guard.py:172-184`, `constants.py:94-99`). A conversion can change thousands of characters while all four axes stay within slack.

**Adopt?** **Partially.** Whisker correctly uses fuzzy metrics for WG21 reflow tolerance, but should add optional **structural sidecar fields** (line count, `|`-count, table-row count) in the baseline JSON, mirroring pymupdf4llm's implicit shape contract. Full byte-diff of candidate MD is out of scope for bench mode.

**Severity:** [CRITICAL]

---

### 1.2 Normalization-before-diff (platform line endings)

**PyMuPDF4LLM:** Every SCE-150 test strips `\r` from expected before compare: `expected.replace('\r', '')  # For github windows` (`tests/test_sce-150.py:13,32,51`). CI matrix includes `windows-2022` (`.github/workflows/test_push.yml:22`).

**guard.py:** Rounds the **drop** to 4 decimals (`guard.py:177-180`) but never normalizes inputs; asymmetric rounding of `prior` vs `cur` before subtraction is not applied. No CRLF/LF normalization on any text artifact.

**Adopt?** **Yes [ACTIONABLE-NOW].** Round **both** `prior` and `cur` to baseline storage precision before computing `drop`, and document that bench inputs must use normalized markdown (LF-only) when building goldens on Windows.

**Severity:** [HIGH]

---

### 1.3 Conversion-parameter contract in baseline

**PyMuPDF4LLM:** Goldens are only valid for a fixed kwargs bundle baked into each test, e.g. `write_images=False, embed_images=False, header=False, footer=False` (`tests/test_sce-150.py:14-19`; `tests/test_370.py:21-31` adds `force_text=True, page_separators=True`). Changing defaults invalidates goldens silently unless tests are re-run.

**guard.py:** `baseline_from_rows` stores only metric floats (`guard.py:136-147`). No record of corpus path, block-match budget, or which converter produced the candidate.

**Adopt?** **Yes.** Embed `schema_version`, `whisker` package version, and `GUARD_REGRESSION_AXES` in baseline; fail if baseline axes set ≠ current constants (pymupdf4llm enforces this at import via `src/__init__.py:12-15`).

**Severity:** [HIGH]

---

### 1.4 Version-gated / skip-matrix tests (dependency-keyed baselines)

**PyMuPDF4LLM:** Tests early-return when `pymupdf.mupdf_version_tuple < (1, 28)` (`tests/test_137.py:13-15`, `tests/test_ocr.py:27-28,49-50`). `setup.py` pins `pymupdf=={VERSION}` and `pymupdf_layout=={VERSION}` (`setup.py:26-28`); import raises on mismatch (`src/__init__.py:12-15`). Cross-repo synthesis notes parent PyMuPDF uses **version-keyed parallel goldens** so dependency bumps cannot pass against the wrong snapshot.

**guard.py:** `schema_version` is written (`guard.py:125`) but **never validated** on read in `diff_rows` or `__main__.py`. No engine-version dimension.

**Adopt?** **Yes [ACTIONABLE-NOW].** Validate `baseline["schema_version"]` and optionally `baseline["kind"]`; warn-or-fail on mismatch. Pin `tomd`/whisker version in baseline metadata.

**Severity:** [HIGH]

---

### 1.5 Environment-conditional expectedFailure (known-bad under missing deps)

**PyMuPDF4LLM:** OCR tests branch on runtime capability: if Tesseract/RapidOCR unavailable, `U+FFFD` **must** remain (`tests/test_ocr.py:35-38`); if available, it **must not** (`tests/test_ocr.py:36`). Same PDF, opposite expected outcome keyed on env.

**guard.py:** Monotonic below-floor model for weak baselines (`guard.py:160-163`, docstring `22-24`) covers stable known-bad scores, but there is **no env-keyed allowlist** (e.g. "this PID may fail when OCR backend absent").

**Adopt?** **Yes, later.** Add optional `baseline["expected_failure"]` or env-tagged skip entries for CI tiers (fast smoke vs full corpus), matching pymupdf4llm's conditional OCR assertions.

**Severity:** [MEDIUM]

---

### 1.6 Dual code-path regression (layout on vs off)

**PyMuPDF4LLM:** `use_layout(True/False)` toggles entirely different extractors (`src/__init__.py:199-203`). Tests cover default layout (`tests/pymupdf4llm/llama_index/test_layout.py:8-20`) and nolayout malicious-link golden (`tests/test_137.py:19-61` with `use_layout(False)`).

**guard.py:** Single `run_bench` path; `reading_order` stored but **not** in `GUARD_REGRESSION_AXES` (`constants.py:97-99`). Layout/oracle divergence is invisible to guard.

**Adopt?** **Partially [ACTIONABLE-NOW].** Add `reading_order` to regression axes with its own slack, or record which reference-oracle mode produced each baseline row.

**Severity:** [HIGH]

---

### 1.7 Cross-entry-point parity (same golden, two APIs)

**PyMuPDF4LLM:** `pdf4llm/tests/test_general.py:9-48` reuses `test_370.pdf` + `test_370_expected.md` but calls `pdf4llm.to_markdown()` instead of `pymupdf4llm.to_markdown()` — same committed golden, two entry points must match.

**guard.py:** Scores one candidate source (paperstore staged MD). No guard that two scoring entry points (e.g. CLI re-run vs cached sidecar) produce identical metrics.

**Adopt?** **No for guard proper** (whisker scores tomd output once). **Yes** as a meta-test: re-score same PID twice in one guard run and assert metric identity (determinism check pymupdf4llm assumes via exact equality).

**Severity:** [MEDIUM]

---

### 1.8 Missing / added corpus item detection

**PyMuPDF4LLM:** New PDF **requires** a new committed `*.expected.md`; CI fails on `assert md == expected` until the golden exists. No "new item passes" path.

**guard.py:** Missing baseline PID → hard fail (`guard.py:113-115,221`). **Added** PID → `STATUS_NEW` passes unless below floor (`guard.py:165-169`). `--update` refresh ritual exists (`__main__.py:329-331`) but new papers do not force baseline refresh before merge.

**Adopt?** **Yes [ACTIONABLE-NOW].** Treat unknown PIDs as fail (or require explicit `allow_new: true` in baseline) so CI cannot silently grow corpus without baseline review — pymupdf4llm's "no golden file = no test" is stricter.

**Severity:** [HIGH]

---

### 1.9 Statistical vs exact tolerance semantics

**PyMuPDF4LLM:** **Exact** string equality only. Internal geometry uses small fixed tolerances (`get_text_lines.py:54 tolerance=3`; `utils.py:729 Y_TOLERANCE=1`) but **never** for CI golden diff.

**guard.py:** Deliberate **numeric slack** (`GUARD_AXIS_SLACK=0.02`) and floor-crossing exception (`guard.py:185-190`). Statistical/engineering judgment, not exact diff.

**Adopt?** **Keep slack for metrics** (whisker design is correct for fuzzy axes). Do **not** adopt exact-equality as primary gate; adopt pymupdf4llm's **zero-tolerance on chosen structural invariants** (substring presence, char counts) as supplementary baseline fields.

**Severity:** [LOW] (design difference, not a bug)

---

### 1.10 Baseline `axis_slack` written but not consumed

**PyMuPDF4LLM:** Thresholds live in code/constants co-located with tests; no drift between written config and reader.

**guard.py:** `baseline_from_rows` writes `"axis_slack": C.GUARD_AXIS_SLACK` (`guard.py:141`) but `diff_rows` always uses the caller's `slack` argument (`guard.py:205-206`), defaulting from CLI (`__main__.py:334-335`) — **not** from baseline payload.

**Adopt?** **Yes [ACTIONABLE-NOW].** On read, use `baseline.get("axis_slack", slack)` and fail if CLI `--slack` disagrees with committed baseline (prevents silent slack drift in PRs).

**Severity:** [MEDIUM]

---

## 2. CALIBRATION GAPS

### 2.1 Hand-set multi-threshold cascade (no ROC)

**PyMuPDF4LLM:** OCR decision uses **fixed engineering constants**, not fitted ROC: `BAD_CHAR_THRESHOLD = 0.05` (≥5% bad chars → OCR), `OCR_MODEL_THRESHOLD = 0.93` (ONNX prob gate) (`src/ocr/analyze_page.py:25-29`). Applied as **OR cascade**: bad-char ratio, bad-area ratio, then model prob (`analyze_page.py:318-344`).

**calibrate.py:** Single-axis ROC sweep with `max TPR @ FPR ≤ target` + Youden fallback (`calibrate.py:149-185`). Only `unigram_coverage` edges; no multi-threshold composition.

**Adopt?** **Partially.** Whisker is already more principled than pymupdf4llm for coverage edges. For future axes (table confidence, OCR advisory), adopt pymupdf4llm's **cascade pattern**: calibrate each sub-threshold separately, then document OR/AND composition in `constants.py` comments.

**Severity:** [MEDIUM]

---

### 2.2 Environment-conditional operating points

**PyMuPDF4LLM:** Same PDF, different expected OCR outcome depending on `_ocr_tesseract_available()` / RapidOCR import (`tests/test_ocr.py:10-23,35-38`). Threshold logic is global, but **assertions** are env-keyed.

**calibrate.py:** Single labeled corpus; no stratification by `reference_engine`, OS, or optional dependency presence.

**Adopt?** **Yes, later.** Support `--stratum FIELD` or per-label metadata so calibration can emit separate edges for "oracle available" vs not.

**Severity:** [MEDIUM]

---

### 2.3 Per-axis / per-modality calibration

**PyMuPDF4LLM:** Separate decision stacks for layout path vs legacy RAG path (`src/__init__.py:199-217`); OCR thresholds are per-page feature vector (`analyze_page.py:343-344`), not one scalar "overall."

**calibrate.py:** Fits only `unigram_coverage_fail_edge` and `unigram_coverage_review_edge` (`__main__.py:490-499`). No calibration for `nid/teds/mhs/reading_order` bench floors (`constants.py:56-58` remain provisional).

**Adopt?** **Yes.** Extend calibrate to accept labeled bench rows and fit per-axis floors with the same ROC machinery (pymupdf4llm proves the field never does this; whisker can).

**Severity:** [HIGH]

---

### 2.4 Cross-validation / holdout

**PyMuPDF4LLM:** No k-fold or holdout; thresholds are constants in source. Aptest external harness (`test_push.yml:51-59`) is integration-level, not statistical validation.

**calibrate.py:** Fits on entire `--labels` file in one pass; no train/test split, no confidence interval on chosen edge.

**Adopt?** **Yes, later.** At minimum report bootstrap CIs on TPR/FPR at the chosen point before human promotes to `constants.py`.

**Severity:** [LOW]

---

### 2.5 Class imbalance handling

**PyMuPDF4LLM:** N/A (no labeled corpus).

**calibrate.py:** Tie-break prefers higher TPR, then precision, then **higher threshold** (`calibrate.py:177`). No explicit prevalence weighting; heavy imbalance could pick a edge that maximizes TPR@FPR on a tiny bad set.

**Adopt?** **Partially [ACTIONABLE-NOW].** Require minimum `n_pos` / `n_neg` in CLI output and refuse to promote edges when either class &lt; N (pymupdf4llm's exact tests implicitly require sufficient fixture coverage).

**Severity:** [MEDIUM]

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Function | Scenario | What breaks | Severity |
|----------|----------|-------------|----------|
| `diff_rows` | `baseline["axis_slack"]=0.02` but CLI `--slack 0.05` | Committed slack ignored; false pass on 0.03 drop | [MEDIUM] [ACTIONABLE-NOW] |
| `_evaluate_paper` | `prior=0.90`, `cur=0.879`, slack=0.02 | `round(0.021,4)=0.021 > 0.02` fails, but `round(cur,4)` vs `round(prior,4)` grid asymmetry if one side unrounded | [HIGH] [ACTIONABLE-NOW] |
| `diff_rows` | New PID added to corpus | `STATUS_NEW` → `report.failed` is False; CI green without `--update` | [HIGH] [ACTIONABLE-NOW] |
| `diff_rows` | Duplicate `pid` in `rows` | Two `GuardFinding`s for same pid; ambiguous verdict | [MEDIUM] |
| `_evaluate_paper` | `axes[axis]` is `NaN` or `inf` from broken metric | Comparisons propagate; may never trip regression or floor | [CRITICAL] |
| `baseline_from_rows` | Empty `rows` | Writes empty baseline; later `--update` commits `{}` rows | [MEDIUM] |
| `calibrate_threshold` | All samples same class | `ValueError` (correct) | — |
| `calibrate_threshold` | Single bad + single good at **identical** value 0.72 | At threshold 0.72, `value < 0.72` flags neither; at 0.72+ε flags both — tie handling depends on candidate list | [MEDIUM] |
| `calibrate_threshold` | `NaN` in sample values | `_confusion`: `NaN < t` is False always → silent misclassification | [CRITICAL] |
| `_load_labeled_samples` | Duplicate `pid` in labels file | Last label wins silently | [MEDIUM] |
| `_guard_main` | Missing `.gt.md` candidate (skipped in `_load_corpus_pairs`) | Corpus shrinks; **missing** fires for vanished PIDs but partial corpus may hide regressions on skipped papers | [HIGH] |
| `_evaluate_paper` | Existing paper still below floor (`below_floor` populated) but stable | Passes (`STATUS_OK`) — intentional monotonic model; pymupdf4llm would still fail exact golden | [LOW] (by design) |

---

## 4. MISSING AXIS / CHECK

| PyMuPDF4LLM check | Repo evidence | Whisker equivalent |
|-------------------|---------------|-------------------|
| **`U+FFFD` absence when OCR available** | `tests/test_ocr.py:7,36` | None — no replacement-char gate on candidate MD |
| **`use_ocr=False` preserves bad layer** | `tests/test_ocr.py:43-46` | No per-flag conversion mode in guard |
| **Layout default enforced** | `test_layout.py:23-28` subprocess import assert | No `--reference` / layout-mode parity gate |
| **Malicious link suppression (nolayout)** | `tests/test_137.py:39-58` dedicated golden | No security substring denylist in guard/bench |
| **Exact dependency version coupling** | `src/__init__.py:12-15`, `setup.py:26-28` | Baseline lacks `tomd`/whisker version stamp |
| **Multi-OS golden stability** | `.github/workflows/test_push.yml:20-24` | Guard not run on OS matrix; CRLF drift unhandled |
| **Structural length oracle** | `test_ocr.py:61` `len(md_no_ocr) < len(md)` when OCR runs | No output-length delta axis |
| **Tabulate/version smoke** | `tests/test_tablulate.py:6-23` (no assert — crash-only) | No third-party dep pin in guard baseline |

**Most glaring:** replacement-character and **conversion-kwargs** axes have no whisker metric (`tests/test_ocr.py:36`, `tests/test_sce-150.py:14-19`).

**Severity:** [CRITICAL] for `U+FFFD`/OCR axis; [HIGH] for kwargs/version coupling.

---

## 5. TOP PORTABLE DETAIL

**Adopt:** **CRLF-normalize before any golden or metric compare on Windows CI**, exactly as:

```python
expected = expected.replace('\r', '')   # For github windows.
```

(`tests/test_sce-150.py:13` — repeated at `32`, `51` for all three SCE-150 goldens.)

**Why:** PyMuPDF4LLM runs ubuntu + **windows-2022** + macos (`.github/workflows/test_push.yml:20-24`). Without this one line, byte-exact (and even normalized-text) baselines flip on line endings. For whisker: apply LF normalization when reading/writing `.gt.md` in `_load_corpus_pairs` (`__main__.py:259`) and when hashing/storing baseline rows; pair with rounding **both** sides of metric diffs (`guard.py:177-180`).

**Runner-up (calibration):** OCR cascade thresholds **`BAD_CHAR_THRESHOLD = 0.05`** and **`needs_ocr = prob >= 0.93`** (`src/ocr/analyze_page.py:26-29,344`) — hand-set, but documents the field's preferred pattern for multi-gate decisions; use as template when calibrating multiple coverage sub-signals, not as literal values.

**Severity:** [HIGH] [ACTIONABLE-NOW]
