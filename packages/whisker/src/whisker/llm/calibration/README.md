# LLM lane calibration

Physical home of whisker's calibration work for LLM-readable output: the
punch-list locks for broken tables and broken code blocks, and the workflow
that grows them. The locks live here by operator decision (2026-09-08):
calibration is the process that feeds both lanes, so it gets its own home
outside the det/llm lane split. The deterministic engines that enforce the
locks stay in `det/llm_readability/` (`validate.py`, `code_validate.py`); the
advisory tapetum `code_boundary` lane they calibrate lives in
`llm/pdf_judge.py`.

- [tables/TABLE-CALIBRATION.md](tables/TABLE-CALIBRATION.md): R2 table-defect
  locks (issues #360-#380), enforced by `validate.py`.
- [codeblocks/CODEBLOCK-CALIBRATION.md](codeblocks/CODEBLOCK-CALIBRATION.md):
  C1/C6/C7 codeblock locks, enforced by `code_validate.py`, plus the tapetum
  `code_boundary` lane calibration history (v15-v19, PR 394 before/after
  evidence).
- [tables/00-baseline.md](tables/00-baseline.md) and
  [codeblocks/SYNTHESIS.md](codeblocks/SYNTHESIS.md): reconstructed research
  provenance for R1-R13 and C1-C10. The original uncommitted research
  documents were lost before 2026-09; these files record, per rule, what
  survives and what was lost. The contract citations in
  `det/llm_readability/deepseek-v4/{tables,codeblocks}/rules.toml` resolve
  here.
- [tables/fullread-32-test-comprehension.md](tables/fullread-32-test-comprehension.md):
  reconstructed 2026-07-09 readback study behind the
  sub-threshold-column-association weakness.
- [tables/evidence/n5040-attendance/](tables/evidence/n5040-attendance/notes.md):
  the committed N5040 punch-list evidence cited by the `per-unit-count-dump`
  probe.
- [tables/EVIDENCE.md](tables/EVIDENCE.md) and
  [codeblocks/EVIDENCE.md](codeblocks/EVIDENCE.md): curated maps of every
  living evidence source per rule, including tests and sister research.

## Calibration workflow

Calibration closes the loop between a broken conversion and a whisker check
that catches it. The loop, per defect:

1. Find a broken table or code block in a tomd conversion (issue, human
   review, golden-QA gap).
2. Run `whisker llm-readability check <pid>.md` (with `--construct codeblocks`
   for fence defects). If the check already fires, the defect is covered; pin
   it in the calibration file and stop.
3. If whisker does NOT find it, calibrate whisker: add a NEW helper in the
   engine (`validate.py` for tables, `code_validate.py` for code blocks) plus
   a hermetic fixture, and lock the paper in
   [tables/TABLE-CALIBRATION.md](tables/TABLE-CALIBRATION.md) or
   [codeblocks/CODEBLOCK-CALIBRATION.md](codeblocks/CODEBLOCK-CALIBRATION.md).
   Additive only: never loosen, merge, rename, or "simplify" an existing
   heuristic; if a new branch is too loud, narrow that branch. Contract rules
   stay in `det/llm_readability/deepseek-v4/{tables,codeblocks}/rules.toml`;
   no new rule IDs for these defect classes.
4. Fix tomd.
5. Re-run the check on both states: the lock must still fire on the BASE
   (broken) conversion, and the HEAD (fixed) conversion must come back clean.
6. If the lock no longer fires on BASE, or newly fires on HEAD, recalibrate
   whisker until it separates before from after.

Control papers (`TestNewFlagsControlPapers`, `TestNewCodeFlagsControlPapers`;
P0876R23 / P3596R0) must stay green through every calibration round.

The agent procedure that extends this loop with the advisory LLM paper run
and the user's side-by-side preview gate lives in
`.cursor/skills/whisker-table-calibration/SKILL.md`.
