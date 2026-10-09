# C05 Quality-Stability Replay Audit

**Persona:** C05 -- Quality-Stability Replay Auditor
**Scope:** `packages/whisker/` deterministic scoring path
**Focus:** G3 (determinism by replay), D2 (determinism & reproducibility)
**Contract model:** Quality-stable (semantic equality), not bit-exact

---

## 1. Determinism Contract (from CLAUDE.md)

The whisker `CLAUDE.md` invariants section states:

> **Determinism.** Every metric is a pure function of its inputs. Sort unordered
> collections before output (`hard_flags`, `soft_flags`, bench rows by pid). No
> LLM, no network, no randomness.

The project-level `CLAUDE.md` elaborates the determinism invariants D1-D11.
whisker's scoring path is entirely offline (no LLM calls, no network), so
D1/D4/D5/D6/D9/D10/D11 (LLM-specific) do not apply to the core scoring path.
D7 (sort unordered collections before they feed a prompt) applies at the output
boundary: hard/soft flags and bench rows are sorted.

The contract is **quality-stable**: re-running whisker on the same inputs must
produce the same verdict, the same flags, the same metric values. Bit-exact
reproducibility of LLM outputs is explicitly declared impossible on hosted
endpoints; the deterministic gate is LLM-free by design.

**Verdict:** Contract is clearly documented, scoped, and enforced by
architecture (no LLM in the gate).

---

## 2. `score.py` -- `score_markdown` Purity

### 2.1 Function signature

```
score_markdown(pid, md_text, *, content, reference_md=None, ref_engine=None, ideal_md=None) -> WhiskerResult
```

### 2.2 Analysis

- **Inputs:** `pid` (str), `md_text` (str), `content` (ContentCheckResult from
  tomd), optionally `reference_md`, `ref_engine`, `ideal_md`. All are
  value-typed or frozen dataclass instances.
- **Internal calls:** `compute_metrics` (tomd QA, deterministic regex/AST
  scoring), `run_gates` (deterministic regex gates), `text_nid` / `mhs` /
  `table_score` (deterministic metrics), `score_against_ideal` (deterministic
  metric panel).
- **No side effects:** returns a `WhiskerResult` dataclass. No file I/O, no
  network, no mutation of shared state.
- **No randomness:** zero uses of `random`, `uuid`, `time.time`, `shuffle`,
  `sample`.
- **Output ordering:** `to_dict()` calls `sorted(self.hard_flags)` and
  `sorted(self.soft_flags)` (lines 129-130), and regions are sorted by
  `token_start` (line 283).

**Verdict:** `score_markdown` is a **pure function** of its inputs.

### 2.3 `_decide` Determinism

The verdict function `_decide` takes numeric thresholds and gate results,
produces `(verdict, hard_flags, soft_flags)`. All comparisons use named
constants from `constants.py`. The function is a cascading if/elif chain with
no external state:

1. Iterate gates: failed gate -> append to `hard`.
2. `unigram_coverage` vs `UNIGRAM_COVERAGE_FAIL_EDGE` / `REVIEW_EDGE`.
3. Region count vs `REGION_SOFT_COUNT`.
4. `unigram_drift` vs `DRIFT_SOFT_EDGE`.
5. `qa_score` vs `QA_SCORE_SOFT_EDGE`.
6. `uncertain_count` presence.
7. Optional: `ref_nid` vs `REF_NID_ADVISORY_EDGE` (advisory).
8. Optional: ideal panel axes vs bench floors (advisory).
9. Verdict: `hard` non-empty -> FAIL; benign-region fold -> PASS; `soft`
   non-empty -> REVIEW; else PASS.

The `_is_benign_region_only` helper is a pure predicate on the soft flags list
and the unigram coverage float.

**Verdict:** `_decide` is a **deterministic function** of its numeric inputs.
Same flags in, same verdict out, always.

---

## 3. `metrics.py` -- Metric Determinism

### 3.1 `text_nid(a, b)`

Computes `1.0 - normalized_edit_distance(normalize(a), normalize(b))`.

