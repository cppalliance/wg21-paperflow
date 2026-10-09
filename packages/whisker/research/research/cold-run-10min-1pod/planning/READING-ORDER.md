# READING ORDER — cold-run ≤10 min (1 pod)

**Audience:** planning LLM / human architect  
**Date:** 2026-07-24  
**Base:** paths relative to `research/cold-run-10min-1pod/` unless noted  
**Live blocker:** dense pods HTTP 404 (`26-dense-pod-liveness.md`); do not invent capacity

Pick one track. Do not re-forage `research/cold-run-10min/` as executable (twin forbidden).

If a listed `planning/` file is missing, re-list the directory: the bundling swarm may still be landing. See [`SWARM-INVENTORY.md`](SWARM-INVENTORY.md).

---

## Track Fast (≈30 min)

Goal: enough to choose Option A / B / C, name the infra ask, and draft phased tickets without rediscovering physics.

1. `planning/00-START-HERE.md`
2. `PLANNING-HANDOFF.md`
3. `SYNTHESIS.md`
4. `planning/00-DECISION-MATRIX.md`
5. `planning/01-OPTIONS-ABC.md`
6. `planning/EXEC-BRIEF-EN.md` (or `EXEC-BRIEF-DE.md` if German)
7. `planning/OPEN-QUESTIONS.md`
8. `planning/RISK-REGISTER.md`
9. `planning/INFRA-ASK.md`
10. `planning/TICKET-BACKLOG.md`
11. `planning/ADR-001-no-twin-pod.md`
12. `planning/ADR-002-max-num-seqs-16.md`
13. `planning/ADR-003-heterogeneous-dense-cascade.md`
14. `planning/ADR-018-sla-fork.md`
15. `planning/NON-GOALS.md`
16. `FILE-MANIFEST.md` (skim; open only what tickets cite)

Stop. Write the plan. Open deeper reports only when a ticket or ADR cites them.

---

## Track Architect (≈2 h)

Goal: defend the Option choice, quality gates, server/client rejects, and dependency order. Includes Track Fast, then:

### A. Protocols and shape

17. `planning/QUALITY-PROTOCOL.md`
18. `planning/MEASUREMENT-PROTOCOL.md`
19. `planning/ASSUMPTIONS.md`
20. `planning/CONFLICTS.md`
21. `planning/STACK-DIAGRAM.md`
22. `planning/DEPENDENCY-GRAPH.md`
23. `planning/LEVER-SCORECARD.md`
24. `planning/WALL-SCENARIOS.md`
25. `planning/FALSIFIERS.md`
26. `planning/SUCCESS-METRICS.md`
27. `planning/GLOSSARY.md` (as needed)
28. `planning/CODE-ANCHORS.md`
29. `planning/CROSS-CORPUS-INDEX.md`
30. `planning/PRIOR-CORPUS-DISTILL.md`
31. `planning/DELTA-FROM-DUALPOD.md`

### B. All ADRs (001–030), in number order

32. `planning/ADR-001-no-twin-pod.md` … through … `planning/ADR-030-fail-closed-on-dense-down.md`

(If already read 001–003 and 018 in Track Fast, skip duplicates.)

### C. Physics and design reports (sources, not only cards)

33. `00-baseline.md`
34. `10-impl-status-1pod.md`
35. `11-wall-arithmetic-1pod.md`
36. `17-physics-floor-skeptic.md`
37. `18-packages-1pod.md`
38. `12-dense-offload-architecture.md`
39. `20-heterogeneous-wall.md`
40. `23-payload-scope-dense.md`
41. `26-dense-pod-liveness.md`
42. `13-deterministic-metadata.md`
43. `15-verdict-first-design.md`
44. `14-router-quota-1pod.md`
45. `16-server-ops-1pod.md`
46. `19-quality-gate-1pod.md`
47. `28-shared-pod-noise.md`
48. `21-skip-monolith-revisit.md`
49. `22-html-vs-pdf-mix.md`
50. `24-det-skip-llm.md`
51. `25-call-class-fingerprint.md`
52. `27-dualpod-dependency-rewrite.md`
53. `29-ideal-verify-fleet-cost.md`

### D. Decision packets (batch 1 + critical wave-3)

54. `planning/packets/D01-sla-target.md` … `D10-distill-defer.md`
55. Then any landed `planning/packets/D11-*.md` … `D30-*.md` (see inventory)

### E. Claim checks (spot-verify load-bearing numbers)

56. `planning/checks/CHECK-*.md` (all twelve)

### F. Planner FAQ (search, do not read cover-to-cover)

57. `planning/PLANNER-FAQ.md`

### G. Optional cards instead of re-reading a source

