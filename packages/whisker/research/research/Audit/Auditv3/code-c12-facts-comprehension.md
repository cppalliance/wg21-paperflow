# C12 Facts and Comprehension

**Role**: Audit Lane 3's deterministic comprehension engine (`facts.py`, `tables.py`), and determine whether this run's RED suite implicates it.
**Audited state**: whisker 0.5.0, working tree, manifest b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771
**Gates**: D4 (Per-axis null-eligibility), D5 (Quality-stability)

## 1. Scope

Confirm the 8 fact-type evaluators in `facts.py` are unchanged, examine the
`tables.py` shared grid parser's test-coverage gap flagged in ledger E3, and
directly answer whether either RED failure in ledger E1 touches this lane.

## 2. Commands and Exits

`uv run --package whisker pytest packages/whisker/tests -q --tb=line` (E1):
`3 failed, 1784 passed`. Ledger E3 (test coverage by module) separately
records: "Modules with zero test functions referencing them at all:
`tables.py`, `vlm_pipeline.py`, `judge_task.py`. `tables.py` is notable: it
is the shared grid parser that both `facts.py` (Lane 3 cell-neighbor checks)
and `bench.py` (TEDS) depend on, and it is in the production import chain."

## 3. Current Evidence

### 3.1 `facts.py` mechanism, reconfirmed unchanged

All 8 fact types (`present`, `absent`, `order`, `table`, `math`, `code`,
`xref`, `image_ref`) still have a dedicated branch in `_evaluate`
(`facts.py:436-488`) with a `raise ValueError` catch-all
(`facts.py:488`). The provenance gate is unchanged: `checked == "verified"`
promotes a fact to enforced status (`facts.py:85`,
`CHECKED_VERIFIED = "verified"`); `FactReport.passed`
(`facts.py:145-148`) only checks `self._enforced()`. The two-stage fuzzy
match (`facts.py:299-321`: exact substring first, then rapidfuzz-located
window, then exact free-start/free-end DP `_substring_edit_distance`,
`facts.py:276-296`) is unchanged. The anchorless table ANY-semantics gap
Auditv2 already documented (F4 in that report) is reconfirmed present:
`_check_table` (`facts.py:374-423`) without `table_heading` tries ALL
candidate positions and returns True on the first satisfying occurrence
(`facts.py:416-423`), unchanged from Auditv2's finding.

### 3.2 `tables.py`: the zero-test-function gap, confirmed and explained

Ledger E3's flag is confirmed by direct inspection: `tables.py` exports
`parse_pipe_tables`, `parse_html_tables`, and `split_pipe_cells`
(`tables.py:29-33`). A search of the test suite for direct references to
these three names, or to `whisker.tables`/`from whisker import tables`,
turns up no dedicated test file (Auditv2's own E3-equivalent already noted
"Modules with no dedicated test file" includes `tables.py`; this run's
ledger sharpens that to "zero test functions referencing them at all").

The mechanical reason this gap is more consequential than it looks: `_all_tables`
in `facts.py:342-346` calls `parse_pipe_tables` and `parse_html_tables`
directly, and every `table`-type fact's neighbor check (`_check_table`,
`facts.py:374-423`) runs against the grids those two functions return.
Auditv2's own C08/C12 findings on the corpus canaries (a scrambled table
cell being caught) exercise `tables.py` transitively through `facts.py`'s
own tests, but no test asserts anything about `parse_pipe_tables` or
`parse_html_tables` in isolation: fence-awareness (pipes inside code
blocks), the HTML parser's handling of `<br>`-joined cell text
(`tables.py:108-109`), or rowspan/colspan flattening (documented as a known
loss in the `golden-hook:` comment, `tables.py:17-21`) have no direct
positive or negative test. A defect introduced directly in `tables.py`
(e.g. a fence-detection regression that let a code-block pipe masquerade as
a table row) would only be caught if it happened to also break one of the
corpus canaries' specific cell lookups; it is not guaranteed to.

### 3.3 Direct determination: neither RED failure is in Lane 3

Restated from C11's identical analysis, scoped here to Lane 3 specifically:

- **`test_score_pinning.py::test_score_pinned[p3556r0]` and `[p2040r0]`**:
  imports only `whisker.gates.run_gates` and tomd's `compute_metrics`
  (`test_score_pinning.py:32,34,90-91`); never imports `whisker.facts` or
  `whisker.tables`. Not a Lane 3 test.
- **`test_dev_replay_schema.py::TestHoldoutAnchors::test_locked_candidate_dispositions`**:
  imports `whisker.tapetum_llm.grounding.classify_candidate_evidence`
  (`test_dev_replay_schema.py:20-26`), the advisory LLM lane's evidence
  classifier, not `whisker.facts`. Not a Lane 3 test.

