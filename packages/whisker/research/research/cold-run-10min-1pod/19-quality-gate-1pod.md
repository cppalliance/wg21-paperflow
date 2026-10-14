# 19 - Quality gate protocol (1-pod AGGRESSIVE: dense-offload + deterministic metadata)

**Verdict:** usable-with-conditions — ship the AGGRESSIVE 1-pod package (deterministic metadata diff + dense-judge unit offload on `alliance-pod` + live dense pod) only through a two-run A/A noise floor at MODERATE single-pod baseline, one bundled `--force` B run, and three post-hoc gates; quality pass does **not** imply ≤600 s wall (realistic B run **~715 s**).

**Confidence:** high (adapted from `research/cold-run-10min/25-quality-gate-protocol.md`, `47-quality-equivalence.md`, `10-impl-status-1pod.md`, `22-path-a-b-10min.md`)

**Hard constraint:** No second DeepSeek-V4-Pro pod (`research/cold-run-10min-1pod/00-baseline.md`). Dual-pod shard, twin health probes, and `h200x8-deepseek-v4-pro` are **out of scope**.

**Sources:** `25-quality-gate-protocol.md` (2026-07-24), persona 47, persona 131, persona 23, `16-dense-judge-candidates.md`, `10-impl-status-1pod.md`.

---

## 1. What “not lying about quality” means

Same three tiers as `25-quality-gate-protocol.md` §1, unchanged contract:

| Tier | Corpus | Pass criterion | Catches |
|------|--------|----------------|---------|
| **Fleet flip ceiling** | 381 papers, `--force` cold | `flip_AB ≤ flip_AA + margin` on the **four-component equivalence vector** | Verdict churn inside MoE noise; silent defect-type drops |
| **Dev-replay recall** | 9 golden PRs, 29 labeled defect groups | `recall_B ≥ recall_A − 0.05` AND clean papers still match `expected_llm_verdict` | Short-circuit / dense false-pass: verdict unchanged, localized findings vanish |
| **Holdout anchor recall** | 3 papers, 48 locked anchors | Anchor-level recall on `expected_candidate_status` non-regressing vs A | Evidence-grounding regressions on frozen candidates |

**Equivalence vector per PID** (all four must match for “equivalent”):

1. `suggested_verdict`
2. `fusion.combined_verdict` (after deterministic `--fuse-only` refresh)
3. Defect-group multiset keyed by `defect_type` only (ignore quotes / null `verified_count`)
4. Coverage tuple `(coverage_complete, unchecked_unit_ids, failed_unit_ids, checked_count, mode, all_pages_requested)`

**Noise floor:** identical config A1 vs A2 on full 381 corpus establishes `flip_AA`. Default margin:

`max(0.02, 1.96 × sqrt(flip_AA × (1 − flip_AA) / 381))`

Candidate B passes iff discordant with **both** A runs (tie-break). Secondary: McNemar on paired verdict flips.

Measure `flip_AA` on 381 once at current ship `_LANE_VERSION`. The documented ≥25% flip on 20 borderline PIDs is **not** the fleet gate (`150-verifier` correction).

---

## 2. Lever classification (AGGRESSIVE 1-pod delta)

**Config A (baseline for this gate):** MODERATE stack on **single** `alliance-pod`, S_eff = 16 — metadata Tier A+B short-circuit, escalation dedupe, verdict-first pass schema, HMAC + md-first (PDF + text), server APC/MBT flags. Expected cold wall **~1366–1493 s (~23–25 min)** per run (`10-impl-status-1pod.md`, `22-path-a-b-10min.md` Path B).

**Config B (AGGRESSIVE 1-pod bundle):** A + the two named levers below. Router `combo_safe` is **recommended** in the same B run for wall margin but **not required** for this quality protocol when the ship goal is correctness, not ≤600 s.

| Lever | Changes call graph? | Changes LLM inputs? | Exempt from full 381? | Gate tiers |
|-------|---------------------|---------------------|----------------------|------------|
| **Deterministic metadata diff** | Yes (−377 MoE metadata LLM calls) | Yes (LLM → `compare_metadata_outline()`) | **No** | Fleet + dev-replay + holdout |
| **Dense-judge unit offload** | Yes (1510 unit calls → dense pod; 8 oversize → MoE fallback) | Yes (model family swap on unit lane) | **No** | Fleet + dev-replay + holdout |
| **Router combo_safe** (optional co-bundle) | Yes (−~63 unit selections post-short-circuit) | No (routing only) | **No** | Same B run if bundled; confound accepted |

