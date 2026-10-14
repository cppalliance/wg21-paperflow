# C19 Chunking and Context

**Role**: Audit unit selection, chunking, page coverage, and context budget in the advisory LLM lane.
**Audited state**: whisker 0.5.0, working tree, manifest b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771
**Gates**: G2 (Fail-not-partial), D3 (Fidelity / partial-read capping)

## 1. Scope

Four related questions, all about how much of a paper the advisory lane
actually reads before it is allowed to say `pass`: oversize-paper chunking
(`chunking.py`), unit selection quotas for the source-aware router
(`unit_judge.py`), page/unit coverage bookkeeping in the PDF lane
(`pdf_judge.py`), and the per-request context budget guard that refuses to
silently truncate (`pdf_judge.py`). This file is materially larger in scope
than Auditv2's C19, which covered chunking only; the source-aware routing
and page-coverage machinery did not exist in its current form at that audit.

## 2. Commands and Exits

```
E1: uv run --package whisker pytest packages/whisker/tests -q --tb=line -> 3 failed, 1784 passed, 8 skipped, 3 xfailed (exit 1)
```

No dedicated live chunking/coverage run exists in this audit's runtime
matrix (E13-E20); the evidence below is code-level for the chunking and
coverage machinery, cross-referenced against the live PDF-lane runs that
did execute (E13, E16-E20) to confirm the context-budget and metadata
short-circuit paths were exercised, even if not chunking specifically.

## 3. Current Evidence

### 3.1 Chunking: H2 boundary split, greedy pack, hard-split fallback

`chunk_markdown` (`chunking.py:129-164`) is unchanged from Auditv2 (still
333 lines total): a small-paper fast path (`len(md) <= max_chars` returns
`([md], False)`), fence-aware H2 splitting (`_split_sections`,
`chunking.py:167-194`), greedy packing under `max_chars`, and a hard-split
fallback on line boundaries (`_hard_split`, `chunking.py:197-220`) that sets
`partial = True`. The concatenation invariant (lossless: every input
character appears in exactly one chunk) holds by construction
(`splitlines(keepends=True)` throughout), and no dedicated
`assert "".join(chunks) == md` test exists, same F5 gap Auditv2 recorded.

`MAX_PAPER_MD_CHARS = 500_000` (`tapetum_llm/constants.py:61`) is the
per-request budget: "Papers above this char budget are split on H2
boundaries... a 2.5 MB paper yields ~5-6 serial chunks" (`constants.py:56-60`).
This constant governs the text-cascade lane (`adjudicate.py`), not the PDF
lane, which uses a different budget mechanism (3.4 below).

### 3.2 Worst-axis aggregation and partial-read capping (unchanged)

`aggregate_adjudications` (`chunking.py:226-292`) folds per-chunk
adjudications: most-severe finding per axis (`_finding_rank`,
`chunking.py:295-302`), minimum confidence across chunks, union of evidence
spans deduped on `(axis, quote, reason)`. `worst_axis_verdict`
(`chunking.py:106-123`) applies the severity fold: a `fail` only forces
overall `fail` when `severity == SEVERITY_MAJOR`; a non-major fail folds to
`review`. The calling code (per CLAUDE.md, not re-traced in `adjudicate.py`
this run) caps a `partial=True` read at `review`, so a section too large to
read in full cannot reach a clean `pass`. This mechanism is architecturally
identical to Auditv2's finding; no live oversize-paper test exists in either
audit's ledger to exercise it end to end.

### 3.3 Unit-selection quota: two caps, unclear which is live by default

Two distinct sizing mechanisms coexist for source-aware unit checks:

- `MAX_UNIT_CHECKS = 5` (`constants.py:228-232`), documented as the "fleet
  default" cap.
- `fleet_max_unit_checks` (`unit_judge.py:192-213`), a dynamic per-paper
  quota: `base=3` (`FLEET_UNIT_CHECK_BASE`, `constants.py:237`),
  `ceiling=7` (`FLEET_UNIT_CHECK_CEILING`, `constants.py:238`), bumped by 1
  for high/critical-severity signals, by 1 for `table_presence` signals, and
  by 1 when routable risky units exceed 8
  (`FLEET_UNIT_CHECK_SIGNAL_COUNT_THRESHOLD`, `constants.py:241`).
  Gated by `DYNAMIC_QUOTA_ENV_VAR = "TAPETUM_DYNAMIC_QUOTA"`
  (`unit_judge.py:82`), documented as "1 (default) enables it."

