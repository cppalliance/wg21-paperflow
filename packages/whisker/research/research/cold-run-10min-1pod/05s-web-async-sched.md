# 05s - Web: vLLM #45257 async-scheduling underfill at max-num-seqs

**Verdict:** usable-with-conditions — real scheduler bug, but **not a path to raise S**; at our c=32 / S=16 it is a **keep-or-disable A/B**, not a reason to open slots to 32.
**Confidence:** high on mechanism (issue + PR diffs); medium on fleet wall delta (no alliance-pod measurement of underfill yet).

**Constraint:** single `alliance-pod`, S_eff fixed at **16**, client **c=32**. Raising `--max-num-seqs` to 32 remains forbidden (+57% wall).

**Primary sources (2026-07-24):**
- https://github.com/vllm-project/vllm/issues/45257 (open)
- https://github.com/vllm-project/vllm/pull/45366 (open, draft, `needs-rebase` — maintained fix)
- https://github.com/vllm-project/vllm/pull/45339 (closed in favor of #45366)
- Cousins: #27462 (PP underfill semantics, closed); #42568 (async remote-KV counting, related admission class)

---

## Mechanism (what #45257 is)

Documented meaning of `max_num_seqs`: max sequences **processed in a single iteration**.

Under **async scheduling**, a request that already hit `max_tokens` (or is otherwise ineligible this step) can stay in `self.running` with output placeholders until the prior step's output is applied. The waiting-admission guard historically used:

```text
len(self.running) == max_num_seqs  →  stop admitting waiting requests
```

So resident-but-**skipped** seqs still consume the cap. Actual `num_scheduled_tokens` this step can be **well below** `max_num_seqs` while the waiting queue backs up. Worst case called out upstream: P/D prefill nodes with `max_tokens=1` (finish after one forward, occupy running until async drain).

