# Red-team: whisker guard/calibrate vs html-to-markdown-py

Source repo: `packages/whisker/research/repos/html-to-markdown-py/` (kreuzberg-dev/html-to-markdown, shallow clone June 2026). Primary QA surface: `tools/benchmark-harness/` (`htmbench`), 116 committed `.snap` files, `guardrails.json`, `groups.toml`, tier-oracle tests in `crates/html-to-markdown/tests/`.

## Summary

- html-to-markdown-py gates **byte-exact markdown output** (116 snapshots × 4 option permutations) before any numeric slack; whisker guard only diffs four float axes and can miss content regressions that preserve NID/TEDS/MHS. **[CRITICAL]**
- The external repo stratifies tolerance by **fixture group** (`clean_large` 5%, `adversarial` 30% in `guardrails.json`); whisker uses one global `GUARD_AXIS_SLACK=0.02` for every paper. **[HIGH] [ACTIONABLE-NOW]**
- Known failures are first-class: oracle panics and tier quirks are **explicitly skipped/allowlisted**, not silent passes; whisker has monotonic weak baselines but no `expectedFailure`/panic skip and no improvement-must-refresh rule. **[HIGH]**
- html-to-markdown-py does **not** calibrate quality thresholds (hand-set guardrails only); whisker `calibrate.py` is ahead, but it shares no corpus stratification, no multi-axis fit, and mishandles NaN labels. **[MEDIUM]**
- Top portable artifact: **`guardrails.json` per-group `max_regression_pct` map** (`tools/benchmark-harness/guardrails.json:4-10`) plus the **oracle bless ritual** (`oracle.rs:90-113`, `main.rs:265-267`).

---

## 1. REGRESSION-GATE GAPS

### 1.1 Byte-exact output snapshots vs float-axis-only diff

**What html-to-markdown-py does:** Each fixture × four `Permutation`s produces a committed `.snap`; CI runs `htmbench oracle` and fails on `actual != expected` with a line diff (`oracle.rs:161-168`, `main.rs:291-302`). 116 snapshots cover 29 fixtures (`CHANGELOG.md:325`, snapshot dir count).

**What guard.py does:** `diff_rows` compares rounded `nid`/`teds`/`mhs`/`overall` only (`guard.py:172-198`); no markdown artifact.

**Gap:** A change can alter headings, link targets, table pipes, or whitespace while leaving block-matched metrics unchanged. Exact output gate catches this; guard does not.

**Adopt?** Partially. Full byte snapshots need a committed golden corpus (whisker Phase 4c follow-on). Until then, guard should at minimum fail when **output hash or sidecar verdict** regresses, not only floats.

**Severity:** [CRITICAL]

---

### 1.2 Configuration permutation matrix (4 variants per fixture)

**What html-to-markdown-py does:** `Permutation::ALL` runs Default, NoImages, NoMetadata, AtxClosed per fixture (`oracle.rs:37-42`, `main.rs:281-304`).

**What guard.py does:** One score path per paper via `run_bench` (`__main__.py:358`).

**Gap:** Option-sensitive regressions (heading style, metadata stripping, code-block style) pass guard if the default path is unchanged.

**Adopt?** Yes for any paper where conversion options vary; store baseline keys as `(pid, profile)` or run guard under each profile.

**Severity:** [HIGH]

---

### 1.3 Per-group tolerance vs global slack

**What html-to-markdown-py does:** `cmd_compare` loads per-group `max_regression_pct` from `guardrails.json` (`main.rs:215-218`, `guardrails.json:4-10`): e.g. `clean_large` 5%, `adversarial` 30%.

**What guard.py does:** Single `slack` parameter defaulting to `C.GUARD_AXIS_SLACK` (0.02) for every paper (`guard.py:205`, `constants.py:94`).

**Gap:** Large/adversarial WG21 papers need looser slack or stricter floors than clean one-page HTML; one constant mis-fires in both directions.

**Adopt?** Yes. [ACTIONABLE-NOW] Add optional `groups` map in baseline JSON (mirroring `groups.toml`) and resolve slack/floor per paper group.

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

### 1.4 Exact equality vs numeric slack semantics

**What html-to-markdown-py does:** Oracle uses strict string equality (`oracle.rs:161`); perf compare uses relative percent with zero baseline guard (`main.rs:220-233`).

