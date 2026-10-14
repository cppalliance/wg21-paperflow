# ADR-015: Non-think on unit checks (Pro, structured JSON)

**Status:** Proposed — holdout A/B required before ship (no blanket force).

**Date:** 2026-07-24

---

## Context

Unit checks dominate residual MoE decode after short-circuit. On DeepSeek-V4-Pro, thinking defaults on (hosted) and CoT tokens dominate wall for verdict-shaped calls. Hosted classifier measurement: ~31.8 s thinking-on → ~2.7 s Non-think on a non-stream verdict call. HF mode cliffs are large on hard STEM (GPQA, LiveCodeBench) but mild on knowledge-ish work; schema-bound local-evidence checks are the Non-think candidate bucket, hard adjudication is not.

Client and serving traps:

- `reasoning_effort="low"` on DSV4 maps to **High** (vLLM PR #40982), not a short CoT path.
- Hosted / CN provider docs: do **not** pair `thinking.enabled` with `response_format: json_object`.
- vLLM #41132 class: thinking-on + `json_object` can land JSON in `reasoning` with empty `content`.
- Hosted: `thinking.disabled` + `reasoning_effort` → 400-style conflict. Send one of {think-off, effort}, not both.

---

## Decision

**Propose** Non-think for schema-bound, local-evidence, verdict-first unit checks on `alliance-pod`, gated by holdout A/B. Keep Think High on escalate / hard / ambiguous / code-semantics / multi-hop slices. Never Think Max on the cold unit-check fleet.

### Exact kwargs (vLLM / `alliance-pod`)

Primary (preferred explicit disable):

```python
extra_body={"chat_template_kwargs": {"thinking": False}}
```

Alias:

```python
extra_body={"chat_template_kwargs": {"enable_thinking": False}}
```

Top-level equivalent (auto-injects `enable_thinking=false`):

```python
reasoning_effort="none"
```

Exact kwargs object for Non-think:

```json
{"thinking": false}
```

Do **not** send hosted wire format to the pod:

```json
{"thinking": {"type": "disabled"}}
```

That object is for `api.deepseek.com` only.

If thinking must stay on for a quality holdout slice:

```python
extra_body={
    "chat_template_kwargs": {
        "thinking": True,
        "reasoning_effort": "high",  # never max for unit checks
    },
}
```

### Hard client invariants (never)

| Anti-pattern | Why |
|--------------|-----|
| `reasoning_effort="low"` (or `"medium"` / `"minimal"`) expecting shorter CoT | Maps to **High** on DSV4; burns CoT as High |
| `thinking` / `enable_thinking` true **with** `response_format: json_object` | Official/CN guidance forbids; vLLM can put JSON in `reasoning`, empty `content` |
| `thinking` disabled **plus** `reasoning_effort` set | Hosted 400; risk of silent fallback-to-think on miswired clients |
| Enabling thinking to “fix” schema failures | Schema needs retries / prompt / guided path, not more CoT |
| Blanket Non-think without A/B | GPQA/LiveCodeBench-class silent false-pass/false-fail |

Prefer Non-think + guided/`json_object` / schema-in-prompt + client validation. Keep `temperature=0` / greedy pins on the Non-think path (Non-think honors sampling; thinking mode does not).

### A/B gate (ship bar)

Same papers, same seeds/pins: Pro Non-think unit checks vs current Pro High.

- Defect-group recall / flip rate within existing same-model noise band (≥25% flip budget from prior corpus).
- Fail-closed rate not worse; schema retry rate not up.
- Measured `L_u'` on alliance-pod (not blog tok tables) large enough that `N_u × (L_u − L_u') / 16` closes a material slice of residual wall.

Default policy after pass: escalate-shaped routing — Non-think on the cheap unit-check majority, Think High on escalate/hard slice. Blanket force = **no**.

---

## Consequences

**Positive**

- Cuts **L** on the majority unit-check lane by removing reasoning tokens (order-of-magnitude decode when CoT dominated wall).
- Avoids think+JSON parser footguns and empty-content retries that masquerade as “slow pod.”
- Documents exact vLLM kwargs so clients do not copy hosted `thinking.type` onto alliance-pod.

**Negative / constraints**

- Quality cliff on hard STEM/coding unit checks if Non-think is applied blindly.
- Wall win is L-only at fixed `S_eff=16`; does not alone close the 800–900 s post-MODERATE gap.
- Client stacks (pydantic-ai / `AgentBackend`) must be probed so they do not inject `reasoning_effort=high` while Non-think is requested.

---

## Evidence

| Claim | Source |
|-------|--------|
| Non-think for shallow JSON judges; not blanket | `05a-web-nonthink.md` |
| Three modes only; `low` → High; exact short-decode knobs | `05c-web-reasoning-effort.md` |
| Hosted `thinking.type=disabled` ↔ vLLM `chat_template_kwargs.thinking=false` | `05q-web-official-think-off.md` |
| Never thinking+`json_object`; never disabled+effort; do not think-to-fix-schema | `05y-web-cn-forums.md` |
| Hosted classifier ~31.8 s → ~2.7 s Non-think | DeepSeek #1464 via `05c` |
| vLLM JSON-in-reasoning when think on | vLLM #41132 via `05a`, `05y` |

---

## Open blockers

1. **Holdout A/B** on tapetum unit-check prompts (Proposed → Accepted only after pass).
2. **Live probe** that alliance-pod / client path is not already Non-think, and that Non-think kwargs are honored (no dual `reasoning_effort` inject).
3. Measured `L_u'` under matched occupancy (`28` shared-pod noise).
