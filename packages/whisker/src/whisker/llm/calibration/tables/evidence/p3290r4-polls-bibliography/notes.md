# P3290R4 polls and bibliography: calibration evidence (issue #426)

Date: 2026-09-18. `_LANE_VERSION` 24 -> 25. Model `deepseek-v4-pro`.

BASE markdown: `data/paperstore/p3290r4.md`, sha256
`a133daa2b63551dce042fb0bbc0205870b89dc4511dcf3334d6fc205c2e7622c`
(tomd convert before the #426 bibliography fix; the same bytes on both runs).

## The eight pipe tables

| unit | shape | human | det R2 | lane v24 (BASE run) | lane v25 |
|---|---|---|---|---|---|
| T0-T4 | `SF \| F \| N \| A \| SA`, one numeric row, `Result: Consensus` follows | OK | `truncated_leak` (false positive, frozen) | `prose`, ABSTAIN | `prose`, ABSTAIN |
| T5-T6 | `Name \| Meaning` enum tables | OK | aligned | `match`, PASS | `match`, PASS |
| T7 | bibliography: `[P3191R0] [P3290R0] [P3311R0]` in one header cell, `With Contracts”, 2024` own column, `[P2900R14]` body row, year shifted | tomd defect | `header_is_data` | `glue`, DEFECT | `glue`, DEFECT |

Unit-dump summary both runs: `pass=2 defect=1 abstain=5 fail=0 skip=0`.

## Why T0-T4 abstain and what v25 changed

- No textlayer pairing: a poll header has no token longer than 3 characters,
  so no source-first question. No grid pairing: the page-layout grids on the
  poll pages are pseudo-header grids since v24 (`grid=unreliable (no pairing)`).
  The typed `truncated_leak` question decides.
- v24 already answered `prose` on all five. Two things were still wrong:
  the question did not say that a caption line is prose (the model was right
  without being told), and `_estimate_line_after` matched the first line equal
  to the header text, so T1-T4 were shown T0's trailing prose
  (`_debug_` run on the real markdown, v24: all five lookaheads at line 82;
  v25: 82, 92, 102, 215, 413, each followed by that poll's own
  `Result: Consensus`).
- v25 question: "A short 'Label: value' caption directly under the table,
  such as 'Result: Consensus' or 'Outcome: No consensus', is prose. Answer
  'leaked rows' only when the text carries cell values that belong in the
  table's columns, even if it names a meeting, a date or a poll." The
  adversarial review of the first draft ("or a meeting and date line, is
  prose") produced the counter-table `Meeting | Date | Outcome` with a
  leaked `Wrocław 2024-11-20 Forwarded to LEWG` row; the exemption is the
  caption shape, not the vocabulary.

Final-rubric run (`--force`, P3290R4 only, after the review fix): T0-T4
`prose` ABSTAIN with the `Label: value` question in the sidecar, T5/T6
`match` PASS, T7 `split` DEFECT, tapetum `review` 0.90, fusion `review`.

## T7 stays confirmed

Source-first probe `src-t7` on textlayer page 19: expected `source
verdict=glue`, answered `glue`, `defect_confirmed=true`. The monolith judge
names the same defect in both runs:

- v24: "bibliography table has header with 4 cells but body rows with 3
  cells, shifting values" (tapetum `not-llm-readable` 0.90).
- v25: "The bibliography is corrupted: P2900R14, P3191R0, P3290R0, and
  P3311R0 entries are merged into a malformed table with scrambled text and
  wrong years" (tapetum `review` 0.72).

The monolith verdict moved `not-llm-readable` -> `review` between the runs on
identical bytes and an unchanged monolith prompt (`prompt_sha256` equal, only
`_LANE_VERSION` differs); the unit question is not part of that call. This is
the documented MoE rerun variance, not a rubric effect. Fusion verdict is
`review` in both runs (`ideal review cap`).

## Controls (same command, same run)

| paper | v24 (BASE run) | v25 | units |
|---|---|---|---|
| P0876R23 | review 0.90 | review 0.92 | T0/T1 aligned SKIP, unchanged |
| P3596R0 | review 0.95 | review 0.90 | T0/T1 aligned PASS, unchanged |
| N5040 | review 0.95 | review 0.95 | T0-T3 aligned; T2 `src-t2` answered `leaked-rows` (DEFECT) on the BASE run, `match` (PASS) on v25 and on a `--force` rerun |

N5040 T2 is an `aligned` unit on the source-mismatch probe
(`_build_source_mismatch_question`), which v25 did not touch; the BASE answer
is the outlier of three runs. No control verdict moved.

## Commands

```
whisker llm-readability check data/paperstore/p3290r4.md --json
whisker-tapetum-llm P3290R4 P0876R23 P3596R0 N5040 --inspect --concurrency 1
whisker-tapetum-llm N5040 --inspect --concurrency 1 --force
uv run --package whisker pytest packages/whisker/tests/llm/test_table_probes.py -k P3290
```

HEAD expectation after the tomd fix (#426 part 1): no bibliography unit,
T0-T4 still abstain, controls unchanged. BASE bytes must still confirm T7.
