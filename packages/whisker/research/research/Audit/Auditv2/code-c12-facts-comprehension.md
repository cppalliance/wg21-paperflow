# C12 Facts and Comprehension

**Role:** Audit Lane 3 comprehension engine.
**Auditor scope:** `facts.py`, `tables.py`, `test_facts.py`, `test_comprehension_corpus.py`
**Maps to:** D4 (per-axis null-eligibility), D5 (quality-stability)

## 1. Audited State

- whisker 0.5.0, HEAD 51cb704 + local mods
- `facts.py`: 692 lines, `tables.py`: 142 lines
- `test_facts.py`: 722 lines (69 test functions), `test_comprehension_corpus.py`: 144 lines (8 tests)
- 5 corpus papers, 37 verified facts across 6 types
- All tests passing (E1)

## 2. Commands and Exits

```
E1:  uv run --package whisker pytest packages/whisker/tests  -> 1406 passed (exit 0)
E11: uv run --package whisker pytest packages/whisker/tests/test_comprehension_corpus.py -v  -> 8 passed (exit 0)
```

## 3. Current Evidence

### 3.1 All 8 Fact Types and Their Evaluation

Each fact type has a dedicated branch in `_evaluate` (facts.py L436-488):

| Type | Surface | Matching | Test coverage |
|------|---------|----------|---------------|
| `present` | normalized or raw | `_present_within(needle, haystack, max_diffs)` | `test_present_exact_pass`, `test_present_missing_fails`, `test_present_fuzzy_*` |
| `absent` | normalized or raw | negation of `_present_within` | `test_absent_pass_and_fail` |
| `order` | normalized or raw | strictly increasing `_position_within` positions | `test_order_monotonic_pass`, `test_order_reversed_fails`, `test_order_missing_item_fails` |
| `table` | cell-normalized (lowercase + ws-collapse) | `_check_table`: locate cell in grid, verify neighbor values | 10+ tests (neighbors, heading, decoy, HTML) |
| `math` | `_math_surface` (LaTeX-folded, keeps `^_=`, case-sensitive) | `_present_within` on folded surface | `test_math_structural_pass`, `test_math_missing_exponent_fails`, `test_canary_math_scope_*` |
| `code` | raw (whitespace-collapse only) | `_present_within` on raw surface | `test_code_fact_pass`, `test_code_fact_missing` |
| `xref` | raw | `_present_within` on raw surface | `test_xref_fact_pass`, `test_xref_fact_wrong_revision` |
| `image_ref` | raw | regex `_IMAGE_REF_RE` for presence, optional text substring | `test_image_ref_fact_*` (3 tests) |

### 3.2 Fuzzy Matching Implementation

The fuzzy matching pipeline (facts.py L276-331):

1. **Exact substring first** (L309: `haystack.find(needle)`), the common case.
2. **Approximate region via rapidfuzz** (L314: `fuzz.partial_ratio_alignment`).
3. **Exact substring DP** (L276-296: `_substring_edit_distance`): free-start/free-end Levenshtein on the widened region, since rapidfuzz's Indel window can trim boundary chars.
4. **Budget check** (L319): `<= max_diffs` required.

The two-stage approach (rapidfuzz locates the approximate window, then exact DP measures true edit count) is documented as fixing a known rapidfuzz boundary-trimming issue.

### 3.3 Surface Authority

Three distinct surfaces exist:

| Surface | Function | Applied to |
|---------|----------|-----------|
| **normalized** | `normalized_text` = `clean_string(textblock2unicode(text))` | `present`/`absent`/`order` (default) |
| **raw** | `_raw_surface` (whitespace-collapse only) | `present`/`absent`/`order` with `surface: "raw"`, `code`, `xref`, `image_ref` |
| **math** | `_math_surface` (LaTeX-fold, keep `^_=`, case-sensitive) | `math` |

`code` and `xref` are ALWAYS raw (facts.py L552-555: `surface=SURFACE_RAW` is hardcoded in `_fact_from_record`). This is tested: `test_code_and_xref_always_raw_surface` (test_facts.py L410-416).

### 3.4 Table Grid Parsing (tables.py)

Two parsers return the same `list[list[str]]` grid shape:

1. **`parse_pipe_tables`** (tables.py L50-83): Header + separator + body rows. Fence-aware (pipes inside code blocks are ignored). Deterministic.

2. **`parse_html_tables`** (tables.py L130-141): stdlib `html.parser`, no extra dependency. Handles tomd-emitted `<table>` blocks (CODE_COMPARISON, SPEC_TABLE, NB_BALLOT).

Both are exercised via `_all_tables` in facts.py (L342-346), which concatenates both grids for cell lookup.

### 3.5 Canary Sensitivity

Covered in detail in C08. Summary: 3 corpus canaries (table, code, math) + 8 unit canaries covering decoy tables, HTML tables, operator flips, code-fence pipes, math case/operators, display delimiters, and doubled backslashes.

### 3.6 Provenance Gate

