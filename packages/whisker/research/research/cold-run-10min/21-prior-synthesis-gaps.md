# 21 - Prior synthesis gaps (tapetum-llm-speedup ledger)

**Sources:** `research/tapetum-llm-speedup/SYNTHESIS.md` (2026-07-23),
`research/tapetum-llm-speedup/opus-A-meta-review.md`. Both exist.
**Scope:** Every lever marked unimplemented (paper-only packages), A/B-gated,
or rejected. Plus internal contradictions between personas / between SYNTHESIS
and the meta-review packaging.

Prior synthesis treats packages as a recommended execution program, not as
shipped code. Cold-run delta `00-baseline.md` still asks which levers exist at
HEAD; until that census lands, treat the full package list as **unimplemented**.

---

## 1. Unimplemented (paper-only; not claimed shipped)

### CONSERVATIVE (SYNTHESIS §3)

| Lever | Claimed effect | Notes |
|-------|----------------|-------|
| Error tombstone fingerprints + `--retry-errors` | Warm 65 s → ~10-15 s | Free win; no verdict-semantics change (P46, 150 CONFIRMED) |
| Monolith per-call `asyncio.wait_for` | Removes ~20 min hang / slot hold | Free win (P26) |
| `to_thread` for sync CPU + candidate-token cache | ~30-40 s (+ unblock event loop; screen_pages up to ~17 s/doc) | Free win (P28/P43) |
| LJF paper ordering | ~60-180 s tail trim | Free win; output-order invariant (P29) |
| Per-call timing in sidecars + `/metrics` scrape playbook | Measurement prerequisite | Free win (P79/P96); not a wall saver by itself |
| Server flags: MBT 8192→16384 + APC retention env | Prefill/retention hygiene | Delta after APC-on resolution; optional MTP separate |
| Dual-pod shard (per-pod `Semaphore(16)`, deterministic index split, shard-set in fingerprint) | ~1.9× on remaining wall | Packaged CONSERVATIVE; meta-review also lists under conditional (infra + fingerprint) |

### MODERATE (SYNTHESIS §3)

| Lever | Claimed effect | Notes |
|-------|----------------|-------|
| Metadata-fail short-circuit | ~1341 s (1047 fusion-dead unit calls) | Fail tier = full skip; review tier = policy (keep 1 top unit or report-only) |
| Escalation dedupe | ~23 s | 18/18 escalations duplicated a unit check; hygiene |
| Verdict-first / conditional `reasoning` on pass-path | ~180-360 s (overlaps call elimination) | ~55 of ~77 output tokens unused on 70% pass units |
| MTP speculative decoding | Decode speedup (batch-shape sensitive) | Explicitly A/B-gated inside MODERATE |

### AGGRESSIVE (SYNTHESIS §3)

| Lever | Claimed effect | Notes |
|-------|----------------|-------|
| Deterministic metadata/outline diff (P131) | ~471 s (377 calls) | Cheapest AGGRESSIVE item; needs A/B that LLM adds nothing |
| Router tightening | Part of ~300-500 s band | Full A/B revalidation per lever |
| Dense-judge offload | Part of ~300-500 s band | Quality risk; separate from long-term distill |

### Long-term (separate program; not in near-term packages)

| Lever | Claimed effect | Notes |
|-------|----------------|-------|
| Distill unit-check → small dense judge on own pods | Only credible "docling-class" speed at quality bar | 6-12 weeks; ~1510 labeled judgments/cold run; CLAUDE.md fine-tune path |

**Package wall targets (unimplemented arithmetic):** CONSERVATIVE ~685-856 s
(11-14 min); MODERATE ~596 s central / 530-670 s (9-11 min); AGGRESSIVE
~300-500 s, **≤300 s not reliable**.

---

## 2. A/B-gated (or lane-version + A/B)

Quality gate (SYNTHESIS §4, corrected by 150-verifier): measure true 381-paper
A/A flip floor once; any prompt/schema/routing lever gates against that floor
+ dev-replay recall (35 labels) + untouched holdout. Scheduling/caching/sharding
only needs verdict-identity (sidecar byte-diff).

