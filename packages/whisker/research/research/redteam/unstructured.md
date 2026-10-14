# Red-team: whisker guard/calibrate vs Unstructured QA

- Unstructured gates on **zero-tolerance `diff -ru` of committed per-doc metric TSV trees** (`check-diff-evaluation-metrics.sh:56-73`), not slack-tolerant float deltas; any 0.001 metric wiggle fails CI unless `OVERWRITE_FIXTURES=true` on a dedicated refresh workflow (`ingest-test-fixtures-update-pr.yml:78`, never set in `ci.yml:287`).
- Unstructured runs **three independent eval strategies** (text-extraction, element-type, table-structure) with **dual text axes** (`cct-accuracy` + `cct-%missing` per row, `evaluate.py:434-435`) plus a **manifest-pinned doc set** (`metrics-json-manifest.txt:1-18`); guard collapses to four floats per pid and ignores percent-missing / element-type entirely.
- Unstructured **normalizes before diff** (JSON→clean-text for output goldens, `check-diff-expected-output.sh:49-52`; quote/whitespace prep for metrics, `text_extraction.py:109-110`) and strips volatile metadata at partition time (`local-single-file.sh:31`); guard diffs raw `BenchRow` floats with asymmetric rounding (baseline stored rounded, drop rounded, operands not).
- **`calibrate.py` is ahead of Unstructured** (no ROC/threshold code in-repo), but Unstructured's hard-won **operating-point engineering** (Levenshtein weights `(2,1,1)`, wild size-ratio sentinel `0.01`, `text_extraction.py:417-421`) exposes gaps: no per-axis bench calibration, no `%missing` edge, no doctype stratification.
- **Top portable detail:** commit **per-doc TSV rows** with **exact diff + `OVERWRITE_FIXTURES` refresh ritual** (`check-diff-evaluation-metrics.sh:46-73`); adopt the dual-axis row shape (`cct-accuracy` + `cct-%missing`) as guard baseline fields.

---

## 1. REGRESSION-GATE GAPS

### 1.1 Zero-tolerance exact snapshot diff (statistical vs exact)

**Unstructured:** `check-diff-evaluation-metrics.sh:56-73` runs `diff -ru "$METRICS_DIR" "$TMP_METRICS_LATEST_RUN_DIR"` with **no numeric slack**; any byte change in the committed metrics tree fails. Refresh is explicit via `OVERWRITE_FIXTURES != "false"` (`:46-55`), never in CI (`ci.yml:287` runs ingest without it; refresh is `workflow_dispatch` only, `ingest-test-fixtures-update-pr.yml:78`).

**guard.py:** `diff_rows` allows `drop > slack` (default `0.02`, `guard.py:180-184`, `constants.py:94`) and only rounds the **drop**, not both operands (`guard.py:177-180`).

**Adopt?** **Partially [ACTIONABLE-NOW].** Deterministic whisker metrics justify slack for benign formatting, but Unstructured proves the refresh contract: CI must never rewrite baselines. Add optional `--exact` mode (zero slack, fail on any 4-decimal delta) for release gates; keep slack for dev. Enforce `--update` never runs in CI (document + check `CI` env).

**Severity:** [HIGH]

---

### 1.2 Multi-file metrics tree + aggregate sidecars

**Unstructured:** Each eval writes **two TSVs per strategy**: per-doc (`all-docs-cct.tsv`, `evaluate.py:357-358`) and aggregate with mean/stdev/count (`aggregate-scores-cct.tsv`, `:361-362`, headers `evaluate.py:53-60`). Strategies are separate directories (`evaluation-metrics.sh:18-23`, `test-ingest-src.sh:81-89`).

**guard.py:** Single JSON blob with per-paper axis dict (`baseline_from_rows`, `guard.py:136-147`); no aggregate sidecar, no stdev/count metadata.