The `checked` field controls enforcement (facts.py L84-85):
- Only `checked == "verified"` promotes a fact to enforced status.
- Unverified (draft) facts are evaluated and reported but flagged `verified=False` and do not gate (`FactReport.passed` only checks enforced facts, L146-148).
- Tested: `test_unverified_failing_fact_does_not_gate`, `test_verified_failing_fact_gates`, `test_no_verified_facts_passes`.

### 3.7 Coverage Per Type

Based on test_facts.py test count per fact type:

| Type | Unit tests | Corpus canary | Negative tests |
|------|-----------|---------------|----------------|
| present | 4 | - | 2 (missing, beyond budget) |
| absent | 1 | - | 1 (text present) |
| order | 2 | - | 2 (reversed, missing item) |
| table | 10+ | 1 (P4182R0) | 4+ (wrong neighbor, missing cell, OOB, decoy) |
| math | 5 | 1 (P4185R0) | 3 (wrong exponent, case, operator) |
| code | 1 | 1 (P4234R0) | 1 (missing) |
| xref | 1 | - | 1 (wrong revision) |
| image_ref | 2 | - | 1 (no image) |

## 4. Findings

### F1: All 8 fact types implemented and tested (INFO)

**Severity:** INFO | **Confidence:** HIGH

Every type listed in `FACT_TYPES` has a corresponding branch in `_evaluate`, a positive test, and at least one negative test. No dead code. The type dispatch is exhaustive with a `raise ValueError` catch-all (L488).

### F2: Fuzzy matching is two-stage with documented rationale (INFO)

**Severity:** INFO | **Confidence:** HIGH

The rapidfuzz -> exact-DP pipeline addresses a known limitation (rapidfuzz Indel window trimming). The `max_diffs` budget is respected by the exact DP, not just the approximate locator. Edge case: `max_diffs=0` falls through to exact substring match only (L312-313).

### F3: Math surface correctly preserves structural operators (INFO)

**Severity:** INFO | **Confidence:** HIGH

`_math_surface` uses `textblock2unicode` (LaTeX fold) + whitespace collapse but does NOT pass through `clean_string` (which would strip `^`, `_`, `=`). Case is preserved. Display math (`\[...\]`) is folded to inline form before folding. Doubled backslashes are undoubled. All three are tested with dedicated canaries.

### F4: Anchorless table facts have documented ANY-semantics gap (LOW)

**Severity:** LOW | **Confidence:** HIGH

Same as C08-F2. Without `table_heading`, a decoy table sharing a cell value can exploit the ANY-match path. Documented in CLAUDE.md and mitigated by authoring practice.

### F5: `auto_baseline_checks` is unwired (LOW)

**Severity:** LOW | **Confidence:** HIGH

`auto_baseline_checks` (facts.py L648-691) runs two zero-authoring sanity checks (non-empty alnum, no repeated n-grams) but is not wired into `whisker facts` or `whisker guard` output. Callable standalone only. Tests exist (`test_auto_baseline_*`), but the checks do not gate anything in production.

### F6: `image_ref` tests presence only, not fidelity (INFO)

**Severity:** INFO | **Confidence:** HIGH

`image_ref` (facts.py L478-487) checks that an `![...](...)` pattern exists in the markdown, optionally matching a substring. It does not verify image content, pixel fidelity, or raster extraction. This is by design (CLAUDE.md "Known gaps" item 13) and correctly scoped.

## 5. False-Pass Hypothesis

**Q:** Could a fact pass when the content is actually wrong?

1. **Normalized surface hides operators:** The normalized surface (`clean_string`) strips `!=`, `>=`, etc. A fact asserting `x >= y` on the default surface would pass even if the markdown says `x <= y`. **Mitigation:** `surface: "raw"` mode exists for operator-sensitive assertions, and `math` uses its own surface. Code/xref are always raw.

2. **Fuzzy budget too generous:** A `max_diffs=3` budget on a 5-character needle could match almost anything. **Mitigation:** Budget is per-fact, human-authored, and typically 0-2 for precise needles.

3. **Table heading-less ANY-match:** See F4. A decoy table can satisfy an anchorless fact.

4. **Empty facts file:** `test_corpus_has_at_least_one_comprehension_paper` and `_warn_vacuous_reports` prevent vacuous green.

## 6. Gate/Dimension Mapping

| Gate | Dimension | Status |
|------|-----------|--------|
| D4 Per-axis null-eligibility | N/A for Lane 3 (all types are always evaluated) | N/A |
| D5 Quality-stability | 37 verified facts, 3 canaries, all passing deterministically | PASS |

## 7. Limitations

- This report audits the fact engine implementation. Corpus coverage (which papers, which facts) is a content quality question outside this scope.
- The `auto_baseline_checks` gap (F5) is a known, documented limitation.
- Real-LLM readback validation is BLOCKED (E9).

## 8. Conclusion

Lane 3 comprehension is well-implemented. All 8 fact types have correct evaluation logic, appropriate surface selection, and both positive and negative test coverage. Fuzzy matching uses a rigorous two-stage pipeline. The provenance gate (verified vs draft) is correctly enforced. The main gaps are documented: anchorless table ANY-semantics and unwired auto-baseline checks.

**Gate verdict: PASS**
