# C08 Canary and Gate Teeth

**Role:** Verify that inverted canaries prove gates have teeth.
**Auditor scope:** `tests/test_comprehension_corpus.py`, `facts.py`, `test_facts.py`
**Maps to:** G6 (anti-gaming), D5 (quality-stability)

## 1. Audited State

- whisker 0.5.0, HEAD 51cb704 + local mods
- Python 3.12.10, pytest 8.4.2
- 1406 tests passed, 8 skipped, 3 xfailed (E1)
- 5 corpus papers, 37 verified facts, 3 inverted canaries

## 2. Commands and Exits

```
E1:  uv run --package whisker pytest packages/whisker/tests  -> 1406 passed, 8 skipped, 3 xfailed  (exit 0)
E11: uv run --package whisker pytest packages/whisker/tests/test_comprehension_corpus.py -v  -> 8 passed (exit 0)
```

## 3. Current Evidence

### 3.1 Three Corpus Canaries (test_comprehension_corpus.py)

Each canary deterministically corrupts ONE element of a committed `expected.md` snapshot, then asserts `check_facts()` detects the corruption.

| Canary | Test function | Paper | Corruption | Target fact ID |
|--------|-------------|-------|-----------|---------------|
| **Scrambled table cell** | `test_canary_scrambled_table_cell_fails` (L83-101) | P4182R0 | `(CUDA, SYCL) \| No \|` -> `(CUDA, SYCL) \| Yes \|` | `tableA-gpu-coro-no` |
| **Mangled code snippet** | `test_canary_scrambled_code_fails` (L104-122) | P4234R0 | `asm("Image$$ER_ZI$$Base")` -> `asm("Image__ER_ZI__Base")` | `code-asm-alias` |
| **Flipped math relation** | `test_canary_scrambled_formula_fails` (L125-143) | P4185R0 | `\(x^{2k} \geq 0\)` -> `\(x^{2k} \leq 0\)` | `math-even-power-nonneg` |

**Mechanism:** Each test reads the committed snapshot, applies a single character-level mutation, then calls `check_facts(scrambled, facts, pid)`. The assertion requires:
1. `report.failed` is True (the gate tripped).
2. The SPECIFIC fact ID that should detect this corruption is present in `report.failures()`.

This double assertion is critical: it proves not just "something failed" but "the RIGHT thing failed for the RIGHT reason."

### 3.2 Vacuous-Green Resistance

Two layers prevent a vacuous green (a suite that passes because it tests nothing):

1. **`test_corpus_has_at_least_one_comprehension_paper`** (L58-63): asserts `_PAIRS` is non-empty, so the parametrized `test_verified_facts_hold_against_snapshot` cannot silently collect zero tests and pass.

2. **`test_verified_facts_hold_against_snapshot`** (L67-80): for each paper, asserts `verified` list is non-empty (L76: `assert verified`), so a facts file with zero `checked: verified` entries cannot pass.

3. **CLI-side mirror** (`__main__.py` L642-657, `_warn_vacuous_reports`): `whisker facts` and `whisker guard` also fail when a paper's facts file has zero verified facts, mirroring the CI guard.

### 3.3 Unit-Level Canaries in test_facts.py

Beyond the corpus canaries, `test_facts.py` carries 8 additional canary tests covering exploit classes:

| Test | Exploit class | Lines |
|------|--------------|-------|
| `test_canary_decoy_table_all_occurrences` | Decoy-table false-pass via duplicate heading | L478-498 |
| `test_canary_html_table_scramble_detected` | HTML table neighbor scramble | L555-560 |
| `test_canary_operator_flip` | Raw-surface `>=` vs `<=` | L564-570 |
| `test_canary_pipe_split_in_code` | Pipes inside code fences parsed as tables | L573-578 |
| `test_canary_math_scope_case_and_relation` | Math case/operator sensitivity | L670-678 |
| `test_canary_math_scope_display_delimiters` | Display vs inline math delimiter fold | L681-697 |
| `test_canary_math_scope_doubled_backslashes` | LLM escaping artifact | L700-721 |
| `test_canary_decoy_table_wrong_heading_fails` | Heading mismatch must not pass | L525-532 |

