# Red-team: whisker guard/calibrate vs mdream QA

- mdream gates on **committed exact markdown** (`toBe` / `toMatchSnapshot` / `toMatchFileSnapshot` per fixture and per stream chunk), not scalar metric deltas; whisker guard stores four floats per paper and cannot catch formatting-only or structural regressions mdream catches at line 1.
- mdream enforces **dual-path parity** (`string` vs `stream` after `trimEnd()`, JS vs Rust heading-level match, link count within 2%); whisker guard has no equivalent batch-vs-stream or PDF-vs-HTML parity gate on the bench path.
- mdream uses **per-fixture absolute size floors** (`minOutputKB * 1024`) and **ordered-position reading checks** (`indexOf` chains); guard floors are axis constants only and `reading_order` is never diffed (`constants.py:99`).
- `calibrate.py` is ahead of mdream (mdream has **no ROC fitting**, only hand-set exact expects and ratio thresholds), but can emit **inverted fail/review edges**, ignores **baseline `axis_slack`**, and lacks mdream-style **known-exception** registry for noisy items.
- **Top portable adoption:** normalize with `trimEnd()` before equality compare (`fixture-parity.test.ts:54-55`); secondary: structural invariants (heading level match `fixture-parity.test.ts:89-98`, link count ±2% `fixture-parity.test.ts:112-113`).

---

## 1. REGRESSION-GATE GAPS

### 1.1 Committed full-output goldens (exact + snapshot)

**mdream:** Unit tests assert byte-exact markdown via `expect(markdown).toBe('...')` (`combined.test.ts:19-26`, `headings.test.ts:9`, `spacing.test.ts:9-46`) and Vitest snapshots via `toMatchSnapshot()` / `toMatchInlineSnapshot()` on splitter output (`splitter.test.ts:120,216,412,434,451,645,789,1021,1112,1189`). Integration uses per-chunk `toMatchFileSnapshot` on live Wikipedia fetch (`fetch.test.ts:27-33`). Any output change fails CI; refresh is `vitest -u` locally (not in `.github/workflows/test.yml:211-212`).

**guard.py:** Baseline stores only `nid/teds/mhs/overall/reading_order` scalars (`guard.py:65-71,136-147`). A regression that preserves aggregate metrics but changes table pipe escaping, heading spacing, or chunk boundaries passes.

**Adopt?** Partially. Full markdown goldens are too brittle for tomd (intentional reflow), but guard should commit **hashed markdown snippets or sidecar structural counts** alongside metrics. Scalar-only baselines are a strict subset of mdream's contract.

**Severity:** [CRITICAL]

---

### 1.2 Dual-path parity gate (batch vs stream, engine vs engine)

**mdream:** Every fixture runs string AND streaming conversion; outputs must match after normalization (`fixture-parity.test.ts:50-56`). Cross-engine checks: output length ratio within 1% (`fixture-parity.test.ts:76-78`), heading **count and level** identical (`fixture-parity.test.ts:89-98`), link count within 2% (`fixture-parity.test.ts:112-113`). Simple HTML cases require **byte-identical** JS/Rust output (`fixture-parity.test.ts:132-134`). All node tests run under `describe.each(engines)` (`engines.ts:175-190`, `html-to-markdown-parity.test.ts:4`).

**guard.py:** Scores one candidate markdown path per paper via `run_bench` (`bench.py:149-166`). No check that PDF-batch vs HTML-batch, or re-run vs cached sidecar, produce the same metrics.

**Adopt?** Yes. Add a parity sub-gate: same `pid` scored twice (or PDF vs HTML when both exist) must match within zero slack on deterministic axes, mirroring mdream's `streamResult.trimEnd() === stringResult.trimEnd()`.

**Severity:** [HIGH]

---

### 1.3 Normalization-before-diff (`trimEnd` semantics)

**mdream:** Streaming may emit trailing whitespace from final flush; parity compares `streamResult.trimEnd()` to `stringResult.trimEnd()` with an explicit comment (`fixture-parity.test.ts:54-55`). Whitespace edge cases have dedicated exact expects (`spacing.test.ts:35-47`, `fixture-parity.test.ts:419-436`).

**guard.py:** Rounds the **drop** to 4 decimals (`guard.py:177-180`) and baseline rows to 4 decimals on write (`guard.py:144`), but **current axis values** fed into `_evaluate_paper` are unrounded floats from `BenchRow`. No trailing-whitespace or normalization layer before metric computation lives in guard.

