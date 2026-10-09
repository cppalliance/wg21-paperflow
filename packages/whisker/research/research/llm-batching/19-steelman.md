# 19 - Steelman (Cheapest Path)

**Verdict:** usable-with-conditions — A one-flag concurrency bump (`--concurrency 8`, already implemented in `cli.py:409-416`) plus a single CTO server-side ask (`--max-num-seqs` / prefix caching) likely delivers 70–90% of the 36→single-digit-minute goal; every provider-style batch layer before a 15-minute sweep is premature engineering against a per-hour pod.
**Confidence:** high

## Findings

- [CRITICAL] The cheapest lever already ships: `--concurrency N` with `asyncio.Semaphore` + `asyncio.gather`, per-paper firewall, input-order persistence (`cli.py:409-472`; tests `test_tapetum_llm.py:1263-1349`). Impact: changing `_DEFAULT_CONCURRENCY` from 1→8 (or passing `--concurrency 8` on the existing command) is a one-line default change, not a new subsystem. At c=3 the pod already absorbed 3 streams with 1 retry on 200 papers (00-baseline:12-15).

- [CRITICAL] Arithmetic from measured c=3: 200 papers / 2159.8 s = **10.8 s/paper effective** vs **~15–30 s single-call** (00-baseline:12-18). The 2–3× gap (not 3×) proves the vLLM continuous-batching scheduler is under-fed at c=3; raising N is free throughput until the server knee. Impact: ideal linear speedup from the c=3 baseline projects **T(N) ≈ 2159.8 × (3/N)**.

- [HIGH] Ideal-scaling wall-time projections (effective s/paper stays 10.8, pod not saturated):
  - **c=8:** 2159.8 × 3/8 = **810 s (~13.5 min)** — 2.7× faster than 36 min.
  - **c=16:** 2159.8 × 3/16 = **405 s (~6.8 min)** — 5.3× faster.
  - **c=32:** 2159.8 × 3/32 = **202 s (~3.4 min)** — 10.7× faster.
  Evidence: 00-baseline:12-18, 84-86. Impact: even c=8 alone crosses the "half the wall time" bar with zero new code.

- [HIGH] Latency-degrading projections (knee at K=8, per community `--max-num-seqs 8` dump cited in 00-baseline:35-36; per-request latency grows linearly past K: **L(c) = L₀ × c/K**, L₀ ≈ 22.5 s midpoint of 15–30 s):
  - **c=8 (at knee):** ceil(200/8)=25 waves × 22.5 s = **562 s (~9.4 min)** — still beats 36 min by 3.8×.
  - **c=16:** ceil(200/16)=13 waves × (22.5 × 16/8) = 13 × 45 s = **585 s (~9.8 min)** — barely worse than c=8; extra client concurrency just queues.
  - **c=32:** ceil(200/32)=7 waves × (22.5 × 32/8) = 7 × 90 s = **630 s (~10.5 min)** — worse than c=8; confirms N>8 without server change is wasted client complexity.
  Impact: the sweep's job is to locate K empirically; until then, **cap client N at 8** and reject c=16/32 as production defaults.

- [HIGH] Pod economics kill batch-infrastructure ROI: `SERVICES.toml` alliance-pod is **billed per hour of uptime, NOT per token** (00-baseline:31-32). A 36-min run and a 6-min run cost the same pod-hour. Impact: engineering hours (swarm time) dominate; a 15-minute sweep + one-line default change has negative opportunity cost vs building queues, batch emulators, or pipeline pooling PRs.

- [MED] Escalation load is bounded: 13/197 papers add a tier-2 call (00-baseline:25). At c=8 worst case ≈ 13 concurrent tier-2 bursts across the corpus, not 200×2. Impact: raising paper concurrency does not multiply LLM calls; it parallelizes already-independent papers. Retry budget stayed at 1 on the full 200-paper run (00-baseline:14).

- [MED] Chunk-level parallelism is a dead lever post data-URI strip: P2728R11/R12 went from 755.8 s (7 serial chunks) to 1-chunk / 28 s batch membership (00-baseline:20-22). `_custom_triage` still serializes chunks (D11 comment in adjudicate.py per 00-baseline:61-64), but almost no paper chunks anymore. Impact: chunk fan-out engineering saves seconds on a handful of papers, not 30 minutes on the corpus.

- [LOW] Connection pooling in `pipeline/model_backends.py` (fresh `AsyncOpenAI` per call, 00-baseline:52-56) is **read-only** to whisker and unmeasured: TLS handshake overhead is noise against 15–30 s decode. Impact: park unless the sweep shows client-side stalls (timeouts, connect errors) scaling with N.

## False-pass hypothesis

Raising concurrency under pod saturation (N >> K) lengthens per-request decode without raising errors: tier-1 confidence stays high, but time-pressure and KV-cache contention can shift borderline papers from `review` to `pass`. The existing escalation gate (13/197 tier-2) and grounding/demotion logic (`test_tapetum_llm.py:347-376`) mitigate but do not eliminate distribution drift. **Mitigation:** sweep compares verdict histograms at c=3 vs c=8; any >2 pp shift in pass/review/fail blocks raising the default.

## False-fail hypothesis

