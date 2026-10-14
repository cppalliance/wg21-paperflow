# CHECK: Heterogeneous wall ~511 s MoE-bound

**Claim:** Full dense offload @ 2× yields ~511 s fleet wall, MoE-bound.
**Source:** `12-dense-offload-architecture.md`, `20-heterogeneous-wall.md`

## Quote

> MoE: monolith + … | ~428 | 19–20 s | 16 | **~511**  
> **Fleet (parallel)** | — | — | — | **~511**  
> **MoE-bound.**  
> — `12-dense-offload-architecture.md`
>
> Full unit+metadata offload (82.6%) @ 2× → **~511 s**  
> — `20-heterogeneous-wall.md`

## Verdict

**CONFIRMED** — both 12 and 20 give ~511 s MoE-bound central wall.
