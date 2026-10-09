# C15 -- Metric Construct-Validity Auditor

**Mandate:** Verify NID/NED, TEDS/GriTS, MHS, reading order, content recall, fidelity-vs-comprehension separation.
**Auditor role:** Metric Construct-Validity Auditor
**Date:** 2026-07-19
**Scope:** `metrics.py`, `match.py`, `constants.py`, `test_metrics.py`, `test_match.py`
**Focus dimension:** D4 (construct validity of every metric)

---

## 1. `normalized_text`: clean_string + textblock2unicode (OmniDocBench normalizer)

### F1: `normalized_text` is the verbatim OmniDocBench composition

- **Severity:** INFO (confirmed correct)
- **Claim:** `normalized_text(text) = clean_string(textblock2unicode(text))`. `textblock2unicode` folds inline LaTeX (`$...$`, `\(...\)`) to unicode via pylatexenc with OmniDocBench's guard ladder. `clean_string` strips escapes, normalizes circled glyphs (`replace_textcircle`), and keeps only `\w` + CJK (`\u4e00-\u9fff`).
- **Evidence:** `metrics.py:338-340` (`normalized_text` = `clean_string(textblock2unicode(text))`). `metrics.py:314-335` (`textblock2unicode`: inline regex `_INLINE_REG`, guard ladder: `_should_skip_inline_textblock_formula`, `safe_latex_to_text`). `metrics.py:118-126` (`clean_string`: `replace_textcircle`, escape removal, `_CLEAN_KEEP_RE` = `[^\w\u4e00-\u9fff]`).
- **Affected gate:** D4 (text-axis normalizer)
- **Confidence:** HIGH
- **Test coverage:** `test_clean_string_strips_formatting_keeps_content`, `test_replace_textcircle_folds_circled_glyphs`, `test_textblock2unicode_folds_inline_latex`, `test_normalized_text_is_clean_string_of_textblock2unicode`, `test_normalized_text_handles_malformed_latex_without_raising`.
- **False-pass hypothesis:** `clean_string` does NOT strip YAML front-matter keys (they normalize as content tokens). On real papers these are negligible (CLAUDE.md documents this explicitly).
- **False-fail hypothesis:** If pylatexenc chokes on malformed LaTeX, the guard ladder returns the raw text, which then goes through `clean_string`. The metric degrades gracefully (never crashes, never silently drops content).

---

## 2. `text_nid`: NID via rapidfuzz

### F2: NID uses rapidfuzz (MIT) for char-level edit distance

- **Severity:** INFO (confirmed correct)
- **Claim:** `normalized_edit_distance(a, b)` returns `Levenshtein.distance(a, b) / max(len(a), len(b))`, using `rapidfuzz.distance.Levenshtein` (MIT-licensed). `text_nid(a, b)` returns `1.0 - normalized_edit_distance` after whitespace normalization.
- **Evidence:** `metrics.py:64-78` (`normalized_edit_distance`): `_Lev.distance(a, b) / longest`. `metrics.py:343-350` (`text_nid`): `1.0 - normalized_edit_distance(_normalize_text(a), _normalize_text(b))`.
- **Affected gate:** D4 (edit distance correctness)
- **Confidence:** HIGH
- **Test coverage:** `test_ned_identical_and_empty`, `test_text_nid_whitespace_insensitive`.
- **Provenance:** rapidfuzz is the MIT-licensed sibling of the GPL `levenshtein` package (same maintainer, same algorithm). Score parity is tested in `test_edit_distance_parity.py`.

---

## 3. TEDS: Verbatim PubTabNet/OmniDocBench Port

### F3: TEDS is a verbatim PubTabNet/OmniDocBench port (lxml DOM -> apted)

- **Severity:** INFO (confirmed correct)
- **Claim:** The TEDS implementation follows the PubTabNet/OmniDocBench algorithm verbatim: parse HTML tables with lxml, convert to `_TableTree` nodes, compute APTED tree edit distance with `_TedsConfig` (tag+colspan+rowspan rename cost, char-level Levenshtein for td content), normalize by `max(xpath('.//*'))` descendants.
- **Evidence:** `metrics.py:392-551`. The class hierarchy: `_TableTree(Tree)`, `_TedsConfig(Config)`, `_TEDS` with `tokenize`, `load_html_tree`, `evaluate`. The `evaluate` method at line 490-516: lxml parse, xpath `body/table`, strip ignored nodes, count `.//*` descendants, compute APTED distance, return `1 - distance/n_nodes`.
- **Affected gate:** D4 (TEDS construct validity)
- **Confidence:** HIGH
- **Adaptations from OmniDocBench:** (1) privatized names, (2) dropped batch/CLI helpers, (3) added zero-denominator guard (`n_nodes == 0` returns 1.0 instead of division-by-zero). These are documented in the docstring.
- **Test coverage:** `test_teds_identical_table_is_one`, `test_teds_text_change_reduces_score`, `test_teds_missing_row_reduces_score`, `test_teds_empty_strings_score_zero`, `test_teds_structure_only_ignores_cell_text`, `test_teds_golden_matches_pubtabnet_definition` (pinned 2x1 vs 1x1 = 0.5).

