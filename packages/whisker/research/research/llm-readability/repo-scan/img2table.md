# Repo scan: img2table

**Does it verify LLM-readability?** **no**

img2table is an OpenCV-based **image/PDF table identification and extraction** library (HTML, XLSX, extracted cell grids via OCR). Its test suite validates **multi-stage structural fidelity** (geometry, counts, export bytes) and **reference-free table-structure scoring** for borderless detection. It does not produce LLM-oriented markdown, run comprehension tests, fact assertions, LLM judges, or downstream consumability benchmarks. Repo-wide search finds no `LLM`, `comprehension`, `readability`, or `benchmark` usage in source/docs.

---

## Findings

1. **[HIGH] Per-stage committed structural goldens (exact equality)** — pipeline stages diff against JSON/CSV/HTML/XLSX fixtures: contours → lines → cells → clustered cells → tables → HTML/XLSX. Evidence: `tests/tables/bordered/lines/test_lines.py:15-32`, `tests/tables/bordered/cells/test_cells.py:9-21`, `tests/tables/bordered/tables/creation/test_creation.py:56-69`, `tests/tables/bordered/tables/creation/test_cell_clustering.py:10-23`, `tests/tables/extraction/test_extraction.py:47-79`. Impact: localizes regressions by stage; for whisker, only **summary sidecar fields** (table count, dimensions) are in-scope, not full geometry goldens.

2. **[HIGH] Borderless hard-reject ladder + weighted composite `table_score` with `is_structured()` cutoff 0.425** — six prerequisite floors (min rows/cols, presence ratios, spacing, connectivity, alignment) then weighted sum; sections below 0.425 rejected. Evidence: `src/img2table/tables/borderless/tables/filter/model.py:118-162`, `src/img2table/tables/borderless/tables/filter/metrics/__init__.py:37-50`. Impact: top portable pattern for whisker reference-free gating before GT bench.

3. **[HIGH] Pinned composite formula regression test** — `TableMetrics.score()` asserted at `pytest.approx(0.5675)` for fixed inputs. Evidence: `tests/tables/borderless/tables/filter/test_metrics.py:192-204`. Impact: meta-test pattern whisker should copy when adding weighted `overall` composite.

4. **[HIGH] Cardinality and shape assertions independent of fuzzy scores** — `len(result) == 2`, `nb_rows`/`nb_columns`, contour counts, content grid dimensions. Evidence: `tests/tables/extractor/test_extractor.py:16-20`, `tests/document/image/test_image.py:64-82`, `tests/document/rotation/test_rotation.py:19`. Impact: guard baseline fields camelot/img2table both prove necessary; whisker gap confirmed.

5. **[MED] Normalization before diff (order invariance)** — sorted coordinates for lines/cells; set equality for unordered cell clusters. Evidence: `tests/tables/bordered/lines/test_lines.py:27-32`, `tests/tables/bordered/cells/test_cells.py:19-21`, `test_cell_clustering.py:19-23`. Impact: whisker should sort/normalize before cardinality or structural sidecar diffs.

6. **[MED] Export-format byte/content verification** — HTML string equality; XLSX worksheet values match expected workbook. Evidence: `tests/tables/extraction/test_extraction.py:47-56`, `tests/document/image/test_image.py:103-114`. Impact: export fidelity gate; for whisker, optional pipe-table substring hash rather than byte-exact markdown.

7. **[MED] Blank/zero-content input tests** — blank image returns `[]`; `compute_char_length` on blank returns `(None, None)`. Evidence: `tests/document/image/test_image.py:38-54`, `tests/tables/extractor/test_metrics.py:24-28`. Impact: whisker should hard-fail or flag empty-doc conversions instead of `teds=1.0` when both sides table-less.

8. **[MED] Mixed tolerance semantics** — exact `==` on structures, `pytest.approx` on floats, distributional rotation gate `np.mean(similarities) >= 0.85`. Evidence: `tests/document/image/test_image.py:68-71`, `tests/tables/borderless/tables/filter/test_metrics.py:189-204`, `tests/document/rotation/test_rotation.py:56-65`. Impact: optional corpus-level distributional backstop for whisker guard supplement.

9. **[LOW] OCR `min_confidence` filter (0–99)** — default 50 on `Image.extract_tables`. Evidence: `src/img2table/document/image.py:48-57`. Impact: domain-specific (OCR); not portable to markdown QA unless whisker adds OCR lane.

