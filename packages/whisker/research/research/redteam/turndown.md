# Red-team: whisker guard/calibrate vs turndown QA

**Source repo:** `packages/whisker/research/repos/turndown` (mixmark-io/turndown v7.2.4, shallow clone)  
**Target:** `guard.py`, `calibrate.py` (+ CLI wiring in `__main__.py`)

## Summary

- turndown gates **100 inline HTML case-table goldens** on **byte-exact** `output === expected` with **zero slack** (`node_modules/turndown-attendant/attendant.js:66-74`); guard tolerates per-axis drops up to `GUARD_AXIS_SLACK=0.02`, so visible Markdown regressions that preserve nid/teds/mhs slip through.
- Every turndown fixture runs **twice per case** — DOM node input and HTML-string input — both must match (`attendant.js:72-79`); guard scores one `bench` path only, missing DOM-vs-string parity failures turndown catches routinely.
- turndown **22 `data-options` permutations** exercise converter config variants inline (`test/index.html:101`, `:488`, `:1114`); guard stores one metric row per pid with no config dimension (`guard.py:143-145`).
- turndown has **no calibration** (exact match is the implicit operating point); `calibrate.py` is ahead for fuzzy coverage edges but **does not calibrate guard floors or metric baselines**, and turndown proves a **binary micro-fixture layer** should sit beneath ROC-fit thresholds.
- **Top portable detail:** dual-path `(DOM)` + `(string)` golden assertion per fixture (`attendant.js:72-79`) — adopt as a whisker micro-corpus harness shape.

---

## 1. REGRESSION-GATE GAPS

### 1.1 Full-output golden vs metric snapshots [CRITICAL]

**turndown:** Each `.case` compares the entire converter output to `<pre class="expected">` via strict equality (`attendant.js:39-40`, `66-74`). Any character change fails CI until the golden is hand-edited in `test/index.html`.

**guard.py:** Commits and diffs only `{nid, teds, mhs, overall, reading_order}` floats per pid (`guard.py:65-71`, `136-147`). Output text is never snapshotted.

**Adopt?** **Partially.** Full WG21-paper goldens are impractical (tomd reflow churn), but turndown's 100-case micro-corpus pattern is the right hard backstop beneath metric slack. Metric-only guard cannot catch regressions visible to humans but invisible to block-matched NID/TEDS/MHS (e.g. escaping, list bullets, trailing spaces on `<br>`).

### 1.2 Zero tolerance vs per-axis slack [HIGH]

**turndown:** `t.equal(output, expected)` — tolerance is exactly zero after converter-internal normalization (`attendant.js:74`).

**guard.py:** Regression only when `round(prior - cur, 4) > slack` (`guard.py:180-184`); default slack `0.02` (`constants.py:94`).

**Adopt?** **No wholesale replacement** for the labeled corpus, but adopt turndown's zero-tolerance semantics for a **golden micro-corpus subset**. turndown proves slack is a deliberate relaxation for large-corpus metrics, not the default safety model for HTML edge cases.

### 1.3 Dual entry point: DOM vs string [HIGH] [ACTIONABLE-NOW]

**turndown:** Each case emits two tape tests — `(DOM)` passes the parsed element node, `(string)` passes `inputElement.innerHTML` (`attendant.js:72-79`). Real bugs surface when only one path breaks.

**guard.py / `__main__.py`:** Single path: `_load_corpus_pairs` → `run_bench` → `diff_rows` (`__main__.py:353-383`).

**Adopt?** **Yes.** For whisker's HTML pipeline, score guard logic through both staged-HTML-file and inline-HTML-string inputs on a micro-corpus. turndown's dual-path model is cheap and catches parser/DOM-boundary bugs metric slack will never see.

### 1.4 Inline option permutations (`data-options`) [HIGH]

**turndown:** 22 of 100 cases carry `data-options='{"headingStyle":"atx"}'` (and similar) so the **same HTML input** is gated under multiple converter configs (`test/index.html:101-104`, `:488-498`, `:1114-1117`). Each permutation has its own expected golden.

**guard.py:** One baseline row per pid; no config key (`guard.py:143-145`).

