# 14 - Tapetum-Lane-Fit

**Verdict:** usable-with-conditions — DeepSeek-V4-Pro is a credible deep-tier adjudicator on code, math, and English structure axes, but 94% hallucination/overconfidence, weak 1M retrieval, and non-calibrated confidence scores make the [0.35, 0.65] escalation band unreliable unless tier1 is recalibrated and grounding gaps on confident passes are closed.
**Confidence:** medium

---

## Axis-by-Axis Mapping

Architecture note: per `tapetum_llm.md`, **Gemma4 triages (tier1)**; **DeepSeek-V4-Pro adjudicates (tier2)** only when tier1 confidence is in [0.35, 0.65]. DeepSeek's weaknesses below apply at tier2; the escalation band applies to tier1 unless `--service` overrides both slots.

| Axis | Model weakness (from 00-baseline) | Expected performance | Likely failures | Cascade protection |
|---|---|---|---|---|
| **wording** | English proficiency strong (MMLU-Pro 87.5%); 94% hallucination / almost never abstains (S5.1) | **Good** reading; **Poor** quote fidelity | Paraphrased "evidence"; missed ins/del corruption when tokens preserved; Chinese-influenced register false-flags | `ground_spans` requires verbatim substring or >=0.90 fuzzy match; ungrounded non-pass demoted to `review`; sub-floor confidence (<0.50) demoted to `review` |
| **code** | LiveCodeBench 93.5%, BigCodeBench 63.9%; coding specialist SFT | **Strong** C++ comprehension | Fence-tag vs content confusion; indent/reflow false-flags; `requires`-clause boundary errors | Severity coupling: non-`major` axis `fail` becomes overall `review`; evidence must ground against fence content |
| **stable_names** | BPE tokenizer artifacts; MoE routing variance | **Med-high** recognition; **Med** exact-char preservation | Bracket truncation in quotes; model "corrects" `[P1234R5]` revision letters; tokenizer-normalized evidence fails grounding | Grounding on `normalized_text` helps fuzzy match but drops paraphrased labels; ungrounded fail/review demoted |
| **tables** | No table-specific benchmark; pipe tables are 1D token streams (prompt) | **Med** — best on obvious breakage | Cell/row swaps with preserved tokens (PRIMARY blind spot); merged-cell flattening missed when readable | `select_candidates` routes `lossy_table_count` / `table_parse_errors` papers as PRIMARY; chunk aggregation takes worst finding per axis |
| **xrefs** | MRCR 1M 83.5 vs Opus 92.9; CorpusQA 1M 62.0 vs 71.7; random-position misses at 1M | **Med-low** on long papers | Wrong revision letter; xref to section in another chunk invisible at tier1 | H2 chunking at 500K chars; **tier2 skipped for chunked papers** — DeepSeek never re-reads full doc; cross-chunk xrefs only as tier1 aggregate |
| **math** | HMMT 2026 95.2%; MGSM 84.4 | **Strong** | Inline `$...$` vs Unicode superscript confusion; `\frac{a}{b}` to `a/b` collapse missed if readable | Grounding via `normalized_text` (LaTeX folding); severity must be `major` for hard fail |
| **structure** | LongBench-V2 51.5; long-document training | **Med-high** on section order | Permuted sections (dominant false-pass target); chunk-boundary false-flags | Chunk note in triage message; heading-monotone RESCUE + severity `minor`/`review`; `partial` read blocks clean pass |

---

## Confidence Calibration: [0.35, 0.65] Band

**Assessment: not reliably calibrated for DeepSeek-V4-Pro; band is tier1-gated anyway.**

| Signal | Implication |
|---|---|
| 94% hallucination rate, "almost never abstains" | Model likely emits **extreme confidence** (>=0.85 or <=0.15), not uniform uncertainty in the ambiguous band |
| No abstention training (vs GLM-5 refusal mechanism) | Confidence field is **self-reported bravado**, not calibrated probability |
| `CONFIDENCE_AMBIGUOUS_LO/HI` marked **provisional** | Band adopted from LLM-judge literature, not fitted on tapetum labeled set |
| Tier2 DeepSeek confidence used at decide | Only matters post-escalation; `CONFIDENCE_DECISION_FLOOR=0.50` demotes sub-0.50 to `review` regardless of verdict |

