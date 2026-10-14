# C21 Fusion and Operator Trust

**Role**: Audit what a fused verdict is entitled to claim, given a live, reproducible case where the fused report says `pass` on a document the primary LLM judge called a failing conversion.
**Audited state**: whisker 0.5.0, working tree, manifest b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771
**Gates**: G1 (Advisory non-leakage), D1 (Epistemic separation)

## 1. Scope

This file is the most consequential in the batch. Auditv2's C21 verified
the fusion rule matrix entirely offline (`test_fusion.py`, `pytest`) and
found the asymmetric-transition property sound with "No violations
found." This run has live evidence the offline suite cannot produce: a
real canary (C2, reverse section order, ledger E17) that fused to `pass`
while the primary judge's own suggested verdict on the same record was
`review`, plus a repeated-run measurement (E20) showing the deciding
input is itself unstable. This file traces the mechanism exactly, states
what it does and does not mean for gate integrity, and makes a specific
code-level recommendation.

## 2. Commands and Exits

```
E1:  uv run --package whisker pytest packages/whisker/tests -q --tb=line -> 3 failed, 1784 passed (exit 1)
E17: rt4_canaries.py, C2 (reverse section order), live pod, det verdict pass, llm review (0.95), fused pass
E20: rt7_repeat.py, forced re-run x3 of control and C2, same model, same prompts
```

