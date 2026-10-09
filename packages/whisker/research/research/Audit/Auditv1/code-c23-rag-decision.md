# C23 - RAG Decision Auditor

**Mandate:** Determine if RAG should have been used in whisker.
**Focus dimensions:** Phase 4 RAG protocol.

---

## 1. Whisker Architecture: Single-Paper QA

| Severity | **PASS** (RAG correctly not used) |
|----------|-----------------------------------|
| Claim | Whisker is a single-paper QA tool that compares CONVERTED markdown against SOURCE. This is a same-document task that does not require cross-paper knowledge. |
| Evidence | `CLAUDE.md` ("What this is"): "Deterministic QA for tomd conversions." Every entry point (`score_paper`, `adjudicate_paper`, `readback_paper`) takes a single PID. No function in the codebase reads multiple papers simultaneously. The three lanes (stability, fidelity, comprehension) all operate per-paper. |
| Affected gate | Phase 4 RAG protocol question 1 |
| Confidence | 0.99 |
| False-pass hypothesis | A future cross-paper consistency check (e.g., "does P1234R5 cite P1234R4 correctly?") might benefit from RAG. Not currently in scope. |
| False-fail hypothesis | None. |

---

## 2. RAG Protocol Evaluation

### Protocol Question 1: Does the desired question require cross-paper knowledge?

| Answer | **NO** |
|--------|--------|
| Evidence | Whisker answers: (1) "Is this conversion safe to ship?" (per-paper verdict), (2) "How close is the output to a reference?" (per-paper bench), (3) "Can an LLM still recover the paper's facts?" (per-paper comprehension). None of these require knowledge from OTHER papers. The reference oracle (markitdown) generates a second conversion of the SAME paper. The facts corpus contains per-paper assertions authored against that specific paper's source. |
| Confidence | 0.98 |

### Protocol Question 2: Do deterministic source routing + scoped reads miss labeled defects?

| Answer | **NO** (within current scope) |
|--------|-------------------------------|
| Evidence | `source_router.py:149-233` (`route_pdf_units`): compares source page text against the full candidate markdown using `content_recall` per page, token-delta counting for C++ keywords, and heading/caption drift detection. `source_router.py:236-316` (`route_html_units`): matches HTML section units against markdown sections by title, checks recall per section, and counts code blocks. These are deterministic, scoped reads that directly compare source units against the candidate. The router never needs external knowledge to identify discrepancies. |
| Confidence | 0.95 |
| Limitation | The router could miss defects where a tomd conversion accidentally substitutes content from a DIFFERENT paper (a hypothetical copy-paste bug). RAG would not help here either; this is a converter bug, not a QA knowledge gap. |

### Protocol Question 3: Would a locked holdout show unique true catches from RAG?

| Answer | **NO** (strong evidence) |
|--------|--------------------------|
| Evidence | The whisker architecture provides three independent detection mechanisms without RAG: (1) **Deterministic metrics** (`unigram_coverage`, `text_nid`, `content_recall`): mathematical coverage over the source text catches missing content. (2) **Structural gates** (`gates.py`): non-empty, heading monotone, no-TOC-leak catch structural defects. (3) **Source-verified facts** (`facts.py`): deterministic assertions that a downstream LLM can recover specific information. The LLM advisory lane (`adjudicate.py`) adds per-axis fidelity judgment by reading the paper markdown directly, not via retrieval from an index. |
| Confidence | 0.90 |

---

## 3. Source Routing Analysis (`source_router.py`)

### 3.1 PDF Lane Routing

| Severity | **PASS** |
|----------|----------|
| Claim | The PDF source router deterministically identifies pages with low recall, missing captions, heading drift, and token count imbalances without RAG. |
| Evidence | `source_router.py:149-233`: `route_pdf_units` iterates `PageUnit`s, computes `content_recall(candidate_md, unit.text)` per page, checks `caption_lines` against the candidate surface, and matches `heading_candidates` against parsed markdown headings. Token-delta counting (lines 166-189) flags C++ keywords with `TOKEN_DELTA_THRESHOLD` gap. |
| Affected gate | Phase 4 |
| Confidence | 0.97 |
| False-pass hypothesis | None: the router reads the source directly. |
| False-fail hypothesis | None. |

### 3.2 HTML Lane Routing

