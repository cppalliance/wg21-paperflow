# 29 - Ideal verification fleet cost (381 papers, one pod)

**Verdict:** usable — `ideal_verification` is a **0.13% call-class** on the 381-paper cold fleet; **~60–90 s** direct LLM wall (**2–3%** of v10 cold), not a lever toward ≤600 s. Fleet **cannot** skip ideals via CLI; only **378/381** papers skip automatically (no ideal file). Removing or reordering ideal verify saves **≤90 s** cold; ideal-stage failures add **~14–16 s** fleet-equivalent waste from discarded judge work.
**Confidence:** high (sidecar inventory + v10 baseline + code paths)
**Date:** 2026-07-24
**Scope:** `ideal_verify.py`, `cli.py:_attach_ideal`, `golden_ideals.py`, v10 cold fleet (`research/tapetum-llm-speedup/00-baseline.md`). Single pod only.

**In cold-run critical path?** **no** (negligible N; quality-bearing on 3 golden-QA papers)

---

## Executive answer

| Question | Answer |
|----------|--------|
| **How often does it fire?** | **3/381 papers (0.79%)** — only when `ideal_path()` finds a matching file under `packages/tomd/tests/fixtures/golden/ideals/`. **3 LLM calls** max per cold fleet (one `run_task` → `IdealVerification` each). |
| **Direct cost (seconds)?** | **~60–90 s** serial ideal LLM time on cold v10 (**3 × ~20–30 s/call**). **~2.0–3.0%** of **3003 s** cold wall. |
| **Can fleet skip ideals?** | **No dedicated flag.** Skips only when **no ideal file** (378 papers) or **incremental fingerprint match** skips the whole paper before any LLM (warm steady state). |
| **Does skipping help ≤600 s?** | **No.** Even deleting ideal verify entirely frees **≤90 s**; gap after v11 MODERATE is **~660–893 s** (`10-impl-status-1pod.md`). |
| **Hidden cost?** | **IdealVerificationError** after a completed judge cascade: **2/6** v10 error tombstones; **~11–13 wasted judge calls** (**~220–260 s** serial, **~14–16 s** fleet-equivalent at S=16). |

---

## Seconds table (381-paper cold fleet, v10 baseline)

| Line item | Calls | Serial LLM (s) | Fleet wall @ S=16 (s) | Share of 3003 s wall |
|-----------|------:|---------------:|----------------------:|---------------------:|
| **Ideal verify (direct)** | **3** | **60–90** | **60–90** | **2.0–3.0%** |
| Per-paper breakdown (est.) | | | | |
| — P4020R0 (text, ~21k chars in) | 1 | ~20 | ~20 | |
| — P4182R0 (PDF, ~51k chars in) | 1 | ~29 | ~29 | |
| — P4228R0 (text, ~12k chars in) | 1 | ~17 | ~17 | |
| **Ideal-attributable judge waste** (2 errors, pre-ideal cascade) | **11–13** | **220–260** | **14–16** | **0.5%** |
| **Upper bound if ideal deleted** | −3 | −60–90 | −60–90 | −2–3% |
| **Upper bound if ideal runs first** (fail-fast on 2 errors only) | −11–13 | −220–260 | −14–16 | −0.5% |
| v10 fleet total (reference) | ~2284 | ~45 680 | ~3003 | 100% |
| Post-v11 survivor mix (reference) | ~1298 | — | — | 1 ideal call in mix |

Fleet wall for ideal direct cost assumes **3 globally serialized `run_task` calls** (`tasks.py:30–38`, `_TASK_CONCURRENCY=1`). Ideal calls do not overlap each other; they may interleave with non-`run_task` judge traffic from other papers, so realized wall is at the low end of the band unless all three ideal papers finish cascades in the same window.

---

## Frequency evidence

### Ideal inventory vs fleet overlap

| Ideal file | In 381 fleet? | Cold v10 outcome |
|------------|:-------------:|------------------|
| `p4020r0.md` | yes | `ideal_verification` persisted, `verdict=review`, 8 discrepancies |
| `p4182r0.md` | yes | v10: `IdealVerificationError` tombstone; later rerun: `verdict=agree` |
| `p4228r0.md` | yes | `IdealVerificationError` tombstone (ideal quote ungrounded) |
| `cwg1.md` | no | never triggered |

Runtime inventory (2026-07-24): **4** ideals on disk; **3** overlap converted fleet PIDs. Sidecar fingerprint field `ideal_sha256` non-null on **3/381** files.

### Call census

- v10 cold: **2284** LLM calls; ideal adds **+3** → **0.13%** of call volume (`research/tapetum-llm-speedup/37-ideal-verifier-accountant.md`, `10-call-graph-accountant.md`).
- Post-v11 metadata short-circuit survivor mix: **~1298** calls including **1** ideal (`14-router-quota-1pod.md`).