| Lever | Gate type | Why gated |
|-------|-----------|-----------|
| Guard-tag `HMAC(fleet_secret, pid)` + user-message reorder `[static][candidate_md][unit fields LAST]` | Lane-version bump + A/B (meta-review § conditional); SYNTHESIS §5 calls it "cache enablement" with lane bump | Touches prompts; secret-keyed only; tags out of author-readable artifacts (P45, 149 SAFE-WITH-CONDITIONS) |
| Metadata-fail / review short-circuit | Lane-version + A/B | Inspect reports lose 35 defect groups on 30 papers; verdicts unchanged when stripped (145) |
| Escalation dedupe | Lane-version + A/B (bundled with call elimination) | Touches which calls run |
| Verdict-first / conditional `reasoning` schema | Lane-version + A/B | Schema/prompt change; decode-bound material |
| MTP speculative decoding | Explicit A/B; MODERATE only | vLLM #42518 temp-0 divergence / batch-shape (P38/P103) |
| Deterministic metadata diff (P131) | Per-lever A/B (AGGRESSIVE) | Must prove LLM adds no findings the diff misses |
| Router tightening | Per-lever A/B (AGGRESSIVE) | Routing semantics |
| Dense-judge offload | Per-lever A/B (AGGRESSIVE) | Quality collapse risk |
| Dual-pod least-busy (opt-in) | Infra + fingerprint; fixed split is default | Fixed split loses ~950 s if one pod 50% busy (P140); shard SET not per-paper pod in fingerprint (P21) |

**Prerequisite before any lever claim:** fleet-window `/metrics` scrape (not
lifetime cross-tenant numbers). True 381-paper A/A flip floor once.

---

## 3. Rejected (with grounds)

| Lever | Grounds | Persona |
|-------|---------|---------|
| Multi-unit prompt packing | RuVerBench double-digit quality drops | P12 |
| sglang migration | ≥18 recent radix-cache correctness fixes; no verified single-node V4-Pro win | P113 |
| litellm as dependency | 435 packages; fights `ModelBackend` contract (copy patterns only) | P144 |
| vLLM offline `run_batch` | Cannot target a running server | P41 |
| HTTP tuning | Garbage / noise | P27 |
| Prompt compression | Garbage; ≤13 s | P33 |
| Cross-paper memoization | Garbage; 0/116 revision pairs identical | P36 |
| Chunk parallelism | 0 papers chunk post-strip; serial rationale stale but dormant | P30 |
| Guided JSON as a **speed** lever | ~100 s ceiling; drift risk | P74/P95 |
| Deeper client queues (c>32 / submit-all) | 32 in-flight right for 16 MoE slots behind RunPod proxy; proxy 524 / 600s risk | P71/P77; cold-run baseline forbids |
| Drop monolith / "monolith redundancy" package lever | Verdict delta without cnf-findings **1/181** (not 4/181); wall **226 s / 7.5%** (not 17%); cheap insurance, kept | P16 vs 147; lever **dropped from packages** |
| Drop verification / shrink model / accept partials | Different workload class; "gleiche Qualität" forbids | Anti-steelmans P57/P69/P81/P91/P121/P126 |
| Raise server slots to 32 | **+57% wall** (forbidden) | cold-run `00-baseline` / slots-32-regression |
| APC "turn it on" as the main lever | APC already ON (96.66% lifetime hit); remaining is **our** random guard tag + layout | P40/P100 WRONG after 146 probe |

---

## 4. Internal contradictions (personas / packaging)

### Resolved by meta-review (do not re-litigate; cite resolution)

