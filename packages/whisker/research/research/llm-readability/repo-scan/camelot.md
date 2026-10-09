# Repo scan: camelot-py

**Does it verify LLM-readability?** **no**

Camelot is a PDF **table** extractor (DataFrame / CSV / HTML / Markdown export). It validates **extraction fidelity** (exact cell matrices, intrinsic parse-quality scores, optional ICDAR/FinTabNet structural benchmarks), not whether converted markdown is **comprehensible or fact-recoverable by an LLM** (olmOCR-bench / whisker Lane 3 sense). No LLM judge, no fact JSONL, no downstream QA on prose output. Markdown export exists but is not comprehension-tested.

---

## Findings

1. **[HIGH] Self-reported per-table intrinsic quality: `accuracy`, `whitespace`, composite `confidence`** — `accuracy` is computed from parser structural alignment errors (`compute_parse_errors` → `compute_accuracy`); `whitespace` is % empty stripped cells; `confidence = max(0, (accuracy/100) * (1 - whitespace/100))` with documented `>= 0.8` operating point. Evidence: `camelot/parsers/base.py:328-338`, `camelot/utils.py:1583-1638`, `camelot/core.py:682-732`. Impact: reference-free sidecar pattern portable to whisker per-table/per-document confidence; **not** LLM-readability proof.

2. **[HIGH] Exact per-fixture cell-matrix regression (primary CI gate)** — expected grids in `tests/data.py`; tests assert `pandas.testing.assert_frame_equal` on extracted DataFrames. Evidence: `tests/test_stream.py:12-17`, `tests/test_lattice.py:11-18`, `tests/data.py:3-80` (representative fixture start). Impact: strongest portable pattern for whisker **`table` fact authoring** (human-verified cell + neighbor assertions), analogous to olmOCR table class at extraction layer.

3. **[HIGH] Pinned `parsing_report` metric snapshot alongside cell goldens** — `test_parsing_report` pins `accuracy`, `whitespace`, `order`, `page`, derived `confidence` for `foo.pdf`. Evidence: `tests/test_common.py:30-45`, `tests/test_common.py:383-407` (edge-case confidence unit test). Impact: model for whisker guard baseline pinning intrinsic axes, not just NID/TEDS/MHS.

4. **[MED] Post-extraction dual-threshold filter API** — `TableList.filter(min_accuracy, max_whitespace, min_rows, min_columns)` with inclusive boundary semantics tested. Evidence: `camelot/core.py:1230-1275`, `tests/test_filter.py:29-58`. Impact: two-axis prerequisite gate before GT bench; whisker should couple floors (redteam gap).

5. **[MED] Lattice-only precision gate on near-empty ruled grids** — `_GRID_WHITESPACE_REJECT = 90.0` with ICDAR measurement rationale; network parser explicitly does not inherit. Evidence: `camelot/parsers/lattice.py:26-32`, `299-308`, `tests/test_lattice.py:109-128`. Impact: hard-reject garbage tables before scoring; markdown analog = high empty-cell ratio in pipe tables.

6. **[MED] Table/cardinality count assertions** — CLI and tests assert extraction counts (`Found 1 tables`, `len(tables) == 2`). Evidence: `tests/test_cli.py:41`, `69`, `tests/test_lattice.py:33-41`, `tests/test_auto_flavor.py:19-21`. Impact: cheap whisker baseline field invisible to fuzzy metric slack today.

7. **[MED] Visual debug regression (pytest-mpl)** — nine plot tests vs committed PNGs under `tests/files/baseline_plots/`. Evidence: `tests/test_plotting.py:11-48`. Impact: orthogonal regression layer; low priority for markdown QA unless whisker gains layout-debug artifacts.

8. **[MED] Manual structural benchmarks (not CI pytest)** — `bench/benchmark_icdar.py` and `bench/benchmark_fintabnet.py` score detection-F1, difflib TEDS proxy, row/col count accuracy against ICDAR/FinTabNet GT. Evidence: `bench/_metrics.py:1-67`, `bench/benchmark_icdar.py:1-18`. Impact: resembles whisker Lane 2 (structural fidelity), explicitly **not** comprehension; not wired into `.github/workflows/tests.yml`.

9. **[LOW] Content-preservation regression without exact placement** — `test_overlapping_text_preserves_adjacent_cell` uses regex on row text, not full grid equality. Evidence: `tests/test_common.py:448-485`. Impact: substring/regex anchor pattern for whisker `present` facts when exact layout varies.

