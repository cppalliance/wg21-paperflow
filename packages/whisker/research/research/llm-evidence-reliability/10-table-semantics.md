# 10 - Table-Semantics Specialist

**Verdict:** usable-with-conditions — table-shaped missing-content quotes must bypass document-wide `ground_spans` and use grid-scoped candidate locate with an explicit `present | verified_missing | ambiguous` split; PDF-row→pipe-table reformats and duplicate cell tokens are `present` or `ambiguous`, never `verified_missing` on substring alone.
**Confidence:** high

## Findings

- [CRITICAL] **Document-wide candidate locate is structurally wrong for table quotes.** Evidence: bidirectional design reuses `ground_spans(spans, tomd_md)` on full markdown (`llm-evidence-reliability/03-bidirectional-design.md:40-42`); `normalized_text` deletes pipes, newlines, and punctuation (`metrics.py:118-126`), so a pipe table and a PDF-flattened row collapse to the same token bag. Impact: column swaps and duplicate cell values (PR #290: 0/5 false absences, dates present twice in `00-baseline.md:17-18`) will read as `present_in_candidate` even when grid semantics are wrong, or as `verified_missing` when the quote is a contiguous PDF row string that legitimately became `|`-delimited cells. **Policy:** route quotes through a table classifier before candidate locate; default prose path stays document-wide.

- [CRITICAL] **PDF text-layer rows ≠ Markdown table rows — source and candidate haystacks are asymmetric.** Evidence: tabula-java asserts 40 sequential cell texts in reading order (`tabula-java/TestBasicExtractor.java:225-282`); PDF judge grounds only against `normalize_textlayer` output (`pdf_judge.py:513-520`), not a grid. Candidate side already has `parse_pipe_tables` + `parse_html_tables` returning `list[list[str]]` (`tables.py:50-141`). Impact: a judge quote like `"Project Agency Institution"` may source-ground in flattened PDF text but fail substring match in markdown even when every cell exists in a pipe grid. **Policy:** after source-grounding, candidate locate for table-shaped quotes must (1) parse markdown grids, (2) try row-join match (`" ".join(row)` and `"|".join(row)` normalized), (3) fall back to per-cell multiset match across all grids before declaring `verified_missing`.

- [HIGH] **Column reorder is semantic corruption, not absence — camelot/tabula/TEDS agree.** Evidence: camelot `assert_frame_equal` fails any swapped column (`camelot/tests/test_common.py:53-56`); tabula pins full `tableToArrayOfRows` goldens (`tabula-java/TestBasicExtractor.java:146`); whisker TEDS uses order-matched table pairs and tree-edit distance on cell topology (`bench.py:112-125`, `metrics.py:608-619`); `_check_table` catches swaps only when asserted neighbors differ (`facts.py:374-423`, `golden-hook` at `facts.py:386-391`). Impact: a quote that is only a cell string (`"NSF"`) will `present_in_candidate` under document-wide locate when the column moved but the token remains. **Policy:** if quote tokens appear in parsed grids but row-neighbor relations implied by a multi-cell PDF quote do not match any row, emit `ambiguous` (table_semantic_mismatch), not `verified_missing`. Reserve `verified_missing` for tokens absent from **all** parsed grids and prose fences.

- [HIGH] **Duplicate text elsewhere must demote absence claims — PR #290 is the template.** Evidence: forced replay found date lines "already present, some twice" (`00-baseline.md:17-18`); anchorless `_check_table` uses ANY-occurrence semantics when `table_heading` is absent (`facts.py:381-384`, `416-421`); `ground_spans` monotonic DP maps repeated quotes to successive occurrences (`grounding.py:179-181`). Impact: short table-cell quotes (`"Yes"`, `"2024-01-15"`) will false-clear as `present_in_candidate` if the same token appears in prose, TOC residue, or a second table. **Policy:** for quotes under `TABLE_QUOTE_MAX_CELL_CHARS` (new named constant, start at 32 norm chars), require grid hit **or** row-join hit to count as `present`; a prose-only hit → `ambiguous` (duplicate_collision), not `verified_missing`. Longer row quotes may use document-wide locate as secondary signal only.

- [HIGH] **Pipe/HTML markup and empty cells are sanctioned conversion, not missing content.** Evidence: tomd emits HTML tables when pipe format cannot represent a construct (`tables.py:12-14`, `130-135`); camelot `compute_whitespace` treats stripped-empty cells as quality signal, not content deletion (`camelot/utils.py:1615-1638`); img2table hard-rejects ragged grids before scoring (`img2table/filter/model.py:125-152`). Impact: quotes that include `|`, `---`, or `<td>` from the judge's markdown imagination should never source-ground; quotes that omit pipes but match joined row text should be `present_in_candidate`. **Policy:** strip pipe separators and HTML table tags from candidate haystack for table-route matching; ignore empty grid slots (camelot whitespace analog). Do not treat "PDF had no pipes" as absence.

- [MED] **Reuse whisker table machinery for candidate locate — do not add extractors.** Evidence: `facts.py` already locates cells and checks `up`/`down`/`left`/`right`/`heading` neighbors (`facts.py:349-423`); `bench.py` shares `parse_pipe_tables` for TEDS (`bench.py:87-94`); camelot `confidence = (accuracy/100)*(1-whitespace/100)` is a portable intrinsic sidecar (`camelot/core.py:681-705`), not a quote oracle. Impact: v1 table candidate locate can be ~60 LOC: classify quote → scan grids → optional inverted neighbor check when quote carries ≥2 tokens from same PDF row. No camelot/img2table/tabula runtime dependency.

- [MED] **olmOCR-Bench table-cell tests are the external anchor for quote-level table absence.** Evidence: olmOCR dataset includes table-cell deterministic presence/absence tests (`05-web.md:127-128`); pdf-parse-bench pairs formula/table blocks before LLM scoring (`05-web.md:32-35`). Impact: holdout labels for table quotes should be per-cell or per-row, not document verdict. WG21 replay should tag each of the 20 baseline quotes with `shape: prose|table_row|table_cell` before measuring precision.

- [LOW] **tabula-java-tmp adds spanning-cell fixtures only; whisker grid model still span-blind.** Evidence: `tabula-java-tmp` tests `spanning_cells.pdf` CSV/JSON goldens (`tabula-java-tmp/TestCommandLineApp.java:89-105`); whisker `_HTMLTableParser` ignores `rowspan`/`colspan` (`tables.py:98-117`, `CLAUDE.md` Known gaps #2). Impact: rowspan-induced neighbor drift can false-trigger `ambiguous` on row-neighbor checks; does not change substring absence policy until span-aware grids land.

## Quote-absence decision table

| Scenario | Source locate | Candidate locate | Status | Counts as missing evidence? |
| --- | --- | --- | --- | --- |
| PDF flattened row → faithful pipe table | grounded | row-join or per-cell all present in one grid row | `present_in_candidate` | No |
| PDF row → table, all cells present, columns swapped | grounded | cells found, neighbor/row pattern mismatch | `ambiguous` (`table_semantic_mismatch`) | No (abstain) |
| Cell text absent from all grids + prose | grounded | no grid/prose hit at tier floor | `verified_missing` | Yes |
| Short cell token, duplicate in prose | grounded | prose hit only | `ambiguous` (`duplicate_collision`) | No |
| Short cell token, duplicate in wrong table column | grounded | grid hit without neighbor context | `present_in_candidate` if ANY grid match; `ambiguous` if multi-table + heading context in quote | No / abstain |
| Quote includes `\|` or HTML from judge, not in PDF | not grounded | — | `source_ungrounded` | No |
| Table parse error / lossy table signal | grounded | grids empty or ragged | `ambiguous` (degrade; do not assert absent) | No |

Aligns with tri-state routing in `03-bidirectional-design.md:28-35` and abstention policy in `05-web.md:157-159`.

## Implementation seam (research only; no code in this run)

1. **Classify** each `missing_content` quote: `table_row` if ≥3 whitespace-separated tokens and source page context contains ≥2 aligned table lines in `page_text`; `table_cell` if ≤`TABLE_QUOTE_MAX_CELL_CHARS` and no sentence punctuation; else `prose`.
2. **Candidate locate:** `prose` → existing `ground_spans`; `table_*` → `_all_tables(tomd_md)` from `facts.py:342-346`, then row-join and cell scan with `_norm_cell` (`facts.py:269-270`).
3. **Sidecar:** extend `grounded_evidence` with `quote_shape`, `candidate_status`, `table_route` (`grid_row_join` | `grid_cell` | `document_wide` | `none`); replace false combined reason at `pdf_judge.py:401-404`.
4. **Demotion:** `verified_missing` count excludes `ambiguous` table collisions; verdict cap per `03-bidirectional-design.md:48-57`.

## False-pass hypothesis

WG21 poll table: columns `Yes | No | Abstain` swap positions during conversion. Judge quotes `"Yes"` as missing from markdown. Document-wide `normalized_text` finds `"yes"` in the swapped grid and in a prose sentence ("vote Yes"). Table route returns `present_in_candidate` via ANY cell match (`facts.py:416-421` semantics). **Actual defect:** column semantics wrong for downstream LLM. Mitigation: when `lossy_table_count > 0` or `table_parse_errors > 0` (`adjudicate.py:115-117`) and quote is `table_cell`, prefer `ambiguous` over `present` unless `table_heading` context appears in the quote.

## False-fail hypothesis

Faithful conversion: PDF text layer emits `"Nanotechnology and its publics NSF Pennsylvania State Universit"` as one wrapped line (tabula cell chain `TestBasicExtractor.java:230-232`). Markdown has a correct pipe table. Row-join candidate locate fails because PDF truncation (`Universit` vs `University`) breaks join, cell-level fuzzy passes. Quote demoted to `verified_missing`. Mitigation: per-cell `max_diffs` budget from `facts.py:299-321` on row cells before row-join failure; source fuzzy + per-cell candidate fuzzy → `ambiguous`, not `verified_missing`.

## What would change my mind

A labeled holdout of ≥30 table-shaped quotes from WG21 PDFs showing grid-scoped locate with row-join + duplicate_collision rules achieves ≥90% evidence precision **and** catches ≥80% of intentional column-swap corruptions that document-wide locate misses — would upgrade verdict to **usable** without `ambiguous` bands. Failure mode: >15% of faithful pipe-table conversions still labeled `verified_missing` on row-join path.

## Cross-anchors

- Baseline failure and 40% precision: `00-baseline.md:14-24`, `00-baseline.md:28-44`
- Bidirectional state machine: `03-bidirectional-design.md:12-35`, `03-bidirectional-design.md:48-57`
- Web pattern (deterministic table pairing before LLM): `05-web.md:32-35`, `05-web.md:127-128`
- Whisker table comprehension (neighbor semantics): `packages/whisker/src/whisker/CLAUDE.md` (facts `_check_table`, golden-hook)
- Extractor corpus: `camelot/core.py:681-705`, `img2table/filter/model.py:119-162`, `tabula-java/TestBasicExtractor.java:225-282`
