# C28 — Engineering / Release Meta-Review

**Persona:** Engineering/Release Meta-Reviewer
**Date:** 2026-07-19
**Commit:** `51cb704610220d31c9d5e078b1350c1b37a8714a`
**Scope:** PR-review readiness assessment for whisker 0.5.0

**Input documents:** C01 (baseline), C09 (license), C11 (golden/guard), C12
(facts/comprehension), C13 (corpus/holdout), C14 (calibration), C24 (VLM
boundary), C25 (professional surface), offline evidence report, and the
package CLAUDE.md (797 lines).

---

## 1. Test Coverage Adequacy

**Headline:** 10,754 test LOC / 13,451 source LOC (0.80 ratio). 1,216 passed,
6 skipped, 3 xfailed, 0 failures. The right things are tested.

### What is covered well

The test portfolio targets the high-value surfaces:

- **Score determinism (G3).** 38 pinned-score tests reproduce exact verdicts
  across runs. A 7-paper replay and a 381-paper full-corpus run both show 0
  mismatches. This is the single most important property for a QA tool and it
  has the strongest evidence.
- **Comprehension corpus (G6).** 9 hermetic CI tests: 5 papers with verified
  facts, 3 canaries that must FAIL (one per exploit class: scrambled table,
  flipped math relation, mangled code). The canaries prove the gate has teeth,
  not just that tests are green.
- **Guard regression (Lane 2).** 24 tests in `test_guard.py` covering axis
  regression, slack boundary, floor crossing, null-eligibility, tool-version
  mismatch, embedded slack/floors, missing paper, duplicate PIDs.
- **Facts engine (Lane 3).** All 8 fact types tested with positive, negative,
  and edge cases. Decoy-table defense tested under heading-scoped
  ALL-semantics.
- **Calibration (D4).** 9 tests covering separable data, FPR ceiling, Youden
  fallback, both-classes requirement, confusion-count invariants, threshold
  monotonicity, serialization, and input validation.
- **Package boundary (D7).** VLM guard test
  (`test_pipeline_stays_text_only`) is structural and load-bearing: asserts
  `user_media` absent from pipeline signatures. This is the firewall against
  scope creep.
- **Holdout provenance (D5).** SHA-256 fingerprint verification, dev-replay /
  holdout disjointness, quarantine of contaminated paper, case + punctuation
  canaries.

### Gaps (proportionate for 0.5.0)

| Gap | Risk | Verdict |
|-----|------|---------|
| No CLI integration test for `_calibrate_main` end-to-end | Low: calibrate has never been run on production data | Acceptable |
| No test for golden.json manifest file-to-flag wiring | Low: `GoldenItem.expected_failure` tested directly | Acceptable |
| No test for conjunctive anchor+fact logic at guard CLI level | Medium: tested separately in `__main__.py`, not composed | Recommend adding before 1.0 |
| No integration test for VLM pipeline with real PDF + vision | Low: VLM is dormant | Acceptable (matches dormant status) |
| `image_ref` with `max_diffs > 0` on path substring untested | Low: narrow edge case | Acceptable |

**Assessment: ADEQUATE for 0.5.0.** The ratio is healthy, but the real
signal is what is tested: determinism, regression gates, comprehension
canaries, and package boundaries. These are the properties that matter for
a QA tool. The gaps are concentrated in CLI integration paths that exercise
composition rather than logic; they are pre-1.0 debt, not PR blockers.

---

## 2. Documentation Quality

**Headline:** The 797-line CLAUDE.md is genuinely good documentation. It would
orient a new contributor within 30 minutes.

### Strengths

- **Architecture map with reading order.** Seven numbered steps from mental
  model to history. A new agent does not have to guess where to start.
- **Three lanes explained precisely.** "Fidelity is not comprehension" is
  called out explicitly, with a concrete example (reflow scores high on
  Lane 2, scrambles a table cell, Lane 3 catches it). This is the kind of
  non-obvious design rationale that saves a contributor from conflating
  the wrong things.
- **Verdict model is fully specified.** Hard fails (2 ways), soft signals,
  advisory overlay. The absence of magic is documented: "agreement !=
  correctness" with citations (CE-OCR, Infinity-Parser).
- **Module layout.** Every module has a one-paragraph description explaining
  what it does AND why it works the way it does (e.g., why `ref_nid` uses
  whole-document NID instead of block matching, with the measured 0.57
  underscoring artifact).
- **Known gaps are ranked and honest.** 8 items in CLAUDE.md's Known gaps,
  plus 5-6 more in the "Advisory LLM lane" and "Comprehension corpus"
  subsections. Each states the gap, the mitigation, and the upgrade path.
