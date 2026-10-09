# 19 - Timeout-Tail-Auditor

**Verdict:** usable-with-conditions — per-call `asyncio.wait_for` caps (120/240 s) are wired on every judge LLM path; the remaining tail risk is the **600 s httpx read default** in `model_backends.py` outliving cancelled tasks and holding fleet slots, compounded by a **2220 s outer PDF paper budget** that can absorb serial timeout chains on stragglers. At **c=32** the RunPod **524** class is latent, not dominant.
**Confidence:** high (code audit + concurrency-381 proxy notes + 2026-07-08 c=32/c=381 measurements)

## Timeout inventory (HEAD)

| Layer | Constant / location | Value | Binds when |
|-------|---------------------|-------|------------|
| Unit check | `UNIT_CHECK_TIMEOUT_SECONDS` (`constants.py:241`) | **120 s** | metadata outline, each unit check (`unit_judge.py:263`, `:801`) |
| Page escalation | `PAGE_ESCALATION_TIMEOUT_SECONDS` (`constants.py:197`) | **120 s** | each scoped page call (`pdf_judge.py:405-411`) |
| Monolith / tier | `MONOLITH_TIMEOUT_SECONDS` (`constants.py:244-247`) | **240 s** | PDF monolith (`pdf_judge.py:672-681`), text tier-1 chunks + tier-2 (`adjudicate.py:244-309`) |
| Paper base | `_PAPER_TIMEOUT_SECONDS` (`cli.py:144`) | **900 s** | ideal verifier outer wrap only (`cli.py:1233-1240`); also the **base term** in additive PDF/text budgets |
| PDF paper budget | `_pdf_judge_timeout_seconds()` (`cli.py:160-167`) | **2220 s** default = 900 + 5×120 + 6×120 | outer `wait_for` on `judge_pdf_extraction` (`cli.py:1321-1339`); scales with `--all-pages` unit count |
| Text paper budget | `_text_lane_timeout_seconds()` (`cli.py:204-208`) | **1620 s** = 900 + 6×120 | outer `wait_for` on `adjudicate_paper` (`cli.py:1402-1413`) |
| httpx read (SDK) | `AsyncOpenAI(...)` no `timeout=` (`model_backends.py:283`) | **600 s** read/write/pool; connect **5 s** | every `VllmThinkingBackend.run` call; SDK **2 retries** → up to ~1800 s theoretical (`concurrency-381/11-client-timeouts.md:8-10`) |
| Proxy TTFT | RunPod HTTP proxy | **~100 s** to first byte | idle streaming connections with no SSE until vLLM schedules (`concurrency-381/12-runpod-proxy.md:9-11`) |

### Monolith `wait_for`: present (not absent)

Both lanes cap the largest single payload:

- PDF: `asyncio.wait_for(..., timeout=MONOLITH_TIMEOUT_SECONDS)` at `pdf_judge.py:672-681`.
- HTML/text: tier-1 (incl. chunked triage) and tier-2 at `adjudicate.py:244-309`.

Pre-v11 absence here let a hung monolith hold a paper slot toward the **600 s httpx** floor; v11 added the 240 s cap (`tapetum_llm.md` lane version note). Residual gap: **ideal verifier** (`ideal_verify.py:151-158` via `run_task`) has **no inner** per-call `wait_for`; only the **900 s** CLI wrap (`cli.py:1233-1240`).

### Paper budget arithmetic (fleet default, capped units)

```
_pdf_judge = 900 + MAX_PAGE_ESCALATIONS×120 + (1+MAX_UNIT_CHECKS)×120
           = 900 + 600 + 720 = 2220 s   (~37 min ceiling per paper)

_text_lane = 900 + (1+MAX_UNIT_CHECKS)×120 = 1620 s

Serial worst-case if every inner call hits timeout:
  monolith 240 + metadata 120 + 5×page 600 + 5×unit 600 = 1560 s
  (still under 2220 s outer — outer is not the first binder on that path)
```

## How hung calls affect fleet wall at c=32

**Fleet shape:** 381 papers, client **c=32**, server **16 slots**, **one in-flight LLM call per paper** (D11 serial in-paper chain). Steady-state: up to **32 HTTP connections**, **16 decoding**, **~16 queued** — one slot-time of queue wait (~20–30 s), not the multi-minute depths modeled at c=381 (`concurrency-381/11-client-timeouts.md:16`, `12-runpod-proxy.md:13`).

**Hung-call mechanics:**

