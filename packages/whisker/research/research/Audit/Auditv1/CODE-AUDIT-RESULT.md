# Whisker Audit Result — 2026-07-19 — auditor: 30-persona code audit

## Claims registry (as declared)

| ID | Claim | Value | Activates |
|---|---|---|---|
| C-VER | Version phase | `0.5.0` (pre-1.0) | API-stability bar at reduced strength |
| C-API | Stable public API claimed? | No (SemVer 0.y.z: anything MAY change) | Deprecation policy NOT gate-eligible |
| C-CAL | Calibration status | Stage 0 / uncalibrated (edges borrowed from DP-Bench/Docling/edgeparse) | Uncalibrated threshold cannot be a hard gate |
| C-LAB | Golden-label role | Advisory (golden ideals raise review flags, never hard fails) | IAA/adjudication NOT required |
| C-INF | Default inference path | Self-hosted (Alliance pod, open-weight models) | Cloud-governance NOT a gate |
| C-COMP | "Measures comprehension" claimed? | Yes (Lane 3: deterministic source-verified facts) | M7 comprehension battery activates |
| C-PROD | "Production-grade ops" claimed? | No (pre-1.0, provisional calibration) | M4 observability depth NOT activated |
| C-DET | Determinism tier claimed | Quality-stable (semantic equality of findings, not bit-exact) | Replay must show same verdicts/structure |
| C-LIC | Outbound license + bundled licenses | BSL-1.0 + deps (rapidfuzz MIT, apted MIT, grits-metric MIT, lxml BSD, numpy BSD, scipy BSD, etc.) | Scopes G7 checks |

---

## Gate ledger (conjunctive)

```
G1 Advisory non-leakage:       PASS   evidence: code-c03  confidence: 0.95 (code-analysis-only; runtime adversarial test blocked)
G2 Fail-not-partial:           PASS   evidence: code-c04  confidence: 0.98 (2 LOW findings, neither material)
G3 Determinism by replay:      PASS   evidence: code-c05, code-offline-evidence §5  [tier: quality-stable]  confidence: 0.90 (7-paper replay, not full-corpus; §9 definition pending)
G4 Per-axis + eval integrity:  PASS   evidence: code-c06  confidence: 1.00 (8/8 findings pass, clean)
G5 Untrusted-input mediation:  PASS   evidence: code-c07  confidence: 0.90 (code-analysis-only; no runtime injection test)
G6 Baseline canary (inverted): PASS   evidence: code-c08, code-offline-evidence §2  confidence: 0.98 (3 canaries, all correctly fail)
G7 Licensing / attribution:    PASS   evidence: code-c09  confidence: 0.95 (no pip-licenses run; common knowledge)
```

**All 7 gates PASS. Band is NOT capped at Unsound.**

Evidence grade notes:
- G1, G5: code-analysis-only at the audit cutoff (grade B). Runtime adversarial evidence was blocked by missing `ALLIANCE_POD_KEY`; the later live ideal-verifier evidence is recorded in the final addendum and does not rescore this historical grade.
- G3: provisional (§9 determinism definition questions unanswered). Replay sample is 7/381 papers + 38 pinning tests.
- G2, G4, G6: fully evidenced (grade A).
- G7: confirmed from common knowledge (grade B).

---

## Per-axis / per-dimension table

