# 49 - Monolith Keep-or-Drop

**Verdict:** usable-with-conditions — Speedup’s **7.5% PDF-monolith wall share is confirmed** (147-verifier); **keep monolith**, do **not** drop or merge it with metadata for speed.
**Confidence:** high

## Executive answer

| Question | Answer |
|----------|--------|
| **Is monolith only 7.5% of wall?** | **Yes**, for **PDF monolith calls only** (181 calls → **226 s / 7.5%** of 3003 s). The older **~17%** figure applies to **all first-pass calls** (381 monolith + HTML tier-1 → **472 s / 15.7%**), not PDF monolith in isolation. |
| **Keep monolith?** | **Yes.** |
| **Drop or merge monolith + metadata?** | **No.** Different roles; merge is low yield and high quality risk; metadata is the better elimination target (deterministic diff, AGGRESSIVE tier). |

---

## Findings

- [CRITICAL] **7.5% claim is confirmed and scoped correctly.** Verifier-C replay on 2026-07-23 sidecars: **181 PDF monolith calls** × 20 s / 16 slots = **226 s = 7.5%** of **3003 s** cold wall. Evidence: `147-verifier-monolith-textlane.md:16`, `opus-A-meta-review.md:27-30`. The persona-16 **~17%** claim is **MODIFIED**: **472 s (15.7%)** covers **378 first-pass calls** (181 PDF monolith + **197 HTML tier-1**), fleet-wide. Impact: dropping PDF monolith alone saves **~226 s (~3.8 min)**, not **~476 s**; still **~2400 s short** of a 5–10 min target without unit-call cuts.

- [CRITICAL] **Monolith marginal verdict value is tiny; removal is not free.** Cnf-only simulation (strip monolith `candidate_not_found`, keep metadata/units/escalations): **1/181 PDF papers** change verdict (**P4048R0 fail→review**). Persona-16’s **4/181** overstated: **N5036, P3828R1, P4124R0** stay **review** because unit checks already emit defects. Full monolith removal (not cnf-only): **8/181** differ. Evidence: `147-verifier-monolith-textlane.md:14-16`, `16-monolith-redundancy-skeptic.md:10`. Impact: monolith is **cheap insurance** (~7.5% wall) for document-wide reorder/structure; dropping it trades **~226 s** for **1–8 verdict deltas** and structural blind spots units cannot cover.

- [HIGH] **Monolith’s unique scope is document-wide reorder/structure; units and metadata cannot fully substitute.** Monolith prompt checks reordering (`pdf_judge.py:190-196`); page judge explicitly excludes it (`pdf_judge.py:225-226`). Metadata checks field values, missing sections, heading drift on bounded outline (`unit_judge.py:114-127`), not cross-page section order. **58/181 PDF** papers have zero monolith dispositions yet metadata or units still flag issues; **18 papers** have defect groups with zero monolith cnf (e.g. P1000R8 table corruption). Conversely, **0 fleet examples** cite reordering as the deciding defect today, but the class is structurally exposed if monolith is removed without a cheap outline-only substitute. Evidence: `16-monolith-redundancy-skeptic.md:12-18`, `SYNTHESIS.md:40-41`. Impact: keep monolith; optional future **outline-only reorder call** on borderline papers (~20–30 triggers) is a replacement architecture, not a merge-with-metadata play.

- [HIGH] **Monolith + metadata combined is ~31.6% wall — but the pair should not be dropped or merged.** Call census: **758 calls** (381 first-pass + 377 metadata) → **758 × 20 / 16 ≈ 948 s (~31.6%)** on 3003 s (`10-call-graph-accountant.md:42-45`, `66-marker-quality-speed-flags.md:22`). Nightly monolith+metadata-only still misses unit-check-only defects (table cell swap, localized corruption on quiet pages). **16/381 papers** had merged verdict changed by LLM findings; **70%** of unit checks are zero-defect but the long tail matters. Impact: cutting both front-end calls saves **~948 s** but removes the only document-wide lens plus the metadata gate that drives **31 PDF fails** (14 with zero cnf from any path). Quality risk: **HIGH**.

- [HIGH] **Merge monolith + metadata into one LLM call is unwise.** Payloads differ: monolith sends **full PDF text layer + full candidate markdown** (`pdf_judge.py:640-643`); metadata sends **bounded source metadata + outline + front matter + ATX headings only** (`unit_judge.py:231-256`). Serial chain has **no data dependency** (metadata does not consume monolith output; `03-cascade-topology-auditor.md:12`), so merge saves at most **one ~20 s slot per paper (~377 calls if metadata absorbed, ~181 if monolith absorbed)** while producing a **larger combined prefill** (monolith ≈ 2× unit payload). Metadata is already classified as a **structured diff masquerading as LLM** — AGGRESSIVE tier replaces **377 MoE calls (~471 s)** with deterministic `compare_metadata_outline()` (`131-surya-model-sizing.md:10`, `SYNTHESIS.md:37`). Impact: **replace metadata deterministically, keep monolith separate** beats merge on both wall and quality.

