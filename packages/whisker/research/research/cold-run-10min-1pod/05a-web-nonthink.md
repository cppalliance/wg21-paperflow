# 05a - Web forage: DeepSeek V4 Non-think / Instant vs Thinking (JSON judge)

**Verdict:** usable-with-conditions — Non-think is the real single-pod decode dial for structured unit checks, but blanket force is a quality cliff on hard adjudication; community + docs support JSON-with-thinking-off for classification/extraction, not for STEM-hard judging.
**Confidence:** high on API/mode facts and HF cliffs; medium on "production JSON judge fleets" (guides + framework tests exist; few named WG21-class judge fleets publish A/Bs).

**Constraint context:** single `alliance-pod` MoE (V4-Pro, S_eff=16, c=32); quality-stability / fail-closed; dual-pod forbidden.

## Sources (2026 forage)

| Channel | Source | URL / ID | Date / note |
|---------|--------|----------|-------------|
| Official | Thinking Mode guide | https://api-docs.deepseek.com/guides/thinking_mode/ | live; default **enabled** |
| Official | JSON Output guide | https://api-docs.deepseek.com/guides/json_mode/ | JSON works; empty-content caveat |
| Official | HF V4-Pro README (mode table) | https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro | Non-think / High / Max + cliffs |
| Docs | deepseekai.guide JSON + Non-think | https://deepseekai.guide/api/deepseek-api-json-mode/ | Non-think for high-volume structured |
| Docs | chat-deep.ai thinking + JSON | https://chat-deep.ai/docs/deepseek-thinking-mode/ | Flash Non-think for simple JSON |
| Docs | chat-deep.ai JSON Output | https://chat-deep.ai/docs/json-output/ | Flash→usually non-thinking; Pro→think when hard |
| Blog | Framia mode explainer | https://framia.converge.ai/page/en-US/news/deepseek-v4-thinking-modes | ~200–500 vs ~2k–8k vs ~8k–50k tokens |
| Blog | Verdent coding notes | https://www.verdent.ai/guides/deepseek-v4-preview-for-coding-what-changed | Pro Non-think ≈ Opus 4.6 non-think (vendor claim) |
| HN | Overthink / agent steps | https://news.ycombinator.com/item?id=47984407 | disable thinking for small incremental steps |
| HN | Pro never finishes | https://news.ycombinator.com/item?id=48456099 | long thinking stalls |
| HN | Flash for interactive | https://news.ycombinator.com/item?id=48440796 | Flash nearly instant for small tasks |
| GitHub | vLLM #41132 structured+think | https://github.com/vllm-project/vllm/issues/41132 | JSON lands in `reasoning` when think on |
| GitHub | DeepSeek #1376 tool_choice | https://github.com/deepseek-ai/DeepSeek-V3/issues/1376 | think mode rejects forced tool_choice on `/v1` |
| GitHub | agno V4 TEST_LOG | https://github.com/agno-agi/agno/.../deepseek/TEST_LOG.md | 2026-05-29: think-off + structured JSON **PASS** |
| Ops | Sovereign MoE best practices | https://docs.moe-sovereign.org/guide/best-practices/ | thinking models break JSON planner/judge; disable |
| Prior corpus | cold-run-10min/59 | research/cold-run-10min/59-deepseek-v4-release.md | same official dial; no fleet A/B yet |

Reddit / Discord / Twitter: no high-signal primary threads with reproducible judge A/Bs found in this pass (search noise dominated by launch hype). Treat HN + GitHub + vendor docs as the community evidence floor.

## Findings

- [CRITICAL] **Non-think is the official Instant path; thinking defaults ON.** Hosted: `extra_body={"thinking": {"type": "disabled"}}`. Self-host vLLM: `chat_template_kwargs.enable_thinking=false` (V4-Pro needs explicit enable for think). HF: Non-think = routine/low-risk; Think High = slower/more accurate; Think Max = fullest. Impact: every unit-check that still emits CoT is paying decode we can legally turn off. Moves **L** (per-call decode), not S.

- [CRITICAL] **HF mode cliffs are brutal on hard STEM/coding, mild on knowledge-ish MMLU.** V4-Pro Non-Think → High: GPQA 72.9→89.1; LiveCodeBench 56.8→89.8; HLE 7.7→34.5; HMMT 31.7→94.0; MMLU-Pro only 82.9→87.1. Impact: a unit check that is "schema + local evidence match" ≈ MMLU-class; a unit check that is "is this defect real / does this code claim hold" ≈ GPQA/LiveCodeBench-class. **Blanket Non-think risks silent false-pass/false-fail on the hard slice.**

- [HIGH] **Token/latency dial is order-of-magnitude, not 10%.** Third-party mode writeups cite ~200–500 tok (Non-think) vs ~2k–8k (High) vs ~8k–50k (Max). HN: Pro stalls in long thinking; Flash Non-think feels "nearly instant" for small tasks. Impact: if unit-check mean decode is ~20 s and dominated by reasoning tokens, Non-think is the only client-side lever that can cut **L** enough to matter under S_eff=16.

