# 28 - Performance and Complexity Auditor

**Verdict:** usable-with-conditions — deterministic verification primitives are fast enough for per-quote bidirectional checks on typical WG21 papers (<1 s Python per paper at 80k chars), but global `partial_ratio` on whole documents and uncapped oracle `text_nid` are O(doc×quote) DoS surfaces; block matching and hypothetical NLI belong off the hot path.
**Confidence:** high

## Findings

- [CRITICAL] **Exact monotonic DP is cheap; it should be the default candidate-side tier.** Evidence: `_find_token_occurrences` scans O(T·m) per quote (`grounding.py:70-82`); `_select_monotonic_matches` is O(S·O_avg) frontier DP (`grounding.py:102-168`); reproduced **14.1 ms** for 20 spans on an 80k-char doc (2026-07-16). Baseline replay emitted **20** missing-content quotes across four papers (`00-baseline.md:13-14`); `MAX_MISSING_QUOTES = 5` caps judge output (`pdf_judge.py:80,517`). Impact: bidirectional `ground_spans` on source + candidate adds **≲50 ms** per paper at median size; not the latency bottleneck.

- [CRITICAL] **Global `partial_ratio` against the whole normalized document is O(|doc|·|quote|) per span and scales to seconds on max-budget papers.** Evidence: fallback tier compares `partial_ratio(norm_quote, norm_md)` with `norm_md` = entire doc (`grounding.py:206-236`, `constants.py:67-73`); reproduced **54.4 ms** per call at 500k normalized chars, **512.5 ms** for `ground_spans`×5 at 500k (`llm-stack/06-performance-scalability.md:19`: 269 ms at 500k/3 spans). Corpus largest prose papers: **P2728R11/R12 ~2.5M chars** (`base64-blob-filter/00-corpus-evidence.md:16-19`); normalized alnum surface **~2.0M chars** → extrapolated **~200 ms/call**, **~1 s** for 5 quotes. Impact: candidate-side verification must NOT reuse the whole-doc fuzzy tier; scope to page/H2 windows (olmOCR pattern in `05-web.md:14-18`).

- [HIGH] **Per-quote token-window matching (`facts.py` pattern) is O(doc×quote) on the fuzzy path, acceptable at corpus scale but needs window caps.** Evidence: `_best_match` does exact find, else `partial_ratio_alignment(needle, haystack)` on the **full haystack**, then `_substring_edit_distance` DP on a widened window only (`facts.py:299-321`, `276-296`); reproduced **434.9 ms** for 37 facts on 80k (**~12 ms/fact**). Asymptotic: best case O(|needle|) substring; worst case O(|doc|·|needle|) alignment + O(|needle|·window) DP. Impact: port this for candidate absence with **H2/page-bounded haystack** (≤50k chars) and reuse `PAGE_QUOTE_MAX_DIFFS` length-relative threshold (`constants.py:176-181`, `grounding.py:244-278`); keeps 5-quote PDF-judge replay under **~100 ms** Python.

- [HIGH] **Block matching is seconds-class and already budget-capped; it must not gate per-quote evidence.** Evidence: NED matrix O(G·P·L²) per cell (`match.py:110-116`); `BLOCK_MATRIX_CELL_BUDGET = 400_000` forces whole-doc `text_nid` fallback (`constants.py:141-146`, `match.py:253-255`); corpus scan **28/400** `.md` files exceed budget (worst live: **P3045R8 1730 blocks, 2.99M cells**); persona timing **11.29 s** on real P3045R8 blocks (`persona/14-performance-scalability.md:12`), reproduced **699 ms** for 632×565 synthetic identical blocks (2026-07-16). Impact: reserve block/Hungarian rescue for `ambiguous` quotes only (`05-web.md:94-95`), not the minimal two-sided locate path (`00-baseline.md:61-68`).

- [MED] **NLI is not in code and is unjustified on the hot path; if added later, cost is pair-count × model latency, not document size.** Evidence: web synthesis defers NLI to ambiguous semantics only (`05-web.md:118-120`, dedup conclusion step 4); no NLI import in `tapetum_llm/`. Industry cross-encoders: **~50–200 ms/pair** GPU, **~0.5–2 s/pair** CPU (RefChecker/rag-rack class, `05-web.md:112-118`). On largest post-chunk paper (**500k chars**, `MAX_PAPER_MD_CHARS`, `constants.py:54-61`): naive all-blocks×quotes = **1730×5 ≈ 8650 pairs → hours**; scoped ambiguous-only (**≤5 pairs/ paper**) → **≤1 s GPU serial** under D11. Impact: NLI belongs behind `ambiguous` routing (`05-web.md:153-158`), never as step 2 of the minimal fix.

- [MED] **Existing DoS ceilings cover LLM ingress but leave deterministic scoring unbounded on megabyte markdown.** Evidence: `MAX_PAPER_MD_CHARS = 500_000` + base64 strip (`constants.py:54-61,95-108`) caps LLM view; `EVIDENCE_MIN_FUZZY_CHARS = 20` blocks shortest fuzzy quotes (`constants.py:69-73`); `MAX_PAGE_ESCALATIONS = 5` caps page LLM calls (`constants.py:162-168`); contrast **no size cap** on oracle `text_nid` (`score.py:212`, `persona/11-security-reviewer.md:10`). Reproduced: `Levenshtein` on **500k** normalized chars **0.5 ms** (rapidfuzz SIMD, `metrics.py:64-78`); **2.0M** chars still linear memory. Impact: add `CANDIDATE_VERIFY_MAX_CHARS` mirroring block budget for any new verifier entry point.

