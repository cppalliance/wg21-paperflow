---
name: tomd-surgical-edits
description: Use when changing the tomd PDF/HTML-to-Markdown converter (packages/tomd) - fixing a conversion-quality ticket, or changing how headings, lists, code blocks, tables, ins/del wording, images, metadata, or YAML front matter are detected or emitted, or pinning where a markdown output defect originates.
---

# tomd Surgical Edits

## Overview

`tomd` (`packages/tomd`) converts WG21 paper PDFs and HTML to Markdown,
**deterministically** (no LLM). A clean change means four things in order:
**reproduce on a real paper → localize to the right module AND layer → make the
minimal change → update the blast radius and verify.**

The package `CLAUDE.md` File Map will get you to the right *file*. This skill
covers what the File Map does not, and what trips people up: getting a repro,
the layering, the golden-fixture blast radius, and the traps below.

**Core principle: never edit tomd from the source code alone. Reproduce the
defect on a real paper first, and regenerate golden fixtures after.** Skipping
either is how "surgical" edits become regressions.

## The mental model: two converters, two post-pass layers

`api.py:convert_paper_full` dispatches by suffix, then runs format-agnostic
post-passes. Any output defect lives in one of three places - decide which
*before* editing:

1. **Format converter** - `lib/pdf/pipeline.py:run_pipeline` or
   `lib/html/convert.py:convert_html`. Most detection/emission bugs.
2. **The converter's own tail post-pass** - end of `convert_html`; `emit.py`.
3. **api.py format-agnostic post-pass** - `_normalize_front_matter`,
   `_strip_body_metadata_text`, `strip_freeform_metadata_lines`,
   `strip_leading_h1`, `_strip_toc`.

PDF flows `Block → Line → Span` → `Section` (`compare_extractions`) →
classified `Section`s (`structure_sections`) → markdown (`emit.py`). HTML walks
the BeautifulSoup DOM straight to markdown in `render.py`.

**Full pipeline step order, every module's job, the data types, and a
symptom → function index live in `architecture.md` (this folder). Read it to
localize - do not re-derive the map by grepping.**

## Procedure

1. **Reproduce on a real paper.** A staged corpus exists at `~/wg21-data`:
   `export WG21_DATA_DIR=~/wg21-data` (NOT set by default; in a fresh shell
   prefix one-off commands, e.g. `WG21_DATA_DIR=~/wg21-data uv run paperflow
   convert <PID>`). If the ticket's paper isn't staged,
   `paperflow download <PID> && paperflow convert <PID>`. Read the output at
   `$WG21_DATA_DIR/paperstore/<pid>.md`; diff against the source side-by-side
   with `uv run preview <PID>`. (The golden source papers live in
   `packages/tomd/papers/` and are gitignored/usually absent, so this corpus is
   your repro, not the fixtures.)
2. **Identify the path** - PDF or HTML, from the source suffix.
3. **Localize** with the symptom → location index in `architecture.md`. Confirm
   the function still exists by grepping its name (line numbers drift).
4. **Decide the layer** (converter / converter tail / api.py post-pass).
5. **Make the minimal change.** Tunable values are named module-level constants
   (root CLAUDE.md invariant) - many detection bugs are a constant or a set
   member, not logic. Keep it deterministic; library code returns data, never
   writes.
6. **Update the blast radius.** Almost any detection/emission change alters
   golden output. Regenerate the affected `tests/fixtures/golden/*.golden.md`
   (exact-string compare) per `tests/fixtures/golden/README.md`, which needs the
   source paper present in `packages/tomd/papers/{stem}.{html,pdf}`. The golden
   test **`pytest.skip`s silently when the source is absent** - a skipped golden
   is not a passing one, so stage the sources before trusting the suite. Goldens
   encode *current* output, sometimes a current defect, so a correct fix may
   intentionally change golden content (expected, not a regression). Add/adjust
   unit tests too.
7. **Verify.** `uv run --package tomd pytest`, reconvert the repro paper, and
   re-check with `paperflow convert <PID> --check-content` / `--qa` and
   `uv run preview <PID>`.

## Quick symptom → location (full table in architecture.md)

