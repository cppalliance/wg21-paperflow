# 07 - Math-Notation

**Verdict:** usable-with-conditions — V4-Pro has strong mathematical reasoning and native LaTeX fluency, but published benchmarks measure problem-solving, not notation-fidelity adjudication; the tapetum_llm `math` axis has no direct eval and inherits the model's abstention/hallucination risks.
**Confidence:** medium

## Findings

- [HIGH] **HMMT 95.2% and GSM8K 92.6% measure solving, not notation verification.** Evidence: `00-baseline.md` §1 benchmark table; arXiv 2606.19348 reports MATH EM 64.5% (competition-style proofs) vs HMMT 95.2% (2026 contest). Impact: high solve scores do not bound false-pass rate on tapetum's task (detect `\frac{a}{b}` collapsed to `a/b`, lost superscripts, garbled `\(...\)` delimiters). The MATH/HMMT gap suggests formal-notation sensitivity varies by task shape; adjudication is closer to "is this token string faithful?" than "what is the answer?"

- [HIGH] **No published benchmark tests V4-Pro as a notation-fidelity judge on markdown.** Evidence: Horn & Keuper, "Benchmarking Document Parsers on Mathematical Formula Extraction" (arXiv 2512.09874): LLM-as-judge on formula *pairs* achieves Pearson r=0.78 with humans, but evaluators are GPT-5/Gemini/Mistral, not DeepSeek-V4-Pro; V4-Pro appears only as a text reasoning model, not in the formula-extraction leaderboard. TexOCR-Bench (ACL 2026) tests page-to-LaTeX reconstruction, not post-conversion QA. Impact: we extrapolate from adjacent tasks; tapetum's `math` axis (rank 6, `tapetum_llm.md:51`) has zero V4-Pro-specific evidence.

- [HIGH] **DeepSeek models natively emit `\(...\)` / `\[...\]` LaTeX, confirming training-corpus fluency with WG21-relevant delimiters.** Evidence: DeepSeek-Reasonix PR #2510 (May 2026): "DeepSeek (and most LLMs) emit math with `\(...\)` (inline) and `\[...\]` (block) delimiters"; DeepSeek-Math-V2 docs document the same convention; hollama issue #263 confirms DeepSeek-R1 uses standard LaTeX syntax. Impact: V4-Pro should *read* and *reason about* the delimiter families tomd emits; delimiter confusion is unlikely. Residual risk: markdown parsers eat `\(` as escaped paren (Reasonix root cause), so the model must judge the *stored* markdown string, not a rendered view.

- [MED] **LLM judges over-correct broken notation, a direct false-pass hazard for tapetum.** Evidence: arXiv 2604.22774 (PINK metric, 2026): VLMs "fix" student handwriting during OCR; 60.9% of BLEU-flagged discrepancies are formatting-only, but models still assign high semantic scores to over-corrected transcriptions. Horn & Keuper §4.4: LLM-as-judge "occasionally assigning imperfect scores to identically rendered formulas" and can miss subtle semantic errors. Impact: V4-Pro may mentally reconstruct the intended formula from a corrupted `\frac{a}{b} → a/b` string and rate the conversion `pass`. Combined with baseline §5.1 (94% hallucination / near-zero abstention), the model may also invent plausible evidence quotes for math it "knows" should be there.

- [MED] **V4-Pro is text-only; the math axis cannot cross-check against the source PDF.** Evidence: `00-baseline.md` §5.6; tapetum receives markdown only (`tapetum_llm.md:97-98`, evidence must be verbatim from markdown). Impact: adjudication is self-consistency checking ("does this look like a faithful formula?"), not reference comparison. Obvious corruption (empty superscripts, `\sqrt` → `sqrt`, unbalanced `$`) is detectable; subtle glyph-level errors that still parse as valid LaTeX are not.

- [MED] **Whisker's deterministic math surface folds LaTeX to Unicode, hiding some defects from token gates and potentially from the model.** Evidence: `packages/whisker/src/whisker/metrics.py` `textblock2unicode` folds `$...$` and `\(...\)` via pylatexenc; `test_metrics.py:220-225` shows `$x_1$` and bare `x_1` normalize identically. `facts.py:173-181` `_math_surface` keeps `^`, `_`, `=` but folds `\frac`. Impact: `\frac{a}{b}` collapsed to `a/b` is exactly the failure mode tapetum targets (`tapetum_llm.md:51`); the model must catch it from raw markdown, not from normalized agreement. Lane 3 `math` facts exist (`facts.py:63`) but QA audit reports 0/382 papers with math facts populated (`whisker/notes/QA-RELIABILITY-VERDICT.md`), so no production calibration backs the axis.

- [LOW] **Template-parameter syntax overlapping math (`<T>`, `std::vector<T>`, `requires` clauses) is an unbounded false-fail/false-pass class.** Evidence: no V4-Pro-specific eval found; general LLM markdown pipelines struggle with `$` vs currency (`llama.cpp` PR #16508, Gemma-4 `$\$0.60$` quirk). WG21 papers mix code fences with inline math and angle-bracket templates. Impact: V4-Pro may flag legitimate C++ syntax as math corruption or treat template noise as acceptable. tapetum ranks `code` (axis 2) above `math` (axis 6), partially mitigating template-heavy regions.

- [LOW] **DeepSeek-OCR (separate 0.6B vision model) scores mid-tier on formula extraction; V4-Pro inherits no OCR capability.** Evidence: pdf-parse-bench 2026-Q1: DeepSeek-OCR 8.95 inline / 9.02 display (rank 14/22); Horn & Keuper Table 1: DeepSeek-OCR 8.55 overall. Impact: irrelevant to tapetum (which reads tomd output, not pixels), but confirms the DeepSeek *family* is not SOTA at formula transcription; V4-Pro's math strength is reasoning over text, not vision-verified glyph fidelity.

## False-pass hypothesis

A WG21 paper contains `The complexity is $O(n \log n)$` in the PDF. tomd emits `The complexity is O(n log n)` (dropped math delimiters and backslashes, but readable). Unigram coverage stays high because every token is present. V4-Pro recognizes the intended complexity class, rates the axis `pass` with high confidence, and either supplies no evidence or quotes the plaintext `O(n log n)` without flagging the missing `$...$` wrapper. The conversion is semantically recoverable but notation-faithful it is not.

## False-fail hypothesis

A paper uses `\(...\)` inline math adjacent to C++ template syntax: `for \(...\) in std::vector<T>`. tomd correctly preserves both, but V4-Pro treats the `\(` / `\)` pair as a conversion artifact or confuses `<T>` with malformed math, emitting a `math` axis `fail` with `major` severity despite faithful conversion. tapetum's severity fold (`tapetum_llm.md:56-62`) would demote only non-major fails, so a mislabeled `major` could still escalate review load.

## What would change my mind

A labeled tapetum eval set of 20+ math-heavy WG21 papers (papers with `\frac`, `\sqrt`, `$...$`, `\(...\)`, display math, and complexity notation) with human-verified math-fidelity labels, run through the full triage→adjudicate cascade on V4-Pro, showing ≥90% agreement with human `pass`/`fail`/`review` on the `math` axis and ≤5% false-pass on collapsed-fraction / lost-superscript cases.
