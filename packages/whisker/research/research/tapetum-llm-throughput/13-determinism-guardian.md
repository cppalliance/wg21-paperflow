# 13 - Determinism-Guardian

**Verdict:** usable-with-conditions — the 4.2× wall regression (692.3 s → 2886.4 s on 381 papers, `00-baseline.md:10-14,41-42`) is largely legitimate call-volume growth from the 07-17 source-aware lane; most throughput levers that cut work or raise server concurrency are **forbidden** or **risky** under project determinism and lane fidelity rules. Safe speedups are infra-side (batch-invariant kernels, second live pod) or already deployed (client c=32 overfill).
**Confidence:** high

## Findings

### Lever 1 — In-paper parallel unit checks (multiple in-flight requests for ONE paper)

- [HIGH] **Ruling: allowed-with-conditions (technically), risky (recommended against).** D11 binds `dissect` via `_parallel_semaphore` / `_task_semaphore` at 1 (`CLAUDE.md:86-88`; `pipeline/CLAUDE.md:92`; `MODELS.md:57-60`); it does **not** forbid tapetum's per-package carve-out (`judge_task.py:17-23`; `cli.py:118-119`). Parallelizing unit checks inside one paper would not violate D11.
- [HIGH] **Serial in-paper cascade is documented lane policy, not an accident.** `tapetum_llm.md:27-31` sets `concurrency: 1` for the in-paper cascade; `pdf_judge.py:648-649` states the CLI paper-level semaphore is the bound; `unit_judge.py:379-410` awaits each unit check in a `for` loop. Changing this is an explicit design reversal.
- [CRITICAL] **MoE + continuous-batching variance already active; in-paper parallel amplifies it.** Hosted vLLM decode is batch-non-invariant (`MODELS.md:77-78`); DeepSeek-V4-Pro MoE expert routing shifts with batch composition (`MODELS.md:69-70`). The advisory lane already documents token-level non-stability and a ≥25% verdict-flip rate (`tapetum_llm.md:31`; whisker `CLAUDE.md` advisory section). With fleet client c=32, up to 16 server decode slots are occupied (`00-baseline.md:81-85`; `tapetum_llm.md:29`). Adding 2–5 concurrent unit calls **per paper** multiplies in-flight sequences on the same pod, increasing batch reshaping and expert-routing churn beyond what the 692 s benchmark embedded (`16-determinism-auditor.md:8-14`).
- [MED] **Aggregation is order-independent, but verdict inputs become noisier.** Post-processing (`verify_unit_evidence`, `verify_defect_counts`, fail-closed `coverage_complete`) is deterministic Python (`unit_judge.py:412-464`). Parallelism would not scramble sidecar ownership; it would change **which defects survive** MoE/batch boundary flips on borderline unit verdicts.

**Summary:** Not forbidden by D11. **Risky** under the advisory lane's documented variance budget and explicit serial cascade. Accept only with a measured flip-rate budget (triple rerun A/B per `16-determinism-auditor.md:34`) and pod batch-invariant mode.

---

### Lever 2 — Raising client `--concurrency` beyond 32

- [CRITICAL] **Ruling: forbidden (operational + determinism).** Full-corpus c=381 experiment: 257/381 peer-closed errors (`00-baseline.md:57-58`). RunPod proxy idle-kill ~100 s (`research/concurrency-381/`; `cli.py:127-129` `_MAX_TESTED_CONCURRENCY = 32` with warning above). This is an infrastructure hard ceiling, not a tunable.
- [HIGH] **Marginal determinism cost rises with N even below the ceiling.** Batch/MoE variance scales with concurrent decode depth (`MODELS.md:69-70,77-78`; `16-determinism-auditor.md:10-14`). Client c=32 overfills server `--max-num-seqs 16` deliberately so freed slots back-fill without exceeding 16 simultaneous decodes (`tapetum_llm.md:29`; `00-baseline.md:81-85`). Raising c toward 381 deepens the queue without adding GPU parallelism (`research/concurrency-381/20-batch-alternatives.md:20-21`).

**Summary:** **Forbidden.** Evidence-backed negative result; also increases verdict-distribution drift.

---

### Lever 3 — Raising server `--max-num-seqs` 16 → 32

- [CRITICAL] **Ruling: forbidden (throughput + determinism).** Four full-corpus measurements: server 16 + client 32 = **692.3 s (best)**; server 32 + client 32 = **1090.2 s** (+57%) and warm rerun **1465.2 s** (`research/slots-32-regression/SYNTHESIS.md:6-14`; `tapetum_llm.md:301`; `00-baseline.md:84-85`). Root cause: MoE decode loads union of experts per step; 32 concurrent sequences increase memory-bandwidth pressure (`SYNTHESIS.md:17-21`).
- [HIGH] **Determinism impact is secondary but real.** More simultaneous decodes = more batch-composition reshaping (`16-determinism-auditor.md:8-14`). Flip condition: MoE-aware batch scheduling in a future vLLM release (`SYNTHESIS.md:55-58`; `tapetum_llm.md:307-312`).