`_select_units_with_quotas` (`unit_judge.py:216-254`) then guarantees one
slot per distinct `signal_type` before filling remaining slots in sort
order, backed by `SIGNAL_CLASS_QUOTA = 1`
(`constants.py:243-253`, defined twice, identically, back to back:
apparent copy-paste leftover, harmless but sloppy). This audit did not
trace which cap (`MAX_UNIT_CHECKS` vs the dynamic `fleet_max_unit_checks`
range 3-7) is actually the effective ceiling on a default fleet run;
`MAX_UNIT_CHECKS = 5` sits inside the dynamic range (3-7) so the two do not
obviously contradict on the common case, but neither is dead code by
inspection, and this file does not resolve which one wins when they would
differ (e.g. a paper with `base=3` and no bumps: dynamic quota gives 3,
`MAX_UNIT_CHECKS` alone would allow 5).

### 3.4 PDF lane context budget: no silent truncation

`CONTEXT_SAFETY_MARGIN = 0.80` (`pdf_judge.py:111-114`) governs the
monolith PDF-judge call specifically (separate from `MAX_PAPER_MD_CHARS`,
which governs the text cascade): "Both texts plus prompt overhead must fit
within this fraction of the service's context window, otherwise the paper
fails loudly." Enforced at `pdf_judge.py:639-650`:

```639:650:packages/whisker/src/whisker/tapetum_llm/pdf_judge.py
    total_chars = len(pdf_text) + len(tomd_md)
    est_tokens = (
        total_chars / agent.chars_per_token * agent.token_multiplier
        if agent.chars_per_token else 0
    )
    budget = agent.max_context_window * CONTEXT_SAFETY_MARGIN
    if est_tokens and est_tokens > budget:
        raise PdfLaneError(
            f"{pid}: estimated {est_tokens:.0f} tokens exceeds "
            f"{budget:.0f} context budget; refusing to truncate"
        )
```

This is a hard `PdfLaneError` (fidelity policy: any PDF-lane failure ->
`PdfLaneError`, no partial results, `pdf_judge.py:610`), not a silent
truncate-and-continue. No PDF-lane paper in this run's live matrix
(E13-E20) tripped this guard; the largest base document used was 25157
chars (E17), well under any plausible context-window budget.

### 3.5 Page/unit coverage: fail-closed by construction, short-circuited by design

`_source_aware_requires_review` (`fusion.py:182-227`, see C21) treats
incomplete `unit_coverage` as a review-forcing signal: `coverage_complete
is not True`, or any `unchecked_unit_ids`/`failed_unit_ids`, forces review
regardless of the LLM's suggested verdict. Under `--all-pages`,
`judge_pdf_extraction` (`pdf_judge.py:1015-1074`) builds `unit_coverage`
fail-closed against the PHYSICAL page count, not just the units the router
selected: pages missing from `page_units` (an extractor drop) are added to
`unchecked_unit_ids` even though they were never "required" by the router,
and `coverage_complete` requires `checked_ids == required_set ==
page_units_set` with no unchecked, no failed, and no missing pages
(`pdf_judge.py:1041-1047`).

