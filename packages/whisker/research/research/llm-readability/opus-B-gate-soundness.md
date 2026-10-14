# Opus Meta-Reviewer B - Gate & Logic Soundness

**Scope:** re-verify the load-bearing gate/logic claims of personas 04, 10, 11,
12, 18, 23 against the actual code and at runtime, not on the personas' word.
**Method:** read `facts.py`, `gates.py`, `score.py`, `metrics.py`, `guard.py`,
`__main__.py`, tomd `table.py`, and the two corpus members; then two throwaway
probes (`uv run --package whisker python`) exercising the exploit paths. Every
number below is reproduced, not quoted.
**Repo SHA context:** baseline `e66116a0` (`00-baseline.md:8`).

**Bottom line:** 6/6 load-bearing claims SURVIVE. One (the decoy shadow table)
is refined, not weakened: it is constructible but requires a detail the personas
under-specified. Nothing was dropped or downgraded to speculation.

---

## Claim 1 - Decoy shadow table beats first-match cell lookup

**Persona source:** 10 (CRITICAL), 11 (HIGH), 12 (LOW), 18 (CRITICAL/false-pass).

**Verdict: VERIFIED (constructible), with a correction to the recipe.**

Code path is exactly as claimed. `_check_table` builds the table list with
`_parse_pipe_tables`, which walks `md.splitlines()` top-to-bottom and appends
each grid in document order (`facts.py:268-295`). The locator then iterates that
list and binds the FIRST normalized cell equal to the target, breaking out of all
three loops on the first hit (`facts.py:314-323`). So a pipe table placed ABOVE
the real one in the source wins the binding. Ordering is deterministic document
order, so the exploit is not race-dependent.