10. **[LOW] `nested_approx` helper in conftest, currently unused in tests** — ready for nested float structures. Evidence: `tests/conftest.py:18-29` (ApproxBaseReprMixin), redteam noted unused. Impact: optional guard schema for nested sidecar metrics.

11. **[CONFIRMED ABSENT] LLM, markdown output QA, comprehension, fact benchmarks** — README describes table extraction for documents (`README.md:1-6`, `38-40`); outputs are HTML/XLSX/cell content, not LLM-readable markdown pipelines.

---

## Portable to whisker (ranked)

1. **Hard-reject prerequisite ladder + weighted composite threshold** — prerequisite null/shape checks, then documented weighted sum with committed cutoff (img2table `0.425`; whisker to ROC-fit on labeled corpus). Source: `filter/model.py:125-162`, `filter/metrics/__init__.py:42-50`.

2. **Table/cardinality axes in guard baseline** — fail when extracted table count or max row/col drops vs baseline. Source: `tests/document/image/test_image.py:64-82`, `tests/tables/extractor/test_extractor.py:16-20`.

3. **Pin composite formula at fixed fixture** — `test_table_metrics_score` pattern prevents silent weight drift. Source: `tests/.../test_metrics.py:192-204`.

4. **Blank-document and table-loss hard-fail** — empty input → `[]` tested; whisker analog: GT has tables, candidate has none → fail, not `teds=1.0`. Source: `tests/document/image/test_image.py:38-54`.

5. **Normalization before structural diff** — sort keys / set equality before compare. Source: `tests/tables/bordered/cells/test_cells.py:19-21`.

6. **Optional export anchor** — HTML/XLSX exact match pattern maps to pipe-table content hash or subset of `table` facts. Source: `tests/tables/extraction/test_extraction.py:47-56`.

7. **Low priority:** rotation SSIM distributional gate (`test_rotation.py:56-65`); OCR min_confidence (`document/image.py:48`).

**Not portable as LLM-readability proof:** img2table validates **detected table geometry and OCR cell text**, not markdown fact recovery. Structural score `table_score` is **reference-free layout confidence**, not Lane 3 comprehension.

---

## Cross-check vs redteam report (`packages/whisker/research/redteam/img2table.md`)

| Redteam claim | Verdict | Evidence |
|---------------|---------|----------|
| Per-stage structural goldens (contours→lines→cells→tables→HTML/XLSX) | **CONFIRMED** | paths cited above |
| Count/cardinality assertions (`len`, `nb_rows`, `nb_columns`) | **CONFIRMED** | `test_extractor.py:16-20`, `test_image.py:64-82` |
| Normalization before diff (sort, set equality) | **CONFIRMED** | `test_lines.py:27-32`, `test_cell_clustering.py:19-23` |
| Hard-reject ladder + `table_score >= 0.425` | **CONFIRMED** | `filter/model.py:125-162` |
| Weighted `TableMetrics.score()` formula | **CONFIRMED** | `filter/metrics/__init__.py:42-50` |
| Pinned score `0.5675` | **CONFIRMED** | `test_metrics.py:192-204` |
| Blank input returns `[]` / `None` metrics | **CONFIRMED** | `test_image.py:38-54`, `test_metrics.py:24-28` |
| HTML/XLSX output verification | **CONFIRMED** | `test_extraction.py:47-56`, `test_image.py:103-114` |
| No ROC calibration | **CONFIRMED** | constants in source + pinned tests |
| `nested_approx` in conftest unused | **CONFIRMED** | `tests/conftest.py:18-29`; no test imports found |
| Rotation SSIM mean ≥ 0.85 | **CONFIRMED** | `test_rotation.py:56-65` |
| whisker `--update` ahead of img2table manual fixture edits | **CONFIRMED** (whisker-side strength) | img2table `Makefile:10-18` syncs deps only |

**Additions this scan surfaces (not contradictions):**

- **No markdown export path tested** — redteam mentions HTML/XLSX; this scan confirms img2table never validates markdown LLM consumability (out of scope for the library).
- **Borderless filter metrics are heavily unit-tested** beyond the single `0.5675` pin — submetric tests at `test_metrics.py:73-189` give finer regression coverage than redteam summary implies.

**No contradictions found** against redteam claims.
