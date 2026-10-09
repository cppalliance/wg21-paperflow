# Opus-B Meta-Review: Calibration / LLM-Judge / CI-Reproducibility Cluster

**Cluster:** 12-steelman-llm-first.md, 17-calibration-statistician.md, 20-llm-judge-scholar.md,
23-ci-reproducibility.md
**Method:** re-verified every CRITICAL/HIGH claim against live code
(`fusion.py`, `adjudicate.py`, `constants.py`), the live marker clone
(`packages/whisker/research/repos/marker-v1.10.2/`, read with exact paths per the
00-baseline gitignore caveat), the actual `research/llm-batching/20-sweep-results.md`
and `research/hybrid-llm-scoring/14-confidence-calibration.md` artifacts, and
**381 real production sidecars** at `data/whisker/llm/*.whisker.tapetum.json`
(the WG21 data dir is accessible at `data/` in this workspace — better evidence
than the personas had, since I could recompute the confidence/fusion-rule
distributions directly instead of trusting a cited number).

## Verdict on cluster

**usable-with-conditions.** All four persona verdicts hold up. The det-decides
architecture is confirmed correct by every layer of evidence re-checked here:
code (fusion never lets LLM hard-fail or override det-fail), a code comment
admitting the confidence band is dead, an actual determinism-budget doc
(MODELS.md) explaining *why* it's dead (MoE routing, non-batch-invariant
kernels), a real concurrency sweep showing a **measurable histogram-level
verdict shift between two identical reruns**, and — new evidence this
meta-review adds — **live confirmation from 381 real sidecars that
`llm_clear_soft_review` has fired 96 times and 100% of those firings sit at
confidence >= 0.95** (min 0.95, max 1.0, mean 0.983), i.e. the "decorative
confidence check" claim in P17 is not just plausible from a 204-sample sweep
cited secondhand, it is exactly true on the full current corpus. P12's
steelman is intellectually honest and its concrete proposal is well-guardrailed,
but P23's evidence, re-verified directly against the cited artifact rather than
taken on faith, is strong enough that the proposal cannot bind to `whisker
--gate`'s exit code without first either (a) accepting that "review" becomes a
flaky, rerun-dependent CI signal, which breaks the reproducibility contract the
architecture exists to protect, or (b) paying for server-side batch-invariant
inference and re-measuring. Below "The steelman adjudicated" states exactly why.

## Findings table

