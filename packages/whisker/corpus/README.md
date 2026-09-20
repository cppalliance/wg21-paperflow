# whisker micro-corpus

A small corpus whose artifacts serve distinct validation roles:

```
corpus/
  <pid>.expected.md    Lane 1 stability snapshot (blessed via `whisker golden --update`)
  <pid>.gt.md          optional Lane 2 fidelity reference (human-corrected markdown)
  <pid>.anchors.json   substring/order tripwires (conjunctive hard fail in guard)
  <pid>.facts.jsonl    Lane 3 comprehension facts (this file's subject)
  golden.json          optional: { "kind": "whisker-golden", "expected_failures": [pid, ...] }
```

`<pid>` is a paper id such as `P3100R6`; filename matching is
case-insensitive. Lane membership is independent:

- Lane 1 is the union of existing `<pid>.expected.md` snapshots and optional
  `<pid>.gt.md` bootstrap markers. An expected-only paper is compared normally;
  a GT-only paper is `new` until `whisker golden --update` creates its snapshot.
- Lane 2 includes only `<pid>.gt.md` fidelity references.
- Lane 3 includes `<pid>.facts.jsonl` assertions.

The current canonical corpus has five expected snapshots, five matching facts
files with 37 verified facts, and no GT files. GT remains supported for fidelity
corpora and backward-compatible Lane 1 bootstrapping.

## The three lanes

- **Lane 1 Stability** (`whisker golden`): did the normalized markdown change vs
  the committed `<pid>.expected.md`. Catches silent regressions AND silent
  improvements. Bless a change by reviewing the diff, then `--update`.
- **Lane 2 Fidelity** (`whisker bench` / `whisker guard`): how close is the
  output to `<pid>.gt.md` on nid / teds / mhs. Measures resemblance, NOT
  comprehension.
- **Lane 3 Comprehension** (`whisker facts`): can an LLM still recover the
  paper's facts from the markdown. Deterministic, source-verified assertions, no
  LLM in the scoring loop.

## Provenance discipline

Whisker's `<pid>.expected.md` files are converter-output stability snapshots,
not correctness oracles; they freeze whatever was blessed, bugs included.
`<pid>.gt.md` files are human-corrected fidelity references. The facts lane uses
source-verified assertions: each fact is authored from the SOURCE pdf/html and
is enforced only once its needle has been located there and
`"checked": "verified"` is set.

tomd's canonical `tests/fixtures/golden/ideals/*.md` files are a separate,
human-corrected structural truth set. Whisker auto-reads them, without copying,
for its deterministic Lane 2 ideal panel and for a separate optional LLM ideal
verifier. They do not define Lane 1 corpus membership.

Honest status (2026-07-09): all `verified` facts to date were authored and
source-verified by the agent, at the user's direction; no fact has been
independently blessed by a human yet. Close that gap by spot-checking facts
against the source when blessing the next wave (`CLAUDE.md`, Known gaps).

## Fact schema (`<pid>.facts.jsonl`)

One JSON object per line. See `EXAMPLE.facts.jsonl` for a worked instance.

Common fields:

- `id` (string, optional): unique within the file; defaults to `"<type>[<index>]"`.
- `type` (string, required): one of the eight supported types: `present`,
  `absent`, `order`, `table`, `math`, `code`, `xref`, `image_ref`.
- `checked` (string, optional): only the literal `"verified"` promotes the fact
  to enforced; anything else (absent, `"draft"`) leaves it advisory.
- `max_diffs` (int >= 0, optional, default 0): edit budget for fuzzy matching.

Type-specific fields:

- `present` / `absent`: `text` (required). Asserts the text is / is not in the
  markdown, within `max_diffs` edits on the normalized surface.
- `math`: `text` (required). Like `present` but on a math surface that folds
  LaTeX (`$E=mc^2$`) and KEEPS `^`, `_`, `=` so structure is compared.
- `order`: `sequence` (list of >= 2 strings). Each item must appear, strictly
  after the previous one.
- `table`: `cell` (string) + `neighbors` (object). Locates the cell, then checks
  each neighbor direction (`up` / `down` / `left` / `right` / `heading`) equals
  the expected text. Directly tests "row 3, column 2 still reads correctly".
- `code`: `text` (required). Checks raw Markdown for a code snippet while
  preserving code-sensitive punctuation and case.
- `xref`: `text` (required). Checks raw Markdown for a revision-sensitive paper
  reference such as `[P1234R5]`.
- `image_ref`: optional `text`. Checks only that a Markdown image reference
  `![...](...)` is present and, when `text` is supplied, that its path/alt
  substring is present in the raw Markdown. It does not extract package images,
  inspect raster pixels, or measure image fidelity.

## Running

```powershell
whisker facts  --corpus packages/whisker/corpus           # Lane 3 only
whisker golden --corpus packages/whisker/corpus           # Lane 1 only
whisker guard  --corpus packages/whisker/corpus --baseline <file>   # Lane 2 + anchors + facts
```

`whisker facts` gates only `verified` facts by default; `--strict` also gates
drafts (useful while authoring).
