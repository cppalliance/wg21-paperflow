# 17 - Confidence-Calibration-Statistician

**Verdict:** usable-with-conditions — neither our tapetum self-reported confidence nor reference-repo signal scores are calibrated probabilities; the advisory architecture is sound only because fusion already treats confidence as a binary permission bit paired with ordinal verdicts, not a numeric weight.
**Confidence:** high

## Findings

- [CRITICAL] Tapetum confidence is LLM self-report with no post-hoc calibration. Evidence: `models.py:93` (`confidence: float = Field(ge=0.0, le=1.0)` on `Adjudication`), `tapetum_llm.md:148` ("your calibrated certainty" — aspirational, no fit step). Production distribution is anti-calibrated: min 0.90, median 0.95, 18/18 fails at >= 0.95, 0/198 in `[0.35, 0.65]` (`constants.py:23-26`, `adjudicate.py:233-234`, `tapetum-golden-review-findings-2026-07-14.md:86-89`). Impact: the scalar is not a probability of correctness; treating it as one (merge weights, tier routing, "high confidence" UX) will overweight wrong calls.

- [CRITICAL] PR #282 is the canonical false-clear at maximum confidence. Evidence: `00-baseline.md:82` (heading-level blind spot, "PR #282 pass/1.00 vs human request-changes"); `golden-qa-gap/00-baseline.md:63` (LLM claimed outline match when ideal had `### References` vs source `h2: References` despite `html_outline.py` injection). Impact: any use that treats confidence >= 0.50 or >= 0.85 as "safe to trust" is unsafe; the wrong verdict carried the top of the observed range.

- [HIGH] `CONFIDENCE_DECISION_FLOOR` demotion never fires in production; the floor is inert, not conservative. Evidence: `adjudicate.py:311-312` (demote when `confidence < CONFIDENCE_DECISION_FLOOR`), `constants.py:45` (`CONFIDENCE_DECISION_FLOOR = 0.50`); `pdf_judge.py:525-526` (same floor on PDF lane); sidecar sweep 0/204 below 0.50 (`research/hybrid-llm-scoring/14-confidence-calibration.md:14`). Impact: the only decide-step confidence guard is a no-op today; demotion rides grounding and severity folds, not the scalar.

