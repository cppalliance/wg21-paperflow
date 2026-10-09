# 28 - Retry / Fail-Fast Auditor (tapetum path)

**Verdict:** usable — 55 retries ≈ 100 s on the v10 cold baseline is still accurate at HEAD; retry mechanics unchanged; fail-fast levers recover **~45–125 s** depending on baseline, not minutes.
**Confidence:** high

## Executive answer

| Question | Answer |
|----------|--------|
| Is **55 retries ≈ 100 s** still accurate? | **Yes** on the measured v10 cold run (3003 s, ~2284 calls). Formula unchanged at HEAD. |
| Post-v11 projected retry tax | **~30 retries, ~55 s** (44.6% fewer calls → proportional retry count). |
| **Seconds recoverable by fail-fast** | **~45–80 s** on a v11 cold run; **~70–125 s** if still benchmarking against the legacy 3003 s / 2284-call baseline. |

---

## Current retry stack (tapetum path)

Tapetum judge calls: `run_judge_task` → `AgentBackend.run` → `VllmThinkingBackend.run` (no tools). There is **no** pydantic-ai `ModelRetry`, **no** `output_retries`, **no** whisker `output_validator` hook anywhere in production.

Evidence chain:

| Layer | Mechanism | Budget |
|-------|-----------|--------|
| `judge_task.py:68-74` | Dispatches to `AgentBackend.run`; no extra retry | inherits backend |
| `model_backends.py:300-302` | `max_attempts = min(2, request_limit)` | **2 attempts max** per call |
| `model_backends.py:341-350` | Transient API: `NotFoundError`, `APIConnectionError`, `InternalServerError`, `APITimeoutError`; sleep `2 ** (attempt+1)` then retry | same 2-attempt cap |
| `model_backends.py:377-393` | `finish_reason == "length"`: grow `max_tokens` × 1.5, re-issue **without** context bloat | same cap |
| `model_backends.py:394-405` | Parse / `ValidationError`: append failed assistant turn + JSON nudge, full re-issue | same cap |
| `model_backends.py:77-106` | BPE cleanup (`U+0120`/`U+010A` + JSON-escaped forms) **after** stream completes | not a retry |
| `cli.py:223-248` | `_RetryCountFilter` swallows warnings matching `_RETRY_WARNING_MARKERS` | counts log events, not pydantic-ai retries |

Ideal verifier uses `run_task` (global `Semaphore(1)`) but inherits the same `VllmThinkingBackend` 2-attempt budget (`ideal_verify.py:151-158`).

**D10 as written (CLAUDE.md):** not satisfied literally (`output_retries` + `ModelRetry`). Mitigated by the hand-rolled 2-attempt raw-JSON loop only.

---

## Is 55 retries ≈ 100 s still accurate?

### Measured baseline (still the citation)

| Run | Wall | Retries | Source |
|-----|------|---------|--------|
| v10 cold | 3003.4 s | **55** | `tapetum-llm-speedup/00-baseline.md:17-18` |
| Prior cold | 2883.0 s | **54** | `tapetum-llm-throughput/07-retry-timeout-auditor.md:8` |
| v10 warm (6 error tombstones) | 64.8 s | **2** | `tapetum-llm-speedup/46-warm-run-auditor.md:8` |

### Arithmetic (unchanged)

- Implied per-call latency ~**20 s** at 16 server slots (`00-baseline.md:24-25`).
- Each counted retry ≈ **one extra full HTTP completion** (serial within the call; not overlapped with attempt 1).
- Fleet wall from retries: `55 × 20 s / 16 ≈ 69 s` (slot lower bound) to **~100 s** (measured footer band; includes retry context bloat on parse-nudge path).
- Share of cold wall: **~3.4%** (100 / 3003).

### Code drift since measurement

**None on retry mechanics.** `_LANE_VERSION = 11` (`cli.py:123`) changed call graph (metadata short-circuit, HMAC guard tag, prompt reorder) but did **not** touch `model_backends.py` retry loop or `_RetryCountFilter` markers.

Post-v11 cold run (not re-measured at HEAD):

- Effective calls drop ~44.6% after metadata short-circuit (`pdf_judge.py:742-758`).
- Retry **rate** (~2.4% of calls: 55/2284) should hold if BPE corruption is per-call independent.
- Projected: **~30 retries**, **~55 s** retry wall on a ~1660 s cold run (after metadata cut, before dual-pod).