**Summary:** **Forbidden** until flip conditions met. Proven ~60% wall regression; do not re-test without CTO sign-off and batch-invariant A/B.

---

### Lever 4 — Dual-pod sharding

- [HIGH] **Ruling: allowed-with-conditions (throughput), risky (determinism).** Architecturally free when a second pod is live: disjoint PID lists or `--shard-pods` round-robin (`research/llm-batching/18-load-splitter.md:10-14`). D11 does not block multi-process or per-paper pod assignment.
- [CRITICAL] **Documented determinism concern: verdict drift by pod assignment.** Independent vLLM schedulers with no shared prefix-cache state; same paper rerun on pod A vs pod B can flip tier-1 signals (`18-load-splitter.md:23-24`; `16-determinism-auditor.md:8-14`). Whisker gate stays green; advisory distribution shifts by shard, not conversion quality.
- [MED] **Conditions:** bind `fast` and `deep` to the **same pod per paper** (`18-load-splitter.md:16-17`); treat elevated `error` counts on a dead shard as infra false-fail, not conversion false-fail (`18-load-splitter.md:27-28`). Today only `alliance-pod` is live; twin pod returned 404 (`18-load-splitter.md:8-9`; `tapetum_llm.md:304`).

**Summary:** **Allowed-with-conditions** for throughput when a second healthy pod exists. **Risky** for rerun-stable advisory baselines unless batch-invariant mode or explicit variance budget. Not a determinism rule violation.

---

### Lever 5 — Cutting unit checks / caps / risk-routing thresholds

- [CRITICAL] **Ruling: forbidden (lane fidelity).** Source-aware lane is fail-closed by design (`tapetum_llm.md:122`; `unit_judge.py:446-464`): missing source packet, failed unit call, cap overflow, ambiguous evidence, or source-ungrounded quote caps verdict at `review` and records unchecked units. Tonight's run: 321 `source_aware_review_cap` (`00-baseline.md:29-30`).
- [HIGH] **Project Fidelity section targets analytical pipelines (dissect/agora), but the lane inherits the same "no silent partial" philosophy.** `CLAUDE.md:123-129`: if full fidelity cannot be achieved, stop; never produce a partial result mistakable for complete. Tapetum is advisory-only (`tapetum_llm.md:3-4`), but lowering `MAX_UNIT_CHECKS` (5, `constants.py:223`), skipping mandatory metadata check, or weakening risk-router thresholds would emit **`pass` on incomplete coverage** — the documented false-pass class the 07-17 lane was added to close (`tapetum_llm.md:93-122`; P0957R8 / P0533R9 anchors in `tapetum_llm.md:93,117-118`).
- [MED] **`--all-pages` / exhaustive inspect modes exist for review tooling; fleet default must stay routed + capped.** `coverage_mode` is fingerprinted separately (`cli.py:112-113,615`; `tapetum_llm.md:134`). Removing caps on fleet runs without `--all-pages` violates the lane contract.

**Summary:** **Forbidden** for fleet throughput. Caps and fail-closed routing are fidelity load-bearing, not waste.

---

### Lever 6 — Reducing structured-output schema size or quotes per finding

- [CRITICAL] **Ruling: forbidden (determinism D6 + measured stability).** D6 requires `output_type=<PydanticModel>` (`CLAUDE.md:83`). **Fewer schema fields increase output variance**, not decrease it: Qwen 30B at 3 fields showed 20–28 claim counts across 10 runs; 5 fields stabilized to 19–20 (`MODELS.md:35-51`). Shrinking `DefectFinding` / `UnitCheck` would **worsen** rerun stability.
- [HIGH] **Two-sided evidence verification requires verbatim quotes and disposition fields.** Monolith/page path: `ground_spans` → `classify_candidate_evidence` with `present_in_candidate` / `candidate_not_found` / `ambiguous` (`tapetum_llm.md:37-48`; `pdf_judge.py:690-706`). Unit path: only `source_status == exact` + `candidate_status == not_found` enters verified defect groups (`unit_judge.py:425-429,554-557`). `source_quote` max 25 words and `MAX_MISSING_QUOTES = 5` are load-bearing for scale defects (151 missing `constexpr`, `tapetum_llm.md:93`; `constants.py:75-77`).
- [MED] **Output-discipline caps (reasoning word limits, ≤3 evidence spans) are latency levers, not schema cuts.** `tapetum_llm.md:217-226`; `unit_judge.py:156-158`. Trimming those affects recall of reported defects, not JSON field count; still risky for fidelity if pushed far.

**Summary:** **Forbidden** to remove schema fields or quote slots. Field-count reduction is anti-deterministic per `MODELS.md`. Quote reduction breaks two-sided verification meaning.

---

### Lever 7 — Trimming `CONVERSION_CONTRACT` from fleet (non-all-pages) unit-check prompt

