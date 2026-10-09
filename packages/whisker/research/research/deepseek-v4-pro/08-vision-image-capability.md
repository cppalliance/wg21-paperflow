# 08 - Vision-Image-Capability

**Verdict:** usable-with-conditions — DeepSeek-V4-Pro is confirmed text-only in our deployment; it can adjudicate markdown-internal table and structure defects but cannot verify any pixel-level conversion claim, so image fidelity and visually grounded layout errors are a permanent structural blind spot for tapetum_llm.
**Confidence:** high

## Findings

- [CRITICAL] DeepSeek-V4-Pro has no native image, audio, or video input. NVIDIA NIM model card lists input modality as **Text** only (`Input Types: Text`, `Data Modality: Text`). HuggingFace release describes two MoE **language models** with text encoding/decoding only; no vision encoder in the checkpoint. DeepSeek API serves `deepseek-v4-pro` and `deepseek-v4-flash` as text-in/text-out chat completions. Evidence: https://docs.api.nvidia.com/nim/reference/deepseek-ai-deepseek-v4-pro ; https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro ; https://api-docs.deepseek.com/news/news260424 (Apr 24, 2026); `00-baseline.md` §1 line 29.
  Impact: Our `alliance-pod` / `h200x8-deepseek-v4-pro` services use `VllmThinkingBackend` with string prompts only. The model never receives figure rasters, PDF page renders, or HTML layout trees.

- [CRITICAL] No open-weight V4 multimodal variant ships alongside V4-Pro. The Apr 2026 release family is four text checkpoints only: V4-Pro, V4-Pro-Base, V4-Flash, V4-Flash-Base (1M context, MoE text LLMs). arXiv:2606.19348 discusses text pre-training (32–33T tokens) and long-context attention; it does not describe a V4 vision encoder or image-token interface. Third-party blog claims of "V4 native vision" contradict primary sources and appear to conflate the consumer-app "vision mode" (a mounted encoder, not the open weights we serve) with V4-Pro itself. Evidence: https://arxiv.org/html/2606.19348 ; https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro ; https://www.dataleadsfuture.com/deepseek-v4-cant-read-images-i-made-it-read/ (Jun 2026: "multimodal versions ... still haven't been released"); Thomas Wiegold review (Apr 2026): "No multimodal. Text in, text out."
  Impact: There is no drop-in vision upgrade path within the V4-Pro slot in `SERVICES.toml`. Any future V4-VL / V4.5 would be a new model line, new backend, and new determinism validation.

- [HIGH] DeepSeek maintains **separate** vision model families, not bundled with V4-Pro. Documented lines: **DeepSeek-VL2** (MoE VLM, OCR/charts/documents; open weights, no first-party V4 API), **Janus / Janus-Pro** (unified understanding + generation, SigLIP encoder + separate generation path), **DeepSeek-OCR / DeepSeek-OCR 2** (document layout and text extraction specialists). These pre-date or sit beside V4; VL2 is explicitly "not part of the V4 generation." Evidence: https://deepseekai.guide/models/deepseek-vl2/ ; https://blog.roboflow.com/deepseek-vision-models/ ; https://github.com/deepseek-ai/Janus ; https://deepseekai.guide/guides/deepseek-limitations/ §1 (Apr 2026).
  Impact: Even if we wanted vision-assisted adjudication, it would require a second model slot, cross-model orchestration, and would violate the current single-model deep cascade design. Not available on our RunPod V4 endpoint today.

- [HIGH] tapetum_llm feeds **markdown text only**; image information is limited to `![alt](path)` and tomd honesty markers. `adjudicate.py` wraps `paper.md` via `ctx.inject_untrusted(md)` with no image bytes. The conversion contract (`tapetum_llm.md` line 40) defines images as alt text from figure captions plus filesystem paths. Sanctioned markers (`tomd:uncertain`, `tomd:glyph-placeholders`, `tomd:vector-extraction-uncertain`) disclose converter uncertainty but do not expose pixels. Evidence: `packages/whisker/src/whisker/tapetum_llm/adjudicate.py:327,348` ; `packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md:40,81–87` ; root `CLAUDE.md` prompt-injection note on alt text inheriting `wrap_source` protection (data, not verified vision).
  Impact: Image extraction fidelity is entirely tomd's responsibility (`packages/tomd/src/tomd/lib/pdf/images.py`, `structure.py`). V4-Pro can flag suspicious alt text or missing `![]()` references in prose, but cannot ask "does `<pid>-fig0-1.png` match page 4 of the PDF?"

- [HIGH] **`tables` axis: partial coverage, visual-layout blind spot.** The system prompt instructs the model to catch merged-cell flattening errors, column shifts, pipe-in-cell splits, and header loss in pipe tables (`tapetum_llm.md` §Table fidelity). That works when the markdown still carries contradictory delimiters or wrong header association. It **fails** when tomd emits a self-consistent pipe table whose tokens look plausible but whose column boundaries disagree with the PDF's visual grid (borderless tables, straw-poll grids, feature-test matrices with colspan). Pipe tables cannot express merges; faithful conversion repeats values — a wrong repeat is often indistinguishable from a correct one without seeing cell borders. Evidence: `tapetum_llm.md:68–79` ; whisker `CLAUDE.md`: "Fidelity is not comprehension" — Lane 2 `teds` measures structure against a reference, but tapetum has no reference image.
  Impact: Table cell swaps that preserve multiset token coverage (whisker `unigram_coverage` green) remain a known false-pass class; V4-Pro adds reasoning over markdown but cannot resolve ambiguities that require seeing which physical column a value occupied.