| Topic | Conflict | Resolution |
|-------|----------|------------|
| **Prefix cache on vs off** | P15/P40/P100: APC off. P96/P93 + 146 live `/metrics`: `enable_prefix_caching=True`, **96.66%** hit / 131,568 reqs | **APC is ON.** Server-flag delta shrinks to MBT 16384 + retention (+ optional MTP). Random per-call guard tag still zeroes **in-paper** document-prefix reuse |
| Prefill-bound vs decode-bound | P93: prefill-bound (~17 of 20 s). Live: mean queue/prefill/decode/E2E = 2.38 / 0.46 / 5.91 / 9.01 s | **Decode + queue bound.** Output-token discipline and call elimination outrank further prefill levers. P93 stands only as APC-miss counterfactual |
| P15 wall claim | 600-1100 s from "enable APC" | DOWNGRADED to in-paper document-prefix share only ("few hundred s" in SYNTHESIS) |
| Monolith drop | P16 redundancy vs 147 replay | Keep monolith; drop lever from packages |
| Metadata short-circuit | P17/P34 vs 145 | CONFIRMED-MODIFIED: 0 verdict/fusion drift; inspect cost real; split fail vs review policy |
| Stacking arithmetic | P48 vs 148 | P48 ~12% optimistic; MODERATE ~596 s central |
| Quality flip floor | P47 "≥25%" vs 150 | 25% from 20 borderline PIDs, not fleet A/A; measure 381-paper floor once |

### Still-open packaging contradictions (SYNTHESIS vs opus-A / §3 vs §5)

| Topic | Side A | Side B | Gap for cold-run |
|-------|--------|--------|------------------|
| **Guard-tag tier** | SYNTHESIS §3: CONSERVATIVE, "verdicts unchanged" | opus-A: under "conditional levers (lane-version + A/B)" | Treat as **lane bump + A/B**, not a pure free win |
| **Verdict-first schema tier** | §3 MODERATE package | §5 step 5 lists it with optional AGGRESSIVE items | Prefer **MODERATE + A/B**; §5 ordering slip |
| **MTP tier** | §3 inside MODERATE (A/B-gated) | §5 step 5 with AGGRESSIVE optional list | Prefer **MODERATE, hard A/B gate**; do not ship without batch-shape proof |
| **Dual-pod tier** | §3 CONSERVATIVE | opus-A conditional; §5 step 4 after call elimination | Infra multiplier; fingerprint shard-set; confirm second pod alive before counting 1.9× |
| Lifetime metrics vs fleet-window | Several personas used lifetime `/metrics` | 146 caveat + SYNTHESIS §4: cross-tenant; scrape per lever | Any new serving claim needs fleet-window scrape |

---

## 5. Top 5 still-open high-impact items

Ranked for cold wall toward ~10 min (MODERATE band). All still paper-only
pending HEAD census + A/B / infra checks.

1. **Metadata-fail short-circuit (~1341 s)** — largest verified call cut; 0
   verdict/fusion drift when stripped; A/B for inspect-report policy on
   review tier.
2. **HMAC guard tag + prompt reorder (few hundred s in-paper APC reuse)** —
   APC already on; our random tag + unit-fields-first layout is the miss.
   Lane-version + A/B; secret-keyed only.
3. **Dual-pod sharding (~1.9× on remaining wall)** — biggest infra multiplier
   after call cuts; needs live second pod, per-pod Semaphore(16), shard-set
   fingerprint. Confirm `h200x8-deepseek-v4-pro` (or equivalent) alive.
4. **Verdict-first / terse pass-path schema (~180-360 s, overlaps #1)** —
   decode-bound pod; 70% zero-defect units emit unused `reasoning`. A/B
   schema gate. (MTP sits beside this as decode lever; harder A/B.)
5. **CONSERVATIVE free-win stack (tombstones, `wait_for`, `to_thread`+token
   cache, LJF, timing)** — small cold-wall add (~90-220 s client stalls +
   tail); tombstones dominate **warm** (65→10-15 s). Ship first for zero
   semantics risk, then layer #1-#4.

**Honorable AGGRESSIVE #6:** deterministic metadata/outline diff (~471 s) if
A/B shows the LLM adds nothing — cheapest path if MODERATE undershoots ≤600 s.

**Not open as "turn APC on":** prefix caching is already enabled; that
contradiction is closed.