**Bundling rule (`47:16-17`):** deterministic metadata and dense offload **must not** be validated in separate isolated fleet runs when the goal is minimum wall time — one B run carries both. Failure attribution is confounded; acceptable for ship, not for debugging.

**HEAD note (`10-impl-status-1pod.md`):** neither lever is implemented at HEAD. Protocol assumes: payload scoping landed, dense routing + MoE fallback wired, `compare_metadata_outline()` replaces `run_metadata_outline_check` LLM path, then validate the bundle.

**Dense offload is not “second pod.”** Second pod = second identical DeepSeek-V4-Pro replica (blocked). Dense offload = route unit checks to an **already-running** dense endpoint (`h200-qwen3-32b` primary anchor; `b300-qwen36-27b`, `b200x2-gemma4`, `b200-r1` alternates). Monolith, page escalations, and oversize payloads stay on `alliance-pod` MoE (`16-dense-judge-candidates.md`).

---

## 3. Minimal A/A protocol (once per `_LANE_VERSION` regime)

**Critical 1-pod adaptation:** A runs are **MODERATE single-pod (~25 min)**, not v10 baseline (~50 min). Measuring A/A at 3003 s v10 confounds MODERATE call cuts already shipped in v11.

| Step | Command shape | Wall time |
|------|---------------|-----------|
| **A1** | Full 381 cold, MODERATE single-pod, `--force`, `_LANE_VERSION` = ship target | **~23–25 min** (~1366–1493 s) |
| **A2** | Repeat A1 identical flags | **~23–25 min** |
| **Compute** | Equivalence vector diff A1↔A2 → `flip_AA`, store discordant PID list | ~10 min |

**Operational shortcut (`47:16`):** reuse a **weekly refreshed A2** from `research/tapetum-llm-speedup/_scratch/aa-baseline/` at MODERATE single-pod config → skip second live run (**−~25 min**). Valid only if same `_LANE_VERSION`, `alliance-pod` image, dense pod contract, and `SERVICES.toml`.

**Do not** use warm fingerprint skip for equivalence measurement (`47:16`).

**Pre-B offline check (optional, not counted in gate wall, reduces rework):** replay `compare_metadata_outline()` against v10 stored `metadata_outline_check` on all 381 sidecars (~5 min GPU-free). If >5% disagree **and** any fused verdict would change (`131-surya-model-sizing.md:32`), fix deterministic comparator before fleet B.

---

## 4. Minimal A/B protocol (deterministic metadata + dense offload)

### 4.1 Single bundled B (recommended minimum)

| Step | Config B contents | Wall time |
|------|-------------------|-----------|
| **B1** | MODERATE A + `compare_metadata_outline()` (no metadata LLM) + unit checks routed to `h200-qwen3-32b` (MoE fallback for 8 oversize papers per `23-small-judge-evaluator.md`) + scoped payloads + `_LANE_VERSION` bump + dense service in fingerprint | **~10–12 min** (~585–715 s central; `10-impl-status-1pod.md` table) |
| **Gates** | Post-hoc on B1 sidecars (no extra LLM) | ~10–15 min |

**Pre-flight (not counted in gate wall, but blocks false-fail):**

- Dense pod health probe on `h200-qwen3-32b` (HTTP 200, model id match)
- Confirm 8-paper MoE fallback routing (papers exceeding 131k × 0.80 margin)
- `/metrics` or sidecar `call_timings[]`: unit calls show `pod_id` dense vs MoE split

### 4.2 Pass/fail worksheet

```
flip_AB   = fraction of 381 PIDs not equivalent to A1 (and flagged vs A2)
PASS flip  iff flip_AB ≤ flip_AA + margin

recall_A, recall_B = dev-replay defect-group hits / 29
PASS recall iff recall_B ≥ recall_A − 0.05 AND expected_llm_verdict unchanged on clean papers

holdout_B ≥ holdout_A  (48 anchors, locked candidate SHA-256)

wall_B ≤ 620 s  →  upgrade Path B AGGRESSIVE to ✅ for 10 min goal (22-path-a-b-10min.md:191)
wall_B > 720 s with friction  →  quality pass still possible; 10 min goal missed (plan ~715–910 s)
```

**Deterministic-metadata secondary metrics** (report, not alternate pass bar):

