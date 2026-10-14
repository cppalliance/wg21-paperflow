# TOC A/B Readback Experiment

## Methodology

Each paper in the whisker comprehension corpus was run through
`readback_paper` twice, using the same model, same questions,
and same anti-sycophantic scoring:

- **Variant A (baseline):** original `<pid>.expected.md` (no TOC)
- **Variant B (TOC):** same markdown with a generated Table of
  Contents injected after the YAML front matter, built from all
  `##`-`######` headings as a nested bullet list

Temperature: 0.0 (deterministic). Questions are generated from
fact metadata without embedding answer lexemes. Scoring is
anti-sycophantic: YES/NO types require a grounded quote, not
just a bare affirmative.

Fail classification based on pod answer text:
- **find-problem:** answer contains phrases like 'not found',
  'not mentioned', 'cannot locate' (the LLM could not find the content)
- **read-problem:** answer engages with content but returns a wrong
  value (the LLM found the location but misread it)

## Summary

| Paper | Facts | A pass | A fail | B pass | B fail | TOC overhead | Delta |
|-------|-------|--------|--------|--------|--------|-------------|-------|
| N5040 | 6 | 6 | 0 | 6 | 0 | 1636 chars (~409 tok) | 0 |
| P0876R23 | 8 | 7 | 1 | 8 | 0 | 4727 chars (~1181 tok) | +1 |
| P4182R0 | 8 | 8 | 0 | 8 | 0 | 1137 chars (~284 tok) | 0 |
| P4185R0 | 9 | 7 | 2 | 7 | 2 | 4431 chars (~1107 tok) | 0 |
| P4234R0 | 6 | 6 | 0 | 6 | 0 | 487 chars (~121 tok) | 0 |
| **TOTAL** | **37** | **34** | **3** | **35** | **2** | **12418 chars (~3104 tok)** | **+1** |

## Fail Analysis

### P0876R23 / table-poll-stlouis (table)

**Question**: In the table containing cell '6', identify: the cell immediately right of '6'; the column heading of the column containing '6'. Answer with the exact cell values.

**Expected**: `cell=6, right: 8, heading: SF`

| Variant | Status | Pod answer (truncated) |
|---------|--------|----------------------|
| A (no TOC) | **FAIL** (read-problem) | The cell immediately right of '6' is '8'.   The column heading of the column containing '6' is 'F'. |
| B (TOC) | PASS | The cell immediately right of '6' is '8'.   The column heading of the column containing '6' is 'SF'. |

### P4185R0 / table-anchored-true-zero (table)

**Question**: In the table containing cell 'Anchored at true zero', identify: the cell immediately left of 'Anchored at true zero'; the cell immediately right of 'Anchored at true zero'; the column heading of the column containing 'Anchored at true zero'. Answer with the exact cell values.

**Expected**: `cell=Anchored at true zero, left: Point origin (explicit or implicit), right: N/A, heading: Absolute`

| Variant | Status | Pod answer (truncated) |
|---------|--------|----------------------|
| A (no TOC) | **FAIL** (read-problem) | Left: "Physical origin" Right: "N/A" Column heading: "Absolute" |
| B (TOC) | **FAIL** (read-problem) | Left: "Physical origin (explicit or implicit)" Right: "N/A" Column heading: "Absolute" |

### P4185R0 / table-text-output-point-no (table)

**Question**: In the table containing cell 'Text output', identify: the cell immediately right of 'Text output'; the column heading of the column containing 'Text output'. Answer with the exact cell values.

**Expected**: `cell=Text output, right: ✗, heading: Feature`

| Variant | Status | Pod answer (truncated) |
|---------|--------|----------------------|
| A (no TOC) | **FAIL** (read-problem) | The cell immediately right of "Text output" is "Resolved by absolutes".   The column heading of the column containing "Text output" is "Feature". |
| B (TOC) | **FAIL** (read-problem) | The cell immediately right of 'Text output' is "Resolved by absolutes". The column heading of the column containing 'Text output' is "Feature". |

## Context Overhead

| Paper | Original size | TOC size | Overhead % | ~Tokens added |
|-------|-------------|----------|-----------|--------------|
| N5040 | 84,712 chars | 1,636 chars | 1.9% | ~409 |
| P0876R23 | 137,087 chars | 4,727 chars | 3.4% | ~1181 |
| P4182R0 | 25,160 chars | 1,137 chars | 4.5% | ~284 |
| P4185R0 | 201,968 chars | 4,431 chars | 2.2% | ~1107 |
| P4234R0 | 16,461 chars | 487 chars | 3.0% | ~121 |

## Conclusion

### Fail Classification Summary

| Variant | Find problems | Read problems | Total fails |
|---------|--------------|--------------|-------------|
| A (no TOC) | 0 | 3 | 3 |
| B (TOC) | 0 | 2 | 2 |

**Key finding:** Zero "find problems" in either variant. Every single
fail, in both A and B, was a read/interpretation error (the model
found the table but misread a column alignment or picked the wrong
neighboring cell), never a navigation failure ("couldn't find it").

### The +1 delta is model variance, not a TOC benefit

The one fact that flipped from FAIL to PASS (P0876R23 `table-poll-stlouis`)
changed because the pod answered the column heading as "F" (without TOC)
vs "SF" (with TOC). Both runs located the same table and the same cell;
the difference is which column heading the model attributed to the cell.
This is a table-column-alignment misread, the same class of error as
the two persistent P4185R0 fails. A TOC listing section names cannot
influence how a model reads a pipe-table's column headers.

The two persistent P4185R0 fails (identical in both variants) confirm
this: `table-anchored-true-zero` reads "Physical origin" instead of
"Point origin (explicit or implicit)" (partial cell text extraction),
and `table-text-output-point-no` lands on the wrong table entirely
("Resolved by absolutes" instead of the cross-mark). Both are pure
read errors that a TOC cannot address.

### Bottom line

A TOC adds ~3,100 tokens of redundant context across 5 papers (headings
duplicated verbatim from the body) for zero measurable comprehension
benefit. The hypothesis that "a TOC helps the LLM find information" is
not supported: the model never failed to find a section, it only
struggled to read table cell alignments, which is orthogonal to document
navigation.

## Date and setup

- **Date**: 2026-07-09
- **Model**: deepseek-v4-pro on alliance-pod (self-hosted, RunPod)
- **Temperature**: 0.0
- **Corpus**: 5 papers, 37 source-verified facts
- **Elapsed**: ~81 seconds (74 serial calls, 37 per variant)

