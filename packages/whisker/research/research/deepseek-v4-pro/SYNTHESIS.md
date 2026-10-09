# DeepSeek-V4-Pro - Research Synthesis

**Verdict band:** usable-with-conditions | **Confidence:** medium
**Decision vs our codebase:** adopt (gated on three blocking conditions)
**Freshness:** verified 2026-07-02 by 4 Composer scouts (see `17-freshness-addendum.md`), verdict MOSTLY-CURRENT, no core finding flipped. Serving-stack details corrected below.

## Summary

- DeepSeek-V4-Pro (1.6T params, 49B active MoE, April 2026, MIT license) is the strongest open-weight model available for the tapetum_llm advisory lane. It is near-parity with Claude Opus 4.6 on coding benchmarks (SWE-bench 80.6% vs 80.8%, LiveCodeBench 93.5% vs 88.8%) while being self-hosted on RunPod at zero per-token cost. Evidence: arXiv:2606.19348, NIST CAISI evaluation (May 2026), HuggingFace model card. SWE-bench spread across harnesses: 74% (CAISI held-out) / 80.6% (self-report) / 82.8% (Vals.ai, 2026-07-01). The AA Intelligence Index dropped 52 -> 44 in June under a methodology rebaseline (v4.1), not a capability regression.
- Timeline notes (as of 2026-07-02): V4 graduates preview -> stable mid-July 2026 (hosted API; self-hosted weights unchanged since April 27). DSpark variants (June 27) are the same checkpoint plus a speculative-decoding drafter, a serving optimization only. V4.1 is unconfirmed rumor. Legacy API aliases retire 2026-07-24.
- NIST CAISI independently evaluated V4-Pro as ~8 months behind the US frontier on held-out benchmarks (PortBench 44%, ARC-AGI-2 46%, CTF-Archive-Diamond 32%), but these benchmarks measure agentic reasoning, not markdown fidelity verification. Evidence: NIST CAISI report, May 2026.
- The model's chief behavioral weakness is abstention failure: it almost never declines to answer when uncertain (94% non-abstention rate on AA-Omniscience, Artificial Analysis). This transfers to evidence-span invention, with an estimated 25-45% of emitted evidence quotes failing verbatim grounding. Evidence: persona 12, corroborated by Digital Applied citation tests, FullCite/CAMS benchmarks.
- The tapetum_llm cascade's grounding, confidence floor, and severity-aware demotion protect against hallucinated fails and cosmetic false-fails. However, the demotion logic is **asymmetric**: it audits fails/reviews but not confident passes (`adjudicate.py:237`). This is the primary false-pass vector. Evidence: persona 14 CRITICAL, confirmed by meta-reviewer E.
- The sighting run (2026-07-01, alliance-pod, 196/201 papers) demonstrates end-to-end viability: 72 review-to-pass clears, 6 fail-to-review rescues, zero 413 errors on 7-chunk oversized papers. However, tier2 was never exercised (0 escalations), all slots used the same model, and none of the 72 clears have ground-truth labels. Evidence: `packages/whisker/research/tapetum-sighting-run-2026-07-01.md`.
- The model is text-only (no vision). Image extraction fidelity is structurally unverifiable by any text-only model. This is a known, accepted architectural limitation. Evidence: HuggingFace model card, DeepSeek API docs.

## Top Findings (ranked)

