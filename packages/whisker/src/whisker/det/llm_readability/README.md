# LLM readability (hosted models)

This package holds whisker's definition of a correctly extracted, LLM-readable
table, and the machinery that certifies a document against it. Each hosted model
gets its own subdirectory with a self-contained `rules.toml` that carries the
full contract (R1-R13, thresholds, applicability predicates) with model-specific
values baked in, plus the profile metadata (identity, certification, weaknesses,
probes).

Currently the only profiled model is
[DeepSeek V4](deepseek-v4/README.md) (`deepseek-v4/tables/rules.toml`).

The Python engine (`contract.py`, `profile.py`, `validate.py`, `report.py`,
`cli.py`) sits next to the data and is model-independent.

Punch-list R2 flags are locked in
[TABLE-CALIBRATION.md](../../llm/calibration/tables/TABLE-CALIBRATION.md).

Adding a model means adding a sibling directory to `deepseek-v4/` with its own
`rules.toml`, never a modification of the engine or an existing model's file.

## Calibration workflow

The calibration loop and its punch-list locks live under
[`llm/calibration/`](../../llm/calibration/README.md) (tables and
codeblocks). The engines those locks constrain are `validate.py` and
`code_validate.py` in this package.

## Commands

```powershell
whisker llm-readability rules
whisker llm-readability rules --model deepseek-v4-pro
whisker llm-readability rules --profile deepseek-v4 --rubric
whisker llm-readability rules --json
whisker llm-readability profiles
whisker llm-readability check path\to\candidate.md [--json]
```

`rules` shows the contract for the default profile (deepseek-v4), or for a
specified model. `profiles` lists the packaged profiles with their version,
hash, model identity and certification status. `check` runs the candidate-side
deterministic evaluation and can never print a model certification.

`python -m whisker.det.llm_readability.cli <verb>` reaches the same handler without
the top-level dispatcher, which is useful when bisecting a routing problem.