- **Greppable conventions.** `shortcut:` and `golden-hook:` are
  machine-harvestable. A new contributor can run `rg -n "shortcut:"` and
  immediately see every deliberate simplification.
- **PowerShell examples.** The quickstart has correct Windows-native commands,
  not Unix-only. This is a small thing that saves real time.

### Weaknesses

- **Serial/concurrent wording inconsistency.** CLAUDE.md says "every call is
  serial" in one section and elsewhere tapetum_llm processes up to 32 papers
  concurrently. C01 notes this is consistent when read carefully
  (serial within-paper, concurrent across-paper for advisory only), but the
  text needs tightening. A reviewer would flag this.
- **Length.** 797 lines is long. The tapetum_llm section is 200+ lines of
  detailed LLM-lane documentation interleaved with the core documentation.
  For a new contributor touching only the deterministic core, this is noise.
  Consider splitting tapetum_llm documentation into its own file (the
  existing `tapetum_llm.md` authority doc could absorb the CLAUDE.md
  section).
- **No README.md.** CLAUDE.md serves as docs, which is fine for a
  workspace-internal package. But if whisker is ever published or shared,
  a minimal README pointing at CLAUDE.md would help.
- **Known gaps numbering.** The numbering restarts between subsections
  ("Advisory LLM lane" #4-#8, "Comprehension corpus" #7-#12,
  "Scoring/calibration" #13), so gap #7 exists twice. Minor, but a reviewer
  would mention it.

**Assessment: STRONG.** This is better documentation than most production
packages have. The architecture map alone puts it in the top tier. The
weaknesses are formatting issues, not content gaps.

---

## 3. Known Gaps Honesty

**Headline:** The codebase is unusually honest about its limitations.

Evidence:

| Limitation | Where documented | Honest? |
|-----------|-----------------|---------|
| All edges borrowed/provisional | `constants.py:20-37`, CLAUDE.md "Calibration status", Known gaps #5 | YES: states source of each edge and upgrade path |
| No fact human-blessed | CLAUDE.md Known gaps #8, C01 contradiction #5 | YES: "weaker independence claim than the docs used to state" |
| VLM lane dormant, 793 LOC | CLAUDE.md Known gaps #4, C24 full audit | YES: "Decision pending: delete vs. quarantine" |
| Decoy table exploit | `facts.py:386` golden-hook comment, CLAUDE.md Known gaps #1 | YES: documents the exploit AND interim mitigation |
| `auto_baseline_checks` unwired | CLAUDE.md Known gaps #4 | YES |
| Corpus breadth 5/381 | CLAUDE.md Known gaps #6 | YES: "footnotes and images strata have zero coverage" |
| Grid model loses rowspan/colspan | CLAUDE.md Known gaps #2 | YES: states prerequisite for golden grids |
| Readback scoring version incompatibility | CLAUDE.md whisker-readback section | YES: "Pass rates NOT comparable across scoring versions" |

The pattern: every limitation is documented in at least two places (usually
CLAUDE.md + inline code comment), each with an upgrade path. The documentation
does not hide behind language like "future work" without specifics; it states
what is missing, what the consequence is, and what would fix it.

One area where honesty could improve: the test results are always presented as
"1216 passed, 0 failures" without noting that 381-paper runtime evidence
required `WG21_DATA_DIR` which is not available in CI. The offline evidence
report notes the live LLM tests are BLOCKED, which is honest, but the
deterministic-only test scope should be clearer in a PR description.

**Assessment: STRONG.** This is the right behavior for a pre-1.0 project.

---

## 4. PR Readiness

### What a reviewer would flag

**Questions requiring answers before merge:**

1. **VLM decision.** 793 LOC with no production entry point. A reviewer will
   ask: "Is this shipping or not? If not, why is it in the tree?" (See
   section 6 for recommendation.)

2. **Calibration status.** All thresholds are borrowed. A reviewer will ask:
   "Have you run whisker on enough real papers to know these edges are
   reasonable?" The answer is yes (381 papers scored, 23 fail / 129 review /
   229 pass), but that evidence is in the offline report, not in a PR
   description.

3. **Human verification of facts.** "No fact has been human-blessed yet." A
   reviewer will ask whether the 37 facts are trustworthy enough for CI
   gating. The answer (agent-verified against staged sources, auditable
   needles) is honest but the independence claim is weak.

**Style/hygiene a reviewer would note:**

4. `_score_file_main` duplicates exit-code logic instead of calling
   `_verdict_exit_code` (C25 finding 6.1). Low risk, minor code smell.

