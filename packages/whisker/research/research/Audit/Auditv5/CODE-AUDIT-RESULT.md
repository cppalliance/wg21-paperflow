# Whisker Audit Result — 2026-08-05 — auditor: Audit v5 (corrective re-audit)

## Why this audit exists

Auditv4 (`packages/whisker/research/Audit/Auditv4/CODE-AUDIT-RESULT.md`, composite
84.50, band Professional-grade) misapplied `AUDIT-SCORECARD.md`, the authoritative
rubric at `packages/whisker/research/Audit/Auditv1/AUDIT-SCORECARD.md`. An
adversarial re-check against the scorecard's actual text found five defects:

1. **G2, G3, G4, G5 were graded under invented names** ("Dormant-code safety",
   "Schema pinning", "Reproducibility", "Structured output") instead of their
   real §2 definitions (Fail-not-partial, Determinism by replay, Per-axis
   reporting + eval integrity, Untrusted-input mediation). Per §2's own text,
   "an unproven gate is treated as Fail" — grading the wrong gate under a
   plausible-sounding name is functionally an unproven gate.
2. **D1 was raised 3→4 citing D7's level-4 anchor** ("level 3 plus
   import-linter contract in CI") instead of D1's real anchor ("level 3 plus
   adversarial-verdict rejection under injection"). This was the single
   largest scoring move in Auditv4 (+5.00 composite points).
3. **D5's anchor was misquoted** as "score pinning and inverted canary." The
   real D5 level-3 anchor is "canaries + holdout split + advisory-only judge";
   the third conjunct was never evidenced in Auditv4's writeup.
4. **The uncalibrated-threshold soft cap (§0.2) was never applied.** §0.2:
   "If a threshold is not calibrated on labeled whisker data, record it as
   `borrowed / uncalibrated` and treat the dependent criterion as a soft cap
   (dimension ≤ level 2), never a live hard gate." No prior audit (v1-v4)
   ever applied this to any dimension, despite Auditv3 M6 recording "8 of 16
   thresholds are bare literals; `calibrate` has never produced a committed
   `thresholds.json`" and C-CAL remaining "Stage 0 / uncalibrated" throughout.
5. **Stage 6 (claimed extended modules) was never executed**, and
   best-defensible band width was never attested. Whisker's own claims
   registry activates M7 (Comprehension eval battery, C-COMP=Yes) and M8
   (Scoring-system meta-conformance, always active as the audit's own
   self-check, 0% product weight) — and M8 never once caught this exact error
   class across four prior audit runs.

This report redoes the affected work (gate re-naming, D1, D5, the soft cap,
Stage 6) and re-verifies everything else Auditv4 got right (D2, D3, D6, D7,
D8, and the structural G1/G6/G7 evidence) rather than trusting the prior
verdict. It also closes two real, non-score technical gaps with new guard
tests (import-linter contract existence, VLM-lane reachability). Auditv4 is
not deleted; it now carries a superseded banner pointing here.

**Headline result:** composite falls from 84.50 to **~81 [71, 91]**, and the
**band falls from Professional-grade to Emerging** — not primarily because
whisker's code regressed (D1/D6/D7/D8 evidence Auditv4 gathered mostly still
holds), but because the corrected D1 anchor still clears level 4 on real
evidence while the never-applied calibration soft cap forces D4's evidence
grade to C, which alone makes the "D1-D4 grade ≥ B" Professional-grade entry
condition unreachable regardless of the composite number. This is a smaller
drop in the numeric composite than the ~73-78 initially anticipated before
re-evidencing D1; the honest number is reported below with the reasoning
shown, not adjusted to match the anticipation.

---

## Claims registry (as declared, re-verified against current repo state)

| ID | Claim | Value | Change since Auditv1/v4 |
|---|---|---|---|
| C-VER | Version phase | `0.5.0` (pre-1.0) | **Unchanged.** `packages/whisker/pyproject.toml` still declares `version = "0.5.0"`. |
| C-API | Stable public API claimed? | No (SemVer 0.y.z) | Unchanged. |
| C-CAL | Calibration status | **Stage 0 / uncalibrated** | **Unchanged, and still the operative fact for the softcap below.** No `thresholds.json` exists anywhere under `packages/whisker/` (confirmed by directory search). `calibrate.py`'s own docstring: "ship PROVISIONAL: hand-set from the clean-paper expectation, never fitted on labeled outcomes." `constants.py`'s module docstring: same. |
| C-LAB | Golden-label role | Advisory | Unchanged. |
| C-INF | Default inference path | Self-hosted (`alliance-pod`) | Unchanged. |
| C-COMP | "Measures comprehension" claimed? | Yes (Lane 3 facts + readback) | Unchanged → activates M7. |
| C-PROD | "Production-grade ops" claimed? | No | Unchanged. |
| C-DET | Determinism tier claimed | Quality-stable | Unchanged. |
| C-LIC | Outbound license + bundled licenses | BSL-1.0 + deps | **Scope note added:** `import-linter>=2.13` was added since Auditv4, but it lives in the **root** `pyproject.toml`'s `[dependency-groups] dev`, not in `packages/whisker/pyproject.toml`'s `[project.dependencies]` or its `tapetum-llm` extra. It is a repo-wide dev/CI tool (drives `lint-imports`), never installed into a shipped whisker wheel or sdist. C-LIC's scope (outbound + bundled runtime licenses) is unaffected. |

