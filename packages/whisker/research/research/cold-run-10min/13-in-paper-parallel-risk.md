# 13 - In-Paper Parallel Risk (cold-run delta)

**Verdict:** A/B only — unit checks are dependency-independent and safe to parallelize mechanically, but MoE batch-composition variance on `alliance-pod` makes concurrent in-paper bursts a quality-stability regression risk with ~0 s expected fleet-wall savings; ship only after measured A/B on the 381-paper cold fleet.
**Confidence:** high

## Question

Could unit checks (and sibling in-paper LLM calls) within one paper run concurrently without violating quality-stability? What does MoE batch variance do? What is whisker's D11 exemption?

## Serial loops (current code)

### `unit_judge.py`

| Location | Pattern | Bound |
|----------|---------|-------|
| `run_unit_checks` L402–437 | `for unit_id in selected_unit_ids: await _check_one_unit(...)` | up to `MAX_UNIT_CHECKS` (5) routed; all pages when `exhaustive=True` / `required_unit_ids` |
| Post L439–472 | CPU-only: `verify_unit_evidence`, `_aggregate_defects`, `verify_defect_counts` | must stay serial after all unit LLM results |

Each `_check_one_unit` (L770–816) is one scoped LLM call: shared system prompt + full `candidate_md` prefix + per-unit `source_text` suffix (`guard_tag` stable per paper for APC reuse).

### `pdf_judge.py`

| Step | Location | Pattern | Data dependency |
|------|----------|---------|-----------------|
| Monolith | L668–684 | single `await run_judge_task` | needs `pdf_text`, `tomd_md` |
| Metadata | L701–714 | single `await run_metadata_outline_check` | needs `page_units[0]`, outline from `extract_page_units` — **not** monolith output |
| Page escalations | L818–898 | `for entry in flagged_entries: await _escalate_page(...)` | needs `screen_pages` result (L658, deterministic) — **not** monolith judgment |
| Unit checks | L923–945 | `await run_unit_checks(...)` | needs `route_pdf_units(page_units, raw_tomd_md)` — **not** monolith/metadata/escalation outputs |
| Verdict fold | L716–777, L891–898, L982–988 | CPU + deterministic demotion rules | **must** stay serial after all LLM results |

CLI timeout budget assumes serial in-paper depth: `_pdf_judge_timeout_seconds` scales `(1 + unit_count) × UNIT_CHECK_TIMEOUT_SECONDS` (`cli.py:160–168`); page escalations documented as "one at a time, never concurrently" (`cli.py:152–154`).

### Max parallel width per paper (routed fleet mode)

```
W ≤ 1 monolith + 1 metadata + MAX_PAGE_ESCALATIONS (5) + MAX_UNIT_CHECKS (5) = 12
```

`--all-pages` mode: W ≤ 2 + page_count (e.g. 15-page paper → W=22).

## Dependency conclusion

After shared CPU prep (`extract_page_units`, `screen_pages`, `route_pdf_units`), **all LLM calls for one paper could run in one parallel wave**. Serial order in `pdf_judge.py` and `unit_judge.py` is scheduling policy, not data necessity. Verdict folding stays serial.

