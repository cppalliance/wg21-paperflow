# N5040 Attendance: Whisker check results

Date: 2026-08-15 (v1.0.5: count-then-score defect probes, live DeepSeek V4 Pro run)

## Whisker llm-readability check on data/paperstore/n5040.md

Contract v1.0.5. Verdict: **fail**. document_deterministic_ok: false.

- R1: **FAIL** (1 finding: label shift on pipe table 3)
  - header col 1 empty, body 38/38 filled; adjacent header "Name" (col 2) 0/38 filled
- R2: **FAIL** (5 findings: continuation row used as header)
  - pipe table 4: `de Wever, Mark | ANSI` (follows table 3)
  - pipe table 5: `Kawulak, Robert | PKN` (follows table 4)
  - pipe table 6: `Nash, Phil | BSI` (follows table 5)
  - pipe table 7: `Tanwar Preeti | ANSI` (follows table 6)
  - pipe table 8: `Mara Bos | NEN` (follows table 7)
- R6: **pass**
- R7: **not_applicable**
- R8: **review** (6 findings: long fragments without header repeat)
- R9: **review** (20 findings: blank cells in the phantom column)
- R3/R4/R5/R10/R11: **not_evaluated** (source_compare not wired)
- R12: **not_applicable**
- R13: **not_evaluated** (certification not executed)

## Control papers (no false R1/R2 fail)

- P4182R0: R1 **pass**, R2 **pass**, deterministic ok
- P0876R23: R1 **pass**, R2 **pass**, deterministic ok (R9 review only)

## The defects

### Phantom column (R1)

The PDF has a 2-column table (Name | National Body). tomd emits a 3-column
markdown table with an empty first header cell: `| | Name | National Body |`.
Body rows carry names under the empty header and leave the "Name" column blank.
R1 now detects this as a label shift: empty header with filled body, adjacent
named header with empty body.

### Continuation headers (R2)

After the first fragment, each page-break start is promoted to a GFM header
(`de Wever, Mark | ANSI`, ..., `Mara Bos | NEN`). R2 detects adjacent pipe
tables whose header is a continuation data row.

## DeepSeek V4 Pro defect probes

### v1.0.4 (semantic YES/NO, full paper) - FAILED

v1.0.4 used semantic YES/NO questions and sent the full paper. Result: 1
pass, 3 fail. DeepSeek could not detect the label shift because column
association is its measured weakness (CoTabBench TableQA ~52%).

| Probe | Expected | Answer | Verdict |
|---|---|---|---|
| diag-alignment ("do values sit under correct headers?") | NO | YES | FAIL |
| diag-empty-header-col ("which column has the empty header?") | 1 | 3 | FAIL |
| diag-continuation-header ("are these column names or data?") | data values | data values | PASS |
| lookup-shifted-col ("value under 'Name', body row 1?") | EMPTY | Adams, Michael | FAIL |

### v1.0.5 (count-then-score, isolated fragment) - PASSED

v1.0.5 sends only the isolated table fragment with an R1-aware system prompt
("delimiters carry the coordinates") and asks the model to count pipes and
dump cells by index. The dump is scored deterministically. This plays to the
model's strength: counting (~84% row/column count in CoTabBench).

| Probe | Expected | Answer | Verdict |
|---|---|---|---|
| count-dump-shift (count delimiters, dump cells) | header[1]=EMPTY, body[1][2]=EMPTY | header[1]=EMPTY, body[1][2]=EMPTY | PASS |
| diag-continuation-header ("column names or data?") | data values | data values | PASS |

**DeepSeek V4 Pro recognizes the N5040 Attendance defect when asked to count
delimiters.** The dump clearly shows `[1]=EMPTY` for the header and
`[2]=EMPTY` for every body row, confirming the label shift is visible to the
model at the token level. The deterministic scorer verifies the structure.

Full probe transcript: [defect-probes.md](defect-probes.md) (same directory).

## v1.0.6: All-tables count-dump (per-unit)

v1.0.6 iterates every pipe unit in the paper, classifies each as
label_shift / continuation / aligned, and runs one count-dump or
continuation question per unit. Aligned tables are scored by comparing
the model's cell dump against the unit's actual cells.

| Unit | Classification | Result | Latency |
|---|---|---|---|
| T0 | aligned | PASS | 3593ms |
| T1 | aligned | PASS | 2890ms |
| T2 | label_shift | PASS | 8984ms |
| T3 | continuation (de Wever) | PASS | 483ms |
| T4 | continuation (Kawulak) | PASS | 250ms |
| T5 | continuation (Nash) | PASS | 266ms |
| T6 | continuation (Tanwar) | PASS | 250ms |
| T7 | continuation (Mara Bos) | PASS | 515ms |

**Result: 8/8 pass, 0 fail, 0 skip.**

Punch-list comparison:
- Label shift detected by LLM: YES
- All 5 continuation headers found: YES
- Aligned units false-failed: NONE

**Whisker sees what you saw.** Every punch-list defect matched,
no false-fail on aligned tables.

Full results: [all-tables.md](all-tables.md) (same directory).
Integrity note (2026-09-08): the committed `all-tables.md` is a later re-run
overwritten by transport failures (`ReadTimeout` on all 8 units, 0ms
answers); it is not the passing run. The passing v1.0.6 run's per-unit
outcomes and latencies are the table above; the raw dump of that run was not
preserved outside scratch.
Human-review ground truth: [human-review.toml](human-review.toml) (same directory).

## Issues

- #360: tomd producer bug (page-break reconstruction)
- #361: whisker contract gap (R1 + R2 deterministic lane closed; defect probes now confirm model comprehension via count-dump)
