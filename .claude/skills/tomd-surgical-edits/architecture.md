# tomd Architecture Reference

Companion to `SKILL.md`. Use this to **localize** a change: find the step,
module, and function responsible for a symptom, then go read that code.

> **Line numbers are hints as of 2026-06.** They drift. Always confirm a
> function still exists and matches by grepping its name, not by jumping to a
> line. Function/constant names are durable; line numbers are not.

All paths are under `packages/tomd/src/tomd/`.

---

## 1. The shape: two converters, two post-pass layers

`api.py:convert_paper_full(paper_id, source_path, meta)` is the entry. It:

1. Dispatches by file suffix (`_convert_with_tomd_full`):
   - `.pdf` → `lib/pdf/pipeline.py:run_pipeline` → `PipelineResult`
   - `.html` / `.htm` → `lib/html/convert.py:convert_html`
2. Runs **format-agnostic post-passes** on the returned markdown, in order:
   `_normalize_front_matter` (parse → `sanitize_metadata` → mailing fallback via
   `_FALLBACK_KEY_MAP`/`_OVERRIDE_KEYS` → re-emit via `format_front_matter`)
   → `_strip_body_metadata_text` (remove metadata pipe tables from the body)
   → `strip_freeform_metadata_lines` → re-run `strip_leading_h1`
   → `_strip_toc`.

**Three possible homes for any output defect** — decide which before editing:
- **A. Format converter** (`lib/pdf/*`, `lib/html/*`) — most detection/emission bugs.
- **B. The converter's own tail post-pass** (end of `convert_html`; tail of `run_pipeline`; `emit.py`).
- **C. api.py format-agnostic post-pass** — front-matter canonicalization, body-metadata stripping, TOC stripping.

> The package `CLAUDE.md` File Map says `_canonicalize_front_matter`; the code
> now has `_normalize_front_matter`. Docs drift — trust the code.

---

## 2. PDF spine — `lib/pdf/pipeline.py:run_pipeline`

`lib/pdf/__init__.py` is re-exports only. The pipeline is `pipeline.py`. Order:

1. `fitz.open`; `page_count == 0` → empty result.
2. `_is_slide_deck(doc)` → early exit, `skip_reason="slide deck"` (geometry: ≥80% small-width landscape, or all-landscape; constants `_SLIDE_DECK_MAX_WIDTH=600`, `_SLIDE_DECK_LANDSCAPE_FRACTION=0.8`).
3. `_is_standards_draft(doc)` (`>= _STANDARDS_DRAFT_MIN_PAGES=200`) → early exit.
4. **Per-page loop:** `extract_mupdf` + `extract_spatial` (dual paths) → `Block`s; `get_edge_items`; `collect_links`+`attach_links`; `extract_page_images` (+ `extract_page_vector_images` if `extract_vector`); `collect_glyph_candidates` (+ `collect_text_emoji_bboxes`).
5. `font_counts` → `body_fonts` (top 5 by char count).
6. `find_hidden_regions` per page → `all_hidden`.
7. `_get_page0_text_colors(doc[0])` (texttrace space-color proxy for title darkness).
8. `collect_line_drawings` per page → `page_drawings` (for strikethrough/wording).
9. Parse PDF info date/title/author; close doc.
10. If hidden: `strip_hidden_blocks` both paths.
11. **Readability gate:** `is_readable(mupdf_text)` → if false, `result.readable=False`, return (early exit on scanned/encrypted).
12. `finalize_extraction` (dedup images by xref, cap `_MAX_IMAGES_PER_PAPER=20`).
13. Glyph injection: `filter_coincident` → `inject_glyph_spans` (U+FFFD placeholders for sub-threshold raster emoji) into both paths.
14. `detect_repeating` edge items → `strip_repeating` both paths (header/footer/page-number).
15. `propagate_monospace(mupdf, spatial, dominant_font)`.
16. `classify_wording(mupdf_blocks, page_drawings)` → `wording_problems`; sets `span.wording_role`.
17. `cleanup_text` both paths (NBSP, whitespace, dehyphenation, cross-page join).
18. `normalize_spans` both paths (snap bold/italic to word edges).
19. `extract_metadata_from_blocks` (wg21 metadata) with `page0_colors`.
20. `detect_tables(mupdf_blocks)` → `table_sections`; `exclude_table_regions(spatial)`.
21. `compare_extractions(mupdf, spatial)` → `list[Section]` (dual-path agreement = confident, else UNCERTAIN).
22. Insert `table_sections` by `(page, y)`.
23. Insert IMAGE sections by `(page, y)` (`_insert_image_sections`).
24. **`structure_sections(sections, has_title)`** → classification heart (see §4). Returns `(structure_metadata, sections, nesting_corrections)`.
25. Merge metadata: `{**structure_metadata, **wg21_metadata}` (wg21 wins).
26. `drop_glyphs_in_code_and_tables(sections)`.
27. Vector-image filters (3 passes) if images present.
28. Metadata fallbacks: document from filename stem; date from PDF info; `_override_revision_from_filename`; title from first non-known HEADING or PDF-info title; strip paper-ID prefix via `_TITLE_PID_PREFIX_RE`; reply-to from PDF author; `_enrich_pdf_reply_to` (page-0 email scan).
29. TOC stripping: `_toc_structural_hints` / `find_toc_indices` → drop TOC section indices (IMAGE sections never dropped).
30. `emit_markdown(metadata, sections, ...)` → md (see §6 emit).
31. `emit_prompts(sections)` → prompts; append `wording_prompts`.