**Conclusion:** The **55 ≈ 100 s** claim remains valid for the archived v10 cold run. Do not cite it against a fresh v11 cold run without re-measuring the footer.

---

## What the footer counter actually counts

One increment per swallowed **warning** log line matching:

```python
_RETRY_WARNING_MARKERS = (
    "Raw JSON parse failed",
    "Raw JSON output truncated",
    "Transient API error",
)
```

(`cli.py:229-233`)

So 55 retries ≠ 55 papers; it is ~55 **second attempts** spread across ~2284 calls (~0.14/paper). Batch mode suppresses per-paper lines (`cli.py:224-227`); exhausted retries surface as ERROR / tombstone, not in the counter.

Fleet forensics (`141-litellm-retry-fallback.md:18`): **0** transient API retries in archived logs; the 55 are overwhelmingly `"Raw JSON parse failed"` (BPE / parse), with attempt 2 succeeding (`cli.py:218-221` comment).

---

## Doomed papers: where time is wasted today

v10 cold: **6 error** tombstones. Archived semantic causes (`141-litellm-retry-fallback.md:18`):

| Class | Example PIDs | When it fails | Calls wasted after failure point |
|-------|--------------|---------------|----------------------------------|
| Monolith JSON exhaustion | P3977R0 | After 2 backend attempts on monolith | metadata + up to 5 units (if reached) |
| Metadata validator | P3400R3, P4178R0 | metadata/outline call | units + escalations (v10); **short-circuited in v11** |
| Ideal verification | P4182R0, P4228R0 | After **full** source-aware cascade | 0 LLM, but ~6–8 prior calls already spent |

Priced (`07-retry-timeout-auditor.md:16`): **~26–32 s fleet wall** for 4 identified errors (~14–17 serial calls at ~30 s, /16 slots). v10 added 2 more errors → similar order of magnitude.

Timeouts **did not fire** on measured runs (grep: no `asyncio.TimeoutError` in fleet stderr). Paper budgets are latent ceiling only:

| Budget | Value | Location |
|--------|-------|----------|
| Monolith | 240 s | `constants.py:244-245` |
| Unit / page escalation | 120 s each | `constants.py:197,241` |
| Paper (text) | 900 + 6×120 = **1620 s** | `cli.py:204-208` |
| Paper (PDF default) | 900 + 5×120 + 6×120 = **2220 s** | `cli.py:160-168` |
| HTTP read (SDK default) | **600 s** | `model_backends.py:283` (no override) |

---

## Fail-fast levers (ranked by recoverable wall time)

### 1. Streaming abort on attempt-1 BPE / malformed JSON prefix — **~55–100 s**

**Problem:** With `stream=True`, the backend accumulates the full completion before `_clean_bpe` + parse (`model_backends.py:306-362`). Attempt 1 often pays a full ~20 s decode, then attempt 2 succeeds.

**Fix (pipeline-side):** Cancel stream when buffer shows `\u0120`/`\u010a`, no `{` after N tokens, or obvious JSON breakage; retry within existing 2-attempt budget.

**Recoverable:** Up to **entire retry tax** — **~55 s** (v11 projected) to **~100 s** (legacy 3003 s baseline).

**Quality risk:** LOW if abort only triggers retry; MED if thinking-block preamble triggers false abort (`128-nougat-batch-decode.md:28-29`).

**Whisker boundary:** Requires pipeline change or whisker-local wrapper; cannot edit `packages/pipeline/` without approval.

---

### 2. Metadata short-circuit — **~1341 s (already shipped, v11)**

When metadata/outline verdict ≠ `pass`, skip page escalations and unit checks (`pdf_judge.py:742-758`, HTML mirror `adjudicate.py:521-531`).

This is **call elimination**, not retry tuning. Already counted in cold-run-10min projections. **Not additional fail-fast recovery.**

---

### 3. Ideal verify before source-aware cascade — **~12–15 s fleet**

**Problem:** `_attach_ideal` runs only after `judge_pdf_extraction` / `adjudicate_paper` returns (`cli.py:1341`, `1402+`). Ideal failures tombstone after **6–8 LLM calls** already spent.

**Fix:** Run `verify_against_ideal` first when ideal exists; on `IdealVerificationError`, skip cascade (fail-closed tombstone, same semantics).

**Recoverable:** **~10–13 calls × ~20 s / 16 ≈ 12–15 s** on **≤2 papers** per archived pattern (`25-retry-economist.md:14-16`). Not all 6 errors benefit.

