# Repo scan: Unstructured (Unstructured-IO/unstructured)

**Does it verify LLM-readability?** **partial** (README and metrics target LLM/RAG ingestion quality via deterministic structural proxies; no fact assertions, no LLM-as-judge, no comprehension corpus)

Scanned: local shallow clone at `packages/whisker/research/repos/unstructured` (read-only, 2026-07-06).

## Findings

### Product positioning is LLM/RAG; verification is structural fidelity only

`README.md:40` states use cases "revolve around streamlining and optimizing the data processing workflow for LLMs." Platform marketing mentions chunking and enrichment (`README.md:44`). **No code path runs an LLM to verify that chunks or elements remain semantically consumable.** All gated metrics are deterministic string/structure comparisons against committed gold fixtures.

### Three eval strategies: text, element-type, table-structure (deterministic)

`unstructured/metrics/evaluate.py` defines:

| Strategy | Class | What it measures | Key evidence |
|----------|-------|------------------|--------------|
| Text extraction | `TextExtractionMetricsCalculator` | `cct-accuracy` (Levenshtein score, weights `(2,1,1)`) + `cct-%missing` (BOW recall) | `:409-435`, `text_extraction.py:57-117`, `:160-203` |
| Element-type | `ElementTypeMetricsCalculator` | Frequency match of `(type, category_depth)` tuples | `:449-507`, `element_type.py:18-93` |
| Table structure | `TableStructureMetricsCalculator` | Nine metrics: detection P/R/F1, cell index/content accuracy, composite | `:207-238`, `:248-280`, `table/table_eval.py:1-80` |

These test **extraction fidelity and layout preservation**, not comprehension. Closest whisker analog: Lane 2 (`nid`, `teds`, `unigram_coverage`), not Lane 3 (`facts.py`).

### Dual text axis (`cct-accuracy` + `cct-%missing`) is a weak content-recall proxy

`calculate_percent_missing_text` compares bag-of-word frequencies; does not penalize duplication (`text_extraction.py:172-173`, `:185-203`). A run can score high accuracy while missing rare tokens, or pass `%missing` while scrambling order. **Better than single edit distance for "words survived"** but not equivalent to olmOCR present/absent/order/table/math facts or LLM QA.

Wild size-ratio guard assigns sentinel `accuracy = 0.01` when output/source byte lengths differ by >2× (`evaluate.py:415-421`), preventing misleading Levenshtein on pathological inputs.

### Table eval goes beyond mean TEDS: detection + cell geometry

`table_eval.py:1-15` documents a pipeline: table identification via concatenated-text matching, then per-table element alignment, row/column index tuples, flattened token order along rows/columns. Metrics exported include `table_detection_recall/precision/f1`, `element_col_level_index_acc`, `element_row_level_content_acc`, `composite_structure_acc` (`evaluate.py:227-238`, `table_eval.py:43-60`). This is **structure matching on HTML table JSON**, not LLM table QA (cf. TabVerse/olmOCR table neighbor checks in 05-web Q2/Q1).

### Chunking tests verify semantic-unit integrity at partition boundary, not LLM consumption

`test_unstructured/chunking/test_base.py` extensively tests that tables stay atomic (`_TableChunker`, `_HtmlTableSplitter`), row-boundary splits, and `reconstruct_table_from_chunks` preserves nested HTML (`:2796-2817`: nested table rows stay nested after reconstruction). These assert **ingestion chunk boundaries do not tear tables**, aligning with MDKeyChunker-style atomic-unit guidance (05-web Q5), but **no test feeds chunks to an LLM or asserts fact recoverability.**

### CI gates committed metric TSV snapshots with zero slack

`check-diff-evaluation-metrics.sh:14-73`: default `OVERWRITE_FIXTURES=false`; any byte change in metrics tree fails via `diff -ru`. Refresh requires explicit overwrite or `scripts/ingest-test-fixtures-update.sh` on x86_64 Docker (`:46-55`, `ingest-test-fixtures-update.sh:49-58`). `ci.yml:287` runs ingest with `OVERWRITE_FIXTURES` unset (false). Normalization before diff: quote standardization + `prepare_str` in metrics (`text_extraction.py:109-110`); permission cleanup (`check-diff-evaluation-metrics.sh:58`).

**CI eval loop runs two of three strategies:** `test-ingest-src.sh:81-89` invokes `evaluation-metrics.sh` for `text-extraction` and `element-type` only. `table-structure` eval is implemented (`evaluation-metrics.sh:19-20`) but not in the default CI ingest loop; table coverage is indirect via `local-single-file-with-pdf-infer-table-structure.sh` ingest fixture test (`test-ingest-src.sh:31`).

