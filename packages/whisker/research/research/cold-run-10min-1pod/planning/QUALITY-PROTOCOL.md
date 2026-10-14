# QUALITY-PROTOCOL — Condensed from report 19

**Full source:** [`../19-quality-gate-1pod.md`](../19-quality-gate-1pod.md)  
**Hard constraint:** no second V4-Pro. Dense offload ≠ twin pod.

---

## 1. What “not lying about quality” means

Three tiers; all required to ship AGGRESSIVE (det-metadata + dense unit offload):

| Tier | Corpus | Pass |
|------|--------|------|
| **Fleet flip ceiling** | 381 papers, `--force` cold | `flip_AB ≤ flip_AA + margin` on four-component equivalence vector |
| **Dev-replay recall** | 9 golden PRs, 29 defect groups | `recall_B ≥ recall_A − 0.05` **and** clean papers still match `expected_llm_verdict` |
| **Holdout anchors** | 3 papers, 48 locked anchors | Anchor recall on `expected_candidate_status` non-regressing vs A |

**Equivalence vector** (per PID; all four must match):

1. `suggested_verdict`
2. `fusion.combined_verdict` (after `--fuse-only` refresh)
3. Defect-group multiset keyed by `defect_type` only
4. Coverage tuple `(coverage_complete, unchecked_unit_ids, failed_unit_ids, checked_count, mode, all_pages_requested)`

**Noise margin:**

```
margin = max(0.02, 1.96 × sqrt(flip_AA × (1 − flip_AA) / 381))
```

B passes iff discordant with **both** A runs (tie-break). Secondary: McNemar on paired verdict flips.

---

## 2. Config definitions

| Config | Contents | Expected cold wall |
|--------|----------|-------------------|
| **A** | MODERATE single-pod on `alliance-pod`, S=16: metadata Tier A+B SC, escalation dedupe, verdict-first, HMAC + md-first, server APC/MBT | ~1366–1493 s (~23–25 min) |
| **B** | A + `compare_metadata_outline()` (no metadata LLM) + unit checks → `h200-qwen3-32b` (8 oversize → MoE) + scoped payloads + `_LANE_VERSION` bump | ~585–715 s (~10–12 min) if dense live |

Router `combo_safe` may co-bundle in B (wall margin); not required for correctness gate. Det-metadata and dense **must** share one bundled B when shipping for minimum wall (attribution confounded; OK for ship).

---

## 3. Checklist — Pre-B (blocks false-fail)

- [ ] Payload scoping landed (~10–15k/unit)
- [ ] Dense routing + MoE oversize fallback wired
- [ ] `compare_metadata_outline()` replaces metadata LLM path
- [ ] Dense health: `GET` on `h200-qwen3-32b` → **HTTP 200**, model id match
- [ ] Confirm 8-paper MoE fallback (exceed 131k × 0.80)
- [ ] `/metrics` or `call_timings[]` can show dense vs MoE `pod_id` split
- [ ] Optional: offline replay of det-metadata vs v10 sidecars on 381; if >5% disagree **and** any fused verdict would change → fix comparator first

---

## 4. Checklist — A/A (once per `_LANE_VERSION` regime)

- [ ] **A1:** full 381 cold, MODERATE, `--force`, ship `_LANE_VERSION` (~23–25 min)
- [ ] **A2:** identical flags, **or** weekly cached A2 at same lane/image/`SERVICES.toml` (~−25 min)
- [ ] Compute `flip_AA` + discordant PID list (~10 min)
- [ ] **Do not** use warm fingerprint skip for equivalence
- [ ] **Do not** calibrate A/A on v10 3003 s baseline (confounds v11 MODERATE cuts)

---

## 5. Checklist — Bundled B + gates

- [ ] **B1:** one `--force` AGGRESSIVE run (~10–12 min if infra up)
- [ ] Post-hoc gates on sidecars (~10–15 min, no extra LLM fleet):
  - [ ] `--fuse-only` + equivalence diff → `flip_AB`
  - [ ] Dev-replay recall on 9 PIDs from live sidecars
  - [ ] Holdout scoring on 3 PIDs / 48 anchors
  - [ ] Store under `research/tapetum-llm-speedup/_scratch/equiv/aggressive-1pod-v<N>/`
- [ ] Worksheet:

```
PASS flip   iff flip_AB ≤ flip_AA + margin
PASS recall iff recall_B ≥ recall_A − 0.05 AND clean expected_llm_verdict OK
PASS holdout iff holdout_B ≥ holdout_A
wall_B ≤ 620 s  → may claim 10 min goal
wall_B > 720 s  → quality may still pass; 10 min missed
```

---

## 6. Checklist — Secondary metrics (report, not alternate pass bar)

**Det-metadata:**

- [ ] Metadata LLM call count = **0** on B1
- [ ] Discordant list where metadata component alone differs
- [ ] PDF lane watch: page-1 prose as `missing_sections`

**Dense offload:**

- [ ] Routing ~1510 dense / ~8 MoE / 0 mis-routed oversize
- [ ] Inspect 16/381 verdict-changing papers for false-clear
- [ ] Unit-lane call-count delta vs A1

---

## 7. Explicitly not required

- Exact-match 0% flip
- Strict 381/381 identical fused verdicts as primary bar (debug aspiration only)
- Holdout instead of fleet A/A
- Separate B per lever for minimum-wall ship
- ≤600 s as a quality tier (wall is secondary)
- Dual-pod / twin revival

---

## 8. Gate wall budget (validation only)

| Scenario | Total wall |
|----------|------------|
| Fresh A/A + bundled B | **~0.8–1.2 h** (71–76 min fresh; 46–51 min with cached A2) |
| Strict per-lever isolation (debug) | ~1.8 h — only if a gate fails |

Implementation and ops pod restart are **excluded** from these hours.

---

## 9. Failure triage (first suspects)

| Symptom | Suspect first |
|---------|---------------|
| Dev-replay recall drop, fleet flip OK | Dense false-clear (`page_content_omission`) |
| Metadata defect groups vanish | Det-metadata PDF false-fail |
| Flip rises inside A/A band on defect multisets | Dense false-fail on wording markup (avoid Gemma) |
| Error tombstones | Dead dense pod / missing health gate |

**Ship rule:** three quality tiers pass → ship for fidelity even if wall_B ≈ 715 s. Do **not** claim ≤600 s unless measured B1 ≤ 620 s.
