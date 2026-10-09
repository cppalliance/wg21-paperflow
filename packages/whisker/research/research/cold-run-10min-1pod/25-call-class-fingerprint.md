# 25 - Call-Class Fingerprint (single-pod ops)

**Verdict:** usable-with-conditions — per-call-class fingerprints eliminate the "prompt edit → full 381-paper rerun" tax for dev/ops iteration; **cold first-run impact is 0** on an empty `whisker/llm/` tree.
**Confidence:** high
**Date:** 2026-07-24
**Scope:** `packages/whisker/src/whisker/tapetum_llm/cli.py` fingerprint block; single `alliance-pod` only. Dual-pod is out of scope (`00-baseline.md`).

**In cold-run critical path?** **no**

---

## Executive answer (1pod ops)

| Question | Answer |
|----------|--------|
| **Cold first-run impact?** | **0 s** — no prior sidecars, no call-class entries, every paper pays full ~6-call cascade (~2284 LLM calls, ~3003 s at v10 baseline). |
| **What does it buy?** | **Rerun / iteration** after a prior fleet run: skip LLM calls whose call-class prompt+schema hash still matches, replay cached class output, re-run deterministic merge. |
| **Does it close the ≤600 s single-pod gap?** | **No.** First cold on one pod still needs call elimination (metadata short-circuit, dense offload, schema cuts), not finer skip granularity. |
| **When to ship?** | After v11 cold-path levers land; before the next `_LANE_VERSION` or prompt churn cycle that would otherwise force ~3003 s reruns. |

---

## Problem: monolithic prompt hash

Today's whole-paper fingerprint (`cli.py:595-648`) stores one `prompt_sha256` built from `_pdf_prompt_contract()` — all four PDF-lane system prompts concatenated (`cli.py:505-512`: monolith, page escalation, metadata, unit). `_fingerprint_matches` requires every key equal (`cli.py:679-702`). Any single prompt edit changes `prompt_sha256` and invalidates **all 381 papers**, forcing the full serial cascade even when only one call class actually changed.

Measured baseline (`00-baseline.md`, `tapetum-llm-speedup/00-baseline.md`):

| Metric | Value |
|--------|------:|
| Fleet calls | ~2284 (~6/paper) |
| Cold wall (v10) | 3003 s |
| Warm skip (unchanged inputs) | 375/381 in 64.8 s |
| Unit-prompt-only rerun (today) | ~3003 s (full invalidation) |

Call census at ~20 s/call, S=16 (`tapetum-llm-speedup/10-call-graph-accountant.md`):

| Call class | Count | Est. wall |
|------------|------:|----------:|
| Unit check | ~1510 | ~1888 s |
| Metadata / outline | 377 | ~471 s |
| PDF monolith + HTML tier-1 | ~381 | ~476 s |
| Page escalation | ~16 | ~20 s |
| Ideal verify | ~1 | negligible |

---

## Proposed design: per-call-class fingerprints

Split the monolithic contract into class-scoped hashes stored in the sidecar (and/or a shared `whisker/llm/cache/` memo table). Each LLM invocation checks only its class before HTTP.

### Call classes

| `call_class` | Prompt source | Schema | Typical label prefix |
|--------------|---------------|--------|--------------------|
| `monolith` | `JUDGE_SYSTEM_PROMPT` | `PdfJudgment` | `monolith` |
| `metadata` | `METADATA_CHECK_SYSTEM_PROMPT` | `MetadataOutlineCheck` | `metadata` |
| `unit` | `UNIT_CHECK_SYSTEM_PROMPT` | `UnitCheck` | `unit-check` |
| `page_escalation` | `PAGE_JUDGE_SYSTEM_PROMPT` | `PageJudgment` | `page-escalation` |
| `ideal_verify` | `IDEAL_VERIFY_PROMPT_CONTRACT` | `IdealVerification` | (already separate in fingerprint) |

### Sidecar shape (sketch)

Extend tapetum sidecar beyond top-level `fingerprint`:

```json
{
  "fingerprint": { "md_sha256": "...", "source_sha256": "...", "coverage_mode": "default", ... },
  "call_cache": {
    "monolith": { "prompt_sha256": "...", "schema_sha256": "...", "lane_version": 11, "llm_output": { ... } },
    "metadata": { ... },
    "units": {
      "page:7": { "source_sha256": "...", "risk_signal_sha256": "...", "prompt_sha256": "...", "llm_output": { ... } }
    },
    "page_escalations": { "page:3": { ... } }
  }
}
```

Whole-paper skip (today's fast path) remains: if top-level fingerprint matches, skip the paper in <1 s. Partial invalidation: run only call classes whose hash mismatches, then deterministic merge (`pdf_judge.py:710-928`).

### Class-scoped `lane_version`

Replace fleet-wide `_LANE_VERSION` in every class key with per-class versions (`monolith_v`, `unit_v`, …) or hash the specific Python contract function. A v10-style routing-only bump re-runs **~1510 unit calls (~1888 s)** instead of 2284 (~3003 s) when monolith/metadata prompts are unchanged (`tapetum-llm-speedup/19-incremental-granularity.md:18`).

### Guard-tag normalization (required)

v11 HMAC per-paper guard tags (`cli.py:467-479`) must not poison cache keys. Hash user payload with a fixed sentinel; live prompt keeps the real tag (same pattern as promptfoo body normalization, `135-promptfoo-concurrency-caching.md:18`).

---

## Impact matrix (single pod, S=16)

| Scenario | Calls re-LLM'd (est.) | Est. wall | vs 3003 s | Cold first-run? |
|----------|----------------------:|----------:|----------:|:----------------|
| **True cold (empty sidecars)** | 2284 | **3003 s** | 0% | **yes — 0 s saved** |
| **Cold `--force`** | 2284 | **3003 s** | 0% | **yes — 0 s saved** |
| Warm fleet (unchanged) | ~34 | ~65 s | −98% | no (whole-paper gate) |
| **`_LANE_VERSION` bump, prompts unchanged** | ~758 (mono+meta) | ~2055 s | −32% | no (rerun) |
| **Unit-prompt-only edit** | ~774 (mono+meta+page) | ~2035 s | −32% | no |
| **Metadata-prompt-only edit** | ~1907 (mono+unit+page) | ~476 s | −84% | no |
| **Monolith-prompt-only edit** | ~1903 (meta+unit+page) | ~476 s | −84% | no |
| **Page-prompt-only edit** | ~2268 | ~20 s delta | −99% class | no |
| Single-page tomd fix + per-unit keys | ~3/paper changed | ~60 s/paper | partial | no |

**Cold first-run impact: 0.** Per-call-class fingerprints are a **rerun accelerator**, not a first-pass throughput lever.

---

## 1pod operator guidance

### When this helps

- Prompt or schema edits during golden-PR / tomd-fix iteration loops.
- `_LANE_VERSION` bumps that change routing or merge logic in one lane only (e.g. unit quota) without touching monolith/metadata prompts.
- Re-running after transient errors when error tombstone fingerprints already skip clean papers (`10-impl-status-1pod.md` lever #4).

### When this does NOT help

- **First cold fleet** on empty `whisker/llm/` — still ~2284 calls, ~21–25 min post-v11 (`10-impl-status-1pod.md`), not ≤600 s.
- Closing the single-pod gap — use metadata short-circuit (landed v11), dense offload, payload scoping, verdict-first schema (`10-impl-status-1pod.md` Tier 1).
- Markdown surgical fixes without per-unit keys — still re-LLM all unit checks on that paper unless paired with per-unit `call_cache` (`cold-run-10min/30-per-unit-fingerprint.md`).

### Ops checklist (if implemented)

1. **`--no-llm-cache`** flag for A/B parity runs (mirror promptfoo `--no-cache`).
2. Bump **`call_class_version`** for the class whose Python merge/fold logic changed, not global `_LANE_VERSION` alone.
3. On any **`md_sha256` change**: always re-LLM monolith + metadata; re-ground cached unit outputs (`19-incremental-granularity.md:12-13`).
4. Exclude **`call_timings[]`** from fingerprint hash (observability must not invalidate skip).
5. Document which prompt edit invalidates which class in release notes — operators should expect ~8 min reruns for monolith/metadata edits vs ~31 min for unit-only edits.

---

## Findings

- [CRITICAL] **Cold first-run impact is 0.** Incremental logic fires only when a sidecar `call_cache` entry exists and its class hash matches. Greenfield cold (`whisker/llm/` empty) or `--force` runs all 2284 calls regardless (`cold-run-10min/30-per-unit-fingerprint.md:12`, `19-incremental-granularity.md:20`).

- [CRITICAL] **Monolithic `prompt_sha256` is the iteration tax.** `_pdf_prompt_contract()` concatenates four prompts (`cli.py:505-512`); one `UNIT_CHECK_SYSTEM_PROMPT` edit invalidates 381/381 papers (~3003 s). Call-class split reduces unit-only deploy reruns to **~1888 s (~31 min, −37%)** and monolith/metadata-only edits to **~471–476 s (~8 min, −84%)** (`19-incremental-granularity.md:10`).

- [HIGH] **Quality-safe replay requires deterministic merge after cache hit.** On hit, return cached Pydantic JSON but still run post-processors (`pdf_judge.py:697-706`, `unit_judge.py:604-648`). Bump `call_class_version` when fold/aggregation logic changes without prompt edits (`135-promptfoo-concurrency-caching.md:37`).

- [HIGH] **Per-unit granularity is orthogonal and stacks on markdown edits.** Call-class split fixes prompt-bump reruns; per-unit `call_cache` fixes surgical tomd reconverts (~6 → ~3 calls per changed paper). Neither moves cold first-run wall (`cold-run-10min/30-per-unit-fingerprint.md`).

- [MED] **Not ranked in single-pod ≤600 s path.** v11 metadata short-circuit (−1059 to −1341 s), dense offload (−850 to −1200 s), and decode shrink address **N** and **L** on first cold. Call-class fingerprint addresses **redundant reruns** only (`00-baseline.md:41-42`).

- [LOW] **Implementation anchors:** `cli.py:595-702` (fingerprint), sidecar persist (`719-828`), `judge_task.py` lookup hook, tests `packages/whisker/tests/test_incremental.py`. Precedent: promptfoo disk cache (`135`), persona 19 sidecar design (`19-incremental-granularity.md`).

---

## False-pass hypothesis

**v11 routing bump with cached monolith/metadata:** replay cached monolith `pass` while new unit pre-filter would cap at `review`. Mitigation: bump `unit_v` on routing changes; replay monolith/metadata only when class version + inputs match (`135-promptfoo-concurrency-caching.md:37`).

## False-fail hypothesis

**Skipping monolith on front-matter-only `md_sha256` change:** misses TOC-leak detection in monolith reasoning (`pdf_judge.py:180-202`). Mitigation: always re-LLM monolith + metadata on any candidate change (`19-incremental-granularity.md:28`).

## What would change my mind

A measured post-v11 cold run on empty sidecars showing **<2800 s** wall solely from call-class fingerprint plumbing (no other levers) would contradict the 0 s first-cold claim. No such mechanism exists in the design: cache lookup precedes HTTP only when a prior sidecar row is present.

---

## Related corpus

| Doc | Relationship |
|-----|--------------|
| `cold-run-10min/30-per-unit-fingerprint.md` | Per-unit skip layer; same 0 s cold impact |
| `tapetum-llm-speedup/19-incremental-granularity.md` | Full call-class + per-unit design |
| `tapetum-llm-speedup/135-promptfoo-concurrency-caching.md` | HTTP memo pattern + impact table |
| `cold-run-10min-1pod/10-impl-status-1pod.md` | What actually moves single-pod cold wall |
| `cold-run-10min-1pod/00-baseline.md` | Hard constraint: one MoE pod, ≤600 s goal |