**Adopt?** Yes [ACTIONABLE-NOW]. Round **both** `prior` and `cur` to the baseline grid (4 decimals) before subtraction, not only the drop. Document that bench metrics should apply the same normalization mdream uses before compare (content-equivalence, not byte-equivalence).

**Severity:** [HIGH]

---

### 1.4 Structural invariant checks beyond fuzzy metrics

**mdream:** Reading order via ordered position: `titleIndex.toBeLessThan(paragraphIndex)` (`streaming.test.ts:31-33`). Heading hierarchy in splitter metadata asserted per chunk (`splitter.test.ts:20-25,178-186`). Template/wiki tests snapshot complex table output (`wiki.test.ts:8-9`). Block-element spacing exact (`spacing.test.ts:42-47`).

**guard.py:** `reading_order` is stored in baseline (`guard.py:71`) but **excluded** from `GUARD_REGRESSION_AXES` (`constants.py:99`). No heading-count, link-count, or table-count axes.

**Adopt?** Yes. Add optional baseline fields `heading_count`, `link_count`, `table_count` (cheap regex counts on candidate md) with tight or exact slack, matching mdream's structural gates.

**Severity:** [HIGH]

---

### 1.5 Per-fixture absolute size floors (not just axis floors)

**mdream:** Each committed fixture declares `minOutputKB` and asserts `md.length > minOutputKB * 1024` for both string and stream paths (`fixture-parity.test.ts:10-12,38-48`). Catastrophic empty/near-empty output fails even with no prior baseline.

**guard.py:** Absolute `_FLOORS` apply only to `nid/teds/mhs` (`guard.py:62,160-163`), not output size or element counts. A paper that collapses to empty markdown might still pass if GT comparison is degenerate.

**Adopt?** Yes. Per-paper `min_output_bytes` or `min_block_count` in baseline as a backstop, analogous to mdream's `minOutputKB`.

**Severity:** [MEDIUM]

---

### 1.6 Known-bad / expectedFailure / skip registry

**mdream:** Flaky or unimplemented areas use `describe.skip` (`malformed-html.test.ts:5`, `fetch.test.ts:4`). Known engine gaps documented inline: extended named entities **intentionally omitted** from parity matrix with issue reference (`fixture-parity.test.ts:605-606`).

**guard.py:** Monotonic known-bad for metrics below floor in baseline (`guard.py:160-198`, `test_guard.py:84-99`). No per-`pid` `skip_axes`, `expected_failure`, or documented exception bit in baseline JSON.

**Adopt?** Yes. Baseline row optional `"skip_axes": ["teds"]` or `"expected_failure": true` so mdream-style known gaps do not block the corpus while still catching **worsening**.

**Severity:** [MEDIUM]

---

### 1.7 Closed corpus vs silent new papers

**mdream:** Tests iterate a **fixed fixture list** (`fixture-parity.test.ts:9-13`); there is no "new fixture passes by default." Missing coverage is a test authoring gap, not runtime `STATUS_NEW`.

**guard.py:** Papers absent from baseline get `STATUS_NEW` and pass unless below floor (`guard.py:165-169`). Only **missing baseline papers** (in baseline, absent from run) hard-fail (`guard.py:221,113-115`).

**Adopt?** Yes [ACTIONABLE-NOW]. Add `--strict-corpus` (fail on any `STATUS_NEW`) mirroring mdream's closed fixture set.

**Severity:** [HIGH]

---

### 1.8 Refresh ritual CI lockout

**mdream:** CI runs `pnpm run test` only (`.github/workflows/test.yml:211-212`); snapshot refresh is a local `vitest -u` step, never invoked in CI.

**guard.py / `__main__.py`:** `--update` rewrites baseline unconditionally (`__main__.py:361-367`). No `CI=true` guard, no `kind`/`schema_version` validation on read.

**Adopt?** Yes [ACTIONABLE-NOW]. Refuse `--update` when `CI=true` unless `WHISKER_GUARD_UPDATE=1`; validate `baseline["kind"] == GUARD_BASELINE_KIND` and `schema_version` in `diff_rows`.

**Severity:** [HIGH]

---

### 1.9 Baseline metadata `axis_slack` ignored

**mdream:** Thresholds live in test code next to asserts (ratio `0.99`, link delta `0.02` at `fixture-parity.test.ts:76-78,112-113`); no split between written metadata and runtime gate.

**guard.py:** `baseline_from_rows` writes `"axis_slack": C.GUARD_AXIS_SLACK` (`guard.py:141`); `diff_rows` uses only the `slack` parameter (`guard.py:205,221`), never `baseline.get("axis_slack")`.