**Escalation dynamics:** If Gemma tier1 is better-calibrated than DeepSeek, escalation works. If tier1 also clusters at extremes, tier2 is under-utilized. If both slots override to DeepSeek (testing/pod convenience), expect low escalation rate and high false-pass risk on confident passes with empty/ungrounded evidence.

**Gap:** demotion on ungrounded evidence applies only when verdict != `pass`. A confident `pass` with hallucinated-then-dropped evidence **still passes** — the lane never upgrades, but this is the primary false-pass vector.

---

## Findings

- [CRITICAL] 94% hallucination / abstention failure maps directly to **evidence_spans** integrity (00-baseline S5.1). Impact: high `ungrounded_dropped` counts waste tier2 calls; worse, confident `pass` with dropped quotes is **not demoted** (`adjudicate.py:237-238`). Cascade catches hallucinated *fails*, not hallucinated *passes*.

- [HIGH] Long-context retrieval weakness (MRCR 1M 83.5, CorpusQA 62.0) maps to **xrefs** and distant **structure** checks. Impact: within-chunk xref/section-order errors may survive; tier2 cannot help chunked papers because full-md re-injection is skipped (`adjudicate.py:203-204`).

- [HIGH] Schema-in-prompt JSON extraction affects all axes — invalid/truncated `Adjudication` triggers retry but not structural refusal. Impact: partial axis_findings or missing evidence_spans weaken per-axis coverage; decide falls back to model verdict when `axis_findings` empty (`adjudicate.py:229-232`).

- [MED] Code axis is DeepSeek's strongest fit (LiveCodeBench 93.5%, coding SFT). Impact: tier2 adds real value on ambiguous code-fence cases escalated from tier1; false-fail risk on cosmetic fence-language tags if severity mislabeled `major`.

- [MED] Table axis has no published V4 benchmark; PRIMARY candidate selection ensures table-risk papers reach the lane, but model may miss token-preserving cell swaps — the exact false-pass class tapetum exists to catch. Impact: table axis is highest-stakes, least benchmark-validated.

- [MED] Confidence band [0.35, 0.65] is provisional and mismatched to a model that rarely expresses calibrated uncertainty. Impact: tier2 under-triggered; when triggered, tier2 confidence may still be extreme, making `CONFIDENCE_DECISION_FLOOR` the only demotion lever.

- [LOW] English proficiency is adequate for WG21 markdown (MMLU-Pro 87.5%, thinking-in-English). Impact: **wording** axis reading quality is not the bottleneck; quote hallucination is.

- [LOW] Text-only limitation is structural but out of scope — tapetum reads markdown only; figure fidelity cannot be judged.

## False-pass hypothesis

A pass-tier paper with a **straw-poll table row swap** (SF/F/N/A values permuted but all tokens present, triggering PRIMARY via `lossy_table_count`). DeepSeek tier2 returns `pass`, confidence 0.92, with a paraphrased table quote that fails grounding and is dropped. Decide keeps `pass` because demotion requires `suggested_verdict != VERDICT_PASS` (`adjudicate.py:237`). Whisker gate stays green; committee reads wrong poll numbers.

## False-fail hypothesis

A correctly converted paper with an H2->H4 heading skip (RESCUE population). DeepSeek labels structure axis `fail`/`major` despite prompt instructing `minor`/`review` for heading-level jumps. If severity is `major`, `worst_axis_verdict` returns hard `fail`. Advisory suggests fail on a shippable cosmetic defect — human must override, but lane never hard-gates.

## What would change my mind

A tapetum mini-eval on 30-50 labeled WG21 papers showing: (1) DeepSeek tier2 confidence histogram with >=20% mass in [0.35, 0.65] when labels are ambiguous, (2) grounded-evidence rate >=90% on non-pass verdicts, (3) table-axis recall >=0.85 on token-preserving cell swaps, and (4) zero confident passes where all evidence spans were dropped.