**Plain statement: no RED failure this run touches `facts.py`, `tables.py`,
`test_facts.py`, or `test_comprehension_corpus.py`.** All 69 test functions
in `test_facts.py` and all 8 in `test_comprehension_corpus.py` (per
Auditv2's own count, unchanged source) are part of the 1784 passing tests.

### 3.4 The readback negative control, the empirical validation this lane relies on

`facts.py`'s own module docstring frames Lane 3 as a deterministic PROXY
for LLM comprehension, validated once out of band by `whisker-readback`. C08
of this audit establishes, against live evidence, that the current
`--corrupt` negative control for that validation is weak: `raw/w6-readback-
scan.md` shows only a 5.4 percentage-point fact-level pass-rate drop
(91.9% clean to 86.5% corrupt) with 2 of 5 papers passing every fact
identically in both modes, because `_corrupt_markdown` (`readback.py:371-
387`) only touches pipe-table cells, `>=`/`<=`, and `^n` exponents. This
does not change anything about `facts.py`'s own deterministic correctness
(the fact engine's logic is unchanged, 3.1), but it does mean the
empirical justification CLAUDE.md cites for trusting the deterministic
proxy at all ("That proxy is validated ONCE, empirically and out of band")
is resting on a weaker negative control than the doctrine implies, a
finding that belongs to C08 in full but is directly relevant to how much
confidence C12's own PASS should carry.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | All 8 fact-type evaluators are unchanged and reconfirmed by direct re-read of the current working-tree `facts.py` | Informational | HIGH |
| F2 | The anchorless table ANY-semantics gap (Auditv2 F4) is reconfirmed present and unchanged | LOW | HIGH |
| F3 | `tables.py`, the shared grid parser both `facts.py` and `bench.py` depend on, has zero test functions referencing it directly; its only coverage is transitive, through whichever corpus facts happen to exercise a given table | MEDIUM | HIGH |
| F4 | Neither RED failure in ledger E1 touches `facts.py`, `tables.py`, or their dedicated test files; both are in adjacent machinery (score-path inputs, LLM-lane holdout harness) | Informational (clarifies scope) | HIGH |
| F5 | The empirical validation Lane 3 cites as its justification (`whisker-readback`) rests on a `--corrupt` negative control shown in C08 to be structurally weak, which does not invalidate `facts.py`'s own logic but weakens the doctrine's stated confidence basis | MEDIUM | HIGH |

## 5. False-Pass Hypothesis

**Could a `tables.py`-specific defect currently be gaming Lane 3 comprehension
checks undetected, given F3?** Not confirmed, but plausible and specifically
enabled by the coverage gap. Because no test asserts against
`parse_pipe_tables`/`parse_html_tables` in isolation, a defect that shifted
which cell a given `(row, col)` coordinate resolves to, without breaking any
of the specific cells the current 5-paper corpus happens to assert on, would
pass the entire Lane 3 suite silently. This is the same class of risk
Auditv2 flagged for anchorless table facts (F2 in that report) but one level
lower in the stack: it is a risk to the grid itself, not to the fact
semantics built on top of it.

**Could `facts.py`'s unit tests already cover this indirectly?** Partially.
`test_facts.py`'s HTML table canary (`test_canary_html_table_scramble_detected`,
per Auditv2's own table) exercises `parse_html_tables` transitively and
would catch a scramble in the specific fixture it uses. It would not catch a
parser defect that only manifests on inputs the fixture does not contain
(e.g. a table with `colspan`, which `tables.py`'s own `golden-hook:` comment
already documents as flattened, not span-aware).

## 6. Gate/Dimension Mapping (PROPOSED)

| Gate | Dimension | Proposed status |
|------|-----------|------------------|
| D5 Quality-stability | `facts.py` fact-type evaluation logic | PROPOSED PASS (unchanged, source-confirmed, RED suite does not implicate it) |
| D4 Per-axis null-eligibility | N/A for Lane 3 (all types always evaluated, per Auditv2's own finding, unchanged) | N/A |
| D5 Quality-stability | `tables.py` direct unit coverage | PROPOSED gap, not a pass or fail: zero dedicated tests on the production grid parser both `facts.py` and `bench.py` import |
| D5 Quality-stability | Empirical validation basis (`whisker-readback --corrupt`) | PROPOSED downgraded confidence per C08's live finding; does not change facts.py's own PASS |

## 7. Limitations

- This report does not write a new `tables.py`-specific test to prove or
  disprove F3's plausible-defect hypothesis; it establishes the coverage gap
  and its mechanical consequence, not an actual undetected defect.
- The corpus breadth question (which papers, which facts are authored) is
  explicitly out of scope, per Auditv2's own C12 Section 7, and remains so
  here.
- `auto_baseline_checks` (`facts.py:648-691`) remains unwired into
  `whisker facts`/`whisker guard` output, an Auditv2 finding (F5 in that
  report) reconfirmed present but not re-analyzed in depth here.

## 8. Conclusion

Lane 3's own logic is unchanged and this run's RED suite does not implicate
it: neither `test_score_pinning.py` nor `test_dev_replay_schema.py`'s
failing tests import or exercise `facts.py` or `tables.py`. What this run
adds beyond reconfirming Auditv2's findings is a sharper look at a gap
Auditv2 only listed as "no dedicated test file": `tables.py` has literally
zero direct test functions, despite being production-imported by both Lane
3 and Lane 2's TEDS scoring, and despite the CLAUDE.md-documented
rowspan/colspan flattening limitation living entirely inside it,
untested. Separately, C08's live evidence about the weak `--corrupt`
control means the empirical justification for trusting Lane 3's proxy
relationship to real LLM comprehension is less solid than CLAUDE.md's
doctrine section implies, though this is a confidence-basis finding, not a
defect in `facts.py` itself.

## 9. Delta vs Auditv2

Auditv2's C12 was purely offline (1406 tests passing, HEAD 51cb704) and
concluded "Gate verdict: PASS" without qualification, noting the anchorless
table gap and the unwired `auto_baseline_checks` as LOW-severity items.
This run reconfirms both of those findings unchanged and adds two things
Auditv2 did not have: first, the explicit RED-suite triage this claim's
planner specifically requested (3.3), establishing that Lane 3 is not
implicated by the current regression; second, live evidence from C08's
`whisker-readback --corrupt` run that sharpens Auditv2's own framing of the
readback validation ("Real-LLM readback validation is BLOCKED (E9)") into a
concrete weakness finding now that the block is lifted. Auditv2 never
flagged `tables.py`'s zero-function coverage as its own line item; this
run's ledger (E3) does, and this report traces the mechanical consequence
in full (3.2) rather than repeating the bare observation.