1. **[CRITICAL][ACTIONABLE-NOW]** Confident-pass grounding gap: a `pass` verdict with all evidence spans dropped by grounding is not demoted to `review`. Evidence: `adjudicate.py:237`. Fix: one code change. Adopt? yes (blocking).
2. **[CRITICAL][ACTIONABLE-NOW]** Sighting run's 72 review-to-pass clears are unaudited against ground truth. Evidence: sighting-run document lists them as "suggested review targets." Fix: human-audit ~30 of 72. Adopt? yes (blocking).
3. **[CRITICAL][ACTIONABLE-NOW]** Pod deployment flags unverified: vLLM needs `--tokenizer-mode deepseek_v4 --reasoning-parser deepseek_v4 --tool-call-parser deepseek_v4` (target **v0.24.0**, released 2026-06-29; minimum 0.21.0). The originally cited parser bugs #41132/#41240/#41483 are fixed (v0.20.1-v0.21.0); current watchlist: #46256 (tokenizer ignores `add_generation_prompt`, silent wrong output on multi-turn), #46710 (inline system messages), #47174 (`--kv-cache-dtype auto` trap on SM120), #40801 edge case (DSML leak with auto tool choice, no merged fix). Evidence: vLLM blog 2026-04-24, freshness addendum scout 3. Fix: manifest check. Adopt? yes (blocking).
4. **[HIGH]** Schema-in-prompt structured output is voluntary, not constrained-decoded. 7-field nested Adjudication schema relies on model compliance + 2-attempt retry. Sighting run showed 5 hard JSON failures and pervasive first-attempt retries. June community reports add illegal JSON in tool calls (#1448) and empty responses after tool feedback (#1453) on the hosted API. Evidence: `model_backends.py:125-132, 360-410`; freshness addendum scout 4. Adopt? yes (monitor parse rate).
5. **[HIGH]** Long-context retrieval degrades after 128K (MRCR 0.82 at 256K, 0.59 at 1M). H2-chunking at 500K chars (~125K tokens) keeps individual calls near the 128K inflection point. Within-chunk misses remain possible and are **non-deterministic**: the Lightning Indexer sporadically misses compressed blocks rather than decaying smoothly. Evidence: arXiv:2606.19348 Figure 9, Skywork stress tests, freshness addendum scout 4. Adopt? yes (chunking mitigates).
6. **[HIGH]** MoE routing variance on shared pod: 49B active of 1.6T, FP4+FP8 mixed precision. Serial semaphores eliminate cross-request interference on our side, but foreign batch traffic on the shared alliance-pod can flip expert routes. Evidence: `MODELS.md`, persona 13. Adopt? yes (use dedicated pod for reproducibility-critical runs).
7. **[MED]** `chars_per_token = 4.0` is unmeasured on V4-Pro's tokenizer (distinct from V3/R1). Code-heavy windows drop to ~2.5 chars/token (+60% token undercount). The 393K configured window is safe for tapetum_llm. Evidence: `MODELS.md:111`, persona 15. Adopt? yes (measure and update).
8. **[MED]** No V4-Pro-specific benchmarks exist for table understanding, code verification (vs generation), heading-structure audit, or math-notation verification. Capability is inferred from lineage (R1/V3) and general benchmarks. Evidence: personas 04-07, meta-reviewer B. Adopt? yes (labeled mini-eval will fill the gap).
9. **[LOW]** English proficiency is strong (MMLU-Pro 87.5%, thinking defaults to English). Chinese-origin training data composition is undisclosed but does not measurably impact English technical output quality. Evidence: persona 03, HuggingFace model card. Adopt? yes.
10. **[LOW]** `token_multiplier = 1.5` is deprecated dead config with no active call sites. Evidence: persona 15. Adopt? yes (clean up documentation).

## Bugs / edge-cases in OUR code (surfaced by the comparison)

- `adjudicate.py:237`: confident `pass` with all evidence dropped is not demoted. The demotion guard checks `suggested_verdict != VERDICT_PASS`, so passes are exempt. Fix: add `if suggested_verdict == VERDICT_PASS and not grounded and evidence_was_emitted: suggested_verdict = VERDICT_REVIEW`.
- `model_backends.py:434` docstring says "tool-call-parser gemma4" but V4-Pro needs `deepseek_v4`. The parser is server-side, not client-side, but the docstring is misleading.
- `MODELS.md` workaround table says `VllmThinkingBackend` has "no tools" but the class has `_run_with_tools` and both V4 pods declare `tools_capable = true`. Either update the table or flip `tools_capable = false` until the tool path is smoke-tested on V4.
- `SERVICES.toml` V4 entries lack any comment about required vLLM flags (tokenizer-mode, reasoning-parser, tool-call-parser). These should be documented adjacent to the service declaration.

## Top portable detail

The **demotion asymmetry** pattern (grounding audits fails but not passes) is a general LLM-judge cascade design flaw that applies to any system where an LLM produces a pass/fail verdict with evidence. The fix (audit confident passes that lost all evidence) should be adopted in any future cascade.

## Flip conditions

- **Up to usable:** blocking conditions 1-3 resolved, labeled mini-eval (>=50 papers) shows false-clear rate <= 5% on the pass channel, confidence histogram has >=20% mass in [0.35, 0.65] for genuinely ambiguous cases, and grounded-evidence rate >= 90% on non-pass verdicts.
- **Down to garbage:** labeled mini-eval shows post-decide wrong advisory fails >15% with human agreement, AND the failures are not demotable by existing guardrails after condition 1 is applied.

---

Sources: arXiv:2606.19348 (DeepSeek V4 technical report, June 2026), NIST CAISI evaluation (May 2026), HuggingFace deepseek-ai/DeepSeek-V4-Pro model card, Artificial Analysis AA-Omniscience benchmark, Vals.ai SWE-bench leaderboard (2026-07-01), Epoch AI ECI, vLLM blog 2026-04-24 and v0.24.0 release notes (2026-06-29), sighting-run document 2026-07-01, GitHub issues deepseek-ai/DeepSeek-V3 #1244/#1376/#1257/#1448/#1453/#1464/#1471, vllm-project/vllm #41132/#41240/#41483/#40801/#46256/#46710/#46796/#47174.
Personas: 16. Meta-reviewers: A (benchmark validity), B (extraction axes), C (serving/engineering), D (web provenance), E (steelman + balance). Freshness pass: 4 Composer scouts, 2026-07-02 (`17-freshness-addendum.md`).