- `_normalize_text`: regex whitespace collapse. Deterministic.
- `normalized_edit_distance`: `rapidfuzz.distance.Levenshtein.distance(a, b) /
  max(len(a), len(b))`. Levenshtein is a well-defined mathematical function.
  Deterministic.

### 3.2 `teds(html_a, html_b)`

Verbatim PubTabNet/OmniDocBench TEDS: lxml DOM parse -> APTED tree-edit
distance. Both sides normalized identically (`_normalize_table_html`). APTED is
a deterministic tree-edit-distance algorithm. The `_TedsConfig.rename` cost
uses `rapidfuzz.Levenshtein.distance` (deterministic).

### 3.3 `mhs(md_a, md_b)`

Heading tree built by `_build_heading_tree` (mistune CommonMark AST parse ->
ordered heading list -> stack-based tree). APTED tree-edit distance with
`_MhsConfig.rename` cost (NED on heading text). Both the AST parse and APTED
are deterministic. Heading order is document order (parser iteration order).

### 3.4 `normalized_text(text)`

`clean_string(textblock2unicode(text))`: inline LaTeX folded via pylatexenc
(deterministic mathematical transformation), then alnum+CJK filter. Pure
string transform.

### 3.5 `content_recall(candidate, reference)`

Multiset word recall: `Counter` of tokenized words, matched by
`min(count, hyp[token])`. `Counter` iteration order does not affect the
arithmetic (summation is commutative). Deterministic.

**Verdict:** All three core metrics (`text_nid`, `teds`, `mhs`) and the
supporting functions (`normalized_text`, `content_recall`) are **deterministic
pure functions**. No randomness, no network, no mutable shared state.

---

## 4. `match.py` -- Block Matching Determinism

### 4.1 `match_blocks(gt_blocks, pred_blocks)`

1. Normalize both sides with `normalized_text` (deterministic).
2. Build NED cost matrix `_ned_matrix`: O(m*n) Levenshtein calls, each
   deterministic.
3. Hungarian assignment via `scipy.optimize.linear_sum_assignment`: this is
   the Jonker-Volgenant algorithm, which is deterministic for a given cost
   matrix.
4. Accept pairs at `<= BLOCK_ACCEPT_NED`.
5. Fuzzy rescue: scans unmatched GT blocks in `range(len(gt_text))` order
   and unmatched pred blocks in `range(len(pr_text))` order -- both
   deterministic iteration orders. "First qualifying pred wins" with the
   `break` on line 209.

### 4.2 `reading_order_ned`

NED over integer sequences derived from match indices. Sorted deterministically
on line 290-291: `gt_seq = sorted(g for g, _ in paired)`,
`pred_seq = [g for g, _ in sorted(paired, key=lambda x: x[1])]`.

**Verdict:** Block matching is **fully deterministic**. No random tie-breaking,
no set iteration over unordered collections. Index-order scan and sorted output.

---

## 5. `facts.py` -- Comprehension Check Determinism

### 5.1 `check_facts(md, facts, pid)`

Iterates `facts` in list order (input order). Each `_evaluate` call is
independent and deterministic:

- **present/absent:** `_present_within` -> `_best_match` (exact `str.find`
  first, then `rapidfuzz.fuzz.partial_ratio_alignment` + exact substring DP).
  All deterministic.
- **order:** sequential `_position_within` with strictly-increasing position
  check.
- **table:** `_check_table` iterates tables from `_all_tables(md)` (pipe
  tables then HTML tables, in document order). Cell search is a nested loop
  over grids/rows/columns. Neighbor checks use fixed direction order
  (`_TABLE_DIRECTIONS`).
- **math:** `_math_surface` -> `textblock2unicode` + whitespace collapse.
  Deterministic.
- **code/xref/image_ref:** raw-surface substring search. Deterministic.

### 5.2 Neighbor sort

Table fact neighbors from the JSONL dict are iterated via `.items()` (Python
3.7+ insertion order, but JSON object key order is not guaranteed across
parsers). **Mitigated on line 595:** `neighbors.sort(key=lambda dv:
_TABLE_DIRECTIONS.index(dv[0]))` -- explicit sort by the fixed canonical
direction order. This makes the evaluation order deterministic regardless of
JSON key order.

