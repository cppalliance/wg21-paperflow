# NON-GOALS — Cold-run ≤10 min (1 MoE pod)

**Date:** 2026-07-24  
**Sources:** `PLANNING-HANDOFF.md` §8, `SYNTHESIS.md` reject ledger / out of scope, `00-baseline.md`, `21`, `24`, `05*`.

These are permanent non-goals for this planning cycle. Do not reopen without new evidence and an explicit human override.

---

## Infra / capacity (forbidden)

| Non-goal | Why |
|----------|-----|
| Second DeepSeek-V4-Pro replica (`h200x8-deepseek-v4-pro` twin) | Operator ban (budget/authority). Twin is 404 and out of scope. |
| Raise MoE `--max-num-seqs` above **16** (`S=32`) | Measured **+57%** wall. |
| Client concurrency `c>32` | RunPod 524 / regression corpus. |
| Dual-pod LiteLLM shard / least-busy paper-start across twins | Requires live twin; superseded dual-pod plan is not executable. |
| Same-pod MoE→MoE cascade | Not a heterogeneous speed path; compounds shared-pod noise. |

---

## Quality / product shortcuts (rejected)

| Non-goal | Why |
|----------|-----|
| Skip monolith as default | Fusion false-clears; 10 min reachable without it (`21`). |
| Default `--det-skip` / deterministic skip monolith | Advisory opt-in only; ~250–350 s (`24`). |
| Drop ideal-verify as a 10-min lever | ~60–90 s only; not load-bearing. |
| Images / VLM lane | Operator: out of scope. |
| Exact-match 0% fleet flip as ship bar | False-rejects inside MoE/dense noise; use `flip_AA` margin (`19`). |
| Treat quality pass as proof of ≤600 s | Wall is a secondary metric; need measured B ≤620 s (`19`). |

---

## Server / serving experiments (do not bank)

| Non-goal | Why |
|----------|-----|
| `VLLM_BATCH_INVARIANT` on the speed path | ~50% throughput hit (`05v`). |
| P/D disaggregation on one 8×H200 | Short OSL; cannot split the node (`05k`). |
| Bank MTP wall seconds | Short JSON @ c≈16 is lose/flat (`05j`); A/B only. |
| Flash unit-judge without a deployed Alliance Flash endpoint | Needs weights/endpoint (`05b`). |
| Gemma-4 (`b200x2-gemma4`) as primary unit judge | Wording false-fail on `:::wording-remove` / `<del>` (`12`, `05f`). |
| `b200-r1` as primary unit judge | Thinking overhead; weak decode hypothesis (`12`). |
| Server `guided_grammar` / speculative `guided_json` | Stay schema-in-prompt; guided path is the slow trap (`05i`). |
| `--enable-dbo` at seqs=16 as a banked win | Usually flat; needs ≥32 concurrent decode tokens (`05t`). |
| SGLang migrate / HTTP micro-tuning as cold-run program | Out of scope for this corpus. |
| `auto_tune.sh` / server restarts mid-fleet on shared pod | Unsafe on live Alliance traffic (`28` / harness notes). |

---

## Client / API misuse

| Non-goal | Why |
|----------|-----|
| `thinking.enabled` with `json_object` | Hosted/CN invariant (`05y`). |
| `thinking.disabled` + `reasoning_effort` together | 400 (`05y`). |
| Enable thinking to “fix” schema | Wrong knob (`05y`). |
| `reasoning_effort="low"` for Non-think | Maps to High on DSV4 (`05c`). |

---

## Explicitly in scope (contrast)

These are **goals**, not non-goals: MoE-only package (Option A), heterogeneous cascade on **live** dense Alliance pods (Option B), payload scoping, det-metadata A/B, quality gate (`19`), asking ops to restart `h200-qwen3-32b`, and honest SLA reset to ~15–20 min if dense stays down (Option C).
