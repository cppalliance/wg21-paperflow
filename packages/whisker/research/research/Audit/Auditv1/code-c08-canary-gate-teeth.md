# C08 — Canary and Gate-Teeth Auditor

**Mandate:** Check that canaries exist, must-fail works, and gates have teeth.
**Gate dimensions:** G6 (canaries prove the gate has teeth), D5 (vacuous-green detection)
**Auditor:** Canary and Gate-Teeth Auditor
**Date:** 2026-07-19

---

## Summary

Exactly 3 canaries exist, one per exploit class, and each is correctly implemented. The canaries prove the gate has teeth by deliberately corrupting a committed snapshot and asserting the comprehension gate fails. Gates in `test_gates.py` exercise both pass and fail paths. Vacuous-green detection is present in both the CLI and the hermetic test suite. The codebase is clean on G6 and D5.

---

## Finding 1: Three canaries exist, one per exploit class

- **Severity:** PASS (correctly implemented)
- **Claim:** There are exactly 3 canary tests in `test_comprehension_corpus.py`, covering scrambled table, flipped math, and mangled code.
- **Evidence:**
  - `test_comprehension_corpus.py:83-101` (`test_canary_scrambled_table_cell_fails`): P4182R0, replaces `"(CUDA, SYCL) | No |"` with `"(CUDA, SYCL) | Yes |"`, asserts the `tableA-gpu-coro-no` fact fails.
  - `test_comprehension_corpus.py:104-122` (`test_canary_scrambled_code_fails`): P4234R0, replaces `'asm("Image$$ER_ZI$$Base")'` with `'asm("Image__ER_ZI__Base")'`, asserts the `code-asm-alias` fact fails.
  - `test_comprehension_corpus.py:125-143` (`test_canary_scrambled_formula_fails`): P4185R0, replaces `\(x^{2k} \geq 0\)` with `\(x^{2k} \leq 0\)`, asserts the `math-even-power-nonneg` fact fails.
  - Each canary: (a) loads a committed snapshot, (b) makes a minimal, semantically-meaningful corruption, (c) runs `check_facts`, (d) asserts `report.failed`, (e) asserts the specific fact ID in `report.failures()`.
- **Affected gate/dimension:** G6
- **Confidence:** 1.0
- **False-pass hypothesis:** None. The canary anchor assertions (`assert needle in md`) ensure the corruption target still exists in the snapshot. If the snapshot drifts, the canary skips or fails loudly.
- **False-fail hypothesis:** None.

## Finding 2: Canary for scrambled table cell (P4182R0) — detail

- **Severity:** PASS (correctly implemented)
- **Claim:** The P4182R0 canary specifically tests the table-cell neighbor check: flipping a "No" to "Yes" in a pipe table must fail the `table` fact that asserts the cell value and its neighbors.
- **Evidence:**
  - `test_comprehension_corpus.py:93-94`: `needle = "(CUDA, SYCL) | No |"` — targets a specific cell in Table A.
  - `test_comprehension_corpus.py:95`: `scrambled = md.replace(needle, "(CUDA, SYCL) | Yes |", 1)` — flips the cell value.
  - `test_comprehension_corpus.py:101`: `assert any(c.id == "tableA-gpu-coro-no" for c in report.failures())` — asserts the specific fact ID.
- **Affected gate/dimension:** G6
- **Confidence:** 1.0

## Finding 3: Canary for flipped math relation (P4185R0) — detail

- **Severity:** PASS (correctly implemented)
- **Claim:** The P4185R0 canary flips a relational operator in a formula: `\geq` to `\leq`, proving the math fact surface distinguishes operators.
- **Evidence:**
  - `test_comprehension_corpus.py:135-136`: `needle = r"\(x^{2k} \geq 0\)"` — targets a specific LaTeX formula.
  - `test_comprehension_corpus.py:137`: `scrambled = md.replace(needle, r"\(x^{2k} \leq 0\)", 1)` — flips the relation.
  - `test_comprehension_corpus.py:143`: `assert any(c.id == "math-even-power-nonneg" for c in report.failures())` — asserts the specific fact ID.
- **Affected gate/dimension:** G6
- **Confidence:** 1.0

## Finding 4: Canary for mangled code snippet (P4234R0) — detail

- **Severity:** PASS (correctly implemented)
- **Claim:** The P4234R0 canary mangles a code identifier (replacing `$$` with `__` in an asm alias), proving the code fact raw-surface check catches the corruption.
- **Evidence:**
  - `test_comprehension_corpus.py:114`: `needle = 'asm("Image$$ER_ZI$$Base")'` — targets a code snippet with `$` identifiers.
  - `test_comprehension_corpus.py:116`: `scrambled = md.replace(needle, 'asm("Image__ER_ZI__Base")', 1)` — mangles the identifier.
  - `test_comprehension_corpus.py:122`: `assert any(c.id == "code-asm-alias" for c in report.failures())` — asserts the specific fact ID.
