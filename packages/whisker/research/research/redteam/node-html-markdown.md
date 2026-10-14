# Red-team: whisker guard/calibrate vs node-html-markdown

**Target repo:** `packages/whisker/research/repos/node-html-markdown` (crosstype/node-html-markdown v2.0.0: 5 Jest test modules, ~87 real HTML benchmark files, zero committed golden snapshots, CI = build + `jest --collect-coverage` on Node 20/22/24).

## Summary

- node-html-markdown gates quality with **inline `expect().toBe()` exact string equality** (implicit slack 0) per HTML construct; guard gates on **rounded float axes + 0.02 slack** — formatting, escaping, and whitespace regressions that fail NHM can pass guard unchanged.
- NHM splits regression coverage **by construct** (tables, codeblocks, lists, options, special-cases) and **by option permutation**; guard emits one aggregate `BenchRow` per paper with no construct-level or config-matrix decomposition.
- NHM's **87-file real HTML corpus** (`benchmark/files/`) and **turndown cross-parser harness** measure **speed only** — output is discarded (`benchmark/wrapper/node-html-markdown.js:3–5`); whisker's markitdown oracle is ahead on quality comparison, but guard still lacks NHM's construct-exact tier beneath metrics.
- **[CRITICAL][ACTIONABLE-NOW]** `baseline_from_rows` writes `axis_slack`/`floors` into the baseline JSON but `diff_rows` never reads them — committed baseline metadata is decorative (`guard.py:141–142` vs `guard.py:214–217`, `guard.py:62`).
- **Top portable detail:** NHM's zero-tolerance gate formula `expect(translate(html)).toBe(expected)` (`test/default-tags.test.ts:17–19`) plus hybrid anchor fallbacks for embedded contexts (`test/table.test.ts:141–150`).

---

## 1. REGRESSION-GATE GAPS

### [CRITICAL] Exact full-output string gate vs fuzzy metric snapshot

**NHM:** every regression test compares converter output to an expected string with **zero tolerance** — `expect(res).toBe(expected)` (`test/default-tags.test.ts:17–19`, `test/table.test.ts:18–20`, `test/options.test.ts:22–23`).

**guard:** `guard.py:172–184` diffs only `nid`/`teds`/`mhs`/`overall` with `GUARD_AXIS_SLACK = 0.02` (`constants.py:94`); markdown text never enters the gate.

**Adopt?** Partially. Metric guard is correct for WG21 PDF corpus with GT markdown. Add a **small golden-markdown tier** (exact or normalized-string diff) beneath metrics for escape/table-pipe/list-indent regressions NHM catches at byte level. Metric-only guard cannot replicate NHM's implicit `FPR = 0` on fixtures.

### [CRITICAL] Construct-level decomposition vs one row per paper

**NHM:** five test modules isolate failure domains — `test/table.test.ts` (tables/pipe escape/padding), `test/default-tags-codeblock.test.ts` (code-fence innards), `test/default-tags.test.ts` (lists/links/headings), `test/options.test.ts` (17 option knobs), `test/special-cases.test.ts` (whitespace, entities, mixed-case).

**guard:** `bench.py:149–166` → one `BenchRow` per paper; a table-only collapse on a paper with few tables may not move `teds` enough to trip slack.

**Adopt?** Yes. Report or gate **per-construct subscores** (table excerpt TEDS, list-block NID, heading MHS) in guard findings, mirroring NHM's file split. Aggregate axes alone hide localized regressions.

### [HIGH] Option/configuration permutation matrix

**NHM:** `test/options.test.ts:17–339` mutates each option (`codeFence`, `bulletMarker`, `emDelimiter`, `ignore`, `lineStartEscape`, `useLinkReferenceDefinitions`, …) and asserts a **distinct exact output** per permutation.

**guard:** single scoring config per run; no option dimension in baseline or diff.

