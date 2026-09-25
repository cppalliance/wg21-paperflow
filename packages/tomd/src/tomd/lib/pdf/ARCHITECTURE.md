# tomd PDF Converter Architecture

## Overview

tomd converts WG21 (C++ standards committee) PDF papers to Markdown. It uses a dual-extraction architecture: every page is processed through two independent text extraction paths, and their agreement determines confidence. Where they agree, the output is clean Markdown. Where they disagree, the region is flagged for manual LLM reconciliation.

The MuPDF path uses the library's built-in block/line/span hierarchy. The spatial path walks raw character coordinates with four geometric rules. Both produce the same intermediate data model (Span -> Line -> Block). The comparison is the confidence mechanism - it is never skipped.

## Core Principles

- **Multi-signal confidence.** Every structural decision (heading, paragraph, list, code, table) considers all available signals and produces a confidence level. Single-signal classification is prohibited.
- **Preserve all metadata.** Font size, font name, font flags, coordinates, and page boundaries are preserved through extraction. Downstream phases use this metadata for classification.
- **Honest output.** The tool never silently produces bad Markdown. Uncertain regions are marked with HTML comments and accompanied by a prompts file for LLM reconciliation.
- **MuPDF-preferred emission.** When paths disagree, MuPDF's version goes in the output (more battle-tested). Both versions go in the prompts file.

## Data Model

```
Span   - A run of text with uniform font properties (text, font_name, font_size,
         bold, italic, monospace, bbox, origin, color, link_url)
Line   - A sequence of Spans forming one visual line (properties: text, font_size, is_bold)
Block  - A group of Lines forming a paragraph-level unit (property: font_size as mode)
Section - A classified document region (kind, text, confidence, heading_level, lines,
          mupdf_text, spatial_text, page_num, font_size, metadata, columns, fence_lang)
```

Enums:
- `Confidence`: HIGH, MEDIUM, LOW, UNCERTAIN
- `SectionKind`: TITLE, METADATA, HEADING, PARAGRAPH, LIST, CODE, TABLE, IMAGE, UNCERTAIN, WORDING, WORDING_ADD, WORDING_REMOVE

## Pipeline (13 steps)

| Step | What | Module |
|------|------|--------|
| 1 | Dual extraction (MuPDF + spatial) + edge items + links + hidden scan + drawings + image extraction | `extract.py`, `cleanup.py`, `wording.py`, `images.py`, `__init__.py` |
| 1.5 | Slide-deck / standards-draft detection (geometry or page-count early exit) | `__init__.py` |
| 2 | Close document | `__init__.py` |
| 3 | Hidden block stripping + readability check | `cleanup.py`, `types.py` |
| 4 | Header/footer detection and stripping | `cleanup.py` |
| 5 | Monospace propagation (spatial -> MuPDF) | `mono.py` |
| 5.5 | Wording detection (HSV color + drawing correlation) | `wording.py` |
| 6 | Text cleanup (format chars, NBSP, dehyphenation, cross-page join) | `cleanup.py` |
| 7 | Span normalization (style boundaries to word edges) | `spans.py` |
| 8 | WG21 metadata extraction + table detection | `wg21.py`, `table.py` |
| 9 | Dual-path comparison (per-page, fallback cascade) | `structure.py` |
| 10 | Structure (headings, lists, paragraphs, code blocks, nesting) | `structure.py` |
| 11 | TOC stripping | `toc.py` |
| 12 | Emit Markdown + prompts file | `emit.py` |
| 13 | Return `PipelineResult` | `__init__.py` |

## Techniques by Layer

### Layer 1: Extraction (8 techniques)

**T0. Document-type and readability early exits**
- `pipeline.py:_is_slide_deck`, `pipeline.py:_is_standards_draft`, `types.py:is_readable`
- Four skip kinds, all via `PipelineResult.for_skip(SkipReason, ...)`: empty PDF (`page_count == 0`), slide deck, standards draft (page count >= 200), and unreadable extracted text.
- Slide-deck detection: landscape (width > height) AND small (width < 600pt) on 80%+ of pages, or every page landscape. Catches presentation PDFs whose navigation sidebars confuse the dual-path extractor.
- Standards-draft detection: page count >= 200. Catches C++ standard drafts (2000+ pages) that are not technical papers.
- Unreadable gate: after hidden-text stripping, joined MuPDF text must pass `is_readable` (minimum length, alphanumeric ratio, slash density).
- `_enforce_skip_contract` validates skip invariants on every `run_pipeline` return.
- Named constants: `_SLIDE_DECK_MAX_WIDTH`, `_SLIDE_DECK_LANDSCAPE_FRACTION`, `_STANDARDS_DRAFT_MIN_PAGES`

