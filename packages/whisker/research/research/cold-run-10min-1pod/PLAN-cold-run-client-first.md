# PLAN — Cold-run Phase 1: Client-only (no pod operator)

**Date:** 2026-07-25
**Supersedes:** `PLAN.md` (old A-to-B plan; now a pointer to this file)
**Planner:** Fable 5 (PlannerExecutor orchestration)
**Inputs:** `PLANNING-HANDOFF.md`, `SYNTHESIS.md`, `planning/CODE-ANCHORS.md`, `planning/TICKET-BACKLOG.md`, `planning/00-DECISION-MATRIX.md`
**Execute-source-of-truth:** `C:\Users\sabo2\.cursor\plans\cold-run_phase_1_client-only_32352831.plan.md`

---

## 1. Goal

Cut `whisker-tapetum-llm` cold fleet (381 papers) wall time from measured ~48-50 min (v10) down to ~12-15 min using **only client-side code changes** on the existing `alliance-pod` (DeepSeek-V4-Pro, S_eff=16). No pod-operator interaction, no dense pods, no infra changes.

Phase 1 is the MoE-only package (Option A from `PLANNING-HANDOFF.md`). If the result is not good enough, Escalation Plan 2 (pod operator involvement, Option B heterogeneous cascade) fires only on explicit user approval.

**Honest SLA:** ~15-20 min cold after Phase 1. MoE-only cannot reach <=10 min at quality (`17`).

## 2. Orchestration (PlannerExecutor, verbindlich)

| Role | Model | Responsibility |
|------|-------|----------------|
| **Planner** | Fable 5 (this chat) | Decides sequence, reviews every gate, authors probe/debug scripts, re-dispatches on blockers |
| **Executor** | Sonnet 5 (`Task generalPurpose, model=claude-sonnet-5-thinking-high`) | Implements code + tests: P1-SHIP-V11, P1-DET-META, P1-VERDICT, P1-ROUTER, P1-PAYLOAD-PREP |
| **Workhorse** | Composer 2.5 (`Task, model=composer-2.5-fast`) | Cold runs, replays, holdouts, probes, `uv run pytest` |

Escalation rule: Executor/Workhorse blockers go immediately back to Planner; no guessing in the cheap tier past a failure.

## 3. Phase 1 tickets (sequence, gates, owners)

### P1-MEASURE: Cold-fleet remeasure on v11

| Field | Value |
|-------|-------|
| **Owner** | Workhorse (Composer, CLI) |
| **Command** | `uv run --package whisker whisker-tapetum-llm --force --trace` |
| **Protocol** | Off-hours, `$env:PYTHONIOENCODING = "utf-8"`, `/v1/metrics` occupancy note (`28`) |
| **Gate** | Band ~21-25 min confirmed (`10`, `11`); if <=700 s without dense, reopen accounting |
| **Expectation** | Truth baseline; v11 short-circuit already cuts ~1059-1341 s from v10 |
| **Evidence** | `00`, `10`, `11`, `28` |

### P1-SHIP-V11: v11 finalize + tests

| Field | Value |
|-------|-------|
| **Owner** | Executor (Sonnet) |
| **What** | Finalize v11 as commit candidate: short-circuit (PDF `pdf_judge.py:742-759` + HTML `adjudicate.py:521-531`), LJF (`cli.py:1030-1038`), timeouts (`constants.py:245`), tombstones (`cli.py:373-378`). Close or explicitly defer: text-lane HMAC `guard_tag` (`cli.py:467-479`), remaining prompt reorder |
| **Gate** | Tests green (`uv run --package whisker pytest`); release notes state in/deferred |
| **Constraint** | Do not overwrite uncommitted `_LANE_VERSION = 11`. Commit only on user approval |
| **Evidence** | `10` levers 1-8, `21` (reject skip-monolith) |

### P1-DET-META: Deterministic metadata/outline

| Field | Value |
|-------|-------|
| **Owner** | Executor (Sonnet) implements + tests; Workhorse runs 381-sidecar replay |
| **What** | Replace `run_metadata_outline_check` (`unit_judge.py:231-273`) with `compare_metadata_outline()` (pure function, no LLM). Wire into `pdf_judge.py:702` + `adjudicate.py:512`. Reuse `source_router.py:286-312`, `html_outline.py:128-147`, `gates.py:34-75`. Shadow via `TAPETUM_METADATA_SHADOW=1` |
| **Staging** | HTML-first (~-251 s), then fleet (~-471 s) |
| **Gate** | <=5% metadata-verdict drift AND zero fused-verdict changes on 381-sidecar replay (`13`) |
| **Evidence** | `13`, `22`, `10` |

### P1-VERDICT: UnitCheckClear bifurcation

