# Shared Evidence Ledger (Audit v2)

Non-duplicated offline, replay, canary, packaging, and runtime evidence.
All C02-C25 reports reference this ledger instead of re-running commands.

## E1. Full test suite

**Command:** `uv run --package whisker pytest packages/whisker/tests -v --tb=short`
**Exit code:** 0
**Result:** 1406 passed, 8 skipped, 3 xfailed in 27.65s

## E2. Comprehension corpus and canaries (9 tests)

**Command:** `uv run --package whisker pytest packages/whisker/tests/test_comprehension_corpus.py -v`
**Exit code:** 0
**Result:** 9 passed in 1.44s

- `test_corpus_has_at_least_one_comprehension_paper` PASSED
- `test_verified_facts_hold_against_snapshot[N5040]` PASSED
- `test_verified_facts_hold_against_snapshot[P0876R23]` PASSED
- `test_verified_facts_hold_against_snapshot[P4182R0]` PASSED
- `test_verified_facts_hold_against_snapshot[P4185R0]` PASSED
- `test_verified_facts_hold_against_snapshot[P4234R0]` PASSED
- `test_canary_scrambled_table_cell_fails` PASSED (inverted canary: table)
- `test_canary_scrambled_code_fails` PASSED (inverted canary: code)
- `test_canary_scrambled_formula_fails` PASSED (inverted canary: math)

Three distinct inverted canaries prove the gate has teeth: scrambled table cell (P4182R0), mangled code snippet (P4234R0), flipped math relation (P4185R0).

## E3. Golden, guard, fusion, incremental, gates tests (284 tests)

**Command:** `uv run --package whisker pytest test_golden.py test_fusion.py test_incremental.py test_golden_ideals.py test_gates.py test_guard.py -v`
**Exit code:** 0
**Result:** 284 passed in 2.74s

Key coverage: golden normalization, membership rules, update safety, expected failures, fusion matrix (agree/rescue/clear/escalate/locked/ideal/source-aware), incremental fingerprinting, gate teeth (front matter, heading, code blocks, tables, TOC leak), guard regression/floors/slack.

## E4. Core metric/scoring tests (218 tests)

**Command:** `uv run --package whisker pytest test_score.py test_metrics.py test_facts.py test_bench.py test_match.py test_score_pinning.py test_edit_distance_parity.py -v`
**Exit code:** 0
**Result:** 218 passed in 1.57s

Key coverage: verdict trichotomy, unigram/shingle separation, reference advisory demotion, region benign filter, metric determinism, TEDS (PubTabNet parity), MHS (APTED parity), content recall, block matching, score pinning (19 papers), edit distance GPL-free parity, facts (all types: present/absent/order/table/math/code/xref/image_ref, fuzzy budgets, canaries), bench aggregate.

## E5. tapetum_llm advisory lane tests (431 tests, 8 skipped)

**Command:** `uv run --package whisker pytest test_tapetum_llm.py test_pdf_judge.py test_readback.py test_ideal_verify.py test_vlm_lane.py test_tapetum_llm_eval.py test_unit_models.py test_unit_judge.py -v`
**Exit code:** 0
**Result:** 431 passed, 8 skipped in 5.24s

Key coverage: cascade topology, escalation signals, grounding (exact/fuzzy/normalized), PDF judge (text layer, per-page screen, recall floors), readback (question generation, scoring, corruption control), ideal verifier (grounding, demotion rules), VLM lane (boundary tests, pipeline text-only guard), unit judge (defect groups, verified counts), model schemas, fingerprinting.

## E6. Invariant, contract, interoperability tests (464 tests, 3 xfailed)

**Command:** `uv run --package whisker pytest test_invariants.py test_claude_invariants.py test_check_facts_main.py test_score_file.py test_dev_replay_acceptance.py test_dev_replay_schema.py test_report.py test_menu.py test_calibrate.py test_source_router.py test_source_aware_integration.py test_html_outline.py test_reference.py test_anchors.py -v`
**Exit code:** 0
**Result:** 464 passed, 3 xfailed in 6.56s