Prior analysis: `research/tapetum-llm-speedup/20-in-paper-parallelist.md` (findings CRITICAL #1–#2).

## Quality-stability: could unit checks run concurrently?

**Mechanically:** yes. Units do not read each other's outputs; aggregation is deterministic post-processing.

**For quality-stability:** not without controlled measurement. Reasons:

### MoE batch-composition variance

Production judge is **DeepSeek-V4-Pro MoE** at **`--max-num-seqs 16`** on `alliance-pod` (`research/tapetum-llm-speedup/00-baseline.md`).

`MODELS.md:69–70`:

> **MoE routing.** Qwen3-30B-A3B is Mixture-of-Experts … Under concurrent load, batch composition affects which experts route. **Serializing requests via the semaphores removes this entirely.**

`MODELS.md:77–78`:

> **Hosted inference is best-effort reproducible, not bit-exact.** vLLM/SGLang-class servers … flip tokens because matmul/attention/RMSNorm kernels are not batch-invariant … Server-side fixes exist (vLLM `VLLM_BATCH_INVARIANT_LEVEL`, SGLang `--enable-deterministic-inference`); **Fireworks does not currently expose them.**

In-paper parallel bursts co-schedule heterogeneous prompts (full-doc monolith prefill, page-scoped escalation, unit check with full `candidate_md` each) on the same 16-slot pod, **increasing batch token-shape diversity** versus today's one-call-at-a-time per paper under cross-paper c=32.

Measured baseline: **≥25% verdict-flip rate** on identical reruns at paper-level c=32 (`packages/whisker/src/whisker/CLAUDE.md`, tapetum_llm advisory section; `research/llm-golden-verification-gap/personas/c13-determinism.md`).

Impact: parallel unit checks do not create prompt-order dependencies, but they **add concurrent load within a paper**, worsening MoE routing variance at decision boundaries (pass/review/fail, defect counts, `affected_count`).

### Prefix-cache interaction (secondary)

Shared `CONVERSION_CONTRACT` prefix is broken by per-call `guard_instruction(tag)` at system-prompt tail. Parallel within-paper multiplies simultaneous full-markdown prefills (`unit_judge.py:791–793`), competing for 16 KV blocks under cross-paper load. Single-paper latency win may be **< linear in W**; possible ITL inflation under contention (`20-in-paper-parallelist.md` MED finding).

## Fleet wall: why this lever does not reach 10 min

Total slot-seconds = call count × mean latency, independent of in-paper scheduling:

| Metric | Value |
|--------|-------|
| Papers / calls | 381 / ~2284 |
| Slots | 16 |
| Implied wall | ~2855 s (closes on measured 3003 s) |
| Cross-paper c | 32 (already overfills 16 slots, `cli.py:125–133`) |

In-paper parallelism changes **depth per paper**, not **total calls**. Expected cold-fleet saving: **~0 s** (± queueing noise). Critical path for a median 6-call paper drops from ~120 s serial to ~20–30 s in theory, but fleet throughput is slot-saturated.

For `--all-pages` / `--inspect` single-paper UX, parallel units matter (15 pages × ~20 s serial ≈ 300 s vs ceil(15/16) × ~20 s ≈ 40 s). That is a tail-latency win, not a 48→10 min fleet breakthrough.

## Whisker D11 exemption (what CLAUDE.md / MODELS.md say)

### Root `CLAUDE.md`

- **D11:** `dissect` at most one in-flight LLM request; framework defaults `_parallel_semaphore` and `_task_semaphore` at `Semaphore(1)`.
- **Permitted escape:** "New packages that opt into concurrent execution must do so through a **per-package mechanism** that leaves dissect on the serial path (per-context or per-call concurrency parameter; **never a global flip**)."

### `judge_task.py` (whisker-local mechanism)

```17:23:packages/whisker/src/whisker/tapetum_llm/judge_task.py
This module is the per-package concurrency mechanism that D11 sanctions
("per-context or per-call concurrency parameter; never a global flip"),
implemented on the whisker side so the pipeline package stays untouched.
```

Bypasses `pipeline.run_task`'s global `Semaphore(1)`. Actual bound: CLI paper-level `asyncio.Semaphore(concurrency)` (`cli.py:1193`), default c=32 cross-paper.

### `packages/whisker/src/whisker/CLAUDE.md`

- Deterministic whisker paths: serial.
- Advisory tapetum lane: cross-paper concurrency up to 32; **requests within one paper remain serial today**.
- Lane never gates; ≥25% flip rate tolerated architecturally.

### `research/cold-run-10min/00-baseline.md`

> Dissect D11 serial path must stay untouched; tapetum uses `judge_task.py` exemption.

**In-paper parallel is a whisker-local scheduling change only** — does not touch `pipeline.runner._parallel_semaphore` or dissect. D11 compliant if implemented inside `judge_pdf_extraction` / `run_unit_checks` with a per-paper fan-out cap, not a global pipeline flip.

## False-pass hypothesis

Parallel monolith + five unit checks on a borderline paper: MoE batch routes monolith to a "pass" expert composition under a fat heterogeneous burst while a serial rerun demotes to review; fusion cannot promote to deterministic pass, but advisory `suggested_verdict` clears a paper the operator treats as LLM-verified. Trigger: c=32 fleet + in-paper W=12 on `deepseek-v4-pro` without batch-invariant kernels.

(`20-in-paper-parallelist.md` false-pass hypothesis.)

## False-fail hypothesis

`--all-pages` fires page_count parallel unit checks; several hit `UNIT_CHECK_TIMEOUT_SECONDS = 120` under slot contention, land in `failed_unit_ids`, force `coverage_complete=false` → advisory review cap on an otherwise clean conversion. Serial c=1 within paper would succeed sequentially.

(`20-in-paper-parallelist.md` false-fail hypothesis; `unit_judge.py:433–437`, `pdf_judge.py:1040–1048`.)

## Cold-run 10 min fit

| Lever | Fleet wall impact | Quality risk |
|-------|-------------------|--------------|
| In-paper parallel (units + escalations + monolith/metadata wave) | ~0 s (slot accounting) | MoE variance ↑, timeout false-fail ↑ |
| Metadata short-circuit | ~1341 s (already ranked #1) | verdicts unchanged when stripped |
| APC / guard tag | ~180–360 s | low |
| Dual-pod shard | ~1.9× on remainder | infra |

In-paper parallel is **not a substitute** for call elimination (metadata short-circuit, deterministic metadata diff) or infra multiplier (dual-pod). Rank it for `--all-pages` UX only until A/B proves fleet-neutral quality.

## What would change my mind

Measured A/B on live 381-paper cold fleet:

- **(A)** current serial in-paper + c=32
- **(B)** max-parallel in-paper + c=32 (same ~2284 calls, same model)

Report: fleet wall within **±2%** AND defect-group recall / merged-verdict distribution within established MoE drift band (≤2 pp flip on papers whose merged verdict changed in prior baseline). Without that, reject for fleet; allow guarded `--all-pages` A/B only.

## Ship recommendation

| Option | One-line why |
|--------|--------------|
| **shippable now?** | **No** — MoE batch variance on an already ≥25%-flip advisory lane, plus zero expected cold-fleet wall savings, make uncontrolled in-paper fan-out negative EV. |
| **A/B only** | **Yes (selected)** — dependency-safe for single-paper/`--all-pages` latency; bounded whisker-local change; needs fleet A/B before default-on. |
| **reject** | Too strong — `--all-pages` tail latency (~4–6× single-paper) is real; reject as fleet lever, not as inspect UX experiment. |

**Final:** **A/B only** — parallel unit checks do not violate prompt dependencies, but MoE batch-composition variance and slot-neutral fleet accounting forbid shipping without a 381-paper quality A/B.
