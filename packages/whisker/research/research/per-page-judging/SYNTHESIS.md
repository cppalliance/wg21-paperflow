# Per-Page LLM Judging - Research Synthesis

**Verdict band:** usable-with-conditions   **Confidence:** high
**Decision vs our codebase:** adopt-partially - NOT the planned 33x per-page LLM
judge; instead a deterministic per-page recall screen + scoped LLM escalation on
flagged pages only, keeping the monolithic call for global checks.

## Summary

- **The planned design (one LLM call per page, full markdown injected, worst-page
  -wins) is refuted by the swarm.** Three independent lines: (1) worst-page-wins
  noise math: document false-review rate is `1-(1-p)^n`; at n=33 pages a 1%/page
  false-flag rate yields 28.1% document-level false review; keeping doc noise at
  10% requires <= 0.32%/page precision, implausible for an uncalibrated judge
  whose production confidence is anti-calibrated (18/18 fails at >= 0.95)
  (20-false-fail-hunter.md finding 1). (2) Cost: 33 serial calls at 8-28 s/call
  is 4.4-15 min per paper, ~15.8 h for the 189-PDF corpus vs ~1.3 h monolith
  (21-steelman-monolith.md finding 3). (3) The verified incident (p0957r8) is
  ALREADY closed end-to-end by det `missing_region` + fusion
  `clear_blocked_missing_region` (21-steelman finding 1); a redesign must add
  incremental detection, not re-fix a fixed bug.
- **No surveyed repo runs an LLM per page for VERIFICATION.** olmocr-bench, the
  strongest prior art, is page-scoped but DETERMINISTIC: JSONL facts bound to
  `(pdf, page, id)`, fuzzy `partial_ratio` presence/absence with length-relative
  tolerance `1.0 - max_diffs/len(ref)`, `find_near_matches` order tests - no LLM
  in the eval loop (10-olmocr-bench-analyst.md, tests.py:150-182,214-226).
  docling: per-page numeric scores with 10th-percentile-tail aggregation,
  advisory only (13-docling-analyst.md). nougat: deterministic per-page
  degeneration guards, `[MISSING_PAGE_FAIL:n]` in-band markers
  (15-nougat-surya-analyst.md). marker: block-scoped LLM with reject-and-keep
  sanity gates (12-marker-analyst.md). Extraction repos (MinerU, Dolphin,
  grobid, unstructured) scope units but never verify (14, 17).
- **The page-1/TOC/figure traps make naive per-page presence checks structurally
  false-fail-prone.** Page-1 title block maps to YAML front matter (sanctioned),
  TOC pages are deliberately removed, figure-internal text is legitimately
  imaged, cross-page paragraph joins leave dangling raw tails, and header/footer
  stripping is skipped below 3 pages (20-false-fail-hunter.md findings 2-6).
  Each is a guaranteed per-page flag unless every page call inherits the full
  conversion contract.
- **Per-page presence checking has its own blind spots.** Cross-page reordering
  (all tokens present, order wrong), duplicated content (presence rewards it),
  token-preserving cell swaps, and rubber-stamping (33 near-identical prompts,
  nothing rejects uniform `pass 0.98 []`) (19-false-pass-hunter.md findings
  1,4,5,6). The monolith's global view (reordering, structure) must be kept.

## The adopted design (hybrid, ~1+k LLM calls instead of 33)

```
pdf_judge (lane-local, independence preserved):
  1. extract_textlayer -> clean_pages (list preserved)
  2. DETERMINISTIC per-page screen (free, no LLM):
     page_recall_k = content_recall(page_k, tomd_md) for every page
     flag pages below PAGE_RECALL_FLOOR (skip pages < PAGE_MIN_TOKENS)
  3. Monolithic judge call: UNCHANGED (global checks: order, structure)
  4. Scoped LLM escalation: ONLY flagged pages (k is typically 0-2) get a
     page-scoped call: page raw text + markdown, prompt inherits the FULL
     conversion contract (YAML, TOC, figure-text, reflow sanctions) and asks
     "which content of THIS page is missing from the markdown?"
  5. Aggregation:
     - flagged page + LLM confirms missing -> verdict capped at review,
       page-attributed quotes in missing_content ([p13] ...)
     - flagged page + LLM says sanctioned -> keep monolith verdict, record
       the page finding in the sidecar (operator visibility)
     - LLM never upgrades a det page flag to pass silently
```

Why this holds against the swarm findings:

- **Steelman cost objection:** ~1+k calls; corpus stays ~1.5 h. Wall-clock per
  paper grows only when det actually flags a page.
