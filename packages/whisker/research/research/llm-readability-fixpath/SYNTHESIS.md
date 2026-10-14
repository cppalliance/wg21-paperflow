# LLM-readability fix-path implementation - Research Synthesis

**Verdict band:** usable-with-conditions   **Confidence:** high
**Decision vs the 31 comparison repos:** keep ours, adopt-partially (5 named ports below)

Run: 2026-07-09, base SHA e66116a + uncommitted fix-path work. 11 Composer-2.5
comparison scans (01-11) + 1 self red-team (12), meta-verified by main agent
reproducing the top 3 claims against live code (all 3 CONFIRMED).

## Summary

- **The architecture is genuinely ahead of the field.** None of the 31 repos,
  including the production LLM-readability products (firecrawl, pymupdf4llm,
  markitdown, mdream), maintains a human/agent-verified comprehension fact corpus
  OR a blind LLM readback harness. 11/11 scans confirm this independently. What we
  built this week (facts schema extension, HTML tables, math-surface fixes,
  vacuous-green gate, grounding demotion, readback CLI, corpus tools) has no
  complete equivalent anywhere in the comparison set.
- **But the 37/37 readback score is overclaimed.** Meta-verified exploits:
  (1) present/absent/code/xref readback questions embed the answer needle and
  `_evaluate_answer` accepts a bare sycophantic "Yes" (readback.py:112-122,183-186;
  reproduced: `_evaluate_answer(present, "YES", "Yes, definitely.")` → True).
  (2) Table readback scoring is document-wide substring: answer "18" passes an
  expected "8" (readback.py:200-203; reproduced). Only the table question TYPE was
  fixed for blindness this week; scoring and the YES/NO types were not.
- **One CRITICAL deterministic-gate exploit remains open:** a decoy pipe table
  sharing the same `table_heading` with correct neighbors passes `_check_table`
  while the real table is scrambled (facts.py:396-403; reproduced with a live
  probe). This is the residual half of the SYNTHESIS-#3 decoy exploit the fix
  path was supposed to close; all-occurrence matching closed the anchorless case
  only.
- **CI gate covers 17 of 37 verified facts.** Only P4182R0/P4185R0 have
  `<pid>.expected.md` snapshots; the 3 new wave-2 papers are live-readback-only
  evidence (test_comprehension_corpus.py:40-44).
- **Delivery check vs the 2026-07-06 ranked fix path:** 6 of 9 promised items
  fully delivered; partial: corpus scale (5/30 papers), auto-baseline wired
  fleet-wide (code exists, not wired), decoy-table closure (see above). Full
  table in 12-redteam-ours.md.

## Top findings (ranked)

- [CRITICAL][NOW] Decoy-table false pass with matching `table_heading`.
  Evidence: facts.py:396-403, reproduced. Fix direction: when `table_heading` is
  set and MULTIPLE tables match it, require ALL matching tables to satisfy the
  neighbors, or bind the fact to a table index/nearest-heading anchor. adopt? ours-to-fix.
- [HIGH][NOW] Readback YES/NO sycophancy + needle-embedding. Evidence:
  readback.py:112-122,183-186, reproduced. Fix direction: for present/code/xref
  require a verbatim quote in the answer and verify the quote grounds in the
  paper markdown (reuse `ground_spans`); for absent keep NO but treat it as weak
  evidence only. adopt? ours-to-fix.
- [HIGH][NOW] Table readback substring scoring. Evidence: readback.py:200-203,
  reproduced ("8" ⊂ "18"). Fix direction: exact `_norm_cell` equality against
  the answer's extracted value per direction, or regex word-boundary. adopt? ours-to-fix.
- [HIGH][SOON] 18/37 facts not CI-gated. Evidence: corpus dir 2 expected.md vs 5
  facts files. Fix direction: commit `<pid>.expected.md` for wave-2 papers (the
  staged .md IS the current output; snapshot it). adopt? ours-to-fix.
- [MED][SOON] `classify_paper` counts `$$…$$` inside code fences as display math
  (corpus_tools.py:40,76; caused P4234R0's nonsense math auto-drafts). Fix
  direction: strip fenced blocks before regex (reuse tables.py fence walker). adopt? ours-to-fix.
- [MED][SOON] `auto_baseline_checks` implemented but not wired into `whisker
  facts` (facts.py:631-674, CHANGELOG). The ~198 zero-facts papers have no floor.
- [MED][LATER] Readback transport errors score as FAIL not ERROR
  (readback.py:279-283; a live timeout produced a spurious FAIL on N5040).

## Bugs / edge-cases in OUR code (surfaced by the comparison)

- facts.py:396-403 decoy-table (above).
- readback.py:167-203 answer-scoring weaknesses (above).
- corpus_tools.py:40 fence-blind display-math regex (above).

## Adoption candidates (license-clean, ranked by leverage)

1. **olmocr `FootnoteTest.run`** (Apache-2.0) - footnote-integrity assertion type
   we lack entirely; wave-2 strata flagged footnotes (P1040R9/10) with no fact
   type to express them. See 01-olmocr.md.
2. **camelot `compute_whitespace` + `Table.confidence`** (MIT, ~40 LOC) - reference-
   free table-quality score; direct fit as an `auto_baseline_checks` table axis.
   See 07-table-extractors.md.
3. **docling `verify_table_v2` pattern** (MIT) - exhaustive per-cell verification
   incl. `column_header`/`row_header` flags; the model for a future span-aware
   grid in tables.py (our list[list[str]] loses rowspan/colspan). See 03-docling.md.
4. **html-to-markdown-go `goldenfiles.go` corpus layout** (MIT) - construct-
   isolated paired `.in.html`/`.out.md` micro-goldens; the organizational
   pattern for the planned golden-file wave. See 09-js-go-converters.md.
5. **langextract `_normalize_token` plural-stem** (Apache-2.0, ~7 LOC) - small
   robustness win for grounding alignment. See 10-langextract.md.

Rejected: MinerU/firecrawl/PyMuPDF ports (AGPL), marker's pandoc normalize (GPL),
langextract LCS Tier-3 (unsafe per 10-langextract.md).

## Top portable detail

olmocr's per-fact-class test objects (FootnoteTest et al., Apache-2.0): each fact
type is a class with its own `run(md) -> (bool, reason)` returning an explanation
string. Our `_evaluate` returns bare bool + note; the explanation-string pattern
would make `whisker facts -v` diagnostics and readback questions richer for free.

## Flip conditions

- Verdict rises to **usable** when: decoy-table exploit closed + readback scoring
  binds values (no substring) + YES/NO types require grounded quotes + all 5
  corpus papers CI-gated. All four are small, named diffs.
- Verdict falls to **garbage** only if the corpus facts themselves were wrong;
  wave-2 facts were verified against original sources (HTML/PDF), so no path there.

---
Sources: 31 repos at packages/whisker/research/repos/ (analyzed in place),
baseline 00-baseline.md, prior run research/llm-readability/ (2026-07-06).
Scans: 01-11 (Composer-2.5, grouped). Red-team: 12 (Composer-2.5).
Meta-verification: main agent, 3/3 top claims reproduced live, 2026-07-09.
