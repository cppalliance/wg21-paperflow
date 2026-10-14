# 58 - MAX_UNIT_CHECKS Knob (5 vs 3)

**Verdict:** usable-with-conditions — **keep 5 as fleet default**; **try 3 only behind a holdout A/B**; **prefer dynamic quota** over a permanent cap cut for speed.
**Confidence:** medium-high (call census and cap-saturation measured; cap-3 savings are modeled, not replayed)

## Executive answer

| Option | Wall impact (3003 s baseline) | Quality risk | Recommendation |
|--------|------------------------------|--------------|----------------|
| **Keep 5** | 0 s (status quo) | Lowest — current fail-closed contract | **Default for production fleet** |
| **Cap 3 (A/B)** | **~−503 s central** @ S=16 (**~−251 s** @ S=32 dual-pod) | **MEDIUM–HIGH** on defect recall; **LOW** on silent false-pass (fusion caps) | **Run once** on 381-paper cold + 48-anchor holdout; ship only if flip rate ≤ baseline |
| **Dynamic quota** | **~−200 to −400 s** if tuned (hypothesis) | **LOW–MEDIUM** if severity + `table_presence` floors preserved | **Best long-term knob** — extends existing `SIGNAL_CLASS_QUOTA` |

**Return line:** **keep 5** | **try 3 with A/B** | **dynamic quota** — in that priority order.

---

## Baseline: what MAX_UNIT_CHECKS=5 buys today

| Metric | Value | Source |
|--------|-------|--------|
| Fleet unit checks | **1510** / 2284 calls (**66.1%**) | `tapetum-llm-speedup/00-baseline.md:22-23`, `10-call-graph-accountant.md:8` |
| Unit-check wall share | **~1888 s** (~63% of 3003 s) | `10-call-graph-accountant.md:8` (`1510×20/16`) |
| Median checks/paper (units) | PDF **5**, HTML **4**, fleet median **7** total calls | `01-call-count-accountant.md:11-14,30` |
| Cap saturation | **179/180 PDF** at 5; **376/381** papers routed | `01-call-count-accountant.md:30` |
| Zero-defect unit checks | **1057/1510 (70%)** | `cold-run-10min/00-baseline.md:26` |
| Verdict changed by LLM | **16/381** papers | `tapetum-llm-speedup/00-baseline.md:29-30` |
| Golden-PR misses at cap 5 | PR #286 pages 8/9 unchecked; PR #295 secno sections starved | `llm-golden-verification-gap/00-baseline.md`, `c15-false-positive-hunter.md` |

Implementation: `MAX_UNIT_CHECKS = 5` (`constants.py:223-227`); selection via `_select_units_with_quotas` — phase 1 guarantees `SIGNAL_CLASS_QUOTA=1` slot per distinct `signal_type`, phase 2 fills by `(severity, unit_id)` sort (`unit_judge.py:175-213`, `356-381`). Cap overflow → `unchecked_unit_ids` → `coverage_complete=false` → fusion `source_aware_review_cap` (`fusion.py:192-196`).

---

## Arithmetic: cap 5 → cap 3

### Call model

Per paper with routable units:

```
checked_units = min(MAX_UNIT_CHECKS, |routable_risky_ids|)
```

Fleet unit calls = Σ checked_units. Lowering the cap only removes calls on papers where `checked_units` was **> 3** under cap 5.

### Sidecar-informed estimate (381-paper v10 run)

| Cohort | Observed unit pattern | Δ calls if cap=3 |
|--------|----------------------|-------------------|
| PDF (n=180) | **179** papers at **5** checks | **−358** (179×2) |
| HTML (n=201) | median **4** units; ~**614** unit calls total | **−144 to −210** (papers at 4 lose 1; subset at 5 lose 2) |
| Zero-signal / error | unchanged | 0 |
| **Fleet central** | 1510 → **~1008** | **−502 calls** |

Conservative range (papers already at ≤3 unchanged): **−382 to −550 calls** (−25% to −36% of unit class).

### Wall savings (linear slot model, L=20 s/call)

```
Δwall = ΔN_units × L / S_eff
```

