# C01 Claims and Fresh Baseline

Auditor: C01 (Claims and Fresh Baseline)
Date: 2026-07-20
Scope: `packages/whisker/` at the audited worktree state below.

## 1. Worktree boundary

| Field | Value |
|---|---|
| Date | 2026-07-20 18:38 UTC+2 |
| HEAD | `51cb704610220d31c9d5e078b1350c1b37a8714a` |
| Subject | `whisker: probe the Alliance server health endpoint` |
| Branch | `main` |
| Origin | `https://github.com/sabriguenes/wg21-paperflow-workspace.git` |
| Upstream | `https://github.com/cppalliance/wg21-paperflow.git` |

### Committed vs local modifications

The worktree has extensive **uncommitted local modifications** in `packages/whisker/`. The audited state is HEAD + the working tree. Key modified whisker files:

**Source (modified):** `CLAUDE.md`, `__main__.py`, `corpus_tools.py`, `golden.py`, `metrics.py`, `tapetum_llm/cli.py`, `tapetum_llm/constants.py`, `tapetum_llm/fusion.py`, `tapetum_llm/fusion_report.py`, `tapetum_llm/inspect_report.py`, `tapetum_llm/models.py`, `tapetum_llm/pdf_judge.py`, `tapetum_llm/tapetum_llm.md`, `tapetum_llm/transcribe.py`, `tapetum_llm/vision.py`, `tapetum_llm/vision_task.py`, `tapetum_llm/vlm_diff.py`, `tapetum_llm/vlm_pipeline.py`

**Source (untracked/new):** `tapetum_llm/ideal_verify.py`

**Tests (modified):** `test_check_facts_main.py`, `test_facts.py`, `test_fusion.py`, `test_golden.py`, `test_golden_ideals.py`, `test_incremental.py`, `test_menu.py`, `test_pdf_judge.py`, `test_readback.py`, `test_score_file.py`, `test_tapetum_llm.py`, `test_tapetum_llm_eval.py`, `test_unit_models.py`

**Tests (untracked/new):** `test_ideal_verify.py`

**Other modified:** `corpus/README.md`, `tests/fixtures/score-baseline.json`

This is not a clean-commit audit. Every finding references this combined state.

## 2. Environment

| Component | Version |
|---|---|
| OS | Windows NT 10.0.26200.0 |
| Python | 3.12.10 |
| uv | 0.9.13 |
| pytest | 8.4.2 |

## 3. Package metadata

| Field | Value |
|---|---|
| Name | whisker |
| Version | 0.5.0 |
| License | BSL-1.0 |
| requires-python | >=3.12 |
| Build backend | hatchling |
| Wheel | `whisker-0.5.0-py3-none-any.whl` (builds successfully) |
| WHISKER_SCHEMA_VERSION | 4 |
| FUSION_SCHEMA_VERSION | 4 |

### Core dependencies

`apted>=1.0.3`, `grits-metric>=0.6.0`, `lxml>=5.0.0`, `markitdown[pdf]>=0.1.6`, `mistune~=3.2.0`, `numpy>=1.26`, `paperstore`, `pylatexenc>=2.10`, `rapidfuzz>=3.14.5,<4`, `rich>=13.0`, `scipy>=1.11`, `tomd`

### Optional `tapetum-llm` extra

`openai`, `pipeline`, `pydantic-ai`, `pydantic>=2.0`, `python-dotenv>=1.0`

### CLI entry points

| Script | Module |
|---|---|
| `whisker` | `whisker.__main__:main` |
| `whisker-tapetum-llm` | `whisker.tapetum_llm.cli:main` |
| `whisker-readback` | `whisker.tapetum_llm.readback_cli:main` |

## 4. Source and test inventory

| Category | Files | LOC |
|---|---|---|
| Source (`src/whisker/`) | 43 | 15,589 |
| Tests (`tests/`) | 36 | 14,436 |
| **Total** | **79** | **30,025** |

Exclusions: `__pycache__/`, `research/`, vendored repos, `.pyc`.

### Source file inventory (43 files)