**Adopt?** Yes if tomd exposes scored flags. NHM proves config drift is a first-class regression surface; guard should either baseline per-config rows or fail when config hash changes without baseline refresh.

### [HIGH] Whitespace / escape / line-break exact semantics

**NHM:** tests lock precise spacing policy — two-space hard breaks `  \n` (`test/default-tags.test.ts:17–19`), list indent `  ` (`test/default-tags.test.ts:127–141`), pipe escape `A\\|B` (`test/table.test.ts:42–43`), line-start escape `\\+` (`test/options.test.ts:216–217`), `\r\n`/`\t` collapse (`test/special-cases.test.ts:68–70`).

**guard:** `normalized_text` / block matching absorb formatting before scoring; a whitespace-policy regression can leave `nid`/`teds` unchanged.

**Adopt?** Yes for a golden tier or dedicated **escape/whitespace anchor checks** on known snippets. Do not rely on aggregate NID alone for delimiter/escape invariants NHM locks with exact strings.

### [HIGH] Hybrid exact + partial-anchor assertions for embedded contexts

**NHM:** most tests use full `toBe`, but table-in-list uses a **weaker anchor ladder** when full exactness is brittle: `expect(result).not.toContain('|\\')`, `expect(result).toMatch(/^\* foo/)`, `expect(result).toContain('| foo | bar |')` (`test/table.test.ts:141–150`).

**guard:** no substring/order/forbidden-token assertions; only numeric floors and drops.

**Adopt?** Yes as a complementary tier (markitdown/olmocr pattern). Partial anchors catch embedding-context bugs (table inside list) that holistic metrics miss.

### [MEDIUM] Issue-linked minimal repro fixtures

**NHM:** regression tests cite GitHub issues in comments (`test/special-cases.test.ts:55`, `:66–67`, `:73–74`, `:84–85`, `:105`) and ship `test-fix.js:3–7` as a hand-run repro harness for #34/#61.

**guard:** baseline rows are opaque floats with no provenance to failure mode.

**Adopt?** Yes. Attach `issue`/`reason` metadata to baseline entries (or sidecar facts files) so guard failures map to known regression classes, not just `"teds 0.99 -> 0.97"`.

### [MEDIUM] Real-world HTML corpus exists but is not quality-gated

**NHM:** `benchmark/files/` holds **87** hash-named production HTML pages (`benchmark/index.js:13–24`); `benchmark/wrapper/node-html-markdown.js:3–5` calls `translate(html)` and **discards output** — only wall-clock time is recorded (`benchmark/index.js:54–62`, `benchmark/execute.js:69–127`).

**guard:** scores labeled `*.gt.md` corpus only; no harness to score real HTML→MD paths.

**Adopt?** Partially. NHM itself does not gate this corpus (whisker is not behind here on plumbing). If tomd gains HTML input, adopt the **file inventory pattern** but diff output/metrics, not speed alone.

### [MEDIUM] Cross-parser harness compares speed, not output quality

**NHM:** `benchmark/execute.js:13–20` forks turndown vs node-html-markdown wrappers; README (`README.md:31–59`) publishes speed ratios only — **no output diff** between parsers.

**guard/bench:** whisker's markitdown oracle compares text agreement (advisory). NHM confirms the field pattern: cross-converter harnesses default to perf, not quality regression.

**Adopt?** Keep whisker's quality oracle; do **not** copy NHM's speed-only benchmark as a regression gate. Optionally add speed tracking outside guard.

### [MEDIUM] New test case must land with expected output; guard passes `STATUS_NEW`

**NHM:** adding coverage requires a new `test(...)` + `expect().toBe(...)` in the same PR — no silent corpus growth.

**guard:** `guard.py:165–169` — missing baseline entry → `STATUS_NEW` (passes if floors met).

**Adopt?** Yes [ACTIONABLE-NOW]. Treat unknown PIDs as **fail until baselined** (or explicit allowlist in baseline JSON). NHM's model prevents unaudited corpus expansion.

