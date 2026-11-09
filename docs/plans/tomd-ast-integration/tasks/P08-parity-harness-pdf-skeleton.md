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
     - If `result.skipped`, returns `PaperDocument(paper_id=paper_id, is_skipped=True, skip_reason=result.skip_reason, diagnostics=Diagnostics(extra_prompts=result.extra_prompts or tuple(result.prompts or ())))`.
     - Populates `metadata=PaperMetadata.from_dict(result.metadata)`, `images=list(result.images)`, and `diagnostics=Diagnostics(images_truncated=result.images_truncated, source_image_count=result.source_image_count, vector_uncertainty=result.vector_uncertainty, glyph_stats=result.glyph_stats, extra_prompts=result.extra_prompts)`.
   - Update `PaperDocument.get_reconciliation_prompts()` in `domain/document.py` to append `self.diagnostics.extra_prompts` after uncertain-element prompts (returning `None` if both are empty) so `doc.get_reconciliation_prompts() == result.prompts`.

4. **Legacy Bridge (`tomd/parsers/legacy_bridge.py`):**
   - Isolate the post-writer string passes in `PDF_STRING_PASSES`:
     1. `dedup_paragraphs`
     2. `strip_redundant_body_meta`
     3. `strip_orphan_toc_list`
     4. `inject_table_css` (extracted in `lib/pdf/emit.py` and shared between `emit_markdown` and `render_pdf`)
     5. `_strip_leading_h1` (`apply_strip_leading_h1` with the front-matter title)
   - Isolate the API-level normalizer chain in `apply_api_normalizers(md: str, meta: dict[str, Any]) -> str`.
   - `render_pdf(document: PaperDocument) -> str`:
     - Returns `""` when `document.is_skipped`.
     - Calls `MarkdownWriter().write_body(document)`, runs `PDF_STRING_PASSES`, appends trailer markers via `append_trailer_markers(md, document.diagnostics, kept_image_count=len(document.images))`, and finishes with `md.rstrip() + "\n"`.

5. **Dark Entry Point (`tomd/parsers/pdf/__init__.py`):**
   - `PdfParser` implementing `DocumentParser`
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

- `packages/tomd/src/tomd/domain/diagnostics.py`
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
  - docs/plans/tomd-ast-integration/tasks/P08-parity-harness-pdf-skeleton.md (new)
  - packages/tomd/scripts/parity_corpus.py (new)
  - packages/tomd/src/tomd/domain/diagnostics.py
  - packages/tomd/src/tomd/domain/document.py
  - packages/tomd/src/tomd/lib/pdf/emit.py
  - packages/tomd/src/tomd/lib/pdf/pipeline.py
  - packages/tomd/src/tomd/parsers/__init__.py (new)
  - packages/tomd/src/tomd/parsers/base.py (new)
  - packages/tomd/src/tomd/parsers/legacy_bridge.py (new)
  - packages/tomd/src/tomd/parsers/pdf/__init__.py (new)
  - packages/tomd/src/tomd/parsers/pdf/adapter.py (new)
  - packages/tomd/tests/parity/__init__.py (new)
  - packages/tomd/tests/parity/corpus.py (new)
  - packages/tomd/tests/parity/rawblock_allowlist.py (new)
  - packages/tomd/tests/parity/test_pdf_parity.py (new)
  - packages/tomd/tests/parity/test_rawblock_ratchet.py (new)
Checklist output (tails):
  - pytest parity: 79 passed
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
      "pdf:table:code_blocks",
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
