# Meta-Reviewer E: Steelman + Balancing Decision

**Date:** 2026-07-02
**Inputs:** 00-baseline.md, persona reports 01-16, `packages/whisker/research/tapetum-sighting-run-2026-07-01.md` (verified directly, not via persona citation).
**Verdict tally:** 15/16 personas say **usable-with-conditions** (confidence: medium x14, high x1); the Steelman alone says **usable** (high confidence).

---

## Steelman Audit (is the FOR case honest?)

**Mostly honest, with two load-bearing omissions and one internal contradiction.**

What the Steelman gets right, and where it is actually *more* rigorous than the critics:

1. **The 94% reframe is correct.** The Steelman's claim that AA-Omniscience measures "answer anyway on trivia," not "quote a substring from a document you were just shown," is independently confirmed by persona 12's own CRITICAL finding (the metric is `incorrect / non-correct` on 6,000 parametric-knowledge questions). The Steelman is not spinning here; it is correcting a misreading that several critics inherited uncritically (see Pile-On Check).
2. **Advisory-only is architecturally verified.** Multiple personas independently confirm in code that the lane never gates, never overwrites the whisker verdict, and demotes on sub-floor confidence, ungrounded non-pass evidence, and partial reads. The safety nets are real, not marketing.
3. **Its falsifier is fair.** "What would change my mind" names a concrete, measurable condition (>15% wrong advisory fails on a >=50-paper labeled holdout, human-confirmed, not demotable).

Where it papers over:

1. **The confident-pass grounding gap is never mentioned.** Persona 14's CRITICAL finding: demotion on ungrounded evidence fires only when `suggested_verdict != pass` (`adjudicate.py:237`). A confident `pass` whose hallucinated evidence was silently dropped **still passes**. The Steelman's finding 2 claims "hallucinated evidence... structurally demoted" without the qualifier that this holds only for non-pass verdicts. That qualifier is the whole ballgame, because passes are the lane's headline product.
2. **Internal contradiction on the human-in-the-loop.** The Steelman defends its own false-pass hypothesis with "a human reviewing `--inspect` side-by-side still sees whisker risk signals." But the sighting run's headline value, which the Steelman itself cites as validation, is **72 review -> pass** clears, i.e. the advisory telling humans *not* to look. The FOR case cannot simultaneously sell the lane on removing human review and absorb its false passes by assuming human review. This is the single place where the Steelman is rhetorically dishonest rather than merely selective.
3. **The sighting run validates less than claimed.** Verified against the run document: (a) **tier2 escalations = 0**, so the deep-tier cascade and the [0.35, 0.65] confidence band the Steelman praises were never exercised; (b) fast, deep, and default slots were all `alliance-pod` (same model), so the Gemma-triage / DeepSeek-adjudicate split was not tested; (c) **none of the 72 clears or 6 rescues have ground-truth labels yet**, the run itself lists them as "suggested review targets... potential golds." Zero escalations is also weak corroboration of persona 14's calibration concern: tier1 confidence never landed in the ambiguous band across 196 papers, consistent with a model that emits extremes.
4. **Serving-stack risks are omitted entirely.** Persona 11's CRITICAL finding (the `deepseek_v4` parser-flag triad is not declared in SERVICES.toml; vLLM >= 0.21.0 floor; MTP/flashinfer failure classes) and the run's own weaknesses (5 JSON hard failures at "line 49 column 17," pervasive first-attempt parse retries, a burst of ~74 transient HTTP 500s) do not appear in the FOR case.

**Net:** the Steelman's core argument, advisory-only + grounding + confidence floor makes the failure profile survivable, is structurally sound for *fail/review* outputs and unsound for *pass* outputs. It is an honest brief with a blind spot exactly where the risk concentrates.

## Pile-On Check (are criticisms independent?)

**Partial pile-on; the consensus survives it.**

The 94% figure appears in roughly nine reports (01, 02, 04, 05, 06, 07, 12, 13, 14). Independence breakdown:

- **Genuinely independent (3):** Persona 12 re-derived the metric definition, brought four new corroborating sources (Digital Applied 15.7% citation hallucination, the biomedical reference study, FullCite Snippet-F1, CAMS), and produced the only quantified transfer estimate (30-40% per-span drop rate). Persona 14 applied the number to a distinct mechanism (confidence-band calibration, "self-reported bravado"). Persona 01 cited the primary Artificial Analysis source with its own corroboration.
- **Inherited from 00-baseline S5.1 (5-6):** Personas 04, 05, 06, 07, 13 cite the number as-received, without checking the metric definition. Persona 06's phrasing ("hallucinates on 94% of queries where it should abstain") is approximately right; others use it as loose severity garnish.

**Implication for severity weighting:** the 94% number is **one finding, not nine**. Counting CRITICAL/HIGH flags across reports overstates the hallucination case by roughly 3x. However, the pile-on does not corrupt the verdict, because the single best analysis (12) both *narrows* the number (it is not an ungrounded-quote rate) and *confirms* the underlying behavioral concern (the guess-instead-of-abstain reflex transfers to evidence-span invention, with independent literature support). A pile-on that survives its own strongest debunking attempt is a real finding.

Non-94% findings show healthy independence: long-context (09), serving/tokenizer (11), structured output (10), token budget (15), vision (08), and tables (04) each rest on distinct evidence bases with minimal cross-citation.

## Conditions Assessment (are they actionable?)

**Yes, after filtering.** The 16 "what would change my mind" clauses split into three tiers:

**Blocking, must be done before trusting production output (all cheap, all concrete):**