**Fix direction (#45366, njhill):** count only non-finished residents against the admission cap (`len(running) - async_finished_reqs`), and align watermark / invariant checks. #45339's broader "count only scheduled" approach was dropped to avoid oversubscription; #45366 is the surgical variant and adopted the regression tests. As of 2026-07-24: **not merged** (draft + merge conflicts).

---

## Findings

- [CRITICAL] **Do not "fix" underfill by raising `--max-num-seqs` 16→32.** Evidence: slots-32 regression +57% cold wall at client c=32 (`research/slots-32-regression/SYNTHESIS.md`, `00-baseline.md`). Impact: underfill means **S_eff < advertised S**; opening the knob widens the MoE expert-union batch and makes wall **worse**, not better. Arithmetic still requires `S_eff=16` in the denominator.

- [HIGH] **Bug bites hardest when completions are short / finish every step.** Evidence: #45257 + #45366 tests use `max_tokens=1` (P/D prefill mimic); second `schedule()` before output apply must still admit a full batch. Impact on our path: long thinking+JSON judges (L≈20 s) keep most of the 16 actively decoding, so underfill is a **tail / turnover** tax. Short-OSL / Non-think / verdict-first (OSL 50–200, `05m`) raises finish rate → more placeholder residents → **higher underfill risk** exactly when we try to cut L.

- [HIGH] **c=32 vs S=16 already oversubscribes 2:1; underfill turns that into pure client queue, not GPU work.** Evidence: baseline client c=32 / server 16 (`00-baseline.md`); admission gate blocks waiting while `running` looks "full". Impact: `/metrics` can show `num_requests_running≈16` and non-trivial `num_requests_waiting` while **scheduled batch &lt; 16** → TTFT/queue (C) rises, decode slots idle. Looks like "need more slots"; is actually async residency accounting.

- [HIGH] **Upstream fix is not shippable yet; ops must not wait on main.** Evidence: #45366 open, draft, `needs-rebase`, `mergeable=false` (checked 2026-07-24); #45339 closed without merge. Impact: no image bump "includes the fix" until that PR lands. Immediate lever is **flag state**, not vendor pin.

- [MED] **`--async-scheduling` is optional on our recipe path, not required for S=16 correctness.** Evidence: DeepSeek-V4-Pro verified H200 recipe does **not** list it (`40-vllm-deepseek-recipe.md` D2); listed as optional advanced / EP A/B (`05c`, `05m`, `40`). Newer vLLM may default it on (`05c`). Impact: if pod already has it on, treat as **A/B candidate to disable** when underfill signals appear; if off, do not enable for Tier-2 wins until #45366 is in the image **or** metrics prove scheduled==running under load.

- [MED] **Related admission bugs are a different class (async KV / PP), not our current topology.** Evidence: #27462 (PP micro-batch underfill via `len(running)`); #42568 (async remote KV loads must count toward cap). Impact: alliance-pod is single-node TP8+EP, not P/D disagg (`05k` out of scope as twin). Do not chase KV-connector patches for this cold-run corpus.

- [LOW] **Prior corpus already flagged the card; this note pins ops action for 1-pod.** Evidence: `research/cold-run-10min/41-vllm-github-issues.md` Card 2. Impact: synthesis should treat #45257 as **ops hygiene**, not a wall-closing lever toward ≤600 s.

---

## Impact on c=32 / S=16 (arithmetic)

Honest model (no silent S=32):

```text
wall ≈ (N_rem × L_eff) / S_eff + T + C − L_abs
S_eff ≤ 16   (advertised max-num-seqs)
```

| Scenario | S_eff effect | Wall effect @ fixed N,L |
|---|---|---|
| Async off, or long-decode steady state | ≈16 | baseline |
| Async on, mild finish/placeholder churn | ~14–15 (hypothesis) | ~+7–14% compute term |
| Async on + short-OSL / max_tokens≈1 style | can drop far below 16 | large C + underfilled steps; upstream P/D worst case |
| "Compensate" with max-num-seqs=32 | forbidden | measured **+57%** wall |

**Does not move us to ≤600 s.** At best, disabling a bad underfill path recovers toward the **honest S=16** envelope already in `11-wall-arithmetic-1pod.md`. At worst, enabling async without the fix **erodes** the 16 we already pinned.

---

## Ops action (answer)

**Do this:**

1. **Confirm** on `alliance-pod` whether async scheduling is on (`startup` / `/server_info`: `async_scheduling` / `--async-scheduling`).
2. Under a c=32 fleet load, watch for the underfill signature:
   - `vllm:num_requests_running` stuck near **16**
   - `vllm:num_requests_waiting` elevated
   - generation throughput / GPU util below the filled-16 band
3. **If underfill signature present:** restart with **`--no-async-scheduling`** (or omit enable). Keep `--max-num-seqs 16`. Re-measure cold wall + waiting metrics.
4. **If underfill absent:** leave flag alone; do **not** raise seqs. Optional future: re-enable async only after image includes merged #45366 (or cherry-pick) and A/B shows L down with waiting flat.
5. **Never** raise `--max-num-seqs` to paper over this bug.

**One-line ops action:**  
**Verify async-scheduling; if waiting climbs while running=16 and util is soft, disable it (`--no-async-scheduling`). Keep S=16. Do not bump seqs. Do not block on unmerged #45366.**

---

## False-pass hypothesis

Ops sees `num_requests_running=16` under c=32 and concludes "slots are full / healthy," while scheduled batch is underfilled by async placeholders; they keep async on and chase MTP/DeepEP for "more throughput" that never fills the hole.

## False-fail hypothesis

Ops attributes every waiting spike to #45257 and disables async scheduling when the real issue is MBT=8192, APC miss, or MoE expert-union at true batch 16; wall flat for unrelated reasons and async gets blamed forever.

## What would change my mind

- Live alliance-pod scrape proving scheduled batch consistently equals 16 with async on under our judge mix (bug irrelevant for this workload).
- #45366 merged into the Alliance image **and** A/B showing material L cut at S=16 with no waiting regression.
- Measurement that short-OSL path underfills so hard that S_eff≈8–10 with async on (then disable becomes a **HIGH** wall lever, still without raising seqs).