- **False-fail noise:** the screen is deterministic and calibratable (one named
  constant, fitted like whisker's unigram edges); the LLM sees only suspect
  pages WITH the sanction contract, so page-1/TOC/figure traps become "LLM
  clears the det flag as sanctioned" instead of noise.
- **False-pass (p0957r8 class):** page-13 recall collapses locally while
  document recall stayed 0.9806; the per-page screen isolates exactly what the
  document-level floor (Fix 4) mathematically cannot. Attention is not involved.
- **Rubber-stamping:** the screen cannot rubber-stamp; the LLM's role shifts
  from "find what is missing" (absence detection, weak) to "explain/confirm
  this specific flagged gap" (presence-scoped, strong).
- **Independence:** the screen is computed lane-locally from source + markdown
  (the admissible html_outline pattern); it never reads the det sidecar
  (21-steelman finding 6c).

## Top findings (ranked)

- [CRITICAL][NOW] Worst-page-wins noise math kills naive per-page LLM. Evidence:
  20-false-fail-hunter.md finding 1. adopt? yes (design changed).
- [CRITICAL][NOW] olmocr-bench: page-scoped DETERMINISTIC fuzzy checks, no LLM.
  Evidence: tests.py:150-182, benchmark.py:91-126. adopt? partial (per-page
  recall screen; fuzzy fact engine already exists as whisker facts.py).
- [CRITICAL][NOW] p0957r8 already closed by det+fusion; incremental value of
  per-page LLM is the narrow token-preserving-corruption class. Evidence:
  21-steelman finding 1-2. adopt? yes (keep monolith, scope escalation).
- [HIGH][NOW] Page-1 YAML / TOC / figure-text sanctions must be inherited by any
  page-scoped prompt. Evidence: 20-false-fail-hunter findings 2,3,6. adopt? yes.
- [HIGH][NOW] Anti-rubber-stamp: reject a page pass at conf >= 0.95 with empty
  missing_content when the page's deterministic recall < 1.0 disagrees.
  Evidence: 19-false-pass-hunter finding 6. adopt? partial (det screen makes
  the primary decision; LLM disagreement -> review).
- [HIGH][LATER] Cross-page order stays a det job: shingle coverage /
  COV_UNIGRAM_GAP_TRIGGER already signal it; olmocr TextOrderTest pattern
  portable into facts.py order facts. Evidence: 19 finding 1. adopt? later.
- [MED][LATER] marker reject-and-keep (schema + sanity gate, keep original on
  reject) for any future LLM-refinement step. Evidence: 12-marker-analyst.
- [MED][LATER] docling dual-tail aggregation (10th percentile of cells, then of
  pages) as the numeric analogue if the screen ever becomes a score instead of
  a flag. Evidence: 13-docling-analyst.

## Bugs / edge-cases in OUR code (surfaced by the comparison)

- `textlayer.py:56-58,153-160` - header/footer stripping can hide REAL repeated
  boilerplate (95-char normative sentence on 40% of pages) from the judge; the
  <120-char cap is the only guard. Fix direction: log stripped lines into the
  debug artifact; consider olmocr zone-scoped facts for wording papers.
- `textlayer.py:60-62` - header/footer detection skipped below 3 pages; short
  admin papers keep furniture in the raw text the judge sees. Known, accepted;
  page-scoped prompts must keep the furniture sanction.
- `grounding.py:39-52` - whole-document `partial_ratio >= 0.90` is the wrong
  shape for page-local grounding; page-scoped quotes should ground against the
  page (length-relative tolerance, olmocr pattern) - facts.py:299-326 is the
  closer in-repo precedent.
- Per-page recall on dehyphenated splits ("implementa-" / "tion") loses the
  token pair across the page boundary; threshold must tolerate ~2-3% floor
  slack, or normalization should dehyphenate the raw page tail.

## Top portable detail

olmocr-bench's length-relative fuzzy threshold `threshold = 1.0 -
max_diffs/len(reference)` with `fuzz.partial_ratio` (tests.py:168-173): one
line, deterministic, page-scoped, and the exact replacement for "verbatim
substring or drop" grounding on page-local quotes.

## Flip conditions

- If simulation shows per-page recall does NOT isolate p0957r8 page 13 (i.e.
  page-13 recall stays above any plausible floor while content is missing),
  the screen idea fails and the two-pass inventory (RAW figure/table inventory
  call -> presence-check call, 2x cost) becomes the fallback
  (21-steelman finding 6b).
- If a labeled >= 30-paper holdout later shows det+fusion+monolith already catch
  >= 90% of verified defects, the scoped escalation can be dropped entirely
  (21-steelman "what would change my mind").

---
Sources: local clones at packages/whisker/research/repos/ (olmocr, marker,
docling, MinerU, Dolphin, nougat, surya, langextract, grobid, unstructured),
baseline 00-baseline.md, 2026-07-14.
Personas: 12 (10-21). Meta-review: orchestrator verification of the five
decision-critical reports (10, 19, 20, 21, 18) against code and prior research.
