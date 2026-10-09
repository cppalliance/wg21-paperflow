# C19 Chunking and Context

**Role:** Audit oversize paper handling in the advisory LLM lane.
**Auditor scope:** `tapetum_llm/chunking.py`
**Maps to:** D3 (advisory non-leakage), D1 (determinism)

## 1. Audited State

- whisker 0.5.0, HEAD 51cb704 + local mods
- `tapetum_llm/chunking.py`: 333 lines
- All 1406 tests passing (E1)

## 2. Commands and Exits

```
E1:  uv run --package whisker pytest packages/whisker/tests  -> 1406 passed (exit 0)
```

## 3. Current Evidence

### 3.1 `chunk_markdown` (chunking.py L129-164)

**Small-paper fast path** (L142-143): If `len(md) <= max_chars`, returns `([md], False)`. No chunking, no overhead, the common path.

**H2 boundary splitting** (L147, `_split_sections`): The paper body is split at `## ` headings, which is the tomd body contract (WG21 paper bodies start at H2).

**`_split_sections`** (L167-194):
- Fence-aware: `## ` inside fenced code blocks is not treated as a heading (L178-186).
- The preamble (front matter, H1 title, anything before the first H2) forms the first section.
- Sections are exact: the concatenation reproduces `md` exactly (lossless, using `splitlines(keepends=True)`).

