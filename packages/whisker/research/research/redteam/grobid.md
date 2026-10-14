# Red-team: whisker guard/calibrate vs GROBID QA

**Source repo:** `packages/whisker/research/repos/grobid` (kermitt2/grobid, shallow clone 2026-06-25)

## Summary

- GROBID gates quality via **committed, versioned benchmark snapshots** (`doc/benchmarks/*.md`) compared manually at release; CI runs unit tests only, never `jatsEval`/`teiEval` (`ci-build-unstable.yml:31-32`). whisker `guard` is **ahead** on automated per-item regression but should adopt GROBID's **snapshot publication ritual** alongside `--update`.
- GROBID scores **four matching tiers** (strict / soft / Levenshtein≥0.8 / Ratcliff≥0.95) with **pre-compare normalization** on every textual field (`EndToEndEvaluation.java:453-461`, `:66-67`, `:2090-2159`). guard uses one scalar slack on rolled-up axes; formatting-only churn can false-regress or miss real field loss.
- GROBID never collapses to one number: **per-field micro/macro P/R/F1**, **section strata** (header / citation / fulltext), **instance-level recall**, and **corpus-specific field nulling** (`Stats.java:232-278`, `EndToEndEvaluation.java:488-527`, `Benchmarking-pmc.md:38-111`). guard diffs only `nid/teds/mhs/overall`; a table-only collapse inside a healthy `overall` is invisible unless `teds` alone drops > slack.
- **Concrete whisker bugs exposed:** baseline `axis_slack`/`floors`/`kind` written but not read on diff; duplicate PIDs duplicate findings; `calibrate_threshold` can emit `fail_edge > review_edge`; NaN/inf samples silently skew ROC.
- **Top portable detail:** adopt GROBID's **relative Levenshtein pass rule** `pct = (max_len - distance) / max_len; pass iff pct >= 0.8` on normalized text (`EndToEndEvaluation.java:1126-1134`, `:1479-1487`) as a second regression tier beneath strict axis slack.

---

## 1. REGRESSION-GATE GAPS

### 1.1 Committed benchmark snapshots + human diff ritual (no CI auto-gate)

GROBID publishes frozen end-to-end numbers per release in `doc/benchmarks/Benchmarking-pmc.md` (version **0.9.0**, dataset **PMC_sample_1943**, lines 1-111) and states they exist **to compare improvements over time and catch regressions** (`doc/benchmarks/Benchmarking.md:13-15`). Refresh is manual: run `./gradlew jatsEval -Prun=1`, paste results into markdown, commit (`doc/End-to-end-evaluation.md:78-88`, `build.gradle:628-640`). CI never runs evaluation (`ci-build-unstable.yml:31-32`); eval image is `workflow_dispatch` only (`ci-build-manual-eval.yml:3-5`).

**guard gap:** has `--update` baseline JSON (`__main__.py:329-367`) but no companion **human-readable snapshot** (markdown table of per-paper axes + corpus micro-avg) for PR review like GROBID's benchmark pages.

**Adopt?** **Yes [MEDIUM] [ACTIONABLE-NOW].** Keep JSON as machine gate; emit a sorted markdown diff summary on guard runs mirroring `Benchmarking-pmc.md` field tables so reviewers see regressions without parsing JSON.

### 1.2 Per-item vs corpus-aggregate

GROBID iterates **one directory per article** (`EndToEndEvaluation.java:563-605`), accumulates field stats per document, and reports **instance-level** correct counts (`Benchmarking-pmc.md:98-110`: 205/1943 strict instances). whisker `guard` diffs **each PID** (`guard.py:216-218`) — **matches GROBID's per-document loop intent**, exceeds GROBID's committed snapshots (which only store corpus aggregates).

**Adopt?** **Already present.** Extend with per-document instance-level bit (all axes pass) as an optional strict mode (see §4).

### 1.3 Per-axis / per-field stratification