**Adopt?** **Yes** for baseline keyed by `(pid, config_id)` or a recorded global bench config hash. A tomd option change that alters output but not aggregate metrics passes guard silently.

### 1.5 Fail-closed on new corpus items vs `STATUS_NEW` passes [HIGH] [ACTIONABLE-NOW]

**turndown:** A new `.case` without a matching `<pre class="expected">` crashes at load time (`attendant.js:38-39`); a wrong expected fails exact compare. Unreviewed cases cannot pass CI.

**guard.py:** Papers absent from baseline get `STATUS_NEW` and **do not fail** if above floors (`guard.py:165-169`, `52-53`; `test_guard.py:78-81`).

**Adopt?** **Yes.** Require explicit baseline acknowledgment for new pids (fail unless `--update`). turndown's model prevents silent corpus expansion from weakening coverage.

### 1.6 Missing-item detection (asymmetric) [MEDIUM]

**turndown:** Deleting a `.case` div removes the parametrized test — coverage drops but CI stays green (no explicit removal gate).

**guard.py:** **Hard-fails** when a baseline pid vanishes (`guard.py:220-221`, `113-115`). Stricter than turndown; **keep**.

**Adopt?** Already present.

### 1.7 Pre-compare normalization contract [HIGH] [ACTIONABLE-NOW]

