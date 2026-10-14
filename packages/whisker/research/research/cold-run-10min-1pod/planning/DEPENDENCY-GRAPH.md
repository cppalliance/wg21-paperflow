# Dependency graph — P0→P8 + infra gate

**Date:** 2026-07-24  
**Sources:** `PLANNING-HANDOFF.md` §6, `SYNTHESIS.md` execution order, reports `10`–`20`.

Phases are sequential where arrows show hard prerequisites. MoE software (P1–P4) can proceed while dense is down; ≤10 min remains blocked at the infra gate until P5.

```mermaid
flowchart TD
  P0["P0 Remeasure cold on local v11<br/>truth baseline ~21–25 min"]
  P1["P1 Ship / commit v11 levers<br/>short-circuit, LJF, partial HMAC"]
  P2["P2 Det-metadata shadow A/B<br/>HTML-first ~251 s → fleet ~471 s"]
  P3["P3 Verdict-first + router / dynamic quota<br/>~−200–450 s stack"]
  P4["P4 Server Tier-1 ops<br/>MBT / APC / CUDA graphs; MTP A/B only"]
  GATE{{"INFRA GATE<br/>Restart h200-qwen3-32b<br/>dense endpoints 404 today"}}
  P5["P5 Dense pod live<br/>confirm 200 + bench shapes"]
  P6["P6 Payload scoping + call-class router<br/>~10–15k/unit; dense S=32–48"]
  P7["P7 Cascade + quality gate 19<br/>381/381 parity; escalate ≤15%"]
  P8["P8 Distill only if P7 quality fails<br/>parallel program"]
  OPTC["Option C: SLA reset ~15–20 min<br/>if dense never restarts"]
  TEN["≤10 min candidate<br/>wall ≈ max T_moe T_dense ~511 s"]

  P0 --> P1
  P1 --> P2
  P2 --> P3
  P3 --> P4
  P1 --> GATE
  P4 --> GATE
  GATE -->|ops restarts dense| P5
  GATE -->|ops will not restart| OPTC
  P5 --> P6
  P6 --> P7
  P7 -->|parity pass| TEN
  P7 -->|parity fail| P8
```

## Phase unlocks

| Phase | Work | Unlocks |
|-------|------|---------|
| P0 | Remeasure cold on local v11 | Truth baseline (~21–25 min expected) |
| P1 | Commit/ship v11 levers already in tree | Stable short-circuit |
| P2 | Det-metadata shadow A/B (HTML-first → fleet) | −~251 then −~471 s |
| P3 | Verdict-first + router/quota | −~200–450 s stack |
| P4 | Server Tier-1 flags (ops) | L cut; not enough alone |
| **Gate** | Alliance restarts `h200-qwen3-32b` | Unblocks Option B |
| P5 | Dense live + recipe | Safe to route units |
| P6 | Payload scoping + call-class router | Dense S=32–48 (without scoping: negative EV) |
| P7 | Cascade + quality gate (`19`) | Ship Option B or fail closed |
| P8 | Distill | Only if P7 quality fails |

## Hard rules on the graph

1. **P6 before dense enable:** unscoped full-md dense → S≤16, L≈20 s, T_dense ≈ 2349 s (`12`, `23`).
2. **P7 before `_LANE_VERSION` bump** for default dense routing (`19`).
3. **P2–P4 do not unlock ≤10 min** without P5–P7 (`17`, `18`).
4. **Twin / S=32** are not nodes on this graph (forbidden).
