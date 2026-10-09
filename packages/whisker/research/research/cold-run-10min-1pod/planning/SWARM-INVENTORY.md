# SWARM INVENTORY — bundling pack for planners

**Audience:** planning LLM that must know what was commissioned vs what may still be landing  
**Date:** 2026-07-24  
**Swarm:** Grok multi-agent fill of `research/cold-run-10min-1pod/planning/`  
**Rule:** Prefer a fresh directory listing over this snapshot. Paths relative to `planning/` unless noted.

This file lists what the bundling swarm was **asked to produce**. Status column is a snapshot at write time; re-glob before treating a gap as final.

| Status | Meaning |
|--------|---------|
| **landed** | File present at inventory write |
| **partial** | Category asked; some IDs still missing |
| **landing** | Explicitly still expected / this writer’s job |
| **extra** | Present on disk but not in the named Task prompts below |

---

## 1. Matrices and option compare

| Asked file | Status |
|------------|--------|
| `00-DECISION-MATRIX.md` | landed |
| `01-OPTIONS-ABC.md` | landed |

---

## 2. ADRs 001–030

| ADR | Filename | Status |
|-----|----------|--------|
| 001 | `ADR-001-no-twin-pod.md` | landed |
| 002 | `ADR-002-max-num-seqs-16.md` | landed |
| 003 | `ADR-003-heterogeneous-dense-cascade.md` | landed |
| 004 | `ADR-004-payload-scoping.md` | landed |
| 005 | `ADR-005-dense-primary-qwen3-32b.md` | landed |
| 006 | `ADR-006-deterministic-metadata.md` | landed |
| 007 | `ADR-007-verdict-first-schema.md` | landed |
| 008 | `ADR-008-router-dynamic-quota.md` | landed |
| 009 | `ADR-009-keep-monolith.md` | landed |
| 010 | `ADR-010-no-default-det-skip.md` | landed |
| 011 | `ADR-011-server-ops-tier1.md` | landed |
| 012 | `ADR-012-reject-guided-grammar.md` | landed |
| 013 | `ADR-013-reject-batch-invariant.md` | landed |
| 014 | `ADR-014-mtp-ab-only.md` | landed |
| 015 | `ADR-015-nonthink-unit-checks.md` | landed |
| 016 | `ADR-016-flash-requires-deploy.md` | landed |
| 017 | `ADR-017-ship-v11-baseline.md` | landed |
| 018 | `ADR-018-sla-fork.md` | landed |
| 019 | `ADR-019-keep-schema-in-prompt.md` | landed |
| 020 | `ADR-020-escalate-band-15pct.md` | landed |
| 021 | `ADR-021-html-first-det-metadata.md` | landed |
| 022 | `ADR-022-call-class-fingerprint-later.md` | landed |
| 023 | `ADR-023-no-pd-disagg.md` | landed |
| 024 | `ADR-024-no-gemma-primary-judge.md` | landed |
| 025 | `ADR-025-shared-pod-measurement.md` | landed |
| 026 | `ADR-026-ideal-verify-keep.md` | landed |
| 027 | `ADR-027-reject-sglang-migrate.md` | landed |
| 028 | `ADR-028-reject-http-microtuning.md` | landed |
| 029 | `ADR-029-oversize-unit-moe-fallback.md` | landed |
| 030 | `ADR-030-fail-closed-on-dense-down.md` | landed |

---

## 3. Planner tool docs (wave 1)

| Asked file | Status |
|------------|--------|
| `RISK-REGISTER.md` | landed |
| `OPEN-QUESTIONS.md` | landed |
| `TICKET-BACKLOG.md` | landed |
| `CROSS-CORPUS-INDEX.md` | landed |
| `CONFLICTS.md` | landed |
| `NON-GOALS.md` | landed |
| `QUALITY-PROTOCOL.md` | landed |
| `INFRA-ASK.md` | landed |
| `MEASUREMENT-PROTOCOL.md` | landed |
| `STACK-DIAGRAM.md` | landed |
| `ASSUMPTIONS.md` | landed |
| `README.md` (pack table) | landed |

---

## 4. Cards (`cards/*-CARD.md`)

One-page distill per research report. Asked sources:

| Batch | Sources | Status |
|-------|---------|--------|
| Core 00–20 | `00`, `10`–`20` → `cards/<basename>-CARD.md` | landed |
| Explored 21–29 | `21`–`29` → `*-CARD.md` | landed |
| Meta cards | `SYNTHESIS-CARD.md`, `PLANNING-HANDOFF-CARD.md` | landed |
| Web 05–05m | `05`, `05a`–`05m` → `*-CARD.md` | landed |
| Web 05n–05z | `05n`–`05z` → `*-CARD.md` | landed (incl. `05y`, `05z`) |

Also: early writers may have dropped non-`*-CARD.md` names under `cards/`; prefer `*-CARD.md` as canonical.

---

## 5. Decision packets (`packets/D*.md`)

### Batch 1 (D01–D10) — asked explicitly