Key coverage: CLAUDE.md invariant checks, score-file/check-facts interop, dev-replay acceptance and schema, report rendering, menu routing, calibration, source router, HTML outline, reference oracle, anchors.

## E7. Wheel build and inspection

**Command:** `uv build --package whisker --wheel`
**Exit code:** 0
**Result:** `whisker-0.5.0-py3-none-any.whl` built successfully.

Wheel contains 49 files:
- 19 core modules + CLAUDE.md
- 24 tapetum_llm modules + tapetum_llm.md
- dist-info (METADATA, WHEEL, entry_points.txt, RECORD)

All source files present. No stale or unexpected files.

## E8. Core import without tapetum-llm extra

**Command:** `uv run --package whisker python -c "import whisker; print(dir(whisker))"`
**Exit code:** 0
**Result:** Core imports successfully. All documented public symbols available. No tapetum_llm dependency required.

## E9. Real-LLM runtime matrix

**Status:** BLOCKED
**Reason:** `ALLIANCE_POD_KEY` environment variable not set. Health endpoint at `sgjy18glyi4blu-8000.proxy.runpod.net` returns HTTP 401 (Unauthorized). Pod infrastructure is reachable but authentication is unavailable.

All 10 required scenarios are blocked:
1. Positive control: BLOCKED
2. Known structural defect: BLOCKED
3. Instruction in document: BLOCKED
4. Delimiter forgery: BLOCKED
5. Adversarial advisory verdict: BLOCKED
6. Grounding failure: BLOCKED
7. Operational failure: BLOCKED
8. status="error" fallback: BLOCKED
9. Mixed batch: BLOCKED
10. Readback corruption control: BLOCKED

Per Runbook section 8: "Definitive credential, endpoint, quota, or entitlement denial is recorded once as blocked evidence." This is recorded once here. Historical runs do not replace a current proof.

## E10. Deterministic replay

Replay evidence is partially available through the test suite (E4 score pinning covers 19 papers with deterministic assertions). A full separate-process replay was not executed due to the lack of a WG21_DATA_DIR workspace with converted papers. The test suite's deterministic assertions (`test_metrics_are_deterministic`, `test_match_blocks_is_deterministic`, `TestFusionDeterminism`) provide offline evidence of pure-function reproducibility.

## E11. Packaging and license

- **Wheel:** builds cleanly (E7)
- **License:** BSL-1.0 in pyproject.toml
- **Core deps:** MIT (rapidfuzz, apted, grits-metric, mistune, markitdown), BSD (numpy, scipy, lxml), LGPL-3.0+ (pylatexenc), MIT (rich)
- **Optional tapetum-llm deps:** MIT (openai), Apache-2.0 (pydantic, pydantic-ai), MIT (python-dotenv), plus internal `pipeline` package
- **BSL-1.0 headers:** Not mechanically verified across all 43 source files in this ledger; C09 role report will audit.

## E12. Fault injection (offline)

The test suite includes offline fault injection paths:
- Malformed sidecar handling (test_fusion: 4 malformed payload tests, all PASSED)
- Invalid whisker/tapetum inputs (test_fusion: 7 invalid whisker tests, 7 invalid tapetum tests)
- Missing candidates (test_golden: missing_candidate_is_hard_fail)
- Missing papers (test_guard: missing_paper_is_hard_fail)
- Nonfinite values (test_guard: nonfinite_baseline_value_raises, nonfinite_current_axis_is_invalid)
- Empty corpus (test_golden: empty_corpus_still_errors)
- Schema mismatch (test_guard: schema_mismatch_baseline_raises)
- Symlink rejection (test_golden: update_rejects_symlinked_member)
- Debug flush before tombstone (test_incremental: partial_pdf_debug_is_flushed_before_tombstone)

Live fault injection (endpoint failure, timeout, persistence failure) requires runtime and is BLOCKED (E9).
