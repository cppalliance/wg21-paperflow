# FILE MANIFEST — `research/cold-run-10min-1pod/`

Complete inventory for planning agents. All paths relative to this directory unless noted.

## Entry points (read in this order)

| # | File | Purpose |
|---|------|---------|
| 1 | `PLANNING-HANDOFF.md` | **Start here** — constraints, options, checklist |
| 2 | `PROMPT-FOR-PLANNER.md` | Paste-ready prompt for the planning LLM |
| 3 | `SYNTHESIS.md` | Executive verdict + reject ledger |
| 4 | `planning/` | ADRs, matrices, cards, packets (Grok swarm) |
| 5 | `FILE-MANIFEST.md` | This catalog |

### `planning/` pack (swarm)

| Glob | Purpose |
|------|---------|
| `00-DECISION-MATRIX.md`, `01-OPTIONS-ABC.md` | Master choices |
| `ADR-*.md` | Architecture decision records |
| `cards/*-CARD.md` | One-page distill per research report |
| `packets/D*.md` | Decision packets |
| `checks/CHECK-*.md` | Claim confirmation slips |
| `micro/M*.md` | Micro claim cards |
| `RISK-REGISTER.md`, `OPEN-QUESTIONS.md`, `TICKET-BACKLOG.md`, `PLANNER-FAQ.md` | Planner tools |

## Baseline & status

| File | One-line |
|------|----------|
| `00-baseline.md` | Twin forbidden; S=16; 3003 s cold measurement |
| `10-impl-status-1pod.md` | v11 already landed; top remaining code levers |
| `26-dense-pod-liveness.md` | All 4 dense pods HTTP 404; alliance-pod UP |
| `28-shared-pod-noise.md` | Multi-tenant HIGH variance risk |

## Arithmetic & physics

| File | One-line |
|------|----------|
| `11-wall-arithmetic-1pod.md` | Stacked table; central ~680 s AGGRESSIVE |
| `17-physics-floor-skeptic.md` | ≤10 min impossible MoE-only; ~23 min floor |
| `18-packages-1pod.md` | CONSERVATIVE / MODERATE / AGGRESSIVE @ S=16 |
| `20-heterogeneous-wall.md` | `wall = max(T_moe, T_dense)` |

## Architecture designs

| File | One-line |
|------|----------|
| `12-dense-offload-architecture.md` | Call split MoE~428 / dense~1879; ~511 s |
| `13-deterministic-metadata.md` | A/B-only; −471 s; design anchors |
| `14-router-quota-1pod.md` | Safe −150–250 calls post-v11 |
| `15-verdict-first-design.md` | UnitCheckClear bifurcation; −92–155 s |
| `16-server-ops-1pod.md` | Alliance-pod-only ops checklist |
| `19-quality-gate-1pod.md` | Validation ~0.8–1.2 h; gates |
| `23-payload-scope-dense.md` | H2 window + presence index; dense S unlock |
| `27-dualpod-dependency-rewrite.md` | Dual-pod → 1-pod substitutes |

## Explored / rejected / small levers

| File | One-line |
|------|----------|
| `21-skip-monolith-revisit.md` | Skip monolith = **No** |
| `22-html-vs-pdf-mix.md` | HTML 52.8%; det-meta HTML-first ~251 s |
| `24-det-skip-llm.md` | No default LLM-skip mode |
| `25-call-class-fingerprint.md` | 0 s cold first-run; warm/rerun only |
| `29-ideal-verify-fleet-cost.md` | 3/381 papers; ~60–90 s |

## Web / DeepSeek / literature (`05*`)

| File | Topic |
|------|-------|
| `05-web-think-off-official.md` | Official think-off |
| `05a-web-nonthink.md` | Force Non-think conditions |
| `05b-web-flash-vs-pro.md` | Flash vs Pro; needs deploy |
| `05c-web-reasoning-effort.md` | vLLM kwargs; never `low` |
| `05d-web-single-node-serving.md` | Top ops flags @ S=16 |
| `05e-web-single-endpoint-judge.md` | Single-endpoint patterns |
| `05f-web-dense-judge-lit.md` | Qwen3-32B class; not Gemma |
| `05g-web-slmjury.md` | Path F dense+short tokens |
| `05h-web-eval-harness-1backend.md` | DeepEval/Ragas call cuts |
| `05i-web-community-workarounds.md` | Ranked community tips |
| `05j-web-mtp-short-json.md` | MTP A/B; do not bank |
| `05k-web-pd-disagg.md` | P/D reject |
| `05l-web-cascade-papers.md` | FrugalGPT/Jung cascade design |
| `05m-web-short-osl-moe.md` | Short-OSL vLLM flags |
| `05n-web-v4-structured.md` | Schema-slim tactics |
| `05o-web-localllama.md` | LocalLLaMA DSpark/MTP tips |
| `05p-web-frugalgpt.md` | ~70–85% stay on cheap model |
| `05q-web-official-think-off.md` | Exact kwargs table |
| `05r-web-extractor-judge.md` | MinerU/marker still extract-only |
| `05s-web-async-sched.md` | Async underfill; try disable |
| `05t-web-dbo-deepep.md` | ~12% DeepEP @ S=16 |
| `05u-web-arena-judges.md` | Verdict-token / parallel sizing |
| `05v-web-batch-invariant.md` | BI reject (~50% hit) |
| `05w-web-ngram-spec.md` | Ngram marginal |
| `05x-web-v4-paper-efficiency.md` | CSA/HCA already on |
| `05y-web-cn-forums.md` | thinking+json_object hard limit |
| `05z-web-hosted-latency.md` | Flash ~1.7× Pro decode |

## Meta / superseded

| File | Note |
|------|------|
| `_index.md` | Short pointer |
| `SYNTHESIS-DRAFT.md` | Superseded → `SYNTHESIS.md` |

## Related corpora (outside this dir)

| Path | Role |
|------|------|
| `research/cold-run-10min/` | Dual-pod era; superseded for execution |
| `research/tapetum-llm-speedup/` | Original 150-agent speedup swarm |
| `research/tapetum-llm-throughput/` | Call census / sidecars |
| `research/slots-32-regression/` | Why S=32 is forbidden |
| `research/concurrency-381/` | Why c>32 fails |
| `packages/whisker/research/deepseek-v4-pro/` | Whisker-local V4 notes |