- Metadata LLM call count = **0** on B1 (377 eliminated)
- Discordant PID list where metadata component alone differs (expect near-zero if offline replay passed)
- PDF lane false-fail watch: page-1 prose registered as `missing_sections` (`131:28-29`)

**Dense-offload secondary metrics** (report, not alternate pass bar):

- Unit call routing: ~1510 dense, ~8 MoE fallback, 0 mis-routed oversize
- Inspect 16/381 verdict-changing papers (`00-baseline.md:29-30`) for false-clear (P0957R8-class localized omission, `23-small-judge-evaluator.md:24`)
- Call-count delta vs A1 on unit lane only

**Optional router co-bundle:** if `combo_safe` included in B1, report 6/47 defect-group papers at risk (`50-router-false-economy.md`); router FN is independent of dense gate.

### 4.3 What we explicitly do not require

- Exact-match (0% flip) — false-rejects inside MoE / dense noise (`47:30-31`)
- Persona 23’s strict **381/381 identical fused verdicts** as the primary bar — use four-component equivalence + `flip_AA` margin (`47`); 381/381 is a debug aspiration, not the ship gate
- Holdout **instead of** fleet A/A calibration (`47:14`)
- Separate B runs per lever when shipping the bundle (`47:16` confound accepted)
- ≤600 s wall as a quality gate — wall is a **secondary success metric**, not a tier-1 pass criterion
- Dual-pod shard or twin pod revival

---

## 5. Wall-time cost of the gate itself

Per-run durations use **single-pod** arithmetic (`S_eff = 16`). Dual-pod ~50 min runs from `25-quality-gate-protocol.md` do **not** apply.

| Phase | LLM fleet runs | Post-hoc compute | Total wall |
|-------|----------------|------------------|------------|
| **A/A calibration (fresh)** | 2 × ~25 min | ~10 min | **~60 min** |
| **A/A (weekly A2 cached)** | 1 × ~25 min | ~10 min | **~35 min** |
| **Bundled B + three gates** | 1 × ~11 min | ~10–15 min | **~21–26 min** |
| **Protocol total (fresh A/A)** | 2 × ~25 + ~11 min | ~20–25 min | **~71–76 min** |
| **Protocol total (cached A2)** | 1 × ~25 + ~11 min | ~20–25 min | **~46–51 min** |

Gate compute breakdown (~10–15 min, no GPU):

- `--fuse-only` refresh + equivalence diff on 381 sidecars: ~5–10 min
- Dev-replay recall script on 9 PIDs from B sidecars: <1 min
- Holdout anchor scoring on 3 PIDs: <1 min
- Metadata offline replay diff (if not done pre-B): ~5 min
- Dense routing audit + McNemar + artifact write to `_scratch/equiv/aggressive-1pod-v<N>/`: ~2 min

Dev-replay pytest (`test_dev_replay_acceptance.py`) is hermetic router logic; **LLM recall is measured from live sidecars**, not that test alone.

---

## 6. Relationship to full AGGRESSIVE 1-pod package

Full AGGRESSIVE per `SYNTHESIS.md` §3 adds **router combo_safe** on top of metadata diff + dense offload. Router changes call multiset (−~63 selections scaled post-short-circuit) and carries 6/47 defect-group FN risk.

| Added lever | Isolated B required? | Notes |
|-------------|---------------------|-------|
| Router combo_safe | Prefer isolated (+~25 min) if attribution matters | **−~80–130 s** wall; bundle in same B1 for minimum wall |
| Payload scoping alone | N/A (prerequisite, not shippable delta) | Without scoping, dense pod reverts to L≈20 s, negative EV (`105`) |
| Verdict-first (if not already in A) | Already in MODERATE A | Must be in config A before AGGRESSIVE B |

### 6.1 Minimum AGGRESSIVE 1-pod ship (dense + metadata, honest on quality)

One `_LANE_VERSION` bump. Router optional in same B1 (zero marginal fleet wall if bundled).

| Path | Fleet runs | Gate compute | **Total wall hours** |
|------|------------|--------------|----------------------|
| **Fresh A/A + bundled B** | 2 × ~25 min + ~11 min | ~25 min | **~1.2 h (71–76 min)** |
| **Cached A2 + bundled B** | 1 × ~25 min + ~11 min | ~25 min | **~0.8 h (46–51 min)** |

### 6.2 Strict isolated attribution (not minimum wall)