**T1. MuPDF dict-path extraction**
- `extract.py:extract_mupdf`
- Uses `page.get_text("dict")` for MuPDF's block/line/span hierarchy
- Preserves font name, size, flags (bold bit 4, italic bit 1), bbox, origin, color
- Accepts only type-0 (text) blocks

**T2. Spatial rawdict-path extraction**
- `extract.py:extract_spatial`
- Uses `page.get_text("rawdict")` for per-character coordinates
- Four spatial rules in priority order:
  - `dy > avg_fs * 2.5` -> paragraph break
  - `dy > avg_fs * 1.8` -> line break
  - `dy > avg_fs * 0.3` -> line break
  - `dx > avg_fs * 0.3` -> word break (insert space)
- Characters sorted by y-band (half font height) then x-position, giving deterministic reading order within each band

**T3. Monospace classification (4 signals)**
- `mono.py:classify_monospace`
- Signal 1 (font name): strip modifiers, split camelCase, check keywords {mono, courier, code, consolas, menlo}
- Signal 2 (glyph width CV): coefficient of variation of character bbox widths (lower = more uniform)
- Signal 3 (glyph spacing CV): coefficient of variation of inter-glyph x-origin spacing (strongest - measures the defining property)
- Signal 4 (fat/thin): compare widths of fat chars {M,W,m,w,@,%} vs thin chars {I,i,l,1,|,!,.,space}. Ratio > 1.3 -> immediate reject
- Acceptance: 2+ signals agree, or signal 3 alone, or signal 1 alone. Signal 2 alone rejected (weakest).

**T4. Monospace propagation**
- `mono.py:propagate_monospace`
- Spatial path has per-character data (signals 2-4). MuPDF path has only font name (signal 1).
- After extraction: collect fonts classified as monospace by spatial. Exclude the dominant body font (most common by character count). Set `monospace=True` on matching MuPDF spans.

**T5. Link collection and attachment**
- `extract.py:collect_links`, `extract.py:attach_links`
- Collects `page.get_links()`, filters to http/https/mailto schemes
- Attaches to spans by bounding rect overlap (best overlap wins)

**Resource-Dictionary path (image extraction).**
- `images.py:extract_page_images`, `images.py:finalize_extraction`
- A fourth PDF API surface, independent of the MuPDF dict and spatial
  rawdict text-extraction paths. Uses `page.get_images(full=True)` +
  `page.get_image_rects(xref)` + `doc.extract_image(xref)` to enumerate
  the raster image XObjects referenced by the page's resource dictionary,
  not the rendered glyphs.
- Produces `ExtractedImage` records (page, index_on_page, ext, bytes,
  bbox, suggested_alt, stored_filename). The caller persists `bytes`;
  this module never writes to disk.
- Runs per page during step 1 (while the document is still open). The
  caption-proximity heuristic uses the spatial-path text blocks already
  produced on the same page, so no duplicate text extraction.
- Cross-page xref deduplication and the 20-image cap are applied by
  `finalize_extraction` after the readability check passes. Unreadable
  PDFs and early-exit paths (slide deck, standards draft) produce
  `PipelineResult.images = []` so the CLI never persists orphan PNGs.
- Visible to this path: every embedded JPEG / PNG / JPX, regardless of
  rendering.
- Invisible to this path: vector drawings (paths and lines, e.g.
  flowcharts, graph diagrams), scanned-page rasters that ARE the page
  rather than embedded within it, and any structural meaning of the
  image. The caption-proximity regex over Path 1's text is a v1
  stopgap; the layout-aware path in `improvements.md` section 4 would
  supersede it with structural `caption` bboxes from a layout model.