- [MED] **Ruling: allowed-with-conditions (no explicit anti-divergence rule), risky (consistency + invalidation).** No project rule forbids different system prompts between fleet and `--all-pages` review. Fingerprints **do** hash prompt text and `coverage_mode` separately (`cli.py:563-616`; `_LANE_VERSION` bumps on contract changes `cli.py:99-113`).
- [HIGH] **`CONVERSION_CONTRACT` is shared across monolith, page escalation, and unit checks.** Single source in `unit_judge.py:70-106`, imported by `pdf_judge.py:85-87,192,227`. Trimming for fleet unit checks only would make **monolith judge and unit judge disagree on sanctioned behavior** (TOC removal, front-matter mapping, wording divs) within the same paper run — a consistency defect, not a throughput win.
- [HIGH] **07-22 prompt growth is part of the regression story; trimming trades tokens for false-pass risk.** Baseline notes full contract moved into `UNIT_CHECK_SYSTEM_PROMPT` (`00-baseline.md:74-77`). TOC-leak rule in contract mirrors deterministic `no_toc_leak` (`tapetum_llm.md:169`; `unit_judge.py:78-85`). Omitting it revives TOC-blind false-clears (P1122R3 baseline in `tapetum_llm.md` leaked-TOC discussion).

**Summary:** **Allowed-with-conditions** only if trimmed **identically** across all PDF judge prompts (monolith + page + unit) and re-measured on holdout. Fleet-only trim is **risky/forbidden in spirit** (split-brain rubric). Prefer output-discipline tightening over contract amputation.

---

### Cross-cutting (baseline numbers)

- [CRITICAL] Tonight's 2886.4 s run is a **full cold re-adjudication** (`_LANE_VERSION` 9; `00-baseline.md:43-45`), not a concurrency regression. Steady ~7.6 s/paper (`00-baseline.md:37-42`) vs 1.8 s/paper on 07-09 (`00-baseline.md:41-42`) matches ~4–9× call-volume estimate (`00-baseline.md:104-108`).
- [HIGH] **Bit-stable regression baselines require server-side batch-invariant mode** — infra ask, not a client knob (`tapetum_llm.md:31`; `MODELS.md:77-78`; `16-determinism-auditor.md:22`).
- [MED] Sampling pins are non-negotiable: D2/D5, greedy decoding (`MODELS.md:22-33`; `pipeline/CLAUDE.md:91`). Do not trade temperature/seed for speed.

## Speedup lever summary table

| Lever | Ruling | Primary cite |
|---|---|---|
| 1. In-paper parallel unit checks | allowed-with-conditions; **risky** | D11 carve-out `judge_task.py:17-23`; serial policy `tapetum_llm.md:27-31`; MoE `MODELS.md:69-70` |
| 2. Client c > 32 | **forbidden** | `00-baseline.md:57-58`; `cli.py:127-129`; `research/concurrency-381/` |
| 3. Server max-num-seqs 16→32 | **forbidden** | `research/slots-32-regression/SYNTHESIS.md:6-14` |
| 4. Dual-pod sharding | allowed-with-conditions; **risky** | `18-load-splitter.md:23-24`; bind fast+deep `18-load-splitter.md:16-17` |
| 5. Cut checks/caps/thresholds | **forbidden** | fail-closed `tapetum_llm.md:122`; `unit_judge.py:446-464`; `CLAUDE.md:123-129` |
| 6. Shrink schema/quotes | **forbidden** | field-count stability `MODELS.md:35-51`; two-sided verify `tapetum_llm.md:37-48` |
| 7. Trim CONVERSION_CONTRACT (fleet only) | allowed-with-conditions; **risky** if split | shared contract `unit_judge.py:70-140`; fingerprint `cli.py:596-615` |

## False-pass hypothesis

Fleet throughput work lowers `MAX_UNIT_CHECKS` or parallelizes unit checks while keeping client c=32. A paper with localized table cell swap (whisker clean, token recall high) draws unlucky MoE routing on a parallel unit batch; unit check returns `pass` with empty defects, monolith already passed, fail-closed coverage bit still set but operator focuses on footer pass count. Combined advisory stays `pass` on a conversion that routed-mode sampling would have caught on rerun A — **distribution shift masquerading as optimization** (`16-determinism-auditor.md:24-26`; `18-load-splitter.md:23-24`).

## False-fail hypothesis

Raising server `--max-num-seqs` to 32 to "feed more work" slows decode enough that unit checks hit `UNIT_CHECK_TIMEOUT_SECONDS`, marking units `failed`, triggering fail-closed `review` cap (`unit_judge.py:406-410,460-464`). Operators interpret the 321 `source_aware_review_cap` entries as "the lane is too strict" when the root cause is **forbidden infra tuning** inflating timeouts and retries (`research/slots-32-regression/SYNTHESIS.md:6-14`; tonight 54 model retries, `00-baseline.md:27-28,99-100`).

## What would change my mind

A controlled experiment on the **same 381-paper corpus** with frozen prompts/schemas: (A) current serial in-paper + c=32 + server slots 16, (B) parallel unit checks (max 3 in-flight) + same client/server caps, (C) same as B with `VLLM_BATCH_INVARIANT_LEVEL` enabled on the pod. Report per-PID verdict flip rate and pass/review/fail histogram vs(A). If flip rate ≤2% for B vs A **and** wall time drops ≥15%, I would upgrade lever 1 to **allowed**. If C is required for ≤2%, mandate infra before any in-paper parallelization.
