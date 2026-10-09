# C02 Deterministic Core

**Role**: Audit the deterministic lane (gates, metrics, verdict trichotomy, purity, reproducibility) for determinism violations and for whether it currently reproduces its own historical scores.
**Audited state**: whisker 0.5.0, working tree, manifest b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771 (HEAD 0d18a65 + 7205 uncommitted insertions).
**Gates**: G3 (Scoring determinism / reproducible pipeline).

## 1. Scope

`score.py`, `gates.py`, `metrics.py`, `constants.py`, `bench.py`: no randomness, no network, no LLM in the scoring path; sorted unordered outputs; frozen/pure data structures; the verdict trichotomy (`_decide`) as the single source of `pass`/`review`/`fail`; and whether the deterministic core currently reproduces its own pinned baseline (E1).

## 2. Commands and Exits

| Evidence | Command / source | Exit |
|---|---|---|
| E1 | `uv run --package whisker pytest packages/whisker/tests -q --tb=line` | **1** (3 failed, 1784 passed, 8 skipped, 3 xfailed) |
| E9 | `--gate` matrix, 3 representative papers | 0 / 3 / 5 per row, exact contract |
| E10 | separate-process replay, 3 papers x 2 runs | 0 (both runs); stdout byte-identical |
| E11 | fault injection, 5 cases | 1 (x4), 5 (x1); never 0 |
| E12 | `--no-write` file-count check | 0 files added/changed |
| E18 | canary C4 (14 mangled code spans) | n/a (metric-value comparison, not exit code) |

## 3. Current Evidence

### 3.1 No randomness, network, or LLM in the scoring path

`score.py:1-40` imports only `paperstore.backend`, `tomd.lib.check_content`, `tomd.lib.pdf.qa`, and whisker-internal modules (`constants`, `bench`, `gates`, `golden_ideals`, `metrics`, `reference`). No `random`, `uuid`, `secrets`, `os.urandom`, `http`, `requests`, `httpx`, `openai`, or `pydantic_ai` import appears in `score.py`, `gates.py`, `metrics.py`, or `bench.py`. `gates.py` is pure `re` and string splitting (`gates.py:17-219`). `metrics.py` uses `rapidfuzz.distance.Levenshtein`, `apted.APTED`, `lxml`, `mistune`, `pylatexenc` (`metrics.py:28-41`), all deterministic parsers/algorithms; the only stateful module-level object is `_AST_RENDERER = mistune.create_markdown(...)` (`metrics.py:562`), a stateless renderer reused across calls (consistent with Auditv2 F7, not re-derived independently here).

### 3.2 Verdict trichotomy: exactly two hard triggers

`_decide` (`score.py:136-231`) is the single function producing `(verdict, hard_flags, soft_flags)`. Its only two `hard.append` call sites are:

- `score.py:179`: a failing `GateResult` from `gates.py`.
- `score.py:182`: `unigram_coverage < C.UNIGRAM_COVERAGE_FAIL_EDGE` (0.85, `constants.py:37`).

Every other signal (region mismatch, `unigram_drift`, `qa_score`, `uncertain_count`, `ref_nid`, ideal axes) only reaches `soft.append` (`score.py:187,191,194,196,198,203,215`). `score.py:217-231` then folds: any `hard` -> `VERDICT_FAIL`; else a benign-region-only soft set at `unigram_coverage >= REGION_BENIGN_UNIGRAM_FLOOR` (0.95) folds to `VERDICT_PASS` with flags annotated `(benign)`; else any remaining `soft` -> `VERDICT_REVIEW`; else `VERDICT_PASS`. This is an unconditional, input-only function: no I/O, no clock, no global state read.

### 3.3 Data structures: mostly frozen, one exception