GROBID evaluates **~20+ named fields** per section with separate P/R/F1 (`FieldSpecification.java:36-300`, `Benchmarking-pmc.md:42-48` title/authors/abstract/…). Sections are **HEADER / CITATION / FULLTEXT** (`EndToEndEvaluation.java:60-62`, `:488-497`). whisker guard diffs four bench axes + `overall` (`constants.py:99`, `guard.py:172-184`); `reading_order` stored but excluded (`guard.py:71`, `constants.py:98`).

**Adopt?** **Partial [HIGH].** Keep four axes for CI brevity, but add **optional sub-axis breakdown** in guard findings (e.g. table count, block-match rate) so a single-axis collapse is localized like GROBID's `label` rows. Full field-level XPath evaluation is out of scope for markdown QA.

### 1.4 Multi-tier tolerance (strict / soft / fuzzy), not one slack

GROBID runs **four parallel matchers** on normalized text (`EndToEndEvaluation.java:453-461`):
- strict: exact after `basicNormalization` (`:2090-2096`)
- soft: `removeFullPunct` (`:2148-2159`)
- Levenshtein: pass if `(max_len - dist)/max_len >= 0.8` (`:66`, `:1126-1134`)
- Ratcliff/Obershelp: pass if `>= 0.95` (`:67`, `:1146-1160`)

Non-textual fields (dates, volume) skip fuzzy tiers (`EndToEndEvaluation.java:460-461`, `:1104-1107`).

guard uses **one absolute drop slack** `GUARD_AXIS_SLACK = 0.02` (`constants.py:94`, `guard.py:180-181`) on pre-aggregated scores already normalized upstream in `bench`.

**Adopt?** **Yes [HIGH] [ACTIONABLE-NOW].** Add a **soft tier** for guard: flag regression only if strict slack fails AND Levenshtein-normalized content drop exceeds a second threshold (port formula from `:1131-1133`). Stops punctuation/reflow false regressions GROBID explicitly filters.

### 1.5 Normalization-before-diff

GROBID normalizes **before** every compare: lowercase, whitespace collapse, entity unescape (`basicNormalization`, `:2090-2096`), punctuation strip for soft tier (`removeFullPunct`, `:2148-2159`), Unicode normalize for fulltext (`basicNormalizationFullText` + `UnicodeUtil`, `:2122-2145`). DOI matching adds ASCII-fold signatures (`EvaluationDOIMatching.java:631-638`).

guard rounds metrics to 4 decimals at baseline write/compare (`guard.py:144`, `:180`) but does **not** re-normalize underlying markdown before bench scoring on guard runs (relies on `bench` path).

**Adopt?** **Yes [MEDIUM].** Document/enforce that guard corpus candidates must be scored with the same `normalized_text` path; optionally snapshot **normalization version** in baseline JSON alongside `schema_version`.

### 1.6 Corpus-specific field / axis eligibility

GROBID drops fields that are absent or meaningless per corpus: PMC strips `doi/pmid/pmcid` from citation eval (`EndToEndEvaluation.java:505-508`); eLife drops `keywords`, contribution/conflict statements (`:510-519`, `:522-527`).

guard treats every paper with the same four axes and floors; no `null when N/A` (contrast opendataloader pattern noted in whisker notes).

**Adopt?** **Yes [MEDIUM] [ACTIONABLE-NOW].** Allow baseline entries with `"axes": {"teds": null}` meaning **skip axis** for that PID (papers with no GT tables). Prevents false floor/regression on axis-inapplicable items.

### 1.7 Floors / known-bad / expectedFailure

GROBID acknowledges **imperfect gold** and uses metrics for **relative** comparison only (`Benchmarking.md:11-13`); no `expectedFailure` list. whisker implements tabula-style monotonic guard: stable below-floor papers stay `ok` (`guard.py:184-198`, `test_guard.py:84-92`).

**Adopt?** **Already present and correct** for whisker's use case. GROBID instead documents gold limits (`End-to-end-evaluation.md:134-152` raw-string citations → false positives).

### 1.8 Missing / added item detection