`convert_pdf(path)` is a thin wrapper returning `(r.md, r.prompts)`.

---

## 3. HTML spine — `lib/html/convert.py:convert_html`

`lib/html/__init__.py` re-exports `convert_html`; logic is in `convert.py`. Order:

1. Read text UTF-8 (errors="replace").
2. `parse_html(text)` → BeautifulSoup (`html.parser`, forgiving — source of misnesting repairs in render.py).
3. `detect_generator(soup)` → one of: `mpark`, `bikeshed`, `dascandy/fiets`, `hackmd`, `hand-written`, `wg21`, `schultke`, `unknown` (first-match order in `extract.py:detect_generator`).
4. `extract_metadata(soup, generator)` → per-generator extractor + `_enrich_reply_to`; document fallback from filename; `_override_revision_from_filename`.
5. `strip_boilerplate(soup, generator)` → decomposes nav/TOC/header/title nodes in place; returns `problems` (→ prompts). Unknown generator adds a problem unless metadata was found.
6. Optional `rewrite_imgs_via_manifest` (img src → on-disk filename).
7. **`render_body(soup, generator)`** → markdown body (DOM walk; see §5).
8. Optional truncation marker if images capped.
9. Title fallback from first `^##\s+` heading (note: expects H2 — see heading bug below).
10. Assemble: `format_front_matter(metadata)` + body; strip stray leading `---`.
11. `dedup_paragraphs(md)`.
12. `strip_leading_h1(body, title)` (1st pass).
13. `strip_redundant_body_meta(md)`.
14. `strip_leading_h1(body, title)` (2nd pass).
15. rstrip + "\n"; `problems` → prompts.

---

## 4. PDF classification — `lib/pdf/structure.py`

`structure_sections` (the orchestrator) runs, in order: `_extract_metadata` →
`_detect_body_size` → `_rank_font_sizes` → per-section title/heading/list/paragraph
classification loop → then the pipeline of passes:
`_detect_lists_by_position` → `_merge_paragraphs` → `_detect_code_blocks` →
strip lang labels → `_classify_wording_sections` → `_coalesce_code_paragraphs`
→ `_rescue_unfenced_code` → `_demote_repeated_low_confidence_numbers` →
`_validate_nesting`.

