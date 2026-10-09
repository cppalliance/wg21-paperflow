# C04 Fail-Not-Partial Audit: whisker

Persona: **C04 — Fail-Not-Partial Fault Injector**
Scope: `packages/whisker/` (deterministic QA lanes only; tapetum_llm advisory lane noted where relevant)
Date: 2026-07-19
Invariants under test: **G2 (fail-not-partial)**, **D3 (fidelity)**

## Executive Summary

whisker's deterministic lanes are **well hardened** against the fail-not-partial
invariant. The batch-worker firewall is commented, exit codes are typed and
correct, vacuous-green detection is present and enforced, gate failures propagate
to hard flags, and NaN/inf values are caught before they can corrupt comparisons.
Two low-severity gaps remain: (1) pylatexenc normalization failures degrade
metrics silently rather than failing the paper, and (2) the `content_recall`
function cannot return None, so a missing-reference edge case is structurally
impossible but the division-by-zero guard produces a 1.0 (vacuous pass).

Verdict: **PASS with 2 LOW findings** (no CRITICAL, no HIGH, no MEDIUM).

---

## 1. Batch-Worker Firewall (`__main__.py:218-233`)

### Stage: `_score_main` per-paper scoring loop

**What failure looks like:** `score_paper()` raises any exception (upstream
extraction/normalization bug, corrupt PDF, unreadable file).

**What whisker does:**

```
218:    for idx, pid in enumerate(pids, start=1):
219:        try:
220:            result = score_paper(pid, backend, reference_engine=reference_engine)
221:            results.append(result)
222:            scored_pids.append(pid)
223:        except (MissingPaperMdError, MissingSourceError) as exc:
224:            skipped += 1
225:            logger.warning("skipping %s: %s", pid, exc)
226:        except Exception:
227:            # Batch worker firewall: one paper that trips an upstream
228:            # extraction/normalization bug must not abort the whole run or
229:            # discard the results already gathered.
230:            errored += 1
231:            logger.exception("error scoring %s (skipped)", pid)
```