| Dimension | Level (0-4) | Grade (A-D) | Reason | Evidence | Eligible/Null |
|---|---|---|---|---|---|
| **D1** Epistemic separation | 3 | B | CI contract tests prove non-leakage: fusion is advisory and never changes the deterministic verdict or gate. Existing overall fusion is asymmetric, not demotion-only: it retains heading-only fail→review rescue and soft-review→pass clear. Only the new ideal verifier is demotion-only. Adversarial-verdict rejection test absent (LLM blocked). Separate executables, separate import trees, `_decide()` is LLM-free. Level capped at 3 (not 4) because adversarial-verdict injection under live model is unproven. | code-c03 (7 findings, all PASS), code-c21 (fusion trust), code-c26 G1 spot-check | Eligible |
| **D2** Determinism & reproducibility | 3 | B | Tier map documented (quality-stable). Variance sources enumerated (none in scoring path). 7-paper replay holds. 38 pinning tests + CI-blocked update. Level capped at 3 (not 4) because replay suite is small sample (7/381) and §9 questions pending. | code-c05, code-c02, code-offline-evidence §3/§5, code-c26 G3 | Eligible (provisional: §9 pending) |
| **D3** Fidelity / fail-not-partial | 3 | A | Fidelity-critical stages identified (gates, coverage floor). Fail-closed on all hard paths. No hollow-complete artifact. Debug preserved (logger.exception). Batch-worker firewall commented. Vacuous-green detected and fails. Two LOW findings (NaN theoretical gap, uncommented LaTeX fallback). | code-c04 (full fault-injection analysis), code-c19 (chunking partial→review) | Eligible |
| **D4** Metric construct validity & per-axis eval | 3 | B | Per-axis reporting with null-eligibility (8/8 findings pass). Table = structure (TEDS) + content (recall) paired but independent. Constructs kept distinct (NID vs NED, order vs text, fidelity vs comprehension). Evaluator pinned (rapidfuzz, apted, grits-metric versions in pyproject.toml). Level capped at 3 (not 4) because calibration thresholds are borrowed/uncalibrated, constraining construct validity confidence. | code-c06, code-c10, code-c14, code-c15, code-c18 | Eligible |
| **D5** Anti-gaming / Goodhart | 3 | B | 3 canaries (one per exploit class) + inverted canary tests pass. Holdout secrecy (SHA-256 locked, dev-replay disjoint). LLM-judge advisory-only. Level capped at 3 (not 4) because there are no optimization-budget caps or proxy-divergence monitoring. Golden provenance is mechanically discoverable from tomd's canonical five-file `ideals/*.md` inventory; ideals are structural truth while source remains factual authority. | code-c08, code-c13, code-c22 (readback --corrupt), `test_golden_ideals.py` | Eligible |
| **D6** Untrusted-input / prompt-injection | 3 | B | Trust-boundary inventory present (paper text, model-derived text both wrapped). `inject_untrusted` + `guard_instruction` on all LLM prompts. Structured-output validation (pydantic output_type on all calls). Level capped at 3 (not 4) because no runtime document-embedded injection test corpus executed. | code-c07 (8 findings, all PASS) | Eligible |
| **D7** API contract + packaging | 3 | A | Documented public API + `__all__` (39 symbols). PEP 621 pyproject + correct hatchling wheel. LLM/cloud deps isolated in `tapetum-llm` optional extra. No import cycles (core→tapetum: zero; tapetum→core: read-only). Version consistency (0.5.0 both files). 3 console scripts correctly registered. | code-c25 (14 findings, 12 PASS, 2 NOTED), code-c24 (VLM boundary clean) | Eligible |
| **D8** Docs + operator CLI | 3 | A | 797-line CLAUDE.md contract doc (architecture map, verdict model, exit codes, calibration status, known gaps). Exit-code contract: 0/1/3/5 documented and implemented consistently across 9 verbs. stdout/stderr discipline. `--json` clean. Actionable errors. Runnable path documented. | code-c25, code-c28 §2 | Eligible |

---

## Composite (navigation only)

```
D1: level 3 → 75/100, weight 20 → 15.00
D2: level 3 → 75/100, weight 15 → 11.25
D3: level 3 → 75/100, weight 15 → 11.25
D4: level 3 → 75/100, weight 15 → 11.25
D5: level 3 → 75/100, weight 12 →  9.00
D6: level 3 → 75/100, weight 10 →  7.50
D7: level 3 → 75/100, weight  8 →  6.00
D8: level 3 → 75/100, weight  5 →  3.75

Composite = 75.00
```

Interval: **[69, 81]** (w = ±6, driven by uncalibrated thresholds on D4, blocked LLM evidence on D1/D6, and provisional G3)

Weakest-link grade: **B** (D1, D2, D4, D5, D6 all at grade B; D3, D7, D8 at grade A)

