# 28 - Shared pod noise (alliance-pod multi-tenant impact on cold-run variance)

**Verdict:** usable-with-conditions — `alliance-pod` is a dedicated RunPod instance but an **Alliance-shared** hourly pod with no tenant isolation; noisy neighbors add **wall-time jitter** and **MoE batch-composition variance** on cold fleets; isolation knobs exist but trade throughput or are blocked in the 1-pod corpus.
**Confidence:** high (SERVICES.toml + MODELS.md + measured flip floor; external-tenant load is modeled, not continuously metered)

**Variance risk (cold-run): HIGH**

**Sources:** `SERVICES.toml:59-74`, `MODELS.md:55-78`, `packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md:27-31`, `packages/whisker/research/llm-stack/03-determinism-auditor.md`, `packages/whisker/research/deepseek-v4-pro/13-claude-invariant-auditor.md`, `research/cold-run-10min/51-determinism-risk-matrix.md`, `research/cold-run-10min/13-in-paper-parallel-risk.md`, `research/cold-run-10min-1pod/05v-web-batch-invariant.md`, `research/tapetum-llm-speedup/140-litellm-router-loadbalancing.md`, `research/tapetum-llm-speedup/101-vllm-bench-harness.md`.

**Hard constraint:** single `alliance-pod` only (`00-baseline.md`). Twin `h200x8-deepseek-v4-pro` is out of scope for this corpus.

---

## Executive answer

| Question | Answer |
|----------|--------|
| Is `alliance-pod` shared / multi-tenant? | **Yes (Alliance-shared).** Separate instance from `h200x8-deepseek-v4-pro`, same model, 24/7 hourly pod; not an exclusive single-tenant endpoint. Research treats **foreign vLLM traffic** on the same scheduler as a first-class cold-run risk. |
| Impact on cold-run **wall** variance | **HIGH when externally loaded.** Sustained 381-paper fleet at client c=32 overfills 16 server slots for ~50 min; external tenants consume slots → longer queue waits → run-to-run wall jitter. Modeled worst case: half the slots externally occupied roughly **doubles** effective wall on that pod's shard (`140-litellm-router-loadbalancing.md`). |
| Impact on cold-run **verdict** variance | **HIGH even without foreign traffic.** Baseline ≥25% identical-rerun flip rate at c=32; MoE expert routing + non-batch-invariant kernels flip tokens under batch composition (`MODELS.md:69-78`, `tapetum_llm.md:31`). Shared neighbors add an **uncontrolled batch-composition axis** on top of that floor. |
| Isolation knobs? | **Limited.** Client can lower `--concurrency` (throughput tax). Server can enable `VLLM_BATCH_INVARIANT=1` (~50% throughput cost, rejected for speed). No per-tenant vLLM queue, no RunPod-side slot reservation, no Fireworks-style session affinity on this stack. Practical mitigations: off-hours windows, metrics watch, dedicated twin (blocked here). |

---

## What SERVICES.toml declares

```toml
# Alliance shared pod (Sam). Same model as h200x8-deepseek-v4-pro but a
# separate running instance. Key lives in the gitignored .env via
# ALLIANCE_POD_KEY; only the env-var name is committed here.
# Runs 24/7; billed per hour of uptime, NOT per token, so run size is not a
# cost question (used as the whisker tapetum_llm advisory lane endpoint).
[services.alliance-pod]
backend = "vllm_thinking"
base_url = "https://sgjy18glyi4blu-8000.proxy.runpod.net/v1"
api_key = "$ALLIANCE_POD_KEY"
model = "deepseek-v4-pro"
max_context_window = 393216
stream = true
```

| Property | Implication |
|----------|-------------|
| **"Alliance shared pod (Sam)"** | One RunPod deployment shared across Alliance workloads, not a private per-project replica. |
| **Separate from `h200x8-deepseek-v4-pro`** | Isolation is **instance-level** (different URL/key), not model-level. Same weights, different scheduler state. |
| **24/7 hourly billing** | Pod stays up for multiple consumers; cold fleets can collide with unrelated traffic. |
| **`ALLIANCE_POD_KEY` in `.env`** | API key gates access but does **not** reserve GPU slots or isolate batch queues inside vLLM. |

