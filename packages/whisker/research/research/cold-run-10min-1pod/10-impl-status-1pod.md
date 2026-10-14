# 10 - Implementation Status: single-pod path (no twin)

**Verdict:** usable-with-conditions — v11 in the working tree already captures the largest single-pod call cut (metadata short-circuit) and most CONSERVATIVE scheduling/cache levers; **~21–25 min** cold wall is reachable at HEAD without code, but **≤600 s requires dense offload + AGGRESSIVE call/schema cuts**, not dual-pod.
**Confidence:** high on what is coded; medium on exact post-v11 wall (needs one fresh cold run)
**Date:** 2026-07-24
**Scope:** `packages/whisker/src/whisker/tapetum_llm/` working tree vs `research/cold-run-10min-1pod/00-baseline.md`. **Dual-pod is out of scope.**

---

## Executive summary

| Question | Answer |
|----------|--------|
| What does v11 buy on one pod? | **~1059–1341 s** from metadata short-circuit alone; plus partial in-paper prefix reuse (HMAC + md-first on PDF unit/page). Expected cold wall **~1260–1493 s (~21–25 min)**, not 3003 s. |
| Can MODERATE software alone hit 10 min on one pod? | **No.** Compute on 1419 surviving calls @ S=16 is **~1774 s** before latency trims (`22-path-a-b-10min.md`). |
| Gap after v11 MODERATE (single pod) | **~660–893 s** vs 600 s target |
| What code closes the gap? | Dense unit/metadata offload, deterministic metadata, verdict-first decode shrink, router tightening, payload scoping |

---

## v11 levers already in working tree (single-pod value)

Audited against `research/cold-run-10min/10-impl-status-auditor.md` and HEAD sources.

| # | Lever | Status | Evidence | Single-pod impact |
|---|-------|--------|----------|-------------------|
| 1 | **Metadata-fail short-circuit** | **Done** | `pdf_judge.py:742-759` skips page escalations + unit checks when metadata ≠ pass (exempt: `--all-pages`, `--exhaustive-units`, `--inspect`); HTML mirror `adjudicate.py:521-531`. `_LANE_VERSION = 11` (`cli.py:119-123`). | **−1059 to −1341 s** (44.6% fleet calls). Largest landed lever. |
| 2 | **HMAC per-paper guard tag** | **Partial** | `_paper_guard_tag` (`cli.py:467-479`); wired PDF path `cli.py:1331-1333`. Text lane `adjudicate_paper()` at `cli.py:1402-1412` receives **no** `guard_tag`. | Partial prefix reuse on PDF lane; text lane (~50% calls) still random tags per call. Est. **−100 to −200 s** unrealized. |
| 3 | **Candidate-md-first user messages** | **Partial** | Unit checks `unit_judge.py:791-798`; page escalations `pdf_judge.py:397-403`. **Not reordered:** monolith RAW-PDF-first `pdf_judge.py:662-665`; metadata source-first `unit_judge.py:252-261`; text triage `adjudicate.py`. | In-paper APC on PDF unit/page only. Monolith + metadata still break shared-prefix chain. |
| 4 | **Error tombstone fingerprints + `--retry-errors`** | **Done** | Flag `cli.py:373-378`; tombstone writer `cli.py:810-828`; skip path `cli.py:1269-1293`. | Warm steady state **65 s → ~10–15 s** after failed runs; no cold-wall change. |
| 5 | **LJF paper ordering** | **Done** | `_sort_pids_ljf` `cli.py:1030-1038`; applied full run `cli.py:1063`. | Tail trim **~−30 to −60 s** (T+C term). |
| 6 | **`asyncio.to_thread(screen_pages)`** | **Done** | `pdf_judge.py:658`. | Client stall trim **~−30 s**. |
| 7 | **Monolith / tier timeouts** | **Done** | `MONOLITH_TIMEOUT_SECONDS = 240.0` `constants.py`; PDF `pdf_judge.py:672-681`; text `adjudicate.py:244-246`. | Prevents hung-slot tail; bounded worst case. |
| 8 | **Empty-packet pre-filter (v10)** | **Done** | `unit_judge.py:370-381` excludes unroutable IDs before quota selection. | Stops quota slot burn; **0 LLM tokens** saved class already fixed. |
| 9 | **Per-paper `duration_seconds`** | **Done** | `cli.py:723-741, 1375-1378`. | Observability only. |

### Expected cold wall at working-tree HEAD (single pod, S=16)

```
Baseline:     3003 s
After v11:    3003 − 1200 (short-circuit mid) − 200 (partial prefix est.) − 90 (LJF+to_thread)
            ≈ 1260–1493 s (~21–25 min)
Gap to 600 s: ~660–893 s
```

No fresh cold run post-v11 exists; remeasure before treating arithmetic as fact.

---

## Remaining code to write (single-pod only)

Dual-pod shard, per-pod semaphores, and twin health probes are **explicitly excluded**.

### Tier 1 — required to approach ≤600 s on one MoE pod

