# 14 - Confidence Calibration

**Verdict:** usable-with-conditions — the `Adjudication.confidence` field is schema-valid, persisted, and useful for audit/demotion, but its observed distribution is anti-calibrated (clustered 0.90–1.00, zero separation across pass/review/fail), so it must not enter a numeric merge weight until a labeled fit exists.
**Confidence:** high

## Findings

- [CRITICAL] Self-reported confidence is anti-calibrated in production and the codebase already documents it. Evidence: `adjudicate.py:216-217` ("18/18 fails at >= 0.95, band never hit in 198 runs"); sidecar sweep `n=204`: min 0.90, median 0.95, mean 0.9617, 196/204 in `>=0.95`, 0/204 in `[0.35, 0.65]` (`constants.py:27-28`). Impact: confidence-weighted fusion would overweight wrong disagreements (123/204 sidecars differ from whisker at *higher* mean confidence 0.970 vs 0.949 when agreeing).

- [CRITICAL] Fail verdicts carry the same confidence band as passes, so scalar weight cannot rank severity. Evidence: sidecar distribution — fail `n=10` mean 0.9500 min/max 0.9500; pass `n=105` mean 0.9733; review `n=89` mean 0.9492; all 10/10 fails at `>=0.95`. Baseline example `p4003r0.whisker.tapetum.json`: whisker `review` → tapetum `fail`, confidence 0.95, escalated on `axis_conflict` not confidence. Impact: a merged numeric score treating confidence as LLM lane weight would assign near-max weight to hard fails and soft passes alike (goal 3).

- [HIGH] The ambiguous-confidence escalation band is a dead gate; escalation now rides derived signals, not the scalar. Evidence: `constants.py:23-26` ("0/198 escalations; … never left [0.85, 1.00]"); sidecars `0/204` with `confidence_ambiguous`, `14/204` escalated (mostly `axis_conflict` / `ungrounded_evidence` per samples). Impact: any merge design that assumes tier-1/tier-2 confidence separation for quality tiers is unsupported today; ordinal merge on `suggested_verdict` + signal flags is the honest path (goals 1–3, C1).

- [HIGH] Confidence only affects output through a demotion floor, and that floor never fires on current sidecars. Evidence: `adjudicate.py:284-285` demotes to `review` when `confidence < CONFIDENCE_DECISION_FLOOR` (0.50, `constants.py:45`); sidecars `0/204` below 0.50. `models.py:77` explicitly: "The lane never turns low confidence into a pass/fail." Impact: confidence is not a continuous quality axis in the pipeline today — only a binary "keep human" guard that never triggers — so weighting it in fusion duplicates noise (goal 3).

- [MED] Chunk aggregation takes `min(confidence)` across chunks, compressing any rare low values further upward. Evidence: `chunking.py:233-234`, `chunking.py:259`. Impact: oversized papers (6+ per baseline) get the most conservative verdict fold but not a calibrated uncertainty scalar; merge weights would be even less informative for the long-doc tail.

- [MED] Existing `calibrate.py` + `whisker calibrate` fit *lower-is-worse* thresholds on labeled coverage, not LLM confidence — the right machinery, wrong target today. Evidence: `calibrate.py:16-21`, `calibrate.py:150-160`; `__main__.py:803-846` loads `{pid,label}` and fits `unigram_coverage_*` edges with `DEFAULT_TARGET_FPR=0.05` (`calibrate.py:44`). Synthesis already maps the reuse: `tapetum-llm-decision-synthesis.md:137-138` ("invert comparator: escalate iff confidence *inside* band"). Impact: smallest calibration path is a second labels join + artifact, not new math (goal 3, C4).

- [LOW] Sidecar count (204) exceeds the 2026-07-06 adjudicated run (194, `00-baseline.md:49`) but confirms the same clustering pattern; 6 tapetum errors still leave absent LLM lane (`00-baseline.md:51`). Impact: merge must treat missing/errored tapetum as its own ordinal state, not confidence 0.0 weight (C5).

## False-pass hypothesis

Whisker `pass` with hidden table risk never reaches tapetum (`adjudicate.py:86-88`, `_has_pass_risk_signals`). If we merged with confidence weight anyway, a hypothetical tapetum `pass` at 0.98 would dominate a deterministic pass despite the lane not having seen the paper — baseline notes 134/381 deterministic passes with selective LLM coverage (`00-baseline.md:48-49`). Ordinal merge must not upgrade whisker pass on unseen LLM pass.

## False-fail hypothesis

`p4003r0.whisker.tapetum.json`: whisker `review`, tapetum `fail`, confidence 0.95. A confidence-weighted merge could pull a soft review toward fail even when the fail is severity-folded from axis conflict (`adjudicate.py:274-275`, `chunking.py:34-51`) — the scalar says "very sure" while the fold logic says "major fail." Weighting confidence would amplify tier disagreements without human-label validation.

## What would change my mind

A labeled holdout (15–30 papers, human verdict vs source PDF/HTML per `tapetum-llm-decision-synthesis.md:126-133`) where `(confidence, suggested_verdict)` yields monotonic separation: e.g. ROC AUC ≥ 0.75 for predicting human agreement *and* calibrated bins (reliability diagram slope ≈ 1) after a `calibrate.py`-style fit — either a promoted `CONFIDENCE_DECISION_FLOOR`/escalation band from `_confusion` on `(1 - confidence)` or an isotonic map persisted beside `thresholds.json`. Until that artifact exists, merge stays ordinal: map `pass/review/fail` to tiers, apply conservative fusion rules (never upgrade whisker fail/pass without LLM + human policy), show lanes separately (goals 2–3, C1).

### Smallest calibration protocol (reuse `calibrate.py` patterns)

1. **Labels file** — same shape as `whisker calibrate --labels` (`__main__.py:809-810`): `{pid, label}` with `label ∈ {pass, review, fail}` against source.
2. **Join** — for each labeled PID with `<pid>.whisker.tapetum.json`, emit samples:
   - **Escalation fit:** `(confidence, needs_deep)` where `needs_deep = 1` iff human disagrees with tier-1-only outcome or human is fail while tier-1 pass; sweep *inside-band* thresholds via inverted `_confusion` (synthesis §2d).
   - **Demotion floor:** `(confidence, tapetum_correct)` where `tapetum_correct = (suggested_verdict == human)`; use `calibrate_threshold` on `(1 - confidence, not tapetum_correct)` to pick a floor that demotes wrong high-confidence calls at FPR ≤ 0.05.
   - **Merge gate (optional third fit):** only emit a numeric LLM weight if post-fit bin-wise accuracy spans ≥ 15 pp across `[0.5,0.65,0.8,0.95]`; otherwise artifact flags `merge_mode: ordinal`.
3. **Artifact** — mirror `__main__.py:865-878` payload (`kind: tapetum-calibration`, `fitted`, `current` constants); human promotes into `constants.py` (C4). No code change required for this research tranche.