**Quality risk:** LOW for wall time; **design tension** — loses independent judge verdict on ideal-fail papers that previously had a usable `review` sidecar before ideal threw (`07-retry-timeout-auditor.md:28`).

---

### 4. Monolith-fail circuit breaker — **~5–10 s fleet**

**Problem:** Papers like P3977R0 exhaust 2 monolith attempts then could still run metadata/units before `PdfLaneError`.

**Fix:** On `MalformedModelOutputError` after backend retry exhaustion at monolith phase, tombstone immediately (skip metadata + units).

**Recoverable:** **~4–6 calls × ~20 s / 16 ≈ 5–7 s** per early-fail paper; **~1–2 papers**/fleet → **~5–10 s**.

**Quality risk:** None (already doomed; fail-closed).

---

### 5. Do not retry `NotFoundError` on same pod / cross-pod failover — **~0 s today**

Backend retries 404 twice on the same pod (`model_backends.py:341-342`). Archived runs: **0** transport tombstones. Failover is resilience for future dual-pod, not cold-run speed (`141-litellm-retry-fallback.md`).

---

### 6. Tighter unit/page timeouts (120 s → 60 s) — **~0 s today**

No measured timeout hits. Would only help under slot starvation or future higher concurrency.

---

### 7. Error tombstone fingerprint skip — **warm only (~50–58 s/night)**

Implemented v11 (`cli.py:810-828`, `--retry-errors`). Saves warm re-runs, **0 s on cold fleet**.

---

## Recoverable seconds summary

| Lever | Cold-run recoverable (s) | Status | Notes |
|-------|--------------------------|--------|-------|
| Streaming BPE/JSON abort (zero retry tax) | **55–100** | Not implemented | Largest pure retry win |
| Ideal-first when ideal exists | **12–15** | Not implemented | ≤2 papers/run |
| Monolith JSON-exhaustion circuit breaker | **5–10** | Not implemented | ~1–2 papers/run |
| Metadata short-circuit | **~1341** | **Shipped v11** | Call elimination, not retry |
| Transport failover / no 404 retry | **0** | Not needed on logs | Future dual-pod |
| Lower 120 s unit/page timeout | **0** | N/A | No timeout fires measured |
| Error tombstone fingerprint | **0 cold / ~50 warm** | **Shipped v11** | Steady-state only |

### Total **new** fail-fast recovery (do not double-count shipped levers)

| Baseline | Low | High |
|----------|-----|------|
| Legacy v10 cold (3003 s, 55 retries) | **~70 s** | **~125 s** |
| v11 projected cold (~1660 s, ~30 retries) | **~45 s** | **~80 s** |

**Interpretation:** Fail-fast on retries and doomed-paper paths is a **rounding-error** lever vs metadata short-circuit (~1341 s) and dual-pod (~÷1.9). Worth doing for tail hygiene and operator time, not for reaching 600 s alone.

---

## False-pass hypothesis

Disabling the parse-nudge retry path (fail on first `ValidationError`) to "fail faster" would tombstone papers where attempt 2 currently recovers from BPE corruption — converting **transient parse noise** into **error tombstones** and forcing full warm re-runs without improving quality.

---

## False-fail hypothesis

Ideal-first on P4182R0-class papers would tombstone before the independent pdf-judge `review` verdict is persisted, discarding advisory signal the operator could use while ideal grounding is fixed — same shape as today's false-fail, but **earlier** in the chain.

---

## What would change my mind

A fresh 381-paper v11 cold run footer showing **>80 retries** or retry wall **>200 s** would mean BPE rate regressed or counter semantics changed — re-audit `_RetryCountFilter` and per-call debug tags. Per-call debug for all retried completions tagging failure mode (BPE vs truncation vs API) would justify prioritizing stream-abort over other fail-fast work.

---

## Code anchors (HEAD)

```
packages/pipeline/src/pipeline/model_backends.py   # VllmThinkingBackend retry loop
packages/whisker/src/whisker/tapetum_llm/judge_task.py
packages/whisker/src/whisker/tapetum_llm/cli.py    # _RetryCountFilter, tombstones, timeouts
packages/whisker/src/whisker/tapetum_llm/pdf_judge.py  # metadata short-circuit
research/tapetum-llm-speedup/25-retry-economist.md   # prior pricing
research/tapetum-llm-throughput/07-retry-timeout-auditor.md
```
