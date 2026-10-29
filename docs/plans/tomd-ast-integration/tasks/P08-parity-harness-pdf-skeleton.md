# P08: Parity Harness, Ratchet, PDF Skeleton, and Legacy Bridge

| Wave | Deps | Parallel with | Size | Risk |
|------|------|---------------|------|------|
| 2 | P05, P06, P07 | P07 (when `RawBlock` is present) | L | high |

## Context

With the domain AST and `MarkdownWriter` extensions from Wave 1 (P03-P07) in place, P08 stands up the dark PDF conversion path and parity verification harness that every Wave 2 and Wave 3 task relies on:
1. Extract the input-mutating pre-passes from `emit_markdown` (`assign_emdash_nesting` and `fold_table_continuations`) so `run_pipeline` runs them idempotently before storing `result.sections`.
2. Introduce `tomd/parsers/` with the `DocumentParser` protocol, the PDF skeleton adapter (`sections_to_document`), and `parsers/legacy_bridge.py` (`render_pdf`).
3. Stand up `tests/parity/` (converter-level and API-level byte-parity tests + the `RawBlock` origin ratchet) and `packages/tomd/scripts/parity_corpus.py`.

## Approach

1. **Idempotent Pre-Pass Extraction (`lib/pdf/emit.py` and `lib/pdf/pipeline.py`):**
   - Rename `_assign_emdash_nesting` to `assign_emdash_nesting(sections: list[Section]) -> None`.
   - Extract `fold_table_continuations(sections: list[Section]) -> list[Section]` in `lib/pdf/emit.py`. Update `sections[:]` in place when removing folded continuation indices and return `sections`, so calling `fold_table_continuations` a second time on either the same list reference or the returned list is a no-op.
   - In `lib/pdf/pipeline.py:run_pipeline`, call `assign_emdash_nesting(sections)` and `sections = fold_table_continuations(sections)` right after `drop_leaked_toc_entries(sections)` and before `emit_markdown` / `emit_prompts`. Keep both calls at the top of `emit_markdown` so direct unit tests of `emit_markdown` remain unchanged.

2. **Parser Protocol (`tomd/parsers/base.py` and `tomd/parsers/__init__.py`):**
   - Define `DocumentParser` `Protocol` with `parse(self, path: Path) -> PaperDocument`.
   - Re-export `DocumentParser` in `tomd/parsers/__init__.py` with `__all__ = ["DocumentParser"]`.

3. **PDF Skeleton Adapter (`tomd/parsers/pdf/adapter.py`):**
   - `SectionAdapter = Callable[[Section], list[BlockElement]]` and `ADAPTERS: dict[SectionKind, SectionAdapter] = {}`.
   - `_raw_origin(sec: Section) -> str`: returns `f"pdf:table:{sec.table_strategy}"` when `sec.kind == SectionKind.TABLE` and `sec.table_strategy` is non-empty, otherwise `f"pdf:{sec.kind.value}"`.
   - Default fallback `_adapt_raw_section(sec: Section) -> list[BlockElement]`:
     - Renders `rendered = _render_section_md(sec)`.
     - Applies `emit_markdown`'s skip rules: drops if `not rendered.strip()` or if `sec.kind in (SectionKind.TITLE, SectionKind.HEADING)` and `not rendered.lstrip("#").strip()`.
     - Returns `[RawBlock(markdown=rendered, origin=_raw_origin(sec), provenance=Provenance(page=sec.page_num, confidence=sec.confidence))]`.
   - `UNCERTAIN` sections map directly to `UncertainElement` with `mupdf_text=sec.mupdf_text`, `spatial_text=sec.spatial_text`, `page=sec.page_num`, `text=sec.text`, and 200-char `context_before` / `context_after` from neighboring non-uncertain sections in `result.sections`.
   - `sections_to_document(result: PipelineResult, *, paper_id: str = "") -> PaperDocument`:
     - If `result.skipped`, returns `PaperDocument(paper_id=paper_id, is_skipped=True, skip_reason=result.skip_reason, diagnostics=Diagnostics(extra_prompts=tuple(result.prompts or ())))`.
     - Populates `metadata=PaperMetadata.from_dict(result.metadata)`, `images=list(result.images)`, and `diagnostics=Diagnostics(images_truncated=result.images_truncated, source_image_count=result.source_image_count, vector_uncertainty=result.vector_uncertainty, glyph_stats=result.glyph_stats, extra_prompts=tuple(wording_prompts))`.
   - Update `PaperDocument.reconcile_prompts()` in `domain/document.py` to append `list(self.diagnostics.extra_prompts)` after uncertain-element prompts (returning `None` if both are empty) so `doc.reconcile_prompts() == result.prompts`.

