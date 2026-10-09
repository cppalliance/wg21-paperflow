# C18 — Grounding and Source-Router Audit

**Auditor**: Grounding and Source-Router Auditor
**Focus**: D4 (evidence provenance), D5 (grounding fidelity)
**Scope**: `packages/whisker/src/whisker/tapetum_llm/grounding.py`, `source_router.py`
**Date**: 2026-07-19

---

## Executive Summary

Evidence grounding is a three-tier system (exact DP, fuzzy substring, fuzzy ratio) with a post-alignment semantic parity guard. Source-aware routing (v6) classifies candidate evidence with explicit `present_in_candidate` / `candidate_not_found` / `ambiguous` provenance. Shallow guards correctly abstain on link/emphasis reformatting, front-matter migration, table token presence, math folding, TOC entries, page furniture, and running headers. Test coverage is extensive with 20 golden-PR replay fixtures and parametrized edge cases.

---

## Findings

### F1. Three-tier grounding: exact DP → fuzzy substring → fuzzy ratio

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | `ground_spans` implements three tiers per span: (1) monotonic DP exact-occurrence matching with char intervals (ported from langextract), (2) normalized substring check, (3) rapidfuzz `partial_ratio` >= `EVIDENCE_FUZZY_FLOOR` (0.90) gated to quotes >= `EVIDENCE_MIN_FUZZY_CHARS` (20 chars). Unmatched quotes are dropped. |
| **Evidence** | `grounding.py:248-335` (`ground_spans`). `grounding.py:147-213` (`_select_monotonic_matches`, langextract DP port). `grounding.py:324-328` (fuzzy substring: `if norm_quote in norm_md`). `grounding.py:327-331` (fuzzy ratio: `partial_ratio(norm_quote, norm_md) / 100.0 >= EVIDENCE_FUZZY_FLOOR`). `constants.py:67-73` (floor and min-chars constants). |
| **Affected gate** | D4 (evidence provenance), D5 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None. |
| **False-fail hypothesis** | N/A. |

### F2. Post-alignment semantic parity guard prevents wrong-span acceptance

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | After the DP selects a token-aligned interval, `semantic_parity_holds` verifies that: (1) case-sensitive word tokens match, and (2) Unicode punctuation/symbol sequences match. A parity failure downgrades the grounding from `GROUND_EXACT` to `GROUND_FUZZY` (no char interval). |
| **Evidence** | `grounding.py:216-245` (`semantic_parity_holds`). `grounding.py:309-322` (post-alignment guard in `ground_spans`: `if normalized_text(markdown[start:end]) == norm_quote: parity_holds = semantic_parity_holds(span, markdown[start:end])`; if parity fails, grounded as `GROUND_FUZZY` with `None` interval). |
| **Affected gate** | D5 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | The parity check is case-sensitive but LaTeX script groups (`_{...}`, `^{...}`) are pre-normalized on the `math` axis (line 232-234). An exotic math construct not handled by the regex could bypass parity. |
| **False-fail hypothesis** | N/A. |

### F3. `classify_candidate_evidence`: explicit three-status provenance

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | `classify_candidate_evidence` classifies each source-grounded missing-content claim against the candidate markdown: `present_in_candidate` (refuted), `candidate_not_found` (not located), `ambiguous` (uncertain). The function is deliberately asymmetric: only exact+parity matches refute; fuzzy matches abstain. |
| **Evidence** | `grounding.py:419-585` (`classify_candidate_evidence`). `grounding.py:52-53` (status constants: `CANDIDATE_PRESENT`, `CANDIDATE_NOT_FOUND`, `CANDIDATE_AMBIGUOUS`). `grounding.py:466-485` (exact candidate grounding with parity check → `CANDIDATE_PRESENT`). `grounding.py:521-530` (case-folded surface match → `CANDIDATE_AMBIGUOUS`). `grounding.py:545-583` (sanctioned patterns, TOC, page furniture, math folding → `CANDIDATE_AMBIGUOUS` or `CANDIDATE_NOT_FOUND`). |
| **Affected gate** | D4 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None; the function explicitly never upgrades to `present` without parity. |
| **False-fail hypothesis** | N/A. |

### F4. Source misses remain `source_ungrounded` (never falsely confirmed)

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | When a missing-content quote cannot be grounded against the source text (PDF text layer or HTML), it is dropped as ungrounded. The sidecar records `source_ungrounded` count. Source-ungrounded quotes never reach candidate classification. |
| **Evidence** | `pdf_judge.py:678-682` (quotes are grounded against `pdf_text` via `ground_spans`; only `grounded` spans enter `classify_candidate_evidence`). `pdf_judge.py:760-765` (page-escalation quotes grounded via `ground_page_spans`). `unit_judge.py:524-533` (unit check quotes grounded against source text; ungrounded → `source_ungrounded` status). |
| **Affected gate** | D4 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None. |
| **False-fail hypothesis** | N/A. |