Concurrent papers are independent (separate state, separate sidecar writes, `cli.py:414-415`), and the batch firewall already isolates failures (`test_tapetum_llm.py:1338-1343`). False-fail risk is retry storms under overload: if latency degrades, `output_retries` budget exhausts on more papers, surfacing as `error` counts. **Mitigation:** sweep gates on retry count + error count per 20-paper batch, not wall time alone.

## What would change my mind

A 15-minute empirical concurrency sweep showing **c=8 wall time ≥ c=3 scaled expectation** (i.e. ≥ 810 s ideal / ≥ 562 s degraded for 200 papers, or proportionally for 20-paper batches) **AND** retry/error counts rising above the c=3 baseline (1 retry / 3 errors per 200), would flip the verdict to "provider-style infra or server reconfig required before client parallelism."

---

## Supplement: 15-minute sweep protocol (gates all further engineering)

**Design:** 3 batches × 20 papers (same candidate set, fixed PID order) at `--concurrency 8`, `16`, `32`. Record wall time, model retry count (footer line), error count, and per-paper effective s.

**What it settles:**

| Question | Pass criterion | Fail → next action |
|---|---|---|
| Where is the knee? | c=8 beats c=3 proportional projection; c=16 ≈ c=8 wall time | Stop at c=8; ask CTO for `--max-num-seqs` raise |
| Is client parallelism safe? | retry+error ≤ c=3 baseline rate (≤1 retry / ≤1 error per 20 papers) | Roll back N; investigate overload, not batch APIs |
| Is ideal or degraded model correct? | If c=16 wall ≈ c=8 → degraded; if c=16 wall ≈ half c=8 → ideal, headroom past 8 | Informs whether CTO ask or higher N is warranted |

**Time budget:** 20 papers at c=8 projected ~216 s (10.8 s/paper × 20/8 waves) per batch ≈ 3.6 min; three batches ≈ 11 min + setup. Fits 15 minutes.

**Gate rule (Minimalism Ladder rung 1):** No new whisker code beyond possibly `_DEFAULT_CONCURRENCY = 8` until sweep completes. No pipeline PRs. No batch emulator.

---

## Workstreams: REJECT / PARK / KEEP

### REJECT (not justified by numbers)

| Workstream | Why reject |
|---|---|
| **Provider-style batch endpoint emulation** (`/v1/batches`, `vllm run-batch`) | vLLM 0.24 batch API is offline/unknown to our pod (00-baseline:90-93); we have no shell. Emulation layer in whisker duplicates what HTTP concurrency already does, with added state machine + polling code. |
| **Work queues / job runners** | `asyncio.gather` + `Semaphore` IS the queue (cli.py:416-472). A second queue adds latency (enqueue/dequeue) without increasing server parallelism. |
| **Chunk-level parallelism** | Data-URI strip retired multi-chunk papers (00-baseline:20-22); serial chunk path affects ≪1% of corpus seconds. |
| **Connection pooling changes in pipeline** | Read-only constraint (00-baseline:55-56); unmeasured vs 15–30 s decode; fresh-client-per-call is a premature optimization without connect-stall evidence. |

### PARK (valid but after sweep + server ask)

| Workstream | Park until |
|---|---|
| **Dual-pod load split** (`--service deep=alliance-pod` / shard papers) | Sweep shows c=8 at knee with retries/errors clean but wall still >10 min |
| **`max_tokens` / output-verbosity reduction** (lever b) | Sweep shows latency dominated by decode tokens, not queue wait |
| **Prefix caching confirmation** | CTO confirms `enable_prefix_caching`; shared 8 KB system prompt (00-baseline:65-67) makes this high-leverage but server-side only |

### KEEP (survives scrutiny — not cheap, genuinely needed if sweep passes)

1. **CTO server-side request (one ask, zero whisker code):** raise `--max-num-seqs` from 8 toward 16–32 and confirm prefix caching on the shared system prompt. This is the only lever that moves the degraded-model knee; client N>8 without it is provably wasteful (585–630 s vs 562 s at c=8 in degraded math above).

2. **Per-call latency cut via `max_tokens` / guided JSON** (whisker-side, small diff in `adjudicate.py:450-458`): output tokens dominate decode (00-baseline:87-88). Not a one-liner, but orthogonal to concurrency and compounds with it: halving decode from 22.5→11 s at c=8 yields ~280 s for 200 papers even at the knee. Justified only if sweep shows queue wait is short (ideal scaling holds) and per-paper latency—not saturation—is the bottleneck.

---

## Recommended cheapest plan (post-sweep, pre-everything-else)

1. Run 15-minute sweep (above).
2. If pass: set `_DEFAULT_CONCURRENCY = 8` (one line, `cli.py:52`) or document `--concurrency 8` in the corpus rerun command.
3. Send CTO one message: max-num-seqs + prefix caching status.
4. Re-run full 200-paper corpus; expect **9–14 min** (degraded–ideal bracket at c=8), not 36 min.
5. Stop. Revisit only if wall time >15 min or verdict distribution shifts.

**Model boundary:** This plan is revised if the sweep shows c=8 is not ≥2× faster than c=3 on 20-paper batches, or if retry/error rates superlinear in N.
