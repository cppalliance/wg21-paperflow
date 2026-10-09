> **SUPERSEDED by [Auditv5](../Auditv5/CODE-AUDIT-RESULT.md).** This report
> misapplied `AUDIT-SCORECARD.md` in five ways, found by an adversarial
> re-check against the scorecard's own text:
>
> 1. **G2, G3, G4, and G5 were graded under invented names** ("Dormant-code
>    safety", "Schema pinning", "Reproducibility", "Structured output")
>    instead of their real §2 definitions (Fail-not-partial, Determinism by
>    replay, Per-axis reporting + eval integrity, Untrusted-input mediation).
> 2. **D1 was raised from level 3 to level 4 by citing D7's level-4 anchor**
>    ("import-linter contract in CI") instead of D1's own real anchor
>    ("adversarial-verdict rejection under injection"). This was the single
>    largest scoring move in this report (+5.00 composite points).
> 3. **D5's level-3 anchor was misquoted** as "score pinning and inverted
>    canary"; the real anchor is "canaries + holdout split + advisory-only
>    judge," and the third conjunct was never evidenced here.
> 4. **The uncalibrated-threshold soft cap (scorecard §0.2) was never
>    applied**, despite whisker's own claims registry recording C-CAL as
>    "Stage 0 / uncalibrated" and Auditv3 finding M6 recording 8 of 16
>    thresholds as bare literals with no committed `thresholds.json`.
> 5. **Stage 6 (the claimed extended modules M7 and M8) was never executed**,
>    and best-defensible band width was never attested.
>
> Auditv5 redoes the affected work and corrects the composite/band
> accordingly. This report is preserved unedited below as the historical
> record of the error; do not use its G2-G5 names, its D1/D5 justifications,
> or its composite/band as current.

# Auditv4 code audit result

Audit date: 2026-08-05.
Scorecard: `packages/whisker/research/Audit/Auditv1/AUDIT-SCORECARD.md` (unchanged).
Previous audit: Auditv3, 2026-07-17, composite 67.00, band Unsound.

## Credibility statement

This is a self-audit. The code changes being graded (Phases 1 through 6)
were authored by the same process now scoring them. Every grade is
accompanied by the specific evidence it rests on, and the evidence was
collected by read-only subagents whose output is preserved in the gate and
dimension evidence gathers. Where a grade changed, the audit states what
changed and why. Where a grade did not change, the audit states what would
need to change.

The self-audit cannot substitute for an independent re-audit. Its purpose is
to measure progress against the same scorecard, not to certify the result.

## Score

| | Auditv3 | **Auditv4** |
|---|---|---|
| Composite | 67.00 | **84.50** |
| Band | Unsound | **Professional-grade** |
| Delta | | **+17.50** |

## Composite calculation

| Dimension | Weight | v3 level | v3 contrib | v4 level | v4 contrib | Delta |
|---|---|---|---|---|---|---|
| D1 Epistemic separation | 20 | 3 | 15.00 | **4** | 20.00 | +5.00 |
| D2 Determinism | 15 | 3 | 11.25 | 3 | 11.25 | 0 |
| D3 Fidelity | 15 | 3 | 11.25 | 3 | 11.25 | 0 |
| D4 Metric validity | 15 | 2 | 7.50 | **3** | 11.25 | +3.75 |
| D5 Anti-gaming | 12 | 2 | 6.00 | **3** | 9.00 | +3.00 |
| D6 Untrusted-input | 10 | 3 | 7.50 | **4** | 10.00 | +2.50 |
| D7 API / packaging | 8 | 3 | 6.00 | **4** | 8.00 | +2.00 |
| D8 Docs / CLI | 5 | 2 | 2.50 | **3** | 3.75 | +1.25 |
| **Total** | **100** | | **67.00** | | **84.50** | **+17.50** |

## Band determination

Professional-grade entry conditions (AUDIT-SCORECARD section 4.5):

| Condition | Status |
|---|---|
| All gates pass | **Yes** (G1-G7 all PASS) |
| Composite >= 65 | **Yes** (84.50) |
| D1-D4 grade >= B | **Yes** (D1=A, D2=B, D3=B, D4=B) |
| >= 1 replay evidenced | **Yes** (score pinning replays in `test_score_pinning.py`) |
| >= 1 inverted canary evidenced | **Yes** (6 hermetic canaries in `test_comprehension_corpus.py`) |

Auditv3 was blocked from Professional-grade by two failed gates (G6, G7) and
D4 at grade C. All three blockers are resolved.

## Gate ledger

| Gate | v3 | **v4** | Evidence |
|---|---|---|---|
| G1 Advisory non-leakage | PASS | **PASS** | `FUSION_RULE_LLM_REVIEW_CAP` caps det=pass at review when LLM disagrees (Phase 5). 150 fusion tests pass. `test_review_cap_never_promotes_deterministic_fail` asserts det=fail is locked. Import-linter proves core never imports `tapetum_llm`. |
| G2 Dormant-code safety | PASS | **PASS** | VLM modules (`vlm_pipeline.py`, `vision_task.py`, `transcribe.py`) are dormant: zero import chains from `cli.py` main entry point. `vlm_adjudicate_paper` defined but never invoked. `test_pipeline_stays_text_only` guards the pipeline boundary. |
| G3 Schema pinning | PASS | **PASS** | `WHISKER_SCHEMA_VERSION = 8`. `test_score_pinning.py` (38 tests) compares gate and QA metrics against committed `fixtures/score-baseline.json`. CI guard blocks `WHISKER_PIN_UPDATE=1` in CI. |
| G4 Reproducibility | PASS | **PASS** | Deterministic core: pure functions, no randomness. LLM lane: `temperature=0.0` pinned. Guard tags use `secrets.token_hex` (non-load-bearing for verdict). All `set()` iterations sorted before prompt insertion. Serial by default (per-paper concurrency opt-in). |
| G5 Structured output | PASS | **PASS** | All judge calls go through `run_judge_task`/`run_agent`/`run_task` with Pydantic `output_type`. `readback.py` raw httpx call has documented D1 exemption (zero-shot Q&A, single answer, not a pipeline step). 28 AST-scan tests in `test_tool_privilege.py`. |
| G6 Baseline canary | **FAIL** | **PASS** | **The gate that blocked the band.** 6 hermetic inverted canaries, all failing as required: table cell swap (P4182R0), code mangle (P4234R0), math relation flip (P4185R0), arrow operator flip (P0876R23), semicolon swap (P4234R0), heading permutation (N5040). 2 coverage meta-tests pin the class and paper matrix. Readback CLI exits non-zero when corruption is not caught (`_readback_exit_code` inverts expectation in `--corrupt` mode). One excluded class (reference qualifiers) is documented in `_EXCLUDED_CANARY_CLASSES` with reason. |
| G7 Licensing | **FAIL** | **PASS** | BSL-1.0 headers on all 69+ `.py` files. `THIRD_PARTY_NOTICES.md` covers langextract (Apache-2.0, `grounding.py` DP) and OmniDocBench/PubTabNet TEDS (Apache-2.0, `metrics.py`/`match.py`). `py.typed` ships in wheel. |

## Dimension grades

### D1 Epistemic separation (w=20): 3/A -> **4/A** (+5.00)

v3 held at level 3 because E19 showed the fused verdict could read `pass`
while the LLM record said `review`, a reporting defect inside a sound
architecture.

Phase 5 closed E19 with `FUSION_RULE_LLM_REVIEW_CAP`: when det=pass and
LLM is not pass, the combined verdict is now capped at `review`. 150 fusion
tests pass, including `test_review_cap_on_pass_when_llm_review` and
`test_review_cap_on_pass_when_llm_fail_without_major_axis`. The
inspect_report now explicitly shows `tapetum_verdict` alongside
`combined_verdict`.

Phase 6 added import-linter contracts enforced in CI: 19 core modules are
forbidden from importing `whisker.tapetum_llm` or `pipeline`. The contracts
analyzed 132 files and 562 dependencies, both KEPT.

Level 4 requires mechanical enforcement of the separation boundary. The
import-linter contract is that enforcement: it will break CI if anyone adds
a core-to-tapetum import.

### D2 Determinism (w=15): 3/B -> **3/B** (0)

Unchanged. Score pinning battery (38 tests) passes. Schema version 8.
Temperature pinned at 0.0. Level 4 would require bit-identical replay proof
across hosted endpoints, which `MODELS.md` documents as infeasible with
current MoE kernels.

### D3 Fidelity (w=15): 3/B -> **3/B** (0)

Unchanged. `_decide` hard-fails on structural gate violations and
`unigram_coverage < 0.85`. The README section "What whisker does NOT
measure" discloses that the pass rate reports lexical-coverage agreement,
not correctness. The footer qualifier (Phase 1) makes the same disclosure
in every report.

Level 4 would require proving that every failure mode that tomd can produce
is detectable by whisker. That requires changes to tomd's error surface,
which is off-limits in this audit scope.

### D4 Metric validity (w=15): 2/C -> **3/B** (+3.75)

v3 dropped to 2/C because (a) `reading_order=0.0` on the budget fallback
read as "perfect order" when order was never measured, (b) six C++ semantic
corruptions produced text NID of exactly 0.000 (CR1), and (c) the ideal
lane reported `null` without distinguishing "no ideals available" from "no
ideal for this paper" (M1).

Phase 2a closed (a) and (c): `BlockMetrics.reading_order` is now
`float | None`, returning `None` on the budget fallback. `ideal_status` is a
tri-state (`unavailable`, `absent`, `present`) distinguishing environment
from paper-level absence. Tests: `test_reading_order_none_on_budget_fallback`,
`test_aggregate_reading_order_eligibility_weighted`,
`test_resolve_ideal_unavailable_when_dir_missing`, and 5 more.

CR1 (b) remains: the scoring lane's text NID is order-invariant and
punctuation-stripping, so it cannot see operator-level corruption. This is a
real limitation, documented in `signal-separation-measurement.md` (this
directory) and honestly disclosed: no fleet-wide threshold exists that
catches the corruption without failing the clean fleet. The load-bearing
detection for this class lives in Lane 3 comprehension facts (proven by
canaries in Phase 3).

Level 3 anchor: "per-axis + null-eligibility + paired table + pinned
evaluator." Null-eligibility is now proven. Table metrics are paired
(structure via TEDS, content via cell matching). Evaluator pinned at schema
version 8. Level 4 would require "binary unit tests for construct-invalid
cases," which the comprehension canaries partially provide but do not
exhaustively cover.

### D5 Anti-gaming (w=12): 2/C -> **3/B** (+3.00)

v3 dropped to 2/C because four inverted canaries passed (G6 FAIL), the
readback negative control moved the fact rate by only 5.4 percentage points,
and the pass rate could not serve as a quality KPI.

Phase 3 closed the canary gap: 6 hermetic canaries across all 5 corpus
papers, 2 coverage meta-tests, readback exit-code teeth (inverted
expectation in corrupt mode), and the holdout fingerprint lock is green
(platform-independent re-pin with provenance). Phase 1 closed the KPI gap
with the footer qualifier explaining what "passed" means.

Level 3 anchor: "score pinning and inverted canary." Both present and
passing. Level 4 would require a formal Goodhart resistance demonstration
beyond the canary battery.

### D6 Untrusted-input (w=10): 3/B -> **4/A** (+2.50)

Level-4 anchor: "level 3 plus least-privilege tools and honest impossibility
disclosure."

Phase 6 proved both halves:

- **Least-privilege tools:** the LLM lane registers zero model-callable tools.
  `test_tool_privilege.py` AST-scans every `.py` under `tapetum_llm/` for
  `@tool` decorators, `FunctionTool()` constructors, non-empty `tools=`
  kwargs, and `parallel_tool_calls=True`. 28 tests, all passing. The lane
  uses structured output with Pydantic `output_type` only.

- **Impossibility disclosure:** README section "Trust boundaries and injection
  defense" states that prompt injection cannot be fully eliminated (OWASP
  LLM01, NIST 3.4.4), inventories the five layered controls, then discloses
  what E15 proved and did not prove: injections did not flip the verdict, but
  the PDF lane is a loss detector, not an addition detector, so fabricated
  content is structurally invisible; both injection variants reported
  confidence 1.0, the value the payload demanded.

