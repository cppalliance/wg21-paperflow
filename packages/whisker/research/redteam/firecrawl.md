# Red-team: whisker guard/calibrate vs firecrawl QA

**Source repo:** `packages/whisker/research/repos/firecrawl/` (deep-read June 2026)  
**Target:** `guard.py`, `calibrate.py` (+ CLI wiring in `__main__.py`)

## Summary

- Firecrawl gates conversion quality with **124 `markdown.toContain` / `not.toContain` substring anchors** across scrape paths (`apps/api/src/**/*.ts`), not committed metric snapshots; whisker guard has no content-anchor layer beneath fuzzy bench axes.
- Firecrawl runs the **same scrape assertions across an engine matrix** (`undefined`, `fire-engine;chrome-cdp`, `fire-engine;tlsclient`, `fetch`) and a **CI matrix** (engine × proxy × search × ai × nuq) so regressions cannot hide on one path (`scrapeURL.test.ts:24-37`, `test-server.yml:15-30`).
- PDF shadow comparison uses **joint multi-metric tier thresholds** (`lenRatio >= 0.8 AND numberPreservation >= 0.9` → good; else acceptable/poor) plus **table-count diff**; guard diffs axes independently with slack but has no length/number/table auxiliary checks (`shadowComparison.ts:54-61`).
- Firecrawl asserts **metadata, HTTP status, unicode, links/images formats, and change-tracking** as separate axes; guard only stores bench metrics and ignores verdict transitions, metadata, and format-specific outputs.
- **Concrete whisker bugs exposed:** duplicate PIDs duplicate findings; `NaN`/`inf` coverage values silently break calibration; identical bad/good scores yield TPR=0 at `max_tpr_at_fpr`; baseline `axis_slack` is stored but never read during diff.

---

## 1. REGRESSION-GATE GAPS

### 1.1 Content substring anchors (must / must-not) [HIGH] — adopt (follow-on layer)

Firecrawl asserts that converted markdown **contains** expected phrases and **excludes** stripped content, per URL and per scrape option:

- `expect(out.document.markdown).toContain("Firecrawl Test Site")` (`scrapeURL.test.ts:55`)
- `expect(out.document.markdown).not.toContain("[FAQ](/faq/)")` after `excludeTags` (`scrapeURL.test.ts:142-143`)
- Unicode CJK anchor on `/blog/unicode-post` (`scrape.test.ts:191-193`)
- Go html-to-md service: `contains(response.Markdown, tc.expectedOutput)` (`handler_test.go:157-162`)

**guard.py gap:** `_evaluate_paper` only compares float axes (`guard.py:172-184`); no `must_include` / `must_not_include` per PID. Formatting churn that preserves NID can still drop a legally required phrase; firecrawl would catch it, guard would not.

