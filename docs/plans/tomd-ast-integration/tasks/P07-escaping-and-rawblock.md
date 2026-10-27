# P07: Writer Escaping Policy and `RawBlock`

| Wave | Deps | Parallel with | Size | Risk |
|------|------|---------------|------|------|
| 1 | P02 | P03, P04, P05, P06 | M | high (byte drift) |

## Context

Today, Markdown escaping is scattered across the legacy PDF and HTML renderers:
- `escape_leading_atx` in `lib/pdf/cleanup.py` escapes a paragraph line that starts with `#`..`######` followed by whitespace or EOL so it is not misparsed as an ATX heading.
- `_escape_italic_text` in `lib/pdf/emit.py` escapes `\\`, `*`, `_`, backticks, and leading block markers (`-`, `*`, `+`, `>`, `#`, `1.`) inside synthesized `*<caption>*` italic wrappers (used for image captions and sub-captions). Ordinary inline `EmphasisSpan` nodes in prose are NOT escaped this way.
- `replace("|", "\\|")` in `lib/pdf/emit.py` and `lib/html/render.py` escapes literal pipe characters inside GFM pipe-table cells (whereas `writers/markdown/tables.py` currently uses an ad hoc `re.sub(r"(?<!\\)\\|", r"\\|", raw)`).
- `_escape_wording_text` in `lib/pdf/wording_emit.py` HTML-escapes `&`, `<`, and `>` in wording prose so template angle brackets like `vec<float>` are not swallowed as HTML tags alongside `<ins>`/`<del>`.

In addition, incremental converter migration (P08-P22) needs a temporary `RawBlock(markdown, origin)` AST element that `MarkdownWriter` emits verbatim until each section/tag family is migrated to structured AST nodes.

## Approach

1. **Add `RawBlock` to `tomd.domain.elements`:**
   - Add `RAW = "raw"` to `ElementKind`.
   - Define `@dataclass class RawBlock(BlockElement)` with `markdown: str` and `origin: str`, where `text` returns `self.markdown`. Document that `RawBlock` is temporary migration scaffolding deleted in P28/P29.
   - Re-export `RawBlock` from `tomd/domain/__init__.py`.
   - Register `RawBlock` on `write_element` in `tomd/writers/markdown/blocks.py` to return `element.markdown` verbatim.

2. **Create `tomd/writers/markdown/escape.py` (pure stdlib `re`, zero `tomd.lib` imports):**
   - `escape_leading_atx(text: str) -> str`: moved from `lib/pdf/cleanup.py`.
   - `escape_italic_wrapper(text: str) -> str`: moved from `lib/pdf/emit.py:_escape_italic_text`.
   - `escape_pipe_in_cell(text: str) -> str`: `return text.replace("|", "\\|")`.
   - `escape_wording_angle_brackets(text: str) -> str`: moved from `lib/pdf/wording_emit.py:_escape_wording_text`.

3. **Wire `writers/markdown/` and legacy call sites directly (no `as X` re-exports, no `__all__` in regular modules):**
   - `writers/markdown/blocks.py`:
     - `_write_paragraph` returns `escape_leading_atx(write_spans(element.spans))`.
     - `_format_wording_paragraph` and `_write_wording_spans` use `escape_leading_atx` and `escape_wording_angle_brackets` from `tomd.writers.markdown.escape`.
     - `_write_heading` stays unescaped (headings intentionally start with `#`).
   - `writers/markdown/tables.py`:
     - `_format_pipe_cell` uses `escape_pipe_in_cell(raw).strip()`.
     - `write_table` escapes `table.caption` with `escape_italic_wrapper(table.caption)`.
   - Legacy callers updated to import directly from `tomd.writers.markdown.escape`:
     - `lib/pdf/cleanup.py` (remove `escape_leading_atx` definition)
     - `lib/pdf/emit.py` (import `escape_leading_atx`, `escape_italic_wrapper`, `escape_pipe_in_cell`)
     - `lib/pdf/pipeline.py` (import `escape_italic_wrapper`)
     - `lib/pdf/wording_emit.py` (import `escape_leading_atx`, `escape_wording_angle_brackets`)
     - `lib/html/render.py` (import `escape_pipe_in_cell` for the 3 pipe-table cell sites)
     - `tests/test_cleanup.py`, `tests/test_emit.py` (remove duplicate unit tests for functions moved to `escape.py`)
     - `tests/test_images.py` (update import of moved function)

## Files to Modify

- `packages/tomd/src/tomd/domain/elements.py`
- `packages/tomd/src/tomd/domain/__init__.py`
- `packages/tomd/src/tomd/writers/markdown/escape.py` (new)
- `packages/tomd/src/tomd/writers/markdown/blocks.py`
- `packages/tomd/src/tomd/writers/markdown/tables.py`
- `packages/tomd/src/tomd/lib/pdf/cleanup.py`
- `packages/tomd/src/tomd/lib/pdf/emit.py`
- `packages/tomd/src/tomd/lib/pdf/pipeline.py`
- `packages/tomd/src/tomd/lib/pdf/wording_emit.py`
- `packages/tomd/src/tomd/lib/html/render.py`
- `packages/tomd/tests/domain/test_domain_models.py`
- `packages/tomd/tests/writers/markdown/test_escape.py` (new)
- `packages/tomd/tests/writers/markdown/test_blocks.py`
- `packages/tomd/tests/writers/markdown/test_tables.py`
- `packages/tomd/tests/test_cleanup.py`
- `packages/tomd/tests/test_emit.py`
- `packages/tomd/tests/test_images.py`

