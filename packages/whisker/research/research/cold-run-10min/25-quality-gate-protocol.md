# 25 - Quality gate protocol (short-circuit + HMAC + dual-pod → MODERATE)

**Verdict:** usable-with-conditions — ship the three named levers and the MODERATE package only through a two-run A/A noise floor plus one bundled `--force` B run and three post-hoc gates; lying about quality is prevented by the four-component equivalence vector plus dev-replay recall, not verdict histogram alone.

**Confidence:** high (grounded in `tapetum-llm-speedup/SYNTHESIS.md` §4, `47-quality-equivalence.md`, HEAD census `10-impl-status-auditor.md`)

**Sources:** SYNTHESIS quality gate (2026-07-23), persona 47 (2026-07-17 labels), cold-run baseline (3003 s / ~50 min per fleet run).

---

## 1. What “not lying about quality” means

Three tiers, all required for levers that skip calls or change prompts (`47-quality-equivalence.md`):

| Tier | Corpus | Pass criterion | Catches |
|------|--------|----------------|---------|
| **Fleet flip ceiling** | 381 papers, `--force` cold | `flip_AB ≤ flip_AA + margin` on the **four-component equivalence vector** | Verdict churn inside MoE noise; silent defect-type drops |
| **Dev-replay recall** | 9 golden PRs, 29 labeled defect groups | `recall_B ≥ recall_A − 0.05` AND clean papers still match `expected_llm_verdict` | Short-circuit false-pass: verdict unchanged, localized findings vanish (`47:26-27`) |
| **Holdout anchor recall** | 3 papers, 48 locked anchors | Anchor-level recall on `expected_candidate_status` non-regressing vs A | Evidence-grounding regressions on frozen candidates |

**Equivalence vector per PID** (all four must match for “equivalent”):

1. `suggested_verdict`
2. `fusion.combined_verdict` (after deterministic `--fuse-only` refresh)
3. Defect-group multiset keyed by `defect_type` only (ignore quotes / null `verified_count`)
4. Coverage tuple `(coverage_complete, unchecked_unit_ids, failed_unit_ids, checked_count, mode, all_pages_requested)`

**Noise floor:** identical config A1 vs A2 on full 381 corpus establishes `flip_AA`. Default margin:

`max(0.02, 1.96 × sqrt(flip_AA × (1 − flip_AA) / 381))`

Candidate B passes iff discordant with **both** A runs (tie-break). Secondary: McNemar on paired verdict flips.

The documented **≥25% flip on 20 borderline PIDs** is not the fleet gate (`SYNTHESIS.md:60-61`; `150-verifier` correction). Measure `flip_AA` on 381 once at current `_LANE_VERSION`.

---

## 2. Lever classification (the three named levers)

| Lever | Changes call graph? | Changes LLM inputs? | Exempt from full 381? | Gate tiers |
|-------|---------------------|---------------------|----------------------|------------|
| **Metadata short-circuit** | Yes (−847 to −1047 calls) | No (skipped calls only) | **No** | Fleet + dev-replay + holdout |
| **HMAC guard tag + user reorder** | No | Yes (prompt layout) | **No** | Fleet + dev-replay + holdout |
| **Dual-pod shard** | No (scheduling only) | Same prompts per paper | **Conditional** — share B run; still run full 381 equivalence on B | Fleet flip + wall-time; dev-replay/holdout from same sidecars |

**Bundling rule (`47:16-17`):** HMAC and short-circuit **must not** be validated in separate isolated runs if the goal is minimum wall time — one B run carries both. Failure attribution is confounded; acceptable for ship, not for debugging.

Dual-pod composes with both (same token streams, partition only). One combined B is honest for ship.

**HEAD note (`10-impl-status-auditor.md`):** short-circuit is **live in v11**; HMAC/reorder is **PDF-only partial**; dual-pod is **not implemented**. Protocol below assumes: finish HMAC text-lane parity + implement dual-pod, then validate the bundle (retroactive short-circuit proof included).

---

## 3. Minimal A/A protocol (once per `_LANE_VERSION` regime)

| Step | Command shape | Wall time |
|------|---------------|-----------|
| **A1** | Full 381 cold, config A, `--force`, `_LANE_VERSION` = ship target | ~50 min |
| **A2** | Repeat A1 identical flags | ~50 min |
| **Compute** | Equivalence vector diff A1↔A2 → `flip_AA`, store discordant PID list | ~10 min |

