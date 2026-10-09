# Cold-run 48 min -> 10 min — Delta Synthesis (2026-07-24)

**Verdict band:** usable-with-conditions  
**Confidence:** high on diagnosis; medium on exact post-v11 wall (needs one fresh cold run)  
**Decision:** implement remaining levers in order below; **revive twin pod or accept ~20–25 min single-pod floor**

Swarm: baseline + ~60 Composer/Grok agents writing under `research/cold-run-10min/`,
plus prior 150-agent corpus `research/tapetum-llm-speedup/SYNTHESIS.md`.
HEAD git tip: `51cb704`. Working tree carries uncommitted v11 tapetum changes.

---

## 1. Bottom line

| Question | Answer |
|----------|--------|
| Is ~48 min real? | **Yes.** Measured 2883–3003 s cold fleet (381 papers, ~2284 LLM calls, alliance-pod / DeepSeek-V4-Pro, 16 slots, c=32). |
| Why so long? | Source-aware lane ≈6 calls/paper × ~20 s/call ÷ 16 slots. Not "lost concurrency." |
| Is 10 min reachable? | **Yes with MODERATE package + dual-pod (~596 s central).** |
| Dual-pod today? | **No.** Twin `h200x8-deepseek-v4-pro` → HTTP **404**. Alliance-pod → **200**. |
| Biggest surprise vs Jul-23 research | Most CONSERVATIVE + metadata short-circuit levers are **already coded in the working tree** (`_LANE_VERSION = 11`) but **not committed** and **not remeasured**. |

If you still see ~48 min, you are almost certainly running **pre-v11** (committed HEAD) or an old workspace. Remeasure after the local v11 patch.

---

## 2. What already landed (working tree, uncommitted)

Verified in `packages/whisker/src/whisker/tapetum_llm/` (`10-impl-status-auditor.md`):

| Lever | Status |
|-------|--------|
| Metadata short-circuit (fail **and** review) | Done — `pdf_judge.py:742+`, `adjudicate.py:521+` |
| HMAC per-paper guard tag | Done PDF path — `cli._paper_guard_tag`; text lane still missing |
| Candidate-md-first user messages | Done for unit/page; not monolith/metadata |
| Error tombstone fingerprints + `--retry-errors` | Done |
| LJF paper order | Done |
| `asyncio.to_thread(screen_pages)` | Done |
| Monolith `wait_for` | Done |
| Dual-pod shard CLI | **Missing** |
| Verdict-first / terse pass schema | **Missing** |
| Escalation dedupe | **Missing** |
| Per-call sidecar timings | **Missing** |
| Deterministic metadata (no LLM) | **Missing** (AGGRESSIVE) |

**Expected wall after shipping/running v11 alone (single pod):** roughly **~21–25 min** (short-circuit −~1059–1341 s, partial prefix), not 10 min. Arithmetic: `11-wall-arithmetic.md`, `22-path-a-b-10min.md`.

---

## 3. Path to ≤10 min

### Path A — twin alive (recommended)

```
N cuts (short-circuit + escalation dedupe)
+ prefix/HMAC (already partial)
+ verdict-first schema (~−155 s on survivors)
+ dual-pod Semaphore(16)×2 (~÷1.9 on compute)
→ ~530–670 s (central ~596 s)
```

Needs: restart `h200x8-deepseek-v4-pro` + ~20 lines `--shard-pods` in `cli.py` (custom shard, not LiteLLM — `45-litellm-vs-custom-shard.md`).

### Path B — twin stays dead

Single-pod MODERATE ceiling ≈ **~1490 s (~25 min)**. Compute term alone on 1419 remaining calls @ 16 slots is ~1774 s before latency cuts.

To hit 10 min without twin, you need **at least one** of:

1. **Second live DeepSeek endpoint** (revive twin or stand up another V4-Pro replica).
2. **Dense unit-check offload** to a fast dense pod (`h200-qwen3-32b` / gemma) with A/B quality gate (AGGRESSIVE; `16-dense-judge-candidates.md`).
3. **Hardware uplift** toward official V4-Pro recipe (**8×H200 DP+EP**, not 1×H200) — `40-vllm-deepseek-recipe.md`. Official recipes treat "H200" as a full node.

Raising `--max-num-seqs` 16→32 remains **forbidden** (+57% wall, `slots-32-regression`).

---

## 4. Fresh external findings (post Jul-23)

