# Red-team: whisker guard/calibrate vs pdfplumber QA

- pdfplumber gates on **exact structural outputs** (committed `comparisons/*.txt`, inline `SCOTUS` tree dict, per-cell row lists) and **domain accounting invariants** (`colsum == total * 2`); whisker guard diffs four fuzzy axes with slack and misses localized cell/text regressions metrics absorb.
- pdfplumber embeds **dozens of named, operation-specific tolerances** (`tolerance=3`, `intersection_tolerance=5`, `RECT_TOLERANCE=2`) and tests tolerance sensitivity; guard has one global `GUARD_AXIS_SLACK` and **ignores `axis_slack`/`floors` stored in the baseline JSON it writes**.
- pdfplumber asserts **cardinality and shape** (`len(tables)==3`, `len(edges)==364`, layout line width `==75`); guard has no count/shape axes, so table split/merge regressions can pass.
- pdfplumber has **no ROC calibration** (whisker `calibrate.py` is ahead), but its issue-fixture pattern and exact-boundary asserts expose gaps: unvalidated baseline schema, **added-paper pass** (asymmetric vs missing), independent fail/review fits that can invert the band.
- **Top portable adoption:** NICS table accounting invariant `colsum == (total * 2)` per numeric column (`tests/test_nics_report.py:82-85`).

---

## 1. REGRESSION-GATE GAPS

### [CRITICAL] Domain accounting invariants (reference-free structural truth)

**pdfplumber:** After parsing the NICS firearms table, every numeric column must satisfy `colsum == (total * 2)` (month + YTD rows) (`tests/test_nics_report.py:81-85`). Failure means table geometry or cell assignment broke even if extracted text "looks fine."

**guard.py:** No invariant layer; only metric deltas vs baseline (`guard.py:172-184`) or static floors (`guard.py:161-163`, `constants.py:56-58`).

**Adopt?** Yes. Add optional per-`pid` `invariants` block in baseline JSON (e.g. column-sum laws, row-count equality). Metrics catch drift; invariants catch wrong structure with high NID. Complements guard; does not replace slack diff.

---

### [CRITICAL] Committed exact-output goldens (byte-exact text)

**pdfplumber:** `tests/comparisons/scotus-transcript-p1.txt` and `scotus-transcript-p1-cropped.txt` are committed; tests assert `extract_text(...) == target` with no slack (`tests/test_utils.py:383-398`, `tests/test_convert.py:312-314` CLI path).

**guard.py:** Stores rounded floats only (`baseline_from_rows`, `guard.py:143-146`); never snapshots output text or line lists.

