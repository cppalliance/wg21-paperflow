# LLM-Readability Fix Path: Implementation Report

> **Path note (2026-09-07):** the module paths cited below predate the lane restructure; deterministic modules now live under `src/whisker/det/` and the advisory lane under `src/whisker/llm/` (was `tapetum_llm/`). Current map: `src/whisker/CLAUDE.md`.

Date: 2026-07-09. Scope: `packages/whisker/` only (package boundary respected;
no other package was touched). This report documents WHAT was implemented,
WHY it was designed this way, and WHERE the future golden-file layer plugs in.

Provenance: two research runs drove this work.

1. `research/llm-readability/` (Meta-E ranked fix path): produced the original
   A1-A4 / B1-B2 work items (grounding demotion, vacuous-green gate, fact
   schema extensions, primitives hardening, blind readback harness, corpus
   tooling).
2. `research/llm-readability-fixpath/` (self-target audit, 25-persona
   Composer-2.5 swarm + Opus verification): red-teamed the finished A/B work
   against 12 comparison repos and found the six weaknesses fixed in this
   hardening pass.

## 1. What was implemented (this hardening pass)

### Fix 1: Decoy-table fail-closed semantics (`facts.py`, CRITICAL)

`_check_table` with a `table_heading` anchor now requires EVERY occurrence of
the target cell in heading-matching tables to satisfy the neighbor checks.
Before, the first satisfying occurrence won, so a decoy table sharing the
heading and contradicting the genuine row was shadowed by the genuine one
(red-team exploit: append a scrambled copy of a poll table; the fact still
passed). Without a heading anchor the ANY-semantics is kept, because cell
values legitimately repeat across unrelated tables (measured on the corpus:
P4182R0 `tableA-gpu-coro-no` has 3 occurrences of "No" across 16 tables).

Why fail-closed only under an anchor: the anchor states "this fact is about
tables with THIS heading"; a conflicting occurrence under that scope is
evidence of corruption or ambiguity, and Lane 3's contract (CLAUDE.md,
Fidelity) is that uncertainty fails rather than passes. Canary:
`test_canary_decoy_table_all_occurrences` now asserts the decoy FAILS.

### Fix 2: Anti-sycophancy readback scoring (`tapetum_llm/readback.py`, HIGH)

YES/NO readback checks (`present`/`code`/`xref`/`image_ref`) previously
passed on `answer.startswith("yes")`. An agreeable model that answers YES to
everything scored 100%. Now `_grounded_quote` requires the fact's needle to
appear in the answer (fuzzy, within the fact's own `max_diffs` budget, on the
fact's own surface: raw for `code`/`xref`/`surface:"raw"`, normalized
otherwise; for `image_ref` the `![...](...)` reference itself). The questions
for `xref`/`image_ref` were extended to explicitly request the quote, so
grounding is a fair demand. `absent` facts pass on NO but are flagged
`weak` (a correct NO cites nothing; visible in terminal and markdown output),
never silently equated with grounded evidence.

### Fix 3: Word-boundary table-answer scoring (`readback.py`, HIGH)

Expected cell value "8" previously matched an answer containing "18"
(substring). `_cell_value_in_answer` now matches on alphanumeric boundaries
(`(?<![0-9a-z])8(?![0-9a-z])`), so "18" is rejected while "(8)" and "8,"
still match. Regression test: `test_cell_value_8_does_not_match_18`.

### Fix 4: Hermetic CI snapshots for wave-2 papers (HIGH)

`corpus/N5040.expected.md`, `corpus/P0876R23.expected.md`,
`corpus/P4234R0.expected.md` are now committed, so all 5 corpus papers (not
just the original 2) gate hermetically in CI via
`test_comprehension_corpus.py` (37 verified facts total, no backend, no
`data/`). A third canary (`test_canary_scrambled_code_fails`) scrambles the
P4234R0 asm-alias snippet and asserts the `code` fact fails, completing the
canary set (table cell, math relation, code snippet: one per exploit class).

### Fix 5: Fence-blind stratum classification (`corpus_tools.py`, MED)