10. **[CONFIRMED ABSENT] LLM, comprehension, fact assertions, downstream consumability QA** — repo targets table extraction for humans/pandas (`README.md:12-21`); no olmOCR-style fact JSONL, no LLM-as-judge, no reading-order comprehension beyond table ordering metadata (`parsing_report["order"]`).

---

## Portable to whisker (ranked)

1. **Per-table (or per-paper) composite confidence sidecar** — emit `(accuracy_analog/100) * (1 - empty_cell_pct/100)` on converted markdown tables; document operating point; pin in guard baseline. Source: `core.py:682-705`, `tests/test_common.py:35-40`.

2. **Dual-axis hard reject before GT bench** — accuracy/whitespace analogs (e.g. `% empty pipe cells`, heading-level misassignment) with lattice-style upstream reject at extreme whitespace. Source: `lattice.py:26-32`, `core.py:1230-1275`.

3. **Cardinality axes in guard baseline** — table count, row/col extrema; fail when count drops. Source: `tests/test_cli.py:41`, `tests/test_lattice.py:39`.

4. **Pin intrinsic metric snapshots in baseline JSON** — alongside fuzzy NID/TEDS/MHS, store rounded confidence components per PID. Source: `tests/test_common.py:30-45`.

5. **Cell-matrix → Lane 3 `table` facts** — camelot's `tests/data.py` + `assert_frame_equal` is the authoring workflow for human-verified neighbor facts in `corpus/*.facts.jsonl`. Source: `tests/test_stream.py:12-17`.

6. **Inclusive boundary meta-tests for filter thresholds** — document and test edge semantics when whisker adds composite floors. Source: `tests/test_filter.py:50-58`.

7. **Low priority:** mpl plot baselines (`test_plotting.py`); manual ICDAR bench scripts for parser tuning only (`bench/benchmark_icdar.py`).

**Not portable as LLM-readability proof:** camelot scores **PDF table extraction**, not tomd markdown consumability. Confidence is **self-reported structural alignment**, not fact recovery. Whisker must still run Lane 3 on **tomd output**.

---

## Cross-check vs redteam report (`packages/whisker/research/redteam/camelot.md`)

| Redteam claim | Verdict | Evidence |
|---------------|---------|----------|
| Exact DataFrame golden + `assert_frame_equal` | **CONFIRMED** | `tests/test_stream.py:12-17`, `tests/data.py` |
| Pinned `parsing_report` (`accuracy`, `whitespace`, `confidence`) | **CONFIRMED** | `tests/test_common.py:30-45`, `core.py:726-732` |
| Composite `confidence = (accuracy/100)*(1-whitespace/100)`, `>= 0.8` guidance | **CONFIRMED** | `core.py:682-689`, `705` |
| `compute_accuracy` / `compute_whitespace` implementation | **CONFIRMED** | `utils.py:1583-1638`, assigned `base.py:328-338` |
| Visual plot regression (pytest-mpl) | **CONFIRMED** | `tests/test_plotting.py:11-48` |
| Table count assertions | **CONFIRMED** | `tests/test_cli.py:41`, `tests/test_lattice.py:33-41` |
| Lattice `_GRID_WHITESPACE_REJECT = 90.0` with ICDAR note | **CONFIRMED** | `lattice.py:26-32`, `308`, `tests/test_lattice.py:109-119` |
| Network parser does not inherit whitespace reject | **CONFIRMED** | `tests/test_lattice.py:122-128` |
| Inclusive filter boundary semantics | **CONFIRMED** | `core.py:1272-1273`, `tests/test_filter.py:50-58` |
| No ROC calibration | **CONFIRMED** | thresholds are constants + pinned test literals |
| whisker guard lacks intrinsic confidence axis | **CONFIRMED** (whisker-side gap, not camelot contradiction) | N/A in camelot |

**Additions this scan surfaces (not contradictions):**

- **`bench/` structural benchmarks exist** (ICDAR/FinTabNet, TEDS proxy, F1) but are **manual scripts, not CI** — redteam focused on pytest gates; camelot still has GT structural eval outside pytest (`bench/_metrics.py`, `bench/benchmark_icdar.py`).
- **README `parsing_report` example omits `confidence` key** (`README.md:44-49`) while code/tests include it since #659 — documentation lag, not test gap.

**No contradictions found** against redteam claims.