`h200x8-deepseek-v4-pro` is the **twin** candidate for dual-shard (`SERVICES.toml:47-57`, `57-alliance-inventory.md`). It is the natural "exclusive lane" for measurement baselines; it is **not** available in the 1-pod corpus.

---

## What MODELS.md says about variance (mechanism)

### Client-side pins (necessary, insufficient)

Greedy decoding (`temperature=0`, `seed=0`, `top_k=1`) and serial dissect semaphores (`_parallel_semaphore=1`, `_task_semaphore=1`) remove **client-induced** variance. Tapetum uses a **D11 exemption**: paper-level `--concurrency 32` with serial in-paper calls (`tapetum_llm.md:27-29`).

### Server-side variance (already active on cold run)

| Mechanism | Source | Cold-run effect |
|-----------|--------|-----------------|
| **MoE routing** | `MODELS.md:69-70` | Batch composition affects which experts activate. Foreign requests change composition even when tapetum serializes calls **within** a paper. |
| **Non-batch-invariant kernels** | `MODELS.md:77-78` | Matmul/attention/RMSNorm reduction order depends on batch size; greedy argmax can flip at decision boundaries. |
| **Continuous batching** | `03-determinism-auditor.md` | Default vLLM mode on alliance-pod; `temperature=0` + `seed=0` do **not** guarantee identical outputs across runs. |

Documented server-side fixes (`VLLM_BATCH_INVARIANT_LEVEL`, SGLang `--enable-deterministic-inference`) are **not** enabled on alliance-pod for the speed path (`05v-web-batch-invariant.md`: ~50% throughput tax).

Fireworks deployment invariants (`min=max=1`, session affinity) in `MODELS.md:79-95` **do not apply** to RunPod vLLM proxy endpoints.

---

## Noisy-neighbor impact on cold-run variance

### Cold-run load profile (maximum interference window)

| Parameter | Value | Noise relevance |
|-----------|-------|-----------------|
| Papers / calls | 381 / ~2284 | Longest sustained fleet; ~50 min window for foreign traffic overlap |
| Client c | **32** | Overfills `--max-num-seqs 16`; queue depth sensitive to external occupancy |
| In-paper | serial | Reduces **within-paper** burst width; does **not** isolate from foreign batches |
| Fingerprint skip | **off** (cold) | Every call hits the pod; no warm-run escape |

### Wall-time variance (run A vs run B, same code)

Foreign tenants hold vLLM slots without tapetum's knowledge:

```
effective_slots = 16 − external_in_flight
wall ≈ (N × L) / effective_slots + queue_tail
```

Modeled scenario (`140-litellm-router-loadbalancing.md`): **8/16 slots externally occupied** on alliance-pod while a sibling pod is idle → tapetum shard wall ≈ **2855 s** vs **1428 s** on an idle pod (same call count). That is **~2× wall jitter** from occupancy alone, before per-call latency drift.

Prometheus on alliance-pod exposes `num_requests_running`, `num_requests_waiting`, `request_queue_time_seconds` (`96-vllm-metrics-probe.md`). Cold runs should log these; absence of logging does not mean absence of contention.

### Verdict / semantic variance (quality-stability)

Measured floor without any lever change:

- **≥25% verdict-flip rate** on identical reruns at production c=32 (`tapetum_llm.md:31`, `whisker/CLAUDE.md` advisory section, `51-determinism-risk-matrix.md` A/A noise floor).
- MoE batch variance is **already embedded** in the baseline flip floor at c=32 / 16 slots (`13-in-paper-parallel-risk.md:65-69`).

Noisy neighbors **add**:

1. **Unpredictable batch neighbors** during each of ~2284 decodes across ~50 min.
2. **Queue-position variance** → different inter-arrival batching when slots free.
3. **Retry-path bifurcation** when DeepSeek JSON corruption triggers multi-turn retries (`03-determinism-auditor.md`) — corruption rate may correlate with load (unmeasured on alliance-pod).

Cold-run **A/B lever claims** (metadata short-circuit, verdict-first, dense offload) cannot attribute drift to a code change until **double-A noise floor** is measured under the **same external load conditions** (`51-determinism-risk-matrix.md`, `150-verifier-warmrun-quality.md`).

### Interaction with speed levers (1-pod corpus)

