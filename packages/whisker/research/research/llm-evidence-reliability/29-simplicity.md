# 29 - Simplicity and Maintainability Skeptic

**Verdict:** usable-with-conditions — the 40% evidence-precision failure is a one-sided
verification bug, not a missing subsystem; the smallest correct fix reuses
`ground_spans`/`ground_page_quotes` twice (source haystack, then candidate haystack)
inside `pdf_judge.py`, and every surveyed repo plus whisker's own `facts.py` confirms
that pattern beats new abstractions, NLI, or dependencies.
**Confidence:** high

## Findings

- [CRITICAL] The production bug is ~30 LOC of missing logic, not a new verifier
  module. `pdf_judge.py:513-520` grounds missing-content quotes against `pdf_text`
  only; `to_sidecar_dict()` then labels every survivor `"present in PDF text layer,
  absent from markdown"` (`pdf_judge.py:401-404`) without ever checking `tomd_md`.
  The PR replay measured **8/20 = 40%** candidate-absence precision
  (`00-baseline.md:14-24`). Impact: fix is a second `ground_spans(spans, tomd_md)`
  (or equivalent filter) in the same function — same API the text lane already uses
  on markdown (`adjudicate.py` via `ground_spans`); no new file, no new dependency.

- [HIGH] `grounding.py` already implements the olmOCR-bench bidirectional pattern the
  web corpus recommends (`05-web.md` Q1 olmOCR `TextPresenceTest`, Q5 dual-signal
  FActScore). Three tiers (monotonic exact DP, normalized substring, length-gated
  `partial_ratio`) plus page-scoped length-relative fuzzy in `ground_page_quotes`
  (`grounding.py:171-278`) are the portable machinery; olmOCR's length guard is
  already ported at `grounding.py:272`. Impact: importing olmOCR code or adding
  chopdiff/semdiff/NLI is unjustified — the web conclusion explicitly names
  "olmOCR-style candidate-side check built from existing `ground_spans`,
  `ground_page_quotes`, `rapidfuzz`" (`05-web.md:192-194`).

- [HIGH] Reject Personas 3, 6, 20, 21 (entailment, token-window retrieval, RAG, NLI)
  for the first fix. AbsenceBench shows models systematically fail surface-form
  absence even with both documents in context (`05-web.md` Q1 AbsenceBench); RefChecker
  and semdiff add model dependencies with no measured lift on our 9-paper replay.
  `match.py` block alignment (OmniDocBench port, `05-web.md` Q3) belongs in the
  `ambiguous` rescue tier only, not v1 — Hungarian assignment is ~200 LOC and a
  second codepath for a problem `ground_spans` already solves on whole-document
  quotes. Impact: scope creep here trades a shippable precision fix for research
  infrastructure inside a 4751 LOC advisory lane that never gates CI.

- [HIGH] Do not fork candidate verification into `facts.py` or a new schema layer.
  Lane 3 `facts._present_within` (`facts.py:324-326`, `441-444`) is the same
  locate-then-measure idea but operates on human-verified needles with per-fact
  `max_diffs` and gates CI — a different contract. Personas 17–18 (claim schema,
  provenance designer) would add Pydantic types and sidecar fields for a filter that
  fits in `pdf_judge.py` with existing `GroundedSpan.status` (`grounding.py:46-47`)
  and honest `reason` strings. Impact: a `BidirectionalVerifier` class or
  `EvidenceProvenance` subsystem duplicates `ground_spans` and increases the
  22-module touch surface without moving evidence precision.

- [MED] Tri-state output (`present | absent | ambiguous`) is a label change, not a
  framework. CRAG's ambiguous band (`05-web.md` Q5) and LitRAG's "locate hit
  overrides LLM missing" (`05-web.md` Q2) both map to: source grounded + candidate
  `GROUND_EXACT` → drop quote (false positive); source grounded + candidate dropped
  → retain absent; source grounded + candidate `GROUND_FUZZY` only → `ambiguous`,
  demote verdict, do not count as absent. `adjudicate.py` already demotes fuzzy-only
  evidence for text-lane passes (`adjudicate.py:319`); mirror that policy on PDF
  missing-content quotes. Impact: avoids binary trust in normalized substring hits
  for code/math (Personas 11–12) without raw-surface parallel matchers in v1.

- [MED] Page escalation repeats the same one-sided bug. `ground_page_quotes` at
  `pdf_judge.py:572-574` checks source page text only; candidate-side page check is
  the same function with `tomd_md` (or a page slice if added later). Marker and
  pdf-parse-bench both say: deterministic pairing before LLM adjudication
  (`05-web.md` Q1 Marker, pdf-parse-bench). Impact: page and monolith paths stay
  symmetric; one helper call per path, not a second escalation architecture.

- [LOW] Maintainability wins (VLM quarantine, dual prompt collapse, cascade
  deletion) from `llm-qa-integration/14-maintainability-complexity.md` and Opus-D are
  real but orthogonal — they shrink dead LOC, they do not fix 12/20 false-absence
  quotes. Bundling them with evidence verification violates whisker's minimalism
  ladder and package-boundary discipline: one measured fix per pass. Impact: ship
  candidate-side grounding first; queue ~788 LOC VLM deletion as a separate hygiene
  PR.

- [LOW] Benchmarks (olmOCR-Bench 7,010 tests, QASPER, FEVER evidence F1,
  `05-web.md` Q4) justify a labeled holdout for threshold tuning, not for choosing
  the architecture. The 31 local clones (`00-baseline.md:76-83`) converge on
  deterministic locate-then-judge; zero use LLM absence as a mechanical gate
  (`llm-qa-integration/SYNTHESIS.md:18-28`). Impact: after the two-sided filter
  lands, replay the nine PRs — if precision ≥ 0.85, stop; only then consider
  `ambiguous` block-window rescue from `match.py`.

## False-pass hypothesis

PR #285 class: date line `"2024-01-15"` present in markdown twice (normalized
substring hit) but reported missing because candidate check was never run
(`00-baseline.md:17-18`). After fix, quote drops; if we only add source-side
grounding without tri-state, a dehyphenation edge (`constexpr` split across a
fenced code line) could still false-absent when normalized substring fails but
raw `facts._present_within` with small `max_diffs` would match — mitigated by
`ambiguous` on fuzzy-only candidate hits, not by NLI.

## False-fail hypothesis

PR #293 class: five `constexpr` declarations genuinely absent (`00-baseline.md:19`).
Candidate-side `ground_spans` drops them (no exact, no substring, ratio below
`EVIDENCE_FUZZY_FLOOR`); they correctly stay absent. False-fail risk is over-tight
fuzzy floor on short quotes — olmOCR length-relative threshold already exists for
page quotes (`grounding.py:272`); applying the same formula to monolith quotes is
a constant tweak, not a new matcher.

## What would change my mind

A labeled replay of the nine PR papers showing two-sided `ground_spans` suppresses
≥3 genuine absences (precision worse than 0.60) would force a third tier (page slice,
raw-surface branch, or block-window `ambiguous` rescue). Until that number exists,
the smallest correct fix stands.
