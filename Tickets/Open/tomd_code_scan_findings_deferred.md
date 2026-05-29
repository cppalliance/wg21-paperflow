# tomd Full Code Scan -- Deferred Findings

Date: 2026-05-18
Status: PARKED (not actionable without major refactor risk)
Scope: `packages/tomd/src/tomd/lib/` (27 files, full scan)
Context: Generated during pre-PR cleanup session. These are real findings
but the tomd pipeline is too tightly coupled to safely refactor most of them
without multi-day effort and high regression risk.

---

## Why These Are Parked

The tomd package has ~10k lines of interdependent pipeline code with
circular import chains, multi-signal classification heuristics, and
dual-path extraction logic. Most HIGH findings below require extracting
helpers from 200-380 line functions that were written as monoliths
deliberately (pipeline phase ordering is load-bearing). Touching them
risks subtle regressions in paper conversion quality that tests may
not catch (edge cases in 1000+ real WG21 papers).

Rule: Do NOT attempt these unless a specific bug forces it.

---

## HIGH Severity (10 findings)

### H1. `_run_pipeline` 380 lines (pipeline.py:254)
Extract named phases. RISK: Phase ordering is the pipeline's core
invariant. Extraction changes call order visibility.

### H2. `extract_metadata_from_blocks` 280 lines (wg21.py)
Same issue as H1. Monolith by design.

### H3. `attach_links` O(n^2) (pdf/extract.py:234)
Quadratic: links x blocks x lines x spans. Needs spatial index.
Only matters for 100+ page documents.

### H4. `_normalize_bullets` per-char join (emit.py:246)
Replace with `str.translate`. Low risk but marginal gain.

### H5. Pipe-table assembly 3x (html/render.py:554)
`_render_denormalized_table`, `_render_table_flat`, `_render_table`
all build header + separator + rows identically.

### H6. "append-to-reply-to" pattern 4x (html/extract.py:633)
Repeated in schultke, wg21, handwritten, generic extractors.

### H7. Regex compiled in loop (html/extract.py:104)
`_AT_SPLIT` and `_DOT_WORD` inside per-line loop.

### H8. Meta-label alternation 3x (shared.py:184)
`_FREEFORM_META_LABEL_RE`, `_HEADING_META_LABEL_RE`, `_LIST_META_LABEL_RE`
share the same alternation string.

### H9. Title-echo detection copy-pasted (strip.py pass 1 vs pass 2)
The title-stem-overlap check is duplicated between the two passes of
`strip_metadata_headings`. Author-matching was already extracted (3.4a)
but title-echo remains.

### H10. FALSE POSITIVE: convert.py:96 front-matter strip
This is the double `strip_leading_h1` call. Adversarial check proved
the second call is REQUIRED (catches H1 exposed after content stripping).
Not a duplicate. Do not touch.

---

## MEDIUM Severity (14 findings)

- M1. `_BARE_NUM_RE` compiled per call (toc.py:124)
- M2. `_PRE_FIELD_RE` compiled per call (html/extract.py:729)
- M3. Meta-region builder duplicated (html/extract.py:820 vs 888)
- M4. `_render_children_joined` pattern 7x (html/render.py:194)
- M5. x-midpoint recomputed 4x (pipeline.py:108)
- M6. `_assign_emdash_nesting` O(n^2) (emit.py:509)
- M7. 5 linear scans instead of 1 Counter (qa.py:315)
- M8. HSV recomputation cacheable (wording.py)
- M9. `_COALESCE_CODE_RE` / `_STRUCTURAL_CODE_RE` overlap (INTENTIONAL)
- M10. `avg_fs` shadowed in inner loop (pdf/extract.py:170)
- M11. Space-span inherits wrong monospace status (pdf/extract.py:183)
- M12. Sequential if/return -> single expression (mono.py:186)
- M13. Month-name alternation duplicated (shared.py:887 vs 896)
- M14. Regex + constants inside function body (abstract.py)

---

## LOW Severity (15 findings)

- L1. `color == 0x000000` unreachable (cleanup.py:307)
- L2. `strip_freeform_metadata_lines` single-consumer wrapper (shared.py:529)
- L3. Docstring restates constants (shared.py:74)
- L4. `_render_inline` single-consumer wrapper (render.py:720)
- L5. Unreachable fallback in `_inline_text` (render.py:821)
- L6. `_render_heading` returns "" vs None inconsistency (render.py:248)
- L7. `_EMAIL_TAGS` list inside function body (html/extract.py:855)
- L8. `result.page_count > 0` always true (pipeline.py:327)
- L9. `_TOC_LABEL_MAX_WORDS` inside function body (pipeline.py:598)
- L10. `sum([s1,s2,s3])` -> `s1+s2+s3` (mono.py:186)
- L11. `if ":" in line` double-checked (qa.py:108)
- L12. `_score` unreachable empty-output branch (qa.py:363)
- L13. `except (ValueError, KeyError)` too broad (pdf/extract.py:213)
- L14. Unreachable `if not sec.lines` branch (emit.py:99)
- L15. `_render_group` closure could be module-level (emit.py:330)

---

## Already Fixed (this session)

These findings overlapped with what was already done:

- table.py 4x table-text-builder -> extracted `_render_table_text` (3.5)
- strip.py author-matching 2x -> extracted `_matches_author_name` (3.4a)
- cleanup.py fitz lazy import -> documented with comment (2.3)
- strip_leading_h1 double call -> verified as REQUIRED, not redundant (3.10)
