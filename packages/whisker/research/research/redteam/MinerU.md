# Red-team: whisker guard + calibrate vs MinerU QA

**Repo deep-read:** `packages/whisker/research/repos/MinerU` (master, June 2026). MinerU ships **one** PDF e2e fixture (`tests/unittest/pdfs/test.pdf`), **no** committed conversion goldens, **no** metric baseline regression, **no** ROC calibration. Its QA surface is (a) **typed per-block assertions** on runtime `content_list.json` (`test_e2e.py:152-220`), (b) **parse-method-stratified** substring/fuzzy thresholds (`test_e2e.py:198-201`), (c) a **code-coverage meta-gate** (`get_coverage.py:20`, `cli.yml:37-39`), and (d) external OmniDocBench leaderboard claims in `README.md` (not in-repo). whisker guard/calibrate are ahead on committed per-paper regression plumbing; MinerU exposes gaps in modality-local checks, substring anchors, backend-specific thresholds, and HTML/equation axes.

## Summary (5 bullets)

- **[CRITICAL]** MinerU gates **per block type** (image caption, table caption+body substrings, equation LaTeX tokens, text `fuzz.ratio`) on `content_list.json` (`test_e2e.py:159-219`); `guard.py` diffs four corpus-level floats only (`guard.py:172-184`) and misses localized regressions MinerU would catch at the cell/token level.
- **[HIGH][ACTIONABLE-NOW]** MinerU requires **modality coverage** (`len(type_set) >= 4`, `test_e2e.py:220`) and **parse-method-specific** table hit rates (`0.9` txt/ocr vs `0.7` vlm, `test_e2e.py:198-201`); guard has no modality-presence axis and one global `GUARD_AXIS_SLACK` for all backends (`constants.py:94-99`).
- **[HIGH]** MinerU uses **hand-set fuzzy thresholds** (`fuzz.ratio > 90`, `correct_count > 0.9 * len(targets)`, `test_e2e.py:163-199`) with **no committed snapshot diff**; guard has regression baselines but `calibrate.py` fits only `unigram_coverage`, not NID/TEDS/MHS or MinerU-style per-modality ratios.
- **[MEDIUM][ACTIONABLE-NOW]** MinerU CI runs **txt and ocr paths in one test** (`test_e2e.py:50-71`) and gates **code coverage >= 20%** (`get_coverage.py:20`), not conversion-quality regression; guard has no dual-backend baseline dimension and no meta-gate that bench actually ran the full corpus.
- **[HIGH][ACTIONABLE-NOW]** Concrete foolers: table-free papers get `teds=1.0` (`bench.py:128-129`) so guard diffs a synthetic axis; duplicate PIDs silently overwrite in `baseline_from_rows` (`guard.py:143-146`); `calibrate_threshold` can emit **inverted fail/review edges** (`__main__.py:494-499`).

---

## 1. REGRESSION-GATE GAPS

### 1.1 Typed per-block assertions (not scalar metrics)

**MinerU:** `assert_content` walks each `content_list.json` entry and switches on `type`: image caption `fuzz.ratio > 90` (`test_e2e.py:161-169`), table caption ratio + `validate_html(table_body)` + substring hit count (`test_e2e.py:171-203`), equation LaTeX token presence (`test_e2e.py:205-209`), text block `fuzz.ratio > 90` (`test_e2e.py:211-218`).

**guard.py:** Stores/diffs `nid/teds/mhs/overall` per paper (`guard.py:65-71,136-147`). A regression that drops table cell `"0.98740"` but preserves aggregate TEDS can pass guard and fail MinerU (`test_e2e.py:181-199`).

**Adopt?** **Partially [CRITICAL].** Full `content_list` replay is out of scope for markdown bench, but guard should support optional per-paper **anchor facts** (required substrings per modality) beneath fuzzy metrics, matching MinerU's table `target_str_list` pattern.

---

### 1.2 Modality coverage minimum (structural completeness)

