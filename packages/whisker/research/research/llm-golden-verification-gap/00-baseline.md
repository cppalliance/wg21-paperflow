# 00 - Evidence Baseline: Why can't we verify golden-PR candidates 100% with the LLM lane?

Date: 2026-07-22. Repo HEAD: `51cb704610220d31c9d5e078b1350c1b37a8714a` (dirty working tree,
pre-existing; dirtiness is itself a recorded reproducibility caveat in
`packages/whisker/research/improvement-bugs/PR286-LLM-FALSE-CLEAR.md`).

## Research question (the one sentence every persona answers)

Despite ~13k LOC of QA code, 31 studied reference repos, and 10+ prior research syntheses,
the source-aware LLM lane keeps failing to name the real, human-verified defects in
golden-ideal PR candidates (recall ~0 on the two most recent reviews). **Where exactly is
the recall lost, is that loss fixable, and is "100% LLM verification of goldens" even an
attainable target, or the wrong metric?**

## What the target is

`packages/whisker` is deterministic QA for tomd's PDF/HTML->Markdown conversions
(three lanes: stability, fidelity, comprehension) plus an opt-in, advisory,
never-gating LLM lane `whisker.tapetum_llm` (PDF text-layer judge, HTML text cascade,
source-aware unit routing v6, two-sided evidence verification, deterministic fusion).
Entry points: `whisker` CLI (`__main__.py`), `whisker-tapetum-llm` (`tapetum_llm/cli.py`).
Authority docs: `packages/whisker/src/whisker/CLAUDE.md`, `tapetum_llm/tapetum_llm.md`.

## Size (measured 2026-07-22)

- whisker core: 5,594 LOC (`packages/whisker/src/whisker/*.py`).
- tapetum_llm: 24 modules, ~7,800 LOC. Largest: `cli.py` 1173, `pdf_judge.py` 848,
  `fusion.py` 456+258, `grounding.py` 556, `unit_judge.py` 543, `adjudicate.py` 590,
  `readback.py` 407+190, `models.py` 352, `textlayer.py` 308, `source_router.py` 279,
  `html_outline.py` 177. Dormant VLM stack: `vision*.py`, `vlm_*.py`, `transcribe.py` (~460).
- Tests: 36 files under `packages/whisker/tests/`.
- Comparison repos: 31 clones under `packages/whisker/research/repos/`.

## Runtime facts (from the two most recent branchless golden reviews, both 2026-07-22)

Both runs used local code at HEAD above, fresh temp workspaces, exact PR-head bytes.
Full report: `packages/whisker/research/improvement-bugs/PR286-LLM-FALSE-CLEAR.md`.

### PR #286, P1068R11 (PDF, head `ffa54f8f...`, source sha `a686518789b7...`, candidate sha `e79079f289eb...`)

- Human-verified blocker: 6 poll tables (candidate lines 382/394/405/415/425/433) transcribe
  the vertically wrapped first header cell `SF` as `S` (source pages 8-9; cell boundaries
  proven by PyMuPDF geometry: column x = 72.5/95.5/110.5/127.5/144.5/167.5, wrapped `S`+`F`
  at x=77.25 vs separate second-column `F` at x=100.5).
- Deterministic verdict: `pass`, all 6 gates green, QA 100.
- LLM lane: verdict `review` conf 0.98, metadata/outline `pass`. Routed pages
  1,2,3,4,5,6,8,9,13; checked 1,2,3,4,13; **pages 8/9 routed but displaced** by
  `MAX_UNIT_CHECKS = 5` (`tapetum_llm/constants.py:223`) under severity-then-LEXICAL
  unit-id sort (`tapetum_llm/unit_judge.py:225-241`, `page:13` < `page:2` lexically).
- One generated claim (page-13 heading numbers) was FALSE and died in evidence
  verification (`ambiguous=1`); accepted defect groups: 0. True-positive groups: 0/1.
- Fusion: `review` via `source_aware_review_cap` = coverage caution, not detection.
- `PageUnit.has_tables` exists (`tapetum_llm/textlayer.py:86-98`) but `route_pdf_units`
  (`tapetum_llm/source_router.py:149-233`) never reads it; **no table-cell comparison
  exists anywhere in the lane**.

### PR #295, P3953R0 (HTML, head `0bd71bf9...`, source sha `2aa5d2dda5b7...`, candidate sha `f4988f05cf5a...`)

- Human-verified blocker: 4 H2 headings retain bikeshed `span.secno` labels
  (`## 1. Abstract` ... `## 4. Impact on existing code`); golden contract requires the
  label stripped, H2 level kept.
- LLM lane metadata/outline: **`pass` with empty heading_drift** (verified from the saved
  sidecar). Root cause: `html_outline.py:66-81` collects ALL heading descendant text, so
  source outline says `1. Abstract` == candidate `1. Abstract`; the normalization rule
  exists only in the human contract, never in the prompt or the comparison.
- Routing produced 3 signals (verified from saved sidecar
  `whisker-pr295-p3953r0-.../whisker/llm/p3953r0.whisker.tapetum.json`):
  `section:0` h1 title "candidate missing" (false: it maps to YAML front matter; also the
  `<br>` in `<h1>` concatenates to `P3953R0Rename std::runtime_format`),
  `section:1` subtitle "candidate missing" (false: bikeshed chrome `no-num no-toc no-ref`),
  `section:6` recall 0.0437 (polluted: `_SectionExtractor` does not exclude `<script>`/
  `<style>` content). Checked: section:1, section:6. `section:0` routed but **no source
  packet resolved** (empty-body title section) -> silently unchecked.
- Generated defect claims: 0. Structure-only recall: 0/1 groups, 0/4 headings.
- Fusion: `review` via `source_aware_review_cap`, again coverage-only.

