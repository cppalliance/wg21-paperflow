# CARD: 05q — Official V4 think-off → vLLM kwargs

## Bottom line
Hosted API disables thinking with `{"thinking": {"type": "disabled"}}`. On alliance-pod vLLM, Non-think is `chat_template_kwargs: {"thinking": false}` (alias `enable_thinking: false`) or top-level `reasoning_effort="none"`. Do not paste the hosted nested object onto vLLM and expect think-off.

## Numbers
- Hosted default: thinking **enabled**; effort `high` | `max` only when thinking on (`low`/`medium`→`high`, `xhigh`→`max`).
- Exact Non-think kwargs (vLLM): `{"thinking": false}`.
- Preferred client: `extra_body={"chat_template_kwargs": {"thinking": False}}`.
- Server default option exists: `--default-chat-template-kwargs '{"thinking": false}'` (request still overrides).
- Encoding: Non-think = `thinking_mode="chat"` (closes think block immediately after assistant token).

## Architecture implication
Explicit think-off on structured UnitCheck routes is a first-class L lever. Prefer explicit `false` over omit-kwargs when any server default or client path may enable thinking. Serve with `--tokenizer-mode deepseek_v4` and `--reasoning-parser deepseek_v4`.

## Reject-or-A-B
- **Ship / confirm:** map Non-think to exact vLLM kwargs above (ops + client).
- **Reject:** copying hosted `{"thinking": {"type": "disabled"}}` into `chat_template_kwargs`.
- **A/B (quality):** Non-think unit checks vs think-on (see `05a` / ADR-015); kwargs mapping itself is settled.

## Links
- Source: `05q-web-official-think-off.md`
- Related: `05-web-think-off-official.md`, `05a-web-nonthink.md`, `05c-web-reasoning-effort.md`, ADR-015
- https://api-docs.deepseek.com/api/create-chat-completion/
- https://api-docs.deepseek.com/guides/thinking_mode
- https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro
- https://docs.vllm.ai/en/stable/features/reasoning_outputs/