| Symptom | Where |
|---|---|
| Bullet glyph literal / list not detected (PDF) | `types.py:BULLET_CHARS`; `structure.py` list fns; `emit.py:_normalize_bullet` |
| Body heading H1 instead of H2 (HTML) | `render.py:_render_heading` (`level=int(el.name[1])`, no offset) |
| Heading wrong level (PDF) | `structure.py:_heading_level_from_number` (depth+1), `heading_confidence` |
| Code split / prose-in-code (PDF) | `structure.py:_detect_code_blocks`/`_coalesce_code_paragraphs`/`_rescue_unfenced_code` |
| Table mis-detected/split (PDF) | `table.py:detect_tables` (+ constants) |
| ins/del wording (PDF) | `wording.py:classify_wording`; render `emit.py:_render_wording_section` |
| Header/footer/page-number leak (PDF) | `cleanup.py:detect_repeating`/`strip_repeating` |
| Front-matter order/fields | `shared.py:format_front_matter` + `FRONT_MATTER_ORDER`; `api.py:_normalize_front_matter` |
| Metadata block duplicated in body | `api.py:_strip_body_metadata_text`; HTML `shared.py:strip_redundant_body_meta` |
| Generator misdetected/unsupported (HTML) | `extract.py:detect_generator` |
| TOC leaking / over-stripped | `lib/toc.py:find_toc_indices`; `api.py:_strip_toc` |
| Slide deck/standards draft skip | `pipeline.py:_is_slide_deck`/`_is_standards_draft` |

## Traps (each has bitten a real change)

- **No repro without the corpus.** `WG21_DATA_DIR` is not set by default and the
  golden source papers are gitignored. Stage the paper (`paperflow download` /
  `convert`) instead of reasoning from code alone.
- **Golden fixtures encode current output.** A detection/emission change that
  does not regenerate `tests/fixtures/golden/*.golden.md` fails the exact-string
  golden test. Regeneration needs the source paper present.
- **Two bullet sets.** `types.py:BULLET_CHARS` (list detection, the canonical
  one) vs `wg21.py:_BULLET_CHARS` (metadata author-line stripping; includes more
  glyphs). They are not cross-referenced. Fix list bugs in `types.py`; do not
  unify them casually.
- **`indent_level` is computed but never read by emit.** `structure.py` stores it
  on each `Section`; `emit.py:_render_list_spans` ignores it, so nested lists
  render flat. Recognizing a bullet ≠ indenting it - those are separate changes.
- **`__init__.py` is re-exports only.** Logic lives in named modules
  (`pipeline.py`, `structure.py`, `lib/shared.py`, `html/convert.py`). The File
  Map sometimes describes `__init__.py` as holding logic.
- **Docs drift.** The File Map names `_canonicalize_front_matter`; the code has
  `_normalize_front_matter`. Use the map to find the file; trust the code.
- **PDF and HTML do NOT share heading logic.** PDF derives levels from
  numbering depth (`depth+1`, reserves `#` for title); HTML emits the source tag
  digit verbatim. A "fix it like the other path" assumption is wrong.
- **A "fix" is often document-relative or a signal conflict, not a blanket
  transform.** Before changing how a level/marker is computed, check whether
  some inputs already conform: HTML papers come both `<h1>`-rooted and
  `<h2>`-rooted, so a blanket `+1` corrupts the already-correct ones - shift
  relative to the document's minimum heading instead. PDF heading *inversions*
  (parent shallower than child) come from `KNOWN_SECTIONS` pinning a section to
  `##` and overriding font-size depth; `_validate_nesting` only clamps headings
  that are too *deep*, never too *shallow*, so it cannot repair an inverted
  parent on its own.
- **Three post-pass layers run `strip_leading_h1`/dedup** (emit.py, convert.py,
  api.py). A front-matter/H1 fix may belong to a specific one.

## Invariants (from root + package CLAUDE.md)

- Tunable numbers are named module-level constants - no bare literals.
- Library returns data; the CLI persists. Never add writes inside tomd.
- `__init__.py` carries only re-exports. New `.py` files carry the BSL-1.0 header.
- Honest output: never silently drop content. Uncertain PDF regions emit
  `<!-- tomd:uncertain:... -->` plus a reconcile prompt.
- Use `logging`, never `print`. Keep conversion deterministic.