**Adopt?** Yes [ACTIONABLE-NOW]. Default `slack` from baseline when CLI omits `--slack`.

**Severity:** [MEDIUM]

---

### 1.10 Statistical vs exact tolerance semantics

**mdream:** Micro-cases: **exact** equality. Large fixtures: **ratio/count** tolerances (1% length, 2% links, exact heading levels). No corpus mean; every fixture item checked.

**guard.py:** Single global `GUARD_AXIS_SLACK = 0.02` on all regression axes (`constants.py:94-99`). `bench --baseline` still checks corpus-mean `overall` only (`__main__.py:306-315`), a pattern mdream does not use.

**Adopt?** Partially. Keep per-paper guard; add axis-specific slack (tables tighter than nid) matching mdream's split between exact micro-tests and ratio macro-tests.

**Severity:** [MEDIUM]

---

### 1.11 Improvements silently allowed (asymmetric vs snapshot repos)

**mdream:** Snapshots fail on **any** output change, including improvements, forcing explicit `-u` refresh.

**guard.py:** Only **drops** fail; improvements above baseline pass silently (`guard.py:171-198`).

**Adopt?** Optional `--strict-snapshot` mode or report `improved` status for audit. Not required for release gating; mdream's asymmetry is intentional for golden repos.

**Severity:** [LOW]

---

## 2. CALIBRATION GAPS

### 2.1 mdream does not calibrate; whisker is ahead on methodology

**mdream:** No ROC, no labeled good/bad sweep. Quality bars are hand-set exact strings, snapshot files, and ratio constants (`fixture-parity.test.ts:76-78,112-113`). Bench suite (`bench/compare.bench.ts`) measures **ops/sec only**, not accuracy thresholds.

**calibrate.py:** Full ROC sweep with `max TPR @ FPR <= target` (`calibrate.py:149-185`).

**Adopt?** Keep calibrate; mdream offers no competing fitter. Document that mdream's "calibration" is engineering judgment encoded as exact expects.

**Severity:** [LOW] (informational)

---

### 2.2 Independent fail/review fits can invert the band

**mdream:** N/A (no dual threshold), but spacing tests encode ordered tiers as separate exact cases (`spacing.test.ts:9-46`).

**calibrate.py / `__main__.py`:** `fail_fit` and `review_fit` are fit independently on different positive definitions (`__main__.py:490-498`). Nothing enforces `fail_edge <= review_edge`; review threshold can end up **below** fail threshold, inverting the band.

**Adopt?** Yes [ACTIONABLE-NOW]. After both fits, clamp so `fail_edge <= review_edge`, or fit review on samples with `label != fail` only.

**Severity:** [HIGH]

---

### 2.3 Multi-threshold at different granularities

**mdream:** Three fixture tiers with different `minOutputKB` (5, 10, 50 KB at `fixture-parity.test.ts:10-12`); cross-engine link tolerance 2%; length tolerance 1%.

**calibrate.py:** Single scalar edge per band on `unigram_coverage` only (`calibrate.py:149-185`). No per-axis calibration for `nid/teds/mhs`, no per-corpus-size stratum.

**Adopt?** Yes for bench axes: either separate ROC per axis or mdream-style hand floors per stratum until labeled data exists.

**Severity:** [MEDIUM]

---

### 2.4 No cross-validation or holdout

**mdream:** Fixed fixtures; no train/test split (no learner).

**calibrate.py:** Fits on entire `--labels` file; reports in-sample TPR/FPR only (`calibrate.py:136-146`).

**Adopt?** Yes when label count allows (e.g. leave-one-out or k-fold minimum TPR). mdream avoids overfit by exact fixtures, not statistics.

**Severity:** [MEDIUM]

---

### 2.5 Class imbalance and sparse positives

**mdream:** Parity matrix runs hundreds of HTML cases; imbalance is structural (many pass cases).

**calibrate.py:** Requires both classes (`calibrate.py:166-169`); no weighting, no minimum positive count beyond nonzero.

**Adopt?** Yes. Require `n_pos >= N` (e.g. 5) and report Wilson CI on FPR/TPR for small samples.