The metadata short-circuit (`pdf_judge.py:768-786`) is the other half of
the coverage story: when the mandatory metadata/outline check does not
return `pass`, page escalations and unit checks are skipped entirely
("neither can raise a verdict the metadata check already capped"),
documented fleet-wide at "44.6% of LLM calls... verified zero verdict
drift" (`CLAUDE.md` "Metadata short-circuit"). This is a genuine coverage
trade: on a short-circuited paper, `unit_coverage` is reset to a vacuous
`coverage_complete: True` with `mode: "metadata_short_circuit"`
(`pdf_judge.py:1083-1092`) rather than reflecting that zero units were
actually checked. The short-circuit is skip-by-design and bypassed for
audit modes (`--all-pages`, `--exhaustive-units`), so it is not a coverage
gap in the `--all-pages` golden-PR path CLAUDE.md requires, but it does
mean the DEFAULT fleet run's `unit_coverage.coverage_complete: True` can
mean either "every routed risky unit was actually checked" or "checking was
skipped because the metadata gate already failed" -- two very different
facts sharing one field value.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | `chunk_markdown`/`aggregate_adjudications` are unchanged from Auditv2 (333 lines, same lossless-concatenation and worst-axis-fold design); no live oversize-paper test exists in either audit | Informational | HIGH |
| F2 | Two unit-check sizing mechanisms coexist (`MAX_UNIT_CHECKS=5` static, `fleet_max_unit_checks` dynamic 3-7); this audit did not determine which is authoritative on a default fleet run or whether they can produce different caps on the same paper | LOW | MEDIUM |
| F3 | `SIGNAL_CLASS_QUOTA` and (separately) `MAX_IDEAL_DISCREPANCIES`/`MAX_IDEAL_QUOTE_CHARS`/`MAX_IDEAL_EXPLANATION_CHARS` are each defined twice in `constants.py` (lines 81/90, 86-87/91-92, 243-247/249-253); the ideal-discrepancy constant's two definitions disagree (8 then 10, the later one wins), the rest are identical duplicates | LOW | HIGH |
| F4 | The PDF-lane context-budget guard (`CONTEXT_SAFETY_MARGIN=0.80`) hard-fails (`PdfLaneError`) rather than truncating; this run's live papers never approached the threshold, so the guard's failure path itself is code-verified but not live-exercised | Informational | HIGH |
| F5 | `unit_coverage.coverage_complete: True` is emitted both when coverage was genuinely exhaustive and when the metadata short-circuit skipped checking entirely (`mode` distinguishes the two, but a reader filtering only on `coverage_complete` cannot tell them apart) | MEDIUM | HIGH |
| F6 | The `--all-pages` fail-closed coverage check correctly treats extractor-dropped pages as coverage gaps even when the router never listed them as required, closing a gap a naive "checked == required" comparison would miss | Informational | HIGH |

## 5. False-Pass Hypothesis

**Could chunking or unit selection let a corrupted paper reach a clean
`pass` by never reading the corrupted region?** For chunking: no. The
lossless split plus worst-axis fold plus partial-read capping (3.1-3.2,
unchanged from Auditv2) structurally prevents this for the text cascade.
For unit selection: partially open. `MAX_UNIT_CHECKS`/`fleet_max_unit_checks`
cap the NUMBER of scoped unit checks, and `_select_units_with_quotas`
guarantees only one slot per signal TYPE, not per flagged unit. A paper
with many risky units of the same signal type (e.g. ten `low_recall` pages)
under the 3-7 cap will have some of those units never individually
checked. This does not silently produce `pass`, because `unit_coverage`
capped-at-review logic (3.5) treats any router-flagged unit that was never
checked and remains in `unchecked_unit_ids` as review-forcing under
`--all-pages`; but in ROUTED (non-all-pages) mode, `unit_coverage` is only
built from `unit_result` when `risk_signals` is non-empty (`pdf_judge.py:
960-971`), and units the quota-selection process (`_select_units_with_
quotas`) excluded because their signal type was already covered are not
obviously tracked as `unchecked_unit_ids` in the routed path the way they
are in the `--all-pages` path. This audit did not trace `run_unit_checks`'s
internal handling of quota-excluded-but-risky units far enough to confirm
whether routed mode's `coverage_complete` accounts for them; flagged as an
open question, not resolved here.

**Could the metadata short-circuit hide a real defect from unit checks that
would have caught it?** By design, no: the short-circuit only fires when
the metadata check ALREADY caps the verdict below `pass` (`review` or
`fail`), so the paper cannot exit the short-circuited path with a clean
`pass` regardless of what the skipped unit checks would have found. The
risk is narrower: a paper whose metadata check wrongly returns `review` for
a cosmetic reason gets its DEFECT INVENTORY truncated (no unit-level defect
groups, no page escalations), even though the final verdict cap is correct.
A human reading the sidecar for such a paper sees `review` with no
supporting unit-level evidence, which is a diagnosability gap, not a
false-pass gap.

## 6. Gate/Dimension Mapping (PROPOSED)