Runtime reproduction (corrected decoy, P4182R0's two verified `table` facts):
I prepended two decoy pipe tables that reproduce each fact's cell + neighbors,
then placed the REAL tables below with the GPU `Coro` cell flipped `No -> Yes`.
Result: both `tableA-gpu-coro-no` and `tableB-console-alloc` return
`passed=True`, and all five structural gates pass (`run_gates` all True). A
downstream LLM answering "does GPU device code support coroutines?" reads the
scrambled `Yes`.

**Correction the personas missed (evidence-based):** my first decoy attempt
FAILED `tableB` with `heading of 'Arenas common' is 'coro', want 'Alloc'`. The
reason is `_neighbor_value(..., "heading")` returns `grid[0][c]` - the header of
the SAME COLUMN the cell sits in (`facts.py:300-301`), not a free-floating
label. So a working decoy must place the cell in a column whose row-0 header text
matches the fact's `heading` neighbor, in addition to reproducing up/down/left/
right. Persona 10's "row-unique replacement string" framing (`10:26`) is directionally
right but omits this column-alignment constraint; once satisfied, the exploit is
trivially constructible (proven above). This makes the claim slightly HARDER to
weaponize by accident than 10 implies, but no less real for a deliberate adversary.

**Impact:** the CI canary (`test_comprehension_corpus.py` scrambled-cell case,
`00-baseline.md:59-60`) scrambles the ONLY table in place; it does not add a
shadow table, so it does not exercise this path. Real defense requires table
identity (heading-anchored or all-occurrence matching), not first-match.

---

## Claim 2 - tomd emits HTML tables that `_parse_pipe_tables` cannot see; P4185R0 ships one with zero facts

**Persona source:** 18 (CRITICAL).

**Verdict: VERIFIED (both halves).**

Half A (tomd emits HTML for whole classes). `_STRATEGY_MAP` routes
`CODE_COMPARISON`, `SPEC_TABLE`, and `NB_BALLOT` to `TableStrategy.HTML_TABLE`
(`packages/tomd/src/tomd/lib/pdf/table.py:124-133`, read verbatim). Additionally,
ANY pipe-eligible table with a newline in any cell is force-upgraded to HTML
(`table.py:2410-2419`: "If any cell contains a newline, force HTML table
rendering regardless of kind"). Lane 3's parser is pipe-only: it detects a table
solely by a header line + `_TABLE_SEP_RE` separator (`facts.py:280-291`) and has
no `<table>` branch anywhere in the module. So Tony tables, spec/requirement
tables, NB-ballot grids, and any multi-line-cell table are invisible to
`_check_table`.

Half B (the corpus proves it). P4185R0's committed snapshot carries a
`<!-- tomd:mixed-table -->` HTML `<table>` at
`corpus/P4185R0.expected.md:760-786` with `<br/>` multi-line code cells (a
`From\To` conversion matrix). Runtime: `_parse_pipe_tables(p4185_md)` returns 12
pipe grids and the string `from\to` is NOT among any parsed cell; `<table>` is
present in the text. The two P4185R0 `table` facts target the PIPE grid at
`corpus/P4185R0.facts.jsonl:5-6` (cells `Anchored at true zero`, `Text output`),
never the HTML table. So a committed corpus member contains an HTML table with
zero comprehension coverage, exactly as claimed.

**Impact:** the highest-semantic-density WG21 tables (before/after code, API
spec, NB ballots) are structurally un-fact-checkable in Lane 3 today. Not a bug
in the checker; a coverage hole the fact schema cannot express.

---

## Claim 3 - Operator erasure: `x != y` and `x == y` both normalize to `xy`

**Persona source:** 10 (CRITICAL), 23 (CRITICAL).

**Verdict: VERIFIED.**

`present`/`absent`/`order` facts evaluate on `normalized_text` (`facts.py:343`,
`:347`, `:354`, `:358`). `normalized_text = clean_string(textblock2unicode(text))`
(`metrics.py:338-340`), and `clean_string` runs `_CLEAN_KEEP_RE =
re.compile(r"[^\w\u4e00-\u9fff]")` which deletes everything that is not a word
char or CJK (`metrics.py:115-126`). `!`, `=`, `<`, `>`, `+` are all stripped.

Runtime (reproduced):

```
'x != y'          -> 'xy'         | 'x == y'          -> 'xy'         | equal=True
'requires x == y' -> 'requiresxy' | 'requires x != y' -> 'requiresxy' | equal=True
'C++20'           -> 'C20'        | 'C20'             -> 'C20'        | equal=True
'a >= b'          -> 'ab'         | 'a <= b'          -> 'ab'         | equal=True
```

**Impact:** three of five fact types cannot distinguish an operator flip, a
`requires`-clause negation, or `C++20` from `C20`. For a standards-paper corpus
this is the core payload. Only `table` (exact cell) and `math` (`_math_surface`,
which keeps `^_=` via `facts.py:181`) retain any operator sensitivity, and even
`math` folds `!=`/`==` away because those characters survive neither surface as
distinct tokens after lowering/whitespace-collapse. This is a false-PASS vector,
not a false-fail.

---

## Claim 4 - Exact-match cell location vs `max_diffs`-tolerant neighbors (false-fail vector)

**Persona source:** 11 (HIGH/false-fail).

**Verdict: VERIFIED.**

The asymmetry is in the code: the cell is located by strict equality
`if value == target` where `target = _norm_cell(fact.cell)` (`facts.py:311`,
`:317`) with NO edit budget, while each neighbor is accepted when
`actual == want or _Lev.distance(actual, want) <= fact.max_diffs`
(`facts.py:333`). `_norm_cell` only lowercases and collapses whitespace
(`facts.py:184-185`); it does not strip markdown emphasis, footnote markers, or
punctuation.

Runtime (reproduced): wrapping the target cell as `**GPU device code (CUDA,
SYCL)**` yields `cell '...' not found in any table` (hard fail), while a neighbor
`helxo` vs expected `hello` at `max_diffs=2` passes. So cosmetic, semantically
faithful cell polish (bold, `[1]` footnote, trailing period) hard-fails a
verified `table` fact - and because facts are conjunctive in `whisker guard`
(`__main__.py:444-452`, `465-466`), it fails the whole paper even when nid/teds/
mhs are green.

**Impact:** genuine false-fail on readable markdown. Compounds with Claim 1: the
same rigidity that rejects a bolded real cell is why an adversary must reproduce
the decoy cell verbatim, but a verbatim decoy is cheap while faithful tomd polish
gets punished. The exact-match cell is simultaneously a false-fail source and the
thing that makes the shadow exploit require an exact string.

---

## Claim 5 - An all-draft facts file exits 0 in `whisker facts` and `whisker guard`

**Persona source:** 04 (CRITICAL), 12 (CRITICAL, factless variant).

**Verdict: VERIFIED (with the precise boundary).**

`FactReport.passed` iterates only `_enforced()` = checks where `verified` is True
(`facts.py:124-130`); `all([])` is True, so a report with zero verified facts is
`passed=True`, `failed=False`. Runtime: a single draft `present` fact whose text
is absent evaluates to a FAILED check, yet `report.passed=True`,
`enforced count=0`.

CLI wiring:
- `whisker facts` default: `failed = any(r.failed for r in reports)` ->
  `EXIT_OK` (`__main__.py:739-740`). `--strict` flips to
  `any(not c.passed for r in reports for c in r.checks)` and WOULD catch it
  (`__main__.py:736-737`), but strict is not the CI default.
- `whisker guard`: `facts_failed = any(r.failed for r in fact_reports)` -> False,
  so the facts leg does not fail the paper (`__main__.py:452`, `465-466`).

So both production CLIs exit 0 on an all-draft (or empty, or factless) file. The
"no vacuous green" guarantee (`00-baseline.md`, whisker `CLAUDE.md`) holds ONLY
in the hermetic pytest gate `test_comprehension_corpus.py`, which additionally
asserts `>=1` verified fact exists. Persona 04's contract framing is exactly
right.

**Impact:** the CI file gate has teeth; the shipping CLIs do not enforce that a
corpus member actually gates anything. A paper can carry an all-draft facts file
and pass `guard` forever.

---

## Claim 6 - Token-preserving corruption (cell swap) passes the content gate

**Persona source:** 12 (CRITICAL).

**Verdict: VERIFIED.**

The hard content gate is `unigram_coverage < UNIGRAM_COVERAGE_FAIL_EDGE`
(`score.py:156-160`); the order-sensitive shingle `coverage` is explicitly never
a verdict flag (`score.py:136-140`, whisker `CLAUDE.md` verdict model).
`unigram_coverage` is order-invariant multiset recall. Runtime confirmation via
the sibling `content_recall` (same `content_tokens` alphabet, `metrics.py:358-389`):
swapping two cell values `yes|no -> no|yes` gives `content_recall = 1.0` and an
IDENTICAL token multiset `['a','b','no','yes']` on both sides.

So a row/column swap, or an xref revision drift that keeps the same tokens, does
not move `unigram_coverage` at all. Combined with Claims 1 and 3, a corruption
that (a) preserves the token multiset, (b) touches only operators/punctuation, or
(c) scrambles a non-fact-checked table row can hold `unigram_coverage == 1.0`,
clear all structural gates, and (for the ~198 factless papers, `00-baseline.md:77`)
face no deterministic objection. tapetum_llm is opt-in and its PRIMARY selection
needs a risk signal these corruptions do not raise (persona 12 evidence against
`adjudicate.py`; not re-audited here, out of my scope, flagged as inherited).

**Impact:** the gate math is confirmed. The order-invariant content floor is
structurally blind to token-preserving semantic corruption - by design (reflow
robustness), but that design choice is exactly the false-negative surface.

---

## Cluster summary

The gate logic is internally consistent and does what its docstrings say; the
soundness problem is not bugs but **expressiveness and enforcement boundaries**,
and every load-bearing persona claim about them reproduces:

- **False-PASS cluster (1, 2, 3, 6):** all four survive. The through-line is that
  the deterministic surfaces are lossy in adversarially-exploitable ways -
  `normalized_text` erases operators (3), `unigram_coverage` erases order and
  cell placement (6), the pipe parser erases HTML tables (2), and first-match
  erases table identity (1). Each is a place where "the tokens are all present"
  or "a matching cell exists" is certified as "comprehensible," which it is not.

- **False-FAIL cluster (4):** survives. Exact-match cell location punishes
  faithful cosmetic polish and is conjunctive in `guard`. It is the mirror image
  of (1): the same strictness that rejects a bolded real cell is what the shadow
  decoy must satisfy verbatim.

- **Enforcement-boundary cluster (5):** survives. The anti-vacuous guarantee is
  real in pytest and absent in the shipping CLIs. The gate that has teeth is not
  the gate operators run.

**Refinements, not downgrades:** Claim 1's recipe needs the heading-column
alignment detail (`facts.py:300-301`) the personas omitted; the exploit is real
but requires that the decoy reproduce the same-column header, not merely linear
neighbors. Claim 5's precise boundary is "default CLI, not `--strict`, not the
pytest gate." Neither changes the verdict.

**Single most load-bearing verified finding:** the **decoy shadow table (Claim 1)**.
It is the only finding that is simultaneously (a) a live, reproduced exploit of
the strongest deterministic table check, (b) uncovered by the existing CI canary,
and (c) fixable with a bounded change (heading-anchored or all-occurrence cell
matching in `facts.py:313-323`). Operator erasure (3) and the token-preserving
gate (6) are broader, but they are acknowledged design lossiness; the shadow
table is a check that actively certifies a corrupted primary table as correct.

**Out of my scope (inherited, not re-verified):** tapetum `adjudicate.py`
selection/grounding logic (personas 12, 04); the ~198 factless-paper coverage
count (`00-baseline.md:77`, a corpus-size fact, not a gate-logic fact).
