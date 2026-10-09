# 07 - table-extractors

**Verdict:** usable-with-conditions (+ our Lane 3 `table` facts with `table_heading` + all-occurrence neighbor matching beat every extractor on comprehension QA, but we lack their reference-free intrinsic table metrics, full-grid goldens, and span-aware grid models)
**Confidence:** high

## Findings

### Q1 — Table accuracy self-testing (how extractors test their own output)

- **[HIGH] Camelot: full DataFrame golden + pinned intrinsic `parsing_report`.** Every stream/lattice fixture builds expected cell matrices in `tests/data.py` and asserts `pandas.testing.assert_frame_equal` on the extracted DataFrame (`tests/test_stream.py:12-17`, `tests/test_lattice.py:11-18`). Separately, `test_parsing_report` pins `accuracy`, `whitespace`, `order`, `page`, and derived `confidence` for `foo.pdf` (`tests/test_common.py:30-45`). Impact: strongest **position-exact** regression gate; any swapped column fails the golden even when individual cell text still appears somewhere in the grid. **Stronger than our neighbor-only facts** for arbitrary column permutations unless facts assert both `left` and `right` (and `heading`) on uniquely placed cells.

- **[HIGH] pdfplumber: per-cell, per-row, and per-column slice asserts on real PDFs.** `test_rows_and_columns` pins the last table row byte-for-byte AND asserts an entire column slice (`tests/test_table.py:64-100`: `t[-1] == [...]`, `col == ["UPC code", "0085648100305", ...]`). Impact: column-order regressions are caught explicitly without a full-grid golden; our `_check_table` neighbor checks catch column swaps only when the asserted `left`/`right`/`heading` values differ across the swapped columns. If two adjacent columns hold similar text, neighbor facts can false-pass where pdfplumber's column slice or camelot's `assert_frame_equal` would fail.

