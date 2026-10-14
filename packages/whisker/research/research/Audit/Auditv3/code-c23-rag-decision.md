# C23 RAG Decision

**Role**: Bounded reassessment of whether the decision not to use RAG still holds, given every feature added since Auditv2.
**Audited state**: whisker 0.5.0, working tree, manifest b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771
**Gates**: D2 (Determinism & reproducibility)

## 1. Scope

Verify that whisker's same-document premise, source and its own candidate
conversion, nothing else, still holds after the source-aware routing,
golden-ideal integration, per-page screening, and ideal verification added
since Auditv1/v2, and that no cross-document retrieval infrastructure has
been introduced anywhere in the codebase.

## 2. Commands and Exits

```
E1: uv run --package whisker pytest packages/whisker/tests -q --tb=line -> 3 failed, 1784 passed (exit 1)
```

No RAG-specific command exists to run; this remains, as in Auditv1/v2, an
architectural assessment rather than a live-testable claim. Per the
batch's hard rule, E1's passing-test count is not cited as evidence for
this file's architectural claim; the claim rests on the import and
call-signature evidence in Section 3.

## 3. Current Evidence

### 3.1 The same-document premise, re-verified against the current tree

Every scoring and adjudication entry point still takes exactly one
paper's source and one paper's candidate:

- `score_paper` (`score.py:334`) takes `(pid, backend)` and reads
  `backend.get_paper_md(pid)` for that one pid; no second pid parameter
  exists anywhere in its signature.
- `score_markdown` (`score.py:244`) takes `(pid, md_text, content=...,
  reference_md=..., ideal_md=...)`, all scoped to the same paper: 
  `reference_md` is a second CONVERTER's output on the SAME source
  (`reference.py`, independent markitdown run, not a different document),
  and `ideal_md` is the SAME paper's human-blessed golden
  (`golden_ideals.ideal_path(pid, ...)`, `golden_ideals.py:94-106`).
- `score_against_ideal` (`golden_ideals.py:114-147`) takes
  `(md_text, ideal_md)`, both for one paper.
- `judge_pdf_extraction` (`pdf_judge.py`, per C19/C24) takes one PDF's
  text layer and one candidate markdown.
- `verify_against_ideal` (`ideal_verify.py:134-160`) takes
  `(candidate_md, ideal_md)`, both scoped to the paper under test.

### 3.2 No retrieval infrastructure exists anywhere in the tree

A targeted sweep of `packages/whisker/src` for
`embedding|vector_store|faiss|chromadb|pinecone|retrieval|
similarity_search` returns zero hits for any vector-store or
retrieval-engine reference. The only two `embedding` string matches
(`readback.py:17,125,154`) refer to NOT embedding an expected answer
LEXEME inside a generated question, an unrelated sense of the word from
document retrieval. No cross-paper query, no "find similar papers"
function, no corpus-wide index of any kind exists in `packages/whisker`.

### 3.3 What has changed since Auditv1/v2, and why none of it is retrieval

Four features have materially grown since the prior audits, all
same-document by construction:

- **Source-aware routing** (`source_router.py`, per C19/C20): compares a
  PDF/HTML source's own units (pages, sections) against that SAME
  document's candidate markdown. No other paper's data enters this
  comparison.
- **Golden-ideal integration** (`golden_ideals.py`): each ideal is looked
  up by the SAME pid (`ideal_path(pid, ideals_dir)`, case-insensitive
  stem match); there is no fallback to a different paper's ideal, and no
  nearest-neighbor or similarity-based ideal selection exists.
- **Per-page/unit screening** (`pdf_judge.py`'s `--all-pages` coverage
  bookkeeping, per C19 §3.5): pages are units of the SAME PDF, not
  documents drawn from a corpus.
- **Ideal verification** (`ideal_verify.py`): compares candidate vs ideal
  for the SAME paper (`verify_against_ideal`, 3.1).

None of these four introduces a query against a corpus, an embedding
index, or any notion of "most similar prior paper." Each is a second view
of the SAME paper's own source or its own hand-corrected ideal.

### 3.4 The one external-lookup path that exists is not retrieval

