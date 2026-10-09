# 00 — START HERE (planner index)

**Audience:** downstream planning agent  
**Date:** 2026-07-24  
**Corpus:** `research/cold-run-10min-1pod/`

This directory is the architecture decision pack. It is **not** the sole entry point for the program.

## Parents (read first)

1. [`../PLANNING-HANDOFF.md`](../PLANNING-HANDOFF.md) — constraints, options A/B/C, phase sketch, reject ledger  
2. [`../PROMPT-FOR-PLANNER.md`](../PROMPT-FOR-PLANNER.md) — paste-ready brief for the planning LLM  

Then: [`../SYNTHESIS.md`](../SYNTHESIS.md) for the executive verdict, then the artifacts below. Do not re-forage the dual-pod tree (`research/cold-run-10min/`) as executable; twin V4-Pro is forbidden.

## LIVE BLOCKER: dense pods 404

As of the 2026-07-24 probe ([`../26-dense-pod-liveness.md`](../26-dense-pod-liveness.md)):

- All four dense `SERVICES.toml` endpoints (`h200-qwen3-32b`, `b300-qwen36-27b`, `b200x2-gemma4`, `b200-r1`) return **HTTP 404**.
- Only `alliance-pod` (DeepSeek-V4-Pro) is up.
- Heterogeneous Option B / Package C is **infra-blocked**. Policy permission alone does not unblock ≤10 min.
- Without a dense restart, honest SLA is **~15–20 min** (Option A + Option C language). Do not invent live dense capacity.

## Five human decisions (required before a plan is executable)

A plan that picks tickets without these answers is speculative, not executable. The human / Alliance ops must answer:

1. **Dense restart:** Will Alliance restart at least `h200-qwen3-32b`, and by when? (yes / no / dated commit)
2. **SLA:** Keep the public goal at ≤10 min (requires live dense + Option B), or reset to ~15–20 min?
3. **Program posture if dense stays down:** End the ≤10 min program explicitly (Option C), or ship MoE-only levers with **no** 10-min claim (Option A only)?
4. **Dense production authority:** May tapetum use Alliance dense pods as a production unit/metadata lane (with MoE fallback for oversize), not inventory-only?
5. **Measurement window:** Will ops grant a quiet / occupancy-matched window on `alliance-pod` (and dense, if live), and who funds/schedules the ~0.8–1.2 h quality-gate wall?

Detail and Option-mapping: [`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md). SLA fork mechanics: [`ADR-018-sla-fork.md`](ADR-018-sla-fork.md).

## Planning artifact categories (globs)

Paths relative to this `planning/` directory. Some globs may be empty until the swarm finishes landing.

| Category | Glob / path | Role |
|----------|-------------|------|
| This index | `00-START-HERE.md` | Master planner index |
| Decision matrix | `00-DECISION-MATRIX.md` | Master yes / no / defer / blocked table |
| Options compare | `01-OPTIONS-ABC.md` | Options A / B / C side-by-side |
| ADRs | `ADR-*.md` | One architecture decision per file |
| Research cards | `cards/*-CARD.md` | One-page distill per numbered report |
| Card scratch / web notes | `cards/*.md` | Supporting card notes (may include non-`CARD` names) |
| Decision packets | `packets/D*.md` | Decision packets (if present) |
| Claim checks | `checks/CHECK-*.md` | Claim confirmation slips (if present) |
| Micro claims | `micro/M*.md` | Micro claim cards (if present) |
| Risks | `RISK-REGISTER.md` | Risks + mitigations |
| Open questions | `OPEN-QUESTIONS.md` | Human / ops-only questions |
| Tickets | `TICKET-BACKLOG.md` | Suggested implementation tickets |
| Planner FAQ | `PLANNER-FAQ.md` | FAQ for planners (if present) |
| Non-goals | `NON-GOALS.md` | Explicit out-of-scope |
| Conflicts | `CONFLICTS.md` | Cross-report contradictions + resolution (if present) |
| Assumptions | `ASSUMPTIONS.md` | Load-bearing assumptions + falsifiers (if present) |
| Quality protocol | `QUALITY-PROTOCOL.md` | Condensed gate from report `19` |
| Infra ask | `INFRA-ASK.md` | Exact ask to Alliance ops |
| Measurement | `MEASUREMENT-PROTOCOL.md` | Honest cold A/B under shared-pod noise |
| Stack diagram | `STACK-DIAGRAM.md` | Call-routing / cascade diagram |
| Cross-corpus index | `CROSS-CORPUS-INDEX.md` | Links into prior research trees |
| Prior distill | `PRIOR-CORPUS-DISTILL.md` | Distill of superseded / prior corpora |
| Dual-pod delta | `DELTA-FROM-DUALPOD.md` | What dual-pod plans do **not** mean here |
| Lever scorecard | `LEVER-SCORECARD.md` | Lever ranking / EV notes |
| Code anchors | `CODE-ANCHORS.md` | Code touchpoints for tickets |
| Exec brief (DE) | `EXEC-BRIEF-DE.md` | German executive brief for ops / stakeholders |
| Pack README | `README.md` | Short directory role table |

Parent corpus catalog (numbered reports, `05*`, synthesis): [`../FILE-MANIFEST.md`](../FILE-MANIFEST.md).

## Swarm landing warning

This pack is filled by a multi-agent swarm. **Some files may still be landing** while you read.

- Re-list this directory (and `cards/`, `packets/`, `checks/`, `micro/` if present) before you finalize the plan.
- Prefer fresh globs over any cached file list from an earlier turn.
- Missing optional globs (`packets/`, `checks/`, `micro/`, `CONFLICTS.md`, `ASSUMPTIONS.md`, `PLANNER-FAQ.md`) are expected until writers finish; do not invent their contents.
- Parents and LIVE BLOCKER above remain authoritative even if individual ADRs are still arriving.

## Suggested read order inside this pack

1. `00-DECISION-MATRIX.md`  
2. `01-OPTIONS-ABC.md`  
3. `OPEN-QUESTIONS.md` + `INFRA-ASK.md` (human blockers)  
4. `RISK-REGISTER.md` + `TICKET-BACKLOG.md`  
5. `ADR-*.md` as needed for chosen Option  
6. `QUALITY-PROTOCOL.md` + `MEASUREMENT-PROTOCOL.md`  
7. `NON-GOALS.md` + `STACK-DIAGRAM.md`  

## Deliverable reminder

Produce one plan document with: chosen Option A / B / C (or sequenced A→B / A+C), explicit infra ask or SLA-reset language, phased tickets with dependencies and quality gates, non-goals, measurement protocol, and citations to report IDs (`12`, `17`, `26`, …). Do not propose a second V4-Pro or MoE `--max-num-seqs 32`.
