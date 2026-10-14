# PLANNER FAQ — Cold run ≤10 min, 1 MoE pod

**Audience:** planning LLM writing the architecture/execution plan.  
**Date:** 2026-07-24  
**Rule:** Answers cite **this corpus only** (`research/cold-run-10min-1pod/`). File ids are basename stems (`17` = `17-physics-floor-skeptic.md`).  
**Entry points:** `PLANNING-HANDOFF.md`, `SYNTHESIS.md`, `FILE-MANIFEST.md`.

---

## Physics & why not ≤10 min (MoE-only)

### Q1. Why can we not hit ≤10 min on one V4-Pro pod alone?
**A.** Quality-preserving MoE-only floor is ~23 min (MODERATE ~1366–1493 s). Front-end alone (758 calls × 20 / 16) is already **948 s** before any unit check. (`17`, `00`, `SYNTHESIS`)

### Q2. What is the measured cold baseline?
**A.** v10 cold wall **3003 s** (~48–50 min), ~2284 calls (~6/paper), L≈20 s, S=16, client c=32. (`00`, `PLANNING-HANDOFF`)

### Q3. What does “physics floor” mean here?
**A.** Irreducible wall under S=16 + quality-bounded call census: ~16 min (monolith+metadata only) to ~23 min (MODERATE survivors N≈1419). 10 min needs violating S=16, fantasy solo tok/s, or dropping verification. (`17`)

### Q4. Is loaded decode alone already over 10 min?
**A.** Yes for quality survivors: loaded decode physics ≈ **672 s** at ~19 tok/s/user before prefill/queue; full MODERATE wall still ~1366–1493 s. (`17`)

### Q5. Why is solo ~70 tok/s a false planning number?
**A.** That is batch=1 ITL. Under S=16 continuous batching, per-user is ~19 tok/s. Using 70 collapses wall into fantasy (~183 s). (`17`)

### Q6. What is the only arithmetic path under the twin ban that can claim ≤600 s?
**A.** Heterogeneous wall `max(T_moe, T_dense)` with an already-running dense Alliance endpoint + scoping + parity — not a second V4-Pro. Design central ~511 s. (`12`, `20`, `SYNTHESIS`)

---

## Twin ban, S=32, concurrency

### Q7. Why is a twin / second V4-Pro forbidden?
**A.** Operator hard constraint (2026-07-24): no budget/authority to revive `h200x8-deepseek-v4-pro`. Plans assume only `alliance-pod`. (`00`, `PLANNING-HANDOFF` C1)

### Q8. Why not raise `--max-num-seqs` to 32?
**A.** Measured **+57%** cold wall at c=32. S stays 16 forever on MoE. (`00`, `PLANNING-HANDOFF` C2; also `05s`)

### Q9. Why not raise client concurrency above 32?
**A.** Forbidden: RunPod 524 / TTFT regression corpus. c≤32. (`00`, `PLANNING-HANDOFF` C3)

### Q10. Can async-scheduling underfill be “fixed” by opening S to 32?
**A.** No. Underfill means S_eff &lt; advertised S; raising S worsens MoE expert-union batch. A/B `--no-async-scheduling` if metrics show underfill; never raise S. (`05s`)

---

## Dense offload & why dense 404 matters

### Q11. Why pursue dense offload at all?
**A.** Only quality-preserving design that can approach ≤600 s: ~1879 calls → dense, ~428 stay on MoE; wall ≈ max(~476 s MoE, ~207–511 s dense) → MoE-bound ~511 s if 2× dense decode holds. (`12`, `20`)

### Q12. Is dense offload “a second pod”?
**A.** No. Second pod = identical V4-Pro replica (forbidden). Dense = different model on an already-paid Alliance endpoint in `SERVICES.toml`. (`00`, `12`)

### Q13. Why does dense HTTP 404 matter for the plan?
**A.** 2026-07-24 probe: all four dense endpoints return **404**; only `alliance-pod` is UP. Package B / AGGRESSIVE dense path is **infra-blocked**; ~82% of routed calls cannot land on dense. (`26`, `SYNTHESIS`)

### Q14. Which dense service is the primary ask to restart?
**A.** `h200-qwen3-32b` (Qwen3-32B). Minimum for offload pilot. (`26`, `12`, `INFRA-ASK` if present)

