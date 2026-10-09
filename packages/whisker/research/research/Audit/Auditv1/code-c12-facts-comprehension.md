# C12 -- Facts and Comprehension Auditor

**Mandate:** Deep-audit Lane 3 comprehension.
**Auditor role:** Facts and Comprehension Auditor
**Date:** 2026-07-19
**Scope:** `facts.py`, `tables.py`, `test_facts.py`, `metrics.py` (normalized_text, textblock2unicode)
**Focus dimensions:** D4 (construct validity), D5 (coverage)

---

## 1. Fact Type Coverage

### F1: All 8 fact types implemented and dispatched

- **Severity:** INFO (confirmed correct)
- **Claim:** `_evaluate` dispatches on `fact.type` for all 8 types: `present`, `absent`, `order`, `table`, `math`, `code`, `xref`, `image_ref`. An unknown type raises `ValueError`.
- **Evidence:** `facts.py:437-488` -- each type has an explicit `if fact.type == FACT_*` branch. Line 488: `raise ValueError(f"unknown fact type {fact.type!r}")`.
- **Affected gate:** Lane 3 comprehension
- **Confidence:** HIGH

### F2: `present` -- fuzzy matching semantics

- **Severity:** INFO (confirmed correct)
- **Claim:** `present` locates the needle in the haystack using `_present_within`, which delegates to `_best_match`. For `max_diffs == 0`, exact substring match via `str.find`. For `max_diffs > 0`, rapidfuzz `partial_ratio_alignment` locates the approximate region, then `_substring_edit_distance` (a free-start/free-end Levenshtein DP) verifies the true edit count within the widened window.
- **Evidence:** `facts.py:299-326` -- `_best_match`: exact substring first, then rapidfuzz locates the alignment, widens by `max_diffs`, and the exact DP confirms. The two-stage approach fixes the documented rapidfuzz Indel boundary-char trimming artifact.
- **Affected gate:** D4 (construct validity of fuzzy matching)
- **Confidence:** HIGH
- **False-pass hypothesis:** rapidfuzz `partial_ratio_alignment` could place the window slightly wrong, but the exact DP on the widened region is the actual gate; rapidfuzz is only the approximate locator.
- **False-fail hypothesis:** If the widened window is still too narrow (rare edge case with clustered edits near both ends), the DP could miss a valid alignment. The `max_diffs` widening on both sides (`start - max_diffs`, `end + max_diffs`) is the documented mitigation.

### F3: `absent` -- negation of present

- **Severity:** INFO (confirmed correct)
- **Claim:** `absent` is the logical negation of `_present_within`. If the needle IS found within budget, the fact fails.
- **Evidence:** `facts.py:441-444`.
- **Confidence:** HIGH

### F4: `order` -- strictly increasing positions

- **Severity:** INFO (confirmed correct)
- **Claim:** For each item in `fact.sequence`, `_position_within` locates it. Positions must be strictly increasing (`pos <= prev_pos` fails). A missing item fails immediately.
- **Evidence:** `facts.py:448-465` -- `pos = _position_within(item, haystack, fact.max_diffs)`, checks `pos == -1` (absent) and `pos <= prev_pos` (not after previous).
- **Affected gate:** D4 (order semantics)
- **Confidence:** HIGH
- **False-pass hypothesis:** If two sequence items happen to share the same best-match start position (different edits at the same location), the `<=` check would correctly fail. No issue.
- **False-fail hypothesis:** None under normalized surface. Under raw surface with overlapping needles, positions might collide, but the strictly-increasing check is intentional.

### F5: `table` -- cell + neighbor verification with heading semantics

- **Severity:** MEDIUM (D4, documented known gap)
- **Claim:** `_check_table` locates a target cell in all tables (pipe + HTML), then verifies directional neighbors. Two semantics: WITH `table_heading`, ALL occurrences in heading-matching tables must satisfy (fail-closed). WITHOUT `table_heading`, ANY occurrence satisfying passes (ANY-semantics).
- **Evidence:** `facts.py:374-423`. The `golden-hook:` comment at line 386-391 documents that anchorless facts remain exploitable by a decoy table.
- **Affected gate:** D4 (table comprehension), D5 (decoy defense)
- **Confidence:** HIGH
- **False-pass hypothesis (D4):** An anchorless fact with a decoy table providing a matching cell + neighbors passes even if the genuine table is corrupted. DOCUMENTED gap. Mitigation: author facts WITH `table_heading` whenever possible.
- **False-fail hypothesis (D4):** A heading-scoped fact fails if ANY occurrence under that heading has wrong neighbors, even if the genuine row is correct but a duplicate heading exists in a decoy table. This is the fail-closed design and is intentional.

