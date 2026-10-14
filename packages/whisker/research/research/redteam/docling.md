# Red-team: whisker guard/calibrate vs Docling QA

- Docling gates on **801 committed multi-artifact goldens** (JSON + MD + doctags + page meta per item), not scalar metric deltas; whisker guard stores four floats per paper and misses structural regressions Docling would catch at line 1.
- Docling enforces **CI-safe refresh** (`DOCLING_GEN_TEST_DATA=0` in CI via `test_data_gen_flag.py:8-9`) and **2-reviewer Mergify** on `tests/data/**` (`.github/mergify.yml:16-24`); whisker `--update` has no equivalent lockout or review hook.
- Docling uses **tiered tolerances** (strict bbox `0.0025`, fuzzy `0.005`, OCR text NED `<0.4`) with **serialize-then-compare** rounding (`COORD_PREC=2`, `verify_utils.py:23-27,64-72,110-112`); guard applies one global `0.02` slack and ignores the `axis_slack` it writes into the baseline (`guard.py:141` vs `diff_rows` never reading it).
- Docling separates **per-item axis skips** (`SKIP_DOCTAGS_COMPARISON`, `test_e2e_conversion.py:17-20,65-71`) and **xfail known-flaky items** (`test_backend_msword.py:121-132`); guard has monotonic known-bad for metrics only, no per-paper axis exemption or expected-failure bit.
- `calibrate.py` is ahead of Docling on ROC fitting (Docling uses hand-set grade bands `base_models.py:530-538`), but can emit **inverted fail/review edges** and has no **5th-percentile worst-area** operating point like Docling's `low_grade`.

---

## 1. REGRESSION-GATE GAPS

### 1.1 Multi-artifact per-item goldens (exact + fuzzy structural diff)

**Docling:** `verify_conversion_result_v2` compares four committed artifacts per source file: page-cell counts (`.pages.meta.json`), full `DoclingDocument` JSON, exported markdown, and doctags (`verify_utils.py:355-439`). Item-level structure is walked in lockstep: text/table/picture counts, labels, provenance, bbox, per-cell table text (`verify_utils.py:219-344`).

**guard.py:** Stores and diffs only `nid/teds/mhs/overall/reading_order` scalars (`guard.py:65-71,136-147`). A regression that preserves aggregate metrics but breaks table header flags, bbox placement, or markdown line order can pass.

**Adopt?** **Partially.** Full golden replay is out of whisker's scope (tomd outputs markdown, not DoclingDocument JSON), but guard should at minimum diff **committed markdown snippets or sidecar structural fields** alongside metrics. Scalar-only baselines are a strict subset of Docling's contract.

**Severity:** [CRITICAL]

---

### 1.2 Normalization-before-diff with declared serialization precision

**Docling:** Coordinates and confidences are rounded to fixed precision before equality/tolerance checks (`COORD_PREC=2`, `CONFID_PREC=3`, `verify_utils.py:23-24,64-72`). Bbox tolerance is `max(10^-COORD_PREC, page_extent * tol_ratio)` with separate strict/fuzzy ratios (`verify_utils.py:25-27,51-52`).

**guard.py:** Rounds drops to 4 decimals when comparing regression (`guard.py:177-180`) and baseline rows to 4 decimals (`guard.py:144`), but current axis values fed in are unrounded floats from `BenchRow`. No page-extent-relative tolerance; one `GUARD_AXIS_SLACK` for all axes.

**Adopt?** **Yes [ACTIONABLE-NOW].** Round **both** baseline and current axis values to the same 4-decimal grid before subtraction (not only the drop). Consider axis-specific slack (Docling OCR uses fuzzy text NED `<0.4`, `verify_utils.py:110-112`, while strict PDF uses exact line match, `verify_utils.py:100-108`).

**Severity:** [HIGH]

---

### 1.3 Per-item, per-axis conditional gating