`find_ideals_dir` (`golden_ideals.py:73-91`) walks the directory tree to
LOCATE a fixed, deterministic path
(`packages/tomd/tests/fixtures/golden/ideals/`); this is a filesystem path
resolution, not a query over document content, and it returns at most one
file per pid via exact (case-insensitive) stem match, never a ranked or
approximate result.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | The same-document premise holds unchanged across every scoring, ideal, and PDF-lane entry point inspected this run | Informational | HIGH |
| F2 | Zero retrieval, embedding-index, or vector-store infrastructure exists anywhere in `packages/whisker/src`; the only "embedding" string matches are an unrelated sense (not leaking answer lexemes into a question) | Informational | HIGH |
| F3 | All four features added since Auditv1/v2 (source-aware routing, golden ideals, per-page screening, ideal verification) are same-document by construction; none introduces a cross-paper or corpus-wide query | Informational | HIGH |
| F4 | The one directory-tree lookup in the codebase (`find_ideals_dir`) is a fixed, deterministic path resolution, not a similarity- or relevance-ranked retrieval | Informational | HIGH |

## 5. False-Pass Hypothesis

**Could a same-document architecture quietly acquire retrieval-like
behavior without anyone calling it "RAG"?** The closest candidate is
`find_ideals_dir`'s directory walk, which does search a filesystem tree,
but it resolves to at most one exact-match file per pid and returns
`None` on no match (`golden_ideals.py:91`); it has no ranking, no
approximate matching, no fallback to a different pid's ideal. This audit
did not find any code path where a paper's scoring could be influenced by
another paper's source, candidate, or ideal content. The claim "no RAG"
would be false if any such cross-paper influence existed; none was found
in this sweep.

**Could this reassessment be too narrow to catch a subtle RAG-adjacent
addition?** The sweep in 3.2 is keyword-based (a grep for common retrieval
library and concept names) plus a manual read of every new feature's
function signature (3.1, 3.3). A RAG-adjacent addition using neither
common library names nor an obvious cross-paper signature could evade
both checks; this file does not claim exhaustive coverage of that
possibility, only that no such addition was found by the methods applied.

## 6. Gate/Dimension Mapping (PROPOSED)

| Gate | Dimension | Proposed status |
|------|-----------|------------------|
| D2 Determinism & reproducibility | Absence of retrieval-induced non-determinism (no external corpus query, no embedding-index staleness, no ranking variance) | PROPOSED PASS |

No gate in the G1-G7 cross-cutting set maps directly to this claim; it
remains, as in Auditv1/v2, an architectural assessment feeding D2 rather
than a gate with its own pass/fail contract.

## 7. Limitations

- This is a bounded reassessment (keyword sweep plus manual signature
  read of the four features added since Auditv1/v2), not an exhaustive
  audit of every function added to the codebase since the prior run.
- A RAG-adjacent addition using unconventional naming could evade the
  keyword sweep in 3.2; this file does not claim to have ruled that out
  by any method stronger than the sweep performed.
- Future features (cross-paper deduplication, corpus-wide anomaly
  detection, a "papers similar to this one" feature) could change this
  premise; none exist in the current codebase or, per this file's own
  scope, in any roadmap document read this run.

## 8. Conclusion

The same-document premise Auditv1 and Auditv2 both verified remains
unchanged after this run's re-check against the current tree. Every
feature added since those audits, source-aware routing, golden-ideal
integration, per-page screening, and ideal verification, is same-document
by construction: each compares a paper against its own source, its own
candidate, or its own hand-corrected ideal, never against another paper.
No retrieval, embedding-index, or vector-store infrastructure exists
anywhere in the current `packages/whisker/src` tree. The decision not to
use RAG continues to hold for the same reason it held at the prior
audits: there is no information need in this system's task that requires
retrieving content from documents other than the one being scored.

## 9. Delta vs Auditv2

Auditv2's C23 reached the identical conclusion ("RAG remains unnecessary,"
flat "Gate verdict: PASS (confirmed, closed)") against a smaller feature
set and a GREEN suite (1406 passed, 0 failed). This run re-verifies the
same premise against a materially larger feature set, the four items in
3.3, none of which existed in their current form at Auditv2's audit, and
confirms none of them introduces retrieval. The verdict is unchanged; the
evidence base supporting it is larger. This file also does not lean on
the suite's passing-test count as evidence, unlike Auditv2's citation of
"1406 passed" as its Commands-and-Exits entry; this run's E1 is RED
(3 failed) for reasons unrelated to this claim (C02 §3.6), and this file's
conclusion rests entirely on the import/signature evidence in Section 3,
not on test-suite health.