---

## Band + width + drivers

**Band: Professional-grade**

Entry conditions met:
- All gates pass: YES (G1-G7 PASS)
- Composite ≥ 65: YES (75.00)
- D1-D4 grade ≥ B: YES (D1=B, D2=B, D3=A, D4=B)
- ≥1 replay evidenced: YES (7-paper replay, 38 pinning tests)
- ≥1 inverted canary evidenced: YES (3 canaries, all correctly fail)

**Width: 1 tier** (Professional-grade to Emerging boundary is 10 points away)

**Drivers of width:**
1. **Audit-time blocked live-LLM evidence** (D1, D5, D6): runtime adversarial tests could not be executed without `ALLIANCE_POD_KEY`; the final addendum records a later successful live ideal-verifier run, without rescoring
2. **Uncalibrated thresholds** (D4): all edges borrowed, never fitted on whisker's own labeled corpus
3. **Provisional G3** (D2): §9 pre-audit determinism questions unanswered; 7-paper replay, not full-corpus
4. **Golden inventory breadth** (D5): five canonical tomd ideals provide strong provenance but limited whole-paper coverage

---

## Flip conditions (named)

1. **Advisory→gating:** If any `tapetum_llm` output is routed into the `hard` flags list or `_verdict_exit_code` results, G1 fails → Band = Unsound.
2. **Replay refutation:** If a replay at the declared quality-stable tier shows different verdicts on the same inputs, G3 fails → Band = Unsound.
3. **Version-phase (→1.0):** Crossing to v1.0 activates API-stability bar at full strength. Would require deprecation policy and stronger calibration to maintain Professional-grade.
4. **Calibration fit:** Running `whisker calibrate` on 30-50 labeled papers and committing fitted edges with TPR/FPR/precision would elevate D4 toward level 4 and tighten the interval.
5. **Further live LLM evidence:** Running `test_tapetum_llm_eval.py` plus adversarial injection tests would extend the successful live ideal-verifier evidence toward D1/D5/D6 grade-A coverage and narrow the band width.
6. **Golden coverage:** Expanding the canonical tomd ideal inventory beyond the current five papers, while preserving ideal structural authority and source factual authority, would strengthen D5 coverage evidence.

---

## Ranked findings

### Hard-gate adjacent (no gate failures, but close monitoring warranted)

1. **G3 provisional status.** The §9 pre-audit determinism questions (user/Sean definition, reconciliation, equality contract, variance scope) remain unanswered. G3 passes on the interim quality-stability contract, but cannot be certified until definitions are reconciled.

2. **G1/G5 code-analysis-only evidence.** No runtime adversarial test (adversarial all-clear verdict, delimiter-forgery document-embedded injection). The defense is structural (separate executables, delimiter wrapping, structured output), but the AUDIT-SCORECARD's full evidence artifacts are absent.

### False-pass risk

3. **Uncalibrated thresholds.** All content-coverage edges (0.85 fail, 0.95 review) are borrowed from external repos. False-pass rate on the WG21 domain is unknown. The 381-paper corpus run (23 fail / 129 review / 229 pass) suggests reasonable calibration, but "reasonable by inspection" is not fitted.

4. **Golden inventory coverage (5 ideals).** Auto-discovery and provenance are tested, and the source-aware judge remains independent, but five whole-paper ideals cover only a small part of the corpus.

5. **Comprehension corpus breadth.** Only a small subset of papers has verified facts. `image_ref` is intentionally presence-only; raster inspection, VLM coverage, and image fidelity are outside this audit's scope and are not missing gate requirements.

### PR blockers

6. **None identified.** C28 (Engineering Meta-Review) confirms: "There are no integrity failures, no broken tests, no license violations, no undocumented breaking changes, and no silent data-loss paths."

### Polish / pre-1.0 debt

