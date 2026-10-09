# Offline Evidence Report — Phase 1

**Date:** 2026-07-19
**Commit:** `51cb704610220d31c9d5e078b1350c1b37a8714a`

---

## 1. Full Test Suite

```
1216 passed, 6 skipped, 3 xfailed, 0 failures, 0 errors
Duration: 8.90s
Platform: Windows 10, Python 3.12.10
```

**Verdict: PASS** — all tests green on current commit.

## 2. Comprehension Corpus (Hermetic CI Gate)

```
9/9 passed in 1.66s
- test_corpus_has_at_least_one_comprehension_paper: PASS
- test_verified_facts_hold_against_snapshot[N5040]: PASS
- test_verified_facts_hold_against_snapshot[P0876R23]: PASS
- test_verified_facts_hold_against_snapshot[P4182R0]: PASS
- test_verified_facts_hold_against_snapshot[P4185R0]: PASS
- test_verified_facts_hold_against_snapshot[P4234R0]: PASS
- test_canary_scrambled_table_cell_fails: PASS (canary 1)
- test_canary_scrambled_code_fails: PASS (canary 3)
- test_canary_scrambled_formula_fails: PASS (canary 2)
```

**Verdict: PASS** — all 5 corpus papers pass, all 3 canaries correctly fail. Gate has teeth (G6).

## 3. Score Pinning Tests

```
38/38 passed in 1.48s
- 19 test_score_pinned cases: all PASS
- 19 test_no_unacknowledged_gate_failures cases: all PASS
```

**Verdict: PASS** — pinned scores reproduce exactly. G3 (determinism) evidence.

## 4. Invariant Tests

```
330 passed, 3 xfailed in 1.97s
- test_no_lazy_imports: all source files pass (except 3 xfailed)
- test_init_only_reexports: all __init__.py files pass
```

**Verdict: PASS** — CLAUDE.md invariants enforced in CI.

## 5. Deterministic Replay (G3)

### 3-paper replay
```
P3181R1, P3100R6, P4182R0: 0 mismatches
Verdicts, unigram_coverage, hard_flags: identical across 2 independent runs
```

### 7-paper replay (10 requested, 3 not converted)
```
7 papers scored twice: 0 mismatches
Verdicts, flags, coverage: identical
```

### Full-corpus reference-free run
```
381 papers scored in 113.6s
23 failed, 129 review, 229 passed
Exit code: 5 (correct: worst verdict is fail)
```

**Verdict: PASS** — quality-stable determinism confirmed.

## 6. Dependency Isolation (D7)

### Core install (no extras)
```
Core dependencies: apted, grits-metric, lxml, markitdown[pdf], mistune,
numpy, paperstore, pylatexenc, rapidfuzz, rich, scipy, tomd
NO LLM deps in core install: PASS
```

### tapetum-llm extra
```
openai, pipeline, pydantic-ai, pydantic, python-dotenv
Correctly isolated behind optional extra: PASS
```

### Import direction
```
Core → tapetum_llm: ZERO (except menu.py lazy import in function body)
tapetum_llm → core: read-only imports (verdict constants, metrics, facts parser)
One-way dependency: PASS
```

## 7. BSL-1.0 Headers (G7)

```
42/42 source .py files have BSL-1.0 copyright headers: PASS
```

## 8. Live LLM Tests — BLOCKED

```
ALLIANCE_POD_KEY: not set
Pod health check: 401 Unauthorized (server running, auth required)
WG21_DATA_DIR: set (C:\Users\sabo2\Desktop\cppalliance\data)
paperstore.db: exists
```

**Status: INCOMPLETE** — The Alliance pod is reachable but API key is not configured in the current environment. Live LLM evidence (Phase 2) cannot be gathered without the key. The audit remains incomplete on the real-LLM-authenticity dimension (C16) and related scenarios. Per the plan: "the audit remains incomplete rather than receiving a professional-grade band."

## 9. Package Surface

| Check | Status |
|---|---|
| pyproject.toml PEP 621 | PASS |
| Build backend (hatchling) | PASS |
| Wheel targets | `src/whisker` — PASS |
| Version consistency | `0.5.0` in both pyproject.toml and __init__.py — PASS |
| `__all__` exports | 51 symbols — PASS |
| Console scripts (3) | whisker, whisker-tapetum-llm, whisker-readback — PASS |
| Exit codes documented | 0/1/3/5 — PASS |

## 10. Corpus Inventory

| Item | Count | Status |
|---|---|---|
| Comprehension papers | 5 | OK |
| Verified facts | 37 | OK (all agent-authored) |
| Canaries | 3 (one per exploit class) | OK |
| Dev-replay PRs | 9 | OK |
| Holdout papers | 3 (+ 1 quarantined) | OK |
| `expected.md` snapshots | 5 | OK |
| Validation evidence | 2 (P4182R0, P4185R0) | Partial (3 papers lack validation) |

## Summary for Gate/Dimension Evidence

| Gate | Offline Evidence | Status |
|---|---|---|
| G1 Advisory non-leakage | Import analysis: zero core→tapetum imports in scoring path | Evidenced |
| G2 Fail-not-partial | Test suite passes; exit codes 0/1/3/5 | Needs fault-injection detail (C04) |
| G3 Determinism by replay | 7-paper and 38-pinning replays: 0 mismatches | Evidenced |
| G4 Per-axis + eval integrity | Per-axis reporting in bench/score/report | Needs C06 detail |
| G5 Untrusted-input mediation | Import of wrap_source in adjudicate.py | Needs C07 detail |
| G6 Baseline canary (inverted) | 3/3 canaries correctly fail in test suite | Evidenced |
| G7 Licensing / attribution | 42/42 BSL-1.0 headers; deps are MIT/BSD compatible | Evidenced |

| Dimension | Key Evidence | Pending |
|---|---|---|
| D1 Epistemic separation | Lane isolation proven by import analysis | C03 detail |
| D2 Determinism | 7-paper replay + 38 pinning tests | Quality-stable confirmed |
| D3 Fidelity | Test suite; batch firewall | C04 fault-injection |
| D4 Metric construct validity | OmniDocBench ports documented | C15 detail |
| D5 Anti-gaming | 3 canaries + holdout split | C08 detail |
| D6 Prompt-injection | wrap_source usage | C07 detail |
| D7 API contract + packaging | PEP 621; extras isolation; __all__ | Clean |
| D8 Docs + operator CLI | 797-line CLAUDE.md; exit codes; stdout/stderr | C25 detail |
