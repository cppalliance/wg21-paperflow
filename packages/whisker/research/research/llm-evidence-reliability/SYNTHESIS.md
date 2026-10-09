# LLM Evidence Reliability - Synthesis

**Date:** 2026-07-16  
**Scope:** 5 web foragers, 30 local-repository/code personas, GPT-5.6
re-verification, and runtime replay against the 20 observed missing-content
quotes. Research only; no production code changed.

## Answer

Whisker's LLM comparison architecture is sound, but its evidence label is not.
The PDF lane verifies only that a quote occurs in the source, then reports that
it is absent from Markdown without checking the Markdown.

The smallest correct improvement is a conservative, deterministic
candidate-side filter built from the existing `ground_spans` machinery. The LLM
continues to propose missing content. Mechanics determine whether each proposal
is:

- `present_in_candidate`: the missing claim is refuted;
- `candidate_not_found`: source-grounded, but absence is not proved;
- `ambiguous`: a fuzzy, sanctioned, or surface-sensitive match prevents a
  reliable binary claim;
- `source_ungrounded`: existing hallucination rejection.

Do not add NLI, RAG, another model, or a new dependency. Do not make LLM evidence
a deterministic gate.

## Verified root cause

`judge_pdf_extraction()` grounds `judgment.missing_content` only against
`pdf_text` (`pdf_judge.py:513-520`). `PdfJudgeResult.to_sidecar_dict()` then emits
the reason `"present in PDF text layer, absent from markdown"`
(`pdf_judge.py:401-404`). The page-escalation path repeats the same one-sided
proof (`pdf_judge.py:572-580`).

This is not a calibration problem. Confidence thresholds, prompt changes, and
judge cascades cannot prove candidate absence after the call. Even the
current-design steelman concluded that candidate locate is the minimum required
concession (`30-steelman.md`).

## GPT-5.6 runtime replay

The existing `ground_spans` function was run a second time against each
candidate Markdown for all 20 source-grounded quotes from PRs #284, #285, #290,
and #293. Human labels came from the forced golden replay in `00-baseline.md`.

| PR | Human-present | Candidate `exact` | Human-absent | Candidate `not_found` |
| --- | ---: | ---: | ---: | ---: |
| #284 | 2 | 2 | 3 | 3 |
| #285 | 5 | 5 | 0 | 0 |
| #290 | 5 | 5 | 0 | 0 |
| #293 | 0 | 0 | 5 | 5 |
| **Total** | **12** | **12** | **8** | **8** |

On this replay, candidate filtering raises missing-evidence precision from
8/20 (40%) to 8/8 (100%) while retaining all eight genuine omissions. It also
removes all twelve false missing quotes. This is a development-set result, not a
generalization claim.

## Why symmetric binary grounding is rejected

The same runtime check reproduced four counterexamples:

- `x >= y` in the quote versus `x <= y` in Markdown returns `exact`, because
  token and normalized guards erase the operator.
- `must not throw` versus `must throw` returns `fuzzy`.
- `P2583R3` versus `P2583R4` returns `fuzzy`.
- Plain `P1234R5` versus a Markdown link, and plain text versus `_emphasis_`,
  return `not_found` even though the content is present.

Therefore:

1. Candidate `fuzzy` must mean `ambiguous`, never proven present or absent.
2. Candidate `exact` may refute a missing claim, except when the quote contains
   semantic code/math operators and the matched raw interval does not preserve
   them.
3. Candidate `not_found` must be described honestly as failure to locate, not
   proof of absence.
4. Front-matter migration, TOC/page furniture, figures, tables, code, and math
   are exception surfaces. V1 should abstain when their cheap existing checks
   disagree, not implement a complete equivalence engine.

## Research convergence

No surveyed repository or web system supports one model judgment as proof of
PDF-to-Markdown absence. The recurring pattern is:

1. deterministic source locate;
2. deterministic candidate locate;
3. explicit abstention;
4. model adjudication only for unresolved semantics;
5. per-claim provenance;
6. evidence metrics kept separate from document verdicts.

