# DeepSeek V4 LLM-readable tables

The single normative copy of the contract is [`rules.toml`](rules.toml). It
contains the full rule set (R1-R13), all thresholds, the DeepSeek V4 profile
metadata, known weaknesses and required probes, with model-specific values
baked directly into the definitions. The Python engine that loads, validates
and evaluates this contract (`contract.py`, `profile.py`, `validate.py`,
`report.py`, `cli.py`) lives in `llm_readability/` (two levels up), not
here, because it is model-independent. This file explains why the contract
says what it says.

## Status: pending, not certified

The contract exists, the certification process is implemented, and defect
detection probes have been executed. **Certification is still pending.**
`source_compare` (R3-R5, R10, R11) is not wired. R13 stays `not_evaluated`
(corrupt control does not invert). Nobody may claim "DeepSeek V4 Pro certified."

### Defect detection evidence (v1.0.6)

N5040 section 10 (Attendance) has two conversion defects: a phantom column
(label shift) and five page-break continuation headers. Whisker detects both:

- **Deterministic:** R1 fails the label shift, R2 fails all five continuations.
  `whisker llm-readability check` fails the paper.
- **LLM (per-unit count-dump):** `run_unit_dumps` sends each of the 8 pipe
  units as an isolated fragment to DeepSeek V4 Pro. All 8 match the human
  punch-list: label shift seen, all five continuations classified as data
  values, two aligned tables pass without false-fail.

This is evidence about per-table model comprehension, not a certification gate.
`whisker-tapetum-llm` runs the dumps when pod credentials are present and
writes them as `unit_dumps` on the readability block. They do not stamp
`METHOD_LLM` and do not certify. The scratch runner calls the same block.

A five-paper readback (2026-08-12, de-needle-v2, `alliance-pod`) scored 31
of 37 facts. That is comprehension evidence, not table certification.

## What it binds to

The profile binds to model identity `deepseek-v4-pro`, plus the vendor-style
aliases the same model appears under. Two service slots currently serve it,
`alliance-pod` and `h200x8-deepseek-v4-pro`, and both are recorded as provenance
only. A slot rename does not change what this profile is about; swapping a slot to
a different model does, which is why the binding is on the model name.

Resolving by service works by reading the model identity out of `SERVICES.toml`
first, so a slot pointed at a model with no profile fails closed rather than
silently inheriting this one.

## Why the thresholds are at the strict end

Two contextual thresholds are set at the strict end of the band the research
established rather than at the loose end:

- **Wide-table column budget: 6.** Published evaluations of this lineage lose
  10 to 15 points on wide and hierarchical tables, and there is no table benchmark
  for V4 Pro at all. WG21 papers routinely carry the multi-row headers that fall
  in exactly that category. The loose end of the band (8) is not defensible for a
  model whose table behavior is extrapolated.
- **Caption adjacency: 5 lines.** The binding between a label and its table
  is the cheapest piece of context to lose, and this model's structure
  understanding is unmeasured.

## Why R13 is HARD

R13 is the probe rule. For this model, whose table literacy is **extrapolated
from V3-era benchmarks**, an unexecuted lookup probe means the central claim was
never tested. A certification run must execute cell-lookup and row-retrieval
probes with a corrupt control that demonstrably inverts. Format conformance never
discharges R13 here.

## The intermittent failure that drives R7's extra instruction

In the 2026-07-09 grounded readback, the run that scored 34 of 37, this model
named the right neighbor cell of P0876R23's St. Louis poll table correctly and
then reported the column heading `F` where the table says `SF`. A clean
five-column pipe table, well below any wide-table budget.

The current de-needle-v2 run passes both P0876R23 poll probes, answering `SF` both
times. That does not retire the weakness, and the current certificate must not be
cited as evidence of the failure. A later TOC A/B experiment moved this same fact
by one and attributed the difference to model variance rather than to navigation,
so what we have is an intermittent column-association failure on a clean narrow
table, not a fixed one. One passing run is not evidence of absence.

Passing the column count therefore proves nothing about whether values were
attributed to the right column, so R7 carries an added instruction in `rules.toml`
demanding at least one value be verified against its header label explicitly.

The fleet holds no committed pipe table above the wide-table budget, so R7's own
threshold is currently a hypothesis on our corpus while column association is a
demonstrated, variance-prone failure below it.

## Known weaknesses

| Weakness | Rules | Basis |
|---|---|---|
| Merged and transposed tables | R4, R5 | Lineage benchmark, roughly 37.8% exact match on merged cells and 25.0% on transposed. |
| Wide and hierarchical degradation | R7 | Lineage benchmark, 10 to 15 point loss, worsening with table token count. |
| Sub-threshold column association | R7, R13 | Measured on this model on P0876R23 in the 2026-07-09 grounded run; the current run passes the same probe, so the failure is intermittent. |
| Table-neighbor misread | R1, R13 | Measured locally on P4185R0: wrong neighbor cells returned while the deterministic lane passed the same facts on the same markdown. |
| Near-zero abstention | R5, R10, R11 | The model returns a confident answer instead of an unknown, so confidence is not usable as a correctness proxy and a model verdict without grounded verbatim cell evidence must not close a source-compare rule. |

Lineage figures are labeled as such in `rules.toml`. They are V3-era numbers and
are not measurements of the served model.

## What certification would take

The profile requires all four lanes to have actually run: `deterministic`,
`source_compare`, `llm`, `certification`. It additionally requires R5, R10, R12
and R13 to carry a real status rather than `not_evaluated` or `not_applicable`.
R12 is listed so a run must declare its chunk boundaries instead of leaving chunk
atomicity inapplicable.

R7 is deliberately absent from that list, even though wide tables are this
model's worst measured category. R7 only applies once a table exceeds the column
budget, so demanding a real status for it would make every narrow-table paper
permanently uncertifiable, and a certification nobody can earn stops meaning
anything. The column-association weakness is carried by R13 instead, which is
promoted to HARD and whose required probes include a narrow table.

Four probes are required:

1. **Cell lookup with corrupt control** on the largest table, where the clean run
   recovers cells and the corrupt run fails them.
2. **Column association on a narrow table**, because that is where this model is
   measured to fail locally.
3. **Merged-cell denormalization**, in both directions: accept a faithfully
   repeated span value, reject a value repeated into rows the span did not cover.
4. **Code-in-cell structure**, so a listing flattened into a single pipe cell is
   detected rather than paraphrased back as prose.