**Docling:** Per-file skip lists disable specific comparison axes: `SKIP_DOCTAGS_COMPARISON` (`test_e2e_conversion.py:17,65-71`), `SKIP_E2E_TEST` removes entire items (`test_e2e_conversion.py:20,29-30`), OCR engines skip rotation-incompatible files (`test_e2e_ocr_conversion.py:107-108`), markdown backend uses per-stem `json_filter`/`yaml_filter` (`test_backend_markdown.py:29-30,51-73`).

**guard.py:** Same four regression axes for every paper (`constants.py:99`). No per-`pid` axis mask in baseline.

**Adopt?** **Yes.** Baseline rows should carry optional `"skip_axes": ["teds"]` or `"verify_doctags": false` equivalents so known-noisy papers do not block the corpus.

**Severity:** [HIGH]

---

### 1.4 Known-bad / expectedFailure / xfail semantics

**Docling:** `@pytest.mark.xfail(strict=False)` for flaky `textbox.docx` (`test_backend_msword.py:129-132`); separate failure-scenario corpus in `test_failed_pages.py` excluded from happy-path e2e (`test_e2e_conversion.py:19-20`). Partial-success PDFs assert `ConversionStatus.PARTIAL_SUCCESS`, not golden match (`test_failed_pages.py:99-102`).

**guard.py:** Monotonic known-bad: papers below floor in baseline are not re-flagged unless they worsen (`guard.py:160-198`, tested in `test_guard.py:84-99`). No `expectedFailure` bit, no xfail that allows CI green on a permanently broken item, no `ConversionStatus`-style pre-gate.

**Adopt?** **Partially.** Add baseline `"expected_failure": true` (fail only on regression, never on absolute floor) for items Docling would xfail. Do not copy xfail silently-green semantics wholesale; whisker is a release gate.

**Severity:** [MEDIUM]

---

### 1.5 Refresh ritual CI lockout + governance

**Docling:** Regenerate via `DOCLING_GEN_TEST_DATA=1 uv run pytest` (`CONTRIBUTING.md:76-80`). CI asserts the flag is off (`test_data_gen_flag.py:5-9`). Golden PRs require **two reviewers** when `tests/data/**` changes (`.github/mergify.yml:16-24`).

**guard.py / `__main__.py`:** `--update` rewrites baseline with no env guard (`__main__.py:361-367`). No schema/kind check on read.

**Adopt?** **Yes [ACTIONABLE-NOW].** Refuse `--update` when `CI=true` or a dedicated `WHISKER_GUARD_UPDATE=1` is unset; validate `kind == whisker-guard-baseline` and `schema_version` on load.

**Severity:** [HIGH]

---

### 1.6 Missing-item vs added-item detection

**Docling:** Corpus is a **closed set**: tests discover sources via `rglob` and require matching groundtruth paths (`test_e2e_conversion.py:23-32`, `verify_utils.py:380-385`). A new PDF without goldens fails on missing files, not as "new ok."

**guard.py:** Baseline papers absent from current run are hard-fail `missing` (`guard.py:221,113-115`). **New** papers with no baseline entry pass as `STATUS_NEW` (`guard.py:165-169,169`) unless below floor.

**Adopt?** **Yes [ACTIONABLE-NOW].** Option: `--strict-corpus` fails on any `STATUS_NEW` until baseline is updated, mirroring Docling's closed corpus.

**Severity:** [MEDIUM]

---

### 1.7 Conversion-success precondition

**Docling:** `verify_conversion_result_v2` asserts `ConversionStatus.SUCCESS` before any diff (`verify_utils.py:366-368`).

**guard.py:** Assumes `run_bench` produced valid floats; no check that candidate markdown exists, scoring succeeded, or partial conversion occurred.

**Adopt?** **Yes.** Guard should accept optional per-row `ok: bool` or fail papers whose candidate load was skipped (`__main__.py:256-258` warns and continues).

**Severity:** [MEDIUM]

---

### 1.8 Statistical vs exact tolerance semantics