4. **Legacy Bridge (`tomd/parsers/legacy_bridge.py`):**
   - Isolate the post-writer string passes in `PDF_STRING_PASSES`:
     1. `dedup_paragraphs`
     2. `strip_redundant_body_meta`
     3. `strip_orphan_toc_list`
     4. `_inject_table_css` (identical `<style>` injection when `"<table "` is in `md`)
     5. `_strip_leading_h1` (`apply_strip_leading_h1(md, document.metadata.title)` when front matter was emitted)
   - `render_pdf(document: PaperDocument) -> str`:
     - Returns `""` when `document.is_skipped`.
     - Calls `MarkdownWriter().write_body(document)`, runs `PDF_STRING_PASSES`, appends trailer markers via `append_trailer_markers(md, document.diagnostics, kept_image_count=len(document.images))`, and finishes with `md.rstrip() + "\n"`.

5. **Dark Entry Point (`tomd/parsers/pdf/__init__.py`):**
   - `parse_pdf(path: Path, *, extract_vector: bool = False, whiteout_text: bool = False) -> PaperDocument`
   - `convert_pdf_dark(path: Path, *, extract_vector: bool = False, whiteout_text: bool = False) -> str`

6. **Parity Harness, Ratchet, and Corpus Script:**
   - `packages/tomd/tests/parity/corpus.py`: discovers all golden PDF stems from `tests/fixtures/golden/stems/*.txt`, the 4 `synth_*.pdf` fixtures, and `p2583r3-gold-standard.pdf`.
   - `packages/tomd/tests/parity/test_pdf_parity.py`:
     - Converter-level parity: `run_pipeline(path)` vs `parse_pdf(path)` + `render_pdf(doc)` (checking both `md` and `prompts`).
     - API-level parity: legacy `convert_paper_full` vs dark output passed through the API normalizer chain with a fixed `meta` dict.
     - Unit tests for `assign_emdash_nesting` and `fold_table_continuations` idempotence.
   - `packages/tomd/tests/parity/rawblock_allowlist.py` & `test_rawblock_ratchet.py`: asserts the set of `RawBlock.origin` values emitted across the PDF corpus equals `PDF_RAWBLOCK_ALLOWLIST` exactly.
   - `packages/tomd/scripts/parity_corpus.py`: runs converter-level and API-level parity over `--data-dir` (default `$WG21_DATA_DIR`).

## Files to Modify

- `packages/tomd/src/tomd/domain/document.py`
- `packages/tomd/src/tomd/lib/pdf/emit.py`
- `packages/tomd/src/tomd/lib/pdf/pipeline.py`
- `packages/tomd/src/tomd/parsers/__init__.py` (new)
- `packages/tomd/src/tomd/parsers/base.py` (new)
- `packages/tomd/src/tomd/parsers/legacy_bridge.py` (new)
- `packages/tomd/src/tomd/parsers/pdf/__init__.py` (new)
- `packages/tomd/src/tomd/parsers/pdf/adapter.py` (new)
- `packages/tomd/tests/parity/__init__.py` (new)
- `packages/tomd/tests/parity/corpus.py` (new)
- `packages/tomd/tests/parity/rawblock_allowlist.py` (new)
- `packages/tomd/tests/parity/test_pdf_parity.py` (new)
- `packages/tomd/tests/parity/test_rawblock_ratchet.py` (new)
- `packages/tomd/scripts/parity_corpus.py` (new)