7. **CLAUDE.md serial/concurrent wording inconsistency** (C01 contradiction #1). A reviewer will flag it. Fix: "serial within-paper, concurrent across-paper for the advisory lane only."

8. **Main CLI missing stdout UTF-8 reconfiguration** (C25 finding 9.1). Papers with non-ASCII titles could crash on Windows cp1252 consoles.

9. **Known gaps numbering** (CLAUDE.md). Gap #7 appears twice across subsections.

10. **`_corrupt_markdown` has no unit test** (C22 LOW). Simple function, but a regression would go undetected.

11. **Uncommented `except Exception` in `metrics.py:295,331`** (C04 F02). LaTeX normalization fallback catches. Add a comment documenting them as intentional fallbacks.

---

## PR blockers

**None.** The codebase clears the PR bar for a v0.5.0 pre-1.0 package. All gates pass. All tests pass (1216/1216 + 3 xfailed). License compliance is clean. Exit codes are documented and consistent. No silent data-loss paths.

---

## Strengths

1. **Determinism is proven, not claimed.** 38 pinned scores + 7-paper replay + 381-paper full-corpus run. All metrics are pure functions. Zero randomness sources in the scoring path. The property is structural (architecture enforces it), not accidental.

2. **Three-lane architecture is conceptually clean and architecturally enforced.** Stability (golden.py), Fidelity (score/bench/guard), and Comprehension (facts.py) are separate modules, separate CLI verbs, separate test files. "Fidelity is not comprehension" is not just documented; it is structurally impossible to conflate them.

3. **Comprehension canaries prove the gate has teeth.** Three canaries (scrambled table cell, flipped math relation, mangled code) that MUST fail. The methodology (corrupt a committed snapshot, assert specific fact ID fails) directly targets semantic corruptions that token-level metrics miss.

4. **License discipline is impeccable.** 42/42 BSL-1.0 headers. GPL levenshtein replaced with MIT rapidfuzz. All ported code attributed inline AND in THIRD_PARTY_NOTICES.md. The provenance chain is auditable.

5. **Advisory LLM lane architecture is a studied design.** The never-gates-on-LLM decision is backed by measured evidence (0/31 repos gate on LLM, >= 25% verdict-flip rate, anti-calibrated confidence). Overall fusion remains advisory but intentionally supports heading-only rescue and soft-review clear. The new ideal verifier alone is a one-way demotion cap: `review` can cap a combined pass, while `agree` never promotes, rescues, or clears.

6. **Known gaps are honest and actionable.** Every limitation is documented with: what is missing, what the consequence is, what the interim mitigation is, and what would fix it. `shortcut:` and `golden-hook:` are greppable.

7. **Package boundary discipline.** Core never imports tapetum_llm (proven by exhaustive grep). VLM guard test structurally prevents pipeline contamination. Extras isolation correct.

8. **Metric implementations are faithful ports of published algorithms** (OmniDocBench normalizer, PubTabNet TEDS, GriTS-Con, OmniDocBench block matching, langextract DP). Ensures cross-system comparability.

9. **Professional CLI surface.** 9 verbs, exit codes 0/1/3/5, stdout/stderr discipline, `--json` clean, schema-versioned sidecars, progress bar auto-suppressed on pipe.

10. **Corpus provenance is rigorous.** Dev-replay and holdout disjoint. SHA-256 fingerprints lock evaluation inputs. Contaminated paper quarantined with documented reason. All enforced by automated tests.

---

## External deltas

### Adopted (correctly)
- OmniDocBench `normalized_text` (verbatim two-stage pipeline)
- PubTabNet/OmniDocBench TEDS (lxml → APTED tree-edit distance)
- OmniDocBench block matching with Hungarian assignment
- Multiset content recall (Docling/Nougat/DP-Bench pattern)
- Separate reading-order axis (never gates)
- Advisory-only LLM (ecosystem universal: 0/31 repos gate on LLM)
- GriTS-Con as advisory axis
- Zero-authoring baseline checks (olmOCR pattern, implemented but unwired)

### Missed (proportionate for v0.5.0)
- Span-aware table grid (Docling `verify_table_v2`) — HIGH priority pre-1.0
- Per-formula metric (Nougat, MinerU) — MEDIUM
- Calibration from own labeled data — MEDIUM (infrastructure exists, needs data)
- Paragraph-level drill-down — LOW
- Multi-evaluator agreement — LOW (irrelevant for deterministic gate)

### Correctly rejected
- RAG (same-document task; would add complexity for zero gain)
- LLM-as-judge for hard gating (measured >= 25% flip rate, anti-calibrated confidence)
- Single composite score (strata stay separate; null-eligibility precludes averaging)
- Embedding-based similarity (introduces model dependency; masks word-level corruption)
- Reference-free LLM scoring (the source IS the reference)
- Human annotation pipeline as runtime dependency

---

## RAG verdict

**REJECT.** Evidence-based assessment (C23, 6 findings all confirmed):

1. Whisker is a same-document QA tool. Every operation compares a paper's conversion against its own source.
2. No cross-paper knowledge is required for any detection mechanism.
3. Deterministic source routing + scoped reads cover all labeled defects.
4. The LLM lane reads the full document in context (up to 500K chars); no retrieval needed.
5. RAG would violate the determinism invariant (D1) by introducing embedding drift and retrieval non-determinism.
6. The document IS the context.

---

## Determinism verdict

**Quality-stable contract: SUPPORTED by evidence.**

The deterministic scoring path exhibits strong quality-stability determinism:
- Every metric is a pure function of string inputs (no RNG, no network, no LLM, no mutable shared state).
- All unordered collections are sorted before output (17 `sorted()` sites verified).
- Zero grep hits for `random`/`shuffle`/`sample`/`uuid`/`time.time` in scoring code.
- 38 pinned-score tests reproduce exactly with CI-blocked baseline update.
- 7-paper replay: 0 mismatches across 2 independent runs.
- 381-paper full-corpus run completes without variance.

**Provisional flag:** The §9 pre-audit determinism questions (user/Sean definition, reconciliation, equality contract, variance scope) are unanswered. The verdict uses the interim quality-stability tier. The advisory LLM lane is explicitly non-deterministic and never gates.

---

## Real-LLM proof

### Proven (code-level):
- All 3 LLM call paths are structurally sound (pipeline `run_agent`, `AgentBackend.run`, raw `httpx`)
- Fingerprint recording covers 7 identity components (SHA-256 of md, source, prompt, model, lane version, schema)
- Schema validators enforce structured output (pydantic output_type on all calls)
- All CI tests are fully mocked (correct for determinism; no live LLM in CI)
- `inject_untrusted` + `guard_instruction` wraps all untrusted text entering prompts

### Blocked at the audit cutoff (historical):
- `test_tapetum_llm_eval.py` (5 broken-paper fixtures, live model classification)
- Adversarial all-clear injection test (G1 runtime evidence)
- Delimiter-forgery document-embedded injection corpus (G5 runtime evidence)
- Readback re-validation on current model weights
- `--corrupt` adversarial control on 5-paper corpus

### Historical empirical anchor:
- Readback 34/37 pass (2026-07-09). Code is unchanged since that date. Model weights may have drifted.

---

## Stop conditions triggered

**None triggered.** The audit completed all stages without halt.

- Stop condition 1 (insufficient evidence): Not triggered. All gates have code-level evidence. G1/G5 lack runtime evidence but are structurally defensible.
- Stop condition 2 (uncalibrated thresholds on calibration claim): Not triggered. C-CAL = Stage 0 / uncalibrated (no calibration claim made).
- Stop condition 3 (failed fidelity-critical path): Not triggered. G2 passes.
- Stop condition 4 (definition-blocked determinism): **Active as a flag only.** §9 questions unanswered. G3 runs in provisional mode. Verdict carries `determinism-definition-pending` flag.
- Stop condition 5 (fabricated evidence): Not triggered. All citations resolve to primary source (line numbers verified by C26 meta-review).
- Stop condition 6 (scope drift): Not triggered. No enterprise-imitation machinery required.

---

## Open questions / blockers

1. **§9 Determinism definitions (BLOCKING for G3 certification).** User's definition, Sean's definition, reconciliation, equality contract, and variance scope are all unanswered. G3 passes provisionally under the interim quality-stability contract.

2. **Live-LLM breadth (audit-time blocker).** At the audit cutoff, the missing `ALLIANCE_POD_KEY` prevented `test_tapetum_llm_eval.py`, adversarial injection tests, and readback re-validation. The final addendum now proves the current ideal verifier on one live P4020R0 run; the broader adversarial battery remains follow-up work.

3. **Golden inventory coverage (WEAKENS D5).** The five canonical tomd ideals are auto-discovered with provenance and fingerprint tests, but they do not yet cover a representative fraction of the corpus.

4. **Calibration dry-run (WEAKENS D4).** The `whisker calibrate` workflow is structurally complete and tested, but has never been run on any real data (dev-replay or production). A dry-run on the 9 dev-replay papers would prove the wiring works end-to-end.

---

## Clarification addendum — 2026-07-19

The earlier “user/Sean definitions unanswered” framing in the G3 notes, ranked
finding 1, determinism verdict, stop-condition discussion, and open question 1
misstates the audited question. This audit is evaluating interoperability and
visibility of the merged implementation, not reconciling personal definitions
of determinism.

Verified command provenance and separation:

- Sean Parsons' `cd3cf85` introduced deterministic file bridge commands
  `score-file` and `check-facts` for tomd's subprocess-based golden-QA flow.
- The user-side `58a978c` introduced the menu, advisory fusion, readback,
  dormant VLM tools, and corpus authoring tools.
- Merge commit `29c4ce6` combined those command surfaces. Both file commands
  remain routed by the current `whisker` entry point.
- Deterministic workspace scoring writes `whisker/det/` sidecars and
  `report.md`/`report.json`. Tapetum/fusion writes separate `whisker/llm/`
  sidecars and `report-merged.md`/`report-merged.json`.
- `score-file` and `check-facts` emit stdout JSON or human output. tomd may
  render those responses as its whisker metrics and comprehension panels, but
  those panels are not incorporated into either the deterministic workspace
  report or the fusion report.

The command-visibility gap identified during clarification was real: both file
commands were dispatchable, but top-level `whisker --help` exposed only the
bare scoring parser. The top-level help now lists the complete routed command
surface and returns success for both `-h` and `--help`.

Remaining visibility gaps:

1. There is intentionally no single report combining deterministic workspace
   results, tapetum/fusion results, and tomd's file-command panels.
2. `score-file` and `check-facts` have no whisker-owned persisted report; their
   direct result is stdout unless a caller such as tomd renders it.
3. `image_ref` verifies Markdown reference presence only. Package image
   extraction, raster inspection, VLM coverage, and pixel fidelity are
   explicitly outside the audit scope.

This addendum corrects interpretation and visibility only. Historical sections
above remain unchanged, and no dimension level, gate result, composite, band,
or confidence score is rescored here.

## Golden-ideal integration addendum — 2026-07-20

The final audit authority now includes two distinct locally integrated change
lines, which must not be conflated:

- **PR #282:** new ideal/source/baseline evidence and the approved ideal-aware
  verification inputs;
- **PR #310:** converter implementation and snapshot improvements, plus the
  required deterministic score-pin refresh for those changed snapshots;
- tomd remains the only canonical store, currently five direct
  `tests/fixtures/golden/ideals/*.md` files;
- whisker auto-discovers that inventory read-only and creates no duplicate
  copies;
- the source-aware judge remains independent and source-authoritative;
- only the conditional ideal verifier is demotion-only; existing overall
  fusion still permits its documented heading rescue and soft-review clear;
- fingerprints cover ideal presence/content and verifier identity;
- inspect reports show complete grounded discrepancies, while merged reports
  expose only ideal verdict/count.

This evidence replaces the removed human-fact-blessing and image/VLM-coverage
requirements. Historical persona reports remain historical evidence, not final
instructions. The existing 75.00 composite and [69, 81] interval were not
recalculated; this addendum must not be read as a score increase.

## Lane-1 corpus membership correction — 2026-07-20

`whisker golden` now derives membership from the deterministic,
case-insensitive union of committed `<pid>.expected.md` snapshots and optional
`<pid>.gt.md` bootstrap markers. Existing expected-only snapshots are therefore
real Lane-1 members, including an explicit `missing` finding when their staged
candidate is absent. GT-only members retain the prior `new`,
`--update`, and `--fail-on-new` behavior. Lane 2 remains GT-only.

The corrected canonical audit basis is five committed expected snapshots with
five matching facts files (37 verified facts) and no GT files. The temporary
P3045R8, P3351R4, and P4214R0 expected/facts pairs created during the audit were
removed and are excluded from every corpus count and conclusion. tomd's four
canonical ideals are structural truth and remain separate: Whisker auto-reads
them for the deterministic ideal panel and the conditional LLM verifier, but
they do not define Lane-1 corpus membership. Source documents remain factual
authority.

## Final post-audit evidence update — 2026-07-20

This section records post-audit verification only. It does not alter the
historical 75.00 composite, [69, 81] interval, dimension levels, gate results,
band, or audit-time confidence grades.

### Integrated upstream evidence

- Merged PR #282 was applied locally with its exact P4020R0 evidence:
  `packages/tomd/tests/fixtures/golden/ideals/p4020r0.md`,
  `packages/tomd/tests/fixtures/golden/sources/p4020r0.html`,
  and the P4020R0 record in
  `packages/tomd/tests/fixtures/golden/baselines.json`.
- PR #310's converter and snapshot changes were applied. Whisker's deterministic
  score pin was refreshed for exactly the five affected records, not the wider
  corpus.

### Final test evidence

- tomd full suite: **2022 passed, 9 skipped, 1 xfailed, 0 failed**.
- Whisker's actual test root: **1396 passed, 8 skipped, 3 xfailed, 0 failed**.
  Broad `pytest packages/whisker/` is not a valid package-suite command because
  it collects vendored repositories under `research/`; use the Whisker tests
  root.
- After removal of audit-created ad-hoc pairs, the canonical Whisker corpus is
  **5 expected snapshots, 5 fact files, 37 verified facts, 0 GT files**.
  `whisker golden` now derives membership from the expected-plus-optional-GT
  union and completed **5/5 ok** against the staged corpus.

### Live Alliance Pod proof

A real text-only serial run,
`whisker-tapetum-llm P4020R0 --text-only --concurrency 1 ...`, reached an
endpoint reporting HTTP 200 health, and every model call returned HTTP 200. The
successful run persisted its sidecar with `ideal_sha256` present. The ideal
verifier returned `review` with eight grounded major-heading discrepancies; the
first pair was candidate `### Contracts in general` versus ideal
`## Contracts in general`. The independent LLM suggested `review` at confidence
0.98. Fusion remained advisory and returned `review` with
`ideal_verdict=review` and `ideal_discrepancy_count=8`.

The first runtime attempt exposed a token-grounding versus Markdown-marker
mismatch. It failed loudly and produced no successful sidecar. Grounding was
corrected to a verifier-local raw-exact multiset check, then the same live run
completed successfully. This is positive current ideal-verifier evidence, not
an assertion that the remaining adversarial battery has run.

### Final authority and follow-up

- Human-fact blessing and image/VLM special audit requirements are removed.
  tomd ideals are canonical structural truth, source documents remain factual
  authority, and `image_ref` remains presence-only. Image extraction, raster or
  pixel inspection, VLM coverage, and image fidelity are not audit
  requirements.
- P3045R8, P3351R4, and P4214R0 were audit-created ad-hoc pairs, were removed,
  and are not canonical corpus members.
- A pre-existing CLI operational issue (a failed tapetum adjudication wrote an
  error tombstone but exited 0) has been resolved: `_run()` now returns 1 when
  `counts["error"] > 0`, `status="error"` results are treated as operational
  errors before ideal verification, and `main()` propagates the code via
  `SystemExit`. Regression coverage: `TestExitContract` (10 scenarios).