### F6: `math` -- LaTeX-folded structural compare

- **Severity:** INFO (confirmed correct)
- **Claim:** `math` uses `_math_surface` which: (1) undoubles `\\command` to `\command`, (2) folds `\[...\]` display math to `\(...\)` inline form, (3) runs `textblock2unicode` (pylatexenc LaTeX-to-unicode), (4) collapses whitespace. Unlike `normalized_text`, it KEEPS `^`, `_`, `=`, case, and relational operators.
- **Evidence:** `facts.py:238-255` -- `_math_surface`. The folding chain: `_fold_display_math_delims(_undouble_latex_backslashes(text))` then `textblock2unicode` then whitespace collapse.
- **Affected gate:** D4 (math construct validity)
- **Confidence:** HIGH
- **Test coverage:** `test_math_structural_pass`, `test_math_missing_exponent_fails`, `test_math_ignores_dollar_delimiters`, `test_canary_math_scope_case_and_relation`, `test_canary_math_scope_display_delimiters`, `test_canary_math_scope_doubled_backslashes`.
- **False-pass hypothesis:** If pylatexenc silently drops a superscript during folding, the comparison would miss the exponent. Mitigated by the test `test_math_missing_exponent_fails`.
- **False-fail hypothesis:** If the markdown uses an unsupported LaTeX dialect, the guard ladder rejects it and falls back to the raw text, which may not match the folded form of the fact. Acceptable: the fact is authored against the source.

### F7: `code` -- raw-surface snippet presence

- **Severity:** INFO (confirmed correct)
- **Claim:** `code` uses `_raw_surface` (whitespace-normalize only) for both needle and haystack. Always uses raw surface regardless of the `surface` field.
- **Evidence:** `facts.py:468-472`. `facts.py:553-555` -- `_fact_from_record` sets `surface=SURFACE_RAW` for code facts.
- **Confidence:** HIGH

### F8: `xref` -- raw-surface revision-sensitive reference

- **Severity:** INFO (confirmed correct)
- **Claim:** `xref` uses `_raw_surface` and always sets `surface=SURFACE_RAW`. Revision sensitivity is preserved (e.g., `[P1234R5]` vs `[P1234R4]`).
- **Evidence:** `facts.py:473-477`, `facts.py:553-555`. Test: `test_xref_fact_wrong_revision`.
- **Confidence:** HIGH

### F9: `image_ref` -- `![...](...)`  presence

- **Severity:** INFO (confirmed correct)
- **Claim:** `image_ref` first checks for any `![...](...)` pattern via `_IMAGE_REF_RE`. If `fact.text` is non-empty, additionally checks that the text substring is present on the raw surface.
- **Evidence:** `facts.py:478-487`. Tests: `test_image_ref_fact_pass`, `test_image_ref_fact_with_text`, `test_image_ref_fact_no_image`.
- **Confidence:** HIGH

---

## 2. Surface Selection: raw vs normalized

### F10: Surface routing is correct

- **Severity:** INFO (confirmed correct)
- **Claim:** `_surface_for` routes based on `fact.surface`: `SURFACE_RAW` returns `_raw_surface` (whitespace-collapse only, preserves operators/case), default returns `normalized_text` (alnum+CJK only). `code`, `xref`, `image_ref` always use raw. `present`, `absent`, `order` can use either. `math` has its own surface (`_math_surface`).
- **Evidence:** `facts.py:429-433` (`_surface_for`), `facts.py:547-555` (forced raw for code/xref/image_ref).
- **Affected gate:** D4 (surface construct validity)
- **Confidence:** HIGH
- **Test coverage:** `test_raw_surface_present_preserves_operators`, `test_raw_surface_preserves_case`, `test_raw_surface_absent`, `test_raw_surface_order`, `test_code_and_xref_always_raw_surface`, `test_canary_operator_flip`.

---

## 3. Decoy-Table Attack Defense

### F11: Heading-scoped ALL-semantics defends against shared-heading decoys