| Configuration | ΔN (central) | Δwall (s) | % of 3003 s baseline |
|---------------|-------------:|----------:|---------------------:|
| Single pod (S=16) | −502 | **−628** | **−21%** |
| Dual pod (S=32) | −502 | **−314** | **−10%** |
| MODERATE stack (~596 s central, dual) | **−502** on full fleet* | **−314** → **~282 s** planning wall | Still ≤600 s, **low margin** |

\*Metadata Tier A+B (−847 unit calls) overlaps: cap-3 bites only on **metadata-pass survivors** (~663 unit checks in MODERATE rescale, `11-wall-arithmetic.md:37`). Rescaled cap-3 savings on survivors: roughly **−502 × (663/1510) ≈ −220 calls → −138 s @ S=32** after metadata short-circuit — **not additive** with −1059 s metadata cut.

### What cap 3 does **not** fix

- Does not remove **381 monolith + 377 metadata** mandatory calls (~847 s wall).
- Does not replace **metadata short-circuit** (−1059 s @ S=16) or **dual-pod** (−887 s on MODERATE remainder).
- **Insufficient alone** for ≤600 s: even −628 s on raw baseline leaves **~2375 s** @ S=16 (`11-wall-arithmetic.md:97`).

---

## Quality impact hypotheses (from research)

Ranked by evidence strength. Answer-class tags from golden-gap corpus: **1**=no compare exists, **2**=routing/budget starvation, **3**=model miss, **4**=fusion cap only, **5**=architecture.

### H1 — Fail-closed dominates: fewer checks → more `review`, not silent `pass` [HIGH, class 4]

Cap overflow already forces `coverage_complete=false` and fusion `source_aware_review_cap` at cap **5** (`c07-schema-validators.md`, `fusion.py:192-196`). Lowering to **3** increases `unchecked_unit_ids` on saturated papers (**~313** papers likely bound today). **Hypothesis:** merged advisory verdict **review rate rises**; **`pass` rate should not rise** on incomplete coverage. **Risk:** operators treat extra `review` as noise (boy-who-cried-wolf), not as safety (`c15-false-positive-hunter.md`).

### H2 — Defect recall loss on displaced high-severity units [HIGH, class 2]

At cap 5, PR #286 already left poll-table pages **8/9 unchecked** while spending slots on pages 1–4, 13 (`00-baseline.md:46-49`, lexical sort + `heading_drift` noise). Cap **3** removes **two more** slots on **179/180 PDFs** and on HTML papers with ≥4 routable units. **Hypothesis:** probability that a **verified defect-bearing unit** is unchecked **increases ~40%** on saturated papers (5→3 is a 40% cut in inspection slots). **Counter:** if displaced checks were the **70% zero-defect tail**, fleet **detection rate** unchanged.

### H3 — SIGNAL_CLASS_QUOTA interaction at cap 3 [MEDIUM, class 2]

Phase 1 reserves **one slot per signal class** before severity fill (`unit_judge.py:186-203`, `constants.py:229-233`). Router emits up to **6+ classes** (`low_recall`, `heading_drift`, `token_delta`, `missing_code`, `missing_captions`, `table_presence`). With **max_checks=3**, quota phase can consume **all three slots** on diversity alone — **zero severity-ranked fill**. **Hypothesis:** cap 3 **helps** table classes vs heading noise **if** `table_presence` sorts early in quota walk; **hurts** if three low-value `heading_drift` units win quota on a table-defect paper (`49-steelman-defender.md:30` table_presence saturation on **256/376** papers).

### H4 — Zero-defect tail is the economic target [MEDIUM, class 5]

**1057/1510** unit checks returned **zero defect groups**; only **16/381** papers had merged verdict changed by LLM findings (`00-baseline.md:29-30`). **Hypothesis:** checks **4–5** on saturated papers are ** disproportionately zero-yield** — cap 3 removes cost with **low verdict flip risk**. **Counter:** the **16** flip papers are exactly where unit checks matter; sidecar replay has **not** tagged which check index (1–5) supplied the decisive defect (`10-call-graph-accountant.md:36-38`).

### H5 — Inspect / golden-PR regression [MEDIUM, class 4]