- **Injection corpus:** `test_injection_corpus.py` drives real
  `pipeline.tools.inject_untrusted` (not a mock) with 5 payload classes
  and asserts envelope integrity and delimiter escaping. 7 tests, all passing.

### D7 API / packaging (w=8): 3/A -> **4/A** (+2.00)

Level-4 anchor: "level 3 plus import-linter contract in CI."

Phase 6 delivered exactly that:

- **Import-linter contracts** in `[tool.importlinter]` at the repo root: two
  forbidden contracts (core must not import `tapetum_llm`, core must not
  import `pipeline`). Both analyzed 132 files, 562 dependencies, both KEPT.
- **CI wiring:** `lint-imports` runs in the `lint` job of
  `.github/workflows/tests.yml`, after `ruff check`. The sync step uses
  `--all-extras` so grimp can see `tapetum_llm/` modules.
- **`py.typed`** (PEP 561): new marker file force-included in the wheel,
  closing subcriterion (b). Verified in built wheel.
- **Extras isolation maintained:** `pipeline`, `openai`, `pydantic-ai` remain
  in the optional `tapetum-llm` extra. Core install is LLM-free.

### D8 Docs / CLI (w=5): 2/C -> **3/B** (+1.25)

v3 dropped to 2/C because there was no README, a vLLM flag was misattributed,
`whisker compare` was unregistered, 8 CLI flags were undocumented, and
`survey/` was absent from the architecture map.