GROBID skips directories with no gold XML with a **warning** (`EndToEndEvaluation.java:590-592`); does not fail the run. whisker **hard-fails** baseline PIDs missing from current corpus (`guard.py:221`, `:113-115`) and passes **new** PIDs as `STATUS_NEW` (`guard.py:165-169`) without requiring explicit bless.

**Adopt?** **Partial [MEDIUM].** Missing detection is good. Consider **warn-only mode** for new PIDs (GROBID always evaluates newcomers) vs silent pass — new papers can hide first-run quality issues until someone runs `--update`.

### 1.9 Refresh ritual

GROBID: `-Prun=1` regenerates TEI, eval with `-Prun=0` for score-only (`End-to-end-evaluation.md:85-88`). whisker: `--update` rewrites baseline (`__main__.py:361-367`).

**Adopt?** **Already present.** Add requirement to commit **both** baseline JSON and markdown snapshot in same PR (GROBID pattern).

### 1.10 Statistical vs exact

GROBID is **statistical** (P/R/F1, support counts, micro/macro — `Stats.java:232-278`). whisker guard is **exact numeric diff** on deterministic metrics with slack (`guard.py:177-184`).

**Adopt?** **Keep exact diff** for whisker (deterministic scorer). Borrow GROBID's **support** reporting: include GT table count / block count in guard findings so small-sample swings are visible (`Benchmarking-pmc.md:42-48` support column).

### 1.11 Baseline metadata ignored on read

`baseline_from_rows` writes `axis_slack` and `floors` (`guard.py:141-142`); `diff_rows` always uses caller `slack` param and module-level `_FLOORS` (`guard.py:62`, `:204-205`, `:161-163`), never `baseline["axis_slack"]` or `baseline["floors"]`.

**Adopt?** **Yes [HIGH] [ACTIONABLE-NOW].** Read slack/floors from baseline when present; validate `kind == whisker-guard-baseline` and `schema_version`.

### 1.12 Subsample / fileRatio

GROBID supports `-PfileRatio=0.1` for partial eval (`EndToEndEvaluation.java:64`, `:569-573`, `End-to-end-evaluation.md:89-92`).

**Adopt?** **Optional [LOW].** `--sample 0.1` for fast guard smoke; not needed for CI full corpus.

---

## 2. CALIBRATION GAPS

GROBID **does not calibrate**: Levenshtein **0.8** and Ratcliff **0.95** are fixed engineering constants (`EndToEndEvaluation.java:66-67`); DOI alignment uses a **separate** Ratcliff floor **0.5** (`EvaluationDOIMatching.java:56`). Thresholds are documented, not ROC-fit (`doc/End-to-end-evaluation.md:115-128`).

whisker `calibrate.py` is **more principled** than GROBID; gaps are where GROBID's **multi-threshold, per-context** practice still beats a single ROC sweep:

| Gap | GROBID evidence | calibrate.py gap | Adopt? |
|-----|-----------------|------------------|--------|
| **Multi-threshold / tiered operating points** | Four tiers with different constants (`:66-67`) | Single threshold per `calibrate_threshold` call | **Yes [HIGH]:** calibrate fail edge on strict rule, review edge on soft/Levenshtein tier |
| **Per-axis / per-field calibration** | Title vs abstract vs citation fields scored separately (`Benchmarking-pmc.md:42-48` vs `:121-133`) | Only `unigram_coverage` (`__main__.py:488-498`) | **Yes [MEDIUM]:** extend labels file to fit `nid/teds/mhs` bench axes separately |
| **Context-specific thresholds** | DOI matching Ratcliff 0.5 vs field eval 0.95 (`EvaluationDOIMatching.java:56` vs `EndToEndEvaluation.java:67`) | One global `target_fpr` | **Yes [LOW]:** allow per-metric `target_fpr` |
| **Class imbalance / support weighting** | Reports **support** per label; micro vs macro (`Stats.java:232-278`, `Benchmarking-pmc.md:50-51`) | Unweighted sample counts (`calibrate.py:164-165`) | **Yes [MEDIUM]:** weight by paper stratification or report support per class |
| **Cross-validation / holdout** | Holdout **datasets** independent of training (`Benchmarking.md:7-8`, `End-to-end-evaluation.md:17-23`) | Single labels file, no split (`calibrate.py:149-185`) | **Yes [MEDIUM]:** require held-out PID list; report train vs holdout TPR/FPR |
| **ROC operating-point selection** | N/A (fixed constants) | max TPR @ FPR≤ceiling, Youden fallback (`calibrate.py:174-180`) | **Keep** — whisker advantage |
| **Ordered band edges (fail ≤ review)** | N/A | fail and review fit independently (`__main__.py:494-498`) | **Yes [HIGH] [ACTIONABLE-NOW]:** enforce `fail_edge <= review_edge` post-fit |
| **Empty-field handling in metrics** | Both-empty fields skipped (`EndToEndEvaluation.java:1420-1423`) | Not modeled in calibration | **Yes [LOW]:** exclude `unigram_coverage` when structural gates already failed |