**Adopt?** **Yes.** Export guard baseline as per-doc TSV (pid row) + aggregate JSON sidecar mirroring Unstructured's `aggregate-*.tsv` shape. Catches corpus-level drift even when no single paper crosses slack.

**Severity:** [MEDIUM]

---

### 1.3 Dual text axes (accuracy + percent-missing), not collapsed

**Unstructured:** Text extraction stores **`cct-accuracy` and `cct-%missing` on every row** (`evaluate.py:434-435`, `text_extraction.py:160-203` bag-of-words missing-text). Both are diffed via exact TSV tree diff.

**guard.py:** Bench guard tracks `nid/teds/mhs/overall` only (`constants.py:99`). No `%missing` / content-recall axis in guard despite whisker computing `unigram_coverage` on the score path.

**Adopt?** **Yes [ACTIONABLE-NOW].** Add `percent_missing` or `unigram_coverage` to baseline rows and `GUARD_REGRESSION_AXES`. A nid-stable run can still lose words (Unstructured's `%missing` catches this; nid/block-match may not).

**Severity:** [CRITICAL]

---

### 1.4 Separate modality eval strategies (element-type, table-structure)

**Unstructured:** Three independent gates: `text-extraction`, `element-type`, `table-structure` (`evaluation-metrics.sh:15-24`). Element-type uses structural frequency match (`element_type.py:43-93`, column `element-type-accuracy`, `evaluate.py:497-498`). Table structure exposes nine metrics per doc (`evaluate.py:227-238`).

**guard.py:** `teds` proxies table quality; **no element-type / layout-class axis**. `reading_order` stored but excluded from regression axes (`guard.py:71`, `constants.py:97-99`).

**Adopt?** **Partially.** Element-type has no whisker equivalent today (tomd outputs markdown, not Unstructured elements). **Do adopt** gating `reading_order` with slack, or a future element-count proxy. Table: consider guard fields for table-detection recall/precision if bench grows beyond mean TEDS.

**Severity:** [HIGH]

---

### 1.5 Normalization-before-diff

**Unstructured:** Structured JSON goldens diff **clean extracted text**, not raw JSON (`check-diff-expected-output.sh:49-52` → `json-to-clean-text-folder.sh`). Metrics prep: `standardize_quotes` + `prepare_str` before Levenshtein (`text_extraction.py:109-110`). Permission noise stripped before diff (`check-diff-evaluation-metrics.sh:58`, `clean-permissions-files.sh:21-24`). Partition metadata excluded for reproducibility (`local-single-file.sh:31`).

**guard.py:** Compares raw metric floats from `run_bench`; no normalization layer. Baseline values pre-rounded to 4 decimals (`guard.py:144`) but current `cur` is not (`guard.py:173-180`).

**Adopt?** **Yes [ACTIONABLE-NOW].** Round **both** `prior` and `cur` to 4 decimals before subtraction. Document that guard assumes deterministic `run_bench` (same as Unstructured assumes deterministic partition on pinned tesseract, `ci.yml:107-110`).

**Severity:** [HIGH]

---

### 1.6 Missing / added item detection

**Unstructured:** `diff -ru` on the **entire metrics directory** fails on added/removed files or rows. Per-doc identity is `filename` column (`evaluate.py:434`). Eval corpus pinned by `metrics-json-manifest.txt:1-18` copied via `evaluation-ingest-cp.sh:16-21`. Output file count gated (`check-num-files-output.sh:19-22`).

**guard.py:** Baseline pid **vanish** → hard fail (`guard.py:113-115`, `221`). **New pid** → `STATUS_NEW` passes (`guard.py:165-169`, `__main__.py:393-395`). No file-count invariant. `_load_corpus_pairs` **silently skips** missing candidates (`__main__.py:256-258`), shrinking the corpus without failing if those pids were never baselined.

**Adopt?** **Yes [ACTIONABLE-NOW].** Fail on `STATUS_NEW` unless `--allow-new` or require `--update` to bless additions (mirror Unstructured: new TSV row = diff fail). Optionally gate corpus size vs baseline row count.

**Severity:** [CRITICAL]

---

### 1.7 Known-bad / expectedFailure monotonic guard

**Unstructured:** No monotonic known-bad pattern. Exact diff means even a **stable bad** metric snapshot must match committed bytes. (Improvement also requires refresh.)

**guard.py:** Tabula-style monotonic model: paper below floor in baseline stays `ok` if stable (`guard.py:192-198`, `test_guard.py:84-92`).

**Adopt?** **Keep whisker's model** for bench metrics (hand-set floors + intentional weak baselines). Unstructured avoids the problem by exact snapshots, not by semantics. Document that `--update` is required to bless improved weak papers.

**Severity:** [LOW] (design difference, not a whisker bug)

---

### 1.8 Floors as backstop

**Unstructured:** No absolute metric floors in the diff scripts; the committed snapshot **is** the floor.

**guard.py:** `_FLOORS` for nid/teds/mhs (`guard.py:62`, `constants.py:56-58`); `crossed_floor` for sub-slack downward floor cross (`guard.py:185-190`). `overall` has no floor.

**Adopt?** **Keep.** Whisker floors are the backstop Unstructured lacks when baselines go stale. Ensure `baseline["floors"]` is honored if edited (`baseline_from_rows:142` writes floors but `diff_rows` reads `_FLOORS` from constants only — **drift risk**).

**Severity:** [MEDIUM] [ACTIONABLE-NOW]: read floors from baseline payload when present.

---

### 1.9 Refresh ritual governance

**Unstructured:** Refresh runs on x86_64 Docker matching CI tesseract (`ingest-test-fixtures-update.sh:24-49`), opens PR via `create-pull-request` with explicit paths (`ingest-test-fixtures-update-pr.yml:116-120`), assigns reviewer = actor.

**guard.py:** `--update` rewrites baseline locally (`__main__.py:361-367`); no schema check, no PR template, no hardware pin.

**Adopt?** **Process, not code.** Require baseline diff review in PR checklist. Optional: `--update` refuses when `CI=true`.

**Severity:** [MEDIUM]

---

### 1.10 Committed output goldens (in addition to metrics)

**Unstructured:** Layer 1: structured JSON exact diff (`check-diff-expected-output.sh:48-67`). Layer 2: markdown/HTML derivative diffs (`check-diff-expected-output-markdown.sh:45-61`). Layer 3: metrics TSV diff.

**guard.py:** Metrics-only gate on labeled `.gt.md` corpus; no committed candidate markdown snapshot.

**Adopt?** **No for guard** (whisker scores conversion quality, not ingest connector output). **Yes** as optional `--snapshot-md` hash per pid in baseline for tomd output regression.

**Severity:** [LOW]

---

## 2. CALIBRATION GAPS

Unstructured **does not ROC-calibrate**; thresholds are engineering constants. `calibrate.py` is still ahead, but Unstructured exposes what to calibrate:

### 2.1 Multi-metric operating points (accuracy + %missing)

**Unstructured:** Text gate uses **two coupled metrics** per document (`evaluate.py:434-435`); both must match snapshots. `%missing` uses bag-of-words recall (`text_extraction.py:185-203`), analogous to whisker `unigram_coverage`.

**calibrate.py:** Fits only `unigram_coverage` fail/review edges (`__main__.py:490-498`). Does not calibrate bench floors (`NID_FLOOR`, etc.) or a `%missing`-style axis on labeled bench data.

**Adopt?** **Yes.** Run `calibrate_threshold` separately for `unigram_coverage` (score path) and, on labeled bench JSON, for `1 - percent_missing` if added to guard rows. Record both TPR/FPR in `thresholds.json`.

**Severity:** [HIGH]

---

### 2.2 Per-axis / per-strategy calibration

**Unstructured:** Separate calculators with distinct metrics (`TextExtractionMetricsCalculator`, `ElementTypeMetricsCalculator`, `TableStructureMetricsCalculator`, `evaluate.py:342-507`). No single `overall` score gates CI.

**calibrate.py:** Single scalar per call; no nid/teds/mhs joint fit. Floors in `constants.py:56-58` remain hand-set.

**Adopt?** **Yes.** Extend calibrate to accept labeled bench CSV with per-axis labels (or proxy labels from floor breaches) and emit per-axis operating points.

**Severity:** [MEDIUM]

---

### 2.3 Stratified thresholds (doctype / connector)

**Unstructured:** `get_mean_grouping` exports aggregates by `doctype` or `connector` (`evaluate.py:510-596`, columns on every row `evaluate.py:411-412`).

**calibrate.py:** Pooled ROC only; no grouping.

**Adopt?** **Later.** WG21 corpus is mostly PDF/HTML papers, not multi-connector. Revisit if corpus stratifies.

**Severity:** [LOW]

---

### 2.4 Cross-validation / warm-up sample size

**Unstructured:** Performance regression uses rolling **median** over `--window 20` with `--min-samples 5` warm-up before gating (`compare_benchmark.py:228-235`, `197-198`). Prevents single outlier baseline.

**calibrate.py:** Fits on all labels in one shot; no holdout, no min-n warning beyond class emptiness (`calibrate.py:164-169`).

**Adopt?** **Yes.** Add `--min-samples` and k-fold or simple holdout reporting in calibration output. Small-n fitted edges are overfit (Unstructured avoids this by exact snapshots, not fitting).

**Severity:** [MEDIUM]

---

### 2.5 Class imbalance and tie semantics

**Unstructured:** Implicitly handles imbalance via per-doc rows (one bad doc fails diff). Wild size-ratio sends accuracy to sentinel `0.01` (`evaluate.py:417-421`).

**calibrate.py:** `target_fpr=0.05` default (`calibrate.py:43`); tie-break prefers higher threshold (`calibrate.py:177`). No per-class weighting. Sentinel behavior for pathological inputs not modeled.

**Adopt?** **Partially [ACTIONABLE-NOW].** Log `n_pos/n_neg` and warn when `n_pos < 10`. Reject calibration when any labeled value is NaN/inf.

**Severity:** [MEDIUM]

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Scenario | Function | What breaks |
|----------|----------|-------------|
| **New pid in corpus** | `diff_rows` / `_evaluate_paper` | Returns `STATUS_NEW` (passes) while Unstructured would fail TSV diff on new row (`guard.py:165-169`). Corpus can grow without baseline review. [CRITICAL] [ACTIONABLE-NOW] |
| **Candidate missing, pid not in baseline** | `_load_corpus_pairs` + `diff_rows` | Skip with warning (`__main__.py:256-258`); no fail. Unstructured fails if output dir empty (`check-diff-expected-output.sh:41`). [HIGH] |
| **Duplicate pid in `rows`** | `diff_rows` | Emits duplicate `GuardFinding` entries; `to_dict` not deduped (`guard.py:216-218`). [MEDIUM] |
| **Baseline `axis_slack` ignored** | `diff_rows` | Writes `axis_slack` in baseline (`guard.py:141`) but always uses CLI `slack` arg (`guard.py:205`, `383`); committed slack can lie. [HIGH] [ACTIONABLE-NOW] |
| **Baseline `floors` ignored** | `_evaluate_paper` | Uses module `_FLOORS` from constants (`guard.py:62`), not `baseline["floors"]` (`guard.py:142-143`). [MEDIUM] [ACTIONABLE-NOW] |
| **Asymmetric float grid** | `_evaluate_paper` | `prior=0.9700` stored, `cur=0.949999999` → drop rounds to `0.0200` not `0.0201`; boundary flips vs rounding both sides. [HIGH] [ACTIONABLE-NOW] |
| **NaN / inf axis value** | `_evaluate_paper` | `nan < floor` is False; `drop > slack` is False; paper passes silently. [HIGH] [ACTIONABLE-NOW] |
| **Stable below-floor existing paper** | `_evaluate_paper` | `below_floor` populated but `status=ok` (`guard.py:192-198`); CI green while metric violates `NID_FLOOR`. Intentional monotonic model, but unlike Unstructured exact gate. [MEDIUM] |
| **Empty `rows`, nonempty baseline** | `diff_rows` | All baseline pids in `missing` → fail (`guard.py:221`). OK. |
| **Empty labeled corpus** | `calibrate_threshold` | Blocked at CLI (`__main__.py:484-486`). OK. |
| **Single class labels** | `calibrate_threshold` | `ValueError` (`calibrate.py:166-169`). OK. |
| **Identical good/bad values** | `calibrate_threshold` | Any threshold flags both; Youden fallback (`calibrate.py:178-180`, `test_calibrate.py:37-49`). OK but precision undefined at `tp+fp=0` (`calibrate.py:142`). [LOW] |
| **All labels same class after filter** | `_load_labeled_samples` | Not reached if upstream passes. OK. |
| **Huge corpus** | `diff_rows` | O(n) per paper; fine. Unstructured diff O(tree). OK. |
| **Unicode pid** | `baseline_from_rows` | JSON UTF-8; OK if consistent casing (`__main__.py:253` uppercases). [LOW] |
| **Wild text length ratio** | N/A in whisker | Unstructured assigns `accuracy=0.01` (`evaluate.py:417-421`); whisker bench has no analogous sentinel — block-match fallback only (`constants.py:116-118`). A pathological paper could score misleadingly. [MEDIUM] |

---

## 4. MISSING AXIS / CHECK

| Unstructured gate | Whisker equivalent | Gap |
|-------------------|-------------------|-----|
| `cct-accuracy` (Levenshtein score, weights `(2,1,1)`, `text_extraction.py:57-117`) | `nid` (block-matched NID) | Different formula; guard does not document comparability. |
| `cct-%missing` (BOW missing fraction, `text_extraction.py:160-203`) | `unigram_coverage` on score path only | **Not in guard baseline.** [CRITICAL] |
| `element-type-accuracy` (`element_type.py:43-93`) | none | Layout taxonomy not scored. |
| Table structure 9-metric bundle (`evaluate.py:227-238`) | `teds` only | No detection recall/precision/F1 gate. |
| Structured JSON golden diff | none | Output snapshot not gated. |
| File count invariant (`check-num-files-output.sh:19-22`) | none | Partial corpus can pass. |
| Metadata-stability partition args | none | Whisker inherits tomd output as-is. |
| Performance median regression (`compare_benchmark.py:237-238`, threshold `0.30`) | none | Out of scope for quality guard; note for runtime CI. |

---

## 5. TOP PORTABLE DETAIL

**Adopt:** Unstructured's **per-document metrics-as-snapshots** with **exact tree diff** and **explicit `OVERWRITE_FIXTURES` refresh**, plus the **dual-axis row shape** (`cct-accuracy`, `cct-%missing`).

**Source:** `check-diff-evaluation-metrics.sh:46-73` (refresh + `diff -ru` gate); `evaluate.py:434-435` (row schema); `metrics-json-manifest.txt:1-18` (pinned eval corpus).

**Concrete whisker mapping:**

1. Baseline JSON rows add `"percent_missing": <float>` (or reuse `1 - unigram_coverage` on bench pairs) alongside `nid/teds/mhs`.
2. Guard fails on any pid row change beyond slack **or** any pid present/missing vs baseline (fail new pids by default).
3. `--update` is the only writer; CI sets no update flag (mirror `OVERWRITE_FIXTURES` default `false`, `check-diff-evaluation-metrics.sh:14`).
4. Optional: export `guard-baseline/<pid>.tsv` for human diff review like Unstructured's committed tree.

**Severity:** [CRITICAL] [ACTIONABLE-NOW] for items 2-3; dual-axis field is highest-value metric addition.
