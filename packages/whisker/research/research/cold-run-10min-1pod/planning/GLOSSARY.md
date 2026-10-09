# GLOSSARY — cold-run 10 min / 1 pod

**Date:** 2026-07-24  
**Corpus:** `research/cold-run-10min-1pod/`  
**Audience:** planners and implementers reading ADRs / CODE-ANCHORS.

---

## alliance-pod

The live Alliance MoE endpoint that serves **DeepSeek-V4-Pro** for `whisker-tapetum-llm`. Declared in repo-root `SERVICES.toml`. Hard constraints for this program: sole V4-Pro replica, server `--max-num-seqs 16` (`S_eff = 16`), client paper concurrency default 32. Raising server slots to 32 was measured to **worsen** wall (~+57%). All MoE-only wall arithmetic assumes this pod.

---

## twin

A second DeepSeek-V4-Pro replica (historically `h200x8-deepseek-v4-pro`) that would double MoE scheduler capacity (effective S 16→32) via dual-pod sharding. **Forbidden** for this program (budget/authority; ADR-001). Also infra-dead (HTTP 404) as of the 2026-07-24 probe. Dual-pod MODERATE ~596 s plans from `research/cold-run-10min/` are historical context only. Dense offload to a different model family is **not** a twin.

---

## S_eff

**Effective server concurrency** used in wall formulas: number of in-flight decode/prefill slots the MoE pod can keep busy. For this corpus **S_eff = 16** always (matches `--max-num-seqs 16`). Never silently substitute 32. Dense pods may use their own S (e.g. 32–48) when offloading; that does not change MoE `S_eff`.

---

## N_rem

**Remaining LLM call count** after call-elimination levers (short-circuit, router cuts, deterministic metadata, etc.). Baseline cold fleet ≈ **2284** calls (381 papers). After v11 metadata short-circuit ≈ **1419**. Wall compute term scales with `N_rem`, not the original fleet size.

---

## L_eff

**Effective mean latency per call** (seconds) for the mix still on a given queue after latency-changing levers (decode shrink, dense 2× hypothesis, Non-think, etc.). Baseline planning value **L ≈ 20 s**. Dense-offload AGGRESSIVE models often use a blended `L_eff` (e.g. ~11.7 s) when some fraction of calls run faster on dense hardware; heterogeneous layouts prefer separate `T_moe` / `T_dense` legs instead of one blended L.

---

## monolith

The **whole-document first-pass LLM judgment**: PDF `PdfJudgment` over full PDF text + full candidate markdown, or HTML tier-1 triage over the full document. Kept on `alliance-pod` (393k context). Complements unit checks; must not be skipped as a default “10 min” lever (ADR-009). ~381 first-pass calls dominate MoE queue once units/metadata move elsewhere.

---

## unit check

A **scoped** structured LLM call (`UnitCheck`) against one risky region (`page:N` or `section:…`) after the monolith and metadata steps, selected by the source router up to `MAX_UNIT_CHECKS` (default 5). Catches localized omissions the monolith quote budget cannot express. Implemented mainly in `unit_judge.py` (`_check_one_unit`). Majority of fleet call volume; primary target for dense offload and verdict-first decode shrink.

---

## metadata/outline

The mandatory per-paper **front-matter + heading outline** comparison (`MetadataOutlineCheck` via `run_metadata_outline_check`). Runs after monolith even when no risky units are routed. Verdict folds into the paper (fail forces fail; review demotes pass) and can **short-circuit** further unit/page work when non-pass. Deterministic-metadata lever replaces this LLM call with a pure `compare_metadata_outline()` while preserving the same schema and fold rules.

---

## short-circuit

**Metadata-fail short-circuit (v11):** when metadata/outline verdict already caps the paper, skip page escalations and unit checks (audit flags exempt). Largest landed call cut (~44.6% of fleet calls; ~−1059 to −1341 s @ S=16). Orthogonal to **deterministic metadata**, which removes the metadata LLM itself rather than skipping downstream work after it runs.

---

## fusion

Post-hoc pure merge of the **deterministic whisker sidecar** with the **tapetum LLM sidecar** (`fusion.py`). Produces `combined_verdict` / rules. Asymmetric and demotion-oriented: advisory LLM can demote but never hard-fail CI and never overwrite the whisker verdict on record. Quality gates for dense/det-metadata require parity on fused fields, not only raw LLM JSON.

---

## whisker-tapetum-llm cold

