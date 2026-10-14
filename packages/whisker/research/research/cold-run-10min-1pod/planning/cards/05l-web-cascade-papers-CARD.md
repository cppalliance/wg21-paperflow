# Card 05l — Cascade LLM judges (cheap → expensive)

**Source report:** `05l-web-cascade-papers.md`  
**Verdict in source:** usable

## Bottom line

Literature supports cheap-first escalate for judges with large cost cuts at matched quality / ≥80% calibrated agreement. Portable fleet shape: **monolith = Pro, units = dense** — not a second V4-Pro. Hybrid: route by call class, cascade within units on confidence. Do not cite FrugalGPT 98% as cold wall ≤600 s proof.

## Numbers

- Jung stronger cascade: **−78.5%** cost at guaranteed ≥80% human agreement; weaker **−87.4%** (~12.6% of GPT-4 cost); ChatArena ~**88%** of covered work on cheap judges @ ~79% coverage.
- FrugalGPT: up to **98%** cost cut matching best LLM; or **+4%** accuracy at same cost; OVERRULING example +1% acc / **−73%** cost.
- AutoMix: **>50%** cost cut at comparable performance.
- RouteLLM (route, not cascade): up to **−85%** cost at **95%** of GPT-4 (MT-Bench).
- ABC: up to 14× edge→cloud; ~3× GPU rental; 2–25× API vs SOTA cascades.
- Escalate caveat: hard path pays **sum of tier latencies**; keep escalate often **≤15–30%** to strongest tier; target **≤15%** of dense unit attempts for our wall.
- Hetero sketch (from `12`): dense ~180–220 s; Pro ~510–540 s; wall **max ≈ 510–540 s** (MoE-bound) if escalate band small. Escalate 30% of units can push Pro queue back above 600 s.

## Architecture implication

```
T0 CPU det → T1 dense units (accept if conf≥λ + schema OK)
          → T2 Pro: monolith / HTML tier-1 / oversize / escalate band
```

Escalate on invalid schema, low conf, empty defect quote on non-pass, dense 5xx, oversize. Prefer schema confidence over Simulated Annotators N=5 (multiplies calls). Instrument `{accepted_dense, escalated_pro, dense_conf, fused_delta}`.

## Reject-or-A-B

**A/B gated adopt** after dense live + scoping + 381/381 parity. **Reject:** twin Pro; ABC multi-dense jury every unit; cloud proprietary judges; FrugalGPT DistilBERT training before schema-threshold cascade ships. Escalate >25% at parity λ → cascade EV collapses.

## Links

- https://arxiv.org/abs/2407.18370 (Jung)
- https://arxiv.org/abs/2305.05176 (FrugalGPT)
- https://arxiv.org/abs/2310.12963 (AutoMix)
- https://arxiv.org/abs/2407.02348 (ABC)
- https://www.lmsys.org/blog/2024-07-01-routellm/
- `12-dense-offload-architecture.md`