### F5. Shallow guards: link/emphasis, front-matter, table, math, TOC, page furniture

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | The candidate classifier has explicit shallow guards that abstain (→ `CANDIDATE_AMBIGUOUS`) rather than falsely claiming presence or absence: markdown link/emphasis reformatting, front-matter label migration, table token presence, math NFKD folding, TOC entries (stem + trailing page number), isolated page numbers, and running headers. |
| **Evidence** | `grounding.py:338-395` (surface helpers: `_markdown_semantic_surface` strips images/links/emphasis/HTML/backticks; `_front_matter_intent` extracts YAML intent). `grounding.py:59-76` (compiled regexes: `_FRONT_MATTER_LABEL_RE`, `_TOC_QUOTE_RE`, `_PAGE_FURNITURE_RE`, `_RUNNING_HEADER_RE`, `_TOC_ENTRY_RE`). `grounding.py:545-583` (sanctioned checks: front-matter labels with YAML, TOC quotes, page furniture, running headers, TOC entry stem, table token presence, math folded surface). Tests: `test_tapetum_llm.py:340-378` (parametrized: sanctioned TOC/page furniture, TOC entry, running header, math reformat). |
| **Affected gate** | D4, D5 |
| **Confidence** | 0.98 |
| **False-pass hypothesis** | A novel reformatting pattern not covered by the shallow guards (e.g., a new HTML construct in tomd's output) could result in `CANDIDATE_NOT_FOUND` when the content is actually present. This is a known limitation of the guard ladder approach. |
| **False-fail hypothesis** | N/A. |

### F6. Duplicate claims are tracked via surface-interval consumption

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | When the LLM emits duplicate missing-content quotes, the classifier tracks consumed presentation-surface intervals. The first occurrence is classified normally; the second cannot reuse the same candidate interval and falls to `CANDIDATE_AMBIGUOUS`. |
| **Evidence** | `grounding.py:397-416` (`_consume_surface_occurrence`: reserves non-overlapping intervals in a sorted consumed list). `grounding.py:460-464` (`claim_consumed_intervals` per `(preserve_operators, semantic_surface)` key). Tests: `test_tapetum_llm.py:380-458` (`test_repeated_quotes_map_deterministically`, `test_duplicate_claims_do_not_reuse_one_candidate_occurrence`, `test_distinct_nested_claims_may_share_candidate_occurrence`). |
| **Affected gate** | D4 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None. |
| **False-fail hypothesis** | N/A. |

### F7. Source router (v6): lane-local, never reads deterministic sidecar

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | `route_html_units` and `route_pdf_units` compare source units directly against candidate markdown. Neither function reads the deterministic whisker sidecar or any whisker-computed signal. Parameters are source units + candidate markdown + (for HTML) source outline. |
| **Evidence** | `source_router.py:8-11` (docstring: "never reads deterministic whisker artifacts"). `source_router.py:149-233` (`route_pdf_units` signature: `page_units, candidate_md`). `source_router.py:236-316` (`route_html_units` signature: `section_units, candidate_md, source_outline`). Tests: `test_source_aware_integration.py:252-268` (`TestLaneIndependence`: verifies router ignores det sidecar, `run_unit_checks` signature has no whisker/det parameter). |
| **Affected gate** | Lane independence (confirmation-bias defense) |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None. |
| **False-fail hypothesis** | N/A. |

### F8. Test coverage: 20 golden-PR replay fixtures + parametrized edge cases

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | `test_pdf_judge.py` has 20 parametrized golden-quote-replay fixtures from PRs #284/#285/#290/#293 with expected dispositions (12 `present_in_candidate`, 8 `candidate_not_found`). `test_tapetum_llm.py` has ~30 parametrized candidate-evidence tests covering operator mismatch, case sensitivity, markdown markup, front-matter, table reformat, math reformat, and more. `test_source_router.py` covers PDF and HTML routing: low recall, token delta, missing captions, heading drift, clean passes, TOC section immunity. |
| **Evidence** | `test_pdf_judge.py:531-649` (`_GOLDEN_QUOTE_REPLAY`, 20 entries). `test_tapetum_llm.py:120-458` (`TestCandidateEvidenceClassification`, ~25 test methods). `test_source_router.py:1-306` (14 test functions). `test_source_aware_integration.py:1-421` (integration tests with monkeypatch). |
| **Affected gate** | D4, D5 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None. |
| **False-fail hypothesis** | N/A. |

---

## Summary Verdict

Grounding and source routing are rigorous. The three-tier grounding with semantic parity guards prevents both wrong-span acceptance and false refutation. The candidate classifier's explicit three-status provenance (`present` / `not_found` / `ambiguous`) is asymmetric by design, never upgrading without proof. Shallow guards cover all known reformatting patterns. Lane independence is structurally enforced. **No blocking issues. D4/D5 compliance is comprehensive.**
