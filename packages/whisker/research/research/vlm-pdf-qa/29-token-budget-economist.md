# 29 - Token Budget Economist

**Verdict:** usable-with-conditions — per-page VLM at low resolution (728 px / ~478 visual tokens) is tractable on 189 PDFs / 6,266 pages serially (~21–56 h wall-clock) but costs ~8× input tokens vs today's whole-doc text lane; det-guided page selection alone covers <2% of pages and cannot substitute for full coverage.
**Confidence:** medium

## Findings

- [CRITICAL] **Visual-token math (Qwen2.5-VL, 28×28 patches).** Formula: `visual_tokens = min( (longest_px × longest_px / √2) / 784 , max_pixels_cap / 784 )` for A4 portrait (√2 aspect). Evidence: patch size and formula from `05-web.md:55`; olmocr default longest edge 1288 px (`00-baseline.md:15`, `olmocr/pipeline.py:1229`). Arithmetic:

  | Scenario | Longest edge | Raw pixels | Raw tokens | Effective (1280 cap) |
  |----------|-------------|------------|------------|----------------------|
  | Low | 728 px | 374,755 | 478 | 478 |
  | Mid | 1,288 px | 1,173,051 | 1,497 | **1,280** (hits default `1280×28×28` cap, `05-web.md:46-49`) |
  | High | 2,048 px | 2,965,821 | 3,783 | 1,280 unless server raises `--mm-processor-kwargs` |

  Impact: mid and high collapse to the same visual cost under vLLM defaults; only client-side pre-resize below 1,288 px actually saves encoder tokens.

- [HIGH] **Text tokens per page request (tapetum baseline + slice).** Measured at runtime (2026-07-07):

  | Component | Chars | Tokens (÷4) | Source |
  |-----------|------:|------------:|--------|
  | System prompt | 8,139 | 2,034 | `tapetum_llm.md:31-106` (measured) |
  | Adjudication schema | 2,240 | 560 | `models.py:72-86` JSON schema (measured) |
  | Triage user header | 136 | 34 | `adjudicate.py:379-389` (measured) |
  | Page QA instruction (est.) | 1,200 | 300 | new VLM wrapper (not yet in repo) |
  | Markdown slice / page | 2,090 median | 523 | `data/paperstore/*.md` ÷ page_count: median 2,090, mean 2,204 chars/page (runtime) |
  | **Fixed text subtotal** | | **3,451** | |
  | + visual (low / mid / high) | | **478 / 1,280 / 1,280** | |
  | **Input per page** | | **3,929 / 4,731 / 4,731** | |

  Output budget: reuse tapetum tier-1 ceiling 2,048 tokens (`adjudicate.py:73-75`); page-level structured findings likely ~600 tokens mean (assumption, not measured).

  Impact: text overhead dominates at low resolution (3,451 / 3,929 = 88%); shrinking the system prompt or page-slice is higher leverage than further DPI cuts below 728 px.

- [HIGH] **Per-paper totals (serial, one request per page).** Using median md slice 523 tok/page, output 600 tok/page, escalation N/A (no tier-2 per page assumed; fold in Python):

  | Pages | Text-only lane (today) | VLM low (478 vis) | VLM mid (1,280 vis) | VLM× / text |
  |------:|-----------------------:|------------------:|--------------------:|------------:|
  | 3 | in 6,017 / out 2,318 | in 11,784 / out 1,800 | in 14,190 / out 1,800 | **2.0× / 2.4×** |
  | 8 | in 10,254 / out 2,318 | in 31,424 / out 4,800 | in 37,840 / out 4,800 | **3.1× / 3.7×** |
  | 13 | in 14,488 / out 2,318 | in 51,064 / out 7,800 | in 61,490 / out 7,800 | **3.5× / 4.2×** |

  Text-only arithmetic: system 2,034 + header 34 + (pages × 2,090 ÷ 4) input; output 1,200 tier-1 + 62% × (1,800 tier-2 − 1,200) = 2,318 avg out. Escalation rate 123/198 = 62% from `constants.py:32-34` comment / `research/hybrid-llm-scoring/17-determinism-auditor.md:12`. Sample anchor: `n5036` 13 pages, 13,047 md chars (`00-baseline.md:81`).

  Impact: token multiplier grows with page count because VLM is O(pages) while text lane is O(1) whole-doc call.

- [HIGH] **Corpus totals: 189 PDFs, 6,266 pages (runtime `fitz.page_count`).** Serial throughput, 6,266 page-requests:

  | | Input tokens | Output tokens | HTTP requests |
  |--|-------------:|--------------:|--------------:|
  | Text-only (189 whole-doc, 62% escalated) | ~3.1 M | ~0.44 M | ~302 |
  | VLM low | **24.6 M** | 3.8 M | **6,266** |
  | VLM mid | **29.6 M** | 3.8 M | 6,266 |
  | VLM high (uncapped 3,783 vis) | **45.3 M** | 3.8 M | 6,266 |

  VLM low / text-only input ratio: 24.6 M / 3.1 M = **7.9×**. Request count ratio: 6,266 / 302 = **20.7×**.

  Wall-clock (serial, per page = 2 s image prefill + 600 output tok ÷ throughput):

  | vLLM decode tok/s | sec/page | corpus hours |
  |------------------:|---------:|-------------:|
  | 20 (conservative) | 32.0 | **55.7 h** |
  | 40 (mid) | 17.0 | **29.6 h** |
  | 60 (optimistic) | 12.0 | **20.9 h** |

  No olmocr README tok/s figure found in repo; olmocr cites **<$200 / 1 M pages** cost, not latency (`packages/whisker/research/repos/olmocr/README.md:36`). Prefill 1–3 s assumed from task brief; olmocr sets `MODEL_MAX_CONTEXT=16384`, `max_tokens=8000` per page (`olmocr/pipeline.py:107,162`).

  Impact: alliance-pod billing is hourly not per-token (`tapetum_llm.md:27-28`), but serial wall-clock dominates ops planning: ~1–2.5 h for text-only 189 papers vs ~21–56 h for full VLM pass.

