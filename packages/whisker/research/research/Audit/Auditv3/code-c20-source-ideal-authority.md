# C20 Source-Aware and Ideal Authority

**Role**: Audit which artifact is authority when source, ideal, and candidate disagree, and how the deterministic and advisory lanes each encode that authority.
**Audited state**: whisker 0.5.0, working tree, manifest b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771
**Gates**: G4 (Per-axis + eval integrity), D5 (Anti-gaming / Goodhart: golden-ideal provenance)

## 1. Scope

Three artifacts, three authority claims: the source (PDF/HTML) is declared
factual authority; the human-blessed ideal is declared structural
authority; the candidate markdown is what is being judged against both.
This file verifies the authority hierarchy in code (unchanged from
Auditv2's scope) and then adds what Auditv2 could not test: whether the
source-vs-candidate axis and the ideal-vs-candidate axis actually agree
when a document is reordered, since one is order-invariant by design and
the other is not.

## 2. Commands and Exits

```
E1:  uv run --package whisker pytest packages/whisker/tests -q --tb=line -> 3 failed, 1784 passed (exit 1)
E17: rt4_canaries.py, 4 mutations of one base ideal document, against the live pod
```

No dedicated live ideal-verifier run exists in this audit's matrix; ideal
authority is verified by code inspection (unchanged from Auditv2) plus the
order-sensitivity analysis in 3.5-3.6, which is new this run and grounded
in live canary evidence (E17) even though the canary harness itself was
not built to test ideal authority specifically.

## 3. Current Evidence

### 3.1 Ideal location and read-only consumption (unchanged from Auditv2)

`_IDEALS_RELPATH` (`golden_ideals.py:51`) points to
`packages/tomd/tests/fixtures/golden/ideals/`. Ideals live only there;
whisker discovers them by walking up the directory tree
(`find_ideals_dir`, `golden_ideals.py:73-91`) and never writes: "Pure
functions; the module never writes. Callers persist." (`golden_ideals.py:29`).
No mutation call (`write`, `mkdir`, `open(..., "w")`) exists in the module.
This is unchanged from Auditv2's C20 §3.1-3.2 and §3.8; not re-derived
independently beyond confirming the same line numbers still hold.

### 3.2 Source declared factual authority, ideal declared structural authority

`ideal_verify.py:26-30` (system prompt, unchanged text from Auditv2):

```26:30:packages/whisker/src/whisker/tapetum_llm/ideal_verify.py
IDEAL_VERIFY_SYSTEM_PROMPT = (
    "You are an ideal-aware conversion verifier. The source remains the "
    "highest authority for factual content. The ideal is human-blessed "
    "STRUCTURAL ground truth for how that source should be represented in "
    "Markdown.\n\n"
```

`golden_ideals.py:114-134` (`score_against_ideal` docstring): "an ideal is
a hand-corrected version of the same conversion, so reading order matches
by construction," which is the load-bearing assumption 3.5 below tests.

### 3.3 Ideal verdict remains demotion-only in both lanes (unchanged from Auditv2)

Deterministic: `score.py:205-215`, every ideal axis reaches `soft.append`
only; no `hard.append` in the `ideal is not None` block. Fusion:
`ideal_review_cap` (`constants.py:138` per Auditv2 citation, not
re-verified at that exact line this run but consistent with `fusion.py`'s
review-cap rule family traced in C21) caps a non-fail combined verdict at
`review` when the ideal verifier disagrees; there is no code path where
`ideal_verdict == "agree"` promotes anything. This authority shape is
unchanged from Auditv2's F3/F4.

### 3.4 Ideal verifier grounding is exact, not fuzzy (unchanged from Auditv2)

`_require_raw_exact_evidence` (`ideal_verify.py:114-131`) calls
`_require_raw_exact_quotes` (`ideal_verify.py:97-111`) against both the
candidate and the ideal separately; any discrepancy whose quote cannot be
found verbatim (non-overlapping, per-quote, `document.find` walk) raises
`IdealVerificationError`, failing the run rather than emitting a partial
discrepancy list. This is stricter than the main grounding tiers used
elsewhere in the pipeline (no fuzzy tier here at all) and is unchanged
from Auditv2's F5.

### 3.5 The order-sensitivity split: one hard axis is blind to reordering, one soft axis is not

`unigram_coverage` (`score.py:65`), the sole metric feeding the HARD gate
(`score.py:181-186`, the only two `hard.append` sites are the gate loop
and this edge per C02 §3.2), is documented at its own definition site as
"order-invariant token-set" comparison (`score.py:149`). A document whose
sections are reversed or reordered without deleting content changes zero
tokens in the multiset, so `unigram_coverage` is unaffected by
construction, not by omission.

`ref_nid` (`score.py:83`, `score.py:266-276`), the deterministic lane's
OWN source-vs-candidate comparison (computed as `text_nid(normalized_
text(md_text), normalized_text(reference_md))`, `score.py:272`), is the
same whole-document, order-SENSITIVE `text_nid` function `golden_ideals.
score_against_ideal` uses for the ideal-vs-candidate axis
(`golden_ideals.py:135`). `ref_nid` is advisory-only: "low `ref_nid`
agreement is layered on as an ADVISORY soft signal only" (`score.py:162`),
triggering `soft.append(f"reference text agreement {ref_nid:.3f} low
(advisory)")` (`score.py:203`) below `REF_NID_ADVISORY_EDGE`.

This means the deterministic lane, by its own two-axis design, is
structurally set up to produce EXACTLY the disagreement the task
description describes: an order-invariant HARD axis (`unigram_coverage`)
that a reordering canary cannot move, sitting next to an order-sensitive
SOFT axis (`ref_nid`, or the ideal's `nid` via `score_against_ideal`) that
the same reordering would move substantially, because whole-document
`text_nid` is edit-distance-based and reordering large spans is expensive
in edit-distance terms.

### 3.6 Live grounding: E17 C2 shows the hard-axis half of this split; the soft-axis half is not independently confirmed live

E17's C2 canary (reverse section order, per ledger and per C08 §3.2) shows
`unigram_coverage` unchanged from the control (matches 3.5's prediction:
an order-invariant metric cannot see reordering). The live LLM verdict for
C2 was `review` at confidence 0.95, describing the mutation directly:
"sections 4.2-4.7 appear before 4.1... This structural corruption
constitutes substantial reordering, failing the conversion" (per C08
§3.2, ledger E17-E19). The fused `combined_verdict` for C2 came out
`pass` (E19), via the fusion path traced in C21 (`fusion.py:182`,
`fusion.py:538`), not via the ideal or `ref_nid` soft-flag path.

This audit's ledger does not record whether the C2 canary run populated
`ref_nid` or an ideal comparison at all: `rt4_canaries.py` mutates one base
document and scores it, but whether it wires a `reference_md` (source
markdown) or an ideal panel into that scoring call was not traced this
run. The precise three-way disagreement the task frames (source-vs-
candidate axis says fine, ideal-vs-candidate axis says structural
problem) is therefore CONFIRMED AS A CODE-LEVEL MECHANISM (3.5, two
functions with opposite order-sensitivity, both live in `score.py` and
`golden_ideals.py` today) but NOT independently confirmed as a live
NUMERICAL disagreement on the C2 canary specifically, because this audit
did not verify `ref_nid` or ideal fields were populated and nonzero-low on
that run. What IS confirmed live is the weaker, adjacent fact already
established in C08/C21: the deterministic hard axis (`unigram_coverage`)
passed while the LLM's independent structural read said `review`, and the
mechanism that discarded the LLM's read is a fusion rule
(`FUSION_RULE_WHISKER_ONLY`), not a source/ideal-authority rule.

### 3.7 Ideal fingerprinting and no ideal copies (unchanged from Auditv2)

Not independently re-traced this run beyond the file locations confirmed
in 3.1; Auditv2's F6 (incremental fingerprints include ideal presence,
`tapetum_llm.md:86-89` per that audit's citation) and F2/§3.8 (no ideal
duplicates under `packages/whisker/`) are carried forward as unverified-
this-run, not re-confirmed independently.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | Source-as-factual-authority and ideal-as-structural-authority remain declared identically in `ideal_verify.py`'s system prompt, unchanged from Auditv2 | Informational | HIGH |
| F2 | Ideal verdict remains demotion-only in both `score.py` and `fusion.py`; no promote/rescue path exists for ideal agreement | Informational | HIGH |
| F3 | The deterministic lane's own hard-gate metric (`unigram_coverage`) is order-invariant by explicit design; a reordering-only mutation cannot move it, regardless of severity | HIGH | HIGH |
| F4 | The deterministic lane's advisory `ref_nid` axis and the ideal-comparison `nid` axis use the identical order-sensitive whole-document `text_nid` function; both are structurally capable of flagging a reordering the hard gate cannot see, but neither can promote past `review` | MEDIUM | HIGH |
| F5 | This audit did not verify whether the live C2 reordering canary (E17-E19) populated `ref_nid` or an ideal panel; the source-vs-candidate/ideal-vs-candidate numerical disagreement is a confirmed code-level mechanism, not an independently confirmed live measurement on that specific canary | MEDIUM | MEDIUM |
| F6 | `golden_ideals.score_against_ideal`'s docstring assumption ("reading order matches by construction" because an ideal is hand-corrected from the same conversion) is an unverified premise; no test in this audit's ledger constructs an ideal that itself disagrees with the source on ordering | LOW | MEDIUM |

