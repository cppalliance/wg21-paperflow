# PR #286 and PR #295: source-aware diagnostic misses

## Current revalidation, 2026-07-22

This section is the current diagnosis. Sections 1 through 11 below preserve the
2026-07-21 PR #286 snapshot because its earlier candidate is still useful as a
development replay. They must not be read as the diagnosis of the current PR
heads.

Two independent golden reviews reproduced the same system-level failure:
Whisker's final disposition was conservative, but neither the deterministic nor
the source-aware LLM lane identified the real source-backed defects. The two
papers exercise different source types and different failure mechanisms:

- PR #286, P1068R11, is a 15-page PDF. Its current defect is a wrapped table-cell
  transcription error on PDF pages 8 and 9.
- PR #295, P3953R0, is HTML. Its current defects include retained
  `span.secno` heading labels and rendered-Markdown fidelity losses.

The result is not evidence that `deepseek-v4-pro` alone is bad. Several misses
occurred before the unit model could inspect the relevant source:

- PR #286 pages 8 and 9 were routed, then displaced by the five-unit budget.
- PR #295 routing included a unit ID for which no source packet was available.
- HTML outline preprocessing preserved source-only `span.secno` text, so the
  metadata prompt did not encode the golden contract's required normalization.

There are also model/prompt-level misses:

- PR #286 generated an inconsistent false heading-number claim on page 13.
- PR #295 emitted zero defect claims overall. The manually identified target
  sections were not among the checked source packets, so this is an end-to-end
  routing/coverage miss, not evidence that a unit model false-cleared those
  particular defects.

### Input identity

The review fetched each PR head directly from
`https://github.com/cppalliance/wg21-paperflow.git`, extracted files from
`FETCH_HEAD` byte-faithfully, verified Git blob identity, and staged the source
and candidate in a fresh temporary `SqliteBackend`. It did not checkout either
PR or use the real `WG21_DATA_DIR`.

| Review | PR head | Source | Source SHA-256 | Candidate ideal SHA-256 |
|---|---|---|---|---|
| #286 | `ffa54f8f212e20c7b681fbdc6aae712841cf8576` | P1068R11 PDF | `a686518789b75fc98c9ad2747812180b2df223ce9e7732a409c4c776d7bb0481` | `e79079f289eb794c4b42eb0531133d9fc02100b8cfc06f97cfd607538f34e4dd` |
| #295 | `0bd71bf90d69bb675483c75ca33bfa85c7647264` | P3953R0 HTML | `2aa5d2dda5b7d1c792427b63cc63a76231355103a88fd9dedcde90aa5157c9a8` | `f4988f05cf5a01a61f921932b51b5cbef358460cffacf207c35f12f377da3f28` |

The Whisker executions used the current local code at
`51cb704610220d31c9d5e078b1350c1b37a8714a`. The checkout was dirty before the
review and the dirty diff was not captured as a reproducibility artifact.
Runtime code identity is therefore the base commit plus an incompletely
identified pre-existing dirty working tree. The PRs are golden-only, so running
local Whisker rather than PR code is intentional.

### Validation method

#### P1068R11 PDF

1. Rendered all 15 source pages at 144 DPI and visually inspected every page.
2. Compared the complete source structure with the candidate: front matter,
   heading map, lists, code boundaries, six poll tables, figure, references,
   wording, and chrome.
3. Resolved disputed findings with PyMuPDF font and geometry evidence.
4. Verified the poll table's vertical boundaries at x =
   `72.5, 95.5, 110.5, 127.5, 144.5, 167.5`.
5. Verified `S` and `F` at x = `77.25` are vertically wrapped inside the first
   cell, while the second-column `F` is at x = `100.5`. The last cell similarly
   wraps `S` and `A`.
6. Rejected two false manual hypotheses: green wording additions do not require
   `<ins>`/`<del>` ghosts, and the page-11 `std::ranges::copy` line is Calibri
   body text, not a monospace listing.
7. Reproduced deterministic Whisker, source-aware Whisker, fusion, local tomd
   conversion, bidirectional bench, and `tomd bless`.

The corrected ground truth is one blocking defect group with six instances:
candidate lines 382, 394, 405, 415, 425, and 433 use
`|S|F|N|A|SA|`; the source uses `|SF|F|N|A|SA|`.

Four additional Markdown-quality groups were recorded as minor: raw
`<random>`, trailing whitespace, hard-wrapped prose, and loose revision-history
lists. They are not the table blocker.

#### P3953R0 HTML

1. Parsed the source DOM directly; HTML, not tomd output, was authoritative.
2. Built a complete heading map and compared source tags, `span.secno`
   children, candidate levels, and candidate text.
3. Counted and compared all lists, `<pre>` blocks, links, description-list
   entries, tables, images, and wording elements.
4. Verified rendered CommonMark semantics where raw source characters can be
   consumed as Markdown syntax.
5. Reproduced deterministic Whisker, source-aware Whisker, fusion, local tomd
   conversion, bidirectional bench, and `tomd bless`.

The structure-only `tomd-review` ground truth was:

1. Four H2s retain source `span.secno` labels: `1.` through `4.`. The golden
   contract requires stripping structural section labels while preserving the
   H2 levels and semantic heading text.

The broader `/pr-golden-review` fidelity pass also recorded four observations
outside the structure-only skill:

1. `` `constexpr`contexts `` loses a source-significant separating space.
2. Literal grave accents visible in the P3391 citation are consumed as
   Markdown code delimiters.
3. The epigraph's explicit `<br>` is flattened.
4. Two `<cite>` units lose citation emphasis.

The two `cpp` fences self-flagged in the PR body were verified fixed.

### Reproduction commands

Both papers were staged as source plus candidate ideal in separate temporary
paperstore workspaces, then run with:

```text
uv run --package whisker whisker <PID> --workspace <fresh-temp-workspace> --json
uv run --package whisker whisker-tapetum-llm <PID> --workspace <fresh-temp-workspace> --inspect --trace --debug
```

The local converter and baseline checks used
`tomd.api.convert_paper_full`, `whisker.bench.run_bench` in both directions,
and `tomd bless <PID>` against a temporary golden directory.

### Observed results

#### PR #286, P1068R11