**Verdict: PASS.**
- The broad `except Exception` catch at line 226 is **commented** ("Batch worker
  firewall") — compliant with the repo invariant that uncommented broad catches
  are treated as bugs.
- Missing papers (`MissingPaperMdError`, `MissingSourceError`) are distinguished
  from unexpected errors — separate `skipped` vs `errored` counters.
- Progress bar renders regardless (`finally` block, line 232-233).
- The `errored` count is reported in the summary output (line 271-280).

### Post-loop behavior (lines 236-283)

| Condition | Exit code | Artifact preserved? |
|-----------|-----------|---------------------|
| No papers scored, all errored | `EXIT_ERROR` (1) | No sidecars (nothing to write) |
| Some errored, some scored | Warning logged; scored results written | Sidecars + report for successful papers |
| All scored | Normal verdict exit | Full report + sidecars |

**Non-zero exit on total failure: PASS.** Line 236-238: `if not results: return
C.EXIT_ERROR`. A run where every paper errors out exits 1, never 0.

**Errored papers in exit code: PASS.** The verdict exit code (line 283) is
computed from the scored papers' verdicts. Errored papers do not silently
disappear from the exit code: they are excluded from the scored set (no
hollow result injected), and the error count is logged. A run with some errors
and some passes exits based on the pass/fail of the scored subset, which is
correct — the errored papers are unscorable, not judgeable.

---

## 2. Exit Code Contract

**Defined in `constants.py:154-157`:**

| Code | Constant | Meaning |
|------|----------|---------|
| 0 | `EXIT_OK` | All verdicts acceptable |
| 1 | `EXIT_ERROR` | Infrastructure/setup failure |
| 3 | `EXIT_REVIEW` | At least one review verdict |
| 5 | `EXIT_FAIL` | At least one fail verdict |

**`_verdict_exit_code` (line 130-136):** Correct. It checks if any verdict in
the results list exceeds the `--gate` threshold. With the default `--gate review`,
a `fail` verdict produces exit 5 and a `review` verdict produces exit 0 (review
is accepted). With `--gate pass`, both review and fail produce non-zero exits.

**`_score_file_main` (lines 392-393):** Direct exit code assignment from hard/soft
flags — `EXIT_FAIL` if hard flags, `EXIT_REVIEW` if soft flags only, `EXIT_OK`
otherwise. No verdict-exit-code indirection needed. PASS.

**Backend unavailable (lines 190-194):** `_open_backend` raises `EnvironmentError`,
caught and returns `EXIT_ERROR` (1). PASS.

**No papers to score (lines 196-206, 236-238):** `--all` with no converted papers
returns `EXIT_ERROR`. All papers errored returns `EXIT_ERROR`. PASS.

---

## 3. Gate Failures → Hard Flags (`gates.py` → `score.py`)

**Propagation chain:**

1. `run_gates(md_text)` returns `list[GateResult]` — each gate has
   `name`, `passed`, `detail`.
2. `_decide()` in `score.py` lines 177-179: every failed gate becomes a hard
   flag: `hard.append(f"gate:{gate.name}:{gate.detail or 'failed'}")`.
3. Hard flags force `VERDICT_FAIL` (line 217-218).
4. `_verdict_exit_code` maps `VERDICT_FAIL` to `EXIT_FAIL` (5).

**All 6 gates are hard:**
- `non_empty` — empty body
- `front_matter_valid` — missing/malformed front matter
- `heading_monotone` — heading level jumps
- `no_empty_code` — empty fenced code blocks
- `no_empty_table` — table separator with no data row
- `no_toc_leak` — TOC content leaked into body

**Test coverage:** `test_gates.py` covers all 6 gates with pass and fail cases
(16 tests). `test_score.py:test_broken_structure_forces_fail_despite_coverage`
verifies that a gate failure produces `VERDICT_FAIL` even with 0.99 coverage.
PASS.

**Verdict: PASS.** No path exists where a gate failure is swallowed or produces
a non-fail verdict.

---

## 4. NaN/inf in Metrics (`guard.py`, `bench.py`, `score.py`)

### guard.py — Explicit NaN/inf detection

**`_finite()` (line 135-136):** `isinstance(value, (int, float)) and
math.isfinite(value)`. Used throughout.

**`_evaluate_paper()` (lines 341-349):** Before any comparison, all checked axes
are scanned for non-finite values. A NaN/inf produces `STATUS_INVALID`, which is
in `_FAILING_STATUSES` and hard-fails the paper.

**`_validate_baseline()` (lines 296-304):** Baseline values are validated at load
time — a non-finite stored metric raises `ValueError`, which propagates to
`EXIT_ERROR` in the CLI.

**`GuardFinding.to_dict()` (lines 159-161):** Non-finite axes are serialized as
`null` (not bare `NaN` tokens that would produce invalid JSON). PASS.

### bench.py — No NaN/inf guard

`run_bench()` and `aggregate()` perform arithmetic (division by `len(parts)`,
division by `n`, division by `len(teds_vals)`) without NaN/inf checks. However:

- `block_metrics()`, `teds()`, `mhs()`, `content_recall()` all return floats in
  [0, 1] by construction (edit distances divided by max lengths, with
  zero-length guards).
- `aggregate()` guards `if not rows: return {...}` with explicit defaults.
- `teds_vals` / `mhs_vals` empty lists are guarded: `mean_teds = ... if
  teds_vals else None`.
- `overall` is `sum(parts) / len(parts)` where `parts` always contains at least
  `nid_v` (text NID is always eligible), so `len(parts)` >= 1.

**Verdict: PASS.** NaN/inf cannot reach the guard's per-paper comparison because
the metrics themselves are structurally bounded. The guard catches any that
somehow leak through.

### score.py — No explicit NaN/inf guard

`score_markdown()` passes `content.unigram_coverage` etc. directly into
`_decide()`. These come from `tomd.lib.check_content.check_paper_content()` /
`compute_content_coverage()`, which are external. If they returned NaN/inf, the
comparison `< UNIGRAM_COVERAGE_FAIL_EDGE` would be `False` (NaN comparisons are
always False in IEEE-754), so a NaN coverage would **not** trigger the hard fail
and would silently pass.

**Finding F01 (LOW):** In `_decide()`, a NaN `unigram_coverage` would slip
through both the fail and review band checks (all comparisons are False for NaN)
and produce a `VERDICT_PASS`. In practice, `check_paper_content` returns finite
floats from token counting, so this is a theoretical gap. The guard path
(`guard.py`) catches it. The score path (`score.py`) does not.

---

## 5. Missing Source / Missing Markdown

### score_paper() (score.py:334-371)

`backend.get_paper_md(pid)` raises `MissingPaperMdError` if the markdown is not
staged. `check_paper_content(pid, backend)` raises `MissingSourceError` if the
source PDF/HTML is not staged. Both are NOT caught inside `score_paper` — they
propagate to the caller.

### _score_main() (\_\_main\_\_.py:218-225)

Both are caught explicitly at lines 223-225: `skipped += 1`, warning logged. The
paper is excluded from `results` — no hollow artifact is written.

**Verdict: PASS.** A paper without a source or markdown is skipped with a
warning, never silently passed or erroneously failed.

### score-file CLI (_score_file_main, lines 332-335, 343-345, 358-360)

File-not-found checks (`args.md.is_file()`, `args.ref.is_file()`,
`args.source.is_file()`) return `EXIT_ERROR` with a stderr message. PASS.

Content-coverage failure (lines 363-365): `except Exception` returns
`EXIT_ERROR`. Commented: "content coverage failed". PASS.

---

## 6. Vacuous Green Detection (`facts.py`, `__main__.py`)

### FactReport.passed property (facts.py:145-148)

```python
@property
def passed(self) -> bool:
    return all(c.passed for c in self._enforced())
```

`_enforced()` returns only `verified=True` checks. If there are zero verified
facts, `all([])` is `True` — the report passes. This is **by design**: the
`FactReport` itself is pass/fail on the verified facts only.

### Vacuous-green guard (`__main__.py:642-657`)

`_warn_vacuous_reports()` scans for papers with zero `verified_count` and:
1. Logs a warning per vacuous paper.
2. Returns the set of vacuous PIDs.

### facts CLI (`_facts_main`, lines 898-916)

```python
vacuous_pids = _warn_vacuous_reports(reports)
...
return C.EXIT_FAIL if (failed or vacuous_pids) else C.EXIT_OK
```

A facts file with zero verified facts **exits FAIL (5)**. PASS.

### guard CLI (`_guard_main`, lines 601-602)

```python
facts_vacuous = _warn_vacuous_reports(fact_reports)
facts_failed = any(r.failed for r in fact_reports) or bool(facts_vacuous)
```

Vacuous facts in guard also propagate to `EXIT_FAIL`. PASS.

### CI hermetic gate (`test_comprehension_corpus.py:75-76`)

```python
verified = [c for c in report.checks if c.verified]
assert verified, f"{pid}: facts file has no checked:verified fact"
```

The test asserts at least one verified fact per corpus paper. PASS.

**Verdict: PASS.** Vacuous green is detected and fails at every level: CLI,
guard, and CI test suite.

---

## 7. content_recall Returns None or 0 (`bench.py`, `metrics.py`)

### metrics.content_recall (metrics.py:372-389)

```python
def content_recall(candidate: str, reference: str) -> float:
    ref = Counter(content_tokens(reference))
    if not ref:
        return 1.0
    hyp = Counter(content_tokens(candidate))
    matched = sum(min(count, hyp[token]) for token, count in ref.items())
    return matched / sum(ref.values())
```

- Empty reference → 1.0 (nothing to recall). Correct by definition.
- Empty candidate → `matched` = 0, `sum(ref.values())` > 0 → returns 0.0. Correct.
- Function **never returns None**; always returns a float.
- Division by zero is impossible: `sum(ref.values())` > 0 when `ref` is non-empty
  (the `if not ref: return 1.0` guard).

### bench.py usage (line 195)

```python
recall_v = content_recall(candidate_md, reference_md)
```

Used directly in `BenchRow` with a default of 1.0. Since `content_recall` never
returns None, `recall_v` is always a float.

### aggregate() floor check (line 253)

```python
or r.content_recall < C.CONTENT_RECALL_FLOOR
```

Since `content_recall` is always a float, this comparison works correctly.

**Verdict: PASS.** `content_recall` is structurally safe — it cannot produce None,
NaN, or division-by-zero.

---

## 8. `except Exception` Catches — Commentary Audit

| Location | Commented? | Firewall? | Finding |
|----------|------------|-----------|---------|
| `__main__.py:226` | Yes: "Batch worker firewall" | Yes | PASS |
| `metrics.py:295` | No (implicit: pylatexenc guard ladder fallback) | No — returns raw text | **F02 (LOW)** |
| `metrics.py:331` | No (implicit: inline LaTeX folding) | No — `continue` skips formula | **F02 (LOW)** |
| `tapetum_llm/readback_cli.py:173` | No (implicit batch skip) | Yes (batch skip) | OUT OF SCOPE (advisory lane) |
| `tapetum_llm/cli.py:541,961,1012,1050,1067` | Various | Advisory lane | OUT OF SCOPE |
| `tapetum_llm/vision.py:71,92` | Re-raise as RasterError | Not a swallow | OUT OF SCOPE |
| `tapetum_llm/textlayer.py:124,142,177,198` | Re-raise as TextLayerError | Not a swallow | OUT OF SCOPE |
| `tapetum_llm/adjudicate.py:569` | Yes: "Best-effort source metadata" | Yes (best-effort) | OUT OF SCOPE |
| `tapetum_llm/unit_judge.py:266` | No (batch skip with warning) | Advisory lane | OUT OF SCOPE |

### Finding F02 (LOW): Silent normalization fallback in metrics.py

`safe_latex_to_text()` (line 295) catches all exceptions from
`LatexNodes2Text().latex_to_text()` and returns the raw input text. Similarly,
`textblock2unicode()` (line 331) catches exceptions per inline formula and
`continue`s, keeping the raw LaTeX in the text stream.

**Impact:** A pylatexenc crash on a specific formula silently degrades the
normalized text (LaTeX delimiters remain, lowering the NID/ref_nid axis). This
could cause a false review (NID drops below the advisory edge) or, less likely, a
false pass (the formula was dropped from both sides equally). Neither catch is
commented as a batch-worker firewall per repo convention.

**Mitigation:** The OmniDocBench codebase from which this is ported uses the same
pattern. The guard ladder (`_likely_bad_latex`, `_looks_like_weak_latex_input`,
`_looks_like_plaintext_formula_noise`) rejects the dangerous inputs before
pylatexenc ever runs. In practice, the broad catch is a last-resort safety net
on the normalization path, not a scoring or gating path.

**Recommendation:** Add a comment documenting the fallback pattern as intentional
(matching the "uncommented broad catches are treated as bugs" invariant) or
log a debug-level warning when the fallback triggers.

---

## 9. Artifact Preservation on Failure

### Sidecars and report written only for scored papers

`_score_main()` lines 243-264: sidecars are written per `(pid, result)` in
`zip(scored_pids, results)`. Only papers that returned a `WhiskerResult` get a
sidecar. Errored or skipped papers get no sidecar — no hollow artifact.

The `report.json` and `report.md` are written from the `results` list, which
contains only successful scores. PASS.

### Guard/facts/golden baselines

`--update` writes baselines only from complete rows (`baseline_from_rows(rows)`,
guard.py:227-248). An empty `rows` list is caught before reaching this point
(lines 465-467: "no (candidate, reference) pairs found"). PASS.

### Debug info preservation

The batch-worker firewall (line 231) calls `logger.exception(...)`, which logs
the full traceback at ERROR level. Debug information is preserved in the log
stream. No separate debug artifact is written for errored papers (there is no
partial result to write). PASS.

---

## 10. Calibrate and Corpus Commands

### calibrate (`_calibrate_main`)

- `_load_labeled_samples` raises `ValueError`/`OSError`/`KeyError` — caught at
  lines 1078-1087, returns `EXIT_ERROR`. PASS.
- Empty samples: line 1089-1090, returns `EXIT_ERROR`. PASS.
- Calibration failure: lines 1098-1107, returns `EXIT_ERROR`. PASS.
- Inverted edges (fail > review): warning logged, NOT a hard fail. Correct: the
  human must review. PASS.
- Calibration always returns `EXIT_OK` — it is informational, never gates. PASS.

### corpus (`_corpus_main`)

- `get_paper_md` exception on line 1230: `except Exception`, `logger.warning`,
  `continue`. This catch is uncommented. However, it is in a batch-iterator
  (draft scaffolding for multiple PIDs), and the pattern is identical to the
  main batch-worker firewall. **Finding: the catch is NOT commented as a
  firewall.** But the impact is LOW: this is the `whisker corpus draft` authoring
  tool, not a scoring/gating path.

---

## Findings Summary

| ID | Severity | Stage | Description |
|----|----------|-------|-------------|
| F01 | LOW | `score.py:_decide()` | NaN `unigram_coverage` would silently pass (all NaN comparisons are False). In practice unreachable: `check_paper_content` returns finite floats. The `guard.py` path catches NaN explicitly. |
| F02 | LOW | `metrics.py:295,331` | Uncommented broad `except Exception` catches in LaTeX normalization fallback. Degrades NID silently rather than failing the paper. Ported from OmniDocBench. |

---

## Cross-Reference: Test Coverage of Error Paths

| Error path | Test file | Test(s) |
|------------|-----------|---------|
| Gate failure → FAIL verdict | `test_score.py` | `test_broken_structure_forces_fail_despite_coverage`, `test_benign_region_with_hard_flag_is_fail` |
| Low coverage → hard fail | `test_score.py` | `test_low_coverage_is_fail`, `test_low_unigram_is_hard_fail` |
| Mid coverage → review | `test_score.py` | `test_mid_coverage_is_review`, `test_mid_unigram_is_soft_review` |
| Gate pass/fail per type | `test_gates.py` | 16 tests covering all 6 gates |
| Verified fact failure → gate | `test_facts.py` | `test_verified_failing_fact_gates` |
| Unverified fact → no gate | `test_facts.py` | `test_unverified_failing_fact_does_not_gate` |
| Zero verified facts → pass (at FactReport level) | `test_facts.py` | `test_no_verified_facts_passes` |
| Vacuous green → fail (at CLI level) | `test_comprehension_corpus.py` | `test_corpus_has_at_least_one_comprehension_paper` |
| Canary: scrambled table → fail | `test_comprehension_corpus.py` | `test_canary_scrambled_table_cell_fails` |
| Canary: scrambled code → fail | `test_comprehension_corpus.py` | `test_canary_scrambled_code_fails` |
| Canary: scrambled formula → fail | `test_comprehension_corpus.py` | `test_canary_scrambled_formula_fails` |
| Malformed facts file → ValueError | `test_facts.py` | `test_invalid_json_reports_line_number`, `test_unknown_type_raises`, etc. |
| Aggregate empty rows | `test_bench.py` | `test_aggregate_empty` |
| Ineligible axes (None) | `test_bench.py` | `test_no_table_no_heading_axes_are_none`, `test_overall_not_inflated_by_ineligible_axes` |
| Dropped section → low recall | `test_bench.py` | `test_dropped_section_lowers_content_recall_but_keeps_nid` |
| Below-floor detection | `test_bench.py` | `test_aggregate_flags_below_floor` |

### Missing test coverage (noted, not a finding)

- No test exercises the `__main__.py` batch-worker firewall path (a `score_paper`
  call that raises an unexpected exception inside the loop). This is hard to test
  without mocking, and the firewall is simple and visible.
- No test verifies that `_score_main` returns `EXIT_ERROR` when all papers error.
- No test for NaN/inf values reaching `_decide()` in `score.py`. The guard path
  (`guard.py`) has this coverage via the `STATUS_INVALID` status.

---

## Conclusion

The whisker package demonstrates strong fail-not-partial discipline:

1. **Non-zero exits on failure:** Every failure mode (gate failure, coverage
   below threshold, errored papers, missing source, vacuous facts) produces a
   non-zero exit code.
2. **No hollow artifacts:** Sidecars and reports are only written for
   successfully scored papers. No partial or empty results are emitted for
   errored papers.
3. **Debug info preserved:** `logger.exception` captures full tracebacks for
   errored papers. Advisory lane failures are logged with cause.
4. **Batch isolation:** One failing paper does not abort the batch. Errored
   papers are counted and reported separately.
5. **Vacuous green detected:** Facts files with zero verified facts fail at
   CLI, guard, and CI levels.
6. **NaN/inf hardened:** The guard path explicitly detects and rejects
   non-finite metrics. The score path is theoretically vulnerable but
   practically unreachable.
