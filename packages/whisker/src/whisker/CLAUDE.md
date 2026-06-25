# whisker - Agent Rules

## What this is

Deterministic QA for tomd conversions, with no LLM. whisker answers two
questions:

- **Per paper, without hand-labeled ground truth:** is this conversion safe to
  ship, does it need a human, or is it broken? (`whisker [PID ...]`) The hard
  gate is the reference-free path (structural gates + a content-coverage floor).
  By default whisker ALSO generates an independent reference markdown from the
  same source with a second converter (the *oracle*, markitdown) and scores
  tomd's text against it as an ADVISORY signal: low cross-converter agreement
  raises a review flag for a human to look, but never fails a paper on its own
  (agreement != correctness). `--no-reference` skips the oracle entirely.
- **Against labeled ground truth:** how good is the conversion on the structural
  fidelity axes, and did it regress? (`whisker bench`)

## Three lanes (do not conflate them)

Regression detection is split into three independent lanes that answer different
questions. They are deliberately NOT interchangeable; a paper can pass two and
fail the third.

- **Lane 1 Stability** (`whisker golden`, `golden.py`): did the normalized
  markdown change vs a committed `<pid>.expected.md` snapshot. Exact `difflib`
  compare; catches silent regressions AND silent improvements. Bless a change by
  reviewing the diff, then `--update`. A blessed snapshot is NOT a correctness
  oracle: it freezes whatever a human approved, bugs included.
- **Lane 2 Fidelity** (`whisker bench` / `whisker guard`): how CLOSE is the
  output to a `<pid>.gt.md` reference, on `nid`/`teds`/`mhs`/`content_recall`.
  This is resemblance, not comprehension.
- **Lane 3 Comprehension** (`whisker facts`, `facts.py`): can an LLM still
  RECOVER the paper's facts from the markdown. Deterministic human-verified
  assertions (`present`/`absent`/`order`/`table`/`math`), no LLM in the loop.

**Fidelity is not comprehension.** A reflow can score high on every Lane 2 axis
and still scramble a table cell or drop a formula's exponent so a downstream LLM
reads "row 3, column 2" wrong, with every fidelity metric green. Only Lane 3
catches that. Lane 3 also sidesteps the ground-truth-provenance problem: across
the 28 surveyed converters, none has an automatic "this file is 100% correct"
oracle, and only `olmocr` tests comprehension at all. A handful of human-verified
facts per paper are cheap to author and independent of any single `tomd` output,
so they are the honest WG21 ground truth without a perfect golden file.

`whisker guard` additionally folds substring anchors (`anchors.py`,
`<pid>.anchors.json`) and Lane 3 facts (`<pid>.facts.jsonl`) in CONJUNCTIVELY: a
missed anchor or a failed VERIFIED fact is a hard fail even when the numeric
slack holds. The shared micro-corpus layout lives in `packages/whisker/corpus/`.

whisker is standalone. It depends on `paperstore`, `tomd`, `markitdown` (the
reference oracle), `rapidfuzz` (MIT edit distance), `apted` + `lxml` (the verbatim
PubTabNet/OmniDocBench TEDS), `mistune` (heading-tree AST, shared with tomd QA),
`grits-metric` (advisory GriTS-Con cell-F1 table axis), `pylatexenc` (inline-LaTeX
folding in the text normalizer), and `numpy` + `scipy` (the block-matching cost
matrix and Hungarian assignment). It edits no other package, reuses tomd's QA
functions by import (read-only), and never modifies the paperstore/cli source.

## Usage (quickstart)

whisker needs both the source and the converted markdown in the paperstore, so
run `paperflow convert <pid>` first. The CLI lives in the workspace venv.

Activate the venv once, point at the data dir, then call `whisker` directly
(PowerShell):

```powershell
.\.venv\Scripts\Activate.ps1
$env:WG21_DATA_DIR = "C:\path\to\wg21-data"   # dir that holds paperstore.db
whisker --all
```

Without activating, prefix every call with `uv run --package whisker` (note the
word `whisker` appears twice: package name, then script name):

```powershell
uv run --package whisker whisker --all
```

Common invocations:

```powershell
whisker P3181R1 P3100R6     # score specific papers (case-insensitive ids)
whisker --all               # score every converted paper, with a progress bar
whisker --all --stats       # same, plus a flag rollup (which reason, how often)
whisker --all -q            # one-line footer only
whisker --all -v            # show every paper incl. pass, no per-section cap
whisker --all --json        # machine-readable JSON array on stdout
whisker --all --no-write    # stdout only, write no files
whisker --all --no-reference # skip the oracle, use reference-free structural path
whisker --gate pass P3100R6 # CI: a review verdict also exits non-zero
whisker bench --corpus ./gt --baseline whisker/report.json   # benchmark mode
```