| Gate | Dimension | Proposed status |
|------|-----------|------------------|
| G2 Fail-not-partial | Oversize-paper chunking (text cascade) | PROPOSED PASS (code-verified, unchanged from Auditv2, no live oversize test in either audit) |
| D3 Fidelity / partial-read capping | Worst-axis aggregation and partial-read demotion | PROPOSED PASS (code-verified) |
| G2 Fail-not-partial | PDF-lane context budget (no silent truncation) | PROPOSED PASS (code-verified; hard-fail path never live-exercised this run) |
| D3 Fidelity / partial-read capping | Unit-selection coverage in routed (non-all-pages) mode | PROPOSED gap: quota-excluded risky units' effect on `coverage_complete` not traced to a conclusion |

## 7. Limitations

- No live run in this audit's matrix (E13-E20) exercised a paper large
  enough to trigger H2 chunking, the `MAX_PAPER_MD_CHARS` split, or the
  PDF-lane `CONTEXT_SAFETY_MARGIN` guard's failure branch. All chunking/
  budget evidence here is code-level, same limitation Auditv2 recorded for
  chunking specifically, now extended to the newer context-budget and
  coverage machinery that did not exist as audited surface in Auditv2.
- Whether `MAX_UNIT_CHECKS` or `fleet_max_unit_checks` is authoritative on
  a default fleet run was not resolved (F2); this would require reading
  the call site that chooses between them in `pdf_judge.py`'s unit-check
  dispatch, which this file did not trace to a conclusion.
- The routed-mode (non-`--all-pages`) coverage-completeness question in
  Section 5 is flagged, not resolved.
- The suite is RED (E1); none of the 3 failing tests are in
  `chunking.py`, `unit_judge.py`, or the PDF-lane context-budget path by
  name, but this file does not independently confirm chunking-specific
  tests are among the 1784 passing (no test file dedicated to
  `chunking.py` is named in the ledger's per-module coverage scan, E3).

## 8. Conclusion

The chunking mechanism itself is unchanged from Auditv2 and remains sound
by code inspection: lossless splitting, severity-aware worst-axis
aggregation, and partial-read capping all still hold, still unverified live.
This audit's scope is substantially larger than Auditv2's because the
source-aware unit-selection quota system and the PDF lane's context-budget
guard and coverage bookkeeping are now mature enough to audit. The
context-budget guard fails loudly rather than truncating, which is the
correct fidelity posture, though never exercised live this run. Two
open questions are recorded rather than resolved: which of two competing
unit-check quota mechanisms is authoritative by default, and whether
routed-mode coverage tracking accounts for risky units the quota selector
excluded on signal-type grounds. Neither is evidence of a false pass; both
are gaps in this audit's ability to certify the coverage claim completely.

## 9. Delta vs Auditv2

Auditv2's C19 scoped `chunking.py` only (chunking, worst-axis aggregation,
partial-read tracking, binary-payload stripping) and concluded flat
"Gate verdict: PASS" against `1406 passed, 0 failed`. Its own Limitations
section explicitly named the gap this file now partially closes:
"real-LLM runtime is BLOCKED (E9); chunking behavior on actual oversize
papers is not verified live" -- the pod being live this run (00-PRECONDITIONS.md
§2) makes that verification POSSIBLE, but no live matrix scenario in
E13-E20 happened to use an oversize paper, so the gap persists factually
unchanged even though the blocker that caused it is gone.

The larger delta is scope, not verdict: `unit_judge.py`'s dynamic quota
system, `pdf_judge.py`'s context-budget guard, and the `--all-pages`
fail-closed coverage bookkeeping are new audited surface this file adds
that Auditv2's C19 did not cover at all (that source-aware v6 machinery is
listed as untracked/new in `00-PRECONDITIONS.md` §1). This file also
surfaces two findings Auditv2 had no occasion to find: the duplicate
(and, for `MAX_IDEAL_DISCREPANCIES`, DISAGREEING) constant definitions in
`constants.py`, and the ambiguity between `coverage_complete: True` meaning
"exhaustive" versus "short-circuited." Per the batch-wide hard rule, this
file does not lean on E1's 1784 passing tests as proof of correctness; the
suite's RED status (3 failed) is carried forward from the shared ledger
without independent re-verification that the failures are unrelated to
chunking/coverage (see Limitations).
