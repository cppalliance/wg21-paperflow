# LLM-Readability of Our Converted Markdown - Research Synthesis

**Verdict band:** usable-with-conditions   **Confidence:** high
**Decision vs our codebase:** self-target; decision = keep the architecture, close five ranked conditions.
**Run question:** "Are our markdowns provably fully LLM-readable, theoretically and practically confirmed?"
**Honest one-line answer:** proven for the 2 corpus papers' authored facts; NOT YET PROVEN for the ~200-paper fleet; the stack is on the only externally validated path to making it provable.

Synthesized by Fable 5 (main context) from 25 Composer persona reports, 5 web foragers,
5 Opus meta-reviews, and 15 Composer repo scanners over 31 cloned converter repos.
Repo SHA `e66116a09bbe833a8080e9e60a95833ab339cf64`, 2026-07-06.

## Summary

- **Theory: confirmed.** Lane 3's deterministic, LLM-free fact-assertion design is the
  only externally validated comprehension-gating pattern. olmOCR-bench (7,010 unit
  tests, LLM-free scoring), ParseBench (169K deterministic rules, explicitly rejects
  LLM-as-judge and TEDS gating), and RealDocBench (typed field-level QA) all converge
  on the same conclusion whisker reached independently (05-web.md Q1/Q3). Among the 31
  cloned repos, olmOCR remains the ONLY one with comprehension-style gating: the
  repo-scan wave re-verified the original survey claim (repo-scan/_patterns-matrix.md).
- **Practice: confirmed only at POC scope.** The deterministic gate provably recovers
  17 human-verified facts from 2 blessed papers, with working canaries
  (test_comprehension_corpus.py:77-116) and one byte-exact blind read-back (P4182R0
  run 3, 8/8; P4185R0 9/9). Meta-reviewer A re-verified all methodology critiques AND
  downgraded persona 22's "garbage" verdict on the anchor: it is garbage as FLEET
  evidence, sound as a scoped POC anchor. Any "fleet practically confirmed" language
  must be struck.
- **The fleet gap is the single honest CRITICAL.** 198 of ~200 converted papers carry
  zero verified facts; Lane 3 passes vacuously for them (facts.py:128-130). Their only
  protection is the order-blind `unigram_coverage >= 0.85` multiset gate + structural
  gates + a never-gating advisory lane. Token-preserving corruption (cell swaps, xref
  drift, operator garbling, reorder) provably survives all of it (meta-B verified the
  cell-swap keeps content_recall = 1.0).
- **The deterministic gate has verified, reproducible exploit classes.** Meta-reviewer
  B reproduced the decoy-shadow-table exploit live (both P4182R0 table facts pass
  against decoys while the real tables are scrambled, all gates green; facts.py:313-323
  first-match cell lookup). Meta-reviewer A reproduced the math brace-scope erasure
  (`x^{2k}` and `x^2k` both fold to `x^2k`; facts.py:173-181 + lowercase). Verified:
  `x != y` and `x == y` both normalize to `xy` under clean_string, so NO existing fact
  type can assert C++ operator fidelity: the core WG21 payload class is un-assertable.
  tomd emits HTML tables for entire classes (CODE_COMPARISON/SPEC_TABLE/NB_BALLOT +
  any newline-cell; tomd table.py:124-133, 2410-2419) which `_parse_pipe_tables`
  cannot see at all; P4185R0's snapshot already contains an HTML table with zero facts.
- **tapetum_llm: all three #277 blocking conditions remain OPEN four days after the
  #277 synthesis.** Meta-D verified verbatim: `adjudicate.py:237` still reads
  `if suggested_verdict != VERDICT_PASS and not grounded:` (confident pass with all
  evidence dropped still passes, no compensating path, zero regression test); no
  sighting-run ground-truth audit artifact exists in-repo; SERVICES.toml has no vLLM
  flag documentation. Meta-E re-graded this from the swarm's 6x CRITICAL down to MED
  for THIS run's question (tapetum is advisory-only, outside the readability proof
  path) but HIGH within the lane's own scope.
- **Documentation drift found by meta-D:** the baseline (and root CLAUDE.md) name
  `dissect` and `pipeline.tools.wrap_source`; at this SHA the actual markdown consumer
  is `assay`, and the live API is `inject_untrusted`. Worse: agora injects raw
  unwrapped `paper_source` (agora pipeline.py:268, 454), a real prompt-injection
  surface OUTSIDE the whisker scope but inside the fleet's actual reading path.
