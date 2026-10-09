# Codeblocks calibration evidence map

Curated map of every living evidence source behind the C1-C10 codeblock
contract. Normative rule text lives only in
`../../det/llm_readability/deepseek-v4/codeblocks/rules.toml`; this file is a
finding aid, not a second copy.

## In this folder

- [CODEBLOCK-CALIBRATION.md](CODEBLOCK-CALIBRATION.md): punch-list locks for
  the C-rule deterministic checks, plus the tapetum `code_boundary` LLM lane
  calibration history (v15-v19, PR 394 before/after evidence on p0533r9 and
  p2040r0). Additive only.
- [SYNTHESIS.md](SYNTHESIS.md): reconstructed codeblock research synthesis,
  per-rule provenance C1-C10.

## Living citations carried by rules.toml

Every C1-C10 rule, the contract header, the `diagram-as-cpp` weakness, and
the `identifier-line-lookup` probe cite the reconstructed
[SYNTHESIS.md](SYNTHESIS.md). The original uncommitted synthesis is lost;
what it backed survives in the rule text, the locks, and the fixtures below.

## Tests that hold this contract

- `tests/det/test_llm_readability_codeblocks.py`: contract schema, citation
  resolution, `TestHeadingInFence` (C7, BASE p0533r9), `TestListingSplit`
  (C1, HEAD p0533r9), `TestFalseWordingOnComment` (C6, BASE p2040r0),
  `TestMetadataShortCircuit`, control papers `TestNewCodeFlagsControlPapers`
  (P0876R23 / P3596R0).
- Engines constrained by the locks: `det/llm_readability/code_validate.py`
  and `det/llm_readability/code_probes.py`; the advisory lane they calibrate
  is `llm/pdf_judge.py` (`code_boundary`).

## Related calibration assets outside this folder

- Table-cell listings are owned by the tables contract R11, see
  [../tables/EVIDENCE.md](../tables/EVIDENCE.md).
- The PR 394 raw before/after artifacts (tapetum JSON, debug transcripts)
  live in `_scratch/whisker-pr394-llm/` and are ephemeral by design; their
  committed distillation is CODEBLOCK-CALIBRATION.md.
