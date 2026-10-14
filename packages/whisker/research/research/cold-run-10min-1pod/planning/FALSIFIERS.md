# FALSIFIERS — Load-bearing SYNTHESIS claims

**Date:** 2026-07-24  
**Source of claims:** [`SYNTHESIS.md`](../SYNTHESIS.md)  
**How to use:** each row is a claim that the plan banks on. The falsifier is a concrete measurement or probe that would kill that claim (or the option that depends on it). Prefer matched-occupancy cold fleets per [`MEASUREMENT-PROTOCOL.md`](MEASUREMENT-PROTOCOL.md).

---

## Physics and options

| # | Claim (SYNTHESIS) | Cite | Falsifier (concrete) |
|---|-------------------|------|----------------------|
| P1 | ≤10 min cold on **one** V4-Pro @ S=16 is below the quality-preserving physics floor; front-end alone is 758×20/16 = **948 s** | `17`, Verdict table | Instrumented MoE-only MODERATE cold (full 381, `--force`, matched `/metrics`) finishes **≤650 s** with monolith + metadata still running → floor model wrong; reopen MoE-only ≤10 min. If wall stays **≥900 s** while N_front≈758 and L≈20 hold → floor stands. |
| P2 | Under the twin ban, the only arithmetic ≤10 min path is `wall = max(T_moe, T_dense)` on an **already-running** dense Alliance endpoint (not a second V4-Pro) | `12`, `20`, Verdict | Twin stays forbidden **and** dense stays 404 **and** MoE-only still hits ≤600 s → P2 false (physics/census wrong). Or: dense live, scoping+parity pass, but instrumented B wall **>620 s** with dense idle and MoE saturated → heterogeneous model wrong (not “Option B dies”, Option B’s wall model dies). |
| P3 | Dense pods all **HTTP 404**; only `alliance-pod` UP → Package C / Option B **infra-blocked** | `26`, LIVE BLOCKER | `GET /v1/models` (or health) on `h200-qwen3-32b` returns **200** + model id match + one unit-check completion → infra blocker lifted; Option B unblocked. If all four dense stay 404 after ops “restart” → blocker still true. |
| P4 | Without dense (or if ops will not restart): honest SLA **~15–20 min** after MoE package; ≤10 min impossible at quality | Verdict, ADR-018 | After full MoE package (v11 SC + det-metadata + verdict-first + router + Tier-1), matched cold wall **≤600 s** → 15–20 SLA language is too pessimistic; reopen 10-min claim. If wall **>25 min** after that package with quiet pod → MoE package EV overstated (Option A under-delivers). |

---

## v11 / baseline

| # | Claim | Cite | Falsifier |
|---|-------|------|-----------|
| V1 | Working-tree `_LANE_VERSION = 11` metadata short-circuit buys **−1059 to −1341 s** vs v10 | `10`, What v11 buys | Cold remeasure on local v11 still **~3000 s** (≈ v10 3003 s band) with SC enabled and quiet pod → short-circuit **not landed** or not firing. If wall drops only ~few minutes → SC partial / wrong corpus. |
| V2 | Expected cold after v11 alone: **~21–25 min**, not 3003 s | `10`, `18` MODERATE band | Remeasured v11 cold **>45 min** (still ~50 min class) with SC on → “v11 already buys” claim dies; do not stack further wins on a fake baseline. If v11 cold **≤15 min** MoE-only → census/L assumptions wrong. |
| V3 | Remeasure before claiming further wins | Execution order §1 | Any lever A/B that cites v10 3003 s as A without a post-v11 A → invalid attribution (process falsifier). |

---

## Package rollups @ S=16