1. **Per-call `wait_for` (120/240 s)** fires first on judge paths → paper task errors or aborts that call; slot freed for the next paper in the gather pool.
2. **If cancellation is leaky**, the underlying httpx stream may continue until **600 s** read timeout — one zombie connection still counts against c=32 and vLLM's accepted-but-silent queue (`concurrency-381/19-vllm-http-limits.md:12`, `:26`).
3. **Proxy 524 (~100 s TTFT)** applies when a connection sits with **zero response bytes** (`12-runpod-proxy.md:9-11`). At c=32, normal queue wait (~20–30 s) stays **below** the 100 s Cloudflare origin-response ceiling; 524 is a **burst/c>32** failure mode (measured **257/381** proxy-killed at c=381, `cli.py:136-137`, `12-runpod-proxy.md:29-37`), not the observed c=32 run (**692.3 s**, 1 transient error, `slots-32-regression/SYNTHESIS.md:11`).
4. **Fleet wall extension** from a hung call is **not** 600 s × 32. `asyncio.gather` over papers waits on the **slowest task in the current wave**. One straggler at the tail adds roughly its **remaining paper time** to wall; mid-batch stragglers overlap with other slots (31 papers keep moving).

**Quantified c=32 impact:**

| Scenario | Per-paper stall | Fleet wall delta (order of magnitude) | Frequency |
|----------|-----------------|---------------------------------------|-----------|
| Median healthy call | ~20 s | **0 s** (baseline physics) | ~99%+ calls |
| One inner timeout (unit/page) | 120 s | **0–120 s** (0 if not tail straggler) | rare |
| Monolith timeout | 240 s | **0–240 s** on last wave | rare |
| Leaky cancel → httpx 600 s | up to 600 s | **0–600 s** on last wave; **~37 s** equivalent if saturated (600/16) | latent |
| Full serial timeout chain | 1560 s | **0–1560 s** if every call in one tail paper hits cap | pathological |
| c=381-style proxy 524 | ~100 s fail | **N/A at c=32** under normal queue; dominant at c>32 | forbidden config |

**Median fleet impact of timeout stack today: ~0 s** (caps rarely fire; wall ≈ 2284 calls × ~20 s / 16 ≈ 2860 s). **Worst-case tail:** one last-wave paper running the full serial timeout chain adds **~1440 s** above its normal ~120 s (~**+24 min** on a ~48 min cold run) — or **+480 s** if only httpx zombies leak past 240 s monolith caps.

## Findings (ranked)

- [CRITICAL] **httpx 600 s default with no override is the widest tail window.** Evidence: `model_backends.py:283` (`AsyncOpenAI` without `timeout=`); `concurrency-381/11-client-timeouts.md:8-10` (600 s read, 3 SDK attempts). Inner judge caps are 120/240 s, so httpx should be a **safety net**, not the primary binder — but it becomes primary if `wait_for` cancellation does not tear down the stream. Impact at c=32: a leaky hung monolith holds **1/32 client slots up to 600 s** instead of 240 s (**2.5× straggler extension**); at tail, up to **+360 s fleet wall** per zombie vs a clean 240 s cap.

- [HIGH] **Per-call caps are complete on judge paths; monolith `wait_for` is the shipped fix.** Evidence: `pdf_judge.py:672-681`, `adjudicate.py:244-309`, `unit_judge.py:263-272`, `:801-807`, `pdf_judge.py:405-411`. `00-baseline.md:37` credits monolith `wait_for` with **~90–220 s** cold-run savings vs httpx-only stall. Impact: median **~0 s**; prevents pre-v11 monolith hangs from approaching 600 s/900 s.

- [HIGH] **Outer paper budgets (2220/1620 s) exceed serial inner sums and rarely bind before inner caps.** Evidence: `cli.py:160-167`, `:204-208`; inner serial max **1560 s** vs outer **2220 s**. Impact: outer `wait_for` is a backstop for runaway chains, not median path; mis-tuned `--all-pages` scaling (`unit_count×120`) can push outer toward **5100 s+** on 40-page papers (`all-pages-llm-coverage/00-baseline.md:24`) while fleet still runs at c=32 — **tail straggler risk** on audit modes, not fleet default.

- [HIGH] **Proxy 524 is real but subordinate at c=32; cite concurrency-381.** Evidence: `12-runpod-proxy.md:9-11` (~100 s Cloudflare origin-response, HTTP **524** when no initial stream); `12-runpod-proxy.md:29-31` (524 before client 600 s on idle queue); `cli.py:136-137` (**257/381** at c=381); `11-client-timeouts.md:16` (papers ~321–381 predict APITimeout at c=381). At c=32, queue depth ~1 slot-time → TTFT usually **<100 s** → 524 **latent** unless pod scheduling stalls or concurrency is raised (`slots-32-regression/SYNTHESIS.md:59-60` flip condition).

- [MED] **900 s `_PAPER_TIMEOUT_SECONDS` comment conflates base term and ideal-verifier cap.** Evidence: comment at `cli.py:140-143` names 600 s httpx; constant used as **additive base** (2220 s PDF budget) and **ideal wrap** (`cli.py:1233-1240`). Ideal path lacks inner `MONOLITH_TIMEOUT_SECONDS`. Impact: ideal verify hung call can hold a post-judge slot up to **900 s** on golden-PR papers — small count, pure tail.