**What guard.py does:** Absolute drop with `round(prior - cur, 4) > slack` (`guard.py:180-181`).

**Gap:** Different semantics: html-to-markdown never allows a one-byte output drift; guard allows up to 0.02 per axis (and compound erosion across axes only if each axis stays under slack unless `overall` also drops).

**Adopt?** Keep absolute slack for fuzzy metrics, but document that it is looser than byte-exact; pair with output anchors or hashes for high-risk papers.

**Severity:** [MEDIUM]

---

### 1.5 Known-bad / expectedFailure / panic fixtures

**What html-to-markdown-py does:** Oracle catches convert panics on `kimbrain.html`/`rbloggers.html`, logs NOTE, treats as skip not fail (`oracle.rs:10-14`, `103-111`, `151-158`). Tier test allowlists `KNOWN_TIER2_QUIRK_FIXTURES` (`tier1_byte_equality_test.rs:107-122`).

**What guard.py does:** Monotonic model for papers already below floor (`guard.py:84-92`, `166-169`): stable weak papers stay `ok`; no explicit `expectedFailure` status or skip list.

**Gap:** Papers that **always error** (missing source, scorer exception) are skipped in CLI (`__main__.py:256-258`) but not recorded in baseline as known-bad; re-run behavior differs from oracle's tracked skip.

**Adopt?** Yes. Add `expected_failure` / `skip` entries in baseline so CI distinguishes "known broken" from "newly broken."

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

### 1.6 Refresh ritual and baseline audit metadata

**What html-to-markdown-py does:** `htmbench oracle --bless` overwrites snapshots (`main.rs:265-267`, `benchmark.yml:20-23`); perf baselines record `schema`, git `sha`, `host`, `created_at` (`schema.rs:32-42`, `main.rs:164-170`). CHANGELOG states baselines are human-blessed, not CI-written (`CHANGELOG.md:360`).

**What guard.py does:** `--update` writes baseline via `baseline_from_rows` (`__main__.py:361-367`); stores `schema_version`, `kind`, `axis_slack`, `floors` but **no git sha / timestamp / host**.

**Gap:** Weaker audit trail for "who refreshed what when"; harder to correlate a baseline bump with a code change.

**Adopt?** Yes for metadata fields; bless/update remains human-only (already correct).

**Severity:** [MEDIUM] [ACTIONABLE-NOW]

---

### 1.7 Missing / added item detection asymmetry

**What html-to-markdown-py does:** Missing baseline entry for a result fixture → **warn and skip**, CI still passes (`main.rs:210-212`). Missing snapshot on non-panic path → **hard fail** with "run oracle --bless" (`oracle.rs:136-141`). `find_ungrouped()` detects HTML files absent from `groups.toml` (`fixture.rs:89-105`).

**What guard.py does:** Baseline paper absent from current run → **hard fail** (`guard.py:221`, `113-115`). New paper with no baseline → `STATUS_NEW`, passes unless below floor (`guard.py:165-169`).

**Gap:** whisker is stricter on removals (good) but **too loose on additions**: new corpus members silently pass. html-to-markdown requires explicit bless for new oracle snapshots.

**Adopt?** Fail or require `--update` when baseline count increases (opt-in flag for deliberate corpus expansion).

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

### 1.8 Baseline payload fields ignored on read

**What html-to-markdown-py does:** Compare loads full `RunResults` schema and matches by fixture key (`main.rs:202-207`).

**What guard.py does:** Writes `axis_slack` and `floors` into baseline (`guard.py:141-142`) but `diff_rows` always uses call-time `slack` and module `C.*_FLOOR` (`guard.py:161-162`, `205`); does not validate `kind` or `schema_version` on read.

**Gap:** Editing committed baseline slack/floors has no effect; wrong JSON kind could diff silently.

**Adopt?** Yes. [ACTIONABLE-NOW] Honor baseline `axis_slack`/`floors` when present; reject wrong `kind`/schema.

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

### 1.9 Normalization before diff

**What html-to-markdown-py does:** Oracle compares **raw converter output** bytes (`oracle.rs:161`); normalization is absent by design (output is the contract).

**What guard.py does:** Metrics run through `normalized_text`, block matching, TEDS HTML wrapper (`bench.py:157-160`); guard diffs post-normalized scores.