### Stability / calibration facts (from `packages/whisker/src/whisker/CLAUDE.md`, "Why the LLM never gates")

- Identical reruns on the alliance pod: >= 25% verdict-flip rate (same paper/model/prompt).
- Self-reported confidence anti-calibrated: 96/96 clear firings at >= 0.95 confidence,
  including a false-clear at 1.00 (PR #282 p4020r0).
- 0 of 31 surveyed document-conversion QA repos gate mechanically on LLM signals.
- Evidence verification (`tapetum_llm/grounding.py`) is a PRECISION control (two-sided:
  source grounding + candidate classification); it has zero RECALL power: claims the
  model never generates are invisible to it (report section 6.5).
- Schema validators force internal consistency only: `UnitCheck.verdict_matches_defects`
  (`tapetum_llm/models.py:315-320`) accepts pass-with-empty-defects; it cannot force the
  model to have looked at the right thing (proven by the page-13 false-clear on the
  historical PR #286 run: unit checked the heading signal, ignored malformed inline code).

## The five candidate answer classes (personas must place their findings in one)

1. **Contract-encoding gap**: golden-contract rules (secno stripping, wrapped-cell
   reading, TOC policy...) live in human skill docs, not in deterministic preprocessing
   or prompts. The LLM is asked to rediscover rules nobody told it.
2. **Routing/budget starvation**: real defect units are routed but displaced (lexical
   sort, MAX_UNIT_CHECKS=5, noisy same-severity heading signals), or never routed
   (defect classes with no signal type: table cells, list cardinality, inline-code
   rendering, punctuation-only loss).
3. **Model capability ceiling**: even when the right unit reaches the model with the
   right prompt, deepseek-v4-pro misses (page-13 false-clear) or hallucinates
   (page-13 false claim), with anti-calibrated confidence and >=25% verdict flips.
4. **Verification asymmetry**: the pipeline can only subtract (refute/abstain), never
   add; zero generated claims short-circuits everything downstream.
5. **Goal mis-specification**: "100% LLM verification" may be unattainable in principle
   (no surveyed repo does it; ecosystem uses LLM for triage only). The honest ceiling
   may be "deterministic tripwires find the countable defects; LLM triages the rest".

## Comparison anchors (our code the verdict must land on)

- `packages/whisker/src/whisker/tapetum_llm/{source_router,unit_judge,html_outline,textlayer,pdf_judge,adjudicate,grounding,models,fusion,constants}.py`
- Deterministic lane: `packages/whisker/src/whisker/{gates,score,metrics,golden_ideals}.py`
- Corpus: `packages/whisker/corpus/dev-replay/labels.json` (stale v1 schema),
  `packages/whisker/corpus/holdout/manifest.json` (locked; never tune on it).
- Open P0 remediation plan (already designed, not yet implemented):
  `.cursor/plans` "Whisker P0 Remediation Bundle" - personas should treat its five fixes
  (replay identity, heading normalization, table-cell compare, scheduling, HTML packets)
  as hypotheses to confirm/refute/extend, not as settled truth.

## Prior work to RE-VERIFY, not re-file (the "ALL our research results" axis)

`research/` (top level): golden-qa-gap, llm-qa-integration (advisory-only decision),
llm-evidence-reliability, hybrid-llm-scoring, per-page-judging, vlm-pdf-qa,
llm-readability, llm-readability-fixpath, concurrency-381, slots-32-regression.
`packages/whisker/research/`: persona/ (prototype swarm, 30 personas + 5 opus),
Audit/Auditv1 + Auditv2 (29 code claims + 30 papers each), improvement-bugs/,
deepseek-v4-pro/, llm-batching/, llm-stack/, langextract/, base64-blob-filter/,
redteam/, buildvsbuy/, comprehension-poc-report.md, tapetum-eval-report.md,
tapetum-golden-review-findings-2026-07-14.md, tapetum-llm-decision-synthesis.md,
tapetum-sighting-run-2026-07-01.md, toc-ab-experiment.md, models-vram-deployment-survey.md.

Each archaeology persona answers: (a) what did that corpus conclude, (b) which
conclusions were implemented in code (cite file:line), (c) which were ignored/dropped,
(d) does anything in it already predict/explain the PR #286/#295 misses, (e) what does
it imply for the five answer classes.

## Rules of engagement (binding for every subagent)

- READ-ONLY on all code, corpora, and repos. You may run `rg`, `git log/show` (read-only),
  and small `python -c` counting snippets. NEVER modify files outside
  `research/llm-golden-verification-gap/`, never run LLM services, never touch
  `WG21_DATA_DIR`, never run `pytest` (too heavy for this stage).
- Every finding cites `file:line`, a runtime number from this baseline, or a URL from
  `05-web.md`. Argue against these numbers, not guesses.
- The TEMP artifacts cited above may have been cleaned; the numbers in this baseline are
  the verified record. Do not fail your task if TEMP paths are gone.

## Required persona report template (verbatim)

```
# NN - <Persona name>

**Verdict:** usable | usable-with-conditions | garbage   (+ 1 sentence why)
**Confidence:** high | medium | low

## Findings
- [CRITICAL|HIGH|MED|LOW] <claim>. Evidence: <file:line OR runtime number from 00 OR URL>.
  Impact: <why it makes the target more/less trustworthy or adoptable>.
  Answer-class: <1|2|3|4|5 from the baseline's five classes>.
  (repeat; 3-8 findings, ranked)

## False-pass hypothesis
<one concrete case the target/our-equivalent would wrongly accept, or "none found">

## False-fail hypothesis
<one concrete case it would wrongly reject, or "none found">

## What would change my mind
<the single piece of evidence that would flip my verdict>
```