**Greedy packing** (L155-163): Sections are packed into chunks greedily (marker's section packing pattern). A chunk accumulates sections until adding the next would exceed `max_chars`.

**Hard split fallback** (L148-150): A single section larger than `max_chars` is hard-split on line boundaries (`_hard_split`, L197-220). This sets `partial = True`, meaning the section was broken mid-content.

**`_hard_split`** (L197-220):
- Splits on line boundaries first.
- A single line longer than the budget is char-sliced as a final fallback (L210-211).
- Every returned piece is guaranteed `<= max_chars`.
- Lossless: concatenation reproduces the original.

### 3.2 Serial Triage

The chunking module is pure (no LLM, no I/O). The calling code in `adjudicate.py` triages chunks serially (one in-flight request at a time, per D11). This is documented in chunking.py's module docstring (L18: "process each unit") and CLAUDE.md ("split on H2 boundaries, triaged serially").

### 3.3 Worst-Axis Aggregation

**`aggregate_adjudications`** (chunking.py L226-292):

1. **Per-axis worst finding** (L250-256): For each axis name, keeps the most severe finding across all chunks. Severity ranking: major-fail (3) > non-major-fail (2) > review (1) > pass (0).

2. **Verdict: severity-aware worst** (L258): `worst_axis_verdict(axis_findings)` applies the same severity fold as the single-chunk decide step: a `fail` only becomes overall `fail` if severity is `major`; non-major folds to `review`.

3. **Confidence: minimum across chunks** (L259): Most conservative estimate.

4. **Evidence: union with dedup** (L268-275): Evidence spans are deduped on `(axis, quote, reason)` tuple, order-preserving.

5. **Reasoning/primary_concern** (L277-282): Taken from the worst chunk, annotated with `(paper chunked into N parts for size)`.

6. **Empty parts** (L239-248): Zero chunks produce a `review` verdict with zero confidence and a clear error message. This is the no-partial-success path.

### 3.4 Partial-Read Tracking

When a section is hard-split (L148-150), `partial = True` is set. The calling code uses this to mark the read as incomplete: a partial read can never become a clean `pass` (CLAUDE.md: "A section too large to read in full marks the read partial and can never become a clean pass").

### 3.5 Binary-Payload Stripping

`strip_binary_payloads` (chunking.py L54-103) is a pre-LLM filter:

1. **Data URI images** (L46-47, `_DATA_URI_IMAGE_RE`): `![alt](data:mime;base64,payload)` -> `<!-- tapetum:data-uri-stripped MIME ~SIZEkB -->`. Alt text preserved (prose, judgeable).

2. **Bare base64 lines** (L86-99): Lines >= `BASE64_LINE_MIN_CHARS` with >= `BASE64_LINE_ALPHABET_FLOOR` base64 alphabet fraction -> `<!-- tapetum:base64-line-stripped -->`. Whitespace counts AGAINST the ratio (prose has ~15-20% spaces, base64 has none).

Pure function, returns `(filtered_md, stripped_count)`. The on-disk paper.md is never touched.

### 3.6 `worst_axis_verdict` (chunking.py L106-123)

The severity-aware worst-axis fold:
- `fail` + `major` severity -> overall `VERDICT_FAIL` (immediate return).
- `fail` + non-major -> `VERDICT_REVIEW` (cosmetic, e.g. heading-level jump).
- `review` -> `VERDICT_REVIEW`.
- Otherwise -> `VERDICT_PASS`.

This is the RESCUE mechanism for the false-fail population.

## 4. Findings

### F1: H2 boundary splitting is correct and fence-aware (INFO)

**Severity:** INFO | **Confidence:** HIGH

`_split_sections` correctly identifies `## ` at the start of a line, skips `## ` inside fenced code blocks, and preserves the exact content (lossless concatenation). The preamble handling is correct.

### F2: Worst-axis aggregation preserves the severity fold (INFO)

**Severity:** INFO | **Confidence:** HIGH

`aggregate_adjudications` applies the same severity-aware verdict logic as the single-chunk path. A non-major `fail` in one chunk does not escalate to overall `fail`; it stays `review`. This is consistent with the design.

### F3: Partial-read tracking prevents false-pass on oversize sections (INFO)

**Severity:** INFO | **Confidence:** HIGH

The `partial` flag is set when hard-split is used. The calling code caps the verdict at `review` for partial reads. This is the correct behavior: a section that could not be read in full cannot be declared clean.

### F4: Binary-payload stripping is deterministic and conservative (INFO)

**Severity:** INFO | **Confidence:** HIGH

Both filters (data URI, bare base64 lines) are regex-based, deterministic, and leave markers for auditability. The whitespace-ratio heuristic for bare base64 lines is sound (prose has spaces, base64 does not).

### F5: No test for chunk losslessness assertion (LOW)

**Severity:** LOW | **Confidence:** MEDIUM

The `chunk_markdown` contract claims concatenation reproduces `md` exactly, and the code implements this correctly (splitlines with keepends, greedy packing). However, this invariant is not directly asserted in a dedicated test. The existing tests may cover it indirectly, but an explicit `assert "".join(chunks) == md` test would strengthen confidence.

## 5. False-Pass Hypothesis

**Q:** Could chunking cause a corrupted paper to pass?

1. **Lost content:** The lossless concatenation invariant prevents content loss. Every character of the input appears in exactly one chunk.

2. **Chunk boundary cuts a defect:** A defect spanning an H2 boundary could be split across two chunks. Each chunk sees only half. **Mitigation:** Worst-axis aggregation takes the maximum severity across chunks, so a defect visible in either chunk is reported.

3. **Partial read hides defect:** A section too large for the context window is hard-split and marked partial. The partial flag caps the verdict at `review`, so the defect cannot be silently passed.

4. **Empty chunks bypass:** Zero chunks produce `review` with zero confidence. No silent pass.

## 6. Gate/Dimension Mapping

| Gate | Dimension | Status |
|------|-----------|--------|
| D3 Advisory non-leakage | Chunking is advisory-lane only; never gates deterministic verdicts | PASS |
| D1 Determinism | All functions are pure, no randomness, no LLM | PASS |

## 7. Limitations

- This report audits the chunking module only. The calling code in `adjudicate.py` that enforces serial triage and partial-read capping is audited structurally (by documentation reference), not by code trace.
- The `MAX_PAPER_MD_CHARS` threshold is defined in `tapetum_llm/constants.py` and is not verified against real paper sizes in this report.
- Real-LLM runtime is BLOCKED (E9); chunking behavior on actual oversize papers is not verified live.

## 8. Conclusion

The oversize paper handling is well-designed. H2 boundary splitting follows the tomd body contract. Greedy packing with a hard-split fallback ensures every paper is processable regardless of size. Worst-axis aggregation preserves the severity-aware verdict logic. Partial-read tracking prevents false-pass on sections too large to read in full. Binary-payload stripping is deterministic and conservative. All functions are pure.

**Gate verdict: PASS**
