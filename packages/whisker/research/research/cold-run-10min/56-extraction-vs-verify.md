# 56 - Extraction vs verification (olmocr / docling)

**Date:** 2026-07-24
**Question:** Confirm prior finding that olmOCR and Docling are extraction, not verification. Did any NEW 2026 olmOCR LLM-judge mode appear that we missed?
**Answer:** **Still different workload class? yes.**

## Verdict

Prior finding stands. olmOCR and Docling remain **PDF→text/structure extraction** pipelines. Neither ships a production **LLM-as-judge** path that scores already-produced conversion markdown against the source for accept/reject. No 2026 olmOCR release or paper adds such a mode; olmOCR 2 explicitly doubled down on **deterministic unit-test rewards**, the opposite of runtime LLM judging.

## Prior finding (reconfirmed)

| Source | Claim |
|--------|--------|
| `research/tapetum-llm-speedup/SYNTHESIS.md` §1 | docling / marker / olmocr / MinerU do extraction with dense VLMs; **no production LLM-judge verification** |
| `research/tapetum-llm-speedup/81-olmocr-anti-steelman.md` | olmOCR = 1 VLM call/page emit markdown; quality path is offline `test.run(md)` bench, **zero** verification LLM calls at score time |
| `research/tapetum-llm-speedup/57-docling-anti-steelman.md` | Docling VlmPipeline = 1 call/page `"Convert this page to docling."`; not verification |
| `research/all-pages-llm-coverage/v2/11a-docling-callsites.md` C1 | Docling has **no** path where LLM/VLM judges already-produced conversion vs source |
| `research/llm-readability/repo-scan/_patterns-matrix.md` row 2 | No cloned converter gates markdown with an LLM judge; olmOCR LLM use in `bench/miners/` is **test mining only** |

Workload contrast vs tapetum-llm (unchanged):

| Axis | olmOCR / Docling | tapetum-llm |
|------|------------------|-------------|
| Task | Emit markdown/HTML from page image | Judge already-converted candidate vs source |
| Calls | ~1 generative touch / page | ~6 serial judge calls / paper (~2284 / 381) |
| Model class | Dense OCR VLM (olmOCR 7B; Docling GraniteDocling ~258M) | MoE judge (DeepSeek-V4-Pro), long evidence payloads |
| Fail mode | Soft retries / fallbacks / partial docs | Fail-closed + grounded structured verdicts |
| Eval | Offline deterministic unit tests / roundtrips | Online LLM cascade with grounding |

## 2026 delta check: any new olmOCR LLM-judge mode?

**No.** Checked:

1. **Local clone** `research/repos/olmocr` @ `f7cfe4c` (2026-03-25). Production hot path still `build_page_query` → `build_no_anchoring_v4_yaml_prompt()` + page PNG (`pipeline.py:106-139`). Repo-wide search for `LLM-as-a-Judge` / `llm-as-judge` / `as-a-judge` in `.py`/`.md`: **empty**.
2. **GitHub releases** through **v0.4.27** (2026-03-12): PII tagging, GPU deps, parallel retries, queue fixes. No judge / verification / quality-gate feature.
3. **GitHub code search** (`repo:allenai/olmocr` for `LLM-as-a-judge`, `as-a-judge`): **0 hits**.
4. **olmOCR 2** (Ai2 blog 2025-10-22; arXiv 2510.19817): RL with **binary unit-test rewards** (GRPO). Blog: *"deterministic verifiers"* for table/math/reading-order; same framework for train and olmOCR-Bench. Explicitly **not** an LLM-as-judge scoring loop at inference.
5. **LLM touches that look like "verify"** remain offline mining only:
   - `olmocr/bench/miners/check_headers_footers.py` — VLM assists **authoring** presence tests
   - `olmocr/bench/miners/check_old_scans_math.py` — same for LaTeX
   - Score path: `benchmark.py` → `test.run(md_content)` deterministic fuzzy/unit checks (see also PR #462 length-guard fix, 2026)

## Docling (brief, unchanged)

No new counterexample needed for this delta: prior C1 at SHA `fbd39b8` still holds in the cold-run framing. Generative sites take source crops/pages and **produce** text/structure (extraction/enrichment). `tests/verify_utils.py` is deterministic string compare, not an LLM judge.

## What would flip this to "no" (same workload class)

A released olmOCR (or Docling) production CLI path that, for each converted page/paper:

1. Takes **already-produced** markdown as input,
2. Calls an LLM/VLM to emit a **pass/fail or defect list** against the source,
3. Gates acceptance on that judgment (fail-closed or review),

with published throughput on that path. **None exists as of 2026-07-24.**

## Implication for cold-run ≤10 min

Do not import olmOCR/Docling pages/s headlines as evidence that our MoE verification fleet "should" hit the same wall clock. Steal portable **serving/payload** ideas only; the workload class difference remains load-bearing.
