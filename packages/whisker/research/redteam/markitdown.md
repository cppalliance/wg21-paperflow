# Red-team: whisker guard/calibrate vs MarkItDown QA

- MarkItDown gates on **per-format substring anchors** (`must_include` / `must_not_include` on every vector) and **ordered `str.find()` section chains**, not scalar metric deltas; guard's four-float baseline cannot catch anchor misses or section swaps that MarkItDown fails in CI.
- MarkItDown runs **seven entry-point permutations** per fixture (local, stream±hints, data/file URI, CLI stdout/file/stdin); guard scores one `(candidate, gt)` path via `run_bench` and never exercises CLI/oracle divergence.
- MarkItDown uses **negative structural assertions** (no `|` in academic PDF, receipt table-row cap `<5`, duplication `SKU-8847` count `<=4`); guard has no anti-duplication or false-table axis.
- MarkItDown stores **committed `expected_outputs/*.md`** with **line-count tolerance `<=2`** plus structural count floors (`| > 80`, table rows `>15`); guard never snapshots output shape, only metrics.
- `calibrate.py` is **ahead of MarkItDown** (no ROC/threshold code in-repo), but MarkItDown's implicit multi-threshold QA (anchors + order + counts) exposes gaps: no per-axis calibration, no cross-validation, and guard ignores the `axis_slack` it writes into baselines.

---

## 1. REGRESSION-GATE GAPS

### 1.1 Per-item content anchors (must / must-not substrings)

**MarkItDown:** Every format declares hard anchors in `FileTestVector` (`_test_vectors.py:11-12`) and every conversion test asserts them (`test_module_vectors.py:65-68`, `test_cli_vectors.py:59-62`). PDF helpers reuse the same pattern (`test_pdf_tables.py:14-21`).

**guard.py:** Diffs only `nid/teds/mhs/overall` (`guard.py:172-184`, `constants.py:99`). A conversion can lose a critical string (e.g. `"GRAND TOTAL"`, `_test_vectors.py:95-98` PDF anchor) while NID stays high after block matching.

**Adopt?** **Yes.** Add optional per-`pid` `must_include` / `must_not_include` in the baseline JSON (or companion facts file). Metrics catch drift; anchors catch localized deletion. Complements guard, does not replace it.

**Severity:** [CRITICAL]

---

### 1.2 Reading-order / section-order regression (ordered `find()` chains)

**MarkItDown:** PDF tests build monotonic position chains: `header_pos < first_table < variance_analysis < ... < recommendations` (`test_pdf_tables.py:225-271`, receipt order `457-493`). Failure is exact index ordering, not a fuzzy score.

**guard.py:** `reading_order` is stored in baseline rows (`guard.py:71`) but **excluded** from `GUARD_REGRESSION_AXES` (`constants.py:97-99`). A section swap that preserves token sets can pass guard while failing MarkItDown.

**Adopt?** **Yes [ACTIONABLE-NOW].** Either add `reading_order` to regression axes with its own slack, or adopt MarkItDown-style ordered anchor pairs per paper in the baseline.

**Severity:** [HIGH]

---

### 1.3 Normalization-before-assert

**MarkItDown:** `validate_strings` strips backslashes before `in` checks (`test_pdf_tables.py:16`). Full-output tests normalize lines with `rstrip()` before line-count compare (`test_pdf_tables.py:750-751`).

**guard.py:** Rounds stored baseline values and the **drop** to 4 decimals (`guard.py:144,177-180`) but compares raw `BenchRow` floats for the current side. No output-text normalization layer.

**Adopt?** **Partially [ACTIONABLE-NOW].** Round **both** `prior` and `cur` to 4 decimals before subtraction (symmetric grid). Anchor checks should apply the same normalizer MarkItDown uses before substring search.

**Severity:** [HIGH]

---

### 1.4 Negative structural / anti-false-positive gates

**MarkItDown:** Academic PDF must have **zero** pipe chars and zero extracted tables (`test_pdf_tables.py:609-618`). Receipt must have `<5` table rows (`test_pdf_tables.py:1110-1113`). Borderless inventory caps duplicate SKU occurrences `<=4` (`test_pdf_tables.py:287-291`).

**guard.py:** No equivalent. TEDS/NID can stay high while spurious tables or duplicated blocks appear (bench table pairing is order-indexed, `bench.py:130-137`).