| Severity | **PASS** |
|----------|----------|
| Claim | The HTML source router deterministically identifies sections with heading-level drift, low recall, and missing code blocks without RAG. |
| Evidence | `source_router.py:236-316`: `route_html_units` parses markdown sections, matches them by title key against source section units, checks heading levels, computes `content_recall` per section, and counts code blocks. Occurrence tracking (lines 248-258, 276-287) handles duplicate section titles. |
| Affected gate | Phase 4 |
| Confidence | 0.97 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

---

## 4. LLM Lane: Full Paper Text Access (`adjudicate.py`)

| Severity | **PASS** |
|----------|----------|
| Claim | The LLM adjudication lane sends the FULL paper markdown (or H2-chunked sections for oversized papers) directly to the model. It does not use retrieval; the model reads the document in full. |
| Evidence | `adjudicate.py:228-249`: `_custom_triage` sends the paper markdown (or chunks) as the user message. `adjudicate.py:530-580`: `_build_triage_message` wraps the markdown with `ctx.inject_untrusted(md)`. `adjudicate.py:583-611`: `_build_adjudicate_message` sends the full markdown for tier-2 re-reads. For oversized papers (>500k chars): `adjudicate.py:234-248`: H2-boundary chunking with serial triage and aggregation. |
| Affected gate | Phase 4 |
| Confidence | 0.99 |
| False-pass hypothesis | None: the LLM reads the document text, not a retrieval index. |
| False-fail hypothesis | None. |

---

## 5. Evidence For RAG

| Factor | Evidence | Weight |
|--------|----------|--------|
| Cross-paper citation checking | Not in scope. whisker checks conversion quality, not paper content quality. | 0 |
| Historical regression detection | Handled by Lane 1 (`golden.py`): exact diff against committed snapshots. No retrieval needed. | 0 |
| Pattern learning from past conversions | Not applicable: whisker uses deterministic metrics, not learned patterns. | 0 |
| Large-scale corpus analytics | `whisker --all` iterates papers but scores each independently. No cross-paper aggregation benefits from RAG. | 0 |

---

## 6. Evidence Against RAG

| Factor | Evidence | Weight |
|--------|----------|--------|
| Same-document task | Every whisker operation compares a paper's converted markdown against its own source. RAG adds latency and complexity for zero information gain. | HIGH |
| Determinism requirement (D1) | RAG introduces embedding drift, index staleness, and retrieval non-determinism. The project's determinism invariant would be violated. | HIGH |
| No LLM in the gate | The deterministic gate (whisker core) has no LLM. Adding RAG would introduce LLM dependency in a path that is currently LLM-free. | HIGH |
| Full document fits in context | The advisory LLM lane already reads the full paper markdown in one call (up to 500k chars). No retrieval is needed because the document IS the context. | HIGH |
| Source routing is deterministic | `source_router.py` identifies risk units by direct text comparison, not by semantic search. | MEDIUM |

---

## 7. Conclusion

| Severity | **PASS** (RAG correctly not used) |
|----------|-----------------------------------|
| Claim | RAG would not improve whisker's defect detection. The tool operates on a single paper at a time, has direct access to both the source and the converted markdown, and uses deterministic metrics plus scoped LLM reads (full document in context). RAG would add complexity, latency, and non-determinism for zero information gain. |
| Evidence | All three RAG protocol questions answered NO. The architecture is fundamentally same-document comparison, not information retrieval. |
| Affected gate | Phase 4 RAG protocol |
| Confidence | 0.97 |
| False-pass hypothesis | A future whisker feature requiring cross-paper knowledge (e.g., "has this conversion error pattern been seen in other papers?") would benefit from RAG. This is a product decision, not a current gap. |
| False-fail hypothesis | RAG could theoretically improve the LLM's comprehension of WG21 conventions by providing relevant context from other papers. However, the advisory lane already achieves good results with zero-shot reading of the document text, and the deterministic gate does not use LLM at all. |

---

## Summary

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | Whisker is a same-document QA tool | CRITICAL | CONFIRMED |
| 2 | No cross-paper knowledge required | HIGH | CONFIRMED |
| 3 | Deterministic source routing covers scoped reads | HIGH | CONFIRMED |
| 4 | LLM lane reads full document in context | HIGH | CONFIRMED |
| 5 | RAG would violate determinism invariant (D1) | HIGH | CONFIRMED |
| 6 | All three RAG protocol questions answered NO | CRITICAL | CONFIRMED |

**Auditor verdict: RAG is correctly absent from whisker.** The tool's architecture is fundamentally same-document comparison. Every detection mechanism operates on direct text access to the source and candidate, not on retrieval from an index. Adding RAG would violate the determinism invariant and add complexity for zero defect-detection gain.