### Q15. Which dense models are reject / reserve?
**A.** Avoid primary: `b200x2-gemma4` (wording false-fail), `b200-r1` (thinking overhead). Reserve: `b300-qwen36-27b` after A/B. (`12`, `05f`, `SYNTHESIS`)

### Q16. What happens if dense stays down forever?
**A.** Option C: publish honest SLA **~15–20 min**; stop the 10-min program. MoE package can still ship. (`01-OPTIONS-ABC`, `PLANNING-HANDOFF`, `SYNTHESIS`)

---

## Packages & walls

### Q17. What are the package walls @ S=16?
**A.** CONSERVATIVE ~2163 s; MODERATE ~1366 s; AGGRESSIVE realistic ~715 s; bare optimistic ~585 s (hairline, unvalidated). (`18`, `SYNTHESIS`)

### Q18. Does AGGRESSIVE without dense hit 10 min?
**A.** No. MoE-only AGGRESSIVE realistic ~715–910 s (~12–15 min); full stacked central ~680 s still planning-misses ≤600. (`11`, `18`, `SYNTHESIS`)

### Q19. What does Option A promise?
**A.** MoE-only shippable path: ~12–23 min honest; **do not** claim ≤10 min. Levers: v11 → det-meta → verdict-first → router → Tier-1. (`01-OPTIONS-ABC`, `PLANNING-HANDOFF`)

### Q20. What does Option B require?
**A.** Dense restart + payload scoping (~10–15k/unit) + 381/381 parity (~0.8–1.2 h gate). Only ≤10 min design candidate. (`01-OPTIONS-ABC`, `12`, `19`, `23`)

### Q21. What is Option C?
**A.** SLA reset to **~15–20 min** if dense will not restart and twin stays forbidden; abandon ≤600 s as a committed deliverable. Still ship A levers so the label is real. (`01-OPTIONS-ABC`, `PLANNING-HANDOFF`)

---

## v11 status

### Q22. What is already in working-tree v11?
**A.** Metadata-fail short-circuit (−1059 to −1341 s), LJF, `to_thread`, monolith timeouts, tombstones (warm), partial HMAC/md-first. `_LANE_VERSION = 11`. (`10`)

### Q23. Expected cold wall after v11 (before more levers)?
**A.** ~1260–1493 s (~21–25 min), not 3003 s. Remeasure before banking further wins. (`10`, `SYNTHESIS`)

### Q24. Must the plan ship v11 as baseline?
**A.** Yes — P0 remeasure + P1 commit short-circuit as stable baseline before stacking det-meta/router. (`PLANNING-HANDOFF` §5–6)

---

## Deterministic metadata & det-skip

### Q25. What does deterministic metadata buy?
**A.** Eliminate 377 metadata LLM calls → **~471 s** @ S=16. Orthogonal to v11 short-circuit (which skips units on metadata fail). (`13`)

### Q26. Is det-metadata shippable without A/B?
**A.** No. A/B-only: holdout parity, ≤5% metadata drift and zero fused-verdict changes. (`13`, `SYNTHESIS`)

### Q27. Why HTML-first for det-metadata staging?
**A.** HTML is 52.8% of papers; HTML-first det-meta ≈ **251 s**, then fleet ≈ **471 s**. Lower PDF outline noise risk in staging. (`22`, `SYNTHESIS` exec order)

### Q28. Can we default `--det-skip` (skip LLM on strong det)?
**A.** No as default cold path. Advisory opt-in only; modeled ~250–350 s; selection-gap blind spot. (`24`, reject ledger)

---

## Skip monolith

### Q29. Why not skip monolith to hit 10 min?
**A.** Rejected. Skip alone leaves MoE-only ~890 s; fusion false-clears (6 papers lose soft-review; 16 PDF lose mono-only defects). 10 min reachable without it once dense lands. (`21`, `PLANNING-HANDOFF` C5)

### Q30. Does monolith skip help under heterogeneous wall?
**A.** Only ~159 s margin (511→~352) because wall is `max(T_moe,T_dense)`. Quality cost unbounded by “metadata+units suffice.” Prefer det-meta instead. (`21`)

---

## Think-off, Flash, MTP, guided decoding