5. Main CLI (`__main__.py`) lacks the stdout UTF-8 reconfiguration that
   `readback_cli.py` has (C25 finding 9.1). Paper titles with non-ASCII
   characters could crash on Windows cp1252 consoles.

6. CLAUDE.md serial/concurrent wording inconsistency (C01 contradiction #1).
   Reviewer will ask for clarification.

### What's strong

- **Zero test failures.** 1216/1216 + 3 xfailed. Clean.
- **License compliance.** 42/42 BSL-1.0 headers. All deps permissively
  licensed. Ported code attributed with inline comments AND
  `THIRD_PARTY_NOTICES.md`. GPL levenshtein explicitly replaced with MIT
  rapidfuzz. A reviewer's G7 pass is immediate.
- **Package boundary discipline.** Core/tapetum-llm isolation proven by
  import analysis. `__init__.py` exports only core symbols. pyproject.toml
  extras correctly isolated. Version consistency (0.5.0 in both files).
- **Determinism evidence.** 38 pinned scores + 7-paper replay + 381-paper
  full-corpus run. This is more determinism evidence than most production
  systems can show.
- **Professional CLI surface.** Exit codes documented and implemented
  consistently across all 9 verbs. stdout/stderr discipline. `--json`
  produces clean JSON. Progress bar suppressed on non-tty.
- **Schema versioning.** `WHISKER_SCHEMA_VERSION = 4` with documented
  migration history. Guard baseline embeds tool versions and refuses to diff
  against a wrong-era baseline.
- **Regression guard design.** Per-paper, per-axis with slack. Floor
  crossings caught. Tool-version mismatch hard-fails. Missing papers
  hard-fail. Null-eligibility handled. This is sophisticated and correct.

---

## 5. Pre-1.0 Proportionality

### Right-sized for 0.5.0

| Practice | Status | Assessment |
|----------|--------|------------|
| Named constants for all thresholds | Present (17 named constants) | RIGHT: prevents magic numbers |
| Schema versioning | v4 with migration history | RIGHT: pays off immediately on sidecar compat |
| BSL-1.0 headers on all files | 42/42 | RIGHT: painful to retrofit later |
| Three independent lanes | Implemented and tested | RIGHT: this is the architecture, not ceremony |
| Deterministic replay evidence | Present | RIGHT: core property of a QA tool |
| Comprehension canaries | 3, one per exploit class | RIGHT: proves gates have teeth |
| Holdout/dev-replay separation | SHA-256 locked, disjoint sets | RIGHT: prevents test-set contamination |
| Guard tool-version check | Present | RIGHT: cheap safety net |
| `shortcut:` / `golden-hook:` conventions | Present | RIGHT: zero-cost upgrade-path markers |
| THIRD_PARTY_NOTICES.md | Present | RIGHT: tracks ported-code attribution |

### Would be over-engineering for 0.5.0

| Practice | Status | Assessment |
|----------|--------|------------|
| Inter-annotator agreement (IAA) | Not present | CORRECT: 5 corpus papers does not justify IAA ceremony |
| Production observability (metrics/dashboards) | Not present | CORRECT: pre-1.0, not claimed (C-PROD = No) |
| Deprecation policy | Not present | CORRECT: SemVer 0.y.z means anything may change |
| Full corpus coverage (all 381 papers with facts) | 5/381 | CORRECT: unrealistic without tooling maturity |
| Formal code review gates | Not present | CORRECT: small team, pre-1.0 |
| Configuration file for thresholds | Not present | CORRECT: constants.py is the right abstraction at this scale |

### Legitimately missing (should exist at 0.5.0)

| Practice | Status | Risk |
|----------|--------|------|
| At least one human-blessed fact | 0/37 | MEDIUM: the blessing ceremony is defined but has never been exercised. The ceremony should be proven to work before 1.0. A single spot-check (10 min of human time against the source PDF) would close this. |
| Calibrate dry-run evidence | Workflow tested, never run | LOW: the workflow is structurally correct and well-tested. Running it on 30-50 labeled papers is pre-1.0 work, but a dry run on the existing 9 dev-replay papers would prove the pipeline wires correctly end-to-end. |
| Main CLI stdout UTF-8 | Missing | LOW: only manifests on Windows cp1252 consoles with non-ASCII paper titles. Easy fix. |

**Assessment: PROPORTIONATE.** The engineering practices match the maturity
stage. Nothing essential is missing; nothing superfluous is present. The
project is not cosplaying enterprise-grade while being pre-1.0, and it is
not cutting corners on the things that matter (determinism, licensing,
regression detection).

---

## 6. VLM Decision

**Facts:** 793 LOC across 5 files (`vlm_pipeline.py`, `vlm_diff.py`,
`vision.py`, `vision_task.py`, `transcribe.py`). 33 unit tests, all pass.
D1 exception documented. Serial semaphore enforced. Sampling pins hardcoded.
Guard test prevents pipeline contamination. No production entry point calls
this code. Never been run end-to-end with a real vision model.

**Options:**

| Option | Pro | Con |
|--------|-----|-----|
| **Delete** | Smaller tree, no dormant-code questions | Loses tested, documented work. Re-implementing costs more than keeping. |
| **Keep as-is** | Zero effort | 793 LOC that a new contributor might mistake for production code. "Decision pending" in Known gaps forever. |
| **Quarantine** | Preserves work, signals intent, no ambiguity | Minor: needs a marker (docstring, README, or conditional import) |

**Recommendation: Keep, with a clear dormant marker.**

Rationale:
1. The code is disciplined. It reimplements all framework invariants (D5, D6,
   D10, D11) and has documented justification for the D1 exception. This is
   not throwaway prototype code.
2. The guard test (`test_pipeline_stays_text_only`) is load-bearing and should
   stay regardless of the VLM code's status. It protects the package boundary.
3. The 33 tests are data-model and signature guards, not integration tests.
   They cost nothing to run (< 0.5s) and document the expected API shape.
4. Deletion in a pre-1.0 package creates churn that helps nobody. The code is
   not in any import path or CLI verb.

**Concrete action:** Add a one-line docstring amendment to each VLM module:
`# Status: DORMANT — not wired to any CLI verb. See CLAUDE.md Known gaps #4.`
This costs 5 lines and removes all ambiguity.

---

## 7. Calibration Honesty

**Headline:** All edges are borrowed. The documentation is honest. The
calibrate workflow exists and is correct.

### Documentation chain

The provenance of each threshold is documented in at least two places:

| Edge | Value | Source | Documented at |
|------|-------|--------|---------------|
| `UNIGRAM_COVERAGE_FAIL_EDGE` | 0.85 | DP-Bench/Docling clean-conversion recall norms | `constants.py:20-37`, CLAUDE.md "Calibration status" |
| `UNIGRAM_COVERAGE_REVIEW_EDGE` | 0.95 | Same | Same |
| `REF_NID_ADVISORY_EDGE` | 0.85 | edgeparse NID CI floor (literal repo constant) | `constants.py:92-94`, CLAUDE.md verdict model |
| `TEDS_FLOOR` | 0.80 | Bench metric floor | `constants.py` |
| `MHS_FLOOR` | 0.80 | Bench metric floor | `constants.py` |
| `NID_FLOOR` | 0.90 | Bench metric floor | `constants.py` |
| `CONTENT_RECALL_FLOOR` | 0.90 | Bench metric floor | `constants.py` |

All are marked "PROVISIONAL, pre-calibration" in constants.py.

### Workflow status

The calibrate workflow is **structurally complete**:
- `calibrate_threshold` implements a full ROC sweep with TPR-at-FPR
  selection and Youden-J fallback (C14 F1-F2).
- The CLI wires sample loading, dual-edge fitting, edge-ordering sanity
  check, and JSON output (C14 F8).
- The workflow is informational only: it writes a `thresholds.json` artifact
  but NEVER auto-promotes edges to `constants.py` (C14 F4). Human promotion
  is enforced by design.
- 9 unit tests cover perfect separation, FPR ceiling, Youden fallback,
  error cases, invariants, and serialization.

The workflow has **never been run on production data**. This is honestly
documented in CLAUDE.md "Calibration status": "A calibrate step (label 30-50
papers, pick max recall at FPR <= 10%, commit fitted edges with recorded
TPR/FPR/precision) would replace these with measured operating points."

