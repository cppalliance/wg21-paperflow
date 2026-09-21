# whisker - Agent Rules

## Architecture map (start here)

Reading order for a new agent, from contract to detail:

1. **This file, "What this is" + "Three lanes"**: the mental model. whisker is
   deterministic QA for tomd conversions; three independent lanes (stability,
   fidelity, comprehension) plus two opt-in LLM tools that never gate.
2. **The source tree is the lane boundary.** Three tiers under
   `src/whisker/`:
   - `det/`: the deterministic lane. Scoring, the Lanes 1-3 engines, golden
     QA, the structural alignment checks, `compare/`, `llm_readability/`,
     and the deterministic verb bodies (`det/cli.py`).
   - `llm/`: the opt-in advisory LLM lane (renamed from `tapetum_llm`),
     including the quarantined `vlm/` modules. Never gates.
   - Shared root: what both lanes import (`constants.py`, `metrics.py`,
     `tables.py`, `facts.py`, `gates.py`, `golden_ideals.py`) plus entry
     plumbing (`__main__.py` slim dispatcher, `menu.py`, `cli_common.py`).
     `survey/` and `branding/` are cross-lane tooling at the root.
   Import direction is one-way: `llm/` may import the root and `det/`
   read-only; `det/` and the root never import `llm/` (import-linter
   contracts, guarded by `tests/test_import_contracts.py`). The single
   sanctioned root-to-`llm` crossing is the menu's deferred, function-local
   import; `__main__.py` itself dispatches to `det/` and `survey/` only.
3. **`constants.py`**: every threshold, named. If you are about to type a bare
   numeric literal, it belongs here.
4. **The lane you are touching**:
   - Lane 1 stability: `det/golden.py` + the `golden` verb in `det/cli.py`.
   - Lane 2 fidelity: `metrics.py` -> `det/match.py` ->
     `det/bench.py`/`det/guard.py`, scored in `det/score.py`.
   - Lane 3 comprehension: `facts.py` (+ `tables.py` for grids), gated by the
     `facts` verb and hermetically by `tests/test_comprehension_corpus.py`.
5. **LLM readability contract** (`det/llm_readability/`): whisker's definition
   of a correctly LLM-readable table, specialized for DeepSeek V4. Normative
   `det/llm_readability/deepseek-v4/tables/rules.toml`, not tomd. See "LLM
   readability contract" below. Do not duplicate R1-R13.
6. **The corpus**: `packages/whisker/corpus/` holds `<pid>.facts.jsonl`
   (human/agent-verified assertions), `<pid>.expected.md` (committed
   stability snapshots and hermetic CI substrate), optional `<pid>.gt.md`
   (human-corrected Lane 2 fidelity references and backward-compatible Lane 1
   bootstrap markers), and `<pid>.validation.md` (readback evidence). Authoring
   tools: `det/corpus_tools.py` (`whisker corpus`).
7. **Opt-in LLM layer** (`llm/`, extra `tapetum-llm`, never in CI):
   `adjudicate.py` (advisory fidelity second opinion), `trace_render.py`
   (per-lane `--trace` rendering), `readback.py` +
   `readback_cli.py` (blind comprehension validation of the facts corpus).
8. **Competitor monitor** (`survey/`): repeatable monthly conversion of the
   frozen corpus with tomd and a registered competitor, scored on Lanes 1/2/3.
   Registry in `survey/registry.py`; adapters via `survey/adapters/contract.py`.
   Runtimes land under `%LOCALAPPDATA%/whisker/survey/<name>/<version>/`.
9. **Tests mirror the lanes**: `tests/det/` (deterministic engines and
   verbs), `tests/llm/` (advisory lane, offline), `tests/` root (shared
   modules, cross-lane contract guards, survey, the hermetic Lane 3 corpus
   gate).
10. **Research**: `research/research/` holds the topic dirs and loose
    reports; `research/plans/` holds plans (including the 2026-09-07 lane
    restructure plan); `research/repos/` and `research/.gitignore` stay at
    the research root (third-party clone cache, lint-excluded).
11. **Greppable conventions**: `shortcut:` (deliberate simplification + its
    ceiling), `golden-hook:` (where the future golden-file layer plugs in).
    Harvest with `rg -n "shortcut:|golden-hook:"`.
12. **History**: `CHANGELOG.md` (what changed and why), `FIXPATH-REPORT.md`
    (the 2026-07 hardening pass: design rationale, verification evidence,
    golden-file outlook; its paths predate this tree).

## What this is

Deterministic QA for tomd conversions, with no LLM in the gate (a separate,
opt-in advisory LLM lane, `llm`, is documented below and never gates).
whisker answers two questions:

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

## Command history, merged surface, and result ownership

The current CLI is the merged implementation of three commits:

- Sean Parsons' `cd3cf85` added the deterministic file bridge commands
  `score-file` and `check-facts`, used by tomd's golden-QA subprocess bridge.
- The user-side `58a978c` added the interactive menu, advisory fusion reports,
  blind readback, dormant VLM tooling, and corpus authoring tools.
- Merge commit `29c4ce6` combined both lines. Commit provenance identifies where
  a command entered the tree; it does not assign a personal definition of
  determinism or architectural doctrine to an author.

Top-level `python -m whisker` / `whisker` commands and their result locations:

- Bare `whisker` in a TTY opens the menu. With PIDs or `--all`, it runs
  deterministic workspace scoring: human or JSON output goes to stdout and,
  unless `--no-write`, per-paper sidecars plus `report.md`/`report.json` go to
  `whisker/det/`.
- `bench` emits its leaderboard JSON to stdout and optionally the `--out` file.
- `guard` emits a human summary or `--json` to stdout, optionally writes
  `--out`, and only rewrites its named baseline under explicit `--update`.
- `golden` emits a human summary or `--json` to stdout, optionally writes
  `--out`, and only rewrites corpus snapshots under explicit `--update`.
- `facts` emits a human summary or `--json` to stdout and optionally writes
  `--out`.
- `calibrate` emits fitted-edge JSON to stdout and optionally writes `--out`;
  it does not promote thresholds.
- `corpus stratify` reports candidates through logging; `corpus draft` logs and
  writes draft facts to its explicit `--out` directory.
- `score-file` emits one human result or JSON object to stdout. When invoked by
  `tomd score`, that JSON is rendered in tomd's whisker metrics panel.
- `check-facts` emits one human result or JSON object to stdout. When invoked by
  `tomd score`, that JSON is rendered in tomd's comprehension panel.
- `llm-readability rules` / `llm-readability profiles` / `llm-readability check`
  inspect or evaluate the LLM-readable table contract. See "LLM readability
  contract". Candidate `check` cannot certify a model.
- `survey` is the repeatable competitor monitor against the frozen corpus
  contract in `packages/whisker/benchmark/corpus/`. `list` shows registered
  competitors; `status [NAME]` reports last success and due state (exit 2 = due:
  older than 30 days or newer upstream) and stays silent about network failure so
  it works offline; `install NAME [--force]` builds the competitor runtime into
  `%LOCALAPPDATA%/whisker/survey/<name>/<version>/` (applying locked patches),
  verifies integrity and the version pin, then stops; `run NAME
  [--refresh-runtime] [--out DIR]` installs on demand, converts with tomd and the
  competitor, scores Lanes 1/2/3, and writes `survey-<name>.json`/`.md` under
  `packages/whisker/benchmark/reports/YYYY-MM/` (or `--out`); `purge` removes
  runtime caches; `clean` removes run bundles; `reports [--open]` locates
  generated reports.
- Competitors resolve through `survey/registry.py`, and each spec names an
  adapter module loaded by `survey/adapters/contract.py`, which rejects an
  incomplete adapter before any install runs. Nothing in the CLI is
  Marker-specific. Adding a project is an adapter module plus a lockfile; see
  `packages/whisker/benchmark/protocol/ADDING-A-COMPETITOR.md`.

- `qa <verb>` (also `qa-<verb>`) is the golden QA workflow (migrated from
  tomd). Verbs: `add` (stage a source), `generate` (seed an ideal from tomd),
  `render` (PDF page images, deferred),
  `score` (structural comparison + rich panel), `bless` (lock a baseline),
  `issue` (draft GitHub issues from gaps), `rebless` (re-lock after
  improvements), `fact` (author facts from an ideal), `anchor` (author anchors
  from an ideal). These are on-demand developer tools, not part of the
  deterministic `(1)` run. The deterministic run enriches golden-backed papers
  automatically via `score_paper` -> `golden_compare`.

The last two file commands do not write whisker reports. Their stdout/tomd
panels are not included in `whisker/det/report.md` or
`whisker/llm/report-merged.md`. The opt-in `whisker-tapetum-llm` executable owns
tapetum sidecars, inspection output, and fusion reports; `whisker-readback`
owns terminal readback output and explicit `<pid>.readback.md` files. The VLM
modules have no production command or report path and remain dormant.

## Three lanes (do not conflate them)

Regression detection is split into three independent lanes that answer different
questions. They are deliberately NOT interchangeable; a paper can pass two and
fail the third.

- **Lane 1 Stability** (`whisker golden`, `det/golden.py`): did the normalized
  markdown change vs a committed `<pid>.expected.md` snapshot. Exact `difflib`
  compare; catches silent regressions AND silent improvements. Bless a change by
  reviewing the diff, then `--update`. A blessed snapshot is NOT a correctness
  oracle: it freezes whatever a human approved, bugs included. Membership is
  the case-insensitive, PID-sorted union of existing expected snapshots and
  optional GT markers. Expected-only members compare normally; GT-only members
  remain `new` for `--update` / `--fail-on-new` compatibility.
