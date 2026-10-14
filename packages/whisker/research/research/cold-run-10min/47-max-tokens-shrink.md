# 47 - Max-Tokens Shrink (pass-path decode caps)

**Verdict:** usable-with-conditions — current `max_tokens` ceilings (1536 judge / 1024 fast) are 3–20× above measured P50 completions; pass-path caps can safely drop to 128–512 without touching fail-path quote headroom, but wall savings (~124–155 s MODERATE stack) require pairing schema shrink (verdict-first / empty pass reasoning), not ceiling tuning alone.
**Confidence:** medium

## Findings

- [CRITICAL] **All PDF-lane judge calls share one `max_tokens=1536` agent; HTML metadata/unit use `fast=1024`.** Evidence: judge agent construction `packages/whisker/src/whisker/tapetum_llm/cli.py:1106-1112` ("PdfJudgment is small … 1536 covers worst-case output with margin"); monolith `pdf_judge.py:672-680`, metadata `unit_judge.py:263-272`, unit check `unit_judge.py:801-803` all call `run_judge_task(agent, …)` with no per-call override; `judge_task.py:68-74` forwards to `agent.run` without `max_tokens` kwarg. HTML lane: `_SLOT_MAX_TOKENS fast=1024/deep=2048` `adjudicate.py:90-93`; metadata on HTML passes `ctx.agents["fast"]` `adjudicate.py:502-517`. Impact: a single 1536 ceiling applies to monolith, metadata, unit check, and page escalation even though observed outputs differ 4× by call type.

- [CRITICAL] **Measured completion lengths (377 sidecars, 2026-07-23 cold fleet) — not hypothetical.** Source: `research/tapetum-llm-throughput/11-output-token-decode-auditor.md:10-14` (reconstructed from `data/whisker/llm/*.whisker.tapetum.json`). P50 output tokens per call type:

  | Call type | Schema | Fleet count | P50 | P90 | Pass-shaped / notes |
  |-----------|--------|-------------|-----|-----|---------------------|
  | Monolith | `PdfJudgment` | 381 | **283** | ~350 | ~124 tok if empty `missing_content`; P50 inflated by verbose 60-word `reasoning` |
  | Metadata / outline | `MetadataOutlineCheck` | 377 | **112** | ~180 | ~55 tok is 40-word `reasoning`; bools + empty lists on clean pass |
  | Unit check | `UnitCheck` | 1510 | **77** | **395** | 70% pass (`defects:[]`); ~55 tok is pass `reasoning`; P90 = 2–3 `DefectFinding` groups |
  | Page escalation | `PageJudgment` | ~16 | ~150 est. | ~250 | Same quote discipline as monolith |
  | **Fleet total** | — | 2284 | **134/call** | — | **~303,447 output tokens** (`14-output-token-surgeon.md:8`) |

  Pod lifetime mean (all requests, not tapetum-isolated): **235 output tokens/request**, decode **5.91 s** vs prefill **0.46 s** (`146-verifier-prefix-cache-contradiction.md:22-25`). Impact: 1536 cap binds rarely; decode time tracks **emitted** tokens, not ceiling.

- [HIGH] **1536 cap rationale is worst-case quote grounding, not observed pass path.** Evidence: comment `cli.py:1106-1108` (verdict + ≤5 short quotes + 60-word reasoning); synthetic worst-case `UnitCheck` with 5 `DefectFinding` groups ≈ **554 tok** (`11-output-token-decode-auditor.md:14`); monolith worst-case `PdfJudgment` ≈ **222 tok** JSON chars. Current cap = **2.8×** worst-case unit JSON; pass unit P50 = **20×** under cap. Backend retry on `finish_reason=length` grows budget 1.5× (`model_backends.py:377-387`, `_RETRY_MAX_TOKENS_GROWTH`). Impact: lowering pass-path cap to 128–512 leaves **768+ fail-path headroom** without touching quote fields.

- [HIGH] **Pass-path shrink target is schema + cap, not cap alone.** Evidence: 1057/1510 unit checks (70%) zero-defect (`00-baseline.md:29`); pass P50 77 tok, ~55 tok is `reasoning` nobody consumes on pass (`14-output-token-surgeon.md:8`, `unit_judge.py` persists but fusion/grounding skip it). Verdict-first / empty pass reasoning: **~55 tok → ~10 tok** per pass unit (`11-wall-arithmetic.md:39`); scaled MODERATE savings **~124–155 s** on surviving calls after metadata short-circuit (not full-fleet −250 s). `10-impl-status-auditor.md:29`: verdict-first **not implemented** at HEAD. Impact: `max_tokens=128` on unchanged 77-tok pass JSON saves **0 s** (model still decodes full schema); cap + schema shrink together capture savings.

- [MED] **Per-call `max_tokens` override is supported but unwired on judge path.** Evidence: `AgentBackend.run(..., max_tokens: int | None = None)` `packages/pipeline/src/pipeline/agents.py:117-125`; `run_judge_task` omits it `judge_task.py:68-74`. Implementation: add optional `max_tokens` to `run_judge_task`; pass lower cap when routing pass-path schema variants (or when pre-screen predicts empty defects). Whisker-only; no pipeline edit required.

