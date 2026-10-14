# Opus Meta-Review B - Extraction Axes Soundness

**Date:** 2026-07-02
**Reviewer:** Meta-Reviewer B (Extraction Axes Soundness)
**Scope:** `00-baseline.md`, `04-table-understanding.md`, `05-code-fidelity.md`, `06-heading-structure.md`, `07-math-notation.md`, `08-vision-image-capability.md`
**Codebase re-verification:** `packages/whisker/src/whisker/tapetum_llm/models.py`, `adjudicate.py`, plus `constants.py`, `chunking.py`, `grounding.py`, `gates.py`, `facts.py`, `tapetum_llm.md`, `tapetum-sighting-run-2026-07-01.md`, `research/persona/00-EVIDENCE-BASELINE.md`, `notes/QA-RELIABILITY-VERDICT.md`

**Overall verdict: the five extraction-axis personas are SOUND.** Claims are correctly labeled as lineage inference vs measurement, code citations check out (several to the exact line), and no persona asserts a V4-Pro failure it cannot evidence. Three soundness caveats found (Q3, §Cross-cutting), none invalidating a verdict.

---

## Q1. Table-understanding limitations (04): substantiated or lineage-inferred?

**Lineage-inferred, and honestly labeled as such.** 04's first [HIGH] finding states outright that V4-Pro has *zero* published table benchmarks and that all capability claims extrapolate from DeepSeek-R1/V3 scores (TableEval, CompTab, TableBench, CoTabBench, RealHiTBench). The mid-tier and merged-cell-weakness claims are substantiated **for the lineage** (CompTab: V3 merged 37.80%, transposed 25.00% EM; TableEval: 10-15% drops on nested tables) but explicitly *not measured on V4-Pro*. The persona's "medium" confidence and its "what would change my mind" (a V4-specific CompTab/TableEval eval) correctly price this in.

Codebase claims re-verified:

- "wide tables, more than 6-8 columns" and the six table failure modes: confirmed at `tapetum_llm.md` lines 68-79 (verbatim: "wide tables, more than 6-8 columns, are the usual victims", line 73).
- "merges flattened, but readable → at most `review`": confirmed, `tapetum_llm.md` line 79.
- The grounding claim (invented pipe-table fragments dropped by `ground_spans`): confirmed. `grounding.py` requires normalized-substring match OR rapidfuzz `partial_ratio >= 0.90` (`EVIDENCE_FUZZY_FLOOR`, `constants.py:50`).

**One unexploited caveat:** the fuzzy floor at 0.90 means a *near-verbatim* invented table quote (one cell value altered) can still ground. 04's claim that grounding "catches these by requiring exact substring match" (inherited from 00-baseline §5.1) slightly overstates the defense: it is exact-or-90%-fuzzy, and a 90%-similar hallucinated table row is precisely the failure shape tables produce. Minor, but the grounding defense is weaker on the tables axis than 00/04 imply.

**Q1 verdict: sound.** Inference is labeled as inference; no benchmark laundering detected.

## Q2. Code generation vs verification distinction (05): real gap or speculative?

**Real as a task-family mismatch; correctly framed as absence-of-evidence, not asserted failure.** The load-bearing structure is: (a) LiveCodeBench 93.5% measures synthesis; (b) CRUXEval literature (arXiv 2401.03065) documents that generation scores do not transfer to execution/verification reasoning; (c) V4-Pro's technical report publishes no CRUXEval-class number. Point (c) is the honest core: 05 concludes "we lack direct evidence V4-Pro can reliably verify code semantics," which is an evidential gap, not speculation dressed as measurement. The within-model spread (93.5 / 76.8 / 63.9 across LiveCodeBench / HumanEval / BigCodeBench, from 00-baseline) independently supports "benchmark choice dominates."

Codebase claims re-verified:

- `gates.py:115-129` `_gate_no_empty_code`: **exact line match.** The gate only fails empty fences; reflow/garbling inside a non-empty fence passes the deterministic gate, so the advisory lane really is the only catch, as 05 claims.
- `code_format.py` kerning artifacts (`template <typename From >`): confirmed in the module docstring (cited as lines 12-22; actual docstring spans ~10-28, examples at 16-18 — cite imprecise by a couple of lines, substance correct). The false-fail hypothesis (model flags sanctioned kerning normalization) is grounded in real converter behavior.
- Sighting-run citations (196/201 adjudicated, 0 tier-2 escalations, 5 JSON parse failures, both slots on alliance-pod): **all confirmed** against `tapetum-sighting-run-2026-07-01.md`.
- The false-pass mechanism "confident pass with empty evidence cannot be demoted": **confirmed in `adjudicate.py:237`** — the ungrounded-evidence demotion applies only when `suggested_verdict != pass`. A clean-looking pass with no evidence sails through by design.

**Q2 verdict: sound.** 05 is the only extraction persona that integrates the runtime sighting run, which strengthens it relative to its peers.

## Q3. Heading-structure assessment (06): grounded or just "no benchmark exists"?

**Grounded in substantially more than benchmark absence**, but with two soundness caveats.

What checks out:

- `gates.py:96-112` `_gate_heading_monotone`: **exact line match** (H-level jump > 1 hard-fails).
- The gate-vs-rubric divergence: confirmed. `tapetum_llm.md` line 52 calls the heading jump "cosmetic: severity `minor`, verdict `review` at most, never `fail`", and `chunking.py:worst_axis_verdict` + `adjudicate.py:_custom_decide` enforce the non-major-fail → review fold in code. 06's central point — V4-Pro must obey the rubric, not mirror the gate, or it inverts the RESCUE purpose — is architecturally accurate.
- "9/14 reference-free hard fails heading-only, P3941Rx at uni=0.999": confirmed in `research/persona/00-EVIDENCE-BASELINE.md` ("9 of 14 fails are heading_monotone").
- Chunk-boundary rules and front-matter contract cites (`tapetum_llm.md:35-36, 91-93`): confirmed at those lines.

**Caveat 1 (stale vs runtime evidence).** 06 never cites the 2026-07-01 sighting run, which directly bears on its false-fail hypothesis: the P3941R4 rescue **succeeded** (whisker fail → advisory review, confidence 0.95, structure `review`/`minor`, 1 grounded span). That is n=1 contrary evidence to the persona's headline risk, and it partially satisfies 06's own "what would change my mind" criterion (anecdotally, not at the ≥20-paper bar). The verdict (usable-with-conditions) survives, but the false-fail risk should be downweighted from where 06 left it.

**Caveat 2 (snapshot-dependent arithmetic).** The "64% of current hard fails" figure derives from the 9/14 snapshot; the *same* evidence-baseline file carries a later 382-paper count set (20 fails, 6 heading_monotone = 30%). The qualitative point (heading pedantry dominates fails) holds in both snapshots; the specific percentage is corpus-snapshot-dependent and should not be quoted as a stable number.

**Q3 verdict: sound with two caveats.** It triangulates code, corpus flag statistics, long-context numbers, and a documented production analog (DeepSeek-Reasonix heading/list conflation — external, unverifiable here, plausible) rather than resting on "no benchmark."

## Q4. Math-notation false-pass / over-correction claims (07): supported?

**Supported as a hazard by adjacent-task literature, correctly hedged, never claimed as a measured V4-Pro behavior.** The over-correction mechanism (model mentally reconstructs the intended formula from corrupted notation and rates it faithful) is evidenced by the PINK metric paper (VLM OCR over-correction) and Horn & Keuper's LLM-as-judge observations. Both are analogies: PINK is a vision-OCR task, Horn & Keuper's judges are GPT-5/Gemini/Mistral, not V4-Pro — and 07 says so explicitly ("we extrapolate from adjacent tasks; ... zero V4-Pro-specific evidence"). Combined with the 94% hallucination / near-zero abstention figure (00 §5.1), the false-pass concern is a coherent, honestly-derived risk, not a measurement.

Codebase claims re-verified:

- `facts.py:63` `FACT_MATH = "math"`: **exact line match.**
- `facts.py:173-181` `_math_surface` (keeps `^`, `_`, `=`; folds `\frac` via pylatexenc): **exact line match.**
- "0/382 papers with math facts populated": confirmed in `notes/QA-RELIABILITY-VERDICT.md` ("Lane 3 Comprehension (facts): NON-OPERATIONAL, 0/382"). The claim that no production calibration backs the math axis is accurate.
- Math axis rank 6 and the `\frac{a}{b} → a/b` target: confirmed at `tapetum_llm.md:51`; severity-fold cites (56-62) correct.
- The MATH-EM-64.5 vs HMMT-95.2 spread used to argue task-shape sensitivity is internally consistent with 00-baseline.

One judgment call worth recording: 07's false-pass example (`$O(n \log n)$` → `O(n log n)`) is semantically recoverable, so under the severity-coupling rules a correct adjudication might legitimately be `review`/`minor` rather than `fail` — the "false pass" there is a notation-purity miss, not a content loss. 07's framing ("semantically recoverable but notation-faithful it is not") acknowledges this. Not an error, but readers should not read that example as a major-defect miss.

**Q4 verdict: supported, with the analogy-not-measurement status clearly disclosed.**

## Q5. Vision/text-only finding (08): correctly documented, impact scope accurate?