| # | Claim | Status | Evidence |
|---|---|---|---|
| 1 | P17 CRITICAL: `CONFIDENCE_DECISION_FLOOR` (0.50) demotion never fires in production | **CONFIRMED, stronger than cited** | Live: 0/381 sidecars below 0.50 (min observed 0.85 across corpus, min 0.95 among fails); code `adjudicate.py:311-312` gates on it correctly but the input never crosses it. |
| 2 | P17 CRITICAL: `llm_clear_soft_review` is structurally "LLM said pass" with a decorative confidence check | **CONFIRMED, stronger than cited** | Live: 96/381 sidecars fired this rule; **all 96** have `confidence` in `[0.95, 1.0]`, mean 0.983 — the `conf >= CONFIDENCE_DECISION_FLOOR` (0.50) guard in `fusion.py:196` never came within 0.45 of binding on a real paper. |
| 3 | P17 HIGH: cascade confidence band `[0.35, 0.65]` is a dead gate (0/198 in earlier sweep) | **CONFIRMED** | Live: 0/381 sidecars in `[0.35, 0.65]`. Code comment `constants.py:23-26` and `adjudicate.py:233-234` state the same for n=198/n=204 historically; the pattern holds at n=381. |
| 4 | P17: production confidence distribution min 0.90, 18/18 fails >= 0.95 (from `research/hybrid-llm-scoring/14-confidence-calibration.md`) | **CONFIRMED (file exists, content matches verbatim)** — minor drift on live n=381: min is now 0.85, fails now 9/9 (not 18/18) all in `[0.95, 1.0]` | `14-confidence-calibration.md` reads exactly as cited (n=204: min 0.90, median 0.95, mean 0.9617). Corpus has grown/re-run since; direction and conclusion (anti-calibrated, fails and passes share the top confidence band) are unchanged. |
| 5 | P17 CRITICAL: PR #282 false-clear at confidence 1.00 despite injected HTML outline | **CONFIRMED verbatim** | `research/golden-qa-gap/00-baseline.md:63` (MC5): "despite having the explicit HTML heading outline injected into the prompt (`html_outline.py`)." Independently corroborated by `packages/whisker/research/tapetum-golden-review-findings-2026-07-14.md` F3 (same defect, deeper root-cause trace, dated one day earlier — F3 was written *before* the outline-injection fix landed and proposed it as the fix; MC5's PR #282 replay shows the fix landed and the LLM *still* missed it). This is the single most damaging fact in the whole cluster for any "give the LLM the outline and trust it" proposal. |
| 6 | P23 HIGH: 25% per-PID verdict flip on a 20-PID rerun (c=32 vs c=32) | **CONFIRMED at the histogram level; "25%" is the minimum, not a verified per-PID list** | `packages/whisker/research/llm-batching/20-sweep-results.md:31-40` (verbatim, file exists at the exact cited path): run 3 vs run 4, identical concurrency and PIDs, "15 pass / 5 review vs 10 pass / 10 review." Fail count is absent from both runs (implying constant), so the pass↔review shift of 5/20 is a **lower bound** on flips (cancelling flips in both directions would only make the true rate higher, never lower). The doc's *named* per-PID flip examples (N5034, P4023R0, P3842R1) are from a *different* comparison (c=8 vs the c=3 baseline), not from the run-3-vs-4 pair P23 cites for the 25% figure — P23's arithmetic is sound but the source doc does not itself enumerate which 5 PIDs flipped in that specific pair. Downgrade P23's confidence tag on this one line from "measured" to "measured lower bound," conclusion unaffected. |
| 7 | P23 CRITICAL: an LLM verdict cannot be a CI-hard gate on this stack today (MoE/batch non-invariance, D5/D11, CLAUDE.md quality-stability language) | **CONFIRMED** | `MODELS.md:77` (verbatim: "vLLM/SGLang-class servers flip tokens because matmul/attention/RMSNorm kernels are not batch-invariant... Server-side fixes exist (vLLM `VLLM_BATCH_INVARIANT_LEVEL`)... Fireworks does not currently expose them"); `tapetum_llm.md:29` (verbatim: "token-level output on a hosted vLLM pod is not bit-stable under continuous batching and MoE expert routing... D11 binds dissect, not this lane"); `tests/test_tapetum_llm_eval.py:12` (verbatim: "NOT a CI gate: the LLM is non-deterministic and results vary across runs"). All three independently corroborate. |
| 8 | P20: marker `LLMScorer` renders page 0 to PIL, sends `[img, prompt-with-markdown]`, element-conditional 0=N/A sub-scores, describe-then-score field order (`llm.py:15-51,87-134`) | **CONFIRMED** | Read live at `packages/whisker/research/repos/marker-v1.10.2/benchmarks/overall/scorers/llm.py`. `doc[0].render(...)` confirms page-0-only (line 102); `score_keys` includes tables/forms/equations/section_headers/lists/images (line 90); "Use 0/5 if a field isn't applicable" (line 50); example JSON at lines 64-78 places `image_description`/`markdown_description`/`comparison` before the integer scores, matching the describe-then-score claim. |
| 9 | P20: marker Elo `Comparer` fixes version A before B in-prompt; `random.shuffle` only permutes which converters pair, not intra-judgment position (`elo.py:32-40,116-131,194-195`) | **CONFIRMED** | Read live at `.../elo.py`. Prompt template (lines 20-91) always presents "Version A" then "Version B." `random.shuffle(method_lst)` at line 195 only reorders `method_lst`, the list of converter *names*; the call `comparer(row["img"], method_a_md, method_b_md)` (line 204) always passes `method_a`'s markdown as `version_a`. No position-swap-within-a-judgment exists. Confirms P20's finding that porting Elo as-is would import the exact position-bias defect Q2's web findings warn about. |
| 10 | P12 CRITICAL: deterministic gates are order-invariant (`unigram_coverage`) and blind to row/cell swaps; the authority doc explicitly assigns this class to the LLM axis | **CONFIRMED verbatim** | `tapetum_llm.md:84`: "Row or cell swap — content present but in the wrong position. The deterministic token gate is blind to this; you are the catch." |
| 11 | P12 HIGH: the selection gap — `--review-all` never reaches clean-pass token-preserving corruption, mitigated only by running the full corpus | **CONFIRMED, and materially mitigated in current practice** | `whisker/CLAUDE.md` (candidate filter section, verbatim): "Known limit: the filter never reaches clean-pass papers with token-preserving corruption (the documented 'selection gap'), which is why the full run is the default." Live evidence: 381/381 papers in the data dir *do* have tapetum sidecars, i.e. the full-corpus default is actually being exercised in this environment, not just documented as an intention. |
| 12 | P12's own guardrail table (grounding required, major-severity-only, never sole hard-fail, position-swap if pairwise added, grader-disagreement reporting) | **CONFIRMED as internally consistent with D-invariants** | Cross-checked against `fusion.py` (never fail-locks from LLM, `whisker_fail_locked`/`llm_rescue_heading` paths), `models.py`/D6 (schema-locked output), D5/D11 (temp/seed pinned, serial per-paper). No contradiction found. |
| 13 | F1 finding (missing_region false-pass-upgrade bug) is still open | **REFUTED — already fixed in current code, ahead of the 2026-07-14 finding doc** | `tapetum-golden-review-findings-2026-07-14.md` F1 describes `llm_clear_soft_review` upgrading a `missing_region` review to pass because fusion "does not consult `missing_region_count`." Current `fusion.py:172-190` (`FUSION_RULE_CLEAR_BLOCKED_MISSING_REGION`) explicitly blocks exactly this case, and P17 already cites the current guardrail correctly (`fusion.py:177-190`). Not a persona error — P17 is up to date; flagging here only so a reader of the older findings doc doesn't think the bug is live. |

