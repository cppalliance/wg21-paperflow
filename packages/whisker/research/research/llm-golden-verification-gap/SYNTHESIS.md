# Why the LLM lane cannot 100%-verify golden PRs - Research Synthesis

**Verdict band:** usable-with-conditions   **Confidence:** high
**Decision vs our codebase:** keep the advisory lane, reshape its recall path: encode the golden contract deterministically (cell-grid compare, secno-aware heading normalization), give golden-PR runs an uncapped per-context budget, and redefine the goal from "100% LLM verification" to "100% deterministic recall on mechanically-checkable classes + measured LLM recall on the fuzzy residue + 100% coverage reporting."

Date: 2026-07-22. Repo HEAD `51cb704` (dirty). Pipeline: evidence baseline
(`00-baseline.md`), 5 web foragers, 17 research archaeologists, 15 repo miners,
25 code personas (62 reports total), 2 meta-reviewers (`meta/A-code-verification.md`:
10/12 claims CONFIRMED, 2 PARTIAL, 0 REFUTED; `meta/B-contradictions.md`: 9
disagreements resolved, consensus core ranked). Every claim below survived
meta-review; corrected numbers are used where meta-review found errors.

## The answer

The golden files from PRs cannot be 100%-verified by the LLM lane because **the
recall was never lost inside the model - it is lost before any model call, in four
compounding layers we built**, and because "100% verification by an LLM" is a goal
no measured system anywhere achieves. Ranked by evidence weight:

1. **Contract-encoding gap (class 1) - the dominant cause.** 29-38% of the atomic
   golden-contract rules (10-13 of 34, `archaeology/a17`) reach neither
   deterministic code nor any LLM prompt. The two incident blockers are both in
   that gap: no code or prompt anywhere mentions secno stripping (`rg secno` over
   whisker src: zero hits), and no table-cell content rule exists in either lane.
   The check's polarity makes it worse: the unit prompt defines fidelity as
   "candidate preserves source text" (`unit_judge.py:99-100`), so a heading that
   verbatim-retains the label the contract requires stripped is *by definition
   correct* to the model. The LLM is asked to rediscover rules nobody told it,
   against a framing that punishes the right answer.

2. **Routing/budget starvation (class 2) - the PR #286 mechanism.** Pages 8/9 were
   routed and then displaced: nine equal-severity `heading_drift` signals competed
   for `MAX_UNIT_CHECKS = 5` slots under a severity-then-LEXICAL sort
   (`unit_judge.py:225-239`, `"page:13" < "page:2"`). Meta-verified: numeric sort
   alone would NOT have saved them (top five would still be pages 1-5); the fix
   needs cap >= routed count or class quotas. The cap itself has no cost basis for
   golden PRs: the pod is billed hourly, not per token (`SERVICES.toml:62-63`),
   and checking all nine routed units costs ~2 minutes. It is a fleet-scale
   latency guard misapplied to a rare, high-stakes review. Compounding this,
   all 7 slots actually spent across both PRs went to FALSE signals (front-matter
   title, bikeshed chrome, script-polluted recall) - sanctioned golden transforms
   the router misreads as loss (`personas/c15`). Git history shows the cap, the
   lexical sort, and the screening architecture landed together in one commit
   (`c59139c`, 2026-07-17) as a first-ship design choice, falsified five days
   later (`archaeology/a16`).

3. **Verification asymmetry (class 4) - why nothing downstream can recover.** The
   lane is architecturally subtract-only: defect groups are created exactly once,
   from model-emitted claims (`unit_judge.py:291`); `grounding.py` and `fusion.py`
   can refute or demote but never create (meta-A claim 8 CONFIRMED). Zero generated
   claims short-circuits everything into a schema-valid vacuous pass
   (`models.py:315-320` accepts pass-with-empty-defects). On PR #286 the machinery
   worked perfectly in the only direction it has: it killed the model's one claim,
   which was false. Precision without recall, by construction.

4. **Model capability ceiling (class 3) - real, but not the cause of these
   incidents.** No model ever saw either defect: 13 of 14 systematically constructed
   contract-defect scenarios die before the LLM (12 at router, 1 at budget,
   `personas/c14`), and the PDF packets are flat `get_text` text with all span
   geometry discarded (`textlayer.py:197`, meta-A claim 4) - even a perfect model
   could not reconstruct the wrapped `SF` cell from what we feed it. The ceiling
   is real for the residue: the historical page-13 false-clear at confidence 1.0
   proves misses despite correct routing; verdicts flip >= 25% on identical reruns
   (config-scoped: n=20, concurrency 32, no batch-invariant kernels); self-reported
   confidence is non-discriminative (96/96 clears at >= 0.95). Published judge
   ceilings corroborate: 57-64% recall on objective error detection, 13-56% flip
   rates (`web/w1`). But class 3 was never reached in the causal chain of either
   incident.

5. **Goal mis-specification (class 5) - the frame.** 0 of 31 reference repos gate
   on LLM verification; 1 of 31 uses an LLM even advisorily (marker, offline);
   6 of 31 do cell-grid comparison, all as offline benchmarks (`repos/r13`, `r14`).
   No surveyed eval framework or published system claims complete-recall LLM
   verification of document conversions (`web/w1/w3/w5`). Both incident defects
   were deterministically decidable (PyMuPDF geometry, DOM class). The own prior
   research (llm-qa-integration, 2026-07-16) had already concluded the LLM lane
   cannot be a recall instrument - the expectation drifted afterward
   (`archaeology/a02`).