`--inspect` / `--exhaustive-units` bypasses cap (`unit_judge.py:335-337`, `cli.py:309`). Fleet cap 3 does **not** shrink golden-PR exhaustive runs. **Hypothesis:** production fleet `--inspect` on a 15-page PDF shows **3/15** LLM unit checks unless exhaustive — **worse operator trust** than today's 5/15 (`all-pages-llm-coverage/32-steelman-all-pages.md:14`).

### H6 — MoE stability unchanged [LOW]

Cap reduction does not add in-paper parallelism; **no new batch-composition variance** (`13-in-paper-parallel-risk.md`). Quality risk is **coverage**, not decode variance.

### H7 — Deterministic false-pass surface [LOW–MEDIUM, class 1+2]

Localized token-preserving corruption with clean router (`per-page-judging/SYNTHESIS.md`) never routes a unit. Cap 3 **does not widen** that blind spot. Cap 3 **does** shrink sampled coverage on **routed** table pages where deterministic lane already passes (`a01-golden-qa-gap.md` P1068R11 SF cell).

---

## Option analysis

### A. Keep 5 (recommended default)

**Pros:** Matches measured fleet; golden-gap archaeology assumes cap 5; quota phase still has **2 fill slots** after typical 3-class papers; exhaustive path unchanged.

**Cons:** **179/180 PDFs** pay **2 extra serial calls** (~40 s/paper × 179 ≈ **7160 s aggregate serial**, ~**448 s fleet** @ S=16) mostly confirming absence.

**When right:** Production cold fleet until holdout A/B proves cap 3 equivalent.

### B. Try 3 with A/B (recommended experiment)

**Protocol** (from `47-quality-equivalence.md`):

1. Baseline A: `MAX_UNIT_CHECKS=5`, full 381 cold run, record per-PID `(suggested_verdict, defect_type multiset, coverage tuple)`.
2. Candidate B: `MAX_UNIT_CHECKS=3`, same prompts/model/`_LANE_VERSION` except cap constant.
3. **Gate:** fleet flip rate ≤ baseline; **holdout 48 anchors** (`31-steelman-target.md`) must not lose verified defect groups; **no increase** in `pass` where A had `unchecked_unit_ids` with table/cell signals.
4. **Acceptable trade:** higher `review` from coverage cap if **zero new `pass`** on anchor blockers.

**Expected wall (if shipped):** **−503 s central @ S=16**, **−251 s @ S=32** — meaningful but **secondary** to metadata short-circuit + dual-pod.

**Do not ship** on wall alone: **13-determinism-guardian.md** warns lowering cap without router retune emits **`pass` on incomplete coverage** only if fusion bugs; more likely **inspect false-clear appearance** when operators ignore `review`.

### C. Dynamic quota (recommended direction)

Static **5→3** treats every paper identically; saturation data says the bug is **scheduling**, not the number five (`r15-routing-budget-survey.md`: fix is **signal-class quotas + deterministic table tripwires**, not peer cap copy).

**Already partial:** `SIGNAL_CLASS_QUOTA=1` + two-phase selection (`unit_judge.py:175-213`).

**Proposed dynamic policy (hypothesis, not implemented):**

```
max_checks = clamp(
    base=3,
    +1 if any routed unit has severity in {critical, high},
    +1 if any routed page has has_tables or table_presence,
    +1 if len(routable_risky_ids) > 8,
    max=7,
)
```

Fleet mode `base=3`, golden `--inspect` `exhaustive=True` unchanged. **Hypothesis:** recovers **~60–80%** of cap-3 wall savings on zero-yield tail while preserving **≥1 table slot** on PR #286-class papers. **Needs:** sidecar replay + holdout A/B — same gate as cap 3.

**Pros:** Targets **256/376** table-saturated papers (`49-steelman-defender.md`) without uniform cut.

**Cons:** More constants; `_LANE_VERSION` bump; fusion tests for new `unit_selection` audit fields.

---

## Stacking note (cold-run-10min program)

| Lever | Est. saving | Overlap with cap 3 |
|-------|------------:|-------------------|
| Metadata Tier A+B | −1059 s @ S=16 | **High** — removes unit calls on 232 papers first |
| Cap 3 (full fleet) | −628 s @ S=16 | Apply rescale on **survivor mix only** (~−138 s @ S=32 post-metadata) |
| Dual-pod | −887 s on MODERATE remainder | Independent |
| Prefix / verdict-first | −281 / −155 s scaled | Overlap on eliminated unit calls |