- [HIGH] **Production JSON + thinking-off is real and recommended for simple structured work.** Official JSON mode works with think on or off; JSON lives in `content`, not `reasoning_content`. Guides (deepseekai.guide, chat-deep.ai): Flash + Non-think for classification / extraction / high-volume JSON; Pro + think when the schema decision needs multi-step inference. agno cookbook (2026-05-29) PASS on `thinking_mode.py` (off) and `structured_output.py` on V4-Flash. Impact: "JSON judge with thinking off" is a documented production pattern for **shallow** judges, not a fringe hack.

- [HIGH] **Thinking-on hurts structured-output reliability on self-host stacks.** vLLM #41132: `response_format: json_object` + `enable_thinking: true` put the JSON object into `reasoning` with `content=None` on V4-Pro/Flash (closed after parser kwargs fix; still a footgun class). Sovereign MoE: thinking models wrap CoT and break JSON planners/judges → disable thinking. Hosted #1376: thinking rejects `tool_choice=required` on `/v1` (breaks framework structured-output paths that force a tool). Impact: for schema-in-prompt / JSON-object unit checks, **Non-think is the safer serving mode**, independent of quality cliffs.

- [MED] **Community framing matches our workload split.** HN: reasoning tuned for hard questions, overthinks small agent steps → try disable thinking + tight instructions. Vendor/blog: Pro Non-think quality approaches Opus non-think; still trails Opus-with-think. Impact: unit checks that are short, schema-bound, verdict-first are the community-endorsed Non-think bucket; fusion / hard rescue is not.

- [MED] **Arithmetic (S_eff=16 fixed).** Let unit-check share of residual after v11 short-circuit be `N_u` of `N_rem`, with mean latency `L_u`. Non-think hypothesis: `L_u' ≈ L_u / k` with `k ∈ [3,8]` if CoT was 2k–8k tokens and verdict JSON is ≤500 tokens (order-of-magnitude from mode tables; **measure on alliance-pod**, do not trust blog tok counts). Then  
  `Δwall ≈ N_u × (L_u − L_u') / 16`.  
  Example: `N_u=800`, `L_u=20`, `k=4` → `Δwall ≈ 800×15/16 ≈ 750 s` toward the ~800–900 s gap after MODERATE. That only counts if quality A/B holds. Flash swap is a separate product tradeoff (smaller active MoE), not required to get Non-think on Pro.

- [LOW] **No named public "DeepSeek V4 Non-think JSON judge fleet at 381-paper scale" found.** Closest: framework tests (agno), MoE pipeline docs (Sovereign), API guide recipes. Impact: we must run our own holdout; do not cite web as proof of tapetum parity.

## False-pass hypothesis

Force Non-think on all unit checks because "JSON judge = classification," then merge looks green while hard-defect recall collapses (GPQA/LiveCodeBench-class misses). Looks like a free wall win; destroys fail-closed credibility.

## False-fail hypothesis

Refuse Non-think entirely because "MODELS.md / quality-stability requires thinking" — official thinking mode ignores temperature pins anyway; Non-think is a first-class mode; shallow JSON judges in the wild deliberately disable CoT; vLLM think+JSON bugs argue the opposite for reliability.

## What would change my mind

1. Holdout A/B (same papers, same seeds/pins): Pro Non-think unit checks vs current Pro High — defect-group recall / flip rate within existing same-model noise band (≥25% flip budget from prior corpus), fail-closed rate not worse.
2. Measured `L_u'` on alliance-pod (not blog tok tables) large enough that `N_u × (L_u−L_u')/16` closes a material slice of the 800–900 s gap after MODERATE + short-circuit.
3. Counter-evidence: a production judge fleet showing Non-think worse on schema validity (retries) than High — would push keep-think for reliability even if slower.

## Return answer (operator question)

### Should we force Non-think on unit checks?

**Conditions (not blanket yes).**

| Decision | When |
|----------|------|
| **YES — force Non-think** | Unit checks that are schema-bound, local-evidence, verdict-first / classification-shaped; after holdout A/B within flip-noise; keep `temperature=0` / greedy pins on the Non-think path (Non-think honors sampling; thinking mode does not). Prefer Pro Non-think before Flash unless Flash A/B also holds. |
| **NO — keep Think High** | Hard / ambiguous adjudication, code-semantics, multi-hop claim checks, escalation / rescue paths, anything that historically flips under same-model noise. |
| **Never** | Think Max on the cold unit-check fleet (token explosion; wrong side of 10 min). Global force without A/B. Treating Non-think as free under S=32 / twin-pod fantasies. |

**Default policy recommendation for this corpus:** escalate-shaped routing — Non-think on the cheap unit-check majority, Think High on escalate/hard slice — only after the holdout. Blanket force = **no**.