- **Lane 2 Fidelity** (`whisker bench` / `whisker guard`): how CLOSE is the
  output to a human-corrected `<pid>.gt.md` reference, on
  `nid`/`teds`/`mhs`/`content_recall`. This is resemblance, not comprehension.
- **Lane 3 Comprehension** (`whisker facts`, `facts.py`): can an LLM still
  RECOVER the paper's facts from the markdown. Deterministic source-verified
  assertions (`present`/`absent`/`order`/`table`/`math`), no LLM in the loop.

**Fidelity is not comprehension.** A reflow can score high on every Lane 2 axis
and still scramble a table cell or drop a formula's exponent so a downstream LLM
reads "row 3, column 2" wrong, with every fidelity metric green. Only Lane 3
catches that. Lane 3 also sidesteps the ground-truth-provenance problem: across
the 28 surveyed converters, none has an automatic "this file is 100% correct"
oracle, and only `olmocr` tests comprehension at all. A handful of source-verified
facts per paper are cheap to author and independent of any single `tomd` output,
so they are the honest WG21 ground truth without a perfect golden file.

`whisker guard` additionally folds substring anchors (`det/anchors.py`,
`<pid>.anchors.json`) and Lane 3 facts (`<pid>.facts.jsonl`) in CONJUNCTIVELY: a
missed anchor or a failed VERIFIED fact is a hard fail even when the numeric
slack holds. The shared micro-corpus layout lives in `packages/whisker/corpus/`.

whisker is standalone. It depends on `paperstore`, `tomd`, `markitdown` (the
reference oracle), `rapidfuzz` (MIT edit distance), `apted` + `lxml` (the verbatim
PubTabNet/OmniDocBench TEDS), `mistune` (heading-tree AST, shared with tomd QA),
`grits-metric` (advisory GriTS-Con cell-F1 table axis), `pylatexenc` (inline-LaTeX
folding in the text normalizer), and `numpy` + `scipy` (the block-matching cost
matrix and Hungarian assignment). It edits no other package, imports tomd's
converter and content-check functions (read-only), owns all golden-QA scoring
code, reads tomd's golden ideal/source fixtures read-only, and never modifies the
paperstore/cli source.

## LLM readability contract

Whisker is the normative authority for what a correctly LLM-readable table
extraction is. tomd is a later audited producer of candidate markdown, not the
rule owner: a rule is justified by evidence about how reading models fail, never
by what the converter emits today.

The normative copy of the rules is `det/llm_readability/deepseek-v4/tables/rules.toml`,
a single file carrying the full contract (R1-R13, thresholds, applicability)
with DeepSeek-specific values baked in, plus the profile metadata.
The DeepSeek V4 profile (`deepseek-v4`) has certification status **pending**.
Do not restate R1-R13 here. The package README is the architectural map:

- [`det/llm_readability/README.md`](det/llm_readability/README.md)
- [`llm/calibration/tables/TABLE-CALIBRATION.md`](llm/calibration/tables/TABLE-CALIBRATION.md)
  and [`llm/calibration/codeblocks/CODEBLOCK-CALIBRATION.md`](llm/calibration/codeblocks/CODEBLOCK-CALIBRATION.md):
  punch-list locks. Add a new helper for a new defect class. Do not
  loosen, merge, or rename an existing R2 heuristic when a paper fixture
  or control test goes red. See also
  [`.cursor/rules/whisker-calibration.mdc`](../../../../.cursor/rules/whisker-calibration.mdc)
  for the standing convention on what "whisker kalibrieren" means.

`llm_readability` is deterministic core: it must not import `llm` or
`pipeline`. Its verdicts are not `run_gates` / `WhiskerResult` outcomes and never
feed `whisker --gate`.

- `document_deterministic_ok`: every applicable HARD rule that candidate
  markdown alone can prove was checked and passed, and the document is not
  vacuous.
- `model_certified` (aliased as `certified`): a profile resolved, every method
  that profile demands actually ran, and no applicable HARD rule is failing or
  unevaluated. Never derivable from candidate markdown alone.
- `vacuous` / no-table: nothing was certified. Never a pass, never a
  certification.

Discover the contract from the CLI:

```powershell
whisker llm-readability rules
whisker llm-readability profiles
whisker llm-readability check path\to\candidate.md
```

`check` is candidate-side deterministic evaluation. It cannot print a model
certification: a file carries no source, no model, and no probe results.

Changing a rule requires, in one pass: cited evidence, a `[contract] version`
bump in the profile's `rules.toml`, and green contract tests. Do not duplicate
normative prompt prose; judges consume `render_llm_rubric()` from the same TOML.

DeepSeek V4 Pro is **not certified**. Table model certification stays pending
until a successful versioned live run with the required source, readback, and
corrupt-control probes.

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
whisker bench --corpus ./gt --baseline whisker/det/report.json   # benchmark mode
whisker facts --corpus ./corpus       # Lane 3: gate on <pid>.facts.jsonl
whisker corpus stratify --corpus ./corpus   # list zero-coverage authoring candidates
whisker corpus draft P1234R5 --out ./corpus # generate a checked:draft facts scaffold
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
  skipped]) in Ts ===`, colored by the worst verdict present. In default and
  verbose modes, a qualifier line follows: `"passed" means no gate fired, not
  that the conversion is correct.` This line is suppressed in `--quiet` mode,
  where the footer is the sole output.

`render_summary` in `det/report.py` is a pure function: color and elapsed are
parameters, so the rendering is deterministic and unit-tested on plain text.

## Module layout

The tree mirrors the lanes: `det/` is the deterministic lane, `llm/` the
opt-in advisory lane, and the package root holds the modules both lanes
share (import-graph proven: the LLM lane imports exactly these, plus
`det.score` verdicts/paths and `det.llm_readability`, read-only).

Shared root:

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
- `gates.py` - reference-free structural gates. Every gate is hard.
  `no_toc_leak` catches TOC content left in the body (golden-qa-gap MC2,
  PR-replay #290/#293): a standalone `Contents` / `Table of Contents` line, or
  a page-numbered duplicate heading pair (`## 1. Introduction 3` alongside
  `## 1. Introduction`). Matching is pairwise (stem + trailing bare number vs
  the exact same stem), so unrelated numbered headings (`Step 1` / `Step 2`)
  never collide. tomd's contract strips the TOC; a TOC surviving into the body
  is a conversion defect, and a leaked TOC in a golden ideal is a fixture bug.
- `golden_ideals.py` - tomd golden ideals as human-corrected structural ground
  truth for the deterministic lane. Auto-discovers tomd's approved ideals
  (`packages/tomd/tests/fixtures/golden/ideals/<pid>.md`) by walking up from
  the whisker source; `score_against_ideal` computes the Lane-2 panel
  (nid/teds/mhs/content-recall + overall). Read-only file access into tomd's
  fixture tree, no tomd-private imports. ADVISORY ONLY in the verdict:
  below-floor axes raise review flags, never hard fails. Any new
  `ideals/*.md` file is picked up on the next run. tomd remains the canonical
  STORAGE location for ideal files and their sources; whisker owns all
  golden-QA scoring, gap analysis, and CLI verbs. The staged PDF/HTML source
  remains the factual authority if an ideal and its source disagree.