**Docling:** Strict mode: exact string equality with **line-level** diagnostics (`verify_utils.py:100-108`). Fuzzy mode: normalized Levenshtein `dist/len(gt) < 0.4` (`verify_utils.py:110-112`). Bbox: `math.isclose` with absolute tolerance derived from page size (`verify_utils.py:68-72`).

**guard.py:** Absolute metric drop `> slack` only (`guard.py:180-184`). No fuzzy text path, no relative/NED tolerance.

**Adopt?** **Partially.** For `nid`-like axes, a relative drop cap `(prior-cur)/prior > slack` catches proportional collapse on high baselines. Keep absolute slack for bounded [0,1] metrics.

**Severity:** [MEDIUM]

---

### 1.9 Baseline `axis_slack` field ignored

**Docling:** N/A (exact/fuzzy constants live in verifier module).

**guard.py:** `baseline_from_rows` writes `"axis_slack": C.GUARD_AXIS_SLACK` (`guard.py:141`) but `diff_rows` only uses the function argument / CLI default (`guard.py:201-206`, `__main__.py:334-335`), not the committed baseline value.

**Adopt?** **Yes [ACTIONABLE-NOW].** `slack = baseline.get("axis_slack", slack)` when baseline present; CLI override only with explicit `--slack`.

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

### 1.10 Meta-tests on gate logic

**Docling:** `test_verify_utils.py` parametrize bbox/image fuzziness boundaries (e.g. `254x267` pixel cases, lines 118-161) independent of document fixtures.

**guard.py:** `test_guard.py` covers slack/floor/missing but not duplicate pids, schema mismatch, or baseline slack round-trip.

**Adopt?** **Yes.** Extend guard meta-tests to match Docling's verifier-test depth.

**Severity:** [MEDIUM]

---

## 2. CALIBRATION GAPS

### 2.1 Docling does not ROC-calibrate; it uses fixed grade bands

**Docling:** `_score_to_grade`: `<0.5 POOR`, `<0.8 FAIR`, `<0.9 GOOD`, `>=0.9 EXCELLENT` (`base_models.py:530-538`). Docs tell users to trust **`mean_grade` / `low_grade`**, not raw scores (`docs/concepts/confidence_scores.md:11-13,48-49`).

**calibrate.py:** Sweeps ROC on `unigram_coverage` only; no grade labels, no stability layer above raw thresholds.

**Adopt?** **Partially.** After ROC pick, map edges to named grades (fail/review/pass) and document that raw scores are internal. Docling's fixed bands are not evidence-backed either; whisker's ROC is strictly better if edges are ordered and validated.

**Severity:** [LOW]

---

### 2.2 Worst-area operating point (5th percentile)

**Docling:** Document-level `low_score` = `nanquantile(..., q=0.05)` over component scores (`base_models.py:568-578`); `low_grade` gates on the worst 5%, not the mean.

**calibrate.py:** Maximizes corpus TPR at FPR ceiling on per-paper scalar samples; no percentile/worst-case aggregation.

**Adopt?** **Yes for bench guard calibration.** When fitting bench floors, a paper with `min(nid,teds,mhs)` below threshold catches Docling-style "one bad page" failures better than mean axis scores.

**Severity:** [MEDIUM]

---

### 2.3 Multi-threshold / multi-axis calibration

**Docling:** Four component scores (`layout_score`, `ocr_score`, `parse_score`, `table_score`) plus aggregate grades (`docs/concepts/confidence_scores.md:37-42`, `base_models.py:512-516`).

**calibrate.py:** Only `unigram_coverage` fail and review edges (`__main__.py:488-499`). No `nid/teds/mhs` floor fitting, no advisory `ref_nid` edge.

**Adopt?** **Yes.** Extend calibrate to accept labeled bench rows and fit per-axis floors with the same ROC machinery.

**Severity:** [HIGH]

---

### 2.4 Fail/review edge ordering not enforced