| File | Topic | Status |
|------|-------|--------|
| `D01-sla-target.md` | SLA | landed |
| `D02-infra-dense-restart.md` | Dense restart | landed |
| `D03-ship-moe-package.md` | MoE package | landed |
| `D04-heterogeneous-when.md` | When Option B | landed |
| `D05-quality-bar.md` | Quality bar | landed |
| `D06-server-flags.md` | Server flags | landed |
| `D07-client-think-json.md` | Client think/JSON | landed |
| `D08-measurement.md` | Measurement | landed |
| `D09-non-goals-lock.md` | Non-goals lock | landed |
| `D10-distill-defer.md` | Distill defer | landed |

### Batch 2 (D11–D30) — one topic each

Asked topics: router combo_safe, dynamic unit quota, Non-think probe, DeepEP enable, async-sched audit, ngram defer, call-class fingerprint defer, HTML-first detmeta, PDF detmeta fleet, escalate 15%, oversize fallback, presence index, H2 window, Qwen27 reserve, R1 avoid, BI reject, guided reject, P/D reject, skip monolith reject, distill trigger.

| IDs | Status at snapshot |
|-----|--------------------|
| `D11`–`D24` | landed |
| `D25`–`D30` | landed — `D25-r1-avoid`, `D26-bi-reject`, `D27-guided-reject`, `D28-pd-reject`, `D29-skip-monolith-reject`, `D30-distill-trigger` |

---

## 6. Claim checks (`checks/CHECK-*.md`)

Asked twelve slips:

| File | Claim | Status |
|------|-------|--------|
| `CHECK-front-end-948s.md` | 758 calls → 948 s @ S=16 | landed |
| `CHECK-dense-404.md` | All 4 dense 404 | landed |
| `CHECK-slots32-regress.md` | S=32 +57% | landed |
| `CHECK-v11-shortcircuit.md` | ~−1059 to −1341 s | landed |
| `CHECK-hetero-511.md` | ~511 s MoE-bound | landed |
| `CHECK-moe-floor-23min.md` | ~1366 s MODERATE | landed |
| `CHECK-mtp-dont-bank.md` | MTP do not bank | landed |
| `CHECK-flash-1.7x.md` | Flash ~1.7× | landed |
| `CHECK-deepep-12pct.md` | DeepEP ~12% | landed |
| `CHECK-ideal-60s.md` | Ideal-verify ~60–90 s | landed |
| `CHECK-html-share.md` | HTML 52.8% | landed |
| `CHECK-shared-noise-high.md` | Shared-pod noise HIGH | landed |

---

## 7. Micro claims (`micro/M01.md` … `M40.md`)

Asked: 40 files, 5–8 lines each (CLAIM / EVIDENCE / IMPLICATION / STATUS).

| Range | Status |
|-------|--------|
| `M01`–`M40` | landed |

---

## 8. Scorecards, anchors, prior distill (wave 2)

| Asked file | Status |
|------------|--------|
| `LEVER-SCORECARD.md` | landed |
| `DEPENDENCY-GRAPH.md` | landed |
| `WALL-SCENARIOS.md` | landed |
| `CODE-ANCHORS.md` | landed |
| `GLOSSARY.md` | landed |
| `PRIOR-CORPUS-DISTILL.md` | landed |
| `DELTA-FROM-DUALPOD.md` | landed |
| `PLANNER-FAQ.md` (≥40 Q&A) | landed |

---

## 9. Exec briefs and integration (wave 3–4)

| Asked file | Status |
|------------|--------|
| `EXEC-BRIEF-DE.md` | landed |
| `EXEC-BRIEF-EN.md` | landed |
| `FALSIFIERS.md` | landed |
| `SUCCESS-METRICS.md` | landed |
| `00-START-HERE.md` | landed |
| `READING-ORDER.md` | landed (this track guide) |
| `SWARM-INVENTORY.md` | landed (this file) |

---

## 10. How a planner should use gaps

1. Re-list `planning/`, `cards/`, `packets/`, `checks/`, `micro/` before finalizing.  
2. Missing **optional** depth (late packets, two web cards) does **not** block Option A/C planning if parents + matrix + ADR-001/002/003/018 + `INFRA-ASK` are present.  
3. Missing **`00-DECISION-MATRIX.md`** or **`01-OPTIONS-ABC.md`** or core ADRs **does** block an executable plan: wait or fall back to `../PLANNING-HANDOFF.md` + `../SYNTHESIS.md` only.  
4. Never invent dense liveness, wall seconds, or ADR status. Cite report IDs.  
5. Parents remain authoritative: `../PLANNING-HANDOFF.md`, `../PROMPT-FOR-PLANNER.md`, `../SYNTHESIS.md`.

---

## 11. Swarm wave map (commission order)

| Wave | Commissioned |
|------|----------------|
| 1 | Matrices, Options ABC, ADR-001–020, risks/open Qs/tickets, cross-corpus/conflicts, non-goals/quality/infra/measurement/stack/assumptions |
| 2 | Cards (00–29 + SYNTHESIS/HANDOFF + 05*), lever scorecard, dependency graph, wall scenarios, code anchors, glossary, prior distill, dual-pod delta, planner FAQ, packets D01–D10, ADR-021–030 |
| 3 | Checks CHECK-*, packets D11–D30, exec briefs DE/EN, reading order + this inventory, falsifiers, success metrics |
| 4 | Micro M01–M40, `00-START-HERE.md` |

Corpus research reports under `../` (numbered + `05*`) were produced **before** this bundling swarm; they are inputs, not swarm outputs.
