# P04 Wording and blockquote: model and writer

| Wave | Deps | Parallel with | Size | Risk |
|------|------|---------------|------|------|
| 1 | P02 | P03, P05, P06, P07 | M | high |

## Goal

Represent wording blocks with their `ins`/`del` roles intact (including code diffs) and
blockquotes with block children, and reproduce legacy bytes. Port the redundant-role
cleanup as a pure function over the AST.

## Read first

- `lib/pdf/wording_emit.py` (whole file: three shapes, `_group_wording_spans`,
  `_escape_wording_text`, code-promotion constants)
- `lib/wording_cleanup.py` (`strip_redundant_tags`), `lib/wording_policy.py`,
  `lib/wording_markup.py` (`wording_tag_open`)
- `lib/html/render.py`: `_render_wording_div` (940), `_render_blockquote` (1500), the
  `example-block/note-block/bug-block` branch in `_render_element` (about line 590).
  Both blockquote sites quote blank lines as `> ` (trailing space).
- `domain/elements.py` (`WordingBlock` has a hand-written `__init__`; replace it),
  `writers/markdown/blocks.py`
- Tests: `tests/test_wording*.py`, wording cases in `tests/test_emit.py`,
  `tests/test_html_render.py`

## Change

Domain:
- `WordingBlock(role: Literal["wording", "wording-add", "wording-remove"],
  children: list[BlockElement])` as a plain dataclass.
- A code-diff representation: fenced code whose lines carry `ins`/`del` spans. Choose
  the smallest model that lets the writer match `_render_wording_section` for
  wholesale code, code diff, and prose shapes (for example `CodeBlock` gains an optional
  `lines: list[list[Span]] | None`, or a separate `CodeDiffBlock`). Document the choice
  in the module docstring.
- `Blockquote(children: list[BlockElement], role: str | None)`.

Writer:
- Render all three wording shapes byte-identically to `wording_emit` (including angle
  bracket escaping inside diffs and the `<ins>/<del>` tag syntax from
  `wording_markup`). Wording has no div fence in the output; the role only matters to
  the cleanup below.
- Blockquote: render children joined by a blank line, quote every line. Verified in the
  legacy code: both sites (`_render_blockquote`, the note/example branches) do
  `"> " + inner.replace("\n", "\n> ")`, so a blank line becomes `> ` WITH a trailing
  space. The merged writer writes a bare `>`; change the writer to match legacy and add
  the trailing-space quirk to Known divergences (it violates the no-trailing-whitespace
  rule; a behavior PR can fix it later).

Pass (new `tomd/passes/wording.py`, BSL header): `strip_redundant_roles(block:
WordingBlock) -> WordingBlock`, a port of `strip_redundant_tags` using
`UNIFORM_ROLE_THRESHOLD` and `implicit_role_for` from `wording_policy`: when the block
role implies `ins`/`del` and at least the threshold of role-bearing characters carry it,
unwrap the redundant inline spans.

## Do not

- Touch legacy code or converters. Do not move `wording_policy` constants.

## Tests

Twin tests: build `Section` objects of each wording kind (prose; code with
`monospace` spans; code diff with green/red spans) and the equivalent AST, compare to
`wording_emit._render_wording_section`. Cleanup: compare `strip_redundant_roles` to
`strip_redundant_tags` rendered output over a table of inputs at, below and above the
threshold. Blockquote: compare to the HTML renderer on parsed snippets (single paragraph,
multiple blocks, blank lines, nested list inside).

## Acceptance

Checklist green; each twin test asserts byte equality.

## Handoff (fill in at the end)

```
Status: done
Files changed:
  packages/tomd/src/tomd/domain/__init__.py
  packages/tomd/src/tomd/domain/elements.py
  packages/tomd/src/tomd/writers/markdown/blocks.py
  packages/tomd/tests/domain/test_domain_models.py
  packages/tomd/tests/fixtures/markdown/sample_documents/wording_diff.md
  packages/tomd/tests/fixtures/sample_documents.py
  packages/tomd/tests/writers/markdown/test_blocks.py
  packages/tomd/tests/writers/markdown/test_wording_and_blockquote.py
Checklist output (tails):
  tomd pytest: 2568 passed, 7 skipped, 1 xfailed in 122.04s
  ruff:        All checks passed!
  pyright:     0 errors, 0 warnings, 0 informations
  other pkgs:  paperstore (122), mailing (37), pipeline (260), agora (301),
               assay (450), whisker (367), cli (153), root tests (8) all passed
Model chosen for code diffs and why:
  CodeBlock gains an optional `lines: list[list[Span]] | None = None` field (with
  `code: str = ""` default). This keeps a single fenced-code block element across
  the AST and writer while preserving per-line `UnderlineSpan`/`StrikethroughSpan`
  role spans for intra-block code diffs.
Known divergences found (confirm the blockquote trailing-space quirk is recorded):
  Confirmed recorded in STATUS.md: blockquote blank lines render as `> ` with a
  trailing space in HTML-sourced output (`lib/html/render.py` `_render_blockquote`
  and note/example branches).
Open questions:
  None.
```
