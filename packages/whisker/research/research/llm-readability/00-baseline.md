# 00 - Evidence Baseline: LLM-Readability of Our Converted Markdown

Target: **self-target** "our LLM-readability stack" = whisker Lane 3 comprehension
(`packages/whisker/src/whisker/facts.py`) + comprehension corpus
(`packages/whisker/corpus/`) + tapetum_llm advisory LLM lane
(`packages/whisker/src/whisker/tapetum_llm/`) + tomd markdown output conventions.

Repo SHA at analysis time: `e66116a09bbe833a8080e9e60a95833ab339cf64` (2026-07-06).
Comparison codebase: this monorepo itself (self-target; no external adopt/replace
axis, the verdict is "are we positioned so our markdowns are provably LLM-readable,
and where do we improve").

Driving issues:

- **#254** (OPEN): "verify converted output is actually LLM-readable (read ->
  understood -> correct), not just golden-file faithful." This is the research
  question of this run.
- **#256** (MERGED): the whisker package implementing Lanes 1-3.
- **#277** (OPEN): capability limits of DeepSeek-V4-Pro as the tapetum_llm judge.
  Already researched to completion (see Prior Work); verdict
  usable-with-conditions, ADOPT gated on 3 blocking conditions.

## What the target is

tomd converts WG21 papers (PDF/HTML) to markdown consumed by LLM pipelines
(dissect/agora). whisker QAs those conversions in three deliberately independent
lanes (`packages/whisker/src/whisker/CLAUDE.md`):

- **Lane 1 Stability** (`golden.py`): exact diff vs committed `<pid>.expected.md`.
- **Lane 2 Fidelity** (`bench.py`/`guard`): nid/teds/mhs/content_recall vs
  hand-cleaned `<pid>.gt.md`. Resemblance, not comprehension.
- **Lane 3 Comprehension** (`facts.py`): deterministic, human-verified fact
  assertions; the only lane that tests "can an LLM still recover the paper's
  facts." No LLM in the scoring loop (olmOCR model, adopted deliberately).
- **tapetum_llm** (opt-in, never gates): two-tier LLM cascade giving an advisory
  second opinion on 7 fidelity axes (wording, code, stable_names, tables, xrefs,
  math, structure), running on self-hosted DeepSeek-V4-Pro (alliance-pod).

## Size / runtime facts

- `facts.py`: 493 source lines (405 non-blank). 5 fact types:
  `present`/`absent`/`order`/`table`/`math` (`facts.py:59-64`).
- Provenance gate: only `checked == "verified"` facts gate
  (`facts.py:68`, `facts.py:124-130`); drafts are evaluated but advisory
  (`facts.py:379-388`).
- Table check: locate cell by normalized exact match, verify
  `up/down/left/right/heading` neighbors within a `max_diffs` Levenshtein budget
  (`facts.py:309-335`). Pipe-table grid parser skips fenced code
  (`facts.py:261-295`). First-match-wins cell location (`facts.py:313-323`).
- Math surface: `pylatexenc` folding keeps `^ _ =` (`facts.py:173-181`).
- Fuzzy presence: exact substring first, then rapidfuzz alignment + exact
  free-start/free-end DP within the widened window (`facts.py:214-236`).
- Corpus: **2 members**. P4182R0 = 8 verified facts (4 present, 1 absent,
  1 order, 2 table; math N/A). P4185R0 = 9 verified facts (4 math, 2 table,
  1 present, 1 absent, 1 order). Counted from
  `packages/whisker/corpus/P4182R0.facts.jsonl` (8 lines) and
  `P4185R0.facts.jsonl` (9 lines).
- CI gate: `packages/whisker/tests/test_comprehension_corpus.py`, hermetic (no
  `WG21_DATA_DIR`), in the `.github/workflows/tests.yml` package matrix, with
  scrambled-cell and scrambled-formula canaries.
- Empirical anchor: one-time blind LLM read-backs, NOT in CI. P4182R0: 3x 8/8
  (incl. both table cells). P4185R0: 9/9 (gpt-5.5-medium, all 4 formulas
  verbatim). Recorded in `corpus/P4182R0.validation.md`,
  `corpus/P4185R0.validation.md`.