- `facts.py` - Lane 3 comprehension. `check_facts(md, facts)` evaluates
  deterministic, source-verified assertions from `<pid>.facts.jsonl`: `present` /
  `absent` (fuzzy within a `max_diffs` budget: rapidfuzz locates the window, then
  an exact free-start/free-end substring DP measures the true edit count, since
  rapidfuzz's Indel window can trim a boundary char), `order` (strictly
  increasing positions), `table` (locate a cell, check `up`/`down`/`left`/`right`/
  `heading` neighbors, the direct "row 3, column 2" test), `math` (presence on a
  LaTeX-folded surface that KEEPS `^`/`_`/`=`, and now case + relational
  operators, so `X >= Y` and `x <= y` stay distinguishable), `code` (raw-surface
  snippet presence, fence-aware), `xref` (raw-surface revision-sensitive paper
  reference, e.g. `[P1234R5]`), `image_ref` (`![...](...)` presence, optionally
  matching a path/alt substring). `surface: "raw"` is an optional mode on
  `present`/`absent`/`order` (default is the alnum-folded `normalized_text`
  surface): whitespace-collapse only, keeping operators and case, so `x != y`
  vs `x == y` and `C++` vs `c++` become assertable (`code`/`xref`/`image_ref`
  always use raw surface). `table` facts take an optional `table_heading`
  anchor (matched against the table's header row) to disambiguate a cell value
  that repeats across tables (the decoy-table exploit). WITH an anchor the
  check is fail-closed: EVERY occurrence of the cell in heading-matching
  tables must satisfy the neighbors, so a decoy table sharing the heading and
  contradicting the genuine row fails the fact instead of being shadowed.
  WITHOUT an anchor, ALL occurrences are tried and ANY satisfying occurrence
  passes (cell values legitimately repeat across unrelated tables; this fixed
  the prior first-match-wins false pass). Tables are
  read from BOTH markdown pipe tables and tomd-emitted HTML `<table>` blocks
  (`tables.py`), so Tony/SPEC/NB-Ballot tables are no longer invisible to
  facts. `auto_baseline_checks(md)` (zero-authoring, olmOCR-pattern) asserts
  non-empty alphanumeric content and no long repeated n-grams (mojibake); not
  yet wired into `whisker facts`/`guard` output, callable standalone. Only
  `checked: verified` facts gate; drafts are reported but advisory.
  Macro-averaged per type. No LLM.
- `tables.py` - shared table-grid parsing used by both `facts.py` (cell-
  neighbor checks) and `det/bench.py` (TEDS scoring), replacing two independent
  pipe-table scanners. `parse_pipe_tables` (fence-aware pipe-table scanner) and
  `parse_html_tables` (stdlib `html.parser`, no new dependency) both return the
  same grid shape: a list of rows, each a list of raw cell strings.
- `cli_common.py` - CLI helpers shared by both lane CLIs: `open_backend`,
  `render_progress`, `verdict_exit_code`. The extraction removed the LLM
  lane's private import of `__main__._render_progress`; `det/cli.py` and
  `llm/cli.py` both import from here.
- `menu.py` - interactive TTY menu, launched by bare `whisker` in a TTY.
  Dispatches to `det/cli.py` verb bodies with synthesized argv and reaches
  `llm/` only through deferred, function-local imports (the one sanctioned
  root-to-`llm` crossing).
- `survey/` - repeatable monthly competitor monitor. `registry.py` resolves
  competitors; each spec names an adapter loaded by `adapters/contract.py`,
  which rejects an incomplete adapter before install. Runtimes land under
  `%LOCALAPPDATA%/whisker/survey/<name>/<version>/`. Reports under
  `packages/whisker/benchmark/reports/YYYY-MM/`. See Command history for the
  `whisker survey` verb surface.
- `branding/` - C++ Alliance report theme shared by every human-facing
  report: `theme.py` (branded HTML shell with inlined assets), `markdown.py`
  (report markdown -> themed HTML), `pdf.py` (HTML -> PDF via headless
  Chromium). `branding/assets/` ships as package data.
- `__main__.py` - the `whisker` console entry, a slim dispatcher only (its
  shape is guarded by `tests/test_cli_structure.py`). Scoring and lane verbs
  route to `det/cli.py`; `llm-readability` routes to
  `det/llm_readability/cli.py`, `qa` to `det/qa_cli.py`, `survey` to
  `survey/cli.py`.

det/ (deterministic lane):

- `det/cli.py` - the deterministic verb bodies (`score_main`, `bench_main`,
  `guard_main`, `golden_main`, `facts_main`, `delta_main`,
  `calibrate_main`, `corpus_main`, `score_file_main`,
  `check_facts_main`). Owns all det-lane persistence and stdout: per-paper
  sidecars, `report.json`/`report.md`, and the `report.prev.json` snapshot.
  `whisker facts`/`whisker guard` fail (not just warn) when a paper's
  `.facts.jsonl` has zero `checked: verified` facts (vacuous green: a facts
  file that never gates anything proves nothing about comprehension),
  mirroring the pre-existing CI guard in `test_comprehension_corpus.py`.
- `det/match.py` - block-level text matching (OmniDocBench `match_quick` port): split
  prose into blocks, normalize, build a NED cost matrix, Hungarian-assign, accept
  at <= 0.70 NED, fuzzy-rescue embedded GT blocks at < 0.40. `block_text_nid`
  (reorder-robust `1 - edit_whole`) and `reading_order_ned` (a SEPARATE advisory
  axis) come from one matching pass. The O(gt*pred) matrix is capped
  (`BLOCK_MATRIX_CELL_BUDGET`): giant papers fall back to the whole-document
  `text_nid`. Used by `bench`; the oracle deliberately does NOT use it (see below).
- `det/reference.py` - `reference_markdown(pid, backend, *, engine) -> str`. Runs
  the oracle (markitdown) on the staged source, no network/LLM. Library returns
  data. The engine is pluggable (`REFERENCE_ENGINES`).
- `det/pdf_geometry.py` - shared PDF geometry extraction for `paragraph_align` and
  `code_fence_align`. Owns `PdfLine` (per-line position, baseline, fonts,
  sizes), `load_pdf_lines` (PyMuPDF), `body_font_size`, and
  `is_monospace_line` (delegates to tomd's triple-signal `classify_monospace`,
  which covers Courier, cmtt, lmtt, Consolas, Menlo and other monospace
  families). Both structural check modules import from here.
- `det/paragraph_align.py` - source-vs-candidate paragraph-boundary comparison
  (PDF geometry, deterministic, no LLM). Closes a structural blind spot: every
  other source-aware signal is token-based, so a dropped paragraph break moves
  no token and leaves coverage, drift, punct recall and the LLM lane all green
  (PR #284 p0957r8: an all-pages LLM run cleared both defects at 0.98). The
  detector picks ONE of two conventions per document. A first-line indent is
  chosen by ISOLATION (is the indented line followed by a margin line?), never
  by frequency: on p0957r8 the wording-block indent at x0=75.0 has more lines
  than the real paragraph indent at x0=62.5 and wins on count while scoring
  0.00 against 0.67 on isolation. The parskip fallback measures baseline to
  baseline, never bbox top, because footnote superscripts inflate the bbox and
  invent breaks (p3556r0: 15.57 against an 11.96 leading, two false positives).
  Only the MERGED direction is emitted; the inverse measured ~54% precision
  (captions, notes and page-opening lines are legitimately indented) and is
  deliberately withheld rather than shipped as noise. HTML sources report
  `unsupported`, an undetectable convention `abstained`; neither flags.
  Validated on the five PDF goldens plus the PR #284 pair: 2 true positives,
  0 false positives.
- `det/code_fence_align.py` - source-vs-candidate code-fence boundary comparison
  (PDF font geometry, deterministic, no LLM). Closes the second token-preserving
  structural blind spot after paragraph boundaries: a prose line swallowed into
  a fence or a code listing left unfenced moves no token, so coverage and the
  LLM lane stay green. Two directions: `prose_in_fence` (fenced line matched
  a non-monospaced PDF line), `code_outside_fence` (a run of >= 3 consecutive
  monospaced PDF lines appeared outside any fence). Abstains when the source is
  not a PDF, has no monospaced font, or matches are ambiguous. Uses
  `pdf_geometry.is_monospace_line` (tomd's `classify_monospace`). Soft only.
- `det/score.py` - `score_paper(pid, backend, *, reference_engine="markitdown",
  ideals_dir=None) -> WhiskerResult` + the trichotomy verdict.
  `score_markdown(...)` is the backend-free core for tests (pass
  `reference_md=` to exercise the oracle path, `ideal_md=` for the ideal
  panel). `score_paper` auto-discovers a golden ideal per pid (see
  `golden_ideals.py`) and, when found, layers the ideal panel on as advisory
  soft flags against the Lane-2 floors AND runs `golden_compare` to produce
  per-axis structural breakdown (`gc_*` fields: composite, frontmatter,
  heading, heading_text/level/nesting, list, code, table, text, worst_axis).
  The oracle `ref_nid` is the WHOLE-DOCUMENT `text_nid` on `normalized_text`, NOT
  block-matched: markitdown blocks the page at an erratic granularity (often a
  few giant blocks), and block matching without an adjacency-merge under-scores
  those by up to 0.57 vs the full-document nid (measured), which would
  manufacture false advisory-review flags. Block matching is reserved for `bench`
  against well-formed labeled GT.
- `det/bench.py` - `run_bench(pairs) -> [BenchRow]` + `aggregate`, the leaderboard.
  `nid` is `block_text_nid` (reorder-robust); `content_recall` is multiset
  bag-of-words recall of GT content in the candidate (catches dropped sections
  edit distance hides), a first-class gate (floor + per-paper guard) but NOT
  folded into `overall` (strata stay separate); `reading_order` and `grits_con`
  (GriTS-Con cell-content F1, complementary to `teds`) are reported as separate
  ADVISORY axes, never folded into `overall` and never gated (`grits_con` until
  it has its own calibration). `teds`/`mhs`/`grits_con` are `None` when the
  reference lacks that modality (null-eligibility).
- `det/guard.py` - per-paper, per-axis regression guard behind `whisker guard`.
  `bench` reports corpus means, so one paper can collapse while the mean holds;
  `diff_rows` diffs EACH paper's EACH axis (`nid`/`teds`/`mhs`/
  `content_recall`/`overall`) against a committed baseline and fails on any
  per-paper regression. Per-axis floors backstop papers with no baseline entry;
  a known-weak paper re-flags only when it gets WORSE or crosses a floor
  downward. Slack, floors, and the stamped `tool_versions` are read from the
  baseline itself (a dependency bump hard-fails before any diff); `--update`
  is the explicit refresh ritual. Library returns data (`GuardReport`).
- `det/golden.py` - Lane 1 stability. `diff_goldens(items)` exact-compares each
  candidate's `normalize_for_exact_lane(...)` against a committed
  `<pid>.expected.md` snapshot (stdlib `difflib`). Decoupled from metrics: bless
  is a human reviewing the diff, never a metric threshold. Optional
  `expected_failures` (in `golden.json`) flag known-imperfect snapshots that must
  fail on silent change AND silent improvement.
- `det/golden_compare.py` - deterministic structural comparator (Sean Parsons).
  Parses two Markdown strings into a normalized block tree and scores how well
  they match across six independent axes (front-matter, heading, list, code,
  table, per-block text). Pure: no I/O, no LLM. Migrated from
  `tomd.lib.golden_compare`. The `StructuralScore` result feeds into
  `score_paper` as the `gc_*` sidecar fields when a golden ideal exists.
- `det/golden_gaps.py` - gap analysis between tomd output and golden ideals (Sean
  Parsons). `locate_gaps` returns per-axis `GoldenGap` objects; `draft_issues`
  formats them as GitHub issue drafts. Migrated from `tomd.lib.golden_gaps`.
- `det/golden_qa.py` - golden QA orchestration (Sean Parsons). `find_source`,
  `score_stem`, `generate_ideal`, `bless_stem`, `rebless_stems`, and the
  render helper for the on-demand QA workflow. Subprocess bridges
  converted to in-process calls. LLM/network functions (`download_source`,
  `review_ideal`, `_claude_runner`) were stripped; `generate_ideal` fails
  closed if no source is staged locally. Migrated from `tomd.lib.golden_qa`.
- `det/qa_cli.py` - on-demand golden QA CLI verbs (Sean Parsons). Provides
  `whisker qa-<verb>` commands: add, generate, render, score, bless,
  issue, rebless, fact, anchor. The `review` verb was removed (its
  backing `review_ideal` function was stripped from `golden_qa.py`).
  Migrated from `tomd.cli`. Routed from `__main__.py`.
- `det/anchors.py` - per-paper substring/order tripwires. `check_anchors(md, spec)`
  over `<pid>.anchors.json`: `must_contain` / `must_not_contain` / `ordered`
  chains / regex `patterns`, on the `raw` or `normalized` surface. Conjunctive
  hard fail in `whisker guard`.
- `det/corpus_tools.py` - whisker-local corpus-authoring helpers (`whisker corpus`
  CLI). `stratify_candidates` classifies zero-coverage papers by structural
  stratum (pipe/HTML tables, display math, code-heavy, footnotes, images) so a
  human can pick a representative sample. Display math is counted on a
  fence-stripped surface (`_strip_fenced_blocks`): `$` is legal in code
  identifiers (P4234R0), so `$$...$$` inside code fences is never math.
  `draft_facts_scaffold` generates a
  `checked: draft` `.facts.jsonl` skeleton per paper (heading order/presence,
  one table fact per detected table, math/code/image/xref facts where present)
  for a human to review, correct, and promote to `verified`. Never writes
  `verified` itself; blessing stays a manual step.
- `det/report.py` - `build_report` / `render_report_md` / `render_summary`.
- `det/delta.py` - run-to-run comparison of two det-lane `report.json`
  payloads behind `whisker delta` (exit 0 clean, 3 regressed, 1 operational
  error). Pure library returning `DeltaResult`/`DeltaFinding`; `det/cli.py`
  reads the reports and owns rendering and exit codes.
- `det/calibrate.py` - fits the content-coverage edges from labeled,
  fit/holdout-split data behind `whisker calibrate`. Returns data only; a
  human promotes fitted edges into `constants.py`.
- `det/canonical.py` - convention-level canonicalization (`:::wording`
  fenced divs, heading section numbers, `<ins>`/`<del>` edit markup) applied
  to BOTH candidate and reference, so block agreement measures conversion
  quality, not markup dialect.
- `det/structural.py` - structural marker counts (`count_markers`) for cheap
  categorical triage: a converter emitting zero code fences still scores
  respectably on char-level recall; per-class counts expose that directly.
- `det/probe_strength.py` - Lane-3 fact-set mutilators
  (`strip_all_structure`, `keep_fraction`, `shuffle_sections`): a fact set
  that still passes on a severely degraded document is too easy to be
  measuring conversion quality.
- `det/llm_readability/` - LLM-readable table contract (`deepseek-v4/tables/rules.toml`).
  See "LLM readability contract". Not a `run_gates` input.
- `det/compare/` - block-aligned Markdown side-by-side comparison (align, HTML
  render, provenance). Benchmark tooling only: no console script, not routed
  from `__main__`. Invoke as `python -m whisker.det.compare.cli run|clean`.
  Called by `gen_compare_pdf.py` and `gen_appendix.py` in
  `packages/whisker/benchmark/tools/`, not by operators.

llm/ (opt-in advisory lane, extra `tapetum-llm`, never in CI):

- The behavior contract lives in "llm advisory LLM lane" below; services,
  cascade steps, and the full system prompt live in `llm/llm.md`. Entry
  points: `llm/cli.py` (`whisker-tapetum-llm`) and `llm/readback_cli.py`
  (`whisker-readback`). Core modules: `adjudicate.py` (HTML/text cascade),
  `pdf_judge.py` (PDF text-layer judge), `source_router.py` +
  `unit_judge.py` (risky-unit routing and scoped checks), `fusion.py` +
  `fusion_report.py` (demote-only fusion and the merged report),
  `readback.py` (blind comprehension Q&A library), `trace_render.py`
  (`--trace` rendering). `llm/vlm/` is quarantined: no production entry
  point imports it, and `tests/llm/test_vlm_lane.py` enforces that. The
  lane imports the shared root and `det/` read-only; nothing outside
  `llm/` imports it.

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
uncertain marker, any source paragraph break missing from the candidate
(`det/paragraph_align.py`), and any code fence boundary mismatch
(`det/code_fence_align.py`). Misaligned regions are soft only: tomd intentionally
strips furniture (headers, footers, page numbers, TOCs), so some regions are
expected on clean papers; `unigram_coverage` below the floor is the hard signal
for missing content. The paragraph signal is soft for a different reason: tomd
flattens paragraph structure by design today, so hard-gating it would fail the
fleet the way hard-gating `ref_nid` and the shingle `coverage` did (see
"Calibration status"). The golden-QA bless path, where the candidate claims to
BE the measuring stick, is where it can legitimately bite.

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
  dataclasses. Only the CLI layer (`det/cli.py` verb bodies, dispatched by
  `__main__.py`) writes sidecars and the leaderboard.
- **Thresholds are named constants.** No bare numeric literal in the scoring
  path. New tunables go in `constants.py` with a comment on what they gate.
- **BSL-1.0 header** on every new `.py` file. `__init__.py` is re-exports only.

## Artifacts

All whisker output is grouped under a single `whisker/` directory in the data
dir (sibling of `paperstore/`), not scattered among the converted papers. The
two lanes are separated on disk: deterministic artifacts under `whisker/det/`,
advisory LLM artifacts (tapetum sidecars, merged reports, inspect report) under
`whisker/llm/`. Override the deterministic location with `--report-dir`.

- Per-paper sidecar: `whisker/det/<pid>.whisker.json` (schema-versioned,
  deterministic field order).
- Run report: `whisker/det/report.json` (counts + every result) and
  `whisker/det/report.md` (a leaderboard table), rewritten each run.
- LLM lane: `whisker/llm/<pid>.whisker.tapetum.json` (advisory adjudication +
  fusion block), `whisker/llm/report-merged.md/json`, and
  `whisker/llm/tapetum-inspect.md`. Freshness contract: a completed
  full-corpus LLM run (`whisker-tapetum-llm` with no PIDs) refreshes
  per-paper sidecars AND `report-merged.md/json`. Partial runs (explicit
  PIDs, `--review-all`) update only selected sidecars and do not rebuild
  the corpus-wide aggregate. `--fuse-only` recomputes fusion blocks and
  the aggregate from existing sidecars without LLM calls.
  The aggregate's `det` column is NOT a cached copy: `build_merged_json`
  re-derives it from the live `whisker/det/<pid>.whisker.json` sidecars on
  every rebuild. Consequence: a bare `whisker --all` (which rescores det
  sidecars without triggering a rebuild) leaves the aggregate's det column
  frozen exactly as a partial LLM run leaves its llm column frozen. The
  staleness probe (`_llm_report_is_stale`) therefore watches BOTH sidecar
  families (tapetum `*.whisker.tapetum.json` AND det `*.whisker.json`) and
  warns when either postdates the aggregate.
  All merged results are advisory and never replace deterministic verdicts
  or gate exit codes. When a tomd ideal exists, the tapetum sidecar also carries the
  separate `ideal_verification` result. Fusion schema v4 exposes only its
  compact verdict/count; the inspect report renders every grounded discrepancy,
  while the merged report remains bounded to verdict/count. Old sidecars and
  papers without ideals use a neutral absent marker.
- Bench leaderboard: JSON with `aggregate` (means + `below_floor`) and per-paper
  `rows`. Compare against a committed baseline with `--baseline`.

## Exit codes (CI contract)

`0` ok, `1` error, `3` review, `5` fail. `--gate {pass,review,fail}` sets the
lowest verdict still considered acceptable for exit 0 (default `review`).

`whisker-tapetum-llm` uses a separate, simpler contract: advisory verdicts
(pass/review/fail) always exit 0; operational errors (exception, timeout,
`status="error"`) exit 1 after the batch completes. Successful papers are
persisted even when another paper in the batch fails.

`whisker delta` returns `0` clean, `3` if any paper regressed, `1` on an
operational error. `whisker delta --llm` returns `0` or `1` only: it renders
both a deterministic and an advisory section but gates on neither.

Rule: **exactly one command gates a given signal, and it is the one reading
the artifact whose baseline moves in lockstep with it.** `whisker delta` owns
deterministic regression gating because it reads `report.json` against
`report.prev.json`, both written by the same det-lane run. `whisker delta
--llm` reads `report-merged.json`, whose `det` column is re-derived from live
det sidecars (honest) but only on an aggregate rebuild (a full LLM run or
`--fuse-only`). That is a different sampling interval from the det lane's own
delta, so the two disagree in both directions: a `whisker --all` with no
tapetum run afterwards moves one and not the other, and a late `--fuse-only`
surfaces a move the det baseline already absorbed. Two gates on one signal
over two intervals contradict each other by construction. Any future view
that mirrors a gated signal onto a second artifact inherits this rule: render
it, do not gate it.

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
step (label 30-50 papers on a fit/holdout split, pick max recall at a target
FPR, commit fitted edges with recorded holdout TPR/FPR/precision) would replace
these with measured operating points; until then review beats a false pass.
The fail and review edges get two distinct FPR ceilings, not one shared
number, because the two errors have asymmetric cost: `DEFAULT_TARGET_FPR_FAIL_EDGE`
(0.05) caps the fail-edge fit (a false positive there wrongly hard-fails a
good paper, the more severe error) and `DEFAULT_TARGET_FPR_REVIEW_EDGE` (0.10)
caps the review-edge fit (a false positive there only flags a good paper for
human review, a cheaper, recoverable error).

## Comprehension corpus + one-time LLM read-back (Lane 3 in CI)

Lane 3 now runs in CI against a real corpus member, not just engine unit tests.
`tests/test_comprehension_corpus.py` is the hermetic gate: it reads the committed
`corpus/<pid>.expected.md` (the substrate) and `corpus/<pid>.facts.jsonl`, runs
`check_facts`, and asserts every `checked: verified` fact holds, that at least one
verified fact exists (no vacuous green), and that a deliberately scrambled
snapshot FAILS (a canary, so the gate has teeth). It needs no backend and no
`data/`, so it gates in CI where the `whisker facts` CLI cannot: the CLI reads the
candidate from the paperstore backend (`backend.get_paper_md`), which is absent in
CI. whisker is now in the `.github/workflows/tests.yml` package matrix (it was
missing); the hermetic suite passes with no `WG21_DATA_DIR`.

Canonical corpus members (5 papers, 37 verified facts, all with committed
`expected.md` snapshots so all gate hermetically in CI, and currently no
`gt.md` files): **P4182R0** (8
facts, the original POC member; its snapshot is byte-identical to
`run_pipeline`'s output), **P4185R0** (9 facts incl. 4 `math`), and the
wave-2 papers **P4234R0** (`$`-identifiers: `code`/`xref`/raw-surface
`present`), **N5040** (pipe AND HTML tables), **P0876R23** (poll tables,
code, xref). Three canaries prove the gate has teeth, one per exploit class:
scrambled table cell (P4182R0), flipped math relation (P4185R0), mangled
code snippet (P4234R0).

The deterministic facts are a deterministic PROXY for what a downstream LLM must recover.
That proxy is validated ONCE, empirically and out of band: hand a fresh LLM ONLY
the converted markdown plus the fact questions, let it answer blind, compare to
the verified facts. P4182R0 passed 3x 8/8 including the two table cells (recorded
in `corpus/P4182R0.validation.md`). This read-back is NEVER in CI (determinism,
cost, model-sovereignty); it is the one-time anchor that justifies trusting the
LLM-free gate. A "regenerate similar text" round-trip is the WRONG test (LLMs
paraphrase, so resemblance measures fidelity, not comprehension); the test is
question answering ("row X, column Y reads what?").

Authoring and source verification stay separate (provenance): a fact ships as
`checked: draft` and is flipped to `checked: verified` only after its needle is
located verbatim in the SOURCE pdf/html; only verified facts gate. Honest status:
all current facts were authored and source-verified against staged sources at
the user's direction. The audit requires reproducible source provenance and
canary sensitivity, not a separate human-blessing ceremony. The full POC
writeup (goal, every command, evidence) is
`research/research/comprehension-poc-report.md`.

Note on reading whisker numbers for a clean paper: trust `uni` (content recall)
and `qa`; `teds`/`mhs` against the markitdown oracle are structurally near-zero
(different formatting, not bad tables) and never gate; `ovr` is only a display
composite. The LLM read-back, not the oracle's `teds`, is the comprehension proof.

## llm advisory LLM lane (opt-in, never gates)

The deterministic gate above stays LLM-free and reproducible. `llm` is a
SEPARATE, opt-in advisory layer (install `whisker[tapetum-llm]`, run the
`whisker-tapetum-llm` CLI) that **triages the fuzzy residuum**: conversion
anomalies that deterministic checks cannot verify mechanically. The deterministic
lane (whisker core, source router, table comparator) is the recall owner for
mechanically checkable classes (heading labels, cell content, token counts). The
LLM lane handles the false-pass case (token-preserving semantic corruption,
table/cell swaps, math collapse, code garbling that survives order-blind
`unigram_coverage`) and the false-fail case (heading-monotone-only fails that
are cosmetic). It does NOT validate the golden ideal; it triages. It NEVER
hard-fails, is never in the `whisker --gate` CI contract, and never overwrites
the whisker verdict on record.

### Why the LLM never gates (design rationale)

The advisory-only architecture is a deliberate, evidence-based decision:

1. **Ecosystem norm.** 0 of 31 surveyed document-conversion QA repositories
   gate mechanically on LLM signals. LLM output is used for diagnostics,
   triage, or human review, never as a hard pass/fail authority.
2. **Measured instability.** Identical reruns on the Alliance pod show a
   >= 25 % verdict-flip rate (same paper, same model, same prompt). No
   production gate can tolerate that variance.
3. **Anti-calibrated confidence.** The model's self-reported confidence is
   anti-correlated with accuracy: 96/96 clear firings at >= 0.95 confidence,
   including a known false-clear at 1.00 (PR #282 p4020r0).
4. **Model sovereignty.** The project targets open-weight self-hosted models.
   Their output is less stable than cloud-API models (no server-side
   batch-invariant kernels). Deterministic-first is necessary, not just
   convenient.
5. **Fusion asymmetry.** The LLM can demote (pass -> review, fail -> review via
   RESCUE) but can never hard-fail, and can never override a deterministic
   `fail` into a `pass`. This one-way ratchet is the architectural consequence
   of the instability above.

Full evidence: `research/research/llm-qa-integration/SYNTHESIS.md`.

- **Run modes.** Bare `whisker-tapetum-llm` (no PIDs) is a full run: every
  converted paper, with automatic fingerprint-based skip (sidecar records
  SHA-256 of markdown, source, prompt, model, output schema,
  `_LANE_VERSION` (currently 27), a `unit_check_mode` key tracking the
  `TAPETUM_VERDICT_FIRST` toggle, and `coverage_mode`; unchanged papers are
  skipped, `--force` re-evaluates everything). `_LANE_VERSION` 11 -> 12
  closed a fingerprint gap: the verdict-first `UnitCheckClear`/
  `UnitCheckDefects` schemas were dispatched to the LLM but never hashed, so
  a schema change there could silently poison incremental reuse; the bump
  forces a one-time re-evaluation of every paper on the next warm run. The
  coverage-mode key uses superset semantics (`all_pages` > `exhaustive` >
  `default`): an existing sidecar with a higher-rank mode satisfies a
  lower-rank request, so a fleet run never re-adjudicates or overwrites a
  fresher `--all-pages` review artifact. The reverse (requesting
  `all_pages` against a `default` sidecar) always re-evaluates. Explicit
  PIDs always re-evaluate (no silent skip; `--incremental` opts in).
  `--review-all` restricts to the risk-candidate filter below. `--would-skip`
  is a dry run: prints each pid's would-be decision (`run`, `skip
  (fingerprint match)`, `skip (superset: MODE)`, `skip (tombstone)`) with no
  LLM call, no health probe, and no sidecar/report write, sharing the exact
  skip-decision logic (`_fingerprint_skip_decision`) the live run uses.
- **Error-skip + `--retry-errors`.** Error tombstones now carry fingerprints
  too. On an incremental/full run, a paper whose prior sidecar ended in
  `status="error"` is skipped like a successful paper when its fingerprint
  still matches; pass `--retry-errors` to force re-evaluation regardless.
  This drops warm-run time from ~65s to ~10-15s on a fleet with a handful
  of persistent errors. This-run errors (papers that fail during the current
  gather) are retried automatically at low concurrency before the footer;
  that wave does not re-open prior-run tombstones.
- **Skip visibility and warm markers.** Live fingerprint skips log at INFO
  (visible even in batch mode, not just debug), and the batch footer reports
  a breakdown, not just a bare count: `N skipped (incremental: X
  fingerprint, Y superset, Z tombstone)`. Every tapetum sidecar carries
  `evaluated_at` (UTC ISO 8601, schema_version 9), set only on an actual
  evaluation, never on a skip; the merged report uses it to mark a row
  `replayed` when the LLM result is a warm-skip carryover rather than fresh
  this run (`_is_replayed`, `build_merged_json`). A fingerprint skip still
  recomputes and persists the sidecar's fusion block against the CURRENT
  deterministic sidecar (`_refresh_fusion_on_skip`, pure recompute, zero LLM
  calls), so a skip never leaves a stale fusion paired with a rescored det
  verdict.
- **Menu surface for the freshness choice.** The interactive menu asks the
  warm/cold decision as one named prompt (`warm` | `cold` | `preview` in
  `_TAPETUM_MODES`, mapping to no flag / `--force` / `--would-skip`), not as
  a `Force re-evaluation of unchanged papers?` y/n. That earlier shape grew
  one y/n per flag until options (2) and (3) asked seven and nine questions,
  and it never used the words the docs use, so the warm/cold switch was
  findable only by someone who already knew it was `--force`. Diagnostics
  (`--retry-errors`, `--debug`, `--trace`) sit behind a single
  `Advanced options?` gate; `--inspect` rides along on warm and cold but not
  on preview, which returns before adjudicating. The `--review-all` arm asks
  no mode because `--force` is ignored there. Option (1) states that the
  deterministic lane has no cache instead of offering a switch it lacks. Any
  new lane flag belongs in a named mode or behind the advanced gate, not as
  a fresh top-level prompt.
- **Trace.** `--trace` writes `<pid>.trace.tapetum_llm.md` for both lanes
  with per-phase durations (`trace_render.py`). HTML/text goes through
  `dispatch` + `render_text_trace` (Select, Triage, Adjudicate, Decide).
  PDF is written from the CLI `finally` via `render_pdf_trace` (Extract
  through Code boundary). Previously a silent no-op.
- **Metadata short-circuit.** When the mandatory metadata/outline check
  itself fails or reviews, the PDF lane skips page escalations and unit
  checks: neither can raise a verdict the metadata check already capped.
  Verified zero verdict drift on a 378-paper fleet, eliminating ~44.6% of
  LLM calls. Audit modes (`--all-pages`, `--exhaustive-units`, `--inspect`)
  are exempt (they need full coverage regardless of the capped verdict);
  `unit_coverage.mode` is set to `"metadata_short_circuit"` on the sidecar.
- **Constant guard tag.** Both lanes use `constants.GUARD_TAG`, identical
  across papers and runs (v11 used `HMAC(run_secret, pid)`, per paper and
  per run; the HTML lane never set it and got a random tag per context).
  The framework floor puts the guard instruction at byte 0 of the system
  prompt, so any per-paper tag defeats cross-paper vLLM prefix-cache reuse
  of the 28-33k-char shared system prompt, and any per-run tag changes the
  prompt bytes between runs, which makes verdict-stability measurements
  meaningless. Security is unchanged: `escape_guard_delimiters` (not tag
  secrecy) is the load-bearing prompt-injection control.
- **LJF ordering.** Full and fleet runs sort papers by descending predicted
  work (`_predicted_work_seconds`: sidecar duration, else PDF page count,
  else source KiB) before dispatch, trimming tail latency
  under concurrency instead of leaving the largest papers to surface last.
- **Per-paper timing.** Sidecars record `duration_seconds` (per-paper wall
  time) alongside the fingerprint, for warm/cold run measurement.
- **Candidate filter** (`select_candidates`, pure Python, no LLM; only under
  `--review-all`): three populations. PRIMARY, pass-tier papers carrying
  gate-ignored risk signals (lossy tables, table parse errors, mojibake, or a
  `unigram_coverage - coverage` gap). SECONDARY, non-benign review papers
  (region-only review with high unigram is skipped). RESCUE,
  `heading_monotone`-only fails (advisory "likely shippable"). Known limit:
  the filter never reaches clean-pass papers with token-preserving corruption
  (the documented "selection gap"), which is why the full run is the default.
- **Two lanes by source kind.** PDF papers go through the PDF-text-layer judge
  (`pdf_judge.py`): PyMuPDF extracts the raw text layer, the judge model
  compares it against the converted markdown and returns a structured
  `PdfJudgment`. Missing-content quotes are first grounded against the PDF text,
  then checked against the candidate Markdown by a deterministic post-processor
  inside the LLM lane. HTML papers (and `--text-only`) go through the markdown
  text cascade below. Both lanes are independent of whisker signals (no
  deterministic verdicts/flags/metrics in any prompt; confirmation-bias
  defense). Lane independence means never reading the deterministic whisker
  sidecar or its verdict in a prompt; deterministic signals computed
  lane-locally from the source and the converted markdown (the PDF lane's
  own text_nid/content_recall floors, and the per-page screen below) are not
  a confirmation-bias violation and remain allowed.
- **Conditional ideal verifier.** After the independent source-aware judge
  completes, the CLI checks tomd's canonical
  `packages/tomd/tests/fixtures/golden/ideals/*.md` inventory. If and only if a
  matching ideal exists, a separate structured verifier compares candidate and
  ideal and attaches `ideal_verification` to the tapetum sidecar. Both candidate
  and ideal quotes must ground exactly. `review` can only cap a combined
  advisory pass at review; `agree` never promotes, rescues, or clears a
  deterministic result. The source-aware judge does not receive the ideal and
  remains independent. Fingerprints include ideal presence/content plus the
  verifier prompt, schema, service, and model identities, so add/change/remove
  invalidates incremental reuse exactly once.
- **PDF evidence has two-sided provenance.** Source grounding proves only that
  the model copied a quote from the PDF. `classify_candidate_evidence` then
  classifies the same quote as `present_in_candidate` (the Missing claim is
  refuted), `candidate_not_found` (the text could not be located, which is NOT
  proof of absence), or `ambiguous` (fuzzy or surface-sensitive equivalence).
  Source misses remain `source_ungrounded`. The sidecar schema v6 persists all
  dispositions and counts; `missing_content` contains only
  `candidate_not_found`. Verification uses the unfiltered on-disk candidate;
  binary-payload filtering applies only to LLM prompts. Candidate `exact`
  matches must preserve semantic operators; `fuzzy` always abstains.
  Shallow link/emphasis, front-matter,
  table, math/Unicode, TOC, and page-furniture guards prevent sanctioned
  reformats from becoming trusted Missing evidence. This post-processor does
  not read the deterministic sidecar; evidence-driven folding may revise
  `suggested_verdict` from the model verdict.
  The deterministic verdict, LLM verdict, and post-hoc fused verdict remain
  three separate results.
- **Leaked TOC is a prompt-level defect rule.** The PDF-lane conversion
  contract sanctions a MISSING table of contents (tomd strips it), and both
  judge prompts plus the text-lane `structure` axis (`llm.md`) state
  the inverse: TOC content that REMAINS in the body is a structure defect,
  severity at least major, verdict capped at `review` or worse. Signatures:
  a standalone `Contents` label/heading, a heading duplicated with a trailing
  page number, or an unpaired heading carrying a section number, title,
  bracketed stable name, and trailing page number (e.g.
  `## 5 Lexical conventions [lex] 10` with no unsuffixed twin). Without this
  rule the judge is provably TOC-blind (baseline: p1122r3 false-clear at
  pass/0.98). A mechanical post-judge clamp (`toc_leak.detect_unpaired_toc_leak`)
  enforces the severity floor when the model under-grades. Mirrors the
  deterministic `no_toc_leak` gate; leaked TOC is reported in `reasoning`,
  never as a missing-content quote (those stay reserved for verbatim
  RAW-PDF-TEXT evidence).
- **Per-page screen** (PDF lane only). `screen_pages()` computes a
  deterministic, lane-local `content_recall` per page (floor 0.90, pages
  under 50 content tokens skipped as trivial) before any LLM call, catching
  localized content loss that the whole-document `PDF_JUDGE_RECALL_FLOOR`
  (a document-wide average) can mathematically hide. Only pages the screen
  flags escalate to a scoped LLM call (one page's text + the full markdown,
  capped at `MAX_PAGE_ESCALATIONS`; over the cap, no escalation calls are
  made and the verdict caps at `review` on screen evidence alone). The LLM
  can only confirm or sanction a flag; it never silently upgrades a flagged
  page back to a clean pass. Calibration and design rationale:
  `research/research/per-page-judging/SYNTHESIS.md`.
- **Two-tier cascade** (text lane). A fast model triages every candidate;
  escalation to the deep model fires on any of three signals: axis conflict
  (pass and fail axes simultaneously), ungrounded evidence (grounding dropped
  at least one quote), or ambiguous-band confidence. A confident, consistent,
  well-grounded triage incurs no deep-model cost. Each tier emits per-axis
  findings on seven fidelity axes (wording, code, stable_names, tables, xrefs,
  math, structure).
- **Severity-aware decide.** The overall verdict equals the worst axis, but an
  axis `fail` forces an overall `fail` only when its severity is `major`
  (unrecoverable); a non-major `fail` (cosmetic, e.g. a heading-level jump) folds
  to `review`. This is what rescues the false-fail population. Evidence quotes are
  grounded verbatim against the markdown (ungrounded quotes are dropped); an
  ungrounded non-pass or sub-floor confidence demotes to `review`. A confident
  `pass` whose evidence was emitted but entirely dropped by grounding (the
  model claimed evidence, none of it survived verbatim matching) ALSO demotes
  to `review` (`working.evidence_spans and not grounded`, not a bare
  `not grounded`, so a sanctioned empty-evidence pass is untouched). The lane
  never turns uncertainty into a pass/fail.
- **Oversize papers.** A paper above `MAX_PAPER_MD_CHARS` is split on H2
  boundaries, triaged serially (one in-flight request at a time, for
  determinism), then folded into one adjudication (worst axis, minimum
  confidence, union of evidence). A section too large to read in full marks the
  read partial and can never become a clean `pass`. This is the documented fix
  for the `413 Payload Too Large` the largest papers (> 1 MB markdown) hit.
- **Sanctioned tomd markers.** The system prompt tells the model not to flag
  tomd's honest-uncertainty markers (`tomd:uncertain`, glyph placeholders,
  `tomd:vector-extraction-uncertain`) as conversion defects.
- **Inspect report.** `whisker-tapetum-llm --inspect` writes a side-by-side
  whisker-vs-advisory report for human review (`whisker/llm/tapetum-inspect.md`).
- **Availability and cost model.** The Alliance self-hosted pod (`alliance-pod`
  in `SERVICES.toml`) runs 24/7. Billing is per hour of pod uptime, NOT per token,
  so the lane may run anytime and run size is never a cost question: there is no
  per-token budget and no hourly-cost rationing. Run the full corpus freely.
  Production targets open-weight self-hosted models (model-sovereignty);
  deterministic whisker paths process papers serially. Only this advisory LLM
  lane adds cross-paper concurrency: requests within one paper remain serial,
  while its CLI processes up to 16 papers concurrently by default (matched
  to the pod's `--max-num-seqs 16`; this-run errors retry at concurrency 16
  for up to 2 extra rounds). Token-level
  output on a hosted pod is not bit-stable across reruns
  (see `llm.md` re: verdict-flip rate); the advisory architecture
  tolerates this because the LLM never gates.
- **Authority doc.** `src/whisker/llm/llm.md` holds the services,
  the cascade steps, and the full system prompt. Isolation invariant: whisker
  core never imports `llm`; the lane imports core read-only (one-way).

### Golden-PR PDF reviews (all-pages)

Golden-PR PDF reviews must run `whisker-tapetum-llm` with `--all-pages`.
`--inspect` / `--exhaustive-units` alone do NOT guarantee page coverage on any
lane. The sidecar's `unit_selection` / `all_pages_requested` fields are the
audit trail.

## whisker-readback (opt-in, blind LLM comprehension check, never in CI)

A second, separate opt-in CLI in the `tapetum-llm` extra (`whisker-readback`),
distinct from `whisker-tapetum-llm`. Where Lane 3 (`facts.py`) is the
deterministic, source-verified comprehension gate, `whisker-readback` is the
periodic empirical validation that a real LLM reading the SAME markdown blind
actually recovers the SAME facts (the same read-back methodology used once for
P4182R0, now generalized and tool-supported). Never gates, never runs in CI
(LLM-touching, non-deterministic by nature of the task).

- For each `checked: verified` fact in a paper's `.facts.jsonl`, sends a
  comprehension question with the paper's markdown to the pod
  (`alliance-pod` in `SERVICES.toml` by default, overridable with `--service`)
  as a single zero-shot Q&A call. Protocol v2: `present`/`absent`/`math`/
  `code`/`xref`/`order` facts require an authored `question` field that must
  not embed answer lexemes. `table`/`image_ref` keep generated locus
  questions. A missing or leaky authored question is a schema ERROR, not a
  generated prompt that quotes the needle.
- Scoring is anti-sycophantic: `present`/`code`/`xref`/`image_ref` require a
  grounded quote of the fact's needle in the answer (fuzzy within the fact's
  `max_diffs`, on the fact's own surface). A bare "YES" never passes. A
  quote without a YES prefix may pass. `absent` passes on NOT FOUND / "does
  not appear" / NO but is flagged `weak`. Table-cell values match on
  alphanumeric word boundaries (expected "8" does not match an answer
  containing "18"). Transport failures (timeouts, resets) are a separate
  `ERROR` state, excluded from pass/fail counts, so comprehension statistics
  are never polluted by infrastructure noise. Offline tests:
  `tests/llm/test_readback.py`.
- Renders every question, the pod's answer, the expected value, and PASS/FAIL
  visibly in the terminal as it runs (`render_terminal`), and persists a
  `<pid>.readback.md` markdown artifact per paper (`--out DIR`) for a human to
  review alongside the source when blessing a corpus wave.
- `--corrupt` is the adversarial control: deterministically scrambles table row
  order, flips relational operators, and shifts formula exponents before
  asking, so a healthy setup shows the SAME questions now FAILING (proof the
  test is sensitive to the markdown content, not just answerable from prior
  knowledge or a lucky guess).
- D1 exemption (documented in the module docstring): calls the pod via raw
  `httpx`, not `pipeline.run_agent`, because this is a single ad hoc Q&A call
  with no pipeline steps, no structured output type, and no retry/adjudication
  cascade; wiring it through the `pipeline` package would be over-engineering
  for a diagnostic script whose only consumer is a human reading the terminal.
- `whisker.llm.readback` is the library (`readback_paper`,
  `render_terminal`, `render_markdown`); `readback_cli.py` is the console
  script (`whisker-readback`) and owns all stdout/file writes.
- Service resolution (`_resolve_service` in `readback_cli.py`) parses
  `SERVICES.toml` directly with stdlib `tomllib` rather than importing
  `pipeline.services.load_services()`: that loader returns `ModelBackend`
  instances whose `base_url`/`api_key`/`model` are private by design (meant
  for `pipeline`'s own call paths, not raw extraction). This keeps
  `whisker-readback` standalone and off `pipeline` entirely.
- `main()` reconfigures stdout to UTF-8 with `errors="replace"`: Windows
  consoles default to cp1252, which raises `UnicodeEncodeError` on pod
  answers containing non-ASCII math/prose (found live, see below).
- Verified live against the alliance-pod and the two-paper corpus
  (2026-07-08): P4182R0 8/8, P4185R0 9/9 (17/17 total) after closing three
  bugs this run surfaced: the service-resolution bug above, the Windows
  console encoding crash above, and two `_math_surface` folding gaps
  (`\[...\]` display math, doubled `\\command` backslashes; both documented
  in the Fixed section of `CHANGELOG.md`).
- Rerun under the stricter grounded scoring over all 5 papers (2026-07-09):
  **34/37 pass, 3 fail, 0 error**. The 3 fails are pod column-alignment
  misreads of clean tables (advisory findings about the MODEL; the
  deterministic gate passes all 37 facts on the same markdown). Pass rates
  are NOT comparable across scoring versions: the earlier 100% numbers were
  produced by the sycophancy-prone scorer (bare YES sufficed for half the
  fact types). Details in `FIXPATH-REPORT.md`.

## Golden ideals and golden-QA ownership

Whole-paper golden ideals are integrated, and whisker owns the entire golden-QA
pipeline (scoring, gap analysis, CLI verbs). tomd retains the canonical STORAGE
of human-corrected ideals in `packages/tomd/tests/fixtures/golden/ideals/*.md`
and their source files in `packages/tomd/tests/fixtures/golden/sources/`; whisker
reads those read-only. All golden-QA CODE (golden_compare, golden_gaps,
golden_qa, qa_cli) lives in whisker, migrated from tomd in 2026-08-06.

The deterministic `(1)` run (`score_paper`) auto-discovers ideals per pid via
`golden_ideals.py`, computes the Lane-2 ideal panel (nid/teds/mhs/recall), AND
runs `golden_compare` to produce the per-axis structural breakdown (`gc_*`
fields on the sidecar: frontmatter, heading with text/level/nesting sub-signals,
list, code, table, text, composite, worst_axis). Both are advisory (review
flags, never hard fails). The on-demand `whisker qa-*` verbs give developers
the full QA workflow (add, generate, score, bless, rebless, issue, fact, anchor).
No ideal means no golden-compare fields and no verifier call; no duplicate
whisker fixture. Source remains factual authority.

More granular golden forms remain possible future additions that may eventually
replace parts of the facts corpus:

- A **golden grid** (whole table committed, compared grid-vs-grid) catches
  column swaps and row reordering that point-wise neighbor facts cannot see;
  papers shipping a golden grid can retire their per-cell `table` facts.
- **Construct-isolated golden pairs** (`<case>.in.html`/`<case>.out.md`, one
  construct per case, html-to-markdown-go `goldenfiles.go` pattern) localize
  WHICH construct broke, complementing whole-paper snapshots that catch
  drift but not cause.

The four integration points are marked in the code with `golden-hook:`
comments (`rg -n "golden-hook:"`): `_check_table` in `facts.py`, the grid
model in `tables.py`, `_corpus_pairs` in `test_comprehension_corpus.py`, and
the `golden` verb in `det/cli.py`. Each comment states what the golden
layer replaces there and why it is the right seam. Build against those
anchors; do not invent a new verb or a second grid model.

## Contract rule triage (a17 inventory)

The golden-contract audit (research/research/llm-golden-verification-gap/archaeology/a17-golden-contract.md)
identified 34 atomic contract rules, of which 13 had no deterministic or LLM enforcement.
P0 fixes #6 (secno stripping, now in `llm/html_outline.py` + `llm/source_router.py`) and #23
(table cell comparison, now in `llm/table_compare.py`). Status of the remaining 8 docs-only
rules:

| # | Rule | Triage | Rationale |
|---|------|--------|-----------|
| 14 | Bikeshed chrome (`no-toc`/`no-ref`) exclusion | (a) P1 backlog: deterministic | Strip in `llm/html_outline.py` same as secno; low priority |
| 16 | Two-space indent per list level | (c) human-only | Style preference; no semantic signal |
| 20 | One source listing = one fence | (b) prompt-encodable | Add to `UNIT_CHECK_SYSTEM_PROMPT` |
| 27 | Max one blank line between blocks | (c) human-only | Formatting convention; tomd emit handles |
| 29 | Preserve source typos in ideal | (c) human-only | Requires human judgment on intent |
| 30 | Structure-only edits (no wording paraphrase) | (c) human-only | Process rule for human reviewers |
| 33 | `-` bullets not `*` in ideals | (a) P1 backlog: deterministic | Regex check on candidate markdown |
| 34 | No pandoc ghost artifacts | (a) P1 backlog: deterministic | Pattern match for stray `:::` or `<del>` |

Rules #13 (self-link glyph) and #17 (list nesting depth) are borderline: #13 is
already handled by tomd's `render.py` but not in the verification path; #17 is
implicit in `det/golden_compare.py` depth scoring. Both are (b) prompt-encodable if
needed.

## Known gaps / where to improve next

Honest list for the next agent, ranked. Verify each against the code before
acting; this section describes the state as of 2026-07-22.

### Deterministic gates

1. **`no_toc_leak` is under- and over-inclusive.** Under-inclusive: dot-leader
   TOCs, roman-numeral page numbers, `Inhaltsverzeichnis` (non-English),
   and table-formatted TOCs pass undetected. Over-inclusive: a legitimate
   `## Table of Contents` heading or a pair like `## C++ 26` / `## C++`
   can hard-fail. Design iteration needed; blind regex patches will not
   converge.
2. **`heading_monotone` = 64 % of ref-free hard-fails.** Whether to exempt
   more patterns (e.g. single-level jumps) or keep the current operating
   point is a product decision. The RESCUE path (LLM advisory override for
   heading-only fails) is the current escape valve.
3. **Pinning baseline has no CI guard against silent gate additions.** Fixed
   in this batch (A2): `WHISKER_PIN_UPDATE=1` is blocked when `CI=true`, and
   unannotated `false` gates in the baseline now fail a meta-test.
3a. **`paragraph_align` covers PDFs only, in one direction.** HTML sources
   report `unsupported` even though `<p>` boundaries are explicit there and
   would be more reliable than any PDF heuristic; however tomd deliberately
   merges/splits `<p>` at ~10 documented points in `render.py`, so a naive
   `<p>` count comparison would false-fire on every generator. Measure before
   building. The candidate-splits-where-source-continues direction stays
   unemitted until captions, note blocks and page-opening lines are excluded
   (measured ~54% precision without those exclusions). The two convention
   detectors were fitted on five PDF goldens plus one review pair, which is a
   thin calibration set: a paper using neither convention abstains silently,
   and an abstain is indistinguishable from a clean result in the sidecar
   without reading `paragraph_status`. Note also that the a17 contract
   inventory's 34 rules contain NO paragraph-boundary rule, so this defect
   class was outside the audited contract entirely.
3b. **`code_fence_align` covers PDFs only.** HTML sources report `unsupported`
   because there is no font geometry to compare. Direction 1 (prose in fence)
   and Direction 2 (code outside fence) both rely on tomd's `classify_monospace`
   for the font classification, which covers the WG21-relevant families (cmtt,
   lmtt, Courier, Consolas, Menlo). A PDF with no monospaced font at all
   abstains.

### Advisory LLM lane

4. **VLM lane is quarantined.** 788 LOC across 5 files now live in
   `llm/vlm/`. No production entry point imports them; a reachability
   guard (`tests/llm/test_vlm_lane.py`) enforces this. Activation path: deploy a
   self-hosted Vision Pod and wire `vlm_adjudicate_paper` into the CLI.
5. **Cascade escalation rate never re-measured.** The 0/198 figure is
   pre-TOC-fix. The three new triggers (axis conflict, ungrounded evidence,
   ambiguous confidence) have not been measured on the full corpus.
6. **Dev-replay is separate from the locked holdout.** The 9 golden PRs
   (#282-#286, #290, #293-#295) are the development replay set with expected
   verdicts (`corpus/dev-replay/labels.json`). The active holdout manifest lists
   48 source-page-verified anchors across 3 non-replay papers and 7 strata
   (metadata, headings, prose, punctuation, code, tables, math). Candidate
   dispositions were checked against fresh local tomd conversions. `p0533r9`
   is retained only as quarantined audit history and is excluded from every
   holdout metric because it is PR #293. Never tune thresholds on the holdout.
7. **Source-aware routing (v6) is wired end-to-end and fail-closed.** Both
   `judge_pdf_extraction()` (PDF) and `adjudicate_paper()` (HTML) preserve the
   existing whole-document monolith call as the first LLM judgment. A mandatory
   metadata/outline call follows even when routing finds no risky unit. The
   router then computes recall, captions, headings, and document-wide token
   deltas (for example `constexpr`) directly from source and candidate, never
   from the deterministic sidecar. At most `MAX_UNIT_CHECKS` risky units receive
   scoped calls. Routed units whose source packet cannot be extracted are
   classified *unroutable* BEFORE quota selection (v10): they consume no cap
   slot, never enter `unchecked_unit_ids`, and never cap the verdict; they are
   tracked in `unit_coverage.unroutable_unit_ids`. Everything else stays
   fail-closed: failed calls, cap overflow, ambiguous evidence, or
   source-ungrounded evidence make coverage incomplete and cap the LLM lane at
   `review`; they can never silently produce `pass`. Exception to the
   unroutable rule: a REQUIRED unit (`--all-pages`) without a packet stays in
   `unchecked` and still caps at `review` (a physical page without extractable
   text must not silently vanish). Since v26, a non-aligned table unit without
   a text-layer pairing uses the same class-specific typed question as the
   source-first fallback instead of skipping merely because the pairing is
   absent. A typed confirmation can confirm the defect; reject-and-keep classes
   such as `flattened` abstain when the typed answer does not confirm. Aligned
   units still skip rather than self-judge, and a class with no typed question
   still skips.    Since v27, `header_is_data` confirms only the exact answer `body row`,
   and only when the PDF shows a different header above the markdown
   header. A section reference that opens the table is the top row.
   `data values` abstains. The typed fallback sends the paired text-layer
   page along.
8. **Defect groups express scale, not exhaustive evidence.** A defect group
   reports the LLM's `affected_count` plus representative examples. Countable
   keyword groups replace that estimate with document-wide `source_count`,
   `candidate_count`, `verified_delta`, and `verified_count`; non-countable
   groups explicitly keep `verified_count=null` and `count_status=unverified`.
   Candidate-present claims are refuted before aggregation. This lets P0533R9's
   231-vs-80 `constexpr` delta establish 151 omissions without pretending five
   examples are exhaustive. Metadata, unit coverage, evidence dispositions,
   and all source-aware prompts/schemas/services are persisted or fingerprinted.

### Comprehension corpus (Lane 3)

9. **Anchorless table facts are still ANY-semantics.** Fail-closed only
   applies under `table_heading`. An anchorless fact remains exploitable by
   a decoy table (see the `golden-hook:` in `_check_table`; the golden grid
   is the structural fix). Interim mitigation: author corpus facts WITH
   `table_heading` whenever the header row is stable.
10. **Grid model loses rowspan/colspan.** `tables.py` flattens spanning cells
   into their first slot; a span-aware grid (docling `verify_table_v2`) is
   the prerequisite for golden grids.
11. **Readback table questions cannot express "exactly this cell".** The
   P4185R0 `table-text-output-point-no` fail was partly caused by two
   near-identical cells ("Text output" / "Text output for points") in
   different tables; the question phrasing has no exact-match qualifier.
12. **`auto_baseline_checks` is not wired into `whisker facts`/`guard`
    output.** Callable standalone only.
13. **Corpus breadth.** Only a small subset of converted papers has verified
    facts. `image_ref` intentionally proves Markdown reference presence only;
    raster extraction, pixel inspection, VLM coverage, and image fidelity are
    outside the audit scope and are not missing scoring requirements.

### Benchmark accuracy (schema 7)

14. **`block_agreement` and `heading_level_parity` are advisory only.** Neither
    is gated or folded into `overall`. `block_agreement` separates tomd from
    Marker by ~4.5x but has no calibrated floor yet. `heading_level_parity`
    catches the MHS level-blindness but its threshold needs calibration on a
    larger corpus before gating.
15. **`structural_parity` hard gate is binary.** A zero-vs-many check per marker
    class is deliberately coarse: a converter emitting 1 fence vs 112 still
    passes parity. A ratio-based gate or a minimum-count threshold could
    catch partial structural loss, but needs a larger calibration set.
16. **Canonicalization is convention-specific.** `canonicalize_conventions`
    removes `:::wording`, `<ins>`/`<del>`, and heading section numbers. If tomd
    gains new convention-layer markup, the canonicalization must be updated or
    the block-agreement comparison will charge for it.
17. **Probe-strength gate has two mutilators.** `structure_stripped` and
    `keep_10pct` are the admission gate. `order_reversed` is computed but not
    gated. Additional mutilators (e.g. table-cell scrambling, identifier
    substitution) could tighten the gate further.

### Scoring / calibration

18. **Lane 2 edges are provisional.** `UNIGRAM_COVERAGE_*` and
    `REF_NID_ADVISORY_EDGE` are adopted from external repos, not fitted on
    our labeled corpus (see "Calibration status").

## Tests

The suite mirrors the source lanes: `tests/det/` covers the deterministic
engines and verbs, `tests/llm/` the advisory lane (offline, the pod is
mocked), and `tests/` root the shared modules plus the cross-lane contract
guards (`test_import_contracts.py`, `test_tool_privilege.py`,
`test_cli_structure.py`, `test_claude_invariants.py`). whisker is in the root
`testpaths`, so repo-wide `uv run pytest` collects it; the package suite
also runs standalone:

```bash
uv run --package whisker pytest packages/whisker/tests
```

The Lane 3 comprehension corpus gate is hermetic (no `WG21_DATA_DIR`, no backend):

```bash
uv run --package whisker pytest packages/whisker/tests/test_comprehension_corpus.py
```
