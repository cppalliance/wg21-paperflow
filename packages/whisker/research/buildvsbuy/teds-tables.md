VERDICT: KEEP TEDS verbatim — owned deps, leaderboard parity; add GriTS via grits-metric

# Build vs Buy: Table Structural Metrics (TEDS + Complements)

Research date: 2026-06-25. Scope: whisker bench/guard table axis only. No whisker source changes in this pass.

Hard constraints: deterministic, no LLM scoring, permissive license only (MIT/BSD/Apache/BSL/PSF/ISC), Python >=3.12, lib funcs return data.

---

## 1. Current state (file:symbol)

| Symbol | Location | Role |
|--------|----------|------|
| `teds()` | `packages/whisker/src/whisker/metrics.py:608-619` | Public API: normalize two HTML table strings, run PubTabNet TEDS, return [0,1] |
| `_TEDS` | `metrics.py:513-584` | Core evaluator: lxml DOM → `_TableTree` → APTED edit distance, xpath-descendant denominator |
| `_TedsConfig` | `metrics.py:491-510` | APTED rename cost: tag/colspan/rowspan mismatch = 1.0; td text = normalized Levenshtein |
| `_TableTree` | `metrics.py:470-488` | APTED tree node (tag, colspan, rowspan, char-token content) |
| `_normalize_table_html()` | `metrics.py:587-605` | OmniDocBench preprocess: wrap `<html><body>`, `th`→`td`, strip thead/tbody/tfoot |
| `_extract_md_tables()` | `packages/whisker/src/whisker/bench.py:72-106` | Markdown pipe tables → minimal HTML for TEDS |
| `_rows_to_html()` | `bench.py:109-121` | OmniDocBench-style `<table border="1">` wrapper |
| `_table_score()` / `table_score()` | `bench.py:124-146` | Mean TEDS over **order-matched** table pairs; `1.0` if neither side has tables |
| `TEDS_FLOOR` | `packages/whisker/src/whisker/constants.py:56-58` | Absolute floor (0.80) on score path and guard |
| Invariant tests | `packages/whisker/tests/test_invariants.py:74-91` | Identity, bounds, no-table→0, cell change lowers score |

Provenance comment (`metrics.py:18-22`, `460-467`): verbatim port of PubTabNet/OmniDocBench `table_metric.py` (Apache-2.0, IBM). Only renames, dropped batch CLI, zero-denominator guard. Algorithm unchanged for leaderboard comparability.

Owned dependencies (already in `pyproject.toml`): `apted>=1.0.3`, `levenshtein>=0.25.1`, `lxml>=5`.

**Not present:** GriTS, cell-level F1, row/col precision-recall, Hungarian multi-table matching, table-detection recall/precision.

---

## 2. Candidate table-metric libraries / implementations