## 5. False-Pass Hypothesis

**Could the source-authority declaration be cosmetic, i.e. the ideal
silently outranks the source in practice?** No evidence found for this;
unchanged from Auditv2's F1/F2, both lanes remain demotion-only for ideal
signals (3.3), and the reordering-canary mechanism (3.5-3.6) shows the
LIMIT of the deterministic lane's ability to represent source authority is
an order-invariance BLIND SPOT in the hard gate, not a case of the ideal
overriding the source.

**Could a reader assume "the deterministic gate passed, so the source-
vs-candidate comparison found no structural problem" when in fact the
gate is mathematically incapable of seeing reordering at all?** This is
the sharper risk this file surfaces. `unigram_coverage`'s hard-gate role
combined with its documented order-invariance means a `pass` exit code
answers "is roughly the same set of tokens present" and nothing about
sequence. A human who does not separately read the `ref_nid` soft flag (or
an ideal panel, when one exists) has no way to learn from the exit code
alone that a severe reordering occurred. E17-E19's fusion outcome for C2
(`pass`, C21) is exactly this risk realized: the one signal that DID
describe the reordering (the LLM's `review`) was available and then
discarded by a fusion rule, leaving the human-facing summary silent on
the very defect an order-sensitive axis exists to catch.

## 6. Gate/Dimension Mapping (PROPOSED)

| Gate | Dimension | Proposed status |
|------|-----------|------------------|
| D5 Anti-gaming / Goodhart | Golden-ideal provenance, read-only consumption, demotion-only verdict | PROPOSED PASS (code-verified, unchanged from Auditv2) |
| G4 Per-axis + eval integrity | Order-sensitivity separation between hard gate (`unigram_coverage`) and soft axes (`ref_nid`, ideal `nid`) | PROPOSED gap: the separation is real and by design, but its practical effect (a reordering-blind hard gate) is not surfaced anywhere the exit code alone would reveal it |
| G4 Per-axis + eval integrity | Live verification that ideal/reference axes actually fire on the C2 reordering canary | PROPOSED unresolved: not independently traced this run (F5) |

## 7. Limitations

- Whether `rt4_canaries.py` populates `reference_md` or an ideal panel for
  its mutated documents was not traced; F5's hedge follows directly from
  this gap and is not resolved in this file.
- The `score_against_ideal` docstring's "reading order matches by
  construction" premise (3.7, F6) is a design assumption about ideals
  being hand-corrections of the SAME conversion; it was not tested against
  an ideal that itself uses a different section order than its source,
  which this audit's corpus does not appear to contain evidence of either
  way.
- No live ideal-verifier run exists in this audit's matrix (E13-E20 are
  all PDF-lane or metadata/outline scenarios); the ideal-authority
  evidence in 3.1-3.4 is unchanged code inspection, same limitation
  Auditv2 recorded ("Cannot verify live ideal verifier behavior").
