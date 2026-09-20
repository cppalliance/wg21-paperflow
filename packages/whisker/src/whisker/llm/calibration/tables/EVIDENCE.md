# Tables calibration evidence map

Curated map of every living evidence source behind the R1-R13 table contract.
Normative rule text lives only in
`../../det/llm_readability/deepseek-v4/tables/rules.toml`; this file is a
finding aid, not a second copy.

## In this folder

- [TABLE-CALIBRATION.md](TABLE-CALIBRATION.md): punch-list locks (issues
  #360-#380). Additive only.
- [00-baseline.md](00-baseline.md): reconstructed conformance baseline,
  per-rule provenance R1-R13 + R28.
- [fullread-32-test-comprehension.md](fullread-32-test-comprehension.md):
  reconstructed 2026-07-09 readback study backing the
  sub-threshold-column-association weakness.
- [evidence/n5040-attendance/](evidence/n5040-attendance/notes.md): the
  N5040 attendance punch-list evidence (moved out of `_scratch` on
  2026-09-08 because the normative contract cites it): human-review ground
  truth (`human-review.toml`), per-unit dump results (`all-tables.md`),
  probe transcripts (`defect-probes.md`), run record (`notes.md`,
  `check.json`, `attendance-excerpt.md`).

## Living citations carried by rules.toml

| Rule | Living evidence beyond the reconstructed baseline |
|---|---|
| R1, R2 | `evidence/n5040-attendance/` (issues #360/#361, v1.0.4-v1.0.6 probe evolution) |
| R3 | `research/research/llm-readability/05-web.md:110-130` |
| R4 | `research/research/llm-readability/repo-scan/olmocr.md:50-55` |
| R5, R6, R11 | `research/research/llm-readability/18-table-semantics-auditor.md` |
| R12 | `research/research/llm-readability/24-chunking-boundary-auditor.md:8` |
| R13 | `research/research/llm-readability/05-web.md:43-50`, `18-table-semantics-auditor.md:12` |
| weaknesses | `research/research/deepseek-v4-pro/04-table-understanding.md`, `00-baseline.md` (deepseek-v4-pro topic), `FIXPATH-REPORT.md:90-99`, `research/research/llm-golden-verification-gap/archaeology/a14-langextract-redteam.md:18` |
| probes | `corpus/READBACK-CERTIFICATE.md`, `corpus/p4185r0.readback.md`, `corpus/p0876r23.readback.md`, `evidence/n5040-attendance/` |

All paths above are relative to `packages/whisker/`. `gist:<lines>` entries
are unchecked external-source shorthand.

## Sister research (context, not cited by the contract)

- `research/research/llm-readability/`: the readability research topic
  (baseline, synthesis, `_patterns-matrix.md`, `repo-scan/` with about 20
  converter scans).
- `research/research/llm-readability-fixpath/`: the tomd fix-path topic.
- `research/research/deepseek-v4-pro/`: model capability research.

## Tests that hold this contract

- `tests/det/test_llm_readability.py`: contract schema, citation resolution,
  `TestContinuationHeaderDetection`, `TestHtmlHeaderIsDataR2`,
  `TestFlattenedProseDetection`, control papers `TestNewFlagsControlPapers`
  (P0876R23 / P3596R0).
- Engines constrained by the locks: `det/llm_readability/validate.py` and
  `det/llm_readability/table_probes.py`.