| Lever | Shared-pod noise interaction |
|-------|-------------------------------|
| Client c=32 (default) | **Compounds** — maximum cross-paper batch diversity + foreign traffic |
| `--max-num-seqs 16` (fixed) | Cannot absorb external load by raising cap (+57% wall forbidden) |
| MTP k=1 (server ops) | **Compounds** — verify batch_size=2 adds argmax flip edges (`05d-web-mtp-specdecode.md`) |
| In-paper parallel | **Rejected** — W≤12 bursts worsen MoE composition; ~0 s fleet savings (`13-in-paper-parallel-risk.md`) |
| `VLLM_BATCH_INVARIANT=1` | **Mitigates** verdict variance; **~2× L** → incompatible with ≤600 s goal (`05v-web-batch-invariant.md`) |
| Off-hours cold run | **Mitigates** wall jitter; does not remove MoE non-invariance |

---

## Isolation knobs (inventory)

### Available today

| Knob | Layer | Effect on noise | Cost / constraint |
|------|-------|-----------------|-------------------|
| **`--concurrency 1`** (CLI) | Client | Reduces tapetum cross-paper batching; lowers MoE neighbor diversity | Fleet wall ≈ **3003 s → unusable** for 10 min goal; regression baselines only |
| **Serial in-paper calls** | Client | Already on; isolates within-paper call chain | Does not block foreign requests in same vLLM batch |
| **Off-hours / maintenance window** | Ops | Reduces external slot theft | Informal; no enforcement |
| **`GET /metrics` scrape** | Ops | Detect `num_requests_waiting` / queue p95 during cold run | Observability only |
| **`VLLM_BATCH_INVARIANT=1`** | Server env | Batch-composition-invariant kernels | **~50% throughput**; rejects speed path; V4-Pro not on vLLM tested-model list |
| **Dedicated twin pod** | Infra | Full scheduler isolation | **`h200x8-deepseek-v4-pro` blocked** in 1-pod corpus |
| **Dual-pod + least-busy paper-start** | Client routing | Skews work away from contended pod | Requires second live twin; N/A for 1-pod |

### Not available (do not assume)

| Expected knob | Reality on alliance-pod |
|---------------|-------------------------|
| Per-API-key slot reservation | vLLM OpenAI server: single shared continuous batch |
| RunPod proxy tenant isolation | One pod, one scheduler; Bearer key is auth only |
| Fireworks `session-affinity` / `min=max=1` | Documented for Fireworks (`MODELS.md:84-87`), not RunPod template |
| Raise `--max-num-seqs` for headroom | **Forbidden** (+57% wall, `00-baseline.md`) |
| Client-side batch-invariant mode | No pydantic-ai / httpx flag; server env only |
| `auto_tune.sh` / server restarts during fleet | **Do not run** on live shared pod (`101-vllm-bench-harness.md`) |

### Tapetum-specific determinism posture

`tapetum_llm.md:31` documents variance as an **advisory-lane budget**, not zero defect:

> token-level output on a hosted vLLM pod is not bit-stable under continuous batching and MoE expert routing; this holds already at low concurrency and is a documented variance budget of the advisory lane, not a defect.

Shared-pod noise **widens** that budget on cold runs; it does not change the architectural choice (LLM never gates).

---

## Risk matrix (cold-run, shared alliance-pod)

| Dimension | Risk | Rationale |
|-----------|------|-----------|
| **Wall time run-to-run** | **HIGH** | 50 min sustained load; external slot theft can ≈2× effective queue time (modeled) |
| **Verdict flip run-to-run** | **HIGH** | ≥25% baseline + MoE batch non-invariance + foreign batch neighbors |
| **A/B lever attribution** | **HIGH** | Without load-matched double-A, drift confounds code changes with occupancy |
| **Proxy / infra false-fail** | **MED** | Queue + prefill under contention → RunPod 524 risk (`12-runpod-proxy.md` class) |
| **Bit-exact sidecar replay** | **HIGH** | Incompatible with default server mode; needs `VLLM_BATCH_INVARIANT` or exclusive pod |

**Overall cold-run variance risk: HIGH**

Downgrade to **MED** only if: (1) cold fleets run in a verified quiet window with metrics showing **external_in_flight ≈ 0** for the full run, **and** (2) double-A on 381 papers shows `flip_AA ≤ 5%` on the four-component vector (`51-determinism-risk-matrix.md`). Neither condition is evidenced today.