## Do Not

- Modify any golden snapshot or baseline to make parity pass.
- Convert any section family (other than `UNCERTAIN`) to structured AST elements in this PR.
- Wire `convert_pdf_dark` into `tomd/api.py`.

## Verification

```bash
uv run --package tomd pytest packages/tomd/tests/parity -q
uv run --package tomd pytest packages/tomd/tests -q
uv run ruff check packages tests
uv run pyright packages/tomd/src/tomd packages/tomd/tests
git status --short
```

## Handoff

```
Status: done
Files changed:
  - docs/plans/tomd-ast-integration/tasks/P07-escaping-and-rawblock.md
  - docs/plans/tomd-ast-integration/tasks/P08-parity-harness-pdf-skeleton.md
  - packages/tomd/scripts/parity_corpus.py (new)
  - packages/tomd/src/tomd/domain/document.py
  - packages/tomd/src/tomd/domain/elements.py
  - packages/tomd/src/tomd/lib/body/abstract.py
  - packages/tomd/src/tomd/lib/pdf/docling_backend.py
  - packages/tomd/src/tomd/lib/pdf/emit.py
  - packages/tomd/src/tomd/lib/pdf/pipeline.py
  - packages/tomd/src/tomd/lib/pdf/structure.py
  - packages/tomd/src/tomd/lib/pdf/table.py
  - packages/tomd/src/tomd/parsers/__init__.py (new)
  - packages/tomd/src/tomd/parsers/base.py (new)
  - packages/tomd/src/tomd/parsers/legacy_bridge.py (new)
  - packages/tomd/src/tomd/parsers/pdf/__init__.py (new)
  - packages/tomd/src/tomd/parsers/pdf/adapter.py (new)
  - packages/tomd/src/tomd/writers/markdown/blocks.py
  - packages/tomd/src/tomd/writers/markdown/tables.py
  - packages/tomd/tests/conftest.py
  - packages/tomd/tests/parity/__init__.py (new)
  - packages/tomd/tests/parity/corpus.py (new)
  - packages/tomd/tests/parity/rawblock_allowlist.py (new)
  - packages/tomd/tests/parity/test_pdf_parity.py (new)
  - packages/tomd/tests/parity/test_rawblock_ratchet.py (new)
  - packages/tomd/tests/test_cleanup.py
  - packages/tomd/tests/test_emit.py
  - packages/tomd/tests/test_glyphs.py
  - packages/tomd/tests/test_images.py
  - packages/tomd/tests/test_regex_patterns.py
  - packages/tomd/tests/test_structure.py
  - packages/tomd/tests/test_table.py
  - packages/tomd/tests/test_table_passes.py
  - packages/tomd/tests/writers/markdown/test_markers.py
Checklist output (tails):
  - pytest parity + domain + writers + emit + cleanup: 442 passed in 22.86s
  - ruff check packages tests: All checks passed!
  - pyright domain + writers + parsers + parity + script: 0 errors, 0 warnings, 0 informations
Corpus size (papers) at converter level / API level:
  - 33 PDFs (28 golden stems + 4 synth fixtures + p2583r3-gold-standard.pdf)
  - 37 converter-level cases (33 default + 4 synth fixtures with extract_vector=True)
  - 33 API-level cases
Initial ratchet allow-list (paste):
  PDF_RAWBLOCK_ALLOWLIST = frozenset({
      "pdf:code",
      "pdf:heading",
      "pdf:image",
      "pdf:list",
      "pdf:paragraph",
      "pdf:table:html_table",
      "pdf:table:pipe_table",
      "pdf:title",
      "pdf:wording",
      "pdf:wording-add",
      "pdf:wording-remove",
  })
Anything in emit_markdown that mutates input besides the two pre-passes:
  - None. Only assign_emdash_nesting and fold_table_continuations mutate input sections.
Known divergences found:
  - Until P02a merges, legacy format_front_matter emits a bare `reply-to:` line when
    `result.metadata["reply-to"] == []` (8 single-page/synth fixtures), whereas
    PaperMetadata.to_dict() omits empty lists. `render_pdf` in `legacy_bridge.py`
    bridges this via `_apply_legacy_empty_reply_to` so converter-level parity is
    byte-identical both before and after P02a.
Open questions:
  - None.
```

