# P06 Uncertain element, reconcile prompts, provenance

| Wave | Deps | Parallel with | Size | Risk |
|------|------|---------------|------|------|
| 1 | P02 | P03, P04, P05, P07 | M | medium |

## Goal

Make uncertain regions round-trip: the element carries both extractions and its
neighbor context, the writer reproduces the `<!-- tomd:uncertain:L{a}-L{b} -->` marker
with legacy line arithmetic, and reconcile prompts are built from the AST. Add optional
provenance (page, confidence) to blocks.

## Read first

- `lib/pdf/emit.py`: `emit_markdown` (the `line_num` arithmetic at the top of the loop
  and in the UNCERTAIN branch), `emit_prompts` (line 1344)
- `lib/pdf/types.py`: `Confidence`, `Section` fields `mupdf_text`, `spatial_text`,
  `page_num`, `confidence`
- `domain/elements.py` `UncertainElement`, `writers/markdown/blocks.py`,
  `writers/markdown/writer.py`
- Tests: `tests/test_emit.py` uncertain and prompts cases; golden prompts files
  (`tests/fixtures/golden/*.prompts.json`)

## Change

1. Move `Confidence` into `domain/` (for example `domain/provenance.py`); `lib/pdf/types.py`
   re-exports it. Add `Provenance(page: int, confidence: Confidence)`.
2. `BlockElement` gains `provenance: Provenance | None = field(default=None, kw_only=True)`.
   Writers ignore it.
3. `UncertainElement(mupdf_text: str, spatial_text: str, page: int, text: str,
   context_before: str = "", context_after: str = "")`. `text` is what is emitted (the
   MuPDF version). `context_*` are the at-most-200-character neighbor snippets that
   `emit_prompts` computes today; the adapter fills them, so the AST never has to
   reproduce `Section.text` projections.
4. Writer: a render context tracks `line_num` with exactly the legacy arithmetic:
   start `fm.count("\n") + 3` if front matter was emitted else `1`; after a normal block
   `+= rendered.count("\n") + 2`; for an uncertain block
   `text_start = line_num + 2`, `+= text_lines + 3`, marker
   `<!-- tomd:uncertain:L{text_start}-L{text_start + text_lines - 1} -->`. Blocks that
   render to empty strings are skipped exactly as in `emit_markdown`.
5. `tomd/prompts.py` (new): `build_reconcile_prompts(document) -> list[str] | None`, a
   port of `emit_prompts` using `UncertainElement` fields. Prompt text must be
   byte-identical; keep the strings as module constants.

## Do not

- Change marker format or prompt wording. Do not touch `emit.py`.
- Compute context from neighboring elements; it is data on the element.

## Tests

Twin tests: build `Section` lists with uncertain sections at the start, middle, end,
adjacent to each other, and after empty-rendering sections; build the equivalent AST;
assert writer output equals `emit_markdown(...)` and `build_reconcile_prompts` equals
`emit_prompts`. Include a case with and without front matter (line offset).

## Acceptance

Checklist green; twin tests byte-equal.

## Handoff (fill in at the end)

```
Status: done
Files changed:
  docs/plans/tomd-ast-integration/tasks/P06-uncertain-prompts-provenance.md
  packages/tomd/src/tomd/domain/__init__.py
  packages/tomd/src/tomd/domain/elements.py
  packages/tomd/src/tomd/domain/provenance.py
  packages/tomd/src/tomd/lib/pdf/types.py
  packages/tomd/src/tomd/prompts.py
  packages/tomd/src/tomd/writers/markdown/blocks.py
  packages/tomd/src/tomd/writers/markdown/writer.py
  packages/tomd/tests/domain/test_domain_models.py
  packages/tomd/tests/writers/markdown/test_blocks.py
  packages/tomd/tests/writers/markdown/test_uncertain_and_prompts.py
Checklist output (tails):
  imports:     python -c "import tomd.domain, tomd.lib.pdf, tomd.prompts" (exit 0)
  pytest:      493 passed, 5 warnings in 0.39s
  ruff:        All checks passed!
  pyright:     0 errors, 0 warnings, 0 informations
Known divergences found:
  None. UncertainElement uses @dataclass(slots=True) so its required `text: str`
  field descriptor cleanly overrides `BlockElement.text` read-only property at
  both runtime and static type checking.
Open questions:
  None.
```

---

# Review follow-ups

Adversarial review of the P06 working tree. Items are ordered by severity and resolved in place.

## R1. Encapsulate `line_num` tracking in `RenderContext` and simplify `MarkdownWriter.write` / `blocks.py` (medium)

