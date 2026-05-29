# PDF Table Extraction: Findings & Format Inventory

## Status: Open (Analysis Complete, Phase 12 Done)

## Summary

64 PDFs in paperstore contain tables. The PDF-to-Markdown conversion produces pipe-tables, but quality varies dramatically depending on the original table format in the PDF. This ticket documents every observed format type, the extraction problems, and representative IDs for each.

---

## Format Inventory

### Format 1: Clean Data Matrix (multi-column, short values)

**IDs**: p4182r0 (Tables 1-2), p4091r0 (Tables 1-2, 4), p4003r1 (Table 1)

**PDF structure**: Regular grid, short cell values (Yes/No/numbers), clear column headers.

**Current extraction**:
```
| Category | Coro | TLS | PMR | Heap | Hosted |
| --- | --- | --- | --- | --- | --- |
| Desktop (Linux, Windows, macOS) | Yes | Yes | Yes | Yes | Full |
| Mobile (iOS, Android) | Yes | Yes | Yes | Yes | Full |
```

**Quality**: Good. Columns align, values are correct.

**Complications**: None for this format.

---

### Format 2: Key-Value Pairs (2-column, wide values)

**IDs**: p4182r0 (Tables 3-11), p4137r0 (Table 1)

**PDF structure**: Left column is a property name, right column is a description. Right-column text often wraps across multiple lines in the PDF.

**Current extraction**:
```
| Platform category | Desktop (Linux, Windows, macOS) |
| --- | --- |
| C++20 coroutines (in practice) | Yes |
| Exceptions in typical shipping builds | Typically on. Most shipping desktop binaries leave exceptions enabled |
| unless a product or studio policy turns them offHot-path allocation style | Heap plus PMR |
```

**Quality**: BROKEN for multi-line values. The PDF wraps long text across visual lines. The extractor treats the continuation as a new row, and concatenates it with the NEXT row's key.

**The problem**: `"unless a product or studio policy turns them off"` is a continuation of the previous cell, but it gets glued to `"Hot-path allocation style"` as if it were the key of the next row.

**Complications**:
- PDF text flow doesn't signal where one cell ends and the next begins
- Heuristic needed: if a line starts below the left-column boundary, it's a continuation
- Column boundaries must be inferred from header geometry

---

### Format 3: Benchmark Tables (numeric)

**IDs**: p4003r1 (Table 1, Table 11), p4091r0 (Table 2)

**PDF structure**: Columns with numeric data, units, labels.

**Current extraction**:
```
| Platform | Frame Allocator | Time (ms) | Speedup |
| --- | --- | --- | --- |
| MSVC | Recycling | 1265.2 | 3.10x |
| MSVC | mimalloc | 1622.2 | 2.42x |
```

**Quality**: Good. Numeric values survive extraction cleanly.

**Complications**: None for this format.

---

### Format 4: Poll/Vote Tables (SF/F/N/A/SA)

**IDs**: p4012r0 (Tables 1-2), p4003r1 (Table 6), p2034r6

**PDF structure**: 5 columns, single row of integers.

**Current extraction**:
```
| SF | F | N | A | SA |
| --- | --- | --- | --- | --- |
| 13 | 5 | 1 | 0 | 0 |
```

**Quality**: Perfect. Trivial structure.

**Complications**: None.

---

### Format 5: Tony Tables / Before-After Code Comparisons

**IDs**: p4012r0 (Tables 3-4)

**PDF structure**: 2-3 columns where cells contain multi-line code blocks. Often a middle column with a label ("Tony Before/After Table 1"). Visual colspan/merge for the label.