## Why nobody noticed until the PRs

A closed loop kept the gap invisible (all meta-verified):

- `corpus/dev-replay/labels.json` records PR #295 as clean with
  `expected_llm_verdict: "pass"` and PR #286 without the SF defect - the ground
  truth encodes both misses as non-defects (meta-A claim 10).
- Test stubs default to pass-with-empty-defects; zero end-to-end assertions that
  any known golden defect is detected (meta-A claim 11). Green CI was structurally
  compatible with recall 0.
- Auditv2 (2026-07-20, two days before) certified architecture and safety with all
  10 live-LLM scenarios blocked; it audited non-leakage and demotion, never recall.
- The operator surface hides the one actionable fact it has: `inspect_report.py`
  renders unit-coverage COUNTS but not the unchecked unit IDs (`page:8`, `page:9`)
  sitting in the sidecar JSON (meta-A claim 7). `review` for "coverage incomplete"
  is indistinguishable from `review` for "defect found".
- Statistically, the 9-paper corpus cannot certify anything: even a perfect run
  gives a weak recall lower bound; certifying >= 95% per class needs ~59-73 labeled
  positives per class (Clopper-Pearson; meta-B corrected c12's inflated figure).
  Two contract classes have zero labeled positives today.

Important honesty note (`personas/c22` steelman, meta-B D6): the lane emitted
`review`, not `pass`, on both PRs - no false-clear under its advisory contract.
The failure is that it could not NAME either defect and its report gave the human
no pointer, making it useless as a verification instrument while technically
honoring its triage contract.

## What to do (ranked, all evidence-backed)

1. **Encode the two blocker classes deterministically (P0, confirmed).** The
   planned P0 bundle attacks the right layers. Cell grid: PyMuPDF `find_tables()`
   (already a dependency) assigns wrapped glyphs to one cell given
   `strategy="text"`/column x-lines (`repos/r11`); portable references are
   docling's `verify_table_v2` cell-text diff, MinerU's `matcher.py` IoU
   assignment + span merge, unstructured's `table_alignment.py` (`repos/r03/r04/r05`).
   Heading normalization: strip structural-label spans before comparison in
   `html_outline.py` and encode the rule in the metadata prompt; five of seven
   surveyed converters already drop script/style by default, ours must too
   (`repos/r09`).
2. **Fix the scheduler as a per-context budget, not a constant tweak.** For golden
   PRs: check every routed unit (hourly billing, +2 min). Numeric page order and
   signal-class quotas (guaranteed slot per signal type) for fleet runs. Record
   `unit_selection` with displacement reasons. Meta-B D9: the sort fix alone is
   insufficient - do not ship it as "the fix".
3. **Report coverage as loudly as detection.** Render unchecked/failed unit IDs
   and the fusion subreason (`coverage cap` vs `defect groups`) in
   `inspect_report.py` and the merged report. This is the steelman's surviving
   criticism and the cheapest change with the highest operator value.
4. **Make the corpus able to measure recall.** Correct the two wrong labels, add
   the two miss-classes as labeled positives, then grow per-class positives toward
   ~59-73 via deterministic mutation of known-good goldens (flip a cell, inject a
   secno, drop a list item). Until then, no recall claim about the lane is
   statistically meaningful.
5. **Add one accountability test per contract class.** A defect-emitting stub plus
   one end-to-end assertion per class that a planted golden defect lands in
   `defect_groups`. This breaks the green-CI-at-recall-0 loop.
6. **Stop consuming self-reported confidence in decisions.** It is documented as
   anti-calibrated in the same files that branch on it (meta-A claim 9). Replace
   with derived signals; long-term, logprob/probe-based confidence (`web/w4`).
7. **Do NOT wire the VLM stack for this (yet).** Meta-B D1: no runtime evidence
   exists that VLM readback would catch PR #286 (the readback corrupt-controls are
   text-mode artifacts; the as-built whole-doc `text_nid` diff would likely drown
   6 corrupted tokens in ~13k). Run the 1-minute experiment (model on pages 8/9
   with a proper packet) before spending on the ~800-LOC stack. Same for k-of-3
   voting: it helps only after routing delivers the right units.

## The honest ceiling

After fixes 1-5: mechanically-checkable contract classes (tables, headings,
script/style, front matter, TOC, counts) reach deterministic 100% recall by
construction. The LLM residue (qualitative wording, rendered-semantics judgment,
genuinely fuzzy equivalence) is bounded by published judge ceilings (~57-64%
single-shot recall on objective errors) and our measured flip rate; with full
routed coverage, k-sampling, and per-class measurement it can be raised and,
for the first time, honestly measured. "100% LLM verification" was never the
attainable target; "100% verification, with the LLM doing the part only an LLM
can do" is.

## Caveats

- The >= 25% flip rate is config-scoped (n=20, c=32, no `VLLM_BATCH_INVARIANT`);
  it is a serving property, not an immutable model constant.
- The "38%" contract-gap figure is the generous end; a17's strict count is 29%.
- Class 3 on table content is UNTESTED, not passed: no run ever reached the model
  with the defect visible. The 1-minute fair-packet experiment should precede any
  claim about model capability on cells.
- c12's sample-size arithmetic and any "VLM would have caught it" sentence were
  rejected in meta-review; do not quote them from the persona reports.
- Single-source estimates (token/latency model in c21-cost, object counts in
  c20-coverage) are directionally safe, magnitudes unmeasured.