## 4. Findings

### F1: Canaries are effective and exploit-class-specific (INFO)

**Severity:** INFO | **Confidence:** HIGH

Each of the 3 corpus canaries targets a distinct exploit class (table, code, math). Each mutates exactly one element and asserts the specific fact ID that should detect it. The mutation is minimal (one cell value flip, one symbol swap, one relation flip), proving the gate discriminates at the lowest granularity the fact engine supports.

### F2: Anchorless table facts remain ANY-semantics (LOW)

**Severity:** LOW | **Confidence:** HIGH

`_check_table` (facts.py L374-423): when `table_heading` is absent, the loop tries ALL candidate `(r, c, grid)` positions and returns True on the FIRST match (L417-420: `if ok: return True, ""`). A decoy table sharing a cell value but in an unrelated table passes the fact via the genuine occurrence. The `test_canary_decoy_table_all_occurrences` canary specifically demonstrates this: with `table_heading` set the decoy is caught; without it, the decoy is exploitable.

**Mitigation:** The codebase documents this (CLAUDE.md "Known gaps" item 9) and recommends authoring facts WITH `table_heading`. All 5 corpus papers' table facts use headings.

### F3: No corpus canary for `absent` or `order` exploit classes (LOW)

**Severity:** LOW | **Confidence:** HIGH

The 3 corpus canaries cover table, code, and math. No corpus-level canary tests `absent` (forbidden text appearing) or `order` (sequence reversal). Unit-level tests cover these (`test_absent_pass_and_fail`, `test_order_reversed_fails`), but the corpus-level gate only proves teeth for the three tested exploit classes.

## 5. False-Pass Hypothesis

**Q:** Could the canary suite pass despite a broken gate?

1. **Anchor drift:** Each canary asserts the mutation target string is present before scrambling (`assert needle in md`). If the snapshot drifts and the needle vanishes, `pytest.skip` fires, which counts as "skipped" not "passed." This is visible in the test count (currently 0 skipped in this file).

2. **Fact file drift:** If a fact ID is removed from the facts file, the `assert any(c.id == "..." for c in report.failures())` line would fail, catching it.

3. **Empty corpus:** `test_corpus_has_at_least_one_comprehension_paper` explicitly guards against this.

4. **Vacuous verified list:** Each parametrized test asserts `assert verified`, so a paper with only draft facts cannot pass silently.

**Conclusion:** The false-pass surface is narrow. The main residual risk is that the 3 exploit classes tested (table/code/math) do not cover absent/order/image_ref at corpus level.

## 6. Gate/Dimension Mapping

| Gate | Dimension | Status |
|------|-----------|--------|
| G6 Anti-gaming | Canaries prove detection of targeted corruption | PASS |
| D5 Quality-stability | 3 corpus canaries + 8 unit canaries stable across runs | PASS |

## 7. Limitations

- This report audits canary tests only; it does not verify that the underlying fact engine is correct on all edge cases (see C12).
- Corpus canaries cover 3 of 8 fact types. `present`/`absent`/`order`/`xref`/`image_ref` lack corpus-level canaries (unit tests exist).
- Real-LLM runtime is BLOCKED (E9); the `whisker-readback` validation is not re-verified.

## 8. Conclusion

The gate has teeth. Three corpus canaries prove that targeted single-element corruption in table cells, code snippets, and math formulas is detected by the specific fact that should catch it. Vacuous-green resistance is enforced at both CI (test suite) and CLI (runtime) levels. The canary architecture is sound; the residual gap is breadth (3 of 8 fact types at corpus level).

**Gate verdict: PASS**
