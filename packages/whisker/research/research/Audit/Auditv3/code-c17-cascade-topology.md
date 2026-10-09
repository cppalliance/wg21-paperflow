# C17 Cascade Topology

**Role**: Audit the cascade: routing, ordering, and which stage can veto which.
**Audited state**: whisker 0.5.0, working tree, manifest b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771.
**Gates**: G5 (LLM lane authenticity, PROPOSED), D11-adjacent (concurrency/ordering, PROPOSED, referenced from CLAUDE.md).

## 1. Scope

Trace the PDF-Text-Lane's stage order (monolith judge, metadata/outline
check, page escalation, unit checks) and the deterministic-plus-advisory
fusion stage that follows it, from source code, then confront that trace
against two live records (ledger E19, E16) that each exercise a different
edge of the same machinery: one where an advisory `review` signal was
discarded in favor of a deterministic `pass`, and one where a deterministic
`fail` was capped down to `review` by an advisory signal. State the exact
predicate in each case, not a general characterization.

## 2. Commands and Exits

| Evidence | Command / source | Result |
|---|---|---|
| E16 | `rt3_stress.py`, heading-jump stress paper | det=fail, LLM=review conf 0.98, rule `llm_rescue_heading`, fused=review, exit code after LLM ran still 5 |
| E19 | `rt4_canaries.py`, C2 (section-order reversal) | det=pass, LLM `suggested_verdict: review`, fusion selected `whisker_only`, fused=pass |
| — | `packages/whisker/src/whisker/tapetum_llm/pdf_judge.py` read | full file, stage order in `judge_pdf_extraction` |
| — | `packages/whisker/src/whisker/tapetum_llm/fusion.py` read | full file, `fuse_verdicts` and its helper predicates |
| — | `packages/whisker/src/whisker/tapetum_llm/unit_judge.py` read | `run_unit_checks`, quota selection, defect aggregation |

## 3. Current Evidence

### 3.1 The PDF-Text-Lane's internal stage order, as executed

`judge_pdf_extraction` (`pdf_judge.py:570-1128`) runs, per its own numbered
docstring (lines 581-601) and confirmed against the body:

1. Extract the PDF text layer (`extract_textlayer`, line 620) and the
   deterministic per-page recall screen (`screen_pages`, line 660).
2. One monolith LLM judge call (lines 670-684), producing `judgment:
   PdfJudgment` with `verdict`, `missing_content`, `confidence`,
   `reasoning`.
3. Ground `judgment.missing_content` against the source text layer
   (`ground_spans`, line 748), then classify each grounded quote against
   the candidate markdown (`classify_candidate_evidence`, line 749);
   `_fold_monolith_verdict` (lines 346-370, called at line 762) recomputes
   the monolith's verdict from these two-sided dispositions.
4. The mandatory metadata/outline check (`run_metadata_outline_check` or,
   under an env flag, the deterministic `compare_metadata_outline`, lines
   704-733) runs next; if its verdict is `fail`, the running verdict is
   forced to `fail` (line 764); if `review` and the running verdict is
   `pass`, it is forced to `review` (lines 765-766). This check's outcome
   also gates step 5-6 execution (below).
5. Self-reported-confidence and floor demotions (lines 790-803): a `pass`
   with `confidence == 0.0` demotes to `review`; a `pass` with
   `recall < PDF_JUDGE_RECALL_FLOOR` or `nid < PDF_JUDGE_NID_FLOOR` demotes
   to `review`.
