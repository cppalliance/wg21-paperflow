# Opus Meta-Review C - Engineering Quality

**Scope:** re-verify the load-bearing engineering claims of personas 03, 05, 07,
09, 13, 14, 24 against the code at the baseline SHA
(`e66116a09bbe833a8080e9e60a95833ab339cf64`), NOT against the personas' word.
Every claim below was reproduced by reading the cited source and, where the
claim asserted runtime behavior, by executing a probe. A claim that did not
reproduce is downgraded or dropped explicitly.

**Overall engineering verdict:** usable-with-conditions. The deterministic lanes
are clean and reproducible; the load-bearing defects are (1) a real advisory
false-pass gap at `adjudicate.py:237` with zero regression coverage and (2)
structural duplication/normalization drift that no test guards. Several
portability claims are real as *inconsistencies* but do not actually skew any
committed verdict and are downgraded.

---

## Per-claim verdicts

### Claim 1 - Encoding split (corpus read) and BOM verdict-skew

**Split: CONFIRMED. Verdict-skew: REFUTED for the real corpus, DOWNGRADED to a hygiene/latent finding.**

The split is exactly as stated:

- CI comprehension gate reads the snapshot with plain UTF-8:
  `md = expected_path.read_text(encoding="utf-8")` (`test_comprehension_corpus.py:62`).
- The `whisker golden` CLI reads the *same* `corpus/<pid>.expected.md` with
  BOM-stripping `utf-8-sig` (`__main__.py:584`).
- `whisker facts` and the CI test read `*.facts.jsonl` with `utf-8-sig`
  (`__main__.py:506`, `test_comprehension_corpus.py:63`).

So a BOM survives into `check_facts` in CI but is stripped on the golden path.
That inconsistency is real. **But it cannot flip any of the 17 committed corpus
facts.** Runtime probe (executed, then deleted):

- U+FEFF is not whitespace: `isspace()==False`, `re \s` no-match, `str.strip()`
  does not remove it. So the naive "it gets normalized like a space" assumption
  is false, which is why the persona feared a skew.
- `normalized_text` keeps only alnum+CJK (`metrics.py` `clean_string`), so it
  strips U+FEFF entirely: `normalized_text("\ufeff...") == normalized_text("...")`.
  Therefore `present`/`absent`/`order`/`math` facts (`facts.py:342-365`) are
  **immune** to a BOM.
- `_norm_cell` (`facts.py:184-186`) does NOT strip U+FEFF, so a table cell whose
  text begins with the BOM would mis-match. **However**, a BOM is a single
  character at file offset 0, and every tomd corpus snapshot begins with YAML
  front matter (`---`), so the BOM lands on the front-matter line, never on a
  table cell. Probe on the realistic shape (front matter, then a mid-doc table):
  `present.passed` and `table.passed` are identical with and without the BOM.
  The skew only appears in a pathological doc where a pipe table is the literal
  first line with no front matter, which the tomd front-matter contract forbids.

**Downgrade:** the portability report's headline ("can silently flip
present/absent/table verdicts off the author's machine") does not reproduce.
The residual is a genuine latent inconsistency worth unifying on `utf-8-sig`, but
its impact is CRLF/BOM diff-churn and reviewer confusion, not a verdict flip. HIGH → LOW/MED.

### Claim 2 - Duplicated pipe-table parsers with divergent normalization

**CONFIRMED (HIGH, structural/maintainability).**

Two independent pipe-table detectors exist with byte-identical detection regexes
but divergent cell normalization:

- Lane 3 `_parse_pipe_tables` (`facts.py:261-295`) with `_split_cells` →
  `_norm_cell` = `_WS_RE.sub(" ", text).strip().lower()` (`facts.py:252-258`,
  `184-186`): lowercases and collapses internal whitespace.
- Lane 2 `_extract_md_tables` (`bench.py:98-132`) with `_split_cells` = plain
  `c.strip()` (`bench.py:89-95`): preserves case and internal whitespace, then
  emits HTML for TEDS.

The separator/fence regexes are literally duplicated:
`_TABLE_SEP_RE`/`_FENCE_RE` at `facts.py:73-74` are character-for-character equal
to `bench.py:55-56`. A GFM edge-case or fence-skip fix applied to one detector
silently leaves the other on the old behavior, and no test exercises both
parsers on the same input to catch the divergence. The persona's "will drift as
the corpus grows" is a valid structural risk. (Note: each lane's normalizer is
individually defensible for its own metric; the finding is the *duplication and
absence of a shared, tested helper*, not that one normalizer is wrong.)

### Claim 3 - `_hard_split` cuts mid-table / mid-fence

**CONFIRMED (CRITICAL for oversize papers, as scoped).**

