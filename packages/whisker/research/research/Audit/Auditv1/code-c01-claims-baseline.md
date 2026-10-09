# C01 — Claims Registry and Baseline Freeze

**Persona:** Claims and Baseline Clerk
**Date:** 2026-07-19
**Commit:** `51cb704610220d31c9d5e078b1350c1b37a8714a` (2026-07-17)

---

## Claims Registry (AUDIT-SCORECARD §1)

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

## Fresh Baseline

### Source inventory

| Category | Count |
|---|---|
| Source `.py` files (core + tapetum_llm) | 42 |
| Source lines (all `.py`) | 13,451 |
| Test `.py` files | 35 |
| Test lines (all `.py`) | 10,754 |
| Test:source ratio | 0.80 |
| BSL-1.0 headers present | 42/42 (100%) |

### Source modules (main tree: `packages/whisker/src/whisker/`)

**Core (deterministic, no LLM):** `__init__.py`, `__main__.py`, `anchors.py`, `bench.py`, `calibrate.py`, `constants.py`, `corpus_tools.py`, `facts.py`, `gates.py`, `golden.py`, `golden_ideals.py`, `guard.py`, `match.py`, `menu.py`, `metrics.py`, `reference.py`, `report.py`, `score.py`, `tables.py` (19 files)

**tapetum_llm (opt-in LLM, never gates):** `__init__.py`, `adjudicate.py`, `chunking.py`, `cli.py`, `constants.py`, `fusion.py`, `fusion_report.py`, `grounding.py`, `html_outline.py`, `inspect_report.py`, `judge_task.py`, `models.py`, `pdf_judge.py`, `readback.py`, `readback_cli.py`, `source_router.py`, `textlayer.py`, `transcribe.py`, `unit_judge.py`, `vision.py`, `vision_task.py`, `vlm_diff.py`, `vlm_pipeline.py` (23 files)

### Test results (current commit, Windows)

```
1216 passed, 6 skipped, 3 xfailed in 8.90s
0 failures, 0 errors
```

### CLI verbs (real, from `__main__.py`)

| Verb | Entry | Description |
|---|---|---|
| `whisker [PID...]` / `--all` | `_score_main` | Per-paper QA verdict (reference + reference-free) |
| `whisker bench` | `_bench_main` | Benchmark vs ground-truth corpus |
| `whisker guard` | `_guard_main` | Per-paper regression gate with anchors + facts |
| `whisker golden` | `_golden_main` | Lane 1 stability: exact compare vs snapshots |
| `whisker facts` | `_facts_main` | Lane 3 comprehension gate |
| `whisker calibrate` | `_calibrate_main` | Fit coverage edges from labeled data |
| `whisker score-file` | `_score_file_main` | File-based scoring (no backend required) |
| `whisker check-facts` | `_check_facts_main` | File-based fact/anchor checking |
| `whisker corpus stratify` | `_corpus_main` | List zero-coverage papers by stratum |
| `whisker corpus draft` | `_corpus_main` | Generate draft facts scaffold |
| (no args, tty) | `run_menu` | Interactive menu |
| `whisker-tapetum-llm` | `tapetum_llm.cli:main` | Advisory LLM fidelity adjudication |
| `whisker-readback` | `tapetum_llm.readback_cli:main` | Blind LLM comprehension check |

### Console scripts (pyproject.toml)

| Script | Entry point |
|---|---|
| `whisker` | `whisker.__main__:main` |
| `whisker-tapetum-llm` | `whisker.tapetum_llm.cli:main` |
| `whisker-readback` | `whisker.tapetum_llm.readback_cli:main` |

### Dependencies

**Core (always installed):**
`apted>=1.0.3`, `grits-metric>=0.6.0`, `lxml>=5.0.0`, `markitdown[pdf]>=0.1.6`, `mistune~=3.2.0`, `numpy>=1.26`, `paperstore`, `pylatexenc>=2.10`, `rapidfuzz>=3.14.5,<4`, `rich>=13.0`, `scipy>=1.11`, `tomd`

**Optional `tapetum-llm` extra:**
`openai`, `pipeline`, `pydantic-ai`, `pydantic>=2.0`, `python-dotenv>=1.0`

### Corpus inventory

**Comprehension corpus (5 papers, 37 verified facts):**

| Paper | Facts file | Expected snapshot | Validation | Fact types |
|---|---|---|---|---|
| P4182R0 | 8 facts | Yes | Yes (P4182R0.validation.md) | present, order, table |
| P4185R0 | 9 facts | Yes | Yes (P4185R0.validation.md) | present, math, table |
| P4234R0 | facts file | Yes | No | code, xref, raw-surface present |
| N5040 | facts file | Yes | No | pipe + HTML tables |
| P0876R23 | facts file | Yes | No | poll tables, code, xref |

**Canaries (3, one per exploit class):**
1. Scrambled table cell (P4182R0)
2. Flipped math relation (P4185R0)
3. Mangled code snippet (P4234R0)

