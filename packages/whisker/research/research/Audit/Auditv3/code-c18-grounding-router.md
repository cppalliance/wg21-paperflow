# C18 Grounding and Source Router

**Role**: Audit two-sided evidence grounding and the source-aware risk router.
**Audited state**: whisker 0.5.0, working tree, manifest b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771.
**Gates**: G5 (LLM lane authenticity, PROPOSED), D6/D10 upstream discipline (PROPOSED, referenced).

## 1. Scope

Trace the deterministic grounding pipeline (`grounding.py`) that verifies
every LLM-cited quote against source text and then classifies it against
candidate text, and the lane-local risk router (`source_router.py`) that
flags source-vs-candidate discrepancies independent of any deterministic
whisker artifact. Confront both against the C15 metrology canaries (E17,
E18) and the C17 fusion trace (E19) to determine what the grounding and
routing machinery can and cannot see, using the same construct-validity
discipline as C15: state capability boundaries from the code's own token
and pattern definitions, not from a pass/fail label.

## 2. Commands and Exits

| Evidence | Command / source | Result |
|---|---|---|
| E17 | `rt4_canaries.py` canary matrix | grounding/routing outcomes implicit in det verdict and LLM findings per canary |
| E18 | C4 detail | `<memory_resource>` corruption; deterministic surface and router both blind |
| E19 | C2 fusion trace | metadata check's own grounded assessment of the reorder |
| — | `packages/whisker/src/whisker/tapetum_llm/grounding.py` read | full file, 640 lines |
| — | `packages/whisker/src/whisker/tapetum_llm/source_router.py` read | full file, 371 lines |
| — | `packages/whisker/src/whisker/tapetum_llm/unit_judge.py` read | `verify_unit_evidence`, two-sided disposition enrichment |

## 3. Current Evidence

### 3.1 Three-tier grounding, confirmed present and unchanged in shape

