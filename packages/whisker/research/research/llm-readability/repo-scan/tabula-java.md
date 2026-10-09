# tabula-java — LLM-readability repo scan

**Source:** `packages/whisker/research/repos/tabula-java` (tabulapdf/tabula-java, shallow clone read 2026-07-06). Duplicate checkout `tabula-java-tmp` points at the same upstream URL; not scanned separately.

**Does it verify LLM-readability?** **no**

tabula-java is a PDF table extractor (CSV/JSON/TSV writers). It has no markdown output path, no comprehension corpus, no LLM-as-judge, no downstream-consumability benchmark, and no fact assertions about whether an LLM can recover document meaning. Its QA is **structural extraction fidelity** (geometry + cell text), which maps to whisker Lane 2 / anchors, not Lane 3.

---

## Findings

1. **[HIGH] Byte-exact output goldens (fact-assertion pattern for cell content).** Tests load committed CSV/JSON fixtures and compare full writer output with `assertEquals`. Evidence: `TestWriters.java:39-46` (CSV), `:63-68` (JSON), `:94-94` (CSV infinity case); `TestBasicExtractor.java:317-325`, `:342-349` (CSV from fixture PDFs). `UtilsForTesting.loadCsv` normalizes line endings before compare (`UtilsForTesting.java:85`: `(?<!\r)\n` → `\r`). Impact: this is the closest tabula pattern to olmOCR-style deterministic fact checks: **exact expected cell strings**, not fuzzy metrics. Portable as whisker output goldens or anchor strings.

2. **[HIGH] Per-cell programmatic fact assertions (not just file diff).** `TestBasicExtractor.testNaturalOrderOfRectangles` asserts 40 individual cell strings in reading order (`TestBasicExtractor.java:225-282`: e.g. `"Project"`, `"NSF"`, `"Pennsylvania State Universit"`). Same pattern in `TestSpreadsheetExtractor.testRTL` for Arabic cells (`TestSpreadsheetExtractor.java:458-466`). Impact: direct analogue to whisker `table` facts (locate cell, assert neighbor content) and `present` anchors; still tests extraction correctness, not LLM comprehension of serialized output.

3. **[HIGH] ICDAR corpus with per-PDF committed JSON regression baselines.** 67 PDFs (EU+US) each have a sidecar JSON (`us-001.json:1`: `numExpectedTables`, `numCorrectlyDetectedTables`, `numErroneouslyDetectedTables`, `expectedFailure`). Loaded at test start (`TestTableDetection.java:58-70`, `:87-89`). First run writes baseline inside the test (`:267-272`); subsequent runs compare (`:274-282`). Impact: monotonic regression gate, not comprehension; portable to whisker `guard` baseline semantics.

4. **[HIGH] `expectedFailure` monotonic triple (16/67 cases).** For known-bad PDFs, CI requires: recall counter must not drop (`numCorrectlyDetectedTables >= baseline`, `:277`), false-positive counter must not rise (`numErroneouslyDetectedTables <= baseline`, `:278`), and **improvement to pass fails until JSON refresh** (`assertTrue(..., failed)` on `:279`). Verified count: 16 JSON files with `"expectedFailure": true`. Impact: regression discipline for weak papers; no LLM-readability claim.

5. **[MED] Geometric detection QA (layout, not text comprehension).** ICDAR black-box rules: detected region must contain GT bbox without intersecting other GT regions (`TestTableDetection.java:290-318`, `:297-308`). Errors are boolean pass/fail per PDF (`:249`, `:281`). Impact: whisker has no layout stage; not portable to markdown QA except as inspiration for upper-bound spurious-region counters.

6. **[MED] Command-line integration goldens.** `TestCommandLineApp` compares CLI CSV/JSON output to expected strings (`TestCommandLineApp.java:37`, `:91`, `:216`). End-to-end extraction path gated same as unit tests.

7. **[LOW] No LLM/downstream/readability vocabulary anywhere.** README and test suite grep find no comprehension, LLM, QA benchmark, or markdown-consumability hooks. Output is CSV/JSON for spreadsheets, not LLM-oriented linearizations.

---

## Portable to whisker (ranked)

| Rank | Pattern | tabula evidence | whisker landing |
|------|---------|-----------------|-----------------|
| 1 | **`expectedFailure` monotonic triple** | `TestTableDetection.java:267-279` | Add `expected_failure` per PID in guard baseline; fail on axis drop, upper-bound rise, and silent improvement until `--update` |
| 2 | **Exact output golden / cell fact asserts** | `TestWriters.java:45-46`, `TestBasicExtractor.java:225-282` | Second gate tier: normalized markdown hash or committed anchors; extend `table` facts / `anchors.json` with per-cell strings |
| 3 | **Dual-direction counters (recall + false-positive cap)** | `TestTableDetection.java:277-278`, `:328-331` | Guard upper-bound axis (e.g. `extra_regions`, drift) with `<= baseline` for known-weak papers |
| 4 | **Normalization-before-diff ritual** | `UtilsForTesting.java:85` | Record `schema_version` + normalization revision in guard baseline; optional CRLF/whitespace layer before markdown goldens |
| 5 | **Per-item JSON baselines (not corpus mean)** | `TestTableDetection.java:104-122`, `:260-264` (stats logged, not gated) | guard already exceeds this; deprecate mean-only `bench --baseline` |

Not portable to LLM-readability: ICDAR bbox geometry, CSV writer fidelity as end goal (whisker target is markdown for LLM pipelines).

---

## Cross-check vs redteam report

**Report:** `packages/whisker/research/redteam/tabula-java.md`

| redteam claim | Scan verdict | Evidence |
|---------------|--------------|----------|
| 67-PDF ICDAR corpus + per-PDF JSON baselines | **CONFIRMED** | `TestTableDetection.java:104-118`, `:58-70`; `us-001.json` |
| 16 `expectedFailure:true` monotonic cases | **CONFIRMED** | 16 JSON files; `:275-279` |
| Byte-exact CSV/JSON goldens alongside metric baselines | **CONFIRMED** | `TestWriters.java:39-46`, `TestBasicExtractor.java:325` |
| No ROC calibration; fixed geometry thresholds | **CONFIRMED** | `:290-318`; no calibration module in repo |
| guard lacks expectedFailure / improvement-must-refresh | **CONFIRMED (whisker gap, not tabula)** | tabula `:279` vs whisker guard behavior documented in redteam |
| Top portable: expectedFailure triple | **CONFIRMED** | `:267-279` |

No contradictions found. Redteam correctly scoped tabula as **regression-gate** research, not LLM-readability; this scan adds: tabula's cell-level `assertEquals` chain is the actionable **fact-assertion** pattern for whisker Lane 3/table facts, even though tabula never tests LLM consumption.