- Requirement 4 specifies a render context tracking `line_num`. Instead, `line_num` arithmetic was split across `MarkdownWriter.write` (`front.count("\n") + 3 if front else 1` and `line_num += rendered.count("\n") + 2`) and `blocks.format_uncertain_element` (which returned a `(rendered, next_line_num)` 2-tuple that `_write_uncertain_element` had to unpack and discard).
- Because `format_uncertain_element` joins the comment marker and `text` with `\n\n` into one block string (`f"{comment}\n\n{text}"`), its line advancement `rendered.count("\n") + 2` is algebraically identical to `text_lines + 3` (`(2 + text_lines - 1) + 2 == text_lines + 3`).
- `MarkdownWriter.write` also duplicated `@singledispatch` type checks (`isinstance(elem, UncertainElement)`, `isinstance(elem, Table)`, `isinstance(elem, BlockElement)`, `isinstance(elem, Heading)`), and placed empty-heading suppression in `writer.py` instead of `_write_heading` in `blocks.py` (so `write_element(Heading.from_text(2, "   "))` returned `"##    "` instead of `""`).

Fix:
- Make `_write_heading` in `writers/markdown/blocks.py` return `""` when `not content.strip()`.
- Make `format_uncertain_element(element, line_num=1) -> str` return only the formatted block string.
- Add `RenderContext` (`from_front_matter`, `render_block`) in `writers/markdown/blocks.py` and use it in `MarkdownWriter.write`, removing the redundant `Heading`, `UncertainElement`, `Table`, `write_table`, and `format_uncertain_element` imports and branches from `writer.py`.

## R2. Narrow `tomd/prompts.py` exports and extract per-element helper (low)

- `tomd/prompts.py` exported 7 internal string constants (including `CODE_FENCE = "```"`) in `__all__` alongside `build_reconcile_prompts`.
- `build_reconcile_prompts` mixed document filtering with single-element prompt formatting.

Fix:
- Extract `_format_reconcile_prompt(elem: UncertainElement) -> str` and keep `build_reconcile_prompts` focused on filtering `document.elements`.
- Narrow `__all__` in `tomd/prompts.py` to `["build_reconcile_prompts"]` while keeping the prompt strings as module constants.

## R3. Use `Self` return annotations and remove redundant `from __future__ import annotations` (low)

- `from_text` factories in `domain/elements.py` used stringified class return annotations instead of `Self`.
- `writers/markdown/blocks.py` and `lib/pdf/types.py` carried unnecessary `from __future__ import annotations` imports.

Fix:
- Use `-> Self` on `from_text` factories in `domain/elements.py`.
- Remove `from __future__ import annotations` from `writers/markdown/blocks.py` and `lib/pdf/types.py`.

## R4. Consolidate `test_uncertain_and_prompts.py`, cover multi-line and prompt boundary cases, and clean up `test_domain_models.py` (medium)

- Every confident section preceding an `UncertainElement` in `test_uncertain_and_prompts.py` rendered as a single line (`rendered.count("\n") == 0`), so `rendered.count("\n")` in `line_num += rendered.count("\n") + 2` was never exercised for non-zero newline counts.
- Missing prompt boundary cases: `context_after` > 200 characters adjacent to an uncertain block, asymmetric `mupdf_text`/`spatial_text` empty fallbacks (only one empty), and whitespace-only confident neighbors (`ctx_before` stripping to `""`).
- `test_domain_models.py` had a function-local import `from tomd.lib.pdf.types import Confidence as PdfConfidence`.

Fix:
- Fix `Span.bbox` in `_make_section` so multi-line `SectionKind.CODE` sections render as multi-line code blocks in `emit_markdown`, and add a multi-line `CodeBlock` before an `UncertainElement` case.
- Consolidate `test_uncertain_and_prompts.py` with `@pytest.mark.parametrize` and add the missing `context_after` > 200 chars, asymmetric extraction fallback, and whitespace-neighbor cases.
- Move the `PdfConfidence` import to module top level in `test_domain_models.py`.

## Resolution log

| Item | Outcome |
|------|---------|
| R1 | Done. Added `RenderContext` in `blocks.py`, simplified `format_uncertain_element` to return `str`, handled empty headings in `_write_heading`, and simplified `MarkdownWriter.write`. |
| R2 | Done. Extracted `_format_reconcile_prompt` and narrowed `tomd/prompts.py` `__all__` to `["build_reconcile_prompts"]`. |
| R3 | Done. Used `-> Self` on `from_text` factories in `domain/elements.py` and removed `from __future__ import annotations` from `blocks.py` and `lib/pdf/types.py`. |
| R4 | Done. Consolidated `test_uncertain_and_prompts.py` with `@pytest.mark.parametrize`, added multi-line code block and prompt boundary cases, and moved `PdfConfidence` import to top level in `test_domain_models.py`. |
