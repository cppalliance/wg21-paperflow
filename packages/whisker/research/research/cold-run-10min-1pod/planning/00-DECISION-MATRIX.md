# 00 — Decision matrix (cold-run ≤10 min, 1 MoE pod)

**Date:** 2026-07-24  
**Audience:** planning LLM  
**Sources:** `PLANNING-HANDOFF.md`, `SYNTHESIS.md`, numbered reports cited in Evidence column.  
**Rule:** numbers and statuses below are from those reports only; do not invent new wall figures.

---

## 1. Master decision table

| Decision | Options | Recommendation | Status | Evidence file IDs | Depends on |
|----------|---------|----------------|--------|-------------------|------------|
| **SLA target** | (a) Keep ≤600 s / ~10 min; (b) Reset to ~15–20 min honest MoE-only; (c) Publish ~12–23 min Option A band without 10-min claim | **Open fork:** ≤10 min only if dense restart + Option B; else Option C ~15–20 min. Do not promise ≤10 min on MoE alone. | **open** | `PLANNING-HANDOFF.md` §3–4; `SYNTHESIS.md` Verdict; `17-physics-floor-skeptic.md`; `18-packages-1pod.md` | Dense restart; Option A/B/C choice |
| **Architecture path (A/B/C)** | **A** MoE-only shippable (~12–23 min); **B** Heterogeneous cascade (~511 s design); **C** Reset SLA | If dense will restart → plan **B**; if not → **A+C** language in one plan. | **open** | `PLANNING-HANDOFF.md` §4; `SYNTHESIS.md`; `12-dense-offload-architecture.md`; `20-heterogeneous-wall.md` | Dense restart; SLA |
| **Twin V4-Pro / `h200x8-deepseek-v4-pro`** | Revive twin; keep forbidden | **Reject permanently** (budget/authority + 404). | **decided** | `00-baseline.md`; `PLANNING-HANDOFF.md` C1; `SYNTHESIS.md` Reject ledger | — |
| **MoE `--max-num-seqs` / S=32** | Keep S=16; raise to 32 | **Keep S=16 forever** on MoE. S=32 measured **+57%** wall. | **decided** | `00-baseline.md`; `PLANNING-HANDOFF.md` C2; `16-server-ops-1pod.md`; `research/slots-32-regression/` (manifest) | — |
| **Client concurrency c>32** | Keep c=32; raise c>32 | **Forbidden** (RunPod 524 / regression corpus). | **decided** | `00-baseline.md`; `PLANNING-HANDOFF.md` C3; `research/concurrency-381/` (manifest) | — |
| **Dense restart (`h200-qwen3-32b` min)** | Ask Alliance restart; wait; abandon 10-min | **Ask Alliance to restart at least `h200-qwen3-32b`.** All four dense endpoints **404** today; Package C infra-dead until then. | **blocked** | `26-dense-pod-liveness.md`; `PLANNING-HANDOFF.md` §7; `SYNTHESIS.md` LIVE BLOCKER | Ops authority / schedule |
| **Dense primary model** | `h200-qwen3-32b`; `b300-qwen36-27b`; `b200x2-gemma4`; `b200-r1` | **Primary: Qwen3-32B (`h200-qwen3-32b`).** Reserve `b300-qwen36-27b` after A/B. **Avoid** Gemma-4 (wording false-fail) and R1 (thinking overhead) as primary unit judge. | **decided** (model choice); **blocked** (liveness) | `12-dense-offload-architecture.md`; `05f-web-dense-judge-lit.md`; `SYNTHESIS.md` Think-off / dense class | Dense restart |
| **Dense offload / heterogeneous cascade** | MoE-only; route units+metadata to dense; same-pod MoE→MoE cascade | **Design: T0 CPU → T1 dense units (± metadata LLM) → T2 MoE monolith/HTML/oversize/escalate ≤15%.** Same-pod MoE→MoE cascade **rejected**. Ship only after liveness + scoping + parity. | **blocked** | `12-dense-offload-architecture.md`; `20-heterogeneous-wall.md`; `05e-web-single-endpoint-judge.md`; `05l-web-cascade-papers.md`; `05p-web-frugalgpt.md` | Dense restart; payload scoping; quality gate `19` |
| **Payload scoping (dense S unlock)** | Full `candidate_md` each unit; H2±1 + presence index ~10–15k; skip scoping | **Ship H2 window + presence index (~10–12k / soft 8k–hard 12k chars); oversize → MoE fallback.** Without scoping dense stays S≤16, L≈20 s → **negative EV**. | **open** (design ready; blocked on dense for EV) | `23-payload-scope-dense.md`; `12-dense-offload-architecture.md`; `SYNTHESIS.md` Hard blockers | Dense restart for throughput win; can prototype on MoE path independently |
| **Escalate fraction (cascade)** | Escalate all units to Pro; escalate ≤15%; no escalate | **Escalate ≤15%** units to Pro; predictive route. | **decided** (policy); **blocked** (needs dense live) | `SYNTHESIS.md`; `05l-web-cascade-papers.md`; `05p-web-frugalgpt.md`; `12-dense-offload-architecture.md` | Dense cascade ship |
| **v11 metadata short-circuit (working tree)** | Ship as baseline; remeasure first then ship; discard | **Remeasure cold on local v11, then commit/ship as baseline.** Est. cold ~21–25 min (not 3003 s). | **open** (ops schedule; code landed) | `10-impl-status-1pod.md`; `PLANNING-HANDOFF.md` P0–P1; `SYNTHESIS.md` What v11 already buys | Remeasure protocol |
| **Deterministic metadata (det-metadata)** | Keep LLM metadata; HTML-first det then fleet; fleet-wide day-1; reject | **A/B only:** implement `compare_metadata_outline()`; **HTML-first staging (~251 s)** then fleet (~471 s @ S=16). Ship iff ≤5% metadata drift **and** zero fused-verdict changes. | **A-B** | `13-deterministic-metadata.md`; `22-html-vs-pdf-mix.md`; `SYNTHESIS.md` Remaining levers #2 | v11 baseline; holdout parity |
| **Verdict-first / schema bifurcation** | Keep full `UnitCheck` always; `UnitCheckClear` → fail-path `UnitCheckDefects`; max_tokens-only | **Schedule after det-metadata.** Full MODERATE stack ~**−124 to −155 s** (~−92 s bifurcation alone post-v11). Holdout gate. | **A-B** | `15-verdict-first-design.md`; `05n-web-v4-structured.md`; `SYNTHESIS.md` #3 | Det-metadata schedule (handoff order); holdout |
| **Router combo_safe + dynamic MAX_UNIT_CHECKS** | combo_safe only; static cap 3; dynamic quota; combined; blind cut 289 | **Combined dynamic + combo_safe:** ~**−150–250 calls / −190–310 s**. Gate on **3/381** cap drivers + **16/381** flip-set. Do not harvest full 289 fusion-dead band blind. | **A-B** | `14-router-quota-1pod.md`; `PLANNING-HANDOFF.md` checklist #6 | Holdout 3/381 + 16/381; preferably after verdict-first per phase order |
| **Skip monolith** | Fleet skip; conditional skip when metadata+units suffice; keep monolith | **Reject permanently** as default / quality path. Savings real but fusion false-clears; 10 min reachable without it (`21`). | **decided** | `21-skip-monolith-revisit.md`; `PLANNING-HANDOFF.md` C5; `SYNTHESIS.md` Reject ledger | — |
| **Default `--det-skip` / LLM-skip mode** | Default on; advisory opt-in; reject | **Advisory opt-in only; never default.** ~250–350 s class if used. | **decided** | `24-det-skip-llm.md`; `SYNTHESIS.md` Reject ledger | — |
| **Server Tier-1 (MBT / CUDA graphs / APC)** | No ops; Tier-1 flags; raise S to “fix” underfill | **Yes Tier-1:** MBT **16384**, decode CUDA graphs, EP/APC per checklist. Never raise S. Server alone max ~422 s post-SC → still ~25 min. | **open** (ops ask) | `16-server-ops-1pod.md`; `05d-web-single-node-serving.md`; `SYNTHESIS.md` Server ops | Alliance ops access to `alliance-pod` |
| **DeepEP (`deepep_low_latency`)** | Default AGRS; enable DeepEP-LL; DeepEP + DBO always | **Plan ~10–15% tok/s (~12% planning number) from DeepEP-LL at S=16.** DBO usually **flat** at seqs=16 unless ≥32 concurrent decode tokens. | **A-B** (ops) | `05t-web-dbo-deepep.md`; `16-server-ops-1pod.md`; `SYNTHESIS.md` Reject / do-not-bank | Server Tier-1; confirm current all2all backend |
| **`--enable-dbo`** | On with DeepEP; off at S=16; threshold-gated | **Usually flat at seqs=16;** enable only if DEP thresholds fire / effective tokens ≥32. | **decided** (default off / gated) | `05t-web-dbo-deepep.md`; `SYNTHESIS.md` | DeepEP config |
| **MTP (speculative decoding)** | Bank MTP wall cut; k=1 A/B; k=2 recipe; reject forever | **A/B only, k=1; do not bank seconds.** Short JSON @ c≈16 is lose/flat zone. Verify MTP head present + acceptance under load. | **A-B** | `05j-web-mtp-short-json.md`; `SYNTHESIS.md` Reject ledger; `16-server-ops-1pod.md` | Server ops window; acceptance metrics |
| **Ngram / PLD as MTP substitute** | Use as primary; marginal A/B; reject | **Marginal** (~37–75 s; keys only). Not a plan pillar. | **decided** (do not bank) | `05w-web-ngram-spec.md`; `SYNTHESIS.md` | — |
| **Non-think on unit checks** | Force Non-think; leave High; use `reasoning_effort="low"` | **Probe then A/B:** `chat_template_kwargs.thinking=false` / `enable_thinking=false` / `reasoning_effort="none"`. **Never** `reasoning_effort="low"` (maps to High on DSV4). Re-probe alliance-pod (may already be Non-think). | **A-B** | `05q-web-official-think-off.md`; `05a-web-nonthink.md`; `05c-web-reasoning-effort.md`; `05y-web-cn-forums.md`; `SYNTHESIS.md` | Probe kwargs; unit-check A/B quality |
| **Flash (V4-Flash unit judge)** | Deploy Flash; use if Alliance has endpoint; reject without deploy | **Yes if deployed + A/B; no Alliance Flash endpoint today** → out of budget path. Hosted prior: Flash decode ~**1.7×** Pro (not 3.8× theory). | **blocked** (no endpoint) | `05b-web-flash-vs-pro.md`; `05z-web-hosted-latency.md`; `SYNTHESIS.md` | New Flash deploy / weights |
| **`VLLM_BATCH_INVARIANT` (BI mode)** | Enable for stability; enable for speed; keep off | **Reject for speed path** (~50% throughput hit). Quality-stability ≠ bit-exact. | **decided** | `05v-web-batch-invariant.md`; `28-shared-pod-noise.md`; `SYNTHESIS.md` | — |
| **P/D disagg on one 8×H200** | Enable P/D; reject | **Reject** (short OSL; can't split node). | **decided** | `05k-web-pd-disagg.md`; `SYNTHESIS.md` | — |
| **Server `guided_grammar` / speculative `guided_json`** | Enable guided; stay schema-in-prompt | **Stay schema-in-prompt.** Guided path is the slow trap. | **decided** | `05i-web-community-workarounds.md`; `SYNTHESIS.md` | — |
| **Client thinking + `json_object` invariants** | Mix thinking.enabled with json_object; thinking.disabled + reasoning_effort; enable thinking to fix schema | **Never** `thinking.enabled` with `json_object`; **never** `thinking.disabled` + `reasoning_effort` (400); do not enable thinking to fix schema. | **decided** | `05y-web-cn-forums.md`; `SYNTHESIS.md` | — |
| **CSA/HCA / paper efficiency switches** | Seek hidden 3.7× switch; treat as already on | **Already on with V4-Pro weights; no hidden switch.** | **decided** | `05x-web-v4-paper-efficiency.md`; `SYNTHESIS.md` | — |
| **Async scheduling underfill** | Keep async; try `--no-async-scheduling` if underfill; raise S | If `running≈16` + elevated waiting + soft util under c=32 → **try `--no-async-scheduling`**. Never raise S to “fix” underfill. | **A-B** | `05s-web-async-sched.md`; `SYNTHESIS.md` | `/metrics` confirmation |
| **Distill timing (Path F / SFT judge)** | Distill first for 3×; dense+scoping first; distill only if quality fails | **Distill only if Path F (scoped dense + short pass tokens) fails 381 gate.** Off-shelf dense + scoping is faster path; ~1510 labels/run below JudgeLM floor for ship claim. | **open** (timing gate) | `05g-web-slmjury.md`; `SYNTHESIS.md` Execution order #5; `PLANNING-HANDOFF.md` P8 | Dense cascade + quality gate `19` outcome |
| **Quality gate / parity protocol** | Ship without 381 gate; full `19` protocol; wall-only gate | **Ship bar:** fleet flip ceiling + dev-replay recall + holdout anchors. Validation wall ~**0.8–1.2 h**. Quality pass ≠ ≤600 s; instrumented B ≤620 s to claim 10 min. | **decided** (protocol); **open** (when to run B) | `19-quality-gate-1pod.md`; `PLANNING-HANDOFF.md` §10 | Det-metadata and/or dense bundle under test |
| **Measurement protocol (shared-pod noise)** | Single A/B anytime; off-hours + `/metrics` matched occupancy; double-A | **HIGH variance risk.** Measure cold runs **off-hours** with `/metrics` matched occupancy; never treat single A/B as ground truth without matched occupancy. Double-A for noise floor. | **decided** (protocol); **open** (schedule windows) | `28-shared-pod-noise.md`; `PLANNING-HANDOFF.md` checklist #10; `19-quality-gate-1pod.md` | Ops calendar; metrics access |
| **Call-class fingerprints** | Use for cold cut; warm/rerun only | **Not cold path:** 0 s first greenfield; helps prompt-edit reruns only. | **decided** | `25-call-class-fingerprint.md`; `SYNTHESIS.md` | — |
| **Ideal-verify deletion as 10-min lever** | Cut ideal-verify for wall; ignore | **Reject as 10-min lever** (~60–90 s only; 3/381 papers). | **decided** | `29-ideal-verify-fleet-cost.md`; `PLANNING-HANDOFF.md` §8 | — |
| **Images / VLM** | In scope; out of scope | **Out of scope.** | **decided** | `PLANNING-HANDOFF.md` C6 | — |
| **Package rollup target (planning envelope)** | CONSERVATIVE ~2163 s; MODERATE ~1366 s; AGGRESSIVE realistic ~715 s; bare optimistic ~585 s | **Plan on MODERATE for MoE-only; AGGRESSIVE realistic (~715 s) only with dense+gates; do not bank ~585 s hairline.** | **open** (which package to commit) | `18-packages-1pod.md`; `11-wall-arithmetic-1pod.md`; `SYNTHESIS.md` Package rollups | SLA + dense restart |
| **Physics floor (MoE-only ≤10 min)** | Claim MoE-only 10 min possible; treat as impossible at quality | **Impossible at quality.** Front-end alone **948 s**; MODERATE survivors ~**1366–1493 s**. | **decided** | `17-physics-floor-skeptic.md`; `PLANNING-HANDOFF.md` §3 | — |

---

## 2. Blocked until infra vs can ship on `alliance-pod` alone

### 2a. Blocked until infra (dense restart and/or new deploy)

Requires Alliance ops to bring up at least one dense endpoint (`h200-qwen3-32b` minimum per `26-dense-pod-liveness.md`), and/or a Flash deploy not present today.

| Decision | Why blocked | Evidence |
|----------|-------------|----------|
| SLA ≤600 s claim | Only heterogeneous `max(T_moe, T_dense)` path is ≤10 min candidate; dense pods all 404 | `17`, `20`, `26`, `SYNTHESIS.md` |
| Option B heterogeneous cascade | ~1879 calls routed to dense; zero dense pods live | `12`, `26` |
| Dense primary model (live use) | Model choice decided; pods down | `12`, `05f`, `26` |
| Dense offload EV / S=32–48 on dense | Needs live dense + scoping | `23`, `12` |
| Cascade escalate ≤15% (production) | Needs dense T1 lane | `12`, `05l`, `05p` |
| Flash unit-judge | No Alliance Flash endpoint | `05b`, `05z` |
| Distill-as-unblocker for 10 min | Distill is fallback **after** Path F dense fails gate — still needs dense (or long SFT program) | `05g`, `SYNTHESIS.md` P8 |
| Instrumented B ≤620 s “10 min claim” | Config B assumes dense offload live | `19`, `PLANNING-HANDOFF.md` §10 |

**Infra ask (minimum):** restart `h200-qwen3-32b` so `GET /v1/models` returns 200 with configured model id + unit-check smoke (`26-dense-pod-liveness.md`). Twin V4-Pro remains forbidden even if it comes back (`00-baseline.md`).

### 2b. Can ship on `alliance-pod` alone

No second MoE pod; no dense dependency for these rows. Still subject to quality A/B and measurement protocol where Status = A-B.

| Decision | Ship note | Evidence |
|----------|-----------|----------|
| Keep twin forbidden / S=16 / c≤32 | Already constraints | `00-baseline.md` |
| Reject skip monolith, default det-skip, BI, P/D, guided_grammar, bank MTP, Flash-without-deploy | Reject ledger | `SYNTHESIS.md`, `21`, `24`, `05v`, `05k`, `05i`, `05j`, `05b` |
| v11 short-circuit baseline | Remeasure then commit | `10`, handoff P0–P1 |
| Det-metadata HTML-first → fleet | A/B gate; −~251 then −~471 s | `13`, `22` |
| Verdict-first bifurcation | After det-metadata; holdout | `15`, `05n` |
| Router + dynamic quota | Holdout 3/381 + 16/381 | `14` |
| Server Tier-1 (MBT, CUDA graphs, APC) | Ops on alliance-pod; not enough alone | `16`, `05d` |
| DeepEP-LL (~10–15% tok/s) + gated DBO | Ops A/B at S=16 | `05t`, `16` |
| MTP k=1 A/B (no banked seconds) | Ops acceptance gate | `05j` |
| Non-think probe + unit A/B | Confirm kwargs on alliance-pod | `05q`, `05a`, `05c` |
| Async-scheduling probe | Metrics-triggered | `05s` |
| Measurement protocol (off-hours + `/metrics`) | Required for honest A/B | `28`, `19` |
| Option A MoE package + Option C SLA language | Honest ~15–20 min if dense stays down | `PLANNING-HANDOFF.md` §4, §12 |
| Call-class fingerprints / ideal-verify cut | Non-goals for cold 10-min | `25`, `29` |

**Honest MoE-only outcome if dense stays down:** after MoE package, publish **~15–20 min** SLA; ≤10 min remains impossible at quality (`SYNTHESIS.md`, `17-physics-floor-skeptic.md`).

---

## 3. Planner must resolve

Open / blocked / A-B rows that still need an explicit plan answer (decided rejects omitted).

| Decision | Status | What planner must answer | Evidence |
|----------|--------|--------------------------|----------|
| **SLA target** | open | Keep ≤10 min (requires dense restart commitment) **or** reset to ~15–20 min (Option C)? | `PLANNING-HANDOFF.md` §5 #1; `SYNTHESIS.md` |
| **Architecture path A/B/C** | open | Choose A, B, or C — or A+C if dense uncertain | `PLANNING-HANDOFF.md` §4, §12 |
| **Dense restart** | blocked / open | Yes / no / when for `h200-qwen3-32b`? | `26`; handoff §5 #2 |
| **Package rollup commitment** | open | Commit MODERATE-only vs pursue AGGRESSIVE (needs dense) | `18`, `11` |
| **v11 ship schedule** | open | Remeasure then commit yes? (handoff expects yes) | `10`; handoff §5 #3 |
| **Det-metadata schedule** | A-B | HTML-first then fleet timing + A/B owners | `13`, `22`; handoff §5 #4 |
| **Verdict-first schedule** | A-B | After det-metadata — calendar / ticket order | `15`; handoff §5 #5 |
| **Router/quota holdout** | A-B | Run 3/381 + 16/381 gates; combine with dynamic quota? | `14`; handoff §5 #6 |
| **Server Tier-1 ops** | open | Who applies MBT 16384 / CUDA graphs / DeepEP on alliance-pod? | `16`; handoff §5 #7 |
| **DeepEP / DBO** | A-B | Enable DeepEP-LL; leave DBO gated? | `05t`, `16` |
| **MTP** | A-B | Run k=1 A/B only (do not bank) — yes/no this ops window? | `05j`; handoff §5 #7 |
| **Non-think probe** | A-B | Confirm alliance-pod kwargs; unit-check A/B? | `05q`, `05a`; handoff §5 #8 |
| **Async scheduling** | A-B | Probe `--no-async-scheduling` if metrics show underfill? | `05s` |
| **Payload scoping** | open | Implement before dense returns (prep) or only after liveness? | `23`, `12` |
| **Distill timing** | open | Hold distill until Path F fails `19` gate (recommended) — confirm | `05g`; handoff P8 |
| **Quality gate Config B timing** | open | When to run ~0.8–1.2 h validation; require instrumented B ≤620 s for 10-min claim? | `19`; handoff §10 |
| **Measurement protocol windows** | open | Off-hours + matched `/metrics` occupancy for every cold A/B — who schedules? | `28`; handoff §5 #10 |
| **Flash** | blocked | Defer forever vs request Flash deploy (out of current budget path) | `05b`, `05z` |

---

*End of decision matrix. Next: `01-OPTIONS-ABC.md`, ADR cards, `INFRA-ASK.md`, `MEASUREMENT-PROTOCOL.md`.*