### [MEDIUM] No committed snapshot refresh ritual (NHM is weaker; guard is ahead)

**NHM:** expected strings live **inside test source**; "refresh" = edit TypeScript and merge — no `--update`, no separate golden artifact, no `__snapshots__/` directory.

**guard:** `__main__.py:361–367` `--update` rewrites baseline JSON with explicit ritual.

**Adopt?** Keep guard's ritual; add CI dry-run that fails if `--update` would change baseline (NHM lacks this entirely). Do not copy NHM's inline-string-only model for WG21 corpus baselines.

### [MEDIUM] Baseline metadata written but not honored

**NHM:** N/A (no baseline JSON).

**guard:** `baseline_from_rows` writes `"axis_slack"` and `"floors"` (`guard.py:141–142`); `diff_rows` always uses live `constants.py` `_FLOORS` (`guard.py:62`) and CLI `--slack` (`guard.py:205`, `__main__.py:334–335`), never `baseline["axis_slack"]` or `baseline["floors"]`.

**Adopt?** Yes [ACTIONABLE-NOW]. Read slack/floors from committed baseline when present; fail on schema/kind mismatch instead of silent empty baseline (`guard.py:214`).

### [LOW] Missing-item detection

**NHM:** tests are code-defined; removing a test removes coverage silently (no "missing fixture" fail).

**guard:** `guard.py:221` hard-fails baseline PIDs absent from current run — **stronger** than NHM.

**Adopt?** Keep.

### [LOW] Known-bad / expectedFailure monotonic baselines

**NHM:** every test must pass exactly today; no `expectedFailure`.

**guard:** `guard.py:84–92`, `tests/test_guard.py:84–92` — papers already weak in baseline are not re-flagged unless they worsen (tabula-java pattern).

**Adopt?** Keep — whisker ahead of NHM for long-lived weak papers.

### [LOW] Statistical vs exact tolerance

**NHM:** exact only (`toBe`); benchmark stats use mean ± sd for **timing** only (`benchmark/execute.js:82–87`), not output quality.

**guard:** deterministic floats + slack; no sampling on scores.

**Adopt?** Keep score determinism; never import NHM's timing variance model into quality gates.

---

## 2. CALIBRATION GAPS

node-html-markdown has **no ROC, no labeled good/bad classes, no threshold JSON** — quality calibration is implicit: **`fail iff output !== expected`** (100% precision, 0% tolerated deviation on inline fixtures).

### [HIGH] calibrate optimizes fuzzy FPR; NHM enforces exact-output FPR = 0

**NHM:** any character change fails the relevant `toBe` (`test/default-tags.test.ts:19`).

**calibrate:** `calibrate.py:149–180` sweeps `unigram_coverage` with default `target_fpr=0.05` (`calibrate.py:43`, `__main__.py:466–467`) — accepts ~1/20 good papers wrongly flagged at the chosen edge.

**Adopt?** Use calibrate for **unlabeled/scored corpus** edges only; keep an exact golden subset outside ROC. Add `target_fpr=0.0` mode for NHM-equivalent fixture sets.

### [MEDIUM] Discrete multi-threshold via option matrix, not continuous ROC

**NHM:** each option value defines an independent exact operating point (`test/options.test.ts:36–52` bulletMarker `*` vs `-` vs `<->`; `:290–315` inline vs reference links) — **17+ implicit thresholds** at equality.

**calibrate:** one scalar edge per `calibrate_threshold` call; no option dimension (`__main__.py:490–498`).

**Adopt?** If tomd options affect scores, calibrate or exact-gate **per option profile**, not one global edge.

### [MEDIUM] No cross-validation / holdout

**NHM:** all inline fixtures run every CI (`build.yml:42–45`); full-corpus every push — implicit in-sample gate.

**calibrate:** fits in-sample on all labels; no k-fold or holdout report before promoting to `constants.py`.

