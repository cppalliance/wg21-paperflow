# Red-team: whisker guard/calibrate vs markdownify QA

**Corpus:** `python-markdownify` (matthewwithanm/python-markdownify, develop). ~320 inline `assert` golden checks across 8 test modules; zero external snapshot files, zero numeric metrics, zero calibration.

## Summary

- **markdownify gates on exact expected Markdown strings**, not scored metrics: any output change fails CI unless a human edits the inline assert (`tests/test_conversions.py:7`, `tests/test_tables.py:289`). whisker guard tolerates up to `GUARD_AXIS_SLACK` (0.02) per-axis drop (`guard.py:180-181`), so formatting-only regressions that leave nid/teds/mhs unchanged slip through.
- **markdownify normalizes before compare** via a dedicated test harness (`tests/utils.py:6-8`) and documents production-vs-test default divergence (`tests/test_args.py:30-34`); guard baseline stores metric floats only, not normalization/scoring config, so pipeline drift can pass the gate.
- **markdownify exhaustively permutes converter options** (e.g. every table fixture run twice with `table_infer_header` True/False at `tests/test_tables.py:288-321`); guard has one scalar row per pid with no config dimension (`guard.py:143-145`).
- **calibrate.py solves a problem markdownify never has** (ROC on unigram_coverage); markdownify's implicit operating point is edit distance zero. calibrate still lacks per-axis fits for nid/teds/mhs and ignores markdownify's modality-split test taxonomy.
- **Top portable detail:** pin a pre-diff normalization/config block in the baseline (markdownify's `strip_document=None` test ritual at `tests/utils.py:6-8`) so guard diffs are reproducible across harness changes.

---

## 1. REGRESSION-GATE GAPS

### 1.1 Exact golden equality vs metric slack [HIGH] — adopt partially

markdownify: every case is `assert md(html) == '<expected>'` with **zero tolerance** (`tests/test_conversions.py:7`, `tests/test_basic.py:5-6`). ~320 asserts, no committed snapshot files; refresh = edit the assert in the PR (no `--update` ritual).

whisker guard: per-paper, per-axis float diff with `drop > slack` (`guard.py:172-184`, `constants.py:94`).

**Gap:** A conversion can change visible Markdown (escaping, table pipes, list bullets, whitespace) while block-matched nid/teds/mhs move <0.02; markdownify CI would fail, guard passes.

**Adopt?** Yes for a follow-on **raw-output or anchor layer** beneath metrics; keep slack for metric stability. Exact full-doc compare is too brittle for tomd's intentional reflow, but markdownify proves metric-only gates miss string-level regressions.

### 1.2 Pre-compare normalization ritual [HIGH][ACTIONABLE-NOW] — adopt

markdownify forces test-stable boundaries:

```6:9:packages/whisker/research/repos/markdownify/tests/utils.py
def md(html, **options):
    options = {"strip_document": None, **options}

    return MarkdownConverter(**options).convert(html)
```

Production default differs (`tests/test_args.py:30`: `markdownify("<p>Hello</p>") == "Hello"` vs `strip_document=None` → `"\n\nHello\n\n"` at line 34).

whisker guard baseline records `rows` + `floors` + `axis_slack` but **no scoring/normalization fingerprint** (`guard.py:136-146`). If `normalized_text`, block-match budget, or table HTML wrapping changes, metrics shift without a guard-visible "config changed" flag.

**Adopt?** Yes: store `scoring_config` / schema hash in baseline; fail or require `--update` when it drifts.

### 1.3 Option-matrix / config dimension [HIGH] — adopt

markdownify duplicates the full table suite under `table_infer_header=True` and `False` (`tests/test_tables.py:288-321`); heading styles permuted (`tests/test_conversions.py:218-225`, `156-168`); strip/convert lists (`tests/test_args.py:9-26`).

guard: one metric vector per pid, no option key (`guard.py:143-145`). Option change that alters output but not metrics passes silently.

**Adopt?** Yes for baseline keyed by `(pid, config_id)` or a recorded global bench config.

### 1.4 Multi-accept ambiguity sets [MEDIUM][ACTIONABLE-NOW] — adopt for harness tests

markdownify allows two valid outputs when whitespace is ambiguous:

```11:11:packages/whisker/research/repos/markdownify/tests/test_conversions.py
    assert md(f'<{tag}></{tag}> bar') in ['foo  bar', 'foo bar']  # Either is OK
```

guard: strict `drop > slack` boolean (`guard.py:180-181`); no "acceptable band" or alternate baseline values.

**Adopt?** Yes for guard **meta-tests** and optionally per-paper `acceptable_ranges` in baseline; not for production CI loosening.

### 1.5 Modality-stratified regression (tag/file taxonomy) [HIGH] — adopt as reporting

markdownify splits gates by concern: `test_tables.py`, `test_lists.py`, `test_escaping.py`, `test_conversions.py` (links, headings, code, blockquote, …). A table regression does not hide inside a single scalar.

guard diffs nid/teds/mhs/overall (`constants.py:99`) but cannot say *which HTML construct* broke; markdownify failure localizes to the tag under test.

**Adopt?** Yes as structured failure tags or a future anchor/facts layer; guard already per-axis diffs (good) but lacks construct-level localization.

### 1.6 Missing-item detection [PRESENT in guard] / silent corpus shrink [MEDIUM][ACTIONABLE-NOW]

markdownify: deleting a test function **shrinks coverage with no CI failure** (no inventory check). guard: `missing` list hard-fails when baseline pid absent from current run (`guard.py:221`, `114-115`).

**Gap in whisker:** `_load_corpus_pairs` skips unconverted candidates with a warning only (`__main__.py:256-258`); if gt exists but candidate md missing, pid lands in `missing` (good). Empty `rows` with nonempty baseline → all missing, fail (good). Empty `rows` + no baseline → vacuous pass (`guard.py:216-222`).

**Adopt?** Fail on empty scored corpus when `--baseline` exists; markdownify lesson = never allow zero-assert runs.

### 1.7 Added-item detection [MEDIUM] — adopt stricter policy

markdownify: new HTML behavior requires a **new explicit test** (human adds `def test_*`).

guard: new pid → `STATUS_NEW`, **passes** (`guard.py:165-169`, `169`). Corpus can grow without `--update`; baseline stale until someone refreshes.

**Adopt?** Optional `--strict` fail on `STATUS_NEW`; or require baseline refresh when new pids appear.

### 1.8 Known-bad / expectedFailure [LOW] — guard leads

markdownify: **no** `xfail`, `skip`, or expectedFailure anywhere in tests. Every case must pass exactly today.

guard: monotonic model for papers already below floor in baseline (`guard.py:160-163`, `test_guard.py:84-92` doc intent).

**Adopt?** guard's model is strictly more practical for a weak corpus; markdownify offers no portable expectedFailure pattern.

### 1.9 Refresh ritual [PARTIAL] — guard leads

markdownify: no `--bless`/`--update`; golden refresh = PR edit of inline strings.

guard: `--update` rewrite (`__main__.py:361-367`).

**Adopt?** guard already better; markdownify exposes risk of **unreviewed assert edits** mixed with code changes (no separate ritual artifact).

### 1.10 Baseline metadata not enforced [HIGH][ACTIONABLE-NOW] — adopt

guard writes `kind`, `schema_version`, `axis_slack`, `floors` (`guard.py:139-142`) but `diff_rows` reads only `rows` (`guard.py:213-214`); CLI never validates `kind` (`__main__.py:372-376`). Stored `axis_slack` / `floors` ignored in favor of live constants + CLI `--slack`.

**Adopt?** Validate kind/schema; use baseline `floors`/`axis_slack` unless CLI override.

### 1.11 Statistical vs exact [CRITICAL concept gap] — by design

markdownify: **exact** (deterministic string equality).

guard: **tolerance-based** numeric regression.

**Adopt?** Keep numeric guard for tomd; add markdownify-style exact checks only for a small golden micro-corpus (tables, escaping, lists).

### 1.12 Improvement / baseline staleness [MEDIUM] — adopt as warning

markdownify: improved output **requires assert update** or CI fails on next run (baseline is the assert itself).

guard: improvements pass silently (`guard.py:192-197`); baseline can sit above live metrics indefinitely.

**Adopt?** Report `improved` status or nag when live >> baseline + slack.

---

## 2. CALIBRATION GAPS

markdownify performs **no threshold calibration** (no ROC, no floors, no class labels). Its "operating point" is implicit: **predicted markdown must equal expected string**. calibrate.py is therefore compared to what markdownify's discipline *implies* calibrate should also cover.

### 2.1 Single metric vs modality-split thresholds [HIGH][ACTIONABLE-NOW] — adopt

markdownify effectively has **per-modality gates** via separate test modules (tables `test_tables.py`, lists `test_lists.py`, escaping `test_escaping.py`).

calibrate fits only `unigram_coverage` fail/review edges (`__main__.py:488-499`); `NID_FLOOR`/`TEDS_FLOOR`/`MHS_FLOOR` remain hand-set (`constants.py:56-58`).

**Adopt?** Extend calibrate to accept labeled bench rows and fit nid/teds/mhs floors separately.

### 2.2 Implicit zero-FPR operating point [MEDIUM] — acknowledge

markdownify FPR = 0 on fixtures by construction (any mismatch fails). calibrate targets `DEFAULT_TARGET_FPR = 0.05` (`calibrate.py:43`, `149-154`).

**Adopt?** Document that 0.05 is looser than golden-file repos; offer `target_fpr=0.0` mode (already supported in tests at `test_calibrate.py:31`).

### 2.3 No cross-validation / holdout [MEDIUM] — adopt later

markdownify avoids overfitting via **many independent exact cases** (~320 asserts), not statistical CV.

calibrate: single-sample ROC sweep (`calibrate.py:171-172`), no k-fold.

**Adopt?** k-fold or holdout when label count > ~30; markdownify shows fixture count matters more than fit sophistication.

### 2.4 Review edge merges fail+review labels [MEDIUM][ACTIONABLE-NOW] — reconsider

```491:491:packages/whisker/src/whisker/__main__.py
    review_samples = [(cov, label in (_LABEL_FAIL, _LABEL_REVIEW)) for _, label, cov in samples]
```

markdownify separates concerns by test (escaping failures ≠ table failures ≠ list failures).

**Adopt?** Fit review edge on review-only positives; use fail edge for hard gate; do not merge labels.

### 2.5 Option-conditioned calibration [MEDIUM] — adopt if config matrix added

markdownify table scores depend on `table_infer_header` (`tests/test_tables.py:306-321`, `markdownify/__init__.py:768-771`).

calibrate: one global edge per name, no stratification by paper type (PDF vs HTML) or bench config.

**Adopt?** Stratify labels by modality when sample size allows.

### 2.6 Class imbalance / tiny corpus [LOW] — guardrails exist

markdownify: no classes. calibrate: raises on single-class (`calibrate.py:166-169`).

**Adopt?** Already handled; add minimum-n warning (markdownify relies on large assert count, not statistics).

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Severity | Function | Scenario | markdownify lesson |
|----------|----------|----------|-------------------|
| [CRITICAL][ACTIONABLE-NOW] | `_evaluate_paper` (`guard.py:162-180`) | `axes[axis]` is NaN: `NaN < floor` is False; `round(prior - NaN, 4)` not `> slack`; paper passes while metrics corrupt | markdownify would fail on any output corruption producing NaN text paths (`test_escaping.py:16-26` entity edge cases) |
| [CRITICAL][ACTIONABLE-NOW] | `_confusion` (`calibrate.py:110-111`) | `value` is NaN: `NaN < threshold` is False → bad sample never flagged, TPR understated | exact tests fail loudly on any parse/normalize bug |
| [HIGH][ACTIONABLE-NOW] | `diff_rows` (`guard.py:213-214`) | Baseline JSON with wrong `kind` (e.g. bench leaderboard) still diffs `rows` key if present | markdownify tests are typed by module; no schema confusion |
| [HIGH][ACTIONABLE-NOW] | `diff_rows` / `_FLOORS` (`guard.py:62`, `141-142`) | Baseline stores `floors` at write time; diff always uses live `C.NID_FLOOR` etc. | markdownify expects are frozen in the assert string at commit time |
| [HIGH][ACTIONABLE-NOW] | `baseline_from_rows` (`guard.py:143-145`) | Duplicate pids in `rows`: dict last-wins silently | markdownify duplicate test names would error at collection |
| [HIGH][ACTIONABLE-NOW] | `_load_corpus_pairs` (`__main__.py:251-260`) | All candidates missing → `pairs` empty → error before guard; but partial skip + `--update` writes shrunk baseline without comparing to old missing set | markdownify full suite always runs all tests |
| [MEDIUM][ACTIONABLE-NOW] | `diff_rows` (`guard.py:216-222`) | `rows=[]`, `baseline=None` → `failed=False` (vacuous clean) | zero tests passing tox would fail (`tox.ini:12`) |
| [MEDIUM][ACTIONABLE-NOW] | `calibrate_threshold` (`calibrate.py:123-133`) | All identical values, mixed labels: every threshold same confusion; tie-break picks higher threshold (`calibrate.py:177`) — arbitrary edge | markdownify would pin one expected string per case |
| [MEDIUM][ACTIONABLE-NOW] | `_evaluate_paper` (`guard.py:160-163`) | Paper below floor in baseline, improves but still below floor: `status=ok`, only `below_floor` info — correct monotonic, but no "still broken" fail | markdownify fails until assert matches good output |
| [MEDIUM] | `_evaluate_paper` (`guard.py:185-190`) | `prior >= floor > cur` crossed_floor path requires `prior >= floor`; paper already below floor crossing lower still only regresses if drop > slack | N/A |
| [MEDIUM] | `float` slack boundary (`guard.py:180`) | `drop == slack` passes (tested `test_guard.py:55-60`); markdownify has no boundary slack | OK if intentional |
| [LOW] | `GuardFinding.to_dict` (`guard.py:98`) | `round(v, 4)` on NaN/Inf propagates non-finite JSON | — |
| [LOW] | `_calibrate_main` (`__main__.py:448`) | `float(r["unigram_coverage"])` on non-numeric raises; no range clamp [0,1] | — |

**Unicode / huge corpus:** markdownify tests `\u00a0` (`test_conversions.py:62`, `test_p` line 284), entities (`test_escaping.py:20-26`). guard does not validate pid or metric finiteness after `run_bench`. Huge corpora: guard O(n) per paper only; calibrate O(n × unique thresholds) (`calibrate.py:171-172`).

---

## 4. MISSING AXIS / CHECK

Axes markdownify gates on that whisker guard/calibrate have **no equivalent**:

| Check | markdownify evidence | whisker gap |
|-------|---------------------|-------------|
| **Full output string equality** | all conversion tests | metrics only |
| **Markdown escaping correctness** | `tests/test_escaping.py:6-77` (`*`, `_`, `#`, `\|`, list markers) | no escape-layer assert |
| **Table header inference / colspan / thead-tbody** | `tests/test_tables.py:288-321`, `markdownify/__init__.py:747-789` | teds scalar only; order-matched table pairs |
| **Nested list bullet alternation** | `tests/test_lists.py:76-81`, `84-85` | no list-structure axis |
| **Script/style stripping** | `tests/test_conversions.py:316-321` | no "must not contain" gate |
| **HTML comment removal** | `tests/test_advanced.py:20-27` | no comment-leak check |
| **Whitespace / chomp invariants** | `tests/test_basic.py:12-14`, `markdownify/__init__.py:82-92` | normalized_text partial |
| **Custom tag / extensibility hooks** | `tests/test_custom_converter.py:26-38` | no plugin-drift detection |
| **Static typing of public API** | `.github/workflows/python-app.yml:50-51` mypy | guard/calibrate untyped contract tests thin |
| **Lint on gate code** | `tox.ini:13` flake8 on every CI run | whisker guard not coupled to lint job |

[CRITICAL]: escaping + full-string gate. [HIGH]: table/list structure. [MEDIUM]: script/style/comment leaks. [LOW]: mypy/flake8 bundling.

---

## 5. TOP PORTABLE DETAIL

**Pin pre-diff normalization config in the committed baseline** — mirror markdownify's test harness forcing stable document boundaries before equality compare:

```6:8:packages/whisker/research/repos/markdownify/tests/utils.py
def md(html, **options):
    options = {"strip_document": None, **options}
```

**Portable adoption for whisker guard today:**

1. Add baseline field `bench_config`: `{ "whisker_schema_version", "block_matrix_cell_budget", "guarded_axes", "normalizer": "clean_string+textblock2unicode", "strip_document": "n/a" }` (exact keys TBD).
2. On `diff_rows`, if `baseline["bench_config"] != current_bench_config()`, fail with `[config_drift]` unless `--update`.
3. Store `axis_slack` and `floors` from baseline file, not only constants (`guard.py:141-142` written but unused on read).

This is the single highest-leverage markdownify lesson: **regression is only meaningful when the comparison harness is frozen and explicit** — they achieve it via `utils.md()` defaults; whisker must achieve it via baseline metadata because metric scores are harness-dependent.

**Secondary (honorable mention):** duplicate critical fixtures under option permutations like `table_infer_header` (`tests/test_tables.py:306-321`) → baseline rows keyed by `(pid, option_hash)` for any bench knob that moves metrics.