**Operational shortcut (`47:16`):** reuse a **weekly refreshed A2** from `research/tapetum-llm-speedup/_scratch/aa-baseline/` → skip second live run (−50 min). Still valid only if same `_LANE_VERSION`, pod image, and `SERVICES.toml` contract.

**Do not** use warm fingerprint skip for equivalence measurement (`47:16`).

---

## 4. Minimal A/B protocol (short-circuit + HMAC + dual-pod)

### 4.1 Single bundled B (recommended minimum)

| Step | Config B contents | Wall time |
|------|-------------------|-----------|
| **B1** | A + per-paper `HMAC(secret, pid)` on **all lanes** + document-first user reorder on unit/page/metadata where applicable + metadata Tier A+B short-circuit (fail skip; review → 1 top unit per `17-metadata-short-circuit.md:16`) + `--shard-pods alliance-pod,h200x8-deepseek-v4-pro` + per-pod `Semaphore(16)` + shard-set in fingerprint | ~50 min |
| **Gates** | Post-hoc on B1 sidecars (no extra LLM) | ~10–15 min |

**Pre-flight (not counted in gate wall, but blocks false-fail):**

- Dual health probe on both pods (`21-dual-pod-sharder.md:12`)
- `/metrics` scrape during B1: prefix hit rate, prefill/decode split (`SYNTHESIS.md:66-67`)

### 4.2 Pass/fail worksheet

```
flip_AB   = fraction of 381 PIDs not equivalent to A1 (and flagged vs A2)
PASS flip  iff flip_AB ≤ flip_AA + margin

recall_A, recall_B = dev-replay defect-group hits / 29
PASS recall iff recall_B ≥ recall_A − 0.05 AND expected_llm_verdict unchanged on clean papers

holdout_B ≥ holdout_A  (48 anchors, locked candidate SHA-256)

wall_B ≤ 1700 s first dual-pod adoption target (21-dual-pod); planning MODERATE central ~596 s after full MODERATE stack
```

**Short-circuit-specific secondary metrics** (report, not alternate pass bar):

- Call-count delta vs A1 (expect −847 to −1047 unit calls)
- Discordant PID list restricted to the 16/381 papers whose merged verdict changed in baseline (`00-baseline.md:29-30`)
- Inspect completeness: note 19 review-tier papers losing sub-findings (accepted MODERATE semantics per `SYNTHESIS.md:51`)

**Dual-pod-specific:**

- If `flip_AB` passes but wall_B > 2000 s → infra/scheduling failure, not quality pass
- Optional 20-PID borderline spot check if validating dual-pod **without** HMAC/short-circuit in B (not this bundle)

### 4.3 What we explicitly do not require

- Exact-match (0% flip) — false-rejects inside MoE noise (`47:30-31`)
- Holdout **instead of** fleet A/A calibration (`47:14`)
- Separate B runs per lever when shipping the bundle (`47:16` confound accepted)
- Bit-identical sidecars across pods (`21-dual-pod-sharder.md:16`)

---

## 5. Wall-time cost of the gate itself

| Phase | LLM fleet runs | Post-hoc compute | Total wall |
|-------|----------------|------------------|------------|
| **A/A calibration (fresh)** | 2 × ~50 min | ~10 min | **~110 min** |
| **A/A (weekly A2 cached)** | 1 × ~50 min | ~10 min | **~60 min** |
| **Bundled B + three gates** | 1 × ~50 min | ~10–15 min | **~60–65 min** |
| **Protocol total (fresh A/A)** | 3 × ~50 min | ~20–25 min | **~170–175 min** |
| **Protocol total (cached A2)** | 2 × ~50 min | ~20–25 min | **~120–125 min** |

Gate compute breakdown (~10–15 min, no GPU):

- `--fuse-only` refresh + equivalence diff on 381 sidecars: ~5–10 min
- Dev-replay recall script on 9 PIDs from B sidecars: <1 min
- Holdout anchor scoring on 3 PIDs: <1 min
- McNemar + flip-rate math + artifact write to `_scratch/equiv/<lever-id>/`: ~2 min

Dev-replay pytest (`test_dev_replay_acceptance.py`) is hermetic router logic; **LLM recall is measured from live sidecars**, not that test alone.

---

## 6. Extending to full MODERATE package

MODERATE = CONSERVATIVE (mostly shipped) + short-circuit + **escalation dedupe** + **verdict-first pass schema** + MTP (optional, not in central 596 s).

