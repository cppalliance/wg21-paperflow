# 00 - Evidence Baseline: Hybrid Deterministic + LLM Scoring

Date: 2026-07-07. Author: parent agent (Fable 5), grounded in code reads + the 2026-07-06 whisker run.

## Research goal (one sentence)

Find out how the 31 surveyed converter/extraction repos use LLMs for scoring/eval, especially HYBRID (deterministic + LLM) score fusion, and derive what whisker should adopt to (1) keep LLM scoring, (2) persist it in `data/whisker/` alongside the deterministic results (ideally same file), and (3) produce a MERGED score (deterministic + LLM = combined) that is also shown separately per lane.

## Our substrate (comparison anchors, file:line)

All paths relative to `c:\Users\sabo2\Desktop\cppalliance\`.

### Deterministic lane (whisker core)

- `packages/whisker/src/whisker/score.py`
  - `_decide` (~line 118-184): verdict = rules, NOT a score. Hard fails: any gate failure, `unigram_coverage < UNIGRAM_COVERAGE_FAIL_EDGE` (0.85). Soft (review): coverage band 0.85-0.95, drift > 0.1, misaligned regions, qa < edge, uncertain markers, `ref_nid < 0.85` (advisory).
  - `WhiskerResult` (~line 53-115): fields incl. `ref_nid/ref_teds/ref_mhs/ref_overall` (advisory oracle agreement; `ref_overall = (nid+teds+mhs)/3` at line ~215). `to_dict` is schema-versioned (`schema_version: 3`, `constants.py WHISKER_SCHEMA_VERSION`).
- `packages/whisker/src/whisker/report.py`
  - `render_report_md` (~line 98-142): PID-sorted leaderboard table `| PID | verdict | overall | nid | teds | mhs | unigram | coverage | drift | qa | regions | flags |`.
  - `_worst_first` (~line 145-163): triage sort by `unigram_coverage`, then `ref_overall` tiebreak, then pid.
  - `render_summary`: pytest/ruff-style terminal triage (fail + review sections, footer).
- `packages/whisker/src/whisker/__main__.py` `_score_main` (~line 234-257): persists `<pid>.whisker.json` sidecar per paper + `report.json` + `report.md` into `data/whisker/`.
- `packages/whisker/src/whisker/bench.py`: the ONLY true numeric composite (`overall` = mean of eligible axes vs labeled GT, line ~235-243). Gate mode has NO composite by design.

### LLM lane (tapetum_llm, advisory)

- `packages/whisker/src/whisker/tapetum_llm/models.py`
  - `Adjudication` (pydantic output_type): `reasoning`, `axis_findings[7 axes]`, `worst_axis`, `verdict`, `confidence [0..1]`, `evidence_spans`, `primary_concern`.
  - `TapetumResult.to_dict` (~line 114-136): persisted JSON incl. `whisker_verdict`, `suggested_verdict`, `confidence`, `escalated`, `axis_findings`, `grounded_evidence`, `"advisory": true`.
- `packages/whisker/src/whisker/tapetum_llm/cli.py`
  - `_persist_result` (~line 207-217): writes `<pid>.whisker.tapetum.json` NEXT TO the whisker sidecar (separate file, same dir).
  - `_persist_inspect` (~line 231-243): writes `tapetum-inspect.md` side-by-side report.
- `packages/whisker/src/whisker/tapetum_llm/chunking.py` `worst_axis_verdict` (~line 34-51): severity-aware fold (axis `fail` only forces overall fail when severity `major`).
- `packages/whisker/src/whisker/tapetum_llm/adjudicate.py`: `select_candidates` (3 populations: PRIMARY pass-tier risk signals, SECONDARY non-benign reviews, RESCUE heading-monotone-only fails), two-tier cascade (fast triage -> deep escalate in ambiguity band).

### Hard constraints (from `packages/whisker/src/whisker/CLAUDE.md` and root `CLAUDE.md`)

- C1. tapetum_llm NEVER gates, is never in the `whisker --gate` CI contract, and NEVER overwrites the whisker verdict on record.
- C2. Isolation invariant: whisker core never imports `tapetum_llm`; the lane imports core read-only (one-way).
- C3. Determinism: deterministic lane is a pure function; LLM lane is quality-stable, serial by default.
- C4. Library returns data; only CLI persists. Thresholds are named constants. Schema changes bump `WHISKER_SCHEMA_VERSION`.
- C5. Fidelity: never produce a partial result mistakable for a complete one.

Any merge design MUST satisfy C1+C2: a merged score can be a REPORTED composite (new artifact/lane), not a change to the deterministic verdict on record.

## Runtime facts (2026-07-06 run, terminal evidence)

- Deterministic: 381 scored, 134 pass / 232 review / 15 fail, 1069.5s.
- tapetum: 200 candidates, 194 adjudicated: 101 pass / 76 review / 17 fail / 6 error, 118 model retries, 4826.0s. 123 of 194 DIFFER from the whisker verdict.
- Sidecar examples on disk: `data/whisker/p4182r0.whisker.json` (schema 3, verdict review, `ref_overall 0.3083`), `data/whisker/p4003r0.whisker.tapetum.json` (whisker review -> tapetum fail, confidence 0.95, escalated, tables axis fail/major).
- 6 tapetum errors = truncated/invalid JSON after retries (e.g. P2728R11/12, P3568R2, P3904R1, P3951R1, P4233R0): today they leave NO tapetum sidecar verdict; a merge design must handle "LLM lane absent/errored".

## Targets (cloned repos, analyze in place, read-only)

Root: `packages/whisker/research/repos/`. Repos: camelot, docling, Dolphin, firecrawl, grobid, html-to-markdown-go, html-to-markdown-py, html2text, img2table, langextract, markdownify, marker, markitdown, mdream, MinerU, node-html-markdown, nougat, olmocr, opendataloader-pdf, pandoc, PDF-Extract-Kit, pdf-to-markdown, pdfplumber, PyMuPDF, pymupdf4llm, surya, tabula-java, turndown, unstructured.

High-prior candidates for LLM/hybrid scoring: olmocr (LLM-judge benchmark), marker (`--use_llm` hybrid), opendataloader-pdf (deterministic local + AI hybrid mode, published benchmark 0.907), MinerU, docling, Dolphin, langextract (grounding/char intervals), firecrawl (LLM extraction), unstructured, grobid (consolidation confidence), surya (benchmarks), nougat (repetition detection heuristics).

## Prior work (MUST read before re-filing findings)

- `packages/whisker/research/tapetum-llm-decision-synthesis.md` (why the LLM lane looks the way it does)
- `packages/whisker/research/redteam/*.md` (olmocr, MinerU, Dolphin, camelot, pdfplumber deep reads)
- `packages/whisker/research/llm-stack/*.md` (esp. 00-baseline, 06-performance, 11-false-positive-hunter)
- `packages/whisker/research/persona/` + `packages/whisker/notes/QA-RELIABILITY-VERDICT.md`
- `packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md` (authority doc: axes, prompts, cascade)

## The three user goals (what findings must serve)

1. KEEP LLM scoring (tapetum lane stays; possibly upgraded with adopted mechanics).
2. PERSIST LLM scoring in `data/whisker/` the way the deterministic lane does, ideally continuing/extending the same per-paper file so both lanes are visible in one place.
3. MERGED scoring: deterministic + LLM = combined verdict/score, with BOTH lanes still individually visible next to the merged value (report.md, terminal, JSON).

## Required persona report template (every persona uses exactly this shape)

```
# NN - <Persona name>

**Verdict:** usable | usable-with-conditions | garbage   (+ 1 sentence why)
**Confidence:** high | medium | low

## Findings
- [CRITICAL|HIGH|MED|LOW] <claim>. Evidence: <file:line OR runtime number from 00 OR URL>.
  Impact: <why it matters for goals 1-3>.
  (repeat; 3-8 findings, ranked)

## False-pass hypothesis
<one concrete case a merged det+LLM score would wrongly accept, or "none found">

## False-fail hypothesis
<one concrete case a merged det+LLM score would wrongly reject, or "none found">

## What would change my mind
<the single piece of evidence that would flip my verdict>
```
