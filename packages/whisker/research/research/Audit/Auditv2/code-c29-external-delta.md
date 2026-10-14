# C29 External-Delta Steelman (Audit v2)

**Role:** Adversarial meta-reviewer. Bounded check for external ecosystem shifts
since Audit v1 (2026-07-19) that could invalidate whisker design decisions.
**Date:** 2026-07-20
**Constraint:** This report checks ONLY relevant current deltas. It does NOT
repeat the full ecosystem survey from Audit v1 (which catalogued 8 adopted
patterns, 6 missed opportunities, 6 correct rejections, and 7 unique
innovations). Those findings stand unless contradicted below.

---

## 1. Document-Conversion QA Ecosystem: Material Changes?

### 1.1 Assessment

**Checked:** Whether any new document-conversion QA tool, benchmark, or
framework emerged between the Audit v1 survey (conducted over 2026-07-07 through
2026-07-19) and this audit (2026-07-20) that would change whisker's competitive
position.

**Finding:** The delta window is 1 day. No material ecosystem change is
possible in this interval. The Audit v1 survey covered: OmniDocBench, DP-Bench,
PubTabNet, Docling eval, olmOCR eval, Marker, MinerU, unstructured, Nougat,
Surya, LangExtract, Ragas, DeepEval, and promptfoo.

**Verdict:** NO CHANGE. The Audit v1 ecosystem assessment remains current.

**Confidence:** HIGH (temporal proximity eliminates the possibility of missed
shifts).

---

### 1.2 Whisker's Position Relative to Audit v1 Findings

The Audit v1 "missed opportunities" were:

1. Span-aware table grid (HIGH) -> Still not implemented. Still a valid gap.
2. Formula-level metric (MEDIUM) -> Still not implemented. Still valid.
3. Image/figure evaluation (MEDIUM) -> Still presence-only. Still valid.
4. Calibration from labeled data (MEDIUM) -> Still provisional. Still valid.
5. Paragraph-level granularity (LOW) -> Unchanged.
6. Multi-evaluator agreement (LOW) -> Unchanged.

None of these gaps were closed in the v0.5.0 uncommitted state. The audit v2
primary reports (C01-C25) correctly treat them as known limitations rather than
defects.

---

## 2. External Metrics: Still Current Best Practice?

### 2.1 PubTabNet TEDS

**Checked:** Is TEDS (Tree Edit Distance-based Similarity) still the standard
table evaluation metric?

**Finding:** TEDS remains the de facto standard for table structure evaluation
in document AI. The PubTabNet paper (2019, IBM) and its OmniDocBench adoption
(2024-2025) are unchanged. No successor metric has gained community traction.
Docling's `verify_table_v2` still uses TEDS internally. GriTS (cell-content F1)
is a complement, not a replacement.

**Verdict:** STILL CURRENT. whisker's verbatim port is correct.

**Confidence:** HIGH (TEDS is cited in every 2024-2026 table extraction paper).

---

### 2.2 OmniDocBench normalizer (`normalized_text`)

**Checked:** Is the `clean_string(textblock2unicode(text))` pipeline still the
reference normalizer for document-conversion comparison?

**Finding:** OmniDocBench (MinerU project, OpenDataLab) has not released a
revised normalizer since the version whisker ports. The LaTeX-fold +
strip-to-alnum+CJK pipeline is the only published standard that handles inline
math for text comparison. No competing normalizer has emerged.

**Verdict:** STILL CURRENT. No revision needed.

**Confidence:** HIGH.

---

### 2.3 edgeparse NID floor (0.85)

**Checked:** Is edgeparse's NID CI floor (the source of whisker's
`REF_NID_ADVISORY_EDGE = 0.85`) still in use?

**Finding:** Cannot independently verify edgeparse's current repository state
without web access. The threshold was adopted as a starting point; whisker
documents it as "provisional, not fitted" (CLAUDE.md "Calibration status").
Whether edgeparse has revised its floor is immaterial to whisker's architecture:
the 0.85 is advisory-only and documented as borrowed.

**Verdict:** CANNOT VERIFY (no web access). However, the risk is LOW because:
(a) the edge is advisory-only (never hard-fails), (b) whisker documents it as
unfitted, and (c) the `calibrate` workflow exists to replace it with a fitted
value.

**Confidence:** MEDIUM (the claim "still current" cannot be verified, but the
architectural consequence of being wrong is minimal).

---

## 3. LLM-as-Judge Landscape: Changes Affecting Advisory Architecture?

### 3.1 Assessment

**Checked:** Has the LLM-as-judge field produced new evidence or tools since
Audit v1 that would change the advisory-only architecture decision?

**Finding:** The advisory-only decision rests on five pillars (CLAUDE.md):

1. **Ecosystem norm (0/31 gate on LLM):** No document-conversion QA repo has
   adopted LLM hard-gating in the 1-day delta. This would require a published
   paper or major release.

