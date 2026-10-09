# C02 Deterministic Core

**Role:** Audit pure paths in whisker core for determinism violations.
**Audited state:** whisker 0.5.0, HEAD 51cb704, Python 3.12.10, pytest 8.4.2.
**Date:** 2026-07-20

## 1. Scope

Verify that the whisker scoring pipeline (`score.py`, `metrics.py`, `match.py`,
`gates.py`, `facts.py`, `golden.py`, `constants.py`) contains no randomness,
no network access, no LLM calls in the scoring path, uses sorted outputs for
unordered collections, employs pure functions, and has no mutable shared state.

## 2. Commands and Exits

| Evidence | Command / source | Exit |
|----------|-----------------|------|
| E1 | Full test suite 1406p/8s/3x | 0 |
| E3 | Golden/guard/fusion/incremental/gates 284p | 0 |
| E4 | Core metric/scoring 218p | 0 |
| E10 | Deterministic replay via test assertions | 0 |

## 3. Current Evidence

### 3.1 No randomness

Inspected all imports across the 7 audited modules. None import `random`,
`uuid`, `secrets`, `os.urandom`, or any PRNG source. No `time.time()` calls
seed any computation. All arithmetic is deterministic floating point (IEEE-754).

- `metrics.py` uses `rapidfuzz.distance.Levenshtein` (deterministic SIMD),
  `apted.APTED` (deterministic tree edit), `lxml`/`mistune` parsers
  (deterministic DOM/AST). Lines 64-78: `normalized_edit_distance` is a pure
  function of two string inputs.