- [MED] **Speed packages correctly dropped monolith elimination as a lever.** Opus meta-review: “Monolith stays (cheap insurance, only document-wide lens); **the lever is dropped from the packages**” (`opus-A-meta-review.md:27-30`). CONSERVATIVE/MODERATE stacks target metadata short-circuit (−847 unit calls), prefix cache, dual-pod — not monolith cuts (`11-wall-arithmetic.md`, `SYNTHESIS.md:45-52`). Impact: engineering effort on monolith removal **~226 s max** distracts from **~1341 s** metadata-fail unit waste and **~1888 s** unit-check class.

- [MED] **Monolith prefill is large but wall share is capped by call count.** One call per PDF paper vs **median 5 unit checks** each repeating full markdown (`unit_judge.py:769-776`). Unit checks = **66.1% of calls / ~63% of wall** (`10-call-graph-accountant.md:8-9`). Monolith quote yield is weak: **392 quotes**, **228 refuted**, **87 grounded cnf**, **63 papers** with all quotes refuted. Impact: monolith cost is **one heavy prefill per paper**, not six; unit elimination dominates speed work.

---

## Wall-share table (3003 s baseline, 16 slots, 20 s/call)

| Component | Calls | Est. wall (s) | Share of 3003 s |
|-----------|------:|--------------:|----------------:|
| PDF monolith | 181 | **226** | **7.5%** ✓ |
| HTML tier-1 (text “monolith”) | 201 | ~251 | 8.4% |
| **All first-pass** | 381 | ~476 | **15.9%** (≈ old “17%”) |
| Metadata / outline | 377 | ~471 | 15.7% |
| **Monolith + metadata** | 758 | ~948 | 31.6% |
| Unit checks | 1510 | ~1888 | 62.9% |
| Page escalation + tier-2 | ~39 | ~49 | 1.6% |

---

## Recommendation

| Action | Verdict | Rationale |
|--------|---------|-----------|
| **Keep PDF monolith** | **Yes** | 7.5% wall; sole document-wide reorder/structure lens; 1/181 cnf-only verdict delta on removal; dropped from speed packages intentionally. |
| **Drop monolith** | **No** | Saves ~226 s (~3.8 min); exposes reorder class; 8/181 full-removal deltas. |
| **Merge monolith + metadata (one LLM call)** | **No** | Mixed payloads, larger prefill, schema/prompt entanglement; metadata better eliminated deterministically (~471 s, AGGRESSIVE). |
| **Drop monolith + metadata together** | **No** | ~948 s savings but removes front-end gates; unit-check-only defects ship on nightly path. |
| **Replace metadata with deterministic diff; keep monolith** | **Yes (AGGRESSIVE, A/B-gated)** | ~471 s without touching monolith’s unique scope (`131-surya-model-sizing.md`, `SYNTHESIS.md:37`). |

---

## False-pass hypothesis

Drop monolith on “clean screen” papers without a reorder substitute: a paper with **≥0.90 per-page recall** but **swapped section order** passes screen, deterministic metadata, and routed units — only monolith explicitly checks reordering. **0 fleet hits today**, structurally exposed (`16-monolith-redundancy-skeptic.md:26-27`).

## False-fail hypothesis

Keep monolith on every paper: **63 PDF papers** pay full PDF+MD prefill for quotes **100% refuted** by grounding (`16-monolith-redundancy-skeptic.md:30`). Wasted **~226 s fleet-wide** is real but bounded; not a reason to delete without substitute.

## What would change my mind

Holdout replay of **≥30 labeled PDFs** where verified defect class is **document-wide reordering or cross-page structure**: if **≥50%** are caught **only** by monolith and by neither screen+units nor a cheap outline-only call, monolith becomes mandatory at current call rate. Alternatively, measured ablation showing monolith+metadata-only misses **≥10%** of unit-check-only defects with severity ≥ review would justify rethinking the front-end stack — not merge, but nightly/thorough split (`66-marker-quality-speed-flags.md:34`).

---

## Sources

- `research/tapetum-llm-speedup/147-verifier-monolith-textlane.md` — 7.5% confirmation, verdict-delta replay
- `research/tapetum-llm-speedup/opus-A-meta-review.md` — monolith kept, lever dropped from packages
- `research/tapetum-llm-speedup/16-monolith-redundancy-skeptic.md` — scope, replacement architecture
- `research/tapetum-llm-speedup/10-call-graph-accountant.md` — call-class ledger
- `research/tapetum-llm-speedup/SYNTHESIS.md` — package ranking
- `research/tapetum-llm-speedup/131-surya-model-sizing.md` — metadata deterministic replacement
- `research/cold-run-10min/11-wall-arithmetic.md` — MODERATE stack (no monolith cut)