| # | Claim | Cite | Falsifier |
|---|-------|------|-----------|
| R1 | CONSERVATIVE central **~2163 s** | `18` | Quiet-pod CONSERVATIVE cold outside **~1800–2500 s** by a wide margin without explaining occupancy → rollup wrong. |
| R2 | MODERATE central **~1366 s** (~23 min); pess. ~1493 s | `18`, `17` | Quiet-pod MODERATE cold **≤650 s** → R2/P1 wrong. Quiet-pod MODERATE **>1800 s** with N≈1419 → L_eff or SC accounting wrong. |
| R3 | AGGRESSIVE realistic (with dense) **~715–910 s**; bare optimistic **~585 s** (hairline) | `18`, Verdict | Dense live + scoping + parity pass, yet instrumented AGGRESSIVE cold **>1100 s** with matched occupancy → do not bank 715/585. If cold **≤550 s** repeatedly → bare optimistic understates headroom (still require quality gates). |
| R4 | Full AGGRESSIVE stack planning central **~680 s** (585–910) still **No** for ≤600 s in planning table | Verdict | Single quiet B run **≤580 s** **and** quality gate pass → planning “No” for ≤600 becomes “Yes (measured)”; still require repeat before marketing. |

---

## Heterogeneous design (Option B)

| # | Claim | Cite | Falsifier |
|---|-------|------|-----------|
| H1 | Split ~428 MoE / ~1879 dense; at 2× scoped dense decode, wall ≈ **max(~476 s MoE, ~207–511 s dense)** → MoE-bound **~511 s** if scoping + parity land | `12`, `20` | Dense returns **200**, scoping live, but `call_timings` show dense leg **>600 s** while MoE **<500 s** → not MoE-bound; Option B wall target dies unless dense S/L fixed. If MoE leg **>650 s** after offload → MoE census/cuts wrong. |
| H2 | Without **payload scoping** (~10–15k/unit), dense collapses to S≤16, L≈20 → **negative EV** | `23`, Hard blockers | Scoped payloads deployed, dense still stuck at effective S≤16 and dense wall **> MoE wall by ≫100 s** → scoping failed as enabler. If **unscoped** dense still delivers S≫16 and B ≤620 s → H2 overstated (still prefer scoping for stability). |
| H3 | Ship requires **381/381 fused-verdict parity** + 16 flip-set equivalence | `19`, Hard blockers | Dense pod **200** but `flip_AB > flip_AA + margin` on four-component vector **or** holdout/dev-replay fail → **Option B dies** (quality), even if wall ≤600 s. |
| H4 | Primary dense = **Qwen3-32B** (`h200-qwen3-32b`); avoid `b200x2-gemma4` (wording false-fail), `b200-r1` (thinking overhead); reserve `b300-qwen36-27b` after A/B | `05f`, Hard blockers | Gemma-4 as primary passes 381 parity **and** beats Qwen3-32B wall without wording false-fail rate → avoid-primary claim dies. R1 as primary with thinking off matching Qwen latency+parity → R1 ban softens. |
| H5 | Dense offload EV **−850 to −1200 s** vs MoE-only (post-v11) | Remaining levers #1 | Dense live + scoping + parity, but MoE-only vs heterogeneous delta **<400 s** wall → EV overstated; Option B may still hit 10 min but not via that savings band. |

---

## MoE-only levers

| # | Claim | Cite | Falsifier |
|---|-------|------|-----------|
| M1 | Deterministic metadata **−~471 s** (HTML-first staging ~251 s) — A/B only | `13`, `22` | Shadow A/B: fused verdict / outline disagree materially on >5% **or** any holdout fused flip → do not enable; −471 s not bankable. If enabled and quiet wall drop **≪200 s** → savings overstated. |
| M2 | Verdict-first / schema-slim **−124 to −155 s** | `15`, `05n` | Holdout fails **or** quiet wall drop **<60 s** after ship → do not bank. |
| M3 | Router `combo_safe` + dynamic quota **−190 to −310 s** | `14` | Fail **3/381** or **16/381** holdout gates → router stays off. Pass gates but wall drop **<100 s** → savings overstated. |
| M4 | Server ops alone: max **~422 s** post-SC → still ~25 min; Tier-1 yes; **never** `--max-num-seqs`>16 | `16`, `00` | Raising S>16 **reduces** quiet cold wall without +57% class regression → S=16 forever claim weakens (still policy-forbidden unless re-measured). Tier-1 flags with **0%** tok/s / wall move → do not bank DeepEP ~10–15%. |
| M5 | Call-class fingerprints (`25`): **0 s** on first greenfield cold; warm/prompt-edit only | `25` | First greenfield cold with fingerprints enabled shows material wall cut vs identical config without → claim dies. |

---

## Reject / do-not-bank ledger

