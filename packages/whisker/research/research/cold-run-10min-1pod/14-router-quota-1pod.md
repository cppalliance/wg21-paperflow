# 14 - Router + dynamic MAX_UNIT_CHECKS (single pod)

**Verdict:** usable-with-conditions — a **paired** dynamic cap + router tightening can safely reclaim **~150–220 calls (~5–7% of pre-v11 fleet, ~12–17% of post-v11 survivors)** on one pod; it **cannot** erase the full **~289-call (~12%)** fusion-dead band without risking the **3/381** unit-cap-driver papers and inspect detail on the broader **16/381** LLM-flip set.
**Confidence:** medium-high (sidecar replay + code paths from v10/v11; post-v11 rescale modeled, not replayed on fresh fleet)

**Sources:** `research/cold-run-10min/50-router-false-economy.md`, `research/cold-run-10min/58-max-unit-checks-knob.md`, `research/cold-run-10min/70-fusion-verdict-influence.md`, `research/tapetum-llm-speedup/11-router-precision-auditor.md`, `research/cold-run-10min-1pod/00-baseline.md`.

**Hard constraint:** `S_eff = 16` only. No twin pod. Dual-pod savings are out of scope.

---

## Executive answer

| Option | Expected call cut (post-v11 survivors) | Wall @ S=16 | Quality risk |
|--------|----------------------------------------:|------------:|--------------|
| **Router combo_safe only** | **~63 calls** (~2.7% of v10 fleet) | **~79 s** | **MEDIUM** — **6/47** defect-group papers lose unit evidence; merged verdict unchanged on replay |
| **Static cap 3** (no router retune) | **~220 calls** (663-survivor rescale) | **~275 s** | **MEDIUM–HIGH** — recall loss on saturated PDFs; fusion stays fail-closed (`review`), not silent `pass` |
| **Dynamic quota (recommended)** | **~132–220 calls** (60–80% of cap-3 on survivors) | **~165–275 s** | **LOW–MEDIUM** — preserves table/severity floors; still needs holdout A/B |
| **Combined dynamic + combo_safe** | **~150–250 calls** (non-additive; overlap ~15–30 calls) | **~190–310 s** | **MEDIUM** — gate on **3/381** cap drivers + **16/381** equivalence vector |
| **Blind cut of all 289 fusion-dead calls** | 289 (upper bound) | ~361 s | **HIGH** — includes cap-locked checks that decorate inspect and occasional rescue/clear inputs |

**Return line:** expect **~150–220 calls (~5–7% fleet)** safely cut on one pod; **~12% (~289 calls) is not fully harvestable** without A/B-proven zero regression on the **3/381** unit-cap set and dev-replay recall.

---

## Problem framing (post-v11, one pod)

After metadata short-circuit (v11), the survivor mix is **~1298 LLM calls** (378 monolith + 378 metadata + **523 unit** + 18 escalation + 1 ideal). The residual waste band documented in persona **50** is:

| Waste class | Calls | Share of v10 fleet (2345) | Share of survivors (1298) |
|-------------|------:|--------------------------:|--------------------------:|
| Metadata fusion-dead (eliminated v11) | 1047 | 44.6% | — |
| **Cap-locked pass-tier units + refuted escalations** | **~289** | **~12.3%** | **~22.3%** |
| Router combo_safe trimmable (scaled) | ~63 | ~2.7% | ~4.9% |
| Zero-defect survivors (not all fusion-dead) | ~365 | ~15.6% | ~28.1% |

On a single pod, **289 × 20/16 ≈ 361 s** is the **upper-bound wall** if every fusion-dead survivor call were removable. Persona **70** narrows quality exposure:

- **16/381 (~4.2%)** — any LLM-driven **merged** verdict change (9 `llm_rescue_heading`, 7 `llm_clear_soft_review`).
- **3/381 (~0.8%)** — unit **accepted defect_groups** drove `source_aware_review_cap` (the unit-only merged flip set).

Speed levers on units must track **both** sets: the **16** for fleet equivalence (`25-quality-gate-protocol.md`), the **3** for defect-group recall on cap-driver papers.

---

## Design A — dynamic MAX_UNIT_CHECKS

