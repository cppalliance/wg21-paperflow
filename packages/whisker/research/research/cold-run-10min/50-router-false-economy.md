# 50 - Router False-Economy (post-metadata-short-circuit)

**Verdict:** usable-with-conditions — v11 metadata short-circuit removes the dominant 44.6% fusion-dead class; **~11.6–12.3% of fleet LLM calls remain fusion-dead for merged verdict** on the v10 sidecar replay; router still over-selects low-yield signal classes on metadata-pass papers, but empty-packet slot burn is already fixed at HEAD.
**Confidence:** high (sidecar aggregates + code paths); medium on post-v11 rescale (no fresh cold fleet run)

**Sources:** `research/tapetum-llm-throughput/12-false-economy-hunter.md`, `research/tapetum-llm-speedup/{145-verifier-metadata-short-circuit,11-router-precision-auditor,10-call-graph-accountant}.md`, `research/cold-run-10min/10-impl-status-auditor.md`, HEAD `unit_judge.py`, `source_router.py`, `fusion.py`, `pdf_judge.py`.

---

## Executive answer

| Metric | Value |
|--------|------:|
| Metadata short-circuit (already at HEAD v11) | **44.6%** of fleet calls (1047/2345) |
| **Extra call waste beyond 44.6%** | **~11.6–12.3%** of fleet calls (**289/2345**) |
| Total no-verdict-change waste (pre-cut baseline) | **58.2%** (1332/2308) |
| Extra waste as share of **survivors** (1298 calls) | **~22.3%** (289/1298) |
| Router-only safe tightening (combo_safe, post-cut scale) | **~2.7%** fleet (~63 calls) |

---

## Findings

- [CRITICAL] **Yes — pre-v11 we selected many unit checks that could not affect fusion; v11 removes the largest class.** Sidecar replay: **232/378** papers with metadata ≠ pass ran **1047** unit checks; fusion caps at `source_aware_review_cap` before clear/rescue rules when metadata ≠ pass (`fusion.py:187-189`, `410-423`). PDF lane folds metadata before units (`pdf_judge.py:737-740`); units only demote pass→review, never lift fail/review caps. Counterfactual strip: **0/232** `suggested_verdict` or `combined_verdict` drift (`145-verifier-metadata-short-circuit.md`). v11 short-circuits escalations + units when metadata ≠ pass (`pdf_judge.py:742-758`, `adjudicate.py:521-531`). Impact: **1047 calls (44.6%)** were provably fusion-dead; now skipped in fleet mode.

- [CRITICAL] **Extra waste beyond 44.6% = ~289 calls (~11.6–12.3% of fleet).** False-economy hunter broader set: **1332/2308 (58.2%)** unit calls on `source_aware_review_cap` papers + refuted escalations changed no merged verdict. Subtract metadata-dead unit spend: **1332 − 1043 = 289**. On denominator **2345**: **289/2345 = 12.3%**; delta vs headline **58.2 − 44.6 = 11.6 pp** (rounding on 2308 vs 2345 denominators). Survivor mix after short-circuit: **1298 calls** (378 monolith + 378 metadata + **523** unit + 18 escalation + 1 ideal). **289/1298 = 22.3%** of remaining calls still fusion-dead for verdict.

- [HIGH] **Router waste beyond metadata short-circuit is real but smaller: ~11.6% of unit selections, not another 44%.** Router-precision replay on v10 sidecars: `heading_drift` **903/1284 (70.3%)** zero-defect on checked units; `table_presence` **313/511 (61.3%)** zero-defect; combined safe filter (one `table_presence`/paper, drop long PDF prose `heading_drift`, recall floor 0.90→0.85) saves **190/1634 routed selections (11.6%) ≈ 238 s**. Post-short-circuit scale: **190 × (523/1570) ≈ 63 calls ≈ 2.7%** of original fleet. Impact: router tightening is a **MODERATE/AGGRESSIVE** trim, not a second metadata-class lever. Quality risk: **6/47** defect-group papers lost under combo_safe (`11-router-precision-auditor.md`).