6. Metadata short-circuit check (lines 773-785): if the metadata verdict is
   not `pass` and neither `all_pages` nor `exhaustive_units` was requested,
   steps 7-8 are skipped entirely (documented as saving "44.6% of LLM calls
   in the verified baseline," line 600), because the metadata verdict has
   already capped the running verdict at `review` or `fail` and nothing
   downstream can raise it further.
7. Scoped page escalation (lines 824-925): for each page the deterministic
   recall screen flagged, one scoped LLM call re-checks that single page;
   a confirmed miss demotes a `pass` to `review` (line 918-919); if flagged
   pages exceed `MAX_PAGE_ESCALATIONS`, no escalation calls are made at all
   and the verdict is demoted directly (lines 829-842).
8. Source-aware unit checks (lines 926-1013): `route_pdf_units` computes
   risk signals from source-vs-candidate deltas (traced in C18); flagged
   units get scoped LLM checks (`run_unit_checks`); a `review` unit-check
   verdict demotes a `pass` running verdict to `review` (lines 1008-1009).

Every demotion in this internal cascade is one-directional: verdict only
ever moves `pass -> review` or `review/pass -> fail` (via the metadata
check's `fail` branch, line 764) within this function. No later stage in
this list can promote a verdict raised by an earlier one back up.

### 3.2 The fusion stage: deterministic sidecar meets tapetum sidecar

`fuse_verdicts(whisker, tapetum)` (`fusion.py:348-549`) is a separate, pure
function operating on the two already-finalized sidecars (the deterministic
`whisker` result and the PDF-Text-Lane's `tapetum` sidecar from 3.1). Its
branch order, as written:

1. If the tapetum sidecar is unusable (absent, `status: "error"`, or a
   confidence-0 stub without axis findings; `_tapetum_is_usable`, lines
   154-164), return `combined_verdict = det`, rule `whisker_only`
   (lines 365-376).
2. If `det == "fail"`: check `_is_heading_only_fail(whisker)` (lines
   311-322, true only when every hard flag starts with `gate:
   heading_monotone`) AND `llm in (pass, review)`; if both hold, return
   `combined_verdict = "review"`, rule `llm_rescue_heading` (lines 384-396).
   Otherwise return `combined_verdict = "fail"`, rule
   `whisker_fail_locked` (lines 398-408). Fail is otherwise always locked.
3. If `det in (pass, review)` and `_source_aware_requires_review(tapetum)`
   (traced in 3.3 below) is true: return `combined_verdict = "review"`, rule
   `source_aware_review_cap` (lines 410-423).
4. If the ideal-verifier's own verdict is `review`: return `combined_
   verdict = "review"`, rule `ideal_review_cap` (lines 425-436).
5. If `det == "review"`: three sub-branches can clear to `pass`
   (`llm_clear_soft_review` and its two guarded variants, lines 439-519),
   gated on `_has_only_soft_flags(whisker)`, `llm == "pass"`, no axis fail,
   and (when `ref_nid` is present) `ref_nid >= FUSION_REF_NID_FLOOR`; one
   sub-branch (`clear_blocked_missing_region`, lines 443-458) explicitly
   blocks the clear when `whisker.missing_region_count > 0`, reasoning that
   the LLM only sees the markdown and cannot verify content absence.
6. If `det == "pass"` and `llm == "fail"` with a major-severity axis
   finding (`_has_major_axis_fail`, lines 295-300): return `combined_
   verdict = "review"`, rule `llm_escalate_major` (lines 524-535). This
   is the only path by which an advisory signal can move a deterministic
   `pass` upward toward `review`; it requires `fail`, not `review`, on the
   LLM side.
7. Default (line 538): `rule = FUSION_RULE_AGREE if det == llm else
   FUSION_RULE_WHISKER_ONLY`, `combined_verdict = det`. This is the
   fallback that fires whenever none of the preceding rules matched.

### 3.3 `_source_aware_requires_review`, the one predicate that decides whether an advisory `review` survives

`_source_aware_requires_review` (`fusion.py:182-227`) returns `True`
(forcing a review cap) under any of:

- No source-aware data present at all returns `False` immediately (line
  184-185), i.e. this predicate only applies to schema-v6+ sidecars.
- The `metadata_outline_check` verdict is anything other than `pass`
  (lines 187-189).
- `unit_coverage.coverage_complete` is not `True`, or `unchecked_unit_ids`
  / `failed_unit_ids` is non-empty (lines 191-195).
- Under `all_pages_requested`, the `unit_selection` required set is empty
  or has unchecked/failed entries (lines 197-207).
- At least one `high`/`critical`-severity defect group carries a `verified_
  count > 0` count-verification status, or matches an accepted unit defect
  or flattened disposition (lines 209-226).

Nothing in this predicate reads `suggested_verdict`, `confidence`, or the
free-text `reasoning` field directly. It is a check over the METADATA
check's own verdict and the UNIT-CHECK coverage/defect-verification state,
not over the primary judge's overall verdict.

### 3.4 E19 traced against 3.2-3.3: why the review was discarded

C2 (section-order reversal) produced `det = "pass"` (deterministic gates
pass on a token-preserving reorder, per C15 §3.2) and `tapetum.
suggested_verdict = "review"` at confidence 0.95 (E17), with the model's
reasoning explicitly naming "substantial reordering... failing the
conversion" (E19 quoted text). Per 3.2 step 3, fusion checks
`_source_aware_requires_review(tapetum)`. Per the ledger (E19 point 2), the
metadata/outline check for this paper returned `verdict: "pass"` with
reasoning *"Candidate headings are in reverse order... but all source
sections are present. Heading levels are consistent."* Per 3.3, this makes
the metadata branch of the predicate return `False` (verdict IS `pass`);
assuming (as the ledger states, "with the cap not firing") unit coverage
was complete and no qualifying defect group existed, every branch of
`_source_aware_requires_review` returns `False`, so step 3 of `fuse_
verdicts` does not fire. Step 4 (ideal review cap) does not apply here
(no `ideal_verdict == "review"` stated). Step 5 does not apply (`det` is
`pass`, not `review`). Step 6 requires `llm == "fail"`; here `llm ==
"review"`, so `llm_escalate_major` cannot fire either (this is the exact
mechanism the ledger names: "`llm_escalate_major` cannot cover it either:
that rule requires the LLM verdict to be fail with a major axis"). Execution
reaches the default at line 538: `det == llm` is `"pass" == "review"`,
false, so `rule = FUSION_RULE_WHISKER_ONLY`, `combined_verdict = det =
"pass"`. The precise predicate that let the review-suggesting advisory
verdict be discarded is: no rule in `fuse_verdicts` demotes a deterministic
`pass` on the strength of an LLM `review` verdict alone; `_source_aware_
requires_review` is gated on the METADATA and UNIT-COVERAGE checks, not on
the primary judge's own verdict, and in this instance the metadata check
independently agreed the document was structurally intact despite seeing
the same reversal the primary judge flagged.

### 3.5 E16 traced against 3.2: why the fail was capped, not locked

The stress paper carried `hard_flags: ['gate:heading_monotone:heading level
jumps H2 -> H4']` only (E16), which is exactly the shape
`_is_heading_only_fail` requires (every hard flag starts with `gate:
heading_monotone`, `fusion.py:311-322`). With `det == "fail"` and this
predicate true, and `llm == "review"` (which is in `(pass, review)`), step 2
of 3.2 fires: `combined_verdict = "review"`, rule `llm_rescue_heading`
(`fusion.py:384-396`). This is the ONLY fail-side rescue path in the entire
function; every other `det == "fail"` combination falls through to
`whisker_fail_locked` (line 398-408) regardless of what the LLM says. The
ledger confirms the two invariants this predicate guarantees at runtime:
"promoted to pass: no" (the rescue's return value is hardcoded to `review`,
never `pass`, matching line 387) and "deterministic exit code after the LLM
ran: 5" (the fusion result is advisory-only; `score.py`'s gate exit code is
computed from the deterministic verdict alone, unaffected by anything in
`fuse_verdicts`).

### 3.6 Both mechanisms are the same code path, read without moralizing

E19 and E16 are not two different bugs; they are two branches of one
function reached under different `(det, llm, source_aware_state)` triples.
`llm_rescue_heading` (3.5) exists to prevent a single narrow deterministic
false-fail (a heading-level jump with no other hard flag) from locking out
an LLM's contrary evidence, and it is deliberately asymmetric (never
promotes past `review`). `_source_aware_requires_review` (3.3-3.4) exists to
cap a `pass`/`review` at `review` when the METADATA/UNIT-COVERAGE evidence
says so, independent of the primary judge's own suggested verdict. Neither
predicate reads the other's trigger condition, which is exactly how E19
occurs: the primary judge's `review` had no channel to act on `det == pass`
because `llm_escalate_major` (the one primary-judge-driven upgrade path)
requires `llm == fail`, and the source-aware cap's own inputs (metadata,
unit coverage) happened to independently clear.

### 3.7 Unit-check ordering and quota, unchanged shape from Auditv2, confirmed present

`run_unit_checks` (`unit_judge.py:358-589`) sorts risk signals by severity
rank first (`critical`, `high`, `medium`, `low`, lines 403-412), then by
unit id, then guarantees at least one selected unit per distinct
`signal_type` before filling remaining quota slots in sorted order
(`_select_units_with_quotas`, lines 216-254). The per-paper cap is dynamic
in fleet mode (`fleet_max_unit_checks`, lines 192-213, bumps above
`FLEET_UNIT_CHECK_BASE` for critical/high severity, table-presence signals,
or high signal count, capped at `FLEET_UNIT_CHECK_CEILING`) unless
`TAPETUM_DYNAMIC_QUOTA` is set to something other than `"1"`, in which case
the static `MAX_UNIT_CHECKS` applies; both are bypassed entirely under
`exhaustive=True` (audit modes). Required units (`all_pages` mode) are
promoted into the selected set regardless of quota (lines 439-447). This
ordering was not independently re-verified against a live multi-unit run in
this pass; it is read from source and is architecturally consistent with
the aggregate defect-count and coverage fields observed in E16/E19's
sidecars.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---|---|---|
| F1 | The internal PDF-Text-Lane cascade (monolith, metadata, page-escalation, unit-checks) is strictly one-directional within `judge_pdf_extraction`: every stage can only hold or demote the running verdict, never promote it past a prior stage's cap | INFO | HIGH |
| F2 | `_source_aware_requires_review` (`fusion.py:182-227`) is keyed on the METADATA check's verdict and UNIT-COVERAGE/defect-verification state, not on the primary judge's `suggested_verdict`; this is the exact mechanism by which E19's advisory `review` was discardable while `det == pass` | HIGH | HIGH |
| F3 | `llm_rescue_heading` (`fusion.py:384-396`) is the only path by which a deterministic `fail` can be softened, gated narrowly on hard flags being exclusively `gate:heading_monotone`, and is architecturally incapable of promoting past `review`; E16 confirms both properties live | INFO | HIGH |
| F4 | `llm_escalate_major`, the only rule that lets the LLM raise a deterministic `pass`, requires `llm == "fail"` with a major-severity axis finding; an LLM `review`, however strongly worded, cannot trigger it, which is the second half of the E19 mechanism | HIGH | HIGH |
| F5 | The two live records (E16, E19) exercise disjoint branches of the same `fuse_verdicts` function under different input triples; neither is anomalous relative to the code as read, both are the code executing its written branch order | INFO | HIGH |
| F6 | Unit-check severity/quota ordering (`_select_units_with_quotas`, `fleet_max_unit_checks`) is unchanged in structure from what would be expected of Auditv2's description, but was not independently exercised by live multi-unit evidence in this pass | INFO | MEDIUM |

## 5. False-Pass Hypothesis

**Could a reader of the merged advisory sidecar reasonably conclude the
document was clean when the primary judge explicitly said otherwise?** Yes,
for the exact shape of E19: the sidecar's `combined_verdict` field reads
`pass`, and the free-text reasoning naming "substantial reordering" lives
in a different field (`tapetum_verdict` / the underlying judge reasoning),
not surfaced in the top-line combined result. This is not a moralizing
claim about intent; it is a description of which field a consumer reading
only `combined_verdict` would see, per the fields the sidecar actually
carries (ledger E19: "The sidecar's own fusion block records
`tapetum_verdict: 'review'` and `combined_verdict: 'pass'`").

**Could the metadata check's independent agreement with the deterministic
`pass` be characterized as the metadata check "missing" the reorder?** No:
per E19's quoted reasoning, the metadata check saw the reversal explicitly
("Candidate headings are in reverse order") and voted `pass` anyway,
because its own rubric (per `METADATA_CHECK_SYSTEM_PROMPT`, `unit_judge.py:
131-144`) judges "field values, missing sections, and heading-level drift,"
and a reordering that preserves every section and every heading level is
outside that specific rubric's fail criteria. This is a scope statement
about what the metadata check is designed to catch, not a defect in that
check relative to its own definition.

## 6. Gate/Dimension Mapping (PROPOSED)

| Gate | Dimension | Status (PROPOSED) |
|---|---|---|
| G5: LLM lane authenticity | Advisory-to-gate isolation (fail-side) | PROPOSED CONFIRMED, live (F3, E16) |
| G5: LLM lane authenticity | Advisory-to-gate isolation (pass-side, upward) | PROPOSED CONFIRMED narrow (F4): only `llm_escalate_major`, requiring LLM `fail` |
| G5: LLM lane authenticity | Primary-judge `review` signal propagation into the merged verdict | PROPOSED GAP (F2, F4): no direct channel when `det` is `pass` and source-aware checks independently clear |

## 7. Limitations

- This report traces `fuse_verdicts` against exactly the two triples
  observed live (E16, E19); it does not enumerate or test every branch of
  the function (e.g. `llm_clear_soft_review` and its guarded variants,
  `ideal_review_cap`) against live evidence, only against source reading.
- Whether `_source_aware_requires_review`'s unit-coverage and defect-group
  conditions were literally all `False`/empty for the C2 canary (as opposed
  to simply not documented in the ledger) is inferred from the ledger's own
  phrasing ("with the cap not firing") rather than from a raw sidecar dump
  independently read in this pass.
- 3.7's unit-check ordering claims were not exercised against a live
  multi-unit run with several risk signals of mixed severity in this
  audit's evidence; they are read from source only.
- Per 00-PRECONDITIONS.md §1, this is a working-tree audit; the exact line
  numbers cited match the file as read this pass and could shift under
  further uncommitted changes.

## 8. Conclusion

The cascade has two layers: an internal, strictly one-directional stage
sequence inside the PDF-Text-Lane itself (monolith, metadata, page
escalation, unit checks, each only able to hold or demote), and a separate
pure fusion function that merges the lane's finalized sidecar against the
deterministic verdict. Two live records expose opposite edges of the fusion
function's branch order. In E19, a `pass`-side deterministic verdict was
not demoted by an advisory `review` because the one predicate that could
have capped it (`_source_aware_requires_review`) is keyed to the metadata
and unit-coverage checks, not to the primary judge's own verdict, and those
checks independently agreed the document was intact under their own
narrower rubric; the one rule that CAN raise a `pass` on LLM say-so
(`llm_escalate_major`) requires an LLM `fail`, not a `review`, so a `review`
from the primary judge has no channel to act on a deterministic `pass` at
all. In E16, a `fail`-side deterministic verdict was capped down to
`review`, never promoted to `pass`, and the gating exit code was
unaffected, via the sole narrowly-scoped `llm_rescue_heading` rule. Both are
the same machinery, read as written, exercised under different inputs. No
verdict is rendered on whether this branch structure is the right design;
the predicates and their exact trigger conditions are reported for
synthesis.

## 9. Delta vs Auditv2

Auditv2's C17 (HEAD 51cb704, no live LLM lane available) described the
two-tier cascade, escalation triggers, and aggregation rules entirely from
static reading of `fusion.py` and `unit_judge.py`, necessarily stating the
branch predicates as code facts without runtime confirmation that any given
predicate would actually fire as read. This report adds two live firings
(E16's `llm_rescue_heading`, E19's fall-through to `whisker_only`) that
confirm Auditv2's structural trace was accurate in shape, while surfacing a
consequence Auditv2 could not observe without a live model: that the same
branch structure can let a document the primary LLM judge explicitly called
"substantially reordered... failing the conversion" fuse to a top-line
`pass`, because the demotion path for `pass`-side advisory disagreement
runs through the metadata/unit-coverage checks rather than through the
primary judge's own verdict, and because the LLM-upgrade path
(`llm_escalate_major`) requires `fail`, not `review`, from the LLM. Auditv2
had no occasion to identify this specific gap because it requires an actual
`(det=pass, llm=review, metadata=pass)` triple occurring at runtime to
surface, which Auditv2's blocked LLM lane could not produce.