Flags: `--all` (score everything; **two dashes**, not `-all`), `-v/--verbose`,
`-q/--quiet`, `--stats`, `--json`, `--no-write`, `--report-dir DIR`,
`--reference {markitdown}` (oracle engine, default markitdown),
`--no-reference` (reference-free fallback),
`--gate {pass,review,fail}`, `--workspace DIR` (overrides `$WG21_DATA_DIR`).
The oracle runs a second full conversion per paper, so `--all` is slower than
the reference-free path (seconds per paper); `--no-reference` is the fast path.
A live progress bar prints to stderr on a real terminal; it is suppressed
automatically when output is piped, so it never corrupts `--json` on stdout.
`--all` skips un-converted papers silently and a single failing paper is logged
and skipped, never aborting the batch.

## Output (human terminal)

Modeled on pytest/ruff/eslint: stdout carries the result, stderr carries
progress and log lines. The default is a triaged summary, not a per-paper dump.

- **Default:** a `fail` section then a `review` section, each worst-agreement
  first and capped at `SUMMARY_SECTION_CAP` lines (overflow collapses to
  `... and N more (see report.md)`). Passes are hidden; they live in the footer
  count. With the oracle on, every paper line leads with the agreement axes
  `PID  ovr= nid= teds= mhs=  <reasons>` (nid is an advisory review signal;
  teds/mhs are informational); on `--no-reference` it is
  `PID  uni= cov= drift= qa=  <reasons>` (`uni` is the content gate, `cov` the
  reading-order proxy shown for context).
  On a tty the verdict tiers are colored (red fail, yellow review, green pass).
- **`-v/--verbose`:** lift the cap and add the `pass` section (full listing).
- **`-q/--quiet`:** print only the footer line.
- **`--stats`:** append a ruff-style flag rollup, counts per hard/soft flag
  category (values stripped so "coverage 0.53 < 0.85" and "0.78 < 0.85"
  aggregate into one `coverage <` row).
- **`--json`:** the JSON array on stdout, unchanged; no human text leaks in.
- **Footer (always last):** `=== F failed, R review, P passed (N scored[, S
  skipped]) in Ts ===`, colored by the worst verdict present.

`render_summary` in `report.py` is a pure function: color and elapsed are
parameters, so the rendering is deterministic and unit-tested on plain text.

## Module layout

- `constants.py` - every threshold, named (incl. block-match `BLOCK_*` edges).
- `metrics.py` - `teds` (tables): a VERBATIM port of PubTabNet/OmniDocBench TEDS
  (lxml DOM -> `apted`, char-token cells, xpath-descendant denominator), so table
  scores are comparable to the published leaderboards. `mhs` (heading hierarchy)
  scores `apted` tree edit distance over a heading tree parsed from mistune's
  CommonMark AST (the same engine tomd QA uses): ATX + setext headings, inline
  markup flattened to prose, front matter stripped, top-level headings only
  (nested `> ##` / `- ##` skipped, matching tomd QA). `text_nid` (full-text
  similarity). `normalized_text` = `clean_string(textblock2unicode(text))`, the
  OmniDocBench text-axis normalizer adopted verbatim: `textblock2unicode` folds
  inline LaTeX (`$...$`, `\(...\)`) to unicode via `pylatexenc` behind its
  guard ladder, `replace_textcircle` folds circled glyphs, and `clean_string`
  strips escapes/whitespace then keeps only alnum + CJK. Applied symmetrically so
  text comparison measures CONTENT agreement, not tomd-style vs oracle-style
  formatting (front-matter, headings, pipe tables, emphasis, reflow all vanish).
  Note `clean_string` does NOT strip YAML front-matter keys; on real papers those
  few tokens are negligible. The char-level edit distance uses the MIT-licensed
  `rapidfuzz` package (drop-in for the old GPL `levenshtein`, score-identical):
  a full-document compare is milliseconds, where a pure-Python DP would hang for
  minutes. Deterministic.
- `match.py` - block-level text matching (OmniDocBench `match_quick` port): split
  prose into blocks, normalize, build a NED cost matrix, Hungarian-assign, accept
  at <= 0.70 NED, fuzzy-rescue embedded GT blocks at < 0.40. `block_text_nid`
  (reorder-robust `1 - edit_whole`) and `reading_order_ned` (a SEPARATE advisory
  axis) come from one matching pass. The O(gt*pred) matrix is capped
  (`BLOCK_MATRIX_CELL_BUDGET`): giant papers fall back to the whole-document
  `text_nid`. Used by `bench`; the oracle deliberately does NOT use it (see below).
- `reference.py` - `reference_markdown(pid, backend, *, engine) -> str`. Runs
  the oracle (markitdown) on the staged source, no network/LLM. Library returns
  data. The engine is pluggable (`REFERENCE_ENGINES`).