---

## Findings

- [CRITICAL] **`alliance-pod` is explicitly an Alliance shared pod**, not an exclusive replica. Evidence: `SERVICES.toml:59-63`. Impact: cold fleets compete with unrelated traffic on one vLLM scheduler for ~50 min.

- [CRITICAL] **API key ≠ isolation.** `ALLIANCE_POD_KEY` authenticates; vLLM still continuous-batches all authorized clients into one `--max-num-seqs 16` pool. Impact: no knob in repo config reserves slots for tapetum cold runs.

- [HIGH] **MoE + non-batch-invariant kernels make batch neighbors a verdict lever.** Evidence: `MODELS.md:69-78`; `13-claude-invariant-auditor.md:35-36` ("foreign batch traffic shares the vLLM scheduler"). Impact: cold run at c=32 is the worst-case neighbor diversity regime.

- [HIGH] **Baseline flip floor ≥25% before shared-pod effects.** Evidence: `tapetum_llm.md:31`, `51-determinism-risk-matrix.md:15`. Impact: cold-run variance risk is **HIGH** even on a quiet pod; shared occupancy adds wall jitter on top.

- [HIGH] **Modeled external half-occupancy ≈2× wall on alliance-pod shard.** Evidence: `140-litellm-router-loadbalancing.md:10` (8/16 external slots). Impact: run-to-run wall can swing by **tens of minutes** if external load differs between cold runs.

- [MED] **`VLLM_BATCH_INVARIANT=1` is the only server knob that directly targets batch-composition variance.** Evidence: `MODELS.md:77-78`, `05v-web-batch-invariant.md`. Impact: mitigates semantic variance but **rejects** ≤600 s speed goal (~50% throughput).

- [MED] **Lowering client c reduces tapetum-induced batching but not foreign traffic.** Evidence: `03-determinism-auditor.md` proposes c=1 for baselines. Impact: partial mitigation; unusable for production cold-run speed target.

- [LOW] **Separate instance from `h200x8-deepseek-v4-pro` isolates prefix-cache and scheduler state, not Alliance sharing.** Evidence: `SERVICES.toml:47-74`. Impact: twin is an isolation upgrade path when unblocked, not current state.

---

## False-pass hypothesis

Operator schedules a cold fleet, sees **~3003 s ± 50 s**, and treats wall variance as "MoE noise within tolerance." External traffic was absent both times. Verdict A/B for a new lever shows "no regression" because flip rate is already 25%+. **False conclusion:** shared pod is harmless. Reality: wall was stable by luck; verdict variance remains too high to gate levers without double-A under matched load.

---

## False-fail hypothesis

Operator sees **3200 s vs 2800 s** between two cold runs, blames a shipped client lever, and reverts a **−400 s** metadata short-circuit. Root cause: alliance-pod had 6–10 external slots occupied during the slower run (visible in `/metrics` queue depth). **False fail:** infra occupancy, not code regression.

---

## What would change my mind

1. **Instrumented 381-paper cold run** with `/metrics` scrape every 10 s, logging `num_requests_running`, `num_requests_waiting`, and external occupancy estimate → if wall variance **<5%** across three runs with occupancy matched, downgrade wall risk to **MED**.
2. **Double-A at c=32** with `flip_AA < 5%` on four-component equivalence → downgrade verdict risk to **MED** (contradicts current docs unless batch-invariant mode deployed).
3. **Dedicated exclusive pod** (twin live, zero foreign traffic for 30 days) with ≤2% daily flip on 20-paper serial reruns → downgrade overall to **LOW** for that pod only (not alliance-pod).

---

## Planning implication (1-pod, ≤600 s)

Shared-pod noise is a **measurement confounder**, not a primary **−800 s** lever. For cold-run research in this corpus:

1. Treat **HIGH** variance risk as default when interpreting wall and A/B results on alliance-pod.
2. Prefer **metrics-instrumented** cold runs and document occupancy alongside wall.
3. Do **not** enable `VLLM_BATCH_INVARIANT` on the speed path; accept semantic variance budget or move measurement to an exclusive pod (blocked here).
4. Speed levers that **raise** concurrent heterogeneous load (in-paper parallel, c>32, seq=32) remain **rejected** partly because they **compound** shared-pod MoE variance.