Key functions / constants:
- **Headings:** `_heading_level_from_number(section_num)` returns **depth + 1**
  (`#` reserved for title); `heading_confidence(...)`; `_rank_font_sizes`;
  constants `_HEADING_SIZE_RATIO=1.05`, `_TITLE_SIZE_RATIO=1.2`, `_HEADING_MAX_WORDS=12`.
  **Caveat:** `heading_confidence` hard-pins `KNOWN_SECTIONS` names to `##`,
  which *overrides* the font-size rank. On a font-only paper this can leave a
  known-section child shallower than its non-known parent (inverted nesting),
  and `_validate_nesting` only clamps headings that go too *deep* (never too
  shallow), so it cannot repair the inversion. The heading branch also classifies
  before checking for empty text, so a blank elevated-font line (e.g. on a TOC
  page) can become an empty `HEADING` that `emit.py` renders as `##### `.
- **Lists / bullets:** `_line_starts_with_bullet` (`text[0] in BULLET_CHARS`),
  `_detect_lists_by_position`, `_split_section_by_position` (computes `indent_level`
  via x-position; `_INDENT_TOLERANCE=5.0`), `_join_bullet_marker_lines`
  (`_BULLET_JOIN_MAX_CHARS=3`), `_split_inline_bullets_text` (`_BULLET_SPLIT_RE`).
  All key off `BULLET_CHARS` (types.py). `BULLET_RE`/`NUMBERED_LIST_RE` used in the
  classification loop.
- **Code:** `_detect_code_blocks`, `_coalesce_code_paragraphs`, `_rescue_unfenced_code`
  (`_RESCUE_MIN_CODE_LINES=3`, `_STRUCTURAL_CODE_RE`), `_detect_lang_label` (`_LANG_LABELS`).
- **Nesting:** `_validate_nesting` (no heading skips >1 level deeper; `_SIBLING_FONT_TOL=0.1`).
- **Two-column / reading order:** `_page_is_multicolumn`, `_order_sections_reading`
  (`_COLUMN_GUTTER_MIN=10.0`, `_COLUMN_VOVERLAP_MIN=3.0`).
- **Title:** detection inside the loop; `_TITLE_PID_PREFIX_RE`, `_TITLE_CONT_*`.

---

## 5. HTML rendering — `lib/html/render.py`

`render_body` runs DOM repairs (`_fix_misnested_blocks`, `_fix_misnested_list_items`),
then `_render_children`/`_render_element` dispatch by tag.

- **Headings (H1-vs-H2 bug zone):** `_render_heading` → `level = int(el.name[1])`
  — **the source tag digit, verbatim, NO offset.** Contrast PDF (`depth+1`). The
  contract "body starts at H2; title is the only H1" is enforced only by
  `strip_boilerplate` (removing the title `<h1>`) and `strip_leading_h1` (deleting,
  not demoting). A body `<h1>` that is neither → renders as `#`. Also strips section
  numbers (`SECTION_NUM_PREFIX_RE`) and `_HEADING_SKIP_CLASSES` spans (anchor
  ids / self-links).
- **Lists:** `_render_list` (markers `-`/`1.`; sublist extraction).
- **Code:** `_render_pre` (`_detect_code_language`), `_render_code_block_custom`
  (Schultke `<code-block>`), dascandy/fiets `<div class="code">`.
- **Tables:** `_render_table` → `_render_code_table` / `_render_table_flat` /
  `_denormalize_table` (rowspan/colspan); lossy tables carry `_LOSSY_TABLE_MARKER`.
- **Wording:** `_render_wording_div` emits Pandoc fenced divs `:::wording` /
  `:::wording-add` / `:::wording-remove`.
- **Inline:** `_inline_text` — code/strong/em/links (scheme-filtered; fragment `#`
  links flattened); `ins/del/sub/sup` preserved as raw HTML; `br` → `\n`.
- **Images:** `_render_img` (suppresses empty `src`); `rewrite_imgs_via_manifest`.