`classify_paper` counted `$$...$$` on raw markdown, so `$`-prefixed
identifiers inside code fences (P4234R0's entire subject matter) were
misclassified as display math. `_strip_fenced_blocks` removes fenced content
before the display-math regex, in both `classify_paper` and
`draft_facts_scaffold` (so drafts no longer propose bogus math facts).

### Fix 6: ERROR status for readback transport failures (MED)

An `httpx` timeout previously rendered as FAIL, conflating "the pod never
answered" with "the pod misread the document". `ReadbackCheck.error` now
marks transport failures; they render as `[!] ERROR`, are excluded from
pass/fail counts, and the CLI summary reports them separately with a rerun
hint. Comprehension statistics are no longer polluted by infrastructure
noise.

## 2. Verification evidence

- Full whisker suite: **901 passed, 6 skipped, 5 xfailed** (
  `uv run pytest packages/whisker/tests -q`, 2026-07-09).
- Deterministic Lane 3 gate: `whisker facts --corpus packages/whisker/corpus`
  = **clean over 5 papers, 37 verified facts gated, 0 vacuous**.
- Live blind readback rerun (alliance-pod, DeepSeek-V4-Pro, all 5 papers,
  under the NEW stricter scoring): **34 pass, 3 fail, 0 error** out of 37.
  Artifacts: `data/whisker/readback/<pid>.readback.md`.

The 3 fails are honest advisory findings about the MODEL, not the markdown
(the deterministic gate passes all 37 facts against the same markdown):

- `P0876R23 table-poll-stlouis`: pod named the right neighbor correctly (8)
  but answered the wrong column heading ('F' instead of 'SF'), an off-by-one
  column-alignment misread of a clean pipe table.
- `P4185R0 table-anchored-true-zero`: pod answered the row label ("Physical
  origin") instead of the immediate left neighbor ("Point origin (explicit
  or implicit)"), again a column-alignment misread.
- `P4185R0 table-text-output-point-no`: the paper has both a "Text output"
  cell and a "Text output for points" cell in different tables; the pod
  answered from the wrong one. Partially a question-phrasing limitation
  (the question does not say "exactly matching cell"); noted as a known gap.

Under the OLD scoring these three would also have failed; no previously
green result was silently re-scored. But note the old 100%-pass claims for
waves 1-2 were made under sycophancy-prone scoring (bare YES sufficed for
half the fact types); the 34/37 under grounded scoring is the honest number
going forward, and readback pass rates are not comparable across scoring
versions.

## 3. Why this design

- **Fail-closed over fail-open** (Fix 1): Lane 3's value is that a green
  gate MEANS something. Any ambiguity that could mask corruption demotes to
  failure, mirroring the fidelity rule "never produce a partial result
  mistakable for a complete one".
- **Blindness + grounding as a contract** (Fixes 2, 3): the readback harness
  only proves comprehension if the question cannot leak the answer AND the
  answer cannot bluff the scorer. Question generation never embeds expected
  lexemes; scoring never accepts unquoted assent.
- **Deterministic gate and advisory readback stay separate**: `whisker facts`
  is LLM-free, hermetic, in CI; `whisker-readback` is opt-in, live,
  never in CI. The readback validates the METHODOLOGY (are the facts
  recoverable by a real LLM), not individual conversions.
- **Errors are not data** (Fix 6): a comprehension statistic that counts
  timeouts as misreads cannot be trusted; the ERROR lane keeps the numbers
  clean.
- **Corpus provenance**: wave-2 facts were drafted by `whisker corpus draft`
  and verified by the agent against the ORIGINAL staged sources (HTML/PDF),
  each needle located verbatim in the source before `checked: verified`, at
  the user's direction (no human-in-the-loop for this wave). The committed
  snapshots freeze the exact markdown those facts were verified against.

## 4. Golden files: the next validation layer

Golden files (committed ground-truth artifacts compared structurally, not
point-wise) are planned as an ADDITIONAL validation layer on top of the
facts corpus, and may eventually REPLACE parts of it:

- A **golden grid** (whole table committed as a snapshot, compared
  grid-vs-grid) catches column swaps and row reordering that point-wise
  neighbor facts structurally cannot see. Once a paper ships a golden grid,
  its per-cell `table` facts become redundant and can be retired.
- **Construct-isolated golden pairs** (`<case>.in.html` / `<case>.out.md`,
  one construct per case, following html-to-markdown-go's `goldenfiles.go`)
  localize WHICH construct broke without human triage, complementing the
  whole-paper `expected.md` snapshots that catch drift but not cause.

### golden-hook anchors (greppable: `rg -n "golden-hook:"`)

The four integration points are marked IN THE CODE with `golden-hook:`
comments (same convention as `shortcut:`), so whoever builds the golden
architecture greps the anchors and immediately knows where and why to plug
in, instead of re-deriving the research findings:

| File | Anchor purpose |
| --- | --- |
| `src/whisker/facts.py` (`_check_table`) | Golden-grid compare replaces the per-cell candidate scan; catches column swaps/row reorder that neighbor facts cannot see. |
| `src/whisker/tables.py` (module docstring) | The `list[list[str]]` grid loses rowspan/colspan; a span-aware grid (docling `verify_table_v2` pattern) is the golden-grid candidate model, introduced here so facts and bench inherit it. |
| `tests/test_comprehension_corpus.py` (`_corpus_pairs`) | Construct-isolated golden pairs plug in as a second substrate source next to whole-paper `expected.md` snapshots. |
| `src/whisker/__main__.py` (`_golden_main`) | The golden-file layer extends the existing `golden` verb (never a new one); golden grids can then partially retire table facts. |

These anchors are the mechanism that makes the later quality step cheap:
the plumbing decisions are already made and documented at the exact lines
where they apply.

## 5. Files changed in this pass

- `src/whisker/facts.py`: Fix 1 + golden-hook anchor.
- `src/whisker/tapetum_llm/readback.py`: Fixes 2, 3, 6.
- `src/whisker/tapetum_llm/readback_cli.py`: error count in summary.
- `src/whisker/corpus_tools.py`: Fix 5.
- `src/whisker/tables.py`, `src/whisker/__main__.py`: golden-hook anchors.
- `corpus/N5040.expected.md`, `corpus/P0876R23.expected.md`,
  `corpus/P4234R0.expected.md`: new committed snapshots (Fix 4).
- `tests/test_facts.py`, `tests/test_readback.py` (new),
  `tests/test_comprehension_corpus.py`: regression tests + canaries.
- `src/whisker/CLAUDE.md`, `CHANGELOG.md`: documentation.