| Lever | Verdict | Source cards |
|-------|---------|--------------|
| Official V4-Pro recipe pins `max-num-seqs 16`, `MBT 16384`, `deepseek_v4` parsers, `FULL_DECODE_ONLY` | Align with our 16-slot pin; ops should confirm flags | `05a`, `40`, recipes.vllm.ai |
| Alliance hardware | Already **8×H200 TP8+EP**, not 1×GPU. Wider EP alone does not hit 10 min; second replica does | `53`, `40` |
| Ops kernels at fixed seqs=16 | `--all2all-backend deepep_low_latency` + `--enable-dbo` are ops-actionable A/B; FlashInfer MoE not default | `64`, `05c` |
| MTP k=1 | Possible **modest** decode win; JSON+reasoning+MTP is version-sensitive; A/B required; not a solo path to 10 min | `05d`, `66` |
| MTP at high concurrency / short OSL | Can **hurt** | vLLM GB300 blog via `05a` |
| `thinking_budget` / Non-think | Client already omits budget (~0 s). Official "disable thinking / use Flash" is a **product** tradeoff, not a free knob on our schema-in-prompt path | `46`, `59` |
| SGLang migration | Still **reject / revisit later** | `05g` |
| HTTP client retune | Still **noise** | `27`, `63` |
| Docling/olmocr "speed" | Still **different workload** (extraction, no MoE judge) | `56` |
| NVFP4 / Blackwell quant | Not worth A/B on H200 for 10 min goal | `65` |
| Dual-pod shard algorithm | `blake2b(pid) % N` after health filter; custom shard, not LiteLLM | `67`, `45` |

### Residual waste after v11 short-circuit

| Class | Fleet share | Source |
|-------|------------:|--------|
| Metadata fusion-dead (eliminated at v11) | 44.6% | `24`, `17` |
| Cap-locked pass-tier units + refuted escalations | **~12%** still open | `50` |
| Escalation dedupe remaining | **~4 s** | `48` |
| Unit checks that change **merged** fusion verdict | **~3/381** (16/381 is any-LLM change, mostly rescue/clear) | `70` |

---

## 5. Execution order (do this)

### Day 0 — measure truth

1. Commit or at least run local v11 tapetum changes.
2. Cold fleet: `uv run --package whisker whisker-tapetum-llm --force` (or lane bump) on alliance-pod.
3. Record footer wall + call census. Expected: **~20–25 min**, not 48.
4. If still ~48 min: short-circuit not firing — check metadata pass rate / flags.

### Day 1 — free / low-risk code (single pod)

1. Finish HMAC + document-first on **HTML/text lane**.
2. Escalation dedupe (~23 s).
3. Per-call `call_timings[]` in sidecars (unlocks honest A/B).
4. Ops: confirm `--tokenizer-mode deepseek_v4`, `--reasoning-parser deepseek_v4`, APC on, `max-num-batched-tokens 16384`, keep `max-num-seqs 16` (`26-server-ops-checklist.md`).

### Day 2 — MODERATE software

1. Verdict-first / terse pass-path schema for `UnitCheck` (A/B vs holdout).
2. Quality gate protocol: `25-quality-gate-protocol.md` (fleet A/A once, then per-lever A/B).

### Day 3 — infra (required for 10 min)

1. **Bring twin pod back** (404 today).
2. Ship `--shard-pods alliance-pod,h200x8-deepseek-v4-pro` with per-pod Semaphore(16), health probe both, shard-set in fingerprint (`67-dual-endpoint-shard-patterns.md`).
3. Remeasure cold → expect **~9–11 min**.

### Optional / later

- MTP k=1 A/B only after structured-output patches confirmed on pod image.
- Dense-judge offload program (weeks).
- Judge distillation from ~1510 labeled unit checks/run (`05h`).

---

## 6. Honest limitations

- Stacked wall times are **models** until a post-v11 cold run exists.
- Metadata short-circuit on **review** skips all units (inspect loses sub-findings; fleet verdicts unchanged per P145). Use `--inspect` / `--exhaustive-units` when you need full reports.
- Dual-pod introduces MoE cross-pod verdict-drift risk: require verdict-identity check, not vibes.
- Images/VLM skipped per operator note.

---

## 7. Product note (steelman)

Warm incremental is already **~65 s** (→ ~10–15 s after tombstone FP). Nightly cost of a **lane bump** cold run is the pain, not every night. Still: a 48 min (or even 25 min) forced cold blocks iteration. Keep the **10 min cold** target for lane-version bumps; do not confuse it with warm steady state (`31-steelman-target.md`).

---

Sources: `00-baseline.md`, `10`–`70` persona/web cards in this directory, `research/tapetum-llm-speedup/SYNTHESIS.md`, live probes 2026-07-24, code under `packages/whisker/src/whisker/tapetum_llm/`.