| Candidate | License | Maintenance (2026-06) | Determinism | Adds vs in-repo TEDS | Verdict |
|-----------|---------|----------------------|-------------|----------------------|---------|
| **Keep in-repo TEDS** (`metrics.py`) | BSL-1.0 (whisker) / upstream Apache-2.0 | Owned; invariant tests | Yes (APTED + Levenshtein + lxml, no RNG) | Baseline; OmniDocBench/opendataloader/marker leaderboard axis | **KEEP** |
| [`table-recognition-metric`](https://pypi.org/project/table-recognition-metric/) v0.0.6 | Apache-2.0 | SWHL/RapidAI; ~680 DL/mo; 4.6 KB wheel; same deps as whisker | Yes (same apted+lxml+levenshtein stack) | Nothing algorithmically; thin `TEDS` class wrapper | **BUY: reject** (parity risk, no win) |
| [`docling-metrics-teds`](https://pypi.org/project/docling-metrics-teds/) | MIT (per prior PyPI listing) | IBM Docling team; C++ accel variant | Yes | Docling HTML/bracket adapters; may differ on normalize edge cases | **BUY: reject** (extra dep, normalization drift) |
| [`table-metrics`](https://pypi.org/project/table-metrics/) v1.0 | MIT | gu1show; ~50 DL/mo; bundles TEDS+GriTS | Yes | Combined TEDS+GriTS; requires **Python >=3.13**; uses `rapidfuzz` not Levenshtein | **BUY: reject** (py3.13 floor, duplicate TEDS impl) |
| [`grits-metric`](https://pypi.org/project/grits-metric/) v0.6.0 | MIT | Kensho (GriTS authors); v0.6.0 uploaded 2026-04-15 | Yes (numpy/scipy/pylcs; no LLM) | **GriTS-Top** (topology F1), **GriTS-Con** (cell content F1), **GriTS-Loc** (bbox IoU), Hungarian multi-table TE, per-cell P/R/F1 | **BUY: adopt as complement** |
| PubTabNet `src/metric.py` (upstream) | Apache-2.0 | Reference only; not on PyPI | Yes | Same as current port | Already **built** |
| microsoft/table-transformer `src/eval.py` | MIT | Microsoft; GriTS reference impl | Yes | Same GriTS as `grits-metric` (extracted to PyPI) | **BUILD: skip** (use PyPI) |

**PyPI TEDS landscape:** No maintained package offers a materially different or better TEDS than the PubTabNet reference. `table-recognition-metric` is a ~150-line re-export of the same apted+lxml+levenshtein pattern whisker already owns. Switching would add a transitive dep without removing code complexity and would **break score parity** unless proven by a golden-vector suite against OmniDocBench fixtures.

---

## 3. Per-repo evidence (how the field evaluates tables)

Local clones under `packages/whisker/research/repos/` were **git metadata only** at research time (no working-tree files; ripgrep returned 0 hits). Evidence below is from the June 2026 red-team deep-reads (`research/redteam/*.md`), which cite paths from populated clones. **table-transformer / PubTabNet were not cloned.**

| Repo | Table evaluation | Formula / library | Citation (red-team source) |
|------|------------------|-------------------|----------------------------|
| **opendataloader-pdf** | **TEDS** (+ structure-only `teds_s`), corpus mean floor 0.47, `table_detection_f1`; null axis when GT has no tables | OmniDocBench-style evaluator | `evaluator_table.py:228-246`, `thresholds.json:3`, `run.py:73-86` — `redteam/opendataloader-pdf.md` |
| **marker** | **TEDS** mean ≥ 0.7 on table benchmark path; per-block table scores in heuristic benchmark | In-repo table scorer + TEDS | `verify_scores.py:16-22`, `table/scoring.py:92-108` — `redteam/marker.md` |
| **unstructured** | **9-metric table-structure bundle** (not TEDS); exact TSV diff | Custom table-structure strategy | `evaluate.py:227-238` — `redteam/unstructured.md` §4 |
| **MinerU** | Per-block **fuzz.ratio > 90**, table substring hit-rate (0.9 txt/ocr, 0.7 vlm), `validate_html`; cites external OmniDocBench leaderboard | rapidfuzz + inline anchors | `test_e2e.py:171-203` — `redteam/MinerU.md` |
| **nougat** | Tables stratum: char-NED + **set-F1** (order-invariant); no TEDS | NLTK f_measure on word sets | `metrics.py:104-117`, `39-43` — `redteam/nougat.md` §4 |
| **docling** | **Grid verify**: row/col count, header flags, per-cell text (`verify_table_v2`); no TEDS in guard path | Exact structural asserts + fuzzy NED | `verify_utils.py:134-172` — `redteam/docling.md` §4 |
| **img2table** | Intrinsic **weighted table_score** (≥0.425 cutoff); stage goldens (counts, geometry) | Custom filter metrics | `filter/model.py:118-162`, `filter/metrics/__init__.py:37-50` — `redteam/img2table.md` |
| **camelot** | **DataFrame equality** + parsing_report (accuracy, whitespace, confidence) | pandas asserts | `tests/test_stream.py`, `core.py:688-705` — `redteam/camelot.md` |
| **surya** | **No in-repo table metric**; external olmOCR-bench (Tables stratum) | External benchmark only | `README.md:404-408` — `redteam/surya.md` §1.1 |
| **PDF-Extract-Kit** | **No markdown TEDS**; layout YOLO classes include `table`; demo drops table blocks | None on MD path | `pdf2markdown.py:320-321`, `yolo.py:18-28` — `redteam/PDF-Extract-Kit.md` |
| **tabula-java** | Table **detection recall** (`numCorrectlyDetectedTables`); exact JSON goldens | Geometry + XML expected counts | `TestTableDetection.java:169-314` — `redteam/tabula-java.md` |
| **PyMuPDF** | Pickle cell snapshots + markdown table tests; no TEDS | Exact asserts | `test_tables.py:15-37` — `redteam/PyMuPDF.md` |
| **PubTabNet** (not cloned) | **TEDS** reference implementation | apted + lxml + levenshtein | `ibm-aur-nlp/PubTabNet/src/metric.py` (upstream) |
| **table-transformer** (not cloned) | **GriTS** Top/Con/Loc in eval pipeline | `src/eval.py` | [microsoft/table-transformer](https://github.com/microsoft/table-transformer) MIT |

**Field consensus:** TEDS is the de facto leaderboard axis for HTML-table structure (opendataloader, marker, OmniDocBench ecosystem). GriTS is the PubTables/table-transformer axis (cell-grid F1). Most converters (surya, PDF-Extract-Kit, camelot, img2table) use **non-TEDS** gates: exact goldens, counts, or intrinsic geometry.

Whisker gap-matrix row #16: verbatim TEDS/MHS/NID is a **LEADS** position; keep and protect with invariant tests (`notes/gap-matrix.md`).

---

## 4. Verdicts

### 4a. TEDS: **KEEP-AS-IS** (do not replace with PyPI)

**Why:**

1. **Score parity is contractual.** Guard baselines, `TEDS_FLOOR`, and cross-tool comparisons (opendataloader thresholds, marker 0.7 floor) assume OmniDocBench TEDS semantics, including `_normalize_table_html` (`th`→`td`, thead unwrap, xpath-descendant denominator). PyPI wrappers (`table-recognition-metric`) do not document identical normalization; any drift invalidates committed baselines without a full corpus re-bless.

2. **Minimalism ladder: deps already paid.** TEDS sits on `apted`, `levenshtein`, `lxml` — all already whisker dependencies. A PyPI TEDS package adds a wrapper layer (~5 KB) and a version pin for zero algorithmic benefit.

3. **No maintenance burden.** The port is ~160 lines, frozen to a published metric definition. Upstream PubTabNet is reference-only (not actively versioned on PyPI). Risk of upstream breaking changes is lower than risk of silent PyPI wrapper drift.

4. **Determinism proven.** `test_invariants.py` covers identity, bounds, and monotonicity under cell edits. Replacing with BUY requires a golden-vector parity suite against OmniDocBench fixtures before any switch — none of the PyPI packages ship such vectors.

5. **Gap-matrix alignment.** "Real metric math in-repo" is intentional differentiation (`notes/gap-matrix.md` #16).

**Do not BUY** `table-recognition-metric`, `docling-metrics-teds`, or `table-metrics` for the primary TEDS axis.

### 4b. GriTS / cell-F1: **BUY `grits-metric`** as complementary axis (not TEDS replacement)

**Why BUY not BUILD:**

- Official extraction by GriTS authors (Kensho); MIT license; v0.6.0 (2026-04-15).
- Adds **orthogonal signal**: cell-level pseudo-F1 with precision/recall (`grits_top`, `grits_con`), header/topology vs content split, Hungarian matching for multi-table pages — catches merge/split and localized cell errors that tree-edit TEDS can smooth over.
- Overlaps existing deps: `numpy`, `scipy` already in whisker; only new runtime dep is `pylcs` (small, deterministic).
- BUILD from `microsoft/table-transformer/src/eval.py` would duplicate maintained PyPI code (~20 KB wheel vs porting + tests).

**Why complementary, not replacement:**

- Published WG21/OmniDocBench/opendataloader/marker baselines use **TEDS**, not GriTS. Replacing TEDS would break external comparability.
- Red-team evidence: opendataloader and marker gate TEDS; docling/img2table use grid/count checks; nougat uses set-F1 — no repo in the survey uses GriTS on markdown bench, but PubTables/GriTS literature is the standard for **cell-level** structure QA.

**Suggested integration shape (future pass, not this doc):**

- Add `grits_top` and/or `grits_con` to `BenchRow` alongside `teds` (separate guard axis, separate floor).
- Use `grits.html_to_grids()` on the same HTML fragments `_extract_md_tables()` already produces.
- Decide table pairing: keep order-match for TEDS (OmniDocBench convention); use `hungarian_grits_*` when GT/pred table counts differ (GriTS TE mode).
- Do **not** fold into `overall` until calibrated; treat like `reading_order` (stored, gated independently).

**Defer:** `grits_loc` (needs bboxes; markdown path has none). Cell-F1 without GriTS (raw row/col TP/FP/FN) would be BUILD with unclear advantage over GriTS-Con.

---

## 5. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **TEDS PyPI switch breaks baselines** | CRITICAL | KEEP verbatim; if ever BUY, require bit-identical golden vectors on WG21 corpus first |
| **Dual-axis disagreement** (TEDS pass, GriTS fail) | HIGH | Report both axes in guard findings; calibrate separate floors; document which axis is "leaderboard" |
| **Table pairing mismatch** (order-match TEDS vs Hungarian GriTS) | HIGH | Document pairing policy per axis; use Hungarian only on GriTS axis |
| **`teds=1.0` when no GT tables** inflates overall | HIGH (known) | Null-axis eligibility (`notes/redteam-synthesis.md` Tier 3); exclude from mean when GT has no tables |
| **`grits-metric` adds `pylcs` dep** | LOW | Acceptable; deterministic; one small dep vs porting GriTS |
| **`grits-metric` API churn** (v0.6 macro vs micro aggregate) | MEDIUM | Pin version; use `compute_mean_grits_per_sample()` for TSR parity with older papers if needed |
| **HTML normalization differs** (whisker `_normalize_table_html` vs `grits.html_to_grids`) | MEDIUM | Run both on identical post-processed HTML; add parity tests |
| **Guard baseline refresh** when adding GriTS | MEDIUM | New axis requires `--update` on full corpus; semver bump whisker |
| **Local repos empty** — could not re-grep live sources | LOW | Re-clone before next pass; red-team citations remain valid as of June 2026 |

---

## References

- Whisker TEDS port: `packages/whisker/src/whisker/metrics.py:460-619`
- Bench integration: `packages/whisker/src/whisker/bench.py:72-146`
- Prior synthesis: `packages/whisker/notes/gap-matrix.md` (#16), `notes/redteam-synthesis.md`
- PyPI: [table-recognition-metric](https://pypi.org/project/table-recognition-metric/0.0.6/), [grits-metric](https://pypi.org/project/grits-metric/0.6.0/)
- Upstream: [PubTabNet TEDS](https://github.com/ibm-aur-nlp/PubTabNet/tree/master/src), [table-transformer GriTS](https://github.com/microsoft/table-transformer) (MIT)