### F4: TEDS normalization: th->td, thead/tbody unwrapped

- **Severity:** INFO (confirmed correct)
- **Claim:** `_normalize_table_html` converts `<th>` to `<td>` (PubTabNet's `load_html_tree` drops th text) and unwraps `<thead>/<tbody>/<tfoot>` so rows sit directly under `<table>`, matching OmniDocBench preprocessing.
- **Evidence:** `metrics.py:519-537`.
- **Confidence:** HIGH

---

## 4. MHS: mistune CommonMark AST

### F5: MHS uses mistune CommonMark AST for heading parsing

- **Severity:** INFO (confirmed correct)
- **Claim:** `_parse_headings` uses mistune's AST renderer to parse headings. ATX and setext headings are both captured. Inline markup is flattened to prose. Front matter is stripped first. Only top-level headings are collected (headings nested in blockquotes/lists are skipped).
- **Evidence:** `metrics.py:558` -- `_AST_RENDERER = mistune.create_markdown(renderer="ast", plugins=["table"])`. `metrics.py:583-603` (`_parse_headings`): strips front matter, iterates AST tokens, extracts `type == "heading"`, flattens inline text.
- **Affected gate:** D4 (heading-tree construct validity)
- **Confidence:** HIGH
- **Test coverage:** `test_parse_headings_atx`, `test_parse_headings_setext`, `test_parse_headings_flattens_inline_markup`, `test_parse_headings_strips_front_matter`, `test_parse_headings_suppresses_fenced_code`, `test_parse_headings_skips_nested_headings`.

### F6: MHS uses the same APTED engine as TEDS

- **Severity:** INFO (confirmed correct)
- **Claim:** `mhs` builds a heading tree nested by level (`_build_heading_tree`), then computes APTED tree edit distance with `_MhsConfig` (unit insert/delete, NED rename), normalized by `max(node_count)`. The same `APTED` engine used for TEDS.
- **Evidence:** `metrics.py:678-693`. `_MhsConfig` at line 618-640: `delete=1.0`, `insert=1.0`, `rename=normalized_edit_distance(text)` or `0.0` for structure_only.
- **Affected gate:** D4 (MHS construct validity)
- **Confidence:** HIGH
- **Test coverage:** 8 parity vectors pinned from the retired Zhang-Shasha engine (`_MHS_PARITY` in `test_metrics.py`), plus `test_mhs_identical_is_one`, `test_mhs_level_change_reduces_score`, `test_mhs_no_headings_is_one`, `test_mhs_counts_setext_headings`.

---

## 5. Content Recall: Multiset Bag-of-Words

### F7: `content_recall` is multiset bag-of-words (NOT sequence-dependent)

- **Severity:** INFO (confirmed correct)
- **Claim:** `content_recall(candidate, reference)` tokenizes both sides via `content_tokens` (textblock2unicode + lowercase + `\w+` split), builds `Counter` bags, computes `sum(min(count, hyp[token]))` / `sum(ref.values())`. Order-invariant: reordering the candidate does not change recall. Extra candidate words are not penalized.
- **Evidence:** `metrics.py:372-389`. `content_tokens` at line 358-369: `_CONTENT_TOKEN_RE.findall(textblock2unicode(text).lower())`.
- **Affected gate:** D4 (content-recall construct validity)
- **Confidence:** HIGH
- **Test coverage:** `test_content_recall_identical_is_one`, `test_content_recall_empty_reference_is_one`, `test_content_recall_dropped_words`, `test_content_recall_is_order_invariant`, `test_content_recall_ignores_extra_candidate_words`, `test_content_recall_respects_multiplicity`.

---

## 6. Reading Order NED: Separate and Never Gates

### F8: `reading_order_ned` is SEPARATE from content metrics and NEVER gates

- **Severity:** INFO (confirmed correct)
- **Claim:** `reading_order_ned` computes a Levenshtein distance over block-index sequences (GT canonical order vs pred-matched order), normalized to [0,1]. It is computed in the same matching pass as `block_text_nid` but is a SEPARATE metric. It NEVER appears in `GUARD_REGRESSION_AXES`, is never a verdict flag, and is explicitly marked advisory.
- **Evidence:** `match.py:279-295` (`reading_order_ned`). `constants.py:127` -- `GUARD_REGRESSION_AXES = ("nid", "teds", "mhs", "content_recall", "overall")` -- reading_order is absent. CLAUDE.md: "reading order never gates content". `guard.py:42-43` docstring: "Reading order is carried for reporting but never gates."
- **Affected gate:** D4 (metric-gate separation)
- **Confidence:** HIGH

---

## 7. Block-Matched NID: `match.py`

### F9: `block_text_nid` is reorder-robust

- **Severity:** INFO (confirmed correct)
- **Claim:** `block_text_nid` splits both documents into paragraph blocks, normalizes via `normalized_text`, builds a NED cost matrix, Hungarian-assigns, accepts at <= 0.70 NED, fuzzy-rescues unmatched GT blocks at < 0.40 NED, then computes `1 - sum(edit_num)/sum(upper_len)` (OmniDocBench `edit_whole`). Because blocks are matched independently of position, a faithful reflow scores high even when block order changes.
- **Evidence:** `match.py:140-211` (`match_blocks`), `match.py:214-219` (`block_edit_whole`), `match.py:268-276` (`block_text_nid`).
- **Affected gate:** D4 (block-matching construct validity)
- **Confidence:** HIGH
- **Fallback:** Papers exceeding `BLOCK_MATRIX_CELL_BUDGET` (400,000 cells) fall back to whole-document `text_nid` (line 253-255 in `block_metrics`).

---

## 8. Fidelity-vs-Comprehension Separation

### F10: Lane 2 (fidelity) and Lane 3 (comprehension) are architecturally separate

- **Severity:** INFO (confirmed correct)
- **Claim:** Fidelity metrics (nid, teds, mhs, content_recall) live in `metrics.py` and `match.py`. Comprehension facts live in `facts.py`. The two lanes use different surfaces (normalized_text vs type-specific surfaces), different evaluation logic (edit distance/tree distance vs assertion-based), and gate independently. A paper can pass fidelity and fail comprehension (a reflow scrambles a table cell), or vice versa.
- **Evidence:** The entire architectural separation documented in CLAUDE.md "Three lanes (do not conflate them)": "Fidelity is not comprehension." The code paths are structurally independent: `bench.py`/`guard.py` call `metrics.py`/`match.py`; `facts.py` has its own evaluation engine.
- **Affected gate:** D4 (construct separation)
- **Confidence:** HIGH

---

## 9. GriTS-Con (Advisory)

### F11: GriTS-Con is advisory and never gated

- **Severity:** INFO (confirmed correct)
- **Claim:** `grits_con` (GriTS-Con cell-content F1) is computed in `bench.py` via the `grits-metric` package but is carried as a SEPARATE advisory axis, never folded into `overall`, and never gated. It is excluded from `GUARD_REGRESSION_AXES`.
- **Evidence:** `constants.py:127` -- `GUARD_REGRESSION_AXES` does not include `grits_con`. CLAUDE.md bench description: "grits_con (GriTS-Con cell-content F1, complementary to teds) are reported as separate ADVISORY axes, never folded into overall and never gated."
- **Affected gate:** D4 (metric authority boundary)
- **Confidence:** HIGH

---

## 10. Summary

| Finding | Severity | Dimension | Verdict |
|---------|----------|-----------|---------|
| F1: normalized_text = clean_string(textblock2unicode) | INFO | D4 | CONFIRMED |
| F2: NID uses rapidfuzz (MIT) char-level Levenshtein | INFO | D4 | CONFIRMED |
| F3: TEDS is verbatim PubTabNet/OmniDocBench port | INFO | D4 | CONFIRMED |
| F4: TEDS normalization (th->td, unwrap) correct | INFO | D4 | CONFIRMED |
| F5: MHS uses mistune CommonMark AST | INFO | D4 | CONFIRMED |
| F6: MHS uses same APTED engine as TEDS | INFO | D4 | CONFIRMED |
| F7: content_recall is multiset bag-of-words | INFO | D4 | CONFIRMED |
| F8: reading_order_ned separate and never gates | INFO | D4 | CONFIRMED |
| F9: block_text_nid is reorder-robust | INFO | D4 | CONFIRMED |
| F10: Fidelity vs comprehension architecturally separate | INFO | D4 | CONFIRMED |
| F11: GriTS-Con advisory and never gated | INFO | D4 | CONFIRMED |

**Overall assessment:** Every metric has clear construct validity grounded in published benchmarks (PubTabNet, OmniDocBench, DP-Bench, Docling). The implementation is faithful to the referenced algorithms, with adaptations documented. The fidelity-vs-comprehension separation is architecturally enforced, not just documented. Reading order and GriTS-Con are correctly excluded from all gates. No material construct-validity defects found.