**Gap:** Guard cannot detect regressions in **normalization/matching code** that cancel in both candidate and reference paths; html-to-markdown would catch any output shift.

**Adopt?** Add metric invariant tests (whisker Phase 4c) plus optional raw-md hash column in baseline.

**Severity:** [MEDIUM]

---

### 1.10 Statistical vs deterministic gating

**What html-to-markdown-py does:** Perf gate uses calibrated iteration count, best-of-3 timing (`bench.rs:34-119`); quality gate is deterministic exact compare.

**What guard.py does:** Deterministic metric re-score (documented in `constants.py:90-93`).

**Gap:** None on determinism; whisker is aligned with oracle quality path, not perf path.

**Adopt?** N/A (keep deterministic).

**Severity:** [LOW]

---

## 2. CALIBRATION GAPS

html-to-markdown-py has **no ROC/TPR/FPR calibration**; thresholds are hand-set in `guardrails.json` (`schema.rs:47-49`) and tier/oracle tests. whisker `calibrate.py` is already more principled for coverage edges. Gaps are relative to what a mature combined system would need:

### 2.1 No labeled operating-point workflow in external repo

**External:** Static `max_regression_pct` per group (`guardrails.json:4-10`).

**calibrate.py:** Sweeps thresholds, max TPR at FPR ceiling, Youden fallback (`calibrate.py:149-180`).

**Gap:** calibrate does not emit or fit **guard slack** or **bench metric floors** (`NID_FLOOR`, etc.); only `unigram_coverage_*` edges (`__main__.py:488-499`).

**Adopt?** Extend calibrate to fit per-axis bench floors from labeled bench rows, not only coverage.

**Severity:** [MEDIUM]

---

### 2.2 No per-group / per-axis calibration

**External:** Per-group perf thresholds only.

**calibrate.py:** One global sweep per edge name; no paper group, no `nid`/`teds`/`mhs` axes.

**Gap:** Class imbalance and axis correlation across paper types are ignored; a single fail edge may over-flag multi-column papers.

**Adopt?** Stratify labels by corpus tag before sweep (mirror `groups.toml`).

**Severity:** [MEDIUM]

---

### 2.3 No cross-validation

**External:** N/A.

**calibrate.py:** Fits on full label set; no holdout fold.

**Gap:** Reported TPR/FPR are in-sample only; overfit risk on 30–50 paper labels noted in `constants.py:14-15`.

**Adopt?** Optional k-fold or holdout reporting in calibration artifact.

**Severity:** [LOW]

---

### 2.4 Multi-threshold coupling

**External:** Oracle (quality) + guardrails (perf) are separate gates in CI (`CHANGELOG.md:357-360`).

**calibrate.py:** Fits fail and review edges independently (`__main__.py:494-498`) without enforcing `fail_edge <= review_edge`.

**Gap:** Fitted review edge can drift below fail edge on small samples.

**Adopt?** [ACTIONABLE-NOW] Constrain `review_edge >= fail_edge` after fit.

**Severity:** [MEDIUM] [ACTIONABLE-NOW]

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Function | Scenario | Behavior | Severity |
|----------|----------|----------|----------|
| `diff_rows` | `rows=[]`, `baseline=None` | Returns `failed=False` (vacuous pass). Verified: `failed False`. | [CRITICAL] [ACTIONABLE-NOW] |
| `diff_rows` / `_evaluate_paper` | `BenchRow` with `nid=float('nan')` | `STATUS_NEW`, `failed=False`; NaN never `< floor`, never regresses. | [CRITICAL] [ACTIONABLE-NOW] |
| `calibrate_threshold` | Sample `(nan, True)` + good paper | Runs; chosen point TPR=0 (bad never flagged). Silent false negative. | [CRITICAL] [ACTIONABLE-NOW] |
| `baseline_from_rows` | Duplicate `pid` in input rows | Dict last-wins silently (`{'P1': … teds: 0.5}` overwrites 0.99). | [HIGH] [ACTIONABLE-NOW] |
| `diff_rows` | Baseline stores `axis_slack: 0.5` but CLI uses `0.02` | Ignores stored slack; still `regressed`. Verified. | [HIGH] [ACTIONABLE-NOW] |
| `diff_rows` | Baseline JSON wrong `kind` / missing `rows` | Accepts `{}` as empty baseline; no validation. | [HIGH] [ACTIONABLE-NOW] |
| `diff_rows` | New paper added to corpus | `STATUS_NEW` passes gate; html-to-markdown requires bless. | [HIGH] [ACTIONABLE-NOW] |
| `_load_corpus_pairs` | Duplicate `*.gt.md` mapping to same PID | Undefined ordering; duplicate bench rows. | [MEDIUM] |
| `calibrate_threshold` | Single positive or single negative | Raises `ValueError` (correct). | OK |
| `calibrate_threshold` | All identical values, mixed labels | Youden fallback; arbitrary tie-break (`calibrate.py:177-180`). | [MEDIUM] |
| `calibrate_threshold` | Empty `samples` | CLI rejects (`__main__.py:484-486`); library not called empty. | OK |
| `_confusion` | `value < threshold` with float noise at 4 decimals | Guard rounds drop; calibrate does not round inputs before sweep. | [LOW] |
| `diff_rows` | Huge corpus | O(n) per paper; no batching issue. | OK |
| Unicode / identical all-pass | Normal float compare | OK | OK |