- [MED] **Risk envelope for aggressive caps.** Evidence: `14-output-token-surgeon.md:38-40` — cap below P90 defect output triggers length retry (doubles decode, masquerades as regression); `DefectFinding.source_quote` (25 words ≈ 35 tok) and `affected_count` are mechanically consumed (`unit_judge.py:448`, `703-708`). Fail-path floor: unit **≥768** (P90 395 + margin + 1.5× retry), monolith/page **≥768** (3 quotes + reasoning), metadata **≥512**. Pass-path only: unit **128**, metadata **256**, monolith **512**.

- [LOW] **HTML text lane caps (1024/2048) are decoupled from PDF judge 1536.** Evidence: `20-payload-scoping-auditor.md:11-15`; tier-1 `Adjudication` P50 ~220 tok on pass (`14-output-token-surgeon.md:16`) — 1024 already 4× headroom. Lower priority for 10 min target (201 HTML tier-1 calls vs 1510 PDF unit checks).

## Current vs measured vs proposed caps

| Call type | Agent / current cap | Observed P50 | Observed P90 | **Recommended pass cap** | **Recommended fail cap** | 1.5× retry ceiling |
|-----------|---------------------|--------------|--------------|--------------------------|--------------------------|--------------------|
| PDF monolith | `judge` / **1536** | 283 | ~350 | **512** | **768** | 1152 |
| Metadata / outline (PDF) | `judge` / **1536** | 112 | ~180 | **256** | **512** | 768 |
| Metadata / outline (HTML) | `fast` / **1024** | 112 | ~180 | **256** | **512** | 768 |
| Unit check pass (70%) | `judge` / **1536** | 77 (~55 reasoning) | — | **128** | — | 192 |
| Unit check fail / review | `judge` / **1536** | — | 395 | — | **768** | 1152 |
| Unit check (HTML pass) | `fast` / **1024** | 77 | — | **128** | — | 192 |
| Page escalation | `judge` / **1536** | ~150 | ~250 | **384** (pass) | **768** | 1152 |

**Pass cap assumes paired schema change:** verdict-first field order; on pass, `reasoning` omitted or capped at 10 words; `UnitCheck` pass micro-schema `{unit_id, verdict, confidence}` (~15–25 tok). Without schema change, keep pass caps at observed P50 + 50% margin (unit **128**, metadata **384**, monolith **512**) — still far below 1536.

## Pass-path shrink proposal (implementation order)

1. **Schema (MODERATE, ~124–155 s wall)** — verdict-first / conditional pass reasoning on `UnitCheck` and `MetadataOutlineCheck` (`10-impl-status-auditor.md:13`); monolith `reasoning` 60→20 words on pass (`14-output-token-surgeon.md:12`). Holdout gate: 48-paper manifest, ≥95% verdict stability (`14-output-token-surgeon.md:44`).

2. **Per-call `max_tokens` on judge path (LOW risk, incremental)** — extend `run_judge_task` with optional `max_tokens`; wire from call site:
   - Pass unit: **128** (HTML fast + PDF judge agents).
   - Pass metadata: **256**.
   - Pass monolith (empty `missing_content` pre-check impossible pre-call — use **512** default; escalate to **768** when risk router or monolith pre-screen expects quotes).
   - Fail/review paths: table fail caps above.

3. **Do not lower global judge agent default below 768** until pass/fail routing exists — a single 512 default on `AgentBackend(..., max_tokens=512)` would truncate P90 defect unit checks and trigger costly length retries (`14-output-token-surgeon.md:38-40`).

4. **Leave `_IDEAL_MAX_TOKENS=2048` and HTML `deep=2048` unchanged** — negligible fleet share (~1 ideal + ~23 tier-2 calls).

## False-pass hypothesis

Pass cap **128** with verdict-first empty reasoning on the 1057 zero-defect unit checks removes auditable CoT (`models.py:14-15`). Model returns `pass`/`defects:[]` without comparing localized source — widening the selection gap (`00-baseline.md:29-30`, only 16/381 verdicts changed by LLM today). Mitigation: keep deterministic post-checks (`verify_unit_evidence`, keyword delta groups); holdout A/B before fleet rollout.

## False-fail hypothesis

Global judge cap **512** (without pass/fail split) hits P90 unit output (~395 tok) or 5-group worst case (~554 tok), triggering `finish_reason=length` → 1.5× retry → **1152 effective decode** on borderline papers — net slower than 1536 single shot, plus spurious `error`/`review` from truncated JSON (`14-output-token-surgeon.md:38-40`).

## What would change my mind

`--debug` logging of `usage.completion_tokens` per call type on 20-paper replay: if pass unit median **>120 tok** despite empty defects, caps below 256 are unsafe; if median **≤30 tok** after verdict-first schema lands, pass cap **96** is viable and MODERATE wall savings toward **155 s** upper bound are confirmed.

## Code anchors

- `packages/whisker/src/whisker/tapetum_llm/cli.py:1106-1112` — judge `max_tokens=1536`
- `packages/whisker/src/whisker/tapetum_llm/adjudicate.py:90-93` — `_SLOT_MAX_TOKENS` 1024/2048
- `packages/whisker/src/whisker/tapetum_llm/judge_task.py:68-74` — no per-call cap forward
- `packages/whisker/src/whisker/tapetum_llm/models.py:262-320` — schema field caps (40/60-word reasoning)
- `research/tapetum-llm-throughput/11-output-token-decode-auditor.md` — measured P50/P90 completions
- `research/tapetum-llm-speedup/14-output-token-surgeon.md` — field-level budgets + shrink math
- `research/cold-run-10min/11-wall-arithmetic.md:39` — verdict-first wall estimate (scaled)