- tapetum_llm sighting run 2026-07-01: 196/201 papers, 72 review->pass clears
  (unaudited), 6 fail->review rescues, 0 escalations to tier2, 5 hard JSON
  failures (`packages/whisker/research/tapetum-sighting-run-2026-07-01.md`).

## Load-bearing current-state findings (verified against code at this SHA)

1. **The #277 blocking condition 1 is NOT yet implemented.**
   `tapetum_llm/adjudicate.py:237` still reads
   `if suggested_verdict != VERDICT_PASS and not grounded:` -> a confident `pass`
   whose evidence spans were all dropped by grounding still passes. The #277
   synthesis (2026-07-02) called this CRITICAL/blocking; four days later the code
   is unchanged.
2. **Corpus coverage is 2 papers** against a paperstore of ~200 converted papers
   (sighting run scored 196). No adversarial table paper (multi-column, nested,
   merged cells), no display-math/aligned-environment paper, no code-heavy paper.
3. **Fact schema has no `code` or `xref` or `image-ref` type** while tapetum_llm
   adjudicates 7 axes including code, xrefs, structure. Lane 3 covers 5 of the
   risk classes; code blocks and cross-references are only covered indirectly
   via `present` text.
4. **The 72 review->pass clears from the sighting run remain unaudited** (#277
   blocking condition 2, still open).
5. Thresholds (`UNIGRAM_COVERAGE_FAIL_EDGE` 0.85 etc.) are adopted from external
   repos, "provisional, not yet fitted on our own labeled corpus"
   (`CLAUDE.md` Calibration status section).

## Prior work inventory (do not re-file; re-verify)

All under `packages/whisker/research/` (historical prototype tree, untouched):

- `comprehension-poc-report.md`: the #254 POC. Claim: only olmOCR of 28
  surveyed converters tests comprehension at all. Blind read-back methodology
  documented (3x 8/8, byte-exact run 3).
- `deepseek-v4-pro/` (17 files): #277 complete. Verdict usable-with-conditions;
  3 blocking conditions (grounding gap fix, ground-truth the sighting run,
  vLLM v0.24.0 flags); abstention failure 94% non-abstention; long-context
  degradation past 128K non-deterministic.
- `redteam/` (28 reports): per-converter red-team survey. The claim to
  re-verify in Wave 2: comprehension testing exists only in olmOCR.
- `llm-stack/`, `langextract/`, `persona/`, `buildvsbuy/`: adjacent research
  (LLM serving stack, langextract grounding, whisker metrics red-team,
  build-vs-buy for teds/mhs/nid).
- `tapetum-llm-decision-synthesis.md`, `whisker-llm-lane4-plan.md`,
  `models-vram-deployment-survey.md`, `tapetum-sighting-run-2026-07-01.md`.

## Cloned repos for Wave 2 (31 dirs at `packages/whisker/research/repos/`)

camelot, docling, Dolphin, firecrawl, grobid, html-to-markdown-go,
html-to-markdown-py, html2text, img2table, langextract, markdownify, marker,
markitdown, mdream, MinerU, node-html-markdown, nougat, olmocr,
opendataloader-bench-tmp, opendataloader-pdf, pandoc, PDF-Extract-Kit,
pdf-to-markdown, pdfplumber, PyMuPDF, pymupdf4llm, surya, tabula-java,
tabula-java-tmp (duplicate checkout), turndown, unstructured.

## Persona roster (25)

Generic core (17):

