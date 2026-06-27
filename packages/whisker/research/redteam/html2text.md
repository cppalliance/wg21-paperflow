# Red-team: whisker guard/calibrate vs html2text QA

**Source repo:** `packages/whisker/research/repos/html2text` (74 `.html`/`.md` golden pairs, pinned clone)  
**Target:** `guard.py`, `calibrate.py` (+ CLI wiring in `__main__.py`)

## Summary

- html2text gates **74 fixtures** on **byte-exact** golden markdown (`actual.rstrip() == expected.rstrip()` after `cleanup_eol`), **zero slack**; whisker guard gates **fuzzy per-axis metrics** with `GUARD_AXIS_SLACK=0.02`, so formatting-only regressions that preserve nid/teds/mhs slip through.
- html2text is **fail-closed on corpus growth**: every new `.html` must ship a paired `.md` or `get_baseline()` raises; guard assigns `STATUS_NEW` and **passes** new papers above floors without a baseline entry — unreviewed corpus expansion is invisible.
- html2text exercises **three entry points** (library `HTML2Text`, CLI subprocess, `html2text()` function) with **filename-driven option permutations** (`generate_testdata()`); guard only runs the `bench` scoring path — no CLI/library parity check.
- html2text **normalizes before diff** (`cleanup_eol` for CRLF, `.rstrip()` only); guard compares rounded floats but has **no gate-boundary normalization** of inputs and ignores `axis_slack` stored in committed baselines.
- html2text has **no calibration** (exact match *is* the threshold); `calibrate.py` fits only `unigram_coverage` edges and does **not** calibrate guard's `NID_FLOOR`/`TEDS_FLOOR`/`MHS_FLOOR` or per-paper metric baselines.

---

## 1. REGRESSION-GATE GAPS

### 1.1 Full-output golden vs metric snapshots [CRITICAL]

**html2text:** Each fixture compares the entire converter output to a committed `.md` golden via exact string equality (`test/test_html2text.py:191`, `221-222`). Any character change fails CI.

**guard.py:** Stores and diffs only `{nid, teds, mhs, overall, reading_order}` floats per pid (`guard.py:65-71`, `136-147`). Output text is never snapshotted.