The strongest reusable precedents are olmOCR's deterministic
presence/absence tests, Marker's localized alignment, and whisker's own
`ground_spans`, `ground_page_quotes`, `_best_match`, raw/math surfaces, and table
parsers. The code required for the first reliable filter already exists in
whisker.

## Recommended implementation

### Step 1 - honest two-sided filtering

Adapt existing files only:

- `tapetum_llm/grounding.py`: add a small candidate-classification helper around
  `ground_spans`; exact, fuzzy, and dropped remain distinct.
- `tapetum_llm/pdf_judge.py`: run candidate classification after source
  grounding in both monolith and page-escalation paths.
- `tests/test_tapetum_llm.py`: pin the 20-quote behavior and adversarial
  operator, negation, revision, Markdown-link, emphasis, front-matter, table,
  code, and math cases.
- `packages/whisker/src/whisker/CLAUDE.md`: document the evidence states and why
  candidate absence is not called proof.

No new production module and no dependency are justified.

Policy:

- `exact` candidate match, with semantic-operator parity when applicable:
  remove from `missing_content`, count as `present_in_candidate`.
- `fuzzy` candidate match: remove from asserted missing evidence and report as
  `ambiguous`.
- no candidate match: retain the quote as `candidate_not_found`, not
  `verified_missing`.
- source miss: preserve existing `ungrounded_dropped`.
- sort persisted evidence deterministically.
- bump the sidecar schema version.

Do not automatically rewrite the LLM verdict in Step 1. PRs #285 and #290 had
false missing quotes but independent real defects in their reasoning. Evidence
cleanup and verdict calibration are separate decisions.

### Step 2 - conservative surface guards

Before broad use, add only the guards demonstrated necessary:

- code/operator quote: compare the raw matched interval and preserve semantic
  operators; otherwise `ambiguous`;
- Markdown link/emphasis: use a shallow Markdown-aware normalization that keeps
  operators;
- front matter, TOC/furniture, figures, tables, and math: reuse existing
  parsers/surfaces when a cheap decisive check exists, otherwise `ambiguous`.

Do not route whole documents through global `partial_ratio` as a candidate
absence oracle. Do not add block Hungarian matching or NLI to the hot path.

### Step 3 - measured acceptance

First gate the implementation on:

- replay precision: at least 90%;
- genuine-absence recall: at least 7/8;
- all twelve known false missing quotes suppressed or abstained;
- all operator/negation/revision adversarial cases prevented from becoming
  trusted binary evidence;
- deterministic and LLM verdict behavior unchanged unless a separate,
  explicitly reviewed policy change is made.

Then lock a holdout before threshold tuning: 48 verified anchors across prose,
sanctioned reformats, code/xrefs, tables, and math/Unicode, separate from the
20-quote development replay. Report evidence precision, absence recall,
false-missing rate, and abstention by stratum. Do not fold these into the
document-level verdict score.

## Rejected approaches

- **Prompt-only fix:** cannot verify post-hoc absence.
- **Confidence calibration:** calibrates a model score, not candidate presence.
- **Binary symmetric `ground_spans`:** fails reproduced operator, negation,
  revision, link, and emphasis cases.
- **NLI/RAG/second judge in V1:** added latency and nondeterminism without
  evidence of lift on the replay.
- **New verifier subsystem or large claim schema:** duplicates existing
  machinery before the minimal filter is measured.
- **Automatic verdict demotion when quotes disappear:** confuses evidence
  reliability with independent structural findings.
- **LLM evidence as a gate:** contradicts whisker's advisory-only architecture.

## Model boundary and open questions

This recommendation should be revised if the implementation fails to retain at
least seven of the eight genuine replay omissions, or if the locked holdout
cannot reach 85% evidence precision without surface-specific complexity.

Still unknown:

- how often production quotes fall into code/math/table exception surfaces;
- whether shallow Markdown-aware normalization resolves links and emphasis
  without new false refutations;
- whether page-level candidate localization adds measurable precision beyond
  full-candidate exact matching;
- whether any later verdict policy should react to evidence disposition.

Those questions require the labeled holdout, not another unmeasured model layer.