**Adopt?** Add holdout reporting for whisker labels (field blind spot; still worth doing before edge promotion).

### [MEDIUM] External coverage metric without in-repo floor

**NHM:** CI posts coverage to Coveralls (`build.yml:47–50`); **no** `coverageThreshold` in `jest.config.js:1–18` or repo config.

**calibrate/guard:** no linkage between code-coverage regression and conversion-metric regression.

**Adopt?** Low priority for guard/calibrate; note NHM also treats coverage as advisory-only, same class as whisker's `reading_order` axis.

### [LOW] Class imbalance / per-axis calibration

**NHM:** N/A (no classes).

**calibrate:** `calibrate.py:164–168` rejects empty class; no weighting; only `unigram_coverage` (`__main__.py:490–498`), not per-axis `nid`/`teds`/`mhs` ROC.

**Adopt?** Later: per-axis calibration when labeled bad/good exists per axis (NHM's construct split suggests the strata).

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Tag | Function | Scenario | Break / fool behavior |
|-----|----------|----------|------------------------|
| **[CRITICAL][ACTIONABLE-NOW]** | `diff_rows` | Baseline JSON has `"axis_slack": 0.05` or edited `"floors"` | Ignored — uses CLI `--slack` + live `constants.py` `_FLOORS` (`guard.py:214–217`, `guard.py:62`; written at `guard.py:141–142`). |
| **[CRITICAL][ACTIONABLE-NOW]** | `_evaluate_paper` | Baseline stores `round(v,4)` (`guard.py:144`); current `cur` is full-precision `BenchRow` | Asymmetric compare at slack boundary: stored `prior` vs live `cur` can flip `drop > slack` vs true arithmetic drop. |
| **[HIGH][ACTIONABLE-NOW]** | `diff_rows` | Malformed baseline (missing `"kind"`, wrong shape) | `baseline.get("rows", {}) or {}` (`guard.py:214`) → empty baseline → all papers `STATUS_NEW`/floors-only; silent weakening. NHM fails at compile/test discovery. |
| **[HIGH]** | `_evaluate_paper` | Escape regression: `\|` → `\|` vs `\\|` in table cell | NHM fails `toBe` (`test/table.test.ts:43`); `normalized_text` may score identical → guard **ok**. |
| **[HIGH]** | `_evaluate_paper` | `axes[axis]` is `NaN` (upstream bench failure) | `NaN < floor` → False; `round(prior - NaN, 4)` → NaN; `NaN > slack` → False → **status ok**, silent pass. |
| **[HIGH]** | `diff_rows` | Duplicate `pid` in `rows` | Two `GuardFinding` same pid; no dedup/error (`guard.py:216–218`). NHM test names are unique by definition. |
| **[MEDIUM][ACTIONABLE-NOW]** | `_evaluate_paper` | Paper stable vs baseline but **currently** below floor (was above in baseline, drop sub-slack) | Only caught if `prior >= floor > cur` crossed-floor path (`guard.py:185–190`); `below_floor` alone does not change status (`guard.py:196–197`). |
| **[MEDIUM]** | `calibrate_threshold` | All samples same value, mixed labels | At every threshold TPR/FPR move together; Youden fallback + arbitrary tie-break (`calibrate.py:178–180`). NHM would fail both with exact `toBe`. |
| **[MEDIUM]** | `calibrate_threshold` | `NaN`/`inf` in sample values | `value < threshold` → False for NaN; inflates TN, depresses FPR — bogus operating point. |
| **[MEDIUM]** | `_load_labeled_samples` | Duplicate `pid` in labels JSON | Last record wins silently (`__main__.py:442–452`). |
| **[LOW]** | `diff_rows` | Empty `rows`, empty baseline | `report.failed == False` (`guard.py:112–115`); library API vacuous pass. CLI guards pairs (`__main__.py:354–356`). |
| **[LOW]** | `calibrate_threshold` | `n_pos=1, n_neg=1` | Runs; TPR/FPR ∈ {0,1} only — overfit edge. NHM has dozens of inline fixtures minimum across 5 files. |
| **[LOW]** | `_evaluate_paper` | Unicode/HTML entities: `&gt;` in code (`test/special-cases.test.ts:86–102`) | If normalization folds entities symmetrically, entity decode regression invisible to guard while NHM `toBe` fails. |

---

## 4. MISSING AXIS / CHECK (NHM gates, whisker has no equivalent)

| Tag | NHM check | Evidence | whisker gap |
|-----|-----------|----------|-------------|
| **[CRITICAL]** | Full markdown exact output | `test/default-tags.test.ts:17–19`, all `toBe` tests | No output snapshot diff in guard |
| **[HIGH]** | Table pipe escape / padding | `test/table.test.ts:42–58` | No per-table escape anchor; TEDS is holistic |
| **[HIGH]** | List nesting + `  \n` hard-break layout | `test/default-tags.test.ts:115–222` | `reading_order` advisory only; not gated |
| **[HIGH]** | Option/config permutation exact outputs | `test/options.test.ts:17–339` | Single config per guard run |
| **[HIGH]** | Codeblock inner whitespace preservation | `test/default-tags-codeblock.test.ts:19–102`, `test/special-cases.test.ts:86–102` | Normalization may hide whitespace policy drift |
| **[MEDIUM]** | Mixed-case HTML tags | `test/special-cases.test.ts:106–166` | No HTML-case corpus axis (PDF-primary) |
| **[MEDIUM]** | Line-start / global escape rules | `test/options.test.ts:213–257` | No escape-specific anchors |
| **[MEDIUM]** | Link reference vs inline modes | `test/options.test.ts:290–339` | No link-style invariant |
| **[MEDIUM]** | Partial anchors in embedded table-in-list | `test/table.test.ts:117–150` | No `must_include`/`must_not_include` tier |
| **[MEDIUM]** | `test.each` parameterized format-tag matrix | `test/special-cases.test.ts:47–63` | No parameterized construct sweep in guard tests |
| **[LOW]** | Ad-hoc issue repro harness | `test-fix.js:3–15` | No minimal-repro runner tied to guard |
| **[LOW]** | Parse throughput regression | `benchmark/execute.js:69–127`, not in CI | Out of scope for quality guard |

---

## 5. TOP PORTABLE DETAIL

**Adopt:** **zero-slack exact output gate on construct fixtures**, with hybrid anchors where embeddings are brittle.

**Primary formula (NHM implicit threshold):**

```text
fail iff NodeHtmlMarkdown.translate(html) !== expected   // slack = 0, FPR = 0 on fixture
```

Evidence: `test/default-tags.test.ts:17–19` (`expect(res).toBe(\`a  \\nb\`)`), `test/table.test.ts:18–20`.

**Secondary pattern for embedded contexts** (`test/table.test.ts:141–150`):

```text
assert not output.contains('|\\')
assert output.matches(/^\* foo/)
assert output.contains('| foo | bar |')
```

**Whisker mapping [ACTIONABLE-NOW]:**

1. Add a **golden-markdown micro-corpus** (10–20 snippets: table escape, list nesting, code fence) with exact or `normalized_text` equality gate alongside `whisker guard` — slack **0** on that tier (`--strict` or separate subcommand).
2. For table-in-list / furniture embeddings, add optional per-paper **facts JSON** (`must_include` / `must_not_include` / ordered `find` chains) beneath metric guard — NHM's `table.test.ts:141–150` pattern.
3. Keep metric guard with 0.02 slack for full WG21 papers; exact tier catches what NHM catches and metrics cannot.

NHM does **not** provide a portable numeric threshold (no `thresholds.json`); its operating point is **equality**. The hybrid anchor block is the single most actionable supplement when full equality is too brittle.
