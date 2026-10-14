# CARD: 05p — FrugalGPT / AutoMix / cascade routing (latency)

## Bottom line
Literature cascades keep ~70–85% of queries on the cheap model (~15–30% escalate). Cascade latency is additive on escalations; predictive routing (pick once) beats FrugalGPT-style sequential hops when the cheap hop is not much faster than the strong. Same-size V4-Pro→V4-Pro cascade does not help wall.

## Numbers
- FrugalGPT HEADLINES: only **16.6%** reach GPT-4 → **~83.4%** stay cheap; cost savings **50–98%** vs best single LLM.
- RouteLLM: **86%** stay on weak model for 95% GPT-4 quality on MT Bench; MMLU needs ~**54%** strong for same bar.
- AutoMix: **>50%** compute cut; router **<1 ms**; ops target **60–80%** stay on SLM (escalate **20–40%**).
- Planning central: **~75%** stay cheap; escalate under **~30%**.
- Sketch @ N=1200, L_strong=20 s, S=16: always-Pro **1500 s**; predictive 75%/L_cheap=5 s → **~656 s**; cascade same split → **~750 s**.

## Architecture implication
Cascade/routing only helps if cheap hop is a **faster dense** endpoint already in SERVICES.toml, with escalate in the 15–30% band. Prefer HybridLLM/RouteLLM-style predictive route over always-pay-cheap then escalate. Monitor escalate % as an SLO; p99 is the escalate path.

## Reject-or-A-B
- **A/B:** dense judge (Qwen/Gemma) vs V4-Pro on 50–100 papers — if cheap-stay **<50%** at fail-closed quality, literature 70–85% does not transfer.
- **Reject:** same-size MoE cascade; treating classification/QA router scores as WG21 objection fidelity without parity gate.
- **Watch false-fail:** self-verify thresholds over-escalate to 40–90% → slower than always-strong.

## Links
- Source: `05p-web-frugalgpt.md`
- Related: `12-dense-offload-architecture.md`, `00-baseline.md`, ADR-003 heterogeneous cascade
- arXiv:2305.05176 (FrugalGPT), arXiv:2310.12963 (AutoMix), arXiv:2404.14618 (HybridLLM), arXiv:2406.18665 (RouteLLM)