**Do not sum** cap 3 + metadata naively. Cap 3 is a **third-tier** lever after metadata short-circuit and infra (dual-pod, prefix).

---

## Findings

- [CRITICAL] **Unit checks are 1510/2284 calls and ~63% of wall; cap 5 is saturated on 179/180 PDFs.** Evidence: `01-call-count-accountant.md:8-11,30`. Impact: cap 3 is one of few **N-cut** knobs left, but **smaller than metadata short-circuit (−1059 s)**.

- [CRITICAL] **Cap 3 central savings ~−502 calls → −628 s @ S=16 (−21% wall), −314 s @ S=32.** Evidence: saturation table above; closure `ΔN×20/S`. Impact: **does not reach 10 min alone**; on MODERATE+dual **~282 s** central if naively stacked (overstates overlap).

- [HIGH] **Quality risk is recall on routed defect units, not fusion false-pass.** Evidence: PR #286/#295 starvation at cap 5 (`c15`, `c14-false-negative-hunter.md`); fail-closed fusion (`c07`). Impact: cap 3 **worsens class-2 golden misses** unless paired with router/table tripwires.

- [HIGH] **70% zero-defect checks argue for smarter skip, not blind −2 slots.** Evidence: `00-baseline.md:29-30`, `35-zero-defect-predictor.md`. Impact: **dynamic quota** or metadata/table deterministic gates beat uniform cap 3.

- [MED] **SIGNAL_CLASS_QUOTA at cap 3 may consume entire budget on diversity.** Evidence: `unit_judge.py:186-203`, six signal classes in router. Impact: table vs heading tradeoff **sharpens** at 3 — A/B must stratify by `table_presence` saturation.

- [MED] **Only 16/381 papers had LLM-driven verdict changes — high leverage, tiny denominator.** Evidence: `00-baseline.md:29-30`. Impact: cap 3 A/B must use **equivalence on those 16**, not fleet pass rate alone.

- [LOW] **Timeout budget in cli.py scales with MAX_UNIT_CHECKS** (`19-timeout-tail-auditor.md`: `(1+MAX_UNIT_CHECKS)×120`). Impact: cap 3 saves **240 s per-paper timeout headroom**, irrelevant to mean cold wall.

---

## False-pass hypothesis

Cap **3** on a paper with **monolith pass + metadata pass + localized table cell swap** on page 9: router emits `table_presence` on pages 8–9 plus three `heading_drift` units on pages 1–3; quota + cap leave page 9 unchecked; monolith and metadata stay pass; fusion sees `coverage_complete=false` → **review**, not pass — **unless** operator treats advisory `review` as shippable. Silent false-pass requires **ignoring coverage cap**, not cap 3 alone.

## False-fail hypothesis

Cap **3** on a **clean 15-page golden** with six `heading_drift` signals: three checks all pass with zero defects; twelve routed units unchecked → **review** via `source_aware_review_cap` with **no defect groups** — same shape as today's cap-5 saturation (`all-pages-llm-coverage/32-steelman-all-pages.md`), **more frequent** on PDFs (179 papers lose 2 checks).

## What would change my mind

Sidecar replay on the v10 381-paper run reporting: (1) **≥90%** of checks in slots 4–5 have zero defect groups **and** no incident in the **16** verdict-flip papers; (2) cap-3 replay **zero holdout anchor regressions**; (3) **`pass` count unchanged** and `review` delta ≤ **+5%**. Would upgrade cap 3 from A/B-only to ** shippable fleet default**.

---

## Recommendation summary

1. **Keep 5** for production until holdout A/B completes.
2. **Try 3 with A/B** — cheap constant change, **~21% wall @ S=16** if accepted; gate on equivalence + 48 anchors, not footer seconds alone.
3. **Invest in dynamic quota** (severity + table floor + routable-count ceiling) instead of permanently shipping cap 3 — addresses saturation root cause documented in `r15-routing-budget-survey.md` and `49-steelman-defender.md`.

**Do not** lower cap to 3 as a substitute for metadata short-circuit, dual-pod, or router precision work ranked in `cold-run-10min/00-baseline.md:32-38`.
