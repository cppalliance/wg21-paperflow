# C18 Grounding and Source Router

**Role**: Audit evidence grounding rules and source-unit risk routing.
**Audited state**: whisker 0.5.0, HEAD 51cb704 + local mods.
**Gates**: D1 (All LLM calls via pipeline), D6 (Structured output).

## 1. Scope

Verify the deterministic evidence grounding mechanism (exact/fuzzy/normalized),
PDF/HTML source routing, quote allocation, source verification, and ungrounded
demotion rules.

## 2. Commands and Exits

```
uv run --package whisker pytest packages/whisker/tests/test_source_router.py -v
uv run --package whisker pytest packages/whisker/tests/test_source_aware_integration.py -v
```

Exit: Offline suite passes (E1). Grounding and routing are pure Python (no
LLM required), so test evidence is fully available.

## 3. Current Evidence

### 3.1 Three-tier grounding (grounding.py)

`ground_spans()` implements three tiers per quote, in model-output order:

1. **Exact (monotonic DP)**: Ported from langextract (Google, Apache-2.0).
   `_select_monotonic_matches()` uses a dynamic programming approach: repeated
   evidence phrases map to successive non-overlapping occurrences. Each exact
   match produces a `(start, end)` char interval in the raw markdown. A
   post-alignment guard (`_post_align_guard`) rejects any interval whose raw
   slice does not normalize back to the quote.

2. **Fuzzy substring**: `normalized_text()` normalization applied to both
   quote and document. If the normalized quote appears as a substring of the
   normalized document, it grounds as `fuzzy` (no char interval).

3. **Fuzzy ratio**: `partial_ratio` from rapidfuzz, gated by two constants:
   - `EVIDENCE_FUZZY_FLOOR` (0.90): Minimum ratio threshold.
   - `EVIDENCE_MIN_FUZZY_CHARS` (20): Minimum normalized quote length.
   Short generic phrases ("the committee") cannot clear the ratio against a
   whole document because they are below the min-chars threshold.

A quote that grounds at none of the three tiers is dropped as ungrounded.
The `ground_spans()` function returns `(grounded: list[GroundedSpan], dropped: int)`.

### 3.2 Page-scoped grounding (ground_page_spans)

`ground_page_spans()` uses a length-relative fuzzy tier instead of the
document-wide `EVIDENCE_FUZZY_FLOOR`. The threshold is
`1.0 - PAGE_QUOTE_MAX_DIFFS / len(quote)`, keeping short quotes strict and
giving long quotes proportional slack. This mirrors the olmocr-bench pattern
(documented in constants.py lines 199-204).

### 3.3 Quote sanitization and filtering

Several regex patterns filter quotes that are structurally not evidence:

- `_FRONT_MATTER_LABEL_RE`: Rejects quotes that are front-matter labels
  (date, document, title, etc.) because these map to YAML, not body content.
- `_TOC_QUOTE_RE`: Rejects "Table of Contents" / "Contents" labels.
- `_PAGE_FURNITURE_RE`: Rejects page numbers and running headers.
- `_RUNNING_HEADER_RE`: Rejects document-number + short text patterns.
- `_TOC_ENTRY_RE`: Strips trailing page numbers from TOC-like entries.

These filters run within `classify_candidate_evidence()` before candidate
matching, preventing false missing-content claims from structural elements
the converter deliberately removes.

### 3.4 Candidate evidence classification

`classify_candidate_evidence()` (grounding.py) classifies each source-grounded
quote against the candidate markdown:

- **present_in_candidate**: Exact (operator-preserving) or shallow
  Markdown-aware match refutes the Missing claim.
- **candidate_not_found**: The verifier could not locate the quote. Retained
  as evidence to inspect, never described as proof of absence.
- **ambiguous**: Fuzzy, sanctioned, or surface-sensitive matching cannot
  support a binary claim. The verifier abstains.

This three-state classification is intentionally non-binary (documented in
`tapetum_llm.md` lines 44-47).

### 3.5 Source router: PDF path

`route_pdf_units()` (source_router.py) receives `PageUnit` objects extracted
by `textlayer.py` and the candidate markdown. For each page unit:

1. Computes `content_recall(candidate_md, page_text)`.
2. Flags pages below `SECTION_RECALL_FLOOR` (0.90) with signal `low_recall`.
3. Counts tracked C++ keywords (`constexpr`, `template`, etc.) in source
   vs candidate. Flags delta >= `TOKEN_DELTA_THRESHOLD` (5) with signal
   `token_delta`.
4. Checks for heading drift between source heading candidates and markdown
   headings. Flags mismatches with signal `heading_drift`.
