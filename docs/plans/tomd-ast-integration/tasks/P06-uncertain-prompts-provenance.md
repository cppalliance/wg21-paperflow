# P06: Uncertain Regions, Reconcile Prompts, and Block Provenance

## Context

When `tomd` converts a PDF paper into Markdown, it extracts text from each page using two independent algorithms:
1. **MuPDF extraction** (`mupdf_text`): PyMuPDF's native text-block ordering.
2. **Spatial extraction** (`spatial_text`): geometric clustering of spans and lines by bounding box.

When the two extractions agree (`Confidence.HIGH`, `MEDIUM`, or `LOW`), the converter classifies the text into normal structural blocks (headings, paragraphs, lists, code blocks, tables). When they disagree on a page (`Confidence.UNCERTAIN`), `tomd` does not silently guess. Instead, it does two things:

1. **Marks the region in `<pid>.md`** with a 1-based line-range HTML comment above the MuPDF text:
   ```markdown
   <!-- tomd:uncertain:L120-L125 -->

   <MuPDF extracted text>
   ```
2. **Generates an LLM reconciliation prompt in `<pid>.prompts.json`** containing the page number, both extractions (`mupdf_text` and `spatial_text`), and up to 200 characters of the preceding and following confident sections (`context_before` and `context_after`).

Previously, the AST domain (`tomd.domain`) and `MarkdownWriter` only had a placeholder `UncertainElement(prompt, raw_content)` that could not represent dual-path extractions, compute line-range markers, or build reconciliation prompts. Additionally, `BlockElement` had no field to carry source `page` and `Confidence` metadata (which `lib/pdf` tracks on every `Section`).

## Approach

1. **Block Provenance (`Confidence` and `Provenance` in `domain/elements.py`)**
   - Define `Confidence` (`HIGH`, `MEDIUM`, `LOW`, `UNCERTAIN`) and `Provenance(page: int, confidence: Confidence)` directly in `tomd.domain.elements` (re-exported from `tomd.domain`), and update internal callers to import `Confidence` from `tomd.domain.elements` so `domain` never imports from `lib/pdf`.
   - Delete the separate `packages/tomd/src/tomd/domain/provenance.py` file.
   - Keep `provenance: Provenance | None = field(default=None, kw_only=True)` on `BlockElement`.

2. **`UncertainElement` and Reconcile Prompts in `tomd.domain`**
   - Delete top-level `packages/tomd/src/tomd/prompts.py`.
   - `UncertainElement` in `domain/elements.py` holds `mupdf_text: str`, `spatial_text: str`, `page: int`, `text: str = ""`, `context_before: str = ""`, and `context_after: str = ""`.
   - Add `UncertainElement.reconcile_prompt(self) -> str` with the prompt template inline so the entire prompt format is readable in one place.
   - Add `PaperDocument.reconcile_prompts(self) -> list[str] | None` in `domain/document.py` to collect prompts from all `UncertainElement` blocks in document order (returning `None` when there are none, matching `emit_prompts`).

3. **1-Based Line Tracking in `MarkdownWriter` (`writer.py` and `blocks.py`)**
   - Remove `RenderContext` from `writers/markdown/blocks.py`.
   - Simplify `format_uncertain_element(element, line_num=1) -> str` in `blocks.py`:
     - The comment sits on `line_num`, a blank line sits on `line_num + 1`, so the text starts at `text_start = line_num + 2` and ends at `text_end = text_start + text.count("\n")`.
   - Track `line_num = 1` directly inside `MarkdownWriter.write` in `writer.py`:
     - Every emitted block `b` (including front matter and each non-empty body element) is followed by a blank separator line (`"\n\n"`), so it advances `line_num += b.count("\n") + 2`.
     - Empty or whitespace-only blocks (including empty `Heading`s) are skipped without advancing `line_num`.

## Files to Modify

- `packages/tomd/src/tomd/domain/__init__.py`
- `packages/tomd/src/tomd/domain/document.py`
- `packages/tomd/src/tomd/domain/elements.py`
- `packages/tomd/src/tomd/domain/provenance.py` (delete)
- `packages/tomd/src/tomd/prompts.py` (delete)
- `packages/tomd/src/tomd/lib/pdf/types.py`
- `packages/tomd/src/tomd/writers/markdown/blocks.py`
- `packages/tomd/src/tomd/writers/markdown/writer.py`
- `packages/tomd/tests/domain/test_domain_models.py`
- `packages/tomd/tests/writers/markdown/test_blocks.py`
- `packages/tomd/tests/writers/markdown/test_uncertain_and_prompts.py`
- `docs/plans/tomd-ast-integration/tasks/P06-uncertain-prompts-provenance.md`

## Reuse

- `tomd.domain.elements.UncertainElement` and `tomd.domain.document.PaperDocument` as the home for reconcile prompt generation (matching how P02 placed metadata fallback on `PaperMetadata`).
- `tomd.lib.pdf.emit.emit_markdown` and `tomd.lib.pdf.emit.emit_prompts` (`packages/tomd/src/tomd/lib/pdf/emit.py`) as the byte-parity oracle in tests.
- `make_section`, `make_line`, `make_span` (`packages/tomd/tests/conftest.py`) in `test_uncertain_and_prompts.py`.

## Steps

- [x] Move `Confidence` and `Provenance` into `packages/tomd/src/tomd/domain/elements.py`, update imports in `domain/__init__.py` and `lib/pdf/types.py`, and delete `packages/tomd/src/tomd/domain/provenance.py`.
- [x] Add `reconcile_prompt()` to `UncertainElement` in `domain/elements.py` and `reconcile_prompts()` to `PaperDocument` in `domain/document.py`, then delete `packages/tomd/src/tomd/prompts.py`.
- [x] Simplify `format_uncertain_element` in `writers/markdown/blocks.py`, remove `RenderContext`, and inline the `line_num` loop in `MarkdownWriter.write` (`writers/markdown/writer.py`).
- [x] Update `test_domain_models.py` and `test_uncertain_and_prompts.py` to use `doc.reconcile_prompts()` and `conftest.py` helpers, trimming test boilerplate.
- [x] Run pytest, ruff, and pyright to verify all checks pass.

## Verification

- `uv run --package tomd pytest packages/tomd/tests -q`
- `uv run ruff check packages tests`
- `uv run pyright packages/tomd/src/tomd packages/tomd/tests`
- `git status --short`