**Verdict:** `check_facts` is **deterministic**. All surfaces are pure string
transforms, all iteration is ordered, neighbor dict iteration is
post-hoc-sorted.

---

## 6. Non-Determinism Source Grep

Searched `packages/whisker/src/whisker/*.py` for:
`random`, `shuffle`, `sample`, `uuid`, `time.time`

**Result: Zero matches in the scoring path.** The only hits were `sample` in
`report.py` and `__main__.py` referring to `reg["sample"]` (a region text
snippet field name), not `random.sample`. No randomness source exists anywhere
in the deterministic scoring code.

---

## 7. `sorted()` Usage Audit

Every unordered collection that feeds into output is sorted:

| Location | Collection | Sort Key |
|---|---|---|
| `score.py:129` | `hard_flags` | `sorted()` (lexicographic) |
| `score.py:130` | `soft_flags` | `sorted()` (lexicographic) |
| `score.py:283` | `missing_regions` / `extra_regions` | `sorted(key=token_start)` |
| `report.py:47` | flags for summary | `sorted(hard) + sorted(soft)` |
| `report.py:92,103` | results list | `sorted(key=pid)` |
| `bench.py:211` | bench rows | `sorted(key=pid)` |
| `match.py:290-291` | reading-order sequences | `sorted()` |
| `golden.py:150-151` | status counts, findings | `sorted()`, `sorted(key=pid)` |
| `guard.py:204-210` | floors, status counts, missing, findings | All `sorted()` |
| `facts.py:595` | neighbor directions | `sort(key=direction_index)` |
| `calibrate.py:131` | threshold candidates | `sorted(set(values))` |
| `__main__.py:401-402` | CLI hard/soft flags | `sorted()` |

**One set iteration without pre-sort** in the scoring path:

- `gates.py:63-69`: `keys = set()` for front-matter key collection, but the
  set is only tested for membership (`k not in keys`), never iterated into
  output. The `missing` list on line 70 iterates `_REQUIRED_FRONT_MATTER_KEYS`
  (a tuple, fixed order). **No determinism risk.**

**Verdict:** All collections reaching output are properly sorted. The D7
invariant is honored throughout.

---

## 8. Score Pinning Tests (`test_score_pinning.py`)

### 8.1 What it tests

For each of 19 committed tomd golden markdowns, `_score_one` runs:
- `run_gates(md_text)` -- all 6 structural gates
- `compute_metrics(md_text)` -- tomd QA (heading count, code blocks, tables,
  uncertain markers, mojibake, lossy tables, paragraph count, heading skips,
  wording sections)

The results are compared field-by-field against a committed baseline JSON at
`tests/fixtures/score-baseline.json`.

### 8.2 How it enforces replay determinism

Any change to gate logic or QA scoring that shifts a single field on any of the
19 goldens breaks the test. Updating the baseline requires
`WHISKER_PIN_UPDATE=1`, which is **blocked in CI** (line 134-138: `if
os.environ.get("CI"): pytest.fail(...)`). This prevents silent regressions.

### 8.3 Meta-test for unacknowledged gate failures

`test_no_unacknowledged_gate_failures` (line 186) verifies that every false
gate in the baseline is explicitly listed in `_EXPECTED_GATE_FAILURES`. A new
golden with an un-listed gate failure breaks CI, forcing an explicit
acknowledge-or-fix decision.

### 8.4 Coverage gap

The pinning tests cover gates and QA metrics but do NOT pin the full
`score_markdown` output (no `_decide` verdict pinning, no `ref_nid`/`ref_teds`/
`ref_mhs` pinning). The verdict logic is tested separately via unit tests
elsewhere. For pure replay determinism, the gate+QA pinning is the most
sensitive layer (any shift in structural scoring breaks it).

**Verdict:** Score pinning provides **strong replay-determinism evidence** for
the structural scoring path. The CI-blocked update mechanism prevents silent
baseline drift.

---

## 9. Dev-Replay Tests

### 9.1 `test_dev_replay_acceptance.py`

Tests the deterministic portions of the advisory LLM pipeline:
- **Label consistency:** papers with known defects expect non-pass LLM
  verdicts; clean papers expect pass; merge-verdict papers have no defects.
