# Repo scan: surya (datalab OCR/layout engine)

**Source:** `packages/whisker/research/repos/surya/` (datalab-to/surya v0.20.0, shallow clone, read-only)  
**Question:** Does surya verify that its output is LLM-readable (reading-order QA, table-structure comprehension, fact recovery)?

## Does it verify LLM-readability?

**no** (in-repo)

Surya’s **in-repo** QA is smoke and structural: pytest invariants, CLI runs without output comparison, garbled-text binary classification, and runtime degeneracy guards (repeat-loop, blank-page). README cites **external** olmOCR-bench pass rates (deterministic fact assertions — comprehension class), but that harness lives in `allenai/olmocr`, not in surya. Surya does not ship markdown comprehension tests, fact JSONL, LLM read-backs, or downstream consumability evals.

---

## Findings

1. **[HIGH] No markdown output or fact-assertion benchmark in repo.**  
   `tests/` contains six modules (`test_detection.py`, `test_layout.py`, `test_recognition.py`, `test_table_rec.py`, `test_ocr_errors.py`, `conftest.py`) — all operate on **synthetic images or inline strings**, not converted markdown corpora.  
   `Select-String` / manual review: no `fact`, `comprehension`, `olmocr/bench`, or QA harness under `surya/**/*.py`.  
   README benchmark section (`README.md:378-408`) links to [olmOCR-bench](https://huggingface.co/datasets/allenai/olmOCR-bench) and reports per-source pass rates; **evaluation code is external**.

2. **[HIGH] CI is smoke-only: CLI executes, no output scoring.**  
   `.github/workflows/scripts.yml:25-40` downloads benchmark PDFs, runs `surya_detect`, `surya_ocr`, `surya_layout`, `surya_table` on `switch_trans.pdf` — **no diff vs gold, no metric threshold**.  
   `.github/workflows/ci.yml:29-30` runs `uv run pytest` only.  
   Contrast olmOCR-bench: 7,010 deterministic unit tests (see `00-baseline.md`, `05-web.md` Q1).

3. **[MED] Reading-order field exists in schema; tests check non-negativity only, not correctness.**  
   Output schema documents `reading_order` as “0-indexed position in layout output” (`README.md:157-160`).  
   `tests/test_recognition.py:14-15` asserts `blk.reading_order >= 0` for each block — **no GT order facts**, no Kendall-τ vs reference, no multi-column scramble detection.  
   Layout tests check `box.position` is an int (`test_layout.py:13`) — structural, not semantic order QA.

4. **[MED] Table recognition tests are geometric, not cell-content QA.**  
   `tests/test_table_rec.py:4-25` draws a synthetic table image, runs `table_rec_predictor`, asserts row/col/cell **counts** (`len(cells) == len(rows) * len(cols)` or relaxed).  
   **No assertion** that “Alice”, “New York”, etc. appear in output — no table neighbor facts, no TEDS, no pipe-table consumability check.

5. **[MED] OCR quality gate is garbled-vs-good classification, not comprehension.**  
   `tests/test_ocr_errors.py:1-15` feeds Hindi-garbage vs English prose to `ocr_error_predictor`; expects labels `"bad"` / `"good"`.  
   `surya/ocr_error/__init__.py` (per redteam) uses argmax on logits — **binary OCR health**, not “can an LLM answer questions from this markdown.”

6. **[MED] Runtime degeneracy guards are reference-free safety nets, not LLM-readability tests.**  
   `_detect_repeat_loop` (`recognition/__init__.py:81-108`) detects decoder repetition loops.  
   Full-page OCR falls back on empty non-blank pages (`:296-307`) and repeat loops (`:309-315`).  
   Per-block `error` / `confidence` / `skipped` flags (`recognition/__init__.py:226-237`, `README.md:164-166`).  
   These prevent broken output from shipping silently; they do **not** verify factual recoverability.

7. **[LOW] VLM tests silently pass when backend unavailable.**  
   `conftest.py:22-25` session-scopes `pytest.skip` if VLM spawn fails.  
   `tests/test_recognition.py:3-5`, `test_layout.py:6-8`, `test_table_rec.py:16-17` **return without asserting** when `error` is set.  
   CI can go green with zero meaningful OCR assertions on ubuntu/windows (redteam §1.8 — **confirm**).

8. **[LOW] External olmOCR-bench scores are comprehension-class but not surya-owned.**  
   README table (`README.md:404-408`): ArXiv 88.3%, MultCol 82.4%, Tables 86.6% on olmOCR-bench `default` preset.  
   Those numbers come from allenai’s fact-assertion scorer (presence, absence, order, table, math — `05-web.md` Q1).  
   **Portable lesson:** adopt olmOCR-bench methodology in whisker; surya only **consumes** the leaderboard, does not implement it.

---

## Portable to whisker

Ranked for whisker guard, Lane 3, and CI design:

1. **Adopt olmOCR-bench-style deterministic fact assertions (external to surya, cited by surya README)** — present/absent/order/table/math unit tests on converted markdown; this is what surya’s published quality numbers actually measure. Whisker `facts.py` already implements this lane; expand corpus coverage to match olmOCR strata (MultCol, Tables, OldScan per `README.md:404-408`).

2. **Degeneracy gate: repeat-loop + empty-on-non-blank detection** — reference-free hard fail before metrics.  
   Source: `recognition/__init__.py:81-108`, `:296-315`.  
   Action: guard treats looping or empty conversion as axis regression (redteam surya §1.5).

3. **Persist block-level `error` / `skipped` / `confidence` rollups in baseline** — surya exposes first-class failure signals (`README.md:164-166`, `recognition/__init__.py:226-237`).  
   Action: if tomd/marker pipeline surfaces analogous flags, guard fails on rising error count even when aggregate `nid` is flat.

4. **Image-adaptive threshold scaling → per-paper guard slack** — heterogeneous docs should not share one global slack.  
   Source: `detection/heatmap.py:13-21` (`get_dynamic_thresholds`).  
   Action: `slack(pid) = f(GT length, baseline strength)` (redteam surya §1.6 — **confirm** pattern).

5. **Tiered CI: fast matrix vs GPU smoke** — `ci.yml:6-11` matrix + `scripts.yml:25-40` heavy smoke.  
   Action: whisker `--smoke` / `--max-papers N` on PR, full guard nightly (redteam §1.2).

6. **Stratified reporting by document source/modality** — README olmOCR per-column reporting (`README.md:404-408`); whisker baseline should tag strata and fail within stratum, not only corpus mean.

7. **Do not adopt:** silent pass on backend failure (`test_recognition.py:3-5`), smoke-only CLI with no output compare (`scripts.yml:29-38`), geometric-only table tests as quality gate (`test_table_rec.py:22-25`).

---

## Cross-check vs redteam report

**File:** `packages/whisker/research/redteam/surya.md`

| Redteam claim | Verdict | Evidence |
|---------------|---------|----------|
| No committed per-item regression baseline | **Confirm** | No baseline JSON in repo; `scripts.yml` ephemeral PDF |
| CI smoke-only, no output comparison | **Confirm** | `scripts.yml:29-38`; pytest structural only |
| olmOCR-bench stratified in README, not CI | **Confirm** | `README.md:378-408` external scores; no in-repo harness |
| Tiered CI matrix (fast vs GPU smoke) | **Confirm** | `ci.yml:6-11`, `scripts.yml:25-40` |
| Per-block error/skipped/confidence in schema | **Confirm** | `README.md:164-166`; `recognition/__init__.py:226-237` |
| Repeat-loop / blank-page degeneracy detection | **Confirm** | `recognition/__init__.py:81-108`, `:296-315` |
| `get_dynamic_thresholds` image-adaptive scaling | **Confirm** | `detection/heatmap.py:13-21` |
| Silent pass when VLM unavailable or `error` set | **Confirm** | `conftest.py:22-25`; `test_recognition.py:3-5` |
| No in-repo ROC calibration | **Confirm** | `settings.py` hand constants (redteam cites `:112-113`) |
| reading_order in output but whisker treats order as advisory | **Confirm for surya tests** | Surya only checks `reading_order >= 0` (`test_recognition.py:15`); no GT order QA in surya |
| **Redteam scope:** guard/calibrate vs surya QA patterns | **Extend** | Redteam did not claim surya has comprehension tests; this scan **confirms absence** and clarifies README olmOCR-bench numbers are **external comprehension eval**, not surya implementation |

**Net:** All redteam regression/calibration comparisons **confirmed**. For LLM-readability: surya **does not verify** markdown comprehension in-repo; its public quality story depends on **olmOCR-bench** (portable to whisker Lane 3, already partially implemented in `facts.py`).