- **Severity:** MEDIUM (D5, partial defense)
- **Claim:** With `table_heading` set, ALL occurrences of the cell in heading-matching tables must satisfy the neighbor checks. A decoy table sharing the heading and contradicting the genuine row fails the fact (fail-closed).
- **Evidence:** `facts.py:409-413` -- the `heading_filter` branch iterates ALL candidates and fails on the first bad occurrence.
- **Test coverage:** `test_canary_decoy_table_all_occurrences` -- the decoy with `table_heading="Feature"` correctly fails. `test_table_heading_all_semantics_pass_when_consistent` -- tables without the heading are ignored.
- **Confidence:** HIGH
- **False-pass hypothesis (D5):** Without `table_heading`, ANY-semantics allows a decoy table with correct neighbors to shadow a corrupted genuine table. DOCUMENTED gap (CLAUDE.md Known gaps #1, golden-hook at facts.py:386).
- **Residual risk:** A sophisticated adversarial corruption that preserves both the heading and the neighbor values (e.g., a column swap that happens to leave the checked neighbors intact) would pass. This is inherent to point-wise neighbor checks; the golden-grid layer (planned) is the structural fix.

---

## 4. `auto_baseline_checks` Status

### F12: `auto_baseline_checks` exists but is unwired

- **Severity:** LOW (D5, documented gap)
- **Claim:** `auto_baseline_checks(md)` runs two zero-authoring checks (non-empty alnum content, no mojibake n-grams). It returns `FactCheck` objects but is NOT wired into `whisker facts` or `whisker guard` output. Callable standalone only.
- **Evidence:** `facts.py:648-691` -- the function exists and is tested. `__main__.py` grep for `auto_baseline` shows zero references in the guard/facts verb paths. CLAUDE.md Known gaps #4 documents this.
- **Affected gate:** D5 (fleet coverage)
- **Confidence:** HIGH
- **Test coverage:** `test_auto_baseline_nonempty_passes`, `test_auto_baseline_nonempty_fails_on_empty`, `test_auto_baseline_repeated_ngrams_passes_clean`, `test_auto_baseline_repeated_ngrams_fails_mojibake`, `test_auto_baseline_all_verified`.

---

## 5. Test Coverage Assessment (`test_facts.py`)

### Fact type coverage in tests:

| Fact type | Tests | Covered? |
|-----------|-------|----------|
| `present` | exact pass, missing fail, fuzzy within budget, fuzzy beyond budget | YES |
| `absent` | pass, fail | YES |
| `math` | structural pass, missing exponent, dollar delimiters, case+relation, display delims, doubled backslashes | YES (comprehensive) |
| `order` | monotonic pass, reversed fail, missing item fail | YES |
| `table` | neighbors pass, left/down, wrong neighbor, missing cell, out of bounds, heading neighbor, fuzzy budget | YES |
| `code` | pass, missing | YES |
| `xref` | pass, wrong revision | YES |
| `image_ref` | pass, with text, no image | YES |

### Additional coverage:

| Area | Tests |
|------|-------|
| Verified gate | unverified not gated, verified gates, no verified passes |
| Reporting | by_type macro average |
| Loader/validation | JSONL roundtrip, checked promotion, invalid JSON line number, unknown type, present requires text, order requires 2 items, table requires cell+neighbors, bad direction, negative max_diffs, bool max_diffs, duplicate ID, neighbor sort order, default ID |
| Decoy defense | heading ALL-semantics, consistent pass, wrong heading fails |
| HTML tables | cell check, scramble detected |
| Canaries | operator flip, pipe in code, math case+relation, display delimiters, doubled backslashes |

**Gaps:** No test exercises the interaction between `auto_baseline_checks` output and the `FactReport` (because they are unwired). No test exercises `image_ref` with `max_diffs > 0` on the path substring.

---

## 6. Summary

| Finding | Severity | Dimension | Verdict |
|---------|----------|-----------|---------|
| F1: All 8 fact types dispatched | INFO | D4 | CONFIRMED |
| F2: Fuzzy matching two-stage (rapidfuzz + exact DP) | INFO | D4 | CONFIRMED |
| F3: absent = negation of present | INFO | D4 | CONFIRMED |
| F4: order = strictly increasing positions | INFO | D4 | CONFIRMED |
| F5: table heading ALL vs ANY semantics | MEDIUM | D4,D5 | CONFIRMED (known gap documented) |
| F6: math LaTeX-folded structural compare | INFO | D4 | CONFIRMED |
| F7: code always raw surface | INFO | D4 | CONFIRMED |
| F8: xref always raw surface | INFO | D4 | CONFIRMED |
| F9: image_ref presence + optional text | INFO | D4 | CONFIRMED |
| F10: Surface routing correct | INFO | D4 | CONFIRMED |
| F11: Decoy defense partial (heading-scoped only) | MEDIUM | D5 | CONFIRMED (known gap) |
| F12: auto_baseline_checks unwired | LOW | D5 | CONFIRMED (known gap) |

**Overall assessment:** Lane 3 comprehension is structurally sound with comprehensive test coverage. The two documented gaps (anchorless table ANY-semantics, auto_baseline_checks unwired) are honestly documented in CLAUDE.md and have planned mitigations (golden-grid layer, wiring into guard output).