- The suite is RED (E1); no ideal-specific test is named among the 3
  failures, but this file does not independently confirm which named
  tests exercise `golden_ideals.py` or `ideal_verify.py` among the 1784
  passing.

## 8. Conclusion

The authority hierarchy Auditv2 verified by code inspection is unchanged:
the source is declared factual authority, the ideal is declared structural
authority only, and both the deterministic lane and fusion treat ideal
agreement as strictly demotion-only. This run adds a mechanism-level
explanation for why the source-vs-candidate axis and an ideal-vs-candidate
axis can numerically disagree on a permuted document: one is
order-invariant by explicit design (the hard gate), the other is
order-sensitive by construction (both `ref_nid` and the ideal `nid` share
the same `text_nid` function). E17's C2 canary demonstrates the
order-invariant half of that split live (the hard gate did not move under
reordering) and is consistent with, but does not independently confirm,
the order-sensitive half firing on that same run. The precise risk this
file surfaces is not that authority is inverted, but that the hard gate's
order-blindness is invisible from the exit code alone, and the one signal
in this run that did name the reordering (the LLM's `review`) was
subsequently discarded by an unrelated fusion rule, a finding this file
hands off to C21 rather than re-litigating.

## 9. Delta vs Auditv2

Auditv2's C20 verified the same authority hierarchy (source-declared,
ideal-declared-structural, demotion-only in both lanes, exact-quote
grounding) entirely by code inspection against a runtime-BLOCKED ledger,
concluding "No violations found" with an unqualified PASS mapping for its
D4/D1. Every one of Auditv2's six findings (ideal location, read-only
consumption, demotion-only verdict, clear-blocking soft flags, exact
grounding, fingerprint invalidation) is reaffirmed unchanged in 3.1-3.4 and
3.7 above; this file does not contradict any of them.

The delta is a new analytical layer Auditv2 had no live evidence to
support: the order-sensitivity split between `unigram_coverage` (hard,
order-invariant) and `ref_nid`/ideal `nid` (soft, order-sensitive), and its
live grounding via E17's C2 reordering canary. This is also where this
file's verdict becomes materially more qualified than Auditv2's flat
PASS: Auditv2 had no reordering canary and could not have surfaced F3-F5.
This file does not downgrade Auditv2's authority-hierarchy findings, but it
adds a boundary condition (order-blindness of the hard gate) that a reader
of Auditv2 alone would not know to look for.
