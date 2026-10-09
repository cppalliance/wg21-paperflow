# Prompt template — paste to the planning LLM

Copy everything below the line into the planning agent.

---

You are writing an **architecture and execution plan** for cutting `whisker-tapetum-llm` cold full-fleet latency from ~48–50 min to a realistic target under a **single DeepSeek-V4-Pro pod** constraint.

## Read first (in order)

1. `research/cold-run-10min-1pod/PLANNING-HANDOFF.md` — entry point
2. `research/cold-run-10min-1pod/SYNTHESIS.md` — verdict
3. `research/cold-run-10min-1pod/planning/00-DECISION-MATRIX.md`
4. `research/cold-run-10min-1pod/planning/01-OPTIONS-ABC.md`
5. `research/cold-run-10min-1pod/planning/RISK-REGISTER.md`
6. `research/cold-run-10min-1pod/planning/OPEN-QUESTIONS.md`
7. `research/cold-run-10min-1pod/planning/TICKET-BACKLOG.md`
8. `research/cold-run-10min-1pod/FILE-MANIFEST.md` — then open any cited report

Optional depth: all `planning/ADR-*.md`, `CONFLICTS.md`, `ASSUMPTIONS.md`, `STACK-DIAGRAM.md`.

Prior dual-pod research in `research/cold-run-10min/` is **superseded for execution** (twin forbidden). Use only as historical context.

## Hard constraints (do not violate)

- No second V4-Pro / twin pod
- `--max-num-seqs` stays 16 on MoE (32 regresses +57%)
- Client concurrency c≤32
- Do not skip monolith as the 10-min path
- Do not bank MTP / Flash / dense savings without infra+A/B
- As of 2026-07-24 probe: **all dense Alliance pods return HTTP 404**; only `alliance-pod` is up

## Physics you must accept

- MoE-only quality floor ≈ **23 min** (MODERATE); AGGRESSIVE realistic ≈ **12–15 min** / ~680 s central
- ≤10 min requires heterogeneous dense offload + payload scoping + parity, currently **infra-blocked**
- Without dense restart: honest SLA **~15–20 min**

## Deliverable

Write a plan document (markdown) with:

1. Chosen Option A / B / C (or sequenced A→B)
2. Explicit infra ask (or SLA reset language)
3. Phased tickets with dependencies and quality gates
4. Non-goals
5. Measurement protocol (shared-pod noise)
6. Citations to report IDs (`12`, `17`, `26`, …)

Do not invent live dense capacity. Do not propose S=32 or a twin pod.