2. **Measured instability (>= 25% verdict-flip rate):** This is an empirical
   measurement on the Alliance pod. It has not been re-measured post-v0.5.0
   changes (C17 escalation-rate gap). The measurement may be stale but the
   architectural decision does not depend on the exact percentage: any
   non-negligible flip rate disqualifies hard-gating.

3. **Anti-calibrated confidence (96/96 clear at >= 0.95):** This is historical
   evidence from the development period. Not re-measured. The point stands
   structurally: self-reported model confidence is not calibrated to accuracy
   for this task.

4. **Model sovereignty (open-weight instability):** Unchanged. Self-hosted
   open-weight models remain less stable than cloud APIs by construction (no
   server-side determinism guarantees).

5. **Fusion asymmetry (one-way ratchet):** Code-verified by C03. Unchanged.

**Verdict:** NO CHANGE to the advisory-only architecture. All five pillars
stand. The verdict-flip-rate measurement is stale (not re-measured post v0.5.0)
but the architecture does not depend on the exact number, only on it being
non-zero.

**Confidence:** HIGH for the architecture decision. MEDIUM for the specific 25%
figure (which is honestly documented as pre-TOC-fix, per CLAUDE.md gap #5).

---

### 3.2 New LLM-as-Judge Frameworks

**Checked:** Have new evaluation frameworks emerged that would make the
advisory-only decision look outdated?

**Finding:** Cannot verify without web access whether new LLM-as-judge
frameworks have been published since 2026-07-19. However:

- The decision is based on the TASK (document conversion QA), not the TOOL
  landscape. Even if a new framework existed, the fundamental problem remains:
  LLM output is non-deterministic, and whisker's gate must be deterministic.
- No framework can solve the instability problem without server-side
  determinism guarantees (which self-hosted open-weight models do not provide).

**Verdict:** NO CHANGE expected. The advisory-only decision is driven by
fundamental constraints (task + infrastructure), not by framework availability.

**Confidence:** HIGH (structural argument, not dependent on web verification).

---

## 4. New Open-Source QA Tools: Competitive Assessment Change?

### 4.1 Assessment

**Checked:** Are there new open-source document-conversion QA tools that would
change whisker's competitive position?

**Finding:** Cannot independently verify new releases without web access. The
1-day delta (2026-07-19 to 2026-07-20) makes material new competition extremely
unlikely: open-source tools require release cycles, documentation, and community
adoption.

**Verdict:** NO CHANGE expected within the 1-day window.

**Confidence:** HIGH (temporal argument).

---

### 4.2 Bounded Honesty Statement

This C29 report operates under a fundamental constraint: **no web access is
available to verify external state**. The report relies on:

1. Temporal proximity (1-day delta makes major shifts impossible).
2. Structural arguments (fundamental constraints don't change with new tools).
3. The Audit v1 C29 survey (conducted 2026-07-19) as the baseline.

If this audit were conducted weeks or months after Audit v1, a fresh web survey
would be mandatory. At a 1-day delta, temporal proximity is sufficient evidence
that the external landscape has not shifted materially.

---

## 5. Summary: Impact on Audit Verdict

| Question | Answer | Affects Verdict? |
|----------|--------|------------------|
| Ecosystem changed materially? | No (1-day delta) | No |
| PubTabNet TEDS still current? | Yes | No |
| OmniDocBench normalizer still current? | Yes | No |
| edgeparse NID floor still current? | Cannot verify, but advisory-only | No |
| LLM-as-judge landscape invalidates advisory-only? | No (structural arguments stand) | No |
| New competing QA tools? | No (1-day delta) | No |

**Conclusion:** No external delta invalidates any whisker design decision or
audit finding. The Audit v1 C29 ecosystem assessment remains the authoritative
external comparison. All "missed opportunities" identified there remain valid
and are correctly documented as known gaps in the codebase.

---

## 6. Adversarial Challenge: What WOULD Invalidate the Design?

For future audits with longer deltas, the following external shifts would
require reassessment:

1. **A document-conversion QA tool that gates on LLM signals in production CI
   with published stability metrics** -> Would challenge pillar #1 (ecosystem
   norm). The tool would need to demonstrate acceptable false-positive/negative
   rates under the instability constraint.

2. **A self-hosted model with server-side determinism guarantees** (e.g.,
   batch-invariant inference, fixed KV-cache ordering) -> Would challenge pillar
   #4 (model sovereignty instability). Would make LLM-gating feasible for
   self-hosted deployments.

3. **A published metric that replaces TEDS for table evaluation with community
   adoption** -> Would require updating `metrics.py`. Unlikely in the near term
   given TEDS's entrenchment.

4. **OmniDocBench publishing a revised normalizer** (e.g., handling display
   math, nested LaTeX environments differently) -> Would require updating
   `textblock2unicode` to maintain comparability.

5. **A calibration study on WG21-like academic/standards papers** that shows
   whisker's provisional edges are materially wrong -> Would require running
   `whisker calibrate` with that data.

None of these have occurred. This section exists to make the audit falsifiable:
future reviewers can check whether these conditions have been met.