### Pinned eval corpus via manifest

`test_unstructured_ingest/metrics/metrics-json-manifest.txt:1-18` lists 18 JSON fixture stems (PDF, HTML, DOCX, CSV, etc.). `evaluation-metrics.sh:26-31` pulls gold from S3 using eval name. Prevents silent corpus drift.

### No LLM-as-judge, fact assertions, or comprehension benchmarks

Repo search finds no comprehension tests, fact JSONL fixtures, LLM-as-judge harness, or downstream QA benchmark integration. `test_unstructured/metrics/test_evaluate.py` unit-tests calculator wiring with mocks (`:61-106`); `test_text_extraction.py` tests edit-distance and BOW math on synthetic strings (`:15-60`). **No test asks "can a model answer X from this chunk."**

### Normalization and output golden layers (structural, not semantic)

Ingest also diffs structured JSON output (`check-diff-expected-output.sh`, cited in redteam) and markdown/HTML derivatives. These gate **format stability**, not LLM comprehension.

## Portable to whisker (ranked)

1. **Dual-axis guard rows: accuracy + percent_missing** — add `percent_missing` (or `1 - unigram_coverage`) alongside `nid/teds/mhs` in guard baseline (`evaluate.py:434-435`; maps to whisker `unigram_coverage` on score path). Highest-value gap vs current four-float guard.
2. **Exact snapshot diff + explicit refresh flag** — optional `--exact` release gate mirroring `OVERWRITE_FIXTURES` contract (`check-diff-evaluation-metrics.sh:46-73`); CI must never auto-`--update`.
3. **Per-doc TSV + aggregate sidecar** — human-reviewable baseline tree plus corpus mean/stdev/count (`evaluate.py:53-60`, `:361-362`).
4. **Table metric bundle beyond mean TEDS** — consider guard fields for detection F1 and cell index accuracy when bench grows (`evaluate.py:227-238`, `table_eval.py:43-60`).
5. **Normalization-before-diff** — round both baseline and current operands; quote/whitespace prep like `text_extraction.py:109-110`.
6. **Wild size-ratio sentinel** — flag pathological length mismatch before scoring (`evaluate.py:417-421`; whisker block-match fallback is weaker).
7. **Fail on new baseline PIDs by default** — mirror TSV tree diff catching added rows (`check-diff-evaluation-metrics.sh:56-73` vs whisker `STATUS_NEW` pass).
8. **Pinned corpus manifest** — committed PID/fixture list like `metrics-json-manifest.txt:1-18`.
9. **Chunk atomicity tests as inspiration** — whisker table facts should assume pipe-table atomicity; redteam already covers parser scope.

**Not portable as comprehension:** element-type taxonomy has no whisker markdown equivalent today; do not import as Lane 3 substitute.

## Cross-check vs redteam report

**Confirms** (`packages/whisker/research/redteam/unstructured.md`):

- Zero-tolerance `diff -ru` on committed metrics TSV trees; `OVERWRITE_FIXTURES` refresh ritual never in CI (`check-diff-evaluation-metrics.sh:46-73`, `ci.yml:287`).
- Three eval strategies with dual text axes (`evaluate.py:434-435`, `text_extraction.py:160-203`).
- Normalization before diff (quotes, whitespace); table structure nine-metric bundle (`evaluate.py:227-238`, `table_eval.py`).
- No ROC/threshold calibration in-repo; top portable detail (per-doc TSV + dual-axis rows) stands.
- `%missing` not in whisker guard today — CRITICAL gap claim upheld.

**Adds / nuance (this scan's LLM-readability lens):**

- Redteam compared guard/calibrate mechanics; **this scan:** README LLM positioning (`README.md:40`) is aspirational — verification stops at structural metrics. No contradiction, but the gap between marketing and proof is explicit.
- Redteam lists three strategies as CI gates; **correction:** default CI ingest loop runs **text-extraction + element-type only** (`test-ingest-src.sh:81-89`). Table-structure eval code exists but is not in that loop; table work is covered partly by separate ingest fixture scripts.
- Chunking tests (`test_base.py:2796-2817`) verify table HTML reconstruction across chunk seams — structural consumability prerequisite Unstructured tests but redteam did not cite; still not LLM comprehension.
- Redteam's `metrics-json-manifest.txt:1-18` path verified; manifest pins 18 docs not entire ingest corpus (narrower than implied "all ingest output").

**No material contradiction** on regression-gate design; redteam claims on dual-axis value and exact-diff ritual are verified.