- **P0533R9 constexpr count:** mechanically verified 151-count against the PDF
  source (when available).
- **Risk router signals:** PDF omission defects specify pages; qualifier
  omissions specify the tracked token.

These tests verify that the **dev-replay label corpus** is internally
consistent and that the deterministic risk router produces expected signals.
They are hermetic (no LLM needed for the label-consistency checks).

### 9.2 `test_dev_replay_schema.py`

Schema validation for both the dev-replay (9 PRs) and holdout (3+ papers)
corpora:
- Dev-replay labels have all required fields, valid verdicts, valid severities.
- Holdout anchors: >= 48 anchors across >= 4 strata, no overlap with dev-replay
  papers.
- **Locked candidate dispositions:** SHA-256 of source + candidate files
  verified against manifest, then `classify_candidate_evidence` re-run on the
  locked candidate to verify dispositions match. This is a **replay
  determinism test**: given the same source and candidate bytes, the evidence
  classifier must produce the same dispositions.
- **Case/punctuation canaries:** `FLT_EVAL_METHOD` -> `flt_eval_method`
  and `==` -> `!=` mutations are detected as AMBIGUOUS (not PRESENT).

**Verdict:** The dev-replay tests verify corpus-level determinism (label
consistency, evidence classification replay, mutation sensitivity). They
complement the score-pinning tests by covering the advisory pipeline's
deterministic substrate.

---

## 10. Summary of Findings

### Determinism Status: STRONG

| Dimension | Status | Evidence |
|---|---|---|
| Metric purity | PASS | `text_nid`, `teds`, `mhs`, `content_recall` are pure functions of string inputs |
| Scoring purity | PASS | `score_markdown` and `_decide` have no side effects, no external state |
| No randomness | PASS | Zero hits for `random`/`shuffle`/`sample`/`uuid`/`time.time` in scoring code |
| Output ordering | PASS | All flag lists, result lists, bench rows sorted; dict iterations post-hoc-sorted |
| Block matching | PASS | Index-order iteration, Hungarian assignment deterministic, sorted output |
| Fact checking | PASS | Document-order iteration, neighbor sort by canonical direction |
| Gate evaluation | PASS | Fixed gate list, regex-based, no external state |
| Pinning tests | PASS | 19-golden baseline with CI-blocked update, field-by-field comparison |
| Replay evidence | PASS | Dev-replay SHA-locked dispositions, canary mutations |

### Observations (not defects)

1. **Verdict not pinned directly.** The score-pinning tests pin gates+QA but
   not the `_decide` verdict itself. The verdict is a deterministic function of
   the pinned values plus coverage/drift (which come from tomd's
   `check_paper_content`, outside whisker). The architectural purity of
   `_decide` compensates: given the same inputs it cannot produce different
   outputs.

2. **Quality-stable, not bit-exact.** The contract explicitly acknowledges that
   LLM outputs on hosted endpoints are not bit-reproducible. The deterministic
   gate is designed to be LLM-free precisely for this reason. The advisory LLM
   lane (`tapetum_llm`) tolerates verdict flips because it never gates.

3. **`scipy.optimize.linear_sum_assignment` determinism.** The Hungarian
   algorithm is deterministic for a given cost matrix. If `rapidfuzz` or
   `scipy` changed their implementations across versions, the block-matching
   output could shift. This is mitigated by pinning dependency versions in
   `pyproject.toml` and by the guard baseline (which would catch any shift).

4. **`pylatexenc` LaTeX folding.** The `textblock2unicode` -> `safe_latex_to_text`
   path depends on pylatexenc's deterministic LaTeX-to-unicode conversion.
   Malformed LaTeX falls back to the raw string (deterministic fallback).

### Risk Assessment: LOW

The whisker scoring path exhibits strong quality-stability determinism. Every
metric is a pure function, every output collection is sorted, no randomness
source exists, and the pinning test infrastructure enforces regression
detection with CI-blocked baseline updates. The architectural separation of
the deterministic gate from the advisory LLM lane is sound and well-documented.

No violations of G3 (determinism by replay) or D2 (determinism &
reproducibility) were found in the scoring path code.