- 01 Security-Reviewer | prompt-injection surface of paper markdown into LLM readers | untrusted text reaching an LLM outside `wrap_source`.
- 02 License-Compliance | provenance of adopted olmOCR/OmniDocBench code and metrics | a license that forbids our use.
- 03 Determinism-Auditor | run-to-run variance in facts/gates/tapetum | non-reproducible verdicts.
- 04 API-Contract-Design | facts schema, CLI contracts, sidecar shapes | a contract docs promise but code breaks.
- 05 Maintainability-Complexity | whisker module coupling, dead code | structure that will rot.
- 06 Performance-Scalability | fact checking and table parsing on giant papers | cost exploding with input size.
- 07 Test-Suite-Auditor | whisker test coverage, vacuous asserts, canary strength | tests passing while behavior is wrong.
- 08 Documentation-Claims | CLAUDE.md / README / POC-report claims vs code | a documented claim the code contradicts.
- 09 Error-Handling-Robustness | facts loader, chunking, tapetum failure paths | a failure mode that hides data loss.
- 10 Adversary-Evasion | make Lane 3 pass while the markdown is unreadable | a false-pass exploit.
- 11 False-Positive-Hunter | facts/gates wrongly failing readable markdown | a correct conversion wrongly rejected.
- 12 False-Negative-Hunter | unreadable markdown the lanes wave through | a broken conversion wrongly accepted.
- 13 Dependency-Supply-Chain | rapidfuzz, pylatexenc, apted, mistune, grits-metric | a fragile or risky dependency.
- 14 Portability-Platform | Windows/Ubuntu CI, encoding (BOM), paths | code that breaks off the author's machine.
- 15 Downstream-Consumer | what dissect/agora actually experience reading our md | a sharp edge that traps the real consumer.
- 16 Product-Decision-Skeptic | does Lane 3 + read-back actually prove #254's goal | mismatch between claim and delivered proof.
- 17 Steelman | strongest honest case FOR the current stack | over-harsh consensus missing real strengths.

Ad-hoc target personas (8):

- 18 Table-Semantics-Auditor | pipe-table grid parser, neighbor checks, merged/nested cells | a table corruption Lane 3 cannot express or detect.
- 19 Math-Fidelity-Auditor | `_math_surface`, pylatexenc folding, display math | a formula corruption the math surface erases.
- 20 Reading-Order-Auditor | order facts, multi-column reflow, coverage-vs-unigram split | scrambled order that still passes.
- 21 Corpus-Coverage-Skeptic | 2 corpus members vs ~200 papers; selection bias | a paper class with zero comprehension coverage.
- 22 Blind-Readback-Methodologist | the 3x 8/8 and 9/9 experiments' rigor | contamination, leading questions, sample size.
- 23 Fact-Assertion-Design | expressiveness of the 5 fact types vs the 7 tapetum axes | a risk class (code, xrefs, images) with no assertable fact type.
- 24 Chunking-Boundary-Auditor | H2 chunking at MAX_PAPER_MD_CHARS, aggregation | content lost or duplicated at chunk seams.
- 25 LLM-Judge-Integration | tapetum lane fit, adjudicate demotions, #277 conditions status | an advisory clear that tells a human not to look, wrongly.

## Web questions (Step 0.5)

1. How exactly does olmOCR's per-fact assertion benchmark work (fact types,
   counts, unit-test integration)? `olmocr benchmark fact assertion design allenai 2026`
2. What does published 2025-2026 research say about LLM comprehension of
   markdown tables (formats, failure modes, pipe vs HTML)? `LLM markdown table comprehension accuracy study 2026`
3. How do document-conversion benchmarks (OmniDocBench, DP-Bench, olmOCR-bench)
   measure downstream readability rather than visual fidelity? `document parsing benchmark downstream QA readability OmniDocBench 2026`
4. What is known about LLM-as-judge pitfalls for conversion QA (grounding,
   abstention, verbosity bias) and mitigations? `LLM as judge document conversion QA grounding hallucination mitigation 2026`
5. Which markdown formatting choices measurably affect LLM reading accuracy
   (heading depth, inline LaTeX, front matter, table style)? `markdown formatting choices LLM readability RAG ingestion study 2026`

---

## Required persona report template

Every persona writes `research/llm-readability/NN-<persona>.md` in EXACTLY this shape:

```
# NN - <Persona name>

**Verdict:** usable | usable-with-conditions | garbage   (+ 1 sentence why)
**Confidence:** high | medium | low

## Findings
- [CRITICAL|HIGH|MED|LOW] <claim>. Evidence: <file:line OR runtime number from 00>.
  Impact: <why it makes the target more/less trustworthy or adoptable>.
  (repeat; 3-8 findings, ranked)

## False-pass hypothesis
<one concrete case the target/our-equivalent would wrongly accept, or "none found">

## False-fail hypothesis
<one concrete case it would wrongly reject, or "none found">

## What would change my mind
<the single piece of evidence that would flip my verdict>
```
