# fullread-32 test comprehension (reconstructed)

> **Provenance notice (2026-09-08).** The original
> `research/tomd-llm-readable-conformance/fullread-32-test-comprehension.md`
> was never committed and is lost (see the reconstruction notice in
> [00-baseline.md](00-baseline.md)). It was cited at line 136 by exactly two
> entries in `det/llm_readability/deepseek-v4/tables/rules.toml`: the known
> weakness `sub-threshold-column-association` and the required probe
> `column-association-narrow-table`. This file reconstructs what that citation
> supported, from sources that survive.

## What line 136 backed

The 2026-07-09 grounded readback run (alliance-pod, DeepSeek-V4-Pro, the run
that scored 34/37 under the stricter grounded scoring): the pod named the
right neighbor cell of P0876R23's St. Louis poll table correctly (8) and then
reported the column heading "F" where the table says "SF". A clean
five-column pipe table, far below any wide-table budget.

This finding survives verbatim in `packages/whisker/FIXPATH-REPORT.md:90-99`,
which records all three fails of that run:

- `P0876R23 table-poll-stlouis`: right neighbor, wrong column heading
  ("F" instead of "SF"), an off-by-one column-alignment misread.
- `P4185R0 table-anchored-true-zero`: the row label ("Physical origin")
  instead of the immediate left neighbor ("Point origin (explicit or
  implicit)"), again a column-alignment misread.
- `P4185R0 table-text-output-point-no`: answered from the wrong one of two
  similarly named cells; partially a question-phrasing limitation.

The deterministic lane passed all 37 facts against the same markdown, so the
fails are honest advisory findings about the model, not the markdown.

## What else the original carried

The "32" scope of the study (its paper set and full question inventory) is
lost. Surviving context around the same weakness:

- The current de-needle-v2 run (2026-08-12, same pod and model) PASSED both
  P0876R23 poll-table probes, answering "SF" both times, as recorded in
  `packages/whisker/corpus/p0876r23.readback.md`. That run scored 31/37 with
  a corrupt control that did not invert; it is evidence about the model, not
  a table certification (rules.toml profile notes).
- A later TOC A/B experiment moved this same fact by one and attributed the
  difference to model variance rather than to navigation (rules.toml weakness
  prose). One clean run of a probe that has failed before under stricter
  scoring is exactly what a variance-prone column-association failure looks
  like.
- `packages/whisker/research/research/llm-golden-verification-gap/archaeology/a14-langextract-redteam.md:18`
  is cited alongside this weakness.
- `packages/whisker/corpus/READBACK-CERTIFICATE.md` and
  `packages/whisker/corpus/p4185r0.readback.md` back the sibling weakness
  `table-neighbor-misread` (P4185R0 table-anchored fact failed under
  de-needle-v2 with wrong neighbor cells while the deterministic lane passed).

## Standing instruction (carried by rules.toml)

Do not cite the current certificate as evidence of this failure, and do not
cite one passing run as evidence of its absence. The probe
`column-association-narrow-table` remains required even though the most
recent run passes it: the failure it targets is intermittent on this model.