**MinerU:** Requires at least four distinct block types in output: `assert len(type_set) >= 4` (`test_e2e.py:157,220`).

**guard.py:** No check that bench output still covers image/table/equation/text modalities. A paper that loses entire block classes can still show stable `overall` if remaining axes hold.

**Adopt?** **Yes [HIGH][ACTIONABLE-NOW].** Add baseline field `modalities_present: ["text","table",...]` or gate on GT-derived modality flags; fail when a class disappears.

---

### 1.3 Parse-method / backend-stratified thresholds

**MinerU:** Same fixture run under `parse_method="txt"` and `"ocr"` (`test_e2e.py:50-71`); table substring gate is `correct_count > 0.9 * len(target_str_list)` for txt/ocr but `> 0.7 * len(...)` for vlm (`test_e2e.py:198-201`).

**guard.py:** Single slack and floors for all papers (`constants.py:56-58,94-99`). Baseline carries no `parse_method` or engine variant.

**Adopt?** **Yes [HIGH].** Baseline rows should record scoring context (`reference_engine`, source format). Apply stricter slack for deterministic paths, looser for oracle/VLM backends, mirroring MinerU's 0.9 vs 0.7 split.

---

### 1.4 Committed golden snapshot diff

**MinerU:** Generates `test_content_list.json` under `tests/unittest/output/` at test time (`test_e2e.py:57-59,125-128`). **No** committed expected JSON; assertions use **inline hardcoded strings** (`test_e2e.py:166-167,181-192,216-217`). No `--update` / `--bless` ritual.

**guard.py:** Committed per-paper baseline JSON + explicit `--update` (`__main__.py:329-367`). **Ahead of MinerU.**

**Adopt?** **Keep guard pattern.** MinerU is the anti-pattern (non-reproducible output dir, no PR-reviewed snapshot refresh).

---

### 1.5 Per-item regression vs aggregate

**MinerU:** Single-item test only (`tests/unittest/pdfs/test.pdf`); no corpus mean, no per-item baseline delta. External OmniDocBench numbers in `README.md:88-89` are publish-only.

**guard.py:** Per-paper, per-axis diff (`guard.py:172-184`). **Ahead.**

**Adopt?** **Keep.**

---

### 1.6 Floors and known-bad semantics

**MinerU:** Hard floors inline: `fuzz.ratio > 90`, substring hit rate `> 0.9` (or `0.7` vlm). No monotonic known-bad baseline; every run re-asserts absolute bars.

**guard.py:** Absolute `_FLOORS` plus monotonic known-bad (stable below-floor papers not re-flagged, `guard.py:171-198`; `test_guard.py:84-99`). **Ahead on regression semantics.**

**Adopt?** **Keep monotonic model.** Optionally expose MinerU-style **absolute re-check** mode for release branches.

**Severity:** [LOW]

---

### 1.7 Missing / added item detection

**MinerU:** Closed single-PDF corpus by construction. No detection of added/removed benchmark PDFs.

**guard.py:** `missing` baseline PIDs hard-fail (`guard.py:220-221,113-115`); new PIDs get `STATUS_NEW` (`guard.py:165-169`).

**Gap:** `_load_corpus_pairs` skips papers without staged MD with a warning (`__main__.py:256-258`), so removing a `.gt.md` drops the paper from the run without populating `missing` if baseline row still exists.

**Adopt?** **Yes [MEDIUM][ACTIONABLE-NOW].** Cross-check corpus file list vs baseline keys before diff; fail on silent skips.

---

### 1.8 Normalization-before-diff

**MinerU:** Compares raw extracted strings via `fuzz.ratio` and Python `in` on `table_body` HTML (`test_e2e.py:164-196`). No committed normalizer version.

**guard.py:** Metrics flow through OmniDocBench `normalized_text` / block matching (`bench.py:153-157`, `match.py` per CLAUDE.md). Baseline does not record normalizer generation.

**Adopt?** **Yes [MEDIUM].** Pin `metric_version` / normalizer id in baseline payload so formatting-only pipeline changes trigger explicit refresh, not silent metric drift.