- Deterministic verdict: `pass`.
- All six deterministic gates: pass.
- QA: `100`.
- Coverage/drift: `0.9334 / 0.0509`.
- Unigram coverage/drift: `0.9758 / 0.0079`.
- Source-aware verdict: `review`, confidence `0.98`.
- Metadata/outline: `pass`.
- Routed pages: 1, 2, 3, 4, 5, 6, 8, 9, and 13.
- Checked pages: 1, 2, 3, 4, and 13.
- Unchecked pages: 5, 6, 8, and 9.
- Generated defects: one page-13 heading claim.
- Evidence disposition: `ambiguous=1`; accepted defect groups: 0.
- Fusion: `review` by `source_aware_review_cap`.
- PDF trace: absent despite `--trace`; debug was present.

The real blocker was on pages 8 and 9. Both pages were routed and both were
left unchecked by `MAX_UNIT_CHECKS = 5`. The model therefore had no chance to
detect the table defect in a unit call. The page-13 call instead claimed that
stripped `X.`, `XI.`, and `XII.` labels were missing, contradicting both the
golden contract and the metadata/outline `pass`.

Confusion accounting against the blocking ground truth:

- true-positive groups: 0;
- false-negative groups: 1, containing six table-header instances;
- generated false-positive groups: 1;
- accepted false-positive groups after evidence verification: 0.

The four Markdown-quality observations were not counted as expected LLM defect
groups because they are outside the structure-only review contract.

#### PR #295, P3953R0

- Deterministic verdict: `review`.
- All six deterministic gates: pass.
- QA: `100`.
- Coverage/drift: `0.9884 / 0.0000`.
- Reference NID/TEDS/MHS/overall:
  `0.8081 / 1.0000 / 0.7000 / 0.8360`.
- Source-aware verdict: `review`, confidence `1.0`.
- Metadata/outline: `pass`.
- Checked units: `section:1` and `section:6`.
- Unchecked unit: `section:0`; no source packet was available for that routed
  ID in this execution.
- Generated and accepted defect groups: 0.
- Fusion: `review` by `source_aware_review_cap`.
- Schema failures/retries: 0/0.

The three routing signals were not real candidate defects. Two arose from
title/date content correctly moved into YAML; one was polluted by embedded
HTML script text. The final `review` was therefore conservative for routing
coverage, not because a real defect was found.

Confusion accounting against manual ground truth:

- true-positive groups: 0;
- accepted false-positive groups: 0;
- routing false positives: 3;
- structure-only false-negative groups: 1;
- high-severity heading-label recall: 0/1 groups and 0/4 affected headings.

Against the broader golden-fidelity observations, document-level recall was
0/5 groups. That extended number must not be confused with the structure-only
`tomd-review` score.

The metadata/outline `pass` is the central failure. Current
`html_outline.py` collects all heading inner text, including `span.secno`.
Without deterministic contract normalization, source and candidate both
contained the same labels, so the prompt was not given the normalized expected
outline. This is primarily a preprocessing/contract bug, not proof that the
model independently chose to violate a rule it was never encoded.

The unit lane emitted no claims for evidence verification. The target sections
were not checked, so this execution cannot isolate whether a correctly routed
unit call would have found the broader fidelity observations.

### What the two-paper validation proves

1. A fused `review` is not proof that Whisker found a real defect.
2. Zero evidence dispositions can mean zero generated claims, not successful
   validation.
3. Correct risk routing is insufficient when the cap leaves the real units
   unchecked.
4. LLM outline comparison cannot enforce normalization rules omitted from
   deterministic preprocessing.
5. High text and structural similarity can hide a wrong golden because current
   tomd output and the candidate can share the same defect.
6. Evidence verification protects precision after claim generation; it cannot
   recover defects that routing or the unit judge never claims.

### Revised prioritized fixes

#### P0. Encode heading-label policy deterministically

Normalize source outlines before routing and metadata comparison:

- strip leading Roman, alphabetic, and decimal labels when source evidence
  identifies them as structural section numbering;
- strip known source-only numbering children such as HTML `span.secno`;
- evaluate `span.header-section-number` fixtures before enabling the same rule
  for that producer pattern;
- strip self-link/chrome children;
- preserve heading level and semantic title;
- preserve numbers that are semantic content rather than section labels.

Normalize and extend the deterministic source-outline-to-candidate-outline
comparison already present in `source_router.py`. Do not ask the LLM to infer a
project contract that preprocessing can encode exactly.

#### P0. Add source-aware table-cell comparison

`PageUnit.has_tables` and `SectionUnit.has_tables` exist, but table presence is
not used by the router and there is no source-aware cell-grid comparison in
`tapetum_llm`.

For HTML, compare parsed source table cells with the localized candidate table.
For PDF, use text position and detected column boundaries to construct a
review-oriented cell packet. The P1068R11 replay must distinguish vertically
wrapped `SF` from a separate `S` cell.

#### P0. Fix unit scheduling under a bounded budget

Current selection sorts by severity and lexical `unit_id`, then takes the first
five units. This permits `page:13` to sort before `page:2` and lets noisy
same-severity heading signals consume the budget.

- sort numeric unit IDs numerically;
- rank signal specificity before lexical identity;
- reserve capacity for distinct structural signal classes;
- record selected and displaced units with reasons;
- either check every routed unit or make cap displacement explicit and
  severity-aware.

Raising the cap alone is not a complete fix.

#### P0. Clean and align HTML source packets

- Exclude `<script>` and `<style>` content from section text.
- Ensure every routed unit ID resolves to exactly one source packet.
- Test outline/section index invariants.
- Treat a missing packet as an internal routing error with a diagnostic reason,
  not as an unexplained unchecked unit.

`section:0` is a valid first section ID in current code. The observed bug is
that this routed ID had no packet in the execution, not that the ID itself is
invalid.

#### P1. Compare rendered Markdown semantics

This is broader than the structure-only `tomd-review` contract. If the
source-aware lane is intended to validate full golden fidelity, add bounded
deterministic or source-aware checks for:

- text adjacency around inline code;
- literal grave accents consumed as Markdown delimiters;
- raw HTML-like tokens such as `<random>`;
- explicit source line breaks when structurally meaningful;
- `<cite>`, `<em>`, `<i>`, and `<var>` preservation.