- [MED] **SDK retry re-queues at tail without preserving FCFS position.** Evidence: `11-client-timeouts.md:10-12`. After 524 or 600 s read timeout, retry enters vLLM queue at the back. Impact at c=32: low (shallow queue); amplifies **error tombstones** rather than wall time when combined with proxy 524 at higher c.

- [LOW] **Unit/page 120 s caps can false-fail under transient slot contention, not fleet stall.** Evidence: `87-langextract-retry-handling.md:22`; measured ~20 s/call median vs 120 s cap. Impact: quality/coverage (review/error tombstone), not +minutes fleet wall unless many papers hit cap serially.

## Biggest tail-risk fix

**Pass an explicit httpx read timeout to `AsyncOpenAI` in `model_backends.py` aligned to inner caps + queue slack** (e.g. `read=270 s` ≥ `MONOLITH_TIMEOUT_SECONDS` + ~30 s c=32 queue headroom; keep `connect=5 s`). Optionally add `MONOLITH_TIMEOUT_SECONDS` wrap on `verify_against_ideal`.

Why this beats other levers:

- Monolith `wait_for` is **already shipped** (diminishing returns).
- Lowering unit/page 120 s caps trades **false-fail coverage** for marginal wall savings.
- Raising `_PAPER_TIMEOUT_SECONDS` or httpx toward 1800 s **defers** failures while keeping zombie connections (explicitly **risky** in `11-client-timeouts.md:37`).
- c=32 is already the empirically safe client ceiling (`cli.py:133-137`); fixing proxy 524 without TCP/direct path does not move median wall.

**Estimated impact:**

| Metric | Median cold fleet (~2883 s) | Worst-case tail straggler |
|--------|----------------------------|---------------------------|
| httpx 600 → 270 s alignment | **~0 s** (timeouts rarely fire) | **−360 s to −480 s** per leaky monolith zombie (600→240 effective); **−0 s** when cancellation is clean |
| Ideal inner 240 s `wait_for` | **~0 s** | **−660 s** per hung ideal on golden papers (900→240) |
| Full serial timeout chain (pathological) | n/a | **+1440 s** above normal paper today; inner caps already limit to 1560 s/paper |

**Net:** median fleet wall unchanged; worst-case tail straggler drops from **~600 s httpx-shaped** stalls toward **240 s monolith-shaped** stalls — order **~6 min saved per worst tail paper**, **~0 s** on median paper. Under c=32 with healthy pod, expect **524-class failures ≈ 0**; the binding tail is **client-side zombie HTTP**, not proxy queue depth.

## False-pass hypothesis

Lowering httpx read below monolith work on legitimately slow decode (rare >240 s monolith on 500k-char payload) causes premature `APITimeoutError` → error tombstone → operator `--retry-errors` reruns the paper; advisory lane fails closed, no silent pass.

## False-fail hypothesis

A pod stall that would eventually complete at 250–300 s is cut at 240 s monolith `wait_for` → `PdfLaneError` / error sidecar with debug transcript preserved — fail-closed review, not a deterministic pass. Acceptable for advisory lane; hurts cold-run completion rate if pod is degraded.

## What would change my mind

1. Fleet trace at c=32 logging **task cancel → httpx connection close latency**: if 100% of `wait_for` timeouts close connections within 1 s, httpx 600 s is dead code and the biggest fix shifts to **tightening outer 2220 s budget** or **`--all-pages` timeout scaling**.
2. Controlled c=32 run with **per-request HTTP status + TTFT**: any **524** before 100 s with queue depth ≤16 would contradict `12-runpod-proxy.md` for the operating point and elevate proxy ahead of httpx.
3. Live c=381 rerun with 0 proxy errors would demote 524 notes and re-open client c>32 (explicitly forbidden in `00-baseline.md:52` until then).

## Code anchors

- `packages/whisker/src/whisker/tapetum_llm/constants.py:191-247`
- `packages/whisker/src/whisker/tapetum_llm/cli.py:133-167`, `:204-208`, `:1321-1339`
- `packages/whisker/src/whisker/tapetum_llm/pdf_judge.py:405-411`, `:672-681`
- `packages/whisker/src/whisker/tapetum_llm/unit_judge.py:263-272`, `:801-807`
- `packages/whisker/src/whisker/tapetum_llm/adjudicate.py:244-309`
- `packages/pipeline/src/pipeline/model_backends.py:283`, `:341-351`
- `research/concurrency-381/11-client-timeouts.md`, `12-runpod-proxy.md`
- `research/slots-32-regression/SYNTHESIS.md:11`, `:59-60`