---

### 1.9 Tolerance semantics: fuzzy ratio vs absolute slack

**MinerU:** **Relative fuzzy match:** `fuzz.ratio(a,b) > 90` (scale 0-100, effectively 10% edit budget per block, `test_e2e.py:163-168,213-218`). Table cells: **fraction of anchors found** `correct_count / len(targets) > 0.9` (`test_e2e.py:194-199`).

**guard.py:** Absolute drop `round(prior - cur, 4) > slack` on [0,1] metrics (`guard.py:177-184`).

**Adopt?** **Partially [HIGH].** For `nid`-like axes, add optional **relative drop** `(prior-cur)/prior > rel_slack` when baseline high (MinerU's ratio gate is inherently relative-to-reference). Keep absolute slack for bounded scores.

---

### 1.10 Refresh ritual + CI lockout

**MinerU:** No baseline refresh command. CI runs `coverage run` + `get_coverage.py` only (`cli.yml:31-39`); `--update` equivalent does not exist.

**guard.py:** `whisker guard --update` rewrites baseline with no `CI=true` guard (`__main__.py:361-367`).

**Adopt?** **Yes [MEDIUM][ACTIONABLE-NOW].** Refuse `--update` in CI unless `WHISKER_GUARD_UPDATE=1`, matching the intent of repos that never auto-refresh in CI (MinerU simply has nothing to refresh).

---

### 1.11 Baseline `axis_slack` field ignored on read

**guard.py:** Writes `"axis_slack"` at baseline creation (`guard.py:141`) but `diff_rows` uses only the function argument / CLI default (`guard.py:205-206`, `__main__.py:334-335`), not `baseline.get("axis_slack")`.

**Adopt?** **Yes [HIGH][ACTIONABLE-NOW].** Honor committed slack when baseline present.

---

### 1.12 Statistical vs exact

**MinerU:** Deterministic string/fuzzy checks on one PDF; no statistical aggregation, no mean hiding.

**guard.py:** Deterministic per-paper floats; no stochastic layer. **Aligned.**

---

## 2. CALIBRATION GAPS

### 2.1 MinerU does not ROC-calibrate; uses fixed engineering thresholds

**MinerU:** `fuzz.ratio > 90` for text/image captions (`test_e2e.py:163-168,213-218`); table anchors `correct_count > 0.9 * len(target_str_list)` txt/ocr, `> 0.7 *` vlm (`test_e2e.py:198-201`). No sweep, no TPR/FPR reporting.

**calibrate.py:** Full ROC sweep + max-TPR-at-FPR for `unigram_coverage` only (`calibrate.py:149-185`, `__main__.py:488-499`). **Ahead on methodology** for the one axis it covers.

**Adopt?** **Extend calibrate**, not revert to MinerU hand-sets. Record chosen edges beside MinerU-comparable ratios (e.g. map NID to equivalent `ratio > 90` operating point).

**Severity:** [MEDIUM]

---

### 2.2 Per-modality / per-axis calibration

**MinerU:** Distinct thresholds per block type and parse method (text ratio 90, table substring 90%/70%, equation token presence binary, `test_e2e.py:159-203`).

**calibrate.py:** Single scalar per run (`unigram_coverage` fail/review). No fit for `nid`, `teds`, `mhs`, caption ratio, or table hit-rate.

**Adopt?** **Yes [HIGH].** Accept labeled bench rows; run the same ROC machinery per axis with MinerU-style stratification (table-only labels for TEDS floor, etc.).

---

### 2.3 Operating-point selection

**MinerU:** Fixed operating points (90, 90%, 70%). No FPR ceiling, no Youden fallback.

**calibrate.py:** `max_tpr_at_fpr` with `DEFAULT_TARGET_FPR=0.05`, Youden fallback (`calibrate.py:43-46,174-180`). **Strictly better** when labels exist.

**Gap:** No **worst-case** operating point (MinerU asserts every block in the one PDF; whisker could miss one bad paper in a mean).

**Adopt?** **Yes [MEDIUM].** After ROC, report corpus `min(unigram_coverage)` at chosen edge and flag if any labeled-bad paper sits above edge.

---

### 2.4 Multi-threshold ordering (fail vs review)

**MinerU:** Implicit ordering: equation checks are binary; text/table use nested thresholds (90 ratio inside 90% anchor coverage).

**calibrate.py:** Independent `fail_fit` and `review_fit` (`__main__.py:494-499`); no invariant `fail_edge <= review_edge`.

**Adopt?** **Yes [HIGH][ACTIONABLE-NOW].** Enforce monotonic band after both fits.

---

### 2.5 Cross-validation / class imbalance

**MinerU:** One PDF, deterministic pass/fail; no held-out set, no class balance (not applicable at n=1).

**calibrate.py:** Single-sample ROC; requires both classes (`calibrate.py:164-169`) but no minimum count, no bootstrap CI, no warning on 20:2 label skew.

**Adopt?** **Yes [MEDIUM].** Warn when `n_pos < 10` or `n_neg < 10`; document that MinerU-scale corpora (n=1) cannot calibrate meaningfully.

---

### 2.6 Metric choice mismatch

**MinerU:** `fuzzywuzzy.fuzz.ratio` on raw block text (`test_e2e.py:7-8,164-167`).

**calibrate.py / guard:** `unigram_coverage` (token-set recall) and block-matched NID for bench (`bench.py:157-158`). Different scale and invariances.

**Adopt?** **Document mapping.** Calibrating coverage does not set MinerU-equivalent `ratio > 90` edges; either add `text_fuzz_ratio` as a calibratable metric or publish conversion table between NID and fuzz.ratio on WG21 corpus.

**Severity:** [MEDIUM]

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Function | Scenario | MinerU lesson | Actual behavior | Severity |
|----------|----------|---------------|-----------------|----------|
| `_table_score` / `diff_rows` | GT and candidate have **no tables** | MinerU still asserts table substrings when `type=="table"` exists (`test_e2e.py:171-203`) | `teds=1.0` always (`bench.py:128-129`); guard diffs meaningless 1.0→1.0 or false regression on synthetic 1.0 | [HIGH] [ACTIONABLE-NOW] |
| `baseline_from_rows` | Duplicate `pid` in `rows` | MinerU has one doc name | Last row wins silently in dict comp (`guard.py:143-146`) | [MEDIUM] [ACTIONABLE-NOW] |
| `diff_rows` | Hand-edited baseline NaN axis | MinerU asserts would fail loudly | `NaN < floor` False; `drop > slack` False → silent pass (`guard.py:162,180-181`) | [HIGH] [ACTIONABLE-NOW] |
| `diff_rows` | `baseline["axis_slack"]=0.05`, CLI default 0.02 | MinerU thresholds are inline constants | Ignores baseline slack (`guard.py:141,205-206`) | [HIGH] [ACTIONABLE-NOW] |
| `diff_rows` | Paper loses table modality; NID/TEDS unchanged on remaining text | MinerU `len(type_set) >= 4` fails (`test_e2e.py:220`) | Guard passes if metrics stable | [CRITICAL] |
| `_load_corpus_pairs` | `.gt.md` removed, baseline row remains | MinerU fixed corpus | Paper skipped, not in `missing` (`__main__.py:256-258`, `guard.py:220-221`) | [MEDIUM] [ACTIONABLE-NOW] |
| `diff_rows` | Empty `rows`, `baseline=None` | n/a | Vacuous pass: `failed=False` (`guard.py:216-222`) | [MEDIUM] |
| `calibrate_threshold` | Sample contains NaN | MinerU uses string ops | Undefined comparisons (`calibrate.py:110-111`) | [HIGH] [ACTIONABLE-NOW] |
| `calibrate_threshold` | All labels same class | MinerU always has pass+fail implicit in asserts | `ValueError` (`calibrate.py:166-169`) | OK |
| `calibrate_threshold` | Bad/good tie at 0.85 | MinerU exact asserts | Youden fallback; ambiguous edge (`calibrate.py:179-180`) | [MEDIUM] |
| `_calibrate_main` | Fail edge 0.92, review edge 0.88 | MinerU nested thresholds imply order | Emits inverted band (`__main__.py:494-499`) | [HIGH] [ACTIONABLE-NOW] |
| `_evaluate_paper` | `prior=0.905`, `cur=0.895`, nid floor 0.90 | MinerU absolute `> 90` ratio | `crossed_floor` (`guard.py:185-190`) | OK (by design) |
| `run_bench` | Unicode-heavy WG21 paper | MinerU test uses English PDF only | Metrics computed; guard stores rounded axes (`guard.py:98-99`) | OK |
| `calibrate_threshold` | 10k samples | n/a | O(n × unique values); acceptable (`calibrate.py:171-172`) | OK |

---

## 4. MISSING AXIS / CHECK (MinerU gates, whisker has no equivalent)

| MinerU check | Source | Whisker gap |
|--------------|--------|-------------|
| Image caption fuzzy match (`fuzz.ratio > 90`) | `test_e2e.py:161-169` | No figure/caption axis in bench or guard |
| Table HTML well-formedness | `validate_html` + assert (`test_e2e.py:144-149,180`) | TEDS only; no parseability gate on table HTML |
| Table cell **substring anchors** (11 literals, hit-rate gate) | `test_e2e.py:181-199` | No required-token facts file |
| Equation LaTeX token presence (`$$`, `lambda`, `frac`, `bar`) | `test_e2e.py:205-209` | No formula/CDM axis |
| Text block **fuzz.ratio > 90** per block | `test_e2e.py:211-218` | NID is block-matched corpus score, not per-block ratio floor |
| Modality diversity `len(type_set) >= 4` | `test_e2e.py:220` | No structural completeness check |
| Dual parse path (txt **and** ocr) on same input | `test_e2e.py:50-71` | Single candidate path per guard run |
| VLM-relaxed table threshold (70% vs 90%) | `test_e2e.py:200-201` | No backend-specific threshold table |
| Code-coverage meta-gate (>= 20% lines) | `get_coverage.py:20`, `cli.yml:37-39` | No meta-gate that guard/bench executed all baseline papers without skip |
| Committed `content_list.json` golden diff | absent (runtime output only) | Guard diffs metrics, not intermediate JSON |

---

## 5. TOP PORTABLE DETAIL

**Adopt MinerU's modality-stratified table gate: substring hit-rate with parse-method-specific operating point.**

```python
# test_e2e.py:181-201
target_str_list = ["Model", "Testing", "Error", ...]
correct_count = sum(1 for t in target_str_list if t in content_dict["table_body"])
if parse_method in ("txt", "ocr"):
    assert correct_count > 0.9 * len(target_str_list)
elif parse_method == "vlm":
    assert correct_count > 0.7 * len(target_str_list)
```

Combined with per-type text fuzzy floor:

```python
# test_e2e.py:213-218
assert fuzz.ratio(content_dict["text"], expected_paragraph) > 90
```

**For whisker today:** add optional per-paper `facts.json` with `{ "table_substrings": [...], "min_hit_rate": 0.9 }` (0.7 when baseline marks `backend: vlm`), checked in guard **before** or **alongside** scalar TEDS/NID diff. This is the single highest-signal MinerU pattern guard lacks: **localized, modality-specific anchors** that holistic TEDS cannot replace.

**Single file:line anchor:** `test_e2e.py:194-201` (hit-rate formula + txt/ocr vs vlm split).

---

*Sources: MinerU clone at `packages/whisker/research/repos/MinerU/`. Whisker: `guard.py`, `calibrate.py`, `bench.py`, `constants.py`, `__main__.py`, `test_guard.py`, `test_calibrate.py`.*