A **full-fleet cold run** of the opt-in advisory CLI `whisker-tapetum-llm`: 381 converted papers, fingerprint skip disabled or invalidated (true cold), against live pods. Baseline measured wall ~**2883–3003 s (~48–50 min)** at S=16, client c=32. Distinct from warm incremental runs (tombstones / fingerprints) and from deterministic `whisker` scoring. Target discussed in this corpus: ≤**600 s (~10 min)** under quality-stability — physics-hard on MoE-only.

---

## dense offload

Routing **unit checks** (and optionally metadata LLM calls) to an already-running **open-weight dense** Alliance endpoint (primary candidate: `h200-qwen3-32b`), while monolith / HTML tier-1 / oversize / page escalations stay on `alliance-pod`. Fleet wall ≈ **`max(T_moe, T_dense)`**, not a second V4-Pro. Requires payload scoping for S>16 on dense; requires 381/381 fused-verdict parity before `_LANE_VERSION` bump. As of 2026-07-24 dense endpoints may be HTTP 404 (infra-blocked).

---

## payload scoping

Shrinking the **unit-check LLM prompt** from full `candidate_md` to a **H2 window (±1 neighbor) + compact presence index** (~10–12k tokens), while post-hoc grounding still uses full raw markdown. Unblocks dense KV concurrency (S=32–48 with FP8 KV). Without it, dense offload stays at MoE-class L and is negative EV. Prefill savings alone on MoE are secondary (~7%); main job is dense headroom.

---

## verdict-first

Decode-shrink design: emit **verdict (and confidence) before long reasoning**, and bifurcate schemas so clean passes use a micro-schema (`UnitCheckClear`: no nested `defects[]`) while defect paths use a fuller `UnitCheckDefects`. Optional tighter `max_tokens` on the clear path. Saves decode/grammar work on ~70% pass-shaped unit calls. Apply savings to **post-short-circuit survivors** only when stacking. MODERATE stack estimate ~**124–155 s** @ S=16; does not alone hit 600 s.

---

## Non-think

Serving/client mode that **disables chain-of-thought / thinking blocks** for structured judge JSON (kwargs such as `thinking=false`, `enable_thinking=false`, or `reasoning_effort="none"`). Cuts thinking-token latency tax. **Never** use `reasoning_effort="low"` on DeepSeek-V4 — it maps to High. Probe and A/B before banking wall seconds; may already be active on alliance-pod.

---

## MTP

**Multi-Token Prediction** speculative decode (vLLM / DeepSeek stack). Can raise decode tok/s when acceptance is healthy; on short structured JSON at saturated batch (`max-num-seqs 16`, client c=32) often **flat or lose**. Policy: MTP k=1 **A/B only**; **do not bank** MTP seconds in central wall plans. Related speculative schemes (DSpark, ngram) follow the same measure-or-off rule under full slots.

---

## DeepEP

DeepSeek **expert-parallel** communication backend for MoE serving (e.g. vLLM `--all2all-backend deepep_low_latency`). Ops Tier-1 lever: planning ~**10–15%** tok/s at S=16 from low-latency DeepEP alone; DBO only if DEP thresholds fire. Server-side only; does not change client call graph. Never pair with forbidden S=32 as a “fix.”

---

## Package A / B / C

In this planning pack, **Packages A/B/C** mean the three **execution options** (also called Options A/B/C in `01-OPTIONS-ABC.md`):

| Package | Name | Intent |
|---------|------|--------|
| **A** | MoE-only | Ship call cuts + decode discipline on `alliance-pod` alone. Honest wall ~12–23 min (MODERATE ~1366–1493 s). **Do not claim ≤10 min.** |
| **B** | Heterogeneous dense | Design for ≤600 s via `max(T_moe, T_dense)` + scoping + parity. **Only arithmetic path to ~10 min** under the twin ban. Infra-blocked while dense pods 404. |
| **C** | SLA reset | Stop the 10-min program; publish ~**15–20 min** as the goal if dense will not restart and twin stays forbidden. |

Related but distinct: lever **stacks** CONSERVATIVE / MODERATE / AGGRESSIVE in `18-packages-1pod.md` (prefix/tombstones → short-circuit+verdict-first → router+dense+det-metadata). AGGRESSIVE numbers assume dense offload and feed Package B arithmetic; they are not Package A walls.

---

## Quick formula

```
# Single MoE queue
wall ≈ (N_rem × L_eff) / S_eff + T + C − L_abs

# Heterogeneous (Package B)
wall ≈ max(T_moe, T_dense) + T_client
```

`T` = paper-tail / LJF term; `C` = client stall; `L_abs` = absolute decode/prefix savings not re-divided by S.