`GateResult` (`gates.py:26`, `@dataclass(frozen=True)`), `BenchRow` (`bench.py:57`, `@dataclass(frozen=True)`) are immutable. `WhiskerResult` (`score.py:58-59`), the top-level scoring result, is a **plain `@dataclass`, not frozen**. No mutation site was found: a targeted search of `score.py`, `report.py`, and `__main__.py` for attribute assignment on a `WhiskerResult`/`result` instance (`result.<field> =`, `setattr(...)`) returned zero matches, and `to_dict()` (`score.py:97-133`) only reads fields. So the class is mutable by construction but is not observed to be mutated anywhere in the current codebase; see Finding F5.

### 3.4 Sorted outputs

`score.py:129-130`: `hard_flags=sorted(...)`, `soft_flags=sorted(...)` in `to_dict()`. `score.py:283`: `_region_dicts` sorts by `token_start` before capping at `REGION_DETAIL_CAP`. `bench.py:211`: `run_bench` returns `sorted(rows, key=lambda r: r.pid)`. No unsorted set/dict iteration was found feeding a serialized field in the four scoped modules.

### 3.5 Exit-code and separate-process reproducibility (live)

E9 reproduced the documented exit contract exactly on 3 representative papers (pass/review/fail), with `--gate pass|review|fail` producing 0/3/5 as specified, no deviation. E10 scored the same 3 papers twice each in **separate OS processes** and hashed stdout JSON: 3 of 3 pairs byte-identical. E12 confirmed `--no-write` adds and changes zero files on disk for a real paper. E11 confirmed no fault-injection case (unknown pid, empty markdown, binary-as-markdown, corrupt PDF as source, missing markdown) produces exit 0; the empty-markdown case correctly scores exit 5 (a fidelity fail, not silently skipped).

### 3.6 The suite is RED, and the failures are inside the reproducibility mechanism itself

E1: `3 failed, 1784 passed, 8 skipped, 3 xfailed`. This is not a peripheral failure. Two of the three are inside `test_score_pinning.py` (`packages/whisker/tests/test_score_pinning.py:170,181`), the exact mechanism whose stated purpose is "any change to tomd golden output *or* whisker scoring logic shows up as a diff in one file" (`test_score_pinning.py:14-15`):

- `test_score_pinned[p3556r0]`: `gate mismatch` (`test_score_pinning.py:170-171`), i.e. `run_gates()` currently returns a different pass/fail per-gate map for the `p3556r0` golden markdown than the committed `score-baseline.json` records.
- `test_score_pinned[p2040r0]`: `max_heading_level mismatch: actual=3, expected=4` (`test_score_pinning.py:181`), a field sourced from `tomd.lib.pdf.qa.compute_metrics` (`test_score_pinning.py:91,97`), not from whisker's own gate/metric code, but pinned through whisker's harness.

Both mismatches score **tomd's own committed golden markdown files** (`_golden_md_path`, `test_score_pinning.py:66-79`), not a live conversion. Given `00-PRECONDITIONS.md` §1 (44 files changed across `packages/whisker` **and** `packages/tomd`, 7205 insertions, all uncommitted), the most parsimonious explanation is that an uncommitted change to a tomd golden fixture or to tomd's/whisker's parsing logic has not yet been reconciled into `score-baseline.json`. This audit did not adjudicate which side changed; what is certain is that **the deterministic core does not currently reproduce its own pinned baseline for 2 of 19 pinned papers**, and the CI safety guard that exists specifically to prevent silent, unreviewed baseline updates (`WHISKER_PIN_UPDATE=1` forbidden under `CI=true`, per Auditv2 C05 §3.1, not re-verified live this run) means these two mismatches are sitting unresolved rather than silently absorbed.

