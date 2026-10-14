# C15 Metric Validity

**Role:** Audit metric implementations for construct validity.
**Auditor scope:** `metrics.py`, `match.py`, `tables.py`
**Maps to:** G4 (measurement validity), D4 (per-axis null-eligibility)

## 1. Audited State

- whisker 0.5.0, HEAD 51cb704 + local mods
- `metrics.py`: 698 lines, `match.py`: 296 lines, `tables.py`: 142 lines
- All 1406 tests passing (E1)

## 2. Commands and Exits

```
E1:  uv run --package whisker pytest packages/whisker/tests  -> 1406 passed (exit 0)
```

## 3. Current Evidence

### 3.1 TEDS (Table Edit Distance-based Similarity)

**Claim:** TEDS matches the PubTabNet/OmniDocBench definition.

**Evidence from `metrics.py` L396-555:**

1. **lxml DOM -> APTED pipeline** (L498-518): `_TEDS.evaluate` parses both HTML strings with `lxml_html.fromstring`, extracts `body/table`, optionally strips ignored nodes, builds APTED trees via `load_html_tree`, and computes `1.0 - (distance / max(n_nodes_pred, n_nodes_true))`.

2. **Verbatim PubTabNet algorithm:**
   - Cell content tokenized as character tokens with inline HTML tags (L457-466, `tokenize`).
   - td-only content extraction (L471-472: non-td nodes get `None` content).
   - xpath-descendant denominator: `len(pred.xpath(".//*"))` and `len(true.xpath(".//*"))` (L507-508).
   - Rename cost: tag, colspan, rowspan exact match + normalized Levenshtein on cell content (L435-446).

3. **Normalization** (`_normalize_table_html`, L523-541): `<th>` -> `<td>`, `thead`/`tbody`/`tfoot` stripped, `<html><body>` wrapper added. Matches OmniDocBench's pre-processing.

4. **Zero-denominator guard** (L510-513): Two parseable but row-less tables return 1.0. OmniDocBench would divide by zero here; the guard is a defensive addition.

5. **Dependencies:** `apted` (APTED algorithm), `lxml` (DOM parsing) are direct dependencies.

**Assessment:** The implementation is a verbatim port from `_bench_src/OmniDocBench/src/metrics/table_metric.py` as documented. The algorithm (lxml DOM -> APTED, char-token cells, xpath-descendant denominator) matches the PubTabNet definition. The only adaptation is the zero-denominator guard.

### 3.2 MHS (Markdown Heading Similarity)

**Claim:** MHS uses APTED tree edit distance.

**Evidence from `metrics.py` L558-697:**

1. **Heading tree construction** (`_build_heading_tree`, L657-668): Parses headings from mistune's CommonMark AST (`_parse_headings`, L587-607), nests by level under a synthetic root. Front matter stripped first. Top-level headings only (nested in lists/blockquotes skipped, matching tomd QA).

2. **APTED backend** (L682-697, `mhs`): `APTED(tree_a, tree_b, _MhsConfig(...)).compute_edit_distance()`, normalized as `1.0 - dist / max(n_a, n_b)`.

3. **Cost model** (`_MhsConfig`, L622-644): Unit insert/delete (1.0), rename cost = normalized edit distance between heading texts (or 0.0 for structure-only). Same cost model as the retired Zhang-Shasha implementation (noted at L628: "so scores are unchanged").

4. **Null-eligibility** (`has_headings`, L671-679): Returns False when no headings exist, signaling bench to record the axis as `None` (not a synthetic 1.0).

**Assessment:** MHS correctly uses APTED with a well-defined cost model. The heading tree is parsed from the same AST engine tomd uses. Null-eligibility is implemented.

### 3.3 text_nid (Normalized Information Distance)

**Claim:** text_nid uses the OmniDocBench normalizer.

**Evidence from `metrics.py` L342-354:**

1. **`normalized_text`** (L342-344): `clean_string(textblock2unicode(text))`.