**Adopt?** **Yes.** Add optional baseline fields: `max_substring_count`, `forbid_char`, `max_table_rows` (ported from MarkItDown thresholds). Cheap, deterministic, catches regressions metrics miss.

**Severity:** [HIGH]

---

### 1.5 Committed output goldens with loose structural tolerance

**MarkItDown:** `expected_outputs/*.md` committed beside PDFs; tests require `abs(len(actual_lines) - len(expected_lines)) <= 2` (`test_pdf_tables.py:754-757`, `807-810`, `895-898`) plus structural floors (`test_pdf_tables.py:760-761`, `813`). Golden file content is **not** byte-diffed; anchors + counts carry the gate.

**guard.py:** Metric snapshot only (`baseline_from_rows`, `guard.py:136-147`). No line-count, pipe-count, or sidecar snapshot.

**Adopt?** **Partially.** Store `{line_count, pipe_count, table_row_count}` per paper in baseline; fail on regression beyond slack (MarkItDown's `<=2` line tolerance is a concrete portable constant).

**Severity:** [MEDIUM]

---

### 1.6 Multi-entry-point parity (API vs stream vs CLI)

**MarkItDown:** Same `FileTestVector` drives module local, stream with/without hints, data URI, file URI, HTTP (local only), and CLI stdout/file/stdin (`test_module_vectors.py:57-159`, `test_cli_vectors.py:43-125`).

**guard.py / `__main__.py`:** Single path: staged candidate MD from paperstore vs `.gt.md` (`__main__.py:245-260`, `358`). No guard that CLI-rendered output matches library output.

**Adopt?** **No for guard itself** (whisker scores tomd output, not markitdown). **Yes** for whisker's reference oracle path: if markitdown is the oracle, parity tests belong in whisker CI, not in guard's metric diff.

**Severity:** [LOW]

---

### 1.7 Known-bad / expectedFailure / monotonic baselines

**MarkItDown:** Scanned PDF expects **empty** output (`test_pdf_tables.py:649-652`, `974-978`); empty is the committed golden, not a failure. No `@xfail`, but permanently weak cases are encoded as expected empty or anchor subsets.

**guard.py:** Monotonic known-bad for metrics: below-floor baseline not re-flagged unless worsening (`guard.py:160-198`, `test_guard.py:84-99`). No per-paper `expected_failure` bit; no empty-output contract.

**Adopt?** **Partially [ACTIONABLE-NOW].** Baseline flag `"expected_failure": true` or `"expect_empty": true` for scanned/ocr-less fixtures so guard matches MarkItDown's empty golden semantics.

**Severity:** [MEDIUM]

---

### 1.8 Missing-item vs added-item detection

**MarkItDown:** Closed corpus: each PDF/HTML fixture has tests; new file without vectors is simply untested (no silent pass). Full-output tests `pytest.skip` if golden missing (`test_pdf_tables.py:740-741`).

**guard.py:** Missing baseline papers hard-fail (`guard.py:221`). **New** papers without baseline entries pass as `STATUS_NEW` (`guard.py:165-169`) unless below floor.

**Adopt?** **Yes [ACTIONABLE-NOW].** `--strict-corpus` (or default in CI): fail on any `STATUS_NEW` until `--update`, mirroring MarkItDown's "new fixture needs explicit test/authored golden" discipline.

**Severity:** [HIGH]

---

### 1.9 Refresh ritual

**MarkItDown:** No `--accept` CLI; goldens updated by hand-editing `expected_outputs/*.md` and vectors in `_test_vectors.py`. CI never regenerates (`tests.yml:17-18` runs `hatch test` only).

**guard.py:** `--update` rewrites baseline (`__main__.py:361-367`) with no CI env lockout.

**Adopt?** **Partially.** Whisker already has a refresh ritual (ahead of MarkItDown). Add CI lockout (`CI=true` → refuse `--update`) like other repos; MarkItDown does not model this, but whisker should not regress here.

**Severity:** [MEDIUM] [ACTIONABLE-NOW]

---

### 1.10 Statistical vs exact tolerance

**MarkItDown:** Substring checks are **exact** (`assert string in text`). Numeric tolerances are deterministic integers: line count `<=2`, duplication `<=4`, memory `peak_mib < 30` (`test_pdf_memory.py:328`). No corpus means, no ROC.

**guard.py:** Per-axis float slack `0.02` (`constants.py:94`), exact floor cross for sub-slack drops (`guard.py:185-190`).

**Adopt?** **Keep guard's model** for metrics; **add** MarkItDown's exact integer structural tolerances as a second layer. Do not replace slack with corpus means (MarkItDown never uses means).

**Severity:** [MEDIUM]

---

## 2. CALIBRATION GAPS

MarkItDown has **no threshold calibration, ROC, or fitted operating points** in-repo. All gates are hand-authored strings and counts. `calibrate.py` is strictly ahead on formal FPR-bounded edge fitting.

Gaps **relative to MarkItDown's implicit multi-threshold practice**:

| MarkItDown implicit gate | calibrate.py coverage |
|---|---|
| `must_include` / `must_not_include` (hard 0/1) | Not fittable; absent from calibrate |
| Section-order `find()` chain | Not calibrated |
| Line-count `<=2`, pipe `>80`, dup `<=4` | Not calibrated |
| Single metric `unigram_coverage` | **Only** this axis (`__main__.py:490-498`) |

**2.1 No per-axis / structural calibration** [HIGH]: MarkItDown effectively calibrates **per format** via separate vectors (`GENERAL_TEST_VECTORS` vs `DATA_URI_TEST_VECTORS`, `_test_vectors.py:15-279`). `calibrate.py` fits one scalar twice (fail vs review labels) with no `nid/teds/mhs` ROC.

**Adopt?** Optional separate calibrations per bench axis when labeled GT exists; keep anchors as hard asserts, not ROC.

**2.2 Nested fail/review edges from one `target_fpr`** [MEDIUM] [ACTIONABLE-NOW]: Review fit treats `fail|review` as positives (`__main__.py:491`). No constraint that `review_edge >= fail_edge`. MarkItDown's tiers are independent lists; misfit can invert bands.

**Adopt?** After fitting, enforce `review_edge >= fail_edge` or fit review only on `label==review` samples.

**2.3 No cross-validation / holdout** [MEDIUM]: MarkItDown avoids overfit by **fixed public fixtures** committed in git. `calibrate_threshold` (`calibrate.py:149-185`) fits in-sample on all labels; no k-fold or holdout report.

**Adopt?** Report train/holdout TPR/FPR or require minimum `n` per class (MarkItDown has ~15+ formats × multiple asserts as implicit sample size).

**2.4 Class imbalance** [LOW]: MarkItDown does not balance classes; rare formats get their own vector anyway. `calibrate.py` uses raw counts (`calibrate.py:164-165`) with no stratification by `pid` or format family.

**2.5 Operating-point selection** [LOW]: MarkItDown uses **conjunctive** asserts (all `must_include` must pass). calibrate uses **one** threshold on one continuous score. Different semantics; calibrate should document that it replaces only the coverage band, not anchor/order gates.

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Function | Scenario | MarkItDown lesson | Outcome |
|---|---|---|---|
| `diff_rows` | Baseline JSON has `"axis_slack": 0.05` but CLI uses default `0.02` | MarkItDown tolerances live **in test code** beside asserts, not ignored metadata | Slack mismatch; false pass/fail [HIGH] [ACTIONABLE-NOW] (`guard.py:141` vs `205`, never reads baseline slack) |
| `diff_rows` | Baseline missing/wrong `kind` or `schema_version` | MarkItDown tests fail closed on missing golden (`test_pdf_tables.py:740-741`) | Silent diff against malformed dict [HIGH] [ACTIONABLE-NOW] |
| `diff_rows` | Two `BenchRow` with same `pid` | MarkItDown one test per fixture | Duplicate findings; `current_pids` set hides multiplicity [MEDIUM] [ACTIONABLE-NOW] |
| `_evaluate_paper` | `axes[axis]` is NaN/inf from broken metric | MarkItDown never divides; pure string ops | NaN comparisons skip regressions and floors [CRITICAL] [ACTIONABLE-NOW] |
| `diff_rows` | New paper added, metrics above floor | MarkItDown requires new vector/golden | `STATUS_NEW` passes; baseline stale [HIGH] [ACTIONABLE-NOW] |
| `_evaluate_paper` | `below_floor` on stable known-weak paper | MarkItDown still asserts `must_include` on every run | Status `ok` despite `below_floor` strings; anchors would catch [MEDIUM] |
| `calibrate_threshold` | Sample value NaN | N/A in MarkItDown | `flagged = value < threshold` is False; mislabels bad as good [CRITICAL] [ACTIONABLE-NOW] |
| `calibrate_threshold` | All samples identical, mixed labels | MarkItDown uses disjoint must/must-not strings | Youden fallback; 50/50 tie at one threshold (`calibrate.py:178-180`) [MEDIUM] |
| `calibrate_threshold` | Single positive or negative | MarkItDown always has both pass and fail fixtures per vector | `ValueError` (`calibrate.py:166-169`) — OK but CLI gives no minimum-n guidance [LOW] |
| `_load_corpus_pairs` | GT file exists, candidate missing | MarkItDown asserts on conversion output | Paper skipped with warning; guard may report `missing` for baseline pid without scoring current [MEDIUM] (`__main__.py:256-258`) |
| `baseline_from_rows` | Unicode GT (cp932 CSV equivalent) | MarkItDown asserts Japanese cells (`_test_vectors.py:146-152`) | Works if metrics computed; no test that round-trip preserves CJK in guard [LOW] |
| `_candidate_thresholds` | Huge corpus, many unique values | MarkItDown O(n) substring scans | O(n) curve points (`calibrate.py:171-172`); fine for 30-50 labels, not thousands [LOW] |

---

## 4. MISSING AXIS / CHECK

| MarkItDown gate | whisker equivalent | Gap |
|---|---|---|
| `must_include` / `must_not_include` per format | None in guard/bench | [CRITICAL] |
| Ordered section `find()` chain | `reading_order` metric, not gated | [HIGH] |
| Duplication ceiling (`count <= 4`) | None | [HIGH] |
| Forbidden char class (no `\|` in prose PDF) | None | [HIGH] |
| False table detection (receipt `<5` rows) | TEDS only on real MD tables | [MEDIUM] |
| Line-count / pipe-count structural snapshot | None | [MEDIUM] |
| Table column consistency (`validate_table_structure`, `test_pdf_tables.py:74-94`) | TEDS holistic | [MEDIUM] |
| Memory / resource ceiling (`peak_mib < 30`, `test_pdf_memory.py:328`) | None | [LOW] (tomd-side) |
| Charset / encoding (`charset="cp932"`, `_test_vectors.py:144`) | UTF-8 assumed in corpus load | [LOW] |
| Format-option vectors (`DATA_URI_TEST_VECTORS`) | Single candidate path | [LOW] |
| Verdict trichotomy (`pass/review/fail`) | Guard is pass/fail on metrics only | [MEDIUM] (gap-matrix #3) |

---

## 5. TOP PORTABLE DETAIL

**Adopt:** MarkItDown **section-order gate** — monotonic `str.find()` position chain with hard fail on any `-1` or order inversion.

**Source:** `test_pdf_tables.py:225-271` (borderless inventory PDF):

```python
header_pos = text_content.find("INVENTORY RECONCILIATION REPORT")
variance_pos = text_content.find("Variance Analysis:")
recommendations_pos = text_content.find("Recommendations:")
assert header_pos < first_table_pos < variance_pos < ... < recommendations_pos
```

**Portable spec for whisker baseline JSON:**

```json
"section_order": [
  ["INVENTORY RECONCILIATION REPORT", "Product Code", "Variance Analysis:", "Recommendations:"]
]
```

**Gate rule:** for anchors `[a0, a1, ..., an]`, require `find(ai) != -1` and `find(ai) < find(ai+1)` on candidate markdown (after `replace("\\", "")` normalization per `test_pdf_tables.py:16`).

**Why this over metric slack:** guard already slack-tolerates NID/TEDS; MarkItDown proves **order swaps** are independent failures detected only by index order, exactly the axis whisker explicitly removed from `GUARD_REGRESSION_AXES` (`constants.py:97-99`). One ordered chain per corpus paper closes the highest-leverage hole MarkItDown exposes with zero statistical tuning.

**Severity:** [CRITICAL] [ACTIONABLE-NOW] (baseline schema + check function; not necessarily in `guard.py` float loop today)