- **Repo-scan yield beyond olmOCR:** no repo verifies its "LLM-ready" marketing
  (markitdown: our oracle!, mdream, pymupdf4llm, firecrawl all market LLM-readability
  and none verify comprehension). Portable patterns whisker lacks: olmOCR per-page
  baseline sanity facts (non-empty, repeated-n-gram, unexpected-script) and
  first/last-N-char zone presence; CommonMark output linting (html-to-markdown-py,
  opendataloader-pdf: only 2/31 do it); camelot-style per-table confidence sidecars;
  langextract's monotonic exact-occurrence alignment DP for tapetum grounding;
  firecrawl/RealDocBench-style schema-validated fixed-extractor QA as an optional
  consumability lane.

## Top findings (ranked)

1. **[CRITICAL][fleet]** 198/~200 papers have zero comprehension coverage; Lane 3 is
   vacuously green; the order-blind unigram gate passes token-preserving semantic
   corruption end-to-end. Evidence: facts.py:128-130, meta-B cell-swap probe
   (content_recall unchanged), persona 12/21/16. Fix: condition 1 below.
2. **[HIGH][design]** No `code`/`xref`/`image-ref` fact type and `normalized_text`
   strips operators: `x != y` ≡ `x == y`. WG21's highest-value payload is
   un-assertable. Evidence: meta-B probe, facts.py:59-64, metrics.py clean_string.
3. **[HIGH][design]** First-match table-cell lookup is defeated by a decoy table
   (live reproduced, canary-invisible); heading-anchored or all-occurrence matching
   fixes it. Evidence: facts.py:313-323, opus-B-gate-soundness.md claim 1.
4. **[HIGH][design]** HTML-emitted tomd tables are invisible to the pipe-only grid
   parser; a whole emission class has no assertable table facts. Evidence:
   facts.py:261-295 vs tomd table.py:124-133, 2410-2419; P4185R0 snapshot.
5. **[HIGH][design]** Math surface erases brace scope, case, and root index
   (`x^{2k}` ≡ `x^2k`, live reproduced). olmOCR's KaTeX-geometry compare is the
   stronger model we deliberately traded away. Evidence: facts.py:173-181,
   opus-A-metric-validity.md claim 1.
6. **[HIGH][methodology]** The read-back anchor has real limits: 2/3 P4182R0 runs
   were not byte-exact, questions embed answer lexemes, contamination uncontrolled,
   no adversarial control (an LLM was never shown corrupted markdown). Keep the
   anchor, fix the protocol on the next corpus wave. Evidence: opus-A claims 4-5,
   opus-E section 2.
7. **[MED][advisory-lane]** #277 blocking conditions 1-3 all still open; confident
   ungrounded advisory passes ship with zero regression test; the correct fix must
   gate on `working.evidence_spans and not grounded` (NOT bare `not grounded`, which
   would wrongly demote sanctioned empty-evidence passes). Evidence:
   adjudicate.py:237, opus-D claims 1-2, opus-C claim 5.
8. **[MED][engineering]** Verified engineering debt: duplicated pipe-table parsers
   with divergent normalization (facts.py:261-295 vs bench.py:98-132); `_hard_split`
   cuts mid-fence/mid-table (chunking.py:125-148); `whisker --all` drops errored
   papers from report.json/--json (only the footer counts them; __main__.py:210-261);
   rapidfuzz alignment path has zero frozen test vectors; no .gitattributes
   (411/2180 files CRLF); vacuous-green `whisker facts`/`guard` on all-draft files
   (--strict exists but is not the default); utf-8 vs utf-8-sig split (downgraded to
   LOW/MED by meta-C: BOM provably cannot flip committed facts).
9. **[MED][docs]** Stale/overreaching docs: "never turns uncertainty into a
   pass/fail" tagline vs the pass exemption; root CLAUDE.md names dissect and
   wrap_source, actual consumer is assay and the API is inject_untrusted; agora
   injects unwrapped paper_source (agora pipeline.py:268,454). Evidence: opus-D.
10. **[LOW][license]** Apache-2.0 verbatim OmniDocBench ports (metrics.py:394-399,
    88-96; match.py:23-24) lack a THIRD_PARTY_NOTICES file: attribution gap, no
    copyleft risk. Evidence: opus-D claim 4.