**Docling:** Grades are monotonic by construction (`base_models.py:530-538`).

**calibrate.py:** `fail_fit` and `review_fit` are independent (`__main__.py:494-499`). Nothing requires `fail_edge <= review_edge`.

**Adopt?** **Yes [ACTIONABLE-NOW].** After both fits, assert `fail_edge <= review_edge` or constrain review fit to thresholds `>= fail_edge`.

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

### 2.5 Cross-validation / class imbalance

**Docling:** No held-out calibration (goldens are the contract). Class imbalance handled implicitly by exact per-item tests, not aggregate rates.

**calibrate.py:** Single-sample ROC; no k-fold, no stratification, no minimum per-class count beyond `n_pos/n_neg > 0` (`calibrate.py:164-169`).

**Adopt?** **Yes for whisker.** With 30-50 labels (per `constants.py` doc intent), report bootstrap CIs or leave-one-out max-FPR; warn when `n_pos < 10`.

**Severity:** [MEDIUM]

---

### 2.6 Engine-variant thresholds

**Docling:** Groundtruth paths include OCR engine suffix (`verify_utils.py:378-385`, `engine_suffix = f".{ocr_engine}"`).

**calibrate.py / guard:** Single threshold set; no stratification by `--reference` engine or HTML vs PDF.

**Adopt?** **Later.** If oracle engine affects `unigram_coverage` distribution, calibrate per engine or require `--no-reference` labels only.

**Severity:** [LOW]

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Function | Scenario | Expected failure mode | Actual behavior | Severity |
|----------|----------|----------------------|-----------------|----------|
| `diff_rows` | Baseline committed with `axis_slack: 0.05`, CLI uses default `0.02` | Use baseline slack | Ignores baseline field; uses CLI only (`guard.py:141,205-206`) | [HIGH] [ACTIONABLE-NOW] |
| `diff_rows` | `rows` contains duplicate `pid` | Dedupe or error | Duplicate `findings`; `current_pids` set hides duplication (`guard.py:216-221`) | [MEDIUM] [ACTIONABLE-NOW] |
| `diff_rows` | `baseline["rows"]` has NaN axis (hand-edited JSON) | Reject or fail paper | `NaN < floor` is False; `prior - cur` is NaN; `drop > slack` is False → silent pass (`guard.py:162,180-181`) | [HIGH] [ACTIONABLE-NOW] |
| `diff_rows` | Empty `rows`, baseline has 10 papers | Fail (nothing scored) | `findings=[]`, `missing` has 10 entries → fails correctly (`guard.py:216-222`) | OK |
| `diff_rows` | Empty `rows`, `baseline=None` | Error or vacuous pass | `GuardReport(findings=[], missing=[], failed=False)` (`guard.py:216-222`) | [MEDIUM] |
| `_evaluate_paper` | Existing paper, `teds=0.50` (below floor), stable vs baseline `0.50` | Docling would still fail exact golden | `status=ok` with informational `below_floor` only (`guard.py:192-198`) | By design; document vs Docling |
| `calibrate_threshold` | Sample value `float("nan")` | `ValueError` | Propagates; comparisons undefined (`calibrate.py:110-111`) | [HIGH] [ACTIONABLE-NOW] |
| `calibrate_threshold` | All bad papers score `0.90`, all good `0.95`, `target_fpr=0.0` | Edge in `(0.90,0.95]` | Works; tie-break picks higher threshold (`calibrate.py:177`) | OK |
| `calibrate_threshold` | Single bad, single good, identical value `0.85` | Undefined or max FPR | Youden fallback; both classes at same value (`calibrate.py:179-180`) | [MEDIUM] |
| `_calibrate_main` | Labels: 20 fail, 2 pass | Warn imbalance | Fits without warning (`__main__.py:488-502`) | [MEDIUM] |
| `_calibrate_main` | Fail fit → `0.92`, review fit → `0.88` | Invariant violation | Emits inverted band (`__main__.py:494-499`) | [HIGH] [ACTIONABLE-NOW] |
| `baseline_from_rows` | `slack` param someday added to CLI update vs diff mismatch | Single source of truth | Only written at update time from constants (`guard.py:141`) | [HIGH] |
| `_load_corpus_pairs` | Corpus adds `NEW.gt.md`, no baseline row | Fail until `--update` | Guard passes `STATUS_NEW` (`guard.py:169`, `__main__.py:353-358`) | [MEDIUM] |
| `_evaluate_paper` | Unicode pid / metrics | Stable diff | No normalization issue; metrics already computed | OK |
| `calibrate_threshold` | 10k samples | Performance | O(n * unique values); fine | OK |

