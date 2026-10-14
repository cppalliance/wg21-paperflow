# 25 - Evidence-Historian

**Verdict:** usable-with-conditions (second-hand scout claims are substantively correct on architecture; several file:line anchors drifted or were imprecise and need correction in 00-baseline)
**Confidence:** high

## Findings

- [HIGH] **Pandoc golden tests via `.native` AST + refresh mechanism: CONFIRMED.** Evidence: `packages/whisker/research/repos/pandoc/test/Tests/Old.hs:31-32` (reader tests write `-w native` to `.native` goldens), `:380-408` (`goldenTest` + `updateGolden` writes norm file on accept). `--accept` refresh documented at `pandoc/changelog.md:11714` ("`--accept` can be used to update expected output"); not wired in Old.hs itself (tasty-golden CLI convention). Impact: classic-converter row in 00 §1 is trustworthy; anchor lines 380-408 are exact.

- [HIGH] **Markitdown `must_include`/`must_not_include` CI vectors + no LLM on default path: CONFIRMED.** Evidence: `_test_vectors.py:11-12` defines fields; `test_module_vectors.py:65-68` and `test_cli_vectors.py:59-62` hard-fail with `assert string in result`. Default `MarkItDown()` sets `_llm_client/_llm_model = None` at `_markitdown.py:124-126`; vision captioning gated at `_image_converter.py:69-71` (`if llm_client is not None and llm_model is not None`). Impact: markitdown row accurate; opt-in LLM is explicit, not default conversion.

- [HIGH] **Firecrawl LLM extract/clean opt-in: CONFIRMED (line citations partially WRONG).** Evidence: `llmExtract.ts` lives at `firecrawl/apps/api/src/scraper/scrapeURL/transformers/llmExtract.ts`. `performLLMExtract` only enters LLM path when `hasFormatOfType(..., "json")` at `:959-972`; otherwise returns document unchanged at `:1127`. `performCleanContent` no-ops unless `meta.options.onlyCleanContent` at `:1134-1136`. `generateObject` LLM call at `:811`. Baseline cited `:128-140` for "clean via GPT" but those lines are `normalizeSchema` recursion, not clean-content logic (clean prompt starts `:1193+`). Impact: architecture claim (LLM optional, deterministic scrape default) holds; fix stale line refs.

- [MED] **Firecrawl "124× toContain CI anchors": DRIFTED.** Evidence: live count in `firecrawl/apps/api/src/__tests__/**/*.ts` is **348** `.toContain(` occurrences (shell rg, 2026-07-16); e2e_full_withAuth alone has 49. Deterministic substring/status asserts remain the CI gate pattern (e.g. `e2e_withAuth/index.test.ts:92-116` markdown substring checks); LLM-extraction e2e tests assert schema/shape, not model quality scores. Impact: qualitative claim stands; numeric anchor is stale and should not be cited as 124.

- [MED] **Mdream "zero LLM markers": CONFIRMED for conversion path, imprecise globally.** Evidence: no `openai`/`gpt`/`generateObject`/`chat.completions` in `mdream/packages/mdream/src/` (rg empty). Ratio hard-fail gates at `fixture-parity.test.ts:76-78` (`expect(ratio).toBeGreaterThan(0.99)` / `toBeLessThan(1.01)`). Non-conversion LLM-adjacent artifacts exist: `packages/llms-txt`, README "LLM-optimized", `bench/token-usage.ts:10` (gpt-4 token-cost estimation only, not inference). Impact: 00 row "(a) conversion = none" is correct; "zero LLM markers" overstates if read repo-wide.

- [HIGH] **Opendataloader `check_regression` threshold gating: CONFIRMED substance, DRIFTED path.** Evidence: `opendataloader-pdf/run.py` **does not exist** in clone (Test-Path False; no `check_regression` under opendataloader-pdf). Threshold logic lives in companion bench clone `opendataloader-bench-tmp/src/run.py:53-86` (NID/TEDS/MHS vs thresholds, `:110-114` returns False on failure). Integration: `opendataloader-pdf/scripts/bench.sh:83` runs `uv run python src/run.py` from cloned opendataloader-bench. Impact: regression-gating claim is real but anchor must read `opendataloader-bench/src/run.py:69-86`, not opendataloader-pdf.

- [HIGH] **Pymupdf4llm no LLM call in core path: CONFIRMED.** Evidence: rg over `pymupdf4llm/src/` finds zero `openai`/`gpt`/`chat.completions`/`generateObject`. Core entry `src/__init__.py:88-217` routes through `pymupdf4llm.helpers.document_layout.parse_document` and `pymupdf_rag.to_markdown` (layout/OCR heuristics). OpenAI appears only in `examples/country-capitals/country-capitals.py:22,95-97` (demo RAG, not library). Optional `pymupdf_layout` is ONNX layout ML (CHANGES.md:179-188), not an LLM API. Impact: "marketing name only" row holds for LLM-QA comparison; note layout-ML is separate from LLM.

## False-pass hypothesis

A firecrawl default markdown scrape (`formats: ["markdown"]` only) passes all 348+ deterministic `toContain`/status asserts while LLM-only fields (`extract`, `json`, `summary`) are never requested, so CI gives no signal on LLM extraction quality. Same class as whisker's selection gap: deterministic path green, optional LLM lane untested in CI.

## False-fail hypothesis

Markitdown `must_include` vectors embed fixture-specific UUIDs and base64 fragments (`_test_vectors.py:21-28`); any benign converter change to image embedding format fails CI even when semantic content is preserved. Classic golden brittleness, not LLM-related.

## What would change my mind

Finding any of the 31 reference repos (or a major 2025-2026 doc-AI benchmark) that mechanically hard-fails CI or production accept on an LLM judge score for converted output, with the LLM verdict wired as the sole or primary gate (not retry/fallback/advisory), verified in live clone the same way these six were.