**Adopt?** Yes, as a per-paper facts file (already noted in `gap-matrix.md` #9). Not inside guard's float diff, but guard report should surface anchor failures alongside metric regressions.

### 1.2 Metadata and HTTP-status axes [HIGH] — adopt (separate guard fields)

Firecrawl gates **metadata independently** of markdown body:

- Title, description, og* fields, `statusCode`, `sourceURL` (`scrapeURL.test.ts:56-71`)
- Error pages: expects `metadata.statusCode` 400/401/403/404/405/500 (`scrapeURL.test.ts:162-257`)

**guard.py gap:** baseline stores only `nid/teds/mhs/overall/reading_order` (`guard.py:65-71`, `baseline_from_rows:144`). A conversion that preserves text similarity but breaks front-matter title or returns wrong HTTP semantics passes guard.

**Adopt?** Yes for WG21 papers: YAML front-matter fields (`title`, `document`, `date`) are contractually fixed; guard should baseline and diff them.

### 1.3 Multi-path / multi-engine matrix [MEDIUM] — adopt for tomd source-type stratification

Firecrawl replays identical quality checks under `describe.each(testEngines)` (`scrapeURL.test.ts:24-37`). CI multiplies dimensions: engine, proxy, search, AI, NuQ backend (`test-server.yml:15-30`, `264-265`).

**guard.py gap:** one bench row per PID regardless of PDF vs HTML source or conversion options. A regression visible only on HTML papers or a specific tomd code path can pass if the corpus is PDF-heavy.

**Adopt?** Yes: stratify baseline keys as `(pid, source_kind)` or run guard separately per source family.

### 1.4 Negative / exclusion assertions [HIGH] — adopt with anchors

Firecrawl verifies **content removal** (`not.toContain`) when `excludeTags` / `onlyMainContent` apply (`scrapeURL.test.ts:118-119`, `142-144`; `html-transformer.test.ts:354-357`).

**guard.py gap:** floors and slack only detect score *drops*; they never assert forbidden substrings (navigation, footer, injected boilerplate).

**Adopt?** Yes via must-not anchors; guard cannot infer exclusions from metric deltas alone.

### 1.5 Joint multi-metric PDF shadow tiers (not per-axis slack) [HIGH] [ACTIONABLE-NOW] — adopt for PDF bench auxiliary gate

Firecrawl's PDF engine shadow compare requires **both** length ratio and numeric preservation:

```typescript
if (lenRatio >= 0.8 && numberPreservationRatio >= 0.9) overallMatch = "good";
else if (lenRatio >= 0.5 && numberPreservationRatio >= 0.7) overallMatch = "acceptable";
```

(`shadowComparison.ts:54-61`). Also diffs **table counts** (`shadowComparison.ts:51-52`, `66-84`).

**guard.py gap:** each axis regresses independently with uniform slack (`guard.py:172-184`); correlated small drops on length + numbers + tables can each stay under `GUARD_AXIS_SLACK` while overall content is "poor" by firecrawl's joint rule.

**Adopt?** Yes: add auxiliary shadow metrics to baseline or a composite "poor" rule for PDF papers.

### 1.6 Pre-compare normalization [MEDIUM] — partial; harden

Firecrawl normalizes before cross-version compare: `parseMarkdown(productionHTML)` then Jaccard word similarity (`ab-test-comparison.ts:60-67`). HTML transformer tests normalize via `transformHtml` before substring checks (`html-transformer.test.ts:311-358`).

**guard.py gap:** metrics use `normalized_text` internally, but baseline JSON stores rounded floats (`baseline_from_rows:144`) without recording normalizer version; guard does not detect normalizer drift separately from converter drift.

**Adopt?** Partially present; add `normalizer_version` / schema field to baseline and fail on mismatch.

### 1.7 Added-corpus-item detection [MEDIUM] [ACTIONABLE-NOW] — adopt

Firecrawl encodes corpus membership in **test code**; a new URL without a test is invisible until someone adds one.

**guard.py gap:** new PIDs get `STATUS_NEW` and **pass** (`guard.py:165-169`, `52-53`; verified: added `NEW` alongside baseline `P1` → `report.failed False`). Corpus can grow without an explicit `--update` review of new entries.

**Adopt?** Yes: optional `--fail-on-new` or require new PIDs to appear in baseline after review (fail until baselined).

### 1.8 Missing-item detection [PRESENT] — keep

Firecrawl has no symmetric metric baseline; whisker **hard-fails** when baseline PIDs vanish (`guard.py:113-115`, `221`). Matches the "dropped paper hides regression" concern; firecrawl would only catch this if the test URL is removed from code.

### 1.9 Known-bad / expectedFailure monotonic baselines [LOW] — partial

Firecrawl **comments out** broken domains (`scrape.test.ts:174-179` `// TEMP: domain broken`) and uses `describeIf` / `concurrentIf` to skip when infra unavailable (`snips/lib.ts:45-48`).

**guard.py gap:** papers below floor in baseline are not re-flagged if stable (`test_guard.py:84-92`), but there is no explicit `expectedFailure` bit in baseline JSON—behavior is implicit via "already below floor."

**Adopt?** Optional explicit `expected_weak: ["teds"]` in baseline for audit clarity; behavior is mostly correct.

### 1.10 Refresh ritual [PRESENT] — keep

Firecrawl has **no metric baseline refresh**; expectations live in test source. whisker's `--update` (`__main__.py:329-367`) is the pandoc-style ritual firecrawl lacks for numeric regression. Correct for whisker's model.

### 1.11 Statistical vs exact tolerance [MEDIUM] — different tradeoff

Firecrawl uses **exact substring** checks and **fixed ratio thresholds** (5% AB variance: `ab-test-comparison.ts:5-6`, `67`; engpicker similarity 0.85: `engpicker.ts:288-290`). No per-paper float slack.

**guard.py gap:** `GUARD_AXIS_SLACK = 0.02` (`constants.py:94`) allows bounded metric erosion invisible to firecrawl's anchor model.

**Adopt?** Keep slack for fuzzy metrics, but add exact anchors for legal/requirement text firecrawl-style.

### 1.12 External on-demand quality eval [LOW] — note for CI

Firecrawl dispatches `#scrape-quality-eval` to external `scrape-evals` repo (`scrape-evals.yml:9-69`); post-deploy prod benchmark via `eval_run.py` (`eval-prod.yml:34-36`).

**guard.py gap:** no hook for out-of-repo eval dispatch.

**Adopt?** Optional CI workflow trigger; not guard.py core.

---

## 2. CALIBRATION GAPS

Firecrawl **does not ROC-calibrate** from labeled corpora; thresholds are engineering constants. `calibrate.py` is ahead on principled FPR-bounded ROC fit, but firecrawl exposes gaps in **what** gets calibrated and **how** thresholds combine.

### 2.1 Multi-metric joint operating points [HIGH] [ACTIONABLE-NOW]

Shadow PDF verdict requires **simultaneous** lenRatio and numberPreservation (`shadowComparison.ts:55-58`). AB compare uses Jaccard **word-set** similarity with 5% variance (`ab-test-comparison.ts:18-31`, `5-6`). Engpicker uses three thresholds together (`engpicker.ts:288-295`).

**calibrate.py gap:** fits **one scalar** `unigram_coverage` edge per call (`calibrate.py:149-185`); no joint fit across `(length_ratio, number_preservation, table_count)` or across `(fail_edge, review_edge)` with ordering constraints.

**Adopt?** Yes: add composite gate calibration or enforce `fail_edge < review_edge` after independent fits (`__main__.py:494-499` does not check ordering).

### 2.2 Per-axis / per-signal calibration [HIGH]

Firecrawl maintains **separate thresholds per signal** (length, numbers, tables, Jaccard similarity, Levenshtein similarity, HTTP status). **calibrate.py** only targets content coverage (`__main__.py:488-491`); bench floors `NID/TEDS/MHS` remain hand-set (`constants.py:56-58`).

**Adopt?** Yes: extend calibrate to accept labeled bench rows and fit per-axis floors with the same ROC machinery.

### 2.3 Cross-validation / holdout [MEDIUM]

Firecrawl's fixed thresholds are validated by **extensive e2e snips** (vitest `test:snips`, `package.json:22`) across CI matrix, not by k-fold. No labeled holdout set.

**calibrate.py gap:** fits on all labels in one file; no train/test split, no reported confidence interval on TPR/FPR.

**Adopt?** Yes for production promotion: leave-one-out or simple holdout before writing `thresholds.json`.

### 2.4 Class imbalance handling [MEDIUM]

Firecrawl implicitly handles rare failures via many positive `toContain` tests per feature. **calibrate.py** uses `target_fpr` ceiling (`calibrate.py:40-43`, `174-177`) but no explicit **minimum TPR floor** or **prevalence weighting** when positives are rare.

**Adopt?** Add `min_tpr` constraint and report `n_pos/n_neg` warnings when `n_pos < 10`.

### 2.5 Normalization-before-calibration [MEDIUM]

Firecrawl always compares **post-`parseMarkdown`** outputs (`ab-test-comparison.ts:60-64`). **calibrate.py** scores via `score_paper` when `unigram_coverage` absent (`__main__.py:448-451`); if labels file mixes precomputed and live-scored rows, distribution can shift.

**Adopt?** Require single source: always rescore or always use frozen coverage values; document in calibration artifact.

### 2.6 No calibration refresh audit trail [LOW]

Firecrawl changes thresholds by editing source constants (`shadowComparison.ts:55-58`). **calibrate.py** emits JSON (`__main__.py:504-516`) but human promotion to `constants.py` is manual—same as firecrawl's code-edit model. Adequate.

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Severity | Function | Scenario | Behavior | Firecrawl lesson |
|----------|----------|----------|----------|------------------|
| [HIGH] [ACTIONABLE-NOW] | `calibrate_threshold` | Labeled sample with `unigram_coverage=NaN` (score failure propagated) | `value < threshold` is False for NaN → never flagged; TPR collapses silently (runtime: NaN sample → `tpr=0.5`) | Firecrawl rejects invalid inputs early (`handler_test.go:189-201` empty HTML → 400) |
| [HIGH] [ACTIONABLE-NOW] | `calibrate_threshold` | `+inf` coverage on bad paper | Never flagged (`inf < t` is False) | Firecrawl validates response shape before assert (`scrapeURL.test.ts:48-49`) |
| [HIGH] [ACTIONABLE-NOW] | `calibrate_threshold` | Bad and good share **identical** coverage (e.g. both 0.85) | Chooses `threshold=0.85`, `tpr=0.0`, `fpr=0.0` under `target_fpr=0.0` — declares success while catching nothing | Firecrawl would still fail a `toContain` anchor independent of score |
| [MEDIUM] [ACTIONABLE-NOW] | `diff_rows` | Duplicate `pid` in `rows` | Emits **two findings** for same PID (runtime: 2× `P1`); no dedup error | Firecrawl tests one URL per case block |
| [MEDIUM] [ACTIONABLE-NOW] | `diff_rows` / `baseline_from_rows` | Baseline stores `axis_slack` (`baseline_from_rows:141`) but diff uses CLI `slack` only (`guard.py:201-206`) | Committed slack ignored; local `--slack` override can desync from baseline intent | Firecrawl constants live in test/config source (`ab-test-comparison.ts:5`, `shadowComparison.ts:55`) |
| [MEDIUM] | `calibrate_threshold` | `target_fpr` negative or >1 | No validation; `fpr <= 1.5` accepts all thresholds | Firecrawl uses named constants with semantic bounds |
| [MEDIUM] | `_calibrate_main` | After independent fail/review fits | No check that `fail_edge <= review_edge` | Firecrawl tier thresholds are ordered (`acceptable` wider than `good`, `shadowComparison.ts:55-58`) |
| [LOW] | `diff_rows` | Empty `rows`, non-empty baseline | `findings=[]`, `missing` populated, `failed=True` (`guard.py:216-222`) | Correct fail, but human summary omits "zero papers scored" context |
| [LOW] | `_evaluate_paper` | Improvement above baseline | Never surfaces "unexpected improvement" (firecrawl would require new anchor if content grows) | Informational only |
| [LOW] | `calibrate_threshold` | `-inf` coverage | Always flagged for any finite threshold | Pathological; reject non-finite inputs |

---

## 4. MISSING AXIS / CHECK (firecrawl gates, whisker has no equivalent)

| Axis | Firecrawl evidence | Whisker status |
|------|-------------------|----------------|
| **Substring must-include / must-not** | 124× `markdown…toContain` in `apps/api/src` | Absent (metrics only) |
| **HTTP / metadata correctness** | `metadata.statusCode`, title, og* (`scrapeURL.test.ts:56-71`) | Absent in guard baseline |
| **Links / images extract formats** | `formats: ["links"]`, `["images"]` with length/count checks (`scrape.test.ts:198-224`) | Absent |
| **Raw HTML structure** | `html.toContain("<h1")` when `formats: ["markdown","html"]` (`scrapeURL.test.ts:94-95`) | Absent |
| **Change-tracking / diff** | `changeTracking` modes git-diff / json (`scrape.test.ts:646-1150`) | Absent |
| **PDF length + numeric preservation + table count** | `comparePdfOutputs` (`shadowComparison.ts:27-76`) | Partially via TEDS/NID; no length/number aux |
| **Cross-engine parity** | Engine matrix (`scrapeURL.test.ts:24-37`) | Absent |
| **Unicode / encoding fidelity** | CJK post (`scrape.test.ts:181-195`) | Not isolated in guard (depends on NID) |
| **Configuration-scoped output** | `excludeTags`, `onlyMainContent` (`scrapeURL.test.ts:100-144`) | Absent |
| **Verdict transition (pass→review→fail)** | N/A (no whisker verdict in firecrawl) | Absent per `gap-matrix.md` #3 |
| **Zero-data-retention / logging** | ZDR suppresses logs (`handler_test.go:264-300`) | Out of scope for guard |

---

## 5. TOP PORTABLE DETAIL

**Adopt firecrawl's PDF shadow joint tier gate** as an auxiliary regression check for PDF papers:

```typescript
// shadowComparison.ts:54-61
if (lenRatio >= 0.8 && numberPreservationRatio >= 0.9) {
  overallMatch = "good";
} else if (lenRatio >= 0.5 && numberPreservationRatio >= 0.7) {
  overallMatch = "acceptable";
} else {
  overallMatch = "poor";
}
```

Supporting helpers at `shadowComparison.ts:16-24` (`extractNumbers` via `\d+(?:\.\d+)?`, `countTables` via markdown separator rows).

**Why this over the 124× `toContain` pattern:** WG21 guard already has labeled GT markdown for bench; length/number/table preservation catches catastrophic PDF text loss that can leave NID/TEDS partially inflated (dropped sections, missing numeric tokens, lost tables). Implementation path: compute `(lenRatio, numberPreservationRatio, table_delta)` in `bench.py`, store in guard baseline, fail on transition to `poor` or table-count drop—**[ACTIONABLE-NOW]** in `guard.py` + `bench.py` without a new facts-file system.

**Runner-up (content anchors):** `expect(out.document.markdown).toContain("Firecrawl Test Site")` / `not.toContain` pattern (`scrapeURL.test.ts:55`, `142-143`) — highest firecrawl test volume, best for legal anchor text, but requires new per-PID facts schema (later phase per `gap-matrix.md` #9).