- [MED] **`structure` axis: heading tree yes, page layout no.** V4-Pro can judge section order, missing H2s, duplicated headings, and mid-sentence truncation from markdown (`structure` axis rules in `tapetum_llm.md:52–53`). It cannot verify: multi-column reading order (reflowed into linear prose that reads naturally), figure/table float placement vs in-text anchors, page-header/footer material stripped correctly vs body text dropped, or side-by-side code/figure layouts merged incorrectly when the merged markdown still has coherent headings. Whisker itself omits bbox visualization ("no layout stage to map token positions back to page coordinates"). Evidence: `packages/whisker/src/whisker/CLAUDE.md` (What vs where / deliberate omissions) ; `tapetum_llm.md:52–53`.
  Impact: Permuted or reflowed sections with intact heading labels are the dominant false-pass class the deterministic gate misses; text-only adjudication helps only when heading markers or section titles reveal the permute — not when visual order diverges but ATX headings were assigned correctly.

- [MED] Consumer "vision mode" (mounted VLU on V4 backbone) is **out of scope** for wg21-paperflow. Reports describe a separate visual encoder mounted post-training on the V4 text stack (DeepSeek app JSON config, Stage 1 of a roadmap; Stage 2 V4-VL ~2026 Q3 rumoured). This is not in the MIT weights we self-host, not exposed on our vLLM RunPod endpoints, and not wired into `tapetum_llm`. Workarounds (sub-agent with Kimi K2.6 reading images into text) prove the gap: they require a **second** multimodal model. Evidence: https://www.besthub.dev/articles/deepseek-v4-vision-mode-architecture-breakdown-and-benchmark-vs-top-models-e60517b133a2 ; https://www.dataleadsfuture.com/deepseek-v4-cant-read-images-i-made-it-read/ ; Medium V4 review (Apr 2026): "K2.6 has multimodality at launch where V4 does not."
  Impact: Do not plan tapetum adjudication upgrades assuming V4-Pro will "see" PDF pages without a separate architecture decision.

- [LOW] **Quantified blind spot — error classes structurally undetectable by text-only V4-Pro** (no source pixels, no figure bytes in prompt):

  | Class | Example | Detectable from markdown alone? |
  |---|---|---|
  | Wrong/missing raster figure | Correct caption, wrong or empty PNG | **No** — alt/path can look valid |
  | Figure content ≠ caption | Chart values wrong; alt says "Figure 2: throughput" | **No** |
  | Vector figure skipped silently | No `![]()`, no `vector-extraction-uncertain` comment | **No** |
  | Sub-threshold glyph dropped | Emoji/raster glyph under 18pt omitted without placeholder | **No** (unless `tomd:glyph-placeholders` emitted) |
  | Visually merged table mis-denormalized | Repeated value in wrong row; pipe table parses clean | **Rarely** — only if row semantics contradict prose |
  | Borderless / HTML layout table → wrong grid | Self-consistent pipe table, wrong column semantics | **Rarely** |
  | Multi-column read order swap | All words present, order reflowed plausibly | **No** (headings may still look fine) |
  | Diagram-only-as-image | Code/architecture diagram rasterized; alt empty or generic | **No** |
  | Figure/table float vs in-text anchor | Figure file exists but attached to wrong section | **No** |
  | Color/font emphasis lost | Bold/italic from visual styling not in text layer | **Partial** — only if wording axis sees semantic loss |

  **Coverage estimate:** Of tomd's image pipeline outputs (`suggested_alt`, raster extraction, vector heuristic, 20-figure cap in `images.py`), **0%** of pixel fidelity is visible to V4-Pro. For **`tables`**, roughly **half** of the prompt-listed failure modes (delimiter/header/pipe-in-cell) are text-detectable; **merged-cell association and visual grid alignment** are not. For **`structure`**, **heading hierarchy and section completeness** are text-detectable; **page-layout order and float placement** are not. This matches the failure class: **structural inability to verify image extraction fidelity.**

  Evidence: `packages/tomd/src/tomd/lib/pdf/images.py` (raster/vector extraction) ; `tapetum_llm.md:68–79` ; whisker `CLAUDE.md` Lane 2 vs Lane 3 split.

## False-pass hypothesis

P3100R6 converts with all words present (`unigram_coverage` pass). A straw-poll table's SA/SF columns are visually swapped in the PDF grid, but tomd emits a readable pipe table with internally consistent headers; V4-Pro triage returns `tables=pass`, `structure=pass`, `confidence=0.81`, because every quoted cell substring exists and reads coherently — no pixel comparison is possible.

## False-fail hypothesis

A paper with `<!-- tomd:vector-extraction-uncertain: complex vector figure skipped -->` and no `![]()` for that figure: V4-Pro flags `structure=fail` / `major`, claiming a missing figure, when the source had no extractable raster and the sanctioned marker correctly documents the skip — a false fail on structure because the model infers a defect from absence of an image reference it cannot verify was required.

## What would change my mind

DeepSeek ships an open-weight **V4-VL** checkpoint (or documents image-token input on the same served name) with a vLLM path we can A/B on tapetum_llm, plus a benchmark on ≥20 WG21 papers where experts label figure-extraction and visual-table defects: if the multimodal deep slot reaches ≥85% recall on pixel-grounded defects while keeping ≤10% false-pass on text-only cases, the structural blind spot would be materially closed.