1. **Close the confident-pass grounding gap.** One code change in `adjudicate.py`: a `pass` verdict whose emitted evidence spans were *all* dropped by grounding (or that arrived with empty evidence on a PRIMARY-risk paper) is demoted to `review`, or at minimum flagged in the inspect report. This converts the primary false-pass vector (personas 12, 14, 05 all converge on it) into the same demotion path that already protects fails.
2. **Ground-truth the sighting run's own suggested golds.** Human-verify the 6 fail -> review rescues and a random sample (20-30) of the 72 review -> pass clears. Acceptance: false-clear rate <= 5%. Until this exists, the run's headline yield is unaudited.
3. **Verify the pod deployment.** Confirm vLLM >= 0.21.0 with `--tokenizer-mode deepseek_v4 --reasoning-parser deepseek_v4 --tool-call-parser deepseek_v4`, record MTP and flashinfer-autotune status, log vLLM version per call. This is a manifest check, not an experiment (persona 11).

**Operational, first 30 days of production use:**

4. Telemetry: first-attempt Adjudication JSON parse rate (target >= 98%; the sighting run's 5 hard failures plus pervasive retries suggest we are below it), `ungrounded_dropped / total_spans_emitted` per run, and a fixed-paper re-run stability check (verdict flip rate <= 2%, persona 13).
5. The labeled mini-eval (30-50 WG21 papers, persona 14's four-metric spec: confidence histogram mass in the ambiguous band, grounded-evidence rate >= 90% on non-pass, table-swap recall, zero confident passes with all spans dropped). This is the condition that would move the verdict band, and it doubles as the eval most single-axis personas (04, 05, 06, 07, 09) asked for.
6. Measure `chars_per_token` on the live V4 endpoint including one code-heavy paper (persona 15); delete or re-document the dead `token_multiplier`.

**Non-actionable (informational only, must not gate the decision):** DeepSeek publishing corpus language histograms (03), an open-weight V4-VL shipping (08), and third-party WG21-register benchmarks appearing (01). Waiting on these would be waiting forever.

## Single Most Important Finding

**The lane's demotion machinery is asymmetric, and the asymmetry points at its headline product.** Grounding and confidence-floor demotions audit *fails and reviews*; nothing audits a *confident pass* whose evidence was hallucinated and silently dropped (`adjudicate.py:237`, persona 14 CRITICAL). Meanwhile the sighting run shows the lane's chief value is exactly confident passes: 72 review -> pass clears that tell a human not to look, none yet verified against ground truth. Combined with the one model trait every independent analysis confirmed (V4-Pro guesses instead of abstaining when uncertain), the expected failure mode is not a noisy fail, it is a clean-looking clear. The 94% headline number is a red herring in its naive reading; the abstention *reflex* behind it, landing in the one output slot with no safety net, is the real finding. It is also the cheapest to fix of any CRITICAL raised.

## Recommended Verdict Band

**usable-with-conditions. The consensus is correctly calibrated, neither too harsh nor too lenient.**

- **Not too harsh:** "usable" (the Steelman's band) requires trusting the pass channel, and today that channel has (a) an identified structural gap, (b) zero ground-truth validation of the 72 clears, (c) an unexercised deep tier and confidence band, and (d) an unverified serving config. Every one of those is fixable within days; none is fixed yet.
- **Not too lenient:** "garbage" would require the safety nets to be fake. They are not; multiple personas verified never-gates, grounding, the confidence floor, and severity folding in code, and the sighting run demonstrates real yield (196/201 adjudicated, the P3941R4 rescue behaving exactly per rubric, 7-chunk oversize handling with zero 413s). The hallucination rate, read correctly per persona 12, does not transfer at face value to in-context quoting.
- The gap between the Steelman's "usable" and the consensus is not a factual dispute. It is one unstated assumption: the Steelman prices the false-pass risk as if a human still reviews, while the lane's purpose is that they will not. Resolve that assumption (conditions 1 and 2) and the two positions converge.

## Decision Recommendation

**ADOPT DeepSeek-V4-Pro for the tapetum_llm advisory lane, gated on blocking conditions 1-3.**

Rationale: the alternative set is empty or worse. The lane requires an open-weight, self-hostable model (model-sovereignty invariant, non-negotiable per root CLAUDE.md); V4-Pro is the strongest available open-weight model on the axes the lane exercises (code comprehension, long technical English documents), it is already deployed on per-hour billing making re-runs free, and one full-corpus run has demonstrated end-to-end viability. Rejecting it means either a weaker open-weight model with the same unknowns and less capability, or retreating to a cloud API, which the architecture forbids.

Sequencing:

1. **Now:** apply blocking conditions 1-3 (one code change, one human audit of ~30 papers, one deployment manifest check). Do not treat review -> pass clears as human-review waivers until conditions 1 and 2 land.
2. **First 30 days:** run operational conditions 4-6. If the labeled mini-eval hits persona 14's thresholds, upgrade the band to **usable** and retire this review's caveats.
3. **Standing exit criterion** (adopt the Steelman's own falsifier, it is the fairest one written): if a >= 50-paper labeled holdout shows post-decide wrong advisory fails above 15% with human agreement, or the pass-channel audit shows a false-clear rate materially above 5% after condition 1 lands, revisit the adoption, first by re-splitting the cascade (Gemma tier1 / V4-Pro tier2 as designed) before abandoning the model.

One dissent worth recording: the deep-tier (tier2) role specifically is **unvalidated, not validated**, by everything above. Zero escalations means we have adopted V4-Pro on tier1 evidence. If recalibrating the ambiguous band ever produces real escalation traffic, tier2 output deserves its own spot-audit before it is trusted.