---

## 3. CONCRETE BUGS / EDGE-CASES IN WHISKER CODE

| Severity | Function | Scenario | Expected failure mode |
|----------|----------|----------|------------------------|
| **[CRITICAL] [ACTIONABLE-NOW]** | `diff_rows` / `_evaluate_paper` | Baseline JSON edited to tighten `floors` or `axis_slack`; guard still uses `C.NID_FLOOR` / CLI default slack (`guard.py:62`, `:204-205`) | **Silent false pass** on regressions that exceed committed baseline tolerances |
| **[HIGH] [ACTIONABLE-NOW]** | `diff_rows` | Baseline file is bench leaderboard or wrong `kind` | No validation; garbage compare or empty `rows` → floor-only mode (`guard.py:213-214`) |
| **[HIGH] [ACTIONABLE-NOW]** | `_calibrate_main` | Separable labels where fail fit threshold 0.92, review fit 0.88 | **Inverted band** — papers fail review but pass fail gate (`__main__.py:494-498`) |
| **[HIGH]** | `calibrate_threshold` | Sample `(0.50, True), (0.50, False)` with `target_fpr=0.0` | Youden fallback; **0.50 threshold** flags both (`test_calibrate.py:36-49`) — ties not excluded from candidate sweep |
| **[MEDIUM] [ACTIONABLE-NOW]** | `diff_rows` | Duplicate `pid` in `rows` | Duplicate `GuardFinding` entries; `report.failed` still works but counts/overrides wrong (`guard.py:216-218`) |
| **[MEDIUM]** | `_evaluate_paper` | `axes[axis]` is `NaN` (bench division edge) | `drop > slack` is False; `NaN < floor` is False → **STATUS_OK** masks broken score |
| **[MEDIUM]** | `calibrate_threshold` | `unigram_coverage=float('nan')` in labels | `value < threshold` always False → labeled bad papers become **FN** without error |
| **[MEDIUM]** | `diff_rows` | Empty `rows`, nonempty baseline | `findings=[]`, `missing=all baseline PIDs`, `failed=True` (`guard.py:221`) — correct but no finding detail for why |
| **[MEDIUM]** | `_evaluate_paper` | New paper added; first run scores `teds=0.75` (below floor 0.80) | `STATUS_NEW_BELOW_FLOOR` fails — good; but **re-run after `--update`** without fixing converter permanently encodes weak baseline (GROBID warns about imperfect gold; whisker monotonic model cements it) |
| **[LOW]** | `_candidate_thresholds` | All samples exactly `1.0` | Only thresholds `{1.0, 2.0}`; coarse curve (`calibrate.py:130-133`) |
| **[LOW]** | `baseline_from_rows` | Paper with only whitespace PID via corpus loader | Not guard's job, but duplicate corpus files could collide on PID uppercase (`__main__.py:253`) |
| **[LOW]** | `_evaluate_paper` | Uniform axis drop `0.015` each (< slack 0.02) | Passes (`test_guard.py:109-114`) — GROBID instance-level would still catch multi-field partial errors; whisker **overall** axis uses same slack, not composite instance gate |