- Named constants: `_MAX_IMAGES_PER_PAPER`,
  `_CAPTION_SEARCH_RADIUS_BELOW_PT`, `_CAPTION_SEARCH_RADIUS_ABOVE_PT`,
  `_CAPTION_LABEL_RE`.

### Layer 2: Cleanup (9 techniques)

**T6. Hidden region detection**
- `cleanup.py:find_hidden_regions`
- Detects Google Docs widget artifacts: non-body-font, non-black color, Roboto/Google/Material font names
- Rendering mode 3 (invisible text) intentionally ignored - MuPDF dict/rawdict already excludes it
- Blocks entirely within hidden regions are stripped

**T7. Header/footer detection**
- `cleanup.py:detect_repeating`, `cleanup.py:strip_repeating`
- Top 3 and bottom 3 lines per page by y-coordinate
- Y-bucket by tolerance (2.0 units), count pages per bucket
- Items on 50%+ of pages at the same y -> repeating (exact text, page number pattern, or doc number pattern)

**T8. Text normalization**
- `cleanup.py:cleanup_text`, `cleanup.py:strip_format_chars`, `cleanup.py:normalize_whitespace`
- Strips all Unicode Cf-category characters (format chars) via precomputed frozenset
- Replaces NBSP with space
- Collapses multi-space (except in monospace spans)

**T9. Dehyphenation**
- `cleanup.py:cleanup_text` (span-level, active in pipeline) via `collect_hyphen_evidence` + `dehyphenate_pair`
- Line ends with `-` (no space before it), next line starts lowercase, same monospace-ness on both sides
- Keep-or-glue decided per pair, document evidence first: compound seen hyphenated mid-line -> keep; glued word seen whole -> glue; prefix in `COMPOUND_PREFIXES` -> keep; acronym / digit-led prefix -> keep; both halves standalone words -> keep; tail ends another compound -> keep; else glue. Wrap fragments never count as evidence. Monospace pairs and hyphens after a non-alphanumeric (`convertible_-`) use the compound-seen rule only.
- Both outcomes pull the next line's first word up onto the hyphen line, so a flattened paragraph never reads `non- associative`
- `structure.py:_merge_paragraphs` runs `dehyphenate_pair` on a text-merge boundary (MuPDF opens a new block after a hyphen at normal line spacing), same evidence built from all section lines

**T10. Cross-page paragraph joining**
- `cleanup.py:_join_cross_page`
- Previous block ends without terminal punctuation (`.?!:`), next block starts lowercase, different page numbers -> merge blocks
- Copies blocks before mutating to prevent caller mutation

**T11. Page 0 color extraction**
- `__init__.py:_get_page0_text_colors`
- Type 3 fonts report black for all glyphs. Space characters (type=0 in texttrace) leak the true graphics-state fill color.
- Maps y-positions to lightness values for title detection

**T12. Readability check**
- `types.py:is_readable`
- Rejects encrypted/scanned PDFs: min 100 chars, alphanumeric ratio > 0.3, slash ratio < 0.1

### Layer 3: Span Normalization (1 technique)

**T13. Style boundary word-edge snapping**
- `spans.py:normalize_spans`
- Two passes: left-to-right then right-to-left
- When a bold/italic boundary falls mid-word between adjacent non-monospace spans, moves text to align the boundary with a word edge
- Monospace spans are exempt (code boundaries are intentional)
- Uses `dataclasses.replace` for immutable span updates

### Layer 4: Table Detection (3 techniques)

