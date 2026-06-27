# Red-team: whisker guard/calibrate vs pandoc QA

**Source repo:** `packages/whisker/research/repos/pandoc` (~1,760 command tests in `test/command/*.md`, ~255+ `.native` AST goldens, reader/writer unit suites)  
**Target:** `guard.py`, `calibrate.py` (+ CLI wiring in `__main__.py`)

## Summary

- Pandoc gates **every fixture** on **byte-exact golden output** after deterministic normalization (`expected == actual`, zero slack); whisker guard diffs **rounded floats** with `GUARD_AXIS_SLACK=0.02`, so output regressions invisible to nid/teds/mhs slip through.
- Pandoc **fail-closes on new tests**: each new command block or `.native` pair must ship committed expected output or CI fails; guard assigns `STATUS_NEW` and **passes** new papers above floors without a baseline entry.
- Pandoc runs **three regression layers** (command integration, golden file pairs, QuickCheck/property invariants); guard has one path (`run_bench` → `diff_rows`) with no round-trip or gate-engine meta-tests.
- Pandoc **normalizes before diff** (`\r` stripping, XML timestamp whitelists, format-specific normalizers); guard ignores committed `axis_slack`/`floors` in baseline JSON and has no gate-boundary normalization contract.
- Pandoc performs **no ROC/threshold calibration** (exact match is the operating point); `calibrate.py` fits only `unigram_coverage` edges and does not calibrate guard floors or per-axis metric baselines.

---

## 1. REGRESSION-GATE GAPS

### 1.1 Full-output golden vs metric-only snapshots [CRITICAL]

**Pandoc:** Each reader/writer fixture compares **entire converter output** to a committed golden via `goldenTest`; pass condition is exact string equality after normalization (`test/Tests/Old.hs:380-408`, `compareValues` at `402-403`). Command tests embed expected stdout in the `.md` fixture itself (`test/Tests/Command.hs:101-129`).

**guard.py:** Stores and diffs only `{nid, teds, mhs, overall, reading_order}` per pid (`guard.py:65-71`, `136-147`). Markdown text is never snapshotted.