- `gates.py` - reference-free structural gates. Every gate is hard.
- `score.py` - `score_paper(pid, backend, *, reference_engine="markitdown") ->
  WhiskerResult` + the trichotomy verdict. `score_markdown(...)` is the
  backend-free core for tests (pass `reference_md=` to exercise the oracle path).
  The oracle `ref_nid` is the WHOLE-DOCUMENT `text_nid` on `normalized_text`, NOT
  block-matched: markitdown blocks the page at an erratic granularity (often a
  few giant blocks), and block matching without an adjacency-merge under-scores
  those by up to 0.57 vs the full-document nid (measured), which would
  manufacture false advisory-review flags. Block matching is reserved for `bench`
  against well-formed labeled GT.
- `bench.py` - `run_bench(pairs) -> [BenchRow]` + `aggregate`, the leaderboard.
  `nid` is `block_text_nid` (reorder-robust); `content_recall` is multiset
  bag-of-words recall of GT content in the candidate (catches dropped sections
  edit distance hides), a first-class gate (floor + per-paper guard) but NOT
  folded into `overall` (strata stay separate); `reading_order` and `grits_con`
  (GriTS-Con cell-content F1, complementary to `teds`) are reported as separate
  ADVISORY axes, never folded into `overall` and never gated (`grits_con` until
  it has its own calibration). `teds`/`mhs`/`grits_con` are `None` when the
  reference lacks that modality (null-eligibility).
- `golden.py` - Lane 1 stability. `diff_goldens(items)` exact-compares each
  candidate's `normalize_for_exact_lane(...)` against a committed
  `<pid>.expected.md` snapshot (stdlib `difflib`). Decoupled from metrics: bless
  is a human reviewing the diff, never a metric threshold. Optional
  `expected_failures` (in `golden.json`) flag known-imperfect snapshots that must
  fail on silent change AND silent improvement.
- `anchors.py` - per-paper substring/order tripwires. `check_anchors(md, spec)`
  over `<pid>.anchors.json`: `must_contain` / `must_not_contain` / `ordered`
  chains / regex `patterns`, on the `raw` or `normalized` surface. Conjunctive
  hard fail in `whisker guard`.
- `facts.py` - Lane 3 comprehension. `check_facts(md, facts)` evaluates
  deterministic, human-verified assertions from `<pid>.facts.jsonl`: `present` /
  `absent` (fuzzy within a `max_diffs` budget: rapidfuzz locates the window, then
  an exact free-start/free-end substring DP measures the true edit count, since
  rapidfuzz's Indel window can trim a boundary char), `order` (strictly
  increasing positions), `table` (locate a cell, check `up`/`down`/`left`/`right`/
  `heading` neighbors, the direct "row 3, column 2" test), `math` (presence on a
  LaTeX-folded surface that KEEPS `^`/`_`/`=`). Only `checked: verified` facts
  gate; drafts are reported but advisory. Macro-averaged per type. No LLM.
- `report.py` - `build_report` / `render_report_md` / `render_summary`.
- `__main__.py` - the `whisker` CLI. Owns all persistence and stdout.

## Verdict model

Three outcomes: `pass`, `review`, `fail`. The hard gate is the same whether or
not the oracle ran; the oracle only adds an advisory review overlay.

**Hard fails (the only ways to fail):**

- any structural gate failure (`gates.py`), or
- `unigram_coverage < UNIGRAM_COVERAGE_FAIL_EDGE` (0.85): content genuinely
  missing.

The content gate runs on `unigram_coverage` (order-invariant token-set recall),
NOT on the shingle `coverage`. Every document-parsing benchmark splits two axes:
content coverage (is the text present?) and reading order (is it in the right
sequence?), and reading order never gates content quality. Docling scores
`set(word_tokenize)` precision/recall; Nougat reports set-F1; OmniDocBench
Hungarian-matches blocks before NED and keeps reading-order out of the overall
score. The shingle `coverage` (5-gram, order-sensitive) is a reading-order
proxy: a converter that correctly reflows multi-column PDF text scores low on it
while every word is present. It is REPORTED (sidecar field, `cov=` in the
summary, `coverage` column in report.md) but is NEVER a verdict flag. tomd's own
`ContentCheckResult` docstring states the same: a large `unigram_coverage -
coverage` gap means faithful reflow, a low `unigram_coverage` means missing
content.

**Soft signals (review):** `unigram_coverage` in the 0.85-0.95 band (some words
missing), drift over edge, any misaligned region, qa under the soft edge, any
uncertain marker. Misaligned regions are soft only: tomd intentionally strips
furniture (headers, footers, page numbers, TOCs), so some regions are expected
on clean papers; `unigram_coverage` below the floor is the hard signal for
missing content.