**Yes on both counts. This is the best-evidenced persona of the five** (the only "high" confidence, and it earns it via primary sources: NVIDIA NIM modality listing, HF checkpoint contents, DeepSeek API docs, and the arXiv report's silence on any vision encoder). It also correctly de-conflates the consumer app's "vision mode" (mounted encoder, not in the MIT weights) from the self-hosted checkpoint — the exact trap third-party blogs fall into.

Codebase claims re-verified:

- `adjudicate.py:327` and `:348` (`ctx.inject_untrusted(...)`, markdown-only prompt construction): **exact line matches.** The model demonstrably never receives image bytes; the only image signal is `![alt](path)` text plus tomd honesty markers.
- Sanctioned-marker cites (`tapetum_llm.md:81-87`) and images-contract cite (line 40): confirmed. (The structure-axis cite "52-53" is off by one — the axis text is line 52 — immaterial.)
- The impact-scope table (ten undetectable-from-markdown error classes, 0% pixel fidelity visible, ~half of the prompt-listed table modes text-detectable): a fair reading of `tapetum_llm.md:68-79`. Delimiter damage, pipe-in-cell, and header loss leave textual traces; merged-cell association and visual-grid alignment do not. The "Rarely" ratings are defensible.
- The "no drop-in vision upgrade path in the V4-Pro slot" claim matches `SERVICES.toml` semantics as documented in 00-baseline §2.

One quibble: 08's false-fail hypothesis (model flags a `tomd:vector-extraction-uncertain` marker as a structure fail) presumes the model *disobeys* an explicit system-prompt rule ("never flag sanctioned markers", `tapetum_llm.md:83-87`). That is a prompt-obedience failure scenario, not a structural one — plausible given the schema-in-prompt serving path, but it should be read as a weaker-order hypothesis than the pixel-blind-spot findings.

**Q5 verdict: correctly documented, scope accurate.**

## Q6. Cross-persona contradictions on extraction capabilities

**No genuine contradictions found.** The apparent tensions resolve as complementary views of the same ambiguity:

| Pair | Apparent tension | Resolution |
|---|---|---|
| 04 vs 08 (tables) | 04: swaps are a realistic miss; 08: swaps "rarely" detectable | Same claim from two angles: both say token-preserving positional damage is the false-pass class. Consistent. |
| 04 false-fail vs 08 merged-cell finding | 04: model may over-flag correct repeated values; 08: wrong repeats indistinguishable from correct ones | Two sides of one ambiguity (repetition-is-correct for pipe tables); both follow from the no-ground-truth condition. Complementary. |
| 06 vs 08 (structure) | 06: permutes catchable via global section-sequence scan; 08: only when heading markers reveal the permute | 08's is the precise statement; 06's false-pass hypothesis actually agrees (local scanning misses global order). Consistent. |
| 05 vs 07 (false-fail style) | 05: kerning spaces over-flagged; 07: `<T>` templates confused with math | Same over-flagging failure family on adjacent axes. Consistent. |
| Verdicts | All five: usable-with-conditions | Uniform; no persona is an outlier on extraction capability. |

The one **shared factual pattern** worth naming: 04, 06, and 07 all lean on the 94% hallucination figure from a single source chain (AA-Omniscience via jacksunwei.me, per 00 §5.1). That figure measures abstention behavior on knowledge queries, not evidence-quoting on provided documents; the transfer to "will invent evidence spans" is plausible but is a *shared single-source assumption*, so the three personas are correlated, not independent, on that point.

## Cross-cutting findings from codebase re-verification

1. **`models.py` docstring overclaims "constrained decoding."** Lines 12-16 describe the Adjudication schema as "(pydantic, constrained decoding)", but 00-baseline §4 (correctly) documents that `VllmThinkingBackend` uses schema-in-prompt + raw JSON extraction — the model is NOT constrained-decoded on our serving path. The personas all used the correct (schema-in-prompt) model; the code comment is the stale artifact. Recommend a docstring fix.
2. **The sighting run's 0/201 tier-2 escalations is an underused calibration signal.** Every tier-1 confidence landed outside [0.35, 0.65] (`constants.py:22-23`), which corroborates the overconfidence/poor-calibration concern raised abstractly in 04/06/07 — a well-calibrated judge on 201 borderline candidates should land in the ambiguous band sometimes. Only 05 cites the run at all; none draws this inference. The 5 JSONDecodeError failures in the same run also empirically confirm 00 §5.3's structured-output concerns.
3. **Baseline schema/constant claims all verified.** Adjudication: 7 fields, reasoning-first, confidence bounded [0,1] (`models.py:72-86` — cite exact). Constants: 0.35 / 0.65 / 0.50 / 500,000 / 0.90 all match `constants.py`. Escalation gating and chunked-paper tier-2 skip confirmed in `adjudicate.py:195-212` (chunked papers never escalate — a scope limit 00-baseline does not mention but which caps deep-slot exposure for the largest papers).
4. **Grounding is exact-or-0.90-fuzzy, not strictly verbatim.** Several files describe grounding as "exact substring match"; `grounding.py:49-52` accepts rapidfuzz `partial_ratio >= 0.90` as an alternative. Slightly weakens the anti-hallucination defense claimed in 00/04; worth propagating to the synthesis.

## Bottom line

All five extraction-axis personas survive re-verification. Their common epistemic posture — "no V4-Pro-specific eval exists for this axis; lineage and adjacent-task evidence say the risk is real; a ≥20-paper labeled WG21 eval would settle it" — is honest and consistent, and each one's "what would change my mind" names the same missing artifact. The synthesis should (a) treat the labeled tapetum eval set as the single highest-value action item, since it discharges all five personas' conditions at once, (b) fold in the sighting-run calibration signal (0 escalations, 5 JSON failures) that most personas predate or ignore, and (c) correct the two documentation nits (`models.py` "constrained decoding"; "exact substring" grounding descriptions).
