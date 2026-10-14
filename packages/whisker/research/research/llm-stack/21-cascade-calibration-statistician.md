# 21 - Cascade-Calibration-Statistician

**Verdict:** usable-with-conditions — the advisory lane demotes and grounds safely, but the two-tier cascade and both confidence thresholds are inert in production because DeepSeek self-reported confidence never enters the designed operating region.
**Confidence:** high

## Findings

- [CRITICAL] The ambiguous band never fired: 0 / 198 sidecars have `escalated=true`, and 0 / 198 tier-1 confidences fall in `[CONFIDENCE_AMBIGUOUS_LO, CONFIDENCE_AMBIGUOUS_HI]` = [0.35, 0.65]. Evidence: reproduced histogram over `data/whisker/*.tapetum.json` (min=0.85, max=1.00, mean=0.9586, median=0.95, p05=p10=p25=0.95, 194/198 in [0.95, 1.01]); gate at `adjudicate.py:206-208`; constants at `constants.py:22-23`. Impact: Step 2 (`adjudicate.py:195-212`, `tapetum_llm.md:135-147`) is dead code in the 200-paper batch; the documented "two-tier cascade" is single-tier in practice.

- [CRITICAL] Self-reported confidence is anti-calibrated: every suggested `fail` carries confidence >= 0.95 (18/18 fails, mean 0.9539). Evidence: reproduced cross-tab on 198 sidecars; `models.py:84` accepts any float in [0,1] with no calibration constraint; prompt asks for "calibrated certainty" (`tapetum_llm.md:127`) but the model emits bravado. Impact: the cascade cannot distinguish uncertain from confident failures; `CONFIDENCE_DECISION_FLOOR = 0.50` (`constants.py:28`, applied at `adjudicate.py:239-240`) demoted 0/198 papers, so the floor is also inert.

- [HIGH] Even if the band fired, escalation would be a no-op model swap: both `fast` and `deep` resolve to `alliance-pod` (`tapetum_llm.md:17-19`); reproduced `tier1_model={'alliance-pod'}`, `tier2_model=∅` on all 198 sidecars. Impact: a triggered escalation buys a second serial pass on the same DeepSeek-V4-Pro pod, not a larger or differently-calibrated judge; cost savings and quality uplift from tiering are both illusory until slots diverge.

- [HIGH] A derived uncertainty signal already present in outputs would have triggered escalation 123/198 times, but the gate ignores it. Evidence: reproduced count of papers where per-axis verdicts disagree (e.g. one axis `pass`, another `review`/`fail`); gate uses only scalar `state.tier1.confidence` (`adjudicate.py:206-208`). Impact: the model expresses internal conflict across seven fidelity axes while reporting 0.95+ overall confidence; axis-disagreement, ungrounded-drop rate (9/198 had `ungrounded_dropped > 0`), or raw-JSON retry count (`model_backends.py:76-85`) are better escalation triggers than self-reported bravado.

- [MED] Chunk aggregation uses minimum confidence, which can only shrink the band downward, never widen it. Evidence: `chunking.py:155-161`, `chunking.py:187` (`confidence = min(a.confidence for a in parts)`); 4/198 sidecars show chunked aggregation text. Impact: for the ~6 oversize papers in corpus (`constants.py:42-43`), min-fold pushes confidence further from [0.35, 0.65]; tier-2 is also explicitly skipped when `state.chunked` (`adjudicate.py:203-204`), a second dead path.

- [MED] The review plurality (106/198 = 53.5% suggested `review`; 74 pass, 18 fail) is largely inherited from whisker candidate selection, not miscalibrated demotion. Evidence: reproduced verdict counts; whisker `review` -> tapetum `review` = 94/106 review outcomes; tapetum downgrades whisker `review` to `pass` in 71 cases vs upgrades to stricter in 21. Impact: the lane is not systematically over-reviewing relative to whisker; the calibration defect is under-escalation and overconfidence on failures, not excess review noise.

- [MED] Constants explicitly mark the band as provisional and unfitted (`constants.py:16-21`: "provisional and must be refit on the labeled review set"), mirroring whisker's pre-calibration posture for `UNIGRAM_COVERAGE` edges. Evidence: `constants.py:16-21`, `52-54`; no tapetum mini-eval artifact in repo. Impact: the thresholds are literature placeholders, not operating points; adopting them without a labeled holdout was predictable failure (0% band occupancy vs the >=20% ambiguous mass target in `research/deepseek-v4-pro/SYNTHESIS.md:43`).

- [LOW] Unit tests prove the gate wiring works in isolation but cannot catch production miscalibration. Evidence: `test_tapetum_llm.py:276-303` (`test_ambiguous_tier1_escalates` uses injected confidence=0.50); 0/198 production escalations. Impact: test suite gives false assurance that the cascade is live; a calibration regression test on sidecar histograms would have caught this.

## False-pass hypothesis

A token-preserving table cell swap or math exponent drop that leaves `unigram_coverage` high: the model returns `suggested_verdict=pass` with `confidence=0.95` (the modal bucket, 132/198 at 0.95 rounded), no axis marked `fail`, and empty or generic evidence spans that fuzzy-ground at `EVIDENCE_FUZZY_FLOOR=0.90` (`constants.py:50`, `grounding.py:24-56`). With 0 escalations and no sub-floor demotion, this is a single-tier confident pass with no second look.

## False-fail hypothesis

A `heading_monotone`-only whisker fail (RESCUE population) where the model marks structure axis `fail`/non-`major`, forcing overall `review` via severity fold (`constants.py:35`, `adjudicate.py:229-230`), yet reports `confidence=0.95` alongside other axes at `pass` — 18 whisker `review` -> tapetum `fail` cases exist, all at confidence >= 0.95. A human might ship after inspecting the cosmetic heading jump; the lane flags `fail` with false certainty, wasting review attention without triggering escalation.

## What would change my mind

A labeled tapetum mini-eval (>=50 WG21 papers, human-verified fidelity labels) showing that a refit band or derived escalation signal (axis disagreement OR ungrounded-drop OR retry count) achieves: (1) >=15% of genuinely ambiguous cases routed to tier-2, (2) tier-2 on a *different* model slot reduces false-clear rate on pass-channel labels by >=30% vs tier-1 alone, and (3) post-decide confidence correlates with human agreement (Spearman rho >= 0.4). Until then, keep the lane advisory but treat the cascade as documentation debt.