- [HIGH] Fusion `llm_clear_soft_review` gates on `conf >= CONFIDENCE_DECISION_FLOOR` — structurally unsafe with anti-calibrated scores. Evidence: `fusion.py:196-207`, `fusion.py:214-225` (clear requires `llm == pass` and `conf >= CONFIDENCE_DECISION_FLOOR`); `test_fusion.py:167` (blocks clear at `CONFIDENCE_DECISION_FLOOR - 0.01`). Because every production sidecar sits >= 0.85 (`constants.py:24-25`), the floor is a tautology: any LLM `pass` on soft-review whisker clears regardless of whether the pass is wrong (PR #282-class). Impact: the clear rule is effectively "LLM said pass" with a decorative confidence check; only `FUSION_REF_NID_FLOOR` and missing-region blocks add real guardrails (`fusion.py:127`, `fusion.py:177-190`).

- [HIGH] The cascade confidence band is a dead gate; escalation correctly moved to derived signals. Evidence: `adjudicate.py:250-251` (`SIGNAL_CONFIDENCE_AMBIGUOUS` when confidence in `[CONFIDENCE_AMBIGUOUS_LO, CONFIDENCE_AMBIGUOUS_HI]`); `constants.py:27-28` (band 0.35–0.65); 0/198 scalar-band escalations, 0/204 `confidence_ambiguous` in sidecars (`14-confidence-calibration.md:12`). Derived triggers (`SIGNAL_AXIS_CONFLICT`, `SIGNAL_UNGROUNDED_EVIDENCE`, `adjudicate.py:241-248`) are the honest uncertainty path. Impact: keeping the band as a "calibrated uncertainty" story is misleading; refitting the band without new labels cannot help.

- [MED] Reference repos do not deliver calibrated confidence either; they avoid the failure mode by not gating on it. Docling: scores aggregate deterministic pipeline signals (OCR cell confidences, layout scores), explicitly not LLM judge (`05-web.md / Q5 / docling #1102 - confidence from deterministic pipeline signals`; `00-baseline.md:29` `ConfidenceReport`); docs tell users to trust categorical grades, not numerics (`packages/whisker/research/repos/docling/docs/concepts/confidence_scores.md:11-13`, `05-web.md / Q5 / Docling confidence scores - grades decide, numerics advisory`). Docling still uses hand-set grade bands, not ROC/ECE (`research/redteam/docling.md:135-141`). Surya: `mean_token_prob` / block `confidence` is telemetry (`00-baseline.md:30`); mechanical reroute on repeat/blank/parse-error, confidence never gates accept (`00-baseline.md:30`; `research/redteam/surya.md:54-60`). Impact: signal-derived confidence is **strictly better than self-report for gating** (monotonic link to measurable inputs, no LLM overconfidence per `05-web.md / Q2 / Overconfidence in LLM-as-a-Judge`), but it is **not automatically calibrated** — Docling admits numerics are unstable across releases (`05-web.md / Q5`).

- [MED] We already have one honestly calibrated confidence: VLM diff uses `min(nid, recall)` (`vlm_diff.py:183-189`), a deterministic lower-is-worse scalar with defined semantics. That is signal-derived and auditable, but still unfitted (thresholds `MHS_REVIEW_THRESHOLD` etc. are named constants, not ECE-validated). Impact: the pattern to copy internally is signal composition + ordinal verdict, not LLM self-report.

- [LOW] Chunk aggregation `min(confidence)` (`chunking.py:259`) further compresses any rare low values on oversized papers (~6 corpus members, `constants.py:59-60`). Impact: even a future calibration map would under-express uncertainty on chunked papers unless fit per-chunk then aggregate with worst-case rule (Docling `low_grade` 5th-percentile pattern, `research/redteam/docling.md:147-149`).

## False-pass hypothesis

PR #282 replay: whisker det `pass`, tapetum `suggested_verdict=pass`, `confidence=1.00` (`00-baseline.md:82`, `golden-qa-gap/00-baseline.md:63`). Fusion `llm_clear_soft_review` does not apply (det already pass), but inspect/fusion footer displays confidence 1.00 as if it were calibrated certainty (`inspect_report.py:57-67`). A human trusting "pass at 1.00" ships a heading-level defect the deterministic lane cannot see.

## False-fail hypothesis

PR #295: LLM `review` at 0.95 for an H2→H3 jump that matches the source HTML (`golden-qa-gap/00-baseline.md:65`). High confidence here means "confidently wrong direction" — demotion floor and fusion floor do not rescue (verdict is already `review`, not pass). A confidence-weighted merge would pull toward review/fail without adding signal.

## What would change my mind

A promoted calibration artifact from a labeled holdout where post-fit bins show reliability slope ≈ 1 and TH-Score/ECE beat an ordinal-only baseline (`05-web.md / Q2 / Overconfidence in LLM-as-a-Judge` TH-Score + ECE methodology), with fusion clear-rule precision >= 0.90 at the fitted floor on a **held-out** slice not used for threshold picking.

### Concrete calibration study (honest scope)

**Labels (minimum viable):**
1. **Seed set:** 9 PR human-review verdicts (`00-baseline.md:61-63`, `golden-qa-gap/00-baseline.md:23-68`) — `{pid, label}` with `label ∈ {pass, review, fail}` against source PDF/HTML. Use for case audit and directional checks only.
2. **Fit set:** 30–50 additional labeled papers (`whisker/CLAUDE.md:414-418`; `14-confidence-calibration.md:36`) stratified by miss-class (MC1–MC5 in `golden-qa-gap/00-baseline.md`) and source kind (PDF/HTML). Required before any constant promotion.

**Join:** For each labeled PID, join `<pid>.whisker.tapetum.json` fields `(confidence, suggested_verdict, escalated, escalation_signals, axis_findings)` and human label. Reuse `calibrate.py:150-195` machinery (`__main__.py:1099-1102` labels loader).

**Metrics (per `05-web.md / Q2`):**
- **ECE** on binned predicted confidence vs empirical accuracy (human agreement with tapetum verdict, and separately human "conversion acceptable").
- **TH-Score** (or reliability-diagram slope) comparing pre- and post-calibration maps.
- **ROC/operating points** for escalation (`needs_deep` = human disagrees with tier-1) and demotion (`tapetum_wrong` = `suggested_verdict != human`) via inverted `_confusion` on `(1 - confidence)` (`14-confidence-calibration.md:37-40`).

**Sample-size verdict:** **n = 9 is insufficient** for ECE/TH-Score promotion. Rule of thumb: stable ECE needs hundreds of labeled decisions per score bin; with 10 bins and ~30 samples/bin, plan on **300+ paper-level labels** for a publishable calibration, or **≥30–50 papers minimum** for a provisional `constants.py` fit with wide confidence intervals and `merge_mode: ordinal` default (`14-confidence-calibration.md:40-41`). The 9 PR reviews are high-value anchors (especially the 1.00 false-clear) but can only falsify "already calibrated," not establish calibration.

**Promotion gate:** Emit `kind: tapetum-calibration` artifact (`14-confidence-calibration.md:41`) only if post-fit bin accuracy spans ≥ 15 pp across `[0.5, 0.65, 0.8, 0.95]` on holdout; otherwise keep `CONFIDENCE_DECISION_FLOOR` and cascade band as documented dead constants and retain derived-signal escalation only.

**Unsafe uses to disable until fit:** numeric merge weights; any CI/accept gate on self-reported confidence; user-facing "calibrated" wording in prompts (`tapetum_llm.md:148`). **Safe uses today:** sidecar audit field, ordinal fusion paired with `axis_findings` severity and grounding (`fusion.py:231` major-axis check), derived escalation signals (`adjudicate.py:230-253`).
