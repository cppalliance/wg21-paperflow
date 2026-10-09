# STACK-DIAGRAM — Option B cascade + Option A MoE-only

**Sources:** `12-dense-offload-architecture.md`, `PLANNING-HANDOFF.md` §4, `SYNTHESIS.md`, `20-heterogeneous-wall.md`.

---

## Option B — Heterogeneous cascade (only ≤10 min design)

**Wall model:** `wall ≈ max(T_moe, T_dense) + T_client`  
**Central (scoped, 2× dense decode, parity):** MoE-bound ~**511 s** (planning band ~510–710 s).  
**Prereqs:** live `h200-qwen3-32b`, payload scoping, quality gate (`19`).

```mermaid
flowchart TB
  subgraph T0 ["T0 CPU — no LLM"]
    DET["det metadata / outline<br/>compare_metadata_outline()"]
    SC["metadata Tier A+B short-circuit<br/>v11 — already landed"]
  end

  subgraph CLIENT ["tapetum client c=32"]
    R["service router<br/>per-pod semaphores"]
  end

  subgraph DENSE ["T1 dense — h200-qwen3-32b S=32–48"]
    U["unit checks ~1502<br/>scoped ~10–15k"]
    MD["metadata LLM 377<br/>optional if det-metadata not shipped"]
  end

  subgraph MOE ["T2 MoE — alliance-pod S=16"]
    M["PDF monolith / HTML tier-1 ~381"]
    T2["HTML tier-2 ~23"]
    P["page escalation ~16"]
    O["oversize units 8"]
    E["escalate ≤15% units from dense"]
  end

  SC --> R
  DET --> R
  R -->|"131k scoped units / meta"| DENSE
  R -->|"393k full-doc / oversize"| MOE
  U -->|"fail / escalate ≤15%"| E
  U -->|"token preflight oversize"| O
```

### Option B call split (report 12)

| Lane | Calls | Role |
|------|------:|------|
| MoE `alliance-pod` | ~428 | Monolith, HTML tier-1/2, page esc, oversize units, escalations |
| Dense `h200-qwen3-32b` | ~1879 | In-budget units + metadata (metadata drops if det-diff ships) |

```mermaid
flowchart LR
  subgraph client [tapetum client c=32]
    R[service router]
  end

  subgraph moe [alliance-pod S=16]
    M[monolith + HTML t1]
    P[page esc ~16]
    O[oversize units 8]
    T2[tier-2 ~23]
  end

  subgraph dense [h200-qwen3-32b S=32-48]
    U[unit checks ~1502]
    MD[metadata 377]
  end

  R -->|393k or oversize| moe
  R -->|131k scoped| dense
```

**Scheduling:** `Semaphore(16)` on MoE, `Semaphore(32–48)` on dense. Fleet wall = **max**, not sum.

**Reserve (not primary):** `b300-qwen36-27b` after A/B. **Avoid primary:** `b200x2-gemma4`, `b200-r1`.

---

## Option A — MoE-only (shippable without dense infra)

**Wall model:** `wall ≈ (N_rem × L_eff) / 16 + T + C − L_abs`  
**Honest cold after full MoE package:** ~**12–23 min** (MODERATE ~23–25 min; AGGRESSIVE realistic without dense ~12–15 min).  
**Do not promise ≤10 min.**

```mermaid
flowchart TB
  subgraph T0A ["T0 CPU"]
    SC2["v11 short-circuit<br/>metadata Tier A+B"]
    DET2["det-metadata shadow → fleet<br/>A/B gated"]
  end

  subgraph MOEONLY ["alliance-pod only — S=16 forever"]
    ALL["all surviving LLM calls<br/>~monolith + units + meta + esc"]
    VF["verdict-first / schema-slim"]
    RT["router combo_safe + dynamic MAX_UNIT_CHECKS"]
    OPS["server Tier-1: MBT 16384,<br/>CUDA graphs, DeepEP low-latency"]
  end

  SC2 --> ALL
  DET2 --> ALL
  ALL --> VF --> RT --> OPS
```

```mermaid
flowchart LR
  client[tapetum c=32] --> pod[alliance-pod DeepSeek-V4-Pro S=16]
  pod --> out[sidecars + fusion]
```

---

## Option C — SLA reset (no diagram change)

If dense will not restart and twin stays forbidden: publish **~15–20 min** as the goal; stop the 10-min program. Stack remains Option A.

---

## Blockers on the diagram

| Node | Blocker |
|------|---------|
| Dense subgraph | All dense endpoints **404** today (`26`) — ask ops (`INFRA-ASK.md`) |
| Scoped unit edge | Payload scoping **not landed** — without it dense is negative EV |
| Ship edge | Quality gate ~0.8–1.2 h (`QUALITY-PROTOCOL.md`) |
