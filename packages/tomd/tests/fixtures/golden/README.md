# Golden files

Expected outputs for [`test_html_golden.py`](../../test_html_golden.py) and
[`test_pdf_golden.py`](../../test_pdf_golden.py). For the end-to-end workflow
(score, bless, rebless, the gate), see [`docs/tomd-qa.md`](../../../../../docs/tomd-qa.md).

Files are organized by role:

```
golden/
  sources/     <stem>.pdf | <stem>.html        inputs to both nets
  snapshots/   <stem>.md (+ <stem>.prompts.json, + <stem>-figN.png)
  ideals/      <stem>.md
  stems/       <stem>.txt                      PDF snapshot registry
  baselines.json
```

- **Stem** (`stems/<stem>.txt`): registers one PDF paper for `test_pdf_golden`. The filename is the key: the test globs `stems/*.txt` and runs one byte-exact snapshot test per stem, so a golden without a stem file is not tested. The body is a free-form note about the paper and is never read. A new paper is a new file. Family-pin tests live in `packages/tomd/tests/pdf_pins/`, one module per paper.
- **Source** (`sources/<stem>.{pdf,html}`): the paper, input to both nets.
- **Snapshot** (`snapshots/<stem>.md`): a byte-exact lock on tomd's *current*
  output. Guarded by `test_pdf_golden` / `test_html_golden`. Answers "did the
  output change at all?" Any figure PNGs the markdown references live beside it.
- **Ideal** (`ideals/<stem>.md`): the structural *gold standard* (only for
  blessed papers). Guarded by `test_golden_gate`. Answers "did the output get
  worse than the ideal?"

## PDF golden files

Selected for structural diversity:

| Paper | Features |
|-------|----------|
| p0533r9 | tables, code blocks, bold, italic |
| p0957r8 | tables, 66 code blocks, 22 lists, uncertain regions |
| p1068r11 | heavy wording (94 ins), lists, code |
| p3556r0 | both ins and del wording, headings, code, links |
| p1122r3 | list-heavy (29 lists), headings, code, links |
| p2040r0 | balanced (code, lists, headings), full 5-field front matter |
| p3714r0 | minimal paper (2 headings, 1 code block) |
| p1112r4 | uncertain regions, lists, italic |
| p4174r0 | TOC-strip regression (#122): short paper, no real TOC; full body (title, abstract, sections) must survive |
| p4004r1 | TOC-strip regression (#122): small partial-loss paper; mid-body sections must survive |
| p4100r1 | leaked heading-kind TOC (#122 pt2): empty duplicate-heading TOC block removed; one heading per section |
| p3968r0 | promotion-dedup guard (pt3): confident page doubled by a neighbour's promotion; each section must appear exactly once |
| p4096r0 | shattered tables (#380): Google Docs export, every wrapped cell line its own block; four tables pinned by family in `pdf_pins/test_p4096r0.py` |

## Refreshing HTML baselines

From the `tomd/` directory, after intentionally changing HTML converter output:

```bash
python -c "
import json
from pathlib import Path
from tomd.lib.html import convert_html
src = Path('tests/fixtures/golden/sources').resolve()
snap = Path('tests/fixtures/golden/snapshots').resolve()
for name in ['p3411r5.html', 'p2728r11.html', 'p3953r0.html', 'p4005r0.html',
             'p4020r0.html', 'p3911r2.html', 'n5034.html']:
    stem = Path(name).stem
    md, prompts = convert_html(src / name)
    (snap / f'{stem}.md').write_text(md, encoding='utf-8', newline='\n')
    ppath = snap / f'{stem}.prompts.json'
    if prompts:
        ppath.write_text(json.dumps(prompts, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    elif ppath.exists():
        ppath.unlink()
"
```

## Refreshing PDF baselines

From the `tomd/` directory, after intentionally changing PDF converter output:

```bash
python -c "
import json
from pathlib import Path
from tomd.lib.pdf import run_pipeline
src = Path('tests/fixtures/golden/sources')
snap = Path('tests/fixtures/golden/snapshots')
for stem in ['p0533r9', 'p0957r8', 'p1068r11', 'p3556r0',
             'p1122r3', 'p2040r0', 'p3714r0', 'p1112r4']:
    r = run_pipeline(src / f'{stem}.pdf')
    md, prompts = r.md, r.prompts
    (snap / f'{stem}.md').write_text(md, encoding='utf-8', newline='\n')
    ppath = snap / f'{stem}.prompts.json'
    if prompts:
        ppath.write_text(json.dumps(prompts, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    elif ppath.exists():
        ppath.unlink()
"
```

Prompts goldens are JSON arrays where each element is a self-contained LLM
reconcile prompt. Review diffs, then commit.

## Structural baselines (golden QA gate)

The structural gate (`tests/test_golden_gate.py`) compares tomd's output
against BLESSED IDEAL goldens, not snapshots of tomd's own output. A blessed
ideal lives at `ideals/<stem>.md` and encodes the correct structure (verbatim
content, ideal heading levels, list nesting, fences, tables, chrome stripped).
It is distinct from the `snapshots/<stem>.md` snapshots, which are tomd's current
output and are guarded byte-exactly by `test_pdf_golden` / `test_html_golden`.

A freshly-blessed ideal encodes structure current tomd does not reach yet, so
its score starts below 1.0. `baselines.json` records each blessed paper's
per-axis score (front-matter, heading, list, code, table, text); the gate
fails if any axis drops below its committed baseline. The gap to 1.0 is the
visible bug backlog. Sources live in `sources/`.

Ratchet baselines after a reviewed tomd improvement (outside a venv, prefix
with `uv run --package tomd`):

    tomd rebless --all          # raise every blessed paper's baseline
    tomd rebless <paper_id>     # one paper

`rebless` only ever raises a baseline: it refuses to lower any axis (that would
enshrine the regression the gate exists to catch) unless you pass `--force`.
Scores are stored exactly, never rounded: a rounded-up baseline would sit above
the score tomd can achieve and fail its own blessed paper.

## Seed, correct, then bless

To add a new blessed ideal for a paper:

1. Seed it from tomd's own conversion (no LLM, instant):

       tomd generate <paper_id>

   This writes tomd's current output to `ideals/<stem>.md` as a starting draft.
2. Correct its STRUCTURE against the source: headings at the right level, lists
   nested correctly, code fenced and labeled, tables intact, front matter in
   canonical order. tomd already gets the content right, so you rarely touch the
   words; the structural corrections are what make the draft a gold standard. An
   uncorrected seed is byte-identical to tomd's output and is rejected at bless
   time (and by `test_golden_gate`), so the correction step cannot be skipped.
   Optionally run `tomd review <paper_id>` for an LLM punch-list of suspected
   structural divergences (a de-anchoring second pair of eyes).
3. Validate and record the baseline:

       tomd bless <paper_id>

   It runs the fidelity gate (a coarse "not gutted" guard, not a paraphrase
   detector), refuses a raw uncorrected seed, prints coverage/drift, and records
   the per-axis baseline row in `baselines.json`.
4. Review the printed baseline row, then commit the `ideals/<stem>.md` and the
   `baselines.json` change together.

If the fidelity gate fails, the candidate dropped or gutted too much of the
source. Never lower the gate thresholds to pass a bad candidate.
