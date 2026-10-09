# C23 RAG Decision

**Role:** Bounded reassessment of whether RAG was needed.
**Auditor scope:** Architecture review of whisker's same-document premise
**Maps to:** D1 (determinism)

## 1. Audited State

- whisker 0.5.0, HEAD 51cb704 + local mods
- Same-document architecture unchanged since initial design

## 2. Commands and Exits

```
E1:  uv run --package whisker pytest packages/whisker/tests  -> 1406 passed (exit 0)
```

No RAG-specific commands; this is an architectural assessment.

## 3. Current Evidence

### 3.1 The Same-Document Premise

whisker operates on a SAME-DOCUMENT basis: every scoring function takes a source (PDF/HTML) and its conversion (Markdown) as input. The comparison is always source-vs-candidate for the same paper.

Evidence from the codebase:

1. **`score_paper`** (score.py L334-371): Takes `(pid, backend)`, reads `backend.get_paper_md(pid)` and `check_paper_content(pid, backend)`. One paper, one source, one candidate.

2. **`score_markdown`** (score.py L244-331): Takes `(pid, md_text, content=..., reference_md=..., ideal_md=...)`. All inputs are for the same paper.

3. **`check_facts`** (facts.py L491-507): Takes `(md, facts, pid)`. Facts are paper-specific assertions from `<pid>.facts.jsonl`.

4. **`run_bench`** (referenced in __main__.py L469): Takes `pairs` of `(pid, candidate, reference)` for the same paper.

5. **Advisory LLM lane** (`tapetum_llm/`): `adjudicate_paper` and `judge_pdf_extraction` both take a single paper's source and candidate.

### 3.2 No Cross-Document Retrieval Anywhere

A grep for retrieval-related patterns confirms no RAG infrastructure exists:

- No vector stores, embeddings, or similarity search.
- No cross-paper queries.
- No document retrieval from external corpora.
- No "find similar papers" functionality.

The only external data access is:
- `reference_markdown` (reference.py): runs an independent converter (markitdown) on the SAME source. This is not retrieval; it is a second conversion of the same document.
- `find_ideals_dir` / `ideal_path` (golden_ideals.py): reads a human-blessed ideal for the SAME paper from the tomd fixture tree.

### 3.3 Has Anything Changed the Premise?

Since v1 audit, the following features were added:
- Golden ideals integration (still same-document: ideal is per-paper)
- Source-aware routing (PDF/HTML, still same-document)
- Per-page screening (still same-document: pages from the same PDF)
- Ideal verification (still same-document: compares candidate vs ideal for same paper)

**None of these introduce cross-document retrieval.**

## 4. Findings

### F1: RAG was not needed and remains not needed (INFO)

**Severity:** INFO | **Confidence:** HIGH

whisker's task is QA of a document conversion pipeline. The input is always (source, candidate) for the same paper. There is no information need that requires retrieving content from other documents. The same-document premise is architecturally sound and unchanged.

## 5. False-Pass Hypothesis

Not applicable. This is an architectural assessment, not a gate.

## 6. Gate/Dimension Mapping

| Gate | Dimension | Status |
|------|-----------|--------|
| D1 Determinism | No external retrieval means no retrieval-induced non-determinism | PASS |

## 7. Limitations

- This is a bounded reassessment, not a full architecture review.
- Future features (e.g., cross-paper deduplication, corpus-wide anomaly detection) could change the premise, but none are in the current codebase or roadmap.

## 8. Conclusion

The same-document premise is unchanged. whisker operates exclusively on (source, candidate) pairs for individual papers. No cross-document retrieval exists or is needed. RAG remains unnecessary.

**Gate verdict: PASS (confirmed, closed)**
