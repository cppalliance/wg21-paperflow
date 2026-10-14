# 00 - Baseline: LLM-QA-Integration across 31 reference repos vs whisker

**Research question (operator's doubt, verbatim intent):** "The other repos have partially
integrated LLMs. Have we taken a *wrong* path by letting deterministic gates decide and
keeping the LLM lane advisory-only?"

**Target:** cross-repo comparison. 31 local clones under
`packages/whisker/research/repos/` (verified non-empty: docling 1555 files, grobid 13896,
marker 296, MinerU 426, olmocr 430, langextract 6311, ...) plus our own
`packages/whisker/` as the comparison codebase.

**Date:** 2026-07-16. **Method:** 6 Composer-2.5 scouts (3 repo-groups with live
`file:line` anchors; 2 groups sourced from June/July 2026 red-team deep-reads because the
scouts misread the clone dirs as empty - flagged for meta-review re-verification; 1 scout
on our own whisker anchors).

---

## 1. The comparison matrix (the core fact sheet)

Three LLM roles: **(a)** LLM produces the conversion output, **(b)** LLM judges/validates
converted output (QA), **(c)** LLM scores benchmarks (LLM-as-judge).

| Repo | (a) conversion | (b) LLM QA of output | (c) LLM-judge bench | LLM signal gates mechanically? |
|---|---|---|---|---|
| marker | optional Gemini processors (`processors/llm/__init__.py:50-67`) | in-path self-QA: table rewrite retried when LLM score < 4 (`llm_table.py:213-225`) | Gemini LLMScorer + Elo, ADVISORY (`benchmarks/overall/scorers/llm.py:94-134`, failures skipped `overall.py:61-63`) | CI blocks ONLY on deterministic means: heuristic >= 90, TEDS >= 0.7 (`benchmarks/verify_scores.py:12-22`) |
| MinerU | VLM backend is the engine (`vlm_analyze.py:222-238`); optional OpenAI title leveling | none | none in tests | E2E hard-fails on fuzz.ratio > 90 + substring rates (`test_e2e.py:163-219`); LLM title failure is fail-soft no-op (`llm_aided.py:221-223`) |
| olmOCR | VLM produces all page markdown (`pipeline.py:106-146`) | in-pipeline mechanical checks (finish_reason, rotation) -> retry/fallback, no judge model | NO: bench gates on committed JSONL facts, LLM only MINES candidate facts, humans curate via review app (`bench/tests.py:150-176` TextPresenceTest gate logic, `review_app.py:54-57` verified-count; note: `checked` is a curation-workflow flag, benchmark.py evaluates the full loaded set, not a verified-only runtime filter) | bench blocks on fact pass-rate; pipeline never hard-fails a page (temp escalation -> pdftotext fallback `pipeline.py:329-332`) |
| docling | VlmPipeline VLM output (`vlm_pipeline.py:236-274`); caption VLM | NO judge; deterministic ConfidenceReport (`base_models.py:540-577`); agent-skill evaluate script is heuristic (`docling-evaluate.py:133-215`) | none | grades never block conversion; layout clusters dropped below per-label thresholds (`layout_postprocessor.py:175-193`, drop site `:264-268`) |
| surya | VLM is the engine (`inference/backends/openai_client.py`) | none; mean_token_prob is telemetry (`inference/schema.py:33-35`) | none (smoke tests) | mechanical reroute on repeat/blank/parse-error -> fallback lane (`recognition/__init__.py:292-315`); confidence never gates accept |
| Dolphin | Qwen2.5-VL end-to-end (`demo_page.py:186-307`) | none | none in-repo (external OmniDocBench) | bad layout JSON -> distorted_page fallback (`demo_page.py:203-208`); no quality abort |
| nougat | VLM+MBart decode (`model.py:229,591-607`) | none | string metrics BLEU/edit (`metrics.py:28-44`) | logit-variance repeat detection truncates + flags PAGE inclusion (`model.py:614-649`), not pipeline abort |
| PDF-Extract-Kit | UniMERNet formula rec; rest CV/OCR | none | docs "Coming Soon" | detection-confidence thresholds filter boxes; scores are metadata |
| langextract | LLM extraction is the product (`annotation.py:404-431`) | DETERMINISTIC alignment validation of LLM output: exact token DP -> partial -> fuzzy LCS 0.75 (`resolver.py:1006-1014,691-707`) | grounding-rate metrics, no judge (`benchmarks/benchmark.py:227-231`) | parse errors dropped fail-soft by default; `prompt_validation_level=ERROR` can raise (`prompt_validation.py:237-266`) |
| firecrawl | optional /extract + clean via GPT (LLM-path gate `llmExtract.ts:959-972`, passthrough `:1127`, clean opt-in `:1134-1136`, LLM call `:811`, clean prompt `:1193`) | none | external scrape-evals repo | CI hard-fails on 348 toContain anchors across 36 test files (live count 2026-07-16) + shadow tiers; LLM outputs only checked by deterministic asserts |
| markitdown | optional vision captioning / OCR plugin | none | none | must_include/must_not_include hard-fail CI (`_test_vectors.py:11-12`) |
| mdream | none | none | ops/sec only | snapshots + ratio gates hard-fail (`fixture-parity.test.ts:76-78`) |
| opendataloader-pdf(+bench) | none | none | NO: NID/TEDS/MHS vs ~200-doc human GT | check_regression blocks CI on corpus means (`opendataloader-bench-tmp/src/run.py:53-117`, thresholds `:69-96`, fail return `:110-114`; invoked via `opendataloader-pdf/scripts/bench.sh:83` - companion repos); thresholds hand-set |
| 15 classic converters (pandoc, html2text, turndown, pdfplumber, PyMuPDF, pymupdf4llm, camelot, img2table, tabula-java, grobid, ...) | none (pymupdf4llm: marketing name only; grobid: CRF/DeLFT ML, not LLM) | none | none | golden/snapshot tests hard-fail byte- or AST-exact (pandoc `test/Tests/Old.hs:380-408`; go goldie `goldenfiles.go:63-78`; pdfplumber committed text files) |

## 2. The load-bearing observation

Across all 31 repos, **zero** use an LLM quality signal as a mechanical CI/accept gate for
converted output. The observed division of labor is uniform:

1. **LLM in the conversion path**: common (8/31), always paired with mechanical
   guards (schema validation, repeat detection, temp-0 pins, retries, fallback lanes).
2. **LLM as QA judge of output**: essentially absent. Closest analogues: marker's
   in-loop table-rewrite retry (LLM score triggers RETRY of its own rewrite, never
   accept/reject of the document) and docling's deterministic ConfidenceReport (no LLM).
3. **LLM as benchmark judge**: only marker, and there explicitly advisory (skipped on
   failure), with CI gating on the deterministic axes instead.
4. **Ground truth**: human-labeled or human-verified everywhere it matters. olmOCR is
   the strongest precedent: LLM *mines* candidate facts, a human review app marks
   `checked: verified`, the bench gates only on verified facts.

**Where whisker sits:** the same architecture, plus pieces most references lack: an
advisory LLM lane with verdict fusion (`fusion.py:15-24`), evidence grounding
(`grounding.py:171-241`, same DP->fuzzy pattern as langextract `resolver.py`), a per-page
recall screen, and 995 tests (live `--collect-only` count 2026-07-16; the "986 green" in
section 5 is an earlier point-in-time count from the MC2 session). Numbers: gates.py 219
LOC decides; tapetum_llm ~4751 LOC advises. Fresh empirical anchor (2026-07-16 PR re-run):
det+advisory-LLM agreement with human verdicts went 4/9 -> 5/9 -> 8/9 (Run 1 -> Run 2
after the F1 false-pass fix -> Run 3 after the no_toc_leak gate + TOC prompt rule); every
one of the 4 new hard fails came from the deterministic gate; the LLM confirmed and
localized.

## 3. Comparison anchors (our code)

- `packages/whisker/src/whisker/gates.py:209-218` - 6 hard gates.
- `packages/whisker/src/whisker/score.py:136-231` - `_decide` trichotomy; unigram floors
  `constants.py:37-38` (0.85 fail / 0.95 review).
- `packages/whisker/src/whisker/tapetum_llm/fusion.py:124-252` - fusion matrix; LLM can
  rescue/escalate to review, can clear soft-review to pass under guardrails, can NEVER
  hard-fail or override a det fail.
- `packages/whisker/src/whisker/tapetum_llm/grounding.py:171-241` - evidence grounding.
- `packages/whisker/src/whisker/CLAUDE.md:34-35,475-477` - "no LLM in the gate", advisory.
- Repo `CLAUDE.md` - Model sovereignty + Determinism sections (design constraints that
  forbid cloud-LLM gating regardless of ecosystem practice).

## 4. Documented weaknesses of OUR approach (personas: attack here, do not re-file)

| Known gap | Anchor |
|---|---|
| Heading-level blind spot (HTML lane) | `research/tapetum-golden-review-findings-2026-07-14.md:60-82`; PR #282 pass/1.00 vs human request-changes |
| Selection gap (clean-pass corruption never reaches LLM under --review-all) | whisker `CLAUDE.md:490-492` |
| Confidence uncalibrated (0.85-1.00 everywhere, incl. wrong verdicts) | RULERS flood analysis 2026-07-15: 64% of passes have 0 grounded evidence by design |
| Two-tier cascade: confidence band alone proved dead (0/198 escalations); mechanism widened 2026-07-16 (derived signals axis_conflict/ungrounded_evidence added, `adjudicate.py:230-253`); empirical rate under new triggers not yet re-measured | findings doc `:86-89`; `constants.py:32-40` |
| Unigram floors provisional, not corpus-fitted | whisker `CLAUDE.md:414-418` |
| LLM reasoning contradicts itself ("sanctioned TOC leak" while flagging it) | A/B run 2026-07-16, p0957r8/p1122r3 sidecars |

## 5. Prior work (re-verify, do not re-file)

Existing syntheses: `research/golden-qa-gap/SYNTHESIS.md` (5 miss-classes MC1-MC5),
`research/per-page-judging/SYNTHESIS.md` (per-page screen calibration),
`packages/whisker/research/llm-stack/` (pass-channel grounding gap),
`research/hybrid-llm-scoring/`, `research/vlm-pdf-qa/`. The 2026-07-16 session closed
MC2 (TOC leak: det gate + prompt rule + fusion prefix-match fix, 986 tests green).

## 6. Caveat for meta-review

Scouts for the "classic 15" and "firecrawl/markitdown/mdream/opendataloader" groups cited
June-2026 red-team notes instead of the live clones (they misdiagnosed the clone dirs as
empty; verified non-empty on 2026-07-16). Their claims match prior deep-reads but need
spot re-verification against the actual clones (assigned: persona 25 Evidence-Historian,
meta-reviewer D).

**ROOT CAUSE (found 2026-07-16, after persona stage):** `packages/whisker/research/.gitignore`
line 4 ignores `repos/`. Gitignore-respecting search tools (agent Glob/Grep) therefore see
the clones as empty; the directories are fully populated (marker 296 files, langextract
6311, pandoc 2805, verified via filesystem listing). Consequence for verification:
**use `rg --no-ignore --no-ignore-vcs`, plain `Get-ChildItem`, or direct file reads with
exact paths.** Persona findings that fell back to secondary sources (P18 langextract
lines "verified vs upstream", P24 reference anchors, both classic-scout groups) must be
re-checked in the live clones with ignore-bypassing search.

---

## Required persona report template

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

Note for personas: "the target" of this research is the ARCHITECTURE QUESTION
(deterministic-gates-decide + advisory-LLM vs LLM-integrated alternatives), evidenced by
the 31 repos and our whisker code. Verdict semantics: "usable" = our current path is
sound as evidenced; "usable-with-conditions" = sound but with named adoptable upgrades;
"garbage" = the ecosystem evidence says we took the wrong path.