**§9 pre-audit determinism questions:** re-checked by grepping the entire
`packages/whisker/research/Audit/` tree for the five questions' answer
patterns. They appear **only** inside Auditv1's own `AUDIT-SCORECARD.md`,
`SYNTHESIS.md`, and `code-c26-gate-meta-review.md` — i.e., only as the
*source* of the questions, never as an answer from the user or Sean. **§9
remains unanswered as of this audit.** Per §0.1 step 2, "If unanswered, D2/G3
run in provisional mode only." This audit carries that flag forward
explicitly (Auditv4 mentioned it was "unanswered" but did not restate the
mechanical §0.1 consequence as plainly).

---

## Gate ledger (conjunctive, correct names, re-evidenced)

| Gate | Real pass rule (quoted from §2) | Verdict | Evidence |
|---|---|---|---|
| **G1 Advisory non-leakage** | "Removing the advisory field leaves the verdict unchanged; adversarial 'all-clear' structured output is ignored by the deterministic layer" | **PASS** | `test_fusion.py::test_review_cap_never_promotes_deterministic_fail`: a det=fail + adversarial llm=pass (confidence 1.0, zero findings) fuses to `FUSION_RULE_WHISKER_FAIL_LOCKED`, still `fail`. 150 fusion tests pass (re-ran, confirmed). Import-linter's "Deterministic core must not import the advisory LLM lane" contract mechanically enforces the separation the gate needs to be meaningful. |
| **G2 Fail-not-partial** | "Fidelity-critical fault → non-zero exit, no output artifact updated, debug preserved" | **PASS** | Re-ran `test_readback.py` (typed `EXIT_OK`/`EXIT_FAIL`/`EXIT_ERROR` in `readback_cli.py`, inverted in `--corrupt` mode). **Beyond readback**, the core scoring CLI path also has fault-injection exit-code tests: `test_score_file.py::test_score_file_broken_front_matter_fails` (rc=5/`EXIT_FAIL` on a fidelity-critical structural fault) and `test_score_file_missing_md_returns_error` (rc=1/`EXIT_ERROR`); `test_check_facts_main.py::test_check_facts_fails_absent_text` (rc=5) and `test_check_facts_missing_md_returns_error` (rc=1). `tapetum_llm/cli.py`'s `TestExitContract` (10 scenarios) covers the advisory lane's own operational-error contract (`_run()` returns 1 iff `counts["error"] > 0`). All ran clean. |
| **G3 Determinism by replay** | "Re-run under the declared tier (C-DET) satisfies the tier's equality contract" | **PASS, provisional** (§9 unanswered) | `test_score_pinning.py` (38 tests, re-ran, all pass) diffs gate/QA metrics against a committed `fixtures/score-baseline.json`; a CI guard blocks `WHISKER_PIN_UPDATE=1` when `CI=true`. `WHISKER_SCHEMA_VERSION = 8` confirmed in `constants.py`; the pinning suite passes post-bump, so replay holds at the current schema. Carries the mandatory `determinism-definition-pending` flag per §9/§7 stop condition 4: this is a PASS on the interim quality-stability contract, not a certified determinism tier. |
| **G4 Per-axis reporting + eval integrity** | "Report shows per-axis scores with `eligible/null` counts; table gate requires structure AND content at the same bar; no modality scored when absent" | **PASS** | `BlockMetrics.reading_order: float \| None` confirmed at `match.py:239` (Phase 2a; `None` on the matrix-budget fallback instead of a synthetic "perfect order" 0.0). `ideal_status` tri-state (`unavailable`/`absent`/`present`) confirmed in the schema-8 changelog in `constants.py`. `test_match.py`, `test_bench.py`, `test_golden_ideals.py` re-ran clean (57 tests). Table fidelity pairs structure (TEDS) and content (cell/recall matching) as independent axes, never collapsed into a single table pass/fail. One evidence gap noted honestly: I could not find a single dedicated unit test isolating "TEDS structure-pass + content-fail must not satisfy a table claim" as its own named test case; the property holds architecturally (the two axes are computed and reported independently, never AND-ed into one boolean), which is a structural guarantee rather than a directly asserted regression test. Not load-bearing enough to flip the verdict, but recorded as an open item below. |
| **G5 Untrusted-input mediation** | "Paper/web text wrapped (segregation + delimiter hardening) and structured-output-validated before any prompt" | **PASS** | `test_injection_corpus.py` (Phase 6, re-ran: 7 tests, all pass) drives the REAL `pipeline.tools.inject_untrusted`/`escape_guard_delimiters`/`guard_instruction` (not mocks) against 5 payload classes (instruction override, forged envelope close, forged system line, nested delimiter, alt-text payload) and asserts envelope integrity + payload containment. **CI-coverage check (verified, not assumed):** the package-tests job runs `uv sync --all-packages` (no `--all-extras`). I confirmed via uv's own docs that `--all-packages` installs **every workspace member and its base dependencies into the shared environment by default** ("By default, all workspace members and their dependencies are installed into the environment" — uv `sync` reference). Because `pipeline` is itself a workspace member (`packages/pipeline`), `import pipeline.tools` succeeds in CI's whisker job even without the `tapetum-llm` extra — the test does **not** silently skip in CI via `pytest.importorskip`. **This corrects a suspicion raised in the task brief**: there is no CI-coverage gap here. |
| **G6 Baseline canary (inverted)** | "A zero-authoring baseline runs on 100% of pages; inverting a canary (known-bad output) MUST fail the gate" | **PASS, one nuance flagged** | 6 hermetic inverted canaries in `test_comprehension_corpus.py`, re-ran clean, all fail as required (table-cell swap, code mangle, formula flip, arrow-operator flip, semicolon swap, heading permutation), plus 2 coverage meta-tests pinning the class/paper matrix. The "100% of pages" clause is satisfied by whisker's always-on structural gates (`gates.py`) and the `unigram_coverage` hard gate, which run zero-authoring on every scored paper unconditionally. **Flagged nuance:** the more specific, olmOCR-pattern `auto_baseline_checks` function (non-empty content + no repeated-n-gram mojibake, `constants.py`'s `BASELINE_MIN_ALNUM_CHARS`/`BASELINE_MAX_REPEATED_NGRAM_RATIO`) is a documented dormant function — CLAUDE.md's own known-gap list states "`auto_baseline_checks` is not wired into `whisker facts`/`guard` output. Callable standalone only." This is a real, if narrow, gap between the *specific* baseline pattern named in G6's trace (p28-B1/B2, olmOCR) and what actually runs in production; it does not flip the verdict because the broader structural+coverage gate suite already provides zero-authoring, 100%-coverage baseline checking, but it is recorded as an open finding (see Findings). |
| **G7 Licensing / attribution** | "No incompatible license combination shipped; required third-party attribution present; BSL-1.0 full-notice satisfied" | **PASS** | BSL-1.0 headers confirmed across the package. `THIRD_PARTY_NOTICES.md` now names both the langextract (Apache-2.0) monotonic-match port AND the OmniDocBench/PubTabNet TEDS port (Apache-2.0) — the exact attribution gap Auditv3 found (finding H4, its cheapest-to-fix failure) is closed. No GPL-family dependency in the ship graph (pylatexenc is MIT, corrected in Auditv3). |