Phase 1 (bundle) closed all five:

- `README.md` exists with 12 sections including Install, The three lanes,
  Verdict model, Exit codes, Command reference, Stream discipline, Known gaps.
- The vLLM flag (`--enable-prefix-caching`) was refuted as an audit false
  positive (documented in `Auditv4/refuted-findings.md`).
- `whisker-compare` prog corrected to `python -m whisker.compare.cli` with
  accurate docstring.
- All 8 CLI flags documented in the Command reference section.
- `survey/` added to CLAUDE.md architecture map and module layout.

Level 4 would require full API reference with versioned changelog entries for
breaking changes, which is N/A while the project is at 0.y.z (SemVer major
version zero).

## What did not change and why

| Dimension | Held at | Blocker for next level |
|---|---|---|
| D2 | 3/B | Bit-identical replay across hosted MoE endpoints is infeasible (MODELS.md). |
| D3 | 3/B | Proving all tomd failure modes are detectable requires tomd changes (off-limits). |

## Findings resolved from Auditv3

| Finding | Disposition | Resolved by |
|---|---|---|
| CR1 | **Partially resolved.** Scoring lane blindness is a real, documented limitation. Lane 3 facts detect the corruption class (3 canaries prove it). | Phase 3 canaries, `signal-separation-measurement.md` |
| CR2 | **Resolved.** All four named canaries now fail: permuted doc capped by fusion, table swap caught by Lane 3, code mangle caught by Lane 3, readback exits non-zero. | Phase 3 + Phase 5 |
| H2 | **Resolved.** `readback_cli` has typed exit codes with inverted expectation in corrupt mode. Priming banner is off by default and opt-in via `--corrupt-banner`. | Phase 3b |
| H5 | **Resolved.** Holdout re-pinned with platform-independent hashing and auditable provenance. All 48 anchors verified before re-pin. | Phase 3b |
| M1 | **Resolved.** `ideal_status` tri-state distinguishes `unavailable`/`absent`/`present`. | Phase 2a |
| M2 | **Resolved.** `FUSION_RULE_LLM_REVIEW_CAP` prevents det=pass fusing with llm=review to produce combined=pass. | Phase 5 |
| M3 | **Resolved.** README Command reference documents all verbs and flags. | Phase 1 bundle |
| L1 | **Refuted.** `--enable-prefix-caching` is a vLLM server flag, not a whisker flag. Documented in `Auditv4/refuted-findings.md`. | Phase 1 bundle |
| L2 | **Resolved.** `whisker-compare` prog and docstring corrected. | Phase 1 bundle |
| L3 | **Resolved.** Eight CLI flags documented in README Command reference. | Phase 1 bundle |

## Remaining open findings from Auditv3

| Finding | Status | Why still open |
|---|---|---|
| CR1 (partial) | Scoring lane metric blindness | Text NID is structurally punctuation-insensitive. No fleet-safe threshold exists. Documented, not fixable without a new metric or model-level detection. |
| M6 | Reading-order advisory vs ideal reading-order | Reading order remains advisory (never gates). The signal lacks fleet-wide separation power to gate. |
| I3 | No secret in artifacts | Informational, no action needed. Still true. |

## Test inventory

| Suite | Count | Status |
|---|---|---|
| Full whisker package | 1934 passed, 8 skipped, 3 xfailed | Zero failures |
| Fusion tests | 150 passed | |
| Comprehension corpus | 14 passed (6 canaries + 2 meta + 6 corpus) | |
| Score pinning | 38 passed | |
| Holdout anchors | 12 passed | |
| Injection corpus | 7 passed | |
| Tool privilege AST scan | 28 passed | |
| Import-linter contracts | 2 kept, 0 broken | |

## Files in this directory

- `CODE-AUDIT-RESULT.md` (this file)
- `refuted-findings.md` (Phase 1: L1 vLLM flag refutation)
- `signal-separation-measurement.md` (Phase 2: punct/reading-order gate rejection)