**Float precision:** rounding `drop` to 4 decimals (`guard.py:180`) matches reported granularity; boundary at exactly slack is handled (`test_guard.py:55-60`). **Unicode:** GROBID normalizes before compare; whisker relies on `normalized_text` in metrics — guard itself does not re-check unicode normalization on diff.

**Huge corpora:** GROBID uses `fileRatio` subsampling (`EndToEndEvaluation.java:569-573`); guard loads all pairs synchronously (`__main__.py:353-358`) — memory bound by bench, not guard logic.

---

## 4. MISSING AXIS / CHECK (GROBID gates, whisker has no equivalent)

| GROBID check | Evidence | whisker equivalent |
|--------------|----------|-------------------|
| **Field-level micro/macro P/R/F1** | `Stats.java:232-278`, `ModelStats.java:139-157` | None — only scalar `nid/teds/mhs` |
| **Instance-level all-fields-correct** | `Benchmarking-pmc.md:98-110`, `EndToEndEvaluation.java:1174-1184` | None — per-axis slack can pass when 3/4 axes barely fail individually |
| **Section/strata split (header / citation / fulltext)** | `EndToEndEvaluation.java:488-497` | None in guard |
| **Four-tier match reporting** | `EndToEndEvaluation.java:463-466` | Single slack |
| **Citation alignment before field scoring** | Four signature rules (`EndToEndEvaluation.java:810-816`, `:1017-1041`) | Block matching in bench only; no alignment failure bucket in guard |
| **Fulltext structure eval** | `FULLTEXT` section (`EndToEndEvaluation.java:494-496`, `:1539+`) | `reading_order` advisory only, not gated |
| **Support / class counts in report** | `Benchmarking-pmc.md:42-48` support column | `status_counts` only (`guard.py:121-130`) |
| **PDF parse failure accounting** | `Benchmarking-pmc.md:27` "0 PDF parsing failure" | Missing candidate MD skipped with warning (`__main__.py:256-258`); not aggregated in guard report |
| **Meta-tests on evaluation engine** | `EvaluationUtilitiesTest.java:13-222` (token + field stats) | `test_guard.py` covers slack/floor logic; no tests for baseline metadata read, duplicate PID, NaN |

---

## 5. TOP PORTABLE DETAIL

**Adopt GROBID's relative Levenshtein pass formula as a guard secondary tier:**

```java
// EndToEndEvaluation.java:1126-1134 (citation fields) and :1479-1487 (header fields)
int distance = TextUtilities.getLevenshteinDistance(goldResult, grobidResult);
int bigger = Math.max(goldResult.length(), grobidResult.length());
pct = (double) (bigger - distance) / bigger;
// pass field if pct >= minLevenshteinDistance (0.8)
```

Constants: `minLevenshteinDistance = 0.8`, `minRatcliffObershelpSimilarity = 0.95` at `EndToEndEvaluation.java:66-67`.

**Why this one:** whisker `nid` is already edit-distance-based on normalized text (`bench.py:157-158`, `metrics.py` via CLAUDE.md). GROBID proves the field uses **normalization first** (`basicNormalization` `:2090-2096`, soft tier `:2148-2159`) then a **fixed relative Levenshtein floor**, not an absolute character delta. Mapping to guard: when strict axis slack flags a regression, re-score that PID's normalized markdown with the GROBID formula; if `pct >= 0.8`, downgrade to **advisory** (formatting churn). This directly addresses GROBID's core QA insight — **relative fuzzy match for text fields, exact for numeric/date fields** (`EndToEndEvaluation.java:460-461`) — without replacing whisker's deterministic bench axes.

**Implementation hook [ACTIONABLE-NOW]:** add optional `soft_tier: levenshtein@0.8` in guard report for `nid` drops ≤ slack but > 0; wire constant `GUARD_LEVENSHTEIN_FLOOR = 0.8` next to `GUARD_AXIS_SLACK` in `constants.py`.