## Do Not

- Add escaping for characters legacy code does not escape (e.g., `*`, `_`, `<` in plain prose `Paragraph`, `Heading`, or inline `EmphasisSpan`).
- Leave `from x import Y as Y` re-exports in `cleanup.py`, `emit.py`, or `wording_emit.py`, or add `__all__` to `escape.py`.

## Tests

- `tests/writers/markdown/test_escape.py`: parametrized input/output tables for `escape_leading_atx`, `escape_italic_wrapper`, `escape_pipe_in_cell`, and `escape_wording_angle_brackets`, plus writer-level tests verifying:
  - Plain prose `Paragraph` containing `*`, `_`, `<` is emitted unchanged, while a leading `# heading-like` paragraph is escaped to `\# heading-like`.
  - `Heading` text starting with `#` is not double-escaped.
  - `Table` caption is escaped via `escape_italic_wrapper`.
  - `RawBlock` round-trips arbitrary markdown bytes including internal blank lines and trailing spaces.

## Verification

```bash
uv run --package tomd pytest packages/tomd/tests -q
uv run ruff check packages tests
uv run pyright packages/tomd/src/tomd packages/tomd/tests
git status --short
```

## Handoff

```
Status: done
Files changed:
- docs/plans/tomd-ast-integration/tasks/P07-escaping-and-rawblock.md (new)
- packages/tomd/src/tomd/domain/elements.py
- packages/tomd/src/tomd/domain/__init__.py
- packages/tomd/src/tomd/writers/markdown/escape.py (new)
- packages/tomd/src/tomd/writers/markdown/blocks.py
- packages/tomd/src/tomd/writers/markdown/tables.py
- packages/tomd/src/tomd/lib/pdf/cleanup.py
- packages/tomd/src/tomd/lib/pdf/emit.py
- packages/tomd/src/tomd/lib/pdf/pipeline.py
- packages/tomd/src/tomd/lib/pdf/wording_emit.py
- packages/tomd/src/tomd/lib/html/render.py
- packages/tomd/tests/domain/test_domain_models.py
- packages/tomd/tests/writers/markdown/test_escape.py (new)
- packages/tomd/tests/writers/markdown/test_blocks.py
- packages/tomd/tests/writers/markdown/test_tables.py
- packages/tomd/tests/test_cleanup.py
- packages/tomd/tests/test_emit.py
- packages/tomd/tests/test_images.py
Checklist output (tails):
- pytest (domain/writers/cleanup/emit/images): 598 passed, 1 xfailed in 0.44s
- pytest (full tomd): 2624 passed, 7 skipped, 1 xfailed
- ruff check: All checks passed!
- pyright (domain/writers): 0 errors, 0 warnings, 0 informations
Legacy functions extracted (name, file):
- escape_leading_atx, packages/tomd/src/tomd/lib/pdf/cleanup.py -> packages/tomd/src/tomd/writers/markdown/escape.py:escape_leading_atx
- _escape_italic_text, packages/tomd/src/tomd/lib/pdf/emit.py -> packages/tomd/src/tomd/writers/markdown/escape.py:escape_italic_wrapper
- _escape_wording_text, packages/tomd/src/tomd/lib/pdf/wording_emit.py -> packages/tomd/src/tomd/writers/markdown/escape.py:escape_wording_angle_brackets
Known divergences found: none
Open questions: none
```

# Adversarial Review Follow-ups

Adversarial review of the P07 working tree. Items are ordered by severity and resolved in place.

## R1. Remove `from __future__ import annotations` from `blocks.py` and `tables.py` (medium)

`functools.singledispatch` in `writers/markdown/blocks.py` resolves dispatch types from function annotations at registration time, and no type annotations in `blocks.py` or `tables.py` require postponed evaluation on Python 3.12+.

Fix: remove `from __future__ import annotations` from `packages/tomd/src/tomd/writers/markdown/blocks.py` and `packages/tomd/src/tomd/writers/markdown/tables.py`.

## R2. Remove duplicate unit tests from `test_cleanup.py` and `test_emit.py` (low)

After moving `escape_leading_atx` and `_escape_italic_text` (`escape_italic_wrapper`) to `tomd.writers.markdown.escape` and covering all of their cases in `packages/tomd/tests/writers/markdown/test_escape.py`, `TestEscapeLeadingAtx` in `packages/tomd/tests/test_cleanup.py` and the 10 `test_escape_italic_text_*` functions in `packages/tomd/tests/test_emit.py` duplicated the canonical `test_escape.py` suite.

Fix: remove `from tomd.writers.markdown.escape import escape_leading_atx` and `TestEscapeLeadingAtx` from `packages/tomd/tests/test_cleanup.py`, and remove `from tomd.writers.markdown.escape import escape_italic_wrapper` and the 10 `test_escape_italic_text_*` functions from `packages/tomd/tests/test_emit.py`.