**Adopt?** **Partially.** Full WG21-paper goldens are impractical, but pandoc proves the primary gate must be **committed expected output**, not derived scores alone. Add a small golden-markdown micro-corpus (pandoc's command-test pattern) as a hard layer beneath metric slack.

### 1.2 Zero tolerance vs per-axis slack [HIGH]

**Pandoc:** No numeric tolerance. Regression is any diff in line-oriented output (`Old.hs:401-408`, `Helpers.hs:136-147`).

**guard.py:** Regression only when `round(prior - cur, 4) > slack` (`guard.py:180-184`); default `GUARD_AXIS_SLACK = 0.02` (`constants.py:94`).

**Adopt?** **No wholesale replacement** for the large labeled corpus, but adopt pandoc's zero-tolerance semantics for golden subset. Pandoc treats slack as absent by design; whisker's slack is an explicit relaxation that must not be mistaken for pandoc-grade safety.

### 1.3 Fail-closed on added items vs `STATUS_NEW` passes [HIGH] [ACTIONABLE-NOW]

**Pandoc:** Command tests auto-discover every `test/command/*.md` file (`Command.hs:83-87`); each code block must include committed expected output after `^D` or the golden compare fails. New `.native` pairs in `Old.hs` require a committed golden file (`Old.hs:370-394`).

**guard.py:** Papers absent from baseline receive `STATUS_NEW` and **do not fail** when above floors (`guard.py:165-169`, `52-53`).

**Adopt?** **Yes.** New corpus pids must require explicit baseline acknowledgment (fail CI or pass only via `--update`), matching pandoc's "no fixture without a golden" rule.

### 1.4 Bidirectional corpus membership (added archive members) [MEDIUM] [ACTIONABLE-NOW]

**Pandoc:** OOXML golden tests fail if generated archives contain files **not** in the committed golden, not only if golden files are missing (`test/Tests/Writers/OOXML.hs:97-119`, `compareFileList`).

**guard.py:** Hard-fails when baseline pids vanish (`guard.py:220-221`, `113-115`) but **does not fail** when new pids appear (`STATUS_NEW` passes).

**Adopt?** **Yes** for symmetric corpus contract: missing **and** unacknowledged additions should fail, mirroring OOXML's bidirectional file-list gate.

### 1.5 Pre-compare normalization layer [HIGH] [ACTIONABLE-NOW]

**Pandoc:** Multiple deterministic normalizers before equality: strip `\r` on Windows (`Old.hs:389-391`, `Helpers.hs:84-85`); FB2 XML tag splitting (`Old.hs:351-361`); OOXML ignores `dcterms:created`/`modified` timestamps (`OOXML.hs:26-33`); dedicated docx inline-normalization fixtures (`Docx.hs:163-169`, `docx/normalize.docx`).

**guard.py:** Metrics normalize internally (`bench`/`metrics`), but the guard boundary accepts raw `BenchRow` floats with no documented normalization ritual. Committed baseline `floors` and `axis_slack` are written (`guard.py:141-142`) but **never read** in `diff_rows` (uses `C.*` constants and CLI `--slack` only, `guard.py:205-217`).

**Adopt?** **Yes.** Read `baseline["floors"]` and `baseline["axis_slack"]` when present; document LF/rounding policy at the gate boundary the way pandoc documents `\r` filtering before diff.

### 1.6 Any output change fails (including improvements) [MEDIUM]

**Pandoc:** Output improvements fail CI until goldens are refreshed with `--accept` (`Makefile:50-55`, `CONTRIBUTING.md:272-279`).

**guard.py:** Only metric **drops** fail; improvements always `STATUS_OK` (`guard.py:172-184`).

**Adopt?** **Partially.** Metric baselines can allow silent improvement; golden subset should adopt pandoc's "any change requires `--accept`" rule to prevent unreviewed drift.

### 1.7 Multi-layer / multi-surface regression detection [HIGH]

**Pandoc:** Parallel gates: CLI command tests (`Command.hs`), committed file goldens (`Old.hs`), reader/writer unit tests with AST equality (`Helpers.hs:53-66`), QuickCheck round-trip (`Writers/Native.hs:10-16`), table normalization properties (`Writers/AnnotatedTable.hs:137-151`), warning-log fixtures (`Docx.hs:48-57`), binary/media integrity (`Docx.hs:62-96`, `OOXML.hs:171-200`).

**guard.py / `__main__.py`:** Single path: `_load_corpus_pairs` → `run_bench` → `diff_rows` (`__main__.py:353-383`).

**Adopt?** **Yes** for at least one property/meta-test layer on guard logic (pandoc tests the test engine, not just documents). Whisker has unit tests for guard (`tests/test_guard.py`) but no QuickCheck-style invariant on metric math comparable to `p_write_rt`.

### 1.8 known-bad / expectedFailure [LOW]

**Pandoc:** No `expectedFailure` mechanism. Known-bad behavior is encoded **in the committed golden** (the expected output documents current behavior) or left as commented-out properties (`Readers/Markdown.hs:151-162`).

**guard.py:** Monotonic model: papers below floor in baseline are not re-flagged unless they worsen (`guard.py:22-24`; `tests/test_guard.py:84-91`).

**Adopt?** Keep guard's explicit monotonic metric model for labeled scores; for goldens, use pandoc's "golden IS the contract" model instead of `expectedFailure`.

### 1.9 Refresh ritual (CI never auto-accepts) [LOW] (whisker leads on ergonomics)

**Pandoc:** `make test TESTARGS='--accept'` rewrites goldens locally (`Makefile:50-55`); CONTRIBUTING requires human review before commit (`CONTRIBUTING.md:272-279`). CI runs tests without `--accept`.

**guard.py:** `whisker guard --update` rewrites baseline (`__main__.py:361-367`).

**Adopt?** Keep `--update`; add pandoc-style **mandatory PR review of baseline diff** (whisker already separates update from diff; align docs with pandoc's explicit "check changed golden files for accuracy").

### 1.10 Statistical vs exact [HIGH]

**Pandoc:** Deterministic exact compare; no ROC, no floors, no corpus means.

**guard.py:** Fuzzy metrics + slack + absolute floors (`constants.py:56-58`, `94-99`).

**Adopt?** Hybrid model: exact goldens (pandoc) on micro-corpus + fuzzy per-paper metrics (whisker) on labeled corpus. Pandoc shows the field-proven default is exact, not statistical.

### 1.11 Per-item granularity [MEDIUM] (partial overlap)

**Pandoc:** Each command code block is an independent gate (`Command.hs:137-141`); each `.native` pair is independent (`Old.hs:370-394`).

**guard.py:** Per-paper, per-axis diff (`guard.py:172-184`) — **matches pandoc's per-item spirit** for metrics.

**Adopt?** Already present for metrics; extend per-item to golden output, not only floats.

---

## 2. CALIBRATION GAPS

Pandoc performs **no threshold calibration**. Its operating point is implicit: **100% exact match** after normalization. ROC/FPR are undefined because correctness is structural equality.

### 2.1 calibrate.py solves a problem pandoc avoids [MEDIUM]

**Pandoc:** No labeled good/bad classes, no ROC sweep, no FPR ceiling — the gate is `expected == actual` (`Old.hs:402-403`).

**calibrate.py:** ROC sweep with max TPR subject to `fpr <= target_fpr` (`calibrate.py:149-180`); wired only to `unigram_coverage` fail/review edges (`__main__.py:490-498`).

**Adopt?** Keep calibrate for fuzzy content gates, but recognize pandoc's lesson: **fuzziness forces calibration; exact goldens eliminate it.** Guard's `NID_FLOOR`/`TEDS_FLOOR`/`MHS_FLOOR` remain hand-set like pandoc's implicit threshold (= exact).

### 2.2 Guard metric floors not calibrated [HIGH] [ACTIONABLE-NOW]

**Pandoc:** N/A (exact match subsumes floors).

**calibrate.py:** Does not fit `NID_FLOOR`, `TEDS_FLOOR`, `MHS_FLOOR`, or per-paper baseline slack — only `unigram_coverage` (`__main__.py:488-498`, `constants.py:56-58`).

**Adopt?** **Yes** if whisker keeps metric gates: either add per-axis ROC on labeled bench scores, or add pandoc-style exact goldens so floors become backstop-only.

### 2.3 Per-axis / per-format calibration [HIGH]

**Pandoc:** Each reader/writer/format has its **own** golden set (`Old.hs:27-285`, `test-pandoc.hs:67-112`). There is no single global threshold; each fixture is its own binary classifier with threshold 0 (any diff = fail).

**calibrate.py:** Single scalar sweep per call; no nid/teds/mhs axes, no stratification by paper type or source format.

**Adopt?** **Yes** for bench guard: calibrate (or golden-snapshot) **per axis** separately, matching pandoc's refusal to collapse formats into one number.

### 2.4 Cross-validation / holdout [MEDIUM]

**Pandoc:** N/A (deterministic goldens are the validation set).

**calibrate.py:** Fits and reports on the same labeled list; no train/holdout split (`calibrate.py:149-185`).

**Adopt?** **Yes** before promoting edges to `constants.py`; pandoc avoids overfit by requiring human review of every golden change, which calibrate should mirror with holdout metrics in the emitted JSON.

### 2.5 Class imbalance and tie-heavy samples [MEDIUM] [ACTIONABLE-NOW]

**Pandoc:** N/A.

**calibrate.py:** Tie-break prefers higher threshold (`calibrate.py:177-178`); identical `(value, label)` pairs (see `test_calibrate.py:37-44`) force Youden fallback with symmetric confusion — no explicit imbalance weighting or minimum support per class beyond empty-class `ValueError` (`calibrate.py:166-169`).

**Adopt?** **Yes:** report class counts (already in `CalibrationResult`) **and** warn when `n_pos` or `n_neg` < minimum support; pandoc's equivalent is "don't add a golden until you've seen the failure mode."

### 2.6 Multi-threshold operating points [LOW]

**Pandoc:** Implicit multi-threshold via thousands of independent binary fixtures (each test is its own pass/fail boundary).

**calibrate.py:** Two edges (fail + review) from one metric (`__main__.py:490-498`); no joint optimization ensuring fail ⊂ review monotonicity when fit separately.

**Adopt?** **Yes:** enforce `fail_edge <= review_edge` after independent fits, or fit review conditional on fail (pandoc enforces consistency by having one golden answer per question).

---

## 3. CONCRETE BUGS/EDGE-CASES IN OUR CODE

| Function | Scenario | Pandoc lesson | Severity |
|----------|----------|---------------|----------|
| `diff_rows` / `_evaluate_paper` | New pid above floors, absent from baseline | Pandoc fails any fixture without committed expected output (`Command.hs:115-121`) | [HIGH] [ACTIONABLE-NOW] |
| `baseline_from_rows` | Duplicate `pid` in `rows` | Pandoc gives each test a unique name/path; duplicates would be a harness bug | [MEDIUM] [ACTIONABLE-NOW] — dict comprehension silently keeps last row (`guard.py:143-146`) |
| `diff_rows` | Baseline stores `floors`/`axis_slack` but run uses CLI defaults | Pandoc goldens embed the normalization contract in the file under test | [MEDIUM] [ACTIONABLE-NOW] — ignores `baseline["floors"]`, `baseline["axis_slack"]` (`guard.py:141-142` vs `205-217`, `62`) |
| `_evaluate_paper` | Existing paper current value below absolute floor but not worse vs baseline | Pandoc would fail exact golden regardless of history | [HIGH] — `below_floor` populated but `status == ok` (`guard.py:160-163`, `192-198`; `test_guard.py:84-91`) |
| `_evaluate_paper` | `prior == floor`, `cur == floor - ε` with ε < slack | Pandoc: any output change fails | [MEDIUM] — `crossed_floor` requires `prior >= floor > cur` (`guard.py:185-189`); at-floor prior skips crossed path |
| `_evaluate_paper` / `run_bench` | `NaN`/`inf` axis values from broken scorer | Pandoc compares strings; NaN never appears as "equal enough" | [HIGH] — comparisons silently treat NaN as non-regression (`guard.py:162`, `180-181`) |
| `calibrate_threshold` | `NaN`/`inf` in sample values | Pandoc N/A | [HIGH] — `_candidate_thresholds`/`sorted(set(values))` produce undefined ordering; confusion counts wrong |
| `calibrate_threshold` | Single positive, many negatives (extreme imbalance) | Pandoc uses many fixtures per feature area | [MEDIUM] — meets class check but chosen edge may have unstable FPR at `target_fpr=0.05` with n_neg small |
| `calibrate_threshold` | All samples identical value, mixed labels | Pandoc encodes ambiguity in golden, not ROC | [MEDIUM] — Youden fallback; any threshold flags all or none (`calibrate.py:178-180`) |
| `diff_rows` | Empty `rows`, nonempty baseline | Pandoc dropping all tests would leave empty suite (visible) | [LOW] — all pids land in `missing` → hard fail (`guard.py:220-221`) ✓ |
| `baseline_from_rows` / JSON round-trip | Float `0.899999999` scored, stored as `0.9` | Pandoc stores exact text output, not rounded floats | [MEDIUM] — `round(v, 4)` (`guard.py:144`) can hide sub-0.00005 regressions pandoc would catch in text |
| `_load_corpus_pairs` | Two `*.gt.md` differing only by case on case-insensitive FS | Pandoc paths are explicit in test tree | [LOW] — duplicate/overwritten pid possible on Windows |

---

## 4. MISSING AXIS/CHECK

Pandoc gates quality dimensions whisker guard/calibrate do not cover:

| Pandoc check | Evidence | Whisker gap | Severity |
|--------------|----------|-------------|----------|
| **Exit code contract** | Command tests assert `=> N` on failure (`Command.hs:67-69`, `7861.md:4-6`) | Guard only checks metric floats; no exit-code gate on `whisker`/`paperflow` | [HIGH] |
| **Stderr / warning log** | Expected warnings prefixed `2> ` (`Command.hs:67-68`, `svg.md:5`; `Docx.hs:48-57`) | No regression gate on tomd/whisker warning logs | [HIGH] |
| **Binary / media integrity** | Docx media bag byte compare (`Docx.hs:62-96`); OOXML binary file compare (`OOXML.hs:171-185`) | Bench scores markdown text only; extracted images not gated | [MEDIUM] |
| **AST / round-trip invariant** | `read (writeNative d) == d` (`Native.hs:10-12`) | No `convert → score → convert` idempotence check | [MEDIUM] |
| **Normalization correctness** | Property: annotated table normalizes like builder (`AnnotatedTable.hs:137-151`) | No property tests that metric normalization matches benchmark reference impl | [MEDIUM] |
| **Multi-case fixtures per document** | One `.md` file, many `% pandoc` blocks (`Command.hs:136-141`, `yaml-metadata-blocks.md`) | One row per pid; no sub-case granularity | [MEDIUM] |
| **Error-path behavior** | Nonzero exit with partial stdout golden (`7861.md:1-6`) | Guard skips errored papers in score path (`__main__.py:185-190`); bench path warns and continues (`__main__.py:256-258`) | [MEDIUM] |

---

## 5. TOP PORTABLE DETAIL

**Adopt pandoc's golden gate contract verbatim at the normalization boundary:**

```haskell
-- test/Tests/Old.hs:389-403
then return $ filter (/='\r') . normalizer $ UTF8.toStringLazy out
...
if expected == actual
   then return Nothing
```

Plus refresh config:

```
# Makefile:50-51
# make test TESTARGS='--accept'
```

**Why:** Pandoc's entire QA stack rests on (1) deterministic pre-diff normalization, (2) **exact** equality (threshold = 0), (3) human-reviewed `--accept` refresh never run in CI (`CONTRIBUTING.md:272-274`). Whisker already has `--update` and float slack; adding the pandoc **`filter \r` + exact-compare** layer on a micro-corpus closes the gap where metric slack allows formatting regressions pandoc would reject in one CI run.

**Whisker mapping:** For a committed `whisker/goldens/<pid>.md` subset, compare normalized markdown with exact equality (no slack); keep `guard.py` metric diff as the labeled-corpus layer. Read committed `axis_slack`/`floors` from baseline JSON when present so the baseline file is the contract (pandoc embeds the contract in the golden file itself).
