# Hybrid Deterministic + LLM Scoring - Research Synthesis

**Verdict band:** usable-with-conditions   **Confidence:** high
**Decision vs our codebase:** adopt-partially (build a small fusion layer inside `tapetum_llm`; adopt patterns from grobid/docling/olmocr; reject weighted numeric composites)

Date: 2026-07-07. Swarm: 25 Composer-2.5 personas (01-25) + Opus baseline (00). All reports in `research/hybrid-llm-scoring/`.

## Summary

- **Nobody averages.** Across all 29 surveyed repos, not one fuses a deterministic score and a model score into a numeric composite. The dominant production pattern is **asymmetric: deterministic primary, model as selective second opinion with recorded provenance** (grobid consolidation `status`/`source` fields, 10; marker selective `--use_llm` processors with deterministic fallback, 02; opendataloader hybrid routing, 03; olmocr deterministic unit checks judged per-rule, 01). Long-tail sweep (12): per-document hybrid QA like ours is rare; most converters have NO self-scoring at all.
- **LLM confidence is anti-calibrated and must not weight anything** (14): observed on our 204 tapetum sidecars: min 0.90, median 0.95, 196/204 >= 0.95; fails carry the same confidence as passes (all 10 fails at exactly 0.95). Web prior art (24) confirms verbalized-confidence miscalibration is the norm. Fusion must be **ordinal (verdict tiers)**, not scalar, until a labeled calibration exists (protocol drafted in 14 using existing `calibrate.py` machinery).
- **The fusion rule that survives both hunters** (19 false-pass, 20 false-fail) is an **asymmetric escalation/rescue matrix**, not worst-of and not persona-13's unconditional fail-lock:
  - Hard-gate fails stay `fail` EXCEPT the heading-monotone-only RESCUE carve-out -> `review` (9 of 15 fails are this class; the LLM lane was built to catch exactly this, `adjudicate.py` RESCUE population).
  - Soft-only det reviews + LLM pass (grounded, conf >= floor) -> merged `pass_advisory` (this clears 101 of 232 reviews = 44% queue shrink, the LLM lane's proven value; guardrail: exclude pathological `ref_nid < 0.10` upgrades).
  - Det pass + LLM fail(major) -> `review` (never auto-fail; C1).
  - LLM absent/errored/stub(conf==0.0) -> merged = det verdict, `combined_rule: whisker_only` (explicit lane-coverage status; C5).
  - Merge consumes `axis_findings` + severity, NEVER the folded verdict string alone (chunk-fold bypass, 20-HIGH; llm-stack/11 prior finding).
  - No flag arithmetic across lanes (N5035's one heading jump surfaces 3x across lanes; additive merges double-count, 20-MED).
- **Placement is settled by C2** (23, 13, 16): `tapetum_llm/fusion.py` (pure function: two sidecar dicts in, FusionResult out) + `tapetum_llm/fusion_report.py` (rendering). Core `whisker/report.py`, `score.py`, `__main__.py` stay untouched. JSON-on-disk is the sanctioned cross-lane interface (established by `inspect_report.py`); core never imports tapetum.
- **CI contract stays sealed** (18): the single gate choke point is `_verdict_exit_code` in `__main__.py:275`. Merged verdict lives only in namespaced advisory fields (`combined_verdict`, `advisory: true`), the fusion CLI exits 0 always, `--gate-merged` on the whisker CLI is rejected outright per CLAUDE.md ("never in the whisker --gate CI contract").
- **Determinism** (17): the merge itself is a pure function (unit-testable); the LLM lane's variance (118 retries/194 papers is the top source) is contained by recording provenance in the merged record: which tapetum result was joined (model names, confidence, and a fingerprint/hash of the joined whisker payload for staleness detection; neither sidecar records `md_hash` today - add it).
- **Injection resistance** (22): a deterministic verdict floor (det-primary fusion) denies paper-embedded "this conversion is perfect" text any score power. Biggest blind spot is NOT fusion math but SELECTION: token-preserving permutation corruption never reaches tapetum (`select_candidates` gap) and merges as `whisker_only` pass - a pre-existing gap, documented, not widened by fusion.

## Persistence decision (user goal 2: "same file")

Evidence is against writing into `<pid>.whisker.json`: `whisker --all` full-overwrites each sidecar with no read-merge (`__main__.py:246-248`), so a nested LLM block dies on the next det run unless core gains preserve-unknown-keys logic (15-CRITICAL). Three viable options, ranked:

- **A (recommended): fusion block inside `<pid>.whisker.tapetum.json`** + run-level `report-merged.md`/`report-merged.json`. The tapetum CLI already owns that file exclusively (no write conflict), it already embeds `whisker_verdict` (the join key), zero core changes, zero new per-paper files. "Weiterbearbeitet im gleichen File" from the LLM lane's side.
- **B: nested block in `<pid>.whisker.json`** (the literal user wish): requires a small core change (preserve extension keys on rewrite, ~5 lines, no tapetum import so C2 holds) + fingerprint staleness. Write-ownership and concurrency caveats (15).
- **C: third file `<pid>.fusion.json`**: cleanest isolation, but 3 files/paper and three-way staleness (15, steelman 25 both advise against).

## Top findings (ranked)

- [CRITICAL][NOW] Worst-of fusion destroys tapetum's entire rescue value (merged review count 235/381, worse than either lane). Evidence: 20, cross-tab of all 204 sidecars. adopt? yes (rules out worst-of).
- [CRITICAL][NOW] Confidence-weighted fusion is statistically indefensible today (anti-calibrated, 14) and false-pass prone (19: P3844R4 shipped at conf 0.95 despite coverage 0.507). adopt? yes (rules out weighting; ordinal only).
- [HIGH][NOW] Asymmetric matrix with RESCUE carve-out + gated upgrade clears ~44% of the review queue while keeping every non-cosmetic hard fail locked. Evidence: 20 (101 review/pass pairs, 9 heading-only fails), 13 (matrix skeleton), 19 (det-floor guardrails). adopt? yes, with 20's two amendments to 13's matrix.
- [HIGH][NOW] Fusion must branch on `tapetum_available` and treat `confidence == 0.0` stubs as unavailable (`adjudicate.py:490-501`; 4 of the 6 errored papers now hold valid rerun sidecars, 20/21). adopt? yes.
- [HIGH][NOW] Provenance fields in the merged record: joined verdicts, model names, `whisker_fingerprint` (hash of det payload), tapetum sub-schema version (15, 17). adopt? yes.
- [MED][LATER] Calibration protocol for confidence (labels file + `calibrate_threshold` reuse; 14) - prerequisite for ever weighting confidence. adopt? later.
- [MED][LATER] Det-side benign-region fold could clear 44 never-adjudicated region-only reviews with no LLM at all (20-MED). adopt? separate task, do not bundle.
- [MED][NO] grobid-style external-source consolidation and docling grade aggregation are informative but need no code adoption now (10, 05).

## Bugs / edge-cases in OUR code (surfaced by the comparison)

- `chunking.py:311-316` `_worst_part_verdict` promotes part-level `fail` with empty `axis_findings` to overall fail, bypassing the severity fold (20; extends llm-stack/11). Fix direction: apply the same major-severity fold on the empty-findings path.
- Pipeline-failure stub (`adjudicate.py:490-501`) emits `suggested_verdict=review, confidence=0.0` that is indistinguishable from a real review in the sidecar. Fix direction: explicit `status: "error"` field (also needed by fusion).
- Neither sidecar records the markdown content hash -> stale joins are undetectable (17, 15). Fix direction: add `md_hash`/`whisker_fingerprint` at write time in the tapetum lane.
- Selection gap: permutation corruption on pass-tier papers without risk signals never reaches tapetum (22). Documented blind spot; candidate-selection widening is a separate future task.

## Top portable detail

grobid's consolidation provenance (10): every model-vs-second-opinion merge records `status` + `source` per decision. Ported: every `FusionResult` carries `combined_rule` (e.g. `whisker_only`, `llm_rescue_heading`, `llm_clear_soft_review`, `llm_escalate_major`) so an operator can always answer "why is merged X?" without replaying either lane.

## Flip conditions

- A blind human-labeled holdout showing < ~85% of the 101 review/pass papers are truly shippable would kill the gated upgrade and revert to persona 13's no-upgrade matrix.
- A labeled calibration showing monotonic confidence separation (ROC AUC >= 0.75, 14) would unlock confidence as a tiebreak (never as a weight before that).

---
Sources: 29 repos at packages/whisker/research/repos/ (read in place), our sidecars at data/whisker/ (381 det + 204 tapetum), baseline 00-baseline.md, 2026-07-07.
Web: 24-web-prior-art.md (~20 finding cards).
Personas: 25. Meta-review: folded into this synthesis (parent agent); hunters 19/20 cross-checked against 13/15/16 in text above.