**Advisory overlay (reference oracle on, the default).** Cross-converter TEXT
agreement (`ref_nid`, the whole-document `text_nid` on `normalized_text`) is
layered on as ONE extra soft signal:

- `ref_nid < REF_NID_ADVISORY_EDGE` (0.85) -> a `review` flag
  (`reference text agreement <x> low (advisory)`).
- It NEVER hard-fails. `ref_teds` and `ref_mhs` are computed and reported
  per-axis but never flag at all.

This is deliberate. No major benchmark uses a second automated converter as a
pass/fail reference (all use human gold); cross-converter agreement is a
confidence signal, not ground truth (CE-OCR, Infinity-Parser: "agreement !=
correctness"). The oracle (pdfminer for PDF) also emits no reliable heading
hierarchy and structures tables differently, so teds/mhs carry no signal against
it, which is why they are report-only (OpenDataloader nulls such axes;
OmniDocBench/kapa.ai never collapse per-axis scores into one number). The
advisory edge 0.85 is adopted from a literal repo constant (edgeparse's NID CI
floor). Low nid means LOOK, not "tomd is wrong"; so it raises review, never fail.

`--no-reference` skips the oracle and leaves the `ref_*` fields null; the
hard/soft gate above is identical, just without the advisory overlay.

## What vs where

Flags carry the rule-level WHY (which check tripped and the threshold it
crossed). Gate detail carries structural location (which structural invariant
broke). The region detail (`missing_regions`, `extra_regions` on `WhiskerResult`)
carries the content-level WHERE: the PDF page and a 60-char text snippet
locating the missing or extra content, sorted by token position and capped at
`REGION_DETAIL_CAP` per side.

Deliberate omissions: no HTML/bbox visualization (whisker has no layout stage
to map token positions back to page coordinates), no per-table-cell diff (no
benchmark repo does it; tables are scored holistically via TEDS).

## Invariants

- **Standalone.** Never edit another package to make whisker work. Reuse tomd by
  import. Derive the sidecar path from `backend.get_paper_md_path(pid)`; never
  build paths from `workspace_dir`.
- **Determinism.** Every metric is a pure function of its inputs. Sort unordered
  collections before output (`hard_flags`, `soft_flags`, bench rows by pid). No
  LLM, no network, no randomness.
- **Library returns data; CLI persists.** `score_paper` / `run_bench` return
  dataclasses. Only `__main__.py` writes sidecars and the leaderboard.
- **Thresholds are named constants.** No bare numeric literal in the scoring
  path. New tunables go in `constants.py` with a comment on what they gate.
- **BSL-1.0 header** on every new `.py` file. `__init__.py` is re-exports only.

## Artifacts

All whisker output is grouped under a single `whisker/` directory in the data
dir (sibling of `paperstore/`), not scattered among the converted papers.
Override the location with `--report-dir`.

- Per-paper sidecar: `whisker/<pid>.whisker.json` (schema-versioned, deterministic
  field order).
- Run report: `whisker/report.json` (counts + every result) and
  `whisker/report.md` (a leaderboard table), rewritten each run.
- Bench leaderboard: JSON with `aggregate` (means + `below_floor`) and per-paper
  `rows`. Compare against a committed baseline with `--baseline`.

## Exit codes (CI contract)

`0` ok, `1` error, `3` review, `5` fail. `--gate {pass,review,fail}` sets the
lowest verdict still considered acceptable for exit 0 (default `review`).

## Calibration status

The hard gate (structural gates + `UNIGRAM_COVERAGE_FAIL_EDGE`) is the
trustworthy verdict; the reference advisory edge (`REF_NID_ADVISORY_EDGE` 0.85,
adopted from edgeparse's NID CI floor) only steers a pass to review when tomd and
the oracle disagree on text. Two earlier designs over-failed: hard-gating on
`ref_nid` collapsed to near-all-fail (fixed by `clean_string` + advisory demotion),
and hard-gating on the shingle `coverage` failed 43 papers where tomd had
correctly reflowed multi-column text (95% of words present, 66% sequential). The
fix moved the content gate to the order-invariant `unigram_coverage`, matching
how every benchmark repo separates content from reading order. The unigram edges
(0.85 fail / 0.95 review) mirror DP-Bench/Docling clean-conversion recall norms
but remain provisional, not yet fitted on our own labeled corpus. A `calibrate`
step (label 30-50 papers, pick max recall at FPR <= 10%, commit fitted edges with
recorded TPR/FPR/precision) would replace these with measured operating points;
until then review beats a false pass.

## Tests

whisker is not in the root `testpaths` (standalone). Run it directly:

```bash
uv run --package whisker pytest packages/whisker/tests
```