| # | Claim | Cite | Falsifier |
|---|-------|------|-----------|
| X1 | Skip monolith = **No** (fusion false-clears; 10 min reachable without) | `21` | Heterogeneous path already ≤600 s **without** skip, **and** a controlled monolith-skip A/B shows **zero** fusion false-clears on 381 + holdout → reopen (high bar). False-clears on skip → reject stands. |
| X2 | `--det-skip` default = **No** (advisory opt-in; ~250–350 s) | `24` | Default-on det-skip passes full `19` gate with no fused false-clears → default ban softens. |
| X3 | `VLLM_BATCH_INVARIANT` = **No** (~50% throughput hit) | `05v` | BI mode on quiet pod shows wall **≤** non-BI within noise **and** quality unchanged → reject weakens. If wall **~1.5×** → reject stands. |
| X4 | MTP wall savings = **A/B only**; short JSON @ c≈16 is lose/flat; **do not bank** | `05j` | Acceptance-gated MTP k=1 shows quiet cold **≥10%** wall cut with quality hold → can bank. Flat/lose → reject banking stands. |
| X5 | P/D disagg on one 8×H200 = **No** | `05k` | Working P/D on this single node with short-OSL workload beating S=16 continuous batch → reopen. |
| X6 | Flash unit-judge without new deploy = **No**; hosted Flash decode only **~1.7×** Pro (not 3.8× theory) | `05b`, `05z` | Alliance Flash endpoint appears **and** unit-judge A/B shows ≥2.5× wall cut on units with parity → deploy path reopens; 1.7× claim dies if measured ≫1.7× on our payloads. |
| X7 | Twin / S=32 / c>32 = **Forbidden** | Constraint | Operator lifts ban **and** remeasure shows S=32/c>32 win → policy claim changes (not a physics falsifier). Measured S=32 still regresses → forbid stands on evidence. |

---

## Think / client / noise

| # | Claim | Cite | Falsifier |
|---|-------|------|-----------|
| T1 | Non-think on unit checks only after A/B; never `reasoning_effort="low"` (maps High on DSV4) | `05a`, `05c` | `reasoning_effort="low"` on alliance-pod yields Non-think latency/token pattern **and** parity pass → mapping claim dies. Thinking forced on to “fix schema” improves schema **and** wall → client invariant guidance wrong. |
| T2 | Re-probe alliance-pod — prior probe may already be Non-think | Think-off § | Probe shows think-on (long reasoning tokens) on unit-shaped requests → assume Non-think savings still available; opposite → do not double-count think-off. |
| N1 | Shared-pod noise HIGH: ~2× wall if half slots stolen; ≥25% flip confound; never treat single A/B as truth without matched occupancy | `28` | Double-A under documented `external_in_flight≈0` shows `flip_AA ≤5%` **and** walls within ~10% → variance may be downgraded for that window only. Single A/B with stolen slots matching “lever win” → attribution falsified. |

---

## Option kill switches (summary)

| Option | Dies if… |
|--------|-----------|
| **A (MoE-only ≤10 min marketing)** | Always dead for ≤600 s while P1 holds; also dies if post-package wall still sold as ≤10 min. |
| **B (heterogeneous ≤10 min)** | Dense stays 404 (**P3**); **or** dense 200 but 381 A/B fails parity (**H3**); **or** scoping fails and dense negative EV (**H2**); **or** instrumented B **>620 s** quiet (**H1**/handoff). |
| **C (15–20 min SLA)** | Dense returns + B ≤620 s + quality pass → reopen 10-min program; **or** MoE package never gets wall into 15–20 band → SLA false (need longer published SLA). |

---

## Index

| Report | Used for |
|--------|----------|
| `SYNTHESIS.md` | Claim list |
| `17-physics-floor-skeptic.md` | 948 s / 1366–1493 s floors |
| `18-packages-1pod.md` | Package centrals |
| `10-impl-status-1pod.md` | v11 inventory |
| `12`, `20` | Heterogeneous wall |
| `19` | Parity gate |
| `23` | Payload scoping |
| `26` | Dense 404 probe |
| `28` | Shared-pod noise |
| `13`–`16`, `21`–`25`, `05*` | Lever / reject specifics |
