# Codeblock-defect calibration lock

Punch-list calibration for C-rule deterministic checks. **Additive only.**

A new convert defect gets a **new helper** and a hermetic fixture. Do not
loosen, merge, rename, or "simplify" an existing heuristic if a row below
or `TestNewCodeFlagsControlPapers` goes red. If a new branch is too loud,
narrow *that* branch.

Engine: `code_validate.py` (flags) → C1/C6/C7 checks → tapetum
`code_boundary` LLM lane. Contract rules stay in
`deepseek-v4/codeblocks/rules.toml`. No new rule IDs for these classes.

| Paper | Issue | Lock (must still fire) | Tests / check |
|---|---|---|---|
| P0533R9 BASE | PR 394 S1 | heading-in-fence must fire (C7) | `TestHeadingInFence`, `check p0533r9.md --construct codeblocks` (BASE swap) |
| P0533R9 HEAD | PR 394 S1 | listing-split must fire (C1); heading-in-fence quiet | `TestListingSplit` |
| P2040R0 BASE | PR 394 S2 | false wording on comment must fire (C6) | `TestFalseWordingOnComment` |
| P2040R0 HEAD | PR 394 S2/S3 | C6 comment branch quiet; `### ABSL_FLAG` present | `TestFalseWordingOnComment` |
| P0876R23 / P3596R0 | control | no new flags | `TestNewCodeFlagsControlPapers` |
| P4016R0 HEAD | issue 413 | LLM `prose_in_fence` quiet on monospace-set lines (fence:1 `[1e16, 1, 1, -1e16, 1, 1]`, fence:5/6 `Iterative Pairwise (IPR)  Recursive Bisection`); font evidence + clamp (v22) | `tests/llm/test_fence_fonts.py`, `whisker-tapetum-llm P4016R0 --all-pages` -> pass |

`_false_wording_on_comment_findings` fires only when `<ins>/<del>` wraps
a bare `//` comment. Clean code with `//` comments passes.

## LLM lane (tapetum `code_boundary`)

The LLM `code_boundary` lane in `pdf_judge.py` runs scoped checks on
individual fences (one LLM call per fence slice with context lines).
As of v16/v19, the lane uses per-fence scoping instead of per-page
scoping. The default fleet gates CB behind `--inspect` / `--all-pages` /
`--exhaustive-units` and the metadata short-circuit. Cap is 6.

### Design: per-fence scoping (v16/v17)

v15 sent the ENTIRE markdown plus a page number to the LLM per call.
Because the markdown has no page anchors, the model hallucinated
fence-membership: attributing headings and prose to the wrong fences,
duplicating findings across page calls, and flagging content that sits
cleanly outside any fence.

v16 fixes this with `_fence_slices()`: each LLM call receives ONE fence
plus `CODE_BOUNDARY_CONTEXT_LINES` (8) lines of surrounding context.
The prompt demands EXACTLY ONE finding per call.

v17 raised `CODE_BOUNDARY_FENCE_CAP` from 6 to 25. v18/v19 reverted the
cap to 6 (v17 calibration overfit; 0 CB demotions on the 09-01 fleet).
Per-fence calls are cheap (~40-80 lines each). Audit modes still run
CB. Future work: risk-prioritized fence selection (let deterministic
signals nominate suspect fences) to keep cost flat on very large papers.

Eliminated FP classes (v16):
- Fehlattribution (content from line 235 reported as "page:1")
- Duplicate findings (same `fwd`/`make_array` on pages 2, 3, and 6)
- Hallucinated fence-membership (`## Design points`, bullet lists
  flagged as `in_fence` despite being cleanly outside)

### Before/after evidence (PR 394, v17, 2026-08-27)

| Paper | State | Non-clean findings (v17) | Key finding |
|---|---|---|---|
| P0533R9 | BASE | 9 (fence:2,5,6,7,8,11,12,14,18) | **heading_in_fence C7** on fence:7,8 (`F. Modifications to "Header<cmath> synopsis" [cmath.syn]`) |
| P0533R9 | HEAD | 7 (fence:2,3,6,7,9,11,12) | heading_in_fence **GONE** (fence:7 is now `//[c.math.abs]` comment, borderline) |
| P2040R0 | BASE | 2 (fence:11,12) | label-in-fence residuals (`fwd`); C6 not found by LLM (deterministic lane handles `<ins>`/`<del>`) |
| P2040R0 | HEAD | 2 (fence:11,12) | same residuals, zero new findings, all early fences clean |

C7 on P0533R9: the cmath section heading was captured inside a code
fence in BASE and is **absent from HEAD**. This is the critical PR-394
fix, confirmed by the LLM lane across a full v17 before/after cycle.

C6 on P2040R0: `false_wording_on_comment` (`<ins>//constrains...</ins>`)
is a content-level defect (HTML wording markup inside code). The
per-fence `code_boundary` prompt targets structural boundary issues
(heading/prose captured in fence, listing split). C6 is handled by the
deterministic lane, which fires correctly on BASE and is quiet on HEAD.

Residual true positives (tomd defects, not PR-394 regressions):
- P0533R9 fence:2-3: prose fragment `by, or logarithms2 of, zero);`
  swallowed into a code fence (originates from PDF extraction).
- P0533R9 fence:5-6,9,11-12: ellipsis-only fences (`...`), listing-
  split artifacts.
- P2040R0 fence:11-12: bare label lines `fwd`/`make_array` in fence
  (PDF listing-label extraction artifact).

### Source font evidence and the C9 clamp (v22, issue #413, 2026-09-16)

P4016R0 (18 comparison tables, all locked) stayed on `review` because the
CB judge flagged three lines as `prose_in_fence`: the data literal
`[1e16, 1, 1, -1e16, 1, 1]` (fence:1) and the ASCII-diagram column header
`Iterative Pairwise (IPR)     Recursive Bisection` (fence:5, fence:6).
All three are set in a monospace font in the PDF; the deterministic
`prose_in_fence` (which has the font layer) was quiet. The judge only
saw the markdown and read the lines as prose.

`llm/fence_fonts.py` closes the gap from both sides: the per-fence user
message carries a `SOURCE FONT EVIDENCE` block (monospace / proportional /
unmatched counts, up to 3 proportional sample lines), the prompt makes it
authoritative for C9, and `clamp_source_monospace` rewrites a surviving
`prose_in_fence` on a monospace-set line to `clean`. A proportional-set
line (genuinely swallowed prose, P0533R9 fence:2-3 `by, or logarithms2
of, zero);`) is never clamped, so the true-positive residuals above keep
firing.

Test: `TestMetadataShortCircuit::test_metadata_short_circuit_still_runs_code_boundary`
verifies the lane runs under the metadata short-circuit (hermetic, no LLM).
Test: `TestFenceSlices` verifies slice construction, context windows, and cap.