### Q31. How do we turn thinking off (official / vLLM)?
**A.** Hosted: `thinking: {type: "disabled"}`. vLLM: `chat_template_kwargs` `thinking=false` or `enable_thinking=false`; also `reasoning_effort="none"`. (`05q`, `05a`, `SYNTHESIS`)

### Q32. Why never `reasoning_effort="low"`?
**A.** On DSV4 it maps to High, not Non-think. (`05c`, `SYNTHESIS`)

### Q33. Should we bank Flash unit-judge speedups?
**A.** No without a deployed Flash endpoint. Alliance today serves Pro only. Hosted prior: Flash decode ~**1.7×** Pro (not 3.8× active-param theory); think on/off dominates wall. (`05b`, `05z`)

### Q34. Should we bank MTP wall savings?
**A.** No. Short structured JSON @ c≈16 is lose/flat zone; A/B k=1 only. Do not put MTP seconds in the plan arithmetic. (`05j`, `SYNTHESIS`)

### Q35. Why is server guided decoding rejected for speed?
**A.** Community + our path: `guided_grammar` / speculative `guided_json` is the slow trap (even ~0.1 tok/s cliffs). Stay schema-in-prompt + extract + retry. (`05i`, `SYNTHESIS`)

### Q36. Client invariant: thinking + json_object?
**A.** Never combine `thinking.enabled` with `json_object`; never `thinking.disabled` + `reasoning_effort` (400). Do not enable thinking to “fix” schema. (`05y`, `SYNTHESIS`)

---

## P/D, BI, DeepEP, ngram, async

### Q37. Why reject P/D disaggregation on one 8×H200?
**A.** Workload is decode-bound short OSL; cannot usefully split one node; PD loses on short-output shapes. (`05k`)

### Q38. Why reject `VLLM_BATCH_INVARIANT`?
**A.** ~50% throughput hit (upstream). Wrong tool for ≤10 min; quality-stability ≠ bit-exact. (`05v`, `28`)

### Q39. What tok/s can we plan from DeepEP at S=16?
**A.** ~**10–15%** from `deepep_low_latency` alone; central planning **~12%**. `--enable-dbo` usually flat at seqs=16 (needs ≥32 concurrent decode tokens). (`05t`)

### Q40. Is ngram/PLD a substitute for MTP?
**A.** Marginal (~37–75 s class); helps JSON keys only. Prefer MTP k=1 A/B on Pro; ngram as dense fallback. Do not bank as 10-min closer. (`05w`, `SYNTHESIS`)

### Q41. When try `--no-async-scheduling`?
**A.** If `/metrics` shows `running≈16` + elevated waiting + soft util under c=32 (underfill). Keep-or-disable A/B; never raise S. (`05s`)

---

## Cascade / FrugalGPT / Gemma

### Q42. What escalate rate should the dense cascade target?
**A.** Escalate ≤**15%** units to Pro (corpus ops target). Lit: ~70–85% stay on cheap model; escalation under ~30%. Prefer predictive route, not same-pod MoE→MoE. (`05p`, `05l`, `05e`, `SYNTHESIS`)

### Q43. Why reject Gemma-4 as primary unit judge?
**A.** Wrong class for structured unit checks: wording/`:::wording-remove`/`&lt;del&gt;` false-fail; JSON/grammar collapse risk. Qwen3-32B primary. (`05f`, `12`)

### Q44. Same-pod MoE→MoE cascade?
**A.** Rejected. Cheap hop must be a faster dense endpoint; cascade that still starts on V4-Pro does not help wall. (`05p`, reject ledger)

---

## Payload scoping, quality gates, HTML/PDF

### Q45. Why is payload scoping a hard blocker for Option B?
**A.** Without ~10–15k scoped unit payloads, dense collapses to S≤16, L≈20 s → negative EV vs keeping units on MoE. (`23`, `12`)

### Q46. What are the quality gates for AGGRESSIVE ship?
**A.** Fleet flip ceiling (flip_AB ≤ flip_AA + margin), dev-replay recall, holdout anchors; validation wall ~**0.8–1.2 h**. Quality pass ≠ ≤600 s; instrumented B ≤620 s to claim 10 min. (`19`, `PLANNING-HANDOFF` §10)

### Q47. Config A vs Config B for the gate?
**A.** A = MODERATE single-pod (~23–25 min). B = A + det-metadata + dense offload (~10–12 min if infra up; realistic B ~715 s). (`19`)

