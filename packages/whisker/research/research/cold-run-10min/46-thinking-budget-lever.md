# 46 - Thinking-Budget Lever (unit-check pass path)

**Verdict:** garbage as a wall-saving lever — judge agents already omit `thinking_budget`, alliance-pod emits no hidden reasoning on the production template, and decode is dominated by visible in-schema JSON (`reasoning` fields), so "lowering thinking" on the unit-check pass path saves ~0 s.
**Confidence:** high (live probe 2026-07-07 + HEAD agent construction + prior `31-thinking-token-auditor.md`)

**Safe to lower?** **no**

(If the question meant shrinking the in-schema `UnitCheck.reasoning` field on pass, that is a different lever: **A-B**, already ranked as verdict-first / pass-path schema shrink in `00-baseline.md`.)

## Findings

- [CRITICAL] **Tapetum judge agents never set `thinking_budget` at HEAD.** Evidence: PDF/unit judge path constructs `AgentBackend(judge_backend, max_tokens=1536)` with explicit comment that thinking is omitted (`packages/whisker/src/whisker/tapetum_llm/cli.py:1109-1113`); text-lane slots pass only `max_tokens` (`adjudicate.py:783-790`). `VllmThinkingBackend` only emits thinking kwargs when `thinking_budget is not None` (`packages/pipeline/src/pipeline/model_backends.py:294-298`): `0` → `enable_thinking: false`, `>0` → `thinking_token_budget`. Impact: there is no live thinking budget on unit checks to lower; expected wall delta **0 s** on the 3003 s cold run.

- [CRITICAL] **Live probe: pod ignores budget; default path has no hidden reasoning phase.** Evidence: `packages/whisker/research/llm-batching/21-terse-output.md:11-23` (alliance-pod, vLLM 0.24.0, DeepSeek V4 Pro): baseline 13.7 s / 948 completion tokens / reasoning "none"; `thinking_token_budget=512` ignored (12.7 s); explicit `thinking=true` doubled wall (~26.5 s) without separated reasoning. Authority docs agree: `tapetum_llm.md:33`, `:307-308`; prior auditor `research/tapetum-llm-speedup/31-thinking-token-auditor.md:8-10`. Impact: "lower thinking on pass path" cannot cut decode because hidden CoT is already off.

- [CRITICAL] **Decode-bound wall is visible JSON, not thinking tokens.** Evidence: cold-run baseline decode-dominated (~70 tok/s solo; mean decode 5.91 s vs prefill 0.46 s, `research/cold-run-10min/00-baseline.md:24-25`); unit-check P50 ~77 tok with pass path ~55 tok dominated by the 40-word in-schema `reasoning` field (`models.py:301-303`; `31-thinking-token-auditor.md:16`; `14-output-token-surgeon` via prior corpus). Impact: the pass-path decode lever is **schema/prompt output discipline** (verdict-first / terse `reasoning`), not `thinking_budget`. Ranked already as MODERATE lever #3 in `00-baseline.md:34` (~180-360 s band before short-circuit overlap).

- [HIGH] **Authority-doc `thinking-budget` values are dead knobs for this pod.** Evidence: cascade steps declare `thinking-budget: 1024/4096` (`tapetum_llm.md:247-248`, `:268-269`) but "are NOT forwarded to the model backend" (`tapetum_llm.md:33`). Backend misalignment: budget kwarg ≠ V4-Pro `enable_thinking` (`model_backends.py:294-298` vs probe C). Impact: wiring or lowering those meta values does not change decode today; enabling thinking would **increase** wall (~2× on probe B).

- [HIGH] **MODELS.md sampling pins are orthogonal and already applied; do not retune for this lever.** Evidence (`MODELS.md` "Sampling pins"):

  | Setting | Pin | Relevance here |
  |---|---|---|
  | `temperature` | 0.0 | Greedy; unchanged by thinking_budget |
  | `top_p` | 1.0 | Documented; unchanged |
  | `top_k` | 1 (`package_body`) | Constrains decode space; unchanged |
  | `seed` | 0 | Tie-break where honored; unchanged |
  | `parallel_tool_calls` | False | N/A for judge structured JSON |
  | `max_tokens` | Per agent | Judge 1536; text fast/deep 1024/2048 — these cap **visible** JSON when thinking is off |

  Impact: any pass-path speed play must shrink emitted tokens under these pins (schema/prompt), not loosen sampling. D5 forbids per-call temperature/seed overrides.

- [MED] **Defensive `thinking_budget=0` is insurance only.** Evidence: would send `enable_thinking: false` explicitly (`model_backends.py:295-296`); quality risk low; wall saving 0 s if server default already off (`31-thinking-token-auditor.md:24-26`). Impact: optional hygiene if pod defaults flip; not a 10-min-path lever.

- [MED] **No per-verdict thinking control exists.** Evidence: one `AgentBackend` instance serves all unit checks (`cli.py` / `unit_judge.py`); pass vs fail is model output, not a client branch that could set a lower thinking budget only on predicted passes. Impact: even if thinking were on, "lower on pass path only" would require a two-call cascade or speculative short schema — not a budget knob.

## False-pass hypothesis

Lowering/omitting `thinking_budget` further: **none** on current pod (already off). The false-pass risk attaches to the **adjacent** lever — shrinking pass-path in-schema `reasoning` / guided pass micro-schema — where a model can emit `verdict:"pass"` + empty `defects` without comparing countable deltas (e.g. `constexpr` counts), widening the documented selection gap (only 16/381 papers had LLM-changed merged verdicts; `00-baseline.md` prior corpus). That lever needs holdout A/B, not a thinking-budget change.

## False-fail hypothesis

`thinking_budget=0` when already off: **none**. Explicitly **enabling** thinking on structured JSON risks JSON landing in an unread reasoning channel (vLLM reasoning-parser / content split), parse retries, and tombstone `error` / demotion to `review` without new defect catch (`31-thinking-token-auditor.md:37-38`).

## What would change my mind

One `--debug` fleet sample (≥20 papers) on alliance-pod where median per-call `<!-- reasoning -->` / hidden-reasoning chars exceed ~500 while raw JSON stays <800 chars, **and** usage `completion_tokens` exceeds reconstructed visible JSON by a similar margin. That would reopen hidden-thinking suppression as a rank-1 decode lever. Absent that, close the thinking-budget track and fund pass-path **visible** output shrink + call elimination.

## Answer (machine-readable)

```
safe_to_lower: no
wall_saving_if_lowered_now: ~0 s
real_pass_path_lever: in-schema reasoning / verdict-first schema (A-B required)
sampling_pins: MODELS.md temperature=0 top_p=1 top_k=1 seed=0 parallel_tool_calls=false
```