---

## 6. PDF emission — `lib/pdf/emit.py`

`emit_markdown(metadata, sections, ...)` dispatches in `_render_section_md` by
`SectionKind`: TITLE/HEADING → `_render_heading_spans`; TABLE → `_render_table`
(row0 = header + `---`); IMAGE → `_render_image` (`![alt](stored_filename)`, alt
from `image_ref.suggested_alt`); CODE → `_render_code_block` (indent from glyph
x ÷ `_estimate_char_width`, default 6.0); LIST → `_render_list_spans`
(`_normalize_bullet` maps `char→*` only `if char in BULLET_CHARS`; **does NOT use
`Section.indent_level`** → nested lists flatten); WORDING* → `_render_wording_section`
(`:::{kind}`); PARAGRAPH → `_render_paragraph_spans`.

`_render_line_spans` merges consecutive monospace spans into one backtick pair.
Tail post-passes here too: `dedup_paragraphs`, `strip_leading_h1` ×2 around
`strip_redundant_body_meta`, then trailing diagnostic markers (truncation, vector
uncertainty, glyph placeholders — appended LAST so counts match a grep of the body).
UNCERTAIN sections emit `<!-- tomd:uncertain:L{start}-L{end} -->` + MuPDF text.
`emit_prompts` builds one self-contained reconcile prompt per UNCERTAIN section.

---

## 7. Data types — `lib/pdf/types.py`

- **`Span`**: `text, font_name, font_size, bold, italic, monospace, bbox, origin, color (packed int), link_url, wording_role`.
- **`Line`**: `spans, bbox, page_num`; computed `text`, `font_size` (max span), `is_bold`.
- **`Block`**: `lines, bbox, page_num`; computed `text`, `font_size`.
- **`Section`**: `kind, text, confidence, heading_level, lines, mupdf_text, spatial_text, page_num, font_size, metadata, columns (table rows→cells→spans), fence_lang, indent_level, image_ref`.
- **`Confidence`**: `HIGH, MEDIUM, LOW, UNCERTAIN`.
- **`SectionKind`**: `TITLE, METADATA, HEADING, PARAGRAPH, LIST, CODE, TABLE, IMAGE, UNCERTAIN, WORDING, WORDING_ADD, WORDING_REMOVE`.

Key constants in types.py: spatial ratios `WORD_GAP_RATIO=0.3`, `LINE_SPACING_RATIO=1.8`,
`PARA_SPACING_RATIO=2.5` (foundation of `extract_spatial`); `SIMILARITY_THRESHOLD=0.82`
(dual-path agreement); `BULLET_CHARS` (line ~184), `BULLET_RE`, `NUMBERED_LIST_RE`,
`KNOWN_SECTIONS` (unnumbered sections promoted to `##`), `is_readable` thresholds.

---

## 8. Symptom → location index