**T14. Table detection (two-signal)**
- `table.py:detect_tables`
- Signal 1 (block structure): blocks with 2+ lines where x-starts have gaps > 50 units are columnar. Consecutive matching-column blocks (within 10-unit tolerance) form a table run (min 2 rows). Works across page boundaries: blocks from consecutive pages with matching columns form one table.
- Signal 2 (geometric column profile): pre-pass over all blocks collects x positions that co-occur with other x positions in the same y-band across 2+ y-bands. Y-bands are scoped per page. Body text (alone in its y-band) never qualifies; only genuine table column x positions are selected.
- Orphan absorption: single-line blocks whose x0 matches a confirmed column are "orphans" (wrapped cell first lines split off by MuPDF). Absorbed when the following block is a full table row (one-block lookahead confirms continuation). Three guards prevent false positives: (1) only single-line blocks qualify; (2) orphan must be on the same page as the last confirmed table row; (3) the confirming lookahead block must also be on the same page as the orphan. Orphan partial rows are merged into the following row's first cell so multi-line cells render as a single cell string.
- Known gap: a wrapped cell whose continuation line is the first block on the next page will not be absorbed (cross-page orphan). The table will end at the last same-page row and the orphan will appear in the output as an uncertain region.
- Backward tails (#380): an orphan at column 1+ (any column count, non-monospace) is the wrapped tail of the previous row's cell and merges backward via the partial-row path. An orphan without a confirming full row behind it is a trailing continuation absorbed inside the scan loop (Branch 4c), so a partial row that follows still joins the table. Fragment absorption reaches at most `_PARTIAL_ROW_MAX_Y_GAP` below the last row.
- Shattered tables (#380): `_detect_side_by_side_tables(atomized_only=True)` runs before Pass 1 and claims tables whose cells are one block per wrapped line, either under an atomized header or under a regular header row block over an atomized body (`_body_is_atomized`). A dense-table gate (`_ATOMIZED_PREPASS_MIN_ROWS_DENSE`) and a mid-table seed guard bound it. Sections from the pre-pass, Pass 1, Pass 2, Pass 4, Pass 4b and the banded-grid path record their producer in `table_source` (`side_by_side_prepass`, `side_by_side`, `horizontal_rows`, `column_aligned`, `banded_grid`, `spec_label`); Pass 3, Pass 5 and merged cross-page fragments leave it `None`.
- Post-passes: header cluster absorption (`_collect_header_cluster`, free blocks directly above a table whose lines sit on table columns) and separator-row removal (`_drop_separator_rows`, a body row of dash-only cells).
- Extracted as TABLE sections with HIGH confidence

**T15. Spatial table exclusion**
- `table.py:exclude_table_regions`
- Removes spatial blocks whose y-center falls within detected table y-ranges (5-unit margin)

**T16. Table section insertion**
- `pipeline.py:run_pipeline`
- Tables inserted into the section list by page number and y-position ordering

### Layer 5: Wording Detection (3 techniques)

**T17. HSV color classification**
- `wording.py:classify_wording`
- Converts span RGB color to HSV via `colorsys.rgb_to_hsv`
- Saturation gate: S < 0.15 -> achromatic (not a chromatic signal). Non-black achromatic text with lightness 0.25-0.65 classified as "context" (existing spec text).
- Hue neighborhoods: green [90-180] = ins candidate, red [0-30 or 330-360] = del candidate, blue [210-270] = link (skipped)
- Document-relative: body color identified from character-count histogram, only non-body chromatic text is classified
- Block skip (`_block_has_foreign_colors`, `_block_has_highlighter_palette`): a block with a foreign chromatic hue (purple/orange/cyan), or with two or more distinct shades inside the green band or inside the red band (Pygments keyword + number green), is syntax-highlighted code and is skipped unless a red span carries a confirmed strikethrough (#413)

**T18. Drawing decoration correlation**
- `wording.py:_match_underline`, `_match_strikethrough`
- Horizontal line drawings from `page.get_drawings()` correlated with span bboxes
- Underline: horizontal line within 1.5pt of span bbox bottom
- Strikethrough: horizontal line within 2.0pt of span bbox vertical center
- Drawing color provides additional confirmation

**T19. Multi-signal confidence with prompts**
- `wording.py:classify_wording`
- HIGH: color + decoration agree (green + underline, red + strikethrough)
- MEDIUM: color only (no decoration confirmation)
- LOW: decoration only (hue not in green/red range)
- Document threshold: fewer than 5 ins/del spans -> skip entirely (suppresses false positives)
- Returns problem descriptions for the prompts file when confidence is MEDIUM-only

### Layer 6: Dual-Path Comparison (1 technique, 5 fallback stages)

**T20. Comparison cascade**
- `structure.py:compare_extractions`
- Stage 1: Per-page word-level multiset similarity. Threshold 0.85.
- Stage 2: NFC normalization fallback. If word similarity fails, NFC-normalize joined words and compare. Catches Unicode normalization differences.
- Stage 3: Page-pair window. For uncertain pages, combine with next page and re-check similarity. Catches content shifted across page boundaries. When the pair clears the threshold both pages are promoted, but blocks are re-emitted as paragraphs only for pages that actually carried an UNCERTAIN section: a confident pairing partner already has its first-pass PARAGRAPH sections, so re-emitting it would duplicate every block on that page.
- Stage 4: Document-level pool. Combine all remaining uncertain pages and check total similarity. Catches systematic page-assignment differences. Same uncertain-only re-emission rule as stage 3 (a no-op here, since pooled pages are all uncertain by construction).
- Stage 5: Tiny-region demotion. Uncertain sections with fewer than 10 words in the shorter version -> demoted to PARAGRAPH with LOW confidence.

### Layer 6: WG21 Metadata (2 techniques)

**T21. WG21 metadata extraction**
- `wg21.py:extract_metadata_from_blocks`
- Scans page 0 blocks for labeled fields (Document Number, Date, Audience, Reply-to, Project)
- Handles Scrivener layout (one field per block) and Google Docs layout (multiple fields per block)
- Reply-to continuation: absorbs unlabeled blocks with email addresses after the reply-to field
- Author parsing: pairs names with emails across line boundaries

**T22. Title detection (2 signals)**
- `wg21.py:extract_metadata_from_blocks`
- Signal 1 (font size): picks the largest-font block among pre-label blocks
- Signal 2 (color darkness): uses space-color proxy lightness. Darker = more likely title, lighter = watermark.
- Sorting: `max(font_size, -lightness)` - font size primary, darkness secondary
- All pre-label blocks consumed (including category labels like "WG21 PROPOSAL")
- Category labels (short all-uppercase text) also stripped by `structure.py:_extract_metadata`

### Layer 7: Structure (6 techniques)

**T23. Multi-signal heading classification**
- `structure.py:_heading_confidence`
- 5 signals: section number (highest), font size rank, bold, known section name, font size > body
- Decision matrix with 11 outcomes mapping signal combinations to (level, confidence)
- Bold never determines heading level but raises confidence by one tier as a confirming signal
- Nesting validated: no heading may skip more than one level deeper than predecessor

**T24. List detection (regex + position)**
- `structure.py:structure_sections`, `_detect_lists_by_position`
- Regex: bullet patterns and numbered list patterns against all lines
- Position: line x-coordinate vs body margin (leftmost frequent x). Indented lines with bullet chars -> LIST
- Bullet marker joining: single-char bullet lines merged with following text lines
- Inline bullet splitting: fallback for sections without position data

**T25. Paragraph merging**
- `structure.py:_merge_paragraphs`
- Prev section (PARAGRAPH or LIST) ends without terminal punctuation, next PARAGRAPH starts lowercase -> merge
- Inline continuation (`_starts_inline_continuation` + `_is_wrapped_continuation`): next PARAGRAPH opens with `(`, a bracketed reference the sentence runs on from (`[numerics.defns]. ...`, `[4] and ...`: closing bracket followed by punctuation or a lowercase word, `_BRACKET_CONTINUATION_RE`) or an inline code span on a mixed prose line, and the geometry proves a wrap: same page (by line), same font size (0.5pt), first line exactly one wrap pitch below the previous last line (baseline to baseline, `_WRAP_PITCH_TOL` 0.15 font sizes), starting at that line's left edge (a first-line indent to its left is allowed only when that line is the block's single line, nothing to its right), and the next block's first word would have crossed the text margin had it stayed on that line (`_AVG_CHAR_WIDTH` 0.5 em per glyph) -> merge. The wrap pitch (`_wrap_pitch`) is the median baseline distance over the pairs known to be wraps: consecutive prose lines inside one section and the boundaries the lowercase rule merges; it is exact per document (P4016R0 1.500, P0957R8 1.566, P4100R1 1.850) and a paragraph break adds at least 0.5 font sizes (Word 6pt after 12pt text), so the gate needs no tuned window. The margin (`_text_margin`) is the largest line end that at least `_LAYOUT_WITNESS_MIN` (3) paragraph/list lines in the document share within 6pt; fewer witnesses for either measure (a short list alone, a lone long URL, a document of one-line paragraphs ending in periods) means no inline merge; a wide code listing (still a paragraph at this stage) or the right column of a two-column layout inflates the margin and only disables the merge. MuPDF splits the block where the glyph run changes (`... topology coordinate` / `(lane count L), ...`); a short last line (definition entry `V be ...,` / `A be ...:`, bibliography URL then label) is a deliberate break, and `(1)`/`(a)` numbering (`_ENUM_LABEL_RE`), `[GB-SEQ] = ...` labels and `[Note: ...` openers are lexically excluded. The terminal-punctuation gate looks behind closing quotes, emphasis and brackets (`"unified interface."`); a trailing hyphen is left to the lowercase path (T9). All-monospace lines (code), bullets and list numbers never qualify.
- Copies sections before mutating to prevent caller mutation

**T26. Code block detection**
- `structure.py:_detect_code_blocks`
- Consecutive all-monospace sections merged into CODE with HIGH confidence
- Empty sections between monospace runs are bridged (blank lines in code)
- Language labels (16 languages) detected and applied to fence language

**T27. Metadata zone extraction**
- `structure.py:_extract_metadata`
- Scans early sections for doc number, date, reply-to, audience patterns
- Category labels (short all-uppercase text with >=1 letter, <=3 words) consumed
- Metadata zone ends at first section-numbered heading

**T28. Body size and font ranking**
- `structure.py:_detect_body_size`, `_rank_font_sizes`
- Body size: most common font size by character count (fallback 11.0)
- Font ranking: sizes > body * 1.05 ranked descending (rank 1 = largest = shallowest heading)

### Layer 8: TOC Detection (2 techniques)

**T29. TOC detection with exact-match + fuzzy fallback**
- `toc.py:find_toc_indices`
- Normalizes entries: strips dot leaders, page numbers, section prefixes, collapses whitespace
- Fast path: exact-match set lookup (`_exact_set`) against normalized headings. O(1) per section.
- Fuzzy fallback: only when heading count is below `_MAX_FUZZY_HEADINGS` (200). Uses dual-algorithm OR-gate (SequenceMatcher >= 0.75 OR Jaccard >= 0.65). Without this guard, large documents (2000+ pages, 40k sections) hang on O(sections * headings) fuzzy comparisons.
- Requires 3+ consecutive matches. Bridges gaps up to 3 non-matching entries, but only when each bridged entry is trivial (`_bridgeable`: blank, a bare/numeric label, or <= `_MAX_BRIDGE_ENTRY_WORDS` words with no terminal punctuation). A real prose paragraph breaks the run instead of being swallowed.
- A section that is itself a body heading (`is_heading[i]`) is excluded from matching, *unless* its own text is shaped like a TOC line (`_TOC_LINE_RE`: a dot leader followed by a page number, e.g. `Foo .... 7`). Without this, every body heading matched itself in the reference set and the gap-fill deleted the prose between headings, destroying the body of short papers. The shipped predicate keys on the dot-leader-then-page-number shape, not a bare trailing number, so body headings like `Step 1` / `Phase 2` are never eligible.
- Stops on duplicate first-line (second occurrence = real heading, not TOC entry)
- Includes preceding "Table of Contents" / "Contents" label

**T29b. Leaked mixed-kind TOC removal**
- `structure.py:drop_leaked_toc_entries`, run after the T29 strip and the IMAGE filter, before emit
- T29 deliberately does not match a heading-kind TOC entry that lacks the dot-leader shape (the `is_heading` guard, to avoid the body-deletion class). Such a TOC therefore leaks, and it leaks as a *mix* of kinds: some entries survive as empty duplicate `HEADING`s, others as short title-like `PARAGRAPH`/`LIST` sections (`3. The Rationale for Unification`). The heading-only predecessor caught only the heading-kind entries; this pass removes the whole block.
- The single discriminator across both *entry* kinds is **recurrence as a later heading**. A `HEADING` is an entry when it is empty and its normalized title recurs later; a `PARAGRAPH`/`LIST` is an entry when it is title-like (at most `_TOC_ENTRY_MAX_LINES` text lines, derived from `sec.text`) and its first-line title recurs later. A heading's emptiness bridges trivial fragments *and* title-like non-headings, so `## 3.7 Summary` sitting over a `LIST`-kind entry still counts as empty.
- Removal is a run of entries of length at least `MIN_TOC_RUN` (shared with `toc.py`) that clears the **heading anchor** (at least one empty-heading entry). A run whose heading subsequence strictly deepens is rejected (`15`/`15.1`/`15.1.1` clause-container stack; applies to all-heading and mixed runs alike). Also drops in-span trivial fragments and a preceding `Table of Contents` label whether paragraph-kind or heading-kind (P4003R1's leaked `### Table of Contents`).
- **Relaxed bridging.** A real leaked TOC is often *fragmented* by non-recurring **stragglers**: title-like paragraph/list lines whose body heading text drifted, and once-only empty headings. The strict variant broke its run at each; this pass bridges stragglers as in-span run members so the block coalesces and removes whole (P4016R0's ~146-entry appendix dump, P4007R0's once-only `8.1`-`8.4` objections, both previously left as a residual). The relaxation is gated by five interacting layers, and the body-safety is the *conjunction*, not any single layer: (1) the **heading anchor** above; (2) a **front-region bound** (`body_start` = the first non-recurring, non-trivial, `>= 2`-line `PARAGRAPH`) so straggler bridging fires only in the front matter, never in the body where repeated spec boilerplate forms dense false runs (this is the guard against p2846r6's `Effects:` wording loss); (3) a **recurrence-density floor** (`_TOC_RUN_MIN_RECUR_FRACTION`, fraction of counted members that recur as headings); (4) the **in-span / trailing rule** (only stragglers strictly between the first and last *entry* are removed; trailing stragglers the scan bridged are kept, protecting a real section and real single-line abstract prose right after the TOC, e.g. P4016R0's idx150/151); (5) a **forward-reference gate** on paragraph/list stragglers only (`_straggler_forward_references`: removed only if the normalized title appears as a later heading via bidirectional containment, so a unique body sentence is never deleted; empty-heading stragglers are exempt because heading text drifts between TOC and body and a hard gate there regresses P4007R0).
- The gates are decomposed into independently unit-tested predicates (`_is_title_like_straggler`, `_is_empty_heading`, `_straggler_forward_references`, `_run_recurrence_density`, `_compute_body_start`) so a refactor cannot silently drop one layer's contribution. Not body-safe by construction for the empty-heading-straggler class (heading-level loss only), which the corpus anchor/density/front/in-span gates plus a standing manual heading review cover; the paragraph-straggler (prose) class is gated automatically by forward-reference. `_TOC_ENTRY_MAX_BODY_CHARS`, `_TOC_ENTRY_MAX_LINES`, `_TOC_RUN_MIN_RECUR_FRACTION`, `_TOC_STRAGGLER_MIN_TITLE_LEN`, and `MIN_TOC_RUN` are corpus-tuned; under-removal leaves a cosmetic remnant (a forward-ref-failing paragraph straggler is bridged-but-kept, leaving at most one stray line). Recall limit: an entry whose body counterpart is *not* a recurrence-matching heading carries no signal and is left in place.

### Layer 9: Emission (8 techniques)

**T30. YAML front matter**
- `emit.py:_format_front_matter`
- Fixed field order: title, document, date, audience, reply-to
- Title double-quoted (may contain colons). Reply-to as YAML list of double-quoted strings.

**T31. Inline Markdown formatting**
- `emit.py:_render_span`, `_render_line_spans`
- Separates leading/trailing whitespace from content before applying bold/italic/link markers
- Consecutive monospace spans merged into single backtick pair (prevents fragmented inline code)
- Bold suppressed in headings (ATX prefix already conveys weight)

**T32. Paragraph unwrapping**
- `emit.py:_render_paragraph_spans`
- PDF line breaks joined with spaces to produce single unwrapped paragraph lines

**T33. Code block rendering**
- `emit.py:_render_code_block`
- Fenced with language tag. Indentation estimated from glyph x-positions divided by character width.

**T34. Table rendering**
- `emit.py:_render_table`
- GitHub-style Markdown pipe tables. First row = header with bold suppressed.
- A cell with more than one line of code renders as a labeled fence group: a bold row label, then one italic column header and a cpp fence or a plain paragraph per column. Never a raw HTML table.

**T35. Uncertain region marking**
- `emit.py:emit_markdown`
- HTML comments with line ranges: `<!-- tomd:uncertain:L{start}-L{end} -->`
- Line numbers tracked cumulatively through the document

**T36. Prompts file generation**
- `emit.py:emit_prompts`
- For each uncertain region: page number, surrounding context (200 chars), both extraction versions in code fences
- Returns None if no uncertain regions

**T37. Output cleanup**
- `emit.py:emit_markdown`
- Empty sections filtered. Parts joined with single blank line. Single trailing newline.

### Layer 10: Pipeline Orchestration (1 technique)

**T38. Pipeline execution**
- `pipeline.py:run_pipeline`
- Strict ordering of all pipeline steps. Early exit via `SkipReason` on empty PDF, slide deck, standards draft, or unreadable text.
- Metadata merging: `{**structure_metadata, **wg21_metadata}` - WG21 metadata takes precedence.
- TOC heading collection: only HEADING sections used as the reference set for TOC matching. The per-section `is_heading` flags are also passed to `find_toc_indices` so a body heading cannot match itself out of existence.

### Layer 11: Quality Assurance (1 technique)

**T39. Markdown-only QA scoring**
- `qa.py:compute_metrics`
- Design constraint: takes ONLY a Markdown string. No page count, no file format, no pipeline internals. Every signal is derived from the text via mistune AST parsing. This keeps scoring format-agnostic and decoupled from the converter. Do not add parameters that leak converter state.
- Signals: heading count, code block count, list/table count, front-matter field count, uncertain region markers (`<!-- tomd:uncertain -->`), unfenced code lines (C++ syntax patterns in paragraphs), paragraph count, structural variety
- "Long document" threshold (`_LONG_DOC_PARAGRAPHS = 10`) gates penalties that only make sense for substantial documents (no-headings, low-variety)
- `run_qa_batch` handles batch execution via `lib/batch.run_parallel_batch` with parallel workers and straggler timeout; `format_qa_report` formats stdout output (CLI-owned)

## Module Map

| Module | Responsibility | Public API | Lines |
|--------|---------------|------------|------:|
| `pipeline.py` | Pipeline orchestration, skip contract, slide-deck detection | `run_pipeline`, `PipelineResult`, `ExtractedImage` | ~1100 |
| `__init__.py` | Re-exports | `run_pipeline`, `PipelineResult`, `SkipReason`, `ExtractedImage` | ~25 |
| `types.py` | Data model, enums, constants | Span, Line, Block, Section, SectionKind, Confidence, SkipReason, is_readable + shared constants | ~280 |
| `extract.py` | Dual-path text extraction | `extract_mupdf`, `extract_spatial`, `collect_links`, `attach_links` | ~249 |
| `images.py` | Resource-Dictionary path: embedded raster extraction | `ExtractedImage`, `ExtractionResult`, `extract_page_images`, `finalize_extraction` | ~250 |
| `mono.py` | Monospace font detection | `classify_monospace`, `propagate_monospace` | ~222 |
| `wording.py` | Wording section detection (ins/del) | `classify_wording`, `collect_line_drawings` | ~250 |
| `cleanup.py` | Text cleanup, header/footer, hidden regions | `detect_repeating`, `strip_repeating`, `cleanup_text`, `find_hidden_regions`, `strip_hidden_blocks` | ~373 |
| `spans.py` | Style boundary normalization | `normalize_spans` | ~149 |
| `table.py` | Two-signal table detection and exclusion | `detect_tables`, `exclude_table_regions` | ~252 |
| `structure.py` | Comparison, heading/list/code classification | `compare_extractions`, `structure_sections` | ~939 |
| `emit.py` | Markdown and prompts generation | `emit_markdown`, `emit_prompts` | ~401 |
| `wg21.py` | WG21 metadata extraction | `extract_metadata_from_blocks` | ~199 |
| `qa.py` | Markdown QA scoring (mistune AST) | `compute_metrics`, `run_qa_batch`, `format_qa_report` | ~326 |
| `similarity.py` | Fuzzy string comparison | `similar` | ~66 |
| `toc.py` | TOC detection and removal | `find_toc_indices` | ~159 |
| **Total** | | **24 public functions** | **~4132** |