`ground_spans` (`grounding.py:248-335`) grounds each LLM-cited quote against
source markdown/text in model-output order, in three tiers: (1) an exact
tier via a monotonic dynamic-program port of langextract's `resolver.py`
(`_select_monotonic_matches`, lines 147-213, credited "Copyright Google
LLC, Apache-2.0" in the module docstring, lines 14-21), which maps repeated
quote phrases to successive non-overlapping token-sequence occurrences
rather than always the first substring hit, and yields a concrete
`(start, end)` char interval verified by a post-alignment guard
(`normalized_text(markdown[start:end]) == norm_quote`, line 309); (2) a
fuzzy-substring tier, normalized quote as a substring of normalized
markdown with no locatable interval (line 324); (3) a fuzzy-ratio tier,
rapidfuzz `partial_ratio` at or above `EVIDENCE_FUZZY_FLOOR`, gated to
quotes of at least `EVIDENCE_MIN_FUZZY_CHARS` (lines 326-330), the guard
against a short generic phrase clearing a whole-document ratio comparison.
A quote failing all three tiers is dropped (`dropped` count incremented,
never silently kept, line 333).

### 3.2 Semantic parity is a stricter, separate check layered on the exact tier

`semantic_parity_holds` (`grounding.py:225-245`) requires the quote's word
tokens AND its full Unicode punctuation/symbol sequence
(`_semantic_punctuation_signature`, lines 216-222, every code point whose
Unicode category starts with `P` or `S`, in source order) to match the
candidate slice exactly. An exact-tier hit that fails this check is
downgraded from `GROUND_EXACT` to `GROUND_FUZZY` (lines 314-320): the token
match located the right words, but the punctuation sequence around them
differs. This is the mechanism by which the grounding pipeline COULD, in
principle, distinguish `<memory_resource>` from `<memory_resource<`: the
word token `memory_resource` matches, but the punctuation signature (`<`,
`>` vs. `<`, `<`) would not. Whether this mechanism actually fires for C4
is addressed in 3.5.

### 3.3 Candidate classification is deliberately asymmetric with source grounding

`classify_candidate_evidence` (`grounding.py:419-585`) takes quotes already
grounded against the SOURCE and re-grounds them against the CANDIDATE, with
an explicit asymmetry documented in its own docstring (lines 425-428): "An
exact candidate hit refutes a missing claim only when semantic operators
survive in the raw interval. Fuzzy or sanctioned-format matches abstain. A
miss is reported as `candidate_not_found` rather than overstated as proven
absence." The function walks a specific precedence order per quote: (1)
exact grounding with parity, `CANDIDATE_PRESENT` (lines 466-485); (2) a
presentation-neutral surface match with non-overlapping interval
consumption, `CANDIDATE_PRESENT` (lines 487-504); (3) a canonical-metadata
case-insensitive match for the YAML `intent` field only, `CANDIDATE_PRESENT`
(lines 506-519); (4) a case-folded surface substring match without interval
consumption, `CANDIDATE_AMBIGUOUS` (lines 521-532); (5) any other fuzzy
candidate hit, `CANDIDATE_AMBIGUOUS` (lines 534-543); (6) a set of sanctioned
patterns (front-matter labels, TOC markers, page furniture, running
headers, TOC-entry-with-page-number, table-token subset, math-folded
substring), `CANDIDATE_AMBIGUOUS` if matched, else `CANDIDATE_NOT_FOUND`
(lines 545-583).

### 3.4 The router is lane-local and never reads deterministic artifacts

`route_pdf_units` and `route_html_units` (`source_router.py:167-268`,
`271-370`) operate purely on `page_units`/`section_units` (source-derived)
and `candidate_md`; the module docstring states this explicitly: "The
router compares source packets directly with candidate Markdown. It never
reads deterministic whisker artifacts and never emits a conversion
verdict" (lines 10-11). Five signal types are computed: `token_delta`
(a fixed C++ keyword list's count deficit, lines 184-207), `low_recall`
(`content_recall` per unit below `PAGE_RECALL_FLOOR`/`SECTION_RECALL_FLOOR`,
lines 209-222, 342-354), `missing_captions` (lines 224-234), `heading_drift`
(lines 236-258 for PDF, 296-327 for HTML), and `table_presence`/
`missing_code` (lines 260-266, 356-368). None of these emits a verdict;
they feed `run_unit_checks`'s scoped LLM calls (traced in C17 §3.7).

### 3.5 C4's corruption is invisible to the router for two independent reasons

`_CPP_KEYWORDS` (`source_router.py:45-48`) is `("constexpr", "template",
"struct", "class", "enum", "auto", "concept", "requires", "noexcept",
"void", "int", "float", "double", "char")`. `memory_resource` is not a
member of this tuple, so the `token_delta` signal (the only signal in
`route_pdf_units` that inspects specific keyword identity rather than
recall/structure) cannot fire for this corruption regardless of what
happened to the token. Independently, per C15 §3.1, `_WORD_RE` in
`source_router.py:49` is `re.compile(r"\b\w+\b", re.UNICODE)`, the same
`\w`-only family as `grounding.py`'s own `_TOKEN_RE` (line 54); even a
tracked keyword's word-token form would be unaffected by an angle-bracket
mangle. This is the same construct-level blindness identified in C15,
independently confirmed in the router's own tokenizer, not a second,
different bug. `semantic_parity_holds`'s punctuation-signature check (3.2)
is the one mechanism in this codebase that COULD see the `<` vs. `<`
difference, but it only runs on quotes the LLM actually cites as evidence
spans; per ledger E18, the LLM's own reasoning for C4 was byte-identical to
the control, meaning no evidence span naming `memory_resource` was ever
generated for grounding to check. The grounding pipeline's capability is
therefore never exercised for this corruption, not because the pipeline
itself is blind, but because the upstream signal that would trigger a
citation never fired.

### 3.6 The metadata check's own scope explains its C2 vote, read through the grounding-adjacent lens

Per C17 §3.4-3.6, the metadata/outline check for C2 (section reversal)
returned `verdict: "pass"` with reasoning naming the reversal explicitly
but judging it out of scope for its own rubric (heading levels, field
values, section presence, per `METADATA_CHECK_SYSTEM_PROMPT`, `unit_judge.
py:131-144`). This is not a grounding failure: the check is not
grounding-mediated at all (it is a direct LLM judgment over structured
packets, `compare_metadata_outline`/`run_metadata_outline_check`, not an
`EvidenceSpan`-based claim subject to `ground_spans`). It is included here
because `_source_aware_requires_review` (the router-adjacent fusion
predicate traced in C17) is gated on this check's verdict, and its scope
boundary is therefore load-bearing for what the fusion layer treats as
"source-aware evidence of a problem."

### 3.7 Unit-check evidence is two-sided by the same grounding primitives

`verify_unit_evidence` (`unit_judge.py:747-819`) applies the identical
source-then-candidate grounding sequence to every unit-check defect's
`source_quote`: ground against the unit's own source text
(`ground_spans`, line 779), demote `GROUND_EXACT` to fuzzy if semantic
parity fails against the source slice itself (lines 789-793), then classify
against the full candidate markdown (`classify_candidate_evidence`, line
794). A defect whose quote is too short (`< 5` chars, lines 769-770) or
fails to ground against its own claimed source unit is marked `source_
ungrounded` and excluded from `verified_defects` in `run_unit_checks`
(`unit_judge.py:504-508`: only `CANDIDATE_NOT_FOUND` status with `source_
status == GROUND_EXACT` counts as verified). This is the same two-sided
discipline as the monolith judge's missing-content quotes (3.1-3.3),
applied at unit-check granularity.

### 3.8 The count-verification layer is a second, independent evidence class

`verify_defect_counts` (`unit_judge.py:670-726`) is not part of the
grounding pipeline; it is a purely mechanical word-count comparison
(`_mechanical_count`, lines 614-616) restricted to a fixed set of
`_COUNTABLE_KEYWORDS` (line 604-608: `constexpr, template, noexcept,
concept, requires, override, virtual, explicit, inline, static, volatile,
mutable, extern, register`), a different and non-overlapping list from
`source_router.py`'s `_CPP_KEYWORDS`. `memory_resource` is absent from this
list too, for the same reason as 3.5: it is not a qualifier keyword these
functions were built to track. When a `verified_delta` of `0` coincides
with `exact_location_verified` being true, the group's status flips to
`unverified` with a `location_conflict` flag (lines 709-713) rather than
asserting a false positive, an explicit hedge against the mechanical count
and the LLM's located quote disagreeing.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---|---|---|
| F1 | The three-tier grounding pipeline (exact monotonic DP, fuzzy substring, fuzzy ratio) and its semantic-parity downgrade are confirmed present and structurally unchanged; every quote either grounds at a specific tier or is counted as dropped, never silently accepted | INFO | HIGH |
| F2 | `classify_candidate_evidence`'s asymmetry (exact-with-parity or consumed-surface match required for `CANDIDATE_PRESENT`; everything else is `AMBIGUOUS` or `NOT_FOUND`) means a candidate re-appearance of a quote is deliberately never treated as stronger proof of absence than the source grounding already established | INFO | HIGH |
| F3 | `source_router.py`'s `_CPP_KEYWORDS` list and `unit_judge.py`'s `_COUNTABLE_KEYWORDS` list are both fixed, non-overlapping keyword sets that exclude `memory_resource`; the router and the mechanical count-verifier share the metrics surface's `\w`-token blindness identified in C15 independently, not derivatively | HIGH | HIGH |
| F4 | `semantic_parity_holds`'s punctuation-signature check is the one mechanism in the codebase capable of distinguishing C4's specific corruption class, but per E18 no evidence span naming the corrupted identifier was ever generated by the LLM, so this capability was not exercised for C4 | MEDIUM | HIGH |
| F5 | The metadata/outline check that gates `_source_aware_requires_review` (C17) is not grounding-mediated; its C2 vote is a scope boundary of its own rubric (heading level, field values, section presence), not a grounding pipeline failure | INFO | HIGH |
| F6 | Unit-check evidence and mechanical count-verification apply the same two-sided source-then-candidate discipline as the monolith judge, at finer (unit) granularity, and explicitly flag mechanical-count/LLM-location disagreement rather than silently picking one | INFO | HIGH |

## 5. False-Pass Hypothesis

**Could the grounding pipeline be mistaken for a general corruption
detector because it correctly rejects hallucinated quotes?** The pipeline's
job, per its own docstring, is narrower: verify that a QUOTE THE LLM ALREADY
PRODUCED is locatable in source and then in candidate. It has no mechanism
to generate a quote the LLM never produced. F4 states this precisely: the
one sub-mechanism (`semantic_parity_holds`) that could distinguish C4's
corruption never ran, because the upstream signal (an LLM-generated
evidence span naming the corrupted text) never existed. A reader crediting
the grounding pipeline with catching C4-class corruption would be
attributing a capability to a stage that was never invoked for this input.

**Could the router's fixed keyword lists give a false sense of C++-specific
coverage?** The lists (`_CPP_KEYWORDS`, `_COUNTABLE_KEYWORDS`) cover common
core-language keywords (`constexpr`, `template`, `noexcept`, etc.) but are
demonstrably not exhaustive of the C++ standard library vocabulary
(`memory_resource` is a standard library type name, absent from both
lists). Any corruption touching an identifier outside these fixed lists is
outside what `token_delta` or mechanical count-verification can flag, by
construction, independent of threshold placement.

## 6. Gate/Dimension Mapping (PROPOSED)

| Gate | Dimension | Status (PROPOSED) |
|---|---|---|
| G5: LLM lane authenticity | Two-sided evidence grounding (exact/fuzzy tiers, semantic parity) | PROPOSED SOUND for cited evidence spans (F1, F2) |
| G5: LLM lane authenticity | Router keyword-based signal coverage | PROPOSED BOUNDED to fixed, non-exhaustive keyword lists (F3) |
| G5: LLM lane authenticity | Grounding coverage of non-cited corruption | PROPOSED OUT OF SCOPE by construction (F4): grounding only verifies claims that exist |

## 7. Limitations

- F4's claim that "no evidence span naming the corrupted identifier was
  generated" rests on the ledger's report of byte-identical LLM reasoning
  for C4 (E18); this report did not independently inspect a raw sidecar's
  `missing_content` or `evidence_verification` list for the C4 run to
  directly confirm the absence of any `memory_resource`-adjacent span.
- The keyword-list gap (F3) is demonstrated for exactly one identifier
  (`memory_resource`); this report does not enumerate the full C++ standard
  library vocabulary against either fixed list to quantify total coverage.
- `route_html_units`'s heading-drift and recall logic (3.4) was read but
  not exercised against any HTML-source live evidence in this pass; all
  live canary and stress evidence in the ledger is PDF-sourced.
- Per 00-PRECONDITIONS.md §1, this is a working-tree audit; line numbers
  match the file as read this pass.

## 8. Conclusion

The grounding pipeline (`grounding.py`) and the source-aware risk router
(`source_router.py`) are, on this reading, functioning exactly as their own
definitions specify: a three-tier, order-preserving, drop-on-failure
grounding scheme for LLM-cited quotes, a deliberately asymmetric candidate
classification that never overstates absence, and a lane-local router that
computes source-vs-candidate deltas without touching deterministic
artifacts. Where this machinery cannot see a corruption, the cause is
traceable to one of two independent, structurally distinct facts: the
router's keyword lists are fixed and do not cover every identifier that
matters (`memory_resource` absent from both `_CPP_KEYWORDS` and
`_COUNTABLE_KEYWORDS`), and the grounding pipeline's one mechanism that
could distinguish a punctuation-level corruption (`semantic_parity_holds`)
never runs unless the LLM first generates a citation naming the affected
text, which for C4 it did not. Neither is a defect in the grounding logic
relative to its own contract; both are boundary conditions of what
"grounding a claim" and "routing on tracked keywords" can mean when no
claim exists to ground and no keyword is tracked. No verdict is rendered on
whether these boundaries are acceptable; they are reported precisely for
synthesis.

## 9. Delta vs Auditv2

Auditv2's C18 (HEAD 51cb704, no live LLM lane) described three-tier
grounding, page-scoped grounding, quote sanitization, candidate
classification, PDF/HTML source routing, unit-check caps, and the
ungrounded-demotion rule entirely from static code reading. This report
confirms that structural description is unchanged in shape (3.1-3.4, 3.7)
and adds one live-evidence-grounded finding Auditv2's code-only pass could
not produce: that the router's specific fixed keyword lists have a concrete
gap (`memory_resource`, F3) demonstrated by an actual canary run, not
inferred abstractly from reading a list of fourteen keywords and noting it
is "fixed." It further adds a precise account (F4) of WHY the one grounding
mechanism theoretically capable of catching a punctuation-level corruption
(`semantic_parity_holds`) did not engage for C4: the mechanism is
downstream of an LLM-generated citation that never existed for this input,
a causal chain only visible once a real model run against a real
corruption was available. Auditv2 had no live canary evidence and so could
only describe the parity check's existence and design intent, not observe
a case where it was structurally unreachable.