Raw-token equality is insufficient because source characters can survive in
Markdown bytes while disappearing or changing role when rendered.

#### P1. Make fusion reasons machine-readable

Keep the conservative `source_aware_review_cap`, but persist distinct
subreasons such as `metadata_nonpass`, `coverage_incomplete`,
`unchecked_units`, `failed_units`, and `verified_defects`. Operators must be
able to distinguish "defect found" from "inspection incomplete".

#### P1. Wire PDF trace end to end

The text path forwards `trace`; the PDF call to `judge_pdf_extraction` does
not. The historical and current P1068R11 PDF runs both reproduced the missing
trace artifact. Add the trace parameter, record every executed PDF step, and
write the artifact even when a later step fails.

### Current code anchors

- `tapetum_llm/constants.py:223-226`: `MAX_UNIT_CHECKS = 5`.
- `tapetum_llm/unit_judge.py:225-252`: severity/lexical unit sorting, cap
  selection, and missing-packet handling.
- `tapetum_llm/unit_judge.py:305-323`: incomplete coverage forces `review`.
- `tapetum_llm/html_outline.py:66-81`: heading text collects all descendant
  data without a `secno` filter.
- `tapetum_llm/html_outline.py:147-172`: section extraction records table
  presence but also admits script text because scripts are not excluded.
- `tapetum_llm/source_router.py:236-316`: HTML routing has no source table-cell
  comparison.
- `tapetum_llm/fusion.py:183-196`: metadata and coverage collapse into the
  single `source_aware_review_cap` decision.
- `tapetum_llm/cli.py:1114-1118`: PDF dispatch forwards debug but not trace.
- `tapetum_llm/cli.py:1173-1178`: the text path forwards trace, proving the
  current asymmetry.

### Current-head acceptance tests

PR #286 and PR #295 are development replay cases, not holdout.

For the exact current PR #286 source and candidate hashes above:

- report one table-header defect group with six affected instances;
- localize it to pages 8 and 9 and the six candidate table headers;
- verify source `SF`, candidate `S`;
- do not reintroduce rejected `<ins>`/`<del>` or page-11 fence findings;
- do not flag correctly stripped Roman/alphabetic section labels;
- do not count a coverage-only fused `review` as defect detection.

For the exact current PR #295 source and candidate hashes above:

- report the four retained structural heading labels as one defect group;
- report affected count 4 and preserve all H2 levels;
- keep the two `cpp` fences clean;
- do not flag the source's intentional `runtime_format` call;
- do not require absent `intent` metadata.

Extended golden-fidelity acceptance, if that scope is retained for the
source-aware lane:

- detect the missing space after inline code;
- detect source-visible grave accents consumed as Markdown delimiters;
- detect the explicit epigraph break and two citation-emphasis losses.

Shared tests:

- source outline normalization strips structural labels but preserves semantic
  numeric text;
- script/style payloads never enter routing or unit packets;
- every selected unit has a packet;
- cap overflow records selected/displaced units and reasons;
- zero generated claims is distinct from zero rejected claims;
- fusion subreasons distinguish coverage from verified defects;
- `--trace` on the PDF path writes a trace artifact.

### Current artifact inventory

PR #286:

- review root:
  `C:\Users\sabo2\AppData\Local\Temp\pr286-review\run-20260722-20260722-125805-5958397`;
- consolidated review:
  `PR286-golden-review-p1068r11-current.md`;
- corrected manual ground truth:
  `corrected-manual-ground-truth.md` and `.json`;
- rendered source pages:
  `manual-source-fidelity\p1068r11-144dpi`;
- runtime root:
  `whisker-fresh-20260722-130231-410ef679`;
- deterministic sidecar:
  `whisker\det\p1068r11.whisker.json`;
- source-aware sidecar:
  `whisker\llm\p1068r11.whisker.tapetum.json`;
- inspection report:
  `whisker\llm\tapetum-inspect.md`;
- debug transcript:
  `paperstore\p1068r11.debug.tapetum_llm.md`.

PR #295:

- review root:
  `C:\Users\sabo2\AppData\Local\Temp\pr295-review\run-20260722-131832019-f5c74e13`;
- consolidated review:
  `PR295-golden-review-p3953r0.md`;
- manual ground truth:
  `manual-source-fidelity.md` and `.json`;
- runtime root:
  `C:\Users\sabo2\AppData\Local\Temp\whisker-pr295-p3953r0-20260722T112239792Z-d8ddb879`;
- deterministic sidecar:
  `whisker\det\p3953r0.whisker.json`;
- source-aware sidecar:
  `whisker\llm\p3953r0.whisker.tapetum.json`;
- inspection report:
  `whisker\llm\tapetum-inspect.md`;
- debug transcript:
  `paperstore\p3953r0.debug.tapetum_llm.md`.

## 1. Status, severity, and scope

- **Status:** Open architecture bug and improvement backlog item.
- **Severity:** High for golden-validation correctness. The system did not fail operationally, but it failed to diagnose four source-backed defect classes in a proposed human ideal.
- **Owner area:** `packages/whisker`, primarily deterministic scoring and `whisker.tapetum_llm` PDF routing, unit judging, fusion reporting, observability, and ideal-verifier integration.
- **Discovered:** 2026-07-21 during the PR #286 review.
- **Affected review head:** `757ec47cf9938ad75b305c27278b260727c78165`.
- **Affected source:** P1068R11, original 15-page PDF, SHA-256 `a686518789b75fc98c9ad2747812180b2df223ce9e7732a409c4c776d7bb0481`.
- **Affected candidate ideal:** PR ideal SHA-256 `cdac61b10cc0cf5c8c9b9d19d51a7c87c232224864cf4cc6a52b1cf7eac79860`.
- **Observed Whisker schema:** deterministic schema 4, Tapetum sidecar schema 7, fusion schema 4, PDF lane version 8.
- **Observed model:** `alliance-pod/deepseek-v4-pro` through the PDF text-layer judge.

**Model boundary:** This diagnosis should be revised if a replay against the same source and candidate bytes shows that the verified defects are absent, or if the current routing, unit-judge, fusion, trace, or ideal-discovery code differs materially from the files cited below. A different model may change unit accuracy, but it does not remove the deterministic, routing-budget, observability, or branchless ideal-discovery gaps demonstrated here.