| Added lever | Isolated B required? | Notes |
|-------------|---------------------|-------|
| Escalation dedupe | Prefer isolated (+50 min) if attribution matters | Touches call multiset (−18 calls) |
| Verdict-first schema | Prefer isolated (+50 min) | Schema/prompt change |
| MTP spec-decode | Server-side; wall + JSON validity during any B | Optional upside 220–470 s; omit from minimum MODERATE gate |

### 6.1 Minimum MODERATE ship (bundled, honest on quality)

Add escalation dedupe + verdict-first into the **same B1** as §4.1 (one `_LANE_VERSION` bump). MTP excluded from minimum bar.

| Path | Fleet runs | Gate compute | **Total wall hours** |
|------|------------|--------------|----------------------|
| **Fresh A/A + bundled MODERATE B** | 3 × 50 min | ~25 min | **~2.9 h (175 min)** |
| **Cached A2 + bundled MODERATE B** | 2 × 50 min | ~25 min | **~2.1 h (125 min)** |

### 6.2 Strict isolated attribution (not minimum wall)

Per `47:16`, call-graph and prompt levers isolated:

`A/A (100 min) + B_hmac (50) + B_shortcircuit (50) + B_dualpod (50) + B_dedupe+schema (50) + gates (4×10)` → **~310 min (~5.2 h)**

Only use when a gate fails and the failing lever must be identified.

---

## 7. Recommended execution order (smallest validation cost)

Aligns with `SYNTHESIS.md:69-83` and HEAD state:

1. **Already shipped, no re-run:** tombstones, LJF, `to_thread`, monolith timeout (scheduling-only; wall check optional).
2. **Implement before B:** HMAC text-lane parity, dual-pod CLI, escalation dedupe, verdict-first schema; operator server flags (APC retention, MBT) applied before B.
3. **A/A once** at ship `_LANE_VERSION` (v12+ if schema/reorder/shard bump).
4. **One bundled MODERATE B** with `--force`.
5. **Three gates** on sidecars; store under `research/tapetum-llm-speedup/_scratch/equiv/moderate-v12/`.
6. **Ship** if all pass; if dev-replay fails, suspect short-circuit inspect regression first (`47:26-27`), not flip rate alone.

---

## 8. False-pass / false-fail guardrails

**False-pass (must be caught by dev-replay, not flip gate):** metadata short-circuit skips unit calls; `suggested_verdict` and fusion stay capped by metadata; fleet flip looks equivalent while `page_content_omission` / `table_corruption` groups disappear from sidecars (`47:26-27`).

**False-fail:** HMAC reorder causes pass↔review churn on ~18/381 papers with unchanged defect multisets — inside A/A band; rejecting forfeits 500–900 s APC savings (`47:30-31`).

**False-fail (infra):** dead twin pod without health gate → error tombstones, not quality regression (`21-dual-pod-sharder.md:28-29`).

---

## 9. Answer: minimum wall hours before shipping MODERATE package

| Scenario | Minimum wall hours |
|----------|-------------------|
| **Bundled protocol, fresh 381-paper A/A** | **~2.9 hours** (175 min) |
| **Bundled protocol, weekly A2 cache valid** | **~2.1 hours** (125 min) |
| **Named three levers only (same bundled B, MTP omitted)** | Same as above |
| Strict per-lever isolation (debug path) | ~5.2 hours — not minimum |

Implementation and operator pod work are excluded; this is **validation wall time only**.

Central MODERATE cold target after pass: **~596 s (9–11 min)** with dual-pod alive (`11-wall-arithmetic.md`); without twin pod, same levers stay **~1490 s** — quality-safe but misses the 10 min goal (`22-path-a-b-10min.md`).

---

## References

- `research/tapetum-llm-speedup/SYNTHESIS.md` §3–§5 (packages, quality gate, execution order)
- `research/tapetum-llm-speedup/47-quality-equivalence.md` (full gate spec)
- `research/tapetum-llm-speedup/17-metadata-short-circuit.md` (Tier A+B policy)
- `research/tapetum-llm-speedup/21-dual-pod-sharder.md` (shard + health)
- `research/tapetum-llm-speedup/45-guard-tag-cryptanalyst.md`, `149-verifier-guard-tag.md` (HMAC)
- `research/cold-run-10min/10-impl-status-auditor.md` (HEAD drift)
- `packages/whisker/corpus/dev-replay/labels.json`, `corpus/holdout/manifest.json`