## The steelman adjudicated (P12 vs P23/P17 evidence)

P12's concrete proposal: bind `FUSION_RULE_LLM_ESCALATE_MAJOR` (det=pass + LLM
grounded major-axis fail) and PDF per-page confirmed-missing to the CI exit
code as a hard `review` (exit 3), never `fail`.

**Why the proposal is well-formed on its own terms.** It targets exactly the
defect class the deterministic gate structurally cannot see (`tapetum_llm.md:84`,
finding #10), it reuses an already-implemented, already-tested primitive
(`fusion.py:228-240`, `test_fusion.py:172-188`), it never lets the LLM produce a
false *fail* (only det can fail; LLM can only add a review), and its guardrail
list (grounding, major-severity-only, position-swap-if-pairwise,
grader-disagreement reporting) is consistent with every D-invariant checked
(finding #12).

**Why P23's evidence still defeats binding it to the exit code today, not to
authority in general.** `FUSION_RULE_LLM_ESCALATE_MAJOR` fires on
`axis_findings` (verdict=fail, severity=major). `suggested_verdict` is *derived*
from `axis_findings` via `worst_axis_verdict` (`adjudicate.py:291-294`), and the
only other thing that can change `suggested_verdict` post-hoc is the confidence
floor demotion — which finding #1 shows **never fires** (0/381). That means the
run-to-run drift in `suggested_verdict` documented by P23 (finding #6, the
pass/review histogram shift under identical inputs) is not explained by
confidence-floor noise; it has to come from the `axis_findings` themselves
changing between runs — the exact severity/verdict pair
`FUSION_RULE_LLM_ESCALATE_MAJOR` reads. There is no evidence in this cluster
that axis-level findings are *more* stable than the aggregate verdict they feed;
the mechanism (MoE batch non-invariance flipping argmax tokens mid-generation,
per `MODELS.md:77`) operates on the model's raw output before any aggregation,
so it should affect axis findings at least as much as the derived verdict.
**Consequence: binding `llm_escalate_major` to `--gate`'s exit code inherits the
same ~25%-of-borderline-papers flip risk P23 measured for the aggregate
verdict**, not a smaller one. A CI run that exits 3 (review) today and 0 (pass)
tomorrow on an unchanged commit is precisely the failure mode the entire
31-repo survey (`00-baseline.md` §2) shows the ecosystem unanimously avoids, and
it is a materially worse UX than the status quo (advisory field, human reads it
when they choose to).

This does **not** kill P12's proposal outright — it kills only the "bind to the
exit code now" version. P23's own "what would change my mind" (a controlled
rerun with `VLLM_BATCH_INVARIANT_LEVEL` showing <=1% flip) is the correct
falsifiable gate for exactly this question, and it has not been run. Until it
is, P12's primitive should be *surfaced*, not *gated*: exit code stays det-only;
the `llm_escalate_major` / per-page-confirmed-missing signal should appear as a
loud, separately-labeled line in `report.md`/`tapetum-inspect.md` so an operator
who runs `whisker-tapetum-llm` sees "det=pass but LLM found a grounded major
defect" without whisker's exit code becoming rerun-flaky. P12's own honest-costs
section already half-concedes this ("binding CI on LLM escalations introduces
flake risk the 31-repo survey explicitly avoided") — the adjudication here is
that this concession should be the entire policy, not a caveat next to a
CI-binding recommendation.

Separately, finding #5 (PR #282, outline injected, still false-cleared at
1.00) is evidence against a *different* possible upgrade path — giving the LLM
authority on heading-level defects even with source-outline assistance — and
P12 already carves this out correctly ("do not expand LLM authority there
without the diff pre-check"). That carve-out is confirmed necessary and
sufficient by the live doc trail; no further restriction is needed there.

**Is there a safe upgrade path at all?** Yes, narrower than P12's CI-binding
ask but real: (1) the `llm_escalate_major` / per-page-confirmed-missing signal
promoted to a *prominent advisory* (not exit-code) surface — zero determinism
risk, immediate value, uses existing code; (2) marker-style image-grounded
per-page judging (P20, finding #8) to close the heading/table-formatting blind
spot the text-only PDF judge has — improves advisory quality, does not touch
gating, moderate engineering cost since `vision.py`/`vision_task.py` groundwork
already exists; (3) exit-code binding of any tapetum signal is gated behind a
measured <=1% flip rate on a batch-invariant-enabled pod (P23's falsifier),
which is an infra project, not a code change.

## Recommended actions, ranked by cost

1. **(Near-zero cost, do now) Stop presenting confidence as calibrated.**
   `inspect_report.py` currently prints `confidence 1.00` next to a verdict as
   if it were a probability. Label it "self-reported, uncalibrated" or drop the
   decimal display in favor of the ordinal verdict alone. Directly fixes the
   PR #282-class human-trust failure (finding #5) at effectively zero
   engineering cost; no code path changes, just report text.

2. **(Low cost) Promote `llm_escalate_major` / per-page confirmed-missing to a
   loud advisory line, not a gate.** The primitive, tests, and guardrails
   already exist (`fusion.py`, `test_fusion.py`); the only change is making the
   existing `combined_rule == "llm_escalate_major"` case visually distinct in
   `report.md`/`tapetum-inspect.md` output so operators do not have to grep the
   JSON to find it. Zero determinism risk because the exit code is untouched.

3. **(Low cost) Report grader-disagreement rate as a standing metric.** Rerun a
   fixed labeled slice (the existing 20-PID sweep set, or the 9 human-reviewed
   PRs) twice per tapetum-lane release and publish the flip rate next to the
   verdict histogram in `SYNTHESIS.md`-style tracking. This operationalizes
   P23's own falsifier and turns "the LLM is flaky" from an assertion into a
   tracked number, cheaply.

4. **(Medium cost) Marker-style image-grounded per-page judging for the PDF
   lane (P20).** Targets the heading/table-formatting blind spot the
   text-layer judge structurally cannot see; reuses existing `vision.py`
   groundwork; stays fully within D5/D6/D11 (temp=0, schema-locked, serial).
   Advisory-only, so no reproducibility risk is introduced.

5. **(Medium-high cost, infra) Measure flip rate under
   `VLLM_BATCH_INVARIANT_LEVEL`.** This is the one experiment that could
   actually promote P12's CI-binding proposal from "not yet" to "acceptable."
   Costs pod throughput (~50% per `MODELS.md`) during the measurement window
   only; P23's own bar (<=1% per-PID flip on the fixed 20-PID set,
   quote-agnostic fusion rules) is the acceptance criterion. Do not bind to CI
   before this runs.

6. **(Highest cost, deferred, needs 30-50+ labeled papers) Formal calibration
   fit (P17).** Only relevant once/if a numeric confidence weight is ever
   wanted in fusion; today confidence is a documented decorative no-op
   (findings #1-#4), and ordinal merge (verdict + grounded-evidence + severity)
   is the entire safe surface. Do not schedule this before items 1-3 are done
   and item 5's answer is known, since a "not yet CI-bindable" answer from item
   5 would make a calibration study for CI-gating purposes moot (though it
   would still be independently useful for the fusion clear/escalate ordinal
   rules' precision).