- [LOW] **Python verification stays <1% of tapetum wall clock; LLM serialism dominates.** Evidence: tapetum batch **25–40 s/paper**, **1.5–2 h/200 papers** (`llm-stack/06-performance-scalability.md:8-9`); setup **2.5 ms/paper**, grounding **37 ms** at 80k (`06-performance-scalability.md:11`). Impact: optimize windowing and caps, not SIMD Levenshtein.

## Asymptotic summary (anchors)

| Primitive | Where | Time | Space | Typical WG21 (80k) | Largest (500k–2.5M) |
|-----------|-------|------|-------|--------------------|---------------------|
| Exact token DP | `grounding.py:70-168` | O(Q·T·m + S·O) | O(T + S) | **14 ms / 20 Q** | **≲150 ms / 20 Q** at 500k T |
| Global `partial_ratio` | `grounding.py:232-236` | O(\|doc\|·\|q\|) / span | O(\|doc\|) | **8 ms / call** | **54–200 ms / call** |
| Per-quote window + DP | `facts.py:276-321` | O(\|doc\|·\|q\|) worst; O(\|q\|) best | O(\|q\|·w) | **12 ms / fact** | **cap haystack → ≲50 ms / Q** |
| Block Hungarian + NED | `match.py:110-211` | O(G·P·L²) + O(n³) | O(G·P) | **0.7–11 s** | fallback **0.13 s** (`persona/14`) |
| Full-doc `text_nid` | `metrics.py:64-78` | O(\|doc\|²) | O(\|doc\|) | **<1 ms** | **0.5 ms @ 500k norm** |
| NLI (hypothetical) | — | O(pairs · L_enc) | model | **0 @ v1** | **≤1 s @ ≤5 pairs GPU** |

Q = quote count (≤5 judge, ≤20 replay), T = doc tokens (~12.8k @ 80k alnum), G/P = block counts, L = block length (~565 P3045R8).

## Minimal fast design

1. **Source locate:** existing `ground_spans(pdf_text)` / `ground_page_quotes(page_text)` — unchanged (`00-baseline.md:48-51`).
2. **Candidate locate:** second `ground_spans(spans, tomd_md)` for exact/substring; on miss, **`facts._best_match` on page or H2 window** (not global `partial_ratio`) with olmOCR length-relative threshold for page quotes (`grounding.py:244-278`, `05-web.md:14-18`).
3. **Verdict:** retain quote iff source grounded **and** candidate miss; label `present | absent | ambiguous` (`00-baseline.md:64-68`, `05-web.md:182-190`).
4. **Escalation:** block-window fuzzy rescue **only** for `ambiguous` (`05-web.md:94-95`); **no NLI in v1** (`05-web.md:118-120`).
5. **Budget:** reuse `MAX_MISSING_QUOTES=5`, `MAX_PAGE_ESCALATIONS=5`, `EVIDENCE_MIN_FUZZY_CHARS=20`; add explicit **50k-char candidate haystack cap** per quote (≈4× median section).

Expected Python overhead per PDF-judge paper: **~50–150 ms** (median) + **~0.5–1 s** (500k-char outliers with 5 quotes) — still **<3%** of **25–40 s** LLM latency.

## Denial-of-service ceilings

| Control | Value | File:line | Closes | Open gap |
|---------|-------|-----------|--------|----------|
| LLM markdown budget | 500_000 chars | `constants.py:61` | nginx 413 | pre-strip P2728 **2.5M** raw |
| Fuzzy quote min length | 20 norm chars | `constants.py:73` | boilerplate fuzzy | ≥20-char generic still passes |
| Page escalation cap | 5 LLM calls | `constants.py:168` | page fan-out | monolith unbounded |
| Missing-quote cap | 5 | `pdf_judge.py:80` | quote fan-out | — |
| Block matrix budget | 400_000 cells | `constants.py:146` | bench O(G·P) | **28/400** papers silent fallback |
| Fuzzy rescue pred len | 2000 chars | `constants.py:151` | window scan | unmatched G×P pairs |
| Base64 line strip | ≥1024 chars @ 90% b64 | `constants.py:107-108` | 1.1 MB lines | prose megabytes |
| Oracle `text_nid` | **none** | `score.py:212` | — | crafted multi-MB `.md` |
| Candidate verifier (proposed) | **50_000 chars/quote window** | — | whole-doc fuzzy | not implemented |

**Hard reject rule (proposed):** if `len(normalized_text(md)) > 2_000_000` or verify budget exceeded, demote all absence claims to `ambiguous` and cap wall time at **5 s** Python — fail-closed on evidence, not on verdict (`00-baseline.md:56-57`).

## False-pass hypothesis

Bidirectional `ground_spans` with the existing global fuzzy tier on the candidate side: a **25-char** generic quote clears **0.90** against a **500k** haystack in **~54 ms** (`grounding.py:232-236`), grounding a fabricated "absent" claim without a char interval — same false-pass as today's source-only path (`00-baseline.md:21-24`, `llm-stack/22-grounding-robustness-auditor.md:7`).

## False-fail hypothesis

Running block matching on every candidate miss before fuzzy rescue: a **P3045R8-scale** paper (**1730 blocks**) spends **11+ s** (`persona/14-performance-scalability.md:12`) per verify pass, causing operators to disable candidate checks entirely and revert to source-only labels (`pdf_judge.py:401-404`).

## What would change my mind

A profiled bidirectional replay of the **20-quote** nine-PR set (`00-baseline.md:11-14`) showing windowed candidate verify completes in **<500 ms** total Python on the largest involved paper **and** cuts false "absent" labels by **≥50%** without new dependencies — measured end-to-end, not asymptotic argument alone.