**Severity:** [MEDIUM]

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Function | Scenario | Break | Severity |
|----------|----------|-------|----------|
| `_evaluate_paper` | `prior=0.99`, `cur=0.9700000000000001` (IEEE noise) | `drop = round(prior-cur,4)` may be `0.0199` or `0.0200` at slack boundary; `cur` not pre-rounded | [HIGH] |
| `diff_rows` | Duplicate `pid` in `rows` (duplicate corpus entries) | Two `GuardFinding`s for same pid; baseline lookup ambiguous | [MEDIUM] |
| `diff_rows` | `baseline` is bench `report.json` (wrong `kind`) | Silent partial diff; no validation (`guard.py:212-214`) | [MEDIUM] [ACTIONABLE-NOW] |
| `diff_rows` | Baseline stores `axis_slack: 0.03`, CLI uses default `0.02` | Gate uses wrong slack vs committed contract | [MEDIUM] [ACTIONABLE-NOW] |
| `run_bench` → guard | `teds`/`nid` is NaN (metric bug) | Comparisons `axes[axis] < floor` and `drop > slack` all False; paper passes | [CRITICAL] [ACTIONABLE-NOW] |
| `calibrate_threshold` | All samples `unigram_coverage=0.91` (zero variance) | `_candidate_thresholds` returns `[0.91, 1.91]`; feasible point may flag zero papers, TPR=0 | [MEDIUM] [ACTIONABLE-NOW] |
| `calibrate_threshold` | `target_fpr=1.5` or negative | Unvalidated (`calibrate.py:149-154`); `feasible` set wrong | [MEDIUM] [ACTIONABLE-NOW] |
| `calibrate_threshold` | `value=float('nan')` in samples | Sort order undefined; `value < t` always False for NaN | [HIGH] [ACTIONABLE-NOW] |
| `_calibrate_main` | All labels `pass` or all `fail` | `ValueError` raised (`calibrate.py:166-169`); OK but no partial report | [LOW] |
| `_calibrate_main` | 1 fail, 99 pass, `target_fpr=0.05` | High-variance FPR estimate; edge unstable | [MEDIUM] |
| `_load_corpus_pairs` | GT file exists, candidate missing (skipped) | Guard runs subset; if baseline not updated, `missing` fires; if user drops GT, silent shrink | [MEDIUM] |
| `_evaluate_paper` | Known weak paper stable but `below_floor` populated | `status=ok` despite `below_floor` strings; CI summary may confuse (`guard.py:192-198`) | [LOW] |

---

## 4. MISSING AXIS / CHECK

| mdream check | Evidence | whisker equivalent |
|--------------|----------|-------------------|
| String vs stream parity | `fixture-parity.test.ts:50-56` | None on bench/guard path |
| JS vs Rust / dual-engine exact or ratio | `fixture-parity.test.ts:62-113` | None (single converter) |
| Reading order (`indexOf` ordering) | `streaming.test.ts:31-33` | `reading_order` metric exists but not gated (`constants.py:99`) |
| Heading count + level match | `fixture-parity.test.ts:89-98` | `mhs` only (fuzzy tree edit distance) |
| Link count ±2% | `fixture-parity.test.ts:101-113` | None |
| Output byte-size floor per fixture | `fixture-parity.test.ts:10-12,41` | None |
| Exact substring / anchor presence | `streaming.test.ts:27-28`, `client-bundle.browser.test.ts:54-59` | None (gap-matrix #9) |
| Per-chunk stream snapshot | `fetch.test.ts:27-33` | N/A (tomd not streaming) |
| Browser screenshot regression | `integration/__screenshots__/*.png` | None |
| Chunk metadata (headers, code lang) | `splitter.test.ts:59-69,1029-1030` | None |
| Malformed HTML recovery parity | `fixture-parity.test.ts:615-632`, `malformed-html.test.ts` | Not scored on guard path |
| Tiered CI (PR Linux vs main OS matrix) | `.github/workflows/test.yml:42,153` | whisker guard not in CI matrix yet |

---

## 5. TOP PORTABLE DETAIL

**Adopt:** normalize both sides with **`trimEnd()` before equality compare**, with an explicit comment that one path may emit trailing whitespace from flush semantics.

```typescript
// fixture-parity.test.ts:54-55
expect(streamResult.trimEnd()).toBe(stringResult.trimEnd())
```

**Why:** mdream treats batch and stream as one contract; whitespace-only drift must not fail or pass spuriously. whisker should apply the same rule wherever two scoring paths are diffed (re-score vs cached sidecar, PDF vs HTML candidate, rounded metric inputs before slack compare).

**Secondary (structural, not scalar):** heading level match loop (`fixture-parity.test.ts:94-98`) and link-count tolerance `Math.abs(a-b)/max(a,1) < 0.02` (`fixture-parity.test.ts:112-113`) as cheap regex baselines alongside `nid/teds/mhs`.