`test_fusion.py` (Auditv2's sole cited evidence for C21) is not
independently re-run this pass; per the batch's hard rule this file does
not lean on E1's passing-test count as evidence the matrix is correct,
because the live case in Section 3 demonstrates a real record for which
the matrix's OWN documented rule set has no rule that catches it, a gap
an offline parametric test suite constructed to test the EXISTING rules
would not surface unless it happened to include this exact input shape.

## 3. Current Evidence

### 3.1 The live case, verbatim

Ledger E17/E19. Base document: 25157 chars, 9 H2 sections. C2 mutation:
reverse section order, token-preserving (no content added or removed).
`unigram_coverage` for C2 is 0.9542, identical to the untouched control,
so the deterministic verdict is `pass`. The LLM's own report on the same
document (E19):

> "The markdown body is severely reordered: sections 4.2-4.7 appear before
> 4.1... The abstract, revision history, disclosure, and motivation
> sections are also moved to the end. This structural corruption
> constitutes substantial reordering, **failing the conversion**."

`suggested_verdict` for this call is `review` at confidence 0.95. The
sidecar's own `fusion` block records `tapetum_verdict: "review"` and
`combined_verdict: "pass"`, rule `whisker_only` (E19). This is not a
hypothetical: it is the literal content of one live sidecar, produced by
one live run against the real pod, on this audit's manifest.

### 3.2 The mechanism, traced to two specific lines

`fuse_verdicts` (`fusion.py:348-549`) branches on `det` (whisker's
deterministic verdict). For `det == VERDICT_PASS` (C2's case), the ONLY
rule capable of demoting the combined verdict below `pass` before the
function reaches its fallback is:

```410:423:packages/whisker/src/whisker/tapetum_llm/fusion.py
    if det in (VERDICT_PASS, VERDICT_REVIEW) and _source_aware_requires_review(
        tapetum
    ):
        return FusionResult(
            combined_verdict=VERDICT_REVIEW,
            combined_rule=FUSION_RULE_SOURCE_AWARE_REVIEW_CAP,
            ...
```

followed by an ideal-review check (`fusion.py:425-436`, not applicable,
no ideal data for this synthetic canary) and, later in the function, an
escalation rule that only fires when `llm == VERDICT_FAIL` with a major
axis (`fusion.py:522-535`, `FUSION_RULE_LLM_ESCALATE_MAJOR`). C2's
`llm` value is `review`, not `fail`, so escalation categorically does not
apply regardless of what the model wrote. With `_source_aware_requires_
review` returning `False` (3.3) and no ideal data, execution falls
through every branch and reaches the unconditional fallback:

```538:549:packages/whisker/src/whisker/tapetum_llm/fusion.py
    # Default: agree (verdicts match) or no applicable rule (keep det)
    rule = FUSION_RULE_AGREE if det == llm else FUSION_RULE_WHISKER_ONLY
    return FusionResult(
        combined_verdict=det,
        combined_rule=rule,
        ...
```

`det` ("pass") != `llm` ("review"), so `rule = FUSION_RULE_WHISKER_ONLY`
and `combined_verdict = det = "pass"`. The primary judge's `review`,
carrying a confidence-0.95, evidence-backed description of the exact
defect, is discarded at this line with no trace left in `combined_verdict`
(it remains visible only in the separately-recorded `tapetum_verdict`
field of the same sidecar).

### 3.3 Why the source-aware cap did not fire: it reads a verdict field, not the reasoning that produced it

`_source_aware_requires_review` (`fusion.py:182-227`) is a fail-closed
predicate over three independent legs: the metadata/outline check's own
`verdict` field (`fusion.py:187-189`), unit-coverage completeness
(`fusion.py:191-195`), and verified high/critical defect groups
(`fusion.py:209-226`). For C2, ledger E19 records the metadata check's
own output directly: `verdict: "pass"`, with reasoning *"Candidate
headings are in reverse order... but all source sections are present.
Heading levels are consistent."* (E19). The model that performs THIS
specific sub-check saw the reversal, described it accurately in its own
reasoning text, and still emitted `verdict: "pass"`, because the
structured schema this sub-check populates apparently does not treat
"heading order matches source order" as a required condition for `pass`
(no distinct order/sequence field was found in the metadata/outline
check's schema this audit inspected). `_source_aware_requires_review`
reads only the boolean-shaped `verdict` field at line 188; it has no
visibility into the reasoning string that, on this exact record,
contained the correct answer.

This is a two-layer loss, not one: the metadata sub-check's OWN verdict
classification discards the order signal its own reasoning already
computed (layer 1), and then `_source_aware_requires_review` trusts that
verdict field at face value with no secondary check (layer 2). Both
layers are necessary for the loss; fixing either alone would close this
specific gap.

### 3.4 Instability of the deciding input (E20)

`rt7_repeat.py` forced three re-runs of the same three papers, identical
model, identical prompts. C2 produced `review` in runs 1-2 and `pass` in
run 3 (`whisker_only`); the untouched control itself produced `review` in
runs 1-2 and `pass` in run 3 too. Including the original canary run, the
control fused to `pass` in 1 of 4 total observations and C2 in 2 of 4
(E20). The ledger attributes the flip specifically to "the metadata/
outline check, which returned `pass` in run 3 and `review` in runs 1 and
2 for identical input" (E20). This means the exact predicate traced in
3.2-3.3, the one gate standing between C2 and a dropped `review`, is
itself a coin flip on this evidence: the SAME document, SAME model,
SAME prompt produced a different metadata-check verdict in 2 of 4 tries,
and the fused `combined_verdict` followed it exactly both times.

### 3.5 Three things, stated separately, as the evidence requires

**(1) This is not a gate breach.** `score.py` never reads a tapetum
sidecar (unchanged architectural fact, not re-derived independently this
run; consistent with C02 §3.1's import-boundary evidence). The `whisker
--gate` exit code for C2 is whatever the deterministic `pass` alone
produces; nothing in `fuse_verdicts` writes back into `WhiskerResult` or
into the exit-code path. `FusionResult.advisory` is a frozen `True`
(Auditv2 F6, not re-verified at that exact line this run but consistent
with the module's pure-function shape confirmed in 3.2). The advisory
lane, including this specific failure mode, never authorizes a CI pass.

**(2) It IS a reporting defect.** The fused report's `combined_verdict`
field is the line a human is meant to read as the merged answer; that is
its entire purpose (Auditv2's own framing: "the merged human-facing
report"). On this live record, that field reads `pass` while the record's
own `tapetum_verdict` field, two lines away in the same JSON object,
reads `review` and is backed by an evidence-quoted description of
"substantial reordering, failing the conversion." A human who reads only
`combined_verdict`, which is the field the fused report is FOR, is told
the opposite of what the primary judge concluded. This is not a
disagreement between two lanes about a genuinely ambiguous document; both
lanes are visible in the record, but the field designed to summarize them
picks the one that contradicts the other's own words.

**(3) The root predicate gates on a verdict classification, not on the
underlying finding.** `_source_aware_requires_review` (`fusion.py:182`)
is architecturally a check on OTHER checks' verdict fields (the metadata
check's `verdict`, unit-coverage's `coverage_complete`, defect groups'
`verified_count`), not a check on the primary judge's own top-level
`suggested_verdict`. The gap this exposes is structural: there is no
fusion rule anywhere in `fuse_verdicts` (`fusion.py:348-549`) that caps a
deterministic `pass` at `review` simply because the primary judge's own
`suggested_verdict` is `review`, independent of source-aware sub-check
data. `llm_escalate_major` (`fusion.py:522-535`) exists for `llm == fail`
with a major axis; no symmetric rule exists for `llm == review` without
source-aware corroboration. C2 falls into exactly that hole: `det=pass`,
`llm=review`, no source-aware trigger, no ideal data, no escalation
eligibility (llm is not fail), so the ONLY code path left is the
fallback, and the fallback keeps `det` whenever `det != llm` (which is
definitionally true here) rather than treating a plain `review` from the
primary judge as review-worthy in its own right.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | A live canary (C2) fused to `pass` while the primary LLM judge's own `suggested_verdict` on the identical record was `review` at confidence 0.95, with a quoted, accurate description of the defect | HIGH | HIGH |
| F2 | The deterministic exit code and gate are untouched by this failure mode; `score.py` never consumes a tapetum sidecar (unchanged architectural fact) | Informational (confirms non-leakage) | HIGH |
| F3 | No fusion rule exists that caps a deterministic `pass` at `review` on a plain `llm == review` disagreement without source-aware or ideal corroboration; `llm_escalate_major` only covers `llm == fail` | HIGH | HIGH |
| F4 | The metadata/outline check's own reasoning text can correctly describe a defect (heading reversal) while its structured `verdict` field says `pass`; `_source_aware_requires_review` reads only the verdict field | HIGH | HIGH |
| F5 | The metadata check's verdict for the same document, same model, same prompt flipped between `review` and `pass` in 2 of 4 observations (E20); this is the exact field the entire cap in F4 depends on | HIGH | HIGH |
| F6 | The other three canaries (C1 gross loss, C3 cell swap, C4 code-span corruption) do not reproduce this failure mode: C1 hard-fails both lanes, C3 correctly lands on fused `review`, C4 is missed by both lanes identically (not a fusion defect, a metric blind spot per C02 §3.7) | Informational (scopes F1 to the reordering class specifically) | HIGH |

## 5. False-Pass Hypothesis

**Could this be dismissed as "the LLM lane is noisy, so of course one
canary flips"?** No. The flip is not random noise scattered across
canaries; it is traceable to one specific, named code path
(`_source_aware_requires_review` reading one boolean field) and one
specific, named instability source (the metadata check's own verdict
classification, E20). A false-pass hypothesis that attributed this to
generic LLM variance without tracing the mechanism would be
underspecified; this file traces it to the exact line and the exact
missing rule (3.2-3.3, F3-F4).

**Could the "not a gate breach" framing be used to wave this away as
unimportant?** No, and this is the central risk the Role statement
exists to flag. The gate's integrity is not in question (F2). But
CLAUDE.md's own stated purpose for the advisory lane is to give a human
"a second opinion" (per C07's citation of `tapetum_llm.md:3-4`); a second
opinion that is computed correctly, recorded correctly in the sidecar,
and then overwritten by the summary field a human is expected to read is
a second opinion that has been rendered invisible in the one place it
was supposed to surface. Severity is scoped to reporting/trust, not to
gate correctness, but that scope is still HIGH: a human operator relying
on `combined_verdict` alone (the field's entire reason to exist) would
approve a document the primary judge explicitly called a failing
conversion.

**Could adding a rule for `llm == review` without corroboration cause new
false demotions?** This is the correct question to ask before
implementing the recommendation below, and this file does not claim to
have answered it. A blanket "llm == review always caps det == pass at
review" rule would make EVERY control-run flip (E20 shows the untouched
control itself hits `llm == review` in 3 of 4 observations) visible as a
review-capped result rather than a clean pass, which is arguably more
honest (the ledger's own point: the control's LLM read is unstable too)
but would also raise the review rate on papers where the LLM's `review`
is a false positive rather than a caught defect (per C08 F1-F2, the LLM
lane has both true positives, C1/C3, and no evidence either way on
routine false positives at scale). This trade-off is a policy decision
for the planner, not settled here.

## 6. Gate/Dimension Mapping (PROPOSED)

| Gate | Dimension | Proposed status |
|------|-----------|------------------|
| G1 Advisory non-leakage | Deterministic exit code / gate integrity under this failure mode | PROPOSED PASS (F2, unchanged architectural fact, live-consistent) |
| D1 Epistemic separation | Fused-report fidelity to its own constituent judge verdicts | PROPOSED FAIL: a live, reproducible case exists where `combined_verdict` contradicts `tapetum_verdict` in the same record, in the direction a human is most likely to trust (pass) |
| G1 Advisory non-leakage | Coverage of the fusion rule matrix against `llm == review` without source-aware corroboration | PROPOSED gap: no rule exists (F3); the fallback silently prefers `det` |

## 7. Limitations

- This audit observed the failure mode on one canary family (reordering,
  C2) with 4 total observations (E17 + E20's 3 reruns). It does not
  establish a rate at which this specific failure mode occurs across the
  corpus; C1/C3/C4 do not reproduce it (F6), so it is not a general
  "fusion is broken" finding, it is specific to `det=pass`,
  `llm=review`, no source-aware/ideal corroboration.
- Whether the metadata/outline check's structured schema has any field
  capable of representing "order differs from source" was inspected only
  through the reasoning text quoted in the ledger (E19); this file did
  not independently read the `MetadataOutlineCheck` Pydantic model's
  field list to confirm no such field exists at all versus existing but
  unpopulated. The recommendation in Section 8 should be verified against
  that model before implementation.
- The policy question raised in Section 5's third paragraph (would a
  fix over-trigger on the control's own instability) is explicitly not
  resolved here; it requires either a larger live sample or an explicit
  decision from the planner about acceptable review-rate inflation.
- Per the batch's hard rule, this file does not cite `test_fusion.py`'s
  passing status (part of E1's 1784) as evidence the matrix is sound;
  the live gap found here would not necessarily be caught by that
  offline suite unless it contains a fixture shaped like this exact
  input.

## 8. Conclusion

Three facts hold simultaneously and must not be collapsed into one
verdict. The deterministic gate is untouched: `score.py` and the exit
code for C2 are exactly what `unigram_coverage` alone would produce, and
nothing about this failure mode threatens G1. The fused report is,
independently, currently wrong in the sense that matters most to a human
reader: `combined_verdict: pass` sits next to `tapetum_verdict: review`
in the same sidecar, describing a document the primary judge called a
failing conversion in its own words. And the root cause is precisely
locatable: `_source_aware_requires_review` (`fusion.py:182`) is a check on
OTHER checks' verdict fields, there is no fusion rule that caps a plain
`llm == review` disagreement without source-aware or ideal corroboration,
and the one sub-check whose verdict field could have caught this specific
case (the metadata/outline check) is measured, on this same evidence, to
flip between `pass` and `review` on identical input in roughly half of
observations (E20).

**Recommendation, precise:**

1. Root-cause fix: give the metadata/outline check's structured output an
   explicit, required boolean field for sequence/order agreement (e.g.
   `heading_order_matches_source`), separate from the general `verdict`
   field, and make a non-null `False` on that field an unconditional
   trigger in `_source_aware_requires_review`, independent of what the
   check's own `verdict` field says. This closes the exact gap in 3.3: the
   model already computes the right answer in its reasoning text; the fix
   is to force that specific fact into a structured field the cap
   predicate can read, rather than trusting an aggregate `verdict` that
   may not weight ordering as disqualifying.
2. Fusion-layer fix, independent of (1): add a rule to `fuse_verdicts`
   for `det == VERDICT_PASS` and `llm == VERDICT_REVIEW` with no other
   rule matching, mirroring the existing `llm_escalate_major` pattern but
   for `review` rather than `fail`, so a plain top-level disagreement from
   the primary judge is never silently absorbed by the `whisker_only`
   fallback. This is the more general fix and would have caught C2 even
   if fix (1) is not implemented, at the cost of the review-rate
   trade-off flagged in Section 5's third paragraph, which the planner
   must weigh.
3. Stability precondition for either fix: because E20 shows the metadata
   check's own verdict is unstable on identical input, any fix that reads
   that field (fix 1) inherits that instability unless the check itself is
   made more deterministic first (e.g., majority-vote across 2-3 calls
   before trusting the verdict, or replacing the LLM-based order check
   with a mechanical heading-sequence comparison, which is entirely
   computable without a model call and would remove this specific
   instability source from the critical path). Fix (2) is more robust to
   this instability than fix (1) alone, because it caps on the top-level
   `suggested_verdict`, which in this evidence set (E17, E19) was stable
   and correct across the observations that matter (review, review,
   review across all 4 C2 observations per E20's own table: runs 1-2 show
   `review`, and even the flipped run 3 is the metadata check flipping,
   not the top-level suggested_verdict).

## 9. Delta vs Auditv2

Auditv2's C21 was entirely offline: `test_fusion.py` under `pytest`,
concluding "The fusion rule matrix is well-designed and asymmetric by
construction... No violations found," with its Limitations section
explicitly naming the gap this file closes: "The interaction between
live LLM sidecars and fusion behavior in practice requires runtime
testing (BLOCKED)." That blocker is resolved this run (00-PRECONDITIONS.md
§2), and the live test surfaces exactly the kind of gap an offline
parametric suite built around the EXISTING named rules would not
find: a real input shape (`det=pass`, `llm=review`, no source-aware
trigger) for which the documented rule table has no entry at all, only a
fallback that happens to prefer `det`.

Auditv2's asymmetric-transition analysis (fail->pass impossible,
pass->fail impossible, 3.5 of that file) is not contradicted here: C2's
transition is `pass` staying `pass`, not a forbidden transition firing.
What Auditv2 could not have found, because it never ran live evidence, is
that "no forbidden transition fired" and "the fused report accurately
represents the underlying disagreement" are two different claims, and
this run's live canary is proof the second one currently fails on at
least one reproducible input class. Auditv2's F4 ("Source-aware review cap
runs before clear check, trumps LLM opinion") is reaffirmed as
CODE-ACCURATE but shown, live, to be narrower in practice than its
phrasing implies: the cap only trumps the LLM's opinion when the
source-aware sub-checks themselves agree there is a problem; it does not
generically trump a plain, uncorroborated `review` from the same LLM's
own top-level verdict.