- **[HIGH] tabula-java: programmatic per-cell chain + byte-exact CSV goldens.** `testNaturalOrderOfRectangles` asserts 40 individual cell strings in reading order (`TestBasicExtractor.java:225-282`, e.g. `assertEquals("Project", cells.get(0).getText())` through row nine). Full-grid tests use `assertArrayEquals(EU_002_EXPECTED, UtilsForTesting.tableToArrayOfRows(table))` (`TestBasicExtractor.java:118-122`). CSV writer output is compared with `assertEquals(expectedCsv, sb.toString()) after `UtilsForTesting.loadCsv` line-ending normalization (`TestBasicExtractor.java:317-325`, `UtilsForTesting.java:85`). Impact: direct analogue to our `table` fact schema; full 2D golden is the strictest swap detector.

- **[HIGH] img2table: per-stage structural goldens + export-format equality.** Prior scan (`research/llm-readability/repo-scan/img2table.md`): contours→lines→cells→tables→HTML/XLSX each diff against committed fixtures (`tests/tables/bordered/lines/test_lines.py:15-32`, `tests/tables/extraction/test_extraction.py:47-56`). Impact: localizes regressions by pipeline stage; only summary sidecar fields (table count, dimensions) are in-scope for whisker guard, not geometry goldens.

- **[MED] Camelot reference-free intrinsic scores alongside goldens.** `compute_accuracy` weights structural alignment errors (`camelot/utils.py:1536-1565`); `compute_whitespace` counts `%` empty stripped cells (`utils.py:1567-1590`); `Table.confidence` composes `(accuracy/100)*(1-whitespace/100)` (`camelot/core.py:674-697`, `parsing_report` at `:700-723`). Tests pin the composite (`tests/test_common.py:383-407`). Impact: catches ragged/near-empty tables before human goldens; whisker has no markdown analog on guard/bench today (00-baseline A3 `auto_baseline_checks` gap).

- **[MED] pdfplumber domain accounting invariant (reference-free).** After `extract_table`, every numeric column must satisfy `colsum == (total * 2)` on the NICS layout (`tests/test_nics_report.py:81-85`). Impact: catches wrong cell assignment when fuzzy TEDS/NID stay green; no whisker equivalent.

- **[LOW] Partial-content regression without full placement.** Camelot `test_overlapping_text_preserves_adjacent_cell` uses regex on row text, not full grid equality (`tests/test_common.py:448-485`). Impact: substring anchor pattern we already cover with `present` facts.

**Swap-detection summary:** Full-grid equality (camelot, tabula) and pdfplumber column slices beat partial neighbor facts for **global** column permutations. Our `_check_table` with `table_heading` + all-occurrence try (`facts.py:373-406`) is **better** than first-match-wins for decoy tables and **competitive** when facts assert multiple orthogonal neighbors on semantically unique cells; it is **weaker** when only one neighbor is checked or swapped columns share neighbor signatures.

### Q2 — Grid model (spans, merged cells, hierarchy)

- **[HIGH] whisker `tables.py` flattens to `list[list[str]]` and drops span metadata.** Pipe parser returns raw cell strings per row (`tables.py:44-77`); HTML parser reads `td`/`th` text but **never reads `rowspan`/`colspan` attributes** (`tables.py:92-117`). Impact: Tony Tables / SPEC_TABLE merged cells collapse incorrectly; neighbor checks operate on a wrong grid.

- **[HIGH] pdfplumber: bbox grid with `None` holes — minimal portable span-aware model.** `Table.rows` builds `Row([xdict.get(x) for x in xs])` where missing slots are `None` (`pdfplumber/table.py:318-336`); `extract()` returns `List[List[Optional[str]]]` with `None` for absent cells (`table.py:376-410`). Impact: merged cells appear once with `None` placeholders; ~30 lines of logic, no explicit rowspan integers, but preserves rectangular grid shape. Best **minimal** model to copy into whisker HTML parsing.

- **[HIGH] camelot: geometry `Cell` grid with span flags, DataFrame export.** `Cell` carries bbox + `hspan`/`vspan` booleans derived from border presence (`camelot/core.py:425-508`); `Table` holds 2D `cells` and exports `.df`. Impact: span-aware at PDF geometry layer; still flattens to DataFrame for tests. Not directly portable to markdown pipe tables.

- **[MED] img2table: `OrderedDict[int, list[TableCell]]` + HTML span reconstruction.** `ExtractedTable.content` maps row index to bbox-backed `TableCell` list; `html` property groups cells by hash and emits `rowspan`/`colspan` via `create_all_rectangles` / `html_cell_span()` (`src/img2table/tables/objects/extraction.py`, per repo-scan and GitHub source). Impact: richest span-aware export; heavier than whisker needs unless we emit HTML tables from facts.

- **[LOW] tabula-java: row/column `RectangularTextContainer` list without explicit span integers.** `Table.getRows()` returns geometric cells (`TestBasicExtractor.java:225-282`); merged cells are implicit in layout. Impact: geometry-only; not portable to markdown QA.

**Recommendation:** Extend `_HTMLTableParser` to emit pdfplumber-style `list[list[str | None]]` (fill span slots with `None`, anchor cell holds text). Defer img2table-style span reconstruction unless we need to **emit** merged HTML from parsed grids.

### Q3 — Cell normalization before comparison

- **[HIGH] whisker `_norm_cell`: whitespace collapse + lowercase only.** `_WS_RE.sub(" ", text).strip().lower()` (`facts.py:268-269`); neighbor compare allows Levenshtein budget via `fact.max_diffs` (`facts.py:368-369`). Impact: deterministic and cheap; case-folds away intentional case facts unless `surface: raw` (which `_norm_cell` still lowercases for tables — table path always uses `_norm_cell`).

- **[MED] pdfplumber: domain-specific pre-assert normalization.** `fix_row_spaces` strips **intra-cell** spaces on first three columns only before row compare (`tests/test_ca_warn_report.py:14-15`, `:54-55`); NICS numeric parse uses `int(x.replace(",", ""))` before invariant math (`tests/test_nics_report.py:67-68`). Impact: tighter than blanket lowercasing for numeric tables; pattern worth optional `table` fact `normalize: strip_commas` flag, not global `_norm_cell` change.

- **[MED] camelot: extraction-time `strip_text` + empty-cell strip in metrics.** Stream tests pass `strip_text=" ,\n"` (`tests/test_stream.py:177-181`); `compute_whitespace` treats `not cell.strip()` as empty (`utils.py:1587-1588`). Impact: whitespace metric aligns with stripped empties; no unicode NFKC.

- **[MED] tabula-java: transport normalization only.** `UtilsForTesting.loadCsv` normalizes `\n` → `\r` before byte compare (`UtilsForTesting.java:85`). Impact: documents need for shared normalization layer in whisker guard baseline schema.

- **[MED] img2table: sort/set equality before structural diff.** Prior scan: sorted coordinates for lines/cells (`tests/tables/bordered/lines/test_lines.py:27-32`). Impact: order-invariant cardinality diffs; whisker table facts are order-sensitive by design (correct for comprehension).

**Gap vs extractors:** We do not strip thousands separators or domain-specific intra-cell spaces before table compare; pdfplumber shows when that matters (`test_ca_warn_report.py:14-15`).

### Q4 — Camelot `accuracy`/`whitespace` metrics as whisker auto-baseline fact

- **[HIGH] Worth adopting as a reference-free **sidecar**, not a Lane 3 replacement.** Map camelot's `compute_whitespace` (`utils.py:1567-1590`) to `%` empty cells in `parse_pipe_tables` + `parse_html_tables` output; map `accuracy` analog to structural signals we already have (ragged row lengths, separator misparse, fence-skipped false tables). Composite `confidence = (accuracy/100)*(1-whitespace/100)` with documented `>= 0.8` operating point (`core.py:688-689`, `:674-697`) fits 00-baseline A3 `auto_baseline_checks` as a **table-level auto-baseline field** pinned in guard JSON like camelot pins `parsing_report` (`tests/test_common.py:35-40`). Impact: catches near-empty or ragged pipe/HTML tables before fuzzy TEDS; does **not** prove LLM comprehension (00-baseline: Lane 3 still required).

- **[MED] Pair with camelot lattice `_GRID_WHITESPACE_REJECT = 90.0` hard-reject pattern** (`camelot/parsers/lattice.py:26-32`, `299-308`) as upstream gate when whitespace analog exceeds threshold — same spirit as img2table's hard-reject ladder.

- **[LOW] Do not ROC-hand-copy camelot's 0.8 cut.** Fit on labeled corpus or pin per-PID snapshots; camelot itself does not calibrate (`research/llm-readability/repo-scan/camelot.md` finding 8).

### Q5 — Single highest-leverage adoptable module

- **[HIGH] Adoption candidate: camelot `compute_whitespace` + `Table.confidence` composite (`camelot/utils.py:1567-1590`, `camelot/core.py:674-697`, MIT).** ~40 lines, zero new dependencies, plugs directly into whisker `auto_baseline_checks` / guard baseline pinning (`tests/test_common.py:35-40` pattern). Delivers reference-free table-quality axis none of the four extractors' **full** golden suites port cleanly to markdown, while img2table's ladder (`filter/model.py:125-162`) and pdfplumber's NICS invariant (`tests/test_nics_report.py:81-85`) are document-specific.

## False-pass hypothesis

Two adjacent WG21 ballot columns swap (`Yes`/`No` headers exchange places) while every cell string still appears somewhere in the markdown table. Camelot `assert_frame_equal` and pdfplumber column-slice tests fail; whisker `_check_table` passes if the fact only asserts `cell: "Yes"` with `right: "No"` on one occurrence that still exists in the permuted grid **without** a `table_heading` anchor and without asserting the header row — because `_norm_cell` match finds a decoy `(Yes, No)` pair in the wrong row/column.

## False-fail hypothesis

tomd emits an HTML table with `rowspan=2` on a header cell; whisker's flat `_HTMLTableParser` duplicates or drops the spanned cell, shifting neighbors. A correctly converted paper fails `_check_table` neighbor assertions even though human-readable HTML is faithful — false fail driven by our span-blind grid, not conversion error.

## Adoption candidate

**camelot `compute_whitespace` + `Table.confidence` property** — `camelot/utils.py:1567-1590`, `camelot/core.py:674-697`, **license: MIT**. Port as `whisker/tables.py` helpers `empty_cell_pct(grid) -> float` and `table_confidence(grid, ragged_penalty) -> float`; pin in guard baseline JSON alongside existing `nid`/`teds` axes per `tests/test_common.py:35-40`.

## What would change my mind

A blind readback run (37/37 today, 00-baseline) showing column-swap corruption passes **both** Lane 3 `table` facts with `table_heading` + dual neighbors **and** camelot-style whitespace/confidence sidecars on the same papers — would downgrade camelot metrics to optional and elevate full-grid golden or pdfplumber column-slice patterns as the adoption target instead.