## Bugs / edge-cases in OUR code (surfaced by the run)

- `facts.py:313-323`: first-match cell location: decoy-table false pass (verified).
- `facts.py:317` vs `:333`: exact-match cell vs max_diffs-tolerant neighbors: a
  `**bold**` or footnoted cell hard-fails a correct conversion (false-fail vector).
- `facts.py:173-181`: `_math_surface` lowercase + fold erases case/brace semantics.
- `tapetum_llm/adjudicate.py:237`: confident-pass grounding exemption (#277 cond 1).
- `tapetum_llm/chunking.py:125-148`: `_hard_split` not fence/table-aware.
- `__main__.py:210-261`: errored papers vanish from machine-readable batch output.
- `agora/pipeline.py:268,454`: raw unwrapped `paper_source` into the prompt.
- Repo-wide: no `.gitattributes`; corpus reads split utf-8/utf-8-sig.

## Top portable detail (from the 31-repo scan)

**olmOCR's per-page `Baseline` fact class** (non-empty alphanumeric output, no long
repeating n-grams, no unexpected scripts/mojibake, auto-generated for every paper
with no authored facts): it is the ONE pattern that would immediately convert our
198 vacuously-green papers into minimally-gated papers at near-zero authoring cost,
and it is proven in the only comprehension benchmark the field has. Anchor:
repo-scan/olmocr.md; olmocr/bench BasePDFTest/BaselineTest.

## How we are positioned (the user's question, answered directly)

- **Theoretically:** best-in-field. Our architecture independently matches where
  2026 benchmarks (olmOCR-bench, ParseBench, RealDocBench) converged. Nobody among
  the 31 surveyed/cloned converters gates comprehension except olmOCR; we already do.
- **Practically:** proven for exactly 2 papers and 17 facts, with a defensible but
  improvable anchor protocol. The fleet claim of #254 is open. The gate's primitives
  have five verified false-pass/false-fail classes to harden before scaling the
  corpus makes them load-bearing.
- **Can we improve? Yes, concretely and cheaply**, in this order (leverage-ranked by
  meta-E, adopted):
  1. Stratified corpus growth: 30-50 fleet papers (not near-100% converts), >=300
     verified facts, >=5 papers per zero-coverage class (multi-column, merged tables,
     display math, code-heavy, footnotes, images), blind HOLDOUT read-back >=90% on
     the production self-hosted stack, questions authored independently of fact
     strings, one adversarial corrupted-paper control run.
  2. Schema extension: `code`, `xref`, `image-ref` fact types + an operator-sensitive
     raw surface mode for present/absent; plus olmOCR-style auto `baseline` facts for
     every paper (kills vacuous green fleet-wide immediately).
  3. Gate live converter output, not frozen snapshots; fail `whisker facts`/`guard`
     on `verified_count == 0` for processed papers (mirror the pytest guard into the
     CLI).
  4. Harden primitives: heading-anchored table identity, HTML-aware grid builder,
     brace/scope-preserving math surface; one CI canary per exploit class; unify the
     duplicated table parsers.
  5. Land #277 condition 1 (evidence-was-emitted-and-all-dropped -> demote, plus
     regression test), audit the 72 clears, document vLLM flags, fix the docs drift
     (assay/inject_untrusted, agora unwrapped injection).

## Flip conditions

- **Up to usable:** conditions 1-3 closed: stratified corpus live, schema extended,
  baseline facts fleet-wide, live-output gating; holdout read-back >=90% with the
  adversarial control failing as expected.
- **Down to garbage:** the holdout read-back on stratified (non-cherry-picked) papers
  shows systematic fact non-recovery (<70%) on table/math classes, meaning tomd
  output is materially unreadable and the current green fleet is an illusion.

---
Sources: self-target at repo SHA e66116a0 (2026-07-06), baseline 00-baseline.md.
Web: 05-web.md (25 finding cards, 24 unique URLs).
Personas: 25 (01-25). Meta-reviewers: A (metric validity), B (gate soundness),
C (engineering), D (provenance), E (steelman + balance).
Repo scan: 15 Composer agents, 31 reports + _patterns-matrix.md under repo-scan/.
Prior work honored, not re-filed: packages/whisker/research/ (deepseek-v4-pro #277,
comprehension-poc-report, redteam 28-repo survey, llm-stack, langextract, persona,
buildvsbuy).