Static **5→3** treats every paper identically; **179/180 PDFs** already saturate cap 5 (`58`). The bug is **scheduling**, not the number five (`SIGNAL_CLASS_QUOTA` + signal over-fire).

### Proposed policy (fleet mode only)

Replace fixed `MAX_UNIT_CHECKS = 5` with a per-paper function before `_select_units_with_quotas` (`unit_judge.py:175-213`, `378-381`):

```python
def fleet_max_unit_checks(
    routable_risky_ids: list[str],
    signals_by_unit: dict[str, list[RiskSignal]],
    *,
    base: int = 3,
    ceiling: int = 7,
) -> int:
    signals = [s for ss in signals_by_unit.values() for s in ss]
    bump = 0
    if any(s.severity in {"critical", "high"} for s in signals):
        bump += 1
    if any(s.signal_type == "table_presence" for s in signals):
        bump += 1
    if len(routable_risky_ids) > 8:
        bump += 1
    return min(ceiling, base + bump)
```

**Invariants preserved:**

- `--inspect` / `--exhaustive-units` / `--all-pages` still bypass cap (`unit_judge.py:335-337`, `cli.py:309`).
- Unroutable pre-filter unchanged (`unit_judge.py:370-381`).
- Fail-closed: overflow → `unchecked_unit_ids` → `coverage_complete=false` → fusion cap (`fusion.py:192-196`).

### Expected savings (modeled on v10 sidecars, rescaled to v11 survivors)

| Cohort | Cap-5 today | Dynamic (base 3) | Δ calls |
|--------|------------|------------------|--------:|
| PDF saturated (179 papers @ 5) | 895 | ~537–716 (3–4 avg) | **−179 to −358** raw |
| HTML median 4 | ~614 total | ~460–537 | **−77 to −154** raw |
| **Post-metadata survivor scale** (663/1510 unit share) | 523 | **~303–391** | **−132 to −220** |

Wall: **ΔN × 20/16** → **~165–275 s** on one pod.

**Hypothesis (60–80% of cap-3 savings):** table/severity bumps recover PR #286-class pages (poll tables on 8–9) while zero-yield slots 4–5 on clean saturated PDFs drop away.

**Risk vs static cap 3:** at `max_checks=3`, quota phase can consume **all three slots** on signal-class diversity alone (`58` H3). Dynamic bumps to 4–5 when `table_presence` or high severity present avoids that failure mode on table-defect papers.

---

## Design B — router tightening (combo_safe + hygiene)

Router waste beyond metadata is **selection quality**, not extra call volume (`50`). `_select_units_with_quotas` has no fusion awareness (`unit_judge.py:175-213`).

### Tier 1 — zero-LLM hygiene (ship first)