**turndown:** Normalization lives **in the converter** (`src/collapse-whitespace.js:51`, `src/turndown.js:172` trims document edges only; internal whitespace like `<br>`'s two trailing spaces is preserved — `test/index.html:147-150`). The test harness compares raw `textContent` with no secondary normalize pass (`attendant.js:39-40`).

**guard.py:** Metrics normalize internally (`normalized_text`), but the guard boundary accepts raw `BenchRow` floats. Baseline stores `axis_slack` and `floors` but **`diff_rows` reads only `baseline["rows"]`** (`guard.py:213-214`) — committed slack/floors are ignored at diff time; live `constants.py` values apply instead.

**Adopt?** **Yes:** (a) store and enforce a scoring/normalization fingerprint in baseline; (b) read `baseline["axis_slack"]` and `baseline["floors"]` when present, or fail on schema drift. turndown's lesson: the normalization ritual must be part of the committed contract, not implied.

### 1.8 Any output change fails (including improvements) [MEDIUM]

**turndown:** Improving output without updating `<pre class="expected">` **fails** CI — forces explicit golden refresh in the PR.

**guard.py:** Only drops fail; improvements always `STATUS_OK` (`guard.py:172-184`).

**Adopt?** **Partially.** Metric baselines: improvement-without-update is fine. Golden micro-corpus: adopt turndown's "any change requires refresh" rule.

### 1.9 known-bad / expectedFailure [LOW]

**turndown:** No `expectedFailure`. Known-bad behavior is encoded **in the golden itself** (expected output documents current behavior, e.g. `test/index.html:127-129` invalid `<h7>` degrades to plain text).

**guard.py:** Monotonic model — papers already below floor in baseline are not re-flagged unless they worsen (`guard.py:22-24`; `test_guard.py:84-92`).

**Adopt?** Keep guard's explicit monotonic logic for metrics. For goldens, use turndown's "golden IS the contract" model.

### 1.10 Refresh ritual [LOW]

**turndown:** No CLI `--accept`; refresh = hand-edit `<pre class="expected">` in `test/index.html`, review in PR. CI never auto-updates goldens (`.github/workflows/test.yml:30-31`).

**guard.py:** Explicit `--update` ritual (`__main__.py:329-367`).

**Adopt?** whisker is **ahead** here. Keep `--update`; add turndown-style visual diff review for golden micro-corpus when built.

### 1.11 Statistical vs exact [MEDIUM]

**turndown:** Pure exact match; no ROC, no floors, no means.

**guard.py:** Fuzzy floats + slack + floors.

**Adopt?** **Layer both.** turndown shows exact match is correct for micro-fixtures; guard's fuzzy layer is correct for large labeled corpus. Neither replaces the other.

---

## 2. CALIBRATION GAPS

turndown has **no threshold calibration** — the operating point is implicit: edit distance zero (`attendant.js:74`). Findings for `calibrate.py`:

### 2.1 Binary operating point vs ROC fit [MEDIUM]

**turndown:** Pass/fail is `output === expected`. No TPR/FPR sweep, no class labels.

**calibrate.py:** Sweeps ROC on `unigram_coverage` with `target_fpr=0.05` (`calibrate.py:149-185`).

**Gap:** calibrate solves a problem turndown never has (fuzzy content coverage on real papers). turndown proves a **binary golden layer** should exist where ROC is the wrong tool.

**Adopt?** Do not ROC-fit the micro-corpus. Keep `calibrate` for coverage edges; add exact-match goldens separately.

### 2.2 No per-axis / per-metric calibration [HIGH] [ACTIONABLE-NOW]

**turndown:** Every structural axis (headings, lists, links, code, whitespace) is an independent exact assertion — no collapsed `overall`.

**calibrate.py:** Fits only `unigram_coverage_fail_edge` and `unigram_coverage_review_edge` (`__main__.py:490-498`). Does not fit `NID_FLOOR`, `TEDS_FLOOR`, `MHS_FLOOR`, or `GUARD_AXIS_SLACK`.

**Adopt?** **Yes** for guard floors: either derive from labeled bench outcomes per axis, or declare micro-corpus goldens use slack=0 and large-corpus uses hand-set floors. turndown's per-case isolation is the model for per-axis independence.

### 2.3 No cross-validation / holdout [MEDIUM]

**turndown:** N/A (deterministic goldens).

**calibrate.py:** In-sample ROC on all labels; no k-fold or holdout split (`calibrate.py:149-185`).

**Adopt?** **Yes** when label count is small (turndown's 100 cases suggest a holdout slice). In-sample TPR/FPR overstates confidence.

### 2.4 Class imbalance handling [LOW]

**turndown:** N/A.

**calibrate.py:** `max TPR s.t. FPR <= ceiling` (`calibrate.py:174-177`) handles imbalance implicitly but reports no prevalence weighting.

**Adopt?** Optional; turndown offers no guidance. Document assumed bad-paper prevalence when promoting fitted edges.

### 2.5 Metric choice for calibration [MEDIUM]

**turndown:** Output string is the metric.

**calibrate.py:** Only `unigram_coverage`; ignores `ref_nid`, structural gate outcomes, per-axis bench scores.

**Adopt?** **Partially.** turndown shows string-level checks catch failures coverage misses (escaping, NBSP). Consider calibrating on a composite or adding anchor-hit rate as a second calibrated axis.

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

Given turndown's lessons, inputs that break or fool guard/calibrate:

| Severity | Function | Scenario | Why |
|----------|----------|----------|-----|
| [HIGH] [ACTIONABLE-NOW] | `diff_rows` | Baseline JSON stores `axis_slack: 0.05` but CLI passes default `0.02` | Only `baseline["rows"]` is read (`guard.py:213-214`); stored slack ignored — stale committed tolerance never applied. |
| [HIGH] [ACTIONABLE-NOW] | `diff_rows` / `_evaluate_paper` | Baseline JSON stores `floors: {nid: 0.88}` but `constants.py` changes to `0.90` | `_FLOORS` always from live constants (`guard.py:62`, `161-163`); baseline floors are write-only decoration. |
| [HIGH] | `_evaluate_paper` | `axes[axis]` is `NaN` (bench failure upstream) | `NaN < floor` is False; `NaN > slack` is False — paper silently `STATUS_OK`. turndown would fail loudly on non-string output. |
| [HIGH] | `diff_rows` | Duplicate pid in `rows` | No dedup; two `GuardFinding`s for same pid, ambiguous pass/fail rollup. turndown cases are uniquely named via `data-name`. |
| [HIGH] | guard (design) | Markdown escaping / NBSP / `<br>` trailing-space regression | turndown gates exact bytes (`test/index.html:147-150`, `:1099-1110`); NID/TEDS unchanged → guard passes. |
| [MEDIUM] [ACTIONABLE-NOW] | `diff_rows` | New pid above floors, baseline exists | `STATUS_NEW` passes (`guard.py:169`); turndown would fail until golden committed. |
| [MEDIUM] | `_evaluate_paper` | Uniform axis erosion `0.015` each (< slack) | Confirmed pass (`test_guard.py:109-114`); turndown exact match would fail on any visible change. |
| [MEDIUM] | `calibrate_threshold` | All bad papers have `unigram_coverage=0.90`, all good at `0.90` | Tie at class boundary; threshold semantics `value < t` (`calibrate.py:111`) means boundary values never flagged — degenerate fit. |
| [MEDIUM] | `_load_labeled_samples` | Duplicate pid in labels file | Both records scored; double-counts in calibration (`__main__.py:441-452`). |
| [MEDIUM] | `calibrate_threshold` | `target_fpr=0.0` with overlapping classes | May fall back to Youden (`calibrate.py:178-180`); chosen edge may have FPR > 0 without surfacing invariants test. |
| [LOW] | `baseline_from_rows` | Empty `rows` written via `--update` | Produces valid baseline; next run diffs nothing useful but missing detection still works. |
| [LOW] | `_candidate_thresholds` | Single sample per class (n=2) | Legal but TPR/FPR are only 0 or 1; turndown's 100-case corpus shows minimum fixture count for confidence. |
| [LOW] | `calibrate_threshold` | Empty `values` after filter | Guarded by class-count check (`calibrate.py:166-169`); empty list before that raises in CLI (`__main__.py:484-486`). |

---

## 4. MISSING AXIS / CHECK

Axes turndown gates on that whisker guard has **no equivalent**:

| turndown axis | Evidence | whisker gap |
|---------------|----------|-------------|
| **Exact whitespace semantics** | `<br>` → two trailing spaces + LF (`test/index.html:147-150`); NBSP cases (`:1099-1110`) | `reading_order` is advisory, excluded from `GUARD_REGRESSION_AXES` (`constants.py:99`) |
| **Markdown escaping fidelity** | `escape = when used as heading` (`:91-94`); img alt escapes (`:174-177`) | No string-level escape check; NID may absorb escape changes |
| **Link reference styles** | `linkStyle: referenced` + collapsed/shortcut variants (`:270-295`) | No per-modality config gate |
| **List / blockquote formatting** | Ordered/unordered spacing (`:407-511`); nested blockquotes (`:622-636`) | MHS partial; no list-marker or `>` prefix assert |
| **DOM vs string input parity** | Dual tests per case (`attendant.js:72-79`) | Single bench input path |
| **Converter option matrix** | 22 `data-options` cases | One row per pid |
| **Internal helper correctness** | `edgeWhitespace` unit tests + 32768-char perf bound (`internals-test.js:5-34`) | Guard logic meta-tests exist (`test_guard.py`) but no perf/regression bounds on metric code |
| **Input validation** | null/undefined throw (`turndown-test.js:19-33`) | Missing candidate md skipped with warning (`__main__.py:256-258`), not a guard fail |
| **Tables** | *Not in turndown corpus* (0 `<table>` cases) | whisker **leads** on TEDS; turndown gap, not whisker gap |

---

## 5. TOP PORTABLE DETAIL

**Dual-path golden assertion per fixture: `(DOM)` + `(string)`.**

```72:79:packages/whisker/research/repos/turndown/node_modules/turndown-attendant/attendant.js
  this.test(testCaseName + ' (DOM)', function (t) {
    t.plan(1)
    t.equal(output, expected)
  })

  this.test(testCaseName + ' (string)', function (t) {
    t.plan(1)
    t.equal(turndownService.turndown(inputElement.innerHTML), expected)
  })
```

**Why:** One HTML→MD conversion path can pass while the other breaks (parser DOM attachment vs raw string). Metric slack on nid/teds/mhs will not detect this class of bug. **Adopt today** as the shape of whisker's HTML micro-corpus harness: each fixture runs staged file input and inline-string input, both compared to committed expected markdown (exact for micro-corpus, metric guard for full papers).

**Secondary (config dimension):** `data-options='{"headingStyle":"atx"}'` on the same input (`test/index.html:101-104`) — baseline key should be `(fixture_id, options_hash)`, not pid alone.
