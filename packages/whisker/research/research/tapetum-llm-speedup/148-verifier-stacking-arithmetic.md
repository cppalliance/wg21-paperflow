# 148 - Verifier-D (Stacking-Arithmetic Auditor)

**Verdict:** usable-with-conditions (+ persona 48's stacking rule and overlap dedup are sound; point estimates are optimistic on dual-pod efficiency, prefix low-bound, and friction; MODERATE central wall is ~580–610 s, not ~505 s)
**Confidence:** medium-high

## Findings

- [CRITICAL] **Independent wall model (rebuilt from 00 baseline).** Formula: `wall = (N_rem × L_eff) / S_eff + T + C − L_abs`, where `L_abs` = absolute seconds from prefix cache and verdict-first (not halved when `S` doubles). Baseline closure: `N=2284`, `L=20 s`, `S=16`, `T+C≈148 s` (`2284×20/16 + 148 = 3003 s` ✓). Apply **N cuts first**, scale **L_abs** to the surviving call mix, then divide by **S**. Do not sum prefix savings computed on the pre-cut unit population with metadata elimination savings on the same calls.

- [CRITICAL] **Call-census discrepancy (2284 vs 2345 vs 2362) breaks percentage math if mixed.** `00-baseline.md` / `10-call-graph-accountant`: **2284** = 381 first-pass + 377 metadata + **~1510** unit + **~16** page esc (HTML tier-2 **~23** omitted from headline; sidecar aggregate **~2308**). `34-verdict-value-analyst`: **2345** on 378 ok sidecars because v10 sidecars count **1570** unit checks (+60 vs 1510) and tier-2 inline. `17-metadata-short-circuit`: **2362** sidecar denominator for `%` quotes. **Only N=2284 closes the measured 3003 s wall** with `L=20`; rescaling persona-17/34 `%` savings to 2284: metadata Tier A+B **847 calls** and **~1059 s** compute @ S=16 (`847×20/16`), not 1076 s (`847/2362×3003`). Use **847 / 1419 / 1229** as the stacking N ladder; treat 2345/2362 as sidecar accounting only.

- [CRITICAL] **Double-count handling (confirmed + one gap).** Metadata Tier A+B removes **847 unit checks** (~100% of eliminated calls are units, `17`). Prefix unit-block saving must scale: `500 s × (663/1510) ≈ 219 s`, not 500 s. Static-system APC scales: `100 s × (1419/2284) ≈ 62 s`. Verdict-first scales: `250 s × (1419/2284) ≈ 155 s`. Overlap pairs correctly treated as **max not sum** in persona 48. **Gap:** persona 48 does not subtract text-lane-only prefix (~333 s, `42-text-lane-accountant`) separately from PDF unit reorder; fleet-wide `(663/1510)` ratio is acceptable but **overstates PDF page-esc / monolith APC** (~16 + 381 calls) where reorder does not apply — net **~20–40 s** optimism in MODERATE prefix line.

- [HIGH] **Uniform L=20 vs class-specific latencies.** Baseline effective **20 s/call** is a fleet mean that closes wall (`00-baseline.md:24-25`). `105-vllm-dense-judge-throughput` decomposes: monolith **18–22 s**, metadata **8–10 s**, unit **20 s** @ MoE S=16. Recomputing remaining MODERATE mix (756 non-unit + 663 unit) yields **L_eff≈18 s**, not 20 — **~90 s optimistic** if applied naively to MODERATE. **Pessimistic rule:** keep **L=20** for MoE-only packages; class-specific L is mandatory only for AGGRESSIVE dense offload (and only after scoping lands, `105`/`13`).

- [HIGH] **Dual-pod sharding is ~1.75–1.9× on total wall, not a clean 2×.** `21-dual-pod-sharder`: `2284×20/32 ≈ 1428 s` compute vs 2855 s (**2.0×** on compute term only); measured expectation **3003 → ~1600 s** (**1.88×** total) when `T+C` do not halve. Residual skew without per-pod semaphores: **+100–300 s** (`22-multi-pod-fleet-designer`, cited in 48). Persona 48 treats per-pod sem guard as **−50 s** (additional saving); independent audit treats unfixed skew as **+75–125 s friction** on CONSERVATIVE/MODERATE. Effective slots **S=28–30** is a safer planning number than 32 until live dual-pod proof.

- [HIGH] **Text-lane 49.9% wall share interacts with PDF-biased levers.** `42-text-lane-accountant`: **1200/2362 calls (50.8%)**, **~1500/3003 s wall (49.9%)**. Metadata short-circuit is **fleet-wide** (458 text + 589 PDF unit calls in the 847 Tier A+B cut — same lever). **PDF-only levers do not transfer:** page-escalation dedupe (**18** calls, PDF-only, `18`); prefix reorder on **section:** units (592 cacheable 2nd+ checks) mirrors PDF but with different prompt geometry; `--all-pages` / screen_pages CPU levers are PDF-only. **No double-count** if metadata + prefix use fleet N, but **AGGRESSIVE router combo_safe** is PDF-signal-heavy (`11`: `table_presence` PDF-only) — **~60% of router savings** may sit on PDF papers; fleet −190 is still valid, variance ±15 calls.

- [MED] **Prefix envelope 600–1100 s is pre-rescale, S=16, full N=2284.** Low bound **600 s** (`15`, server APC + per-paper tag + unit user reorder). Rescaled to MODERATE (`48`): **281 s** (= 219 + 62). Pessimistic rescale using prefix low-bound haircut (APC overhead at 0% hits until reorder ships, `15`/`102`): **unit reorder base 400 s** → **175 s** + **50 s** static → **225 s** total prefix on MODERATE, not 281 s.

- [MED] **Metadata short-circuit: 847 calls, not 1047.** Tier A+B (`17`): **−847** (−141 fail, −706 review@1 unit). Full skip **−1047** adds **200** calls (+250 s vs Tier A+B) with inspect regression — excluded from MODERATE. Escalation dedupe **−18** (`18`, not 16 in baseline headline). Combined N: **2284 − 847 − 18 = 1419**.

- [MED] **AGGRESSIVE ≤300 s requires optimistic tail of ranges.** Persona 48: **260–350 s** with `L_eff=11.74 s`, `N=1229`, friction +130 s. Pessimistic rebuild: dense **12 s** not 10 s (`105`: scoped payload not landed → `L_unit≈20`), **`L_eff=13.7 s`**, prefix **180 s**, verdict **110 s**, friction **+230 s** → **~495 s**. **≤300 s is not supported** under pessimistic dense/scoping/KV assumptions; needs measured A/B (`105` what-would-change-mind).

## Rebuilt package walls (pessimistic central + range)

Method: same lever set as persona 48; adversarial rounding (lower savings, upper friction). `T=100 s` base (retries ~100, `29`), `C=58 s`; LJF **−60 s**, `to_thread` **−30 s** → **T+C=68 s** after trims (vs 48's 28 s — pessimistic retention of **+40 s** irreducible tail).

| Package | N_rem | S_eff | L_abs (net) | Friction | Central wall | Range |
|---------|------:|------:|------------:|---------:|-------------:|------:|
| Baseline | 2284 | 16 | 0 | 0 | 3013 | 3003 (meas) |
| CONSERVATIVE | 2284 | 32 | −550 (prefix) | +100 | **945** | **860–1020** |
| MODERATE | 1419 | 32 | −225 (prefix) −124 (verdict) | +75 | **596** | **530–670** |
| AGGRESSIVE | 1229 | 32 | −180 −110 | +230 | **495** | **420–580** |

**Deltas vs persona 48 central estimates:**

| Package | Persona 48 | Verifier-D (pess.) | Δ |
|---------|-------------:|-------------------:|--:|
| CONSERVATIVE | ~770 (685–856 band) | **945** | **+175 s** |
| MODERATE | ~479 (+50 sem → 529) | **596** | **+67 to +117 s** |
| AGGRESSIVE | ~134 (+friction → ~295) | **495** | **+200 s** |

Persona 48 MODERATE **480–530 s** aligns with **optimistic** friction (sem guard as saving, prefix=281, T+C=28). Independent central **~596 s** (+12%) is the planning number.

**Target gates (pessimistic):**

| Target | CONSERVATIVE | MODERATE | AGGRESSIVE |
|--------|:------------:|:--------:|:----------:|
| ≤600 s (10 min) | ❌ | ✅ (low band tight) | ✅ |
| ≤300 s (5 min) | ❌ | ❌ | ❌ |

## Final reconciled table

| Package | Levers (deduped) | Expected wall (pess. range) | Quality risk | Validation cost |
|---------|------------------|----------------------------:|:-------------|:----------------|
| **CONSERVATIVE** | Server APC + retention env; per-paper guard tag; unit user-block reorder; dual-pod shard (`alliance-pod` + `h200x8-deepseek-v4-pro`) + per-pod semaphores; LJF; `asyncio.to_thread` for screen/ground | **860–1020 s** (~16–17 min) | **LOW–MED** — reorder holdout only | **LOW–MED** — pod flags, shard CLI, 48-paper reorder A/B |
| **MODERATE** | CONSERVATIVE + metadata Tier A+B (fail skip + review→1 unit); escalation skip-and-synthesize; pass-path verdict-first / shrink empty reasoning | **530–670 s** (~9–11 min) | **MED** — inspect completeness on 19 review papers; verdict-first drift | **MED** — ~2–3 weeks; 0 metadata-flip replay + 48-paper verdict stability |
| **AGGRESSIVE** | MODERATE + router combo_safe (−190); unit+metadata offload to `h200-qwen3-32b` (MoE fallback oversize) | **420–580 s** (~7–10 min) | **HIGH** — router 6 FN PIDs; dense 381/381 parity | **HIGH** — ~6–10 weeks; full fleet fused A/B + scoping prerequisite |

## Discrepancies ledger

| Issue | Sources | Reconciliation |
|-------|---------|----------------|
| N = 2284 vs 2345 vs 2362 | `00`, `10`, `17`, `34` | **2284** for wall closure; 2345/2362 = sidecar sums (+60 unit calls, tier-2); rescale `%` savings |
| L = 20 s uniform vs 18/9/12 class | `00`, `105` | **20 s** MoE packages; class L only with dense offload + scoping |
| Dual-pod 2× vs 1.9× | `21`, `48` | **1.88×** total wall; compute term 2×; plan **+75–125 s** skew friction |
| Metadata −847 vs −1047 | `17`, `48` | **847** in MODERATE; 1047 = Tier C (inspect regression) |
| Prefix 600–1100 s | `15`, `48` | Full fleet @ S=16; **281 s** (48) or **225 s** (pess.) after metadata rescale |
| Text 49.9% wall | `42` | Metadata cut fleet-wide; page-esc/router PDF-heavy; prefix split ~44% text / ~56% PDF — no extra double-count if using fleet N |
| 1510 vs 1570 unit checks | `00` vs `34` sidecars | **1510** in baseline census; 1570 in sidecar recount — 3% shift in prefix ratios |
| Persona 48 sem "guard" sign | `48` | Treated as **−50 s** saving in 48; independent audit treats unfixed skew as **+cost** unless proven |

## False-pass hypothesis

Ship MODERATE using persona 48's **529 s** as SLA without rescaling prefix after metadata elimination: live run lands **~620–700 s** (measured within persona 48's own ±15% band upper edge), operators disable metadata short-circuit as "broken," and revert to **~900 s** CONSERVATIVE-only — losing real **~350 s** from call cuts.

## False-fail hypothesis

Reject dual-pod because `h200x8-deepseek-v4-pro` once returned 404 (`21`): single-pod MODERATE stays **~750–850 s** (compute @ S=16 on 1419 calls ≈ 1774 s before L_abs — actually 1774 - 349 + 68 = 1493 s), falsely concluding metadata cut "failed to reach 10 min" when the missing lever was **S**, not N.

## What would change my mind

Instrumented MODERATE cold run logging `{call_type, N_rem cumulative, pod_id, cached_tokens, wall_s}` with measured wall **450–620 s** would upgrade MODERATE central to persona 48's band; measured **>700 s** would confirm prefix+skew overlap larger than modeled and force AGGRESSIVE for 10 min.