| Field | Value |
|-------|-------|
| **Owner** | Executor + tests; Workhorse holdout run |
| **What** | Add `UnitCheckClear` (pass micro-schema, `max_tokens=128`) and `UnitCheckDefects` (768) in `models.py:298-320` vicinity. Two-stage routing in `_check_one_unit` (`unit_judge.py:770-809`). Enum-harden `DefectFinding.defect_type` (`models.py:231-259`) |
| **Gate** | 48-anchor holdout >=95% verdict stability (`15`) |
| **Evidence** | `15`, `05n` |

### P1-ROUTER: Dynamic unit quota + combo_safe

| Field | Value |
|-------|-------|
| **Owner** | Executor + tests; Workhorse holdout |
| **What** | Dynamic `MAX_UNIT_CHECKS` (base 3, ceiling 7) + `combo_safe` tightening in `_select_units_with_quotas` (`unit_judge.py:175+`), `constants.py:223` |
| **Gate** | 3/381 cap-driver papers + 16/381 flip-set: zero regression (`14`) |
| **Evidence** | `14`, `10`, `19` |

### P1-NONTHINK: Thinking probe + A/B

| Field | Value |
|-------|-------|
| **Owner** | Planner writes probe script; Workhorse executes; Executor builds flag if A/B is green |
| **What** | Probe whether `alliance-pod` has thinking enabled on unit checks. If yes: A/B `chat_template_kwargs: {thinking: false}` on unit checks only |
| **Forbidden** | Never `reasoning_effort="low"` (maps to High on DSV4). Never `thinking.enabled` + `json_object` (`05y`) |
| **Gate** | Unit A/B within flip noise |
| **Evidence** | `05a`, `05c`, `05q`, `05y` |

### P1-FINAL-MEASURE: Instrumented cold run

| Field | Value |
|-------|-------|
| **Owner** | Workhorse |
| **What** | Instrumented cold fleet after full Phase 1 stack. Quiet window, double-A for noise floor (`28`, `19`) |
| **Gate** | Measurement protocol honored; result is the Phase 1 number |
| **Evidence** | `28`, `19` |

### P1-PAYLOAD-PREP (optional, last): Payload scoping enabler

| Field | Value |
|-------|-------|
| **Owner** | Executor + tests |
| **What** | H2 +/-1 neighbor window + presence index (~10-12k tokens). Oversize -> MoE fallback (~8/381). New `payload_scope.py`: `build_unit_window()`, `build_presence_index()`. Constants `UNIT_SCOPE_*` in `constants.py` |
| **Gate** | Holdout without recall loss |
| **Value** | 0 s now; enables dense S=32-48 for Plan 2 |
| **Evidence** | `23`, `12` |

## 4. "Gut genug?" gate

After P1-FINAL-MEASURE, user decides:

- **Cold <=~900 s quiet-window**: Phase 1 success, publish SLA "~15 min", done.
- **Not good enough / <=10 min desired**: trigger Escalation Plan 2 (pod operator involvement).

## 5. Escalation Plan 2 (not executed without user OK)

Documented for completeness; blocked until user triggers:

1. Send `planning/INFRA-ASK.md` to Alliance ops: restart `h200-qwen3-32b`, explicitly no twin
2. Server Tier-1 flags on `alliance-pod` (MBT 16384, decode CUDA graphs, APC, DeepEP-LL ~10-15%; MTP k=1 A/B only)
3. Cascade router: units+metadata -> dense (~1879 calls), monolith/escalations -> MoE (~428); escalate <=15%; fail-closed on dense-404 (ADR-030)
4. Quality gate `19` (~0.8-1.2 h, fail-closed); 10-min claim only at instrumented B <=620 s
5. 14-day SLA fork (ADR-018) if operator does not deliver

Expected Plan 2 wall: **~511 s MoE-bound** (`12`, `20`).

## 6. Hard constraints (non-negotiable)

- Twin V4-Pro: **forbidden** (`00`)
- `--max-num-seqs`: stays **16** on MoE (+57% wall at 32) (`00`, `16`)
- Client `c>32`: **forbidden** (RunPod 524) (`00`)
- Skip monolith: **no** (`21`)
- Bank MTP: **A/B only, do not bank** (`05j`)
- Quality: fused-verdict parity, fail closed (`19`, CLAUDE.md)
- `_LANE_VERSION` bump on any lane-semantics change
- D6/D10 structured-output discipline (CLAUDE.md)
- Measurements off-hours with `/metrics` occupancy (`28`)

## 7. Physics reminder

```
wall = (N_rem x L_eff) / S_eff + T + C - L_abs    # single MoE queue
```

- `S_eff = 16` always for this program
- Front-end alone (381+377 calls): **948 s** (`17`) -- already >600 s before units
- MoE-only AGGRESSIVE realistic: **~715-910 s (~12-15 min)** (`18`)
- <=10 min impossible on MoE alone at quality (`17`)

---

*Evidence chain: `FILE-MANIFEST.md`. Every number traces to a report ID in this directory.*