This report is a backlog artifact. It records observed behavior, causal boundaries, fix options, and acceptance tests. It does not claim that any fix has been implemented.

## 2. Executive summary

PR #286 contains four verified classes of defects in the proposed P1068R11 ideal:

1. Normative Effects text on PDF page 7 loses `N>.`.
2. Two ordered-list groups on page 10 collapse from 2 and 3 items to 1 and 1 items.
3. Three visually distinct subordinate design headings on pages 9 and 10 flatten into prose.
4. Inline code on pages 12 and 13 renders literal backtick debris around the two `std::ranges::generate_random` examples.

Deterministic Whisker exited 0 with `pass`, all six gates passing, QA 100, and no flags. That result is explainable under the current contract: token-normalized agreement is insensitive to small punctuation/operator loss, parseability gates do not compare list cardinality, text-only metrics do not reconstruct visual heading tiers, and normalized token scoring does not test rendered Markdown delimiter integrity.

The source-aware LLM lane also completed successfully but found no real defect. The whole-document judge said the conversion was faithful. The page screen flagged 0 of 15 pages. Routing emitted nine noisy `heading_drift` signals, then the `MAX_UNIT_CHECKS = 5` budget selected pages 1, 13, 2, 3, and 4. Pages 7 and 10 were never routed, page 9 was routed but left unchecked, and the page 13 unit check false-cleared malformed inline code. All five unit checks passed, `defect_groups` was empty, and all evidence-disposition counts were zero.

Fusion returned `review` through `source_aware_review_cap`. This was conservative triage caused by incomplete unit coverage and a metadata/outline `review`, not diagnosis of any verified defect. The fused result was directionally safer than the deterministic pass, but it cannot be cited as successful defect detection.

**Verdict:** architecture false-clear and diagnostic miss, not an operational failure. The commands exited 0, structured retry recovered, debug evidence was written, and fusion behaved as coded. The architecture still allowed a defective golden candidate to receive a clean deterministic diagnosis and an LLM review with zero true findings.

## 3. Reproduction

### 3.1 Inputs

Use a fresh temporary paperstore workspace containing:

- the original P1068R11 PDF with SHA-256 `a686518789b75fc98c9ad2747812180b2df223ce9e7732a409c4c776d7bb0481`;
- the PR-head ideal staged as the candidate Markdown, with source bytes SHA-256 `cdac61b10cc0cf5c8c9b9d19d51a7c87c232224864cf4cc6a52b1cf7eac79860`;
- reviewed PR head `757ec47cf9938ad75b305c27278b260727c78165`.

On Windows, paperstore persistence translated the ideal's LF newlines to CRLF. The staged Markdown hash became `5be810cb4d467e95661c1dcbd3b46f463e082ef5658d6deb9d7747fe973462b6`, while universal-newline text remained identical. The authoritative PR-file hash remains `cdac61...`.

### 3.2 Deterministic command

```text
uv run --package whisker whisker p1068r11 --workspace <fresh-temp-workspace> --json
```

Observed:

- exit code: `0`;
- verdict: `pass`;
- coverage: `0.9555`;
- drift: `0.0333`;
- unigram coverage: `0.9807`;
- unigram drift: `0.0078`;
- QA score: `100`;
- missing regions: `0`;
- extra regions: `0`;
- soft flags: none;
- hard flags: none.

All gates passed:

- `non_empty`;
- `front_matter_valid`;
- `heading_monotone`;
- `no_empty_code`;
- `no_empty_table`;
- `no_toc_leak`.

The markitdown advisory panel reported NID `0.9569`, TEDS `0.1294`, MHS `0.0417`, and overall `0.3760`. Those weak-oracle structural values did not create a verdict flag under the current contract.

### 3.3 Source-aware command

```text
uv run --package whisker whisker-tapetum-llm p1068r11 --workspace <fresh-temp-workspace> --inspect --trace --debug
```

Observed:

- exit code: `0`;
- lane: `pdf_textlayer_judge`;
- service/model: `alliance-pod/deepseek-v4-pro`;
- whole-document judgment: `pass`;
- final suggested verdict: `review`;
- confidence: `0.98`, self-reported and uncalibrated;
- text-layer NID: `0.9587`;
- content recall: `0.9940`;
- page screen: `0 / 15` flagged;
- page escalations: none;
- risk signals: 9, all medium `heading_drift`;
- unit checks: 5 passed;
- defect groups: 0;
- evidence dispositions: present 0, candidate-not-found 0, ambiguous 0, source-ungrounded 0;
- fusion: `review` by `source_aware_review_cap`;
- one schema-invalid unit result retried successfully;
- debug artifact: generated;
- PDF trace artifact: not generated.

## 4. Expected versus actual behavior

### Expected

Golden validation should not produce a clean diagnostic for this candidate. At least one independent lane should surface the concrete defect types and locations, or a deterministic source-structural tripwire should force a targeted review that identifies them.

The expected diagnostic is not necessarily a hard gate. The LLM remains advisory. A correct outcome can be:

- deterministic `review` with specific source-structural flags;
- source-aware `review` with grounded defect groups;
- or both.

The diagnostic must distinguish "coverage incomplete" from "verified defect found."

### Actual

- Deterministic Whisker returned `pass` with no flags.
- The whole-document PDF judge falsely stated: `No content is missing or corrupted`.
- Metadata/outline returned `review` while narrating false claims that IX subheadings were added and `Notices & Disclaimers` was absent from the source outline. Both are present in the PDF.
- The router spent its five-check budget on pages 1, 13, 2, 3, and 4.
- Pages 7 and 10, which contain three of the four verified defect classes, were not routed.
- Page 9 was routed but not checked.
- Page 13 was checked and false-cleared despite malformed inline code.
- No claim reached two-sided evidence verification.
- Fusion returned `review` only because source-aware coverage was incomplete and metadata was non-pass.

This is a false-clear at the diagnostic level even though the final fused triage label was `review`.

## 5. Ground-truth defect matrix