`_hard_split` (`chunking.py:125-148`) iterates `text.splitlines(keepends=True)`
with **no `in_fence` and no table state**. Its only structural awareness is a
last-resort char-slice for a single line longer than the budget
(`chunking.py:134-139`). By contrast `_split_sections` (`chunking.py:95-122`)
*does* track `in_fence` — but only for H2 *detection*, and that state is not
carried into `_hard_split`. So an H2 section larger than `MAX_PAPER_MD_CHARS`
routed through `chunk_markdown` (`chunking.py:76-77`) can place a fence opener in
one chunk and its closer in the next, or split a pipe table across the chunk
seam. The `partial=True` flag is set (`chunking.py:78`) and only demotes an
*overall* `pass` to `review` (`adjudicate.py:245-246`); it does not prevent a
per-axis `tables=pass`/`code=pass` on a locally-plausible fragment, and
`aggregate_adjudications` folds worst-per-axis (`chunking.py:178-184`) with no
cross-chunk re-read. Persona 24's false-pass mechanism holds. Scope caveat: this
bites only the ~6 papers above the 500K-char budget, so it is CRITICAL within
that population, not for the median paper.

### Claim 4 - `whisker --all` drops errored papers from report.json / --json

**CONFIRMED (CRITICAL for batch-artifact completeness).**

The batch loop (`__main__.py:210-226`) appends to `results` only on success
(`:213-214`); the `except Exception` firewall (`:218-223`) increments a bare
`errored` counter and appends nothing. Consequently:

- `report.json` = `build_report(results)` (`__main__.py:250-251`) — errored PIDs
  absent.
- Sidecars are written only for `scored_pids` (`__main__.py:240-249`) — no error
  stub.
- `--json` stdout = `[r.to_dict() for r in results]` (`__main__.py:261`) — errored
  PIDs absent.
- Only the human `render_summary(..., errored=errored, ...)` footer
  (`__main__.py:263-273`) surfaces the count.

A downstream script consuming `report.json`/`--json` cannot distinguish "never
run" from "errored out," so a broken conversion vanishes from the
machine-readable artifact while its siblings may read `pass`. The
`if not results: return EXIT_ERROR` guard (`__main__.py:228-230`) only fires when
*every* paper errored, not a subset. Claim reproduced verbatim.

### Claim 5 - No regression test for the `adjudicate.py:237` grounding gap

**CONFIRMED (CRITICAL — both the code gap and the test hole).**

Code gap: `_custom_decide` demotes an ungrounded verdict only on the non-pass
branch — `if suggested_verdict != VERDICT_PASS and not grounded: ... = REVIEW`
(`adjudicate.py:237-238`). A confident, non-partial `pass` whose evidence spans
were *all* dropped by `ground_spans` (empty `grounded`) is NOT demoted. The two
other safety demotions do not cover it: `confidence < CONFIDENCE_DECISION_FLOOR`
(`:239-240`) requires low confidence, and `state.partial` (`:245-246`) requires a
hard-split. So a high-confidence ungrounded pass survives.

Test hole (grep of `test_tapetum_llm.py`): no test isolates this. The nearest
candidates all miss it:
- `test_decide_grounds_and_builds_result` (`:305-340`) uses a `review` verdict
  with mixed (one grounded) evidence — never a pass with all spans dropped.
- `test_decide_demotes_on_low_confidence` (`:342-371`) is a `pass` with empty
  evidence that demotes, but **only via the confidence floor** (confidence 0.40);
  it does not isolate `grounded==[]` on a *confident* pass, and would still
  demote if the grounding branch were deleted.
- `TestDecideSeverity` (`:567-607`) covers only self-reported `fail`
  (major→fail, minor→review) with grounded quotes.
- `test_tapetum_llm_eval.py` is pod-gated (`WHISKER_LLM_EVAL=1`) and asserts
  `suggested_verdict != "pass"` on broken markdown, not ungrounded confident
  passes.

The suite can stay green while a hallucination-backed `pass` ships. This is the
single most load-bearing verified finding in the engineering cluster: a real
code defect (#277 blocking condition 1, still open four days after the synthesis
flagged it CRITICAL) with zero test to prevent regression or force the fix.

### Claim 6 - rapidfuzz alignment drift; only Levenshtein parity-tested

**CONFIRMED (HIGH, latent supply-chain).**

The fuzzy fact path locates its window with
`fuzz.partial_ratio_alignment(needle, haystack)` and then re-measures with the
exact substring DP over the widened window (`facts.py:229-236`). The parity
oracle `test_edit_distance_parity.py` freezes only `Levenshtein.distance` and
`normalized_edit_distance` (`:26-53`) — grep of `packages/whisker/tests`
confirms `partial_ratio_alignment`, `_best_match`, `_substring_edit_distance`
have **zero** frozen vectors (only an incidental comment mention at
`test_tapetum_llm.py:91`). pyproject floor is `rapidfuzz>=3.14.5,<4`, and guard's
`tool_versions` stamps only `tomd`/`whisker` (`guard.py:67-73`), so a rapidfuzz
patch that shifts `dest_start`/`dest_end` can move which window the DP sees and
flip a `present`/`absent`/`order`/`math` fact at the `max_diffs` boundary with no
CI signal. The gap is latent (the lock currently pins 3.14.5) but real: the one
non-deterministic-across-versions surface in an otherwise pure lane has no golden
vector.