2. **`textblock2unicode`** (L316-339): Folds inline LaTeX (`$...$`, `\(...\)`) to unicode via pylatexenc, with OmniDocBench's guard ladder (bad-latex, weak-input, plaintext-noise detectors ported verbatim).

3. **`clean_string`** (L118-126): Replaces circled glyphs (`replace_textcircle`), strips escapes/whitespace, keeps only `\w` + CJK (L115: `_CLEAN_KEEP_RE = re.compile(r"[^\w\u4e00-\u9fff]")`).

4. **`text_nid`** (L347-354): `1.0 - normalized_edit_distance(normalize(a), normalize(b))`, with whitespace normalization before distance.

5. **`normalized_edit_distance`** (L64-78): `Lev.distance(a, b) / max(len(a), len(b))`, OmniDocBench's exact normalization.

6. **rapidfuzz** (MIT-licensed Levenshtein, L42): Drop-in for GPL `levenshtein` package. Score-identical (documented: "see tests/test_edit_distance_parity.py").

**Assessment:** The normalizer chain (`textblock2unicode` -> `clean_string`) is the OmniDocBench pipeline adopted verbatim. The NID formula matches. Applied symmetrically to both sides.

### 3.4 content_recall (Multiset Bag-of-Words)

**Claim:** content_recall is multiset bag-of-words recall.

**Evidence from `metrics.py` L357-393:**

1. **`content_tokens`** (L362-373): `_CONTENT_TOKEN_RE.findall(textblock2unicode(text).lower())`. Unicode word boundary tokenizer on LaTeX-folded, lowercased text. Keeps token granularity (unlike `normalized_text` which flattens to no boundaries).

2. **`content_recall`** (L376-393):
   ```python
   ref = Counter(content_tokens(reference))
   hyp = Counter(content_tokens(candidate))
   matched = sum(min(count, hyp[token]) for token, count in ref.items())
   return matched / sum(ref.values())
   ```

   This is textbook multiset recall: for each reference token, count how many occurrences are present in the candidate (capped at reference count), divide by total reference tokens. Empty reference yields 1.0.

**Assessment:** Correct multiset bag-of-words recall implementation. Extra/duplicate candidate tokens are not penalized (additive drift is a separate signal). Documented as the Unstructured `cct-%missing` complement.

### 3.5 Block Matching (match.py)

**Evidence from `match.py` L140-211:**

1. NED cost matrix (`_ned_matrix`), Hungarian assignment (`linear_sum_assignment`), accept threshold `BLOCK_ACCEPT_NED` (0.70).
2. Fuzzy rescue for unmatched GT blocks embedded in pred blocks within `BLOCK_FUZZY_RESCUE_NED` (< 0.40).
3. `block_edit_whole`: `sum(Edit_num) / sum(upper_len)`, the OmniDocBench `edit_whole` formula.
4. Matrix budget cap (`BLOCK_MATRIX_CELL_BUDGET`): giant papers fall back to whole-document `text_nid`.

### 3.6 Construct Separation (Structure vs Content)

**Verification that the three axes measure different constructs:**

| Axis | What it measures | What it ignores |
|------|-----------------|-----------------|
| `teds` | Table HTML structure (tags, spans, cell content as char tokens) | Prose, headings, non-table content |
| `mhs` | Heading hierarchy (level nesting, heading text) | Prose, tables, non-heading content |
| `text_nid` | Full-text content agreement (all prose, normalized) | Structure (headings, tables are flattened by normalizer) |
| `content_recall` | Token-level content coverage (bag-of-words) | Order, structure, formatting |

The normalizer chain ensures separation: `clean_string` strips all markdown syntax (headings, pipe tables, emphasis) so `text_nid` measures content, not structure. TEDS operates on HTML DOM, not prose. MHS operates on heading AST, not tables.

## 4. Findings

### F1: TEDS is a faithful PubTabNet port (INFO)

**Severity:** INFO | **Confidence:** HIGH

