# P4178R0 citation boxes: calibration evidence (issue #427)

Date: 2026-09-21. `_LANE_VERSION` 25 -> 26. Model `deepseek-v4-pro`.

BASE markdown: `data/paperstore/p4178r0.md`, sha256
`6a19ffc75d7512c9e83d799f34c1ec8671e4a4db7be7208dd4b131aa4543b391`.

## The seven pipe-table units

| unit | human / det | lane v25 | lane v26 expectation |
|---|---|---|---|
| T0 | OK control | PASS | unchanged PASS |
| T1 | OK; det `header_is_data` is C5 disagreement/noise | ABSTAIN | unchanged ABSTAIN |
| T2-T5 | det `flattened`; real citation-box flattening | DEFECT | unchanged DEFECT |
| T6 | det `flattened`; real citation-box flattening | SKIP: `no typed question for flattened` | typed `flattened` answer confirms DEFECT |

det is frozen. This change only closes the advisory lane's no-textlayer
dispatch gap.

## Why T6 skipped and what v26 changes

- T6 has no text-layer pairing. In v25, the no-source branch had its own
  partial typed-question dispatch and did not include `flattened`, even though
  the source-first fallback already had `_build_flattened_question`.
- v26 sends a non-aligned no-textlayer unit through the shared
  `_typed_question_for` and `_score_typed_answer` dispatch. T6 therefore gets
  the existing closed question and an answer of `flattened` confirms the
  defect.
- The shared branch preserves typed-class behavior: `truncated_leak` without
  markdown lines still skips, while `wrap_orphan` and `hyphen_glue` use their
  existing typed scorers.
- The change does not turn self-comparison into evidence. An aligned unit
  without text-layer evidence still skips with `no textlayer; refusing
  self-dump`.
- `flattened` remains reject-and-keep. A typed `match` does not clear det's
  class; without source or a keep-worthy grid signal the unit ABSTAINS.

T0 and T1 are locks on blast radius. T0 remains PASS. T1 still asks the
`header_is_data` typed question and remains unconfirmed when the answer is
`column headers`.

## Adversarial logic review

The review found that `score_flattened_answer` accepted any answer containing
the substring `flatten`, so a negative answer such as `not flattened; match`
could incorrectly become sole evidence of a defect on the no-source path.
The minimal fix follows the prompt contract: typed and source-first probes
accept only one complete normalized closed answer. Prose, negation, punctuation,
embedded forms such as `unflattened`, and multiple verdicts are ambiguous and
non-confirming. An ambiguous aligned answer is not stamped `DEFECT`; a recognized
non-match verdict such as `split` still is.

## Rerun variance is unrelated

The fleet comparison also showed a P3596 class-result movement on rerun and an
N5040 source-probe movement. Neither paper exercised the changed no-textlayer
typed-question path: the P3596 class unit path and the N5040 source-first probe
path were unchanged. These are model rerun variance, not effects of the v26
dispatch change. `tapetum-outlier-v26.log` records the follow-up run; it does
not justify widening this change.

The target P4178R0 rerun is the only causal rerun required for this calibration.
Fleet `suggested_verdict`, confidence, and unit-dump shape deltas are advisory
blast-radius evidence. The hard gate is parseability, snapshot commit/tree/lane
binding, use of the live staged lane, and stable markdown/source/schema/model
identity.

## Final target-only rerun

`tapetum-target-final-v26.log` records the target rerun on the final code bytes
with lane 26: tapetum `review` at 0.90 confidence. T0 aligned PASS; T1
`header_is_data` ABSTAIN; T2-T6 `flattened` DEFECT. No units skipped, and the
T6 typed answer was `flattened`.

## Tests

The exact regression classes are `TestFlattenedTypedQuestion`,
`TestScoreFlattenedAnswer`, `TestClosedVocabTypedAnswers`,
`TestScoreSourceMismatchAnswer`, `TestNoSourceTypedBranch`, and
`TestSourcePairedClosedAnswers` in
`packages/whisker/tests/llm/test_table_probes.py`. The issue-path locks include:

- `test_flattened_unit_without_textlayer_gets_typed_question`
- `test_flattened_typed_answer_confirms`
- `test_flattened_match_answer_abstains`
- `test_not_flattened_match_abstains`
- `test_header_pair_stays_unconfirmed`
- `test_aligned_without_textlayer_still_skipped`
- `test_truncated_leak_without_md_lines_is_skipped`
- `test_wrap_orphan_without_textlayer_uses_typed_scorer`
- `test_hyphen_glue_without_textlayer_uses_typed_scorer`

Commands:

```powershell
uv run --package whisker pytest packages/whisker/tests/llm/test_table_probes.py -q -k "TestFlattenedTypedQuestion or TestScoreFlattenedAnswer or TestNoSourceTypedBranch"
uv run --package whisker pytest packages/whisker/tests/llm/test_table_probes.py packages/whisker/tests/llm/test_incremental.py -q
```

Current affected-file result after the lane 27 scorer and question change: `254 passed, 3 skipped`.

## Lane v27: section-reference headers

HEAD golden sha256 `03cb700354ce4b618dc8855b10e2ae1783439a9cadfa26d61840ba493cf1cf7f`.
Lane v26 judged that file `review` 0.95 with zero `flattened` units, and
confirmed three `header_is_data` units (3 Section 4.15, 9 1.9.3/receiver,
14 4.9.4/Context) because the typed question asked whether a section
reference was a data value, and the typed call did not send the text
layer. Source-first had said `match`.

Lane v27 asks whether the markdown header is the PDF's top row or a body
row that moved up. Only the exact answer `body row` confirms. `data values`
abstains. The typed fallback sends the paired text-layer page.

BASE on lane 27 (`6a19ffc7…`, `tapetum-inspect-BASE-v27.md`): T0 aligned
PASS, T1 `header_is_data` ABSTAIN (`top row`), T2-T6 `flattened` DEFECT.
The broken paper stayed broken.

The first HEAD wording (2026-09-21) confirmed 10 units with `body row`.
The question then said a section reference opens the table and is the
top row, and `body row` only when the PDF shows a different header above
it. Second HEAD rerun, same golden `03cb7003…`: 19 units, 0
`defect_confirmed`, every `header_is_data` typed answer `top row`. Fused
`review` 0.95 remains the text nid gate (0.75), not a table defect.

The following files are local evidence under the issue scratch directory.
They are not shipped:

- `tapetum-inspect-BASE-v25.md`
- `fleet-v26-vs-snapshot.md`
- `tapetum-outlier-v26.log`
- `tapetum-target-final-v26.log`