- [HIGH] **Empty-packet / quota slot burn is fixed at HEAD — not ongoing router LLM waste.** False-economy hunter (v10 run): **111** "no source packet" warnings on **102** papers; selection happened before empty guard, poisoning `coverage_complete` and burning `MAX_UNIT_CHECKS` slots. HEAD: `routable_risky_ids` pre-filter before `_select_units_with_quotas` (`unit_judge.py:370-381`); unroutable units tracked separately, excluded from coverage math (`unit_judge.py:496-507`, `tapetum_llm.md:124`). Impact: **0 LLM tokens** for empty packets at HEAD; remaining issue is **signal emission** for uncallable units (`source_router.py:285-312` HTML `heading_drift` on title-only sections), not paid calls.

- [HIGH] **Survivor unit checks still skew low-yield: ~70% zero-defect on metadata-pass tier.** Fleet aggregate: **1057/1510 (70%)** unit checks returned no defects (`12-false-economy-hunter.md`). Metadata-non-pass subset: **692/1047 (66.1%)** zero-defect (`145`). Survivor pass-tier estimate: **1057 − 692 ≈ 365** zero-defect calls on **523** surviving unit checks (**~69.8%**). Only **16/381** papers had LLM-driven merged-verdict changes (9 `llm_rescue_heading`, 7 `llm_clear_soft_review`; 0 `llm_escalate_major`). Impact: most surviving unit spend confirms absence of defects on metadata-pass papers; necessary for fail-closed coverage, but **~278** calls on metadata-pass papers still capped by coverage-incomplete / other cap drivers cannot flip merged verdict.

- [MED] **Risk router fires on nearly the whole corpus while page screen rarely fires — quota saturation, not extra LLM calls.** v10 fleet: **376/381** papers non-empty `risk_signals`; **168/181** PDF papers `screen_flagged=0` but mean **15.2** router signals/paper (`12-false-economy-hunter.md`). **179/180** PDFs saturated `MAX_UNIT_CHECKS=5` (`01-call-count-accountant`). `SIGNAL_CLASS_QUOTA=1` forces one slot per signal class before fill (`unit_judge.py:186-203`, `constants.py:229-233`), displacing higher-value units (PR286 P1068R11: nine `heading_drift` signals consumed five slots). Impact: router shapes **which** five units run, not **how many** calls; fusion-dead outcome when monolith/metadata already capped or checks return zero defects.

- [MED] **Page escalations: 11/16 refuted (~0.5% fleet) — fusion-dead but negligible wall.** Refuted escalations (`confirmed=False`, `quotes=0`) included in false-economy **1068** no-finding set; survive metadata short-circuit on metadata-pass PDF papers only. Impact: **~11 calls (~0.5% fleet, ~69% of escalation spend)** — hygiene, not 10 min lever.

- [LOW] **Monolith + metadata are not fusion-dead; do not router-cut them.** Mandatory serial chain; metadata failure is primary cap signal for **240** merged papers. Short-circuit correctly preserves both calls and skips downstream units only.

---

## Are we selecting unit checks that can't affect fusion?

| Era | Selecting fusion-dead units? | Mechanism |
|-----|:----------------------------:|-----------|
| v10 fleet (sidecar replay) | **Yes, massively** | **1043** unit calls after metadata fail/review; fusion already capped (`fusion.py:187-189`) |
| v10 fleet (slot burn) | **Yes (0 LLM tokens)** | **111** empty-packet units selected before guard → quota + `coverage_complete` poison |
| HEAD v11 (metadata short-circuit) | **Mostly fixed** | Metadata ≠ pass → skip units/escalations (`pdf_judge.py:748-758`) |
| HEAD v10+ (pre-filter) | **Slot burn fixed** | Unroutable IDs excluded before quota (`unit_judge.py:370-381`) |
| HEAD v11 survivors | **Partially yes** | **~289** verdict-dead calls: cap-locked pass-tier units + refuted escalations; **~365** zero-defect survivors that did not flip any of **16** verdict-changing papers |

**Code confirmation:** `_select_units_with_quotas` has no fusion-awareness — it optimizes signal-class coverage, not merged-verdict marginal value (`unit_judge.py:175-213`). Fusion applies cap **before** `llm_clear_soft_review` / `llm_rescue_heading` (`fusion.py:410-423` precedes `477-519`), so units on already-capped papers cannot promote verdict.