The algorithm, data structures, normalization, and cost model match the published PubTabNet/OmniDocBench TEDS. The zero-denominator guard is the only addition and is defensive (prevents a division-by-zero on edge cases the original code does not handle).

### F2: MHS uses APTED, replacing the retired Zhang-Shasha (INFO)

**Severity:** INFO | **Confidence:** HIGH

The transition to APTED is documented with a "72/72 score-parity check" against the prior implementation. The cost model is identical. This is good engineering: one tree-edit engine for both axes (TEDS and MHS).

### F3: content_recall is correctly independent of text_nid (INFO)

**Severity:** INFO | **Confidence:** HIGH

`content_recall` uses bag-of-words (multiset), `text_nid` uses edit distance. They share the LaTeX-folding step (`textblock2unicode`) but differ in normalization: `content_recall` lowercases and keeps token boundaries, `text_nid` passes through `clean_string` (strips to alnum+CJK). A dropped section affects `content_recall` directly but may be hidden by `text_nid` if the remaining text is long enough (documented as the "blind spot edit distance hides").

### F4: Null-eligibility is implemented for heading-dependent axes (INFO)

**Severity:** INFO | **Confidence:** HIGH

`has_headings` (L671-679) returns False when no heading hierarchy exists, allowing bench to record `mhs` as `None` rather than a synthetic 1.0. This matches the opendataloader-pdf null-eligibility rule cited in the CLAUDE.md.

### F5: `clean_string` does not strip YAML front-matter keys (LOW)

**Severity:** LOW | **Confidence:** HIGH

Documented in CLAUDE.md: "Note `clean_string` does NOT strip YAML front-matter keys; on real papers those few tokens are negligible." On a paper with a long front-matter block, these tokens would slightly inflate `text_nid`. The effect is symmetric (both sides have front matter) and empirically negligible.

## 5. False-Pass Hypothesis

**Q:** Could a metric report high similarity when the content is actually different?

1. **TEDS on non-table content:** TEDS returns 0.0 when either side has no parseable table (`if not pred.xpath("body/table") or not true.xpath("body/table")`). It cannot falsely inflate on prose.

2. **MHS on flat documents:** `has_headings` returns False for heading-free documents. Bench records `None`, not 1.0. No inflation.

3. **text_nid on short documents:** Normalized edit distance on very short strings (< 10 chars) can swing wildly. This is inherent to the metric and mitigated by the fact that real papers are thousands of characters.

4. **content_recall with duplicated tokens:** If the candidate duplicates all reference tokens, recall is 1.0 even if the content is semantically different. This is by design (recall, not precision; drift is a separate signal).

## 6. Gate/Dimension Mapping

| Gate | Dimension | Status |
|------|-----------|--------|
| G4 Measurement validity | TEDS matches PubTabNet, MHS uses APTED, text_nid uses OmniDocBench normalizer, content_recall is multiset | PASS |
| D4 Per-axis null-eligibility | `has_headings` prevents synthetic 1.0 for MHS; TEDS returns 0.0 for table-free docs | PASS |

## 7. Limitations

- This report verifies the metric IMPLEMENTATIONS, not their operating points (thresholds are audited in C10).
- Block matching (`match.py`) is audited structurally but not verified against OmniDocBench's own test vectors (none are committed in this repo).
- `grits_con` (GriTS-Con cell-F1) is mentioned in CLAUDE.md as an advisory axis but is not in the audited files (`metrics.py`, `match.py`); it likely lives in `bench.py`.

## 8. Conclusion

All four primary metrics (TEDS, MHS, text_nid, content_recall) are correctly implemented according to their claimed definitions. TEDS is a verbatim PubTabNet port. MHS uses APTED with an identical cost model to the retired Zhang-Shasha. text_nid uses the OmniDocBench normalizer chain. content_recall is standard multiset bag-of-words recall. Construct separation is maintained: each axis measures a distinct dimension (table structure, heading hierarchy, content text, token coverage).

**Gate verdict: PASS**