| Source page | Candidate location | Verified defect | Deterministic outcome | Routing outcome | Unit outcome |
|---|---|---|---|---|---|
| 7 | PR ideal near line 350, second distribution Effects bullet | Normative type loses trailing `N>.` from `span<invoke_result_t<D&, G&>, N>.` | `pass`; page recall `1.0`; no flag | Page 7 not routed | No unit check |
| 9 | PR ideal near line 447 | `Library only solution (buffer under the hood)` flattened into following prose | `pass`; heading gate remains syntactically monotone | Page 9 received medium `heading_drift`, but fell beyond the five-unit cap | Unchecked |
| 10 | PR ideal near lines 457 and 469 | Two ordered-list groups collapse from 2+3 items to 1+1 | `pass`; remaining list syntax is valid | Page 10 not routed | No unit check |
| 10 | PR ideal near lines 459 and 475 | `Library only solution (overloads for std::ranges::generate)` and `Compiler+library solution` flattened into prose | `pass`; no source-relative heading-tier check | Page 10 not routed | No unit check |
| 12 | PR ideal near line 543 | `std::ranges::generate_random(range, g);` contains literal delimiter debris when rendered | `pass`; normalized token agreement remains high | Page 12 not routed | No unit check |
| 13 | PR ideal near line 561 | `std::ranges::generate_random(range, g, d);` contains literal delimiter debris when rendered | `pass`; page recall `0.9974`; no flag | Page 13 routed for unrelated heading noise | Unit returned `pass` at confidence `1.0` and discussed headings/URLs, not malformed inline code |

The three heading defects are one defect class with three instances. The two list collapses are two structural groups containing five intended source items. The inline-code corruption has two instances.

### Excluded and retracted claims

The following historical classifications apply only where stated:

- absence of `<ins>`, `<del>`, or `:::wording` from a human ideal;
- the previously claimed merged Remarks/Note/Returns defect.

Human ideals intentionally remove converter wording ghosts. On 2026-07-21,
heading-prefix retention was classified as clean; the 2026-07-22 revalidation
superseded that classification. It applied the contract's leading
section-number rule to structural Roman, alphabetic, and HTML `span.secno`
labels while preserving heading level and semantic title. Under that reviewed
interpretation, retained structural prefixes are defects. Numeric text that is
part of the semantic title remains valid. The Remarks/Note/Returns claim was
retracted after source reinspection.

## 6. Root-cause tree

### 6.1 Deterministic lane: contract blind spots, not runtime malfunction

`packages/whisker/src/whisker/constants.py` defines the deterministic content gate around unigram coverage, with reading-order coverage reported separately. `packages/whisker/src/whisker/golden_ideals.py::score_against_ideal` can compare candidate and canonical ideal using NID, TEDS, MHS, and content recall, but no canonical P1068R11 ideal was discoverable in this branchless PR setup.

Each defect escaped for a distinct reason:

- **Missing `N>.`:** punctuation/operator-only loss has little or no effect on word-token recall, and normalization reduces its effect on text similarity.
- **Collapsed lists:** the Markdown still contains ordered-list syntax, so parseability and non-empty structure gates remain satisfied. No source-relative list cardinality or item-boundary comparison runs in the reference-free path.
- **Flattened subordinate headings:** the candidate heading sequence remains monotone. Text-only token metrics preserve the heading words even when their visual/structural role is lost.
- **Literal backtick debris:** the underlying words survive normalized scoring. Existing gates test empty code blocks, not malformed inline-code rendering or delimiter residue.

The deterministic result is therefore explainable by the current contract. The defect is the absence of a source-structural lane or targeted replay tripwire, not that unigram gates failed to infer visual semantics they were never designed to measure.

### 6.2 Routing signal precision: noisy headings consume the budget

`packages/whisker/src/whisker/tapetum_llm/source_router.py::route_pdf_units` compares every `PageUnit.heading_candidates` entry against candidate Markdown heading keys. The observed extraction supplied many prose fragments and split section prefixes as heading candidates. This created nine medium `heading_drift` page signals, including very long prose-heavy details on pages 4 through 6.

`packages/whisker/src/whisker/tapetum_llm/unit_judge.py::run_unit_checks` sorts by severity, then lexical `unit_id`, signal type, and detail. All observed signals had equal medium severity. Grouped unit IDs were selected as the first five under `MAX_UNIT_CHECKS = 5`, yielding:

```text
page:1, page:13, page:2, page:3, page:4
```

Lexical ordering places `page:13` between `page:1` and `page:2`. The cap then left pages 5, 6, 8, and 9 unchecked. Page 10 had no signal at all.

The router correctly failed closed at the coverage level, but low-precision signals displaced higher-value source regions. Coverage caution cannot substitute for useful localization.

### 6.3 Routing signal recall: four defect mechanisms are outside current triggers

The PDF router currently emits signals for:

- document-wide tracked C++ keyword deficits;
- low page content recall;
- missing captions;
- large-font lines absent from Markdown headings.

That surface misses:

- punctuation/operator-only normative loss;
- ordered-list item-boundary collapse where all words remain present;
- subordinate visual heading tiers that are not reliably represented by current `heading_candidates`;
- malformed Markdown inline delimiters where source and candidate words remain present.

The page screen in `packages/whisker/src/whisker/tapetum_llm/pdf_judge.py::screen_pages` uses `content_recall` with `PAGE_RECALL_FLOOR = 0.90`. Every page cleared it. Page 7 scored `1.0`; page 13 scored `0.9974`. This screen is appropriate for localized content absence, but it cannot detect source-to-Markdown role changes or delimiter corruption.

### 6.4 Unit quality: a selected defective page was false-cleared

`packages/whisker/src/whisker/tapetum_llm/unit_judge.py::_check_one_unit` sends one source page, the full candidate document, and the routing detail. `UNIT_CHECK_SYSTEM_PROMPT` names `punctuation_loss` and `code_loss`, but the observed page 13 call focused on the unrelated heading signal and returned:

```text
Headings X, XI, XII are correctly rendered as level-2 headings. Content, including URLs, is faithfully preserved.
```

It did not inspect the malformed inline-code rendering. `packages/whisker/src/whisker/tapetum_llm/models.py::UnitCheck.verdict_matches_defects` enforces internal consistency, not external completeness: a `pass` with an empty defect list is schema-valid. The successful schema retry proves output recovery, not judgment correctness.

This is a distinct unit-quality bug. Better routing alone would not fix the page 13 miss.