- [MED] **Whole-doc-as-many-images (13 pages in one request) hits context and memory cliffs before it saves money.** 13 × 1,280 visual = 16,640 tokens + ~6,000 text ≈ **22,640 input tokens**, exceeding olmocr's per-call budget `MODEL_MAX_CONTEXT=16384` (`olmocr/pipeline.py:162`). Qwen2.5-VL native 128K (`05-web.md:46`) but vLLM serving recommends `--max-model-len` well below 128K and Issue #424 documents OOM at 128K on 16 GB (`05-web.md:34-35`). Default `--limit-mm-per-prompt.image` is 10 on the vLLM Qwen2.5-VL recipe (`05-web.md:46`); 13 pages needs an explicit raise. Memory scales with visual tokens (`05-web.md:48-49`: "Larger images = more visual tokens = OOM risk"). Batching 13 encoder passes in one prefill also removes serial determinism (D11-style concern for the advisory lane).

  Impact: multi-image whole-doc is a lose-lose for papers >10 pages under olmocr-class 16K contexts; per-page serial remains the safe default.

- [MED] **Mitigations — coverage vs cost tradeoffs.**

  1. **Page sampling (e.g. every 2nd page):** 13-page doc → 7 requests (−46% cost) but ** misses 6/13 pages (46% blind spot)** — incompatible with "check EVERY page."
  2. **Det-lane-guided selection:** Whisker sidecars expose `missing_regions` / `extra_regions` with optional `page` field (`n5036.whisker.json` sample: `{page: 1, token_start, token_end, sample}`). Runtime on 189 PDFs: **120 / 6,266 pages (1.9%)** have explicit page tags; 598/777 region rows have `page: null`. Only 92/381 sidecars have any page tag. Fallback "all pages if untagged" → 41.7% of det-corpus pages — still not full PDF coverage. Impact: det-guided selection is a **cost amplifier for flagged pages**, not a full-corpus substitute.
  3. **Resolution tiers:** Dropping 1,288 → 728 px saves 1,280 → 478 visual tokens (−63% visual, −17% total input at mid→low). Raising above 1,288 buys nothing until `--mm-processor-kwargs` max_pixels is raised (`05-web.md:51-52`: per-request pixel limits ineffective under vLLM).

- [LOW] **Cheapest configuration that still checks EVERY page (recommendation).**

  1. **Loop:** one serial HTTP request per PDF page (6,266 total); `--limit-mm-per-prompt '{"image":1}'`.
  2. **Model:** self-hosted `allenai/olmOCR-2-7B-1025-FP8` or Qwen2.5-VL-7B-Instruct on vLLM (task-matched, Apache 2.0, `05-web.md:25-32`).
  3. **Resolution:** client pre-render **728 px longest edge** (PyMuPDF, reuse `00-baseline.md:74-84`) → **~478 visual tokens**; do not rely on per-request `max_pixels` (`05-web.md:51-52`).
  4. **Text:** reuse tapetum system prompt + `Adjudication` schema; inject **~2,090 char md slice per page** (proportional split or page-boundary heuristic); keep binary stripping (`constants.py:95-108`).
  5. **Aggregation:** pure-Python worst-axis fold across page results (no second LLM); mirrors `chunking.worst_axis_verdict` pattern.
  6. **Server:** `--max-model-len 32768` (single-page headroom), `--max-num-seqs 1` (determinism + memory, `05-web.md:34-35`), `--mm-processor-kwargs '{"max_pixels":375000}'` (~478 tokens).
  7. **Expected cost:** ~24.6 M input + 3.8 M output tokens; **~21–56 h** serial wall-clock on one GPU; ~**8×** input tokens vs today's text-only lane for the same 189 papers.

  Impact: this is the Pareto floor for exhaustive page coverage; further cuts require skipping pages or accepting higher false-pass risk on unscanned pages.

## False-pass hypothesis

A 728 px render misses fine print (footnotes, straw-poll cells, `__cpp_lib_*` feature-test tables). VLM returns `pass` on garbled md the text lane would catch — same class as HQH OCR hallucination / missed defects at low resolution (`05-web.md:59-60`: OCR hardest category ~60% hallucination average across models). Mitigation: escalate resolution to 1,280 cap only on pages where tier-1 text adjudication or det signals flag tables/math (`lossy_table_count`, `table_parse_errors` in `adjudicate.py:385-387`).

## False-fail hypothesis

At 728 px the VLM hallucinates a footer or page number absent from markdown (tomd strips furniture by design, `packages/whisker/CLAUDE.md` conversion contract) and emits `structure`/`wording` fail — the P3100R6-class case documented in `research/vlm-pdf-qa/15-false-fail-hunter.md:30`. Mitigation: conversion-contract prompt clause (already in `tapetum_llm.md:39-48`) plus sanctioned-marker rules (`tapetum_llm.md:89-98`).

## What would change my mind

Measured end-to-end tok/s and prefill latency for `olmOCR-2-7B-1025-FP8` on alliance-pod hardware at 728 px and 1,280 px, logged from 50 representative WG21 pages — would tighten the 21–56 h wall-clock band from ±2× to ±20% and confirm whether mid-resolution is free at our GPU memory budget.
