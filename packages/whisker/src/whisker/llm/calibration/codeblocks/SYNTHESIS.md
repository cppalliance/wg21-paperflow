# LLM-readability codeblocks synthesis (reconstructed)

> **Provenance notice (2026-09-08).** The original
> `research/llm-readability-codeblocks/SYNTHESIS.md` was never committed and
> is lost (see the reconstruction notice in
> [../tables/00-baseline.md](../tables/00-baseline.md)). It was cited as
> `SYNTHESIS.md:C<n>` by every codeblock rule C1-C10, the contract header,
> the `diagram-as-cpp` weakness, and the `identifier-line-lookup` probe in
> `det/llm_readability/deepseek-v4/codeblocks/rules.toml`. This file is the
> honest reconstruction at the calibration home: per rule, what the lost
> synthesis contributed and which evidence survives. It restates no rule
> text; the rules.toml remains the single normative copy of C1-C10, and the
> punch-list locks plus the tapetum `code_boundary` lane history (v15-v19,
> PR 394 before/after) live in
> [CODEBLOCK-CALIBRATION.md](CODEBLOCK-CALIBRATION.md) next to this file.

What the original was: the synthesis of the codeblock readability research,
from which rules C1-C10 were distilled. The rule text, thresholds, and
rationales survive verbatim in rules.toml; lost is the narrative research
layer. The measured before/after behavior of the advisory lane is not lost:
it is locked in CODEBLOCK-CALIBRATION.md and reproduced by the hermetic
fixtures in `tests/det/test_llm_readability_codeblocks.py`.

## C1

Contribution: the observation that an unfenced listing collapses into
surrounding prose and loses line identity, indent, and program-versus-paper
boundaries for a reading model. Surviving: the deterministic
`listing_is_fenced` check, `TestListingSplit` (HEAD p0533r9 evidence:
ellipsis-only fence fires C1), and the v15-v17 PR 394 locks in
CODEBLOCK-CALIBRATION.md.

## C2

Contribution: empty fences as phantom listings that waste judge attention and
hide a dropped body. Surviving: the `empty_fence` check; the `<ins>`/`<del>`
wrapper carve-out survives in the rule text.

## C3

Contribution: reflow destroys line-oriented lookup; indent is C++ meaning.
One source line is one markdown line. Surviving: the `code_no_reflow`
source-compare check and its trailing-newline carve-out.

## C4

Contribution: the survival-token set (`constexpr`, `consteval`, `requires`,
`concept`) as the load-bearing grammar of modern C++ wording that must stay
inside its fence on the same relative line. Surviving: the named threshold
`survival_tokens` and the `survival_tokens` check.

## C5

Contribution: fence boundaries follow source fonts, but a source-compare that
ignores reflow false-fails papers whose only defect is wrap, so C5 abstains
when the line maps disagree. Surviving: the `fence_boundary_align` check with
its `not_evaluated` abstention path; HTML sources without a font map stay
unsupported.

## C6

Contribution: post-2026 emit dropped wording fenced divs; `<ins>`/`<del>`
must remain literal, unescaped tags on the tokens they mark, inside the
fence. Surviving: the `wording_in_fence` check and
`TestFalseWordingOnComment` (BASE p2040r0 evidence: `<ins>`/`<del>` around a
comment fires C6).

## C7

Contribution: font is not kind. A monospaced font does not by itself make a
listing; spec-element prefixes (`Mandates:`, `Effects:`, `Remarks:`, ...)
stay outside the fence, and body-font prose inside a fence is a defect.
Surviving: the `font_is_not_kind` check and `TestHeadingInFence` (BASE
p0533r9 evidence: lettered heading inside a fence fires C7).

## C8

Contribution: one construct per listing. A listing inside a table cell is
owned by the tables contract rule R11; double-scoring a cell `<pre>`
produces contradictory verdicts. Surviving: the `cell_listing_excluded`
check.

## C9

Contribution: ASCII trees, SIMD diagrams, flowcharts, and display-grammar
productions are not `cpp`. HTML conversion already leaves these unlabeled;
PDF still tags them. Surviving: the `diagram_not_cpp` check and the
`diagram-as-cpp` weakness naming P4016R0 and P4100R1 in the pre-golden
corpus.

## C10

Contribution: a listing that cannot be addressed by identifier and line is
not usable as a citation target, even if the fence parses. Surviving: the
`code_identifier_probe` certification check and the required probe
`identifier-line-lookup` (positional lookup with a corrupted control that
must invert). Status pending until a certified profile exists;
candidate-only runs leave C10 `not_evaluated`.

## Calibration history that survives in full

The advisory tapetum `code_boundary` lane calibration (v15 through v19) with
its PR 394 before/after evidence on p0533r9 and p2040r0 is preserved in
[CODEBLOCK-CALIBRATION.md](CODEBLOCK-CALIBRATION.md). The deterministic
control-paper gate is `TestNewCodeFlagsControlPapers` (P0876R23 / P3596R0),
which must stay green through every calibration round.