**Adopt?** Partially. Byte-exact markdown is wrong primary gate for tomd, but pdfplumber proves slack-based metrics miss regressions exact text catches. Add optional `{line_count, hash, anchor_substrings}` per paper in baseline, or companion facts file (gap-matrix #9).

---

### [HIGH] Embedded structure-tree snapshot (exact nested golden)

**pdfplumber:** Full `SCOTUS` structure tree is an inline committed dict; `assert pdf.structure_tree == SCOTUS` (`tests/test_structure.py:719-736`, `1032-1036`). Any MCID/tag/attribute drift fails CI.

**guard.py:** `mhs` is a fuzzy proxy; no hierarchy snapshot. A heading-level swap can leave `mhs` within slack while tree shape changes.

**Adopt?** Partially. Store `{heading_sequence, table_count}` or a normalized outline hash in baseline rows; diff exactly like pdfplumber's tree gate.

---

### [HIGH] Exact per-cell / per-row content assertions

**pdfplumber:** WARN report pins first two parsed rows exactly (`tests/test_ca_warn_report.py:59-77`); issue-140 pins last table row and column slices (`tests/test_table.py:64-100`).

**guard.py:** Block-matched `nid`/`teds` with `GUARD_AXIS_SLACK=0.02` (`constants.py:94`).

**Adopt?** Yes for a micro-corpus: optional `must_match_rows` or substring anchors beneath fuzzy guard. pdfplumber shows cell-level truth is cheap and catches regressions fuzzy scores miss.

---

### [HIGH] Cardinality / count invariants

**pdfplumber:** Hard counts everywhere: `len(tables)==3` with per-table row counts (`tests/test_table.py:183-186`), `len(p0.edges)==364` (`tests/test_ca_warn_report.py:81`), `len(ixs.keys())==304` (`tests/test_ca_warn_report.py:141`), `len(vertical_edges)==700` (`tests/test_nics_report.py:55-56`).

**guard.py:** No table-count, row-count, or block-count axis in baseline or diff.

**Adopt?** Yes [ACTIONABLE-NOW]. Extend `BenchRow`/baseline with `{table_count, heading_count}` from `bench.py`; fail on any count regression beyond zero slack. A TEDS-preserving table merge/split is invisible today.

---

### [HIGH] Pre-assert normalization layer

**pdfplumber:** `fix_row_spaces` strips intra-cell spaces before row compare (`tests/test_ca_warn_report.py:14-15`, `54-55`); layout golden strips trailing `\n` (`tests/test_utils.py:386-387`).

**guard.py:** Rounds stored baseline metrics to 4 decimals (`guard.py:144`) and rounds **drop** only (`guard.py:177-180`); current-axis values compared raw for floor checks (`guard.py:162`).

**Adopt?** Yes [ACTIONABLE-NOW]. Round **both** `prior` and `cur` to baseline granularity before subtraction and floor compare (symmetric grid). Anchor checks need the same normalizer pdfplumber applies pre-assert.

---

### [HIGH] Baseline metadata ignored on read (`axis_slack`, `floors`)

**pdfplumber:** N/A (no baseline JSON), but tolerances are explicit per test (`snap_x_tolerance=3`, etc., `tests/test_ca_warn_report.py:86-89`).

**guard.py:** Writes `"axis_slack"` and `"floors"` into baseline (`guard.py:141-142`) but `diff_rows` always uses the `slack` parameter defaulting to `C.GUARD_AXIS_SLACK` and hardcoded `_FLOORS` (`guard.py:62`, `205`, `161-163`). A committed baseline with different slack/floors is silently overridden.

**Adopt?** Yes [ACTIONABLE-NOW]. On read: `slack = baseline.get("axis_slack", slack)`; merge `baseline["floors"]` over constants. Without this, `--update` on one branch and `--slack` on CI desyncs the contract pdfplumber-style "pinned thresholds" intend.

---

### [MEDIUM] Multi-path output parity (library vs CLI vs utils)

**pdfplumber:** Same PDF must match across `page.extract_text`, `utils.extract_text(page.chars, ...)`, and CLI stdout against the same golden (`tests/test_utils.py:389-398`, `tests/test_convert.py:299-314`).

**guard.py / `__main__.py`:** Single path: staged candidate MD vs `.gt.md` (`__main__.py:245-260`, `358`). No guard that scoring inputs are stable across entry points.

**Adopt?** No inside guard itself (whisker scores tomd output). Yes as a CI harness check if multiple conversion paths exist.

---

### [MEDIUM] Strategy-equivalence regression (two algorithms, same result)

**pdfplumber:** `table.extract() == t_explicit.extract()` for alternate horizontal strategies (`tests/test_nics_report.py:137-160`); tolerance-variant table settings must agree on key paths (`tests/test_table.py:160`).

**guard.py:** One scoring path via `run_bench`; no cross-strategy sanity check.

**Adopt?** Low for whisker unless tomd exposes alternate extract modes. Pattern worth copying: **orthogonal check** that catches algorithm swaps metric scores hide.

---

### [MEDIUM] Added-corpus-item detection (asymmetric vs missing)

**pdfplumber:** New behavior requires a new committed test/fixture; there is no "silent new paper" (`tests/pdfs/issue-*.pdf` per regression).

**guard.py:** Missing baseline PIDs hard-fail (`guard.py:221`, `114-115`); **new** PIDs pass as `STATUS_NEW` (`guard.py:53`, `169`) without requiring `--update`.

**Adopt?** Yes [ACTIONABLE-NOW]. Fail (or `--allow-new` opt-in) when `current_pids - baseline_pids` is non-empty, mirroring missing-paper symmetry. Otherwise corpus grows without baseline review.

---

### [MEDIUM] Issue-numbered regression fixtures (one bug, one PDF, permanent gate)

**pdfplumber:** `tests/pdfs/issue-{N}-*.pdf` with dedicated tests (`tests/test_issues.py:22+`, `tests/test_table.py:177-186` issue #336 table counts).

**guard.py:** Generic per-axis diff; no linkage from failure to a named regression case.

**Adopt?** Process, not code: map baseline PIDs to issue IDs in baseline JSON comments/metadata. Helps refresh review (`--update` ritual, `__main__.py:329-331`).

---

### [LOW] Statistical vs exact tolerance semantics

**pdfplumber:** All gates are exact (`==`) or fixed integer tolerances (`cluster_list(..., tolerance=3)`, `tests/test_ca_warn_report.py:44-45`). No mean/slack regression.

**guard.py:** Deliberate per-axis slack (`drop > slack`, `guard.py:181`); whisker is **ahead** on corpus metric regression. pdfplumber has nothing equivalent to adopt here.

**Adopt?** Keep whisker slack; borrow pdfplumber's **explicit tolerance documentation** in baseline schema.

---

### [LOW] Refresh ritual

**pdfplumber:** Golden updates = edit committed files in PR (`tests/comparisons/`, inline `SCOTUS`). No CLI `--accept`.

**guard.py:** `whisker guard --update` (`__main__.py:329-367`).

**Adopt?** whisker is stronger. No change.

---

### [LOW] known-bad / expectedFailure

**pdfplumber:** No `expectedFailure` or monotonic weak baselines; every test is expected to pass exactly.

**guard.py:** Monotonic known-bad model (`guard.py:22-24`, `test_guard.py:84-92`).

**Adopt?** Keep whisker pattern; pdfplumber does not expose an alternative.

---

## 2. CALIBRATION GAPS

### [HIGH] No domain-specific invariant thresholds (only fuzzy ROC on one scalar)

**pdfplumber:** Thresholds are engineering constants embedded in tests (`intersection_tolerance: 5`, `tests/test_nics_report.py:65`; `RECT_TOLERANCE = 2`, `tests/test_issues.py:34`; `y_tolerance=5`, `tests/test_dedupe_chars.py:119`). Validated by exact asserts, not ROC.

**calibrate.py:** Fits only `unigram_coverage` fail/review edges via ROC (`__main__.py:488-499`, `calibrate.py:149-185`). No fit for `NID_FLOOR`/`TEDS_FLOOR`/`MHS_FLOOR`, no invariant thresholds.

**Adopt?** Yes. After labeled bench corpus exists, run per-axis ROC on `nid`/`teds`/`mhs` separately (pdfplumber's per-operation tolerance matrix suggests axes are independent). Keep domain invariants (colsum) non-calibratable exact checks.

---

### [HIGH] Dual-threshold coupling (fail edge vs review edge)

**pdfplumber:** Implicit ordering: stricter checks are separate tests on the same fixture, not independent ROC fits.

**calibrate.py:** `fail_fit` and `review_fit` are independent (`__main__.py:494-499`). Nothing enforces `review_edge >= fail_edge`; inverted band is possible on overlapping labels.

**Adopt?** Yes [ACTIONABLE-NOW]. After both fits, assert `review_edge >= fail_edge` or fit review conditional on fail threshold.

---

### [MEDIUM] Tolerance-sensitivity testing (operating-point robustness)

**pdfplumber:** Edge-merge tests sweep `snap_x_tolerance`/`join_y_tolerance` and assert count transitions (`tests/test_ca_warn_report.py:79-128`: 364 edges → 46/52/94/174 merged groups).

**calibrate.py:** Single chosen operating point; no sensitivity report around it.

**Adopt?** Yes. Emit neighbors on ROC curve where FPR/TPR shift materially (pdfplumber's sweep is manual but shows the need).

---

### [MEDIUM] Cross-validation / holdout

**pdfplumber:** Each issue PDF is a permanent holdout for its bug class.

**calibrate.py:** Full-sample fit; no k-fold or held-out PID split.

**Adopt?** Yes when label corpus > ~30 papers. pdfplumber's one-bug-one-fixture pattern is informal holdout whisker should formalize.

---

### [MEDIUM] Class imbalance handling

**pdfplumber:** N/A (no classification calibration).

**calibrate.py:** Maximize TPR at FPR ceiling (`calibrate.py:174-177`) with no minimum precision or positive-count floor beyond `n_pos > 0`.

**Adopt?** Optional: require `n_pos >= k` and report Wilson interval on TPR at chosen point.

---

### [LOW] Per-axis bench calibration

**pdfplumber:** Separate tolerance per sub-operation (cluster vs snap vs join).

**calibrate.py:** Bench floors in `constants.py:56-58` are hand-set; calibrate never touches them.

**Adopt?** Yes when labeled `.gt.md` corpus exists: `calibrate_threshold` on each bench axis independently.

---

### [LOW] Operating-point selection methodology

**pdfplumber:** No ROC; thresholds are "whatever makes the golden pass."

**calibrate.py:** Max TPR at FPR ≤ target, Youden fallback (`calibrate.py:174-180`).

**Adopt?** whisker is ahead. No regression vs pdfplumber.

---

## 3. CONCRETE BUGS/EDGE-CASES IN OUR CODE

### [CRITICAL] `diff_rows` ignores committed `axis_slack` and `floors`

**Scenario:** Baseline committed with `"axis_slack": 0.05`; CI runs without `--slack`. **Function:** `diff_rows` (`guard.py:201-222`). Uses `C.GUARD_AXIS_SLACK=0.02` (`constants.py:94`), stricter than baseline contract → false regressions.

**Fix:** Read baseline fields [ACTIONABLE-NOW].

---

### [HIGH] Added papers pass without baseline update

**Scenario:** Corpus gains `PNEW`; baseline lacks it. **Function:** `_evaluate_paper` → `STATUS_NEW` (`guard.py:165-169`); `GuardReport.failed` ignores new (`guard.py:112-115`). pdfplumber would require an explicit new test commit.

**Fix:** Fail on unexpected PIDs unless `--allow-new` [ACTIONABLE-NOW].

---

### [HIGH] Independent calibrations can invert fail/review band

**Scenario:** Labels yield `fail_edge=0.88`, `review_edge=0.82`. **Function:** `_calibrate_main` (`__main__.py:494-499`). Review threshold flags more aggressively at lower coverage than fail, breaking verdict semantics.

**Fix:** Enforce ordering post-fit [ACTIONABLE-NOW].

---

### [HIGH] Asymmetric metric rounding (baseline grid vs live floats)

**Scenario:** Baseline stores `teds=0.9900`; live `teds=0.98995` rounds to `0.9900` in output but raw drop logic uses full float. **Function:** `_evaluate_paper` (`guard.py:173-180` vs `144`). pdfplumber uses `round(..., 3)` on both sides (`tests/test_dedupe_chars.py:47-48`).

**Fix:** Round `cur` and `prior` to 4 decimals before drop/floor math [ACTIONABLE-NOW].

---

### [MEDIUM] `target_fpr` unvalidated

**Scenario:** `--target-fpr 1.5` or negative. **Function:** `calibrate_threshold` (`calibrate.py:149-154`). Feasible set logic breaks silently.

**Fix:** Reject outside `[0.0, 1.0]` [ACTIONABLE-NOW].

---

### [MEDIUM] Duplicate PIDs in bench rows

**Scenario:** `run_bench` returns two `P1` rows (caller bug). **Function:** `diff_rows` (`guard.py:216-218`) emits duplicate findings; `baseline_from_rows` last-wins in dict (`guard.py:143-146`).

**Fix:** Dedupe or hard-fail on duplicate `pid` [ACTIONABLE-NOW].

---

### [MEDIUM] NaN/Inf metric values

**Scenario:** Broken table extract yields `teds=nan`. **Function:** `_evaluate_paper` (`guard.py:162`, `181`). Comparisons propagate NaN; `drop > slack` is False; status may be `ok` while semantically broken. pdfplumber would fail an exact assert.

**Fix:** Treat non-finite axis values as hard fail [ACTIONABLE-NOW].

---

### [MEDIUM] Baseline schema/kind not validated

**Scenario:** Point guard at `whisker bench` leaderboard JSON (wrong `kind`). **Function:** `_guard_main` (`__main__.py:369-383`) loads any JSON with `rows` key.

**Fix:** Require `kind == whisker-guard-baseline` and matching `schema_version` [ACTIONABLE-NOW].

---

### [LOW] `below_floor` informational on existing papers never fails alone

**Scenario:** Existing paper stays at `teds=0.50` (known weak). **Function:** `_evaluate_paper` (`guard.py:192-197`). Status `ok` with `below_floor` populated (intentional monotonic model, `test_guard.py:84-92`). pdfplumber has no equivalent; not a bug, but reviewers may misread report.

**Fix:** Document in report output only.

---

### [LOW] Empty labeled corpus

**Scenario:** `--labels` is `[]`. **Function:** `_calibrate_main` (`__main__.py:484-486`) exits error. Handled.

---

### [LOW] Single-class labels

**Scenario:** All labels `pass`. **Function:** `calibrate_threshold` (`calibrate.py:166-169`) raises `ValueError`. Handled.

---

### [LOW] Identical coverage values at threshold boundary

**Scenario:** Bad and good both at `0.85`; threshold `0.85` flags neither (`value < threshold`). **Function:** `_confusion` (`calibrate.py:111`). Tie goes to unflagged; pdfplumber uses exact equality asserts instead.

**Fix:** Document strict `<` semantics; optional `<=` mode for fail edge.

---

### [LOW] Unicode / CJK paths

**Scenario:** CJK paper in corpus. **Function:** `run_bench` / metrics (handled in `test_invariants.py:27`). guard itself is PID-agnostic. pdfplumber tests CJK dedupe (`tests/test_dedupe_chars.py:34-62`). No guard-specific bug; metric path already covered.

---

## 4. MISSING AXIS/CHECK

| pdfplumber gate | Evidence | whisker equivalent |
|-----------------|----------|-------------------|
| Domain accounting invariant | `colsum == (total * 2)` (`tests/test_nics_report.py:82-85`) | **None** |
| Exact text golden | `comparisons/scotus-transcript-p1.txt` (`tests/test_utils.py:383-398`) | **None** (metrics only) |
| Structure tree exact snapshot | `SCOTUS` dict (`tests/test_structure.py:1032-1036`) | `mhs` fuzzy only |
| Table/edge cardinality | `len(tables)`, `len(edges)` (`tests/test_table.py:183-186`, `tests/test_ca_warn_report.py:81`) | **None** |
| Negative regex/substring guard | `re.search(...) is None` (`tests/test_utils.py:331-336`) | **None** (gap-matrix #9) |
| Layout shape invariant | `all(len(line)==75 ...)` (`tests/test_utils.py:413-414`) | **None** |
| Multi-strategy equivalence | `table.extract() == t_explicit.extract()` (`tests/test_nics_report.py:137-160`) | **None** |
| Float round-before-compare | `round(x, 3)` (`tests/test_dedupe_chars.py:47-48`, `tests/test_basics.py:221`) | Partial (drop only, `guard.py:180`) |
| Metric identity invariants | implicit via exact output | `test_invariants.py` (whisker **has** this; pdfplumber does not) |

---

## 5. TOP PORTABLE DETAIL

**Adopt:** Per-table **domain accounting invariant** on numeric columns:

```python
for c in COLUMNS[1:]:
    total = parsed_table[-1][c]
    colsum = sum(row[c] or 0 for row in parsed_table)
    assert colsum == (total * 2)
```

**Source:** `tests/test_nics_report.py:81-85` (NICS PDF; doubling reflects month + cumulative sections in that report layout).

**Why:** Reference-free, deterministic, catches table extraction regressions that preserve fuzzy NID/TEDS. Map to whisker as optional baseline `invariants: [{"type": "col_sum", "column": "...", "factor": 2}]` checked before metric diff. Formula is document-specific; the **pattern** (derived structural law on parsed tables) is portable to any GT corpus with known totals row.

**Not adopt wholesale:** pdfplumber's byte-exact `comparisons/*.txt` gate (`tests/test_convert.py:312-314`) is too brittle for markdown conversion QA; use anchors or normalized line hashes instead.
