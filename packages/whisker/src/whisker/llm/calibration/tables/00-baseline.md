# tomd LLM-readable conformance baseline (reconstructed)

> **Provenance notice (2026-09-08).** The original research baseline
> `research/tomd-llm-readable-conformance/00-baseline.md` was never committed
> and was lost before the 2026-09-07 lane restructure; the 2026-09-08 debt
> audit recorded its citations as dead (31 across both llm_readability
> contracts, ledger step 5). This file is the honest reconstruction at the
> calibration home. Per rule it records what the lost original contributed and
> which evidence survives. It restates no rule text:
> `det/llm_readability/deepseek-v4/tables/rules.toml` remains the single
> normative copy of R1-R13, and the punch-list locks live in
> [TABLE-CALIBRATION.md](TABLE-CALIBRATION.md) next to this file.

What the original was: the conformance research that measured how LLM-readable
tomd's markdown tables are and from which rules R1-R13 were distilled. Its
per-rule sections were cited as `00-baseline.md:R<n>`. The rule text, the
thresholds, and the per-rule rationale all survive verbatim in `rules.toml`;
what was lost is the narrative research layer underneath them.

`gist:<lines>` citations in `rules.toml` are shorthand for an external
research source. They carry no path and are intentionally not checked by the
citation tests; they are unaffected by this reconstruction.

## R1

Premise: a reading model recovers a pipe table by counting delimiters, so a
dropped delimiter relocates every value after it. Surviving evidence:
`gist:41-82`, `gist:59-63`, plus the measured N5040 label shift in
[evidence/n5040-attendance/notes.md](evidence/n5040-attendance/notes.md)
(issues #360/#361, probe evolution v1.0.4 semantic fail to v1.0.5
count-then-score pass to v1.0.6 per-unit 8/8). Lost: the original's
measurement narrative behind the phantom-column signature.

## R2

Surviving evidence: `gist:80-81`, `gist:279-282`, and the five N5040
continuation headers (de Wever, Kawulak, Nash, Tanwar, Mara Bos) locked in
TABLE-CALIBRATION.md and reproduced by the deterministic `check_pipe_header_separator`
plus the hermetic fixtures in `tests/det/test_llm_readability.py`
(`TestContinuationHeaderDetection`, `TestHtmlHeaderIsDataR2`). Lost: the
original's page-break-split analysis narrative.

## R3

Surviving evidence: `gist:269-286`,
`packages/whisker/research/research/llm-readability/05-web.md:110-130`
(pipe form measures best on multi-table QA at roughly a third of the tokens
of HTML). Lost: nothing load-bearing beyond the citation anchor.

## R4

Surviving evidence: `gist:152-158`, `gist:385-390`,
`packages/whisker/research/research/llm-readability/repo-scan/olmocr.md:50-55`.
Structural and coordinate probes measure best on HTML; merged-cell scoring
requires it. Lost: nothing load-bearing beyond the citation anchor.

## R5

Surviving evidence: `gist:240`, `gist:389-390`,
`packages/whisker/research/research/llm-readability/18-table-semantics-auditor.md:7`,
and the known weakness `merged-and-transposed-tables` in rules.toml (CompTab:
DeepSeek-V3 about 37.8% exact match on merged cells, about 25.0% on
transposed tables; lineage figures, no V4 Pro table benchmark exists).
Corroborating:
`packages/whisker/research/research/deepseek-v4-pro/04-table-understanding.md`.

## R6

Surviving evidence: `gist:245`,
`packages/whisker/research/research/llm-readability/18-table-semantics-auditor.md:8`.
The check reads raw row text because a cell splitter that ignores escapes
reproduces the defect. Lost: nothing load-bearing beyond the citation anchor.

## R7

Surviving evidence: `gist:242`, `gist:285`, the named threshold
`wide_table_column_threshold` (6, strict end of the researched 6 to 8 column
band; published evaluations of this lineage lose 10 to 15 points on wide and
hierarchical tables), and the measured sub-threshold column-association
weakness documented in
[fullread-32-test-comprehension.md](fullread-32-test-comprehension.md)
(reconstructed). The fleet holds no committed pipe table above the budget, so
R7 remains a hypothesis on our corpus.

## R8

Surviving evidence: `gist:243`, `gist:286`, the named thresholds
`long_table_row_threshold` (30 rows, where header labels start falling out of
attention) and `header_repeat_row_interval` (25, from the researched 20 to 30
row window). Lost: nothing load-bearing beyond the citation anchor.

## R9

Surviving evidence: `gist:244`, `gist:283`, the named threshold
`empty_cell_sentinels` (`-`, `N/A`). The rule exists because a blank cell is
ambiguous between intentionally empty and lost in conversion. Lost: nothing
load-bearing beyond the citation anchor.

## R10

Surviving evidence: `gist:228`, `gist:280`, the named threshold
`caption_max_distance_lines` (5, strict end of the researched 5 to 10 line
band). Lost: nothing load-bearing beyond the citation anchor.

## R11

Surviving evidence: `gist:246`,
`packages/whisker/research/research/llm-readability/18-table-semantics-auditor.md:7`.
Pipe syntax and code collide on both the delimiter and the backtick. Table-cell
listings are owned here, not by the codeblocks contract (C8). Lost: nothing
load-bearing beyond the citation anchor.

## R12

Surviving evidence: `gist:215-227`,
`packages/whisker/research/research/llm-readability/24-chunking-boundary-auditor.md:8`.
Half a table reads as complete and answers questions wrongly. The original
also cited `00-baseline.md:R28` (see below). Lost: nothing load-bearing
beyond the citation anchors.

## R13

Surviving evidence:
`packages/whisker/research/research/llm-readability/05-web.md:43-50`,
`packages/whisker/research/research/llm-readability/18-table-semantics-auditor.md:12`,
the named threshold `large_table_cell_budget` (200 cells), and the required
probes in rules.toml. Cell lookup and row retrieval collapse on large tables
for every format measured, so format conformance alone never discharges R13.
Promoted to HARD for this model because its table literacy is extrapolated.

## R28

Cited by R12 as a second anchor of the original baseline, in chunking
context. The original had more rules than the thirteen that were normalized
into the contract; R28's text is lost and no surviving document restates it.
Its normative content lives on only through R12 in rules.toml. This section
exists so the surviving `00-baseline.md:R28` citation resolves to an honest
statement instead of a gap.