---

## Router waste beyond metadata short-circuit

| Waste class | LLM calls | % of 2345 fleet | Status at HEAD |
|-------------|----------:|----------------:|----------------|
| Metadata-fail/review unit checks | 1047 | **44.6%** | **Eliminated** (v11 short-circuit) |
| Cap-locked pass-tier unit checks + refuted esc | ~289 | **~12.3%** | Open (coverage/router policy) |
| Router combo_safe trimmable | ~63 (scaled) | **~2.7%** | Paper-only (`11-router-precision-auditor`) |
| Zero-defect survivors (not all fusion-dead) | ~365 | **~15.6%** | Inherent fail-closed cost on pass tier |
| Empty-packet slot burn | 0 LLM | 0% | **Fixed** (v10 pre-filter) |

**Router-specific beyond metadata:** signal over-fire (`heading_drift` 65% of firings, `table_presence` unconditional on PDF table pages), quota saturation on **256/376** papers at five checks, and HTML outline index vs section-body ID mismatch causing unroutable `heading_drift` (`source_router.py:285-312` vs `adjudicate.py:519-520`). These waste **selection quality** and cap **278** post-short-circuit verdict-dead calls more than they add net-new call volume.

---

## Spend arithmetic (post-v11 cold run, modeled)

```
Baseline fleet:     2345 LLM calls, 3003 s wall
After short-circuit: 1298 calls (−44.6%)
Extra fusion-dead:   289 calls (−12.3% of baseline; −22.3% of survivors)
Residual "useful":  ~1009 calls (monolith + metadata + ~234 verdict-material unit/esc)

Linear wall model (@ 20 s/call, 16 slots):
  Short-circuit save:  1047 × 20/16 ≈ 1341 s  (settled)
  Extra cut (289):       289 × 20/16 ≈  361 s  (upper bound if all safely removable)
  Router combo_safe:      63 × 20/16 ≈   79 s  (bounded FN: 6/47 defect-group papers)
```

Naive sum of 44.6% + 12.3% = **56.9%** ≈ false-economy hunter **58.2%** total no-verdict-change band.

---

## False-pass hypothesis

Ship router combo_safe (+ drop all `table_presence` unconditionally) to capture another **~12%** unit calls without holdout replay: **6/47** defect-group papers (incl. multi-table P4025R1/R2) lose unit-level evidence while monolith stays `review` — inspect false-clear, merged verdict unchanged (`11-router-precision-auditor.md`).

## False-fail hypothesis

Re-enable unit checks on metadata-`review` papers (SYNTHESIS Tier A+B "one corroborating unit"): merged verdict stays capped at `review`, but restores **19** papers' unit-level inspect detail (`145-verifier-metadata-short-circuit.md`) at cost of **~706** extra calls (~25% of fleet) — false economy to skip, false-fail for `--inspect` if skipped.

## What would change my mind

Fresh v11 cold fleet sidecars showing **>16 papers** where unit checks (not metadata/monolith) flipped `combined_rule` to `llm_clear_soft_review` or `llm_rescue_heading` would shrink the **289** survivor waste estimate. A replay proving combo_safe misses **0/47** defect-group papers would upgrade router trim from **~2.7%** to safe MODERATE lever.

---

## Cheapest safe cuts (ranked, post-short-circuit)

1. **Already shipped:** metadata short-circuit (**−44.6%** calls) + unroutable pre-filter (zero LLM; slot/cap hygiene).
2. **Tighten HTML `heading_drift`:** do not emit `RiskSignal` when `unit_text_map` entry is empty (`source_router.py:285-312`) — complements pre-filter; stops unroutable signal noise.
3. **Router combo_safe** on survivors: **~63 calls (~2.7% fleet, ~79 s)** — requires holdout on 6 missed PIDs.
4. **Coverage-cap audit:** distinguish "checked clean" vs "cap without verification" in inspect output — does not cut calls, reduces operator false-clear on **~101** coverage-incomplete caps.

**Do not** re-cut monolith, metadata, or blanket-skip zero-defect survivors without A/B: those **16** verdict-changing papers sit on metadata-pass tier.