| Symptom | Path | Look here |
|---|---|---|
| Bullet glyph rendered literally / list not detected | PDF | `types.py:BULLET_CHARS` (the set); detect `structure.py:_line_starts_with_bullet`, `_split_section_by_position`; render `emit.py:_normalize_bullet` |
| Nested list flattened (right marker, no indent) | PDF | `emit.py:_render_list_spans` ignores `Section.indent_level` (computed in `structure.py:_split_section_by_position`) |
| Heading at wrong level / body H1 instead of H2 | HTML | `render.py:_render_heading` (`level=int(el.name[1])`, no offset) |
| Heading at wrong level | PDF | `structure.py:_heading_level_from_number` (depth+1), `heading_confidence`, `_rank_font_sizes` |
| Heading carries anchor id / `( <id> )` / section number | HTML | `render.py:_render_heading` + `_HEADING_SKIP_CLASSES` / `SECTION_NUM_PREFIX_RE` |
| Empty heading emitted (`##### `) | PDF | cause: `structure.py:structure_sections` heading branch lacks an empty-text guard; symptom surfaces in `emit.py:_render_heading_spans` |
| Inverted nesting (parent shallower than child) | PDF | `heading_confidence` pins `KNOWN_SECTIONS` to `##`, overriding font rank; `_validate_nesting` clamps too-deep only, never too-shallow |
| Code split across pages / prose swallowed into code | PDF | `structure.py:_detect_code_blocks`, `_coalesce_code_paragraphs`, `_rescue_unfenced_code` |
| Code block indentation wrong | PDF | `emit.py:_render_code_block` + `_estimate_char_width` |
| Body text wrongly inline-code (or code not detected) | PDF | `mono.py:classify_monospace`/`propagate_monospace`; render `emit.py:_render_line_spans` |
| Table mis-detected / split / wrapped cell | PDF | `table.py:detect_tables` (+ `_COLUMN_GAP_THRESHOLD=50`, `_MIN_TABLE_ROWS=2`, orphan absorption) |
| Table garbled / rowspan lost | HTML | `render.py:_render_table` family |
| ins/del wording wrong/missing | PDF | `wording.py:classify_wording` (HSV bands, strikethrough, `_MIN_WORDING_SPANS=5`); render `emit.py:_render_wording_section` |
| `:::wording` markers leaking / wording divs | HTML | `render.py:_render_wording_div` |
| Header/footer/page-number leak | PDF | `cleanup.py:detect_repeating`/`strip_repeating` (`REPEATING_THRESHOLD=0.5`, `Y_TOLERANCE`) |
| Dehyphenation / cross-page join wrong | PDF | `cleanup.py:cleanup_text` (+ `COMPOUND_PREFIXES`, `TERMINAL_PUNCTUATION`) |
| Hidden/widget text leak or over-strip | PDF | `cleanup.py:find_hidden_regions` |
| Front-matter key order / fields | both | `lib/shared.py:format_front_matter` + `FRONT_MATTER_ORDER`; fallback `api.py:_normalize_front_matter` |
| Source metadata block duplicated in body | both | `api.py:_strip_body_metadata_text`; HTML `shared.py:strip_redundant_body_meta`; `strip_freeform_metadata_lines` |
| Author email obfuscated / missing / wrong | HTML | `extract.py` per-generator extractors + `_enrich_reply_to`; `shared.py:deobfuscate_email`, `parse_author_lines`, `enrich_reply_to_names` |
| Date not parsed | both | `shared.py:normalize_date` (ISO / slash=YYYY/MM/DD / natural / European) |
| Generator misdetected / unsupported | HTML | `extract.py:detect_generator`; per-generator metadata + `strip_boilerplate` |
| Field label not mapped (wg21) | HTML | `extract.py:_match_field` / `_FIELD_SYNONYMS` (other generators use inline substring checks) |
| TOC leaking into body / real headings stripped as TOC | both | `lib/toc.py:find_toc_indices` (`_MIN_TOC_RUN=3`, `_MAX_GAP=3`, `_MAX_FUZZY_HEADINGS=200`); api.py `_strip_toc` |
| Slide deck / standards draft wrongly skipped (or not) | PDF | `pipeline.py:_is_slide_deck` / `_is_standards_draft` |
| Image dropped / wrong alt / cap | both | PDF `images.py:finalize_extraction` (`_MAX_IMAGES_PER_PAPER=20`); HTML `images.py:load_html_images` + `render.py:rewrite_imgs_via_manifest`/`_render_img` |
| Whole valid paper → empty/garbage md | PDF | `types.py:is_readable` gate; or a mis-fired `_is_slide_deck`/`_is_standards_draft` |
| `--check-content` coverage/drift surprises | both | `lib/check_content.py` (HTML reuses `detect_generator`+`strip_boilerplate` for source text) |
| QA score off / standardese flagged as code | n/a | `lib/pdf/qa.py` (`_STANDARDESE_PREFIX_RE`, `_looks_like_code`) |