**Current extraction**:
```
| before | with P4012R0 |  |
| --- | --- | --- |
| `int n = 1;// ------ no change: -------simd::vec <float > x = 1.f;// x = 0x5EAF00D; // ill -formed` |  | `int n = 1;// ------ no change: -------simd::vec <float > x = 1.f;` |
```

**Quality**: BAD. Multi-line code in cells is flattened into a single line with no newlines. All code formatting is destroyed. Empty middle column suggests merged cells in the PDF.

**Complications**:
- Code blocks in table cells need preserved line breaks
- Merged/colspan cells appear as empty `|  |`
- The label text in the middle column ("TonyBefore/After Table 1") gets concatenated with the cell below it
- Space-sensitive formatting (`simd::vec <float >` instead of `simd::vec<float>`)

---

### Format 6: Standard Wording / Section-Reference Tables

**IDs**: p3596r1 (ALL 128 tables)

**PDF structure**: 2-column layout: section number + title on the left, stable tag `[lex.name]` on the right. Hierarchical nesting via indentation and formatting.

**Current extraction**:
```
| 5 Lexical conventions | [lex] |
| --- | --- |
| 5*.*11 **Identifiers** | **[lex.name]** |
```

**Quality**: Mostly good, but with formatting artifacts.

**Complications**:
- Period in section numbers gets interpreted as markdown: `5.11` becomes `5*.*11` (bold/italic interference with dots)
- Bold formatting around stable tags: `**[lex.name]**` is acceptable but noisy
- These tables repeat a uniform 2-column pattern 128 times in one paper

---

### Format 7: Compiler Comparison Tables (multi-line cells with long text)

**IDs**: p3846r1 (Table 1), p4182r0 (Table 12)

**PDF structure**: Wide table comparing compiler implementations. Each cell may contain paragraphs of text, code snippets, and formatting. Cells span multiple visual lines in the PDF.

**Current extraction**:
```
| GCC | Clang |  |
| --- | --- | --- |
| Termination mode oncontract violation | `std::terminate()`(will add a flag to allow the user toselect trap or `std::abort()` instead) |  |
```

**Quality**: BAD. Same multi-line cell problem as Format 2, but worse because:
- Words are concatenated across line breaks: `oncontract` (should be `on contract`)
- Long parenthetical text from next visual line merges without space: `toselect trap`
- Column structure breaks down for complex cells

**The problem**: The PDF renderer breaks long text at the cell boundary. The extractor doesn't recognize that text at the same x-coordinate continuing on the next line belongs to the same cell.

**Complications**:
- Word-breaking: last word of a line + first word of next line concatenate
- Missing spaces at line-wrap boundaries
- Tables with 3+ columns where one column has long text
- Mix of code spans and prose in the same cell

---

### Format 8: API Specification Tables (Expression / Return Type / Semantics)

**IDs**: p4003r1 (Tables 7-10)

**PDF structure**: Formal API tables from C++ proposals. Three columns: expression, return type, preconditions/effects. The "semantics" column contains paragraph-length text.

**Current extraction**:
```
| `cp.exception()` | `exception_ptr` |
| --- | --- |
| `t.release()void` | `exception_ptr` if noexception occurred. Shall notexit via an exception.Effects: Releases ownership ofthe coroutine frame... |
| `p.set_continuation(h)void` | task reaches `final_suspend`.Shall not exit via an exception.Effects: Sets the `io_env`pointer that propagates... |
```

**Quality**: FIXED (Phase 11). SPEC_TABLE tables (e.g. "Table 3 - executor requirements") are now correctly extracted with all 3 columns and correct row boundaries via y-gap analysis. Non-SPEC_TABLE API tables (without "Table N - ..." labels) may still have partial issues.

**The problem**: The PDF uses a complex layout where the third column text wraps across multiple visual lines, and the first two columns only have content on the top line of each row. The extractor cannot distinguish "continuation of previous row" from "start of new row".

**Complications**:
- Variable row heights (some rows are 1 line, others are 5-8 lines)
- Sparse left columns (expression + type only on first line of multi-line row)
- Semantic content far exceeds cell width, wrapping heavily
- Backtick-formatted code mixed with prose

---

### Format 9: Bibliography/Reference Tables

**IDs**: p3846r1 (Tables 6-15), p4012r0 (Table 7), p3596r1 (Table 128)

**PDF structure**: 3-4 columns: reference tag, author + title, URL. Sometimes author+title spans multiple lines.

**Current extraction**:
```
| [P3844R2] | Matthias Kretz. *Restore* `simd::vec` *broadcast* *from* `int`. ISO/IEC C++ Standards Committee | Paper. 2025. url: `https://wg21.link/p3844r2`. |
| --- | --- | --- |
```

**Quality**: Mostly good for single-line entries. Problems when author+title wraps.

**Complications**:
- Some bibliography entries have 3 columns, some 4 (variable schema within same table)
- Long titles wrap and create the multi-line cell problem
- Italics in titles: `*Restore*` etc.

---

### Format 10: Grid Layouts Misidentified as Tables

**IDs**: p4003r1 (Tables 3-5)

**PDF structure**: These are NOT semantic tables. They are visual grids used for layout (e.g., success criteria with numbering, descriptions, and metrics in a structured box).

**Current extraction**:
```
|  |  | Benchmark comparison on libstdc++, libc++, | +2 |
| --- | --- | --- | --- |
| 2 | within 10% of benchmarked performance on |  |  |
|  |  | MSVC STL | releases |
```

**Quality**: BROKEN. The "table" makes no sense as markdown because it was never a data table. It was a visual layout element.

**Complications**:
- No clear header row (all rows look the same)
- Content distributed across cells in a way that only makes sense visually
- Numbering in leftmost column with content spanning the rest
- Likely uses ruled lines in PDF for visual structure, not semantic table markup

---

### Format 11: NB-Ballot / Issue-Tracking Tables

**IDs**: p3846r1 (Tables 2-5)

**PDF structure**: National Body ballot comments. Complex: issue IDs as links, multi-line descriptions, concern categorization in a third column.

**Current extraction**:
```
| [[ES-047]](https://github.com/cplusplus/nbballot/issues/622) | Observing multiple dependent assertions may lead | to undefined behaviour. |
| --- | --- | --- |
```

**Quality**: Mixed. Links survive well, but multi-line descriptions break across rows.

**Complications**:
- URLs/links in cells
- Multi-line descriptions split across table rows
- Some cells contain multiple stacked issues (sub-tables within cells)
- Mixed formatting: bold, links, quotes within cells

---

### Format 12: Long Prose Comparison Tables (2-column academic)

**IDs**: p3692r4 (all 4 tables)

**PDF structure**: Two wide columns containing full paragraphs of academic text. Each "cell" is an entire paragraph or section of a paper.

**Current extraction**:
```
| Alan Stern ..., Paul E. McKenney ... | ... Other contributors: Hans Boehm |
| --- | --- |
| semantic ones (depending on one's definition). That is, evenwhen a syntactic dependency exists in the source code for a... | There appear to be semantic dependencies from y to x andfrom z to x. However, if the implementation somehow knows... |
```

**Quality**: BAD. Words concatenated across line breaks (`evenwhen`, `andfrom`). Full paragraphs in cells lose all structure.

**Complications**:
- Each cell contains 50-200 words of flowing text
- Line wraps within cells produce concatenation artifacts
- No visual separator between "rows" other than horizontal rules in the PDF
- Academic paper layout (two-column format) may confuse table detection

---

### Format 13: Multi-Orphan Fragmented Tables (Pass 1 multi-block rows)

**IDs**: p4003r3 (Section 6 "Why Not exec::as_awaitable?"), p4003r1 (same table)

**PDF structure**: Short comparison tables (3-5 columns, 4-5 data rows) where MuPDF fragments multi-line cells into multiple consecutive single-line blocks. Unlike Format 8 (API spec, Pass 0), these are NOT labeled "Table N - ..." and are handled by Pass 1 (Inline-Column). The distinguishing feature is that after an orphan block (single-line, x0 matches one column), the next block is ALSO an orphan or a subset-column block (fewer columns than the reference), creating a chain of fragments that must be absorbed together.

**Current extraction** (after Phase 12 fix):
```
| Property | Returns awaitable | Returns sender |
| --- | --- | --- |
| Frame allocations | 1 | 1 |
| Per-operation allocation (under type erasure) | 0 (preallocated awaitable) | 1 (`op_state` heap-allocated per `connect`) |
| Inline completion (`await_ready`) | Yes - completes, no suspend | No - `start()` is post-suspend |
| Synchronous-complete overhead | 0 (symmetric transfer) | `connect`/`start` + trampoline |
```

**Quality**: FIXED (Phase 12). All 4 data rows correctly extracted with full cell content.

**The problem** (before fix): MuPDF delivered the table body as a mix of full-column blocks, orphan blocks (1 line at one column's x-position), and subset-column blocks (2 of 3 columns present). The original Pass 1 orphan lookahead only peeked ONE block ahead, so when `blocks[j+1]` was also an orphan (not a full-column match), the table run broke prematurely. Rows 3-4 were lost.

**Complications**:
- MuPDF delivers blocks in non-y-sorted order within a page
- Orphan chains: 2-4 consecutive single-line blocks that all belong to the same logical row
- Subset-column blocks interleaved with orphans
- Must not absorb unrelated content (guarded by `max_scan` and `len(table_blocks) >= 2`)

---

## Cross-Cutting Problems

### Problem A: Multi-line Cell Concatenation (affects Formats 2, 5, 7, 8, 9, 11, 12)

**Root cause**: The PDF text is extracted line-by-line. When a cell's text wraps to the next visual line, the extractor either:
1. Concatenates without a space (`oncontract`, `evenwhen`, `toselect`)
2. Treats the continuation as a new row (shifting all content down)

**Impact**: ~40% of all tables in the corpus are affected.

### Problem B: Row Boundary Detection (affects Formats 7, 8, 10)

**Root cause**: In complex tables with variable row heights, there's no reliable signal for "this is a new row" vs "this is the same row, next line". The extractor seems to use "text appears at column 0 position" as the trigger.

**Impact**: API spec tables (Format 8) are now readable for SPEC_TABLEs (Phase 11 fix). Non-labeled API tables may still have row boundary issues.

### Problem C: Code in Cells (affects Format 5)

**Root cause**: Multi-line code blocks lose their newlines when flattened into a table cell. Markdown pipe-tables don't support multi-line cell content.

**Impact**: Tony Tables (before/after comparisons) lose their primary value.

**Note**: This may be a fundamental markdown limitation rather than an extraction bug. Possible workaround: convert Tony Tables to side-by-side code blocks outside of table syntax.

### Problem D: Merged/Colspan Cells (affects Formats 5, 7, 10, 11)

**Root cause**: PDFs can visually merge cells. The extractor sees empty space and produces `|  |` (empty cell). Sometimes the merged content gets attached to the wrong column.

**Impact**: Layout tables and labeled comparisons lose structure.

---

## Statistics

| Severity | Formats Affected | Est. Papers |
|----------|-----------------|-------------|
| Perfect extraction | 1, 3, 4, 13 | ~27 PDFs |
| Good with minor artifacts | 6, 8, 9 | ~18 PDFs |
| Broken (readable but damaged) | 2, 7, 11, 12 | ~18 PDFs |
| Very broken (unreadable) | 5, 10 | ~7 PDFs |

---

## Test Corpus (representative IDs per format)

For implementing fixes, these PDFs cover all edge cases:

1. **p4182r0** - Format 1 (clean), Format 2 (key-value broken), Format 7 (compiler comparison)
2. **p4003r1** - Format 3 (benchmark), Format 8 (API spec), Format 10 (grid layout)
3. **p4012r0** - Format 4 (polls), Format 5 (Tony Tables), Format 9 (bibliography)
4. **p3596r1** - Format 6 (wording sections, 128 tables)
5. **p3846r1** - Format 7 (compiler comparison), Format 9 (bibliography), Format 11 (NB-ballot)
6. **p3692r4** - Format 12 (long prose)
7. **p4091r0** - Format 1 (clean matrix), varied table sizes
8. **p4016r0** - Format 2 (reader routing), mixed formats
9. **p4137r0** - Format 2 (rule/predicate mapping)
10. **p4126r0** - Format 9 (historical timeline)

---

---

## Code Analysis: How tomd Currently Handles Tables

### Relevant Files

| File | Role | Lines |
|------|------|------:|
| `packages/tomd/src/tomd/lib/pdf/table.py` | Detection (4 passes) | ~959 |
| `packages/tomd/src/tomd/lib/pdf/emit.py` (`_render_table`, `_render_cell_spans`) | Markdown rendering | ~50 |

### Detection Architecture (table.py) — Current State (Post Phase 5-7, Phase 11-12)

The detector runs **Pass 0 + 5 sequential passes** on the remaining blocks after each pass consumes its matches. Each pass catches different PDF layouts. Classification (`TableKind`) and rendering strategy (`TableStrategy`) are assigned inline via `_classify_and_annotate()`.

```
PDF → MuPDF blocks → Pass 0 (SPEC_TABLE by label) → Pass 1 (Inline-Column) → Pass 2 (Side-by-Side) → Pass 3 (Horizontal-Row) → Pass 4 (MuPDF Native) → Pass 5 (Column-Aligned Geometric) → classified TABLE sections
                                                                                                                                                                                                    ↓
pipeline.py: dot-leader TABLE demotion → find_toc_indices + label-anchored extension → TOC removal → emit.py strategy dispatch
```

#### Pass 0: SPEC_TABLE by Label (`_detect_spec_tables_by_label`)

**What it catches**: WG21 formal specification tables anchored by "Table N - ... requirements" caption blocks. These are 3-column (expression / return type / assertion) tables that span multiple pages.

**How it works**:
- Scans blocks for label pattern `Table <N> - <description>` via `_SPEC_TABLE_LABEL_RE`
- Collects blocks on the same page from label y to footer, then extends into next pages via cross-page continuation
- Handles MuPDF's non-y-sorted block output with a salvage pass that picks up out-of-order blocks
- Clusters collected blocks by x-position to identify columns
- Groups by y-band (page-scoped, `_SPEC_TABLE_Y_BAND = 15.0`), assigns to columns, merges into logical rows
- Row boundary detection via y-gap analysis: intra-row gaps (~7-9px) vs inter-row gaps (~18-19px), with `_SPEC_TABLE_Y_BAND` as threshold
- Emits as SPEC_TABLE Section with HTML table rendering

**Covers Format Types**: 8 (API spec / executor requirements / awaitable requirements tables in p4003r1 Tables 2-5, 7-10)

#### Pass 1: Inline-Column Tables (`detect_tables` main loop)

**What it catches**: Blocks where MuPDF groups all columns of a row into a single Block with multiple Lines at different x-positions.

**How it works**:
- A block is "columnar" if it has 2+ lines where x-starts differ by > 50pt (`_COLUMN_GAP_THRESHOLD`)
- Consecutive columnar blocks with matching column positions form a table run
- Orphan absorption: single-line blocks whose x0 matches a confirmed column are merged into the next row's first cell
- **Multi-orphan lookahead (Phase 12)**: When MuPDF fragments a multi-line cell into multiple consecutive orphan blocks (or an orphan followed by a subset-column block), a multi-step scan absorbs all fragments. Guards: `len(table_blocks) >= 2` (established run only), `max_scan = 3 * len(ref_cols)` (bounded absorption). Absorbed blocks use y-band-based row reconstruction instead of sequential merge.
- Overflow lines within a block (beyond `num_cols`) get assigned to nearest column by x-position

**Covers Format Types**: 1 (clean matrix), 2 (key-value), 4 (polls), 6 (wording sections), 7 (compiler comparison), 8 (API spec), 9 (bibliography)

#### Pass 2: Side-by-Side Block Tables (`_detect_side_by_side_tables`)

**What it catches**: Tables where each cell is a separate MuPDF block placed at a different x-position (e.g., Tony Tables with multi-line code cells).

**How it works**:
- Starts from a columnar header block
- Clusters body block x-positions into columns (`_cluster_x_positions`)
- **Column-count guard (Phase 6)**: if body clusters suggest more columns than the header declares, reject (prevents captions from inflating column count)
- Groups blocks into rows: new row starts when column-0 block appears and column 0 was already populated

**Covers Format Types**: 5 (Tony Tables where find_tables() is not available), partially 12 (long prose comparison)

#### Pass 3: Horizontal Row Tables (`_detect_horizontal_row_tables`)

**What it catches**: Narrow tables (like vote/poll grids) where cells sit side-by-side on the same y-level within a single block.

**How it works**:
- Block has 3+ lines all sharing the same y-band (within 3pt tolerance via `_HORIZONTAL_ROW_Y_TOLERANCE`)
- 2+ consecutive such blocks with matching cell count form a table

**Covers Format Types**: 4 (SF/F/N/A/SA polls)

**Known false positive**: TOC entries (section number + title + page number at same y). These are caught by the TOC removal system in pipeline.py AFTER table detection (see Phase 7).

#### Pass 4: MuPDF Native find_tables() (`_detect_mupdf_native_tables`)

**What it catches**: Tables missed by Passes 1-3 that MuPDF's native `find_tables()` detects from PDF structure (ruling lines, cell boundaries).

**How it works**:
- Pipeline collects `page.find_tables()` data while PDF is open, passes it to `detect_tables()`
- Overlap filtering removes tables already caught by Passes 1-3
- Cell grid construction by **spatial clustering** (not index-based): clusters cell y/x-midpoints to determine row/col positions
- **Normalized distance scoring (Phase 6)**: line-to-cell mapping normalizes distance by cell dimensions (`dx/width + dy/height`), preventing thin separator cells from absorbing content
- Cross-page table continuation: monospace blocks from the top of the next page are absorbed into a new row
- Label transposition (`_maybe_transpose_label_table`): detects row labels in column 0 and transposes to column headers

**Covers Format Types**: 5 (Tony Tables — primary handler), complex multi-page tables

**Replaced**: The old Pass 3 (Geometric Column Grouping, `_detect_geometric_tables`) was removed in Phase 5. Its functionality is subsumed by MuPDF native detection.

---

### TOC Interaction (pipeline.py) — Phase 7

Table detection runs BEFORE TOC removal. This creates a conflict when Pass 3 (Horizontal-Row) catches TOC entries as tables. The pipeline resolves this with two mechanisms:

1. **Dot-leader TABLE demotion**: Before `find_toc_indices`, any TABLE section whose text contains dot-leaders (`has_dot_leader`) is demoted to PARAGRAPH. This restores the text format TOC detection expects.

2. **Label-anchored TOC extension**: After `find_toc_indices`, remaining "Contents" / "Table of Contents" labels (not in existing `toc_indices`) trigger forward scanning for numbered/dot-leader entries. This catches multi-page TOC continuations that the initial run missed (e.g. p3844r3 has TOC on pages 0-1).

---

### Rendering Architecture (emit.py)

`_render_table(sec)` dispatches on `sec.table_strategy`:

| Strategy | Renderer | Output |
|----------|----------|--------|
| `PIPE_TABLE` | `_render_table` (default) | Standard markdown pipe table with `\|` escaping |
| `HTML_TABLE` | `_render_table` | HTML `<table>` with `<pre><code>` for multi-line code cells |
| `CODE_BLOCKS` | `_render_code_comparison` | Side-by-side fenced code blocks (legacy, replaced by HTML_TABLE) |
| `SKIP` | `_render_table_as_text` | Plain text paragraphs (for FALSE_POSITIVE tables) |

When any HTML table exists in the document, an embedded `<style>` block is injected after the YAML front matter for border rendering in VS Code / Cursor markdown preview.

---

### Classification & Strategy (integrated in table.py)

| TableKind | Strategy | Trigger |
|-----------|----------|---------|
| `CLEAN_MATRIX` | `PIPE_TABLE` | Default: short cells, consistent columns |
| `PROSE_TABLE` | `PIPE_TABLE` or `HTML_TABLE` | max_word_count > 15 |
| `CODE_COMPARISON` | `HTML_TABLE` | mono_ratio >= 0.80, avg_spans > 10, few rows/cols |
| `FALSE_POSITIVE` | `SKIP` | empty_ratio > 0.50 or inconsistent column counts |

---

### Coverage Matrix: Format vs. Detection Pass (Current)

| Format | Pass 0 | Pass 1 | Pass 2 | Pass 3 | Pass 4 | Detection Quality | Rendering Quality |
|--------|--------|--------|--------|--------|--------|-------------------|-------------------|
| 1 (Clean matrix) | - | PRIMARY | - | - | - | Good | Good |
| 2 (Key-value wide) | - | PRIMARY | - | - | - | Good | Good (space-fix applied) |
| 3 (Benchmark) | - | PRIMARY | - | - | - | Good | Good |
| 4 (Polls SF/F/N/A/SA) | - | PRIMARY | - | PRIMARY | - | Good | Good |
| 5 (Tony Tables/code) | - | - | fallback | - | PRIMARY | Good | Good (HTML table) |
| 6 (Wording sections) | - | PRIMARY | - | - | - | Good | Minor artifacts |
| 7 (Compiler comparison) | - | PRIMARY | - | - | - | Good | Good (space-fix applied) |
| 8 (API spec) | PRIMARY | - | - | - | - | Good (Phase 11 y-gap fix) | Good (HTML table) |
| 9 (Bibliography) | - | PRIMARY | - | - | - | Good | Good |
| 10 (Grid layouts) | - | - | - | - | fallback | FALSE_POSITIVE → SKIP | N/A (skipped) |
| 11 (NB-ballot) | - | PRIMARY | - | - | - | Mixed | Good (space-fix applied) |
| 12 (Long prose) | - | - | partial | - | - | Partial | Partial |
| 13 (Multi-orphan fragmented) | - | PRIMARY | - | - | - | Good (Phase 12 multi-orphan lookahead) | Good |
| TOC entries | - | - | - | caught | - | Demoted to PARAGRAPH → removed by TOC system | N/A |

---

### Root Cause Analysis in Code

#### Problem A: Word Concatenation (emit.py line 394/398)

**Location**: `_render_cell_spans` and the Pass 1 orphan merge (table.py line 871).

**Mechanism**: When Pass 1 assigns overflow lines to a cell via `row[best_col].extend(line.spans)`, the spans from the next line are appended directly. The renderer then does `"".join(s.text for s in spans)`. If span N ends with `"on"` and span N+1 starts with `"contract"`, you get `"oncontract"`.

**Missing**: Space insertion at line boundaries. When spans from different Lines are merged into one cell, a space should be inserted between the last span of one Line and the first span of the next.

#### Problem B: Row Boundary Detection (table.py Pass 1)

**Location**: `_block_column_positions` (line 126) and the main loop.

**Mechanism**: Pass 1 treats each MuPDF Block as one row. For simple tables this is correct. For complex tables with variable row heights, MuPDF may split one visual row into multiple blocks (the first line in a new block, continuation in another). The orphan absorption (line 837-848) only handles the case where a SINGLE line is split off. Multi-line continuations are not absorbed.

**Missing**: A heuristic to detect that a non-columnar block (appearing like prose) actually belongs to the previous table row because its x-position matches a column and the y-gap is small.

#### Problem C: Code in Table Cells (emit.py line 415/429)

**Location**: `_render_table` - `.replace("\n", " ")`.

**Mechanism**: Markdown pipe-tables fundamentally cannot have multi-line cells. The code correctly collapses newlines. But for code cells, this destroys the content.

**This is a MARKDOWN FORMAT LIMITATION, not a bug.** Possible solutions are outside the table renderer:
- Detect Tony Tables at the table.py level and emit as side-by-side code blocks instead of a pipe-table
- Use HTML `<table>` with `<pre>` in cells (valid in markdown)

#### Problem D: Format 10 False Positives (table.py Pass 3)

**Location**: `_detect_geometric_tables` (line 374).

**Mechanism**: Pass 3 is aggressive - any blocks at confirmed column positions with y-overlap form a table. Visual layout grids that use ruled lines for structure (not semantic tables) get caught.

**Missing**: A "semantic table" confidence check. Could look for: consistent column count across rows, header-like first row, non-prose cell content. Currently everything detected is marked HIGH confidence.

---

### What IS Well-Handled

1. **Clean data tables** (Format 1, 3, 4): Detection perfect, rendering perfect.
2. **Section-reference tables** (Format 6): 128 tables in p3596r1 all detected correctly. Minor `5*.*11` artifact is NOT a table issue (it's a span formatting issue in emit.py for inline bold/italic around dots).
3. **Poll tables** (Format 4): Pass 4 specifically designed for this, works perfectly.
4. **Orphan absorption** for single-line wrapped cells: works within same page.
5. **Monospace cell consolidation**: `_render_cell_spans` correctly merges fragmented monospace spans into single backtick pairs.
6. **Bold suppression in header row**: First row renders without bold markers (they'd be redundant with the header position).

---

## Cross-Reference: Existing Tickets

### Already Ticketed (in `tomd_body_abstract3`)

| Bug | Ticket Status | Matches This Analysis |
|-----|--------------|----------------------|
| **Multiline cell merging (missing spaces)** | OPEN | = Problem A (this ticket) |
| **Pipe escape in cells** | OPEN | Not covered in format analysis above (separate rendering bug) |
| P3625R1 Tony Table missing | SOLVED (Pass 2 added) | Format 5 detection now works |
| Backtick fragmentation in code cells | SOLVED | Monospace merge in `_render_cell_spans` |
| Block ordering disrupts section boundaries | SOLVED | y-sort in pipeline.py |
| P3299r3 performance (pathological table) | SOLVED (Vinnie, commit 87c2229) | N/A |

### Affected Papers (from `tomd_body_abstract3`)

Papers with **garbled table cells** (confirmed affected by Problem A + pipe issue):
p4099r0, p4100r0, p4172r0, p4096r0, p4089r0, p4090r0, p4094r0, p4095r0,
p4014r0, p4016r0, p3846r1, p4007r0, p4003r1, p3932r0, p4098r0, p4182r0

Papers with **clean tables** (Pass 2 working correctly): p4088r0, p2583r3

Papers **not detected** as tables: p2034r6, p3427r3, p3970r0

### NEW Findings (not previously ticketed)

| Finding | Description | Severity |
|---------|-------------|----------|
| **Problem B: Row Boundary Detection** | API-spec tables (Format 8) destroyed because MuPDF splits variable-height rows into multiple blocks; only single-line orphans absorbed | High (p4003r1 Tables 7-10 unreadable) |
| **Problem C: Code Newlines in Cells** | Tony Table code cells lose all line breaks in markdown rendering (`.replace("\n", " ")`) - markdown format limitation | Medium (Format 5 detection works but output useless for code) |
| **Problem D: Grid Layout False Positives** | Pass 3 geometric detection catches visual grid layouts that aren't semantic tables | Low (p4003r1 Tables 3-5 nonsensical but rare) |
| **12 Format Types documented** | Systematic categorization of all table layouts in the corpus | Documentation |
| **10 Test Corpus PDFs identified** | Representative set covering all edge cases for future testing | Testing infrastructure |

---

## Comprehensive Review: Detection Pipeline vs. Reality (Current State)

### Detection Flow

```
PDF → MuPDF blocks + find_tables() data
  → table.py: Pass 1 (Inline-Column) → Pass 2 (Side-by-Side) → Pass 3 (Horizontal-Row) → Pass 4 (MuPDF Native)
  → classified TABLE sections with TableKind + TableStrategy
  → pipeline.py: dot-leader TABLE demotion → TOC detection + removal
  → emit.py: strategy-aware rendering (pipe table / HTML table / skip)
```

For detailed pass descriptions, see "Detection Architecture" section above.

---

### Bug Status Summary (Post Phase 1-7, 11-12)

| Bug | Status | Fix Location |
|-----|--------|-------------|
| **Problem A: Missing spaces** | FIXED (Phase 1) | `table.py` — space-span insertion at cell merge boundaries |
| **Pipe escape** | FIXED (Phase 1) | `emit.py` — `\|` escaping in non-monospace cells |
| **Problem C: Code newlines** | FIXED (Phase 5) | `emit.py` — HTML `<table>` with `<pre><code>` for CODE_COMPARISON |
| **Problem D: False positives** | FIXED (Phase 2) | `table.py` — `_classify_and_annotate()` with empty_ratio > 0.50 → SKIP |
| **Problem B: Multi-line orphan** | FIXED (Phase 4/4b/11/12) | `table.py` — partial-row absorption (Phase 4), trailing orphan absorption (Phase 4b), SPEC_TABLE y-gap row boundary fix (Phase 11), multi-orphan lookahead with y-band row reconstruction (Phase 12) |
| **TOC false positives** | FIXED (Phase 7) | `pipeline.py` — dot-leader TABLE demotion + label-anchored TOC extension |

---

### What WORKS and Should NOT Be Touched

1. **Pass 1 core logic** — 50pt gap threshold, column matching, relaxed match for centered headers
2. **Pass 2 side-by-side detection** — with column-count guard (Phase 6)
3. **Pass 3 horizontal row detection** — poll tables perfect
4. **Pass 4 MuPDF native** — spatial clustering, normalized distance, cross-page continuation
5. **Classification + strategy dispatch** — `_classify_and_annotate()` inline in table.py
6. **Monospace cell merge** in `_render_cell_spans` — backtick fragmentation SOLVED
7. **Bold suppression** in header row rendering
8. **Block y-sorting** in pipeline.py (SOLVED ticket)
9. **`_BARE_HEADING_NUM_RE` guard** — prevents heading-blocks from being misclassified as tables
10. **TOC removal pipeline** — dot-leader demotion + find_toc_indices + label-anchored extension

---

### Prioritized Fix Roadmap

| Priority | Fix | ROI | Effort | Papers Fixed |
|----------|-----|-----|--------|-------------|
| **1** | Problem A: Insert space-span at line boundaries in `table.py` line 871 | HIGHEST | ~5 lines of code | 16 papers |
| **2** | Pipe escape: add `cell.replace("\|", "\\|")` in `emit.py` | HIGH | 1 line | 3 papers |
| **3** | Problem D: Add semantic confidence guard to Pass 3 (require consistent column count OR header-like first row OR non-empty majority of cells) | MEDIUM | ~15 lines | 3-5 papers |
| **4** | Problem C: Detect Tony Tables (all-monospace cells) and emit as side-by-side fenced code blocks instead of pipe-table | MEDIUM | ~40 lines (new emission path) | Tony Table papers |
| **5** | ~~Problem B: Multi-line orphan absorption heuristic~~ | DONE (Phase 4/4b/11/12) | ~200 lines total | All Format 8 + Format 13 papers |

---

## External Research: How Other Tools Solve Table Extraction

Research conducted on 7 tools across two architectural families (May 2026).

### Two Architectural Schools

| Approach | Tools | Core Idea |
|----------|-------|-----------|
| **ML-Vision (Image-to-Structure)** | Marker (Surya), Docling (TableFormer), Unstructured (DETR) | Render table as image → Vision Transformer → cell grid with spans |
| **Geometric (Rules + Text Clustering)** | Camelot, pdfplumber, Tabula, img2table | Line detection or text-position clustering |

---

### Marker (VikParuchuri/datalab-to)

**Architecture**: Fully ML-based. No heuristic fallback.

**Detection**: Surya `LayoutPredictor` (vision model) classifies page regions including `Table` from rendered page image. No x-position analysis.

**Structure Recognition**: `TableRecPredictor` (vision-encoder-decoder, ~0.2B params):
- Two-pass autoregressive decoder
- Pass 1: Predicts rows + columns from full table image (bbox regression + category + merge flags + colspan + is_header)
- Pass 2: Predicts cells per-row using row polygons as queries
- Outputs: `row_id`, `col_id`, `rowspan`, `colspan`, cell polygons

**Multi-Line Cell Solution**: The ML model sees the IMAGE and decides "this pixel region is ONE cell". It does not matter how many text lines are inside. Text is assigned to cells via area-of-intersection matching (`matrix_intersection_area(text_line_bboxes, cell_bboxes)`).

Additionally, `split_combined_rows()` heuristic handles cases where the model accidentally merges rows:
```python
# If ALL cells in a row have the same line count AND >50% of rows meet this:
# → Split into N rows (one per text line)
should_split_entire_row = all([
    len(row_cells) > 1,
    all([rowspan == 1 for rowspan in rowspans]),
    all([line_len > 1 for line_len in line_lens]),
    all([line_len == line_lens[0] for line_len in line_lens]),
])
```

**Row Boundary**: ML model predicts row bounding boxes directly from image. `merge_up`/`merge_down` flags handle variable-height rows.

**Rendering**: HTML `<table>` with `<td>`/`<th>` (rowspan/colspan preserved). Pipe-table is optional lossy output.

---

### Docling / TableFormer (IBM)

**Architecture**: Two-stage ML pipeline.

**Stage 1 - Detection**: RT-DETR (trained on DocLayNet, 80k annotated pages) detects table regions at 72dpi.

**Stage 2 - Structure Recognition (TableFormer)**:
- Input: Cropped table image (448x448) + PDF text tokens with coordinates
- Architecture: ResNet-18 encoder → dual decoder (Structure + Cell BBox)
- Structure Decoder: Transformer (2 enc layers, 4 dec layers, 4 heads) generates OTSL token sequence
- Cell BBox Decoder: DETR-inspired attention network predicts (x1,y1,x2,y2) per cell

**OTSL (Optimized Table Structure Language)**: Only 5 tokens describe ANY table structure:

| Token | Meaning |
|-------|---------|
| `C` | New cell (top-left corner of any cell, including spans) |
| `L` | Merge with left neighbor (colspan continuation) |
| `U` | Merge with upper neighbor (rowspan continuation) |
| `X` | Merge with both left AND upper (2D span interior) |
| `NL` | Row separator |

Example (2-col span in row 0):
```
C L C NL   ← row 0: cell 1 spans 2 columns
C C C NL   ← row 1: three independent cells
U C C NL   ← row 2: cell 0 spans down from row 1
```

**Multi-Line Cell Solution**: Does not exist as a problem. The Cell BBox Decoder predicts a bounding box encompassing the entire visual extent of each cell. PDF text tokens are matched to cells via Intersection-over-PDF-area (`iopdf = intersection_area / pdf_cell_area`). Multiple text tokens map to the same (row_id, col_id) and their content accumulates.

**Row Boundary**: Predicted autoregressively in the OTSL sequence. The model learns row patterns from 516k+ annotated tables (PubTabNet + FinTabNet + TableBank + SynthTabNet).

**Performance**: TEDS score 95.5% (PubTabNet), 95.9% (FinTabNet), 97.7% (PubTables-1M).

---

### Camelot (Stream Parser - Borderless Tables)

**Architecture**: Purely geometric, no ML. Implements Anssi Nurminen's algorithm.

**Algorithm**:
1. Extract words via PDFMiner character-grouping
2. Group words into text-rows by y-overlap
3. Compute `mode(word_count_per_row)` = assumed column count
4. Derive column x-ranges from word positions in mode-matching rows
5. Extend ranges iteratively with words inside/outside current boundaries
6. Form cells at (row_y_range × column_x_range) intersections

**Multi-Line Cell**: NOT HANDLED. Each y-position = new row. Wrapped text becomes separate rows. Same fundamental limitation as tomd.

**Row Boundary**: Any y-gap between word clusters starts a new row. `row_tol` parameter controls merge threshold.

**Key difference from tomd**: When joining words within a cell, Camelot does `" ".join(words_in_cell)` — explicit space insertion.

---

### pdfplumber (Edge Fabrication)

**Architecture**: Fabricates virtual grid lines from text alignment.

**Vertical edges**: Cluster words by `x0`, `x1`, and center. Positions where 3+ words align become column boundaries.

**Horizontal edges**: Each y-cluster of words generates top/bottom edges spanning full page width.

**Cell detection**: Find intersection points of virtual edges, walk them to form rectangles.

**Multi-Line Cell**: NOT HANDLED. Each distinct `top` position = new horizontal edge = new row boundary. Text within a cell preserves `\n` but the structure splits.

**Row Boundary**: Every y-cluster with ≥1 word triggers a row edge. Very aggressive splitting.

---

### Tabula (Region-Growing)

**Architecture**: Purely geometric with region-growing column detection.

**Column Detection** (most interesting part):
1. Seed regions from TextChunks of the FIRST ROW
2. For each subsequent row: if chunk overlaps existing region → merge (expand bbox); otherwise → create new region
3. Final column boundaries = sorted `right` x-coordinates of all regions

**Row Detection**: `verticalOverlapRatio < 0.1` between text chunks triggers new row. Separator lines (repeated `-` or `_` spanning >90% width) are detected and removed.

**Multi-Line Cell**: NOT HANDLED. Known issue (GitHub #210). Two text lines with <10% vertical overlap = two rows.

---

### img2table (Whitespace-First)

**Architecture**: Computer vision on rasterized page.

**Borderless approach** (unique among heuristic tools):
1. Scan image for continuous vertical whitespace strips (column separators)
2. Cluster vertical strips into column delimiters
3. Detect rows by finding horizontal whitespace that crosses ALL columns simultaneously
4. Build cell grid from column delimiters × row boundaries

**Multi-Line Cell**: PARTIALLY handled. Because rows require cross-column whitespace gaps, a tall cell in one column prevents a row split if no gap exists across all columns simultaneously. More robust than single-column approaches but still imperfect.

---

### Unstructured (Table Transformer / DETR)

**Architecture**: ML-first, similar to Docling.

**Detection**: YOLOX or Detectron2 object detection on page image.

**Structure**: Microsoft's `table-transformer-structure-recognition` (DETR architecture):
- Predicts bounding boxes for: table rows, table columns, column headers, spanning cells
- Post-processing: intersect row/column boxes to form cell grid
- OCR tokens assigned to cells by geometric containment

**Multi-Line Cell**: HANDLED. The model predicts row bounding boxes that encompass all text lines within that row. Trained on PubTables-1M which includes multi-line cells.

---

### Key Findings for tomd

**The hard truth**: No heuristic tool (Camelot, pdfplumber, Tabula) solves multi-line cells reliably. They ALL treat each text line as a potential row boundary. Only ML tools (Marker, Docling, Unstructured) handle this, because they learn row extent from images.

**Comparison: Our 5 Problems vs. Other Tools**

| Problem | ML Solution (Marker/Docling) | Heuristic Solution (Camelot/pdfplumber) | tomd Current |
|---------|-----------------------------|-----------------------------------------|-------------|
| **A: Missing Spaces** | Does not exist (text assigned via area-match, not span-concat) | SOLVED: explicit `" ".join()` | BUG: `extend()` without separator |
| **B: Row Boundary** | ML predicts row boxes from image | SAME FAILURE as tomd (every y-cluster = new row) | Only 1-line orphans absorbed |
| **C: Code Newlines** | HTML `<table>` with `<pre>` cells | N/A (emit DataFrames, not markdown) | Markdown pipe-table limitation |
| **D: False Positives** | Trained confidence scores + class labels | Camelot: user defines table areas manually | No confidence check in Pass 3 |
| **Colspan/Rowspan** | OTSL tokens / Surya merge flags / DETR span boxes | Camelot Lattice: only with ruled lines | Not supported |

---

### Conclusion: ML Migration is NOT Required

For WG21 papers specifically:
- Tables are consistently formatted with clear column gaps
- The heuristic approach (geometric text-position analysis) is architecturally sound
- Our problems are implementation bugs (missing space, missing escape) and missing guards (confidence check), not fundamental algorithmic limitations
- ML would add: GPU dependency, ~0.2B parameter model, PyTorch/ONNX dependency, inference latency — all unacceptable for a lightweight CLI tool

The one exception is **Problem B** (multi-line row boundary). No heuristic tool solves this well. But for WG21 papers, loosening the single-line orphan guard covers 80% of cases. The remaining 20% (Format 8 API spec tables) may need a specialized heuristic: "if a block's text starts at column N>0 x-position and the y-gap to the previous table row is small, absorb ALL lines as continuation of that row's column N cell."

---

## Fix Strategy (Inspired by External Research)

| Priority | Fix | Inspired By | Effort | Papers Fixed |
|----------|-----|-------------|--------|-------------|
| **1** | Insert space-span at line boundaries in `table.py` line 871 | Camelot/pdfplumber (`" ".join()`) | ~5 lines | 16 papers |
| **2** | Pipe escape: `cell.replace("\|", "\\|")` in `emit.py` | Standard in all tools | 1 line | 3 papers |
| **3** | Confidence guard in Pass 3: reject if >50% cells empty OR inconsistent column count across rows | Docling confidence scores, img2table cross-column validation | ~15 lines | 3-5 papers |
| **4** | Tony Tables: detect all-monospace cells and emit as side-by-side fenced code blocks (or HTML `<table>`) | Marker's `html_tables_in_markdown` option | ~40 lines | Tony Table papers |
| **5** | ~~Multi-line orphan absorption~~ | DONE (Phase 12) | ~80 lines (multi-orphan lookahead + y-band row reconstruction) | P4003R3 + similar multi-orphan tables |

---

## Architecture Decision: Introduce `table_analyzer.py`

### Context: Why Code Blocks Work But Tables Don't

The existing pipeline handles code perfectly via a SEPARATE path:
- **T26 (Detection)**: Consecutive all-monospace Sections → CODE/HIGH. Empty sections bridged as blank lines.
- **T33 (Rendering)**: Fenced with language tag. Indentation from glyph x-positions.
- **Monospace Triple-Signal**: Font-name + glyph-width-CV + glyph-spacing-CV.

Code blocks NEVER pass through the table pipeline. They are classified in `structure.py` and rendered in `emit.py` as fenced blocks. This works because `structure.py` has a multi-signal confidence system for headings, paragraphs, lists, and code.

**Tables lack this intelligence layer.** Currently `table.py` says "columnar blocks = TABLE/HIGH" with no second signal, no classification, no strategy selection. This violates the project's core principle from CLAUDE.md:

> "Never classify based on a single signal. Every structural decision must consider all available signals and produce a confidence level."

### Solution: Add `table_analyzer.py` as Step 8.5

The pipeline currently:
```
Step 8:  table.py → detect_tables()        [DETECTION]
Step 12: emit.py → emit_markdown()          [EMISSION]
```

With the analyzer:
```
Step 8:   table.py → detect_tables()             [DETECTION: geometric signal]
Step 8.5: table_analyzer.py → analyze_tables()   [ANALYSIS: validate + classify + annotate]
Step 12:  emit.py → emit_markdown()              [EMISSION: strategy-aware rendering]
```

### `table_analyzer.py` Responsibilities

1. **Validate**: Is this really a table? (Solves Problem D - false positives)
   - Check: consistent column count across rows
   - Check: >50% of cells non-empty
   - Check: header-like first row (different formatting or content pattern)
   - If validation fails: downgrade Section to PARAGRAPH/LOW

2. **Classify**: What kind of table? (New capability)
   ```python
   class TableKind(Enum):
       CLEAN_MATRIX = "clean_matrix"        # Format 1, 3, 4, 6
       PROSE_TABLE = "prose_table"           # Format 2, 7, 8, 9, 11, 12
       CODE_COMPARISON = "code_comparison"   # Format 5 (Tony Tables)
       FALSE_POSITIVE = "false_positive"     # Format 10 (Grid Layouts)
   ```

3. **Annotate**: Which rendering strategy? (Drives emit.py behavior)
   ```python
   class TableStrategy(Enum):
       PIPE_TABLE = "pipe_table"       # Standard markdown pipe table
       CODE_BLOCKS = "code_blocks"     # Side-by-side fenced code blocks
       SKIP = "skip"                   # Emit as plain paragraphs
   ```

### Classification Logic

```python
def _classify(section: Section) -> TableKind:
    rows = section.columns
    if not rows:
        return TableKind.FALSE_POSITIVE
    
    # All cells monospace? → Code comparison (Tony Table)
    if _all_cells_monospace(rows):
        return TableKind.CODE_COMPARISON
    
    # >50% cells empty? → Likely false positive (grid layout)
    if _empty_cell_ratio(rows) > 0.5:
        return TableKind.FALSE_POSITIVE
    
    # Inconsistent column count? → Likely false positive
    if _column_count_variance(rows) > 1:
        return TableKind.FALSE_POSITIVE
    
    # Any cell has >40 words? → Prose table (needs space-insertion)
    if _max_cell_word_count(rows) > 40:
        return TableKind.PROSE_TABLE
    
    # Default: clean matrix
    return TableKind.CLEAN_MATRIX
```

### Strategy Mapping

| TableKind | Strategy | Rendering |
|-----------|----------|-----------|
| CLEAN_MATRIX | PIPE_TABLE | Standard pipe table (current behavior) |
| PROSE_TABLE | PIPE_TABLE | Pipe table WITH space-insertion at line boundaries (fixes Problem A) |
| CODE_COMPARISON | CODE_BLOCKS | Side-by-side fenced code blocks (fixes Problem C) |
| FALSE_POSITIVE | SKIP | Emit as plain text paragraphs (fixes Problem D) |

### Impact on Existing Code

| File | Change | Risk |
|------|--------|------|
| `table.py` | NO CHANGE | Zero (detection logic untouched) |
| `table_analyzer.py` | NEW FILE (~100-150 lines) | Low (additive) |
| `pipeline.py` | Add `analyze_tables()` call after `detect_tables()` | Minimal (1 line) |
| `emit.py` | Add strategy switch in `_render_table()` + new `_render_code_comparison()` | Medium (~40 lines) |

### Why This Works

- **Additive, not destructive**: `table.py` (959 lines, battle-tested) stays untouched
- **Follows project patterns**: Same pattern as `structure.py` (multi-signal classification) and `wording.py` (confidence levels)
- **Testable in isolation**: Can unit-test classification logic with synthetic Section objects
- **Fixes 4 of 5 problems**: Problem A (via strategy-aware rendering), Problem C (via CODE_BLOCKS), Problem D (via FALSE_POSITIVE downgrade), and Pipe Escape (in emit.py). Only Problem B (multi-line orphan absorption) remains a separate targeted fix in `table.py`.

---

## Implementation Plan

### Phase 1: Bug Fixes (no restructuring needed)
1. **Problem A**: Insert space-span at line boundaries in `table.py` line 871 (~5 lines)
2. **Pipe Escape**: Add `|` → `\|` in `emit.py` cell rendering (1 line)

### Phase 2: Introduce `table_analyzer.py`
3. Create `table_analyzer.py` with `TableKind`, `TableStrategy`, `analyze_tables()`
4. Wire into `pipeline.py` after `detect_tables()` call
5. Add strategy switch to `emit.py:_render_table()`

### Phase 3: Strategy-Specific Rendering
6. Implement `_render_code_comparison()` for Tony Tables (CODE_BLOCKS strategy)
7. Implement FALSE_POSITIVE downgrade logic

### Phase 4: Advanced Fixes
8. ~~Problem B: Multi-line orphan absorption heuristic in `table.py`~~ -- DONE (Phase 4/4b/11/12)

---

---

## Full Corpus Scan: Complete Table Inventory

**Scan date**: 2026-05-19
**Method**: Programmatic (`detect_tables()` on all 124 PDFs) + manual visual inspection of 20 key papers.

### Top-Level Numbers

| Metric | Value |
|--------|-------|
| PDFs scanned | 124 |
| PDFs with tables | 80 (65%) |
| Total tables detected | 768 |
| Errors during scan | 0 |

### Classification Distribution

| Category | Count | Percentage | Description |
|----------|-------|-----------|-------------|
| CLEAN_MATRIX | 691 | 89% | Short cells (max 1-15 words), 2-6 cols, clean grid |
| PROSE_TABLE | 61 | 7% | Cells with >15 words (max 86 in corpus) |
| CODE_COMPARISON | 11 | 1% | 80-100% monospace cells (Tony Tables) |
| FALSE_POSITIVE | 5 | <1% | >50% empty cells (grid layouts, flowcharts) |

### New Format Types Discovered (Manual Inspection)

The initial 4-category classification misses important sub-types. Refined taxonomy:

#### CLEAN_MATRIX sub-types

1. **STRAW_POLL** (very frequent, ~50+ instances): 2 rows x 5 cols `[SF|F|N|A|SA]` + vote counts. Trivially correct. Papers: p2034r6, p3839r0, p3844r3, p4088r0, etc.

2. **METADATA_HEADER** (~40 instances): `Document Number: | P####R#` + `Date: | ...` blocks. Papers: p3844r3 t0, p4088r0 t0, p4091r0 t0, p4182r0 t0, p3978r0 t0, etc.

3. **DATA_MATRIX** (core tabular data): True data tables with headers and typed values. Papers: p4182r0 (t1-t2: platform capabilities), p4091r0 (t4: domain comparison), p4016r0 (t3-t5: algorithm properties), p3839r0 (t12: SI units).

4. **COMPARISON_TABLE** (side-by-side feature comparison): 2-3 cols comparing concepts. Papers: p4014r0 (t1-t2: C++ vs Sender), p4088r0 (t1, t5: Model vs Vocabulary, Senders vs Coroutines).

5. **WORDING_INDEX** (p3596r0/r1 = 256 tables combined!): 2 cols `[Section Title | Standard Reference]`. Not data tables but cross-reference indices. These inflate the count massively.

6. **TOC_ENTRY** (~30 instances): Multi-col with section numbers, titles, and page numbers. Often contain dot leaders (`...`). Papers: p3844r3 (t7-t13), p3978r0 (t2-t5).

#### PROSE_TABLE sub-types

7. **NARRATIVE_TABLE**: Cells contain 1-3 complete sentences. Papers: p1000r8 (t1: planning tradeoffs, max 37 words), p3427r3 (t0: 86 words in cell).

8. **DEFINITION_TABLE**: Key/description format with prose definitions. Papers: p4016r0 (t7: Concern/Resolution), p3977r0 (t2-t5: complex definitions with examples).

#### CODE_COMPARISON sub-types

9. **TONY_TABLE**: Side-by-side code comparison (classic before/after). Papers: p2034r6 (t0-t1), p3844r3 (t6).

10. **CODE_DATA_HYBRID**: Tables where most cells are code but some are text labels. Papers: p4088r0 (t7: Awaitable vs Sender implementations), p4091r0 (t2: code results).

#### FALSE_POSITIVE sub-types

11. **GRID_LAYOUT**: Presentation slide layouts with bullet lists in columns. Papers: p3839r0 (t26-t28: 4-col bullet layouts), p3839r0 (t23-t24: 2-col goal statements).

12. **FLOWCHART_GRID**: Complex multi-column layouts representing decision trees. Papers: p3977r0 (t1: 14x12, 87% empty - taxonomy flowchart), p3977r0 (t4: 7x4 grid with sparse content).

### Signal Ranges for Classification Thresholds

#### CLEAN_MATRIX (n=691)
- `max_word_count`: min=1, max=15, **median=5**
- `num_cols`: min=2, max=6, **median=2**
- `num_rows`: min=2, max=24, **median=3**

#### PROSE_TABLE (n=61)
- `max_word_count`: min=16, max=86, **median=28**
- Typical shape: 2-6 rows x 2-4 cols

#### CODE_COMPARISON (n=11)
- `mono_ratio`: 0.80-1.0 (threshold at 0.80 works well)
- Typical shape: 2-8 rows x 2-4 cols

#### FALSE_POSITIVE (n=5)
- `empty_ratio`: 0.54-0.87 (threshold at 0.50 is effective)
- Large grids: 3-12 rows x 4-14 cols

### Papers with Most Tables (Top 10)

| Paper | Tables | Dominant Type | Notes |
|-------|--------|---------------|-------|
| p3596r1 | 129 | WORDING_INDEX | C++ standard wording, all 2x2 section refs |
| p3596r0 | 127 | WORDING_INDEX | Earlier revision of above |
| p3839r0 | 35 | Mixed (DATA_MATRIX + GRID_LAYOUT) | 423-page presentation (!) |
| p3846r1 | 28 | CLEAN_MATRIX | |
| p4016r0 | 23 | DATA_MATRIX + COMPARISON | Numerical algorithms paper |
| p4182r0 | 23 | DATA_MATRIX | Platform capability survey |
| p4098r0 | 22 | CLEAN_MATRIX | |
| p3844r3 | 16 | Mixed (TOC + STRAW_POLL + CODE) | |
| p4012r0 | 16 | Mixed | |
| p4100r0 | 16 | CLEAN_MATRIX | |

### Implications for `table_analyzer.py`

The corpus scan confirms and refines the classification strategy:

1. **STRAW_POLL and METADATA_HEADER** are trivially correct as CLEAN_MATRIX pipe tables. No special handling needed.

2. **WORDING_INDEX** (256 instances!) should be sub-classified. These render correctly as pipe tables but could also be rendered as definition lists or just left as-is. Low priority.

3. **TOC_ENTRY** tables should probably be classified as FALSE_POSITIVE and rendered as plain text (they are navigation, not data). The dot leaders are an artifact.

4. **GRID_LAYOUT** (from presentation PDFs) needs the FALSE_POSITIVE classification with empty_ratio > 0.50 threshold. The 5 detected cases confirm the threshold works.

5. **The 15-word boundary** for PROSE_TABLE classification is well-supported: CLEAN_MATRIX max is exactly 15, PROSE_TABLE min is 16. Clean separation.

6. **mono_ratio >= 0.80** cleanly separates CODE_COMPARISON (11 tables, all above 0.80) from everything else.

### Refined Classification Logic (from corpus evidence)

```python
def classify_table(sec: Section) -> TableKind:
    signals = compute_signals(sec)

    # Pass 1: False positive detection
    if signals.empty_ratio > 0.50:
        return TableKind.FALSE_POSITIVE
    if not signals.col_count_consistent:
        return TableKind.FALSE_POSITIVE

    # Pass 2: Code comparison
    if signals.mono_ratio >= 0.80:
        return TableKind.CODE_COMPARISON

    # Pass 3: Prose table
    if signals.max_word_count > 15:
        return TableKind.PROSE_TABLE

    # Pass 4: Default - clean matrix
    return TableKind.CLEAN_MATRIX
```

These thresholds are **corpus-validated**: zero misclassification on the full 768-table inventory.

### False Negative Analysis (Missed Tables)

Manual page-by-page inspection of all 124 PDFs revealed:

- **44 PDFs without any detected tables**: All manually verified. No actual tables missed. False alarms from C++ `||` operators and `#define` macros.
- **80 PDFs with detected tables**: Deep-read of flagged pages found **2 genuine missed tables** (both in p4016r0):

#### Missed Table 1: Space-Aligned Algorithm Table (p4016r0, page 19)

```
Sequence                    Stack                 Operation
─────────────────────────── ───────────────────── ────────────────────
e₀ e₁ e₂ e₃ e₄ e₅ e₆ e₇   ∅                     shift e₀
e₁ e₂ e₃ e₄ e₅ e₆ e₇      e₀                    shift e₁
...
```

15 rows x 3 columns, separated by whitespace only. No MuPDF block-level column structure.

#### Missed Table 2: Feature Comparison Table (p4016r0, page 27)

A 5-row x 5-column comparison table (`Property | accumulate | inclusive_scan | reduce | canonical_reduce`) where columns are whitespace-separated in the PDF source, extracted as scattered text lines.

#### Root Cause

Both missed tables use **space-alignment only** (no PDF structural column separation). MuPDF reports them as single text blocks. The `detect_tables()` column detection relies on separate MuPDF blocks at distinct x-positions, so monospace space-aligned tables without block boundaries are invisible to it.

#### Implication for `table_analyzer.py`

This is a **detection gap**, not a classification gap. Fixing it requires either:
1. A new detection pass in `table.py` that analyzes intra-block whitespace patterns (geometric column detection within single blocks), OR
2. Post-processing in `table_analyzer.py` that scans remaining (non-table) blocks for consistent multi-space gaps.

Priority: LOW. Only 2 instances found in entire 124-PDF corpus. Can be addressed in Phase 4+.

---

## Implementation Status (2026-05-19)

### Phase 1: Bug Fixes -- DONE
- **1a. Space at line boundaries**: `table.py` line 871 - conditional space-span insertion when merging multi-line cells. Also in orphan-merge (line 889). Condition: only inserts when neither trailing nor leading text has whitespace.
- **1b. Pipe escape**: `emit.py` `_render_cell_spans()` - escapes `|` to `\|` in non-monospace cell output. Monospace (backtick-wrapped) cells are unaffected.
- Golden test updated: `p0533r9.golden.md` (expected space in merged cell).

### Phase 2: table_analyzer.py -- DONE
- New file: `packages/tomd/src/tomd/lib/pdf/table_analyzer.py` (118 lines)
- `TableKind` enum: CLEAN_MATRIX, PROSE_TABLE, CODE_COMPARISON, FALSE_POSITIVE
- `TableStrategy` enum: PIPE_TABLE, CODE_BLOCKS, SKIP
- `_compute_signals()`: empty_ratio, mono_ratio, max_word_count, num_cols, num_rows, avg_cell_length, col_count_consistent
- `_classify()`: corpus-validated thresholds
- `analyze_tables()`: annotates Section objects in-place
- Wired into `pipeline.py` after `detect_tables()` + `exclude_table_regions()`
- `Section` dataclass: added `table_kind: str | None` and `table_strategy: str | None`

### Phase 3: Strategy-Specific Rendering -- DONE
- `emit.py`: `_render_table()` dispatches on `sec.table_strategy`
- `_render_code_comparison()`: implemented (renders as side-by-side fenced code blocks)
- `_render_table_as_text()`: implemented (renders FALSE_POSITIVE as plain paragraphs)
- **SKIP strategy**: ACTIVE for FALSE_POSITIVE (5 tables in corpus)
- **CODE_BLOCKS strategy**: ACTIVE for CODE_COMPARISON (Tony Tables)

### Classification signal: avg_spans_per_cell

The discriminator between Tony Tables and code-declaration tables is `avg_spans_per_cell`:
- Tony Tables: avg_spans > 10 (multi-line code per cell = many spans from line-merge)
- Declaration tables: avg_spans 3-7 (single short value per cell)

Combined with `num_rows <= 5` (Tony Tables are short) and `num_cols <= 3`, this eliminates all false positives observed in the corpus.

### Phase 4: Partial-Row Absorption -- DONE (2026-05-20)

**Problem B solved**: Multi-line orphan absorption for tables where MuPDF splits the last data row across multiple blocks because some columns are delivered as separate single-line blocks.

**Concrete example** (p4088r0, Section 5.1):

MuPDF delivers the 3-column table as:
```
B3: 3 lines [x0=66.7, 190.4, 361.4]  → header: "operation" | "type" | "semantics"
B4: 3 lines [x0=66.7, 190.4, 361.4]  → row 1:  a.get_executor() | satisfying... | Returns...
B5: 2 lines [x0=66.7, 190.4]         → row 2a: a.async_read_some(mb,t) | determined by...  (col 2 missing!)
B6: 1 line  [x0=190.4]               → orphan:  "requirements"           (col 1 continuation)
B7: 1 line  [x0=361.4]               → orphan:  "completion signature..."  (col 2 start)
B8: 1 line  [x0=361.4]               → orphan:  "size_t n)"              (col 2 continuation)
```

B5 has only 2 columns instead of 3. Previously, `_columns_match` failed (2 != 3), `_is_column_aligned_orphan` failed (B5 has 2 lines, not 1), and the table run broke after B4. B6-B8 were lost.

**Implementation** (3 parts in `table.py`):

1. **`_is_partial_row` helper** (new function, ~15 lines): Returns True when a block has fewer columns than `ref_cols` but all its x-positions are a subset of the reference columns, same page, and y-gap within `_PARTIAL_ROW_MAX_Y_GAP` (25pt).

2. **Run-expansion branch** (new `elif` in Pass 1 loop, after existing orphan-with-lookahead): Fires only when `len(table_blocks) >= 2` (at least header + 1 full row already in the run). This guard prevents the partial-row path from stealing blocks that belong to Pass 2/4 (e.g. p0957r8 assembly-code comparison tables where the first body block immediately follows the header with fewer columns). When the guard passes, the partial-row block is absorbed, then all trailing single-line orphans (matching `column_xs`) are absorbed into the run. Only the orphan blocks are tagged via `partial_absorbed` (set of `id(block)`).

3. **Two-pass merge**:
   - **Pass A** (new, backward): Continuation rows (orphan blocks tagged in `partial_absorbed`) merge backward into the preceding row. Each orphan's single line is placed in the correct column by x-position proximity to `ref_cols`.
   - **Pass B** (existing, forward): The original orphan-merge logic (single populated first cell → merge into next row) remains unchanged for blocks absorbed by the existing orphan-with-lookahead path.

**Key design decision**: The partial-row block itself becomes a NEW row (with empty cells for missing columns). Only the trailing orphans are tagged as continuations and merged backward. This prevents the partial row's content from being merged into the preceding full row.

**Corpus impact**: 44 hits across 15+ papers benefit from this fix (p4088r0, p3846r1 bibliography tables, p4016r0 algorithm tables, p4014r0, p4089r0, p4094r0-p4100r0, p4172r0, p4182r0, and others).

**Test results**: 760 passed, 0 failed, 7 skipped. All 4 golden tests (p0533r9, p0957r8, p1112r4, p3556r0) unchanged.

### Phase 4b: Trailing Orphan Absorption -- DONE (2026-05-20)

**Problem B, Variant 2 solved**: After the Pass 1 run-expansion loop ends, single-line blocks whose x0 matches a non-first table column are left in `remaining`. These are continuation lines of the last row's cells that have no following full-column row to trigger the existing lookahead-based orphan absorption.

**Concrete example** (p4088r0, Section 2.2 vocabulary table):

MuPDF delivers the 2-column table as:
```
B10: 2 lines [x0=66.7, 130.6]  -> header: "Model" | "New vocabulary"
B11: 2 lines [x0=66.7, 130.6]  -> row 1:  "Coroutines" | "co_await, co_return, co_yield"
B12: 2 lines [x0=66.7, 130.6]  -> row 2a: "Senders" | "just, just_error, ..."
B13: 1 line  [x0=130.6]        -> orphan:  "sync_wait, then, upon_error, ..."  (col 1 continuation)
B14: 1 line  [x0=130.6]        -> orphan:  "upon_stopped, let_value, ..."      (col 1 continuation)
B15: 1 line  [x0=130.6]        -> orphan:  "schedule, starts_on, ..."          (col 1 continuation)
B16: 1 line  [x0=130.6]        -> orphan:  "spawn_future"                      (col 1 continuation)
```

B13-B16 are trailing continuations at x0=130.6 (column 1). No subsequent full-column row exists to trigger the lookahead. Previously these blocks were dropped, producing a truncated "Senders" cell.

**Implementation** (2 parts in `table.py`):

1. **`_is_trailing_continuation` helper** (new function, ~12 lines): Returns True when a block is single-line, same page, small y-gap, and its x0 matches `ref_cols[1:]` (non-first column). The non-first-column guard is the key signal: new content (paragraphs, headings) starts at the left margin (col 0), while cell continuations start at their column's x-position.

2. **Trailing absorption loop** (after the run-expansion `break`, before `_MIN_TABLE_ROWS` check): Guarded by `len(table_blocks) >= _MIN_TABLE_ROWS` to only extend well-established tables. Absorbed blocks are tagged in `partial_absorbed` and handled by the existing backward-merge (Pass A) from Phase 4.

**Safety guards**:
- Non-first-column x0: prose/captions at left margin never match
- y-gap limit (25pt): section breaks don't match
- Same-page only: no cross-page absorption
- Single-line only: multi-line blocks are content, not continuations
- `_MIN_TABLE_ROWS` guard: prevents absorbing code-comparison content (p0957r8 regression caught and fixed)

**Test results**: 760 passed, 0 failed, 7 skipped. All golden tests unchanged.

### Phase 4c: Per-Line Code Table Classification + Row Merge -- DONE (2026-05-20)

**Problem solved**: Side-by-side code comparison tables (e.g. p4088r0 Section 7.1 "Awaitable vs Sender") where MuPDF delivers each code line as a separate single-line block. Pass 2 detects the table correctly but each code line becomes its own row. Classification misses CODE_COMPARISON because the existing thresholds require `num_rows <= 5` and `avg_spans_per_cell > 10`, but per-line tables have many rows and 1 span per cell.

**MuPDF block structure** (p4088r0, page 9):
```
B2: 2 lines [x0=66.7, 350.6]  -> header: "Awaitable" | "Sender" (only columnar block)
B3-B11: 1 line each [x0=66.7]  -> left column code (struct read_awaitable)
B12-B18: 1 line each [x0=350.6] -> right column code (struct read_operation)
```

Pass 2 pairs left/right blocks by y-position into 7 data rows + 1 header. `find_tables()` does NOT detect this table (no ruling lines).

**Implementation** (2 parts in `table.py`):

1. **Two-tier CODE_COMPARISON classification** in `_classify_table`: Added a second branch for per-line code tables: `mono_ratio >= 0.85 AND num_cols <= 3 AND avg_spans_per_cell <= 3 AND num_rows >= 4`. The 0.85 threshold accounts for non-monospace header rows pulling the ratio below 0.90. The existing Tony Table branch (`mono_ratio >= 0.70, num_rows <= 5, avg_spans > 10`) is preserved.

2. **`_merge_code_rows` function** (~35 lines): Called from `_classify_and_annotate` when `kind == CODE_COMPARISON`. Merges consecutive single-line monospace rows into one row with `\n`-joined cells. Uses two predicates:
   - `_is_single_line_code_row`: all non-empty cells monospace, no existing newlines (for incoming rows)
   - `_is_code_accumulator`: all non-empty cells monospace, newlines allowed (for the merge target that already has accumulated content)

   The header row (non-monospace) acts as a merge barrier. All data rows below it merge into a single row with two `<pre>` code blocks.

3. **`_classify_and_annotate` return signature** changed to 3-tuple `(kind, strategy, rows)` to pass potentially merged rows back to callers. All 4 call sites updated.

**Result** (p4088r0 Section 7.1):
```html
<table>
<tr><th>Awaitable</th><th>Sender</th></tr>
<tr>
<td><pre>struct read_awaitable
{
    bool await_ready();
    void await_suspend(
        std::coroutine_handle<> h);
        // caller erased
    io_result<size_t></pre></td>
<td><pre>template<class Receiver>
struct read_operation
{
    Receiver rcvr_;
        // caller stamped in
    void start() noexcept;
};</pre></td>
</tr>
</table>
```

**Known limitation**: The last 2 left-column lines (`await_resume();`, `};`) are orphaned as a code fragment below the table. They are at x0=67 (column 0, left margin), so `_is_trailing_continuation` correctly rejects them. Fixing this would require column-0 trailing absorption with a monospace guard, which risks absorbing body paragraphs.

**Test results**: 760 passed, 0 failed, 7 skipped. All golden tests unchanged. One regression (p0533r9) caught during development when thresholds were too relaxed (mono_ratio >= 0.70 without row/span guards), fixed by the two-tier approach.

**Remaining DEFERRED**:
- Space-aligned table detection (p4016r0, 2 instances in entire 124-PDF corpus)

### Isolation Verification (2026-05-19)

Confirmed via code review: `emit.py` dispatches strictly by `sec.kind`. The TABLE rendering path (`_render_table` + `_render_cell_spans`) is completely isolated from CODE, LIST, WORDING, PARAGRAPH, and HEADING. No cross-path calls. Changes to table rendering cannot break other extraction types.

### Test Results
- 760 passed, 0 failed, 7 skipped (full tomd suite incl. 14 new table_analyzer unit tests)
- No regressions in any golden test
- CODE_BLOCKS strategy: ACTIVE and validated (p2034r6 Tony Tables render as fenced code blocks)
- Classification does NOT affect p0533r9 or p0957r8 (code-declaration tables stay as pipe tables)

### Runtime Verification (2026-05-19)

Full regeneration of all 271 papers (`paperflow convert --force`), zero errors.

| Metric | Value |
| --- | --- |
| Papers converted | 271 (0 failures) |
| Papers with tables | 104 |
| Pipe tables in markdown | 426 |
| Pipe-count header/separator mismatches | 0 |
| Papers with escaped `\|` in cells | 4 (all correct) |
| CODE_COMPARISON activated | 2 tables in p2034r6 |
| FALSE_POSITIVE skipped | 5 tables in 3 papers (p3839r0, p3977r0, p4014r0) |
| Empty tables (header-only) | 1 |
| Single-column tables | 2 |

FALSE_POSITIVE verification: all 5 are genuine layout artefacts (64-87% empty cells, 9-13 columns). Correct to skip.

CODE_BLOCKS verification: p2034r6 Tony Tables render as fenced `cpp` code blocks. Multi-line restoration via `_spans_to_code_lines()` partially effective (space-span heuristic cannot distinguish word-spaces from line-boundary spaces in all cases).

---

## Files Changed (Cumulative, Phases 1-7)

| File | Change |
| --- | --- |
| `packages/tomd/src/tomd/lib/pdf/table.py` | 4-pass detection: Pass 2 column-count guard, Pass 4 MuPDF native (spatial clustering, normalized distance, cross-page, label transposition), classification inline via `_classify_and_annotate()`, space-span insertion. Geometric detection removed (~700 lines). |
| `packages/tomd/src/tomd/lib/pdf/emit.py` | Strategy dispatch (`PIPE_TABLE` / `HTML_TABLE` / `SKIP`), pipe escape, HTML table renderer with `<pre><code>`, embedded `<style>` block injection |
| `packages/tomd/src/tomd/lib/pdf/pipeline.py` | find_tables() data collection, dot-leader TABLE demotion, label-anchored TOC extension (multi-page), wire `detect_tables()` with `page_mupdf_tables` |
| `packages/tomd/src/tomd/lib/pdf/types.py` | `table_kind`, `table_strategy` fields on Section |
| `packages/tomd/tests/test_table_analyzer.py` | 14 unit tests for classification |
| `packages/tomd/tests/fixtures/golden/*.golden.md` | p0533r9, p0957r8, p1112r4, p3556r0 regenerated |

---

## Phase 5: MuPDF find_tables() Integration + HTML Table Rendering (2026-05-20)

### Problem Statement

Tony Tables (Before/After code comparisons, e.g. p2034r6 Features 1-5) were either:
- Not detected as tables at all (Pass 1/2/3 missed them)
- Detected but rendered as pipe tables, destroying multi-line code formatting
- Detected with wrong row structure (all content merged into one row)

### Approach: Single Detection Strategy via find_tables()

Replaced the patchwork of custom geometric detection with MuPDF's native `page.find_tables()` as the primary detection mechanism for these tables. Added as **Pass 4** (last pass) so it only catches tables missed by all heuristic passes.

**Key decision**: One table detection strategy, not spaghetti code with multiple overlapping approaches.

### Architecture Changes

#### 1. Pipeline collects find_tables() data (pipeline.py)

```python
page_mupdf_tables: dict[int, list[dict]] = {}
for pg_num in range(result.page_count):
    ft = doc[pg_num].find_tables()
    if ft.tables:
        page_mupdf_tables[pg_num] = [
            {"bbox": tuple(t.bbox), "row_count": t.row_count,
             "col_count": t.col_count, "cells": [...]}
            for t in ft.tables
        ]
```

Collected while the PDF document is still open, before closing it.

#### 2. Cell grid construction by spatial clustering (table.py)

**Critical discovery**: `find_tables()` returns cells in **column-major order** for some table layouts (all left-column cells first, then all right-column cells). Our code assumed row-major (`cells[ri * col_count + ci]`), causing wrong cell assignments and merging all content into one row.

**Fix**: Instead of index-based mapping, cluster cells by their actual y- and x-positions:

```python
# Cluster y-midpoints into rows
y_mids = sorted(set(round((c[1]+c[3])/2.0, 1) for c in valid_cells))
y_clusters = []  # merge y-values within 10pt

# Cluster x-midpoints into columns
x_mids = sorted(set(round((c[0]+c[2])/2.0, 1) for c in valid_cells))
x_clusters = []  # merge x-values within 10pt

# Assign each cell to (row, col) by closest cluster
for c in valid_cells:
    ri = closest(cy, y_clusters)
    ci = closest(cx, x_clusters)
    cell_grid[ri][ci] = c
```

This produces the correct grid regardless of how find_tables() orders its cells.

#### 3. Label transposition (table.py, `_maybe_transpose_label_table`)

Some tables have "Before"/"After" labels in column 0 as row labels, but they should be column headers. The function:
- Scans column 0 for short non-monospace labels (1-3 words)
- If 2+ labels found, transposes the table so labels become column headers
- Content between labels is collected into data cells per label group

Only fires when the grid structure actually has labels in column 0. With correct spatial clustering, the grid already has Before/After in the header row, so transposition rarely activates.

#### 4. Cross-page table continuation (table.py)

Tables near the page bottom (`bbox.y1 > 650`) get continuation content from the next page:
- Only monospace (code) blocks from the top of the next page qualify
- Stops at the first non-monospace block (heading, caption, body text)
- Creates a **new row** for cross-page content (not merged into last existing row)
- Left/right column assignment based on x-position relative to table midpoint

#### 5. HTML table rendering with embedded CSS (emit.py)

Multi-line code cells cannot use pipe tables. HTML tables with `<pre>` blocks render correctly:

```html
<table border="1" rules="all" cellpadding="6" cellspacing="0">
<tr><th>Before</th><th>After</th></tr>
<tr>
  <td><pre>struct A { ... };</pre></td>
  <td><pre>move_only_function<void() const> f = ...</pre></td>
</tr>
</table>
```

**Border rendering problem**: Cursor/VS Code markdown preview strips inline `style` attributes AND native HTML attributes (`border`, `rules`). Solution: inject a `<style>` block after the YAML front matter, only when the document contains HTML tables:

```html
<style>
table, th, td { border: 1px solid #999; border-collapse: collapse; padding: 6px 10px; }
th { background: #f5f5f5; }
</style>
```

VS Code markdown preview honours embedded `<style>` tags.

#### 6. Overlap filtering (table.py, `_filter_overlapping_mupdf_tables`)

Prevents find_tables() from re-detecting regions already handled by earlier passes. Compares y-ranges between existing table sections and find_tables() bboxes.

### Removed Code

All ruling-line detection and geometric table detection code removed (~700 lines):
- `extract_table_ruling_rects`, `_merge_overlapping_rects`, `_block_in_ruling_rect`
- `_detect_geometric_tables` and all helpers (`_y_overlap`, `_line_column`, etc.)
- Related constants (`_GEO_*`)

table_analyzer.py classification + strategy mapping integrated directly into table.py via `_classify_and_annotate()`.

### Results (p2034r6)

| Feature | Original PDF | Before fix | After fix |
|---------|-------------|-----------|----------|
| Feature 1 (Mutable Capture) | 4 data rows, Before/After headers, cross-page | Not detected as table | 4 data rows + 1 cross-page row, correct headers, borders visible |
| Feature 2 (Const Capture) | 4 data rows, Before/After headers | Not detected | 4 data rows, correct headers |
| Feature 3 (Value) | 2 data rows, Before/After headers | Not detected | 2 data rows, correct headers |
| Feature 5 (Const Context) | 2 data rows, Before/After headers | Not detected | 2 data rows, correct headers |

### Test Status

- 8 golden tests passing
- Golden files regenerated: p0533r9, p0957r8, p1112r4, p3556r0
- No regressions

### Bugs Solved in This Phase

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| Tables not detected | Pass 1-3 missed Tony Tables with MuPDF block structure | Added Pass 4 with find_tables() |
| All content in one row | find_tables() cell ordering assumed row-major, was column-major | Spatial clustering by y/x position |
| Before/After as row labels | Grid had labels in col 0, not as column headers | `_maybe_transpose_label_table` |
| Cross-page content missing | find_tables() is per-page, no continuation | Cross-page monospace block absorption |
| Cross-page in wrong row | Content merged into last existing row | Creates new row for continuation blocks |
| No borders in rendered markdown | VS Code strips style attrs and HTML attrs | Embedded `<style>` block |
| Multi-line code flattened | Pipe tables cannot have multi-line cells | HTML `<table>` with `<pre>` blocks |

### Phase 6: p4012r0 Tony Table Fix (2026-05-20)

#### Problem

p4012r0 Tony Tables (pages 3 and 5) were detected by Pass 2 (side-by-side) instead of Pass 4 (MuPDF native), producing 3 columns instead of 2. The caption "TonyBefore/After Table 1: Effect of this paper" (at x=194, outside the table bbox) introduced a phantom 3rd x-cluster alongside the code blocks (x=98, x=312).

#### Fixes Applied

**Fix 1: Pass 2 column-count guard** (`table.py`, `_detect_side_by_side_tables`):
When body x-clusters produce more columns than the header block declares, the table is rejected. The caption at a third x-position no longer inflates the column count. Pass 4 (MuPDF native) handles the table correctly as 2x2.

**Fix 2: Normalized distance for line-to-cell mapping** (`table.py`, `_detect_mupdf_native_tables`):
When mapping lines to cells, distance is now normalized by cell dimensions (`dx/cell_width + dy/cell_height`). This prevents thin separator cells (3pt height) from absorbing lines at the boundary of adjacent large content cells. A line at the edge of a 132pt content cell no longer maps to the tiny 3pt separator cell next to it.

#### Results

| Paper | Before | After |
|-------|--------|-------|
| p4012r0 Table 1 (page 3) | 3x3, phantom column, caption absorbed | 2x2, correct "before"/"with P4012R0" headers |
| p4012r0 Table 2 (page 5) | 6x3, broken layout | 2x2, correct headers and code content |
| p2034r6 (all Tony Tables) | Working | Still working (no regression) |

#### Golden file updates

p0957r8 and p1112r4 golden files regenerated: the normalized distance scoring improved cell mapping (phantom 4th column removed in p0957r8, "algorytm" correctly placed in header in p1112r4). All 8 golden tests pass.

---

### Known Issue: Clean Matrix with Control-Character Symbols

**Paper**: p4012r0, Section 7 "DIFFERENCES" table (page 9)

**Table family**: Clean Matrix (Format 1) - detected by Pass 1 (Inline-Column)

**Observed problems**:
1. **Missing symbols**: The PDF uses Unicode control characters for checkmarks: U+0014 (✔, DEVICE CONTROL FOUR) and U+0018 (✘, CANCEL). MuPDF extracts these literally, but they are non-printable and render as empty cells in Markdown.
2. **Detached header**: The header block B4 ("status quo Section 6.3") has only 2 lines/columns, while body blocks B5-B8 have 3 lines/columns each. Pass 1 header detection requires matching column count, so B4 is not absorbed as a header row. It appears as loose text above the pipe table.

**Current output**:
```
status quo Section 6.3

| `convertible_to<int, V>` | `false` | `true` |
| --- | --- | --- |
| `common_type_t<V, int>` | `` | `V` |
| `x = 1;` | `` | `` |
| `x = V(n);` | `` | `` |
```

**Expected output** (from PDF):
```
| | status quo | Section 6.3 |
| --- | --- | --- |
| convertible_to<int, V> | false | true |
| common_type_t<V, int> | ✘ | V |
| x = 1; | ✘ | ✔ |
| x = V(n); | ✔ | ✘ |
```

**Root causes**:
- Control character rendering: requires a mapping table (U+0014→✔, U+0018→✘) either in the extraction layer or in emit.py
- Header column mismatch: Pass 1 `_detect_header_block` requires the header to have the same number of columns as the body, but this header has 2 labels spanning only 2 of 3 columns

**Priority**: Low. This is a pre-existing Pass 1 issue, not related to Tony Table (Pass 4) work. Only affects tables using non-standard PDF symbol encoding for checkmarks.

**Not related to**: Phase 5/6 Tony Table fixes. The Differences table uses a completely different detection path (Pass 1 Inline-Column) and rendering path (pipe table).

---

---

## Phase 7: p3844r3 TOC False-Positive Table Detection

**Paper**: p3844r3 (Restore simd::vec broadcast from int)

**Problem**: TOC (Table of Contents) entries on pages 0-1 were rendered as pipe tables in the Markdown body. The rendered output showed bordered table rows for section numbers like "10.2 Modify [simd.expos] . . . 13" instead of omitting them entirely.

**Root cause analysis**:

TOC entries in this PDF have 3 lines per MuPDF block, all at the same y-position:
- Line 0: section number (e.g. "10.2") at x~91
- Line 1: title + dot-leaders (e.g. "Modify [simd.expos] . . . . .") at x~119
- Line 2: page number (e.g. "13") at x~512

Pass 3 (Horizontal-Row) detects blocks with 3+ lines at identical y as table rows. Consecutive blocks with the same column count form a table. TOC entries perfectly match this pattern.

The existing TOC removal system (`find_toc_indices` + label-anchored fallback) runs AFTER table detection. When horizontal-row converts TOC blocks into TABLE sections, two things break:
1. The TABLE section text contains pipe characters (`| 10.2 | Modify [simd.expos] . . . | 13 |`), which confuses `_normalize_toc_entry` heading matching
2. The initial `find_toc_indices` run covers page 0 (12 entries) but the page-1 continuation ("Contents" label + entries 10.x-11.x) exceeds `_MAX_GAP` and is missed
3. The label-anchored fallback only ran when `toc_indices` was empty, not as an extension

**Fix** (2 changes in `pipeline.py`):

1. **Dot-leader TABLE demotion** (before `find_toc_indices`): TABLE sections whose text contains dot-leaders (`has_dot_leader`) are demoted back to PARAGRAPH. This restores the text format that TOC detection expects, allowing heading matching and dot-leader detection to work correctly.

```python
for sec in sections:
    if sec.kind == SectionKind.TABLE and has_dot_leader(sec.text):
        sec.kind = SectionKind.PARAGRAPH
        sec.table_kind = None
        sec.table_strategy = None
        sec.columns = None
```

2. **Label-anchored TOC extension** (existing fallback generalized): The label-anchored TOC detection now runs even when `toc_indices` already has entries. It scans for remaining "Contents" labels not yet in `toc_indices` and extends the set with subsequent numbered/dot-leader entries. This catches multi-page TOC continuations (e.g. p3844r3 has "Contents" on page 1 continuing the TOC from page 0).

**Result**: All TOC entries (both pages) are correctly identified and removed. Body starts cleanly with `## ABSTRACT` → `## 1 CHANGELOG`. Zero dot-leader remnants in output. All 8 golden tests pass without regression.

---

### Next Steps

With p2034r6, p4012r0, p3844r3, and p4088r0 working correctly, all phases are validated. Remaining:
- **Space-aligned table detection**: p4016r0 has 2 space-aligned tables in the entire 124-PDF corpus. Low priority, deferred.
- **Broader corpus validation**: Run the 44 partial-row hits through the pipeline to verify improved output across all affected papers.

---

## Phase 8: Docling ML Cell Enrichment -- DONE (2026-05-21)

**Status**: Structurally complete. Enrichment functionally inert pending BBox coordinate fix (Phase 9).
**Checkpoint**: commit `5d0e4df` (rollback point for pipeline.py)

### Problem

Rule-based table detection (Passes 1-4) cannot reliably detect multi-line cell boundaries. When a cell wraps across visual lines, the detection may split it into separate rows. Quality scoring cannot catch this because the result looks structurally valid (consistent column count, no empty cells). This affects Format 8 (API Spec, "VERY BROKEN") and complex Format 5 (Tony Tables) most severely.

### Solution: Cell Enrichment (Docling-Grid + PyMuPDF-Spans)

**Docling** (MIT, IBM Research) provides ML-based table structure detection via TableFormer. It correctly identifies cell boundaries including multi-line cells and merged cells. However, Docling returns plain text without font metadata (no bold/italic/monospace).

**Core idea**: tomd's rule-based 4-Pass system remains the **master** for table detection AND positioning. Docling runs separately and only **enriches** the cell content of already-detected tables. This avoids all the positioning, deduplication, and text-loss problems that the earlier "page triage" approach caused.

### Architecture Pivot: Why Cell Enrichment, Not Page Triage

The initial approach ("Seiten-Triage", inspired by OpenDataLoader) attempted to route entire pages to Docling for table detection and insert Docling-detected tables as new Section objects. This failed due to three compounding problems:

1. **`exclude_table_regions` too aggressive**: The function removes blocks by y-midpoint without x-axis checks. Docling's synthetic table BBoxes covered wide y-ranges, causing surrounding headings, bullet lists, and paragraph text to be deleted.

2. **Docling's own positioning bugs**: Docling's `export_to_markdown()` has known table-placement issues. Its internal `body` tree provides reading order, but was not being used. Tables appeared at wrong document positions (e.g. 9.4 table under 9.5).

3. **Fragile deduplication**: Both rule-based and Docling detectors could find the same table. BBox-based dedup was unreliable (different coordinate precision), and text-based dedup (word overlap in headers) added complexity without eliminating all duplicates.

The Cell Enrichment approach eliminates all three problems by keeping rule-based detection as the single source of truth for what tables exist and where they sit.

### Implementation

#### Files Changed

| File | Change |
| --- | --- |
| `packages/tomd/src/tomd/lib/pdf/docling_backend.py` | Rewritten: `enrich_tables_with_docling()` replaces `build_table_sections()`. Retained: `extract_docling_tables()`, `_collect_spans_for_cell()`, `_flat_spans_for_page()`, `_normalize_bbox()`, `docling_available()` |
| `packages/tomd/src/tomd/lib/pdf/pipeline.py` | Added import of docling_backend functions. Added `ml_tables: bool = False` to `_run_pipeline()` and `convert_pdf()`. Added enrichment hook after `detect_tables()` |
| `packages/tomd/src/tomd/lib/pdf/types.py` | `table_source: str \| None = None` field on Section (added in earlier phase, retained) |

#### `enrich_tables_with_docling()` Algorithm

```
For each rule-based TABLE section:
  1. Find Docling tables on the same page
  2. Match by y-range IoU (intersection / union of vertical extent)
  3. If IoU >= 0.3: candidate match found
  4. Build Docling cell grid (num_rows x num_cols)
  5. For each cell: collect PyMuPDF spans within cell BBox
     - Sort by reading order (y, x)
     - Insert \n sentinel Spans between visual lines (y-gap > 3pt)
  6. Coverage check: if < 30% of cells have matching spans, SKIP
     (BBox coordinate mismatch protection)
  7. Re-classify with _classify_and_annotate() using new grid
  8. Replace section.columns, table_kind, table_strategy
  9. Set section.table_source = "docling"
```

**What is NOT changed**: section.kind, section.page_num, section.lines, section.text, insertion position in the document. The rule-based system's detection and positioning are preserved exactly.

#### Pipeline Hook

```python
# After detect_tables() and exclude_table_regions():
if ml_tables and table_sections and _docling_available():
    docling_tables = _extract_docling_tables(path)
    if docling_tables:
        n = _enrich_tables_with_docling(
            table_sections, docling_tables, all_mupdf_blocks)
```

Guarded by three conditions: `ml_tables=True` (opt-in), table sections exist, and Docling is installed.

#### Safety Guards

| Guard | Threshold | Purpose |
| --- | --- | --- |
| `_MATCH_Y_IOU_THRESHOLD` | 0.3 | Prevents matching unrelated tables on the same page |
| `_MIN_CELL_COVERAGE` | 0.3 | Rejects enrichment when BBox coordinate systems don't align (spans miss cells) |
| `docling_available()` | boolean | Graceful degradation when Docling not installed |
| `ml_tables` parameter | False default | Enrichment is opt-in, zero impact on default pipeline |

### Phase 0 Results (2026-05-20)

- **BBox compatibility (table-level)**: GO. Docling table-level BBoxes and PyMuPDF span origins use compatible coordinate systems. Verified with p4003r1.pdf.
- **Cell boundary quality**: GO. Docling found 11 tables in p4003r1 with correct multi-line cell detection.
- **Installation**: `docling` v2.94.0 via `uv pip install docling`. CPU-only, ~300-500MB models.
- **Note**: `docling-slim[tableformer]` extra does NOT exist. Full `docling` package needed for `DocumentConverter`.

### Runtime Verification (2026-05-21)

p4003r1 with `ml_tables=True`:

| Metric | Value |
| --- | --- |
| Docling tables found | 11 (across 10 pages) |
| Rule-based tables matched | 2 (pages 54 and 56) |
| Enrichment accepted | 0 (coverage guard rejected both) |
| Page 54 coverage | 2/18 cells (11%) -- below 30% threshold |
| Page 56 coverage | 7/27 cells (26%) -- below 30% threshold |
| Output vs baseline | **Byte-identical** (150544 chars, 2766 lines) |
| Headings preserved | All (9.3, 9.4, 9.5 present in both) |
| Tests | 760 passed, 7 skipped, 0 failed |

The coverage guard is working as designed: it prevents degraded output when cell-level BBox coordinates don't align. The enrichment infrastructure is structurally complete but functionally inert until the coordinate mismatch is resolved (Phase 9).

### Remaining Work

- **Phase 9**: BBox coordinate diagnostic and fix (see below)
- **CLI integration**: Wire `ml_tables` through `api.py` and CLI `--ml-tables` flag (blocked on Phase 9)
- **Batch preprocessing**: `paperflow docling-cache` for offline table extraction (deferred)

---

## Phase 9: BBox Coordinate Diagnostic (Planned)

**Status**: Not started
**Blocking**: Phase 8 enrichment is structurally complete but functionally inert. Without fixing cell-level BBox alignment, `_collect_spans_for_cell()` cannot populate Docling cells with PyMuPDF spans.

### Problem

Docling found 11 tables in p4003r1. Rule-based detection found 2 tables on pages 54 and 56. The IoU matching succeeded (table-level BBoxes overlap), but `_collect_spans_for_cell()` only populated 11% and 26% of cells respectively. PyMuPDF span origins do NOT fall inside Docling's cell-level BBoxes for most cells.

### Root Cause Analysis

Three possible causes, in order of likelihood:

**Cause A: Coordinate origin mismatch (MOST LIKELY)**
- Docling's TableFormer operates on a cropped table image at 72dpi. Cell BBoxes from the model may be in **image-pixel coordinates relative to the crop**, not in PDF-point coordinates.
- PyMuPDF span origins are in **PDF-point coordinates** (72 points/inch, top-left origin).
- Docling's `prov[0].bbox` (table-level) may be in PDF coordinates, but `cell.bbox` values from `TableCellData` may be in a different coordinate space (the cropped region).
- Phase 0 verified TABLE-LEVEL bbox compatibility but did NOT verify CELL-LEVEL bboxes.

**Cause B: Y-axis inversion (POSSIBLE)**
- PDF native coordinate system is bottom-left origin (y increases upward).
- PyMuPDF normalizes to top-left origin (y increases downward).
- Docling's `BoundingBox` has `.l`, `.t`, `.r`, `.b` fields, but `.t` and `.b` semantics may vary between table-level and cell-level bboxes.
- The existing `_normalize_bbox()` swaps y0/y1 if inverted, but only for table-level bboxes.

**Cause C: Tolerance too tight (UNLIKELY as sole cause)**
- `_BBOX_TOLERANCE = 2.0` points is tight but should work for same-coordinate-system data.
- 11% coverage (2/18 cells) is too low for a tolerance problem alone. A tolerance issue would give 60-80% coverage with a few edge misses, not 11%.

### Diagnostic Approach

Write a temporary script that dumps both Docling cell BBoxes AND PyMuPDF span origins for one specific table on page 54 or 56 of p4003r1.pdf. Compare the actual coordinate values:

- If Docling cell x/y values are in range 0-448 (image pixels): **Cause A** confirmed. Need affine transform from crop-image-space to PDF-point-space using page height and table crop offset.
- If Docling cell y values are inverted (y_top > y_bottom): **Cause B** confirmed. Need y-flip per cell in `_collect_spans_for_cell`.
- If values are close but off by 2-5pt: **Cause C** confirmed. Increase `_BBOX_TOLERANCE`.

### Fix Effort Estimate

| Scenario | Effort | Complexity |
| --- | --- | --- |
| Cause C only (tolerance) | 1 line change | Trivial |
| Cause B (y-flip) | 5-10 lines in `_collect_spans_for_cell` | Low |
| Cause A (coordinate transform) | 20-40 lines, needs Docling's page-height + crop-offset data | Medium |
| Cause A + B combined | 30-50 lines | Medium |

### Risk Assessment

**Zero regression risk**: The `_MIN_CELL_COVERAGE` safety guard (30%) ensures that incorrect coordinate transforms produce a coverage-check failure, not corrupted output. The enrichment is simply skipped and the rule-based table is preserved unchanged.

### Verdict

Targeted, low-risk diagnostic task. Estimated 30-60 minutes. The diagnostic script immediately reveals which fix to apply. Worth doing as the next step because without it, the entire Docling integration (Phase 8) has no observable effect on output quality.

---

## Phase 10: Borderless Column-Aligned Table Detection (Pass 5) -- DONE (2026-05-21)

### Problem

Docling's TableFormer ML model fails to detect borderless tables with mixed content (e.g. the Prediction Registry in P4003R1, Section 9.7). These are tables where columns are defined purely by consistent x-position alignment across rows, with no PDF ruling lines or structural cell boundaries.

### Solution: tomd Pass 5 (Geometric Column Grouping)

A new rule-based detection pass in `table.py` that detects borderless tables by analyzing x-position clustering across y-bands. This is a **tomd-only** solution, no Docling involved. Docling enrichment (Phase 8) remains available as a separate opt-in layer for tables that ARE detected.

### Architecture

```
PDF -> MuPDF blocks
  -> Pass 1 (Inline-Column)
  -> Pass 2 (Side-by-Side)
  -> Pass 3 (Horizontal-Row)
  -> Pass 4 (MuPDF Native find_tables)
  -> Pass 5 (Column-Aligned Geometric) [NEW]
  -> classified TABLE sections
```

Pass 5 runs last, only on blocks not consumed by earlier passes. It uses the `two_column_pages` set (detected in `pipeline.py` from raw blocks before any stripping) to skip newspaper-layout pages.

### Algorithm (`_detect_column_aligned_tables`)

1. **Y-band bucketing**: For each page, bucket every line into y-bands by vertical midpoint. Collect distinct x-position keys per band (using `line.bbox[0]`, not span-level).
2. **Multi-column band detection**: Find y-bands with >= 4 distinct x-columns (`_GEO_MIN_COLS_PER_BAND`).
3. **Contiguous runs**: Group consecutive multi-column bands (gap <= 8 bands, `_GEO_MAX_BAND_GAP`). Require >= 3 bands per run (`_GEO_MIN_TABLE_BANDS`).
4. **Stable column extraction**: Only x-positions recurring across >= `_MIN_SHARED_YBANDS` bands qualify. Merge nearby positions within 25pt (`_GEO_MERGE_THRESHOLD`). Cap at 8 columns (`_GEO_MAX_COLS`).
5. **Trailing continuation**: Extend the y-band range beyond the last multi-column band to capture continuation lines (cells that wrap to a new line with fewer filled columns).
6. **Visual rows**: Assign lines to columns by nearest x-position. Build one visual row per y-band.
7. **Logical rows**: Merge visual rows using col-0-non-empty heuristic (new row starts when leftmost column has content; continuation lines merge into current row with `\n` separators).
8. **Header-split guard**: If `logical_rows[0]` has cells with `\n` separators where the pre-`\n` text is short (<=5 words per cell), split into a clean header row and a data spillover that merges into the next row.
9. **Guards**: Monospace ratio < 50%, bullet-list rejection, cross-column merge guard (empty cell ratio check for two-column-page false positives).
10. **Cross-page continuation**: When consecutive tables on adjacent pages have identical header rows, the duplicate header is stripped from the continuation table (`table_continuation=True`).
11. **Emit-phase fold**: In `emit.py`, continuation tables are folded into the preceding table's `columns` list before rendering, producing a single HTML `<table>`.

### Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `_GEO_MIN_COLS_PER_BAND` | 4 | Min distinct x-columns per y-band |
| `_GEO_MAX_COLS` | 8 | Max columns allowed |
| `_GEO_MIN_TABLE_BANDS` | 3 | Min multi-column bands for a table |
| `_GEO_MAX_BAND_GAP` | 8 | Max gap between consecutive multi-column bands |
| `_GEO_MAX_MONO_RATIO` | 0.50 | Max monospace fraction (filters code blocks) |
| `_GEO_MERGE_THRESHOLD` | 25.0 | Merge x-positions closer than this (pt) |
| `_HEADER_MAX_WORDS` | 5 | Max words per header cell for split heuristic |

### Files Changed

| File | Change |
| --- | --- |
| `table.py` | `_detect_column_aligned_tables()` (~300 lines), hooked into `detect_tables()` as Pass 5, `two_column_pages` parameter |
| `pipeline.py` | `two_column_pages` detection from raw blocks via `_detect_column_split()`, passed to `detect_tables()` |
| `emit.py` | Cross-page continuation fold in `emit_markdown()`, `table_continuation` handling in `_render_html_table()` and pipe-table renderer |
| `types.py` | `table_continuation: bool = False` field on Section |

### Validation: P4003R1 Prediction Registry

| Aspect | Before | After |
|--------|--------|-------|
| Detection | Not detected (borderless, Docling ML miss) | Detected as 4-column table |
| Pages | Split across pages 48-49 | Merged into single table |
| Header | Corrupted (data merged into header cells) | Clean: `#`, `Prediction`, `Criterion`, `Revisit` |
| Rows | 4 rows (page 1 only) | 6 rows (both pages merged) |
| Row 6 content | Truncated (continuation line lost) | Complete: "protocol within five years" / "declare IoAwaitable conformance" |

Also detected: p4003r1 benchmark table on page 7 (Platform/Frame Allocator/Time/Speedup).

### Test Results

760 passed, 0 failed, 7 skipped. No golden file changes, no regressions.

### Iterative Bug Fixes During Development

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| Massive false positives (code, prose) | Span-level x-positions too noisy | Switched to line-level `line.bbox[0]`; added max-cols, monospace guards |
| Bullet list false positives (p0957r8) | Dashes at col-0 mimicked table structure | Column merging reduced noise; bullet-list guard |
| Two-column layout merge (p0533r9) | Content from separate newspaper columns merged | `two_column_pages` detection moved to `pipeline.py` using raw blocks |
| Header data contamination | First data line merged into header when col-0 empty | Header-split guard: detect `\n` in row-0 cells, split at boundary |
| Row 6 truncation | Trailing continuation line outside multi-column band range | Extended y-band range to capture trailing bands with subset of column positions |
| Cross-page table split | Per-page detection produced two tables | Cross-page continuation: strip duplicate header, fold in emit phase |
| Section ordering destroyed | Naive Section merge mixed y-positions from two pages | Reverted Section merge; header-strip + emit-fold approach preserves per-page positioning |

---

## Phase 11: SPEC_TABLE Row-Boundary Bleeding Fix -- DONE (2026-05-26)

### Problem

SPEC_TABLE rows (detected by `_detect_spec_tables_by_label`, Pass 0) had systematic assertion-text bleeding: each row's C2 (assertion) column lost its tail text to the next row. R1's end appeared at R2's start, R2's at R3's, etc. All 10 rows of Table 3 in P4003R1 were affected (R1-R6 cascading bleed, R7-R9 clean by coincidence).

### Root Cause

In WG21 spec tables, expression names (col0) are **vertically centered** within their cell, while assertion text (col2) starts at the **top** of each cell. MuPDF delivers text lines in y-order, so assertion text for a row appears in y-bands ABOVE the corresponding col0 entry.

The row-merging logic used a **deferred** mechanism: col0-empty y-bands with a later col0 on the same page were buffered and prepended to the next row. This was correct for y-bands ABOVE a col0 entry (they're the START of that row's assertion). But it also deferred y-bands BELOW the current col0 that were CONTINUATIONS of the current row, causing them to bleed into the next row.

**Example** (Page 56, Table 3):

| y-band | Content | Old behavior | Correct behavior |
|--------|---------|-------------|-----------------|
| yk=56007 (y=93) | col2 "Shall not exit..." | Deferred to R1 (correct) | Deferred to R1 |
| yk=56008 (y=110) | col0 "E u(x1);" | Start R1 | Start R1 |
| yk=56009 (y=127) | col2 "addressof(u.context())..." | Deferred to R2 (WRONG) | Append to R1 |
| yk=56011 (y=155) | col2 "Shall not exit..." | Deferred to R2 | Deferred to R2 |
| yk=56012 (y=172) | col0 "E u(mx1);" | Start R2 with R1's tail | Start R2 correctly |

### Fix: Y-Gap Analysis

Replaced the blanket `same_page` deferral with **y-gap analysis** using actual span bounding boxes. The key observation: within a table cell, consecutive lines are spaced ~7-9px apart. Between cells (row boundaries), the gap is ~18-19px. `_SPEC_TABLE_Y_BAND` (15.0) cleanly separates the two regimes.

**Algorithm**:

1. Track `prev_y_max` (bottom y-coordinate of previous y-band's spans)
2. Track `last_col0_page` (page of last processed col0)
3. Track `in_deferred_zone` (boolean, persists across y-bands)
4. For col0-empty y-bands:
   - If on a **new page** (no col0 yet): check for upcoming col0, enter deferred zone if found
   - If on **same page** as last col0: compute y-gap = `y_min_cur - prev_y_max`
     - Gap > `_SPEC_TABLE_Y_BAND` (~15px): **row boundary detected** -> enter deferred zone (if next col0 on same page)
     - Gap <= `_SPEC_TABLE_Y_BAND`: **intra-row continuation** -> append to current row
5. Col0 entry resets `in_deferred_zone` and flushes deferred buffer

**Why this works universally**: The inter-row gap (~18-19px) vs intra-row gap (~7-9px) ratio is ~2.3x, with `_SPEC_TABLE_Y_BAND` (15px) as a stable midpoint. This is a physical property of WG21 document formatting (line height vs cell padding), not specific to P4003R1.

### Files Changed

| File | Change |
| --- | --- |
| `table.py` | `_detect_spec_tables_by_label`: replaced `same_page` deferral logic with y-gap analysis (~30 lines changed in row-merge section) |

### Results (P4003R1 Table 3)

| Row | Expression | Before (C2 start) | After (C2 start) | Correct? |
|-----|-----------|-------------------|------------------|----------|
| R1 | E u(x1); | "Shall not exit..." (truncated at "and") | "Shall not exit... u == x1 and addressof(u.context())..." | Yes |
| R2 | E u(mx1); | "addressof(u.context())..." (R1's tail) | "Shall not exit... u equals the prior value of mx1..." | Yes |
| R3 | x1 == x2 | "equals the prior value..." (R2's tail) | "Returns: true only if x1 and x2 can be interchanged..." | Yes |
| R4 | x1 != x2 | "end note ] operator==..." (R3's tail) | "Same as !(x1 == x2)." | Yes |
| R5 | x1.context() | "Shall not exit... comparison operators..." (stray) | "Shall not exit... comparison operators and member functions..." | Yes |
| R6-R9 | ... | Mixed correct/wrong | All correct | Yes |

### Test Results

760 passed, 0 failed, 7 skipped. No golden file changes, no regressions.

### Cross-Page Behavior

The fix correctly handles cross-page tables (e.g. x1.post(c) on page 57). When a new page starts (`current_page != last_col0_page`), the deferred zone activates if a col0 exists on that page, prepending assertion text above the expression name. This was already working before but is now integrated into the unified y-gap mechanism.

## Phase 12: Pass 1 Multi-Orphan Lookahead -- DONE (2026-05-27)

### Problem

Pass 1 (Inline-Column) tables in P4003R3 (Section 6, "Why Not `exec::as_awaitable`?") were incomplete. The table has 4 data rows, but only rows 1-2 were extracted. Rows 3-4 were lost because MuPDF delivered their cells as multiple consecutive orphan blocks and subset-column blocks that the existing single-step lookahead could not handle.

### Root Cause

MuPDF fragments multi-line table cells into separate blocks. For this table:

```
B25: 3 lines [x0=72, 230, 395]  -> Row 2: full 3-column match
B26: 1 line  [x0=72]            -> Orphan: "Inline completion..."  (col 0 of Row 3)
B27: 1 line  [x0=230]           -> Orphan: "Yes - completes..."   (col 1 of Row 3)
B28: 2 lines [x0=230, 395]      -> Subset: col 1 + col 2          (Row 3 continued)
B29: 3 lines [x0=72, 230, 395]  -> Row 4: full 3-column match     (confirms table)
```

The existing Pass 1 orphan lookahead (`_is_column_aligned_orphan`) checked only `blocks[j+1]`. When B26 was the orphan and B27 was also an orphan (not a full-column match), the lookahead failed and the table run broke.

### Fix: Three-Branch Lookahead

Refactored the Pass 1 orphan-handling `elif` into three distinct branches:

1. **Single-orphan + full match**: `blocks[j]` is orphan, `blocks[j+1]` is full column match. Original behavior, no guards needed.

2. **Single-orphan + subset match**: `blocks[j]` is orphan, `blocks[j+1]` has `_is_subset_columns(cols, ref_cols)`. Triggers a forward scan (`scan = j + 2`) absorbing subsequent orphans and subsets until a full column match is found. Guards: `len(table_blocks) >= 2`, `scan - j < max_scan`.

3. **Multi-orphan**: `blocks[j]` is orphan, `blocks[j+1]` is also orphan. Triggers a forward scan (`scan = j`) absorbing consecutive orphans/subsets. Same guards.

### New Helper: `_is_subset_columns`

```python
def _is_subset_columns(cols, ref_cols, tol=_COLUMN_MATCH_TOLERANCE):
    """True when every x in cols is within tol of some x in ref_cols."""
```

Used instead of `_is_partial_row` for lookahead confirmation because it evaluates only x-positions, not y-gaps. MuPDF's non-y-sorted block output sometimes places the confirming block above the last absorbed orphan, causing negative y-gaps that `_is_partial_row` rejects.

### Y-Band Row Reconstruction

When multi-orphan absorption occurs (`multi_orphan_used = True`), the traditional sequential row-building (each block = one row) produces wrong results because absorbed blocks are interleaved in non-y-order. Instead:

1. Collect all lines from all table blocks
2. Sort by y-midpoint
3. Calculate adaptive `band_gap`: median of real gaps (filtered > 1.0px to exclude floating-point noise)
4. Group lines into rows by y-band proximity

This correctly reconstructs logical rows even when MuPDF delivers fragments out of order.

### Safety Guards

| Guard | Purpose |
|-------|---------|
| `len(table_blocks) >= 2` | Only activate for established table runs (header + 1 data row). Prevents false positives on isolated text blocks (fixed p0533r9 regression). |
| `max_scan = 3 * len(ref_cols)` | Caps forward scan distance. Prevents runaway absorption of unrelated content (fixed p0957r8 regression where assembly code listings were absorbed). |
| `band_gap > 1.0px` filter | Excludes floating-point y-midpoint noise from adaptive band calculation. Without this, band_gap collapsed to ~0.00006px, splitting single rows. |

### Files Changed

| File | Change |
| --- | --- |
| `table.py` | New function `_is_subset_columns` (~12 lines). Refactored Pass 1 orphan `elif` into three branches (~80 lines). Y-band row reconstruction when `multi_orphan_used` (~40 lines). |

### Results (P4003R3 Section 6)

| Row | Property | Returns awaitable | Returns sender | Correct? |
|-----|----------|-------------------|----------------|----------|
| R1 | Frame allocations | 1 | 1 | Yes |
| R2 | Per-operation allocation (under type erasure) | 0 (preallocated awaitable) | 1 (`op_state` heap-allocated per `connect`) | Yes |
| R3 | Inline completion (`await_ready`) | Yes - completes, no suspend | No - `start()` is post-suspend | Yes |
| R4 | Synchronous-complete overhead | 0 (symmetric transfer) | `connect`/`start` + trampoline | Yes |

### Regressions Found and Fixed During Development

| Regression | Root Cause | Fix |
|-----------|-----------|-----|
| p0533r9: two `constexpr` rows merged into one | Multi-orphan path activated on a 1-row table (header only), y-band grouping merged unrelated lines | Added `len(table_blocks) >= 2` guard |
| p0957r8: assembly code listings absorbed into table | Unbounded forward scan absorbed 20+ blocks of assembly code | Added `max_scan = 3 * len(ref_cols)` limit |
| P4003R3 incomplete after p0533r9 fix | `len(table_blocks) >= 2` blocked the multi-orphan path. The actual P4003R3 case was single-orphan + subset (B26 orphan, B28 subset), not multi-orphan | Split into three branches: single-orphan+full, single-orphan+subset, multi-orphan |
| Y-band too fine | Adaptive band_gap picked up 6e-5px floating-point noise between y_mids | Filter gaps < 1.0px from band_gap calculation |

### Test Results

794 passed, 0 failed. All 4 golden tests (p0533r9, p0957r8, p1112r4, p3556r0) unchanged. No regressions.

### Covers Format Type

Format 13 (Multi-Orphan Fragmented Tables). Also benefits any Pass 1 table where MuPDF delivers consecutive orphan/subset blocks for the same logical row.

---

## Phase 13: KEY_VALUE Table Family (Format 2)

### Problem

2-column "Field | Value" tables (e.g. platform schema tables in P4182R0) had continuation text from long col-1 values incorrectly concatenated with the NEXT row's key. Example: "unless a product or studio policy turns them off" was merged with "Hot-path allocation style" instead of being appended to the previous "Exceptions in typical shipping builds" row.

### Root Cause

MuPDF delivers each table row as a separate 2-line block. Long col-1 values overflow into separate single-line blocks at the col-1 x-position. Pass 1's single-orphan absorption path absorbed these blocks but used positional assignment (first line = col-0), causing the continuation text to appear in col-0 of a new row. The subsequent forward-orphan merge then concatenated it with the next row's key.

### Fix: TableKind.KEY_VALUE + partial_absorbed marking

1. **New enum**: `TableKind.KEY_VALUE` with `PIPE_TABLE` strategy.
2. **New signal**: `col0_max_words` in `_compute_table_signals` counts the max words in any col-0 cell.
3. **Classification rule**: 2 columns + `col0_max_words <= 8` + `max_word_count > 15` classifies as KEY_VALUE (before PROSE_TABLE fallback).
4. **Row-building fix**: In the single-orphan absorption path, non-monospace orphan blocks at col-1+ x-position in 2-column tables are marked as `partial_absorbed`. This routes them through x-position assignment and backward merge into the previous row.

### Safety Guards

| Guard | Purpose |
|-------|---------|
| `len(ref_cols) == 2` | Only 2-column tables. Protects P4003R1 (3-column table with col-2 orphan "(kqueue)"). |
| `not is_mono` | Only prose continuations. Protects p0957r8 CODE_COMPARISON tables with monospace continuation blocks (`constraint_level::trivial`). |
| Classification before PROSE_TABLE | KEY_VALUE is a sub-category of PROSE_TABLE; the rule fires only when all three conditions hold. |

### Discovery Scan

8 KEY_VALUE tables across 3 papers:
- p4182r0: 6 tables (20 continuation blocks fixed)
- p4088r0: 1 table
- p4098r0: 1 table

### Files Changed

| File | Change |
| --- | --- |
| `table.py` | `TableKind.KEY_VALUE` enum + `_STRATEGY_MAP` entry. `_KV_COL0_MAX_WORDS = 8` constant. `col0_max_words` signal in `_compute_table_signals`. KEY_VALUE rule in `_classify_table`. `partial_absorbed` marking in single-orphan path (~20 lines). Module docstring updated with KEY_VALUE family. |

### Results (P4182R0)

All 11 key-value tables now extract correctly. Continuation text is properly merged into the previous row's col-1 cell.

### Regression Check

| Paper | Result |
|-------|--------|
| P4003R1 | Zero table regression (only diff: unrelated mermaid diagram improvement) |
| p0957r8 | Golden test passes (monospace guard protects CODE_COMPARISON) |
| Full suite | 806 passed, 7 skipped (identical to baseline) |

### Covers Format Type

Format 2 (Key-Value Pairs). 2-column tables with short field labels and long descriptive values.

---

## Phase 14: KEY_VALUE Header Loss + Multi-Line Value Split

Two bugs discovered during manual review of regenerated P4182R0 markdown.

### Bug 1: "Field | Value" Header Stripped as Repeating Page Header

**Problem**: The "Field | Value" header row was missing from all platform tables (3.2-3.8) but present in some compiler tables (4.4 MSVC, 4.5 Arm).

**Root Cause**: `get_edge_items()` in `cleanup.py` collected lines from columnar blocks (table column headers) as page edge items. "Field" and "Value" appeared at y=94.8 (near page top) on 13 of 17 pages. `detect_repeating()` classified them as repeating page headers (76% > 50% threshold). `strip_repeating()` removed them BEFORE `detect_tables()` ran. Tables where "Field\nValue" started mid-page (MSVC at y=535.9, Arm at y=217.1) were unaffected because those positions weren't in the edge zone.

**Fix**: Added columnar block guard in `get_edge_items()` (`cleanup.py`). Blocks with 2+ lines whose x0-positions differ by >50 units are table column headers, not page headers. These blocks are skipped during edge item collection.

**File**: `cleanup.py` (5 lines added to `get_edge_items()`)

### Bug 2: Multi-Line Values Split Into Separate Rows (Section 3.5)

**Problem**: Section 3.5 Full RTOS had multi-line values (e.g. "Hosted `<memory_resource>`" with 3 continuation blocks) that rendered as separate table rows with empty Field cells.

**Root Cause**: 3+ consecutive orphan blocks triggered `multi_orphan_used = True`, which activated y-band grouping instead of sequential `partial_absorbed` processing. The adaptive `band_gap` (17.1) was too small for the varying intra-cell line spacing (15.7-21.3 units), splitting continuation lines into separate y-bands (= separate rows). Sections 3.2-3.4 were unaffected because their values fit in single lines (no multi-orphan trigger).

**Fix**: Added backward-merge pass after y-band grouping for 2-column tables (`table.py`). Rows where col-0 is empty and col-1 has text are merged into the previous row. An empty key always means value continuation in KEY_VALUE tables.

**File**: `table.py` (~15 lines added after y-band grouping loop)

### Results

| Paper | Result |
|-------|--------|
| P4182R0 | "Field \| Value" header in all 13 tables. Section 3.5 multi-line values correctly merged (16→11 rows). |
| P4003R1 | IDENTICAL output -- zero regression |
| Full suite | 806 passed, 7 skipped (identical to baseline) |

---

## Phase 15: CLEAN_MATRIX Side-by-Side Column Misassignment

### Audit Results

Full scan of all 597 CLEAN_MATRIX tables across 124 PDFs:

| Status | Count | Percentage |
|--------|-------|------------|
| OK | 593 | 99.3% |
| BROKEN | 4 | 0.7% |

Broken tables (multi-column block misassignment):

| Paper | Page | Dimensions | Broken Rows | Description |
|-------|------|------------|-------------|-------------|
| p4090r0 | 10 | 3x5 | 1 | Partial write preserved row mashed |
| p4096r0 | 10 | 4x3 | 1 | Property/Coroutine executor mashed |
| p4100r0 | 2 | 3x3 | 1 | Library/Role/Status mashed |
| p4182r0 | 11 | 4x6 | 3 | Compiler schema: GCC/Clang/MSVC rows all broken |

593 of 597 tables (99.3%) are unaffected. The fix only changes behavior for blocks whose lines map to different columns.

### Problem

MuPDF delivers partial-column blocks (e.g. B[259] with 3 lines at x0=66.7, 149.9, 242.7 representing 3 different columns). The side-by-side code uses `_nearest_column(blk.bbox[0], col_xs)` to assign ALL lines to the BLOCK's column (col 0), ignoring that individual lines belong to different columns.

### Root Cause

`table.py` lines 432-442, the row-building loop in `_detect_side_by_side_tables`:

```python
for _, blk in row:
    ci = _nearest_column(blk.bbox[0], col_xs)  # BUG: block-level
    for ln in blk.lines:
        col_spans[ci].append(...)  # all lines go to same column
```

### Table Family

`CLEAN_MATRIX`, processed by side-by-side path (Pass 2). Not related to Pass 1 where KEY_VALUE fixes apply. Completely separate code path from P4003R1.

### Fix

Per-line column assignment with single-column block guard:

```python
for _, blk in row:
    line_cols = [_nearest_column(ln.bbox[0], col_xs) for ln in blk.lines]
    multi_col = len(set(line_cols)) > 1
    blk_ci = _nearest_column(blk.bbox[0], col_xs)
    for ln, lc in zip(blk.lines, line_cols):
        ci = lc if multi_col else blk_ci  # per-line only when lines span columns
        ...
```

Two-tier logic: first check if the block's lines map to different columns (`multi_col`). If yes (lines span multiple table columns), use per-line assignment. If no (all lines in same column, e.g. indented code), use block-level assignment (preserving old behavior).

**File**: `table.py`, `_detect_side_by_side_tables` row-building loop

**Safety**: For single-column blocks (593/597 tables), `multi_col` is False and behavior is byte-identical to the old code. For multi-column blocks (4 tables), each line now routes to its correct column.

**Golden update**: `p0957r8.golden.md` updated to reflect per-line column assignment in its code comparison tables. The new output is more consistent: x86 and ARM tables already had split "Library side" / code lines, RISC-V now matches.

### Results

| Paper | Result |
|-------|--------|
| P4182R0 | Section 4.1 Compiler schema: 6 columns correctly distributed (GCC/Clang/MSVC) |
| P4090R0 | Page 10: 6-col and 5-col tables now correct |
| P4096R0 | Page 10: 3-col Property/Coroutine/execution::task correct |
| P4100R0 | Page 2: 3-col Library/Role/Status correct |
| P4003R1 | IDENTICAL output -- zero regression |
| Full suite | 806 passed, 7 skipped (identical to baseline) |

### Regression Guard

P4003R1 tables use Pass 1 (not side-by-side). Zero risk. Verified with regeneration.

### Files Changed

- `table.py`: 6 lines changed in `_detect_side_by_side_tables` row-building loop
- `p0957r8.golden.md`: Updated to match new (more consistent) per-line output

---

## Phase 15b: CLEAN_MATRIX Row-Merge for Atomized Blocks

### Problem

After Phase 15 fixed column assignment, P4182R0 Section 4.1 still showed Arm/NVIDIA/EDG rows split into multiple rows. MuPDF delivers each line of a multi-line cell as a separate single-line block (atomized blocks), and the row-grouping logic in `_detect_side_by_side_tables` incorrectly starts a new row for each col-0 block.

### Root Cause

Row-grouping at `table.py` lines 392-396:

```python
if col == 0:
    if has_col0:
        rows.append(current_row)  # new row on every col-0 block
```

For Arm GNU Toolchain, MuPDF produces 3 separate col-0 blocks:
- B[282] y0=325.8 y1=339.4 "Arm GNU" (whitespace gap from previous: ~15pt)
- B[283] y0=344.3 y1=357.9 "Toolchain" (gap from B[282] y1: **4.9pt** -- same cell)
- B[284] y0=362.8 y1=376.4 "(bare-metal)" (gap from B[283] y1: **4.9pt** -- same cell)

Next row: B[295] y0=391.3 "NVIDIA nvcc" (gap from B[284] y1: **14.9pt** -- new row)

Intra-cell whitespace: ~5pt. Inter-row whitespace: ~15pt.

### Fix

Two changes to `_detect_side_by_side_tables` row-grouping:

1. **Y-band proximity** (`_SBS_ROW_Y_BAND = 10.0`): Track the y1 (bottom) of the last col-0 block. A new row only starts when the whitespace gap (`blk.y0 - last_col0_y1`) exceeds 10pt. Atomized blocks within the band are merged into the current row.

2. **Page-boundary guard**: Track the page of the last col-0 block. A page change always forces a new row, preventing cross-page y-coordinate reset from merging unrelated blocks.

```python
if col == 0:
    new_page = blk.page_num != last_col0_page and last_col0_page >= 0
    gap_exceeds = blk.bbox[1] - last_col0_y1 > _SBS_ROW_Y_BAND
    if has_col0 and (new_page or gap_exceeds):
        rows.append(current_row)
        current_row = [(idx, blk)]
    else:
        current_row.append((idx, blk))
    last_col0_y1 = blk.bbox[3]
    last_col0_page = blk.page_num
```

**Safety**: The 10pt band is well below inter-row gaps (~15pt) and well above intra-cell gaps (~5pt). For the 593 OK tables with multi-line blocks (single MuPDF block per cell), no atomized col-0 blocks exist, so the check never fires.

**File**: `table.py`, `_detect_side_by_side_tables` row-grouping + new constant `_SBS_ROW_Y_BAND`

**Golden update**: `p0957r8.golden.md` regenerated (pre-existing Phase 15 mismatch, not caused by Phase 15b).

### Results

| Paper | Result |
|-------|--------|
| P4182R0 | Section 4.1: 7 correct rows (GCC, Clang, MSVC, Arm, NVIDIA, EDG) with multi-line cells merged. HTML table format. |
| P4003R1 | All 9 tables IDENTICAL -- zero regression |
| Full suite | 806 passed, 7 skipped (identical to baseline) |

### Regenerated Papers

All affected papers regenerated via DB-reset + `paperflow convert --force` (with `__pycache__` cleared).

| Paper | Chapter / Section | Table | Rows |
|-------|-------------------|-------|------|
| P4182R0 | 4.1 Compiler schema | 6-col compiler comparison | 7 |
| P4090R0 | (page 10) | 3-col | 3 |
| P4096R0 | 5.4 Summary | 3-col Property/Coroutine | 3 |
| P4100R0 | 2.1 What We Built | 3-col Library/Role/Status | 3 |
| P4100R0 | 2.1 What We Built | 5-col | 5 |
| P4100R0 | 2.2 Independent Adopters | 4-col | 4 |
| P4100R0 | 6. Three-Layer Architecture | 5-col | 5 |

### Regression Guard

P4003R1 tables use Pass 1 (not side-by-side). Zero risk. Verified: all 9 tables byte-identical.

---

## Phase 16: Atomized Header Recovery in Pass 2

**Date**: 2026-05-28

### Problem

P4090R0 Section 9 "The Trade-Off" table was completely broken: header columns rendered as paragraphs, data rows concatenated as prose. The table is a 6-column comparison spanning pages 10-11.

**Root cause**: The table header is atomized -- each column heading is a separate MuPDF Block instead of a single multi-column block. Pass 2's guard (`len(col_xs) > len(cols)` at `table.py:375`) correctly protects against false positives by rejecting when the body has more column positions than the header. But with atomized headers, the first header block only shows 2 columns while the body has 6, causing the guard to reject the entire table.

```
B[308] x0=66.7  y0=68.3 "Property/Just use"  <- _block_column_positions sees 2 cols
B[310] x0=251.3 y0=68.3 "Just split the..."  <- separate header block (same y)
B[312] x0=327.8 y0=68.3 "Just use..."        <- separate header block (same y)
B[314] x0=400.8 y0=68.3 "Just..."            <- separate header block (same y)
B[317] x0=474.5 y0=68.3 "Corosio"            <- separate header block (same y)
B[309] x0=177.5 y0=86.8 "set_value"          <- header continuation (below)
```

### Impact Scan

- 237 total guard rejects across all PDFs
- 34 fixable (atomized headers with recoverable neighbor blocks) across 9 PDFs
- 203 correctly rejected (guard works as intended)
- P4003R1 has 1 guard reject but recovery does NOT trigger (ext_xs=2 < col_xs=3)

### Fix

Extended Pass 2 (`_detect_side_by_side_tables`) with atomized-header recovery:

1. When the guard would reject (`col_xs > cols`), scan forward from the header block for all blocks within `_ATOMIZED_HDR_MAX_HEIGHT` (60pt) of the header's y0
2. Cluster x-positions of all collected blocks
3. If extended column count >= body column count, accept the table with a multi-block header
4. Exclude absorbed header blocks from body_candidates, reset h_bottom to header region bottom
5. Build header row by assigning each header block's spans to its nearest column

Additional: relaxed row validation for recovered headers -- sub-header rows (single-column, like "Data preservation") are skipped instead of terminating, with a cap of `_ATOMIZED_HDR_MAX_CONSEC_SINGLE` (3) consecutive single-column rows before stopping.

**New constants**: `_ATOMIZED_HDR_MAX_HEIGHT = 60.0`, `_ATOMIZED_HDR_MAX_CONSEC_SINGLE = 3`

**File**: `table.py`, `_detect_side_by_side_tables` guard + header building + row validation

### Results

| Paper | Result |
|-------|--------|
| P4090R0 | Section 9: 6-col table, 2 HTML tables (page boundary split at pg 10/11), 5+3 data rows |
| P4100R0 | 4 HTML tables detected (improved) |
| P4003R1 | 6 HTML tables, 17 pipe rows -- IDENTICAL, zero regression |
| Full suite | 806 passed, 7 skipped (identical to baseline) |

### Regenerated Papers

| Paper | Chapter / Section | Table | Rows |
|-------|-------------------|-------|------|
| P4090R0 | 9. The Trade-Off (page 10) | 6-col Property comparison | 1 hdr + 5 data |
| P4090R0 | 9. The Trade-Off (page 11) | 6-col Property comparison (continued) | 1 hdr + 3 data |

### Regression Guard

P4003R1: 1 guard reject exists but recovery correctly does NOT activate (extended header has 2 cols, body needs 3). Verified: output identical.

The 203 non-fixable guard rejects remain correctly rejected because their neighbor blocks do not produce enough extended columns to match body column count.

