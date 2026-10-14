# planning/ — Architecture decision pack

Produced for a downstream planning LLM. Fill-in via Grok swarm 2026-07-24.

| File | Role |
|------|------|
| `00-DECISION-MATRIX.md` | Master yes/no/defer table |
| `01-OPTIONS-ABC.md` | Options A/B/C compared |
| `LEVER-SCORECARD.md` | Every lever: save / risk / infra / ship order / bankable for 10min |
| `DEPENDENCY-GRAPH.md` | Mermaid P0→P8 + dense infra gate |
| `WALL-SCENARIOS.md` | Scenario table: N, L, S, wall, assumptions, status |
| `CODE-ANCHORS.md` | Symbol/file:line → lever change map |
| `GLOSSARY.md` | Shared terms (S_eff, twin, packages, …) |
| `ADR-*.md` | One decision per card |
| `RISK-REGISTER.md` | Risks + mitigations |
| `OPEN-QUESTIONS.md` | Questions only the human/ops can answer |
| `TICKET-BACKLOG.md` | Suggested implementation tickets |
| `CROSS-CORPUS-INDEX.md` | Links into prior research trees |
| `CONFLICTS.md` | Contradictions across reports + resolution |
| `NON-GOALS.md` | Explicit non-goals for the plan |
| `QUALITY-PROTOCOL.md` | Condensed gate from report 19 |
| `INFRA-ASK.md` | Exact ask to Alliance ops |
| `MEASUREMENT-PROTOCOL.md` | How to run honest cold A/B |
| `STACK-DIAGRAM.md` | Mermaid call-routing diagram |
| `FALSIFIERS.md` | Concrete measurements that kill SYNTHESIS claims |
| `SUCCESS-METRICS.md` | How to declare 10-min vs 15–20 min SLA success |

Planner entry: `../PLANNING-HANDOFF.md`