### Q48. Does HTML vs PDF mix get us to 10 min?
**A.** No. HTML 52.8% / PDF 47.2%; HTML already modestly cheaper. Leverage is port det-meta patterns, not “optimize HTML harder.” (`22`)

---

## Ideal verify, fingerprints, shared noise, distill

### Q49. Is ideal-verify a 10-min lever?
**A.** No. Fires on **3/381** papers; ~60–90 s direct. Deleting it cannot close the ~660–893 s post-v11 gap. (`29`)

### Q50. Do call-class fingerprints help cold first greenfield?
**A.** **0 s** cold. Warm/rerun / prompt-edit iteration only. (`25`)

### Q51. How bad is shared-pod noise on alliance-pod?
**A.** HIGH. Multi-tenant: ~2× wall if half slots stolen; ≥25% flip confound. Measure off-hours with `/metrics`; never treat single A/B as ground truth without matched occupancy. (`28`)

### Q52. When distill (SLMJury / JudgeLM path)?
**A.** Only if Path F (scoped dense + short pass tokens) fails the 381 gate. Distill is weeks; off-shelf dense is days. One cold run (~1510 labels) is below JudgeLM’s 3.5K floor. (`05g`, `SYNTHESIS` exec order)

---

## Server ops & remaining levers

### Q53. Can server ops alone hit 10 min?
**A.** No. Max ~422 s post-SC class → still ~25 min. Tier-1: MBT 16384, decode CUDA graphs, EP/DeepEP; never S&gt;16. (`16`, `SYNTHESIS`)

### Q54. Ranked remaining MoE-only code levers post-v11?
**A.** (1) Dense offload −850–1200 s (gated), (2) det-metadata ~−471 s, (3) verdict-first −124–155 s, (4) router −190–310 s, (5) payload scoping enabler. (`SYNTHESIS`, `10`)

### Q55. Verdict-first savings and gate?
**A.** UnitCheckClear bifurcation ≈ −92–155 s (stack band −124–155). Holdout / schema A/B required. (`15`, `05n`, `SYNTHESIS`)

### Q56. Safe router cut post-v11?
**A.** combo_safe + dynamic quota: safe ~−150–250 calls class; holdout on 3/381 + 16/381 flip set. (`14`, `PLANNING-HANDOFF`)

---

## Planning process / non-goals

### Q57. Is the dual-pod corpus (`research/cold-run-10min/`) executable here?
**A.** No. Superseded for execution; twin forbidden. Historical context only. (`PLANNING-HANDOFF`, `PROMPT-FOR-PLANNER`, `FILE-MANIFEST`)

### Q58. What are hard non-goals?
**A.** Twin, S=32, c&gt;32, skip monolith, default det-skip, P/D one node, BI mode, bank MTP/Flash without deploy, Gemma primary, guided_grammar, SGLang migrate, VLM/images, same-pod MoE→MoE cascade. (`NON-GOALS`, `SYNTHESIS` reject ledger)

### Q59. Recommended execution order if dense restart is uncertain?
**A.** Remeasure v11 → ship MoE package (A) → ask Alliance for dense restart → if yes, scoping→cascade→gate (B); if no, Option C SLA language in the same plan. (`PLANNING-HANDOFF` §6, §12)

### Q60. What must every major plan claim cite?
**A.** Report ids from this corpus (`12`, `17`, `26`, …). Do not invent live dense capacity. Do not propose S=32 or twin. (`PROMPT-FOR-PLANNER`, `PLANNING-HANDOFF` §12)

---

## Quick reject cheat-sheet

| Idea | Verdict | Cite |
|------|---------|------|
| ≤10 min MoE-only | Impossible at quality | `17` |
| Twin / S=32 / c&gt;32 | Forbidden | `00` |
| Dense path today | Infra-blocked (404) | `26` |
| Skip monolith | No | `21` |
| Bank MTP | A/B only | `05j` |
| Flash w/o deploy | No | `05b` |
| BI / P/D / guided_grammar | No | `05v`, `05k`, `05i` |
| Gemma primary | No | `05f` |
| Ideal-verify delete | ≤90 s, not a closer | `29` |
| Option C | ~15–20 min SLA | `01-OPTIONS-ABC` |