**Adopt?** **Partially.** Exact full-document goldens are impractical for WG21 papers (tomd output churn, front matter), but guard should add a **small golden-markdown micro-corpus** (html2text's 74-fixture pattern) as a hard backstop beneath metric slack. Metric-only guard cannot catch regressions visible to humans but invisible to block-matched NID/TEDS/MHS.

### 1.2 Zero tolerance vs per-axis slack [HIGH]

**html2text:** Tolerance is **exactly zero** after normalization — no `±0.02`, no floors-with-slack (`test_html2text.py:191`).

**guard.py:** Regression only when `round(prior - cur, 4) > slack` (`guard.py:180-184`); default slack `0.02` (`constants.py:94`).

**Adopt?** **No wholesale replacement**, but adopt html2text's zero-tolerance semantics for a **golden subset**; keep slack for the large labeled corpus where benign formatting drift is expected. html2text proves slack is a deliberate relaxation, not the default safety model.

### 1.3 Fail-closed on added items vs `STATUS_NEW` passes [HIGH] [ACTIONABLE-NOW]

**html2text:** Auto-discovers `*.html` via glob (`test_html2text.py:26-27`); `get_baseline()` opens the paired `.md` (`test_html2text.py:225-233`) — a new fixture without a golden **hard-fails** at test time.

**guard.py:** Papers absent from baseline get `STATUS_NEW` and **do not fail** if above floors (`guard.py:165-169`, `52-53`; verified: `diff_rows([NEW], None)` → `failed=False`).

**Adopt?** **Yes.** Require explicit baseline acknowledgment for new pids (fail or `--update`-only pass). html2text's model prevents silent corpus expansion from weakening coverage.

### 1.4 Missing-item detection (asymmetric) [MEDIUM]

**html2text:** No explicit "removed fixture" test — deleting `.html` removes the parametrized case (coverage drops but CI stays green).

**guard.py:** **Hard-fails** when a baseline pid vanishes from the current run (`guard.py:220-221`, `113-115`). This is **stricter than html2text** and should be kept.

**Adopt?** Already present; no change.

### 1.5 Pre-compare normalization [HIGH] [ACTIONABLE-NOW]

**html2text:** `cleanup_eol()` strips CRLF/CR artifacts on Windows (`test_html2text.py:14-21`); compare uses `.rstrip()` on both sides (`test_html2text.py:191`). Repo enforces LF via `.gitattributes:1` (`* text eol=lf`).

**guard.py:** Metrics internally normalize text (`normalized_text` in metrics path), but the **guard boundary** accepts raw `BenchRow` floats with no input-normalization contract and no EOL/whitespace policy at the gate.

**Adopt?** **Yes** at the gate boundary: document and enforce the same normalization ritual html2text uses before any diff (LF policy + trailing-whitespace rule), or golden diffs will disagree with metric diffs on platform-specific churn.

### 1.6 Multi-entry-point / surface parity [HIGH]

**html2text:** Three parametrized suites — `test_module` (library), `test_command` (CLI subprocess), `test_function` (`html2text()` API) — over the same goldens (`test_html2text.py:173-222`). Filename prefixes select option permutations (`test_html2text.py:32-151`); some paths skip CLI or function API when unsupported (`cmdline_args = skip`, `func_args = skip`).

**guard.py / `__main__.py`:** Single path: `_load_corpus_pairs` → `run_bench` → `diff_rows` (`__main__.py:353-383`). No check that CLI-scored markdown equals library-scored markdown.

**Adopt?** **Yes** for whisker's own CLI: run guard logic through both library and CLI on a micro-corpus. html2text caught real bugs (memleak, repeated-call drift) only because it tests stateful re-entry (`test/test_memleak.py:8-19`, `test/test_newlines_on_multiple_calls.py:6-12`).

### 1.7 Any output change fails (including improvements) [MEDIUM]

**html2text:** Improving output without updating `.md` goldens **fails** CI — forces an explicit baseline refresh in the PR.

**guard.py:** Only **drops** fail; improvements always `STATUS_OK` (`guard.py:172-184`).

**Adopt?** **Partially.** For metric baselines, improvement-without-update is acceptable; for golden subset, adopt html2text's "any change requires refresh" rule to prevent unreviewed drift accumulation.

### 1.8 known-bad / expectedFailure [LOW]

**html2text:** No `expectedFailure`; every golden must match exactly. Known-bad behavior is encoded **in the golden itself** (the expected output documents current behavior).

**guard.py:** Monotonic model — papers below floor in baseline are not re-flagged unless they get worse (`guard.py:22-24`; tests `test_known_weak_paper_not_reflagged_when_stable`).

**Adopt?** guard's model is **more explicit** for metric gates; html2text's equivalent is "update the golden when you accept new behavior." Keep guard's monotonic logic for metrics; for goldens, use html2text's exact-golden model instead.

### 1.9 Refresh ritual [LOW] (whisker leads)

**html2text:** No `--update`/`--bless`; goldens are hand-edited `.md` files committed in the PR.

**guard.py:** `--update` rewrites baseline (`__main__.py:361-367`).

**Adopt?** whisker is ahead; optionally add html2text-style **PR diff review** requirement (CI prints which pids changed) but keep `--update`.

### 1.10 Statistical vs exact [HIGH]

**html2text:** Deterministic exact compare; no ROC, no floors, no means.

**guard.py:** Fuzzy metrics + slack + corpus floors (`constants.py:56-58`).

**Adopt?** Hybrid: exact goldens (html2text) + fuzzy metrics (whisker) on disjoint corpora.

### 1.11 Committed baseline `axis_slack` ignored [MEDIUM] [ACTIONABLE-NOW]

**guard.py:** `baseline_from_rows` writes `"axis_slack"` into the baseline (`guard.py:141`), but `diff_rows` always uses the caller's `slack` parameter (`guard.py:205-206`, `217`) — never `baseline.get("axis_slack")`. A committed baseline cannot pin its own tolerance.

**Adopt?** **Yes.** Read slack from baseline when present; CLI flag overrides.

---

## 2. CALIBRATION GAPS

html2text performs **no threshold calibration** — the operating point is implicit: **100% exact match** after `cleanup_eol` + `.rstrip()`. That is its calibration philosophy.

### 2.1 calibrate.py solves a problem html2text avoids [MEDIUM]

**html2text:** No labeled good/bad, no ROC, no FPR ceiling — correctness is structural equality.

**calibrate.py:** ROC sweep with `max TPR @ FPR ≤ target` (`calibrate.py:149-180`); only wired to `unigram_coverage` fail/review edges (`__main__.py:490-498`).

**Adopt?** Keep calibrate for fuzzy gates, but recognize html2text's lesson: **metric fuzziness is what forces calibration**; guard's nid/teds/mhs floors remain hand-set (`constants.py:56-58`) like html2text's implicit "threshold = exact."

### 2.2 Guard metric floors not calibrated [HIGH] [ACTIONABLE-NOW]

**html2text:** N/A (exact match).

**calibrate.py:** Does not fit `NID_FLOOR`, `TEDS_FLOOR`, `MHS_FLOOR` used by `_FLOORS` in guard (`guard.py:62`, `constants.py:56-58`).

**Adopt?** **Yes** — extend calibrate (or a sibling fitter) to labeled bench rows per axis, or derive floors from golden-corpus exact-pass rate (= 1.0).

### 2.3 No per-fixture / per-option operating points [MEDIUM]

**html2text:** Each fixture is its own "threshold" (the golden string); filename prefixes encode option permutations (`test_html2text.py:32-151`) — effectively **per-fixture calibration** via separate goldens.

**calibrate.py:** One global threshold per edge name across all labels.

**Adopt?** **Partially** — per-paper or per-stratum edges if class imbalance differs (html2text avoids this by having 74 independent gates).

### 2.4 No cross-validation [LOW]

Neither repo cross-validates. html2text's 74 independent exact tests *are* a form of holdout (each fixture is its own test). calibrate.py fits in-sample only.

**Adopt?** **Later** for calibrate; not html2text's pattern.

### 2.5 Class imbalance / ties [MEDIUM]

**html2text:** N/A.

**calibrate.py:** Requires both classes (`calibrate.py:166-169`); identical pos/neg values yield `tpr=0, fpr=0` at that threshold without error (verified: samples `[(0.5,True),(0.5,False),(0.9,False)]`, `target_fpr=0.0` → `method=max_tpr_at_fpr`, `tpr=0.0`). Misleading "success" when no bad paper is caught.

**Adopt?** **Yes** — reject or warn when chosen `tpr==0` with `n_pos>0`, or when pos/neg value sets overlap completely.

### 2.6 Review edge bundles fail+review as positives [MEDIUM]

**calibrate.py:** `review_samples` treats both `fail` and `review` labels as positive (`__main__.py:491`). html2text has no trichotomy — only pass/fail on output.

**Adopt?** Document clearly; consider separate calibration for the review band vs fail band (html2text's binary model is simpler).

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Function | Scenario | html2text lesson | Observed behavior | Severity |
|----------|----------|------------------|-------------------|----------|
| `_evaluate_paper` | `axes[axis]` is `NaN` | `invalid_unicode.html` + `--unicode-snob` tests malformed/entity edge cases (`test_html2text.py:42-45`) | `NaN < floor` is False; `round(prior-NaN,4)` is NaN; `NaN > slack` is False → **`STATUS_OK`, report not failed** | [CRITICAL] [ACTIONABLE-NOW] |
| `calibrate_threshold` | `value=float('nan')` in samples | html2text would fail loudly on garbage output | **No error**; NaN poisons sort/compare silently | [CRITICAL] [ACTIONABLE-NOW] |
| `diff_rows` | Duplicate `pid` in `rows` | html2text parametrizes unique filenames | **Two `GuardFinding`s for same pid** (one ok, one regressed); rollup ambiguous | [HIGH] [ACTIONABLE-NOW] |
| `diff_rows` | New pid above floors, baseline exists | New `.html` must ship `.md` golden | **`STATUS_NEW` passes** (`failed=False`) — unreviewed expansion | [HIGH] [ACTIONABLE-NOW] |
| `diff_rows` | `baseline["axis_slack"]=0.5`, CLI `slack=0.02` | Committed config should be authoritative | **Stored slack ignored**; only CLI param used | [MEDIUM] [ACTIONABLE-NOW] |
| `_evaluate_paper` | Metric **improves** (e.g. teds 0.99→1.0) | Any output change fails until golden updated | **`STATUS_OK`** — silent baseline staleness | [MEDIUM] |
| `_evaluate_paper` | Known-below-floor paper degrades sub-slack | html2text: any change fails | e.g. teds 0.50→0.49, drop 0.01 ≤ slack → **`STATUS_OK`** despite worsening | [MEDIUM] |
| `calibrate_threshold` | All bad/good share identical values | html2text separates by fixture | **`tpr=0` chosen without error** when overlap makes separation impossible | [MEDIUM] [ACTIONABLE-NOW] |
| `calibrate_threshold` | `target_fpr=0.0`, one good at same value as bad | — | Picks threshold with **zero recall** silently | [MEDIUM] |
| `_load_corpus_pairs` | Some pids missing converted md | html2text runs all fixtures | **Silently skips** (`__main__.py:256-258`); guard may compare shrunk corpus without hard-fail unless baseline pid missing | [MEDIUM] |
| `diff_rows` | Empty `rows`, nonempty baseline | — | **`missing` hard-fails** (correct) | — |
| `diff_rows` | Empty `rows`, `baseline=None` | — | Empty findings, **`failed=False`** — vacuous pass | [LOW] |
| `baseline_from_rows` / `diff_rows` | `baseline["schema_version"]` mismatch | — | **Not validated** | [LOW] |
| `_candidate_thresholds` | `value == threshold` boundary | html2text: exact equality | Rule is `value < threshold` (`calibrate.py:111`) — **equality not flagged** (off-by-one at boundary) | [LOW] |

---

## 4. MISSING AXIS / CHECK

| html2text gate | whisker equivalent | Gap |
|----------------|-------------------|-----|
| **Full markdown output exact match** (primary gate) | Metric snapshots only | [CRITICAL] No output golden layer |
| **CLI vs library vs function parity** | Single bench path | [HIGH] |
| **Filename/option permutation matrix** (20+ option flags via fixture name) | Single tomd config | [HIGH] for converter QA |
| **Stateful re-entry** (memleak, repeated `handle()`) | Stateless per-paper score | [MEDIUM] (`test_memleak.py`, `test_newlines_on_multiple_calls.py`) |
| **Unicode / malformed entity handling** (`invalid_unicode.html`, `unicode_snob`) | No dedicated guard fixtures | [MEDIUM] |
| **EOL / line-ending invariance** (`cleanup_eol`, `.gitattributes eol=lf`) | No gate-boundary EOL policy | [MEDIUM] |
| **Table mode variants** (`doc_with_table` vs `doc_with_table_bypass`, `table_ignore`) | Single table scoring path in bench | [MEDIUM] |
| **Google Docs export mode** (`google_doc` fixtures) | No HTML-source-stratum baselines | [LOW] |
| **Immutability of output on repeated conversion** | Not tested in guard | [MEDIUM] |
| **Codecov / coverage gate** (`.github/workflows/main.yml:90-95`) | Not in whisker guard scope | [LOW] |

whisker **has** checks html2text lacks: per-axis numeric floors, monotonic known-bad, missing-pid hard-fail, `--update` ritual, reading_order advisory axis.

---

## 5. TOP PORTABLE DETAIL

**Adopt html2text's tolerance semantics:**

```python
# test/test_html2text.py:14-21, 191
def cleanup_eol(clean_str):
    if os.name == "nt" or sys.platform == "cygwin":
        clean_str = re.sub(r"\r+", "\r", clean_str)
        clean_str = clean_str.replace("\r\n", "\n")
    return clean_str

assert cleanup_eol(actual).rstrip() == cleanup_eol(expected).rstrip()
```

Plus `.gitattributes:1`: `* text eol=lf`.

**Why this one:** html2text's entire regression philosophy reduces to **zero tolerance after deterministic normalization** — no slack, no floors, no calibration. For whisker, port this as the **golden micro-corpus layer**: a handful of `<pid>.golden.md` files compared with exact equality after `cleanup_eol`+`.rstrip()`, while keeping metric slack on the large labeled corpus. This single pattern closes the [CRITICAL] gap where metric-preserving formatting regressions pass guard today.

**Immediate guard.py actions from same source:**
1. Fail (or require `--update`) on `STATUS_NEW` pids when baseline exists.
2. Validate axes for `NaN`/`inf` before compare.
3. Deduplicate pids in `diff_rows`.
4. Honor `baseline["axis_slack"]` when CLI `--slack` not overridden.
