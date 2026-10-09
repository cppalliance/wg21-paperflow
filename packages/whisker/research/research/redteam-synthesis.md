# Red-Team Synthesis: 28 Repos vs `guard.py` + `calibrate.py`

Second-pass swarm (June 2026): 28 `composer-2.5-fast` subagents each deep-read one
external repo (now in `research/repos/`) and adversarially hunted gaps/bugs in the
newly built regression guard and calibration fitter. Raw reports:
`research/redteam/<repo>.md`. This note ranks the CONSENSUS findings (how many of
the 28 independently raised each) and records the fix decision.

## Tier 1: real bugs, near-unanimous, fixed this pass

| # | Bug | Agents flagging | Fix |
|---|-----|-----------------|-----|
| 1 | `diff_rows` writes `axis_slack` + `floors` into the baseline but **never reads them** (always live `constants.py`/CLI) | ~24/28 | Baseline floors/slack are now authoritative; `--slack` overrides only when explicitly passed |
| 2 | **NaN/inf axis values pass silently** (`x < floor` is False for NaN) in `_evaluate_paper`; same in `calibrate_threshold` | ~18/28 | New `STATUS_INVALID` hard-fail in guard; `ValueError` on non-finite samples in calibrate |
| 3 | `calibrate` can fit **`fail_edge > review_edge`** (inverted band) when the two edges are fit independently | ~16/28 | CLI enforces ordering: warns + records `edge_ordering_ok`; never silently ships an inverted band |
| 4 | No **`kind`/`schema_version` validation** of the loaded baseline (a wrong/stale file is trusted) | ~10/28 | `diff_rows` validates `kind == GUARD_BASELINE_KIND` + schema, raises on mismatch |
| 5 | **Duplicate PIDs** silently last-win in `baseline_from_rows`/rows | ~9/28 | `ValueError` on duplicate pids |
| 6 | `target_fpr` unvalidated (accepts <0 or >1) | ~7/28 | `ValueError` if outside [0,1] |
| 7 | **Float asymmetry**: baseline rounded to 4dp, current full precision; boundary flips | ~6/28 | Current axes rounded to 4dp before all comparisons (symmetric) |

## Tier 2: design hardening, consensus, implemented (opt-in / non-breaking)

| # | Gap | Agents | Decision |
|---|-----|--------|----------|
| 8 | `STATUS_NEW` passes a newly added paper above floors **without baseline ack** (pandoc/html2text/turndown/pdfplumber/unstructured fail-closed on corpus growth) | ~12/28 | Added `--fail-on-new` (guard `fail_on_new=`): CI can require an explicit `--update`. Default off (non-breaking) |

## Tier 3: bigger new axes/layers, deferred (documented, NOT built this pass)

Out of scope for a guard/calibrate hardening pass; these are new features touching
`bench.py` contract or whole new check tiers. Recorded for a future pass.

- **Byte-/near-exact golden output tier** beneath the fuzzy metrics (pandoc `--accept`,
  html2text/turndown/markdownify/mdream/node-html-markdown/html-to-markdown-{go,py}/
  pymupdf4llm: exact `.expected.md`, CRLF-normalized, refresh ritual). ~17/28. The single
  most-recommended new layer. whisker catches semantic drift; an exact lane catches
  silent formatting regressions metrics miss.
- **Substring/section-order anchors** per paper (markitdown ordered `find()`, firecrawl
  `toContain`, olmocr present/absent/order facts, MinerU substring hit-rate). ~8/28.
- **Null-axis eligibility**: `teds=1.0` when neither side has tables inflates `overall`
  (opendataloader/nougat/MinerU/PDF-Extract-Kit/surya). Note: real table LOSS (GT has
  tables, candidate drops them) IS already caught (teds tanks); masking only when GT
  genuinely has no tables, which is benign. Lower urgency than agents implied.
- **Set-F1 / `%missing` content-recall axis** alongside NED (nougat, unstructured
  `cct-%missing`). ~5/28.
- **Per-axis / stratified calibration** (calibrate fits only `unigram_coverage`, not the
  bench nid/teds/mhs floors); per-group tolerance (html-to-markdown-py `guardrails.json`).
- **Version-keyed baselines** (PyMuPDF: pick golden by dependency version so a bump can't
  pass against the wrong baseline). Relevant when tomd pins shift.
- **Corpus-mean floor backstop**: already present in `bench` (`below_floor` + baseline
  `overall` regression). guard is the per-paper complement; together they cover both. No
  new work.
- **Intrinsic reference-free confidence** (camelot `(acc/100)*(1-ws/100)`), **per-stage
  intermediate goldens** (pdf-to-markdown/img2table), **four-tier field matching**
  (grobid). Future.

## Portable formulas worth keeping (citations)

- opendataloader `regression_tolerance: 0.02`, rule `mean >= threshold - tol` (`run.py:69-86`).
- grobid relative-Levenshtein pass `(max_len - dist)/max_len >= 0.8` (`EndToEndEvaluation.java:1126-1134`).
- camelot confidence `(accuracy/100) * (1 - whitespace/100)`, op point `>= 0.8` (`core.py:705,688-689`).
- img2table weighted table score, structured cutoff `>= 0.425` (`filter/model.py:118-162`).
- MinerU table substring hit-rate `0.9` txt/ocr vs `0.7` vlm (`test_e2e.py:194-201`).
- nougat per-stratum set-F1 alongside NED (`metrics.py:39-43`).
- firecrawl joint PDF gate `lenRatio>=0.8 AND numberPreservation>=0.9` (`shadowComparison.ts:54-61`).