- `match.py` uses `scipy.optimize.linear_sum_assignment` (deterministic
  Hungarian algorithm) and `numpy` cost matrices built by iteration (lines
  110-116). Fuzzy rescue scans in index order explicitly for determinism
  (line 188 comment: "Scan in index order for determinism; first qualifying
  pred wins").
- `facts.py` uses `rapidfuzz.fuzz.partial_ratio_alignment` (deterministic)
  and a hand-written substring edit distance DP (lines 276-296, pure).

### 3.2 No network, no LLM

No `http`, `requests`, `urllib`, `socket`, `httpx`, `openai`, `pydantic_ai`
imports in any of the 7 modules. The scoring path from `score_markdown` through
`_decide` to verdict is entirely local computation. The `tapetum_llm` advisory
lane is a separate optional extra, imported nowhere in these modules.

### 3.3 Sorted outputs

- `score.py` line 129: `hard_flags=sorted(self.hard_flags)` in `to_dict()`.
- `score.py` line 130: `soft_flags=sorted(self.soft_flags)`.
- `score.py` line 283: `_region_dicts` sorts regions by `token_start`.
- `golden.py` line 191: `diff_goldens` sorts items by pid before evaluation.
- `golden.py` line 150: `GoldenReport.to_dict()` sorts findings by pid.
- `bench.py` line 211: `run_bench` returns `sorted(rows, key=lambda r: r.pid)`.
- `bench.py` line 247: `aggregate` sorts `below` list by pid.
- `guard.py` line 85: `collect_tool_versions` sorts package names.
- `guard.py` line 345: `checked` axes list is sorted.
- `facts.py` line 595: table neighbor directions sorted by canonical order.

### 3.4 Pure functions, no mutable shared state

All key data structures are frozen dataclasses:
- `GateResult` (gates.py:26): `@dataclass(frozen=True)`
- `BlockMatch` (match.py:56): `@dataclass(frozen=True)`
- `BlockMetrics` (match.py:222): `@dataclass(frozen=True)`
- `Fact`, `FactCheck`, `FactReport` (facts.py:96,119,137): all `frozen=True`
- `GoldenItem`, `GoldenFinding`, `GoldenReport` (golden.py:93,107,121): all `frozen=True`
- `BenchRow` (bench.py:57): `@dataclass(frozen=True)`
- `GuardFinding`, `GuardReport` (guard.py:139,174): both `frozen=True`

Module-level state is limited to compiled regex patterns and named constants,
which are immutable. No module-level mutable containers (no global dicts, lists,
or sets that accumulate state across calls).

### 3.5 Explicit determinism tests

- `test_metrics.py::test_metrics_are_deterministic` (line 244): asserts
  `teds(a,b) == teds(a,b)` and `mhs(a,b) == mhs(a,b)` on identical inputs.
- `test_match.py::test_match_blocks_is_deterministic` (line 95): asserts
  block matching produces identical `(gt_index, pred_indices)` on repeated
  invocations.
- `test_fusion.py::TestFusionDeterminism` (line 700): asserts identical dict
  output and stable 16-char fingerprints across repeated `fuse_verdicts` calls.

### 3.6 Constants are named, not bare literals

`constants.py` defines all thresholds as module-level named constants:
`UNIGRAM_COVERAGE_FAIL_EDGE`, `UNIGRAM_COVERAGE_REVIEW_EDGE`, `DRIFT_SOFT_EDGE`,
`REGION_SOFT_COUNT`, `QA_SCORE_SOFT_EDGE`, `TEDS_FLOOR`, `MHS_FLOOR`,
`NID_FLOOR`, `CONTENT_RECALL_FLOOR`, `REF_NID_ADVISORY_EDGE`,
`BENCH_REGRESSION_SLACK`, `GUARD_AXIS_SLACK`, `BLOCK_ACCEPT_NED`,
`BLOCK_FUZZY_RESCUE_NED`, `BLOCK_MATRIX_CELL_BUDGET`. The `_decide` function
in `score.py` (lines 136-231) references only these named constants, never
bare numeric literals.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | All scoring-path modules are free of randomness, network, and LLM imports | PASS | HIGH |
| F2 | All unordered outputs are sorted before serialization (10+ sort sites confirmed) | PASS | HIGH |
| F3 | All data structures in the scoring path use frozen dataclasses | PASS | HIGH |
| F4 | No mutable module-level state exists in the 7 audited modules | PASS | HIGH |
| F5 | Three explicit determinism tests confirm repeatability at metrics, match, and fusion levels | PASS | HIGH |
| F6 | `_INLINE_REG` regex in metrics.py (line 140) lacks `re.DOTALL`, so display math `\[...\]` spanning newlines is not folded by `textblock2unicode`. This is an intentional design choice (documented in facts.py:214-235) to avoid shifting the whole-document NID axis, with a scoped pre-fold in `_math_surface` for facts only. | INFO | HIGH |
| F7 | `_AST_RENDERER` in metrics.py (line 562) is a module-level mistune instance. It is stateless between calls (mistune renderers do not accumulate state), so this is safe. | INFO | HIGH |

## 5. False-Pass Hypothesis and Falsification

**Hypothesis:** The determinism tests could pass vacuously if they test only
trivial inputs that happen to be deterministic while a complex code path
introduces non-determinism.

**Falsification:** The `test_match_blocks_is_deterministic` test uses three
distinct prose paragraphs in reordered blocks, exercising the full
normalize-matrix-Hungarian-assign pipeline. The
`TestFusionDeterminism::test_same_input_same_dict` test exercises JSON
serialization including `sort_keys=True` and verifies byte-identical output.
The test_score_pinning suite pins 19 papers' gate+QA scores against a committed
baseline, catching any non-deterministic drift across the full scoring path.

## 6. Gate/Dimension Mapping

| Gate | Dimension | Status |
|------|-----------|--------|
| G3: Scoring determinism | D2: Reproducible scoring pipeline | PASS |

## 7. Limitations

- The determinism tests assert same-process repeatability. Cross-platform
  determinism (e.g., different numpy/scipy builds producing different
  Hungarian assignments for degenerate cost matrices) is not tested. This is
  mitigated by pinning dependency ranges in pyproject.toml.
- IEEE-754 floating-point arithmetic can produce different results across
  CPU architectures for the same operations. The guard module rounds to
  4 decimal places (`_NDIGITS = 4`) as a mitigation.

## 8. Conclusion

The whisker scoring core is deterministic by construction: pure functions on
frozen dataclasses, no RNG/network/LLM, sorted outputs, named constants, and
three levels of determinism testing (unit, integration, 19-paper score pinning).
No violations found.