### Are the borrowed edges reasonable?

The 381-paper full-corpus run (23 fail / 129 review / 229 pass) suggests the
edges are in the right ballpark: they are not collapsing to near-all-fail
(the earlier `ref_nid` hard gate did that) or near-all-pass (a 0.50 fail
edge would). But "reasonable by inspection" is not calibration. The
documentation is honest about this.

**Assessment: HONEST.** The calibration story is: borrowed edges, documented
provenance, structurally complete workflow, never run. Every part of that
sentence is verifiable in the code and docs. This is the right posture for a
pre-1.0 package that has not yet accumulated enough labeled data.

---

## PR Blockers (MUST fix before merge)

None.

There are no integrity failures, no broken tests, no license violations, no
undocumented breaking changes, and no silent data-loss paths. For a 0.5.0
pre-1.0 package, the codebase clears the PR bar.

---

## PR Recommendations (SHOULD fix)

| # | Item | Effort | Why |
|---|------|--------|-----|
| R1 | Fix CLAUDE.md serial/concurrent wording inconsistency | 10 min | A reviewer will flag it. Clarify: "serial within-paper, concurrent across-paper for the advisory lane only." |
| R2 | Add dormant marker to each VLM module docstring | 5 min | Removes ambiguity for new contributors. One line per file. |
| R3 | Add `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` to main CLI | 5 min | Prevents Windows cp1252 crash on non-ASCII paper titles. Already done in readback_cli. |
| R4 | Human spot-check at least 5 facts against source PDFs | 30 min | Proves the blessing ceremony works. Closes Known gaps #8. |
| R5 | Fix Known gaps numbering (gap #7 appears twice) | 5 min | Minor doc hygiene. |
| R6 | Run `whisker calibrate` dry run on the 9 dev-replay papers | 15 min | Proves the CLI wiring works end-to-end. Does not require promotion. |

Total effort: ~70 minutes. None of these are structural; all are cleanup.

---

## Strengths (what is genuinely good)

1. **Determinism is proven, not claimed.** 38 pinned scores + replay evidence
   is more determinism proof than most production QA tools provide. The
   property is structural (pure functions, sorted collections, no LLM in the
   gate) not accidental.

2. **The three-lane architecture is conceptually clean.** Stability, fidelity,
   and comprehension answer different questions and are deliberately not
   interchangeable. The "fidelity is not comprehension" insight is documented
   with a concrete example and is architecturally enforced (different modules,
   different verbs, different test files).

3. **Comprehension canaries prove the gate has teeth.** Three canaries, one per
   exploit class, that must FAIL. This is better than most QA frameworks that
   only test the happy path. The canary design (scramble a table cell, flip a
   math relation, mangle a code snippet) directly targets the semantic
   corruptions that token-level metrics miss.

4. **License discipline is impeccable.** 42/42 BSL-1.0 headers. GPL
   levenshtein replaced with MIT rapidfuzz. Ported code (TEDS, OmniDocBench,
   langextract) attributed inline AND in THIRD_PARTY_NOTICES.md. The
   provenance chain is auditable. A license reviewer's job is done in minutes.

5. **The advisory LLM lane architecture is a studied design.** The
   never-gates-on-LLM decision is backed by five evidence points: ecosystem
   norm (0/31 repos gate on LLM), measured instability (>= 25% verdict-flip
   rate), anti-calibrated confidence (false-clear at 1.00), model sovereignty,
   and fusion asymmetry. This is not "we didn't get around to it"; it is
   "we measured it and it cannot gate."

6. **Known gaps are honest and actionable.** Every gap states what is missing,
   what the consequence is, what the interim mitigation is, and what would fix
   it. The `shortcut:` and `golden-hook:` grep conventions make the upgrade
   path machine-discoverable.

7. **Package boundary discipline.** Core never imports tapetum_llm (proven by
   import analysis). tapetum_llm imports core read-only. The VLM guard test
   structurally prevents pipeline contamination. Extras isolation in
   pyproject.toml is correct. This is the kind of discipline that prevents
   the dependency graph from rotting.

8. **The calibrate workflow is correct but un-exercised.** This is exactly the
   right order: build the machinery, test it, document the upgrade path,
   wait for labeled data. The alternative (ship calibrated edges on
   insufficient data) would be worse.

9. **Professional CLI surface.** Exit codes documented and consistent across
   9 verbs. stdout carries results, stderr carries progress. `--json` is
   clean. Progress bar auto-suppressed on pipe. Schema-versioned sidecars.
   This is the surface of a tool that expects to be integrated into CI, not
   a script run by its author.

10. **Corpus provenance is rigorous.** Dev-replay and holdout are disjoint.
    SHA-256 fingerprints lock evaluation inputs. Contaminated paper (p0533r9)
    quarantined with documented reason. Holdout README prohibits threshold
    tuning. All enforced by automated tests.

---

## Overall Verdict

whisker 0.5.0 is a well-engineered pre-1.0 package that is honest about its
maturity stage. The test coverage targets the right properties (determinism,
regression gates, comprehension canaries, package boundaries). The
documentation is dense but accurate. The known gaps are documented with
upgrade paths. The licensing is clean.

A PR reviewer would spend most of their time understanding the three-lane
architecture, not finding bugs. The six recommendations above are cleanup,
not structural fixes. The package is ready for review.
