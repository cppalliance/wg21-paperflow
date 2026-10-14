# 55 - Priority vs LJF

**Verdict:** usable — client-side LJF already captures the only fleet-wall reordering win worth shipping; vLLM server priority scheduling is largely redundant with LJF on this workload and should not be implemented.
**Confidence:** high

**Return:** `implement LJF only`

## Question

Does client-side longest-job-first (LJF) paper launch order make vLLM `--scheduling-policy priority` + per-request `priority` redundant for the cold tapetum fleet?

## Axes (do not conflate)

| Lever | What it reorders | Where it acts | Status at HEAD |
|-------|------------------|---------------|----------------|
| **LJF** | Which **papers** enter the client concurrency window first | `cli.py` before `asyncio.gather` | **Implemented** (`_sort_pids_ljf` `cli.py:1030-1038`, full-run apply `cli.py:1063`) |
| **Server priority** | Which **waiting HTTP requests** admit / preempt under KV pressure | vLLM waiting queue + client `priority` body field | **Not wired** (pod default FCFS; no client `priority`; see `tapetum-llm-speedup/99-vllm-priority-scheduling.md`) |

LJF is list scheduling of non-preemptive paper jobs on `m≈16` server slots. Server priority is admission order among already-submitted requests. Same class of win (zero-sum reorder on a saturated decode pod), different knobs.

## Findings

- [CRITICAL] **LJF already owns the makespan / tail problem server priority was sold against.** Evidence: PID-lexicographic launch left long serial papers (chunked HTML, 9–10 call PDFs) to finish alone while slots idle (`29-tail-latency-scheduler.md:8,12`); LJF by source size starts them in the bulk phase (`cli.py:1030-1063`). Modeled save **~60–180 s (2–6%)** on 3003 s; wall arithmetic books **−60 to −90 s** on T (`11-wall-arithmetic.md:42`). Impact: the dominant reorder lever is **done**; quality risk **none**.

- [CRITICAL] **Server priority cannot buy a second independent slice of the same ceiling.** Evidence: fleet wall is compute-bound (`2284×20/16 ≈ 2855 s` closes measured 3003 s, `99-vllm-priority-scheduling.md:13`); priority does not cut tokens or calls; honest fleet-wall envelope **~1–5% (~30–150 s)** and hard cap **~5%** even with perfect ordering (`99:9,13`). Chunked prefill already prefers decode over prefill inside each iteration (`99:11`). Impact: after LJF, remaining priority upside is **overlapping residual queue wait**, not a new term in `wall = (N×L)/S + T + C`. Quality risk **none** for ordering itself; ops risk as below.

- [HIGH] **Continuation-biased priorities (calls 2–6 = priority 0, new first calls = 1) mostly duplicate what LJF already does for wall time.** Under LJF, heavy papers' serial chains run while the active set is still dense, so "prefer in-flight paper's next call over a late first call" is the same makespan story as "start heavy papers early." With `c=32` overfilling 16 slots, FCFS arrival already tends to re-admit the paper that just finished a call (client immediately submits the next). Impact: expected **additive** save from priority **on top of LJF** is much smaller than the solo priority envelope — plan as **~0–60 s**, not another 30–150 s stacked. Quality risk **low** (preemption recomputes KV, not different prompts; `99:9`).

- [HIGH] **Server priority has rollout cost and failure modes LJF does not.** Evidence: needs (a) pod restart with `--scheduling-policy priority` and (b) client `priority` through `VllmThinkingBackend` / `extra_body` or whisker HTTP bypass (`99:15`); FCFS + client priorities **silently no-op** (`99:17`); KV preemption of long prefills can interact with timeouts (`99:18`); starving priority-1 first calls can push papers into the **900 s** paper budget (`99:19`). LJF is ~30 lines, no restart, no preemption, already landed. Impact: **negative expected value** for priority as a cold-run program item vs MBT / APC / MTP / dual-pod (`26-server-ops-checklist.md` top-5 omits priority entirely).

- [MED] **Neither lever moves the 10 min gate.** Evidence: CONSERVATIVE T/C after LJF+`to_thread` is **28–68 s** residual (`22-path-a-b-10min.md:18`); ≤600 s still needs metadata call cuts + dual-pod (`11-wall-arithmetic.md:93-99`). Impact: spending eng/ops on priority instead of dual-pod / verdict-first / call elimination is a **distraction**.

- [LOW] **Warm / partial PID runs are out of scope for this redundancy claim.** Explicit `--pids` preserve caller order and skip LJF (`cli.py:1056-1057` vs full-run branch). Server priority could still bias mixed interactive load on a shared pod; that is not the cold 381-paper wall problem.

## Overlap model (stacking)

```
solo LJF:           −60…−180 s   (tail / makespan)
solo priority:      −30…−150 s   (wait-queue admit order; zero-sum)
LJF then priority:  −60…−180 s   + ~0…−60 s residual
                    ≠ sum of solos
```

Do not book both envelopes into T. Book LJF; treat priority as **superseded** unless measurement proves a large residual (below).

## False-pass hypothesis

Ship "both" and attribute a later cold-run improvement to priority when the delta was LJF (already in v11) or MBT/APC: future ops keep a fragile priority policy that adds starvation risk with **no incremental wall proof**.

## False-fail hypothesis

Reject LJF because a mid-run p99 rose when a chunked HTML giant started early (`29:24`), then chase server priority as a substitute: priority has the same fairness shift plus preemption/timeout risk, and still cannot replace call elimination.

## What would change my mind

Instrumented A/B on alliance-pod with LJF **on** in both arms: arm B adds `--scheduling-policy priority` + continuation-biased client priorities, reports **≥100 s** cold-wall reduction vs LJF-only **and** zero verdict-class drift / zero new timeout tombstones. That would justify **both**. Absent that, priority stays redundant.

## Recommendation

| Option | Decision |
|--------|----------|
| **implement LJF only** | **YES** — keep shipped LJF; do not implement server priority for cold-fleet wall |
| both | No — additive upside too small vs ops + starvation/preemption risk |
| neither | No — LJF is already the right cheap reorder; dropping it would re-grow PID-order tail |

**Return: implement LJF only**
