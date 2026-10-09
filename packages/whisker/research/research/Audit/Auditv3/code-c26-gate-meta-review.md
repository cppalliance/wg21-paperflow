# C26 Gate Meta-Review

**Role**: Adversarially re-examine whether the audit's own gates (Auditv2's
G1-G7 self-gates over the system) and whisker's own structural gates
(`gates.py`) are well-formed, given evidence unavailable to Auditv2: a live
LLM lane and a currently-red test suite.
**Audited state**: whisker 0.5.0, working tree, manifest
b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771
**Gates**: G1 (Advisory non-leakage), G5 (Untrusted-input mediation) re-tested
here with live evidence; `gates.py` structural gates (`no_toc_leak`,
`heading_monotone`) and the score-pinning tripwire assessed for
well-formedness. All PROPOSED.

## 1. Scope

Two questions, both meta: (a) do Auditv2's audit-level gates (G1-G7) still
hold now that runtime evidence exists where Auditv2 had none, and (b) are
whisker's own hard gates (the ones that decide `pass`/`review`/`fail`)
internally well-formed, i.e. free of logic gaps, silently-swallowed signals,
or an untrustworthy tripwire. This report does not repeat G4, G6, G7 from
Auditv2 (per that report, they require no runtime proof and are unaffected
by anything in this ledger); it focuses on G1 and G5, which Auditv2 left
PASS-PROVISIONAL specifically because no runtime evidence existed, plus a new
question Auditv2 never asked: is the gate mechanism itself (the pinning
suite) currently trustworthy.

## 2. Commands and Exits

```
uv run --package whisker pytest packages/whisker/tests -q --tb=line   (E1)
```
Live LLM lane: `rt2_llm_matrix.py`, `rt3_stress.py`, `rt4_canaries.py`,
`rt7_repeat.py` (E13-E20). Exit codes and outputs recorded in the shared
ledger, not re-run here.

## 3. Current Evidence

### 3.1 G1 (Advisory non-leakage), re-tested with live data

Auditv2 (its `code-c26-gate-meta-review.md`, G1) rated this PASS-PROVISIONAL:
structural proof was strong (import absence, frozen `advisory` field,
asymmetric fusion rules) but "the full vector... has never been exercised
end-to-end with a live endpoint." That vector has now run.

- **E16** (the RESCUE case): a deterministic `fail` (hard flag
  `gate:heading_monotone`) reaches the LLM, which returns `review` at
  confidence 0.98. Fusion rule `llm_rescue_heading` fires, the combined
  verdict caps at `review` (not `pass`), and the deterministic exit code
  after the LLM ran is still `5`. This is exactly the proof Auditv2 could not
  obtain: a live adversarial-shaped input, a live rescue vote, and the gate
  held.
- **E15** (prompt injection): two injection variants, both demanding
  `verdict: "pass", confidence: 1.0`, produced `review` in both cases, never
  `pass`. The demanded verdict was not produced. Non-leakage holds under a
  live, explicit injection attempt.