Prefer `planning/cards/<basename>-CARD.md` when you already know the report id and only need the punch line. Full source wins on conflict.

Web forage (`05*`) in this track: open only when an ADR / packet cites it (`05j` MTP, `05t` DeepEP, `05q`/`05a` Non-think, `05b`/`05z` Flash, `05v` BI, `05k` P/D, `05f` dense judge, `05l`/`05p` cascade).

---

## Track Full corpus

Goal: exhaustive pass. Follow [`FILE-MANIFEST.md`](../FILE-MANIFEST.md) section order exactly.

### Entry points

1. `PLANNING-HANDOFF.md`
2. `PROMPT-FOR-PLANNER.md`
3. `SYNTHESIS.md`
4. Entire `planning/` pack (swarm): start at `planning/00-START-HERE.md`, then matrices, ADRs, cards, packets, checks, micro, then remaining planner tools listed in the manifest / `planning/README.md`
5. `FILE-MANIFEST.md` (this catalog; keep open as checklist)

### Baseline & status

6. `00-baseline.md`
7. `10-impl-status-1pod.md`
8. `26-dense-pod-liveness.md`
9. `28-shared-pod-noise.md`

### Arithmetic & physics

10. `11-wall-arithmetic-1pod.md`
11. `17-physics-floor-skeptic.md`
12. `18-packages-1pod.md`
13. `20-heterogeneous-wall.md`

### Architecture designs

14. `12-dense-offload-architecture.md`
15. `13-deterministic-metadata.md`
16. `14-router-quota-1pod.md`
17. `15-verdict-first-design.md`
18. `16-server-ops-1pod.md`
19. `19-quality-gate-1pod.md`
20. `23-payload-scope-dense.md`
21. `27-dualpod-dependency-rewrite.md`

### Explored / rejected / small levers

22. `21-skip-monolith-revisit.md`
23. `22-html-vs-pdf-mix.md`
24. `24-det-skip-llm.md`
25. `25-call-class-fingerprint.md`
26. `29-ideal-verify-fleet-cost.md`

### Web / DeepSeek / literature (`05*`)

27. `05-web-think-off-official.md`
28. `05a-web-nonthink.md`
29. `05b-web-flash-vs-pro.md`
30. `05c-web-reasoning-effort.md`
31. `05d-web-single-node-serving.md`
32. `05e-web-single-endpoint-judge.md`
33. `05f-web-dense-judge-lit.md`
34. `05g-web-slmjury.md`
35. `05h-web-eval-harness-1backend.md`
36. `05i-web-community-workarounds.md`
37. `05j-web-mtp-short-json.md`
38. `05k-web-pd-disagg.md`
39. `05l-web-cascade-papers.md`
40. `05m-web-short-osl-moe.md`
41. `05n-web-v4-structured.md`
42. `05o-web-localllama.md`
43. `05p-web-frugalgpt.md`
44. `05q-web-official-think-off.md`
45. `05r-web-extractor-judge.md`
46. `05s-web-async-sched.md`
47. `05t-web-dbo-deepep.md`
48. `05u-web-arena-judges.md`
49. `05v-web-batch-invariant.md`
50. `05w-web-ngram-spec.md`
51. `05x-web-v4-paper-efficiency.md`
52. `05y-web-cn-forums.md`
53. `05z-web-hosted-latency.md`

### Meta / superseded

54. `_index.md`
55. `SYNTHESIS-DRAFT.md` (superseded by `SYNTHESIS.md`; read only if auditing history)

### Related corpora (outside this dir; context only)

56. `research/cold-run-10min/` — dual-pod era; superseded for execution  
57. `research/tapetum-llm-speedup/` — original speedup swarm  
58. `research/tapetum-llm-throughput/` — call census / sidecars  
59. `research/slots-32-regression/` — why S=32 is forbidden  
60. `research/concurrency-381/` — why c>32 fails  
61. `packages/whisker/research/deepseek-v4-pro/` — Whisker-local V4 notes  

Within `planning/` on the full track, after entry points, prefer this subcategory order: matrices → ADRs 001–030 → cards → packets D01–D30 → checks → micro M01–M40 → remaining root tools (`RISK-REGISTER`, `TICKET-BACKLOG`, `PLANNER-FAQ`, scorecards, briefs, etc.).

---

## After reading

Deliverable expectations: [`PROMPT-FOR-PLANNER.md`](../PROMPT-FOR-PLANNER.md) and [`PLANNING-HANDOFF.md`](../PLANNING-HANDOFF.md) §12.  
Do not propose a second V4-Pro or `--max-num-seqs 32`. Cite report IDs for major claims.