Per `47:16`, call-graph levers isolated on single pod:

`A/A (~50 min) + B_metadata_only (~15 min at ~920 s) + B_dense_only (~25 min MODERATE+dense) + gates (3×10)` → **~105–110 min (~1.8 h)**

Only use when a gate fails and the failing lever must be identified. Metadata-only B is shorter than dense-only B because metadata diff removes 377 calls before dense routing changes unit latency.

---

## 7. Recommended execution order (1-pod corpus)

Aligns with `10-impl-status-1pod.md` and `00-baseline.md`:

1. **Confirm config A:** cold MODERATE single-pod run on working-tree v11; expect **~21–25 min**, not 48 min.
2. **Implement before B:** payload scoping → dense routing + MoE fallback → `compare_metadata_outline()` → optional router combo_safe.
3. **A/A once** at ship `_LANE_VERSION` (v12+ when sidecar shape or routing changes).
4. **Optional offline metadata replay** on v10 sidecars (5 min).
5. **One bundled AGGRESSIVE B** with `--force`; dense pod probed pre-gather.
6. **Three gates** on sidecars; store under `research/tapetum-llm-speedup/_scratch/equiv/aggressive-1pod-v<N>/`.
7. **Ship** if all tiers pass; if dev-replay fails, suspect dense false-clear first (`23:24`), then metadata PDF false-fail (`131:28`).

Implementation and operator pod work are **excluded**; this section is **validation wall time only**.

---

## 8. False-pass / false-fail guardrails

**False-pass (dense):** unit checks on `h200-qwen3-32b` return zero defects on hard conversion-fidelity rubrics while MoE would emit `candidate_not_found`; fleet flip gate passes because verdict was already capped, dev-replay recall on `page_content_omission` drops (`23:24`, `47:26-27`).

**False-pass (metadata):** deterministic diff marks date/review fields pass while LLM would review; fusion unchanged on verdict-only vector but metadata defect groups vanish. Holdout + metadata-component discordant list catches.

**False-fail (dense):** Gemma/Qwen mis-reads sanctioned wording markup → spurious structure defects on clean papers; flip rate rises inside A/A band (`23:28`). Do not reject unless discordant **defect multisets** change, not verdict churn alone.

**False-fail (infra):** dead dense pod without health gate → error tombstones, not quality regression. MoE fallback for 8 oversize must not route to truncated dense context.

**False-fail (expectations):** quality pass with wall_B ≈ 715 s is **honest success** for advisory fidelity but **not** 10 min. Do not block ship on wall alone if three tiers pass; do not claim ≤600 s without measured B1 ≤620 s.

---

## 9. Answer: minimum wall hours before shipping AGGRESSIVE 1-pod package

| Scenario | Minimum wall hours |
|----------|-------------------|
| **Bundled protocol, fresh MODERATE A/A** | **~1.2 hours (71–76 min)** |
| **Bundled protocol, weekly A2 cache valid at MODERATE single-pod** | **~0.8 hours (46–51 min)** |
| **Named two levers only (dense + deterministic metadata, router omitted)** | Same as above |
| Strict per-lever isolation (debug path) | **~1.8 hours (105–110 min)** — not minimum |

Implementation (payload scoping, routing, deterministic comparator) is excluded; this is **validation wall time only**.

Central AGGRESSIVE 1-pod cold target after pass: **~585–715 s (10–12 min)** with dense pod alive (`10-impl-status-1pod.md`); pessimistic friction **~715–910 s** — quality-safe but may miss the 600 s goal (`22-path-a-b-10min.md` Path B). Unlike dual-pod MODERATE (~596 s), AGGRESSIVE 1-pod is a **hairline maybe**, not a planning-grade ≤600 s guarantee.

---

## References

- `research/cold-run-10min/25-quality-gate-protocol.md` (parent protocol; dual-pod MODERATE)
- `research/cold-run-10min-1pod/00-baseline.md`, `10-impl-status-1pod.md`
- `research/tapetum-llm-speedup/47-quality-equivalence.md`
- `research/tapetum-llm-speedup/131-surya-model-sizing.md` (deterministic metadata)
- `research/tapetum-llm-speedup/23-small-judge-evaluator.md` (dense gate)
- `research/cold-run-10min/16-dense-judge-candidates.md`, `22-path-a-b-10min.md`
- `research/cold-run-10min/51-determinism-risk-matrix.md` (rows 21–22)