---

## 4. MISSING AXIS / CHECK (Docling gates, whisker has no equivalent)

| Docling check | Source | Whisker gap |
|---------------|--------|-------------|
| Page/cell count invariant | `verify_cells` (`verify_utils.py:116-131`) | No page/cell concept in markdown bench |
| Docitem label + provenance + bbox | `verify_docitems` (`verify_utils.py:249-282`) | No structural layout gate in guard |
| Table grid: row/col count, header flags, per-cell text | `verify_table_v2` (`verify_utils.py:134-172`) | `teds` mean only; misses header-bit regressions |
| Picture count + image dimensions | `verify_docitems` + `verify_picture_image_v2` (`verify_utils.py:236-237,195-214`) | Not scored |
| Code language / formula items | `verify_docitems` (`verify_utils.py:330-342`) | Not scored |
| Exported doctags equality | `verify_dt` (`verify_utils.py:351-352,436-438`) | No doctags artifact |
| Markdown export equality (strict) | `verify_md` (`verify_utils.py:347-348,432-434`) | Guard diffs metrics, not MD bytes |
| `ConversionStatus` / partial success | `verify_utils.py:366-368`, `test_failed_pages.py` | No conversion status in bench row |
| Confidence: layout / OCR / parse / table | `PageConfidenceScores` (`base_models.py:512-516`) | Reference-free gates exist in `score.py`, not in guard/bench baseline |
| `low_grade` (5th percentile worst area) | `base_models.py:568-578` | Guard uses per-axis independently, no min-percentile rollup |
| Line-order diagnostic on text fail | `verify_text` strict branch (`verify_utils.py:102-106`) | Guard reports axis drop string only |

---

## 5. TOP PORTABLE DETAIL

**Adopt Docling's fuzzy text gate formula as a secondary tolerance path for text-like axes:**

```python
# verify_utils.py:110-112
dist = levenshtein(gt, pred)
assert dist / len(gt) < fuzzy_threshold  # default fuzzy_threshold=0.4
```

Combined with **serialize-then-compare** at fixed precision before any numeric tolerance:

```python
# verify_utils.py:64-72
true_rounded = round(true_value, COORD_PREC)
pred_rounded = round(pred_value, COORD_PREC)
tol = max(10 ** (-COORD_PREC), (page_extent or 0.0) * tol_ratio)
assert math.isclose(true_rounded, pred_rounded, rel_tol=0.0, abs_tol=tol)
```

**For whisker guard today:** apply the rounding half immediately: round both `prior` and `cur` to 4 decimals before computing `drop`, and add an optional per-axis relative check `(prior - cur) / prior > REL_SLACK` when `prior >= 0.5`. Keep Docling's `0.4` NED as the model for a future `nid` fuzzy slack distinct from absolute `GUARD_AXIS_SLACK=0.02`.

**Single file:line anchor:** `verify_utils.py:110-112` (fuzzy NED ratio) + `verify_utils.py:64-72` (rounded isclose).

---

*Sources: docling clone at `packages/whisker/research/repos/docling/` (June 2026). Whisker: `guard.py`, `calibrate.py`, `constants.py`, `__main__.py`, `test_guard.py`, `test_calibrate.py`.*