### 6.5 Evidence and aggregation: no claims entered the verifier

`packages/whisker/src/whisker/tapetum_llm/unit_judge.py::verify_unit_evidence` and `_aggregate_defects` only operate on defects the model emits. Every unit emitted an empty defect list, so:

- no source quote was grounded;
- no candidate absence or ambiguity was classified;
- no defect group was built;
- two-sided evidence had nothing to verify.

The zero disposition counts are not evidence of a clean candidate. They mean claim generation failed upstream. Two-sided verification is a precision control, not a recall mechanism.

### 6.6 Fusion: conservative result for the wrong reason

`packages/whisker/src/whisker/tapetum_llm/fusion.py::_source_aware_requires_review` caps a non-fail result at review when metadata is not `pass`, unit coverage is incomplete, units are unchecked/failed, or accepted high/critical defect evidence exists.

For P1068R11:

- metadata/outline was `review`;
- unit coverage was incomplete;
- four routed units were unchecked;
- accepted defect evidence was empty.

`fuse_verdicts` therefore returned `review` with `source_aware_review_cap`. The rule worked as designed. The weakness is diagnostic: the same output shape can represent "true defect found" or "coverage incomplete with no defect found." `packages/whisker/src/whisker/tapetum_llm/inspect_report.py` exposes both details, but the fused label itself is triage, not diagnosis.

### 6.7 Observability: PDF trace is not wired

The CLI accepts `--trace`, but the PDF branch in `packages/whisker/src/whisker/tapetum_llm/cli.py::_adjudicate_one` calls:

```text
judge_pdf_extraction(pid, backend, judge_agent, debug_log=judge_debug)
```

`packages/whisker/src/whisker/tapetum_llm/pdf_judge.py::judge_pdf_extraction` has no trace parameter. By contrast, the text branch forwards `trace=args.trace` to `adjudicate_paper`.

The PDF debug list is flushed through `write_debug_file`, so full debug exists. No equivalent PDF trace path is invoked. `--trace` silently producing no PDF trace is an observability bug independent of the PR defects.

### 6.8 Ideal-verifier workflow: branchless candidate is not canonical inventory

`packages/whisker/src/whisker/golden_ideals.py::find_ideals_dir` and `ideal_path` discover canonical merged ideals under:

```text
packages/tomd/tests/fixtures/golden/ideals/*.md
```

The CLI only calls `verify_against_ideal` when `ideal_path(pid, ideals_dir)` finds a matching local file. In this branchless review, the unmerged PR ideal was staged as the candidate Markdown but was absent from the checkout's canonical ideal inventory. The separate ideal verifier was therefore unavailable, and sidecar `ideal_verification` remained absent.

This is a workflow/integration gap. It is not necessarily a core model bug. Comparing a PR candidate to itself would also be meaningless, so any branchless design must define which file is candidate, which file is blessed reference, and what to do when no prior blessed ideal exists.

### 6.9 Development replay truth is stale

`packages/whisker/corpus/dev-replay/labels.json` currently labels PR #286 with `heading_hierarchy` and `html_entities`, expects deterministic `review`, and does not encode the four verified defect classes in this report. `packages/whisker/corpus/dev-replay/README.md` likewise summarizes PR #286 as unresolved marker, heading hierarchy, and entities.

The observed current run was deterministic `pass`, and the verified candidate has no inappropriate HTML entities in fenced code. These stale labels can make acceptance tests validate a superseded diagnosis. PR #286 must remain development replay, never holdout, but its replay truth must first be corrected from the final source-backed review.

## 7. Prioritized fixes

All recommendations prefer extending existing components. They are options with tradeoffs, not claims of completed design.

### P0. Correct PR #286 development-replay truth

Extend the existing dev-replay labels and tests to encode the four verified defect classes and current expected behavior during development.

Minimum:

- replace stale PR #286 defect descriptions with punctuation/operator loss, ordered-list collapse, subordinate-heading flattening, and inline-code delimiter corruption;
- record source pages and candidate anchors;
- set expectations from an actual replay rather than the earlier report;
- keep PR #286 disjoint from holdout and document that it is legal to tune against it.

Tradeoff: changing expected outcomes before implementation must distinguish current observed behavior from target acceptance behavior. One field should not serve both roles if that makes the test self-contradictory.

### P0. Add deterministic structural tripwires for cheap, explicit defects

Extend existing deterministic or source-router components with narrow checks:

1. Parse candidate Markdown and flag malformed inline-code delimiter residue or rendered code containing literal backtick debris.
2. Compare source list markers/item boundaries against candidate Markdown list items when reliable PDF layout evidence exists.
3. Add a punctuation/operator-sensitive check for normative/code-like source spans, preserving symbols rather than reducing them to word tokens.

These should raise review signals with page/location evidence. They should not replace unigram coverage or require token gates to solve visual semantics.

Tradeoffs:

- punctuation checks need strong source localization to avoid line-wrap and extraction-noise false positives;
- list comparison must distinguish semantic ordered lists from page furniture and numbering in prose;
- inline-code validation is low risk because candidate Markdown is directly parseable, but source linkage is still needed to prove fidelity rather than mere syntax style.

### P0. Improve PDF routing precision and budget ranking

Extend `route_pdf_units` and `run_unit_checks` rather than adding a new routing framework.

Candidate changes:

- filter or merge split PDF heading candidates before emitting `heading_drift`;
- reject prose-length "heading" candidates using existing font/layout metadata and bounded heuristics;
- rank unit value by signal specificity and severity before lexical page ID;
- sort numeric page IDs numerically;
- reserve budget for distinct signal classes or high-specificity structural signals;
- expose a reason when a unit is displaced by the cap.

Tradeoff: raising `MAX_UNIT_CHECKS` alone increases cost and still lets noise dominate. Better precision and prioritization should precede or accompany any cap increase.

### P0. Make unit checks inspect the signaled structure and candidate rendering

Extend `_check_one_unit` input and `UNIT_CHECK_SYSTEM_PROMPT` with a compact candidate structural packet relevant to the unit:

- parsed headings and levels;
- ordered-list item counts and boundaries;
- inline-code nodes and rendered text;
- code-fence counts;
- source-local punctuation/code spans.

