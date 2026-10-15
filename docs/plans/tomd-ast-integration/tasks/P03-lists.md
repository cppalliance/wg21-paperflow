# P03 Lists: nested model and writer

| Wave | Deps | Parallel with | Size | Risk |
|------|------|---------------|------|------|
| 1 | P02 | P04, P05, P06, P07 | M | medium |

## Goal

Make `ListBlock` able to represent every list the PDF and HTML converters emit, and
make the writer reproduce their bytes. Pure model and writer work; no converter changes.

## Read first (legacy behavior to reproduce)

- PDF: `lib/pdf/emit.py` lines 118-170 (`LIST_BULLET`, em-dash bullets), 285-392
  (`_normalize_bullets`, `_format_list_item`, `_render_list_spans`), 1106-1160
  (`_assign_emdash_nesting`); `lib/pdf/structure.py:1918` `_assign_list_nesting`.
- HTML: `lib/html/render.py` 1000-1121 (`_indent`, `_render_list_item`, `_render_list`).
- Existing tests that pin the shapes: `tests/test_position_lists.py`, the list tests in
  `tests/test_html_render.py` and `tests/test_emit.py`, and the markdown-it nesting tests.
- `writers/markdown/blocks.py` `_format_list_block`, `domain/elements.py`.

## Change

Domain (`domain/elements.py`):
- `ListItem`: `spans` (the label), `children: list[BlockElement]` (continuation blocks,
  including nested `ListBlock`), `marker: str | None` (a preserved ordinal such as
  `b)` or `(a)`; `None` means generate).
- `ListBlock`: add `start: int = 1`; keep `ordered`, `items`.

Writer (`blocks.py`):
- Unordered items always use `-`. Ordered items use `start + i` with `.` unless the
  item has a `marker`, which is written verbatim.
- Continuation blocks are indented to the marker content width (`len(prefix) + 1`);
  a nested `ListBlock` child is tight (no blank line before it), every other child block
  is preceded by a blank line, except when the item has no label: then the first child
  follows the bare marker with no blank line (CommonMark rule noted in
  `_render_list_item`).
- Two-space indentation per nesting level for nested lists, matching the PDF output.

## Do not

- Touch converters or legacy renderers. Do not add escaping (P07 owns it).
- Invent behavior: where legacy PDF and HTML disagree, match each side's bytes via the
  model (for example `marker`), do not unify them.

## Tests

Twin tests in `tests/writers/markdown/test_lists.py`: for each shape build the AST and
the equivalent legacy input and compare. Shapes: flat bullets; ordered from 1; ordered
`start=5`; nested two and three levels; item with continuation paragraph; item with
fenced code child; item with nested list child; label-less item with children; preserved
`b)` / `(a)` markers; multi-line label. Legacy oracle: call
`emit._render_list_spans` on a hand-built `Section` (PDF shapes) and
`render._render_list` on a parsed `<ul>/<ol>` snippet (HTML shapes). Add one fixture to
`tests/fixtures/sample_documents.py` plus its expected `.md`, and keep the
markdown-it nesting assertion style from the existing list tests.

## Acceptance

Checklist green; every shape asserts byte equality with the legacy renderer.

## Handoff (fill in at the end)

```
Status: done | blocked
Files changed:
Checklist output (tails):
Shapes covered / any shape where AST cannot match legacy:
Known divergences found:
Open questions:
```