**Core (19):** `__init__.py`, `__main__.py`, `anchors.py`, `bench.py`, `calibrate.py`, `constants.py`, `corpus_tools.py`, `facts.py`, `gates.py`, `golden_ideals.py`, `golden.py`, `guard.py`, `match.py`, `menu.py`, `metrics.py`, `reference.py`, `report.py`, `score.py`, `tables.py`

**tapetum_llm (24):** `__init__.py`, `adjudicate.py`, `chunking.py`, `cli.py`, `constants.py`, `fusion_report.py`, `fusion.py`, `grounding.py`, `html_outline.py`, `ideal_verify.py`, `inspect_report.py`, `judge_task.py`, `models.py`, `pdf_judge.py`, `readback_cli.py`, `readback.py`, `source_router.py`, `textlayer.py`, `transcribe.py`, `unit_judge.py`, `vision_task.py`, `vision.py`, `vlm_diff.py`, `vlm_pipeline.py`

### Test file inventory (36 files)

`test_anchors.py`, `test_bench.py`, `test_calibrate.py`, `test_check_facts_main.py`, `test_claude_invariants.py`, `test_comprehension_corpus.py`, `test_dev_replay_acceptance.py`, `test_dev_replay_schema.py`, `test_edit_distance_parity.py`, `test_facts.py`, `test_fusion.py`, `test_gates.py`, `test_golden_ideals.py`, `test_golden.py`, `test_guard.py`, `test_html_outline.py`, `test_ideal_verify.py`, `test_incremental.py`, `test_invariants.py`, `test_match.py`, `test_menu.py`, `test_metrics.py`, `test_pdf_judge.py`, `test_readback.py`, `test_reference.py`, `test_report.py`, `test_score_file.py`, `test_score_pinning.py`, `test_score.py`, `test_source_aware_integration.py`, `test_source_router.py`, `test_tapetum_llm_eval.py`, `test_tapetum_llm.py`, `test_unit_judge.py`, `test_unit_models.py`, `test_vlm_lane.py`

## 5. Baseline test evidence

**Command:** `uv run --package whisker pytest packages/whisker/tests -v --tb=short`
**Working directory:** `c:\Users\sabo2\Desktop\cppalliance`
**Exit code:** 0
**Result:** **1406 passed, 8 skipped, 3 xfailed in 27.65s**

No failures. 8 skips and 3 expected failures are within normal bounds.

## 6. CLI help surfaces

### `whisker -h`

```
whisker command-line entry point.

Commands:

    whisker [PID ...] [--all] [--json] [--no-write] [--gate {pass,review,fail}]
            [--reference ENGINE | --no-reference]
    whisker bench       --corpus DIR [--baseline FILE] [--out FILE]
    whisker guard       --corpus DIR --baseline FILE [--update] [--slack F]
                        [--fail-on-new] [--out FILE]
    whisker golden      --corpus DIR [--update] [--fail-on-new] [--out FILE]
    whisker facts       --corpus DIR [--strict] [--out FILE]
    whisker calibrate   --labels FILE [--target-fpr F] [--out FILE]
    whisker score-file  --md FILE [--ref FILE] [--source FILE] [--json]
    whisker check-facts --md FILE [--facts FILE] [--anchors FILE] [--json]
    whisker corpus      {stratify --corpus DIR | draft PID... --out DIR}
```

All documented commands are exposed: bare scoring, bench, guard, golden, facts, calibrate, score-file, check-facts, corpus stratify, corpus draft.

### `whisker-tapetum-llm -h`

```
Advisory LLM conversion-fidelity adjudication.

positional arguments:
  pids                  Paper IDs to adjudicate (case-insensitive).

options:
  --review-all, --debug, --trace, --inspect, --workspace, --service SLOT=NAME,
  --concurrency N, --fuse-only, --text-only, --incremental, --force
```

### Exit codes (documented contract)

| Code | Meaning |
|---|---|
| 0 | ok |
| 1 | error |
| 3 | review |
| 5 | fail |

`whisker-tapetum-llm` uses a separate contract: advisory verdicts exit 0; operational errors exit 1.