- **Affected gate/dimension:** G6
- **Confidence:** 1.0

## Finding 5: Gates actually fail on bad input (test_gates.py)

- **Severity:** PASS (correctly implemented)
- **Claim:** `test_gates.py` tests that each structural gate fails on bad input and passes on good input.
- **Evidence:**
  - `test_gates.py:35-37`: `test_clean_document_passes_all_gates` — a well-formed document passes every gate.
  - `test_gates.py:40-41`: `test_missing_front_matter_fails` — no front matter triggers `front_matter_valid` failure.
  - `test_gates.py:45-48`: `test_unterminated_front_matter_fails` — unclosed front matter fails.
  - `test_gates.py:51-53`: `test_empty_body_fails` — empty body triggers `non_empty` failure.
  - `test_gates.py:57-60`: `test_heading_skip_fails` — H2->H4 jump triggers `heading_monotone` failure.
  - `test_gates.py:63-65`: `test_empty_code_block_fails` — empty code fence triggers `no_empty_code` failure.
  - `test_gates.py:77-80`: `test_headless_table_fails` — single-column table with no content triggers `no_empty_table` failure.
  - `test_gates.py:99-161`: Seven TOC leak tests: page-numbered duplicate fails, reverse order fails, contents label fails, contents heading fails, legit duplicate passes, numbered step headings pass, code-fenced TOC passes.
- **Affected gate/dimension:** G6
- **Confidence:** 1.0

## Finding 6: Score tests verify bad papers get fail verdicts (test_score.py)

- **Severity:** PASS (correctly implemented)
- **Claim:** `test_score.py` includes tests where bad papers receive a `fail` verdict.
- **Evidence:**
  - `test_score.py:83-86` (`test_low_coverage_is_fail`): coverage 0.50 -> FAIL with "coverage" in hard_flags.
  - `test_score.py:99-104` (`test_low_unigram_is_hard_fail`): unigram 0.70 -> FAIL with "unigram coverage" in hard_flags.
  - `test_score.py:175-179` (`test_broken_structure_forces_fail_despite_coverage`): broken structure (no front matter, heading skip) with perfect coverage 0.99 -> FAIL with "gate:" in hard_flags.
  - `test_score.py:241-251` (`test_coverage_still_hard_fails_with_reference_on`): coverage 0.50 with identical reference -> STILL FAIL (reference cannot rescue missing content).
  - `test_score.py:253-262` (`test_reference_does_not_mask_structural_gate`): broken structure with agreeing reference -> STILL FAIL (structural gates are hard under reference).
- **Affected gate/dimension:** G6
- **Confidence:** 1.0

## Finding 7: Vacuous-green detection in __main__.py

- **Severity:** PASS (correctly implemented)
- **Claim:** The CLI detects and warns about facts files with zero verified facts (vacuous green), and treats them as failures.
- **Evidence:**
  - `__main__.py:642-657` (`_warn_vacuous_reports`): Returns PIDs whose facts file has zero verified facts. Logs warning: "facts file has 0 verified facts (%d draft); vacuous green".
  - `__main__.py:601-602`: `facts_vacuous = _warn_vacuous_reports(fact_reports)` followed by `facts_failed = any(r.failed for r in fact_reports) or bool(facts_vacuous)` — vacuous is treated as failure.
  - `__main__.py:898`: `vacuous_pids = _warn_vacuous_reports(reports)` — same pattern in the `facts` verb.
  - `__main__.py:916`: `return C.EXIT_FAIL if (failed or vacuous_pids) else C.EXIT_OK` — vacuous forces non-zero exit.
- **Affected gate/dimension:** D5
- **Confidence:** 1.0

## Finding 8: Vacuous-green detection in test_comprehension_corpus.py

- **Severity:** PASS (correctly implemented)
- **Claim:** The hermetic CI test asserts that each corpus paper has at least one verified fact.
- **Evidence:**
  - `test_comprehension_corpus.py:58-63` (`test_corpus_has_at_least_one_comprehension_paper`): Guards against a vacuous suite: if every paper lost its snapshot, the parametrized test below would silently collect nothing and pass.
  - `test_comprehension_corpus.py:75-76`: `verified = [c for c in report.checks if c.verified]` followed by `assert verified, f"{pid}: facts file has no checked:verified fact"` — per-paper verified-count gate.
- **Affected gate/dimension:** D5
- **Confidence:** 1.0

---

## Verdict

**G6: CLEAN.** Three canaries exist (one per exploit class: table cell scramble, math relation flip, code identifier mangle). Each corrupts a committed snapshot in a semantically meaningful way and asserts the specific fact ID fails. Gate tests in `test_gates.py` exercise both pass and fail paths for every structural gate. Score tests verify bad papers receive fail verdicts.

**D5: CLEAN.** Vacuous-green detection is present in both the CLI (`_warn_vacuous_reports`, treats as failure) and the hermetic test suite (asserts at least one verified fact per paper, asserts at least one corpus paper exists).
