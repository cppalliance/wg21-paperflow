# 17 - Determinism-Auditor

**Verdict:** usable-with-conditions — a merged det+LLM artifact is architecturally sound only if the merge is a pure function over frozen sidecar dicts, records full lane provenance, and rejects stale tapetum inputs; the LLM lane is quality-stable, not rerun-identical, so the merged verdict must never be marketed as deterministic.
**Confidence:** high

## Findings

- [CRITICAL] Model retries are an observed, high-rate alternate generation path: the 2026-07-06 batch logged **118 model retries** across 194 adjudicated papers (`00-baseline.md:49`), and each retry re-issues the LLM with a changed request (malformation retries append prior `raw_content` plus a corrective user turn at `model_backends.py:398-405`; truncation retries grow `max_tokens` at `model_backends.py:384-387`). Impact: a paper that succeeds on attempt 2 can carry a different `suggested_verdict`, axis findings, and confidence than attempt 1 would have on a clean path; any merge that treats tapetum as a stable scalar will flap when retries fire on re-run.

- [CRITICAL] Neither sidecar records input provenance today, so joining lanes after `whisker --all` cannot be proven sound. Whisker writes `<pid>.whisker.json` with `schema_version` only (`score.py:84-115`, `__main__.py:246-248`); tapetum writes `<pid>.whisker.tapetum.json` with `whisker_verdict` copied at adjudication time (`adjudicate.py:180-183`, `309`, `models.py:114-136`) but no `md_hash`, no whisker-sidecar hash, no `adjudicated_at`, and no run id. Impact: re-scoring deterministically refreshes the det lane while a stale tapetum sidecar still reflects an old whisker verdict and old markdown snapshot; a merged artifact must record **which tapetum run** (timestamp or run id, `tier1_model`/`tier2_model` already at `models.py:122-124`, plus `md_content_hash` and `whisker_sidecar_hash`) or audits cannot explain verdict drift.

- [HIGH] Tier-2 escalation adds a second independent LLM surface whenever derived signals fire. `_escalation_signals` sorts axis conflict, ungrounded evidence, and ambiguous confidence (`adjudicate.py:213-236`); `_custom_adjudicate` runs a deep call when any signal is non-empty (`adjudicate.py:239-257`); chunked papers skip tier-2 entirely (`adjudicate.py:247-248`). Baseline run: **123 of 194** tapetum verdicts differed from whisker (`00-baseline.md:49`), and research measured axis disagreement on **123/198** papers (`constants.py:32-34` comment). Impact: if axis-conflict escalation is live (post-baseline code), up to ~63% of candidates get a second stochastic pass whose output replaces tier-1 in `_custom_decide` (`adjudicate.py:262`); merged verdict flapping magnitude is second only to retries.

- [HIGH] Chunk folding multiplies LLM variance for oversize papers (~6 in corpus per `constants.py:59-60`). Oversized markdown is split on H2, triaged serially (`adjudicate.py:196-210`, D11 at `adjudicate.py:193-194`), then folded with severity-aware worst axis, **minimum confidence**, and evidence union (`chunking.py:226-292`, `106-123`). Impact: one chunk flipping `tables` fail/major changes the folded overall verdict for the whole paper; partial reads force review (`adjudicate.py:287-291`, `chunking.py:136-150`); this is a smaller fleet fraction but maximal per-paper flip leverage.

- [HIGH] Six tapetum errors left no LLM lane artifact (`00-baseline.md:51`: truncated/invalid JSON after retries). `TapetumResult.to_dict` is only written on success (`cli.py:207-217`, `334-345` on failure). Impact: merge logic must treat absent/errored tapetum as first-class (not silently inherit last sidecar); fidelity rule C5 (`00-baseline.md:43`) forbids a partial merged score mistakable for complete.

- [MED] Sampling is pinned but quality-stability is explicitly not bit-identical. Root CLAUDE.md D5 forbids per-call temperature override (`CLAUDE.md:82`); backends pin `temperature=0.0`, `seed=0` (`model_backends.py:309-312`, `MODELS.md:26-32`); project goal is "same findings, same verdicts, same structure," not byte-identical (`CLAUDE.md:74`, `MODELS.md:7-8`). Hosted stacks can still flip tokens at decision boundaries (`MODELS.md:74-77`). Impact: even with zero retries, tapetum may drift run-to-run; merge must expose both lanes separately and label merged output as **composite/advisory**, not gate-grade deterministic.

- [MED] Post-LLM decide steps are deterministic pure functions given fixed LLM output: severity fold (`chunking.py:106-123`, `adjudicate.py:274-275`), grounding demotion (`adjudicate.py:266-283`, `grounding.py:170-240`), sorted escalation signals (`adjudicate.py:236`), sorted sidecar fields (`models.py:122-131`). Escalation threshold sensitivity had **zero observed demotions** in production: confidence band `[0.35, 0.65]` (`constants.py:27-28`) never intersected tier-1 output (min 0.85 in baseline research), and `CONFIDENCE_DECISION_FLOOR = 0.50` (`constants.py:45`, `adjudicate.py:284-285`) demoted 0/198. Impact: threshold tuning is low flip risk today; retry and escalation paths dominate.