Require the result to state which requested defect classes were checked. Preserve structured output and finite retries.

Tradeoff: a larger schema can improve auditability but may increase schema failures. Keep fields minimal and test them against `deepseek-v4-pro` and supported self-hosted models.

### P1. Add source-structural PDF signals

Extend `PageUnit` extraction and `route_pdf_units` where source layout supports reliable evidence:

- subordinate heading candidates based on font/color/spacing transitions;
- ordered-list marker sequences and item starts;
- code-font spans and punctuation-rich normative spans.

This is the lane that can address visual structure without asking word-token metrics to infer it.

Tradeoff: PDF layout evidence varies by producer. Signals should be review-oriented and calibrated on development replay plus negative controls. No VLM is required for the defects in this report.

### P1. Preserve the distinction between claim recall and evidence precision

Extend result/report fields to show:

- generated claims;
- verified claims;
- routed but unchecked units;
- selected units that returned clean;
- final review causes.

If generated claims are zero, report "no claims generated" rather than allowing zero evidence dispositions to look like successful verification.

Tradeoff: this is mainly diagnostic and will not improve recall by itself. It prevents operators from misreading a precision subsystem as a completeness guarantee.

### P1. Make fusion reasons diagnostic

Keep `source_aware_review_cap`, but expose machine-readable subreasons such as:

- `metadata_nonpass`;
- `coverage_incomplete`;
- `unchecked_units`;
- `failed_units`;
- `verified_defects`.

The combined verdict remains advisory. A review caused only by incomplete coverage must not be described as defect detection.

Tradeoff: changing persisted fusion shape requires schema/version handling and report compatibility.

### P1. Wire PDF trace end to end

Extend `judge_pdf_extraction` and the PDF CLI branch to accept and populate the same trace contract expected from the text path. Include headings for:

- whole-document judgment;
- metadata/outline;
- page screen;
- routing;
- each selected unit;
- evidence dispositions and aggregation;
- ideal verification when available;
- fusion.

The trace must still be written if a later PDF substep fails, subject to the existing fail-not-partial diagnostic policy.

### P2. Define branchless ideal-verifier behavior

Choose and document one workflow:

1. **Explicit reference option:** accept a user-supplied blessed ideal path distinct from the staged candidate.
2. **Base/head-aware review:** resolve the base branch ideal as reference and PR ideal as candidate.
3. **No-prior-ideal mode:** explicitly mark ideal verification ineligible when the PR adds the first ideal, and rely on source-aware validation.

The current PR #286 adds a new ideal, so option 2 may still have no base reference. Option 3 is therefore required even if base/head awareness is added.

Tradeoff: treating an unmerged PR file as canonical ground truth would invert the review contract and must not be done.

## 8. Acceptance criteria and replay tests

PR #286 is a development replay case. It must never be moved into or treated as holdout.

### Required diagnostic outcome

- The exact source and candidate hashes in this report cannot produce a clean diagnostic.
- At least one lane returns review with concrete, source-backed defect findings.
- A fused `review` caused only by coverage incompleteness does not satisfy defect-detection acceptance.

### Required localization

At minimum, one of these must hold for each target region:

- page 7 is selected for a source-aware check, or a deterministic punctuation/operator tripwire reports the missing `N>.`;
- pages 9 and 10 are selected, or deterministic/source-structural tripwires report the three flattened subordinate headings and both list collapses;
- page 13 is selected and the unit reports malformed inline code, or a deterministic Markdown tripwire reports the delimiter corruption on pages 12 and 13.

### Required defect types

Replay output must surface:

- punctuation/operator loss in normative text;
- ordered-list item-boundary/cardinality loss;
- subordinate-heading flattening;
- inline-code delimiter/rendering corruption.

Counts should be testable against the reviewed candidate:

- one missing `N>.` instance;
- two collapsed ordered-list groups, source cardinalities 2 and 3;
- three flattened subordinate headings;
- two malformed inline-code examples.

### Required negative controls

- Human ideals without `<ins>`, `<del>`, or `:::wording` remain clean for that reason.
- Correctly stripped structural Roman, alphabetic, and HTML `span.secno`
  prefixes remain clean. Semantic numeric title content is preserved.
- The retracted Remarks/Note/Returns claim does not reappear.
- Existing clean dev-replay papers remain clean.
- Existing false-positive defenses for TOC removal, front-matter mapping, page furniture, line reflow, dehyphenation, and imaged figure text remain intact.
- Holdout thresholds and labels are not tuned using PR #286.

### Routing and budget tests

- Numeric page ordering is deterministic.
- Noisy same-severity heading signals cannot consume every unit slot ahead of a more specific punctuation, list, code, or structural signal.
- Cap overflow records selected and displaced units plus selection reasons.
- A page 13 unit fixture containing the reviewed malformed inline code cannot return a clean diagnostic from the complete unit pipeline.

### Evidence and aggregation tests

- Zero generated claims is represented distinctly from zero rejected claims.
- Verified defect groups require source grounding and candidate-side disposition under the existing evidence policy.
- Two-sided evidence continues to reject hallucinated or candidate-present claims.
- Aggregation does not silently erase non-countable exact-location defects merely because document-wide token counts match.

### Fusion tests

- Incomplete coverage without verified defects returns review with an explicit coverage subreason.
- Verified high/critical defects return review with an explicit defect subreason.
- The two cases are distinguishable in sidecar and inspection output.
- The advisory result never changes deterministic `--gate` exit behavior.

### Observability tests

- `--trace` on the PDF path creates a trace artifact at the backend trace path.
- The trace records every executed PDF step and excludes unexecuted steps.
- `--debug` remains full fidelity.
- A schema retry appears in debug and the completed step appears in trace without exposing a false success for an unexecuted check.

### Ideal-verifier workflow tests

- Branchless review behavior is documented and covered.
- A staged candidate that is absent from canonical merged ideal discovery produces an explicit ineligible/not-available reason.
- Candidate and reference identity cannot silently resolve to the same bytes.
- A newly added ideal with no base reference follows the documented no-prior-ideal mode.

## 9. Non-goals