1. **Do not emit `heading_drift`** when `unit_text_map[unit_id]` is empty (`source_router.py:285-312`). Complements existing unroutable pre-filter; stops signal noise (`50` ranked cut #2).

### Tier 2 — combo_safe (holdout-gated)

Simulated on 381 v10 sidecars (`11-router-precision-auditor.md`):

| Filter | Effect |
|--------|--------|
| One `table_presence` per paper (first table page) | Cuts redundant table slots |
| Drop PDF `heading_drift` with `detail` >120 chars containing `large-font` | Targets prose mis-extraction noise (PR286 class) |
| `SECTION_RECALL_FLOOR` 0.90→0.85 | **~16 signals**; **5/16** checked units had defects |

**Full combo_safe:** **190/1634 routed selections (11.6%)** on v10; post-v11 scale **190 × (523/1570) ≈ 63 calls**, **~79 s @ S=16**.

**Quality:** **6/47** defect-group papers lose unit-level evidence; merged verdict unchanged on replay (`11`). Multi-table papers (P4025R1/R2) are the FN shape.

### Tier 3 — quota retune (pairs with dynamic cap)

Adjust phase-1 `SIGNAL_CLASS_QUOTA` walk order:

1. Reserve **`table_presence`** and **`low_recall`** before **`heading_drift`** when `max_checks ≤ 4`.
2. Optional: **`SIGNAL_CLASS_QUOTA = 0`** for `heading_drift` when `table_presence` exists on the same paper (reclaim slot for table page).

Not measured separately in sidecar replay; treat as **quality fix** that may **add** calls on table papers while enabling lower `base` elsewhere.

---

## Design C — optional static cap 3

Persona **58** recommendation order: **keep 5** → **try 3 with A/B** → **prefer dynamic quota**.

| Metric | Cap 3 on survivors (663-scale) |
|--------|-------------------------------|
| Δ calls | **~−220 central** (−382 to −550 on full fleet) |
| Δ wall @ S=16 | **~−275 s central** |
| Overlap with metadata short-circuit | **High** — not additive with −1059 s metadata cut |
| Single-pod MODERATE remainder | Cuts **~282 s** if naively stacked on MODERATE+dual math; here **~275 s** on one pod only |

**Use cap 3 as A/B experiment**, not production default, unless holdout proves equivalence (`58` protocol).

---

## Combined lever model (single pod, S=16)

Post-v11 starting wall (modeled): **~1672–1944 s** (~28–32 min) after metadata short-circuit (`50`, `1pod/00-baseline`).

```
N_survivor_units ≈ 523
N_fusion_dead    ≈ 289   (22.3% of 1298 survivors — not all safely removable)

Safe harvest band:
  router_combo_safe     ≈  63 calls   (~ 79 s)
  dynamic_quota_net     ≈ 132–220 calls (~165–275 s)
  overlap               ≈  15–30 calls (table papers hit by both)
  combined_central      ≈ 150–250 calls (~190–310 s)
```

**Gap to ≤600 s:** even **−310 s** leaves **~1360–1630 s** on one pod. Router/quota is a **third-tier N cut**, not a substitute for decode shrink, dense-judge offload, or prefix cache (`1pod/00-baseline`).

Do **not** sum cap-3 + combo_safe + metadata naively (`58` stacking note).

---

## Quality risk matrix: 16/381 vs 3/381

| Set | Count | What moves | Risk from unit cuts |
|-----|------:|------------|---------------------|
| **16/381** | 4.2% | Merged LLM delta (rescue + clear) | **MEDIUM** for fleet equivalence — most flips are **not** unit-sourced; stripping zero-defect unit checks unlikely to change **16** merged outcomes if monolith/metadata unchanged (`70`) |
| **3/381** | 0.8% | Unit **accepted defect_groups** → fusion cap | **HIGH** — primary gate for dynamic cap + combo_safe; losing a cap-driver group is silent at merged layer only if monolith already `review` |
| **321/381** | 84% | Fusion capped before clear/rescue | Unit spend mostly **inspect decoration** — safe to cut for merged verdict, loses operator quotes |
| **6/47** | defect-group papers | combo_safe FN | Inspect false-clear appearance; merged unchanged in replay |

### Gate protocol (required before ship)

From `25-quality-gate-protocol.md` + `58` cap-3 protocol:

1. **Fleet A/A** on 381 → `flip_AA` noise floor.
2. **Candidate B** = dynamic quota + combo_safe (or cap 3 alone for experiment).
3. **Pass iff:** four-component equivalence vector discordant with **both** A runs; `flip_AB ≤ flip_AA + margin`.
4. **Stratified must-not-regress:**
   - All **16/381** discordant PIDs reviewed (not just pass rate).
   - **3/381** cap-driver papers: defect-group multiset unchanged.
   - **48 holdout anchors**: non-regressing recall.
   - **9 dev-replay PRs**: `recall_B ≥ recall_A − 0.05`.
5. **Acceptable trade:** higher `review` from coverage cap if **zero new `pass`** on anchor blockers.

### False-pass hypothesis

Dynamic cap **3** on a metadata-pass paper with table cell swap on page 9: router emits `table_presence` on 8–9 plus three `heading_drift` on 1–3; without table-first quota retune, page 9 stays unchecked; monolith/metadata pass; fusion → **`review`** via incomplete coverage — **not silent `pass`** unless operator ignores cap (`58`). **combo_safe** on P4025R1/R2: later corrupted table pages skipped; unit checks pass empty; monolith still `review` — **inspect** false-clear.

### False-fail hypothesis

Uniform cap 3 on clean 15-page PDFs: **179 papers lose 2 checks** → more `source_aware_review_cap` **review** noise without new defect groups (`58` H1). Operators treat advisory `review` as shippable → effective false-fail.

---

## Implementation sketch (minimal diff)

| Step | Location | Change |
|------|----------|--------|
| 1 | `constants.py` | `FLEET_UNIT_CHECK_BASE = 3`, `FLEET_UNIT_CHECK_CEILING = 7`; keep `MAX_UNIT_CHECKS = 5` as ceiling alias for tests |
| 2 | `unit_judge.py` | `fleet_max_unit_checks(...)`; pass result as `max_checks` when not `exhaustive` |
| 3 | `source_router.py` | Skip `heading_drift` on empty packets; combo_safe filters behind `_LANE_VERSION` flag |
| 4 | `unit_judge.py` | Optional quota walk: table/low_recall before heading_drift |
| 5 | Sidecar | Persist `unit_selection.max_checks_dynamic` for A/B audit |
| 6 | Tests | Holdout replay fixtures; PR286 routing case; cap-3 quota exhaustion case |

**`_LANE_VERSION` bump** mandatory. No ship on wall alone.

---

## Findings

- [CRITICAL] **The ~12% residual is 289 fusion-dead survivor calls, not a second metadata class.** Evidence: `50` (1332 − 1043 = 289 on cap-locked pass tier). Impact: **~361 s upper bound @ S=16**; realistic safe harvest **~190–310 s**.

- [CRITICAL] **16/381 ≠ unit verdict influence; 3/381 is the unit-cap gate.** Evidence: `70` (9 rescue + 7 clear vs 3 cap-driver defect groups). Impact: A/B must stratify **3** papers for recall, **16** for merged equivalence.

- [HIGH] **Dynamic quota beats static cap 3 for the same wall band.** Evidence: `58` proposed policy + H3 quota interaction. Impact: **~132–220 calls** with table/severity floors vs blind **−2 slots** on 179 PDFs.

- [HIGH] **Router combo_safe is ~63 calls (~79 s) with bounded 6/47 FN.** Evidence: `11`, scaled in `50`. Impact: **MODERATE** trim; pair with dynamic cap, not substitute.

- [HIGH] **70% zero-defect unit checks (~365/523 survivors) fund the economic target, but the 16 flip papers hide in the tail.** Evidence: `50`, `58` H4. Impact: sidecar replay must tag **check index 1–5** on flip papers before claiming slots 4–5 are always safe.

- [MED] **Single-pod 10 min still needs ~800–900 s beyond MODERATE after metadata.** Evidence: `1pod/00-baseline`. Impact: router/quota closes **~3–5%** of original fleet calls — necessary but insufficient alone.

- [MED] **SIGNAL_CLASS_QUOTA at cap 3 can consume entire budget on diversity.** Evidence: `58` H3, six router classes. Impact: dynamic bump + table-first walk required before shipping base=3.

- [LOW] **Timeout headroom drops with lower cap** (`cli.py` `(1+MAX_UNIT_CHECKS)×120`). Impact: cap 3 saves per-paper timeout budget; irrelevant to mean cold wall.

---

## Recommendation (single pod)

1. **Implement dynamic quota (base 3, ceiling 7)** with table/severity/routable-count bumps — do **not** permanently ship static cap 3.
2. **Ship Tier-1 router hygiene** (empty-packet `heading_drift`) immediately — zero LLM risk.
3. **A/B combo_safe + dynamic quota** as one bundle; gate on **3/381 + 16/381 + 48 anchors + dev-replay**.
4. **Expect ~150–220 calls cut (~190–310 s @ S=16)** if gates pass — **not** full 289.
5. **Optional cap-3-only experiment** for sensitivity; use results to tune bump thresholds, not as fleet default.

---

## What would change my mind

1. Fresh v11 sidecar replay tagging check slots **4–5** on all **16** merged-flip papers as zero-defect → upgrade safe cut toward **~250 calls**.
2. Holdout replay showing combo_safe **0/47** FN on defect-group papers → upgrade router trim to CONSERVATIVE.
3. Dynamic quota A/B with **381/381 equivalence** and **unchanged 3/381 defect groups** → ship as MODERATE single-pod lever alongside decode/prefix work.
