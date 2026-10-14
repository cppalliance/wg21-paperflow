# 00 - Baseline: All-Pages LLM Coverage (golden-review mode)

Date: 2026-07-22. Workspace SHA: 51cb704. Orchestrator: Fable 5 (baseline, meta-review, synthesis). Personas: composer-2.5-fast.

## Research question

When `whisker-tapetum-llm` reviews a golden-PR PDF, the operator expects the LLM to compare EVERY physical PDF page against the candidate markdown. Today it does not. Question for the swarm: **how do comparable OSS systems (docling, langextract, marker, olmocr, MinerU, Dolphin, nougat, surya, grobid, unstructured, opendataloader) guarantee that every page of a PDF is processed or validated by an LLM/VLM, and what should our `--all-pages` review mode adopt from them?** Distinguish EXTRACTION coverage (LLM converts every page, trivially "all pages") from VERIFICATION coverage (LLM judges every page against an output). The user's complaint compares us to extraction pipelines; the swarm must establish whether that comparison holds and what the honest prior art for full-coverage verification is.

## What the target is

Target (self): `packages/whisker/src/whisker/tapetum_llm/` - the opt-in advisory LLM lane of whisker (tomd QA). PDF path: monolith judge call over full text layer + deterministic per-page recall screen + scoped LLM escalation on flagged pages + source-aware unit checks on ROUTED risky pages only. Entry: `cli.py` (`whisker-tapetum-llm`), PDF lane `pdf_judge.py::judge_pdf_extraction`, unit checks `unit_judge.py::run_unit_checks`, risk routing `source_router.py::route_pdf_units`.

## Size

LOC (non-blank lines incl. docstrings, `Get-Content | Measure-Object -Line`): cli.py 1182, pdf_judge.py 851, adjudicate.py 686, unit_judge.py 624, grounding.py 556, fusion.py 465, source_router.py 312, textlayer.py 308, constants.py 203. Tests live in `packages/whisker/tests/` (test_pdf_judge.py, test_source_aware_integration.py, test_tapetum_llm.py, test_incremental.py).

## Runtime facts (the defect, verified 2026-07-22)

- Live run on P1068R11 (PR #286 golden, 15-page PDF) with `--inspect --trace --debug`: only **5 of 15 pages** received a scoped LLM unit check. 10 pages were never individually seen by the LLM (only inside the single monolith prompt).
- Root cause 1 (unwired flag): `cli.py:1186-1187` passes `exhaustive=args.exhaustive_units or args.inspect` ONLY to the text/HTML lane (`adjudicate_paper`). The PDF branch `cli.py:1120-1127` calls `judge_pdf_extraction(pid, backend, judge_agent, debug_log=...)` with NO exhaustive parameter. `--exhaustive-units` and `--inspect` are silently dead for PDFs.
- Root cause 2 (no pass-through): `pdf_judge.py:843-850` calls `run_unit_checks(...)` without the `exhaustive` kwarg, so the PDF lane always caps at `MAX_UNIT_CHECKS = 5` (`constants.py:223`, cap applied at `unit_judge.py:304`).
- Root cause 3 (routing, not coverage): `unit_judge.py:287-288` returns `None` when `route_pdf_units` yields no risk signals; a page with NO signal is never checked even in exhaustive mode. Exhaustive means "all ROUTED units", never "all pages". Router signal types: token_delta, low_recall, missing_captions, heading_drift, table_presence (`source_router.py:200-260`).
- Adjacent caps: deterministic per-page recall screen flags pages below `PAGE_RECALL_FLOOR = 0.90` (`constants.py:178`), escalation capped at `MAX_PAGE_ESCALATIONS = 5` (`constants.py:191`); pages under `PAGE_MIN_TOKENS = 50` are skipped (`constants.py:183`).
- Timeout budget is sized for capped mode: `cli.py:140-157` budgets `monolith + MAX_PAGE_ESCALATIONS*PAGE_ESCALATION_TIMEOUT + (1+MAX_UNIT_CHECKS)*UNIT_CHECK_TIMEOUT`; an all-pages run on a 40-page paper would blow this budget.
- Serial execution: one in-flight LLM request (workspace determinism rule D11); an all-pages run on an n-page paper costs n serial unit calls.

## Prior work (re-verify, do not re-file)

`research/per-page-judging/SYNTHESIS.md` (2026-07-14, personas 10-21) established, for FLEET mode:

1. No surveyed repo runs an LLM per page for verification. olmocr-bench is page-scoped but deterministic (fuzzy fact presence, no LLM in the eval loop).
2. Worst-page-wins noise math: doc false-review rate `1-(1-p)^n`; at n=33 and p=1%/page that is 28.1%.
3. 33 serial calls = 4.4-15 min/paper; corpus cost explodes.
4. Verdict: deterministic per-page screen + scoped escalation (now implemented). That design is the CURRENT code.

The new question is NOT fleet mode. It is REVIEW mode (one paper, golden PR, operator explicitly requests full coverage, pod billed hourly). The old cost/noise objections must be re-weighed under review-mode assumptions: n is 10-40 not 189 papers, false flags are triaged by a human, and a missed defect in a golden is permanent. Personas must say explicitly which prior findings survive the mode change and which do not.

## Comparison anchors (our code the verdict lands on)

- `unit_judge.py::run_unit_checks` (required-units extension point).
- `pdf_judge.py::judge_pdf_extraction` (all-pages orchestration + sidecar audit fields).
- `cli.py` arg parsing/validation/timeout/fingerprint (`_compute_fingerprint`, `_pdf_judge_timeout_seconds`).
- `models.py::PdfJudgeResult` sidecar schema.
- Planned change (draft plan exists): `--all-pages` flag forcing every `page:N` as a required unit, fail-closed coverage check against `page_count`, sidecar audit fields, separate fingerprint.

## Clone corpus (read in place, never modify)

`packages/whisker/research/repos/` at these SHAs: olmocr f7cfe4c, docling fbd39b8, langextract 0dff547, marker ef16c2c, MinerU 3e60291, Dolphin befa5da, nougat 5a92920, surya 11d1884, grobid 4a5aadf, unstructured f6eea75, opendataloader-pdf ddd3d8e, opendataloader-bench-tmp 7af1d8f, markitdown e144e0a, pymupdf4llm 288fe55, pdfplumber 4c64b92, PyMuPDF cbb2f4d, PDF-Extract-Kit fdb25fd, camelot 39ba78c, firecrawl 183d750, img2table fba4873, others present but out of scope.

## Required persona report template

Every persona writes exactly this shape to `research/all-pages-llm-coverage/NN-<persona>.md`:

```
# NN - <Persona name>

**Verdict:** usable | usable-with-conditions | garbage   (+ 1 sentence why)
**Confidence:** high | medium | low

## Findings
- [CRITICAL|HIGH|MED|LOW] <claim>. Evidence: <file:line OR runtime number from 00 OR URL from 05-web.md>.
  Impact: <why it makes the target more/less trustworthy or adoptable>.
  (repeat; 3-8 findings, ranked)

## False-pass hypothesis
<one concrete case the target/our-equivalent would wrongly accept, or "none found">

## False-fail hypothesis
<one concrete case it would wrongly reject, or "none found">

## What would change my mind
<the single piece of evidence that would flip my verdict>
```

For repo-analyst personas, "verdict" grades the surveyed repo's coverage mechanism as prior art for OUR review mode (usable = we should copy it). For our-code personas, "verdict" grades our planned `--all-pages` design.