### Claim 7 (extra) - `.gitattributes` absence for the CRLF claim

**CONFIRMED (MED — hygiene, not verdict-skew).**

Repo-wide glob for `**/.gitattributes` returns 0 files. Runtime byte-count
confirms the persona's exact numbers: `P4182R0.expected.md` = 411 `\r\n`,
`P4185R0.expected.md` = 2180 `\r\n`. However, CRLF cannot skew comprehension:
Lane 1 collapses it before diff (`golden.py:88` `text.replace("\r\n","\n")`), and
Lane 3 uses `splitlines()` (`facts.py:268`), which is CRLF-agnostic. So the
finding is real as a diff-churn / bless-trust hazard (a cross-OS re-bless rewrites
thousands of line-ending bytes), not as a verdict defect. Correctly ranked MED by
persona 14.

---

## What survived, what moved

| Claim | Persona rank | Re-verified verdict |
|---|---|---|
| 1 encoding split exists | HIGH (14) | CONFIRMED as an inconsistency |
| 1 BOM skews verdicts | HIGH (14, 09) | **DOWNGRADED → LOW/MED** (normalization + front matter shield it) |
| 2 duplicated table parsers | HIGH (05) | CONFIRMED |
| 3 `_hard_split` mid-table/fence | CRITICAL (24) | CONFIRMED (scoped to ~6 oversize papers) |
| 4 `--all` drops errored | CRITICAL (09) | CONFIRMED |
| 5 grounding-gap has no test | CRITICAL (07) | CONFIRMED (code gap + test hole) |
| 6 rapidfuzz drift untested | HIGH (13) | CONFIRMED (latent) |
| 7 no `.gitattributes` | MED (14) | CONFIRMED (hygiene only) |

**Nothing was dropped outright.** One sub-claim (BOM verdict-skew) was downgraded
from HIGH to LOW/MED because the two mechanisms that would carry a skew are both
neutralized on the actual corpus: alnum+CJK normalization erases the BOM for
text/math/order, and the mandatory YAML front matter keeps the BOM off every
table cell. The encoding split itself, and every other engineering claim,
reproduced against code.

## Cluster summary

The deterministic core (facts/gates/score/metrics/golden) is genuinely pure and
reproducible; determinism auditor's [LOW] good-behavior findings hold. The
engineering debt clusters in two places the tests do not defend. First, the
**advisory tapetum lane**: a confident ungrounded `pass` is not demoted
(`adjudicate.py:237`) and no regression test exists (claim 5), and oversize
papers are cut structurally blind (`_hard_split`, claim 3) then folded worst-axis
with no cross-chunk re-read — a coherent false-pass corridor for exactly the
papers the lane is supposed to catch. Second, **structural duplication**: two
table parsers with divergent normalization (claim 2) and a fuzzy-match window
whose library dependency has no frozen vector (claim 6), both un-tested against
drift. The portability findings (claims 1, 7) are real inconsistencies but were
over-weighted: with normalization and front matter in the way, they churn diffs
and confuse reviewers rather than flipping verdicts.

---

## 5-line summary

1. SURVIVED: duplicated pipe-table parsers with divergent normalization (`facts.py:261-295` vs `bench.py:98-132`), `_hard_split` fence/table-blind chunking (`chunking.py:125-148`), `whisker --all` dropping errored papers from `report.json`/`--json` (`__main__.py:210-261`), rapidfuzz alignment untested by the Levenshtein-only parity oracle (`facts.py:229-236` vs `test_edit_distance_parity.py`), and no `.gitattributes` (411/2180 CRLF confirmed).
2. DOWNGRADED: the "BOM skews present/absent/table verdicts" sub-claim — the encoding split (`test_comprehension_corpus.py:62` utf-8 vs `__main__.py:584` utf-8-sig) is real, but a runtime probe shows `normalized_text` strips U+FEFF for text/math/order and YAML front matter keeps the BOM off every table cell, so no committed corpus fact flips; HIGH → LOW/MED.
3. NOTHING dropped outright; the encoding split and all other claims reproduced against code.
4. Verified nuance: `test_decide_demotes_on_low_confidence` looks like it covers the grounding gap but demotes only via the confidence floor, so the gap at `adjudicate.py:237` is truly un-regressed.
5. MOST LOAD-BEARING VERIFIED FINDING: the confident-ungrounded-`pass` gap at `adjudicate.py:237` — a real code defect (#277 blocking condition 1, still open) that lets a hallucination-backed advisory `pass` ship, with zero test to catch or prevent its regression.