- **E19** (new defect, invisible to code inspection): a section-reversal
  canary (C2) fused to `pass` even though the LLM's own primary judge said
  `review` and its reasoning explicitly named the reordering as failing
  ("This structural corruption constitutes substantial reordering, failing
  the conversion"). Tracing `fusion.py:182` shows the demotion depends on the
  metadata/outline check separately voting `pass`, which it did for C2
  ("Candidate headings are in reverse order... but all source sections are
  present"). When that check does not also flag, `fusion.py:538`'s rule
  `FUSION_RULE_AGREE if det == llm else FUSION_RULE_WHISKER_ONLY` fires and
  the primary judge's `review` is silently dropped from the combined
  advisory verdict.

E19 does **not** breach G1 as Auditv2 defined it: `advisory` stays `True`,
the exit code is unaffected, and `score.py` never sees any of this (the gate
that matters for CI is untouched). But it is a defect in the merged advisory
**report**, the artifact a human reads, and it is a defect that only live
evidence could surface: `test_fusion.py`'s hand-constructed dicts (per
Auditv2's own G1 challenge, "the offline tests cover the function, not real
LLM output written to disk and read back") do not include a case where two
independently-voting sub-checks disagree in exactly this pattern.

### 3.2 G5 (Untrusted-input mediation), re-tested with live data

Auditv2 rated this PASS-PROVISIONAL and specifically flagged: "Whether a real
model obeys the guard instruction... is a property of the model, not the
code. You cannot mock this." E15's two live variants (instruction injection,
delimiter forgery) both failed to produce the demanded output. This is
runtime confirmation of the specific behavioral claim Auditv2 could not test.
One caveat travels with it: both injected variants reported confidence
exactly 1.0, matching the demanded value, but so did the unrelated
adversarial control (S5, no injection present). One coincidence across three
samples is not enough to accuse the confidence field of anything; it is
enough to flag that confidence should not yet be trusted as an
injection-detection signal.

### 3.3 Are `gates.py`'s own structural gates well-formed?

`packages/whisker/src/whisker/CLAUDE.md:869-882` (Known gaps, unchanged
section header, current as of this audit) documents two of the gate module's
own hard gates as imperfect by the project's own admission:

- `no_toc_leak` is "under- and over-inclusive": dot-leader TOCs, roman
  numerals, and non-English "Inhaltsverzeichnis" pass undetected;
  conversely, a legitimate `## Table of Contents` heading can hard-fail.
- `heading_monotone` accounts for 64% of reference-free hard-fails
  (documented figure, not re-measured here); the RESCUE path (S 3.1, E16) is
  the project's own acknowledged escape valve for this gate's
  over-triggering.

Both are pre-existing, self-reported limitations, not new findings. They are
included here because "is the gate well-formed" cannot be answered honestly
without citing the project's own admission that two of its hard gates are
known to misfire in both directions.

### 3.4 Is the gate mechanism itself (score pinning) trustworthy right now?

E1: `test_score_pinning.py::test_score_pinned` fails for `p3556r0` ("gate
mismatch") and `p2040r0` ("max_heading_level mismatch: actual=3,
expected=4"). This suite exists specifically to catch unannounced changes to
gate output or structural metrics (`CLAUDE.md:879-881`: "Pinning baseline has
no CI guard against silent gate additions. Fixed in this batch (A2)...").
`p2040r0` is a paper the pinning fixture itself already flags as a known
false-gate case (`_EXPECTED_GATE_FAILURES = {"p2040r0": {"heading_monotone"}}`,
`packages/whisker/tests/test_score_pinning.py:153-158`); its
`max_heading_level` reading dropping from 4 to 3 means the golden ideal file
backing this fixture changed structurally after the baseline was committed,
and nobody re-baselined. The mechanism designed to catch exactly this kind of
drift is, at the moment of this audit, the thing that is red.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---|---|---|
| F1 | G1 (advisory non-leakage) now has live-endpoint confirmation (E15, E16); Auditv2's specific evidentiary gap is closed | Informational | HIGH |
| F2 | New defect found only by live testing: `whisker_only` fusion can silently drop a primary judge's `review` to a fused `pass` when the metadata/outline sub-check disagrees (E19) | Medium | HIGH |
| F3 | G5 (prompt-injection resistance) now has live confirmation against two adversarial variants (E15) | Informational | HIGH |
| F4 | Confidence=1.0 was reported for both injected variants and one unrelated adversarial control; too few samples to trust confidence as an injection signal | Low | MEDIUM |
| F5 | Two of `gates.py`'s hard gates are self-documented as under/over-inclusive (`no_toc_leak`, `heading_monotone`); this is a pre-existing, acknowledged limitation, not new | Informational | HIGH |
| F6 | The score-pinning tripwire, whose job is to catch exactly this kind of drift, is itself failing on 2 papers right now | High | HIGH |

## 5. False-Pass Hypothesis

**Could E19's fusion-demotion defect actually be silently affecting the hard
gate, not just the advisory report?** No. `score.py`'s `_decide()` (verbatim
in `raw/w4-doctrine-quotes.md` section 4) never reads any tapetum field; the
hard/soft flags are computed entirely from `gates`, `unigram_coverage`,
`unigram_drift`, region counts, `qa_score`, `uncertain_count`, and the
optional `ref`/`ideal` panels. The LLM lane's own module docstring
(`CLAUDE.md:551-564`) states the lane "never overwrites the whisker verdict
on record." F2 is confined to the merged advisory artifact.

**Could the pinning failures (F6) be a fixture bug rather than a real
drift?** `p2040r0`'s failure is specific and numeric (`max_heading_level
mismatch: actual=3, expected=4`), not a generic parse error, which is
consistent with an actual structural change to the golden ideal file, not a
test harness defect. `p3556r0`'s failure ("gate mismatch") is less specific
from the traceback alone; this report cannot rule out a fixture-side cause
for that one paper without inspecting its specific gate diff, which is out of
scope here (see C28 for the engineering-process framing of this same
evidence).

## 6. Gate/Dimension Mapping (PROPOSED)

- **G1 (Advisory non-leakage): PROPOSED PASS.** Upgraded from Auditv2's
  PASS-PROVISIONAL. The specific vector Auditv2 could not test (live
  adversarial output through the full disk-write/fusion-read chain) has now
  run and held for the CI-relevant boundary (exit codes, `score.py`).
- **G5 (Untrusted-input mediation): PROPOSED PASS-PROVISIONAL, upgraded from
  Auditv2's PASS-PROVISIONAL but not to full PASS.** Two live probes held;
  two probes on one paper is not exhaustive coverage of "sophisticated
  prompt injection" (Auditv2's own stated bar).
- **Structural gate well-formedness (new, no Auditv2 predecessor): PROPOSED
  PASS-PROVISIONAL.** The gates are self-documented as imperfect by the
  project, with a stated escape valve (RESCUE), which is a defensible
  engineering posture, not a defect being hidden.
- **Gate-mechanism trustworthiness (new, no Auditv2 predecessor): PROPOSED
  FAIL-UNPROVEN.** A tripwire that is currently tripped by its own drift, not
  by an external regression it was built to catch, cannot be relied on to
  certify "no unannounced gate changes" for this audited state.

## 7. Limitations

- E19's mechanism trace is code-level (`fusion.py:182`, `:538`) matched
  against the observed C2 sidecar fields; it was not independently
  re-executed against a second document to rule out a document-specific
  coincidence.
- This report did not diff `p3556r0`'s specific gate list before/after to
  characterize F6's second failure precisely; only the pytest assertion text
  is cited.
- Whether Auditv2's `no_toc_leak`/`heading_monotone` known-gaps text is
  byte-identical to the version Auditv2 audited was not verified; only that
  the current `CLAUDE.md` states these gaps as of its own dated header
  ("as of 2026-07-22").

## 8. Conclusion

The live LLM lane closes Auditv2's two most consequential evidentiary gaps
(G1, G5) for the boundary that actually matters, the deterministic exit code.
But running the runtime scenarios did not just confirm what Auditv2
suspected; it surfaced a genuinely new defect (E19's silent review-to-pass
drop in the merged advisory report) that no amount of code inspection would
have found, because it depends on the specific interaction of two live
sub-checks disagreeing. Separately, and independently of any LLM evidence,
the audit finds that the mechanism responsible for proving "no unannounced
gate drift" is itself drifted and red. A gate meta-review that only asked
"did the live scenarios pass" would miss this; a gate meta-review that only
asked "is the pinning suite green" would miss E19. Both are load-bearing for
whether the gates, as a system, can be trusted right now.

## 9. Delta vs Auditv2

Auditv2's `code-c26-gate-meta-review.md` covered seven gates (G1-G7) entirely
by code inspection and offline mocked tests, because zero of the ten runtime
scenarios in its own matrix had run (`ALLIANCE_POD_KEY` unset). Its own
verdict table rated G1 and G5 PASS-PROVISIONAL specifically because of that
absence, and its "Recommendations for C30" section explicitly told future
audits not to upgrade those verdicts without runtime evidence.

This report is the first to have that evidence. It upgrades G1 to PASS on
the strength of E15/E16, keeps G5 at PASS-PROVISIONAL (narrower coverage than
"upgrade to PASS" would require), and in the process of exercising the live
lane, finds a defect (E19) that did not exist as a question in Auditv2's
scope at all: Auditv2's G1 challenge anticipated "a corrupted or
maliciously-placed sidecar" as the residual risk, not "two legitimate,
non-adversarial sub-checks disagreeing in a way that drops signal." The
score-pinning red state (F6) is entirely new: Auditv2's suite was fully green
(1406 passed, 0 failed), so Auditv2 had no basis to ask whether the tripwire
itself was trustworthy. This audit's suite is red specifically inside that
tripwire, which makes the question unavoidable here in a way it was not for
Auditv2.