The third failure, `test_dev_replay_schema.py::TestHoldoutAnchors::test_locked_candidate_dispositions` (`test_dev_replay_schema.py:190`, `AssertionError: p4182r0`), is a SHA-256 mismatch on the **locked candidate markdown** for the holdout paper `p4182r0` (`assert _sha256(candidate_path) == fixture["candidate_sha256"], pid`, `test_dev_replay_schema.py:190`). This means the staged candidate artifact for `p4182r0` in the dev-replay holdout no longer matches the fingerprint it was locked under, again consistent with an uncommitted conversion-side change outrunning the locked fixture. This is a fingerprint-pinning failure adjacent to, but distinct from, the score-pinning failures above (it locks a candidate file's hash, not a gate/metric value).

### 3.7 Metrology floor: what the deterministic surface can and cannot represent (E18)

E18 (canary C4): a token-preserving corruption of 14 `<memory_resource>` code spans (each `<memory_resource>` became `<memory_resource<`) produced **numerically identical** `text_nid` (0.8645), `content_recall` (0.9697), and `unigram_coverage` (0.9542) versus the untouched control. This is not a tuning gap in the coverage edges; it is structural. `clean_string` (`metrics.py:118-126`) keeps only `\w` (word) characters plus CJK and strips everything else via `_CLEAN_KEEP_RE = re.compile(r"[^\w\u4e00-\u9fff]")` (`metrics.py:115`); the corrupted character is the closing angle bracket `>`, which is already outside `\w` and is stripped by the SAME normalizer on both the corrupted and uncorrupted side, so the two normalized strings differ only in a character neither side's edit-distance/token-recall computation ever sees. `content_tokens` (`metrics.py:359-373`) tokenizes on `\w+` (`_CONTENT_TOKEN_RE`), which never includes `<`/`>` either. The deterministic text axes are therefore, by construction, blind to punctuation-only corruption inside an otherwise-intact word stream. This is a scope boundary of the metric surface, not a bug in `_decide`'s two-hard-trigger logic (§3.2): the corruption never reaches `_decide` as a signal at all, on either the fail or the pass side.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---|---|---|
| F1 | The scoring-path modules (`score.py`, `gates.py`, `metrics.py`, `bench.py`) contain no randomness, network, or LLM imports | Informational | HIGH |
| F2 | `_decide` has exactly two hard-fail trigger sites; every other signal is soft-only by construction | Informational | HIGH |
| F3 | Exit-code contract and separate-process replay reproduced exactly and byte-identically live (E9, E10) | Informational | HIGH |
| F4 | Fault injection never produces a false exit 0 (E11); `--no-write` is inert on disk (E12) | Informational | HIGH |
| F5 | `WhiskerResult` is a mutable (non-frozen) dataclass, unlike its sibling `GateResult`/`BenchRow`; no mutation site exists today, so this is a latent purity gap, not an active defect | Low | MEDIUM |
| F6 | The suite is currently RED (E1); 2 of 3 failures are inside `test_score_pinning.py`, the mechanism specifically built to catch unannounced scoring drift, on tomd's own committed golden fixtures, not live conversion output | **High** | HIGH |
| F7 | The third failure (`test_locked_candidate_dispositions`) is a SHA-256 fingerprint mismatch on the p4182r0 holdout candidate, indicating the staged conversion artifact has drifted from its locked hash | Medium | HIGH |
| F8 | Punctuation-only, token-preserving corruption (14 mangled code spans, E18) is invisible to `text_nid`, `content_recall`, and `unigram_coverage` because the shared normalizer strips the corrupted character on both sides before comparison | Medium | HIGH |

## 5. False-Pass Hypothesis

**Could the deterministic core look reproducible while actually drifting?**

Falsification attempted on two axes. (a) Same-process purity: Auditv2's explicit determinism unit tests (`test_metrics.py::test_metrics_are_deterministic`, `test_match.py::test_match_blocks_is_deterministic`, `test_fusion.py::TestFusionDeterminism`) were not independently re-run in isolation this pass, but E1's aggregate pass count (1784 passing tests) includes these suites among the passing majority (they are not named in the 3 failures), so same-process purity is not contradicted by this run's evidence. (b) Cross-run/cross-artifact reproducibility: E10's separate-process replay (3/3 byte-identical) proves same-input reproducibility for 3 live papers today, but E1's score-pinning failures prove that "same conceptual input, different point in time" is currently NOT reproducing the same score for at least 2 of 19 pinned tomd goldens. Both facts are true simultaneously: the scoring FUNCTION is pure and reproducible given fixed inputs (E10); the INPUTS (tomd golden fixtures, or the gate/metric logic reading them) have drifted since the baseline was pinned (E1). A claim of "the deterministic core is reproducible" that cited only E10 and omitted E1 would be a false pass; this file does not commit that error.

## 6. Gate/Dimension Mapping

**PROPOSED, not a settled verdict.** G3 (Scoring determinism): the underlying scoring FUNCTIONS are pure, sorted, and free of randomness/network/LLM (F1-F4), and live replay reproduces byte-identical output across processes for unchanged inputs (E10). However, the claim that whisker's deterministic core is *currently* consistent with its own committed regression baseline does not hold: 2 of 19 pinned papers mismatch (F6), plus one locked-candidate fingerprint mismatch (F7), all live and unresolved on this tree. PROPOSED: G3 should be scored **CONDITIONAL / NOT CLEAN**, not a flat pass. The planner should weigh whether the mismatches are an uncommitted-tree artifact (per `00-PRECONDITIONS.md`, expected to some degree given 7205 uncommitted insertions) versus a genuine unannounced regression; this file establishes the fact of the mismatch, not its root cause.

## 7. Limitations

- The root cause of the two score-pinning mismatches (tomd golden fixture change vs. logic change) was not isolated in this pass; doing so would require diffing the uncommitted tomd golden fixtures against their last committed state, which is out of this file's scope.
- Cross-platform floating-point determinism (different numpy/scipy builds) is not tested here, consistent with Auditv2's stated limitation, not independently re-verified.
- `WhiskerResult`'s mutability (F5) is a static-inspection finding; the absence of a mutation site was established by a grep-based search, not by a formal data-flow analysis, so a dynamic mutation via a code path outside `score.py`/`report.py`/`__main__.py` cannot be fully excluded.

## 8. Conclusion

The deterministic scoring core is pure by construction (no randomness/network/LLM, two named hard triggers, sorted serialization) and reproduces byte-identical output across separate processes for fixed inputs today (E9, E10, E12). It also fails closed under fault injection (E11). Against that, the suite is RED, and the two most load-bearing failures sit inside the exact regression-detection mechanism this claim depends on (`test_score_pinning.py`), on tomd's own golden fixtures, with a third failure indicating a locked candidate artifact has drifted from its pinned hash. A metrology boundary (E18) further shows the text-similarity axes cannot see punctuation-only corruption by design, not by oversight. The PROPOSED verdict for G3 is conditional, not a clean pass, pending planner adjudication of the tree-state caveat.

## 9. Delta vs Auditv2

Auditv2's C02 (`Auditv2/code-c02-deterministic-core.md`) reported **1406 passed, 8 skipped, 3 xfailed, zero failures** and concluded "No violations found" with a flat PASS mapping for G3/D2. This run's central delta is that the suite regressed to RED (E1: 3 failed), and the regression lands specifically inside the pinning mechanism Auditv2's own §7 Limitations flagged as untested end-to-end ("separate-process replay ... is blocked by the absence of `WG21_DATA_DIR` in CI"). This audit's E10 closes that specific limitation (separate-process replay now proven live, 3/3 identical) while simultaneously surfacing a new one Auditv2 could not have seen (the pinning baseline itself is stale against the current tree). Auditv2 did not identify the `WhiskerResult` mutability gap (F5) or the punctuation-blind-spot metrology boundary (F8, only possible now that live canary evidence, E18, exists); both are new findings in this run. Auditv2's F6/F7 (the `_INLINE_REG` DOTALL note and the stateless `_AST_RENDERER` note) are unchanged and not re-litigated here.