# Adversarial Review Follow-ups

Adversarial review of the P08 working tree. Items are ordered by severity and resolved in place.

## R1. Preserve unstripped `sec.text` on `UncertainElement` in `sections_to_document` (high)

`sections_to_document` passed `text=sec.text.rstrip()` when constructing `UncertainElement`, whereas legacy `emit_prompts` falls back to unstripped `sec.text` (`sec.mupdf_text or sec.text` and `sec.spatial_text or sec.text`) when `mupdf_text` or `spatial_text` is empty. `format_uncertain_element` in `blocks.py` already calls `element.text.rstrip()` when rendering the Markdown body.

Fix: pass `text=sec.text` in `packages/tomd/src/tomd/parsers/pdf/adapter.py` and cover empty `mupdf_text` with trailing whitespace on `sec.text` in `packages/tomd/tests/parity/test_pdf_parity.py:test_sections_to_document_skipped_and_extra_prompts`.

## R2. Extract `_apply_legacy_empty_reply_to` helper in `legacy_bridge.py` (medium)

The pre-P02a empty `reply-to` front-matter bridge was inlined inside `render_pdf`, obscuring the main pipeline flow.

Fix: extract `_apply_legacy_empty_reply_to(md: str, document: PaperDocument) -> str` in `packages/tomd/src/tomd/parsers/legacy_bridge.py`.

## R3. Make `Confidence` a `StrEnum` and import directly from `tomd.domain.elements` (medium)

`Confidence` in `tomd.domain.elements` inherited from `Enum` instead of `StrEnum`, and callers in `lib/` and `tests/` imported `Confidence` indirectly through `tomd.lib.pdf.types`.

Fix: change `class Confidence(StrEnum):` in `packages/tomd/src/tomd/domain/elements.py` and update callers across `packages/tomd/src/tomd/lib/` and `packages/tomd/tests/` to import `Confidence` directly from `tomd.domain.elements`.

## R4. Import public normalizers and exercise `convert_paper_full` in `parity_corpus.py` (medium)

`parity_corpus.py` and `test_pdf_parity.py` imported private `_normalize_front_matter`, `_strip_body_metadata_text`, and `_strip_toc` from `tomd.api` instead of the public functions in `tomd.writers.markdown.normalizers`, and `parity_corpus.py` computed `legacy_api_md` via `_apply_api_normalizers(legacy.md, meta)` rather than calling `convert_paper_full`.

Fix: import `normalize_front_matter`, `strip_body_metadata_text`, and `strip_toc` from `tomd.writers.markdown.normalizers`, and compute `legacy_api_md` in `packages/tomd/scripts/parity_corpus.py` by patching `tomd.api.run_pipeline` and calling `convert_paper_full(paper_id, pdf_path, meta).markdown`.

## R5. Remove unused `parity/conftest.py` and unify `cached_run_pipeline` signature (low)

`packages/tomd/tests/parity/conftest.py` defined unused fixtures, and `corpus.py` / `test_pdf_parity.py` duplicated `_reuse_pipeline` wrapper closures to accept `whiteout_text`.

Fix: delete `packages/tomd/tests/parity/conftest.py` and accept `whiteout_text: bool = False` directly on `cached_run_pipeline` in `packages/tomd/tests/parity/corpus.py`.

## R6. Sync P07 review cleanups and minor hygiene in `emit.py` and `test_pdf_parity.py` (low)

Sync P07's removal of `from __future__ import annotations` in `blocks.py` and `tables.py` and duplicate escape tests in `test_cleanup.py` and `test_emit.py`, use `sec.table_continuation` directly in `fold_table_continuations` in `packages/tomd/src/tomd/lib/pdf/emit.py`, and use `\u2013` (en-dash) in `test_assign_emdash_nesting_idempotent`.