- The LLM lane does not become a hard gate.
- No VLM is required for the text and structure defects in this report.
- Token gates are not expected to infer all visual semantics.
- Holdout thresholds are not tuned using PR #286.
- Human ideals are not changed to add converter ghosts such as `<ins>`, `<del>`, or `:::wording`.
- The 2026-07-22 revalidation treats structural Roman, alphabetic, and HTML
  `span.secno` prefixes as leading section numbers to strip; semantic numeric
  title content is not stripped.
- The retracted Remarks/Note/Returns claim is not restored.
- Fusion `review` is not redefined as proof that a real defect was found.
- Raising `MAX_UNIT_CHECKS` without improving signal precision is not considered a complete fix.

## 10. Evidence and artifact inventory

### Authoritative review

- Public review: <https://github.com/cppalliance/wg21-paperflow/pull/286#pullrequestreview-4740480002>
- Full TEMP report: `C:\Users\sabo2\AppData\Local\Temp\pr286-review\PR286-golden-review-p1068r11-current.md`
- Run root: `C:\Users\sabo2\AppData\Local\Temp\pr286-review\20260721-025056-358`

### Runtime artifacts

- `deterministic.json`: deterministic metrics, gates, verdict, and flags.
- `deterministic.stderr.txt`: deterministic command diagnostics.
- `workspace/whisker/llm/p1068r11.whisker.tapetum.json`: PDF lane, routing, units, evidence summary, fusion, and fingerprints.
- `workspace/paperstore/p1068r11.debug.tapetum_llm.md`: full LLM debug transcript.
- `workspace/whisker/llm/tapetum-inspect.md`: human-readable inspection report.
- No PDF trace artifact was produced despite `--trace`.

### Source-fidelity artifacts

- `rendered/page-001.png` through `rendered/page-015.png`: rendered source pages.
- `pdf-layout.json`: source font/style/position evidence.
- `pdf-color-counts.txt`: source color evidence.
- `head/`, `base/`, `live-head/`: extracted review inputs.
- `manifest-initial.json`, `manifest-final.json`: input identity and hashes.
- `bench.json`, `converter.md`, `ideal-vs-converter.diff`: conversion and comparison evidence.

### Current code references

- `packages/whisker/src/whisker/constants.py`: deterministic thresholds and schema.
- `packages/whisker/src/whisker/golden_ideals.py`: canonical ideal discovery and metric panel.
- `packages/whisker/src/whisker/tapetum_llm/constants.py`: page floors, unit cap, fusion names.
- `packages/whisker/src/whisker/tapetum_llm/source_router.py`: PDF risk-signal generation.
- `packages/whisker/src/whisker/tapetum_llm/pdf_judge.py`: whole-document judge, page screen, routing, evidence fold.
- `packages/whisker/src/whisker/tapetum_llm/unit_judge.py`: capped selection, unit calls, evidence verification, aggregation.
- `packages/whisker/src/whisker/tapetum_llm/models.py`: structured output consistency and ideal-verification schemas.
- `packages/whisker/src/whisker/tapetum_llm/fusion.py`: source-aware review cap.
- `packages/whisker/src/whisker/tapetum_llm/inspect_report.py`: operator-facing evidence and coverage rendering.
- `packages/whisker/src/whisker/tapetum_llm/cli.py`: PDF/text dispatch, debug persistence, trace asymmetry, ideal attachment.
- `packages/whisker/corpus/dev-replay/labels.json`: current stale PR #286 labels.
- `packages/whisker/corpus/dev-replay/README.md`: development-replay policy and current stale summary.
- `packages/whisker/tests/test_dev_replay_acceptance.py`: deterministic replay expectations.
- `packages/whisker/tests/test_dev_replay_schema.py`: replay/holdout separation and label validation.
- `packages/whisker/tests/test_source_router.py`, `test_unit_judge.py`, `test_pdf_judge.py`, `test_fusion.py`, and `test_source_aware_integration.py`: existing extension points for the acceptance tests above.

## 11. Open questions and implementation order

### Open questions

1. Which source-layout signals are stable enough across WG21 PDF producers to support list and subordinate-heading tripwires without excessive false positives?
2. Should malformed inline-code detection live in deterministic candidate QA, PDF source routing, or both? Candidate syntax is cheap to test, while source linkage proves fidelity.
3. How should routing rank heterogeneous signals under a fixed cost budget? Severity alone is insufficient when all heading noise has the same severity.
4. Should unit checks receive a page-local candidate packet derived from source-to-candidate localization, or a compact whole-document structural index plus the full Markdown?
5. Which unit output field best proves that each requested defect class was actually inspected without encouraging performative checklist answers?
6. How should non-countable structural defects be grounded when the source quote's words are present but their Markdown role is wrong?
7. What is the explicit branchless contract when a PR adds the first ideal and no blessed predecessor exists?
8. Should metadata/outline narrative claims receive the same two-sided verification treatment as defect claims? In this run, narrative falsehoods influenced review without structured mismatches.
9. How should current observed replay behavior and target acceptance behavior coexist in labels without rewriting history?

### Recommended implementation order

1. Extend the development-replay schema so one PID can carry versioned cases
   keyed by source/candidate identity, then preserve the historical PR #286
   replay and add separate current-head PR #286 and PR #295 cases with exact
   source/candidate hashes.
2. Normalize source-only heading labels deterministically and compare normalized
   source outlines with candidate headings.
3. Add source-aware table-cell packets and the six-instance P1068R11 `SF`
   acceptance case.
4. Improve signal precision, numeric ordering, and scheduling under
   `MAX_UNIT_CHECKS`.
5. Remove script/style payloads from HTML packets and enforce routed-unit packet
   identity.
6. Add rendered-Markdown adjacency and delimiter checks with negative controls.
7. Preserve the earlier punctuation/operator, ordered-list, subordinate-heading,
   and malformed-inline-code replays for the historical PR #286 candidate.
8. Add explicit claim-generation and fusion subreason reporting.
9. Wire PDF trace and test artifact creation.
10. Define and test branchless ideal-verifier eligibility.
11. Replay both exact current-head hash pairs, then run complete development
    replay negative controls.
12. Evaluate on locked holdout only after design choices are frozen. Do not tune
    on holdout results.

The implementation is complete only when the replay names the real defects, preserves the existing false-positive defenses, and produces a PDF trace. A bare fused `review` with empty defect groups remains insufficient.