## 7. Corpus, holdout, and ideal inventory

### Comprehension corpus (5 papers, 37 verified facts)

| Paper | Facts | Expected.md | Validation.md | Canary |
|---|---|---|---|---|
| P4182R0 | 8 | Yes | Yes | scrambled table cell |
| P4185R0 | 9 (4 math) | Yes | Yes | flipped math relation |
| P4234R0 | varied | Yes | No | mangled code snippet |
| N5040 | varied | Yes | No | n/a |
| P0876R23 | varied | Yes | No | n/a |

### Dev-replay set

`corpus/dev-replay/labels.json`: 9 golden PRs (#282-#286, #290, #293-#295).

### Holdout

`corpus/holdout/manifest.json` + 4 anchor files: `p0533r9`, `p1112r4`, `p3714r0`, `p4182r0`. p0533r9 quarantined (PR #293).

### tomd golden ideals (4 files)

`cwg1.md`, `p4020r0.md`, `p4182r0.md`, `p4228r0.md`

### SHA-256 hashes of load-bearing corpus inputs

```
ED33C5..A6B0  corpus/EXAMPLE.facts.jsonl
524764..4F6B  corpus/N5040.expected.md
967785..FF6BB corpus/n5040.facts.jsonl
2681F0..31E1  corpus/P0876R23.expected.md
97253E..B57D  corpus/p0876r23.facts.jsonl
BFC2D8..6722  corpus/P4182R0.expected.md
C0B33E..F82D  corpus/P4182R0.facts.jsonl
844906..D16722 corpus/P4182R0.validation.md
DB47F3..8763  corpus/P4185R0.expected.md
E501B0..90AE  corpus/P4185R0.facts.jsonl
BA8742..B94E0 corpus/P4185R0.validation.md
DAECAE..9298  corpus/P4234R0.expected.md
A92B21..2A87  corpus/p4234r0.facts.jsonl
89C76B..CB43  corpus/dev-replay/labels.json
065F27..DD19  corpus/holdout/manifest.json
4DB898..DF03  tomd/ideals/cwg1.md
919F43..D08F  tomd/ideals/p4020r0.md
7B6960..4306  tomd/ideals/p4182r0.md
BBAD0E..3697  tomd/ideals/p4228r0.md
```

## 8. Named constants (deterministic thresholds)

| Constant | Value | Purpose |
|---|---|---|
| UNIGRAM_COVERAGE_FAIL_EDGE | 0.85 | Hard fail: content missing |
| UNIGRAM_COVERAGE_REVIEW_EDGE | 0.95 | Soft review: some words missing |
| REF_NID_ADVISORY_EDGE | 0.85 | Advisory review: oracle disagreement |
| NID_FLOOR | 0.9 | Lane 2 bench/guard floor |
| TEDS_FLOOR | 0.8 | Lane 2 bench/guard floor |
| MHS_FLOOR | 0.8 | Lane 2 bench/guard floor |
| CONTENT_RECALL_FLOOR | 0.9 | Lane 2 bench/guard floor |
| QA_SCORE_SOFT_EDGE | 70 | Soft review edge |
| WHISKER_SCHEMA_VERSION | 4 | Sidecar schema |
| CONFIDENCE_AMBIGUOUS_LO | 0.35 | Cascade escalation low |
| CONFIDENCE_AMBIGUOUS_HI | 0.65 | Cascade escalation high |
| CONFIDENCE_DECISION_FLOOR | 0.50 | Verdict confidence floor |
| MAX_PAPER_MD_CHARS | 500,000 | Chunk split threshold |
| PDF_JUDGE_RECALL_FLOOR | 0.85 | PDF judge demotion floor |
| PDF_JUDGE_NID_FLOOR | 0.80 | PDF judge demotion floor |
| PAGE_RECALL_FLOOR | 0.90 | Per-page screen floor |
| MAX_PAGE_ESCALATIONS | 5 | Page escalation cap |
| FUSION_SCHEMA_VERSION | 4 | Fusion schema |
| FUSION_REF_NID_FLOOR | 0.10 | Clear guardrail |

## 9. Service configuration

### Active services (from SERVICES.toml)

| Name | Backend | Model | Endpoint |
|---|---|---|---|
| alliance-pod | vllm_thinking | deepseek-v4-pro | `sgjy18glyi4blu-8000.proxy.runpod.net` |
| h200x8-deepseek-v4-pro | vllm_thinking | deepseek-v4-pro | `w80putgan2qou8-8000.proxy.runpod.net` |
| anthropic-opus | anthropic | claude-opus-4-6 | Anthropic API |

### Endpoint reachability

| Service | Status |
|---|---|
| alliance-pod | **BLOCKED**: `ALLIANCE_POD_KEY` not set. Health endpoint returns HTTP 401 (Unauthorized). Pod infrastructure reachable but authentication unavailable. |

**Consequence:** The 10-scenario real-LLM runtime matrix (Runbook section 8) cannot execute. This is recorded as definitive credential denial per section 14.5. Runtime-dependent claims (C-LLM, C-EXIT operational) are marked blocked/unproven.

## 10. Core import verification

```
uv run --package whisker python -c "import whisker; print(dir(whisker))"
```

**Exit code:** 0. Core whisker imports without the `tapetum-llm` extra. Public exports include all documented symbols: `WhiskerResult`, `score_paper`, `score_markdown`, `run_bench`, `check_facts`, `diff_goldens`, `run_gates`, `teds`, `mhs`, `text_nid`, etc.

## 11. Fresh claims registry

### C-VER: Version phase

**Value:** `0.5.0` (pre-1.0)
**Evidence:** `pyproject.toml` line 3. Pre-stable; no semver guarantee on public API.

### C-API: Public API stability

**Value:** Unstable (pre-1.0, no documented stability promise)
**Evidence:** Version 0.5.0. `__init__.py` re-exports a substantial surface (`WhiskerResult`, `score_paper`, `run_bench`, etc.) but no `@deprecated` markers or compatibility layer.

### C-CAL: Calibration status

**Value:** Provisional/uncalibrated
**Evidence:** CLAUDE.md "Calibration status" section: `UNIGRAM_COVERAGE_*` and `REF_NID_ADVISORY_EDGE` are "adopted from external repos, not fitted on our own labeled corpus." The `calibrate` command exists but has not been applied.

### C-LAB: Role of labels, snapshots, facts, and ideals

**Value:** Lane 1 snapshots (5 papers), Lane 2 GT (0 papers, no `.gt.md` files), Lane 3 facts (5 papers, 37 verified), tomd ideals (4 papers), holdout (4 papers). Readback validation (2 papers).
**Evidence:** Corpus inventory above. The corpus is small but covers multiple structural strata.

### C-INF: Default inference deployment

**Value:** Self-hosted open-weight (vllm_thinking on RunPod)
**Evidence:** SERVICES.toml: `alliance-pod` runs `deepseek-v4-pro` via vllm. Model-sovereignty doctrine in CLAUDE.md.

### C-COMP: Comprehension claim

**Value:** Deterministic source-verified facts gate in CI; one-time LLM readback validation out of band.
**Evidence:** `test_comprehension_corpus.py` is hermetic. 34/37 pass on grounded readback (CLAUDE.md). 3 fails are model column-alignment misreads.

### C-PROD: Production-operations claim

**Value:** Pre-production (0.5.0, no formal deployment, single-operator use)
**Evidence:** No deployment docs, no monitoring, no SLA. Used by project developers.

### C-DET: Technical determinism tier

**Value:** Deterministic core (no LLM, no network, no randomness). Advisory LLM lane is non-deterministic by design (>= 25% verdict-flip rate documented).
**Evidence:** CLAUDE.md invariants: "Every metric is a pure function of its inputs." Advisory lane instability documented: "Identical reruns show >= 25% verdict-flip rate."

### C-LIC: Outbound and bundled licenses

**Value:** BSL-1.0 (whisker). Dependencies: MIT (rapidfuzz, apted, grits-metric), BSD (numpy, scipy, lxml), MIT (mistune, markitdown), LGPL-3.0+ (pylatexenc).
**Evidence:** `pyproject.toml` license field. Dependency licenses from PyPI metadata.

### C-INT: Merged implementation interoperability

**Value:** `score-file` and `check-facts` (Sean's file bridge) coexist with the user's interactive menu, tapetum, readback, corpus tools.
**Evidence:** CLI help shows both file commands and workspace commands. Three entry points registered.

### C-VIS: Merged function visibility

**Value:** All commands visible in `-h` output.
**Evidence:** `whisker -h` lists `score-file`, `check-facts`, `bench`, `guard`, `golden`, `facts`, `calibrate`, `corpus`.

### C-IDEAL: Ideal discovery and authority

**Value:** 4 tomd ideals discovered read-only. Source remains factual authority. Ideal is structural reference.
**Evidence:** `golden_ideals.py` auto-discovers from `packages/tomd/tests/fixtures/golden/ideals/`. CLAUDE.md: "The staged PDF/HTML source remains the factual authority."

### C-LLM: LLM paths claimed operational

**Value:** tapetum-llm (PDF judge + text cascade + ideal verifier + fusion), readback. VLM lane dormant.
**Evidence:** Three CLI entry points. VLM code present (5 files, ~788 LOC) but no production command.

### C-EXIT: Exit contracts

**Value:** whisker: 0/1/3/5. tapetum-llm: advisory exits 0, operational errors exit 1.
**Evidence:** CLAUDE.md "Exit codes" section. `constants.py`: `EXIT_OK=0, EXIT_ERROR=1, EXIT_REVIEW=3, EXIT_FAIL=5`.

## 12. Findings

### F01 (Medium): Extensive uncommitted modifications

The audited state includes substantial uncommitted changes across 18+ source files and 13+ test files. This makes the audit boundary less reproducible: another agent at the same HEAD would see different code.

### F02 (High): Real-LLM runtime evidence blocked

`ALLIANCE_POD_KEY` is not set. The 10-scenario runtime matrix (Runbook section 8) cannot execute. Runtime-dependent gates (G1 partial, G2 partial, G5 partial) and dimensions (D1, D3, D6) lack mandatory current proofs. This triggers stop condition 14.5.

### F03 (Low): No `.gt.md` ground-truth files

Lane 2 fidelity bench has no committed ground-truth references. `bench`/`guard` exist but have nothing to bench against in the current corpus.

### F04 (Informational): Calibration edges remain provisional

All coverage/NID edges are adopted from external repos, not fitted. The `calibrate` command exists but has not produced committed operating points.

## 13. Gate and dimension mapping

| Gate | C01 evidence | Status |
|---|---|---|
| G1 Advisory non-leakage | Code inspection needed (C03) | Pending |
| G2 Fail-not-partial | Fault injection needed (C04) | Pending |
| G3 Deterministic replay | Replay needed (C05) | Pending |
| G4 Per-axis evaluation | Code inspection needed (C06) | Pending |
| G5 Untrusted-input mediation | Runtime needed (C07) | Pending |
| G6 Inverted canary | Canary run needed (C08) | Pending |
| G7 Licensing | Inspection needed (C09) | Pending |

## 14. Limitations

- Worktree is not a clean commit. Reproducibility requires the same uncommitted modifications.
- Real-LLM runtime evidence is completely blocked by missing credentials.
- No runtime workspace (WG21_DATA_DIR) configured, so workspace-dependent commands (bare `whisker`, `whisker-tapetum-llm`) cannot run outside tests.

## 15. Conclusion

The C01 baseline establishes a comprehensive snapshot of whisker 0.5.0 at the audited worktree state. The test suite passes cleanly (1406/1406, 8 skip, 3 xfail). The package builds, imports, and exposes all documented CLI surfaces. The primary blocker is credential denial for the alliance-pod endpoint, which prevents the mandatory real-LLM runtime matrix. All subsequent role reports must derive their evidence from this baseline and the current code/test state, not from Audit v1.
