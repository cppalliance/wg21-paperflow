# whisker micro-corpus

A small, human-verified corpus that all three whisker lanes share, so the
annotation cost is paid once per paper:

```
corpus/
  <pid>.gt.md          Lane 2 fidelity reference (hand-cleaned ground-truth markdown)
  <pid>.expected.md    Lane 1 stability snapshot (blessed via `whisker golden --update`)
  <pid>.anchors.json   substring/order tripwires (conjunctive hard fail in guard)
  <pid>.facts.jsonl    Lane 3 comprehension facts (this file's subject)
  golden.json          optional: { "kind": "whisker-golden", "expected_failures": [pid, ...] }
```

`<pid>` is the upper-cased paper id (e.g. `P3100R6`). A paper is a member of the
corpus when it has a `<pid>.gt.md`. Lanes are independent: a paper may have facts
without a golden snapshot, or vice versa.

## The three lanes

- **Lane 1 Stability** (`whisker golden`): did the normalized markdown change vs
  the committed `<pid>.expected.md`. Catches silent regressions AND silent
  improvements. Bless a change by reviewing the diff, then `--update`.
- **Lane 2 Fidelity** (`whisker bench` / `whisker guard`): how close is the
  output to `<pid>.gt.md` on nid / teds / mhs. Measures resemblance, NOT
  comprehension.
- **Lane 3 Comprehension** (`whisker facts`): can an LLM still recover the
  paper's facts from the markdown. Deterministic, human-verified assertions, no
  LLM in the scoring loop.

## Provenance discipline

No converter output is a correctness oracle. `<pid>.gt.md` and `<pid>.expected.md`
are blessed by a human eyeballing the source; they freeze whatever was blessed,
bugs included. The facts lane sidesteps this: each fact is authored by a human
reading the SOURCE pdf/html (not any `tomd` output) and is enforced ONLY once
that human sets `"checked": "verified"`. Authoring a fact and blessing it are
separate, auditable steps.

## Fact schema (`<pid>.facts.jsonl`)

One JSON object per line. See `EXAMPLE.facts.jsonl` for a worked instance.

Common fields:

- `id` (string, optional): unique within the file; defaults to `"<type>[<index>]"`.
- `type` (string, required): one of `present`, `absent`, `order`, `table`, `math`.
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

## Running

```powershell
whisker facts  --corpus packages/whisker/corpus           # Lane 3 only
whisker golden --corpus packages/whisker/corpus           # Lane 1 only
whisker guard  --corpus packages/whisker/corpus --baseline <file>   # Lane 2 + anchors + facts
```

`whisker facts` gates only `verified` facts by default; `--strict` also gates
drafts (useful while authoring).
