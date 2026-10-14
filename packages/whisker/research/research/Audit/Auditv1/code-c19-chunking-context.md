# C19 — Chunking and Context Audit

**Auditor**: Chunking and Context Auditor
**Focus**: D3 (context handling, oversize papers)
**Scope**: `packages/whisker/src/whisker/tapetum_llm/chunking.py`, `adjudicate.py`
**Date**: 2026-07-19

---

## Executive Summary

The chunking subsystem handles oversize papers (> 500K chars) by splitting on H2 boundaries with fence awareness, processing serially, and aggregating with worst-axis/min-confidence/union-evidence semantics. Binary payloads are stripped pre-LLM. A section too large for the budget is hard-split on line boundaries and marked as `partial` (forced to `review`). All functions are pure (no I/O, no LLM), deterministic, and losslessly invertible. Test coverage includes roundtrip, fence awareness, YAML front matter, and the P2728 corpus shape.

---

## Findings

### F1. H2 boundary splitting is fence-aware and lossless

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | `_split_sections` splits on `## ` headings while tracking fenced code blocks. A `## ` inside a ``` or ~~~ fence is not treated as a heading. The preamble (front matter, H1, anything before the first H2) is the first section. Concatenation of the returned sections reproduces the original markdown exactly. |
| **Evidence** | `chunking.py:167-194` (`_split_sections`: tracks `in_fence` with ``` and ~~~ markers, fence-closer must match fence-opener). `chunking.py:187` (`if (not in_fence) and line.startswith("## ") and current:`). Tests: `test_tapetum_llm.py:1195-1200` (`test_fence_aware_split`: fenced `## ` is not split). `test_tapetum_llm.py:1407-1420` (`test_tilde_fence_not_split`). `test_tapetum_llm.py:1171-1177` (`test_h2_split_lossless_and_bounded`: `"".join(chunks) == md`). |
| **Affected gate** | D3 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | A 4-backtick fence (````...````) is handled because `len(marker) >= len(fence_marker)` closes it, but an asymmetric fence (``` open, ```` close) would not close. This is an edge case in CommonMark, not observed in the WG21 corpus. |
| **False-fail hypothesis** | N/A. |

### F2. Binary content stripping before LLM prompts

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | `strip_binary_payloads` removes two categories of binary content pre-LLM: (1) `![alt](data:mime;base64,payload)` images (alt text preserved, payload replaced by `<!-- tapetum:data-uri-stripped MIME ~SIZEkB -->`), (2) bare lines >= 1024 chars with >= 90% base64 alphabet (replaced by `<!-- tapetum:base64-line-stripped ~SIZEkB -->`). The on-disk paper.md is never touched. |
| **Evidence** | `chunking.py:54-103` (`strip_binary_payloads`). `chunking.py:45-47` (`_DATA_URI_IMAGE_RE` regex). `constants.py:111-112` (`BASE64_LINE_MIN_CHARS = 1024`, `BASE64_LINE_ALPHABET_FLOOR = 0.90`). Tests: `test_tapetum_llm.py:1558-1632` (data-URI stripped, multiple images, normal images untouched, bare base64 stripped, long prose kept, P2728 shape shrinks below chunk budget). |
| **Affected gate** | D3 (context budget) |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | A long line of prose with unusual character distribution (e.g., all-caps alphanumeric identifiers with no spaces) could be misclassified as binary. The whitespace-counts-against-ratio design mitigates this (prose has ~15-20% spaces). |
| **False-fail hypothesis** | N/A. |

### F3. Serial triage: one in-flight LLM request per paper (D11)

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | When a paper is split into chunks, triage runs serially: a `for` loop over chunks, each awaiting `run_agent` before proceeding. This guarantees one in-flight LLM request per paper, preserving D11 serial semantics within a paper. |
| **Evidence** | `adjudicate.py:243-248` (`for index, chunk in enumerate(chunks): ... parts.append(await run_agent(ctx, spec, user_msg))` — sequential `await`, no `asyncio.gather`). `adjudicate.py:675` (`default_concurrency=1` on `StepContext`). |
| **Affected gate** | D11 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None; the `for`-loop-with-`await` pattern is inherently serial. |
| **False-fail hypothesis** | N/A. |

### F4. Fold logic: worst axis (severity-aware), minimum confidence, union of evidence

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | `aggregate_adjudications` folds per-chunk results: (1) per-axis, the most severe finding across chunks wins (ranked by `_finding_rank`: major-fail=3, non-major-fail=2, review=1, pass=0); (2) verdict is severity-aware worst-axis (a `fail/minor` folds to `review`); (3) confidence is the minimum; (4) evidence spans are the union (dedup by `(axis, quote, reason)` tuple, order-preserving). |
| **Evidence** | `chunking.py:226-292` (`aggregate_adjudications`). `chunking.py:250-256` (per-axis worst: `if _finding_rank(af) > _finding_rank(current): best[af.axis] = af`). `chunking.py:258-259` (`verdict = worst_axis_verdict(axis_findings)`, `confidence = min(a.confidence for a in parts)`). `chunking.py:268-275` (dedup: `key = (sp.axis, sp.quote, sp.reason)`, `if key not in seen`). Tests: `test_tapetum_llm.py:1483-1553` (different worst axes, order invariance, severity tie determinism). |
| **Affected gate** | D1, D3 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None. |
| **False-fail hypothesis** | N/A. |

### F5. Severity-aware worst-axis: minor fail → review (P3941R4 rescue)

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | `worst_axis_verdict` implements severity-aware folding: a `fail` verdict is a hard overall `fail` only when severity is `major` (unrecoverable). A `fail/minor` (e.g., heading-level jump) folds to `review`. This is the mechanism that rescues the false-fail RESCUE population. |
| **Evidence** | `chunking.py:106-123` (`worst_axis_verdict`: `if af.verdict == VERDICT_FAIL: if af.severity == SEVERITY_MAJOR: return VERDICT_FAIL; worst = VERDICT_REVIEW`). `constants.py:52` (`SEVERITY_MAJOR = "major"`). Tests: `test_tapetum_llm.py:1082-1111` (major→fail, minor→review, review→review, all-pass, major-beats-minor, empty). `test_tapetum_llm.py:1114-1155` (`TestDecideSeverity`: P3941R4 scenario, major-fail→fail, minor-fail→review). |
| **Affected gate** | D3 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None. |
| **False-fail hypothesis** | N/A. |

### F6. Partial read forces review (never a clean pass)

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | When a single H2 section exceeds `MAX_PAPER_MD_CHARS` and is hard-split on line boundaries, the `partial` flag is set. In the decide step, a partial read forces `suggested_verdict = VERDICT_REVIEW` (never a clean pass). |
| **Evidence** | `chunking.py:148-149` (`if len(section) > max_chars: pieces.extend(_hard_split(section, max_chars)); partial = True`). `adjudicate.py:346-349` (`if state.partial and suggested_verdict == VERDICT_PASS: suggested_verdict = VERDICT_REVIEW`). `adjudicate.py:184-188` (docstring: "a partial read must never become a clean pass"). Tests: `test_tapetum_llm.py:1180-1187` (`test_oversize_section_hard_split_sets_partial`). |
| **Affected gate** | D3 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None; the guard is unconditional for partial reads. |
| **False-fail hypothesis** | N/A. |

### F7. Context guard: no silent truncation in PDF lane

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | The PDF judge lane computes estimated tokens and refuses to proceed if they exceed 80% of the model's context window. `PdfLaneError` is raised instead of silently truncating. |
| **Evidence** | `pdf_judge.py:106-109` (`CONTEXT_SAFETY_MARGIN = 0.80`). `pdf_judge.py:604-615` (context guard: `if est_tokens and est_tokens > budget: raise PdfLaneError(...)`, message says "refusing to truncate"). Tests: `test_pdf_judge.py:895-903` (`test_context_overflow_raises`). |
| **Affected gate** | D3 (fidelity: no silent truncation) |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None. |
| **False-fail hypothesis** | N/A. |

### F8. Chunk note informs LLM about partial view

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | When chunking is active, the triage message includes a chunk note telling the LLM: "this is chunk i of N of a large paper. Judge only the content shown. Do not flag missing front matter, missing sections, or a body that stops mid-sentence at the chunk boundary." |
| **Evidence** | `adjudicate.py:552-559` (`chunk_note` construction in `_build_triage_message`). `adjudicate.py:245-247` (chunk_index and chunk_count are passed to `_build_triage_message`). |
| **Affected gate** | D3 (context correctness) |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None. |
| **False-fail hypothesis** | N/A. |

---

## Summary Verdict

The chunking and context subsystem is well-engineered for oversize papers. H2 boundary splitting is fence-aware and lossless. Binary payloads are stripped pre-LLM. Serial triage is enforced by sequential await. The fold logic is deterministic with severity-aware worst-axis semantics. Partial reads are forced to review. Context overflow is caught with an explicit error. **No blocking issues. D3 compliance is thorough.**