**Dev-replay:** `corpus/dev-replay/labels.json` — 9 golden PRs (#282-#286, #290, #293-#295) with expected verdicts.

**Holdout:** `corpus/holdout/manifest.json` — 3 papers (p1112r4, p3714r0, p4182r0) with locked SHA-256 candidates. p0533r9 quarantined (PR #293 contamination).

### Exit codes (CI contract)

| Code | Meaning |
|---|---|
| 0 | OK |
| 1 | Error |
| 3 | Review |
| 5 | Fail |

### Named constants (constants.py)

| Constant | Value | Purpose |
|---|---|---|
| UNIGRAM_COVERAGE_FAIL_EDGE | 0.85 | Hard gate: content missing |
| UNIGRAM_COVERAGE_REVIEW_EDGE | 0.95 | Soft: some words missing |
| DRIFT_SOFT_EDGE | 0.10 | Soft: extra tokens |
| REGION_SOFT_COUNT | 1 | Soft: misaligned regions |
| REGION_BENIGN_UNIGRAM_FLOOR | 0.95 | Benign-region fold threshold |
| QA_SCORE_SOFT_EDGE | 70 | Soft: structural QA score |
| TEDS_FLOOR | 0.80 | Bench metric floor |
| MHS_FLOOR | 0.80 | Bench metric floor |
| NID_FLOOR | 0.90 | Bench metric floor |
| CONTENT_RECALL_FLOOR | 0.90 | Bench metric floor |
| REF_NID_ADVISORY_EDGE | 0.85 | Advisory: oracle agreement |
| BENCH_REGRESSION_SLACK | 0.03 | Bench regression tolerance |
| GUARD_AXIS_SLACK | 0.02 | Per-paper guard tolerance |
| BLOCK_LOCK_NED | 0.25 | Block matching: pre-lock |
| BLOCK_ACCEPT_NED | 0.70 | Block matching: accept |
| BLOCK_FUZZY_RESCUE_NED | 0.40 | Block matching: rescue |
| BLOCK_MATRIX_CELL_BUDGET | 400,000 | Block matching: cap |
| WHISKER_SCHEMA_VERSION | 4 | Sidecar/report schema |

All thresholds are **borrowed/uncalibrated** (adopted from external repos, not fitted on whisker's own labeled corpus). `calibrate` workflow exists but has never been run on production data.

---

## Known contradictions (record, do not silently choose)

1. **Serial determinism vs tapetum CLI concurrency:** CLAUDE.md states "every call is serial" for deterministic core. `tapetum_llm/cli.py` processes up to 32 papers concurrently (`--concurrency 32`). The concurrency is within the advisory lane only, which is explicitly non-deterministic. However the CLAUDE.md text also says "requests within one paper are serial" which is a different claim from "all calls serial." **Status:** consistent when read carefully (serial within-paper, concurrent across-paper for the advisory lane only), but the wording in CLAUDE.md is inconsistent between sections.

2. **Core/tapetum isolation vs interactive menu import:** `__main__.py:1244-1246` imports `whisker.menu.run_menu` at runtime (lazy import inside a function). `menu.py` may import tapetum_llm features. **Status:** needs verification whether menu introduces a tapetum dependency at core import time. The lazy import guards it.

3. **Documented trace support vs actual trace emission:** CLAUDE.md references `--trace` and `--debug` artifacts. The deterministic CLI has no `--trace` flag; trace/debug are tapetum_llm CLI features. **Status:** the claim in CLAUDE.md ("Trace and debug" section in the project root) refers to analytical pipelines (dissect, agora), not whisker. whisker's tapetum lane writes debug artifacts but not a trace file.

4. **VLM lane status:** 788 LOC across 5 files (`vlm_pipeline.py`, `vlm_diff.py`, `vision.py`, `vision_task.py`, `transcribe.py`). Known gap #4 in CLAUDE.md: "never reached integration. Decision pending: delete vs. quarantine behind a feature flag." Tests exist (test_vlm_lane.py: 34 tests, all pass) but these are unit tests on data models, not integration. **Status:** dormant library path, must NOT be reported as production coverage.

5. **"No fact has been human-blessed yet":** All 37 verified facts were authored AND verified by the agent, not by a human. CLAUDE.md Known gaps #12 acknowledges this honestly. **Status:** weaker independence claim than ideal.

---

## Package metadata

```
name = "whisker"
version = "0.5.0"
description = "Deterministic QA verdict + benchmark for tomd conversions (no LLM)"
license = BSL-1.0
requires-python = ">=3.12"
build-backend = hatchling
```

## Schema version

`WHISKER_SCHEMA_VERSION = 4` — bumped through 4 releases:
- v1: initial
- v2: guard baseline gained tool_versions
- v3: scoring-v2 (content_recall, null-eligibility, mistune-parsed headings)
- v4: golden-ideal panel (5 nullable ideal_* fields)