| Lever | Status | Code surface | Est. wall impact @ S=16 | Quality gate |
|-------|--------|--------------|------------------------:|--------------|
| **Dense judge offload** (unit + metadata → live dense pod) | **Not started** | New per-call-type service routing in `cli.py` / `judge_task.py`; pass scoped payloads; MoE fallback for oversize; `_LANE_VERSION` bump | **−850 to −1200 s** | **381/381** fused verdict parity (`16-dense-judge-candidates.md`, `23-small-judge-evaluator.md`) |
| **Payload scoping** (unit/metadata windows) | **Not started** | `unit_judge.py`, `source_router.py` — scoped candidate + source slice per unit | Enabler for dense; without it dense pod reverts to S≤16, L≈20 s | MEDIUM if index misses dehyphenated matches |
| **Deterministic metadata diff** (no LLM) | **Not started** | Replace `run_metadata_outline_check` LLM path with `source_router.py` / `html_outline.py` deterministic compare | **−~471 s** (377 metadata calls) | HIGH — must match fold semantics (`17-metadata-shortcircuit-design.md`) |
| **Verdict-first / terse pass schema** | **Not started** | `models.py` (`UnitCheck`, `MetadataOutlineCheck`); conditional pass reasoning; optional `max_tokens` in `run_judge_task` | **−124 to −360 s** decode on survivors | 48-anchor holdout ≥95% verdict stability (`47-max-tokens-shrink.md`) |
| **Router combo_safe tightening** | **Not started** | `source_router.py` signal emission / `_select_units_with_quotas` policy | **−~80 to −130 s** post-short-circuit (~63 calls scaled) | 6/47 defect-group papers at risk (`50-router-false-economy.md`) |

### Tier 2 — MODERATE hygiene (small but shippable)

| Lever | Status | Code surface | Est. impact |
|-------|--------|--------------|------------:|
| **Escalation dedupe** | **Not started** | Skip unit check when page escalation already covered same page (`pdf_judge.py:818-944`) | **~−23 s** |
| **Text-lane HMAC + md-first** | **Partial** | Thread `guard_tag` through `adjudicate_paper()` + HTML unit/metadata prompts | **~−100 to −200 s** prefix |
| **Monolith + metadata prompt reorder** | **Not started** | `pdf_judge.py:662-665`, `unit_judge.py:252-261` | Incremental APC on 758 MoE-resident calls |
| **Per-call `call_timings[]` in sidecars** | **Not started** | `pdf_judge.py`, `judge_task.py`, `cli.py` persistence | **0 s** (unblocks honest A/B) |
| **Dynamic / lowered `MAX_UNIT_CHECKS`** | **Constant only** | `constants.py:223` (=5); cap-3 experiment | **−503 s** if holdout passes (`58-max-unit-checks-knob.md`) |

### Tier 3 — ops / server (not client code)

Confirm on `alliance-pod` only: `--enable-prefix-caching`, `--max-num-batched-tokens 16384`, `--tokenizer-mode deepseek_v4`, `--reasoning-parser deepseek_v4`, keep `--max-num-seqs 16` (`26-server-ops-checklist.md`). Optional A/B: `--all2all-backend deepep_low_latency`, `--enable-dbo` (`64-flashinfer-moe-kernels.md`). **Forbidden:** `--max-num-seqs 32` (+57% wall).

---

## Single-pod path arithmetic (MODERATE + AGGRESSIVE code stack)

Fixed **S_eff = 16**. No silent S=32.

```
wall = (N_rem × L_eff) / 16 + T + C − L_abs
```

| Stack | N_rem | L_eff | Central wall (s) | Hits 600 s? |
|-------|------:|------:|-----------------:|:-----------:|
| v11 only (landed) | ~1419 | 20 | **~1366** | ❌ |
| + verdict-first | ~1419 | ~18.5 | **~1240** | ❌ |
| + router combo_safe | ~1356 | ~18.5 | **~1170** | ❌ |
| + deterministic metadata | ~979 | ~18.5 | **~920** | ❌ |
| + dense offload (validated) | ~979 | ~11.7 | **~585–715** | ⚠️ hairline |

Dense offload is the only remaining **code lever** with enough headroom to cross 600 s on one MoE pod; it requires Tier-1 validation, not a flag flip.

---

## Recommended execution order (1-pod corpus)

1. **Measure:** cold fleet on working-tree v11; confirm ~21–25 min, not 48 min.
2. **Finish partial v11:** text-lane HMAC + md-first; monolith/metadata reorder (low risk, no lane bump if prompt geometry unchanged).
3. **Instrument:** per-call `call_timings[]` (enables A/B denominators).
4. **MODERATE:** verdict-first schema + holdout gate.
5. **AGGRESSIVE:** payload scoping → dense routing for unit + metadata → deterministic metadata diff → router combo_safe (each with quality gate).
6. **Optional:** escalation dedupe; MAX_UNIT_CHECKS cap-3 A/B.

---

## False-pass hypothesis

Operator ships dense offload without 381-paper parity gate: localized omissions (P0957R8-class) pass on dense 32B while V4-Pro would flag `candidate_not_found`, silently weakening advisory recall while wall looks like success.

## False-fail hypothesis

Operator rejects dense offload because "different model," stays at ~1366 s single-pod MODERATE, when validated heterogeneous routing was the only code path left to 10 min without a second V4-Pro replica.

## What would change my mind

1. Post-v11 cold run ≤700 s on one pod without dense offload → revisit L_abs / short-circuit accounting.
2. Dense offload A/B ≤620 s with ≤1.1× borderline verdict-flip rate → upgrade AGGRESSIVE 1-pod path to ✅.
3. Deterministic metadata matches LLM metadata on 381-paper replay with zero fold drift → ship without LLM metadata call.