- [LOW] The merge computation itself **can** be a pure function: `(whisker_dict, tapetum_dict | None, policy constants) -> merged_dict` with no I/O, mirroring whisker core (`CLAUDE.md:279-281`, `score.py:84-115`) and tapetum chunk helpers (`chunking.py:18`). `--concurrency N` on the tapetum CLI affects parallel papers only (`cli.py:39-45`, `292-299`, `357-358`), not per-paper merge math. Impact: unit-test merge policies with fixtures; satisfy C1+C2 by writing merged fields to a new artifact without mutating `whisker.json` verdict (`00-baseline.md:38-44`).

### Variance sources ranked by observed magnitude (baseline + code)

| Rank | Source | Observed scale | Code anchor |
|------|--------|----------------|-------------|
| 1 | JSON/API retries (alternate generations) | **118 retries / 194 papers** (~61% papers touched) | `00-baseline.md:49`, `cli.py:371-379`, `model_backends.py:300-405` |
| 2 | LLM semantic output vs deterministic gate | **123/194 verdict mismatch** vs whisker | `00-baseline.md:49` |
| 3 | Tier-2 second pass when escalation fires | 0 escalated in baseline batch; **123/198** axis-conflict candidates if derived gate active | `adjudicate.py:213-257`, `constants.py:32-34` |
| 4 | Chunked multi-call fold | ~6 oversize papers (`constants.py:59-60`) | `adjudicate.py:196-210`, `chunking.py:226-292` |
| 5 | LLM lane absent/error | **6/200** errors, no sidecar | `00-baseline.md:51`, `cli.py:334-345` |
| 6 | Hosted inference non-invariance (serial mitigates MoE) | Not re-run measured; documented | `MODELS.md:69-77`, `cli.py:45`, `adjudicate.py:471` |
| 7 | Confidence/escalation band boundaries | **0/198** in band; floor demoted 0 | `constants.py:27-28,45`, `adjudicate.py:233-234,284-285` |
| 8 | Grounding fuzzy threshold | Deterministic given quotes; flaps only when LLM quotes change | `grounding.py:232-235`, `constants.py:67` |

### Staleness rules (proposed)

1. At whisker write: persist `md_content_hash` (SHA-256 of `backend.get_paper_md(pid)`) and `scored_at` in `<pid>.whisker.json`.
2. At tapetum write: persist the same `md_content_hash`, `whisker_sidecar_hash` (hash of the whisker JSON consumed), `adjudicated_at`, and model slot names (already partially present at `models.py:122-124`).
3. At merge: **reject or mark stale** when `tapetum.md_content_hash != whisker.md_content_hash`, when `tapetum.whisker_verdict != whisker.verdict`, when whisker `schema_version` changes (`constants.py:166`, `score.py:90`), or when tapetum file is missing and policy requires both lanes (C5).
4. Operational: `whisker --all` should not auto-merge; merge runs only when both sidecars pass staleness checks or tapetum is explicitly re-run for changed PIDs.

## False-pass hypothesis

P4182R0-class case: whisker `review` with high `unigram_coverage` (`00-baseline.md:50`); tapetum returns `suggested_verdict=pass` with `confidence=0.95` and empty grounded evidence because demotion applies only to non-pass without grounding (`adjudicate.py:282-283`), while the prompt allows pass with empty evidence on faithful conversions (`tapetum_llm.md:99` area). A merge rule that OR-upgrades on tapetum pass would accept a token-preserving table swap the det lane cannot see (persona-23 mutation evidence in `packages/whisker/research/persona/23-false-negative-hunter.md`).

## False-fail hypothesis

RESCUE population: whisker `fail` on heading-monotone only (`adjudicate.py:128-134`, `select_candidates` RESCUE at `adjudicate.py:94-96`); tapetum marks `structure` fail/non-major, folded to `review` (`chunking.py:117-120`), but a merge rule that takes the stricter of `{fail, review, pass}` without severity awareness could still surface `review` or, if axis severity is mis-labeled `major`, `fail` — blocking a cosmetic heading jump a human would ship (`tapetum_llm.md:66-68`).

## What would change my mind

A controlled re-run study: adjudicate the same 50-PID holdout twice on a fixed pod (`min=max=1`, session affinity per `MODELS.md:82-88`) with `cli.py:45` concurrency=1, record per-PID verdict delta rate and merged-verdict delta rate under a candidate merge policy. If **≥95%** of papers produce identical `suggested_verdict` and identical merged verdict across both runs **and** staleness checks catch 100% of intentional whisker-only re-scores, I would upgrade to **usable** without the provenance/stale guards as hard requirements.