**Gate summary: 7 PASS (G3 carries the mandatory determinism-definition-pending
flag; G6 carries one flagged, non-blocking nuance). 0 FAIL. Band is NOT capped
at Unsound by the gate layer.**

---

## Per-dimension levels, grades, reasons

| Dim | Weight | Auditv4 | **Auditv5** | Δ level | Reason |
|---|---|---|---|---|---|
| D1 Epistemic separation | 20 | 4/A | **4/B** | 0 (grade ↓) | See below. Level 4 stands on the CORRECT anchor; grade downgraded A→B. |
| D2 Determinism | 15 | 3/B | **3/B** | 0 | Re-verified, unchanged. |
| D3 Fidelity | 15 | 3/B | **3/B** | 0 | Re-verified, unchanged. |
| D4 Metric validity | 15 | 3/B | **2/C** | **−1 (softcap)** | See below. |
| D5 Anti-gaming | 12 | 3/B | **3/B** | 0 (anchor corrected) | Real anchor evidenced; no score change, citation fixed. |
| D6 Untrusted-input | 10 | 4/A | **4/A** | 0 | Re-verified, real anchor was already used correctly. |
| D7 API / packaging | 8 | 4/A | **4/A** | 0 | Re-verified, real anchor was already used correctly (the anchor Auditv4 mis-borrowed FOR D1 is legitimately D7's own). |
| D8 Docs / CLI | 5 | 3/B | **3/B** | 0 | Re-verified, unchanged. |

### D1 — reargued against the CORRECT level-4 anchor

**Verbatim from `AUDIT-SCORECARD.md` §3 (re-quoted directly from the file,
not from this prompt):** "0-4 anchors: 0 no separation; 1 separation claimed
in prose only; 2 lanes documented, wiring untested; 3 CI contract test proves
non-leakage and demote-only; **4 level 3 plus adversarial-verdict rejection
under injection**." Auditv4 instead wrote "Level 4 requires mechanical
enforcement of the separation boundary. The import-linter contract is that
enforcement" — that sentence describes D7's anchor ("level 3 plus
import-linter contract in CI"), a different dimension.

Level 3 holds (lane isolation, demote-only ratchet, CI non-leakage: separate
executables/import trees, `_decide()` LLM-free, 150 fusion tests).

For the real level-4 anchor, two pieces of evidence together satisfy
"adversarial-verdict rejection under injection":

1. **CI-durable, current:** `test_fusion.py::test_review_cap_never_promotes_deterministic_fail`
   feeds exactly the anti-gaming test the scorecard names for D1 ("feed an
   adversarial structured verdict; confirm no gate flips"): a deterministic
   `fail` plus an adversarial all-clear LLM verdict (`pass`, confidence 1.0,
   zero axis findings) — the kind of output a successful injection attack
   would try to produce — and asserts the combined verdict stays `fail`
   under `FUSION_RULE_WHISKER_FAIL_LOCKED`. Re-ran, passes.
2. **Live, historical:** Auditv3's real-LLM runtime matrix (scenario 5,
   "Adversarial advisory verdict... did not propagate") ran an actual
   injection attempt against the live `alliance-pod` and confirmed the
   advisory verdict did not flip a gate (E15). This is real evidence the
   property holds under a genuine attack, not just a synthetic unit test.

**Verdict: D1 = 4 is defensible on the correct anchor.** Grade downgraded
from Auditv4's claimed A to **B**: the durable CI evidence (item 1) is a
synthetic adversarial verdict object, not a live injection; the live
evidence (item 2) is real but single-paper (P4182R0), single-model, and not
refreshed in this audit cycle. Per SYNTHESIS §7.2, "any score resting on an
LLM-judge signal inherits at most grade B" — item 2 is exactly that class of
evidence, and it is load-bearing here (item 1 alone, without any live
component, would be a weaker level-4 claim).

### D4 — the uncalibrated-threshold soft cap

**Verbatim from `AUDIT-SCORECARD.md` §0.2** (re-quoted directly): "No
invented thresholds. If a threshold is not calibrated on labeled whisker
data, record it as `borrowed / uncalibrated` and treat the dependent
criterion as a soft cap (dimension ≤ level 2), never a live hard gate."
**Verbatim from `p17-score-uncertainty-grading.md` criterion U5:** "Any
sub-criterion depending on uncalibrated or borrowed thresholds... is
automatically graded evidence ≤ C, confidence low, and forces minimum band
width until calibration TPR/FPR are recorded."

**Which thresholds are uncalibrated (confirmed, not assumed):** every
numeric edge in `constants.py` — `UNIGRAM_COVERAGE_FAIL_EDGE`/`_REVIEW_EDGE`,
`TEDS_FLOOR`, `MHS_FLOOR`, `NID_FLOOR`, `CONTENT_RECALL_FLOOR`,
`REF_NID_ADVISORY_EDGE`, `READING_ORDER_SOFT_EDGE`, etc. — carries an inline
comment stating it is "PROVISIONAL," "borrowed," or "not yet fitted on our
own labeled corpus." No `thresholds.json` (or any committed calibration
artifact with recorded TPR/FPR/precision, per p17-U5's own test) exists
anywhere under `packages/whisker/` — confirmed by directory search. Auditv3's
finding M6 ("8 of 16 thresholds are bare literals; `calibrate` has never
produced a committed `thresholds.json`") still holds unchanged.

**Which D4 criteria genuinely depend on the threshold VALUE, vs. which are
purely structural (careful reading of the D4 anchor, per the task brief's own
steer):** D4's level-3 anchor text is "per-axis + null-eligibility + paired
table + pinned evaluator." Subcriteria (a) per-axis+null-eligibility, (e)
evaluator/match version pinned, and the "paired table" half of (b) are about
REPORTING STRUCTURE — whether the axes are kept separate, whether absent
modalities are `null` not imputed, whether the evaluator version is pinned.
None of these three literally require a specific threshold VALUE to be
correct; whisker satisfies them (schema v8, `reading_order: float | None`,
`ideal_status` tri-state, `WHISKER_SCHEMA_VERSION` pinning). Read narrowly,
this would support level 3 on structure alone, independent of calibration —
exactly the trap the task brief warned against blindly avoiding.

**Why the soft cap still applies:** D4's stated purpose is "Metric
CONSTRUCT VALIDITY" — whether a reported axis actually measures the
distinction it claims to measure, at a bar that means something. That
purpose is NOT satisfied merely by the reporting scaffolding existing; it
requires the floors themselves (`TEDS_FLOOR`, `CONTENT_RECALL_FLOOR`,
`UNIGRAM_COVERAGE_*`) to correctly separate construct-valid from
construct-invalid conversions, and this is precisely the open question
Auditv3's CR1 finding left unresolved and Auditv4 itself admits is STILL
open: "CR1 (b) remains: the scoring lane's text NID is order-invariant and
punctuation-stripping, so it cannot see operator-level corruption... no
fleet-wide threshold exists that catches the corruption without failing the
clean fleet." That sentence is a first-party admission that no calibrated
operating point has been found — not merely that one hasn't been fit yet, but
that the search for one is unresolved. Because D4's own required evidence
("axis table with eligible/null counts; evaluator version record") is silent
on whether the axis VALUES are trustworthy, and because zero calibration
provenance exists anywhere in the package, §0.2's rule applies literally:
the dependent criterion (does this axis correctly discriminate valid from
invalid?) is capped at level ≤ 2, and its evidence grade is forced to C.

**D5, checked and NOT capped:** D5's canary teeth run through `check_facts`
(Lane 3), which is exact substring/structural boolean matching, not a
continuous calibrated threshold — a canary either flips a specific fact from
verified to failed or it does not, with no tunable cutoff involved. Holdout
secrecy (`corpus/holdout/`, fingerprint-locked) and advisory-only-judge
doctrine (fusion.py's architecture) are likewise structural, not
threshold-value-dependent. D5 is NOT soft-capped.

**Verdict: D4 = 2, grade forced to C, confidence low.** This is the single
dimension change that determines the band below (see "Composite" and "Band").

### D5 — reargued against the correct level-3 anchor

**Verbatim from `AUDIT-SCORECARD.md` §3** (re-quoted directly): "3 canaries +
holdout split + advisory-only judge." Auditv4 wrote "score pinning and
inverted canary" — conflating D2's replay evidence with D5's own anchor and
never evidencing the third conjunct.

- **Canaries:** `test_comprehension_corpus.py`, 6 hermetic canaries + 2
  coverage meta-tests, re-ran clean.
- **Holdout split:** `corpus/holdout/` (locked manifest, SHA-256-pinned
  source+candidate, `test_dev_replay_schema.py` exercises every active
  `expected_candidate_status`; the 9-PR dev-replay set is explicitly
  disjoint from the holdout set per the holdout README's rule 1: "Labels are
  committed once and frozen").
- **Advisory-only judge:** `fusion.py`'s own module docstring: "The merged
  verdict is advisory: it never replaces the deterministic whisker verdict
  and never appears in `whisker --gate` exit codes." Enforced by
  `FUSION_RULE_LLM_REVIEW_CAP`/`FUSION_RULE_WHISKER_FAIL_LOCKED` and proven
  by `test_review_cap_never_promotes_deterministic_fail` (the same test cited
  for D1/G1 — the LLM verdict literally cannot flip a deterministic gate).

**Verdict: all three conjuncts hold with real evidence. D5 = 3 stands**, with
the anchor citation corrected. Level 4 ("optimization-budget caps and
proxy-divergence monitoring") is not evidenced and not claimed.

### D2, D3, D6, D7, D8 — re-verified, unchanged

Re-read each anchor directly and re-ran the cited tests; Auditv4's evidence
for these five dimensions holds:

- **D2 (3/B):** `test_score_pinning.py` (38 tests) re-ran clean;
  `WHISKER_SCHEMA_VERSION = 8` confirmed. Provisional per §9 (see claims
  registry). Level 4 (bit-identical replay across hosted MoE endpoints) is
  infeasible per `MODELS.md`, unchanged reasoning.
- **D3 (3/B):** fail-closed mechanism on structural gates + the
  `unigram_coverage` hard floor confirmed live in `test_score_file.py`/
  `test_check_facts_main.py` (see G2 above). Level 4 would require proving
  every tomd failure mode is whisker-detectable, out of this audit's scope
  (tomd is a different package).
- **D6 (4/A):** real level-4 anchor is "level 3 plus least-privilege tools
  and honest impossibility disclosure" — `test_tool_privilege.py` (28
  AST-scan tests, re-ran clean) proves zero model-callable tools; README's
  "Trust boundaries and injection defense" section discloses the PDF lane's
  loss-detector-not-addition-detector limitation. This dimension's anchor
  was already used correctly in Auditv4; no correction needed.
- **D7 (4/A):** real level-4 anchor IS "level 3 plus import-linter contract
  in CI" — confirmed verbatim from `AUDIT-SCORECARD.md` line 131. The
  `[tool.importlinter]` section exists at the repo root with two forbidden
  contracts (core → tapetum_llm, core → pipeline), both `KEPT` per the
  `lint-imports` CI job. This is legitimately D7's own anchor; Auditv4's
  error was borrowing this language FOR D1, not misapplying it to D7 itself.
- **D8 (3/B):** `README.md` (12 sections) confirmed present; exit-code
  contract documented; unchanged from Auditv4.

---

## Composite (navigation only)

```
D1: level 4 (4/4=100%) x weight 20 = 20.00
D2: level 3 (3/4=75%)  x weight 15 = 11.25
D3: level 3 (3/4=75%)  x weight 15 = 11.25
D4: level 2 (2/4=50%)  x weight 15 =  7.50   <- uncalibrated-derived; treat as ~7-8, not a false-precise 7.50
D5: level 3 (3/4=75%)  x weight 12 =  9.00
D6: level 4 (4/4=100%) x weight 10 = 10.00
D7: level 4 (4/4=100%) x weight  8 =  8.00
D8: level 3 (3/4=75%)  x weight  5 =  3.75

Composite ≈ 81   (exact sum 80.75; not reported to two decimals because a
                   load-bearing input, D4, is uncalibrated-derived per §4.3)
```

**Interval: [71, 91]** (w ≈ 10). Per p17-U1, each grade-C or low-confidence
load-bearing input widens the band by ≥5 composite points:
- D4 forced to grade C (uncalibrated thresholds, softcap) → +5
- D2/G3 provisional, low confidence per §9-unanswered (SYNTHESIS §10.3
  states the determinism dimension is "low confidence... until the user and
  Sean supply concrete definitions") → +5

**Weakest-link grade: C** (D4). Per §4.4, "if any load-bearing input is
grade C or below, the band widens and cannot enter 'Professional-grade.'"

**Note on the composite number itself:** this is higher than the ~73-78
anticipated in the corrective task brief. The difference is entirely
attributable to D1: the task brief's own honest instruction ("if it does not
clearly satisfy [the anchor], drop D1 back to 3") anticipated D1 might not
survive re-argument; on the evidence actually found (a durable CI adversarial-
verdict test plus a real historical live-injection non-flip), D1=4 is
defensible under the CORRECT anchor. The band still falls to Emerging,
because D1's level does not gate the band the way D4's evidence GRADE does —
see below.

---

## Band + width + drivers

**Band: Emerging**

Entry-condition check (re-verified against `AUDIT-SCORECARD.md` §4.5, not
assumed):

| Condition (Professional-grade) | Status |
|---|---|
| All gates pass | **Yes** (7/7, with the flags noted above) |
| Composite ≥ 65 | **Yes** (≈81) |
| D1-D4 grade ≥ B | **No.** D4 is forced to grade C by the uncalibrated-threshold soft cap. |
| ≥1 replay evidenced | Yes |
| ≥1 inverted canary evidenced | Yes |

Because "D1-D4 grade ≥ B" fails, Professional-grade is **unreachable at any
point in the reported interval**, independent of the exact composite value —
this is the practical meaning of a non-compensatory weakest-link grade
(§4.4). Falling back to Emerging's entry condition ("all gates pass;
composite ≥ 40; grade ≥ C"): satisfied (composite ≈81 ≥ 40, weakest grade =
C).

**Width: 1 tier** (Emerging to Professional-grade). At the interval's upper
bound (91) the composite condition for Professional-grade would be met, but
the grade condition would still fail — so width is bounded by the grade gate,
not the composite, and no amount of composite drift alone crosses back to
Professional-grade until D4's evidence grade improves.

**Drivers of width (named):**
1. **D4 uncalibrated thresholds (softcap, primary driver).** Zero calibration
   artifact exists; every numeric floor is self-declared PROVISIONAL. This is
   the dimension that keeps the band at Emerging regardless of composite.
2. **§9 determinism definitions still unanswered (D2/G3).** Same open
   question carried unresolved through Auditv1→v5; caps D2 confidence at
   "low" per SYNTHESIS §10.3 and keeps G3 flagged
   `determinism-definition-pending`.
3. **Single-substrate live-LLM evidence (D1, D5).** All live injection and
   adversarial-verdict evidence (Auditv3 E15) derives from one paper
   (P4182R0), one model, one endpoint, and is historical (not re-run this
   cycle). This is why D1's grade sits at B, not A, even though its level
   reaches 4.
4. **G6 baseline-pattern nuance.** `auto_baseline_checks` (the specific
   olmOCR-pattern zero-authoring check named in G6's trace) remains unwired;
   the broader structural+coverage gate suite covers the gate's literal "100%
   of pages" requirement, but this is a documented, narrower gap worth
   tracking (see Findings).

---

## Active extended modules (claimed: M7; always-active: M8)

### M7 — Comprehension eval battery (activated by C-COMP = Yes)

Per `SYNTHESIS.md` §4.2 (re-quoted directly): "M7 Comprehension eval battery
| p13, p28 | claims 'measures comprehension'." No separate M7-specific 0-4
ladder is defined anywhere in `SYNTHESIS.md` or the referenced persona docs
(p13, p28) beyond the activation trigger itself; this audit scores M7 on the
same 0-4 semantics used for the core dimensions (§7.1), since no other ladder
is provided and inventing one would itself violate §0.2's "no invented
thresholds/criteria" spirit.

**Evidence:**
- Lane 3 deterministic fact verification (`facts.py`): 8 assertion types
  (`present`/`absent`/`order`/`table`/`math`/`code`/`xref`/`image_ref`), no
  LLM in the loop, source-verified provenance (a fact is `checked: verified`
  only after its needle is located verbatim in the source PDF/HTML).
- 37 verified facts across 5 corpus papers (P4182R0, P4185R0, P4234R0,
  N5040, P0876R23), all gate hermetically in CI via
  `test_comprehension_corpus.py` (re-ran clean).
- 6 hermetic canaries (one per exploit class: table cell, code snippet,
  formula relation, arrow operator, semicolon punctuation, heading
  permutation) + 2 coverage meta-tests proving the canary matrix cannot
  silently shrink.
- Independent triangulation: `whisker-readback` (blind LLM comprehension
  validation, never in CI) empirically validated the Lane-3 proxy once,
  out of band: 34/37 pass on the stricter grounded scorer (2026-07-09,
  historical, not refreshed this cycle).

**Level: 3.** Verified behavior (canaries demonstrably have teeth, re-ran
clean), holdout hygiene present. Not level 4: the readback triangulation is
historical and dated, and corpus breadth remains narrow (5 of the full
corpus, an openly documented gap — CLAUDE.md known gap #13, "Only a small
subset of converted papers has verified facts"). **Grade: B** (structural CI
evidence is A-tier; the readback corroboration is LLM-judge-derived and
inherits at most B per SYNTHESIS §7.2, and it is load-bearing for anything
beyond level 3).

### M8 — Scoring-system meta-conformance (always active, 0% product weight)

Per `SYNTHESIS.md` §4.2: "M8 Scoring-system meta-conformance | p14, p15, p30
| always, as audit self-check (0 percent product weight)." This module scores
the AUDIT PROCESS, not whisker's code, and carries zero composite weight —
but it must still be reported.

**Finding, stated plainly:** M8's entire purpose is catching exactly the
error class that occurred in Auditv4: gates graded under invented names,
level anchors cited from the wrong dimension, the mandatory calibration soft
cap skipped, and the Stage-6 extended-module pass skipped entirely. **No
prior audit (v1, v2, v3, or v4) ever executed a genuine M8 self-check.**
Auditv1 defined the instrument but explicitly does not score code (out of
scope by its own charter). Auditv2, v3, and v4 each scored the eight core
dimensions and seven gates but never verified their own anchor citations
against the scorecard's literal text before assigning a level — that
omission is the proximate cause of defects 1-3 above.

**Process gap identified:** no step in `AUDIT-SCORECARD.md` §0.1 (or
anywhere else) requires an auditor to re-quote a dimension's anchor text
verbatim from the file immediately before assigning that dimension's level.
Without that discipline, plausible-sounding paraphrase (e.g., "mechanical
enforcement of the separation boundary" for D1, when that language actually
belongs to D7) can silently substitute for the real anchor, and nothing in
the instrument catches it before publication.

**Level: 2, historically (v1-v4); this audit (v5) is the first to actually
execute the function M8 describes** — every quoted anchor and gate-pass rule
in this report was re-read from `AUDIT-SCORECARD.md`/`SYNTHESIS.md` directly
before being used, and the five Auditv4 defects were found by exactly that
discipline. That makes v5 evidence that the M8 function CAN work, but it is
still a one-off manual discipline, not an enforced or repeatable one (no
lint, checklist, or template forces the next auditor to do the same before
scoring). **Grade: C** (a single demonstrated instance, not yet a durable
control). 0% product weight: this does not move whisker's composite.

**Best-defensible band check (per §4.5, "every claimed module ≥ level 3;
band width ≤ one tier"):** M7 (level 3) clears the bar; M8, being 0%-weight
and process-only rather than a whisker-code claim, is not itself a
"claimed module" whose LEVEL blocks Best-defensible (its function is to
audit the auditor, not the product) — but the band is already capped at
Emerging by D4's grade, so Best-defensible is moot this cycle regardless.

---

## Uncertainty ledger (per p17-U2, one row per contested/low-confidence/uncalibrated/thin-evidence/weight-sensitive input)

| Criterion ID | Type | Description | Effect |
|---|---|---|---|
| D4-U5 | Uncalibrated | Every axis floor in `constants.py` is self-declared PROVISIONAL; no `thresholds.json` or committed TPR/FPR record exists. | Forces D4 level ≤2, evidence grade ≤C (§0.2, p17-U5). Primary band-width driver. |
| D2-G3-§9 | Thin evidence / low confidence | §9 determinism-definition questions unanswered since Auditv1 (re-confirmed this cycle). | D2 confidence "low" per SYNTHESIS §10.3; G3 carries `determinism-definition-pending` flag. Secondary band-width driver. |
| D1-live-injection | Thin evidence (single substrate) | All live adversarial-verdict/injection evidence derives from one paper (P4182R0), one model, `openai/gpt-oss-120b`, one endpoint, dated 2026-08-03 (Auditv3), not re-run this cycle. | Caps D1 evidence grade at B, not A, despite level reaching 4. |
| D5-live-injection | Thin evidence (same substrate as above) | D5's advisory-only-judge conjunct is architecturally proven (fusion.py + unit test) but its real-world "held under live attack" corroboration shares the same single-paper substrate as D1. | Kept D5 at grade B, not raised to A. |
| G6-baseline-pattern | Contested / narrow gap | The specific olmOCR-pattern `auto_baseline_checks` function named in G6's own trace (p28-B1/B2) is documented as unwired (`callable standalone only`); the gate's literal "100% of pages" clause is satisfied by the broader always-on structural+coverage gates instead. | Did not flip G6 to FAIL; recorded as an open finding. |
| G4-construct-test-gap | Thin evidence | No single unit test isolates "TEDS structure-pass + content-fail must not satisfy a table claim" as its own named regression case; the property holds architecturally (independent axes, never AND-ed), not via a dedicated adversarial test. | Did not flip G4; recorded as an open finding for future hardening. |
| M8-process | Contested (self-referential) | M8 (audit self-check) was never executed by any prior audit; this audit is the first instance, but the discipline is not yet enforced mechanically. | M8 graded C, 0% product weight, does not move the composite. |

No two-decimal precision is reported for D4's or D5's composite contribution
for the reasons stated above (D4 rounded/ranged as "~7-8" rather than
"7.50"; the overall composite is stated as "≈81," not "80.75").

---

## Findings (resolved from Auditv4's errors, plus new/still-open items)

### Resolved (this audit)

| ID | Finding | Disposition |
|---|---|---|
| AV4-1 | G2-G5 graded under invented names | Re-graded under the real §2 names; evidence re-gathered fresh against Phase 1-6 changes; all four still PASS under their real names. |
| AV4-2 | D1 raised to 4 citing D7's anchor | Re-argued against D1's real anchor ("adversarial-verdict rejection under injection"); D1=4 stands, but grade corrected A→B and the justification now cites the correct evidence. |
| AV4-3 | D5's anchor misquoted, third conjunct unevidenced | Real anchor quoted and all three conjuncts (canaries, holdout, advisory-only judge) independently evidenced; D5=3 stands with corrected citation. |
| AV4-4 | §0.2 softcap never applied | Applied to D4 (capped at level 2, grade forced to C); explicitly evaluated and NOT applied to D5 with reasoning shown. This is the change that moves the band. |
| AV4-5 | Stage 6 / M7/M8 never executed | M7 scored (level 3/B). M8 scored and used to document this exact incident (level 2 historical, 1 instance this cycle, grade C, 0% weight). |

### New findings from this audit

| ID | Finding | Severity | Evidence |
|---|---|---|---|
| AV5-1 | `auto_baseline_checks` (olmOCR-pattern zero-authoring baseline named in G6's own trace) remains unwired into `whisker facts`/`guard`. | Low (does not flip G6; broader gates already cover "100% of pages") | CLAUDE.md known-gap list; `facts.py`. |
| AV5-2 | No dedicated unit test isolates the G4/D4 anti-gaming case "TEDS structure-pass + content-fail must not satisfy a table claim" as its own named regression. | Low (property holds architecturally) | Searched `test_tables.py`/`test_bench.py`/`test_match.py`; no exact match found. |
| AV5-3 | M8 (audit self-check) has no mechanical enforcement (no lint/checklist forcing verbatim-anchor-quote-before-scoring). | Medium (process risk: the exact failure mode that produced Auditv4 could recur) | This report is the only instance where the discipline was applied; nothing prevents the next audit from skipping it again. |

### Still open (carried from Auditv3/v4, re-confirmed unchanged)

- §9 determinism-definition questions (blocking full, non-provisional D2/G3).
- Zero calibration artifact for any of whisker's ~16 numeric thresholds.
- VLM lane (~800 LOC across `vlm_pipeline.py`, `transcribe.py`,
  `vision_task.py`, `vlm_diff.py`, `vision.py`) remains dormant/unwired by
  deliberate decision, now covered by a reachability guard test (this audit,
  see below) so future wiring cannot land silently.

---

## Guard tests added this audit (technical gap closure, non-score)

Two new whisker-local tests close real, previously-unguarded technical gaps
identified in the task brief. Neither changes any dimension level or gate
verdict; both are load-bearing regression protection going forward.

1. **`packages/whisker/tests/test_import_contracts.py`** (new file, 9 tests).
   Reads the root `pyproject.toml` (path found by walking up from this test
   file, never hardcoded) and asserts `[tool.importlinter]` exists, both
   forbidden contracts (core → `tapetum_llm`, core → `pipeline`) are present
   with `type = "forbidden"` and cover the deterministic-core module set.
   Confirmed passing today; confirmed by code inspection (not by actually
   deleting anything from the real file, per the task's read-only
   constraint) that removing `[tool.importlinter]` or either contract would
   fail the corresponding assertion.

2. **`packages/whisker/tests/test_vlm_lane.py`** (2 new tests added to the
   existing file, class `TestVlmLaneReachabilityGuard`). AST-scans the three
   real production entry points (`__main__.py`, `menu.py`,
   `tapetum_llm/cli.py`) and fails if any of them import or reference
   `vlm_pipeline`, `vlm_adjudicate_paper`, `transcribe`, `vision_task`,
   `vlm_diff`, or `vision`. Confirmed passing today (true negative, current
   dormancy holds). Confirmed by code inspection that adding e.g.
   `from whisker.tapetum_llm.vlm_pipeline import vlm_adjudicate_paper` to any
   of the three entry points would trip the module-leaf-name / referenced-
   name check and fail loudly (true positive), without actually wiring
   anything in to prove it live.

**Full suite after both additions:**
`uv run --package whisker pytest packages/whisker/tests -q` →
**1945 passed, 8 skipped, 3 xfailed, 0 failed** (Auditv4's last count was
1934 passed; +11 = the 9 new import-contract tests + 2 new VLM-reachability
tests, zero regressions elsewhere).

---

## Test inventory (re-run this audit)

| Suite | Count | Status |
|---|---|---|
| Full whisker package | 1945 passed, 8 skipped, 3 xfailed | Zero failures |
| `test_readback.py` + `test_dev_replay_schema.py` + `test_injection_corpus.py` + `test_tool_privilege.py` + `test_score_pinning.py` (combined) | 108 passed | G2/G3/G5 evidence |
| `test_import_contracts.py` (new) | 9 passed | Guard: import-linter contract existence |
| `test_vlm_lane.py` (2 new tests added) | 45 passed total (file) | Guard: VLM reachability + pre-existing unit tests |
| `test_match.py` + `test_bench.py` + `test_golden_ideals.py` | 57 passed | D4/G4 evidence |
| `test_fusion.py` (spot-checked `test_review_cap_never_promotes_deterministic_fail`) | included in full-suite pass count | D1/G1/D5 evidence |

---

## Flip conditions (named, updated)

1. **Calibration.** Running `whisker calibrate` on labeled whisker data and
   committing a `thresholds.json` with recorded TPR/FPR/precision would
   remove D4's softcap, likely restoring D4 toward level 3/grade B and
   re-opening the path to Professional-grade (pending the other conditions
   below).
2. **§9 answered.** Answering the five determinism-definition questions would
   remove D2/G3's provisional flag and close that width driver.
3. **Fresh live-injection evidence, multi-paper.** Re-running the adversarial
   verdict + injection battery live, across more than one paper/model, would
   raise D1 and D5 from grade B toward A.
4. **G6 baseline wiring.** Wiring `auto_baseline_checks` into the production
   `whisker facts`/`guard` path would close AV5-1 and strengthen G6's literal
   match to its own trace (p28-B1/B2).
5. **Advisory→gating (unchanged, highest-impact).** If any `tapetum_llm`
   output were ever routed into a hard-gate exit code, G1 fails → Unsound.
6. **Version-phase (→1.0, unchanged).** Crossing to v1.0 activates the API-
   stability bar at full strength.

---

## Stop conditions triggered

**None triggered as a halt.** Stop condition 4 (definition-blocked
determinism) remains **active as a flag only**, carried forward unchanged
from every prior audit: §9 is unanswered, G3 runs provisionally, and the
verdict carries `determinism-definition-pending`. No other stop condition
fired.

---

## Open questions / blockers

1. **§9 determinism definitions** — still the single largest structural
   blocker to a non-provisional D2/G3, unchanged across five audit cycles.
2. **Zero calibration artifact** — the direct cause of this audit's band
   drop; a single `calibrate` dry-run with committed TPR/FPR would materially
   change the picture.
3. **M8 has no mechanical enforcement** — nothing stops a sixth audit from
   repeating Auditv4's exact error class.