### Code trigger

```1219:1241:packages/whisker/src/whisker/tapetum_llm/cli.py
            async def _attach_ideal(
                result,
                debug_log: list[str] | None,
            ) -> None:
                if paper_ideal is None:
                    return
                ...
                result.ideal_verification = await asyncio.wait_for(
                    verify_against_ideal(
                        ideal_agent,
                        candidate_md,
                        ideal_text,
                        debug_log=debug_log,
                    ),
                    timeout=_PAPER_TIMEOUT_SECONDS,
                )
```

Placement: **after** `judge_pdf_extraction` or `adjudicate_paper` returns (`cli.py:1341`, `1422`). One LLM call per triggered paper (`ideal_verify.py:151–158`).

---

## Can the fleet skip ideals?

| Mechanism | Skips ideal verify? | Notes |
|-----------|:-------------------:|-------|
| **`--skip-ideal` / env flag** | — | **Does not exist** (no match in `cli.py` argparse). |
| **No ideal file for PID** | **yes** | **378/381** papers; `ideal_path()` returns `None` → `_attach_ideal` no-op. |
| **Incremental fingerprint skip** | **yes** (whole paper) | Bare full run: `incremental = not args.force` (`cli.py:1070–1071`). Matching fingerprint short-circuits **before** judge **and** ideal. Warm: **375/381** skipped in **64.8 s** (`00-baseline.md`). |
| **`--force` cold run** | no | All 381 evaluated; ideal fires on all 3 overlap papers. |
| **Remove ideals from fixture tree** | yes | Would silently disable verify fleet-wide; **HIGH** quality risk on golden-QA papers. |
| **Ideal `review` short-circuit cascade** | — | **Not implemented**; would **HIGH** false-pass risk (source-aware lane still required). |

Fingerprint includes ideal presence and content (`cli.py:633–646`): add/change/remove an ideal invalidates incremental reuse for that PID exactly once.

---

## Findings

- [CRITICAL] **Ideal verify is not a 10-min lever.** Evidence: 3 calls / 2284 = 0.13%; 60–90 s / 3003 s = 2–3%. Impact: call elimination must target unit checks (~1510 calls) and metadata survivors, not ideal.

- [HIGH] **No fleet skip switch; conditional by inventory only.** Evidence: `golden_ideals.py:94–106`, `cli.py:1219–1224`; grep shows no `--skip-ideal`. Impact: operators cannot disable ideal verify without removing fixture files or patching CLI.

- [HIGH] **Ideal failures waste completed judge work.** Evidence: v10 log `_scratch/whisker-fullrun/llm-stderr.txt` — P4182R0 logged `pdf-judge verdict=review` then `IdealVerificationError`; P4228R0 text lane then ideal fail. **~8** and **~4–7** calls respectively before ideal (`07-retry-timeout-auditor.md`). Impact: **~14–16 s** fleet-equivalent on cold run; ideal-only retry would recover warm rerun cost.

- [MED] **`run_task` serial gate applies to ideal.** Evidence: `tasks.py:30–38`. Impact: 3 ideal calls never overlap each other; upper bound 90 s with retries; not a fleet-scale choke (1510 unit checks also use `run_task`).

- [MED] **Ideal uses deep slot, 2048 max output tokens.** Evidence: `cli.py:1084–1091`, `_IDEAL_MAX_TOKENS = 2048` (`cli.py:146–148`). Impact: decode comparable to unit check; large prefill on P4182R0 (~51k chars candidate+ideal) pushes per-call toward **~29 s**.

- [LOW] **Advisory-only fusion semantics.** Evidence: `fusion.py` — ideal `review` caps at review; `agree` never promotes (`whisker/CLAUDE.md`). Impact: skipping ideal loses structural discrepancy signal on 3 papers; does not change deterministic whisker gate.

---

## False-pass hypothesis

Running ideal verify first and skipping the source-aware cascade when ideal returns `agree` would false-clear token-preserving corruption the monolith catches (candidate matches ideal structure but diverges from PDF source).

## False-fail hypothesis

`IdealVerificationError` on ungrounded quotes discards an otherwise usable judge sidecar (`status=error` tombstone, no fingerprint). P4182R0 completed at `review` with 5 unit checks before ideal post-grounding failed — operators see error despite substantive judge output.

## What would change my mind

- Ideal inventory grows beyond **3** fleet-overlap files without a proportional quality mandate → ideal share rises above **1%** calls.
- Per-call ideal latency histogram with p50 **>45 s** or p99 **>120 s** → dedicated per-call cap (120 s, matching unit/page) becomes a tail-risk fix.
- Sidecar replay showing ideal `agree` short-circuit would be safe on golden holdout → reorder + conditional skip becomes a **~14 s** cold-run win without quality loss.