---

## 4. MISSING AXIS / CHECK

Quality axes or assertions html-to-markdown-py gates on that whisker guard/calibrate lack:

| External check | Evidence | whisker equivalent |
|----------------|----------|-------------------|
| **Byte-exact markdown output** | `oracle.rs:161-168` | None in guard (metrics only) |
| **Four conversion profiles per fixture** | `oracle.rs:24-42` | Single bench path |
| **Tier-1 vs Tier-2 byte equality** | `tier1_byte_equality_test.rs:96-165` | None |
| **Tier-1 property: never wrong Ok output** | `tier1_property_test.rs:1-54` | None |
| **Perf regression per fixture (ms_best)** | `main.rs:220-233` | N/A for quality (whisker is not perf gate) |
| **Output byte length (`output_bytes`)** | `schema.rs:23-24` (recorded, not compared) | None |
| **Feature coverage survey** (CDATA, custom elements, bare `<`, table-no-tbody) | `survey.rs:16-24`, `56-67` | None |
| **Ungrouped fixture detection** | `fixture.rs:89-105` | None for `<pid>.gt.md` orphans |
| **Substring / structural e2e anchors** | `e2e/python/tests/test_visitor.py:38-40` (must contain) | None (recommended whisker follow-on: facts file) |
| **CommonMark spec vectors** | `packages/python/tests/commonmark_spec.json` | None |
| **Prescan structural flags** | `prescan_test.rs:14-56` | whisker `gates.py` separate from guard |
| **Panic-as-known-skip registry** | `oracle.rs:10-14` | None |

**Severity:** Missing byte-oracle and permutation matrix are [CRITICAL] for parity with html-to-markdown's core QA contract; survey/ungrouped/tier checks are [MEDIUM] hygiene.

---

## 5. TOP PORTABLE DETAIL

**Adopt:** Per-group regression threshold map from `tools/benchmark-harness/guardrails.json`:

```json
"thresholds": {
  "clean_small": { "max_regression_pct": 10 },
  "clean_medium": { "max_regression_pct": 8 },
  "clean_large": { "max_regression_pct": 5 },
  "adversarial": { "max_regression_pct": 30 }
}
```

(`guardrails.json:3-10`; applied in `main.rs:215-218` as `pct_change = (new-base)/base*100`, fail if `pct_change > threshold`.)

**Whisker mapping:** Replace single `GUARD_AXIS_SLACK` with `baseline.groups[tag].axis_slack` (absolute) or `max_drop_pct` (relative) per corpus band, assigned via a `groups.toml`-style manifest beside the GT corpus. Stratify slack before copying html-to-markdown's numeric values verbatim (WG21 papers are closer to `clean_large` / `adversarial` than `clean_small`).

**Second-place portable detail (quality contract):** Oracle bless loop — `htmbench oracle` strict compare + `oracle --bless` refresh (`oracle.rs:90-113`, `main.rs:265-267`) — is the actual backstop that makes their metric-free CI trustworthy; whisker should add committed md5/sha256 per `(pid, profile)` when full snapshots are too heavy.

---

*Generated by red-team pass against html-to-markdown-py QA harness, June 2026.*