5. Checks for missing code blocks and captions.

The router reads ONLY source units and candidate markdown. It never reads
the deterministic whisker sidecar (lane independence, documented in
`tapetum_llm.md` line 104).

### 3.6 Source router: HTML path

`route_html_units()` (source_router.py) receives `SectionUnit` objects from
`html_outline.py`. Applies the same recall/keyword/heading/code checks at
section granularity instead of page granularity.

### 3.7 Unit check cap

`MAX_UNIT_CHECKS` (5): If more than 5 units are risky, the paper verdict is
capped at `review` without individual LLM calls. Same pattern as
`MAX_PAGE_ESCALATIONS` for the monolith page screen.

### 3.8 Ungrounded demotion rules

Evidence grounding feeds into verdict computation in multiple places:

1. `_custom_decide()` (adjudicate.py lines 321-341):
   - Non-pass verdict with no grounded evidence -> `review`
   - Pass with emitted but entirely dropped evidence -> `review`
   - Pass with only fuzzy evidence (no exact) -> `review`

2. `_fold_monolith_verdict()` (pdf_judge.py lines 358-382):
   - Source-ungrounded quotes or ambiguous candidate matches -> `review`
   - All missing claims refuted in candidate -> `pass`
   - Any `candidate_not_found` -> preserve or cap verdict

3. `_escalation_signals()` (adjudicate.py line 268):
   - Ungrounded evidence in Tier-1 triggers SIGNAL_UNGROUNDED_EVIDENCE,
     causing Tier-2 escalation.

### 3.9 Test coverage

`test_source_router.py` tests:
- PDF and HTML routing with synthetic page/section units
- Recall-based flagging
- Keyword delta detection
- Heading drift detection
- Code block presence checks

`test_source_aware_integration.py` tests:
- End-to-end integration of source routing + unit checks + verdict folding

All offline (pure Python, no LLM). Tests pass in E1.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | Three-tier grounding (exact DP, fuzzy substring, fuzzy ratio) with appropriate thresholds | Informational | HIGH |
| F2 | Quote sanitization filters prevent false claims from structural elements | Informational | HIGH |
| F3 | Three-state candidate classification (present/not_found/ambiguous) prevents premature binary claims | Informational | HIGH |
| F4 | Source router is lane-local: never reads deterministic whisker sidecar | Informational | HIGH |
| F5 | Unit check cap prevents unbounded LLM calls on pathological papers | Informational | HIGH |
| F6 | Ungrounded evidence triggers safety demotions at multiple points | Informational | HIGH |

No violations found.

## 5. False-Pass Hypothesis

**Could a false-positive grounding clear a genuinely missing quote?**

The exact tier's post-alignment guard rejects intervals whose raw slice does
not normalize back to the quote. The fuzzy tier requires a 0.90 partial_ratio
AND a minimum of 20 normalized chars. A short generic phrase cannot
accidentally clear against the whole document. The risk is low.

**Could the router miss a genuinely risky region?**

The router uses `SECTION_RECALL_FLOOR` (0.90) and `TOKEN_DELTA_THRESHOLD` (5).
A region with 89% recall but significant content drift would pass. However,
the monolith LLM call runs first and catches global issues; the router is a
supplementary refinement for localized gaps. This is a documented design
trade-off, not a defect.

## 6. Gate/Dimension Mapping

- **D1 (All LLM via pipeline)**: PASS. Grounding and routing are pure Python.
  Unit-check LLM calls go through `run_judge_task()` via `AgentBackend.run()`.
- **D6 (Structured output)**: PASS. Grounding verifies LLM evidence quotes
  against source text deterministically. All unit-check LLM calls use
  `output_type=UnitCheck` (pydantic model).

## 7. Limitations

- Grounding and routing are fully testable offline (pure Python). No runtime
  limitation for this role's core checks.
- The interaction between grounding results and live LLM behavior (whether
  the model produces groundable quotes in practice) requires runtime testing.
- Fuzzy grounding thresholds (0.90 ratio, 20 char minimum) are heuristic.
  Edge cases near the threshold boundary are inherently uncertain.

## 8. Conclusion

The grounding mechanism is architecturally sound: a three-tier approach
(exact DP, fuzzy substring, fuzzy ratio) with appropriate thresholds and
minimum-length gates prevents both false grounding of short generic phrases
and false rejection of legitimate evidence. The source router maintains
lane independence (never reads det sidecar) and provides bounded unit
checks with a cap to prevent unbounded LLM calls. Ungrounded evidence
triggers safety demotions at multiple points in the cascade. All grounding
and routing logic is pure Python and fully testable offline.
